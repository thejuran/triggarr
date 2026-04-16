---
phase: 61-stat-cards-app-cards
plan: 01
subsystem: ui-stat-cards
tags: [ui, stat-cards, tailwind, phosphor-icons]
dependency_graph:
  requires: []
  provides: [triggarr-primary-token, triggarr-elevated-token, artifact-stat-cards]
  affects: [stats_row.html, input.css, output.css]
tech_stack:
  added: []
  patterns: [phosphor-icons-per-card, colored-dot-subtitles, horizontal-mini-bars]
key_files:
  created: []
  modified:
    - triggarr/static/css/input.css
    - triggarr/templates/partials/stats_row.html
    - triggarr/static/css/output.css
    - tests/test_stats_health.py
decisions:
  - Kept .mini-bar CSS class for backward compatibility even though template no longer uses it
  - Renamed Episodes card label to Series to match artifact naming convention
metrics:
  duration: 150s
  completed: 2026-04-16T02:54:51Z
  tasks: 2/2
  files: 4
---

# Phase 61 Plan 01: Stat Cards Restyle Summary

Restyled all stat cards to artifact spec: text-[32px] hero numbers, Phosphor icons per card type, horizontal side-by-side mini bars with app-type colors, colored dot subtitles, and uniform p-5 padding. Added triggarr-primary and triggarr-elevated CSS tokens.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 3ae7154 | feat(61-01): restyle stat cards to artifact spec with hero numbers and Phosphor icons |
| 2 | 784dc8d | test(61-01): update stat card tests for artifact-spec classes and new assertions |

## Task Details

### Task 1: Add CSS tokens and update stats_row.html to artifact spec

- Added `--color-triggarr-primary: #22c55e` and `--color-triggarr-elevated: #233346` to input.css @theme block
- Restructured all 5 stat cards in stats_row.html:
  - Grab Rate: chart-line-up icon, text-[32px] hero, horizontal mini bars, removed gradient overlay and health badge
  - Movies: film-strip icon in radarr orange, colored dot subtitle "In Radarr"
  - Series (renamed from Episodes): television icon in sonarr blue, colored dot subtitle "In Sonarr"
  - Albums: music-notes icon in green, colored dot subtitle "In Lidarr"
  - Next Scan: clock-countdown icon in muted, calendar icon subtitle "Scheduled automatically"
- All cards use uniform p-5 padding, flex-col justify-between layout, shadow-sm
- Preserved all htmx attributes and Jinja2 conditionals unchanged

### Task 2: Update test_stats_health.py assertions

- Updated hero card test: text-4xl -> text-[32px], added tracking-widest and icon assertions
- Replaced health badge test with Phosphor icon test (badge removed per artifact D-09)
- Updated per-app bar test: removed mini-bar class assertion, added h-1 Tailwind utility assertions
- Added 4 new tests: phosphor icons, colored dot subtitles, label typography, horizontal mini bar layout
- All 12 tests pass

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED
