---
phase: 90-removed-instance-pending-search-lifecycle
verified: 2026-11-19T23:45:00Z
verified_commit: 453e3fa4 (last code commit 22b99325)
status: human_needed
score: 12/12 must-haves verified (4 roadmap success criteria + 8 plan must-have groups)
has_blocking_gaps: false
overrides_applied: 0
human_verification:
  - test: "In a real browser, open History and the dashboard activity rail with at least one 'Instance removed' row and one Legacy row on screen; hover the 'Instance removed' badge in both places."
    expected: "A gray 'Instance removed' badge that reads as a different thing from 'Legacy — tracking discontinued'; hovering shows 'This instance was removed before the search finished; it will not be checked again.'; the History outcome filter has an 'Instance removed' option that narrows the list to those rows."
    why_human: "Visual judgment and real hover behavior. The markup, text and title attribute are test-pinned, but how it reads next to Legacy cannot be judged from code (90-VALIDATION.md manual check, 90-04 Task 2 human-check)."
  - test: "Against a live Radarr, Sonarr or Lidarr: let an instance record pending searches, remove it (once with the Remove action, once by leaving it out of Save Settings), then add a new instance under the same name and let one search and tracking cycle run."
    expected: "The old searches show 'Instance removed' in History under the original instance name; the new instance's card shows none of the old lifetime totals; later grabs on the server for the old items do not change the old rows or credit the new instance."
    why_human: "Needs a live *arr server and the real scheduler; the automated suite uses fake clients and a temporary database."
  - test: "Start the new build once on a copy of the production database and read the startup log."
    expected: "One INFO line per app with the number of pending searches being closed as Instance removed (or none when there is nothing to close), then normal startup; a second start closes nothing."
    why_human: "The one-time relabel on upgrade depends on the real production data (owner ruling: per-app count log plus release note, no pre-sweep backup)."
---

# Phase 90: Removed-Instance Pending-Search Lifecycle — Verification Report

**Phase Goal:** A removed instance's leftover pending searches (Sonarr, Radarr or Lidarr) get a defined, visible end state, and a reused instance name never inherits them.
**Verified:** 2026-11-19T23:45:00Z, at HEAD `453e3fa4` (last code commit `22b99325`)
**Status:** human_needed
**Re-verification:** No — initial verification

Verified against the code at HEAD, not against the SUMMARY text. The review fix commits made after the SUMMARYs (`1a9039bd`, `3aa2cad6`, `22b99325`, `1744f43a`, `3e778629`) are all present in the code read below.

## Goal Achievement

### Observable Truths — roadmap success criteria

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | When a Sonarr, Radarr or Lidarr instance is removed, its still-pending searches get the final outcome "Instance removed," stay visible in History, and read as distinct from "Legacy." | VERIFIED (visual part: human) | `remove_instance` (`triggarr/web/routes.py:1371-1404`) and `save_settings` (`routes.py:889-929`) call `close_out_removed_instance_searches` after the settings write, keyed on `app_name.title()` and the stable ID read from server-side settings. The UPDATE (`triggarr/db.py:1590-1593`) sets `outcome='instance_removed'` and `resolved_at`. Badge, tooltip and filter option: `history_results.html:82,102,148,155,160`, `activity_rail.html:34,81-82`, each placed after the `is_legacy` branch. My own probe on a temporary database closed 4 of 4 pending rows (searched, partial, NULL outcome) for each of the three apps; the rows kept their instance name and none was reported `is_legacy`. |
| 2 | "Instance removed" searches no longer count toward the pending-search limit and are never checked or credited again. | VERIFIED | One pending rule (`db.py:824-829`) used by both cap queries (`db.py:920-931`), both prune predicates (`db.py:974-977`), `get_trackable_entries` (`db.py:1202`) and the Legacy rule (`db.py:845`). `instance_removed` is outside `PENDING_OUTCOMES`. Probe: cap reached before close-out, a new insert accepted after; a second close-out closed 0; `get_trackable_entries` for the old stable ID returned 0 rows. Grab rate and the historical flag exclude the outcome (`db.py:1811-1812`, `1892-1893`). |
| 3 | A new instance of any app added under the same name never selects, displays as its own in-progress work, or receives credit for the removed instance's searches. | VERIFIED | Radarr/Lidarr now select by stable ID (`triggarr/tracking.py:135`), Sonarr already did (`tracking.py:564`); credit uses the instance's own stable ID (`tracking.py:210`); an empty stable ID refuses to track (`tracking.py:121-133`). Per-instance stats views pass `app` + stable ID (`routes.py:1761`). Queued work is turned away by identity: `_revalidate_queued_instance` (`triggarr/search/scheduler.py:146-177`) is the first statement inside the lock in the scheduled job (`scheduler.py:223`) and in `search_now` before the rate-limit stamp (`routes.py:1468`). Probe: a same-name instance with a new ID tracked 1 row (its own) with the old rows untouched. |
| 4 | Pending searches already orphaned by a removal before this release reach the same "Instance removed" outcome at the next upgrade or startup. | VERIFIED | `create_lifespan` calls `close_out_orphaned_pending_searches` after `ensure_cutover_recorded` and before clients are built or the scheduler starts (`scheduler.py:784-822`, scheduler start at `:949`), with every configured instance, disabled ones included. No guard on an empty set (`db.py:1640-1670`). Probe: unconfigured-ID row and NULL-ID row closed (2), configured rows kept (3), second run closed 0, zero-instance run closed the rest, the pre-cutover Sonarr row stayed `searched` (Legacy). Per-app INFO count line before the writes: `db.py:1656-1661`. |

