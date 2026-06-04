---
phase: 76-never-searched-first-search-queue
plan: "03"
subsystem: search-engine
tags: [queue-priority, dead-code-removal, test-migration, static-guards]
dependency_graph:
  requires:
    - 76-01 (prioritize_batch pure function + AppState searched-log fields)
    - 76-02 (cursor fields removed + 6 call-site rewire + _merge_defaults strip-pop)
  provides:
    - slice_batch deleted from engine.py (QUEUE-07 final step)
    - post-deletion cold-start guarantee preserved by fixed-expectation test (QUEUE-06)
    - refresh-counts queue-independence re-expressed against searched-log (D-06/T-76-07)
    - 7 incidental UI/route fixtures stripped of removed cursor keys (D-05/D-07)
    - static guards locked (no slice_batch; no *_cursor outside test_state.py + v2.2 detector)
  affects:
    - tests/test_search.py
    - tests/test_refresh_counts.py
    - tests/test_web.py
    - tests/test_app_cards.py
    - tests/test_stats_health.py
    - tests/test_ui_foundations.py
    - tests/test_activity_rail.py
    - tests/test_header_redesign.py
    - tests/test_log_viewer.py
tech-stack:
  added: []
  patterns:
    - Fixed-expectation cold-start test (hardcoded first-N-in-fetch-order, no oracle dependency)
    - Re-expressed invariant tests (seed state -> call -> assert log unchanged)
    - Incidental fixture strip (remove removed-field keys; assert nothing about them)
key-files:
  created: []
  modified:
    - triggarr/search/engine.py
    - tests/test_search.py
    - tests/test_refresh_counts.py
    - tests/test_web.py
    - tests/test_app_cards.py
    - tests/test_stats_health.py
    - tests/test_ui_foundations.py
    - tests/test_activity_rail.py
    - tests/test_header_redesign.py
    - tests/test_log_viewer.py
key-decisions:
  - "Fixed-expectation cold-start test replaces the oracle (slice_batch comparison): hardcoded expected lists for N in {0,1,3,5,7}, no reference to deleted function"
  - "Re-expressed invariant renamed to *_does_not_touch_searched_log for all 3 apps (Radarr/Sonarr/Lidarr), plus the Rewrite-3 malformed-data regression test also migrated"
  - "test_web.py:test_dashboard_shows_position_x_of_y updated: cursor-based X-of-Y position display removed with cursor fields; test now asserts count values appear (42, 7)"
  - "test_web.py incidental cursor-absence assertion removed: canonical HIGH-1 coverage lives in test_state.py::test_strip_on_load_save_round_trip"
requirements-completed: [QUEUE-06, QUEUE-07]
duration: 20min
completed: "2026-06-04"
---

# Phase 76 Plan 03: Dead-Code Removal + Static Guards Summary

Dead `slice_batch` function and its 5 unit tests deleted, cold-start-equivalence guarantee preserved by hardcoded fixed-expectation test, refresh-counts queue-independence invariant re-expressed against the searched-log for all 3 apps, 7 incidental UI/route fixtures stripped of removed cursor keys, and all scoped static guards pass.

## Performance

- **Duration:** ~20 min
- **Started:** 2026-06-04T16:45:00Z
- **Completed:** 2026-06-04T17:05:00Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments

- Deleted `def slice_batch(...)` from `triggarr/search/engine.py` (all 6 callers already migrated in Plan 02; QUEUE-07 final step)
- Added `test_prioritize_batch_cold_start_fixed_expectation` in `tests/test_search.py`: hardcoded first-N-in-fetch-order expectations for N in {0,1,3,5,7} preserve QUEUE-06 guarantee without any oracle dependency
- Re-expressed 3 `*_does_not_advance_cursor` tests across Radarr/Sonarr/Lidarr as `*_does_not_touch_searched_log`: seed searched-logs, call refresh, assert UNCHANGED (D-06, T-76-07)
- Stripped cursor keys from all 7 incidental UI/route fixture files; updated doc-comments and one stale "X of Y" assertion in test_web.py
- All scoped static guards pass; full suite 1089 tests green; ruff clean

## Task Commits

1. **Task 1: Delete slice_batch + tests; add fixed-expectation cold-start test; update refresh docstrings** - `0ec174b` (feat)
2. **Task 2: Re-express refresh-counts queue-independence invariant (Radarr/Sonarr/Lidarr)** - `5b5cb4d` (feat)
3. **Task 3: Strip cursor keys from 7 incidental fixtures + full-suite static guards** - `0adb833` (feat)

## Files Created/Modified

- `triggarr/search/engine.py` - `def slice_batch(...)` deleted; 3 refresh_*_counts docstrings updated from "Does NOT call slice_batch / write missing_cursor/cutoff_cursor" to "Does NOT read or write missing_searched/cutoff_searched"
- `tests/test_search.py` - 5 slice_batch unit tests deleted; oracle equivalence test replaced by fixed-expectation test; `slice_batch` removed from import block; stale comment updated
- `tests/test_refresh_counts.py` - 3 cursor-advance tests re-expressed as searched-log-unchanged tests; Rewrite-3 regression test migrated; route fixtures stripped of cursor keys and seeded with searched-log fields
- `tests/test_web.py` - Main fixture cursor keys stripped; second fixture stripped; doc-comment updated; dashboard test updated to assert count values instead of cursor-based "X of Y"; stale cursor-absence assertion removed
- `tests/test_app_cards.py` - Fixture cursor keys stripped; 5 *_pass refs kept
- `tests/test_stats_health.py` - Fixture cursor keys stripped
- `tests/test_ui_foundations.py` - Fixture cursor keys stripped
- `tests/test_activity_rail.py` - Fixture cursor keys stripped (main fixture + _default dict + _inst dict)
- `tests/test_header_redesign.py` - Fixture cursor keys stripped
- `tests/test_log_viewer.py` - Fixture cursor keys stripped

