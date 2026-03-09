---
phase: 06-bug-fixes-and-resilience
plan: 03
subsystem: web
tags: [asyncio, concurrency, pydantic, loguru, redaction, validation]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "Loguru logging setup with redaction filter, Settings model"
  - phase: 02-search-engine
    provides: "Search cycle functions and APScheduler integration"
  - phase: 03-web-ui
    provides: "Web routes with settings editor and search-now trigger"
  - phase: 06-bug-fixes-and-resilience
    provides: "06-01 state hardening, 06-02 exception hierarchy fixes"
provides:
  - "asyncio.Lock serializing scheduler and manual search-now cycles (QUAL-01)"
  - "Pydantic validate-before-write preventing invalid config on disk (QUAL-02)"
  - "Custom sink-based log redaction covering exception tracebacks (QUAL-05)"
  - "Automatic log redaction refresh when API keys change via settings editor"
affects: [07-test-coverage]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Custom loguru sink for full-output redaction", "asyncio.Lock on app.state for shared concurrency", "Validate-before-write with Pydantic model"]

key-files:
  created: []
  modified: ["fetcharr/logging.py", "fetcharr/search/scheduler.py", "fetcharr/web/routes.py", "tests/test_logging.py"]

key-decisions:
  - "Custom sink replaces filter for traceback redaction (filter only sees record['message'], sink sees full formatted output)"
  - "colorize=False on custom sink because loguru cannot auto-detect terminal on function sinks"
  - "asyncio.Lock created once in lifespan, shared via app.state.search_lock"
  - "Client-is-None check stays outside lock scope (no need to acquire lock for a no-op return)"
  - "Settings validated via SettingsModel(**new_config) before any disk write -- invalid config redirects back"
  - "Log redaction refreshed after every settings save to pick up changed API keys"

patterns-established:
  - "Custom sink pattern: create_redacting_sink(secrets, stream) returns a function that str(message) and replaces secrets"
  - "Shared lock pattern: asyncio.Lock on app.state accessed by both scheduler jobs and request handlers"
  - "Validate-before-write pattern: construct Pydantic model from dict, reject on any exception, write only on success"

requirements-completed: [QUAL-01, QUAL-02, QUAL-05]

# Metrics
duration: 2min
completed: 2026-02-24
---

# Phase 06 Plan 03: Concurrency Lock, Settings Validation, and Traceback Redaction Summary

**asyncio.Lock serializing search cycles, Pydantic validate-before-write for settings, and custom loguru sink redacting secrets in exception tracebacks**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-24T14:27:14Z
- **Completed:** 2026-02-24T14:29:39Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Search cycles (scheduler + manual search-now) are now serialized via asyncio.Lock -- no state corruption from concurrent execution
- Settings are validated via Pydantic model BEFORE writing to disk -- invalid config never reaches the TOML file
- Log redaction switched from filter (message-only) to custom sink (full formatted output including tracebacks) -- API keys in exception stack traces are now redacted
- Log redaction automatically refreshes when API keys change through the settings editor
- New test proves traceback redaction works by raising an exception containing a secret and verifying it is redacted in output

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace filter-based log redaction with custom sink for traceback coverage** - `3957e87` (fix)
2. **Task 2: Add asyncio.Lock in scheduler and wire it into make_search_job** - `4c3bb70` (fix)
3. **Task 3: Add lock in search_now, validate-before-write in save_settings, and redaction refresh** - `1f339c2` (fix)

## Files Created/Modified
- `fetcharr/logging.py` - Replaced create_redaction_filter with create_redacting_sink (custom sink, not filter), updated setup_logging to use sink with colorize=False
- `fetcharr/search/scheduler.py` - Added asyncio import, created asyncio.Lock on app.state.search_lock in lifespan, wrapped job body with lock acquisition
- `fetcharr/web/routes.py` - Added search_lock acquisition in search_now, validate-before-write via SettingsModel in save_settings, log redaction refresh after settings save
- `tests/test_logging.py` - Updated existing tests to use sink-based approach, added test_redaction_covers_tracebacks

## Decisions Made
- Custom sink chosen over filter because loguru filters only see `record["message"]` -- they cannot redact secrets that appear in exception tracebacks formatted by loguru after the filter runs
- `colorize=False` is intentional -- the sink is a function (not a file stream), so loguru cannot auto-detect terminal support; container logs also don't support ANSI codes reliably
- `asyncio.Lock` is non-reentrant, which is correct here since neither the scheduler job nor search_now handler calls the other
- `SettingsModel` alias used for the import to avoid potential conflicts with other Settings imports
- Broad `except Exception` used for validation catch because `Settings(**new_config)` can raise TypeError, ValidationError, or other errors from malformed data

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All Phase 6 bug fixes complete (QUAL-01 through QUAL-06 resolved across plans 01-03)
- Ready for Phase 7 (Test Coverage)

## Self-Check: PASSED

- FOUND: fetcharr/logging.py
- FOUND: fetcharr/search/scheduler.py
- FOUND: fetcharr/web/routes.py
- FOUND: tests/test_logging.py
- FOUND: 3957e87 (Task 1 commit)
- FOUND: 4c3bb70 (Task 2 commit)
- FOUND: 1f339c2 (Task 3 commit)
- VERIFIED: 92/92 tests pass

---
*Phase: 06-bug-fixes-and-resilience*
*Completed: 2026-02-24*
