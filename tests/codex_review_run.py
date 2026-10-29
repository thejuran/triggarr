"""Reproducible runner for the independent Codex adversarial review pass.

Implements docs/codex-adversarial-review-contract.md, Invocation:

-1. Verifies ``--trusted`` against a boundary the operator cannot simply
   assert: GitHub PR ownership or this machine's own local commit history
   (``verify_trust()``, D-18 SA-01). Refused before anything else runs or
   is written.
0. Refuses to start if the contract, schema, checker or runner has
   uncommitted changes, then saves the exact rendered prompt as
   ``<OUT>.prompt.txt`` and a provenance record (template version, sha256
   of those files, harness HEAD, trust verification) as ``<OUT>.meta.json``.
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
   ``<OUT>.status.json``. If this diff changed the checker, schema, prompt
   or runner itself, also cross-grades the same report with the base
   commit's own checker (materialized from git objects only) and saves it
   as ``<OUT>.base-status.json``; the run is complete only if both agree.

``--trusted`` heads (verified by ``verify_trust()``) are reviewed as
above. ``--untrusted`` (bot or fork PRs) runs a separate inspection-only
review instead (Phase 85.1, D-07): the head is never checked out, written
to disk or executed. Its review input is inert text built purely from git
objects, Codex runs inside a disposable container behind a mandatory,
fail-closed isolation-boundary gate, and grading always uses the checker
from a freshly fetched ``origin/main``, never from the reviewed head or
its base (B13). Until the container checks exist (Plans 85.1-07/08) that
gate always reports "unverified", so every ``--untrusted`` run still ends
INCOMPLETE (exit 3) -- but it is reserved, recorded and graded the same
way a trusted run is, not refused outright.

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
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
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

# The checker and schema a base-commit grader needs to cross-grade a report
# whose own checker/schema changed in the reviewed diff (D-18, checker B13).
GRADER_FILES = (
    "tests/codex_report_status.py",
    ".claude/schemas/codex-review-findings.schema.json",
)

# Owner decision 2026-10-22: only this repository's own branches are trusted.
# Widening TRUSTED_AUTHORS is a sensitive review-machinery change and needs
# its own review.
REPO_SLUG = "thejuran/triggarr"
TRUSTED_AUTHORS = frozenset({"thejuran"})

TEMPLATE_HEADING = "## Fixed prompt (version 6)"
PLACEHOLDERS = frozenset({"PR_URL", "HEAD_SHA", "BASE_SHA", "SCOPE", "TEST_EVIDENCE"})

# The untrusted (bot/fork) head's inspection-only prompt (Phase 85.1, D-07):
# Codex gets no checkout, so the review input is inert text substituted into
# this separate template instead of the trusted TEMPLATE_HEADING above.
INSPECTION_TEMPLATE_HEADING = "## Inspection-only prompt (version 1)"
INSPECTION_PLACEHOLDERS = frozenset(
    {"PR_URL", "HEAD_SHA", "BASE_SHA", "SCOPE", "CI_EVIDENCE", "INPUT_FENCE", "INPUT"}
)

# Per-file and total byte bounds on the inert inspection input (T-85.1-20,
# denial of service): a file over PER_FILE_CONTENT_LIMIT is omitted with a
# note instead of read in full; a total input over MAX_INSPECTION_INPUT_BYTES
# is recorded oversize by the caller rather than raising here.
PER_FILE_CONTENT_LIMIT = 262_144
MAX_INSPECTION_INPUT_BYTES = 1_500_000

# Prefix for the random per-run fence marking the inert input block
# (T-85.1-19, prompt injection): new_input_fence() regenerates until the
# result does not occur anywhere in the input it is fencing.
INPUT_FENCE_PREFIX = "TRIGGARR-INERT-"

CI_READY_CHECK_NAME = "CI ready"

# Every git command that reads the untrusted head's content (diff, ls-tree,
# cat-file) is prefixed with this, so a repository-supplied .gitattributes
# driver never runs during the read (T-85.1-16).
GIT_SAFE_PREFIX = ("git", "-c", "core.attributesFile=/dev/null", "-c", "diff.external=")

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

# D-17 (Phase 85): phase plan files are agent instructions BM executors
# follow, so they are brought back into review scope through a second,
# positive diff -- a git pathspec cannot re-include a path EXCLUDE_PATHSPECS'
# blanket .planning/**/*.md already matches. Must match the fixed prompt.
PLAN_PATHSPECS = (":(glob).planning/**/*-PLAN.md",)

OUTPUT_SUFFIXES = (
    ".prompt.txt",
    ".meta.json",
    ".jsonl",
    ".last.json",
    ".status.json",
    ".pytest.txt",
    ".base-status.json",
    # Inspection-only outputs (Phase 85.1, D-07): CI evidence for the exact
    # head, the trusted-main grader provenance record, and the isolation
    # boundary verdict.
    ".ci-evidence.json",
    ".grader-provenance.json",
    ".boundary.json",
)

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
_PR_URL_RE = re.compile(r"https://github\.com/([^/]+/[^/]+)/pull/([0-9]+)")

# Reflog subjects written by this machine's own commit operations ("commit:",
# "commit (amend):", "commit (merge):", "commit (initial):"). Fetched,
# cherry-picked, rebased or reset-to commits never match this, which is the
# point: author/committer email is never a trust signal, only this.
LOCAL_COMMIT_SUBJECT_RE = re.compile(r"^commit( \((amend|merge|initial)\))?: ")

LOCAL_CHECKPOINT_PR_URL = "none (local checkpoint, not pushed)"

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
    # A TimeoutExpired raised by communicate() carries the partial output as
    # raw bytes even in text mode, so normalize it to the caller's mode
    # before appending the marker (decoded as UTF-8 with replacement, like
    # every other captured output).
    marker = f"\n[drain timed out after {DRAIN_TIMEOUT_SECONDS}s; output truncated]\n"
    if text_mode:
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return (output or "") + marker
    if isinstance(output, str):
        output = output.encode("utf-8")
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
    # trusted; their tests and Codex run locally against the real head
    # (execute()). Dependabot and outside-contributor heads are untrusted:
    # their tests are never run and their code is never checked out, so
    # they get the separate inspection-only review instead (Phase 85.1,
    # D-07) -- still Codex, just never on the head's own machine access.
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


def load_template(contract_text: str | None = None, heading: str = TEMPLATE_HEADING) -> str:
    """Return the fixed prompt: the first fenced block after *heading*."""
    text = contract_text if contract_text is not None else CONTRACT_PATH.read_text(encoding="utf-8")
    after = text[text.index(heading) + len(heading) :]
    match = re.search(r"```[^\n]*\n(.*?)```", after, re.DOTALL)
    if match is None:
        raise ValueError(f"no fenced prompt block after {heading!r}")
    return match.group(1)


def template_version(contract_text: str | None = None) -> str:
    """Return the contract's "Template version: N." number."""
    text = contract_text if contract_text is not None else CONTRACT_PATH.read_text(encoding="utf-8")
    match = re.search(r"^Template version: (\d+)\.", text, re.MULTILINE)
    if match is None:
        raise ValueError("contract has no 'Template version: N.' line")
    return match.group(1)


def inspection_template_version(contract_text: str | None = None) -> str:
    """Return the contract's "Inspection-only template version: N." number."""
    text = contract_text if contract_text is not None else CONTRACT_PATH.read_text(encoding="utf-8")
    match = re.search(r"^Inspection-only template version: (\d+)\.", text, re.MULTILINE)
    if match is None:
        raise ValueError("contract has no 'Inspection-only template version: N.' line")
    return match.group(1)


def render_template(template: str, values: dict[str, str], placeholders: frozenset[str]) -> str:
    """Substitute exactly *placeholders* in one pass.

    Single-pass substitution means a value that itself looks like a
    placeholder is never expanded again.
    """
    keys = set(values)
    if keys != placeholders:
        missing = sorted(placeholders - keys)
        unknown = sorted(keys - placeholders)
        raise ValueError(f"placeholder values mismatch: missing {missing}, unknown {unknown}")
    used = set(_PLACEHOLDER_RE.findall(template))
    if used != placeholders:
        raise ValueError(f"template placeholders {sorted(used)} differ from {sorted(placeholders)}")
    return _PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], template)


def render_prompt(template: str, values: dict[str, str]) -> str:
    """Substitute exactly the documented placeholders in one pass.

    Single-pass substitution means a value that itself looks like a
    placeholder is never expanded again.
    """
    return render_template(template, values, PLACEHOLDERS)


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


def plan_diff_argv(base: str, head: str) -> list[str]:
    """The second, positive diff that brings *-PLAN.md files back into review scope (D-17)."""
    return ["git", "diff", f"{base}..{head}", "--", *PLAN_PATHSPECS]


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


def checker_argv(
    run: ReviewRun, *, exit_code: int | None, current_head: str, review_mode: str = "trusted"
) -> list[str]:
    """Build the checker invocation. *review_mode* is caller-declared (never
    inferred from the report), same discipline as --legacy-v1: "trusted"
    (default) leaves the argv unchanged; "inspection-only" appends
    --review-mode inspection-only for an untrusted head's review (D-07)."""
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
    if review_mode == "inspection-only":
        argv += ["--review-mode", "inspection-only"]
    return argv


def _pytest_env() -> dict[str, str]:
    # The caller's virtualenv belongs to the main checkout; the worktree gets its own.
    return {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}


