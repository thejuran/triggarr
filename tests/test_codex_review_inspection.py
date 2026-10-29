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
    execute,
    flatten_pages,
    inspect_untrusted_pr,
    inspection_codex_argv,
    inspection_meta,
    new_input_fence,
    render_inspection_prompt,
    trusted_main_grader_supports_mode,
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


# --- verify_isolation_boundary / run_untrusted_codex (B04-R3) ----------------
#
# Plan 85.1-06 pinned these two seams as an always-"unverified"/always-refuse
# stub (tested here at the time). Plan 85.1-08 replaces both bodies with the
# real container boundary and launch; the stub-specific tests that lived here
# (asserting "always unverified, issues no command" and "always refuses,
# verified or not") are gone with the stub they tested. The real contract --
# deterministic checks, the launch under a ContainerLedger, every failure
# mode -- is covered in tests/test_codex_review_container.py, which also
# owns the scripted docker runner these seams now need. The orchestration
# tests below (which monkeypatch both seams rather than calling the real
# implementation) are unaffected and still pin _execute_inspection's wiring.


# --- Orchestration: execute() / _execute_untrusted() / _execute_inspection() -
# (D-07, B14). The pipeline's own building blocks (inspect_untrusted_pr,
# ci_evidence, build_inspection_input, establish_trusted_main,
# materialize_grader, trusted_main_grader_supports_mode,
# verify_isolation_boundary, run_untrusted_codex) are each unit-tested above
# or in Plan 85.1-05; here they are monkeypatched to canned values so these
# tests exercise only the NEW orchestration code -- the order of operations,
# the outputs, the grading and the exit codes. The few remaining real
# command_runner calls (git status, git rev-parse HEAD, git diff
# --name-only, a second gh pr view, and the head/base checker subprocess)
# are answered by _OrchestrationRunner; anything unscripted raises
# AssertionError.

PR_NUMBER_INT = int(PR_NUMBER)

DEFAULT_PR_INFO = {
    "number": PR_NUMBER_INT,
    "author_login": "dependabot[bot]",
    "is_cross_repository": False,
    "head_ref_oid": H,
    "base_ref_oid": PR_BASE_SHA,
    "merge_base": B,
}

DEFAULT_CI_EVIDENCE = {
    "check_runs": [
        {
            "id": 1,
            "name": CI_READY_CHECK_NAME,
            "head_sha": H,
            "status": "completed",
            "conclusion": "success",
            "html_url": "https://x/1",
        }
    ],
    "ci_ready": {
        "id": 1,
        "name": CI_READY_CHECK_NAME,
        "head_sha": H,
        "status": "completed",
        "conclusion": "success",
        "html_url": "https://x/1",
    },
}

DEFAULT_INPUT_TEXT = "### In-scope diff\nFAKE DIFF\n"
DEFAULT_INPUT_STATS = {
    "bytes": len(DEFAULT_INPUT_TEXT.encode("utf-8")),
    "files_included": 1,
    "files_omitted": 0,
    "oversize": False,
}

DEFAULT_PROVENANCE = {
    "main_ref": TRUSTED_MAIN_REF,
    "main_sha": M,
    "harness_head": M,
    "base": B,
    "base_on_main": True,
    "grader_ref": M,
    "grader_source": "trusted-origin-main",
}

DEFAULT_BOUNDARY_VERIFIED = {
    "boundary_version": 1,
    "verdict": "verified",
    "reasons": [],
    "checked_at": "2026-10-29T00:00:00+00:00",
    "head": H,
    "label": "inspection",
    "attempt": 1,
}

DEFAULT_BOUNDARY_UNVERIFIED = {
    "boundary_version": 1,
    "verdict": "unverified",
    "reasons": ["deterministic container checks are not available in this build"],
    "checked_at": "2026-10-29T00:00:00+00:00",
    "head": H,
    "label": "inspection",
    "attempt": 1,
}

