---
phase: 89-startup-shutdown-resource-cleanup
verified: 2026-11-18T23:55:55Z
status: passed
score: 22/22 must-haves verified
has_blocking_gaps: false
overrides_applied: 0
---

# Phase 89: Startup & Shutdown Resource Cleanup Verification Report

**Phase Goal:** A startup that fails partway closes everything it already opened, and a shutdown where one connection fails to close still closes the rest.
**Verified:** 2026-11-18T23:55:55Z
**Verified head:** 4f7d1672 (code last changed in 6feac144)
**Status:** passed
**Re-verification:** No (initial verification)

## Goal Achievement

The goal is met. The evidence is the code at HEAD, my own re-run of every RED commit against the code it was written for, one full test run, and three real-process probes I wrote for this verification. SUMMARY claims were not used as evidence.

### Observable Truths: roadmap contract

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | When startup fails partway through, Triggarr closes the database and every connection already opened, and the process exits promptly rather than hanging (LIFE-01) | VERIFIED | `triggarr/search/scheduler.py:692-918`: the whole setup section is inside one `try`; the handler closes each tracked client in reverse order and the database, then re-raises. Real-process probes (real uvicorn, real aiosqlite): failed upgrade exits in 0.36s, failed client construction in 0.29s, no non-daemon thread left. 13 failed-startup tests pass and assert the real aiosqlite worker thread has stopped. |
| SC2 | When one *arr connection fails to close at shutdown, the remaining connections and the database still close, and the failure is logged sanitized (LIFE-02) | VERIFIED | `scheduler.py:1013-1022`: every client close and the database close go through `_close_through_cancellation` -> `_safe_close`, which never raises on a close failure and logs through `_sanitize_exc`. `test_shutdown_continues_when_client_close_fails` asserts `clients_closed == [False, True, True]`, worker thread stopped, and the exact warning line. `test_safe_close_never_logs_url_credentials` passes. |
| SC3 | After a failed startup, the scheduler is not left running (LIFE-03) | VERIFIED | `scheduler.py:600-620, 887-891`: the stop decision reads `scheduler.running`, then re-reads it after one loop iteration. Probe with a real `AsyncIOScheduler` failing after `start()`: HEAD reports `scheduler.running: False` and the process exits; the pre-phase code (b4a25aa1) reports `True`, leaves the aiosqlite worker alive, and the process was still running after 60s when I stopped it. |

### Observable Truths: plan 89-01 (shutdown)

| # | Truth (short form) | Status | Evidence |
|---|--------------------|--------|----------|
| 1 | Non-httpx AssertionError on one client close: later clients and database close, lifespan exit does not raise | VERIFIED | `test_shutdown_continues_when_client_close_fails` passes; failed on pre-fix code with "lifespan exit raised AssertionError" (my re-run of 12e9ea02) |
| 2 | Exactly one WARNING `Shutdown: could not close Radarr/'Default' connection (AssertionError); continuing` | VERIFIED | Asserted verbatim in the test above; format at `scheduler.py:571-576` |
| 3 | Database close raises: one WARNING, nothing escapes, "Search engine stopped" still logged, no new summary line | VERIFIED | `test_shutdown_continues_when_db_close_fails` passes; `scheduler.py:1021-1024` |
| 4 | 5.0s module-constant cap, bounded by `asyncio.wait` on an owned task | VERIFIED | `_CLEANUP_STEP_TIMEOUT: float = 5.0` (line 121); `asyncio.wait({task}, timeout=...)` (line 535); no `asyncio.timeout` or `wait_for` in `_safe_close`; wedged real-aiosqlite test passes |
| 5 | Close that outlives the cap: cancelled once, kept in `_ABANDONED_CLOSE_TASKS`, result retrieved at DEBUG | VERIFIED | Lines 471-497, 547-551; `test_safe_close_observes_late_failure_of_abandoned_close` passes |
| 6 | Result-retrieving done-callback attached before the first await; caller's cancellation still propagates | VERIFIED | Line 532 precedes line 535; re-raise at 546; `test_safe_close_retrieves_close_failure_when_caller_is_cancelled` passes |
| 7 | Shutdown order unchanged (scheduler, drain, clients, database, "Search engine stopped") | VERIFIED | Lines 924-1024 read in order; `test_shutdown_order_is_unchanged` and both WR-02 tests pin the order |
| 8 | No `os._exit` / `sys.exit` | VERIFIED | grep on `scheduler.py`: no match |
| 9 | No new runtime dependency | VERIFIED | `git diff --quiet main -- pyproject.toml uv.lock` exits 0 |
| 10 | Every new shutdown test observed failing on unfixed code | VERIFIED | My re-run: 8c01f812 gives 10 failed; 12e9ea02 gives 3 failed, 1 passed (the order pin). Matches the SUMMARY. |

### Observable Truths: plan 89-02 (failed startup)

