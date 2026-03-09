---
phase: 14-dashboard-observability
plan: 01
subsystem: ui
tags: [htmx, jinja2, sqlite, dashboard, search-history]

# Dependency graph
requires:
  - phase: 13-ci-search-diagnostics
    provides: "Search diagnostics logging and CI pipeline"
provides:
  - "X of Y position labels in app cards"
  - "Search outcome/detail columns in search_history table"
  - "Outcome badges in search log (green=searched, red=failed)"
  - "Failed searches recorded to database with error detail"
affects: [dashboard-observability]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Outcome/detail tracking pattern for search history entries"]

key-files:
  created: []
  modified:
    - fetcharr/templates/partials/app_card.html
    - fetcharr/templates/partials/search_log.html
    - fetcharr/db.py
    - fetcharr/search/engine.py
    - tests/test_db.py
    - tests/test_search.py
    - tests/test_web.py

key-decisions:
  - "Failed searches now insert into DB (previously only logged) -- enables outcome tracking"
  - "Outcome defaults to 'searched' for backward compatibility with pre-migration rows"

patterns-established:
  - "Migration pattern: ALTER TABLE with contextlib.suppress for idempotent column additions"
  - "Search outcome tracking: outcome/detail params on insert_search_entry"

requirements-completed: [WEBU-09, WEBU-11]

# Metrics
duration: 4min
completed: 2026-02-24
---

# Phase 14 Plan 01: Dashboard Observability Summary

**X of Y position labels on app cards and colored outcome badges in search log with failed-search DB persistence**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-24T20:54:09Z
- **Completed:** 2026-02-24T20:58:24Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- App card position labels now show "3 of 42" instead of "Position 3" for both missing and cutoff queues
- Search log entries display colored outcome badges (green for searched, red for failed)
- Failed searches are recorded in the database with truncated error detail text
- Hovering item name in search log shows detail tooltip when available
- 7 new tests covering outcome/detail DB operations, failed search logging, and UI rendering

## Task Commits

Each task was committed atomically:

1. **Task 1: Add X of Y position labels and search detail columns** - `03703c8` (feat)
2. **Task 2: Add tests for outcome/detail search history and position labels** - `b1d07be` (test)

## Files Created/Modified
- `fetcharr/templates/partials/app_card.html` - X of Y position format for missing/cutoff
- `fetcharr/templates/partials/search_log.html` - Outcome badge and detail tooltip
- `fetcharr/db.py` - outcome/detail columns, migration, updated insert/retrieve
- `fetcharr/search/engine.py` - Passes outcome/detail on all 8 insert_search_entry calls
- `tests/test_db.py` - 3 new tests for outcome/detail insert, defaults, migration compat
- `tests/test_search.py` - 2 new tests for failed search DB entries + updated per-item skip tests
- `tests/test_web.py` - 2 new tests for X-of-Y format and outcome badge display

## Decisions Made
- Failed searches now insert into DB with outcome="failed" and detail=str(exc)[:200] -- previously failures only logged to console, not persisted
- Outcome column defaults to NULL in migration; get_recent_searches returns "searched" for NULL rows (backward compat)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing per-item skip tests for new behavior**
- **Found during:** Task 1 (engine changes)
- **Issue:** Existing tests `test_run_radarr_cycle_per_item_skip` and `test_run_sonarr_cycle_per_item_skip` asserted only 1 DB entry (successful search), but failed searches now also insert entries
- **Fix:** Updated both tests to assert 2 DB entries with correct outcome values
- **Files modified:** tests/test_search.py
- **Verification:** All 150 tests pass
- **Committed in:** 03703c8 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix in existing tests)
**Impact on plan:** Necessary update to reflect new behavior. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Dashboard observability foundation complete
- Ready for plan 02 (remaining dashboard observability work)

---
*Phase: 14-dashboard-observability*
*Completed: 2026-02-24*
