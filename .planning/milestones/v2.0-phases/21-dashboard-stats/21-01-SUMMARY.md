---
phase: 21-dashboard-stats
plan: 01
subsystem: ui
tags: [htmx, jinja2, sqlite, dashboard, stats]

# Dependency graph
requires:
  - phase: 20-search-tracking
    provides: search_history and lifetime_stats tables, outcome tracking
provides:
  - Dashboard stats cards (Grab Rate, Movies, Episodes, Time to Grab)
  - get_dashboard_stats aggregate query function
  - /partials/stats-row htmx endpoint
  - resolved_at column on search_history (migration v5)
affects: [22-rename-triggarr]

# Tech tracking
tech-stack:
  added: []
  patterns: [aggregate stats query with row_factory, htmx polling partial for stats]

key-files:
  created:
    - fetcharr/templates/partials/stats_row.html
  modified:
    - fetcharr/db.py
    - fetcharr/web/routes.py
    - fetcharr/templates/dashboard.html
    - tests/test_web.py
    - tests/test_db.py

key-decisions:
  - "SUM(CASE WHEN) syntax for SQLite compatibility (no FILTER clause)"
  - "resolved_at column written in update_outcome_and_stats for time-to-grab calculation"
  - "Duration formatting as < 1m / Xm / Xh Ym with --- for no data"

patterns-established:
  - "Stats partial pattern: aggregate DB query -> format in route -> render htmx partial"

requirements-completed: [STATS-01, STATS-02, STATS-03, STATS-04, STATS-05]

# Metrics
duration: 7min
completed: 2026-03-06
---

# Phase 21 Plan 01: Dashboard Stats Summary

**4 stat cards (Grab Rate, Movies, Episodes, Time to Grab) with htmx auto-refresh, backed by aggregate DB queries and migration v5 resolved_at column**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-07T02:15:14Z
- **Completed:** 2026-03-07T02:22:22Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Dashboard displays 4 stat cards above app cards with grab rate, movies, episodes, and time-to-grab metrics
- Stats row auto-refreshes every 30 seconds via htmx polling
- Migration v5 adds resolved_at column; update_outcome_and_stats writes timestamp for time-to-grab calculation
- Empty state shows dash values when no tracking data exists

## Task Commits

Each task was committed atomically:

1. **Task 1: Add get_dashboard_stats DB function and stats partial route** - `0148ca9` (feat)
2. **Task 2: Create stats row template and wire into dashboard** - `053c817` (feat)

## Files Created/Modified
- `fetcharr/db.py` - Migration v5 (resolved_at column), get_dashboard_stats function, resolved_at in update_outcome_and_stats
- `fetcharr/web/routes.py` - _format_duration helper, /partials/stats-row endpoint, stats context in dashboard route
- `fetcharr/templates/partials/stats_row.html` - 4 stat cards in responsive grid with htmx polling
- `fetcharr/templates/dashboard.html` - Include stats_row.html before app cards
- `tests/test_web.py` - 7 new tests for stats cards, partial endpoint, empty state, duration formatting
- `tests/test_db.py` - Updated schema version assertions for migration v5

## Decisions Made
- Used SUM(CASE WHEN) syntax instead of FILTER clause for SQLite compatibility
- resolved_at timestamp written alongside outcome in update_outcome_and_stats (single transaction)
- Duration formatting: < 1m for sub-minute, Xm for minutes, Xh Ym for hours

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_db.py schema version assertions**
- **Found during:** Task 2 (template and tests)
- **Issue:** Two assertions in test_db.py checked `version == 4`, now incorrect after migration v5
- **Fix:** Updated both assertions to `version == 5`
- **Files modified:** tests/test_db.py
- **Verification:** 81 tests pass across test_web.py and test_db.py
- **Committed in:** 053c817 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary correctness fix for new migration. No scope creep.

## Issues Encountered
- Pre-existing test failure in test_search.py::test_radarr_cycle_logs_failed_search_to_db (detail field mismatch "Exception" vs "API timeout"). Not caused by this plan's changes -- verified by running test on pre-change commit.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Stats infrastructure complete and ready for any additional metrics
- resolved_at column enables future time-to-grab analytics
- Pre-existing test_search.py failure should be investigated separately

---
*Phase: 21-dashboard-stats*
*Completed: 2026-03-06*
