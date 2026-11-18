---
phase: 89-startup-shutdown-resource-cleanup
plan: 02
subsystem: lifecycle
tags: [asyncio, startup, aiosqlite, apscheduler, resource-cleanup, tdd]
requires: [89-01]
provides:
  - "Failed-startup unwind in create_lifespan: cause line first, scheduler stopped if running, clients and database closed, one summary line, original exception re-raised"
  - "_stop_scheduler_if_running and _describe_closed in triggarr/search/scheduler.py"
affects: []
tech-stack:
  added: []
  patterns:
    - "Resources tracked as plain locals (db, created_clients, scheduler) from acquisition, never read back from app.state"
    - "Scheduler stop decided from scheduler.running (actual state), then one loop iteration yielded and the state re-read"
key-files:
  created: []
  modified:
    - triggarr/search/scheduler.py
    - tests/test_scheduler.py
key-decisions:
  - "No scheduler_started flag: BaseScheduler.start() sets STATE_RUNNING before it can raise, so cleanup reads scheduler.running"
  - "Summary counts successful closes only; failed closes are reported by their own sanitized WARNING between cause and summary"
requirements-completed: [LIFE-01, LIFE-03]
metrics:
  duration: "about 20 minutes"
  completed: 2026-11-18
---

# Phase 89 Plan 02: Failed-startup resource unwind Summary

When any setup step after the database opens fails (upgrade, cutover, Nth client construction, `scheduler.start()`, or the post-start `update_check` job), the lifespan now logs the sanitized cause first, stops the scheduler if it is actually running, closes every client built so far and the database, logs one summary line, and re-raises the original exception object, so the aiosqlite worker thread stops and the process exits promptly.

## What was built

- `triggarr/search/scheduler.py`: one `try/except Exception as startup_exc:` around the setup section (from `aiosqlite.connect` through the `update_check` `add_job`); `db` and `created_clients` are plain locals; the except branch logs `Startup failed ({exc}); closing what was opened` (via `_sanitize_exc`) first, then `_stop_scheduler_if_running("Startup cleanup", scheduler)`, then one `_safe_close("Startup cleanup", ...)` per client in reverse order and for the database, then one summary `Startup failed; closed {closed} before exiting` (successes only), then bare `raise`.
- New `_stop_scheduler_if_running(context, scheduler) -> bool`: returns False without calling anything when `scheduler.running` is False; otherwise `_safe_stop_scheduler`, one `asyncio.sleep(0)`, re-read `running`, WARNING "the scheduler did not stop" if still running.
- New `_describe_closed(parts)` joins "a, b and c".
- No AsyncExitStack, no `scheduler_started` flag, no forced exit, no dependency change (`pyproject.toml`/`uv.lock` identical to main). Shutdown `finally:` block untouched.

## Observed pre-fix (RED) outcomes (D-01)

Task 1, seven tests run by explicit node ID without `-x`: `7 failed`, each at a positive cleanup assertion on pre-rescue evidence, `rescue_errors` empty:
- `test_startup_failure_init_db_closes_database_and_reraises`: `worker_alive == [False]` failed, observed `[True]`.
- `test_startup_failure_cutover_closes_database`: `worker_alive` observed `[True]`.
- `test_startup_failure_client_construction_closes_earlier_clients`: `clients_closed == [True, True]` failed, observed `[False, False]`.
- `test_startup_failure_scheduler_not_started_no_shutdown_call`: `worker_alive` observed `[True]`.
- `test_startup_failure_cleanup_also_fails_still_raises_original`: `clients_closed == [False, True]` failed, observed `[False, False]`.
- `test_startup_failure_cleanup_also_fails_on_db_close`: `CAUSE in obs.lines` failed (lines empty).
- `test_startup_failure_cause_line_never_logs_credentials`: `worker_alive` observed `[True]`.

Task 2, four tests: `3 failed, 1 passed`:
- `test_startup_failure_scheduler_started_shuts_scheduler_down`: FAIL at `obs.scheduler_shutdown_wait is False`, observed `None`; the real summary read "closed the database and 1 connection(s)".
- `test_startup_failure_partial_scheduler_start_is_stopped` (real `AsyncIOScheduler` subclass whose `wakeup` raises): FAIL at `obs.scheduler_running is False`, observed `True`.
- `test_startup_failure_scheduler_start_raises_no_shutdown_call`: PASS (expected pin).
- `test_stop_scheduler_if_running_reports_a_scheduler_that_stays_running`: FAIL with `ImportError: cannot import name '_stop_scheduler_if_running'`.
- The `_FakeScheduler.running` property added in this task broke no existing test (83 collected, only the 3 expected failures).

## Verification (observed)

- Post-fix: `-k startup_failure` 10 passed; `tests/test_scheduler.py` all green; `uv run pytest tests/ -x -q`: 3376 passed, 1 skipped; `uv run ruff check triggarr/ tests/`: all checks passed; `git diff --quiet main -- pyproject.toml uv.lock` exits 0.
- Acceptance script for except-branch ordering (cause, scheduler stop, closes, summary; exactly two `logger.error`; no `app.state`; bare raise last) passed after Task 1. `_safe_stop_scheduler(` count is 3.
- Not run: a real failed startup in a deployed container.

## Deviations from Plan

**1. [Minor] Cutover test also asserts exception type and message** instead of identity (the plan allowed "type and message" where the test does not hold the object). Cost if wrong: none.

**2. [Minor] Reindent done with a script** (setup section indented four spaces into the new `try`); a first pass put the `created_clients.append` outside the inner loop, caught before the first test run and fixed. Cost if wrong: none; the client-construction test pins it.

## Assumption Drift (advisory)

None material.

## Known Stubs

None.

## Threat Flags

None.

## Commits

- 1999eb85 test(89-02): add failing tests for failed-startup resource cleanup
- e15f6142 feat(89-02): report the cause, then close the database and every opened client when startup fails
- 1c9176b6 test(89-02): add failing tests for stopping a running scheduler after a failed startup
- ea80976f feat(89-02): stop a scheduler left running by a failed startup

## Self-Check: PASSED

Four commits above exist in `git log`; modified files exist; test and lint runs observed as listed.
