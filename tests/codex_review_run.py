"""Reproducible runner for the independent Codex adversarial review pass.

Implements docs/codex-adversarial-review-contract.md, Invocation:

0. Refuses to start if the contract, schema, checker or runner has
   uncommitted changes, then saves the exact rendered prompt as
   ``<OUT>.prompt.txt`` and a provenance record (template version, sha256
   of those files, harness HEAD) as ``<OUT>.meta.json``.
1. Creates a detached worktree of the exact head SHA in a fresh temp dir.
2. With ``--trusted`` (this repository's own branches), runs
   ``uv run --extra dev pytest tests/ -q`` inside that worktree, outside
   the Codex sandbox, and saves the combined output and exit code as
   ``<OUT>.pytest.txt`` next to the raw Codex outputs. With ``--untrusted``
   (Dependabot or outside-contributor heads) it runs no tests and the
   evidence file says "tests not run (untrusted source)".
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
import hashlib
import json
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

# The checkout this harness runs from. REPO_ROOT is where outputs are written
# and git commands run; both are the same checkout in normal use.
HARNESS_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = HARNESS_ROOT
CONTRACT_PATH = HARNESS_ROOT / "docs" / "codex-adversarial-review-contract.md"
SCHEMA_PATH = HARNESS_ROOT / ".claude" / "schemas" / "codex-review-findings.schema.json"

# Files that decide what Codex is told and how its report is judged. Each run
# records their hashes and refuses to start if any has uncommitted changes,
# so the evidence shows exactly which committed versions produced it.
AUDITED_INPUTS = (
    "docs/codex-adversarial-review-contract.md",
    ".claude/schemas/codex-review-findings.schema.json",
    "tests/codex_report_status.py",
    "tests/codex_review_run.py",
)

TEMPLATE_HEADING = "## Fixed prompt (version 4)"
PLACEHOLDERS = frozenset({"PR_URL", "HEAD_SHA", "BASE_SHA", "SCOPE", "TEST_EVIDENCE"})

# Everything under .planning/ -- planning records, raw review transcripts and
# generated review artifacts -- is out of scope for the review diff; planning
# markdown is background Codex may read on demand. Must match the fixed prompt.
EXCLUDE_PATHSPECS = (":(exclude,glob).planning/**",)

OUTPUT_SUFFIXES = (".prompt.txt", ".meta.json", ".jsonl", ".last.json", ".status.json", ".pytest.txt")

# Where the harness evidence is copied inside the temp worktree (untracked),
# so the prompt names a working-copy-relative path and never the operator's
# home directory.
EVIDENCE_RELPATH = ".codex-review-evidence/pytest.txt"
CODEX_TIMEOUT_SECONDS = 1800
PYTEST_TIMEOUT_SECONDS = 1800

_SHA_RE = re.compile(r"[0-9a-f]{40}")
_LABEL_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")

CommandRunner = Callable[..., subprocess.CompletedProcess]


class RunnerError(RuntimeError):
    """A failure the CLI reports in plain words, without a traceback."""


@dataclass(frozen=True)
class ReviewRun:
    head: str
    base: str
    label: str
    attempt: int
    pr_url: str
    scope: str
    phase_dir: Path
    # Owner decision 2026-10-22: harness pytest runs only for this
    # repository's own branches. Dependabot and outside-contributor heads are
    # untrusted: their tests never run on the operator's machine.
    trusted: bool

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


def template_version(contract_text: str | None = None) -> str:
    """Return the contract's "Template version: N." number."""
    text = contract_text if contract_text is not None else CONTRACT_PATH.read_text(encoding="utf-8")
    match = re.search(r"^Template version: (\d+)\.", text, re.MULTILINE)
    if match is None:
        raise ValueError("contract has no 'Template version: N.' line")
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
        "TEST_EVIDENCE": EVIDENCE_RELPATH,
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


UNTRUSTED_EVIDENCE = "tests not run (untrusted source)"


def _untrusted_evidence(run: ReviewRun) -> str:
    return (
        "Test evidence produced by the harness (tests/codex_review_run.py), not by Codex.\n"
        f"head: {run.head}\n"
        "source: untrusted (--untrusted)\n"
        f"{UNTRUSTED_EVIDENCE}\n"
        "Dependabot and outside-contributor heads are never executed by the harness;\n"
        "rely on the PR's CI results for test evidence.\n"
    )


def redact_local_paths(text: str, *, worktree: Path, scratch: Path) -> str:
    """Replace local absolute paths in harness-written text with neutral markers.

    The evidence is committed to a public repository, so the temp worktree,
    the temp dir, the main checkout and the home directory never appear in it.
    """
    replacements: list[tuple[str, str]] = []
    for path, marker in ((worktree, "<worktree>"), (scratch, "<scratch>"), (REPO_ROOT, "<repo>"), (Path.home(), "~")):
        for variant in {str(path), str(path.resolve())}:
            if len(variant) > 1:
                replacements.append((variant, marker))
    for variant, marker in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        text = text.replace(variant, marker)
    return text


def _publish_evidence(run: ReviewRun, worktree: Path, scratch: Path, text: str) -> None:
    """Write the evidence next to the raw outputs and copy it into the worktree."""
    text = redact_local_paths(text, worktree=worktree, scratch=scratch)
    run.output(".pytest.txt").write_text(text, encoding="utf-8")
    copy = worktree / EVIDENCE_RELPATH
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_text(text, encoding="utf-8")


