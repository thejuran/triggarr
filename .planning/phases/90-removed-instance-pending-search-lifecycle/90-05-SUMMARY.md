---
phase: 90-removed-instance-pending-search-lifecycle
plan: 05
subsystem: web
tags: [fastapi, sqlite, cancellation, log-safety, instance-removal]
requires: [90-02, 90-04]
provides:
  - Close-out of pending searches in remove_instance and in save_settings (form-omitted instances)
  - _replace_retired_db helper in triggarr/web/routes.py
affects: [90-06, 90-07, 90-08]
tech-stack:
  added: []
  patterns: [last in-lock step isolated by try/except, run-as-own-task-and-wait-through-shield for the connection swap, sanitized exception type only in log lines]
key-files:
  created: []
  modified: [triggarr/web/routes.py, tests/test_web.py]
key-decisions:
  - "Close-out is the last in-lock step in both routes (after the synchronous tidy-up in Remove, after state persistence in Save Settings)"
  - "Both new error lines log _sanitize_exc(exc) only, never exception text"
  - "A retired connection is swapped for a clean one inside search_lock before the lock is released"
requirements-completed: []
duration: 55min
completed: 2026-11-18
---

# Phase 90 Plan 05: Close-out wired into instance removal Summary

Removing an instance, through the Remove action or by leaving it out of Save Settings, now gives its pending searches the final "instance removed" outcome by stable ID in the same request, without ever failing the removal, skipping another tidy-up step, leaving the shared connection inside a transaction or retired, or writing exception text to a log.

## Commits
- 43777cc9 test(90-05): failing tests for close-out on instance removal (RED)
- 62b09a34 feat(90-05): close out pending searches when an instance is removed (GREEN)
- 61a72320 test(90-05): failing tests for close-out on Save Settings instance omission (RED)
- c31dd68f feat(90-05): close out pending searches for instances dropped by Save Settings (GREEN)

## What changed
- `remove_instance`: reads the stable ID from server-side settings in the lock, then after the synchronous tidy-up runs `close_out_removed_instance_searches(app=app_name.title(), instance_stable_id=..., instance_id=...)`. Empty ID: one WARNING, skipped (never by name). Cancellation is held in the existing `cancelled` variable; other errors log one ERROR with `_sanitize_exc`. `_replace_retired_db(request.app)` runs afterwards on every path, inside the lock.
- `save_settings`: after state persistence, every (app, name, stable ID) present in the old settings and absent (by ID) in the new ones is closed out, each in its own try/except, reading `app.state.db` anew per call, with the same retired-connection replacement. A held cancellation stops the loop, the stale clients are closed through `_close_removed_client`, and the cancellation is then re-raised.
- `_replace_retired_db(app)`: synchronous no-op when the connection is healthy; otherwise opens the replacement as its own task through a shield, assigns it to `app.state.db`, and on failure logs one sanitized ERROR and leaves the retired (fail-closed) connection in place.

## Test evidence (observed)
All route tests use the real database function except where a test patches it on purpose.

Task 1 RED (`uv run pytest tests/test_web.py -q -k "remove_instance and (close_out or pending_searches or stable_id)"`): 12 failed, 1 passed.
- `test_remove_instance_closes_out_pending_searches` x3 (radarr, sonarr, lidarr): RED, `assert 'searched' == 'instance_removed'` (rows stayed pending).
- `..._close_out_failure_still_succeeds`, `..._failure_log_leaks_nothing`, `..._cancelled_during_close_out_still_finishes_tidy_up`, `..._close_out_replacement_failure_still_succeeds`, `..._cancelled_close_out_with_retired_connection_replaces_it_before_reraising`, `..._without_stable_id_skips_close_out`, `..._close_out_runs_after_synchronous_tidy_up`: RED, `AttributeError: triggarr.web.routes does not have the attribute 'close_out_removed_instance_searches'` (the patch target did not exist yet).
- `..._cancelled_during_real_close_out_finishes_db_cleanup_before_releasing_lock`: RED, `TimeoutError` waiting for the UPDATE that unfixed code never issues.
- `..._close_out_with_unverifiable_rollback_replaces_the_connection`: RED, `assert None is True` (the armed commit was never reached, so the close-out never ran).
- `test_remove_instance_write_failure_leaves_pending_searches_pending`: PASS pin, passed before and after.
Task 1 GREEN: 13 passed; `-k remove_instance` 46 passed; lock-coverage test and `tests/audit_lock_coverage.py` (8/8 covered) green.

