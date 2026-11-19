# Phase 90: Removed-Instance Pending-Search Lifecycle - Context

**Gathered:** 2026-11-18
**Status:** Ready for planning

<domain>
## Phase Boundary

When an instance is removed, its still-pending searches (`outcome` `'searched'`/`'partial'`) get a defined, visible final outcome, "Instance removed". They are never checked, credited or counted toward the pending-search limit again, and an instance added later under the same display name never selects them, shows them as its own in-progress work, or receives credit for them. Searches already orphaned by removals before this release reach the same outcome at upgrade/startup.

**Scope widened by owner decision (2026-11-18):** RMINST-01..04 are worded for Sonarr only. The owner chose to apply the whole lifecycle to **Sonarr, Radarr and Lidarr** (D-01). The planner updates the RMINST wording in `.planning/REQUIREMENTS.md` (and the Phase 90 goal/success-criteria wording in `.planning/ROADMAP.md`) to match, following `docs/PLANNING-FORMAT.md`.

Out of scope: lifetime-stats cleanup for removed instances (D-09), any change to the "Legacy" rows' behavior, and the Phase 91 delivery-confidence work.
</domain>

<decisions>
## Implementation Decisions

### Carried forward (milestone standing rules and prior phases, not re-asked)
- **D-00a:** No new runtime dependency. Each fix lands with a regression test that fails on the unfixed code.
- **D-00b:** (Phase 87 D-02/D-15/D-16) In `remove_instance`, nothing changes until the settings file write succeeds. After that the removal is real: if closing out the pending searches fails, the user still sees a normal successful removal, the failure is logged (secrets redacted), and the remaining tidy-up steps still run. The startup sweep (D-11) catches any rows this missed.
- **D-00c:** Identity isolation (backlog item "Pending Sonarr searches of a removed instance", `.planning/backlog/MAINTENANCE.md`): no row is ever selected or credited by an ID other than its own.

### Which apps
- **D-01:** The close-out and same-name protection apply to Sonarr, Radarr and Lidarr. Today Radarr/Lidarr select pending rows by display name (`get_trackable_entries(instance_id=...)` from `tracking.py` non-Sonarr path), so a new same-name Radarr/Lidarr instance inherits and checks the removed one's pending searches against its own server. After this phase, a new same-name instance of any app must never select, display as its own in-progress work, or be credited for a removed instance's searches. Radarr/Lidarr pending-row selection moves to the stable instance ID, as Sonarr already does (rows already carry `instance_stable_id` since migration v10).

### How it reads in History
- **D-02:** The badge text is "Instance removed", with the tooltip: "This instance was removed before the search finished; it will not be checked again." Used in the History page and the activity rail.
- **D-03:** Same muted gray styling as the existing "Legacy — tracking discontinued" badge; the wording distinguishes them. The two must never be conflated: an "Instance removed" row is not shown as Legacy, and vice versa.
- **D-04:** The History page outcome filter gets an "Instance removed" option alongside the existing outcomes.
- **D-05:** Rows keep their original display name (`instance_id`). If a new instance reuses that name, the old rows still appear under that name in History, but carry the "Instance removed" badge and are never shown as pending/in-progress.

### Effect on stats
- **D-06:** "Instance removed" searches are left out of grab-rate and effectiveness figures (the same way Legacy rows are excluded today), because their real outcome is unknown.
- **D-07:** They are not pending: they never count toward the per-instance pending-search cap (`PendingCapExceeded`) or any pending/in-progress count on the dashboard.

### How long they're kept
- **D-08:** Once closed out, these are finished searches and age out of History under the normal finished-row limit, like any other finished search. They are not kept forever.
- **D-09:** The removed instance's lifetime stats are left as they are. The planner verifies that a new same-name instance (all three apps) never displays the old instance's totals, and records the result; any defect found goes to the maintenance backlog, not this phase.

### Close-out timing
- **D-10:** Close out immediately on removal, with no final grab check against the server being removed. Removal must not gain a new network step or a new way to fail.
- **D-11:** A sweep at every startup (after migrations, before the scheduler starts) closes out pending searches whose `instance_stable_id` is not a configured instance. This delivers RMINST-04 (orphans from removals before this release) and repairs any close-out that failed after a successful settings write (D-00b). It must never touch rows of a configured instance, and must never touch pre-cutover Legacy rows (their existing treatment stays). Rows with no `instance_stable_id` at all: the planner decides, with evidence, whether any can exist and how they are treated, without breaking D-00c.

