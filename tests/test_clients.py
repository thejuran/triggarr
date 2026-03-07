"""Tests for client structure, header auth, timeout, subclass hierarchy, and async base methods."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pydantic
import pytest

from triggarr.clients.base import ArrClient
from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.models.arr import GrabEvent


def test_arr_client_sets_api_key_header() -> None:
    """ArrClient sets X-Api-Key in httpx client headers."""
    client = ArrClient(base_url="http://localhost:7878", api_key="test-key-123")
    assert client._client.headers["X-Api-Key"] == "test-key-123"


def test_arr_client_sets_timeout() -> None:
    """ArrClient respects custom timeout parameter."""
    client = ArrClient(base_url="http://localhost:7878", api_key="key", timeout=30)
    # httpx.Timeout stores timeout as a Timeout object; check the connect/read values
    assert client._client.timeout.connect == 30
    assert client._client.timeout.read == 30


def test_arr_client_sets_content_type() -> None:
    """ArrClient sets Content-Type: application/json in default headers."""
    client = ArrClient(base_url="http://localhost:7878", api_key="key")
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
    client = ArrClient(base_url="http://localhost:7878", api_key=api_key)
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
    client = ArrClient(base_url="http://test", api_key="key")
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
    client = ArrClient(base_url="http://test", api_key="key")
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
    client = ArrClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        with patch("asyncio.sleep", new_callable=AsyncMock), pytest.raises(httpx.HTTPStatusError):
            await client._request_with_retry("GET", "/test")
    finally:
        await client.close()


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
    client = ArrClient(base_url="http://test", api_key="key")
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
    client = ArrClient(base_url="http://test", api_key="key")
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
    client = ArrClient(base_url="http://test", api_key="key")
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
    client = ArrClient(base_url="http://test", api_key="key")
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
    client = ArrClient(base_url="http://test", api_key="key")
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
    client = ArrClient(base_url="http://test", api_key="key")
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
    client = ArrClient(base_url="http://test", api_key="key")
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
    client = ArrClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.validate_connection()
        assert result is False
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# page_size configuration (Phase 17)
# ---------------------------------------------------------------------------


def test_client_default_page_size() -> None:
    """ArrClient defaults to page_size=50."""
    client = ArrClient(base_url="http://test:7878", api_key="key")
    assert client._page_size == 50


def test_client_accepts_page_size() -> None:
    """ArrClient stores custom page_size."""
    client = ArrClient(base_url="http://test:7878", api_key="key", page_size=100)
    assert client._page_size == 100


# ---------------------------------------------------------------------------
# Async tests: get_grab_history (Phase 19)
# ---------------------------------------------------------------------------


async def test_radarr_get_grab_history_returns_grab_events() -> None:
    """RadarrClient.get_grab_history returns parsed GrabEvent instances."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "page": 1,
            "pageSize": 50,
            "sortKey": "date",
            "totalRecords": 2,
            "records": [
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
            ],
        }
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
        body = {
            "page": 1,
            "pageSize": 50,
            "sortKey": "date",
            "totalRecords": 0,
            "records": [],
        }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = RadarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_grab_history(movie_id=999)
        assert result == []
    finally:
        await client.close()


async def test_radarr_get_grab_history_passes_movie_id_param() -> None:
    """RadarrClient.get_grab_history passes movieId and eventType=1 in URL params."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["movieId"] == "42"
        assert request.url.params["eventType"] == "1"
        body = {
            "page": 1,
            "pageSize": 50,
            "sortKey": "date",
            "totalRecords": 0,
            "records": [],
        }
        return httpx.Response(200, json=body)

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
        body = {
            "page": 1,
            "pageSize": 50,
            "sortKey": "date",
            "totalRecords": 2,
            "records": [
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
            ],
        }
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
        body = {
            "page": 1,
            "pageSize": 50,
            "sortKey": "date",
            "totalRecords": 0,
            "records": [],
        }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = SonarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_grab_history(series_id=999)
        assert result == []
    finally:
        await client.close()


async def test_sonarr_get_grab_history_passes_series_id_param() -> None:
    """SonarrClient.get_grab_history passes seriesId and eventType=1 in URL params."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["seriesId"] == "10"
        assert request.url.params["eventType"] == "1"
        body = {
            "page": 1,
            "pageSize": 50,
            "sortKey": "date",
            "totalRecords": 0,
            "records": [],
        }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = SonarrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        await client.get_grab_history(series_id=10)
    finally:
        await client.close()
