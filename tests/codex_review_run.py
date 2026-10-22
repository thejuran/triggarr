"""Reproducible runner for the independent Codex adversarial review pass.

Implements docs/codex-adversarial-review-contract.md, Invocation:

1. Creates a detached worktree of the exact head SHA in a fresh temp dir.
2. Runs ``uv run --extra dev pytest tests/ -q`` inside that worktree,
   outside the Codex sandbox, and saves the combined output and exit code
   as ``<OUT>.pytest.txt`` next to the raw Codex outputs.
3. Renders the contract's fixed prompt, substituting only its documented
   placeholders.
4. Runs ``codex exec`` read-only against the worktree with the report
   schema, prompt on stdin, event stream to ``<OUT>.jsonl``.
5. Always removes the worktree, on success and on failure.
6. Runs tests/codex_report_status.py and saves its JSON as
   ``<OUT>.status.json``.

Every command is an argument list run without a shell; free-text inputs
(PR URL, scope) only ever reach Codex through the prompt on stdin.
``--dry-run`` renders the prompt and prints the commands without running
anything or writing any file.

Uses plain ``print()`` because it is review tooling run from the CLI, not
production code under the loguru-only convention documented in CLAUDE.md
(the same exception tests/codex_report_status.py documents).
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = REPO_ROOT / "docs" / "codex-adversarial-review-contract.md"
SCHEMA_PATH = REPO_ROOT / ".claude" / "schemas" / "codex-review-findings.schema.json"

TEMPLATE_HEADING = "## Fixed prompt (version 4)"
PLACEHOLDERS = frozenset({"PR_URL", "HEAD_SHA", "BASE_SHA", "SCOPE", "TEST_EVIDENCE"})

# Everything under .planning/ -- planning records, raw review transcripts and
# generated review artifacts -- is out of scope for the review diff; planning
# markdown is background Codex may read on demand. Must match the fixed prompt.
EXCLUDE_PATHSPECS = (":(exclude,glob).planning/**",)

OUTPUT_SUFFIXES = (".jsonl", ".last.json", ".status.json", ".pytest.txt")
CODEX_TIMEOUT_SECONDS = 1800
PYTEST_TIMEOUT_SECONDS = 1800

_SHA_RE = re.compile(r"[0-9a-f]{40}")
_LABEL_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")

CommandRunner = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True)
class ReviewRun:
    head: str
    base: str
    label: str
    attempt: int
    pr_url: str
    scope: str
    phase_dir: Path

    def __post_init__(self) -> None:
        for name in ("head", "base"):
            if not _SHA_RE.fullmatch(getattr(self, name)):
                raise ValueError(f"{name} must be a full 40-character lowercase commit SHA")
        if not _LABEL_RE.fullmatch(self.label):
            raise ValueError("label must be lowercase letters, digits and hyphens, starting with a letter or digit")
        if self.attempt < 1:
            raise ValueError("attempt must be an integer >= 1")
        if not self.pr_url.strip() or not self.scope.strip():
            raise ValueError("pr-url and scope must not be blank")
        parts = Path(self.phase_dir).parts
        if (
            Path(self.phase_dir).is_absolute()
            or len(parts) < 3
            or parts[:2] != (".planning", "phases")
            or ".." in parts
        ):
            raise ValueError("phase-dir must be a relative path under .planning/phases/")

    @property
    def out_base(self) -> Path:
        return REPO_ROOT / self.phase_dir / "codex" / f"{self.head[:12]}-{self.label}-a{self.attempt}"

    def output(self, suffix: str) -> Path:
        return self.out_base.parent / f"{self.out_base.name}{suffix}"


def load_template(contract_text: str | None = None) -> str:
    """Return the fixed prompt: the first fenced block after the template heading."""
    text = contract_text if contract_text is not None else CONTRACT_PATH.read_text(encoding="utf-8")
    after = text[text.index(TEMPLATE_HEADING) + len(TEMPLATE_HEADING) :]
    match = re.search(r"```[^\n]*\n(.*?)```", after, re.DOTALL)
    if match is None:
        raise ValueError(f"no fenced prompt block after {TEMPLATE_HEADING!r}")
    return match.group(1)


def render_prompt(template: str, values: dict[str, str]) -> str:
    """Substitute exactly the documented placeholders in one pass.

    Single-pass substitution means a value that itself looks like a
    placeholder is never expanded again.
    """
    keys = set(values)
    if keys != PLACEHOLDERS:
        missing = sorted(PLACEHOLDERS - keys)
        unknown = sorted(keys - PLACEHOLDERS)
        raise ValueError(f"placeholder values mismatch: missing {missing}, unknown {unknown}")
    used = set(_PLACEHOLDER_RE.findall(template))
    if used != PLACEHOLDERS:
        raise ValueError(f"template placeholders {sorted(used)} differ from {sorted(PLACEHOLDERS)}")
    return _PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], template)


def prompt_values(run: ReviewRun) -> dict[str, str]:
    return {
        "PR_URL": run.pr_url,
        "HEAD_SHA": run.head,
        "BASE_SHA": run.base,
        "SCOPE": run.scope,
        "TEST_EVIDENCE": str(run.output(".pytest.txt")),
    }


def diff_argv(base: str, head: str) -> list[str]:
    return ["git", "diff", f"{base}..{head}", "--", ".", *EXCLUDE_PATHSPECS]


def worktree_add_argv(worktree: Path, head: str) -> list[str]:
    return ["git", "worktree", "add", "--detach", str(worktree), head]


def worktree_remove_argv(worktree: Path) -> list[str]:
    return ["git", "worktree", "remove", "--force", str(worktree)]


def pytest_argv() -> list[str]:
    # pytest lives in the project's `dev` extra, which a fresh worktree's
    # environment only gets when the extra is requested.
    return ["uv", "run", "--extra", "dev", "pytest", "tests/", "-q"]


def codex_argv(worktree: Path, last_json: Path) -> list[str]:
    return [
        "timeout",
        str(CODEX_TIMEOUT_SECONDS),
        "codex",
        "exec",
        "--sandbox",
        "read-only",
        "--ephemeral",
        "-C",
        str(worktree),
        "--output-schema",
        str(SCHEMA_PATH),
        "--json",
        "-o",
        str(last_json),
        "-",
    ]


def checker_argv(run: ReviewRun, *, exit_code: int | None, current_head: str) -> list[str]:
    checker = REPO_ROOT / "tests" / "codex_report_status.py"
    argv = [sys.executable, str(checker), "--report", str(run.output(".last.json"))]
    if exit_code is not None:
        argv += ["--exit-code", str(exit_code)]
    argv += [
        "--expected-head",
        run.head,
        "--expected-base",
        run.base,
        "--current-head",
        current_head,
        "--attempt",
        str(run.attempt),
    ]
    return argv


def _pytest_env() -> dict[str, str]:
    # The caller's virtualenv belongs to the main checkout; the worktree gets its own.
    return {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}


def _run_pytest(run: ReviewRun, worktree: Path, command_runner: CommandRunner) -> None:
    exit_code: str
    output: str
    try:
        proc = command_runner(
            pytest_argv(),
            cwd=worktree,
            env=_pytest_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=PYTEST_TIMEOUT_SECONDS,
        )
        exit_code, output = str(proc.returncode), proc.stdout or ""
    except subprocess.TimeoutExpired as exc:
        exit_code = f"unknown (timed out after {PYTEST_TIMEOUT_SECONDS}s)"
        captured = exc.stdout or ""
        output = captured.decode("utf-8", "replace") if isinstance(captured, bytes) else captured
    except OSError as exc:
        exit_code, output = "unknown", f"pytest could not start: {type(exc).__name__}\n"

    run.output(".pytest.txt").write_text(
        "Test evidence produced by the harness (tests/codex_review_run.py), not by Codex.\n"
        f"head: {run.head}\n"
        f"working copy: detached worktree at {run.head}\n"
        f"command: {shlex.join(pytest_argv())}\n"
        f"exit_code: {exit_code}\n"
        "--- combined stdout and stderr ---\n"
        f"{output}",
        encoding="utf-8",
    )
    print(f"pytest evidence: {run.output('.pytest.txt')} (exit_code: {exit_code})")


def _run_codex(run: ReviewRun, worktree: Path, prompt: str, command_runner: CommandRunner) -> int | None:
    with run.output(".jsonl").open("w", encoding="utf-8") as events:
        try:
            proc = command_runner(
                codex_argv(worktree, run.output(".last.json")),
                cwd=REPO_ROOT,
                input=prompt,
                stdout=events,
                text=True,
            )
        except OSError as exc:
            print(f"codex could not start: {type(exc).__name__}")
            return None
    print(f"codex exit code: {proc.returncode}")
    return proc.returncode


def execute(run: ReviewRun, *, command_runner: CommandRunner = subprocess.run) -> int:
    """Run the full review pass. Returns the checker's exit code (0 = complete)."""
    existing = [str(run.output(suffix)) for suffix in OUTPUT_SUFFIXES if run.output(suffix).exists()]
    if existing:
        # Raw outputs are never edited after being written; use a new attempt number.
        raise FileExistsError(f"review outputs already exist: {existing}")
    run.out_base.parent.mkdir(parents=True, exist_ok=True)

    template = load_template()
    prompt = render_prompt(template, prompt_values(run))

    scratch = Path(tempfile.mkdtemp(prefix="codex-review-"))
    worktree = scratch / "wt"
    codex_exit: int | None = None
    try:
        command_runner(worktree_add_argv(worktree, run.head), cwd=REPO_ROOT, check=True)
        _run_pytest(run, worktree, command_runner)
        codex_exit = _run_codex(run, worktree, prompt, command_runner)
    finally:
        try:
            removed = command_runner(worktree_remove_argv(worktree), cwd=REPO_ROOT, check=False)
            if removed.returncode != 0:
                print(f"warning: git worktree remove exited {removed.returncode} for {worktree}")
        except OSError as exc:
            print(f"warning: git worktree remove could not run: {type(exc).__name__}")
        shutil.rmtree(scratch, ignore_errors=True)

    current = command_runner(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, check=True, stdout=subprocess.PIPE, text=True
    )
    checker = command_runner(
        checker_argv(run, exit_code=codex_exit, current_head=current.stdout.strip()),
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        text=True,
    )
    run.output(".status.json").write_text(checker.stdout or "", encoding="utf-8")
    print(f"status: {run.output('.status.json')}")
    print(checker.stdout or "", end="")
    return checker.returncode


