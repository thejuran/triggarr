---
phase: 82
slug: ci-tests-what-we-ship
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-10-21
---

# Phase 82 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=9.0.3 (existing) + pytest-playwright (new, browser suite); Node.js `node --test` (existing, release-policy/CI-consistency scripts) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (existing); `tests/e2e/` must stay excluded from the default unit run |
| **Quick run command** | `node --test .github/scripts/*.test.cjs && uv run --no-sync pytest tests/ -q -x` |
| **Full suite command** | Quick run + `uv run --no-sync pytest tests/e2e -q --browser chromium --tracing=retain-on-failure` against a live container (CI `browser-e2e` job) + CI `image-smoke` job |
| **Estimated runtime** | ~60 seconds local quick run; image-smoke/browser-e2e only meaningful in CI |

---

## Sampling Rate

- **After every task commit:** Run `node --test .github/scripts/*.test.cjs` (CISHIP-03/04 work) and `uv run ruff check triggarr/ tests/` (Python work)
- **After every plan wave:** Run `uv run --no-sync pytest tests/ -q` plus a real CI run of `image-smoke` / `browser-e2e` on the phase PR
- **Before `/bm:verify-work`:** Full suite must be green, plus recorded negative demonstrations (broken entrypoint, pill-bug reintroduction) on an isolated branch/draft PR with owner go-ahead
- **Max feedback latency:** ~60 seconds locally; one CI run per wave

---

## Per-Task Verification Map

| Task ID | Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|---------|--------|----------|-----------|-------------------|-------------|--------|
| 82-01-T1, 82-01-T2 | CISHIP-03 | Tag/version mismatch rejected, match accepted | unit (TDD) | `node --test .github/scripts/release-policy.test.cjs` | ✅ (extend) | ⬜ pending |
| 82-02-T1, 82-02-T2 | CISHIP-01 | Stub *arr service + reason-coded HTTP checks | unit (TDD) | `uv run --no-sync pytest tests/test_ci_harness.py -q` | ❌ W0 | ⬜ pending |
| 82-03-T1 | CISHIP-03 | Release identity rehearsal via the release job's own entry points: matching accepted; mismatched/malformed/missing rejected for their specific reasons (D-31a) | unit + script | `node --test .github/scripts/release-identity-rehearsal.test.cjs` | ❌ W0 | ⬜ pending |
| 82-03-T2, 82-03-T3 | CISHIP-03 | Rejection blocks login/push/release-create; any bypass fails the test (D-31b) | static wiring + bypass negatives | `node --test .github/scripts/*.test.cjs && uv run --no-sync pytest tests/test_github_workflows.py -q` | ✅ (extend) | ⬜ pending |
| 82-04-T1 | CISHIP-01 | Container argv builders and lifecycle helpers | unit | `uv run --no-sync pytest tests/test_ci_harness_stack.py -q` | ❌ W0 | ⬜ pending |
| 82-04-T2 | CISHIP-01 | Health/setup/login/static/writable-config/persistence via real entrypoint; missing static asset fails (permanent negative) | smoke (Docker) | `uv run --no-sync python -m tests.harness.image_smoke run --image triggarr:local --expected-image-id-file ...` | ❌ W0 | ⬜ pending |
| 82-05-T1 | CISHIP-02 | Playwright deps installed; tests/e2e excluded from default run | config | `uv lock --check && uv run --no-sync pytest tests/ -q -x` | ✅ (extend) | ⬜ pending |
| 82-05-T2 | CISHIP-02 | No secrets in uploaded artifacts | unit | `uv run --no-sync pytest tests/test_artifact_scan.py -q` | ❌ W0 | ⬜ pending |
| 82-05-T3 | CISHIP-02 | Setup/login/logout browser flows | browser | `uv run --no-sync pytest tests/e2e -q --browser chromium` (live container) | ❌ W0 | ⬜ pending |
| 82-06-T1 | CISHIP-02 | Pill polls on bounded schedule, updates between polls | browser | `uv run --no-sync pytest tests/e2e/test_pill_polling.py --browser chromium` | ❌ W0 | ⬜ pending |
| 82-06-T2 | CISHIP-02 | Reintroduced loop / disabled polling fail the suite (local evidence) | browser (local sensitivity) | `uv run --no-sync pytest tests/e2e/test_pill_polling.py --browser chromium` | ❌ W0 | ⬜ pending |
| 82-07-T1 | CISHIP-01, CISHIP-02 | image-smoke and browser-e2e CI jobs | CI wiring | `node --test .github/scripts/*.test.cjs` + YAML job presence check | ✅ (extend) | ⬜ pending |
| 82-07-T2, 82-07-T3 | CISHIP-04 | New jobs in `ci-ready`; missing/skipped job fails gate; all actions SHA-pinned | static consistency | `node --test .github/scripts/ci-job-consistency.test.cjs && uv run --no-sync pytest tests/test_ci_gate.py tests/test_github_workflows.py -q` | ✅ / ❌ W0 | ⬜ pending |
| 82-08-T1..T3 | CISHIP-01..04 | Recipes documented; first real CI run and time budget recorded | real CI run + owner vibe-check | phase PR CI run (`image-smoke`, `browser-e2e`, `ci-ready`) | n/a | ⬜ pending |
| 82-09-T1..T3 | CISHIP-01, CISHIP-02 | Broken entrypoint / pill bug fail CI on isolated draft PRs (owner go-ahead, D-10) | recorded demonstration | isolated-branch CI runs per `docs/ci-negative-demonstrations.md` | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/e2e/conftest.py` — base_url fixture for running container, stub-*arr control fixture
- [ ] `tests/e2e/test_pill_polling.py` — CISHIP-02 (pill)
- [ ] `tests/e2e/test_setup_login_logout.py` — CISHIP-02 (setup/login/logout)
- [ ] Minimal stub *arr HTTP service (location chosen by planner)
- [ ] `image-smoke` CI job script — container lifecycle, health/setup/login/static/config/restart, missing-asset negative
- [ ] `release-policy.cjs` tag/version validation functions + tests
- [ ] `artifact-promotion.test.cjs` ordering assertion
- [ ] Framework install: playwright + pytest-playwright in dev extras, `playwright install --with-deps chromium` CI step

---

## Verification Expectations (D-31, owner decision 2026-10-21)

- CISHIP-03 evidence is bounded: permanent negatives (four rehearsal cases on the exact audited image, structural bypass tests) pass inside green CI runs. A deliberately red tag-triggered run is not required.
- Evidence records commit SHA, image ID and image.tar sha256, run URL, run ID and attempt, and expected vs observed reason per negative case.
- Phase verification records this sentence verbatim: "Version validation and release wiring verified; actual tag-triggered publication remains unverified until the next authorized release."

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Broken entrypoint makes image-smoke fail | CISHIP-01 | Requires a deliberately broken commit; owner go-ahead needed before each push (D-10) | Follow the documented recipe on an isolated branch/draft PR; record the failing run URL |
| Reintroduced pill polling bug makes browser suite fail | CISHIP-02 | Same — deliberately broken commit | Follow recipe; record failing run URL; confirm uploaded artifacts contain no secrets |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [ ] Feedback latency < 60s — not met by design for Docker/E2E tasks (82-04-T2, 82-05-T3, 82-06-T1/T2, 82-08/09 CI runs): image builds, container lifecycles and real CI runs exceed 60s by nature. Node/unit task verifies stay under 60s.
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** plan-checker confirmed 8a-8d (2026-10-21); Wave 0 files not yet created (`wave_0_complete: false`)
