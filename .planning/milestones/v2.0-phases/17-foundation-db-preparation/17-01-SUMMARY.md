---
phase: 17-foundation-db-preparation
plan: 01
subsystem: config
tags: [pydantic, toml, config, general-settings]

# Dependency graph
requires:
  - phase: 16-deep-code-review
    provides: "Stable codebase after v1.2 deep review"
provides:
  - "GeneralConfig with max_history_rows, request_timeout, page_size, tracking_window_minutes, tracking_poll_seconds"
  - "DEFAULT_CONFIG TOML template with commented entries for all new general settings"
  - "make_settings test helper with GeneralConfig override support"
affects: [17-02, 17-03, 18-connection-manager, 19-radarr-tracking, 20-sonarr-tracking]

# Tech tracking
tech-stack:
  added: []
  patterns: ["commented TOML defaults for optional config fields"]

key-files:
  created: []
  modified:
    - fetcharr/models/config.py
    - fetcharr/config.py
    - tests/conftest.py

key-decisions:
  - "No validators added -- Pydantic handles type coercion for simple typed fields"
  - "All new TOML entries commented out to match existing convention"

patterns-established:
  - "v2.0 config fields grouped with comment separator in GeneralConfig"
  - "make_settings accepts optional GeneralConfig for downstream test customization"

requirements-completed: [DEBT-03, DEBT-07, DEBT-08, TRACK-07]

# Metrics
duration: 1min
completed: 2026-02-24
---

# Phase 17 Plan 01: Config Fields Summary

**Five new GeneralConfig fields (max_history_rows, request_timeout, page_size, tracking_window_minutes, tracking_poll_seconds) with TOML template entries and test helper support**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-25T01:00:22Z
- **Completed:** 2026-02-25T01:01:30Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added 5 typed fields to GeneralConfig with correct defaults for DEBT-03, DEBT-07, DEBT-08, TRACK-07
- Updated DEFAULT_CONFIG TOML template with commented-out entries for all new fields
- Extended make_settings test helper to accept optional GeneralConfig override

## Task Commits

Each task was committed atomically:

1. **Task 1: Add new fields to GeneralConfig model** - `74aabf7` (feat)
2. **Task 2: Update DEFAULT_CONFIG template and test helper** - `ff4e399` (feat)

## Files Created/Modified
- `fetcharr/models/config.py` - Added 5 new GeneralConfig fields with defaults
- `fetcharr/config.py` - Added 5 commented TOML entries to DEFAULT_CONFIG template
- `tests/conftest.py` - Added GeneralConfig import and optional general parameter to make_settings

## Decisions Made
- No validators added -- Pydantic handles type coercion automatically for these simple typed fields
- All new TOML entries are commented out, matching the existing convention of showing defaults as comments

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Config fields in place for downstream plans to wire through the application
- Plan 17-02 can reference these fields for DB schema migration
- Plan 17-03 can use make_settings with custom GeneralConfig in tests

## Self-Check: PASSED

All files exist. All commits verified.

---
*Phase: 17-foundation-db-preparation*
*Completed: 2026-02-24*
