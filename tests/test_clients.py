"""Tests for client structure, header auth, timeout, subclass hierarchy, and async base methods."""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
from unittest.mock import AsyncMock, patch

import httpx
import pydantic
import pytest
from loguru import logger

from triggarr.clients.base import ArrClient
from triggarr.clients.lidarr import LidarrClient
from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.models.arr import GrabEvent, Tag


class _ConcreteClient(ArrClient):
    """Minimal concrete ArrClient for testing base class behavior."""

    async def get_grab_history(self, item_id: int) -> list[GrabEvent]:
        return []


def test_arr_client_sets_api_key_header() -> None:
    """ArrClient sets X-Api-Key in httpx client headers."""
    client = _ConcreteClient(base_url="http://localhost:7878", api_key="test-key-123")
    assert client._client.headers["X-Api-Key"] == "test-key-123"


def test_arr_client_sets_timeout() -> None:
    """ArrClient respects custom timeout parameter."""
    client = _ConcreteClient(base_url="http://localhost:7878", api_key="key", timeout=30)
    # httpx.Timeout stores timeout as a Timeout object; check the connect/read values
    assert client._client.timeout.connect == 30
    assert client._client.timeout.read == 30


def test_arr_client_sets_content_type() -> None:
    """ArrClient sets Content-Type: application/json in default headers."""
    client = _ConcreteClient(base_url="http://localhost:7878", api_key="key")
    assert client._client.headers["Content-Type"] == "application/json"


def test_radarr_client_is_arr_client_subclass() -> None:
    """RadarrClient is a subclass of ArrClient."""
    assert issubclass(RadarrClient, ArrClient)


def test_sonarr_client_is_arr_client_subclass() -> None:
    """SonarrClient is a subclass of ArrClient."""
    assert issubclass(SonarrClient, ArrClient)


def test_radarr_client_app_name() -> None:
    """RadarrClient sets _app_name to 'Radarr'."""
    client = RadarrClient(base_url="http://localhost:7878", api_key="key")
    assert client._app_name == "Radarr"


def test_sonarr_client_app_name() -> None:
    """SonarrClient sets _app_name to 'Sonarr'."""
    client = SonarrClient(base_url="http://localhost:8989", api_key="key")
    assert client._app_name == "Sonarr"


def test_api_key_not_in_url() -> None:
    """API key is in headers only, not in the base URL."""
    api_key = "super-secret-key"
    client = _ConcreteClient(base_url="http://localhost:7878", api_key=api_key)
    assert api_key not in str(client._client.base_url)
    assert client._client.headers["X-Api-Key"] == api_key


# ---------------------------------------------------------------------------
# Async tests: _request_with_retry
# ---------------------------------------------------------------------------


async def test_request_with_retry_first_attempt_success() -> None:
    """_request_with_retry returns response on first-attempt success without retry."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        response = await client._request_with_retry("GET", "/test")
        assert response.status_code == 200
    finally:
        await client.close()


async def test_request_with_retry_retries_on_failure() -> None:
    """_request_with_retry retries once on first failure, returns success response on second attempt."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(500, request=request)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await client._request_with_retry("GET", "/test")
        assert call_count == 2
        assert response.status_code == 200
    finally:
        await client.close()


