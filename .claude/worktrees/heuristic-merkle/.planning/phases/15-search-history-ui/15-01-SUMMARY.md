---
phase: 15-search-history-ui
plan: 01
subsystem: ui
tags: [htmx, jinja2, sqlite, pagination, filtering]

# Dependency graph
requires:
  - phase: 14-dashboard-observability
    provides: outcome column in search_history table
provides:
  - get_search_history() with dynamic filtering and pagination
  - /history page with filter bar, results table, pagination
  - /partials/history-results htmx partial endpoint
  - History nav link in base.html
affects: [15-02]

# Tech tracking
tech-stack:
  added: []
  patterns: [toggle-pill filter pattern with htmx partial swaps, dynamic SQL WHERE clause building]

key-files:
  created:
    - fetcharr/templates/history.html
    - fetcharr/templates/partials/history_results.html
  modified:
    - fetcharr/db.py
    - fetcharr/web/routes.py
    - fetcharr/templates/base.html

key-decisions:
  - "Used COALESCE(outcome, 'searched') in SQL filter to handle pre-migration NULL outcome rows"
  - "Filter pills toggle via URL query param manipulation -- each pill computes its toggled URL in Jinja2"
  - "Text search uses 300ms debounce with hx-vals to carry current filter state"

patterns-established:
  - "Toggle pill filter: each pill link builds URL with current state minus/plus its value, resets page to 1"
  - "Pagination with ellipsis window: show first, last, and 2-page window around current page"

requirements-completed: [SRCH-14]

# Metrics
duration: 2min
completed: 2026-02-24
---

# Phase 15 Plan 01: Search History Backend & UI Summary

**Paginated search history page with toggle-pill filters for app/queue/outcome and text search, all via htmx partial swaps**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-24T21:42:32Z
- **Completed:** 2026-02-24T21:44:59Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- `get_search_history()` backend function with dynamic WHERE clause filtering, parameterized queries, and pagination
- `/history` page accessible from nav bar with filter bar, results table, and pagination controls
- Toggle pill buttons for app (Radarr/Sonarr), queue type (missing/cutoff), and outcome (searched/failed) filters
- Text search with 300ms debounce for real-time filtering by item name
- Pagination with prev/next controls and page number window with ellipsis for large page counts
- Entry rows match dashboard search_log styling exactly (app badges, outcome badges, timestamps)
- Empty state message when no history exists

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend query function and routes** - `daff120` (feat)
2. **Task 2: Templates -- history page, results partial, nav update** - `7eb1af1` (feat)

## Files Created/Modified
- `fetcharr/db.py` - Added `get_search_history()` with filtering, pagination, and total count
- `fetcharr/web/routes.py` - Added `/history` page route, `/partials/history-results` partial route, and `_split_filter_param` helper
- `fetcharr/templates/base.html` - Added History nav link with active state block
- `fetcharr/templates/history.html` - Full page template extending base with correct nav highlighting
- `fetcharr/templates/partials/history_results.html` - Filter bar, results table, pagination partial

## Decisions Made
- Used `COALESCE(outcome, 'searched')` in SQL filter to correctly handle pre-migration rows with NULL outcome
- Filter pills toggle via URL query param manipulation computed in Jinja2 -- each pill builds the full toggled URL
- Text search uses `hx-vals` to carry current filter state alongside the search input value
- Pagination window shows 2 pages around current page with ellipsis for large ranges

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- History page backend and frontend complete, ready for Phase 15 Plan 02 (tests/polish)
- All filter/pagination interactions use htmx partial swaps without full page reloads

## Self-Check: PASSED

All 5 files verified present. Both commits (`daff120`, `7eb1af1`) verified in git log.

---
*Phase: 15-search-history-ui*
*Completed: 2026-02-24*
