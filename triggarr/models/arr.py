"""Response models for *arr API data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class PaginatedResponse(BaseModel):
    """Shared pagination envelope for all *arr API list endpoints.

    Both Radarr and Sonarr return paginated results in this format
    for wanted/missing and wanted/cutoff endpoints.
    """

    page: int
    pageSize: int
    sortKey: str
    totalRecords: int
    records: list[dict[str, Any]]


class SystemStatus(BaseModel):
    """Minimal system status from /api/v3/system/status.

    Only the version string is needed for startup logging.
    Extra fields from the API response are ignored.
    """

    model_config = ConfigDict(extra="ignore")

    version: str
