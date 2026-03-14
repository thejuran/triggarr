---
phase: 44-deep-review-fixes
plan: 01
subsystem: security
tags: [xss, csrf, version-parsing, input-validation, httpx]

# Dependency graph
requires:
  - phase: 43-update-notification-cleanup
    provides: update_check module and _update_info dict pattern
provides:
  - 8 security and correctness fixes from deep code review
  - Pre-release version parsing with regex
  - XSS-safe tag autocomplete
  - CSRF protection on dismiss_migration
  - html_url validation for update check
  - Stale tag warning badge clearing on disconnect
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "html.escape for user-derived HTML attribute values"
    - "HX-Request header check for htmx-only endpoints"
    - "re.match for extracting leading integers from version segments"
    - "Split on hyphen before dot-split for pre-release version stripping"

key-files:
  created: []
  modified:
    - triggarr/update_check.py
    - triggarr/search/engine.py
    - triggarr/search/scheduler.py
    - triggarr/web/routes.py
    - tests/test_update_check.py
    - tests/test_search.py
    - tests/test_web.py

key-decisions:
  - "Pre-release suffix stripped by splitting on hyphen before dot-split, with re.match fallback for .devN suffixes"
  - "Instance filter validation uses trailing-slash stripping instead of strict app/instance format to match existing UI behavior"

patterns-established:
  - "HX-Request header guard: htmx-only DELETE endpoints check request.headers.get('HX-Request') and return 403 if missing"
  - "html.escape in f-string HTML attributes: always escape user-derived values in HTML option/input values"

requirements-completed: []

# Metrics
duration: 27min
completed: 2026-03-13
---

# Phase 44 Plan 01: Deep Review Fixes Summary

**8 targeted security and correctness fixes: XSS-safe autocomplete, CSRF-guarded dismiss, pre-release version parsing, html_url validation, stale badge clearing, redundant exception removal, empty-dict window fix, instance filter sanitization**

## Performance

- **Duration:** 27 min
- **Started:** 2026-03-14T00:15:43Z
- **Completed:** 2026-03-14T00:42:43Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Fixed 4 warning-level issues: empty-dict window in update_check_job, stale tag badges on disconnect, XSS in tag autocomplete, html_url validation
- Fixed 4 medium-level issues: instance filter sanitization, pre-release version parsing, redundant httpx.TimeoutException, CSRF on dismiss_migration
- All 466 tests pass (302 existing + 164 new/updated), zero ruff violations
- TDD approach: wrote 11 failing tests first, then implemented all 8 fixes

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Add failing tests** - `948606f` (test)
2. **Task 1 (GREEN): Apply all 8 fixes** - `833a368` (feat)
3. **Task 2: Full suite verification** - no code changes, verification only

## Files Created/Modified
- `triggarr/update_check.py` - Pre-release version parsing with re.match, html_url validation, redundant TimeoutException removed
- `triggarr/search/engine.py` - tag_warnings=[] in Radarr and Sonarr except blocks for connectivity failure
- `triggarr/search/scheduler.py` - Removed _update_info.clear() to prevent empty-dict window
- `triggarr/web/routes.py` - html.escape in tag autocomplete, CSRF guard on dismiss_migration, instance filter sanitization
- `tests/test_update_check.py` - Pre-release version parametrize cases, non-GitHub html_url rejection test
- `tests/test_search.py` - Tag warnings cleared on connectivity failure tests (Radarr + Sonarr)
- `tests/test_web.py` - CSRF dismiss tests, updated existing dismiss tests with HX-Request header

## Decisions Made
- Pre-release suffix stripped by splitting on hyphen before dot-split, with re.match fallback for .devN suffixes in dot-separated segments
- Instance filter validation uses trailing-slash stripping instead of strict "app/instance" format to match existing UI behavior (history page builds filter values from bare instance_id column values)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adjusted instance filter validation to match UI behavior**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Plan specified strict "app_type/instance" format validation for instance_filter, but existing UI sends bare instance names (e.g., "4K" not "radarr/4K") derived from DB instance_id column
- **Fix:** Changed validation to strip trailing slashes and reject empty values instead of requiring "/" format
- **Files modified:** triggarr/web/routes.py
- **Verification:** All 99 web tests pass including existing instance filter tests
- **Committed in:** 833a368

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Adjusted validation scope to prevent regression in existing UI. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All deep review issues resolved
- Ready for v2.3 release tagging after UAT

---
*Phase: 44-deep-review-fixes*
*Completed: 2026-03-13*
