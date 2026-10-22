---
phase: 82-ci-tests-what-we-ship
plan: "06"
subsystem: testing
tags: [playwright, pytest-playwright, browser-e2e, clock-api, htmx, connection-pill, sensitivity-check]

# Dependency graph
requires:
  - phase: 82-ci-tests-what-we-ship (plan 05)
    provides: "tests/e2e/conftest.py scaffolding (e2e_image, e2e_stack, credentials, triggarr_container, admin_container), SensitiveRegistry, CREDENTIAL_RUN_FLAGS, capture-policy guard"
provides:
  - "tests/e2e/conftest.py: StubControl dataclass + stub_control fixture exposing set_up(bool)/state() against the stub *arr service's Docker-assigned host port"
  - "tests/e2e/test_pill_polling.py: behavioral connection-pill regression test (D-02, D-28, D-29) -- bounded requests, continued scheduled polling, and a real backend state change reflected in the pill, driven by Playwright's browser clock"
  - "Resolution of RESEARCH.md Open Question 1: page.clock.fast_forward() reliably fires exactly one htmx 'every 30s' tick per 31s-equivalent advance; no run_for() fallback needed for the interval ticks themselves"
  - "Local sensitivity evidence (D-07 narrow claim, D-32i): the test fails with the two specific pinned messages against scratch variants reintroducing the original bug and disabling polling"
affects: [82-07-ci-wiring, 82-09-recorded-demonstrations]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Loop guard needs an explicit small clock advance (well under the interval being tested) before the real-time wait, not just a bare time.sleep() -- a paused virtualized clock can defer swap-triggered re-processing until the next explicit advance, so a pure real-time wait can silently miss a one-shot duplicate-request regression that would be caught immediately without clock virtualization"
    - "Distinguish 'a request was sent' (request event listener, confirms a tick fired) from 'the response landed in the DOM' (polling locator text) -- fast_forward()/run_for() never wait for the real network round-trip a fired timer triggers"

key-files:
  created:
    - tests/e2e/test_pill_polling.py
  modified:
    - tests/e2e/conftest.py

key-decisions:
  - "Image substitution per orchestrator decision: used triggarr:ci-pill-<shortsha> instead of the plan's literal triggarr:local for all real-image runs, and triggarr:pill-loop-<shortsha>/triggarr:pill-disabled-<shortsha> (built FROM the session tag) for the two scratch sensitivity variants; all three images removed after verification, no leftovers"
  - "Clock spike resolved fast_forward over run_for for the two 'every 30s' interval ticks (Task 1's required spike) -- both were tried against the loop variant during sensitivity testing with identical results, and fast_forward matches the plan/RESEARCH's starting-point code example, so no reason to prefer run_for for that part"
  - "Loop guard tightened with an extra page.clock.fast_forward(3000) (well under the 30s interval) immediately before the loop guard's real-time wait, discovered necessary during Task 2's local sensitivity check (see Deviations)"
  - "Separate wait helpers for 'a request was sent' (_wait_for_request_count, listener-based) vs. 'the response rendered' (_wait_for_pill_text, DOM-polling) -- using only the former for the first scheduled tick's content assertion read stale DOM text and produced a false failure against the correct image"

patterns-established:
  - "Authenticate browser e2e tests that visit no credential page via checks.login (plain HTTP) + context.add_cookies, never a rendered login form -- keeps the test outside the credential_pages marker entirely"

requirements-completed: [CISHIP-02]

# Metrics
duration: ~35min
completed: 2026-10-21
---

# Phase 82 Plan 06: Connection-Pill Behavioral Regression Test Summary

**Playwright-clock-driven connection-pill test proving bounded requests, continued scheduled polling, and a real backend state change, with local evidence that it detects both the original PR #27 request-loop bug and disabled polling -- the latter only after tightening the loop guard to flush clock-paused swap processing**

## Performance

