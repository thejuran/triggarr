---
phase: 42
slug: dashboard-enhancements
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 42 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (asyncio_mode=auto) |
| **Config file** | `pyproject.toml` |
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
| 42-01-01 | 01 | 1 | INST-07 | unit | `uv run pytest tests/test_web.py -x -q -k health_summary` | ❌ W0 | ⬜ pending |
| 42-01-02 | 01 | 1 | TAG-05 | unit | `uv run pytest tests/test_web.py -x -q -k tag_warning` | ❌ W0 | ⬜ pending |
| 42-01-03 | 01 | 1 | TAG-05 | unit | `uv run pytest tests/test_search.py -x -q -k tag_warning_state` | ❌ W0 | ⬜ pending |
| 42-01-04 | 01 | 1 | OBS-03 | unit | `uv run pytest tests/test_web.py -x -q -k stats_instance` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_web.py` — health summary partial tests (INST-07)
- [ ] `tests/test_web.py` — tag warning rendering tests (TAG-05)
- [ ] `tests/test_search.py` — tag warning state storage tests (TAG-05 data path)
- [ ] `tests/test_web.py` — instance-filtered stats partial tests (OBS-03)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Health card visual layout | INST-07 | CSS/layout visual check | Load dashboard with 2+ instances, verify card at top with counts |
| Tag warning amber badge | TAG-05 | Visual styling check | Configure invalid tag name, verify amber warning on app card |
| Stats dropdown interaction | OBS-03 | htmx swap UX check | Select instance from dropdown, verify stats row updates without page reload |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