async def test_request_with_retry_reraises_when_retry_fails() -> None:
    """_request_with_retry re-raises exception when retry also fails."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with patch("asyncio.sleep", new_callable=AsyncMock), pytest.raises(httpx.HTTPStatusError):
            await client._request_with_retry("GET", "/test")
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# TEST-04 (Phase 65, Plan 04): in-flight aclose() contract tests
# ---------------------------------------------------------------------------
# Three tests pinning the behavioral contract of httpx.AsyncClient.aclose()
# when called while a request is still in flight. ArrClient.close() delegates
# to httpx.AsyncClient.aclose(); the scheduler shutdown drain (extended to 60s
# in plan 65-03) normally lets requests complete first, but in the worst case
# (scheduler.shutdown(wait=False) forces cancellation of a running cycle), an
# in-flight request could still be pending when await client.close() runs.
#
# Why these tests exist (Codex finding 4): a previous draft of TEST-04 used
# only httpx.MockTransport (which bypasses the real async connection pool and
# AsyncHTTPTransport close logic — the very code paths production exercises)
# and accepted "any of {RuntimeError, cancellation, HTTPError, clean completion}"
# for the no-cancel case, which can only prove "the mock does not hang". The
# revised plan keeps the cheap MockTransport regression check but adds two
# httpx.ASGITransport-backed tests that exercise the production close
# machinery, and pins the no-cancel exception class deterministically.
#
# Live probe (httpx 0.28.1, 2026-05-26): with the ASGI app described below,
# calling aclose() WITHOUT cancelling the in-flight request produces a
# deterministic AssertionError on the in-flight task (5/5 probe runs) — the
# assertion `response_complete.is_set()` inside httpx/_transports/asgi.py
# (line 181) trips because aclose() releases the streaming context before the
# ASGI handler has finished sending the response body. close() itself returns
# cleanly within ms. A future httpx release that intentionally changes this
# contract (e.g. surfaces httpx.RemoteProtocolError instead) will fail
# test 3 deliberately, surfacing the change instead of letting it silently
# alter Triggarr's shutdown behavior.
#
# TEST-04 (Codex finding 4): empirically observed exception class on
# httpx==0.28.1; update if httpx behavior changes intentionally.
_HTTPX_INFLIGHT_NO_CANCEL_EXC: type[BaseException] = AssertionError


def _build_slow_asgi_app(request_started: asyncio.Event, sleep_seconds: float = 10.0):
    """Build a bare-ASGI callable for TEST-04 in-flight close tests.

    Routes:
        /slow  — sets ``request_started`` then ``await asyncio.sleep(sleep_seconds)``;
                 never sends a response. The sleep is the configurable "in-flight"
                 window: long enough that the test can deterministically observe
                 the request as pending when close() is called, short enough that
                 the no-cancel test can let the sleep complete (and the transport's
                 ``assert response_complete.is_set()`` trip) within the 3s test
                 budget.
        /fast  — sends a 200 immediately (sanity check that the transport works).
        *      — 404.

    Not production code; only used by the TEST-04 tests below.
    """

    async def app(scope: dict, receive, send) -> None:
        if scope.get("type") != "http":
            return
        path = scope.get("path")
        if path == "/slow":
            request_started.set()
            # Block for ``sleep_seconds``; the test will close the client or
            # cancel the task before the sleep completes (cancel-then-close path),
            # or allow it to complete naturally so the ASGITransport assertion
            # trips (no-cancel path).
            await asyncio.sleep(sleep_seconds)
            return
        if path == "/fast":
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send(
                {"type": "http.response.body", "body": b'{"ok":true}', "more_body": False}
            )
            return
        await send({"type": "http.response.start", "status": 404, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    return app


async def test_aclose_with_mocktransport_returns_quickly_after_cancel() -> None:
    """MockTransport regression: close() returns within 2s after cancelling in-flight.

    TEST-04 cheap unit-level coverage. Proves the in-memory mock path does not
    hang when close() is called immediately after cancelling a request that is
    blocked in the handler. This is NOT a production-machinery contract test —
    that role belongs to the two ASGITransport tests below — but it stays for
    fast feedback on the test fixture itself.

    Key assertion: ``asyncio.wait_for(client.close(), timeout=2.0)`` — a hang
    in close() would surface as TimeoutError, failing the test fast.
    """
    request_started = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        request_started.set()
        await asyncio.sleep(10)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")

    pending = asyncio.create_task(client._request_with_retry("GET", "/slow"))
    try:
        await asyncio.wait_for(request_started.wait(), timeout=2.0)
        pending.cancel()
        with contextlib.suppress(asyncio.CancelledError, httpx.HTTPError):
            await pending
        # close() MUST return within 2s; a hang means a regression.
        await asyncio.wait_for(client.close(), timeout=2.0)
    finally:
        if not pending.done():
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError, httpx.HTTPError, Exception):
                await pending


async def test_aclose_with_real_asgi_transport_in_flight_returns_within_2s() -> None:
    """ASGITransport contract: cancel-then-close returns within 2s, no exceptions from close().

    TEST-04 real-transport contract test (Codex finding 4). Uses
    httpx.ASGITransport — a REAL transport that exercises the production
    AsyncHTTPTransport-equivalent async machinery (connection pool, async
    streaming, event-loop-aware close) — not the in-memory MockTransport that
    bypasses those paths.

    Recommended cancel-then-close shutdown pattern:
        1. cancel the in-flight task
        2. consume the cancellation (CancelledError / httpx.HTTPError)
        3. await client.close() inside asyncio.wait_for(..., timeout=2.0)

    Acceptance: close() returns within 2s with no unhandled exception from
    close() itself. A 2s timeout is ~1000x the expected close latency under
    in-process testing — large enough to absorb CI scheduler jitter, small
    enough that a regression (hang) fails fast.
    """
    request_started = asyncio.Event()
    app = _build_slow_asgi_app(request_started)

    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )

    pending = asyncio.create_task(client._request_with_retry("GET", "/slow"))
    try:
        await asyncio.wait_for(request_started.wait(), timeout=2.0)
        pending.cancel()
        with contextlib.suppress(asyncio.CancelledError, httpx.HTTPError):
            await pending
        # close() MUST return within 2s and MUST NOT raise from close() itself.
        await asyncio.wait_for(client.close(), timeout=2.0)
    finally:
        if not pending.done():
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError, httpx.HTTPError, Exception):
                await pending


async def test_aclose_with_real_asgi_transport_no_cancel_raises_specific_exception() -> None:
    """ASGITransport contract: close-without-cancel pins httpx's exact in-flight exception class.

    TEST-04 real-transport contract test (Codex finding 4). Calls close() while
    the request is still in flight WITHOUT cancelling the task first, then
    asserts the in-flight task raises exactly ``_HTTPX_INFLIGHT_NO_CANCEL_EXC``
    (empirically observed via live probe — see comment above the constant).

    The single-class isinstance assertion replaces the previous four-class
    "accept any of {RuntimeError / cancellation / HTTPError / clean completion}"
    hedging union (Codex finding 4) — that pattern could not detect a
    regression. A future httpx release that intentionally changes the
    in-flight exception class will fail THIS test deliberately, forcing the
    operator to update the pinned constant after auditing the upstream change.

    Acceptance:
        - ``asyncio.wait_for(client.close(), timeout=2.0)`` does not raise
          TimeoutError (close itself must complete within 2s).
        - ``isinstance(result[0], _HTTPX_INFLIGHT_NO_CANCEL_EXC)`` for the
          gathered in-flight task result.

    Implementation note: the /slow handler sleeps for 0.5s (not 10s) in this
    test so the ASGI handler can complete naturally and the transport's
    ``assert response_complete.is_set()`` (httpx 0.28.1 asgi.py line 181) can
    trip — yielding the deterministic _HTTPX_INFLIGHT_NO_CANCEL_EXC the test
    pins. 0.5s is long enough to guarantee the request is in flight when
    close() is called (request_started signals before sleep), and short
    enough that the whole test completes well under the 3s wall-clock budget.
    """
    request_started = asyncio.Event()
    # Short sleep so the ASGI handler completes and the transport assertion
    # fires inside the 3s test budget; long enough that the request is
    # provably in flight when client.close() is called (request_started has
    # already been set by the handler before the sleep begins).
    app = _build_slow_asgi_app(request_started, sleep_seconds=0.5)

    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )

    pending = asyncio.create_task(client._request_with_retry("GET", "/slow"))
    try:
        await asyncio.wait_for(request_started.wait(), timeout=2.0)
        # Do NOT cancel pending — call close() with the request still in-flight.
        await asyncio.wait_for(client.close(), timeout=2.0)

        # Wait for the in-flight task to surface its exception (bounded by the
        # 0.5s sleep + a generous margin; 2.0s total caps the test budget).
        result = await asyncio.wait_for(
            asyncio.gather(pending, return_exceptions=True), timeout=2.0
        )
        assert isinstance(result[0], _HTTPX_INFLIGHT_NO_CANCEL_EXC), (
            f"Expected in-flight task to raise {_HTTPX_INFLIGHT_NO_CANCEL_EXC.__name__} "
            f"after aclose() without prior cancel; got {type(result[0]).__name__}: {result[0]!r}. "
            "If this is an intentional httpx change, update _HTTPX_INFLIGHT_NO_CANCEL_EXC."
        )
    finally:
        if not pending.done():
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError, httpx.HTTPError, Exception):
                await pending


# ---------------------------------------------------------------------------
# Async tests: get_paginated
# ---------------------------------------------------------------------------


async def test_get_paginated_single_page() -> None:
    """get_paginated returns records from a single page."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "page": 1,
            "pageSize": 50,
            "sortKey": "id",
            "totalRecords": 2,
            "records": [{"id": 1}, {"id": 2}],
        }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_paginated("/items")
        assert len(result) == 2
    finally:
        await client.close()


