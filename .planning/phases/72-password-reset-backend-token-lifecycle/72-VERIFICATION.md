---
phase: 72-password-reset-backend-token-lifecycle
verified: 2026-06-03T00:00:00Z
status: passed
score: 7/7 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 72: Password Reset Backend & Token Lifecycle — Verification Report

**Phase Goal:** A locked-out operator with host access can mint a reset token and use it to set a new password — entirely through HTTP, without hand-editing `triggarr.toml` — while a remote attacker hitting the same endpoints gains nothing.
**Verified:** 2026-06-03
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Step 0: Previous Verification

No prior VERIFICATION.md found. Initial mode.

---

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | Requesting a reset writes a CSPRNG token to the application log AND a 0600 `<config_dir>/reset-token.txt`, and the token value never appears in any HTTP response | VERIFIED | `logger.warning("...{token}", token=token)` at routes.py:1689 is the single mint log. `_write_reset_token_file` uses `os.fchmod(fd, 0o600)` before `os.replace` (M1). All three `TemplateResponse` context dicts in `reset_request_post` contain only `"step"` and `"message"` — never `"token"`. `test_token_not_in_response` and `test_token_in_mint_log` both pass. |
| SC-2 | Submitting a valid, unexpired token plus matching new password sets new bcrypt hash, rotates `session_secret`, deletes token file, auto-logs-in with fresh cookie on dashboard | VERIFIED | `reset_confirm_post` (routes.py:1718-1869) executes hash→rotate→model_copy→atomic_write→chmod→load_settings (D-10 order). H2 read-back asserts `reloaded_secret == new_session_secret` (line 1829) before cookie signing. Single-use clear: `app.state.reset_token = None` + `unlink(missing_ok=True)`. `RedirectResponse(status_code=303)` to dashboard with `triggarr_session` cookie. 12 confirm-path tests pass. |
| SC-3 | A token is rejected (generic "invalid or expired" error, no state change) when wrong, expired, already used, or superseded | VERIFIED | Token validation at lines 1782-1792 checks: `stored is None OR time.monotonic() >= stored[1] OR NOT secrets.compare_digest(token, stored[0])` — all produce identical generic `"Invalid or expired reset token"` (D-06). State unchanged on all failure paths. `test_expired_token_rejected`, `test_wrong_token_generic_error`, `test_token_single_use` pass. |
| SC-4a | `/reset/request` and `/reset/confirm` reachable logged-out; no other authenticated route exposed | VERIFIED | Middleware (middleware.py:118) uses `path == "/reset" or path.startswith("/reset/")` — exact-or-prefix. `/resetXYZ` NOT exempt (stays gated). `EXEMPT_PREFIXES` tuple does not include `"/reset"`. `test_no_other_route_exposed` and `test_reset_routes_unauthenticated` pass. |
| SC-4b | Both endpoints throttle rapid repeat calls | VERIFIED | `RESET_REQUEST_RATE_LIMIT_SECONDS = 60` (routes.py:146) with optimistic + in-lock double-check. `RESET_CONFIRM_RATE_LIMIT_SECONDS = 5` (routes.py:147) with single-acquisition M3 pattern (field validation inside lock so stamp fires on all paths). `test_request_rate_limited` and `test_confirm_rate_limited` pass (429). |

### Additional Must-Have Truths (from Plan frontmatter)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| M-1 | `generate_reset_token()` returns URL-safe CSPRNG ~43 chars | VERIFIED | `auth.py:70-76`: `secrets.token_urlsafe(32)`. Runtime spot-check: 5 calls return 43-char distinct strings. |
| M-2 | H1 live-token no-op: second `/reset/request` while unexpired token exists does NOT mint | VERIFIED | `reset_request_post` lines 1662-1676: checks `stored is not None and time.monotonic() < stored[1]` before minting; returns neutral confirmation unchanged. `test_live_token_request_is_noop` passes. |

