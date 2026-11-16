---
phase: 87-settings-state-file-safety
reviewed: 2026-11-16T00:25:58Z
depth: standard
iteration: 3
head: 615a044a
files_reviewed: 6
files_reviewed_list:
  - triggarr/web/routes.py
  - triggarr/config.py
  - triggarr/state.py
  - tests/test_web.py
  - tests/test_config.py
  - tests/test_state.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 87: Code Review Report (iteration 3, review after fix round 2)

**Reviewed:** 2026-11-16T00:25:58Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found
**Head reviewed:** `615a044a` (fix round 2 diff base `d524b1b7`; phase base `3cede400`)

The iteration 1 report (head `6262dd14`) and the iteration 2 report (head `f099c6a8`) are in git history for this file.

## Summary

This is a review of fix round 2 (`git diff d524b1b7..HEAD -- triggarr tests`) against the code itself, not against `87-REVIEW-FIX.md`.

All three round 2 fixes are real and hold up:

- **Codex F001 (`add_instance`):** fixed. An Add Instance that overlaps a removal can no longer bring the removed instance back.
- **Iteration 2 WR-01 and SA-01 (one error entry per failed removal):** fixed as far as the log goes. Every failed-write path now logs one error-level entry naming the app, the instance and the reason.
- **Iteration 2 IN-01 (warning wording):** fixed.

One warning, on the narrow path that iteration 2 WR-01 was about. When the operating system refuses to start the thread for the settings write, the write is not cancelled. It stays queued and runs later, after the user has been told "Nothing was changed". The settings file then loses the instance while the running app keeps it. This was reproduced. It was not introduced by round 2 (the behavior dates from fix round 1), and iteration 2 missed it: that report said live state and the response were correct on this path, which is true only until the queued write runs. Round 2 added a code comment and a test that call this path "the write never starting", which is not what happens in the real failure.

Two info items for the backlog. No blocker.

The `save_settings` comparison the owner asked for is in its own section below. Short answer: a Save carrying a removed instance's fields brought the instance back before this phase too, in every overlap that was tried. The phase changed the result in one of them and fixed a separate, worse overlap.

### Round 2 verification

| Check | Result |
|---|---|
| F001 sequence can no longer bring back a removed instance through `add_instance` | Holds. The settings read, both checks, the build and the validation are inside the lock (`triggarr/web/routes.py:908-928`). An Add that arrives during a removal's write waits at `:908` and then reads the settings the removal left behind. `test_add_instance_during_removal_write_does_not_resurrect_removed` fails on the pre-round-2 code and passes at head (run by this review, see below). |
| Validation still precedes the write | Holds. `SettingsModel(**config_dict)` at `:925`, write at `:931-933`. |
| Live settings swapped only after a successful write | Holds. `:934` is reached only if the awaited write returned. A failed write raises out of the `async with`; live settings and state are untouched. |
| One error-level entry naming app, instance and reason on each failed-removal path | Holds for: settings-build failure (`:1013-1022`), `OSError` from the writer, any other exception from inside the writer, and the write not starting (`:1041-1051`). Known exception, unchanged and stated in the fix report: if the write fails and deleting its temp file also fails, the writer logs a second error for the cleanup. |
| Default `log_failure=True` unchanged for every other caller | Holds. The only code change in `triggarr/config.py` is `if log_failure:` around one log call (`:189-194`). `remove_instance` is the only caller that passes `log_failure=False`; the other eight call sites in `triggarr/web/routes.py` and the one in `triggarr/config.py:419` use the default. `test_atomic_toml_write_logs_unexpected_error_by_default` pins the exact default line. |
| `CancelledError` not swallowed | Holds. Both handlers in `remove_instance` catch `Exception`; on the supported Python versions (3.11+) `asyncio.CancelledError` is a `BaseException` and propagates. |
| New work done while holding `search_lock` | Nothing that can block or deadlock. Inside the lock `add_instance` now also does two dictionary checks, one settings serialization, one pydantic validation and, on a validation failure, one log line. The only `await` in the block is the file write that was already there. Nothing in the block takes `search_lock` again (the lock is not re-entrant). One side effect is IN-01. |
| 400 responses returned from inside the lock | Sound. All three (`:913`, `:915`, `:928`) are plain `return` statements inside `async with`, which releases the lock on the way out. Bodies are unchanged; the instance name is still escaped. |
| Lock released on every path | Holds. Every exit from the `add_instance` and `remove_instance` blocks is a `return` or a raised exception inside `async with`. Confirmed in a probe on the failed-removal path (lock not held after the request). |
| New tests' reliability (timed waits) | No false-failure risk found. The F001 test waits on events with generous limits (10 s) and checks ordering through a recorded call, not through a sleep. The duplicate-check test uses a fixed 250 ms wait; if the requests were slower than that the test would still pass on correct code, so the wait cannot make it fail wrongly. The concurrency and never-starts tests were run 15 times in a row with no failure. Neither new test reads `asyncio.Lock._waiters`. |
| `test_remove_instance_unexpected_real_write_error_logs_one_error` still tests something real | Yes. It drives the real writer's unexpected-error branch through the route and fails on the pre-round-2 code (two error entries). Its assertions on the app and instance names are not satisfied by the file path in the message (the temp path contains neither `radarr` nor `4K`). |
| `test_remove_instance_write_never_starts_logs_one_error` | Passes and checks the log correctly, but it simulates a failure that leaves nothing queued, which the real failure does not do. See WR-01. |

