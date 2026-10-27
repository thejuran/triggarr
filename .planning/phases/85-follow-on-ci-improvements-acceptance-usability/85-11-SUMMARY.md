---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "11"
subsystem: ci
tags: [github-actions, coverage, uv-lock, docker, node-test]

# Dependency graph
requires:
  - phase: 85-follow-on-ci-improvements-acceptance-usability
    plan: "02"
    provides: "findSkipConditions/requiredJobsFor no-skip detector and STEP_IF_ALLOWLIST, used to confirm the edited ci.yml introduces no skip path"
  - phase: 85-follow-on-ci-improvements-acceptance-usability
    plan: "08"
    provides: ".github/scripts/image_lock_consistency.py CLI (--dump-environment, --locked/--freeze/--environment)"
  - phase: 85-follow-on-ci-improvements-acceptance-usability
    plan: "09"
    provides: ".github/scripts/coverage-provenance.cjs write CLI and its MEASURED_PATHS/schema-1 provenance contract"
provides:
  - "ci.yml's test job: no uv build / python-dist upload (D-14); planchk-router tests run by explicit path behind a Node >= 20 guard (D-13); branch coverage collected via a set+e/capture/set-e pytest step (id: pytest) that always exits 0, followed by a provenance write, a run-bound coverage artifact upload, and a final no-if step that reasserts the real pytest exit code (CIMAINT-06)"
  - "ci.yml's docker job: a no-if/no-continue-on-error 'Check image dependencies match uv.lock' step between the dependency audit and pip-audit/image-save, comparing a uv.lock export against the built image's own dumped marker environment (CIMAINT-01)"
