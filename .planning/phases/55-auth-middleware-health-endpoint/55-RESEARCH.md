# Phase 55: Auth Middleware & Health Endpoint - Research

**Researched:** 2026-04-14
**Domain:** FastAPI/Starlette middleware, authentication enforcement, HTTP auth patterns
**Confidence:** HIGH

## Summary

This phase adds a deny-all authentication middleware to Triggarr's FastAPI application that gates every route by default, with an explicit whitelist for exempt paths (`/health`, `/static`, `/login`, `/setup`). The middleware must handle five distinct auth modes (needs-setup redirect, Disabled passthrough, External passthrough, session cookie, API key, Basic auth) in a defined priority order, and differentiate browser vs API clients for response formatting (302 redirect vs 401 JSON).

All building blocks already exist: `validate_session()`, `verify_password()`, `sign_session()` in `triggarr/auth.py`; `AuthConfig` with `needs_setup`/`is_disabled` properties in `triggarr/models/config.py`; settings already exposed on `app.state.settings` via the lifespan in `triggarr/search/scheduler.py` (line 202). The existing `SecurityHeadersMiddleware` and `OriginCheckMiddleware` in `triggarr/web/middleware.py` provide the exact pattern to follow. The health endpoint is a trivial 2-line route addition to `triggarr/web/routes.py`.

**Primary recommendation:** Implement `AuthMiddleware` as a `BaseHTTPMiddleware` subclass in the existing `triggarr/web/middleware.py`, following the established pattern. Register it in `__main__.py` as the outermost middleware (added last, runs first). Add `/health` as a simple GET route in `routes.py`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** AuthMiddleware class lives in `triggarr/web/middleware.py` alongside existing SecurityHeadersMiddleware and OriginCheckMiddleware. One file, all middleware.
- **D-02:** Config access via `request.app.state.settings.auth` -- store settings on `app.state` during startup. Matches FastAPI convention, allows config to update if settings are reloaded.
- **D-03:** AuthMiddleware handles both authentication enforcement AND first-run setup redirect. Single enforcement point -- impossible to miss a route.
- **D-04:** When `auth.needs_setup` is true, browser requests to non-exempt routes get 302 redirect to `/setup`. API requests (non-browser) get 401 JSON: `{"detail": "Setup required", "setup_url": "/setup"}`.
- **D-05:** `/setup` stays in the exempt whitelist permanently. The route handler (Phase 56) checks `auth.needs_setup` and returns 404 if setup is already complete. Middleware doesn't need to know setup state for whitelist logic.
- **D-06:** `GET /health` returns minimal `{"status": "ok"}` with 200. No version, no instance health, no uptime -- uptime monitors only need a 200 response.
- **D-07:** Health route lives in existing `triggarr/web/routes.py`. It's a 2-line function, no separate file needed.
- **D-08:** Middleware validates Basic auth credentials inline -- decodes `Authorization: Basic` header, calls `verify_password()` directly, sets session cookie on the response if valid. No redirect to /login needed.
- **D-09:** Valid session cookie takes priority over auth mode. If a user has a valid session cookie, they're authenticated regardless of whether mode is Forms or Basic. Avoids re-prompting after first Basic auth.
- **D-10:** Middleware check order for non-exempt paths: (1) needs_setup -> setup redirect/401, (2) is_disabled -> pass, (3) External -> pass, (4) valid session cookie -> pass, (5) valid X-Api-Key -> pass, (6) Basic mode -> check Authorization header, validate, set cookie if valid, or 401 with WWW-Authenticate, (7) else -> redirect to /login (browser) or 401 JSON (API).