## Decisions Made

- Fixed-expectation cold-start test replaces the oracle (slice_batch comparison): hardcoded expected lists for N in {0,1,3,5,7}, no reference to deleted function. The oracle (`test_prioritize_batch_cold_start_equivalence`) is deleted — the fixed-expectation variant is now the canonical QUEUE-06 proof.
- Re-expressed invariant renamed to `*_does_not_touch_searched_log` for all 3 apps. The Rewrite-3 malformed-data regression test (`test_refresh_counts_malformed_data_does_not_mutate_search_state`) was also re-expressed (it seeded cursor values; now seeds searched-logs instead).
- `test_web.py:test_dashboard_shows_position_x_of_y` updated: the cursor-based "X of Y" position display no longer exists (cursor fields removed in Plan 02); the test now asserts that count values (42, 7) appear in the dashboard response.
- Incidental `"missing_cursor" not in` assertion removed from test_web.py: canonical HIGH-1 coverage lives in `test_state.py::test_strip_on_load_save_round_trip`; duplicate incidental assertion would violate the cursor static guard.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Additional cursor tests in test_refresh_counts.py beyond the 3 enumerated**
- **Found during:** Task 2
- **Issue:** The Rewrite-3 regression test `test_refresh_counts_malformed_data_does_not_mutate_search_state` seeded `missing_cursor=77`/`cutoff_cursor=88` and asserted their values unchanged — not in the RESEARCH classification table, but a cursor reference that would fail the static guard
- **Fix:** Re-expressed the test to seed `missing_searched=["10","20"]`/`cutoff_searched=["99"]` and assert searched-logs unchanged
- **Files modified:** `tests/test_refresh_counts.py`
- **Verification:** `uv run pytest tests/test_refresh_counts.py -x -q` 31 passed
- **Committed in:** `5b5cb4d` (Task 2 commit)

**2. [Rule 1 - Bug] test_dashboard_shows_position_x_of_y broken by fixture cursor removal**
- **Found during:** Task 3
- **Issue:** After stripping `missing_cursor=3`/`cutoff_cursor=1` from the fixture, the test asserted "3 of 42" and "1 of 7" which were cursor-based position strings the template no longer renders
- **Fix:** Updated test to assert count values ("42" and "7") appear in the dashboard response
- **Files modified:** `tests/test_web.py`
- **Verification:** `uv run pytest tests/test_web.py::test_dashboard_shows_position_x_of_y -x -q` 1 passed
- **Committed in:** `0adb833` (Task 3 commit)

**3. [Rule 1 - Bug] Incidental cursor-absence assertion in test_web.py violated static guard**
- **Found during:** Task 3 static guard verification
- **Issue:** `assert "missing_cursor" not in state[...]` on line 1849 was a Plan 02 auto-fix; references a cursor key name, triggering the static guard
- **Fix:** Removed the line; adjacent `assert state["radarr"]["Default"]["missing_searched"] == []` already proves new model working; canonical cursor-strip coverage in `test_state.py`
- **Files modified:** `tests/test_web.py`
- **Verification:** static guard passes
- **Committed in:** `0adb833` (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (Rule 1 bugs)
**Impact on plan:** All fixes required for green suite + static guard compliance. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None.

## Next Phase Readiness

Phase 76 fully complete:
- `slice_batch` gone, no dead code, no tombstoned fields
- Cold-start guarantee preserved by slice_batch-free fixed-expectation test
- Queue-independence invariant re-expressed and green for all 3 apps
- 7 incidental fixtures clean; test_state.py HIGH-1 regression INTACT
- All static guards pass; full suite 1089 tests green; ruff clean

---

## Known Stubs

None. Dead-code removal and test migration only.

## Threat Flags

None. T-76-07 (queue-independence invariant) and T-76-08 (static guards) fully mitigated.

## Self-Check: PASSED

- `triggarr/search/engine.py`: `def prioritize_batch(` present; `def slice_batch(` absent; no cursor strings
- `tests/test_search.py`: `test_prioritize_batch_cold_start_fixed_expectation` present; no slice_batch import
- `tests/test_refresh_counts.py`: `missing_searched` present; no cursor refs
- `tests/test_state.py`: `missing_cursor` present (HIGH-1 regression intact)
- Commits `0ec174b`, `5b5cb4d`, `0adb833` present in git log
- `! grep -rq "slice_batch" triggarr/ tests/` PASSES
- `! { grep -rlE "missing_cursor|cutoff_cursor" tests/ | grep -qv test_state.py }` PASSES
- `grep -qE "missing_cursor|cutoff_cursor" tests/test_state.py` PASSES
- `! grep -qE "missing_cursor|cutoff_cursor" triggarr/search/engine.py` PASSES
- `uv run pytest tests/ -x -q` 1089 passed
- `uv run ruff check triggarr/ tests/` All checks passed
