---
phase: 85
slug: follow-on-ci-improvements-acceptance-usability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-10-27
validated: 2026-10-27
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

Filled in by Plan 85-19 after execution, one row per plan task, from each
plan's own SUMMARY.md (Task Commits / Verification Evidence sections). "File
Exists" means the artifact(s) named in the task's `<files>` are present on
disk; "Status" is the plan's own recorded verification result, not re-run by
85-19 except where 85-19's own Task 1 covers the full suite.

| Task ID | Requirement/Decision | Automated Command | File Exists | Status |
|---|---|---|---|---|
| 85-01-T1 | ACCEPT-03 (D-01), CIMAINT-05 (D-14) | `grep -c "Phase 85 D-01"`/`"Phase 85 D-14"` on REQUIREMENTS/ROADMAP | ✅ | ✅ complete (`4b8643a`) |
| 85-01-T2 | CIMAINT-03 (D-08..D-12) | `grep` checks on `docs/os-scan-policy.md` content | ✅ | ✅ complete (`a55f690`) |
| 85-01-T3 | CIMAINT-05 | `grep -c "Docker image only"`; no `.whl` references | ✅ | ✅ complete (`4e2a96a`; checkpoint:decision answered) |
| 85-02-T1 | ACCEPT-03, CIMAINT-04 | `node --test ci-job-consistency.test.cjs` (RED, expected fail) | ✅ | ✅ complete (`27f52dc`) |
| 85-02-T2 | ACCEPT-03, CIMAINT-04 | `node --test ci-job-consistency.test.cjs` (50/50) | ✅ | ✅ complete (`a8fc2c1`) |
| 85-03-T1 | ACCEPT-01, D-18 | `pytest tests/test_codex_review_run.py` | ✅ | ✅ complete (`3a8eff2`/`f17eae7`) |
| 85-03-T2 | ACCEPT-01, D-18 | `pytest tests/test_codex_review_run.py` | ✅ | ✅ complete (`f48c011`/`6ce9d49`) |
| 85-04-T1 | ACCEPT-01, D-18 | `pytest tests/test_codex_report_status.py -q -rf` (RED, 3 expected fails) | ✅ | ✅ complete (`07a2f17`) |
| 85-04-T2 | ACCEPT-01, D-18 | `pytest tests/test_codex_report_status.py -x -q` (127 passed) | ✅ | ✅ complete (`4a9a67a`) |
| 85-05-T1 | ACCEPT-01, ACCEPT-02, D-19 | `node --test review-acceptance.test.cjs` | ✅ | ✅ complete (`afa1de3`/`8df9eaf`) |
| 85-05-T2 | ACCEPT-02, D-19 | `node --test review-register.test.cjs review-acceptance.test.cjs` (48 pass) | ✅ | ✅ complete (`46354a5`/`e51d7e7`/`cf8f375`) |
| 85-05-T3 | ACCEPT-02, D-19 | `actionlint`; wiring grep on `review-acceptance.yml` | ✅ | ✅ complete (`19d4d50`) |
| 85-06-T1 | CIMAINT-02 (D-04..D-07) | `pytest tests/test_dependabot_config.py` (RED) | ✅ | ✅ complete (`7fea735`) |
| 85-06-T2 | CIMAINT-02 | `pytest tests/test_dependabot_config.py` (8 passed) | ✅ | ✅ complete (`71a7bb7`) |
| 85-07-T1 | CIMAINT-03 (D-08..D-12) | `node --test os-scan-gate.test.cjs` (RED) | ✅ | ✅ complete (`f5fd8b8`) |
| 85-07-T2 | CIMAINT-03 | `node --test os-scan-gate.test.cjs` (29 passed) | ✅ | ✅ complete (`fff523f`) |
| 85-08-T1 | CIMAINT-01 | `pytest tests/test_image_lock_consistency.py` (15 passed) | ✅ | ✅ complete (`cf0c6e1`/`d594f7e`) |
| 85-08-T2 | CIMAINT-01 | `docker build` + `image_lock_consistency.py` local positive/negative evidence | ✅ | ✅ complete (`88a0faf`; arm64 substitution, documented deviation) |
| 85-09-T1 | CIMAINT-06 | `uv export` before/after diff (byte-identical) | ✅ | ✅ complete (`d58f3a4`) |
| 85-09-T2 | CIMAINT-06 | `node --test coverage-provenance.test.cjs` (33 passed) | ✅ | ✅ complete (`e08d11e`/`babf3f5`) |
| 85-10-T1 | CIMAINT-05, CIMAINT-07 | `pytest tests/test_github_workflows.py` (RED) | ✅ | ✅ complete (`90705a7`) |
| 85-10-T2 | CIMAINT-05, CIMAINT-07 | `pytest` + `node --test artifact-promotion.test.cjs` + `actionlint` | ✅ | ✅ complete (`30cc961`) |
| 85-11-T1 | CIMAINT-01, CIMAINT-05, CIMAINT-06, D-13 | `pytest tests/test_ci_followon_wiring.py` (RED→GREEN) | ✅ | ✅ complete (`1308cd3`/`8a5f48a`) |
| 85-11-T2 | CIMAINT-01 | `pytest tests/test_ci_followon_wiring.py` + `actionlint` | ✅ | ✅ complete (`6f3a190`/`28a8de8`) |
| 85-12-T1 | CIMAINT-03, CIMAINT-04 | Trivy scan + `os-scan-gate.cjs --summary` (0 blocking) | ✅ | ✅ complete (`622a0b0`; arm64 substitution, documented deviation) |
| 85-12-T2 | CIMAINT-03 (checkpoint:decision, gate=blocking) | n/a — gate condition (blocking finding) did not occur | n/a | ⬜ not triggered (0 blocking findings; no decision needed, by design) |
| 85-13-T1 | ACCEPT-01, D-18 SA-01 | `pytest tests/test_codex_review_run.py` | ✅ | ✅ complete (`30ff5ff`/`e6eb5e3`/`dcf0b13`) |
| 85-13-T2 | ACCEPT-01, D-18 | `pytest` (288 passed across codex test files) | ✅ | ✅ complete (`e302937`/`80d2f7a`/`fc34da2`) |
| 85-14-T1 | ACCEPT-01, D-16 | `node --test codex-fallback.test.cjs` | ✅ | ✅ complete (`2b8f7c7`/`282ada4`) |
| 85-14-T2 | ACCEPT-01, D-20 | `node --test acceptance-readiness.test.cjs` (RED) | ✅ | ✅ complete (`a739d81`) |
| 85-14-T3 | ACCEPT-01, D-20 | `node --test acceptance-readiness.test.cjs` (104 passed total) | ✅ | ✅ complete (`171913d`) |
| 85-15-T1 | CIMAINT-03 | `pytest tests/test_ci_followon_wiring.py` (RED→GREEN) | ✅ | ✅ complete (`d1ac0ec`/`0f689c7`) |
| 85-15-T2 | CIMAINT-03, CIMAINT-04, D-11 | `pytest` + `node --test` + `actionlint` (zero findings) | ✅ | ✅ complete (`0c88dd9`/`f38de70`) |
| 85-16-T1 | ACCEPT-03, D-17 | `pytest tests/test_review_machinery_lists.py` | ✅ | ✅ complete (`d0b2b75`/`695e7de`) |
| 85-16-T2 | ACCEPT-03, D-17 | `pytest tests/test_codex_review_run.py tests/test_codex_review_contract.py` (191 passed) | ✅ | ✅ complete (`19f4f6d`/`7cdb651`) |
| 85-17-T1 | ACCEPT-01, D-16, D-07 | `pytest tests/test_review_checkpoint_record.py tests/test_acceptance_docs.py ...` | ✅ | ✅ complete (`b9446cb`/`faa4387`) |
| 85-17-T2 | ACCEPT-01, ACCEPT-02, CIMAINT-03, CIMAINT-06, D-19, D-20 | `pytest tests/test_acceptance_docs.py ...` (51 passed) | ✅ | ✅ complete (`2496e81`/`e72e971`) |
| 85-18-T1 | CIMAINT-01, CIMAINT-04 | `grep` checks on `docs/ci-negative-demonstrations.md` | ✅ | ✅ complete (`fbe6a3a`) |
| 85-18-T2 | CIMAINT-01, CIMAINT-04 | `git apply --check 85-DEMO-NEGATIVE.patch`; `actionlint` on demo workflow (exact expected failure) | ✅ | ✅ complete (`9680a24`) |
| 85-19-T1 | CIMAINT-01..07, ACCEPT-01..03 | `grep -c "PENDING"`/`"ACCEPT-03 cases"`/`"D-07 status"` on `85-REVIEW-EVIDENCE.md` | ✅ | ✅ complete (`7d08ae4`) |
| 85-19-T2 | D-15 | `grep -c "Resolved in Phase 85"`/`"Still open after Phase 85"` on `MAINTENANCE.md`; `grep -c "85-19"` on this file | ✅ | ✅ complete (this commit) |
| 85-19-T3 | — (classification, RISK-01, disclosures, hand-off) | `grep -c "## Hand-off after the last plan"`/`"## RISK-01 note"`; `git status --porcelain \| wc -l` | ⬜ | ⬜ pending — this plan's next task, not yet executed when this map was written |