### Claude's Discretion
- Exact middleware class structure (single dispatch method vs helper methods for each check)
- Whether to use Starlette's BaseHTTPMiddleware or pure ASGI middleware
- Error response JSON structure beyond the minimum fields specified
- How to attach settings to app.state (lifespan vs startup event)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MID-01 | All routes require authentication by default (deny-all middleware with path whitelist) | BaseHTTPMiddleware with EXEMPT_PREFIXES tuple; registered as outermost middleware in `__main__.py` |
| MID-02 | User can authenticate API requests via `X-Api-Key` header | `secrets.compare_digest()` against `auth.api_key.get_secret_value()`; check at step 5 in D-10 order |
| MID-03 | `GET /health` returns `{"status": "ok"}` without authentication | Simple GET route in `routes.py`; path `/health` in EXEMPT_PREFIXES |
| MID-04 | Unauthenticated browser requests redirect to `/login`; unauthenticated API requests return 401 JSON | Browser detection via `Accept: text/html` header; fallback step 7 in D-10 order |
| LOGIN-03 | User can switch auth method to Basic (browser native WWW-Authenticate popup) | Middleware step 6: returns 401 with `WWW-Authenticate: Basic realm="Triggarr"` header when method is Basic and no valid session/API key |
| LOGIN-04 | User can switch auth method to External for reverse proxy delegation | Middleware step 3: when method is External, pass through unconditionally |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.11+, ruff linting (E, F, I, UP, B, SIM), line length 120
- SecretStr for all API keys -- call `.get_secret_value()` only at HTTP client init (and in middleware for comparison)
- Loguru for logging (never print/logging module)
- pytest-asyncio with asyncio_mode=auto
- Deep code review before pushing: no API keys in logs/responses/HTML, SecretStr discipline maintained

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Auth enforcement (deny-all) | Frontend Server (ASGI middleware) | -- | Middleware runs before any route handler; single enforcement point |
| Browser vs API detection | Frontend Server (ASGI middleware) | -- | Accept header inspection happens at request level |
| Session cookie validation | Frontend Server (ASGI middleware) | -- | Cookie is present on request; validated via itsdangerous |
| API key validation | Frontend Server (ASGI middleware) | -- | X-Api-Key header checked in middleware before route dispatch |
| Basic auth credential check | Frontend Server (ASGI middleware) | -- | Authorization header decoded and verified inline |
| Health endpoint | API (route handler) | -- | Simple JSON response, no business logic |
| Setup redirect | Frontend Server (ASGI middleware) | -- | Redirect before any route runs when needs_setup is true |

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.132.0 | Web framework | Already in use [VERIFIED: runtime import] |
| Starlette | 0.52.1 | ASGI toolkit, BaseHTTPMiddleware | Already in use, provides middleware base class [VERIFIED: runtime import] |
| itsdangerous | 2.2.0 | Signed cookie creation/validation | Already used by `sign_session()`/`validate_session()` in `triggarr/auth.py` [VERIFIED: runtime import] |
| bcrypt | 5.0.0 | Password hashing/verification | Already used by `verify_password()` in `triggarr/auth.py` [VERIFIED: runtime import] |

### Supporting (stdlib)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| secrets | stdlib | `compare_digest()` for timing-safe API key comparison | API key validation in middleware |
| base64 | stdlib | Decoding Basic auth `Authorization` header | Basic auth mode credential extraction |

**No new dependencies required.** Everything needed is already installed.

## Architecture Patterns

### System Architecture Diagram

```
Request arrives
    |
    v
[SecurityHeadersMiddleware] --> adds security headers to response
    |
    v
[OriginCheckMiddleware] --> rejects cross-origin POST/PUT/PATCH/DELETE
    |
    v
[AuthMiddleware] --> NEW: deny-all auth gate
    |
    +-- Path in EXEMPT_PREFIXES? --> pass through to route
    |
    +-- needs_setup? --> 302 /setup (browser) or 401 JSON (API)
    |
    +-- is_disabled? --> pass through
    |
    +-- method == External? --> pass through
    |
    +-- Valid session cookie? --> pass through
    |
    +-- Valid X-Api-Key? --> pass through
    |
    +-- method == Basic? --> decode Authorization header
    |       +-- valid credentials? --> set cookie on response, pass through
    |       +-- invalid/missing? --> 401 + WWW-Authenticate: Basic realm="Triggarr"
    |
    +-- Else (Forms mode, no valid auth)
            +-- Browser (Accept: text/html)? --> 302 /login
            +-- API? --> 401 JSON {"detail": "Authentication required"}
    |
    v
[Route Handler] --> /health, /settings, /, etc.
```

### Middleware Registration Order

Starlette middleware executes in reverse registration order (last added = runs first on request). Current registration in `__main__.py`:

```python
# Current:
app.add_middleware(SecurityHeadersMiddleware)  # registered 1st, runs LAST on request
app.add_middleware(OriginCheckMiddleware)       # registered 2nd, runs 2nd on request

# After Phase 55:
app.add_middleware(SecurityHeadersMiddleware)  # runs LAST (adds headers to response)
app.add_middleware(OriginCheckMiddleware)       # runs 2nd (CSRF check)
app.add_middleware(AuthMiddleware)              # registered LAST, runs FIRST on request
```

