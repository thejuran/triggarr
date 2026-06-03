# Phase 72: Password Reset Backend & Token Lifecycle - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Backend for filesystem-token password recovery. Deliver three routes — `reset_request_page` (GET form shell), `reset_request_post` (POST mint), `reset_confirm_post` (POST apply) — plus the `/reset` middleware exemption and the `generate_reset_token()` auth helper. A locked-out operator with host access mints a CSPRNG token (written to the application log + a `0600` file in the config volume, **never** in any HTTP response), then submits it with a new password to set a new bcrypt hash, rotate `session_secret`, and auto-login. A remote attacker hitting the same endpoints gains nothing.

**In scope:** token mint/store/validate (in-memory, 15-min TTL, single-use, restart-invalidated), the confirm/apply path mirroring `change_password`, rate-limiting both endpoints, `/reset` exempt from auth middleware, and the backend tests (token lifecycle, session rotation, rate-limit, redaction, middleware reachability).

**Out of scope (Phase 73):** the "Forgot password?" link on `login.html` and the styled request/confirm reset *pages*. Phase 72 may render a minimal/functional form shell sufficient to exercise the backend and tests; the polished UI styling that matches `login.html`/`setup.html` is Phase 73's deliverable. No count-only refresh (Track B / Phase 74), no drain-timeout knob (Track C / Phase 75).
</domain>

<decisions>
## Implementation Decisions

### Trust model & token transport (LOCKED by spec §2.2, §2.4)
- **D-01:** Recovery proves host/filesystem access, not identity (single-user, no email). Possession of the token *is* authorization.
- **D-02:** Token value appears exactly once, at mint, in two operator-only sinks: the Loguru log at `warning` level (`docker logs`-visible) AND `<config_dir>/reset-token.txt`. It is **never** returned in any HTTP response body, never re-logged at confirm time. The request endpoint returns only a neutral confirmation telling the operator where to read it.
- **D-03:** Adds zero new network attack surface — a remote attacker who can hit the endpoints still cannot read the token, and both endpoints are rate-limited.

