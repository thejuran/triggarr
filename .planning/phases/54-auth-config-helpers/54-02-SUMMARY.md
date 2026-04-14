---
phase: 54-auth-config-helpers
plan: 02
subsystem: auth-helpers
tags: [auth, bcrypt, itsdangerous, cookie-signing, tdd]
dependency_graph:
  requires: [AuthConfig-model, auth-dependencies]
  provides: [auth-helper-functions, password-hashing, cookie-signing, token-generation]
  affects: [triggarr/auth.py]
tech_stack:
  added: []
  patterns: [bcrypt-12-rounds, itsdangerous-TimestampSigner, CSPRNG-token-generation]
key_files:
  created:
    - triggarr/auth.py
    - tests/test_auth_helpers.py
  modified: []
decisions:
  - "Used TimestampSigner.get_timestamp mock for expiry test (itsdangerous 2.x compatible)"
  - "Pure module with no class wrappers -- flat functions per D-04 decision"
metrics:
  duration: 107s
  completed: "2026-04-14T23:53:51Z"
  tasks_completed: 1
  tasks_total: 1
  test_count: 16
  total_tests: 695
---

# Phase 54 Plan 02: Auth Helper Functions Summary

TDD-driven auth helpers: bcrypt password hashing (12 rounds), CSPRNG token generation (API key + session secret), itsdangerous TimestampSigner cookie signing with 30-day expiry validation.

## TDD Gate Compliance

### RED Phase (test gate)
- **Commit:** 09796af
- **Tests written:** 16 tests in `tests/test_auth_helpers.py`
- **Failure reason:** `ModuleNotFoundError: No module named 'triggarr.auth'` -- module did not exist yet
- **Coverage:** password hashing (4 tests), API key generation (3 tests), session secret generation (3 tests), cookie signing/validation (5 tests), constants (1 test)

### GREEN Phase (implementation gate)
- **Commit:** 149bb5c
- **Implementation:** `triggarr/auth.py` with 6 functions + 1 constant
- **Result:** All 16 tests pass, 695 total tests (no regressions), lint clean
- **Test fix:** Updated expiry test to mock `TimestampSigner.get_timestamp` instead of `itsdangerous.signer.time` (itsdangerous 2.x uses `get_timestamp()` method, not a module-level `time` import)

### REFACTOR Phase
- Not needed -- implementation matched plan specification exactly, code is minimal and clean

## What Was Done

### Auth Helper Functions (triggarr/auth.py)
- `hash_password(plaintext)` -- bcrypt with 12 rounds, returns `$2b$12$...` string
- `verify_password(plaintext, hashed)` -- constant-time bcrypt comparison (T-54-04)
- `generate_api_key()` -- 32-char hex via `secrets.token_hex(16)` CSPRNG (T-54-05)
- `generate_session_secret()` -- 64-char hex via `secrets.token_hex(32)` CSPRNG
- `sign_session(username, secret)` -- itsdangerous TimestampSigner cookie creation (T-54-06)
- `validate_session(cookie_value, secret)` -- validates signature + 30-day expiry, returns None on failure (T-54-07)
- `COOKIE_MAX_AGE = 2592000` -- 30 days in seconds

## Verification Results

- `uv run pytest tests/test_auth_helpers.py -x -q` -- 16 passed
- `uv run pytest tests/ -x -q` -- 695 passed (no regressions)
- `uv run ruff check triggarr/auth.py tests/test_auth_helpers.py` -- all checks passed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed expiry test mock target for itsdangerous 2.x**
- **Found during:** GREEN phase
- **Issue:** Test mocked `itsdangerous.signer.time` which does not exist in itsdangerous 2.2.0 (uses `get_timestamp()` method instead)
- **Fix:** Changed mock to patch `TimestampSigner.get_timestamp` with a function that adds 31 days
- **Files modified:** tests/test_auth_helpers.py

## Known Stubs

None -- all functions are fully implemented with real crypto operations.

## Threat Model Compliance

| Threat ID | Status | Implementation |
|-----------|--------|----------------|
| T-54-04 | Mitigated | verify_password uses bcrypt.checkpw (constant-time); no `==` comparison |
| T-54-05 | Mitigated | generate_api_key uses secrets.token_hex (CSPRNG), not random module |
| T-54-06 | Mitigated | sign_session/validate_session use HMAC via itsdangerous; tampered cookies return None |
| T-54-07 | Mitigated | validate_session enforces max_age=2592000; expired cookies return None via SignatureExpired |
| T-54-08 | Accepted | bcrypt 72-byte limit documented; single-user homelab app |

## Self-Check: PASSED

- [x] triggarr/auth.py exists
- [x] tests/test_auth_helpers.py exists
- [x] Commit 09796af exists (RED)
- [x] Commit 149bb5c exists (GREEN)
- [x] No unexpected file deletions
