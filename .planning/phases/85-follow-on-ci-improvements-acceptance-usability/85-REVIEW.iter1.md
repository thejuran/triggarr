---
phase: 85-follow-on-ci-improvements-acceptance-usability
reviewed: 2026-10-27T00:00:00Z
reviewed_head: b4a47b6c575447d6bffde778d0e00ba51f0b2613
diff_base: 091d8ed
depth: standard
files_reviewed: 47
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
  warning: 4
  info: 8
  total: 14
status: issues_found
---

# Phase 85: Code Review Report

**Reviewed:** 2026-10-27 (head `b4a47b6c575447d6bffde778d0e00ba51f0b2613`, diff base `091d8ed`)
**Depth:** standard
**Files Reviewed:** 47 (uv.lock skimmed only)
**Status:** issues_found

## Summary

I reviewed the Phase 85 CI follow-on and acceptance-usability changes: the keyed acceptance register and draft check, the release least-privilege split, the Docker lockfile install and image/lock consistency check, the Trivy OS-scan gate, coverage provenance, the skip-condition detector, the Codex fallback validator, the readiness CLI, and the Codex runner's trust and signal handling.

Baseline checks pass at this head. `node --test .github/scripts/*.test.cjs` passed 315/315. The phase's pytest files passed 416/416. `ruff check triggarr/ tests/ .github/scripts/` is clean. The BM convention checker returned no findings.

Several parts hold up under probing:
- **Acceptance gate:** it uses `Object.hasOwn` slice lookups, retires schema 1 explicitly, and rejects drafts. Its pinned commit `8df9eaf` holds the same `review-acceptance.cjs` as HEAD, and that commit will reach main because the repo uses merge commits.
- **Release workflow:** only the tag-only `github-release` job holds `contents: write`.
- **Docker image:** it installs the hash-checked locked export with `--no-deps`.
- **OS-scan gate:** it fails closed on a hollow or malformed report and on a bad exceptions file.

Two controls this phase was meant to deliver fail open when probed with concrete inputs:
1. **Fallback validator (CR-01):** `codex-fallback.cjs` accepts a record with an empty `owner_decision`, `result`, `reviewer` and `scope`, and with a different PR number. The contract says only an explicit `approve-fallback` that names the head may satisfy the Codex prerequisite.
2. **Skip detector (CR-02):** the ACCEPT-03 detector misses a step-level `if:` written as the first key of a step (`- if: false`). That is a common YAML form, and with it the test job's "Fail if tests failed" step can be silently disabled while every check stays green.

The warnings cover the remaining gaps:
- **WR-01:** the readiness CLI trusts metadata written by the head's own runner.
- **WR-02:** the fallback is not bound to the Codex output it was checked against.
- **WR-03:** an empty `--test-exit` is recorded as a passing test run.
- **WR-04:** a termination signal outside the Codex step leaves a reserved attempt with no status file.

## Critical Issues

### CR-01: Fallback validator accepts a record with no owner approval, no reviewer, no result, and the wrong PR

**File:** `.github/scripts/codex-fallback.cjs:53-158`
**Issue:** `validateFallback` only checks that the nine top-level keys exist. It never requires the nested fields, so:
- `owner_decision.decision` only fails when it equals `wait` or `retry-later`. A missing decision, or any other string such as `"nope"`, passes.
- `owner_decision.verbatim`, `owner_decision.decided_at`, `result.status`, `reviewer.name`, `reviewer.kind` and `scope.diff` are each checked only `if (Object.hasOwn(...))`. If a field is absent, it is not checked at all.
- `context.pr` is never destructured (line 54), and `record.pr` is never compared with it.
- `result.findings` entries that are not objects are skipped with `continue` instead of rejected.

Reproduced at HEAD: the record `{schema:1, pr:999, head:H, base:B, codex_out:'.planning/phases/x/codex/<H12>-r-a2', reviewer:{}, scope:{}, result:{}, owner_decision:{}}` validated against PR 5 with a trusted head at attempt 2 returns `{ok: true, reasons: []}`. The same record with `owner_decision: {decision: 'nope'}` also returns `ok: true`.

The file header (lines 5-8) and `docs/codex-adversarial-review-contract.md:118` both state that only `approve-fallback`, with verbatim words naming the head, satisfies the prerequisite. `acceptance-readiness.cjs:68` relies on this function to turn the Codex line to "ok". So an incomplete or fabricated fallback record makes the readiness checklist report "Ready to request approval" while Codex never completed and the owner never approved a fallback. The tests (`codex-fallback.test.cjs:186-216`) only mutate a fully valid record, so this path is never exercised.

