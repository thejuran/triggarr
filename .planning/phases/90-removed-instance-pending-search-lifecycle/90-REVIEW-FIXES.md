---
phase: 90-removed-instance-pending-search-lifecycle
reviewed: 2026-11-19T23:19:08Z
reviewed_commit: 4b1f9f1bfbaa8f7d16fea6f0e7e6fb243d1a560d
diff_base: 669280d4d7be5a20ec303b47bba2907562d5ed20
depth: standard
files_reviewed: 2
files_reviewed_list:
  - triggarr/db.py
  - tests/test_db.py
findings:
  critical: 0
  warning: 0
  info: 2
  total: 2
status: issues_found
---

# Phase 90: Code Review Report (review after fixes)

**Reviewed:** 2026-11-19T23:19:08Z
**Reviewed commit:** 4b1f9f1bfbaa8f7d16fea6f0e7e6fb243d1a560d (diff base 669280d4)
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found (Info only)

## Summary

This pass covers the fix-round changes to `triggarr/db.py` and `tests/test_db.py` from `669280d4` to `4b1f9f1b`:

- `1a9039bd`: `get_trackable_entries` now passes a NULL outcome to tracking as `'searched'`.
- `3aa2cad6`: both close-out UPDATEs keep an existing `detail` and append ` (instance removed)`.
- `1744f43a`: the orphan sweep logs one INFO line per app, with counts, before it writes.
- `3e778629`: the sweep docstring now states decision A1.

I also checked the code these changes touch: the `_determine_outcome` and `update_outcome_and_stats` callers in `tracking.py`, the scheduler's sweep call site (`scheduler.py:802-822`), the v-migration detail parser (`db.py:497-535`), and the History tooltip (`history_results.html:144`).

Each fix is checked against what the caller asked for:

- **Correct.**
  - The NULL-outcome fix matches the `COALESCE(outcome, 'searched')` used by `_PENDING_SQL`. An empty-string outcome is not selected by the SQL, so `or "searched"` cannot turn a non-pending row into a pending one. `update_outcome_and_stats` updates by `id` only, so tracking can write back to a row that was NULL.
  - The detail CASE runs only on pending rows, so a row cannot get the note twice. The only code that parses detail text (`db.py:528`) reads only `grabbed`/`partial_expired` rows and matches a prefix, so the appended suffix does not affect it.
- **Transaction, rollback and cancellation behavior unchanged.** The added per-app log calls are synchronous and sit inside the existing `try`. No new await point comes before the commit except the existing statements. The `except BaseException` → `_rollback_through_cancellation` → re-raise path is unchanged.
- **Bound parameters only.** `_CLOSE_OUT_DETAIL_SQL` is a module constant with no user input. The note text, app, stable ID and timestamp are all bound with `?`.
- **No sensitive data logged.** The per-app lines contain only the app label (`Radarr`/`Sonarr`/`Lidarr`) and an integer count. No display name, URL or key appears.
- **Test coverage.** Each behavior fix has a test that fails on the unfixed code:
  - The NULL test now asserts `outcome == "searched"`; unfixed code returns `None`.
  - Both detail tests assert `"partial: 2/5 episodes (instance removed)"`; unfixed code wrote `"instance removed"`. The `""` branch (the default from `insert_search_entry`) and the NULL branch are each covered.
  - The per-app log test asserts the exact lines and that they come before the first `Orphan sweep: closed` debug line. It fails if the lines are missing or come after a write. It also checks that a second sweep with nothing to close logs nothing.
  - The docstring change needs no test.
- **Checks run.** `tests/test_db.py` gave 174 passed at `4b1f9f1b`, and `ruff check` on both files is clean. I also tried to confirm each test fails on the unfixed code by running the tests against reverted copies in the scratchpad. A PreToolUse hook (`holdout_guard.py`, "sealed holdout folder (v2.12 barrier)") blocked that, and I did not retry. Whether each test fails without its fix was checked by reading the code, not by running it.

No blocker or warning was found. There are two Info notes.

## Structural Findings (fallow)

No structural pre-pass was provided.

## Narrative Findings (AI reviewer)

## Info

### IN-01: The common production case of the detail fix is untested. Real `searched` rows become "search triggered (instance removed)"

**File:** `triggarr/db.py:1554-1557` (`_CLOSE_OUT_DETAIL_SQL`); `tests/test_db.py` (`test_close_out_instance_removed_keeps_existing_detail`, `test_orphan_sweep_keeps_existing_detail`); producer at `triggarr/search/engine.py:571-573`
**Issue:** Every search the engine records is inserted with `outcome="searched", detail="search triggered"` (`engine.py:573`). The new CASE keeps any non-empty detail, so most real rows that are closed out end with the History hover text `search triggered (instance removed)`. The plain `instance removed` that the comment and test docstrings describe ("empty or NULL detail gets the plain note") applies only to test-seeded rows (`insert_search_entry`'s default `""`) and to item-less imported rows. The result is readable and nothing parses it (`grep` finds no consumer of `"search triggered"`), so this is not a defect. But the tests only seed `""`, `NULL` and `partial: 2/5 episodes`. The text most users will actually see is not pinned by any test, and the comment suggests something different.
**Fix:** Choose one of these and pin it with a test row seeded as the engine seeds it (`detail="search triggered"`):
- Keep the current text, add that row to both detail tests with the expected `"search triggered (instance removed)"`, and reword the comment to "any existing detail is kept and the note is appended".
- Or treat the engine's placeholder as having no progress, so the row gets the plain note: `CASE WHEN detail IS NULL OR detail IN ('', 'search triggered') THEN ? ELSE ... END`.

### IN-02: The detail SQL fragment relies on parameter position and binds the same value twice

**File:** `triggarr/db.py:1556-1557`, `1587`, `1660`
**Issue:** `_CLOSE_OUT_DETAIL_SQL` contains two anonymous `?` placeholders. Each caller must pass `INSTANCE_REMOVED_DETAIL` twice, in the right position, between `outcome` and `resolved_at`. Only the comment "Takes two bound parameters" records this. If someone edits the fragment later (for example, to add a third branch) without updating both parameter tuples, the bindings shift silently. The timestamp could then be written into `detail`, or the call could fail with a binding-count error at removal time, which D-00b would then log and swallow. Both current call sites are correct.
**Fix:** Use a single bound value with SQLite numbered parameters so the fragment takes one binding, for example `detail = CASE WHEN detail IS NULL OR detail = '' THEN ?2 ELSE detail || ' (' || ?2 || ')' END` with `outcome = ?1`, `resolved_at = ?3`. Alternatively, switch both statements to named parameters (`:note`) with a dict.

## Set aside (needs ruling)

None. The owner rulings recorded in the `90-REVIEW.md` Dispositions section (SA-01 D-06 stands, SA-02 dismissed, A1 kept, IN-01/IN-02/IN-03 of the first review accepted or deferred) are decisions, not defects. This pass did not raise them again.

---

_Reviewed: 2026-11-19T23:19:08Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
