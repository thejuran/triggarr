# Phase 90: Removed-Instance Pending-Search Lifecycle - Research

**Researched:** 2026-11-18
**Domain:** Internal change to triggarr (Python 3.11, FastAPI, aiosqlite/SQLite, Jinja2/htmx). No external libraries involved.
**Confidence:** HIGH (all findings are from reading this repo's code; the one external-behaviour claim, SQLite semantics, is tagged)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-00a:** No new runtime dependency. Each fix lands with a regression test that fails on the unfixed code.
- **D-00b:** (Phase 87 D-02/D-15/D-16) In `remove_instance`, nothing changes until the settings file write succeeds. After that the removal is real: if closing out the pending searches fails, the user still sees a normal successful removal, the failure is logged (secrets redacted), and the remaining tidy-up steps still run. The startup sweep (D-11) catches any rows this missed.
- **D-00c:** Identity isolation: no row is ever selected or credited by an ID other than its own.
- **D-01:** The close-out and same-name protection apply to Sonarr, Radarr and Lidarr. Radarr/Lidarr pending-row selection moves to the stable instance ID, as Sonarr already does (rows already carry `instance_stable_id` since migration v10). A new same-name instance of any app must never select, display as its own in-progress work, or be credited for a removed instance's searches.
- **D-02:** Badge text "Instance removed", tooltip "This instance was removed before the search finished; it will not be checked again." Used in the History page and the activity rail.
- **D-03:** Same muted gray styling as the "Legacy — tracking discontinued" badge; wording distinguishes them. Never conflated.
- **D-04:** History outcome filter gets an "Instance removed" option alongside existing outcomes.
- **D-05:** Rows keep their original display name (`instance_id`). Old rows under a reused name still appear in History with the "Instance removed" badge and are never shown as pending/in-progress.
- **D-06:** "Instance removed" searches are left out of grab-rate and effectiveness figures (as Legacy rows are today).
- **D-07:** They are not pending: they never count toward the per-instance pending cap (`PendingCapExceeded`) or any pending/in-progress count on the dashboard.
- **D-08:** Once closed out, they age out of History under the normal finished-row limit.
- **D-09:** Removed instance's lifetime stats left as they are. Planner verifies a new same-name instance (all three apps) never displays the old totals and records the result; defects go to the maintenance backlog, not this phase.
- **D-10:** Close out immediately on removal, no final grab check, no new network step.
- **D-11:** A sweep at every startup (after migrations, before scheduler start) closes out pending searches whose `instance_stable_id` is not a configured instance. Must never touch a configured instance's rows or pre-cutover Legacy rows. Rows with no `instance_stable_id`: planner decides with evidence, without breaking D-00c.

### Claude's Discretion
- Mechanism: a real terminal outcome (e.g. `'instance_removed'`) is expected.
- Consolidate the "which outcomes are pending" rule (about six copies in `db.py`) into one shared predicate/constant with deliberate, tested NULL handling.
- Whether the startup sweep is a one-off migration plus a recurring check, or only a recurring check.
- Whether `grab_ownership` records of a removed instance need handling; leave them unless a defect is shown.
- Log wording (one info line per close-out; one line for the startup sweep).
- Exact filter value/label plumbing and test structure.

### Deferred Ideas (OUT OF SCOPE)
None. Lifetime-stats cleanup for removed instances was considered and declined (D-09). Also out of scope: any change to Legacy rows' behavior, Phase 91 delivery-confidence work.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RMINST-01 | Removed instance's pending searches get final outcome "Instance removed", visible in History, distinct from Legacy | New terminal outcome `'instance_removed'`; close-out in `remove_instance` post-write tidy-up; badge branches in `history_results.html` and `activity_rail.html` (see Architecture, Code Examples) |
| RMINST-02 | Not counted toward pending cap, never checked/credited again | Falls out automatically once the outcome is not in the shared pending predicate; D-06 additionally needs explicit exclusion in `get_dashboard_stats` (`outcome != 'failed'` currently counts it in the denominator) |
| RMINST-03 | Same-name new instance never selects/displays/credits old rows | Move Radarr/Lidarr selection in `tracking.py:123` to `instance_stable_id`; closed rows are not pending so they never render as in-progress; D-09 stats verification |
| RMINST-04 | Pre-release orphans reach same outcome at upgrade/startup | Idempotent startup sweep in lifespan after `ensure_cutover_recorded`; NULL-id analysis below |
</phase_requirements>

## Summary

The change is small in surface but touches the single most reused predicate in `db.py`. The pending rule `outcome IN ('searched','partial')` is written six different ways in `triggarr/db.py` (lines 824, 904, 911, 956, 959, 1183), with two different NULL treatments: `COALESCE(outcome,'searched')` (legacy predicate, prune) versus bare `outcome IN` (cap, trackable). A new terminal outcome `'instance_removed'` needs no schema change: there is no CHECK constraint, enum, `Literal` or pydantic model on `outcome` anywhere (verified by grep: the only CHECK in the schema is `attribution_cutover.id = 1`). It needs a constant, template branches, a filter label, a stats exclusion, a close-out function, a startup sweep, and a selection change for Radarr/Lidarr tracking.

Finished-row pruning (`db.py:953-964`) deletes rows `COALESCE(outcome,'searched') NOT IN ('searched','partial')` beyond the newest `max_rows` by id, so an `'instance_removed'` row is automatically a "finished" row and ages out normally (D-08) with no code change, as long as the shared predicate is the single source for both the prune and the pending rules.

The biggest design risks are (1) the startup sweep running before the attribution cutover is recorded (it would then destroy Legacy rows), (2) building the "configured IDs" set from enabled instead of all configured instances (it would close a disabled instance's pending rows), (3) NULL-`instance_stable_id` rows, which do exist after v10 and, once Radarr/Lidarr select by stable ID, would otherwise become permanent never-pruned "in-progress" rows, and (4) existing tests in `tests/test_tracking.py` that assert the old name-based Radarr/Lidarr behaviour and must be rewritten, not deleted.

**Primary recommendation:** Add `outcome='instance_removed'` (no migration), one shared pending predicate in `db.py`, one `close_out_removed_instance_searches()` and one `close_out_orphaned_pending_searches()` function in `db.py`; call the first from the `remove_instance` post-write tidy-up (isolated try/except) and the second from the lifespan right after `ensure_cutover_recorded`; switch Radarr/Lidarr tracking selection to stable ID; extend stats and both templates.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pending-outcome rule, close-out SQL, orphan sweep | Database / Storage (`triggarr/db.py`) | — | All outcome/legacy predicates live here; one shared constant |
| Trigger close-out on removal | API / Backend (`routes.py::remove_instance`) | — | Post-write tidy-up under `search_lock` |
| Trigger sweep at startup | API / Backend (`scheduler.py::create_lifespan`) | DB | Lifespan owns migrations/cutover ordering |
| Pending-row selection by identity | API / Backend (`tracking.py`) | DB (`get_trackable_entries`) | Selection must use stable ID for all three apps |
| Badge, tooltip, filter option | Frontend Server (Jinja templates) | — | Server-rendered History page and activity rail |
| Stats exclusion (D-06) | Database (`get_dashboard_stats`) | — | SQL-level exclusion mirroring Legacy |

## Standard Stack

No new libraries (D-00a). Existing: Python 3.11+, aiosqlite, loguru, FastAPI, Jinja2, pytest + pytest-asyncio (`asyncio_mode=auto`), ruff (E,F,I,UP,B,SIM; line length 120). `[VERIFIED: codebase, CLAUDE.md]`

**Installation:** none. **Package Legitimacy Audit:** not applicable, no packages are installed by this phase.

## Findings with Code Evidence

### 1. Every encoding of "pending" in `triggarr/db.py`

| Line | Code | NULL handling | Purpose |
|------|------|---------------|---------|
| 822-827 | `_LEGACY_MAX_ID_SQL`, `_LEGACY_PENDING_SQL = (app='Sonarr' AND COALESCE(outcome,'searched') IN ('searched','partial') AND id <= <cutover max>)` | COALESCE (NULL = pending) | Legacy predicate; max id defaults to 0 when no cutover row |
| 904 | cap query (stable ID mode): `outcome IN ('searched','partial') AND app=? AND instance_stable_id=? AND NOT _LEGACY_PENDING_SQL` | bare (NULL not pending) | `PendingCapExceeded` |
| 911 | cap query (name mode, used when stable ID falsy) | bare | same |
| 956, 959 | prune: `COALESCE(outcome,'searched') NOT IN ('searched','partial')` (twice, outer DELETE and subquery) | COALESCE | finished-row trim |
| 1183 | `get_trackable_entries`: `outcome IN ('searched','partial') AND item_id IS NOT NULL AND NOT _LEGACY_PENDING_SQL` | bare | tracking selection |
| 1087 | history filter: `COALESCE(outcome,'searched') IN (...)` | COALESCE | display filter (not a pending rule, but same convention) |

Also: `get_recent_searches` (1007) and `get_search_history` (1113) compute `is_legacy` with `_LEGACY_PENDING_SQL`; `get_dashboard_stats` applies `NOT {_LEGACY_PENDING_SQL}` at 1508 and 1588. `[VERIFIED: codebase grep]`

**NULL conclusion:** a NULL `outcome` cannot arise on current code paths: `insert_search_entry` always writes a non-NULL outcome (default `'searched'`), v1 added the column with `DEFAULT 'searched'`, v4 backfilled NULLs to `'unresolved'`, and `migrate_from_state` (db.py ~1417) omits the column so it takes the default. The display layer treats NULL as `'searched'` (`row["outcome"] or "searched"`, lines 1028/1126) and the prune treats it as pending. **Recommendation:** the shared predicate uses `COALESCE(outcome, 'searched')` everywhere (matches prune, legacy predicate and display; makes the cap/trackable queries consistent). Test it explicitly with a raw-SQL inserted NULL-outcome row: counted by cap, selected by trackable, never pruned. `[VERIFIED: codebase]`

**Consolidation shape (recommended):**
```python
# db.py, near _LEGACY_*; one source of truth
PENDING_OUTCOMES = ("searched", "partial")
OUTCOME_INSTANCE_REMOVED = "instance_removed"
_PENDING_SQL = "COALESCE(outcome, 'searched') IN ('searched', 'partial')"
_NOT_PENDING_SQL = "COALESCE(outcome, 'searched') NOT IN ('searched', 'partial')"
_LEGACY_PENDING_SQL = "(app = 'Sonarr' AND " + _PENDING_SQL + " AND id <= " + _LEGACY_MAX_ID_SQL + ")"
```
Build the tuple-derived SQL from `PENDING_OUTCOMES` (one definition) and add a test asserting that `'instance_removed'` is in neither list. Replace the six copies. `tracking.py` has no pending rule of its own (it relies on `get_trackable_entries`).

### 2. How outcomes are validated/stored

- Schema: `search_history.outcome TEXT` added by `_migrate_v1` (db.py ~397) with default `'searched'`; no CHECK, no enum. `[VERIFIED: codebase]`
- Python: no `Literal`/enum/pydantic model for outcome values (grep of `triggarr/` for outcome hits only db.py, tracking.py, engine.py, routes.py history plumbing, templates).
- Writes: `insert_search_entry` (db.py 830), `update_outcome_and_stats` (1242, sets `outcome, detail, resolved_at` by id, no guard on current outcome), `_migrate_v4/_v8`.
- Templates map outcome to badge by string compare (see section 8). Unknown outcomes fall through to a generic gray branch that prints the raw string (`history_results.html:157`, `activity_rail.html:88`), so without template work a closed row would display literally `instance_removed`. The History filter pill also prints the raw `o_val` (`history_results.html:101`), so the filter needs a value-to-label mapping.
- **Therefore adding `'instance_removed'` requires: a constant, template branches (history badge + title, rail dot + pill), filter list + label, dashboard stats exclusion. No migration.**

### 3. Finished-row pruning and D-08

`insert_search_entry` (db.py 953-964) after every insert runs `DELETE ... WHERE COALESCE(outcome,'searched') NOT IN ('searched','partial') AND id NOT IN (SELECT id ... same predicate ORDER BY id DESC LIMIT max_rows)`. An `'instance_removed'` row matches the not-pending predicate, so it is in the finished pool and is trimmed oldest-id-first like any finished row. Pending rows are never pruned. **D-08 is satisfied with no code change** provided the prune uses the shared predicate. Test: insert N+1 finished rows plus an `instance_removed` row with the lowest id and `max_rows=N`; it is pruned. Note a mass close-out adds many rows to the finished pool; trimming happens on the next insert (the pool can transiently exceed `max_rows`, which is the existing behaviour for any batch). `[VERIFIED: codebase]`

Corollary (important for NULL-id analysis below): any pending row that no code path ever resolves is **never pruned and never expires**. Leaving unreachable pending rows is a permanent leak, not a cosmetic issue.

### 4. `tracking.py` selection and crediting

- `run_tracking_check(db, client, app_name, instance_id, window, *, instance_stable_id)` (tracking.py:69). Sonarr branch (113-121) delegates to `_run_sonarr_tracking_check` (522), which: if `instance_stable_id` empty, logs an error and counts pending rows via `get_trackable_entries(instance_id=...)` only to report `counts["errors"]` and returns without tracking (541-552); otherwise `get_trackable_entries(db, instance_stable_id=...)` (554). Crediting uses `instance_stable_id` for lifetime stats and ownership (`update_outcome_and_stats` at ~756/778; `get_owned_grabs(app="Sonarr", instance_stable_id=...)` at 598).
- Radarr/Lidarr branch (123): `entries = await get_trackable_entries(db, instance_id=instance_id)` selects **by display name**, then credits with `instance_stable_id=entry["instance_stable_id"] or instance_stable_id or None` (line 200), i.e. a same-name new instance inherits the old rows, checks them against its own server, and falls back to crediting itself when the row has no ID. This is the D-01 defect.
- Radarr/Lidarr use no `grab_ownership` (ownership is Sonarr-only; `owned_grabs` is passed only from the Sonarr path). `[VERIFIED: codebase]`
- **Change:** line 123 becomes `get_trackable_entries(db, instance_stable_id=instance_stable_id)` with the same empty-ID guard the Sonarr path has (an empty ID must refuse to track and count errors, never fall back to name). Line 200 simplifies to `instance_stable_id=instance_stable_id` (every selected row now has that ID). Update the docstring (lines 84-95 say selection by name is unchanged). `get_trackable_entries(instance_id=...)` can remain for the Sonarr empty-ID counting path and the no-filter mode used by tests; update its docstring (db.py 1154-1157 "out of scope for this phase").
- The scheduler call site passes `instance_stable_id=instance_config.id` (scheduler.py:222-229); engine inserts always pass `instance_config.id` (engine.py lines 1183, 1211, 1493, 1538, 1796, 1824). Config backfills IDs before startup (`config.py backfill_instance_ids`), so a configured instance never has an empty ID at runtime.

**Existing tests that encode the old Radarr/Lidarr behaviour and must be rewritten** (they assert the new instance DOES select/credit the old row):
- `tests/test_tracking.py:1304` `test_radarr_name_reuse_credits_the_search_rows_own_stable_id`
- `:1322` `test_lidarr_name_reuse_credits_the_search_rows_own_stable_id`
- `:1342` `test_radarr_row_without_stable_id_falls_back_to_current_instance` (a NULL-ID row is now NOT selected by anyone)
- `:1359` `test_radarr_name_reuse_through_real_client_keeps_card_consistent` and `:1396` Lidarr twin (new card must show 0 and the old row must stay untouched; the old card's `movies_found == 1` assertions become 0)
Re-express each as "sid-new never selects/credits sid-old's row; row unchanged; no stats move". Also re-check `test_per_instance_tracking_isolation` (564) and `test_old_name_reuse_by_different_server_isolated` (857) still pass.

### 5. Rows with NULL `instance_stable_id`: they exist

Evidence:
1. Migration v10 adds the column nullable (db.py 684-685) and associates only configured `(app, name)` pairs (729-737). Rows belonging to an instance removed **before** the upgrade stay NULL forever. This is exactly the RMINST-04 population for Radarr/Lidarr (and for Sonarr, where they are pre-cutover and therefore Legacy).
2. `insert_search_entry` stores NULL for a falsy ID (`instance_stable_id or None`, db.py 946; test `test_insert_search_entry_records_stable_id`).
3. `migrate_from_state` imports rows with no instance/stable ID/item_id.
4. Production is already past v10 (v2.12.0 shipped it; prod runs v2.12.1), so for configured instances all pre-v10 rows were associated at that upgrade; after v10, every writer passes `cfg.id`. So any NULL-ID **pending, non-Legacy** row present at a startup is by construction not owned by a currently-configured instance: either an orphan of a removed instance, an item_id-less imported row, or a row whose name was unconfigured at v10 time and has since been re-added (the D-00c case).

Relation to Legacy: Legacy is Sonarr-only and defined by `id <= legacy_max_history_id` (not by ID nullness). NULL-ID Sonarr rows are all `<=` the cutover (cutover is recorded at the first startup after v10 using `MAX(id)`), so they are Legacy and stay Legacy. NULL-ID Radarr/Lidarr rows are never Legacy.

Consequence of the D-01 selection change: after moving Radarr/Lidarr to stable-ID selection, NULL-ID Radarr/Lidarr pending rows are selected by nobody, never resolve, are never pruned, and keep rendering as in-progress. **Recommendation:** the startup sweep treats a pending, non-Legacy row with `instance_stable_id IS NULL` as orphaned and closes it. It cannot break D-00c (closing is the opposite of adoption) and cannot touch a configured instance's rows (those carry its ID). Flag as `[ASSUMED]` A1 below: those that came from the one-time `state.json` import also carry no item_id and were never trackable; labelling them "Instance removed" is slightly inexact but they are untrackable leaks. Alternative if the owner dislikes the label for them: restrict NULL handling to `item_id IS NOT NULL`. Planner should pick the first and document it.

### 6. `remove_instance` and the Phase 87 tidy-up ordering (`routes.py`)

Flow (`remove_instance`, routes.py:1044-1260), all inside `async with request.app.state.search_lock`:
1. validate; existence re-check under lock (1066); build `new_settings` without touching live state (1079-1081).
2. `_settings_to_dict` (guarded), then atomic TOML write in an executor with abandon/claim gate (1126-1193); any failure -> `_removal_failed_response`, nothing changed.
3. **After the write succeeds** (comment 1195-1199: "removal is real (D-15)... every remaining step runs regardless... each failure logged independently (D-16)"): `request.app.state.settings = new_settings` (1200); isolated `try/except Exception` for scheduler job removal (1206-1216); plain dict pops for client, state entry, tag cache (1221-1229).
4. Outside the lock: close the stale client via `_close_removed_client` (1237-1247, failure logged not raised); re-raise a held cancellation; return the normal success response.

**Where the close-out goes:** inside the lock, after `request.app.state.settings = new_settings`, as another isolated step in the same style as the scheduler-job step:
```python
removed_cfg = instances[instance_name]   # capture BEFORE the `del` at 1080 (or read from `settings`)
...
try:
    closed = await close_out_removed_instance_searches(
        request.app.state.db, app=app_name.title(), instance_stable_id=removed_cfg.id, instance_id=instance_name)
    # one info line: app, instance, closed count
except Exception as exc:  # error boundary for post-commit cleanup (D-15, D-16)
    logger.error("Removed {app}/{inst} but closing out its pending searches failed: {exc_type}: {exc}", ...)
```
Placement inside the lock matters: it serializes with tracking and search cycles (both run under `search_lock`), so no tracking check can credit a row mid-close-out. Pitfalls: (a) the stored app name is title-case (`app_name.title()`, as in `scheduler.py:225` and `get_dashboard_stats(app=...)`), while `app_name` in the route is lowercase; (b) `removed_cfg.id` must be captured before the instance is deleted from the dict; if empty (cannot happen post-backfill) skip with a warning rather than closing by name (D-00c); (c) the close-out function must roll back on failure like `update_outcome_and_stats` (R-08) so a failed UPDATE cannot leave an open transaction on the shared connection that another request's commit would then flush; (d) existing `tests/audit_lock_coverage.py` AST-audits routes.py for lock coverage, so keep the call inside the existing `async with` block.
Cancellation: the close-out is awaited inside the lock; `CancelledError` handling is outside the generic `except Exception` (BaseException), same as the other steps. Narrow, pre-existing race: `scheduler.py job()` looks up client/config before taking the lock (lines 175-181), so a job already waiting on the lock when the removal runs can still insert new pending rows for the removed ID after the close-out. The startup sweep repairs those; do not widen scope to fix the job. Mention in a code comment.

Existing remove tests live in `tests/test_web.py` (fixture `multi_instance_app` at 1061, which uses `init_db(db, db_path)` on a real SQLite file and a mock scheduler; tests at 1484-1923). Instances in that fixture have empty `id` unless set explicitly (`InstanceConfig(..., id="...")`), so new tests must give instances explicit ids.

### 7. Lifespan ordering and the startup sweep (`scheduler.py::create_lifespan`, 656-)

Order inside the `try` (line 697): `aiosqlite.connect` + WAL pragmas (698-700) -> build `instance_stable_ids` from **all** configured instances (705-710, includes disabled; `cfg.id` truthy only) -> `init_db` (711, runs migrations incl. v10 association) -> optional `migrate_from_state` import (715-719) -> **`ensure_cutover_recorded` (728)** -> create clients for enabled instances (731-747) -> app.state wiring -> add jobs -> `scheduler.start()` (855). The `except BaseException` block (871-) is the Phase 89 cleanup-on-failure: it stops the scheduler, closes clients and the db, then re-raises. Anything awaited inside this `try` is automatically covered by that cleanup.

**Where to put the sweep:** immediately after `ensure_cutover_recorded` (line 728) and before client creation. This is the only correct slot:
- Before `ensure_cutover_recorded` the cutover row does not exist, `_LEGACY_MAX_ID_SQL` evaluates to 0, nothing is Legacy, and the sweep would close every pre-cutover Sonarr row as "Instance removed", destroying the Legacy treatment (violates D-11). Pitfall P1.
- After it, Legacy is well-defined and excluded via `NOT _LEGACY_PENDING_SQL`.

**Configured IDs:** `{(app_type.title(), cfg.id) for app_type in APP_TYPES for cfg in getattr(settings, app_type).values() if cfg.id}` over ALL configured instances, including `enabled=False` ones (a disabled instance can be re-enabled and must keep its pending rows). Do NOT use `get_enabled_instances`. `settings` here is the lifespan argument (live config already loaded and ID-backfilled by `startup`, `config.py`).

**Failure policy (recommendation):** the sweep is repair, not safety. Safety (D-00c) comes from stable-ID selection, which never selects orphan rows regardless of whether the sweep ran. So the sweep should catch `Exception` (not `BaseException`; cancellation must still propagate to the Phase 89 cleanup), roll back, log one error, and continue starting (retry next startup). This differs from `ensure_cutover_recorded` (deliberately uncaught because a missing cutover has security consequences). `[ASSUMED]` A2: the owner has not stated this; it follows D-00b's "failure is logged, startup/removal continue" spirit.

**Empty-config guard (recommendation):** if the configured-ID set is empty, skip the sweep and log it (mis-mounted/blank config with a real DB would otherwise irreversibly close every pending row). Cost: orphans from removals before the release stay pending in the (rare) case a user has zero instances at that startup; they are still never selected, and runtime removals are closed at removal time. `[ASSUMED]` A3.

**Implementation shape:** select the distinct pending, non-Legacy `(app, instance_stable_id, instance_id)` groups in SQL, decide orphan-ness in Python against the configured set (`instance_stable_id IS NULL` is always an orphan, per section 5), then `UPDATE ... WHERE <pending> AND NOT <legacy> AND app=? AND instance_stable_id IS ?` per group inside one transaction with a single commit; log one info line `"Startup: closed N orphaned pending search(es) of removed instances"` (and per-instance counts at debug). Using `IS ?` (or two statements) handles NULL equality; `= NULL` never matches. Doing the set difference in Python avoids `NOT IN (...)` placeholder-list and empty-list edge cases. `[CITED: sqlite.org/lang_expr.html (IS / IS NOT treat NULL as an ordinary value)]` `[ASSUMED]` not re-fetched this session.

**Migration vs recurring check:** recommend **recurring check only, no migration**. Current max schema version is 10 (`MIGRATIONS` db.py 753-764). A migration would need the configured-ID mapping (v10 got it through a special keyword, db.py 624/776) and the cutover row does not exist yet when migrations run (it is recorded after), so a migration could not exclude Legacy correctly on a DB upgrading from <v10; and it would not repair a close-out that failed after a successful settings write (D-00b). The idempotent every-startup sweep covers RMINST-04 and that repair. Test idempotency by running the sweep twice.

Close-out values: `outcome='instance_removed'`, `detail` a short fixed string (e.g. `'instance removed'`; note History shows `detail` as a tooltip on the title, `history_results.html:143`), `resolved_at` = now ISO-Z (same format as elsewhere: `datetime.now(UTC).isoformat().replace("+00:00","Z")`). `resolved_at` is only read for `outcome='grabbed'` (db.py 1574, 1599), so setting it is harmless and keeps "finished rows have resolved_at" true.

### 8. History page / activity rail / filter plumbing

- Routes: `history_page` (routes.py 563-579) and `partial_history_results` (597-635) parse `outcome` as a comma list via `_split_filter_param` and pass straight to `get_search_history` (db.py 1037), which parameterizes it (`COALESCE(outcome,'searched') IN (...)`, 1081-1088) and expands `partial` to include `partial_expired` (1084-1085). There is no allowlist, so `outcome=instance_removed` already works server-side. `[VERIFIED: codebase]`
- Template filter pills: `history_results.html:82` loop `['searched','grabbed','partial','unresolved','failed']`, pill label `{{ o_val }}` (101), active colour chain (93-97). Add `'instance_removed'` to the list, display label "Instance removed" via a small mapping, gray active style (like `unresolved`). The `outcome` query value stays `instance_removed`.
- Row badge: `history_results.html:145-158`; chain starts with `entry.is_legacy` (gray, tooltip "Searched before the attribution fix...", text "Legacy — tracking discontinued"), then outcome branches; text is `entry.outcome` verbatim except `partial_expired -> partial`. Add `{% elif entry.outcome == 'instance_removed' %}` to the class chain (gray `bg-gray-500/20 text-gray-400`), the `title=` chain (D-02 tooltip), and the text expression ("Instance removed").
- Activity rail: `activity_rail.html` has two chains, dot (32-44: `is_legacy` -> gray, grabbed, partial, searched yellow, failed red, else gray) and pill (77-89; Legacy pill at 78 uses `bg-gray-500/10 text-gray-500 border border-gray-500/20`). The rail fetches via `get_recent_searches(db)` (routes.py:1488). The dot's `else` already renders gray; the pill's `else` prints the raw outcome, so add an explicit `instance_removed` pill branch with the same muted classes and text "Instance removed", and add a `title=` with the D-02 tooltip (the Legacy pill has none; adding one for the new pill is within D-02, which asks for the tooltip in both places). Also note rail card chrome: only `grabbed`/`partial` get the solid card (48), others dashed; `instance_removed` correctly gets the dashed card.
- Legacy/removed never conflated: `is_legacy` requires a pending outcome (`_LEGACY_PENDING_SQL` includes the pending predicate), so a closed row is never `is_legacy`. Close-out and sweep must exclude Legacy rows so a pre-cutover Sonarr row is never rewritten. Add a test that a Legacy row stays `is_legacy` and `searched` after both close-out paths.
- The History page's "searched" filter currently also matches Legacy rows (they are `searched`); unchanged.

### 9. Dashboard stats (D-06, D-07, D-09)

`get_dashboard_stats` (db.py 1435-1622):
- Effectiveness (1503-1511): `grabbed_count = outcome IN ('grabbed','partial','partial_expired')`, `total_count = outcome != 'failed'`, filtered `outcome IS NOT NULL ... AND NOT _LEGACY_PENDING_SQL`. **An `'instance_removed'` row currently lands in the denominator as a miss.** D-06 requires an explicit exclusion: add `AND outcome != 'instance_removed'` (use the constant) to this query and to the historical-flag query at 1585-1590 (otherwise a closed Sonarr row with id <= cutover could flip `rate_includes_historical`; Legacy rows are excluded from closed set but pre-cutover resolved rows can't be `instance_removed` either, so this is belt-and-suspenders, but keep both queries symmetric). The time-to-grab queries filter `outcome='grabbed'` and are unaffected. Current pending (`'searched'`) rows are still counted in the denominator today; that is existing behaviour, do not change it.
- No dashboard "pending/in-progress count" exists: `routes.py` "pending" hits are connection health (`pending` = not yet connected, lines 436-459) and `health_summary.html:17`. D-07's dashboard clause is satisfied by the pending predicate used for the cap. `[VERIFIED: codebase grep]`
- Per-instance stats: `routes.py:1566-1570` calls `get_dashboard_stats(db, app=app_title, instance_stable_id=cfg.id)` (400 on missing cfg or empty id; name-only fallback is only for `instance_app_type is None`). Effectiveness, flags and `lifetime_stats` are all scoped `app = ? AND instance_stable_id = ?` (1493, 1543-1545), so a new same-name instance with a new random id (`config.py new_instance_id`) sees none of the old instance's search rows or lifetime totals. The global dashboard (routes.py:494, no args) sums all `lifetime_stats` rows including removed instances (existing, out of scope per D-09). Residual to verify and record for D-09: (a) `lifetime_stats` rows with `instance_stable_id = ''` (pre-v10 removed instances) are matched only by the legacy `instance_id=` path (db.py 1550-1555) and by `update_outcome_and_stats` when no stable ID is given (1332-1341); after the D-01 change Radarr/Lidarr always pass a stable ID so the `''` fallback no longer fires from tracking. (b) The name-only branch of `get_dashboard_stats(instance_id=...)` would match old rows by name; its only remaining caller is the no-instance route branch. Plan task: add tests for all three apps that `get_dashboard_stats(app=X, instance_stable_id=new_id)` after reusing a name shows zeros/None, and record the outcome in the SUMMARY; defects go to `.planning/backlog/MAINTENANCE.md`.

### 10. Migration framework conventions (only if a migration were chosen; not recommended)

`MIGRATIONS` dict at db.py 753-764, current max 10. Runner `_apply_atomic_migration` owns the transaction and version record; v10 takes keyword `instance_stable_ids` (db.py 128, 153, 380-383). `tests/test_migration_v10_atomic.py` and `tests/migration_faults.py` hold the fault-injection pattern. Not needed here.

## Architecture Patterns

### Data flow
```
Remove click -> POST /api/instance/remove/{app}/{name}
   [search_lock] existence check -> build new settings -> atomic TOML write
        write fails -> "instance kept" error (nothing changed)
        write ok -> swap live settings -> remove scheduler job
                 -> close_out_removed_instance_searches(db, app, stable_id)   (isolated try/except)
                 -> pop client/state/tag cache
   [outside lock] close client -> success redirect

Startup: init_db (migrations) -> import state.json -> ensure_cutover_recorded
      -> close_out_orphaned_pending_searches(db, configured {(App, id)})  (isolated, non-fatal)
      -> create clients -> schedule jobs -> scheduler.start()

Scheduled cycle (per instance, search_lock held):
   search cycle inserts rows with cfg.id
   run_tracking_check -> get_trackable_entries(instance_stable_id=cfg.id)   [all 3 apps]
        -> only this ID's pending, non-Legacy rows; orphan/closed rows never selected

History/rail: get_search_history/get_recent_searches -> templates
   outcome 'instance_removed' -> gray "Instance removed" badge (never is_legacy)
```

### Recommended structure
- `triggarr/db.py`: constants + `_PENDING_SQL`/`_NOT_PENDING_SQL`; `close_out_removed_instance_searches`; `close_out_orphaned_pending_searches`; stats exclusion.
- `triggarr/tracking.py`: Radarr/Lidarr stable-ID selection + empty-ID guard.
- `triggarr/web/routes.py`: close-out step in `remove_instance`.
- `triggarr/search/scheduler.py`: sweep call in lifespan.
- Templates: `partials/history_results.html`, `partials/activity_rail.html`.
- Planning docs: `.planning/REQUIREMENTS.md` RMINST-01..04 wording (line 48-51) and Traceability stays; `.planning/ROADMAP.md` Phase 90 goal/criteria (lines 242 and 298-306) widened to all three apps, per `docs/PLANNING-FORMAT.md`; keep STATE.md `last_updated` refreshed when edited. Also `CHANGELOG.md` entry (there is a `tests/test_changelog.py`; check its rules before adding an entry).

### Anti-Patterns to Avoid
- Selecting or closing rows by display name anywhere in this phase (D-00c). Display name is stored for D-05 display only.
- Adding a seventh copy of the pending rule.
- Using `get_enabled_instances` for the configured-ID set.
- Running the sweep before the cutover is recorded.
- Closing Legacy rows ("must never touch pre-cutover Legacy rows").
- Using `instance_stable_id = NULL` in SQL (never matches); use `IS NULL`/`IS ?`.
- Letting an exception from close-out affect the removal response (D-00b), or leaving an uncommitted transaction on the shared connection.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| "Is this row pending / legacy" | New inline SQL strings | The shared `_PENDING_SQL`/`_LEGACY_PENDING_SQL` | Six divergent copies is the bug being retired |
| Atomic multi-row write on the shared connection | Ad-hoc execute/commit | The `update_outcome_and_stats` pattern (try, commit, `except Exception: rollback; log; raise`) | Shared-connection open-transaction hazard (R-08) |
| Secret redaction in logs | Manual masking | Existing loguru redacting sink; log `{exc_type}: {exc}` like neighbouring steps | Project rule |
| Stable ID generation | Anything | Existing `InstanceConfig.id` | Already backfilled and persisted |

## Common Pitfalls

### P1: Sweep before cutover destroys Legacy rows
**What goes wrong:** `_LEGACY_MAX_ID_SQL` is 0 until `ensure_cutover_recorded` runs, so every Sonarr pending row looks non-Legacy. **Avoid:** sweep strictly after line 728. **Detect:** test that builds a v10 DB with Sonarr pending rows and a recorded cutover, runs the lifespan, and asserts Legacy rows are still `searched` and `is_legacy`; plus a lifespan-order test.

### P2: Disabled instance loses its pending rows
**Avoid:** configured set from all instances. **Detect:** test with an `enabled=False` instance with pending rows; untouched after the sweep.

### P3: NULL-ID rows become immortal pending rows
After the D-01 selection change they are selected by no one and never pruned. **Avoid:** sweep closes NULL-ID pending non-Legacy rows (section 5). **Detect:** NULL-ID Radarr and Lidarr pending rows (with and without `item_id`) closed at startup; NULL-ID Sonarr pre-cutover row stays Legacy.

### P4: Stats denominators
`outcome != 'failed'` counts a closed row as a miss. **Avoid:** explicit exclusion (D-06). **Detect:** grab rate with N grabbed + M closed rows equals N/N, and the historical flag is unaffected.

### P5: Old tests silently assert the defect
The five Radarr/Lidarr tests in section 4 assert the old selection. Planner must schedule their rewrite in the same task as the selection change (TDD: write the new failing tests first, then flip the code).

### P6: App-name casing
Route `app_name` is lowercase; DB `app` is title-case. A close-out by `app_name` silently matches nothing. **Detect:** close-out test through the real route (not just the db function) asserting the rows changed.

### P7: Stale job after removal
A job waiting on `search_lock` can insert rows for the removed ID after close-out (section 6). Sweep repairs; add nothing else.

### P8: Per-instance lock-free read races
History/rail reads are lock-free; no new issue.

### P9: Planning-file format
Editing REQUIREMENTS/ROADMAP/STATE must follow `docs/PLANNING-FORMAT.md` (status wording; avoid words that flip the Roadmaps page status, see memory note on keywords such as "await"/"complete"). No docs-only PR; planning rides in the phase PR.

## Code Examples

Close-out function (pattern follows `update_outcome_and_stats`, db.py 1306-1376):
```python
async def close_out_removed_instance_searches(
    db: aiosqlite.Connection, *, app: str, instance_stable_id: str, instance_id: str,
) -> int:
    if not instance_stable_id:
        return 0  # never close by display name (D-00c)
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        cursor = await db.execute(
            "UPDATE search_history SET outcome = ?, detail = ?, resolved_at = ? "
            f"WHERE app = ? AND instance_stable_id = ? AND {_PENDING_SQL} AND NOT {_LEGACY_PENDING_SQL}",
            (OUTCOME_INSTANCE_REMOVED, "instance removed", now, app, instance_stable_id),
        )
        await db.commit()
    except Exception:
        await db.rollback()  # guarded like update_outcome_and_stats
        raise
    logger.info("Closed out {n} pending search(es) of removed {app}/{inst}", n=cursor.rowcount, app=app, inst=instance_id)
    return cursor.rowcount
```
Template badge (history row), consistent with the Legacy branch:
```jinja
{% elif entry.outcome == 'instance_removed' %}bg-gray-500/20 text-gray-400
...
{% elif entry.outcome == 'instance_removed' %}title="This instance was removed before the search finished; it will not be checked again."
...
{% if entry.is_legacy %}Legacy — tracking discontinued{% elif entry.outcome == 'instance_removed' %}Instance removed{% else %}...{% endif %}
```
`[VERIFIED: patterns from codebase; new code illustrative]`

## State of the Art

| Old | New | Impact |
|-----|-----|--------|
| Radarr/Lidarr pending selected by name (`tracking.py:123`) | Stable-ID selection like Sonarr | Rename-safe and reuse-safe; rewrites 5 tests |
| Pending rule copied 6x with 2 NULL treatments | One predicate, COALESCE | Fixes latent cap/trackable vs prune inconsistency |

## Runtime State Inventory (migration-like data fix)

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Existing pending rows of removed instances in `search_history` (stable ID unconfigured, or NULL) | Data close-out by startup sweep (data migration, not code edit) |
| Live service config | None; the removed server is never contacted (D-10) | None |
| OS-registered state | None | None |
| Secrets/env vars | None | None |
| Build artifacts | None | None |
Also: `lifetime_stats` and `grab_ownership` of removed instances are intentionally left alone (D-09; Discretion item), verified as not read by any selection path for a new ID.

## Environment Availability

Step 2.6 skipped: code/config/template changes only. Tests need `uv` and Python (already used: `uv run pytest tests/test_db.py tests/test_tracking.py tests/test_activity_rail.py -x -q` currently passes, 185 tests, about 4 s). `[VERIFIED: ran in this session]`

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (`asyncio_mode=auto`), ruff |
| Config file | `pyproject.toml` |
| Quick run command | `uv run pytest tests/test_db.py tests/test_tracking.py tests/test_scheduler.py tests/test_activity_rail.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/` |
| TDD | on: write each test first and watch it fail on current code |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RMINST-01 | Close-out turns pending (searched/partial) rows of a stable ID into `instance_removed` with detail/resolved_at; other IDs, resolved rows, Legacy rows untouched | unit (db) | `uv run pytest tests/test_db.py -k instance_removed -x` | new tests in existing file |
| RMINST-01 | `remove_instance` route closes rows for all three apps; failing close-out (patched to raise) still returns normal success and still removes job/client/state/tag cache; logs one error | integration | `uv run pytest tests/test_web.py -k remove_instance -x` | new tests; fixture `multi_instance_app` (give instances ids) |
| RMINST-01 | History badge text/tooltip, never "Legacy"; filter option present and filters; rail pill | template/route | `uv run pytest tests/test_web.py tests/test_activity_rail.py -k "instance_removed" -x` | new tests |
| RMINST-02 | Closed rows excluded from cap (`PendingCapExceeded` not raised at cap with only closed rows); not trackable; grab rate unchanged by closed rows; historical flag unchanged | unit | `uv run pytest tests/test_db.py -k "instance_removed" -x` | new |
| RMINST-02 | Shared predicate: NULL outcome row counted by cap, trackable and never pruned; `instance_removed` not pending; prune ages out closed rows (D-08) | unit | `uv run pytest tests/test_db.py -k pending_predicate -x` | new |
| RMINST-03 | For each of Sonarr, Radarr, Lidarr: new same-name instance (new stable ID) tracking check never selects/credits old row or old lifetime; real-client variants for Radarr/Lidarr (existing MockTransport pattern) | unit/integration | `uv run pytest tests/test_tracking.py -k "name_reuse" -x` | rewrite 5 existing + add Sonarr/closed-row cases |
| RMINST-03 | Radarr/Lidarr empty stable ID refuses to track (errors counted, no selection) | unit | `uv run pytest tests/test_tracking.py -k empty_stable_id -x` | new |
| RMINST-03/D-09 | `get_dashboard_stats(app, instance_stable_id=new)` shows zero/None for each app after reuse | unit | `uv run pytest tests/test_db.py -k name_reuse_stats -x` | new |
| RMINST-04 | Sweep: orphan stable ID and NULL-ID (Radarr/Lidarr) pending rows closed; configured (including disabled) and Legacy rows untouched; idempotent second run closes 0; empty-config guard; one info line | unit | `uv run pytest tests/test_db.py -k orphan_sweep -x` | new |
| RMINST-04 | Lifespan runs the sweep after cutover (order) and before scheduler start; sweep failure does not stop startup; cancellation still reaches Phase 89 cleanup | integration | `uv run pytest tests/test_scheduler.py -k "sweep or lifespan" -x` | new; model on `test_lifespan_records_attribution_cutover_once` (scheduler tests patch `AsyncIOScheduler` with `_FakeScheduler`) |

### Sampling Rate
- Per task commit: the quick run command above (about 5 s).
- Per wave merge: full suite plus ruff.
- Phase gate: full suite green; Codex/vibe-check per CLAUDE.md review workflow.

### Wave 0 Gaps
- None for framework. Fixture helpers to add: a small test helper that inserts rows with chosen `outcome`/`instance_stable_id`/`item_id` and a cutover row (`_insert_cutover` exists in `tests/test_db.py:1930`; `_insert_entry` in `tests/test_tracking.py:64`). Rewrite of the five old tracking tests is a precondition of the selection change.

## Security Domain

| ASVS Category | Applies | Control |
|---------------|---------|---------|
| V2/V3 | no | no auth/session change |
| V4 Access Control | yes | Identity isolation by stable ID (D-00c): closing/selecting is keyed on the row's own ID, never display name; route already behind auth middleware |
| V5 Input Validation | yes | All SQL parameterized (new queries use `?`); `app_name` validated against `APP_TYPES` in the route; stable ID comes from server-side settings, never from the request; the `outcome` filter is already parameterized |
| V6 Cryptography | no | n/a |
| V7 Logging | yes | Log lines contain app, instance name, counts only; exception text via loguru redacting sink (URLs with userinfo are the known gap in the notes; log `exc_type` plus the same sanitized form the neighbouring steps use) |

Threats: cross-instance misattribution (Tampering/Elevation of data ownership) mitigated by stable-ID selection; SQL injection mitigated by parameters (no f-string interpolation of user data; only constants are f-string-formatted); information disclosure via History/tooltips limited to fixed strings.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Close NULL-`instance_stable_id` pending non-Legacy rows (including the item_id-less `state.json`-import rows) in the startup sweep and label them "Instance removed" | 5, 7 | Slightly inexact label for imported rows; alternative is limiting to `item_id IS NOT NULL` |
| A2 | Sweep failure is logged and startup continues (unlike the cutover) | 7 | If owner wants fail-fast, wrap differently; safety is unaffected because selection is by ID |
| A3 | Skip sweep when zero configured instances (mis-mount guard) | 7 | Pre-release orphans stay pending until an instance is configured; they are never selected anyway |
| A4 | `detail` text "instance removed" and `resolved_at` set on close-out | 7 | Cosmetic; tests will pin whatever is chosen |
| A5 | SQLite `IS ?` handles NULL group equality as described | 7 | Verified implicitly by the planned test with NULL-ID rows; use two statements if not |

## Open Questions

1. **NULL-ID handling label (A1).** Recommendation: close all non-Legacy NULL-ID pending rows; the planner records it as the evidence-based decision D-11 asked for.
2. **Should `remove_instance` also re-check the instance inside `job()` after taking the lock (P7)?** Out of scope; note in code comment and optionally backlog.
3. **CHANGELOG entry format** (`tests/test_changelog.py` constraints) to be read by the planner before adding a user-facing note about the Radarr/Lidarr selection change and the startup sweep.

## Sources

### Primary (HIGH confidence, this repo at HEAD 44695052)
- `triggarr/db.py` (predicates, prune, cap, trackable, stats, migrations v1-v10, `update_outcome_and_stats`)
- `triggarr/tracking.py` (selection and crediting)
- `triggarr/web/routes.py` (`remove_instance`, history routes, stats route)
- `triggarr/search/scheduler.py` (lifespan, job), `triggarr/search/engine.py` (insert call sites), `triggarr/attribution.py` (cutover)
- `triggarr/templates/partials/history_results.html`, `activity_rail.html`
- `tests/test_tracking.py`, `tests/test_db.py`, `tests/test_web.py`, `tests/test_scheduler.py`
- `.planning/phases/90-.../90-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `docs/PLANNING-FORMAT.md`, `CLAUDE.md`

### Secondary / not re-fetched
- SQLite NULL comparison semantics (A5), from training knowledge.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH (no new stack)
- Architecture: HIGH (every integration point read in source)
- Pitfalls: HIGH for P1-P6 (derived from code); MEDIUM for P7 (read, not reproduced)

**Research date:** 2026-11-18
**Valid until:** until `db.py`, `tracking.py`, `remove_instance` or the lifespan change (a Phase 91 delivery-confidence change touches tracking/engine, so re-check line numbers if Phase 91 lands first).
