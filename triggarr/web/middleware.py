"""Security middleware for Triggarr web server."""

from __future__ import annotations

from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


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
