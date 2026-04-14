---
phase: 54-auth-config-helpers
plan: 01
subsystem: auth-config
tags: [auth, config, pydantic, security]
dependency_graph:
  requires: []
  provides: [AuthConfig-model, auth-dependencies, auth-secret-redaction]
  affects: [triggarr/models/config.py, triggarr/startup.py, pyproject.toml]
tech_stack:
  added: [bcrypt, itsdangerous]
  patterns: [SecretStr-for-auth-secrets, Literal-validation-for-auth-method]
key_files:
  created:
    - tests/test_auth_config.py
  modified:
    - pyproject.toml
    - triggarr/models/config.py
    - triggarr/startup.py
decisions:
  - "AuthConfig placed after GeneralConfig, before Settings in models/config.py"
  - "DEFAULT_CONFIG template not modified (D-01 honored) -- Pydantic defaults handle missing [auth] section"
  - "Auth secrets collected via explicit field iteration, not reflection"
metrics:
  duration: 127s
  completed: "2026-04-14T23:50:20Z"
  tasks_completed: 2
  tasks_total: 2
  test_count: 11
  total_tests: 679
---

# Phase 54 Plan 01: Auth Config & Helpers -- Config Model Summary

AuthConfig Pydantic model with Literal-validated auth method (Forms/Basic/External/Disabled), SecretStr fields for password_hash/api_key/session_secret, needs_setup/is_disabled properties, integrated into Settings with log redaction via collect_secrets extension.

## What Was Done

### Task 1: Add dependencies and create AuthConfig model
- Added `bcrypt` and `itsdangerous` to pyproject.toml dependencies
- Created `AuthConfig(BaseModel)` with 5 fields: method (Literal), username, password_hash (SecretStr), api_key (SecretStr), session_secret (SecretStr)
- Added `needs_setup` property (True when username is empty)
- Added `is_disabled` property (True when method is "Disabled")
- Added `auth: AuthConfig = AuthConfig()` field to Settings class
- Updated Settings docstring to mention [auth] section
- Confirmed DEFAULT_CONFIG template NOT modified (D-01 honored)
- **Commit:** 74c03e3

### Task 2: Extend collect_secrets and create config tests
- Extended `collect_secrets()` to gather auth password_hash, api_key, session_secret for log redaction (D-07)
- Created 11 unit tests covering: defaults, needs_setup states, is_disabled, all 4 method validation, invalid method rejection, SecretStr masking (str/repr/json), Settings integration, collect_secrets with auth secrets, collect_secrets with empty auth secrets
- Fixed import sorting for ruff compliance
- **Commit:** 3cec3d7

## Verification Results

- `uv run pytest tests/test_auth_config.py -x -q` -- 11 passed
- `uv run pytest tests/ -x -q` -- 679 passed (no regressions)
- `uv run ruff check triggarr/models/config.py triggarr/startup.py tests/test_auth_config.py` -- all checks passed
- `uv run python -c "import bcrypt; import itsdangerous"` -- exits 0

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None -- all fields have proper defaults, all properties are fully implemented.

## Threat Model Compliance

| Threat ID | Status | Implementation |
|-----------|--------|----------------|
| T-54-01 | Mitigated | password_hash, api_key, session_secret all use SecretStr; collect_secrets() gathers them for redaction |
| T-54-02 | Mitigated | Pydantic Literal["Forms", "Basic", "External", "Disabled"] rejects invalid values; test confirms |
| T-54-03 | Mitigated | test_auth_config_secretstr_masking verifies no leakage in str(), repr(), model_dump_json() |

## Self-Check: PASSED

- [x] pyproject.toml contains bcrypt and itsdangerous
- [x] triggarr/models/config.py contains class AuthConfig
- [x] triggarr/startup.py contains settings.auth.password_hash
- [x] tests/test_auth_config.py exists with 11 tests
- [x] Commit 74c03e3 exists
- [x] Commit 3cec3d7 exists
