---
phase: 65-scheduler-hardening-resilience
fixed_at: 2026-05-25T00:00:00Z
review_path: .planning/phases/65-scheduler-hardening-resilience/65-REVIEW.md
iteration: 1
findings_in_scope: 10
fixed: 6
skipped: 4
status: partial
---

# Phase 65: Code Review Fix Report

**Fixed at:** 2026-05-25
**Source review:** `.planning/phases/65-scheduler-hardening-resilience/65-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope (Critical + Warning): 10
- Fixed: 6
- Skipped: 4 (3 design decisions documented in plan, 1 observability/style trade-off)
- Test status: 906/906 passing
- Lint status: `uv run ruff check triggarr/ tests/` clean

## Fixed Issues

### CR-01: Tracking exception logged without sanitization — leaks raw exception representation

**Files modified:** `triggarr/search/scheduler.py`, `triggarr/web/routes.py`
**Commit:** c62d155
**Applied fix:** Applied the same sanitization split documented in `_on_job_error`'s docstring: httpx/pydantic exceptions route through `_sanitize_exc` (engine.py) to strip credentials from `request.url`; aiosqlite and OSError use `str(exc)` since they do not carry secrets. Fixed both call sites in one commit per reviewer guidance — the scheduler's tracking branch (line 212-215) and the pre-existing manual-search-now handler in routes.py:856-862. Added `_sanitize_exc` to routes.py's existing `from triggarr.search.engine import ...` line.

### WR-01: `wait_for(acquire(), ...)` cancellation can leave the lock held

**Files modified:** `triggarr/search/scheduler.py`
**Commit:** 626fd52
**Applied fix:** Replaced `asyncio.wait_for(lock.acquire(), timeout=...)` with `async with asyncio.timeout(_SHUTDOWN_DRAIN_TIMEOUT):` (Python 3.11+ idiom — project minimum). Tracked `acquired` flag separately and moved release into a `finally` block conditional on `acquired` so a `lock.release()` on an unlocked lock cannot raise RuntimeError during the subsequent client-close / db-close steps. The outer try/except/finally preserves the existing structured WARNING-on-timeout log with holder identity.

### WR-04: `secrets` stdlib module shadowed by local variable in `save_settings`

**Files modified:** `triggarr/web/routes.py`
**Commit:** 156c98c
**Applied fix:** Renamed local variable from `secrets` to `_new_secrets`, matching the convention already used in the four other endpoints that call `collect_secrets` (lines 1108, 1358, 1392, 1416). `save_settings` was the lone outlier. The rename eliminates the readability landmine (a future refactor moving a `secrets.compare_digest(...)` call into this function would have failed at runtime with AttributeError on a list).

### WR-05: `app.state.search_lock_holder: tuple[str, float] | None = None` annotation is meaningless on `State`

**Files modified:** `triggarr/search/scheduler.py`
**Commit:** 0d9d468
**Applied fix:** Dropped inline `: type = value` annotations from `app.state.search_lock_holder`, `app.state.last_search_time`, `app.state.search_failures`, and `app.state.persistence_degraded`. Starlette's `State` is a SimpleNamespace-like `__dict__` container — these annotations are discarded at runtime. Moved the type guidance into comments above each assignment so readers see the intended type without inferring runtime enforcement that does not exist.

### WR-08: Test uses private `scheduler._dispatch_event` API

**Files modified:** `tests/test_scheduler.py`
**Commit:** 0c95fd5
**Applied fix:** Replaced `scheduler._dispatch_event(event)` with a direct call to `_on_job_error(event)`. The unit under test is the listener function, not APScheduler's dispatch path, so calling the listener directly is both more robust against future APScheduler upgrades and more faithful to the test's intent. Dropped the now-unused `AsyncIOScheduler` import.

### WR-09: `_evaluate_cycle_outcome` not called when persistence raises — counter state inconsistent

**Files modified:** `triggarr/search/scheduler.py`
**Commit:** d2cd0cb
**Applied fix:** Added `app.state.persistence_degraded = False` on the success branch of the persistence try/except. Previously the flag was sticky — once set True by a transient blip (one-off disk full, brief permission failure on a remote volume), it latched True forever even after the next save succeeded. Reset on success makes the flag track durability of the most recent save attempt.

## Skipped Issues

### WR-02: `_evaluate_cycle_outcome` treats unknown `connected` as success, masking engine-bug signal

**File:** `triggarr/search/scheduler.py:279-291`
**Reason:** Skipped per orchestrator instructions — this is a documented design decision made by the SAFETY-03 executor agent. The function-level docstring explicitly states "Missing or None `connected` is treated as success (do not double-count first-ever cycle before the engine sets the flag)." Changing this would alter documented behavior verified by `tests/test_scheduler.py::test_persistence_failure_logs_error_and_marks_degraded` and the SAFETY-03 plan acknowledgement. The reviewer's INFO-log compromise ("connected status unknown after cycle") is a reasonable follow-up but represents a new observability feature rather than a regression.
**Original issue:** "Unknown" case lumps "first-ever cycle, never run" with "Nth cycle, flag missing — engine bug". A persistent engine bug producing `connected=None` would sit at counter=0 forever with no escalation log.

### WR-03: `scheduler.shutdown(wait=False)` does not cancel in-flight async jobs — drain semantics drift

**File:** `triggarr/search/scheduler.py:478-509`
**Reason:** Skipped per orchestrator instructions — this is a documented design decision made by the RES-01 executor agent. The plan explicitly accepts the "no force-cancel; rely on host SIGKILL after drain timeout" contract; the WARNING-on-timeout log surfaces the stuck-cycle identity for operator triage. Adding explicit cancellation would change the drain semantics chosen by the plan author and would require coordinated changes to client/DB close ordering plus new tests.
**Original issue:** After drain timeout the code continues to db.close() and may crash when aiosqlite finds a still-active cursor on the unsuccessfully-drained cycle. The WARNING says "forcing close" but the code does not actually cancel anything.

### WR-06: `_record_cycle_failure` uses `>=` against threshold but the log message format hides the inequality

**File:** `triggarr/search/scheduler.py:241-249`
**Reason:** Skipped — this is the documented SAFETY-03 escalation semantics (RESEARCH A6: "count==threshold IS ERROR — the threshold represents the Nth failure escalates"). The reviewer states "This is correct behavior per the plan." Both proposed fixes (boundary-only ERROR at `count == threshold`, or alternate log notation) would change behavior verified by `tests/test_scheduler.py::test_threshold_escalation_logs_error_on_third_failure` (line 325). Treating this as a new observability iteration rather than a regression fix.
**Original issue:** Operators searching logs for `3/3` find the first escalation but not subsequent `(4/3)`, `(5/3)` lines — latent observability gap.

### WR-07: Race between `app.state.search_lock_holder` set and drain read

**File:** `triggarr/search/scheduler.py:131` and `triggarr/search/scheduler.py:489-498`
**Reason:** Skipped — design decision made by the RES-01 executor agent. The entry-time INFO log was deliberately added to give operators an immediate signal even when SIGKILL fires before the timeout. The reviewer himself offers "accept the cosmetic gap and document" as a valid resolution. The defensive re-read inside `except TimeoutError:` (line 513, now line 538 after WR-01 fix) already exists. Modifying the entry-time log into a generic "draining lock" message would degrade the operator's ability to see a stuck holder during normal-shutdown SIGKILL windows.
**Original issue:** During incident triage, a queued-but-not-yet-acquired cycle is reported as "no current holder" in the entry log. Benign in normal shutdown but misleading.

---

_Fixed: 2026-05-25_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
