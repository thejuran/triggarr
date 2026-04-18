---
status: complete
phase: quick
plan: 1
subsystem: config
tags: [pydantic, model-validator, validation, htmx]

# Dependency graph
requires: []
provides:
  - "ArrConfig model_validator enforcing at least one search count >= 1 when enabled"
  - "0-minimum support for search_missing_count and search_cutoff_count"
affects: [search-engine, web-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cross-field Pydantic model_validator for dependent field validation"

key-files:
  created: []
  modified:
    - triggarr/models/config.py
    - triggarr/web/routes.py
    - triggarr/templates/settings.html
    - tests/test_validation.py
    - tests/test_web.py

key-decisions:
  - "Used model_validator(mode='after') for cross-field validation rather than route-level checks"

patterns-established:
  - "Cross-field validation via Pydantic model_validator catches invalid combinations before TOML write"

requirements-completed: [QUICK-1]

# Metrics
duration: 2min
completed: 2026-02-25
---

# Quick Task 1: Allow 0 for Missing/Cutoff Counts Summary

**Pydantic model_validator enforcing at least one search count >= 1 when enabled, with 0-minimum on both count fields**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T18:28:16Z
- **Completed:** 2026-02-25T18:30:18Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- ArrConfig now accepts 0 for search_missing_count or search_cutoff_count individually
- Cross-field model_validator rejects both-zero counts when app is enabled, allows when disabled
- HTML form inputs updated to min="0" for missing and cutoff count fields
- Route safe_int calls lowered from minimum=1 to minimum=0 for count fields
- 4 new/updated tests covering 0-minimum clamping and both-zero rejection via settings POST

## Task Commits

Each task was committed atomically:

1. **Task 1: Lower minimum to 0 and add cross-field validation** - `6b281af` (feat)
2. **Task 2: Update tests for new 0-minimum behavior** - `c1ed0f5` (test)

## Files Created/Modified
- `triggarr/models/config.py` - Added model_validator import and cross-field at_least_one_search_count validator
- `triggarr/web/routes.py` - Changed safe_int minimum from 1 to 0 for search_missing_count and search_cutoff_count
- `triggarr/templates/settings.html` - Changed min="1" to min="0" on missing and cutoff count inputs
- `tests/test_validation.py` - Updated test_below_minimum_clamped for 0-minimum, added test_negative_clamped_to_zero
- `tests/test_web.py` - Added test_save_settings_rejects_both_zero_counts and test_save_settings_accepts_zero_missing_with_positive_cutoff

## Decisions Made
- Used `model_validator(mode="after")` on ArrConfig rather than adding route-level validation, keeping the existing Pydantic ValidationError catch block as the single enforcement point

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Search engine can now skip missing or cutoff searches when count is 0 (existing loop behavior handles count=0 as no-op)
- No blockers

## Self-Check: PASSED

All 5 modified files verified on disk. Both task commits (6b281af, c1ed0f5) verified in git log. 177 tests pass, 0 ruff violations.

---
*Quick Task: 1-allow-0-for-missing-cutoff-counts-but-re*
*Completed: 2026-02-25*
