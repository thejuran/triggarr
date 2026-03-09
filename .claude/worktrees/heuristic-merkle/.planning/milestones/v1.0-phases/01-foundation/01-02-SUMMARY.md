---
phase: 01-foundation
plan: 02
subsystem: api-clients
tags: [httpx, async, pagination, retry, radarr, sonarr, arr-api]

# Dependency graph
requires:
  - phase: 01-01
    provides: "Package scaffolding, Pydantic config models with SecretStr API keys"
provides:
  - ArrClient base class with httpx async HTTP, pagination, retry, and connection validation
  - RadarrClient for wanted/missing and wanted/cutoff movie list fetching
  - SonarrClient for wanted/missing and wanted/cutoff episode list fetching with includeSeries
  - PaginatedResponse and SystemStatus response models for *arr API parsing
affects: [01-03, 02-search-engine, 03-web-ui]

# Tech tracking
tech-stack:
  added: []
  patterns: [httpx.AsyncClient with X-Api-Key header auth, single-retry with 2s delay, paginated endpoint exhaustion, context manager lifecycle]

key-files:
  created:
    - fetcharr/models/arr.py
    - fetcharr/clients/base.py
    - fetcharr/clients/radarr.py
    - fetcharr/clients/sonarr.py
  modified:
    - fetcharr/clients/__init__.py

key-decisions:
  - "Content-Type: application/json set on all requests for Sonarr v4 strict enforcement compatibility"
  - "validate_connection calls /api/v3/system/status directly (no retry) for clear startup diagnostics"
  - "Pagination terminates on zero records OR page*pageSize >= totalRecords for correctness on all edge cases"

patterns-established:
  - "ArrClient subclass pattern: thin wrapper setting _app_name and calling get_paginated with endpoint-specific params"
  - "Retry pattern: single retry with 2s delay for transient failures, re-raise on second failure"
  - "Paginated fetch: 1-indexed pages, sortKey=id, terminate on empty or total reached"

requirements-completed: [CONN-01, CONN-02]

# Metrics
duration: 2min
completed: 2026-02-23
---

# Phase 1 Plan 2: API Clients Summary

**httpx async clients for Radarr and Sonarr with paginated list fetching, single-retry logic, and connection validation**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-24T02:42:08Z
- **Completed:** 2026-02-24T02:44:03Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- ArrClient base class wrapping httpx.AsyncClient with X-Api-Key header, Content-Type header, and 30s timeout
- Paginated endpoint fetching that exhausts all pages with zero-record termination and item count logging
- Single-retry with 2-second delay for transient HTTP, connection, and timeout failures
- Connection validation against /api/v3/system/status with specific error messages for 401, ConnectError, TimeoutException
- RadarrClient and SonarrClient subclasses with wanted/missing and wanted/cutoff endpoint methods

## Task Commits

Each task was committed atomically:

1. **Task 1: Create response models and ArrClient base class with pagination and retry** - `d404c20` (feat)
2. **Task 2: Create RadarrClient and SonarrClient subclasses with wanted/cutoff methods** - `175c19d` (feat)

## Files Created/Modified
- `fetcharr/models/arr.py` - PaginatedResponse and SystemStatus Pydantic models for *arr API data
- `fetcharr/clients/base.py` - ArrClient base class with get/post, get_paginated, retry, validate_connection, context manager
- `fetcharr/clients/radarr.py` - RadarrClient with wanted/missing and wanted/cutoff movie endpoints
- `fetcharr/clients/sonarr.py` - SonarrClient with wanted/missing and wanted/cutoff episode endpoints (includeSeries=true)
- `fetcharr/clients/__init__.py` - Package exports for RadarrClient and SonarrClient

## Decisions Made
- Content-Type: application/json header set on all requests (not just POST) for Sonarr v4 strict enforcement compatibility per research pitfall #3
- validate_connection calls system/status directly without retry wrapper, since startup validation benefits from immediate clear error reporting rather than silent retries
- Pagination terminates on both zero-record response AND page*pageSize >= totalRecords to handle edge cases where totalRecords changes mid-fetch

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- RadarrClient and SonarrClient ready for Plan 03 startup validation flow
- validate_connection() returns bool for startup orchestration
- get_wanted_missing() and get_wanted_cutoff() ready for Phase 2 search engine
- Context manager support (async with) for clean resource management

## Self-Check: PASSED

All 5 files verified on disk (4 created, 1 modified). Both task commits (d404c20, 175c19d) verified in git log.

---
*Phase: 01-foundation*
*Completed: 2026-02-23*
