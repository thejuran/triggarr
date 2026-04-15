---
phase: 57
slug: settings-security-nav-logout
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 57 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x with pytest-asyncio |
| **Config file** | `pyproject.toml` (asyncio_mode=auto) |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 57-01-01 | 01 | 1 | SET-01 | T-57-01 | Auth mode only accepts Forms/Basic/External | unit | `uv run pytest tests/test_settings_security.py -k test_auth_mode_change -x` | ❌ W0 | ⬜ pending |
| 57-01-02 | 01 | 1 | SET-02 | T-57-02 | Password change requires correct current password | unit | `uv run pytest tests/test_settings_security.py -k test_password_change -x` | ❌ W0 | ⬜ pending |
| 57-01-03 | 01 | 1 | SET-03 | — | API key regeneration writes new key atomically | unit | `uv run pytest tests/test_settings_security.py -k test_api_key_regenerate -x` | ❌ W0 | ⬜ pending |
| 57-01-04 | 01 | 1 | SET-04 | — | Disabled auth banner shown when method is Disabled | integration | `uv run pytest tests/test_settings_security.py -k test_disabled_banner -x` | ❌ W0 | ⬜ pending |
| 57-01-05 | 01 | 1 | LOGIN-05 | T-57-03 | Session remains valid after auth mode change | integration | `uv run pytest tests/test_settings_security.py -k test_session_survives_mode_change -x` | ❌ W0 | ⬜ pending |
| 57-02-01 | 02 | 1 | UI-03 | — | Security section renders in settings template | integration | `uv run pytest tests/test_settings_security.py -k test_security_section_renders -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_settings_security.py` — stubs for SET-01, SET-02, SET-03, SET-04, LOGIN-05, UI-03
- [ ] Fixtures: test client with auth session, temp config with auth section

*Existing test infrastructure (pytest-asyncio, httpx test client) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| UI matches AIDesigner artifact pixel-exact | UI-03 | Visual comparison | Compare rendered settings page Security section against AIDesigner run 8622a904 |
| Eye toggle reveals/hides API key | SET-03 | Client-side JS behavior | Click eye icon, verify key toggles between masked dots and plaintext |
| Clipboard copy works | SET-03 | Browser API | Click copy button, paste elsewhere, verify key value |
| Contextual auth mode warnings appear | SET-01 | Client-side JS behavior | Select each auth mode, verify correct warning text appears/hides |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
