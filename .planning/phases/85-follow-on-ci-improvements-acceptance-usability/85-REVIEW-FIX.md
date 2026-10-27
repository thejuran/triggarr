---
phase: 85-follow-on-ci-improvements-acceptance-usability
fixed_at: 2026-10-27T19:20:04Z
review_path: .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
rejected: 0
status: all_fixed
---

# Phase 85: Code Review Fix Report

**Fixed at:** 2026-10-27T19:20:04Z
**Source review:** .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW.md (reviewed head `b4a47b6`)
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (CR-01, CR-02, WR-01, WR-02, WR-03, WR-04 — the scope the owner approved on 2026-10-27)
- Fixed: 6
- Skipped: 0
- Rejected: 0
- Out of scope (not touched, as the owner instructed): IN-01 to IN-08, SA-01 to SA-03

Method for each finding: first a regression test was added and confirmed to fail at the pre-fix code, then the fix was applied, then the relevant suites were run. Each finding is one commit containing its test and its fix. Work was done directly on branch `ci-followon` in the main working tree. Nothing was pushed.

## Fixed Issues

### CR-01: Fallback validator accepts a record with no owner approval, no reviewer, no result, and the wrong PR

**Files modified:** `.github/scripts/codex-fallback.cjs`, `.github/scripts/codex-fallback.test.cjs`
**Commit:** fb01095
**Applied fix:** `validateFallback` now:
- reports every missing nested field of `reviewer`, `scope`, `result` and `owner_decision`;
- compares `record.pr` with the context PR ("fallback is for a different PR");
- accepts only `approve-fallback` as the owner decision. `wait` and `retry-later` keep their specific messages, and any other value, including a missing one, gives "owner_decision.decision must be approve-fallback";
- requires a non-blank `reviewer.name`;
- requires `result.findings` to be an array, and rejects non-object entries instead of skipping them.

**Regression tests (6, all failed before the fix):**
- the reviewer's reproduction: empty sub-objects plus a wrong PR;
- decisions `nope`, `''`, `APPROVE-FALLBACK` and `42`;
- a wrong PR;
- a blank reviewer name;
- non-array findings;
- non-object finding entries.

**Status:** fixed: requires human verification (logic/validation change)

### CR-02: Skip-condition detector (ACCEPT-03) misses `- if:` as the first key of a step

**Files modified:** `.github/scripts/ci-job-consistency.cjs`, `.github/scripts/ci-job-consistency.test.cjs`
**Commit:** c96bdb7
**Applied fix:** `extractStepIfs` now finds `if:` in all of these forms:
- on its own 8-space line, as before;
- on the step-start line (`      - if: …`);
- as a quoted key (`"if":` / `'if':`).

An `if:` with an empty value (the scalar sits on the next lines) is read like a folded block. If nothing parseable follows, it is recorded as an empty condition, which is not on the allowlist, so it is reported (fails closed). `name:` on the step-start line was already handled.

**Regression tests (6, all failed before the fix):** `- if: false`, `- if: ${{ false }}` and `- if: >-` (folded), each applied to the real `ci.yml` ("Fail if tests failed" in the `test` job) and to the real `review-acceptance.yml`.

**Status:** fixed: requires human verification (parser logic change)

### WR-01: Readiness trusts the reviewed head's own runner output to decide whether base cross-grading was needed

**Files modified:** `.github/scripts/acceptance-readiness.cjs`, `.github/scripts/acceptance-readiness.test.cjs`
**Commit:** 27eb566
**Applied fix:**
- `runCli` recomputes the audited-input change set itself. It runs `git diff --name-only <base>..<head> -- <AUDITED_INPUTS>` as an argument array with no shell, after checking that both SHAs are 40-hex. If git cannot answer (for example, the commits are not fetched locally), readiness stops with exit 1 rather than continuing (fails closed).
- `codexStatusFor` combines that recomputed set with the meta's claim, so the head's runner can no longer talk the base cross-grade away.
- `meta.head === head` and `meta.base === base` are now mandatory, not conditional.
- A new `AUDITED_INPUTS` constant is exported, and a drift test pins it to `tests/codex_review_run.py`.
- Existing readiness fixtures gained `meta.base`, and the CLI exec tables gained the git-diff call.

**Regression tests (6, all failed before the fix):**
- the drift test;
- a recomputed change overrides a meta that claims none;
- a meta without `head` is never complete;
- a meta with a wrong or missing `base` is never complete;
- the CLI blocks when meta hid a changed grader;
- the CLI fails closed when the diff cannot be computed.

**Operational note:** readiness now needs the PR's base and head commits in the local clone, because `git diff` must be able to resolve both. If they are missing, it fails closed with "could not compute audited-input changes". `docs/owner-cli-acceptance.md` does not mention this yet, and a doc update was left out to keep the change narrow.

