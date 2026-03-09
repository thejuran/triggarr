---
phase: 17-foundation-db-preparation
plan: 03
subsystem: database
tags: [aiosqlite, shared-connection, caller-wiring, page-size, tracking-fields, WAL]

# Dependency graph
requires:
  - phase: 17-foundation-db-preparation
    provides: "GeneralConfig fields (plan 01) and shared-connection db.py signatures (plan 02)"
provides:
  - "Shared WAL connection lifecycle in lifespan (open/close on app.state.db)"
  - "Engine cycles accept Connection, pass item_id/season_number/missing_count/max_rows"
  - "deduplicate_to_seasons includes episode_count per season"
  - "Routes use app.state.db for all db function calls"
  - "Settings save preserves new config fields not yet in UI form"
  - "ArrClient accepts page_size parameter, uses as get_paginated default"
  - "Client construction passes timeout and page_size from settings"
affects: [18-connection-manager, 19-radarr-tracking, 20-sonarr-tracking]

# Tech tracking
tech-stack:
  added: []
  patterns: [shared WAL connection lifecycle, configurable page_size on client, tracking fields in cycle functions]

key-files:
  created: [tests/test_clients.py]
  modified:
    - fetcharr/search/scheduler.py
    - fetcharr/search/engine.py
    - fetcharr/web/routes.py
    - fetcharr/clients/base.py
    - fetcharr/clients/radarr.py
    - fetcharr/clients/sonarr.py
    - tests/test_search.py
    - tests/test_web.py
    - tests/test_clients.py

key-decisions:
  - "Lifespan sets WAL mode and synchronous=NORMAL on shared connection for concurrent reads"
  - "Settings save preserves new config values from current_settings since form UI is deferred"
  - "RadarrClient and SonarrClient __init__ updated to pass through page_size parameter"

patterns-established:
  - "app.state.db holds the shared aiosqlite.Connection (not db_path)"
  - "Cycle functions accept db: aiosqlite.Connection as 4th parameter"
  - "Client constructors accept timeout and page_size from settings.general"

requirements-completed: [DEBT-04, DEBT-07, DEBT-08, DEBT-03]

# Metrics
duration: 9min
completed: 2026-02-24
---

# Phase 17 Plan 03: Caller Wiring Summary

**Shared WAL connection wired through lifespan/engine/routes, configurable page_size and timeout on clients, tracking fields passed to insert_search_entry in all cycle functions**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-25T01:06:15Z
- **Completed:** 2026-02-25T01:15:53Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments
- Lifespan opens shared aiosqlite connection with WAL mode, stores on app.state.db, closes in teardown
- Engine cycle functions accept Connection and pass item_id, season_number, missing_count, max_rows to insert_search_entry
- deduplicate_to_seasons now tracks episode_count per season for missing_count correlation
- Routes use app.state.db instead of app.state.db_path for all database calls
- ArrClient, RadarrClient, and SonarrClient accept configurable page_size and timeout from settings
- Settings save handler preserves new config fields not yet exposed in the UI form
- All 182 tests pass with the new shared-connection pattern

## Task Commits

Each task was committed atomically:

1. **Task 1: Update lifespan and engine to use shared connection with tracking fields** - `c3e8819` (feat)
2. **Task 2: Update routes and client to use shared connection and configurable settings** - `83d4388` (feat)
3. **Task 3: Update all tests for new caller signatures** - `db78fe9` (test)

## Files Created/Modified
- `fetcharr/search/scheduler.py` - Shared WAL connection lifecycle in lifespan, client construction with timeout/page_size
- `fetcharr/search/engine.py` - Cycle functions accept Connection, pass tracking fields, deduplicate_to_seasons with episode_count
- `fetcharr/web/routes.py` - Routes use app.state.db, settings save preserves new config fields, client creation with timeout/page_size
- `fetcharr/clients/base.py` - ArrClient accepts page_size, uses as get_paginated default
- `fetcharr/clients/radarr.py` - RadarrClient passes through page_size parameter
- `fetcharr/clients/sonarr.py` - SonarrClient passes through page_size parameter
- `tests/test_search.py` - All cycle tests use aiosqlite.Connection, deduplicate tests verify episode_count
- `tests/test_web.py` - test_app fixture uses shared connection, mock settings include new general config
- `tests/test_clients.py` - New page_size default and custom tests for ArrClient

## Decisions Made
- Lifespan sets WAL journal mode and synchronous=NORMAL on the shared connection for safe concurrent reads
- Settings save preserves new config values (max_history_rows, request_timeout, page_size, etc.) from current_settings since form UI is deferred to a future phase
- RadarrClient and SonarrClient __init__ updated to accept and pass through page_size parameter to avoid TypeError when constructing clients

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] RadarrClient/SonarrClient missing page_size parameter**
- **Found during:** Task 3 (test run revealed TypeError)
- **Issue:** Subclass constructors only accepted (base_url, api_key, timeout) but callers now pass page_size
- **Fix:** Added page_size parameter to RadarrClient.__init__ and SonarrClient.__init__, passing through to super().__init__
- **Files modified:** fetcharr/clients/radarr.py, fetcharr/clients/sonarr.py
- **Verification:** All 182 tests pass, including save_settings client recreation
- **Committed in:** db78fe9 (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix to propagate page_size through class hierarchy. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All Phase 17 plans complete: config fields (01), DB migration system (02), and caller wiring (03)
- Application is fully wired end-to-end with shared connection and new config fields
- Ready for Phase 18 (connection manager) and downstream tracking phases (19, 20)
- No blockers for downstream plans

## Self-Check: PASSED

All files exist. All commits verified (c3e8819, 83d4388, db78fe9).

---
*Phase: 17-foundation-db-preparation*
*Completed: 2026-02-24*
