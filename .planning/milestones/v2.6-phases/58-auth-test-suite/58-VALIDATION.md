---
phase: 58
slug: auth-test-suite
status: verified
nyquist_compliant: true
wave_0_complete: true
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
| 58-01-01 | 01 | 1 | SC-1 | T-58-01 | Middleware denies unauth | unit | `uv run pytest tests/test_auth_middleware.py -x -q` | Yes | green |
| 58-01-02 | 01 | 1 | SC-3 | T-58-01 | Wrong-secret cookie rejected | unit | `uv run pytest tests/test_auth_middleware.py -x -q -k wrong_secret` | Yes | green |
| 58-01-03 | 01 | 1 | SC-5 | T-58-02 | Invalid API keys rejected | unit | `uv run pytest tests/test_auth_middleware.py -x -q -k api_key` | Yes | green |
| 58-02-01 | 01 | 1 | SC-2 | — | Setup creates creds | integration | `uv run pytest tests/test_auth_routes.py -x -q -k setup` | Yes | green |
| 58-02-02 | 01 | 1 | SC-3 | T-58-03 | Login/logout lifecycle + open redirect defense | integration | `uv run pytest tests/test_auth_routes.py -x -q -k login` | Yes | green |
| 58-02-03 | 01 | 1 | SC-4 | T-58-04 | Auth mode isolation + disabled warning | unit | `uv run pytest tests/test_auth_middleware.py -x -q -k "mode or transition or disabled"` | Yes | green |
| 58-03-01 | 02 | 2 | Cross | T-58-05,T-58-06,T-58-07 | E2E auth flows (setup->login->use->logout) | integration | `uv run pytest tests/test_auth_integration.py -x -q` | Yes | green |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `tests/test_auth_integration.py` — new file for cross-cutting flows (D-02) — 3 tests green
- [x] Traceability comment blocks in all 5 test files (D-03) — verified in all auth test files

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | — |

*All phase behaviors have automated verification.*

---

## Validation Audit 2026-04-15

| Metric | Count |
|--------|-------|
| Tasks audited | 7 |
| COVERED | 7 |
| PARTIAL | 0 |
| MISSING | 0 |
| Total auth tests | 109 |

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** verified 2026-04-15
