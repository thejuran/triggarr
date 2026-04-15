---
phase: 58
slug: auth-test-suite
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 58 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `uv run pytest tests/test_auth_middleware.py tests/test_auth_routes.py tests/test_auth_integration.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_auth_middleware.py tests/test_auth_routes.py tests/test_auth_integration.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 58-01-01 | 01 | 1 | SC-1 | — | Middleware denies unauth | unit | `uv run pytest tests/test_auth_middleware.py -x -q` | Yes | pending |
| 58-01-02 | 01 | 1 | SC-3 | — | Wrong-secret cookie rejected | unit | `uv run pytest tests/test_auth_middleware.py -x -q -k wrong_secret` | No -- gap-fill | pending |
| 58-01-03 | 01 | 1 | SC-5 | — | Invalid API keys rejected | unit | `uv run pytest tests/test_auth_middleware.py -x -q -k api_key` | No -- gap-fill | pending |
| 58-02-01 | 02 | 1 | SC-2 | — | Setup creates creds | integration | `uv run pytest tests/test_auth_routes.py -x -q -k setup` | Yes | pending |
| 58-02-02 | 02 | 1 | SC-3 | — | Login/logout lifecycle | integration | `uv run pytest tests/test_auth_routes.py -x -q -k login` | Yes -- gap-fill | pending |
| 58-02-03 | 02 | 1 | SC-4 | — | Auth mode isolation | unit | `uv run pytest tests/test_auth_middleware.py -x -q -k mode` | No -- gap-fill | pending |
| 58-03-01 | 03 | 2 | Cross | — | E2E auth flows | integration | `uv run pytest tests/test_auth_integration.py -x -q` | No -- Wave 0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_auth_integration.py` — new file for cross-cutting flows (D-02)
- [ ] Traceability comment blocks in all 5 test files (D-03)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | — |

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
