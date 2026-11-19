---
phase: 90-removed-instance-pending-search-lifecycle
reviewed: 2026-11-18T00:00:00Z
reviewed_commit: 096928a7a56fa66fa97fd07650883d39ca27c0ac
diff_base: 4c9abdaed29ddf7c2d5861f7e324947cb78b2ddd
depth: standard
files_reviewed: 13
files_reviewed_list:
  - triggarr/db.py
  - triggarr/search/scheduler.py
  - triggarr/tracking.py
  - triggarr/web/routes.py
  - triggarr/templates/partials/activity_rail.html
  - triggarr/templates/partials/history_results.html
  - tests/test_attribution_disclosure.py
  - tests/test_config_dir.py
  - tests/test_db.py
  - tests/test_removed_instance_lifecycle.py
  - tests/test_scheduler.py
  - tests/test_tracking.py
  - tests/test_web.py
findings:
  critical: 0
  warning: 1
  info: 4
  total: 5
status: issues_found
---

# Phase 90: Code Review Report

**Reviewed:** 2026-11-18
**Reviewed commit:** 096928a7a56fa66fa97fd07650883d39ca27c0ac (diff base 4c9abdae)
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Reviewed the Phase 90 changes: the shared pending predicate and the two close-out functions in `db.py`, including the rollback, retire and replace connection handling; the startup orphan sweep and queued-work revalidation in `scheduler.py`; Radarr/Lidarr selection by stable ID in `tracking.py`; the close-out wiring in `remove_instance`, `save_settings` and `search_now` in `routes.py`; the History and activity-rail badge and filter templates; and the new tests.

Checked against the locked decisions in 90-CONTEXT.md:
- Close-out and lookups use the stable ID only (D-00c, D-01).
- The startup sweep runs after the cutover, uses every configured instance including disabled ones, and never touches Legacy rows (D-11).
- Removed-instance rows are excluded from grab rate (D-06) and from the pending cap (D-07).
- Removal adds no network step (D-10).
- Failures after the settings write do not fail the removal (D-00b).

Each of these holds in the code. Log lines on the failure paths record only the exception type (`_sanitize_exc`), so no secrets leak. Ruff is clean. The six directly affected test modules pass: 394 passed at the reviewed commit.

No blocker was found. One defect causes data loss: closing out a `partial` row overwrites its `detail`, so the record of episodes already grabbed for that search is lost for good. The remaining items are robustness and accuracy notes. Two decided-but-arguable behaviors are set aside for an owner ruling.

## Structural Findings (fallow)

No structural pre-pass was provided.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: Close-out overwrites the detail of `partial` rows, losing the record of confirmed grabs

**File:** `triggarr/db.py:1576-1580` (`close_out_removed_instance_searches`), `triggarr/db.py:1636-1640` (`close_out_orphaned_pending_searches`)
**Issue:** Both close-out UPDATEs set `detail = 'instance removed'` on every pending row, including `outcome = 'partial'` rows. For a Sonarr `partial` row, `detail` is the only per-search record of what was already grabbed (`"partial: 2/5 episodes"`, written by `tracking.py:754-756/896`). History shows it as the hover text on the item name (`history_results.html:144`). After removal, or after the startup sweep, that text is replaced and can never be recovered. The outcome also changes from `partial` to `instance_removed`. As a result, nothing in History shows that a removed instance's search found anything, even though grabs were confirmed and lifetime stats were credited for them. The decisions require the outcome to become "Instance removed" (D-02). None of them requires erasing the existing detail; that is an implementation choice that destroys data. No test pins the detail of a closed `partial` row.
**Fix:** Keep the existing detail and add the removal note to it, or leave `detail` alone when it is not NULL:
```sql
UPDATE search_history
SET outcome = ?,
    detail = CASE WHEN detail IS NULL OR detail = '' THEN ? ELSE detail || ' (' || ? || ')' END,
    resolved_at = ?
WHERE ...
```
Add a test that closes a `partial` row with `detail = 'partial: 2/5 episodes'` and asserts that the grab count is still in `detail` afterwards.

## Info

### IN-01: The refuse-to-track count still selects by display name and can count another instance's rows

**File:** `triggarr/tracking.py:121-133`
**Issue:** When `instance_stable_id` is empty, the code counts pending rows through `get_trackable_entries(db, instance_id=instance_id)`, which matches by display name. If a removed same-name instance's pending rows have not been closed yet, for example because its close-out failed and the next startup has not run, they are counted as this instance's errors. The value is only a count, so D-00c is not broken. It is still the name-based selection this phase set out to remove. The path is reachable only if `ensure_config` failed to backfill an ID.
**Fix:** Log the refusal without a count, or report the count as "rows under this name" so it is not presented as this instance's pending searches.

### IN-02: Retired-connection failures surface as `ValueError`, which the narrow error catches do not handle

**File:** `triggarr/web/routes.py:1132-1161` (`_replace_retired_db`), `triggarr/search/scheduler.py:466`
**Issue:** If replacing the connection fails, `app.state.db` remains a retired (closed) connection. aiosqlite then raises `ValueError("no active connection")`, not `aiosqlite.Error`, so the cycle catch `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error)` and the route catches miss it. Every request then fails with a 500 and every job goes to the generic error listener until a restart. This is documented ("a restart recovers") and needs two unlikely failures in a row. The user-visible effect is generic 500 pages, not a clear degraded state.
**Fix:** Optionally set `app.state.persistence_degraded = True` when the replacement fails, so the condition is visible and is not just a stream of 500s.

