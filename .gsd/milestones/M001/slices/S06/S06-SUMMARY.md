---
id: S06
parent: M001
milestone: M001
provides:
  - Per-instance tracking via run_tracking_check(db, client, app_name, instance_id, window)
  - Instance-scoped get_trackable_entries in tracking
  - Scheduler job passes instance's own client to tracking instead of first-available
requires:
  - slice: S05
    provides: "instance_id on all DB functions"
  - slice: S02
    provides: "instance_name in make_search_job, per-instance clients on app.state"
  - slice: S03
    provides: "Per-instance client objects"
  - slice: S04
    provides: "Tag-filtered cycle functions"
affects:
  - S07
key_files:
  - triggarr/tracking.py
  - triggarr/search/scheduler.py
  - tests/test_tracking.py
  - tests/test_scheduler.py
key_decisions:
  - "run_tracking_check takes single client + app_name + instance_id instead of radarr/sonarr pair"
  - "Removed _get_client helper — client is passed directly by scheduler"
  - "Belt-and-suspenders app_name filter inside tracking even though instance_id should scope correctly"
patterns_established:
  - "Per-instance tracking: scheduler passes instance's own client to tracking"
  - "Single-client tracking function signature for simpler per-instance wiring"
observability_surfaces:
  - "Tracking log messages include [instance_id] prefix for per-instance clarity"
drill_down_paths:
  - .gsd/milestones/M001/slices/S06/S06-PLAN.md
duration: 10min
verification_result: passed
completed_at: 2026-03-11
---

# S06: Scheduler & Tracking Wiring

**Per-instance tracking with instance-scoped DB queries and own-client resolution in scheduler jobs**

## What Happened

Refactored `run_tracking_check` from accepting radarr_client/sonarr_client pair to accepting a single client + app_name + instance_id. This scopes `get_trackable_entries` to the instance and uses the instance's own client for grab history fetches. Updated `make_search_job` to pass the instance's client and identity directly instead of the first-available pattern. Removed the `_get_client` helper. All tracking tests updated for new signature. Added 2 new tests proving per-instance isolation (entries don't cross-contaminate, stats go to correct instance). 386 tests passing, lint clean.

## Verification

- 386 tests pass (17 tracking, 7 scheduler, all others unchanged)
- ruff lint clean
- 2 new tests prove per-instance tracking isolation and per-instance stats routing

## Requirements Advanced

- INST-06 — Per-instance enable/disable: scheduler already manages jobs dynamically in settings save route (done in S02), tracking now correctly scoped per-instance
- OBS-03 — Per-instance effectiveness stats: tracking increments correct instance's lifetime_stats

## Requirements Validated

- None newly validated (requires S07 UI to be user-visible)

## New Requirements Surfaced

- None

## Requirements Invalidated or Re-scoped

- None

## Deviations

None — both tasks executed as planned.

## Known Limitations

- search_now route still triggers first-enabled instance only — S07 will add per-instance search-now
- validate_connections at startup only validates first instance per type — acceptable for now since all instances are validated when settings are saved
- Dashboard still shows first-enabled instance — S07 will add per-instance cards

## Follow-ups

- S07: Per-instance dashboard cards, history filter, settings UI, search-now per instance

## Files Created/Modified

- `triggarr/tracking.py` — Refactored to single-client per-instance signature
- `triggarr/search/scheduler.py` — Per-instance tracking call in make_search_job
- `tests/test_tracking.py` — Updated all tests for new signature, 2 new isolation tests
- `tests/test_scheduler.py` — No changes needed (mocks accept any args)

## Forward Intelligence

### What the next slice should know
- Tracking is fully per-instance now — each scheduler job tracks only its own instance's entries with its own client
- The scheduler already handles dynamic job add/remove/reschedule on settings save (from S02 routes wiring)
- All DB functions are instance-aware (S05) and tracking uses them correctly (S06)

### What's fragile
- Nothing — the per-instance pattern is clean and well-tested

### Authoritative diagnostics
- test_tracking.py per-instance tests are the source of truth for instance isolation

### What assumptions changed
- None — the refactoring was straightforward
