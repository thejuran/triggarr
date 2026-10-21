---
phase: 82-ci-tests-what-we-ship
plan: "02"
subsystem: testing
tags: [ci, http.server, urllib, stub-service, smoke-test, playwright-prep]

# Dependency graph
requires: []
provides:
  - "tests/harness/arr_stub.py: stdlib-only stub *arr HTTP service with a runtime connected/disconnected toggle"
  - "tests/harness/checks.py: reason-coded HTTP smoke checks (health, static assets, setup/login/logout, dashboard) plus expect_failure for D-03 negative tests"
affects: [82-04-image-smoke, 82-05-browser-suite, 82-06-browser-suite]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Stdlib-only HTTP test doubles (http.server.ThreadingHTTPServer) so the stub can run inside the shipped image's Python with no extra packages"
    - "Reason-coded exceptions (SmokeCheckError.reason) with expect_failure() enforcing exact-reason negative-test matching (D-03)"

key-files:
  created:
    - tests/harness/__init__.py
    - tests/harness/arr_stub.py
    - tests/harness/checks.py
    - tests/test_ci_harness.py
  modified: []

key-decisions:
  - "Stub answers exactly the Radarr-cycle endpoint set confirmed in engine.py (system/status, wanted/missing, wanted/cutoff, movie, tag, history/movie, command) -- no Lidarr /api/v1/system/status path added, since neither the plan's interfaces block nor the Radarr cycle reference it"
  - "api_requests counter in /__control/state counts every /api/-prefixed request regardless of auth outcome or up/down state, giving Plan 04/05 a single source of truth for bounded request-count assertions"
  - "checks.py never mentions Origin/Referer in any form (code or docstring) since the real app's OriginCheckMiddleware allows header-less requests; the checks simply never send either header"

patterns-established:
  - "SmokeCheckError(reason, detail) subclasses AssertionError and is raised by every check on failure; expect_failure(reason, fn, *a, **kw) is the one assertion both the image-smoke driver and the browser suite reuse for every negative case"

requirements-completed: [CISHIP-01, CISHIP-02]

# Metrics
duration: 10min
completed: 2026-10-21
---

# Phase 82 Plan 02: CI Harness Stub and Reason-Coded Checks Summary

**Stdlib-only stub *arr HTTP service (http.server) with a /__control/state connected/disconnected toggle, plus a urllib-based reason-coded check library (SmokeCheckError + expect_failure) that Plan 04's image-smoke job and Plans 05/06's browser suite will both reuse**

## Performance

- **Duration:** ~10 min (commit span 17:09-17:19)
- **Started:** 2026-10-21T17:09:37-04:00
- **Completed:** 2026-10-21T17:19:03-04:00
- **Tasks:** 2 completed
- **Files modified:** 4 (all created)

## Accomplishments
- A minimal, stdlib-only stub *arr service (`tests/harness/arr_stub.py`) that answers every endpoint the Radarr search cycle and startup validation call, with X-Api-Key auth and a runtime reachability toggle for CISHIP-02's connection-pill test
- A reusable, reason-coded HTTP check library (`tests/harness/checks.py`) covering health, static assets, setup/login/logout and dashboard reachability, built on stdlib `urllib` so it has no new dependency
- `expect_failure()` enforces D-03: a negative test passes only when the check fails with the exact expected reason, never on any failure
- 43 unit tests (`tests/test_ci_harness.py`) exercising every behavior bullet in the plan, run inside the existing `test` CI job with no new tooling

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Write failing tests for the stub and the checks** - `c7d12cc` (test)
2. **Task 2 (GREEN/REFACTOR): Implement arr_stub.py and checks.py** - `aabf85e` (feat)

**Plan metadata:** (this commit, pending)

## Files Created/Modified
- `tests/harness/__init__.py` - Package docstring only; marks this as CI-only test infrastructure, excluded from the shipped image via `.dockerignore`'s `tests/` entry
- `tests/harness/arr_stub.py` - `build_server(host, port, api_key) -> ThreadingHTTPServer` plus a `main()` CLI entry point (`--host`/`--port`, API key from `STUB_API_KEY`) for Plan 04's stub container
- `tests/harness/checks.py` - `SmokeCheckError`, nine `check_*`/`complete_setup`/`login` functions, and `expect_failure`
- `tests/test_ci_harness.py` - 43 tests: 16 against a real `arr_stub` server on an ephemeral port, 27 against a tiny configurable fake "triggarr" server that each test wires per-path

## Stub Endpoint Set

