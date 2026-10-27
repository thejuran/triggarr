---
phase: 85
slug: follow-on-ci-improvements-acceptance-usability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-10-27
---

# Phase 85 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`uv run pytest`) + Node stdlib `node:test` (`node --test`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (asyncio_mode=auto); Node tests run by explicit path/glob |
| **Quick run command** | `uv run pytest tests/test_<module>.py -x -q` / `node --test .github/scripts/<file>.test.cjs` |
| **Full suite command** | `uv run pytest tests/ -x -q && node --test .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs && uv run ruff check triggarr/ tests/` |
| **Estimated runtime** | ~180 seconds locally (full pytest suite dominates) |

---

## Sampling Rate

- **After every task commit:** Run the quick command for the file(s) touched
- **After every plan wave:** Run the full suite command
- **Before `/bm:verify-work`:** Full suite must be green, plus the four ACCEPT-03 fixture cases and CIMAINT-01's lockfile-mismatch negative case
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

Filled in by the planner per task (each task's `<automated>` verify). Requirement-level map (from 85-RESEARCH.md § Validation Architecture):

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| CIMAINT-01 | Image deps match `uv.lock`; mismatch fails | CI step + Node wiring test | `node --test .github/scripts/ci-job-consistency.test.cjs` + docker-job diff step | ❌ W0 | ⬜ pending |
| CIMAINT-02 | Dependabot config grouped/bounded, valid | config + live run | config assertion test; real Dependabot run after merge | ❌ W0 | ⬜ pending |
| CIMAINT-03 | Blocks Critical/High-with-fix; reports unfixed; fails closed; exception expiry ≤30d | unit + CI job | `node --test .github/scripts/os-scan-gate.test.cjs` | ❌ W0 | ⬜ pending |
| CIMAINT-04 | actionlint always runs; bad workflow fails | CI job + fixture | `node --test .github/scripts/ci-job-consistency.test.cjs` + fixture | ❌ W0 | ⬜ pending |
| CIMAINT-05 | `dist/*` release assets removed, no dangling refs; decision recorded | unit | `node --test .github/scripts/artifact-promotion.test.cjs .github/scripts/release-policy.test.cjs` | ✅ | ⬜ pending |
| CIMAINT-06 | `coverage.xml` + provenance bound to SHA/run; failure exit preserved | CI step + fixture | test-job step + provenance validator test | ❌ W0 | ⬜ pending |
| CIMAINT-07 | `:main`/`:dev` publish without contents:write | Node test + real run | `node --test .github/scripts/release-policy.test.cjs` + live publish | ✅ | ⬜ pending |
| ACCEPT-01 | Readiness prerequisites visible | unit | `node --test .github/scripts/review-acceptance.test.cjs` | ✅ | ⬜ pending |
| ACCEPT-02 | PR+SHA-keyed register; concurrent isolation | unit (concurrent fixtures) | `node --test .github/scripts/review-acceptance.test.cjs` | ✅ | ⬜ pending |
| ACCEPT-03 | No skip condition bypasses required jobs (4 fixture classes) | unit | `node --test .github/scripts/ci-job-consistency.test.cjs` | ✅ | ⬜ pending |
| D-13 | planchk-router tests in CI | unit + wiring | `node --test .claude/plugins/planchk-router/test/planchk-router.test.mjs` | ✅ | ⬜ pending |
| D-16..D-18 | Codex fallback, drift guard, runner hardening | unit | `uv run pytest tests/test_codex_review_run.py tests/test_codex_report_status.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `.github/scripts/os-scan-gate.cjs` + `.test.cjs` — CIMAINT-03 classification + exception validation
- [ ] ACCEPT-03 four-case fixture diffs — ordinary-docs, sensitive-docs, mixed, misclassified
- [ ] Concurrent-update fixtures in `review-acceptance.test.cjs` — ACCEPT-02/D-19
- [ ] Per-D-18-subitem regression tests in `tests/test_codex_review_run.py` / `tests/test_codex_report_status.py`
- [ ] Review-list drift-guard test (D-17)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Grouped Dependabot PRs actually open | CIMAINT-02 | Only GitHub runs Dependabot | After merge, observe first scheduled/manually-triggered run; record PRs |
| `:main`/`:dev` publish under narrowed permissions | CIMAINT-07 | GitHub-enforced permission claim needs a real run | Record the main-push release run after merge (run ID, job permissions, success) |
| Deliberately mismatched lockfile / bad workflow fail the gate on GitHub | CIMAINT-01, CIMAINT-04 | Gate-enforcement claim (Phase 82 D-07); each broken push needs owner go-ahead (D-10) | Isolated draft branch push after owner go-ahead; record per Phase 82 D-06 |
| vibe-check test-sufficiency discovers coverage.xml | CIMAINT-06 | Plugin consumption is a local review run | Run the selected vibe-check on the phase head with the matching CI coverage artifact; record discovery |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