**Fix:** Require the nested fields and allowlist the decision. Compare the PR.
```js
const {pr, head, base, prAuthor, headTrust, codexStatus} = context;
if (Object.hasOwn(record, 'pr') && record.pr !== pr) reasons.push('fallback is for a different PR');

const requireFields = (obj, fields, prefix) => {
  for (const f of fields) if (!isPlainObject(obj) || !Object.hasOwn(obj, f)) reasons.push(`missing required field ${prefix}.${f}`);
};
requireFields(record.reviewer, REVIEWER_FIELDS, 'reviewer');
requireFields(record.scope, SCOPE_FIELDS, 'scope');
requireFields(record.result, RESULT_FIELDS, 'result');
requireFields(record.owner_decision, OWNER_DECISION_FIELDS, 'owner_decision');

if (record.owner_decision?.decision !== 'approve-fallback') {
  // keep the specific wait / retry-later messages, else:
  reasons.push('owner_decision.decision must be approve-fallback');
}
if (typeof record.reviewer?.name !== 'string' || !record.reviewer.name.trim()) reasons.push('reviewer.name is required');
if (!Array.isArray(record.result?.findings)) reasons.push('result.findings must be an array');
// and reject non-object findings instead of `continue`
```
Add negative tests that start from `{}` sub-objects and from a wrong `pr`, not only from mutations of the valid fixture.

### CR-02: Skip-condition detector (ACCEPT-03) misses `- if:` as the first key of a step

**File:** `.github/scripts/ci-job-consistency.cjs:339-372`
**Issue:** `extractStepIfs` treats any `^      - ` line as a step start. It then looks for `if:` only on 8-space lines (`/^        if:/`, line 356). When a step is written with `if:` as its first key, the condition sits on the step-start line itself and is never captured:
```yaml
      - if: false
        name: Fail if tests failed
```
I reproduced this by applying that edit to the real `ci.yml`. `findSkipConditions({workflowText, aggregateJobId: 'ci-ready', triggerContract: TRIGGER_CONTRACTS['ci.yml']})` returns `[]`, while the equivalent 8-space form is correctly reported. With that edit, the `test` job passes whatever pytest returns, because the pytest step itself `exit 0`s and relies on this later step. `CI ready` then goes green and the release preflight accepts the run.

This detector is the phase's mechanism for "no skip condition may let a required check pass" (D-01/D-02). The same blind spot applies to `- continue-on-error:` only by luck: that check scans every line with `\bcontinue-on-error\s*:`, so the `if` path is the exposed one.
**Fix:** Match `if:` on the step-start line too, and fail closed on unparseable step keys:
```js
const ifMatch = line.match(/^        if:\s*(.+?)\s*$/) || line.match(/^      - if:\s*(.+?)\s*$/);
```
Apply the same handling to the folded-block continuation indent (`^          `) and to `name:`. Add regression tests for `- if: false`, `- if: >-` and `- if: ${{ false }}` against the real `ci.yml` and `review-acceptance.yml`.

## Warnings

### WR-01: Readiness trusts the reviewed head's own runner output to decide whether base cross-grading was needed

**File:** `.github/scripts/acceptance-readiness.cjs:37-56` (also `.github/scripts/codex-fallback.cjs:215-227`)
**Issue:** `codexStatusFor` reports Codex "complete" when `meta.review_mode === 'trusted-local-tests'`, `status.status === 'complete'`, and `meta.audited_inputs_changed_in_diff` is empty. All three values are written by `tests/codex_review_run.py` and `tests/codex_report_status.py` as they exist at the reviewed head, which is the checkout the runner executes from (`HARNESS_ROOT`). A diff that changes the runner can therefore record `audited_inputs_changed_in_diff: []` and skip the base cross-grade, and readiness accepts it.

D-18 exists to make the grader unable to self-certify. The head binding is also optional: line 38 compares `meta.head` with the head only `if Object.hasOwn(meta, 'head')`, so a meta file without `head` skips the check. The trust model limits who can author such a diff, but the main risk here is an agent-authored change weakening the grader without anyone noticing.
**Fix:** In `runCli`, recompute the audited-input change set yourself with `git diff --name-only <base>..<head> -- <AUDITED_INPUTS>` (argument array, no shell). Require a `complete` `.base-status.json` whenever that set is non-empty, whatever `meta` says. Make `meta.head === head` (and `meta.base === base`) mandatory rather than conditional.

### WR-02: A fallback record is never bound to the Codex output it is validated against

