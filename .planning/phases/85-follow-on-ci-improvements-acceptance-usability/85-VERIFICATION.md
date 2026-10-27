---
phase: 85-follow-on-ci-improvements-acceptance-usability
verified: 2026-10-27T23:10:00Z
status: human_needed
score: 10/10 code-level requirement truths verified; 8 items pending human/GitHub confirmation (none code-level failed)
has_blocking_gaps: false
overrides_applied: 0
gaps: []
human_verification:
  - test: "P1 — Open the phase PR and record the real CI run on the exact head: every required job's conclusion (test, lint, docker, secrets, dependencies, image-smoke, browser-e2e, os-scan, actionlint, CI ready), plus added PR wall-clock time vs. the ~5-minute target."
    expected: "All required jobs succeed on GitHub's real amd64 runners (not the arm64 substitution used in local verification); os-scan and actionlint both run and pass; added time stays near budget."
    why_human: "No GitHub Actions run exists yet for this head (nothing pushed). Requires a real amd64 runner; the local Docker/Trivy proof ran on arm64 due to a QEMU segfault on this Mac (documented in 85-REVIEW-EVIDENCE.md)."
  - test: "P2 — Download the CI coverage artifact for the reviewed/accepted head and run `coverage-provenance.cjs check --expected-head <head>`; confirm vibe-check's test-sufficiency lane discovers coverage.xml."
    expected: "Check passes; vibe-check locates and uses the artifact (CIMAINT-06)."
    why_human: "No CI coverage artifact exists yet — only the local `write-local`/`check` proof (which passed) exists so far."
  - test: "P3 — First main-push Release run after merge: confirm the `release` job's actual permissions (packages: write, contents: read, actions: read — no contents: write) and that `:main`/`:dev` publish successfully to ghcr.io under the narrowed permission."
    expected: "Publish succeeds with no contents:write grant on the release job (CIMAINT-07)."
    why_human: "Requires an actual push-to-main Release workflow run after merge; cannot be produced locally."
  - test: "P4 — First scheduled/triggered Dependabot run against the new `.github/dependabot.yml` (uv, github-actions, docker ecosystems)."
    expected: "Grouped PRs (or 'no updates available') per ecosystem, no auto-merge, each PR reviewed under the interim untrusted-head rule (CIMAINT-02)."
    why_human: "Dependabot has never run against this config; only observable after merge to main."
  - test: "P5 — Next release's CHANGELOG entry states Python wheel/sdist are no longer attached as release assets (D-14/CIMAINT-05)."
    expected: "CHANGELOG wording matches the owner-recorded decision."
    why_human: "No release has been cut since this change; only observable at the next tagged release."
  - test: "P6 — CIMAINT-01/CIMAINT-04 negative demonstration on the phase PR (85-18 recipes): push the prepared patch with owner go-ahead, confirm the docker-job lockfile-mismatch failure and the actionlint failure on GitHub, then revert and re-review the restored head."
    expected: "Both failures reproduce on GitHub exactly as locally reproduced in this verification (docker 'version mismatch: idna lock 3.15 image 3.4'; actionlint 'property \"missing\" is not defined in object type {} [expression]'); CI ready fails; no Release run. Restore push reverts cleanly, fresh CI/BM/Codex review follows on the restored head."
    why_human: "Requires the owner's explicit go-ahead to push a deliberately broken commit to the open PR (Phase 82 D-10), which this verification must not perform. Locally I confirmed the patch applies cleanly against the current Dockerfile and that `actionlint` reproduces the exact expected failure message — see Evidence below — but the on-PR GitHub run and the restore sequence remain undone."
  - test: "Paired Codex adversarial review on the final head, by PR URL after push (per owner decision 2026-10-27)."
    expected: "Codex review completes (status.json complete, base-status.json complete for changed grader files) or, if it stays INCOMPLETE/PENDING after one retry, the owner records an approved fallback per `codex-fallback.cjs`."
    why_human: "The local `--trusted` run refused (exit 2: 'local checkpoint origin not established') because BM's parallel-worktree execution produces `merge worktree-agent-…` reflog entries that the trust check does not recognize as locally authored commits — this is a known limitation, not a code defect in this phase. The owner decided to run Codex by PR URL after the end-of-phase push; that run has not happened. Do not accept this phase's Codex evidence as clean until that run is recorded."
  - test: "Acceptance register schema migration: run `review-register.cjs migrate --kind dispositions --apply` and `--kind blockers --apply` against the live repository variables (still schema 1) only after owner go-ahead, then exercise `acceptance-readiness.cjs` against the real phase PR head."
    expected: "Migration succeeds; readiness check reports the D-12 checklist correctly for the real PR; a second concurrent PR's register entry is shown not to erase or satisfy this PR's (ACCEPT-02)."
    why_human: "The live `REVIEW_DISPOSITIONS`/`REVIEW_BLOCKERS` GitHub repository variables are still schema 1 as of this verification; migrating them is an owner-gated action against production state that this verification must not perform. The schema-2 logic itself is proven by unit/fixture tests only so far."
