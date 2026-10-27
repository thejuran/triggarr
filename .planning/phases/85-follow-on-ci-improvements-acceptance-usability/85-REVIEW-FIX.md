---
phase: 85-follow-on-ci-improvements-acceptance-usability
fixed_at: 2026-10-27T22:13:35Z
review_path: .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW.md
iteration: 4
findings_in_scope: 4
fixed: 2
skipped: 0
rejected: 0
accepted_residual_risk: 2
status: partial
---

# Phase 85: Code Review Fix Report (iteration 4)

**Fixed at:** 2026-10-27T22:13:35Z
**Source review:** .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW.md (iteration 4, reviewed head `eae6d34`)
**Iteration:** 4. This is the last fix round, by owner decision on 2026-10-27 ("Close cheap gaps, then stop").

**Summary:**
- Findings in scope (critical and warning): 4 (CR-01, WR-01, WR-02, WR-03)
- Fixed: 2 (CR-01, WR-03)
- Not fixed, recorded as owner-accepted residual risk: 2 (WR-01, WR-02)
- Skipped: 0
- Rejected: 0
- Also fixed because the owner put it in scope: IN-13 (info)

All work is on branch `ci-followon` in the main working tree. Nothing was pushed.

## Fixed Issues

### CR-01: The guard ignores `shell:` and `defaults: run: shell:`

**Files modified:** `tests/test_required_jobs_no_skip.py`
**Commit:** 1527d4a
**Applied fix:**
- The authoritative guard now rejects these in `ci.yml` and `review-acceptance.yml`:
  - `shell:` on any step of a required job;
  - `defaults:` on a required job;
  - `defaults:` at workflow level.
- It reports the value, so `shell: true {0}` shows up as `sets shell: 'true {0}'`.
- `shell` and `defaults` were added to `WATCHED_KEYS`, so case variants are caught too (`Shell`, `SHELL`, `Defaults`). Workflow-level `Defaults` is caught as well.
- Built-in shells such as `bash` and `sh` are also rejected, since no workflow uses `shell:` today. If one is ever needed, it should be allowlisted the way step `if:` is.
- **Regression tests, written first and failing (12 of them):**
  - the three placements the review reproduced: job-level `defaults` on `ci-ready`, step `shell` on the `ci-ready` gate step after its `env:` block, and step `shell` on "Fail if tests failed";
  - workflow-level `defaults` in both files;
  - `defaults` and `shell` in the acceptance job;
  - built-in shells;
  - the case variants above.
- The real workflow files still pass. The Node detector was not touched, as instructed.
- I did not add the reviewer's untested `BASH_ENV`/`ENV` hardening idea; it was outside the owner's scope.

### WR-03: Another workflow can publish a second "CI ready" check run

**Files modified:** `tests/test_required_jobs_no_skip.py`
**Commit:** a69c082
**Applied fix:**
- `required_check_name_problems` loads every `.github/workflows/*.yml` and `*.yaml` file with the strict SafeLoader.
- It checks that "CI ready" is the check name of exactly one job across all of them: `ci.yml`'s `ci-ready`.
- A job's check name is its `name:`, or its id when it has no name. Names are compared after trimming and case-folding.
- A workflow file that cannot be loaded fails the scan closed.
- **Scope note:** the same table also pins "Review acceptance" to `review-acceptance.yml`'s `acceptance` job. The owner's instruction named only "CI ready". I added this because the finding names both required checks, the gap is identical, and it is one extra table entry. The real files pass.
- **Regression tests, written first and failing (9 of them):**
  - a mirror workflow with `.yml` and with `.yaml`;
  - an unnamed job whose id is "CI ready";
  - a second "CI ready" name inside `ci.yml`;
  - the name moved off `ci-ready`;
  - a "Review acceptance" mirror;
  - an unloadable workflow;
  - a test that the scan covers every workflow file;
  - the real files pass.
- **Not done:** the readiness-side half of the review's fix (binding the check run to its workflow run in `acceptance-readiness.cjs`). The owner scoped this round to the static guard.

### IN-13: The policy names the Node detector as the no-skip test (info; fixed because the owner put it in scope)

**Files modified:** `docs/review-classification-policy.md`, `tests/test_review_instructions.py`
**Commit:** d160083
**Applied fix:**
- The policy's status line now names `tests/test_required_jobs_no_skip.py` as the authoritative no-skip test. The Node detector `.github/scripts/ci-job-consistency.cjs` is named as a secondary line of defence, and the pytest guard wins when the two disagree.
- The sensitive row now lists "the required-check safeguard tests (`tests/test_required_jobs_no_skip.py`, `tests/test_ci_gate.py`)".
- That entry sits outside the "review machinery (...)" list. Because of that:
  - the three-list drift guard (`tests/test_review_machinery_lists.py`) needed no change;
  - the Codex scope (`AUDITED_INPUTS`) and the acceptance checklist line did not need to change either.
- No other place in the policy lists safeguard tests.
- **Regression tests, written first and failing (2 of them, in `tests/test_review_instructions.py`):** one pins both safeguard tests in the sensitive row and checks they exist; the other pins the authoritative/secondary wording on the status line.

## Not fixed: owner-accepted residual risk

### WR-01: The guard's CI verdict is enforced only by "Fail if tests failed", the step it protects

**File:** `.github/workflows/ci.yml:47-58, 88-95`
**Disposition:** Not fixed. The owner accepted this as residual risk on 2026-10-27.
**Where it is recorded:** commit 4ae24c1:
- `85-REVIEW-EVIDENCE.md`, section "Accepted residual risk (owner decision 2026-10-27)";
- `.planning/backlog/MAINTENANCE.md`, under "Still open after Phase 85". The possible future hardening listed there is to move the gate logic into a tested script, or run the guard in a second required job.

**Original issue:** Adding `continue-on-error` to "Fail if tests failed" swallows the guard's own CI failure, so "CI ready" goes green.

### WR-02: The gate steps are pinned only by their script bodies; hard-coded `env:` inputs pass every check

**File:** `.github/workflows/ci.yml:430-433, 89-90`
**Disposition:** Not fixed. The owner accepted this as residual risk on 2026-10-27, recorded in the same commit (4ae24c1) and the same two places.
**Original issue:** A hard-coded `RESULTS` on the `ci-ready` gate step, or `TEST_EXIT` on "Fail if tests failed", makes the gate always see success.

**Why this is acceptable:** Both are deliberate tampering with the gate steps themselves, which a static guard cannot rule out. They are covered by:
- the sensitive classification of every workflow change;
- BM code review plus the paired Codex pass;
- the owner's acceptance of the exact commit.

## Full gate (after all commits, head 4ae24c1)

| Check | Result |
|-------|--------|
| `uv run pytest tests/ -x -q` | 2650 passed, 0 failed (38 warnings) |
| `uv run ruff check triggarr/ tests/ .github/scripts/` | All checks passed |
| `FORCE_COLOR=0 node --test --test-reporter=tap .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs` | 415 tests, 415 pass, 0 fail |
| `actionlint` | exit 0 |

**Commits this round:**
- `1527d4a` CR-01
- `a69c082` WR-03
- `d160083` IN-13
- `4ae24c1` docs(85): residual-risk record

This report is not committed.

**Next step under the review workflow:** these fixes changed the head. The fresh BM code review and its paired Codex pass must run on the new head before this round can be reported as clean.

---

_Fixed: 2026-10-27T22:13:35Z_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 4_
