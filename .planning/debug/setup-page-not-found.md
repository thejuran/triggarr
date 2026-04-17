---
status: resolved
trigger: "http://maguffynas:8484/setup returns Not Found on fresh install when trying to set up first account"
created: 2026-04-15
updated: 2026-04-15
---

# Debug: Setup Page Not Found

## Symptoms

- **Expected:** Account setup form should appear at /setup for first-time admin account creation
- **Actual:** "Not Found" error when visiting /setup
- **Error:** HTTP 404 Not Found
- **Timeline:** Fresh install, first time trying to set up an account
- **Reproduction:** Visit http://maguffynas:8484/setup in browser

## Current Focus

- hypothesis: confirmed
- test: 806 tests pass, 0 failures, ruff clean
- expecting: /setup redirects to /login?setup=done when auth already configured
- next_action: none (resolved)
- reasoning_checkpoint: Fix applied and verified

## Evidence

- timestamp: 2026-04-15 E1: GET /setup route (routes.py:1013-1023) explicitly returns HTMLResponse(status_code=404, content="Not Found") when auth.needs_setup is False
- timestamp: 2026-04-15 E2: needs_setup property (config.py:97-99) returns `not self.username` -- True only when username is empty string
- timestamp: 2026-04-15 E3: Default AuthConfig has username="" so needs_setup=True on genuinely fresh installs -- confirmed via test
- timestamp: 2026-04-15 E4: POST /setup writes auth config to TOML BEFORE returning the response (routes.py:1077-1081), creating a window where setup completes but response is lost
- timestamp: 2026-04-15 E5: Middleware EXEMPT_PREFIXES includes "/setup" so auth middleware is not blocking access
- timestamp: 2026-04-15 E6: All 17 existing setup tests pass -- the route works correctly for fresh installs in test harness
- timestamp: 2026-04-15 E7: Full production app simulation (exact middleware stack, mount order) confirms /setup returns 200 with "Welcome to Triggarr" on default settings

## Eliminated

- Middleware blocking /setup: EXEMPT_PREFIXES includes "/setup", confirmed exempt
- Route not registered: confirmed at index 22 in app.routes
- Template missing: setup.html and base-auth.html both exist
- StaticFiles mount shadowing: /static mount only matches /static/* paths
- ROOT_PATH interference: tested with root_path, /setup still resolves correctly
- TOML round-trip corruption: empty string username survives write/read cycle
- TomlConfigSettingsSource conflict: confirmed init_settings takes priority correctly

## Resolution

- root_cause: The /setup route returns a bare 404 "Not Found" when auth is already configured (needs_setup=False). On a "fresh install" with a reused Docker volume or after a partial setup completion where the HTTP response was lost, the config already has a non-empty username. The 404 response provides zero context -- the user has no idea they need to go to /login instead, or that their config volume is stale.
- fix: Replaced all three bare 404 responses in GET /setup, POST /setup, and the race-condition guard inside POST /setup with 302 redirects to /login?setup=done. Updated login.html template to show an info message ("Account setup has already been completed. Please sign in.") when ?setup=done is present. Updated login route to pass info context variable. Added new test test_setup_redirect_shows_info_on_login_page.
- verification: 806 tests pass, ruff clean, new test confirms redirect + info message flow
- files_changed: triggarr/web/routes.py, triggarr/templates/login.html, tests/test_auth_routes.py
