---
phase: 81-correct-sonarr-grab-attribution
plan: 05
subsystem: database
tags: [sqlite, aiosqlite, jinja2, dashboard, attribution, disclosure]

# Dependency graph
requires:
  - phase: 81-01
    provides: "InstanceConfig.id -- the stable per-instance identifier this plan's partial_stats_row lookup and per-instance scoping key everything by"
  - phase: 81-03
    provides: "_LEGACY_PENDING_SQL/_LEGACY_MAX_ID_SQL id-cutoff predicate, search_history.instance_stable_id and lifetime_stats.instance_stable_id columns, attribution_cutover and sonarr_instance_pre_fix tables, ensure_cutover_recorded's two persisted pre-fix facts, get_search_history/get_recent_searches' is_legacy flag"
provides:
  - "get_dashboard_stats(db, *, instance_id=, app=, instance_stable_id=): app + stable-ID scoping (mutually exclusive with instance_id), D-07 legacy-pending exclusion from both per-app and overall grab rates, three per-metric *_includes_historical flags (D-06)"
  - "triggarr.attribution.get_attribution_disclosure(db, *, view_app=, sonarr_stable_id=): show_cutover_note / cutover_date / sonarr_lifetime_includes_historical from two independent persisted facts (R4), gated to radarr/lidarr views (D-02)"
  - "partial_stats_row resolves the selected instance's InstanceConfig.id from settings (never the request) and passes app + instance_stable_id to both get_dashboard_stats and get_attribution_disclosure, rejecting any selector that resolves to an instance without a stable id"
  - "stats_row.html: cutover note under the stats grid inside #stats-row, 'Lifetime -- includes historical estimates' beside the Series total, 'Includes historical estimates' beside the overall rate / Sonarr bar / avg time-to-grab, each conditional on its own flag"
  - "history_results.html / activity_rail.html: 'Legacy -- tracking discontinued' as the first branch of the outcome badge/text and styling chain whenever entry.is_legacy is set"
