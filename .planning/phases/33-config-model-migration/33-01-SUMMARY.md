---
phase: 33-config-model-migration
plan: 01
subsystem: config
tags: [pydantic, toml, multi-instance, config-model]

# Dependency graph
requires: []
provides:
  - InstanceConfig model with per-instance fields (url, api_key, enabled, search_interval, search_missing_count, search_cutoff_count)
  - Settings with dict[str, InstanceConfig] for radarr and sonarr
  - Max 5 instances per app type validation
  - get_enabled_instances() helper method
  - ArrConfig backward-compat alias
affects: [33-02-config-loading-migration, 34-per-instance-scheduling, 39-settings-ui]

# Tech tracking
tech-stack:
  added: []
  patterns: [dict-based multi-instance config model, model_validator for instance count limits]

key-files:
  created: []
  modified:
    - triggarr/models/config.py
    - tests/test_config.py

key-decisions:
  - "Renamed ArrConfig to InstanceConfig with ArrConfig alias for backward compat"
  - "Updated existing TOML test fixtures to v2.3 nested format rather than keeping v2.2 format"

patterns-established:
  - "Multi-instance access: settings.radarr['Name'].url instead of settings.radarr.url"
  - "get_enabled_instances(app_type) returns filtered dict of enabled instances"

requirements-completed: [INST-01, INST-02]

# Metrics
duration: 3min
completed: 2026-03-10
---

# Phase 33 Plan 01: Config Model Migration Summary

**InstanceConfig model with dict[str, InstanceConfig] fields on Settings, max 5 per app type validation, and backward-compat ArrConfig alias**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-11T01:33:28Z
- **Completed:** 2026-03-11T01:36:20Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- InstanceConfig class with all fields from old ArrConfig (url, api_key as SecretStr, enabled, search_interval, search_missing_count, search_cutoff_count)
- Settings.radarr and Settings.sonarr changed to dict[str, InstanceConfig] with empty dict defaults
- model_validator enforces max 5 instances per app type
- has_enabled_app iterates dict values correctly
- get_enabled_instances() helper for downstream consumers
- ArrConfig alias preserved for transition period
- 13 new tests + 11 updated existing tests, all 24 pass

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for multi-instance model** - `79b9e0d` (test)
2. **Task 1 GREEN: InstanceConfig model and dict-based Settings** - `f1a99c8` (feat)

## Files Created/Modified
- `triggarr/models/config.py` - InstanceConfig model, ArrConfig alias, dict-based Settings with validation and helpers
- `tests/test_config.py` - 13 new multi-instance tests + 11 updated existing tests for v2.3 format

## Decisions Made
- Renamed ArrConfig to InstanceConfig with `ArrConfig = InstanceConfig` alias for backward compatibility during transition
- Updated existing TOML test fixtures from v2.2 flat format to v2.3 nested format (e.g., `[radarr."Default"]`) since the model no longer accepts flat format -- migration of actual config files is Plan 02's responsibility

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated existing test TOML fixtures to v2.3 format**
- **Found during:** Task 1 GREEN phase
- **Issue:** Existing tests used v2.2-format TOML (`[radarr]` with flat fields) which Pydantic now rejects since `radarr` is `dict[str, InstanceConfig]`
- **Fix:** Updated VALID_TOML, RADARR_ONLY_TOML, NO_APPS_TOML constants and inline TOML in skip_unreleased tests to use v2.3 nested format
- **Files modified:** tests/test_config.py
- **Verification:** All 24 tests pass
- **Committed in:** f1a99c8

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to make existing tests work with new model shape. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- InstanceConfig model ready for Plan 02 (config loading, migration, default config update)
- ArrConfig alias available for gradual consumer migration
- get_enabled_instances() helper ready for Phase 34 per-instance scheduling

---
*Phase: 33-config-model-migration*
*Completed: 2026-03-10*

## Self-Check: PASSED