### Observable Truths — plan must-haves (grouped by plan)

| # | Plan | Truths | Status | Evidence |
|---|------|--------|--------|----------|
| 5 | 90-01 shared pending rule, finished outcome | 6 | VERIFIED | Constants and SQL fragments at `db.py:824-829`; no other copy of the rule found in `triggarr/` (grep for `IN ('searched'` and equivalents returned only the unrelated v8 migration and the close-out detail CASE). NULL outcome is pending by `COALESCE` and is handed to tracking as `searched` (`db.py:1225-1227`, fix `1a9039bd`). |
| 6 | 90-02 close-out and orphan sweep | 9 | VERIFIED, one recorded deviation | Both functions at `db.py:1566-1682`; rollback verified or connection retired (`db.py:1461-1520`); replacement on the recorded path (`db.py:795`, `1523-1551`). **Deviation from the plan's letter:** truth 1 says every closed row gets detail `instance removed`. After review fixes `3aa2cad6` and `22b99325` a `partial` row keeps its grab count: `partial: 2/5 episodes (instance removed)`; every other row gets the plain note (`db.py:1560-1563`, confirmed by the probe). This is the WR-01 fix recorded in 90-REVIEW.md "Dispositions"; it preserves data and meets the truth's intent. |
| 7 | 90-03 Radarr/Lidarr select by stable ID | 6 | VERIFIED | `tracking.py:121-135,205-211`. `instance_id` mode survives only in the refuse-to-track count (review IN-01, accepted). |
| 8 | 90-04 badge, tooltip, filter | 5 | VERIFIED in markup; visual check is human | Template lines listed under truth 1. |
| 9 | 90-05 removal routes close out after the write | 9 | VERIFIED | Close-out is the last step inside `search_lock` in both routes; failure is logged with `_sanitize_exc` only (`routes.py:1392-1397`, `912-917`) and does not change the response; `_replace_retired_db` runs before the lock is released (`routes.py:1402`, `922`); a no-ID instance is skipped with a warning (`routes.py:1371-1376`). |
| 10 | 90-06 startup sweep | 8 | VERIFIED | `scheduler.py:784-822`; non-fatal `except Exception` with sanitized log; retired connection replaced before `app.state.db` is assigned (`:821-822`, `:846`); a replacement error is not caught. |
| 11 | 90-07 queued work turned away | 6 | VERIFIED | `scheduler.py:146-177,216-232`; `routes.py:1461-1478`. Only these two paths run a search cycle or a tracking check (`_run_one_cycle` has two callers, `run_tracking_check` one). |
| 12 | 90-08 end-to-end tests, wording, backlog | 5 | VERIFIED | `tests/test_removed_instance_lifecycle.py` has 7 tests, parametrized over the three apps; REQUIREMENTS.md lines 48-51 and ROADMAP.md Phase 90 goal and criteria carry the three-app wording; RMINST checkboxes are still unticked; `.planning/backlog/MAINTENANCE.md` lines 13-16, 85, 88 hold the resolved notes and the owner-decided leftovers. |

