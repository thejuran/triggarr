---
phase: 13-ci-search-diagnostics
plan: 02
subsystem: search
tags: [loguru, diagnostics, sonarr, radarr, api-version]

# Dependency graph
requires:
  - phase: 13-ci-search-diagnostics
    provides: "CI pipeline (plan 01)"
provides:
  - "Sonarr API version detection (v3/v4) at startup"
  - "Per-cycle diagnostic summary logging for both Radarr and Sonarr"
affects: [search, startup, troubleshooting]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Per-cycle diagnostic logging with fetched/searched/skipped counters", "API version detection with graceful fallback"]

key-files:
  created: []
  modified:
    - fetcharr/clients/sonarr.py
    - fetcharr/startup.py
    - fetcharr/search/engine.py
    - tests/test_startup.py
    - tests/test_search.py

key-decisions:
  - "Version detection uses /api/v3/system/status (same endpoint as validate_connection) -- no extra network call needed"
  - "Defensive try/except around detect_api_version in startup.py to prevent version detection from breaking startup"
  - "Fetched count uses raw API item counts before filtering for pageSize truncation diagnosis"

patterns-established:
  - "Diagnostic cycle summary: consistent format across both apps with duration/fetched/searched/skipped"
  - "Loguru sink capture in tests: io.StringIO + logger.add/remove for verifying log output"

requirements-completed: [SRCH-15, SRCH-16]

# Metrics
duration: 4min
completed: 2026-02-24
---

# Phase 13 Plan 02: Search Diagnostics Summary

**Sonarr v3/v4 API version detection at startup with per-cycle diagnostic summary logging (duration, fetched, searched, skipped) for both Radarr and Sonarr**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-24T20:19:14Z
- **Completed:** 2026-02-24T20:23:06Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- Sonarr API version (v3 or v4) detected and logged at startup after successful connection validation
- Both Radarr and Sonarr cycles log a diagnostic summary line with cycle duration, total items fetched (raw count for pageSize diagnosis), items searched, and items skipped
- All diagnostic logs at INFO level, consistent format across both apps
- 9 new tests: 6 for version detection (3 unit + 3 integration), 3 for diagnostic cycle logging

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Sonarr API version detection** - `d11c167` (feat)
2. **Task 2: Add per-cycle diagnostic summary logging** - `e5956ef` (feat)
3. **Task 3: Add tests for diagnostic cycle logging** - `569353d` (test)

## Files Created/Modified
- `fetcharr/clients/sonarr.py` - Added detect_api_version method (v3/v4 from version string)
- `fetcharr/startup.py` - Call version detection after Sonarr connection validation, log result
- `fetcharr/search/engine.py` - Added time import, cycle_start timing, searched/skipped counters, summary log for both run_radarr_cycle and run_sonarr_cycle
- `tests/test_startup.py` - 6 new tests for version detection (unit + integration)
- `tests/test_search.py` - 3 new tests for diagnostic cycle summary logging

## Decisions Made
- Version detection uses the same /api/v3/system/status endpoint already called by validate_connection, parsed as raw JSON (no Pydantic model needed for this simple check)
- Added defensive try/except around detect_api_version call in startup.py (Rule 2: missing error handling) so version detection failure cannot break startup
- Fetched count uses raw item counts from state (set before filtering) so users can detect pageSize truncation on large libraries

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added defensive error handling around detect_api_version in startup.py**
- **Found during:** Task 1 (Sonarr API version detection)
- **Issue:** If detect_api_version raised an unexpected exception (despite its internal try/except), it would propagate up through validate_connections and potentially break startup
- **Fix:** Wrapped the detect_api_version call in validate_connections with try/except that logs a warning and falls back to v3
- **Files modified:** fetcharr/startup.py
- **Verification:** test_sonarr_version_detection_failure passes
- **Committed in:** d11c167 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Defensive error handling necessary for resilience. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Search diagnostics complete -- users can now see Sonarr API version at startup and per-cycle summaries for troubleshooting
- Ready for Phase 14 and beyond

## Self-Check: PASSED

All files exist, all 3 task commits verified (d11c167, e5956ef, 569353d), 133 tests passing, ruff clean.

---
*Phase: 13-ci-search-diagnostics*
*Completed: 2026-02-24*
