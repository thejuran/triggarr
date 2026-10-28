---
phase: 85-follow-on-ci-improvements-acceptance-usability
reviewed: 2026-10-27T19:27:45Z
reviewed_head: 252fe61410b776d1ff170047ab172f26555ce361
diff_base: 091d8ed
iteration: 2
depth: standard
files_reviewed: 48
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
  - uv.lock
findings:
  critical: 1
  warning: 3
  info: 11
  total: 15
status: issues_found
---

# Phase 85: Code Review Report (iteration 2)

**Reviewed:** 2026-10-27T19:27:45Z (head `252fe61410b776d1ff170047ab172f26555ce361`, diff base `091d8ed`)
**Depth:** standard
**Files Reviewed:** 48 (uv.lock skimmed only)
**Status:** issues_found

## Summary

This is a re-review after the fix round. It covers the whole phase scope at head `252fe61`, and looks hardest at the six fix commits `fb01095..e89c534`.

Baseline at this head:
- `node --test .github/scripts/*.test.cjs` plus the planchk-router test: 356/356 pass.
- The phase's targeted pytest files (runner, report status, wiring, acceptance docs, machinery lists): 322/322 pass.
- `ruff check triggarr/ tests/ .github/scripts/` is clean.

### Status of the iteration-1 findings

I checked each fix with crafted inputs, not only with the fixer's own tests.

| Prior | Verdict | Evidence |
|-------|---------|----------|
| CR-01 fallback validator | **Fixed** | The iteration-1 reproduction (empty sub-objects, `pr: 999`) now returns 13 reasons, including "fallback is for a different PR" and "owner_decision.decision must be approve-fallback". `decision: 'nope'` is rejected. Residual gaps are in WR-03 and IN-09. |
| CR-02 skip detector `- if:` | **Partially fixed. Still bypassable (see CR-01 below)** | `- if: false` is now reported. `if : false`, `-   if: false`, and a flow-mapping step `- {name: …, if: …}` applied to the real `ci.yml` still return `[]`. |
| WR-01 readiness trusts runner meta | **Fixed as specified, with a regression and a residual** | A meta that claims no audited change is now overridden by the recomputed `git diff`, and a missing `meta.head` blocks. However, the now-mandatory `meta.base === baseRefOid` rejects valid local-checkpoint evidence (WR-01 below), and the status files are still not bound to the head (WR-02 below). |
| WR-02 fallback not bound to its Codex output | **Fixed** | A record naming `…-a2` checked against a codexStatus for `…-a3` is rejected. The `validate` CLI exits 1 with "Codex output is for a different head" when meta names another head. |
| WR-03 empty `--test-exit` | **Fixed** | `intArg` accepts only `^\d+$`. The CI producer (`ci.yml:56-57`) always emits integers, so valid runs are not over-rejected. |
| WR-04 signal outside the Codex step | **Fixed** | `execute()` now has an `except BaseException` branch that writes a stub only if `.status.json` is missing, then re-raises unchanged. The guard test confirms that a base-grader interrupt does not overwrite the head status. The documented residual window (between `reserve_outputs` and the `try`) is acceptable. |

### New in this iteration

- **CR-01:** the CR-02 fix closed only one YAML spelling. Three other valid spellings still let a step-level condition disable "Fail if tests failed" without being detected, and actionlint does not catch a non-constant always-false condition.
- **WR-01:** a regression from the WR-01 fix that blocks this phase's own acceptance path.
- **WR-02:** the remaining self-certification gap in readiness.
- **WR-03:** a gap in the fallback reviewer denylist that the first pass missed.

IN-01 to IN-08 and SA-01 to SA-03 are carried forward unchanged, by owner decision, and are labelled as carried.

## Critical Issues

### CR-01: The skip-condition detector (ACCEPT-03) still misses step `if:` written as `if :`, with extra spaces after the dash, or in a flow mapping (the CR-02 fix is incomplete)

**File:** `.github/scripts/ci-job-consistency.cjs:345-379` (`extractStepIfs`)
**Issue:** The fix widened the match to `^(?:      - |        )(?:if|"if"|'if'):`. That still requires:
- exactly one space after `-`;
- the colon immediately after the key;
- a block-mapping step.

All three of these are valid YAML for the same `if` key. PyYAML parses each to `{'if': False, …}`:

```yaml
      - name: Fail if tests failed
        if : false                 # space before the colon
      -   if: false                # extra spaces after the dash
          name: Fail if tests failed
      - {name: Fail if tests failed, if: false, run: exit 1}   # flow mapping
```

