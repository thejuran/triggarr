"""Security middleware for Triggarr web server."""

from __future__ import annotations

import base64
import secrets
import time
from urllib.parse import quote, urlparse

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from triggarr.auth import COOKIE_MAX_AGE, sign_session, validate_session, verify_password
from triggarr.models.config import AuthConfig

# Paths that bypass authentication entirely.
# Prefix matching is intentional: /static covers all static assets,
# /login covers GET and POST, /setup covers the setup flow.
EXEMPT_PREFIXES = ("/health", "/static", "/login", "/setup")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security response headers to every response.

    Sets X-Frame-Options (clickjacking), X-Content-Type-Options (MIME sniffing),
    and Referrer-Policy headers.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Add security headers to the response."""
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )
        return response


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Reject cross-origin mutating requests via Origin/Referer header validation.

    For POST/PUT/PATCH/DELETE requests, checks the Origin header (or Referer
    as fallback) against the Host header. Mismatches return 403 Forbidden.

    When neither Origin nor Referer is present, the request is allowed
    because same-origin browser requests may omit both headers.
    GET/HEAD/OPTIONS methods always pass through.
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
            # Neither header present: allow (same-origin browser behavior)

        return await call_next(request)


class AuthMiddleware(BaseHTTPMiddleware):
    """Deny-all authentication middleware with path whitelist.

    Every non-exempt request must pass one of the authentication checks
    defined in the dispatch method. Check order follows D-10 from the
    phase context:
      1. needs_setup -> redirect to /setup
      2. is_disabled -> pass through
      3. method == External -> pass through
      4. valid session cookie -> pass through
      5. valid X-Api-Key -> pass through
      6. method == Basic -> check Authorization header
      7. fallback -> redirect to /login (browser) or 401 JSON (API)
    """

    _disabled_warned_at: float = 0.0
    _DISABLED_WARN_INTERVAL: float = 60.0  # seconds

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Gate every non-exempt route through authentication checks."""
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

        # Step 2: Disabled -> pass through + warning
        if auth.is_disabled:
            now = time.monotonic()
            if now - AuthMiddleware._disabled_warned_at >= AuthMiddleware._DISABLED_WARN_INTERVAL:
                logger.warning(
                    "Authentication is disabled -- all requests are unauthenticated. "
                    "Set auth.method in triggarr.toml to enable."
                )
                AuthMiddleware._disabled_warned_at = now
            return await call_next(request)

        # Step 3: External -> pass through
        if auth.method == "External":
            return await call_next(request)

        # Step 4: Valid session cookie -> pass through
        cookie = request.cookies.get("triggarr_session")
        username = validate_session(cookie, auth.session_secret.get_secret_value())
        if username:
            return await call_next(request)

        # Step 5: Valid X-Api-Key -> pass through (timing-safe comparison)
        api_key = request.headers.get("x-api-key")
        stored_key = auth.api_key.get_secret_value()
        if api_key and stored_key and secrets.compare_digest(api_key, stored_key):
            return await call_next(request)

        # Step 6: Basic auth mode -> check Authorization header
        if auth.method == "Basic":
            return await self._handle_basic_auth(request, auth, call_next)

        # Step 7: Fallback -> redirect or 401
        if self._is_browser(request):
            next_url = quote(str(request.url.path), safe="/")
            return RedirectResponse(f"/login?next={next_url}", status_code=302)
        return JSONResponse({"detail": "Authentication required"}, status_code=401)

    @staticmethod
    def _is_browser(request: Request) -> bool:
        """Check if the request comes from a browser based on Accept header."""
        accept = request.headers.get("accept", "")
        return "text/html" in accept

    @staticmethod
    async def _handle_basic_auth(
        request: Request, auth: AuthConfig, call_next: RequestResponseEndpoint
    ) -> Response:
        """Decode Basic auth header, verify credentials, set session cookie on success."""
        authorization = request.headers.get("authorization", "")
        if authorization.startswith("Basic "):
            try:
                decoded = base64.b64decode(authorization[6:]).decode("utf-8")
                username, _, password = decoded.partition(":")
                if secrets.compare_digest(username, auth.username) and verify_password(
                    password, auth.password_hash.get_secret_value()
                ):
                    response = await call_next(request)
                    session_value = sign_session(
                        username, auth.session_secret.get_secret_value()
                    )
                    _secure = request.url.scheme == "https" or request.headers.get(
                        "x-forwarded-proto", ""
                    ) == "https"
                    response.set_cookie(
                        "triggarr_session",
                        session_value,
                        max_age=COOKIE_MAX_AGE,
                        httponly=True,
                        samesite="lax",
                        secure=_secure,
                    )
                    return response
            except (ValueError, UnicodeDecodeError):
                pass
        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Triggarr"'},
        )
