---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "18"
subsystem: ci
tags: [github-actions, docker, uv, actionlint, negative-demonstration, hand-off]

# Dependency graph
requires:
  - phase: 85-follow-on-ci-improvements-acceptance-usability
    plan: "08"
    provides: "image_lock_consistency.py's exact 'version mismatch: <name> lock <x> image <y>' failure format and the real idna lock/mismatch version pair (3.15 locked, 3.4 mismatched) already proven locally"
  - phase: 85-follow-on-ci-improvements-acceptance-usability
    plan: "11"
    provides: "the docker job's 'Check image dependencies match uv.lock' step name and its dependents (image-smoke, browser-e2e)"
  - phase: 85-follow-on-ci-improvements-acceptance-usability
    plan: "15"
    provides: "the unconditional actionlint job and os-scan's needs:[docker] wiring, both now required jobs in CI ready"
provides:
  - "docs/ci-negative-demonstrations.md Recipes 4 and 5: the image/lockfile-mismatch and workflow-lint negative demonstrations, written as on-the-phase-PR negative checkpoint pushes (no throwaway PR) with a restore-push and fresh-review rule"
  - "85-DEMO-NEGATIVE.patch: one locally-verified commit's worth of mutations (Dockerfile +1 line pinning a mismatched idna version, plus a new demo-actionlint-negative.yml workflow) ready to apply at push time; never applied to any committed branch state"
  - "85-DEMONSTRATIONS.md: the PENDING evidence skeleton and plain-terms owner go-ahead request text for the Plan 85-19 hand-off"
