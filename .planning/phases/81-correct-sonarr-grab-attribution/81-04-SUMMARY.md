---
phase: 81-correct-sonarr-grab-attribution
plan: 04
subsystem: search-correctness
tags: [sonarr, tracking, attribution, grab-ownership, sqlite, httpx]

# Dependency graph
requires:
  - phase: 81-01
    provides: "InstanceConfig.id (stable per-instance identifier), backfilled before lifespan runs"
  - phase: 81-02
    provides: "Sonarr episode/season identity on GrabEvent, sonarr_identity_problem, correlate_grabs(match_season=...), sanitized fixtures"
  - phase: 81-03
    provides: "Migration v10 schema (grab_ownership, attribution_cutover, sonarr_instance_pre_fix), OwnedGrab/OwnedGrabRecord, get_owned_grabs, update_outcome_and_stats(owned_grabs=...), get_trackable_entries(instance_stable_id=...), ensure_cutover_recorded"
provides:
  - "run_tracking_check(..., *, instance_stable_id: str): ownership-aware Sonarr tracking (selection by stable ID, identity gate, owned-grab exclusion, season match, distinct-episode accumulation, atomic persistence including partial-progress writes); Radarr/Lidarr unchanged except stable-ID-keyed lifetime increments"
  - "Real-client-path fixture regressions proving the above end to end through SonarrClient + httpx.MockTransport (season pack, multi-season pack, alternate-order, repeated checks, missing/malformed/conflicting identity)"
  - "Scheduler lifespan: instance_stable_ids mapping passed to init_db; ensure_cutover_recorded called exactly once, immediately after, uncaught"
  - "Scheduler job: instance_stable_id threaded into every tracking call; tracking summary log reports identity_skipped"
  - "Engine: _search_and_record / all 6 Radarr+Sonarr+Lidarr call sites record each new search row under its instance's stable ID"
