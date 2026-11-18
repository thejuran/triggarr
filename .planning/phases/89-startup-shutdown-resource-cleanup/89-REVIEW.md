---
phase: 89-startup-shutdown-resource-cleanup
reviewed: 2026-11-18T00:00:00Z
depth: standard
iteration: 2
files_reviewed: 2
files_reviewed_list:
  - tests/test_scheduler.py
  - triggarr/search/scheduler.py
findings:
  critical: 0
  warning: 1
  info: 6
  total: 7
status: issues_found
---

# Phase 89: Code Review Report (round 2)

**Reviewed:** 2026-11-18
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

This round re-reviews the full phase diff (`git diff b4a25aa1..HEAD -- triggarr/ tests/`) at HEAD 2fe58c29,
with a focus on fix commit 26a2fc8f (round-1 WR-01). I traced the fix against aiosqlite 0.22.1 (`_connect`
calls `stop()` on any `BaseException`, and `close()` stops the worker in its `finally` even when cancelled)
and against asyncio task semantics. `tests/test_scheduler.py` passes (86 tests), ruff is clean, and the
conventions check returned no findings.

**Round-1 WR-01: resolved.** The failed-startup handler now catches `BaseException`. A non-`Exception` is
logged by type name only, so no unsanitized text reaches the log. A cancellation that arrives during cleanup
is held by `_close_through_cancellation` or by the scheduler-stop `try`. The remaining client closes and the
database close still run, and the cancellation is then re-raised. When the startup error was an ordinary
`Exception`, the cancellation is chained to it (`raise cleanup_cancel from startup_exc`). Otherwise the
original cancellation or interrupt is re-raised with a bare `raise`. I found no path that swallows a
cancellation from an asyncio caller. When the original is a non-`CancelledError` `BaseException` such as
`KeyboardInterrupt`, a held cancellation is dropped in favour of the interrupt, which is the stronger signal
and acceptable. Each new regression test fails on the unfixed code (per the fix report), and each runs
inside an owned task with a deadline.

The fixer pointed out that the normal shutdown `finally:` still stops early when it is cancelled. Judged on
its merits, this is the same defect class as round-1 WR-01, on the path the code's own comments call the most
likely to be cancelled. It is graded the same way (WR-02). The remaining items are minor.

## Narrative Findings (AI reviewer)

## Warnings

### WR-02: A cancellation during normal shutdown skips every remaining close, including the database

**File:** `triggarr/search/scheduler.py:920-1008` (drain at `966`, client loop at `1001-1003`, database close at `1006`)
**Issue:** The shutdown `finally:` has no handling for cancellation. Two points are exposed:
1. **The search-lock drain (`async with asyncio.timeout(drain): await app.state.search_lock.acquire()`).** It
   can wait for up to `shutdown_drain_timeout` seconds while a search cycle holds the lock. A cancellation
   that is not a timeout propagates straight out of the `finally:`. No client is closed, the database is
   never closed, and "Search engine stopped" is never logged. The comment at about line 954 says: "Shutdown
   is exactly where a higher-level cancel (uvicorn reload, test re-entry) is most likely to interleave with
   this code path."
2. **The client loop.** `_safe_close` re-raises `CancelledError`, so a cancellation while closing one client
   skips the later clients and the database.

