"""Phase 61 App Cards tests.

Locks CARD-01 through CARD-04: app-type colored borders, sectioned layout
with header/body/footer, recessed sub-cards, connection pills with borders,
full-width Search Now with app-colored hover, and unreachable error message.
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
    async with aiosqlite.connect(db_path) as db:
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
        app.state.last_health_check = None

        yield app


@pytest.fixture
def client(test_app):
    """Create a TestClient for the test app."""
    return TestClient(test_app)


# ---------------------------------------------------------------------------
# CARD-01: App-type colored left borders
# ---------------------------------------------------------------------------


def test_connected_pill_unified_shape(client, test_app):
    """Connected state shows green pill with rounded shape and border (CARD-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    pill = "rounded text-[10px] font-bold uppercase tracking-wider"
    assert pill in response.text
    assert "bg-triggarr-primary/10 text-triggarr-primary" in response.text
    assert "Connected" in response.text
    assert "border border-triggarr-primary/20" in response.text


def test_unreachable_pill_unified_shape(client, test_app):
    """Unreachable state shows red pill with rounded shape and border (CARD-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    pill = "rounded text-[10px] font-bold uppercase tracking-wider"
    assert pill in response.text
    assert "bg-triggarr-danger/10 text-triggarr-danger" in response.text
    assert "Unreachable" in response.text
    assert "border border-triggarr-danger/20" in response.text


def test_waiting_pill_unified_shape(client, test_app):
    """Waiting state shows muted pill with rounded shape (CARD-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = None
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    pill = "rounded text-[10px] font-bold uppercase tracking-wider"
    assert pill in response.text
    assert "bg-triggarr-border/40 text-triggarr-muted" in response.text
    assert "Waiting..." in response.text


# ---------------------------------------------------------------------------
# CARD-02: Schedule row with Last Run / Next Run
# ---------------------------------------------------------------------------


def test_schedule_row_present(client, test_app):
    """Schedule row shows Last Run and Next Run with font-mono (CARD-02).

    The schedule row uses mb-1 (not mb-4) since the Last OK row below it provides
    the visual separation; the Last OK row itself carries mb-4.
    """
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["last_run"] = "2026-04-13T14:32:10Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Last run" in response.text
    assert "font-mono text-triggarr-muted mb-1 flex justify-between" in response.text
    assert "14:32:10" in response.text


def test_schedule_row_unreachable_no_schedule(client, test_app):
    """When unreachable, schedule row is not shown (body replaced with error message)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Last run" not in response.text
    assert "API connection failed." in response.text


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


def test_connected_card_no_danger_stripes(client, test_app):
    """Connected cards do not show danger stripes (CARD-05)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "danger-stripes" not in response.text


def test_unreachable_card_shows_error_not_stats(client, test_app):
    """Unreachable cards show error message instead of stats grid."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "API connection failed." in response.text
    assert "Missing" not in response.text  # stats grid not shown for unreachable


# ---------------------------------------------------------------------------
# CARD-06: Retry button on unreachable, Search Now on connected
# ---------------------------------------------------------------------------


def test_unreachable_card_retry_button(client, test_app):
    """Unreachable cards show Retry Connection button (CARD-06)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Retry Connection" in response.text
    assert "bg-triggarr-card hover:bg-triggarr-elevated" in response.text
    assert "ph ph-arrows-clockwise" in response.text
    assert "Search Now" not in response.text


def test_connected_card_search_now_button(client, test_app):
    """Connected cards show Search Now button with Phosphor icon (CARD-06)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Search Now" in response.text
    assert "ph ph-magnifying-glass" in response.text
    assert "bg-triggarr-elevated" in response.text
    assert "group-hover:text-triggarr-radarr" in response.text
    assert "Retry Connection" not in response.text


# ---------------------------------------------------------------------------
# CARD-07: Connection pill border styles (replaces dot-pulse)
# ---------------------------------------------------------------------------


def test_connected_pill_has_border(client, test_app):
    """Connected pill has border and tracking-wider text (CARD-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "border border-triggarr-primary/20" in response.text
    assert "tracking-wider" in response.text


def test_unreachable_pill_has_danger_border(client, test_app):
    """Unreachable pill has danger-colored border (CARD-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "border border-triggarr-danger/20" in response.text


# ---------------------------------------------------------------------------
# CARD-01: App-type border colors
# ---------------------------------------------------------------------------


def test_app_card_radarr_border_color(client, test_app):
    """Radarr app card has orange left border (CARD-01)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "border-l-triggarr-radarr" in response.text
    assert "border-l-triggarr-green" not in response.text  # no longer green for connected


def test_app_card_unreachable_border_color(client, test_app):
    """Unreachable app card has red left border regardless of app type (CARD-01)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "border-l-triggarr-danger" in response.text


# ---------------------------------------------------------------------------
# CARD-02: Header border-bottom separator
# ---------------------------------------------------------------------------


def test_card_header_border_bottom(client, test_app):
    """App card header has border-bottom separator (CARD-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "p-4 border-b border-triggarr-border/50" in response.text
    assert "text-[15px]" in response.text  # title font size


# ---------------------------------------------------------------------------
# CARD-03: Recessed sub-cards
# ---------------------------------------------------------------------------


def test_recessed_subcards(client, test_app):
    """Missing and Cutoff stats are in recessed sub-cards (CARD-03)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "bg-triggarr-bg/50 border border-triggarr-border/50 rounded p-2.5" in response.text
    assert "text-lg font-bold text-triggarr-text" in response.text
    assert "text-[10px] text-triggarr-muted uppercase tracking-wider" in response.text


# ---------------------------------------------------------------------------
# CARD-04: Search Now app-colored hover
# ---------------------------------------------------------------------------


def test_search_button_app_colored_hover(client, test_app):
    """Search Now button has app-colored hover on icon (CARD-04)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "group-hover:text-triggarr-radarr" in response.text
    assert "ph ph-magnifying-glass" in response.text
    assert "bg-triggarr-elevated" in response.text


# ---------------------------------------------------------------------------
# Unreachable body error message
# ---------------------------------------------------------------------------


def test_unreachable_body_error_message(client, test_app):
    """Unreachable card body shows centered error message with warning icon."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "ph ph-warning-circle" in response.text
    assert "API connection failed." in response.text
    assert "Check API key or network setup." in response.text


# ---------------------------------------------------------------------------
# Footer section
# ---------------------------------------------------------------------------


def test_footer_section_background(client, test_app):
    """Footer section has bg-triggarr-bg/30 background (CARD-04)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "bg-triggarr-bg/30 border-t border-triggarr-border/50" in response.text


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
