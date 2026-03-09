---
phase: 20-tracking-integration
plan: 02
subsystem: tracking
tags: [async, correlation, orchestrator, state-machine, httpx, aiosqlite]

# Dependency graph
requires:
  - phase: 20-tracking-integration
    provides: "get_trackable_entries and update_outcome_and_stats DB functions (Plan 01)"
  - phase: 19-tracking-infrastructure
    provides: "correlate_grabs pure function, GrabEvent model, client get_grab_history methods"
provides:
  - "run_tracking_check: async orchestrator that polls *arr history, correlates grabs, resolves outcomes"
affects: [20-tracking-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: ["group-by-item API batching to minimize *arr history calls", "three-state outcome machine (searched -> partial -> grabbed/unresolved)"]

key-files:
  created:
    - fetcharr/tracking.py
    - tests/test_tracking.py
  modified:
    - fetcharr/db.py

key-decisions:
  - "Added outcome column to get_trackable_entries query to distinguish searched vs partial entries for Sonarr logic"
  - "missing_count=None treated as 0 expected episodes -- any grab resolves to grabbed"
  - "Partial entries only get stat increments at terminal state (window expiry or upgrade to grabbed)"

patterns-established:
  - "Group entries by (app, item_id) for batched API calls -- one get_grab_history per unique item"
  - "Three-state Sonarr outcome machine: searched -> partial -> grabbed, with upgrade path before window expiry"
  - "Non-fatal error handling: httpx.HTTPError + pydantic.ValidationError caught per item group, entries stay current state"

requirements-completed: [TRACK-04, TRACK-05, TRACK-06]

# Metrics
duration: 2min
completed: 2026-02-25
---

# Phase 20 Plan 02: Tracking Orchestrator Summary

**Async tracking orchestrator that polls *arr grab history, runs correlation, and resolves search outcomes to grabbed/partial/unresolved with atomic stat updates**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T20:52:16Z
- **Completed:** 2026-02-25T20:55:08Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created run_tracking_check orchestrator that groups entries by (app, item_id) for efficient API batching
- Implemented Radarr binary outcome logic (grabbed/unresolved) and Sonarr three-state logic (grabbed/partial/unresolved) with partial->grabbed upgrade path
- 10 tests covering all outcome transitions, error handling, empty DB, and queue-type stat distinctions (228 total tests pass)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create fetcharr/tracking.py with run_tracking_check** - `b9e92c0` (feat)
2. **Task 2: Add tests for run_tracking_check** - `75788aa` (test)

## Files Created/Modified
- `fetcharr/tracking.py` - Tracking orchestrator with run_tracking_check async function (+195 lines)
- `tests/test_tracking.py` - 10 tests covering all outcome transitions and error handling (+342 lines)
- `fetcharr/db.py` - Added outcome column to get_trackable_entries query (+2 lines)

## Decisions Made
- Added outcome column to get_trackable_entries SELECT to distinguish searched vs partial entries (needed for Sonarr partial->grabbed upgrade logic)
- Sonarr entries with missing_count=None (e.g., from older entries) treat any grab as fully resolved ("grabbed")
- Partial Sonarr entries that are still within window and already marked partial get no-op (skip update, keep waiting for more grabs or window expiry)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added outcome column to get_trackable_entries query**
- **Found during:** Task 1 (tracking orchestrator implementation)
- **Issue:** get_trackable_entries did not return the outcome column, but Sonarr logic requires knowing if an entry is "searched" vs "partial" to determine the correct state transition
- **Fix:** Added `outcome` to the SELECT and dict output in get_trackable_entries
- **Files modified:** fetcharr/db.py
- **Verification:** ruff check passes, all 228 tests pass
- **Committed in:** b9e92c0 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential for Sonarr three-state logic correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- run_tracking_check ready for integration into the scheduler loop (Plan 03)
- Clean interface: accepts db + clients + window config, returns summary counts for logging
- All outcome transitions tested and verified against user decisions

---
*Phase: 20-tracking-integration*
*Completed: 2026-02-25*
