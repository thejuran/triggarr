"""Phase 49 Stats & Health Strip tests.

Locks STATS-01 through STATS-05: compact health strip, hero Grab Rate card
with health badge and per-app color-coded bars, and shadow-sm elevation on
all stat cards.
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
    """Build a minimal FastAPI app with mocked state for route testing.

    Inserts search entries with 'grabbed' outcomes to produce non-None
    per-app grab rates.
    """
    log_buffer.clear()
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await init_db(db, db_path)

        # Insert Radarr entries: 2 searched, 1 grabbed -> 50% rate
        await insert_search_entry(db, "Radarr", "missing", "Movie A", outcome="searched")
        await insert_search_entry(db, "Radarr", "missing", "Movie B", outcome="grabbed")

        # Insert Sonarr entries: 1 searched, 1 grabbed -> 100% rate (but partial counts)
        await insert_search_entry(db, "Sonarr", "missing", "Show A", outcome="grabbed")

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
# STATS-01: Health strip (not a card)
# ---------------------------------------------------------------------------


def test_health_strip_is_not_a_card(client):
    """Health summary is a bare strip, NOT a card with bg/border/padding."""
    response = client.get("/partials/health-summary")
    assert response.status_code == 200
    assert "bg-triggarr-card" not in response.text
    assert "flex items-center justify-between text-xs mb-4 px-1" in response.text


def test_health_strip_has_colored_dots(client):
    """Health strip uses colored dots: green=connected, red=disconnected, gray=pending."""
    response = client.get("/partials/health-summary")
    assert response.status_code == 200
    assert "bg-triggarr-green" in response.text
    assert "bg-red-500" in response.text
    assert "bg-triggarr-border" in response.text


def test_health_strip_has_last_sync(client):
    """Health strip shows 'Last sync' timestamp in Geist Mono."""
    response = client.get("/partials/health-summary")
    assert response.status_code == 200
    assert "Last sync" in response.text
    assert "font-geist-mono" in response.text


# ---------------------------------------------------------------------------
# STATS-02: Hero Grab Rate card (2-col, text-4xl)
# ---------------------------------------------------------------------------


def test_grab_rate_hero_card_layout(client):
    """Grab Rate card spans 2 columns with text-4xl headline and gradient."""
    response = client.get("/")
    assert response.status_code == 200
    assert "md:col-span-2" in response.text
    assert "text-4xl font-bold" in response.text
    assert "text-2xl text-triggarr-muted" in response.text
    assert "bg-gradient-to-br from-triggarr-green/5" in response.text


# ---------------------------------------------------------------------------
# STATS-03: Health badge (Healthy/Warn/Critical)
# ---------------------------------------------------------------------------


def test_health_badge_renders(client):
    """Health badge renders with one of the three threshold labels."""
    response = client.get("/")
    assert response.status_code == 200
    text = response.text
    # At least one badge label should appear (depends on test data rate)
    assert any(label in text for label in ("Healthy", "Warn", "Critical"))
    assert "rounded-full" in text


# ---------------------------------------------------------------------------
# STATS-04: Per-app color-coded bars
# ---------------------------------------------------------------------------


def test_per_app_bars_with_colors(client):
    """Per-app grab rate bars use mini-bar class and correct app colors."""
    response = client.get("/")
    assert response.status_code == 200
    assert "mini-bar" in response.text
    # Radarr orange bar (test data has radarr entries)
    assert "#fb923c" in response.text
    assert "text-orange-400" in response.text


# ---------------------------------------------------------------------------
# STATS-05: shadow-sm elevation on all stat cards
# ---------------------------------------------------------------------------


def test_stat_cards_have_shadow(client):
    """All stat cards (hero + Movies + Episodes + Albums + Time to Grab) have shadow-sm."""
    response = client.get("/")
    assert response.status_code == 200
    count = response.text.count("shadow-sm")
    assert count >= 5, f"Expected >= 5 shadow-sm occurrences, got {count}"


# ---------------------------------------------------------------------------
# CSS: mini-bar compiled into output.css
# ---------------------------------------------------------------------------


def test_output_css_contains_mini_bar():
    """Compiled output.css must contain mini-bar styles."""
    css_path = STATIC_DIR / "css" / "output.css"
    css_content = css_path.read_text()
    assert "mini-bar" in css_content, "mini-bar class missing from output.css"
