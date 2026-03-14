"""Tests for the update check module.

Covers version parsing, update detection, and silent failure on HTTP errors.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from triggarr.update_check import _parse_version, check_for_update


@pytest.mark.parametrize(
    ("version_str", "expected"),
    [
        ("v2.3.0", (2, 3, 0)),
        ("0.1.0", (0, 1, 0)),
        ("invalid", (0,)),
        ("", (0,)),
        ("v2.3.0-rc.1", (2, 3, 0)),
        ("0.1.0.dev1", (0, 1, 0)),
        ("1.2.3-beta", (1, 2, 3)),
    ],
)
def test_parse_version(version_str: str, expected: tuple[int, ...]) -> None:
    """_parse_version parses version strings into integer tuples."""
    assert _parse_version(version_str) == expected


async def test_update_available() -> None:
    """check_for_update returns update_available=True when remote > current."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "tag_name": "v2.0.0",
        "html_url": "https://github.com/thejuran/triggarr/releases/tag/v2.0.0",
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("triggarr.update_check.httpx.AsyncClient", return_value=mock_client):
        result = await check_for_update()

    assert result is not None
    assert result["update_available"] is True
    assert result["latest_version"] == "2.0.0"
    assert result["html_url"] == "https://github.com/thejuran/triggarr/releases/tag/v2.0.0"


async def test_no_update() -> None:
    """check_for_update returns update_available=False when remote == current."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "tag_name": "v0.1.0",
        "html_url": "https://github.com/thejuran/triggarr/releases/tag/v0.1.0",
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("triggarr.update_check.httpx.AsyncClient", return_value=mock_client):
        result = await check_for_update()

    assert result is not None
    assert result["update_available"] is False


async def test_silent_failure_http_error() -> None:
    """check_for_update returns None on HTTP error (silent fail)."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))

    with patch("triggarr.update_check.httpx.AsyncClient", return_value=mock_client):
        result = await check_for_update()

    assert result is None


async def test_silent_failure_timeout() -> None:
    """check_for_update returns None on timeout (silent fail)."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timed out"))

    with patch("triggarr.update_check.httpx.AsyncClient", return_value=mock_client):
        result = await check_for_update()

    assert result is None


async def test_rejects_non_github_html_url() -> None:
    """check_for_update returns None when html_url is not a GitHub URL."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "tag_name": "v2.0.0",
        "html_url": "javascript:alert(1)",
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("triggarr.update_check.httpx.AsyncClient", return_value=mock_client):
        result = await check_for_update()

    assert result is None
