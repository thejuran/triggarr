---
phase: 49
slug: stats-health-strip
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-13
---

# Phase 49 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x with pytest-asyncio |
| **Config file** | `pyproject.toml` (pytest section) |
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
| 49-01-01 | 01 | 1 | STATS-01 | — | N/A | visual | Manual browser check | N/A | ⬜ pending |
| 49-01-02 | 01 | 1 | STATS-01 | — | N/A | unit | `uv run pytest tests/ -x -q -k health` | ❌ W0 | ⬜ pending |
| 49-02-01 | 02 | 1 | STATS-02 | — | N/A | visual | Manual browser check | N/A | ⬜ pending |
| 49-02-02 | 02 | 1 | STATS-03 | — | N/A | unit | `uv run pytest tests/ -x -q -k badge` | ❌ W0 | ⬜ pending |
| 49-02-03 | 02 | 1 | STATS-04 | — | N/A | visual | Manual browser check | N/A | ⬜ pending |
| 49-03-01 | 03 | 1 | STATS-05 | — | N/A | visual | Manual browser check | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Existing test infrastructure covers phase requirements
- [ ] `tests/test_web.py` — extend with health strip and stats row template assertions if needed

*Existing infrastructure covers most phase requirements. Visual verification is primary for UI layout changes.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Health strip renders as single-line with colored dots | STATS-01 | Visual layout check | Load dashboard, verify strip above stats grid |
| Grab Rate card spans 2 columns with large percentage | STATS-02 | Visual layout check | Load dashboard, verify hero card size and text-4xl |
| Health badge shows correct color for rate threshold | STATS-03 | Visual + threshold logic | Check badge at various grab rates |
| Per-app bars render with correct colors | STATS-04 | Visual color check | Load dashboard with multiple app types configured |
| Shadow-sm elevation visible on stat cards | STATS-05 | Visual depth check | Compare cards against flat background |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
