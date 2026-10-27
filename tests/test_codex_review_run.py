"""Tests for tests/codex_review_run.py, the reproducible Codex review runner.

Durable Codex completeness (owner 2026-10-22). Only the pure parts are
exercised here -- prompt rendering, the scope pathspec, output naming,
argument construction and dry-run -- plus the orchestration with a fake
command runner. Codex itself is never called.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests import codex_review_run as runner
from tests.codex_review_run import (
    EXCLUDE_PATHSPECS,
    REPO_ROOT,
    SCHEMA_PATH,
    ReviewRun,
    checker_argv,
    codex_argv,
    diff_argv,
    execute,
    load_template,
    main,
    pytest_argv,
    render_prompt,
    worktree_add_argv,
    worktree_remove_argv,
)

H = "a" * 40
B = "b" * 40
PHASE_DIR = Path(".planning/phases/83-paired-bm-codex-review-risk-based-depth")


def _run(**overrides) -> ReviewRun:
    values = {
        "head": H,
        "base": B,
        "label": "explicit",
        "attempt": 2,
        "pr_url": "none (local checkpoint, not pushed)",
        "scope": "Phase 83 changes",
        "phase_dir": PHASE_DIR,
        "trusted": True,
    }
    values.update(overrides)
    return ReviewRun(**values)


def _values(**overrides) -> dict[str, str]:
    values = {
        "PR_URL": "https://github.com/thejuran/triggarr/pull/34",
        "HEAD_SHA": H,
        "BASE_SHA": B,
        "SCOPE": "Phase 83 changes",
        "TEST_EVIDENCE": "/repo/out.pytest.txt",
    }
    values.update(overrides)
    return values


# --- Template and rendering -------------------------------------------------


def test_template_is_the_contract_version_five_prompt() -> None:
    assert runner.TEMPLATE_HEADING == "## Fixed prompt (version 5)"
    assert runner.template_version() == "5"
    template = load_template()
    assert template.startswith("Independently review {{PR_URL}}")
    assert "{{TEST_EVIDENCE}}" in template


def test_render_substitutes_every_placeholder() -> None:
    prompt = render_prompt(load_template(), _values())
    assert "{{" not in prompt
    assert H in prompt and B in prompt
    assert "/repo/out.pytest.txt" in prompt
    assert "https://github.com/thejuran/triggarr/pull/34" in prompt


def test_render_adds_no_other_text() -> None:
    template = load_template()
    prompt = render_prompt(template, _values())
    rebuilt = template
    for key, value in _values().items():
        rebuilt = rebuilt.replace("{{" + key + "}}", value)
    assert prompt == rebuilt


def test_render_is_single_pass() -> None:
    """A value that looks like a placeholder is never expanded again."""
    prompt = render_prompt(load_template(), _values(SCOPE="see {{HEAD_SHA}}"))
    assert "Scope: see {{HEAD_SHA}}." in prompt


def test_render_rejects_missing_value() -> None:
    values = _values()
    del values["TEST_EVIDENCE"]
    with pytest.raises(ValueError, match="TEST_EVIDENCE"):
        render_prompt(load_template(), values)


def test_render_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="EXTRA"):
        render_prompt(load_template(), _values(EXTRA="framing"))


# --- Scope pathspec ----------------------------------------------------------


def test_pathspecs_match_the_prompt() -> None:
    template = load_template()
    for pathspec in EXCLUDE_PATHSPECS:
        assert f"'{pathspec}'" in template


def test_diff_argv_uses_pathspecs() -> None:
    assert diff_argv(B, H) == ["git", "diff", f"{B}..{H}", "--", ".", *EXCLUDE_PATHSPECS]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


# bm:dbe1b7f56bdd:WR-01 (owner-approved round 3, template version 5): planning
# markdown, raw transcripts and generated review artifacts stay out of the
# review diff, but .planning/config.json and any other non-markdown,
# non-codex file under .planning/ stays in it.


def test_exclude_pathspecs_are_narrow() -> None:
    assert EXCLUDE_PATHSPECS == (
        ":(exclude,glob).planning/**/codex/**",
        ":(exclude,glob).planning/**/*.jsonl",
        ":(exclude,glob).planning/**/*.md",
    )


def _policy_sensitive_planning_paths() -> list[str]:
    policy = (REPO_ROOT / "docs" / "review-classification-policy.md").read_text(encoding="utf-8")
    row = next(line for line in policy.splitlines() if line.startswith("| sensitive |"))
    return sorted(set(re.findall(r"`(\.planning/[^`*]+)`", row)))


def test_policy_names_planning_config_as_sensitive() -> None:
    assert ".planning/config.json" in _policy_sensitive_planning_paths()


def test_pathspecs_keep_planning_config_and_drop_planning_docs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("base\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD").strip()

    kept = {
        "triggarr/app.py",
        ".planning/config.json",
        ".planning/phases/83-x/83-config-before.json",
        *_policy_sensitive_planning_paths(),
    }
    dropped = {
        ".planning/STATE.md",
        ".planning/phases/83-x/83-REVIEW.md",
        ".planning/quick/261022-x/261022-x-PLAN.md",
        ".planning/phases/83-x/codex/abc-explicit-a1.last.json",
        ".planning/phases/83-x/codex/abc-explicit-a1.pytest.txt",
        ".planning/phases/83-x/codex/abc-explicit-a1.meta.json",
        ".planning/codex/top-level.json",
        ".planning/quick/run.jsonl",
    }
    for name in kept | dropped:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n")
        _git(repo, "add", "-f", name)
    _git(repo, "commit", "-q", "-m", "change")
    head = _git(repo, "rev-parse", "HEAD").strip()

    argv = diff_argv(base, head)
    changed = set(_git(repo, argv[1], "--name-only", *argv[2:]).split())
    assert changed == kept


# --- Output naming -----------------------------------------------------------


def test_output_base_naming() -> None:
    run = _run()
    assert run.out_base == REPO_ROOT / PHASE_DIR / "codex" / f"{H[:12]}-explicit-a2"


@pytest.mark.parametrize(
    "suffix", [".jsonl", ".last.json", ".status.json", ".pytest.txt", ".prompt.txt", ".meta.json"]
)
def test_output_paths_sit_next_to_each_other(suffix: str) -> None:
    run = _run()
    assert run.output(suffix) == run.out_base.parent / f"{run.out_base.name}{suffix}"


@pytest.mark.parametrize("label", ["", "../x", "A", "has space", "-lead", "a/b"])
def test_label_rejected(label: str) -> None:
    with pytest.raises(ValueError, match="label"):
        _run(label=label)


@pytest.mark.parametrize("phase_dir", ["docs", ".planning", "../elsewhere", "/tmp/x"])
def test_phase_dir_must_be_under_planning_phases(phase_dir: str) -> None:
    with pytest.raises(ValueError, match="phase-dir"):
        _run(phase_dir=Path(phase_dir))


@pytest.mark.parametrize("field", ["head", "base"])
def test_sha_fields_must_be_full_sha(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        _run(**{field: "abc123"})


def test_attempt_must_be_positive() -> None:
    with pytest.raises(ValueError, match="attempt"):
        _run(attempt=0)


# --- Argument construction ---------------------------------------------------


def test_worktree_argv() -> None:
    wt = Path("/tmp/codex-review-x/wt")
    assert worktree_add_argv(wt, H) == ["git", "worktree", "add", "--detach", str(wt), H]
    assert worktree_remove_argv(wt) == ["git", "worktree", "remove", "--force", str(wt)]


def test_pytest_argv() -> None:
    assert pytest_argv() == ["uv", "run", "--extra", "dev", "pytest", "tests/", "-q"]


def test_codex_argv_is_read_only_and_schema_bound() -> None:
    wt = Path("/tmp/codex-review-x/wt")
    last = Path("/repo/out.last.json")
    assert codex_argv(wt, last) == [
        "codex",
        "exec",
        "--sandbox",
        "read-only",
        "--ephemeral",
        "-C",
        str(wt),
        "--output-schema",
        str(SCHEMA_PATH),
        "--json",
        "-o",
        str(last),
        "-",
    ]


def test_checker_argv() -> None:
    run = _run()
    argv = checker_argv(run, exit_code=0, current_head=H)
    assert argv[1:] == [
        str(REPO_ROOT / "tests" / "codex_report_status.py"),
        "--report",
        str(run.output(".last.json")),
        "--exit-code",
        "0",
        "--expected-head",
        H,
        "--expected-base",
        B,
        "--current-head",
        H,
        "--attempt",
        "2",
    ]


def test_checker_argv_never_requests_the_legacy_v1_path(tmp_path, monkeypatch) -> None:
    """bm:49ded1e86444:WR-01: a new run's v1-labelled report is assessed incomplete."""
    import json

    from tests import codex_report_status

    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    (tmp_path / PHASE_DIR).mkdir(parents=True)
    run = _run(attempt=1)
    report = {
        "schema_version": "1",
        "inspected_head_sha": H,
        "inspected_base_sha": B,
        "pr_url": "none (local checkpoint, not pushed)",
        "scope": "Phase 83 changes",
        "verdict": "no-findings",
        "summary": "Only read two files; could not finish.",
        "coverage": ["two files"],
        "exclusions": [],
        "commands_run": [{"command": "git diff", "exit_code": 0, "purpose": "read diff"}],
        "findings": [],
        "limitations": ["ran out of time before covering most files"],
    }
    run.out_base.parent.mkdir(parents=True)
    run.output(".last.json").write_text(json.dumps(report), encoding="utf-8")

    argv = checker_argv(run, exit_code=0, current_head=H)
    assert "--legacy-v1" not in argv
    assert codex_report_status.main(argv[2:]) == 1