async def test_get_paginated_multi_page() -> None:
    """get_paginated returns all records across multiple pages."""

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page", "1")
        if page == "1":
            body = {
                "page": 1,
                "pageSize": 2,
                "sortKey": "id",
                "totalRecords": 3,
                "records": [{"id": 1}, {"id": 2}],
            }
        else:
            body = {
                "page": 2,
                "pageSize": 2,
                "sortKey": "id",
                "totalRecords": 3,
                "records": [{"id": 3}],
            }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_paginated("/items", page_size=2)
        assert len(result) == 3
    finally:
        await client.close()


async def test_get_paginated_empty_results() -> None:
    """get_paginated returns empty list for zero totalRecords."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "page": 1,
            "pageSize": 50,
            "sortKey": "id",
            "totalRecords": 0,
            "records": [],
        }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_paginated("/items")
        assert result == []
    finally:
        await client.close()


async def test_get_paginated_malformed_response() -> None:
    """get_paginated raises ValidationError on malformed API response."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"bad": "data"})

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with pytest.raises(pydantic.ValidationError):
            await client.get_paginated("/items")
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Async tests: validate_connection
# ---------------------------------------------------------------------------


async def test_validate_connection_success() -> None:
    """validate_connection returns True on 200 with valid system status."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": "5.0.0"})

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.validate_connection()
        assert result is True
    finally:
        await client.close()


async def test_validate_connection_401() -> None:
    """validate_connection returns False on 401 Unauthorized."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request)

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.validate_connection()
        assert result is False
    finally:
        await client.close()


