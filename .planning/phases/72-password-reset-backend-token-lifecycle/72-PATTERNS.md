# Phase 72: Password Reset Backend & Token Lifecycle - Pattern Map

**Mapped:** 2026-06-03
**Files analyzed:** 6 (4 modified, 2 new)
**Analogs found:** 6 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/auth.py` | utility | transform | `triggarr/auth.py:52-67` (`generate_api_key`, `generate_session_secret`) | exact |
| `triggarr/web/routes.py` (3 handlers + 2 constants) | controller | request-response | `routes.py:1400-1488` (`change_password`), `routes.py:876-967` (`search_now`), `routes.py:1310-1375` (`login_post`) | exact |
| `triggarr/web/middleware.py` | middleware | request-response | `middleware.py:22` (`EXEMPT_PREFIXES`) | exact |
| `triggarr/search/scheduler.py` (`app.state` init) | config | batch | `scheduler.py:499-528` (existing `app.state` init block) | exact |
| `triggarr/templates/reset.html` | component | request-response | `triggarr/templates/login.html` (minimal shell only; Phase 73 styles it) | role-match |
| `tests/test_reset.py` | test | request-response | `tests/test_auth_routes.py:82-113`, `604-707` | exact |

---

## Pattern Assignments

### `triggarr/auth.py` — add `generate_reset_token()`

**Analog:** `triggarr/auth.py` lines 52–67

**Imports pattern** (lines 1–8, already present — no new imports needed):
```python
from __future__ import annotations

import secrets

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
```

**Core pattern to mirror** (lines 61–67, `generate_session_secret`):
```python
def generate_session_secret() -> str:
    """Generate a 64-character hex session secret using CSPRNG.

    Returns:
        Cryptographically random 64-character hex string.
    """
    return secrets.token_hex(32)
```

**Adaptation:** Insert the new function immediately after line 67, before `sign_session`. Use `secrets.token_urlsafe(32)` instead of `secrets.token_hex(32)` (URL-safe alphabet, 43-char output, 256 bits of entropy). Docstring follows the same two-line Returns convention.

```python
def generate_reset_token() -> str:
    """Generate a URL-safe reset token using CSPRNG.

    Returns:
        Cryptographically random URL-safe string (32 bytes of entropy, ~43 chars).
    """
    return secrets.token_urlsafe(32)
```

---

### `triggarr/web/middleware.py` — add `/reset` to `EXEMPT_PREFIXES`

**Analog:** `triggarr/web/middleware.py` line 22

**Current value** (line 22):
```python
EXEMPT_PREFIXES = ("/health", "/static", "/login", "/setup")
```

**Prefix-match logic** (lines 112–113) — confirms `startswith` semantics, so `/reset` covers `/reset`, `/reset/request`, `/reset/confirm`:
```python
if any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
    return await call_next(request)
```

**Adaptation:** Append `"/reset"` as the fifth element. One-line change:
```python
EXEMPT_PREFIXES = ("/health", "/static", "/login", "/setup", "/reset")
```

---

### `triggarr/search/scheduler.py` — add `reset_token` and `last_reset_time` to `app.state` init

**Analog:** `triggarr/search/scheduler.py` lines 499–528 (existing `app.state` block)

**Existing block to insert after** (lines 499–500):
```python
        # last_search_time: dict[str, float]  (key: rate-limit token, value: monotonic ts)
        app.state.last_search_time = {}
        app.state.last_health_check = None
```

**Adaptation:** Insert two new fields immediately after `app.state.last_search_time = {}` (line 500), before `app.state.last_health_check`. Follow the WR-05 comment style (type annotation in comment, not inline):
```python
        # reset_token: tuple[str, float] | None  (CSPRNG token string, expiry as monotonic ts)
        # Set by reset_request_post, consumed and cleared by reset_confirm_post.
        # A container restart sets this to None, invalidating any pending reset token (D-04, D-18).
        app.state.reset_token = None
        # last_reset_time: dict[str, float]  (key: "request"/"confirm", value: monotonic ts)
        # Rate-limit gate for both reset endpoints (D-14, D-15).
        app.state.last_reset_time = {}
```

---

### `triggarr/web/routes.py` — rate-limit constants (2 new constants)

**Analog:** `triggarr/web/routes.py` line 143

**Existing constant** (line 143):
```python
SEARCH_RATE_LIMIT_SECONDS = 10
```

**Adaptation:** Add two new constants immediately after line 143:
```python
RESET_REQUEST_RATE_LIMIT_SECONDS = 60   # Prevent log/file flooding (~1 mint/min)
RESET_CONFIRM_RATE_LIMIT_SECONDS = 5    # Throttle token-guessing attempts
```

---

### `triggarr/web/routes.py` — `reset_request_page` (GET)

**Analog:** Any existing `@router.get` page handler (e.g. `login_page`)

**Pattern:** Thin GET handler — return a `TemplateResponse` with `request` and `name`. No auth required (middleware exemption handles it). The template receives no sensitive context.

```python
@router.get("/reset/request", response_class=HTMLResponse)
async def reset_request_page(request: Request) -> HTMLResponse:
    """Render the password reset request form (unauthenticated)."""
    return templates.TemplateResponse(request=request, name="reset.html", context={"step": "request"})
