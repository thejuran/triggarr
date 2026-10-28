---
phase: 85-follow-on-ci-improvements-acceptance-usability
reviewed: 2026-10-28T19:09:46Z
reviewed_head: 2f2e8fceb11bb603c9f85aef3694d6d68feb106f
diff_base: 7ee594a3caf19c1bebff923c69b09b821bdd212f
iteration: 8
depth: standard
files_reviewed: 2
files_reviewed_list:
  - tests/codex_review_run.py
  - tests/test_codex_review_run.py
findings:
  critical: 0
  warning: 0
  info: 4
  total: 4
status: issues_found
---

# Phase 85: Code Review Report (iteration 8, confirming the Codex F001 fix)

**Reviewed:** 2026-10-28T19:09:46Z (head `2f2e8fceb11bb603c9f85aef3694d6d68feb106f`, diff base `7ee594a3caf19c1bebff923c69b09b821bdd212f`)
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found (info only; no new blocker or warning)

## Summary

Scope: `git diff 7ee594a..2f2e8fc`, which is commit 2f2e8fc only. It changes `_with_drain_marker` in `tests/codex_review_run.py` and adds two tests. I read `run_command`, `_run_pytest` and `_run_codex` in full for context.

Verification on this tree:
- `uv run pytest tests/test_codex_review_run.py -q`: 153 passed
- `-k drain` run 5 times in a row: 3 passed every time (about 12 s each)
- `uv run ruff check tests/`: clean
- `gsd-tools verify conventions --check` on both files: no findings
- **Proof that the tests catch the bug:** I copied the new test file onto a worktree at 7ee594a (the code before the fix). Both new tests fail there with `TypeError: can't concat str to bytes` at `codex_review_run.py:214`. The older `test_post_kill_drain_is_bounded` passes on both versions. Its child prints nothing, so `drain_exc.stdout` is `None` and the faulty concatenation never ran. That explains how F001 got past the earlier tests.

**Codex F001 is fixed.** The cause was this: CPython's `communicate()` builds `TimeoutExpired.output` from raw byte chunks even in text mode. Before the fix, any text-mode drain timeout that had captured some output raised `TypeError` from inside run_command's `except` handler. `_run_pytest` catches only `TimeoutExpired` and `OSError`, so the runner crashed instead of writing pytest evidence that says "timed out". Now the bytes are decoded first, and the result is the caller's type in all four combinations (bytes or str or None, text or binary mode). The new end-to-end test uses a child that prints and then leaves behind a detached grandchild holding the pipe. That is the real F001 trigger, and the test passes.

Regression checks on the timeout paths:
- **First timeout, drain succeeds:** unchanged. `exc.stdout` comes from the second `communicate()`, which decodes it correctly. The partial output the first call had already read is kept, because CPython stores it on the Popen object, so the drain returns everything. The new test confirms this: `"pytest progress"` is printed before the kill and still appears in the result.
- **First timeout, drain times out:** `exc.stdout` is now `str` in text mode, so `_run_pytest`'s `isinstance(captured, bytes)` branch is no longer needed but still safe. The original `exc` is re-raised, so callers still see the first timeout's `timeout` value.
- **`_run_codex`:** passes `stdout=events` (a file), so `drain_exc.stdout` is `None`. It gets the marker only and ignores it. No change in behavior.
- **`BaseException` branch and `Popen.__exit__`:** not touched. `__exit__`'s unbounded `wait()` comes after the group kill, so it only waits for the already-killed direct child, not the detached grandchild. No new hang.
- **Binary-mode branch** (`str` → encoded): no current caller can reach it. It is harmless and covered by the unit test.

## Structural Findings (fallow)

No structural findings were provided for this run.

## Narrative Findings (AI reviewer)

## Info

### IN-03: The drain-timeout fallback decodes as UTF-8 and ignores the caller's `encoding`, `errors` and newline handling

