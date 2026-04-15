# Phase 59: Security Hardening - Pattern Map

**Mapped:** 2026-04-15
**Files analyzed:** 8 modified + 1 new
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/web/middleware.py` | middleware | request-response | Self (existing code) | exact |
| `triggarr/web/routes.py` | controller | request-response | Self (existing code) | exact |
| `triggarr/web/validation.py` | utility | transform | Self (existing code) | exact |
| `triggarr/templates/partials/security_apikey.html` | component | request-response | Self (existing code) | exact |
| `triggarr/changelog.py` | utility | transform | Self (existing code) | exact |
| `tests/conftest.py` | config | test-infra | Self (existing code) | exact |
| `tests/test_auth_middleware.py` | test | request-response | Self (existing tests) | exact |
| `tests/test_auth_routes.py` | test | request-response | Self (existing tests) | exact |
| `tests/test_validation.py` | test | transform | Self (existing tests) | exact |
| `.gitleaksignore` | config | N/A | None (new file) | N/A |

## Pattern Assignments

### `triggarr/web/middleware.py` (middleware, request-response)

**Analog:** Self -- all changes extend existing middleware classes.

**SecurityHeadersMiddleware -- CSP header addition** (lines 30-36):
```python
async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
    """Add security headers to the response."""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response
```
Pattern: Add `response.headers["Content-Security-Policy"] = ...` in the same block. Also update `X-Frame-Options` from `SAMEORIGIN` to `DENY` to match CSP `frame-ancestors 'none'`.

**AuthMiddleware -- disabled warning pattern** (lines 82, 100-108):
```python
_disabled_warned: bool = False

# In dispatch:
if auth.is_disabled:
    if not AuthMiddleware._disabled_warned:
        logger.warning(
            "Authentication is disabled -- all requests are unauthenticated. "
            "Set auth.method in triggarr.toml to enable."
        )
        AuthMiddleware._disabled_warned = True
    return await call_next(request)
```
Pattern: Replace `_disabled_warned: bool` with `_disabled_warned_at: float = 0.0`. Use `time.monotonic()` comparison with 60-second interval. Add `import time` to imports.

---

### `triggarr/web/routes.py` (controller, request-response)

**Analog:** Self -- modifications to existing route handlers.

**Imports pattern** (lines 1-25):
```python
from __future__ import annotations

import asyncio
import html
import os
import re
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import httpx
import jinja2
import pydantic
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
```
Note: `time` and `secrets` are already imported. No new imports needed for rate limiter.

**Login POST handler -- rate limiter insertion point** (lines 1126-1167):
```python
@router.post("/login", response_model=None)
async def login_post(request: Request) -> HTMLResponse | RedirectResponse:
    """Authenticate credentials, set session cookie, redirect to ?next= or dashboard."""
    auth = request.app.state.settings.auth
    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")
    next_url = form.get("next", "")

    # Verify credentials
    if (
        username
        and password
        and secrets.compare_digest(username, auth.username)
        and verify_password(password, auth.password_hash.get_secret_value())
    ):
        # Success path ...
        return response

    # Failure: re-render with error (D-04)
    logger.warning("Login failed for user {username}", username=username)
    return templates.TemplateResponse(...)
```
Pattern: Add rate limit check BEFORE credential verification. On rate limit hit, return `templates.TemplateResponse` with error message (same pattern as failure path at line 1159). Record failure AFTER failed auth. Module-level dict + helper functions above the route handler.

**Login failure log sanitization** (line 1158):
```python
logger.warning("Login failed for user {username}", username=username)
```
Replace with:
```python
logger.warning(
    "Login failed: username_match={matched}",
    matched=bool(username and secrets.compare_digest(username, auth.username)),
)
```
Pattern: Uses existing `secrets.compare_digest` already at line 1139. Same timing-safe comparison.

**Setup completion log sanitization** (line 1099):
```python
logger.info("Setup completed for user {username}", username=username)
```
Replace with:
```python
logger.info("Setup completed")
```

**Settings page API key exposure** (line 401):
```python
"auth_api_key": settings.auth.api_key.get_secret_value(),
```
Replace with:
```python
"auth_api_key_set": bool(settings.auth.api_key.get_secret_value()),
```
Pattern: Context dict at lines 389-403. Change key name and value type from str to bool.

---

### `triggarr/web/validation.py` (utility, transform)

**Analog:** Self -- extend existing `validate_arr_url`.

**Current IP check pattern** (lines 80-85):
```python
try:
    addr = ipaddress.ip_address(hostname)
    if addr.is_link_local or addr.is_loopback or addr.is_unspecified:
        return (False, "Blocked address")
