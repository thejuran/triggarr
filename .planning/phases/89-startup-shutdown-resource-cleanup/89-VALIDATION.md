---
phase: 89
slug: startup-shutdown-resource-cleanup
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-11-18
---

# Phase 89 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run pytest tests/test_scheduler.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_scheduler.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q` and `uv run ruff check triggarr/ tests/`
- **Before `/bm:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

Filled in by the planner per task. Requirement-level map from RESEARCH.md:

| Requirement | Plan/Task | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|-----------|----------|-----------|-------------------|-------------|--------|
| LIFE-02, D-07, D-09 | 89-01 T1 | `_safe_close` returns False and logs one sanitized WARNING on exception or timeout; never raises; `_CLEANUP_STEP_TIMEOUT == 5.0`; apikey never logged | unit | `uv run pytest tests/test_scheduler.py -q -k "safe_close or safe_stop_scheduler or cleanup_step_timeout"` | ✅ | ⬜ pending |
| D-09, D-02 | 89-01 T1 | `_safe_close` returns at the cap when the close waits again in its cancellation finalizer and when a real aiosqlite worker is blocked; later cleanup proceeds before release; the abandoned task is kept referenced and its late result observed and logged sanitized | unit | `uv run pytest tests/test_scheduler.py -q -k "safe_close and (cancellation_finalizer or wedged_real_aiosqlite or late_failure)"` | ✅ | ⬜ pending |
| D-02, D-07 | 89-01 T1 | Caller of `_safe_close` cancelled as the close fails with a credential-bearing exception: CancelledError propagates, asyncio reports no "exception was never retrieved", the raw text is never logged, one sanitized WARNING | unit | `uv run pytest tests/test_scheduler.py -q -k "safe_close_retrieves_close_failure_when_caller_is_cancelled"` | ✅ | ⬜ pending |
| LIFE-02 | 89-01 T2 | Shutdown: one client's close raises AssertionError; remaining clients and db still close (evidence captured before rescue cleanup); D-07 warning; "Search engine stopped" | unit (in-process lifespan) | `uv run pytest tests/test_scheduler.py -q -k "shutdown_continues_when_client_close_fails"` | ✅ | ⬜ pending |
| LIFE-02, D-08 | 89-01 T2 | Shutdown: db close fails; warning logged; "Search engine stopped" is the last line | unit | `uv run pytest tests/test_scheduler.py -q -k "shutdown_continues_when_db_close_fails"` | ✅ | ⬜ pending |
| D-09, D-04 | 89-01 T2 | Shutdown: hung client close (parked in its cancellation finalizer) abandoned after cap, later clients and db closed before release; order scheduler→clients→db unchanged | unit | `uv run pytest tests/test_scheduler.py -q -k "shutdown_abandons or shutdown_order"` | ✅ | ⬜ pending |
| LIFE-01, D-12, D-05 | 89-02 T1 | Failed startup (init_db) closes db; aiosqlite worker thread stopped; same exception object propagates; sanitized cause line first, summary line last | unit | `uv run pytest tests/test_scheduler.py -k "startup_failure and init_db" -q` | ✅ | ⬜ pending |
| LIFE-01 | 89-02 T1 | Failed startup (cutover) closes db | unit | `uv run pytest tests/test_scheduler.py -k "startup_failure and cutover" -q` | ✅ | ⬜ pending |
| LIFE-01 | 89-02 T1 | Failed startup (Nth client construction) closes db + every earlier client | unit | `uv run pytest tests/test_scheduler.py -k "startup_failure and client_construction" -q` | ✅ | ⬜ pending |
| LIFE-01, D-05, D-06 | 89-02 T1 | Cleanup step (client close / db close) also fails: original error still propagates; exact log order cause, warning, summary; summary counts successes | unit | `uv run pytest tests/test_scheduler.py -k "startup_failure and cleanup_also_fails" -q` | ✅ | ⬜ pending |
| D-05 | 89-02 T1 | Cause line renders the error by sanitized type only; apikey never logged | unit | `uv run pytest tests/test_scheduler.py -k "startup_failure and cause_line" -q` | ✅ | ⬜ pending |
| LIFE-03 | 89-02 T1 | Failure before scheduler.start() (real AsyncIOScheduler): no shutdown call, STATE_STOPPED, no SchedulerNotRunningError | unit | `uv run pytest tests/test_scheduler.py -k "startup_failure and scheduler_not_started" -q` | ✅ | ⬜ pending |
| LIFE-03 | 89-02 T2 | start() raises before the running-state transition: no shutdown call; failure after a completed start: shutdown(wait=False) called by the lifespan's own cleanup (pre-rescue snapshot `obs.scheduler_shutdown_wait`), summary names the scheduler | unit | `uv run pytest tests/test_scheduler.py -k "startup_failure and (scheduler_start_raises or scheduler_started)" -q` | ✅ | ⬜ pending |
| LIFE-03 | 89-02 T2 | Partial start (real AsyncIOScheduler, start() raises after STATE_RUNNING): scheduler actually STATE_STOPPED after cleanup, original error preserved; a scheduler that stays running is reported | unit | `uv run pytest tests/test_scheduler.py -k "partial_scheduler_start or stop_scheduler_if_running" -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements (`tests/test_scheduler.py`, `tests/conftest.py` factories, `_FakeScheduler` double, `io.StringIO()` log capture).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Built-image container exits promptly after a failed upgrade | LIFE-01 | Built-image proof is Phase 92 (SMOKE) scope | Covered by Phase 92 smoke tests |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (4 tasks, all automated)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none)
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
