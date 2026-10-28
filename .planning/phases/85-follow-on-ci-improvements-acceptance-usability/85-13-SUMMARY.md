---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "13"
subsystem: testing
tags: [codex-review, trust-boundary, subprocess, D-18, review-machinery]

# Dependency graph
requires:
  - phase: 85-follow-on-ci-improvements-acceptance-usability (85-03, 85-04)
    provides: Signal-safe process-group cleanup, bounded post-kill drain, and the D-18 hollow-report guard this plan builds the trust boundary and base-grader on top of
provides:
  - "verify_trust(): an independently-verified trust boundary for --trusted (GitHub PR ownership via gh pr view, or every commit in a local checkpoint having a local `commit` reflog entry on this machine) — the operator's own flag, branch membership and author/committer email never establish trust on their own"
  - "--untrusted now records a permanent INCOMPLETE result (meta.json review_mode \"untrusted-refused\", status.json incomplete) and exits 2, instead of silently refusing with no record at all"
  - "audited_inputs_changed_in_diff + materialize_grader()/base-commit cross-grading: a diff that changes the checker/schema/prompt/runner is never the only grader of its own PR"
affects: ["85-14 (readiness/fallback validator binds to the untrusted-refused record)", "85-17 (contract/record docs for trusted mode, .base-status.json and the fallback)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "verify_trust(run, command_runner) dispatches on run.pr_url (LOCAL_CHECKPOINT_PR_URL vs a github.com/.../pull/N match) to one of two independently fail-closed checks, both gated behind a shared --base-on-origin/main requirement"
    - "materialize_grader(grader_ref, dest, command_runner) writes graders from git objects only (git show <ref>:<path>), never from a worktree of the reviewed head"

key-files:
  created: []
  modified:
    - tests/codex_review_run.py
    - tests/test_codex_review_run.py

key-decisions:
  - "UNTRUSTED_REFUSAL's wording and the .status.json reason it produces are two different strings (UNTRUSTED_STATUS_REASON) — the plan's exact quoted refusal text and the behavior spec's two required status-reason substrings don't share a common superstring, so printing one and recording the other was the only way to satisfy both verbatim"
  - "_tmp_run's tempfile.mkdtemp fake was fixed to one directory regardless of prefix; this silently collapsed the base-grader's temp dir onto the worktree's scratch dir once Task 2 needed a second, distinct mkdtemp call in the same run — fixed to key off the prefix"

requirements-completed: [ACCEPT-01]

# Metrics
duration: ~50min
completed: 2026-10-27
---

# Phase 85 Plan 13: Codex Runner Trust Boundary and Base-Grader Cross-Check Summary

**`verify_trust()` independently checks `--trusted` against GitHub PR ownership or this machine's own commit reflog (never the operator's assertion, branch membership, or email); `--untrusted` now records a permanent INCOMPLETE result instead of refusing silently; a diff that changes the checker/schema/prompt/runner is cross-graded by the base commit's own checker before the run can report clean.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 2 completed
- **Files modified:** 2 (`tests/codex_review_run.py`, `tests/test_codex_review_run.py`)

## Accomplishments

- `verify_trust()` (D-18 SA-01): a PR is trusted only if `gh pr view` reports it same-repository, non-bot, authored by someone in `TRUSTED_AUTHORS`, with the given `--head`/`--base`; a local checkpoint is trusted only if every commit in `base..head` has a reflog line on this machine whose subject starts with `commit` (plain/amend/merge/initial) — fetched, cherry-picked, rebased or reset-to commits fail closed. Author/committer email is never read for trust. Both forms also require `--base` to already be an ancestor of `refs/remotes/origin/main` before anything executes, so the base-commit grader (below) is always materialized from code already on this repository's main, never from a PR-supplied base (checker B13).
- `verify_trust()` runs at the top of `execute()`, before the existing-output check, so a refused head (bot, fork, or an un-committed-here checkpoint) writes no file and runs no command.
- `--untrusted` (interim rule, D-07 amendment 2026-10-27): no longer routes through `execute()`. It validates its arguments with zero command-runner calls, then writes exactly two files — `<OUT>.meta.json` (`meta_version` 2, `review_mode` "untrusted-refused", `trust_verification` null, `test_evidence_source` null) and `<OUT>.status.json` (always `"incomplete"`, naming Phase 85.1 and the D-16 owner-approved fallback) — prints `UNTRUSTED_REFUSAL`, and exits 2. `execute()` still raises `RunnerError(UNTRUSTED_REFUSAL)` for an untrusted `ReviewRun` as defense in depth, but is never reached by the CLI path.
- `audited_inputs_changed()` records the sorted `AUDITED_INPUTS` paths that changed between `--base` and `--head` as `meta["audited_inputs_changed_in_diff"]`. When non-empty, `materialize_grader()` writes the checker and schema exactly as they exist at the base commit (`git show <base>:<path>` only) into a scratch dir, and the same report is cross-graded with that base-commit checker, saved as `<OUT>.base-status.json`. The run reports complete (exit 0) only if the head-side checker says complete *and*, when a grader changed, the base checker agrees. A base commit with no checker to cross-grade against is an incomplete `.base-status.json` with a specific reason, never a silent pass.
- `meta_version` bumped to 2; `run_meta()` gains `review_mode`, `trust_verification`, `test_evidence_source`, `audited_inputs_changed_in_diff`, `base_grader_ref` (= `run.base`) and `base_grader_source` ("base") — the full interface contract Plans 85-14 and 85-17 depend on.
- `--dry-run` previews the trust-verification commands (`--trusted`) or the two file paths that would be written (`--untrusted`) without running or writing anything.

