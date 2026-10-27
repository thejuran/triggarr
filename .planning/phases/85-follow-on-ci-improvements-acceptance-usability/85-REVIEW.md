---
phase: 85-follow-on-ci-improvements-acceptance-usability
reviewed: 2026-10-27T19:51:31Z
reviewed_head: 8bd286c2ddb65232150be1c67cdb2a480b3e710e
diff_base: 091d8ed
iteration: 3
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
  critical: 2
  warning: 2
  info: 12
  total: 16
status: issues_found
---

# Phase 85: Code Review Report (iteration 3)

**Reviewed:** 2026-10-27T19:51:31Z (head `8bd286c2ddb65232150be1c67cdb2a480b3e710e`, diff base `091d8ed`)
**Depth:** standard
**Files Reviewed:** 48 (uv.lock skimmed only)
**Status:** issues_found

## Summary

This is a fresh re-review of the whole phase scope at head `8bd286c`, after fix round 2:
- `75ebe6f`: CR-01, the structural `if` reader;
- `ebdd76c`: WR-01, the merge-base rule;
- `b05ced4`: WR-02, status-file binding;
- `e44b818`: WR-03, the reviewer token denylist.

`ae8e4b2` is the merge of origin/main. `git diff 40ddadf ae8e4b2` is empty, so the merge brings in no content. Since iteration 2, only six files in scope changed: the readiness, skip-detector and fallback scripts and their tests. The other 42 files are unchanged from the iteration-2 review.

Baseline at this head:
- `node --test .github/scripts/*.test.cjs` plus the planchk-router test: 406/406 pass.
- The phase's targeted pytest files (11 files): 421/421 pass.
- `ruff check triggarr/ tests/ .github/scripts/` is clean.
- `actionlint` exits 0.

### Status of the iteration-2 findings

I checked each fix with crafted inputs of my own, not only with the fixer's tests.

| Prior | Verdict | Evidence |
|-------|---------|----------|
| CR-01 step `if` spellings | **Fixed for step and job `if` keys that the detector reaches** | Each of these applied to the real `ci.yml` is reported, either as a specific `if` or as "cannot be parsed": `if : false`, `"if" : false`, `-   if:` (whole step re-indented), a bare `-` followed by `if :`, a single-line or multi-line flow-mapping step, an anchored step (`- &s`), a tagged value (`!!str false`), `if:` placed after a `run: \|` block, `if:` with the value on the next line, an alias step, `? if`, `<<: *x`, and `"i\x66"`. `IF:` (upper case) is not detected, but actionlint rejects it as an unknown key, so it cannot reach GitHub through CI. Both real workflows still return `[]`, so the reader adds no false positives. **However**, two bypasses outside the new reader remain: the `continue-on-error` check (CR-01 below) and `parseJobs`'s job boundaries (CR-02 below). The iteration-2 report itself named the `continue-on-error` regex as the fail-closed model to copy, which was wrong. |
| WR-01 merge-base | **Fixed** | `codexStatusFor` with `reviewedBase` set to the merge-base and `base` set to a newer main tip accepts evidence whose `meta.base` is the merge-base, and rejects evidence whose `meta.base` is `baseRefOid`. A merge-base that is missing or not a SHA fails closed (exit 1). The audited-input diff is recomputed over the same range, `mergeBase..head`. I found no fail-open path: criss-cross merge-bases and a stale local `origin/main` both produce a mismatch, so they block. **Regression:** the fallback path still pins `base` to `baseRefOid` (WR-02 below). |
| WR-02 binding | **Fixed (minimum form)** | A complete `status` or required `baseStatus` whose `inspected_head`/`inspected_base` differ from this head and the reviewed base is blocked. `inspected_head` comes from the Codex report and is checked by the checker against `--expected-head` (`codex_report_status.py:407-429`), so binding to it is meaningful. For the residual, see SA-04. |
| WR-03 denylist | **Fixed for every name listed** | `bm-code-reviewer`, `Claude Code`, `Buildomator`, `codex_review_run.py`, and `bm<U+200B>-code-reviewer` (with a zero-width space) are all rejected. Names that still pass are listed in IN-12. |

### Residual WR-02 gap: is the fixer's description accurate?

The fixer limits the gap to "diffs that change the runner itself". That limit is correct.
- Step 0 of the contract refuses to run unless the checkout's HEAD is the reviewed head, so the runner that executes is always the head's runner.
- `materialize_grader` takes the checker and schema from base-commit git objects. A diff that changes only the checker, the schema or the contract is therefore still cross-graded by code the diff did not write.
- The runner imports only stdlib modules, so no unaudited helper can change its behaviour.

