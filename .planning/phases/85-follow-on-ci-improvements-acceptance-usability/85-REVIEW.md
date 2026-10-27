---
phase: 85-follow-on-ci-improvements-acceptance-usability
reviewed: 2026-10-27T21:54:52Z
reviewed_head: eae6d34386c873ed631e83ecbecdd624c73272ff
diff_base: 091d8ed
iteration: 4
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
  - uv.lock
findings:
  critical: 1
  warning: 3
  info: 13
  total: 17
status: issues_found
---

# Phase 85: Code Review Report (iteration 4)

**Reviewed:** 2026-10-27T21:54:52Z (head `eae6d34386c873ed631e83ecbecdd624c73272ff`, diff base `091d8ed`)
**Depth:** standard
**Files Reviewed:** 49 (uv.lock skimmed only)
**Status:** issues_found

## Summary

This is a fresh review of the whole phase at head `eae6d34`, after fix round 3:
- `7178836`: CR-01, the new PyYAML guard `tests/test_required_jobs_no_skip.py`;
- `dbb4443`: CR-02, the job-set cross-checks;
- `ea31695`: WR-01, pinning the allowlisted step to the evidence upload;
- `63b0b3d`: WR-02, binding the fallback to the reviewed base;
- `bb4df1a`: the backlog record.

**Owner rule applied to severity (round 3):** the PyYAML pytest guard is the authoritative no-skip check, and the Node detector is a secondary line. A bypass counts as a blocker only if it passes the pytest guard and CI's pytest run while disabling a required check.

Baseline at this head:
- `node --test .github/scripts/*.test.cjs` plus the planchk-router test: 415/415 pass.
- The 12 phase pytest files, including the new guard: 479/479 pass.
- `ruff check triggarr/ tests/ .github/scripts/` is clean.
- `actionlint` exits 0.

Every mutation below was applied to a detached worktree of `eae6d34`. For each one I ran:
- `actionlint`;
- the 6 workflow and guard pytest files (153 tests);
- the full Node suite;
- `findSkipConditions` on both workflows.

For the CR-01 job-level case I also ran the full `pytest tests/` suite: 2627 passed. The worktree has since been removed. No source file was modified.

### Does the guard run inside the required CI test job?

**Yes, but CI enforces its result only through a step that the guard itself protects.**
- `ci.yml:52` runs `pytest tests/`, which collects the guard. `pyproject.toml` has no `addopts`, and `tests/conftest.py` only ignores `e2e`.
- An import or collection error exits non-zero, so that case fails closed.
- The pytest step deliberately exits 0 (`ci.yml:50-58`). A failure, including a guard failure, only fails the job through "Fail if tests failed" (`ci.yml:88-95`).

So a mutation that neutralises that step neutralises the guard's own CI verdict as well. See CR-01 and WR-01.

### Status of the iteration-3 findings

I checked each fix with my own crafted inputs.

| Prior | Verdict | Evidence |
|-------|---------|----------|
| CR-01 quoted or escaped `continue-on-error` | **Fixed (the guard detects it)** | Putting `'continue-on-error': true` on "Fail if tests failed" makes the guard report 10 failures. The Node detector still returns `[]`; that gap is accepted by the owner. **However**, in CI that guard failure is swallowed by the very `continue-on-error` it detects (WR-01). |
| CR-02 column-0 comments and header spellings | **Fixed** | The guard reports each of these: the column-0 comment followed by a step `if` in `ci-ready` (4 failures), the same after the acceptance gate step (8 failures), and every header spelling the fixer tested. The cross-check of `needs` against `ALL_JOBS`, and the rule that review-acceptance.yml holds exactly one job, both work. |
| WR-01 allowlist keyed by name | **Fixed in both checks** | Renaming the browser gate to "Upload browser failure evidence" with the allowlisted condition is caught by the guard (7 failures) and by the Node detector (it reports the name appearing twice, the step not using `upload-artifact`, and the step having `run:`). A `uses:` with leading whitespace that would make a local action invisible is rejected by actionlint and by the guard. |
| WR-02 fallback base | **Fixed. No fail-open path, and no over-tightening found.** | `codexStatusFor` hands `validateFallback` the `expectedBase`, after already checking that it matches `HEAD_RE` and equals `meta.base`. A `reviewedBase` of `null` gives `expectedBase` null, which fails `HEAD_RE`, so that case blocks. `record.base` and `scope.base` are required fields, so leaving one out cannot skip the comparison. The `validate` CLI checks `--base` against `HEAD_RE` and requires it to equal `meta.base`; a meta with no `base` is rejected. `validateFallback` has no other caller (the GitHub gate does not use it), so readiness and the gate cannot disagree. The trusted PR runner pins `--base` to `baseRefOid` (`codex_review_run.py:505`), and untrusted-refused metas also record `base`, so valid records still pass. The remaining gap, that the CLI does not compute the merge-base itself, is IN-10 (carried, narrowed). |

