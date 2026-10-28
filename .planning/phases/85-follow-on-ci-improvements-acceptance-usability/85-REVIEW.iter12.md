---
phase: 85-follow-on-ci-improvements-acceptance-usability
reviewed: 2026-10-28T20:51:03Z
reviewed_head: 07c22c3bc16c4fec8d6031e4d6724f289a5ffa2f
diff_base: 44d34e231b2789f7927c5b89e84e4723a00733bc
iteration: 12
depth: standard
files_reviewed: 1
files_reviewed_list:
  - tests/test_codex_review_run.py
findings:
  critical: 0
  warning: 0
  info: 6
  total: 6
status: issues_found
---

# Phase 85: Code Review Report (iteration 12, confirming the iteration-11 WR-02 and IN-08 fixes)

**Reviewed:** 2026-10-28T20:51:03Z (head `07c22c3bc16c4fec8d6031e4d6724f289a5ffa2f`, diff base `44d34e231b2789f7927c5b89e84e4723a00733bc`)
**Depth:** standard
**Files Reviewed:** 1
**Status:** issues_found (info items only, all carried; no blocker, no warning)

## Summary

Scope: `git diff 44d34e2..07c22c3 -- tests/test_codex_review_run.py`, which is commit 07c22c3. The diff has two hunks: the fixture docstring (lines 48-52) and the `cwd` of the process-group signal child (line 2006).

Verification on this tree:
- `uv run ruff check tests/test_codex_review_run.py`: clean.
- `uv run pytest tests/test_codex_review_run.py -k kills_active_process_group`: 2 passed.
- `git status` is clean after the run, so the child wrote nothing into the checkout.

**Iteration-11 WR-02: resolved.** `_assert_signal_kills_active_process_group` now starts its child with `cwd=runner.HARNESS_ROOT`. That matches the mid-Codex harness at line 2372. Both `python -c` children now get this checkout as `sys.path[0]`, so `from tests import codex_review_run` loads the code under review and does not depend on where the editable install's `.pth` file points. `HARNESS_ROOT` is `Path(__file__).resolve().parent.parent` (`tests/codex_review_run.py:70`), which is the checkout root. The autouse fixture does not patch it. I checked whether the move has side effects. The child script (lines 1952-1967) writes only to `pid_file`, which is an absolute path under `tmp_path`, and it runs `sleep 60`. It writes nothing relative to its working directory, so starting it at the real checkout leaves nothing behind. No `cwd=runner.REPO_ROOT` remains in the module. The only other `cwd=` (line 157) is a test-local `repo`.

**Iteration-11 IN-08: resolved.** The docstring now says REPO_ROOT is "the output root and the cwd for commands the fake runner intercepts; the harness code itself stays at HARNESS_ROOT." That is accurate, and it no longer suggests REPO_ROOT is safe to use for real commands. It does not mention the checker path (413) or the `<repo>` redaction entry (665), but those follow from "output root" and are covered by `test_checker_argv` re-pinning the root. Not worth a new finding.

**Regressions:** none found in this diff.

## Structural Findings (fallow)

No structural findings were provided for this run.

## Narrative Findings (AI reviewer)

## Info

### IN-09 (carried from iteration 11): Seven now-redundant `monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)` lines remain

**File:** `tests/test_codex_review_run.py:332, 496, 628, 671, 686, 1101, 1241` (also 2392; line numbers are +1 from iteration 11 because of the longer docstring)
**Issue:** Unchanged from iteration 11. These lines are harmless, because the fixture already set the same value. They now read as if the test had to opt out of the real checkout, which is no longer true.
**Fix:** Optional. Remove them, or leave them as explicit documentation. Do not change behavior either way.

### IN-05 (carried from iteration 9): The pins file header points to evidence in a phase folder that will be archived, and nothing checks its "checked" date

**File:** `.github/tool-pins.env:1-5` (not in this round's scope)
**Issue:** Recorded as in iteration 9. Not re-raised.

### IN-03 (carried from iteration 8): The drain-timeout fallback decodes as UTF-8 and ignores the caller's `encoding`, `errors` and newline handling

**File:** `tests/codex_review_run.py:211-222` (not in this round's scope)
**Issue:** Recorded as in iteration 8. Not re-raised.

### IN-04 (carried from iteration 8): The new end-to-end test assumes the child prints within one second

**File:** `tests/test_codex_review_run.py:2079-2111` (line numbers before b272d82; about +11 at 07c22c3; not in this round's scope)
**Issue:** Recorded as in iteration 8. Not re-raised.

### IN-01 (carried from iteration 7, owner left out of scope): The Node detector's quoted-key support misses YAML escape spellings

**File:** `.github/scripts/ci-job-consistency.cjs:589-596` (not in this round's scope)
**Issue:** Recorded as in iteration 7. Not re-raised.

### IN-02 (carried from iteration 7, owner left out of scope): Run-splitting logic is duplicated

**File:** `.github/scripts/codex-fallback.cjs:63-79, 99-111, 133-137` (not in this round's scope)
**Issue:** Recorded as in iteration 7. Not re-raised.

## Resolved this iteration (not counted)

- **WR-02 (iteration 11):** The SIGTERM/SIGHUP process-group child ran in `tmp_path` and imported the runner through the editable install's `.pth` file, not from the checkout under review. Resolved by 07c22c3, which uses `cwd=runner.HARNESS_ROOT`.
- **IN-08 (iteration 11):** The fixture docstring said REPO_ROOT was "only the output root". Resolved by 07c22c3, which says it is also the cwd for intercepted commands and that harness code stays at HARNESS_ROOT.

## Accepted residuals (carried, not counted)

### Iteration-7 WR-01: Run-together reviewer names typed in one case (`claudecode`, `bmreviewer`, `gsdagent`, `codexreviewrun`) still pass

**File:** `.github/scripts/codex-fallback.cjs:113-137`
**Status:** The owner accepted this as a residual after iteration 7. Recorded here for continuity. Not re-raised, and not counted in `findings`.

## Set aside (needs ruling)

### SA-11 (carried from iteration 11): No test covers `main()`'s "phase-dir does not exist" refusal

Unchanged from `85-REVIEW.iter11.md`. Still needs a ruling on whether to add the one-line `SystemExit(2)` test in this phase or defer it.

### SA-10 (carried from iteration 10): The fixture copies and the phase-83 originals can drift apart

Unchanged from `85-REVIEW.iter10.md`.

### SA-08 (carried from iteration 9): resolved by b272d82

Unchanged from `85-REVIEW.iter10.md`.

### SA-09 (carried from iteration 9): `.github/tool-pins.env` is not on the sensitive-path list

Unchanged from `85-REVIEW.iter9.md`.

### SA-07 (carried from iteration 8): When stderr is not captured, `exc.stderr` gets a made-up drain marker

Unchanged from `85-REVIEW.iter8.md`.

### SA-01 to SA-06 (carried from iteration 7)

Unchanged from `85-REVIEW.iter7.md`: SA-01 (acceptance runs on the gate it introduces), SA-02 (register schema cutover strands open PRs), SA-03 (Dependabot `uv` has no cooldown), SA-04 (a runner-changing PR can certify its own base cross-grade; owner-recorded follow-up), SA-05 (reusable workflows and local actions are not inspected; owner-recorded follow-up), SA-06 (digit splitting creates initial-like false positives; inside the accepted residual). This commit does not touch any of them.

---

_Reviewed: 2026-10-28T20:51:03Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