AuthMiddleware MUST be registered last so it runs first -- unauthenticated requests should be rejected before CSRF checks or other processing. [VERIFIED: Starlette middleware order confirmed by reading `__main__.py` lines 67-68 and existing middleware pattern]

### Recommended Structure (within existing files)

```
triggarr/web/middleware.py     # ADD: AuthMiddleware class (D-01)
triggarr/__main__.py           # MODIFY: add app.add_middleware(AuthMiddleware)
triggarr/web/routes.py         # ADD: GET /health endpoint (D-07)
tests/test_auth_middleware.py  # NEW: comprehensive middleware tests
```

### Pattern 1: BaseHTTPMiddleware Dispatch

**What:** Follow the existing middleware pattern in the codebase.
**When to use:** All middleware in this project.

```python
# Source: triggarr/web/middleware.py (existing pattern)
class AuthMiddleware(BaseHTTPMiddleware):
    """Deny-all authentication middleware with path whitelist."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Check exempt paths
        if any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
            return await call_next(request)

        auth: AuthConfig = request.app.state.settings.auth

        # D-10 check order...
        # ... (implementation details)

        return await call_next(request)
```

### Pattern 2: Browser Detection

**What:** Distinguish browser requests from API requests for response formatting.
**When to use:** Fallback auth failure response (step 7 in D-10).

```python
# Source: design spec - Browser vs API Detection section
def _is_browser_request(request: Request) -> bool:
    """Check if the request comes from a browser based on Accept header."""
    accept = request.headers.get("accept", "")
    return "text/html" in accept
```

### Pattern 3: Basic Auth Inline Validation with Cookie Setting

**What:** Decode Basic auth header, verify credentials, set session cookie on success response.
**When to use:** Step 6 in D-10 check order when method is "Basic".

```python
# Source: design spec - Basic Auth Mode section
import base64
from triggarr.auth import verify_password, sign_session

# Inside dispatch, after checking session cookie and API key:
if auth.method == "Basic":
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Basic "):
        try:
            decoded = base64.b64decode(authorization[6:]).decode("utf-8")
            username, _, password = decoded.partition(":")
            if username == auth.username and verify_password(password, auth.password_hash.get_secret_value()):
                response = await call_next(request)
                # Set session cookie so browser doesn't re-prompt
                session_value = sign_session(username, auth.session_secret.get_secret_value())
                response.set_cookie(
                    "triggarr_session", session_value,
                    max_age=COOKIE_MAX_AGE, httponly=True, samesite="lax",
                )
                return response
        except Exception:
            pass  # Fall through to 401
    # No valid Basic credentials
    return Response(
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="Triggarr"'},
    )
```

### Pattern 4: Timing-Safe API Key Comparison

**What:** Use `secrets.compare_digest()` to prevent timing attacks on API key validation.
**When to use:** Step 5 in D-10 check order.

```python
import secrets

api_key_header = request.headers.get("x-api-key")
if api_key_header and secrets.compare_digest(
    api_key_header, auth.api_key.get_secret_value()
):
    return await call_next(request)
```

### Anti-Patterns to Avoid
- **Checking auth in individual route handlers:** Violates deny-all principle. Every new route would need to remember auth. The middleware pattern ensures zero routes can be accidentally left unprotected.
- **Using `app.state` before lifespan runs:** Settings are set on `app.state.settings` in the lifespan (scheduler.py line 202). Middleware must handle the case where `app.state.settings` might not exist yet (though in practice, lifespan runs before any request).
- **Logging API keys or passwords:** SecretStr discipline from CLAUDE.md. Never log `auth.api_key`, `auth.password_hash`, or decoded Basic auth credentials.
- **Using `==` for API key comparison:** Must use `secrets.compare_digest()` to prevent timing side-channel attacks.
- **Bare `except:` clauses:** Project convention requires specific exception types (CLAUDE.md deep review rule).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cookie signing | Custom HMAC scheme | `itsdangerous.TimestampSigner` via `sign_session()`/`validate_session()` | Already implemented in `triggarr/auth.py`, handles expiry, signature verification |
| Password verification | Custom hash comparison | `bcrypt.checkpw()` via `verify_password()` | Already implemented, constant-time comparison built in |
| API key generation | Custom random strings | `secrets.token_hex()` via `generate_api_key()` | Already implemented, CSPRNG-backed |
| Basic auth header parsing | Manual string splitting | `base64.b64decode()` + partition on `:` | Standard, but keep it simple -- stdlib is sufficient here |

