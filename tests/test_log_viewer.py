"""Test suite for the redesigned Application Log viewer (Phase 51).

Covers LOG-01 through LOG-06: monospace grid, TAILING indicator,
level-colored rows, per-app source tags, expand/collapse terminal pane,
pause button, level filter dropdown, and server-side filtering.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from triggarr.db import init_db, insert_search_entry
from triggarr.log_buffer import LogEntry, log_buffer
from triggarr.models.config import GeneralConfig
from triggarr.web.routes import STATIC_DIR, router


@pytest.fixture
async def test_app(tmp_path):
    """Build a minimal FastAPI app with mocked state for route testing."""
    log_buffer.clear()
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await init_db(db, db_path)
        await insert_search_entry(db, "Radarr", "missing", "Test Movie")
        app.state.db = db

        app.state.triggarr_state = {
            "radarr": {
                "Default": {
                    "missing_cursor": 3,
                    "cutoff_cursor": 1,
                    "last_run": "2026-01-15T10:30:00Z",
                    "connected": True,
                    "unreachable_since": None,
                    "missing_count": 42,
                    "cutoff_count": 7,
                },
            },
            "sonarr": {
                "Default": {
                    "missing_cursor": 0,
                    "cutoff_cursor": 0,
                    "last_run": None,
                    "connected": None,
                    "unreachable_since": None,
                    "missing_count": None,
                    "cutoff_count": None,
                },
            },
            "lidarr": {
                "Default": {
                    "missing_cursor": 0,
                    "cutoff_cursor": 0,
                    "last_run": None,
                    "connected": None,
                    "unreachable_since": None,
                    "missing_count": None,
                    "cutoff_count": None,
                },
            },
            "search_log": [],
        }

        app.state.settings = make_settings(
            radarr_url="http://radarr:7878",
            radarr_api_key="test-radarr-key",
            radarr_enabled=True,
            sonarr_url="http://sonarr:8989",
            sonarr_api_key="test-sonarr-key",
            sonarr_enabled=True,
            general=GeneralConfig(skip_unreleased=True, tracking_delay_seconds=90),
        )

        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_job.next_run_time = None
        mock_scheduler.get_job.return_value = mock_job
        app.state.scheduler = mock_scheduler

        radarr_client = MagicMock()
        radarr_client.close = AsyncMock()
        sonarr_client = MagicMock()
        sonarr_client.close = AsyncMock()
        lidarr_client = MagicMock()
        lidarr_client.close = AsyncMock()
        app.state.radarr_clients = {"Default": radarr_client}
        app.state.sonarr_clients = {"Default": sonarr_client}
        app.state.lidarr_clients = {"Default": lidarr_client}

        app.state.config_path = tmp_path / "triggarr.toml"
        app.state.state_path = tmp_path / "state.json"
        app.state.search_lock = asyncio.Lock()
        app.state.last_search_time = {}

        yield app


@pytest.fixture
def client(test_app):
    """Create a TestClient for the test app."""
    return TestClient(test_app)


def test_log_viewer_monospace_grid(client):
    """LOG-01: Log rows use Geist Mono with column-aligned timestamp, level, source, message."""
    log_buffer.clear()
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Radarr: grabbed 12 items"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "font-geist-mono" in response.text, "Log rows must use Geist Mono font"
    assert "w-14" in response.text, "Level column must have w-14 fixed width"
    assert "w-20" in response.text, "Source column must have w-20 fixed width"
    assert "shrink-0" in response.text, "Columns must not shrink"


def test_log_viewer_tailing_indicator(client):
    """LOG-02: TAILING badge with pulsing green dot visible in header."""
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "TAILING" in response.text, "Header must show TAILING badge"
    assert "dot-pulse" in response.text, "TAILING badge must have pulsing dot"


def test_log_viewer_error_row_styling(client):
    """LOG-03: ERROR rows have red-tinted background and red left border."""
    log_buffer.clear()
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "ERROR", "Connection refused"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "bg-red-500/5" in response.text, "ERROR row must have red-tinted background"
    assert "border-l-red-500" in response.text, "ERROR row must have red left border"


def test_log_viewer_debug_row_dimmed(client):
    """LOG-03: DEBUG rows are dimmed with opacity-60."""
    log_buffer.clear()
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "DEBUG", "Cursor advanced"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "opacity-60" in response.text, "DEBUG row must be dimmed"


def test_log_viewer_source_tags_radarr(client):
    """LOG-04: Radarr messages get orange source tag."""
    log_buffer.clear()
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Radarr: grabbed 12 items"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "text-orange-400" in response.text, "Radarr source tag must be orange"
    assert "[Radarr]" in response.text or "Radarr" in response.text, "Radarr source tag must be present"


def test_log_viewer_source_tags_sonarr(client):
    """LOG-04: Sonarr messages get blue source tag."""
    log_buffer.clear()
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Sonarr: found 5 episodes"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "text-blue-400" in response.text, "Sonarr source tag must be blue"


def test_log_viewer_source_tags_lidarr(client):
    """LOG-04: Lidarr messages get green source tag."""
    log_buffer.clear()
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Lidarr: synced 3 albums"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "text-green-400" in response.text, "Lidarr source tag must be green"


def test_log_viewer_expand_button(client):
    """LOG-05: Expand button present in header with correct onclick handler."""
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "toggleLogExpand()" in response.text, "Expand button must call toggleLogExpand()"
    assert "scanline-overlay" in response.text, "Log body must contain scanline overlay"
    assert "terminal-pane" in response.text, "Log viewer must have terminal-pane class"


def test_log_viewer_pause_button(client):
    """LOG-05/LOG-06: Pause button present with correct onclick handler and data attribute."""
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "toggleLogPause(this)" in response.text, "Pause button must call toggleLogPause(this)"
    assert "data-pause-btn" in response.text, "Pause button must have data-pause-btn attribute"


def test_log_viewer_level_filter_dropdown(client):
    """LOG-06: Level filter dropdown present with All/ERROR/WARNING/INFO/DEBUG options."""
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    html = response.text
    assert "<select" in html, "Level filter must be a select element"
    for level in ("ERROR", "WARNING", "INFO", "DEBUG"):
        assert f'value="{level}"' in html, f"Filter must have {level} option"


def test_log_viewer_level_filter_server_side(client):
    """LOG-06: ?level=ERROR filters to only ERROR entries server-side."""
    log_buffer.clear()
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "ERROR", "Something broke"))
    log_buffer.add(LogEntry("2026-01-15 10:30:01", "INFO", "All good"))
    response = client.get("/partials/log-viewer?level=ERROR")
    assert response.status_code == 200
    assert "Something broke" in response.text, "ERROR entry must be shown"
    assert "All good" not in response.text, "INFO entry must be filtered out"


def test_log_viewer_invalid_level_shows_all(client):
    """LOG-06: Invalid level parameter shows all entries (no crash)."""
    log_buffer.clear()
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Normal message"))
    response = client.get("/partials/log-viewer?level=BOGUS")
    assert response.status_code == 200
    assert "Normal message" in response.text, "Invalid level should show all entries"
