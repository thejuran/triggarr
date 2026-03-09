---
phase: 28-fix-code-review-findings-from-v2-2
plan: 01
subsystem: search, ui
tags: [radarr, skip-badge, unreleased-filter, loguru, htmx]

# Dependency graph
requires:
  - phase: 27-dashboard-display
    provides: missing_eligible state field and skip badge template
provides:
  - missing_monitored state field for accurate skip badge math
  - INFO-level skip summary log per Radarr cycle
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "missing_monitored intermediate count between filter_monitored and filter_unreleased"

key-files:
  created: []
  modified:
    - triggarr/search/engine.py
    - triggarr/web/routes.py
    - triggarr/templates/partials/app_card.html
    - tests/test_search.py
    - tests/test_web.py

key-decisions:
  - "missing_monitored set unconditionally after filter_monitored, before conditional unreleased filter"

patterns-established:
  - "Skip badge math uses missing_monitored - missing_eligible (not missing_count - missing_eligible)"

requirements-completed: []

# Metrics
duration: 7min
completed: 2026-03-09
---

# Phase 28 Plan 01: Fix Skip Badge Math and Add INFO Skip Log Summary

**Fixed skip badge to use missing_monitored (post-filter_monitored) instead of raw missing_count, and added INFO log when unreleased movies are skipped**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-03-09T12:58:34Z
- **Completed:** 2026-03-09T13:05:06Z
- **Tasks:** 1 (TDD)
- **Files modified:** 5

## Accomplishments
- Skip badge now accurately shows only unreleased skip count (missing_monitored - missing_eligible), not inflated by unmonitored items
- INFO-level log emitted once per Radarr cycle when unreleased items are skipped, silent when none filtered
- "X of Y items" display now uses missing_monitored as denominator instead of raw missing_count
- All 302 tests pass, no ruff violations

## Task Commits

Each task was committed atomically:

1. **Task 1: Add missing_monitored tracking and INFO skip log** (TDD)
   - RED: `8f59ee4` (test) - Failing tests for missing_monitored and INFO log
   - GREEN: `14b6282` (feat) - Implementation making all tests pass

## Files Created/Modified
- `triggarr/search/engine.py` - Added missing_monitored state field after filter_monitored; INFO log when unreleased items skipped
- `triggarr/web/routes.py` - Added missing_monitored to _build_app_context template dict
- `triggarr/templates/partials/app_card.html` - Skip badge uses missing_monitored; "X of Y" display uses monitored count
- `tests/test_search.py` - Tests for missing_monitored tracking, INFO log presence/absence
- `tests/test_web.py` - Tests for skip badge math using missing_monitored, eligible_total display

## Decisions Made
- missing_monitored set unconditionally after filter_monitored (even when skip_unreleased=False), so it always equals missing_eligible when no unreleased filter runs

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Skip badge math fix complete; remaining code review findings (if any) can proceed independently

---
*Phase: 28-fix-code-review-findings-from-v2-2*
*Completed: 2026-03-09*
