---
phase: 85-follow-on-ci-improvements-acceptance-usability
fixed_at: 2026-10-27T21:43:16Z
review_path: .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW.md
iteration: 3
findings_in_scope: 4
fixed: 4
skipped: 0
rejected: 0
status: all_fixed
---

# Phase 85: Code Review Fix Report (iteration 3)

**Fixed at:** 2026-10-27T21:43:16Z
**Source review:** .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW.md (iteration 3, reviewed head `8bd286c`)
**Iteration:** 3
**Fix head:** `bb4df1ae2c77073996e640be2642f13b6809d42f`

**Summary:**
- Findings in scope: 4 (CR-01, CR-02, WR-01, WR-02; owner-approved scope, 2026-10-27, round 3)
- Fixed: 4
- Skipped: 0
- Rejected: 0
- Recorded, not fixed (owner decision): SA-04, SA-05 and IN-01 to IN-12. They were added to `.planning/backlog/MAINTENANCE.md` under "Still open after Phase 85" (`bb4df1a`). SA-01 to SA-03 were not touched.

Method: each code fix has regression tests. For WR-01 and WR-02, the tests were run and failed before the fix was applied. For CR-01 and CR-02 the fix is itself a new test file. As the regression evidence, I confirmed that the existing Node detector returns `[]` for the reviewed mutations: a quoted job-level `continue-on-error` on `ci-ready`, and the column-0 comment cases in both workflows. The new guard rejects all of them. There is one commit per finding. The work was done directly on `ci-followon` in the main working tree. Nothing was pushed.

## The pytest guard is authoritative

`tests/test_required_jobs_no_skip.py` is now the authoritative no-skip check for the jobs behind required checks. It loads the real `ci.yml` and `review-acceptance.yml` with PyYAML, a real YAML parser, using a SafeLoader subclass that rejects duplicate and unhashable keys. That means the parser decides what each key and value is, and the spelling tricks behind CR-01 and CR-02 cannot hide a key from it.

The Node detector `.github/scripts/ci-job-consistency.cjs` stays as a secondary line. As instructed, it received only the WR-01 change and no further YAML-parsing hardening, so the parse gaps the review describes in CR-01 and CR-02 still exist there. Where the two checks disagree, the pytest guard decides. The guard runs in CI's `test` job with the rest of `tests/`.

## Fixed Issues

### CR-01: `continue-on-error` written as a quoted or escaped key is not detected

