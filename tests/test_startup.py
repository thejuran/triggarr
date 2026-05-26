"""Tests for startup localhost URL detection and Sonarr version detection."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from loguru import logger
from pydantic import SecretStr

from triggarr.clients.sonarr import SonarrClient
from triggarr.models.config import AuthConfig, InstanceConfig, Settings
from triggarr.startup import (
    _warn_if_session_secret_short,
    check_localhost_urls,
    collect_secrets,
    startup,
    validate_connections,
)


def _make_settings(
    radarr_url: str = "http://radarr:7878",
    radarr_enabled: bool = True,
    sonarr_url: str = "http://sonarr:8989",
    sonarr_enabled: bool = True,
) -> Settings:
    """Build a Settings instance with the given app URLs and enabled flags."""
    return Settings(
        radarr={"Default": InstanceConfig(
            url=radarr_url,
            api_key="test-key",
            enabled=radarr_enabled,
        )},
        sonarr={"Default": InstanceConfig(
            url=sonarr_url,
            api_key="test-key",
            enabled=sonarr_enabled,
        )},
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
# SEC-04: _warn_if_session_secret_short (Phase 66, Plan 03)
# ---------------------------------------------------------------------------


def test_warn_if_session_secret_short() -> None:
    """Short session_secret with completed setup triggers a single WARNING (D-13)."""
    settings = Settings(
        auth=AuthConfig(
            method="Forms",
            username="admin",
            password_hash=SecretStr("$2b$12$dummy"),
            api_key=SecretStr("x" * 32),
            session_secret=SecretStr("ZZZSENTINELZZZ"),  # 14 chars -- well under 32; sentinel avoids substring collision with "shorter" in warning
        ),
    )

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        _warn_if_session_secret_short(settings)
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    # D-14: warning names the field
    assert "auth.session_secret is shorter than 32 characters" in output
    # D-14: warning includes remediation hint (Unicode arrow U+2192 preserved)
    assert "regenerate via Settings → Security or set a longer value in config.toml" in output
    # SecretStr discipline: secret VALUE never leaks into the log line
    assert "ZZZSENTINELZZZ" not in output


def test_no_warn_when_session_secret_long() -> None:
    """A normal-length (>= 32 chars) session_secret produces no warning (D-13 trigger)."""
    settings = Settings(
        auth=AuthConfig(
            method="Forms",
            username="admin",
            password_hash=SecretStr("$2b$12$dummy"),
            api_key=SecretStr("x" * 32),
            session_secret=SecretStr("x" * 64),  # production length (generate_session_secret)
        ),
    )

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        _warn_if_session_secret_short(settings)
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    assert "session_secret" not in output


def test_no_warn_when_needs_setup() -> None:
    """Pre-setup state (needs_setup=True, empty username) skips the warning (D-13 guard)."""
    # Default AuthConfig: username="" -> needs_setup=True, session_secret="" (len 0 < 32)
    settings = Settings(auth=AuthConfig())

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        _warn_if_session_secret_short(settings)
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    assert "session_secret" not in output


# ---------------------------------------------------------------------------
# collect_secrets
# ---------------------------------------------------------------------------


def test_collect_secrets_extracts_all_api_keys() -> None:
    """collect_secrets returns non-empty API key values from all configured instances."""
    settings = Settings(
        radarr={"Default": InstanceConfig(
            url="http://radarr:7878",
            api_key="radarr-secret",
            enabled=True,
        )},
        sonarr={"Default": InstanceConfig(
            url="http://sonarr:8989",
            api_key="sonarr-secret",
            enabled=True,
        )},
    )
    result = collect_secrets(settings)
    assert "radarr-secret" in result
    assert "sonarr-secret" in result
    assert len(result) == 2


async def test_startup_default_config_path_follows_current_config_dir(
    monkeypatch, tmp_path: Path
) -> None:
    """startup() without an explicit path should use the current TRIGGARR_CONFIG_DIR."""
    monkeypatch.setenv("TRIGGARR_CONFIG_DIR", str(tmp_path))
    seen_paths: list[Path] = []

    def _fake_ensure_config(path: Path) -> Settings:
        seen_paths.append(path)
        return Settings()

    with (
        patch("triggarr.startup.ensure_config", side_effect=_fake_ensure_config),
        patch("triggarr.startup.setup_logging"),
        patch("triggarr.startup.print_banner"),
        patch("triggarr.startup.validate_connections", new_callable=AsyncMock) as mock_validate,
    ):
        settings = await startup()

    assert isinstance(settings, Settings)
    assert seen_paths == [tmp_path / "triggarr.toml"]
    mock_validate.assert_not_called()


async def test_main_run_wires_current_config_dir_into_startup_and_lifespan(
    monkeypatch, tmp_path: Path
) -> None:
    """The real module entrypoint should pass env-derived config/state paths onward."""
    from contextlib import asynccontextmanager

    import triggarr.__main__ as main_module

    monkeypatch.setenv("TRIGGARR_CONFIG_DIR", str(tmp_path))
    settings = Settings()
    seen_lifespan_args: list[tuple[Settings, Path, Path]] = []

    @asynccontextmanager
    async def _fake_lifespan(_app):
        yield

    def _fake_create_lifespan(settings_arg: Settings, state_path: Path, config_path: Path):
        seen_lifespan_args.append((settings_arg, state_path, config_path))
        return _fake_lifespan

    class _FakeServer:
        def __init__(self, _config) -> None:
            pass

        async def serve(self) -> None:
            return None

    with (
        patch("triggarr.startup.startup", AsyncMock(return_value=settings)) as mock_startup,
        patch.object(main_module, "create_lifespan", side_effect=_fake_create_lifespan),
        patch.object(main_module.uvicorn, "Server", _FakeServer),
    ):
        await main_module._run()

    expected_config_path = tmp_path / "triggarr.toml"
    expected_state_path = tmp_path / "state.json"
    mock_startup.assert_awaited_once_with(expected_config_path)
    assert seen_lifespan_args == [(settings, expected_state_path, expected_config_path)]


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

    with patch("triggarr.startup.SonarrClient") as MockSonarrCls:
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

    assert results["sonarr/Default"] is True
    assert "Detected API v3" in sink.getvalue()


async def test_sonarr_version_detection_v4() -> None:
    """Startup logs 'Detected API v4' after successful Sonarr connection."""
    settings = _make_settings(sonarr_enabled=True, radarr_enabled=False)

    with patch("triggarr.startup.SonarrClient") as MockSonarrCls:
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

    assert results["sonarr/Default"] is True
    assert "Detected API v4" in sink.getvalue()


async def test_sonarr_version_detection_failure() -> None:
    """detect_api_version handles errors internally -- startup gets fallback 'v3'."""
    settings = _make_settings(sonarr_enabled=True, radarr_enabled=False)

    with patch("triggarr.startup.SonarrClient") as MockSonarrCls:
        mock_client = AsyncMock()
        mock_client.validate_connection = AsyncMock(return_value=True)
        # detect_api_version handles errors internally and returns "v3"
        mock_client.detect_api_version = AsyncMock(return_value="v3")
        mock_client.close = AsyncMock()
        MockSonarrCls.return_value = mock_client

        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="INFO")
        try:
            results = await validate_connections(settings)
        finally:
            logger.remove(handler_id)

    # Connection still validated successfully
    assert results["sonarr/Default"] is True
    # Version was logged
    log_output = sink.getvalue()
    assert "Detected API v3" in log_output


# ---------------------------------------------------------------------------
# BUG-01: validate_connections overwrites results -- should key by instance
# ---------------------------------------------------------------------------


def _make_multi_instance_settings(
    radarr_count: int = 2,
    sonarr_count: int = 2,
) -> Settings:
    """Build Settings with multiple enabled instances per app type."""
    radarr_instances = {}
    for i in range(radarr_count):
        name = "Default" if i == 0 else f"Instance{i}"
        radarr_instances[name] = InstanceConfig(
            url=f"http://radarr{i}:7878",
            api_key=f"radarr-key-{i}",
            enabled=True,
        )
    sonarr_instances = {}
    for i in range(sonarr_count):
        name = "Default" if i == 0 else f"Instance{i}"
        sonarr_instances[name] = InstanceConfig(
            url=f"http://sonarr{i}:8989",
            api_key=f"sonarr-key-{i}",
            enabled=True,
        )
    return Settings(radarr=radarr_instances, sonarr=sonarr_instances)


async def test_validate_connections_multi_radarr_returns_both() -> None:
    """validate_connections with 2 enabled Radarr instances returns results for both (BUG-01)."""
    settings = _make_multi_instance_settings(radarr_count=2, sonarr_count=0)

    with patch("triggarr.startup.RadarrClient") as MockRadarrCls:
        mock_client = AsyncMock()
        mock_client.validate_connection = AsyncMock(return_value=True)
        mock_client.close = AsyncMock()
        MockRadarrCls.return_value = mock_client

        results = await validate_connections(settings)

    # Should have TWO entries, keyed by instance name
    radarr_keys = [k for k in results if k.startswith("radarr")]
    assert len(radarr_keys) == 2, f"Expected 2 radarr results, got {radarr_keys}"
    assert all(results[k] is True for k in radarr_keys)


async def test_validate_connections_multi_sonarr_returns_both() -> None:
    """validate_connections with 2 enabled Sonarr instances returns results for both (BUG-01)."""
    settings = _make_multi_instance_settings(radarr_count=0, sonarr_count=2)

    with patch("triggarr.startup.SonarrClient") as MockSonarrCls:
        mock_client = AsyncMock()
        mock_client.validate_connection = AsyncMock(return_value=True)
        mock_client.detect_api_version = AsyncMock(return_value="v3")
        mock_client.close = AsyncMock()
        MockSonarrCls.return_value = mock_client

        results = await validate_connections(settings)

    sonarr_keys = [k for k in results if k.startswith("sonarr")]
    assert len(sonarr_keys) == 2, f"Expected 2 sonarr results, got {sonarr_keys}"
    assert all(results[k] is True for k in sonarr_keys)


# ---------------------------------------------------------------------------
# Sonarr API version detection -- edge cases (Phase 46, Plan 02)
# ---------------------------------------------------------------------------


async def test_detect_api_version_future_major() -> None:
    """detect_api_version returns 'v3' for future major version 5.x (API-03)."""

    async def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": "5.0.0.100"})

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sonarr = SonarrClient("http://test", "fake-key")
        sonarr._client = client
        result = await sonarr.detect_api_version()

    assert result == "v3"


async def test_detect_api_version_empty_version() -> None:
    """detect_api_version returns 'v3' for empty version string (API-03)."""

    async def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": ""})

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sonarr = SonarrClient("http://test", "fake-key")
        sonarr._client = client
        result = await sonarr.detect_api_version()

    assert result == "v3"


async def test_detect_api_version_missing_version_key() -> None:
    """detect_api_version returns 'v3' when version key is missing (API-03)."""

    async def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"appName": "Sonarr"})

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sonarr = SonarrClient("http://test", "fake-key")
        sonarr._client = client
        result = await sonarr.detect_api_version()

    assert result == "v3"


async def test_detect_api_version_beta_format() -> None:
    """detect_api_version returns 'v4' for beta version string 4.0.0-beta1 (API-03)."""

    async def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"version": "4.0.0-beta1"})

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sonarr = SonarrClient("http://test", "fake-key")
        sonarr._client = client
        result = await sonarr.detect_api_version()

    assert result == "v4"


async def test_detect_api_version_connect_error_fallback() -> None:
    """detect_api_version returns 'v3' on ConnectError (API-03)."""

    async def _handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        sonarr = SonarrClient("http://test", "fake-key")
        sonarr._client = client
        result = await sonarr.detect_api_version()

    assert result == "v3"
