---
phase: 01-foundation
plan: 01
subsystem: infra
tags: [pydantic-settings, toml, loguru, secretstr, atomic-write, json-state]

# Dependency graph
requires: []
provides:
  - Pydantic Settings model with TOML config loading (ArrConfig, GeneralConfig, Settings)
  - SecretStr api_key fields that never appear in str/repr
  - TOML config loader with load_settings, generate_default_config, ensure_config
  - Loguru logging with human-readable format and API key redaction filter
  - Atomic JSON state persistence with write-then-rename pattern
  - Package scaffolding (fetcharr/, models/, clients/)
affects: [01-02, 01-03, 02-search-engine, 03-web-ui]

# Tech tracking
tech-stack:
  added: [pydantic-settings, httpx, loguru, tomli-w, fastapi, uvicorn]
  patterns: [SecretStr for API keys, TomlConfigSettingsSource, loguru redaction filter, atomic write via os.replace]

key-files:
  created:
    - pyproject.toml
    - fetcharr/__init__.py
    - fetcharr/models/config.py
    - fetcharr/config.py
    - fetcharr/logging.py
    - fetcharr/state.py
    - fetcharr/models/__init__.py
    - fetcharr/clients/__init__.py
  modified: []

key-decisions:
  - "Settings loads via init_settings + TomlConfigSettingsSource (init kwargs override TOML for testability)"
  - "Config loader reads TOML via tomllib and passes parsed data as init kwargs for path flexibility"
  - "Default config uses plain text template (not tomli_w serialization) to preserve comments"

patterns-established:
  - "SecretStr for all API keys: call .get_secret_value() only where key is needed (httpx client init)"
  - "Loguru redaction filter: single filter function strips all configured secrets from every log message"
  - "Atomic state write: tempfile + os.fsync + os.replace in same directory"
  - "Config path parameter: all config/state functions accept path for testability"

requirements-completed: [CONN-01, CONN-02, SECR-01]

# Metrics
duration: 4min
completed: 2026-02-23
---

# Phase 1 Plan 1: Project Scaffolding Summary

**Pydantic Settings with TOML config loading, SecretStr API keys, loguru redaction filter, and atomic JSON state persistence**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-24T02:35:26Z
- **Completed:** 2026-02-24T02:39:22Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Pydantic Settings model loading from TOML with [general], [radarr], [sonarr] sections and at-least-one-app validator
- SecretStr api_key fields that provably never appear in str() or repr() output
- Loguru logging with configurable level and redaction filter that strips API key values from all log output
- Atomic JSON state persistence with write-then-rename pattern for crash safety

## Task Commits

Each task was committed atomically:

1. **Task 1: Create project scaffolding and Pydantic config models with TOML loading** - `e56ced3` (feat)
2. **Task 2: Set up loguru logging with API key redaction and atomic JSON state store** - `e66fcc6` (feat)

## Files Created/Modified
- `pyproject.toml` - Project metadata with pydantic-settings, httpx, loguru, fastapi dependencies
- `fetcharr/__init__.py` - Package root with __version__
- `fetcharr/models/__init__.py` - Models subpackage
- `fetcharr/models/config.py` - ArrConfig, GeneralConfig, Settings Pydantic models with SecretStr
- `fetcharr/config.py` - TOML config loading, default config generation, ensure_config
- `fetcharr/logging.py` - Loguru setup with redaction filter for API key protection
- `fetcharr/state.py` - Atomic JSON state persistence with TypedDict structures
- `fetcharr/clients/__init__.py` - Clients subpackage (empty, ready for Plan 02)
- `.gitignore` - Python/venv/IDE exclusions

## Decisions Made
- Settings model includes init_settings source alongside TomlConfigSettingsSource so init kwargs can override TOML values for testability
- Config loader uses stdlib tomllib to read TOML and passes parsed data as init kwargs to Settings, allowing arbitrary paths without class-level config changes
- Default config template uses plain text string (not tomli_w serialization) to preserve inline comments that guide user setup

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Settings TOML source override mechanism**
- **Found during:** Task 1 (Config models and TOML loading)
- **Issue:** Plan specified `_toml_file=config_path` as init kwarg to Settings, but pydantic-settings does not accept `_toml_file` as a runtime parameter. The `settings_customise_sources` initially excluded init_settings, so init kwargs were silently ignored.
- **Fix:** Added `init_settings` as first source in `settings_customise_sources` and changed `load_settings` to read TOML via `tomllib.load()` then pass parsed dict as `**kwargs` to Settings.
- **Files modified:** `fetcharr/models/config.py`, `fetcharr/config.py`
- **Verification:** `load_settings(Path(tmp))` correctly loads from arbitrary TOML paths; validator correctly rejects config with no enabled apps
- **Committed in:** `e56ced3` (Task 1 commit)

**2. [Rule 2 - Missing Critical] Added .gitignore**
- **Found during:** Task 1 (before commit)
- **Issue:** No .gitignore existed; venv, __pycache__, and IDE files would be committed
- **Fix:** Created .gitignore with Python, venv, IDE, and OS exclusions
- **Files modified:** `.gitignore`
- **Verification:** `git status` shows clean after venv creation
- **Committed in:** `e56ced3` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug fix, 1 missing critical)
**Impact on plan:** Both fixes necessary for correct operation and clean repo. No scope creep.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Config models, logging, and state store are ready for Plan 02 (httpx API clients)
- `ArrConfig.api_key.get_secret_value()` provides the raw key for httpx client headers
- `setup_logging()` accepts secrets list for redaction setup during startup
- `load_state()`/`save_state()` ready for cursor persistence in Plan 02 search logic

## Self-Check: PASSED

All 9 created files verified on disk. Both task commits (e56ced3, e66fcc6) verified in git log.

---
*Phase: 01-foundation*
*Completed: 2026-02-23*