def _run_pytest(run: ReviewRun, worktree: Path, scratch: Path, command_runner: CommandRunner) -> None:
    if not run.trusted:
        _publish_evidence(run, worktree, scratch, _untrusted_evidence(run))
        print(f"pytest evidence: {run.output('.pytest.txt')} ({UNTRUSTED_EVIDENCE})")
        return
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

    _publish_evidence(
        run,
        worktree,
        scratch,
        "Test evidence produced by the harness (tests/codex_review_run.py), not by Codex.\n"
        f"head: {run.head}\n"
        "source: trusted (--trusted)\n"
        f"working copy: detached worktree at {run.head}\n"
        f"command: {shlex.join(pytest_argv())}\n"
        f"exit_code: {exit_code}\n"
        "--- combined stdout and stderr ---\n"
        f"{output}",
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


def _git_stdout(argv: list[str], command_runner: CommandRunner) -> str:
    """Run a read-only git command in the harness checkout; any failure is a RunnerError."""
    try:
        proc = command_runner(argv, cwd=HARNESS_ROOT, stdout=subprocess.PIPE, text=True, check=False)
    except OSError as exc:
        raise RunnerError(f"{shlex.join(argv[:3])} could not run: {type(exc).__name__}") from exc
    if proc.returncode != 0:
        raise RunnerError(f"{shlex.join(argv[:3])} exited {proc.returncode}")
    return proc.stdout or ""


def audit_inputs(command_runner: CommandRunner) -> dict[str, dict[str, object]]:
    """Return sha256 and committed state for each audited input; refuse if any is dirty."""
    status = _git_stdout(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", *AUDITED_INPUTS], command_runner
    )
    dirty = sorted(line[3:].strip() for line in status.splitlines() if line.strip())
    if dirty:
        raise RunnerError(
            f"audited inputs have uncommitted changes: {dirty}; commit them first so the run is reproducible"
        )
    return {
        relpath: {
            "sha256": hashlib.sha256((HARNESS_ROOT / relpath).read_bytes()).hexdigest(),
            "committed_unchanged": True,
        }
        for relpath in AUDITED_INPUTS
    }


def run_meta(run: ReviewRun, *, harness_head: str, inputs: dict[str, dict[str, object]]) -> dict[str, object]:
    return {
        "meta_version": 1,
        "head": run.head,
        "base": run.base,
        "label": run.label,
        "attempt": run.attempt,
        "trusted": run.trusted,
        "template_version": template_version(),
        "harness_head": harness_head,
        "inputs": inputs,
        "codex_timeout_seconds": CODEX_TIMEOUT_SECONDS,
    }


def reserve_outputs(run: ReviewRun, prompt: str) -> None:
    """Atomically claim this head/label/attempt by creating ``<OUT>.prompt.txt``.

    O_CREAT|O_EXCL makes the claim atomic: if another run already created
    the file, this raises FileExistsError and leaves that file untouched.
    """
    fd = os.open(run.output(".prompt.txt"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(prompt)


def execute(run: ReviewRun, *, command_runner: CommandRunner = subprocess.run) -> int:
    """Run the full review pass. Returns the checker's exit code (0 = complete)."""
    existing = [str(run.output(suffix)) for suffix in OUTPUT_SUFFIXES if run.output(suffix).exists()]
    if existing:
        # Raw outputs are never edited after being written; use a new attempt number.
        raise FileExistsError(f"review outputs already exist: {existing}")

    inputs = audit_inputs(command_runner)
    harness_head = _git_stdout(["git", "rev-parse", "HEAD"], command_runner).strip()
    template = load_template()
    prompt = render_prompt(template, prompt_values(run))
    meta = run_meta(run, harness_head=harness_head, inputs=inputs)

    run.out_base.parent.mkdir(parents=True, exist_ok=True)
    # The reservation is the first write; nothing else is touched if it fails.
    reserve_outputs(run, prompt)
    run.output(".meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    scratch = Path(tempfile.mkdtemp(prefix="codex-review-"))
    worktree = scratch / "wt"
    codex_exit: int | None = None
    try:
        command_runner(worktree_add_argv(worktree, run.head), cwd=REPO_ROOT, check=True)
        _run_pytest(run, worktree, scratch, command_runner)
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
    print(f"git status --porcelain --untracked-files=all -- {' '.join(AUDITED_INPUTS)}  # must be empty")
    print(f"# save the prompt to {shlex.quote(str(run.output('.prompt.txt')))}")
    print(f"# save provenance to {shlex.quote(str(run.output('.meta.json')))}")
    print(shlex.join(worktree_add_argv(worktree, run.head)))
    if run.trusted:
        print(f"(cd {worktree} && {shlex.join(pytest_argv())}) > {shlex.quote(str(run.output('.pytest.txt')))}")
    else:
        print(f"# --untrusted: no pytest; {shlex.quote(str(run.output('.pytest.txt')))} records '{UNTRUSTED_EVIDENCE}'")
    print(
        f"{shlex.join(codex_argv(worktree, run.output('.last.json')))} < prompt"
        f" > {shlex.quote(str(run.output('.jsonl')))}"
    )
    evidence = shlex.quote(str(run.output(".pytest.txt")))
    print(f"# copy {evidence} to {worktree / EVIDENCE_RELPATH} (local paths redacted)")
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
    trust = parser.add_mutually_exclusive_group(required=True)
    trust.add_argument(
        "--trusted",
        dest="trusted",
        action="store_true",
        help="Head is from this repository's own branch: run the harness pytest",
    )
    trust.add_argument(
        "--untrusted",
        dest="trusted",
        action="store_false",
        help="Dependabot or outside-contributor head: run no tests, rely on CI results",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt and commands only")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        run = ReviewRun(
            args.head, args.base, args.label, args.attempt, args.pr_url, args.scope, args.phase_dir, args.trusted
        )
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
    except RunnerError as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
