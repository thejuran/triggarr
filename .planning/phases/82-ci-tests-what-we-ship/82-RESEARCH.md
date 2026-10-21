# Phase 82: CI Tests What We Ship - Research

**Researched:** 2026-10-21
**Domain:** GitHub Actions CI/CD, Docker container smoke testing, browser regression testing (Playwright), release-artifact identity verification
**Confidence:** HIGH (architecture/wiring — verified directly against this repo's live workflows, scripts, and GitHub rulesets) / MEDIUM (exact Playwright timing-control mechanics, which are a Claude's-Discretion design choice this research recommends but cannot verify against an existing implementation)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Broken-case proof (evidence standard)**
- D-01: Hybrid evidence. Cheap negative tests (version/tag mismatch, malformed tags, missing static asset, related wiring) are permanent and run in the CI job they apply to. The expensive negative (deliberately broken-entrypoint image) is demonstrated and recorded once, not rebuilt every run.
- D-02: The connection-pill browser test continuously asserts correct behavior every run. Reintroducing the polling bug is a recorded sensitivity check, not a second browser run on every CI run.
- D-03: A negative-test harness passes only when it observes the expected, specific rejection, never on any failure. Each negative case asserts the failure reason.
- D-04: Permanent negative tests feed deliberately invalid input into the same script/function CI actually invokes (the `.github/scripts/*.test.cjs` pattern) and assert the specific rejection. Must not duplicate validation logic. Test inputs/expected outcomes stay independent of the implementation.
- D-05: CI wiring is verified separately from function behavior — testing a function does not prove the workflow invokes it or that failure reaches `CI ready`. Extend the existing job-consistency/workflow tests to cover the wiring.
- D-06: Every recorded demonstration (broken entrypoint, pill-bug reintroduction, any other one-time negative) captures: exact broken commit + minimal mutation; command run + expected failure; actual failure + CI run/job with logs showing it failed for the intended reason; confirmation `CI ready` also rejects it and publication cannot proceed; the restored final commit and its successful checks.
- D-07: Claims that GitHub's gate enforces a check require a real GitHub CI run on an isolated test branch or draft PR with publication prevented, never a production tag. Local evidence only proves narrowly-stated local claims, never gate enforcement.
- D-08: Reproduction recipes live in the repo. Durable evidence goes in phase verification records, not only in expiring Actions logs/artifacts.
- D-09: Repeat the broken-entrypoint demonstration whenever the Dockerfile, entrypoint, startup probe, or related CI wiring changes.
- D-10: This evidence standard does not authorize pushing deliberate breakage. Each push of a deliberately broken commit/branch needs the owner's separate, explicit go-ahead at execution time.

**CI time budget and run policy**
- D-11: Both the startup smoke test and the browser suite are required — they feed `CI ready` and block merge, for code, runtime, dependency, and relevant CI/control PRs.
- D-12: A docs-only exemption path is NOT built in this phase (Phase 85/ACCEPT-03). Until implemented, every new job runs on every PR; an unexplained skipped job must never count as success.
- D-13: On push to main and release, both checks run against the exact publish-candidate image before publication. PR results alone don't establish readiness. Depends on CI's existing main-push run and release policy's `REQUIRED_JOBS`.
- D-14: Budget target ~5 minutes added PR wall-clock time (not a proven estimate). Measure added critical-path time vs. current baseline (including image download/load and browser setup); parallelize where practical. If exceeded, investigate and report tradeoff to owner before expanding budget. Never remove required assertions or weaken failure handling to hit the target.
- D-15: Browser tests get no automatic retries that turn failure into pass. Keep logs/screenshots/traces from the first failure. A diagnostic rerun may help investigation but doesn't resolve a failure.
- D-16: Fix flaky tests or the app; never remove required coverage to get CI green. Temporary quarantine needs explicit owner approval, a tracked issue, and equivalent coverage or a recorded acceptance gap.

**Release tag rules**
- D-17: Before publication, the tag (without leading `v`), `pyproject.toml` version, and the exact audited image's `org.opencontainers.image.version` label must all agree. Missing/malformed value fails closed.
- D-18: `__version__` and the root package version in `uv.lock` are covered by the existing `tests/test_version.py`, running in the `test` job. `release-policy.cjs`'s `REQUIRED_JOBS` already requires that job on the exact release commit. Confirmed during discussion; planner re-confirms and keeps it mandatory.
- D-19: Keep the existing image revision and digest/ID identity checks. A matching version label alone doesn't prove artifact identity.
- D-20: CHANGELOG completeness stays a release-review item, not part of this identity gate.
- D-21: Only stable `vX.Y.Z` tags publish. Full string match, nonnegative integers, no leading zeros except `0` itself. Reject malformed tags, pre-release suffixes, build metadata before any publication. Tag format alone doesn't protect `:latest` — existing commit eligibility, version agreement, exact-artifact checks must still pass.
- D-22: On mismatch, fail loudly and publish nothing. Leave the git tag untouched — deletion is an explicit owner action; CI gets no tag-write permission.
- D-23: Rejection message reports the reason and the tag/package/image versions available at that point. If validation stops before the image is inspected, report "not inspected" rather than inventing a value.
- D-24: Verify rejection happens before registry login, image push, GitHub Release creation, or release-asset upload. Keep the failed run and its diagnostic evidence.

**Browser suite scope**
- D-25: Three flows — First-run setup (fresh isolated config → setup → create admin → dashboard; setup unavailable afterward); Login (wrong password blocks protected pages; valid credentials reach dashboard); Logout (ends session; fresh request to protected page redirects to login).
- D-26: Password-reset browser flow is deferred; keeps existing unit/integration coverage.
- D-27: Disposable test credentials only. Passwords, cookies, session values, tokens must not appear in captured artifacts (screenshots, traces, logs, HAR files).
- D-28: The connection-pill test watches initial load and at least two scheduled refreshes, asserting: requests stay bounded (no request loop); polling continues on schedule; the refreshed response actually updates the pill (test services must be able to change reported state between polls). Use a bounded range with timing tolerance, never an exact count at a fragile deadline.
- D-29: If the 30s interval is shortened for the test, change only the timing, never the htmx `hx-trigger`/`hx-swap` behavior under test. Demonstrate both the original request-loop bug (`load, every 30s` re-triggering on the outerHTML swap) and disabled polling make the test fail.
- D-30: The browser suite runs against the shipped image — the exact saved CI artifact intended for publication, verified by image identity against `image-id.txt` and the sha256. Fresh container, isolated writable config, test services, normal entrypoint, packaged assets, no source mounts, no rebuild. May use a separate container from the smoke test for isolation, but both must use the same image artifact.

