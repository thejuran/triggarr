---
phase: 55-auth-middleware-health-endpoint
plan: 01
subsystem: web/middleware
tags: [auth, middleware, tdd, security]
dependency_graph:
  requires: [triggarr/auth.py, triggarr/models/config.py]
  provides: [triggarr/web/middleware.py:AuthMiddleware]
  affects: [triggarr/__main__.py]
tech_stack:
  added: []
  patterns: [BaseHTTPMiddleware deny-all dispatch, timing-safe API key comparison, inline Basic auth with cookie setting]
key_files:
  created:
    - tests/test_auth_middleware.py
  modified:
    - triggarr/web/middleware.py
decisions:
  - "AuthMiddleware uses _is_browser() static method for Accept header detection and _handle_basic_auth() static method for Basic auth flow separation"
  - "EXEMPT_PREFIXES defined as module-level tuple, not class attribute, for clarity and reuse"
  - "auth parameter typed as object in _handle_basic_auth to avoid circular import concerns (duck typing on AuthConfig)"
metrics:
  duration: 161s
  completed: "2026-04-15T00:48:00Z"
  test_count: 20
  files_changed: 2
---

# Phase 55 Plan 01: AuthMiddleware Deny-All Dispatch Summary

Deny-all AuthMiddleware with D-10 check order: exempt paths, needs-setup redirect, disabled/external passthrough, session cookie, timing-safe API key, inline Basic auth with cookie setting, browser vs API fallback.

## What Was Built

AuthMiddleware class added to `triggarr/web/middleware.py` implementing the complete D-10 authentication check order as a single enforcement point for all routes. The middleware gates every non-exempt request through a priority chain: needs-setup redirect, disabled/external passthrough, session cookie validation, API key validation (timing-safe via `secrets.compare_digest()`), Basic auth inline validation with session cookie on success, and browser vs API fallback responses (302 redirect vs 401 JSON).

20 test functions in `tests/test_auth_middleware.py` cover all check paths including exempt paths (health, static, login, setup), needs-setup (browser 302, API 401), disabled/external passthrough, session cookie validation, API key (valid + invalid), Basic auth (valid, invalid, malformed base64, missing colon), browser vs API fallback, and session cookie priority in Basic mode.

## TDD Gate Compliance

- RED gate: `test(55-01)` commit `8882f65` -- 20 failing tests (ImportError: AuthMiddleware not yet implemented)
- GREEN gate: `feat(55-01)` commit `f5e7bcf` -- all 20 tests passing
- REFACTOR gate: skipped (no cleanup needed; code is clean and follows existing patterns)

## Task Summary

| Task | Type | Description | Commit | Files |
|------|------|-------------|--------|-------|
| RED | test | Write 20 failing tests for AuthMiddleware D-10 check order | 8882f65 | tests/test_auth_middleware.py |
| GREEN | feat | Implement AuthMiddleware with full D-10 dispatch | f5e7bcf | triggarr/web/middleware.py |

## Threat Mitigations Applied

| Threat ID | Mitigation | Verified |
|-----------|-----------|----------|
| T-55-01 | `secrets.compare_digest()` for API key comparison | Yes -- in middleware line 112 |
| T-55-02 | Cookie set with `httponly=True, samesite="lax"` | Yes -- in _handle_basic_auth |
| T-55-04 | base64 decode wrapped in `try/except (ValueError, UnicodeDecodeError)` | Yes -- test_basic_auth_malformed_header_returns_401 confirms 401 not 500 |

## Deviations from Plan

None -- plan executed exactly as written.

## Verification Results

- `uv run pytest tests/test_auth_middleware.py -x -q` -- 20 passed
- `uv run pytest tests/ -x -q` -- 716 passed (no regressions)
- `uv run ruff check triggarr/web/middleware.py tests/test_auth_middleware.py` -- all checks passed

## Requirements Coverage

| Req ID | Description | Test Coverage |
|--------|-------------|--------------|
| MID-01 | All routes require auth by default (deny-all) | test_unauth_browser_redirects_to_login, test_unauth_api_returns_401 |
| MID-02 | X-Api-Key authentication | test_valid_api_key_passes_through, test_invalid_api_key_does_not_pass |
| MID-04 | Browser 302 redirect vs API 401 JSON | test_unauth_browser_redirects_to_login, test_unauth_api_returns_401 |
| LOGIN-03 | Basic auth with WWW-Authenticate | test_basic_auth_* (5 tests) |
| LOGIN-04 | External mode passthrough | test_external_mode_passes_through |

## Self-Check: PASSED

All files exist, all commits verified.
