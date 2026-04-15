---
phase: 57
slug: settings-security-nav-logout
status: draft
nyquist_compliant: true
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
| 57-01-01 | 01 | 1 | SET-01 | T-57-02 | Auth mode only accepts Forms/Basic/External | unit | `uv run pytest tests/test_auth_routes.py -k "test_security_save_method_basic or test_security_save_rejects_disabled or test_security_save_rejects_invalid" -x` | ✅ Plan 01 Task 1 | ⬜ pending |
| 57-01-02 | 01 | 1 | SET-02 | T-57-01 | Password change requires correct current password | unit | `uv run pytest tests/test_auth_routes.py -k "test_change_password" -x` | ✅ Plan 01 Task 1 | ⬜ pending |
| 57-01-03 | 01 | 1 | SET-03 | — | API key regeneration writes new key atomically | unit | `uv run pytest tests/test_auth_routes.py -k "test_regenerate_api_key" -x` | ✅ Plan 01 Task 1 | ⬜ pending |
| 57-01-04 | 01 | 1 | SET-04 | — | Disabled auth banner context present when method is Disabled | integration | `uv run pytest tests/test_auth_routes.py -k "test_settings_page_disabled_banner" -x` | ✅ Plan 01 Task 1 | ⬜ pending |
| 57-01-05 | 01 | 1 | LOGIN-05 | T-57-03 | Settings page auth context includes expected variables | integration | `uv run pytest tests/test_auth_routes.py -k "test_settings_page_auth_context" -x` | ✅ Plan 01 Task 1 | ⬜ pending |
| 57-02-01 | 02 | 2 | UI-03 | — | Security section renders in settings template | integration | `uv run pytest tests/test_auth_routes.py -x -q` (full suite, templates verified by Jinja2 parse check) | ✅ Plan 01 Task 1 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_auth_routes.py` — tests for SET-01, SET-02, SET-03, SET-04, LOGIN-05 created by Plan 01 Task 1 (TDD RED phase)
- [x] Fixtures: existing `_make_route_app` factory, test client with auth session, temp config

*All Wave 0 test scaffolding is handled by Plan 01 Task 1 (TDD plan, RED phase writes all failing tests first).*

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

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
