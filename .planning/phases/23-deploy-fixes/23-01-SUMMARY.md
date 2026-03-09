---
phase: 23-deploy-fixes
plan: 01
subsystem: infra
tags: [docker, reverse-proxy, uvicorn, root-path, config-dir]

# Dependency graph
requires: []
provides:
  - "TRIGGARR_CONFIG_DIR env var for configurable config/state/db directory"
  - "ROOT_PATH env var for reverse proxy sub-path deployment"
  - "All template URLs use url_for for root_path awareness"
affects: [deployment, docker, reverse-proxy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "get_config_dir() / get_state_path() / get_root_path() functions for testable env var reading"
    - "url_for in all templates and routes for root_path-aware URLs"

key-files:
  created:
    - tests/test_config_dir.py
    - tests/test_root_path.py
  modified:
    - triggarr/models/config.py
    - triggarr/state.py
    - triggarr/__main__.py
    - triggarr/templates/base.html
    - triggarr/templates/dashboard.html
    - triggarr/templates/partials/app_card.html
    - triggarr/templates/partials/history_results.html
    - triggarr/templates/partials/log_viewer.html
    - triggarr/templates/partials/search_log.html
    - triggarr/templates/partials/stats_row.html
    - triggarr/web/routes.py
    - entrypoint.sh
    - tests/test_web.py

key-decisions:
  - "Used get_config_dir() function pattern for testable env var reading without module reload"
  - "Used url_for throughout all templates and route redirects for consistent root_path support"

patterns-established:
  - "Env var config pattern: extract into named function, call at module level for constant"
  - "All template hrefs and hx-get/hx-post use url_for, never hardcoded paths"

requirements-completed: [DEPLOY-01, DEPLOY-02]

# Metrics
duration: 9min
completed: 2026-03-08
---

# Phase 23 Plan 01: Deploy Fixes Summary

**Configurable config directory via TRIGGARR_CONFIG_DIR and reverse proxy support via ROOT_PATH with url_for across all templates**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-09T03:08:06Z
- **Completed:** 2026-03-09T03:16:41Z
- **Tasks:** 2
- **Files modified:** 15

## Accomplishments
- TRIGGARR_CONFIG_DIR env var controls config, state, and DB file locations (defaults to /config)
- ROOT_PATH env var enables sub-path reverse proxy deployment via uvicorn root_path
- All template URLs (nav links, htmx endpoints, static assets) use url_for for root_path awareness
- Route redirects in save_settings use url_for instead of hardcoded paths
- 8 new tests, all 265 tests pass, no ruff violations, Docker builds

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: Configurable config directory via TRIGGARR_CONFIG_DIR**
   - `cb5d0cc` (test) - RED: failing tests for TRIGGARR_CONFIG_DIR
   - `09d4e96` (feat) - GREEN: implementation in config.py, state.py, entrypoint.sh
2. **Task 2: Reverse proxy support via ROOT_PATH**
   - `9fcc47f` (test) - RED: failing tests for ROOT_PATH
   - `68e9070` (feat) - GREEN: implementation in __main__.py, all templates, routes.py

## Files Created/Modified
- `triggarr/models/config.py` - get_config_dir() reads TRIGGARR_CONFIG_DIR, CONFIG_DIR/CONFIG_PATH derived from it
- `triggarr/state.py` - get_state_path() derives STATE_PATH from get_config_dir()
- `triggarr/__main__.py` - get_root_path() reads ROOT_PATH, passed to uvicorn config
- `triggarr/templates/base.html` - Nav links use url_for instead of hardcoded paths
- `triggarr/templates/dashboard.html` - Settings link uses url_for
- `triggarr/templates/partials/app_card.html` - hx-get/hx-post use url_for
- `triggarr/templates/partials/history_results.html` - All filter/pagination hx-get use url_for
- `triggarr/templates/partials/log_viewer.html` - hx-get uses url_for
- `triggarr/templates/partials/search_log.html` - hx-get uses url_for
- `triggarr/templates/partials/stats_row.html` - hx-get uses url_for
- `triggarr/web/routes.py` - RedirectResponse URLs use url_for
- `entrypoint.sh` - CONFIG_DIR from TRIGGARR_CONFIG_DIR, mkdir/chown use variable
- `tests/test_config_dir.py` - 5 tests for config dir env var behavior
- `tests/test_root_path.py` - 3 tests for root path and url_for in templates
- `tests/test_web.py` - Updated 4 assertions to handle url_for full URLs

## Decisions Made
- Used `get_config_dir()` function pattern to make env var reading testable without module reload hacks
- Used `url_for` throughout all templates and route redirects for consistent root_path support

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed existing test assertions for url_for URL format**
- **Found during:** Task 2 (ROOT_PATH implementation)
- **Issue:** Existing tests in test_web.py asserted hardcoded paths like `href="/settings"` and `hx-get="/partials/stats-row"`, but url_for returns full URLs in test client (e.g., `http://testserver/settings`)
- **Fix:** Updated 4 assertions to use `endswith("/settings")`, substring match `"/history" in response.text`, and `"/partials/stats-row" in response.text`
- **Files modified:** tests/test_web.py
- **Verification:** All 265 tests pass
- **Committed in:** 68e9070 (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Necessary fix for existing tests to accommodate url_for behavior. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both deploy features complete and backward compatible
- Ready for Docker deployment with TRIGGARR_CONFIG_DIR and ROOT_PATH env vars
- Docker image builds successfully

---
*Phase: 23-deploy-fixes*
*Completed: 2026-03-08*