**Key insight:** Phase 54 already built all the crypto/auth primitives. This phase is purely orchestration -- wiring those primitives into a middleware dispatch loop.

## Common Pitfalls

### Pitfall 1: Middleware Registration Order
**What goes wrong:** AuthMiddleware registered before OriginCheckMiddleware, so CSRF checks run on unauthenticated requests, or auth runs after security headers, wasting work.
**Why it happens:** Starlette's reverse-order registration is counterintuitive. `add_middleware()` called last = runs first on request.
**How to avoid:** Register AuthMiddleware as the LAST `add_middleware()` call in `__main__.py`. Comment the order explicitly.
**Warning signs:** Tests pass but middleware runs in wrong order. Verify by checking that unauthenticated requests never reach OriginCheckMiddleware.

### Pitfall 2: SecretStr Leakage in Responses or Logs
**What goes wrong:** API key or password hash appears in error responses, log messages, or JSON payloads.
**Why it happens:** Forgetting to call `.get_secret_value()` only at comparison point, or accidentally including auth config in debug output.
**How to avoid:** Never log `auth` object directly. Only call `.get_secret_value()` at the exact point of comparison. Never include auth details in error JSON.
**Warning signs:** Ruff won't catch this. Manual review needed. Deep review step 1.

### Pitfall 3: Basic Auth Decoding Errors
**What goes wrong:** Crash on malformed `Authorization: Basic` header (bad base64, missing colon, non-UTF8).
**Why it happens:** Malicious or misconfigured clients send garbage in the Authorization header.
**How to avoid:** Wrap base64 decode in try/except. Use `partition(":")` instead of `split(":", 1)` to handle missing colon gracefully (empty username or password).
**Warning signs:** Unhandled exceptions in middleware cause 500 errors instead of clean 401.

### Pitfall 4: Exempt Path Prefix Matching Too Broad
**What goes wrong:** A path like `/healthcheck` or `/settings/setup` matches the exempt prefix.
**Why it happens:** Using `startswith("/health")` matches any path starting with "/health".
**How to avoid:** For `/health` specifically, this is acceptable -- there's no `/healthcheck` route. But document this behavior. The design spec uses prefix matching intentionally for `/static/` (all static assets) and `/login` (GET and POST).
**Warning signs:** New routes accidentally falling under exempt prefixes. Review EXEMPT_PREFIXES when adding routes.

### Pitfall 5: Missing Cookie Attributes
**What goes wrong:** Session cookie set without `httponly`, `samesite`, or `secure` flags, making it vulnerable to XSS or CSRF.
**Why it happens:** Forgetting cookie security attributes when setting cookies in middleware (Basic auth flow).
**How to avoid:** Always set `httponly=True`, `samesite="lax"`. Consider `secure=True` only if HTTPS is guaranteed (not in Docker-first homelab context).
**Warning signs:** Browser devtools showing cookie without security flags.

### Pitfall 6: BaseHTTPMiddleware and StreamingResponse
**What goes wrong:** BaseHTTPMiddleware wraps streaming responses, breaking SSE or large file downloads.
**Why it happens:** BaseHTTPMiddleware calls `call_next()` which reads the entire response body. Known Starlette limitation.
**How to avoid:** This project doesn't use streaming responses -- htmx fragments are small HTML chunks. Not a concern for Triggarr, but worth noting. If streaming were needed, a pure ASGI middleware would be required.
**Warning signs:** Memory usage spikes on large responses. Not applicable to Triggarr's current architecture.

## Code Examples

### Complete AuthMiddleware Skeleton

