# Phase 72: Password Reset Backend & Token Lifecycle — Research

**Researched:** 2026-06-03
**Domain:** FastAPI auth route implementation — token lifecycle, session rotation, atomic file writes, middleware exemption, monotonic rate-limiting
**Confidence:** HIGH (all findings drawn directly from live codebase; no external library research required — this phase adds new routes that mirror verified existing patterns)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Trust model & token transport (D-01, D-02, D-03)**
- D-01: Recovery proves host/filesystem access (possession of the token is authorization).
- D-02: Token appears exactly once — in the Loguru log at `warning` level AND `<config_dir>/reset-token.txt`. Never in any HTTP response body.
- D-03: Adds zero new network attack surface; both endpoints are rate-limited.

**Token lifecycle (D-04, D-05, D-06, D-07)**
- D-04: In-memory only: `app.state.reset_token = (token, expiry_monotonic)`. Initialize at startup alongside `last_search_time`.
- D-05: Mint = `secrets.token_urlsafe(32)`, expiry = `time.monotonic() + 900`. New mint overwrites any prior.
- D-06: Validation: present AND `time.monotonic() < expiry` AND `secrets.compare_digest(submitted, stored)`. Any failure → generic "Invalid or expired reset token", no state change, no detail.
- D-07: Single-use: on successful confirm, clear `app.state.reset_token` and delete token file.

**Confirm/apply path — mirror `change_password` (D-08, D-09, D-10, D-11, D-12)**
- D-08: Run apply under `request.app.state.search_lock`; validate token inside the lock (TOCTOU guard).
- D-09: Password validation: non-empty, `new_password == confirm_password`, bcrypt 72-byte limit via `hash_password`'s `ValueError`.
- D-10: Under the lock in order: `new_hash = hash_password(new_password)` → `new_session_secret = generate_session_secret()` → `new_auth = auth.model_copy(update={password_hash: SecretStr(new_hash), session_secret: SecretStr(new_session_secret)})` → `updated = settings.model_copy(update={auth: new_auth})` → `_atomic_toml_write` via `run_in_executor` → `os.chmod(config_path, 0o600)` → `request.app.state.settings = load_settings(config_path)`.
- D-11: After the lock: `_sync_auth_state(settings)` → `collect_secrets(settings)` → `setup_logging(general.log_level, new_secrets)`.
- D-12: Session rotation invalidates all cookies signed with the old secret.

**Auto-login & redirect (D-13)**
- D-13: Set fresh `triggarr_session` cookie signed with the NEW secret (`sign_session(username, new_session_secret)`), attributes: `max_age=COOKIE_MAX_AGE`, `httponly=True`, `samesite="lax"`, `secure=is_secure_request(request)`. Then `RedirectResponse(url=url_for("dashboard"), status_code=303)`.

**Rate-limiting (D-14, D-15)**
- D-14: Reuse `search_now` monotonic-timestamp pattern; new `app.state.last_reset_time` dict keyed per-endpoint.
- D-15: `/reset/request` ~60s window; `/reset/confirm` ~5s window. Optimistic check BEFORE lock, re-check inside lock (same as `search_now`). HTTP 429 response body: "Rate limited — try again shortly".

**Token-file write & edge cases (D-16, D-17, D-18, D-19)**
- D-16: Write `reset-token.txt` to `request.app.state.config_path.parent`; atomic temp-then-rename; `os.chmod(path, 0o600)`. Each mint replaces prior file.
- D-17: Log line FIRST, then file write. If file write fails (OSError), operator recovers from log; log failure at `error` (sanitized, no token); still return neutral confirmation. In-memory token is the authority.
- D-18: Stale file at startup is harmless — in-memory token cleared on restart. No startup cleanup.
- D-19: Token-file deletion failure on successful reset → warn, don't block. Log at `warning` (sanitized) and proceed to auto-login.

**Confirm-failure response shape (D-20)**
- D-20: Failures render HTML (server-rendered, htmx-friendly). Token failures → generic `error` string. Password-field failures → per-field `errors` dict. Status 429 for rate-limited; token/password failures re-render the form.

**Middleware exemption (D-21)**
- D-21: Add `/reset` to `EXEMPT_PREFIXES` in `triggarr/web/middleware.py`.

**Component boundaries (D-22, D-23)**
- D-22: `triggarr/auth.py` — add only `generate_reset_token() -> str` (thin `secrets.token_urlsafe(32)` wrapper).
- D-23: `triggarr/web/routes.py` — three handlers: `reset_request_page` (GET), `reset_request_post` (POST mint), `reset_confirm_post` (POST apply).

### Claude's Discretion

- Exact rate-limit constant names/values within spec's stated windows (D-15).
- Internal helper factoring for token mint + file write (e.g. a private `_write_reset_token_file`).
- Minimal form-shell template markup for Phase 72 (Phase 73 replaces with styled pages).
- Test file organization (extend existing auth test suite vs a new `test_reset.py`).

### Deferred Ideas (OUT OF SCOPE)

- "Forgot password?" link on `login.html` and styled request/confirm reset pages matching `login.html`/`setup.html` — Phase 73 (RCOV-01).
- Count-only refresh (Track B) — Phase 74.
- Drain-timeout settings knob + deferred-record correction (Track C) — Phase 75.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RCOV-02 | User can request a reset, which mints a CSPRNG token written to the application log AND a `0600` file in the config volume — and the token value never appears in any HTTP response. | `reset_request_post` handler: `generate_reset_token()` → log at `warning` → atomic write `reset-token.txt` → neutral HTML response. Token in D-02 and D-16/D-17 pattern. |
| RCOV-03 | A reset token is held in memory only, expires 15 minutes after minting, is single-use, and is invalidated when a newer token is minted. | `app.state.reset_token = (token, time.monotonic() + 900)`; new mint overwrites (D-04, D-05); confirmed → cleared (D-07). |
| RCOV-04 | User can submit the token plus a new password to set a new bcrypt hash, which rotates `session_secret` (invalidating other sessions) and auto-logs-in the user with a fresh cookie. | `reset_confirm_post` mirrors `change_password` (D-08 through D-13): in-lock validate, hash, rotate, persist, reload, refresh, auto-login 303. |
| RCOV-05 | Both reset endpoints (request and confirm) are rate-limited to resist log/file flooding and token-submission abuse. | `app.state.last_reset_time` dict; optimistic+locked monotonic-timestamp pattern from `search_now` (D-14, D-15). |
| RCOV-06 | The `/reset` routes are reachable without authentication (added to middleware `EXEMPT_PREFIXES`), and the token file is deleted on a successful reset. | `EXEMPT_PREFIXES` += `/reset` (D-21); successful confirm deletes `reset-token.txt` before auto-login (D-07, D-10). |
</phase_requirements>

---

## Summary