```

---

### `triggarr/web/routes.py` — `reset_request_post` (POST mint)

**Analog:** `triggarr/web/routes.py` lines 890–908 (`search_now` rate-limit pattern)

**Rate-limit pattern to copy verbatim, then adapt** (lines 890–908):
```python
    # Optimistic rate limit check BEFORE lock (fast-fail for obvious cases)
    rate_key = f"{app_name}_{instance_name}"
    now = time.monotonic()
    last = request.app.state.last_search_time.get(rate_key, 0.0)
    if now - last < SEARCH_RATE_LIMIT_SECONDS:
        logger.info("{name}/{inst}: Manual search rate-limited", name=app_name.title(), inst=instance_name)
        return HTMLResponse("Rate limited -- try again shortly", status_code=429)

    async with request.app.state.search_lock:
        # Re-check inside lock to prevent concurrent bypass (DRSEC-03)
        now = time.monotonic()
        last = request.app.state.last_search_time.get(rate_key, 0.0)
        if now - last < SEARCH_RATE_LIMIT_SECONDS:
            ...
            return HTMLResponse("Rate limited -- try again shortly", status_code=429)
        request.app.state.last_search_time[rate_key] = now
```

**Adaptations for `reset_request_post`:**
- `rate_key = "request"` (fixed string, not per-instance)
- `last_reset_time` instead of `last_search_time`
- `RESET_REQUEST_RATE_LIMIT_SECONDS` instead of `SEARCH_RATE_LIMIT_SECONDS`
- Inside the lock after timestamp update: mint token, store in `app.state`, log at `warning`, write token file via `run_in_executor(_write_reset_token_file, ...)`, return neutral HTML
- Token value NEVER in the HTML response body or context dict

**Token mint + store (inside lock, after rate-stamp update):**
```python
        token = generate_reset_token()
        request.app.state.reset_token = (token, time.monotonic() + 900)
        logger.warning("Password reset token minted. Read from docker logs or reset-token.txt in the config volume.")
        # D-17: log line first (operator can recover from log if file write fails)
        try:
            await asyncio.get_running_loop().run_in_executor(
                None, _write_reset_token_file, token_path, token
            )
        except OSError:
            pass  # already logged inside _write_reset_token_file; in-memory token is authority
