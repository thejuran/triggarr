---
phase: 82-ci-tests-what-we-ship
plan: "03"
subsystem: ci-release-safety
tags: [release-policy, github-actions, node-test, pytest, release-identity, wiring-tests]

# Dependency graph
requires:
  - phase: 82-01
    provides: "parseReleaseTag, parseProjectVersion, validateReleaseIdentity, releaseIdentityGate in release-policy.cjs"
provides:
  - "release.yml: three tag-only steps (Validate release tag format, Read audited image version label, Verify release version identity) wired before any publication step"
  - "release-identity-rehearsal.cjs: rehearseReleaseIdentity({pyprojectText, sha, imageVersion, imageId}) calling release.yml's own releaseIdentityGate/parseReleaseTag against the exact audited image, covering matching/mismatched/malformed/missing cases (D-31a)"
  - "tests/test_github_workflows.py: publication_bypass_violations(workflow) structural proof that a rejection blocks every publication path, with 11 parametrized mutated-workflow negatives (D-31b)"
  - "artifact-promotion.test.cjs: supplementary orderingViolations(text) ordering/sparse-checkout/no-tag-deletion checks (D-05)"
affects: ["82-07 (wires the rehearsal script into the image-smoke job's CI run)", "82-09 (release-safeguard record; D-31d limitation sentence)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Rehearsal calls the exact entry points release.yml calls (releaseIdentityGate, parseReleaseTag), never validateReleaseIdentity directly, so it can never silently diverge from the real gate (D-31a)"
    - "publication_bypass_violations(workflow) is a pure structural function over the parsed YAML dict, proving blocking (position + status-function bypass + continue-on-error + job-reachability + trigger set + tag-only restriction), not merely string ordering (D-31b)"
    - "orderingViolations(text) factored as a pure function returning a violation list so synthetic bad-text negatives can assert non-emptiness without needing a second full workflow fixture"

key-files:
  created:
    - ".github/scripts/release-identity-rehearsal.cjs"
    - ".github/scripts/release-identity-rehearsal.test.cjs"
  modified:
    - ".github/workflows/release.yml"
    - ".github/scripts/artifact-promotion.test.cjs"
    - "tests/test_github_workflows.py"

key-decisions:
  - "Validated imageId/sha format before any case runs in rehearseReleaseIdentity, so a missing or malformed audited-image identity refuses the whole rehearsal rather than silently rehearsing against nothing (D-31a)"
  - "Used a ruff-clean stub (return []) for publication_bypass_violations' RED commit instead of leaving it fully undefined, because the repo's pre-commit hook enforces ruff clean (F821) even on an intentional TDD RED commit; the .cjs side used a true ReferenceError RED state since no equivalent static-analysis hook blocks JavaScript"
  - "Deep-copied the parsed real release.yml for each of the 11 bypass mutations to avoid cross-test mutation bleed between parametrized cases"

requirements-completed: [CISHIP-03, CISHIP-04]

# Metrics
duration: ~20min
completed: 2026-10-21
---

# Phase 82 Plan 03: Release Identity Wiring & Rehearsal Summary

**Wires Plan 01's release-identity gate into release.yml before any publication step, adds a CI rehearsal script that calls the same entry points against the audited image, and proves the gate blocks every publication path with 11 mutated-workflow negatives.**

> **Release-safeguard change:** This plan extends `.github/workflows/release.yml`, the workflow that authorizes and performs every publication (registry login, image push, GitHub Release creation). Per `CLAUDE.md`'s Deep Code Review Convention, this change should be included in the `/deep-review` scope before this phase's PR is pushed.

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-10-21
- **Tasks:** 3
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments
- `rehearseReleaseIdentity` exercises `release.yml`'s own `releaseIdentityGate` and `parseReleaseTag` (never a reimplementation, never `validateReleaseIdentity` directly) against the exact audited image, covering matching/mismatched/malformed/missing version cases, usable as both a library function and a CLI script reading `REHEARSAL_SHA`/`IMAGE_VERSION`/`IMAGE_ID`
- `release.yml`'s `release` job now validates the tag format before downloading the image, reads the audited image's version label only after the existing sha256/image-ID checks, and verifies tag/package/image identity strictly before `docker/login-action`, any image push, or GitHub Release creation — with values passed through `env`, never interpolated into the script body
- `publication_bypass_violations(workflow)` is a structural Python function proving a rejection blocks every publication path: it reports the real `release.yml` clean, and catches 11 distinct bypass mutations (status-function conditions, `continue-on-error`, reordering, an ungated mirror job, a new trigger, and an unrestricted `latest` tag)
- `orderingViolations(text)` in `artifact-promotion.test.cjs` supplies the supplementary ordering/sparse-checkout/no-tag-deletion checks, with its own synthetic-text negatives proving the checker itself can fail
- Full suite after this plan: 113/113 Node tests (`.github/scripts/*.test.cjs`), 2081/2081 pytest tests, `ruff check triggarr/ tests/` clean

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Write failing tests for the release-identity rehearsal script** - `c1219e4` (test)
   **Task 1 (GREEN): Implement the rehearsal script** - `0f485ad` (feat)
2. **Task 2: Wire the release-identity gate into release.yml before publication** - `6cc0181` (feat)
3. **Task 3 (RED): Add failing wiring tests proving a rejection blocks publication** - `dc8713c` (test)
   **Task 3 (GREEN): Implement publication_bypass_violations and orderingViolations** - `6c73d83` (feat)

**Plan metadata:** (this commit, pending) - `docs(82-03): complete release identity wiring and rehearsal plan`

## Files Created/Modified
- `.github/scripts/release-identity-rehearsal.cjs` - `rehearseReleaseIdentity({pyprojectText, sha, imageVersion, imageId, gate, parseTag})`; CLI entry reading `REHEARSAL_SHA`/`IMAGE_VERSION`/`IMAGE_ID` and the checked-out `pyproject.toml`
- `.github/scripts/release-identity-rehearsal.test.cjs` - 7 `node:test` cases covering the matching/mismatched/malformed/missing cases, spy-confirmed gate/parseTag invocation, image-label drift, invalid image identity, and both stubbed-gate negative behaviors (D-03)
- `.github/workflows/release.yml` - Adds "Validate release tag format", "Read audited image version label" (id `image-version`), and "Verify release version identity" steps to the `release` job, all tag-only, all before `docker/login-action`
- `.github/scripts/artifact-promotion.test.cjs` - Adds `orderingViolations(text)` plus 4 new tests (real-workflow clean, reorder negative, tag-deletion negative, sparse-checkout-count negative)
- `tests/test_github_workflows.py` - Adds `publication_bypass_violations(workflow)`, 3 direct wiring assertions (tag-only ifs, env-not-interpolation, unchanged permissions), and 12 new tests (11 parametrized bypass mutations + the real-workflow-is-clean case)

## Decisions Made
- Followed Plan 01's authoritative interface names (`releaseIdentityGate`, `parseReleaseTag`) rather than the earlier `validateTagFormat`/`validateVersionIdentity` names sketched in `82-PATTERNS.md`, consistent with `82-01-SUMMARY.md`'s own note that the `82-01-PLAN.md` interfaces block is the more recent contract.
- `release-identity-rehearsal.cjs` validates `imageId` (`^sha256:[a-f0-9]{64}$`) and `sha` (`^[a-f0-9]{40}$`) before building the contents-API stand-in or parsing `pyproject.toml`, so a missing or malformed audited-image identity refuses the whole rehearsal rather than silently rehearsing against nothing (D-31a: "the rehearsal refuses to run without the audited image's ID").
- For Task 3's RED commit, used a ruff-clean stub (`return []`) for `publication_bypass_violations` instead of leaving it fully undefined — the repo's pre-commit hook enforces `ruff check` (which flags `F821: Undefined name`) even for an intentional TDD RED commit, so a true "undefined function" RED state could not be committed for the Python side. The stub still produced genuine failures for the correct reason (11/12 dependent tests failed because no violations were reported where violations were expected); the `.cjs` side used a real `ReferenceError` RED state since no equivalent static-analysis hook blocks JavaScript commits.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Adjusted the Python TDD RED commit to satisfy the repo's ruff pre-commit hook**
- **Found during:** Task 3 RED commit
- **Issue:** `project_rules` mandates a failing-tests-first commit (`test(82-03): ...`) before the implementation commit. Leaving `publication_bypass_violations` entirely undefined (true RED) tripped the repo's pre-commit hook, which runs `ruff check` on staged files and blocks on `F821: Undefined name`, refusing the commit outright.
- **Fix:** Defined `publication_bypass_violations` as a trivial stub (`return []`) for the RED commit. This kept `ruff check` clean while still producing the intended failures: 11 of 12 dependent tests failed because the stub reports no violations where violations are expected; the real-workflow "clean" case passed trivially (`[] == []`). The following GREEN commit replaced the stub with the full implementation.
- **Files modified:** `tests/test_github_workflows.py`
- **Verification:** `uv run --no-sync ruff check tests/test_github_workflows.py` passed on both the RED and GREEN commits; `pytest -q` showed 11 failed / 6 passed on RED, 17/17 passed on GREEN.
- **Committed in:** `dc8713c` (RED), `6c73d83` (GREEN)

---

**Total deviations:** 1 auto-fixed (1 blocking — CLAUDE.md-enforced tooling constraint)
**Impact on plan:** Cosmetic to the TDD mechanics only — no behavior change, no scope creep. The intended RED/GREEN proof (tests fail before the real implementation exists, for the right reason) still holds.

## Recorded Negative-Case Evidence (D-06-style, per the plan's `<output>` instruction)

**Bypass-negative:** a temporary manual edit added `if: always()` to "Publish audited image without rebuilding" in `.github/workflows/release.yml` (reverted before commit, confirmed via `git diff --stat` showing no diff). `uv run --no-sync pytest tests/test_github_workflows.py -q` failed as follows:

```
FAILED tests/test_github_workflows.py::test_publication_bypass_violations_real_workflow_is_clean
AssertionError: assert ['release.Pub...ction bypass'] == []
  Left contains one more item: 'release.Publish audited image without rebuilding: publication step if-condition has a status-function bypass'
```

**Ordering-negative:** a temporary manual edit moved the "Verify release version identity" step to after the first `docker/login-action` step in `.github/workflows/release.yml` (reverted before commit, confirmed via `git diff --stat` showing no diff). `node --test .github/scripts/artifact-promotion.test.cjs` failed as follows:

```
✖ release.yml release-identity steps are correctly ordered relative to publication (supplementary; D-31b) (1.479625ms)
  AssertionError [ERR_ASSERTION]: Expected values to be strictly deep-equal:
  + actual - expected
  + [ 'Verify release version identity must precede the first docker/login-action' ]
  - []
```

Both suites returned to green (113/113 node, 17/17 python) immediately after reverting each mutation.

## Issues Encountered
None beyond the ruff pre-commit hook adjustment documented above.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - this plan adds CI workflow wiring and test infrastructure only (no UI, no data flows, no mock/placeholder product behavior).

## Next Phase Readiness
- `rehearseReleaseIdentity` is ready for Plan 07 to wire into the `image-smoke` job's CI run, printing its four case lines on every CI run against the exact audited image (D-31a).
- `publication_bypass_violations` and the 11 bypass fixtures are available for Plan 09's release-safeguard evidence record; the plan's required limitation sentence ("Version validation and release wiring verified; actual tag-triggered publication remains unverified until the next authorized release.") is Plan 09's responsibility to record verbatim (D-31d), not reproduced here.
- No blockers. This plan touched exactly its declared files (`release.yml`, `release-identity-rehearsal.cjs`/`.test.cjs`, `artifact-promotion.test.cjs`, `tests/test_github_workflows.py`) and none of `review-acceptance.yml`, `ci.yml`, or `release-policy.cjs` (confirmed via `git diff --name-only` against the phase-start commit).

---
*Phase: 82-ci-tests-what-we-ship*
*Completed: 2026-10-21*

## Self-Check: PASSED

- FOUND: `.github/scripts/release-identity-rehearsal.cjs`
- FOUND: `.github/scripts/release-identity-rehearsal.test.cjs`
- FOUND: `.planning/phases/82-ci-tests-what-we-ship/82-03-SUMMARY.md`
- FOUND: commit `c1219e4` (test(82-03): add failing tests for the release-identity rehearsal script)
- FOUND: commit `0f485ad` (feat(82-03): add release-identity rehearsal script)
- FOUND: commit `6cc0181` (feat(82-03): wire release-identity gate into release.yml before publication)
- FOUND: commit `dc8713c` (test(82-03): add failing wiring tests proving a rejection blocks publication)
- FOUND: commit `6c73d83` (feat(82-03): implement publication_bypass_violations and orderingViolations)
