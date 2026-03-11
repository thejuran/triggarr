---
phase: 36-search-engine-tag-filtering
plan: 02
subsystem: search
tags: [tag-filtering, radarr, sonarr, integration, tdd]

requires:
  - phase: 36-search-engine-tag-filtering
    provides: "filter_by_tag, _radarr_tags, _sonarr_tags, resolve_tag_id, InstanceConfig tag fields"
  - phase: 35-client-registry-tag-resolution
    provides: "Tag model and get_tags() client method"
provides:
  - "Tag filtering wired into run_radarr_cycle and run_sonarr_cycle"
  - "End-to-end tag-based search filtering for both Radarr and Sonarr"
affects: [39-web-ui, search-cycle-behavior]

tech-stack:
  added: []
  patterns: ["Tag resolution once per cycle, filter applied per queue before batching"]

key-files:
  created: []
  modified:
    - triggarr/search/engine.py
    - tests/test_search.py

key-decisions:
  - "Tag resolution happens once per cycle (not per queue) to minimize API calls"
  - "Sonarr tag filter applied BEFORE deduplicate_to_seasons since deduped dicts lose series.tags"
  - "Filter order for Radarr missing: filter_monitored -> filter_by_tag -> filter_unreleased_movies"

patterns-established:
  - "Tag resolution block: resolve once, apply per-queue with None check for fail-open"
  - "get_tags() only called when at least one tag is configured (empty string = skip)"

requirements-completed: [TAG-01, TAG-02, TAG-03]

duration: 9min
completed: 2026-03-11
---

# Phase 36 Plan 02: Wire Tag Filtering into Cycle Functions Summary

**Tag resolution and filter_by_tag wired into both run_radarr_cycle and run_sonarr_cycle with fail-open semantics and conditional get_tags() call**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-11T11:52:36Z
- **Completed:** 2026-03-11T12:01:54Z
- **Tasks:** 2 (TDD: RED + GREEN each)
- **Files modified:** 2

## Accomplishments
- Wired tag resolution and filtering into run_radarr_cycle (missing + cutoff queues)
- Wired tag resolution and filtering into run_sonarr_cycle with correct ordering (before dedup)
- get_tags() API call skipped entirely when both missing_tag and cutoff_tag are empty
- Fail-open: tag name not found in tag list proceeds without filtering (searches all)
- 371 tests pass, lint clean

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for Radarr tag filtering** - `55414f0` (test)
2. **Task 1 (GREEN): Wire tag filtering into run_radarr_cycle** - `02f723e` (feat)
3. **Task 2 (RED): Failing tests for Sonarr tag filtering** - `12d30d9` (test)
4. **Task 2 (GREEN): Wire tag filtering into run_sonarr_cycle** - `d0e3c2d` (feat)

## Files Created/Modified
- `triggarr/search/engine.py` - Added tag resolution block and filter_by_tag calls in both cycle functions
- `tests/test_search.py` - 9 new integration tests for tag filtering in cycle functions

## Decisions Made
- Tag resolution happens once per cycle (single get_tags() call) rather than per-queue
- Sonarr tag filter placed before deduplicate_to_seasons because deduped season dicts lose series.tags
- Radarr filter order: filter_monitored -> filter_by_tag -> filter_unreleased_movies (tag narrows before release check)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Tag filtering is fully functional end-to-end for both Radarr and Sonarr
- Phase 36 complete: config fields, pure functions, and cycle integration all done
- Ready for Phase 37+ (multi-instance UI, settings forms)

---
*Phase: 36-search-engine-tag-filtering*
*Completed: 2026-03-11*

## Self-Check: PASSED