affects: ["85-19 (hand-off plan that performs the actual negative push, owner go-ahead, restore push, and fresh review using this plan's prepared patch and recipes)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Negative demonstration prepared as a standalone, pre-verified patch file plus a PENDING evidence skeleton, so the actual GitHub push (a separate owner-gated hand-off step) only needs to apply a reviewed patch and fill in already-structured fields, not improvise the mutation or its expected failure text at push time."

key-files:
  created:
    - .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-DEMO-NEGATIVE.patch
    - .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-DEMONSTRATIONS.md
  modified:
    - docs/ci-negative-demonstrations.md

key-decisions:
  - "Reused the exact idna 3.15 (locked) / 3.4 (mismatched) version pair that Plan 85-08 already verified locally, rather than picking a new version pair, so the expected failure text is already proven correct rather than newly asserted."
  - "The demo workflow's only trigger is workflow_dispatch, so actionlint's finding is proven on a file that is linted but never itself executed by the negative push or the PR's own CI event -- isolating the actionlint failure from any other job."
  - "Both mutations were prepared and verified in a detached temporary git worktree (never checked out in the main worktree), so the main worktree's Dockerfile and workflows were never actually mutated by this plan -- only the resulting diff was captured as a patch file."

patterns-established: []

requirements-completed: [CIMAINT-01, CIMAINT-04]

# Metrics
duration: ~13min
completed: 2026-10-27
---

# Phase 85 Plan 18: CI Negative-Demonstration Prep (Lockfile Mismatch + Bad Workflow) Summary

**Prepared, but did not push, one single-commit negative demonstration (a mismatched-idna Dockerfile line plus an invalid demo workflow) that locally proves the exact failure text each of CIMAINT-01's and CIMAINT-04's new required CI jobs will show on the real phase pull request, with a PENDING evidence skeleton and go-ahead request ready for the Plan 85-19 hand-off.**

## Performance

- **Duration:** ~13 min
- **Started:** 2026-10-27T14:11Z (approx.)
- **Completed:** 2026-10-27T14:23:57Z
- **Tasks:** 2 completed
- **Files modified:** 3 (1 modified doc, 2 created files)

## Accomplishments

- Added Recipe 4 (image disagrees with uv.lock) and Recipe 5 (workflow lint failure) to `docs/ci-negative-demonstrations.md`, following Recipe 1's structure (purpose, owner go-ahead requirement, mutation, expected failing job and failure text, expected skipped jobs, evidence fields, restore, repeat-when), plus a shared "Where and how these run" paragraph establishing the on-the-phase-PR negative-checkpoint-push-then-restore-push pattern (never a throwaway PR, never main, never a tag, never force-pushed).
- Verified, in a detached temporary git worktree at `PHASE_HEAD` `fbe6a3a4b5764960ce22e22f1fbe6f4ed600320f` (the main worktree never changed branch or files), that:
  - the clean baseline passes: `uv run --locked --extra dev pytest tests/ -q --ignore=tests/test_acceptance_docs.py --ignore=tests/test_review_checkpoint_record.py` -- 2541 passed in 85.84s; `node --test .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs` -- 326 passed, 0 failed, ~0.49s;
  - both mutations apply cleanly (Dockerfile diff is exactly one added line);
  - `actionlint` on the new demo workflow fails with the exact expected text `property "missing" is not defined in object type {} [expression]`;
  - with both mutations applied, the same pytest and node commands produce identical pass counts (2541 / 326), so no other test is demo-induced-affected.
- Wrote `85-DEMO-NEGATIVE.patch` from that worktree's diff (touching only `Dockerfile` +1 line and the new `demo-actionlint-negative.yml`), confirmed `git apply --check` succeeds against the current phase head, then removed the temporary worktree.
- Wrote `85-DEMONSTRATIONS.md`: a `Status: PENDING` skeleton with the plain-terms owner go-ahead request (including the Greptile disclosure), the expected-failures table, the local verification record, and PENDING evidence fields for the negative head, the restore push, and the fresh review on the restored head.
- Confirmed nothing was pushed: `git ls-remote --heads origin 'demo/*'` printed nothing, both before and after this plan's work.

## Task Commits

1. **Task 1: Write Recipes 4 and 5 as negative checkpoint pushes on the phase PR**
   - `fbe6a3a` docs(85-18): add lockfile-mismatch and workflow-lint demonstration recipes (on the phase PR)
2. **Task 2: Prepare and locally verify the demonstration patch; write the evidence skeleton (no push)**
   - `9680a24` docs(85-18): prepare the demonstration patch and evidence skeleton (no push)

_No plan-metadata commit beyond these two; this SUMMARY and the final metadata commit follow per the executor protocol._

## Files Created/Modified

- `docs/ci-negative-demonstrations.md` - added "## Recipe 4: image disagrees with uv.lock (gate enforcement evidence, kind ii)", "## Recipe 5: workflow lint failure (gate enforcement evidence, kind ii)", and "## Where and how these run" (inserted before the existing "## When to repeat a demonstration (D-09)" section).
- `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-DEMO-NEGATIVE.patch` - the single prepared demonstration commit's diff: `Dockerfile` (+1 line, `RUN pip install --no-cache-dir --no-deps "idna==3.4"`, right after the existing locked/hash-checked install) and the new `.github/workflows/demo-actionlint-negative.yml` (11 lines, `workflow_dispatch`-only trigger, one job referencing an undefined step output).
- `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-DEMONSTRATIONS.md` - the PENDING evidence skeleton: owner go-ahead (PENDING), go-ahead request text, expected-failures table, local verification record, and PENDING evidence tables for the negative head, restore push, and fresh review on the restored head.

## Decisions Made

- Reused the exact idna 3.15 (locked) / 3.4 (mismatched) version pair Plan 85-08 already verified locally rather than selecting a new mismatch pair -- the expected checker output (`version mismatch: idna lock 3.15 image 3.4`) is therefore already-proven text, not a new assertion.
- Gave the demo workflow a `workflow_dispatch`-only trigger so `actionlint`'s failure is isolated: the file is linted (and fails) but is never itself executed by the negative push or by the pull request's own CI trigger.
- Did all mutation work in a detached temporary git worktree (`git worktree add --detach`), never checking either mutation into the main worktree's working tree or any committed branch state -- only the resulting diff was captured, as the plan's threat model (T-85-56) requires.

## Deviations from Plan

None -- plan executed exactly as written. Both tasks' automated verification commands and acceptance criteria passed on the first attempt; no auto-fixes were needed.

## Issues Encountered

None. The baseline and mutated test/node runs produced identical pass counts (2541 pytest / 326 node), so the plan's "setup failure vs. demo-induced failure" distinction never had to be exercised in practice -- there were no setup failures and no demo-induced failures to record beyond what the recipes already predict.

## User Setup Required

None -- no external service configuration required. This plan prepares artifacts only; it performs no push and requires no owner action until Plan 85-19's hand-off.

## Verification Evidence

- `grep -c "## Recipe 4" docs/ci-negative-demonstrations.md` -- 1
- `grep -c "## Recipe 5" docs/ci-negative-demonstrations.md` -- 1
- `grep -c "git revert" docs/ci-negative-demonstrations.md` -- 3
- `git diff -- docs/ci-negative-demonstrations.md | grep '^+' | grep -ciE "gh pr create|--draft|scratch branch"` -- 0
- `git apply --check .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-DEMO-NEGATIVE.patch` -- succeeded
- `grep -c "demo-actionlint-negative.yml" .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-DEMO-NEGATIVE.patch` -- 2
- `grep -c "Owner go-ahead" .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-DEMONSTRATIONS.md` -- 1
- `git ls-remote --heads origin 'demo/*'` -- no output (both before and after)
- Local worktree (`PHASE_HEAD` `fbe6a3a`): baseline `pytest` 2541 passed (85.84s); baseline `node --test` 326 passed, 0 failed (~0.49s); `actionlint` on the demo workflow exited 1 with `property "missing" is not defined in object type {} [expression]`; mutated `pytest` 2541 passed (84.72s); mutated `node --test` 326 passed, 0 failed (~0.51s) -- no demo-induced test failures.
- `git status --short` -- clean after every commit in the main worktree; `test -f .github/workflows/demo-actionlint-negative.yml` in the main worktree -- not present (confirms the demo workflow was never checked into the main worktree).

## Next Phase Readiness

- `85-DEMO-NEGATIVE.patch` is ready to `git apply` and commit on the phase's own PR branch, exactly as Plan 85-19's hand-off requires -- no further local preparation is needed.
- `85-DEMONSTRATIONS.md` has every evidence field marked PENDING and the go-ahead request text ready to present to the owner at push time; Plan 85-19 fills these in as the push, restore, and fresh review actually happen.
- `docs/ci-negative-demonstrations.md` now documents Recipes 1 through 5 and the "Where and how these run" on-the-phase-PR pattern, so a future repeat of these demonstrations (per the "repeat when" conditions recorded in each recipe) has a ready template.
- No blockers for Plan 85-19. Nothing in this plan requires owner action until that hand-off step.

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*

## Self-Check: PASSED

- FOUND: `docs/ci-negative-demonstrations.md`
- FOUND: `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-DEMO-NEGATIVE.patch`
- FOUND: `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-DEMONSTRATIONS.md`
- FOUND commit: `fbe6a3a` (docs(85-18): add lockfile-mismatch and workflow-lint demonstration recipes)
- FOUND commit: `9680a24` (docs(85-18): prepare the demonstration patch and evidence skeleton (no push))
