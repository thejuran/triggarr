---
phase: 72-password-reset-backend-token-lifecycle
plan: "01"
subsystem: auth/reset
tags: [auth, password-reset, token-lifecycle, middleware, tdd]
dependency_graph:
  requires: []
  provides:
    - generate_reset_token() in triggarr/auth.py
    - /reset middleware exemption (M2-tightened) in triggarr/web/middleware.py
    - RESET_REQUEST_RATE_LIMIT_SECONDS=60 and RESET_CONFIRM_RATE_LIMIT_SECONDS=5 in triggarr/web/routes.py
    - app.state.reset_token=None and app.state.last_reset_time={} init in triggarr/search/scheduler.py
    - triggarr/templates/reset.html minimal shell
    - tests/test_reset.py all 22 RED specs
  affects:
    - triggarr/web/middleware.py (AuthMiddleware dispatch)
    - triggarr/search/scheduler.py (create_lifespan app.state block)
tech_stack:
  added: []
  patterns:
    - secrets.token_urlsafe(32) CSPRNG helper mirroring generate_session_secret
    - M2-tightened middleware exemption (exact-or-/reset/ predicate, not bare prefix)
    - monotonic timestamp dict pattern (app.state.last_reset_time mirroring last_search_time)
    - loguru temporary sink capture for test_token_in_mint_log
key_files:
  created:
    - triggarr/templates/reset.html
    - tests/test_reset.py
  modified:
    - triggarr/auth.py
    - triggarr/web/middleware.py
    - triggarr/web/routes.py
    - triggarr/search/scheduler.py
decisions:
  - "D-21 M2-tightened: /reset exemption uses exact-or-/reset/ predicate, not bare EXEMPT_PREFIXES append"
  - "D-02: token_in_mint_log test asserts PRESENCE in warning log (deliberate recovery channel)"
  - "D-22: generate_reset_token() thin wrapper in auth.py only"
  - "H1: live-token-noop test added per adversarial finding"
  - "reset.html uses hardcoded /reset/request and /reset/confirm action paths (url_for requires named routes not yet registered)"
metrics:
  duration: ~20 minutes
  completed: 2026-06-03
  tasks_completed: 3
  tasks_total: 3
  files_created: 2
  files_modified: 4
---

# Phase 72 Plan 01: Scaffold — generate_reset_token, /reset exemption (M2), rate-limit constants, app.state init, reset.html, RED tests Summary

**One-liner:** Phase 72 foundation scaffold — CSPRNG reset token helper, M2-tightened /reset middleware exemption (exact-or-/reset/ predicate), rate-limit constants, app.state init fields, minimal reset.html shell, and 22-test RED suite with loguru-capture and H1 live-token-noop guards.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | generate_reset_token + /reset exemption + rate-limit constants + app.state init | f2ec4e2 | triggarr/auth.py, triggarr/web/middleware.py, triggarr/web/routes.py, triggarr/search/scheduler.py |
| 2 | Minimal reset.html form shell | ebdc651 | triggarr/templates/reset.html |
| 3 | tests/test_reset.py RED suite (22 tests) | 3b11314 | tests/test_reset.py |

---

## What Was Built

### Task 1 — Scaffold (f2ec4e2)

**triggarr/auth.py:** Added `generate_reset_token() -> str` after `generate_session_secret()`, using `secrets.token_urlsafe(32)` (URL-safe alphabet, ~43 chars, 256 bits of entropy). No new import needed — `secrets` was already present. Docstring mirrors the `generate_session_secret` convention.

**triggarr/web/middleware.py:** Added M2-tightened `/reset` exemption in `AuthMiddleware.dispatch` using `path == "/reset" or path.startswith("/reset/")` — NOT a bare `EXEMPT_PREFIXES` append, which would over-expose any future `/resetXYZ` route. Updated the `EXEMPT_PREFIXES` comment to explain the deliberate exclusion. The predicate exempts `/reset`, `/reset/request`, and `/reset/confirm` while keeping `/resetXYZ` (and every other path) gated.

**triggarr/web/routes.py:** Added two constants immediately after `SEARCH_RATE_LIMIT_SECONDS = 10`:
- `RESET_REQUEST_RATE_LIMIT_SECONDS = 60` (log/file flooding prevention)
- `RESET_CONFIRM_RATE_LIMIT_SECONDS = 5` (token-guessing throttle)

**triggarr/search/scheduler.py:** In `create_lifespan`, inserted after `app.state.last_search_time = {}` and before `app.state.last_health_check = None`:
- `app.state.reset_token = None` — type: `tuple[str, float] | None` (D-04, D-18)
- `app.state.last_reset_time = {}` — type: `dict[str, float]` keyed `"request"`/`"confirm"` (D-14)