Task 2 RED (`-k "save_settings and (close_out or pending_searches)"`): 5 failed, 2 passed.
- `test_save_settings_form_removal_closes_out_pending_searches`: RED, `('searched', '') == ('instance_removed', ...)`.
- `..._close_out_failure_still_saves`: RED, `0 == 1` (no ERROR line).
- `test_save_settings_close_out_failure_log_leaks_nothing`: RED, `'RuntimeError' in ''` (no ERROR line on stderr).
- `..._cancelled_during_close_out_finishes_remaining_cleanup`: RED, `DID NOT RAISE CancelledError`.
- `..._close_out_with_unverifiable_rollback_replaces_the_connection`: RED, `assert None is True`.
- `test_save_settings_disabling_instance_keeps_pending_searches` and `test_save_settings_unchanged_instances_trigger_no_close_out`: PASS pins, passed before and after. Planned-class note: Task 1 had already added the route's import, so the "close-out not called" assertion held before the change too; `create=True` on the patch keeps them valid either way.
Task 2 GREEN: 7 passed; `-k "save_settings or remove_instance"` 80 passed.

Final gate: `uv run pytest tests/ -x -q` 3472 passed, 1 skipped; `uv run ruff check triggarr/ tests/` clean; `git diff --quiet main -- pyproject.toml uv.lock` exit 0. Acceptance greps: `close_out_removed_instance_searches` 3 occurrences, `closing out its pending searches failed: {exc}` 2, no `{exc_type}` variant, no "never selected" text, close-out after `save_state` in `save_settings`.

Not verified: no live Radarr/Sonarr/Lidarr or browser session; everything is exercised through the ASGI app with a real SQLite file and mocked arr clients. Mutation checks were not run for this plan.

## Log-capture pattern used for the Save Settings sentinel test
The route calls the real `setup_logging(...)`, which replaces all handlers, so a handler added by the test would be removed. The test patches `triggarr.logging.create_redacting_sink` with a wrapper that redirects the real stderr sink to a `StringIO` (so the route's own sinks, built from the post-removal secrets, are what is checked) and reads the viewer buffer from `triggarr.log_buffer.log_buffer`. Neither the removed key sentinel nor the URL-userinfo sentinel appears in either channel or in the response. The Remove-action variant installs real `create_redacting_sink` / `create_buffer_sink` sinks built from the post-removal secrets.

## Save Settings removal path
Found during planning (an instance missing from the form is removed by `save_settings`, pinned by `test_save_settings_form_removal_invalidates_tag_cache`) and covered by Task 2.

## Deviations from Plan

**1. [Rule 3 - Blocking] Pre-existing test adjusted for the new warning**
- **Found during:** Task 1 GREEN
- **Issue:** `test_remove_instance_refused_thread_start_with_write_already_running_reports_the_write` asserts exactly one WARNING record. The fixture's instances have no stable ID, so the mandated "no stable ID" warning is now also emitted and the count became 2.
- **Fix:** the test's warning list excludes the "no stable ID" line; the assertion about the write warning is otherwise unchanged. This is the only pre-existing test modified.
- **Cost if wrong:** test-only; a future change to that warning text would need the filter updated.
- **Commit:** 62b09a34

**2. [Rule 1 - Convention] Test section header without phase number**
- The plan asked for a section headed "(Phase 90)"; the project rule keeps GSD phase framing out of code, so the headers name the behavior only.
- **Cost if wrong:** none functional.
- **Commits:** 43777cc9, 61a72320

**3. Test placement:** the Save Settings tests sit next to the other Save Settings tests (before `test_search_now_refetches_...`) rather than directly after `test_save_settings_form_removal_invalidates_tag_cache`. No behavior effect.

## Known Stubs
None.

## Threat Flags
None. The new error lines carry only `_sanitize_exc` output (T-90-20).

## Notes for later plans
- Work that was already waiting on `search_lock` when a removal ran is plan 90-07's subject; this plan's comments make no claim about it.
- RMINST-01 behavior at removal time is delivered here, but it is left unchecked in REQUIREMENTS.md until 90-07 closes the queued-work race and the phase is verified.

## Self-Check: PASSED
Commits 43777cc9, 62b09a34, 61a72320, c31dd68f exist on the phase branch; `triggarr/web/routes.py` and `tests/test_web.py` modified as described.