```python
# Source: Synthesized from design spec + existing middleware pattern + CONTEXT.md D-10

from __future__ import annotations

import base64
import secrets

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from triggarr.auth import COOKIE_MAX_AGE, sign_session, validate_session, verify_password

EXEMPT_PREFIXES = ("/health", "/static", "/login", "/setup")


class AuthMiddleware(BaseHTTPMiddleware):
    """Deny-all authentication middleware with path whitelist.

    Every non-exempt request must pass one of the authentication checks
    defined in the dispatch method. Check order follows D-10 from the
    phase context.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path

        # Exempt paths pass through without auth
        if any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
            return await call_next(request)

        auth = request.app.state.settings.auth

        # Step 1: needs_setup -> redirect to /setup
        if auth.needs_setup:
            if self._is_browser(request):
                return RedirectResponse("/setup", status_code=302)
            return JSONResponse({"detail": "Setup required", "setup_url": "/setup"}, status_code=401)

        # Step 2: Disabled -> pass through
        if auth.is_disabled:
            return await call_next(request)

        # Step 3: External -> pass through
        if auth.method == "External":
            return await call_next(request)

        # Step 4: Valid session cookie -> pass through
        cookie = request.cookies.get("triggarr_session")
        username = validate_session(cookie, auth.session_secret.get_secret_value())
        if username:
            return await call_next(request)

        # Step 5: Valid X-Api-Key -> pass through
        api_key = request.headers.get("x-api-key")
        if api_key and secrets.compare_digest(api_key, auth.api_key.get_secret_value()):
            return await call_next(request)

        # Step 6: Basic auth mode -> check Authorization header
        if auth.method == "Basic":
            return await self._handle_basic_auth(request, auth, call_next)

        # Step 7: Fallback -> redirect or 401
        if self._is_browser(request):
            return RedirectResponse("/login", status_code=302)
        return JSONResponse({"detail": "Authentication required"}, status_code=401)

    @staticmethod
    def _is_browser(request: Request) -> bool:
        accept = request.headers.get("accept", "")
        return "text/html" in accept

    @staticmethod
    async def _handle_basic_auth(
        request: Request, auth, call_next: RequestResponseEndpoint
    ) -> Response:
        authorization = request.headers.get("authorization", "")
        if authorization.startswith("Basic "):
            try:
                decoded = base64.b64decode(authorization[6:]).decode("utf-8")
                username, _, password = decoded.partition(":")
                if username == auth.username and verify_password(
                    password, auth.password_hash.get_secret_value()
                ):
                    response = await call_next(request)
                    session_value = sign_session(
                        username, auth.session_secret.get_secret_value()
                    )
                    response.set_cookie(
                        "triggarr_session",
                        session_value,
                        max_age=COOKIE_MAX_AGE,
                        httponly=True,
                        samesite="lax",
                    )
                    return response
            except (ValueError, UnicodeDecodeError):
                pass
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Triggarr"'},
        )
```

### Health Endpoint

```python
# Source: design spec + CONTEXT.md D-06, D-07
# Added to triggarr/web/routes.py

@router.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint for uptime monitors."""
    return JSONResponse({"status": "ok"})
```

### Middleware Registration in __main__.py

```python
# Source: CONTEXT.md D-01, existing __main__.py pattern
from triggarr.web.middleware import AuthMiddleware, OriginCheckMiddleware, SecurityHeadersMiddleware

app.add_middleware(SecurityHeadersMiddleware)   # runs 3rd (response headers)
app.add_middleware(OriginCheckMiddleware)        # runs 2nd (CSRF)
app.add_middleware(AuthMiddleware)               # runs 1st (auth gate) -- MUST BE LAST
```

### Test Pattern: Minimal App with AuthMiddleware

```python
# Source: Derived from existing tests/test_middleware.py pattern
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from triggarr.web.middleware import AuthMiddleware
from triggarr.models.config import AuthConfig

def _make_auth_app(auth_config: AuthConfig | None = None) -> FastAPI:
    """Build a minimal FastAPI app with AuthMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    # Set up app.state.settings with auth config
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

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `lifespan` context manager | FastAPI 0.93+ / Starlette 0.27+ | Settings already on app.state via lifespan; no startup event needed [VERIFIED: scheduler.py uses lifespan] |
| Custom ASGI middleware | BaseHTTPMiddleware | Starlette 0.13+ | Simpler API; fine for non-streaming responses [VERIFIED: existing middleware uses this] |

**Deprecated/outdated:**
- `@app.on_event("startup")`: Deprecated in favor of lifespan. This project already uses lifespan correctly.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `path.startswith()` prefix matching for EXEMPT_PREFIXES is sufficient (no need for exact match or regex) | Architecture Patterns | LOW -- only risk is an accidentally matching route like `/healthcheck`, which doesn't exist |
| A2 | `samesite="lax"` is the correct cookie attribute (not "strict") | Code Examples | LOW -- "lax" allows top-level navigation which is needed for login redirects; "strict" would break redirect-then-cookie flow |

## Open Questions

1. **Should `/favicon.ico` be exempt?**
   - What we know: Browsers request favicon on every page load. If not exempt, it will trigger auth checks on every request.
   - What's unclear: Whether the existing `/static` prefix covers favicon (it does if favicon is served from `/static/`).
   - Recommendation: Check if favicon is served from `/static/` -- if so, already covered. If served from root `/favicon.ico`, add it to EXEMPT_PREFIXES or ensure it's a static mount.

2. **Should `secure=True` be set on the session cookie?**
   - What we know: Docker-first homelab deployment. Many users access via HTTP on local network. `secure=True` would break HTTP-only setups.
   - What's unclear: Whether to auto-detect HTTPS or leave it to the user.
   - Recommendation: Omit `secure=True` for now (homelab context). Can be added later as an option or auto-detected from the request scheme.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]` asyncio_mode = "auto") |
