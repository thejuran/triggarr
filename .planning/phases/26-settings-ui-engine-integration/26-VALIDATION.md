---
phase: 26
slug: settings-ui-engine-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 26 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (auto mode) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_web.py tests/test_search.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_web.py tests/test_search.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 26-01-01 | 01 | 1 | CFG-01a | unit | `uv run pytest tests/test_web.py -k "skip_unreleased" -x` | ❌ W0 | ⬜ pending |
| 26-01-02 | 01 | 1 | CFG-01b | unit | `uv run pytest tests/test_web.py -k "skip_unreleased" -x` | ❌ W0 | ⬜ pending |
| 26-01-03 | 01 | 1 | CFG-01c | unit | `uv run pytest tests/test_search.py -k "skip_unreleased" -x` | ❌ W0 | ⬜ pending |
| 26-01-04 | 01 | 1 | CFG-01d | unit | `uv run pytest tests/test_search.py -k "skip_unreleased" -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_web.py` — new tests for skip_unreleased checkbox rendering + save round-trip
- [ ] `tests/test_search.py` or `tests/test_web.py` — new tests for engine conditional filter call
- [ ] `tests/test_web.py` — mock_settings fixture needs `skip_unreleased = True` added

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual checkbox alignment | CFG-01a | CSS rendering | Open settings page, verify checkbox is aligned with other toggles |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