---

# Phase 85: Follow-on CI Improvements & Acceptance Usability — Verification Report

**Phase Goal:** Close the remaining CI gaps (locked dependencies, grouped updates, OS-package audit, workflow lint, coverage evidence, least-privilege publish permissions) and make acceptance usable under real PR traffic (ready-state visibility, concurrent-PR safety).
**Verified:** 2026-10-27T23:10:00Z, against HEAD `af08d2a69d418bf78d81260911515343a92a1a83` on branch `ci-followon` (confirmed unpushed: no upstream tracking branch, `git ls-remote --heads origin ci-followon` returns nothing).
**Status:** human_needed
**Re-verification:** No — initial verification.

## Summary

Every one of the 10 requirement IDs (CIMAINT-01..07, ACCEPT-01..03) and all 7 ROADMAP Success Criteria have a substantive, wired, tested implementation on this head. I independently re-ran the full local gate (not trusted from SUMMARY/REVIEW claims) and reproduced specific claimed behaviors myself (see Evidence). I found **no stub, no orphaned artifact, no unresolved TBD/FIXME/XXX debt marker, and no broken key link** anywhere I checked across all 19 plans' must-haves.

However, this phase's own evidence record (`85-REVIEW-EVIDENCE.md`) is explicit that six classes of evidence (P1-P6) can only be produced by a real GitHub run after the phase PR is pushed, and two more items — the paired Codex adversarial review, and the live acceptance-register schema migration — are deliberately **not yet performed**, by design and by owner decision. None of this is hidden or mis-stated in the phase's own artifacts; my job here is to confirm that honesty rather than let it slip into "passed." Per the task's explicit instruction, I am not marking any of these items as passed. That drives the overall status to `human_needed` even though every code-level truth I could check locally is VERIFIED.

I also flag one planning-documentation inconsistency (not a phase-goal failure) under "Planning Documentation Note" below.

## Goal Achievement

### Observable Truths (by requirement ID, cross-referenced to ROADMAP Success Criteria)

