---
phase: 06-bug-fixes-and-resilience
plan: 02
subsystem: api
tags: [httpx, pydantic, error-handling, resilience]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "Base ArrClient with retry logic and connection validation"
  - phase: 02-search-engine
    provides: "Search engine with deduplicate_to_seasons and cycle functions"
provides:
  - "Broadened retry catch (TransportError) covering all transient transport failures"
  - "ValidationError catch in validate_connection for malformed API responses"
  - "Safe .get() in deduplicate_to_seasons skipping malformed episodes"
  - "Simplified cycle abort catches using httpx.HTTPError + pydantic.ValidationError"
affects: [07-test-coverage]

# Tech tracking
tech-stack:
  added: []
  patterns: ["TransportError as broad retry catch", "pydantic.ValidationError catch at API boundaries"]

key-files:
  created: []
  modified: ["fetcharr/clients/base.py", "fetcharr/search/engine.py"]

key-decisions:
  - "TransportError replaces ConnectError+TimeoutException (covers RemoteProtocolError, ReadError, etc.)"
  - "httpx.HTTPError replaces redundant subcatches in cycle abort handlers"
  - "ValidationError added to cycle abort catches for get_paginated model_validate failures"

patterns-established:
  - "Retry catch pattern: httpx.HTTPStatusError + httpx.TransportError covers all retryable failures"
  - "Cycle abort pattern: httpx.HTTPError + pydantic.ValidationError for maximum resilience"
  - "Safe dict access pattern: .get() with None check and continue for optional fields"

requirements-completed: [QUAL-06]

# Metrics
duration: 2min
completed: 2026-02-24
---

# Phase 06 Plan 02: Exception Hierarchy and API Resilience Summary

**Broadened httpx retry catch to TransportError, added ValidationError handling in validate_connection, safe .get() in deduplicate_to_seasons, and simplified cycle abort catches**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-24T14:22:22Z
- **Completed:** 2026-02-24T14:24:10Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `_request_with_retry` now catches `httpx.TransportError` (parent of TimeoutException, ConnectError, ProtocolError) covering RemoteProtocolError and other transient failures
- `validate_connection` catches `pydantic.ValidationError` from malformed *arr API responses, returning False with a warning instead of crashing
- `deduplicate_to_seasons` uses `.get()` with None check to skip episode records missing seriesId or seasonNumber instead of crashing with KeyError
- Cycle abort catches in `run_radarr_cycle` and `run_sonarr_cycle` simplified from redundant subcatches to `httpx.HTTPError + pydantic.ValidationError`

## Task Commits

Each task was committed atomically:

1. **Task 1: Broaden retry catch to TransportError and add ValidationError handling** - `b8125c8` (fix)
2. **Task 2: Fix deduplicate_to_seasons missing fields and simplify cycle abort catches** - `c04b81f` (fix)

## Files Created/Modified
- `fetcharr/clients/base.py` - Broadened retry catch, added pydantic import and ValidationError catch in validate_connection
- `fetcharr/search/engine.py` - Safe .get() in deduplicate_to_seasons, simplified cycle abort catches, added pydantic import

## Decisions Made
- Used `httpx.TransportError` (not `httpx.HTTPError`) for retry catch because HTTPStatusError is not a TransportError subclass and needs separate handling for retry logic
- Used `httpx.HTTPError` for cycle abort because it is the common parent of both HTTPStatusError and TransportError, catching all httpx failure modes
- Added `pydantic.ValidationError` separately to cycle abort since it is not an httpx exception subclass

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Error handling hardened for all known httpx exception hierarchy gaps
- Ready for 06-03 (next bug fix plan) or Phase 7 (test coverage)

## Self-Check: PASSED

- FOUND: fetcharr/clients/base.py (TransportError in retry, ValidationError in validate_connection)
- FOUND: fetcharr/search/engine.py (ep.get() in deduplicate, HTTPError+ValidationError in cycles)
- FOUND: commit b8125c8 (Task 1)
- FOUND: commit c04b81f (Task 2)
- VERIFIED: 27/27 tests pass (8 client + 19 search)

---
*Phase: 06-bug-fixes-and-resilience*
*Completed: 2026-02-24*
