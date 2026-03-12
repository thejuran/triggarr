---
phase: 41
slug: multi-instance-settings-ui
status: draft
nyquist_compliant: true
wave_0_complete: true
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

## Wave 0 Strategy

Task 1 in Plan 01 uses `tdd="true"`, which means tests are written FIRST (RED phase) before any production code (GREEN phase). This TDD cycle inherently satisfies Wave 0 intent -- all test files exist and fail before implementation begins. No separate Wave 0 stub task is needed.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | TDD | Status |
|---------|------|------|-------------|-----------|-------------------|-----|--------|
| 41-01-01 | 01 | 1 | INST-05 | unit | `uv run pytest tests/test_web.py -x -q -k "test_settings_all_instances"` | tdd=true (RED first) | ⬜ pending |
| 41-01-02 | 01 | 1 | INST-05 | unit | `uv run pytest tests/test_web.py -x -q -k "test_add_instance"` | tdd=true (RED first) | ⬜ pending |
| 41-01-03 | 01 | 1 | INST-05 | unit | `uv run pytest tests/test_web.py -x -q -k "test_remove_instance"` | tdd=true (RED first) | ⬜ pending |
| 41-01-04 | 01 | 1 | INST-05 | unit | `uv run pytest tests/test_web.py -x -q -k "test_save_multi_instance"` | tdd=true (RED first) | ⬜ pending |
| 41-01-05 | 01 | 1 | INST-06 | unit | `uv run pytest tests/test_web.py -x -q -k "test_instance_enable_disable"` | tdd=true (RED first) | ⬜ pending |
| 41-01-06 | 01 | 1 | TAG-06 | unit | `uv run pytest tests/test_web.py -x -q -k "test_tag_autocomplete"` | tdd=true (RED first) | ⬜ pending |
| 41-01-07 | 01 | 1 | TAG-06 | unit | `uv run pytest tests/test_web.py -x -q -k "test_tag_fields_in_form"` | tdd=true (RED first) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tag autocomplete UX | TAG-06 | Browser datalist behavior | Open settings, click tag field, verify suggestions appear from *arr instance |
| Accordion expand/collapse | INST-05 | Visual interaction | Open settings, verify details/summary toggles for each instance |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or TDD cycle covers Wave 0
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covered by tdd="true" on Task 1 (tests written before implementation)
- [x] No watch-mode flags
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready
