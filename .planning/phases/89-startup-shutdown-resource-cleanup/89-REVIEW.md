---
phase: 89-startup-shutdown-resource-cleanup
reviewed: 2026-11-18T00:00:00Z
depth: standard
iteration: 4
files_reviewed: 2
files_reviewed_list:
  - tests/test_scheduler.py
  - triggarr/search/scheduler.py
findings:
  critical: 0
  warning: 0
  info: 2
  total: 2
status: issues_found
---

# Phase 89: Code Review Report (round 4)

**Reviewed:** 2026-11-18
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found (info only; no critical or warning findings)

## Summary

This round re-reviews the full phase diff (`git diff b4a25aa1..HEAD -- triggarr/ tests/`) at HEAD 6e4753f1
(code head 9ec53d89). It focuses on the one code commit since round 3, 9ec53d89. That commit adds a `reason`
argument to `_observe_abandoned_close` and an `abandon_reason` local in `_safe_close`, so the DEBUG line for an
abandoned close says "ended after the cap" when the wait timed out and "ended after the caller was cancelled" when
`_safe_close` itself was cancelled.

**The commit is correct and causes no regressions:**

- **Timeout path:** `asyncio.wait` returns with the task not done. `abandon_reason` keeps its initial
  "the cap", and the `finally` attaches the callback with that value. The WARNING "did not close within" still
  fires. The existing test `test_safe_close_observes_late_failure_of_abandoned_close` still asserts the exact
  "ended after the cap (RuntimeError)" line, and it passes.
- **Cancellation path:** the `except asyncio.CancelledError` branch sets the reason before the `finally` runs. That
  ordering is guaranteed because the `except` body runs before `finally`, including when it re-raises. The
  callback therefore receives "the caller was cancelled". The re-raise, the close order and the redaction
  (`_sanitize_exc` / type name only, never `str(exc)`) are unchanged.
- **Binding the reason:** `functools.partial` binds the reason by value at attach time, so a later change to the
  local cannot affect it. The callback's argument order matches the new signature, and `task` is still the
  argument the callback receives. `_observe_abandoned_close` has no other callers (checked with grep).
- **Logging safety:** `reason` comes from one of two fixed strings, never from user data or exception text, so no
  secret can reach the log through it.

**Tests and lint:** I re-ran both at 9ec53d89. `tests/test_scheduler.py` passes (88 passed, 1 warning), and
`ruff check triggarr/ tests/` reports "All checks passed!". These results match the orchestrator's run.

**Not re-raised:** the backlogged items IN-01..IN-06, SA-01, SA-02 and DR-01 in `.planning/backlog/MAINTENANCE.md`
are unchanged by this commit. One effect is left as it was: on the cancellation path, the abandoned close is still
recorded only at DEBUG, with no WARNING. That is part of DR-01's behavior, and the updated docstring now states it
("a timed-out step was already reported once at WARNING").

## Info

### IN-01: The new "the caller was cancelled" wording has no test

**File:** `triggarr/search/scheduler.py:541`, `tests/test_scheduler.py:2558-2609`
**Issue:** No test exercises the branch that 9ec53d89 introduced. The only cancellation test,
`test_safe_close_retrieves_close_failure_when_caller_is_cancelled` (line 2558), sets `gate` before cancelling. The close has therefore
already finished, nothing is abandoned, and `_observe_abandoned_close` never runs. Only the "the cap" string is
asserted (line 2553). If the assignment at line 541 were removed or misplaced, the suite would still pass. This
is the same untested path DR-01 describes, now carrying a log string that is meant to be distinct. The effect is
limited to the wording of a DEBUG line.
**Fix:** Add a test that cancels the helper while `close_fn` is still parked on `gate`. It should assert the DEBUG
line `"DEBUG | Shutdown: abandoned close of database ended after the caller was cancelled (cancelled)"` and that
`_ABANDONED_CLOSE_TASKS` is empty afterward. This test can be folded into the DR-01 work, because that fix
changes this path anyway.

### IN-02: "the cap" is the default reason for any non-timeout exit, not just the timeout

**File:** `triggarr/search/scheduler.py:537-556`
**Issue:** `abandon_reason` starts as "the cap" before the wait, and only `CancelledError` overrides it. If
`asyncio.wait` exits with any other `BaseException` (for example `KeyboardInterrupt` or `SystemExit` raised inside
the loop), the task is abandoned and the DEBUG line says "ended after the cap", although no cap fired. In that case
the "did not close within" WARNING is skipped, because the exception propagates before it. This is the same kind of
inaccuracy the commit set out to fix, in a narrower and rarely reached case.
**Fix:** Assign "the cap" only where a timeout is actually known. For example, initialise
`abandon_reason = "the caller was interrupted"` and set `abandon_reason = "the cap"` right after a successful
`asyncio.wait` return. Alternatively, keep the current default and add a comment stating that a non-cancellation
`BaseException` from the wait is not distinguished.

## Set aside (needs ruling)

None.

---

_Reviewed: 2026-11-18_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
