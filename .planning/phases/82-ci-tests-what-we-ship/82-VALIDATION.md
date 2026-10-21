---
phase: 82
slug: ci-tests-what-we-ship
status: draft
nyquist_compliant: false
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

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| CISHIP-01 | Health/setup/login/static/writable-config/persistence via real entrypoint | smoke (CI job script) | `image-smoke` CI job | ❌ W0 | ⬜ pending |
| CISHIP-01 | Missing static asset fails the check | smoke negative (permanent) | `image-smoke` CI job step | ❌ W0 | ⬜ pending |
| CISHIP-01 | Broken entrypoint fails the check | recorded demonstration | documented recipe + isolated-branch CI run | ❌ W0 | ⬜ pending |
| CISHIP-02 | Pill polls on bounded schedule, updates between polls | browser | `uv run pytest tests/e2e/test_pill_polling.py --browser chromium` | ❌ W0 | ⬜ pending |
| CISHIP-02 | Setup/login/logout browser flows | browser | `uv run pytest tests/e2e/test_setup_login_logout.py --browser chromium` | ❌ W0 | ⬜ pending |
| CISHIP-02 | Reintroduced polling bug fails suite; no secrets in artifacts | recorded demonstration | documented recipe + isolated-branch CI run | ❌ W0 | ⬜ pending |
| CISHIP-03 | Tag/version mismatch rejected, match accepted | unit | `node --test .github/scripts/release-policy.test.cjs` | ✅ (extend) | ⬜ pending |
| CISHIP-03 | Rejection before login/push/release-create | static wiring | `node --test .github/scripts/artifact-promotion.test.cjs` | ✅ (extend) | ⬜ pending |
| CISHIP-04 | New jobs in `ci-ready`; missing/skipped job fails gate | static consistency | `node --test .github/scripts/ci-job-consistency.test.cjs` | ✅ | ⬜ pending |

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

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Broken entrypoint makes image-smoke fail | CISHIP-01 | Requires a deliberately broken commit; owner go-ahead needed before each push (D-10) | Follow the documented recipe on an isolated branch/draft PR; record the failing run URL |
| Reintroduced pill polling bug makes browser suite fail | CISHIP-02 | Same — deliberately broken commit | Follow recipe; record failing run URL; confirm uploaded artifacts contain no secrets |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
