---
phase: 58-auth-test-suite
reviewed: 2026-04-15T12:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - tests/test_auth_config.py
  - tests/test_auth_helpers.py
  - tests/test_auth_integration.py
  - tests/test_auth_middleware.py
  - tests/test_auth_routes.py
  - triggarr/web/middleware.py
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 58: Code Review Report

**Reviewed:** 2026-04-15T12:00:00Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the auth test suite (5 test files) and the production `AuthMiddleware` module. The code is well-structured with good security practices: timing-safe comparisons (`secrets.compare_digest`) for API keys and usernames, `SecretStr` discipline for sensitive values, open-redirect protection in `_safe_next_url`, proper CSRF-style origin checking, and session cookie signing with expiry. The test suite provides thorough coverage across auth modes, session lifecycle, setup flow, and edge cases.

One warning-level issue was found in the middleware (query string loss on auth redirect). Three informational items relate to test code hygiene.

## Warnings

### WR-01: Auth redirect drops original query string parameters

**File:** `triggarr/web/middleware.py:132`
**Issue:** The fallback redirect to `/login?next=...` uses `request.url.path` which excludes query parameters. A user visiting `/settings?tab=security` while unauthenticated gets redirected to `/login?next=/settings`, losing the `?tab=security` portion. After login they land on `/settings` without their original query context.
**Fix:**
```python
# Replace line 132:
next_url = quote(str(request.url.path), safe="/")

# With:
raw_path = str(request.url.path)
if request.url.query:
    raw_path = f"{raw_path}?{request.url.query}"
next_url = quote(raw_path, safe="/?=&")
```
Note: `_safe_next_url` already accepts query strings (tested via `test_safe_next_url_valid_relative_with_query`), so the login route will handle this correctly.

## Info

### IN-01: Hardcoded `/tmp/` fallback path in test helpers

**File:** `tests/test_auth_routes.py:91`
**File:** `tests/test_auth_integration.py:91`
**Issue:** `_make_route_app` falls back to `Path("/tmp/test-triggarr.toml")` when no `config_path` is provided. While no current test writes to this path without providing `tmp_path`, a future test could accidentally write to the shared `/tmp/` location, causing flaky cross-test interference.
**Fix:** Use a sentinel or raise an error if config_path is needed but not provided. Alternatively, always require `config_path` as a parameter (remove the default).

### IN-02: Duplicated `_configured_auth` and `_make_route_app` helpers across test files

**File:** `tests/test_auth_routes.py:55-98`
**File:** `tests/test_auth_integration.py:55-98`
**File:** `tests/test_auth_middleware.py:78-92`
**Issue:** Three test files define nearly identical `_configured_auth()` helper functions and two files have identical `_make_route_app()` helpers. The integration test file comments note this duplication explicitly (line 47: "duplicated from test_auth_routes.py"). This increases maintenance burden when the test infrastructure changes.
**Fix:** Extract shared helpers into a `tests/conftest.py` fixture or a `tests/auth_helpers.py` module and import from there.

### IN-03: Module-level `hash_password` calls slow test collection

**File:** `tests/test_auth_routes.py:50`
**File:** `tests/test_auth_integration.py:50`
**File:** `tests/test_auth_middleware.py:74`
**Issue:** `_TEST_PASSWORD_HASH = hash_password(_TEST_PASSWORD)` runs bcrypt (12 rounds) at module import time. With three test files each doing this, approximately 0.5-1.0 seconds of bcrypt computation happens before any test executes. This is not a correctness issue but adds latency to test startup.
**Fix:** Use a pre-computed bcrypt hash as a string constant, or use `@pytest.fixture(scope="session")` to compute it once across all test files.

---

_Reviewed: 2026-04-15T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
