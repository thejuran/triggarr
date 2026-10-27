---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "02"
subsystem: ci
tags: [github-actions, node-test, ci-job-consistency, acceptance]

# Dependency graph
requires:
  - phase: 82-ci-tests-what-we-ship
    provides: "ci.yml's ci-ready aggregate, review-acceptance.yml, and the existing ci-job-consistency.cjs/.test.cjs scaffolding"
provides:
  - "findSkipConditions({workflowText, aggregateJobId, triggerContract}): proves no skip path exists for a workflow's required jobs"
  - "requiredJobsFor({workflowText, aggregateJobId, change}): simulates which required jobs run/could be skipped for a given change"
  - "aggregateCanPassWith({workflowText, aggregateJobId, failedNeeds}): demonstrates the continue-on-error escape"
  - "TRIGGER_CONTRACTS and STEP_IF_ALLOWLIST: the reviewed trigger shapes and step-if allowlist entries for ci.yml and review-acceptance.yml"
affects: [ci-maintenance, acceptance-usability, review-classification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Text-scanning workflow analysis (parseJobs/extractJobIf) extended with a new parseOnBlock trigger parser and extractStepIfs step-level if: collector, same stdlib-only approach as the existing checkJobListConsistency"

key-files:
  created: []
  modified:
    - .github/scripts/ci-job-consistency.cjs
    - .github/scripts/ci-job-consistency.test.cjs

key-decisions:
  - "Any job-level if: other than none (and the aggregate's always()) conservatively marks a job skippable for every change in requiredJobsFor, since a condition the simulator cannot evaluate is treated as a possible skip"
  - "continue-on-error is scanned at job level AND step level for every required job including the aggregate itself and its validation step, per checker B11 — a rejected prerequisite must not be able to report success through either path"
  - "A syntax-unparseable on: block (scalar, sequence, or a trigger expressed as a flow mapping) short-circuits findSkipConditions with a single 'unsupported trigger syntax' problem rather than attempting partial validation"

requirements-completed: [ACCEPT-03, CIMAINT-04]

# Metrics
duration: ~15min
completed: 2026-10-27
---

# Phase 85 Plan 02: No-Skip Detector for Required Checks Summary

**Added `findSkipConditions`/`requiredJobsFor`/`aggregateCanPassWith` to `ci-job-consistency.cjs`, proving by permanent test (not separate GitHub runs) that no path filter, job-level if, continue-on-error, non-always aggregate if, or unallowlisted step if can let `ci.yml`'s `ci-ready` or `review-acceptance.yml` pass without every required job running.**

## Performance

- **Duration:** ~15 min (estimate; not precisely timed — see commit timestamps below for the two task commits)
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `findSkipConditions` validates each workflow's trigger contract (which triggers are present, exact branch lists, required PR activity types, and the four skip-enabling filter keys `paths`/`paths-ignore`/`branches-ignore`/`tags-ignore`) and every required job (job-level `if:`, `continue-on-error` at job or step level — including the `ci-ready` aggregate and its own validation step — the aggregate's `if: always()`, and step-level `if:` against a reviewed allowlist), returning one specific-reason problem string per violation.
- `requiredJobsFor` simulates which required jobs would run/be skippable for a given change `{files, labels, title}`, using a minimal `**`/`*` glob matcher for path filters and the conservative "unevaluable if: marks skippable" rule.
- `aggregateCanPassWith` demonstrates the checker B11 escape: false for the real `ci-ready` (its validation step fails closed on any non-success dependency), true once a `continue-on-error` mutation exists at job or step level.
- `TRIGGER_CONTRACTS` pins `ci.yml` (push + pull_request, both branches `[main]`, PR types `opened/synchronize/reopened`) and `review-acceptance.yml` (pull_request only, branches `[main]`, PR types adding `ready_for_review`). `STEP_IF_ALLOWLIST` pins the two existing reviewed evidence-upload step conditions ("test::Upload test evidence" -> `always()`; "browser-e2e::Upload browser failure evidence" -> the normalized folded condition).
- Four classification fixtures (`ordinary-docs`, `sensitive-docs`, `mixed`, `misclassified`) exercise `requiredJobsFor` against the real `ci.yml`: all required jobs run, none skippable, for every fixture at baseline. The misclassified fixture is additionally used to prove that an added job-level `if:` marks the affected job skippable regardless of its claimed classification.

## Task Commits

Each task was committed atomically (TDD RED -> GREEN):

1. **Task 1: RED — tests for the no-skip detector and the four classification fixtures** - `27f52dc` (test)
2. **Task 2: GREEN — implement findSkipConditions, requiredJobsFor and STEP_IF_ALLOWLIST** - `a8fc2c1` (feat)

_No REFACTOR commit was needed — the GREEN implementation did not require cleanup beyond what was written._