except ValueError:
    # Not an IP literal (e.g. "radarr") -- perfectly fine.
    pass
```
Pattern: After the existing check, add `is_multicast` to the existing condition. Then add IPv4-mapped IPv6 check:
```python
if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
    mapped = addr.ipv4_mapped
    if mapped.is_link_local or mapped.is_loopback or mapped.is_unspecified or mapped.is_multicast:
        return (False, "Blocked address")
```
Note: `ipaddress` is already imported at line 9.

---

### `triggarr/templates/partials/security_apikey.html` (component, request-response)

**Analog:** Self -- existing template partial.

**Current non-revealed path** (lines 4-5):
```jinja2
{% else %}
  {% set display_key = auth_api_key if auth_api_key is defined else "" %}
```
Pattern: Change to use `auth_api_key_set` boolean. When set but not revealed, show masked placeholder (`"********************************"`). When not set, show empty. Hide copy/eye-toggle buttons when key is not revealed (key value is just asterisks, not the real key).

**Revealed path** (lines 2-3) -- UNCHANGED:
```jinja2
{% if is_revealed and api_key is defined %}
  {% set display_key = api_key %}
```
This path uses `api_key` from the regen endpoint, not `auth_api_key`. No change needed here.

---

### `triggarr/changelog.py` (utility, transform)

**Analog:** Self -- comment-only change.

**Current docstring** (lines 70-77):
```python
def parse_changelog(text: str, *, latest_only: bool = False) -> str:
    """Parse changelog markdown text into HTML.

    Handles:
    - ``## vX.Y.Z (date)`` -> version header
    - ``* Category:`` -> category subheading
    - ``  * Item text`` -> bullet list item
    """
```
Pattern: Extend docstring with security boundary documentation per D-15. Reference `html.escape()` calls at lines 101, 112, 124 as the XSS defense.

---

### `tests/conftest.py` (config, test-infra)

**Analog:** Self -- existing autouse fixture.

**Current fixture** (lines 12-17):
```python
@pytest.fixture(autouse=True)
def _reset_disabled_warned():
    """Reset AuthMiddleware._disabled_warned before each test to avoid order-dependent failures."""
    AuthMiddleware._disabled_warned = False
    yield
    AuthMiddleware._disabled_warned = False
```
Pattern: Update to reset `_disabled_warned_at = 0.0`. Add a second autouse fixture to clear the rate limiter dict (import the dict or a `_reset_rate_limiter()` helper from routes.py).

---

### `tests/test_auth_middleware.py` (test, request-response)

**Analog:** Self -- existing test patterns.

**Disabled mode warning test** (lines 480-487):
```python
def test_disabled_mode_logs_warning():
    """Disabled mode logs a warning at startup (first request)."""
    auth = _configured_auth(method="Disabled")
    client = TestClient(_make_auth_app(auth))
    with patch("triggarr.web.middleware.logger") as mock_logger:
        client.get("/")
        mock_logger.warning.assert_called_once()
        assert "disabled" in mock_logger.warning.call_args.args[0].lower()
```
Pattern: Update for periodic warning -- may fire more than once. Test that warning fires on first request, then does NOT fire again within 60s, then fires again after interval. Use `patch("triggarr.web.middleware.time")` to control monotonic clock.

**CSP header test pattern** -- use `tests/test_middleware.py` as analog (lines 15-31):
```python
def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with OriginCheckMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(OriginCheckMiddleware)

    @app.post("/test")
    async def post_endpoint():
        return {"status": "ok"}

    return app

client = TestClient(_make_app())
```
Pattern: Same `_make_app()` + `TestClient` pattern. Add `SecurityHeadersMiddleware` and assert `response.headers["Content-Security-Policy"]` contains expected directives.

---

### `tests/test_auth_routes.py` (test, request-response)

**Analog:** Self -- existing test patterns.

**Test file structure** (lines 1-34):
```python
"""Auth route handler tests -- includes Phase 58 gap-fill."""
from __future__ import annotations

import asyncio
import re
import tomllib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from pydantic import SecretStr

