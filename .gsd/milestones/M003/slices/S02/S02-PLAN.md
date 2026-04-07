# S02: Search Engine & Tracking

**Goal:** `run_lidarr_cycle()` executes album-level search with round-robin cursors, tag filtering, and grab tracking — matching the Radarr cycle pattern exactly.
**Demo:** New Lidarr cycle + tracking tests pass, cycle function imported in scheduler dispatch, all existing tests still green.

## Must-Haves

- `run_lidarr_cycle()` in `triggarr/search/engine.py` matching `run_radarr_cycle` signature
- Album-level search (like Radarr movies, not Sonarr seasons — no dedup step)
- Tag filtering via `_lidarr_tags` (already exists)
- `_lidarr_outcome()` in `triggarr/tracking.py` for grab correlation
- Cycle dispatch wired in scheduler.py and routes.py
- Tests covering happy path, network failure, per-item skip, cursor advancement, tag filtering, and tracking outcomes

## Proof Level

- This slice proves: integration
- Real runtime required: no
- Human/UAT required: no

## Verification

- `uv run pytest tests/test_search.py -x -q` — all existing + new Lidarr cycle tests pass
- `uv run pytest tests/test_tracking.py -x -q` — Lidarr outcome tests pass
- `uv run pytest tests/ -x -q` — full suite green (479+ tests)
- `uv run ruff check triggarr/ tests/` — lint clean

## Observability / Diagnostics

- Runtime signals: loguru structured logs with `Lidarr:` prefix matching Radarr/Sonarr patterns
- Inspection surfaces: state dict `state["lidarr"][instance_name]` with `missing_count`, `cutoff_count`, `total_items`, `missing_cursor`, `cutoff_cursor`, `last_run`, `connected`
- Failure visibility: per-item search failures logged + stored in search_history DB with `outcome="failed"`
- Redaction constraints: API keys redacted via existing loguru redaction sink

## Integration Closure

- Upstream surfaces consumed: `LidarrClient` from S01, `_lidarr_tags()` from S01, `APP_TYPES` constant
- New wiring introduced in this slice: `run_lidarr_cycle` added to cycle dispatch dicts in scheduler.py and routes.py
- What remains before the milestone is truly usable end-to-end: S03 (scheduler jobs, dashboard cards, settings form)

## Tasks

- [x] **T01: Implement run_lidarr_cycle in search engine** `est:45m`
  - Why: Core cycle function that drives Lidarr search automation — the main deliverable of this slice
  - Files: `triggarr/search/engine.py`
  - Do: Add `run_lidarr_cycle()` after `run_sonarr_cycle()`, following `run_radarr_cycle` pattern exactly. Album-level search (like movies): fetch wanted/missing + wanted/cutoff, filter_monitored, filter_by_tag with `_lidarr_tags`, slice_batch with round-robin cursors, `client.search_albums([album_id])` per item, insert_search_entry to DB. No dedup step (albums are already unique, unlike Sonarr episodes→seasons). No `filter_unreleased` (not applicable to music). Import `LidarrClient` for type annotation.
  - Verify: `uv run ruff check triggarr/search/engine.py`
  - Done when: `run_lidarr_cycle` exists, is importable, lint clean

- [x] **T02: Add Lidarr outcome logic to tracking** `est:20m`
  - Why: Without a `_lidarr_outcome()` handler, `_determine_outcome` returns `(None, "", None)` for Lidarr — grab tracking silently does nothing
  - Files: `triggarr/tracking.py`
  - Do: Add `_lidarr_outcome()` matching `_radarr_outcome()` (binary: grabbed or unresolved — albums are atomic like movies). Add `app == "Lidarr"` branch in `_determine_outcome`. Use stat key `albums_found` for missing, `albums_updated` for cutoff.
  - Verify: `uv run ruff check triggarr/tracking.py`
  - Done when: `_determine_outcome("Lidarr", ...)` returns correct outcomes

- [x] **T03: Wire cycle dispatch and write tests** `est:45m`
  - Why: Connect `run_lidarr_cycle` to the scheduler and manual-search routes, plus comprehensive test coverage
  - Files: `triggarr/search/scheduler.py`, `triggarr/web/routes.py`, `tests/test_search.py`, `tests/test_tracking.py`
  - Do: Add `run_lidarr_cycle` to cycle_fns dicts in scheduler.py:61 and routes.py:721. Add imports. In test_search.py: add Lidarr cycle tests (happy path, network failure, per-item skip, cursor advancement, tag filtering) following the Radarr test pattern. Update `_make_test_state()` to include lidarr. In test_tracking.py: add `_lidarr_outcome` tests (grabbed, unresolved, within-window). Update conftest `make_settings` to accept lidarr params.
  - Verify: `uv run pytest tests/ -x -q` — all tests pass, `uv run ruff check triggarr/ tests/`
  - Done when: Full suite passes with new tests, cycle dispatch includes lidarr, lint clean

## Files Likely Touched

- `triggarr/search/engine.py`
- `triggarr/tracking.py`
- `triggarr/search/scheduler.py`
- `triggarr/web/routes.py`
- `tests/test_search.py`
- `tests/test_tracking.py`
- `tests/conftest.py`