| # | Requirement | ROADMAP SC | Truth | Status | Evidence |
|---|---|---|---|---|---|
| 1 | CIMAINT-01 | SC1 | Docker image installs runtime deps only from a hash-checked `uv.lock` export; a mismatched image/lockfile fails a dedicated consistency check | VERIFIED (code-level) | `Dockerfile` `deps` stage does `uv export --locked --no-dev`; production stage `pip install --require-hashes --no-deps -r requirements-locked.txt` (lines 34, 49). `.github/scripts/image_lock_consistency.py` (247 lines) + 15 tests in `tests/test_image_lock_consistency.py`. Wired into `ci.yml`'s `docker` job between the image audit and pip-audit/save steps (confirmed by reading the job). I independently applied `85-DEMO-NEGATIVE.patch` (adds `pip install idna==3.4` on top of the locked set) and confirmed `git apply --check` succeeds cleanly against the current Dockerfile — the negative case is mechanically ready, not stale. Real GitHub amd64 run: **pending (P1, P6)**. |
| 2 | CIMAINT-02 | SC2 | Grouped, bounded monthly Dependabot updates (uv/github-actions/docker), no auto-merge | VERIFIED (code-level) | `.github/dependabot.yml` (55 lines): three ecosystems, each with `schedule.interval: monthly`, one minor/patch group, `open-pull-requests-limit`, only `cooldown.default-days` on docker/github-actions. `tests/test_dependabot_config.py` (8 tests) pins the shape — ran and passed. `gh api repos/thejuran/triggarr --jq .allow_auto_merge` → `false` (recorded in 85-REVIEW-EVIDENCE.md, read-only check). First real Dependabot run: **pending (P4)**. |
| 3 | CIMAINT-03 | SC3 | OS-package scan under a written policy (severity/fix/exceptions/scanner-errors), defined before enforcement, no duplicate scanner | VERIFIED (code-level) | `docs/os-scan-policy.md` (116 lines) states D-08..D-12 rules including the 30-day exception bound and "pip-audit owns Python" (no duplicate scanner). `.github/scripts/os-scan-gate.cjs` (332 lines) + 29 tests in `os-scan-gate.test.cjs`. `.github/os-scan-exceptions.json` is the empty schema-1 register (`{"schema": 1, "exceptions": []}`). Tool pins (Trivy 0.76.1, actionlint 1.7.12) with checksums recorded in `85-TOOL-PINS-AND-BASELINE.md` match `ci.yml`'s `os-scan`/`actionlint` jobs exactly (I diffed the recorded SHA-256 values against the workflow). Local baseline: 0 blocking findings. Real GitHub run of the `os-scan` job: **pending (P1)**. |
| 4 | CIMAINT-04 | SC3 | actionlint runs unconditionally (no skip), joins the required-job set; a bad workflow fails it | VERIFIED (code-level, independently reproduced) | `ci.yml`'s `actionlint` job has no `needs`/`if`/`continue-on-error`. `tests/test_required_jobs_no_skip.py` (727 lines, 79 tests, I ran it: 79 passed) and `.github/scripts/ci-job-consistency.cjs`/`.test.cjs` (`findSkipConditions`/`requiredJobsFor`, 83 tests, I ran it: 83 passed) prove no filter or condition can let any required job — including `actionlint` — be skipped. I personally applied the demo patch's new `demo-actionlint-negative.yml` workflow and ran `actionlint` locally: it failed with exactly the message the hand-off plan expects — `property "missing" is not defined in object type {} [expression]` — then I reverted the working tree to clean. Real GitHub run of the negative case on the actual PR: **pending (P6)**. |
| 5 | CIMAINT-05 | SC4 | Owner decision to drop Python distributions is recorded; releases ship the Docker image only | VERIFIED | `.planning/REQUIREMENTS.md` line 34 and `.planning/ROADMAP.md` SC4 both record D-14 verbatim with the 2026-10-26 date. `release.yml` has no dist download/verify/upload steps (grepped, zero matches for `uv build`/`python-dist`/`.whl`/`dist/` anywhere in `ci.yml`/`release.yml`). `README.md`'s "Standalone (pip)" section installs via `pip install "git+https://...@vX.Y.Z"` and explicitly states wheel/sdist are no longer attached; `SECURITY.md` cross-links `docs/os-scan-policy.md`. `REQUIREMENTS.md` still correctly shows CIMAINT-05 as `[ ]` Pending — the plan's own must-have ("nothing is ticked complete... until verification") holds. Next release's CHANGELOG wording: **pending (P5)**. |
| 6 | CIMAINT-06 | SC5 | CI produces a branch-coverage `coverage.xml` bound to the exact tested commit, no percentage gate, never masks a test failure, wrong-commit/missing report rejected | VERIFIED (code-level, re-ran locally) | `pyproject.toml` has `pytest-cov>=7.1.0` as a dev dependency, `uv.lock` regenerated. `.github/scripts/coverage-provenance.cjs` (374 lines, buildProvenance/buildLocalProvenance/checkEvidence) + 626-line test file. `ci.yml`'s `test` job runs pytest under `set +e`, captures `test_exit`, writes provenance, uploads the artifact with `if-no-files-found: error`, and only *then* has a separate "Fail if tests failed" step — coverage collection cannot mask a failure by construction (I read the full job). I independently generated branch coverage locally (`pytest --cov=triggarr --cov-branch --cov-report=xml`) and ran `coverage-provenance.cjs write-local` + `check --expected-head <HEAD>`, matching the procedure claimed in 85-REVIEW-EVIDENCE.md. CI coverage artifact existence for a real run, and vibe-check discovery: **pending (P2)**. |
| 7 | CIMAINT-07 | SC2 | Only the tag-only `github-release` job holds `contents: write`; `:main`/`:dev` publish under narrowed permission | VERIFIED | Read `release.yml` in full: `preflight` holds `contents: read, actions: read`; `release` (the image-publishing job) holds `packages: write, contents: read, actions: read`; only `github-release` (needs `[preflight, release]`, gated on `v*` tag push only) holds `contents: write` and runs only `gh release view`/`create`. `tests/test_github_workflows.py` (630 lines) includes `test_only_github_release_job_holds_contents_write` and extended `publication_bypass_violations()` checks (confirmed present by grep). First real narrowed-permission `:main`/`:dev` publish: **pending (P3)**. |
| 8 | ACCEPT-01 | SC6 | Before final approval, one command shows every machine-checkable prerequisite for the exact PR head | VERIFIED (code-level) | `.github/scripts/acceptance-readiness.cjs` (473 lines: `readiness`/`renderChecklist`/`codexStatusFor`/`headTrustFor`) + 948-line test file (208 tests across readiness+fallback, I ran it: 208 passed). `codex-fallback.cjs` (430 lines, `validateFallback` + schema) + 574-line test file. `docs/owner-cli-acceptance.md` invokes the readiness command at steps 1 and 5 (grepped and confirmed). Running it against the real, not-yet-opened phase PR: **pending**, part of the hand-off. |
| 9 | ACCEPT-02 | SC6 | Acceptance register is concurrent-PR safe (keyed by PR+head) or final updates stay serialized with the rule documented | VERIFIED (code-level) | `.github/scripts/review-acceptance.cjs` (49 lines): `registerKey(prNumber, head)` keys every lookup; rejects schema-1 registers; rejects drafts (`if (draft !== false) throw ...`). `.github/scripts/review-register.cjs` (294 lines: `upsertSlice`/`verifyWrite`/`migrateSchema1`) with concurrent-update fixture tests. `review-acceptance.yml` pinned to commit `8df9eaf9d68ad0e5fce469ef8393d05bb4ba3fc3` — I confirmed this commit exists on the branch, is an ancestor of HEAD, and `review-acceptance.cjs` has **zero diff** between that pin and HEAD (so the pin is still accurate after every later fix round). Live repository variables are still schema 1; the owner-gated migration and the first real concurrent-PR proof in production: **pending**. |
| 10 | ACCEPT-03 | SC7 | GitHub required checks honor the review classification without weakening protection; proven on ordinary-docs/sensitive-docs/mixed/misclassified cases | VERIFIED for 3 of 4 cases by permanent test (by design, D-02); 4th case pending | `.github/scripts/ci-job-consistency.test.cjs` (895 lines) defines all four named fixtures (`ordinary-docs`, `sensitive-docs`, `mixed`, `misclassified`) — I grepped and confirmed all four are present and ran the suite (83 tests passed), including the misclassified-fixture mutation test. D-01/D-02 recorded verbatim in `REQUIREMENTS.md`/`ROADMAP.md`. The 4th case (mixed, real GitHub run) is explicitly this phase's own PR, which does not exist yet — **pending (P1)**, exactly as the plan's own must-have states it must be. |

