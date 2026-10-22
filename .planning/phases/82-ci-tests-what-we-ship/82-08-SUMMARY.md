---
phase: 82-ci-tests-what-we-ship
plan: "08"
subsystem: ci-release-safety
tags: [github-actions, ci-wiring, codeql, release-identity, playwright, required-checks]

# Dependency graph
requires:
  - phase: 82-07
    provides: "image-smoke and browser-e2e jobs wired into ci.yml and joined to CI ready / REQUIRED_JOBS"
provides:
  - "docs/ci-negative-demonstrations.md: reproduction recipes and failure policy for the broken-entrypoint and pill-regression demonstrations (D-08, D-09, D-15, D-16, D-32, D-33)"
  - "82-CI-EVIDENCE.md: pre-push /deep-review record (3 passes, APPROVED) and the first real GitHub CI run of image-smoke/browser-e2e on PR #33, with D-34 commit identities reconciled and the D-14 budget measured"
  - "A recorded, unresolved required-check stop: CodeQL fails at the pushed head on two high-severity clear-text-storage alerts in a Plan 06 e2e probe file"
affects: ["82-09 (release-safeguard evidence record; inherits the open CodeQL finding as a blocker to clear before any final-head owner acceptance)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Required-check stop discipline: a failing required GitHub check (even one outside the plan's own ci.yml changes) halts the plan without an auto-fix attempt or a second push, per the authorization boundary"

key-files:
  created:
    - docs/ci-negative-demonstrations.md
  modified:
    - .planning/phases/82-ci-tests-what-we-ship/82-CI-EVIDENCE.md

key-decisions:
  - "Task 3 stopped after the push and evidence collection rather than attempting to fix the CodeQL finding: the finding predates this task (introduced by Plan 06's capture-policy probe), and the authorization boundary explicitly forbids changing tests/assertions or pushing a fix when a required check fails -- it requires recording and stopping instead"
  - "Computed the D-14 budget (added critical-path time 2m57s against a pre-phase main baseline) and confirmed it is well under the ~5 minute target, so no budget-exceeded stop applies independently of the CodeQL stop"

requirements-completed: []

# Metrics
duration: ~45min (Task 3 portion; Tasks 1-2 completed in a prior session)
completed: 2026-10-21
---

# Phase 82 Plan 08: CI Review Workflow, Push Evidence, and Budget Measurement Summary

**Pushed PR #33 to GitHub and recorded the first real run of image-smoke/browser-e2e (all required ci.yml jobs green, rehearsal and junit evidence captured, D-14 budget 2m57s added, well under 5 minutes) -- then stopped per the plan's authorization boundary because the branch ruleset's required CodeQL check fails at this head on a pre-existing finding in a Plan 06 test probe.**

## Performance

- **Duration:** ~45 min (this session, Task 3 only; Tasks 1-2 were completed in a prior session per the objective)
- **Completed:** 2026-10-21
- **Tasks:** 2 of 3 complete (Task 1 and Task 2 done previously; Task 3 reached its push/evidence/budget goals but stopped before declaring the plan fully green, due to an unplanned required-check failure)
- **Files modified:** 1 (`82-CI-EVIDENCE.md`, this session; `docs/ci-negative-demonstrations.md` was created in Task 1, prior session)

## Status: PARTIAL (stopped at required-check failure, not a plan checkpoint)

Tasks 1 and 2 were already complete when this execution started (Task 1 commit `3d28bc0`; Task 2 decision/outcome recorded at `3315a88`, owner chose `/deep-review`, 3 passes, APPROVED). This execution covered Task 3: pushed the branch, watched the first real GitHub CI run, collected and reconciled all D-34 commit identities, verified the audited image artifact locally, measured the D-14 budget, and recorded all of it in `82-CI-EVIDENCE.md`. All eight `ci.yml` jobs this phase cares about (`test`, `lint`, `docker`, `secrets`, `dependencies`, `image-smoke`, `browser-e2e`, `CI ready`) succeeded. The branch ruleset's fourth required check, `CodeQL`, failed at this head with two new high-severity alerts unrelated to this task's own changes. Per the authorization boundary ("If any required job fails ... do NOT change tests or assertions and do NOT push a fix ... record ... and STOP"), this execution recorded the failure and stopped rather than attempting a fix or a second push.

## Accomplishments

- Pushed `ci-review-workflow` to PR #33 with a plain fast-forward push (`3fa038a..3315a88`); no force push, no change to `main`.
- First real GitHub run of `image-smoke` and `browser-e2e`: run [39697729420](https://github.com/thejuran/triggarr/actions/runs/39697729420), all 8 required `ci.yml` jobs `success` (`test` 2m6s, `lint` 10s, `secrets` 9s, `dependencies` 10s, `docker` 1m6s, `image-smoke` 30s, `browser-e2e` 1m24s, `CI ready` 3s).
- `image-smoke` log confirms `SMOKE PASSED`, the missing-static-asset negative rejected as expected, and the CISHIP-03 rehearsal's four cases (matching accepted `2.12.0`; mismatched, malformed, missing each rejected for their specific reason) against the exact audited image.
- `browser-e2e` log confirms both junit suites green with zero skips (`credential_pages` 6 passed; other pages 1 passed), satisfying the job's own junit-count gate.
- D-34 commit identities collected and reconciled: PR head `3315a882e2e98d2a3a81752708bb0ec8269e3f88`, PR base `81eb55001b0118c026a8276150d852c89e71ff50`, tested SHA (GitHub's `pull_request` merge commit) `16faed9ae7e54403ae200243fcf5118024271177`; `git rev-list --parents` on the tested SHA confirmed its parents are exactly base then head. Downloaded the `audited-image` artifact into the scratch directory, verified `sha256sum -c`, `docker load`-ed it, confirmed the loaded image ID matches `image-id.txt` and the rehearsal's own image ID, and confirmed the `org.opencontainers.image.revision` label equals the tested SHA; removed the local image tag afterward.
- D-14 budget measured: baseline is the most recent main-branch `CI` run predating this phase's first workflow change (run [39660507361](https://github.com/thejuran/triggarr/actions/runs/39660507361), head `81eb550`, workflow wall-clock 1m57s); the new run's workflow wall-clock is 4m54s. Added critical-path time: **2m57s**, well under the ~5 minute D-14 target -- no budget-exceeded stop needed.
- Discovered (not caused by this task) that the branch ruleset's required `CodeQL` check fails at this head: two new high-severity `py/clear-text-storage-sensitive-data` alerts in `tests/e2e/probes/probe_setup_fails_before_registration.py` (lines 38 and 51), where the probe writes its disposable, session-scoped test password and API key to files so a subprocess can hand them back to the parent test. Recorded run/check details, alert numbers (13, 14) and annotation text in `82-CI-EVIDENCE.md`; did not touch the file or push a fix.

## Task Commits

1. **Task 1: Write the reproduction recipes and failure policy** - `3d28bc0` (docs) -- completed in a prior session
2. **Task 2: Pre-push technical review decision** - `3315a88` (docs; the deep-review decision/outcome record) plus the review's own fix commits `a59bb3b`, `d05b1b3`, `ea3a973`, `2d85236`, `d3e46ab`, `131a598`, `1133126` -- completed in a prior session
3. **Task 3: Push to PR #33, record the first real run, measure the budget** - `1a0fdae` (docs; this session)

## Files Created/Modified
- `docs/ci-negative-demonstrations.md` - Reproduction recipes and failure policy (Task 1, prior session; unchanged this session)
- `.planning/phases/82-ci-tests-what-we-ship/82-CI-EVIDENCE.md` - Added "First real GitHub run (Plan 08, Task 3)" section: commit identities, reconciliation, CI evidence (tested SHA), review evidence (PR head), budget measurement, and the CodeQL required-check failure record

## Decisions Made
See `key-decisions` in the frontmatter: stopped at the CodeQL finding rather than auto-fixing or pushing again (out of this task's scope and explicitly forbidden by the authorization boundary on a required-check failure); confirmed the D-14 budget is not exceeded so no separate budget stop applies.

## Deviations from Plan

None in the Rule 1-4 sense -- this execution made no code changes at all (Task 3 is push-and-record only). The CodeQL finding is not a deviation this plan introduced; it is a pre-existing condition at the pushed head (introduced by Plan 06's probe file) that this plan's verification surfaced for the first time because the branch ruleset's `--required` check set includes `CodeQL`, which the plan's own written acceptance criteria (listing only the eight `ci.yml` jobs) did not anticipate failing.

## Assumption Drift (advisory)

- **Found during:** Task 3, immediately after the push, while running `gh pr checks 33 --required` per the plan's verify step.
- **Planned assumption:** The plan's acceptance criteria and verify command assume the first real GitHub run would be judged green on the eight `ci.yml` jobs it explicitly lists (`test, lint, docker, secrets, dependencies, image-smoke, browser-e2e, CI ready`), with Greptile/Review acceptance/CodeQL treated as background checks whose results are "recorded, not paused on" (per the plan's own Task 3 action text, which only mentions recording the Greptile Review conclusion).
- **Actual:** `CodeQL` is itself one of the branch ruleset's four required status checks (confirmed via `repos/thejuran/triggarr/rules/branches/main`), and it failed at this head with two new high-severity findings unrelated to this plan's own file changes.
- **Why it matters:** The authorization boundary's stop condition ("if any required job fails ... STOP") is written broadly enough to cover any required check, not only the `ci.yml` ones the plan's acceptance criteria enumerate. Treating `CodeQL`'s pass/fail as just another thing to "record, not pause on" (as the plan's prose suggests for Greptile) would have been the wrong read; this execution followed the broader, safer reading of the authorization boundary and stopped.

## Issues Encountered

- **CodeQL required-check failure (stop condition, not resolved by this plan):** See "Required-check failure: CodeQL (stop condition)" in `82-CI-EVIDENCE.md` for the full record (check run URL, alert numbers, annotation text, affected lines). The finding is in test-only code (a probe's deliberate file-write of disposable, session-scoped test credentials for a subprocess exchange), but CodeQL's static analysis cannot distinguish that from a production secret-handling bug from the write-to-file pattern alone. This needs a disposition before the branch's required-check set is fully green: either an inline suppression with rationale, a code-scanning alert dismissal with a recorded reason, or a structural change to the probe that avoids writing the values to disk in cleartext (e.g. restricting file permissions and/or using a named pipe), whichever the owner judges appropriate. Not decided here -- outside this task's authorized scope (no test/code changes, no second push).

## User Setup Required

None - no external service configuration required for Task 3 itself. The scratch directory used for local image verification (`/private/tmp/claude-501/-Users-julianamacbook-triggarr/72ccd835-a846-4599-a5e0-d8ba995139ed/scratchpad/ci82`) still holds the downloaded `audited-image` artifact files (`image.tar`, `image.tar.sha256`, `image-id.txt`, `image-requirements.txt`); the loaded Docker image tag itself was removed (`docker image rm triggarr:ci-test`). No NAS or other image was touched.

## Known Stubs

None - this plan's Task 3 is CI push/evidence/measurement only; no UI, no data flows, no product code.

## Threat Flags

None beyond this plan's own `<threat_model>` (T-82-36 through T-82-39, T-82-45), all of which this execution's own conduct satisfies: pushed only `ci-review-workflow`, no force push, never `main` (T-82-36); run IDs/attempts/SHAs/log lines copied into `82-CI-EVIDENCE.md` (T-82-37); no merge or owner-acceptance submission attempted (T-82-38); evidence contains only SMOKE/rehearsal/result lines, no credentials (T-82-39); all five D-34 identity fields recorded separately with an explicit reconciliation line (T-82-45).

## Next Phase Readiness

- **Not ready for Plan 09 / final owner acceptance as-is.** The CodeQL finding is an open required-check failure on the exact head (`3315a882e2e98d2a3a81752708bb0ec8269e3f88`) that would otherwise be the basis for the phase's release-safeguard evidence record. It must be dispositioned (fixed, suppressed with rationale, or dismissed with a recorded reason) and a fresh CI run obtained before Plan 09 can rely on this head, or before any owner acceptance per `docs/owner-cli-acceptance.md`.
- All CI evidence this plan was asked to capture for the `ci.yml` jobs themselves (test/lint/docker/secrets/dependencies/image-smoke/browser-e2e/CI ready, D-34 identities, D-31a rehearsal, D-14 budget) is complete and green, and does not need to be re-collected once the CodeQL finding is resolved -- only a fresh CI run on the resolving commit needs a new identity/evidence pass.
- Local evidence commit `1a0fdae` is **not pushed** (per the authorization boundary, a required-check failure forbids pushing a fix or continuing). The next step is an owner decision on how to disposition the CodeQL finding, then a plan/task to apply it, push, and re-verify.
- `main` was not touched; no force push; no `review-acceptance` approval was requested, submitted, or inferred.

---
*Phase: 82-ci-tests-what-we-ship*
*Completed: 2026-10-21*

## Self-Check: PASSED

- FOUND: docs/ci-negative-demonstrations.md
- FOUND: .planning/phases/82-ci-tests-what-we-ship/82-CI-EVIDENCE.md
- FOUND commit: 3d28bc0 (docs(82-08): add CI negative-demonstration recipes and failure policy)
- FOUND commit: 3315a88 (docs(82-08): record pre-push deep-review decision and outcome)
- FOUND commit: 1a0fdae (docs(82-08): record first GitHub CI run and CodeQL required-check stop)
