---
phase: 88-bounded-upgrade-backups-telemetry-regression
plan: 01
subsystem: database
tags: [sqlite, migrations, backup-retention, loguru, pathlib]

# Dependency graph
requires: []
provides:
  - "_prune_timestamped_backups helper in triggarr/db.py capping timestamped pre-upgrade backups at the 3 most recent per schema version"
  - "run_migrations call site that prunes right after each timestamped backup is written"
  - "9 regression tests proving the bound, the ordering rule, and the failure-never-blocks behavior"
affects: [92-built-image-recovery-demonstration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Keep-newest-N-by-filename-stamp retention, scoped to one version's exact naming pattern, enumerated via iterdir + startswith + regex fullmatch (never glob alone, never mtime)"
    - "Narrow except OSError + logger.warning + continue/return, matching triggarr/state.py::_recover_from_bad_state_file's shape, so a filesystem cleanup failure never blocks the caller"

key-files:
  created: []
  modified:
    - triggarr/db.py
    - tests/test_db.py

key-decisions:
  - "Followed CONTEXT.md D-01..D-09 exactly: no new dependency; canonical backup and just-written backup are structurally excluded from the candidate set (name has no '-stamp' suffix / explicit identity check), never a filter that could be bypassed"
  - "Task 1's GREEN deliberately ships without try/except around iterdir/unlink, so Task 2's RED tests can prove the pre-fix failure mode before the warning-and-continue handling is added"

patterns-established:
  - "Pattern 1 (BKUP-01/02): scoped, pattern-strict filename pruning -- this is now the reference implementation for retention-by-filename-stamp in this codebase, usable as the analog for the next similar need"

requirements-completed: [BKUP-01, BKUP-02]

# Metrics
duration: 14min
completed: 2026-11-16
---

# Phase 88 Plan 01: Bounded Upgrade Backups Summary

**Pre-upgrade retry backups now cap at the canonical copy plus the 3 most recent timestamped copies, ordered by the filename's embedded timestamp, with a pruning failure logged as a warning and never blocking startup.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-11-16T21:35:33-05:00 (approx, from STATE.md session start)
- **Completed:** 2026-11-16T21:49:05-05:00
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments
- `_prune_timestamped_backups(db_path, current, just_written)` added to `triggarr/db.py`, called from `run_migrations`' timestamped-backup branch right after the new backup is written and logged.
- Retention ordering is decided by the `%Y%m%dT%H%M%S%fZ` stamp embedded in the filename (lexicographic sort on a fixed-width string), never by file mtime -- `shutil.copy2` preserves the source database's mtime, not the backup's own creation time.
- The canonical `.v{current}-backup` and the backup just written by the current call are structurally excluded from the candidate set; other schema versions and any name that doesn't exactly match the timestamped pattern (including a directory with a backup-shaped name) are never touched.
- A failure while listing the directory, or while deleting any individual stale file, is caught narrowly (`except OSError`), logged once at WARNING (never ERROR, never a traceback), and never stops the remaining deletions or the migration attempt -- even when the very first deletion attempted is the one that fails.
- 9 new regression tests in `tests/test_db.py`, each observed failing against the unfixed code before the corresponding fix landed (D-01 RED evidence recorded below).

## Task Commits

Each task was committed as a RED/GREEN pair (TDD):

1. **Task 1: Cap timestamped retry backups per schema version, ordered by filename stamp**
   - `07f50a76` test(88-01): add failing tests for bounded upgrade backups
   - `4f646134` feat(88-01): cap timestamped upgrade backups at the 3 most recent
2. **Task 2: A pruning failure is logged as a warning and never blocks the migration**
   - `4150c8b5` test(88-01): add failing tests for pruning failure handling
   - `5519addc` feat(88-01): log pruning failures as warnings without blocking startup

No REFACTOR commits -- `uv run ruff check` was clean after each GREEN step, no cleanup needed.

**Plan metadata:** (this commit, docs(88-01): complete plan)

## Files Created/Modified
- `triggarr/db.py` -- `_BACKUP_STAMP_RE`/`_MAX_RETAINED_TIMESTAMPED_BACKUPS` constants, `_prune_timestamped_backups` helper, call site in `run_migrations`' timestamped branch, updated backup-block comment.
- `tests/test_db.py` -- 9 new tests; `MIGRATIONS`, `run_migrations` added to the top-level `from triggarr.db import (...)` block; `os` and `shutil` added to imports.

## Observed RED Evidence (D-01)

All outcomes below are copied verbatim (type + message) from the actual `uv run pytest -q -rA <node-id...>` runs, executed without `-x`, before the corresponding GREEN commit. Nothing here is inferred.

### Task 1 RED run (6 tests, before `4f646134`)

Command: `uv run pytest -q -rA "tests/test_db.py::test_backup_bound_holds_through_repeated_failed_attempts" "tests/test_db.py::test_backup_crash_loop_then_success_keeps_four_files" "tests/test_db.py::test_prune_orders_by_filename_stamp_not_mtime" "tests/test_db.py::test_prune_never_deletes_just_written_even_if_clock_went_back" "tests/test_db.py::test_prune_ignores_other_versions_and_non_matching_names" "tests/test_db.py::test_prune_logs_one_info_line_per_deleted_backup"` -> `6 failed in 0.76s`

| Test | Observed result |
|------|------------------|
| `test_backup_bound_holds_through_repeated_failed_attempts` | FAILED -- `AssertionError: Never more than 3 timestamped v9 backups after one attempt; got {...}` / `assert 4 <= 3` |
| `test_backup_crash_loop_then_success_keeps_four_files` | FAILED -- `AssertionError: Expected exactly 4 v9 backup files, got [...]` / `assert 6 == 4` |
| `test_prune_orders_by_filename_stamp_not_mtime` | FAILED -- `ImportError: cannot import name '_prune_timestamped_backups' from 'triggarr.db'` |
| `test_prune_never_deletes_just_written_even_if_clock_went_back` | FAILED -- `ImportError: cannot import name '_prune_timestamped_backups' from 'triggarr.db'` |
| `test_prune_ignores_other_versions_and_non_matching_names` | FAILED -- `ImportError: cannot import name '_prune_timestamped_backups' from 'triggarr.db'` |
| `test_prune_logs_one_info_line_per_deleted_backup` | FAILED -- `ImportError: cannot import name '_prune_timestamped_backups' from 'triggarr.db'` |

Also confirmed per the plan: `uv run pytest tests/test_db.py -q` on the unfixed code -> `6 failed, 107 passed` (module collects cleanly; pre-existing tests unaffected).

### Task 2 RED run (3 tests, before `5519addc`)

Command: `uv run pytest -q -rA "tests/test_db.py::test_prune_unlink_failure_logs_warning_and_continues" "tests/test_db.py::test_prune_listing_failure_logs_warning" "tests/test_db.py::test_run_migrations_proceeds_when_pruning_fails"` -> `3 failed in 0.13s`

| Test | Observed result |
|------|------------------|
| `test_prune_unlink_failure_logs_warning_and_continues` | FAILED -- `PermissionError: [Errno 13] Permission denied` (propagated out of `_prune_timestamped_backups`, uncaught) |
| `test_prune_listing_failure_logs_warning` | FAILED -- `OSError: [Errno 5] Input/output error` (propagated out of `_prune_timestamped_backups`, uncaught) |
| `test_run_migrations_proceeds_when_pruning_fails` | FAILED -- `PermissionError: [Errno 13] Permission denied` (propagated out of `run_migrations` via `_prune_timestamped_backups`, uncaught) |

## Decisions Made
- No new dependency added; pruning uses only the already-imported `re`/`pathlib`/`shutil`/`loguru` (D-01).
- Followed the exact log-line shape from `triggarr/state.py::_recover_from_bad_state_file` (`except OSError as exc: logger.warning(..., exc=f"{type(exc).__name__}: {exc}")`) for both of Task 2's warning sites, rather than inventing a new convention.

## Deviations from Plan

None - plan executed exactly as written. Both tasks followed their RED -> GREEN action text directly; no auto-fixes, no architectural questions, no scope changes.

## Issues Encountered
- The first attempt to run Task 2's three RED tests together as a single background command appeared to hang past a 120s timeout with no output written. Re-running the same three node IDs in a fresh foreground invocation completed in 0.13s with the expected three failures; the stray background process was killed. Treated as an isolated harness/background-task glitch, not a defect in the tests or the code -- confirmed by three separate successful runs (two individually, one together) immediately after.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- BKUP-01 and BKUP-02 are both proven by test and merged into `run_migrations`; Phase 92's built-image smoke test can now exercise a real repeated-failed-upgrade scenario against this bounded behavior.
- Plan 88-02 (telemetry regression, Wave 2) can proceed; this plan made no changes outside `triggarr/db.py` and `tests/test_db.py`, so there is no shared-state concern for the next plan.
- `.planning/STATE.md` carries an uncommitted orchestrator `stopped_at` edit and `.planning/config.json` carries an unrelated `model_overrides` edit from outside this plan's scope; both are left for the state-update step / orchestrator to handle, not folded into this plan's task commits.

---
*Phase: 88-bounded-upgrade-backups-telemetry-regression*
*Completed: 2026-11-16*

## Self-Check: PASSED

- FOUND: triggarr/db.py
- FOUND: tests/test_db.py
- FOUND: .planning/phases/88-bounded-upgrade-backups-telemetry-regression/88-01-SUMMARY.md
- FOUND commit: 07f50a76
- FOUND commit: 4f646134
- FOUND commit: 4150c8b5
- FOUND commit: 5519addc
