---
phase: 05-security-hardening
plan: 01
subsystem: security
tags: [csrf, middleware, docker, htmx, starlette]

# Dependency graph
requires:
  - phase: 04-docker
    provides: "Dockerfile, docker-compose.yml, entrypoint.sh, static file serving"
provides:
  - "OriginCheckMiddleware for CSRF defense on POST endpoints"
  - "Docker least-privilege defaults (cap_drop, no-new-privileges, localhost binding)"
  - "Vendored htmx 2.0.8 (no CDN dependency)"
affects: [05-security-hardening, 06-bug-fixes-and-resilience]

# Tech tracking
tech-stack:
  added: []
  patterns: [origin-referer-csrf-middleware, docker-cap-drop-cap-add, vendored-static-assets]

key-files:
  created:
    - fetcharr/web/middleware.py
    - fetcharr/static/js/htmx.min.js
    - tests/test_middleware.py
  modified:
    - fetcharr/__main__.py
    - docker-compose.yml
    - entrypoint.sh
    - fetcharr/templates/base.html

key-decisions:
  - "Origin/Referer header check over CSRF tokens -- no auth/sessions means no cookies to protect"
  - "cap_drop ALL + cap_add CHOWN/SETUID/SETGID to keep entrypoint working while minimizing capabilities"
  - "Vendored htmx.min.js committed to repo (not build-time download) for reproducible builds"

patterns-established:
  - "CSRF middleware: OriginCheckMiddleware on all POST endpoints via app.add_middleware"
  - "Docker hardening: cap_drop ALL + minimal cap_add + no-new-privileges in both compose and entrypoint"
  - "Static asset vendoring: download pinned JS into fetcharr/static/js/, reference via url_for"

requirements-completed: [SECR-02, SECR-05, SECR-07]

# Metrics
duration: 2min
completed: 2026-02-24
---

# Phase 5 Plan 1: Security Hardening - Infrastructure Summary

**Origin/Referer CSRF middleware on POST endpoints, Docker least-privilege (cap_drop ALL, localhost-only port, no-new-privileges), and vendored htmx 2.0.8 replacing CDN**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-24T13:44:23Z
- **Completed:** 2026-02-24T13:46:24Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- OriginCheckMiddleware rejects cross-origin POST requests with 403 while allowing same-origin and header-absent requests
- Docker container drops all Linux capabilities, re-adds only CHOWN/SETUID/SETGID for entrypoint, binds to 127.0.0.1 only, and sets no-new-privileges
- htmx 2.0.8 served from local static file -- zero external CDN dependency in templates
- Six tests cover all middleware validation paths (matching/mismatched Origin, matching/mismatched Referer, no headers, GET bypass)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Origin/Referer CSRF middleware and tests** - `28d29ac` (feat)
2. **Task 2: Docker hardening and htmx vendoring** - `30ce005` (feat)

## Files Created/Modified
- `fetcharr/web/middleware.py` - OriginCheckMiddleware class for CSRF defense
- `tests/test_middleware.py` - Six tests for middleware validation logic
- `fetcharr/__main__.py` - Register OriginCheckMiddleware before router
- `docker-compose.yml` - Localhost binding, cap_drop/cap_add, no-new-privileges
- `entrypoint.sh` - --no-new-privileges flag on setpriv exec
- `fetcharr/static/js/htmx.min.js` - Vendored htmx 2.0.8 (51KB)
- `fetcharr/templates/base.html` - Local static file reference replacing CDN script tag

## Decisions Made
- Origin/Referer header validation chosen over CSRF tokens because Fetcharr has no auth/sessions/cookies -- tokens would add complexity for zero benefit
- cap_drop ALL + cap_add CHOWN/SETUID/SETGID chosen because Docker applies cap_drop before the entrypoint runs; groupadd/useradd/chown need these capabilities
- htmx.min.js committed to repo rather than downloaded during Docker build for reproducible, network-independent builds

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- CSRF middleware active on all POST endpoints
- Docker hardened with least-privilege defaults
- Ready for Plan 2: URL validation, integer clamping, log level allowlist, config file permissions

---
*Phase: 05-security-hardening*
*Completed: 2026-02-24*
