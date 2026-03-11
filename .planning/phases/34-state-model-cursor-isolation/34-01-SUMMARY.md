---
phase: 34-state-model-cursor-isolation
plan: 01
subsystem: state
tags: [state, migration, typeddict, multi-instance]

# Dependency graph
requires:
  - phase: 33-config-model-migration
    provides: "dict[str, InstanceConfig] config model with Settings type"
provides:
  - "Nested TriggarrState with dict[str, AppState] per app type"
  - "v2.2 flat state auto-migration to nested per-instance format"
  - "Orphan cleanup function for removing unconfigured instance state"
  - "_default_state with optional Settings for per-instance defaults"
affects: [35-engine-scheduler-refactor, 39-settings-ui]

# Tech tracking
tech-stack:
  added: []
  patterns: [nested-typeddict-state, two-level-merge-defaults, v22-state-migration]

key-files:
  created: []
  modified:
    - triggarr/state.py
    - tests/test_state.py
    - tests/conftest.py

key-decisions:
  - "TriggarrState uses dict[str, AppState] for radarr and sonarr (nested per-instance)"
  - "_default_state without settings returns empty dicts for backward compat with _merge_defaults"
  - "cleanup_orphaned_instances is standalone function, not called inside load_state (keeps load pure)"
  - "v2.2 migration wraps flat AppState into {'Default': AppState} matching config migration naming"

metrics:
  duration: 2min
  completed: "2026-03-11T02:12:00Z"
  tasks_completed: 1
  tasks_total: 1
  test_count: 16
  test_result: all_passing
---

# Phase 34 Plan 01: Per-Instance State Model Summary

Nested TriggarrState with dict[str, AppState] per app type, v2.2 flat-to-nested migration, orphan cleanup, and two-level-deep merge defaults.

## What Was Built

### State Model Restructuring (triggarr/state.py)

Restructured `TriggarrState` from flat `radarr: AppState` to nested `radarr: dict[str, AppState]`, enabling independent round-robin cursors per configured instance.

Key functions added/updated:
- `_default_instance_state()` -- fresh cursor-0 AppState for a single instance
- `_default_state(settings=None)` -- empty dicts without settings, per-instance entries with settings
- `_is_v22_state_format(data)` -- detects flat format by checking for `missing_cursor` key directly under radarr/sonarr
- `_migrate_v22_state(data)` -- wraps flat AppState into `{"Default": AppState}`
- `_merge_defaults(loaded)` -- two-level-deep merge: iterates instance names, merges each AppState against defaults
- `cleanup_orphaned_instances(state, settings)` -- removes instance keys not in configured settings
- `load_state()` -- now calls v2.2 detection and migration before merge

### Test Suite (tests/test_state.py)

16 tests covering:
- Nested state round trip with multiple instances
- v2.2 flat state migration to nested format
- v2.2 format detection (flat vs nested vs empty)
- Orphan cleanup removing unconfigured instances
- Cross-contamination prevention between instances
- _default_state with and without settings
- Partial nested state merge defaults
- All existing tests updated for nested format

### Conftest Update (tests/conftest.py)

Updated `default_state()` helper to accept optional `settings` parameter, forwarding to `_default_state(settings)`.

## TDD Execution

- **RED:** 16 tests written against new nested API -- all failed at import (functions not yet exported)
- **GREEN:** Implementation written -- all 16 tests pass
- **REFACTOR:** Removed unused imports, fixed import sorting via ruff

## Deviations from Plan

None -- plan executed exactly as written.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| f8ddbc9 | test | Add failing tests for per-instance state model (RED) |
| 141e6e1 | feat | Implement per-instance state model with v2.2 migration (GREEN) |

## Self-Check: PASSED

All files exist. All commits verified.