### New in this iteration

- **CR-01:** the guard does not look at the `shell:` or `defaults: run: shell:` keys, which control how a step runs. Setting `shell: true {0}` neutralises a required gate step, and every static check stays green.
- **WR-01:** the guard is authoritative only locally. In CI, its failure is reported only through "Fail if tests failed", the step it protects, so the iteration-3 CR-01 case still turns "CI ready" green. Under a strict grade-by-effect reading this would be a blocker. It is a warning only because of the owner's round-3 rule (see the note in the finding).
- **WR-02:** the `ci-ready` gate step is pinned by its heredoc body only. Hardcoding the `RESULTS` env, or the `TEST_EXIT` env on "Fail if tests failed", passes every check.
- **WR-03:** a job in another workflow file can produce a second "CI ready" or "Review acceptance" check run. Readiness picks the check run with the highest id by name alone.
- **IN-13:** the classification policy still names the Node detector as "the" no-skip test, and does not classify the authoritative guard as sensitive.

IN-01 to IN-12, SA-04 and SA-05 are owner-recorded follow-ups in `.planning/backlog/MAINTENANCE.md`, and I carry them forward as such. Two were changed by round 3: SA-05 (now forbidden by the guard) and IN-10 (narrowed); both are annotated. SA-01 to SA-03 are carried unchanged.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: The guard ignores `shell:` and `defaults: run: shell:`, so a one-line `shell: true {0}` neutralises `ci-ready` or "Fail if tests failed" with every check green

**File:** `tests/test_required_jobs_no_skip.py:118-171` (`job_problems`); affects `.github/workflows/ci.yml:88-95` and `:423-444`
**Issue:**
- **How it works:** GitHub Actions accepts a custom shell template, `command … {0}`, at three levels: on a step (`shell:`), on a job (`defaults.run.shell`), and on the whole workflow (`defaults.run.shell`). With `true {0}`, the runner executes `/usr/bin/true <script>`, which exits 0 without running the script. That neutralises a step as completely as `continue-on-error`.
- **What the guard misses:** it checks `if`, `continue-on-error`, `uses` and `steps`. It never looks at `shell` or `defaults`. The Node detector does not either.
- **Current usage:** no workflow in this repo uses `shell:` or `defaults:` today (I searched for both), so forbidding them costs nothing.

I applied each edit to the real `ci.yml`:

| Edit | actionlint | Guard and workflow pytest (153) | Node suite | `findSkipConditions` |
|------|-----------|-------------------------------|-----------|----------------------|
| `ci-ready`: `defaults: {run: {shell: true {0}}}` at job level | exit 0 | 153 pass (full `pytest tests/`: 2627 pass) | 404/404 | `[]` |
| `ci-ready` gate step: `shell: true {0}` placed after its `env:` block | exit 0 | 153 pass | 404/404 | `[]` |
| "Fail if tests failed": `shell: true {0}` | exit 0 | 153 pass | 404/404 | `[]` |

