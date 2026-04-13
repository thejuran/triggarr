"""Phase 50 App Cards & Services Grid tests.

Locks CARD-01 through CARD-07 and LAYOUT-01: unified connection pills,
schedule row, pass pill badges, hover elevation, danger stripes,
Retry button, live-refresh dot-pulse, and 3-column xl grid.
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


@pytest.fixture
async def test_app(tmp_path):
    """Build a minimal FastAPI app with mocked state for card testing."""
    log_buffer.clear()
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    await insert_search_entry(db, "Radarr", "missing", "Test Movie")
    app.state.db = db

    app.state.triggarr_state = {
        "radarr": {
            "Default": {
                "missing_cursor": 3,
                "cutoff_cursor": 1,
                "last_run": "2026-04-13T14:32:10Z",
                "connected": True,
                "unreachable_since": None,
                "missing_count": 42,
                "cutoff_count": 7,
                "total_items": 100,
                "missing_pass": 0,
                "cutoff_pass": 0,
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
    await db.close()


@pytest.fixture
def client(test_app):
    """Create a TestClient for the test app."""
    return TestClient(test_app)


# ---------------------------------------------------------------------------
# CARD-01: Unified connection pill for all states
# ---------------------------------------------------------------------------


def test_connected_pill_unified_shape(client, test_app):
    """Connected state shows green pill with unified shape (CARD-01)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "rounded-full bg-triggarr-green/15 text-triggarr-green" in response.text
    assert "Connected" in response.text
    assert "inline-flex items-center gap-1.5" in response.text


def test_unreachable_pill_unified_shape(client, test_app):
    """Unreachable state shows red pill with unified shape (CARD-01)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "rounded-full bg-red-500/15 text-red-400" in response.text
    assert "Unreachable" in response.text
    assert "inline-flex items-center gap-1.5" in response.text


def test_waiting_pill_unified_shape(client, test_app):
    """Waiting state shows muted pill with unified shape (CARD-01)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = None
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "rounded-full bg-triggarr-border/40 text-triggarr-muted" in response.text
    assert "Waiting..." in response.text


# ---------------------------------------------------------------------------
# CARD-02: Schedule row with Last Run / Next Run
# ---------------------------------------------------------------------------


def test_schedule_row_present(client, test_app):
    """Schedule row shows Last Run and Next Run with formatted times (CARD-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["last_run"] = "2026-04-13T14:32:10Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Last run" in response.text
    assert "Next run" in response.text
    assert "border-b border-triggarr-border/50 pb-3" in response.text
    assert "14:32:10" in response.text


def test_schedule_row_unreachable_next_run_dash(client, test_app):
    """When unreachable, Next Run shows em dash (CARD-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    # Em dash entity or unicode
    assert "\u2014" in response.text or "&mdash;" in response.text


# ---------------------------------------------------------------------------
# CARD-03: Pass pill badges
# ---------------------------------------------------------------------------


def test_pass_pill_displayed(client, test_app):
    """Pass pill badge shows when pass > 0 (CARD-03)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["missing_pass"] = 2
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "pass 2" in response.text
    assert "text-[10px] bg-triggarr-border/60" in response.text


def test_pass_pill_hidden_when_zero(client, test_app):
    """Pass pill badge hidden when pass is 0 (CARD-03)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["missing_pass"] = 0
    test_app.state.triggarr_state["radarr"]["Default"]["cutoff_pass"] = 0
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "pass 0" not in response.text
    assert "bg-triggarr-border/60" not in response.text


# ---------------------------------------------------------------------------
# CARD-04: Hover elevation
# ---------------------------------------------------------------------------


def test_card_has_hover_classes(client, test_app):
    """All cards have card-hover and shadow-sm classes (CARD-04)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "card-hover" in response.text
    assert "shadow-sm" in response.text


# ---------------------------------------------------------------------------
# CARD-05: Danger stripes on unreachable cards
# ---------------------------------------------------------------------------


def test_unreachable_card_danger_stripes(client, test_app):
    """Unreachable cards show danger stripes (CARD-05)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "danger-stripes" in response.text
    assert "relative overflow-hidden" in response.text


def test_connected_card_no_danger_stripes(client, test_app):
    """Connected cards do not show danger stripes (CARD-05)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "danger-stripes" not in response.text


def test_unreachable_stats_opacity(client, test_app):
    """Unreachable cards have opacity-60 on stats grid (CARD-05)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "opacity-60" in response.text


# ---------------------------------------------------------------------------
# CARD-06: Retry button on unreachable, Search Now on connected
# ---------------------------------------------------------------------------


def test_unreachable_card_retry_button(client, test_app):
    """Unreachable cards show Retry button, not Search Now (CARD-06)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Retry" in response.text
    assert "bg-red-500/15 text-red-400" in response.text
    assert "Search Now" not in response.text


def test_connected_card_search_now_button(client, test_app):
    """Connected cards show Search Now button, not Retry (CARD-06)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Search Now" in response.text
    assert "Retry" not in response.text


# ---------------------------------------------------------------------------
# CARD-07: Pulsing green dot on Connected pill
# ---------------------------------------------------------------------------


def test_connected_pill_has_dot_pulse(client, test_app):
    """Connected pill has dot-pulse class for live-refresh indicator (CARD-07)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "dot-pulse" in response.text


def test_unreachable_pill_no_dot_pulse(client, test_app):
    """Unreachable pill does not have dot-pulse (CARD-07)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "dot-pulse" not in response.text


# ---------------------------------------------------------------------------
# LAYOUT-01: 3-column grid at xl breakpoint
# ---------------------------------------------------------------------------


def test_dashboard_grid_three_columns(client):
    """Dashboard grid wrapper has xl:grid-cols-3 class (LAYOUT-01)."""
    response = client.get("/")
    assert response.status_code == 200
    assert "xl:grid-cols-3" in response.text


# ---------------------------------------------------------------------------
# CSS rules exist in input.css
# ---------------------------------------------------------------------------


def test_css_has_card_hover_rule():
    """input.css contains .card-hover rule with elevated background."""
    css_path = STATIC_DIR / "css" / "input.css"
    css = css_path.read_text()
    assert ".card-hover" in css
    assert "background-color: #233346" in css


def test_css_has_danger_stripes_rule():
    """input.css contains .danger-stripes rule with gradient."""
    css_path = STATIC_DIR / "css" / "input.css"
    css = css_path.read_text()
    assert ".danger-stripes" in css
    assert "repeating-linear-gradient" in css


# ---------------------------------------------------------------------------
# D-25: Tag warning uses SVG icon
# ---------------------------------------------------------------------------


def test_tag_warning_uses_svg_icon(client, test_app):
    """Tag warning badge uses SVG icon instead of HTML entity (D-25)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["tag_warnings"] = [
        {"field": "missing", "tag": "hdr"},
    ]
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "<svg" in response.text
    assert "&#9888;" not in response.text
