"""Tests for the scheduler job factory (make_search_job).

Covers: client-None early return and unhandled exception swallowing.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI

from tests.conftest import make_settings
from triggarr.search.scheduler import make_search_job
from triggarr.state import _default_state


async def test_make_search_job_client_none_returns_early():
    """Job returns immediately without error when client is None."""
    app = FastAPI()
    app.state.radarr_client = None
    app.state.search_lock = asyncio.Lock()

    job = make_search_job(app, "radarr", Path("/tmp/state.json"))
    # Should complete without error and without touching other state attrs
    await job()


async def test_make_search_job_exception_swallowed():
    """Job catches and swallows unhandled exceptions from cycle function."""
    app = FastAPI()
    app.state.radarr_client = AsyncMock()
    app.state.search_lock = asyncio.Lock()
    app.state.triggarr_state = _default_state()
    app.state.settings = make_settings()

    with (
        patch(
            "triggarr.search.scheduler.run_radarr_cycle",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
        patch(
            "triggarr.search.scheduler.save_state",
            new=MagicMock(),
        ),
    ):
        job = make_search_job(app, "radarr", Path("/tmp/state.json"))
        # Should NOT raise -- exception is caught internally
        await job()
