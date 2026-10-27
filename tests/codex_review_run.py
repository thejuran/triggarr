"""Reproducible runner for the independent Codex adversarial review pass.

Implements docs/codex-adversarial-review-contract.md, Invocation:

0. Refuses to start if the contract, schema, checker or runner has
   uncommitted changes, then saves the exact rendered prompt as
   ``<OUT>.prompt.txt`` and a provenance record (template version, sha256
   of those files, harness HEAD) as ``<OUT>.meta.json``.
1. Creates a detached worktree of the exact head SHA in a fresh temp dir.
2. Runs ``uv run --extra dev pytest tests/ -q`` inside that worktree,
   outside the Codex sandbox, in its own process group so a timeout kills
   pytest and not just ``uv``, and saves the combined output and exit code
   as ``<OUT>.pytest.txt`` next to the raw Codex outputs. A copy goes into
   the worktree, created exclusively and without following links; the run
   is refused if the reviewed tree already has anything at that path.
3. Renders the contract's fixed prompt, substituting only its documented
   placeholders.
4. Runs ``codex exec`` read-only against the worktree with the report
   schema, prompt on stdin, event stream to ``<OUT>.jsonl``.
5. Always removes the worktree, on success and on failure.
6. Runs tests/codex_report_status.py and saves its JSON as
   ``<OUT>.status.json``.

Only ``--trusted`` heads (this repository's own branches) are reviewed.
``--untrusted`` (Dependabot or outside-contributor heads) is refused before
anything runs or is written: Codex stays PENDING for those heads and their
CI results are used instead.

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
import contextlib
import getpass
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
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

TEMPLATE_HEADING = "## Fixed prompt (version 5)"
PLACEHOLDERS = frozenset({"PR_URL", "HEAD_SHA", "BASE_SHA", "SCOPE", "TEST_EVIDENCE"})

# Planning markdown, raw review transcripts and generated review artifacts are
# out of scope for the review diff; planning markdown is background Codex may
# read on demand. Every other file under .planning/ -- notably the sensitive
# BM configuration .planning/config.json -- stays in scope. Must match the
# fixed prompt.
EXCLUDE_PATHSPECS = (
    ":(exclude,glob).planning/**/codex/**",
    ":(exclude,glob).planning/**/*.jsonl",
    ":(exclude,glob).planning/**/*.md",
)

OUTPUT_SUFFIXES = (".prompt.txt", ".meta.json", ".jsonl", ".last.json", ".status.json", ".pytest.txt")

# Where the harness evidence is copied inside the temp worktree (untracked),
# so the prompt names a working-copy-relative path and never the operator's
# home directory.
EVIDENCE_RELPATH = ".codex-review-evidence/pytest.txt"
CODEX_TIMEOUT_SECONDS = 1800
CODEX_TIMEOUT_EXIT = 124  # the exit code GNU timeout uses, so records stay comparable
PYTEST_TIMEOUT_SECONDS = 1800

_SHA_RE = re.compile(r"[0-9a-f]{40}")
_LABEL_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")

CommandRunner = Callable[..., subprocess.CompletedProcess]

# Bounds the post-kill output drain (the second `communicate()` call after a
# timeout or signal kills the process group). A descendant that escaped into
# its own process group (e.g. via setsid) can keep holding the stdout pipe
# open even after the tracked group is dead; without this bound that drain
# could hang the run forever despite the kill having already happened.
DRAIN_TIMEOUT_SECONDS = 10

# Process-group ids started by run_command(start_new_session=True) that are
# still active. SIGTERM/SIGHUP handlers kill every group listed here so an
# external signal can't leave the Codex/pytest group orphaned.
_ACTIVE_GROUPS: set[int] = set()

# Set by _handle_termination_signal to the signal number it was called with,
# so a later cleanup step (_finalize_raw_outputs) can name the signal in the
# status it records, even though the handler itself only communicates via
# the SystemExit it raises.
_RECEIVED_SIGNAL: int | None = None


def _kill_group(proc: subprocess.Popen) -> None:
    # The group may already be gone (ProcessLookupError), or a second kill
    # racing right behind the signal handler's own first SIGKILL can find it
    # briefly unsignalable (PermissionError, confirmed on macOS) -- both mean
    # "already handled", not a real failure, so any OSError here is ignored.
    with contextlib.suppress(OSError):
        os.killpg(proc.pid, signal.SIGKILL)


def _terminate_active_groups() -> None:
    """Kill every process group run_command is still tracking."""
    for pgid in list(_ACTIVE_GROUPS):
        with contextlib.suppress(OSError):
            os.killpg(pgid, signal.SIGKILL)


def _handle_termination_signal(signum: int, _frame: object) -> None:
    global _RECEIVED_SIGNAL
    _RECEIVED_SIGNAL = signum
    _terminate_active_groups()
    print(f"error: received {signal.Signals(signum).name}; stopped the Codex/pytest process group")
    raise SystemExit(128 + signum)


def install_signal_handlers() -> dict[int, object]:
    """Install SIGTERM/SIGHUP handlers that kill every tracked process group.

    Returns the previous handlers so the caller can restore them.
    """
    previous: dict[int, object] = {}
    for sig in (signal.SIGTERM, signal.SIGHUP):
        previous[sig] = signal.getsignal(sig)
        signal.signal(sig, _handle_termination_signal)
    return previous


def _is_text_mode(kwargs: dict) -> bool:
    """True when the Popen call will hand back str output, not bytes."""
    return bool(kwargs.get("text") or kwargs.get("universal_newlines") or kwargs.get("encoding"))


def _with_drain_marker(output: str | bytes | None, *, text_mode: bool) -> str | bytes:
    marker = f"\n[drain timed out after {DRAIN_TIMEOUT_SECONDS}s; output truncated]\n"
    if text_mode:
        return (output or "") + marker
    return (output or b"") + marker.encode()


def run_command(
    argv: list[str],
    *,
    start_new_session: bool = False,
    input: str | None = None,
    timeout: float | None = None,
    check: bool = False,
    **kwargs,
) -> subprocess.CompletedProcess:
    """subprocess.run, except a child started in its own session is killed as a whole group.

    `uv run` starts pytest as a child of its own, so killing only the direct
    child on a timeout would leave pytest running. With *start_new_session*
    the child leads a new process group, tracked in _ACTIVE_GROUPS so an
    external SIGTERM/SIGHUP can also kill it, and a timeout (or any other
    interruption) kills that group before re-raising. The post-kill drain
    that collects partial output is bounded by DRAIN_TIMEOUT_SECONDS so a
    descendant holding stdout open in a different process group can't hang
    the run.
    """
    if not start_new_session:
        return subprocess.run(argv, input=input, timeout=timeout, check=check, **kwargs)
    if input is not None:
        kwargs["stdin"] = subprocess.PIPE
    text_mode = _is_text_mode(kwargs)
    with subprocess.Popen(argv, start_new_session=True, **kwargs) as proc:
        _ACTIVE_GROUPS.add(proc.pid)
        try:
            try:
                stdout, stderr = proc.communicate(input, timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                _kill_group(proc)
                try:
                    exc.stdout, exc.stderr = proc.communicate(timeout=DRAIN_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired as drain_exc:
                    exc.stdout = _with_drain_marker(drain_exc.stdout, text_mode=text_mode)
                    exc.stderr = _with_drain_marker(drain_exc.stderr, text_mode=text_mode)
                raise
            except BaseException:
                _kill_group(proc)
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=DRAIN_TIMEOUT_SECONDS)
                raise
        finally:
            _ACTIVE_GROUPS.discard(proc.pid)
    completed = subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)
    if check:
        completed.check_returncode()
    return completed


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
    # Owner decisions 2026-10-22: only this repository's own branches are
    # trusted. Dependabot and outside-contributor heads are untrusted, and the
    # harness refuses to run Codex or their tests for them.
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
    # The time limit is enforced in-process (run_command's timeout, which
    # kills the whole process group), not by an external `timeout` binary,
    # which macOS does not ship.
    return [
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


UNTRUSTED_REFUSAL = (
    "Codex is not run for untrusted heads (Dependabot or outside-contributor PRs) until the harness is"
    " hardened. Record 'Codex: PENDING — untrusted source' and use the PR's CI results for test evidence;"
    " the owner chooses: wait, retry later, or approve a fallback."
)


def redact_local_paths(text: str, *, worktree: Path, scratch: Path) -> str:
    """Replace local absolute paths in harness-written text with neutral markers.

    The evidence is committed to a public repository, so the temp worktree,
    the temp dir, the system temp dir, the main checkout and the home
    directory are all redacted out of it, and so is the username in
    pytest's ``pytest-of-<user>`` temp directory (it shows up in failure
    output).

    This also runs, going forward, on the raw Codex ``.jsonl`` event stream
    and ``.last.json`` report after each run finishes or is interrupted, so
    a future run's local paths are redacted there too before the checker
    grades it. Raw evidence already published is left as published, by
    owner decision; Codex's own reads of these files during the run are not
    redacted.
    """
    replacements: list[tuple[str, str]] = []
    paths = (
        (worktree, "<worktree>"),
        (scratch, "<scratch>"),
        (REPO_ROOT, "<repo>"),
        (Path(tempfile.gettempdir()), "<tmp>"),
        (Path.home(), "~"),
    )
    for path, marker in paths:
        for variant in {str(path), str(path.resolve())}:
            if len(variant) > 1:
                replacements.append((variant, marker))
    try:
        user = getpass.getuser()
    except (KeyError, OSError) as exc:
        print(
            f"warning: getpass.getuser() failed ({type(exc).__name__});"
            " username redaction in evidence text is skipped"
        )
        user = ""
    if user:
        replacements.append((f"pytest-of-{user}", "pytest-of-<user>"))
    for variant, marker in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        text = text.replace(variant, marker)
    return text


def _publish_evidence(run: ReviewRun, worktree: Path, scratch: Path, text: str) -> None:
    """Write the evidence next to the raw outputs and copy it into the worktree."""
    text = redact_local_paths(text, worktree=worktree, scratch=scratch)
    run.output(".pytest.txt").write_text(text, encoding="utf-8")
    _write_evidence_copy(worktree, text)


def _write_evidence_copy(worktree: Path, text: str) -> None:
    """Create the evidence copy inside the worktree without following any link.

    The worktree is a checkout of the reviewed head, so the head decides what
    already exists there. Anything already at the evidence directory (a
    directory, a file, or a symlink, dangling or not) is refused rather than
    written through; the directory is created fresh and the file with
    O_CREAT|O_EXCL|O_NOFOLLOW.
    """
    relative_dir = Path(EVIDENCE_RELPATH).parent
    directory = worktree / relative_dir
    if os.path.lexists(directory):
        raise RunnerError(f"the reviewed tree already contains {relative_dir}; refusing to write evidence into it")
    try:
        directory.mkdir()
        fd = os.open(worktree / EVIDENCE_RELPATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except OSError as exc:
        # The lexists check above guarantees this directory did not exist
        # before this call, so anything it created is always safe to remove.
        with contextlib.suppress(OSError):
            directory.rmdir()
        raise RunnerError(f"could not create the evidence copy in the worktree: {type(exc).__name__}") from exc
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)


def _run_pytest(run: ReviewRun, worktree: Path, scratch: Path, command_runner: CommandRunner) -> None:
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
            errors="replace",
            timeout=PYTEST_TIMEOUT_SECONDS,
            start_new_session=True,
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
                timeout=CODEX_TIMEOUT_SECONDS,
                start_new_session=True,
            )
        except subprocess.TimeoutExpired:
            print(f"codex timed out after {CODEX_TIMEOUT_SECONDS}s")
            return CODEX_TIMEOUT_EXIT
        except OSError as exc:
            print(f"codex could not start: {type(exc).__name__}")
            return None
    print(f"codex exit code: {proc.returncode}")
    return proc.returncode


def _redact_file(path: Path, *, worktree: Path, scratch: Path) -> None:
    """Rewrite *path* with local absolute paths redacted, if it exists and needs it.

    Write-then-rename, matching this repo's atomic-write convention: the
    redacted text lands in a sibling temp file first, so a failure partway
    through never leaves *path* half-written.
    """
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    redacted = redact_local_paths(text, worktree=worktree, scratch=scratch)
    if redacted == text:
        return
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".redact-tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(redacted)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except OSError:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


def _git_stdout(argv: list[str], command_runner: CommandRunner) -> str:
    """Run a read-only git command in the harness checkout; any failure is a RunnerError."""
    try:
        proc = command_runner(
            argv, cwd=HARNESS_ROOT, stdout=subprocess.PIPE, text=True, errors="replace", check=False
        )
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


def run_meta(
    run: ReviewRun, *, harness_head: str, inputs: dict[str, dict[str, object]], allow_stale_head: bool
) -> dict[str, object]:
    return {
        "meta_version": 1,
        "head": run.head,
        "base": run.base,
        "label": run.label,
        "attempt": run.attempt,
        "trusted": run.trusted,
        "template_version": template_version(),
        "harness_head": harness_head,
        "allow_stale_head": allow_stale_head,
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


def _write_status_stub(run: ReviewRun, reason: str) -> None:
    """Record an incomplete status when the checker's own result is unavailable."""
    stub = {
        "status": "incomplete",
        "reasons": [reason],
        "qualified_ids": [],
        "finding_count": 0,
        "inspected_head": None,
        "inspected_base": None,
    }
    run.output(".status.json").write_text(json.dumps(stub) + "\n", encoding="utf-8")
    print(f"status: {run.output('.status.json')}")
    print(json.dumps(stub))