| Quick run command | `uv run pytest tests/test_auth_middleware.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MID-01 | Unauthenticated request to protected route is blocked | unit | `uv run pytest tests/test_auth_middleware.py::test_unauth_browser_redirect -x` | Wave 0 |
| MID-02 | Valid X-Api-Key passes through | unit | `uv run pytest tests/test_auth_middleware.py::test_valid_api_key_passes -x` | Wave 0 |
| MID-03 | GET /health returns 200 without auth | unit | `uv run pytest tests/test_auth_middleware.py::test_health_no_auth -x` | Wave 0 |
| MID-04 | Browser gets 302, API gets 401 | unit | `uv run pytest tests/test_auth_middleware.py::test_browser_vs_api_response -x` | Wave 0 |
| LOGIN-03 | Basic mode returns WWW-Authenticate header | unit | `uv run pytest tests/test_auth_middleware.py::test_basic_auth_www_authenticate -x` | Wave 0 |
| LOGIN-04 | External mode passes through | unit | `uv run pytest tests/test_auth_middleware.py::test_external_passthrough -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_auth_middleware.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_auth_middleware.py` -- covers MID-01, MID-02, MID-03, MID-04, LOGIN-03, LOGIN-04
- [ ] Update `tests/conftest.py` -- add `make_auth_app()` fixture or `make_settings()` with auth param

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | bcrypt password verification via `verify_password()`, session cookies via `itsdangerous` |
| V3 Session Management | yes | Signed cookies with 30-day expiry, `httponly=True`, `samesite="lax"` |
| V4 Access Control | yes | Deny-all middleware with explicit whitelist |
| V5 Input Validation | yes | Base64 decode wrapped in try/except, `partition()` for safe splitting |
| V6 Cryptography | no | No custom crypto -- uses bcrypt and itsdangerous |

### Known Threat Patterns for FastAPI Auth Middleware

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Timing attack on API key | Information Disclosure | `secrets.compare_digest()` for constant-time comparison |
| Basic auth credential sniffing | Information Disclosure | HTTPS recommended (but not enforced in homelab context) |
| Session cookie theft via XSS | Spoofing | `httponly=True` on cookie prevents JS access |
| CSRF on authenticated endpoints | Tampering | Existing OriginCheckMiddleware handles this |
| Brute force on Basic auth | Tampering | Deferred to FUT-01 (rate limiting); reverse proxy handles in External mode |
| Path traversal bypass of exempt list | Elevation of Privilege | Starlette normalizes paths before middleware sees them |

## Sources

### Primary (HIGH confidence)
- `triggarr/web/middleware.py` -- existing middleware pattern (SecurityHeadersMiddleware, OriginCheckMiddleware)
- `triggarr/__main__.py` -- middleware registration order and app setup
- `triggarr/auth.py` -- all auth helper functions (validate_session, verify_password, sign_session)
- `triggarr/models/config.py` -- AuthConfig model with needs_setup/is_disabled properties
- `triggarr/search/scheduler.py` -- lifespan sets `app.state.settings` (line 202)
- `docs/superpowers/specs/2026-04-14-built-in-auth-design.md` -- design spec for auth flow, exempt paths, Basic auth
- `tests/test_middleware.py` -- existing test pattern for middleware testing

### Secondary (MEDIUM confidence)
- Starlette 0.52.1 BaseHTTPMiddleware behavior [VERIFIED: existing codebase uses it successfully]
- FastAPI 0.132.0 middleware registration order [VERIFIED: reading `__main__.py`]

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all dependencies already installed and in use
- Architecture: HIGH -- follows existing patterns exactly, all integration points inspected
- Pitfalls: HIGH -- derived from codebase inspection and known Starlette behaviors

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (stable -- no external dependencies or fast-moving APIs)
