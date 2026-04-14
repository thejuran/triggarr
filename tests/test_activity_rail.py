"""Test suite for Recent Activity Rail (Phase 52, RAIL-01 through RAIL-06).

Covers the /partials/activity-rail route, activity_rail.html template,
relative_time Jinja filter, and timeline markup.
"""

from __future__ import annotations

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from triggarr.db import init_db, insert_search_entry
from triggarr.log_buffer import log_buffer
from triggarr.web.routes import STATIC_DIR, router


@pytest.fixture
async def rail_app(tmp_path):
    """Build a minimal FastAPI app with seeded search data for rail tests."""
    log_buffer.clear()
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
        app.state.last_search_times = {}
        app.state.update_info = {}
        app.state.last_health_check = None

        yield app


@pytest.fixture
async def empty_rail_app(tmp_path):
    """Build a minimal FastAPI app with NO search data for empty-state test."""
    log_buffer.clear()
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
        app.state.last_search_times = {}
        app.state.update_info = {}
        app.state.last_health_check = None

        yield app


@pytest.fixture
def client(rail_app):
    """Create a TestClient for the rail test app."""
    return TestClient(rail_app)


@pytest.fixture
def empty_client(empty_rail_app):
    """Create a TestClient for the empty rail test app."""
    return TestClient(empty_rail_app)


# RAIL-06: Route returns 200
def test_rail_partial_returns_200(client):
    """GET /partials/activity-rail returns 200."""
    response = client.get("/partials/activity-rail")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"


# RAIL-01: Sticky positioning
def test_rail_has_sticky_classes(client):
    """Response contains sticky and top-20 for fixed positioning."""
    response = client.get("/partials/activity-rail")
    assert "sticky" in response.text, "Rail should have sticky positioning"
    assert "top-20" in response.text, "Rail should have top-20 offset"


# RAIL-05: Hidden below xl breakpoint
def test_rail_hidden_below_xl(client):
    """Response contains hidden xl:flex for responsive hiding."""
    response = client.get("/partials/activity-rail")
    assert "hidden xl:flex" in response.text, "Rail should be hidden below xl breakpoint"


# RAIL-02: Timeline dots and items
def test_timeline_dots_present(client):
    """Response contains timeline-item and timeline-dot classes."""
    response = client.get("/partials/activity-rail")
    assert "timeline-item" in response.text, "Rail should contain timeline-item class"
    assert "timeline-dot" in response.text, "Rail should contain timeline-dot class"


# RAIL-03: App badge with color
def test_entry_has_app_badge(client):
    """Response contains app name with appropriate color class."""
    response = client.get("/partials/activity-rail")
    assert "Radarr" in response.text, "Rail should show Radarr app name"
    assert "bg-orange-500/10" in response.text, "Radarr badge should have orange background"


# RAIL-03: Outcome pill
def test_entry_has_outcome_pill(client):
    """Response contains outcome text with color class."""
    response = client.get("/partials/activity-rail")
    assert "grabbed" in response.text, "Rail should show grabbed outcome"
    assert "text-green-400" in response.text, "Grabbed outcome should use green text"


# RAIL-03: Queue type
def test_entry_has_queue_type(client):
    """Response contains queue type text."""
    response = client.get("/partials/activity-rail")
    assert "missing" in response.text, "Rail should show queue type 'missing'"
    assert "cutoff" in response.text, "Rail should show queue type 'cutoff'"


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
    assert "LIVE" in response.text, "Rail header should show LIVE indicator"
    assert "dot-pulse" in response.text, "LIVE indicator should have pulsing dot"


# RAIL-04: Footer history link
def test_footer_history_link(client):
    """Response contains View full history link to /history."""
    response = client.get("/partials/activity-rail")
    assert "View full history" in response.text, "Rail footer should have history link"
    assert "/history" in response.text, "History link should point to /history"


# RAIL-03: SVG outcome icons
def test_outcome_svg_icons(client):
    """Response contains SVG elements for outcome icons."""
    response = client.get("/partials/activity-rail")
    assert "<polyline" in response.text, "Grabbed outcome should have checkmark SVG"
    assert "<circle" in response.text, "Other outcomes should have circle-based SVGs"


# RAIL-06: Empty state
def test_empty_state(empty_client):
    """When no search entries, response contains 'No recent activity'."""
    response = empty_client.get("/partials/activity-rail")
    assert response.status_code == 200
    assert "No recent activity" in response.text, "Empty rail should show 'No recent activity'"
