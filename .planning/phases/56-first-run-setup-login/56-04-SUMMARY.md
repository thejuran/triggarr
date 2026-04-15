---
phase: 56-first-run-setup-login
plan: 04
subsystem: auth-routes
tags: [auth, integration-tests, tdd, setup, login, logout, open-redirect]
dependency_graph:
  requires: [_safe_next_url, _settings_to_dict-auth-extension, setup_page, setup_post, login_page, login_post, logout]
  provides: [auth-route-integration-tests]
  affects: [tests/test_auth_routes.py]
tech_stack:
  added: []
  patterns: [TestClient-integration-tests, _make_route_app-factory]
key_files:
  created: []
  modified:
    - tests/test_auth_routes.py
decisions:
  - "Used SettingsModel.model_construct() instead of MagicMock for app.state.settings to support real model_copy() in setup_post handler"
  - "Tests written as GREEN-from-start since route handlers already exist from Plan 03 -- tests serve as regression protection"
metrics:
  duration: 205s
  completed: "2026-04-15T02:49:13Z"
  tasks: 1
  files: 1
---

# Phase 56 Plan 04: TDD Integration Tests for Auth Route Handlers Summary

14 integration tests covering setup/login/logout route handlers with real FastAPI app, AuthMiddleware, and Jinja2 templates via _make_route_app factory.

## Task Summary

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | TDD integration tests for setup, login, and logout routes | cd3a4b9 | tests/test_auth_routes.py |

## What Was Built

### Test App Factory: _make_route_app()

Creates a FastAPI app with real route handlers (`router` from routes.py), AuthMiddleware, static file mount, and `SettingsModel.model_construct()` settings with configurable `AuthConfig` and `config_path`. Supports `tmp_path` for TOML persistence tests and `asyncio.Lock()` as search_lock.

### Setup Route Tests (7 tests)

- `test_setup_page_renders_when_needs_setup` -- GET /setup returns 200 with "Welcome to Triggarr"
- `test_setup_page_returns_404_when_configured` -- GET /setup returns 404 when credentials exist (SETUP-04)
- `test_setup_post_creates_credentials` -- POST /setup creates account, shows API key, persists to TOML with [auth] section
- `test_setup_post_password_mismatch_shows_error` -- POST /setup with mismatched passwords shows "Passwords do not match"
- `test_setup_post_empty_password_shows_error` -- POST /setup with empty password shows "Password is required"
- `test_setup_post_sets_session_cookie` -- POST /setup sets triggarr_session cookie (auto-login)
- `test_setup_post_returns_404_when_configured` -- POST /setup returns 404 when already configured

### Login Route Tests (6 tests)

- `test_login_page_renders` -- GET /login returns 200 with "Sign In"
- `test_login_page_redirects_when_authenticated` -- GET /login with valid session redirects to / (D-06)
- `test_login_post_valid_credentials_redirects` -- POST /login with correct credentials returns 303 with session cookie
- `test_login_post_invalid_credentials_shows_error` -- POST /login with wrong password shows "Invalid username or password" with username pre-filled (D-04)
- `test_login_post_respects_next_param` -- POST /login with next=/settings redirects to /settings (D-05)
- `test_login_post_rejects_open_redirect_next` -- POST /login with next=http://evil.com redirects to / (T-56-14)

### Logout Route Tests (1 test)

- `test_logout_clears_cookie_and_redirects` -- POST /logout returns 303 to /login with cookie deletion (max-age=0)

## Test Coverage

- 14 new integration tests added to existing test_auth_routes.py (12 unit tests from Plan 01)
- 26 total tests in test_auth_routes.py, 726 full suite green

## TDD Gate Compliance

Implementation already existed from Plan 03, so tests were written as GREEN-from-start. This is the expected TDD pattern when testing pre-existing code -- tests serve as regression protection rather than driving implementation.

- GREEN gate: `test(56-04)` commit cd3a4b9 -- all 26 tests pass
- RED gate: skipped (implementation pre-exists from Plan 03)
- REFACTOR gate: skipped (no cleanup needed)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Replaced MagicMock with model_construct for Settings**
- **Found during:** Task 1 (RED phase)
- **Issue:** MagicMock(spec=SettingsModel) returned MagicMock from model_copy(), causing TOML serialization to fail with "Object of type 'MagicMock' is not TOML serializable"
- **Fix:** Used SettingsModel.model_construct() with real GeneralConfig and AuthConfig objects
- **Files modified:** tests/test_auth_routes.py
- **Commit:** cd3a4b9

## Threat Surface Verification

- T-56-14 (open redirect): `test_login_post_rejects_open_redirect_next` verifies _safe_next_url blocks http://evil.com
- T-56-15 (information disclosure): `test_login_post_invalid_credentials_shows_error` verifies generic "Invalid username or password" message

## Verification

- `uv run pytest tests/test_auth_routes.py -x -q` -- 26 passed
- `uv run pytest tests/ -x -q` -- 726 passed
- `uv run ruff check tests/test_auth_routes.py` -- all checks passed

## Self-Check: PASSED

All files exist, commit cd3a4b9 verified in git log, all 15 acceptance criteria functions present in test file.