### Claude's Discretion
- Mechanism: a real terminal outcome value written to the rows (e.g. `'instance_removed'`) is the expected shape, since D-08 relies on the normal finished-row pruning. The planner may choose otherwise with reasons, provided D-02..D-11 hold.
- Per the backlog item "Shared pending-outcome rule" (`.planning/backlog/MAINTENANCE.md`), the "which outcomes are pending" rule now copied in about six places in `db.py` is consolidated into one shared predicate/constant in this phase, with deliberate, tested NULL handling, rather than adding another copy.
- Whether the startup sweep is a one-off migration plus a recurring check, or only a recurring check.
- Whether owned-grab records (`grab_ownership`) of a removed instance need any handling; leave them unless a defect is shown.
- Log wording: one info line per close-out (app, instance, number of searches closed), and for the startup sweep, one line stating how many orphaned searches were closed. Secrets redacted by the existing sink.
- Exact filter value/label plumbing and test structure (patterns in `tests/test_db.py`, `tests/test_tracking.py`, existing `remove_instance` tests).

</decisions>

<specifics>
## Specific Ideas

- The existing "Legacy" treatment (`_LEGACY_PENDING_SQL`, `is_legacy` columns, the gray badge) is the model to follow for exclusion and display. "Instance removed" differs from Legacy in being a real finished outcome that ages out (D-08).
- Tests to include: remove an instance with pending searches → rows become "Instance removed", out of the cap, excluded from grab rate, shown with the badge; add a new same-name instance (each of Sonarr, Radarr, Lidarr) → its tracking check never selects or credits the old rows; startup with orphaned pending rows from an unconfigured stable ID → closed out, while a configured instance's pending rows and Legacy rows are untouched.
</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and research
- `.planning/REQUIREMENTS.md` — RMINST-01..04 (wording to widen to all three apps per D-01)
- `.planning/ROADMAP.md` — Phase 90 goal and success criteria
- `.planning/research/SUMMARY.md` — item 7 and open question 4 (removed-instance leftovers)
- `.planning/research/PITFALLS.md` (~line 230) — identity isolation analysis for removed instances
- `.planning/research/ARCHITECTURE.md` (§5, ~lines 228-284) — reuse the `_LEGACY_PENDING_SQL` precedent; integration in `remove_instance`
- `.planning/research/STACK.md` (Capability 5, ~line 179) — where pending rows become orphaned

### Backlog items this phase resolves or must respect
- `.planning/backlog/MAINTENANCE.md` — "Pending Sonarr searches of a removed instance (Phase 81 deep review bugs-005)" and "Shared pending-outcome rule"

### Prior phase decisions
- `.planning/phases/87-settings-state-file-safety/87-CONTEXT.md` — D-02, D-15, D-16 (removal ordering and tidy-up rules)

### Project rules
- `docs/PLANNING-FORMAT.md` — for the REQUIREMENTS/ROADMAP wording update
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `triggarr/db.py` `_LEGACY_PENDING_SQL` / `_LEGACY_MAX_ID_SQL` (~line 822): the exclusion predicate pattern, used in `get_trackable_entries`, the pending-cap queries in `insert_search_entry`, `get_recent_searches`/`get_search_history` (`is_legacy`), and `get_dashboard_stats` effectiveness queries.
- `triggarr/templates/partials/history_results.html` (~lines 83-157) and `partials/activity_rail.html` (~lines 32, 77-78): outcome filter and Legacy badge markup to extend.

### Established Patterns
- Pending = `outcome IN ('searched','partial')`. Finished rows are trimmed inline after each insert; pending rows are never trimmed (`db.py` ~848-960).
- Sonarr tracking selects by `instance_stable_id` (`tracking.py` `_run_sonarr_tracking_check`); Radarr/Lidarr select by display name (`tracking.py` ~line 123), which is what D-01 changes.
- `remove_instance` (`triggarr/web/routes.py` ~line 1044): writes settings under `search_lock` and only then changes live state; the close-out goes into that post-write tidy-up.

### Integration Points
- `remove_instance` post-write tidy-up (close-out on removal).
- App startup in the lifespan after `run_migrations` (startup sweep), following Phase 89's cleanup-on-failure structure.
- `get_trackable_entries`, pending-cap queries, History queries, dashboard stats queries.
</code_context>

<deferred>
## Deferred Ideas

None. Lifetime-stats cleanup for removed instances was considered and declined (D-09).
</deferred>

---

*Phase: 90-removed-instance-pending-search-lifecycle*
*Context gathered: 2026-11-18*