def _finalize_raw_outputs(run: ReviewRun, *, worktree: Path, scratch: Path) -> None:
    """Redact the raw Codex outputs before grading, in a path that always runs.

    Called from a `finally` around the Codex step, not only after it returns
    normally: a SIGTERM/SIGHUP handler raises SystemExit, which would skip a
    post-return call and leave partial raw output unredacted (checker B12).

    Ordering guarantee: by the time this runs, a terminating signal has
    already SIGKILLed every tracked process group (install_signal_handlers),
    run_command's BaseException branch has waited for the child bounded by
    DRAIN_TIMEOUT_SECONDS, and _run_codex's `with open(...)` for the .jsonl
    stream has closed -- so no writer is still appending to either file.

    If this runs while an exception is propagating (including the SystemExit
    a signal handler raises) and no status has been recorded yet, this also
    writes an incomplete status stub naming the signal or failure, then lets
    the exception continue unchanged so the exit status is unaffected.
    """
    _, exc_value, _ = sys.exc_info()
    redaction_failed = False
    for suffix in (".jsonl", ".last.json"):
        path = run.output(suffix)
        try:
            _redact_file(path, worktree=worktree, scratch=scratch)
        except OSError as exc:
            print(f"warning: could not redact {path}: {type(exc).__name__}")
            redaction_failed = True
    if exc_value is None or run.output(".status.json").exists():
        return
    if isinstance(exc_value, SystemExit) and _RECEIVED_SIGNAL is not None:
        reason = f"interrupted by {signal.Signals(_RECEIVED_SIGNAL).name} during the Codex step"
    else:
        reason = f"run failed during the Codex step: {type(exc_value).__name__}"
    if redaction_failed:
        reason += "; the raw output may contain unredacted local paths"
    _write_status_stub(run, reason)