## Task Commits

Both tasks followed RED -> GREEN, with one test-infrastructure correction commit discovered mid-GREEN for each:

1. **Task 1: A verifiable trust boundary for --trusted**
   - `30ff5ff` test(85-13): add failing trust-boundary tests, including one fork commit through both paths
   - `e6eb5e3` test(85-13): defer materialize_grader defense-in-depth check to Task 2
   - `dcf0b13` feat(85-13): verify --trusted against PR ownership or local commit origin; record --untrusted as INCOMPLETE (D-18 SA-01, D-07 interim)
2. **Task 2: audited_inputs_changed_in_diff and a base-commit grader**
   - `e302937` test(85-13): add failing audited-inputs and base-grader tests
   - `80d2f7a` test(85-13): make _tmp_run's mkdtemp fake respect the caller's prefix
   - `fc34da2` feat(85-13): record changed graders and cross-grade with the base checker (D-18)

Plan-start SHA (base for this plan's execution): `f992a17d46deada6afb4782de0796a75328f3d19`.

## Files Created/Modified

- `tests/codex_review_run.py` — `REPO_SLUG`, `TRUSTED_AUTHORS`, `GRADER_FILES`, `_PR_URL_RE`, `LOCAL_COMMIT_SUBJECT_RE`, `LOCAL_CHECKPOINT_PR_URL` added; `verify_trust()` / `_verify_trust_pr()` / `_verify_trust_local()` / `_require_base_on_main()` added and called from `execute()`; `UNTRUSTED_REFUSAL` rewritten, `UNTRUSTED_STATUS_REASON` added, `_untrusted_main()` added and wired into `main()` in place of the old inline refusal; `untrusted_refused_meta()` added; `run_meta()` gains `review_mode`/`trust_verification`/`test_evidence_source`/`audited_inputs_changed_in_diff`/`base_grader_ref`/`base_grader_source`, `meta_version` bumped to 2; `audited_inputs_changed()`, `materialize_grader()`, `_run_base_grader()`, `_write_base_status_stub()` added; `OUTPUT_SUFFIXES` gains `.base-status.json`; `_execute_reserved()` cross-grades with the base checker when the diff changed a grader; `dry_run()` previews trust-verification commands; module docstring updated.
- `tests/test_codex_review_run.py` — `FakeRunner` extended to answer the local-checkpoint trust commands by default (`TRUSTED_BRANCH_REF`, `trust_fail_on`); new PR-form (`_TrustRunner`) and local-checkpoint-form (`_LocalTrustRunner`) unit-test harnesses for `verify_trust()` covering every rejection reason plus the same-fork-commit-through-both-paths regression (checker B05); rewritten `--untrusted` tests for the new two-file INCOMPLETE record; `_tmp_run`'s `mkdtemp` fake fixed to respect the caller's prefix; new tests for `audited_inputs_changed_in_diff` (unchanged / changed+both-complete / changed+base-incomplete / base-missing) and the base-grader's exact-ref materialization.

## Decisions Made

- `UNTRUSTED_REFUSAL` (printed verbatim to stdout, exact plan-quoted text) and `UNTRUSTED_STATUS_REASON` (the `.status.json` reason, required to contain two specific substrings) are deliberately two different strings — see key-decisions above.
- `commits_checked` in `trust_verification` is `None` for the PR form (GitHub's own report is the unit of trust, not a per-commit count) and the actual commit count for the local-checkpoint form.
- `base_grader_ref`/`base_grader_source` are recorded in every trusted run's meta unconditionally (a static fact about where the trusted path's grader would come from), not only when `audited_inputs_changed_in_diff` is non-empty.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_tmp_run`'s `tempfile.mkdtemp` fake ignored the `prefix` argument**
- **Found during:** Task 2, restoring the base-grader implementation and running `test_changed_grader_both_complete_exits_clean`
- **Issue:** `_tmp_run` monkeypatched `tempfile.mkdtemp` to a lambda returning the same `tmp_path / "scratch"` directory for any prefix. Once `_run_base_grader` made a second `tempfile.mkdtemp(prefix="codex-base-grader-")` call in the same `execute()` run, it collapsed onto the identical (already-removed-by-then) path the worktree had just used, and the resulting path string never contained "base-grader" — so tests asserting the base checker actually ran (via a `"base-grader" in str(part)` check) silently fell through to the head-checker's default response instead.
- **Fix:** `_mkdtemp` now creates (and returns) a directory named for the prefix itself, keeping `"codex-review-"` mapped to the long-established `"scratch"` name so every pre-existing test's hardcoded path kept working, while any other prefix gets its own distinct directory.
- **Cost if wrong:** Every "changed grader, base checker ran" test would silently pass by accident (actually exercising the head-checker's fallback path a second time), so a real bug where the base checker never runs at all would go undetected — exactly the self-grading gap this plan exists to close.
- **Files modified:** tests/test_codex_review_run.py
- **Commit:** `80d2f7a`

---

**Total deviations:** 1 auto-fixed (Rule 1 bug, discovered via the plan's own new regression tests)
**Impact on plan:** Necessary for the base-grader tests to actually exercise what they claim to; no scope creep.

## Assumption Drift (advisory)

- **Found during:** Task 1, writing the `.status.json` reason for `--untrusted`
- **Planned:** The plan's action text gives one exact `UNTRUSTED_REFUSAL` string and separately requires the recorded `.status.json` reason to contain two specific substrings ('refused until Phase 85.1' and 'owner-approved fallback (D-16)'); read together this reads as "use the same string for both."
- **Actual:** Those two requirements don't compose into one string (`UNTRUSTED_REFUSAL`'s own wording is "fallback review (D-16, ...)", not "fallback (D-16)"), so a separate `UNTRUSTED_STATUS_REASON` constant satisfies the status-reason substrings exactly while `UNTRUSTED_REFUSAL` is printed to stdout exactly as quoted.
- **Why:** Discovered by running the test against the real implementation and finding the substring assertion failed on the literal UNTRUSTED_REFUSAL text.
- **Cost if wrong:** None functionally — both strings convey the same refusal; a downstream plan grepping `.status.json` for a different exact phrase than `UNTRUSTED_STATUS_REASON` would need updating, but no doc commits to the status-reason's exact wording yet (docs are Plan 85-17's job).

## Issues Encountered

- Running the orchestration test suite twice against an intermediate, not-yet-isolated version of the new `--untrusted` tests left two real files (`aaaaaaaaaaaa-explicit-a1.meta.json`/`.status.json`) under the real `.planning/phases/83-.../codex/` directory (gitignored, untracked) before the test's `REPO_ROOT` monkeypatch was added. Found via `git status --ignored` and removed; no tracked file was touched.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `tests/codex_review_run.py`'s trust boundary and base-grader cross-check are complete and independently tested. Plan 85-14 (readiness/fallback validator) can bind to the recorded `untrusted-refused` INCOMPLETE record for a bot or fork head; Plan 85-17 writes the contract/record docs describing trusted mode, `.base-status.json` and the D-16 fallback — not touched by this plan by design.
- `UNTRUSTED_REFUSAL` names `.github/scripts/codex-fallback.cjs`, which does not exist yet in this repository; it is forward-referenced text for a script a sibling plan (85-14) creates, not a runtime dependency of this plan's code.
- All 288 tests across `tests/test_codex_review_run.py` + `tests/test_codex_report_status.py` + `tests/test_codex_review_contract.py` pass; `uv run ruff check tests/` is clean; the full repository suite (2509 tests) passes; `uv run ruff check triggarr/ tests/` is clean.
- No blockers for downstream plans in this wave.

## Self-Check: PASSED

- FOUND: tests/codex_review_run.py
- FOUND: tests/test_codex_review_run.py
- FOUND: .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-13-SUMMARY.md
- FOUND commit: 30ff5ff (test(85-13): add failing trust-boundary tests, including one fork commit through both paths)
- FOUND commit: e6eb5e3 (test(85-13): defer materialize_grader defense-in-depth check to Task 2)
- FOUND commit: dcf0b13 (feat(85-13): verify --trusted against PR ownership or local commit origin; record --untrusted as INCOMPLETE (D-18 SA-01, D-07 interim))
- FOUND commit: e302937 (test(85-13): add failing audited-inputs and base-grader tests)
- FOUND commit: 80d2f7a (test(85-13): make _tmp_run's mkdtemp fake respect the caller's prefix)
- FOUND commit: fc34da2 (feat(85-13): record changed graders and cross-grade with the base checker (D-18))

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*