In both cases the open aiosqlite connection keeps its non-daemon worker thread alive. That thread causes the
process-exit hang this phase removes (LIFE-01, research Pitfall 6), and LIFE-02 promises that the database
always closes at shutdown. Under today's uvicorn wiring, signals only set `should_exit` and the lifespan
shutdown is awaited rather than cancelled, so production exposure is limited. Round-1 WR-01 was graded
WARNING on the same reachability: test harnesses, embedding, or a future outer timeout. Now that the startup
half is protected, the shutdown half is the only lifespan path that still leaks the thread on cancellation.
**Fix:** Reuse the startup pattern. Hold the cancellation, finish the closes, then re-raise:
```python
cleanup_cancel: asyncio.CancelledError | None = None
try:
    ...  # existing drain block, unchanged
except asyncio.CancelledError as cancel:
    cleanup_cancel = cancel  # still close everything below
for app_type in APP_TYPES:
    for inst_name, client in list(getattr(app.state, f"{app_type}_clients", {}).items()):
        _, cancel = await _close_through_cancellation(
            "Shutdown", f"{app_type.title()}/{inst_name!r} connection", client.close
        )
        cleanup_cancel = cleanup_cancel or cancel
_, cancel = await _close_through_cancellation("Shutdown", "database", app.state.db.close)
cleanup_cancel = cleanup_cancel or cancel
logger.info("Search engine stopped")
if cleanup_cancel is not None:
    raise cleanup_cancel
```
When the drain is cancelled, the lock-holding search cycle may still be mid-write. That is acceptable,
because the alternative is the hang. Log it at WARNING ("Shutdown: drain interrupted by cancellation;
closing anyway"). Add a regression test that holds `search_lock` and cancels the lifespan task during the
drain, then asserts `worker_alive == [False]` and that every tracked client is closed. Add a second test that
cancels during the first client close.

## Info

### IN-01 (carried, still open): Dead `isinstance` guard in `_safe_close`'s synchronous-failure branch

**File:** `triggarr/search/scheduler.py:529`
**Issue:** The code is inside `except Exception as exc:`, so in
`_sanitize_exc(exc) if isinstance(exc, Exception) else type(exc).__name__` the `else` branch can never run.
**Fix:** Use `exc=_sanitize_exc(exc)`.

### IN-02 (carried, still open): The close-failure warning format is repeated four times

**File:** `triggarr/search/scheduler.py:525-530, 540-545, 561-566, 571-576`
**Issue:** The "could not close {label} ({exc}); continuing" call is still copied four times, each with its
own sanitize-or-type-name choice. `_close_through_cancellation` (line 636) adds a fifth close-related warning
shape. A future change to wording or redaction (D-07) must be repeated in every copy. If one copy is missed,
unsanitized text could reach the log.
**Fix:** Extract `_warn_close_failed(context, label, exc: BaseException | str)` so the choice is made once.

### IN-03 (carried, still open, now load-bearing): `_safe_close` docstring says "never raise"

**File:** `triggarr/search/scheduler.py:514`, `triggarr/search/scheduler.py:546`
**Issue:** The docstring summary still says "never raise", but the helper re-raises `CancelledError`. The
WR-01 fix now depends on that re-raise: `_close_through_cancellation` exists only to catch it. Anyone who
trusts the docstring could "simplify" the code and break the fix, or could call `_safe_close` directly in a
new cleanup loop (as the shutdown path does today, see WR-02) without expecting it to stop partway.
**Fix:** Use "never raises, except to propagate cancellation of the caller; see `_close_through_cancellation`".

### IN-04 (carried, still open): The shutdown client loop iterates the live `app.state.*_clients` dicts across awaits

**File:** `triggarr/search/scheduler.py:1002`
**Issue:** This is unchanged from round 1. If an instance is added or removed while a capped close is being
awaited, `RuntimeError: dictionary changed size during iteration` escapes the `finally:` and skips the
database close. The risk is latent while uvicorn drains requests before the lifespan shuts down.
**Fix:** `for inst_name, client in list(getattr(app.state, f"{app_type}_clients", {}).items()):` (this
change is also included in the WR-02 fix sketch).

### IN-05: A close that completed before the cancellation arrived is reported as not closed

**File:** `triggarr/search/scheduler.py:536-546`, `triggarr/search/scheduler.py:633-641`, `triggarr/search/scheduler.py:898-901`
**Issue:** When the caller is cancelled, `_safe_close` logs only when the close task failed. A close task that
already finished successfully, or that was cancelled after its real work was done, still ends up as
`(False, cancel)` with the warning "closing ... was interrupted by cancellation". The startup summary then
undercounts. The new test
`test_startup_cleanup_cancelled_midway_still_closes_remaining_steps_database_last` shows this: both clients
are actually closed (`clients_closed == [True, True]`), but the summary line it asserts says "the database
and 1 connection(s)". The effect is limited to a log inaccuracy on a rare path, but D-05's summary is meant
to tell the operator what was closed.
**Fix:** In `_safe_close`'s `except asyncio.CancelledError` branch, record whether
`task.done() and not task.cancelled() and task.exception() is None`. Have `_close_through_cancellation`
return that value as `closed`. Alternatively, word the summary as "at least N connection(s)" on the
interrupted path.

### IN-06: The test harness cannot observe the cancellation contract the fix promises

**File:** `tests/test_scheduler.py:2752-2753` (`_observe_lifespan`), new tests at `tests/test_scheduler.py:3259-3382`
**Issue:** For a cancelled task, `_observe_lifespan` stores a fresh `asyncio.CancelledError()` rather than the
exception that was actually raised. As a result, no test can check either half of the re-raise contract:
(a) a cleanup cancellation is chained `from` the original startup error (`__cause__ is` the original
`RuntimeError`), and (b) an original cancellation is re-raised unchanged. If someone later drops the `from`,
or replaces the bare `raise` with `raise cleanup_cancel`, the suite stays green. The new tests also never
cover a cancellation during the scheduler-stop step (lines 887-891).
**Fix:** In `drive()`, wrap `async with lifespan_fn(app)` in `try/except BaseException as e: raised.append(e); raise`
and expose `raised[0]` on the observation. Then, in the cancelled-midway test, assert
`isinstance(raised[0].__cause__, RuntimeError)`. Optionally, add a case that cancels inside a fake
scheduler's `shutdown()` and asserts that every client and the database still close.

## Set aside (needs ruling)

### SA-01 (carried): Uvicorn's own startup-failure traceback is unsanitized and is logged after the cleanup lines

**Where:** `triggarr/__main__.py:75-82`; the re-raise is at `triggarr/search/scheduler.py:917-918`
**Why excluded:** The behavior is unchanged and lies outside this phase's diff. Starlette formats the re-raised
exception with `traceback.format_exc()`, and uvicorn logs it through stdlib logging, bypassing the loguru
redacting sink. After the fix, that traceback can also include the chained `CancelledError` and the
original cause.
**Effect if left as is:** The operator sees the full cause, but only after Triggarr's sanitized lines. If a
startup exception's text ever contains a URL with credentials, uvicorn prints it unredacted. No current
startup step makes an HTTP call, so the exposure is theoretical today.
**Needs:** A ruling on whether a later phase should route uvicorn's logs through the loguru sink, or whether
to accept the current behavior.

### SA-02 (carried): A capped database close during failed startup can still delay process exit

**Where:** `triggarr/search/scheduler.py:902-904`, `_ABANDONED_CLOSE_TASKS`
**Why excluded:** D-09 and D-10 accept this, and it is documented next to `_CLEANUP_STEP_TIMEOUT`. The same
applies when a cancellation interrupts the database close: the abandoned close task is cancelled, and
aiosqlite's `close()` still stops the worker in its `finally`, unless the sqlite call itself is wedged.
**Effect if left as is:** A wedged sqlite call still holds the container until Docker kills it, but a
warning now names the step.
**Needs:** Only confirmation of D-10. Phase 92 smoke tests should show whether this happens in practice.

---

_Reviewed: 2026-11-18_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
