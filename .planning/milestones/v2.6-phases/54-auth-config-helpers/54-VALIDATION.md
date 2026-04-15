---
phase: 54
slug: auth-config-helpers
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 54 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x with pytest-asyncio |
| **Config file** | `pyproject.toml` ([tool.pytest.ini_options]) |
| **Quick run command** | `uv run pytest tests/test_auth.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~3 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_auth.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 54-01-01 | 01 | 1 | LOGIN-05 | — | AuthConfig validates Literal method field | unit | `uv run pytest tests/test_auth.py -k "test_auth_config" -x -q` | ❌ W0 | ⬜ pending |
| 54-01-02 | 01 | 1 | LOGIN-05 | — | SecretStr fields redact in repr | unit | `uv run pytest tests/test_auth.py -k "test_secret" -x -q` | ❌ W0 | ⬜ pending |
| 54-02-01 | 02 | 1 | SETUP-03 | T-54-01 | bcrypt hash_password returns valid hash | unit | `uv run pytest tests/test_auth.py -k "test_hash" -x -q` | ❌ W0 | ⬜ pending |
| 54-02-02 | 02 | 1 | SETUP-03 | T-54-01 | verify_password uses constant-time comparison | unit | `uv run pytest tests/test_auth.py -k "test_verify" -x -q` | ❌ W0 | ⬜ pending |
| 54-02-03 | 02 | 1 | LOGIN-02 | T-54-02 | sign_session returns signed cookie string | unit | `uv run pytest tests/test_auth.py -k "test_sign" -x -q` | ❌ W0 | ⬜ pending |
| 54-02-04 | 02 | 1 | LOGIN-02 | T-54-02 | validate_session rejects expired/tampered cookies | unit | `uv run pytest tests/test_auth.py -k "test_validate" -x -q` | ❌ W0 | ⬜ pending |
| 54-02-05 | 02 | 1 | SETUP-03 | — | generate_api_key returns 32-char hex | unit | `uv run pytest tests/test_auth.py -k "test_api_key" -x -q` | ❌ W0 | ⬜ pending |
| 54-03-01 | 03 | 2 | — | — | collect_secrets includes auth secrets | unit | `uv run pytest tests/test_auth.py -k "test_collect" -x -q` | ❌ W0 | ⬜ pending |
| 54-03-02 | 03 | 2 | LOGIN-05 | — | Config round-trip preserves auth_method=Disabled | integration | `uv run pytest tests/test_auth.py -k "test_round_trip" -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_auth.py` — stubs for AuthConfig model, auth helpers, redaction, and config round-trip
- [ ] `bcrypt` and `itsdangerous` in dev dependencies

*Existing infrastructure covers test framework (pytest-asyncio already installed).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | — |

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
