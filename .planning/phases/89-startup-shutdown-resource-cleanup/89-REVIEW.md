---
phase: 89-startup-shutdown-resource-cleanup
reviewed: 2026-11-18T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - tests/test_scheduler.py
  - triggarr/search/scheduler.py
findings:
  critical: 0
  warning: 1
  info: 4
  total: 5
status: issues_found
---

# Phase 89: Code Review Report

**Reviewed:** 2026-11-18
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed `git diff 23392bcc..HEAD` for `triggarr/search/scheduler.py` (the new `_safe_close`,
`_safe_stop_scheduler`, `_stop_scheduler_if_running`, `_describe_closed` helpers and the rewritten
`create_lifespan` startup and shutdown paths) and the roughly 900 lines of new tests in `tests/test_scheduler.py`.
I checked the code against APScheduler 3.11.3 (`AsyncIOScheduler.shutdown` raises
`SchedulerNotRunningError` immediately but defers the real stop with `call_soon_threadsafe`;
`AsyncIOExecutor.shutdown` cancels pending job tasks) and aiosqlite 0.22.1 (`close()` awaits again in its own
`finally`; `_connect` stops the worker thread when the connect fails; the worker thread is non-daemon).

The core design holds up. Every startup step after `aiosqlite.connect` sits inside the `try`. Resources are
tracked as locals, not through `app.state`. The scheduler state is read from the scheduler itself, so a
partial `start()` is caught. Close tasks are owned by the helper, so the cap really returns even when
aiosqlite's close is stuck in its finalizer. Exception text is reduced to `_sanitize_exc` everywhere it is
logged. Close results are always retrieved, so asyncio never reports "Task exception was never retrieved" with
the raw text. Shutdown order D-04 is kept. The tests check real aiosqlite worker-thread shutdown (D-12),
cover every failure stage in D-11, and verify that nothing leaks into the logs. All 83 tests pass and ruff is
clean.

The main gap: the failed-startup cleanup runs only for `Exception`, and a cancellation during cleanup aborts
the remaining steps. In those cases the database worker thread, the cause of the container hang this phase
fixes, is still left running. The other findings are minor.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: Cancellation or interrupt during startup (or during cleanup) still leaks the database worker thread

**File:** `triggarr/search/scheduler.py:845`, `triggarr/search/scheduler.py:536-546`, `triggarr/search/scheduler.py:854-857`
**Issue:** The failed-startup cleanup is `except Exception as startup_exc:`. `asyncio.CancelledError` and
`KeyboardInterrupt`/`SystemExit` are `BaseException`s, so a startup that is cancelled while it is in
`init_db` (for example a long upgrade migration) or in any other awaited step skips cleanup entirely. That
leaves the open `aiosqlite` connection's non-daemon worker thread running, which is the process-exit hang
LIFE-01 is meant to remove. Separately, `_safe_close` re-raises `CancelledError`, so if the cleanup loop is
cancelled while closing the first client, the remaining clients and the database are never attempted. That
contradicts D-02 ("every remaining cleanup step still runs") on that path. Under today's uvicorn wiring
(signals only set `should_exit`, and startup runs to completion), this is unlikely in production. It is
reachable under test harnesses, embedding, or a future `timeout_graceful_shutdown`/outer timeout, and it
fails silently in exactly the case the phase targets.
**Fix:** Run the release half for any `BaseException`, but keep logging and re-raising unchanged. For
example, track success with a flag and do the cleanup in a `finally`, or catch `BaseException` and re-raise
it. When cancelled, still attempt the database close, which is the step that unblocks exit:
```python
except BaseException as startup_exc:
    if isinstance(startup_exc, Exception):
        logger.error("Startup failed ({exc}); closing what was opened", exc=_sanitize_exc(startup_exc))
    else:
        logger.error("Startup interrupted ({t}); closing what was opened", t=type(startup_exc).__name__)
    ...  # existing cleanup
    raise
```
In the cleanup loop, catch `CancelledError` around each `_safe_close` call, finish the remaining steps
(capped), then re-raise the cancellation at the end. Add a regression test that cancels the lifespan task
while `init_db` is awaiting and asserts that `worker_alive == [False]`.

