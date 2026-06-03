---
phase: 72-password-reset-backend-token-lifecycle
plan: "03"
subsystem: auth/reset
tags: [auth, password-reset, token-confirm, session-rotation, tdd, atomic-write]
dependency_graph:
  requires:
    - generate_reset_token() in triggarr/auth.py (Plan 01)
    - RESET_CONFIRM_RATE_LIMIT_SECONDS in triggarr/web/routes.py (Plan 01)
    - app.state.reset_token / app.state.last_reset_time init (Plan 01)
    - /reset middleware exemption (Plan 01)
    - tests/test_reset.py RED suite (Plan 01)
    - reset_request_post / _write_reset_token_file (Plan 02)
  provides:
    - POST /reset/confirm → reset_confirm_post handler in triggarr/web/routes.py
  affects:
    - tests/test_reset.py (all 12 confirm-path tests go GREEN; full 22-test suite GREEN)
tech_stack:
  added: []
  patterns:
    - secrets.compare_digest inside search_lock (TOCTOU guard, D-08/Pitfall 3)
    - change_password apply block mirrored exactly (hash→rotate→model_copy→atomic_write→chmod→load_settings)
    - H2 read-back assertion (reloaded_secret == new_session_secret before cookie signing)
    - Single lock acquisition (M3 anti-deadlock: one async with covers rate-recheck + field validation + token validation + apply)
    - D-19 non-fatal token-file deletion (OSError → warning, proceed)
key_files:
  created: []
  modified:
    - triggarr/web/routes.py
decisions:
  - "[Rule 1 - Bug] Field validation moved inside lock: pre-lock placement prevented rate-limit timestamp from being set on field-error responses, allowing rapid field-error cycling to bypass the 5s window. Stamp must fire before any return path from the confirm handler."
  - "H2 assertion placed AFTER load_settings and BEFORE sign_session: proves cookie-signed-with-persisted-secret invariant rather than assuming it (Pitfall 2 / ordering F)."
  - "All failure paths (bad token, expired, field errors, rate-limit) leave app.state.reset_token and password_hash unchanged (D-06/D-09 no-state-change contract)."
metrics:
  duration: ~25 minutes
  completed: 2026-06-03
  tasks_completed: 1
  tasks_total: 1
  files_created: 0
  files_modified: 1
---

# Phase 72 Plan 03: Reset-Confirm/Apply Path — GREEN Implementation Summary

**One-liner:** reset_confirm_post implemented — single-lock token-validated apply path mirroring change_password with H2 read-back assertion, session-secret rotation, single-use cleanup, and 303 auto-login under the new secret; all 22 reset tests GREEN.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | GREEN: reset_confirm_post (POST /reset/confirm apply path) | 4224314 | triggarr/web/routes.py |

---

## What Was Built

### Task 1 — GREEN Implementation (4224314)

**triggarr/web/routes.py:** One addition — `reset_confirm_post` (POST /reset/confirm), 155 lines inserted after `reset_request_post`.

**Handler structure (single `async with search_lock` — M3):**

1. **Optimistic rate-limit check** (pre-lock): reads `last_reset_time["confirm"]`, returns 429 if within 5s window. Fast-fail for obvious cases.