### Token lifecycle (LOCKED by spec §2.3, §2.5)
- **D-04:** In-memory only: `app.state.reset_token = (token, expiry_monotonic)`. No persistence in TOML, no hashed-token-on-boot path. Initialize this app.state attribute at startup (alongside the other `app.state` fields) so the routes can read it unconditionally.
- **D-05:** Mint = `secrets.token_urlsafe(32)`, expiry = `time.monotonic() + 900` (15-min TTL). A new mint **overwrites** (supersedes/invalidates) any prior token.
- **D-06:** Validation: present AND not expired (`time.monotonic() < expiry`) AND `secrets.compare_digest(submitted, stored)` (constant-time). Any failure → generic "Invalid or expired reset token", **no state change**, no detail leak (don't distinguish wrong-vs-expired-vs-superseded to the client).
- **D-07:** Single-use: on a successful confirm, clear `app.state.reset_token` and delete the token file. A container restart invalidating a pending token is acceptable (user re-clicks "Forgot password?").

### Confirm/apply path — mirror `change_password` (LOCKED by spec §2.3; pattern at routes.py:1401)
- **D-08:** Run the apply under `request.app.state.search_lock` (same as `change_password`). Validate the token **inside the lock** (TOCTOU guard, matching `change_password`'s in-lock current-password verify).
- **D-09:** Password validation: non-empty, `new_password == confirm_password`, and the bcrypt 72-byte limit caught via `hash_password`'s `ValueError` (reuse the existing try/except → field-error pattern from `change_password`).
- **D-10:** On success, in this order under the lock: `new_hash = hash_password(new_password)` → `new_session_secret = generate_session_secret()` → build `new_auth` via `auth.model_copy(update={password_hash: SecretStr(new_hash), session_secret: SecretStr(new_session_secret)})` → `updated = settings.model_copy(update={auth: new_auth})` → `_atomic_toml_write` via `run_in_executor` with `_settings_to_dict(updated)` → `os.chmod(config_path, 0o600)` → `request.app.state.settings = load_settings(config_path)`.
- **D-11:** After the lock (mirroring `change_password`): `_sync_auth_state(settings)` → `collect_secrets(settings)` → `setup_logging(general.log_level, new_secrets)` so the rotated `session_secret` and (unchanged-key) `password_hash` stay fed to the redacting sink.
- **D-12:** Session rotation invalidates all cookies signed with the old secret (a pre-reset cookie fails `validate_session` after reset) — same rationale and effect as `change_password` / the v2.8.1 fix.

### Auto-login & redirect (Claude's Discretion — resolved per login_post/change_password)
- **D-13:** On success, set a fresh `triggarr_session` cookie signed with the **new** secret (`sign_session(username, new_session_secret)`), attributes mirroring `login_post` exactly: `max_age=COOKIE_MAX_AGE`, `httponly=True`, `samesite="lax"`, `secure=is_secure_request(request)`. Then `RedirectResponse(url=url_for("dashboard"), status_code=303)`. The user lands logged in on the dashboard — no second login step.

### Rate-limiting (spec §2.4 names the pattern; scope is Claude's Discretion — resolved)
- **D-14:** Reuse the `search_now` monotonic-timestamp pattern (routes.py:891-908), **not** login's per-IP `_check_rate_limit`. Rationale: the reset limit guards log/file flooding (request) and token-guessing throughput (confirm) — a global monotonic gate matches the spec's explicitly-named pattern; login's per-IP limiter is for distributed credential brute-force, a different threat. Use a new `app.state.last_reset_time` dict (initialized at startup) keyed per-endpoint (e.g. `"request"` / `"confirm"`).
- **D-15:** Windows: `/reset/request` ~60s (new constant, e.g. `RESET_REQUEST_RATE_LIMIT_SECONDS = 60`); `/reset/confirm` a few attempts/min (e.g. `RESET_CONFIRM_RATE_LIMIT_SECONDS = 5`). Throttled response: HTTP `429` with a short body, consistent with `search_now`'s `429` ("Rate limited — try again shortly"). On `/reset/confirm`, do the optimistic check before the lock AND re-check inside (matching `search_now`'s double-check), since confirm holds `search_lock`.

### Token-file write & edge cases (spec §2.4; edge behavior is Claude's Discretion — resolved)
- **D-16:** Write `reset-token.txt` to `request.app.state.config_path.parent` (the config dir — `config_path.parent` is the established config-dir reference, e.g. config.py:237). Use the atomic temp-then-rename pattern of `_atomic_toml_write` (`tempfile.mkstemp(dir=...)` → write → `flush`/`fsync` → `os.replace` → dir fsync), then `os.chmod(path, 0o600)`. Each new mint **replaces** the prior file.
- **D-17:** Partial-mint ordering: write the **log line first**, then the file. If the file write fails (`OSError`), the operator can still recover the token from the log; log the file-write failure at `error` (sanitized, no token in the error) and still return the neutral confirmation. The in-memory token is the authority regardless of file state.
- **D-18:** Stale file at startup (left by a prior container) is **harmless and ignored** — validation keys off the in-memory token, which a restart clears, so a file with no live in-memory counterpart authorizes nothing. No startup cleanup obligation beyond best-effort; do not add a boot-time scan.
- **D-19:** Token-file deletion failure on a successful reset → **warn, don't block**. The reset already succeeded (hash written, secret rotated, in-memory token cleared); a leftover file holds an already-consumed token that no longer validates. Log the deletion failure at `warning` (sanitized) and proceed to auto-login/redirect.

### Confirm-failure response shape (backend feeds Phase 73; Claude's Discretion — resolved)
- **D-20:** Failures render an HTML reset page (server-rendered, htmx-friendly — consistent with `change_password` returning `security_password.html` with an `errors` dict), **not** JSON. Token failures → generic error string in the page context (D-06). Password-field failures (mismatch / empty / >72 bytes) → inline field-level errors keyed by field name, mirroring `change_password`'s `errors: dict[str,str]` contract so Phase 73 can reuse the same context shape. Status codes: `429` for rate-limited (D-15); token/validation failures re-render the form (Phase 73 will own exact status/markup — Phase 72 establishes the context keys: generic `error` for token, per-field `errors` for password).

### Middleware exemption (LOCKED by spec §2.4, §2.6; middleware.py:22)
- **D-21:** Add `/reset` to `EXEMPT_PREFIXES` in `triggarr/web/middleware.py` (currently `("/health", "/static", "/login", "/setup")`). A locked-out user cannot authenticate, so `/reset/*` must be reachable unauthenticated — exactly like `/login` and `/setup`. Verify in tests that the exemption does NOT expose any other authenticated route (prefix-match scope is `/reset` only).

### Component boundaries (LOCKED by spec §2.6)
- **D-22:** `triggarr/auth.py` — add only `generate_reset_token() -> str` (thin `secrets.token_urlsafe(32)` wrapper, for symmetry with `generate_api_key`/`generate_session_secret`). Token **storage/validation stays in the route layer** (request/app-state-scoped), not in `auth.py`.
- **D-23:** `triggarr/web/routes.py` — the three route handlers, reusing `_atomic_toml_write`, `_settings_to_dict`, `hash_password`, `generate_session_secret`, `sign_session`, `_sync_auth_state`, `collect_secrets`, `setup_logging`, `is_secure_request`, `COOKIE_MAX_AGE`.

### Claude's Discretion (planner/executor latitude)
- Exact new rate-limit constant names/values within the spec's stated windows (D-15).
- Internal helper factoring for token mint + file write (e.g. a private `_write_reset_token_file`).
- Minimal form-shell template markup for Phase 72 (Phase 73 replaces with the styled pages).
- Test file organization (extend the existing auth test suite vs a new `test_reset.py`) — follow the established suite layout.
</decisions>

<specifics>
## Specific Ideas

- The reset-confirm session rotation **deliberately mirrors** the v2.8.1 `change_password` rotation (STATE.md cross-cutting thread; PROJECT.md v2.8.1 record). Same pattern: rotate `session_secret`, re-issue the acting user's cookie under the new secret. Reset differs only in that there is no current-password verify (the token is the proof) and it auto-logs-in a previously-logged-out user.
- Neutral request-confirmation copy (spec §2.3): "If recovery is available, a reset token has been written to the application logs and the config volume. Check `docker logs` or `<config_dir>/reset-token.txt`." — wording final in Phase 73, but the *contract* (neutral, no token, points at log + file) is locked here.
- Token compared with `secrets.compare_digest`; username compares already use `secrets.compare_digest` in `login_post` (routes.py:1345) — same constant-time discipline.
</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design spec (source of truth for this milestone/track)
- `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md` §2 — Track A full design: trust model (§2.2), flow (§2.3), security discipline (§2.4), why-in-memory (§2.5), components & boundaries (§2.6), tests (§2.7). §7 confirms all design decisions resolved.

### Codebase patterns to mirror (read before planning)
- `triggarr/web/routes.py` §`change_password` (routes.py:1401-~1490) — THE pattern for reset-confirm: in-lock validation, `hash_password` ValueError catch, `session_secret` rotation via `model_copy`, atomic write + `os.chmod 0o600` + `load_settings`, `_sync_auth_state` + `collect_secrets` + `setup_logging` refresh, cookie re-issue mirroring `login_post`.
- `triggarr/web/routes.py` §`search_now` (routes.py:876-967) — THE rate-limit pattern: optimistic `last_search_time` monotonic check before lock, re-check inside lock, `429` on throttle; the `_build_app_context` → partial response shape (reference only; reset returns a page/redirect, not a card).
- `triggarr/web/routes.py` §`login_post` (routes.py:1311-1375) — cookie attributes for auto-login (`COOKIE_MAX_AGE`, `httponly`, `samesite=lax`, `secure=is_secure_request`), `sign_session`, 303 redirect.
- `triggarr/web/middleware.py:22` — `EXEMPT_PREFIXES`; add `/reset`.
- `triggarr/config.py:95` §`_atomic_toml_write` — temp-then-rename + fsync pattern to mirror for the `0600` token-file write; `config_path.parent` is the config dir (config.py:237).
- `triggarr/auth.py` — `generate_api_key`/`generate_session_secret`/`hash_password`/`sign_session`/`validate_session` (auth.py:13-88); add `generate_reset_token()` for symmetry.

### Project state
- `.planning/STATE.md` — v2.10 milestone shape, cross-cutting thread (Track A adds zero new network attack surface; SecretStr discipline maintained).
- `.planning/codebase/CONVENTIONS.md`, `ARCHITECTURE.md`, `TESTING.md` — repo conventions (SecretStr, Loguru redacting sink, atomic writes, pytest-asyncio `asyncio_mode=auto`).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `change_password` (routes.py:1401) — near-complete template for reset-confirm; copy its lock/rotate/persist/refresh/cookie structure, drop the current-password verify, add token validation + auto-login + token-file delete.
- `search_now` (routes.py:876) — `last_search_time` optimistic-then-locked rate-limit; `SEARCH_RATE_LIMIT_SECONDS` constant (routes.py:143) as the sibling for new reset constants.
- `_atomic_toml_write` (config.py:95) — exact temp-then-rename + fsync + `os.replace` recipe for the token-file write.
- `auth.py` generate_* helpers + `hash_password`/`sign_session`/`validate_session` — reuse wholesale; add `generate_reset_token`.
- `_sync_auth_state` (routes.py:100), `collect_secrets`, `setup_logging`, `_settings_to_dict` (routes.py:211) — the post-mutation refresh chain.
- `is_secure_request`, `COOKIE_MAX_AGE`, `_safe_next_url` — cookie/redirect helpers.

### Established Patterns
- All API keys / `password_hash` / `session_secret` are `SecretStr`; `.get_secret_value()` only at use sites; `collect_secrets` feeds the Loguru redacting sink — refresh after rotation (D-11).
- Atomic file writes (temp-then-rename) for any sensitive file; `0o600` perms on config (and now the token file).
- Mutations that touch auth/config acquire `app.state.search_lock` to avoid races with in-flight search jobs (routes.py:607, 798, 1425).
- Rate limits use `time.monotonic()` (not wall clock) keyed dicts on `app.state`.
- Loguru only (no print/logging); `_sanitize_exc` for httpx/pydantic exceptions that may carry `?apikey=`.

### Integration Points
- `app.state` needs two new fields initialized at startup: `reset_token` (None initially) and `last_reset_time` (empty dict) — find where `last_search_time`/`search_lock` are initialized (app/lifespan setup) and add alongside.
- `EXEMPT_PREFIXES` (middleware.py:22) — single-line addition of `/reset`.
- Router registration in `routes.py` — new `@router.get("/reset...")` and `@router.post("/reset/...")` handlers register with the existing router; confirm they land under the `/reset` exempt prefix.
- `config_path` is on `app.state.config_path` (set in `__main__.py` lifespan via `get_config_path()`); token file = `app.state.config_path.parent / "reset-token.txt"`.
</code_context>

<deferred>
## Deferred Ideas

- "Forgot password?" link on `login.html` (visible only when `not needs_setup`) and the styled request/confirm reset **pages** matching `login.html`/`setup.html` — **Phase 73** (RCOV-01).
- Count-only refresh (Track B) — Phase 74. Drain-timeout settings knob + deferred-record correction (Track C) — Phase 75.
- None of the discussion surfaced scope creep — all decisions stayed within the Track A backend boundary.
</deferred>

---

*Phase: 72-password-reset-backend-token-lifecycle*
*Context gathered: 2026-06-03*
