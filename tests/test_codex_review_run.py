"""Tests for tests/codex_review_run.py, the reproducible Codex review runner.

Durable Codex completeness (owner 2026-10-22). Only the pure parts are
exercised here -- prompt rendering, the scope pathspec, output naming,
argument construction and dry-run -- plus the orchestration with a fake
command runner. Codex itself is never called.
"""

from __future__ import annotations

import subprocess
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


def test_template_is_the_contract_version_four_prompt() -> None:
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


def test_exclude_pathspecs_cover_all_of_planning() -> None:
    assert EXCLUDE_PATHSPECS == (":(exclude,glob).planning/**",)


def test_pathspecs_exclude_everything_under_planning(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("base\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD").strip()

    files = {
        "triggarr/app.py": "x = 1\n",
        ".planning/phases/83-x/83-REVIEW.md": "notes\n",
        ".planning/phases/83-x/codex/abc-explicit-a1.last.json": "{}\n",
        ".planning/phases/83-x/codex/abc-explicit-a1.pytest.txt": "ok\n",
        ".planning/codex/top-level.json": "{}\n",
        ".planning/quick/run.jsonl": "{}\n",
    }
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        _git(repo, "add", "-f", name)
    _git(repo, "commit", "-q", "-m", "change")
    head = _git(repo, "rev-parse", "HEAD").strip()

    argv = diff_argv(base, head)
    changed = set(_git(repo, argv[1], "--name-only", *argv[2:]).split())
    assert changed == {"triggarr/app.py"}


# --- Output naming -----------------------------------------------------------


def test_output_base_naming() -> None:
    run = _run()
    assert run.out_base == REPO_ROOT / PHASE_DIR / "codex" / f"{H[:12]}-explicit-a2"


@pytest.mark.parametrize("suffix", [".jsonl", ".last.json", ".status.json", ".pytest.txt"])
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
        "timeout",
        "1800",
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
    assert {suffix: run.output(suffix).exists() for suffix in runner.OUTPUT_SUFFIXES} == before


def test_cli_rejects_short_sha() -> None:
    argv = _cli(PHASE_DIR, "--dry-run", "--trusted")
    argv[1] = "abc"
    with pytest.raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 2


# --- Orchestration with a fake command runner -------------------------------


class FakeRunner:
    """Records every command; fails the one whose program matches *fail_on*."""

    def __init__(self, fail_on: str | None = None, codex_exit: int = 0) -> None:
        self.calls: list[list[str]] = []
        self.fail_on = fail_on
        self.codex_exit = codex_exit

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        program = argv[2] if argv[0] == "timeout" else argv[0]
        if self.fail_on and self.fail_on in (program, " ".join(argv[:3])):
            raise OSError("simulated failure")
        if argv[:3] == ["git", "worktree", "add"]:
            Path(argv[4]).mkdir(parents=True)
            return subprocess.CompletedProcess(argv, 0)
        if argv[:2] == ["git", "rev-parse"]:
            return subprocess.CompletedProcess(argv, 0, stdout=H + "\n")
        if argv[0] == "uv":
            return subprocess.CompletedProcess(argv, 1, stdout="1 failed, 9 passed\n")
        if program == "codex":
            assert kwargs["input"].startswith("Independently review")
            kwargs["stdout"].write('{"type":"done"}\n')
            return subprocess.CompletedProcess(argv, self.codex_exit)
        if "codex_report_status.py" in " ".join(argv):
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
    assert order.index("uv run --extra") < order.index("timeout 1800 codex")
    assert order.index("timeout 1800 codex") < order.index("git worktree remove")


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
    checker = next(call for call in fake.calls if "codex_report_status.py" in " ".join(call))
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


def test_execute_untrusted_skips_pytest_and_records_why(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    (tmp_path / PHASE_DIR).mkdir(parents=True)
    monkeypatch.setattr(runner.tempfile, "mkdtemp", lambda prefix: str(tmp_path / "scratch"))
    (tmp_path / "scratch").mkdir()
    run = _run(attempt=1, trusted=False)
    fake = FakeRunner()

    execute(run, command_runner=fake)

    assert not any(call[0] == "uv" for call in fake.calls)
    evidence = run.output(".pytest.txt").read_text()
    assert "tests not run (untrusted source)" in evidence
    assert "exit_code:" not in evidence
    assert any("codex" in call for call in fake.calls)


def test_dry_run_untrusted_prints_no_pytest_command(capsys) -> None:
    assert main(_cli(PHASE_DIR, "--dry-run", "--untrusted")) == 0
    out = capsys.readouterr().out
    assert "pytest tests/ -q) >" not in out
    assert "tests not run (untrusted source)" in out


def test_contract_documents_untrusted_sources() -> None:
    text = runner.CONTRACT_PATH.read_text(encoding="utf-8")
    assert "--untrusted" in text and "--trusted" in text
    assert "Dependabot" in text
    assert "tests not run (untrusted source)" in text
    assert "CI results" in text


def test_prompt_covers_untrusted_evidence() -> None:
    assert "untrusted source" in load_template()
