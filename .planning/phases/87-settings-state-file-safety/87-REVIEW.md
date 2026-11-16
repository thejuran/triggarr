---
phase: 87-settings-state-file-safety
reviewed: 2026-11-16T00:47:35Z
depth: standard
iteration: 4
head: 0cb0f12e
files_reviewed: 3
files_reviewed_list:
  - triggarr/web/routes.py
  - tests/test_web.py
  - tests/test_config.py
findings:
  critical: 0
  warning: 0
  info: 2
  total: 2
status: issues_found
---

# Phase 87: Code Review Report (iteration 4, review after fix round 3)

**Reviewed:** 2026-11-16T00:47:35Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found (info only: no critical, no warning)
**Head reviewed:** `0cb0f12e` (fix round 3 diff base `ac5f01fe`; phase base `3cede400`)

The reports for iterations 1 to 3 (heads `6262dd14`, `f099c6a8`, `615a044a`) are in git history for this file.

## Summary

This is a review of fix round 3 (`git diff ac5f01fe..HEAD -- triggarr tests`, commits `b2c95594`, `beff1f34`, `82931b9a`) against the code itself, not against `87-REVIEW-FIX.md`.

**This iteration has no critical and no warning finding.** Under the owner's stopping rule there is nothing to fix. Two info items, both about tests, are listed for the backlog.

Iteration 3 WR-01 is fixed. When the operating system refuses the thread for the settings write, the queued write no longer runs later: the settings file keeps the instance, the running app is untouched, and the user's "was not removed" message stays true. The new guard between the route and the queued write was checked in every ordering, by reading and by running each one. No ordering was found that writes the file after a "not removed" answer, answers "not removed" after the file changed, leaves the request waiting forever, or blocks the event loop.

### Iteration 3 WR-01 verification

| Check | Result |
|---|---|
| Refused thread start, with the real loop, a real executor and the real writer | Holds. `test_remove_instance_refused_thread_start_does_not_write_later` refuses exactly one real thread start and mocks nothing above that. After a later successful use of the same executor the settings file is byte-for-byte unchanged and still has the instance, no temp file is left, and live settings, the scheduler job, the client and the state entry are untouched. One error entry, no other entry at warning level or above. |
| The test fails on the pre-fix code | Yes. The head tests were run against an exported copy of `ac5f01fe`: both variants fail there because the settings file lost the instance (the iteration 3 reproduction), and the third new test fails because the route answered at once. All pass at head. |
| The queued job, once called off, does nothing | Holds (`triggarr/web/routes.py:1049-1053`). It returns before touching the file. Nothing waits on its result in that case. |

### Round 3 review: the guard in every ordering

`write_gate` is held only to read or flip a flag (`:1051-1057` in the job, `:1070-1072` in the route), never across the file write.

| Ordering | Result |
|---|---|
| Normal success (no error) | Unchanged behavior. The route never looks at the flags. |
| Route first: thread start refused, no worker has the job | The route sets `write_abandoned` under the gate and sees `write_claimed` false. Fixed D-05 response, one error entry, live state untouched. The job returns without writing whenever it later runs. Covered by the new test and re-run here. |
| Job first, then succeeds (thread start refused while a busy worker picks the job up) | The route sees `write_claimed`, waits for the real result, and completes the removal. Probed here with the write both still running and already finished when the refusal reaches the route: success response, and the file, live settings, client registry, state entry and tag cache all agree that the instance is gone. Exactly one warning, no error. |
| Job first, then raises (same refusal, but the write fails) | Probed here with an `OSError` and a non-`OSError`, running and already finished: fixed D-05 response, file byte-for-byte unchanged, live state untouched, exactly one error entry naming the app, the instance and the write's reason, no warning. |
| The writer itself raises, job already finished (the ordinary failed save) | The route sees `write_claimed`; the awaited result is already set and is the same exception. One error entry, D-05 response. Behavior identical to before round 3. |
| Refused before queueing ("cannot schedule new futures after shutdown") | Nothing is queued, `write_claimed` is false, same as "route first". |

Other points the round was checked for:

| Check | Result |
|---|---|
| A path where the result is never set, so the request waits forever holding `search_lock` | None found. The route waits on `write_outcome` only after seeing `write_claimed`, and that flag is set in the same locked step that marks the result as running (`:1054-1057`). From there the job always ends in `set_exception` (`:1060-1062`, `BaseException`) or `set_result` (`:1063`). The result cannot be cancelled out from under the job: it is marked running before the route can wait on it. In the probes the lock was free after every request. |
| Anything blocking the event loop | No. The route takes `write_gate` on the loop thread, but the job holds it only for the flag flip. The wait for the result is `asyncio.wrap_future` (`:1078`), not a blocking call. Probed: the loop kept running for 300 ms while the write was held open and the request stayed unanswered. |
| The job's exception reported exactly once | Holds. One error entry on each failing path. No "exception was never retrieved" report reached the loop's exception handler in any probe, including after forced garbage collection. The copy of the exception left on `write_outcome` when nobody waits is on a `concurrent.futures.Future`, which does not log unretrieved exceptions. |
| Success after a refusal: consistency and logging | Holds (see the table above): one warning naming the app, the instance and the refusal; no error entry. |
| `CancelledError` still propagates | Holds. Both handlers catch `Exception` (`:1068`, `:1079`). Probed by cancelling the route during the write: `CancelledError` came out and the lock was released. What a cancelled request leaves behind is the recorded backlog item and was not re-examined. |
| D-05 response and D-07 single error entry on every failure path | Hold. Known exception, unchanged: if the write fails and deleting its temp file also fails, the writer logs a second error for the cleanup. |
| Lock audit | `tests/audit_lock_coverage.py`: covered 8 / 8. |
| Imports | `threading` and `concurrent.futures` are used; `functools` was removed with its only use. |

