---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "03"
subsystem: testing
tags: [codex-review, subprocess, signals, redaction, process-groups]

# Dependency graph
requires:
  - phase: 83-paired-bm-codex-review-risk-based-depth
    provides: tests/codex_review_run.py (the Codex review runner this plan hardens)
provides:
  - Signal-safe process-group cleanup for the Codex/pytest runner (SIGTERM/SIGHUP)
  - Bounded post-kill output drain (DRAIN_TIMEOUT_SECONDS)
  - _write_evidence_copy cleans up its own failed mkdir
  - Logged (not silent) getpass.getuser() fallback in redact_local_paths
  - _finalize_raw_outputs redacts raw Codex .jsonl/.last.json before grading, on every exit path
affects: [85-13 (trust verification and audited-inputs grader check on the same file)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level _ACTIVE_GROUPS set tracked by run_command(), killed by a SIGTERM/SIGHUP handler installed in main()"
    - "finally-based finalize step (_finalize_raw_outputs) that runs on every exit path of a guarded block, not only the normal-return path"

key-files:
  created: []
  modified:
    - tests/codex_review_run.py
    - tests/test_codex_review_run.py

key-decisions:
  - "Widened _kill_group/_terminate_active_groups to suppress OSError broadly, not just ProcessLookupError, after discovering a second kill on an already-SIGKILLed group can raise PermissionError on macOS"

patterns-established:
  - "Signal handlers that raise SystemExit(128+signum) after killing tracked state, installed/restored around main() only"

requirements-completed: [ACCEPT-01]

# Metrics
duration: 50min
completed: 2026-10-27
---

# Phase 85 Plan 03: Codex Runner Process/Signal Hardening Summary

**Signal-safe process-group cleanup, bounded post-kill drain, evidence-dir cleanup, warned getpass fallback, and pre-grading redaction of raw Codex output in tests/codex_review_run.py.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 2
- **Files modified:** 2 (`tests/codex_review_run.py`, `tests/test_codex_review_run.py`)

## Accomplishments

- An external SIGTERM or SIGHUP now kills the whole tracked Codex/pytest process group before the runner exits (`install_signal_handlers()`, `_ACTIVE_GROUPS`), closing the round-6 WR-01 orphaning gap.
- The post-kill output drain (`run_command`'s second `communicate()`/`wait()` after a kill) is now bounded by `DRAIN_TIMEOUT_SECONDS` (10s), with a truncation marker appended to whatever partial output was captured, closing the bugs-002 hang gap.
- `_write_evidence_copy` now removes the directory it just created when the evidence file's `os.open()` fails, instead of leaving an empty directory behind in the reviewed worktree (rm-001).
- `redact_local_paths` now prints a warning naming the exception type when `getpass.getuser()` fails, instead of silently skipping username redaction (compliance-002), and its docstring no longer overclaims that local paths never appear in the text it processes.
- A new `_finalize_raw_outputs()` redacts the raw Codex `.jsonl`/`.last.json` outputs before grading on every exit path of the Codex step -- normal return, a SIGTERM/SIGHUP-raised `SystemExit`, or any other exception -- and, when interrupted with no status already recorded, writes an incomplete `.status.json` stub naming the signal or failure (WR-04, checker B12).

## Task Commits

Both tasks followed RED -> GREEN:

1. **Task 1: Signal-safe process-group cleanup and a bounded post-kill drain**
   - `3a8eff2` test(85-03): add failing signal and drain tests
   - `f17eae7` feat(85-03): kill the Codex/pytest group on SIGTERM/SIGHUP and bound the post-kill drain
2. **Task 2: Evidence-dir cleanup, warned getpass fallback, raw-output redaction and an accurate docstring**
   - `f48c011` test(85-03): add failing evidence-dir, getpass and raw-output redaction tests
   - `6ce9d49` fix(85-03): clean up evidence dir, warn on getpass failure, redact raw Codex output (D-18)

Plan-start SHA (for the "committed raw evidence under Phase 83's `codex/` directory is untouched" check): `57e7e34ddcde5045994ce05565b96a44a846a479`.

## Files Created/Modified

- `tests/codex_review_run.py` - `DRAIN_TIMEOUT_SECONDS`, `_ACTIVE_GROUPS`, `_RECEIVED_SIGNAL`, `_terminate_active_groups`, `_handle_termination_signal`, `install_signal_handlers` added; `run_command` tracks active groups and bounds its post-kill drain; `main()` installs/restores signal handlers; `_write_evidence_copy` cleans up its failed mkdir; `redact_local_paths` warns on `getpass.getuser()` failure and has an updated docstring; `_redact_file` and `_finalize_raw_outputs` added and wired into `_execute_reserved`'s Codex step via an inner `try/finally`; the `execute()` existing-output comment updated.
- `tests/test_codex_review_run.py` - 11 new regression tests covering signal-kills-group, bounded drain, handler restoration, evidence-dir cleanup, getpass warning, raw-output redaction (normal, exception, SIGTERM, SIGHUP paths), and the docstring no longer overclaiming.

## Decisions Made

- Widened `_kill_group`/`_terminate_active_groups` to suppress `OSError` broadly rather than only `ProcessLookupError` (see Deviations below) -- a correctness fix, not a scope change.
- `_finalize_raw_outputs` writes the incomplete status stub itself (checking `sys.exc_info()`) rather than relying solely on the existing outer `except` handlers, so a `SystemExit` from a signal handler -- which those handlers don't catch -- still leaves a recorded, signal-naming status instead of none at all.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_kill_group`/`_terminate_active_groups` only suppressed `ProcessLookupError`, but a second kill on an already-dead group can raise `PermissionError`**
- **Found during:** Task 2, while building the SIGTERM/SIGHUP mid-Codex regression tests
- **Issue:** Once Task 1 added a signal handler that kills a tracked process group and then raises `SystemExit`, `run_command`'s own `except BaseException:` branch calls `_kill_group(proc)` a second time on the same (now-dead) group. On this machine (macOS), that second `os.killpg()` call reliably raised `PermissionError` instead of `ProcessLookupError`. Since `_run_codex`'s `except OSError:` branch catches `PermissionError` too, it silently swallowed the real `SystemExit` and reported "codex could not start: PermissionError" instead of the intended 128+signum exit and redacted-partial-output outcome -- confirmed failing against every one of the signal- and exception-interruption tests until fixed.
- **Fix:** Widened both `_kill_group` and `_terminate_active_groups` to `contextlib.suppress(OSError)` instead of `contextlib.suppress(ProcessLookupError)`, matching the functions' existing intent ("already handled, not a real failure").
- **Cost if wrong:** A real SIGTERM/SIGHUP during a Codex review run would silently misreport as "codex could not start," masking the actual interruption and signal/exit-code information from the evidence trail -- exactly the orphaned/misleading-report scenario this plan exists to close.
- **Files modified:** tests/codex_review_run.py
- **Commit:** `6ce9d49`

---

**Total deviations:** 1 auto-fixed (Rule 1 bug, discovered via the plan's own new regression tests)
**Impact on plan:** Necessary for correctness of the exact behavior Task 1/2 implement; no scope creep.

## Issues Encountered

- Reproducing the SIGTERM/SIGHUP-mid-Codex scenario required building a two-process harness (a disposable child process that installs the real signal handlers and calls `execute()`, with a `fake_codex.py` script substituted for the `codex` binary and run through the real `run_command`) since the mechanism under test is genuine OS-level signal delivery into a blocked `subprocess.Popen.communicate()` call, not something a single in-process `monkeypatch` can simulate. Debugging the PermissionError above required a standalone, instrumented reproduction outside pytest to get a clean traceback.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `tests/codex_review_run.py` is now signal-safe and redacts future raw Codex output before grading; Plan 85-13 (same file, later wave) covers `--trusted` independent verification and the audited-inputs grader check, which this plan did not touch.
- All 129 tests in `tests/test_codex_review_run.py` + `tests/test_codex_review_contract.py` pass; `uv run ruff check tests/` is clean; the full repo suite (2443 tests) passes.
- Committed raw evidence under `.planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/` is untouched (confirmed via `git log <plan-start-SHA>..HEAD -- <that path>` printing nothing).

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*
