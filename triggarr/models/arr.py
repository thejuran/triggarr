"""Response models for *arr API data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


def _coerce_int_or_none(value: Any) -> int | None:
    """Coerce a raw identity value to a real int, rejecting bool/float/str.

    *arr identity fields (ids, season/episode numbers) must be real JSON
    integers to be trusted; anything else (including a numeric-looking
    string or a bool, which is technically an int subclass) is untrustworthy
    and degrades to None rather than raising.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


class PaginatedResponse(BaseModel):
    """Shared pagination envelope for all *arr API list endpoints.

    Both Radarr and Sonarr return paginated results in this format
    for wanted/missing and wanted/cutoff endpoints.
    """

    model_config = ConfigDict(extra="ignore")

    page: int
    pageSize: int
    sortKey: str
    totalRecords: int
    records: list[dict[str, Any]]


class RawPaginatedResponse(PaginatedResponse):
    """Pagination envelope whose records are left unvalidated.

    The envelope fields are still validated; ``records`` may hold any JSON
    value, including null or a string. Used only for wanted-list fetches whose
    caller skips and counts non-object records per item (ROBUST-01), so one bad
    record no longer rejects the whole page.
    """

    records: list[Any]


class EpisodeSummary(BaseModel):
    """Minimal Sonarr episode identity nested in a grab event.

    Only canonical Sonarr numbering (``seasonNumber``, ``episodeNumber``)
    is modelled -- Sonarr's alternate scene-numbering fields are
    deliberately not modelled so matching logic can never accidentally
    read them. ``id``/``seriesId`` are modelled so a grab's episode-level
    identity can be cross-checked against its top-level ``episodeId``/
    ``seriesId`` (Phase 81 ATTR-01/R2/R6). Extra fields are ignored.
    """

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    seriesId: int | None = None
    seasonNumber: int | None = None
    episodeNumber: int | None = None

    @field_validator("id", "seriesId", "seasonNumber", "episodeNumber", mode="before")
    @classmethod
    def _validate_identity_fields(cls, value: Any) -> int | None:
        return _coerce_int_or_none(value)


class GrabEvent(BaseModel):
    """A single grab event from *arr history API.

    Represents a 'grabbed' event where the *arr app sent a release
    to a download client.  Extra fields from the API are ignored.
    ``episodeId``/``seriesId``/``episode`` are Sonarr-only (populated
    when the history request used ``includeEpisode=true``); Radarr and
    Lidarr responses never carry them, so they stay None.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    date: str
    eventType: str
    sourceTitle: str = ""
    episodeId: int | None = None
    seriesId: int | None = None
    episode: EpisodeSummary | None = None

    @field_validator("episodeId", "seriesId", mode="before")
    @classmethod
    def _validate_top_level_identity(cls, value: Any) -> int | None:
        return _coerce_int_or_none(value)

    @field_validator("episode", mode="before")
    @classmethod
    def _validate_episode(cls, value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        return value


class Tag(BaseModel):
    """A tag from the *arr /api/v3/tag endpoint.

    Used for tag name-to-ID resolution during search filtering.
    Extra fields from the API response are ignored.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    label: str


class SystemStatus(BaseModel):
    """Minimal system status from /api/v3/system/status.

    Only the version string is needed for startup logging.
    Extra fields from the API response are ignored.
    """

    model_config = ConfigDict(extra="ignore")

    version: str
