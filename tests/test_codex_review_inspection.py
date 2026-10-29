"""Tests for the untrusted-head inspection-only review input, provenance and orchestration.

Covers tests/codex_review_run.py's inspection-only building blocks (Phase
85.1, D-07): PR/CI preconditions (inspect_untrusted_pr, ci_evidence,
flatten_pages), the inert inspection input built purely from git objects
(build_inspection_input), the inspection-only prompt (new_input_fence,
render_inspection_prompt), trusted-main grader provenance
(establish_trusted_main, trusted_main_grader_supports_mode), the inner Codex
argv and event-stream audit (inspection_codex_argv, audit_event_types), the
isolation-boundary gate and launch seam (verify_isolation_boundary,
run_untrusted_codex), and the end-to-end orchestration that wires all of the
above into execute() (D-07, B14). Every git/gh/Python command is answered by
a scripted command runner; no real subprocess, checkout, or Codex call is
ever made.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from tests import codex_review_run as runner
from tests.codex_review_run import (
    CI_READY_CHECK_NAME,
    GIT_SAFE_PREFIX,
    INSPECTION_PLACEHOLDERS,
    INSPECTION_TEMPLATE_HEADING,
    MAX_INSPECTION_INPUT_BYTES,
    PER_FILE_CONTENT_LIMIT,
    REPO_SLUG,
    TRUSTED_MAIN_REF,
    ReviewRun,
    RunnerError,
    audit_event_types,
    build_inspection_input,
    ci_evidence,
    establish_trusted_main,
    flatten_pages,
    inspect_untrusted_pr,
    inspection_codex_argv,
    new_input_fence,
    render_inspection_prompt,
    run_untrusted_codex,
    trusted_main_grader_supports_mode,
    verify_isolation_boundary,
)

H = "1" * 40  # reviewed head
B = "2" * 40  # reviewed base (the merge-base of the PR base and head)
PR_BASE_SHA = "4" * 40  # the PR's raw baseRefOid, before computing the merge-base
M = "3" * 40  # origin/main SHA
PR_NUMBER = "91"
PR_URL = f"https://github.com/{REPO_SLUG}/pull/{PR_NUMBER}"
PHASE_DIR = Path(".planning/phases/00-codex-review-inspection-test-fixture")


def _run(**overrides) -> ReviewRun:
    values = {
        "head": H,
        "base": B,
        "label": "inspection",
        "attempt": 1,
        "pr_url": PR_URL,
        "scope": "Phase 85.1 changes",
        "phase_dir": PHASE_DIR,
        "trusted": False,
    }
    values.update(overrides)
    return ReviewRun(**values)


class _ScriptedRunner:
    """Records every command; answers by matching argv against canned responses.

    *script* is an ordered list of (matcher, response) pairs, checked in
    order; the first whose matcher accepts argv answers the call. A matcher
    is a tuple (matches when argv[:len(matcher)] == tuple(matcher)) or a
    callable(argv) -> bool. *response* is a subprocess.CompletedProcess or a
    callable(argv, **kwargs) -> subprocess.CompletedProcess (so a test can
    make a call raise, or inspect kwargs). Any argv matching nothing raises
    AssertionError, so a test proves exactly which commands ran.
    """

    def __init__(self, script) -> None:
        self.calls: list[list[str]] = []
        self.script = list(script)

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        for matcher, response in self.script:
            matched = matcher(argv) if callable(matcher) else tuple(argv[: len(matcher)]) == tuple(matcher)
            if matched:
                if isinstance(response, subprocess.CompletedProcess):
                    return response
                return response(argv, **kwargs)
        raise AssertionError(f"unscripted command: {argv}")


def _ok(stdout: str | bytes = "", returncode: int = 0):
    return lambda argv, **kwargs: subprocess.CompletedProcess(argv, returncode, stdout=stdout)


FORBIDDEN_ARGV_WORDS = ("worktree", "checkout", "switch", "clone", "archive", "restore")
FORBIDDEN_FIRST_WORDS = ("uv", "pytest", "python", "python3", "pip", "npm", "node", "make", "sh", "bash", "codex")


def _assert_no_checkout_or_execution(calls: list[list[str]]) -> None:
    for call in calls:
        joined = " ".join(str(part) for part in call)
        assert not any(word in joined for word in FORBIDDEN_ARGV_WORDS), call
        assert call[0] not in FORBIDDEN_FIRST_WORDS, call


# --- Constants sanity (contract wiring) --------------------------------------


def test_inspection_template_heading_and_placeholders() -> None:
    expected_placeholders = frozenset(
        {"PR_URL", "HEAD_SHA", "BASE_SHA", "SCOPE", "CI_EVIDENCE", "INPUT_FENCE", "INPUT"}
    )
    assert INSPECTION_TEMPLATE_HEADING == "## Inspection-only prompt (version 1)"
    assert expected_placeholders == INSPECTION_PLACEHOLDERS
    assert runner.inspection_template_version() == "1"


def test_inspection_byte_limits() -> None:
    assert PER_FILE_CONTENT_LIMIT == 262_144
    assert MAX_INSPECTION_INPUT_BYTES == 1_500_000


# --- inspect_untrusted_pr ----------------------------------------------------


def _gh_json(**fields) -> str:
    data = {
        "author": {"login": "dependabot[bot]", "is_bot": True},
        "isCrossRepository": False,
        "headRefOid": H,
        "baseRefOid": PR_BASE_SHA,
        "state": "OPEN",
    }
    data.update(fields)
    return json.dumps(data)


def _pr_script(**gh_fields) -> list:
    return [
        (("gh", "pr", "view"), _ok(stdout=_gh_json(**gh_fields))),
        (("git", "fetch", "--no-tags", "origin", f"pull/{PR_NUMBER}/head"), _ok()),
        (("git", "rev-parse", "--verify", "FETCH_HEAD^{commit}"), _ok(stdout=f"{H}\n")),
        (("git", "merge-base",), _ok(stdout=f"{B}\n")),
    ]


def test_inspect_untrusted_pr_rejects_local_checkpoint() -> None:
    run = _run(pr_url=runner.LOCAL_CHECKPOINT_PR_URL)
    fake = _ScriptedRunner([])
    with pytest.raises(RunnerError, match="inspection-only review needs CI evidence for the exact head"):
        inspect_untrusted_pr(run, fake)
    assert fake.calls == []


def test_inspect_untrusted_pr_rejects_other_repository() -> None:
    run = _run(pr_url="https://github.com/someone-else/fork/pull/5")
    fake = _ScriptedRunner([])
    with pytest.raises(RunnerError, match="only thejuran/triggarr PRs"):
        inspect_untrusted_pr(run, fake)
    assert fake.calls == []


def test_inspect_untrusted_pr_rejects_closed_state() -> None:
    run = _run()
    fake = _ScriptedRunner(_pr_script(state="CLOSED"))
    with pytest.raises(RunnerError, match="PR is not open"):
        inspect_untrusted_pr(run, fake)


def test_inspect_untrusted_pr_rejects_merged_state() -> None:
    run = _run()
    fake = _ScriptedRunner(_pr_script(state="MERGED"))
    with pytest.raises(RunnerError, match="PR is not open"):
        inspect_untrusted_pr(run, fake)


def test_inspect_untrusted_pr_rejects_head_mismatch() -> None:
    run = _run()
    fake = _ScriptedRunner(_pr_script(headRefOid="9" * 40))
    with pytest.raises(RunnerError, match="PR head is"):
        inspect_untrusted_pr(run, fake)


def test_inspect_untrusted_pr_rejects_fetched_head_mismatch() -> None:
    run = _run()
    script = _pr_script()
    script[2] = (("git", "rev-parse", "--verify", "FETCH_HEAD^{commit}"), _ok(stdout=("9" * 40) + "\n"))
    fake = _ScriptedRunner(script)
    with pytest.raises(RunnerError, match="fetched head does not match"):
        inspect_untrusted_pr(run, fake)


def test_inspect_untrusted_pr_rejects_base_not_merge_base() -> None:
    run = _run(base="5" * 40)  # not the real merge-base B
    fake = _ScriptedRunner(_pr_script())
    with pytest.raises(RunnerError, match="--base must be the merge-base"):
        inspect_untrusted_pr(run, fake)


def test_inspect_untrusted_pr_accepts_bot_author_and_cross_repository_fork() -> None:
    run = _run()
    fake = _ScriptedRunner(_pr_script(author={"login": "dependabot[bot]", "is_bot": True}, isCrossRepository=True))

    result = inspect_untrusted_pr(run, fake)

    assert result == {
        "number": int(PR_NUMBER),
        "author_login": "dependabot[bot]",
        "is_cross_repository": True,
        "head_ref_oid": H,
        "base_ref_oid": PR_BASE_SHA,
        "merge_base": B,
    }


# --- flatten_pages / ci_evidence ---------------------------------------------


def _check_run(id_, name, head_sha=H, status="completed", conclusion="success", **extra):
    data = {
        "id": id_,
        "name": name,
        "head_sha": head_sha,
        "status": status,
        "conclusion": conclusion,
        "html_url": f"https://x/{id_}",
    }
    data.update(extra)
    return data


def test_flatten_pages_concatenates_pages() -> None:
    pages = [{"check_runs": [_check_run(1, "CodeQL")]}, {"check_runs": [_check_run(2, CI_READY_CHECK_NAME)]}]
    items = flatten_pages(json.dumps(pages), "check_runs")
    assert [item["id"] for item in items] == [1, 2]


def test_flatten_pages_rejects_non_array() -> None:
    with pytest.raises(RunnerError, match="could not read GitHub check runs"):
        flatten_pages(json.dumps({"check_runs": []}), "check_runs")


def test_flatten_pages_rejects_page_without_key() -> None:
    with pytest.raises(RunnerError, match="could not read GitHub check runs"):
        flatten_pages(json.dumps([{"other": []}]), "check_runs")


def test_flatten_pages_rejects_unparseable_text() -> None:
    with pytest.raises(RunnerError, match="could not read GitHub check runs"):
        flatten_pages("not json", "check_runs")


def _gh_api_script(pages: list) -> list:
    argv = ("gh", "api", f"repos/{REPO_SLUG}/commits/{H}/check-runs", "--paginate", "--slurp")
    return [(argv, _ok(stdout=json.dumps(pages)))]


def test_ci_evidence_finds_evidence_on_second_page() -> None:
    run = _run()
    pages = [
        {"check_runs": [_check_run(1, "CodeQL")]},
        {"check_runs": [_check_run(2, CI_READY_CHECK_NAME)]},
    ]
    fake = _ScriptedRunner(_gh_api_script(pages))

    result = ci_evidence(run, fake)

    assert result["ci_ready"]["id"] == 2
    assert {item["id"] for item in result["check_runs"]} == {1, 2}
    assert set(result["ci_ready"]) == {"id", "name", "head_sha", "status", "conclusion", "html_url"}


def test_ci_evidence_rejects_ci_ready_for_other_head() -> None:
    run = _run()
    pages = [{"check_runs": [_check_run(1, CI_READY_CHECK_NAME, head_sha="9" * 40)]}]
    fake = _ScriptedRunner(_gh_api_script(pages))
    with pytest.raises(RunnerError, match="no successful CI ready check run for this exact head"):
        ci_evidence(run, fake)


def test_ci_evidence_rejects_when_latest_ci_ready_is_failure_even_if_older_succeeded() -> None:
    run = _run()
    pages = [
        {"check_runs": [_check_run(2, CI_READY_CHECK_NAME, conclusion="success")]},
        {"check_runs": [_check_run(5, CI_READY_CHECK_NAME, conclusion="failure")]},
    ]
    fake = _ScriptedRunner(_gh_api_script(pages))
    with pytest.raises(RunnerError, match="no successful CI ready check run for this exact head"):
        ci_evidence(run, fake)


def test_ci_evidence_keeps_only_allowed_fields() -> None:
    run = _run()
    pages = [{"check_runs": [_check_run(1, CI_READY_CHECK_NAME, app={"slug": "github-actions"})]}]
    fake = _ScriptedRunner(_gh_api_script(pages))

    result = ci_evidence(run, fake)

    assert set(result["ci_ready"]) == {"id", "name", "head_sha", "status", "conclusion", "html_url"}
    assert "app" not in result["ci_ready"]


# --- build_inspection_input ---------------------------------------------------

EVIL_CONTENT = b"echo PLANTED-RUN\n"
HOOK_CONTENT = b"#!/bin/sh\necho hook\n"
BIG_CONTENT = b"x" * (300 * 1024)
BINARY_CONTENT = b"before\x00after"

CHANGED_ENTRIES = [
    ("A", "scripts/evil.sh"),
    ("A", ".githooks/pre-commit"),
    ("A", "big.txt"),
    ("A", "binary.bin"),
    ("D", "deleted.txt"),
    ("A", "link.sh"),
]

LS_TREE_OUTPUT = {
    "scripts/evil.sh": "100644 blob " + "a" * 40 + "\tscripts/evil.sh\0",
    ".githooks/pre-commit": "100755 blob " + "b" * 40 + "\t.githooks/pre-commit\0",
    "big.txt": "100644 blob " + "c" * 40 + "\tbig.txt\0",
    "binary.bin": "100644 blob " + "d" * 40 + "\tbinary.bin\0",
    "deleted.txt": "",
    "link.sh": "120000 blob " + "e" * 40 + "\tlink.sh\0",
}

CAT_FILE_CONTENT = {
    "scripts/evil.sh": EVIL_CONTENT,
    ".githooks/pre-commit": HOOK_CONTENT,
    "big.txt": BIG_CONTENT,
    "binary.bin": BINARY_CONTENT,
}

_DIFF_FLAGS = ("--no-textconv", "--no-ext-diff", "--no-color")


def _name_status_output(entries) -> str:
    fields: list[str] = []
    for status, path in entries:
        fields.append(status)
        fields.append(path)
    return "\0".join(fields) + "\0"


def _build_inspection_script(
    run: ReviewRun,
    *,
    changed_entries=CHANGED_ENTRIES,
    plan_changed_entries=(),
    full_diff_text="FULL-DIFF-TEXT",
    plan_diff_text="PLAN-DIFF-TEXT",
) -> list:
    diff_range = f"{run.base}..{run.head}"
    full_diff_argv = [*GIT_SAFE_PREFIX, "diff", diff_range, *_DIFF_FLAGS, "--", ".", *runner.EXCLUDE_PATHSPECS]
    plan_diff_argv = [*GIT_SAFE_PREFIX, "diff", diff_range, *_DIFF_FLAGS, "--", *runner.PLAN_PATHSPECS]
    name_status_full = [
        *GIT_SAFE_PREFIX,
        "diff",
        "--name-status",
        "-z",
        "--no-renames",
        *_DIFF_FLAGS,
        f"{run.base}..{run.head}",
        "--",
        ".",
        *runner.EXCLUDE_PATHSPECS,
    ]
    name_status_plan = [
        *GIT_SAFE_PREFIX,
        "diff",
        "--name-status",
        "-z",
        "--no-renames",
        *_DIFF_FLAGS,
        f"{run.base}..{run.head}",
        "--",
        *runner.PLAN_PATHSPECS,
    ]

    def _exact(expected):
        return lambda argv: argv == expected

    script = [
        (_exact(full_diff_argv), _ok(stdout=full_diff_text)),
        (_exact(plan_diff_argv), _ok(stdout=plan_diff_text)),
        (_exact(name_status_full), _ok(stdout=_name_status_output(changed_entries))),
        (_exact(name_status_plan), _ok(stdout=_name_status_output(plan_changed_entries))),
    ]
    for _, path in [*changed_entries, *plan_changed_entries]:
        ls_tree_argv = [*GIT_SAFE_PREFIX, "ls-tree", "-z", run.head, "--", path]
        script.append((_exact(ls_tree_argv), _ok(stdout=LS_TREE_OUTPUT.get(path, ""))))
        if path in CAT_FILE_CONTENT:
            cat_file_argv = [*GIT_SAFE_PREFIX, "cat-file", "blob", f"{run.head}:{path}"]
            script.append((_exact(cat_file_argv), _ok(stdout=CAT_FILE_CONTENT[path])))
    return script


def test_build_inspection_input_includes_diff_sections_and_safe_git_prefix() -> None:
    run = _run()
    fake = _ScriptedRunner(_build_inspection_script(run))

    text, stats = build_inspection_input(run, fake)

    assert "### In-scope diff" in text
    assert "FULL-DIFF-TEXT" in text
    assert "### Phase-plan diff" in text
    assert "PLAN-DIFF-TEXT" in text
    assert "### Changed files at head" in text
    for _, path in CHANGED_ENTRIES:
        assert f"#### {path}" in text
    for call in fake.calls:
        assert call[:5] == list(GIT_SAFE_PREFIX)
    assert stats["bytes"] == len(text.encode("utf-8"))
    assert stats["oversize"] is False


def test_build_inspection_input_omits_oversize_file() -> None:
    run = _run()
    fake = _ScriptedRunner(_build_inspection_script(run))

    text, stats = build_inspection_input(run, fake)

    assert "content omitted:" in text
    assert "exceeds PER_FILE_CONTENT_LIMIT; review the diff hunks" in text
    assert str(len(BIG_CONTENT)) in text
    assert stats["files_omitted"] >= 1


def test_build_inspection_input_omits_binary_file() -> None:
    run = _run()
    fake = _ScriptedRunner(_build_inspection_script(run))

    text, _stats = build_inspection_input(run, fake)

    assert "content omitted: binary" in text


def test_build_inspection_input_notes_symlink() -> None:
    run = _run()
    fake = _ScriptedRunner(_build_inspection_script(run))

    text, _stats = build_inspection_input(run, fake)

    assert "symlink at head (target not followed)" in text


def test_build_inspection_input_notes_deleted_file() -> None:
    run = _run()
    fake = _ScriptedRunner(_build_inspection_script(run))

    text, _stats = build_inspection_input(run, fake)

    assert "deleted at head" in text


def test_build_inspection_input_includes_small_text_file_verbatim() -> None:
    run = _run()
    fake = _ScriptedRunner(_build_inspection_script(run))

    text, _stats = build_inspection_input(run, fake)

    assert HOOK_CONTENT.decode("utf-8") in text


def test_build_inspection_input_marks_oversize_without_raising(monkeypatch) -> None:
    monkeypatch.setattr(runner, "MAX_INSPECTION_INPUT_BYTES", 10)
    run = _run()
    fake = _ScriptedRunner(_build_inspection_script(run, full_diff_text="way more than ten bytes of diff text"))

    text, stats = build_inspection_input(run, fake)

    assert stats["oversize"] is True
    assert text


def test_inspection_input_never_checks_out_or_writes_the_head(tmp_path, monkeypatch) -> None:
    def _forbidden_mkdtemp(*_args, **_kwargs):
        raise AssertionError("build_inspection_input must never create a scratch directory")

    monkeypatch.setattr(runner.tempfile, "mkdtemp", _forbidden_mkdtemp)
    run = _run()
    fake = _ScriptedRunner(_build_inspection_script(run))

    build_inspection_input(run, fake)

    _assert_no_checkout_or_execution(fake.calls)
    assert list(tmp_path.iterdir()) == []


def test_planted_files_stay_inert_text() -> None:
    run = _run()
    fake = _ScriptedRunner(_build_inspection_script(run))

    text, _stats = build_inspection_input(run, fake)
    fence = new_input_fence(text)
    prompt = render_inspection_prompt(run, ci_evidence_text="CI evidence text", input_text=text, fence=fence)

    assert "echo PLANTED-RUN" in text
    # rindex, not index: the prompt's own instructional sentence mentions
    # "{fence}-BEGIN"/"{fence}-END" by name earlier in the text, so the first
    # occurrence is prose, not the real trailing fence line.
    begin = prompt.rindex(f"{fence}-BEGIN")
    end = prompt.rindex(f"{fence}-END")
    assert "echo PLANTED-RUN" not in prompt[:begin]
    assert "echo PLANTED-RUN" not in prompt[end:]
    assert "echo PLANTED-RUN" in prompt[begin:end]


# --- new_input_fence ----------------------------------------------------------


def test_new_input_fence_format() -> None:
    fence = new_input_fence("some text")
    prefix = runner.INPUT_FENCE_PREFIX
    assert fence.startswith(prefix)
    suffix = fence[len(prefix) :]
    assert len(suffix) == 32
    assert all(char in "0123456789abcdef" for char in suffix)


def test_new_input_fence_regenerates_on_collision(monkeypatch) -> None:
    collide_suffix = "a" * 32
    fresh_suffix = "b" * 32
    answers = iter([collide_suffix, fresh_suffix])
    monkeypatch.setattr(runner.secrets, "token_hex", lambda _n: next(answers))

    fence = new_input_fence(f"...{runner.INPUT_FENCE_PREFIX}{collide_suffix}...")

    assert fence == runner.INPUT_FENCE_PREFIX + fresh_suffix


# --- render_inspection_prompt --------------------------------------------------


def test_render_inspection_prompt_substitutes_all_placeholders() -> None:
    run = _run(scope="Dependabot bump")
    text = render_inspection_prompt(
        run, ci_evidence_text="CI-EVIDENCE-TEXT", input_text="INPUT-TEXT", fence="TRIGGARR-INERT-deadbeef"
    )
    assert "{{" not in text
    assert run.pr_url in text
    assert H in text and B in text
    assert "Dependabot bump" in text
    assert "CI-EVIDENCE-TEXT" in text
    assert "INPUT-TEXT" in text
    assert "TRIGGARR-INERT-deadbeef-BEGIN" in text
    assert "TRIGGARR-INERT-deadbeef-END" in text


def test_render_inspection_prompt_keeps_literal_placeholder_look_alikes() -> None:
    run = _run()
    text = render_inspection_prompt(
        run, ci_evidence_text="evidence", input_text="literal {{HEAD_SHA}} stays put", fence="TRIGGARR-INERT-ffff"
    )
    assert "literal {{HEAD_SHA}} stays put" in text


# --- establish_trusted_main ---------------------------------------------------


def _trusted_main_script(
    *,
    fetch_rc: int = 0,
    main_sha: str = M,
    rev_parse_main_rc: int = 0,
    harness_head: str = M,
    rev_parse_harness_rc: int = 0,
    status_dirty: str = "",
    ancestor_rc: int = 0,
) -> list:
    return [
        (("git", "fetch", "--no-tags", "origin", f"+refs/heads/main:{TRUSTED_MAIN_REF}"), _ok(returncode=fetch_rc)),
        (
            ("git", "rev-parse", "--verify", f"{TRUSTED_MAIN_REF}^{{commit}}"),
            _ok(stdout=f"{main_sha}\n", returncode=rev_parse_main_rc),
        ),
        (
            lambda argv: argv == ["git", "rev-parse", "HEAD"],
            _ok(stdout=f"{harness_head}\n", returncode=rev_parse_harness_rc),
        ),
        (("git", "status", "--porcelain"), _ok(stdout=status_dirty)),
        (("git", "merge-base", "--is-ancestor"), _ok(returncode=ancestor_rc)),
    ]


def test_establish_trusted_main_returns_provenance_dict() -> None:
    run = _run(base=B)
    fake = _ScriptedRunner(_trusted_main_script())

    result = establish_trusted_main(run, fake)

    assert result == {
        "main_ref": TRUSTED_MAIN_REF,
        "main_sha": M,
        "harness_head": M,
        "base": B,
        "base_on_main": True,
        "grader_ref": M,
        "grader_source": "trusted-origin-main",
    }


def test_establish_trusted_main_fetch_failure() -> None:
    run = _run()
    fake = _ScriptedRunner(_trusted_main_script(fetch_rc=1))
    with pytest.raises(RunnerError, match="could not fetch origin main"):
        establish_trusted_main(run, fake)


def test_establish_trusted_main_rev_parse_main_failure() -> None:
    run = _run()
    fake = _ScriptedRunner(_trusted_main_script(main_sha="not-a-sha"))
    with pytest.raises(RunnerError, match="could not resolve origin/main"):
        establish_trusted_main(run, fake)


def test_establish_trusted_main_harness_head_mismatch() -> None:
    run = _run()
    fake = _ScriptedRunner(_trusted_main_script(harness_head=H))
    with pytest.raises(RunnerError) as exc_info:
        establish_trusted_main(run, fake)
    message = str(exc_info.value)
    assert "the harness checkout is" in message
    assert "run from a checkout of origin/main (D-02)" in message


def test_establish_trusted_main_audited_inputs_dirty() -> None:
    run = _run()
    fake = _ScriptedRunner(_trusted_main_script(status_dirty=" M tests/codex_review_run.py\n"))
    with pytest.raises(RunnerError, match="audited inputs have uncommitted changes"):
        establish_trusted_main(run, fake)


def test_establish_trusted_main_oserror_wraps_exception_type_name() -> None:
    run = _run()

    def _raise(argv, **kwargs):
        raise OSError("boom")

    fake = _ScriptedRunner([(("git", "fetch"), _raise)])
    with pytest.raises(
        RunnerError, match=r"base grader provenance not established: could not fetch origin main \(OSError\)"
    ):
        establish_trusted_main(run, fake)


def test_malicious_base_is_rejected_before_any_grader_runs() -> None:
    run = _run(base="9" * 40)
    fake = _ScriptedRunner(_trusted_main_script(ancestor_rc=1))

    with pytest.raises(RunnerError, match="is not an ancestor of origin/main"):
        establish_trusted_main(run, fake)

    for call in fake.calls:
        joined = " ".join(str(part) for part in call)
        assert "git show" not in joined
        assert call[0] != sys.executable


def test_malicious_base_unexpected_exit_fails_closed() -> None:
    run = _run(base="9" * 40)
    fake = _ScriptedRunner(_trusted_main_script(ancestor_rc=128))

    with pytest.raises(RunnerError, match="git merge-base exited 128"):
        establish_trusted_main(run, fake)


# --- trusted_main_grader_supports_mode ----------------------------------------


def test_trusted_main_grader_supports_mode_true(tmp_path) -> None:
    grader_path = tmp_path / "codex_report_status.py"

    def _runner(argv, **kwargs):
        assert argv == [sys.executable, str(grader_path), "--help"]
        return subprocess.CompletedProcess(argv, 0, stdout="--review-mode {trusted,inspection-only}\n")

    assert trusted_main_grader_supports_mode(grader_path, _runner) is True


def test_older_main_checker_is_reported(tmp_path) -> None:
    grader_path = tmp_path / "codex_report_status.py"

    def _runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout="usage: codex_report_status.py [-h] --legacy-v1\n")

    assert trusted_main_grader_supports_mode(grader_path, _runner) is False


def test_trusted_main_grader_supports_mode_false_on_nonzero_exit(tmp_path) -> None:
    grader_path = tmp_path / "codex_report_status.py"

    def _runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 2, stdout="--review-mode inspection-only")

    assert trusted_main_grader_supports_mode(grader_path, _runner) is False


def test_trusted_main_grader_supports_mode_false_on_oserror(tmp_path) -> None:
    grader_path = tmp_path / "codex_report_status.py"

    def _runner(argv, **kwargs):
        raise OSError("boom")

    assert trusted_main_grader_supports_mode(grader_path, _runner) is False


# --- inspection_codex_argv (the inner `codex exec` command, B04-R3) -----------

REQUIRED_DISABLED_FEATURES = frozenset(
    {
        "shell_tool",
        "unified_exec",
        "code_mode_host",
        "browser_use",
        "browser_use_external",
        "browser_use_full_cdp_access",
        "computer_use",
        "in_app_browser",
        "apps",
        "plugins",
        "remote_plugin",
        "plugin_sharing",
        "view_image",
        "image_generation",
        "sleep_tool",
        "tool_suggest",
        "skill_mcp_dependency_install",
        "tool_call_mcp_elicitation",
        "hooks",
        "multi_agent",
        "multi_agent_v2",
        "workspace_dependencies",
    }
)


def test_schema_in_container_path() -> None:
    assert runner.SCHEMA_IN_CONTAINER == "/schema/codex-review-findings.schema.json"


def test_disabled_features_cover_the_required_set_with_no_duplicates() -> None:
    # Every entry was confirmed present in `codex features list` on this
    # machine (codex-cli 0.153.4); a feature this build does not list is
    # omitted here and named in the plan SUMMARY, never invented.
    assert set(runner.DISABLED_FEATURES) == REQUIRED_DISABLED_FEATURES
    assert len(runner.DISABLED_FEATURES) == len(set(runner.DISABLED_FEATURES))


def test_inspection_codex_argv_golden() -> None:
    argv = inspection_codex_argv()

    expected = [
        "codex",
        "exec",
        "--sandbox",
        "read-only",
        "--ephemeral",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--ignore-rules",
        "--strict-config",
        "-C",
        "/work",
    ]
    for feature in runner.DISABLED_FEATURES:
        expected += ["--disable", feature]
    expected += ["--output-schema", runner.SCHEMA_IN_CONTAINER, "--json", "-o", "/out/last.json", "-"]

    assert argv == expected


def test_inspection_codex_argv_honors_cwd_and_last_json_overrides() -> None:
    argv = inspection_codex_argv(cwd="/other-work", last_json="/other-out/last.json")
    assert "/other-work" in argv
    assert "/other-out/last.json" in argv
    assert "/work" not in argv


def test_inspection_codex_argv_never_grants_write_access() -> None:
    argv = inspection_codex_argv()
    assert "--add-dir" not in argv
    assert "workspace-write" not in argv
    assert "danger-full-access" not in argv
    assert not any(str(part).startswith("--dangerously") for part in argv)


# --- audit_event_types (the event-stream audit, T-85.1-22) -------------------


def _write_jsonl(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


def test_audit_event_types_clean_stream_is_empty(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    _write_jsonl(
        path,
        [
            {"type": "thread.started"},
            {"type": "turn.started"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "hi"}},
            {"type": "item.completed", "item": {"type": "reasoning", "text": "..."}},
            {"type": "turn.completed"},
        ],
    )
    assert audit_event_types(path) == []


def test_audit_event_types_flags_command_execution(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    _write_jsonl(path, [{"type": "item.completed", "item": {"type": "command_execution"}}])
    assert audit_event_types(path) == ["inspection-only review used a tool: command_execution"]


@pytest.mark.parametrize("item_type", ["file_change", "mcp_tool_call", "web_search", "error"])
def test_audit_event_types_flags_every_disallowed_item_type(tmp_path, item_type) -> None:
    path = tmp_path / "events.jsonl"
    _write_jsonl(path, [{"type": "item.completed", "item": {"type": item_type}}])
    reasons = audit_event_types(path)
    assert len(reasons) == 1
    assert item_type in reasons[0]


def test_audit_event_types_flags_unexpected_top_level_event(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    _write_jsonl(path, [{"type": "turn.failed"}])
    assert audit_event_types(path) == ["unexpected Codex event: turn.failed"]


def test_audit_event_types_raises_on_unparseable_line(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text("not json\n", encoding="utf-8")
    with pytest.raises(RunnerError, match="could not audit Codex event stream"):
        audit_event_types(path)


def test_audit_event_types_missing_file_is_a_reason(tmp_path) -> None:
    path = tmp_path / "missing.jsonl"
    assert audit_event_types(path) == ["no Codex event stream recorded"]


# --- verify_isolation_boundary (the mandatory gate, B04-R3) ------------------


def test_verify_isolation_boundary_gate_returns_unverified_and_issues_no_command() -> None:
    run = _run()
    fake = _ScriptedRunner([])
    inner_argv = inspection_codex_argv()

    boundary = verify_isolation_boundary(run, fake, scratch=Path("/tmp/does-not-matter"), inner_argv=inner_argv)

    assert boundary == {
        "boundary_version": 1,
        "verdict": "unverified",
        "reasons": ["deterministic container checks are not available in this build"],
        "checked_at": boundary["checked_at"],
        "head": run.head,
        "label": run.label,
        "attempt": run.attempt,
    }
    datetime.fromisoformat(boundary["checked_at"])  # ISO-8601, parseable
    assert fake.calls == []


# --- run_untrusted_codex (the only launch seam, B04-R3) ----------------------


def test_run_untrusted_codex_seam_rejects_unverified_boundary() -> None:
    run = _run()
    fake = _ScriptedRunner([])
    boundary = {"verdict": "unverified"}

    with pytest.raises(RunnerError, match="untrusted Codex launch requires a verified container boundary"):
        run_untrusted_codex(
            run, inner_argv=inspection_codex_argv(), prompt="prompt", boundary=boundary, command_runner=fake
        )
    assert fake.calls == []


def test_run_untrusted_codex_seam_also_refuses_a_verified_boundary_in_this_plan() -> None:
    run = _run()
    fake = _ScriptedRunner([])
    boundary = {"verdict": "verified"}

    with pytest.raises(RunnerError, match="untrusted Codex launch requires a verified container boundary"):
        run_untrusted_codex(
            run, inner_argv=inspection_codex_argv(), prompt="prompt", boundary=boundary, command_runner=fake
        )
    assert fake.calls == []
    assert all(call[0] != "codex" for call in fake.calls)
