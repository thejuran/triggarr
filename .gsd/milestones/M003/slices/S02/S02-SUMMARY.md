---
status: complete
started: 2026-04-06
completed: 2026-04-06
tests_before: 479
tests_after: 492
---

# S02: Search Engine & Tracking — Summary

## What Was Done

1. **`run_lidarr_cycle()`** added to `triggarr/search/engine.py` — follows `run_radarr_cycle` pattern exactly:
   - Album-level search (atomic like movies, no season dedup)
   - Round-robin cursors for missing and cutoff queues
   - Tag filtering via `_lidarr_tags` (artist.tags)
   - Skip-and-continue error handling per item
   - Diagnostic summary logging with elapsed time

2. **`_lidarr_outcome()`** added to `triggarr/tracking.py` — binary outcome logic:
   - Grabbed → `albums_found` (missing) or `albums_updated` (cutoff) stat
   - Unresolved when tracking window expires with no grabs
   - Dispatched from `_determine_outcome` via `app == "Lidarr"` branch

3. **Cycle dispatch wired** in scheduler.py and routes.py:
   - `run_lidarr_cycle` added to `cycle_fns` dicts in both files
   - Replaces the guard/501 response from S01 review

4. **DB migration v9**: `albums_found` + `albums_updated` columns, Lidarr seed row
   - `_ALLOWED_STAT_COLUMNS` updated to include album stats

5. **13 new tests**: 8 cycle tests + 5 tracking tests
   - Updated test fixtures: conftest, test_web, test_db all Lidarr-aware

## Key Decisions

- Album-level search (not track-level) — albums are the natural search unit in Lidarr
- Binary tracking outcome (like Radarr) — no partial state for albums
- Stat keys: `albums_found`, `albums_updated` — consistent naming with movies/episodes

## Boundary Contract Produced

- `run_lidarr_cycle()` with same signature as `run_radarr_cycle`
- `_lidarr_outcome()` integrated into tracking dispatch
- Cycle dispatch dicts include all three app types
- DB schema supports Lidarr lifetime stats

## What Remains

- S03: Scheduler job creation for Lidarr instances, dashboard cards, settings form, history filtering