Checks run during this review (from the checkout, without writing to it):

- `pytest tests/` (full suite): 3327 passed, 1 skipped.
- `ruff check triggarr/ tests/`: all checks passed.
- `tests/audit_lock_coverage.py`: covered 8 / 8, uncovered 0.
- Convention pack (`verify conventions --check`) on the six files: no findings (not skipped).
- The head tests run against an exported copy of the pre-round-2 code (`d524b1b7`): the six new tests that were meant to fail and the changed test fail there (7 failed); the one test written to pin existing behavior passes. All pass at head.
- Two throwaway probes outside the repo, against exported copies of the phase base and the head: the `save_settings` comparison below, and the WR-01 reproduction.

Not verified: nothing was exercised in a browser, and `triggarr/templates/settings.html` was not re-reviewed (unchanged in round 2).

One thing outside the reviewed files, for whoever updates planning: two entries in `.planning/backlog/MAINTENANCE.md` (the D-13 settings-writer audit and "Settings read before search_lock in add_instance and save_settings") still describe `add_instance` as reading settings before the lock. That is no longer true for `add_instance`; it is still true for `save_settings`.

## Earlier-iteration dispositions

| Finding | Disposition | Verified | Notes |
|---|---|---|---|
| Iteration 2 WR-01: no error entry and no reason when the write never starts | Fixed (the log) | Yes | One error entry with app, instance and reason on this path (`triggarr/web/routes.py:1041-1051`); the warning that pointed at a missing entry is gone. The same path has a different, non-log defect that iteration 2 did not see: WR-01 below. |
| Iteration 2 IN-01: unreadable-state-file warning promised replacement | Fixed | Yes | `triggarr/state.py:297` now says "will try to replace it". The new test fails on the old wording. |
| Iteration 2 SA-01: the one error entry did not name the app or instance on a non-`OSError` writer failure | Fixed | Yes | `log_failure=False` now covers the writer's unexpected-error line (`triggarr/config.py:189-194`); the route's entry is the only one and names all three. |
| Iteration 2 SA-02: a failure closing the directory handle after the file was replaced is reported as "not removed" | Open | No change to verify | `triggarr/config.py:206-208` is unchanged and no ruling is recorded in the fix report or in `.planning/backlog/MAINTENANCE.md`. Carried forward as SA-02 below. Same family as WR-01 (file changed, user told it was not). |
| Codex F001: Add during a removal's write brings the removed instance back | Fixed for `add_instance` | Yes | See the verification table. The `save_settings` half of Codex's suggested fix ("review save_settings for the same stale-snapshot interaction") was deliberately not done and awaits an owner ruling; see the next section. |

## `save_settings` overlap: before this phase versus now

**Purpose:** input for the owner's decision on `save_settings`. This is not a finding and is not counted in the totals.

**The code did not change.** `save_settings` is byte-for-byte the same at the phase base (`3cede400`) and at head. It reads live settings at `triggarr/web/routes.py:640`, before taking the lock at `:727`, and for any app with fields in the form it treats the form as the complete list of that app's instances. What changed is `remove_instance`, which `save_settings` can overlap with. At the base, a removal deleted the instance from live settings first and then wrote the file. Now it writes the file first and changes live settings only afterwards.

