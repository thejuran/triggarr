---
id: S05
parent: M001
milestone: M001
provides:
  - instance_id column on search_history with 'Default' default and index
  - lifetime_stats table with (app, instance_id) composite primary key
  - instance_id parameter on all DB CRUD functions with backward-compatible defaults
  - Engine cycle functions pass instance_name into DB inserts
  - Tracking passes instance_id from DB rows to stat updates
requires:
  - slice: S01
    provides: "InstanceConfig model with instance names"
  - slice: S02
    provides: "instance_name parameter in cycle function signatures"
affects:
  - S06
  - S07
key_files:
  - triggarr/db.py
  - triggarr/search/engine.py
  - triggarr/tracking.py
  - tests/test_db.py
key_decisions:
  - "instance_id defaults to 'Default' everywhere for backward compat with existing single-instance data"
  - "lifetime_stats rebuilt with composite PK via table-swap migration (CREATE new → INSERT from old → DROP old → RENAME)"
  - "update_outcome_and_stats auto-creates stats rows with INSERT OR IGNORE before incrementing"
  - "instance_id included in returned dicts from all query functions for downstream consumption"
patterns_established:
  - "instance_id='Default' as universal backward-compat default"
  - "Optional instance_id/instance_filter on query functions — None means no filtering (all instances)"
  - "INSERT OR IGNORE to ensure stats row exists before UPDATE"
observability_surfaces:
  - "loguru logs during migration v6/v7 execution"
  - "search_history.instance_id column directly queryable"
  - "lifetime_stats (app, instance_id) composite key for per-instance stat inspection"
drill_down_paths:
  - .gsd/milestones/M001/slices/S05/S05-PLAN.md
duration: 15min
verification_result: passed
completed_at: 2026-03-11
---

# S05: Database Schema & Instance Scoping

**instance_id column on search_history, composite-key lifetime_stats, and instance-scoped DB functions threaded from engine/tracking**

## What Happened

Added two schema migrations: v6 adds `instance_id TEXT DEFAULT 'Default'` to search_history with a covering index; v7 rebuilds lifetime_stats with composite `(app, instance_id)` primary key via table-swap pattern, preserving existing data under 'Default' instance. Threaded `instance_id` parameter through all 6 DB CRUD functions (insert_search_entry, get_recent_searches, get_search_history, get_trackable_entries, update_outcome_and_stats, get_dashboard_stats) with backward-compatible defaults. Updated all 8 insert_search_entry calls in engine cycle functions to pass `instance_name`. Updated tracking to pass `instance_id` from DB entries to update_outcome_and_stats. All 384 tests passing (13 new), lint clean.

## Verification

- 384 tests pass (13 new instance-scoped tests in test_db.py)
- ruff lint clean across triggarr/ and tests/
- Existing tests unchanged and still passing — backward compat confirmed
- New tests cover: instance insertion, per-instance filtering on all query functions, per-instance stats isolation, migration column/index presence, composite PK structure, row_factory cleanup

## Requirements Advanced

- OBS-02 — DB schema now supports per-instance search history; instance_filter available on get_search_history
- OBS-03 — Per-instance stats now stored and queryable via get_dashboard_stats(instance_id=...)
- INST-01 — Per-instance DB scoping ready for Radarr multi-instance
- INST-02 — Per-instance DB scoping ready for Sonarr multi-instance

## Requirements Validated

- None newly validated (S05 provides infrastructure; S06/S07 complete the user-visible loop)

## New Requirements Surfaced

- None

## Requirements Invalidated or Re-scoped

- None

## Deviations

None — all three tasks executed as planned in a single commit.

## Known Limitations

- Web routes still don't pass instance_id to DB query functions — S07 will add instance filter dropdown
- Tracking groups by (app, item_id) without instance scoping — sufficient for now since item_ids are unique per *arr instance, but S06 may refine grouping
- migrate_from_state doesn't set instance_id (uses Default) — acceptable since state.json migration predates multi-instance

## Follow-ups

- S06: Scheduler wiring needs to pass instance_name context through to tracking
- S07: Web routes need instance_filter param on history endpoint, instance_id on dashboard stats
- S07: History page needs instance filter dropdown UI

## Files Created/Modified

- `triggarr/db.py` — Migrations v6/v7, instance_id on all CRUD functions
- `triggarr/search/engine.py` — instance_id=instance_name on all 8 insert_search_entry calls
- `triggarr/tracking.py` — instance_id passed to update_outcome_and_stats
- `tests/test_db.py` — 13 new instance-scoped tests

## Forward Intelligence

### What the next slice should know
- All DB functions now accept instance_id with 'Default' as the backward-compat default
- get_trackable_entries returns instance_id in each entry dict — tracking can use it
- update_outcome_and_stats auto-creates lifetime_stats rows via INSERT OR IGNORE — no need to pre-seed

### What's fragile
- lifetime_stats composite PK means callers MUST pass both app AND instance_id for correct stat routing — using just app would match nothing after the v7 migration

### Authoritative diagnostics
- test_db.py instance-scoped tests are the source of truth for per-instance behavior
- Migration v7 table-swap pattern is the authoritative pattern if future migrations need similar restructuring

### What assumptions changed
- None — the design worked as planned