Phase 72 adds a filesystem-token password recovery flow to Triggarr. The entire implementation is a structured composition of existing codebase patterns — no new architectural concepts are introduced. The three routes (`reset_request_page`, `reset_request_post`, `reset_confirm_post`) mirror `change_password` (for the apply path) and `search_now` (for rate-limiting). The `generate_reset_token()` helper in `auth.py` follows the `generate_session_secret()` / `generate_api_key()` symmetry already present.

The key security invariant is that the token value never appears in any HTTP response. It is logged once (Loguru `warning`, operator-readable via `docker logs`) and written once to a `0600` file in the config volume. The in-memory `(token, expiry_monotonic)` tuple is the authority; the file is a convenience copy for operators who cannot tail logs. A container restart clears in-memory state, rendering any stale file harmless.

The confirm path is the highest-complexity piece: it holds `search_lock`, validates the token inside the lock (TOCTOU guard), performs hash + secret rotation under the lock via the existing `change_password` pattern, calls `_atomic_toml_write` via `run_in_executor`, then performs the post-lock refresh chain (`_sync_auth_state` → `collect_secrets` → `setup_logging`). The new session cookie is signed with the NEW `session_secret` read back from `load_settings` — not the in-memory pre-reload value — ensuring the redirect cookie validates under the rotated secret.

**Primary recommendation:** Write `test_reset.py` first (TDD), one test class per invariant category, using the `_make_route_app` + `TestClient` pattern from `test_auth_routes.py`. Drive implementation to make them pass. No new dependencies required.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Token mint + log + file write | API / Backend (`routes.py`) | `auth.py` (thin helper only) | Token storage is request/app-state-scoped; `auth.py` provides only the CSPRNG call |
| Token validation (constant-time, TTL) | API / Backend (route layer, inside `search_lock`) | — | Must be in-lock to prevent TOCTOU; no separate service layer needed |
| Password rehash + secret rotation | API / Backend (`routes.py` calling `auth.py` helpers) | Config layer (`_atomic_toml_write`) | Mirrors `change_password` exactly; business logic and persistence in same route function |
| Session cookie re-issue | API / Backend (`routes.py`) | `auth.py` (`sign_session`) | Cookie attributes controlled at route layer; `sign_session` is the crypto primitive |
| Rate-limiting (both endpoints) | API / Backend (`routes.py` + `app.state`) | — | Monotonic-timestamp dict on `app.state`; same pattern as `last_search_time` |
| Middleware exemption | Frontend Server (middleware.py) | — | Auth gate is in `AuthMiddleware`; exemption list lives there |
| Atomic token-file write | Config / Storage layer (`config.py` pattern) | — | Mirrors `_atomic_toml_write`; same fsync + rename discipline |

---

## Standard Stack

No new packages. All implementation uses the project's existing installed dependencies.

| Asset | Already Present | Purpose in This Phase |
|-------|----------------|----------------------|
| `secrets` (stdlib) | Yes | `token_urlsafe(32)` for token mint; `compare_digest` for constant-time comparison |
| `time` (stdlib) | Yes | `time.monotonic()` for TTL and rate-limit timestamps |
| `os` (stdlib) | Yes | `os.chmod(path, 0o600)`, `os.replace`, `os.fsync` |
| `tempfile` (stdlib) | Yes | `tempfile.mkstemp` for atomic file write |
| `asyncio` (stdlib) | Yes | `run_in_executor` for `_atomic_toml_write` and token-file write |
| `itsdangerous` | Yes | Via `sign_session` / `validate_session` in `auth.py` |
| `bcrypt` | Yes | Via `hash_password` in `auth.py` |
| `loguru` | Yes | Token log line at `warning`; error/warning for file-write failures |
| FastAPI / Starlette | Yes | `Request`, `RedirectResponse`, `HTMLResponse`, `router`, `TestClient` |
| `pydantic` `SecretStr` | Yes | Wrap `new_hash` and `new_session_secret` in `SecretStr` for `model_copy` |

**Installation:** None required. `[VERIFIED: live codebase]`

---

## Package Legitimacy Audit

No new packages are installed in this phase. This section is not applicable.

---

## Architecture Patterns

### System Architecture Diagram

```
Operator (host access)
    │
    ▼
POST /reset/request  (exempt from AuthMiddleware via EXEMPT_PREFIXES)
    │
    ├─ optimistic rate check (last_reset_time["request"], monotonic)
    │   └─ 429 if within 60s window
    │
    ├─ generate_reset_token()  →  token = secrets.token_urlsafe(32)
    ├─ store: app.state.reset_token = (token, time.monotonic() + 900)
    ├─ logger.warning(token)         ← operator reads via docker logs
    ├─ atomic write reset-token.txt  ← operator reads from config volume
    │   └─ OSError → log error (no token), proceed (in-memory is authority)
    └─ return neutral HTMLResponse   ← token NEVER here

Operator reads token from log/file
    │
    ▼
POST /reset/confirm  (exempt from AuthMiddleware)
    │
    ├─ optimistic rate check (last_reset_time["confirm"], monotonic)
    │   └─ 429 if within 5s window
    │
    async with search_lock:
    │   ├─ re-check rate (double-check, same as search_now)
    │   ├─ validate: present? not expired? compare_digest matches?
    │   │   └─ fail → 200 re-render with generic "Invalid or expired" (no state change)
    │   ├─ validate password fields (non-empty, match, ≤72 bytes)
    │   │   └─ fail → 200 re-render with per-field errors dict
    │   ├─ hash_password(new_password)
    │   ├─ generate_session_secret()
    │   ├─ auth.model_copy(update={password_hash, session_secret})
    │   ├─ settings.model_copy(update={auth})
    │   ├─ run_in_executor(_atomic_toml_write, config_path, dict)
    │   ├─ os.chmod(config_path, 0o600)
    │   ├─ load_settings(config_path)  →  app.state.settings
    │   ├─ clear app.state.reset_token = None
    │   └─ delete reset-token.txt (warn on failure, don't block)
    │
    ├─ _sync_auth_state(settings)
    ├─ collect_secrets(settings)  →  setup_logging(log_level, secrets)
    │
    └─ set cookie: sign_session(username, NEW secret)
       RedirectResponse("/", 303)   ← lands on dashboard, logged in
```

### Recommended Project Structure

No new modules. All additions are in-place within existing files:

```
triggarr/
├── auth.py                  # ADD: generate_reset_token() at end of generate_* group
├── web/
│   ├── routes.py            # ADD: 3 handlers + 2 rate-limit constants
│   └── middleware.py        # EDIT: EXEMPT_PREFIXES tuple, add "/reset"
└── templates/
    └── reset.html           # NEW: minimal form shell (Phase 73 replaces)
tests/
└── test_reset.py            # NEW: all Phase 72 tests (TDD-first)
```

### Pattern 1: `search_now` Rate-Limit (optimistic + locked double-check)

