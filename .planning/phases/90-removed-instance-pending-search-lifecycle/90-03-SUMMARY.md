---
phase: 90-removed-instance-pending-search-lifecycle
plan: 03
subsystem: tracking
tags: [tracking, stable-id, radarr, lidarr, name-reuse]
requires: [90-02]
provides:
  - Radarr/Lidarr pending-search selection and lifetime credit by stable instance ID
  - empty-stable-ID refusal for Radarr/Lidarr in run_tracking_check
affects: [90-04, 90-07]
tech-stack:
  added: []
  patterns: [stable-ID-only selection shared by all three apps]
key-files:
  created: []
  modified: [triggarr/tracking.py, tests/test_tracking.py, tests/test_scheduler.py]
key-decisions:
  - "No fallback chain on credit: update_outcome_and_stats gets the tracking instance's own stable ID"
  - "NULL-ID rows are selected by no instance"
requirements-completed: [RMINST-03]
duration: 40min
completed: 2026-11-18
---

# Phase 90 Plan 03: Radarr/Lidarr select by stable ID Summary

Radarr and Lidarr tracking now select pending searches by the instance's stable ID, as Sonarr does, so a new instance that reuses a removed instance's name never checks or credits the old searches; an empty stable ID refuses to track.

## Commits
- 8ca72826 test(90-03): failing tests for Radarr/Lidarr stable-ID selection (RED)
- 8e586e19 feat(90-03): select and credit Radarr and Lidarr searches by stable ID (GREEN)

## Test evidence (observed)
RED run (`uv run pytest tests/test_tracking.py -v -k "name_reuse or empty_stable_id or per_instance_tracking_isolation"`): 9 failed, 10 passed. Pre-fix on unfixed code:

| Test | Class | Pre-fix | Post-fix |
|---|---|---|---|
| test_radarr_name_reuse_never_selects_or_credits_old_rows | RED | FAIL (outcome `grabbed`, not `searched`) | pass |
| test_lidarr_name_reuse_never_selects_or_credits_old_rows | RED | FAIL | pass |
| test_radarr_name_reuse_row_without_stable_id_is_never_selected | RED | FAIL | pass |
| test_name_reuse_new_instance_still_tracks_its_own_rows[Radarr, Lidarr] | RED | FAIL x2 | pass x2 |
| test_empty_stable_id_refuses_to_track[Radarr, Lidarr] | RED | FAIL x2 | pass x2 |
| test_radarr_name_reuse_through_real_client_keeps_card_consistent | RED | FAIL | pass |
| test_lidarr_name_reuse_through_real_client_keeps_card_consistent | RED | FAIL | pass |
| test_sonarr_name_reuse_never_selects_or_credits_old_rows | PASS pin | pass | pass |
| test_name_reuse_closed_rows_never_selected (3 apps x 2 tracking IDs = 6) | PASS pin | pass x6 | pass x6 |
| test_per_instance_tracking_isolation (adjusted: sid-4k / sid-1080p) | adjusted | pass | pass |

Real-client tests keep the request-path assertions (history request occurred; Lidarr `albumId` and `eventType == "1"`), now for the row the new instance owns, plus a check that no request carries the old row's item ID. The old identity's rate is 0.0 (the untouched pending row stays in the denominator), as the plan specified.

Final gate: `uv run pytest tests/ -q` 3442 passed, 1 skipped; `uv run ruff check triggarr/ tests/` clean; `git diff --quiet main -- pyproject.toml uv.lock` exit 0. Acceptance greps: `get_trackable_entries(db, instance_id=instance_id)` 2, `get_trackable_entries(db, instance_stable_id=instance_stable_id)` 2, old fallback chain 0, old test names 0. `-k name_reuse` 15 passed; `-k empty_stable_id` 3 passed. Test function count in tests/test_tracking.py: 45 before, 49 after (parametrized cases add more at run time).

## Audit of Radarr/Lidarr run_tracking_check callers
| Test file | Rows / tracked ID | Action |
|---|---|---|
| tests/test_tracking.py (isolation test) | two Radarr rows both `sid-test`, tracked `sid-test` | gave rows `sid-4k` / `sid-1080p`, tracked as `sid-4k` |
| tests/test_tracking.py (other Radarr/Lidarr tests) | rows default `sid-test`, tracked `sid-test` | none needed (passed) |
| tests/test_attribution_client_path.py | Sonarr only | none |
| tests/test_scheduler.py | run_tracking_check mocked except one test | see below |
| tests/test_db.py | does not call run_tracking_check | none |

## Tests relying on name selection
- `tests/test_scheduler.py::test_search_job_runs_tracking_after_cycle`: inserted a Radarr pending row with no stable ID and let the scheduler track the "Default" instance, whose `InstanceConfig.id` is empty in test settings. Fix (test data only, no assertion changed): the instance gets `id = "sid-radarr-default"` and the row is inserted with that stable ID.

## Deviations from Plan
**1. [Rule 3 - Blocking] scheduler test data** (above). Cost if wrong: test-only. Commit 8e586e19.

## Assumption Drift (advisory)
- Found during: GREEN full-suite gate. Planned: scheduler test left unchanged apart from "any test relying on name selection" being listed; actual: it had to be listed (it is). Cost if wrong: none.

## Known Stubs
None.

## Threat Flags
None.

## Self-Check: PASSED
