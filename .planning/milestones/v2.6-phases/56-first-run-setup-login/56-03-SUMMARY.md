---
phase: 56-first-run-setup-login
plan: 03
subsystem: auth-routes
tags: [auth, routes, setup, login, logout, session-cookie, middleware]
dependency_graph:
  requires: [_safe_next_url, _settings_to_dict-auth-extension, base-auth.html, login.html, setup.html, auth_state-global]
  provides: [setup_page, setup_post, login_page, login_post, logout, _sync_auth_state, middleware-next-param]
  affects: [nav-bar-logout-visibility, settings-save-auth-sync]
tech_stack:
  added: []
  patterns: [race-condition-double-check-locking, auth-state-sync-on-config-change]
key_files:
  created: []
  modified:
    - triggarr/web/routes.py
    - triggarr/web/middleware.py
    - tests/test_auth_middleware.py
decisions:
  - "setup_post acquires search_lock and re-checks needs_setup inside lock to prevent race condition (Pitfall 5)"
  - "login_page syncs auth_state on every load to handle app restart without explicit startup sync"
  - "middleware ?next= uses quote(safe='/') for readable slashes while encoding special characters"
metrics:
  duration: 263s
  completed: "2026-04-15T02:19:06Z"
  tasks: 2
  files: 3
---

# Phase 56 Plan 03: Auth Route Handlers and Middleware ?next= Summary

Five route handlers (GET/POST /setup, GET/POST /login, POST /logout) wired to auth.py helpers with TOML persistence, session cookies, and middleware ?next= redirect preservation.

## Task Summary

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement setup, login, and logout route handlers | ffd134e | triggarr/web/routes.py |
| 2 | Update middleware to append ?next= on login redirect | 62afa78 | triggarr/web/middleware.py, tests/test_auth_middleware.py |

## What Was Built

### Route Handlers (routes.py)

**GET /setup** - Renders first-run setup form with default "admin" username. Returns 404 if credentials already configured (needs_setup is false).

**POST /setup** - Validates username/password/confirm, creates credentials via hash_password + generate_api_key + generate_session_secret, persists to TOML via _atomic_toml_write under search_lock with double-check (re-verifies needs_setup inside lock), reloads settings via load_settings, syncs auth_state, auto-logs in via sign_session cookie, renders success page with API key display.

**GET /login** - Syncs auth_state on load, checks for existing valid session (D-06: redirects authenticated users to dashboard), renders login form with ?next= parameter passed through.

**POST /login** - Verifies username + password against stored credentials, on success sets session cookie and redirects to _safe_next_url(next) or dashboard, on failure re-renders with generic "Invalid username or password" error and username pre-filled (D-04).

**POST /logout** - Deletes triggarr_session cookie and redirects to login page via 303.

### Helper Function

**_sync_auth_state(settings)** - Updates the shared auth_state dict so templates can conditionally show/hide the logout link. Called after setup, login page load, and settings save.

### Middleware Update (middleware.py)

Step 7 fallback redirect now appends `?next=` with the URL-encoded original path, enabling post-login return to the originally requested page. Setup redirect (Step 1) unchanged -- no ?next= needed for first-run flow.

### Test Update

Updated `test_unauth_browser_redirects_to_login` assertion from `/login` to `/login?next=/` to match the new middleware behavior.

## Decisions Made

- Setup POST uses double-check locking pattern: acquires search_lock then re-verifies needs_setup to prevent concurrent setup race condition
- Login page syncs auth_state on every GET to handle app restart scenario without requiring explicit startup hook
- Middleware uses `quote(str(request.url.path), safe="/")` to keep slashes readable in the ?next= parameter

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test assertion for ?next= change**
- **Found during:** Task 2
- **Issue:** test_unauth_browser_redirects_to_login asserted exact `/login` but middleware now redirects to `/login?next=/`
- **Fix:** Updated assertion to match new behavior
- **Files modified:** tests/test_auth_middleware.py
- **Commit:** 62afa78

## Verification

- `uv run ruff check triggarr/web/routes.py` -- all checks passed
- `uv run ruff check triggarr/web/middleware.py` -- all checks passed
- `uv run pytest tests/test_auth_routes.py -x -q` -- 12 passed
- `uv run pytest tests/test_auth_middleware.py -x -q` -- 21 passed
- `uv run pytest tests/ -x -q` -- 726 passed

## Self-Check: PASSED

All modified files verified on disk. Both task commits (ffd134e, 62afa78) verified in git log.