The reviewer also cited `codex-fallback.cjs:215-227` here. No change was needed there for WR-01: in that CLI a meta that falsely claims "complete" only blocks the fallback ("Codex is complete; a fallback is not used"), so it cannot be used to get past the check.

**Status:** fixed: requires human verification (trust/logic change)

### WR-02: A fallback record is never bound to the Codex output it is validated against

**Files modified:** `.github/scripts/codex-fallback.cjs`, `.github/scripts/codex-fallback.test.cjs`
**Commit:** f818fb3
**Applied fix:**
- `validateFallback` now rejects a record whose `codex_out` is not exactly `codexStatus.out` ("fallback codex_out does not match the Codex output checked"). A missing `codexStatus.out` never matches.
- `codexStatusFromOutput` now returns `meta.head`.
- The `validate` CLI exits 1 with "Codex output is for a different head" when that value is not `--head`, including when it is absent.
- On the readiness side, the head binding is covered by WR-01's mandatory `meta.head` check.

**Regression tests (4, all failed before the fix):**
- a `codex_out` that names the right head but a different attempt;
- a missing `codexStatus.out`;
- CLI meta for a different head;
- CLI meta with no head.

**Status:** fixed: requires human verification (logic change)

### WR-03: Empty `--test-exit` is recorded as a passing test run

**Files modified:** `.github/scripts/coverage-provenance.cjs`, `.github/scripts/coverage-provenance.test.cjs`
**Commit:** d6d83d0
**Applied fix:** A new `intArg` helper accepts only `^\d+$`. Both `write` and `write-local` use it for `--test-exit` and `--test-seconds`, so an empty value (an unset step output), `abc`, `-1`, `1.5`, ` 0` or `0x0` now fails with exit 1 and no provenance file is written.

**Behaviour change in CI:** if `steps.pytest.outputs.test_exit` is ever empty, the "write provenance" step itself now fails instead of uploading a file that says the tests passed. A real non-zero pytest exit is still written as evidence, as before.

**Regression tests (8, all failed before the fix):** six bad `--test-exit` values on `write`, an empty `--test-seconds` on `write`, and an empty `--test-exit` on `write-local`.

**Status:** fixed

### WR-04: A termination signal outside the Codex step leaves a reserved attempt with no status file

**Files modified:** `tests/codex_review_run.py`, `tests/test_codex_review_run.py`
**Commit:** e89c534
**Applied fix:** After the reservation, `execute()` now also has an `except BaseException` branch. It catches `SystemExit` raised by the SIGTERM/SIGHUP handler, and `KeyboardInterrupt`. If no `.status.json` exists yet, it writes an incomplete stub, "interrupted by <SIGNAME|KeyboardInterrupt> after reserving the output", then re-raises the original exception unchanged, so the exit code is unaffected. A failed stub write only prints a warning, so it cannot replace the original exit.

`tests/codex_review_run.py` is an audited Codex input. The owner allowed this edit. `tests/codex_report_status.py` was not changed.

**Regression tests (5):**
- a signal during pytest (SIGTERM) and during `git worktree add` (SIGHUP);
- a signal before the scratch directory exists;
- `KeyboardInterrupt` during pytest;
- a guard that a signal during the base grader does not overwrite the head checker's recorded status.

The first four failed before the fix. The guard passed before and after, as intended.

**Residual:** there is a very small window, between `reserve_outputs()` returning and the `try` being entered, that this does not cover. `reserve_outputs` cannot go inside the `try`, because a `FileExistsError` there belongs to another run's reservation and must not get a stub. A signal during the base grader still leaves no `.base-status.json`. That case already fails closed: a missing base status is treated as incomplete, and `.status.json` exists, so the fallback path still works.

**Status:** fixed

## Final gate (run after all six fix commits, at e89c534)

| Command | Result |
|---------|--------|
| `uv run pytest tests/ -x -q` | 2569 passed, 0 failed (38 warnings, pre-existing) |
| `uv run ruff check triggarr/ tests/ .github/scripts/` | All checks passed |
| `FORCE_COLOR=0 node --test --test-reporter=tap .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs` | 356 tests, 356 pass, 0 fail |
| `actionlint` | exit 0, no findings |

Working tree is clean apart from this report, which is left for the orchestrator to commit. Nothing was pushed.

**Review-workflow note:** these fixes change the commit under review, from `b4a47b6` to `e89c534`. Under the project's review workflow (CLAUDE.md), the post-fix BM review and its paired independent Codex pass must run on the new head. The Codex/vibe-check evidence recorded for `b4a47b6` does not cover these commits.

---

_Fixed: 2026-10-27T19:20:04Z_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 1_
