---
phase: 43
slug: update-notification-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 43 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio (asyncio_mode=auto) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~3 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 43-01-01 | 01 | 1 | VER-02 | unit | `uv run pytest tests/test_update_check.py -x -q` | ❌ W0 | ⬜ pending |
| 43-01-02 | 01 | 1 | VER-02 | unit | `uv run pytest tests/test_web.py -x -q -k dismiss_migration` | ❌ W0 | ⬜ pending |
| 43-01-03 | 01 | 1 | - | unit | `uv run pytest tests/test_config.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_update_check.py` — update check logic tests (VER-02a through VER-02d)
- [ ] `tests/test_web.py` — dismiss migration endpoint test (VER-02e)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Nav bar update badge visual | VER-02 | CSS/layout visual check | Start app, verify version badge shows in nav when update available |
| Migration banner display | - | Visual styling check | Create .migrated file in config dir, verify blue banner at top of dashboard |
| Migration banner dismiss | - | htmx interaction check | Click X on banner, verify it disappears and .migrated file is deleted |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
