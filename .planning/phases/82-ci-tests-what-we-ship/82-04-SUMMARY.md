---
phase: 82-ci-tests-what-we-ship
plan: "04"
subsystem: testing
tags: [ci, docker, subprocess, smoke-test, image-smoke, loguru]

# Dependency graph
requires:
  - phase: 82-ci-tests-what-we-ship (plan 02)
    provides: "tests/harness/checks.py reason-coded HTTP checks; tests/harness/arr_stub.py stub *arr service"
provides:
  - "tests/harness/stack.py: pure docker argv builders + HarnessSession lifecycle (session-labelled, exact-name teardown, Docker-assigned ports)"
  - "tests/harness/image_smoke.py: CLI smoke driver running every CISHIP-01 assertion plus the permanent missing-static-asset negative"
  - "tests/harness/fixtures/triggarr-ci.toml: isolated seeded config fixture (one enabled radarr instance pointed at the stub)"
affects: [82-07-ci-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single run_docker(args, check, timeout) subprocess.run(list, shell=False) wrapper -- every Docker-talking helper routes through it"
    - "HarnessSession: CSPRNG session id, name(role) naming, record-on-success, teardown removes only recorded exact names in reverse order (D-33 amendment B)"
    - "Case-insensitive HTTP header lookup helper for real ASGI servers that emit lowercase header names on the wire"

key-files:
  created:
    - tests/harness/stack.py
    - tests/harness/image_smoke.py
    - tests/harness/fixtures/triggarr-ci.toml
    - tests/test_ci_harness_stack.py
  modified:
    - tests/harness/checks.py
    - tests/test_ci_harness.py

key-decisions:
  - "Local Docker builds used a session-distinct tag (triggarr:ci-smoke-local-<shortsha>) instead of the plan's literal triggarr:local, per the orchestrator's parallel-worktree Docker isolation rule (another executor was running Plan 82-03 concurrently against the same local daemon)"
  - "wait_for_http_health now also retries on OSError (not just SmokeCheckError) since urllib.error.URLError/ConnectionResetError are legitimate transient conditions while the server is starting or mid-restart"
  - "checks.py header lookups (_cookie_value, check_setup_closed, check_protected_redirects_to_login) now use a case-insensitive _header() helper, because a real ASGI server emits lowercase set-cookie/location header names that a plain dict.get(\"Set-Cookie\") silently misses"

patterns-established:
  - "Docker port reassignment on restart: a container started with a dynamic (unspecified) host port gets a NEW ephemeral host port on every `docker start` after it has exited -- callers must re-query published_port() after a restart, never reuse the port captured at the initial `docker run -d`"

requirements-completed: [CISHIP-01]

# Metrics
duration: 17min
completed: 2026-10-21
---

# Phase 82 Plan 04: Shipped-Image Startup Smoke Driver Summary

**A CLI smoke driver (`python -m tests.harness.image_smoke run`) that starts the exact shipped image through its real ENTRYPOINT, proves health/setup/login/static-assets/writable-config/persistence-across-restart plus the permanent missing-static-asset negative, verified locally against a real build (SMOKE PASSED, ~12s) with two real bugs found and fixed in the shared harness library along the way**

## Performance

- **Duration:** ~17 min (commit span 17:32–17:49 local)
- **Started:** 2026-10-21T17:32:30-04:00
- **Completed:** 2026-10-21T17:48:51-04:00
- **Tasks:** 2 completed
- **Files modified:** 7 (5 created, 2 modified)

## Accomplishments
- `tests/harness/stack.py`: pure Docker argv builders (`triggarr_run_args`, `stub_run_args`) proving the real `ENTRYPOINT`, the README's cap-drop/cap-add set, and Docker-assigned loopback ports with zero fixed names anywhere in the module; `HarnessSession` records every resource on success and tears down only its own exact names, in reverse order
- `tests/harness/image_smoke.py`: the CLI driver running every CISHIP-01 assertion in sequence (image identity -> first-run default-config exit -> seeded setup/login/dashboard/config-ownership -> restart persistence -> missing-static-asset negative -> cross-container log hygiene), all output through loguru to stderr
- `tests/harness/fixtures/triggarr-ci.toml`: disposable, comment-headed CI fixture seeding one enabled `radarr.ci-stub` instance pointed at the stub, with no `[auth]` table so setup is still required
- Verified locally against a real build of this tree: positive run passes (`SMOKE PASSED`, ~12s wall-clock); a wrong `--expected-image-id-file` fails closed with `SMOKE FAILED [image-identity]`; a locally built broken-entrypoint variant (never pushed, not committed) fails with `SMOKE FAILED [first-run]`
- Found and fixed two real bugs in the shared harness library (`tests/harness/checks.py`, `tests/harness/stack.py`) while running the driver against the actual shipped server for the first time -- both documented below as deviations with regression tests

## Task Commits

Each task was committed atomically (TDD: test commit precedes the implementation commit for Task 1):

1. **Task 1 (RED): failing tests for stack.py argv builders and fixture** - `f5600f5` (test)
2. **Task 1 (GREEN): implement stack.py** - `f236993` (feat)
3. **Task 2: image_smoke.py driver + local proof, including the checks.py/stack.py bugfixes found while proving it** - `3488869` (feat)

**Plan metadata:** (this commit, pending)

## Files Created/Modified
- `tests/harness/stack.py` - `HarnessSession`, `new_session`, `triggarr_run_args`/`stub_run_args`, `create_network`/`create_volume`, `published_port`, `seed_volume`, `start_stub`/`start_triggarr`, `assert_image_identity`, `wait_for_http_health`/`wait_for_docker_health`/`wait_for_exit`, `exec_in`, `container_logs`, `stop_and_remove`, `run_docker`
- `tests/harness/image_smoke.py` - `main(argv) -> int`, the `run` subcommand, and the five lettered steps (A first-run, B seeded run, C restart, D missing-asset negative, E log hygiene)
- `tests/harness/fixtures/triggarr-ci.toml` - isolated seeded config fixture
- `tests/test_ci_harness_stack.py` - 38 unit tests for every `stack.py` behavior, all mocked (no real Docker daemon required in the default test run)
- `tests/harness/checks.py` - added a case-insensitive `_header()` lookup helper; `_cookie_value`, `check_setup_closed`, `check_protected_redirects_to_login` now use it
- `tests/test_ci_harness.py` - added 3 regression tests covering lowercase `set-cookie`/`location` response headers

## Decisions Made
- Used a session-distinct local Docker tag (`triggarr:ci-smoke-local-<shortsha>`) rather than the plan's literal `triggarr:local`, per the orchestrator's parallel-worktree Docker isolation rule (another executor was running Plan 82-03 concurrently against the same shared local Docker daemon). No plan file or product code references the literal tag name, so this has no effect on Plan 07's CI wiring, which will use the real `audited-image` artifact, not a local tag.
- `wait_for_http_health` retries on `OSError` in addition to `SmokeCheckError` (see Deviations below).
- `checks.py`'s header lookups are now case-insensitive (see Deviations below).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `wait_for_http_health` didn't retry a transient connection-refused/reset error**
- **Found during:** Task 2, first local run against the real built image (step A, after `docker start` on the restarted first-run container)
- **Issue:** `checks.check_health` can raise `urllib.error.URLError` (itself an `OSError` subclass) or `http.client.RemoteDisconnected` directly while the server is still starting up or mid-restart -- a legitimate transient condition during polling. `wait_for_http_health`'s retry loop only caught `SmokeCheckError`, so the real connection error propagated unhandled all the way to the driver's top-level exception handler, producing a spurious `SMOKE FAILED [unexpected-error] RemoteDisconnected` instead of continuing to poll.
- **Fix:** Catch `(SmokeCheckError, OSError)` in the polling loop.
- **Files modified:** `tests/harness/stack.py`
- **Verification:** Added `test_wait_for_http_health_retries_past_a_connection_reset` and `test_wait_for_http_health_times_out_on_repeated_connection_reset` to `tests/test_ci_harness_stack.py`; full local run subsequently passed through step A cleanly.
- **Committed in:** `3488869` (Task 2 commit)

**2. [Rule 1 - Bug] `checks.py` header lookups were case-sensitive against a real ASGI server**
- **Found during:** Task 2, first local run against the real built image (step B, `complete_setup` reported `cookie_issued=False` despite the server logging "Setup completed" and actually persisting the account)
- **Issue:** `_cookie_value`'s `headers.get("Set-Cookie")` and the `Location` lookups in `check_setup_closed`/`check_protected_redirects_to_login` did exact-case `dict.get(...)`. A real ASGI server (Starlette/Uvicorn, as used by the shipped image) emits response header names in **lowercase** over the wire (`set-cookie`, `location`), so every one of these lookups silently returned `None`/empty even when the header was genuinely present -- confirmed by inspecting the raw response with `curl -v` and a direct `urllib` request, and by `docker exec`-ing into the running container and finding the admin account `[auth]` section actually present in `/config/triggarr.toml`. Plan 02's own fake-server tests never caught this because the fake server always echoed back whatever exact-case header name the test itself supplied (e.g. `{"Set-Cookie": ...}`), never exercising the real lowercase-header path a genuine ASGI response sends. This blocked Task 2's own local-proof requirement end-to-end: every setup/login/redirect assertion in the driver depends on this parsing being correct.
- **Fix:** Added a case-insensitive `_header(headers, name)` lookup helper; `_cookie_value`, `check_setup_closed`, and `check_protected_redirects_to_login` now use it instead of a direct `dict.get(...)`.
- **Files modified:** `tests/harness/checks.py`
- **Verification:** Added three regression tests to `tests/test_ci_harness.py` (`test_complete_setup_returns_cookie_value_from_lowercase_header`, `test_check_setup_closed_passes_with_lowercase_location_header`, `test_check_protected_redirects_to_login_passes_with_lowercase_location_header`); full local run subsequently passed through steps B and C cleanly. Full suite (2107 tests) and ruff both green afterward.
- **Committed in:** `3488869` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug, both in the shared harness library this plan integrates with and exercises end-to-end for the first time, both directly blocking this task's own local-proof requirement).
**Impact on plan:** Both fixes were required for Task 2's own verification command to pass at all; neither touches product code (`triggarr/`) or changes any CISHIP-01 behavior -- only the test harness's correctness against a *real* server. No scope creep beyond what Task 2 could not complete without them. `checks.py` was not in this plan's `files_modified` list, but Plan 02's own SUMMARY explicitly hands it to this plan for reuse, and the bug is in exactly the integration surface this plan is the first to exercise against the real shipped image.

## Issues Encountered

**Docker port reassignment on restart (not a code bug, a Docker behavior; documented, not a deviation):** a container started with a dynamic host port (`-p 127.0.0.1::8484`, no fixed host port) gets a **new** ephemeral host port on every `docker start` after it has exited -- it is not fixed at container-creation time for this publish form. Step A's first-run container exits deliberately (exit 1, writing the default config), then is restarted via `docker start`; `_step_a_first_run` now re-queries `published_port()` after the restart instead of reusing the port captured at the initial `docker run -d`. Discovered via a manual debug repro (`curl` getting "Connection refused" against the stale port) before it ever reached a committed state.

## User Setup Required

None - no external service configuration required. Docker Desktop (local daemon) was used for verification per the session's local-only Docker rule; no NAS, no network-publishing action, no PR.

## Local Verification Evidence

All runs used the local Docker daemon only, with session-distinct tags (`triggarr:ci-smoke-local-f236993`, a throwaway `triggarr:ci-smoke-broken-entrypoint-f236993` built in the scratch directory). Both images and all debug containers/volumes/networks were removed after verification; a final sweep (`docker ps/volume/network ls --filter label=org.triggarr.ci.session`, and a filter on the `triggarr:ci-smoke*`/`triggarr:broken*` image references) confirmed nothing was left behind.

**Positive run** (`triggarr:ci-smoke-local-f236993`, built from this exact tree):
```
[smoke] session aaa75634ba82
[smoke] step 0: verify image identity
[smoke] step A: first-run default-config exit
[smoke] step B: seeded run against the stub
[smoke] step C: restart on the same volume
[smoke] step D: missing static asset negative
[smoke] negative static-asset-missing: rejected as expected
[smoke] step E: log hygiene across containers
SMOKE PASSED
```
Exit code 0. Wall-clock: ~12s (`0.56s user 0.41s system 7% cpu 12.046 total`). Post-run label-filtered `docker ps -a -q` / `docker volume ls -q` / `docker network ls -q` for session `aaa75634ba82` were all empty.

**Wrong image-ID negative** (same image, a file containing an all-zero fake sha256):
```
[smoke] session 9e72bf50e7a5
[smoke] step 0: verify image identity
SMOKE FAILED [image-identity] expected sha256:0000000000000000000000000000000000000000000000000000000000000000, got sha256:e5e8302f728bb64c85c5cd83b19de3d743912411ca49652fe4456a9bd1812562
```
Exit code 1.

**Broken-entrypoint negative (local evidence only; not gate evidence, D-07):** a throwaway image `FROM triggarr:ci-smoke-local-f236993` with `/entrypoint.sh`'s final line rewritten from `exec ... python -m triggarr` to `exec ... python -m triggarr_missing_module` via a scratch-directory Dockerfile (never committed to this repo, never pushed). Raw container boot log:
```
WARNING: setpriv --no-new-privileges not supported, skipping
/usr/local/bin/python: No module named triggarr_missing_module
```
Driver output:
```
[smoke] session 857f35fd20d4
[smoke] step 0: verify image identity
[smoke] step A: first-run default-config exit
SMOKE FAILED [first-run] expected exit 1 with a default-config log line, got exit=1
```
Exit code 1. This narrowly proves "this startup probe detects a broken entrypoint" (D-07) -- it does not, and is not claimed to, prove that any GitHub-enforced gate rejects this; that claim belongs to Plan 07's real CI run on an isolated branch/draft PR (D-07, D-09).

## Next Phase Readiness

`tests/harness/stack.py` and `tests/harness/image_smoke.py` are ready for Plan 07 to invoke the exact same `python -m tests.harness.image_smoke run --image ... --expected-image-id-file ...` CLI against the downloaded, identity-verified `audited-image` artifact inside the new `image-smoke` CI job. No blockers. One behavior worth carrying into Plan 07's job design: CI runners typically also use dynamic host ports for container-to-host access, so the restart-reassigns-the-port behavior documented above is a property of Docker itself, not of this local environment, and will reproduce identically in GitHub Actions.

---
*Phase: 82-ci-tests-what-we-ship*
*Completed: 2026-10-21*

## Self-Check: PASSED

- FOUND: tests/harness/stack.py
- FOUND: tests/harness/image_smoke.py
- FOUND: tests/harness/fixtures/triggarr-ci.toml
- FOUND: tests/test_ci_harness_stack.py
- FOUND: tests/harness/checks.py
- FOUND: tests/test_ci_harness.py
- FOUND: .planning/phases/82-ci-tests-what-we-ship/82-04-SUMMARY.md
- FOUND commit: f5600f5 (test(82-04): add failing tests for stack.py argv builders and fixture)
- FOUND commit: f236993 (feat(82-04): implement stack.py argv builders and lifecycle helpers)
- FOUND commit: 3488869 (feat(82-04): add image_smoke.py shipped-image startup smoke driver)
