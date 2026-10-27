---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "15"
subsystem: ci
tags: [github-actions, trivy, actionlint, security-scan, node-test, tdd]

# Dependency graph
requires:
  - phase: 85-follow-on-ci-improvements-acceptance-usability
    plan: "01"
    provides: docs/os-scan-policy.md (D-08..D-12), written and committed before any os-scan job existed
  - phase: 85-follow-on-ci-improvements-acceptance-usability
    plan: "02"
    provides: findSkipConditions/requiredJobsFor/aggregateCanPassWith no-skip detector and STEP_IF_ALLOWLIST/TRIGGER_CONTRACTS
  - phase: 85-follow-on-ci-improvements-acceptance-usability
    plan: "05"
    provides: schema-2 keyed acceptance register (unrelated surface, same ci-ready gate this plan extends)
  - phase: 85-follow-on-ci-improvements-acceptance-usability
    plan: "07"
    provides: os-scan-gate.cjs classifier (parseReport/validateExceptions/classifyFindings/renderSummary/runCli) and the empty .github/os-scan-exceptions.json
  - phase: 85-follow-on-ci-improvements-acceptance-usability
    plan: "10"
    provides: release.yml's split permissions and REQUIRED_JOBS consumer (releaseIdentityGate/validateEvidence) this plan's REQUIRED_JOBS update feeds
  - phase: 85-follow-on-ci-improvements-acceptance-usability
    plan: "11"
    provides: ci.yml's test/docker job restructuring (branch coverage, lockfile consistency) that this plan's new jobs are appended alongside
  - phase: 85-follow-on-ci-improvements-acceptance-usability
    plan: "12"
    provides: "verified TRIVY_VERSION=0.76.1/TRIVY_LINUX_64BIT_SHA256 and ACTIONLINT_VERSION=1.7.12/ACTIONLINT_SHA256 pins in 85-TOOL-PINS-AND-BASELINE.md, and the 0-blocking-findings local baseline"
provides:
  - "os-scan job: downloads+checksum-verifies the audited-image artifact, installs a pinned checksum-verified Trivy binary, scans OS packages only with no filter flags, and runs os-scan-gate.cjs with the exceptions file, writing findings to the job summary (CIMAINT-03, D-08/D-09/D-11/D-12)"
  - "actionlint job: unconditional (no needs/if/continue-on-error), installs a pinned checksum-verified actionlint binary, requires shellcheck on PATH, lints every workflow with no file args or -ignore flags (CIMAINT-04)"
  - "os-scan and actionlint added to ci-ready's needs, its Python required set, and release-policy.cjs's REQUIRED_JOBS together (D-11)"
  - "9 new wiring tests in tests/test_ci_followon_wiring.py; ci-job-consistency.test.cjs's NEEDS_LINE/PYTHON_REQUIRED_LINE and every embedded-job-list mutation updated to the 9-job set"
