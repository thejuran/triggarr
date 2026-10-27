---
phase: 85-follow-on-ci-improvements-acceptance-usability
fixed_at: 2026-10-27T19:41:24Z
review_path: .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW.md
iteration: 2
findings_in_scope: 4
fixed: 4
skipped: 0
rejected: 0
status: all_fixed
---

# Phase 85: Code Review Fix Report (iteration 2)

**Fixed at:** 2026-10-27T19:41:24Z
**Source review:** .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW.md (iteration 2, reviewed head `252fe61`)
**Iteration:** 2

**Summary:**
- Findings in scope: 4 (CR-01, WR-01, WR-02, WR-03, the scope the owner approved on 2026-10-27, round 2)
- Fixed: 4
- Skipped: 0
- Rejected: 0
- Out of scope (not touched, as the owner instructed): IN-01 to IN-11, SA-01 to SA-03

Method for each finding: first regression tests were added and confirmed to fail on the pre-fix code, then the fix was applied, then the relevant suites were run. Each finding is one commit containing its tests and its fix. The work was done directly on branch `ci-followon` in the main working tree, on top of `ae8e4b2` (the origin/main merge). Nothing was pushed.

## Fixed Issues

### CR-01: The skip-condition detector still misses `if :`, extra spaces after the dash, and flow-mapping steps

**Files modified:** `.github/scripts/ci-job-consistency.cjs`, `.github/scripts/ci-job-consistency.test.cjs`
**Commit:** 75ebe6f
**Applied fix:** The single-spelling regexes are gone. The detector now uses a small YAML reader for the parts it needs, still with no dependencies. It reads keys at a known column in any spelling: plain, `"if"`, `'if'`, or with a space before the colon. It reads a step's keys whether they start on the dash line after any number of spaces, or on the line after a bare `-`. It also reads flow-mapping steps (`- {name: …, if: …}`), including ones that span lines. Values are read as the inline text plus all more-indented lines, so `if:` with its value on the next line is caught too. Text inside `run:`/`script:` blocks and nested `with:` values is never mistaken for a step key.

The reader reports any shape it cannot read. It does not treat such a step as having no condition (fail closed). This covers:
- an alias, anchor or tag where a step or key should be (`- *x`, `- &x`, `- !!map …`);
- an explicit `? if` key, or a merge `<<:` key;
- a quoted key JSON cannot decode (`"i\x66"`);
- an unterminated flow mapping, or text after one;
- `steps:` written as a flow sequence or an alias;
- a job body not indented by 4 spaces, or other unexpected indentation;
- more than one `steps:` key or job-level `if`.

The new message is `required job "<id>" cannot be parsed for skip conditions: <reason>`. A step can have more than one `if` entry, and each one is checked against the allowlist.

**Related gap closed in the same fix.** Job-level `if` had the same spelling gap: `    if : false`, `    "if": false`, and `    if:` with the value on the next line all returned `[]` before this fix. In `review-acceptance.yml`, the required check is the job itself, so a job skipped this way would count as passing. `extractJobIf` now uses the same reader, which also affects `requiredJobsFor` and the release.yml if-equality test. This is a widening of the review's scope. I included it because it is the same defect in the same detector.

**Regression tests (25 new; 23 failed before the fix, 2 are guards that already passed).** Every variant is applied to the real `ci.yml` ("Fail if tests failed" in the `test` job, or the `lint` job), and the main ones also to the real `review-acceptance.yml`:
- `if : false`;
- `if : github.run_attempt == '0'` (actionlint passes this one);
- `"if" : false`;
- `-   if: false`, with the whole step re-indented;
- flow mapping with `if: false`, and with `if : github.run_attempt == '0'`;
- alias step, `? if` explicit key, `<<: *x` merge key, `"i\x66"` key, unterminated flow mapping, flow-sequence `steps:`;
- job-level `if :`, `"if":`, and `if:` with the value on the next line, on both workflows;
- a job body re-indented away from 4 spaces.

The guards are: `if:` with the value on the next line at step level, and an `if:` nested under `with:` together with the real files' run/script blocks (no problems reported).

