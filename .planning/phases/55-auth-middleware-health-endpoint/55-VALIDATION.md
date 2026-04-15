---
phase: 55
slug: auth-middleware-health-endpoint
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 55 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]` asyncio_mode = "auto") |
| **Quick run command** | `uv run pytest tests/test_auth_middleware.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_auth_middleware.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 55-01-01 | 01 | 1 | MID-01 | T-55-01 | Unauthenticated browser request gets 302 redirect to /login | unit | `uv run pytest tests/test_auth_middleware.py::test_unauth_browser_redirect -x` | ❌ W0 | ⬜ pending |
| 55-01-02 | 01 | 1 | MID-04 | T-55-02 | Unauthenticated API request gets 401 JSON (not redirect) | unit | `uv run pytest tests/test_auth_middleware.py::test_browser_vs_api_response -x` | ❌ W0 | ⬜ pending |
| 55-01-03 | 01 | 1 | MID-02 | T-55-03 | Valid X-Api-Key passes through; timing-safe comparison via secrets.compare_digest | unit | `uv run pytest tests/test_auth_middleware.py::test_valid_api_key_passes -x` | ❌ W0 | ⬜ pending |
| 55-01-04 | 01 | 1 | MID-03 | T-55-04 | GET /health returns 200 without any auth | unit | `uv run pytest tests/test_auth_middleware.py::test_health_no_auth -x` | ❌ W0 | ⬜ pending |
| 55-01-05 | 01 | 1 | LOGIN-03 | T-55-05 | Basic mode returns 401 with WWW-Authenticate: Basic realm="Triggarr" | unit | `uv run pytest tests/test_auth_middleware.py::test_basic_auth_www_authenticate -x` | ❌ W0 | ⬜ pending |
| 55-01-06 | 01 | 1 | LOGIN-04 | T-55-06 | External mode trusts request as authenticated (passthrough) | unit | `uv run pytest tests/test_auth_middleware.py::test_external_passthrough -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_auth_middleware.py` — stubs for MID-01, MID-02, MID-03, MID-04, LOGIN-03, LOGIN-04
- [ ] Update `tests/conftest.py` — add `make_auth_app()` fixture or `make_settings()` with auth param