The fixer understates how the gap works. The fix report says "the runner chooses what it passes to that checker". In fact, a changed `tests/codex_review_run.py` controls all three files readiness reads. It can write `.base-status.json` directly, with `inspected_head`/`inspected_base` set to the right SHAs, and never invoke the base checker. The new binding check only compares values that the same runner supplies, so it adds nothing in this case.

The gap stays limited to runner changes, which `docs/review-classification-policy.md:14` already classifies as sensitive. I have recorded it as SA-04 for the owner's ruling, not as a defect.

### New in this iteration

- **CR-01:** `continue-on-error` is still found by one line regex. A quoted or escaped key disables "Fail if tests failed", or the whole `ci-ready` job, with every test, actionlint and Python check still green.
- **CR-02:** `parseJobs` stops reading at any column-0 comment and silently drops job headers it does not recognise. Verified end to end:
  - In `ci.yml`, the `ci-ready` validation step can be skipped.
  - In `review-acceptance.yml`, the gate step can be skipped.
- **WR-01:** the step-`if` allowlist is keyed only by step name. Renaming the browser-suite completeness gate to the allowlisted evidence-upload name, with the same condition, disables the gate undetected.
- **WR-02:** a regression from the WR-01 fix. A fallback record must now name a different base than the Codex evidence it stands in for.

IN-01 to IN-11 and SA-01 to SA-03 are carried forward unchanged and labelled as carried.

## Critical Issues

### CR-01: `continue-on-error` written as a quoted or escaped key is not detected, so "Fail if tests failed" or the whole `ci-ready` job can be neutralised

**File:** `.github/scripts/ci-job-consistency.cjs:702` (also `aggregateCanPassWith`, `:800`)
**Issue:** The check is `job.lines.some(line => /\bcontinue-on-error\s*:/.test(line))`. A quoted key puts the closing quote between the key and the colon, so the regex does not match. A YAML escape removes the literal text altogether. Round 2 moved `if` onto the structural reader but left this regex in place.

I applied each of these to the real `ci.yml`:

| Edit | `findSkipConditions` | actionlint | PyYAML value |
|------|----------------------|------------|--------------|
| `"continue-on-error": true` on "Fail if tests failed" | `[]` | exit 0 | `True` |
| `'continue-on-error': true` on the same step | `[]` | exit 0 | `True` |
| `"continue-on-error": true` on the same step | `[]` | exit 0 | `True` |
| `'continue-on-error': true` at job level on `ci-ready` | `[]` (and `aggregateCanPassWith` returns `false`) | exit 0 | `True` |

With the escaped variant in a full copy of the repo:
- the whole node suite passes (395/395);
- `test_github_workflows.py`, `test_ci_followon_wiring.py` and `test_ci_gate.py` pass (64/64).

The Python substring guards (`test_ci_followon_wiring.py:174, 258`) cover only `os-scan` and `actionlint`, not `test` or `ci-ready`.

Effect: pytest's step exits 0 by design, and "Fail if tests failed" is what turns a failing pytest into a failed job. With that step set to continue on error, the `test` job succeeds whatever pytest returns. With `ci-ready` set to continue on error at job level, "CI ready" reports success even when its validation script exits non-zero. Either way, the release preflight and readiness accept a red build as green. This is the same consequence as iteration-2 CR-01, through a different key.

**Fix:** Check for `continue-on-error` with the reader you already have, not with a line regex. Also add an independent cross-check that uses a real YAML parser.
```js
// in findSkipConditions, after readJobBody(job.lines):
const coeAt = entries => entries.some(e => e.key === 'continue-on-error');
const stepCoe = body.steps.some(s => s.keys && coeAt(s.keys)); // expose all keys from readStepItem
if (coeAt(body.jobKeys) || stepCoe || job.lines.some(l => /continue-on-|\\u|\\x/.test(l) && /:/.test(l))) {
  problems.push(isAggregate ? `aggregate job "${id}" sets continue-on-error` : `required job "${id}" sets continue-on-error`);
}
```
To do that, `readJobBody` must return every key of each step, not only `name` and `if`. Use the same reader in `aggregateCanPassWith`.

Then add a pytest that loads `ci.yml` and `review-acceptance.yml` with `yaml.safe_load` (a real YAML parser). For every required job, it should assert:
- no `continue-on-error` at job or step level;
- no job-level `if`, except `ci-ready: always()`;
- every step `if` is on the allowlist.

