---
phase: 03-web-ui
plan: 03
subsystem: ui
tags: [fastapi, htmx, jinja2, toml, config-editor, hot-reload, tailwindcss]

# Dependency graph
requires:
  - phase: 03-web-ui/02
    provides: Dashboard templates, app cards, search log, htmx polling partials
  - phase: 02-search-engine/03
    provides: APScheduler integration, make_search_job factory, search cycle functions
provides:
  - Config editor with masked API keys and TOML write/reload
  - Hot-reload of settings, scheduler jobs, and API clients on save
  - Search Now button for on-demand search cycles via htmx
  - Web route test suite (12 tests)
affects: [04-hardening]

# Tech tracking
tech-stack:
  added: [python-multipart, tomli-w]
  patterns: [PRG-redirect, api-key-masking, hot-reload-scheduler, htmx-inline-update]

key-files:
  created:
    - tests/test_web.py
  modified:
    - fetcharr/web/routes.py
    - fetcharr/templates/settings.html
    - fetcharr/templates/partials/app_card.html
    - fetcharr/static/css/output.css
    - pyproject.toml

key-decisions:
  - "API key masking: password field with empty value + placeholder (never the real key in HTML)"
  - "python-multipart added as runtime dependency for FastAPI form parsing"
  - "Client recreation on URL/key change to avoid stale connections after config edit"

patterns-established:
  - "PRG pattern: POST /settings writes TOML, reloads, redirects 303 to GET /settings"
  - "Hot-reload: save_settings swaps clients, reschedules/adds/removes jobs without restart"
  - "AsyncMock for client.close() in tests since httpx clients have async close methods"

requirements-completed: [WEBU-05, WEBU-07, WEBU-08]

# Metrics
duration: 3min
completed: 2026-02-23
---

# Phase 3 Plan 3: Config Editor and Search Now Summary

**Config editor with masked API keys, TOML hot-reload with scheduler/client management, and htmx Search Now button on dashboard cards**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-24T04:38:54Z
- **Completed:** 2026-02-24T04:42:40Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Config editor at /settings with pre-filled form, masked API keys, per-app enable toggles
- POST /settings writes TOML, reloads settings, reschedules/adds/removes scheduler jobs, recreates clients on URL/key changes
- Search Now button on dashboard cards triggers immediate search cycles via htmx POST with inline card update
- 12 web route tests covering all routes, security invariants, and edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1: Config editor routes, settings template, hot-reload, and search-now endpoint** - `81c3a9f` (feat)
2. **Task 2: Web route test suite** - `b63fad6` (test)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified
- `fetcharr/web/routes.py` - Added GET/POST /settings, POST /api/search-now/{app_name} with full scheduler management
- `fetcharr/templates/settings.html` - Config editor form with masked API keys, per-app sections, enable toggles
- `fetcharr/templates/partials/app_card.html` - Added Search Now button with htmx POST
- `fetcharr/static/css/output.css` - Recompiled Tailwind CSS for new template classes
- `tests/test_web.py` - 12 tests: dashboard, settings masking, TOML write/preserve/replace, htmx, search-now
- `pyproject.toml` - Added python-multipart dependency for form parsing

## Decisions Made
- API key masking uses `type="password"` with `value=""` and conditional placeholder; empty submission means "keep existing key"
- python-multipart added as runtime dependency (required by FastAPI for form data parsing)
- Client recreation only triggers when URL or API key actually changes (avoids unnecessary reconnection)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added python-multipart dependency**
- **Found during:** Task 2 (Web route test suite)
- **Issue:** FastAPI requires python-multipart for form parsing; POST /settings tests failed with AssertionError
- **Fix:** Installed python-multipart and added to pyproject.toml dependencies
- **Files modified:** pyproject.toml
- **Verification:** All 12 web tests pass
- **Committed in:** b63fad6 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential dependency for form parsing. No scope creep.

## Issues Encountered
- Mock clients needed AsyncMock for close() method since httpx client close is async; fixed in test fixture

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 3 Web UI is feature-complete: dashboard with polling, config editor, search-now
- Ready for Phase 4 hardening (error handling, security headers, Docker deployment)
- 52 total tests passing across all modules

## Self-Check: PASSED

All 7 files verified present. Both task commits (81c3a9f, b63fad6) verified in git log.

---
*Phase: 03-web-ui*
*Completed: 2026-02-23*