### IN-03: Three copies of the shield-until-done loop

**File:** `triggarr/db.py:1412-1436` (`_run_to_completion`), `triggarr/web/routes.py:1137-1147` (`_replace_retired_db`), existing `_close_removed_client` in `routes.py`
**Issue:** `_replace_retired_db` repeats the `while not task.done(): await asyncio.shield(task)` loop that `_run_to_completion` already provides, with slightly different handling when the task itself ends cancelled. The cancellation semantics are subtle and now live in several places that can drift apart.
**Fix:** Make `_run_to_completion` public, or move it to a small shared helper, and call it from `_replace_retired_db` and `_close_removed_client`.

### IN-04: The sweep docstring says rows without a stable ID "cannot belong to a configured instance", which is not accurate

**File:** `triggarr/db.py:1608-1612`; related ordering in `triggarr/search/scheduler.py:770-775`
**Issue:** `migrate_from_state` runs after `init_db`, so after migration v10 has done its name-to-ID association. Rows it imports from `state.json` therefore always have a NULL `instance_stable_id`, even when their instance is still configured. The decision (RESEARCH A1) accepted closing these rows. The docstring states an unconditional rule, though, and a later maintainer may rely on it.
**Fix:** Rewrite the sentence to match the decision: "Rows with no stable ID are never selected by any instance. This includes the item-less rows imported from `state.json`, which may belong to a configured instance. They are closed by decision A1."

## Set aside (needs ruling)

### SA-01: Closed `partial` rows leave grab rate even though some grabs were confirmed

**Where:** `triggarr/db.py:1782-1785` (effectiveness query, `outcome != 'instance_removed'`)
**Why excluded:** D-06 is a locked decision: "Instance removed" rows are left out of grab rate because their real outcome is unknown.
**Effect if left as is:** A `partial` row's outcome is partly known, since at least one grab was confirmed. Closing it removes a confirmed grab from both the numerator and the denominator, so an instance's or app's grab rate can drop slightly after a removal. Lifetime totals still include the grabs, so the two figures disagree a little.
**Needs:** An owner ruling on whether `partial` rows should end as `partial_expired` (an existing finished outcome that keeps the grab credit) instead of `instance_removed`, or whether D-06 stands as written.

### SA-02: A configured instance whose stable ID changes has its pending searches closed as "Instance removed" at startup

**Where:** `triggarr/search/scheduler.py:786-822`, `triggarr/db.py:1594-1655`
**Why excluded:** D-11 defines an orphan as a row whose stable ID is not configured. This case comes from editing the config by hand (deleting or changing an instance's `id`, or restoring a config file without IDs) rather than from the code under review.
**Effect if left as is:** After such an edit, `ensure_config` gives the instance a new ID. The next startup closes all its pending searches with the tooltip "This instance was removed before the search finished", although the instance was not removed. Before this phase, Radarr and Lidarr would have kept tracking those searches by name.
**Needs:** Owner ruling. Accept this as expected behavior for hand-edited IDs, or document in the config comments that the `id` field must not be edited.

---

_Reviewed: 2026-11-18_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_

## Dispositions (2026-11-19, after the paired Codex pass and the required vibe-check)

Applied in fix round 1 (all on the phase branch; full suite 3520 passed, 1 skipped; ruff clean):

- **WR-01:** fixed in `3aa2cad6`. Both close-out UPDATEs keep an existing detail and append the removal note (`partial: 2/5 episodes (instance removed)`); tests for both functions.
- **IN-04:** fixed in `3e778629` (docstring now states decision A1).
- **IN-03:** not changed. The four wait-loop copies have different cancellation semantics; owner chose to document and unify later as its own task (backlog entry in `.planning/backlog/MAINTENANCE.md`, commit `edf393e4`).
- **IN-01, IN-02:** accepted as documented; no change.

Owner rulings:

- **SA-01:** D-06 stands as written. Part-done searches of a removed instance end as "Instance removed" and leave grab rate; lifetime totals keep the grabs.
- **SA-02:** dismissed. Instance ids are Triggarr-managed; hand-removing or hand-changing them is unsupported (also decided on the vibe-check card, pass 3).
- **A1 (imported `state.json` rows closed as "Instance removed"):** kept as decided.
- **Upgrade visibility (vibe-check impact lane):** log per-app counts before the startup sweep writes (`1744f43a`) and state the one-time relabel in the release notes. No pre-sweep backup.

Other review sources at this checkpoint:

- **Codex (contract pass, head `669280d4`, attempt 1, complete):** F001 (a 90-06 plan acceptance check counted the comment it requires) — the plan check now excludes comment lines.
- **Vibe-check (required at high risk, deep review passes 1-3 on `669280d4` → `1a9039bd`):** NULL-outcome normalization fixed in `1a9039bd` and confirmed by an independent re-check; wait-loop duplication deferred; config-id item dismissed (above).