def dry_run(run: ReviewRun) -> int:
    """Print the rendered prompt and every command without running or writing anything."""
    worktree = Path("<temp-dir>") / "wt"
    prompt = render_prompt(load_template(), prompt_values(run))
    print("# Rendered prompt (sent on stdin to codex exec)")
    print(prompt)
    print("# Commands")
    print(shlex.join(worktree_add_argv(worktree, run.head)))
    print(f"(cd {worktree} && {shlex.join(pytest_argv())}) > {shlex.quote(str(run.output('.pytest.txt')))}")
    print(
        f"{shlex.join(codex_argv(worktree, run.output('.last.json')))} < prompt"
        f" > {shlex.quote(str(run.output('.jsonl')))}"
    )
    print(shlex.join(worktree_remove_argv(worktree)) + "  # always, including on failure")
    checker = checker_argv(run, exit_code=0, current_head="<git rev-parse HEAD>")
    checker[0] = "uv run python"
    print(" ".join(shlex.quote(part) if i else part for i, part in enumerate(checker)), end="")
    print(f" > {shlex.quote(str(run.output('.status.json')))}  # --exit-code is codex's real exit code")
    return 0


def _sha(value: str) -> str:
    if not _SHA_RE.fullmatch(value):
        raise argparse.ArgumentTypeError(f"must be 40 lowercase hex characters, got {value!r}")
    return value


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"must be an integer >= 1, got {value!r}") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError(f"must be an integer >= 1, got {value!r}")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the independent Codex adversarial review pass.")
    parser.add_argument("--head", required=True, type=_sha, help="Full head SHA to review")
    parser.add_argument("--base", required=True, type=_sha, help="Full base SHA")
    parser.add_argument("--label", required=True, help="Output label, e.g. explicit, quick, phase")
    parser.add_argument("--attempt", required=True, type=_positive_int)
    parser.add_argument("--pr-url", required=True, help="PR URL, or 'none (local checkpoint, not pushed)'")
    parser.add_argument("--scope", required=True)
    parser.add_argument("--phase-dir", required=True, type=Path, help="e.g. .planning/phases/83-...")
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt and commands only")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        run = ReviewRun(args.head, args.base, args.label, args.attempt, args.pr_url, args.scope, args.phase_dir)
    except ValueError as exc:
        parser.error(str(exc))
    if not (REPO_ROOT / run.phase_dir).is_dir():
        parser.error(f"phase-dir does not exist: {run.phase_dir}")
    if args.dry_run:
        return dry_run(run)
    try:
        return execute(run)
    except FileExistsError as exc:
        print(f"error: {exc}; use the next attempt number")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