**Score:** 7/7 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `triggarr/auth.py` | `generate_reset_token() -> str` CSPRNG helper | VERIFIED | Lines 70-76, `secrets.token_urlsafe(32)`, ~43 chars |
| `triggarr/web/middleware.py` | `/reset` exemption with exact-or-/reset/ predicate (M2) | VERIFIED | Line 118: `path == "/reset" or path.startswith("/reset/")`. `/reset` NOT in `EXEMPT_PREFIXES` tuple (line 25). |
| `triggarr/web/routes.py` | `RESET_REQUEST_RATE_LIMIT_SECONDS`, `RESET_CONFIRM_RATE_LIMIT_SECONDS` constants | VERIFIED | Lines 146-147: 60s and 5s |
| `triggarr/web/routes.py` | `_write_reset_token_file`, `reset_request_page`, `reset_request_post`, `reset_confirm_post` | VERIFIED | Lines 1557, 1617, 1627, 1717 |
| `triggarr/search/scheduler.py` | `app.state.reset_token = None` and `app.state.last_reset_time = {}` in `create_lifespan` | VERIFIED | Lines 504, 507 — after `last_search_time` and before `last_health_check` |
| `triggarr/templates/reset.html` | Step conditional form shell with correct field names and D-20 error/errors context keys | VERIFIED | 64 lines, extends `base-auth.html`. Fields: `token`, `new_password`, `confirm_password`. Renders `{{ error }}` and `{{ errors["new_password"] }}` / `{{ errors["confirm_password"] }}`. No `{{ token }}` Jinja echo. |
| `tests/test_reset.py` | 22 tests matching VALIDATION.md exactly, `_make_reset_app` helper | VERIFIED | 22 `def test_*` functions confirmed; all names match VALIDATION.md spec; `_make_reset_app` at line 83 sets both `app.state.reset_token` and `app.state.last_reset_time` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `reset_request_post` | `app.state.reset_token` | `(token, monotonic+900)` write inside `search_lock` | VERIFIED | Line 1680: `request.app.state.reset_token = (token, time.monotonic() + 900)` |
| `reset_request_post` | `reset-token.txt` (0600) | `_write_reset_token_file` via `run_in_executor` | VERIFIED | Lines 1697-1700; helper uses `os.fchmod(fd, 0o600)` before `os.replace` (M1) |
| `reset_request_post` | `app.state.last_reset_time["request"]` | Monotonic rate-limit gate (optimistic + in-lock) | VERIFIED | Lines 1644-1656 |
| `reset_confirm_post` | `secrets.compare_digest` | Constant-time token comparison INSIDE `search_lock` | VERIFIED | Line 1786 — inside the single `async with search_lock` block (line 1751) |
| `reset_confirm_post` | `_atomic_toml_write` | `run_in_executor` persist of rotated auth | VERIFIED | Lines 1818-1820 |
| `reset_confirm_post` | `sign_session` | Auto-login cookie signed with captured `new_session_secret` (proven == reloaded secret via H2 assert) | VERIFIED | Line 1862: `sign_session(refreshed_username, new_session_secret)`. H2 assertion at line 1829. |
| `reset_confirm_post` | Single lock acquisition (M3) | One `async with search_lock` for rate-recheck + field validation + token validation + apply | VERIFIED | Lines 1751-1847 contain one acquisition; grep over that range confirms exactly one `async with` |
| `AuthMiddleware.dispatch` | `/reset` exemption (M2) | `path == "/reset" or path.startswith("/reset/")` | VERIFIED | Line 118; `/reset` NOT in `EXEMPT_PREFIXES` |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `reset_request_post` | `token` | `generate_reset_token()` → `secrets.token_urlsafe(32)` | Yes — CSPRNG 32-byte random | FLOWING |
| `reset_confirm_post` | `new_hash` | `hash_password(new_password)` → bcrypt 12-round | Yes — real bcrypt hash | FLOWING |
| `reset_confirm_post` | `new_session_secret` | `generate_session_secret()` → `secrets.token_hex(32)` | Yes — CSPRNG 64-char hex | FLOWING |
| `reset_confirm_post` | persisted TOML | `_atomic_toml_write` + `load_settings` | Yes — real filesystem write + read | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `generate_reset_token()` returns 43-char CSPRNG strings | `uv run python -c "from triggarr.auth import generate_reset_token; ..."` | 5 calls: lengths all 43, all distinct | PASS |
| Full test suite (1006 tests) passes | `uv run pytest tests/ -q` | `1006 passed, 32 warnings in 47.55s` | PASS |
| ruff clean across all modified files | `uv run ruff check triggarr/ tests/` | `All checks passed!` | PASS |
| 22 reset tests collected | `grep -c "^def test_" tests/test_reset.py` | 22 | PASS |

---

### Probe Execution