affects: ["85-16 (review-machinery drift guard and Python RED tests in the same wave)", "85-17 (reviewer procedure built on the required-check set this plan finalizes)", "85-19 (final-wave hard gate re-runs this plan's verification commands)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pinned-binary-tool install (curl -fsSLO + sha256sum -c against a committed checksum), reused identically for both Trivy and actionlint, matching the repo's existing dependencies-job/Tailwind pattern -- no trivy-action/setup-trivy/actionlint wrapper Action anywhere"
    - "Unconditional required job (no needs, no if, no continue-on-error) as the construction that makes 'a skip can't fake a pass' true by inspection, mirrored from the existing secrets job"

key-files:
  created: []
  modified:
    - .github/workflows/ci.yml
    - .github/scripts/release-policy.cjs
    - .github/scripts/ci-job-consistency.test.cjs
    - tests/test_ci_followon_wiring.py

key-decisions:
  - "os-scan's Trivy invocation uses --scanners vuln --pkg-types os (not just --pkg-types os) to be explicit that only the vulnerability scanner runs against OS packages -- this is additive precision, not a filter flag, and does not appear in the task's forbidden-flags list"
  - "actionlint and Trivy pin values (ACTIONLINT_VERSION=1.7.12/ACTIONLINT_SHA256, TRIVY_VERSION=0.76.1/TRIVY_LINUX_64BIT_SHA256) were copied verbatim from 85-TOOL-PINS-AND-BASELINE.md rather than re-verified in this plan -- Plan 85-12 already re-verified them against the live Trivy advisory and actionlint release at execution time"
  - "release-policy.cjs's REQUIRED_JOBS stayed a single-line array (not reformatted to multi-line) so the plan's own exact-literal acceptance grep ('os-scan', 'actionlint', 'CI ready') and the Python wiring test's single-line regex both match without DOTALL"

patterns-established: []

requirements-completed: [CIMAINT-03, CIMAINT-04]

# Metrics
duration: ~10min
completed: 2026-10-27
---

# Phase 85 Plan 15: Required OS-Scan and Actionlint Jobs Summary

**Added a pinned, checksum-verified `os-scan` job (Trivy against the exact audited-image artifact, gated by `os-scan-gate.cjs`) and an unconditional `actionlint` job, then wired both into `ci-ready`'s needs, its Python required set, and `release-policy.cjs`'s `REQUIRED_JOBS` together so neither can be silently skipped on PRs, main pushes, or releases.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-10-27T13:51:30Z
- **Completed:** 2026-10-27T14:01:24Z
- **Tasks:** 2 (both TDD: RED → GREEN)
- **Files modified:** 4

## Accomplishments

- `os-scan` job runs right after `docker`: downloads the `audited-image` artifact, verifies `image.tar.sha256` before touching it, installs Trivy as a pinned binary verified with `sha256sum -c` against a committed checksum (never `aquasecurity/trivy-action`/`setup-trivy`), scans with no result-filtering flags, and hands the raw JSON to the already-committed `os-scan-gate.cjs` classifier with the owner-approved exceptions file and `$GITHUB_STEP_SUMMARY`.
- `actionlint` job is unconditional (no `needs`, no `if`, no `continue-on-error`) so "legitimately not needed" is not a case that can exist; it fails closed if `shellcheck` is missing from `PATH`, installs actionlint as a pinned checksum-verified binary, and lints every workflow with no file arguments or `-ignore` flags.
- Both jobs joined `ci-ready`'s `needs:`, its embedded Python `required = {...}` set, and `release-policy.cjs`'s `REQUIRED_JOBS` in the same commit — `checkJobListConsistency` and the 85-02 no-skip detector (`findSkipConditions`) both report zero problems against the final `ci.yml`.
- `actionlint` run with no arguments against the whole repository exits 0 — no findings needed fixing in `ci.yml`, `release.yml`, or `review-acceptance.yml`.
- D-10 ordering confirmed by `git merge-base --is-ancestor`: the OS-scan policy commit (`a55f690`, Plan 85-01) is an ancestor of this plan's enforcement commit (`f38de70`).

## Task Commits

Each task was committed atomically (TDD RED → GREEN):

1. **Task 1: os-scan required job (wiring tests first)**
   - `d1ac0ec` test(85-15): add failing os-scan wiring tests
   - `0f689c7` ci(85-15): add OS-package scan job (CIMAINT-03)
2. **Task 2: actionlint required job; wire both jobs into CI ready and REQUIRED_JOBS; lint every workflow clean**
   - `0c88dd9` test(85-15): add failing actionlint and aggregate wiring tests
   - `f38de70` ci(85-15): require os-scan and actionlint in CI ready and the release preflight (CIMAINT-03/04, D-11)

_No REFACTOR commit was needed for either task — both GREEN implementations passed verification on the first attempt._

## Files Created/Modified

- `.github/workflows/ci.yml` — new `os-scan` job (after `browser-e2e`) and new `actionlint` job (after `secrets`); `ci-ready`'s `needs:` and Python `required = {...}` set extended to include both.
- `.github/scripts/release-policy.cjs` — `REQUIRED_JOBS` extended to `['test', 'lint', 'docker', 'secrets', 'dependencies', 'image-smoke', 'browser-e2e', 'os-scan', 'actionlint', 'CI ready']` (aggregate still last).
- `.github/scripts/ci-job-consistency.test.cjs` — `NEEDS_LINE`/`PYTHON_REQUIRED_LINE` and every mutation string in the file that embedded the old 7-job list (12 test bodies) updated to the 9-job set; `parseJobs returns the real ci.yml job graph` updated to assert the new job ids and their `needs`.
- `tests/test_ci_followon_wiring.py` — 9 new tests: `test_os_scan_job_shape`, `test_os_scan_scans_verified_audited_artifact`, `test_os_scan_installs_pinned_checksummed_trivy`, `test_os_scan_runs_unfiltered_os_scan`, `test_os_scan_gate_step_uses_exceptions_file_and_summary`, `test_actionlint_job_is_unconditional`, `test_actionlint_installs_pinned_checksummed_binary`, `test_actionlint_requires_shellcheck_and_lints_all_workflows`, `test_new_required_jobs_in_all_three_lists`; plus `_tool_pin()`/`_job_raw_block()` helpers that read pins from `85-TOOL-PINS-AND-BASELINE.md` by regex so a version change must touch both files.

## Decisions Made

- `os-scan`'s Trivy command includes `--scanners vuln` alongside `--pkg-types os` for explicitness (Trivy defaults to scanning all scanner types otherwise); this is not one of the task's forbidden filter flags and does not change which findings are reported — confirmed by the baseline run in Plan 85-12 showing the same finding counts.
- Kept `REQUIRED_JOBS` as a single-line array in `release-policy.cjs` rather than reformatting to multi-line, so both the plan's literal acceptance-criteria grep and the new Python wiring test's single-line regex match directly.
- Followed the plan's instruction to NOT add `os-scan` to `ci-ready` in Task 1 — all aggregate wiring (needs, Python set, REQUIRED_JOBS) landed together in Task 2's single commit, as specified.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' RED tests were confirmed to fail for the expected reason (`KeyError: 'os-scan'`/`'actionlint'`, or a literal-mismatch in the Node mutation constants) before implementation, and both GREEN implementations passed the plan's exact verification commands and acceptance-criteria greps on the first attempt. `actionlint` found zero findings anywhere in the repository both before and after this plan's changes, so no behavior-preserving lint fixes were needed in `release.yml` or `review-acceptance.yml`.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. This plan only edits `ci.yml`/`release-policy.cjs`/test files; it does not itself run in GitHub Actions (that happens the next time this branch's PR runs CI).