### Claude's Discretion
- Browser tool choice. Playwright is expected, added as a dev/CI dependency without changing the runtime image.
- How timing is shortened for the pill test. Prefer browser-side clock control (e.g. Playwright's clock API) over adding a new runtime config knob to the app. A new runtime setting would be a product change needing owner approval.
- Design of the fake *arr test services: a minimal stub HTTP service answering the endpoints startup/health need, with switchable connected/disconnected state.
- Job layout: separate jobs vs. steps, how the saved `audited-image` artifact is shared between the smoke and browser jobs, and restart/persistence mechanics.
- Where the tag/version check lives inside the release preflight path, and how it reads the audited image label before any login or push.
- How the missing-static-asset negative is constructed as a cheap permanent test without a second full image build.

### Deferred Ideas (OUT OF SCOPE)
- Pre-release tag support (`vX.Y.Z-rcN`) that publishes without moving `:latest`: a future milestone.
- A password-reset flow in the browser suite: keep existing unit/integration coverage for now.
- CHANGELOG-entry enforcement at release: stays a release-review item, not an identity gate.
- The docs/planning-only CI exemption path: Phase 85 (ACCEPT-03), after Phase 83 defines the classification policy.
- Lockfile-matched Docker dependencies, the OS-image audit, actionlint, coverage artifacts, publish-permission narrowing: Phase 85 (CIMAINT-01..07).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CISHIP-01 | CI starts the exact publish-candidate image through its normal entrypoint with isolated test config and mocked/test services; verifies health, setup/login, static assets, writable config, persistence across restart; a broken entrypoint and a missing static asset each fail the check | See "Standard Stack", "Architecture Patterns" (new `image-smoke` job), "Don't Hand-Roll" (stub *arr service), "Code Examples" (container lifecycle, missing-asset negative via writable-layer mutation), "Validation Architecture" |
| CISHIP-02 | A small browser regression suite asserts connection-pill request-loop behavior and critical setup/login behavior as observable behavior (not screenshots); reintroducing the polling bug fails the suite; failure logs/screenshots upload as artifacts with no secrets present | See "Standard Stack" (Playwright/pytest-playwright), "Architecture Patterns" (new `browser-e2e` job), "Code Examples" (clock-driven pill test, setup/login/logout flows), "Common Pitfalls" (secrets-in-traces, htmx trigger mechanics, `search_interval` granularity) |
| CISHIP-03 | Before any version-tag publication, CI rejects a tag that disagrees with package metadata or image version, and accepts one that matches — both proven without publishing a production tag; exact-commit CI and artifact-identity checks preserved | See "Architecture Patterns" (release-job placement, sparse-checkout constraint), "Code Examples" (tag format + label-comparison functions), "Don't Hand-Roll" (reuse `test_version.py` + existing label-writing step instead of re-deriving `pyproject.toml` version in the release workflow) |
| CISHIP-04 | The CISHIP jobs join the existing required aggregate gate and consistency checks together; a missing/skipped mandatory job cannot let the gate pass; the published image is never rebuilt | See "Architecture Patterns" ("Single Point of Truth" insight: `REQUIRED_JOBS` cascades into `ci-ready`, `ci-job-consistency.cjs`, and `release-policy.cjs`'s own release-time re-verification from one array edit) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **SecretStr discipline:** all API keys use `SecretStr`; `.get_secret_value()` only at HTTP client init. The stub *arr test service does not need real API keys, but any test fixture that configures an instance must still pass a `SecretStr`-wrapped dummy key through the normal config path — don't bypass the type.
- **Loguru only, redacting sink, never print/logging module:** any new Python test helpers (stub service, smoke-test driver) must not use bare `print`/stdlib `logging` for anything that touches request/response bodies that could carry secrets; prefer loguru or plain test assertions.
- **Atomic file writes (write-then-rename):** the smoke test's "writable config" and "persistence across restart" checks are exercising this existing code path (`_atomic_toml_write`) — don't reimplement config writing in the test harness, drive it through `/setup` and `/settings` like a real user.
- **pytest-asyncio with `asyncio_mode=auto`:** any new async test helpers follow this existing convention; Playwright's **sync** API (used by `pytest-playwright`'s default `page` fixture) does not need `asyncio_mode` at all — don't mix sync Playwright fixtures into `async def` tests.
- **Buildomator + Greptile pilot rules (user's CLAUDE.md, repo CLAUDE.md):** never weaken CI or suppress findings; this phase can only ADD required checks, never relax existing ones (`secrets`, `dependencies`, `CI ready` composition must stay a superset of today's set).
- **Ruff linting (E, F, I, UP, B, SIM), line length 120, Python 3.11+ target:** new Python test/service files must pass `uv run ruff check triggarr/ tests/` — note the stub *arr service, if it lives under `tests/`, is covered by this; if it lives elsewhere (e.g. a new top-level test-infra directory), confirm whether ruff's `check triggarr/ tests/` invocation needs widening or whether the new directory should simply live under `tests/`.
- **Release safety is a safeguard change:** `release-policy.cjs`, `ci-job-consistency.cjs`, and the trusted-commit pin in `review-acceptance.yml` are explicitly flagged in repo conventions as changes requiring independent inspection before approval — this phase edits `release-policy.cjs` (adding `REQUIRED_JOBS` entries and the new version-check function), which the Buildomator/Greptile pilot and owner acceptance process should treat as a safeguard change, not routine code.
- **Owner CLI acceptance (docs/owner-cli-acceptance.md):** no change needed by this phase; noted for completeness since the phase's final PR will go through it.
- **D-10 enforcement reminder (from CONTEXT.md, elevated here because it is also a CLAUDE.md-adjacent safety rule):** never push a deliberately broken commit/branch without the owner's separate, explicit go-ahead at execution time, even though this phase's evidence standard requires doing so once for the broken-entrypoint demonstration.

## Summary

This phase adds three kinds of proof to Triggarr's existing, already well-architected CI/release pipeline: (1) a real container-startup smoke test that runs the exact audited image through its real entrypoint against a disposable config volume and a stub *arr HTTP service, (2) a small Playwright browser suite that proves the connection-pill polls on a bounded schedule and that setup/login/logout work as real browser flows, and (3) a tag-vs-package-vs-image-label identity check inserted into the release workflow before any publish action.

The codebase already has the right shape for all three. The `docker` job in `.github/workflows/ci.yml` builds, audits, and saves an `audited-image` artifact (`image.tar` + `image.tar.sha256` + `image-id.txt`) with the version baked into `org.opencontainers.image.version` — this is the one artifact every new check must download, verify, and reuse, never rebuild. The `ci-ready` aggregate job is driven by a single source of truth, `REQUIRED_JOBS` in `.github/scripts/release-policy.cjs`, which is independently checked for consistency against `ci.yml`'s actual job graph (`ci-job-consistency.cjs`) and independently re-verified against the real GitHub Actions API at release time (`preflight()` in the same file). Adding the two new CI jobs this phase needs (a container-smoke job and a browser-suite job) to that one array is what makes CISHIP-04 ("a missing or skipped mandatory job cannot let the gate pass") true almost for free — the existing machinery already enforces it in three independent places once the array is edited consistently.

The riskiest, least-precedented part of this phase is CISHIP-02's connection-pill assertion (D-28/D-29): proving the pill polls on a bounded schedule and that the polled state actually changes requires either waiting real wall-clock seconds in CI or using Playwright's browser-side clock API (`page.clock.fast_forward()` / `page.clock.install()`) to accelerate htmx's `setInterval`-driven `hx-trigger="every 30s"`. The app's own backend polling granularity (`search_interval`, minutes-only) cannot be shortened to seconds without a new runtime config knob (explicitly out of scope per Claude's Discretion), so the state change between polls should be driven by directly invoking the existing `POST /api/refresh-counts/{app}/{instance}` endpoint from the test harness against a stub *arr service whose reachability is flipped mid-test — this reuses an existing, already-tested code path rather than inventing new app behavior.

**Primary recommendation:** Add `playwright` + `pytest-playwright` (Python) as dev/CI-only dependencies (never touching the Docker runtime image); add two new parallel CI jobs (`image-smoke`, `browser-e2e`) that both depend on `docker`, download and identity-verify `audited-image`, and run against a purpose-built minimal stub *arr HTTP service on a Docker user-defined network; add both new job names to the single `REQUIRED_JOBS` array in `release-policy.cjs` (which cascades into `ci-ready`'s needs/required set and release-time re-verification); and add a tag-format + image-label identity check as new exported, independently-tested functions in `release-policy.cjs`, invoked as new steps in `release.yml`'s `release` job strictly before `docker/login-action`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Container entrypoint / startup smoke test | CI / Build pipeline | — | Exercises the shipped artifact's own `ENTRYPOINT`, not application code directly |
| Stub *arr test service (health/queue endpoints) | CI / Build pipeline (test infrastructure) | — | A throwaway HTTP double that exists only for the CI run's network; not part of the shipped product |
| Browser regression suite (pill, setup, login, logout) | CI / Build pipeline (drives) → Browser/Client (observes) → API/Backend (served by) | — | Playwright drives a real browser against the real container; it is CI infrastructure exercising the existing Browser-tier htmx behavior and Backend-tier routes together, end-to-end |
| Connection-pill polling behavior under test | Browser / Client | API / Backend | The htmx `hx-trigger`/`setInterval` logic is client-tier; the `/partials/connection-pill` data it polls is backend-tier — the test must observe both without changing either |
| Release tag / version / image-label identity check | CI / Build pipeline (release workflow) | — | Pure metadata comparison inside the trusted release workflow; no application or database tier involved |
| `REQUIRED_JOBS` / `ci-ready` consistency | CI / Build pipeline | — | Pure workflow-graph bookkeeping; the existing `ci-job-consistency.cjs` already generalizes this |
| Writable config / persistence-across-restart check | Database / Storage (the `/config` volume) | CI / Build pipeline (orchestrates) | Proves the Docker `VOLUME /config` and the app's atomic-TOML-write path survive a real restart, not a mocked one |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `playwright` (Python) | 1.64.0 (latest; floor-pin `>=1.60`) | Drives a real Chromium browser against the shipped container for CISHIP-02 | Official Microsoft-maintained browser automation library; the only Python option with a first-class, actively-developed clock/time-mocking API (`page.clock`) needed for D-28/D-29. `[VERIFIED: PyPI registry + playwright.dev official docs]` |
| `pytest-playwright` | 0.10.0 (latest; floor-pin `>=0.9`) | Wires Playwright into the existing `pytest` convention (auto-registers `page`/`browser`/`context` fixtures, `--browser`, `--tracing`, `--screenshot` CLI flags) | Official Microsoft plugin (same org as `playwright`); keeps the new suite inside the project's existing `pytest`/`uv run pytest` invocation pattern rather than introducing a second test runner. `requires_dist: pytest<10.0.0,>=7.0.0` — compatible with this repo's `pytest>=9.0.3`. `[VERIFIED: PyPI registry + playwright.dev official docs]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Node.js `node --test` (stdlib, already in use) | n/a (built-in) | Houses the new CISHIP-03 permanent negative tests for tag/version mismatch, alongside existing `release-policy.test.cjs` | Reuse — no new dependency. This is the established pattern for every release-safety negative test in this repo (D-04). |
| A minimal custom HTTP stub (Python stdlib `http.server`, or a tiny FastAPI/Starlette app) | n/a (hand-rolled, in-repo) | Answers the narrow *arr `system/status`-style endpoints the app's health/connection logic needs, with a runtime-switchable connected/disconnected state | Only `/api/v3/system/status` (and whatever queue/history endpoints `refresh_*_counts` calls) need responses — a general-purpose mock-server framework (WireMock, Prism, msw) would add a new ecosystem/toolchain for a ~2-endpoint surface; see "Don't Hand-Roll" for the boundary of what NOT to hand-roll instead. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Playwright (Python) | Playwright (Node.js/TypeScript) | Would introduce `package.json`/npm into a pure-Python+uv repo solely for 1 test suite; the Node `.test.cjs` scripts in `.github/scripts` are workflow-policy tests, not an app test harness, and are a different concern. Python keeps one toolchain. |
| Playwright | Selenium / Cypress | Selenium lacks a first-class clock/time-virtualization API comparable to Playwright's `page.clock`, which D-28/D-29's bounded-polling assertion needs. Cypress is JS-only (same toolchain objection as above) and its component-test model is a worse fit for "drive a real shipped container over HTTP." |
| Custom stub *arr service | A real Radarr/Sonarr/Lidarr Docker image, pre-seeded | Real *arr images are large, slow to start, and would require real-looking libraries/media state to answer `system/status` — massively disproportionate to the ~5 min CI budget (D-14) for proving "health/setup/login/static/config/persistence" and "pill polls on schedule," none of which require real *arr business logic. |
| Browser-side clock control (Playwright `page.clock`) | A new `TRIGGARR_PILL_INTERVAL` env var / config knob | Explicitly steered away from in Claude's Discretion ("A new runtime setting would be a product change and needs owner approval"). Also risks weakening the regression guarantee: a configurable interval could mask the exact bug (`load, every 30s` on swap) if the test environment's shortened interval changes polling *mechanics* rather than just *timing*. |

**Installation:**
```bash
# pyproject.toml [project.optional-dependencies] dev = [...]
#   "playwright>=1.60",
#   "pytest-playwright>=0.9",
uv lock
uv sync --extra dev
uv run playwright install --with-deps chromium
```

**Version verification:** Verified directly against PyPI's JSON registry API (`https://pypi.org/pypi/<name>/json`), not training-data recall:
```
playwright         latest=1.64.0   requires_python=">=3.10"
pytest-playwright  latest=0.10.0   requires_dist=["playwright>=1.18","pytest<10.0.0,>=7.0.0",...]
```
Both satisfy this repo's `requires-python = ">=3.11"`, CI's Python 3.13, and `pytest>=9.0.3`. A locally-cached `pip index versions` lookup returned stale data during this research (showed `pytest-playwright==0.7.1` as "latest" with a `pytest<9.0.0` constraint that would have conflicted with this repo's `pytest>=9.0.3`) — the live PyPI JSON API is the authoritative source and should be re-checked at implementation time rather than trusting a local package-index cache.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `playwright` | PyPI | ~6 years (first released 2020) | very high (millions/week across ecosystems) | github.com/microsoft/playwright-python | [OK] | Approved |
| `pytest-playwright` | PyPI | ~5 years | high | github.com/microsoft/playwright-pytest | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

Both packages are Microsoft-maintained, matched to their expected ecosystem (PyPI, not npm), confirmed via `pip install slopcheck` + `slopcheck install playwright pytest-playwright` (both scanned `[OK]`), and cross-verified against the official PyPI JSON registry endpoint and playwright.dev's official Python CI documentation (not WebSearch alone) — satisfying the `[VERIFIED]` bar for package-name provenance, not just registry existence.

## Architecture Patterns

### System Architecture Diagram

```
PR opened/updated, or push to main
            │
            ▼
   .github/workflows/ci.yml
   ┌─────────────────────────────────────────────────────────────┐
   │  test ──┐                                                   │
   │  lint ──┤                                                   │
   │         ▼                                                   │
   │       docker  (build → pip-audit → save audited-image       │
   │                 artifact: image.tar + .sha256 + image-id)   │
   │         │                                                   │
   │         ├───────────────► image-smoke  (NEW, CISHIP-01)     │
   │         │                   download+verify audited-image   │
   │         │                   docker run (real ENTRYPOINT)    │
   │         │                   against stub *arr + isolated    │
   │         │                   /config volume                  │
   │         │                   → health/setup/login/static/    │
   │         │                     writable-config/restart        │
   │         │                                                   │
   │         └───────────────► browser-e2e  (NEW, CISHIP-02)     │
   │                             download+verify audited-image   │
   │                             docker run (same artifact)      │
   │                             Playwright drives real browser  │
   │                             → pill polling, setup/login/     │
   │                               logout                        │
   │  secrets ──┐                                                │
   │  dependencies ──┤                                           │
   │                 ▼                                           │
   │              ci-ready  (needs: test,lint,docker,secrets,    │
   │                          dependencies,image-smoke,          │
   │                          browser-e2e; Python `required` set │
   │                          must equal `needs`)                │
   └─────────────────────────────────────────────────────────────┘
            │  (GitHub branch ruleset requires "CI ready" context)
            ▼
       merge to main → push-CI run succeeds
            │
            ▼
   .github/workflows/release.yml  (workflow_run, or tag push)
   ┌─────────────────────────────────────────────────────────────┐
   │ preflight (loads release-policy.cjs from MAIN, never tag)   │
   │   → validateEvidence(): re-checks REQUIRED_JOBS incl. the   │
   │     two new names actually succeeded on the exact commit    │
   │         │                                                   │
   │         ▼                                                   │
   │ release job:                                                │
   │   1. recheck preflight (same exact-commit evidence)         │
   │   2. NEW: validate tag format (vX.Y.Z, no pre-release)      │
   │   3. download + verify audited-image (sha256 + image ID)    │
   │   4. NEW: read image's org.opencontainers.image.version     │
   │      label; compare to tag (stripped "v"); fail closed      │
   │   5. docker/login-action (ghcr) ◄── nothing above this      │
   │      point may have passed on a mismatch                    │
   │   6. publish audited image (tag only, never rebuild)        │
   │   7. gh release create / upload                             │
   └─────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure
```
.github/
├── workflows/
│   ├── ci.yml                 # + image-smoke, browser-e2e jobs
│   └── release.yml            # + tag/version-identity steps before login
├── scripts/
│   ├── release-policy.cjs     # + REQUIRED_JOBS entries, + validateTagFormat/validateVersionIdentity
│   ├── release-policy.test.cjs       # + negative/positive cases for the new functions (D-04)
│   └── artifact-promotion.test.cjs   # + static check: new steps run before docker/login-action (D-05)
tests/
├── e2e/                        # NEW — Playwright suite, excluded from the default fast `pytest tests/` run
│   ├── conftest.py             #   base_url fixture, stub-*arr fixture, clock helpers
│   ├── test_pill_polling.py    #   D-28/D-29
│   └── test_setup_login_logout.py  # D-25
└── fixtures/
    └── arr_stub/                # minimal stub HTTP service + its own small test suite
```

### Pattern 1: Single point of truth for "mandatory job" membership
**What:** `REQUIRED_JOBS` in `release-policy.cjs` is read by three independent consumers: `ci-job-consistency.cjs` (statically checks it against `ci.yml`'s real job graph), `ci.yml`'s own `ci-ready` step (a hand-written Python `required` set that must match), and `preflight()`'s `validateEvidence()` (queries the live GitHub Actions API for each named job's status on the exact release commit).
**When to use:** Any time a new job must become "mandatory" for both merge (PR gate) and release (publish gate).
**Example:**
```javascript
// Source: .github/scripts/release-policy.cjs (this repo, read during research)
const REQUIRED_JOBS = ['test', 'lint', 'docker', 'secrets', 'dependencies', 'CI ready'];
// Recommended for this phase:
const REQUIRED_JOBS = ['test', 'lint', 'docker', 'secrets', 'dependencies',
                        'image-smoke', 'browser-e2e', 'CI ready'];
```
Editing this one array, plus adding matching entries to `ci.yml`'s `ci-ready` job (`needs:` list and the Python `required = {...}` set), is sufficient for `checkJobListConsistency()` in `ci-job-consistency.test.cjs` to pass — that test already asserts the real `ci.yml` and real `REQUIRED_JOBS` agree, with no changes needed to `ci-job-consistency.cjs` itself (it's already generic). This is the mechanism that gives CISHIP-04 its "cannot let the gate pass" property for free.

### Pattern 2: Download-and-verify, never rebuild
**What:** Every job that needs the shipped artifact downloads the `audited-image` artifact (uploaded once by `docker`) and re-verifies its sha256 + image ID before using it — exactly as the existing `docker` job's own "round-trip verification" step and `release.yml`'s "Verify and load audited image" step already do.
**When to use:** `image-smoke` and `browser-e2e` must both do this (D-30 requires image-identity verification even though they're new consumers, not the original job).
**Example:**
```yaml
# Source: .github/workflows/ci.yml (existing docker job, adapt for new jobs)
- uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4
  with:
    name: audited-image
    path: image
- name: Verify and load audited image
  working-directory: image
  run: |
    sha256sum -c image.tar.sha256
    docker load -i image.tar
    test "$(docker image inspect triggarr:ci-test --format '{{.Id}}')" = "$(cat image-id.txt)"
```
No `run-id:` is needed here (unlike `release.yml`'s cross-workflow download) because `image-smoke`/`browser-e2e` run in the *same* workflow run as `docker` — `actions/download-artifact` resolves same-run artifacts by name alone, exactly like the existing `docker` job's own round-trip step.

### Pattern 3: Isolated runtime config via `TRIGGARR_CONFIG_DIR` + a Docker named volume
**What:** The app already reads its config directory exclusively from the `TRIGGARR_CONFIG_DIR` env var (`triggarr/models/config.py::get_config_dir()`), defaulting to `/config`, and the Dockerfile declares `VOLUME /config`. No test-only code path is needed — a fresh named volume mounted at `/config` on a container started with the real `ENTRYPOINT` is already an isolated, writable, persistent config directory.
**Example:**
```bash
docker network create triggarr-smoke-net
docker run -d --name arr-stub --network triggarr-smoke-net arr-stub:test
docker volume create triggarr-smoke-config
docker run -d --name triggarr-smoke \
  --network triggarr-smoke-net \
  -p 18484:8484 \
  -v triggarr-smoke-config:/config \
  -e TRIGGARR_CONFIG_DIR=/config \
  triggarr:ci-test   # the loaded, verified audited-image tag
# ... health/setup/login/static checks via curl against localhost:18484 ...
docker stop triggarr-smoke && docker rm triggarr-smoke
docker run -d --name triggarr-smoke-2 \
  --network triggarr-smoke-net \
  -p 18484:8484 \
  -v triggarr-smoke-config:/config \
  -e TRIGGARR_CONFIG_DIR=/config \
  triggarr:ci-test
# ... re-check /health and that the admin account created during setup still logs in ...
```
Starting a *new* container on the same named volume (rather than `docker stop`/`docker start` on the same container) is the stronger persistence proof: it re-exercises `entrypoint.sh`'s PUID/PGID `chown -R` logic against an already-populated, non-empty `/config` directory — an edge case `docker start` on the same container does not re-exercise (the chown already happened once; `docker start` just resumes the same process). Both are explicitly acceptable per CONTEXT.md's "Specific Ideas" note ("survive a `docker stop`/`start` (or a new container on the same volume)").

### Pattern 4: Tag/version identity check placement in `release.yml`
**What:** The release workflow's `preflight`/`release` jobs checkout with `sparse-checkout: .github/scripts` from `main` only — `pyproject.toml` is deliberately NOT available to the release workflow, so the new check must NOT try to read `pyproject.toml` from inside `release.yml`. D-18 already establishes why this is safe: `tests/test_version.py` (in the already-mandatory `test` job) transitively guarantees `pyproject.toml == uv.lock == __version__` on every commit that reaches `main`; the release workflow only needs to compare the **tag** against the **image's own version label** (which was derived from `pyproject.toml` back when the `docker` job built it).
**Example:**
```javascript
// Source: this repo's .github/scripts/release-policy.cjs, extended (recommended, not yet implemented)
function validateTagFormat(tagRef) {
  // tagRef e.g. "refs/tags/v2.13.0"
  const m = /^refs\/tags\/v(\d+\.\d+\.\d+)$/.exec(tagRef);
  if (!m) throw new Error(`Malformed or pre-release tag rejected: ${tagRef}`);
  return m[1]; // "2.13.0" -- nonnegative integers, no leading zeros (regex already enforces no leading zero via \d+ -- add explicit check if "0" vs "01" matters)
}

function validateVersionIdentity({tagVersion, imageVersionLabel}) {
  if (!imageVersionLabel) {
    throw new Error(`Release rejected: image version label not inspected (tag=${tagVersion})`);
  }
  if (tagVersion !== imageVersionLabel) {
    throw new Error(
      `Release rejected: tag version (${tagVersion}) disagrees with audited image label (${imageVersionLabel})`
    );
  }
  return tagVersion;
}
module.exports = {..., validateTagFormat, validateVersionIdentity};
```
```yaml
# Source: .github/workflows/release.yml, new steps (recommended placement)
      - name: Validate tag format
        if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')
        uses: actions/github-script@ed597411d8f924073f98dfc5c65a23a2325f34cd # v8
        with:
          script: |
            const {validateTagFormat} = require('./.github/scripts/release-policy.cjs');
            validateTagFormat(context.ref);
      # ... existing "Download exact successful CI image" + "Verify and load audited image" steps ...
      - name: Read audited image version label
        id: image-version
        run: |
          version="$(docker image inspect triggarr:ci-test --format '{{index .Config.Labels "org.opencontainers.image.version"}}')"
          echo "version=$version" >> "$GITHUB_OUTPUT"
      - name: Validate tag/image version identity
        if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')
        uses: actions/github-script@ed597411d8f924073f98dfc5c65a23a2325f34cd # v8
        env:
          IMAGE_VERSION: ${{ steps.image-version.outputs.version }}
        with:
          script: |
            const {validateTagFormat, validateVersionIdentity} = require('./.github/scripts/release-policy.cjs');
            const tagVersion = validateTagFormat(context.ref);
            validateVersionIdentity({tagVersion, imageVersionLabel: process.env.IMAGE_VERSION});
      # ... only now: docker/login-action, docker push, gh release create ...
```
This placement satisfies D-24 (before login/push/release creation), D-23 (report "not inspected" if the image step hasn't run yet — the two steps are deliberately separate so a tag-format failure reports before the image is even loaded), and D-04 (both functions are exported, pure, and directly testable from `release-policy.test.cjs` with no duplicated validation logic).

### Anti-Patterns to Avoid
- **Re-deriving the package version inside `release.yml`:** Would require widening the deliberately narrow `sparse-checkout: .github/scripts` to include `pyproject.toml`, reopening a tag-tampering surface the existing sparse-checkout was specifically designed to close ("Release logic is loaded from main... so tag contents can't alter the policy" — an established pattern per CONTEXT.md). Compare the tag to the image label instead (Pattern 4).
- **Rebuilding the Docker image inside `image-smoke`/`browser-e2e`:** Violates D-30 and the project's explicit "Retain / do not copy blindly" guidance (`docs/ci-reference-baseline-plan.md`: "Do not copy rebuild-after-test publication... into PR tests"). Always download+verify the `docker` job's artifact.
- **Giving the new CI jobs a custom `name:` override without updating `REQUIRED_JOBS` to match:** `ci-job-consistency.cjs`'s `extractCiReady()` computes effective job names as "the job's `name:` override if present, else its id" — if a new job sets `name: "Image Smoke Test"` but `REQUIRED_JOBS` still says `'image-smoke'`, the consistency check fails (correctly). Keep job ids and `REQUIRED_JOBS` entries identical unless deliberately overriding both.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Driving a real browser, bounded-time polling assertions | A custom headless-Chrome-via-CDP harness, or a hand-rolled `setInterval`-wait-and-poll script | Playwright's `page.clock` API (`install`, `fast_forward`, `pause_at`, `run_for`) | Purpose-built for exactly this (virtualizing timers without flaky real-time `sleep()` calls); confirmed present and stable in current Playwright (added v1.45, Python bindings confirmed via official docs) |
| Verifying the exact shipped image hasn't drifted | Hand-rolled file-diffing or a second `docker build` to "compare" | The existing `sha256sum -c image.tar.sha256` + `docker image inspect --format '{{.Id}}'` comparison, already used by `docker` job's round-trip step and `release.yml` | Already battle-tested in this repo; don't invent a second identity mechanism |
| Version string parsing/validation | A new semver library dependency (e.g. `semver` npm package) for a 3-field `vX.Y.Z` check | A small hand-written regex, matching the style already used in `ci.yml`'s `image-meta` step (`re.fullmatch(r'[A-Za-z0-9.!+_-]+', version)`) | The tag grammar this phase needs (D-21: exactly `vX.Y.Z`, no pre-release/build metadata, no leading zeros) is narrower than general semver (which permits `-rc1`/`+build` the project explicitly wants rejected) — a general semver library would need extra code to re-reject what it natively accepts anyway |
| A fake *arr backend with realistic business logic | A full in-memory clone of Radarr/Sonarr/Lidarr's API surface | A minimal stub answering only `system/status` (and whichever specific endpoints `refresh_*_counts`/startup call) with a runtime-togglable connected/disconnected state | Nothing in CISHIP-01/02 needs real media-library semantics — only reachability and a basic version-ish response; a full API clone is disproportionate complexity for a CI fixture (explicitly flagged in Claude's Discretion as something to design minimally) |
| CI job "is this mandatory and consistent" bookkeeping | A new YAML-parsing or job-graph tool | The existing `ci-job-consistency.cjs` (already a generic parser/checker, not hardcoded to today's 5 jobs) | It already handles arbitrary job sets — this phase only needs to add entries to the data it checks (`REQUIRED_JOBS`, `ci.yml`'s needs list), not touch the checker itself |

**Key insight:** Nearly every piece of this phase already has an existing, generalized mechanism in this repo (artifact identity verification, required-job consistency, release-time re-verification, atomic config writes) — the actual new work is a stub test-double service, a Playwright suite, and ~2 small pure functions. Resist the urge to build new infrastructure where the existing infrastructure already generalizes.

## Common Pitfalls

### Pitfall 1: The connection pill's `hx-trigger` lives in TWO templates, not one
**What goes wrong:** Testing only `triggarr/templates/partials/connection_pill.html` (which has `hx-trigger="every 30s"`) misses that `triggarr/templates/base.html` has a *different* placeholder div with `hx-trigger="load, every 30s"` that fetches the partial on initial page load. The original bug (PR #27, commit `d41b484`) was the partial *also* carrying `"load, every 30s"`, so every outerHTML swap re-included the `load` trigger, firing another request immediately — a true request loop.
**Why it happens:** htmx's `hx-swap="outerHTML"` on the placeholder replaces the whole element (including its `hx-trigger` attribute) with the server's response. If the partial's response re-includes `load`, the *new* element fires on its own insertion into the DOM, infinitely.
**How to avoid:** The browser regression test must assert the actual network request count over an observation window stays bounded (e.g., initial load + N scheduled polls, not dozens), not just assert a string is/isn't present in one template file (the existing `tests/test_header_redesign.py::test_connection_pill_partial_does_not_retrigger_on_swap` already does the latter at the template-string level — CISHIP-02 explicitly wants the *behavioral* guarantee this file does not provide).
**Warning signs:** A request-count assertion that passes with a suspiciously large tolerance band, or one that only ever observes exactly 1 request (never reaching the "at least two scheduled refreshes" D-28 requires).

### Pitfall 2: `search_interval` cannot be shortened below whole minutes — don't drive pill-state changes off the real search cycle
**What goes wrong:** `InstanceConfig.search_interval: int = 30` is minutes, wired into APScheduler via `scheduler.add_job(..., "interval", minutes=cfg.search_interval, ...)` (`triggarr/search/scheduler.py`). There is no sub-minute granularity. A test that tries to get `connected` to flip by waiting for a real scheduled search cycle will need to wait at least 1 real minute per cycle, incompatible with the ~5 minute total CI budget (D-14) for a single assertion, and incompatible with Playwright's browser-side clock (which only virtualizes *browser* JS timers, not the server-side APScheduler process running in a separate container).
**Why it happens:** The scheduling granularity was designed for a background daemon polling real third-party APIs, not for sub-second test determinism.
**How to avoid:** Drive the state change directly via the already-existing `POST /api/refresh-counts/{app}/{instance}` endpoint (confirmed in `triggarr/web/routes.py` to set `ist["connected"] = True`/`False` exactly like a scheduled cycle, without touching `last_run`/`last_success`/the failure counter) from the test harness, between two pill polls, while flipping the stub *arr service's reachability. This proves the *pill* actually re-fetches and re-renders changed state, without needing the real scheduler to run at test speed, and without inventing new app behavior.
**Warning signs:** A test that passes by coincidence because the stub *arr's state never actually changed (i.e., it would pass even with a hardcoded/cached pill).

### Pitfall 3: Origin/Referer CSRF check is permissive to header-less requests — plan the smoke test's HTTP client accordingly
**What goes wrong:** `OriginCheckMiddleware` rejects a POST only when an `Origin` or `Referer` header is present and mismatches `Host`; it explicitly allows the request through when *neither* header is present (`"same-origin browser requests may omit both headers"`). A plain `curl -X POST` or Python `requests.post()` (no `Origin` header) for the CISHIP-01 smoke test's setup/login checks will pass the CSRF gate without any special handling — but a test harness that *sets* an `Origin` header from a habit of "being realistic" must set it to match the `Host` header exactly (including port, e.g. `http://localhost:18484`) or the request will be rejected with 403.
**Why it happens:** The middleware is tuned for real browsers (which always send Origin/Referer for cross-origin and often for same-origin POSTs) vs. simple CLI HTTP clients (which send neither by default).
**How to avoid:** For CISHIP-01's non-browser HTTP checks, either send no `Origin`/`Referer` header at all, or if sent, make sure it exactly matches the container's externally-reachable `Host:port`.
**Warning signs:** Intermittent 403s on setup/login POSTs that only reproduce when the test's HTTP client library auto-populates an Origin/Referer header differing from the mapped port.

### Pitfall 4: Secrets can leak into Playwright traces/HAR files even with disposable test credentials (D-27)
**What goes wrong:** Playwright's trace/HAR recording captures full request/response headers (including `Cookie`/`Set-Cookie`) and DOM snapshots (including typed form values) by default. Even though D-27 mandates disposable test credentials (limiting real-world blast radius), the requirement is explicit that these values must not appear in captured artifacts at all.
**Why it happens:** Trace/HAR recording is designed for maximum debuggability, which is in tension with minimum sensitive-data capture. As of October 2026, Playwright has an in-progress `secrets` redaction option for traces (merged ~Oct 16, 2026) and a fix removing full context options (including credentials) from trace context-options events — but which *stable* release ships either is unconfirmed as of this research; treat both as **not yet verified available** in whatever Playwright version is actually pinned.
**How to avoid:** (1) Record traces/screenshots only on failure (`--tracing=retain-on-failure`, default-off screenshots except on failure) rather than always-on, per the official Playwright CI pattern — this also keeps D-15's "no retries that turn failure into pass, but keep logs/screenshots/traces from the first failure" intact by construction. (2) Do not use `recordHar`/`routeFromHAR` for this suite at all unless a specific need arises; if used, pass `content: "omit"`. (3) As a manual, one-time verification step when first standing up the suite (and whenever Playwright is upgraded), open an uploaded failure trace and confirm no cookie/session value is visible — this is exactly the kind of thing D-06's "recorded demonstration" evidence standard is suited for, even though it's not one of the explicitly named demonstrations.
**Warning signs:** A trace artifact that, when opened, shows the `triggarr_session` cookie value or the test account's plaintext password in a form-fill snapshot.

### Pitfall 5: `uv.lock` must be regenerated and committed after adding Playwright, or CI's `--locked` install fails
**What goes wrong:** `ci.yml`'s `test`, `lint`, and `dependencies` jobs all run `uv sync --locked` / `uv export --locked`, which fail closed if `pyproject.toml` and `uv.lock` disagree.
**Why it happens:** Standard `uv` lockfile discipline — adding a new `dev` extra entry to `pyproject.toml` without running `uv lock` leaves the lockfile stale.
**How to avoid:** Run `uv lock` (not just `uv sync`) after editing `pyproject.toml`'s `dev` list, and commit the updated `uv.lock` in the same change.
**Warning signs:** `test`/`lint`/`dependencies` jobs failing with a lockfile-mismatch error immediately after the dependency-adding commit, unrelated to any test logic.

### Pitfall 6: The release workflow has two near-identical `if:` conditions (`preflight` and `release`) that must stay equal
**What goes wrong:** `ci-job-consistency.test.cjs` already has a test (`'release.yml preflight and release if: are equal and non-null'`) asserting this. New tag-format/version-identity steps gated with `if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')` are a *narrower* condition than the job-level `if:` (which also handles the `workflow_run` trigger) — this is correct (tag-only steps should be skipped on the `workflow_run`/main-push path, which doesn't publish to `:latest` or create a GitHub Release either), but don't accidentally copy the job-level condition onto these tag-only steps or they'll run (and need to handle "no tag" data) on every main-push release run too.
**Why it happens:** Easy to confuse "when does this job run at all" with "when does this specific tag-only step run within the job."
**How to avoid:** Mirror the existing pattern already used by "Download exact successful CI Python distributions" / "Verify distribution artifacts before any publication" steps, which already use the narrower `if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/v')` condition for tag-only behavior within the shared `release` job.
**Warning signs:** The new steps attempting to read `context.ref` as a tag ref during a `workflow_run`-triggered main-push release, where `github.ref` is `refs/heads/main`, not a tag.

## Code Examples

### Minimal stub *arr service shape (recommended, not yet implemented)
```python
# Source: this repo's inferred need from triggarr/clients/base.py (_status_path = "/api/v3/system/status")
# and triggarr/search/engine.py (refresh_radarr_counts sets connected True/False on
# fetch success/failure) -- a minimal control surface, not verified against an existing file.
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()
_state = {"up": True}

@app.get("/api/v3/system/status")
async def status():
    if not _state["up"]:
        return JSONResponse({"error": "down"}, status_code=503)
    return {"version": "5.0.0.0", "appName": "TestArrStub"}

@app.post("/__control/set-up")
async def set_up(up: bool):
    _state["up"] = up
    return {"up": _state["up"]}
```
Run as its own container on the same Docker user-defined network as the triggarr container under test; the triggarr container's instance config points its `url` at `http://arr-stub:9000` (or whatever port the stub listens on). The `__control` endpoint is how the test harness flips reachability between polls (Pitfall 2).

### Bounded connection-pill polling assertion (recommended pattern, not yet implemented)
```python
# Source: synthesized from Playwright's official Python Clock API docs
# (https://playwright.dev/python/docs/api/class-clock) + this repo's confirmed
# hx-trigger="every 30s" (partial) / "load, every 30s" (base.html placeholder).
import re

def test_pill_polls_on_bounded_schedule(page, base_url):
    pill_requests = []
    page.on("request", lambda req: pill_requests.append(req) if "/partials/connection-pill" in req.url else None)

    page.clock.install()
    page.goto(base_url)
    assert len(pill_requests) == 1  # the "load" trigger on base.html's placeholder

    page.clock.fast_forward("00:31")
    assert len(pill_requests) == 2  # first "every 30s" tick

    page.clock.fast_forward("00:31")
    assert len(pill_requests) == 3  # second "every 30s" tick -- D-28's "at least two scheduled refreshes"

    # Bounded, not exact-at-a-deadline (D-28): allow a little jitter, but a request-loop
    # regression would produce far more than this.
    assert len(pill_requests) <= 5
```
This test should be run twice in CI's sense only once (D-02): once against the real app (must pass), and the "reintroduce the bug" / "disable polling" variants are **recorded demonstrations** per D-01/D-06, not a second job step that runs on every CI run.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| `--entrypoint python` override to inspect image dependencies | Real `ENTRYPOINT ["/entrypoint.sh"]` startup smoke test | This phase (CISHIP-01) | Proves PUID/PGID handling, `/config` ownership, and `setpriv` privilege drop actually work — the existing `docker` job's pip-freeze step explicitly proves nothing about startup (noted verbatim in CONTEXT.md's "Specific Ideas") |
| Template-string assertions for htmx behavior (`test_header_redesign.py`) | Behavioral browser assertions (request counts/content changes over time) | This phase (CISHIP-02) | Catches a *regression* of the exact bug class that already shipped once (PR #27), which a string-presence test cannot — a correct string can still describe broken runtime behavior if, e.g., a future change moves the trigger elsewhere |
| Playwright context/trace recording captured full `context-options` (including credentials) | PR microsoft/playwright#43220 (merged, stable-release TBD) trims context-options trace events to non-sensitive fields only; PR #43423 (merged Oct 16, 2026) adds a `secrets` redaction option | October 2026, unconfirmed stable release | Until confirmed present in the pinned Playwright version, rely on "trace/screenshot on failure only" + disposable credentials as the primary D-27 mitigation, not the new redaction features |

**Deprecated/outdated:**
- Relying solely on `docker run --entrypoint python ... pip freeze` as evidence of "the image works": this remains valid for dependency auditing but was never evidence of startup correctness; this phase adds the missing proof without removing the existing audit step.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `POST /api/refresh-counts/{app}/{instance}` is the right mechanism to flip `connected` state between pill polls for CISHIP-02's test, rather than waiting for a real scheduled search cycle | Common Pitfalls (Pitfall 2), Code Examples | If wrong, the pill test would need a different state-change trigger (e.g., a dedicated test-only health-check endpoint), adding scope; verify `refresh_radarr_counts`/`refresh_sonarr_counts`/`refresh_lidarr_counts` actually set `ist["connected"]` as read at the time of implementation (confirmed via `grep` during this research, but re-confirm no intervening refactor) |
| A2 | A new container on the same named Docker volume is a stronger persistence proof than `docker stop`/`docker start` on the same container | Architecture Patterns (Pattern 3) | Low risk — both are explicitly acceptable per CONTEXT.md; this is a recommendation, not a requirement, and the planner/executor may choose either |
| A3 | Playwright's `page.clock` timer virtualization actually intercepts htmx's `setInterval`-based `"every Xs"` trigger mechanism | Code Examples, Common Pitfalls (Pitfall 1) | Confirmed `setInterval` string present in the vendored `htmx.min.js` (v2.0.8) via direct grep, and Playwright's clock API is documented to override `window.setInterval`/`setTimeout` globally once installed — but the exact interaction has not been executed/verified in this repo; if it doesn't work as expected, fall back to real (shortened via `fast_forward`-equivalent wall-clock waits with a smaller real test-only interval is NOT available per Discretion's guidance against a new runtime knob) — flag for the planner as the single highest-uncertainty implementation detail in this phase |
| A4 | Adding `playwright`/`pytest-playwright` to `pyproject.toml`'s `dev` extra (not a new `e2e` extra) is sufficient and matches project convention | Standard Stack | Low risk — `uv sync --extra dev` is the existing CI convention; a separate `e2e` extra would also work but adds a second `uv sync` invocation for no clear benefit given this repo's single `dev` extra convention |
| A5 | New Playwright E2E test files belong under `tests/e2e/` and are excluded from the default `pytest tests/ -q` invocation used by the `test` job | Architecture Patterns (Recommended Project Structure) | If the planner instead wants them inside `tests/` proper, the `test` job's `pytest tests/ -q` step would attempt to collect and run them (requiring Playwright/a browser/a running container inside that job, which does not have one) — this must be explicitly scoped either via a separate `pytest tests/e2e` invocation in the new `browser-e2e` job, or a pytest marker + `-m "not e2e"` exclusion in the `test` job's existing command |

**If this table is empty:** N/A — assumptions listed above need planner/executor confirmation, particularly A3.

## Open Questions

1. **Does Playwright's `page.clock` virtualization reliably advance htmx's internal polling timer across a real network round-trip to a real (non-mocked) backend, inside a CI container?**
   - What we know: htmx 2.0.8 (vendored in this repo) uses `setInterval` somewhere in its trigger-processing code (confirmed via grep); Playwright's Clock API is documented to override global timer functions once `page.clock.install()` is called, before `page.goto()`.
   - What's unclear: Whether `fast_forward()`'s "fire pending timers at most once" semantics correctly fire htmx's specific internal scheduling mechanism (htmx may re-schedule via a recursive `setTimeout` rather than a single long-lived `setInterval`, which could require `run_for()` instead of `fast_forward()` to get each tick) — this needs a short spike against the real `connection_pill.html`/`base.html` markup before the planner commits to exact API calls in the implementation plan.
   - Recommendation: Treat Pattern/Code-Example's `fast_forward()` calls as a starting point, not gospel; the first implementation task for CISHIP-02 should include a quick manual/spike verification of clock-vs-htmx-interval interaction before writing the full assertion suite, and fall back to `run_for()` if `fast_forward()` doesn't fire the expected number of requests.

2. **Exact current SHA pins for any new GitHub Actions used (e.g., `actions/cache` if browser caching is added).**
   - What we know: this repo enforces full-SHA pinning for every action (confirmed convention across `ci.yml`/`release.yml`).
   - What's unclear: This research did not fetch and verify a specific SHA for `actions/cache` (official Playwright guidance recommends skipping browser caching anyway, since restore time ≈ download time — see State of the Art/Standard Stack), so no new action may even be needed.
   - Recommendation: If the planner decides caching is worth it despite official guidance, look up the current `actions/cache` release SHA at implementation time — do not reuse a SHA from training data or copy one from an unrelated public example without verifying it against the actual `actions/cache` repository tags.

3. **Should the missing-static-asset negative test target `tests/e2e` (Playwright) or `image-smoke`'s plain-HTTP checks?**
   - What we know: D-01 classifies "a missing static asset" as a cheap, permanent negative test (not an expensive one-off demonstration); CISHIP-01's own listed assertions include "static assets."
   - What's unclear: Whether this negative belongs inside the `image-smoke` job (mutating a running container's writable layer via `docker exec ... rm ...` before a `curl` check, per the technique documented in this research's Architecture section) or as a Playwright-level network-404 assertion in `browser-e2e`.
   - Recommendation: Put it in `image-smoke` — it's a container/HTTP-layer concern (does `/static/css/output.css` 404 when absent), not a browser-behavior concern, and keeps `browser-e2e` scoped to D-25/D-28 only.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Engine (GitHub-hosted `ubuntu-latest` runner) | `image-smoke`, `browser-e2e` (container lifecycle, `docker network`/`docker volume`) | ✓ (GitHub-hosted runners ship Docker Engine preinstalled) | Runner-provided, not independently pinned by this repo | — |
| Python 3.13 via `actions/setup-python` | `test`, `lint`, new `browser-e2e`'s pytest/Playwright invocation | ✓ (already used in `ci.yml`) | 3.13 (pinned in existing workflow steps) | — |
| `uv` via `astral-sh/setup-uv` | dependency install for the new Playwright deps | ✓ (already used in `ci.yml`) | pinned action SHA already in repo | — |
| Node.js (preinstalled on `ubuntu-latest`, used via bare `node --test`) | New CISHIP-03 negative tests in `.github/scripts/*.test.cjs` | ✓ (already relied on by existing `test` job step) | Runner-provided | — |
| Playwright browser binaries (Chromium) | `browser-e2e` | Not yet installed anywhere in this repo — new, must be installed via `playwright install --with-deps chromium` as a new CI step | 1.64.0 (matching the pinned `playwright` Python package version) | None needed — this is a required new install step, not optional |

**Missing dependencies with no fallback:**
- None that block execution — Playwright browser binaries are a new, required install step (not a missing environment capability), fully addressed by adding the install step to the new `browser-e2e` job.

**Missing dependencies with fallback:**
- None identified.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` (existing, `pytest>=9.0.3`) + `pytest-playwright` (new) for the browser suite; Node.js stdlib `node --test` (existing) for release-policy negatives |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (existing: `asyncio_mode = "auto"`) — the new `tests/e2e/` suite should NOT inherit `asyncio_mode=auto` concerns since Playwright's sync API fixtures are plain `def test_...`, not `async def` |
| Quick run command | `uv run --no-sync pytest tests/ -q` (existing, unit/integration — must continue to EXCLUDE `tests/e2e/`) |
| Full suite command | `uv run --no-sync pytest tests/e2e -q --browser chromium --tracing=retain-on-failure` (new, browser suite — runs only inside `browser-e2e` job, against a live container) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CISHIP-01 | Health/setup/login/static/writable-config/persistence against the real entrypoint | smoke (shell/HTTP, inside `image-smoke` job) | `curl`/`requests`-based script, run as a CI job step (not a pytest file) | ❌ Wave 0 — new job script |
| CISHIP-01 | Broken entrypoint fails the check | smoke, recorded demonstration (not per-run) | manual/documented recipe in repo (D-08); not a standing automated test | ❌ Wave 0 — reproduction recipe doc |
| CISHIP-01 | Missing static asset fails the check | smoke, permanent (D-01) | same `image-smoke` job, extra step mutating the running container's writable layer then re-`curl`ing | ❌ Wave 0 — new job step |
| CISHIP-02 | Pill polls on bounded schedule, state updates between polls | browser (Playwright) | `uv run pytest tests/e2e/test_pill_polling.py --browser chromium` | ❌ Wave 0 — new file |
| CISHIP-02 | Setup/login/logout as real browser flows | browser (Playwright) | `uv run pytest tests/e2e/test_setup_login_logout.py --browser chromium` | ❌ Wave 0 — new file |
| CISHIP-02 | Reintroducing polling bug fails suite | browser, recorded sensitivity check (D-02) | manual/documented recipe, not a standing per-run test | ❌ Wave 0 — reproduction recipe doc |
| CISHIP-03 | Tag/version/label mismatch rejected; match accepted | unit (Node `node --test`) | `node --test .github/scripts/release-policy.test.cjs` (extended) | ❌ Wave 0 — new test cases in existing file |
| CISHIP-03 | Rejection happens before login/push/release-create | static/wiring (Node `node --test`) | `node --test .github/scripts/artifact-promotion.test.cjs` (extended, string-position style like its existing tests) | ❌ Wave 0 — new test cases in existing file |
| CISHIP-04 | New jobs join `ci-ready`; missing/skipped job fails the gate | static consistency (Node `node --test`, already generic) | `node --test .github/scripts/ci-job-consistency.test.cjs` (existing test `'real ci.yml and real REQUIRED_JOBS are consistent'` already covers this once `REQUIRED_JOBS`/`ci.yml` are updated) | ✅ existing, auto-covers once data is updated |

### Sampling Rate
- **Per task commit:** `node --test .github/scripts/*.test.cjs` (fast, seconds) for CISHIP-03/04 work; `uv run ruff check` for any new Python files.
- **Per wave merge:** Full `uv run pytest tests/ -q` (unit/integration) + a real `image-smoke`/`browser-e2e` CI run (these cannot be meaningfully run locally without Docker + the built image; treat the CI run itself as the wave-merge gate for CISHIP-01/02).
- **Phase gate:** All of `test`, `lint`, `docker`, `secrets`, `dependencies`, `image-smoke`, `browser-e2e` green on a real PR before `/bm:verify-work`; plus the D-07-mandated real GitHub CI run demonstrating the broken-entrypoint and pill-bug-reintroduction negatives on an isolated branch/draft PR (not main, not a production tag).

### Wave 0 Gaps
- [ ] `tests/e2e/conftest.py` — base_url fixture pointed at the running smoke/e2e container, stub-*arr control fixture
- [ ] `tests/e2e/test_pill_polling.py` — covers CISHIP-02 (pill)
- [ ] `tests/e2e/test_setup_login_logout.py` — covers CISHIP-02 (D-25)
- [ ] A minimal stub *arr HTTP service (new file(s), location TBD by planner — e.g. `tests/fixtures/arr_stub/` or a dedicated `testinfra/` directory) + its own packaging so it can run as a CI-built throwaway Docker image or a plain `uv run python -m ...` process reachable on the Docker network
- [ ] New `image-smoke` CI job script (shell, not pytest) — container lifecycle, health/setup/login/static/config/restart checks, missing-asset negative
- [ ] `release-policy.cjs` — `validateTagFormat`, `validateVersionIdentity` (or equivalent) exported functions
- [ ] `release-policy.test.cjs` — positive + negative cases for the two new functions (D-04)
- [ ] `artifact-promotion.test.cjs` — static wiring assertion that the new validation steps run before `docker/login-action` (D-05)
- [ ] Framework install: `uv add --optional dev playwright pytest-playwright` (or manual `pyproject.toml` edit + `uv lock`) + `uv run playwright install --with-deps chromium` as a new CI step

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | yes (indirectly) | This phase doesn't change auth logic; it adds browser-level regression coverage for the *existing* session-cookie login flow (`triggarr/auth.py`'s `sign_session`/`verify_password`, already implemented) — no new control needed, just test coverage |
| V3 Session Management | yes (indirectly) | Same — logout/session-invalidation behavior is asserted at the browser level for the first time (CISHIP-02/D-25), using existing `triggarr_session` cookie mechanics |
| V4 Access Control | no (new) | Not touched by this phase |
| V5 Input Validation | yes | New tag-format regex (`validateTagFormat`) and version-label comparison (`validateVersionIdentity`) are themselves input validation on untrusted-ish data (a git tag ref) — fail closed, reject malformed input, matches existing style (`ci.yml`'s `image-meta` step's `re.fullmatch` check) |
| V6 Cryptography | no (new) | Not touched; no new cryptographic code |
| V7 Error Handling / Logging | yes | D-23's "report the reason and the tag/package/image versions available... never invent a value" and D-27's "no secrets in captured artifacts" are both error-handling/logging-adjacent controls this phase must get right |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Tag/artifact confusion — publishing an image whose contents don't match its claimed version | Tampering / Repudiation | CISHIP-03's tag-vs-label identity check, layered on top of the already-existing image-ID/sha256 identity checks (D-19) |
| Secrets (session cookies, test credentials) leaking into CI artifact storage (traces, screenshots, logs) | Information Disclosure | Disposable test credentials (D-27) + failure-only trace/screenshot capture + avoiding HAR recording (Common Pitfalls, Pitfall 4) |
| A skipped/renamed CI job silently stops being "mandatory" without anyone noticing | Repudiation / Tampering (of the CI process itself) | The existing `REQUIRED_JOBS`/`ci-job-consistency.cjs`/`preflight()` triad (Architecture Pattern 1), extended with this phase's two new job names |
| A deliberately broken branch gets pushed to a public/shared location by accident | (process risk, not STRIDE) | D-10: every broken-commit push requires the owner's separate, explicit go-ahead at execution time — this is a process control this research cannot verify technically, only flag for the executor to respect |

## Sources

### Primary (HIGH confidence)
- This repository, read directly during research: `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `.github/workflows/review-acceptance.yml`, `.github/scripts/release-policy.cjs`, `.github/scripts/release-policy.test.cjs`, `.github/scripts/ci-job-consistency.cjs`, `.github/scripts/ci-job-consistency.test.cjs`, `.github/scripts/artifact-promotion.test.cjs`, `Dockerfile`, `entrypoint.sh`, `pyproject.toml`, `triggarr/models/config.py`, `triggarr/web/routes.py`, `triggarr/web/middleware.py`, `triggarr/web/security.py`, `triggarr/search/scheduler.py`, `triggarr/search/engine.py`, `triggarr/templates/base.html`, `triggarr/templates/partials/connection_pill.html`, `triggarr/static/js/htmx.min.js`, `tests/test_header_redesign.py`, `tests/test_auth_integration.py`, `tests/test_version.py`, `tests/test_github_workflows.py`
- GitHub REST API, queried live during research: `GET /repos/thejuran/triggarr/rulesets/14805779` — confirmed the branch ruleset's `required_status_checks` list is exactly `["CI ready", "Greptile Review", "Review acceptance", "CodeQL"]`, i.e., no ruleset change is needed for CISHIP-01/02's new jobs since they feed the already-required "CI ready" context
- PyPI JSON registry API (`https://pypi.org/pypi/playwright/json`, `https://pypi.org/pypi/pytest-playwright/json`) — authoritative version/dependency metadata
- `slopcheck install playwright pytest-playwright` — both `[OK]`
- https://playwright.dev/python/docs/api/class-clock — official Clock API reference (fetched via WebSearch results quoting the page directly)
- https://playwright.dev/python/docs/ci and https://playwright.dev/python/docs/ci-intro — official CI setup guidance, including the "caching browsers is not recommended" statement

### Secondary (MEDIUM confidence)
- WebSearch results summarizing Playwright trace/HAR secret-leakage behavior and the in-progress `secrets` trace-redaction feature (PRs microsoft/playwright#43423, #43220) — real PRs, but unconfirmed which stable release includes them as of this research; treated as not-yet-reliable mitigation, with failure-only capture + disposable credentials as the primary, verified-available mitigation instead

### Tertiary (LOW confidence)
- None relied upon as load-bearing for this research's recommendations — every claim above is either a direct repository read, a live GitHub API query, an official-docs citation, or explicitly flagged as an open question/assumption for the planner.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Playwright/pytest-playwright versions and compatibility verified against live PyPI registry data, not training-data recall; both pass slopcheck
- Architecture (CI job wiring, REQUIRED_JOBS cascade, release workflow placement): HIGH — verified by direct reading of this repo's actual workflow/script files and a live GitHub API call against the real branch ruleset
- Architecture (exact Playwright clock-vs-htmx timing mechanics): MEDIUM — grounded in official Playwright docs and a direct grep confirming `setInterval` in the vendored htmx build, but not executed/verified end-to-end in this repo; flagged as Open Question 1
- Pitfalls: HIGH for CSRF/Origin behavior, `search_interval` granularity, and the two-template pill trigger split (all confirmed by direct code reading); MEDIUM for the Playwright secrets-in-traces guidance (based on recent, possibly-unreleased Playwright PRs)
- Security domain: MEDIUM — reasoned from existing ASVS-relevant code already in the repo (session/auth), not independently re-audited in this research pass

**Research date:** 2026-10-21
**Valid until:** ~30 days for the architecture/wiring findings (stable, repo-internal); ~14 days for the exact Playwright version pins and the trace-redaction feature-availability claim (fast-moving upstream project, October 2026 PRs still landing)