## Info

### IN-01: Dead `isinstance` guard in `_safe_close`'s synchronous-failure branch

**File:** `triggarr/search/scheduler.py:529`
**Issue:** Inside `except Exception as exc:`, the expression
`_sanitize_exc(exc) if isinstance(exc, Exception) else type(exc).__name__` always takes the first branch, so
the `else` can never run.
**Fix:** Use `exc=_sanitize_exc(exc)`.

### IN-02: The same warning format is repeated four times in `_safe_close`

**File:** `triggarr/search/scheduler.py:525-530, 540-545, 561-566, 571-576`
**Issue:** The "could not close {label} ({exc}); continuing" call and its sanitize-or-type-name expression
are copied four times. A future wording or redaction change (D-07) has to be made in all four places, and
missing one could let unsanitized text through.
**Fix:** Extract `_warn_close_failed(context, label, exc: BaseException | str)` that does the
sanitize-or-type-name choice once.

### IN-03: `_safe_close` docstring says "never raise" but it re-raises `CancelledError`

**File:** `triggarr/search/scheduler.py:514`, `triggarr/search/scheduler.py:546`
**Issue:** The summary line says "never raise", but the helper intentionally re-raises `CancelledError`.
Callers that rely on the docstring (see WR-01) will not expect the cleanup loop to stop partway.
**Fix:** Change the docstring to "never raises except to propagate cancellation of the caller".

### IN-04: The shutdown client loop iterates the live `app.state.*_clients` dicts across awaits

**File:** `triggarr/search/scheduler.py:947-949`
**Issue:** The search lock is released (line 942) before the clients are closed. The loop iterates
`getattr(app.state, ...).items()` directly and awaits up to `_CLEANUP_STEP_TIMEOUT` per client. If any code
path adds or removes an instance during that window, `RuntimeError: dictionary changed size during
iteration` escapes the `finally` and skips the database close and the "Search engine stopped" line, which is
the exact isolation failure LIFE-02 addresses. Today uvicorn drains requests before the lifespan shuts down
(no `timeout_graceful_shutdown`), so this is latent.
**Fix:** Iterate over a snapshot:
`for inst_name, client in list(getattr(app.state, f"{app_type}_clients", {}).items()):`.

## Set aside (needs ruling)

### SA-01: Uvicorn's own startup-failure traceback is unsanitized and is logged after the cleanup lines

**Where:** `triggarr/__main__.py:75-82` (uvicorn configured with default stdlib logging); the failure is re-raised at `triggarr/search/scheduler.py:864`
**Why excluded:** This is not in this phase's diff and it is existing behavior. After the re-raise, Starlette
sends `lifespan.startup.failed` with `traceback.format_exc()`, and uvicorn logs it through stdlib logging.
That bypasses the loguru redacting sink.
**Effect if left as is:** The operator still sees the full cause, but only after Triggarr's type-only ERROR
line and the cleanup lines. If a startup exception's text ever contains a URL with credentials, uvicorn
prints it unredacted. No current startup step makes HTTP calls, so the exposure is theoretical today.
**Needs:** A ruling on whether to route uvicorn's logs through the loguru sink in a later phase, or to accept this.

### SA-02: A capped database close during failed startup can still delay process exit

**Where:** `triggarr/search/scheduler.py:857`, `_ABANDONED_CLOSE_TASKS`
**Why excluded:** Accepted by D-09/D-10 and documented next to `_CLEANUP_STEP_TIMEOUT`. If the cap fires on
the database close, the non-daemon aiosqlite thread stays alive, and `asyncio.run` waits for the abandoned
task at teardown.
**Effect if left as is:** A wedged sqlite call still holds the container until Docker kills it, as before,
but now with a warning naming the step.
**Needs:** None beyond confirming the D-10 decision. Phase 92 smoke tests should show whether this occurs in practice.

---

_Reviewed: 2026-11-18_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