**File:** `.github/scripts/codex-fallback.cjs:164-189, 322-337`; `.github/scripts/acceptance-readiness.cjs:59-68`
**Issue:** `codexOutMatchesHead` checks only that `record.codex_out`'s basename starts with the head prefix. It never compares `record.codex_out` with `codexStatus.out`, meaning the `--codex-out` whose `.meta.json`/`.status.json` were actually read to get `attempt` and `reviewMode`.

In the `validate` CLI, `meta.head` is never compared with `--head` at all. Attempt 2 of a different head's Codex run, or a later complete attempt, can therefore supply the "attempt ≥ 2 and incomplete" evidence for a fallback whose `codex_out` string merely names the right head. Readiness passes `out` in `codexStatus`, but `validateFallback` ignores it.
**Fix:** Add `if (record.codex_out !== codexStatus?.out) reasons.push('fallback codex_out does not match the Codex output checked')`. In `codexStatusFromOutput`, return `meta.head` and reject when it differs from `--head`.

### WR-03: Empty `--test-exit` is recorded as a passing test run

**File:** `.github/scripts/coverage-provenance.cjs:269, 290`
**Issue:** `Number(requireArg(args, 'test-exit'))` turns `''` into `0`. `requireArg` only rejects `undefined` or a bare flag. The CI step passes `--test-exit "$TEST_EXIT"` from `steps.pytest.outputs.test_exit`, which is empty if that output was never written (for example, the step was edited or its output name drifted).

Reproduced: `runCli(['write', ..., '--test-exit', '', '--test-seconds', '', ...])` exits 0 and writes `test_exit_code: 0`. `checkEvidence` then accepts the report as evidence from a passing run. The CI job still fails through "Fail if tests failed" (`"" != "0"`), but the uploaded provenance file says the tests passed, and that file is what vibe-check consumes.
**Fix:** Parse strictly and fail closed:
```js
function intArg(args, name) {
  const raw = requireArg(args, name);
  if (!/^\d+$/.test(raw)) throw new Error(`--${name} must be a non-negative integer, got ${JSON.stringify(raw)}`);
  return Number(raw);
}
```

### WR-04: A termination signal outside the Codex step leaves a reserved attempt with no status file

**File:** `tests/codex_review_run.py:1076-1133` (`execute` / `_execute_reserved`), `186-191` (`_handle_termination_signal`)
**Issue:** The signal handler raises `SystemExit`, which is a `BaseException`. Only the Codex step is wrapped in `try/finally: _finalize_raw_outputs(...)`, and only that function writes a status stub for a `SystemExit`. If SIGTERM or SIGHUP (or Ctrl-C, which raises `KeyboardInterrupt`) arrives at another point, nothing records a status, because `except RunnerError` and `except Exception` in both functions do not catch it. Those points are:
- during the up-to-30-minute pytest run (`_run_pytest`, line 1111);
- during `git worktree add`;
- after the reservation but before the scratch directory exists;
- during the base grader.

The attempt is left with `.prompt.txt` and `.meta.json` but no `.status.json`, which contradicts the `execute` comment "never leave it without a status". The effect still fails closed, because readiness errors with "could not read Codex status file". It also blocks the fallback path: `codexStatusFromOutput` throws for that attempt, so the operator must burn another attempt and cannot record the interrupted one as the incomplete attempt the fallback rule needs.
**Fix:** In `execute`, catch `BaseException` after `reserve_outputs`. Write a stub that names `_RECEIVED_SIGNAL`, or `KeyboardInterrupt`, if `.status.json` does not exist yet, then re-raise. Alternatively, move the "status must exist" guarantee into one outer `try/finally` that covers the whole reserved section.

## Info

### IN-01: OS-scan policy claims image-ID verification that the job does not do
**File:** `docs/os-scan-policy.md` (Scope paragraph) vs `.github/workflows/ci.yml:405-407`
**Issue:** The policy says the image is "scanned only after its checksum and image ID are verified". The `os-scan` job runs `sha256sum -c` only. The checksum is sufficient, because Trivy scans the same tar, but the document overstates what the job checks.
**Fix:** Change the doc to "checksum-verified", or add a `docker load` + image-ID comparison step like the one in `image-smoke`.

### IN-02: `os-scan` checkout persists the job token in `.git/config`
**File:** `.github/workflows/ci.yml:398`
**Issue:** The new `actionlint` and `secrets` jobs set `persist-credentials: false`, but `os-scan` does not, even though it runs a third-party binary (Trivy) in the same workspace. The token is read-only, so the impact is low.
**Fix:** Add `with: { persist-credentials: false }` to the `os-scan` checkout.

