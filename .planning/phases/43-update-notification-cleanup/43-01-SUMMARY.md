---
phase: 43-update-notification-cleanup
plan: 01
subsystem: ui
tags: [httpx, apscheduler, htmx, github-api, update-check]

requires:
  - phase: 33-multi-instance-config
    provides: InstanceConfig model with ArrConfig backward-compat alias
  - phase: 42-dashboard-enhancements
    provides: Dashboard templates with health summary and stats row
provides:
  - GitHub release update check module (triggarr/update_check.py)
  - Nav bar update badge showing latest version available
  - Dismissible migration banner on dashboard
  - ArrConfig alias removed (dead code cleanup)
affects: []

tech-stack:
  added: []
  patterns:
    - "Lazy import inside closure to break circular dependency (scheduler -> routes)"
    - "Mutable dict as Jinja2 global for cross-module template state (_update_info)"

key-files:
  created:
    - triggarr/update_check.py
    - triggarr/templates/partials/migration_banner.html
    - tests/test_update_check.py
  modified:
    - triggarr/web/routes.py
    - triggarr/search/scheduler.py
    - triggarr/templates/base.html
    - triggarr/templates/dashboard.html
    - triggarr/models/config.py
    - tests/test_config.py
    - tests/test_web.py

key-decisions:
  - "Lazy import of _update_info inside update_check_job closure to avoid circular import between scheduler and routes"
  - "Mutable dict pattern for _update_info Jinja2 global (clear+update to propagate across template renders)"

patterns-established:
  - "Lazy import: use inside nested function to break circular module dependencies"

requirements-completed: [VER-02]

duration: 4min
completed: 2026-03-13
---

# Phase 43 Plan 01: Update Notification & Cleanup Summary

**GitHub release update check with nav badge, dismissible migration banner, and ArrConfig dead code removal**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-13T23:47:00Z
- **Completed:** 2026-03-13T23:51:00Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Update check module queries GitHub releases API every 24h via APScheduler
- Nav bar shows green "vX.Y.Z available" link when newer release exists
- Dashboard shows dismissible blue migration banner when .migrated marker file exists
- ArrConfig backward-compat alias removed from config.py and all test references updated

## Task Commits

Each task was committed atomically:

1. **Task 1: Update check module, migration dismiss endpoint, and tests** - `f4d327b` (test), `47089b5` (feat)
2. **Task 2: Scheduler wiring, templates, and dead code removal** - `368bb24` (feat)

_Note: Task 1 used TDD flow (RED test commit + GREEN implementation commit)_

## Files Created/Modified
- `triggarr/update_check.py` - GitHub release check with _parse_version and check_for_update
- `triggarr/templates/partials/migration_banner.html` - Dismissible blue info banner partial
- `tests/test_update_check.py` - 8 tests for version parsing and update detection
- `triggarr/web/routes.py` - Added _update_info Jinja2 global, dismiss migration endpoint, show_migration_banner context
- `triggarr/search/scheduler.py` - Wired update_check_job into APScheduler (24h interval)
- `triggarr/templates/base.html` - Added update badge after version span in nav
- `triggarr/templates/dashboard.html` - Added migration banner include
- `triggarr/models/config.py` - Removed ArrConfig = InstanceConfig alias
- `tests/test_config.py` - Replaced ArrConfig with InstanceConfig, removed alias test
- `tests/test_web.py` - Added dismiss migration endpoint tests

## Decisions Made
- Used lazy import of `_update_info` inside `update_check_job` closure to avoid circular import (scheduler imports routes, routes imports scheduler)
- Used mutable dict pattern for `_update_info` Jinja2 global -- `clear()` + `update()` so the same dict object registered in Jinja2 env gets updated in place

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed circular import between scheduler and routes**
- **Found during:** Task 2 (Scheduler wiring)
- **Issue:** Plan called for top-level `from triggarr.web.routes import _update_info` in scheduler.py, but routes.py already imports `make_search_job` from scheduler.py, creating a circular import
- **Fix:** Moved import inside the `update_check_job` closure (lazy import at call time)
- **Files modified:** triggarr/search/scheduler.py
- **Verification:** Full test suite passes (458 tests)
- **Committed in:** 368bb24

**2. [Rule 3 - Blocking] Fixed ruff import ordering violation**
- **Found during:** Task 2 (Verification)
- **Issue:** `CONFIG_DIR, Settings as SettingsModel` combined import violated ruff I001 (import block sorting)
- **Fix:** Split into separate import lines
- **Files modified:** triggarr/web/routes.py
- **Verification:** `ruff check triggarr/` clean (remaining warnings are pre-existing in test_web.py)
- **Committed in:** 368bb24

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both auto-fixes necessary for correct module loading. No scope creep.

## Issues Encountered
None beyond the deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Update notification and migration banner features complete
- All ArrConfig references cleaned up
- Ready for UAT or next milestone planning

---
*Phase: 43-update-notification-cleanup*
*Completed: 2026-03-13*

## Self-Check: PASSED
