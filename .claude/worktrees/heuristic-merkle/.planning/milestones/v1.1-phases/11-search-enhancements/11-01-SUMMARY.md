---
phase: 11-search-enhancements
plan: 01
subsystem: search
tags: [batch-cap, safety-ceiling, config, settings-ui]

# Dependency graph
requires:
  - phase: 04-search-engine
    provides: search cycle orchestrators and batch slicing
  - phase: 06-settings-ui
    provides: settings page with form fields and validation
provides:
  - hard_max_per_cycle config field on GeneralConfig
  - cap_batch_sizes pure function for proportional batch capping
  - Settings UI field for hard max editing
affects: [search-engine, settings-ui]

# Tech tracking
tech-stack:
  added: []
  patterns: [proportional-split-cap, pre-slice-batch-capping]

key-files:
  created: []
  modified:
    - fetcharr/models/config.py
    - fetcharr/config.py
    - fetcharr/search/engine.py
    - fetcharr/web/routes.py
    - fetcharr/templates/settings.html
    - tests/test_search.py

key-decisions:
  - "Proportional split for cap: missing gets floor(missing/total*max), cutoff gets remainder"
  - "Cap applied before slicing, not after -- affects batch size not post-slice trimming"

patterns-established:
  - "Pre-slice cap pattern: compute effective limits before slice_batch calls in cycle functions"

requirements-completed: [SRCH-12]

# Metrics
duration: 2min
completed: 2026-02-24
---

# Phase 11 Plan 01: Hard Max Per Cycle Summary

**Global hard_max_per_cycle safety cap with proportional batch splitting, settings UI, and 5 edge-case tests**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-24T18:16:42Z
- **Completed:** 2026-02-24T18:19:29Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added hard_max_per_cycle field to GeneralConfig (default 0 = unlimited) and DEFAULT_CONFIG template
- Created cap_batch_sizes pure function with proportional splitting and integrated into both run_radarr_cycle and run_sonarr_cycle
- Added settings UI input field (0-1000 range) with form persistence via GET/POST handlers
- Added 5 tests covering unlimited, no-cap-needed, proportional split, one-zero queue, and very-small-max edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1: Add hard_max_per_cycle to config and engine** - `e2c10a7` (feat)
2. **Task 2: Add hard max to settings UI and write tests** - `2fad66a` (feat)

## Files Created/Modified
- `fetcharr/models/config.py` - Added hard_max_per_cycle field to GeneralConfig
- `fetcharr/config.py` - Added commented hard_max_per_cycle to DEFAULT_CONFIG template
- `fetcharr/search/engine.py` - Added cap_batch_sizes function, integrated into both cycle functions
- `fetcharr/web/routes.py` - Added hard_max_per_cycle to settings GET context and POST handler
- `fetcharr/templates/settings.html` - Added Hard Max Items Per Cycle input in General section
- `tests/test_search.py` - Added 5 tests for cap_batch_sizes

## Decisions Made
- Proportional split for cap: missing gets floor(missing/total*max), cutoff gets remainder -- simple and predictable
- Cap applied before slicing (affects batch size computation, not post-slice trimming) -- cleaner integration with existing cycle logic

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed lint E501 line-too-long in engine.py**
- **Found during:** Task 2 (verification)
- **Issue:** Two lines in engine.py exceeded 120 character limit due to long settings attribute comparisons
- **Fix:** Stored original values in local variables before cap, compared against locals instead of full settings paths
- **Files modified:** fetcharr/search/engine.py
- **Verification:** ruff check passes cleanly
- **Committed in:** 2fad66a (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor style fix required for lint compliance. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Hard max cap feature complete and tested
- Ready for 11-02 plan (next search enhancement)
- All 120 tests pass, no lint violations

---
*Phase: 11-search-enhancements*
*Completed: 2026-02-24*

## Self-Check: PASSED

All 7 files verified present. Both commits (e2c10a7, 2fad66a) confirmed in git log. cap_batch_sizes import and GeneralConfig.hard_max_per_cycle field validated.
