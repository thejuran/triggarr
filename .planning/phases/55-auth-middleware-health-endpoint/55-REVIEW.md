---
phase: 55-auth-middleware-health-endpoint
reviewed: 2026-04-14T12:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - tests/test_auth_middleware.py
  - triggarr/__main__.py
  - triggarr/web/middleware.py
  - triggarr/web/routes.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 55: Code Review Report

**Reviewed:** 2026-04-14T12:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the auth middleware, health endpoint, security middleware, CSRF origin check, route handlers, main entry point, and test suite. The implementation is solid -- the deny-all middleware correctly follows the D-10 check order, uses timing-safe comparison for API keys, bcrypt for password verification, and itsdangerous TimestampSigner for session cookies. Test coverage is thorough across all auth modes and edge cases.

Two warnings found: a missing `secure` flag on session cookies (relevant for HTTPS deployments) and a type annotation weakness in the Basic auth handler. Two informational items noted.

## Warnings

### WR-01: Session cookie missing `secure` flag

**File:** `triggarr/web/middleware.py:147-153`
**Issue:** The `set_cookie` call in `_handle_basic_auth` sets `httponly=True` and `samesite="lax"` but omits `secure=True`. When Triggarr is deployed behind an HTTPS-terminating reverse proxy (the expected Docker deployment model), the session cookie will still be sent over plain HTTP connections if any exist. This makes session hijacking possible on non-HTTPS paths.
**Fix:** Add `secure=True` to the `set_cookie` call. If HTTP-only development support is needed, consider making this conditional on a config flag or environment variable:
```python
response.set_cookie(
    "triggarr_session",
    session_value,
    max_age=COOKIE_MAX_AGE,
    httponly=True,
    samesite="lax",
    secure=True,
)
```

### WR-02: `_handle_basic_auth` uses `object` type hint instead of `AuthConfig`

**File:** `triggarr/web/middleware.py:131-133`
**Issue:** The `auth` parameter is typed as `object`, losing all type-checking benefits. Callers pass an `AuthConfig` instance, and the method body accesses `.username`, `.password_hash`, and `.session_secret` attributes without any type safety. A typo in an attribute name would not be caught by type checkers.
**Fix:** Import and use the proper type:
```python
from triggarr.models.config import AuthConfig

@staticmethod
async def _handle_basic_auth(
    request: Request, auth: AuthConfig, call_next: RequestResponseEndpoint
) -> Response:
```

## Info

### IN-01: Mutating live settings before confirming TOML write success in `remove_instance`

**File:** `triggarr/web/routes.py:701`
**Issue:** `del instances[instance_name]` mutates the live `settings` object before the `_atomic_toml_write` call on line 706. If the write fails (disk full, permission error), the in-memory state no longer matches the on-disk config. The `save_settings` endpoint avoids this by constructing a new `SettingsModel` first and only assigning it after the write succeeds.
**Fix:** Follow the same pattern as `save_settings`: build a new config dict without the instance, validate via `SettingsModel(**config_dict)`, write to TOML, then assign the new settings object to `app.state.settings`.

### IN-02: Test module executes bcrypt and CSPRNG at import time

**File:** `tests/test_auth_middleware.py:58-61`
**Issue:** `generate_session_secret()`, `hash_password(_PASSWORD)`, and the `_API_KEY` constant are computed at module level. The bcrypt hash in particular adds ~100ms to import time. This is not a bug but could slow down test collection in large suites.
**Fix:** Consider using `@pytest.fixture(scope="module")` to defer computation until tests actually run, or accept the current approach as acceptable for a focused test module.

---

_Reviewed: 2026-04-14T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