(If `shell:` is placed directly after the gate step's `name:` line, three Node tests fail. That is only because a text anchor in those tests stops matching; moving the key one line down avoids it.)

**Effect:**
- **First row (`ci-ready`):** the "Require every mandatory job to succeed" script never runs. "CI ready", the required check in the ruleset (`docs/buildomator-greptile-pilot.md:28`), is green whatever `test`, `docker`, `os-scan` and the other needed jobs concluded. Readiness (`acceptance-readiness.cjs:135-139`) checks only "CI ready", so it reports CI as ok. Release preflight checks every job (`release-policy.cjs:3`), so a release would still be blocked. A merge would not.
- **Third row ("Fail if tests failed"):** the `test` job succeeds even when pytest fails, so neither CI ready nor the release preflight sees the failure. Only the manual coverage-provenance step at the checkpoint (`docs/review-checkpoint-record.md:159`, `test_exit_code !== 0`) would catch it.
- **Severity:** this passes the guard and CI's pytest run, and it disables a required check, so it meets the owner's blocker bar. It is the same "neutralise" class as `continue-on-error`, and the guard's docstring says it covers that class ("no job … can be skipped or neutralised").

**Fix:** In the guard, forbid execution-control overrides for every required job and the workflow itself:
```python
# in ci_problems / acceptance_problems, after loading:
if "defaults" in doc:
    problems.append(f"{path_name} sets workflow-level defaults: (a run.shell override can neutralise every run step)")

# in job_problems:
if "defaults" in job:
    problems.append(f"{prefix} sets defaults: (run.shell can neutralise its run steps)")
...
# per step:
if "shell" in step:
    problems.append(f"{prefix} {label} sets shell: {step['shell']!r}")
```
Also:
- Add `"shell"` and `"defaults"` to `WATCHED_KEYS`, so case variants are caught too.
- Add regression tests for the three rows above, plus workflow-level `defaults`.
- If a future step genuinely needs a shell, allowlist the exact `(job, step name, shell)` the way step `if` is allowlisted, and accept only the built-in names (`bash`, `sh`, `python`, `pwsh`).
- **Hardening (I did not test it):** consider also rejecting `BASH_ENV`/`ENV` in workflow, job and step `env:`. Non-interactive bash sources `BASH_ENV` before the script, so it could inject an early `exit 0` if it points at a file that an earlier step wrote.

## Warnings

### WR-01: The authoritative guard's CI verdict is enforced only by "Fail if tests failed", the step it protects, so the iteration-3 CR-01 case still turns "CI ready" green

**File:** `.github/workflows/ci.yml:47-58, 88-95`; `tests/test_required_jobs_no_skip.py` (where it runs); `.github/scripts/ci-job-consistency.cjs` (the `continue-on-error` line regex)
**Issue:** The pytest step captures pytest's exit status and always exits 0. The job fails only when "Fail if tests failed" sees `TEST_EXIT != 0`.

Consider the iteration-3 CR-01 edit: `'continue-on-error': true` on "Fail if tests failed". Verified results:
- actionlint: exit 0.
- Node suite: 404/404 pass, and `findSkipConditions` returns `[]` (the accepted Node gap).
- The guard: 10 failures.

In CI, that means:
1. pytest exits 1, and `test_exit=1` is recorded.
2. "Fail if tests failed" exits 1, but `continue-on-error` gives it the conclusion `success`.
3. The `test` job result is `success`, `ci-ready` sees `success`, and "CI ready" is green.

The guard's failure appears only in the step log and annotations. The release preflight also passes, because every job concluded success. The only thing that would show it is the manual coverage-provenance check.

The owner downgraded the Node detector's parse gaps because "the pytest guard is authoritative". For this exact case, the guard does not gate CI. It gates only local runs.

**Severity note:** the guard does flag this edit, and CI's pytest exits non-zero. So under the owner's round-3 rule it is graded WARNING. By effect it is blocker-level: the required check is green while tests, including the guard, fail. The owner may want to rule whether "CI's pytest run" in that rule means "pytest exits non-zero" or "CI goes red".
**Fix:** Do both of the following.
1. Make the swallowed failure machine-visible. Have readiness, and the release preflight, download the run's `coverage-<run_id>-<attempt>` artifact and run `coverage-provenance.cjs check`, which already rejects `test_exit_code !== 0` (`coverage-provenance.cjs:192`). This turns the existing manual checkpoint step into a gate that does not depend on the `test` job's own step conclusions.
2. Close the one Node gap that matters here. The Node step runs before pytest and is not behind "Fail if tests failed". Make its `continue-on-error` check fail closed: flag any job line where a key contains `continue` and `error` in any quoting, or contains a `\x`/`\u` escape, and report it as unreadable. A false positive only costs a reword. A false negative costs the gate.

Another option is to run `pytest tests/test_required_jobs_no_skip.py tests/test_ci_gate.py -q` as a plain step, without `set +e`, in a second required job (for example `lint`). Then a single neutralised step no longer hides the guard.

### WR-02: The `ci-ready` gate step and the `test` job's failure check are pinned only by their script bodies; hardcoding their `env:` inputs passes every check

**File:** `.github/workflows/ci.yml:430-433` (`RESULTS: ${{ toJSON(needs) }}`), `:89-90` (`TEST_EXIT: ${{ steps.pytest.outputs.test_exit }}`); `tests/test_ci_gate.py:33-50` (extracts and tests only the heredoc)
**Issue:** `test_ci_gate.py` executes the real heredoc against synthetic `needs` results, which is good. Nothing checks where the script's input comes from. I verified both edits:

| Edit | actionlint | Guard and workflow pytest | Node suite | Detector |
|------|-----------|-----------------------|-----------|----------|
| `RESULTS: '{"test":{"result":"success"}, …all 9…}'` (a literal) | exit 0 | 153 pass | 404/404 | `[]` |
| "Fail if tests failed": `TEST_EXIT: "0"` (a literal) | exit 0 | 153 pass | 404/404 | `[]` |

The first makes "CI ready" green whatever the needed jobs concluded. The second makes the `test` job green whatever pytest returned.

(Prepending `exit 0` to the `ci-ready` run block is caught by actionlint/shellcheck as unreachable code, so that variant is not open.)

These edits change the gate's input values, not how it executes, which is why I graded this as a warning rather than with CR-01. They are visible in a sensitive-class diff. But the `ci-ready` job is tiny, and it is the one required check, so pinning it exactly is cheap.
**Fix:** In the guard, assert the exact structure of the two gate steps:
- `jobs["ci-ready"]["steps"]` has length 1.
- `step["env"] == {"RESULTS": "${{ toJSON(needs) }}"}`.
- `step["run"]` equals the text that `test_ci_gate._extract_ci_ready_script` wraps (`python3 - <<'PY'\n…\nPY\n`), and nothing else.
- The step has no `shell`, `working-directory` or `timeout-minutes` override.
- For "Fail if tests failed": `env == {"TEST_EXIT": "${{ steps.pytest.outputs.test_exit }}"}`, and the step with `id: pytest` writes `test_exit=$status`.

Add the two edits above as regression tests.

### WR-03: Another workflow can publish a second "CI ready" or "Review acceptance" check run, and readiness picks the check run with the highest id by name alone

**File:** `.github/scripts/acceptance-readiness.cjs:122-126` (`latestCheck`), `:134-139`; `tests/test_required_jobs_no_skip.py` (reads only `ci.yml` and `review-acceptance.yml`)
**Issue:** `latestCheck` keeps check runs whose `name` matches and whose `head_sha` is the head, then takes the highest `id`. It does not check which workflow file, or which app, produced the run.

I verified the static side. A new file, `.github/workflows/mirror.yml`, on `pull_request` to main, with one job `name: CI ready` that runs `echo ok`, gives:
- actionlint: exit 0;
- the guard and workflow pytest files: 153 pass;
- the Node suite: 404/404 pass.

The guard and the Node detector only ever read `ci.yml` and `review-acceptance.yml`. (A second "CI ready" job inside `ci.yml` is caught: 4 pytest failures.)

If the mirror job is delayed (for example `needs:` on a job that sleeps), its check run is created after the real one, so readiness reports CI ready "ok" from the mirror. The ruleset requires "CI ready" and "Review acceptance" from their "expected apps". Every workflow posts as the GitHub Actions app, so that pin does not tell the two apart. I did not verify how GitHub's ruleset resolves two same-named check runs from the same app on one commit. Readiness's behaviour is proven from the code.
**Fix:**
- Add a guard test that loads every `.github/workflows/*.yml` and asserts that "CI ready" and "Review acceptance" are each the `name` (or id, when no name is set) of exactly one job, in `ci.yml` and `review-acceptance.yml` respectively.
- In readiness, bind the check to its workflow. Fetch the check suite's workflow run (`GET /repos/{o}/{r}/actions/runs?check_suite_id=…`), require `path == '.github/workflows/ci.yml'`, and block when more than one check run named "CI ready" exists for the head.

## Info

### IN-13: The classification policy still names the Node detector as the no-skip test, and does not list the authoritative guard as sensitive (new)
**File:** `docs/review-classification-policy.md:3, 14`
**Issue:**
- Line 3 says "a permanent no-skip test (`.github/scripts/ci-job-consistency.cjs`) fails CI…". Since round 3, `tests/test_required_jobs_no_skip.py` is the authoritative check, and no document says so.
- The sensitive row lists `.github/scripts/**` and the Codex review machinery. It does not list the guard, or `tests/test_ci_gate.py`, whose `ALL_JOBS` the guard imports.

So a PR that only weakens the guard (for example widening `STEP_IF_ALLOWLIST`) is classified "code" rather than sensitive. The code class still gets the full review, so the effect is the missing RISK-01 note.
**Fix:**
- Name both checks on line 3, and say the pytest guard is authoritative.
- Add `tests/test_required_jobs_no_skip.py` and `tests/test_ci_gate.py` to the sensitive row.
- Optionally add both to `tests/test_review_machinery_lists.py`'s drift guard.

### IN-01 to IN-12 (carried, owner-recorded follow-ups, MAINTENANCE.md "Still open after Phase 85")
These are unchanged from iteration 3 and recorded by owner decision on 2026-10-27:
- IN-01: the OS-scan image-ID wording.
- IN-02: `persist-credentials` on the `os-scan` checkout.
- IN-03: `--repo` on the register reads and writes.
- IN-04: the raw `gh variable set` trace.
- IN-05: the build-time packages (`hatchling`, `uv`).
- IN-06: the hollow-report guard.
- IN-07: the CodeQL fallback match.
- IN-08: the readiness dry run uses HEAD's gate.
- IN-09: hollow nested values in fallback records.
- IN-10: **narrowed by `63b0b3d`**. The CLI now binds `--base` to `meta.base`, but it still does not compute the merge-base itself.
- IN-11: the readiness prerequisites are not in the docs.
- IN-12: the reviewer-name denylist misses run-together and model-only names. `63b0b3d` and `e44b818` did not touch the denylist, so it is unchanged.

**Fix:** As recorded in the backlog.

## Set aside (needs ruling)

### SA-04 (carried, owner-recorded follow-up): A PR that changes `tests/codex_review_run.py` can certify its own base cross-grade
**Where:** `tests/codex_review_run.py` (`_run_base_grader`); `.github/scripts/acceptance-readiness.cjs:80-88`
**Why excluded:** The owner decided on 2026-10-27 to record it rather than fix it. Round 3 did not change it.
**Effect if left as is:** For a PR that changes the runner, a "complete" Codex item rests on the changed runner's honesty.
**Needs:** None this round (recorded). Revisit when the backlog item is scheduled.

### SA-05 (carried, owner-recorded follow-up; changed by round 3): The checks do not look inside reusable workflows or local actions
**Where:** `tests/test_required_jobs_no_skip.py:129-130, 151-153`
**Why excluded:** Recorded by the owner. Round 3 now forbids both in required jobs. I verified that a job-level `uses:`, `./`, `../` and `/` actions, and a `" ./…"` spelling (rejected by actionlint) are all caught. The residual applies only if the owner ever wants one of them.
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

_Reviewed: 2026-10-27T21:54:52Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
_Iteration: 4_
