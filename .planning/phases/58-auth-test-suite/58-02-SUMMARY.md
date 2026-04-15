---
phase: 58-auth-test-suite
plan: 02
subsystem: auth-integration-tests
tags: [testing, auth, integration, end-to-end]
dependency_graph:
  requires: [auth-gap-fill-tests]
  provides: [auth-integration-tests]
  affects: [tests/test_auth_integration.py]
tech_stack:
  added: []
  patterns: [multi-step-flow-tests, cross-module-integration]
key_files:
  created:
    - tests/test_auth_integration.py
  modified: []
decisions:
  - Used /settings as protected route in integration tests because dashboard requires DB/scheduler state not needed for auth flow verification
metrics:
  duration: 249s
  completed: "2026-04-15T18:49:03Z"
---

# Phase 58 Plan 02: Auth Integration Tests Summary

Cross-cutting end-to-end auth flow tests verifying middleware + routes + auth helpers + config cooperation through multi-step user scenarios using TestClient with real route handlers.

## Task Completion

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create test_auth_integration.py with cross-cutting end-to-end flow tests | 5ebd6bc | tests/test_auth_integration.py |

## What Was Built

### Task 1: Integration Flow Tests (3 new tests)

- **test_full_setup_login_use_logout_flow** (SC-2 + SC-3): Complete lifecycle from unconfigured app through setup (auto-login), access protected route, logout, verify access denied, manual login with setup credentials, verify access restored. 7-step flow.
- **test_setup_then_api_key_access** (SC-5): After setup POST, reads API key from saved TOML config file, uses X-Api-Key header to access protected route. Verifies setup handler updates app.state.settings via load_settings() so middleware sees new API key.
- **test_password_change_old_session_still_valid** (SC-3): Signs session cookie, verifies access, changes password, verifies old session cookie still works because session_secret is unchanged (only password_hash changed).

All tests use `_make_route_app` factory with real AuthMiddleware and route handlers, `follow_redirects=False` for redirect assertions, `tmp_path` for TOML config writes, and `_reset_auth_state` fixture to prevent test pollution.

## Decisions Made

- **Protected route choice**: Used `/settings` instead of `/` (dashboard) as the protected route for integration assertions. The dashboard handler requires `app.state.db` (aiosqlite connection), `app.state.triggarr_state`, and `app.state.scheduler` which are heavy to mock. `/settings` only needs `app.state.settings`, making it ideal for testing auth flow without unrelated infrastructure.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Logout redirect uses full URL in TestClient**
- **Found during:** Task 1
- **Issue:** `resp.headers["location"]` returns `http://testserver/login` not `/login` because logout handler uses `request.url_for()` which produces absolute URLs in TestClient
- **Fix:** Changed assertion from `== "/login"` to `in resp.headers["location"]`
- **Files modified:** tests/test_auth_integration.py
- **Commit:** 5ebd6bc

**2. [Rule 3 - Blocking] Dashboard route requires DB state not present in test factory**
- **Found during:** Task 1
- **Issue:** Dashboard handler calls `get_dashboard_stats(request.app.state.db)` which uses `async with db.execute()` -- impossible to mock with simple AsyncMock
- **Fix:** Changed protected route from `/` to `/settings` which only needs `app.state.settings`
- **Files modified:** tests/test_auth_integration.py
- **Commit:** 5ebd6bc

## Verification

- `uv run pytest tests/test_auth_integration.py -x -q` -- 3 passed
- `uv run pytest tests/test_auth_config.py tests/test_auth_helpers.py tests/test_auth_middleware.py tests/test_auth_routes.py tests/test_auth_integration.py -x -q` -- 109 passed
- `uv run pytest tests/ -x -q` -- 774 passed
- `uv run ruff check tests/test_auth_integration.py` -- All checks passed
- Test count: 774 total (771 before + 3 new integration tests)

## Self-Check: PASSED
