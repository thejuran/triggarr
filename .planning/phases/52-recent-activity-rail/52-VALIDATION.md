---
phase: 52
slug: recent-activity-rail
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-13
---

# Phase 52 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pyproject.toml` (asyncio_mode=auto) |
| **Quick run command** | `uv run pytest tests/test_activity_rail.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_activity_rail.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 52-01-01 | 01 | 1 | RAIL-01 | — | N/A | unit | `uv run pytest tests/test_activity_rail.py::test_rail_has_sticky_classes -x` | ❌ W0 | ⬜ pending |
| 52-01-02 | 01 | 1 | RAIL-02 | — | N/A | unit | `uv run pytest tests/test_activity_rail.py::test_timeline_dots_present -x` | ❌ W0 | ⬜ pending |
| 52-01-03 | 01 | 1 | RAIL-03 | — | N/A | unit | `uv run pytest tests/test_activity_rail.py::test_entry_components -x` | ❌ W0 | ⬜ pending |
| 52-01-04 | 01 | 1 | RAIL-04 | — | N/A | unit | `uv run pytest tests/test_activity_rail.py::test_live_indicator_and_footer -x` | ❌ W0 | ⬜ pending |
| 52-01-05 | 01 | 1 | RAIL-05 | — | N/A | unit | `uv run pytest tests/test_activity_rail.py::test_hidden_below_xl -x` | ❌ W0 | ⬜ pending |
| 52-01-06 | 01 | 1 | RAIL-06 | — | N/A | unit | `uv run pytest tests/test_activity_rail.py::test_partial_returns_200 -x` | ❌ W0 | ⬜ pending |
| 52-01-07 | 01 | 1 | RAIL-07 | — | N/A | unit | `uv run pytest tests/test_activity_rail.py::test_no_inline_search_log -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_activity_rail.py` — stubs for RAIL-01..07
- [ ] Update `tests/test_web.py` — fix `test_dashboard_shows_search_log` and `test_search_log_partial_returns_200`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Sticky scroll behavior on wide viewport | RAIL-01 | CSS position:sticky requires browser viewport | Open dashboard at >=1280px, scroll main content, verify rail stays fixed |
| Timeline visual appearance (dots, connecting line, colors) | RAIL-02 | Visual rendering | Inspect timeline items in browser, verify green/amber/blue/gray/red dots with connecting vertical line |
| Rail hidden on narrow screens | RAIL-05 | Responsive breakpoint | Resize browser below xl breakpoint, verify rail disappears and main goes full-width |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
