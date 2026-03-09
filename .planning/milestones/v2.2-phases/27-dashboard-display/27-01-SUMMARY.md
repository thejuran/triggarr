---
phase: 27-dashboard-display
plan: 01
subsystem: ui, search, state
tags: [htmx, jinja2, tailwind, dashboard, eligible-count, skip-badge]

# Dependency graph
requires:
  - phase: 26-settings-ui-engine-integration
    provides: skip_unreleased config field and filter_unreleased_movies in engine pipeline
provides:
  - missing_eligible field in AppState TypedDict
  - eligible count stored after filtering in both Radarr and Sonarr cycles
  - "X of Y items" display format on dashboard app cards
  - conditional amber skip badge on Radarr card
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [eligible count tracking after pipeline filters, conditional Jinja2 badge rendering]

key-files:
  created: []
  modified:
    - triggarr/state.py
    - triggarr/search/engine.py
    - triggarr/web/routes.py
    - triggarr/templates/partials/app_card.html
    - tests/test_search.py
    - tests/test_web.py

key-decisions:
  - missing_eligible captures post-filter count for both Radarr (after filter_monitored + conditional filter_unreleased_movies) and Sonarr (after filter_sonarr_episodes + deduplicate_to_seasons)
  - skip badge restricted to Radarr only since Sonarr filtering is always-on and not user-controlled
  - cursor progress line uses missing_eligible for accuracy since cursor operates on post-filter list

metrics:
  duration_seconds: 608
  completed: "2026-03-09T12:33:00Z"
  tasks_completed: 2
  tasks_total: 2
  tests_before: 295
  tests_after: 300
---

# Phase 27 Plan 01: Dashboard Display Summary

Eligible-count tracking with "X of Y items" display and conditional amber skip badge on Radarr app cards.

## What Was Done

### Task 1: Add missing_eligible to state, engine, and routes (TDD)
- Added `missing_eligible: int | None` field to `AppState` TypedDict
- Engine stores `len(missing)` after filtering in `run_radarr_cycle` (captures count after both `filter_monitored` and conditional `filter_unreleased_movies`)
- Engine stores `len(missing_seasons)` after filtering + dedup in `run_sonarr_cycle`
- Routes pass `missing_eligible` and `skip_unreleased` to template context via `_build_app_context`
- **Commits:** `baff29d` (RED), `93fc652` (GREEN)

### Task 2: Update app card template with eligible/total display and skip badge
- Main count line shows "X of Y items" when both values available, falls back to "Y items" or em-dash
- Cursor progress line uses `missing_eligible` when available for accuracy
- Amber skip badge appears below cursor line only when: `skip_unreleased` is true AND app is Radarr AND `missing_eligible < missing_count`
- **Commit:** `48f8703`

## Deviations from Plan

None - plan executed exactly as written.

## Verification

- All 300 tests pass (5 new tests added)
- Ruff lint clean
- All must_have artifacts verified present in source files

## Self-Check: PASSED
