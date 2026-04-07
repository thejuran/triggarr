"""Lidarr async API client."""

from __future__ import annotations

from typing import Any

import httpx

from triggarr.clients.base import ArrClient
from triggarr.models.arr import GrabEvent, Tag


class LidarrClient(ArrClient):
    """HTTP client for Lidarr API v1.

    Thin wrapper around ArrClient that defines Lidarr-specific
    endpoint paths for wanted/missing and wanted/cutoff album lists.
    Always includes ``includeArtist=true`` for tag filtering support
    (tags live on artist objects in Lidarr).

    Note: Lidarr uses ``/api/v1/`` endpoints, not ``/api/v3/``.
    """

    _status_path = "/api/v1/system/status"

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0, page_size: int = 50) -> None:
        super().__init__(base_url, api_key, timeout, page_size)
        self._app_name = "Lidarr"

    async def get_wanted_missing(self) -> list[dict[str, Any]]:
        """Fetch all wanted/missing albums from Lidarr.

        Includes artist data (``includeArtist=true``) for tag filtering
        support, since tags are stored on artist objects.
        """
        return await self.get_paginated(
            "/api/v1/wanted/missing",
            extra_params={"includeArtist": "true"},
        )

    async def get_wanted_cutoff(self) -> list[dict[str, Any]]:
        """Fetch all albums that don't meet their quality cutoff.

        Includes artist data (``includeArtist=true``) for tag filtering
        support, since tags are stored on artist objects.
        """
        return await self.get_paginated(
            "/api/v1/wanted/cutoff",
            extra_params={"includeArtist": "true"},
        )

    async def get_library_count(self) -> int:
        """Return the total number of artists in the Lidarr library.

        Fetches ``/api/v1/artist`` (non-paginated flat array) and
        counts the entries.
        """
        artist_list = await self.get_json_list("/api/v1/artist")
        return len(artist_list)

    async def get_tags(self) -> list[Tag]:
        """Fetch all tags from the Lidarr instance.

        Overrides base class to use ``/api/v1/tag`` (not ``/api/v3/tag``).
        """
        data = await self.get_json_list("/api/v1/tag")
        return [Tag.model_validate(item) for item in data]

    async def get_grab_history(self, album_id: int) -> list[GrabEvent]:
        """Fetch grab history for a specific album from Lidarr.

        Uses the ``/api/v1/history`` endpoint filtered to grabbed events
        for the given album ID.  Lidarr's history is paginated, so we
        fetch page 1 with a reasonable size to capture recent grabs.

        Note: Lidarr's ``eventType`` query parameter accepts **integers**
        (not strings like Radarr/Sonarr v3).  The enum value for
        ``grabbed`` is ``1`` (Unknown=0, Grabbed=1, ...).
        """
        response = await self.get(
            "/api/v1/history",
            params={
                "albumId": album_id,
                "eventType": 1,
                "page": 1,
                "pageSize": self._page_size,
                "sortKey": "date",
                "sortDirection": "descending",
            },
        )
        data = response.json()
        records = data.get("records", []) if isinstance(data, dict) else data
        return [GrabEvent.model_validate(r) for r in records]

    async def search_albums(self, album_ids: list[int]) -> httpx.Response:
        """Trigger an AlbumSearch command for the given album IDs."""
        return await self.post(
            "/api/v1/command",
            json_data={"name": "AlbumSearch", "albumIds": album_ids},
        )