**Score:** 12/12 (4 roadmap success criteria + 8 plan groups covering 54 plan truths)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `triggarr/db.py` | Pending rule, outcome constant, both close-out functions, rollback/retire/replace | VERIFIED | +339 lines in the phase diff; used by routes, scheduler and tracking |
| `triggarr/tracking.py` | Stable-ID selection for Radarr/Lidarr | VERIFIED | Called from the scheduled job with `instance_config.id` |
| `triggarr/web/routes.py` | Close-out in `remove_instance` and `save_settings`; revalidation in `search_now` | VERIFIED | Imported from `triggarr.db` and `triggarr.search.scheduler` and called |
| `triggarr/search/scheduler.py` | Startup sweep; `_revalidate_queued_instance` | VERIFIED | Both wired into the lifespan and the job |
| `triggarr/templates/partials/history_results.html` | Badge, tooltip, filter option | VERIFIED | Rendered by the History routes (`routes.py:574,621`) |
| `triggarr/templates/partials/activity_rail.html` | Dot and pill with tooltip | VERIFIED | Fed by `get_recent_searches` (`routes.py:1681`) |
| `tests/test_removed_instance_lifecycle.py` | Three-app lifecycle and D-09 tests | VERIFIED | 7 tests, no skip or xfail markers |
| Named tests in `tests/test_db.py`, `test_tracking.py`, `test_attribution_disclosure.py`, `test_web.py`, `test_scheduler.py` | The nine `contains:` test names from the plan frontmatter | VERIFIED | All nine found by name |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `_LEGACY_PENDING_SQL` | `_PENDING_SQL` | string composition, `db.py:845` | WIRED |
| `get_dashboard_stats` rate and flag queries | `OUTCOME_INSTANCE_REMOVED` | explicit exclusion, `db.py:1812,1893` | WIRED |
| close-out UPDATE | pending and not-Legacy predicates | `WHERE app = ? AND instance_stable_id = ?`, `db.py:1592` | WIRED |
| orphan sweep | configured set | Python decision per group, `IS ?` update, `db.py:1650-1667` | WIRED |
| both close-out functions | `_rollback_through_cancellation` → `_retire_connection` | `except BaseException`, `db.py:1597,1671,1510` | WIRED |
| `init_db` | `replace_retired_connection` | `_CONNECTION_PATHS`, `db.py:795,1537` | WIRED |
| `run_tracking_check` | `get_trackable_entries` / `update_outcome_and_stats` | `instance_stable_id=instance_stable_id`, `tracking.py:135,210` | WIRED |
| `remove_instance`, `save_settings` | `close_out_removed_instance_searches`, `_replace_retired_db`, `_sanitize_exc` | `routes.py:1379-1402`, `899-922` | WIRED |
| `create_lifespan` | `close_out_orphaned_pending_searches`, `replace_retired_connection` | `scheduler.py:809,822` | WIRED |
| job and `search_now` | `_revalidate_queued_instance` | first statement inside the lock, `scheduler.py:223`, `routes.py:1468` | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|----------|------|--------|-----------|--------|
| `history_results.html` | `entry.outcome`, `entry.is_legacy`, `entry.instance_id` | `get_search_history` SQL over `search_history` (`db.py:1128-1134`) | Yes | FLOWING |
| `activity_rail.html` | same fields | `get_recent_searches` SQL (`db.py:1025-1037`) | Yes | FLOWING |

