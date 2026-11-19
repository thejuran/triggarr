---
phase: 90-removed-instance-pending-search-lifecycle
plan: 06
subsystem: scheduler
tags: [lifespan, startup, sqlite, orphan-sweep]
requires: [90-02, 90-05]
provides:
  - Startup orphan sweep in create_lifespan (after the attribution cutover, before clients and scheduler)
affects: [90-07, 90-08]
tech-stack:
  added: []
  patterns: [non-fatal repair step with retired-connection replacement before the connection is published]
key-files:
  created: []
  modified: [triggarr/search/scheduler.py, tests/test_scheduler.py, tests/test_config_dir.py]
key-decisions:
  - "Sweep failure is logged (sanitized) and startup continues; only Exception is caught"
  - "A retired connection is replaced inside the failure handler, before app.state.db is set; a failed replacement is not caught"
  - "Zero configured instances: the sweep still runs"
requirements-completed: []
duration: 35min
completed: 2026-11-18
---

# Phase 90 Plan 06: Startup orphan sweep Summary

Every start now closes, as "Instance removed", the pending searches that no configured instance (enabled or disabled) owns, directly after the attribution cutover is recorded and before any client is built or the scheduler starts, sparing configured and Legacy rows.

## Commits
- 8afe2600 test(90-06): failing tests for the startup orphan sweep (RED)
- 7b6a1255 feat(90-06): close out orphaned pending searches at startup (GREEN)

## Decisions recorded
- **Failure policy (A2): logged, startup continues.** The sweep is repair; safety does not depend on it (rows are selected only under their own stable ID, plan 90-03; queued work for a removed instance is turned away in the lock, plan 90-07) and the next start repeats it. Unlike `ensure_cutover_recorded`, which stays uncaught. One ERROR line with `_sanitize_exc` output only. `CancelledError` is not caught and reaches the failed-startup cleanup.
- **Retired connection:** inside the failure handler, `if is_connection_retired(db): db = await replace_retired_connection(db)`, before client construction and `app.state.db = db`. A replacement error is deliberately uncaught, so startup stops through the existing cleanup.
- **Zero-instance decision:** the sweep runs with an empty configured set. A missing, corrupt or invalid configuration exits in `ensure_config` before the lifespan exists, so the sweep only sees validated configuration. **Consequence:** a start with a valid configuration that has no instances (for example a regenerated default file) next to an existing database closes the searches pending at that moment as "Instance removed". Stable IDs live only in the configuration file, so instances re-added by hand could never own those rows again. Legacy rows are preserved.
- **Evidence for the upstream exits (existing tests in tests/test_config.py, no new test needed):** missing file `test_ensure_config_exits_on_missing`; corrupt file `test_ensure_config_logs_friendly_error_on_toml_syntax_error` (also `..._on_invalid_utf8`); invalid configuration `test_ensure_config_exits_cleanly_on_invalid_url` (also `..._on_blocked_metadata_url`). All pass.

## Test evidence (observed)
RED run (`uv run pytest tests/test_scheduler.py -q -k sweep`): 11 failed. All planned RED:
- `test_lifespan_sweep_runs_after_cutover_and_before_scheduler_start`: order was `[init_db, ensure_cutover_recorded, scheduler.start]`, sweep never called.
- `..._closes_orphans_and_spares_configured_disabled_and_legacy`, `..._with_zero_instances_closes_pre_release_orphans_and_keeps_legacy`, `..._repairs_failed_close_out_of_last_instance[sonarr|radarr|lidarr]`: rows stayed `searched` instead of `instance_removed`.
- `..._is_idempotent_across_restarts`: orphan stayed `searched`.
- `..._failure_does_not_stop_startup`: no sweep ERROR line (0 != 1).
- `..._cancellation_reaches_startup_cleanup`: lifespan did not raise CancelledError.
- `..._failure_with_retired_connection_starts_on_a_replacement` and `..._failure_with_unreplaceable_connection_stops_startup`: sweep never called, so no failure/OSError observed.
GREEN: `-k sweep` 11 passed; `-k startup_failure` 10 passed (Phase 89 tests unmodified). Final: `uv run pytest tests/ -x -q` 3483 passed, 1 skipped; `uv run ruff check triggarr/ tests/` clean; `git diff --quiet main -- pyproject.toml uv.lock` exit 0. Acceptance awk ordering checks pass (call before replacement before `app.state.db = db`; call between cutover and client construction); no zero-instance guard at the call site; `close_out_orphaned_pending_searches` appears twice in non-comment lines.
Unreplaceable-connection test: the captured failed-startup output carries only the exception type name (`Startup failed (OSError); closing what was opened`), the `s3cret` text appears nowhere.
Not verified: no live arr instances or running container; everything runs through the real lifespan with a real SQLite file and a fake scheduler. No mutation checks.

## Deviations from Plan

**1. [Rule 3 - Blocking] Existing tests adjusted for the sweep**
- `test_lifespan_cutover_after_init_db` (plan-mandated) and `tests/test_config_dir.py::test_lifespan_derives_sqlite_path_from_injected_state_path` mock the database, so each also patches the sweep (assertions unchanged).
- Cost if wrong: test-only.

**2. [Rule 1 - Behavior change in existing tests] Legacy-import tests**
- Found during: GREEN full run. `test_lifespan_imported_rows_keep_outcomes_and_stay_unassociated` and `test_lifespan_imported_legacy_rows_stay_out_of_grab_rate_denominators` import a Radarr row with no stable ID while no Radarr instance is configured. By D-11 and the NULL-ID decision the sweep correctly closes it, so the Radarr row is now `instance_removed`, `radarr_rate`/`overall_rate` are None and the later overall rate is 50.0. Legacy Sonarr assertions unchanged.
- Cost if wrong: if the owner wants imported NULL-ID rows kept, the sweep's NULL-ID rule (plan 90-02) would change and these two tests revert.
- Commit: 7b6a1255

**3. [Rule 1 - Lint] RED commit carried one ruff finding** (nested `with` in a test helper); fixed in the GREEN commit.

## Known Stubs
None.

## Threat Flags
None.

## Self-Check: PASSED
Commits 8afe2600 and 7b6a1255 exist; triggarr/search/scheduler.py, tests/test_scheduler.py, tests/test_config_dir.py modified as described.