Both real workflows still report `[]`. The two allowlisted step conditions (`test::Upload test evidence` `always()`, and the folded `browser-e2e::Upload browser failure evidence`) still pass. I also checked by hand that a tab after the dash, a tag, an anchor, a bare `-` followed by `if :`, a multi-line flow step, a JSON-style `{"if":false}` step, a `'if' :` key, and a compact `steps:` list at the job-key column are each either reported or read correctly.

**Status:** fixed: requires human verification (parser logic change)

### WR-01: Mandatory `meta.base === baseRefOid` rejected valid local-checkpoint Codex evidence

**Files modified:** `.github/scripts/acceptance-readiness.cjs`, `.github/scripts/acceptance-readiness.test.cjs`
**Commit:** ebdd76c
**Applied fix:** Readiness now runs `git merge-base <baseRefOid> <head>` itself, as an argument array with no shell. It requires `meta.base` to equal that merge-base. If git fails, or returns something other than a 40-hex SHA, readiness stops with exit 1 and "could not compute the merge-base" (fails closed). The audited-input diff is recomputed over the same range, `<merge-base>..<head>`, so audited files that changed only on main after the fork point no longer force a cross-grade. The checklist now shows `Reviewed base SHA (merge-base): …` under `Full base SHA: …`.

**Why this rule, and why it is the narrowest one.** It is narrower than the review's suggestion, which was to accept either `baseRefOid` or the merge-base:
- *PR checkpoint:* the runner's `verify_trust` refuses a PR base that is not an ancestor of the head. So any PR-checkpoint base the runner can record already equals `merge-base(baseRefOid, head)`.
- *Local phase checkpoint:* the contract's `git merge-base origin/main HEAD` is the branch's fork point (or its last merge of main). That stays the merge-base with the current `baseRefOid` when main moves forward. This is the case that was being rejected.
- So one exact value covers both contract rules. A `baseRefOid` that is *not* an ancestor of the head is no longer accepted, because no runner reviews that two-dot range. Accepting it would have been the only new acceptance path in the review's suggestion, and it is not needed.
- For direct callers of `codexStatusFor`/`readiness` that pass no merge-base, the PR base itself is still required (the previous, stricter rule). Every `runCli` path passes the merge-base.

**Not changed:** the fallback validator still checks a fallback record's `base` against the PR base. That is unchanged behaviour, and the IN-10 alignment was out of scope.

**On this branch now:** after the `ae8e4b2` merge, `git merge-base origin/main HEAD` equals `origin/main` (`decd5f1`). A post-fix local Codex pass will therefore record a base that readiness accepts under both the old and the new rule.

**Regression tests (5 new; 4 failed before the fix, 1 guard already passed):**
- main moved to a merge commit ahead of the fork point, with meta.base equal to the merge-base, is ready (exit 0). This includes an audited file changed only on main, which must not count;
- meta.base equal to a `baseRefOid` that is not an ancestor of the head is blocked;
- meta.base that is neither value is blocked (guard);
- merge-base missing, empty, or not a SHA fails closed;
- `codexStatusFor` uses `reviewedBase` when it is given.

The existing CLI exec tables gained the `git merge-base` call.

**Status:** fixed: requires human verification (trust/logic change)

### WR-02: Readiness accepted status files not bound to this head or base

**Files modified:** `.github/scripts/acceptance-readiness.cjs`, `.github/scripts/acceptance-readiness.test.cjs`
**Commit:** b05ced4
**Applied fix:** This is the review's "minimum" fix. A checker verdict of `complete` now counts only if its `inspected_head` equals the PR head and its `inspected_base` equals the verified `meta.base`:
- in the head-side `.status.json`;
- in `.base-status.json`, whenever a base cross-grade is required.

Otherwise readiness blocks with "Codex status file is not bound to this head and base", or for the base grade, "grader changed in this diff: the base checker status is not bound to this head and base". I confirmed that the base checker on `origin/main` already emits both fields, so a real cross-grade is not over-rejected. The untrusted-head "claims complete" block still fires first, unchanged. The existing readiness fixtures now carry bound statuses.

