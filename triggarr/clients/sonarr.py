"""Sonarr async API client."""

from __future__ import annotations

from typing import Any

import httpx
import pydantic
from loguru import logger
from pydantic import SecretStr

from triggarr.clients.base import ArrClient, _sanitize_exc
from triggarr.models.arr import EpisodeSummary, GrabEvent


class SonarrClient(ArrClient):
    """HTTP client for Sonarr API.

    Thin wrapper around ArrClient that defines Sonarr-specific
    endpoint paths for wanted/missing and wanted/cutoff episode lists.
    Always includes ``includeSeries=true`` for human-readable log
    messages and season-level deduplication in the search engine.
    """

    def __init__(self, base_url: str, api_key: SecretStr, timeout: float = 30.0, page_size: int = 50) -> None:
        super().__init__(base_url, api_key, timeout, page_size)
        self._app_name = "Sonarr"

    async def detect_api_version(self) -> str:
        """Detect the Sonarr application major version (v3, v4 or v5).

        Calls ``/api/v3/system/status`` and inspects the ``version``
        field. This reports the application major only -- it never
        selects API routes; every call stays on ``/api/v3`` regardless
        of the detected major (Sonarr v5 still serves the ``/api/v3``
        controller tree).

        Returns:
            ``"v3"``, ``"v4"`` or ``"v5"`` when the major version is
            confirmed, otherwise ``"unknown"`` (non-string reply,
            unrecognized major, or a request failure).
        """
        try:
            response = await self._client.get("/api/v3/system/status")
            response.raise_for_status()
            data = response.json()
            version = data["version"]
            if not isinstance(version, str):
                logger.warning(
                    "Sonarr: API version reply was not a string -- reporting unknown, continuing with /api/v3 endpoints"
                )
                return "unknown"
            if version.startswith("3"):
                return "v3"
            if version.startswith("4"):
                return "v4"
            if version.startswith("5"):
                return "v5"
            logger.warning(
                "Sonarr: unrecognized API version reply -- reporting unknown, continuing with /api/v3 endpoints"
            )
            return "unknown"
        except (httpx.HTTPError, pydantic.ValidationError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "Sonarr: API version detection failed -- reporting unknown, continuing with /api/v3 endpoints: {exc}",
                exc=_sanitize_exc(exc),
            )
            return "unknown"

    async def get_wanted_missing(self, *, allow_non_object_records: bool = False) -> list[Any]:
        """Fetch all wanted/missing episodes from Sonarr.

        Includes series data (``includeSeries=true``) for human-readable
        log messages and season-level deduplication.
        """
        return await self.get_paginated(
            "/api/v3/wanted/missing",
            extra_params={"includeSeries": "true"},
            allow_non_object_records=allow_non_object_records,
        )

    async def get_wanted_cutoff(self, *, allow_non_object_records: bool = False) -> list[Any]:
        """Fetch all episodes that don't meet their quality cutoff.

        Includes series data (``includeSeries=true``) for human-readable
        log messages and season-level deduplication.
        """
        return await self.get_paginated(
            "/api/v3/wanted/cutoff",
            extra_params={"includeSeries": "true"},
            allow_non_object_records=allow_non_object_records,
        )

    async def get_library_count(self) -> int:
        """Return the total number of episodes across all series in Sonarr.

        Fetches ``/api/v3/series`` and sums each series'
        ``statistics.episodeCount`` (total tracked episodes).

        Note: Sonarr's ``/api/v3/series`` is a non-paginated flat array,
        so this downloads all series metadata.  The response is typically
        much smaller than the equivalent Radarr movie list, but callers
        should still handle failures gracefully (e.g. timeouts on very
        large libraries).
        """
        series_list = await self.get_json_list("/api/v3/series")
        return sum(
            s.get("statistics", {}).get("episodeCount", 0)
            for s in series_list
        )

    async def get_grab_history(self, series_id: int) -> list[GrabEvent]:
        """Fetch grab history for a specific series from Sonarr.

        Uses the per-series history endpoint ``/api/v3/history/series``
        filtered to grabbed events (``eventType=grabbed``) for the
        given series ID, with ``includeEpisode=true`` so each grab
        carries Sonarr's own episode/season identity. Returns parsed
        GrabEvent models.
        """
        records = await self.get_json_list(
            "/api/v3/history/series",
            params={
                "seriesId": series_id,
                "eventType": "grabbed",
                "includeEpisode": "true",
            },
        )
        return [GrabEvent.model_validate(r) for r in records]

    async def get_series_episodes(self, series_id: int) -> list[EpisodeSummary]:
        """Fetch every episode of a series from Sonarr (v5 episode-identity resolution only).

        Used only to resolve a v5 grab-history record's episode/season
        identity when its nested ``episode`` object is absent or lacks a
        valid season (Sonarr v5 omits it entirely; v4 never needs this
        method). One GET to ``/api/v3/episode?seriesId=<id>`` (``X-Api-Key``
        auth via the base client) covers a season pack or complete-series
        pack of any size in a single request. No retry -- a transient
        failure here defers resolution to the next tracking check rather
        than doubling request latency.

        Raises:
            ValueError: If the response body is not a JSON array.
            httpx.HTTPError: On a non-2xx response or transport failure.
            pydantic.ValidationError: If a record fails model validation.
        """
        response = await self._client.get("/api/v3/episode", params={"seriesId": series_id})
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise ValueError(f"Expected JSON array from /api/v3/episode, got {type(data).__name__}")
        return [EpisodeSummary.model_validate(item) for item in data if isinstance(item, dict)]

    async def get_episode(self, episode_id: int) -> EpisodeSummary:
        """Fetch a single episode by id (v5 episode-identity resolution fallback only).

        Used only as a fallback for an episode id missing from
        :meth:`get_series_episodes`'s result (rare: a deleted or moved
        episode). One GET to ``/api/v3/episode/{episode_id}``, no retry.

        Raises:
            httpx.HTTPError: On a non-2xx response (including 404 when the
                episode id does not exist) or transport failure.
            pydantic.ValidationError: If the response body fails model
                validation.
        """
        response = await self._client.get(f"/api/v3/episode/{episode_id}")
        response.raise_for_status()
        return EpisodeSummary.model_validate(response.json())

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