from triggarr.auth import generate_session_secret, hash_password, sign_session
from triggarr.models.config import AuthConfig, GeneralConfig, InstanceConfig
from triggarr.models.config import Settings as SettingsModel
from triggarr.web.middleware import AuthMiddleware
from triggarr.web.routes import _safe_next_url, _settings_to_dict, auth_state, router
```
Pattern: New rate limiter tests follow existing structure -- use existing `_make_app()` helper (or equivalent) to create test client, POST to `/login` with bad credentials, assert behavior.

---

### `tests/test_validation.py` (test, transform)

**Analog:** Self -- existing test class.

**Existing SSRF test pattern** (lines 11-50):
```python
class TestValidateArrUrl:
    """URL validation: scheme enforcement, SSRF blocking, private-IP allow."""

    def test_valid_http_url(self) -> None:
        ok, err = validate_arr_url("http://radarr:7878")
        assert ok is True
        assert err == ""

    def test_link_local_ip_blocked(self) -> None:
        ok, err = validate_arr_url("http://169.254.42.42")
        assert ok is False
        assert "blocked" in err.lower()
```
Pattern: Add tests in same class. Call `validate_arr_url("http://[::ffff:127.0.0.1]:7878")` and assert blocked. Same `(ok, err)` tuple assertion pattern.

---

### `.gitleaksignore` (config, N/A)

**Analog:** None -- new file at repository root.

**Content pattern:** One file path per line, with comment header explaining purpose.
```
# Test fixture API keys -- not real credentials
tests/test_auth_middleware.py
tests/test_auth_routes.py
tests/test_auth_integration.py
tests/test_auth_config.py
```

## Shared Patterns

### Logging (Loguru)
**Source:** `triggarr/web/routes.py` (throughout) and `triggarr/web/middleware.py` (line 103)
**Apply to:** All modified files with logging changes
```python
from loguru import logger

# Structured logging with keyword args (Loguru format)
logger.warning("Login failed: username_match={matched}", matched=bool(...))
logger.info("Setup completed")
logger.warning("Authentication is disabled -- ...")
```
Convention: Loguru with `{}` placeholders and keyword arguments. Never include user-controlled input directly in log messages (this is the fix for SHIELD-005/011).

### Error Response Rendering
**Source:** `triggarr/web/routes.py` lines 1159-1166
**Apply to:** Rate limiter 429 response
```python
return templates.TemplateResponse(
    request=request,
    name="login.html",
    context={
        "error": "Invalid username or password",
        "username": username,
        "next_url": _safe_next_url(next_url) if next_url else "",
    },
)
```
Pattern: Rate limit rejection should use the same `TemplateResponse` with `login.html` and an error message in context. Same structure, different error text.

### SecretStr Discipline
**Source:** `triggarr/web/routes.py` line 401, `triggarr/web/middleware.py` line 122
**Apply to:** API key exposure fix
```python
# CURRENT (violates SecretStr discipline -- passes raw value to template):
"auth_api_key": settings.auth.api_key.get_secret_value(),

# FIX (passes boolean only):
"auth_api_key_set": bool(settings.auth.api_key.get_secret_value()),
```
Convention from CLAUDE.md: "SecretStr for all API keys -- call `.get_secret_value()` only at HTTP client init."

### Test Structure
**Source:** `tests/test_middleware.py` lines 15-31, `tests/test_validation.py` lines 11-50
**Apply to:** All new tests
```python
# Middleware tests: _make_app() + TestClient pattern
def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SomeMiddleware)
    @app.get("/test")
    async def endpoint():
        return {"status": "ok"}
    return app

client = TestClient(_make_app())

# Validation tests: direct function call, assert (ok, err) tuple
class TestValidateArrUrl:
    def test_something_blocked(self) -> None:
        ok, err = validate_arr_url("http://...")
        assert ok is False
        assert "blocked" in err.lower()
```

### Test Fixture Reset
**Source:** `tests/conftest.py` lines 12-17
**Apply to:** New rate limiter state, updated disabled warning state
```python
@pytest.fixture(autouse=True)
def _reset_disabled_warned():
    """Reset AuthMiddleware._disabled_warned before each test."""
    AuthMiddleware._disabled_warned = False
    yield
    AuthMiddleware._disabled_warned = False
```
Pattern: Autouse fixture that resets module-level state before and after each test. Same pattern for rate limiter dict.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.gitleaksignore` | config | N/A | New file type not present in repo. Use simple line-per-file format from RESEARCH.md. |

## Metadata

**Analog search scope:** `triggarr/web/`, `triggarr/`, `tests/`, project root
**Files scanned:** 14
**Pattern extraction date:** 2026-04-15