affects: [81-06, 81-07, 81-08, 81-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Scope-argument validation via a single guard block: app/instance_stable_id must arrive together, both non-empty, and never combined with the legacy instance_id parameter -- raises ValueError before any query runs"
    - "Per-metric historical-contribution flags as EXISTS queries sharing the same WHERE clause (minus the metric-specific condition) as the metric they flag, so a flag can never diverge from what the metric itself actually counts"
    - "Two independent persisted booleans (has_pre_fix_data vs. lifetime_includes_pre_fix) read straight through with no derived combination logic -- the note and the lifetime label can disagree by design (R4)"

key-files:
  created:
    - tests/test_attribution_disclosure.py
  modified:
    - triggarr/db.py
    - triggarr/attribution.py
    - triggarr/web/routes.py
    - triggarr/templates/partials/stats_row.html
    - triggarr/templates/partials/history_results.html
    - triggarr/templates/partials/activity_rail.html
    - triggarr/static/css/output.css
    - tests/test_db.py
    - tests/test_attribution.py
    - tests/test_web.py

key-decisions:
  - "get_dashboard_stats' three *_includes_historical flags are computed via dedicated EXISTS queries reusing the effectiveness/TTG query's own WHERE clause plus 'app=Sonarr AND id <= legacy_max_history_id' -- guarantees a flag only ever reflects rows the metric it labels actually counted, never a coincidental match elsewhere"
  - "sonarr_rate_includes_historical and overall_rate_includes_historical share one underlying flag query (the overall rate's only possible Sonarr-attributable inputs are the same rows the Sonarr-specific query already found) -- documented inline rather than duplicating the query"
  - "partial_stats_row now rejects (400) any resolved instance whose InstanceConfig.id is empty, instead of silently falling back to name-only stats -- an empty stable id would otherwise match unassociated ('') rows, exactly the contamination R3/S1 exist to prevent"
  - "stats_row.html's outer #stats-row div keeps its hx-* polling attributes and becomes a plain wrapper; a new inner div carries the grid classes so the cutover note can sit after the grid but still inside the polled element (no duplicate note across refreshes)"

patterns-established:
  - "Pattern: any future per-metric 'this number includes historical/legacy data' flag should follow get_dashboard_stats' EXISTS-sharing-the-metric's-own-WHERE approach rather than a single coarse 'any historical data exists' boolean"

requirements-completed: [ATTR-05, ATTR-06]

# Metrics
duration: ~17min
completed: 2026-10-19
---

# Phase 81 Plan 05: Sonarr Attribution Stats Disclosure & Legacy Labeling Summary

**get_dashboard_stats gains app+stable-ID scoping and D-07 legacy-rate exclusion with three per-metric historical flags; get_attribution_disclosure surfaces two independently-persisted cutover facts through a rewired partial_stats_row and a restructured stats_row.html; History and the activity rail now label frozen legacy rows "Legacy — tracking discontinued".**

## Performance

- **Duration:** ~17 min
- **Completed:** 2026-10-19
- **Tasks:** 3 (all complete)
- **Files modified:** 11 (10 production/test files modified, 1 new test file)

## Accomplishments

- **Task 1 — `get_dashboard_stats` scoping and D-06/D-07:** New `app`/`instance_stable_id` keyword pair (mutually exclusive with the legacy `instance_id`) scopes the effectiveness query, the lifetime_stats query and two new per-metric flag queries by one identity. Frozen legacy-pending Sonarr rows (`_LEGACY_PENDING_SQL`) are excluded from both the per-app and overall grab-rate denominators — resolved historical rows stay in. Three new keys (`overall_rate_includes_historical`, `sonarr_rate_includes_historical`, `avg_time_to_grab_includes_historical`) each reflect only that metric's actual pre-fix Sonarr inputs in the current view, proven against a Radarr+Sonarr instance pair sharing the display name "Default" and against a renamed/reused stable ID.
- **Task 2 — Cutover note and lifetime label:** New `triggarr.attribution.get_attribution_disclosure` reads the note (`any_pre_fix_sonarr_data`/`has_pre_fix_data`) and the lifetime label (`pre_fix_sonarr_lifetime`/`lifetime_includes_pre_fix`) as two independent persisted facts — a legacy-pending-only instance gets the note but never the label (R4). `partial_stats_row` now looks up the selected instance's `InstanceConfig.id` from settings (never the request), uses it to scope both `get_dashboard_stats` and the disclosure, and rejects (400) any instance — explicit `app/name` or legacy bare name — that resolves without a stable id. `stats_row.html`'s outer `#stats-row` wrapper now holds the polling attributes around an inner grid plus the note, so a 30s refresh never duplicates it; the three rate/TTG labels read "Includes historical estimates" (never "Lifetime"), and the Series card alone reads "Lifetime — includes historical estimates".
- **Task 3 — Legacy row labeling:** `history_results.html`'s outcome badge and `activity_rail.html`'s timeline dot + outcome pill both gained `entry.is_legacy` as their first branch, rendering "Legacy — tracking discontinued" in existing gray styling. Every other branch, the stored outcome, and History's page structure (no divider or banner) are unchanged.

## Task Commits

Each task followed RED (test) then GREEN (feat):

1. **Task 1: `get_dashboard_stats` scoping, legacy exclusion, historical flags**
   - `0411513` test(81-05): add failing dashboard legacy-exclusion and historical-flag tests
   - `b30c629` feat(81-05): exclude legacy pending rows from grab rates and flag historical inputs
2. **Task 2: Cutover note and lifetime label; stats row rendering**
   - `df2c47a` test(81-05): add failing stats disclosure tests
   - `14f705a` feat(81-05): attribution cutover note and historical-estimate labels
3. **Task 3: "Legacy — tracking discontinued" in History and the activity rail**
   - `a6f89ba` test(81-05): add failing legacy badge tests
   - `14ec598` feat(81-05): label frozen legacy rows in history views

## Files Created/Modified

- `triggarr/db.py` - `get_dashboard_stats` signature + scope-argument validation, D-07 legacy exclusion in the effectiveness query, two new EXISTS-based flag queries, three new return keys
- `triggarr/attribution.py` - new `get_attribution_disclosure(db, *, view_app=, sonarr_stable_id=)`
- `triggarr/web/routes.py` - `dashboard()` and `partial_stats_row()` both call `get_attribution_disclosure`; `partial_stats_row` resolves `cfg.id` from settings for both the stats call and the disclosure call, rejecting a missing stable id
- `triggarr/templates/partials/stats_row.html` - restructured wrapper (polling attrs outside the grid), cutover note, three "Includes historical estimates" labels, one "Lifetime — includes historical estimates" label
- `triggarr/templates/partials/history_results.html` - `entry.is_legacy` first branch in the outcome badge class/title/text chain
- `triggarr/templates/partials/activity_rail.html` - `entry.is_legacy` first branch in both the timeline dot and the outcome pill
- `triggarr/static/css/output.css` - rebuilt once (Task 2) to compile two new-to-this-file classes (`align-middle`, `text-triggarr-muted/80`); Task 3 reused only already-compiled classes, no further rebuild
- `tests/test_db.py` - 14 new `get_dashboard_stats` tests (legacy exclusion, historical flags, R3 shared-name scoping, S1 rename/name-reuse, unassociated-row handling, scope-argument validation)
- `tests/test_attribution.py` - 9 new `get_attribution_disclosure` unit tests
- `tests/test_attribution_disclosure.py` (new) - rendered-route tests for the dashboard/stats-row disclosure (R3, R4, S1, D-01..D-08) and the History/activity-rail legacy badge (ATTR-05, D-04)
- `tests/test_web.py` - updated `test_stats_row_instance_filter` to expect `app="Radarr"` + `instance_stable_id=` instead of the removed `instance_id=` call shape

## Decisions Made

- Confirmed the plan's exact `inst_clause` design (one shared identity for effectiveness, flags and lifetime_stats) rather than a per-query scoping parameter — kept the four queries structurally identical in how they bind `app`/`instance_stable_id`.
- `sonarr_rate_includes_historical` and `overall_rate_includes_historical` return the same underlying flag value (documented inline) rather than two separately-computed queries, since the overall rate's only possible Sonarr-attributable pre-fix rows are exactly the rows the Sonarr-specific flag query already finds.
- For the rendered rename/name-reuse tests (S1), stable-ID association was seeded by directly stamping `instance_stable_id` on rows (mirroring Task 1's unit-test style) rather than driving a full v9→v10 migration via `tests/migration_faults.seed_v9_db`. The observable end state (rows associated with a stable ID before a display-name rename) is identical either way, and Plan 03's own migration-association mechanics are already covered by its test suite — this plan's tests focus on the stats/disclosure layer reading that state correctly. See Assumption Drift below.

## Assumption Drift (advisory)

- **Found during:** Task 2, writing `test_stats_row_rename_shows_history_and_disclosure` / `test_stats_row_name_reuse_shows_nothing_historical`.
- **Planned:** The plan's interface notes describe building these rendered S1 tests by constructing a v9 database and running `init_db(..., instance_stable_ids={...})` followed by `ensure_cutover_recorded`, i.e. driving the association through the real migration path.
- **Actual:** The tests instead insert rows directly with `instance_stable_id` already set (via `insert_search_entry`/raw `UPDATE`), then call `ensure_cutover_recorded` to produce the real persisted pre-fix facts.
- **Why:** This plan's scope is the stats/disclosure read layer, not the migration-association mechanism itself (fully covered by Plan 03's `tests/test_migration_v10_atomic.py` and `tests/test_attribution.py`). The resulting database state — rows carrying a stable ID before a later display-name rename — is identical whichever path produces it, and the simpler seeding keeps these tests focused on what this plan actually changes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `get_dashboard_stats` call in `partial_stats_row` exceeded the 120-char line length**
- **Found during:** Task 2 GREEN, writing the scoped `get_dashboard_stats` call
- **Issue:** The single-line call with `app=instance_app_type.title()` inline pushed the line to 121 characters (ruff E501 would fail at commit time).
- **Fix:** Extracted `app_title = instance_app_type.title()` as a local variable, shortening the call to fit on one line (also keeps the acceptance-criteria grep `get_dashboard_stats(...) | grep -c "app="` matching a single line).
- **Files modified:** `triggarr/web/routes.py`
- **Verification:** `uv run ruff check triggarr/web/routes.py` clean; acceptance-criteria greps re-run and passing.
- **Committed in:** `14f705a` (Task 2 GREEN commit)

**2. [Rule 1 - Bug] A RED test's own "searched" assertion was too broad**
- **Found during:** Task 3 GREEN, running `test_history_page_legacy_pending_shows_legacy_badge` against the finished implementation
- **Issue:** The test asserted `"searched"` was absent from the whole page, but History's outcome filter bar always renders the literal word "searched" as a filter pill regardless of row data — a pre-existing, unrelated page element, not a bug in the new legacy-badge code.
- **Fix:** Scoped the assertion to the results-list fragment (after the `space-y-0` results container), which correctly proves the legacy row's own badge never also shows "searched".
- **Files modified:** `tests/test_attribution_disclosure.py`
- **Verification:** `uv run pytest tests/test_attribution_disclosure.py tests/test_activity_rail.py -x -q` (40 passed).
- **Committed in:** `14ec598` (Task 3 GREEN commit, since the fix was required for Task 3's own RED test to correctly verify the new code)

---

**Total deviations:** 2 auto-fixed (1 line-length fix required for a ruff-clean commit, 1 test-assertion scoping fix caught by the RED/GREEN cycle)
**Impact on plan:** No scope creep. Both were direct, narrow consequences of this plan's own new code/tests.

## Issues Encountered

None beyond the two deviations above, both caught and fixed within the same task's RED/GREEN cycle.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `get_dashboard_stats(app=, instance_stable_id=)` and `get_attribution_disclosure` are both pure, importable functions ready for Plan 04's tracking-layer wiring (if any further dashboard surfaces need scoped stats) and for Plan 06's live-verification work to read against.
- `partial_stats_row`'s new 400-on-missing-stable-id behavior depends on every enabled instance having a non-empty `InstanceConfig.id` — guaranteed by Plan 01's startup backfill, confirmed by this plan's own rendered tests using instances with explicit ids.
- Full suite (1926 tests) and `uv run ruff check triggarr/ tests/` both pass clean at the end of this plan.
- No blockers for the remaining Phase 81 plans.

---
*Phase: 81-correct-sonarr-grab-attribution*
*Completed: 2026-10-19*

## Self-Check: PASSED

All modified/created files confirmed present on disk (`triggarr/db.py`, `triggarr/attribution.py`, `triggarr/web/routes.py`, `triggarr/templates/partials/stats_row.html`, `triggarr/templates/partials/history_results.html`, `triggarr/templates/partials/activity_rail.html`, `triggarr/static/css/output.css`, `tests/test_db.py`, `tests/test_attribution.py`, `tests/test_attribution_disclosure.py`, `tests/test_web.py`). All 6 task commits (`0411513`, `b30c629`, `df2c47a`, `14f705a`, `a6f89ba`, `14ec598`) confirmed present in `git log --oneline bbf6800..HEAD`. Full suite (1926 passed) and `uv run ruff check triggarr/ tests/` (clean) re-run and confirmed immediately before writing this summary. Every acceptance-criteria grep gate from all 3 tasks re-verified passing in the same pass.