**Files modified:** `tests/test_required_jobs_no_skip.py` (new)
**Commit:** 7178836
**Applied fix:** This commit adds the guard. For every required job (in `ci.yml`, each job in `ci-ready`'s `needs` plus `ci-ready`; in `review-acceptance.yml`, every job), it checks:
- `continue-on-error` at job or step level is rejected whatever its value: true, false, or an expression. This is stricter than "truthy or expression" because no required job needs the key at all.
- A job-level `if` is rejected, except on `ci-ready`, where it must be exactly the string `always()`. A missing `if` on `ci-ready`, `${{ always() }}`, and `success() || failure()` are all rejected.
- Every step `if` must match an allowlist entry keyed by (job, step name, exact condition). The two entries are the same as before.
- PyYAML loads the bare key `on` as `True`. `workflow_triggers` accepts either form and requires exactly one of them.

Negative tests build mutated YAML in memory from the real files. Each mutation helper asserts that its anchor text occurs exactly once, so no test can pass without its mutation being applied. The cases:
- quoted, single-quoted, `\x72`-escaped, `-`-escaped and space-before-colon `continue-on-error`;
- `continue-on-error` as an expression, and set to `false`;
- job-level `continue-on-error` on `ci-ready` and on `acceptance`;
- job-level `if` written as `if :`, `"if":`, `!!str`, or with the value on the next line;
- step `if` as `if :`, as an escaped `"i\x66"`, after a bare `-`, and as one-line or multi-line flow-mapping steps;
- a merge key `<<: {if: …}`;
- an alias pulling a condition from an anchor in another job;
- an anchored step reused through an alias;
- a duplicate `if` key, which plain PyYAML would silently resolve to the last value;
- an allowlisted name with a different condition.

**Status:** fixed: requires human verification (new guard logic)

### CR-02: `parseJobs` stops at column-0 comments and drops unrecognised job headers

**Files modified:** `tests/test_required_jobs_no_skip.py`
**Commit:** dbb4443
**Applied fix:** PyYAML reads the whole document, so a column-0 comment or an unusual header spelling no longer hides anything from the guard. This commit adds cross-checks so that a dropped job also fails:
- `ci-ready`'s `needs` must equal `ALL_JOBS`, imported from `tests/test_ci_gate.py`.
- `review-acceptance.yml` must contain exactly the `acceptance` job.
- A missing `ci-ready` is reported.
- Non-string keys, and case variants of `if`, `continue-on-error`, `uses` or `steps`, are rejected.
- SA-05 is forbidden for today: a required job may not call a reusable workflow (job-level `uses:`), and a required step may not use a local action (`uses:` starting with `.` or `/`).

Negative tests:
- both of the review's end-to-end cases. A column-0 comment followed by a step `if` in `ci-ready`, and the same in the acceptance gate step, each produce exactly one problem. The `ci-ready` case also hides `continue-on-error`.
- `acceptance` headers written with a trailing comment, double-quoted, single-quoted with a space before the colon, and as an explicit `? acceptance` key;
- a `jobs:` block re-indented by 4 spaces. The unmodified re-indented file still passes, so the guard adds no false positive.
- a job dropped from `needs`, and `needs` reduced to a single string;
- the acceptance job renamed, or an extra job added;
- a reusable workflow, and local actions in both workflows.

**Status:** fixed: requires human verification (new guard logic)

### WR-01: The step-`if` allowlist is keyed by step name only

**Files modified:** `tests/test_required_jobs_no_skip.py`, `.github/scripts/ci-job-consistency.cjs`, `.github/scripts/ci-job-consistency.test.cjs`
**Commit:** ea31695
**Applied fix:** Both allowlist entries are evidence uploads. In both the pytest guard and the Node detector, a step that carries an allowlisted (job, name, condition) must now also:
- be the only step with that name in its job;
- use `actions/upload-artifact@`;
- have no `run:`.

The Node change is small. The step reader now also returns `uses` and `hasRun`, and `findSkipConditions` adds these three checks after an allowlist match.

Regression tests, all confirmed failing before the fix:
- the review's case: the browser gate renamed to "Upload browser failure evidence" with the allowlisted condition;
- the same rename after the real upload is renamed away and loses its condition, so the name is unique again;
- the `test`-job variant.

The same-name/different-condition case was already rejected and is also tested. There are two new Node tests.

**Status:** fixed: requires human verification (logic change)

### WR-02: A fallback record had to name `baseRefOid` while its Codex evidence names the merge-base

**Files modified:** `.github/scripts/acceptance-readiness.cjs`, `.github/scripts/acceptance-readiness.test.cjs`, `.github/scripts/codex-fallback.cjs`, `.github/scripts/codex-fallback.test.cjs`, `docs/codex-adversarial-review-contract.md`
**Commit:** 63b0b3d
**Applied fix:** `codexStatusFor` now passes `validateFallback` the same reviewed base it has already checked against the Codex meta's `base` (`expectedBase`: the merge-base when readiness computes one). Before, it passed the PR base. The fallback record, its `scope.base` and the Codex evidence therefore all have to name one base: the range that was actually reviewed.

The reviewer's suggested fix also covered the `validate` CLI, and I applied that part. Without it, the CLI and readiness would still disagree:
- The CLI now requires `--base` to equal the Codex meta's recorded `base`, and rejects a meta that has no base.
- The validator's message now reads "does not match the reviewed base (merge-base)".
- The contract's fallback `base` field now says it is the reviewed base, the one the Codex output records, and that `--base` must equal it.

**No fail-open path:**
- The fallback base is still pinned to exactly one SHA.
- That SHA has already been checked to equal both the merge-base readiness computed itself and the meta's `base`. A merge-base that cannot be computed still blocks (exit 1, unchanged).
- Direct callers that pass no reviewed base keep the PR-base rule, which is tested.
- A fallback that names the moved PR base, or whose record base and scope base disagree, is rejected.

**Regression tests:**
- Readiness, 4 new: a fallback that names the merge-base is accepted; one that names the moved PR base is rejected; a record base and scope base that disagree are rejected; the PR-base rule without a reviewed base still holds.
- CLI, 3 new: a meta base different from `--base` is rejected; a meta with no base is rejected; a matching base is accepted.
- Changed tests: two older CLI fixtures had no `meta.base`, so I added `base: BASE` to them. Two message assertions were updated to the new wording.

**IN-10 effect:** the `validate` CLI now binds the meta's `base`, which covers IN-10's binding gap. It still does not compute the merge-base itself, so IN-10 remains in the backlog with that narrower remainder.

**Status:** fixed: requires human verification (logic change)

## Backlog (not code fixes)

`bb4df1a` (`docs(85)`, added with `git add -f`) appends SA-04, SA-05 and IN-01 to IN-12 to `.planning/backlog/MAINTENANCE.md` under "Still open after Phase 85", in plain language:
- SA-04: a PR that changes `tests/codex_review_run.py` can write its own complete `.base-status.json`. The fix is to make the base cross-grade independent of the runner being reviewed (about half a day).
- SA-05: the checks do not inspect reusable workflows or local actions. The new guard forbids both in required jobs today.

## Full gate (at `bb4df1a`)

| Command | Result |
|---|---|
| `uv run pytest tests/ -x -q` | 2627 passed, 0 failed (38 warnings), exit 0 |
| `uv run ruff check triggarr/ tests/ .github/scripts/` | All checks passed, exit 0 |
| `FORCE_COLOR=0 node --test --test-reporter=tap .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs` | 415 tests, 415 pass, 0 fail |
| `actionlint` | exit 0 |

The new guard file on its own: 58 passed.

## Not done / for the owner

- The Node detector still has the parse gaps in CR-01 and CR-02 (the quoted job-level `continue-on-error`, column-0 comments, header spellings). As instructed, it was not hardened further. The pytest guard covers those cases and is authoritative.
- Per the project's review workflow, this fix round needs a fresh BM code review of the new head, with its paired Codex pass on the exact commit.
- REVIEW-FIX.md is not committed. The orchestrator handles that.

---

_Fixed: 2026-10-27T21:43:16Z_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 3_
