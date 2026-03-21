"""Radarr async API client."""

from __future__ import annotations

from typing import Any

import httpx

from triggarr.clients.base import ArrClient
from triggarr.models.arr import GrabEvent


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

    async def get_library_count(self) -> int:
        """Return the total number of movies in the Radarr library.

        Uses a lightweight paginated request (pageSize=1) to read
        ``totalRecords`` without fetching the full movie list.
        """
        return await self.get_total_records("/api/v3/movie")

    async def get_grab_history(self, movie_id: int) -> list[GrabEvent]:
        """Fetch grab history for a specific movie from Radarr.

        Uses the per-movie history endpoint ``/api/v3/history/movie``
        filtered to grabbed events (``eventType=grabbed``) for the
        given movie ID.  Returns parsed GrabEvent models.
        """
        records = await self.get_json_list(
            "/api/v3/history/movie",
            params={
                "movieId": movie_id,
                "eventType": "grabbed",
            },
        )
        return [GrabEvent.model_validate(r) for r in records]

    async def search_movies(self, movie_ids: list[int]) -> httpx.Response:
        """Trigger a MoviesSearch command for the given movie IDs."""
        return await self.post(
            "/api/v3/command",
            json_data={"name": "MoviesSearch", "movieIds": movie_ids},
        )
