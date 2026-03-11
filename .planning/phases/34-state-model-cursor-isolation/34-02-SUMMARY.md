---
phase: 34-state-model-cursor-isolation
plan: 02
subsystem: search-engine
tags: [engine, scheduler, routes, startup, multi-instance, per-instance-state]

provides:
  - "Instance-aware cycle functions (run_radarr_cycle, run_sonarr_cycle)"
  - "Per-instance scheduler jobs with instance-scoped IDs"
  - "Per-instance client creation and shutdown in lifespan"
  - "Orphan cleanup and default state initialization in lifespan"
  - "Per-instance state reading in dashboard routes"
  - "Dict-based settings iteration in startup functions"
affects: [39-settings-ui]

tech-stack:
  added: []
  patterns: [per-instance-cycle-dispatch, instance-scoped-job-ids, nested-state-consumers]

key-files:
  created: []
  modified:
    - triggarr/search/engine.py
    - triggarr/search/scheduler.py
    - triggarr/web/routes.py
    - triggarr/startup.py
    - tests/test_search.py
    - tests/test_scheduler.py
    - tests/test_web.py
    - tests/test_startup.py

key-decisions:
  - "Dashboard shows first enabled instance state (Phase 39 adds multi-instance UI)"
  - "Settings form saves as single instance under existing name (Phase 39 for editing)"
  - "search_now triggers first enabled instance (Phase 39 for per-instance triggers)"
  - "Tracking uses first available client per app type for grab history checks"

metrics:
  duration: 18min
  completed: "2026-03-11T02:33:00Z"
  tasks_completed: 2
  tasks_total: 2
  test_count: 342
  test_result: all_passing
---

# Phase 34 Plan 02: Per-Instance State Consumers Summary

Wired the nested per-instance state model through all consumer files (engine, scheduler, routes, startup), completing INST-03 multi-instance cursor isolation.

## What Was Built

### Engine Cycle Functions (triggarr/search/engine.py)

Updated `run_radarr_cycle` and `run_sonarr_cycle` signatures to accept `instance_name: str` and `instance_config: InstanceConfig` parameters. All state access changed from `state["radarr"]` to `state["radarr"][instance_name]`. Batch sizes read from `instance_config` instead of `settings.radarr`. General config (hard_max, skip_unreleased, max_history_rows) still from `settings` param.

### Scheduler (triggarr/search/scheduler.py)

- `make_search_job` accepts `instance_name` parameter, looks up client from `app.state.{app_name}_clients` dict
- `create_lifespan` calls `cleanup_orphaned_instances` after `load_state`
- New instances automatically get `_default_instance_state()` entries
- Client creation iterates `settings.get_enabled_instances(app_name)` to create per-instance clients stored in `app.state.radarr_clients` / `app.state.sonarr_clients` dicts
- Jobs scheduled per instance with ID format `{app_name}_{instance_name}_search`
- Shutdown iterates all client dicts to close connections

### Routes (triggarr/web/routes.py)

- `_build_app_context` reads first enabled instance's state (Phase 39: multi-instance dashboard)
- `health` endpoint iterates all enabled instances, checking `connected` status
- `settings_page` reads first instance per app type for form display
- `save_settings` constructs nested `{"Default": {...}}` config shape
- Scheduler updates handle per-instance job IDs and client dicts
- `search_now` passes `instance_name` and `instance_config` to cycle functions

### Startup (triggarr/startup.py)

- `collect_secrets` iterates `settings.radarr.values()` and `settings.sonarr.values()`
- `print_banner` shows per-instance status lines
- `check_localhost_urls` iterates enabled instances
- `validate_connections` iterates `settings.get_enabled_instances()` per app type

### Test Updates

All test files updated for nested state format and dict-based settings:
- `test_search.py`: 52 tests with new cycle function signatures
- `test_scheduler.py`: Updated to use `_clients` dicts and `make_search_job` with `instance_name`
- `test_web.py`: Real Settings objects instead of MagicMock, nested state structure
- `test_startup.py`: `InstanceConfig` dict-based Settings construction

## TDD Execution (Task 1)

- **RED:** Updated all engine test calls to new 6-arg signature -- TypeError confirmed
- **GREEN:** Implemented `instance_name`/`instance_config` params, nested state access -- all 52 pass

## Deviations from Plan

None -- plan executed exactly as written.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| 08fe9f4 | test | Update engine tests for per-instance cycle signatures (RED) |
| bf88a89 | feat | Update engine cycle functions for per-instance state access (GREEN) |
| 222020f | feat | Update scheduler, routes, and startup for per-instance wiring |

## Self-Check: PASSED

All files exist. All commits verified.
