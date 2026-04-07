"""Base async HTTP client for *arr applications."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import httpx
import pydantic
from loguru import logger

from triggarr.models.arr import GrabEvent, PaginatedResponse, SystemStatus, Tag


class ArrClient(ABC):
    """Base httpx async client wrapping *arr API communication.

    Provides paginated fetching, retry logic, and connection validation.
    Subclasses set ``_app_name`` and define endpoint-specific methods.
    """

    _status_path: str = "/api/v3/system/status"
    """API path for system/status endpoint. Override in subclasses with different API versions."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0, page_size: int = 50) -> None:
        self._app_name: str = ""
        self._page_size = page_size
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "X-Api-Key": api_key,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout),
        )

    # ------------------------------------------------------------------
    # Low-level HTTP methods
    # ------------------------------------------------------------------

    async def _request_with_retry(
        self, method: str, path: str, **kwargs: Any
    ) -> httpx.Response:
        """Execute an HTTP request with a single retry on failure.

        On the first failure (HTTP status error, connection error, or timeout),
        wait 2 seconds and retry once.  If the retry also fails, log a warning
        and re-raise the exception.
        """
        try:
            response = await self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response
        except (httpx.HTTPStatusError, httpx.TransportError):
            logger.debug(
                "{app}: Request to {path} failed, retrying in 2s",
                app=self._app_name,
                path=path,
            )
            await asyncio.sleep(2)
            try:
                response = await self._client.request(method, path, **kwargs)
                response.raise_for_status()
                return response
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                logger.warning(
                    "{app}: Retry failed for {path}: {exc}",
                    app=self._app_name,
                    path=path,
                    exc=(
                        f"HTTP {exc.response.status_code}"
                        if isinstance(exc, httpx.HTTPStatusError)
                        else type(exc).__name__
                    ),
                )
                raise

    async def get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """Send a GET request to the *arr API."""
        return await self._request_with_retry("GET", path, params=params)

    async def post(self, path: str, json_data: dict[str, Any]) -> httpx.Response:
        """Send a POST request to the *arr API."""
        return await self._request_with_retry("POST", path, json=json_data)

    # ------------------------------------------------------------------
    # Non-paginated list fetching
    # ------------------------------------------------------------------

    async def get_json_list(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch a non-paginated JSON array from an *arr endpoint.

        Used for per-item endpoints (e.g. ``/api/v3/history/movie``,
        ``/api/v3/history/series``) that return a flat JSON array
        instead of a paginated envelope.
        """
        response = await self.get(path, params=params)
        data = response.json()
        if not isinstance(data, list):
            raise ValueError(
                f"Expected JSON array from {path}, got {type(data).__name__}"
            )
        logger.debug(
            "Fetched {count} items from {path}",
            count=len(data),
            path=path,
        )
        return data

    # ------------------------------------------------------------------
    # Tag fetching
    # ------------------------------------------------------------------

    async def get_tags(self) -> list[Tag]:
        """Fetch all tags from the *arr instance.

        Calls ``/api/v3/tag`` which returns a flat JSON array of
        ``{id, label}`` objects.  Each item is validated into a
        :class:`Tag` model.
        """
        data = await self.get_json_list("/api/v3/tag")
        return [Tag.model_validate(item) for item in data]

    # ------------------------------------------------------------------
    # Lightweight count
    # ------------------------------------------------------------------

    async def get_total_records(self, path: str) -> int:
        """Return ``totalRecords`` from a paginated endpoint without fetching all pages.

        Requests a single page with ``pageSize=1`` and reads the
        ``totalRecords`` field from the paginated response envelope.
        """
        params: dict[str, Any] = {"page": 1, "pageSize": 1, "sortKey": "id"}
        response = await self.get(path, params=params)
        data = PaginatedResponse.model_validate(response.json())
        return data.totalRecords

    # ------------------------------------------------------------------
    # Paginated fetching
    # ------------------------------------------------------------------

    async def get_paginated(
        self,
        path: str,
        page_size: int | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all pages from a paginated *arr endpoint.

        Pages are 1-indexed.  Pagination terminates when the response
        contains zero records or when all records have been retrieved.
        Uses ``self._page_size`` as default when *page_size* is not provided.
        """
        all_records: list[dict[str, Any]] = []
        page = 1
        extra = extra_params or {}
        effective_page_size = page_size if page_size is not None else self._page_size
        total_records: int | None = None

        while True:
            params: dict[str, Any] = {
                "page": page,
                "pageSize": effective_page_size,
                "sortKey": "id",
                **extra,
            }
            response = await self.get(path, params=params)
            data = PaginatedResponse.model_validate(response.json())

            # Lock totalRecords from first page to prevent infinite loops
            if total_records is None:
                total_records = data.totalRecords

            # Handle zero total records immediately
            if total_records == 0:
                logger.debug(
                    "Fetched 0 items from {path} (0 total)",
                    path=path,
                )
                return []

            all_records.extend(data.records)

            # Terminate when we have all records or page came back empty
            if len(data.records) == 0 or page * effective_page_size >= total_records:
                break

            page += 1

        logger.debug(
            "Fetched {count} items from {path} ({total} total)",
            count=len(all_records),
            path=path,
            total=total_records,
        )
        return all_records

    # ------------------------------------------------------------------
    # Connection validation
    # ------------------------------------------------------------------

    async def validate_connection(self) -> bool:
        """Validate the connection to the *arr application.

        Calls the system/status endpoint (``_status_path`` class attribute)
        and returns True on success.  Returns False (with appropriate logging)
        for auth failures, connection errors, and timeouts.
        """
        try:
            response = await self._client.get(self._status_path)
            response.raise_for_status()
            status = SystemStatus.model_validate(response.json())
            logger.info(
                "Connected to {app} v{version}",
                app=self._app_name,
                version=status.version,
            )
            return True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                logger.error(
                    "{app}: API key is invalid (401 Unauthorized)",
                    app=self._app_name,
                )
            else:
                logger.warning(
                    "{app}: Unexpected HTTP error: {exc}",
                    app=self._app_name,
                    exc=exc,
                )
            return False
        except httpx.ConnectError:
            logger.warning(
                "{app}: Connection refused at configured URL",
                app=self._app_name,
            )
            return False
        except httpx.TimeoutException:
            logger.warning(
                "{app}: Connection timed out (30s)",
                app=self._app_name,
            )
            return False
        except pydantic.ValidationError as exc:
            logger.warning(
                "{app}: Unexpected API response format: {exc}",
                app=self._app_name,
                exc=exc,
            )
            return False

    # ------------------------------------------------------------------
    # Abstract methods — must be implemented by subclasses
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_grab_history(self, item_id: int) -> list[GrabEvent]:
        """Fetch grab history for a specific item from the *arr instance.

        Must be implemented by each subclass with the appropriate API path
        and response parsing for that application.
        """
        ...

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()

    async def __aenter__(self) -> ArrClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