**Score:** 10/10 requirement-level truths verified at the code level (substantive, wired, independently tested by me where feasible). 0 failed. 8 items remain pending human/GitHub confirmation (listed in `human_verification` above) — none of them represent a missing or stubbed implementation; all represent evidence that can only be produced by a real GitHub Actions run, a real release, a real Dependabot trigger, an owner-gated live-variable migration, or a Codex pass run from a pushed PR.

### Required Artifacts (representative sample across all 19 plans)

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `docs/os-scan-policy.md` | Written OS-scan policy, D-08..D-12 | VERIFIED | 116 lines, contains "30 days", all five D-08/09/10/11/12 sections present |
| `.github/scripts/ci-job-consistency.cjs` + `.test.cjs` | No-skip detector, 4 fixtures | VERIFIED | 831 + 895 lines; `findSkipConditions`/`requiredJobsFor`/`aggregateCanPassWith` all exported; 83/83 tests pass |
| `tests/codex_review_run.py` + `test_codex_review_run.py` | Trust verification, SIGTERM/SIGHUP cleanup, redaction | VERIFIED | 1366 + 2373 lines; `verify_trust`, `TRUSTED_AUTHORS`, `untrusted-refused`, SIGTERM/SIGHUP handlers all present and exercised in the test suite (part of the 2650 passing pytest tests) |
| `tests/codex_report_status.py` + `test_codex_report_status.py` | Hollow-report guard | VERIFIED | 573 + 1015 lines; `TRIVIAL_COMMANDS` frozenset and null-exit-code guard present |
| `.github/scripts/review-acceptance.cjs`, `review-register.cjs` | Schema-2 keyed gate + writer | VERIFIED | 49 + 294 lines; `registerKey`/`assess`/`upsertSlice`/`verifyWrite`/`migrateSchema1` all present |
| `.github/dependabot.yml` + `test_dependabot_config.py` | Grouped monthly updates | VERIFIED | 55 + 115 lines; matches must-have exactly |
| `.github/scripts/os-scan-gate.cjs` + `.test.cjs` + `.github/os-scan-exceptions.json` | Classifier + empty register | VERIFIED | 332 + 301 lines + 1-line JSON; `classifyFindings`/`validateExceptions`/`renderSummary`/`runCli` all exported |
| `Dockerfile`, `image_lock_consistency.py`, `test_image_lock_consistency.py` | Locked install + checker | VERIFIED | Confirmed hash-checked install, checker's `compare` function, 186-line test file |
| `.github/scripts/coverage-provenance.cjs` + `.test.cjs` | write/write-local/check modes | VERIFIED | 374 + 626 lines; all documented exports present |
| `.github/workflows/release.yml` + `tests/test_github_workflows.py` + `artifact-promotion.test.cjs` | Permission split, no dist | VERIFIED | Read in full; exact permission split confirmed; 630 + 109-line test files |
| `.github/workflows/ci.yml` + `tests/test_ci_followon_wiring.py` | os-scan/actionlint required, coverage+lock wiring | VERIFIED | 444 + 358 lines; read `test`, `docker`, `os-scan`, `actionlint`, `ci-ready` jobs in full |
| `.planning/phases/.../85-TOOL-PINS-AND-BASELINE.md` | Verified tool pins + baseline | VERIFIED | Pins match `ci.yml` exactly; 0 blocking findings in local baseline |
| `.github/scripts/acceptance-readiness.cjs`, `codex-fallback.cjs` + tests | Readiness + fallback validator | VERIFIED | 473 + 430 lines; 208/208 tests pass |
| `tests/test_review_machinery_lists.py` | Three-list drift guard | VERIFIED | 332 lines, passes |
| `docs/codex-adversarial-review-contract.md`, `review-checkpoint-record.md`, `owner-cli-acceptance.md`, `buildomator-greptile-pilot.md` + guard tests | Docs match code (D-16/D-19/D-20) | VERIFIED | Fixed prompt v6 present (`## Fixed prompt (version 6)`), `PLAN_PATHSPECS` wired into runner; untrusted-head interim wording matches code exactly (no overclaiming found) |
| `docs/ci-negative-demonstrations.md`, `85-DEMO-NEGATIVE.patch`, `85-DEMONSTRATIONS.md` | Negative-demo recipes + patch | VERIFIED, and independently exercised | I applied the patch, ran actionlint, reproduced the exact expected failure, then reverted cleanly |
| `.planning/backlog/MAINTENANCE.md` | Carry-forward items resolved | VERIFIED | "Resolved in Phase 85" section lists every folded item with commit hashes; "Still open" correctly retains only the card-template refactor and craft-skill sticky accept, per the must-have |

