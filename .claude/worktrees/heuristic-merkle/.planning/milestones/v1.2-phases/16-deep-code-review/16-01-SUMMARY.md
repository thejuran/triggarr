---
phase: 16-deep-code-review
plan: 01
subsystem: security
tags: [xss, ssrf, aiosqlite, jinja2, tojson, input-validation]

# Dependency graph
requires:
  - phase: 15-search-history-ui
    provides: history_results.html template, db.py search history, validation.py SSRF checks
provides:
  - XSS-safe hx-vals attribute using tojson filter
  - Deterministic aiosqlite cursor cleanup via async with
  - ZeroDivisionError guard on per_page/page parameters
  - Expanded SSRF blocklist (Azure, Alibaba metadata, loopback, unspecified addresses)
  - 7 regression tests covering W1, W5, W7 findings
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "hx-vals double-quoted tojson pattern for safe JSON attribute rendering"
    - "async with db.execute() for deterministic aiosqlite cursor cleanup"
    - "Input parameter guards at function top before any arithmetic"

key-files:
  created: []
  modified:
    - fetcharr/templates/partials/history_results.html
    - fetcharr/db.py
    - fetcharr/web/validation.py
    - tests/test_web.py
    - tests/test_validation.py
    - tests/test_db.py

key-decisions:
  - "Used is_unspecified in addition to is_loopback to block 0.0.0.0 (Python ipaddress treats it as unspecified, not loopback)"
  - "Changed error message from 'Link-local address blocked' to 'Blocked address' to cover loopback and unspecified"

patterns-established:
  - "hx-vals tojson: always use double-quoted tojson filter for hx-vals attributes to prevent XSS"
  - "Cursor management: always use async with db.execute() for aiosqlite cursor lifecycle"

requirements-completed: []

# Metrics
duration: 3min
completed: 2026-02-24
---

# Phase 16 Plan 01: Warning Fixes Summary

**Patched 4 code review warnings (XSS hx-vals, aiosqlite cursor leaks, zero-division guard, SSRF blocklist gaps) with 7 regression tests**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-24T22:45:30Z
- **Completed:** 2026-02-24T22:48:04Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- W1: hx-vals attribute now uses double-quoted tojson filter, eliminating single-quote XSS breakout vector
- W4: All 3 bare aiosqlite cursor patterns replaced with async with for deterministic cleanup
- W5: get_search_history guards per_page < 1 and page < 1 to prevent ZeroDivisionError
- W7: SSRF blocklist expanded with Azure metadata, Alibaba metadata, and loopback/unspecified address checks
- 7 new regression tests covering all security-relevant fixes

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix W1 (XSS), W4 (cursors), W5 (zero division), W7 (SSRF blocklist)** - `8cc4e28` (fix)
2. **Task 2: Add regression tests for W1 (XSS), W5 (zero-division), W7 (SSRF blocklist)** - `76acecb` (test)

## Files Created/Modified
- `fetcharr/templates/partials/history_results.html` - hx-vals switched from single-quoted JSON to double-quoted tojson filter
- `fetcharr/db.py` - 3 cursor sites wrapped in async with; per_page/page guards added
- `fetcharr/web/validation.py` - BLOCKED_HOSTS expanded; is_loopback + is_unspecified checks added
- `tests/test_web.py` - W1 XSS regression test added
- `tests/test_validation.py` - 5 W7 SSRF regression tests added; existing assertion updated for new error message
- `tests/test_db.py` - W5 zero-division regression test added

## Decisions Made
- Used `is_unspecified` in addition to `is_loopback` to block `0.0.0.0` -- Python's ipaddress module classifies it as unspecified, not loopback
- Changed error message from "Link-local address blocked" to "Blocked address" to cover all blocked address types uniformly

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added is_unspecified check for 0.0.0.0 blocking**
- **Found during:** Task 2 (regression test for W7)
- **Issue:** Plan specified is_loopback to block 0.0.0.0, but Python's ipaddress module classifies 0.0.0.0 as is_unspecified (not is_loopback), so the test failed
- **Fix:** Added `or addr.is_unspecified` to the condition in validation.py
- **Files modified:** fetcharr/web/validation.py
- **Verification:** test_zero_address_blocked passes
- **Committed in:** 76acecb (Task 2 commit)

**2. [Rule 1 - Bug] Refined W1 XSS test to target hx-vals attribute specifically**
- **Found during:** Task 2 (W1 regression test)
- **Issue:** Checking `"onmouseover=" not in response.text` was too broad -- the XSS payload appears safely HTML-entity-escaped in the search input's value attribute, causing false positive
- **Fix:** Used regex to extract the hx-vals attribute content and assert onmouseover is absent from it specifically
- **Files modified:** tests/test_web.py
- **Verification:** test_history_results_hx_vals_no_single_quote_breakout passes
- **Committed in:** 76acecb (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bug fixes)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 4 warning-level findings from the code review are resolved
- 174 total tests pass with no regressions
- Ready for Plan 02 (informational findings) or release preparation

## Self-Check: PASSED

- All 6 modified files verified on disk
- Commit 8cc4e28 (Task 1) verified in git log
- Commit 76acecb (Task 2) verified in git log
- 174 tests pass, 0 ruff violations

---
*Phase: 16-deep-code-review*
*Completed: 2026-02-24*
