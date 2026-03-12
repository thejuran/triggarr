# S05: Database Schema & Instance Scoping

**Goal:** All search history entries carry an `instance_id` column, all DB query/stat functions accept optional instance filtering, and existing data migrates cleanly with a default instance name.
**Demo:** Insert entries for two different instances, query by instance filter, verify stats are per-instance. All existing tests still pass with backward-compatible defaults.

## Must-Haves

- Migration v6: add `instance_id TEXT DEFAULT 'Default'` to `search_history` + index
- Migration v7: add `instance_id TEXT` to `lifetime_stats` (composite PK: app + instance_id), seed per-instance rows
- `insert_search_entry` accepts `instance_id` parameter
- `get_search_history` accepts optional `instance_filter` parameter
- `get_recent_searches` accepts optional `instance_id` parameter
- `get_trackable_entries` accepts optional `instance_id` parameter
- `get_dashboard_stats` accepts optional `instance_id` parameter for per-instance stats
- `update_outcome_and_stats` routes stat increments to correct app+instance row
- Engine cycle functions pass `instance_name` as `instance_id` to `insert_search_entry`
- Tracking passes `instance_id` through to DB queries
- All existing tests pass unchanged (defaults make instance_id transparent)

## Proof Level

- This slice proves: contract + integration
- Real runtime required: no
- Human/UAT required: no

## Verification

- `pytest tests/test_db.py -v` — all existing tests pass, plus new instance-scoped tests
- `pytest tests/test_search.py -v` — cycle functions pass instance_id through
- `pytest tests/test_tracking.py -v` — tracking uses instance_id
- `pytest -x -q` — full suite green
- `ruff check triggarr/ tests/` — lint clean

## Observability / Diagnostics

- Runtime signals: loguru logs during migration v6/v7 with row counts
- Inspection surfaces: `search_history.instance_id` column, `lifetime_stats` composite key
- Failure visibility: migration logs report backfill counts and errors
- Redaction constraints: none (no secrets in DB schema)

## Integration Closure

- Upstream surfaces consumed: `InstanceConfig` from S01, `instance_name` param in cycle functions from S02
- New wiring introduced in this slice: `instance_id` threaded from engine → db on insert, `instance_id` filter on all query functions
- What remains before the milestone is truly usable end-to-end: S06 (scheduler wiring), S07 (web UI instance filter dropdown, per-instance dashboard cards)

## Tasks

- [x] **T01: Schema migrations v6 and v7 — add instance_id to search_history and lifetime_stats** `est:25m`
  - Why: The DB has no concept of which instance produced a search entry or stat row. This is the foundation for all instance-scoped queries.
  - Files: `triggarr/db.py`, `tests/test_db.py`
  - Do:
    1. Add `_migrate_v6`: `ALTER TABLE search_history ADD COLUMN instance_id TEXT DEFAULT 'Default'`; create index `idx_search_history_instance_id` on `(instance_id, timestamp DESC)`
    2. Add `_migrate_v7`: Recreate `lifetime_stats` with composite key `(app, instance_id)` — copy existing rows with `instance_id='Default'`, drop old table, rename new. Seed any missing app+instance combos.
    3. Register both in `MIGRATIONS` dict
    4. Write tests: verify v6 adds column + index, verify v7 preserves existing stats with Default instance, verify new instance rows can be inserted
  - Verify: `pytest tests/test_db.py -k "migrate" -v` — all migration tests pass
  - Done when: Both migrations run cleanly on fresh and existing DBs, existing data preserved with instance_id='Default'

- [x] **T02: Thread instance_id through all DB CRUD functions** `est:25m`
  - Why: All insert/query/update functions need to accept and use instance_id for scoping.
  - Files: `triggarr/db.py`, `tests/test_db.py`
  - Do:
    1. `insert_search_entry`: add `instance_id: str = "Default"` param, include in INSERT
    2. `get_recent_searches`: add `instance_id: str | None = None` param, add WHERE clause when set
    3. `get_search_history`: add `instance_filter: list[str] | None = None` param (like app_filter pattern), include `instance_id` in returned entries
    4. `get_trackable_entries`: add `instance_id: str | None = None` param, add WHERE clause when set, include `instance_id` in returned dicts
    5. `update_outcome_and_stats`: add `instance_id: str = "Default"` param, use composite key `(app, instance_id)` for lifetime_stats UPDATE
    6. `get_dashboard_stats`: add `instance_id: str | None = None` param — when set, filter search_history and lifetime_stats by instance
    7. Write tests: insert entries for two instances, verify filtering returns only matching instance, verify stats are per-instance
  - Verify: `pytest tests/test_db.py -v` — all tests pass including new instance-scoped tests
  - Done when: Every DB function supports instance_id, all existing tests pass with defaults, new tests prove per-instance isolation

- [x] **T03: Wire instance_id from engine and tracking into DB calls** `est:15m`
  - Why: The cycle functions and tracking orchestrator need to pass instance_name through to DB inserts and queries so that production data is instance-scoped.
  - Files: `triggarr/search/engine.py`, `triggarr/tracking.py`, `tests/test_search.py`, `tests/test_tracking.py`
  - Do:
    1. In `run_radarr_cycle` and `run_sonarr_cycle`: pass `instance_id=instance_name` to every `insert_search_entry` call
    2. In `run_tracking_check`: pass `instance_id` through to `get_trackable_entries` and `update_outcome_and_stats` (trackable entries now include instance_id from the DB row)
    3. Update search tests to verify instance_id appears in DB entries after cycle runs
    4. Update tracking tests to verify instance_id flows through
  - Verify: `pytest tests/test_search.py tests/test_tracking.py -v` — all pass
  - Done when: Instance name flows from cycle function args into DB rows, tracking resolves against correct instance, full test suite green

## Files Likely Touched

- `triggarr/db.py`
- `triggarr/search/engine.py`
- `triggarr/tracking.py`
- `tests/test_db.py`
- `tests/test_search.py`
- `tests/test_tracking.py`
