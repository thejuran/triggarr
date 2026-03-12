---
phase: 41
slug: multi-instance-settings-ui
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 41 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (asyncio_mode=auto) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_web.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_web.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 41-01-01 | 01 | 0 | INST-05 | unit | `uv run pytest tests/test_web.py -x -q -k "test_settings_all_instances"` | ❌ W0 | ⬜ pending |
| 41-01-02 | 01 | 0 | INST-05 | unit | `uv run pytest tests/test_web.py -x -q -k "test_add_instance"` | ❌ W0 | ⬜ pending |
| 41-01-03 | 01 | 0 | INST-05 | unit | `uv run pytest tests/test_web.py -x -q -k "test_remove_instance"` | ❌ W0 | ⬜ pending |
| 41-01-04 | 01 | 0 | INST-05 | unit | `uv run pytest tests/test_web.py -x -q -k "test_save_multi_instance"` | ❌ W0 | ⬜ pending |
| 41-01-05 | 01 | 0 | INST-06 | unit | `uv run pytest tests/test_web.py -x -q -k "test_instance_enable_disable"` | ❌ W0 | ⬜ pending |
| 41-01-06 | 01 | 0 | TAG-06 | unit | `uv run pytest tests/test_web.py -x -q -k "test_tag_autocomplete"` | ❌ W0 | ⬜ pending |
| 41-01-07 | 01 | 0 | TAG-06 | unit | `uv run pytest tests/test_web.py -x -q -k "test_tag_fields_in_form"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_web.py` — stubs for INST-05 (multi-instance CRUD)
- [ ] `tests/test_web.py` — stubs for INST-06 (enable/disable toggle)
- [ ] `tests/test_web.py` — stubs for TAG-06 (tag autocomplete endpoint)
- [ ] `tests/test_validation.py` — stubs for instance name validation

*Existing test infrastructure — `test_web.py` fixture `test_app` with mocked state — covers the foundation. New tests extend existing patterns.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tag autocomplete UX | TAG-06 | Browser datalist behavior | Open settings, click tag field, verify suggestions appear from *arr instance |
| Accordion expand/collapse | INST-05 | Visual interaction | Open settings, verify details/summary toggles for each instance |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