CLEAN_EVENTS = [
    {"type": "thread.started"},
    {"type": "turn.started"},
    {"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}},
    {"type": "turn.completed"},
]

TOOL_USE_EVENTS = [
    {"type": "thread.started"},
    {"type": "item.completed", "item": {"type": "command_execution", "command": "cat /etc/passwd"}},
    {"type": "turn.completed"},
]

COMPLETE_STATUS_JSON = (
    json.dumps(
        {
            "status": "complete",
            "reasons": [],
            "qualified_ids": [],
            "finding_count": 0,
            "inspected_head": H,
            "inspected_base": B,
        }
    )
    + "\n"
)

INCOMPLETE_STATUS_JSON = (
    json.dumps(
        {
            "status": "incomplete",
            "reasons": ["codex exited 1"],
            "qualified_ids": [],
            "finding_count": 0,
            "inspected_head": H,
            "inspected_base": B,
        }
    )
    + "\n"
)


def _use_tmp_repo_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    (tmp_path / PHASE_DIR).mkdir(parents=True)


class _OrchestrationRunner:
    """Answers the real command_runner calls left once the pipeline's own
    building blocks are monkeypatched (see _patch_pipeline): git status
    (audit_inputs), git rev-parse HEAD (harness_head), git diff --name-only
    (audited_inputs_changed), a second gh pr view (the post-run current
    head), `git show` (only when materialize_grader is NOT monkeypatched),
    and the head/base checker subprocess calls (distinguished by the
    "codex-base-grader" mkdtemp prefix _run_base_grader uses for its own
    temp dir). Anything else raises AssertionError, proving exactly which
    commands ran.
    """

    def __init__(
        self,
        *,
        dirty: str = "",
        changed_paths: str = "",
        harness_head: str = M,
        current_head_ref_oid: str = H,
        checker_stdout: str = COMPLETE_STATUS_JSON,
        checker_returncode: int = 0,
        base_checker_stdout: str | None = None,
        base_checker_returncode: int = 0,
        git_show_files: dict[str, str] | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self.dirty = dirty
        self.changed_paths = changed_paths
        self.harness_head = harness_head
        self.current_head_ref_oid = current_head_ref_oid
        self.checker_stdout = checker_stdout
        self.checker_returncode = checker_returncode
        self.base_checker_stdout = base_checker_stdout if base_checker_stdout is not None else checker_stdout
        self.base_checker_returncode = base_checker_returncode
        self.git_show_files = git_show_files or {}

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        if argv[:2] == ["git", "status"]:
            return subprocess.CompletedProcess(argv, 0, stdout=self.dirty)
        if argv == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(argv, 0, stdout=f"{self.harness_head}\n")
        if argv[:2] == ["git", "diff"] and "--name-only" in argv:
            return subprocess.CompletedProcess(argv, 0, stdout=self.changed_paths)
        if argv[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({"headRefOid": self.current_head_ref_oid}))
        if argv[:2] == ["git", "show"]:
            _, _, relpath = argv[2].partition(":")
            if relpath in self.git_show_files:
                return subprocess.CompletedProcess(argv, 0, stdout=self.git_show_files[relpath])
            return subprocess.CompletedProcess(argv, 1, stdout="")
        if argv and argv[0] == sys.executable and len(argv) > 1 and "codex_report_status.py" in str(argv[1]):
            if "codex-base-grader" in str(argv[1]):
                return subprocess.CompletedProcess(
                    argv, self.base_checker_returncode, stdout=self.base_checker_stdout
                )
            return subprocess.CompletedProcess(argv, self.checker_returncode, stdout=self.checker_stdout)
        raise AssertionError(f"unscripted command: {argv}")


def _patch_pipeline(
    monkeypatch,
    *,
    pr_info: dict | None = None,
    ci: dict | None = None,
    input_text: str | None = None,
    input_stats: dict | None = None,
    provenance: dict | None = None,
    provenance_error: str | None = None,
    patch_materialize_grader: bool = True,
    grader_supports_mode: bool = True,
    boundary: dict | None = None,
    codex_events: list[dict] | None = None,
    codex_report: dict | None = None,
    codex_result: tuple[int, list[str]] | None = None,
    codex_error: str | None = None,
) -> None:
    """Monkeypatch every building block execute()/_execute_untrusted()/
    _execute_inspection() calls, except the handful of raw command_runner
    calls _OrchestrationRunner answers. Each keyword overrides one seam;
    unset ones fall back to a COMPLETE, happy-path default (verified
    boundary, clean event stream, no audited-input change).
    """
    monkeypatch.setattr(runner, "inspect_untrusted_pr", lambda run, command_runner: dict(pr_info or DEFAULT_PR_INFO))
    monkeypatch.setattr(runner, "ci_evidence", lambda run, command_runner: dict(ci or DEFAULT_CI_EVIDENCE))

    text = input_text if input_text is not None else DEFAULT_INPUT_TEXT
    stats = dict(input_stats) if input_stats is not None else dict(DEFAULT_INPUT_STATS)
    monkeypatch.setattr(runner, "build_inspection_input", lambda run, command_runner: (text, stats))

    if provenance_error is not None:

        def _raise_provenance(run, command_runner):
            raise RunnerError(provenance_error)

        monkeypatch.setattr(runner, "establish_trusted_main", _raise_provenance)
    else:
        monkeypatch.setattr(
            runner, "establish_trusted_main", lambda run, command_runner: dict(provenance or DEFAULT_PROVENANCE)
        )

    if patch_materialize_grader:
        monkeypatch.setattr(runner, "materialize_grader", lambda grader_ref, dest, command_runner: None)
    monkeypatch.setattr(
        runner, "trusted_main_grader_supports_mode", lambda grader_path, command_runner: grader_supports_mode
    )
    monkeypatch.setattr(
        runner,
        "verify_isolation_boundary",
        lambda run, command_runner, **kw: dict(boundary or DEFAULT_BOUNDARY_VERIFIED),
    )

    if codex_error is not None:

        def _raise_codex(run, **kw):
            raise RunnerError(codex_error)

        monkeypatch.setattr(runner, "run_untrusted_codex", _raise_codex)
    else:
        exit_code, problems = codex_result if codex_result is not None else (0, [])
        events = codex_events if codex_events is not None else CLEAN_EVENTS
        report = codex_report if codex_report is not None else {"verdict": "no-findings"}

        def _fake_codex(run, **kw):
            _write_jsonl(run.output(".jsonl"), events)
            run.output(".last.json").write_text(json.dumps(report), encoding="utf-8")
            return exit_code, problems

        monkeypatch.setattr(runner, "run_untrusted_codex", _fake_codex)


def _untrusted_run(**overrides) -> ReviewRun:
    return _run(trusted=False, **overrides)


def test_execute_untrusted_happy_path_is_complete(tmp_path, monkeypatch) -> None:
    _use_tmp_repo_root(tmp_path, monkeypatch)
    _patch_pipeline(monkeypatch)
    run = _untrusted_run()
    fake = _OrchestrationRunner()

    assert execute(run, command_runner=fake) == 0

    assert run.output(".status.json").read_text(encoding="utf-8") == COMPLETE_STATUS_JSON
    assert not run.output(".base-status.json").exists()
    meta = json.loads(run.output(".meta.json").read_text(encoding="utf-8"))
    assert meta["meta_version"] == 2
    assert meta["review_mode"] == "inspection-only-ci-evidence"
    assert meta["trusted"] is False
    assert json.loads(run.output(".ci-evidence.json").read_text(encoding="utf-8")) == DEFAULT_CI_EVIDENCE
    provenance = json.loads(run.output(".grader-provenance.json").read_text(encoding="utf-8"))
    assert provenance["established"] is True
    boundary = json.loads(run.output(".boundary.json").read_text(encoding="utf-8"))
    assert boundary["verdict"] == "verified"
    assert any(call[:3] == ["gh", "pr", "view"] for call in fake.calls)


def test_execute_untrusted_oversize_input_stops_before_provenance(tmp_path, monkeypatch) -> None:
    _use_tmp_repo_root(tmp_path, monkeypatch)
    stats = dict(DEFAULT_INPUT_STATS)
    stats["oversize"] = True
    _patch_pipeline(monkeypatch, input_stats=stats)

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("must not be called once the input is oversize")

    monkeypatch.setattr(runner, "establish_trusted_main", _forbidden)
    monkeypatch.setattr(runner, "verify_isolation_boundary", _forbidden)
    monkeypatch.setattr(runner, "run_untrusted_codex", _forbidden)
    run = _untrusted_run()
    fake = _OrchestrationRunner()

    assert execute(run, command_runner=fake) == 3

    status = json.loads(run.output(".status.json").read_text(encoding="utf-8"))
    assert status["status"] == "incomplete"
    assert any("exceeds MAX_INSPECTION_INPUT_BYTES" in reason for reason in status["reasons"])
    assert not run.output(".grader-provenance.json").exists()
    assert not run.output(".boundary.json").exists()


def test_malicious_base_end_to_end(tmp_path, monkeypatch) -> None:
    """establish_trusted_main's B13 rejection stops the run before any grader materializes or Codex launches."""
    _use_tmp_repo_root(tmp_path, monkeypatch)
    _patch_pipeline(
        monkeypatch,
        provenance_error=f"base grader provenance not established: {B[:12]} is not an ancestor of origin/main",
    )

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("must not be reached once grader provenance fails")

    monkeypatch.setattr(runner, "verify_isolation_boundary", _forbidden)
    monkeypatch.setattr(runner, "run_untrusted_codex", _forbidden)
    run = _untrusted_run()
    fake = _OrchestrationRunner()

    assert execute(run, command_runner=fake) == 3

    provenance = json.loads(run.output(".grader-provenance.json").read_text(encoding="utf-8"))
    assert provenance["established"] is False
    assert "is not an ancestor of origin/main" in provenance["reasons"][0]
    status = json.loads(run.output(".status.json").read_text(encoding="utf-8"))
    assert "base grader provenance not established" in status["reasons"][0]
    for call in fake.calls:
        joined = " ".join(str(part) for part in call)
        assert "git show" not in joined
        assert call[0] != sys.executable


def test_boundary_not_verified_stops_before_launch(tmp_path, monkeypatch, capsys) -> None:
    _use_tmp_repo_root(tmp_path, monkeypatch)
    _patch_pipeline(monkeypatch, boundary=dict(DEFAULT_BOUNDARY_UNVERIFIED))

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("run_untrusted_codex must not be called when the boundary is not verified")

    monkeypatch.setattr(runner, "run_untrusted_codex", _forbidden)
    run = _untrusted_run()
    fake = _OrchestrationRunner()

    assert execute(run, command_runner=fake) == 3

    boundary = json.loads(run.output(".boundary.json").read_text(encoding="utf-8"))
    assert boundary["verdict"] == "unverified"
    status = json.loads(run.output(".status.json").read_text(encoding="utf-8"))
    assert any("isolation boundary not verified" in reason for reason in status["reasons"])
    assert any("Codex was not run on the untrusted head" in reason for reason in status["reasons"])
    out = capsys.readouterr().out
    assert f"Codex INCOMPLETE for {H[:12]}" in out
    assert "Ask the owner to decide" in out
    assert "do not record this run as clean" in out
    for call in fake.calls:
        assert call[0] != "codex"
        assert call[:2] != ["docker", "start"]


def test_untrusted_codex_launch_failure_is_incomplete(tmp_path, monkeypatch) -> None:
    _use_tmp_repo_root(tmp_path, monkeypatch)
    _patch_pipeline(
        monkeypatch,
        boundary=dict(DEFAULT_BOUNDARY_VERIFIED),
        codex_error="untrusted Codex launch requires a verified container boundary",
    )
    run = _untrusted_run()
    fake = _OrchestrationRunner()

    assert execute(run, command_runner=fake) == 3

    status = json.loads(run.output(".status.json").read_text(encoding="utf-8"))
    assert any(
        "untrusted Codex launch failed: untrusted Codex launch requires a verified container boundary" in reason
        for reason in status["reasons"]
    )


def test_untrusted_codex_refreshed_sign_in_is_incomplete_without_grading(tmp_path, monkeypatch) -> None:
    _use_tmp_repo_root(tmp_path, monkeypatch)
    _patch_pipeline(
        monkeypatch,
        boundary=dict(DEFAULT_BOUNDARY_VERIFIED),
        codex_result=(0, ["Codex refreshed its sign-in during the run; re-login needed"]),
    )
    run = _untrusted_run()
    fake = _OrchestrationRunner()

    assert execute(run, command_runner=fake) == 3

    status = json.loads(run.output(".status.json").read_text(encoding="utf-8"))
    assert any("refreshed its sign-in" in reason for reason in status["reasons"])
    assert not any(call[0] == sys.executable and "codex_report_status.py" in str(call[1]) for call in fake.calls)


def test_event_audit_finds_tool_use_even_if_checker_would_say_complete(tmp_path, monkeypatch) -> None:
    _use_tmp_repo_root(tmp_path, monkeypatch)
    _patch_pipeline(monkeypatch, boundary=dict(DEFAULT_BOUNDARY_VERIFIED), codex_events=TOOL_USE_EVENTS)
    run = _untrusted_run()
    fake = _OrchestrationRunner()  # would answer the checker with COMPLETE_STATUS_JSON if ever asked

    assert execute(run, command_runner=fake) == 3

    status = json.loads(run.output(".status.json").read_text(encoding="utf-8"))
    assert any("inspection-only review used a tool: command_execution" in reason for reason in status["reasons"])
    assert not any(call[0] == sys.executable and "codex_report_status.py" in str(call[1]) for call in fake.calls)


def test_older_main_checker_stops_before_boundary_check(tmp_path, monkeypatch) -> None:
    _use_tmp_repo_root(tmp_path, monkeypatch)
    _patch_pipeline(monkeypatch, grader_supports_mode=False)
    run = _untrusted_run()

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("must not be reached once the trusted-main checker predates --review-mode")

    monkeypatch.setattr(runner, "verify_isolation_boundary", _forbidden)
    monkeypatch.setattr(runner, "run_untrusted_codex", _forbidden)
    fake = _OrchestrationRunner(changed_paths="tests/codex_review_run.py\n")

    assert execute(run, command_runner=fake) == 3

    status = json.loads(run.output(".status.json").read_text(encoding="utf-8"))
    assert any(
        f"trusted-main checker at {M[:12]} predates --review-mode inspection-only" in reason
        for reason in status["reasons"]
    )


def test_cross_grade_base_checker_incomplete_blocks_even_if_head_is_complete(tmp_path, monkeypatch) -> None:
    _use_tmp_repo_root(tmp_path, monkeypatch)
    _patch_pipeline(monkeypatch, boundary=dict(DEFAULT_BOUNDARY_VERIFIED), patch_materialize_grader=False)
    run = _untrusted_run()
    fake = _OrchestrationRunner(
        changed_paths="tests/codex_review_run.py\n",
        checker_stdout=COMPLETE_STATUS_JSON,
        checker_returncode=0,
        base_checker_stdout=INCOMPLETE_STATUS_JSON,
        base_checker_returncode=1,
        git_show_files={
            "tests/codex_report_status.py": "# materialized from main\n",
            ".claude/schemas/codex-review-findings.schema.json": "{}",
        },
    )

    assert execute(run, command_runner=fake) == 3

    assert run.output(".status.json").read_text(encoding="utf-8") == COMPLETE_STATUS_JSON
    assert run.output(".base-status.json").read_text(encoding="utf-8") == INCOMPLETE_STATUS_JSON
    for call in fake.calls:
        joined = " ".join(str(part) for part in call)
        assert f"git show {B}:" not in joined
    show_refs = {call[2].split(":")[0] for call in fake.calls if call[:2] == ["git", "show"]}
    assert show_refs == {M}


def test_cross_grade_both_checkers_complete_is_complete(tmp_path, monkeypatch) -> None:
    _use_tmp_repo_root(tmp_path, monkeypatch)
    _patch_pipeline(monkeypatch, boundary=dict(DEFAULT_BOUNDARY_VERIFIED), patch_materialize_grader=False)
    run = _untrusted_run()
    fake = _OrchestrationRunner(
        changed_paths="tests/codex_review_run.py\n",
        checker_stdout=COMPLETE_STATUS_JSON,
        checker_returncode=0,
        base_checker_stdout=COMPLETE_STATUS_JSON,
        base_checker_returncode=0,
        git_show_files={
            "tests/codex_report_status.py": "# materialized from main\n",
            ".claude/schemas/codex-review-findings.schema.json": "{}",
        },
    )

    assert execute(run, command_runner=fake) == 0

    head_argv = next(c for c in fake.calls if c[0] == sys.executable and "codex-base-grader" not in str(c[1]))
    base_argv = next(c for c in fake.calls if c[0] == sys.executable and "codex-base-grader" in str(c[1]))
    assert "--review-mode" in head_argv and "inspection-only" in head_argv
    assert "--review-mode" in base_argv and "inspection-only" in base_argv


def test_execute_untrusted_refuses_when_output_already_exists(tmp_path, monkeypatch) -> None:
    _use_tmp_repo_root(tmp_path, monkeypatch)
    _patch_pipeline(monkeypatch)
    run = _untrusted_run()
    run.out_base.parent.mkdir(parents=True)
    run.output(".status.json").write_text("recorded")
    fake = _OrchestrationRunner()

    with pytest.raises(FileExistsError, match="already exist"):
        execute(run, command_runner=fake)

    assert not run.output(".meta.json").exists()
    assert run.output(".status.json").read_text() == "recorded"


def test_execute_untrusted_runner_error_before_reservation_writes_nothing(tmp_path, monkeypatch) -> None:
    _use_tmp_repo_root(tmp_path, monkeypatch)

    def _raise(run, command_runner):
        raise RunnerError("PR is not open: PR #91 state is CLOSED")

    monkeypatch.setattr(runner, "inspect_untrusted_pr", _raise)
    run = _untrusted_run()
    fake = _OrchestrationRunner()

    with pytest.raises(RunnerError, match="PR is not open"):
        execute(run, command_runner=fake)

    assert not run.output(".meta.json").exists()
    assert not run.output(".status.json").exists()


def test_inspection_meta_shape() -> None:
    run = _untrusted_run()
    meta = inspection_meta(
        run,
        harness_head=M,
        inputs={"docs/codex-adversarial-review-contract.md": {"sha256": "x", "committed_unchanged": True}},
        audited_inputs_changed_in_diff=[],
        input_stats=dict(DEFAULT_INPUT_STATS),
    )

    assert meta["meta_version"] == 2
    assert meta["head"] == H
    assert meta["base"] == B
    assert meta["label"] == run.label
    assert meta["attempt"] == run.attempt
    assert meta["pr_url"] == run.pr_url
    assert meta["trusted"] is False
    assert meta["review_mode"] == "inspection-only-ci-evidence"
    assert meta["inspection_template_version"] == "1"
    assert meta["harness_head"] == M
    assert meta["test_evidence_source"] == "GitHub CI check runs"
    assert meta["audited_inputs_changed_in_diff"] == []
    assert meta["base_grader_source"] == "trusted-origin-main"
    assert meta["inspection_input"] == {
        "bytes": DEFAULT_INPUT_STATS["bytes"],
        "files_included": 1,
        "files_omitted": 0,
    }


def test_output_suffixes_gained_the_three_new_outputs() -> None:
    assert ".ci-evidence.json" in runner.OUTPUT_SUFFIXES
    assert ".grader-provenance.json" in runner.OUTPUT_SUFFIXES
    assert ".boundary.json" in runner.OUTPUT_SUFFIXES


def test_write_json_atomic_round_trips(tmp_path) -> None:
    path = tmp_path / "out.json"
    runner._write_json_atomic(path, {"a": 1, "b": [1, 2, 3]})
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1, "b": [1, 2, 3]}
    assert list(tmp_path.iterdir()) == [path]  # no leftover temp file