| # | Truth (short form) | Status | Evidence |
|---|--------------------|--------|----------|
| 1 | Any setup step after the database opens fails: database and constructed clients closed, original exception re-raised, worker thread stopped | VERIFIED | Lines 692-918; stage tests for init_db, cutover, client construction, scheduler start, post-start add_job all pass |
| 2 | Cause line `Startup failed (RuntimeError); closing what was opened` first, via `_sanitize_exc` | VERIFIED | Line 875 is the first statement of the handler; `test_startup_failure_cause_line_never_logs_credentials` passes |
| 3 | Exactly one final summary line counting successes only | VERIFIED | Lines 906-912; observed in probes: "closed the database and 1 connection(s)", "closed the scheduler, the database and 3 connection(s)" |
| 4 | A cleanup step that fails is one WARNING between cause and summary; remaining steps run; original error propagates | VERIFIED | `test_startup_failure_cleanup_also_fails_still_raises_original` and `..._on_db_close` pass |
| 5 | Scheduler stop decided from `scheduler.running`, never-started scheduler never shut down, partially started one observed stopped | VERIFIED | Lines 610-620; `test_startup_failure_partial_scheduler_start_is_stopped` uses a real `AsyncIOScheduler`; my real-scheduler probe |
| 6 | Resources tracked as locals, never read back from `app.state` | VERIFIED | Lines 689-690, 741; zero `app.state` references in lines 866-918 |
| 7 | Cleanup steps run through the 89-01 helpers; no `AsyncExitStack` | VERIFIED | Lines 888, 895-903; grep for `AsyncExitStack`: no match |
| 8 | No forced exit, no new dependency | VERIFIED | As 89-01 truths 8 and 9 |
| 9 | Every new failed-startup test observed failing at a positive cleanup assertion | VERIFIED | My re-run: 6b5eeb05 gives 7 failed; 7a1dc852 gives 3 failed, 1 passed (the pin). Matches the SUMMARY. |

**Score:** 22/22 truths verified (3 roadmap criteria, 10 from plan 89-01, 9 from plan 89-02)

### Review-fix additions (not plan must-haves, checked because they changed the same code)

| Fix | Commit | Status | Evidence |
|-----|--------|--------|----------|
| WR-01: startup cleanup also runs on cancellation or interrupt | 26a2fc8f | VERIFIED | Handler is `except BaseException` (line 866); its 3 tests fail against the parent commit's code and pass at HEAD |
| WR-02: shutdown closes continue through cancellation, cancellation re-raised | 6feac144 | VERIFIED | Lines 968-1027; its 2 tests fail against the parent commit's code and pass at HEAD |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `triggarr/search/scheduler.py` | Close helpers, hardened shutdown, failed-startup unwind | VERIFIED | Exists, substantive, wired into `create_lifespan`, which `triggarr/__main__.py` passes to FastAPI |
| `tests/test_scheduler.py` | Helper, shutdown and failed-startup tests plus the `_observe_lifespan` harness | VERIFIED | 31 phase tests; harness drives the real lifespan with real aiosqlite and real httpx clients |

`bm-sdk query verify.artifacts` reports one issue on plan 89-02: missing pattern `except Exception as startup_exc:`. The line is now `except BaseException as startup_exc:` after WR-01. This is a superset of the planned behavior, not a stub.

### Key Link Verification

`bm-sdk query verify.key-links` returned "Source file not found" for all nine links because the plans' `from` fields are descriptions, not file paths. Each link was checked by hand.

| From | To | Status | Details |
|------|----|--------|---------|
| Shutdown step 3 | `_safe_close` | WIRED | Now via `_close_through_cancellation("Shutdown", ...)` (lines 1015, 1021), which calls `_safe_close`. The plan's literal pattern `await _safe_close("Shutdown"` no longer matches; the link holds. |
| `_safe_close` | `_sanitize_exc` | WIRED | Lines 529, 544, 575 |
| `_safe_close` | `asyncio.wait(..., timeout=_CLEANUP_STEP_TIMEOUT)` | WIRED | Line 535 |
| `_safe_close` | `_ABANDONED_CLOSE_TASKS` | WIRED | Add at 549, discard at 481 |
| `_safe_close` | `_retrieve_close_result` | WIRED | Line 532 |
| Startup handler | cause line | WIRED | Line 875 |
| Startup handler | `_safe_close("Startup cleanup", ...)` | WIRED | Via `_close_through_cancellation` at 895 and 903 |
| Startup handler | `_stop_scheduler_if_running` | WIRED | Line 888 |
| Setup section | `created_clients.append` | WIRED | Line 741, inside the inner loop |

### Data-Flow Trace (Level 4)

