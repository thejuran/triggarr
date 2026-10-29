"""Tests for the untrusted-head inspection-only review input and provenance.

Covers tests/codex_review_run.py's inspection-only building blocks (Phase
85.1, D-07): PR/CI preconditions (inspect_untrusted_pr, ci_evidence,
flatten_pages), the inert inspection input built purely from git objects
(build_inspection_input), the inspection-only prompt (new_input_fence,
render_inspection_prompt), and trusted-main grader provenance
(establish_trusted_main, trusted_main_grader_supports_mode). No
orchestration is exercised here -- Plan 85.1-06 wires these into execute().
Every git/gh/Python command is answered by a scripted command runner; no
real subprocess, checkout, or Codex call is ever made.
"""

from __future__ import annotations

import json
import subprocess
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
    ReviewRun,
    RunnerError,
    build_inspection_input,
    ci_evidence,
    flatten_pages,
    inspect_untrusted_pr,
    new_input_fence,
    render_inspection_prompt,
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
    begin = prompt.index(f"{fence}-BEGIN")
    end = prompt.index(f"{fence}-END")
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