def _add_worktree(run: ReviewRun, worktree: Path, command_runner: CommandRunner) -> None:
    try:
        added = command_runner(worktree_add_argv(worktree, run.head), cwd=REPO_ROOT, check=False)
    except OSError as exc:
        raise RunnerError(f"git worktree add could not run: {type(exc).__name__}") from exc
    if added.returncode != 0:
        raise RunnerError(f"git worktree add exited {added.returncode} for head {run.head[:12]}")


def execute(
    run: ReviewRun, *, command_runner: CommandRunner = run_command, allow_stale_head: bool = False
) -> int:
    """Run the full review pass. Returns the checker's exit code (0 = complete).

    A head that is not the checkout's HEAD can only be assessed stale, so it
    is refused unless *allow_stale_head* is set (for example, finishing an
    earlier head's automatic retry).
    """
    if not run.trusted:
        raise RunnerError(UNTRUSTED_REFUSAL)
    existing = [str(run.output(suffix)) for suffix in OUTPUT_SUFFIXES if run.output(suffix).exists()]
    if existing:
        # Raw outputs are not edited after the pre-grading redaction; use a new attempt number.
        raise FileExistsError(f"review outputs already exist: {existing}")

    inputs = audit_inputs(command_runner)
    harness_head = _git_stdout(["git", "rev-parse", "HEAD"], command_runner).strip()
    if harness_head != run.head and not allow_stale_head:
        raise RunnerError(
            f"--head {run.head[:12]} is not the checkout's HEAD {harness_head[:12]}, so the result can only be"
            " assessed stale; pass --allow-stale-head to run it anyway"
        )
    template = load_template()
    prompt = render_prompt(template, prompt_values(run))
    meta = run_meta(run, harness_head=harness_head, inputs=inputs, allow_stale_head=allow_stale_head)

    run.out_base.parent.mkdir(parents=True, exist_ok=True)
    # The reservation is the first write; nothing else is touched if it fails.
    reserve_outputs(run, prompt)
    try:
        return _execute_reserved(run, prompt=prompt, meta=meta, inputs=inputs, command_runner=command_runner)
    except RunnerError:
        # Every RunnerError raised after the reservation has already written its status.
        raise
    except Exception as exc:
        # The output name is reserved, so never leave it without a status,
        # whatever went wrong. The type name only: messages can carry paths.
        reason = f"harness failed after reserving the output: {type(exc).__name__}"
        if not run.output(".status.json").exists():
            _write_status_stub(run, reason)
        raise RunnerError(reason) from exc


