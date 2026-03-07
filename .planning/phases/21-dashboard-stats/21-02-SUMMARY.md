---
phase: 21-dashboard-stats
plan: 02
subsystem: ui
tags: [htmx, jinja2, tailwind, settings, outcome-badges]

# Dependency graph
requires:
  - phase: 21-dashboard-stats/01
    provides: "Dashboard stats cards, get_dashboard_stats DB function, stats_row partial"
provides:
  - "Color-coded outcome badges (grabbed=green, partial=amber, unresolved=gray) in history and search log"
  - "5-outcome filter pills in history filter bar"
  - "4 new General config inputs in settings form (tracking_window, request_timeout, page_size, max_history_rows)"
  - "Settings save handler reads new fields from form data"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Traffic-light outcome badge scheme: grabbed=green, partial=amber, unresolved=gray, failed=red, searched=blue"
    - "Tooltip on new outcome badges explaining each state"

key-files:
  created: []
  modified:
    - fetcharr/templates/partials/history_results.html
    - fetcharr/templates/partials/search_log.html
    - fetcharr/templates/settings.html
    - fetcharr/web/routes.py
    - tests/test_web.py

key-decisions:
  - "request_timeout uses safe_int (returns int) -- Pydantic coerces to float for GeneralConfig.request_timeout"
  - "tracking_delay_seconds remains preserved (not user-editable) per CONTEXT.md"

patterns-established:
  - "5-way outcome badge conditional with tooltips for grabbed/partial/unresolved"
  - "Filter pill colors match badge colors for each outcome"

requirements-completed: [STATS-01, STATS-02, STATS-03, STATS-04, STATS-05]

# Metrics
duration: 11min
completed: 2026-03-06
---

# Phase 21 Plan 02: Dashboard Stats UI Summary

**Color-coded outcome badges with tooltips in history/search log, 5-outcome filter pills, and 4 new General config inputs in settings form**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-07T02:24:44Z
- **Completed:** 2026-03-07T02:35:43Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- All 5 outcome values render with traffic-light colored badges and tooltips in both history and search log
- History filter bar extended from 2 to 5 outcome pills with matching colors
- Settings form has 4 new General inputs: max_history_rows, request_timeout, page_size, tracking_window_minutes
- Settings save handler reads new fields from form data with safe_int validation
- 3 new tests added covering settings rendering, save, and outcome badge colors

## Task Commits

Each task was committed atomically:

1. **Task 1: Add outcome badges with colors and tooltips to history and search log templates** - `365e6ad` (feat)
2. **Task 2: Wire new config fields into settings form and save handler** - `3170893` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified
- `fetcharr/templates/partials/history_results.html` - 5-way outcome badge, tooltips, 5 filter pills
- `fetcharr/templates/partials/search_log.html` - 5-way outcome badge with tooltips
- `fetcharr/templates/settings.html` - 4 new General config inputs with hints
- `fetcharr/web/routes.py` - save_settings reads new fields from form data
- `tests/test_web.py` - 3 new tests for settings fields, save, outcome badges

## Decisions Made
- request_timeout uses safe_int (returns int) -- Pydantic coerces to float for GeneralConfig.request_timeout
- tracking_delay_seconds remains preserved (not user-editable) per CONTEXT.md

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing test failure in tests/test_search.py::test_radarr_cycle_logs_failed_search_to_db (detail stores exception type name instead of message) -- unrelated to this plan's changes, logged to deferred-items.md

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 21 UI complete: stats cards, outcome badges, filter pills, config form
- All dashboard tracking features are now visible and configurable through the web UI

## Self-Check: PASSED

All files exist, all commits verified, all must_have artifacts contain required patterns.

---
*Phase: 21-dashboard-stats*
*Completed: 2026-03-06*
