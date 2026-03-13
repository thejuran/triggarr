---
phase: 42-dashboard-enhancements
plan: 02
subsystem: web-ui
tags: [htmx, templates, dashboard, health-summary, tag-warnings, stats-filter]
dependency_graph:
  requires: [42-01]
  provides: [dashboard-health-summary, tag-warning-badges, stats-instance-filter]
  affects: [dashboard.html, app_card.html, stats_row.html, health_summary.html, routes.py]
tech_stack:
  added: []
  patterns: [htmx-hx-include-preserves-selection, conditional-grid-columns, amber-warning-badge]
key_files:
  created:
    - triggarr/templates/partials/health_summary.html
  modified:
    - triggarr/templates/partials/app_card.html
    - triggarr/templates/partials/stats_row.html
    - triggarr/templates/dashboard.html
    - triggarr/web/routes.py
decisions:
  - Health summary card placed above stats row (not between stats and app cards)
metrics:
  duration: ~10min
  completed: "2026-03-13"
---

# Phase 42 Plan 02: Dashboard UI Templates Summary

Jinja2 templates for health summary card, tag warning badges, and instance filter dropdown using htmx partial patterns.

## What Was Done

### Task 1: Create health summary partial, tag warning badge, stats filter dropdown, and conditional stats cards

- Created `health_summary.html` partial with 30s htmx polling, showing connected/disconnected/pending instance counts with green/red color coding
- Updated `app_card.html` with amber warning badge for tag warnings (single and combined two-warning format)
- Updated `stats_row.html` with `hx-include="[name='instance']"` to preserve dropdown selection across polls, and conditional card visibility (Movies hidden for Sonarr, Episodes hidden for Radarr)
- Updated `dashboard.html` with stats filter dropdown above stats row and health summary include above app cards grid
- **Commit:** 95ae3d4

### Task 2: Visual verification (checkpoint)

- User verified all three features in browser
- Post-checkpoint fix: moved health summary card above stats row per context decision
- **Commit:** e73237c

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Health summary card position**
- **Found during:** Checkpoint verification
- **Issue:** Health summary was placed between stats row and app cards; context specified it should be above stats row
- **Fix:** Moved the health_summary include above the stats dropdown/row in dashboard.html
- **Files modified:** triggarr/templates/partials/health_summary.html, triggarr/templates/dashboard.html
- **Commit:** e73237c

## Verification

- All 449 tests pass
- Ruff lint clean
- Visual verification approved by user

## Self-Check: PASSED
