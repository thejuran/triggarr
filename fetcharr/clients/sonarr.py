"""Sonarr async API client."""

from __future__ import annotations

from typing import Any

import httpx
import pydantic
from loguru import logger

from fetcharr.clients.base import ArrClient


class SonarrClient(ArrClient):
    """HTTP client for Sonarr API.

    Thin wrapper around ArrClient that defines Sonarr-specific
    endpoint paths for wanted/missing and wanted/cutoff episode lists.
    Always includes ``includeSeries=true`` for human-readable log
    messages and season-level deduplication in the search engine.
    """

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0, page_size: int = 50) -> None:
        super().__init__(base_url, api_key, timeout, page_size)
        self._app_name = "Sonarr"

    async def detect_api_version(self) -> str:
        """Detect whether the Sonarr instance is running v3 or v4.

        Calls ``/api/v3/system/status`` and inspects the ``version``
        field.  This is purely informational -- no behaviour changes
        based on the result.

        Returns:
            ``"v4"`` if the major version is 4+, otherwise ``"v3"``.
        """
        try:
            response = await self._client.get("/api/v3/system/status")
            response.raise_for_status()
            data = response.json()
            version = data["version"]
            if version.startswith("4"):
                return "v4"
            return "v3"
        except (httpx.HTTPError, pydantic.ValidationError, KeyError, Exception) as exc:
            logger.warning(
                "Sonarr: API version detection failed -- assuming v3: {exc}",
                exc=exc,
            )
            return "v3"

    async def get_wanted_missing(self) -> list[dict[str, Any]]:
        """Fetch all wanted/missing episodes from Sonarr.

        Includes series data (``includeSeries=true``) for human-readable
        log messages and season-level deduplication.
        """
        return await self.get_paginated(
            "/api/v3/wanted/missing",
            extra_params={"includeSeries": "true"},
        )

    async def get_wanted_cutoff(self) -> list[dict[str, Any]]:
        """Fetch all episodes that don't meet their quality cutoff.

        Includes series data (``includeSeries=true``) for human-readable
        log messages and season-level deduplication.
        """
        return await self.get_paginated(
            "/api/v3/wanted/cutoff",
            extra_params={"includeSeries": "true"},
        )

    async def search_season(self, series_id: int, season_number: int) -> httpx.Response:
        """Trigger a SeasonSearch command for a specific season."""
        return await self.post(
            "/api/v3/command",
            json_data={
                "name": "SeasonSearch",
                "seriesId": series_id,
                "seasonNumber": season_number,
            },
        )
