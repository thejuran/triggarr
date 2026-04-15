# Phase 55: Auth Middleware & Health Endpoint - Pattern Map

**Mapped:** 2026-04-14
**Files analyzed:** 4 (3 modified, 1 new)
**Analogs found:** 4 / 4

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/web/middleware.py` (modify: add AuthMiddleware) | middleware | request-response | `triggarr/web/middleware.py` (OriginCheckMiddleware) | exact |
| `triggarr/__main__.py` (modify: register AuthMiddleware) | config | request-response | `triggarr/__main__.py` lines 67-68 | exact |
| `triggarr/web/routes.py` (modify: add /health endpoint) | route | request-response | `triggarr/web/routes.py` (existing route handlers) | exact |
| `tests/test_auth_middleware.py` (new) | test | request-response | `tests/test_middleware.py` | exact |

## Pattern Assignments

### `triggarr/web/middleware.py` -- add AuthMiddleware (middleware, request-response)

**Analog:** `triggarr/web/middleware.py` -- OriginCheckMiddleware (same file)

**Imports pattern** (lines 1-9):
```python
"""Security middleware for Triggarr web server."""

from __future__ import annotations

from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
```

**Core middleware dispatch pattern** (lines 28-53, OriginCheckMiddleware):
```python
class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Reject cross-origin mutating requests via Origin/Referer header validation.
    ...
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Check Origin/Referer on mutating requests, pass through otherwise."""
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            host = request.headers.get("host", "")

            if origin:
                if urlparse(origin).netloc != host:
                    return Response("Forbidden", status_code=403)
            elif referer and urlparse(referer).netloc != host:
                return Response("Forbidden", status_code=403)

        return await call_next(request)
```

Key patterns to copy:
- Class extends `BaseHTTPMiddleware`
- Single `async def dispatch(self, request, call_next) -> Response` method
- Early return for rejection cases, `await call_next(request)` for pass-through
- Docstring on class and dispatch method
- Import `Response` from `starlette.responses` (not FastAPI)

**Auth helpers to consume** (from `triggarr/auth.py` lines 1-10, 70-106):
```python
from triggarr.auth import COOKIE_MAX_AGE, sign_session, validate_session, verify_password

# validate_session(cookie_value: str | None, secret: str) -> str | None
# verify_password(plaintext: str, hashed: str) -> bool
# sign_session(username: str, secret: str) -> str
# COOKIE_MAX_AGE = 30 * 24 * 60 * 60  (30 days)
```

**Config access pattern** (from `triggarr/search/scheduler.py` line 202):
```python
# Settings are set on app.state during lifespan:
app.state.settings = settings

# In middleware, access via:
auth = request.app.state.settings.auth
# auth is AuthConfig with properties: needs_setup, is_disabled, method, username, password_hash, api_key, session_secret
```

**AuthConfig model** (from `triggarr/models/config.py` lines 83-104):
```python
class AuthConfig(BaseModel):
    method: Literal["Forms", "Basic", "External", "Disabled"] = "Forms"
    username: str = ""
    password_hash: SecretStr = SecretStr("")
    api_key: SecretStr = SecretStr("")
    session_secret: SecretStr = SecretStr("")

    @property
    def needs_setup(self) -> bool:
        return not self.username

    @property
    def is_disabled(self) -> bool:
        return self.method == "Disabled"
```

**SecretStr access pattern** -- only call `.get_secret_value()` at point of use:
```python
# API key comparison (timing-safe):
secrets.compare_digest(api_key_header, auth.api_key.get_secret_value())

# Session cookie validation:
validate_session(cookie, auth.session_secret.get_secret_value())

# Password verification:
verify_password(password, auth.password_hash.get_secret_value())

# Session signing:
sign_session(username, auth.session_secret.get_secret_value())
```

---

### `triggarr/__main__.py` -- register AuthMiddleware (config, request-response)

**Analog:** `triggarr/__main__.py` lines 16-17, 67-68

**Import pattern** (line 16):
```python
from triggarr.web.middleware import OriginCheckMiddleware, SecurityHeadersMiddleware
```

**Registration pattern** (lines 67-68):
```python
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(OriginCheckMiddleware)
```

AuthMiddleware must be registered LAST (runs first due to Starlette reverse order):
```python
app.add_middleware(SecurityHeadersMiddleware)   # runs 3rd
app.add_middleware(OriginCheckMiddleware)        # runs 2nd
app.add_middleware(AuthMiddleware)               # runs 1st -- MUST BE LAST
```

---

### `triggarr/web/routes.py` -- add /health endpoint (route, request-response)

**Analog:** `triggarr/web/routes.py` (existing route handlers)

**Router setup pattern** (lines 1-26):
```python
from __future__ import annotations
# ... imports ...
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

router = APIRouter()
```

**Route handler pattern** -- simple JSON endpoint:
```python
@router.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint for uptime monitors."""
    return JSONResponse({"status": "ok"})