That one test removes the whole class of spelling bypasses, because PyYAML decides the key and not a regex. Add regression tests for the four rows above.

### CR-02: `parseJobs` stops at any column-0 comment and silently drops job headers it does not recognise, so the detector never sees the steps or jobs that follow

**File:** `.github/scripts/ci-job-consistency.cjs:43` (`if (/^\S/.test(line)) break;`) and `:45` (`/^  ([A-Za-z0-9_.-]+):\s*$/`)
**Issue:** The new reader only reads the job lines that `parseJobs` gives it, and `parseJobs` has two problems:

1. **Line 43** treats any non-indented line as the start of the next top-level key. A comment at column 0 is legal YAML anywhere, including inside a job's `steps:` list or after a block scalar. Every line after it is dropped from that job, and every later job disappears from the parse.
2. **Line 45** recognises a job header only in the exact form `  id:`. These are all valid YAML for the same job:
   - a header with a trailing comment (`  acceptance: # gate`);
   - a quoted id (`  "acceptance":`);
   - an explicit key (`? acceptance`);
   - a flow-mapping job;
   - the whole `jobs:` block indented 4 spaces.

   An unrecognised header is either merged into the previous job or, before the first job, discarded. When `aggregateJobId` is `null` (review-acceptance.yml), the required jobs are "whatever `parseJobs` found", so a discarded job is simply never checked.

Verified end to end. Each case passes `findSkipConditions` with `[]`, passes the full node suite (395/395), passes actionlint (exit 0), and PyYAML reads the condition:

- **ci.yml, `ci-ready` (the last job).** Insert a column-0 comment after the validation heredoc, then a step-level condition:
  ```yaml
            PY
  # reviewed
          if: github.run_attempt == '0'
  ```
  PyYAML gives `ci-ready.steps[0].if == "github.run_attempt == '0'"`. The pytest workflow files (95 tests) also pass. The "Require every mandatory job to succeed" step is skipped, `ci-ready` succeeds, and "CI ready" is green whatever the needed jobs concluded. The same placement hides `continue-on-error: true`.
- **review-acceptance.yml.** Append `# end of gate` at column 0, then `        if: github.run_attempt == '0'`, after the `script: |` block. The github-script gate step is skipped, and the "Review acceptance" check succeeds without running `assess()` against the dispositions or blockers. Only the environment approval remains.
- **Other variants in review-acceptance.yml.** The header-comment, quoted-id, explicit-key and 4-space-indented-jobs forms also return `[]` with a job-level `if:`. These four happen to turn existing mutation tests red: those tests inject into a job the parser no longer sees. That is a side effect, and the failure messages would be misleading.

When the comment or header sits in a job other than the last in `ci.yml`, the result is "Aggregate job ci-ready not found". That fails closed, but a harmless section-divider comment breaks CI with a confusing error.

**Fix:**
- At `:43`, skip comment lines and end the section only at a real top-level key: `if (/^#/.test(line) || /^\s*$/.test(line)) { if (current) current.lines.push(line); continue; } if (/^\S/.test(line)) break;`
- At `:45`, parse the header with `parseMappingKey(line.slice(2))` when the indent is exactly 2. Then throw (fail closed) for any non-blank, non-comment line at indent 2 or less inside `jobs:` that is not a readable `id:` header with an empty or comment-only value. Do not merge it into a job or drop it.
- Require at least one job, and throw if `jobs:` is not followed by 2-space job keys.
- The PyYAML cross-check in CR-01 also catches this: compare `set(yaml jobs)` with the ids `parseJobs` returns, and fail on any difference.
- Add regression tests for the two end-to-end cases above, plus the header-comment, quoted-id and re-indented forms.

## Warnings

### WR-01: The step-`if` allowlist is keyed by step name only, so renaming the browser-suite completeness gate disables it undetected

**File:** `.github/scripts/ci-job-consistency.cjs:504-509, 727-731`; `.github/workflows/ci.yml:339, 376`
**Issue:** A step condition is allowed when `STEP_IF_ALLOWLIST["<job>::<step name>"]` equals it. Nothing checks:
- that only one step has that name;
- that the step is the evidence upload (`uses: actions/upload-artifact@…`).

Test: in `browser-e2e`, rename "Require a complete browser-suite result" to "Upload browser failure evidence" and give it the allowlisted `failure() && hashFiles(…) != '' && hashFiles(…) != ''` condition. `findSkipConditions` returns `[]`. The completeness gate then runs only after a failure, so a run where every browser test is skipped (pytest exits 0) passes `browser-e2e`. That is exactly what that gate exists to reject.

