---
phase: 89-startup-shutdown-resource-cleanup
fixed_at: 2026-11-18T23:45:00Z
review_path: .planning/phases/89-startup-shutdown-resource-cleanup/89-REVIEW.md
iteration: 2
findings_in_scope: 1
fixed: 1
skipped: 0
rejected: 0
status: all_fixed
---

# Phase 89: Code Review Fix Report

**Fixed at:** 2026-11-18T23:45:00Z
**Source review:** .planning/phases/89-startup-shutdown-resource-cleanup/89-REVIEW.md
**Iteration:** 2 (final fix round)

**Summary (this iteration):**
- Findings in scope: 1 (WR-02). By owner decision, IN-01..IN-06 and SA-01/SA-02 are not fixed here and go to the backlog.
- Fixed: 1
- Skipped: 0
- Rejected: 0

**Both rounds:**

| Iteration | Finding | Status | Commit |
|-----------|---------|--------|--------|
| 1 | WR-01: cancellation or interrupt during startup (or its cleanup) leaked the database worker thread | fixed: requires human verification | 26a2fc8f |
| 2 | WR-02: cancellation during normal shutdown skipped every remaining close, including the database | fixed: requires human verification | 6feac144 |

## Fixed Issues

### WR-02 (iteration 2): A cancellation during normal shutdown skips every remaining close, including the database

**Files modified:** `triggarr/search/scheduler.py`, `tests/test_scheduler.py`
**Commit:** 6feac144
**Status:** fixed: requires human verification (this changes how cancellation is handled, which is a logic change)
**Applied fix:**
- The shutdown `finally:` in `create_lifespan` now holds a cancellation instead of letting it end shutdown early,
  using the same pattern as the WR-01 startup fix.
  - If the cancellation lands during the search-lock drain, one warning is logged ("Shutdown: drain interrupted
    by cancellation; closing anyway"), and the clients and the database are still closed. The search cycle that
    holds the lock may still be writing; closing anyway is preferred over leaving the process hung.
  - Each client close and the database close now go through `_close_through_cancellation`. A cancellation during
    one close is logged once ("closing {label} was interrupted by cancellation; continuing") and every remaining
    close still runs.
- The shutdown order is unchanged: stop the scheduler, drain, close the clients, close the database last, then
  log "Search engine stopped". After that line, a held cancellation is re-raised, so cancellation is never
  swallowed. No bare `except:` was added. The 5-second per-step cap and log redaction are unchanged.
- The docstring of `_close_through_cancellation` now says it serves shutdown as well as failed-startup cleanup.
- The live-dict iteration (IN-04) was left unchanged, as instructed. The review's fix sketch included it.
- Two regression tests were written first, and both failed on the unfixed code:
  - `test_shutdown_cancelled_during_drain_still_closes_clients_and_database` holds the search lock, then cancels
    the lifespan task during the drain. Before the fix, no close ran (order `[]`). Now the order is
    `["radarr", "sonarr", "lidarr", "db"]`, all three clients are closed, the real aiosqlite worker thread stops,
    `CancelledError` propagates, and the last line is "Search engine stopped".
  - `test_shutdown_cancelled_during_client_close_still_closes_remaining_steps_database_last` cancels the lifespan
    during the first client close. Before the fix, only `["radarr"]` ran. Now every close runs with the database
    last, the worker thread stops, and `CancelledError` propagates.
- Verification: `uv run pytest tests/ -x -q` gave 3381 passed and 1 skipped. `uv run ruff check triggarr/ tests/`
  passed. The shutdown tests (15) passed in each of five repeated runs.

### WR-01 (iteration 1): Cancellation or interrupt during startup (or during cleanup) still leaks the database worker thread

**Files modified:** `triggarr/search/scheduler.py`, `tests/test_scheduler.py`
**Commit:** 26a2fc8f
**Status:** fixed: requires human verification (round 2 review judged it resolved)
**Applied fix:**
- The failed-startup handler catches `BaseException` instead of `Exception`. An ordinary `Exception` is logged as
  before. A cancellation or interrupt is logged by type name only.
- The new helper `_close_through_cancellation` holds a cancellation that arrives during a close step, so every
  remaining step still runs and the database is closed last. A cancellation while the scheduler is stopping is
  held the same way.
- The original exception is re-raised unchanged. A cancellation during cleanup of an ordinary startup error is
  raised `from` that error.
- Three regression tests were added, and all three failed on the unfixed code:
  `test_startup_cancelled_during_init_db_still_closes_database`,
  `test_startup_interrupt_during_client_construction_closes_earlier_clients`, and
  `test_startup_cleanup_cancelled_midway_still_closes_remaining_steps_database_last`.
- Verification at the time: 3379 passed and 1 skipped; ruff passed.

## Not fixed this round (owner decision: backlog)

IN-01 through IN-06 and SA-01/SA-02 from the round-2 review were left as they are. IN-05 also shows up on the new
shutdown path: a client whose close finished just before the cancellation arrived is still reported as "interrupted
by cancellation". The second WR-02 test documents this, because the Radarr client is in fact closed.

---

_Fixed: 2026-11-18T23:45:00Z_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 2_