```

---

### `triggarr/web/routes.py` — `reset_confirm_post` (POST apply)

**Analog:** `triggarr/web/routes.py` lines 1400–1488 (`change_password`) — primary analog; lines 1348–1360 (`login_post` cookie block)

**Full `change_password` apply block** (lines 1424–1488):
```python
    config_path = request.app.state.config_path
    async with request.app.state.search_lock:
        # Verify current password inside lock to prevent TOCTOU race (WR-01)
        current_settings = request.app.state.settings
        if not verify_password(current_password, current_settings.auth.password_hash.get_secret_value()):
            ...  # return error

        try:
            new_hash = hash_password(new_password)
        except ValueError:
            return templates.TemplateResponse(
                request=request,
                name="partials/security_password.html",
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

    _sync_auth_state(request.app.state.settings)
    _new_secrets = collect_secrets(request.app.state.settings)
    setup_logging(request.app.state.settings.general.log_level, _new_secrets)

    refreshed_username = request.app.state.settings.auth.username
    if refreshed_username:
        response.set_cookie(
            "triggarr_session",
            sign_session(refreshed_username, new_session_secret),
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=is_secure_request(request),
        )
```

**Cookie block from `login_post`** (lines 1351–1359):
```python
    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(
        "triggarr_session",
        sign_session(username, auth.session_secret.get_secret_value()),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=is_secure_request(request),
    )
```

**Adaptations for `reset_confirm_post` vs `change_password`:**

1. Rate-limit gate first (same double-check pattern as `reset_request_post`, using `"confirm"` key and `RESET_CONFIRM_RATE_LIMIT_SECONDS`). Optimistic check BEFORE lock; re-check INSIDE lock.
2. Pre-lock password field validation (non-empty, match) — same as `change_password` lines 1410–1422 — returns early with `errors` dict before acquiring the lock.
3. Replace current-password verify (lines 1427–1434) with token validation inside the lock:
   ```python
   stored = request.app.state.reset_token
   if stored is None or time.monotonic() >= stored[1] or not secrets.compare_digest(submitted_token, stored[0]):
       return templates.TemplateResponse(request=request, name="reset.html",
           context={"step": "confirm", "error": "Invalid or expired reset token"})
   ```
4. After `load_settings`, inside the lock — clear token and delete file:
   ```python
   request.app.state.reset_token = None
   try:
       (_runtime_config_dir(request) / "reset-token.txt").unlink(missing_ok=True)
   except OSError as exc:
       logger.warning("Failed to delete reset token file: {exc}", exc=exc)
   ```
5. Response is `RedirectResponse(url=request.url_for("dashboard"), status_code=303)` (not a `TemplateResponse`) with the cookie set on the redirect.
6. Cookie signed with captured `new_session_secret` local (not re-read from `app.state`) — ordering safety (Pitfall F in RESEARCH.md).

---

### `triggarr/web/routes.py` — `_write_reset_token_file` (private helper)

**Analog:** `triggarr/config.py` lines 95–163 (`_atomic_toml_write`)

**Full `_atomic_toml_write` pattern** (lines 95–163):
```python
def _atomic_toml_write(path: Path, data: dict) -> None:
    dir_fd = None
    renamed = False
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            tomli_w.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        renamed = True
        dir_fd = os.open(path.parent, os.O_RDONLY)
        os.fsync(dir_fd)
    except OSError as exc:
        if renamed:
            logger.warning("Config written but directory fsync failed: {path} - {exc}", path=path, exc=exc)
            return
        logger.error("Config write failed: {path} - {exc}", path=path, exc=exc)
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        except OSError as cleanup_exc:
            logger.error("Failed to clean up temp file {tmp} during config write: {exc}", tmp=tmp_path, exc=cleanup_exc)
        raise
    ...
    finally:
        if dir_fd is not None:
            os.close(dir_fd)
```

**Adaptation for `_write_reset_token_file(path: Path, token: str) -> None`:**
- Open fd in `"w"` (text) mode instead of `"wb"` (binary) — write `token` string directly with `f.write(token)`
- No `tomli_w.dump` — plain text write
- On `OSError` before rename: log at `error` with path and exception only — NEVER include `token` in the message (D-17)
- On `OSError` after rename (dir fsync): log at `warning` (same as `_atomic_toml_write`)
- After successful rename: call `os.chmod(path, 0o600)` (same position as in `change_password` after `os.replace`)
- Dispatch via `run_in_executor` from the route handler (same as `_atomic_toml_write`)
- `OSError` is NOT re-raised (D-17: in-memory token is the authority; file write failure is non-fatal)

---

### `tests/test_reset.py` (new file)

**Analog:** `tests/test_auth_routes.py` lines 1–113 (imports, helpers), 604–707 (session rotation tests), 1120–1133 (monkeypatch `time.monotonic`)

**Imports block to mirror** (test_auth_routes.py lines 17–43):
```python
from __future__ import annotations

import asyncio
import time
import tomllib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from pydantic import SecretStr

from triggarr.auth import generate_session_secret, hash_password, sign_session, validate_session
from triggarr.models.config import AuthConfig, GeneralConfig
from triggarr.models.config import Settings as SettingsModel
from triggarr.web.middleware import AuthMiddleware
from triggarr.web.routes import router, auth_state
```

**App-builder helper pattern** (test_auth_routes.py lines 82–108):
```python
def _make_route_app(auth_config: AuthConfig | None = None, config_path: Path | None = None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(router)
    static_dir = Path(__file__).resolve().parent.parent / "triggarr" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    cfg = auth_config or AuthConfig()
    settings = SettingsModel.model_construct(
        general=GeneralConfig(), auth=cfg, radarr={}, sonarr={}, lidarr={}
    )
    app.state.settings = settings
    app.state.config_path = config_path or Path("/tmp/test-triggarr.toml")
    app.state.search_lock = asyncio.Lock()
    auth_state["active"] = cfg.method in ("Forms", "Basic") and not cfg.needs_setup
    auth_state["method"] = cfg.method
    return app
```

**Adaptation — `_make_reset_app` wraps `_make_route_app` and adds Phase 72 fields:**
```python
def _make_reset_app(auth_config: AuthConfig | None = None, config_path: Path | None = None) -> FastAPI:
    app = _make_route_app(auth_config=auth_config, config_path=config_path)
    # Phase 72 app.state fields (not initialized by _make_route_app, which predates this phase)
    app.state.reset_token = None
    app.state.last_reset_time = {}
    return app
```

**Time injection for TTL tests** (test_auth_routes.py lines 1120–1133):
```python
    fake_time = 1000.0
    monkeypatch.setattr(time, "monotonic", lambda: fake_time)
```

**Cookie assertion helper** (test_auth_routes.py line 111–113):
```python
def _set_cookie_has_secure_attribute(set_cookie: str) -> bool:
    return "secure" in {part.strip().lower() for part in set_cookie.split(";")[1:]}
```

**Session rotation assertion pattern** (test_auth_routes.py lines 631–638):
```python
    persisted = tomllib.loads(config_file.read_text())
    new_secret = persisted["auth"]["session_secret"]
    assert new_secret != _TEST_SESSION_SECRET
    assert validate_session(old_cookie, new_secret) is None  # old cookie invalidated
```

**Redaction assertion pattern (new for Phase 72):**
```python
    assert token_value not in response.text
    assert token_value not in response.headers.get("set-cookie", "")
    assert token_value not in str(dict(response.headers))
```

**Rate-limit isolation:** Each test that checks rate-limiting should construct a fresh `_make_reset_app()` instance (fresh `app.state.last_reset_time = {}`). The `conftest.py` autouse fixtures only reset `_login_failures` via `_reset_rate_limiter()` — they do not touch `app.state.last_reset_time`, which is per-app-instance.

---

## Shared Patterns

### Rate-limit double-check (optimistic + locked)
**Source:** `triggarr/web/routes.py` lines 890–908 (`search_now`)
**Apply to:** `reset_request_post` and `reset_confirm_post`
```python
    rate_key = "request"   # or "confirm"
    now = time.monotonic()
    last = request.app.state.last_reset_time.get(rate_key, 0.0)
    if now - last < RESET_REQUEST_RATE_LIMIT_SECONDS:
        return HTMLResponse("Rate limited -- try again shortly", status_code=429)

    async with request.app.state.search_lock:
        now = time.monotonic()
        last = request.app.state.last_reset_time.get(rate_key, 0.0)
        if now - last < RESET_REQUEST_RATE_LIMIT_SECONDS:
            return HTMLResponse("Rate limited -- try again shortly", status_code=429)
        request.app.state.last_reset_time[rate_key] = now
        # ... proceed
```

### Session-secret rotation + post-lock refresh chain
**Source:** `triggarr/web/routes.py` lines 1449–1466 (`change_password`)
**Apply to:** `reset_confirm_post` (inside lock + after lock)
```python
        new_session_secret = generate_session_secret()
        new_auth = current_settings.auth.model_copy(
            update={"password_hash": SecretStr(new_hash), "session_secret": SecretStr(new_session_secret)}
        )
        updated = current_settings.model_copy(update={"auth": new_auth})
        config_dict = _settings_to_dict(updated)
        await asyncio.get_running_loop().run_in_executor(None, _atomic_toml_write, config_path, config_dict)
        os.chmod(config_path, 0o600)
        request.app.state.settings = load_settings(config_path)

    _sync_auth_state(request.app.state.settings)
    _new_secrets = collect_secrets(request.app.state.settings)
    setup_logging(request.app.state.settings.general.log_level, _new_secrets)
```

### Cookie re-issue with rotated secret
**Source:** `triggarr/web/routes.py` lines 1477–1486 (`change_password`), 1351–1359 (`login_post`)
**Apply to:** `reset_confirm_post` (auto-login redirect)
```python
    response = RedirectResponse(url=request.url_for("dashboard"), status_code=303)
    response.set_cookie(
        "triggarr_session",
        sign_session(refreshed_username, new_session_secret),  # captured local, not re-read from app.state
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=is_secure_request(request),
    )
    return response
```

### Atomic write + fsync + rename
**Source:** `triggarr/config.py` lines 95–163 (`_atomic_toml_write`)
**Apply to:** `_write_reset_token_file` helper (text write, not TOML; non-fatal OSError path per D-17)

### SecretStr wrapping on model_copy
**Source:** `triggarr/web/routes.py` lines 1450–1455 (`change_password`)
**Apply to:** `reset_confirm_post` — wrap `new_hash` and `new_session_secret` in `SecretStr` for `model_copy`:
```python
"password_hash": SecretStr(new_hash),
"session_secret": SecretStr(new_session_secret),
```

### Config-dir path helper
**Source:** `triggarr/web/routes.py` lines 95–97
**Apply to:** `reset_request_post` and `reset_confirm_post` for token-file path construction:
```python
def _runtime_config_dir(request: Request) -> Path:
    return Path(request.app.state.config_path).parent
```
Token file path: `_runtime_config_dir(request) / "reset-token.txt"`

---

## No Analog Found

No files in this phase lack a codebase analog. All patterns are directly mirrored from verified existing code.

---

## Metadata

**Analog search scope:** `triggarr/auth.py`, `triggarr/web/routes.py`, `triggarr/web/middleware.py`, `triggarr/config.py`, `triggarr/search/scheduler.py`, `tests/test_auth_routes.py`, `tests/conftest.py`
**Files scanned:** 7
**Pattern extraction date:** 2026-06-03
