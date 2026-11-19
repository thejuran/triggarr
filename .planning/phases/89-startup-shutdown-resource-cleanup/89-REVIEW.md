---
phase: 89-startup-shutdown-resource-cleanup
reviewed: 2026-11-18T00:00:00Z
depth: standard
iteration: 5
reviewed_head: 4c9abdaed29ddf7c2d5861f7e324947cb78b2ddd
files_reviewed: 2
files_reviewed_list:
  - tests/test_scheduler.py
  - triggarr/search/scheduler.py
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 89: Code Review Report (round 5, PR #64 head)

**Reviewed:** 2026-11-18
**Reviewed head:** `4c9abdaed29ddf7c2d5861f7e324947cb78b2ddd` (HEAD was not moved; working tree clean)
**Depth:** standard
**Files Reviewed:** 2
**Status:** clean (no new findings; open items are already in the backlog)

## Summary

This round reviews the full phase diff, `git diff b4a25aa1..4c9abdae -- triggarr/ tests/` (2 files, +1577/-174),
at the PR #64 head. `git diff 4a7c7c5f..4c9abdae -- triggarr/ tests/` is empty. The commits since round 4 change
only `.planning/backlog/MAINTENANCE.md` and the Codex evidence files under `.planning/`. The code under review is
therefore byte-identical to round 4 (code head `9ec53d89`).

I re-read `triggarr/search/scheduler.py` in full and re-checked the paths most likely to hide a defect:

- **`_safe_close`:** the close task is owned by this helper. `_retrieve_close_result` is attached on every path. The
  abandon/cancel ordering in the `finally` is correct, the reason is bound by value through `functools.partial`,
  cancellation is re-raised, and every log line is redacted (`_sanitize_exc` or the type name, never `str(exc)`).
- **Failed-startup cleanup:** the order is scheduler, then clients in reverse, then the database. A cancellation
  during cleanup is held until every step has run. `raise cleanup_cancel from startup_exc` applies only when the
  original was an ordinary `Exception`. Otherwise the bare `raise` re-raises the original unchanged, and the
  handled exception is correctly restored after the nested handlers inside the awaited helpers.
- **Shutdown:** the drain releases the lock only when it was acquired. The drain, each client close and the
  database close each hold a cancellation, which is re-raised after the database close.
- **Scheduler stop:** `_stop_scheduler_if_running` reads the scheduler's own state, so a `start()` that raised
  after it set the running state is still stopped.

I found no new bug, security issue or test-reliability defect. The new tests restore `_CLEANUP_STEP_TIMEOUT`
through patching. They also assert that `_ABANDONED_CLOSE_TASKS` is drained, so no global state leaks between tests.

**Tests and lint (re-run at 4c9abdae):**
- `.venv/bin/python -m pytest tests/test_scheduler.py -q`: **88 passed, 1 warning** in 6.32s. The warning is
  Starlette's `httpx` TestClient deprecation and is unrelated to this phase.
- `.venv/bin/ruff check triggarr/ tests/`: **All checks passed!**
- Convention check (`gsd-tools verify conventions --check`) on both files: **0 findings**.

## Already backlogged (not re-raised)

These items are recorded in `.planning/backlog/MAINTENANCE.md` under the Phase 89 entry. The code is unchanged, so
each one still applies as described there. None of them counts toward this round's totals.

| ID | Where | Summary |
|----|-------|---------|
| IN-01 | `scheduler.py:532` | Dead `isinstance` guard in `_safe_close`'s synchronous-failure branch |
| IN-02 | `scheduler.py:528-581` | The "could not close" warning and its redaction are repeated four times |
| IN-03 | `scheduler.py:517` | The docstring says "never raise", but the helper re-raises cancellation (load-bearing) |
| IN-04 | `scheduler.py:1018-1023` | The shutdown loop iterates the live `*_clients` dicts across awaits |
| IN-05 | `scheduler.py:540-551, 640-646` | A close that finished just before a cancellation is counted as interrupted |
| IN-06 | `tests/test_scheduler.py` (`_observe_lifespan`) | A fresh `CancelledError()` is stored, so `from` chaining and two cancellation points go untested |
| SA-01 | uvicorn / APScheduler stdlib logging | Tracebacks bypass the redacting sink (predates Phase 89; needs owner ruling) |
| SA-02 | `scheduler.py:116-121` | A close at the 5 s cap can still delay process exit (accepted under D-10; confirm in Phase 92) |
| DR-01 | `scheduler.py:552-556` | A cancelled `_safe_close` cancels the in-progress close instead of letting it finish within the cap |
| R4-IN-01 | `scheduler.py:541` | No test covers the "ended after the caller was cancelled" DEBUG line |
| R4-IN-02 | `scheduler.py:537` | A non-cancellation `BaseException` from the wait is still logged as "the cap" |

## Set aside (needs ruling)

None.

---

_Reviewed: 2026-11-18_
_Reviewed head: 4c9abdaed29ddf7c2d5861f7e324947cb78b2ddd_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
