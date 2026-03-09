---
phase: 19-tracking-infrastructure
plan: 02
subsystem: correlation
tags: [correlation, datetime, dataclass, tdd, pure-functions, grab-matching]

# Dependency graph
requires:
  - phase: 19-tracking-infrastructure
    provides: "GrabEvent model and get_grab_history methods"
provides:
  - "SearchRecord dataclass for minimal search record representation"
  - "CorrelationResult dataclass with grab_count and matched_grabs"
  - "correlate_grabs pure function matching grabs to searches by time window"
affects: [20-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Most-recent-first processing for overlapping window credit", "Claimed-set pattern to prevent double-attribution of grabs"]

key-files:
  created:
    - fetcharr/correlation.py
    - tests/test_correlation.py
  modified: []

key-decisions:
  - "Most recent search claims grabs first via reverse-chronological processing order"
  - "Inclusive boundary: grabs at exactly search_time + window are matched"
  - "Claimed-set prevents double-attribution when multiple search windows overlap"

patterns-established:
  - "Pure correlation functions with no I/O -- Phase 20 handles DB integration"
  - "SearchRecord as lightweight DB-row extraction for correlation input"

requirements-completed: [TRACK-03]

# Metrics
duration: 2min
completed: 2026-02-25
---

# Phase 19 Plan 02: Grab Correlation Logic Summary

**Pure correlate_grabs function matching *arr grab events to fetcharr searches using configurable time windows with most-recent-search-gets-credit semantics**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T18:48:26Z
- **Completed:** 2026-02-25T18:50:29Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- SearchRecord and CorrelationResult dataclasses for typed correlation I/O
- correlate_grabs pure function: parses grab dates, processes searches most-recent-first, claims grabs via set tracking
- 11 comprehensive tests covering: within/outside window, exact boundary, before-search exclusion, multiple grabs, most-recent-search-gets-credit, non-overlapping windows, empty inputs, Sonarr missing_count
- TDD approach: RED phase (failing tests) then GREEN phase (working implementation)

## Task Commits

Each task was committed atomically:

1. **Task 1: Define correlation data structures and write failing tests** - `0df263e` (test)
2. **Task 2: Implement correlate_grabs to pass all tests** - `abed893` (feat)

## Files Created/Modified
- `fetcharr/correlation.py` - Pure correlation module with SearchRecord, CorrelationResult, correlate_grabs, and _parse_iso helper
- `tests/test_correlation.py` - 11 unit tests with synthetic data covering all correlation edge cases

## Decisions Made
- Most recent search claims grabs first by sorting searches descending by searched_at and using a claimed-set to prevent double-attribution
- Inclusive boundary per user decision: grabs at exactly search_time + tracking_window are matched
- Pure functions only (no DB, no I/O) -- Phase 20 provides the integration layer
- Removed unused imports in RED phase to satisfy ruff lint (timedelta re-added in GREEN phase when needed)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed ruff F401 lint violations in RED phase**
- **Found during:** Task 1 (test file creation)
- **Issue:** `timedelta` imported but unused in stub, `CorrelationResult` imported but unused in tests
- **Fix:** Removed unused imports from stub (timedelta re-added in Task 2) and test file
- **Files modified:** fetcharr/correlation.py, tests/test_correlation.py
- **Verification:** `uv run ruff check` passes
- **Committed in:** 0df263e (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Minor lint fix, no scope impact.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- correlate_grabs ready for Phase 20 integration into search cycle
- Phase 20 will read search_history from DB, call get_grab_history, then pass results to correlate_grabs
- CorrelationResult.grab_count enables outcome determination (grabbed/partial/unresolved)

## Self-Check: PASSED

All files exist. All commits verified (0df263e, abed893).

---
*Phase: 19-tracking-infrastructure*
*Completed: 2026-02-25*