**Method.** A probe ran the real `save_settings` and `remove_instance` from an exported copy of each commit, with the real settings writer, against the same four sequences. The Save carried the fields of both instances, as the Settings page form does, with the API-key box left empty (the page never pre-fills it). The removed instance was enabled.

| Sequence | Phase base `3cede400` | Head `615a044a` |
|---|---|---|
| **A.** Save is submitted while the removal is writing the file | Instance comes back, as a **new** instance: new id, **empty API key**, enabled, with a connection and a schedule. It cannot authenticate until the key is entered again. | Instance comes back as **itself**: original id and API key, enabled, with a connection and a schedule. It resumes searching. |
| **B.** Removal and Save are both waiting behind a running search; the removal goes first | Instance comes back as itself (original id and key, connection, schedule). | Same as base. |
| **C.** Save from a page that was loaded before the removal, submitted after the removal finished (stale tab) | Instance comes back as a new instance (new id, empty API key). | Same as base. |
| **D.** Removal is submitted while a Save is writing the file | **Broken at base:** the removal overwrote the Save on disk. The settings file lost both the instance and the Save's other changes, while the running app kept the Save's changes and still listed the instance, without a connection or schedule. | **Correct:** the Save is kept, the instance is removed, and the file and the running app agree. |

In every row where the instance comes back, on both commits, its queue progress and last-run times are reset to defaults, both requests report success (303), and the file and the running app agree with each other.

**Answers to the two questions:**

1. *Did a Save carrying a removed instance's fields recreate it before this phase too?* Yes, in all three sequences where the removal goes first (A, B, C). This phase did not create that behavior.
2. *Did this phase make the overlap behavior worse?* It changed one case and fixed another:
   - **A changed in kind, not in outcome.** In both versions the removal is silently undone. Before, the instance returned without its API key, so it failed to connect and the user would notice. Now it returns fully working and resumes searching, so the undone removal is easier to miss. Whether that is worse is a product judgment: the instance the user asked to remove is active again, but nothing is left half-configured. The window is the duration of one settings-file write (normally milliseconds).
   - **D was fixed.** This was the more damaging case at the base (a Save lost on disk, and the file and the running app disagreeing). It no longer happens.
   - **B and C are unchanged.** C, the stale tab, needs no overlap at all and is by far the easiest to hit in practice.

So the phase did not introduce "Save brings back a removed instance" and did not widen when it can happen. A fix aimed only at the overlap (rows A and B) would leave row C as it is.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: When the thread for the settings write cannot be started, the write still runs later, after the user was told nothing changed

**File:** `triggarr/web/routes.py:1031-1051` (comment at `:1024-1030`); test at `tests/test_web.py:2021-2074`
**Issue:** The handler at `:1041` treats an exception from `run_in_executor` as "the write did not happen": it logs, returns the "was not removed ... Nothing was changed" message and leaves live state alone. For the real failure this path exists for (`RuntimeError: can't start new thread`), that is not true. Python's thread pool puts the job on its queue *before* it tries to start a thread. When the thread cannot be started the error is raised, but the job stays queued. The next time anything uses the default executor and a thread can be started (a state save after a search cycle, any other settings write), that thread runs the queued removal write first.

Reproduced with a probe that makes the operating system refuse exactly one thread during a real removal, with the real loop, executor and writer:

```
response : 200 "'4K' was not removed: the settings file could not be saved. Nothing was changed. Check the Triggarr log for details."
log      : ERROR Could not save settings file <config>/triggarr.toml while removing radarr/4K; instance kept: RuntimeError: can't start new thread
running app, radarr instances                    : 4K, Default
settings file, right after the failed removal    : 4K, Default
settings file, after the next executor use       : Default
running app, radarr instances                    : 4K, Default
```

Effects:

1. The message shown to the user is false after the fact. The instance keeps running, but it is gone from the settings file, so it disappears at the next restart together with its URL and API key. The file and the running app stay out of step until some later settings write or a restart.
2. The late write runs outside `search_lock`, with data built at the time of the failed removal.
3. The log says "instance kept", and nothing is logged when the late write lands.

Why this is a warning and not a blocker: it needs the operating system to refuse a new thread at a moment when the pool has no idle worker. That is rare (a process or thread limit on the host or container, or memory pressure). When it does happen the outcome above is the expected one, not an unlucky one, because the queued job runs as soon as threads are available again. It contradicts the phase's own guarantee for a failed removal (CONSIST-01), which is why it is not graded lower.

