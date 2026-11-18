---
phase: 89-startup-shutdown-resource-cleanup
fixed_at: 2026-11-18T23:40:00Z
review_path: .planning/phases/89-startup-shutdown-resource-cleanup/89-REVIEW.md
iteration: 1
findings_in_scope: 1
fixed: 1
skipped: 0
rejected: 0
status: all_fixed
---

# Phase 89: Code Review Fix Report

**Fixed at:** 2026-11-18T23:40:00Z
**Source review:** .planning/phases/89-startup-shutdown-resource-cleanup/89-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 1 (WR-01; scope was critical_warning, and IN-01..IN-04 and SA-01/SA-02 were excluded by the orchestrator)
- Fixed: 1
- Skipped: 0
- Rejected: 0

## Fixed Issues

### WR-01: Cancellation or interrupt during startup (or during cleanup) still leaks the database worker thread

**Files modified:** `triggarr/search/scheduler.py`, `tests/test_scheduler.py`
**Commit:** 26a2fc8f
**Status:** fixed: requires human verification (this changes how errors are handled, which is a logic change)
**Applied fix:**
- The failed-startup handler in `create_lifespan` now catches `BaseException` instead of `Exception`. An ordinary
  `Exception` is logged exactly as before (sanitized cause, then "Startup failed; closed ... before exiting").
  A cancellation or interrupt is logged by exception type only: "Startup interrupted (CancelledError); closing what
  was opened", then "Startup interrupted; closed ... before exiting".
- A new helper, `_close_through_cancellation`, wraps `_safe_close`. If the caller is cancelled during a close step,
  the helper logs one warning ("closing {label} was interrupted by cancellation; continuing") and returns the
  cancellation instead of raising it. The cleanup loop then still attempts every remaining client close and closes
  the database last. Cancellation while the scheduler is stopping is held the same way.
- After cleanup, the original exception is re-raised unchanged with a bare `raise`. If the original was an ordinary
  `Exception` and a cancellation arrived during cleanup, the cancellation is raised `from` the original error, so
  cancellation is never swallowed. No bare `except:` was added. The 5-second per-step cap and the log redaction are
  unchanged.
- Three regression tests were added, and all three failed on the unfixed code:
  - `test_startup_cancelled_during_init_db_still_closes_database` cancels the lifespan task while it awaits
    `init_db`. Before the fix the real aiosqlite worker thread stayed alive (`[True]`); now it stops (`[False]`).
  - `test_startup_interrupt_during_client_construction_closes_earlier_clients` raises a non-`Exception`
    `BaseException` partway through building the clients. Before the fix neither client was closed; now both are,
    and the database worker thread stops.
  - `test_startup_cleanup_cancelled_midway_still_closes_remaining_steps_database_last` cancels the lifespan during
    the first close step. Before the fix the close order was `["sonarr"]`; now it is
    `["sonarr", "radarr", "db"]`, the worker thread stops, and `CancelledError` still propagates.
- Verification: `uv run pytest tests/ -x -q` gave 3379 passed and 1 skipped. `uv run ruff check triggarr/ tests/`
  passed. The three new tests passed in each of five repeated runs.

**IN-03 note:** `_safe_close` was not changed, and it still re-raises `CancelledError`. The WR-01 fix relies on that
behavior, and its docstring is still inaccurate in the same way as before ("never raise"), so the fix does not make
the docstring more wrong or more right. It was left for IN-03, as instructed.

**Not covered (outside WR-01's cited lines):** the normal shutdown path (`finally:` after `yield`) still stops its
remaining closes if it is cancelled partway through. The finding cited only the startup lines.

---

_Fixed: 2026-11-18T23:40:00Z_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 1_
