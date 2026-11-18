---
phase: 89-startup-shutdown-resource-cleanup
reviewed: 2026-11-18T00:00:00Z
depth: standard
iteration: 3
files_reviewed: 2
files_reviewed_list:
  - tests/test_scheduler.py
  - triggarr/search/scheduler.py
findings:
  critical: 0
  warning: 0
  info: 6
  total: 6
status: issues_found
---

# Phase 89: Code Review Report (round 3, final)

**Reviewed:** 2026-11-18
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found (info only; no critical or warning findings)

## Summary

This round re-reviews the full phase diff (`git diff b4a25aa1..HEAD -- triggarr/ tests/`) at HEAD 5e0d2a33.
It focuses on fix commit 6feac144 (round-2 WR-02). I checked three things: that a cancellation is never
swallowed, that the close order is unchanged, and that the new tests are reliable. `tests/test_scheduler.py`
passes (88 tests). The startup and shutdown subset (26 tests) passed in three repeated runs. Ruff is clean, and
the conventions check returned no findings. The only pytest warning is an unrelated Starlette deprecation
notice for `httpx`.

**Round-1 WR-01: resolved** (confirmed in round 2; the startup path did not change in this round).

**Round-2 WR-02: resolved.** Traced in `triggarr/search/scheduler.py:968-1027`:
- **Cancellation never swallowed.** A cancellation during the drain is caught at line 975 and held in
  `shutdown_cancel`. A cancellation during any client close or the database close is caught by
  `_close_through_cancellation` and held the same way (lines 1015-1022). After "Search engine stopped", line
  1027 re-raises the held exception object itself, so an outer `asyncio.timeout` that started the cancellation
  still recognizes it and converts it to `TimeoutError`. I found no path where a held cancellation is dropped,
  except when an unrelated exception escapes the close loop afterward (see IN-04, unchanged). Neither new test
  could pass if the re-raise were removed: both assert `isinstance(obs.exc, asyncio.CancelledError)`, and a
  swallowed cancellation would leave `obs.exc is None`.
- **Close order unchanged (D-04).** The order is still: stop the scheduler (synchronous, so a cancellation cannot
  arrive there), drain, Radarr/Sonarr/Lidarr clients, the database last, then "Search engine stopped". Both tests
  pin `order == ["radarr", "sonarr", "lidarr", "db"]`.
- **Drain semantics.** The `acquired` flag still guards the release. When `Lock.acquire()` is cancelled, it
  hands the lock to the next waiter without taking it, so the cancelled drain cannot leave the lock held. The
  task's `cancelling()` count stays raised after the catch. That is harmless, because no later step in this
  task uses `asyncio.timeout`: `_safe_close` bounds each close with `asyncio.wait(timeout=...)` and runs the
  close in its own task. The close task is always scheduled (`ensure_future`) before the caller can receive a
  cancellation, so the close coroutine reaches its first step and aiosqlite's own `finally` can stop the worker.
- **Test reliability.** Both tests run inside the owned-task harness with a deadline and an unconditional rescue
  stage. They are deterministic. In the drain test, `owner.cancel()` is called while the owner task is running,
  so the cancellation is delivered at the very next suspension, inside `held.acquire()`. In the client-close
  test, the close task's `await asyncio.sleep(0)` makes the owner's cancellation reach it before the close task
  finishes, which consistently exercises the "interrupted" path. Each test asserts that the real aiosqlite
  worker thread has stopped (`worker_alive == [False]`), not just that a mock was called.

I considered whether shutdown should also catch `KeyboardInterrupt`/`SystemExit`, as the startup handler does.
I did not raise this. On Python 3.11+, the asyncio runner and uvicorn turn SIGINT into a task cancellation (or
a `should_exit` flag), not into an exception raised inside the coroutine, so the cancellation handling covers
the realistic trigger.

No new critical or warning findings. Under the owner's decision for this round, IN-01..IN-06 and SA-01/SA-02
carry forward to the backlog. Their status is updated below.

## Narrative Findings (AI reviewer)

### Resolved

| ID | Finding | Status | Fix commit |
|----|---------|--------|------------|
| WR-01 | Cancellation or interrupt during startup or its cleanup leaked the database worker thread | Resolved (round 2) | 26a2fc8f |
| WR-02 | Cancellation during normal shutdown skipped every remaining close, including the database | Resolved (this round) | 6feac144 |

## Info

### IN-01 (carried, still open): Dead `isinstance` guard in `_safe_close`'s synchronous-failure branch

**File:** `triggarr/search/scheduler.py:529`
**Issue:** The code is inside `except Exception as exc:`, so the `else type(exc).__name__` branch in
`_sanitize_exc(exc) if isinstance(exc, Exception) else type(exc).__name__` can never run.
**Fix:** `exc=_sanitize_exc(exc)`.

### IN-02 (carried, still open): The close-failure warning format is repeated four times

**File:** `triggarr/search/scheduler.py:525-530, 540-545, 561-566, 571-576`
**Issue:** The "could not close {label} ({exc}); continuing" call is still copied four times, each with its own
sanitize-or-type-name choice. `_close_through_cancellation` (lines 636-640) now produces its warning on the
shutdown path too. A future change to wording or redaction (D-07) must be repeated in every copy. If one copy
is missed, unsanitized text could reach the log.
**Fix:** Extract `_warn_close_failed(context, label, exc: BaseException | str)` so the choice is made once.