def test_checker_argv_omits_unknown_exit_code() -> None:
    argv = checker_argv(_run(), exit_code=None, current_head=H)
    assert "--exit-code" not in argv


# --- Dry run -----------------------------------------------------------------


def _cli(phase_dir: Path, *extra: str) -> list[str]:
    return [
        "--head",
        H,
        "--base",
        B,
        "--label",
        "explicit",
        "--attempt",
        "1",
        "--pr-url",
        "none (local checkpoint, not pushed)",
        "--scope",
        "Phase 83 changes",
        "--phase-dir",
        str(phase_dir),
        *extra,
    ]


def test_dry_run_prints_prompt_and_commands_without_running(monkeypatch, capsys) -> None:
    def _forbidden(*_args, **_kwargs):
        raise AssertionError("dry run must not run any command")

    monkeypatch.setattr(runner.subprocess, "run", _forbidden)
    monkeypatch.setattr(runner.tempfile, "mkdtemp", _forbidden)

    run = ReviewRun(H, B, "explicit", 1, "none (local checkpoint, not pushed)", "Phase 83 changes", PHASE_DIR, True)
    before = {suffix: run.output(suffix).exists() for suffix in runner.OUTPUT_SUFFIXES}

    assert main(_cli(PHASE_DIR, "--dry-run", "--trusted")) == 0
    out = capsys.readouterr().out

    assert "Independently review none (local checkpoint, not pushed)" in out
    assert str(run.output(".pytest.txt")) in out
    assert "{{" not in out
    assert "git worktree add --detach" in out
    assert "uv run --extra dev pytest tests/ -q" in out
    assert "codex exec --sandbox read-only --ephemeral" in out
    assert "git worktree remove --force" in out
    assert "tests/codex_report_status.py" in out
    # The evidence copy lands in the worktree before Codex starts.
    assert out.index("# copy ") < out.index("codex exec --sandbox")
    assert {suffix: run.output(suffix).exists() for suffix in runner.OUTPUT_SUFFIXES} == before


def test_cli_rejects_short_sha() -> None:
    argv = _cli(PHASE_DIR, "--dry-run", "--trusted")
    argv[1] = "abc"
    with pytest.raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2


# --- Orchestration with a fake command runner -------------------------------


def _is_checker(argv) -> bool:
    """The checker invocation (not the audited-input `git status`, which also names the file)."""
    return any(str(part).endswith("codex_report_status.py") for part in argv) and "--report" in argv