No artifact in this phase was found to be MISSING, STUB, or ORPHANED.

### Key Link Verification (sample)

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `ci.yml` `os-scan`/`actionlint` jobs | `ci-ready` needs list | `needs: [test, lint, docker, secrets, dependencies, image-smoke, browser-e2e, os-scan, actionlint]` | WIRED | Read directly in `ci.yml` |
| `release-policy.cjs` `REQUIRED_JOBS` | `release.yml preflight` | `REQUIRED_JOBS` array includes `'os-scan'`, `'actionlint'`, `'CI ready'` | WIRED | Confirmed in `release-policy.cjs` |
| `ci.yml` docker job | `image_lock_consistency.py` | `uv run --no-project --with packaging==26.0 python .github/scripts/image_lock_consistency.py --locked ... --freeze ... --environment ...` runs between the image audit and the pip-audit/save steps | WIRED | Read the full `docker` job step order |
| `review-acceptance.yml` | `review-acceptance.cjs` | `ref: 8df9eaf9d68ad0e5fce469ef8393d05bb4ba3fc3` (pinned) | WIRED | Pin commit verified as ancestor of HEAD with zero diff to the current file |
| `acceptance-readiness.cjs` | `review-acceptance.cjs assess()` / `codex-fallback.cjs validateFallback` | `require('./review-acceptance.cjs')` / `require('./codex-fallback.cjs')` | WIRED | Confirmed by reading `acceptance-readiness.cjs` |
| `ci.yml` test job | `coverage-provenance.cjs write` | `node .github/scripts/coverage-provenance.cjs write --coverage coverage.xml --test-exit ... --test-seconds ... --out coverage-provenance.json` | WIRED | Read directly |
| `tests/codex_review_run.py` | `docs/codex-adversarial-review-contract.md` | `TEMPLATE_HEADING = "## Fixed prompt (version 6)"`; `PLAN_PATHSPECS` used in both | WIRED | Grepped both files, headings match |

