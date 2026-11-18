---
phase: 89-startup-shutdown-resource-cleanup
plan: 01
subsystem: lifecycle
tags: [asyncio, shutdown, aiosqlite, httpx, resource-cleanup, tdd]
requires: []
provides:
  - "_safe_close / _safe_stop_scheduler / _ABANDONED_CLOSE_TASKS / _CLEANUP_STEP_TIMEOUT in triggarr/search/scheduler.py"
  - "_observe_lifespan / _LifespanObservation / _spy_connect test helpers in tests/test_scheduler.py"
affects: [89-02]
tech-stack:
  added: []
  patterns:
    - "Bounded wait on an owned task via asyncio.wait(timeout=...) instead of asyncio.timeout around a close"
    - "Result-retrieving done-callback attached to every close task at creation"
key-files:
  created: []
  modified:
    - triggarr/search/scheduler.py
    - tests/test_scheduler.py
key-decisions:
  - "_safe_close owns the close task and bounds only its own wait (asyncio.wait), because aiosqlite's close() awaits again in its finally after cancellation"
  - "Failure reasons are always _sanitize_exc(exc) / type name, never str(exc)"
requirements-completed: [LIFE-02]
metrics:
  duration: "about 25 minutes"
  completed: 2026-11-18
---

# Phase 89 Plan 01: Isolated, time-capped shutdown closes Summary

Shutdown now closes every *arr client and the database through a non-raising, 5-second-capped helper (`_safe_close`) that runs each close in a task it owns, so one failing or hanging close can no longer stop the remaining closes or leak the aiosqlite worker thread.

## What was built

- `triggarr/search/scheduler.py`: `_CLEANUP_STEP_TIMEOUT = 5.0`, `_ABANDONED_CLOSE_TASKS`, `_observe_abandoned_close`, `_retrieve_close_result`, `_safe_close`, `_safe_stop_scheduler`, and the shutdown `finally:` now calls `_safe_stop_scheduler("Shutdown", scheduler)`, `_safe_close("Shutdown", "<App>/'<inst>' connection", client.close)` per client and `_safe_close("Shutdown", "database", app.state.db.close)`. Drain, order (D-04) and the final `Search engine stopped` line are unchanged; no summary line added (D-08); no forced exit (D-10); no dependency change.
- `tests/test_scheduler.py`: 14 new tests plus `_spy_connect`, `_LifespanObservation`, `_observe_lifespan` (drive, observe, rescue; assertions only against the returned observation).

## Signatures for plan 89-02

Production:
- `async def _safe_close(context: str, label: str, close_fn: Callable[[], Awaitable[None]]) -> bool`
- `def _safe_stop_scheduler(context: str, scheduler) -> bool` (sync; True means stop requested; no running-state check inside)
- `_ABANDONED_CLOSE_TASKS: set[asyncio.Task]`, `_CLEANUP_STEP_TIMEOUT: float = 5.0` (read at call time; patch `triggarr.search.scheduler._CLEANUP_STEP_TIMEOUT`)

Test helpers (module level in tests/test_scheduler.py, Phase 89 section):
- `_spy_connect(captured: list, hook=None)`
- `_LifespanObservation` fields: exc, reached_yield, exit_timed_out, elapsed, scheduler_running, scheduler_shutdown_wait, clients_closed, worker_alive, lines, rescue_errors
- `async def _observe_lifespan(settings, tmp_path, scheduler, *, body=None, tracked=None, gates=(), connect_hook=None, log_level="INFO", deadline=10.0)`
- Also `_capture_sink(level)`, `_sink_lines(sink)`, `_track_all_clients(app, tracked)`, `_CAP` constant string.
- Note: real startup emits an unrelated `WARNING | Attribution cutover: ...` line; filter warnings by the `Shutdown:`/`Startup` prefix rather than all WARNING lines.

## Observed pre-fix (RED) outcomes (D-01)

Task 1, run by explicit node ID without `-x`, `10 failed`: every one of `test_cleanup_step_timeout_default_is_5s`, `test_safe_close_returns_true_on_success`, `test_safe_close_logs_sanitized_warning_and_returns_false_on_exception`, `test_safe_close_never_logs_url_credentials`, `test_safe_close_times_out_and_continues`, `test_safe_close_returns_at_cap_when_close_waits_in_cancellation_finalizer`, `test_safe_close_observes_late_failure_of_abandoned_close`, `test_safe_close_retrieves_close_failure_when_caller_is_cancelled`, `test_safe_close_returns_at_cap_on_wedged_real_aiosqlite_close`, `test_safe_stop_scheduler_logs_warning_when_shutdown_raises` FAILED with `ImportError: cannot import name '<new name>' from 'triggarr.search.scheduler'` inside the test body. The rest of the module still collected.

Task 2, run by explicit node ID without `-x` (`3 failed, 1 passed`):
- `test_shutdown_continues_when_client_close_fails`: FAIL at oracle, `lifespan exit raised AssertionError('in-flight close')`.
- `test_shutdown_continues_when_db_close_fails`: FAIL at oracle, `lifespan exit raised OSError(5, 'Input/output error')`.
- `test_shutdown_abandons_hung_client_close_after_cap`: FAIL at oracle, `lifespan exit did not finish within the deadline` (exit_timed_out=True, elapsed 2.0s).
- `test_shutdown_order_is_unchanged`: PASS (expected for an order pin).

## Verification (observed)

- Post-fix: 10/10 Task 1 tests pass; 4/4 Task 2 tests pass; hung-close test about 0.6s.
- `uv run pytest tests/ -x -q`: 3365 passed, 1 skipped. `uv run ruff check triggarr/ tests/`: all checks passed.
- Acceptance greps: 2 `await _safe_close("Shutdown"` calls; 0 bare close awaits; 0 `os._exit`/`sys.exit`; `pyproject.toml` and `uv.lock` unchanged vs main.
- The scripted `inspect`-based `_safe_close` body checks (asyncio.wait present, no asyncio.timeout/wait_for, one `.cancel()`, retrieval callback before first wait) passed.
- Not run: a real production shutdown against live *arr instances.

## Deviations from Plan

**1. [Rule 1 - Test bug] Shutdown tests filtered warnings by `WARNING | Shutdown:` prefix**
- **Found during:** Task 2 GREEN
- **Issue:** A startup `WARNING | Attribution cutover: ... no stable ID yet` line is emitted in these test setups, so "exactly one WARNING line" was wrong as written.
- **Fix:** Tests assert on warnings starting with `WARNING | Shutdown:`. Folded into the feat commit.
- **Cost if wrong:** a stray non-shutdown warning would not be caught by these tests; low.
- **Commit:** f58eebd6

**2. [Minor] `_close_failure_reason` helper not kept**: the sanitize-or-type-name expression is inlined in `_safe_close` so the literal `_sanitize_exc(` appears in its body per the acceptance check. Cost if wrong: none.

## Assumption Drift (advisory)

None material.

## Known Stubs

None.

## Threat Flags

None.

## Commits

- 376ae008 test(89-01): add failing tests for the safe close helpers
- 5bf4c5bf feat(89-01): add non-raising close helpers with a bounded owned-task wait
- b0119db6 test(89-01): add failing tests for isolated shutdown closes
- f58eebd6 feat(89-01): isolate each shutdown close so one failure never blocks the rest

## Self-Check: PASSED

Files and commits above exist (verified via git log and test runs).
