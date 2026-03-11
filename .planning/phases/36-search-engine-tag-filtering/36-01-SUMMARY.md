---
phase: 36-search-engine-tag-filtering
plan: 01
subsystem: search
tags: [pydantic, filtering, radarr, sonarr, tags]

requires:
  - phase: 35-client-registry-tag-resolution
    provides: "Tag model and resolve_tag_id function"
provides:
  - "InstanceConfig.missing_tag and cutoff_tag fields"
  - "filter_by_tag() pure function with Callable-based tag accessor"
  - "_radarr_tags and _sonarr_tags accessor functions"
affects: [36-02, search-cycle-integration]

tech-stack:
  added: []
  patterns: ["Callable[[dict], list[int]] tag accessor pattern for app-specific tag location"]

key-files:
  created: []
  modified:
    - triggarr/models/config.py
    - triggarr/search/engine.py
    - triggarr/config.py
    - tests/test_config.py
    - tests/test_search.py

key-decisions:
  - "Tag accessor pattern uses Callable[[dict], list[int]] for Radarr vs Sonarr tag location difference"
  - "Tag fields default to empty string (search all) for backward compatibility"

patterns-established:
  - "Tag accessor pattern: _radarr_tags reads item['tags'], _sonarr_tags reads item['series']['tags']"
  - "Sonarr tag filtering must happen BEFORE deduplicate_to_seasons (episodes have series.tags, deduped dicts do not)"

requirements-completed: [TAG-01, TAG-02, TAG-03]

duration: 1min
completed: 2026-03-11
---

# Phase 36 Plan 01: Tag Config Fields and Filter Function Summary

**InstanceConfig tag fields (missing_tag/cutoff_tag) and filter_by_tag pure function with Radarr/Sonarr accessors**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-11T11:49:02Z
- **Completed:** 2026-03-11T11:50:20Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 5

## Accomplishments
- Added missing_tag and cutoff_tag string fields to InstanceConfig with empty-string defaults
- Implemented filter_by_tag() pure function with Callable-based tag accessor pattern
- Added _radarr_tags and _sonarr_tags accessors handling the Radarr vs Sonarr tag location difference
- Updated DEFAULT_CONFIG template with tag filtering documentation
- 362 tests pass, lint clean

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for tag fields and filter_by_tag** - `dba2df0` (test)
2. **Task 1 (GREEN): Implement tag fields and filter function** - `bcf73fb` (feat)

## Files Created/Modified
- `triggarr/models/config.py` - Added missing_tag and cutoff_tag fields to InstanceConfig
- `triggarr/search/engine.py` - Added filter_by_tag, _radarr_tags, _sonarr_tags functions
- `triggarr/config.py` - Updated DEFAULT_CONFIG template with tag filtering comment
- `tests/test_config.py` - 4 new tests for tag config fields and backward compat
- `tests/test_search.py` - 7 new tests for filter_by_tag and tag accessors

## Decisions Made
- Tag accessor pattern uses Callable[[dict], list[int]] for app-specific tag location, keeping filter_by_tag generic
- Tag fields default to empty string so existing configs parse without error (backward compatible)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Tag config fields and filter function ready for Plan 02 to wire into search cycle functions
- Plan 02 will call resolve_tag_id (Phase 35) + filter_by_tag (this plan) in run_radarr_cycle/run_sonarr_cycle

---
*Phase: 36-search-engine-tag-filtering*
*Completed: 2026-03-11*

## Self-Check: PASSED