### IN-03: Register reads and writes depend on the current directory's repository
**File:** `.github/scripts/acceptance-readiness.cjs:339-340`; `.github/scripts/review-register.cjs:167, 176`
**Issue:** `gh variable get/set` run without `--repo`, while every other call in these scripts pins `REPO = 'thejuran/triggarr'`. If either script runs from a fork clone or a different remote default, it reads or overwrites another repository's variables.
**Fix:** Pass `'--repo', REPO` on every `gh variable` call.

### IN-04: `review-register.cjs` lets a failed `gh variable set` escape as a raw stack trace
**File:** `.github/scripts/review-register.cjs:212, 256`
**Issue:** `writeRegister` is the only `gh` call in the CLI without a try/catch. A failure (auth, network, or size limit) throws out of `runCli` with a Node stack trace instead of the plain message and exit code 1 that every other path uses.
**Fix:** Wrap it the same way `readRegister` calls are wrapped.

### IN-05: Build-time packages outside the locked set
**File:** `Dockerfile:16, 33, 55`
**Issue:** The final stage's `pip install --no-deps .` uses build isolation, which fetches an unpinned `hatchling` from PyPI and runs it during the image build. The `deps` stage installs `uv==0.12.17` without a hash. None of this ships in the image, and the image/lock consistency check proves what does ship, but these build steps run unpinned code.
**Fix:** Consider `--no-build-isolation` with a hash-pinned `hatchling` in the locked export, or document this as an accepted build-time risk.

### IN-06: Hollow-report guard is easy to sidestep
**File:** `tests/codex_report_status.py` (`TRIVIAL_COMMANDS`)
**Issue:** A report that records only `ls` or `cat README.md` with exit code 0 passes the D-18 hollow-report guard. That is acceptable for a heuristic, but the docstring says the guard proves the diff was inspected.
**Fix:** Consider also requiring at least one recorded command that names the reviewed range (`git diff <base>..<head>`), or soften the wording.

### IN-07: The CodeQL readiness fallback match is unlikely to fire
**File:** `.github/scripts/acceptance-readiness.cjs:96-107`
**Issue:** When there is no `CodeQL` check run, the fallback looks for `Analyze*` runs from the `github-advanced-security` app. Default-setup `Analyze (<lang>)` runs come from the `github-actions` app, and the fallback also takes only the single newest run. A failing analysis for one language could be hidden behind a passing one.
**Fix:** Require every matching analysis run on the head to succeed, and match on the app that actually posts them.

### IN-08: The readiness dry run uses HEAD's gate, not the pinned gate the job runs
**File:** `.github/scripts/acceptance-readiness.cjs:11`; `.github/workflows/review-acceptance.yml:28`
**Issue:** Readiness `require`s the local `review-acceptance.cjs`, while the acceptance job checks out `8df9eaf…`. Both are identical today. Once either moves, "ready" can disagree with the real gate, which is the failure D-20 is meant to prevent.
**Fix:** Have readiness load the gate with `git show <pinned-sha>:.github/scripts/review-acceptance.cjs` (pin read from the workflow file), or add a test asserting that the pinned blob equals HEAD's.

## Set aside (needs ruling)

### SA-01: This PR's acceptance runs on the gate it introduces
**Where:** `.github/workflows/review-acceptance.yml:23-28`
**Why excluded:** It is disclosed in the workflow comment, and the effect is a governance choice rather than a code defect.
**Effect if left as is:** The schema-2 keyed gate checks its own introduction. If it has a defect that admits a bad register, that defect also admits this PR.
**Needs:** An owner ruling: accept as disclosed, or require the independent Codex/vibe-check pass to explicitly clear `review-acceptance.cjs` before approval.

### SA-02: Register schema cutover strands other open PRs
**Where:** `.github/scripts/review-acceptance.cjs:9-11`; `.github/scripts/review-register.cjs:95-112`
**Why excluded:** This is an operational ordering question, not a code bug.
**Effect if left as is:** Until the variables are migrated, this PR's acceptance fails with "Missing blocker register". After migration, any other open PR still using the old pin (`25f1ecd`, schema 1) fails acceptance until it rebases. Schema-1 dispositions are archived and not carried forward, so in-flight PRs need their dispositions re-entered.
**Needs:** An owner ruling on migration timing relative to other open PRs (including Dependabot).

### SA-03: Dependabot `uv` ecosystem has no cooldown
**Where:** `.github/dependabot.yml:23-31`
**Why excluded:** Cooldown is a policy choice. The comment explains the restriction for docker/actions but not why `uv` has none.
**Effect if left as is:** Monthly `uv` PRs can pick up a release published minutes earlier, so there is less buffer against a malicious or yanked package than for actions/docker.
**Needs:** An owner ruling: add a `cooldown` for `uv`, or accept as is.

---

_Reviewed: 2026-10-27_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
