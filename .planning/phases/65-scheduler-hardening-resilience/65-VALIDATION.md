---
phase: 65
slug: scheduler-hardening-resilience
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-25
---

# Phase 65 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3+ with pytest-asyncio (`asyncio_mode="auto"`, pyproject.toml:38) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`); no separate pytest.ini |
| **Quick run command** | `uv run pytest tests/test_scheduler.py tests/test_clients.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~20 seconds (Phase 64 baseline) |

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/test_scheduler.py tests/test_clients.py -x -q`
- **After every plan wave:** `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green AND `uv run ruff check triggarr/ tests/` clean
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 65-01-W0a | 01 | 0 | SAFETY-02 | — | n/a | unit | invert `test_make_search_job_exception_swallowed` → `test_make_search_job_unexpected_exception_propagates` | ❌ W0 | ⬜ pending |
| 65-01-W0b | 01 | 0 | SAFETY-02 | — | n/a | unit | add `test_make_search_job_httperror_swallowed` | ❌ W0 | ⬜ pending |
| 65-01-W0c | 01 | 0 | SAFETY-02 | T-65-07 | sanitized exc logging via `_sanitize_exc` | unit | add `test_event_job_error_listener_logs_unexpected_exception` | ❌ W0 | ⬜ pending |
| 65-01-impl | 01 | 1 | SAFETY-02 | T-65-07 | narrow tuple + EVENT_JOB_ERROR listener | unit | `uv run pytest tests/test_scheduler.py -k "unexpected_exception or httperror_swallowed or event_job_error_listener" -x` | n/a | ⬜ pending |
| 65-02-W0a | 02 | 0 | SAFETY-03 | — | n/a | unit | add `test_failure_counter_increments_on_cycle_exception` | ❌ W0 | ⬜ pending |
| 65-02-W0b | 02 | 0 | SAFETY-03 | — | n/a | unit | add `test_failure_counter_escalates_at_threshold` | ❌ W0 | ⬜ pending |
| 65-02-W0c | 02 | 0 | SAFETY-03 | — | n/a | unit | add `test_failure_counter_resets_on_success` | ❌ W0 | ⬜ pending |
| 65-02-W0d | 02 | 0 | SAFETY-03 | — | n/a | unit | add `test_failure_counter_per_instance_scoped` | ❌ W0 | ⬜ pending |
| 65-02-W0e | 02 | 0 | SAFETY-03 | T-65-08 | safe_int bounds 1..100 | unit | add `test_general_config_default_max_consecutive_failures` (tests/test_config.py) | ❌ W0 | ⬜ pending |
| 65-02-impl | 02 | 1 | SAFETY-03 | T-65-08 | per-(app,instance) in-memory counter + safe_int bounds | unit | `uv run pytest tests/test_scheduler.py -k "failure_counter" tests/test_config.py -k "max_consecutive_failures" -x` | n/a | ⬜ pending |
| 65-03-W0a | 03 | 0 | RES-01 | — | n/a | unit | add `test_shutdown_timeout_is_60s` | ❌ W0 | ⬜ pending |
| 65-03-W0b | 03 | 0 | RES-01 | — | n/a | unit | add `test_shutdown_timeout_logs_holder_identity` | ❌ W0 | ⬜ pending |
| 65-03-impl | 03 | 1 | RES-01 | — | n/a | unit + regression | `uv run pytest tests/test_scheduler.py -k "shutdown" -x` (covers new + existing `test_shutdown_drains_search_lock`, `test_shutdown_proceeds_after_lock_released`) | partial — 2 regression tests exist; 2 new tests Wave 0 | ⬜ pending |
| 65-04-W0a | 04 | 0 | TEST-04 | — | n/a | unit | add `test_aclose_does_not_hang_with_in_flight_requests` | ❌ W0 | ⬜ pending |
| 65-04-W0b | 04 | 0 | TEST-04 | — | n/a | unit | add `test_aclose_raises_when_requests_in_flight` (httpx documented behavior) | ❌ W0 | ⬜ pending |
| 65-04-impl | 04 | 1 | TEST-04 | — | n/a | unit | `uv run pytest tests/test_clients.py -k "aclose" -x` | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_scheduler.py` — ~9 new/edited tests covering SAFETY-02, SAFETY-03, RES-01 (listed above). Inversion of existing `test_make_search_job_exception_swallowed` is an EDIT, not a deletion.
- [ ] `tests/test_clients.py` — 2 new tests for TEST-04 (in-flight aclose pattern; `_ConcreteClient + MockTransport` pattern already established at line 21+).
- [ ] `tests/test_config.py` — 1 new test for `max_consecutive_failures` default (config-test pattern established by Phase 64).
- No framework install needed — pytest + pytest-asyncio + loguru already in `pyproject.toml [project.optional-dependencies] dev`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Operator observability of escalated ERROR log on real Radarr outage | SAFETY-03 | Requires sustained external-service failure | Stop Radarr container; wait for ≥5 search cycles; confirm log line escalates from WARNING to ERROR at the configured threshold |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
