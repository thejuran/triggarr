---
id: S01
parent: M001
milestone: M001
provides:
  - InstanceConfig model with dict[str, InstanceConfig] Settings fields
  - v2.2 config detection and auto-migration with backup and .migrated marker
  - _atomic_toml_write helper for safe TOML writes
  - Updated default config template for web UI-managed instances
key_files:
  - triggarr/models/config.py
  - triggarr/config.py
  - tests/test_config.py
  - tests/conftest.py
key_decisions:
  - "Renamed ArrConfig to InstanceConfig with backward-compat alias"
  - "v2.2 detection uses flat key set intersection"
  - "Extracted _atomic_toml_write helper for reuse"
  - ".migrated marker file for web UI banner (S07)"
patterns_established:
  - "dict[str, InstanceConfig] for named instance collections"
  - "_atomic_toml_write(path, data) for safe TOML writes"
  - "detect_and_migrate_v22() called before load_settings() in ensure_config()"
observability_surfaces:
  - "loguru info/warning logs during migration"
drill_down_paths:
  - .planning/phases/33-config-model-migration/33-01-SUMMARY.md
  - .planning/phases/33-config-model-migration/33-02-SUMMARY.md
duration: 14min
verification_result: passed
completed_at: 2026-03-11
---

# S01: Config Model & Migration

**Multi-instance config model with InstanceConfig, dict-based Settings, v2.2 auto-migration, and atomic TOML write helper**

## What Happened

Renamed ArrConfig to InstanceConfig and restructured Settings to use `dict[str, InstanceConfig]` for radarr/sonarr instead of flat fields. Added missing_tag and cutoff_tag string fields to InstanceConfig. Built v2.2 format detection (_is_v22_format) and auto-migration (detect_and_migrate_v22) that backs up the original config, writes the migrated version atomically, and creates a .migrated marker for the web UI. Updated default config template and conftest fixtures. 42 config tests passing.

## Verification

- 42 test_config.py tests pass covering model validation, migration, backup, marker, round-trip, disabled preservation
- Lint clean (ruff)
- conftest make_settings() updated to dict-based model

## Deviations

None — plans executed as written.

## Known Limitations

- test_startup.py, test_web.py, test_search.py, test_scheduler.py have expected failures (38 tests) due to flat access patterns (settings.radarr.url) — updated in S02+

## Follow-ups

- _atomic_toml_write ready for routes.py update in S07

## Files Created/Modified

- `triggarr/models/config.py` — InstanceConfig model, tag fields, dict-based Settings
- `triggarr/config.py` — Migration logic, _atomic_toml_write, updated DEFAULT_CONFIG, ensure_config integration
- `tests/test_config.py` — 42 tests for model and migration
- `tests/conftest.py` — Updated make_settings() to dict-based format

## Forward Intelligence

### What the next slice should know
- Settings.radarr and Settings.sonarr are now dict[str, InstanceConfig], not flat objects
- All consumers need updating to iterate instances

### What's fragile
- 38 tests in other modules expect flat settings.radarr.url access — must be updated

### Authoritative diagnostics
- test_config.py is the source of truth for config model behavior

### What assumptions changed
- None — pydantic-settings with dict[str, InstanceConfig] worked as expected