async def test_validate_connection_connect_error() -> None:
    """validate_connection returns False on ConnectError."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.validate_connection()
        assert result is False
    finally:
        await client.close()


async def test_validate_connection_timeout() -> None:
    """validate_connection returns False on TimeoutException."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.validate_connection()
        assert result is False
    finally:
        await client.close()


async def test_validate_connection_dns_failure() -> None:
    """validate_connection returns False on DNS resolution failure (CONN-02)."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("[Errno -2] Name or service not known")

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://nonexistent.invalid", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.validate_connection()
        assert result is False
    finally:
        await client.close()


async def test_validate_connection_ssl_error() -> None:
    """validate_connection returns False on SSL/TLS error (CONN-03)."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="https://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="https://test")
    try:
        result = await client.validate_connection()
        assert result is False
    finally:
        await client.close()


async def test_validate_connection_connect_error_logs_warning() -> None:
    """validate_connection logs warning with app name on ConnectError (CONN-01 gap)."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        result = await client.validate_connection()
        assert result is False
        assert "Connection refused" in sink.getvalue()
        assert "Test" in sink.getvalue()
        assert "key" not in sink.getvalue()  # API key must never appear in log output
    finally:
        logger.remove(handler_id)
        await client.close()


# ---------------------------------------------------------------------------
# page_size configuration (Phase 17)
# ---------------------------------------------------------------------------


def test_client_default_page_size() -> None:
    """ArrClient defaults to page_size=50."""
    client = _ConcreteClient(base_url="http://test:7878", api_key="key")
    assert client._page_size == 50


def test_client_accepts_page_size() -> None:
    """ArrClient stores custom page_size."""
    client = _ConcreteClient(base_url="http://test:7878", api_key="key", page_size=100)
    assert client._page_size == 100


# ---------------------------------------------------------------------------
# Async tests: get_grab_history (Phase 19)
# ---------------------------------------------------------------------------


async def test_radarr_get_grab_history_returns_grab_events() -> None:
    """RadarrClient.get_grab_history returns parsed GrabEvent instances."""

    def handler(request: httpx.Request) -> httpx.Response:
        # Per-movie history endpoint returns a flat JSON array (not paginated)
        body = [
            {
                "id": 100,
                "date": "2026-02-25T10:00:00Z",
                "eventType": "grabbed",
                "sourceTitle": "Movie.2024.1080p",
                "movieId": 42,
                "quality": {"quality": {"name": "Bluray-1080p"}},
            },
            {
                "id": 101,
                "date": "2026-02-25T09:30:00Z",
                "eventType": "grabbed",
                "sourceTitle": "Movie.2024.720p",
                "movieId": 42,
                "quality": {"quality": {"name": "Bluray-720p"}},
            },
        ]
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = RadarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_grab_history(movie_id=42)
        assert len(result) == 2
        assert all(isinstance(e, GrabEvent) for e in result)
        assert result[0].id == 100
        assert result[0].date == "2026-02-25T10:00:00Z"
        assert result[0].eventType == "grabbed"
        assert result[0].sourceTitle == "Movie.2024.1080p"
        assert result[1].id == 101
        assert result[1].sourceTitle == "Movie.2024.720p"
        # Extra fields should be ignored
        assert not hasattr(result[0], "movieId")
    finally:
        await client.close()


async def test_radarr_get_grab_history_empty() -> None:
    """RadarrClient.get_grab_history returns empty list for zero results."""

    def handler(request: httpx.Request) -> httpx.Response:
        # Per-movie history endpoint returns empty array
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    client = RadarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_grab_history(movie_id=999)
        assert result == []
    finally:
        await client.close()


async def test_radarr_get_grab_history_passes_correct_params() -> None:
    """RadarrClient.get_grab_history uses /history/movie with movieId and eventType=grabbed."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/api/v3/history/movie" in str(request.url.path)
        assert request.url.params["movieId"] == "42"
        assert request.url.params["eventType"] == "grabbed"
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    client = RadarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        await client.get_grab_history(movie_id=42)
    finally:
        await client.close()


