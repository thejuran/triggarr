---
phase: 87-settings-state-file-safety
reviewed: 2026-11-16T04:27:46Z
depth: standard
iteration: 6
head: 88832ef9
files_reviewed: 2
files_reviewed_list:
  - triggarr/web/routes.py
  - tests/test_web.py
findings:
  critical: 0
  warning: 0
  info: 3
  total: 3
status: issues_found
---

# Phase 87: Code Review Report (iteration 6, review after the vibe-check cancellation fixes)

**Reviewed:** 2026-11-16T04:27:46Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found (info only: no critical, no warning)
**Head reviewed:** `88832ef9` (diff base `70f79434`, which carries the same code as iteration 5 head `e90f8cef` plus docs)

The reports for iterations 1 to 5 (heads `6262dd14`, `f099c6a8`, `615a044a`, `0cb0f12e`, `e90f8cef`) are in git history for this file.

## Summary

This iteration reviews the three commits from the vibe-check deep review (`git diff 70f79434..88832ef9 -- triggarr tests`), checked against the code itself:

- `f9186e87`: `remove_instance` handles cancellation of its settings write. If no worker has claimed the write, it is called off. If a worker has claimed it, the route waits for it through `asyncio.shield` (`_await_claimed_write`) and applies the result to live state before re-raising.
- `9c2fc602`: `_close_removed_client` finishes the removed client's close even under BaseHTTPMiddleware's level-triggered cancellation.
- `88832ef9`: a close task that was itself cancelled is reported as an error and logged.

**This iteration has no critical and no warning finding.** Under the owner's stopping rule there is nothing to fix. Three info items are listed for the backlog. The most notable is IN-01: under the production middleware, a cancelled removal's wait loop runs about 4,000 times in 60 ms because anyio re-delivers the cancellation on every turn of the event loop. Nothing is lost or wrong, but it burns CPU until the write and close finish. A one-line fix is suggested and was confirmed by a probe.

The fixes are real. In every cancellation case tested, the settings file and the running app agree afterwards, the lock is released, and the removed client's connection is closed.

### Fix verification

| Check | Result |
|---|---|
| Cancelled before a worker claims the write | The route sets `write_abandoned` under `write_gate` and re-raises at once (`routes.py:1152-1159`). Nothing is written and nothing live changes. If a worker has already taken the job from the queue but has not reached the gate yet, it finds `write_abandoned` set and returns without writing (`:1133-1135`). |
| Cancelled after the write is claimed, write succeeds | The route waits for the real outcome (`:1167`). It then applies the removal to settings, scheduler, clients, state and tag cache, closes the client, and re-raises (`:1249-1252`). `test_remove_instance_cancelled_during_write_keeps_file_and_live_state_in_step[True]` confirms that the file and live state agree and the lock is free. |
| Cancelled after the write is claimed, write fails | The route logs one error, keeps the instance and re-raises (`:1181-1192`). The `[False]` case of the same test confirms that. |
| `write_outcome` cannot be cancelled underneath the waiter | Holds. The worker calls `set_running_or_notify_cancel()` under the gate before writing (`:1139`). Once that has run, a cancelled `wrap_future` waiter cannot cancel the concurrent future, and `shield` also keeps the waiter itself from being cancelled. So `waiter.exception()` at `:1000` cannot raise `CancelledError`. |
| Write already finished when the cancellation arrives | Handled. The job is claimed and `write_outcome` is done, so `_await_claimed_write` returns after one turn of the loop. |
| No `await` between the commit and the close | Holds. The post-commit tidy-up is synchronous, and leaving `async with search_lock` does not suspend. The only remaining place a cancellation can arrive is inside `_close_removed_client`, which absorbs it. |
| Close finishes under level-triggered cancellation (`9c2fc602`) | Holds. The close runs as its own task. The anyio cancel scope does not track a task created with `asyncio.ensure_future`, so the close is never cancelled with the request. `test_remove_instance_cancelled_through_middleware_stack_still_closes_client` passes. |
| A cancelled close task is reported as an error (`88832ef9`) | Holds. `closing.cancelled()` returns a `RuntimeError` (`:1035-1036`). The route logs one error naming the app and instance (`:1240-1247`). |
| Each new test fails without its fix | Yes. The head `tests/test_web.py` was run against exported copies of each parent commit. At `70f79434` all 5 new tests fail. At `f9186e87` the middleware test and both cancelled-close tests fail. At `9c2fc602` the two cancelled-close tests fail. |
| API keys / logging | No secret is logged. The new log line logs only the exception type and message from `close()`. |

### Checks run during this review (from the checkout, without writing to it)

- `pytest tests/` (full suite): 3336 passed, 1 skipped.
- `pytest tests/test_web.py -k "remove_instance or close_removed"`: 34 passed.
- `ruff check triggarr/web/routes.py tests/test_web.py`: all checks passed.
- Convention pack (`verify conventions --check`) on the two files: no findings (not skipped).
- Throwaway probes in the session scratchpad, not in the repo:
  - Each new test run against exported copies of `70f79434`, `f9186e87` and `9c2fc602` (results above).
  - `asyncio.shield` call counts for the cancellation tests, as written at head and with the IN-01 fix applied via monkeypatch (IN-01).

