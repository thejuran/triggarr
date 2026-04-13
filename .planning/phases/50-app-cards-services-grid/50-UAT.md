---
status: complete
phase: 50-app-cards-services-grid
source: 50-01-SUMMARY.md, 50-02-SUMMARY.md
started: 2026-04-13T19:55:00Z
updated: 2026-04-13T20:05:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Connection Pill — Connected State
expected: Connected cards show a green pill with "Connected" text and an animated pulsing dot
result: pass
verified_by: test_connected_pill_unified_shape, test_connected_pill_has_dot_pulse

### 2. Connection Pill — Unreachable State
expected: An unreachable card shows a red "Unreachable" pill (static, no pulse dot) and the entire card has diagonal red danger stripes at low opacity with stats grid dimmed (opacity-60)
result: pass
verified_by: test_unreachable_pill_unified_shape, test_unreachable_card_danger_stripes, test_unreachable_stats_opacity, test_connected_card_no_danger_stripes

### 3. Schedule Row
expected: Each app card shows a schedule row with "Last Run" (HH:MM:SS format) and "Next Run" (HH:MM format). Unreachable cards show an em dash for Next Run instead of a time
result: pass
verified_by: test_schedule_row_present, test_schedule_row_unreachable_next_run_dash

### 4. Pass Pill Badges
expected: Stats grid entries (missing/cutoff) show small pill badges with pass counts when passes > 0. When passes = 0, no pill badge is shown
result: pass
verified_by: test_pass_pill_displayed, test_pass_pill_hidden_when_zero

### 5. Card Hover Elevation
expected: Hovering over any app card produces a smooth background-color and box-shadow transition (150ms). Cards have shadow-sm by default
result: pass
verified_by: test_card_has_hover_classes, test_css_has_card_hover_rule

### 6. Retry vs Search Now Button
expected: Connected cards show a green "Search Now" button. Unreachable cards show a red "Retry" button instead
result: pass
verified_by: test_unreachable_card_retry_button, test_connected_card_search_now_button

### 7. Tag Warning Badge
expected: If an instance has tag configuration issues, a warning badge with an SVG triangle icon is displayed (not the old HTML entity)
result: pass
verified_by: test_tag_warning_uses_svg_icon

### 8. 3-Column Grid at XL Viewport
expected: At viewport width >= 1280px, the app cards arrange into a 3-column grid layout. Below that breakpoint, the layout falls back to fewer columns
result: pass
verified_by: test_dashboard_grid_three_columns

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