**File:** `tests/codex_review_run.py:211-222`
**Issue:** When the drain succeeds, Python decodes the output with the caller's `encoding` (default: the locale encoding) and `errors`, and converts `\r\n` to `\n`. When the drain times out, the new fallback always decodes as UTF-8 with `errors="replace"` and keeps `\r\n` as is. So the same pytest output can come out slightly differently depending on which path ran. The code comment says "like every other captured output", which is true for `_run_pytest` (`errors="replace"`, and the locale is UTF-8 on the macOS and Linux runners), but not in general. Today this has no effect: the only text-mode caller with a pipe is `_run_pytest`, its output is close to ASCII, and a stray `\r` only affects how the evidence file looks.
**Fix:** Pass the caller's settings through so the fallback matches what `communicate()` would have returned, or narrow the comment:
```python
encoding = kwargs.get("encoding") or "utf-8"
errors = kwargs.get("errors") or "replace"
output = output.decode(encoding, errors).replace("\r\n", "\n").replace("\r", "\n")
```

### IN-04: The new end-to-end test assumes the child prints within one second

**File:** `tests/test_codex_review_run.py:2079-2111`
**Issue:** `timeout=1.0` has to cover three things before the kill: the child interpreter starting, the child's `Popen` of the grandchild, and the print. Locally this takes well under the limit (5 of 5 runs passed). On a heavily loaded CI runner, two Python start-ups can get close to a second. If they do, `"pytest progress"` is missing and the test fails even though the code is fine. The test still catches the F001 regression either way, because the `TypeError` needs the child to have printed something.
**Fix:** Print before starting the grandchild, and/or raise `timeout` to about 3 s. The drain is already limited to 0.5 s, so the test's run time barely changes.

### IN-01 (carried from iteration 7, owner left out of scope): The Node detector's quoted-key support misses YAML escape spellings

**File:** `.github/scripts/ci-job-consistency.cjs:589-596` (not in this round's scope)
**Issue:** Recorded as in iteration 7. Not re-raised.

### IN-02 (carried from iteration 7, owner left out of scope): Run-splitting logic is duplicated

**File:** `.github/scripts/codex-fallback.cjs:63-79, 99-111, 133-137` (not in this round's scope)
**Issue:** Recorded as in iteration 7. Not re-raised.

## Accepted residuals (carried, not counted)

### Iteration-7 WR-01: Run-together reviewer names typed in one case (`claudecode`, `bmreviewer`, `gsdagent`, `codexreviewrun`) still pass

**File:** `.github/scripts/codex-fallback.cjs:113-137`
**Status:** The owner accepted this as a residual after iteration 7. Recorded here for continuity. Not re-raised, and not counted in `findings`.

## Set aside (needs ruling)

### SA-07: When stderr is not captured, `exc.stderr` gets a made-up drain marker

**Where:** `tests/codex_review_run.py:262`
**Why excluded:** This was already the behavior before this commit, and nothing reads the value. With `stderr=subprocess.STDOUT` (pytest) or no stderr pipe (codex), `drain_exc.stderr` is `None`, and `_with_drain_marker` turns it into a bare marker string.
**Effect if left as is:** None today. A future caller that checks `exc.stderr` would see a "truncated" message for a stream that was never captured.
**Needs:** No ruling needed unless the owner wants it tidied. The fix is to apply the marker only when the stream was piped: `if drain_exc.stderr is not None or kwargs.get("stderr") == subprocess.PIPE`.

### SA-01 to SA-06 (carried from iteration 7)

Unchanged from `85-REVIEW.iter7.md`: SA-01 (acceptance runs on the gate it introduces), SA-02 (register schema cutover strands open PRs), SA-03 (Dependabot `uv` has no cooldown), SA-04 (a runner-changing PR can certify its own base cross-grade; owner-recorded follow-up), SA-05 (reusable workflows and local actions are not inspected; owner-recorded follow-up), SA-06 (digit splitting creates initial-like false positives; inside the accepted residual). This commit does not touch any of them.

---

_Reviewed: 2026-10-28T19:09:46Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
