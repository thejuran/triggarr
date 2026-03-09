---
phase: 02-search-engine
plan: 03
subsystem: search
tags: [apscheduler, fastapi, uvicorn, lifespan, scheduler, pytest]

# Dependency graph
requires:
  - phase: 02-search-engine/02
    provides: "run_radarr_cycle and run_sonarr_cycle async cycle functions"
  - phase: 02-search-engine/01
    provides: "Search engine utility functions and client search methods"
  - phase: 01-foundation
    provides: "Settings model, state persistence, startup orchestration"
provides:
  - "APScheduler integration via create_lifespan factory for FastAPI"
  - "Configurable interval jobs for Radarr and Sonarr with immediate first run"
  - "Uvicorn-served FastAPI entry point with lifespan-managed scheduler"
  - "19-test search engine test suite covering all utility functions"
affects: [03-web-ui]

# Tech tracking
tech-stack:
  added: [apscheduler-3.x]
  patterns:
    - "FastAPI lifespan context manager wrapping APScheduler lifecycle"
    - "State shared by reference via nonlocal in job closures (single event loop)"
    - "Long-lived clients created in lifespan, closed on shutdown"

key-files:
  created:
    - fetcharr/search/scheduler.py
    - tests/test_search.py
  modified:
    - fetcharr/__main__.py
    - fetcharr/startup.py
    - pyproject.toml

key-decisions:
  - "APScheduler 3.x chosen over 4.x (4.x still alpha, 3.x is stable)"
  - "Uvicorn log_level=warning to keep loguru as sole log channel"
  - "State shared by reference via nonlocal (safe: AsyncIOScheduler runs on same event loop)"

patterns-established:
  - "create_lifespan factory pattern: settings + state_path -> FastAPI lifespan context manager"
  - "Job wrappers catch all exceptions to prevent scheduler crashes"

requirements-completed: [SRCH-08]

# Metrics
duration: 2min
completed: 2026-02-23
---

# Phase 2 Plan 3: Scheduler and Tests Summary

**APScheduler-driven search cycles via FastAPI lifespan with configurable intervals, state persistence after every cycle, and 19-test utility function suite**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-24T03:34:13Z
- **Completed:** 2026-02-24T03:36:32Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- APScheduler wired into FastAPI lifespan with create_lifespan factory producing a reusable context manager
- Independent Radarr/Sonarr interval jobs with configurable intervals and immediate first run (next_run_time=now)
- Entry point upgraded from placeholder to uvicorn-served FastAPI app with full scheduler lifecycle
- 19 comprehensive tests covering all search engine utility functions with edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1: Create APScheduler integration with FastAPI lifespan and update entry point** - `e515c1b` (feat)
2. **Task 2: Create search engine test suite** - `7657b30` (test)

## Files Created/Modified
- `fetcharr/search/scheduler.py` - create_lifespan factory: APScheduler with interval jobs, long-lived clients, state persistence, clean shutdown
- `fetcharr/__main__.py` - FastAPI app with lifespan-managed scheduler served via uvicorn on port 8080
- `fetcharr/startup.py` - Updated docstring noting temporary vs long-lived client distinction
- `pyproject.toml` - Added apscheduler>=3.11,<4 dependency
- `tests/test_search.py` - 19 tests: filter_monitored, slice_batch, append_search_log, deduplicate_to_seasons, filter_sonarr_episodes

## Decisions Made
- APScheduler 3.x chosen over 4.x because 4.x is still alpha; 3.x is battle-tested with AsyncIOScheduler
- Uvicorn log_level set to "warning" so uvicorn access logs do not clutter the loguru output
- State shared by reference using nonlocal in job closures -- safe because AsyncIOScheduler runs on the same event loop (no threading)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Search engine is now a fully autonomous daemon: cycles run on schedule, state persists across restarts
- Phase 2 (Search Engine) is complete: config, clients, utilities, cycles, scheduler, tests all delivered
- 40 total tests pass (21 foundation + 19 search engine)
- Ready for Phase 3 (Web UI) which will add the htmx dashboard on top of this FastAPI app

## Self-Check: PASSED

- FOUND: fetcharr/search/scheduler.py
- FOUND: fetcharr/__main__.py
- FOUND: tests/test_search.py
- FOUND: 02-03-SUMMARY.md
- FOUND: e515c1b (Task 1 commit)
- FOUND: 7657b30 (Task 2 commit)

All created files verified on disk. All commit hashes found in git log.

---
*Phase: 02-search-engine*
*Completed: 2026-02-23*
