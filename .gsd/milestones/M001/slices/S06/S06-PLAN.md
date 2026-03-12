# S06: Scheduler & Tracking Wiring

**Goal:** Each enabled instance's tracking uses its own client scoped to its own DB entries. The scheduler job runs tracking per-instance rather than globally with first-available clients.
**Demo:** Two Radarr instances with different tracked entries — each resolves grabs only using its own client and its own pending entries.

## Must-Haves

- `run_tracking_check` refactored to accept a single client + instance_id, scoping entries to that instance
- `make_search_job` calls tracking with the instance's own client and instance_id
- Tracking no longer uses first-available client pattern
- All existing scheduler and tracking tests pass with updated signatures
- New tests prove per-instance tracking isolation

## Proof Level

- This slice proves: integration
- Real runtime required: no
- Human/UAT required: no

## Verification

- `pytest tests/test_tracking.py -v` — all tests pass with updated signatures
- `pytest tests/test_scheduler.py -v` — all tests pass with per-instance tracking
- `pytest -x -q` — full suite green
- `ruff check triggarr/ tests/` — lint clean

## Observability / Diagnostics

- Runtime signals: loguru logs include instance_id in tracking messages
- Inspection surfaces: tracking entries scoped by instance_id in DB
- Failure visibility: per-instance tracking error counts in result dict
- Redaction constraints: none

## Integration Closure

- Upstream surfaces consumed: `instance_id` on DB functions (S05), per-instance clients on app.state (S02), `instance_name` in make_search_job (S02)
- New wiring introduced in this slice: per-instance tracking call in make_search_job, instance-scoped get_trackable_entries call
- What remains before the milestone is truly usable end-to-end: S07 (web UI integration — per-instance dashboard, settings, history filter)

## Tasks

- [x] **T01: Refactor run_tracking_check for single-client per-instance tracking** `est:20m`
  - Why: Currently accepts radarr_client + sonarr_client and queries all entries globally. Needs to accept a single client + app_name + instance_id to scope tracking to one instance.
  - Files: `triggarr/tracking.py`, `tests/test_tracking.py`
  - Do:
    1. Change `run_tracking_check` signature: replace `radarr_client`/`sonarr_client` with `client: RadarrClient | SonarrClient`, `app_name: str`, `instance_id: str`
    2. Call `get_trackable_entries(db, instance_id=instance_id)` to scope entries
    3. Remove `_get_client` helper — client is passed directly
    4. Filter entries to matching app_name (belt-and-suspenders since instance_id should already scope correctly)
    5. Pass `instance_id` to `update_outcome_and_stats`
    6. Add instance_id to log messages for clarity
    7. Update all existing tracking tests for new signature
    8. Add test: two instances' entries don't cross-contaminate during tracking
  - Verify: `pytest tests/test_tracking.py -v` — all pass
  - Done when: run_tracking_check is instance-scoped, all tracking tests green

- [x] **T02: Wire per-instance tracking into make_search_job** `est:15m`
  - Why: The scheduler job currently passes first-available client to tracking. It should pass the instance's own client and instance_id.
  - Files: `triggarr/search/scheduler.py`, `tests/test_scheduler.py`
  - Do:
    1. In make_search_job's `job()` closure: replace the global tracking call with per-instance call — pass the instance's client, app_name, instance_name to run_tracking_check
    2. Remove the first-available client pattern for tracking
    3. Update scheduler tests that mock run_tracking_check to match new signature
    4. Add test: tracking is called with correct client and instance_id
  - Verify: `pytest tests/test_scheduler.py -v` — all pass
  - Done when: make_search_job runs per-instance tracking, scheduler tests green, full suite green

## Files Likely Touched

- `triggarr/tracking.py`
- `triggarr/search/scheduler.py`
- `tests/test_tracking.py`
- `tests/test_scheduler.py`
