"""Security middleware for Fetcharr web server."""

from __future__ import annotations

from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Reject cross-origin POST requests via Origin/Referer header validation.

    For POST requests, checks the Origin header (or Referer as fallback)
    against the Host header. Mismatches return 403 Forbidden.

    When neither Origin nor Referer is present, the request is allowed
    because same-origin browser requests may omit both headers.
    Non-POST methods always pass through.
    """

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        """Check Origin/Referer on POST requests, pass through otherwise."""
        if request.method == "POST":
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