affects: [85-15 (new required jobs: os-scan, actionlint), 85-17 (reviewer procedure consuming coverage.xml/coverage-provenance.json)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Step outputs passed to a script via env: variables, never inline ${{ }} interpolation in the run script body (same rule as the existing release-identity step) -- applied to PR_HEAD_SHA/PR_BASE_SHA and the pytest step's test_exit/test_seconds outputs"
    - "Exit-status-preserving coverage collection: set +e / capture $? / set -e / always exit 0 from the measuring step, then a separate final no-if step re-asserts the real exit code after all evidence (provenance JSON, coverage artifact) has already been written -- mirrors the existing browser-e2e job's idiom"

key-files:
  created: []
  modified:
    - .github/workflows/ci.yml
    - tests/test_ci_followon_wiring.py

key-decisions:
  - "The coverage artifact name is exactly `coverage-${{ github.run_id }}-${{ github.run_attempt }}` (no github.sha component), per the plan's literal wording -- binding to run id + attempt is sufficient since coverage-provenance.json itself records tested_sha/pr_head_sha inside the artifact"
  - "The docker job's pre-existing astral-sh/setup-uv step was already positioned immediately after 'Audit actual image dependencies' and before the pip-audit step, so no step reordering was needed -- the new 'Check image dependencies match uv.lock' step was inserted directly after it, which still satisfies 'after the audit, before pip-audit and before Save the audited image'"
  - "The packaging version pin (`--with packaging==26.0`) is read from uv.lock at plan-execution time (grep -A2 'name = \"packaging\"' uv.lock) and hardcoded into the workflow step, matching the plan's instruction; the wiring test re-derives the same value from uv.lock at test time so a future uv.lock bump without a workflow update would fail the test rather than silently drift"

requirements-completed: [CIMAINT-01, CIMAINT-05, CIMAINT-06]

# Metrics
duration: ~25min
completed: 2026-10-27
---

# Phase 85 Plan 11: Wire Coverage, Lock Consistency & planchk-router Tests Into ci.yml Summary

**Wired the Wave 1 pieces into ci.yml's existing `test` and `docker` jobs: dropped the distribution build/upload (D-14), added branch coverage with run-bound provenance that can never mask a test failure (CIMAINT-06), wired the planchk-router tests behind a Node >= 20 guard (D-13), and added a lockfile/image consistency check that runs before the image is ever saved as audited-image (CIMAINT-01) — no new jobs, no coverage-percentage gate.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2 completed
- **Files modified:** 2 (`.github/workflows/ci.yml`, `tests/test_ci_followon_wiring.py`)

## Accomplishments

- `test` job no longer runs `uv build` or uploads a `python-dist` artifact; the "Compile and package" step is now a bare "Compile" step (`compileall` only).
- "Test release safety policy" renamed to "Test CI policy scripts and plugin hooks": a `node -e` guard exits 1 with "Node >= 20 required for node:test and --import" below Node 20, then `node --test .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs` runs both script test suites and the plugin tests by explicit file path (no directory recursion).
- "Run tests" replaced by step `id: pytest`, "Run tests with branch coverage": `set +e` / capture `$?` and elapsed seconds / `set -e`, writing `test_exit`/`test_seconds` to `$GITHUB_OUTPUT`, always exiting 0 so later steps run unconditionally.
- "Write coverage provenance" (no step-level `if:`) calls `node .github/scripts/coverage-provenance.cjs write` with `PR_HEAD_SHA`/`PR_BASE_SHA`/`TEST_EXIT`/`TEST_SECONDS` passed via `env:`, never inline `${{ }}` interpolation in the run script.
- "Upload coverage evidence" (no `if:`) uploads `coverage.xml` + `coverage-provenance.json` as `coverage-${{ github.run_id }}-${{ github.run_attempt }}`, `if-no-files-found: error`.
- "Fail if tests failed" (no `if:`) is the job's final step: exits 1 with "pytest failed (exit N); coverage collection did not change this result" when the recorded pytest exit is non-zero — coverage collection and evidence upload can never mask a real test failure.
- `docker` job gained "Check image dependencies match uv.lock" (no `if:`, no `continue-on-error`) between the existing "Audit actual image dependencies" step and "Check image dependency vulnerabilities"/"Save the audited image": exports `uv.lock` via `uv export --locked --no-dev --no-emit-project --no-hashes`, dumps the built image's own marker environment via `.github/scripts/image_lock_consistency.py --dump-environment` run inside `triggarr:ci-test` with the script bind-mounted read-only, then runs `image_lock_consistency.py --locked` against both with `--with packaging==26.0` (the version pinned in `uv.lock`).
- 9 new wiring tests in `tests/test_ci_followon_wiring.py` (6 for the test job, 3 for the docker job), all written RED-first and confirmed to fail before the corresponding GREEN change.

## Task Commits

Each task was committed atomically (TDD RED -> GREEN):

1. **Task 1 RED — failing test-job wiring tests** - `1308cd3` (test)
2. **Task 1 GREEN — branch coverage, provenance, planchk-router tests, no dist build** - `8a5f48a` (feat/ci)
3. **Task 2 RED — failing docker lock-consistency wiring tests** - `6f3a190` (test)
4. **Task 2 GREEN — lockfile/image consistency check in the docker job** - `28a8de8` (feat/ci)

_No REFACTOR commit was needed for either task — each GREEN implementation passed verification on the first attempt._

## Files Created/Modified

- `.github/workflows/ci.yml` — `test` job: renamed/restructured steps as described above (no `uv build`, no `python-dist` upload, planchk-router wiring, branch-coverage pytest step + provenance + run-bound coverage artifact + final failure reassertion). `docker` job: new "Check image dependencies match uv.lock" step.
- `tests/test_ci_followon_wiring.py` — new file, 9 tests: `test_test_job_has_no_python_distribution_build`, `test_test_job_collects_branch_coverage_without_threshold`, `test_test_job_reasserts_test_failure_after_coverage_upload`, `test_coverage_artifact_bound_to_run`, `test_provenance_receives_pr_head_and_base`, `test_node_tests_include_planchk_router_by_explicit_path`, `test_docker_job_checks_lock_consistency_before_audit_and_save`, `test_lock_consistency_uses_image_environment_and_exact_export`, `test_lock_consistency_step_has_no_if_or_continue_on_error`.

## Decisions Made

- Coverage artifact naming uses `${{ github.run_id }}-${{ github.run_attempt }}` only (no `github.sha` segment), following the plan's literal instruction rather than Pattern 7's illustrative `coverage-${{ github.sha }}-...` example — the full provenance JSON inside the artifact already records `tested_sha`/`pr_head_sha`, so the SHA is not lost, only absent from the artifact name itself.
- The pre-existing `astral-sh/setup-uv` step in the docker job was already positioned correctly (right after "Audit actual image dependencies", right before the pip-audit step), so the plan's conditional "move it if not already before the new step" did not trigger — the new step was inserted directly after it with no reordering.
- The packaging version (`26.0`) was read once from `uv.lock` at execution time and hardcoded into the workflow step per the plan's instruction; the wiring test re-derives the same value from `uv.lock` independently (via its own regex) so the two will disagree — and the test will fail — if `uv.lock`'s packaging version ever changes without a matching workflow update.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' RED tests were confirmed to fail before implementation, and both GREEN implementations passed the plan's exact verification commands and acceptance-criteria greps on the first attempt.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. This plan only edits `ci.yml` and adds a test file; it does not itself run in GitHub Actions (that happens the next time this branch's PR runs CI).

## Verification Evidence

- `uv run --no-sync pytest tests/test_ci_followon_wiring.py tests/test_github_workflows.py -x -q` — 49 passed.
- `node --test .github/scripts/ci-job-consistency.test.cjs .github/scripts/release-policy.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs` — 128 passed, 0 failed (confirms the Plan 85-02 no-skip detector reports no problems over the edited `ci.yml` without widening `STEP_IF_ALLOWLIST`).
- `actionlint .github/workflows/ci.yml` — exit 0, no output.
- `grep -c "uv build" .github/workflows/ci.yml` → 0; `grep -c "python-dist" .github/workflows/ci.yml` → 0; `grep -c "planchk-router.test.mjs" .github/workflows/ci.yml` → 1; `grep -c -- "--cov-branch" .github/workflows/ci.yml` → 1; `grep -ci "fail-under" .github/workflows/ci.yml` → 0; `grep -c "image_lock_consistency.py --locked" .github/workflows/ci.yml` → 1.
- `git status --short` is clean after both task commits — no untracked or generated files left in the worktree.

Per this plan's own `<verification>` note (W06: same-wave Plans 85-13 and 85-14 own RED tests), the full `pytest tests/ -x -q` suite and the `node --test .github/scripts/*.test.cjs` glob were deliberately NOT run here — that post-wave integration gate runs once after every plan in this wave has finished.

## Next Phase Readiness

- Plan 85-15 (new required jobs: os-scan, actionlint) can add further jobs to `ci-ready`'s `needs:` without touching anything this plan changed.
- Plan 85-17's reviewer procedure (downloading the `coverage-${{ run_id }}-${{ run_attempt }}` artifact and running `coverage-provenance.cjs check` before placing `coverage.xml` in a vibe-check worktree) can now rely on this plan's artifact actually existing in CI runs.
- No blockers for other Phase 85 plans. The docker job's new step and the test job's restructured steps were verified only via YAML-level wiring tests and `actionlint`/`node --test` in this plan — the first real GitHub Actions run of this exact workflow (this phase's own PR) is the live confirmation that the `uv export`/`--dump-environment`/`image_lock_consistency.py` sequence and the coverage-provenance write actually succeed end-to-end inside a real runner; that was out of this plan's scope per its own Purpose line (no new GitHub run was requested or performed).

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*

## Self-Check: PASSED

- FOUND: `.github/workflows/ci.yml`
- FOUND: `tests/test_ci_followon_wiring.py`
- FOUND: `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-11-SUMMARY.md`
- FOUND commit: `1308cd3` (test(85-11): add failing test-job wiring tests)
- FOUND commit: `8a5f48a` (ci(85-11): branch coverage with provenance, planchk-router tests, no dist build)
- FOUND commit: `6f3a190` (test(85-11): add failing docker lock-consistency wiring tests)
- FOUND commit: `28a8de8` (ci(85-11): fail the docker job when the image disagrees with uv.lock)
