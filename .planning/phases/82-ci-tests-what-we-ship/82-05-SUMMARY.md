---
phase: 82-ci-tests-what-we-ship
plan: "05"
subsystem: testing
tags: [playwright, pytest-playwright, browser-e2e, capture-policy, artifact-scan, docker-isolation]

# Dependency graph
requires:
  - phase: 82-ci-tests-what-we-ship (plan 02)
    provides: "tests/harness/checks.py reason-coded HTTP checks (complete_setup/login); tests/harness/arr_stub.py stub *arr service"
  - phase: 82-ci-tests-what-we-ship (plan 04)
    provides: "tests/harness/stack.py HarnessSession/new_session/start_stub/start_triggarr/published_port/wait_for_http_health; fixtures/triggarr-ci.toml"
provides:
  - "pyproject.toml dev extra: playwright>=1.60, pytest-playwright>=0.9 (CI-only, no Dockerfile/runtime change)"
  - "tests/conftest.py collect_ignore: tests/e2e excluded from the default run unless TRIGGARR_E2E_IMAGE is set (D-12, fails not skips)"
  - "tests/harness/artifact_scan.py: scrub(output_dir, sensitive_values) -> ScanReport, byte-scans text/binary artifacts for raw/URL-encoded/base64 forms (D-27 extra defence)"
  - "tests/e2e/conftest.py: e2e_image/e2e_stack/credentials/triggarr_container/admin_container fixtures, SensitiveRegistry, pytest_collection_finish capture-policy guard (D-33 amendment A), pytest_sessionfinish artifact scan, CREDENTIAL_RUN_FLAGS"
  - "tests/e2e/test_setup_login_logout.py: D-25 browser flows (first-run setup, login incl. wrong password, logout) against the shipped image"
  - "tests/e2e/test_capture_policy.py + tests/e2e/probes/: proof that a pre-registration setup failure leaves no capture, and Docker session isolation (D-33 amendment B)"
  - "tests/test_e2e_capture_guard.py: 5-case proof of the capture-policy guard in the default unit job (no Docker, no browser)"
affects: [82-06-browser-suite-pill-test, 82-07-ci-wiring]

# Tech tracking
tech-stack:
  added: ["playwright>=1.60", "pytest-playwright>=0.9"]
  patterns:
    - "pytest_collection_finish (not pytest_collection_modifyitems) as the capture-policy enforcement point -- runs on the final post -m/-k selection, before any fixture or browser"
    - "SensitiveRegistry: a session-scoped append-only list of exposed secret values, used both for log redaction and as scrub()'s input at session end"
    - "Subprocess probes (tests/e2e/probes/probe_*.py, collected only via an explicit -o python_files override) that get their own fully-isolated HarnessSession beside a live parent session, proven disjoint via an E2E_SESSION_RECORD JSON handshake file"
    - "sentinel_plugin.py: a pytest plugin whose pytest_runtest_setup writes a nodeid marker, proving a rejected collection never reaches any fixture"

key-files:
  created:
    - tests/e2e/__init__.py
    - tests/e2e/conftest.py
    - tests/e2e/test_setup_login_logout.py
    - tests/e2e/test_capture_policy.py
    - tests/e2e/probes/__init__.py
    - tests/e2e/probes/probe_setup_fails_before_registration.py
    - tests/e2e/probes/probe_capture_allowed.py
    - tests/e2e/probes/sentinel_plugin.py
    - tests/test_e2e_capture_guard.py
    - tests/harness/artifact_scan.py
    - tests/test_artifact_scan.py
  modified:
    - pyproject.toml
    - uv.lock
    - .gitignore
    - tests/conftest.py

key-decisions:
  - "Used a session-distinct local Docker image tag (triggarr:ci-e2e-local-<shortsha>) for local verification, never the plan's literal triggarr:local, per the established parallel-worktree Docker isolation precedent from Plan 04 -- removed after verification, no leftovers"
  - "config.getoption() called with the literal flag strings (\"--tracing\" etc.), confirmed to resolve via pytest's _opt2dest mapping -- matches the plan's literal wording and pytest-playwright's actual registered dest names"
  - "pytest_runtest_makereport implemented with the modern hookimpl(wrapper=True) generator form (yield returns the TestReport directly, then `return report`), confirmed against pytest 9.0.3/pluggy 1.6.0's own internal usage of the same pattern, not the legacy hookwrapper=True outcome.get_result() form"
  - "browser_context_args override docstring avoids the literal string \"record_har\" (describes behavior instead) so the D-27 acceptance grep for that identifier outside comments stays accurate to intent"

