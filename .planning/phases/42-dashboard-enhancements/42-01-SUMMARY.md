---
phase: 42-dashboard-enhancements
plan: 01
subsystem: web, search-engine, state
tags: [dashboard, health-summary, tag-warnings, stats-filter]
dependency_graph:
  requires: []
  provides: [health-summary-route, tag-warning-state, stats-instance-filter]
  affects: [triggarr/web/routes.py, triggarr/search/engine.py, triggarr/state.py]
tech_stack:
  added: []
  patterns: [health-summary-computation, tag-warning-storage, instance-scoped-stats]
key_files:
  created:
    - triggarr/templates/partials/health_summary.html
  modified:
    - triggarr/state.py
    - triggarr/search/engine.py
    - triggarr/web/routes.py
    - tests/test_search.py
    - tests/test_web.py
decisions:
  - tag_warnings cleared at cycle start (not accumulated across cycles)
  - health summary iterates only enabled instances via get_enabled_instances
  - stats-row instance filter splits on "/" for app_type/instance_name
  - tag_warnings defaults to [] in _build_app_context for backward compat
metrics:
  duration: 9min
  completed: 2026-03-13
---

# Phase 42 Plan 01: Dashboard Backend Data Paths Summary

Tag warning state storage in search engine, health summary route, instance-filtered stats, and tag_warnings context passthrough.

## What Was Done

### Task 1: Tag Warning State Storage and AppState Update (8aa5a55)

- Added `tag_warnings: list[dict]` field to `AppState` TypedDict in `triggarr/state.py`
- Modified both `run_radarr_cycle` and `run_sonarr_cycle` in `triggarr/search/engine.py`:
  - Clear `ist["tag_warnings"] = []` at start of tag resolution (before any tag checks)
  - Append `{"tag": name, "field": "missing"}` when missing tag not found and `tag_fetch_ok=True`
  - Append `{"tag": name, "field": "cutoff"}` when cutoff tag not found and `tag_fetch_ok=True`
  - Set `ist["tag_warnings"] = []` even when no tags configured (always initialized)
- Added 6 tests in `tests/test_search.py`:
  - Radarr/Sonarr tag not found stores warning dicts
  - Tags resolve successfully stores empty list
  - No tags configured stores empty list
  - Warnings cleared each cycle (no accumulation)
  - Both missing and cutoff tag warnings stored together

### Task 2: Health Summary, Stats Filter, Tag Passthrough (2590108)

- Added `_build_health_summary(request)` helper: iterates enabled instances, counts connected/disconnected/pending
- Added `_build_all_instances(settings)` helper: builds dropdown filter data
- Added `GET /partials/health-summary` route returning health counts HTML
- Extended `GET /partials/stats-row` to accept `?instance=app/name` query param:
  - Splits on "/" to extract app_type and instance_name
  - Passes instance_id to `get_dashboard_stats`
  - Determines instance_app_type for template context
- Added `tag_warnings` to `_build_app_context` return dict (defaults to `[]`)
- Updated `dashboard` route to pass health summary and all_instances context
- Created `health_summary.html` partial template
- Added 7 tests in `tests/test_web.py`:
  - Health summary counts (connected, pending, disconnected)
  - Disabled instances excluded from health summary
  - Stats-row instance filter passes instance_id correctly
  - Stats-row without filter passes instance_id=None
  - App context includes tag_warnings
  - Dashboard includes health and all_instances

## Deviations from Plan

None - plan executed exactly as written.

## Verification

- All 180 tests pass (85 search + 95 web)
- Ruff lint clean on all 3 modified source files
- No pre-existing tests broken