Confirmed against `triggarr/clients/base.py`, `triggarr/clients/radarr.py`, and the Radarr search cycle in `triggarr/search/engine.py` (`run_radarr_cycle`, `refresh_radarr_counts`, and the grab-history poll in `triggarr/tracking.py`) -- no additional endpoint was found beyond what the plan's interfaces block already listed:

| Method | Path | Response |
|--------|------|----------|
| GET | `/api/v3/system/status` | 200 `{"version": "5.0.0.0", "appName": "TriggarrArrStub"}` |
| GET | `/api/v3/wanted/missing` | 200 empty `PaginatedResponse` envelope |
| GET | `/api/v3/wanted/cutoff` | 200 empty `PaginatedResponse` envelope |
| GET | `/api/v3/movie` | 200 empty `PaginatedResponse` envelope (used by `get_library_count`) |
| GET | `/api/v3/tag` | 200 `[]` |
| GET | `/api/v3/history/movie` | 200 `[]` |
| POST | `/api/v3/command` | 201 `{"id": 1}` |
| any `/api/*` | missing/wrong `X-Api-Key` | 401 |
| any `/api/*` | while `up=false` | 503 |
| GET | `/__control/state` | 200 `{"up": bool, "api_requests": int}` (no API key required) |
| POST | `/__control/state` | `{"up": bool}` -> 200 echo; non-boolean/invalid JSON -> 400, state unchanged |
| anything else | | 404 |

## Reason Codes (checks.py)

| Function | Reason on failure |
|----------|--------------------|
| `check_health` | `health` |
| `check_static_assets` | `static-asset-missing` (detail names the missing path) |
| `check_setup_available` | `setup-unavailable` |
| `complete_setup` | `setup-failed` |
| `check_setup_closed` | `setup-still-open` |
| `check_login_rejected` | `login-accepted-wrong-password` |
| `login` | `login-failed` |
| `check_dashboard` | `dashboard-unreachable` |
| `check_protected_redirects_to_login` | `protected-page-open` |
| `expect_failure` (wrong/no failure) | `negative-harness` |

## Decisions Made
- Scoped the stub's status-path support to exactly `/api/v3/system/status` (Radarr/Sonarr), not adding Lidarr's `/api/v1/system/status` -- the plan's interfaces block and Task 2's `read_first` instruction were both scoped to "the Radarr search cycle," and no other v2.13 plan in this phase currently exercises Lidarr. If Plan 04/05/06 need Lidarr coverage, that is additive and will be requested there.
- `api_requests` in `/__control/state` counts every `/api/`-prefixed request unconditionally (before the auth/up checks), giving the browser suite's bounded-request-count assertions (D-28) a single, unambiguous counter that reflects actual reachability-probing frequency regardless of outcome.
- Kept the words "Origin"/"Referer" out of `checks.py` entirely (not even in comments) since the checks simply never set those headers -- there was nothing to explain that the code itself doesn't already make obvious, and it keeps the module's behavior self-evidently CSRF-safe without needing to re-litigate `OriginCheckMiddleware`'s header-less exemption in every docstring.

## Deviations from Plan

None - plan executed exactly as written. No endpoint beyond the plan's listed interfaces was found while reading `engine.py`/`tracking.py`, so no additional stub route was added.

## Issues Encountered

The worktree's starting branch (`worktree-agent-a3d1c7787252d175e`) was based on an older commit (`81eb550`, predating the Phase 82 work) rather than the expected phase-start commit (`d915bc6`). Corrected per the `worktree_branch_check` step's sanctioned `git reset --hard d915bc64512e3f8c04320aada1d3c5db93dbb2c2` before any other work began.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`tests/harness/arr_stub.py` and `tests/harness/checks.py` are ready for Plan 04 (image-smoke CI job) to mount the stub into a disposable container via `python -m tests.harness.arr_stub` and for Plans 05/06 (browser suite) to reuse `checks.py`'s setup/login/logout helpers and the stub's reachability toggle for the connection-pill polling test. No blockers.

---
*Phase: 82-ci-tests-what-we-ship*
*Completed: 2026-10-21*

## Self-Check: PASSED

- FOUND: tests/harness/__init__.py
- FOUND: tests/harness/arr_stub.py
- FOUND: tests/harness/checks.py
- FOUND: tests/test_ci_harness.py
- FOUND: .planning/phases/82-ci-tests-what-we-ship/82-02-SUMMARY.md
- FOUND commit: c7d12cc (test(82-02): add failing tests for CI harness stub and checks)
- FOUND commit: aabf85e (feat(82-02): add CI harness stub service and reason-coded checks)
