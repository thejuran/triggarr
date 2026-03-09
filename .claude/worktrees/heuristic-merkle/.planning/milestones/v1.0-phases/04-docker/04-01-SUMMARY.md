---
phase: 04-docker
plan: 01
subsystem: infra
tags: [docker, dockerfile, compose, puid-pgid, tailwindcss, healthcheck]

# Dependency graph
requires:
  - phase: 03-web-ui
    provides: Web UI with Tailwind CSS and static assets for containerization
provides:
  - Multi-stage Dockerfile with pytailwindcss builder and python:3.13-slim production
  - entrypoint.sh with PUID/PGID privilege dropping via setpriv
  - docker-compose.yml with named volume, port mapping, restart policy
  - .dockerignore for build context exclusion
  - Localhost URL detection in startup for Docker networking mistakes
affects: []

# Tech tracking
tech-stack:
  added: [pytailwindcss (build-stage only), setpriv]
  patterns: [multi-stage Docker build, LinuxServer.io PUID/PGID convention, named Docker volume at /config]

key-files:
  created: [Dockerfile, entrypoint.sh, .dockerignore, docker-compose.yml, tests/test_startup.py]
  modified: [fetcharr/startup.py]

key-decisions:
  - "pytailwindcss in builder stage only -- not installed in production image"
  - "HEALTHCHECK uses python3 urllib.request instead of curl (no extra binary in slim image)"
  - "entrypoint.sh uses exec setpriv so python becomes PID 1 and receives SIGTERM directly"
  - "docker-compose.yml references ghcr.io image with comment about local build alternative"

patterns-established:
  - "Docker PUID/PGID: numeric validation with fallback to 1000"
  - "Localhost detection: urlparse hostname check against known loopback patterns"
  - "Named volume at /config: all persistent state in one mount point"

requirements-completed: [DEPL-01]

# Metrics
duration: 2min
completed: 2026-02-24
---

# Phase 4 Plan 1: Docker Packaging Summary

**Multi-stage Dockerfile with pytailwindcss builder, PUID/PGID entrypoint via setpriv, docker-compose with named /config volume, and localhost URL detection at startup**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-24T12:54:37Z
- **Completed:** 2026-02-24T12:56:49Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Multi-stage Dockerfile: builder compiles Tailwind CSS, production runs python:3.13-slim with HEALTHCHECK
- entrypoint.sh validates and creates PUID/PGID user, drops privileges via setpriv, exec replaces shell
- docker-compose.yml with named volume (fetcharr_config:/config), port 8080, unless-stopped restart
- Localhost URL detection warns before connection validation with actionable Docker networking advice
- 5 new tests covering localhost, 127.0.0.1, IPv6 loopback, non-localhost, and disabled app scenarios

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Docker artifacts** - `d99f76e` (feat)
2. **Task 2: Add localhost URL detection** - `b31d280` (feat)

**Plan metadata:** `112f727` (docs: complete plan)

## Files Created/Modified
- `Dockerfile` - Two-stage build: pytailwindcss builder + python:3.13-slim production with HEALTHCHECK
- `entrypoint.sh` - PUID/PGID user creation, numeric validation, setpriv privilege dropping
- `.dockerignore` - Build context exclusions for .venv, .git, tests, .planning, __pycache__
- `docker-compose.yml` - Service definition with named volume, port 8080, PUID/PGID env
- `fetcharr/startup.py` - Added check_localhost_urls function and LOCALHOST_PATTERNS constant
- `tests/test_startup.py` - 5 tests for localhost URL detection (all patterns + edge cases)

## Decisions Made
- pytailwindcss installed only in builder stage -- keeps production image slim
- HEALTHCHECK uses python3 urllib.request (no curl needed in slim image)
- exec setpriv replaces shell process so Python becomes PID 1 for clean SIGTERM handling
- docker-compose.yml references ghcr.io/thejuran/fetcharr:latest with comment about build: . alternative
- Localhost detection uses urlparse hostname against set of known loopback patterns (localhost, 127.0.0.1, ::1)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Docker packaging complete and ready for image builds
- All 57 tests passing (52 existing + 5 new)
- No blockers or concerns

## Self-Check: PASSED

All files verified present. All commit hashes verified in git log.

---
*Phase: 04-docker*
*Completed: 2026-02-24*