async def test_sonarr_get_grab_history_returns_grab_events() -> None:
    """SonarrClient.get_grab_history returns parsed GrabEvent instances."""

    def handler(request: httpx.Request) -> httpx.Response:
        # Per-series history endpoint returns a flat JSON array (not paginated)
        body = [
            {
                "id": 200,
                "date": "2026-02-25T11:00:00Z",
                "eventType": "grabbed",
                "sourceTitle": "Show.S01E01.1080p",
                "seriesId": 10,
                "episodeId": 55,
            },
            {
                "id": 201,
                "date": "2026-02-25T10:45:00Z",
                "eventType": "grabbed",
                "sourceTitle": "Show.S01E02.1080p",
                "seriesId": 10,
                "episodeId": 56,
            },
        ]
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = SonarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_grab_history(series_id=10)
        assert len(result) == 2
        assert all(isinstance(e, GrabEvent) for e in result)
        assert result[0].id == 200
        assert result[0].date == "2026-02-25T11:00:00Z"
        assert result[0].eventType == "grabbed"
        assert result[0].sourceTitle == "Show.S01E01.1080p"
        assert result[1].id == 201
        assert result[1].sourceTitle == "Show.S01E02.1080p"
        # Extra fields should be ignored
        assert not hasattr(result[0], "seriesId")
    finally:
        await client.close()


async def test_sonarr_get_grab_history_empty() -> None:
    """SonarrClient.get_grab_history returns empty list for zero results."""

    def handler(request: httpx.Request) -> httpx.Response:
        # Per-series history endpoint returns empty array
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    client = SonarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_grab_history(series_id=999)
        assert result == []
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Tag model and get_tags() (Phase 35)
# ---------------------------------------------------------------------------


def test_tag_model_parses_response() -> None:
    """Tag.model_validate parses {id, label} JSON into Tag object."""
    tag = Tag.model_validate({"id": 1, "label": "4k"})
    assert tag.id == 1
    assert tag.label == "4k"


def test_tag_model_ignores_extra_fields() -> None:
    """Tag model ignores extra fields from the API response."""
    tag = Tag.model_validate({"id": 1, "label": "4k", "extra": "stuff"})
    assert tag.id == 1
    assert tag.label == "4k"
    assert not hasattr(tag, "extra")


async def test_get_tags_returns_tag_list() -> None:
    """ArrClient.get_tags() returns list of Tag objects from API response."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[
            {"id": 1, "label": "4k"},
            {"id": 2, "label": "anime"},
        ])

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_tags()
        assert len(result) == 2
        assert all(isinstance(t, Tag) for t in result)
        assert result[0].id == 1
        assert result[0].label == "4k"
        assert result[1].id == 2
        assert result[1].label == "anime"
    finally:
        await client.close()


async def test_get_tags_empty_response() -> None:
    """ArrClient.get_tags() returns empty list when endpoint returns []."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_tags()
        assert result == []
    finally:
        await client.close()


