---
phase: 89
slug: startup-shutdown-resource-cleanup
status: draft
nyquist_compliant: false
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

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| LIFE-01 | Failed startup (init_db stage) closes db; aiosqlite worker thread stopped; original error propagates | unit (in-process lifespan) | `uv run pytest tests/test_scheduler.py -k "startup_failure and init_db" -x -q` | ✅ | ⬜ pending |
| LIFE-01 | Failed startup (cutover stage) closes db + clients built so far | unit | `uv run pytest tests/test_scheduler.py -k "startup_failure and cutover" -x -q` | ✅ | ⬜ pending |
| LIFE-01 | Failed startup (client construction, Nth instance) closes db + earlier clients | unit | `uv run pytest tests/test_scheduler.py -k "startup_failure and client_construction" -x -q` | ✅ | ⬜ pending |
| LIFE-01 | Failed startup where a cleanup step also fails still re-raises the original error | unit | `uv run pytest tests/test_scheduler.py -k "startup_failure and cleanup_also_fails" -x -q` | ✅ | ⬜ pending |
| LIFE-02 | Shutdown: one client's close raises; remaining clients and db still close; sanitized warning | unit | `uv run pytest tests/test_scheduler.py -k "shutdown and client_close_fails" -x -q` | ✅ | ⬜ pending |
| LIFE-02 | Shutdown: db close fails; warning logged; "Search engine stopped" still logs | unit | `uv run pytest tests/test_scheduler.py -k "shutdown and db_close_fails" -x -q` | ✅ | ⬜ pending |
| LIFE-03 | Failure before scheduler.start(): no shutdown call, no SchedulerNotRunningError | unit | `uv run pytest tests/test_scheduler.py -k "startup_failure and scheduler_not_started" -x -q` | ✅ | ⬜ pending |
| LIFE-03 | Failure at/after scheduler.start(): scheduler shut down, not left running | unit | `uv run pytest tests/test_scheduler.py -k "startup_failure and scheduler_started" -x -q` | ✅ | ⬜ pending |

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

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