### IN-03 (carried, still open, load-bearing): `_safe_close` docstring says "never raise"

**File:** `triggarr/search/scheduler.py:514`, re-raise at `triggarr/search/scheduler.py:546`
**Issue:** The docstring summary says "never raise", but the helper re-raises `CancelledError`. Both the startup
cleanup and the shutdown path now rely on that re-raise, because `_close_through_cancellation` exists to catch
it. A maintainer who trusts the docstring could remove the re-raise, which would turn every held cancellation
into a swallowed one. The shutdown tests would catch that (they assert `CancelledError`), but the docstring
still misleads.
**Fix:** "never raises, except to propagate cancellation of the caller; see `_close_through_cancellation`".

### IN-04 (carried, still open): The shutdown client loop iterates the live `app.state.*_clients` dicts across awaits

**File:** `triggarr/search/scheduler.py:1014`
**Issue:** This is unchanged; the fixer deliberately left it as is. If an instance is added or removed while a
capped close is being awaited, `RuntimeError: dictionary changed size during iteration` escapes the `finally:`.
That skips the database close, and it also drops any cancellation already held in `shutdown_cancel` (the
cancellation survives only as `__context__`). The risk is latent while uvicorn finishes serving requests before
the lifespan shuts down.
**Fix:** `for inst_name, client in list(getattr(app.state, f"{app_type}_clients", {}).items()):`

### IN-05 (carried, still open, now also on the shutdown path): A close that completed before the cancellation arrived is reported as interrupted

**File:** `triggarr/search/scheduler.py:536-546`, `triggarr/search/scheduler.py:633-641`, `triggarr/search/scheduler.py:895-900` (startup summary), `triggarr/search/scheduler.py:1015-1018` (shutdown)
**Issue:** When the caller is cancelled, a close task that had already done its work still returns
`(False, cancel)` and is logged as "closing ... was interrupted by cancellation". During startup cleanup this
makes the D-05 summary undercount. During shutdown the result is discarded, so only the warning wording is
wrong. `test_shutdown_cancelled_during_client_close_still_closes_remaining_steps_database_last` documents
this: the Radarr client is closed (`clients_closed[0] is True`), but the warning says its close was interrupted.
**Fix:** In `_safe_close`'s `except asyncio.CancelledError` branch, record
`task.done() and not task.cancelled() and task.exception() is None` and return it as `closed`. Alternatively,
word the warning as "may not have finished closing".

### IN-06 (carried, still open, scope widened): The tests cannot observe the cancellation's identity, and two cancellation points are untested

**File:** `tests/test_scheduler.py:2756` (`_observe_lifespan`); WR-01/WR-02 tests from `tests/test_scheduler.py:3259` onward
**Issue:** For a cancelled task, `_observe_lifespan` records a fresh `asyncio.CancelledError()`, so no test can
check that (a) a startup-cleanup cancellation is chained `from` the original error, or (b) the shutdown path
re-raises the held cancellation object rather than a new one. Swallowing is covered; identity and chaining are
not. Two cancellation points also have no test: a cancellation during the database close at shutdown (line 1021,
the last step before the re-raise) and a cancellation during the startup scheduler stop (lines 887-891).
**Fix:** In `drive()`, wrap the `async with` in `try/except BaseException as e: raised.append(e); raise` and expose
`raised[0]`. Assert `raised[0].__cause__` in the startup cancelled-midway test. Add one shutdown case whose
`db.close` cancels the owner, and assert `worker_alive == [False]` and `CancelledError`.

## Set aside (needs ruling)

### SA-01 (carried, unchanged): Uvicorn's own startup-failure traceback is unsanitized and is logged after the cleanup lines

**Where:** `triggarr/__main__.py:75-82`; the re-raise is at `triggarr/search/scheduler.py:916-918`
**Why excluded:** The behavior lies outside this phase's diff. Starlette formats the re-raised exception with
`traceback.format_exc()`, and uvicorn logs it through stdlib logging, bypassing the loguru redacting sink. That
traceback can include the chained `CancelledError` and the original cause.
**Effect if left as is:** The operator sees the full cause after Triggarr's sanitized lines. If a startup
exception's text ever contains a URL with credentials, uvicorn prints it unredacted. No current startup step
makes an HTTP call, so the exposure is theoretical today.
**Needs:** A ruling on whether a later phase should route uvicorn's logs through the loguru sink, or whether to
accept the current behavior.

### SA-02 (carried, unchanged): A capped database close can still delay process exit

**Where:** `triggarr/search/scheduler.py:902-904` (startup), `triggarr/search/scheduler.py:1021` (shutdown), `_ABANDONED_CLOSE_TASKS`
**Why excluded:** D-09 and D-10 accept this, and it is documented next to `_CLEANUP_STEP_TIMEOUT`. It now applies to
the cancelled-shutdown path as well: the abandoned close task is cancelled, and aiosqlite's `close()` still
stops the worker in its `finally`, unless the sqlite call itself is wedged.
**Effect if left as is:** A wedged sqlite call still holds the container until Docker kills it, but a warning
names the step.
**Needs:** Only confirmation of D-10. Phase 92 smoke tests should show whether this happens in practice.

---

_Reviewed: 2026-11-18_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
