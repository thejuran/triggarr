"""Phase 61 Stats & Health Strip tests.

Locks STAT-01 through STAT-04: compact health strip, hero Grab Rate card
with Phosphor icons, per-app color-coded horizontal bars, colored dot
subtitles, and shadow-sm elevation on all stat cards.
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
                    "last_run": "2026-01-15T10:30:00Z",
                    "connected": True,
                    "unreachable_since": None,
                    "missing_count": 42,
                    "cutoff_count": 7,
                },
            },
            "sonarr": {
                "Default": {
                    "last_run": None,
                    "connected": None,
                    "unreachable_since": None,
                    "missing_count": None,
                    "cutoff_count": None,
                },
            },
            "lidarr": {
                "Default": {
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
# STAT-02: Hero Grab Rate card (2-col, text-[32px])
# ---------------------------------------------------------------------------


def test_grab_rate_hero_card_layout(client):
    """Grab Rate card spans 2 columns with text-[32px] headline (STAT-02)."""
    response = client.get("/")
    assert response.status_code == 200
    assert "md:col-span-2" in response.text
    assert "text-[32px] font-bold" in response.text
    assert "text-2xl text-triggarr-muted" in response.text
    assert "tracking-widest" in response.text
    assert "ph ph-chart-line-up" in response.text


# ---------------------------------------------------------------------------
# STAT-03: Phosphor icon on Grab Rate card
# ---------------------------------------------------------------------------


def test_grab_rate_has_phosphor_icon(client):
    """Grab Rate card shows chart-line-up Phosphor icon (STAT-03)."""
    response = client.get("/")
    assert response.status_code == 200
    assert "ph ph-chart-line-up" in response.text
    assert "text-triggarr-primary" in response.text


# ---------------------------------------------------------------------------
# STAT-04: Per-app color-coded horizontal bars
# ---------------------------------------------------------------------------


def test_per_app_bars_with_colors(client):
    """Per-app grab rate bars use Tailwind utilities and correct app colors."""
    response = client.get("/")
    assert response.status_code == 200
    assert "h-1" in response.text
    assert "bg-triggarr-bg rounded-full" in response.text
    # Radarr and Sonarr bar fills
    assert "bg-triggarr-radarr" in response.text
    assert "bg-triggarr-sonarr" in response.text


# ---------------------------------------------------------------------------
# STAT-05: shadow-sm elevation on all stat cards
# ---------------------------------------------------------------------------


def test_stat_cards_have_shadow(client):
    """All stat cards (hero + Movies + Series + Albums + Next Scan) have shadow-sm."""
    response = client.get("/")
    assert response.status_code == 200
    count = response.text.count("shadow-sm")
    assert count >= 5, f"Expected >= 5 shadow-sm occurrences, got {count}"


# ---------------------------------------------------------------------------
# CSS: mini-bar compiled into output.css (backward compat)
# ---------------------------------------------------------------------------


def test_css_has_mini_bar_rule():
    """input.css contains .mini-bar rule with height and border-radius."""
    css_path = STATIC_DIR / "css" / "input.css"
    css = css_path.read_text()
    assert ".mini-bar" in css
    assert "height: 6px" in css


# ---------------------------------------------------------------------------
# STAT-03: All stat cards have Phosphor icons
# ---------------------------------------------------------------------------


def test_stat_cards_have_phosphor_icons(client):
    """All stat cards display Phosphor icons matching app type (STAT-03)."""
    response = client.get("/")
    assert response.status_code == 200
    assert "ph ph-chart-line-up" in response.text  # Grab Rate
    assert "ph ph-film-strip" in response.text  # Movies
    assert "ph ph-television" in response.text  # Series
    assert "ph ph-clock-countdown" in response.text  # Next Scan


# ---------------------------------------------------------------------------
# STAT-04: Colored dot subtitles
# ---------------------------------------------------------------------------


def test_stat_card_subtitles(client):
    """Stat cards show colored dot + label subtitles (STAT-04)."""
    response = client.get("/")
    assert response.status_code == 200
    assert "w-1.5 h-1.5 rounded-full bg-triggarr-radarr" in response.text
    assert "In Radarr" in response.text
    assert "w-1.5 h-1.5 rounded-full bg-triggarr-sonarr" in response.text
    assert "In Sonarr" in response.text
    assert "Scheduled automatically" in response.text


# ---------------------------------------------------------------------------
# STAT-04: Label typography
# ---------------------------------------------------------------------------


def test_stat_card_label_typography(client):
    """Stat card labels use font-bold tracking-widest uppercase (STAT-04)."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text-xs font-bold tracking-widest uppercase text-triggarr-muted" in response.text


# ---------------------------------------------------------------------------
# STAT-02: Horizontal mini bar layout
# ---------------------------------------------------------------------------


def test_mini_bars_horizontal_layout(client):
    """Mini bars use horizontal flex layout with h-1 rounded-full bars (STAT-02)."""
    response = client.get("/")
    assert response.status_code == 200
    assert "flex items-center justify-between gap-4" in response.text
    assert "h-1 bg-triggarr-bg rounded-full overflow-hidden" in response.text
    assert "h-full bg-triggarr-radarr rounded-full" in response.text