I applied each edit to the real `.github/workflows/ci.yml` (`test` job, "Fail if tests failed") and ran `findSkipConditions({workflowText, aggregateJobId: 'ci-ready', triggerContract: TRIGGER_CONTRACTS['ci.yml']})`:

| Variant | Result |
|---------|--------|
| `- if: false` (the fixed case) | reported |
| `if : false` | `[]` |
| `-   if: false` (re-indented step) | `[]` |
| flow-mapping step | `[]` |

actionlint does not cover the gap. It flags only the constant `false`. With a non-constant always-false condition such as `if : github.run_attempt == '0'` (or the same condition in a flow mapping), actionlint exits 0.

The pytest step `exit 0`s by design and relies on "Fail if tests failed". With that step disabled, the `test` job passes whatever pytest returns, `CI ready` goes green, and the release preflight accepts the run. This is the same consequence as the iteration-1 BLOCKER. Only the spelling differs.

The same parser is used for `review-acceptance.yml` (`aggregateJobId: null`), so that workflow is exposed in the same way.

**Fix:** Stop matching `if` as one exact spelling. Fail closed on any `if` key inside a required job's step region, the way `continue-on-error` is already handled (`/\bcontinue-on-error\s*:/` on every line). For example:
- Treat any line in the job's `steps:` region that matches `/(^|[\s{,])["']?if["']?\s*:/` as a condition.
- Treat any step-start line that is not `^      - (name|uses|run|id|env|with|shell|working-directory|timeout-minutes|if)\b` (that is, a flow mapping `- {`, an alias `- *`, or irregular indentation) as an unparseable step, and report it.

Add regression tests for `if :`, `-   if:`, `- {…, if: …}`, and `- *alias`, run against both real workflows.

## Warnings

### WR-01: Mandatory `meta.base === baseRefOid` rejects valid local-checkpoint Codex evidence, including this phase's own (regression from the WR-01 fix)

**File:** `.github/scripts/acceptance-readiness.cjs:54-56` and `382` (two-dot recompute)
**Issue:** Readiness now blocks with "Codex evidence is for a different base" unless `meta.base` equals the PR's current `baseRefOid`, the tip of `main`. The contract (`docs/codex-adversarial-review-contract.md`, Invocation step 1) tells the operator to use `BASE_SHA = git merge-base origin/main HEAD` for a phase-scope local checkpoint. The project workflow runs that local pass before the end-of-phase push, so that is the evidence normally presented at acceptance.

This repo merges with merge commits, so `main`'s tip moves to a new merge commit whenever any PR lands. It does not match a branch's merge-base unless the branch was cut from that exact tip.

Concrete case: this branch. `git merge-base origin/main HEAD` is `b07e532` (the phase-83 tip). `origin/main` is `decd5f1` (the PR #35 merge commit). Both have identical trees. When this phase's PR is opened against `decd5f1`:
- The post-fix Codex pass that CLAUDE.md requires, run as a local checkpoint per the contract, records `base: b07e532`, so readiness reports BLOCKED.
- The PR form of the runner cannot fix this either. `verify_trust` refuses because `decd5f1` is not an ancestor of the head (`codex_review_run.py:513-518`).

The only way through is to merge `main` into the branch. That creates a new head and invalidates the BM review, the Codex review, CI, and any vibe-check. The check fails closed, but it rejects correct evidence for a review whose scope (merge-base..head) is exactly right.

There is a second problem. The recompute at line 382 uses a two-dot `git diff ${base}..${head}` against `baseRefOid`. When `main` has moved, that compares trees, so audited inputs changed on `main` (not in this PR) are counted as changed in this PR. That demands a base cross-grade the runner never performed.

**Fix:**
- Accept `meta.base` when it equals `baseRefOid` or `git merge-base <baseRefOid> <head>`, computed by readiness with an argument array.
- Compute the audited-input set over the same range the evidence covers: `git diff --name-only <meta.base>..<head>` once `meta.base` is verified to be one of those two values, or `<baseRefOid>...<head>` (three dots).
- Show both SHAs in the checklist ("Full base SHA" vs "Reviewed base SHA").
- Add a test where `baseRefOid` is a merge commit ahead of the branch's merge-base.

### WR-02: Readiness still accepts status files that are not bound to this head or base, and that the reviewed runner wrote itself (residual of iteration-1 WR-01)

**File:** `.github/scripts/acceptance-readiness.cjs:60-61`; `tests/codex_review_run.py:1165-1196, 946-984`
**Issue:** Readiness now forces a base cross-grade whenever an audited input changed. It then accepts that cross-grade on `baseStatus?.status === 'complete'` alone. It never compares `status.inspected_head` / `inspected_base`, or `baseStatus.inspected_head` / `inspected_base`, with the PR head and base, even though the checker emits those fields (`codex_report_status.py:537-539`).

Reproduced with `codexStatusFor`:
- `meta` correct for head `H` / base `B`;
- recomputed audited change `['tests/codex_review_run.py']`;
- `status` and `baseStatus` both `{status: 'complete', inspected_head: O, inspected_base: O}` for an unrelated commit `O`.

Result: `{ok: true, detail: 'complete'}`.

The deeper problem is that when `tests/codex_review_run.py` itself changes, `.base-status.json` is still written by the changed runner (`_run_base_grader` runs inside the head's harness and passes it the head's `checker_tail`). So the recompute forces a file to exist, but the code under review writes that file. D-18's goal ("the grader cannot self-certify") still does not hold for a runner change.

**Fix:**
- Minimum: require `status.inspected_head === head && status.inspected_base === meta.base`, and the same for `baseStatus` whenever a base grade is required.
- Stronger: when the recomputed set is non-empty, readiness itself materializes `git show <base>:tests/codex_report_status.py` and the schema into a temp dir, re-grades `<OUT>.last.json` with `--expected-head/--expected-base`, and ignores `.base-status.json`.

### WR-03: The fallback reviewer denylist does not include BM's own reviewer agent or common Claude names

**File:** `.github/scripts/codex-fallback.cjs:17, 92-97`
**Issue:** `DISALLOWED_REVIEWERS` is an exact-match list: `bm`, `bm code review`, `buildomator`, `claude`, `gsd-code-reviewer`, `codex_review_run`. BM's reviewer agent in this project is `bm-code-reviewer`, which is the name this report is signed with. It is not on the list.

Probed with a record whose other fields are all valid:
- `reviewer: {name: 'bm-code-reviewer', kind: 'other-independent'}` returns `ok: true`;
- `reviewer: {name: 'Claude Code', …}` returns `ok: true`.

The contract says BM and Claude are not independent fallback reviewers. A fallback by the same agent that did the BM review would therefore satisfy the Codex prerequisite in readiness. Owner approval is still required. However, the validator's "independent reviewer" claim is what the owner is shown, and here it is false.

This was missed in iteration 1.

**Fix:** Normalize the name (lowercase, collapse `[-_\s]+` to one space) and reject any name containing the tokens `bm`, `buildomator`, `gsd`, `claude`, or `codex_review_run`, rather than requiring an exact match. Add `bm-code-reviewer` and `claude code` cases to the tests.

## Info

### IN-09: Fallback records still accept hollow nested values (new)
**File:** `.github/scripts/codex-fallback.cjs:136-155, 175-177, 79-81`
**Issue:** After the CR-01 fix, these fields are required to exist but are not checked for content:
- `result.summary` may be `""`.
- A finding may lack `id` and `severity`; only `disposition` is checked, and the message then reads `finding undefined has no disposition`.
- `decided_at` passes the regex with impossible values such as `2026-13-45T99:99:99Z`.
- A string `pr: "5"` is rejected with the misleading message "fallback is for a different PR".

**Fix:** Require a non-blank `summary`; require `id` and `severity` on each finding; check `decided_at` with `!Number.isNaN(Date.parse(v))` plus a round-trip; report a non-integer `pr` as a type error.

### IN-10: The `validate` CLI binds the Codex meta to `--head` but not to `--base` (new)
**File:** `.github/scripts/codex-fallback.cjs:268-274, 370-373`
**Issue:** WR-02's fix returns `meta.head` and checks it, but `codexStatusFromOutput` does not return `meta.base`, so the CLI never compares it with `--base`. Readiness does compare them. The two entry points now disagree on what counts as matching Codex evidence.
**Fix:** Return `base: meta.base` and reject when it differs from `--base`, consistent with however WR-01 above is resolved.

### IN-11: The acceptance procedure does not document the new readiness prerequisites (new)
**File:** `docs/owner-cli-acceptance.md:15, 19`
**Issue:** Readiness now:
- shells out to `git diff`, so it needs the PR base and head fetched locally;
- must be run from the repo root, because the pathspecs and `--codex-out` are relative to the working directory;
- fails with "could not compute audited-input changes" or "Codex evidence is for a different base".

The fix report acknowledges that the doc was intentionally left unchanged. The owner sees these messages at acceptance time with no procedure to follow.
**Fix:** Add one sentence to step 1: "Run from the repository root after `git fetch origin main pull/<N>/head`."

### IN-01 (carried): The OS-scan policy claims image-ID verification that the job does not perform
**File:** `docs/os-scan-policy.md` (Scope paragraph) vs `.github/workflows/ci.yml:405-407`
**Issue:** The job runs `sha256sum -c` only. The doc says it verifies the checksum and the image ID. Unchanged.
**Fix:** Say "checksum-verified", or add a `docker load` plus image-ID comparison.

### IN-02 (carried): The `os-scan` checkout persists the job token in `.git/config`
**File:** `.github/workflows/ci.yml:398`
**Issue:** There is no `persist-credentials: false`, while a third-party binary (Trivy) runs in that workspace. Unchanged.
**Fix:** Add `with: { persist-credentials: false }`.

### IN-03 (carried): Register reads and writes depend on the current directory's repository
**File:** `.github/scripts/acceptance-readiness.cjs:356-357`; `.github/scripts/review-register.cjs:167, 176`
**Issue:** `gh variable get/set` run without `--repo REPO`. Unchanged (the line numbers moved).
**Fix:** Pass `'--repo', REPO`.

### IN-04 (carried): `review-register.cjs` lets a failed `gh variable set` escape as a raw stack trace
**File:** `.github/scripts/review-register.cjs:212, 256`
**Issue:** The `writeRegister` calls are not wrapped in a try/catch. Unchanged.
**Fix:** Wrap them the same way the `readRegister` calls are wrapped.

### IN-05 (carried): Build-time packages outside the locked set
**File:** `Dockerfile:16, 33, 55`
**Issue:** The build uses an unpinned `hatchling` under build isolation, and `uv==0.12.17` is installed without a hash. Unchanged.
**Fix:** Use `--no-build-isolation` with a hash-pinned `hatchling`, or document this as an accepted risk.

### IN-06 (carried): The hollow-report guard is easy to sidestep
**File:** `tests/codex_report_status.py` (`TRIVIAL_COMMANDS`)
**Issue:** A report that ran only `ls` passes the guard. Unchanged.
**Fix:** Require a recorded command naming the reviewed range, or soften the docstring.

### IN-07 (carried): The CodeQL readiness fallback match is unlikely to fire
**File:** `.github/scripts/acceptance-readiness.cjs:113-124`
**Issue:** The fallback filters on the `github-advanced-security` app slug and takes only the single newest run. Unchanged.
**Fix:** Require every matching analysis run to succeed, and match on the app that actually posts them.

### IN-08 (carried): The readiness dry run uses HEAD's gate, not the pinned gate the job runs
**File:** `.github/scripts/acceptance-readiness.cjs:11`; `.github/workflows/review-acceptance.yml:28`
**Issue:** Readiness loads the local `review-acceptance.cjs`, while the job runs the pin `8df9eaf…`. Unchanged.
**Fix:** Load the gate from the pinned blob, or test that the pinned blob equals HEAD's.

## Set aside (needs ruling)

### SA-01 (carried): This PR's acceptance runs on the gate it introduces
**Where:** `.github/workflows/review-acceptance.yml:23-28`
**Why excluded:** It is disclosed in the workflow, and it is a governance choice.
**Effect if left as is:** A defect in the schema-2 gate would also admit this PR.
**Needs:** An owner ruling: accept as disclosed, or require the independent pass to clear `review-acceptance.cjs` explicitly.

### SA-02 (carried): The register schema cutover strands other open PRs
**Where:** `.github/scripts/review-acceptance.cjs:10-12`; `.github/scripts/review-register.cjs:95-112`
**Why excluded:** It is an operational ordering question.
**Effect if left as is:** In-flight PRs need their dispositions re-entered after migration. (`gh pr list` shows no open PRs today.)
**Needs:** An owner ruling on migration timing.

### SA-03 (carried): The Dependabot `uv` ecosystem has no cooldown
**Where:** `.github/dependabot.yml:23-31`
**Why excluded:** It is a policy choice.
**Effect if left as is:** There is less buffer against a malicious or yanked PyPI release than for actions/docker.
**Needs:** An owner ruling: add a `cooldown`, or accept as is.

---

_Reviewed: 2026-10-27T19:27:45Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
_Iteration: 2_