async def test_sonarr_get_grab_history_passes_correct_params() -> None:
    """SonarrClient.get_grab_history uses /history/series with seriesId and eventType=grabbed."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/api/v3/history/series" in str(request.url.path)
        assert request.url.params["seriesId"] == "10"
        assert request.url.params["eventType"] == "grabbed"
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    client = SonarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        await client.get_grab_history(series_id=10)
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# LidarrClient tests
# ---------------------------------------------------------------------------


def test_lidarr_client_is_arr_client_subclass() -> None:
    """LidarrClient is a subclass of ArrClient."""
    assert issubclass(LidarrClient, ArrClient)


def test_lidarr_client_app_name() -> None:
    """LidarrClient sets _app_name to 'Lidarr'."""
    client = LidarrClient(base_url="http://localhost:8686", api_key="key")
    assert client._app_name == "Lidarr"


async def test_lidarr_get_wanted_missing_uses_v1_with_include_artist() -> None:
    """LidarrClient.get_wanted_missing uses /api/v1/ path with includeArtist=true."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/api/v1/wanted/missing" in str(request.url.path)
        assert request.url.params["includeArtist"] == "true"
        return httpx.Response(200, json={
            "page": 1, "pageSize": 50, "sortKey": "id",
            "totalRecords": 0, "records": [],
        })

    transport = httpx.MockTransport(handler)
    client = LidarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_wanted_missing()
        assert result == []
    finally:
        await client.close()


async def test_lidarr_get_wanted_cutoff_uses_v1_with_include_artist() -> None:
    """LidarrClient.get_wanted_cutoff uses /api/v1/ path with includeArtist=true."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/api/v1/wanted/cutoff" in str(request.url.path)
        assert request.url.params["includeArtist"] == "true"
        return httpx.Response(200, json={
            "page": 1, "pageSize": 50, "sortKey": "id",
            "totalRecords": 0, "records": [],
        })

    transport = httpx.MockTransport(handler)
    client = LidarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_wanted_cutoff()
        assert result == []
    finally:
        await client.close()


async def test_lidarr_get_library_count_counts_artists() -> None:
    """LidarrClient.get_library_count returns number of artists."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/api/v1/artist" in str(request.url.path)
        return httpx.Response(200, json=[
            {"id": 1, "artistName": "Artist One"},
            {"id": 2, "artistName": "Artist Two"},
            {"id": 3, "artistName": "Artist Three"},
        ])

    transport = httpx.MockTransport(handler)
    client = LidarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        count = await client.get_library_count()
        assert count == 3
    finally:
        await client.close()


async def test_lidarr_get_tags_uses_v1_endpoint() -> None:
    """LidarrClient.get_tags uses /api/v1/tag (not /api/v3/tag)."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/api/v1/tag" in str(request.url.path)
        assert "/api/v3/" not in str(request.url.path)
        return httpx.Response(200, json=[
            {"id": 1, "label": "flac"},
            {"id": 2, "label": "vinyl"},
        ])

    transport = httpx.MockTransport(handler)
    client = LidarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_tags()
        assert len(result) == 2
        assert all(isinstance(t, Tag) for t in result)
        assert result[0].label == "flac"
    finally:
        await client.close()


async def test_lidarr_get_grab_history_returns_grab_events() -> None:
    """LidarrClient.get_grab_history returns parsed GrabEvent instances."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/api/v1/history" in str(request.url.path)
        assert request.url.params["albumId"] == "42"
        assert request.url.params["eventType"] == "1"
        # Lidarr history is paginated (uses get_paginated → PaginatedResponse)
        body = {
            "page": 1, "pageSize": 50, "sortKey": "id", "totalRecords": 2,
            "records": [
                {
                    "id": 300,
                    "date": "2026-04-06T10:00:00Z",
                    "eventType": "grabbed",
                    "sourceTitle": "Artist.Album.FLAC",
                    "albumId": 42,
                    "artistId": 5,
                    "quality": {"quality": {"name": "FLAC"}},
                },
                {
                    "id": 301,
                    "date": "2026-04-06T09:30:00Z",
                    "eventType": "grabbed",
                    "sourceTitle": "Artist.Album.MP3-320",
                    "albumId": 42,
                    "artistId": 5,
                    "quality": {"quality": {"name": "MP3-320"}},
                },
            ],
        }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = LidarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_grab_history(album_id=42)
        assert len(result) == 2
        assert all(isinstance(e, GrabEvent) for e in result)
        assert result[0].id == 300
        assert result[0].sourceTitle == "Artist.Album.FLAC"
        assert result[1].id == 301
    finally:
        await client.close()


