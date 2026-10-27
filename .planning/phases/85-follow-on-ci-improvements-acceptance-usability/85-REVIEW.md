---
phase: 85-follow-on-ci-improvements-acceptance-usability
reviewed: 2026-10-27T22:19:23Z
reviewed_head: 1f8e3391f02f7637bdf29d6e68038563fadc2258
diff_base: 091d8ed
iteration: 5
depth: standard
files_reviewed: 49
files_reviewed_list:
  - .github/dependabot.yml
  - .github/os-scan-exceptions.json
  - .github/scripts/acceptance-readiness.cjs
  - .github/scripts/acceptance-readiness.test.cjs
  - .github/scripts/artifact-promotion.test.cjs
  - .github/scripts/ci-job-consistency.cjs
  - .github/scripts/ci-job-consistency.test.cjs
  - .github/scripts/codex-fallback.cjs
  - .github/scripts/codex-fallback.test.cjs
  - .github/scripts/coverage-provenance.cjs
  - .github/scripts/coverage-provenance.test.cjs
  - .github/scripts/image_lock_consistency.py
  - .github/scripts/os-scan-gate.cjs
  - .github/scripts/os-scan-gate.test.cjs
  - .github/scripts/release-policy.cjs
  - .github/scripts/review-acceptance.cjs
  - .github/scripts/review-acceptance.test.cjs
  - .github/scripts/review-register.cjs
  - .github/scripts/review-register.test.cjs
  - .github/workflows/ci.yml
  - .github/workflows/release.yml
  - .github/workflows/review-acceptance.yml
  - .gitignore
  - Dockerfile
  - docs/buildomator-greptile-pilot.md
  - docs/ci-negative-demonstrations.md
  - docs/codex-adversarial-review-contract.md
  - docs/os-scan-policy.md
  - docs/owner-cli-acceptance.md
  - docs/review-checkpoint-record.md
  - docs/review-classification-policy.md
  - pyproject.toml
  - README.md
  - SECURITY.md
  - tests/codex_report_status.py
  - tests/codex_review_run.py
  - tests/test_acceptance_docs.py
  - tests/test_ci_followon_wiring.py
  - tests/test_ci_gate.py
  - tests/test_codex_report_status.py
  - tests/test_codex_review_contract.py
  - tests/test_codex_review_run.py
  - tests/test_dependabot_config.py
  - tests/test_github_workflows.py
  - tests/test_image_lock_consistency.py
  - tests/test_review_checkpoint_record.py
  - tests/test_review_machinery_lists.py
  - tests/test_required_jobs_no_skip.py
  - tests/test_review_instructions.py
  - uv.lock
findings:
  critical: 0
  warning: 0
  info: 13
  total: 13
status: clean
---

# Phase 85: Code Review Report (iteration 5, confirming)

**Reviewed:** 2026-10-27T22:19:23Z (head `1f8e3391f02f7637bdf29d6e68038563fadc2258`, diff base `091d8ed`)
**Depth:** standard
**Files Reviewed:** 49 (uv.lock skimmed only)
**Status:** clean. There are no critical or warning findings outside the owner-accepted class. 13 info items remain: 1 new and 12 carried.

## Summary

This is the confirming review after the final owner-approved fix round 4:
- `1527d4a`: CR-01, forbidding `shell:` and `defaults:` overrides;
- `a69c082`: WR-03, requiring each required check name to come from exactly one job;
- `d160083`: IN-13, the policy wording and the sensitive classification of the safeguard tests;
- `4ae24c1`: the residual-risk record.

Between `eae6d34` and this head, only these source files changed:
- `tests/test_required_jobs_no_skip.py`
- `tests/test_review_instructions.py`
- `docs/review-classification-policy.md`

Every other file in scope is byte-identical to the iteration-4 head. The whole-phase findings from iteration 4 therefore still stand, unless this report revises them below.

**Owner stopping rule applied (2026-10-27).** The static no-skip guard targets accidental and obvious skip paths. Deliberately tampering with a gate step's own logic or inputs is owner-accepted residual risk. That class covers iteration-4 WR-01 and WR-02, BASH_ENV-style env injection, and similar edits to a gate step's script or env. It is covered by:
- the sensitive classification of every workflow change;
- BM code review plus the paired Codex pass;
- the owner's acceptance of the exact commit.

No new finding is raised in that class.

**Baseline at this head:**

| Check | Result |
|---|---|
| `uv run pytest tests/ -x -q` | 2650 passed |
| `uv run ruff check triggarr/ tests/ .github/scripts/` | clean |
| Node suite (`.github/scripts/*.test.cjs` plus planchk-router) | 415/415 pass |
| `actionlint` | exit 0 |