affects: [81-05, 81-06, 81-07, 81-08, 81-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sonarr tracking split into a private _run_sonarr_tracking_check helper so the identity-gate/ownership/season-match/accumulation logic never touches the unchanged Radarr/Lidarr path, and the match_season=True literal stays grep-able in one place"
    - "Partial-progress persistence: when _sonarr_outcome returns None but new grabs were matched against an already-'partial' search, ownership for those new grabs is still committed now (same update_outcome_and_stats transaction shape, stat_increments=None) rather than waiting for a terminal outcome -- keeps a partial search's grabs owned between checks so no other search can claim them first"
    - "Distinct-episode accumulation key: a set of Sonarr episodeIds built from previously-owned records plus this check's newly-matched grabs, with no grab-id fallback anywhere, so a repeat grab event (season-pack re-grab) is owned twice but counted once"

key-files:
  created:
    - tests/test_attribution_client_path.py
  modified:
    - triggarr/tracking.py
    - triggarr/search/scheduler.py
    - triggarr/search/engine.py
    - tests/test_tracking.py
    - tests/test_scheduler.py
    - tests/test_search.py
    - tests/test_config_dir.py

key-decisions:
  - "run_tracking_check's instance_stable_id is a required keyword-only str (no default) -- every one of the 17 pre-existing test call sites and the one production call site must supply it explicitly, so no caller can silently fall back to an empty value"
  - "Sonarr's empty-stable-id guard counts pending entries by display name (get_trackable_entries(instance_id=...)) specifically for the error-count report, since stable-ID selection is unavailable by definition in that branch"
  - "Radarr/Lidarr forward instance_stable_id or None to update_outcome_and_stats unconditionally (even though their selection/outcome logic is untouched) so a configured instance's lifetime counters key off the stable ID like Sonarr's do (S1), falling back to the legacy name-keyed row when the config id is still empty"
  - "In the rename-during-partial-tracking scenario, the lifetime_stats row for the stable ID is created fresh under whichever display name is current at first-ever stat write (no earlier write occurred during the non-terminal 'partial' detection, since that path intentionally carries stat_increments=None) -- confirmed via test, not assumed"

patterns-established:
  - "Any future app-specific orchestration inside a shared dispatcher function (run_tracking_check) that diverges enough in selection/ownership semantics should split into a private per-app helper rather than branching deeply inline -- keeps each app's acceptance-criteria greps (e.g. match_season=True exactly once) unambiguous"

requirements-completed: [ATTR-01, ATTR-02, ATTR-04, ATTR-05, SONARRV5-03]

# Metrics
duration: ~75min
completed: 2026-10-19
---

# Phase 81 Plan 04: Sonarr Attribution Tracking & Scheduler Wiring Summary

**`run_tracking_check` now excludes already-owned grabs, matches by season, counts distinct Sonarr episodes, accumulates ownership across checks, and persists it all atomically; the scheduler records the attribution cutover once at startup and threads each instance's stable ID into every new search row and tracking check.**

## Performance

- **Duration:** ~75 min (including worktree repair -- the phase-81 planning directory and REQUIREMENTS.md are git-excluded locally and had to be copied in from the main checkout before work could start)
- **Completed:** 2026-10-19
- **Tasks:** 3 (all complete)
- **Files modified:** 8 (3 production, 5 test; 1 new test file)

## Accomplishments

- **Task 1 -- Ownership-aware Sonarr tracking:** `run_tracking_check` gained a required `instance_stable_id` keyword. Sonarr selection now reads `get_trackable_entries(db, instance_stable_id=...)` instead of the display name, so a rename or a different server reusing an old name can never misroute or double-credit a pending search (R1). An empty stable ID refuses to track entirely (logged error, pending entries counted as errors) rather than risk sharing ownership. Every grab is checked against `sonarr_identity_problem`; untrustworthy grabs are dropped and counted in a new `identity_skipped` counter (R2, R6). Grabs already owned for the series are excluded before correlation; `correlate_grabs(..., match_season=True)` then requires the matching season. Distinct Sonarr `episodeId`s (previously-owned plus newly-matched, no grab-id fallback) drive the unchanged `_sonarr_outcome` state machine. Ownership rows commit in the same transaction as every outcome/stat write, including a partial-to-partial progress update when new grabs arrive but the search has not yet resolved. A same-instance ownership `IntegrityError` is caught per entry and counted as a non-fatal error (T-81-20). Radarr/Lidarr selection and outcome logic are unchanged; the only difference is that their lifetime increments now key off the stable ID when one is configured.
- **Task 2 -- Real-client-path fixture regressions (D-12):** A real `SonarrClient` over `httpx.MockTransport` serves the Plan 02 sanitized fixtures (season pack, multi-season pack, alternate-order, standard v4) through `get_grab_history` -> `GrabEvent` validation -> `run_tracking_check`, proving season-pack repeat-grab counting, cross-season isolation, canonical-season matching over scene numbering, and repeated-check idempotency hold end to end. The same real path also proves R2/R6: missing, malformed (non-int/bool/zero `episodeId`, non-dict/malformed `episode`), and conflicting/missing series identity values are all skipped and counted via the production parse path without raising, while valid records in the same response still credit normally, and warning log lines never carry the release title.
- **Task 3 -- Startup, engine and scheduler wiring:** The lifespan builds a `{(app, name): stable id}` mapping from every configured instance (Settings is already backfilled before the lifespan runs) and passes it to `init_db` for the one-time v10 association of existing rows, then calls `ensure_cutover_recorded` immediately after, uncaught -- a failed cutover stops startup the same way a failed migration does, so pre-cutover pending rows can never be tracked under the new rules. The scheduled job's tracking call now passes `instance_stable_id=instance_config.id`; the tracking summary log also reports `identity_skipped` and treats a non-zero value as its own reason to emit the line. `_search_and_record` gained a keyword-only `instance_stable_id`, forwarded to both `insert_search_entry` calls; all six Radarr/Sonarr/Lidarr call sites across the three `run_*_cycle` functions now pass their cycle's `instance_config.id`.

## Task Commits

Each task followed RED (test) then GREEN (feat), except Task 2 which is a test-only regression task (no production behavior to add):

1. **Task 1: Sonarr ownership-aware tracking**
   - `a392df0` test(81-04): add failing ownership-aware tracking tests
   - `7ffb4a0` feat(81-04): ownership-aware Sonarr tracking with distinct-episode accumulation
2. **Task 2: Real-client-path fixture regressions (SONARRV5-03, D-12)**
   - `cfda95e` test(81-04): client-path attribution fixture regressions
3. **Task 3: Startup, engine and scheduler wiring**
   - `ebeed6c` test(81-04): add failing scheduler wiring tests
   - `7db1af5` feat(81-04): wire cutover recording and stable instance id into the scheduler

## Files Created/Modified

- `triggarr/tracking.py` -- `run_tracking_check(..., *, instance_stable_id: str)`; new private `_run_sonarr_tracking_check` (selection, identity gate, ownership exclusion, season match, distinct-episode accumulation, atomic persistence, partial-progress writes, `IntegrityError` handling)
- `triggarr/search/scheduler.py` -- `instance_stable_ids` mapping built and passed to `init_db`; `ensure_cutover_recorded` import and call right after; job closure passes `instance_stable_id=instance_config.id`; tracking summary log reports and gates on `identity_skipped`
- `triggarr/search/engine.py` -- `_search_and_record` gains `instance_stable_id`, forwarded to both `insert_search_entry` calls; 6 call sites (Radarr/Sonarr/Lidarr x 2 queues) pass `instance_config.id`
- `tests/test_tracking.py` -- `_grab`/`_insert_entry`/`_get_stat` helpers updated for season/episode/series identity and stable-ID scoping; `instance_stable_id` added to all 17 pre-existing `run_tracking_check` calls; 16 new tests covering every spec acceptance scenario
- `tests/test_attribution_client_path.py` (new) -- 7 real-client-path fixture regression tests
- `tests/test_scheduler.py` -- 6 new tests (cutover recorded once, call order, stable-ID mapping, v9->v10 upgrade association, job-level stable-ID threading, `identity_skipped` logging)
- `tests/test_search.py` -- 2 new tests (`run_radarr_cycle`/`run_sonarr_cycle` record the cycle's instance stable ID on every new row)
- `tests/test_config_dir.py` -- updated one pre-existing fully-mocked lifespan test to also patch `ensure_cutover_recorded` and assert `init_db`'s new `instance_stable_ids={}` kwarg (see Deviations)

## Decisions Made

- `instance_stable_id` is a required keyword on `run_tracking_check` (no default) so no call site can silently omit it; all 17 existing test calls and the 1 production call site were updated to supply it explicitly.
- Radarr/Lidarr now forward `instance_stable_id or None` to `update_outcome_and_stats` unconditionally, even though their selection and outcome logic are otherwise untouched, so a configured instance's lifetime counters key off the stable ID consistently with Sonarr (S1).
- The Sonarr empty-stable-ID guard reports its error count by display-name selection (`get_trackable_entries(instance_id=...)`), since stable-ID selection is definitionally unavailable in that branch.
- Confirmed via test (not assumed) that in a rename-during-partial scenario, the lifetime_stats row for a stable ID is created fresh under whichever display name is current at the first real stat write -- because the non-terminal "partial" detection path intentionally carries `stat_increments=None`, no row exists yet to preserve an earlier name.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing fully-mocked lifespan test broke on the new `ensure_cutover_recorded` call**
- **Found during:** Task 3 GREEN, running the full suite after wiring cutover recording into the lifespan
- **Issue:** `tests/test_config_dir.py::test_lifespan_derives_sqlite_path_from_injected_state_path` patches `aiosqlite.connect` and `init_db` to a bare mock but does not touch `ensure_cutover_recorded`. Once the lifespan called the real `ensure_cutover_recorded` against the mocked `AsyncMock` database, it raised `TypeError: 'coroutine' object does not support the asynchronous context manager protocol` -- a direct, narrow consequence of this plan's own new call, not a pre-existing product bug.
- **Fix:** Added a patch for `triggarr.search.scheduler.ensure_cutover_recorded` alongside the existing `init_db` patch, and updated the `init_db` assertion to the new signature (`instance_stable_ids={}`, since the test's bare `Settings()` configures no instances) plus a new assertion that `ensure_cutover_recorded` was awaited once with `{}`.
- **Files modified:** `tests/test_config_dir.py`
- **Verification:** `uv run pytest tests/test_config_dir.py -q` (11 passed); full suite (1914 passed) and `ruff check` (clean) re-run after.
- **Committed in:** `7db1af5` (Task 3 GREEN commit, since the fix was required for that commit's own full-suite verification)

---

**Total deviations:** 1 auto-fixed (Rule 1 -- a direct, narrow consequence of this plan's own new lifespan call, caught by the plan's own full-suite verification step)
**Impact on plan:** No scope creep. The touched file (`tests/test_config_dir.py`) is outside this plan's declared `files_modified` list, but the fix was required by this plan's own change and nothing else.

## Issues Encountered

- While bringing the 16 new `test_tracking.py` tests to green, three test-authoring bugs in my own new test code (not production code) surfaced and were fixed before the GREEN commit: (1) several new tests inserted rows with the helper's default `instance_stable_id="sid-test"` while calling `run_tracking_check` with a different stable ID (e.g. `"sid-main"`), so selection found nothing; (2) `_get_stat`'s original pattern of toggling `db.row_factory` to `None` after each read broke a later `run_tracking_check` call in the same test once a mid-test stat check was introduced (multi-check tests are new to this plan); (3) a restart test reconnected to the same database file without re-running `init_db`, which is what sets `row_factory` in production too. None of these were deviations from the plan -- they were caught and fixed within the same RED->GREEN cycle, before any commit landed.
- Phase 81's planning directory (`.planning/phases/81-correct-sonarr-grab-attribution/`) and `.planning/REQUIREMENTS.md` are excluded from git locally (per STATE.md's documented handoff note) and were not present in this worktree at spawn time. Copied them in from the main checkout (`/Users/julianamacbook/triggarr/.planning/`) before reading the plan, per the note's own instructions; no planning file was edited, only read.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Every spec acceptance scenario for Sonarr attribution passes at the tracking layer (original repro, owned-grab exclusion, cross-instance isolation, rename, rename-during-partial, old-name reuse, untrustworthy identity skip/count, pruning, restart, partial-to-complete accumulation, season-pack repeat-grab counting, legacy-pending exclusion, empty-stable-ID refusal, non-fatal ownership `IntegrityError`) and through the real Sonarr client path (season pack, multi-season pack, alternate order, repeated checks).
- Startup now records the cutover exactly once, right after the v10 migration, and associates every pre-existing row with its instance's stable ID; every new search row and tracking check from this point forward is stable-ID-scoped.
- Full test suite (1914 tests) and `ruff check triggarr/ tests/` both pass clean at the end of this plan.
- No blockers for Plan 05 (stats disclosure), which can rely on `attribution_cutover`/`sonarr_instance_pre_fix` (Plan 03) being populated correctly by a real startup from this plan onward.

---
*Phase: 81-correct-sonarr-grab-attribution*
*Completed: 2026-10-19*

## Self-Check: PASSED

All 8 created/modified files confirmed present on disk (`triggarr/tracking.py`, `triggarr/search/scheduler.py`, `triggarr/search/engine.py`, `tests/test_tracking.py`, `tests/test_attribution_client_path.py`, `tests/test_scheduler.py`, `tests/test_search.py`, `tests/test_config_dir.py`). All 5 task commits (`a392df0`, `7ffb4a0`, `cfda95e`, `ebeed6c`, `7db1af5`) confirmed present in `git log --oneline --all`. Full suite (1914 passed) and `ruff check triggarr/ tests/` (clean) re-run and confirmed immediately before writing this summary. Plan-level verification block (`uv run pytest tests/test_tracking.py tests/test_attribution_client_path.py tests/test_scheduler.py -x -q` -> 100 passed; `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/` -> 1914 passed, ruff clean) re-run and confirmed immediately before writing this summary.