No probe scripts declared in PLAN or SUMMARY. No `scripts/*/tests/probe-*.sh` found. Step 7c: SKIPPED (no probe scripts for this phase).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RCOV-02 | 72-01, 72-02 | CSPRNG token written to log AND 0600 file; never in HTTP response | SATISFIED | `logger.warning("...{token}", token=token)` in `reset_request_post`; `_write_reset_token_file` with `os.fchmod(fd, 0o600)`; no `"token"` key in any TemplateResponse context; `test_request_mints_token`, `test_token_file_written_0600`, `test_token_not_in_response`, `test_token_in_mint_log` all pass |
| RCOV-03 | 72-01, 72-02, 72-03 | In-memory token, 15-min TTL, single-use, invalidation by newer mint; H1 live-token no-op | SATISFIED | `app.state.reset_token = (token, monotonic+900)` (900s = 15 min); `app.state.reset_token = None` on success (single-use); H1 guard prevents supersession of live token; `test_token_ttl_stored_correctly`, `test_expired_token_rejected`, `test_new_mint_supersedes_prior`, `test_token_single_use`, `test_live_token_request_is_noop` all pass |
| RCOV-04 | 72-03 | New bcrypt hash, `session_secret` rotation, auto-login with fresh cookie | SATISFIED | Full apply block in `reset_confirm_post`; H2 read-back assertion; `test_confirm_success_redirects_with_cookie`, `test_confirm_rotates_session_secret`, `test_pre_reset_cookie_invalid_after_reset`, `test_new_cookie_validates_after_reset`, `test_wrong_token_generic_error`, all field-error tests pass |
| RCOV-05 | 72-01, 72-02, 72-03 | Rate-limiting on both endpoints | SATISFIED | 60s window on request (optimistic + in-lock); 5s window on confirm (single-lock M3, stamp fires before field/token error returns); `test_request_rate_limited`, `test_confirm_rate_limited` both pass (429) |
| RCOV-06 | 72-01, 72-02, 72-03 | `/reset` routes exempt from auth middleware; token file deleted on success | SATISFIED | Exact-or-/reset/ predicate in `AuthMiddleware.dispatch` (M2); `unlink(missing_ok=True)` on success path; `test_reset_routes_unauthenticated`, `test_no_other_route_exposed`, `test_token_file_deleted_on_success` all pass |

**Note on RCOV-01:** RCOV-01 ("Forgot password?" link on login page) is explicitly mapped to Phase 73 in REQUIREMENTS.md and ROADMAP.md. It is not in Phase 72's scope and is not missing.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | — |

No `TBD`, `FIXME`, or `XXX` markers found in modified files. No stub patterns (empty returns, `console.log`-only handlers, hardcoded empty data in render paths). The single `assert` statement in `reset_confirm_post` (H2 read-back at line 1829) is an intentional correctness invariant guard, not a test stub. The `reset.html` action paths are hardcoded (not `url_for`) — this is a documented intentional choice for Phase 72 (named routes available from Plans 02/03; Phase 73 will own the styled version with `url_for`). The SUMMARY notes this explicitly. Not a blocker.

---

### Human Verification Required

The two operator-facing read channels from VALIDATION.md require a real deployed container and are explicitly documented as manual-only in the validation strategy:

1. **Operator reads token from `docker logs`**
   - **Test:** In a deployed container, trigger `POST /reset/request`, then run `docker logs <container>` and search for the warning log line containing the reset token.
   - **Expected:** The token value appears exactly once in the warning log output.
   - **Why human:** Requires a real Docker container with log streaming; the in-process loguru test (`test_token_in_mint_log`) proves the code path — the container integration is environment-level.

2. **Operator reads token from mounted config volume**
   - **Test:** After triggering a reset request in a deployed container, `cat /config/reset-token.txt` inside the container or from the host volume mount.
   - **Expected:** The token file exists with mode 0600 and contains the token value.
   - **Why human:** Requires a real volume mount; the in-process test (`test_token_file_written_0600`) proves the file write — the volume integration is environment-level.

These are documented as walkthrough-verified items in the validation strategy (VALIDATION.md "Manual-Only Verifications"). They do not block automated verification passing.

---

## Gaps Summary

No gaps found. All must-haves verified against the codebase.

---

## Phase Goal Assessment

**Goal Half 1 — Operator recovery path:** The full HTTP-only reset flow is implemented and exercised. `GET /reset/request` renders the form unauthenticated. `POST /reset/request` mints a CSPRNG token (`secrets.token_urlsafe(32)`, ~43 chars), stores it as `(token, monotonic+900)` in `app.state.reset_token`, logs it once at `WARNING` level (the deliberate operator recovery channel), and writes it atomically to a `0600` `reset-token.txt` in the config dir. `POST /reset/confirm` validates the token inside `search_lock` via `secrets.compare_digest`, rehashes the password with bcrypt, rotates `session_secret`, persists atomically, reloads settings, refreshes the redacting sink, clears the in-memory token, deletes the token file, and 303-redirects to the dashboard with a fresh cookie signed by the new secret. The operator never edits `triggarr.toml`.

**Goal Half 2 — Remote attacker gains nothing:** Token never in any HTTP response body, headers, or template context (only in warning log + 0600 file requiring host access). Both endpoints rate-limited (60s request, 5s confirm) with optimistic + in-lock double-check. The `/reset` exemption uses the exact-or-/reset/ predicate — `/resetXYZ` stays behind the auth gate. All error paths return identical generic messages (no enumeration). `secrets.compare_digest` is used for constant-time comparison inside the lock. H1 live-token no-op prevents supersession-DoS: a remote attacker hitting `/reset/request` every 60s cannot perpetually invalidate a legitimate operator's in-progress token.

---

_Verified: 2026-06-03T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
