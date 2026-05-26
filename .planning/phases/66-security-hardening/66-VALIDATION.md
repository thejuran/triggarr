---
phase: 66
slug: security-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-26
---

# Phase 66 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (asyncio_mode=auto) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/` |
| **Estimated runtime** | ~25–35 seconds for full suite (857 tests + ruff) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_<scope>.py -x -q` (scoped to the touched test file — e.g., `test_middleware.py` for SEC-01/SEC-03)
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite green AND `uv run ruff check triggarr/ tests/` exits 0
- **Max feedback latency:** 35 seconds

---

## Per-Task Verification Map

The planner will fill this in completely. Below is the verification scaffolding — every plan must produce tasks that map to one of these requirement IDs and types.

| Plan | Requirement | Verification Type | Automated Command |
|------|-------------|-------------------|-------------------|
| 66-01 (SEC-02 URL validator) | SEC-02 | unit | `uv run pytest tests/test_config.py::test_instance_url_rejects_apikey -x -q` |
| 66-02 (SEC-03 Basic auth chars) | SEC-03 | unit + integration | `uv run pytest tests/test_middleware.py::test_basic_auth_rejects_control_chars -x -q` |
| 66-03 (SEC-04 session_secret startup warn) | SEC-04 | unit | `uv run pytest tests/test_startup.py::test_warn_if_session_secret_short -x -q` |
| 66-04 (SEC-01 inline-handler migration — preparatory) | SEC-01 (part 1) | integration + grep | `uv run pytest tests/test_routes.py -x -q && ! grep -rE 'on(click\|change\|submit\|load\|blur\|focus\|keydown\|keyup\|input)=' triggarr/templates/` |
| 66-05 (SEC-01 nonce wiring + drop unsafe-inline) | SEC-01 (part 2) | integration | `uv run pytest tests/test_middleware.py::test_csp_has_nonce_no_unsafe_inline -x -q` |

---

## Wave 0 Requirements

No Wave 0 framework install needed — pytest + pytest-asyncio + httpx + loguru are all already in `pyproject.toml [dev]`. Existing test files (`tests/test_middleware.py`, `tests/test_config.py`, `tests/test_startup.py`, `tests/test_routes.py`) cover all phase requirements with established patterns.

- [x] `tests/test_middleware.py` exists — SEC-01, SEC-03 add tests here
- [x] `tests/test_config.py` exists — SEC-02 adds tests here
- [x] `tests/test_startup.py` exists — SEC-04 adds tests here
- [x] `tests/test_routes.py` exists — SEC-01 nonce integration test goes here (verifies header + rendered HTML)

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Browser DevTools confirms no CSP violations on dashboard, settings, setup, login pages | SEC-01 | `TestClient` does not enforce CSP — the browser is the only CSP enforcer | (1) Build local Docker image; (2) run container; (3) open dashboard in Chrome with DevTools Console open; (4) navigate dashboard → settings → security tab → log out → login; (5) confirm zero `Refused to execute inline script because it violates the following Content Security Policy directive` entries in console |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (N/A — all infrastructure exists)
- [ ] No watch-mode flags
- [ ] Feedback latency < 35s
- [ ] `nyquist_compliant: true` set in frontmatter (set after plans complete)
- [ ] Manual browser CSP verification scheduled before milestone deploy

**Approval:** pending
