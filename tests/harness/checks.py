"""Reason-coded HTTP smoke checks for the shipped Triggarr image.

Shared by the image-smoke CI job (Plan 04) and the browser suite's setup
scaffolding (Plans 05/06): one implementation runs both the positive smoke
path and the permanent missing-static-asset negative (D-01, D-04). Every
check raises :class:`SmokeCheckError` carrying a specific reason code on
failure; :func:`expect_failure` enforces D-03 -- a negative passes only on
the exact expected rejection, never on any failure.

Stdlib-only (urllib, http.cookies, json) so this module stays usable inside
a minimal CI environment with no extra HTTP client dependency.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from http.cookies import SimpleCookie
from typing import Any

from loguru import logger

SESSION_COOKIE = "triggarr_session"
STATIC_ASSETS = ("/static/css/output.css", "/static/js/htmx.min.js")
_TIMEOUT_SECONDS = 10.0


class SmokeCheckError(AssertionError):
    """Raised by every check on failure, carrying a machine-checkable reason.

    ``detail`` must never include a password or cookie value (T-82-08) --
    callers that need to reference a secret in a failure message describe it
    (e.g. "no session cookie was set"), never embed the value itself.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"[{reason}] {detail}")

    def __str__(self) -> str:
        return f"[{self.reason}] {self.detail}"


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Prevent urllib from automatically following redirects.

    Checks that assert on a 302/303 response need to observe that response
    itself, never whatever it points to.
    """

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


_opener = urllib.request.build_opener(_NoRedirectHandler)


def _request(
    base: str,
    path: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    cookie: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """Issue a single HTTP request and return (status, response headers, body).

    Only headers explicitly passed by the caller (plus an optional session
    cookie) are sent, and redirects are never followed automatically.
    """
    request_headers = dict(headers or {})
    if cookie is not None:
        request_headers["Cookie"] = f"{SESSION_COOKIE}={cookie}"
    request = urllib.request.Request(base + path, data=data, headers=request_headers, method=method)
    try:
        response = _opener.open(request, timeout=_TIMEOUT_SECONDS)
        return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        resp_headers = dict(exc.headers.items()) if exc.headers else {}
        return exc.code, resp_headers, exc.read()


def _header(headers: dict[str, str], name: str) -> str | None:
    """Case-insensitive header lookup (HTTP header names are case-insensitive, RFC 7230 S3.2).

    A real ASGI server (Starlette/Uvicorn, as used by the shipped image) emits
    response header names in lowercase over the wire -- a plain dict.get() with
    mixed-case names like "Set-Cookie"/"Location" silently misses them.
    """
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def _cookie_value(headers: dict[str, str], name: str) -> str | None:
    """Parse a Set-Cookie response header and return the named cookie's value, if present."""
    raw = _header(headers, "Set-Cookie")
    if not raw:
        return None
    jar: SimpleCookie[str] = SimpleCookie()
    jar.load(raw)
    morsel = jar.get(name)
    return morsel.value if morsel else None


def check_health(base: str) -> None:
    """GET /health must return 200 {"status": "ok"}."""
    status, _, body = _request(base, "/health")
    if status != 200:
        raise SmokeCheckError("health", f"expected 200, got {status}")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise SmokeCheckError("health", "response body was not valid JSON") from None
    if payload != {"status": "ok"}:
        raise SmokeCheckError("health", f"unexpected response body: {payload!r}")


def check_static_assets(base: str, assets: tuple[str, ...] = STATIC_ASSETS) -> None:
    """Every default static asset must return 200 with a non-empty body."""
    for path in assets:
        status, _, body = _request(base, path)
        if status != 200 or not body:
            raise SmokeCheckError("static-asset-missing", path)


def check_setup_available(base: str) -> None:
    """GET /setup must show the setup form while setup is needed."""
    status, _, body = _request(base, "/setup")
    if status != 200 or b'name="confirm_password"' not in body:
        raise SmokeCheckError("setup-unavailable", f"GET /setup returned status={status}")


def complete_setup(base: str, username: str, password: str) -> str:
    """POST /setup to create the admin account; returns the issued session cookie value."""
    form = f"username={username}&password={password}&confirm_password={password}".encode()
    status, headers, _ = _request(
        base,
        "/setup",
        method="POST",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    cookie = _cookie_value(headers, SESSION_COOKIE)
    if status != 200 or not cookie:
        raise SmokeCheckError("setup-failed", f"POST /setup returned status={status}, cookie_issued={bool(cookie)}")
    return cookie


def check_setup_closed(base: str) -> None:
    """GET /setup must redirect to /login once setup has already been completed."""
    status, headers, _ = _request(base, "/setup")
    location = _header(headers, "Location") or ""
    if status != 302 or "/login" not in location:
        raise SmokeCheckError("setup-still-open", f"GET /setup returned status={status}")


def check_login_rejected(base: str, username: str, wrong_password: str) -> None:
    """POST /login with a wrong password must reject without issuing a session."""
    form = f"username={username}&password={wrong_password}".encode()
    status, headers, body = _request(
        base,
        "/login",
        method="POST",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if _cookie_value(headers, SESSION_COOKIE):
        raise SmokeCheckError("login-accepted-wrong-password", "a session cookie was issued for a wrong password")
    if status != 200 or b"Invalid username or password" not in body:
        raise SmokeCheckError("login-accepted-wrong-password", f"POST /login returned status={status}")


def login(base: str, username: str, password: str) -> str:
    """POST /login with valid credentials; returns the issued session cookie value."""
    form = f"username={username}&password={password}".encode()
    status, headers, _ = _request(
        base,
        "/login",
        method="POST",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    cookie = _cookie_value(headers, SESSION_COOKIE)
    if status != 303 or not cookie:
        raise SmokeCheckError("login-failed", f"POST /login returned status={status}, cookie_issued={bool(cookie)}")
    return cookie


def check_dashboard(base: str, cookie: str) -> None:
    """GET / with a valid session must reach the dashboard."""
    status, _, body = _request(base, "/", headers={"Accept": "text/html"}, cookie=cookie)
    if status != 200 or b"Dashboard - Triggarr" not in body:
        raise SmokeCheckError("dashboard-unreachable", f"GET / with session returned status={status}")


def check_protected_redirects_to_login(base: str) -> None:
    """GET / without a session must redirect a browser request to /login."""
    status, headers, _ = _request(base, "/", headers={"Accept": "text/html"})
    location = _header(headers, "Location") or ""
    if status != 302 or "/login" not in location:
        raise SmokeCheckError("protected-page-open", f"GET / without session returned status={status}")


def expect_failure(reason: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Assert that ``fn(*args, **kwargs)`` fails with exactly the expected reason (D-03).

    Passes only when ``fn`` raises :class:`SmokeCheckError` with ``.reason == reason``.
    Raises ``SmokeCheckError("negative-harness", ...)`` if ``fn`` returns normally or
    raises a different reason, so an unrelated failure can never masquerade as a
    passing negative test.
    """
    try:
        fn(*args, **kwargs)
    except SmokeCheckError as exc:
        if exc.reason != reason:
            raise SmokeCheckError(
                "negative-harness", f"expected reason {reason!r}, got {exc.reason!r}"
            ) from exc
        logger.debug(
            "expect_failure: {fn} failed with expected reason {reason!r}",
            fn=getattr(fn, "__name__", repr(fn)),
            reason=reason,
        )
        return
    raise SmokeCheckError(
        "negative-harness", f"{getattr(fn, '__name__', repr(fn))} did not fail (expected reason {reason!r})"
    )
