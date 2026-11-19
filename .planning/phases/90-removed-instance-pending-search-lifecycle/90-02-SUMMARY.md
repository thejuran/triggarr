---
phase: 90-removed-instance-pending-search-lifecycle
plan: 02
subsystem: database
tags: [sqlite, aiosqlite, cancellation, rollback, close-out]
requires: [90-01]
provides:
  - close_out_removed_instance_searches, close_out_orphaned_pending_searches in triggarr/db.py
  - INSTANCE_REMOVED_DETAIL, is_connection_retired, replace_retired_connection, _retire_connection, _rollback_through_cancellation
affects: [90-05, 90-06, 90-08]
tech-stack:
  added: []
  patterns: [run-as-own-task-and-wait-through-shield for rollback and close, verified rollback with connection retirement]
key-files:
  created: []
  modified: [triggarr/db.py, tests/test_db.py]
key-decisions:
  - "Rows with no stable ID are closed by the sweep (they cannot belong to a configured instance)"
  - "No set-size guard: with zero configured instances every pending non-Legacy search is an orphan"
  - "Both close-outs end with the transaction verified finished or the connection retired and replaceable"
requirements-completed: [RMINST-01, RMINST-04]
duration: 45min
completed: 2026-11-18
---

# Phase 90 Plan 02: Close-out of pending searches by stable ID and orphan sweep Summary

Two database operations that are the only writers of `instance_removed`: a per-instance close-out keyed on (app, stable ID), and a startup sweep of orphans, both finishing their transaction (verified rollback, or a retired and replaceable connection) before any error or cancellation surfaces.

## Commits
- 6764a401 test(90-02): failing tests for removed-instance close-out and rollback retirement (RED)
- 2a2cf451 feat(90-02): close out a removed instance's pending searches with a verified rollback (GREEN)
- b0b42282 test(90-02): failing tests for the orphaned pending-search sweep (RED)
- 5199fa43 feat(90-02): sweep orphaned pending searches at startup (GREEN)

## Test evidence (observed)
- Task 1 RED (`uv run pytest tests/test_db.py -q -k close_out_instance_removed`): collection error, `ImportError: cannot import name '_retire_connection' from 'triggarr.db'`, so every new test was red. After the fix: 23 passed (first run had 2 test-side faults, fixed before commit: a wrong `update_outcome_and_stats` call, and a blocker SELECT that left a cursor open and so held a lock after the connection closed).
- Task 2 RED (`-k orphan_sweep`): collection error, `ImportError: cannot import name 'close_out_orphaned_pending_searches'`. After: 14 passed (one test expectation corrected: the unrelated row committed in that test is itself an orphan, so the replacement connection's sweep closes 3, not 2).
- Mutation 1 (handler narrowed to `except Exception` in the removal function): 3 failed, 20 passed (`..._cancelled_with_update_queued...`, `..._rollback_survives_a_second_cancellation`, `..._caller_cancel_unverifiable_rollback_retires_and_raises_cancelled`). Same narrowing in the sweep: `test_orphan_sweep_cancelled_between_group_updates_rolls_back_everything` failed (1 failed, 13 passed). Restored; green.
- Mutation 2 (single unverified rollback attempt, log and return): 7 failed, 16 passed (log-type-names, retry, cancelled-rollback-task, both persistent-failure cases, caller-cancel-unverifiable, replacement). Restored; green.
- Final gate: `uv run pytest tests/ -x -q` 3431 passed, 1 skipped; `uv run ruff check triggarr/ tests/` clean; `git diff --quiet main -- pyproject.toml uv.lock` exit 0; no non-comment `'searched', 'partial'` literal; no new `await db.rollback()` (rollbacks go through the helper).

## Decisions recorded
- **NULL-ID rows:** the sweep closes pending, non-Legacy rows with no stable ID (migration v10 associated every configured pair and writers always pass the ID; nobody selects such rows after plan 90-03 and pending rows are never pruned).
- **Zero configured instances:** no set-size guard. A missing, corrupt or invalid configuration stops the process in `ensure_config` before the lifespan exists, so the sweep only sees validated configuration. Stated consequence: starting Triggarr with a valid configuration that has no instances (for example a regenerated default file) next to an existing database closes the searches pending at that moment as "Instance removed". Stable IDs exist only in the configuration file, so hand re-added instances get new IDs and could never own those rows; only tracking of those pending searches is lost if the old file is restored later.
- **No migration:** it cannot see the cutover and would not repair a close-out that failed after a successful settings write.
- **Detail text:** fixed string `instance removed`, overwriting the previous detail.
- **grab_ownership and lifetime_stats:** untouched (pinned by test).
- **Transaction finalization:** both functions catch `BaseException`; rollback runs as its own task awaited through a shield loop (survives repeated cancellation), is verified (call completed, then `db.in_transaction` False), retried up to 3 times, else the connection is marked retired and closed. The caller's cancellation is re-raised after; a rollback error never replaces it.
- **Retirement and replacement:** `is_connection_retired(db)` after any failure; `replace_retired_connection(db)` opens a new connection on the path `init_db` recorded (same PRAGMAs, Row factory, no migration, no `app.state` change; the caller publishes it).
- **Cost of retirement:** needs three consecutive failed or cancelled rollbacks, i.e. the disk or process is already in trouble. Other work mid-flight on the retired connection fails instead of committing (intended fail-closed). If the close itself cannot finish, the worker thread may keep the write lock and the replacement fails writes with a lock error until restart (still fail-closed). Callers (90-05, 90-06) keep D-00b: the removal response stays successful and the startup sweep repairs an abandoned close-out.

## Observation: `update_outcome_and_stats`
It rolls back on `Exception` only and rolls back once without verification, so it shares the cancellation gap (a cancelled call can leave an applied write in an open transaction on the shared connection). Not changed in this phase.

## Deviations from Plan
**1. [Rule 3 - Blocking] Test helper fixes** (found during GREEN): the worker-blocking statement is `SELECT 1 WHERE triggarr_block() = 99` (finishes without rows) instead of a bare `SELECT triggarr_block()`, because the latter left an unfinished cursor that kept the file locked after the connection closed.
- Cost if wrong: test-only; a flaky "database is locked" in the retirement tests.
- Commit: 2a2cf451

**2. [Rule 1 - Bug, test] Sweep retirement test expected count** changed 2 to 3 (the unrelated row is an orphan too). Commit: 5199fa43. Cost if wrong: test-only.

## Known Stubs
None.

## Threat Flags
None.

## Self-Check: PASSED