## Verification Evidence

- `uv run --no-sync pytest tests/test_ci_followon_wiring.py -x -q` — 18 passed (9 new + 9 from Plan 85-11).
- `uv run --no-sync pytest tests/test_ci_followon_wiring.py tests/test_github_workflows.py -x -q` — 58 passed.
- `uv run --no-sync ruff check triggarr/ tests/` — clean.
- `actionlint` (no arguments, all workflows) — exit 0, zero findings.
- `node --test .github/scripts/*.test.cjs` — tests 315, pass 315, fail 0.
- `node --test .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs` — tests 326, pass 326, fail 0.
- `node --test .github/scripts/ci-job-consistency.test.cjs` specifically — tests 50, pass 50, fail 0 (includes `findSkipConditions on real ci.yml returns no problems` and `real ci.yml and real REQUIRED_JOBS are consistent`).
- `grep -n "uses:.*aquasecurity" .github/workflows/ci.yml` — no output (0 matches).
- `grep -v '^\s*#' .github/workflows/ci.yml | grep -c ignore-unfixed` — 0.
- `grep -c "os-scan, actionlint\]" .github/workflows/ci.yml` — 1.
- `grep -c "'os-scan', 'actionlint', 'CI ready'" .github/scripts/release-policy.cjs` — 1.
- `git merge-base --is-ancestor a55f69033d9117d4dfa21e34c6ba68d807385835 f38de70` — exit 0 (policy commit `a55f690` precedes enforcement commit `f38de70`).
- `git status --short` — clean after every commit; no untracked or generated files left in the worktree.

Per this plan's own `<verification>` note (W06: same-wave Plan 85-16 owns RED Python tests, and no wave-3 plan has Node RED tests), the full `uv run pytest tests/ -x -q` suite was deliberately NOT run here — that post-wave integration gate (W06-R4) runs once after every plan in wave 3 has finished.

## Added CI time (per plan's SUMMARY instruction)

`os-scan` runs in parallel with `image-smoke`/`browser-e2e` after `docker` completes (not serialized behind them), and `actionlint` runs in parallel from workflow start (no `needs`). Plan 85-12's local baseline measured the Trivy scan itself at 7 seconds including a fresh ~130 MiB vulnerability-DB download; `actionlint`'s binary install + lint is sub-second after download. Neither job is expected to extend the critical path measurably against the ~5-minute added-PR-time target (Phase 82 D-14) — but per that target's own standing rule, the real measurement is the phase PR's first actual CI run (Plan 85-19 hand-off), not a local estimate.

## Next Phase Readiness

- `os-scan` and `actionlint` are now required, pinned, checksum-verified jobs gating every PR, main push, and release via `ci-ready` and `REQUIRED_JOBS` together — CIMAINT-03 and CIMAINT-04 are structurally complete pending the first real GitHub Actions run (this phase's own PR) to confirm the non-emulated amd64 Trivy scan and actionlint binary installs succeed on GitHub's actual runners (Plan 85-12's local baseline used `linux/arm64` due to a documented QEMU segfault on this machine; this plan's jobs don't build images at all, so they are unaffected by that substitution, but the real amd64 Trivy download/extract has not yet been observed on a live runner).
- No blockers for Plan 85-16 (review-machinery drift guard, same wave) or Plan 85-17 (reviewer procedure). Plan 85-19's final-wave hard gate re-runs this plan's exact verification commands (`actionlint`, the full `node --test` glob, the full `pytest` suite) as part of its own post-wave integration check.
- `.github/os-scan-exceptions.json` remains the empty schema-1 register from Plan 85-07 — no exception was needed or added by this plan; the baseline recorded in `85-TOOL-PINS-AND-BASELINE.md` (Plan 85-12) found 0 blocking findings.

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*

## Self-Check: PASSED

- FOUND: `.github/workflows/ci.yml`
- FOUND: `.github/scripts/release-policy.cjs`
- FOUND: `.github/scripts/ci-job-consistency.test.cjs`
- FOUND: `tests/test_ci_followon_wiring.py`
- FOUND commit: `d1ac0ec` (test(85-15): add failing os-scan wiring tests)
- FOUND commit: `0f689c7` (ci(85-15): add OS-package scan job (CIMAINT-03))
- FOUND commit: `0c88dd9` (test(85-15): add failing actionlint and aggregate wiring tests)
- FOUND commit: `f38de70` (ci(85-15): require os-scan and actionlint in CI ready and the release preflight (CIMAINT-03/04, D-11))