def _execute_reserved(
    run: ReviewRun,
    *,
    prompt: str,
    meta: dict[str, object],
    inputs: dict[str, dict[str, object]],
    command_runner: CommandRunner,
) -> int:
    """Everything after the output name is reserved; see execute()."""
    run.output(".meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    try:
        scratch = Path(tempfile.mkdtemp(prefix="codex-review-"))
    except OSError as exc:
        reason = f"harness could not create its temp directory: {type(exc).__name__}"
        _write_status_stub(run, reason)
        raise RunnerError(reason) from exc
    worktree = scratch / "wt"
    codex_exit: int | None = None
    try:
        _add_worktree(run, worktree, command_runner)
        _run_pytest(run, worktree, scratch, command_runner)
        try:
            codex_exit = _run_codex(run, worktree, prompt, command_runner)
        finally:
            _finalize_raw_outputs(run, worktree=worktree, scratch=scratch)
    except RunnerError as exc:
        _write_status_stub(run, f"harness failed before codex finished: {exc}")
        raise
    except Exception as exc:
        # The output name is already reserved, so record why this attempt
        # stopped instead of leaving a reservation with no status. This also
        # covers errors that are not OSError, such as a decoding error.
        reason = f"harness failed before codex finished: {type(exc).__name__}"
        _write_status_stub(run, reason)
        raise RunnerError(reason) from exc
    finally:
        try:
            removed = command_runner(worktree_remove_argv(worktree), cwd=REPO_ROOT, check=False)
            if removed.returncode != 0:
                print(f"warning: git worktree remove exited {removed.returncode} for {worktree}")
        except OSError as exc:
            print(f"warning: git worktree remove could not run: {type(exc).__name__}")
        shutil.rmtree(scratch, ignore_errors=True)

    try:
        current_head = _git_stdout(["git", "rev-parse", "HEAD"], command_runner).strip()
    except RunnerError as exc:
        _write_status_stub(run, f"could not determine the current head after the run: {exc}")
        return 1
    # The checker and schema are read from disk now, up to the Codex time
    # limit after .meta.json recorded their hashes; only run them if they
    # still match.
    try:
        inputs_after = audit_inputs(command_runner)
    except RunnerError as exc:
        _write_status_stub(run, f"audited inputs changed during the run: {exc}")
        return 1
    if inputs_after != meta["inputs"]:
        changed = sorted(path for path in AUDITED_INPUTS if inputs_after.get(path) != inputs[path])
        _write_status_stub(run, f"audited inputs changed during the run: {changed}")
        return 1
    try:
        checker = command_runner(
            checker_argv(run, exit_code=codex_exit, current_head=current_head),
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            text=True,
            errors="replace",
        )
    except OSError as exc:
        _write_status_stub(run, f"checker could not run: {type(exc).__name__}")
        return 1
    if not (checker.stdout or "").strip():
        _write_status_stub(run, f"checker produced no output (exit {checker.returncode})")
        return 1
    run.output(".status.json").write_text(checker.stdout, encoding="utf-8")
    print(f"status: {run.output('.status.json')}")
    print(checker.stdout, end="")
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
    print(f"(cd {worktree} && {shlex.join(pytest_argv())}) > {shlex.quote(str(run.output('.pytest.txt')))}")
    evidence = shlex.quote(str(run.output(".pytest.txt")))
    print(
        f"# copy {evidence} to {worktree / EVIDENCE_RELPATH} (local paths redacted; refused if the"
        " reviewed tree already has that path; created with O_CREAT|O_EXCL|O_NOFOLLOW)"
    )
    print(
        f"{shlex.join(codex_argv(worktree, run.output('.last.json')))} < prompt"
        f" > {shlex.quote(str(run.output('.jsonl')))}  # timeout {CODEX_TIMEOUT_SECONDS}s in-process, exit 124"
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
    trust = parser.add_mutually_exclusive_group(required=True)
    trust.add_argument(
        "--trusted",
        dest="trusted",
        action="store_true",
        help="Head is from this repository's own branch: run the harness pytest and Codex",
    )
    trust.add_argument(
        "--untrusted",
        dest="trusted",
        action="store_false",
        help="Dependabot or outside-contributor head: refused (Codex PENDING, rely on CI results)",
    )
    parser.add_argument(
        "--allow-stale-head",
        action="store_true",
        help="Run even though --head is not the checkout's HEAD (the result will be assessed stale)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt and commands only")
    return parser


def main(argv: list[str] | None = None) -> int:
    previous_handlers = install_signal_handlers()
    try:
        parser = _build_parser()
        args = parser.parse_args(argv)
        try:
            run = ReviewRun(
                args.head, args.base, args.label, args.attempt, args.pr_url, args.scope, args.phase_dir, args.trusted
            )
        except ValueError as exc:
            parser.error(str(exc))
        if not run.trusted:
            print(f"error: {UNTRUSTED_REFUSAL}")
            return 2
        if not (REPO_ROOT / run.phase_dir).is_dir():
            parser.error(f"phase-dir does not exist: {run.phase_dir}")
        if args.dry_run:
            return dry_run(run)
        try:
            return execute(run, allow_stale_head=args.allow_stale_head)
        except FileExistsError as exc:
            print(f"error: {exc}; use the next attempt number")
            return 2
        except RunnerError as exc:
            print(f"error: {exc}")
            return 2
        except subprocess.CalledProcessError as exc:
            print(f"error: {shlex.join(str(part) for part in exc.cmd[:3])} exited {exc.returncode}")
            return 2
    finally:
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