### Task 2 — reset.html (ebdc651)

Created `triggarr/templates/reset.html` (64 lines) extending `base-auth.html`. Single template with step conditional:
- `step == "request"`: POST form to `/reset/request` (submit-only, neutral confirmation)
- `step == "confirm"`: POST form to `/reset/confirm` with inputs `token`, `new_password`, `confirm_password`
- Renders `{{ error }}` for generic token failures (D-06) and `{{ errors["new_password"] }}` / `{{ errors["confirm_password"] }}` for field-level errors (D-20)
- The `token` field is an INPUT only — no `{{ token }}` Jinja expression echoes the value back (D-02)
- Hardcoded action paths (`/reset/request`, `/reset/confirm`) rather than `url_for` — named routes are not registered in Plan 01 (Plans 02/03 add handlers)

### Task 3 — RED test suite (3b11314)

Created `tests/test_reset.py` (717 lines) with:
- `_make_route_app` base helper (mirrors test_auth_routes.py pattern)
- `_make_reset_app` wrapping helper — adds `app.state.reset_token = None` and `app.state.last_reset_time = {}` (Pitfall 4 prevention)
- `_configured_reset_auth` and `_init_toml` helpers for TOML rotation tests
- 22 tests matching VALIDATION.md exactly, including both adversarial-findings additions:
  - `test_token_in_mint_log` — asserts token IS in a warning-level log record (D-02 deliberate recovery channel, uses loguru `logger.add` temporary sink to capture records)
  - `test_live_token_request_is_noop` — pre-seeds a live unexpired token and asserts a second POST /reset/request does not change it (H1 supersession-DoS guard)
  - `test_no_other_route_exposed` — asserts `/resetXYZ` returns non-200 while `/reset` and `/reset/request` return 200/404 (M2)

**Collection result:** `pytest --collect-only` lists 22 tests, 0 import errors, 0 collection errors.
**Existing suite:** 984 tests pass (no regressions).

---

## Deviations from Plan

None — plan executed exactly as written.

The only implementation choice note: `reset.html` uses hardcoded action paths (`/reset/request`, `/reset/confirm`) rather than `request.url_for('reset_request_post')` — the plan's Task 2 verify checks for the literal strings `/reset/request` and `/reset/confirm` in the file, and `url_for` requires named routes not yet registered in Plan 01. This is explicitly within Claude's Discretion for the minimal Phase 72 shell (Phase 73 will own the polished template where `url_for` will work correctly).

---

## Verification Results

```
uv run ruff check triggarr/ tests/        # All checks passed
uv run pytest tests/test_reset.py --collect-only -q  # 22 tests collected, 0 errors
uv run pytest tests/ -x -q --ignore=tests/test_reset.py  # 984 passed
```

Middleware predicate verified:
- `/reset` → exempt (path == "/reset")
- `/reset/request` → exempt (startswith("/reset/"))
- `/reset/confirm` → exempt (startswith("/reset/"))
- `/resetXYZ` → NOT exempt (M2)
- `"/reset"` is NOT in EXEMPT_PREFIXES

app.state.reset_token init: `grep -n "app.state.reset_token" triggarr/search/scheduler.py` → line 504, exactly one.
app.state.last_reset_time init: `grep -n "app.state.last_reset_time" triggarr/search/scheduler.py` → line 507, exactly one.

---

## Known Stubs

The 22 tests in `tests/test_reset.py` are RED — the three route handlers (`reset_request_page`, `reset_request_post`, `reset_confirm_post`) are not implemented until Plans 02/03. This is expected and intentional (TDD RED phase). The test stubs have correct assertions; they will go GREEN as handlers are implemented.

`reset.html` hardcodes action paths instead of `url_for` — intentional for the Phase 72 minimal shell (Phase 73 resolves to styled pages with `url_for`).

---

## Threat Flags

No new threat surface introduced by this plan that is not already in the plan's threat_model. The M2-tightened `/reset` exemption is correctly scoped.

---

## Self-Check: PASSED

Files exist:
- triggarr/auth.py — FOUND (generate_reset_token)
- triggarr/web/middleware.py — FOUND (/reset exemption)
- triggarr/web/routes.py — FOUND (RESET_REQUEST/CONFIRM_RATE_LIMIT_SECONDS)
- triggarr/search/scheduler.py — FOUND (app.state.reset_token, app.state.last_reset_time)
- triggarr/templates/reset.html — FOUND (64 lines)
- tests/test_reset.py — FOUND (22 tests)

Commits exist:
- f2ec4e2 — FOUND
- ebdc651 — FOUND
- 3b11314 — FOUND
