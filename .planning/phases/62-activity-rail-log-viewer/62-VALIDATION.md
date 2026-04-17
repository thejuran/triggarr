---
phase: 62
slug: activity-rail-log-viewer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-17
---

# Phase 62 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 62-01-01 | 01 | 1 | RAIL-01 | — | N/A | unit | `uv run pytest tests/test_activity_rail.py -x -q` | ✅ | ⬜ pending |
| 62-01-02 | 01 | 1 | RAIL-02 | — | N/A | unit | `uv run pytest tests/test_activity_rail.py -x -q` | ✅ | ⬜ pending |
| 62-01-03 | 01 | 1 | RAIL-03 | — | N/A | unit | `uv run pytest tests/test_activity_rail.py -x -q` | ✅ | ⬜ pending |
| 62-02-01 | 02 | 1 | LOG-01 | — | N/A | unit | `uv run pytest tests/test_log_viewer.py -x -q` | ✅ | ⬜ pending |
| 62-02-02 | 02 | 1 | LOG-02 | — | N/A | unit | `uv run pytest tests/test_log_viewer.py -x -q` | ✅ | ⬜ pending |
| 62-02-03 | 02 | 1 | LOG-03 | — | N/A | unit | `uv run pytest tests/test_log_viewer.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Card-based entries with speech bubble pointers render visually correct | RAIL-01 | Visual layout verification | Open dashboard, verify activity rail cards have speech bubble CSS pointers and colored timeline dots |
| Opacity fade on older entries looks correct | RAIL-02 | Visual gradient verification | Scroll activity rail, verify older items fade with decreasing opacity |
| Phosphor icons display correctly in log viewer | LOG-01 | Icon rendering verification | Open log viewer, verify pause/expand icons are Phosphor-styled |
| Pulsing green dot animation on TAILING badge | LOG-02 | Animation verification | Open log viewer in tailing mode, verify green dot pulses |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
