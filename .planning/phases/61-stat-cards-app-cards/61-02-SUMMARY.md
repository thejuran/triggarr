---
phase: 61-stat-cards-app-cards
plan: "02"
subsystem: web-ui
tags: [app-cards, tailwind, jinja2, htmx]
dependency_graph:
  requires: [61-01]
  provides: [CARD-01, CARD-02, CARD-03, CARD-04]
  affects: [triggarr/templates/partials/app_card.html, tests/test_app_cards.py]
tech_stack:
  added: []
  patterns: [sectioned-card-layout, recessed-sub-cards, app-type-color-conditional]
key_files:
  created: []
  modified:
    - triggarr/templates/partials/app_card.html
    - tests/test_app_cards.py
decisions:
  - "Unreachable body replaced entirely with centered error message (no stats grid)"
  - "Schedule row removed from unreachable cards (only shown for connected/waiting)"
metrics:
  duration_seconds: 228
  completed: "2026-04-16T02:58:00Z"
  tasks_completed: 2
  tasks_total: 2
  test_count: 26
---

# Phase 61 Plan 02: App Card Restyling Summary

Sectioned app card layout with app-type colored left borders, recessed sub-cards, and full-width Search Now button with Phosphor icons and app-colored hover.

## What Changed

### Task 1: Restructure app_card.html (3d5957c)

Rewrote app_card.html from flat single-div layout to three-section structure (header/body/footer):

- **Outer wrapper**: Removed `p-5` padding (moved to sections), added `overflow-hidden flex flex-col`
- **Left border**: Changed from connection-status-based (green/red) to app-type-based (radarr=orange, sonarr=blue, lidarr=green) with red override only for unreachable
- **Header section**: `p-4 border-b border-triggarr-border/50` with `text-[15px] font-bold` title and `rounded` connection pills (replaced `rounded-full` + dot-pulse)
- **Connected body**: `p-4 flex-1` with `font-mono` schedule row, recessed sub-cards (`bg-triggarr-bg/50 border border-triggarr-border/50 rounded p-2.5`) for Missing/Cutoff stats
- **Unreachable body**: Replaced stats grid + opacity-60 with centered error message (`ph-warning-circle` icon + "API connection failed.")
- **Footer**: `p-3 bg-triggarr-bg/30 border-t` with full-width buttons -- Search Now (`ph-magnifying-glass`, app-colored group-hover) and Retry Connection (`ph-arrows-clockwise`)
- **Danger overlay**: Gradient overlay for unreachable cards with z-10 stacking on interactive elements

### Task 2: Update test_app_cards.py (0792673)

Updated 8 existing tests and added 8 new tests (26 total, all passing):

- Updated pill assertions from `rounded-full` to `rounded` + `tracking-wider` + border
- Updated schedule row from `border-b pb-3` to `font-mono mb-4`
- Updated button assertions for new Phosphor icons and elevated backgrounds
- Replaced dot-pulse tests with pill border tests
- Replaced unreachable stats opacity test with error message test
- Added tests for: radarr border color, unreachable border color, header border-bottom, recessed subcards, app-colored hover, error message body, footer background

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated unreachable schedule row test**
- **Found during:** Task 2
- **Issue:** `test_schedule_row_unreachable_next_run_dash` checked for em dash in schedule row, but unreachable cards no longer render the schedule row (body replaced with error message)
- **Fix:** Changed test to verify schedule row absence and error message presence
- **Files modified:** tests/test_app_cards.py
- **Commit:** 0792673

**2. [Rule 1 - Bug] Fixed ruff E501 line length violations**
- **Found during:** Task 2
- **Issue:** Three pill assertion lines exceeded 120 char limit
- **Fix:** Extracted common pill classes to local variable
- **Files modified:** tests/test_app_cards.py
- **Commit:** 0792673

## Known Stubs

None.

## Self-Check: PASSED