2. **Single lock acquisition** — `async with request.app.state.search_lock:` — all subsequent steps execute within this one block:

   - **In-lock rate re-check + stamp**: concurrent bypass prevention (DRSEC-03 discipline). Rate-limit stamp set HERE so all confirm attempts (including field-error returns) count against the window.

   - **Password field validation** (D-09/D-20): `new_password` empty → `{"new_password": "New password is required"}`; mismatch → `{"confirm_password": "Passwords do not match"}`. Per-field errors dict, no state change, returns `reset.html` with `step="confirm"` + `errors`.

   - **Token validation** (D-06/D-08): `stored = app.state.reset_token`; if `stored is None` OR `time.monotonic() >= stored[1]` OR `not secrets.compare_digest(token, stored[0])` → generic `"Invalid or expired reset token"`, no state change, no detail leak. `secrets.compare_digest` is INSIDE the lock (Pitfall 3 / TOCTOU guard).

   - **Apply block** (D-10, change_password order exactly): `hash_password(new_password)` (ValueError → 72-char field error) → `generate_session_secret()` → `model_copy(update={password_hash: SecretStr(new_hash), session_secret: SecretStr(new_session_secret)})` → `model_copy(update={auth: new_auth})` → `run_in_executor(_atomic_toml_write, ...)` → `os.chmod(config_path, 0o600)` → `load_settings(config_path)`.

   - **H2 read-back assertion**: `reloaded_secret = app.state.settings.auth.session_secret.get_secret_value(); assert reloaded_secret == new_session_secret` — proves the auto-login cookie will be signed with the PERSISTED secret, not an in-flight local that diverged from disk (Pitfall 2 / ordering F).

   - **Single-use cleanup** (D-07): `app.state.reset_token = None`; `(_runtime_config_dir(request) / "reset-token.txt").unlink(missing_ok=True)`. `OSError` on deletion → `logger.warning("Failed to delete reset token file: {exc}")` — no token value in message, proceed (D-19 non-fatal).

3. **Post-lock refresh chain** (D-11): `_sync_auth_state(settings)` → `collect_secrets(settings)` → `setup_logging(log_level, new_secrets)`. Rotated `session_secret` and unchanged-key `password_hash` fed to redacting sink. Reset token NOT in `collect_secrets` (by design — it is the deliberate log channel).

4. **Auto-login** (D-13): `RedirectResponse(url=request.url_for("dashboard"), status_code=303)` + `set_cookie("triggarr_session", sign_session(refreshed_username, new_session_secret), max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax", secure=is_secure_request(request))`. Cookie signed with captured `new_session_secret` local (proven == reloaded secret by H2 assertion above — never re-read from `app.state` for signing). User lands on dashboard, logged in.

5. **Info log** (D-02 compliance): `logger.info("Password reset applied; session secret rotated, other sessions invalidated")` — no token value, no old/new secret values.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Field validation moved inside lock to ensure rate-limit stamp fires on all confirm paths**

- **Found during:** Task 1 — `test_confirm_rate_limited` failed (200 instead of 429 on second request)
- **Issue:** Plan specified pre-lock field validation. When the first confirm has mismatched passwords, the handler returns 200 via the pre-lock path WITHOUT entering the `async with` block, so `last_reset_time["confirm"]` is never stamped. A second rapid request passes the optimistic rate check (timestamp still 0) and also returns 200 — the rate window is never enforced on field-error paths.
- **Fix:** Moved password field validation INTO the `async with search_lock` block, AFTER the in-lock rate re-check + stamp. The stamp now fires for every confirm attempt that passes the optimistic pre-lock check, regardless of whether it proceeds to token validation or returns a field error. This is the only correct position for field validation given the M3 single-acquisition constraint (moving the stamp outside the lock would violate the double-check pattern).
- **Files modified:** triggarr/web/routes.py
- **Commit:** 4224314

---

## Verification Results

```
uv run ruff check triggarr/web/routes.py    # All checks passed

uv run pytest tests/test_reset.py -x -q    # 22 passed

uv run pytest tests/ -x -q                 # 1006 passed
```

**Single-acquire check (M3):** `grep -nc "async with request.app.state.search_lock" triggarr/web/routes.py` → 10 (up from 9 in Plan 02; exactly one acquisition in `reset_confirm_post`). The optimistic rate-check is the ONLY pre-lock check; in-lock rate re-check + stamp + field validation + token validation + apply are all in the single `async with` block.

**Token-compare-in-lock check:** `grep -n "secrets.compare_digest" triggarr/web/routes.py` shows line 1786 (reset token compare) inside the `async with ... search_lock:` block of `reset_confirm_post`. The existing username compare at line 1349 (login_post) is also inside its own lock context.

