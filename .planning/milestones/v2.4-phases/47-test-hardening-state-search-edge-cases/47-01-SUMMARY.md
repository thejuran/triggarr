# Phase 47 Plan 01 Summary: Corrupt State/Config Tests

## What was done

Added 14 tests across 3 test files verifying Triggarr handles corrupt persistent
state without crashing or losing data.

### tests/test_config.py (7 new tests)

**STATE-01 (Broken TOML config):**
- `test_toml_syntax_error_raises_decode_error` -- missing bracket raises TOMLDecodeError
- `test_toml_negative_search_interval_raises_validation_error` -- both counts 0 when enabled raises ValidationError
- `test_toml_wrong_type_raises_validation_error` -- array instead of string raises ValidationError

**STATE-04 (Config migration edge cases):**
- `test_migrate_v22_partial_radarr_only` -- radarr only, no sonarr key
- `test_migrate_v22_unknown_extra_fields_preserved` -- unknown fields preserved by wrapping
- `test_is_v22_format_missing_general` -- no general section still detects flat format
- `test_migrate_v22_mixed_nested_and_flat_only_detects_flat` -- mixed nested/flat detected

### tests/test_state.py (4 new tests)

**STATE-03 (Invalid JSON state):**
- `test_state_truncated_json_recovers` -- truncated JSON recovers to defaults
- `test_state_empty_file_recovers` -- empty file recovers to defaults
- `test_state_wrong_structure_list_crashes` -- list JSON crashes (documents limitation)
- `test_state_wrong_nested_type_recovers` -- string radarr value recovers gracefully

### tests/test_db.py (3 new tests)

**STATE-02 (Corrupt SQLite):**
- `test_init_db_corrupt_file_raises_database_error` -- random bytes raises DatabaseError
- `test_init_db_locked_database` -- locked DB raises OperationalError with zero busy_timeout
- `test_get_schema_version_on_empty_db` -- fresh DB returns version 0

## Deviations from plan

- Plan specified `test_toml_missing_required_api_key_raises_validation_error` but api_key
  has a default value in InstanceConfig, so substituted with
  `test_toml_negative_search_interval_raises_validation_error` (both counts 0 when enabled)
- Plan specified `enabled = "yes"` for wrong type test but pydantic coerces strings to bool,
  so used `url = [1, 2, 3]` (array for string field) instead

## Production code changes

None -- test-only phase.

## Verification

- 607 tests pass (full suite)
- Ruff lint clean
