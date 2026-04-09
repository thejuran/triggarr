---
phase: 46
slug: test-hardening-infrastructure-failures
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-09
---

# Phase 46 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | pyproject.toml (asyncio_mode = "auto") |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 46-01-01 | 01 | 1 | CONN-01 | — | N/A | unit | `uv run pytest tests/test_clients.py tests/test_search.py -x -q -k "timeout_cycle or unreachable_since"` | ❌ W0 | ⬜ pending |
| 46-01-02 | 01 | 1 | CONN-02 | — | N/A | unit | `uv run pytest tests/test_clients.py tests/test_search.py -x -q -k "dns"` | ❌ W0 | ⬜ pending |
| 46-01-03 | 01 | 1 | CONN-03 | — | N/A | unit | `uv run pytest tests/test_clients.py tests/test_search.py -x -q -k "ssl"` | ❌ W0 | ⬜ pending |
| 46-01-04 | 01 | 1 | CONN-04 | — | N/A | unit | `uv run pytest tests/test_search.py -x -q -k "all_search_fail or mid_cycle"` | ❌ W0 | ⬜ pending |
| 46-02-01 | 02 | 1 | API-01 | — | N/A | unit | `uv run pytest tests/test_clients.py tests/test_search.py -x -q -k "malformed or invalid_json or decoding"` | ❌ W0 | ⬜ pending |
| 46-02-02 | 02 | 1 | API-02 | — | N/A | unit | `uv run pytest tests/test_clients.py tests/test_search.py -x -q -k "403 or 502 or status_code"` | ❌ W0 | ⬜ pending |
| 46-02-03 | 02 | 1 | API-03 | — | N/A | unit | `uv run pytest tests/test_startup.py -x -q -k "detect_api_version"` | Partial | ⬜ pending |
| 46-02-04 | 02 | 1 | API-04 | — | N/A | unit | `uv run pytest tests/test_clients.py -x -q -k "truncat or paginated"` | Partial | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

- No new test frameworks needed
- No new fixtures needed (`_ConcreteClient`, `_make_test_state`, `_cycle_settings`, `_cycle_instance_config` all exist)
- No new config needed

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