**Cookie-ordering + read-back check (H2):** `assert reloaded_secret == new_session_secret` appears AFTER `request.app.state.settings = load_settings(config_path)` and BEFORE the `sign_session(..., new_session_secret)` call. `test_new_cookie_validates_after_reset` proves the new cookie validates under the reloaded secret.

**Confirm-time redaction grep:** `grep -nE "logger\.(warning|error|info)" ... | grep -i "reset|confirm|token"` → only `logger.info("Password reset applied; session secret rotated...")` — no token value in confirm-time log lines.

**Tests going GREEN (12 confirm-path tests):**
- `test_expired_token_rejected` — PASS
- `test_confirm_success_redirects_with_cookie` — PASS
- `test_confirm_rotates_session_secret` — PASS
- `test_pre_reset_cookie_invalid_after_reset` — PASS
- `test_new_cookie_validates_after_reset` — PASS
- `test_token_single_use` — PASS
- `test_wrong_token_generic_error` — PASS
- `test_password_mismatch_field_error` — PASS
- `test_empty_password_field_error` — PASS
- `test_password_too_long_field_error` — PASS
- `test_confirm_rate_limited` — PASS
- `test_token_file_deleted_on_success` — PASS

---

## Known Stubs

None. The `reset.html` template renders `error`, `errors`, and `step` context keys correctly (minimal shell from Plan 01). Phase 73 will style the form pages. The handler's success path wires directly to real data.

---

## Threat Flags

No new threat surface beyond what is in the plan's threat_model. All STRIDE mitigations verified:

| Threat ID | Status | Evidence |
|-----------|--------|---------|
| T-72-replay | MITIGATED | `app.state.reset_token = None` after success; test_token_single_use GREEN |
| T-72-expiry | MITIGATED | `time.monotonic() >= stored[1]` inside lock; test_expired_token_rejected GREEN |
| T-72-enum | MITIGATED | Single generic "Invalid or expired reset token" for all token failures; test_wrong_token_generic_error GREEN |
| T-72-bruteforce | MITIGATED | 5s global rate window (stamp fires on all confirm paths including field errors); test_confirm_rate_limited GREEN |
| T-72-deadlock | MITIGATED | Exactly ONE `async with search_lock` acquisition in reset_confirm_post; grep confirms count=10 (one added) |
| T-72-replay-toctou | MITIGATED | secrets.compare_digest INSIDE search_lock; in-lock rate re-check confirms no TOCTOU window |
| T-72-session | MITIGATED | generate_session_secret() + model_copy + persist + reload + H2 assertion + sign with local; test_confirm_rotates_session_secret + test_pre_reset_cookie_invalid_after_reset + test_new_cookie_validates_after_reset GREEN |
| T-72-redaction | MITIGATED | No token value in any confirm-time log/error/header/response; logger.info line confirmed clean |
| T-72-cleanup | ACCEPTED (degrade gracefully) | OSError on file deletion → warning (no token), proceed; D-19 |
| T-72-72byte | MITIGATED | hash_password ValueError → per-field error; test_password_too_long_field_error GREEN |

---

## TDD Gate Compliance

RED gate: tests were committed RED in Plan 01 (commit 3b11314) — the RED gate was satisfied in Wave 1.
GREEN gate: implementation committed in this plan (commit 4224314) — feat(72-03) commit exists after the RED test commit.
Gate sequence: test(72-01) → feat(72-02) [request path] → feat(72-03) [confirm path]. COMPLIANT.

---

## Self-Check: PASSED

Files exist:
- triggarr/web/routes.py — FOUND (reset_confirm_post added at end of Phase 72 section)
- triggarr/web/routes.py contains reset_confirm_post — FOUND

Commits exist:
- 4224314 — FOUND (feat(72-03): implement reset_confirm_post — token-validated apply path)

Test counts:
- 22 reset tests GREEN (all confirm-path + request-path tests)
- 1006 total tests pass (984 baseline + 22 reset)