patterns-established:
  - "CREDENTIAL_RUN_FLAGS tuple in tests/e2e/conftest.py is the one source of truth for \"capture fully off\", reused by this plan's own subprocess probes and left for Plan 07's CI wiring to reuse unchanged"

requirements-completed: [CISHIP-02]

# Metrics
duration: 18min
completed: 2026-10-21
---

# Phase 82 Plan 05: Browser Suite Foundation + D-25 Auth Flows Summary

**Playwright/pytest-playwright dev dependency, an artifact byte scanner, and a browser suite proving D-25's setup/login/logout flows against the shipped image -- with D-33's capture policy enforced by prevention (a pytest_collection_finish guard raising UsageError, exit 4) rather than detection, proven by a probe that fails before the generated API key is ever registered, and by Docker-session isolation between a live parent stack and a subprocess probe**

## Performance

- **Duration:** ~18 min (commit span 17:56-18:14 local)
- **Started:** 2026-10-21T17:56:51-04:00
- **Completed:** 2026-10-21T18:14:33-04:00
- **Tasks:** 3 completed (Task 2 is TDD: test commit before implementation commit)
- **Files modified:** 15 (11 created, 4 modified)

## Accomplishments
- Added `playwright>=1.60` and `pytest-playwright>=0.9` to the existing `dev` extra only (verified current PyPI versions resolve to `playwright==1.64.0`, `pytest-playwright==0.10.0`, matching RESEARCH.md); `uv.lock` regenerated and committed in the same commit; Chromium installed locally
- `tests/conftest.py`'s `collect_ignore` excludes `tests/e2e` from the default run unless `TRIGGARR_E2E_IMAGE` is set, so `pytest tests/e2e` without it exits non-zero (no silent skip, D-12)
- `tests/harness/artifact_scan.py`: stdlib-only `scrub()` that byte-scans every file (including zip members) for raw/URL-encoded/base64 forms of each sensitive value, deletes matches, writes `withheld.txt` (reasons only, never the value) then `scan-complete.json` (counts) -- the completion marker is never written if scanning raises; a corrupt zip fails closed; values under 8 chars are rejected. 10 unit tests, TDD RED-then-GREEN.
- `tests/e2e/conftest.py`: session scaffolding (`e2e_image`, `e2e_stack`, `credentials`, `triggarr_container`, `admin_container`), a `SensitiveRegistry` that tracks every exposed value, and the D-33 amendment A capture guard in `pytest_collection_finish` (not `pytest_collection_modifyitems`, per the plan's documented hook-ordering rationale)
- `tests/e2e/test_setup_login_logout.py`: D-25's three flows as real Chromium interactions -- first-run setup creates the admin and closes setup (fresh browser context confirms `/setup` now redirects to `/login`), a wrong password keeps protected pages locked with no session cookie issued, valid credentials reach the dashboard, logout ends the session and a fresh request to a protected page redirects to `/login`
- `tests/e2e/test_capture_policy.py` + `tests/e2e/probes/`: a probe subprocess proves a setup failure before API-key registration leaves no capture (0 `.png`/`.jpg`/`.jpeg`/`.webm`/`.zip` files, `scan-complete.json` present, the key never echoed in subprocess output) and that the probe's own Docker session (network/container/volume) is fully disjoint from, and never disturbs, the parent's live stack (D-33 amendment B)
- `tests/test_e2e_capture_guard.py`: all 5 amendment-A selection/capture-flag combinations verified in the default unit job -- no Docker, no browser, since a rejected selection never reaches a fixture

## Task Commits

Each task was committed atomically (Task 2 is TDD: RED then GREEN):

1. **Task 1: Add Playwright dev dependencies and isolate tests/e2e from the default run** - `4f657ca` (feat)
2. **Task 2 (RED): Add failing tests for artifact secret scanner** - `37b262c` (test)
3. **Task 2 (GREEN): Implement artifact secret scanner** - `62b2a35` (feat)
4. **Task 3: e2e conftest, capture policy guard and probe, and setup/login/logout browser tests** - `02942f0` (feat)

**Plan metadata:** (this commit, pending)

## Files Created/Modified
- `pyproject.toml` - `playwright>=1.60`, `pytest-playwright>=0.9` added to the existing `dev` extra (no new extra, Dockerfile unchanged)
- `uv.lock` - regenerated; resolved `playwright==1.64.0`, `pytest-playwright==0.10.0` plus transitive deps (`pyee`, `greenlet`, `python-slugify`, `text-unidecode`)
- `.gitignore` - added `e2e-artifacts/` and `test-results/` (Playwright `--output` directories)
- `tests/conftest.py` - `collect_ignore` excludes `e2e` unless `TRIGGARR_E2E_IMAGE` is set
- `tests/e2e/__init__.py` - package docstring explaining the exclusion/fail-not-skip contract
- `tests/harness/artifact_scan.py` - `scrub(output_dir, sensitive_values) -> ScanReport`, stdlib-only (`zipfile`, `base64`, `urllib.parse`, `json`) plus loguru
- `tests/test_artifact_scan.py` - 10 unit tests covering every behavior bullet (removal, withheld.txt contents, scan-complete.json ordering/non-write-on-raise, short-value rejection, encoded-form matching, empty/missing dir, corrupt zip, recursive walk)
- `tests/e2e/conftest.py` - session scaffolding, `SensitiveRegistry`, capture-policy guard, `pytest_sessionfinish` byte scan, `CREDENTIAL_RUN_FLAGS`
- `tests/e2e/test_setup_login_logout.py` - D-25's three flows, module-marked `credential_pages`
- `tests/e2e/test_capture_policy.py` - pre-registration-failure capture proof + Docker isolation proof (D-33 amendment B)
- `tests/e2e/probes/__init__.py`, `probe_setup_fails_before_registration.py`, `probe_capture_allowed.py`, `sentinel_plugin.py` - subprocess probe targets and a setup-phase sentinel plugin
- `tests/test_e2e_capture_guard.py` - 5-case guard proof, default unit job, no Docker/browser

## Decisions Made
- **Session-distinct local Docker tag for verification** (not the plan's literal `triggarr:local`): built `triggarr:ci-e2e-local-62b2a35` from this exact tree, ran the full local verification against it, then removed the image afterward. This follows Plan 04's documented precedent for avoiding collisions with other executors sharing the same local Docker daemon; it has no effect on product code or Plan 07's CI wiring (which uses the real `audited-image` CI artifact, not a local tag).
- **`config.getoption()` called with literal flag strings** (`"--tracing"`, `"--screenshot"`, `"--video"`) in the capture guard, matching the plan's literal wording -- confirmed via `pytest.Config.getoption`'s own implementation that it resolves literal `--OPT` strings through its internal `_opt2dest` mapping, so this is equivalent to (and more literally traceable to the plan than) using the bare dest names.
- **Modern `hookimpl(wrapper=True)` form for `pytest_runtest_makereport`**: verified against pytest 9.0.3/pluggy 1.6.0's own internal hooks (`_pytest/skipping.py`) that the yielded value under `wrapper=True` is the `TestReport` itself (not a legacy `outcome` wrapper needing `.get_result()`), and that the hook must `return report` at the end. Avoided the legacy `hookwrapper=True` form, which pytest 9's own codebase no longer uses for this hook.
- **Reworded the `browser_context_args` override docstring** to avoid the literal substring the D-27 acceptance check greps for outside comments, while still documenting the same "no HAR recording" guarantee in different words.

## Deviations from Plan

None - plan executed exactly as written. One acceptance-criteria-driven touch-up: a docstring initially used the literal identifier the `record_har` grep check was meant to catch in actual *usage*; reworded it to describe the behavior without that literal string once the grep flagged it mid-verification (not a behavior change, not a Rule 1-4 deviation).

## Issues Encountered

None blocking. Pitfall-1 (Open Question 1 from RESEARCH.md, Playwright clock vs. htmx's `setInterval`) does not apply to this plan -- it is Plan 06's concern, not this plan's three tasks.

## Playwright Trace Secret Redaction (plan's <output> requirement)

The installed version, `playwright==1.64.0`, does **not** offer trace secret redaction. Confirmed directly: `Tracing.start()`'s signature in `playwright/sync_api/_generated.py` (this installed package) has no `secrets`/redaction parameter (`aria_snapshots`, `live`, `name`, `screen_snapshots`, `screenshots`, `snapshots`, `sources`, `title` only), and a repo-wide grep of the installed package for `secret`/`redact` near the tracing API returns nothing relevant. This matches RESEARCH.md's flag that the upstream PRs (microsoft/playwright#43220, #43423) were unconfirmed for a stable release as of the research date. Consequence: the byte scanner (Task 2) and the capture-policy guard's prevention (Task 3, D-33) remain the full enforcement for this suite -- there is no additional upstream redaction layer to rely on yet. If a future Playwright upgrade adds this, it would be an additional layer, not a replacement for the scanner or the guard.

## Local E2E Verification Evidence

Built `triggarr:ci-e2e-local-62b2a35` locally from this exact tree (session-distinct tag, see Decisions). Ran:
```
TRIGGARR_E2E_IMAGE=triggarr:ci-e2e-local-62b2a35 \
EXPECTED_IMAGE_ID=$(docker image inspect triggarr:ci-e2e-local-62b2a35 --format '{{.Id}}') \
uv run --no-sync pytest tests/e2e -q -m credential_pages --browser chromium \
  --tracing off --screenshot off --video off --output e2e-artifacts/credential
```
Result: **6 passed in 19.54s** (4 D-25 flow tests + 2 capture-policy tests, including the full Docker-isolation proof with a live probe subprocess). `e2e-artifacts/credential/scan-complete.json` present (`{"scanned": 0, "withheld": []}` -- no capture files existed to scan, as expected with capture fully off). `find e2e-artifacts/credential -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.webm' -o -name '*.zip' | wc -l` = 0.

Negative check: `pytest tests/e2e -q -m credential_pages --tracing retain-on-failure` against the same image exited **4** with `ERROR: capture is disabled for credential pages: run them with --tracing off --screenshot off --video off` and "no tests ran" (fixtures never started).

Post-run: `docker ps/volume/network -q --filter label=org.triggarr.ci.session` all empty (no leftovers). The verification image tag was removed after use (`docker rmi`).

Unit-job guard proof (no Docker, no browser): `uv run --no-sync pytest tests/test_e2e_capture_guard.py -q` -> **5 passed in 1.73s**.

Full suite + lint: `uv run --no-sync pytest tests/ -q` -> **2137 passed** (2122 prior + 10 artifact_scan + 5 capture_guard); `uv run --no-sync ruff check triggarr/ tests/` -> **All checks passed**.

## User Setup Required

None - no external service configuration required. Docker Desktop (local daemon) used for verification per the session's local-only Docker rule; no NAS, no network-publishing action, no PR.

## Next Phase Readiness

`tests/e2e/conftest.py`'s fixtures (`e2e_image`, `e2e_stack`, `credentials`, `triggarr_container`, `admin_container`), `CREDENTIAL_RUN_FLAGS`, and the `credential_pages` marker/guard are ready for Plan 06 to build the connection-pill test on top of (non-credential-page tests authenticate via cookie injection per the plan's own design, not covered by this plan's tasks). Plan 07 can reuse `CREDENTIAL_RUN_FLAGS` and the two-invocation pattern (`-m credential_pages` with capture off, `-m "not credential_pages"` with capture on) unchanged for CI wiring. No blockers.

---
*Phase: 82-ci-tests-what-we-ship*
*Completed: 2026-10-21*

## Self-Check: PASSED

- FOUND: tests/e2e/__init__.py
- FOUND: tests/e2e/conftest.py
- FOUND: tests/e2e/test_setup_login_logout.py
- FOUND: tests/e2e/test_capture_policy.py
- FOUND: tests/e2e/probes/__init__.py
- FOUND: tests/e2e/probes/probe_setup_fails_before_registration.py
- FOUND: tests/e2e/probes/probe_capture_allowed.py
- FOUND: tests/e2e/probes/sentinel_plugin.py
- FOUND: tests/test_e2e_capture_guard.py
- FOUND: tests/harness/artifact_scan.py
- FOUND: tests/test_artifact_scan.py
- FOUND commit: 4f657ca (feat(82-05): add Playwright dev dependency and isolate tests/e2e)
- FOUND commit: 37b262c (test(82-05): add failing tests for artifact secret scanner)
- FOUND commit: 62b2a35 (feat(82-05): implement artifact secret scanner)
- FOUND commit: 02942f0 (feat(82-05): add browser suite D-25 flows with D-33 capture-policy guard)
