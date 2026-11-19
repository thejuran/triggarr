---
phase: 90-removed-instance-pending-search-lifecycle
plan: 04
subsystem: ui
tags: [templates, history, activity-rail, instance-removed]
requires: [90-01]
provides:
  - "Instance removed" badge, tooltip and outcome filter option in History
  - "Instance removed" pill, tooltip and explicit gray dot in the activity rail
affects: [90-07]
tech-stack:
  added: []
  patterns: [instance_removed branch placed directly after is_legacy in every template chain]
key-files:
  created: []
  modified:
    - triggarr/templates/partials/history_results.html
    - triggarr/templates/partials/activity_rail.html
    - tests/test_attribution_disclosure.py
key-decisions:
  - "Reused existing Legacy gray classes in each template; no CSS rebuild, no static change"
  - "is_legacy branch kept first so a Legacy row can never render as Instance removed"
requirements-completed: []
duration: 20min
completed: 2026-11-18
---

# Phase 90 Plan 04: Instance removed labeling Summary

Searches closed as `instance_removed` now render as a gray "Instance removed" badge with the agreed tooltip in History and the activity rail, stay distinct from Legacy, and History has an "Instance removed" filter option.

RMINST-01 and RMINST-03 are only partly delivered by this plan (display only); they are left unchecked in REQUIREMENTS.md for the plans that finish the lifecycle.

## Commits
- 26453e27 test(90-04): failing tests for Instance removed badge and filter in History (RED)
- 77e49614 feat(90-04): show Instance removed badge, tooltip and filter in History (GREEN)
- 982a3e88 test(90-04): failing tests for Instance removed pill in activity rail
- f56fb1ce feat(90-04): show Instance removed pill and dot in activity rail (GREEN)

## Test evidence (observed)
Task 1 RED run (`uv run pytest tests/test_attribution_disclosure.py -q -k "history and instance_removed"`): 6 failed.

| Test | Class | Pre-fix | Post-fix |
|---|---|---|---|
| test_history_instance_removed_row_shows_badge_and_tooltip | RED | FAIL (text not rendered) | pass |
| test_history_instance_removed_badge_uses_legacy_gray | RED | FAIL (no span renders `Instance removed`) | pass |
| test_history_legacy_and_instance_removed_never_conflated | RED | FAIL (0 == 1 badges) | pass |
| test_history_outcome_filter_offers_instance_removed | RED | FAIL (no filter link) | pass |
| test_history_outcome_filter_instance_removed_filters_rows | RED | FAIL (no pill element; server filter already worked) | pass |
| test_history_instance_removed_row_keeps_instance_name_and_is_not_in_progress | RED | FAIL (0 badges) | pass |

Task 2 RED run (`-k "activity_rail and instance_removed"`): 3 failed, 1 passed.

| Test | Class | Pre-fix | Post-fix |
|---|---|---|---|
| test_activity_rail_instance_removed_row_shows_pill_and_tooltip | RED | FAIL | pass |
| test_activity_rail_instance_removed_pill_uses_legacy_gray | RED | FAIL | pass |
| test_activity_rail_legacy_and_instance_removed_never_conflated | RED | FAIL | pass |
| test_activity_rail_instance_removed_uses_dashed_card | PASS pin | pass (as planned) | pass |

GREEN gate: `-k instance_removed` 10 passed; `uv run pytest tests/ -x -q` 3452 passed, 1 skipped; `uv run ruff check triggarr/ tests/` clean. `git diff --stat main -- triggarr/static` empty.

Not verified: the browser hover/visual check in 90-VALIDATION.md (no GUI run); tooltip presence is verified in rendered HTML only.

## Deviations from Plan

**1. [Process] RED commit ordering for task 1**
- **Found during:** Task 1
- **Issue:** A BSD `sed -i` cleanup in the same shell batch as the RED commit failed, so the template edit ran before the RED commit. The RED failures were observed beforehand (6 failed); the test commit (26453e27) still precedes the feat commit (77e49614).
- **Cost if wrong:** none; history order is test then feat.

Otherwise plan executed as written.

## Known Stubs
None.

## Threat Flags
None. New markup is fixed template literals, autoescape unchanged, no `| safe`.

## Self-Check: PASSED
