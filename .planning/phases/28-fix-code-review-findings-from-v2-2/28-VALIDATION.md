---
phase: 28
slug: fix-code-review-findings-from-v2-2
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 28 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (auto mode) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Finding | Test Type | Automated Command | File Exists | Status |
|---------|------|------|---------|-----------|-------------------|-------------|--------|
| 28-01-01 | 01 | 1 | F1 | unit | `uv run pytest tests/test_search.py -k "eligible" -x` | Needs update | ⬜ pending |
| 28-01-02 | 01 | 1 | F1 | unit | `uv run pytest tests/test_web.py::test_app_card_skip_indicator_shown -x` | Needs update | ⬜ pending |
| 28-02-01 | 02 | 1 | F2 | manual | Visual inspection | N/A | ⬜ pending |
| 28-03-01 | 03 | 1 | F4 | unit | `uv run pytest tests/test_search.py -k "unreleased" -x` | New test | ⬜ pending |
| 28-04-01 | 04 | 1 | M3 | unit | `uv run pytest tests/ -x -q` | Existing | ⬜ pending |
| 28-04-02 | 04 | 1 | M5 | lint | `uv run ruff check triggarr/ --select T201` | N/A | ⬜ pending |
| 28-04-03 | 04 | 1 | M6 | lint | `uv run ruff check triggarr/ --select UP006` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. Tests need updating (not creation from scratch).

---

## Manual-Only Verifications

| Behavior | Finding | Why Manual | Test Instructions |
|----------|---------|------------|-------------------|
| Settings checkbox styling | F2 | CSS/HTML layout visual | Inspect settings page, verify `<p>` tag is inside checkbox parent div |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
