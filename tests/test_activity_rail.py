"""Test suite for Recent Activity Rail (Phase 62, RAIL-01 through RAIL-06).

Covers the /partials/activity-rail route, activity_rail.html template,
relative_time Jinja filter, card-based layout, and timeline markup.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from triggarr.db import init_db, insert_search_entry
from triggarr.log_buffer import log_buffer
from triggarr.web.routes import STATIC_DIR, router


@pytest.fixture(autouse=True)
async def _clear_log_buffer():
    """Reset shared log_buffer before and after each test."""
    log_buffer.clear()
    yield
    log_buffer.clear()


@pytest.fixture
async def rail_app(tmp_path):
    """Build a minimal FastAPI app with seeded search data for rail tests."""
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    db_path = tmp_path / "test_rail.db"
    async with aiosqlite.connect(db_path) as db:
        await init_db(db, db_path)
        # Seed two entries with different apps and outcomes
        await insert_search_entry(db, "Radarr", "missing", "Test Movie", outcome="grabbed")
        await insert_search_entry(db, "Sonarr", "cutoff", "Test Show", outcome="failed", detail="Connection refused")
        app.state.db = db

        app.state.triggarr_state = {
            "radarr": {
                "Default": {
                    "missing_cursor": 0, "cutoff_cursor": 0,
                    "last_run": None, "connected": True,
                    "unreachable_since": None,
                    "missing_count": None, "cutoff_count": None,
                },
            },
            "sonarr": {
                "Default": {
                    "missing_cursor": 0, "cutoff_cursor": 0,
                    "last_run": None, "connected": True,
                    "unreachable_since": None,
                    "missing_count": None, "cutoff_count": None,
                },
            },
            "lidarr": {
                "Default": {
                    "missing_cursor": 0, "cutoff_cursor": 0,
                    "last_run": None, "connected": None,
                    "unreachable_since": None,
                    "missing_count": None, "cutoff_count": None,
                },
            },
            "search_log": [],
        }

        app.state.settings = make_settings()
        app.state.last_search_time = {}
        app.state.update_info = {}
        app.state.last_health_check = None
        app.state.scheduler = MagicMock()
        app.state.search_lock = asyncio.Lock()
        app.state.config_path = tmp_path / "triggarr.toml"
        app.state.state_path = tmp_path / "state.json"

        yield app


@pytest.fixture
async def empty_rail_app(tmp_path):
    """Build a minimal FastAPI app with NO search data for empty-state test."""
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    db_path = tmp_path / "test_rail_empty.db"
    async with aiosqlite.connect(db_path) as db:
        await init_db(db, db_path)
        app.state.db = db

        _default = {
            "missing_cursor": 0, "cutoff_cursor": 0, "last_run": None,
            "connected": None, "unreachable_since": None,
            "missing_count": None, "cutoff_count": None,
        }
        app.state.triggarr_state = {
            "radarr": {"Default": {**_default}},
            "sonarr": {"Default": {**_default}},
            "lidarr": {"Default": {**_default}},
            "search_log": [],
        }

        app.state.settings = make_settings()
        app.state.last_search_time = {}
        app.state.update_info = {}
        app.state.last_health_check = None
        app.state.scheduler = MagicMock()
        app.state.search_lock = asyncio.Lock()
        app.state.config_path = tmp_path / "triggarr.toml"
        app.state.state_path = tmp_path / "state.json"

        yield app


@pytest.fixture
async def rail_app_many(tmp_path):
    """Build a minimal FastAPI app with 5 seeded entries for opacity fading tests."""
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)
    db_path = tmp_path / "test_rail_many.db"
    async with aiosqlite.connect(db_path) as db:
        await init_db(db, db_path)
        await insert_search_entry(db, "Radarr", "missing", "Movie 1", outcome="grabbed")
        await insert_search_entry(db, "Sonarr", "cutoff", "Show 2", outcome="searched")
        await insert_search_entry(db, "Radarr", "missing", "Movie 3", outcome="partial")
        await insert_search_entry(db, "Sonarr", "cutoff", "Show 4", outcome="failed")
        await insert_search_entry(db, "Radarr", "missing", "Movie 5", outcome="grabbed")
        app.state.db = db
        _inst = {
            "missing_cursor": 0, "cutoff_cursor": 0, "last_run": None,
            "connected": True, "unreachable_since": None,
            "missing_count": None, "cutoff_count": None,
        }
        _inst_none = {**_inst, "connected": None}
        app.state.triggarr_state = {
            "radarr": {"Default": {**_inst}},
            "sonarr": {"Default": {**_inst}},
            "lidarr": {"Default": {**_inst_none}},
            "search_log": [],
        }
        app.state.settings = make_settings()
        app.state.last_search_time = {}
        app.state.update_info = {}
        app.state.last_health_check = None
        app.state.scheduler = MagicMock()
        app.state.search_lock = asyncio.Lock()
        app.state.config_path = tmp_path / "triggarr.toml"
        app.state.state_path = tmp_path / "state.json"
        yield app


@pytest.fixture
def client(rail_app):
    """Create a TestClient for the rail test app."""
    return TestClient(rail_app)


@pytest.fixture
def empty_client(empty_rail_app):
    """Create a TestClient for the empty rail test app."""
    return TestClient(empty_rail_app)


@pytest.fixture
def many_client(rail_app_many):
    return TestClient(rail_app_many)


# RAIL-06: Route returns 200
def test_rail_partial_returns_200(client):
    """GET /partials/activity-rail returns 200."""
    response = client.get("/partials/activity-rail")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"


# RAIL-01: Sticky positioning
def test_rail_has_sticky_classes(client):
    """Response contains sticky and top-[73px] for fixed positioning."""
    response = client.get("/partials/activity-rail")
    assert "sticky" in response.text, "Rail should have sticky positioning"
    assert "top-[73px]" in response.text, "Rail should have top-[73px] offset"


# RAIL-05: Hidden below xl breakpoint
def test_rail_hidden_below_xl(client):
    """Response contains hidden xl:flex for responsive hiding."""
    response = client.get("/partials/activity-rail")
    assert "hidden xl:flex" in response.text, "Rail should be hidden below xl breakpoint"


# RAIL-02: Timeline dots — double-circle pattern
def test_timeline_dots_present(client):
    """Response contains double-circle timeline dot pattern."""
    response = client.get("/partials/activity-rail")
    assert "w-7 h-7 rounded-full" in response.text, "Double-circle outer ring must be present"
    assert "w-2.5 h-2.5 rounded-full" in response.text, "Double-circle inner dot must be present"


# RAIL-03: App badge with color dot
def test_entry_has_app_badge(client):
    """Response contains app name with colored dot indicator and monospace font."""
    response = client.get("/partials/activity-rail")
    assert "Radarr" in response.text, "Rail should show Radarr app name"
    assert "w-1.5 h-1.5 rounded-full" in response.text, "App badge dot must be present"
    assert "font-mono" in response.text, "App badge must use monospace font"


# RAIL-03: Outcome pill
def test_entry_has_outcome_pill(client):
    """Response contains outcome text with triggarr-primary color."""
    response = client.get("/partials/activity-rail")
    assert "grabbed" in response.text, "Rail should show grabbed outcome"
    assert "text-triggarr-primary" in response.text, "Grabbed outcome should use triggarr-primary color"


# RAIL-03: Queue type removed in card redesign — entries now show app badge + outcome pill
def test_entry_has_app_and_outcome(client):
    """Response contains app name and outcome pill (queue type no longer shown)."""
    response = client.get("/partials/activity-rail")
    assert "Radarr" in response.text, "Rail should show app name"
    assert "grabbed" in response.text, "Rail should show outcome"


# RAIL-03: Relative timestamp
def test_entry_has_relative_timestamp(client):
    """Response contains relative time pattern."""
    response = client.get("/partials/activity-rail")
    # Entries were just inserted, so should show "Just now" or "Xs ago"
    text = response.text
    assert "ago" in text or "Just now" in text, "Rail should show relative timestamps"


# RAIL-04: LIVE indicator
def test_live_indicator_present(client):
    """Response contains LIVE text and dot-pulse class."""
    response = client.get("/partials/activity-rail")
    assert "Live" in response.text, "Rail header should show Live indicator"
    assert "dot-pulse" in response.text, "LIVE indicator should have pulsing dot"


# RAIL-04: Footer history link
def test_footer_history_link(client):
    """Response contains View full history link to /history."""
    response = client.get("/partials/activity-rail")
    assert "View full history" in response.text, "Rail footer should have history link"
    assert "/history" in response.text, "History link should point to /history"


# RAIL-01: Outcome pills use text-only badges
def test_outcome_pills_text_only(client):
    """RAIL-01: Outcome pills use text-only badges without SVGs."""
    response = client.get("/partials/activity-rail")
    assert response.status_code == 200
    assert "grabbed" in response.text, "Grabbed pill text must be present"
    assert "<polyline" not in response.text, "SVG polyline must not appear in pills"
    assert "<circle" not in response.text, "SVG circle must not appear in pills"


# RAIL-06: Empty state
def test_empty_state(empty_client):
    """When no search entries, response contains 'No recent activity'."""
    response = empty_client.get("/partials/activity-rail")
    assert response.status_code == 200
    assert "No recent activity" in response.text, "Empty rail should show 'No recent activity'"


# RAIL-01: Card-based layout
def test_card_based_layout(client):
    """RAIL-01: Activity entries use card-based layout with proper styling."""
    response = client.get("/partials/activity-rail")
    assert response.status_code == 200
    assert "bg-triggarr-card" in response.text, "Solid cards must use bg-triggarr-card"
    assert "rounded-lg p-3" in response.text, "Cards must have rounded-lg p-3"


# RAIL-01: Dashed cards for non-grab outcomes
def test_dashed_cards_for_non_grab(client):
    """RAIL-01: Non-grabbed entries use dashed border cards."""
    response = client.get("/partials/activity-rail")
    assert response.status_code == 200
    assert "border-dashed" in response.text, "Failed/searched entries must have dashed borders"


# RAIL-01: Speech bubble pointer
def test_speech_bubble_pointer(client):
    """RAIL-01: Cards have speech bubble pointer with rotate-45."""
    response = client.get("/partials/activity-rail")
    assert response.status_code == 200
    assert "rotate-45" in response.text, "Speech bubble pointer must use rotate-45"


# RAIL-03: Opacity fading
def test_opacity_fading(many_client):
    """RAIL-03: Entries 3+ fade with decreasing opacity."""
    response = many_client.get("/partials/activity-rail")
    assert response.status_code == 200
    assert "opacity-75" in response.text, "Entry 3 must have opacity-75"
    assert "opacity-60" in response.text, "Entry 4+ must have opacity-60"


# D-09: Rail header styling
def test_rail_header_styling(client):
    """RAIL-01: Rail header uses updated styling per D-09."""
    response = client.get("/partials/activity-rail")
    assert response.status_code == 200
    assert "tracking-widest" in response.text, "Header title must use tracking-widest"
    assert "backdrop-blur-md" in response.text, "Header must use backdrop blur"
    assert "text-[13px]" in response.text, "Header title must use text-[13px]"


# D-05: Vertical timeline line
def test_vertical_timeline_line(client):
    """RAIL-01: Vertical timeline line connects dots."""
    response = client.get("/partials/activity-rail")
    assert response.status_code == 200
    assert "left-[38px]" in response.text, "Timeline line must be positioned at left-[38px]"


# D-10: Footer Phosphor icon
def test_footer_phosphor_icon(client):
    """RAIL-01: Footer uses Phosphor arrow-right icon."""
    response = client.get("/partials/activity-rail")
    assert response.status_code == 200
    assert "ph-arrow-right" in response.text, "Footer must use ph-arrow-right icon"
    assert "group-hover:translate-x-1" in response.text, "Arrow must animate on hover"