*Status: ⬜ pending · ✅ complete/green · ❌ red · ⚠️ flaky*

### Requirement-level rollup

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| CIMAINT-01 | Image deps match `uv.lock`; mismatch fails | CI step + Node wiring test + Python checker | `pytest tests/test_image_lock_consistency.py` + `pytest tests/test_ci_followon_wiring.py` (docker-job diff step) | ✅ | ✅ green locally; P1/P6 pending real GitHub run |
| CIMAINT-02 | Dependabot config grouped/bounded, valid | config + live run | `pytest tests/test_dependabot_config.py` (8 tests); real Dependabot run after merge | ✅ | ✅ green locally; P4 pending (real run after merge) |
| CIMAINT-03 | Blocks Critical/High-with-fix; reports unfixed; fails closed; exception expiry ≤30d | unit + CI job | `node --test .github/scripts/os-scan-gate.test.cjs` (29 tests) + local baseline (0 blocking) | ✅ | ✅ green locally; P1 pending (real CI run) |
| CIMAINT-04 | actionlint always runs; bad workflow fails | CI job + fixture | `node --test .github/scripts/ci-job-consistency.test.cjs` (no-skip detector) + `actionlint` | ✅ | ✅ green locally; P1/P6 pending |
| CIMAINT-05 | `dist/*` release assets removed, no dangling refs; decision recorded | unit | `node --test .github/scripts/artifact-promotion.test.cjs .github/scripts/release-policy.test.cjs`; `pytest tests/test_github_workflows.py` | ✅ | ✅ green locally; P5 pending (next release CHANGELOG) |
| CIMAINT-06 | `coverage.xml` + provenance bound to SHA/run; failure exit preserved | CI step + fixture | `node --test .github/scripts/coverage-provenance.test.cjs` (33 tests) + exact-head local write/check | ✅ | ✅ green locally; P2 pending (CI artifact check) |
| CIMAINT-07 | `:main`/`:dev` publish without contents:write | Node test + real run | `node --test .github/scripts/release-policy.test.cjs .github/scripts/artifact-promotion.test.cjs` | ✅ | ✅ green locally; P3 pending (live publish after merge) |
| ACCEPT-01 | Readiness prerequisites visible | unit | `node --test .github/scripts/acceptance-readiness.test.cjs` (40 tests) | ✅ | ✅ green locally; readiness output pending a real PR |
| ACCEPT-02 | PR+SHA-keyed register; concurrent isolation | unit (concurrent fixtures) | `node --test .github/scripts/review-register.test.cjs .github/scripts/review-acceptance.test.cjs` | ✅ | ✅ green locally; live schema-1→2 migration pending (hand-off step 12) |
| ACCEPT-03 | No skip condition bypasses required jobs (4 fixture classes) | unit | `node --test .github/scripts/ci-job-consistency.test.cjs` | ✅ | ✅ green locally (3/4 cases by test); mixed case pending the real phase PR (D-02) |
| D-13 | planchk-router tests in CI | unit + wiring | `node --test .claude/plugins/planchk-router/test/planchk-router.test.mjs`; wired into `ci.yml` | ✅ | ✅ green locally and wired |
| D-16..D-18 | Codex fallback, drift guard, runner hardening | unit | `uv run pytest tests/test_codex_review_run.py tests/test_codex_report_status.py tests/test_review_machinery_lists.py -x -q` | ✅ | ✅ green locally |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All five now exist, confirmed on disk by Plan 85-19:

- [x] `.github/scripts/os-scan-gate.cjs` + `.test.cjs` — CIMAINT-03 classification + exception validation (Plan 85-07)
- [x] ACCEPT-03 four-case fixture diffs — ordinary-docs, sensitive-docs, mixed, misclassified (Plan 85-02, `.github/scripts/ci-job-consistency.test.cjs`)
- [x] Concurrent-update fixtures — ACCEPT-02/D-19 (Plan 85-05, `.github/scripts/review-register.test.cjs`; the plan's original wording named `review-acceptance.test.cjs`, but the fixtures that exercise concurrent writers live in `review-register.test.cjs`, which `review-acceptance.cjs` reads through)
- [x] Per-D-18-subitem regression tests in `tests/test_codex_review_run.py` / `tests/test_codex_report_status.py` (Plans 85-03, 85-04, 85-13)
- [x] Review-list drift-guard test (D-17) (Plan 85-16, `tests/test_review_machinery_lists.py`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Grouped Dependabot PRs actually open | CIMAINT-02 | Only GitHub runs Dependabot | After merge, observe first scheduled/manually-triggered run; record PRs |
| `:main`/`:dev` publish under narrowed permissions | CIMAINT-07 | GitHub-enforced permission claim needs a real run | Record the main-push release run after merge (run ID, job permissions, success) |
| Deliberately mismatched lockfile / bad workflow fail the gate on GitHub | CIMAINT-01, CIMAINT-04 | Gate-enforcement claim (Phase 82 D-07); each broken push needs owner go-ahead (D-10) | One negative checkpoint push on the phase PR after the end-of-phase push, with the owner's go-ahead at push time, then a restore push and fresh final-head review (85-18 prepares, 85-19 hand-off performs); record per Phase 82 D-06/D-34 |
| vibe-check test-sufficiency discovers coverage.xml | CIMAINT-06 | Plugin consumption is a local review run | Run the selected vibe-check on the phase head with the matching CI coverage artifact; record discovery |

### 85-19 hand-off items (P1-P6, from `85-REVIEW-EVIDENCE.md`)

| Item | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| P1 — phase-PR CI run, positive cases + time budget | CIMAINT-01, CIMAINT-03, CIMAINT-04, CIMAINT-06, ACCEPT-03 | Needs a real GitHub Actions run on the actual phase PR | Record run ID/URL/attempt, every required job's conclusion, and added PR wall-clock vs. the ~5-minute target (Phase 82 D-14) |
| P2 — CI coverage artifact check per reviewed/accepted head | CIMAINT-06 | Needs a real CI-produced `coverage.xml`/`coverage-provenance.json` artifact | `gh run download` + `coverage-provenance.cjs check --expected-head <head> --expected-run-id <run>`; record whether vibe-check's test-sufficiency lane discovered it |
| P3 — first main-push Release run after merge | CIMAINT-07 | GitHub-enforced permission claim needs a real run | Record run ID/URL, `release` job's actual permissions, `:main`/`:dev` publish success and digests |
| P4 — first Dependabot run after merge | CIMAINT-02 | Only GitHub/Dependabot can run this | Observe the repository's Dependabot view/API after merge; record grouped PRs or "no updates available" per ecosystem |
| P5 — next release's CHANGELOG notes no distributions | CIMAINT-05 (D-14) | Depends on the next authorized release | Confirm the CHANGELOG entry states wheel/sdist are no longer attached |
| P6 — CIMAINT-01/CIMAINT-04 negative demonstration on the phase PR | CIMAINT-01, CIMAINT-04 | Gate-enforcement claim (Phase 82 D-07); needs owner go-ahead (D-10) at push time | `85-DEMO-NEGATIVE.patch` applied to the phase PR per `docs/ci-negative-demonstrations.md` Recipes 4/5, with a restore push and fresh review on the restored head; record per Phase 82 D-06/D-34 (85-18 prepared, 85-19 hand-off performs) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
