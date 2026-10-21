---
phase: 82-ci-tests-what-we-ship
plan: "07"
subsystem: ci-release-safety
tags: [github-actions, ci-wiring, node-test, pytest, release-policy, required-jobs]

# Dependency graph
requires:
  - phase: 82-01
    provides: "parseReleaseTag, parseProjectVersion, validateReleaseIdentity, releaseIdentityGate in release-policy.cjs"
  - phase: 82-03
    provides: "release-identity-rehearsal.cjs: rehearseReleaseIdentity(...) calling release.yml's own releaseIdentityGate/parseReleaseTag"
  - phase: 82-04
    provides: "tests/harness/image_smoke.py: python -m tests.harness.image_smoke run --image IMAGE --expected-image-id-file PATH"
  - phase: 82-06
    provides: "tests/e2e/conftest.py CREDENTIAL_RUN_FLAGS and the credential_pages marker/guard; tests/e2e/test_pill_polling.py and test_setup_login_logout.py"
provides:
  - "ci.yml: image-smoke and browser-e2e jobs, both depending only on docker, verifying the audited-image artifact's sha256/image ID before use, never rebuilding"
  - "image-smoke: runs the shipped-image smoke driver, then rehearses release identity against the exact audited image via release-identity-rehearsal.cjs (D-31a)"
  - "browser-e2e: runs tests/e2e twice (credential_pages with capture fully off, everything else with failure-only capture), gates on junit test/skipped/failures/errors counts, uploads failure evidence only after both scan-complete.json markers exist"
  - "ci-ready: needs and required set extended to the full seven-job set; REQUIRED_JOBS in release-policy.cjs extended to match, 'CI ready' last"
  - "ci-job-consistency.test.cjs: updated constants/mutations plus two new negative tests for the new job names"
  - "tests/test_ci_gate.py: runs the real ci-ready heredoc with synthetic needs results (all-success, each new job skipped/failed/cancelled/absent, extra unknown key)"
  - "tests/test_github_workflows.py: _ci_workflow() loader and 17 wiring tests proving the new jobs' shape, image-identity-before-use, SHA pinning, capture-policy split, no-retry, failure-upload gating, junit gating, rehearsal fidelity (byte-identical IMAGE_VERSION format string vs. release.yml), no path filters, D-18 coverage, and ci-ready's if: always()"