def _require_base_on_main(run: ReviewRun, command_runner: CommandRunner) -> None:
    """Require --base to already be on this checkout's origin/main.

    Applies to both the PR and local-checkpoint forms, so the base-commit
    grader Task 2 may materialize (``materialize_grader(grader_ref=run.base,
    ...)``) is always code that already landed on this repository's main,
    never a PR-supplied base (checker B13). No fetch happens here; a stale
    local origin/main is the operator's to refresh.
    """
    try:
        result = command_runner(
            ["git", "merge-base", "--is-ancestor", run.base, "refs/remotes/origin/main"],
            cwd=HARNESS_ROOT,
            check=False,
        )
    except OSError as exc:
        raise RunnerError(f"could not verify trust: git merge-base could not run ({type(exc).__name__})") from exc
    if result.returncode != 0:
        raise RunnerError(
            f"base is not on origin/main: {run.base[:12]} is not an ancestor of refs/remotes/origin/main;"
            " run `git fetch origin main` and retry"
        )


_GH_PR_VIEW_FIELDS = "author,isCrossRepository,headRefOid,baseRefOid"

# The inspection-only PR precondition check (inspect_untrusted_pr) also needs
# the PR's open/closed state, which the trusted path's check never needs
# (D-09 open-PR rule).
_GH_PR_VIEW_FIELDS_INSPECTION = "author,isCrossRepository,headRefOid,baseRefOid,state"


