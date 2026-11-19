---
phase: 90-removed-instance-pending-search-lifecycle
plan: 01
subsystem: database
tags: [sqlite, search-history, pending-cap, grab-rate]
requires: []
provides:
  - PENDING_OUTCOMES, OUTCOME_INSTANCE_REMOVED, _PENDING_SQL, _NOT_PENDING_SQL in triggarr/db.py
  - instance_removed as a finished, uncounted outcome
affects: [90-02, 90-03, 90-04, 90-05, 90-06, 90-07, 90-08]
tech-stack:
  added: []
  patterns: [single shared SQL fragment built from a module constant tuple]
key-files:
  created: []
  modified: [triggarr/db.py, tests/test_db.py]
key-decisions:
  - "NULL outcome counts as pending everywhere (cap in both modes, trackable, never pruned)"
  - "instance_removed is excluded from the grab rate and the historical rate flag with an explicit AND outcome != exclusion"
requirements-completed: [RMINST-02]
duration: 25min
completed: 2026-11-18
---

# Phase 90 Plan 01: Shared pending rule and finished instance_removed outcome Summary

One definition of "pending" in `triggarr/db.py` (`PENDING_OUTCOMES` plus `_PENDING_SQL` / `_NOT_PENDING_SQL`), NULL counted as pending, and `instance_removed` as a finished outcome that is out of the cap, tracking, grab rate and historical flag.

## Commits
- ba88e13c test(90-01): failing tests for shared pending rule and NULL handling (RED)
- c9d2fdfe feat(90-01): one shared pending-outcome rule with NULL counted as pending (GREEN)
- 410c64fa test(90-01): tests for the instance_removed outcome (RED)
- f4f45b19 feat(90-01): exclude instance_removed from grab rate and historical flag (GREEN)

## NULL-handling decision
NULL is pending. This matches the existing prune predicate (`COALESCE(outcome, 'searched')`), the legacy rule and the display layer's `outcome or 'searched'`. Before, NULL rows were never pruned yet never capped or tracked; now they are capped and tracked consistently.

## Test evidence (observed)
Task 1 RED run (`uv run pytest tests/test_db.py -q -k pending_predicate`): 4 failed, 1 passed.
- test_pending_predicate_constants: RED, failed (ImportError) -> passes
- test_pending_predicate_null_outcome_counts_toward_cap: RED, failed (no PendingCapExceeded) -> passes
- test_pending_predicate_null_outcome_counts_toward_cap_name_mode: RED, failed -> passes
- test_pending_predicate_null_outcome_is_trackable: RED, failed (row absent) -> passes
- test_pending_predicate_null_outcome_never_pruned: PIN, passed before and after
Post-fix: 5 passed; `tests/test_db.py tests/test_tracking.py` 171 passed.

Task 2 RED run (`-k instance_removed`): 3 failed, 5 passed (an earlier run failed all 8 only from a missing import, fixed before the commit).
- test_instance_removed_rows_left_out_of_grab_rate: RED, `assert 25.0 == 100.0` -> passes
- test_instance_removed_only_rows_give_no_grab_rate: RED, `assert 0.0 is None` -> passes
- test_instance_removed_row_does_not_set_historical_rate_flag: RED, `assert True is False` -> passes
- test_instance_removed_rows_do_not_count_toward_pending_cap, _are_not_trackable, _age_out_with_finished_rows, _row_is_never_legacy, _outcome_filter_returns_only_those_rows: PINs, passed before and after.

Final gate: `uv run pytest tests/ -x -q` 3394 passed, 1 skipped; `uv run ruff check triggarr/ tests/` clean; `git diff --quiet main -- pyproject.toml uv.lock` exit 0. `grep -c OUTCOME_INSTANCE_REMOVED triggarr/db.py` = 4; no literal `'searched', 'partial'` remains in non-comment code.

## Deviations from Plan
None in behavior. Minor: the pre-commit ruff import sort moved the new test imports to top-level imports (`OUTCOME_INSTANCE_REMOVED` added to the existing import block); constants test imports the private SQL fragments inside the test body.
Cost if wrong: none; test-only.

## Known Stubs
None.

## Self-Check: PASSED
