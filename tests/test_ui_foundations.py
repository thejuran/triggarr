"""Phase 48 UI foundations smoke tests.

Locks the v2.5 design-system scaffolding: sticky nav, widened container,
active-tab underline, pulsing update dot, and CSS compilation artifacts.
No Playwright, no snapshots, no new dependencies.
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
from triggarr.log_buffer import log_buffer
from triggarr.models.config import GeneralConfig
from triggarr.web.routes import STATIC_DIR, router

TEMPLATES_DIR = STATIC_DIR.parent / "templates"


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
        app.state.last_health_check = None

        yield app


@pytest.fixture
def client(test_app):
    """Create a TestClient for the test app."""
    return TestClient(test_app)


# ---------------------------------------------------------------------------
# Container widening (FOUND-04)
# ---------------------------------------------------------------------------


def test_dashboard_has_widened_container(client):
    """Dashboard uses max-w-7xl and no longer has max-w-5xl."""
    response = client.get("/")
    assert response.status_code == 200
    assert "max-w-7xl" in response.text
    assert "max-w-5xl" not in response.text


def test_history_has_widened_container(client):
    """History page uses max-w-7xl and no longer has max-w-5xl."""
    response = client.get("/history")
    assert response.status_code == 200
    assert "max-w-7xl" in response.text
    assert "max-w-5xl" not in response.text


def test_settings_has_widened_container(client):
    """Settings page uses max-w-7xl and no longer has max-w-5xl."""
    response = client.get("/settings")
    assert response.status_code == 200
    assert "max-w-7xl" in response.text
    assert "max-w-5xl" not in response.text


# ---------------------------------------------------------------------------
# Sticky nav (NAV-01)
# ---------------------------------------------------------------------------


def test_nav_is_sticky_and_blurred(client):
    """Header element has sticky positioning with backdrop blur."""
    response = client.get("/")
    assert response.status_code == 200
    assert "sticky top-0 z-50" in response.text
    assert "backdrop-blur-md" in response.text
    assert "bg-triggarr-bg/95" in response.text


# ---------------------------------------------------------------------------
# Active tab underline (NAV-02)
# ---------------------------------------------------------------------------


def test_active_tab_underline_on_dashboard(client):
    """Dashboard page has the green underline active-tab marker."""
    response = client.get("/")
    assert response.status_code == 200
    assert "bg-triggarr-green" in response.text
    assert "-bottom-[21px]" in response.text


def test_active_tab_underline_on_history(client):
    """History page has the green underline active-tab marker."""
    response = client.get("/history")
    assert response.status_code == 200
    assert "bg-triggarr-green" in response.text


def test_active_tab_underline_on_settings(client):
    """Settings page has the green underline active-tab marker."""
    response = client.get("/settings")
    assert response.status_code == 200
    assert "bg-triggarr-green" in response.text


# ---------------------------------------------------------------------------
# No dead nav_*_class block overrides (D-21 regression lock)
# ---------------------------------------------------------------------------


def test_nav_has_no_blocked_class_overrides():
    """Child templates must not contain nav_*_class block overrides."""
    for name in ("dashboard.html", "history.html", "settings.html"):
        content = (TEMPLATES_DIR / name).read_text()
        assert "nav_dashboard_class" not in content, f"{name} still has nav_dashboard_class"
        assert "nav_history_class" not in content, f"{name} still has nav_history_class"
        assert "nav_settings_class" not in content, f"{name} still has nav_settings_class"


# ---------------------------------------------------------------------------
# Update chip pulsing dot (NAV-03)
# ---------------------------------------------------------------------------


def test_update_chip_pulse_dot_when_update_available(client):
    """When an update is available, the nav renders a dot-pulse span."""
    import triggarr.web.routes as routes_module

    original = dict(routes_module.update_info)
    routes_module.update_info.update({
        "update_available": True,
        "html_url": "https://github.com/thejuran/triggarr/releases/tag/v99.0.0",
        "latest_version": "99.0.0",
    })
    try:
        response = client.get("/")
        assert response.status_code == 200
        assert "dot-pulse" in response.text
        assert "v99.0.0 available" in response.text
    finally:
        routes_module.update_info.clear()
        routes_module.update_info.update(original)


def test_update_chip_no_pulse_dot_when_no_update(client):
    """When no update is available, dot-pulse is not rendered."""
    import triggarr.web.routes as routes_module

    original = dict(routes_module.update_info)
    routes_module.update_info.clear()
    try:
        response = client.get("/")
        assert response.status_code == 200
        # The update chip renders "vX.Y.Z available" with a dot-pulse span;
        # when update_info is empty the entire chip block is absent.
        assert "available\n" not in response.text
    finally:
        routes_module.update_info.clear()
        routes_module.update_info.update(original)


# ---------------------------------------------------------------------------
# CSS compilation assertions (D-31)
# ---------------------------------------------------------------------------


def test_output_css_contains_elevation_token_and_dot_pulse():
    """Compiled output.css must contain the elevation hex, dot-pulse, and Geist Mono."""
    css_path = STATIC_DIR / "css" / "output.css"
    css_content = css_path.read_text()
    assert "#233346" in css_content, "Elevation token #233346 missing from output.css"
    assert "dot-pulse" in css_content, "dot-pulse class missing from output.css"
    assert "dot-ring-pulse" in css_content, "ring-expansion keyframes missing from output.css"
    assert "0 0 0 6px" in css_content, "ring-expansion box-shadow stop missing from output.css"
    assert "Geist Mono" in css_content, "Geist Mono font reference missing from output.css"