class FakeRunner:
    """Records every command; fails the one whose program matches *fail_on*."""

    def __init__(self, fail_on: str | None = None, codex_exit: int = 0, dirty: str = "") -> None:
        self.calls: list[list[str]] = []
        self.fail_on = fail_on
        self.codex_exit = codex_exit
        self.dirty = dirty

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        program = argv[2] if argv[0] == "timeout" else argv[0]
        if self.fail_on and self.fail_on in (program, " ".join(argv[:3])):
            raise OSError("simulated failure")
        if argv[:3] == ["git", "worktree", "add"]:
            Path(argv[4]).mkdir(parents=True)
            return subprocess.CompletedProcess(argv, 0)
        if argv[:2] == ["git", "status"]:
            return subprocess.CompletedProcess(argv, 0, stdout=self.dirty)
        if argv[:2] == ["git", "rev-parse"]:
            return subprocess.CompletedProcess(argv, 0, stdout=H + "\n")
        if argv[0] == "uv":
            return subprocess.CompletedProcess(argv, 1, stdout="1 failed, 9 passed\n")
        if program == "codex":
            assert kwargs["input"].startswith("Independently review")
            kwargs["stdout"].write('{"type":"done"}\n')
            return subprocess.CompletedProcess(argv, self.codex_exit)
        if _is_checker(argv):
            return subprocess.CompletedProcess(argv, 1, stdout='{"status": "incomplete"}\n')
        return subprocess.CompletedProcess(argv, 0)


def _tmp_run(tmp_path: Path, monkeypatch) -> ReviewRun:
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    (tmp_path / PHASE_DIR).mkdir(parents=True)
    monkeypatch.setattr(runner.tempfile, "mkdtemp", lambda prefix: str(tmp_path / "scratch"))
    (tmp_path / "scratch").mkdir()
    return _run(attempt=1)


def _removed(fake: FakeRunner) -> bool:
    return any(call[:4] == ["git", "worktree", "remove", "--force"] for call in fake.calls)


