---
phase: 90-removed-instance-pending-search-lifecycle
reviewed: 2026-11-19T00:00:00Z
reviewed_commit: 22b993255c668ac880a043abdf0dcece26829f48
diff_base: 4b1f9f1bfbaa8f7d16fea6f0e7e6fb243d1a560d
depth: standard
files_reviewed: 2
files_reviewed_list:
  - triggarr/db.py
  - tests/test_db.py
findings:
  critical: 0
  warning: 0
  info: 1
  total: 1
status: issues_found
---

# Phase 90: Code Review Report (review after fix round 2)

**Reviewed commit:** 22b993255c668ac880a043abdf0dcece26829f48 (diff base 4b1f9f1b)
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found (Info only)

## Summary

Commit `22b99325` fixes IN-01 of `90-REVIEW-FIXES.md`. `_CLOSE_OUT_DETAIL_SQL` (`triggarr/db.py:1554-1563`) now keeps the existing detail and appends ` (instance removed)` only when the row's outcome is `'partial'` and its detail is neither NULL nor empty. Every other row closed out gets the plain `instance removed`. Both detail tests now include a row seeded the way the engine seeds it (`detail="search triggered"`, `engine.py:573`).

Each point the caller asked about was checked:

- **The right-hand side reads the values from before the update.** SQLite evaluates every SET expression against the row as it was before the UPDATE. So `outcome = 'partial'` inside the CASE sees the old outcome, not `instance_removed`, even though `outcome = ?` comes first in the SET list. I confirmed this with an in-memory SQLite run of the exact fragment, outside the repository. The partial row kept `partial: 2/5 episodes (instance removed)`. The test suite also confirms it: if the CASE read the new value, the partial row would get the plain note and both tests would fail.
- **NULL and empty values.**
  - A partial row whose detail is NULL or `''` gets the plain note. The guard prevents `NULL || ...` from producing NULL and prevents a bare ` (instance removed)`.
  - A row whose outcome is NULL (pending through `COALESCE(outcome, 'searched')` in `_PENDING_SQL`) does not match `outcome = 'partial'`, so it falls to ELSE and gets the plain note. That is correct.
  - The in-memory run covered all eight combinations: searched, partial and NULL outcomes, each with `''`, NULL and non-empty detail. Only `partial` with a non-empty detail kept its text.
- **Bound-parameter order.** The fragment still has two anonymous `?`. Their roles swapped: the THEN placeholder now comes first and the ELSE placeholder second. Both callers (`db.py:1592` and `db.py:1665`) bind `(OUTCOME_INSTANCE_REMOVED, INSTANCE_REMOVED_DETAIL, INSTANCE_REMOVED_DETAIL, now, app, stable_id)`. The count is still six and the two middle values are identical, so the swap has no effect. The fragment-fragility point from the earlier IN-02 still applies and is not raised again here.
- **Producers of pending detail.** Pending rows get their detail from only these places:
  - the engine's `"search triggered"` on `searched` rows;
  - the default `""` from `insert_search_entry`;
  - tracking, which writes `partial: N/M episodes` or `partial: N episodes` only together with outcome `partial` (`tracking.py:752-767`, `tracking.py:895-897`).

  No `searched` row carries a meaningful detail that the new rule would throw away.
- **Would the tests fail without the fix?** Yes. Under the previous fragment, the in-memory run turned the new `"search triggered"` row into `search triggered (instance removed)`. Both `test_close_out_instance_removed_keeps_existing_detail` and `test_orphan_sweep_keeps_existing_detail` expect `instance removed` in that position, so both fail on `4b1f9f1b`. I checked this by running the SQL expression on its own. I did not run reverted source, because a hook blocked that in the previous round.
- **Checks run.** `uv run pytest tests/test_db.py -x -q` gave 174 passed at `22b99325`, and the full suite (`uv run pytest tests/ -x -q`) gave 3520 passed and 1 skipped. `ruff check` on both files is clean. The conventions check (`verify conventions --check`) returned no findings.
- **Security.** The fragment is still a module constant with no input interpolated into it. All values are bound.

There is no blocker and no warning, and one Info note.

## Structural Findings (fallow)

No structural pre-pass was provided.

## Narrative Findings (AI reviewer)

## Info

### IN-01: No test pins the new guard for a partial row with NULL or empty detail

**File:** `triggarr/db.py:1561` (`detail IS NOT NULL AND detail != ''`); `tests/test_db.py:3544-3563`, `tests/test_db.py:4022-4043`
**Issue:** The new CASE has a branch that neither test reaches: an outcome `'partial'` row with NULL or `''` detail. In both tests the partial row has `partial: 2/5 episodes`. The NULL and empty rows in both tests are `searched`: in the close-out test, `_seed_pending` makes only `ids[1]` partial, and in the orphan test, `_add_row` defaults to `searched`. If a later edit dropped the `IS NOT NULL AND != ''` guard, every test would still pass. Production would then write a NULL detail (`NULL || ...` is NULL) or a bare ` (instance removed)` for such a row. Tracking always writes a detail when it sets `partial`, so such rows are rare today. Imported or hand-edited rows could still have this shape.
**Fix:** In one of the two tests, add a row with outcome `partial` and detail NULL, for example `_add_row(db, "Sonarr", "sid-gone", "partial-null", outcome="partial")` followed by `_set_detail(db, id, None)`. Expect `"instance removed"` for it.

## Set aside (needs ruling)

None. The earlier IN-02 (two anonymous positional `?` in the shared fragment) still applies to this code, and its disposition is the one already recorded. This pass did not raise it again.

---

_Reviewed: 2026-11-19_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
