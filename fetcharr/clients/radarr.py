"""Radarr async API client."""

from __future__ import annotations

from typing import Any

import httpx

from fetcharr.clients.base import ArrClient
from fetcharr.models.arr import GrabEvent


class RadarrClient(ArrClient):
    """HTTP client for Radarr API.

    Thin wrapper around ArrClient that defines Radarr-specific
    endpoint paths for wanted/missing and wanted/cutoff movie lists.
    """

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0, page_size: int = 50) -> None:
        super().__init__(base_url, api_key, timeout, page_size)
        self._app_name = "Radarr"

    async def get_wanted_missing(self) -> list[dict[str, Any]]:
        """Fetch all wanted/missing movies from Radarr."""
        return await self.get_paginated("/api/v3/wanted/missing")

    async def get_wanted_cutoff(self) -> list[dict[str, Any]]:
        """Fetch all movies that don't meet their quality cutoff."""
        return await self.get_paginated("/api/v3/wanted/cutoff")

    async def get_grab_history(self, movie_id: int) -> list[GrabEvent]:
        """Fetch grab history for a specific movie from Radarr.

        Queries /api/v3/history filtered to grabbed events (eventType=1)
        for the given movie ID.  Returns parsed GrabEvent models.
        """
        records = await self.get_paginated(
            "/api/v3/history",
            extra_params={
                "movieId": movie_id,
                "eventType": 1,
                "sortDirection": "descending",
            },
        )
        return [GrabEvent.model_validate(r) for r in records]

    async def search_movies(self, movie_ids: list[int]) -> httpx.Response:
        """Trigger a MoviesSearch command for the given movie IDs."""
        return await self.post(
            "/api/v3/command",
            json_data={"name": "MoviesSearch", "movieIds": movie_ids},
        )
