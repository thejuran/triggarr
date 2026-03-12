---
id: S02
parent: M001
milestone: M001
provides:
  - Per-instance state model with dict[str, AppState] keyed by instance name
  - v2.2 state migration wrapping flat AppState into {"Default": AppState}
  - cleanup_orphaned_instances standalone function
  - Engine, scheduler, routes, and startup updated for per-instance wiring
requires:
  - slice: S01
    provides: "InstanceConfig model with dict[str, InstanceConfig] Settings"
affects:
  - S05
  - S06
  - S07
key_files:
  - triggarr/state.py
  - triggarr/search/engine.py
  - triggarr/search/scheduler.py
  - triggarr/web/routes.py
  - triggarr/startup.py
  - tests/test_state.py
key_decisions:
  - "TriggarrState uses dict[str, AppState] for nested per-instance cursors"
  - "_default_state without settings returns empty dicts for backward compat"
  - "cleanup_orphaned_instances is standalone (not inside load_state)"
  - "Dashboard shows first enabled instance (S07 for multi-instance UI)"
  - "Tracking uses first available client per app type for grab checks"
  - "search_now triggers first enabled instance (S07 for per-instance)"
patterns_established:
  - "Per-instance state access: state['radarr']['InstanceName']"
  - "First-enabled-instance pattern for interim single-instance UI compatibility"
observability_surfaces:
  - "loguru logs during state migration and orphan cleanup"
drill_down_paths:
  - .planning/phases/34-state-model-cursor-isolation/34-01-SUMMARY.md
  - .planning/phases/34-state-model-cursor-isolation/34-02-SUMMARY.md
duration: 20min
verification_result: passed
completed_at: 2026-03-11
---

# S02: State Model & Cursor Isolation

**Per-instance state with independent round-robin cursors, v2.2 state migration, and full engine/scheduler/routes/startup rewiring**

## What Happened

Restructured TriggarrState to use `dict[str, AppState]` for radarr/sonarr, keyed by instance name. Built v2.2 state migration that wraps flat AppState into `{"Default": AppState}`. Added standalone `cleanup_orphaned_instances` to remove state for instances no longer in config. Updated all consumers (engine, scheduler, routes, startup) to iterate instances and use first-enabled-instance pattern for interim dashboard compatibility. All 371 tests passing.

## Verification

- 371 tests pass across all modules
- State isolation proven: two instances of same app type don't share cursors
- v2.2 state migration tested with round-trip verification
- Lint clean (ruff)

## Deviations

None.

## Known Limitations

- Dashboard, search_now, and tracking use first-enabled-instance — full multi-instance UI deferred to S07

## Follow-ups

- S06 needs per-instance scheduler jobs instead of first-enabled pattern
- S07 needs per-instance dashboard cards

## Files Created/Modified

- `triggarr/state.py` — Per-instance state model, v2.2 migration, orphan cleanup
- `triggarr/search/engine.py` — Cycle functions accept instance-keyed state
- `triggarr/search/scheduler.py` — Updated for per-instance scheduling
- `triggarr/web/routes.py` — Dashboard reads first enabled instance
- `triggarr/startup.py` — State migration on startup
- `tests/test_state.py` — Per-instance state tests

## Forward Intelligence

### What the next slice should know
- State is now nested: state['radarr']['InstanceName'] = AppState
- First-enabled-instance pattern is a temporary bridge — replace in S06/S07

### What's fragile
- First-enabled-instance pattern means multi-instance users only see one instance on dashboard

### Authoritative diagnostics
- test_state.py covers isolation and migration edge cases

### What assumptions changed
- None