The same trick on the `test` job ("Upload test evidence" plus `always()`) is harmless, because `always()` still runs the step.

The edit is a visible rename inside a sensitive-class file, so this is a warning rather than a blocker. Still, the allowlist is presented as "the one place a required job may skip a step", and it does not actually pin a specific step.
**Fix:** Key each allowlist entry on more than the name. For example, `{name, condition, uses: 'actions/upload-artifact@<sha>'}`, and require exactly one step per job with that name. Report any allowlisted name that appears more than once in a job. Add a test with the rename described above.

### WR-02: A fallback record must name `baseRefOid` while the Codex evidence it backs must name the merge-base (regression from the WR-01 fix)

**File:** `.github/scripts/codex-fallback.cjs:138-144`; `.github/scripts/acceptance-readiness.cjs:112`
**Issue:** After WR-01, `codexStatusFor` requires `meta.base === mergeBase`. It still passes `base: baseSha` (the PR base) to `validateFallback`, which requires `record.base` and `scope.base` to equal it and states "fallback must review the full base..head diff".

Reproduced with `codexStatusFor` (`reviewedBase: D`, `base: B`, incomplete status, an otherwise valid fallback):
- fallback `base: D` (the merge-base, which is the range actually reviewed) gives `{ok: false, detail: "fallback scope base does not match the PR base"}`;
- fallback `base: B` gives `{ok: true}`.

When `main` has moved past the fork point (the case WR-01 was fixed for), a fallback reviewer who follows the record's own rule reviews `B..H` as a two-dot diff. That compares trees, so it includes `main`'s unrelated changes in reverse. Otherwise the record has to claim a base that was not the reviewed range.

Untrusted heads (Dependabot or fork PRs) always need a fallback, so this path is used routinely.

Before round 2, both checks used `baseRefOid` and agreed. Round 2 made them disagree. IN-10 (the `validate` CLI does not bind `--base`) is the same misalignment seen from the CLI side.
**Fix:** Pass the reviewed base to the validator, `validateFallback(fallback, {pr, head, base: reviewedBase ?? base, …})`. Change the message to "does not match the reviewed base (merge-base)". In the `validate` CLI, compute the merge-base the same way and also bind `meta.base`, which resolves IN-10. Add a test where `baseRefOid` is ahead of the merge-base and the fallback names the merge-base.

## Info

### IN-12: The reviewer-name denylist misses concatenated and model-only names (new)
**File:** `.github/scripts/codex-fallback.cjs:22, 59-67`
**Issue:** Tokens are split on non-alphanumeric characters, so names with no separator, or with only a model name, are accepted. These pass with `kind: other-independent`:
- `BMcodereviewer`, `ClaudeCode`, `codexreviewrun`;
- `Cl<U+0430>ude` (Cyrillic small a), `Claudé`;
- `opus 4 review`, `sonnet`.

The name is self-declared and the owner approves the record, so the effect is limited to a misleading "independent reviewer" label.
**Fix:** Also reject a name when the lowercased name, with separators removed, contains `claude`, `buildomator`, `codexreviewrun` or `bmcode`. Add `opus`, `sonnet`, `haiku` and `anthropic` as tokens. Normalise with NFKD and reject any name that is not ASCII.

### IN-09 (carried): Fallback records still accept hollow nested values
**File:** `.github/scripts/codex-fallback.cjs` (result, findings and `decided_at` checks)
**Issue:** An empty `result.summary`, findings without `id` or `severity`, impossible `decided_at` dates, and a misleading message for `pr: "5"` are all still accepted. Unchanged.
**Fix:** As in iteration 2.

### IN-10 (carried): The `validate` CLI binds the Codex meta to `--head` but not to `--base`
**File:** `.github/scripts/codex-fallback.cjs:258-289`
**Issue:** Unchanged. WR-02 above now widens the same misalignment.
**Fix:** Return `meta.base` and compare it with the reviewed base (see WR-02).

### IN-11 (carried): The acceptance procedure does not document the new readiness prerequisites
**File:** `docs/owner-cli-acceptance.md:15, 19`
**Issue:** Readiness now also runs `git merge-base`. It needs both PR commits fetched and must be run from the repository root. Unchanged.
**Fix:** "Run from the repository root after `git fetch origin main pull/<N>/head`."

### IN-01 (carried): The OS-scan policy claims image-ID verification that the job does not perform
**File:** `docs/os-scan-policy.md` (Scope paragraph) vs the `os-scan` job in `.github/workflows/ci.yml`
**Issue:** The job runs only `sha256sum -c`. Unchanged.
**Fix:** Say "checksum-verified", or add a `docker load` plus image-ID comparison.