async def test_lidarr_get_grab_history_empty() -> None:
    """LidarrClient.get_grab_history returns empty list for zero results."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "page": 1, "pageSize": 50, "sortKey": "id", "totalRecords": 0, "records": [],
        })

    transport = httpx.MockTransport(handler)
    client = LidarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_grab_history(album_id=999)
        assert result == []
    finally:
        await client.close()


async def test_lidarr_validate_connection_uses_v1_endpoint() -> None:
    """LidarrClient.validate_connection uses /api/v1/system/status (not /api/v3/)."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/api/v1/system/status" in str(request.url.path)
        assert "/api/v3/" not in str(request.url.path)
        return httpx.Response(200, json={
            "version": "2.8.0.1234",
            "appName": "Lidarr",
        })

    transport = httpx.MockTransport(handler)
    client = LidarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.validate_connection()
        assert result is True
    finally:
        await client.close()


async def test_lidarr_validate_connection_returns_false_on_401() -> None:
    """LidarrClient.validate_connection returns False on 401."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "Unauthorized"})

    transport = httpx.MockTransport(handler)
    client = LidarrClient(base_url="http://test", api_key="bad-key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.validate_connection()
        assert result is False
    finally:
        await client.close()


async def test_lidarr_search_albums_sends_correct_command() -> None:
    """LidarrClient.search_albums sends AlbumSearch command with albumIds."""

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        assert "/api/v1/command" in str(request.url.path)
        body = json.loads(request.content)
        assert body["name"] == "AlbumSearch"
        assert body["albumIds"] == [10, 20, 30]
        return httpx.Response(200, json={"id": 1, "name": "AlbumSearch", "status": "queued"})

    transport = httpx.MockTransport(handler)
    client = LidarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        response = await client.search_albums(album_ids=[10, 20, 30])
        assert response.status_code == 200
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Bad API response tests (Phase 46, Plan 02)
# ---------------------------------------------------------------------------


async def test_validate_connection_403() -> None:
    """validate_connection returns False on 403 Forbidden (API-02)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request)

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.validate_connection()
        assert result is False
    finally:
        await client.close()


async def test_validate_connection_502() -> None:
    """validate_connection returns False on 502 Bad Gateway (API-02)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, request=request)

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.validate_connection()
        assert result is False
    finally:
        await client.close()


async def test_get_paginated_invalid_json() -> None:
    """get_paginated raises on invalid JSON response body (API-01)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json at all", headers={"content-type": "application/json"})

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with pytest.raises(json.JSONDecodeError):
            await client.get_paginated("/items")
    finally:
        await client.close()


async def test_get_paginated_truncated_response() -> None:
    """get_paginated returns actual records when totalRecords exceeds reality (API-04)."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "page": 1,
            "pageSize": 50,
            "sortKey": "id",
            "totalRecords": 10,
            "records": [{"id": 1}, {"id": 2}, {"id": 3}],
        }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_paginated("/items")
        # page*pageSize (1*50=50) >= totalRecords (10), so terminates after page 1
        assert len(result) == 3
    finally:
        await client.close()


async def test_get_paginated_mid_pagination_empty_page() -> None:
    """get_paginated terminates when mid-pagination page returns empty records (API-04)."""

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page", "1")
        if page == "1":
            body = {
                "page": 1,
                "pageSize": 2,
                "sortKey": "id",
                "totalRecords": 6,
                "records": [{"id": 1}, {"id": 2}],
            }
        else:
            body = {
                "page": 2,
                "pageSize": 2,
                "sortKey": "id",
                "totalRecords": 6,
                "records": [],
            }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_paginated("/items", page_size=2)
        assert len(result) == 2
    finally:
        await client.close()


async def test_get_paginated_missing_records_key() -> None:
    """get_paginated raises ValidationError when response lacks records key (API-04)."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = {"page": 1, "pageSize": 50, "sortKey": "id", "totalRecords": 5}
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with pytest.raises(pydantic.ValidationError):
            await client.get_paginated("/items")
    finally:
        await client.close()