### Verification of the round-4 fixes with crafted inputs

I ran these probes against the guard's own functions (`ci_problems`, `acceptance_problems`, `required_check_name_problems`) on mutated copies of the real workflow text. I used a scratch script outside the repo and deleted it afterwards. No source file was modified.

| Prior | Verdict | Crafted inputs and results |
|---|---|---|
| CR-01 (`shell:` / `defaults:`) | **Fixed** | Each of these probes is caught:<br>- `<<: {shell: "true {0}"}` merged into the `ci-ready` gate step: reports `sets shell: 'true {0}'`.<br>- An escaped key, `"s\x68ell": true {0}`, on "Fail if tests failed": caught.<br>- A flow-mapping `defaults: {run: {shell: "true {0}"}}` on `ci-ready`: caught.<br>- A quoted workflow-level `"defaults":`: caught.<br>- An empty `shell:` (value `None`): caught.<br>- Using an alias before its anchor fails to load, so it fails closed.<br>The 12 regression tests cover job-level, step-level and workflow-level placements, built-in shells and case variants. No workflow uses `shell:` or `defaults:` today, so blanket rejection has no false positives. |
| WR-03 (unique check names) | **Fixed for literal names** | Each mirror workflow publishing these names is caught:<br>- `'CI ready '` (trailing space);<br>- `"ci READY"`;<br>- a JSON/flow-style document;<br>- an unnamed job whose id is the check name.<br>An unloadable file fails closed. The scan misses a name built from an expression (`${{ 'CI ready' }}`, `${{ format(...) }}`, or a matrix value). That evasion is deliberate only, so it is graded Info: see IN-14. |
| Round-4 extra "Review acceptance" uniqueness check | **No false positives** | Against the real repo (`ci.yml`, `release.yml`, `review-acceptance.yml`), `required_check_name_problems(workflow_texts()) == []`. No `release.yml` job's name or id case-folds to either required check. A "Review acceptance" mirror is caught. Pinning it to `review-acceptance.yml:acceptance` matches the acceptance-job identity that `acceptance_problems` already enforces, so the two checks cannot disagree. |
| IN-13 (policy wording) | **Fixed** | The status line names `tests/test_required_jobs_no_skip.py` as authoritative and the Node detector as secondary. The sensitive row lists both safeguard tests. Two new tests in `tests/test_review_instructions.py` pin this. The three-list drift guard (`tests/test_review_machinery_lists.py`) still passes, because the new entry sits outside the "review machinery (...)" list. |

### Whole-phase check outside the accepted class

These areas are unchanged since `eae6d34`:
- readiness: `acceptance-readiness.cjs`. Head/base/merge-base binding, `boundHere`, the untrusted refusal and the single fallback validator are all intact, and every external read fails closed.
- fallback: `codex-fallback.cjs`.
- register: `review-register.cjs`.
- os-scan: `os-scan-gate.cjs` and the pinned, checksum-verified Trivy.
- coverage provenance.
- release permissions: workflow-level `contents: read`, and preflight `actions: read`.
- the Codex runner.
- the acceptance workflow: pinned gate commit, `persist-credentials: false`, read-only permissions.

I found no new fail-open path. No workflow grants `checks: write`. Secret hygiene is unchanged: no secret values appear in the files under review. The iteration-4 IN/SA items stay as recorded.

**Accepted-class, informational (one line each; not findings):**
- `continue-on-error` on "Fail if tests failed" swallows the guard's CI failure (iteration-4 WR-01, accepted).
- Hard-coded `RESULTS` or `TEST_EXIT` gate inputs (iteration-4 WR-02, accepted).
- BASH_ENV/ENV injection through workflow, job or step `env:` (accepted).
- Replacing the `ci-ready` gate step's `run:` with a container action whose entrypoint is a no-op. This is gate-step logic tampering (accepted). The heredoc extraction in `test_ci_gate.py` would also fail.
- The guard's docstring and the policy status line say no required job "can be skipped or neutralised". The accepted class above qualifies that claim (wording only).

## Narrative Findings (AI reviewer)

## Info

### IN-14: The check-name uniqueness scan misses names built from expressions, and the readiness-side half of WR-03 is not recorded in the backlog (new)

**File:** `tests/test_required_jobs_no_skip.py:282-286` (`required_check_name_problems`); `.github/scripts/acceptance-readiness.cjs:124-139` (`latestCheck`, `ciReadyItem`); `.planning/backlog/MAINTENANCE.md` (iteration-4 section)

