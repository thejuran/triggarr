---
phase: 33-config-model-migration
plan: 02
subsystem: config
tags: [toml, migration, multi-instance, config-loading, atomic-write]

# Dependency graph
requires:
  - phase: 33-01
    provides: InstanceConfig model with dict[str, InstanceConfig] Settings fields
provides:
  - v2.2 config detection and auto-migration to v2.3 multi-instance format
  - Atomic TOML write helper (_atomic_toml_write)
  - Updated default config template with web UI comment and empty instance sections
  - ensure_config integration with migration
  - conftest make_settings() using dict-based model
affects: [34-per-instance-scheduling, 39-settings-ui]

# Tech tracking
tech-stack:
  added: [tomli_w]
  patterns: [atomic TOML write via tempfile+fsync+os.replace, v2.2 format detection by flat key presence]

key-files:
  created: []
  modified:
    - triggarr/config.py
    - tests/test_config.py
    - tests/conftest.py

key-decisions:
  - "Extracted _atomic_toml_write helper for reuse (migration and future routes.py update)"
  - "v2.2 detection checks for flat url/api_key/enabled keys under radarr/sonarr sections"
  - "Migration creates .migrated marker file for web UI banner (Phase 39)"

patterns-established:
  - "detect_and_migrate_v22() called before load_settings() in ensure_config()"
  - "_atomic_toml_write(path, data) for safe TOML file writes"

requirements-completed: [INST-04]

# Metrics
duration: 11min
completed: 2026-03-10
---

# Phase 33 Plan 02: Config Migration & Default Config Summary

**v2.2-to-v2.3 auto-migration with backup, .migrated marker, atomic TOML writes, and updated default config template for web UI-managed instances**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-11T01:38:47Z
- **Completed:** 2026-03-11T01:49:44Z
- **Tasks:** 2 (1 TDD + 1 auto)
- **Files modified:** 3

## Accomplishments
- _is_v22_format detects flat radarr/sonarr sections (v2.2 format) vs nested instance names (v2.3)
- detect_and_migrate_v22 backs up original, writes migrated config atomically, creates .migrated marker
- Already-migrated v2.3 configs are not re-migrated (returns False, no backup created)
- Disabled apps preserved as disabled "Default" instances with URL and API key intact
- API keys written as plaintext in TOML (not SecretStr-masked)
- Default config template updated with web UI comment and empty radarr/sonarr sections
- ensure_config runs migration before loading for existing configs
- conftest make_settings() updated to dict-based radarr/sonarr with "Default" instance
- 42 test_config.py tests pass, lint clean

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for v2.2 migration** - `d7ce933` (test)
2. **Task 1 GREEN: v2.2 detection, migration, default config** - `c576d12` (feat)
3. **Task 2: Update conftest and fix test assertions** - `f01caec` (fix)

## Files Created/Modified
- `triggarr/config.py` - Migration logic (_is_v22_format, _migrate_v22_to_v23, detect_and_migrate_v22), _atomic_toml_write helper, updated DEFAULT_CONFIG template, ensure_config with migration integration
- `tests/test_config.py` - 18 new migration tests (detection, backup, marker, round-trip, disabled preservation, API key plaintext)
- `tests/conftest.py` - make_settings() updated to use dict-based radarr/sonarr with InstanceConfig

## Decisions Made
- Extracted _atomic_toml_write as a shared helper (tempfile + fsync + os.replace) for reuse in migration and future routes.py update
- v2.2 detection uses set intersection of flat keys (url, api_key, enabled) against section data -- simple and reliable
- .migrated marker file is empty (touch) -- web UI only needs to check existence

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Config model and migration complete for Phase 33
- test_startup.py, test_web.py, test_search.py, test_scheduler.py have expected failures (38 tests) due to flat access patterns (settings.radarr.url) -- these consumers will be updated in Phase 34+
- _atomic_toml_write helper ready for routes.py update in Phase 39

---
*Phase: 33-config-model-migration*
*Completed: 2026-03-10*

## Self-Check: PASSED
