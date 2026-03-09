---
phase: 18-security-operations
plan: 02
subsystem: reliability
tags: [asyncio, graceful-shutdown, csrf, middleware, fastapi, testing]

# Dependency graph
requires:
  - phase: 17-foundation-db-preparation
    provides: shared DB connection and search_lock on app.state
  - phase: 18-01
    provides: scheduler.py already had lock-drain code committed
provides:
  - graceful shutdown with bounded lock drain before DB close (DEBT-06)
  - CSRF integration test confirming middleware covers /settings route (DEBT-02)
  - shutdown sequence tests verifying lock-drain behavior
affects: [19-radarr-tracking, 20-sonarr-tracking]

# Tech tracking
tech-stack:
  added: []
  patterns: [asyncio.wait_for for bounded lock drain on shutdown, integration testing with real router + middleware]

key-files:
  created: []
  modified:
    - fetcharr/search/scheduler.py
    - tests/test_middleware.py
    - tests/test_scheduler.py

key-decisions:
  - "Task 1 scheduler changes were already committed in 18-01 (fb388b4) -- no duplicate commit needed"
  - "Used builtin TimeoutError instead of asyncio.TimeoutError per ruff UP041"
  - "Split CSRF integration into two tests: cross-origin rejected (403) and same-origin passes (not 403)"

patterns-established:
  - "Integration test pattern: _make_settings_app() builds full app with router + middleware for realistic route testing"
  - "Shutdown test pattern: create_lifespan + async with for testing lifespan lifecycle without full app server"

requirements-completed: [DEBT-02, DEBT-06]

# Metrics
duration: 4min
completed: 2026-02-25
---

# Phase 18 Plan 02: Graceful Shutdown & CSRF Integration Summary

**Bounded lock-drain shutdown sequence (asyncio.wait_for 35s timeout) and CSRF integration test verifying OriginCheckMiddleware blocks cross-origin POST to /settings**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-25T18:17:30Z
- **Completed:** 2026-02-25T18:21:33Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Verified graceful shutdown lock-drain (asyncio.wait_for with 35s timeout) already in place from 18-01
- Added CSRF integration test proving OriginCheckMiddleware blocks cross-origin POST to real /settings route (DEBT-02)
- Added shutdown sequence tests proving lock-drain runs before DB close (DEBT-06)
- Fixed ruff lint violations (UP041 TimeoutError alias, I001 import sorting)

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix graceful shutdown to drain in-flight search cycle** - `fb388b4` (already committed in 18-01)
2. **Task 2: Add CSRF integration test for /settings route** - `5627b21` (test)
3. **Task 3: Add graceful shutdown test to test_scheduler.py** - `72e6fdc` (test)
4. **Lint fixes** - `fca1c76` (fix: ruff UP041 + I001)

## Files Created/Modified
- `fetcharr/search/scheduler.py` - Graceful shutdown with bounded lock drain (from 18-01) + TimeoutError fix
- `tests/test_middleware.py` - CSRF integration tests for /settings route with real router wiring
- `tests/test_scheduler.py` - Shutdown sequence tests verifying lock-drain behavior

## Decisions Made
- Task 1 (scheduler.py lock drain) was already committed as part of 18-01 plan execution (`fb388b4`). No duplicate commit was needed -- only lint fix applied.
- Used `raise_server_exceptions=False` in same-origin test to avoid 500 from missing state_path reaching the route handler. The test validates middleware behavior (not 403), not route handler correctness.
- Split `_make_settings_app()` factory into its own function for reuse across both integration tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff UP041 violation in scheduler.py**
- **Found during:** Verification (post-Task 3)
- **Issue:** `asyncio.TimeoutError` should be `TimeoutError` per ruff UP041 (Python 3.11+)
- **Fix:** Replaced `except asyncio.TimeoutError:` with `except TimeoutError:`
- **Files modified:** fetcharr/search/scheduler.py
- **Verification:** `uv run ruff check fetcharr/` passes
- **Committed in:** fca1c76

**2. [Rule 1 - Bug] Fixed ruff I001 import sorting in test_middleware.py**
- **Found during:** Verification (post-Task 3)
- **Issue:** `from fetcharr.web.routes import STATIC_DIR, router as fetcharr_router` flagged as unsorted
- **Fix:** Split into two separate import lines
- **Files modified:** tests/test_middleware.py
- **Verification:** `uv run ruff check tests/` passes
- **Committed in:** fca1c76

---

**Total deviations:** 2 auto-fixed (2 Rule 1 - bugs)
**Impact on plan:** Both are lint fixes required for CI compliance. No scope creep.

## Issues Encountered
- Task 1 changes (scheduler.py lock drain) were already committed in 18-01 execution. The edit was a no-op since the file already contained the target code. This is not an error -- the 18-01 plan bundled the scheduler fix with its rate limiter work.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- DEBT-02 (CSRF coverage gap) and DEBT-06 (graceful shutdown) are resolved
- All 192 tests passing, ruff clean
- Ready for Phase 19 (Radarr tracking) and Phase 20 (Sonarr tracking)

## Self-Check: PASSED

All files verified present, all commit hashes found in git log.

---
*Phase: 18-security-operations*
*Completed: 2026-02-25*
