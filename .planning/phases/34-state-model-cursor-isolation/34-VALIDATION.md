---
phase: 34
slug: state-model-cursor-isolation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 34 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | `pyproject.toml` (asyncio_mode=auto) |
| **Quick run command** | `uv run pytest tests/test_state.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_state.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 34-01-01 | 01 | 1 | INST-03a | unit | `uv run pytest tests/test_state.py::test_independent_instance_cursors -x` | ❌ W0 | ⬜ pending |
| 34-01-02 | 01 | 1 | INST-03b | unit | `uv run pytest tests/test_state.py::test_per_instance_round_trip -x` | ❌ W0 | ⬜ pending |
| 34-01-03 | 01 | 1 | INST-03c | unit | `uv run pytest tests/test_state.py::test_v22_state_migration -x` | ❌ W0 | ⬜ pending |
| 34-01-04 | 01 | 1 | INST-03d | unit | `uv run pytest tests/test_state.py::test_orphan_cleanup -x` | ❌ W0 | ⬜ pending |
| 34-01-05 | 01 | 1 | INST-03e | unit | `uv run pytest tests/test_state.py::test_no_cross_contamination -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_state.py` — new tests for nested format, migration, orphan cleanup, cross-contamination
- [ ] `tests/conftest.py` — `default_state()` fixture needs updating for nested format
- [ ] Existing `test_state.py` tests need updating (they assert flat format)

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
