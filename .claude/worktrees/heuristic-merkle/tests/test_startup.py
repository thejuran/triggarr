"""Tests for startup localhost URL detection and Sonarr version detection."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, patch

import httpx
from loguru import logger

from fetcharr.clients.sonarr import SonarrClient
from fetcharr.models.config import ArrConfig, Settings
from fetcharr.startup import check_localhost_urls, collect_secrets, validate_connections


def _make_settings(
    radarr_url: str = "http://radarr:7878",
    radarr_enabled: bool = True,
    sonarr_url: str = "http://sonarr:8989",
    sonarr_enabled: bool = True,
) -> Settings:
    """Build a Settings instance with the given app URLs and enabled flags."""
    return Settings(
        radarr=ArrConfig(
            url=radarr_url,
            api_key="test-key",
            enabled=radarr_enabled,
        ),
        sonarr=ArrConfig(
            url=sonarr_url,
            api_key="test-key",
            enabled=sonarr_enabled,
        ),
    )


def test_localhost_url_logs_warning() -> None:
    """Enabled app with localhost URL triggers a warning."""
    settings = _make_settings(radarr_url="http://localhost:7878")

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        check_localhost_urls(settings)
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    assert "Radarr" in output
    assert "localhost" in output
    assert "host.docker.internal" in output


def test_127_0_0_1_url_logs_warning() -> None:
    """Enabled app with 127.0.0.1 URL triggers a warning."""
    settings = _make_settings(sonarr_url="http://127.0.0.1:8989")

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        check_localhost_urls(settings)
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    assert "Sonarr" in output
    assert "127.0.0.1" in output


def test_ipv6_loopback_url_logs_warning() -> None:
    """Enabled app with ::1 (IPv6 loopback) URL triggers a warning."""
    settings = _make_settings(radarr_url="http://[::1]:7878")

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        check_localhost_urls(settings)
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    assert "Radarr" in output


def test_non_localhost_url_no_warning() -> None:
    """Normal service-name URLs produce no warning."""
    settings = _make_settings(
        radarr_url="http://radarr:7878",
        sonarr_url="http://sonarr:8989",
    )

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        check_localhost_urls(settings)
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    assert output == ""


def test_disabled_app_with_localhost_no_warning() -> None:
    """Disabled app with localhost URL produces no warning (skipped)."""
    # Radarr disabled with localhost -- should be skipped.
    # Sonarr enabled with non-localhost -- satisfies validator, no warning.
    settings = _make_settings(
        radarr_url="http://localhost:7878",
        radarr_enabled=False,
        sonarr_url="http://sonarr:8989",
        sonarr_enabled=True,
    )

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        check_localhost_urls(settings)
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    assert output == ""


# ---------------------------------------------------------------------------
# collect_secrets
# ---------------------------------------------------------------------------


def test_collect_secrets_extracts_all_api_keys() -> None:
    """collect_secrets returns non-empty API key values from all configured apps."""
    settings = Settings(
        radarr=ArrConfig(
            url="http://radarr:7878",
            api_key="radarr-secret",
            enabled=True,
        ),
        sonarr=ArrConfig(
            url="http://sonarr:8989",
            api_key="sonarr-secret",
            enabled=True,
        ),
    )
    result = collect_secrets(settings)
    assert "radarr-secret" in result
    assert "sonarr-secret" in result
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Sonarr API version detection -- unit tests on SonarrClient
# ---------------------------------------------------------------------------


async def test_detect_api_version_parses_v3() -> None:
    """SonarrClient.detect_api_version returns 'v3' for v3 version strings."""

    async def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": "3.0.10.1567"})

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sonarr = SonarrClient("http://test", "fake-key")
        sonarr._client = client
        result = await sonarr.detect_api_version()

    assert result == "v3"


async def test_detect_api_version_parses_v4() -> None:
    """SonarrClient.detect_api_version returns 'v4' for v4 version strings."""

    async def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": "4.0.1.929"})

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sonarr = SonarrClient("http://test", "fake-key")
        sonarr._client = client
        result = await sonarr.detect_api_version()

    assert result == "v4"


async def test_detect_api_version_handles_error() -> None:
    """SonarrClient.detect_api_version falls back to 'v3' on error."""

    async def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sonarr = SonarrClient("http://test", "fake-key")
        sonarr._client = client

        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="WARNING")
        try:
            result = await sonarr.detect_api_version()
        finally:
            logger.remove(handler_id)

    assert result == "v3"
    assert "version detection failed" in sink.getvalue()


# ---------------------------------------------------------------------------
# Sonarr API version detection -- integration tests via validate_connections
# ---------------------------------------------------------------------------


async def test_sonarr_version_detection_v3() -> None:
    """Startup logs 'Detected API v3' after successful Sonarr connection."""
    settings = _make_settings(sonarr_enabled=True, radarr_enabled=False)

    with patch("fetcharr.startup.SonarrClient") as MockSonarrCls:
        mock_client = AsyncMock()
        mock_client.validate_connection = AsyncMock(return_value=True)
        mock_client.detect_api_version = AsyncMock(return_value="v3")
        mock_client.close = AsyncMock()
        MockSonarrCls.return_value = mock_client

        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="INFO")
        try:
            results = await validate_connections(settings)
        finally:
            logger.remove(handler_id)

    assert results["sonarr"] is True
    assert "Detected API v3" in sink.getvalue()


async def test_sonarr_version_detection_v4() -> None:
    """Startup logs 'Detected API v4' after successful Sonarr connection."""
    settings = _make_settings(sonarr_enabled=True, radarr_enabled=False)

    with patch("fetcharr.startup.SonarrClient") as MockSonarrCls:
        mock_client = AsyncMock()
        mock_client.validate_connection = AsyncMock(return_value=True)
        mock_client.detect_api_version = AsyncMock(return_value="v4")
        mock_client.close = AsyncMock()
        MockSonarrCls.return_value = mock_client

        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="INFO")
        try:
            results = await validate_connections(settings)
        finally:
            logger.remove(handler_id)

    assert results["sonarr"] is True
    assert "Detected API v4" in sink.getvalue()


async def test_sonarr_version_detection_failure() -> None:
    """When detect_api_version raises, startup still completes (fallback to v3)."""
    settings = _make_settings(sonarr_enabled=True, radarr_enabled=False)

    with patch("fetcharr.startup.SonarrClient") as MockSonarrCls:
        mock_client = AsyncMock()
        mock_client.validate_connection = AsyncMock(return_value=True)
        mock_client.detect_api_version = AsyncMock(
            side_effect=httpx.ConnectError("refused")
        )
        mock_client.close = AsyncMock()
        MockSonarrCls.return_value = mock_client

        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="INFO")
        try:
            results = await validate_connections(settings)
        finally:
            logger.remove(handler_id)

    # Connection still validated successfully
    assert results["sonarr"] is True
