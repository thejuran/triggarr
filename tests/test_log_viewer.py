"""Test suite for the redesigned log viewer (Phase 62).

Covers LOG-01 through LOG-03: Phosphor icon controls, System Logs title,
TAILING badge with border container, GRAB row keyword highlights,
font-mono level filter, and server-side filtering.
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


@pytest.fixture(autouse=True)
async def _clear_log_buffer():
    """Reset shared log_buffer before and after each test."""
    log_buffer.clear()
    yield
    log_buffer.clear()


@pytest.fixture
async def test_app(tmp_path):
    """Build a minimal FastAPI app with mocked state for route testing."""
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
    """LOG-01: Log rows use mono font with column-aligned timestamp, level, source, message."""
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Radarr: grabbed 12 items"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "font-mono" in response.text, "Log rows must use mono font"
    assert "w-14" in response.text, "Level column must have w-14 fixed width"
    assert "shrink-0" in response.text, "Columns must not shrink"


def test_log_viewer_tailing_indicator(client):
    """LOG-02: TAILING badge with pulsing green dot in border container."""
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "Tailing" in response.text, "Header must show Tailing badge"
    assert "dot-pulse" in response.text, "TAILING badge must have pulsing dot"
    assert "bg-triggarr-bg border border-triggarr-border" in response.text, (
        "TAILING badge must be in border container per D-13"
    )
    assert "text-triggarr-primary" in response.text, "TAILING text must use triggarr-primary color"
    assert "font-mono" in response.text, "TAILING badge must use mono font"


def test_log_viewer_error_row_styling(client):
    """LOG-03: ERROR rows have red-tinted background and red left border."""
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "ERROR", "Connection refused"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "bg-red-500/5" in response.text, "ERROR row must have red-tinted background"
    assert "border-l-red-500" in response.text, "ERROR row must have red left border"


def test_log_viewer_debug_row_dimmed(client):
    """LOG-03: DEBUG rows are dimmed with opacity-60."""
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "DEBUG", "Cursor advanced"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "opacity-60" in response.text, "DEBUG row must be dimmed"


def test_log_viewer_source_tags_radarr(client):
    """LOG-04: Radarr messages get triggarr-radarr source tag."""
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Radarr: grabbed 12 items"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "text-triggarr-radarr" in response.text, "Radarr source tag must use triggarr-radarr token"
    assert "[Radarr]" in response.text or "Radarr" in response.text, "Radarr source tag must be present"


def test_log_viewer_source_tags_sonarr(client):
    """LOG-04: Sonarr messages get triggarr-sonarr source tag."""
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Sonarr: found 5 episodes"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "text-triggarr-sonarr" in response.text, "Sonarr source tag must use triggarr-sonarr token"


def test_log_viewer_source_tags_lidarr(client):
    """LOG-04: Lidarr messages get green source tag."""
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Lidarr: synced 3 albums"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "text-triggarr-green" in response.text, "Lidarr source tag must use triggarr-green token"


def test_log_viewer_expand_button(client):
    """LOG-01: Expand button uses Phosphor icon with correct onclick handler."""
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "toggleLogExpand()" in response.text, "Expand button must call toggleLogExpand()"
    assert "ph ph-corners-out" in response.text, "Expand button must use Phosphor corners-out icon per D-12"
    assert "bg-[#0b1120]" in response.text, "Log viewer must use dark background per D-16"


def test_log_viewer_pause_button(client):
    """LOG-01: Pause button uses Phosphor icon with correct onclick handler."""
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "toggleLogPause(this)" in response.text, "Pause button must call toggleLogPause(this)"
    assert "data-pause-btn" in response.text, "Pause button must have data-pause-btn attribute"
    assert "ph ph-pause" in response.text, "Pause button must use Phosphor pause icon per D-12"


def test_log_viewer_level_filter_dropdown(client):
    """LOG-03: Level filter dropdown with Level: prefix format and font-mono styling."""
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    html = response.text
    assert "<select" in html, "Level filter must be a select element"
    for level in ("ERROR", "WARNING", "INFO", "DEBUG"):
        assert f'value="{level}"' in html, f"Filter must have {level} option value"
    assert "Level: INFO" in html, "Filter must display 'Level: INFO' format per D-14"
    assert "Level: WARN" in html, "Filter must display 'Level: WARN' format per D-14"
    assert "Level: ERROR" in html, "Filter must display 'Level: ERROR' format per D-14"
    assert "Level: ALL" in html, "Filter must display 'Level: ALL' format per D-14"
    assert "font-mono" in html, "Filter must use mono font per D-14"


def test_log_viewer_level_filter_server_side(client):
    """LOG-06: ?level=ERROR filters to only ERROR entries server-side."""
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "ERROR", "Something broke"))
    log_buffer.add(LogEntry("2026-01-15 10:30:01", "INFO", "All good"))
    response = client.get("/partials/log-viewer?level=ERROR")
    assert response.status_code == 200
    assert "Something broke" in response.text, "ERROR entry must be shown"
    assert "All good" not in response.text, "INFO entry must be filtered out"


def test_log_viewer_invalid_level_shows_all(client):
    """LOG-06: Invalid level parameter shows all entries (no crash)."""
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Normal message"))
    response = client.get("/partials/log-viewer?level=BOGUS")
    assert response.status_code == 200
    assert "Normal message" in response.text, "Invalid level should show all entries"


def test_system_logs_title(client):
    """LOG-01: Header shows 'System Logs' with terminal-window Phosphor icon per D-11."""
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "System Logs" in response.text, "Title must say 'System Logs' per D-11"
    assert "Application Log" not in response.text, "Old title 'Application Log' must be removed"
    assert "ph ph-terminal-window" in response.text, "Title must have terminal-window icon per D-11"


def test_log_header_bar(client):
    """LOG-01: Log header bar uses bg-triggarr-card background per D-16."""
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "bg-triggarr-card" in response.text, "Header bar must use bg-triggarr-card per D-16"


def test_vertical_divider(client):
    """LOG-01: Vertical divider between filter and buttons per D-15."""
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "w-px h-4 bg-triggarr-border" in response.text, "Vertical divider must be present per D-15"


def test_grab_row_highlight(client):
    """LOG-01: GRAB-related messages get green highlight with [GRAB] label per D-17."""
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Radarr: grabbed 12 items"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "bg-triggarr-primary/10" in response.text, "GRAB row must have green background"
    assert "[GRAB]" in response.text, "GRAB row must show [GRAB] level label"
    assert "border-triggarr-primary" in response.text, "GRAB row must have green left border"


def test_non_grab_row_hover(client):
    """D-18: Non-grab log rows have hover:bg-white/5 with group hover transitions."""
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Normal status message"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "hover:bg-white/5" in response.text, "Non-grab rows must have hover:bg-white/5 per D-18"
    assert "group-hover:text-white" in response.text, "Message text must transition on group hover per D-18"


def test_grab_keyword_found_release(client):
    """D-17: 'found release' keyword triggers GRAB highlight."""
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Radarr: found release for Movie Title"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "[GRAB]" in response.text, "'found release' must trigger GRAB highlight"


def test_log_body_sizing(client):
    """D-16: Log body uses h-48 height and p-3 padding."""
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Test"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "h-48" in response.text, "Log body must use h-48 per artifact"
    assert "text-[13px]" in response.text, "Log rows must use text-[13px] per D-18"