Not applicable: no artifact in this phase renders dynamic data.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Whole suite passes at HEAD | `uv run pytest tests/ -q` (run once) | 3381 passed, 1 skipped | PASS |
| Lint | `uv run ruff check triggarr/ tests/` | All checks passed | PASS |
| Failed upgrade: real process exits promptly | uvicorn + real aiosqlite, `init_db` raising | exited after 0.36s; cause line then "closed the database and 0 connection(s)"; no non-daemon thread | PASS |
| Failed client construction: earlier client and database closed | same, `SonarrClient` raising | exited after 0.29s; "closed the database and 1 connection(s)" | PASS |
| Failure after a real scheduler started | real `AsyncIOScheduler`, `update_check` add_job raising | HEAD: scheduler not running, no thread left, process exits. Pre-phase code: scheduler running, worker thread alive, process still running after 60s | PASS |

One limit on the second-to-last pair of rows: the pre-phase code also exited in about 0.3s in the upgrade and client-construction scenarios. aiosqlite 0.22.1 stops its worker thread when an unclosed connection is garbage collected, so those two scenarios do not hang in a small harness. The hang was reproduced only in the scheduler-left-running scenario. These probes therefore prove HEAD's behavior in all three scenarios and prove a before/after difference in one.

### TDD Sequence (RED then GREEN)

Each test commit touches only `tests/test_scheduler.py`; each following feat commit carries the production change. I exported each test commit and ran only the tests it added.

| Plan | RED commit | Result on unfixed code | GREEN commit |
|------|-----------|------------------------|--------------|
| 89-01 task 1 | 8c01f812 | 10 failed | acb838c3 |
| 89-01 task 2 | 12e9ea02 | 3 failed, 1 passed (order pin, expected) | 6a1155fd |
| 89-02 task 1 | 6b5eeb05 | 7 failed | 90db21b0 |
| 89-02 task 2 | 7a1dc852 | 3 failed, 1 passed (pin, expected) | 1a186d0e |
| WR-01 | 26a2fc8f (tests and fix together) | 3 failed against the parent's code | same commit |
| WR-02 | 6feac144 (tests and fix together) | 2 failed against the parent's code | same commit |

6a1155fd also edits six lines of the tests (the warning-prefix filter, recorded as deviation 1 in the 89-01 SUMMARY).

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes are declared or present for this phase. Skipped.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| LIFE-01 | 89-02 | Failed startup closes the database and every opened connection; process exits promptly | SATISFIED | SC1 |
| LIFE-02 | 89-01 | One failed close at shutdown does not stop the rest; failure logged sanitized | SATISFIED | SC2 |
| LIFE-03 | 89-02 | Scheduler not left running after a failed startup | SATISFIED | SC3 |

REQUIREMENTS.md maps exactly these three IDs to Phase 89. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `triggarr/search/scheduler.py` | none | TBD / FIXME / XXX / TODO / HACK | none | No markers in either modified file's phase diff |
| `triggarr/search/scheduler.py` | 1014 | Shutdown loop iterates the live client dicts across awaits (review IN-04) | Info | Latent; owner-deferred. Does not block the goal while uvicorn finishes requests before lifespan shutdown. |

### Notes for the owner (none block the goal)

1. **SUMMARY commit hashes are stale.** The eight hashes in the two SUMMARY files (376ae008 ... ea80976f) are not on this branch. They live on `backup/phase-89-pre-rebuild`. The branch commits (8c01f812 ... 1a186d0e) carry identical patches, checked pair by pair with `git patch-id`. The SUMMARY "Commits" lists point at the wrong objects for anyone auditing the PR.
2. **Deferred review items are not in the backlog yet.** 89-REVIEW.md and 89-REVIEW-FIX.md say IN-01 to IN-06 and SA-01/SA-02 go to the backlog. `.planning/backlog/MAINTENANCE.md` has no Phase 89 entry on this branch.
3. **Container-level proof is not an explicit Phase 92 criterion.** 89-CONTEXT says built-image proof belongs to Phase 92. Phase 92's success criteria cover corrupted-state recovery and bounded backups under repeated failed upgrades; none states that a failed startup exits promptly in the container. The repeated-failed-upgrade check will exercise the path, but will not necessarily assert on it.
4. **Jobs can start before a post-start failure is cleaned up.** When startup fails after `scheduler.start()`, the three search jobs had already begun and were cancelled. APScheduler logs "Error running job ..." with a `CancelledError` traceback through stdlib logging, outside the loguru redacting sink. No secret appeared in the output. This is the same channel as review item SA-01.
5. **STATE.md still reads "Executing Phase 89 ... next: phase review".** Not edited here, as instructed.

### Human Verification Required

None. All three roadmap criteria were confirmed by running code, including in real processes.

### Gaps Summary

No gaps. All 22 must-haves are verified against the code at HEAD, all three requirement IDs are accounted for, and the RED-then-GREEN sequence was reproduced independently for both plans and both review fixes.

---

_Verified: 2026-11-18T23:55:55Z_
_Verifier: Claude (bm-verifier)_