```

---

### `tests/test_auth_middleware.py` (new test file)

**Analog:** `tests/test_middleware.py`

**Imports pattern** (lines 1-12):
```python
"""Test suite for Origin/Referer CSRF middleware.
...
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from triggarr.web.middleware import OriginCheckMiddleware
```

**Test app factory pattern** (lines 15-28):
```python
def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with OriginCheckMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(OriginCheckMiddleware)

    @app.post("/test")
    async def post_endpoint():
        return {"status": "ok"}

    @app.get("/test")
    async def get_endpoint():
        return {"status": "ok"}

    return app


client = TestClient(_make_app())
```

**Integration test app factory with mock state** (lines 90-140):
```python
def _make_settings_app() -> FastAPI:
    """Build a FastAPI app with router + middleware, mimicking real app wiring."""
    from unittest.mock import MagicMock
    # ...
    app = FastAPI()
    app.add_middleware(OriginCheckMiddleware)
    # ...
    mock_settings = MagicMock()
    # set up mock_settings fields...
    app.state.settings = mock_settings
    # ...
    return app
```

**Test function pattern** (lines 34-41):
```python
def test_post_matching_origin_passes():
    """POST with Origin matching Host should return 200."""
    response = client.post(
        "/test",
        headers={"Origin": "http://testserver", "Host": "testserver"},
    )
    assert response.status_code == 200
```

For AuthMiddleware tests, the factory should accept an `AuthConfig` parameter:
```python
from unittest.mock import MagicMock
from triggarr.models.config import AuthConfig
from triggarr.web.middleware import AuthMiddleware

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

    return app
```

---

## Shared Patterns

### Starlette Middleware Base Class
**Source:** `triggarr/web/middleware.py` lines 7, 12-25
**Apply to:** AuthMiddleware class

All middleware in this project:
- Extends `BaseHTTPMiddleware`
- Implements `async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response`
- Uses early `return Response(...)` for rejection
- Uses `return await call_next(request)` for pass-through

### SecretStr Discipline
**Source:** `triggarr/models/config.py` lines 92-94 (AuthConfig field definitions)
**Apply to:** AuthMiddleware (all secret comparisons)

- Never log SecretStr values
- Call `.get_secret_value()` only at the exact point of comparison/use
- Use `secrets.compare_digest()` for API key comparison (timing-safe)

### Error Response Convention
**Source:** `triggarr/web/middleware.py` line 48
**Apply to:** AuthMiddleware rejection responses

- Use `starlette.responses.Response` for simple text responses (403)
- Use `starlette.responses.JSONResponse` for structured JSON error payloads (401)
- Use `starlette.responses.RedirectResponse` for browser redirects (302)

### Test App Factory Pattern
**Source:** `tests/test_middleware.py` lines 15-28
**Apply to:** `tests/test_auth_middleware.py`

- Create minimal FastAPI app in a factory function
- Add only the middleware under test
- Define inline route handlers (no real router)
- Use `TestClient` for synchronous test requests
- Mock `app.state.settings` with `MagicMock` for integration tests

## No Analog Found

No files in this phase lack an analog. All four files have exact matches in the existing codebase.

## Metadata

**Analog search scope:** `triggarr/web/`, `triggarr/`, `tests/`
**Files scanned:** 6 (middleware.py, __main__.py, routes.py, auth.py, config.py, test_middleware.py)
**Pattern extraction date:** 2026-04-14