History: the behavior comes from fix round 1, which first caught this exception and answered "not removed". At the phase base the exception surfaced as a server error with the instance already deleted from live settings, so the late write agreed with the running app. Round 2 did not change the behavior; it added the comment at `:1024-1030` and the test, both of which describe the path as "the write never starting". The test replaces `run_in_executor` with a mock that raises without queueing anything, so it cannot see the late write. The other documented cause, `cannot schedule new futures after shutdown`, is raised before queueing and is not affected.

**Fix:** Make the queued write refuse to run once the route has given up on it. This stays inside `triggarr/web/routes.py`:

```python
abandoned = threading.Event()

def _write_unless_abandoned() -> None:
    # If the route already answered "not removed", this job must not run later.
    if abandoned.is_set():
        return
    _atomic_toml_write(config_path, config_dict, log_failure=False)

try:
    await asyncio.get_running_loop().run_in_executor(None, _write_unless_abandoned)
except Exception as exc:  # error boundary: nothing live has been changed yet
    abandoned.set()
    logger.error(...)  # unchanged
    return _removal_failed_response(request, instance_name)
```

Setting the flag when the writer itself raised is harmless (that job has already finished). A very small window remains in which an already-running worker picks the job up between the error and `abandoned.set()`; closing it fully needs a small lock shared by the job and the handler, which is optional. Add a test that refuses one real thread start (patching `threading.Thread.start` for the executor's thread, not `run_in_executor`), then lets a later executor call succeed, and asserts the settings file still contains the instance. Correct the comment at `:1024-1030`. Check that `tests/audit_lock_coverage.py` still reports 8 / 8 with the writer reference inside the nested function.

## Info

### IN-01: Add Instance's "already exists" and "maximum 5" answers now wait for a running search to finish

**File:** `triggarr/web/routes.py:908-915`
**Issue:** A search cycle holds `search_lock` for its whole duration (`triggarr/search/scheduler.py:169`). Before round 2 the duplicate and limit checks ran before the lock and answered at once. They now run inside it, so a rejected Add waits as long as a successful one always has. This is the price of the F001 fix (the checks must see current settings), nothing is wrong in the result, and the two cheap checks that need no settings still answer immediately.
**Fix:** None needed. Recorded so the changed timing is known.

### IN-02: A test docstring describes the old `log_failure` behavior

**File:** `tests/test_config.py:925`
**Issue:** The docstring of `test_atomic_toml_write_log_failure_false_suppresses_primary_line` says `log_failure=False` "suppresses only the primary 'Config write failed' line". Since round 2 it also suppresses the unexpected-error line. The test itself is correct and passes. The fix report already notes this.
**Fix:** Reword the docstring to cover both lines.

## Set aside (needs ruling)

### SA-01: The same late write can happen in every other settings writer

**Where:** `triggarr/web/routes.py:728-730` (`save_settings`), `:931-933` (`add_instance`), and the writes at `:1566`, `:1831`, `:1880`, `:1904`, `:2233`
**Why excluded:** These routes are outside this phase's scope (the phase changes how removal reports a failed save, and D-13/D-14 leave the other writers alone), and the behavior predates the phase. It is the same mechanism as WR-01, found by reading; only the removal path was reproduced.
**Effect if left as is:** If the operating system refuses the thread for one of these writes, the user gets a server error and the running app keeps the old settings, but the queued write lands later, outside the lock. The settings file then holds a change the running app never applied, until the next settings write or a restart. Same rare trigger as WR-01.
**Needs:** Ruling: backlog (a shared helper that all writers use would fix every route at once) / accept.

### SA-02: A failure closing the directory handle after the settings file was already replaced is reported as "not removed" (carried forward from iteration 2)

**Where:** `triggarr/config.py:206-208` (unchanged this phase), reached from `triggarr/web/routes.py:1031-1051`
**Why excluded:** The code predates Phase 87 and no ruling was recorded after iteration 2.
**Effect if left as is:** If closing the directory handle raises after the rename succeeded, the route reports a failed save: the user is told nothing was changed and the running app keeps the instance, but the file no longer has it, so it disappears at the next restart. Very unlikely in practice; found by reading, not reproduced.
**Needs:** Ruling: accept / backlog next to IN-04 from iteration 1 (same function).

---

_Reviewed: 2026-11-16T00:25:58Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