**Issue:** `jobs.<id>.name` accepts expressions, and the scan compares the raw YAML string. I added mirror workflows on `pull_request` to main with these job names:
- `name: ${{ 'CI ready' }}`;
- `name: "${{ format('CI {0}', 'ready') }}"`;
- a matrix job with `name: ${{ matrix.n }}`, `n: ['CI ready']`.

Each one:
- returns `[]` from `required_check_name_problems`;
- passes `actionlint` (exit 0).

At runtime GitHub evaluates each name to "CI ready". Readiness then takes the highest-id check run named "CI ready" (`latestCheck`), whichever workflow it came from.

This needs a deliberate edit to a workflow file, and every such edit is sensitive-class. It is in the spirit of the owner's stopping rule, so it is graded Info, not Warning.

Separately, round 4 left out the readiness-side half of WR-03, which is binding the "CI ready" check run to the `ci.yml` workflow run. The fix report records that the owner scoped it out. But neither `85-REVIEW-EVIDENCE.md` "Accepted residual risk" nor `MAINTENANCE.md` records it, so the gap is not tracked anywhere.

**Fix:** Either or both:
- **Guard:** for every job in every workflow file, reject a `name:` that contains `${{` when its id or literal text could produce a required check name. The simplest version rejects `${{` in any job `name:` across all workflows, since none use it today.
- **Readiness:** block when more than one check run named "CI ready" exists for the head, or require the check suite's workflow path to be `.github/workflows/ci.yml`.

At minimum, add a line under the "Phase 85 code review iteration 4" heading in `MAINTENANCE.md` recording that the readiness binding was deferred.

### IN-01 to IN-12 (carried, owner-recorded follow-ups, MAINTENANCE.md "Still open after Phase 85")

None of these changed in round 4. They are recorded by owner decision on 2026-10-27:
- IN-01: the OS-scan image-ID wording.
- IN-02: `persist-credentials` on the `os-scan` checkout.
- IN-03: `--repo` on the register reads and writes.
- IN-04: the raw `gh variable set` trace.
- IN-05: the build-time packages (`hatchling`, `uv`).
- IN-06: the hollow-report guard.
- IN-07: the CodeQL fallback match.
- IN-08: the readiness dry run uses HEAD's gate.
- IN-09: hollow nested values in fallback records.
- IN-10: the merge-base is not computed by the fallback CLI (narrowed in round 3).
- IN-11: the readiness prerequisites are not in the docs.
- IN-12: gaps in the reviewer-name denylist.

**Fix:** As recorded in the backlog.

(IN-13 from iteration 4 is fixed and no longer counted.)

## Set aside (needs ruling)

### SA-04 (carried, owner-recorded follow-up): A PR that changes `tests/codex_review_run.py` can certify its own base cross-grade
**Where:** `tests/codex_review_run.py` (`_run_base_grader`); `.github/scripts/acceptance-readiness.cjs:80-98`
**Why excluded:** Recorded by the owner on 2026-10-27. Unchanged.
**Effect if left as is:** For a PR that changes the runner, a "complete" Codex item rests on the changed runner's honesty.
**Needs:** None this round.

### SA-05 (carried, owner-recorded follow-up): The checks do not look inside reusable workflows or local actions
**Where:** `tests/test_required_jobs_no_skip.py:156-157, 178-180`
**Why excluded:** Recorded by the owner. The guard forbids both in required jobs.
**Effect if left as is:** None today.
**Needs:** None this round.

### SA-01 (carried): This PR's acceptance runs on the gate it introduces
**Where:** `.github/workflows/review-acceptance.yml:20-30`
**Why excluded:** It is disclosed in the workflow, and it is a governance choice.
**Effect if left as is:** A defect in the schema-2 gate would also admit this PR.
**Needs:** An owner ruling.

### SA-02 (carried): The register schema cutover strands other open PRs
**Where:** `.github/scripts/review-acceptance.cjs:10-12`; `.github/scripts/review-register.cjs:95-112`
**Why excluded:** It is an operational ordering question.
**Effect if left as is:** In-flight PRs need their dispositions re-entered after migration.
**Needs:** An owner ruling on migration timing.

### SA-03 (carried): The Dependabot `uv` ecosystem has no cooldown
**Where:** `.github/dependabot.yml:23-31`
**Why excluded:** It is a policy choice.
**Effect if left as is:** There is less buffer against a malicious or yanked PyPI release.
**Needs:** An owner ruling.

---

_Reviewed: 2026-10-27T22:19:23Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
_Iteration: 5_