- **Duration:** ~35 min (first file read to final verification)
- **Completed:** 2026-10-21
- **Tasks:** 2 completed
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- `tests/e2e/conftest.py` gained a `StubControl` dataclass + `stub_control` fixture (`set_up(bool)`, `state()`) against the stub *arr service's Docker-assigned host port (`E2EStack.stub_port`), resetting to `up=True` at teardown -- no fixed port anywhere (D-33 amendment B)
- `tests/e2e/test_pill_polling.py::test_connection_pill_polls_on_schedule_without_loop_and_shows_new_state` authenticates via `checks.login` (plain HTTP) + `context.add_cookies` -- no credential page rendered, no `credential_pages` marker -- then:
  1. Waits (bounded 45s real time) for the startup search cycle to reach the stub
  2. Installs the browser clock, loads `/`, confirms exactly 1 initial request and "Connection Stable"
  3. Loop guard: a small clock advance (3s, well under the 30s interval) plus a 3s real-time wait, asserting the count stays in `[1, 2]`
  4. Flips the stub down and POSTs `/api/refresh-counts/radarr/ci-stub` (reusing the existing, already-tested code path -- Pitfall 2/A1), confirming 200
  5. Two `page.clock.fast_forward("00:31")` calls, each followed by a bounded (10s) wait for a new request and (for the first) the pill text changing to "Connection Issue"
  6. Asserts the final bounded total is in `[3, 5]` (D-28: tolerance, never an exact count at a fragile deadline)
- **Clock spike (RESEARCH Open Question 1, resolved):** `page.clock.fast_forward("00:31")` reliably fires exactly one htmx `every 30s` tick per call against the real image -- confirmed by three full passing runs. `run_for()` was not needed for the interval ticks themselves. No runtime interval setting was added.
- **Local sensitivity evidence** (Task 2, D-07 narrow claim, D-32i) -- see dedicated section below.

## Task Commits

Each task was committed atomically:

1. **Task 1: Spike clock-vs-htmx timing, then write the pill test and stub-control fixture** - `bb13c18` (feat)
2. **Task 2: Local sensitivity check (loop guard tightening)** - `6fb6e8c` (fix)

**Plan metadata:** (this commit, pending)

## Files Created/Modified
- `tests/e2e/conftest.py` - added `StubControl` dataclass + `stub_control` fixture
- `tests/e2e/test_pill_polling.py` - the behavioral connection-pill test, including the two wait helpers (`_wait_for_request_count`, `_wait_for_pill_text`) and the startup-wait helper (`_wait_for_startup_connected`)

## Decisions Made

- **Image substitution** (orchestrator decision, not a plan deviation): every place the plan says `triggarr:local`, this execution built and used `triggarr:ci-pill-<shortsha>` from this worktree's exact tree instead, verified via `docker image inspect --format '{{.Id}}'` before each run. The two sensitivity variants (`triggarr:pill-loop-<shortsha>`, `triggarr:pill-disabled-<shortsha>`) were built `FROM` that session tag, in a scratch directory outside the repo, never committed or pushed. All three image tags were removed after verification (`docker rmi`); `triggarr:local` and other sessions' tags were never touched.
- **Clock API choice**: `fast_forward()` over `run_for()` for the two interval ticks -- both were tried against the loop variant during debugging with identical results for that part of the test, and `fast_forward()` matches RESEARCH.md's starting-point code example, so no reason to switch.
- **Two distinct wait helpers**: `_wait_for_request_count` (listener-based, proves a request was *sent*) and `_wait_for_pill_text` (DOM-polling, proves the response *rendered*). An earlier version read the DOM text immediately after confirming the request count, which raced the real network round-trip and produced a false failure against the known-good image (see Deviations).
- **Authentication without a rendered page**: `checks.login` (plain HTTP, already used by the image-smoke harness) + `context.add_cookies`, matching the plan's D-33 design -- the test file carries no `credential_pages` marker and visits only `/` plus the pill partial.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Initial tick-content check raced the real network round-trip**
- **Found during:** Task 1's own verification run (against the real image, before any sensitivity testing)
- **Issue:** After `page.clock.fast_forward("00:31")`, the test read `page.locator("#connection-pill").inner_text()` immediately once the "request sent" listener count incremented. A `page.on("request")` event fires when the browser *sends* a request, not once the response has been processed into the DOM -- the real HTTP round trip (unaffected by clock virtualization, which only overrides JS timers) still takes real wall-clock time. The test failed against the correct, unmodified image with "expected pill text to contain 'Connection Issue', saw 'Connection Stable'".
- **Fix:** Replaced the immediate `inner_text()` read with `_wait_for_pill_text`, a bounded (10s) real-time polling helper that waits for the DOM text to actually change before asserting.
- **Files modified:** `tests/e2e/test_pill_polling.py`
- **Verification:** Re-ran against the real image -- 1 passed in 9.44s. Committed as part of Task 1 (`bb13c18`), before Task 2's sensitivity testing began.

