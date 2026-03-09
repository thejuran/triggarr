---
phase: 17-foundation-db-preparation
plan: 02
subsystem: database
tags: [aiosqlite, migration, sqlite, schema-versioning, tracking, pruning]

# Dependency graph
requires:
  - phase: none
    provides: existing db.py with connection-per-operation pattern
provides:
  - Shared-connection db module (all functions accept aiosqlite.Connection)
  - Versioned schema migration system (4 migrations, backup-before-migrate)
  - Tracking columns (item_id, season_number, missing_count) on search_history
  - lifetime_stats table with Radarr/Sonarr seed rows
  - Tracking-aware pruning (preserves outcome='searched' rows)
  - Backfill migration for legacy NULL outcome rows
affects: [17-03-PLAN, 18-config-tracking-settings, 19-radarr-tracking, 20-sonarr-tracking]

# Tech tracking
tech-stack:
  added: [shutil (stdlib)]
  patterns: [shared-connection signatures, sequential schema migration, tracking-aware pruning]

key-files:
  created: []
  modified: [fetcharr/db.py, tests/test_db.py]

key-decisions:
  - "Backup file uses Path.with_suffix replacing .db extension (e.g. test.v0-backup not test.db.v0-backup)"
  - "MIGRATIONS dict declared empty at module top, reassigned after migration functions are defined"
  - "Row factory set/reset around queries to avoid side effects on shared connection"

patterns-established:
  - "Shared-connection pattern: all db.py functions accept db: aiosqlite.Connection as first parameter"
  - "Migration registry: MIGRATIONS dict maps version int to (description, async callable) tuple"
  - "Test helper: _init_test_db(tmp_path) creates fresh db with all migrations applied"

requirements-completed: [DEBT-04, TRACK-08, DEBT-03]

# Metrics
duration: 3min
completed: 2026-02-24
---

# Phase 17 Plan 02: DB Migration System Summary

**Shared-connection db.py rewrite with 4-step versioned migration system, tracking columns, lifetime_stats table, and tracking-aware pruning**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-25T01:00:27Z
- **Completed:** 2026-02-25T01:03:38Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Rewrote all db.py public functions to accept aiosqlite.Connection instead of Path (DEBT-04)
- Built versioned schema migration system with 4 migrations: outcome columns, tracking columns, lifetime_stats table, and backfill
- Tracking-aware pruning preserves pending rows (outcome='searched') while capping resolved rows at max_rows (DEBT-03)
- Added item_id, season_number, missing_count columns for tracking correlation (TRACK-08)
- Created lifetime_stats table with Radarr/Sonarr seed rows for downstream stats tracking
- Backup-before-migrate creates safety copy before running schema changes
- Comprehensive test coverage: 26 tests including 6 new tests for migration system and tracking features

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite db.py with migration system and shared-connection signatures** - `fefa8fe` (feat)
2. **Task 2: Update test_db.py for new signatures and migration system** - `49d1aa9` (test)

## Files Created/Modified
- `fetcharr/db.py` - Shared-connection db module with migration system, tracking columns, lifetime_stats, tracking-aware pruning
- `tests/test_db.py` - Updated all tests for new signatures, added 6 new tests for migration system and tracking features

## Decisions Made
- Backup file naming uses `Path.with_suffix()` which replaces the `.db` extension (e.g. `test.v0-backup` not `test.db.v0-backup`) -- this is a natural consequence of the stdlib API
- MIGRATIONS dict is declared empty at module top to satisfy the type hint, then reassigned after migration functions are defined to avoid forward references
- `db.row_factory` is set to `aiosqlite.Row` before queries and reset to `None` after to avoid side effects on the shared connection

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- db.py is fully refactored with shared-connection signatures -- Plan 03 can update all callers
- Migration system is in place for future schema changes
- Callers (engine.py, scheduler.py, routes.py) still use the old Path-based signatures and need updating in Plan 03
- No blockers for downstream plans

---
*Phase: 17-foundation-db-preparation*
*Completed: 2026-02-24*
