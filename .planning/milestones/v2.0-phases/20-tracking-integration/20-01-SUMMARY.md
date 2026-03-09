---
phase: 20-tracking-integration
plan: 01
subsystem: database
tags: [aiosqlite, tracking, atomic-transactions, lifetime-stats]

# Dependency graph
requires:
  - phase: 19-tracking-infrastructure
    provides: "lifetime_stats table, search_history tracking columns"
provides:
  - "get_trackable_entries: query pending search entries for tracking resolution"
  - "update_outcome_and_stats: atomic outcome + lifetime stats update"
affects: [20-tracking-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: ["atomic multi-table update in single transaction", "column-name validation for dynamic SQL"]

key-files:
  created: []
  modified:
    - fetcharr/db.py
    - tests/test_db.py

key-decisions:
  - "frozenset for allowed stat columns prevents SQL injection via dynamic column names"
  - "Single db.commit() after both UPDATE statements ensures atomicity"
  - "noqa S608 suppression for dynamic SQL since column names are validated against allowlist"

patterns-established:
  - "Allowlist validation: dynamic SQL column names checked against frozenset before execution"
  - "Atomic multi-table updates: outcome + stats updated in single transaction with one commit"

requirements-completed: [TRACK-04, TRACK-05, TRACK-06]

# Metrics
duration: 2min
completed: 2026-02-25
---

# Phase 20 Plan 01: Tracking DB Queries Summary

**Async DB functions for querying trackable search entries and atomically updating outcomes with lifetime stat increments**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T20:48:37Z
- **Completed:** 2026-02-25T20:50:16Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added get_trackable_entries to query search_history for entries with outcome IN (searched, partial) and non-null item_id, ordered oldest-first
- Added update_outcome_and_stats for atomic outcome update + lifetime_stats increment in a single transaction
- 9 new tests covering happy path, edge cases, ordering, and error validation (35 total tests pass)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add get_trackable_entries and update_outcome_and_stats to db.py** - `50a22a2` (feat)
2. **Task 2: Add tests for get_trackable_entries and update_outcome_and_stats** - `f0b48c4` (test)

## Files Created/Modified
- `fetcharr/db.py` - Added get_trackable_entries and update_outcome_and_stats functions (+100 lines)
- `tests/test_db.py` - Added 9 tests for new DB functions (+192 lines)

## Decisions Made
- Used frozenset (_ALLOWED_STAT_COLUMNS) for column validation to prevent SQL injection via dynamic SET clause
- Single db.commit() at end of update_outcome_and_stats ensures both outcome and stats are atomic
- Added noqa S608 for the dynamic SQL in update_outcome_and_stats since column names are validated against allowlist

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- get_trackable_entries and update_outcome_and_stats ready for consumption by tracking orchestrator (Plan 02)
- Clean data layer interface: Plan 02 can query pending entries and persist outcomes without direct SQL

---
*Phase: 20-tracking-integration*
*Completed: 2026-02-25*