## Files Created/Modified

- `.github/scripts/ci-job-consistency.test.cjs` - Added the `ACCEPT-03 no-skip detector` describe block: 29 new tests covering real-workflow clean passes, trigger-contract violations (missing trigger, narrowed/widened branches, missing PR activity type, unsupported syntax, unknown trigger, unknown key), filter-key violations (`paths`, `paths-ignore`, `branches-ignore`), job-level `if:` and `continue-on-error` violations (including the `ci-ready` aggregate and its validation step, in both boolean and expression form), the `aggregateCanPassWith` escape demonstration, the aggregate's `if: always()` check, and step-level `if:` allowlist violations.
- `.github/scripts/ci-job-consistency.cjs` - Added `parseOnBlock`, `extractStepIfs`, `resolveRequiredJobIds`, `findSkipConditions`, `requiredJobsFor`, `aggregateCanPassWith`, plus the `TRIGGER_CONTRACTS` and `STEP_IF_ALLOWLIST` constants and supporting helpers (`parseFlowList`, `arraysEqual`, `globToRegExp`/`globMatch`). All five new names added to `module.exports` alongside the existing ones.

## Decisions Made

- When a trigger's syntax can't be parsed as a block mapping (scalar `on:`, sequence `on: [...]`, or a trigger expressed as a flow mapping), `findSkipConditions` returns immediately with a single `unsupported trigger syntax` problem rather than attempting any further validation on unparseable data (fail closed, matches `parseOnBlock`'s and the rest of the file's existing fail-closed style).
- `continue-on-error` detection is a single regex scan (`/\bcontinue-on-error\s*:/`) applied to every line inside a required job's raw block, catching job-level, step-level, boolean, and expression-form (`${{ true }}`) occurrences uniformly rather than parsing each form separately — simpler and matches the plan's "whatever its value" requirement.
- `requiredJobsFor`'s job-level-if-marks-skippable rule does not attempt to evaluate the condition's actual label/branch logic; it is deliberately conservative (any non-`always()` job-level if marks the job skippable for every change), matching the plan's explicit "a condition the simulator cannot evaluate is treated as a possible skip" instruction.

## Deviations from Plan

None - plan executed exactly as written. All test mutation strings were verified against the real file content for exact whitespace/uniqueness before writing (several `mutate()` targets needed enough surrounding context, e.g. including the job-id header line, to avoid ambiguous first-match replacement against near-duplicate lines elsewhere in `ci.yml`, such as the four jobs that each have `timeout-minutes: 20` or the two `if: always()` occurrences at different indentation levels) — this is normal test-writing care within the task's own scope, not a deviation from the plan's instructions.

## Issues Encountered

None. The `node --test --test-skip-pattern="ACCEPT-03 no-skip detector"` behavior used by the plan's RED verify step was confirmed experimentally (a standalone throwaway fixture, not committed) before relying on it: the flag skips tests whose full name matches the given pattern, including a `describe` block by its title.

## User Setup Required

None - no external service configuration required. No new dependencies added (`grep -c "require(" .github/scripts/ci-job-consistency.cjs` returns 0, confirmed).

## Next Phase Readiness

- `findSkipConditions`, `requiredJobsFor`, `aggregateCanPassWith`, `STEP_IF_ALLOWLIST`, and `TRIGGER_CONTRACTS` are now available from `.github/scripts/ci-job-consistency.cjs` for any later same-wave or downstream plan that needs to add a new required job (e.g. an OS-package scan or actionlint job) — such additions should be re-verified against `findSkipConditions` to confirm the new job doesn't introduce a skip path.
- Per the plan's own `<verification>` note, the post-wave integration gate (full `pytest` suite + `node --test .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs`) was deliberately NOT run here — it runs once after every plan in wave 1 has finished, since same-wave plans may hold intentionally failing RED tests. This plan's own test file (`node --test .github/scripts/ci-job-consistency.test.cjs`) passes standalone (50/50), and the broader `node --test .github/scripts/*.test.cjs` glob (148/148) also passes, confirming no cross-script-file regression from this change specifically.
- No blockers for later Phase 85 plans that add required jobs (OS scan, actionlint) — they should extend `REQUIRED_JOBS`/`ci.yml`'s `needs:`/Python `required` set together (already guarded by existing consistency tests) and will automatically be covered by this plan's no-skip scan since it derives required jobs from `ci-ready`'s `needs:` at test time, not a hard-coded list.

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*

## Self-Check: PASSED

- FOUND: `.github/scripts/ci-job-consistency.cjs`
- FOUND: `.github/scripts/ci-job-consistency.test.cjs`
- FOUND: `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-02-SUMMARY.md`
- FOUND: commit `27f52dc` (test(85-02): RED)
- FOUND: commit `a8fc2c1` (feat(85-02): GREEN)
