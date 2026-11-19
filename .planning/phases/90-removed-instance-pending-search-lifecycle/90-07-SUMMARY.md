---
phase: 90-removed-instance-pending-search-lifecycle
plan: 07
subsystem: scheduler
tags: [search-lock, race, revalidation, removal]
requires: [90-06]
provides:
  - "_revalidate_queued_instance: in-lock identity check used by the scheduled job and the manual search"
affects: [90-08]
tech-stack:
  added: []
  patterns: [re-validate values read before a lock, inside the lock, by identity]
key-files:
  created: []
  modified: [triggarr/search/scheduler.py, triggarr/web/routes.py, tests/test_scheduler.py, tests/test_web.py]
key-decisions:
  - "Rule: enabled under the same name, same stable ID (equality), live client is the captured client (is)"
  - "Live configuration read inside the lock is what the cycle and tracking then use"
  - "Same-ID client replacement turns queued work away for that one run"
  - "A turned-away manual search answers the existing 400 'Instance not enabled'"
requirements-completed: []
duration: 40min
completed: 2026-11-18
---

# Phase 90 Plan 07: In-lock revalidation of queued search work Summary

A scheduled job or manual search that was already waiting on `search_lock` when its instance was removed (Remove action or Save Settings omission) or replaced under the same name now does nothing once it gets the lock: no cycle, no client call, no new pending row, no tracking, no credit, no rate-limiter stamp.

## Commits
- 5002967b test(90-07): failing tests for scheduled work queued behind a removal (RED)
- 0c865f50 feat(90-07): turn away scheduled work queued behind a removal (GREEN, task 1)
- 4c71d11a test(90-07): failing tests for a manual search queued behind a removal (RED)
- 0af108be feat(90-07): turn away a manual search queued behind a removal (GREEN, task 2)

## Decisions recorded
- **Rule:** inside the lock the instance must still be enabled under that name, its `id` must equal the stable ID captured before waiting (equality, not non-empty, because fixtures hold empty IDs), and `app.state.<app>_clients[name]` must be the captured client object (`is`).
- **Live configuration:** the check returns the config read inside the lock; `job()` and `search_now` rebind `instance_config` to it before the tag resolver, cycle and tracking.
- **Same-ID client replacement:** queued work is turned away for that run (the old client is closed anyway); the job runs again at its interval, a manual search can be clicked again.
- **Turned-away manual search:** `HTMLResponse("Instance not enabled", status_code=400)`, checked before the rate-limit re-check and stamp. One INFO line each in the job and the route, carrying app and display name only.
- **Observed, left unchanged:** `refresh_counts` reads its client before the lock the same way but records no search and credits nothing.
- **Comments:** the close-out comment blocks in `remove_instance` and `save_settings` now state what protects against queued work. `grep -rniE "never selected|nobody selects|selected by nobody" triggarr/` prints nothing (there was no such claim left in `triggarr/`).

## Test evidence (observed)
Unit tests (tests/test_scheduler.py): RED = collection error (`_revalidate_queued_instance` does not exist), so all 7 were unrunnable; GREEN 7 passed (`unchanged_instance_and_returns_live_config`, and `rejects_stale_work` x6: removed, disabled, same_name_new_stable_id, same_stable_id_replaced_client, same_name_new_id_and_new_client, client_missing).

Barrier tests (tests/test_web.py), pre-fix result then post-fix result:
- `test_queued_scheduled_job_does_nothing_after_instance_removed[remove_action]` RED (extra `searched` row for sid-4k inserted by the stale job, i.e. stale dispatch observed) -> PASS
- `...[save_settings_omission]` RED (same) -> PASS
- `test_queued_scheduled_job_is_not_revived_by_same_name_recreation` RED (cycle stub called with the old client and `sid-4k`) -> PASS
- `test_queued_scheduled_job_still_runs_for_unchanged_instance` PASS pin: passed before and after
- `test_queued_manual_search_does_nothing_after_instance_removed[remove_action]` and `[save_settings_omission]` RED: the stale search ran and then the card render for the removed instance raised `AssertionError: Must not be empty` (empty instance name in `url_for`), so the request raised instead of answering 400. Observed difference from the planned failure (planned: a `searched` row exists); the stale dispatch is the cause either way. -> PASS
- `test_queued_manual_search_is_not_revived_by_same_name_recreation` RED (stale search ran, 200 instead of 400) -> PASS
- `test_queued_manual_search_still_runs_for_unchanged_instance` PASS pin: passed before and after

All RED runs finished on their own (no timeouts). GREEN: `-k revalidate_queued_instance` 7 passed; `-k "queued and scheduled_job"` 4 passed; `-k queued` 8 passed; `-k search_now` 9 passed; `tests/test_audit_lock_coverage.py` 1 passed; `uv run python tests/audit_lock_coverage.py` covered 8/8; `uv run pytest tests/ -x -q` 3498 passed, 1 skipped; `uv run ruff check triggarr/ tests/` clean; `git diff --quiet main -- pyproject.toml uv.lock` exit 0; awk ordering checks (job: check before cycle before tracking; route: check before the rate-limit stamp) exit 0.
Not verified: no live arr instance or running container; no mutation checks.

## Deviations from Plan
None of substance. The real writer is imported inside the barrier helper (`from triggarr.config import _atomic_toml_write as real_atomic_write`); the module also imports it at top level, which the existing tests use. Cost if wrong: none (test-only).

## Known Stubs
None.

## Threat Flags
None.

## Self-Check: PASSED
Commits 5002967b, 0c865f50, 4c71d11a, 0af108be exist; the four modified files exist.