**2. [Rule 1 - Bug] Loop guard was not sensitive to the actual request-loop regression**
- **Found during:** Task 2's local sensitivity check, first run against the `pill-loop` variant
- **Issue:** The loop-guard assertion (`time.sleep(3)` then check count is `1 <= n <= 2`) passed even against the bugged image -- the regression's duplicate request only appeared several steps later, surfacing as a *different*, unintended failure ("expected 3-5 total pill requests after two scheduled ticks, saw 227" or similar, depending on how far execution got before the final bounded-count assertion caught it). Root cause, isolated via a throwaway debug copy of the test (never committed): with the browser clock installed and paused, htmx's swap-triggered re-processing of the newly inserted (bugged) partial does not proceed until an explicit clock advance occurs -- a bare real-time `time.sleep()` leaves it frozen indefinitely. A second debug run with no clock virtualization at all confirmed the regression in this htmx version (2.0.8) produces exactly one duplicate request, not a true unbounded storm, and that duplicate is masked entirely while the clock stays paused with no advance.
- **Fix:** Added `page.clock.fast_forward(3000)` (3 virtual seconds, well under the 30s interval) immediately before the loop guard's `time.sleep(3)`, flushing any pending swap-triggered re-processing without crossing the interval boundary. Re-verified: the loop variant now fails inside the loop guard itself with the required message ("connection pill request loop: 3 requests without any scheduled tick"); the real image and the disabled-polling variant were unaffected by this change.
- **Files modified:** `tests/e2e/test_pill_polling.py`
- **Verification:** Three full re-runs (real image, loop variant, disabled variant) all produced the correct pass/fail outcome with the correct message after the fix; full `tests/` suite still green (2137 passed); `ruff check` clean.
- **Committed in:** `6fb6e8c` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 -- bugs in the test's own timing assumptions, found and fixed before the test was ever considered final). No deviation touched `triggarr/` or any template; `git diff --name-only -- triggarr/` stayed empty throughout.
**Impact on plan:** Both fixes were necessary for the test to actually mean what it claims (D-28's "no request loop" and "real state change" assertions). No scope creep -- no new app behavior, no runtime config knob added.

## Local sensitivity evidence (narrow claim: the test detects these regressions locally; not gate evidence, D-07)

Built from this exact worktree tree (`e892928`): `triggarr:ci-pill-e892928` (image ID `sha256:4227816e...`).

Confirmed the template path inside the image first (inspection only):
```
docker run --rm --entrypoint ls triggarr:ci-pill-e892928 /app/triggarr/templates/partials
```

Two scratch Dockerfiles (never committed, never pushed, outside the repo), both `FROM triggarr:ci-pill-e892928`:

- **`pill-loop`** (reintroduces PR #27's exact bug): `sed` changes the partial's `hx-trigger="every 30s"` to `hx-trigger="load, every 30s"`.
  Built as `triggarr:pill-loop-e892928` (image ID `sha256:895bd0ba...`). Verified via `grep` inside the image that only the partial changed.
  **Run:**
  ```
  TRIGGARR_E2E_IMAGE=triggarr:pill-loop-e892928 EXPECTED_IMAGE_ID=sha256:895bd0ba... \
  uv run --no-sync pytest tests/e2e/test_pill_polling.py -q --browser chromium \
    --tracing retain-on-failure --screenshot only-on-failure --output e2e-artifacts/pages
  ```
  **Result: FAILED.** Exact failure line:
  ```
  AssertionError: connection pill request loop: 3 requests without any scheduled tick
  ```

- **`pill-disabled`** (polling removed): `sed` changes the partial's `hx-trigger="every 30s"` to `hx-trigger=""`, and the base.html placeholder's `hx-trigger="load, every 30s"` to `hx-trigger="load"`.
  Built as `triggarr:pill-disabled-e892928` (image ID `sha256:6fe8b042...`). Verified via `grep` inside the image that both files changed as intended.
  **Run:** same command shape, swapping image/ID.
  **Result: FAILED.** Exact failure line:
  ```
  Failed: connection pill did not refresh after a scheduled interval: expected at least 2 requests, saw 1
  ```

**Capture-safety check on both failing runs** (D-27 extra defence, T-82-26): `e2e-artifacts/<run>/scan-complete.json` present in both (`{"scanned": 3, "withheld": [".../trace.zip"]}`), `withheld.txt` confirms the trace was withheld for containing the registered session cookie; `grep -rl "ci-stub-key-not-a-secret" e2e-artifacts/` returned no match in either run. Only a failure screenshot and container logs remained after withholding -- no trace, no API key anywhere in either artifact tree.

**Real image re-confirmed passing** after the loop-guard fix (same command against `triggarr:ci-pill-e892928`): `1 passed in 9.23s`. Also re-ran the plan's two-invocation verify command (`-m credential_pages` with capture off, `-m "not credential_pages"` with capture on): 6 passed / 1 deselected, and 1 passed / 6 deselected, 0 skipped in both -- matching Task 1's acceptance criteria.

All three image tags (`triggarr:ci-pill-e892928`, `triggarr:pill-loop-e892928`, `triggarr:pill-disabled-e892928`) were removed (`docker rmi`) after verification. No Docker container, volume or network carrying the `org.triggarr.ci.session` label was left behind at any point (checked via label-filtered listing before and after). No Dockerfile variant was committed; `git status --porcelain` stayed clean apart from the two intended test-file commits throughout.

**CI-level demonstration** (the real audited image, on an isolated draft PR, with the owner's go-ahead per D-10) is Plan 09's responsibility, not this plan's.

## Issues Encountered

None blocking beyond the two auto-fixed timing bugs documented above (both resolved before Task 2's acceptance criteria were checked).

## User Setup Required

None -- no external service configuration required. Local Docker daemon only, per session rules; no NAS, no network-publishing action, no PR.

## Next Phase Readiness

`tests/e2e/test_pill_polling.py` and the `stub_control` fixture are ready for Plan 09's CI-level demonstration (the recorded broken-entrypoint/pill-bug-reintroduction evidence against the real audited image on an isolated draft PR, D-32ii). Plan 07's CI wiring can run this test unchanged as part of the `browser-e2e` job's `-m "not credential_pages"` invocation. No blockers.

---
*Phase: 82-ci-tests-what-we-ship*
*Completed: 2026-10-21*

## Self-Check: PASSED

- FOUND: tests/e2e/test_pill_polling.py
- FOUND: tests/e2e/conftest.py
- FOUND: .planning/phases/82-ci-tests-what-we-ship/82-06-SUMMARY.md
- FOUND commit: bb13c18 (feat(82-06): add connection-pill regression test with clock control)
- FOUND commit: 6fb6e8c (fix(82-06): tighten pill loop guard to reveal the request-loop regression)
