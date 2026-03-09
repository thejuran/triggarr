---
phase: 02-search-engine
plan: 02
subsystem: search
tags: [radarr, sonarr, httpx, loguru, async, search-cycle]

# Dependency graph
requires:
  - phase: 02-search-engine/01
    provides: "filter_monitored, slice_batch, append_search_log, deduplicate_to_seasons, filter_sonarr_episodes utilities"
  - phase: 01-foundation/02
    provides: "RadarrClient and SonarrClient async API clients"
  - phase: 01-foundation/01
    provides: "Settings model with ArrConfig search fields"
provides:
  - "run_radarr_cycle async function for complete Radarr search orchestration"
  - "run_sonarr_cycle async function for complete Sonarr search orchestration"
affects: [02-search-engine/03, 03-scheduler]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "fetch-filter-slice-search-log pipeline for arr search cycles"
    - "skip-and-continue per-item error handling in search batches"
    - "top-level cycle abort on fetch failure with cursor preservation"
    - "independent cursors for missing and cutoff queues"

key-files:
  created: []
  modified:
    - "fetcharr/search/engine.py"

key-decisions:
  - "Top-level abort catches httpx.HTTPError (and subclasses) to cover all network/HTTP failure modes"
  - "Per-item search failures catch broad Exception to ensure skip-and-continue resilience"

patterns-established:
  - "Cycle function pattern: fetch -> filter -> (deduplicate) -> slice -> search -> log -> update cursors -> update last_run"
  - "Independent cursor management: missing_cursor and cutoff_cursor operate independently within each cycle"

requirements-completed: [SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05, SRCH-06, SRCH-07, SRCH-10]

# Metrics
duration: 2min
completed: 2026-02-23
---

# Phase 2 Plan 2: Search Cycle Functions Summary

**Radarr and Sonarr search cycle orchestrators composing fetch-filter-slice-search-log pipelines with skip-and-continue error handling and independent cursor management**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-24T03:30:06Z
- **Completed:** 2026-02-24T03:31:47Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Implemented `run_radarr_cycle` that fetches missing/cutoff movie lists, filters monitored, slices batches, triggers MoviesSearch, and logs results
- Implemented `run_sonarr_cycle` that fetches episodes, filters (monitored + air date), deduplicates to seasons, slices batches, triggers SeasonSearch with "Show Title - Season N" log format
- Both cycles handle individual item failures with skip-and-continue and abort cleanly on fetch failure with cursor preservation

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement run_radarr_cycle function** - `c749822` (feat)
2. **Task 2: Implement run_sonarr_cycle function** - `aaea54f` (feat)

## Files Created/Modified
- `fetcharr/search/engine.py` - Added run_radarr_cycle and run_sonarr_cycle async cycle functions alongside existing utility functions

## Decisions Made
- Top-level abort catches `httpx.HTTPError` and its subclasses (`HTTPStatusError`, `ConnectError`, `TimeoutException`) to handle all network and HTTP failure modes while letting other exceptions propagate
- Per-item search failures catch broad `Exception` to maximize skip-and-continue resilience -- a single movie or season failure should never abort the entire cycle

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both cycle functions ready for integration with scheduler (Phase 3)
- Plan 03 (search engine tests) can now write integration tests against these cycle functions
- All 21 existing tests continue to pass

## Self-Check: PASSED

- FOUND: fetcharr/search/engine.py
- FOUND: c749822 (Task 1 commit)
- FOUND: aaea54f (Task 2 commit)

---
*Phase: 02-search-engine*
*Completed: 2026-02-23*