def test_execute_writes_all_outputs_and_removes_worktree(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner()

    assert execute(run, command_runner=fake) == 1

    evidence = run.output(".pytest.txt").read_text()
    assert f"head: {H}" in evidence
    assert "command: uv run --extra dev pytest tests/ -q" in evidence
    assert "exit_code: 1" in evidence
    assert "1 failed, 9 passed" in evidence
    assert run.output(".jsonl").read_text() == '{"type":"done"}\n'
    assert run.output(".status.json").read_text() == '{"status": "incomplete"}\n'
    assert _removed(fake)
    assert not (tmp_path / "scratch").exists()

    order = [" ".join(call[:3]) for call in fake.calls]
    assert order.index("git worktree add") < order.index("uv run --extra")
    assert order.index("uv run --extra") < order.index("codex exec --sandbox")
    assert order.index("codex exec --sandbox") < order.index("git worktree remove")


def test_execute_runs_pytest_in_the_worktree(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    seen: dict[str, object] = {}
    fake = FakeRunner()

    def _spy(argv, **kwargs):
        if argv[0] == "uv":
            seen["cwd"] = kwargs.get("cwd")
            seen["env_has_virtual_env"] = "VIRTUAL_ENV" in (kwargs.get("env") or {})
        return fake(argv, **kwargs)

    monkeypatch.setenv("VIRTUAL_ENV", "/elsewhere/.venv")
    execute(run, command_runner=_spy)
    assert seen["cwd"] == tmp_path / "scratch" / "wt"
    assert seen["env_has_virtual_env"] is False


def test_execute_removes_worktree_when_codex_fails(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner(fail_on="codex")

    assert execute(run, command_runner=fake) == 1
    assert _removed(fake)
    assert not (tmp_path / "scratch").exists()
    checker = next(call for call in fake.calls if _is_checker(call))
    assert "--exit-code" not in checker


def test_execute_removes_worktree_when_pytest_cannot_start(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner(fail_on="uv")

    execute(run, command_runner=fake)
    assert _removed(fake)
    assert "exit_code: unknown" in run.output(".pytest.txt").read_text()


def test_execute_refuses_to_overwrite_recorded_output(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    run.output(".last.json").parent.mkdir(parents=True)
    run.output(".last.json").write_text("recorded")
    fake = FakeRunner()

    with pytest.raises(FileExistsError):
        execute(run, command_runner=fake)
    assert fake.calls == []
    assert run.output(".last.json").read_text() == "recorded"


# --- Source trust (owner decision 2026-10-22, owner-approved round 2) --------
# Harness pytest runs only for this repository's own branches. Dependabot and
# outside-contributor heads use --untrusted: no tests run, CI results count.


def test_review_run_requires_explicit_trust() -> None:
    with pytest.raises(TypeError):
        ReviewRun(H, B, "explicit", 1, "none", "scope", PHASE_DIR)  # type: ignore[call-arg]


@pytest.mark.parametrize("flags", [(), ("--trusted", "--untrusted")])
def test_cli_requires_exactly_one_trust_flag(flags: tuple) -> None:
    argv = _cli(PHASE_DIR, "--dry-run", *flags)
    with pytest.raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2


# Owner decision 2026-10-22 (owner-approved round 3, resolves
# bm:dbe1b7f56bdd:CR-01 = codex:dbe1b7f56bdd:a1:F001 and bm:dbe1b7f56bdd:WR-02):
# Codex is not run for untrusted heads at all until the harness is hardened.
# The record shows "Codex: PENDING — untrusted source" and CI results are used.


def _forbid_everything(monkeypatch) -> None:
    def _forbidden(*_args, **_kwargs):
        raise AssertionError("an untrusted run must not run any command or create any directory")

    monkeypatch.setattr(runner.subprocess, "run", _forbidden)
    monkeypatch.setattr(runner.tempfile, "mkdtemp", _forbidden)


@pytest.mark.parametrize("extra", [(), ("--dry-run",)])
def test_main_refuses_untrusted_and_writes_nothing(monkeypatch, capsys, extra: tuple) -> None:
    _forbid_everything(monkeypatch)
    run = _run(attempt=1, trusted=False)
    before = {suffix: run.output(suffix).exists() for suffix in runner.OUTPUT_SUFFIXES}

    assert main([*_cli(PHASE_DIR, "--untrusted"), *extra]) == 2

    out = capsys.readouterr().out
    assert "Codex: PENDING — untrusted source" in out
    assert "CI results" in out
    for choice in ("wait", "retry later", "fallback"):
        assert choice in out
    assert {suffix: run.output(suffix).exists() for suffix in runner.OUTPUT_SUFFIXES} == before


def test_execute_refuses_untrusted_before_any_work(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    (tmp_path / PHASE_DIR).mkdir(parents=True)
    run = _run(attempt=1, trusted=False)
    fake = FakeRunner()

    with pytest.raises(runner.RunnerError, match="PENDING"):
        execute(run, command_runner=fake)
    assert fake.calls == []
    assert not (tmp_path / PHASE_DIR / "codex").exists()


def test_cli_still_requires_an_explicit_trusted_flag() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(_cli(PHASE_DIR, "--dry-run"))
    assert exc_info.value.code == 2


def test_contract_documents_untrusted_sources() -> None:
    text = runner.CONTRACT_PATH.read_text(encoding="utf-8")
    assert "--untrusted" in text and "--trusted" in text
    assert "Dependabot" in text
    assert "Codex: PENDING — untrusted source" in text
    assert "Phase 85" in text
    assert "CI results" in text


def test_record_documents_untrusted_pending() -> None:
    record = (REPO_ROOT / "docs" / "review-checkpoint-record.md").read_text(encoding="utf-8")
    assert "Codex: PENDING — untrusted source" in record


def test_prompt_covers_untrusted_evidence() -> None:
    assert "untrusted source" in load_template()


# --- Privacy (bm:322afc50367d:IN-07, owner-approved round 2) ------------------
# No prompt or harness evidence path or text contains the operator's home
# directory: the evidence is copied into the temp worktree and referenced by
# a working-copy-relative path.


def test_prompt_evidence_path_is_relative_to_the_working_copy() -> None:
    value = runner.prompt_values(_run())["TEST_EVIDENCE"]
    assert value == runner.EVIDENCE_RELPATH
    assert not Path(value).is_absolute()
    assert str(Path.home()) not in value


def test_prompt_reads_stay_inside_the_working_copy() -> None:
    template = load_template()
    assert "Read only files inside this working copy; do not read any file outside it." in template
    assert "plus {{TEST_EVIDENCE}}" not in template


def test_execute_copies_evidence_into_worktree_and_strips_home(tmp_path, monkeypatch) -> None:
    home = "/Users/someone-private"
    monkeypatch.setenv("HOME", home)
    run = _tmp_run(tmp_path, monkeypatch)
    worktree = tmp_path / "scratch" / "wt"
    seen: dict[str, str] = {}
    fake = FakeRunner()

    def _spy(argv, **kwargs):
        if argv[0] == "uv":
            out = f"{worktree}/tests/test_x.py:1: warning\n{home}/.cache/uv/thing\n2 passed\n"
            return subprocess.CompletedProcess(argv, 0, stdout=out)
        if "codex" in argv and "exec" in argv:
            seen["prompt"] = kwargs["input"]
            seen["copy"] = (worktree / runner.EVIDENCE_RELPATH).read_text()
        return fake(argv, **kwargs)

    execute(run, command_runner=_spy)

    evidence = run.output(".pytest.txt").read_text()
    assert seen["copy"] == evidence
    for text in (evidence, seen["prompt"]):
        assert home not in text
        assert str(tmp_path) not in text
    assert "~/.cache/uv/thing" in evidence
    assert "<worktree>/tests/test_x.py" in evidence


# --- Audit trail (bm:322afc50367d:WR-02, owner-approved round 2) --------------
# Each run saves the exact prompt and a provenance record, and refuses to run
# when the contract, schema, checker or runner has uncommitted changes.


def test_output_suffixes_include_prompt_and_meta() -> None:
    assert ".prompt.txt" in runner.OUTPUT_SUFFIXES
    assert ".meta.json" in runner.OUTPUT_SUFFIXES


def test_execute_saves_the_exact_prompt(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    sent: dict[str, str] = {}
    fake = FakeRunner()

    def _spy(argv, **kwargs):
        if "codex" in argv and "exec" in argv:
            sent["prompt"] = kwargs["input"]
        return fake(argv, **kwargs)

    execute(run, command_runner=_spy)
    assert run.output(".prompt.txt").read_text(encoding="utf-8") == sent["prompt"]


def test_execute_records_provenance(tmp_path, monkeypatch) -> None:
    import hashlib
    import json as _json

    run = _tmp_run(tmp_path, monkeypatch)
    execute(run, command_runner=FakeRunner())

    meta = _json.loads(run.output(".meta.json").read_text(encoding="utf-8"))
    assert meta["template_version"] == "5"
    assert meta["head"] == H and meta["base"] == B
    assert meta["harness_head"] == H
    assert meta["trusted"] is True
    assert set(meta["inputs"]) == {
        "docs/codex-adversarial-review-contract.md",
        ".claude/schemas/codex-review-findings.schema.json",
        "tests/codex_report_status.py",
        "tests/codex_review_run.py",
    }
    for relpath, entry in meta["inputs"].items():
        digest = hashlib.sha256((runner.HARNESS_ROOT / relpath).read_bytes()).hexdigest()
        assert entry == {"sha256": digest, "committed_unchanged": True}


def test_execute_refuses_when_inputs_have_uncommitted_changes(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner(dirty=" M docs/codex-adversarial-review-contract.md\n")

    with pytest.raises(runner.RunnerError, match="uncommitted changes"):
        execute(run, command_runner=fake)
    assert not any(call[:3] == ["git", "worktree", "add"] for call in fake.calls)
    assert not any(run.output(suffix).exists() for suffix in runner.OUTPUT_SUFFIXES)


def test_dirty_check_covers_every_audited_input(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner()
    execute(run, command_runner=fake)
    status = next(call for call in fake.calls if call[:2] == ["git", "status"])
    for relpath in runner.AUDITED_INPUTS:
        assert relpath in status


def test_main_reports_dirty_inputs_as_error(monkeypatch, capsys) -> None:
    def _dirty(_run, **_kwargs):
        raise runner.RunnerError("audited inputs have uncommitted changes: x")

    monkeypatch.setattr(runner, "execute", _dirty)
    assert main(_cli(PHASE_DIR, "--trusted")) == 2
    assert "error: audited inputs have uncommitted changes" in capsys.readouterr().out


def test_contract_and_record_list_prompt_and_meta_outputs() -> None:
    contract = runner.CONTRACT_PATH.read_text(encoding="utf-8")
    start = contract.index("## Raw output storage")
    storage = contract[start : contract.index("## Failure rule", start)]
    assert "`.prompt.txt`" in storage and "`.meta.json`" in storage
    record = (REPO_ROOT / "docs" / "review-checkpoint-record.md").read_text(encoding="utf-8")
    assert "`.prompt.txt`" in record and "`.meta.json`" in record


# --- Atomic output reservation (codex:322afc50367d:a1:F002, owner-approved round 2)
# Two runs with the same head/label/attempt can both pass the "outputs exist"
# check; only one may win. The reservation creates the first output with
# O_CREAT|O_EXCL before any other work.


def test_second_reservation_fails_without_touching_the_first(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    run.out_base.parent.mkdir(parents=True)

    runner.reserve_outputs(run, "first prompt")
    with pytest.raises(FileExistsError):
        runner.reserve_outputs(run, "second prompt")
    assert run.output(".prompt.txt").read_text(encoding="utf-8") == "first prompt"


def test_execute_loses_a_race_without_touching_files(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    real_audit = runner.audit_inputs

    def _audit_then_other_run_reserves(command_runner):
        result = real_audit(command_runner)
        run.out_base.parent.mkdir(parents=True, exist_ok=True)
        run.output(".prompt.txt").write_text("other run", encoding="utf-8")
        return result

    monkeypatch.setattr(runner, "audit_inputs", _audit_then_other_run_reserves)
    fake = FakeRunner()

    with pytest.raises(FileExistsError):
        execute(run, command_runner=fake)
    assert run.output(".prompt.txt").read_text(encoding="utf-8") == "other run"
    assert not run.output(".meta.json").exists()
    assert not any(call[:3] == ["git", "worktree", "add"] for call in fake.calls)


def test_main_reports_lost_reservation_as_error(monkeypatch, capsys) -> None:
    def _taken(_run, **_kwargs):
        raise FileExistsError("review output already reserved: x.prompt.txt")

    monkeypatch.setattr(runner, "execute", _taken)
    assert main(_cli(PHASE_DIR, "--trusted")) == 2
    assert "use the next attempt number" in capsys.readouterr().out


# --- Robustness (bm:322afc50367d:IN-05, IN-08, IN-04 runner part; round 2) ---


def test_codex_timeout_is_enforced_in_process(tmp_path, monkeypatch) -> None:
    """No external `timeout` binary: subprocess's own timeout, recorded as exit 124."""
    run = _tmp_run(tmp_path, monkeypatch)
    seen: dict[str, object] = {}
    fake = FakeRunner()

    def _spy(argv, **kwargs):
        if argv[:2] == ["codex", "exec"]:
            seen["timeout"] = kwargs.get("timeout")
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        return fake(argv, **kwargs)

    execute(run, command_runner=_spy)
    assert seen["timeout"] == runner.CODEX_TIMEOUT_SECONDS
    checker = next(call for call in fake.calls if _is_checker(call))
    assert checker[checker.index("--exit-code") + 1] == "124"


def test_worktree_add_failure_is_a_clean_error_and_cleans_up(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner()

    def _spy(argv, **kwargs):
        if argv[:3] == ["git", "worktree", "add"]:
            fake.calls.append(list(argv))
            if kwargs.get("check"):
                raise subprocess.CalledProcessError(128, argv)
            return subprocess.CompletedProcess(argv, 128)
        return fake(argv, **kwargs)

    with pytest.raises(runner.RunnerError, match="git worktree add"):
        execute(run, command_runner=_spy)
    assert _removed(fake)
    assert not (tmp_path / "scratch").exists()
    status = run.output(".status.json").read_text(encoding="utf-8")
    assert '"status": "incomplete"' in status
    assert "git worktree add" in status
    assert not any(call[:2] == ["codex", "exec"] for call in fake.calls)


def test_current_head_failure_after_codex_writes_status_stub(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner()
    rev_parses = {"n": 0}

    def _spy(argv, **kwargs):
        if argv[:2] == ["git", "rev-parse"]:
            rev_parses["n"] += 1
            if rev_parses["n"] > 1:
                if kwargs.get("check"):
                    raise subprocess.CalledProcessError(128, argv)
                return subprocess.CompletedProcess(argv, 128, stdout="")
        return fake(argv, **kwargs)

    assert execute(run, command_runner=_spy) == 1
    status = run.output(".status.json").read_text(encoding="utf-8")
    assert '"status": "incomplete"' in status
    assert "current head" in status


def test_empty_checker_output_writes_status_stub(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner()

    def _spy(argv, **kwargs):
        if _is_checker(argv):
            fake.calls.append(list(argv))
            return subprocess.CompletedProcess(argv, 1, stdout="")
        return fake(argv, **kwargs)

    assert execute(run, command_runner=_spy) == 1
    status = run.output(".status.json").read_text(encoding="utf-8")
    assert '"status": "incomplete"' in status
    assert "checker produced no output (exit 1)" in status


def test_main_reports_git_failure_without_traceback(monkeypatch, capsys) -> None:
    def _fails(_run, **_kwargs):
        raise subprocess.CalledProcessError(128, ["git", "worktree", "add"])

    monkeypatch.setattr(runner, "execute", _fails)
    assert main(_cli(PHASE_DIR, "--trusted")) == 2
    assert "error:" in capsys.readouterr().out


# --- Head already stale at launch (bm:322afc50367d:IN-06, round 2) ------------
# A run whose --head is not the checkout's HEAD can only ever be assessed
# stale, so it needs an explicit --allow-stale-head (e.g. finishing an
# earlier head's D-09 retry) instead of silently spending a Codex run.

OTHER = "e" * 40


def _head_is(sha: str, fake: FakeRunner):
    def _spy(argv, **kwargs):
        if argv[:2] == ["git", "rev-parse"]:
            fake.calls.append(list(argv))
            return subprocess.CompletedProcess(argv, 0, stdout=sha + "\n")
        return fake(argv, **kwargs)

    return _spy


def test_execute_refuses_stale_head_without_flag(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner()

    with pytest.raises(runner.RunnerError, match="--allow-stale-head"):
        execute(run, command_runner=_head_is(OTHER, fake))
    assert not any(run.output(suffix).exists() for suffix in runner.OUTPUT_SUFFIXES)
    assert not any(call[:3] == ["git", "worktree", "add"] for call in fake.calls)


def test_execute_allows_stale_head_with_flag_and_records_it(tmp_path, monkeypatch) -> None:
    import json as _json

    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner()

    execute(run, command_runner=_head_is(OTHER, fake), allow_stale_head=True)
    meta = _json.loads(run.output(".meta.json").read_text(encoding="utf-8"))
    assert meta["allow_stale_head"] is True
    assert meta["harness_head"] == OTHER


def test_main_passes_allow_stale_head(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def _capture(_run, **kwargs):
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(runner, "execute", _capture)
    assert main(_cli(PHASE_DIR, "--trusted", "--allow-stale-head")) == 0
    assert seen["allow_stale_head"] is True
    assert main(_cli(PHASE_DIR, "--trusted")) == 0
    assert seen["allow_stale_head"] is False


# --- Evidence copy never follows links (bm:dbe1b7f56bdd:CR-01 =
# codex:dbe1b7f56bdd:a1:F001, owner-approved round 3, defence in depth for
# trusted runs). The reviewed tree decides what exists in the worktree, so the
# harness refuses when the evidence path or its directory already exists, and
# creates the file with O_CREAT|O_EXCL|O_NOFOLLOW.


def _hostile_worktree(kind: str, outside: Path, fake: FakeRunner):
    def _spy(argv, **kwargs):
        result = fake(argv, **kwargs)
        if argv[:3] == ["git", "worktree", "add"]:
            evidence_dir = Path(argv[4]) / ".codex-review-evidence"
            if kind == "symlinked-directory":
                evidence_dir.symlink_to(outside, target_is_directory=True)
            elif kind == "symlinked-file":
                evidence_dir.mkdir()
                (evidence_dir / "pytest.txt").symlink_to(outside / "sentinel.txt")
            elif kind == "dangling-symlinked-file":
                evidence_dir.mkdir()
                (evidence_dir / "pytest.txt").symlink_to(outside / "does-not-exist.txt")
            elif kind == "regular-file":
                evidence_dir.write_text("tracked by the head\n")
        return result

    return _spy


@pytest.mark.parametrize(
    "kind", ["symlinked-directory", "symlinked-file", "dangling-symlinked-file", "regular-file"]
)
def test_evidence_copy_refuses_pre_existing_paths(tmp_path, monkeypatch, kind: str) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel.txt").write_text("precious\n")
    fake = FakeRunner()

    with pytest.raises(runner.RunnerError, match="evidence"):
        execute(run, command_runner=_hostile_worktree(kind, outside, fake))

    assert sorted(p.name for p in outside.iterdir()) == ["sentinel.txt"]
    assert (outside / "sentinel.txt").read_text() == "precious\n"
    status = run.output(".status.json").read_text(encoding="utf-8")
    assert '"status": "incomplete"' in status
    assert "evidence" in status
    assert not any(call[:2] == ["codex", "exec"] for call in fake.calls)
    assert _removed(fake)
    assert not (tmp_path / "scratch").exists()


def test_evidence_copy_is_created_exclusively_without_following_links(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    seen: dict[str, int] = {}
    real_open = runner.os.open

    def _spy_open(path, flags, *args, **kwargs):
        if str(path).endswith(runner.EVIDENCE_RELPATH):
            seen["flags"] = flags
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(runner.os, "open", _spy_open)
    execute(run, command_runner=FakeRunner())

    required = runner.os.O_CREAT | runner.os.O_EXCL | runner.os.O_NOFOLLOW
    assert seen["flags"] & required == required



# --- Remaining round-2 gaps (owner-approved round 3, decision 4) ------------


def test_oserror_after_reservation_writes_status_stub(tmp_path, monkeypatch) -> None:
    """bm:dbe1b7f56bdd:IN-03: an OSError mid-run leaves an incomplete status, not a bare reservation."""
    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner()

    def _codex_cannot_open_events(*_args, **_kwargs):
        raise PermissionError("simulated: cannot open the event stream")

    monkeypatch.setattr(runner, "_run_codex", _codex_cannot_open_events)

    with pytest.raises(runner.RunnerError, match="PermissionError"):
        execute(run, command_runner=fake)
    status = run.output(".status.json").read_text(encoding="utf-8")
    assert '"status": "incomplete"' in status
    assert "PermissionError" in status
    assert _removed(fake)
    assert not (tmp_path / "scratch").exists()


def test_main_reports_oserror_without_next_attempt_advice(monkeypatch, capsys) -> None:
    def _fails(_run, **_kwargs):
        raise runner.RunnerError("harness failed before codex finished: PermissionError")

    monkeypatch.setattr(runner, "execute", _fails)
    assert main(_cli(PHASE_DIR, "--trusted")) == 2
    out = capsys.readouterr().out
    assert "error: harness failed" in out
    assert "next attempt number" not in out


def test_evidence_redacts_pytest_temp_paths_and_username(tmp_path, monkeypatch) -> None:
    """bm:dbe1b7f56bdd:IN-05: pytest's $TMPDIR/pytest-of-<user>/ paths never reach the evidence."""
    run = _tmp_run(tmp_path, monkeypatch)
    system_tmp = tmp_path / "system-tmp"
    system_tmp.mkdir()
    monkeypatch.setattr(runner.tempfile, "gettempdir", lambda: str(system_tmp))
    monkeypatch.setattr(runner.getpass, "getuser", lambda: "someone-private")
    fake = FakeRunner()

    def _spy(argv, **kwargs):
        if argv[0] == "uv":
            out = f"E   AssertionError: {system_tmp}/pytest-of-someone-private/pytest-3/test_x0/out.txt\n1 failed\n"
            return subprocess.CompletedProcess(argv, 1, stdout=out)
        return fake(argv, **kwargs)

    execute(run, command_runner=_spy)
    evidence = run.output(".pytest.txt").read_text(encoding="utf-8")
    assert "someone-private" not in evidence
    assert str(system_tmp) not in evidence
    assert "<tmp>/pytest-of-<user>/pytest-3/test_x0/out.txt" in evidence


def test_inputs_changed_during_run_writes_stub_instead_of_checking(tmp_path, monkeypatch) -> None:
    """bm:dbe1b7f56bdd:IN-06: the checker only runs if the audited inputs still match .meta.json."""
    run = _tmp_run(tmp_path, monkeypatch)
    real_audit = runner.audit_inputs
    calls = {"n": 0}

    def _audit(command_runner):
        calls["n"] += 1
        result = real_audit(command_runner)
        if calls["n"] > 1:
            result = dict(result)
            result["tests/codex_report_status.py"] = {"sha256": "0" * 64, "committed_unchanged": True}
        return result

    monkeypatch.setattr(runner, "audit_inputs", _audit)
    fake = FakeRunner()

    assert execute(run, command_runner=fake) == 1
    assert calls["n"] == 2
    status = run.output(".status.json").read_text(encoding="utf-8")
    assert '"status": "incomplete"' in status
    assert "audited inputs changed during the run" in status
    assert not any(_is_checker(call) for call in fake.calls)


def test_inputs_dirty_after_run_writes_stub_instead_of_checking(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    statuses = {"n": 0}
    fake = FakeRunner()

    def _spy(argv, **kwargs):
        if argv[:2] == ["git", "status"]:
            statuses["n"] += 1
            fake.calls.append(list(argv))
            dirty = " M tests/codex_report_status.py\n" if statuses["n"] > 1 else ""
            return subprocess.CompletedProcess(argv, 0, stdout=dirty)
        return fake(argv, **kwargs)

    assert execute(run, command_runner=_spy) == 1
    status = run.output(".status.json").read_text(encoding="utf-8")
    assert "audited inputs changed during the run" in status
    assert not any(_is_checker(call) for call in fake.calls)


# --- bm:49ded1e86444:WR-02 (owner-approved round 5) ---------------------------

_NON_UTF8_SCRIPT = "import sys; sys.stdout.buffer.write(b'1 passed \\xff\\xfe not utf-8\\n')"


def _real_bytes_for(predicate, fake: FakeRunner, script: str = _NON_UTF8_SCRIPT):
    """Run a real child that prints non-UTF-8 bytes, with the runner's own subprocess kwargs."""
    import sys

    def _spy(argv, **kwargs):
        if predicate(argv):
            fake.calls.append(list(argv))
            kwargs.pop("cwd", None)
            return subprocess.run([sys.executable, "-c", script], check=False, **kwargs)
        return fake(argv, **kwargs)

    return _spy


def test_non_utf8_pytest_output_does_not_crash_the_runner(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner()

    assert execute(run, command_runner=_real_bytes_for(lambda argv: argv[0] == "uv", fake)) == 1

    evidence = run.output(".pytest.txt").read_text(encoding="utf-8")
    assert "exit_code: 0" in evidence
    assert "1 passed \ufffd\ufffd not utf-8" in evidence
    assert run.output(".status.json").read_text() == '{"status": "incomplete"}\n'
    assert _removed(fake)


def test_non_utf8_checker_output_still_writes_a_status(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner()
    script = "import sys; sys.stdout.buffer.write(b'{\"status\": \"incomplete\", \"note\": \"\\xff\"}\\n'); sys.exit(1)"

    assert execute(run, command_runner=_real_bytes_for(_is_checker, fake, script)) == 1

    status = run.output(".status.json").read_text(encoding="utf-8")
    assert status.startswith('{"status": "incomplete"')
    assert "\ufffd" in status


def test_unexpected_exception_after_reservation_writes_status_stub(tmp_path, monkeypatch) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner()

    def _pytest_raises(*_args, **_kwargs):
        raise ValueError("simulated: unexpected failure")

    monkeypatch.setattr(runner, "_run_pytest", _pytest_raises)

    with pytest.raises(runner.RunnerError, match="ValueError"):
        execute(run, command_runner=fake)
    status = run.output(".status.json").read_text(encoding="utf-8")
    assert '"status": "incomplete"' in status
    assert "harness failed before codex finished: ValueError" in status
    assert "simulated" not in status
    assert _removed(fake)
    assert not (tmp_path / "scratch").exists()


@pytest.mark.parametrize("exc", [OSError("simulated: disk full"), TypeError("simulated: not serializable")])
def test_meta_write_failure_after_reservation_writes_status_stub(tmp_path, monkeypatch, exc) -> None:
    """The .meta.json write runs after the reservation, so its failure must leave a status too."""
    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner()
    real_dumps = runner.json.dumps

    def _dumps(obj, *args, **kwargs):
        if isinstance(obj, dict) and obj.get("meta_version") == 1:
            raise exc
        return real_dumps(obj, *args, **kwargs)

    monkeypatch.setattr(runner.json, "dumps", _dumps)

    with pytest.raises(runner.RunnerError, match=type(exc).__name__):
        execute(run, command_runner=fake)
    assert run.output(".prompt.txt").exists()
    status = run.output(".status.json").read_text(encoding="utf-8")
    assert '"status": "incomplete"' in status
    assert type(exc).__name__ in status
    assert not any(call[:3] == ["git", "worktree", "add"] for call in fake.calls)


# --- vibe-check #6 (owner-approved round 6): kill the whole process group -----
#
# `uv run` starts pytest as its own child, so a timeout that kills only the
# direct child leaves pytest running. The long-running children start in their
# own session and the timeout kills that whole group.


@pytest.mark.parametrize("program", ["uv", "codex"])
def test_long_running_children_start_in_their_own_session(tmp_path, monkeypatch, program: str) -> None:
    run = _tmp_run(tmp_path, monkeypatch)
    fake = FakeRunner()
    seen: dict[str, object] = {}

    def _spy(argv, **kwargs):
        if argv[0] == program:
            seen.update(kwargs)
        return fake(argv, **kwargs)

    execute(run, command_runner=_spy)
    assert seen["start_new_session"] is True


def test_execute_defaults_to_the_process_group_runner() -> None:
    import inspect

    assert inspect.signature(execute).parameters["command_runner"].default is runner.run_command


_SPAWNS_GRANDCHILD = """
import subprocess, sys, time
grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
with open(sys.argv[1], "w") as handle:
    handle.write(str(grandchild.pid))
print("started", flush=True)
time.sleep(60)
"""


def _alive(pid: int) -> bool:
    import os

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_timeout_kills_the_grandchild_too(tmp_path) -> None:
    import os
    import signal
    import sys
    import time

    pid_file = tmp_path / "grandchild.pid"
    argv = [sys.executable, "-c", _SPAWNS_GRANDCHILD, str(pid_file)]
    grandchild: int | None = None
    try:
        with pytest.raises(subprocess.TimeoutExpired) as exc_info:
            runner.run_command(
                argv,
                start_new_session=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=2,
            )
        assert "started" in (exc_info.value.stdout or "")
        grandchild = int(pid_file.read_text(encoding="utf-8"))
        # The orphaned grandchild is reaped by init; give it a moment.
        for _ in range(50):
            if not _alive(grandchild):
                break
            time.sleep(0.05)
        assert not _alive(grandchild)
    finally:
        if grandchild is not None and _alive(grandchild):
            os.kill(grandchild, signal.SIGKILL)


def test_run_command_without_a_session_is_plain_subprocess_run() -> None:
    import sys

    proc = runner.run_command([sys.executable, "-c", "print('ok')"], stdout=subprocess.PIPE, text=True, check=False)
    assert proc.returncode == 0
    assert proc.stdout == "ok\n"


def test_run_command_passes_input_to_a_session_child() -> None:
    import sys

    proc = runner.run_command(
        [sys.executable, "-c", "import sys; print(sys.stdin.read().upper())"],
        start_new_session=True,
        input="prompt",
        stdout=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0
    assert proc.stdout == "PROMPT\n"


# --- D-18, round-6 WR-01: an external SIGTERM/SIGHUP kills the active group --
#
# install_signal_handlers() registers a handler that kills every process group
# run_command is still tracking (_ACTIVE_GROUPS), then exits 128+signum. The
# handler runs in a separate child process so the active handler can be
# replaced and restored without touching this test session's own signal
# disposition.

_REPORT_ACTIVE_GROUP_THEN_RUN = """
import sys, threading, time
from tests import codex_review_run as runner

pid_file = sys.argv[1]


def _report_pgid():
    while not runner._ACTIVE_GROUPS:
        time.sleep(0.01)
    with open(pid_file, "w") as handle:
        handle.write(str(next(iter(runner._ACTIVE_GROUPS))))


threading.Thread(target=_report_pgid, daemon=True).start()
runner.install_signal_handlers()
runner.run_command(["sleep", "60"], start_new_session=True)
"""


def _wait_for_text(path: Path, timeout: float = 5.0) -> str:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                return text
        time.sleep(0.02)
    raise TimeoutError(f"{path} was never written")


def _process_group_is_gone(pgid: int, timeout: float = 5.0) -> bool:
    import os
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def _assert_signal_kills_active_process_group(tmp_path: Path, sig: int) -> None:
    import os
    import sys

    pid_file = tmp_path / "pgid.txt"
    child = subprocess.Popen(
        [sys.executable, "-c", _REPORT_ACTIVE_GROUP_THEN_RUN, str(pid_file)],
        cwd=runner.REPO_ROOT,
    )
    try:
        pgid = int(_wait_for_text(pid_file))
        os.kill(child.pid, sig)
        assert _process_group_is_gone(pgid)
        assert child.wait(timeout=5) != 0
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


@pytest.mark.skipif(sys.platform == "win32", reason="process groups and POSIX signals are not available on Windows")
def test_sigterm_kills_active_process_group(tmp_path: Path) -> None:
    import signal

    _assert_signal_kills_active_process_group(tmp_path, signal.SIGTERM)


@pytest.mark.skipif(sys.platform == "win32", reason="process groups and POSIX signals are not available on Windows")
def test_sighup_kills_active_process_group(tmp_path: Path) -> None:
    import signal

    _assert_signal_kills_active_process_group(tmp_path, signal.SIGHUP)


# --- D-18, bugs-002: the post-kill output drain is bounded --------------------
#
# A grandchild started in its own (different) process group can keep the
# stdout pipe open after run_command kills the direct child's group; the
# second communicate() call must give up after DRAIN_TIMEOUT_SECONDS instead
# of hanging forever.

_FORKS_DETACHED_GRANDCHILD = """
import subprocess, sys, time
grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)
with open(sys.argv[1], "w") as handle:
    handle.write(str(grandchild.pid))
time.sleep(30)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="process groups are not available on Windows")
def test_post_kill_drain_is_bounded(tmp_path: Path) -> None:
    import os
    import signal
    import sys
    import time

    pid_file = tmp_path / "grandchild.pid"
    argv = [sys.executable, "-c", _FORKS_DETACHED_GRANDCHILD, str(pid_file)]
    grandchild: int | None = None
    try:
        start = time.monotonic()
        with pytest.raises(subprocess.TimeoutExpired) as exc_info:
            runner.run_command(
                argv,
                start_new_session=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=0.5,
            )
        elapsed = time.monotonic() - start
        assert elapsed < runner.DRAIN_TIMEOUT_SECONDS + 5
        marker = f"\n[drain timed out after {runner.DRAIN_TIMEOUT_SECONDS}s; output truncated]\n"
        assert (exc_info.value.stdout or "").endswith(marker)
    finally:
        for _ in range(100):
            text = pid_file.read_text().strip() if pid_file.exists() else ""
            if text:
                grandchild = int(text)
                break
            time.sleep(0.05)
        if grandchild is not None:
            try:
                os.kill(grandchild, signal.SIGKILL)
            except ProcessLookupError:
                pass


# --- D-18, round-6 WR-01: main() restores the previous handlers on return ----


def test_signal_handlers_restored_after_main(monkeypatch) -> None:
    import signal

    before_term = signal.getsignal(signal.SIGTERM)
    before_hup = signal.getsignal(signal.SIGHUP)
    seen: dict[str, object] = {}

    def _capture(_run, **_kwargs):
        seen["term"] = signal.getsignal(signal.SIGTERM)
        seen["hup"] = signal.getsignal(signal.SIGHUP)
        return 0

    monkeypatch.setattr(runner, "execute", _capture)
    assert main(_cli(PHASE_DIR, "--trusted")) == 0

    assert seen["term"] is runner._handle_termination_signal
    assert seen["hup"] is runner._handle_termination_signal
    assert signal.getsignal(signal.SIGTERM) == before_term
    assert signal.getsignal(signal.SIGHUP) == before_hup