def _pr_merge_base(pr_base: str, head: str, command_runner: CommandRunner) -> str:
    """Return ``git merge-base <pr_base> <head>``, failing closed on any error."""
    try:
        result = command_runner(
            ["git", "merge-base", pr_base, head],
            cwd=HARNESS_ROOT,
            stdout=subprocess.PIPE,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RunnerError(f"could not verify trust: git merge-base could not run ({type(exc).__name__})") from exc
    merge_base = (result.stdout or "").strip()
    if result.returncode != 0 or not _SHA_RE.fullmatch(merge_base):
        raise RunnerError(
            f"could not verify trust: no merge-base of PR base {pr_base[:12]} and head {head[:12]};"
            " run `git fetch origin` and retry"
        )
    return merge_base


def _verify_trust_pr(run: ReviewRun, command_runner: CommandRunner, match: re.Match[str]) -> dict[str, object]:
    slug, number = match.group(1), match.group(2)
    if slug != REPO_SLUG:
        raise RunnerError(f"PR URL is for a different repository: {slug!r} is not this repository ({REPO_SLUG})")
    try:
        result = command_runner(
            ["gh", "pr", "view", number, "--repo", REPO_SLUG, "--json", _GH_PR_VIEW_FIELDS],
            stdout=subprocess.PIPE,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RunnerError(f"could not verify trust: gh pr view could not run ({type(exc).__name__})") from exc
    if result.returncode != 0:
        raise RunnerError(f"could not verify trust: gh pr view exited {result.returncode}")
    try:
        data = json.loads(result.stdout or "")
    except ValueError as exc:
        raise RunnerError(
            f"could not verify trust: gh pr view returned unparseable JSON ({type(exc).__name__})"
        ) from exc
    author = data.get("author") or {}
    login = author.get("login", "")
    is_bot = bool(author.get("is_bot")) or login.endswith("[bot]")
    if data.get("isCrossRepository"):
        raise RunnerError(f"PR #{number} is cross-repository (fork): not a trusted origin for local test execution")
    if is_bot:
        raise RunnerError(
            f"not a trusted origin for local test execution: author {login} is a bot; use --untrusted for this head"
        )
    if login not in TRUSTED_AUTHORS:
        raise RunnerError(f"author {login} is not in TRUSTED_AUTHORS")
    if data.get("headRefOid") != run.head:
        raise RunnerError(f"PR head is {data.get('headRefOid')}, not --head {run.head}")
    pr_base = data.get("baseRefOid")
    if not isinstance(pr_base, str) or not _SHA_RE.fullmatch(pr_base):
        raise RunnerError(f"could not verify trust: gh pr view returned no valid baseRefOid ({pr_base!r})")
    # The reviewed base is the merge-base of the PR base and the head, the same
    # rule acceptance-readiness.cjs applies to meta.base. It equals the PR base
    # while the branch is up to date with it, and stays the branch's fork point
    # after main moves on, so the base..head diff never includes main-only
    # changes in reverse.
    reviewed_base = _pr_merge_base(pr_base, run.head, command_runner)
    if reviewed_base != run.base:
        raise RunnerError(
            f"--base {run.base} is not the reviewed base: the merge-base of PR base {pr_base} and head"
            f" {run.head} is {reviewed_base}; pass that merge-base as --base"
        )
    _require_base_on_main(run, command_runner)
    return {"method": "gh pr view", "pr_number": int(number), "author": login, "commits_checked": None}


def _verify_trust_local(run: ReviewRun, command_runner: CommandRunner) -> dict[str, object]:
    try:
        ancestor = command_runner(
            ["git", "merge-base", "--is-ancestor", run.base, run.head], cwd=HARNESS_ROOT, check=False
        )
    except OSError as exc:
        raise RunnerError(f"could not verify trust: git merge-base could not run ({type(exc).__name__})") from exc
    if ancestor.returncode != 0:
        raise RunnerError(f"base is not an ancestor of head: {run.base[:12]} is not an ancestor of {run.head[:12]}")

    try:
        contains = command_runner(
            ["git", "for-each-ref", "--contains", run.head, "--format=%(refname)", "refs/heads/"],
            cwd=HARNESS_ROOT,
            stdout=subprocess.PIPE,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RunnerError(f"could not verify trust: git for-each-ref could not run ({type(exc).__name__})") from exc
    if contains.returncode != 0 or not (contains.stdout or "").strip():
        raise RunnerError(f"head {run.head[:12]} is not on a local branch")

    rev_list_output = _git_stdout(["git", "rev-list", f"{run.base}..{run.head}"], command_runner)
    commits = [line.strip() for line in rev_list_output.splitlines() if line.strip()]

    try:
        all_branches = command_runner(
            ["git", "for-each-ref", "--format=%(refname)", "refs/heads/"],
            cwd=HARNESS_ROOT,
            stdout=subprocess.PIPE,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RunnerError(f"could not verify trust: git for-each-ref could not run ({type(exc).__name__})") from exc
    refs = ["HEAD", *(line.strip() for line in (all_branches.stdout or "").splitlines() if line.strip())]

    committed: set[str] = set()
    for ref in refs:
        try:
            reflog = command_runner(
                ["git", "reflog", "show", "--format=%H%x09%gs", ref],
                cwd=HARNESS_ROOT,
                stdout=subprocess.PIPE,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise RunnerError(f"could not verify trust: git reflog show could not run ({type(exc).__name__})") from exc
        if reflog.returncode != 0:
            continue  # a ref with no reflog contributes nothing
        for line in (reflog.stdout or "").splitlines():
            if "\t" not in line:
                continue
            sha, subject = line.split("\t", 1)
            if LOCAL_COMMIT_SUBJECT_RE.match(subject):
                committed.add(sha)

    missing = [sha for sha in commits if sha not in committed]
    if missing:
        raise RunnerError(
            f"local checkpoint origin not established: {missing[0][:12]} was not committed on this machine"
        )

    _require_base_on_main(run, command_runner)
    return {"method": "local reflog", "pr_number": None, "author": None, "commits_checked": len(commits)}


def verify_trust(run: ReviewRun, command_runner: CommandRunner) -> dict[str, object]:
    """Verify --trusted against a boundary the operator cannot simply assert (D-18 SA-01).

    A PR is trusted only if GitHub itself reports it as same-repository,
    non-bot, authored by someone in TRUSTED_AUTHORS, with the given --head,
    and --base is the merge-base of the PR base and that head (the reviewed
    base acceptance readiness requires). A local checkpoint is trusted only if this machine's own
    commit operations created every commit in scope: fetched, cherry-picked,
    rebased or reset-to commits fail closed, and the remedy is to push and
    review by PR URL instead (owner-authored PRs pass the PR check).
    Self-declared signals -- local branch membership, author/committer
    email, the operator's own flag -- never establish trust on their own.
    A bot or fork head is never trusted; until Phase 85.1 it gets CI plus an
    owner-approved fallback review (D-16). Both forms also require --base to
    already be an ancestor of (or equal to) refs/remotes/origin/main, so the
    base-commit grader (Task 2) never executes a PR-supplied base.
    """
    if run.pr_url == LOCAL_CHECKPOINT_PR_URL:
        return _verify_trust_local(run, command_runner)
    match = _PR_URL_RE.fullmatch(run.pr_url)
    if match is None:
        raise RunnerError(f"unrecognized --pr-url form: {run.pr_url!r}")
    return _verify_trust_pr(run, command_runner, match)


# --- Inspection-only review for untrusted (bot/fork) heads (Phase 85.1, D-07) -----
#
# An untrusted head is never checked out, never written to disk and never
# executed. These functions build the review input purely from git objects
# read into memory, confirm CI evidence for exactly that head, render the
# inspection-only prompt, and establish that the grader is a freshly fetched
# origin/main before any grader code runs (B13, D-02). No orchestration here
# -- Plan 85.1-06 wires these into execute().


def _git_bytes(argv: list[str], command_runner: CommandRunner) -> bytes:
    """Like _git_stdout, but returns raw bytes (no decoding) for blob content.

    The caller checks for a NUL byte (binary detection) before any decoding
    happens; decoding with errors="replace" happens only after that check.
    """
    try:
        proc = command_runner(argv, cwd=HARNESS_ROOT, stdout=subprocess.PIPE, check=False)
    except OSError as exc:
        raise RunnerError(f"{shlex.join(argv[:3])} could not run: {type(exc).__name__}") from exc
    if proc.returncode != 0:
        raise RunnerError(f"{shlex.join(argv[:3])} exited {proc.returncode}")
    output = proc.stdout or b""
    return output.encode("utf-8") if isinstance(output, str) else output


def flatten_pages(text: str, kind: str) -> list[dict]:
    """Flatten a `gh api --paginate --slurp` array of pages into one list.

    *text* must parse as a JSON array; every page must be a dict with a list
    at *kind*. Anything else -- non-array JSON, a page missing the key, or
    unparseable text -- fails closed (T-85.1-18): a missed or malformed page
    must never be silently treated as "no evidence" or "ignored".
    """
    try:
        pages = json.loads(text)
    except ValueError as exc:
        raise RunnerError(f"could not read GitHub check runs: unparseable JSON ({type(exc).__name__})") from exc
    if not isinstance(pages, list):
        raise RunnerError("could not read GitHub check runs: expected a --slurp array of pages")
    items: list[dict] = []
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get(kind), list):
            raise RunnerError(f"could not read GitHub check runs: a page is missing its {kind!r} list")
        items.extend(page[kind])
    return items


_CHECK_RUN_FIELDS = ("id", "name", "head_sha", "status", "conclusion", "html_url")


def ci_evidence(run: ReviewRun, command_runner: CommandRunner) -> dict[str, object]:
    """Return the GitHub check-run evidence for exactly --head, requiring a successful CI ready.

    Only the latest (highest id) "CI ready" check run for this exact head
    counts (T-85.1-18): a successful run for another head, or an older
    successful run superseded by a later failure, is never accepted.
    """
    try:
        proc = command_runner(
            ["gh", "api", f"repos/{REPO_SLUG}/commits/{run.head}/check-runs", "--paginate", "--slurp"],
            cwd=HARNESS_ROOT,
            stdout=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise RunnerError(f"could not read GitHub check runs: gh api could not run ({type(exc).__name__})") from exc
    if proc.returncode != 0:
        raise RunnerError(f"could not read GitHub check runs: gh api exited {proc.returncode}")
    runs = flatten_pages(proc.stdout or "", "check_runs")
    for_head = [
        {field: run_item.get(field) for field in _CHECK_RUN_FIELDS}
        for run_item in runs
        if isinstance(run_item, dict) and run_item.get("head_sha") == run.head
    ]
    ci_ready_runs = [item for item in for_head if item.get("name") == CI_READY_CHECK_NAME]
    latest_ci_ready = max(ci_ready_runs, key=lambda item: item.get("id") or 0, default=None)
    if (
        latest_ci_ready is None
        or latest_ci_ready.get("status") != "completed"
        or latest_ci_ready.get("conclusion") != "success"
    ):
        raise RunnerError("no successful CI ready check run for this exact head")
    return {"check_runs": for_head, "ci_ready": latest_ci_ready}


def inspect_untrusted_pr(run: ReviewRun, command_runner: CommandRunner) -> dict[str, object]:
    """Verify the inspection-only preconditions for an untrusted PR head.

    An untrusted head needs CI evidence bound to the exact head, so an
    unpushed (local checkpoint) head is refused outright. A closed or
    merged PR is never reviewed (D-09): only an open PR whose fetched head
    matches --head and whose reviewed base is the merge-base of its base and
    head may proceed. Unlike verify_trust(), a bot author and a
    cross-repository fork are both accepted here -- that is exactly the kind
    of head this path exists for.
    """
    if run.pr_url == LOCAL_CHECKPOINT_PR_URL:
        raise RunnerError("inspection-only review needs CI evidence for the exact head; an unpushed head has none")
    match = _PR_URL_RE.fullmatch(run.pr_url)
    if match is None:
        raise RunnerError(f"unrecognized --pr-url form: {run.pr_url!r}")
    slug, number = match.group(1), match.group(2)
    if slug != REPO_SLUG:
        raise RunnerError(f"only {REPO_SLUG} PRs are reviewed inspection-only: {slug!r} is a different repository")
    try:
        result = command_runner(
            ["gh", "pr", "view", number, "--repo", REPO_SLUG, "--json", _GH_PR_VIEW_FIELDS_INSPECTION],
            stdout=subprocess.PIPE,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RunnerError(f"could not verify the PR: gh pr view could not run ({type(exc).__name__})") from exc
    if result.returncode != 0:
        raise RunnerError(f"could not verify the PR: gh pr view exited {result.returncode}")
    try:
        data = json.loads(result.stdout or "")
    except ValueError as exc:
        raise RunnerError(
            f"could not verify the PR: gh pr view returned unparseable JSON ({type(exc).__name__})"
        ) from exc
    if data.get("state") in ("CLOSED", "MERGED"):
        raise RunnerError(f"PR is not open: PR #{number} state is {data.get('state')}")
    if data.get("headRefOid") != run.head:
        raise RunnerError(f"PR head is {data.get('headRefOid')}, not --head {run.head}")
    try:
        fetched = command_runner(
            ["git", "fetch", "--no-tags", "origin", f"pull/{number}/head"], cwd=HARNESS_ROOT, check=False
        )
    except OSError as exc:
        raise RunnerError(f"could not fetch the PR head: git fetch could not run ({type(exc).__name__})") from exc
    if fetched.returncode != 0:
        raise RunnerError(f"could not fetch the PR head: git fetch exited {fetched.returncode}")
    try:
        verified = command_runner(
            ["git", "rev-parse", "--verify", "FETCH_HEAD^{commit}"],
            cwd=HARNESS_ROOT,
            stdout=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise RunnerError(
            f"could not verify the fetched head: git rev-parse could not run ({type(exc).__name__})"
        ) from exc
    fetched_head = (verified.stdout or "").strip()
    if verified.returncode != 0 or fetched_head != run.head:
        raise RunnerError(f"fetched head does not match --head {run.head}: FETCH_HEAD resolved to {fetched_head!r}")
    pr_base = data.get("baseRefOid")
    if not isinstance(pr_base, str) or not _SHA_RE.fullmatch(pr_base):
        raise RunnerError(f"could not verify the PR: gh pr view returned no valid baseRefOid ({pr_base!r})")
    merge_base = _pr_merge_base(pr_base, run.head, command_runner)
    if merge_base != run.base:
        raise RunnerError(
            f"--base must be the merge-base of PR base {pr_base} and head {run.head}, which is {merge_base},"
            f" not {run.base}"
        )
    author = data.get("author") or {}
    return {
        "number": int(number),
        "author_login": author.get("login", ""),
        "is_cross_repository": bool(data.get("isCrossRepository")),
        "head_ref_oid": data.get("headRefOid"),
        "base_ref_oid": pr_base,
        "merge_base": merge_base,
    }


def _ls_tree_entry(run: ReviewRun, path: str, command_runner: CommandRunner) -> str | None:
    """Return the ls-tree mode for *path* at --head, or None if absent at head."""
    output = _git_stdout([*GIT_SAFE_PREFIX, "ls-tree", "-z", run.head, "--", path], command_runner)
    if not output.strip():
        return None
    # "<mode> <type> <sha>\t<path>\0" -- only the leading mode is needed.
    return output.split(maxsplit=1)[0]


def _inspected_file_note(run: ReviewRun, path: str, mode: str, command_runner: CommandRunner) -> str:
    """Return the text (or a replacement note) for one changed path's head content."""
    if mode == "120000":
        return "symlink at head (target not followed)"
    if mode == "160000":
        return "submodule pointer, not inspected"
    if mode not in ("100644", "100755"):
        return f"content omitted: unsupported mode {mode}"
    content = _git_bytes([*GIT_SAFE_PREFIX, "cat-file", "blob", f"{run.head}:{path}"], command_runner)
    if len(content) > PER_FILE_CONTENT_LIMIT:
        return f"content omitted: {len(content)} bytes exceeds PER_FILE_CONTENT_LIMIT; review the diff hunks"
    if b"\x00" in content:
        return "content omitted: binary"
    return content.decode("utf-8", errors="replace")


def _changed_paths(run: ReviewRun, pathspecs: tuple[str, ...], command_runner: CommandRunner) -> list[str]:
    output = _git_stdout(
        [
            *GIT_SAFE_PREFIX,
            "diff",
            "--name-status",
            "-z",
            "--no-renames",
            "--no-textconv",
            "--no-ext-diff",
            "--no-color",
            f"{run.base}..{run.head}",
            "--",
            *pathspecs,
        ],
        command_runner,
    )
    fields = [field for field in output.split("\0") if field]
    # "<status>\0<path>\0<status>\0<path>\0..."; every even index is a status code.
    return [fields[i] for i in range(1, len(fields), 2)]


def build_inspection_input(run: ReviewRun, command_runner: CommandRunner) -> tuple[str, dict[str, object]]:
    """Build the inert text input for an untrusted head's inspection-only review.

    Every byte of the untrusted head reaches this function only as git
    objects read into memory via *command_runner* -- no checkout, worktree,
    archive, clone or restore is ever issued, and nothing from the head is
    ever written to disk. Oversize input is reported in *stats*, not raised:
    the caller decides how to record that (INCOMPLETE), not this function.
    """
    diff_flags = ("--no-textconv", "--no-ext-diff", "--no-color")
    full_diff = _git_stdout(
        [*GIT_SAFE_PREFIX, "diff", f"{run.base}..{run.head}", *diff_flags, "--", ".", *EXCLUDE_PATHSPECS],
        command_runner,
    )
    plan_diff = _git_stdout(
        [*GIT_SAFE_PREFIX, "diff", f"{run.base}..{run.head}", *diff_flags, "--", *PLAN_PATHSPECS],
        command_runner,
    )
    full_scope_paths = _changed_paths(run, (".", *EXCLUDE_PATHSPECS), command_runner)
    plan_scope_paths = _changed_paths(run, PLAN_PATHSPECS, command_runner)
    paths: list[str] = []
    for path in [*full_scope_paths, *plan_scope_paths]:
        if path not in paths:
            paths.append(path)

    files_included = 0
    files_omitted = 0
    file_sections: list[str] = []
    for path in paths:
        mode = _ls_tree_entry(run, path, command_runner)
        if mode is None:
            note = "deleted at head"
            files_omitted += 1
        else:
            note = _inspected_file_note(run, path, mode, command_runner)
            if note.startswith("content omitted") or note.startswith("symlink") or note.startswith("submodule"):
                files_omitted += 1
            else:
                files_included += 1
        file_sections.append(f"#### {path}\n{note}")

    text = (
        "### In-scope diff\n"
        f"{full_diff}\n\n"
        "### Phase-plan diff\n"
        f"{plan_diff}\n\n"
        "### Changed files at head\n" + "\n\n".join(file_sections)
    )
    total_bytes = len(text.encode("utf-8"))
    stats = {
        "bytes": total_bytes,
        "files_included": files_included,
        "files_omitted": files_omitted,
        "oversize": total_bytes > MAX_INSPECTION_INPUT_BYTES,
    }
    return text, stats


def new_input_fence(input_text: str) -> str:
    """Return a fresh random fence that does not occur anywhere in *input_text*.

    Regenerated until the random suffix does not collide, so an attacker who
    could predict (or got lucky guessing) the marker can never use it to
    forge the end of the fenced block (T-85.1-19).
    """
    while True:
        fence = INPUT_FENCE_PREFIX + secrets.token_hex(16)
        if fence not in input_text:
            return fence


def inspection_prompt_values(run: ReviewRun, *, ci_evidence_text: str, input_text: str, fence: str) -> dict[str, str]:
    return {
        "PR_URL": run.pr_url,
        "HEAD_SHA": run.head,
        "BASE_SHA": run.base,
        "SCOPE": run.scope,
        "CI_EVIDENCE": ci_evidence_text,
        "INPUT_FENCE": fence,
        "INPUT": input_text,
    }


def render_inspection_prompt(run: ReviewRun, *, ci_evidence_text: str, input_text: str, fence: str) -> str:
    """Render the inspection-only prompt, substituting all seven placeholders in one pass.

    Single-pass substitution (render_template) means text inside *input_text*
    that looks like a placeholder (e.g. literal "{{HEAD_SHA}}") is never
    expanded -- it stays exactly as it appears in the untrusted head.
    """
    template = load_template(heading=INSPECTION_TEMPLATE_HEADING)
    values = inspection_prompt_values(run, ci_evidence_text=ci_evidence_text, input_text=input_text, fence=fence)
    return render_template(template, values, INSPECTION_PLACEHOLDERS)


# --- Trusted-main grader provenance for untrusted reviews (B13, D-02) --------

TRUSTED_MAIN_REF = "refs/remotes/origin/main"
_PROVENANCE_PREFIX = "base grader provenance not established"


def establish_trusted_main(run: ReviewRun, command_runner: CommandRunner) -> dict[str, object]:
    """Establish that an untrusted run's grader is a freshly fetched origin/main, and only that.

    This is the only provenance rule for untrusted runs: it never reads,
    materializes or runs anything from --base (B13). Requiring the harness
    checkout's own HEAD to equal the freshly fetched origin/main means the
    checker, the prompt contract and this runner itself are all main's too
    -- there is no bootstrap exception (D-02). _require_base_on_main (the
    trusted path's own ancestor check) is unrelated and unaffected.
    """
    try:
        fetched = command_runner(
            ["git", "fetch", "--no-tags", "origin", f"+refs/heads/main:{TRUSTED_MAIN_REF}"],
            cwd=HARNESS_ROOT,
            check=False,
        )
    except OSError as exc:
        raise RunnerError(f"{_PROVENANCE_PREFIX}: could not fetch origin main ({type(exc).__name__})") from exc
    if fetched.returncode != 0:
        raise RunnerError(f"{_PROVENANCE_PREFIX}: could not fetch origin main")

    try:
        resolved = command_runner(
            ["git", "rev-parse", "--verify", f"{TRUSTED_MAIN_REF}^{{commit}}"],
            cwd=HARNESS_ROOT,
            stdout=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise RunnerError(f"{_PROVENANCE_PREFIX}: could not resolve origin/main ({type(exc).__name__})") from exc
    main_sha = (resolved.stdout or "").strip()
    if resolved.returncode != 0 or not _SHA_RE.fullmatch(main_sha):
        raise RunnerError(f"{_PROVENANCE_PREFIX}: could not resolve origin/main")

    try:
        harness = command_runner(
            ["git", "rev-parse", "HEAD"],
            cwd=HARNESS_ROOT,
            stdout=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise RunnerError(f"{_PROVENANCE_PREFIX}: could not resolve the harness HEAD ({type(exc).__name__})") from exc
    harness_head = (harness.stdout or "").strip()
    if harness.returncode != 0 or not _SHA_RE.fullmatch(harness_head):
        raise RunnerError(f"{_PROVENANCE_PREFIX}: could not resolve the harness HEAD")
    if harness_head != main_sha:
        raise RunnerError(
            f"{_PROVENANCE_PREFIX}: the harness checkout is {harness_head[:12]}, not the freshly fetched"
            f" origin/main {main_sha[:12]}; run from a checkout of origin/main (D-02)"
        )

    try:
        audit_inputs(command_runner)
    except RunnerError as exc:
        raise RunnerError(f"{_PROVENANCE_PREFIX}: audited inputs have uncommitted changes") from exc

    try:
        ancestor = command_runner(
            ["git", "merge-base", "--is-ancestor", run.base, main_sha], cwd=HARNESS_ROOT, check=False
        )
    except OSError as exc:
        raise RunnerError(f"{_PROVENANCE_PREFIX}: git merge-base could not run ({type(exc).__name__})") from exc
    if ancestor.returncode == 1:
        raise RunnerError(f"{_PROVENANCE_PREFIX}: {run.base[:12]} is not an ancestor of origin/main")
    if ancestor.returncode != 0:
        raise RunnerError(f"{_PROVENANCE_PREFIX}: git merge-base exited {ancestor.returncode}")

    return {
        "main_ref": TRUSTED_MAIN_REF,
        "main_sha": main_sha,
        "harness_head": harness_head,
        "base": run.base,
        "base_on_main": True,
        "grader_ref": main_sha,
        "grader_source": "trusted-origin-main",
    }


def trusted_main_grader_supports_mode(grader_path: Path, command_runner: CommandRunner) -> bool:
    """True only if the checker materialized from MAIN_SHA already supports --review-mode inspection-only.

    Never raises: an older main checker, a non-zero exit or any OSError is
    reported as False, so the caller can report "older main checker" in
    plain words instead of crashing. Runs the checker's --help only --
    trusted-main Python, never anything from the reviewed head or --base.
    """
    try:
        proc = command_runner(
            [sys.executable, str(grader_path), "--help"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
        )
    except OSError:
        return False
    if proc.returncode != 0:
        return False
    stdout = proc.stdout or ""
    return "--review-mode" in stdout and "inspection-only" in stdout


# --- Isolation boundary and the only Codex launch seam for untrusted heads ---
# (Phase 85.1, B04-R3). The inner codex invocation, the event-stream audit,
# the mandatory boundary gate and the launch seam are each fixed, tested
# contracts before the container exists: this plan's verify_isolation_boundary
# always returns "unverified" and run_untrusted_codex always refuses, so every
# untrusted run still ends INCOMPLETE. Plans 85.1-07/08 replace only the
# bodies below the already-tested gate/seam boundary.

# The schema path as it exists inside the review container (read-only mount,
# Plan 85.1-07), distinct from SCHEMA_PATH (the harness checkout's own copy).
SCHEMA_IN_CONTAINER = "/schema/codex-review-findings.schema.json"

# Codex features disabled inside the review container (defense in depth --
# the guarantee is the verified container boundary, not this list). Built
# from `codex features list` on this machine (codex-cli 0.153.4); every
# entry below was confirmed present there. Extending this tuple is a
# sensitive review-machinery change and needs its own review.
DISABLED_FEATURES: tuple[str, ...] = (
    "shell_tool",  # the model's own command-execution tool
    "unified_exec",  # the unified exec/pty tool
    "code_mode_host",  # code-mode sandboxed code execution
    "browser_use",  # built-in browser automation
    "browser_use_external",  # browser automation against an external browser
    "browser_use_full_cdp_access",  # full Chrome DevTools Protocol access
    "computer_use",  # computer-use (mouse/keyboard) tool
    "in_app_browser",  # the in-app browser surface
    "apps",  # third-party app integrations
    "plugins",  # plugin loading
    "remote_plugin",  # remote plugin loading
    "plugin_sharing",  # plugin sharing/distribution
    "view_image",  # reading image files from disk
    "image_generation",  # image generation
    "sleep_tool",  # the sleep/wait tool
    "tool_suggest",  # tool-use suggestions (reduces incentive to reach for a tool)
    "skill_mcp_dependency_install",  # installing skill/MCP dependencies
    "tool_call_mcp_elicitation",  # MCP elicitation during a tool call
    "hooks",  # user/project hook execution
    "multi_agent",  # spawning sub-agents
    "multi_agent_v2",  # spawning sub-agents (v2)
    "workspace_dependencies",  # installing workspace dependencies
)

# Event-stream audit allowlists (T-85.1-22): any item type outside
# ALLOWED_ITEM_TYPES or top-level event type outside ALLOWED_EVENT_TYPES
# means Codex reached for something other than reading and reasoning about
# the inert input -- itself the violation, whatever the checker's report
# claims. Extending either requires a justified non-tool type actually
# observed in a real Codex run, recorded in the plan's SUMMARY, never added
# speculatively.
ALLOWED_ITEM_TYPES = frozenset({"agent_message", "reasoning"})
ALLOWED_EVENT_TYPES = frozenset(
    {"thread.started", "turn.started", "turn.completed", "item.started", "item.updated", "item.completed"}
)


def inspection_codex_argv(cwd: str = "/work", last_json: str = "/out/last.json") -> list[str]:
    """The inner ``codex exec`` command run inside the disposable review container.

    Read-only and ephemeral, with every feature in DISABLED_FEATURES turned
    off. Never writable: no extra writable directory is granted, no
    ``workspace-write`` or ``danger-full-access`` sandbox, and no
    ``--dangerously-*`` flag.
    """
    argv = [
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
        cwd,
    ]
    for feature in DISABLED_FEATURES:
        argv += ["--disable", feature]
    argv += ["--output-schema", SCHEMA_IN_CONTAINER, "--json", "-o", last_json, "-"]
    return argv


def audit_event_types(path: Path) -> list[str]:
    """Audit a Codex event stream against ALLOWED_ITEM_TYPES/ALLOWED_EVENT_TYPES.

    Fails closed: a missing file is itself a reason (never silently
    "clean"), and any item type or event type outside the allowlists is a
    reason, whatever the checker's report says (T-85.1-22). An unparseable
    line raises RunnerError rather than being skipped, since a corrupted
    stream cannot be audited at all.
    """
    if not path.exists():
        return ["no Codex event stream recorded"]
    reasons: list[str] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError as exc:
            raise RunnerError("could not audit Codex event stream") from exc
        if not isinstance(event, dict):
            raise RunnerError("could not audit Codex event stream")
        event_type = event.get("type")
        if event_type not in ALLOWED_EVENT_TYPES:
            reasons.append(f"unexpected Codex event: {event_type}")
            continue
        if event_type == "item.completed":
            item = event.get("item")
            item_type = item.get("type") if isinstance(item, dict) else None
            if item_type not in ALLOWED_ITEM_TYPES:
                reasons.append(f"inspection-only review used a tool: {item_type}")
    return reasons


def verify_isolation_boundary(
    run: ReviewRun, command_runner: CommandRunner, *, scratch: Path, inner_argv: list[str]
) -> dict[str, object]:
    """The mandatory precondition before any untrusted Codex launch (B04-R3).

    Must never return "verified" without performing every deterministic
    container check on that call -- no cache, no override flag. This
    plan's body always returns "unverified": Plan 85.1-07 replaces it with
    the real ``docker inspect``-based checks against a created container.
    Issues no command of any kind.
    """
    return {
        "boundary_version": 1,
        "verdict": "unverified",
        "reasons": ["deterministic container checks are not available in this build"],
        "checked_at": datetime.now(UTC).isoformat(),
        "head": run.head,
        "label": run.label,
        "attempt": run.attempt,
    }


def run_untrusted_codex(
    run: ReviewRun,
    *,
    inner_argv: list[str],
    prompt: str,
    boundary: dict[str, object],
    command_runner: CommandRunner,
) -> tuple[int, list[str]]:
    """The only seam through which an untrusted head may reach Codex (B04-R3).

    The host must never run ``codex`` for an untrusted head outside this
    function. A non-"verified" boundary is refused outright. Plan 85.1-08
    replaces the body below the guard with the real disposable-container
    launch (``docker create``/``docker start``); until then every call --
    verified boundary or not -- raises the same refusal, so an untrusted
    run can never reach Codex in this build. The disabled features in
    *inner_argv* are defense in depth, not the guarantee: the guarantee is
    the verified container boundary itself.
    """
    if boundary.get("verdict") != "verified":
        raise RunnerError("untrusted Codex launch requires a verified container boundary")
    raise RunnerError("untrusted Codex launch requires a verified container boundary")


# --- Review container configuration and deterministic verification --------
# (Phase 85.1, B04-R3, B16, B17). The exact `docker create` invocation for
# both the review container and the in-container canary check, the
# host-exposure rule shared by both, and the two deterministic checks that
# prove the running configuration matches: a static `docker inspect`
# comparison (verify_container_config) and a parse of the canary script's
# own report from inside a container built by the same builder
# (parse_canary_check). No Docker daemon is called by any function below
# -- Plan 85.1-08 is the only place that actually creates, inspects or
# starts a container.

# Must match ARG CODEX_VERSION in docker/codex-review/Dockerfile (asserted
# by test_review_image_version_parity in tests/test_codex_review_image.py).
# Deliberately decoupled from the host's own installed Codex version, so a
# host-side Codex update can never silently change which Codex build
# reviews an untrusted head.
REVIEW_CODEX_VERSION = "0.153.4"
REVIEW_IMAGE_REPO = "triggarr-codex-review"
REVIEW_IMAGE_REF = f"{REVIEW_IMAGE_REPO}:{REVIEW_CODEX_VERSION}"
REVIEW_IMAGE_LABEL = "org.triggarr.codex-review"
REVIEW_IMAGE_BUILD_ARGV = [
    "docker",
    "build",
    "-f",
    "docker/codex-review/Dockerfile",
    "-t",
    REVIEW_IMAGE_REF,
    "docker/codex-review",
]

CONTAINER_USER = "10001:10001"
CONTAINER_TMPFS = {
    "/work": "rw,size=64m,mode=0700,uid=10001,gid=10001",
    "/tmp": "rw,size=64m,mode=1777",
}

# The canary script run inside a container built by the same builder as the
# review container (B04-R3). Invoked as
# `docker create --entrypoint /bin/sh <options> <image> -c CANARY_CHECK_SCRIPT canary <path>...`,
# which Docker runs as `sh -c "$CANARY_CHECK_SCRIPT" canary <path>...`: "canary"
# becomes $0 (not part of "$@"), so only the path arguments are tested. Never
# prints an environment variable's value, only its name.
CANARY_CHECK_SCRIPT = r'''for p in "$@"; do
  if [ -e "$p" ] || [ -L "$p" ]; then
    echo "present $p"
  else
    echo "absent $p"
  fi
done
echo "work-entries $(ls -A /work | wc -l | tr -d ' ')"
for n in $(ls -A /codex-home); do
  echo "codex-home-entry $n"
done
echo "schema-sha256 $(sha256sum /schema/codex-review-findings.schema.json | cut -d' ' -f1)"
env | sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' | while IFS= read -r n; do
  echo "env $n"
done
echo "canary-done"
'''


def _container_options(codex_home_dir: Path, out_dir: Path, schema_dir: Path) -> list[str]:
    """The `docker create` options shared by the review container and the canary check.

    Every value here is fixed in code; the only variables are the three
    per-run temp directories the harness itself created (PC-03). No
    `-v`/`--volume`, `--privileged`, host namespace, `--device`,
    `-p`/`--publish`, Docker socket or `--env-file` ever appears.
    """
    return [
        "-i",
        "--read-only",
        "--tmpfs",
        f"/work:{CONTAINER_TMPFS['/work']}",
        "--tmpfs",
        f"/tmp:{CONTAINER_TMPFS['/tmp']}",
        "--user",
        CONTAINER_USER,
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "256",
        "--memory",
        "2g",
        "--network",
        "bridge",
        "--mount",
        f"type=bind,src={codex_home_dir},dst=/codex-home",
        "--mount",
        f"type=bind,src={out_dir},dst=/out",
        "--mount",
        f"type=bind,src={schema_dir},dst=/schema,readonly",
        "-e",
        "CODEX_HOME=/codex-home",
        "-w",
        "/work",
    ]


def container_create_argv(
    image_ref: str, *, codex_home_dir: Path, out_dir: Path, schema_dir: Path, inner_argv: list[str]
) -> list[str]:
    """The exact `docker create` invocation for the review container (B04-R3).

    Relies on the image's own `ENTRYPOINT ["codex"]`; *inner_argv* is the
    inner `codex exec ...` command with its leading "codex" element
    dropped, since the entrypoint already supplies it.
    """
    return [
        "docker",
        "create",
        *_container_options(codex_home_dir, out_dir, schema_dir),
        image_ref,
        *inner_argv[1:],
    ]


def container_check_argv(
    image_ref: str,
    codex_home_dir: Path,
    out_dir: Path,
    schema_dir: Path,
    *,
    canary_paths: list[str],
) -> list[str]:
    """The exact `docker create` invocation for the in-container canary check.

    Uses the same option list as the review container
    (_container_options), overriding only the entrypoint to run
    CANARY_CHECK_SCRIPT. Always `docker create`, never `docker run` and
    never `--rm`: Plan 85.1-08 owns the canary's `docker start` and
    confirmed `docker rm` removal, not this function.
    """
    return [
        "docker",
        "create",
        "--entrypoint",
        "/bin/sh",
        *_container_options(codex_home_dir, out_dir, schema_dir),
        image_ref,
        "-c",
        CANARY_CHECK_SCRIPT,
        "canary",
        *canary_paths,
    ]


def _mount_src(mount_value: str) -> str | None:
    for part in mount_value.split(","):
        if part.startswith("src="):
            return part[len("src=") :]
    return None


def host_exposure_problems(
    argv: list[str],
    *,
    kind: str,
    per_run_dirs: tuple[Path, ...],
    host_home: Path,
    repo_root: Path,
    host_codex_home: Path,
) -> list[str]:
    """Verify a `docker create` argv never exposes a protected host path (PC-03).

    Applies to both the review and the canary argv (*kind* is "review" or
    "canary"): no `--mount` source, no `-e`/`--env-file` value, and -- for
    "review" -- no element anywhere in the argv may reference *host_home*,
    *repo_root* or *host_codex_home* (T-85.1-29). The canary argv's
    positional arguments after the fixed `-c CANARY_CHECK_SCRIPT canary`
    boundary are inert data the canary script only tests for absence, so a
    protected path there is allowed; everywhere else in either argv it is
    not. Every reason names a path by marker only, never by the raw path.
    Mount sources are compared after os.path.realpath, same as
    verify_container_config.
    """
    protected = (
        (os.path.realpath(str(host_home)), "<HOST_HOME>"),
        (os.path.realpath(str(repo_root)), "<REPO_ROOT>"),
        (os.path.realpath(str(host_codex_home)), "<HOST_CODEX_HOME>"),
    )
    per_run_real = {os.path.realpath(str(d)) for d in per_run_dirs}

    def _protected_marker(value: str) -> str | None:
        # host_codex_home is typically nested under host_home (e.g.
        # ~/.codex); pick the most specific (longest) protected prefix
        # that matches, not just the first one in *protected*, so a
        # mount of the narrower path is reported by its own marker.
        real = os.path.realpath(value)
        candidates = [
            (protected_real, marker)
            for protected_real, marker in protected
            if real == protected_real or real.startswith(protected_real + os.sep)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda pair: len(pair[0]))[1]

    boundary_index = len(argv)
    if kind == "canary":
        for i in range(len(argv) - 2):
            if argv[i] == "-c" and argv[i + 1] == CANARY_CHECK_SCRIPT and argv[i + 2] == "canary":
                boundary_index = i + 3
                break

    reasons: list[str] = []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token == "--mount" and i + 1 < len(argv):
            src = _mount_src(argv[i + 1])
            if src is not None:
                marker = _protected_marker(src)
                if marker is not None:
                    reasons.append(f"mount source exposes a protected host path: {marker}")
                elif os.path.realpath(src) not in per_run_real:
                    reasons.append("unexpected mount source")
            i += 2
            continue
        if token == "-e" and i + 1 < len(argv):
            if argv[i + 1] != "CODEX_HOME=/codex-home":
                reasons.append("forwarded environment value not allowed")
            i += 2
            continue
        if token == "--env-file":
            reasons.append("forwarded environment value not allowed")
            i += 1
            continue
        if i < boundary_index:
            marker = _protected_marker(token)
            if marker is not None:
                reasons.append(f"{kind} argv references a protected host path: {marker}")
        i += 1
    return reasons


def canary_paths(
    *,
    host_home: Path,
    repo_root: Path,
    host_codex_home: Path,
    ssh_auth_sock: str | None,
    host_canary_file: Path,
) -> list[tuple[str, str]]:
    """Build the (path, marker) pairs the canary script checks for absence (B04-R3).

    Host-sensitive paths are reported by marker, never by raw path, in
    every reason host_exposure_problems()/parse_canary_check() produce.
    The fixed in-container paths use their own path as the marker, since
    they carry no host-identifying information. *ssh_auth_sock* is
    included only when set (the host may not have one).
    """
    pairs: list[tuple[str, str]] = [
        (str(host_home), "<HOST_HOME>"),
        (str(repo_root), "<REPO_ROOT>"),
        (str(host_codex_home), "<HOST_CODEX_HOME>"),
    ]
    if ssh_auth_sock is not None:
        pairs.append((ssh_auth_sock, "<SSH_AUTH_SOCK>"))
    pairs.append((str(host_canary_file), "<HOST_CANARY>"))
    for fixed in (
        "/run/host-services/ssh-auth.sock",
        "/var/run/docker.sock",
        "/root/.ssh",
        "/home/review/.ssh",
        "/codex-home/config.toml",
        "/codex-home/sessions",
    ):
        pairs.append((fixed, fixed))
    return pairs


def stage_output_schema(dest_dir: Path, *, expected_sha256: str) -> str:
    """Copy SCHEMA_PATH into *dest_dir* read-only, after verifying its hash (B17).

    Refuses with RunnerError if the hash does not match the audited value
    the caller recorded, or if the destination already exists
    (O_CREAT|O_EXCL). The copy is written 0o444 via fchmod on the open fd
    (bypassing umask) so nothing inside the container can modify the
    schema it was launched with, independent of the read-only mount
    itself.
    """
    data = SCHEMA_PATH.read_bytes()
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if actual_sha256 != expected_sha256:
        raise RunnerError(f"audited output schema hash mismatch: expected {expected_sha256}, got {actual_sha256}")
    dest = dest_dir / SCHEMA_PATH.name
    try:
        fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    except FileExistsError as exc:
        raise RunnerError(f"output schema already staged: {dest}") from exc
    os.fchmod(fd, 0o444)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    return actual_sha256


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


def audited_inputs_changed(run: ReviewRun, command_runner: CommandRunner) -> list[str]:
    """Return the AUDITED_INPUTS paths that changed between --base and --head.

    A non-empty result means the diff under review modifies the very
    checker, schema, prompt contract or runner that grades it (D-18
    WR-03/ARCH-03/impact-001), so the result is also cross-graded by the
    base commit's own checker (see materialize_grader / _run_base_grader).
    """
    output = _git_stdout(
        ["git", "diff", "--name-only", f"{run.base}..{run.head}", "--", *AUDITED_INPUTS], command_runner
    )
    return sorted(line.strip() for line in output.splitlines() if line.strip())


def run_meta(
    run: ReviewRun,
    *,
    harness_head: str,
    inputs: dict[str, dict[str, object]],
    allow_stale_head: bool,
    trust_verification: dict[str, object] | None,
    audited_inputs_changed_in_diff: list[str],
) -> dict[str, object]:
    return {
        "meta_version": 2,
        "head": run.head,
        "base": run.base,
        "label": run.label,
        "attempt": run.attempt,
        "trusted": run.trusted,
        "review_mode": "trusted-local-tests",
        "template_version": template_version(),
        "harness_head": harness_head,
        "allow_stale_head": allow_stale_head,
        "inputs": inputs,
        "codex_timeout_seconds": CODEX_TIMEOUT_SECONDS,
        "trust_verification": trust_verification,
        "test_evidence_source": "harness-local-pytest",
        "audited_inputs_changed_in_diff": audited_inputs_changed_in_diff,
        # The base-commit grader is only ever materialized from this base
        # (verify_trust has already required it to be on origin/main); this
        # is a static fact about the trusted path, not conditional on
        # whether audited_inputs_changed_in_diff is non-empty.
        "base_grader_ref": run.base,
        "base_grader_source": "base",
    }


def inspection_meta(
    run: ReviewRun,
    *,
    harness_head: str,
    inputs: dict[str, dict[str, object]],
    audited_inputs_changed_in_diff: list[str],
    input_stats: dict[str, object],
) -> dict[str, object]:
    """The provenance record for an untrusted head's inspection-only review (D-07).

    Carries harness_head and inputs like the trusted run_meta(), but
    review_mode "inspection-only-ci-evidence", test_evidence_source
    "GitHub CI check runs" (never local pytest, which never runs for an
    untrusted head), and inspection_input stats instead of a worktree/pytest
    record. base_grader_source is always "trusted-origin-main": the
    inspection-only path's grader never comes from --base (B13).
    """
    return {
        "meta_version": 2,
        "head": run.head,
        "base": run.base,
        "label": run.label,
        "attempt": run.attempt,
        "pr_url": run.pr_url,
        "trusted": False,
        "review_mode": "inspection-only-ci-evidence",
        "inspection_template_version": inspection_template_version(),
        "harness_head": harness_head,
        "inputs": inputs,
        "test_evidence_source": "GitHub CI check runs",
        "audited_inputs_changed_in_diff": audited_inputs_changed_in_diff,
        "base_grader_source": "trusted-origin-main",
        "inspection_input": {
            "bytes": input_stats["bytes"],
            "files_included": input_stats["files_included"],
            "files_omitted": input_stats["files_omitted"],
        },
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


def _write_base_status_stub(run: ReviewRun, reason: str) -> None:
    """Record an incomplete .base-status.json when the base checker's own result is unavailable."""
    stub = {
        "status": "incomplete",
        "reasons": [reason],
        "qualified_ids": [],
        "finding_count": 0,
        "inspected_head": None,
        "inspected_base": None,
    }
    run.output(".base-status.json").write_text(json.dumps(stub) + "\n", encoding="utf-8")
    print(f"base-status: {run.output('.base-status.json')}")
    print(json.dumps(stub))


def _write_json_atomic(path: Path, obj: object) -> None:
    """Write JSON to *path* via a temp file + os.replace (this repo's atomic write-then-rename convention)."""
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(obj, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except OSError:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


def materialize_grader(grader_ref: str, dest: Path, command_runner: CommandRunner) -> None:
    """Write the checker and schema exactly as they exist at *grader_ref* into *dest*.

    Always materialized from git objects (``git show <grader_ref>:<path>``),
    never from a worktree of the reviewed head: the base grader is the
    operator's own repository history, not anything the PR under review
    could have supplied (checker B13). The trusted path always calls this
    with grader_ref = run.base, which verify_trust has already required to
    be on refs/remotes/origin/main.
    """
    for relpath in GRADER_FILES:
        target = dest / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            proc = command_runner(
                ["git", "show", f"{grader_ref}:{relpath}"],
                cwd=HARNESS_ROOT,
                stdout=subprocess.PIPE,
                text=True,
                errors="replace",
                check=False,
            )
        except OSError as exc:
            raise RunnerError(f"could not materialize the base grader: {type(exc).__name__}") from exc
        if proc.returncode != 0:
            raise RunnerError(
                "grader changed in this diff and the base commit has no checker to cross-grade it:"
                f" base commit {grader_ref[:12]} has no {relpath}"
            )
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(proc.stdout or "")


def _run_base_grader(
    run: ReviewRun, *, grader_ref: str, checker_tail: list[str], command_runner: CommandRunner
) -> int:
    """Materialize *grader_ref*'s checker/schema and cross-grade the same report with it.

    Returns the base checker's exit code (0 = complete). Any failure to
    materialize or run the base checker is recorded as an incomplete
    .base-status.json and treated as a non-zero (failing) result, never as
    a pass by default (fail closed).
    """
    try:
        tmp = Path(tempfile.mkdtemp(prefix="codex-base-grader-"))
    except OSError as exc:
        _write_base_status_stub(run, f"harness could not create its base-grader temp directory: {type(exc).__name__}")
        return 1
    try:
        try:
            materialize_grader(grader_ref, tmp, command_runner)
        except RunnerError as exc:
            _write_base_status_stub(run, str(exc))
            return 1
        base_checker_path = tmp / "tests" / "codex_report_status.py"
        try:
            proc = command_runner(
                [sys.executable, str(base_checker_path), *checker_tail],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                text=True,
                errors="replace",
                check=False,
            )
        except OSError as exc:
            _write_base_status_stub(run, f"base checker could not run: {type(exc).__name__}")
            return 1
        if not (proc.stdout or "").strip():
            _write_base_status_stub(run, f"base checker produced no output (exit {proc.returncode})")
            return 1
        run.output(".base-status.json").write_text(proc.stdout, encoding="utf-8")
        print(f"base-status: {run.output('.base-status.json')}")
        print(proc.stdout, end="")
        return proc.returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
    earlier head's automatic retry). An untrusted head (bot or fork PR)
    dispatches to _execute_untrusted() instead, the inspection-only review
    (Phase 85.1, D-07); verify_trust() is never called for it.
    """
    if not run.trusted:
        return _execute_untrusted(run, command_runner)
    # Verified before anything else, including the existing-output check, so
    # nothing is written for a refused head (D-18 SA-01).
    trust_verification = verify_trust(run, command_runner)
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
    audited_changed = audited_inputs_changed(run, command_runner)
    template = load_template()
    prompt = render_prompt(template, prompt_values(run))
    meta = run_meta(
        run,
        harness_head=harness_head,
        inputs=inputs,
        allow_stale_head=allow_stale_head,
        trust_verification=trust_verification,
        audited_inputs_changed_in_diff=audited_changed,
    )

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
    except BaseException as exc:
        # SystemExit from the SIGTERM/SIGHUP handler, or KeyboardInterrupt,
        # anywhere outside the Codex step (pytest, worktree add, before the
        # scratch directory exists, the base grader): still never leave the
        # reserved attempt without a status, then let it propagate unchanged
        # so the exit status is unaffected.
        if not run.output(".status.json").exists():
            if isinstance(exc, SystemExit) and _RECEIVED_SIGNAL is not None:
                cause = signal.Signals(_RECEIVED_SIGNAL).name
            else:
                cause = type(exc).__name__
            try:
                _write_status_stub(run, f"interrupted by {cause} after reserving the output")
            except OSError as write_exc:
                print(f"warning: could not record the interrupted status: {type(write_exc).__name__}")
        raise


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
    checker_full_argv = checker_argv(run, exit_code=codex_exit, current_head=current_head)
    try:
        checker = command_runner(
            checker_full_argv,
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

    grader_changed = meta["audited_inputs_changed_in_diff"]
    if not grader_changed:
        return checker.returncode
    print(f"grader changed in this diff: {grader_changed}; cross-grading with the base commit's checker")
    base_exit = _run_base_grader(
        run, grader_ref=run.base, checker_tail=checker_full_argv[2:], command_runner=command_runner
    )
    if base_exit != 0:
        print("grader changed in this diff: the base commit's checker did not confirm completeness")
    return checker.returncode if base_exit == 0 else 1


# --- Inspection-only orchestration for untrusted (bot/fork) heads (D-07, B14) -
#
# execute() dispatches an untrusted ReviewRun to _execute_untrusted(), which
# gathers everything needed to build the inspection-only prompt purely from
# read-only git/gh calls, then reserves the output name exactly like the
# trusted path before writing anything. _execute_inspection() is everything
# after that reservation: it returns 0 (COMPLETE) or 3 (INCOMPLETE) and never
# raises except for a BaseException escaping the Codex launch, which
# _execute_untrusted still turns into a status stub before re-raising.


def _ci_evidence_text(ci: dict[str, object]) -> str:
    """A short textual summary of *ci* for the inspection-only prompt's CI_EVIDENCE placeholder."""
    ready = ci.get("ci_ready") or {}
    return (
        f"GitHub check run {ready.get('name')!r} (id {ready.get('id')}) completed with conclusion"
        f" {ready.get('conclusion')!r} for this exact head: {ready.get('html_url')}"
    )


def _refetch_head_ref_oid(run: ReviewRun, pr_info: dict[str, object], command_runner: CommandRunner) -> str:
    """Re-read the PR's headRefOid via a second ``gh pr view`` call after the Codex run.

    Grading must use the head as it is now, not as it was when the
    inspection input was built: a fast-moving PR could gain new commits
    during the run (T-85.1-18).
    """
    try:
        result = command_runner(
            ["gh", "pr", "view", str(pr_info["number"]), "--repo", REPO_SLUG, "--json", "headRefOid"],
            stdout=subprocess.PIPE,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RunnerError(
            f"could not confirm the current head: gh pr view could not run ({type(exc).__name__})"
        ) from exc
    if result.returncode != 0:
        raise RunnerError(f"could not confirm the current head: gh pr view exited {result.returncode}")
    try:
        data = json.loads(result.stdout or "")
    except ValueError as exc:
        raise RunnerError(
            f"could not confirm the current head: gh pr view returned unparseable JSON ({type(exc).__name__})"
        ) from exc
    head_ref_oid = data.get("headRefOid")
    if not isinstance(head_ref_oid, str) or not _SHA_RE.fullmatch(head_ref_oid):
        raise RunnerError("could not confirm the current head: gh pr view returned no valid headRefOid")
    return head_ref_oid


def _print_inspection_result(run: ReviewRun, *, complete: bool, reason: str | None) -> None:
    head12 = run.head[:12]
    if complete:
        print(f"Codex COMPLETE for {head12} (inspection-only)")
        return
    print(
        f"Codex INCOMPLETE for {head12}: {reason} Ask the owner to decide whether to retry or investigate;"
        " do not record this run as clean."
    )


def _inspection_incomplete(run: ReviewRun, reason: str, *, write_stub: bool = True) -> int:
    """Record (unless *write_stub* is False, when the checker already wrote .status.json), print, and return 3."""
    if write_stub:
        _write_status_stub(run, reason)
    _print_inspection_result(run, complete=False, reason=reason)
    return 3


def _execute_inspection(
    run: ReviewRun,
    *,
    prompt: str,
    meta: dict[str, object],
    inputs: dict[str, dict[str, object]],
    pr_info: dict[str, object],
    input_stats: dict[str, object],
    command_runner: CommandRunner,
) -> int:
    """Everything after the output name is reserved, for an untrusted head (D-07, B14).

    verify_isolation_boundary() is the mandatory precondition and runs
    after grader provenance (establish_trusted_main) and before the only
    launch seam (run_untrusted_codex); a non-"verified" verdict never
    reaches it (B04-R3). Returns 0 (COMPLETE) or 3 (INCOMPLETE).
    """
    if input_stats.get("oversize"):
        return _inspection_incomplete(run, "inspection input exceeds MAX_INSPECTION_INPUT_BYTES")

    try:
        provenance = establish_trusted_main(run, command_runner)
    except RunnerError as exc:
        _write_json_atomic(run.output(".grader-provenance.json"), {"established": False, "reasons": [str(exc)]})
        return _inspection_incomplete(run, str(exc))
    _write_json_atomic(run.output(".grader-provenance.json"), {"established": True, **provenance})

    main_sha = str(provenance["grader_ref"])
    audited_changed = list(meta["audited_inputs_changed_in_diff"])

    scratch = Path(tempfile.mkdtemp(prefix="codex-inspection-"))
    try:
        if audited_changed:
            grader_dir = scratch / "trusted-main-grader"
            materialize_grader(main_sha, grader_dir, command_runner)
            checker_path = grader_dir / "tests" / "codex_report_status.py"
            if not trusted_main_grader_supports_mode(checker_path, command_runner):
                return _inspection_incomplete(
                    run,
                    f"trusted-main checker at {main_sha[:12]} predates --review-mode inspection-only;"
                    " cross-grading cannot run",
                )

        inner_argv = inspection_codex_argv()
        boundary = verify_isolation_boundary(run, command_runner, scratch=scratch, inner_argv=inner_argv)
        _write_json_atomic(run.output(".boundary.json"), boundary)
        if boundary.get("verdict") != "verified":
            reasons = "; ".join(str(reason) for reason in (boundary.get("reasons") or []))
            return _inspection_incomplete(
                run, f"isolation boundary not verified ({reasons}); Codex was not run on the untrusted head"
            )

        codex_exit: int | None = None
        problems: list[str] = []
        try:
            codex_exit, problems = run_untrusted_codex(
                run, inner_argv=inner_argv, prompt=prompt, boundary=boundary, command_runner=command_runner
            )
        except RunnerError as exc:
            return _inspection_incomplete(run, f"untrusted Codex launch failed: {exc}")
        finally:
            # There is no separate worktree for an untrusted head; the same
            # scratch dir stands in for both arguments.
            _finalize_raw_outputs(run, worktree=scratch, scratch=scratch)

        if problems:
            return _inspection_incomplete(run, "; ".join(problems))

        audit_reasons = audit_event_types(run.output(".jsonl"))
        if audit_reasons:
            return _inspection_incomplete(run, "; ".join(audit_reasons))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    try:
        current_head = _refetch_head_ref_oid(run, pr_info, command_runner)
    except RunnerError as exc:
        return _inspection_incomplete(run, f"could not confirm the current head after the run: {exc}")

    checker_full_argv = checker_argv(
        run, exit_code=codex_exit, current_head=current_head, review_mode="inspection-only"
    )
    try:
        checker = command_runner(
            checker_full_argv, cwd=REPO_ROOT, stdout=subprocess.PIPE, text=True, errors="replace"
        )
    except OSError as exc:
        return _inspection_incomplete(run, f"checker could not run: {type(exc).__name__}")
    if not (checker.stdout or "").strip():
        return _inspection_incomplete(run, f"checker produced no output (exit {checker.returncode})")
    run.output(".status.json").write_text(checker.stdout, encoding="utf-8")
    print(f"status: {run.output('.status.json')}")
    print(checker.stdout, end="")
    head_complete = checker.returncode == 0

    base_complete = True
    if audited_changed:
        print(f"grader changed in this diff: {audited_changed}; cross-grading with the trusted-main checker")
        base_exit = _run_base_grader(
            run, grader_ref=main_sha, checker_tail=checker_full_argv[2:], command_runner=command_runner
        )
        base_complete = base_exit == 0
        if not base_complete:
            print("grader changed in this diff: the trusted-main checker did not confirm completeness")

    if head_complete and base_complete:
        _print_inspection_result(run, complete=True, reason=None)
        return 0
    return _inspection_incomplete(run, "see .status.json for reasons", write_stub=False)


def _execute_untrusted(run: ReviewRun, command_runner: CommandRunner) -> int:
    """Pre-reservation gathering and reservation for an untrusted head, then _execute_inspection() (D-07).

    Every step up to and including reserve_outputs may raise RunnerError or
    FileExistsError; nothing is written for a refused or already-claimed
    head. From the reservation onward, every path writes a status before
    returning or re-raising, mirroring execute()'s own wrapper for the
    trusted path (same Exception/BaseException stub-writing pattern).
    """
    pr_info = inspect_untrusted_pr(run, command_runner)
    ci = ci_evidence(run, command_runner)
    inputs = audit_inputs(command_runner)
    harness_head = _git_stdout(["git", "rev-parse", "HEAD"], command_runner).strip()
    audited_changed = audited_inputs_changed(run, command_runner)
    input_text, input_stats = build_inspection_input(run, command_runner)
    fence = new_input_fence(input_text)
    prompt = render_inspection_prompt(run, ci_evidence_text=_ci_evidence_text(ci), input_text=input_text, fence=fence)

    existing = [str(run.output(suffix)) for suffix in OUTPUT_SUFFIXES if run.output(suffix).exists()]
    if existing:
        raise FileExistsError(f"review outputs already exist: {existing}")

    meta = inspection_meta(
        run,
        harness_head=harness_head,
        inputs=inputs,
        audited_inputs_changed_in_diff=audited_changed,
        input_stats=input_stats,
    )

    run.out_base.parent.mkdir(parents=True, exist_ok=True)
    # The reservation is the first write; nothing else is touched if it fails.
    reserve_outputs(run, prompt)
    try:
        run.output(".meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        _write_json_atomic(run.output(".ci-evidence.json"), ci)
        return _execute_inspection(
            run,
            prompt=prompt,
            meta=meta,
            inputs=inputs,
            pr_info=pr_info,
            input_stats=input_stats,
            command_runner=command_runner,
        )
    except RunnerError:
        # Every RunnerError raised after the reservation has already written its status.
        raise
    except Exception as exc:
        reason = f"harness failed after reserving the output: {type(exc).__name__}"
        if not run.output(".status.json").exists():
            _write_status_stub(run, reason)
        raise RunnerError(reason) from exc
    except BaseException as exc:
        if not run.output(".status.json").exists():
            if isinstance(exc, SystemExit) and _RECEIVED_SIGNAL is not None:
                cause = signal.Signals(_RECEIVED_SIGNAL).name
            else:
                cause = type(exc).__name__
            try:
                _write_status_stub(run, f"interrupted by {cause} after reserving the output")
            except OSError as write_exc:
                print(f"warning: could not record the interrupted status: {type(write_exc).__name__}")
        raise


_PR_BASE_PLACEHOLDER = "<baseRefOid-from-gh>"


def _trust_preview_commands(run: ReviewRun) -> list[str]:
    """Commands verify_trust() would run for *run*, without running any of them."""
    base_on_main = shlex.join(["git", "merge-base", "--is-ancestor", run.base, "refs/remotes/origin/main"])
    if run.pr_url == LOCAL_CHECKPOINT_PR_URL:
        return [
            shlex.join(["git", "merge-base", "--is-ancestor", run.base, run.head]),
            shlex.join(["git", "for-each-ref", "--contains", run.head, "--format=%(refname)", "refs/heads/"]),
            shlex.join(["git", "rev-list", f"{run.base}..{run.head}"]),
            shlex.join(["git", "for-each-ref", "--format=%(refname)", "refs/heads/"]),
            "git reflog show --format=%H%x09%gs <ref>  # HEAD and every local branch",
            base_on_main,
        ]
    match = _PR_URL_RE.fullmatch(run.pr_url)
    number = match.group(2) if match else "<pr-number>"
    # Same order as _verify_trust_pr. The PR base is unknown until gh answers,
    # so the merge-base line carries a placeholder for it.
    return [
        shlex.join(["gh", "pr", "view", number, "--repo", REPO_SLUG, "--json", _GH_PR_VIEW_FIELDS]),
        f"git merge-base {_PR_BASE_PLACEHOLDER} {shlex.quote(run.head)}  # must equal --base {run.base}",
        base_on_main,
    ]


def dry_run(run: ReviewRun) -> int:
    """Print the rendered prompt and every command without running or writing anything."""
    worktree = Path("<temp-dir>") / "wt"
    prompt = render_prompt(load_template(), prompt_values(run))
    print("# Rendered prompt (sent on stdin to codex exec)")
    print(prompt)
    print("# Commands")
    print("# the two diff commands codex is instructed to run itself (D-17)")
    print(shlex.join(diff_argv(run.base, run.head)))
    print(shlex.join(plan_diff_argv(run.base, run.head)))
    print("# trust verification (D-18 SA-01)")
    for command in _trust_preview_commands(run):
        print(command)
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


def dry_run_untrusted(run: ReviewRun) -> int:
    """Print the inspection-only prompt and every command without running or writing anything (D-07)."""
    match = _PR_URL_RE.fullmatch(run.pr_url)
    number = match.group(2) if match else "<pr-number>"
    prompt = render_inspection_prompt(
        run,
        ci_evidence_text="<CI evidence: built at run time>",
        input_text="<inert input: built at run time>",
        fence="<fence: generated per run>",
    )
    print("# Rendered inspection-only prompt (sent on stdin to codex exec inside the review container)")
    print(prompt)
    print("# Commands")
    print("# PR and CI preconditions, bound to the exact head (D-09, T-85.1-18)")
    print(shlex.join(["gh", "pr", "view", number, "--repo", REPO_SLUG, "--json", _GH_PR_VIEW_FIELDS_INSPECTION]))
    print(shlex.join(["git", "fetch", "--no-tags", "origin", f"pull/{number}/head"]))
    print(shlex.join(["git", "rev-parse", "--verify", "FETCH_HEAD^{commit}"]))
    print(shlex.join(["gh", "api", f"repos/{REPO_SLUG}/commits/{run.head}/check-runs", "--paginate", "--slurp"]))
    print("# the inert review input is built from git objects only, never a checkout")
    print("# trusted-main grader provenance: the checker always comes from a fresh origin/main (B13, D-02)")
    print(shlex.join(["git", "fetch", "--no-tags", "origin", f"+refs/heads/main:{TRUSTED_MAIN_REF}"]))
    print(shlex.join(["git", "merge-base", "--is-ancestor", run.base, TRUSTED_MAIN_REF]))
    print(f"git status --porcelain --untracked-files=all -- {' '.join(AUDITED_INPUTS)}  # must be empty")
    print(f"# save the prompt to {shlex.quote(str(run.output('.prompt.txt')))}")
    print(f"# save provenance to {shlex.quote(str(run.output('.meta.json')))}")
    print("# the mandatory isolation boundary gate; Codex is launched only if it reports verified (B04-R3)")
    print(shlex.join(inspection_codex_argv()))
    print("# always removes the disposable review container, on success and on failure")
    checker = checker_argv(run, exit_code=0, current_head="<second gh pr view>", review_mode="inspection-only")
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
        help=(
            "Dependabot or outside-contributor PR: inspection-only Codex review in a verified disposable"
            " container; the head is never checked out or executed; run from a checkout of the freshly"
            " fetched origin/main"
        ),
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
        if not (REPO_ROOT / run.phase_dir).is_dir():
            parser.error(f"phase-dir does not exist: {run.phase_dir}")
        if args.dry_run:
            return dry_run(run) if run.trusted else dry_run_untrusted(run)
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
