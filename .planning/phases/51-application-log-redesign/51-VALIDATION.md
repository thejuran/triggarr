---
phase: 51
slug: application-log-redesign
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-13
---

# Phase 51 — Validation Strategy

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
| 51-01-01 | 01 | 1 | LOG-01 | — | N/A | visual+unit | `uv run pytest tests/test_log_viewer.py -x -q` | ❌ W0 | ⬜ pending |
| 51-01-02 | 01 | 1 | LOG-02 | — | N/A | visual+unit | `uv run pytest tests/test_log_viewer.py -x -q` | ❌ W0 | ⬜ pending |
| 51-01-03 | 01 | 1 | LOG-03 | — | N/A | visual+unit | `uv run pytest tests/test_log_viewer.py -x -q` | ❌ W0 | ⬜ pending |
| 51-02-01 | 02 | 1 | LOG-04 | — | N/A | visual | Manual browser check | N/A | ⬜ pending |
| 51-02-02 | 02 | 1 | LOG-05 | — | N/A | integration | `uv run pytest tests/test_log_viewer.py -x -q` | ❌ W0 | ⬜ pending |
| 51-02-03 | 02 | 1 | LOG-06 | — | N/A | integration | `uv run pytest tests/test_log_viewer.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_log_viewer.py` — stubs for LOG-01 through LOG-06
- [ ] Test fixtures for mock log entries with various levels and source prefixes

*Existing pytest infrastructure covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Geist Mono column-aligned rows | LOG-01 | Visual font rendering | Open dashboard, verify monospace alignment in log panel |
| TAILING indicator with pulsing dot | LOG-02 | CSS animation visual | Open dashboard, verify green pulsing dot in log header |
| Scanline effect in expanded pane | LOG-04 | CSS visual overlay | Click expand icon, verify scanline lines visible over log |
| Expanded pane stays fixed on scroll | LOG-04 | Scroll behavior | Expand log, scroll dashboard, verify pane stays pinned |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