**Regression tests (5 new; 4 failed before the fix):**
- the reviewer's reproduction (status and base-status both complete for an unrelated commit, with a recomputed audited change) is blocked;
- a complete status with the wrong head, the wrong base, or no or null inspected SHAs is blocked;
- a required base-status that is complete but unbound is blocked;
- bound status plus bound base-status is ok (guard);
- the CLI blocks a status file graded for another head.

**Residual, needs an owner ruling.** The review's "stronger" option is not implemented: readiness would itself materialize the base commit's checker and re-grade `<OUT>.last.json`, ignoring `.base-status.json`. So when `tests/codex_review_run.py` itself changes, `.base-status.json` is still written by the changed runner. A runner change could make it write a bound, "complete" base status. The base checker *code* still comes from the base commit, but the runner chooses what it passes to that checker. The two options:
- *(a) Keep as is.* No added code. The residual is limited to diffs that change the runner itself. Those diffs are already sensitive-class under the classification policy, and the owner must accept them in any case.
- *(b) Implement the stronger re-grade in readiness.* Readiness would gain a Python subprocess and a temp-dir materialization, plus the need for the `.last.json` report and the Codex exit code to be present locally. That is roughly half a day with tests, and it adds acceptance-time failure modes.

My recommendation is (a) for this phase, with (b) recorded as a follow-up if runner changes become frequent.

**Status:** fixed: requires human verification (trust/logic change; residual above)

### WR-03: Fallback reviewer denylist missed `bm-code-reviewer` and `Claude Code`

**Files modified:** `.github/scripts/codex-fallback.cjs`, `.github/scripts/codex-fallback.test.cjs`
**Commit:** e44b818
**Applied fix:** The exact list (`DISALLOWED_REVIEWERS`, still exported) is kept. In addition, the reviewer name is lowercased and split on every run of non-alphanumeric characters. The name is rejected as not independent when any token is `bm`, `buildomator`, `gsd` or `claude`, or when the token sequence `codex review run` appears.

Matching is by token, not substring, so `submarine` is not caught by `bm`. A human reviewer whose name contains the word "Claude" would be rejected. That errs on the safe side, and they can be recorded under another name.

**Regression tests (15 new; 10 failed before the fix):**
- rejected: `bm-code-reviewer`, `Claude Code`, `Claude (bm-code-reviewer)`, `claude-opus`, `BM_code_review`, `GSD code reviewer`, `gsd-code-fixer`, `Buildomator review agent`, `codex_review_run.py`, `Codex Review Run`, and `  BM  ` (a guard that already passed);
- still accepted: `vibe-check deep review (owner-run)`, `manual Codex inspection session`, `independent human reviewer`, `submarine review`.

**Status:** fixed

## Final gate (run after all four fix commits, at e44b818)

| Command | Result |
|---------|--------|
| `uv run pytest tests/ -x -q` | 2569 passed, 0 failed (38 warnings, pre-existing) |
| `uv run ruff check triggarr/ tests/ .github/scripts/` | All checks passed |
| `FORCE_COLOR=0 node --test --test-reporter=tap .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs` | 406 tests, 406 pass, 0 fail (356 at the start of iteration 1, 381 after CR-01, 386 after WR-01, 391 after WR-02) |
| `actionlint` | exit 0, no findings |

The working tree is clean apart from this report, which is left for the orchestrator to commit. Nothing was pushed, no `--no-verify` was used, and no stash was used.

**Review-workflow note:** these fixes change the commit under review from `ae8e4b2` to `e44b818`. Under the project's review workflow (CLAUDE.md), the post-fix BM review and its paired independent Codex pass must run on the new head. Evidence recorded for earlier heads does not cover these commits. `tests/codex_review_run.py` and `tests/codex_report_status.py` were not changed in this round, so the Codex audited inputs are unchanged by these fixes.

---

_Fixed: 2026-10-27T19:41:24Z_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 2_