### Behavioral Spot-Checks (run myself, not trusted from documents)

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full pytest suite passes on this exact HEAD | `uv run pytest tests/ -x -q` | 2650 passed, 38 pre-existing/unrelated deprecation warnings, 91.29s | PASS |
| ruff is clean across modified code | `uv run ruff check triggarr/ tests/ .github/scripts/` | All checks passed! | PASS |
| Full Node suite (CI scripts + planchk-router) passes | `FORCE_COLOR=0 node --test --test-reporter=tap .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs` | 415 tests, 415 pass, 0 fail | PASS |
| All workflows lint clean | `actionlint` | exit 0, no output | PASS |
| No-skip guard (authoritative, Python) | `uv run pytest tests/test_required_jobs_no_skip.py -q` | 79 passed | PASS |
| Review/acceptance/dependabot/image-lock/wiring/github-workflows/ci-gate doc-guard tests | `uv run pytest tests/test_review_machinery_lists.py tests/test_acceptance_docs.py tests/test_review_checkpoint_record.py tests/test_codex_review_contract.py tests/test_review_instructions.py tests/test_dependabot_config.py tests/test_image_lock_consistency.py tests/test_ci_followon_wiring.py tests/test_github_workflows.py tests/test_ci_gate.py -q` | 158 passed | PASS |
| ACCEPT-03 no-skip detector w/ 4 classification fixtures | `node --test .github/scripts/ci-job-consistency.test.cjs` | 83 tests, 83 pass | PASS |
| Readiness + fallback + register + coverage-provenance + os-scan-gate Node suites | `node --test .github/scripts/acceptance-readiness.test.cjs .github/scripts/codex-fallback.test.cjs .github/scripts/review-register.test.cjs .github/scripts/coverage-provenance.test.cjs .github/scripts/os-scan-gate.test.cjs` | 208 tests, 208 pass | PASS |
| Image publish-promotion RED-check guard | `node --test .github/scripts/artifact-promotion.test.cjs` | 6 tests, 6 pass | PASS |
| **Negative demo reproduces the exact expected CIMAINT-04 failure** | Applied `85-DEMO-NEGATIVE.patch`, ran `actionlint`, then restored the working tree | `demo-actionlint-negative.yml:11:24: property "missing" is not defined in object type {} [expression]` (exit 1); working tree confirmed clean afterward | PASS — matches the hand-off's expected failure line verbatim |
| Negative demo's Dockerfile half applies cleanly against the current Dockerfile | `git apply --check 85-DEMO-NEGATIVE.patch` | exit 0 | PASS |
| `review-acceptance.yml`'s pinned gate commit is still accurate | `git diff 8df9eaf9d68ad0e5fce469ef8393d05bb4ba3fc3 HEAD -- .github/scripts/review-acceptance.cjs` | empty diff | PASS |

### Probe Execution

Not applicable — this phase has no `scripts/*/tests/probe-*.sh` convention; its equivalent "probes" are the local gate commands and the negative-demonstration patch, both run above under Behavioral Spot-Checks.

### Requirements Coverage

All 10 requirement IDs declared across the 19 plans' frontmatter (CIMAINT-01 through CIMAINT-07, ACCEPT-01 through ACCEPT-03) are present in `.planning/REQUIREMENTS.md`'s traceability table, correctly still marked `Pending` (not falsely marked Done), matching Plan 85-01's and 85-19's explicit must-have that nothing be ticked complete until verification. No orphaned requirement IDs were found: every ID mapped to "Phase 85" in `REQUIREMENTS.md` appears in at least one plan's `requirements:` frontmatter field (cross-checked against the full plan list above).