### IN-02 (carried): The `os-scan` checkout persists the job token in `.git/config`
**File:** the `os-scan` job's `actions/checkout` step in `.github/workflows/ci.yml`
**Issue:** There is no `persist-credentials: false`, while Trivy runs in that workspace. Unchanged.
**Fix:** Add `with: { persist-credentials: false }`.

### IN-03 (carried): Register reads and writes depend on the current directory's repository
**File:** `.github/scripts/acceptance-readiness.cjs:386-387`; `.github/scripts/review-register.cjs:167, 176`
**Issue:** `gh variable get/set` run without `--repo REPO`. Unchanged.
**Fix:** Pass `'--repo', REPO`.

### IN-04 (carried): `review-register.cjs` lets a failed `gh variable set` escape as a raw stack trace
**File:** `.github/scripts/review-register.cjs:212, 256`
**Issue:** Unchanged.
**Fix:** Wrap the `writeRegister` calls the same way the `readRegister` calls are wrapped.

### IN-05 (carried): Build-time packages outside the locked set
**File:** `Dockerfile:16, 33, 55`
**Issue:** An unpinned `hatchling` is used under build isolation, and `uv==0.12.17` is installed without a hash. Unchanged.
**Fix:** Use `--no-build-isolation` with a hash-pinned `hatchling`, or document this as an accepted risk.

### IN-06 (carried): The hollow-report guard is easy to sidestep
**File:** `tests/codex_report_status.py` (`TRIVIAL_COMMANDS`)
**Issue:** A report that ran only `ls` passes the guard. Unchanged.
**Fix:** Require a recorded command naming the reviewed range, or soften the docstring.

### IN-07 (carried): The CodeQL readiness fallback match is unlikely to fire
**File:** `.github/scripts/acceptance-readiness.cjs:140-150`
**Issue:** It filters on the `github-advanced-security` app slug and takes only the newest run. Unchanged.
**Fix:** Require every matching analysis run to succeed, and match on the app that actually posts them.

### IN-08 (carried): The readiness dry run uses HEAD's gate, not the pinned gate the job runs
**File:** `.github/scripts/acceptance-readiness.cjs:11`; `.github/workflows/review-acceptance.yml:28`
**Issue:** Unchanged.
**Fix:** Load the gate from the pinned blob, or test that the pinned blob equals HEAD's.

## Set aside (needs ruling)

### SA-04: Residual of WR-02, where a diff that changes `tests/codex_review_run.py` can certify its own base cross-grade (new; the fixer asked for a ruling)
**Where:** `tests/codex_review_run.py:943-985` (`_run_base_grader`) and Invocation step 0 in the contract; `.github/scripts/acceptance-readiness.cjs:73-82`
**Why excluded:** The fixer stated this residual and deferred it to the owner. My assessment of the fixer's description is in the Summary: the scope is correct (runner changes only), but the mechanism is understated. A changed runner can write a bound "complete" `.base-status.json` directly, without running the base checker, and the binding check cannot detect that.
**Effect if left as is:** For a PR that changes the Codex runner, a "complete" Codex item in readiness rests on the changed runner's own honesty. CI and owner acceptance are unaffected, and runner changes are already sensitive-class.
**Needs:** An owner ruling.
- (a) Accept, with the classification policy as the control. If so, have readiness print "Codex runner changed in this diff: base cross-grade is self-reported" so the owner sees it at acceptance.
- (b) Have readiness re-grade `<OUT>.last.json` with the base commit's checker itself.

### SA-05: Detector scope ends at this file (new)
**Where:** `.github/scripts/ci-job-consistency.cjs` (`findSkipConditions`)
**Why excluded:** This is a design boundary, not a defect in the code as written.
**Effect if left as is:** A required job or step that calls a reusable workflow (job-level `uses:`) or a local composite action (`uses: ./.github/actions/…`) can hold step conditions or `continue-on-error` the detector never reads. Today, no required job does this.
**Needs:** An owner ruling.
- Either forbid job-level `uses:` and local `./` actions in required jobs (one more fail-closed check),
- or accept the boundary and say so in `docs/review-classification-policy.md`.

### SA-01 (carried): This PR's acceptance runs on the gate it introduces
**Where:** `.github/workflows/review-acceptance.yml:23-28`
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

_Reviewed: 2026-10-27T19:51:31Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
_Iteration: 3_
