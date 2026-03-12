---
phase: 40-fix-multi-instance-bugs-and-hardening
plan: 01
subsystem: search-engine
tags: [multi-instance, state-management, setdefault, bug-fix]

requires:
  - phase: 34-state-and-scheduler-per-instance
    provides: per-instance state structure and TriggarrState TypedDict
provides:
  - setdefault guard in run_radarr_cycle and run_sonarr_cycle for missing instance state
  - per-instance keyed connection validation results
  - state initialization for runtime-added instances in save_settings
affects: [40-02, 40-03, search-engine, web-routes, startup]

tech-stack:
  added: []
  patterns: [setdefault guard before accessing per-instance state]

key-files:
  created: []
  modified:
    - triggarr/search/engine.py
    - triggarr/startup.py
    - triggarr/web/routes.py
    - tests/test_search.py
    - tests/test_startup.py
    - tests/test_web.py

key-decisions:
  - "setdefault with _default_instance_state() as guard pattern for missing state entries"
  - "validate_connections keys results as 'app/instance' (e.g., 'radarr/Default') for unique per-instance tracking"
  - "save_settings persists state after adding new instance entries to prevent loss on restart"

patterns-established:
  - "setdefault guard: always call state[app].setdefault(instance_name, _default_instance_state()) before accessing per-instance state"

requirements-completed: [BUG-01, BUG-02, BUG-03]

duration: 19min
completed: 2026-03-11
---

# Phase 40 Plan 01: Fix Multi-Instance Crash Bugs Summary

**setdefault guards in engine cycle functions, per-instance keyed connection validation, and runtime state initialization in save_settings**

## Performance

- **Duration:** 19 min
- **Started:** 2026-03-12T01:04:18Z
- **Completed:** 2026-03-12T01:23:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Engine cycle functions (run_radarr_cycle, run_sonarr_cycle) no longer crash with KeyError when instance state is missing
- validate_connections returns per-instance keyed results, preventing last-instance-wins data loss
- save_settings creates default state entries for newly enabled instances and persists to disk

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix engine.py KeyError and startup.py loop overwrite** - `9190e0a` (test) + `d006eeb` (fix)
2. **Task 2: Fix save_settings missing state entry** - `7a2687f` (test) + `6c51d81` (fix)

_Note: TDD tasks have RED (test) + GREEN (fix) commits_

## Files Created/Modified
- `triggarr/search/engine.py` - Added setdefault guard and _default_instance_state import
- `triggarr/startup.py` - Keyed results by "app/instance", updated log summary parsing
- `triggarr/web/routes.py` - Added state initialization for new instances after scheduler setup
- `tests/test_search.py` - Added tests for missing instance state handling
- `tests/test_startup.py` - Added tests for multi-instance connection validation
- `tests/test_web.py` - Added tests for state creation in save_settings

## Decisions Made
- Used setdefault with _default_instance_state() as the guard pattern -- minimal, idempotent, and consistent with existing state.py patterns
- Keyed validate_connections results as "radarr/Default" format -- human-readable and unique per instance
- Persist state in save_settings after instance creation -- prevents loss if process restarts before first cycle

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing failing test `test_save_settings_preserves_non_edited_instances` from plan 40-03 (BUG-05) -- not caused by this plan's changes, excluded from verification

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All three crash-causing bugs fixed (BUG-01, BUG-02, BUG-03)
- Ready for plan 40-02 (additional bug fixes) and plan 40-03 (hardening)
- 405 tests passing, no ruff violations

---
*Phase: 40-fix-multi-instance-bugs-and-hardening*
*Completed: 2026-03-11*
