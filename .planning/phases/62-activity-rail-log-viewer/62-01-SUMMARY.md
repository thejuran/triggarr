---
phase: 62-activity-rail-log-viewer
plan: 01
subsystem: ui/activity-rail
tags: [css, html, templates, tests, tailwind]
dependency_graph:
  requires: []
  provides: [card-based-rail, font-mono-alias, cleaned-css]
  affects: [triggarr/static/css/input.css, triggarr/templates/partials/activity_rail.html, tests/test_activity_rail.py]
tech_stack:
  added: []
  patterns: [card-based-layout, speech-bubble-pointer, double-circle-dots, opacity-fading]
key_files:
  created: []
  modified:
    - triggarr/static/css/input.css
    - triggarr/templates/partials/activity_rail.html
    - tests/test_activity_rail.py
decisions:
  - "Queue type display removed from card layout per UI-SPEC card redesign (app badge + outcome pill replace it)"
metrics:
  duration: 230s
  completed: "2026-04-17T11:30:25Z"
  tasks_completed: 3
  tasks_total: 3
  tests_passed: 19
  files_modified: 3
---

# Phase 62 Plan 01: Activity Rail Card Restyling Summary

Card-based activity rail with speech bubble pointers, double-circle timeline dots, outcome-based solid/dashed cards, position-based opacity fading, and cleaned CSS removing obsolete timeline/scanline/terminal-pane classes.

## What Was Done

### Task 1: Clean CSS and add font-mono alias
- Added `--font-mono` theme alias in `@theme` block for Tailwind `font-mono` utility
- Removed `@keyframes scanline`, `.terminal-pane`, `.scanline-overlay` CSS blocks (LOG-05)
- Removed `.timeline-item`, `.timeline-dot` CSS blocks (RAIL-02)
- Preserved all other rules: dot-pulse, mini-bar, card-hover, danger-stripes, log-viewer.expanded
- **Commit:** 07c98b6

### Task 2: Restyle activity rail template to card-based layout
- Rewrote `activity_rail.html` with card-based entries per decisions D-01 through D-10
- Speech bubble pointers with `rotate-45` on card edges (D-03)
- Double-circle timeline dots: outer `w-7 h-7` ring + inner `w-2.5 h-2.5` outcome-colored dot (D-04)
- Solid cards for grabbed/partial, dashed cards for searched/failed/unresolved (D-01)
- Vertical timeline line at `left-[38px]` (D-05)
- App badges with colored dot indicators + font-mono labels (D-06)
- Position-based opacity fading: entry 3 = 75%, entry 4+ = 60% (D-07)
- LIVE badge stays green per D-08 override
- Sticky header with backdrop-blur-md (D-09)
- Footer with Phosphor `ph-arrow-right` icon and hover animation (D-10)
- Removed all inline SVGs from outcome pills (text-only)
- Preserved htmx wiring: `id="activity-rail"`, `hx-get`, `hx-trigger="every 5s"`, `hx-swap="outerHTML"`
- **Commit:** e3ae4c2

### Task 3: Update activity rail tests for new card-based layout
- Updated `test_rail_has_sticky_classes`: `top-20` -> `top-[73px]`
- Updated `test_timeline_dots_present`: timeline-item/dot -> double-circle pattern assertions
- Updated `test_entry_has_app_badge`: orange bg -> colored dot + font-mono assertions
- Updated `test_entry_has_outcome_pill`: green-400 -> triggarr-primary assertion
- Replaced `test_outcome_svg_icons` with `test_outcome_pills_text_only` (no SVGs)
- Updated `test_entry_has_queue_type` -> `test_entry_has_app_and_outcome` (queue_type removed)
- Added `rail_app_many` fixture (5 entries for opacity tests)
- Added 7 new tests: card layout, dashed cards, speech bubbles, opacity fading, header styling, timeline line, footer icon
- All 19 tests pass, ruff clean
- **Commit:** e12f2b3

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Queue type test updated for card redesign**
- **Found during:** Task 3
- **Issue:** `test_entry_has_queue_type` asserted `"missing"` and `"cutoff"` in response text, but the new card template no longer renders `entry.queue_type`. The plan's test updates did not account for this removal.
- **Fix:** Replaced with `test_entry_has_app_and_outcome` that checks for app name and outcome pill presence instead.
- **Files modified:** tests/test_activity_rail.py
- **Commit:** e12f2b3

**2. [Rule 1 - Bug] Ruff line length violations in rail_app_many fixture**
- **Found during:** Task 3
- **Issue:** Plan's fixture code had inline dict literals exceeding 120-char line limit (ruff E501).
- **Fix:** Extracted common instance dict to `_inst` variable with multiline formatting.
- **Files modified:** tests/test_activity_rail.py
- **Commit:** e12f2b3

## Verification Results

| Check | Result |
|-------|--------|
| `pytest tests/test_activity_rail.py -x -q` | 19 passed |
| `ruff check triggarr/templates/ tests/test_activity_rail.py` | All checks passed |
| Obsolete CSS (timeline-item/dot, terminal-pane, scanline) | 0 occurrences |
| font-mono alias present | Yes |

## Self-Check: PASSED