### New tests: reliability and isolation

- **Thread-start patch:** `patch.object(threading.Thread, "start", ...)` is a context manager in both tests and is undone on every exit. While active it only refuses a thread whose name starts with the test's own prefix, and only once; all other threads start normally.
- **Fresh default executor:** it is installed on the test's own event loop. The project does not set a shared loop scope, so each test gets a new loop, and closing that loop shuts its default executor down. It cannot reach another test. No default executor existed on the loop before the replacement, so nothing is orphaned.
- **Events:** both tests release their blocking events in `finally`, so a failed assertion cannot leave a worker thread waiting.
- **Repeat runs:** the three new tests plus the mock-based one were run 15 times in a row, with the full suite running at the same time for part of it: no failure.
- One timing assumption could cause a false failure on a very slow machine: IN-01.

### Checks run during this review (from the checkout, without writing to it)

- `pytest tests/` (full suite): 3330 passed, 1 skipped.
- An earlier full run with `-x` stopped at one failure in `tests/test_codex_review_run.py::test_sigterm_mid_codex_redacts_partial_outputs`. That file is not part of this phase. The test passed three times in isolation and in the complete run above. The cause was not investigated; it is noted here so it is not lost.
- `ruff check triggarr/ tests/`: all checks passed.
- Convention pack (`verify conventions --check`) on the three files: no findings (not skipped).
- Head tests against an exported copy of `ac5f01fe`: the three new tests fail, the two mock-based ones pass.
- A throwaway probe file outside the repo (10 cases, all passed): the six "job first" combinations above, the ordinary failed save with two exception types, cancellation during the write, and a timing measurement for IN-01.

Not verified: nothing was exercised in a browser. `triggarr/config.py`, `triggarr/state.py` and the templates are unchanged in round 3 and were not re-reviewed.

One thing outside the reviewed files, for whoever updates planning: the `.planning/backlog/MAINTENANCE.md` entry for the directory-handle close failure (SA-02) still says "no owner ruling yet". The ruling given for this iteration is backlog.

## Earlier-iteration dispositions

| Finding | Disposition | Verified | Notes |
|---|---|---|---|
| Iteration 3 WR-01: a removal write queued behind a refused thread start ran later, after the user was told nothing changed | Fixed | Yes | `triggarr/web/routes.py:1044-1102`. Reproduced as fixed with the real loop, executor and writer; all orderings of the guard checked. See the tables above. |
| Iteration 3 IN-01: Add Instance's "already exists" and "maximum 5" answers wait for a running search | Backlog | Yes | Recorded in `.planning/backlog/MAINTENANCE.md`. Code unchanged in round 3 (`:909-916`). |
| Iteration 3 IN-02: test docstring described the old `log_failure` behavior | Fixed | Yes | `tests/test_config.py:924-935` now describes both suppressed lines and the two that are never suppressed. Docstring only; no assertion changed. |
| Iteration 3 SA-01: the same late write in the other settings routes | Backlog | Yes | Recorded in `.planning/backlog/MAINTENANCE.md` together with request cancellation during a write. The other routes are unchanged in round 3. |
| Iteration 3 SA-02: a failure closing the directory handle after the file was replaced is reported as "not removed" | Backlog | Yes (entry exists) | `triggarr/config.py` unchanged. The backlog entry's "no owner ruling yet" wording is out of date (see above). |

## Narrative Findings (AI reviewer)

## Info

### IN-01: The "write already running" test allows 100 ms for the request to reach the write

**File:** `tests/test_web.py:2227-2229`
**Issue:** The test starts the removal request, lets the loop run for twenty 5 ms sleeps, and then asserts that the thread start was already refused (`len(refused) == 1`). On correct code that assertion fails if the request has not reached the settings write within about 100 ms. Measured here, the request reaches the write in about 15 ms while the full suite was running alongside, so the margin is roughly seven times. On a heavily loaded machine that margin could be used up and the test would fail although the code is right. It cannot pass wrongly. Not seen in 15 repeat runs.
**Fix:** Wait for the condition instead of a fixed time: loop on `await asyncio.sleep(0.005)` until `refused` is non-empty (with a generous limit, as the F001 test does), then do the "request is still unanswered" check.

### IN-02: The mock-based test still describes the failure as "the write never starts"

**File:** `tests/test_web.py:2025`
**Issue:** `test_remove_instance_write_never_starts_logs_one_error` replaces `run_in_executor` with a mock that queues nothing. Its name and docstring are accurate for that mock, but not for the real refused-thread-start failure, where the write is queued. The real failure is now covered by the two new tests, so nothing is untested; the name can only mislead a later reader. The fix report already notes this.
**Fix:** Rename it or add one docstring line pointing at the refused-thread-start tests.

## Set aside (needs ruling)

None.

---

_Reviewed: 2026-11-16T00:47:35Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