Existing live instances are not swept by mistake: search rows of all three apps are already written with `instance_stable_id=instance_config.id` (`triggarr/search/engine.py`, unchanged in this phase), so only rows with an unconfigured or missing ID are closed at startup.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite | `uv run pytest tests/ -x -q -p no:cacheprovider` | 3520 passed, 1 skipped, 38 warnings in 197.57s | PASS |
| Lint | `uv run ruff check triggarr/ tests/` | All checks passed | PASS |
| Lifecycle on a real migrated temporary database, three apps (own script, not the phase's tests) | close-out, repeat close-out, same-name reuse with tracking, History filter, orphan sweep with configured set, repeat, zero-instance sweep | Results as quoted in the truths table; no unexpected value | PASS |

### Probe Execution

Not applicable: the phase declares no `probe-*.sh` scripts.

### Requirements Coverage

| Requirement | Source plans | Description | Status | Evidence |
|-------------|--------------|-------------|--------|----------|
| RMINST-01 | 90-02, 90-04, 90-05, 90-07, 90-08 | Removed instance's pending searches end as "Instance removed", stay in History, distinct from Legacy | SATISFIED (visual confirmation pending) | Truth 1 |
| RMINST-02 | 90-01, 90-03, 90-05, 90-07, 90-08 | Not counted toward the pending limit; never checked or credited again | SATISFIED | Truth 2 |
| RMINST-03 | 90-03, 90-04, 90-07, 90-08 | A reused name never selects, displays as in-progress, or is credited | SATISFIED | Truth 3 |
| RMINST-04 | 90-02, 90-06, 90-08 | Earlier orphans reach the same outcome at upgrade or startup | SATISFIED | Truth 4 |

All four IDs that REQUIREMENTS.md maps to Phase 90 are claimed by at least one plan. No orphaned requirement.

### Anti-Patterns Found

No `TBD`, `FIXME`, `XXX`, `TODO`, `HACK` or placeholder marker in any file changed by the phase. No stub pattern found.

Informational, not gaps:

| Item | Where | Severity | Note |
|------|-------|----------|------|
| Queued count refresh is not revalidated | `refresh_counts`, `routes.py:1583` | Info | It reads the client before the lock like `search_now` did, but records no search and runs no tracking, so it cannot create or credit a pending search. Outside the phase goal. |
| Review leftovers | `.planning/backlog/MAINTENANCE.md:14-16` | Info | Already recorded under the owner's stopping rule. |

### Owner decisions — recorded, not gaps

From 90-REVIEW.md "Dispositions": D-06 stands (part-done searches of a removed instance leave grab rate, lifetime totals keep the grabs); SA-02 dismissed (hand-edited instance ids are unsupported); A1 kept (item-less rows imported from `state.json` are closed at startup); per-app count log plus a release note for the one-time relabel, no pre-sweep backup. The count log is in the code (`db.py:1656-1661`). The release note itself is release work and is not part of this phase's code; the material for it is in 90-08-SUMMARY.md.

### Human Verification Required

#### 1. Badge and tooltip in a real browser

**Test:** Open History and the dashboard activity rail with an "Instance removed" row and a Legacy row visible; hover the badge in both places; use the History outcome filter.
**Expected:** Gray "Instance removed" badge that reads as different from "Legacy — tracking discontinued"; the tooltip text appears on hover; the filter narrows to those rows.
**Why human:** Visual judgment and real hover behavior.

#### 2. Removal and same-name reuse against a live server

**Test:** With a live Radarr, Sonarr or Lidarr, record pending searches, remove the instance (Remove action, and separately Save Settings omission), add a new instance under the same name, let a cycle run.
**Expected:** Old searches read "Instance removed" under the original name; the new instance shows none of the old totals and is never credited for old items.
**Why human:** Needs a live *arr server and the real scheduler.

#### 3. First start on a copy of production data

**Test:** Start the build once on a copy of the production database and read the log; start it again.
**Expected:** Per-app INFO count lines for what is being closed, then normal startup; the second start closes nothing.
**Why human:** Depends on real production data.

### Gaps Summary

No gaps. Every roadmap success criterion and every plan must-have is met in the code at HEAD, the full suite and ruff are green, and an independent probe on a real database reproduced the lifecycle for all three apps. Three items remain that only a person can confirm (browser appearance, a live server run, the first start on production data), so the status is human_needed, not passed.

---

_Verified: 2026-11-19T23:45:00Z_
_Verifier: Claude (bm-verifier)_
