# Phase 58: Auth Test Suite - Pattern Map

**Mapped:** 2026-04-15
**Files analyzed:** 5 (4 existing gap-fill + 1 new)
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tests/test_auth_middleware.py` (gap-fill) | test | request-response | self (existing file) | exact |
| `tests/test_auth_routes.py` (gap-fill) | test | request-response | self (existing file) | exact |
| `tests/test_auth_config.py` (gap-fill) | test | transform | self (existing file) | exact |
| `tests/test_auth_helpers.py` (gap-fill) | test | transform | self (existing file) | exact |
| `tests/test_auth_integration.py` (NEW) | test | request-response | `tests/test_auth_routes.py` | exact |

## Pattern Assignments

### `tests/test_auth_middleware.py` (test, request-response) -- GAP-FILL

**Analog:** self -- append new tests following existing patterns

**Imports pattern** (lines 1-20):
```python
from __future__ import annotations

import base64
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from triggarr.auth import generate_session_secret, hash_password, sign_session
from triggarr.models.config import AuthConfig
from triggarr.web.middleware import AuthMiddleware
```

**App factory pattern** (lines 22-51):
```python
def _make_auth_app(auth_config: AuthConfig | None = None) -> FastAPI:
    """Build a minimal FastAPI app with AuthMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    settings = MagicMock()
    settings.auth = auth_config or AuthConfig()
    app.state.settings = settings

    @app.get("/")
    async def index():
        return {"page": "home"}

    @app.get("/health")
    async def health():
        return {"status": "ok"}
    # ... stub routes for /static, /login, /setup
    return app
```

**Credential fixtures pattern** (lines 58-89):
```python
_SESSION_SECRET = generate_session_secret()
_PASSWORD = "test-password-123"
_PASSWORD_HASH = hash_password(_PASSWORD)
_API_KEY = "abcdef1234567890abcdef1234567890"

def _configured_auth(
    method: str = "Forms",
    username: str = "admin",
    password_hash: str = _PASSWORD_HASH,
    api_key: str = _API_KEY,
    session_secret: str = _SESSION_SECRET,
) -> AuthConfig:
    return AuthConfig(
        method=method, username=username,
        password_hash=SecretStr(password_hash),
        api_key=SecretStr(api_key),
        session_secret=SecretStr(session_secret),
    )

def _valid_session_cookie() -> str:
    return sign_session("admin", _SESSION_SECRET)

def _basic_auth_header(username: str = "admin", password: str = _PASSWORD) -> str:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {encoded}"
```

**Test function pattern -- middleware assertion** (lines 97-101):
```python
def test_health_no_auth():
    """GET /health passes through without authentication (exempt path)."""
    client = TestClient(_make_auth_app())
    response = client.get("/health")
    assert response.status_code == 200
```

**Test function pattern -- redirect assertion** (lines 287-294):
```python
def test_unauth_browser_redirects_to_login():
    """Unauthenticated browser request to protected route gets 302 to /login."""
    auth = _configured_auth()
    client = TestClient(_make_auth_app(auth), follow_redirects=False)
    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 302
    assert response.headers["location"] == "/login?next=/"
```

**Test function pattern -- cookie-based auth** (lines 182-189):
```python
def test_valid_session_cookie_passes_through():
    """Request with valid session cookie passes through regardless of method."""
    auth = _configured_auth()
    client = TestClient(_make_auth_app(auth))
    cookie = _valid_session_cookie()
    response = client.get("/", cookies={"triggarr_session": cookie})
    assert response.status_code == 200
    assert response.json() == {"page": "home"}
```

---

### `tests/test_auth_routes.py` (test, request-response) -- GAP-FILL

**Analog:** self -- append new tests following existing patterns

**Imports pattern** (lines 1-29):
```python
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

**Auth state reset fixture** (lines 31-37):
```python
@pytest.fixture(autouse=True)
def _reset_auth_state():
    """Reset module-level auth_state between tests to prevent order dependency."""
    original = dict(auth_state)
    yield
    auth_state.clear()
    auth_state.update(original)
```

**Full app factory with real routes** (lines 67-93):
```python
def _make_route_app(auth_config: AuthConfig | None = None, config_path: Path | None = None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(router)

    static_dir = Path(__file__).resolve().parent.parent / "triggarr" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    cfg = auth_config or AuthConfig()
    settings = SettingsModel.model_construct(
        general=GeneralConfig(), auth=cfg,
        radarr={}, sonarr={}, lidarr={},
    )
    app.state.settings = settings
    app.state.config_path = config_path or Path("/tmp/test-triggarr.toml")
    app.state.search_lock = asyncio.Lock()

    auth_state["active"] = cfg.method in ("Forms", "Basic") and not cfg.needs_setup
    auth_state["method"] = cfg.method
    return app
```

**Route integration test pattern -- POST with tmp_path** (lines 245-266):
```python
def test_setup_post_creates_credentials(tmp_path: Path):
    """POST /setup with valid credentials creates account and shows API key."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text("[general]\nlog_level = \"info\"\n")

    app = _make_route_app(config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    response = client.post(
        "/setup",
        data={"username": "admin", "password": "test123", "confirm_password": "test123"},
    )
    assert response.status_code == 200
    assert "Account Created" in response.text
```

**Route integration test pattern -- authenticated request** (lines 434-456):
```python
def test_change_password_success(tmp_path: Path):
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')

    auth_cfg = _configured_auth()
    app = _make_route_app(auth_config=auth_cfg, config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    cookie = sign_session("admin", _TEST_SESSION_SECRET)

    response = client.post(
        "/settings/password",
        data={...},
        cookies={"triggarr_session": cookie},
    )
    assert response.status_code == 200
    assert "Password updated" in response.text
```

---

### `tests/test_auth_config.py` (test, transform) -- GAP-FILL

**Analog:** self -- append traceability comment block only

**Imports pattern** (lines 1-9):
```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from triggarr.models.config import AuthConfig, Settings
from triggarr.startup import collect_secrets
```

**Test function pattern -- model validation** (lines 16-19):
```python
def test_auth_config_default_method() -> None:
    """AuthConfig defaults to Forms method."""
    assert AuthConfig().method == "Forms"
```

---

### `tests/test_auth_helpers.py` (test, transform) -- GAP-FILL

**Analog:** self -- append traceability comment block only

**Imports pattern** (lines 1-15):
```python
from __future__ import annotations

import re

from triggarr.auth import (
    COOKIE_MAX_AGE,
    generate_api_key,
    generate_session_secret,
    hash_password,
    sign_session,
    validate_session,
    verify_password,
)
```

**Test function pattern -- crypto helper assertion** (lines 33-36):
```python
def test_hash_password_returns_bcrypt_hash() -> None:
    """hash_password returns a bcrypt hash string starting with $2b$12$."""
    hashed = hash_password("mypassword")
    assert hashed.startswith("$2b$12$")
```

**Test function pattern -- time-based expiry with mock** (lines 146-164):
```python
def test_validate_session_expired_returns_none() -> None:
    """validate_session rejects an expired cookie (>30 days)."""
    from unittest.mock import patch
    from itsdangerous import TimestampSigner

    secret = generate_session_secret()
    signed = sign_session("admin", secret)

    original_get_timestamp = TimestampSigner.get_timestamp

    def future_timestamp(self: TimestampSigner) -> int:
        return original_get_timestamp(self) + (31 * 24 * 60 * 60)

    with patch.object(TimestampSigner, "get_timestamp", future_timestamp):
        result = validate_session(signed, secret)
    assert result is None
```

---

### `tests/test_auth_integration.py` (test, request-response) -- NEW FILE

**Analog:** `tests/test_auth_routes.py`

**Imports to copy** (adapted from test_auth_routes.py lines 1-29):
```python
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from pydantic import SecretStr

from triggarr.auth import generate_session_secret, hash_password, sign_session
from triggarr.models.config import AuthConfig, GeneralConfig
from triggarr.models.config import Settings as SettingsModel
from triggarr.web.middleware import AuthMiddleware
from triggarr.web.routes import auth_state, router
```

**MUST include auth_state reset fixture** (from test_auth_routes.py lines 31-37):
```python
@pytest.fixture(autouse=True)
def _reset_auth_state():
    """Reset module-level auth_state between tests to prevent order dependency."""
    original = dict(auth_state)
    yield
    auth_state.clear()
    auth_state.update(original)
```

**MUST reuse _make_route_app pattern** (from test_auth_routes.py lines 67-93):
Copy or import `_make_route_app`. Since it is a module-level function (not exported), duplicate it in this file with identical logic. Also duplicate `_configured_auth` and credential constants.

**Integration test flow pattern** (from test_auth_routes.py lines 245-266, adapted for multi-step):
```python
def test_full_setup_login_use_logout_flow(tmp_path: Path):
    """Complete flow: setup -> login -> access protected -> logout -> denied."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')
    app = _make_route_app(config_path=config_file)
    client = TestClient(app, follow_redirects=False)

    # Step 1: Setup
    resp = client.post("/setup", data={...})
    assert resp.status_code == 200
    session_cookie = resp.cookies.get("triggarr_session")

    # Step 2: Access protected route with session
    resp = client.get("/", cookies={"triggarr_session": session_cookie})
    assert resp.status_code == 200

    # Step 3: Logout
    resp = client.post("/logout", cookies={"triggarr_session": session_cookie})
    assert resp.status_code == 303

    # Step 4: Access denied
    resp = client.get("/", headers={"Accept": "text/html"})
    assert resp.status_code == 302
```

---

## Shared Patterns

### Traceability Comment Block (D-03)
**Apply to:** ALL 5 test files (prepend to existing docstring or add as new block)
```python
"""Tests for [module] -- Phase 58 gap-fill.

Traceability:
  SC-1 (middleware enforcement): test_health_returns_ok_body, ...
  SC-3 (session lifecycle): test_wrong_secret_cookie_rejected_by_middleware, ...
  SC-5 (API key auth): test_empty_api_key_does_not_pass, ...
"""
```

### TestClient with follow_redirects=False
**Source:** `tests/test_auth_middleware.py` line 133, `tests/test_auth_routes.py` line 231
**Apply to:** ALL tests that assert redirect behavior (302/303)
```python
client = TestClient(_make_auth_app(auth), follow_redirects=False)
```

### Credential Fixture Pattern
**Source:** `tests/test_auth_middleware.py` lines 58-78
**Apply to:** `test_auth_integration.py` (must duplicate, not import -- module-level functions)
```python
_SESSION_SECRET = generate_session_secret()
_PASSWORD = "test-password-123"
_PASSWORD_HASH = hash_password(_PASSWORD)
_API_KEY = "abcdef1234567890abcdef1234567890"

def _configured_auth(method="Forms", username="admin", ...) -> AuthConfig:
    return AuthConfig(method=method, username=username,
        password_hash=SecretStr(password_hash), api_key=SecretStr(api_key),
        session_secret=SecretStr(session_secret))
```

### Auth State Cleanup
**Source:** `tests/test_auth_routes.py` lines 31-37
**Apply to:** `test_auth_integration.py` (MANDATORY -- prevents test pollution)
```python
@pytest.fixture(autouse=True)
def _reset_auth_state():
    original = dict(auth_state)
    yield
    auth_state.clear()
    auth_state.update(original)
```

### tmp_path for TOML Config
**Source:** `tests/test_auth_routes.py` lines 245-249
**Apply to:** Any test that triggers config writes (setup POST, password change, security save, integration flows)
```python
def test_something(tmp_path: Path):
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')
    app = _make_route_app(config_path=config_file)
```

### JSON vs HTML Response Detection
**Source:** `tests/test_auth_middleware.py` lines 287-302
**Apply to:** API key tests, middleware edge case tests
```python
# Browser request (expects redirect):
response = client.get("/", headers={"Accept": "text/html"})
assert response.status_code == 302

# API request (expects JSON 401):
response = client.get("/", headers={"Accept": "application/json"})
assert response.status_code == 401
assert response.json() == {"detail": "Authentication required"}
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | -- | -- | All files have exact analogs in existing test suite |

## Metadata

**Analog search scope:** `tests/` directory
**Files scanned:** 5 test files + conftest.py
**Pattern extraction date:** 2026-04-15