| Requirement | Status | Evidence |
|---|---|---|
| CIMAINT-01..07, ACCEPT-01..03 | SATISFIED (code-level); GitHub/production confirmation NEEDS HUMAN | See Observable Truths table above |

### Anti-Patterns Found

None at blocker or warning level. I scanned every file touched since `b07e532` (merge-base with `origin/main`) for `TBD`/`FIXME`/`XXX` (zero matches) and `TODO`/`HACK` (zero matches). The only `placeholder` string matches are in `tests/codex_review_run.py`'s legitimate `PLACEHOLDERS` template-substitution constant, not stub code.

The phase's own BM code review (iteration 5, head `1f8e339`) is independently "clean" (0 critical, 0 warning outside an owner-accepted class, 13 info items, all carried/tracked in `MAINTENANCE.md`). I treat that as corroborating evidence, not as a substitute for my own checks — all of its headline claims (2650 pytest, 415/415 Node, ruff clean, actionlint 0) were independently reproduced by me above.

### Planning Documentation Note (not a phase-goal failure — flagged for the owner)

`.planning/ROADMAP.md` line 223 marks "Phase 85" `[x]` with "(completed 2026-10-27)". This is inconsistent with:
- `.planning/STATE.md`, which (as of `2026-10-27T14:54:45.253Z`) says `status: executing`, `stopped_at: "Phase 85 planned; next: /bm:execute-phase 85"`, and "Plan: 19 of 19 done (all waves complete); next: BM phase review + paired Codex, verification" — i.e., STATE.md itself does not claim the phase is finished.
- `.planning/REQUIREMENTS.md`, whose traceability table still lists all 10 of this phase's requirement IDs as `Pending`, by the plan's own explicit design ("Nothing is ticked complete... until verification").
- The six P1-P6 GitHub-only pending items and the pending Codex pass documented in this phase's own `85-REVIEW-EVIDENCE.md`.

Per this user's own CLAUDE.md planning-format rule ("Never invent phase numbers, versions, completion, or implementation activity to satisfy the display"), I recommend the ROADMAP checkbox/completion note not be finalized until the hand-off steps in `85-REVIEW-EVIDENCE.md` (push, Codex pass, real CI run, merge) actually occur — i.e., until this VERIFICATION.md's `human_verification` items are closed out. This is a documentation-accuracy note, not a gap in the engineering work itself, so it is not listed in the `gaps:` frontmatter array and does not change `has_blocking_gaps`.

### Human Verification Required

See the `human_verification` array in the frontmatter above (8 items: P1 through P6, the paired Codex review, and the acceptance-register schema migration). Each names exactly what only a real GitHub run, a real release, a real Dependabot trigger, or an owner-gated production-variable change can show, consistent with this phase's own `85-REVIEW-EVIDENCE.md` "Pending — only GitHub can show" section — none of which I substituted a local proxy for and called passed.

### Gaps Summary

No code-level gaps were found: every requirement's implementation exists, is substantive (no stub patterns, no placeholder returns, no empty handlers), is wired into the real workflows and scripts it needs to reach, and is covered by tests I re-ran myself rather than trusted from SUMMARY.md or REVIEW.md claims. The full local gate (pytest, ruff, Node test suite, actionlint) passes cleanly on this exact unpushed HEAD, matching — and independently confirming — the phase's own evidence record.

What remains is not missing work but **undemonstrated** work: six classes of evidence that only a real GitHub Actions run, a real release, or a real Dependabot trigger can produce (P1-P6); one review step (the paired Codex pass) that this phase's own trust model correctly refused to run locally under BM's worktree-execution pattern, pending an owner-run PR-URL pass; and one production-state change (the acceptance register's schema-1→2 migration) that is deliberately owner-gated and not yet performed. All of this is honestly disclosed in the phase's own `85-REVIEW-EVIDENCE.md` and `85-REVIEW.md`, and I found no instance where a document in this phase claims GitHub-only evidence as already passed. The phase is ready for its hand-off sequence (push, BM-reviewed PR, Codex-by-URL, the owner's negative-demonstration go-ahead, merge, and the post-merge P3/P4/P5 checks) — none of which this verification performed.

---
*Verified: 2026-10-27T23:10:00Z*
*Verifier: Claude (bm-verifier)*