Not verified: nothing was exercised against a real uvicorn server or a real client disconnect. Production cancellation was modelled only by the test's three `BaseHTTPMiddleware` layers.

## Owner decisions recorded by the vibe-check review (not re-raised)

| Item | Owner decision | Status at this head |
|---|---|---|
| `save_settings`' post-commit close loop is not cancellation-safe (`routes.py:867`, `await c.close()`) | Deferred (pre-existing, outside phase scope) | Unchanged. Not re-examined. |
| A close task that cancels itself while the request is not cancelled still re-raises `CancelledError` | Deferred (shutdown-only edge) | Unchanged. `shield` turns the inner task's cancellation into a `CancelledError` at `:1028`, which is recorded as the request's own cancellation. `test_remove_instance_cancelled_close_logs_error` currently pins that re-raise (`pytest.raises(asyncio.CancelledError)`). If the deferred item is fixed, that assertion must change too. |
| Test default executors are not shut down explicitly | Dismissed (asyncio shuts them at loop close) | Not re-raised. |

## Earlier-iteration dispositions

| Finding | Disposition | Notes |
|---|---|---|
| Iteration 5 IN-01: a rejected Save waits for the lock | Backlog | Code unchanged in this iteration. |
| Iteration 5 SA-01 / SA-02 | Awaiting/recorded owner ruling | `triggarr/config.py` and `save_settings` unchanged. Not re-examined. |
| Codex F001 at `0cb0f12e`: a removal cancelled after its write started leaves live state stale | Fixed for `remove_instance` in `f9186e87` | Verified above. The backlog entry's "fix once for all settings routes" still applies to Save Settings and Add Instance, which this diff does not touch. |

## Narrative Findings (AI reviewer)

## Info

### IN-01: Under the production middleware, a cancelled removal busy-loops on the event loop until its write and close finish

**File:** `triggarr/web/routes.py:996-1003` (`_await_claimed_write`), `triggarr/web/routes.py:1026-1033` (`_close_removed_client`)
**Issue:** anyio's cancel scope (inside each `BaseHTTPMiddleware`) re-delivers `task.cancel()` on every turn of the event loop until the task leaves the scope. anyio does not know about `asyncio.shield`, so every `await asyncio.shield(...)` in these loops is cancelled on the next turn, and the loop starts another shield at once. Measured in `test_remove_instance_cancelled_through_middleware_stack_still_closes_client`: **4,063 `shield` calls** during a 50 ms write plus a 10 ms close, against 1 to 2 calls when the cancellation arrives once (the plain-asyncio test). The loop yields on each pass, so other requests are still served and the result is correct. However, the event loop runs at full CPU for as long as the write takes to fsync, which can take noticeably longer on NAS storage, and for the close. Only a cancelled removal is affected, which is rare. This is mainly a resource cost, so it is graded Info.
**Fix:** Also stop anyio from re-delivering, and keep the existing loop for one-off asyncio cancellations:
```python
import anyio

async def _await_claimed_write(outcome):
    waiter = asyncio.wrap_future(outcome)
    cancelled = None
    with anyio.CancelScope(shield=True):
        while not waiter.done():
            ...  # unchanged loop body
```
Do the same in `_close_removed_client`. Probed by wrapping both helpers in `anyio.CancelScope(shield=True)` via monkeypatch: the middleware test drops to 2 `shield` calls, and all 5 new cancellation tests still pass. The first `CancelledError` must still be captured before the shielded scope is entered (it is: the route receives it from `run_in_executor` at `:1151`).

### IN-02: The middleware close test would also pass with a fire-and-forget close

**File:** `tests/test_web.py` (`test_remove_instance_cancelled_through_middleware_stack_still_closes_client`, the `for _ in range(100): if close_done: break` loop after `await request_task`)
**Issue:** The docstring says the close must finish "before the cancellation propagates". After the request task has ended, the test polls for up to 500 ms for `close_done`. Code that only scheduled the close (`asyncio.create_task(client.close())`) and re-raised at once would therefore pass, although the route would no longer wait for the close. The test does catch the original defect: the plain `await client.close()` is cancelled mid-close and never finishes, so the test fails on `9c2fc602^` as verified above.
**Fix:** Assert `close_done` immediately after `await request_task`, without the polling loop. At head, `close_done` is already `True` at that point because the route waits for the close.

### IN-03: The final re-raise comment names only the write

**File:** `triggarr/web/routes.py:1249-1251`
**Issue:** The comment says "The request was cancelled while the write ran". `cancelled` can also come from `_close_removed_client` (`:1238-1239`), when the cancellation arrives during the close. It can also come from a close task cancelling itself, as described in the deferred owner item above. A reader tracing a `CancelledError` from a removal would be misled about where it came from.
**Fix:** Change the comment to say the request was cancelled while the write or the close was running, and that the removal has been applied and the client closed (or the close failure logged) before the cancellation is let through.

## Set aside (needs ruling)

None. The two deferred items and the dismissed item from the vibe-check review are recorded above as owner decisions and are not counted here.

---

_Reviewed: 2026-11-16T04:27:46Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