affects: ["82-08 (CI-level recorded demonstrations: broken entrypoint, pill-bug reintroduction)", "82-09 (release-safeguard evidence record)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Download-and-verify, never rebuild: both new jobs reuse the docker job's exact sha256sum -c / docker image inspect --format '{{.Id}}' round-trip pattern before any other use of the audited image"
    - "Single point of truth for REQUIRED_JOBS: editing ci.yml's ci-ready (needs + Python required set) and release-policy.cjs's REQUIRED_JOBS together is what ci-job-consistency.test.cjs's existing real-files-are-consistent test verifies for free"
    - "Wiring tests parse the real YAML/text, never reimplement the workflow semantics (image_version_format_matches compares two extracted format strings, it does not re-derive either)"

key-files:
  created:
    - tests/test_ci_gate.py
  modified:
    - .github/workflows/ci.yml
    - .github/scripts/release-policy.cjs
    - .github/scripts/ci-job-consistency.test.cjs
    - tests/test_github_workflows.py

key-decisions:
  - "Corrected an execution-sequencing slip before it reached Task 2: my first Task 1 edit's anchor text accidentally included ci-ready's needs/required lines, prematurely applying Task 2's change. Used `git reset --soft HEAD~1` (non-destructive, working tree/index untouched) to uncommit, re-split the diff so Task 1 left ci-ready byte-identical to the pre-plan state, then ran Task 2's RED test against the genuinely unmodified ci-ready before GREEN -- preserving the project_rules TDD requirement (failing wiring test before the ci.yml/REQUIRED_JOBS change)"
  - "browser-e2e wires TRIGGARR_E2E_IMAGE via a step-level env: block rather than an inline shell-prefixed pytest invocation (the plan's <interfaces> 'via' text showed the inline form) -- same effect, idiomatic GitHub Actions style matching how other env values already reach steps in this workflow (e.g. ci-ready's RESULTS); no behavior difference"
  - "The browser-suite run step computes both pytest exit codes itself (set +e/set -e) and exits 1 if either failed, rather than relying on GitHub Actions' default step-failure propagation -- this keeps both invocations unconditional (no retry, both always run per D-15) while still failing the job for either outcome"
  - "The junit-count gate step does not use if: always() -- it is unreachable after a nonzero exit from the invocation step, which is fine: that step already reports a specific exit-code failure; the junit gate's own job is to catch the case the exit code alone can't (zero selected tests trivially 'passing'), which it does regardless of whether the invocation step itself failed first"

requirements-completed: [CISHIP-01, CISHIP-02, CISHIP-03, CISHIP-04]

# Metrics
duration: ~25min
completed: 2026-10-21
---

# Phase 82 Plan 07: CI Wiring for image-smoke, browser-e2e, and the Required Gate Summary

**Wires the Phase 82 smoke driver, browser suite, and release-identity rehearsal into two new mandatory CI jobs that consume only the verified audited image, joins them to `ci-ready`/`REQUIRED_JOBS` together, and proves the wiring with a test that runs the real gate script plus 17 new YAML-level assertions against the real workflow.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-10-21
- **Tasks:** 3 completed
- **Files modified:** 4 (1 created, 4 modified -- `ci.yml`, `release-policy.cjs`, `ci-job-consistency.test.cjs` modified across Tasks 1-2; `tests/test_ci_gate.py` created and `tests/test_github_workflows.py` modified in Tasks 2-3)

## Accomplishments
- `image-smoke` (15 min timeout) and `browser-e2e` (20 min timeout) added between `dependencies` and `ci-ready`, both `needs: [docker]`, no `if:`, no path filters anywhere in `ci.yml`'s `on:` (D-12)
- `image-smoke` downloads and identity-verifies `audited-image`, runs `python -m tests.harness.image_smoke run --image triggarr:ci-test --expected-image-id-file image/image-id.txt`, then rehearses release identity against the same image: re-checks the image ID, exports `IMAGE_ID`/`IMAGE_VERSION` (the latter read with the byte-identical `docker image inspect` format string release.yml's "Read audited image version label" step uses) and `REHEARSAL_SHA`, then runs `node .github/scripts/release-identity-rehearsal.cjs` (D-31a) -- no `if:`, no `continue-on-error`
- `browser-e2e` downloads and identity-verifies the same artifact, installs Chromium, runs `tests/e2e` twice (credential_pages with `--tracing off --screenshot off --video off`; everything else with `--tracing retain-on-failure --screenshot only-on-failure`), computes both exit codes itself and fails if either is nonzero (both always run, no retry, D-15), then a junit-count gate step fails unless both junit files report the expected minimum test counts with zero skipped/failures/errors (an unexplained skip never counts as success, D-12), then uploads `e2e-artifacts` as `browser-e2e-failure` only `if: failure() && hashFiles(.../scan-complete.json) != ''` for both markers -- never uploading the junit files themselves
- `ci-ready`'s `needs` and Python `required` set, and `release-policy.cjs`'s `REQUIRED_JOBS`, now list all seven jobs plus `CI ready` last; `ci-job-consistency.cjs` itself is untouched (confirmed via `git diff --quiet`)
- `tests/test_ci_gate.py` (new, 6 tests) extracts and runs the real `ci-ready` Python heredoc from `ci.yml` with synthetic `RESULTS`, proving: all-seven-success exits 0; `image-smoke` skipped, `browser-e2e` failure/cancelled each exit nonzero with "did not succeed"; a missing key or an extra unknown key each exit nonzero with "Missing or unexpected"
- `tests/test_github_workflows.py` gains a `_ci_workflow()` loader and 17 new tests (34 total in the file, up from 17 before this plan) covering job shape, image-verify-before-first-use with no rebuild steps, universal 40-hex SHA pinning, the credential-pages/failure-only capture split read against `tests/e2e/conftest.py`'s own `CREDENTIAL_RUN_FLAGS`, no reruns/retries, the failure-upload gate, the junit skip/failure/error gate, the harness+rehearsal invocations, rehearsal step fidelity (ordering, no `if`/`continue-on-error`, `IMAGE_ID`/`IMAGE_VERSION`/`REHEARSAL_SHA` present), a byte-identical format-string comparison against `release.yml` (plus a mismatch-detection negative proving the comparison helper actually discriminates), the `on:` trigger set, D-18's test-job coverage, and `ci-ready`'s `if: always()`
- Full verification: `node --test .github/scripts/*.test.cjs` → 115/115; `uv run --no-sync pytest tests/ -q` → 2160/2160 (up from 2137 before this plan); `uv run --no-sync ruff check triggarr/ tests/` → clean

## Task Commits

1. **Task 1: Add image-smoke and browser-e2e jobs to ci.yml** - `3815822` (feat)
2. **Task 2 (RED): Add failing tests for the ci-ready gate script** - `61778c3` (test)
3. **Task 2 (GREEN): Join image-smoke and browser-e2e to the required CI gate** - `3ca4fbd` (feat)
4. **Task 3: Add CI workflow wiring tests for image-smoke/browser-e2e** - `73ae4b2` (test)

**Plan metadata:** (this commit, pending) - `docs(82-07): complete CI wiring plan`

## Files Created/Modified
- `.github/workflows/ci.yml` - Adds `image-smoke` and `browser-e2e` jobs; extends `ci-ready`'s `needs:` and Python `required` set to the full seven-job list
- `.github/scripts/release-policy.cjs` - `REQUIRED_JOBS` extended with `'image-smoke'`, `'browser-e2e'`, keeping `'CI ready'` last
- `.github/scripts/ci-job-consistency.test.cjs` - `NEEDS_LINE`/`PYTHON_REQUIRED_LINE` constants and every derived `mutate()` string updated to the new eight-job graph; `parseJobs` assertion updated; two new negative tests added (removing `image-smoke` from needs+Python set with `REQUIRED_JOBS` unchanged; removing `browser-e2e` from `REQUIRED_JOBS` only)
- `tests/test_ci_gate.py` (new) - Extracts and runs the real `ci-ready` heredoc with synthetic `RESULTS`; 6 tests
- `tests/test_github_workflows.py` - Adds `_ci_workflow()` and 17 new wiring tests (see Accomplishments)

## Decisions Made
See `key-decisions` in the frontmatter for the execution-sequencing correction and the two cosmetic wiring choices (step-level `env:` for `TRIGGARR_E2E_IMAGE`; the invocation step computing both exit codes itself rather than relying on GitHub Actions' default step-failure propagation).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Corrected a self-inflicted task-boundary violation before it reached Task 2's RED/GREEN gate**
- **Found during:** Task 1, immediately after the first commit
- **Issue:** Task 1's single `Edit` call used an anchor string that spanned into `ci-ready`'s `needs:`/`required =` lines (needed to place the new jobs immediately before `ci-ready`), and the replacement text I supplied for that anchor also updated those two lines to the new seven-job form -- prematurely applying Task 2's change inside Task 1's commit, and violating Task 1's own explicit constraint ("ci-ready is changed in Task 2") and the orchestrator's `tdd_mode` requirement ("failing wiring tests first ... before the ci.yml/REQUIRED_JOBS change").
- **Fix:** Used `git reset --soft HEAD~1` (non-destructive -- working tree and index untouched, nothing in `destructive_git_prohibition`'s list) to uncommit, reverted just the two `ci-ready` lines back to the pre-plan 5-job form in the working tree, re-committed Task 1 scoped to only the two new jobs (confirmed via `git diff HEAD -- .github/workflows/ci.yml` showing no `ci-ready`/`needs:`/`required =` lines in the diff), then proceeded with Task 2's RED test against the genuinely unmodified `ci-ready` before GREEN.
- **Files modified:** `.github/workflows/ci.yml`
- **Verification:** `tests/test_ci_gate.py` run against the reverted `ci-ready` showed 4/6 tests failing with "Missing or unexpected mandatory CI jobs" (the real pre-change behavior); after Task 2's GREEN edit, all 6 passed.
- **Committed in:** Resolved before `3815822` was finalized; no separate commit needed since the correction happened pre-commit via the soft reset.

**2. [Rule 3 - Blocking] Reformatted the "Upload browser failure evidence" `if:` condition to a folded multi-line block to satisfy the acceptance-criteria grep count**
- **Found during:** Task 1, verifying acceptance criteria
- **Issue:** The plan's acceptance criteria specify `grep -c "scan-complete.json" .github/workflows/ci.yml` = 2. `grep -c` counts matching *lines*, not occurrences; my first draft put both `hashFiles(...)` calls on one single-line `if:`, so the count was 1, not 2.
- **Fix:** Reformatted the `if:` to the repo's existing folded-scalar style (`if: >-` with each clause on its own line, same pattern as `release.yml`'s job-level `if:`), putting each `hashFiles('.../scan-complete.json')` call on its own line.
- **Files modified:** `.github/workflows/ci.yml`
- **Verification:** `grep -c "scan-complete.json" .github/workflows/ci.yml` now returns 2; `yaml.safe_load` confirms the folded block parses to the identical single boolean expression as before.
- **Committed in:** `3815822` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3 -- blocking/mechanical, both resolved before or within Task 1's commit). No deviation touched product code (`triggarr/`) or changed any CI behavior beyond what the plan specifies; `git diff --name-only` against the phase-start commit shows only the plan's declared `files_modified` plus this SUMMARY.
**Impact on plan:** Deviation 1 preserved the TDD gate integrity the project rules require; deviation 2 is purely a grep-counting cosmetic fix with no behavior change. No scope creep.

## Recorded Negative-Case Evidence (per the plan's acceptance criteria, not a committed RED state)

Temporarily added `if: github.event_name == 'push'` to `browser-e2e` in `.github/workflows/ci.yml` (reverted before the Task 3 commit; `git diff --stat -- .github/workflows/ci.yml` showed no diff afterward). `uv run --no-sync pytest tests/test_github_workflows.py -q` failed as follows:

```
FAILED tests/test_github_workflows.py::test_new_ci_jobs_depend_only_on_docker_with_no_if[browser-e2e]
AssertionError: assert 'if' not in {'if': "github.event_name == 'push'", 'needs': ['docker'], 'runs-on': 'ubuntu-latest', 'steps': [...], ...}
```

1 failed, 33 passed. Reverting the mutation returned the file to the committed state and all 34 tests passed again.

## Issues Encountered
- Node's default `node --test` reporter on this environment prints `ℹ fail N` rather than a `# fail N` TAP line; confirmed pass/fail state via exit codes and the reporter's own pass/fail counts throughout (same non-issue noted in 82-01-SUMMARY.md).

## User Setup Required
None - no external service configuration required. This plan touches only GitHub Actions workflow/script/test files; no Docker build, no NAS, no push, no PR.

## Known Stubs
None - this plan adds CI workflow wiring and test infrastructure only (no UI, no data flows, no product code, no mock/placeholder behavior).

## Threat Flags
None beyond what the plan's own `<threat_model>` already registers (T-82-30 through T-82-35, T-82-SC). This plan introduces no new network endpoints, auth paths, file-access patterns, or schema changes -- both new jobs inherit workflow-level `permissions: contents: read`, reference no secrets, and only download-and-verify the existing `audited-image` artifact.

## Next Phase Readiness
- Both `image-smoke` and `browser-e2e` are fully wired into the required gate and ready for Plan 08's real GitHub CI run (the D-07 requirement that GitHub-enforced-gate claims need an actual CI run on an isolated branch/draft PR, never local evidence alone) and its recorded broken-entrypoint/pill-bug demonstrations.
- `REQUIRED_JOBS`, `ci-ready`, and `ci-job-consistency.cjs`'s checker all agree (CISHIP-04); `release-policy.cjs`'s own release-time `preflight()`/`validateEvidence()` will transparently re-verify both new jobs on the next release via the same `REQUIRED_JOBS` array, with no further changes needed there.
- No blockers. This plan touched exactly its declared files (`ci.yml`, `release-policy.cjs`, `ci-job-consistency.test.cjs`, `tests/test_ci_gate.py`, `tests/test_github_workflows.py`) and none of `review-acceptance.yml`, `release.yml`, `ci-job-consistency.cjs`, `tests/harness/**`, or `tests/e2e/**` (confirmed via `git diff --name-only` against the phase-start commit).

---
*Phase: 82-ci-tests-what-we-ship*
*Completed: 2026-10-21*

## Self-Check: PASSED

- FOUND: tests/test_ci_gate.py
- FOUND: .github/workflows/ci.yml
- FOUND: .github/scripts/release-policy.cjs
- FOUND: .github/scripts/ci-job-consistency.test.cjs
- FOUND: tests/test_github_workflows.py
- FOUND commit: 3815822 (feat(82-07): add image-smoke and browser-e2e jobs to ci.yml)
- FOUND commit: 61778c3 (test(82-07): add failing tests for the ci-ready gate script)
- FOUND commit: 3ca4fbd (feat(82-07): join image-smoke and browser-e2e to the required CI gate)
- FOUND commit: 73ae4b2 (test(82-07): add CI workflow wiring tests for image-smoke/browser-e2e)