The rate-limit pattern for `/reset/request` and `/reset/confirm`. Both endpoints use this structure with their own keys in `app.state.last_reset_time`. [VERIFIED: live codebase routes.py:876-908]

```python
# Source: triggarr/web/routes.py lines 890-908 (search_now)

# Optimistic rate limit check BEFORE lock (fast-fail for obvious cases)
rate_key = "request"  # or "confirm"
now = time.monotonic()
last = request.app.state.last_reset_time.get(rate_key, 0.0)
if now - last < RESET_REQUEST_RATE_LIMIT_SECONDS:
    return HTMLResponse("Rate limited -- try again shortly", status_code=429)

async with request.app.state.search_lock:
    # Re-check inside lock to prevent concurrent bypass
    now = time.monotonic()
    last = request.app.state.last_reset_time.get(rate_key, 0.0)
    if now - last < RESET_REQUEST_RATE_LIMIT_SECONDS:
        return HTMLResponse("Rate limited -- try again shortly", status_code=429)
    request.app.state.last_reset_time[rate_key] = now
    # ... proceed with operation
```

**Key difference from `search_now`:** For `/reset/request`, there is no `search_lock` acquisition for the actual mint operation — only the rate-limit re-check needs the lock. However, because the spec says to reuse the `search_now` monotonic-timestamp pattern and the confirm path already acquires `search_lock`, using the same lock for both is simplest and correct. [ASSUMED: the request endpoint's rate limit re-check may be done without holding `search_lock` since the mint itself is non-conflicting with search cycles; the confirm path holds the lock for the full apply sequence per D-08.]

**Clarification on lock scope for `/reset/request`:** The `search_now` pattern holds the lock for the whole operation. For the mint path, holding the lock is also safe (the mint is fast), but is not strictly required since there is no TOCTOU concern on mint — minting always overwrites. The planner should decide: either acquire `search_lock` for the rate-check double-check + mint (simple, consistent), or do the mint without the lock (acceptable, slightly less contention). D-08 only mandates the lock on the confirm path.

### Pattern 2: `change_password` — Apply Path to Mirror

The exact sequence for `reset_confirm_post` after token validation passes. [VERIFIED: live codebase routes.py:1424-1488]

```python
# Source: triggarr/web/routes.py lines 1424-1488 (change_password)

config_path = request.app.state.config_path
async with request.app.state.search_lock:
    # Validate token inside lock (TOCTOU guard — replaces current-password verify)
    current_settings = request.app.state.settings

    try:
        new_hash = hash_password(new_password)
    except ValueError:
        return templates.TemplateResponse(
            request=request,
            name="reset.html",
            context={"errors": {"new_password": "Password must be 72 characters or fewer"}},
        )

    new_session_secret = generate_session_secret()
    new_auth = current_settings.auth.model_copy(
        update={
            "password_hash": SecretStr(new_hash),
            "session_secret": SecretStr(new_session_secret),
        }
    )
    updated = current_settings.model_copy(update={"auth": new_auth})
    config_dict = _settings_to_dict(updated)
    await asyncio.get_running_loop().run_in_executor(
        None, _atomic_toml_write, config_path, config_dict
    )
    os.chmod(config_path, 0o600)
    request.app.state.settings = load_settings(config_path)
    # RESET-SPECIFIC: also clear in-memory token and delete token file here

_sync_auth_state(request.app.state.settings)
_new_secrets = collect_secrets(request.app.state.settings)
setup_logging(request.app.state.settings.general.log_level, _new_secrets)

# Auto-login: set cookie under NEW secret (read from reloaded settings)
refreshed_username = request.app.state.settings.auth.username
response = RedirectResponse(url=request.url_for("dashboard"), status_code=303)
response.set_cookie(
    "triggarr_session",
    sign_session(refreshed_username, new_session_secret),
    max_age=COOKIE_MAX_AGE,
    httponly=True,
    samesite="lax",
    secure=is_secure_request(request),
)
return response
```

**Critical ordering note (Pitfall F):** `new_session_secret` must be captured as a local variable inside the lock before `load_settings` reloads from disk. The `sign_session` call after the lock can safely use this local variable — it equals the value now in `app.state.settings.auth.session_secret`. Do NOT call `request.app.state.settings.auth.session_secret.get_secret_value()` for signing — use the captured `new_session_secret` local or the reloaded settings value. They are identical but the captured local is proof of ordering.

### Pattern 3: Atomic Token-File Write

Mirrors `_atomic_toml_write` but writes raw bytes (the token string) rather than TOML. [VERIFIED: live codebase config.py:95-163]

```python
# Source: triggarr/config.py lines 95-163 (_atomic_toml_write — adapt for token file)

token_path = request.app.state.config_path.parent / "reset-token.txt"
fd, tmp_path = tempfile.mkstemp(dir=token_path.parent, suffix=".tmp")
renamed = False
dir_fd = None
try:
    with os.fdopen(fd, "w") as f:
        f.write(token)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, token_path)
    renamed = True
    dir_fd = os.open(token_path.parent, os.O_RDONLY)
    os.fsync(dir_fd)
except OSError as exc:
    if renamed:
        logger.warning("Token file written but directory fsync failed: {exc}", exc=exc)
        # proceed — file is there
    else:
        logger.error("Token file write failed: {exc}", exc=exc)  # NO token in message
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        # per D-17: still proceed, in-memory token is authority
finally:
    if dir_fd is not None:
        os.close(dir_fd)
os.chmod(token_path, 0o600)
```

**Note:** This write is synchronous and should be dispatched via `run_in_executor` (or a private `_write_reset_token_file` helper callable from executor) to avoid blocking the event loop, consistent with how `_atomic_toml_write` is dispatched in `change_password`.

### Pattern 4: `login_post` Cookie Attributes

The exact cookie shape for auto-login. [VERIFIED: live codebase routes.py:1351-1359]

```python
# Source: triggarr/web/routes.py lines 1351-1359 (login_post success)

response = RedirectResponse(url=redirect_url, status_code=303)
response.set_cookie(
    "triggarr_session",
    sign_session(username, auth.session_secret.get_secret_value()),
    max_age=COOKIE_MAX_AGE,   # 30 * 24 * 60 * 60 = 2592000
    httponly=True,
    samesite="lax",
    secure=is_secure_request(request),
)
```

### Pattern 5: app.state Initialization Site

New fields must be added alongside the existing `app.state` initialization block in `create_lifespan`. [VERIFIED: live codebase scheduler.py:471-534]

```python
# Source: triggarr/search/scheduler.py lines 499-500 (existing fields to mirror)

# last_search_time: dict[str, float]  (key: rate-limit token, value: monotonic ts)
app.state.last_search_time = {}

# ADD alongside these two (same WR-05 comment style):
# reset_token: tuple[str, float] | None  (token string, expiry monotonic ts)
app.state.reset_token = None
# last_reset_time: dict[str, float]  (key: "request"/"confirm", value: monotonic ts)
app.state.last_reset_time = {}
```

**Exact location:** After line 500 (`app.state.last_search_time = {}`) and before line 501 (`app.state.last_health_check = None`), or grouped with the rate-limit fields.

### Pattern 6: `generate_reset_token()` Placement in `auth.py`

Add after `generate_session_secret()` (auth.py:61-67), before `sign_session`. [VERIFIED: live codebase auth.py:52-68]

```python
# Source: triggarr/auth.py — symmetry with generate_api_key/generate_session_secret

def generate_reset_token() -> str:
    """Generate a URL-safe reset token using CSPRNG.

    Returns:
        Cryptographically random URL-safe string (32 bytes of entropy, 43 chars).
    """
    return secrets.token_urlsafe(32)
```

### Anti-Patterns to Avoid

- **Re-acquiring `search_lock` inside `_run_one_cycle`:** `search_now` explicitly documents this: "This lock is already held; `_run_one_cycle` must NOT acquire it again (single asyncio.Lock; double-acquire deadlocks)" (routes.py:931-932). The reset confirm path holds the lock for the full apply sequence. No nested lock acquisition.
- **Signing the cookie with `app.state.settings.auth.session_secret.get_secret_value()` after `load_settings`:** The reloaded settings will have the new secret, so this is technically correct — but use the captured `new_session_secret` local to make the intent clear and avoid any ambiguity about which value is used.
- **Logging the token value at any point other than the single intentional `logger.warning` call:** The token must never appear in error messages, file-write failure messages, or confirm-path log entries. Use sanitized messages (`"Token file write failed: {exc}"`, not `"Failed to write token {token}: {exc}"`).
- **Calling `secrets.compare_digest` outside the lock:** Token validation must be inside `search_lock` per D-08. An optimistic read-without-lock for the rate check is fine (reading `last_reset_time`), but the token comparison itself must not race.
- **Returning the token in any HTTP response field:** Not just the body — also not in a header, redirect URL, or error context. The `reset.html` template must not receive `token` in its context dict.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSPRNG token | Custom entropy source | `secrets.token_urlsafe(32)` | stdlib CSPRNG; already used for `generate_session_secret` |
| Constant-time comparison | `submitted == stored` | `secrets.compare_digest(submitted, stored)` | Timing-safe; prevents timing oracle on token guessing |
| Password hashing | Custom bcrypt call | `hash_password(new_password)` in `auth.py` | Already handles 72-byte check + gensalt(12) |
| Cookie signing | Custom HMAC | `sign_session(username, secret)` in `auth.py` | `itsdangerous.TimestampSigner`; already used everywhere |
| Cookie validation | Comparing raw cookie values | `validate_session(cookie, secret)` in `auth.py` | Handles expiry + signature verification |
| Atomic file write | Direct open + write | `_atomic_toml_write` pattern (adapt for token) | temp-then-rename + fsync ensures durability on crash |
| Rate-limit state | In-request counter | `app.state.last_reset_time` monotonic dict | Matches existing `last_search_time` pattern exactly |
| Session secret rotation | Any other invalidation mechanism | `generate_session_secret()` + `model_copy` + persist | Same as `change_password`; all existing session cookies fail `validate_session` against new secret |

**Key insight:** Every non-trivial security operation in this phase has an existing implementation in the codebase. The task is assembly, not invention.

---

## Codebase Investigation Findings

### 1. Exact Code: `change_password` Key Lines

Lines 1425–1488 of `triggarr/web/routes.py` [VERIFIED: live codebase]:

```
1424: config_path = request.app.state.config_path
1425: async with request.app.state.search_lock:
1426:     # Verify current password inside lock to prevent TOCTOU race (WR-01)
1427:     current_settings = request.app.state.settings
1437:     try:
1438:         new_hash = hash_password(new_password)
1439:     except ValueError:                       # bcrypt 72-byte limit
1440:         return TemplateResponse(...)          # field-level error
1449:     new_session_secret = generate_session_secret()
1450:     new_auth = current_settings.auth.model_copy(
1451:         update={"password_hash": SecretStr(new_hash), "session_secret": SecretStr(new_session_secret)}
1452:     )
1456:     updated = current_settings.model_copy(update={"auth": new_auth})
1457:     config_dict = _settings_to_dict(updated)
1458:     await asyncio.get_running_loop().run_in_executor(
1459:         None, _atomic_toml_write, config_path, config_dict
1460:     )
1461:     os.chmod(config_path, 0o600)
1462:     request.app.state.settings = load_settings(config_path)
1464: _sync_auth_state(request.app.state.settings)
1465: _new_secrets = collect_secrets(request.app.state.settings)
1466: setup_logging(request.app.state.settings.general.log_level, _new_secrets)
1477: refreshed_username = request.app.state.settings.auth.username
1478: if refreshed_username:
1479:     response.set_cookie("triggarr_session", sign_session(refreshed_username, new_session_secret), ...)
```

**Reset-confirm differences from `change_password`:**
1. No `verify_password(current_password, ...)` — token validation replaces it.
2. After lock succeeds: clear `app.state.reset_token = None` and delete `reset-token.txt`.
3. Response is `RedirectResponse(303)` to dashboard (not a partial `TemplateResponse`).
4. Cookie is set on the redirect response (not a pre-built template response).

### 2. Exact Code: `search_now` Rate-Limit Lines

Lines 890–908 of `triggarr/web/routes.py` [VERIFIED: live codebase]:

```
890:   rate_key = f"{app_name}_{instance_name}"
891:   now = time.monotonic()
892:   last = request.app.state.last_search_time.get(rate_key, 0.0)
893:   if now - last < SEARCH_RATE_LIMIT_SECONDS:
894:       logger.info("... rate-limited")
895:       return HTMLResponse("Rate limited -- try again shortly", status_code=429)
897:   async with request.app.state.search_lock:
899:       now = time.monotonic()
900:       last = request.app.state.last_search_time.get(rate_key, 0.0)
901:       if now - last < SEARCH_RATE_LIMIT_SECONDS:
902:           logger.info("... rate-limited (after lock)")
903:           return HTMLResponse("Rate limited -- try again shortly", status_code=429)
907:       request.app.state.last_search_time[rate_key] = now
```

`SEARCH_RATE_LIMIT_SECONDS = 10` is defined at line 143. New constants for reset should be adjacent:

```python
# After SEARCH_RATE_LIMIT_SECONDS = 10 (routes.py:143)
RESET_REQUEST_RATE_LIMIT_SECONDS = 60
RESET_CONFIRM_RATE_LIMIT_SECONDS = 5
```

### 3. `app.state.config_path` Initialization and Config-Dir Reference

`config_path` is set in `create_lifespan` at `scheduler.py:479`:
```python
app.state.config_path = config_path  # Path to triggarr.toml
```

`config_path` is passed in from `__main__.py:68`:
```python
app = FastAPI(lifespan=create_lifespan(settings, state_path, config_path))
```

where `config_path = get_config_path()` = `get_config_dir() / "triggarr.toml"`. [VERIFIED: live codebase]

Therefore: `token_path = request.app.state.config_path.parent / "reset-token.txt"` gives the correct config directory. `config.py:237` confirms: `config_path.parent.mkdir(parents=True, exist_ok=True)` — the parent is the config dir, which already exists by the time routes run.

In `routes.py`, `_runtime_config_dir(request)` at lines 95-97 provides this as a helper:
```python
def _runtime_config_dir(request: Request) -> Path:
    return Path(request.app.state.config_path).parent
```
The reset handlers can use this helper for `reset-token.txt` path construction.

### 4. Middleware `EXEMPT_PREFIXES` Prefix-Match Analysis

`middleware.py:112`: `if any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES):`

Current `EXEMPT_PREFIXES = ("/health", "/static", "/login", "/setup")` (middleware.py:22).

Adding `"/reset"` exempts:
- `/reset` — GET form page (`reset_request_page`)
- `/reset/request` — POST mint
- `/reset/confirm` — POST apply

**Over-exposure analysis:** No existing routes begin with `/reset` (confirmed by grep of `triggarr/web/routes.py` — zero matches for `"/reset`). The only routes added by this phase are:
- `GET /reset/request` (or `GET /reset`) — the form shell
- `POST /reset/request` — mint
- `POST /reset/confirm` — apply

There is no risk of a hypothetical `/resetXYZ` route being accidentally exempted because no such routes exist in the codebase and none will be added by this phase. The prefix `/reset` is a clean namespace. [VERIFIED: live codebase grep]

**Note:** The `/reset` prefix is more specific than `/login` (which also exempts `/login?next=...` via query strings — but that is not a security concern as query strings are not part of `path`). The exemption is correct and not over-broad.

### 5. Test Patterns for Reset Tests

From `test_auth_routes.py`, the established patterns are:

**App construction:** `_make_route_app(auth_config, config_path)` at test_auth_routes.py:82-108:
```python
def _make_route_app(...) -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(router)
    app.mount("/static", ...)
    app.state.settings = settings
    app.state.config_path = config_path or Path("/tmp/test-triggarr.toml")
    app.state.search_lock = asyncio.Lock()
    return app
```

For reset tests, the `_make_route_app` helper needs two additional `app.state` fields:
```python
app.state.reset_token = None
app.state.last_reset_time = {}
```

These can be added to a local `_make_reset_app` helper in `test_reset.py` that wraps `_make_route_app` and patches the additional fields, or the team can extend `_make_route_app` directly.

**Time injection for monotonic-dependent tests** (from test_auth_routes.py:1120-1133, `monkeypatch.setattr(time, "monotonic", lambda: fake_time)`):

```python
def test_token_expired(tmp_path, monkeypatch):
    """Token rejected after 15-minute TTL."""
    app = _make_reset_app(config_path=tmp_path / "triggarr.toml")
    # Mint token at t=0
    app.state.reset_token = ("sometoken", 0.0 + 900)   # expires at t=900
    # Simulate t=901 (past expiry)
    monkeypatch.setattr(time, "monotonic", lambda: 901.0)
    client = TestClient(app, follow_redirects=False)
    resp = client.post("/reset/confirm", data={"token": "sometoken", "new_password": "x", "confirm_password": "x"})
    # Should get generic error, not success
    assert resp.status_code == 200
    assert "Invalid or expired" in resp.text
```

**Direct state manipulation** (simpler alternative for some TTL tests):
```python
# Set token with already-expired timestamp
app.state.reset_token = ("sometoken", time.monotonic() - 1)  # expired 1s ago
```

**Cookie assertion pattern** (from test_auth_routes.py:111-113):
```python
def _set_cookie_has_secure_attribute(set_cookie: str) -> bool:
    return "secure" in {part.strip().lower() for part in set_cookie.split(";")[1:]}
```

**Redaction assertion pattern** (no token in response body):
```python
assert token_value not in response.text
assert token_value not in response.headers.get("set-cookie", "")
assert token_value not in str(response.headers)
```

**Session rotation verification** (from test_auth_routes.py:604-638):
```python
persisted = tomllib.loads(config_file.read_text())
new_secret = persisted["auth"]["session_secret"]
assert new_secret != original_secret
assert validate_session(old_cookie, new_secret) is None  # old cookie invalid
```

**`conftest.py` auto-resets:** The global `_reset_rate_limiter()` autouse fixture in `conftest.py` resets login rate state, but NOT `app.state.last_reset_time` (since that's per-app-instance). Test isolation for reset rate-limit is via constructing fresh app instances (standard pattern for integration tests) or by setting `app.state.last_reset_time = {}` in a fixture.

**File organization decision (Claude's Discretion):** The spec's §2.7 tests map naturally to a new `tests/test_reset.py` file (9+ test categories, comparable in scope to `test_auth_routes.py`'s reset-related subsections). This is cleaner than growing `test_auth_routes.py` further.

### 6. Pitfall Analysis (Requested in Objective)

**(a) Double-acquire of `search_lock` deadlock:** `search_now` documents the hazard at routes.py:931-932 for `_run_one_cycle`. `reset_confirm_post` does NOT call `_run_one_cycle`, so this specific hazard does not apply. However: any helper called from inside the `async with search_lock:` block must not attempt to acquire the same lock. The token-file delete and the token-file write are simple synchronous operations dispatched via `run_in_executor` — neither touches `search_lock`. Safe. [VERIFIED: no nested lock acquisition in the apply path]

**(b) Token redaction — interaction with `collect_secrets` and the redacting sink:** `collect_secrets` (startup.py:74-100) extracts `password_hash`, `api_key`, and `session_secret` from settings — it does NOT include the reset token. This is correct by design: the token is deliberately logged once at `warning` level, and should not be suppressed from that log entry. The redacting sink would suppress it from ALL subsequent log lines if it were added. Since the token is short-lived and never logged again after the initial mint, the design is correct — do NOT add the token to `collect_secrets`. After a successful reset, `collect_secrets` is called with the updated settings (new `session_secret`, new `password_hash`), which correctly refreshes the redaction set for those rotated values. [VERIFIED: startup.py:74-100]

**(c) `is_secure_request` / cookie `Secure` flag behind a proxy:** `is_secure_request` reads `request.url.scheme` (security.py:15), which uvicorn sets from the `X-Forwarded-Proto` header only when the request comes from a trusted proxy IP (`forwarded_allow_ips` in uvicorn config). Direct requests (non-proxy) get the raw connection scheme. Tests use `base_url="https://testserver"` to trigger `secure=True`. The spoofed `X-Forwarded-Proto` tests in `test_auth_routes.py` verify the correct behavior (must not trust a spoofed header from an untrusted source). The reset cookie uses the same `is_secure_request(request)` call — no special handling needed. [VERIFIED: live codebase security.py + test_auth_routes.py:381-396]

**(d) The 72-byte bcrypt limit `ValueError` path:** `hash_password` in `auth.py:13-29` raises `ValueError` with message "Password must be 72 bytes or fewer" when `len(plaintext.encode()) > 72`. The catch in `change_password` returns a field-level error: `{"new_password": "Password must be 72 characters or fewer"}`. Reset confirm should use the same pattern. Note: the `ValueError` from `hash_password` is on raw byte length, not character count, but the error message says "characters" (consistent with existing `change_password` behavior). [VERIFIED: live codebase auth.py:25-28 + routes.py:1438-1444]

**(e) Constant-time compare with `secrets.compare_digest`:** The token must be compared with `secrets.compare_digest(submitted_token, stored_token)` where `stored_token` is the string from `app.state.reset_token[0]`. Both arguments must be the same type (str). `secrets.token_urlsafe(32)` returns a str; form data `str(form.get("token", ""))` is also str. No encoding mismatch risk. The username comparison in `login_post` uses `secrets.compare_digest(username, auth.username)` at routes.py:1345 — same pattern. [VERIFIED: live codebase auth.py + routes.py:1345]

**(f) Ordering hazard: rotate-secret → write-TOML → reload-settings → re-sign-cookie:** The critical constraint is that the cookie must be signed with the NEW secret. The ordering in `change_password` (the template) handles this correctly:
1. `new_session_secret` is captured as a local variable (routes.py:1449).
2. `_atomic_toml_write` persists the new secret.
3. `load_settings` reloads from disk — `app.state.settings.auth.session_secret` now holds the new value.
4. `sign_session(username, new_session_secret)` uses the local (identical to reloaded) value.

The new cookie validates against the new `session_secret` in `app.state.settings`. Any subsequent `validate_session` call (including the very next request from this browser) will succeed. Old cookies fail because `validate_session(old_cookie, new_secret)` gets `BadSignature`. [VERIFIED: live codebase routes.py:1449-1486 + auth.py:88-106]

---

## Common Pitfalls

### Pitfall 1: Token Value in Error Message
**What goes wrong:** An `OSError` handler for the token-file write includes `{token}` in the log message. The token now appears in the application log at `error` level — beyond the intentional `warning` line.
**Why it happens:** Copy-paste from patterns that log the value being operated on.
**How to avoid:** All error/warning log messages about the token file must reference only the file path and exception, never the token string itself.
**Warning signs:** Any logger call inside the file-write try/except that accesses the `token` variable.

### Pitfall 2: Cookie Signed with Pre-Reload Secret
**What goes wrong:** The redirect cookie is signed with `request.app.state.settings.auth.session_secret.get_secret_value()` read BEFORE `load_settings` is called. The settings object in memory still holds the OLD secret, so the cookie fails validation on the next request.
**Why it happens:** The `new_session_secret` local variable captures the right value, but a developer reads from `app.state.settings` for consistency — not noticing that `load_settings` happens later.
**How to avoid:** Always use the captured `new_session_secret` local for the `sign_session` call, not `app.state.settings.auth.session_secret`.
**Warning signs:** `sign_session` call appearing before `request.app.state.settings = load_settings(config_path)`.

### Pitfall 3: Token Comparison Before Lock
**What goes wrong:** The `secrets.compare_digest` call is placed in the optimistic pre-lock check (fast path). This creates a TOCTOU window: two concurrent confirm requests could both pass the optimistic comparison if the token is about to expire, then both proceed into the lock.
**Why it happens:** Rate-limit follows `search_now`'s optimistic pattern, which is correct for rate limits. Token validation requires the lock (D-08).
**How to avoid:** Token validation (expiry check + `compare_digest`) must be inside the `async with request.app.state.search_lock:` block. Only rate-limit timestamp reads happen outside.
**Warning signs:** `app.state.reset_token` accessed or compared before the `async with` block.

### Pitfall 4: `test_reset.py` Missing `app.state.last_reset_time` and `app.state.reset_token`
**What goes wrong:** Test helper builds the app using `_make_route_app` but does not initialize the two new `app.state` fields. The route handler's `.get(rate_key, 0.0)` on `app.state.last_reset_time` raises `AttributeError`.
**Why it happens:** `_make_route_app` in `test_auth_routes.py` predates Phase 72 and only initializes `search_lock` (and implicitly `settings`, `config_path`). The lifespan is not run in unit tests — `app.state` fields must be set manually.
**How to avoid:** `test_reset.py`'s app-building helper must explicitly set: `app.state.reset_token = None` and `app.state.last_reset_time = {}`.
**Warning signs:** `AttributeError: 'State' object has no attribute 'last_reset_time'` in test output.

### Pitfall 5: Neutral Confirmation Response Leaking Token
**What goes wrong:** The `reset_request_post` handler passes `token` in the template context for debugging, or includes it in a `data-` attribute or hidden field.
**Why it happens:** Template developers may want to make token retrieval convenient.
**How to avoid:** Template context for the confirmation page must not include the token. The template receives only the neutral message string ("check docker logs or reset-token.txt").
**Warning signs:** `token` appears in any `context=` dict passed to a `TemplateResponse` in the request handler.

### Pitfall 6: Token File Permission Race
**What goes wrong:** `os.chmod(token_path, 0o600)` is called after `os.replace`. Between `os.replace` and `os.chmod`, the file exists at `token_path` with default permissions (umask-dependent). A concurrent reader could access the token.
**Why it happens:** `chmod` must follow the rename (pre-rename `chmod` on the temp file is also correct since `os.replace` preserves permissions on Linux, but this is less obvious).
**How to avoid:** Set permissions on the temp file fd BEFORE `os.replace` (via `os.fchmod(fd, 0o600)` immediately after `mkstemp` and before writing), or accept the brief window (acceptable in single-container deployments where only the triggarr process has access to the config directory). The `_atomic_toml_write` pattern applies `os.chmod` after `os.replace` — maintain the same behavior for consistency.
**Warning signs:** `os.chmod` call before the `os.replace` step is missing, or relies on the umask being restrictive.

---

## Code Examples

### `generate_reset_token` Addition to `auth.py`

```python
# Source: auth.py — add after line 67 (generate_session_secret), before sign_session
# [VERIFIED: live codebase auth.py structure]

def generate_reset_token() -> str:
    """Generate a URL-safe reset token using CSPRNG.

    Returns:
        Cryptographically random URL-safe string (32 bytes of entropy, ~43 chars).
    """
    return secrets.token_urlsafe(32)
```

### `EXEMPT_PREFIXES` Update

```python
# Source: triggarr/web/middleware.py line 22
# [VERIFIED: live codebase]
# Before:
EXEMPT_PREFIXES = ("/health", "/static", "/login", "/setup")
# After:
EXEMPT_PREFIXES = ("/health", "/static", "/login", "/setup", "/reset")
```

### Rate-Limit Constants (routes.py)

```python
# Source: triggarr/web/routes.py — add after SEARCH_RATE_LIMIT_SECONDS = 10 (line 143)
# [VERIFIED: live codebase]
SEARCH_RATE_LIMIT_SECONDS = 10
RESET_REQUEST_RATE_LIMIT_SECONDS = 60   # Prevent log/file flooding (~1 mint/min)
RESET_CONFIRM_RATE_LIMIT_SECONDS = 5    # Throttle token-guessing attempts
```

### Token Deletion on Successful Reset

```python
# Inside async with search_lock, after load_settings succeeds:
app.state.reset_token = None
token_path = _runtime_config_dir(request) / "reset-token.txt"
try:
    token_path.unlink(missing_ok=True)
except OSError as exc:
    logger.warning("Failed to delete reset token file: {exc}", exc=exc)
    # D-19: warn, don't block — reset already succeeded
```

### `app.state` Init in `create_lifespan` (scheduler.py addition)

```python
# Source: triggarr/search/scheduler.py — add after line 500
# [VERIFIED: live codebase scheduler.py:499-500]

# last_search_time: dict[str, float]  (key: rate-limit token, value: monotonic ts)
app.state.last_search_time = {}
# reset_token: tuple[str, float] | None  (CSPRNG token string, expiry as monotonic ts)
# Set by reset_request_post, consumed and cleared by reset_confirm_post.
# A container restart sets this to None, invalidating any pending reset token (D-04, D-18).
app.state.reset_token = None
# last_reset_time: dict[str, float]  (key: "request"/"confirm", value: monotonic ts)
# Rate-limit gate for both reset endpoints (D-14, D-15).
app.state.last_reset_time = {}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Email-based password reset | Filesystem-token model (log + 0600 file) | Triggarr design decision (v2.10) | No mail infra needed; proves host access not identity |
| Hand-edit `triggarr.toml` to recover | `/reset` HTTP flow | Phase 72 (this phase) | Operator recovery without TOML knowledge |
| `change_password` required current password | Token replaces current-password verify | Phase 72 (this phase) | Recovery when locked out |
| No session rotation on recovery | Rotate `session_secret` on reset (mirrors v2.8.1) | Phase 72 (this phase) | All pre-reset cookies invalidated; fresh start |

**The v2.8.1 precedent (critical context):** The `change_password` session rotation (CWE-613 fix, commit `0866332`) is the direct ancestor of the reset-confirm rotation. Phase 72 extends the same pattern to the recovery path. The test patterns in `test_auth_routes.py:604-707` (rotation, re-issue, eviction, API-key unaffected) are the exact test categories needed for reset-confirm.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `/reset/request` mint does not need to hold `search_lock` for the mint itself (only for the rate-limit double-check if the lock is acquired at all). The lock is mandatory for `/reset/confirm` per D-08. | Architecture Patterns, Pattern 1 note | Low — if planner decides to hold the lock for the entire request path (simpler, consistent with `search_now`), that is also correct. The only risk is unnecessary contention if a search cycle is running, but mints are rare. |
| A2 | Test file organization: a new `tests/test_reset.py` is preferred over extending `test_auth_routes.py`. | Codebase Investigation §5 | Low — either is valid. The planner/executor can choose based on suite layout at implementation time. |

**If this table is empty after review:** All other claims are verified directly from the live codebase.

---

## Open Questions (RESOLVED)

> Both resolved during planning — recommendations below are implemented in the plans
> (lock scope → Plan 72-02; single combined template → Plan 72-01 Task 2).

1. **Lock scope for `/reset/request` mint**
   - What we know: D-08 mandates `search_lock` for the confirm apply path. D-14/D-15 mandate the optimistic+locked rate-check pattern from `search_now`.
   - What's unclear: Does the mint itself need to run inside `search_lock` (analogous to the `search_now` pattern where the rate-timestamp update happens inside the lock), or is it sufficient to do only the rate-limit double-check inside the lock and then release before minting?
   - Recommendation: Planner should hold `search_lock` for the rate-check + timestamp update + mint (full `search_now` pattern). The mint is fast (one CSPRNG call + one state assignment). This is consistent, avoids a race where two concurrent mints could both pass the rate check, and keeps the pattern simple.

2. **Minimal `reset.html` template scope**
   - What we know: Phase 72 may render "a minimal/functional form shell sufficient to exercise the backend and tests." Phase 73 replaces with styled pages.
   - What's unclear: Should Phase 72's `reset.html` be a single template serving both the request form and the confirm form (with a conditional), or two separate templates?
   - Recommendation: A single `reset.html` with a conditional block is simplest for Phase 72. Phase 73 can split into `reset_request.html` and `reset_confirm.html` when styling.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 72 is a pure Python code addition within the existing project. No new external services, CLIs, or runtimes are required. All dependencies (`bcrypt`, `itsdangerous`, `loguru`, `fastapi`, `pytest-asyncio`) are already in `pyproject.toml` and installed.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio, `asyncio_mode=auto` |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_reset.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RCOV-02 | POST /reset/request mints token visible in state; NOT in response body | unit+integration | `uv run pytest tests/test_reset.py::test_request_mints_token -x` | ❌ Wave 0 |
| RCOV-02 | Token file written at `config_path.parent/reset-token.txt` with mode 0600 | integration | `uv run pytest tests/test_reset.py::test_token_file_written_0600 -x` | ❌ Wave 0 |
| RCOV-02 | Token value not in HTTP response body or headers | integration | `uv run pytest tests/test_reset.py::test_token_not_in_response -x` | ❌ Wave 0 |
| RCOV-03 | Token stored with correct 900s TTL (expiry = monotonic + 900) | unit | `uv run pytest tests/test_reset.py::test_token_ttl_stored_correctly -x` | ❌ Wave 0 |
| RCOV-03 | Expired token rejected (monotonic clock injectable) | unit | `uv run pytest tests/test_reset.py::test_expired_token_rejected -x` | ❌ Wave 0 |
| RCOV-03 | New mint invalidates prior token | unit | `uv run pytest tests/test_reset.py::test_new_mint_supersedes_prior -x` | ❌ Wave 0 |
| RCOV-03 | Single-use: confirmed token cannot be reused | integration | `uv run pytest tests/test_reset.py::test_token_single_use -x` | ❌ Wave 0 |
| RCOV-04 | Valid token + matching password → 303 to dashboard + session cookie | integration | `uv run pytest tests/test_reset.py::test_confirm_success_redirects_with_cookie -x` | ❌ Wave 0 |
| RCOV-04 | `session_secret` is rotated in persisted TOML | integration | `uv run pytest tests/test_reset.py::test_confirm_rotates_session_secret -x` | ❌ Wave 0 |
| RCOV-04 | Pre-reset cookie fails `validate_session` after reset | integration | `uv run pytest tests/test_reset.py::test_pre_reset_cookie_invalid_after_reset -x` | ❌ Wave 0 |
| RCOV-04 | New cookie validates under new secret | integration | `uv run pytest tests/test_reset.py::test_new_cookie_validates_after_reset -x` | ❌ Wave 0 |
| RCOV-04 | Wrong token → generic error, no state change | integration | `uv run pytest tests/test_reset.py::test_wrong_token_generic_error -x` | ❌ Wave 0 |
| RCOV-04 | Password mismatch → per-field error | integration | `uv run pytest tests/test_reset.py::test_password_mismatch_field_error -x` | ❌ Wave 0 |
| RCOV-04 | Empty password → per-field error | integration | `uv run pytest tests/test_reset.py::test_empty_password_field_error -x` | ❌ Wave 0 |
| RCOV-04 | >72-byte password → per-field error | integration | `uv run pytest tests/test_reset.py::test_password_too_long_field_error -x` | ❌ Wave 0 |
| RCOV-05 | Second /reset/request within 60s → 429 | integration | `uv run pytest tests/test_reset.py::test_request_rate_limited -x` | ❌ Wave 0 |
| RCOV-05 | Rapid /reset/confirm attempts → 429 | integration | `uv run pytest tests/test_reset.py::test_confirm_rate_limited -x` | ❌ Wave 0 |
| RCOV-06 | GET /reset/request reachable unauthenticated (no cookie) | integration | `uv run pytest tests/test_reset.py::test_reset_routes_unauthenticated -x` | ❌ Wave 0 |
| RCOV-06 | /reset/* does not expose any other authenticated route | integration | `uv run pytest tests/test_reset.py::test_no_other_route_exposed -x` | ❌ Wave 0 |
| RCOV-06 | Token file deleted after successful reset | integration | `uv run pytest tests/test_reset.py::test_token_file_deleted_on_success -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_reset.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_reset.py` — all tests listed above (new file, does not exist)

*(Existing test infrastructure — `conftest.py`, `_make_route_app` helper in `test_auth_routes.py`, `monkeypatch` for `time.monotonic`, `tomllib` for TOML verification — covers all ancillary needs. Only the new test file is a Wave 0 gap.)*

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | Token-proves-host-access model; bcrypt via `hash_password`; no credential enumeration |
| V3 Session Management | Yes | `session_secret` rotation via `generate_session_secret()`; itsdangerous `TimestampSigner`; `httponly`, `samesite=lax`, `secure=is_secure_request` |
| V4 Access Control | Yes | `/reset` added to `EXEMPT_PREFIXES` (explicitly unauthenticated); no escalation to authenticated routes |
| V5 Input Validation | Yes | Token: `secrets.compare_digest`; password: non-empty + match + 72-byte limit; form field types enforced |
| V6 Cryptography | Yes | `secrets.token_urlsafe(32)` (CSPRNG, 256 bits); `secrets.compare_digest` (constant-time); bcrypt 12 rounds |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Token enumeration (brute force via confirm endpoint) | Information Disclosure | `secrets.compare_digest` (constant-time) + `RESET_CONFIRM_RATE_LIMIT_SECONDS=5` global throttle |
| Log flooding via repeated mint requests | Denial of Service | `RESET_REQUEST_RATE_LIMIT_SECONDS=60` global throttle |
| Token leakage via HTTP response | Information Disclosure | Token never in any response body, header, or context dict; template receives only neutral confirmation string |
| TOCTOU on token validation | Tampering | Token validation inside `search_lock` (D-08); same pattern as `change_password` current-password verify |
| Cookie signed with old secret after rotation | Elevation of Privilege | Use captured `new_session_secret` local; `load_settings` reloads rotated value; ordering validated in tests |
| Stale token file authorizing after container restart | Spoofing | In-memory token cleared on restart (D-04); file without in-memory counterpart → no validation |
| Token in error log message | Information Disclosure | Sanitized error messages never include token value; only file path and exception (D-17) |
| Timing oracle distinguishing wrong-vs-expired token | Information Disclosure | Single generic "Invalid or expired reset token" message for all validation failures (D-06); no branching by failure type in response |
| Prefix overmatch on `/reset` exemption | Elevation of Privilege | Verified: no existing or planned routes begin with `/reset` other than the three added by this phase |

---

## Sources

### Primary (HIGH confidence — live codebase, all VERIFIED)

- `triggarr/web/routes.py:876-967` — `search_now` rate-limit pattern (exact code quoted above)
- `triggarr/web/routes.py:1400-1488` — `change_password` apply pattern (exact code quoted above)
- `triggarr/web/routes.py:1310-1375` — `login_post` cookie attributes (exact code quoted above)
- `triggarr/web/routes.py:95-108` — `_runtime_config_dir`, `_sync_auth_state`
- `triggarr/web/routes.py:143` — `SEARCH_RATE_LIMIT_SECONDS = 10` (sibling constant location)
- `triggarr/web/middleware.py:22` — `EXEMPT_PREFIXES` current value
- `triggarr/web/middleware.py:107-113` — prefix-match logic (confirmed `any(path.startswith(prefix) ...)`)
- `triggarr/search/scheduler.py:471-534` — `app.state` initialization in `create_lifespan` (exact location for new fields)
- `triggarr/config.py:95-163` — `_atomic_toml_write` (exact pattern to mirror for token-file write)
- `triggarr/auth.py:1-107` — all auth helpers (hash_password, generate_*, sign_session, validate_session, COOKIE_MAX_AGE)
- `triggarr/startup.py:74-100` — `collect_secrets` (confirmed: does NOT collect reset token — by design)
- `triggarr/web/security.py:8-15` — `is_secure_request` (reads `request.url.scheme`)
- `tests/test_auth_routes.py:46-1294` — test patterns (app construction, monkeypatch for time, cookie assertions, TOML verification, session rotation tests)
- `tests/conftest.py:1-27` — autouse fixtures (rate-limiter reset, middleware reset)

### Secondary (MEDIUM confidence)

- `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md` §2 — Design spec (source of truth for locked decisions)
- `.planning/phases/72-password-reset-backend-token-lifecycle/72-CONTEXT.md` — All 23 decisions, canonical references

### Tertiary (LOW confidence)

None. All research was conducted against the live codebase.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all existing library usage verified in codebase
- Architecture: HIGH — exact code lines quoted from live codebase; patterns verified working
- Pitfalls: HIGH — derived from existing code comments, test patterns, and the v2.8.1 security patch record
- Test patterns: HIGH — directly extracted from `test_auth_routes.py` which is the authoritative example

**Research date:** 2026-06-03
**Valid until:** Indefinite for this codebase snapshot (no external dependency versions to expire). Re-read `routes.py:change_password` if the change_password implementation changes before Phase 72 executes.
