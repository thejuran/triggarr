"""Test suite for web UI routes.

Covers dashboard rendering, settings form (masked API keys, TOML write,
key preservation, PRG redirect), htmx partials, and search-now validation.
"""

from __future__ import annotations

import asyncio
import errno
import json
import re
import threading
import tomllib
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from httpx import ASGITransport
from loguru import logger

from tests.conftest import make_settings
from triggarr.config import _atomic_toml_write, _settings_to_dict
from triggarr.db import init_db, insert_search_entry
from triggarr.log_buffer import LogEntry, log_buffer
from triggarr.models.config import APP_TYPES, GeneralConfig, InstanceConfig, Settings
from triggarr.web.routes import STATIC_DIR, router


@pytest.fixture
async def test_app(tmp_path):
    """Build a minimal FastAPI app with mocked state for route testing."""
    log_buffer.clear()  # Prevent test pollution from module-level singleton
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    # Initialize SQLite search history database with shared connection
    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await init_db(db, db_path)
        await insert_search_entry(db, "Radarr", "missing", "Test Movie")
        app.state.db = db

        # Mock triggarr state (nested per-instance format)
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

        # Real Settings with dict-based instances
        app.state.settings = make_settings(
            radarr_url="http://radarr:7878",
            radarr_api_key="test-radarr-key",
            radarr_enabled=True,
            sonarr_url="http://sonarr:8989",
            sonarr_api_key="test-sonarr-key",
            sonarr_enabled=True,
            general=GeneralConfig(skip_unreleased=True, tracking_delay_seconds=90),
        )

        # Mock scheduler
        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_job.next_run_time = None
        mock_scheduler.get_job.return_value = mock_job
        app.state.scheduler = mock_scheduler

        # Mock clients (close() is async, so needs AsyncMock) -- per-instance dicts
        radarr_client = MagicMock()
        radarr_client.close = AsyncMock()
        sonarr_client = MagicMock()
        sonarr_client.close = AsyncMock()
        lidarr_client = MagicMock()
        lidarr_client.close = AsyncMock()
        app.state.radarr_clients = {"Default": radarr_client}
        app.state.sonarr_clients = {"Default": sonarr_client}
        app.state.lidarr_clients = {"Default": lidarr_client}

        # Paths
        app.state.config_path = tmp_path / "triggarr.toml"
        app.state.state_path = tmp_path / "state.json"

        # Search lock (needed by search_now endpoint)
        app.state.search_lock = asyncio.Lock()
        app.state.search_lock_holder = None

        # SAFETY-03: failure counter + persistence flag (needed by _run_one_cycle)
        app.state.search_failures = {}
        app.state.persistence_degraded = False

        # Rate limit state (needed by search_now rate limiter — DEBT-01)
        app.state.last_search_time = {}
        app.state.last_refresh_time = {}          # Phase 74: sibling rate-limit dict for refresh_counts
        app.state.last_health_check = None

        # RES-03: tag cache (read by search_now resolver, popped by
        # save_settings / remove_instance invalidation).
        app.state.tag_cache = {}

        yield app


@pytest.fixture
def client(test_app):
    """Create a TestClient for the test app."""
    return TestClient(test_app)


def test_dashboard_returns_200(client):
    """GET / returns 200 and contains app name."""
    response = client.get("/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "Radarr" in response.text, "Dashboard should display Radarr card"


def test_dashboard_shows_activity_rail(client):
    """GET / response contains activity rail placeholder that loads via htmx (RAIL-07)."""
    response = client.get("/")
    assert response.status_code == 200
    assert "activity-rail" in response.text, "Dashboard should include activity rail"
    assert 'hx-trigger="load, every 5s"' in response.text, "Activity rail should load via htmx"


def test_settings_page_returns_200(client):
    """GET /settings returns 200."""
    response = client.get("/settings")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"


def test_settings_page_does_not_leak_api_keys(client):
    """GET /settings response must NOT contain actual API key values."""
    response = client.get("/settings")
    assert "test-radarr-key" not in response.text, "Radarr API key leaked in settings page"
    assert "test-sonarr-key" not in response.text, "Sonarr API key leaked in settings page"


def test_settings_page_shows_masked_placeholder(client):
    """GET /settings shows ******** placeholder when API key exists."""
    response = client.get("/settings")
    assert "********" in response.text, "Settings should show masked placeholder for existing key"


def test_app_card_partial_returns_200(client):
    """GET /partials/app-card/radarr/Default returns 200."""
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"


def test_app_card_partial_has_htmx_attributes(client):
    """App card partial contains htmx polling attributes."""
    response = client.get("/partials/app-card/radarr/Default")
    assert "hx-trigger" in response.text, "Card should have hx-trigger attribute"
    assert "every 5s" in response.text, "Card should poll every 5 seconds"


def test_activity_rail_partial_returns_200(client):
    """GET /partials/activity-rail returns 200."""
    response = client.get("/partials/activity-rail")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"


def test_save_settings_writes_toml(client, test_app, tmp_path):
    """POST /settings writes TOML to config_path and redirects (303)."""
    response = client.post(
        "/settings",
        data={
            "log_level": "debug",
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "new-key",
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "15",
            "radarr__Default__search_missing_count": "10",
            "radarr__Default__search_cutoff_count": "3",
            "radarr__Default__missing_tag": "",
            "radarr__Default__cutoff_tag": "",
            "sonarr__Default__url": "",
            "sonarr__Default__api_key": "",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, f"Expected 303 redirect, got {response.status_code}"
    assert response.headers["location"].endswith("/settings")

    # Verify TOML was written
    config_path = test_app.state.config_path
    assert config_path.exists(), "Config file should have been written"
    content = config_path.read_text()
    assert "radarr" in content, "TOML should contain radarr section"
    assert "new-key" in content, "TOML should contain the new API key"


def test_save_settings_preserves_existing_api_key(client, test_app, tmp_path):
    """POST /settings with empty api_key field preserves the existing key."""
    response = client.post(
        "/settings",
        data={
            "log_level": "info",
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "",  # Empty = keep existing
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "30",
            "radarr__Default__search_missing_count": "5",
            "radarr__Default__search_cutoff_count": "5",
            "radarr__Default__missing_tag": "",
            "radarr__Default__cutoff_tag": "",
            "sonarr__Default__url": "http://sonarr:8989",
            "sonarr__Default__api_key": "",  # Empty = keep existing
            "sonarr__Default__enabled": "on",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    # Verify the existing keys were preserved in TOML
    content = test_app.state.config_path.read_text()
    assert "test-radarr-key" in content, "Existing radarr key should be preserved"
    assert "test-sonarr-key" in content, "Existing sonarr key should be preserved"


def test_save_settings_replaces_api_key_when_provided(client, test_app, tmp_path):
    """POST /settings with new api_key value writes the new key to TOML."""
    response = client.post(
        "/settings",
        data={
            "log_level": "info",
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "brand-new-key",  # Explicit new key
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "30",
            "radarr__Default__search_missing_count": "5",
            "radarr__Default__search_cutoff_count": "5",
            "radarr__Default__missing_tag": "",
            "radarr__Default__cutoff_tag": "",
            "sonarr__Default__url": "http://sonarr:8989",
            "sonarr__Default__api_key": "",
            "sonarr__Default__enabled": "on",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    content = test_app.state.config_path.read_text()
    assert "brand-new-key" in content, "New API key should be written to TOML"
    assert "test-radarr-key" not in content, "Old radarr key should be replaced"


def test_save_settings_rejects_both_zero_counts(client, test_app, tmp_path):
    """POST /settings with both counts=0 for enabled app redirects without writing config."""
    response = client.post(
        "/settings",
        data={
            "log_level": "info",
            "hard_max_per_cycle": "0",
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "test-key",
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "30",
            "radarr__Default__search_missing_count": "0",
            "radarr__Default__search_cutoff_count": "0",
            "radarr__Default__missing_tag": "",
            "radarr__Default__cutoff_tag": "",
            "sonarr__Default__url": "",
            "sonarr__Default__api_key": "",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, f"Expected 303 redirect, got {response.status_code}"
    assert response.headers["location"].endswith("/settings")
    # Config file should NOT have been written (validation rejected the request)
    assert not test_app.state.config_path.exists(), "Config should not be written when both counts are 0"


def test_save_settings_accepts_zero_missing_with_positive_cutoff(client, test_app, tmp_path):
    """POST /settings with missing=0, cutoff=5 for enabled app writes config successfully."""
    response = client.post(
        "/settings",
        data={
            "log_level": "info",
            "hard_max_per_cycle": "0",
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "test-key",
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "30",
            "radarr__Default__search_missing_count": "0",
            "radarr__Default__search_cutoff_count": "5",
            "radarr__Default__missing_tag": "",
            "radarr__Default__cutoff_tag": "",
            "sonarr__Default__url": "",
            "sonarr__Default__api_key": "",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, f"Expected 303 redirect, got {response.status_code}"
    assert response.headers["location"].endswith("/settings")
    # Config file SHOULD have been written (0 missing is valid when cutoff > 0)
    assert test_app.state.config_path.exists(), "Config should be written when one count is positive"
    content = test_app.state.config_path.read_text()
    assert "radarr" in content, "TOML should contain radarr section"


def test_search_now_invalid_app(client):
    """POST /api/search-now/invalid returns 400."""
    response = client.post("/api/search-now/invalid/Default")
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    assert "Invalid app" in response.text


def test_search_now_happy_path(client, test_app):
    """POST /api/search-now/radarr triggers cycle and returns 200 with updated card."""
    with patch(
        "triggarr.search.scheduler.run_radarr_cycle",
        new=AsyncMock(return_value=test_app.state.triggarr_state),
    ), patch(
        "triggarr.search.scheduler.save_state",
    ):
        response = client.post("/api/search-now/radarr/Default")
        assert response.status_code == 200
        assert "Radarr" in response.text  # Card partial contains app name


# ---------------------------------------------------------------------------
# WEBU-09 / WEBU-11: Position labels and outcome badge
# ---------------------------------------------------------------------------


def test_dashboard_shows_position_x_of_y(client):
    """Dashboard app card renders app counts (WEBU-09).

    Cursor-based position display removed in v2.11 (cursor fields replaced by searched-log).
    The dashboard renders count data (missing_count, cutoff_count) from instance state.
    """
    response = client.get("/")
    assert response.status_code == 200
    # Radarr mock state: missing_count=42 and cutoff_count=7 are present in fixture
    assert "42" in response.text, "Missing count should appear in dashboard"
    assert "7" in response.text, "Cutoff count should appear in dashboard"


async def test_activity_rail_shows_outcome_badge(test_app, tmp_path):
    """Activity rail partial shows outcome badge for entries (WEBU-11)."""
    # Insert a failed search entry
    db = test_app.state.db
    await insert_search_entry(
        db, "Radarr", "missing", "Failed Movie",
        outcome="failed", detail="Connection refused",
    )

    with TestClient(test_app) as tc:
        response = tc.get("/partials/activity-rail")
    assert response.status_code == 200
    assert "failed" in response.text, "Activity rail should show failed outcome badge"
    assert "bg-red-500" in response.text, "Failed outcome should use red styling"


def test_dashboard_shows_log_viewer_section(client):
    """GET / response contains the System Logs section heading."""
    # Add a sample log entry so the viewer has content
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Test log message for dashboard"))
    response = client.get("/")
    assert response.status_code == 200
    assert "System Logs" in response.text, "Dashboard should show System Logs section"
    assert "Test log message for dashboard" in response.text, "Dashboard should show log entry"


def test_log_viewer_partial_returns_200(client):
    """GET /partials/log-viewer returns 200 with htmx attributes."""
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "hx-get" in response.text, "Log viewer should have hx-get attribute"
    assert "every 5s" in response.text, "Log viewer should poll every 5 seconds"


def test_log_viewer_partial_shows_entries(client):
    """GET /partials/log-viewer shows log entries when buffer has data."""
    log_buffer.clear()
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "ERROR", "Something went wrong"))
    log_buffer.add(LogEntry("2026-01-15 10:30:01", "WARNING", "Watch out"))
    response = client.get("/partials/log-viewer")
    assert response.status_code == 200
    assert "Something went wrong" in response.text
    assert "Watch out" in response.text
    assert "text-red-400" in response.text, "ERROR should use red color"
    assert "text-yellow-500" in response.text, "WARNING should use yellow color"


# ---------------------------------------------------------------------------
# SRCH-14: Search history page and partial tests
# ---------------------------------------------------------------------------


def test_history_page_returns_200(client):
    """GET /history returns 200 and contains Search History heading."""
    response = client.get("/history")
    assert response.status_code == 200
    assert "Search History" in response.text


def test_history_page_has_nav_link(client):
    """GET /history nav contains active History link with text-white class."""
    response = client.get("/history")
    assert response.status_code == 200
    # url_for returns full URL in test client (http://testserver/history)
    assert "/history" in response.text
    # The history page sets nav_history_class to text-white (active)
    # Find the <a> tag containing the history href and check its class
    text = response.text
    # Match the href ending with /history (url_for produces full URL in tests)
    import re
    match = re.search(r'href="[^"]*(/history)"', text)
    assert match, "History nav link should be present"
    history_link_start = match.start()
    a_start = text.rfind("<a", 0, history_link_start)
    a_end = text.index(">", history_link_start)
    a_tag = text[a_start:a_end + 1]
    assert "text-triggarr-text" in a_tag, "History nav link should have active text-triggarr-text class"


def test_history_page_shows_entries(client):
    """GET /history shows entries from fixture (Test Movie)."""
    response = client.get("/history")
    assert response.status_code == 200
    assert "Test Movie" in response.text


def test_history_results_partial_returns_200(client):
    """GET /partials/history-results returns 200 with swap target id."""
    response = client.get("/partials/history-results")
    assert response.status_code == 200
    assert 'id="history-results"' in response.text


def test_history_results_partial_with_app_filter(client):
    """GET /partials/history-results?app=Radarr returns 200 with Radarr entry."""
    response = client.get("/partials/history-results?app=Radarr")
    assert response.status_code == 200
    assert "Radarr" in response.text


async def test_history_results_partial_pagination(test_app):
    """GET /partials/history-results?page=2 shows pagination markup after inserting 60+ entries."""
    db = test_app.state.db
    for i in range(60):
        await insert_search_entry(db, "Radarr", "missing", f"Bulk Movie {i}")

    with TestClient(test_app) as tc:
        response = tc.get("/partials/history-results?page=2")
    assert response.status_code == 200
    # Pagination controls should be present (Previous / Next links or page numbers)
    assert "Previous" in response.text


async def test_history_page_empty_state(test_app, tmp_path):
    """GET /history with empty DB shows 'No search history yet' message."""
    # Create a fresh empty DB at a different tmp_path
    empty_db_path = tmp_path / "empty.db"
    async with aiosqlite.connect(empty_db_path) as empty_db:
        await init_db(empty_db, empty_db_path)
        test_app.state.db = empty_db

        with TestClient(test_app) as tc:
            response = tc.get("/history")
        assert response.status_code == 200
        assert "No search history yet" in response.text


def test_dashboard_nav_has_history_link(client):
    """GET / dashboard nav bar contains History link."""
    response = client.get("/")
    assert response.status_code == 200
    # url_for returns full URL in test client (http://testserver/history)
    assert "/history" in response.text


async def test_history_results_instance_filter(test_app):
    """GET /partials/history-results?instance=4K returns only 4K instance entries."""
    db = test_app.state.db
    await insert_search_entry(db, "Radarr", "missing", "Movie A", instance_id="4K")
    await insert_search_entry(db, "Radarr", "missing", "Movie B", instance_id="1080p")
    await insert_search_entry(db, "Sonarr", "missing", "Show C", instance_id="4K")

    with TestClient(test_app) as tc:
        response = tc.get("/partials/history-results?instance=4K")
    assert response.status_code == 200
    assert "Movie A" in response.text
    assert "Show C" in response.text
    assert "Movie B" not in response.text


def test_dashboard_shows_version(client):
    """Dashboard nav bar shows version string."""
    response = client.get("/")
    assert response.status_code == 200
    from triggarr.version import get_display_version
    assert get_display_version() in response.text


def test_app_card_shows_instance_name(client):
    """App card partial includes instance identifier."""
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    # Default instance doesn't show "/ Default" but the card_id should be present
    assert "radarr-Default-card" in response.text


# ---------------------------------------------------------------------------
# W1 regression: XSS in hx-vals attribute (Phase 16 code review)
# ---------------------------------------------------------------------------


def test_history_results_hx_vals_no_single_quote_breakout(client):
    """hx-vals uses double-quoted tojson, preventing single-quote XSS breakout."""
    response = client.get(
        "/partials/history-results?search=foo'+onmouseover='alert(1)"
    )
    assert response.status_code == 200
    # The hx-vals attribute must use double-quote delimiters (tojson pattern)
    assert 'hx-vals="' in response.text, "hx-vals should use double-quote delimiter"
    assert "hx-vals='" not in response.text, "hx-vals must NOT use single-quote delimiter"
    # Extract the hx-vals attribute value to verify XSS payload is safely escaped
    import re
    hx_vals_match = re.search(r'hx-vals="([^"]*)"', response.text)
    assert hx_vals_match is not None, "hx-vals double-quoted attribute should exist"
    hx_vals_content = hx_vals_match.group(1)
    # Inside the hx-vals JSON, the payload must not break out as a raw attribute
    assert "onmouseover" not in hx_vals_content, "XSS payload should not appear in hx-vals JSON"


# ---------------------------------------------------------------------------
# DEBT-01: Rate limiter on search-now endpoint
# ---------------------------------------------------------------------------


def test_search_now_rate_limited(client, test_app):
    """Second POST /api/search-now/radarr within rate limit window returns 429."""
    import time

    test_app.state.last_search_time["radarr_Default"] = time.monotonic()

    response = client.post("/api/search-now/radarr/Default")
    assert response.status_code == 429, f"Expected 429 rate limit, got {response.status_code}"
    assert "Rate limited" in response.text


def test_search_now_rate_limit_concurrent_protection(client, test_app):
    """Two rapid POST /api/search-now/radarr calls: second returns 429 (DRSEC-03).

    Validates that the re-check inside search_lock prevents concurrent bypass.
    """
    with patch(
        "triggarr.search.scheduler.run_radarr_cycle",
        new=AsyncMock(return_value=test_app.state.triggarr_state),
    ), patch("triggarr.search.scheduler.save_state"):
        resp1 = client.post("/api/search-now/radarr/Default")
        assert resp1.status_code == 200, f"First request should succeed, got {resp1.status_code}"

        resp2 = client.post("/api/search-now/radarr/Default")
        assert resp2.status_code == 429, f"Second request within rate window should be 429, got {resp2.status_code}"
        assert "Rate limited" in resp2.text


def test_search_now_not_rate_limited_after_window(client, test_app):
    """POST /api/search-now/radarr after window expires is not rate-limited."""
    import time

    from triggarr.web.routes import SEARCH_RATE_LIMIT_SECONDS

    # Set last_search_time to well before the window
    test_app.state.last_search_time["radarr_Default"] = time.monotonic() - (SEARCH_RATE_LIMIT_SECONDS + 1)

    with patch(
        "triggarr.search.scheduler.run_radarr_cycle",
        new=AsyncMock(return_value=test_app.state.triggarr_state),
    ), patch("triggarr.search.scheduler.save_state"):
        response = client.post("/api/search-now/radarr/Default")
    assert response.status_code == 200, f"Expected 200 after window expired, got {response.status_code}"


# ---------------------------------------------------------------------------
# DEBT-05: /health endpoint
# ---------------------------------------------------------------------------


def test_health_returns_200(client):
    """GET /health always returns 200 with status ok (simplified per D-06)."""
    response = client.get("/health")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# STATS-01..05: Dashboard stats cards
# ---------------------------------------------------------------------------


def test_dashboard_renders_stats_cards(client):
    """GET / renders all 4 stat card labels (STATS-01)."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Grab Rate" in response.text, "Dashboard should show Grab Rate card"
    assert "Movies" in response.text, "Dashboard should show Movies card"
    assert "Series" in response.text, "Dashboard should show Series card"
    assert "Average time to grab" in response.text, "Dashboard should show the time-to-grab card"


def test_stats_row_partial_returns_200(client):
    """GET /partials/stats-row returns 200 with stat card HTML (STATS-02)."""
    response = client.get("/partials/stats-row")
    assert response.status_code == 200
    assert "Grab Rate" in response.text
    assert "/partials/stats-row" in response.text
    assert "every 30s" in response.text


async def test_stats_empty_db_shows_dashes(test_app, tmp_path):
    """Stats cards show dash values when no tracking data exists (STATS-03)."""
    empty_db_path = tmp_path / "empty_stats.db"
    async with aiosqlite.connect(empty_db_path) as empty_db:
        await init_db(empty_db, empty_db_path)
        test_app.state.db = empty_db

        with TestClient(test_app) as tc:
            response = tc.get("/partials/stats-row")
        assert response.status_code == 200
        assert "---" in response.text, "Empty state should show dash values for time-to-grab"


# ---------------------------------------------------------------------------
# STATS-01..05: Settings form new config fields and outcome badge tests
# ---------------------------------------------------------------------------


def test_settings_page_renders_new_config_fields(client):
    """GET /settings renders the 4 new General config inputs (STATS-05)."""
    response = client.get("/settings")
    assert response.status_code == 200
    assert "tracking_window_minutes" in response.text, "Settings should show tracking window input"
    assert "max_history_rows" in response.text, "Settings should show max history rows input"
    assert "request_timeout" in response.text, "Settings should show request timeout input"
    assert "page_size" in response.text, "Settings should show page size input"
    assert "How long to wait for grabs" in response.text, "Settings should show tracking window hint"
    assert "shutdown_drain_timeout" in response.text, "Settings should show drain timeout input (75-02 D-02)"


def test_save_settings_with_new_fields(client, test_app):
    """POST /settings with new config fields saves them correctly (STATS-05)."""
    response = client.post(
        "/settings",
        data={
            "log_level": "info",
            "hard_max_per_cycle": "0",
            "max_history_rows": "5000",
            "request_timeout": "60",
            "page_size": "100",
            "tracking_window_minutes": "120",
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "",
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "30",
            "radarr__Default__search_missing_count": "5",
            "radarr__Default__search_cutoff_count": "5",
            "radarr__Default__missing_tag": "",
            "radarr__Default__cutoff_tag": "",
            "sonarr__Default__url": "http://sonarr:8989",
            "sonarr__Default__api_key": "",
            "sonarr__Default__enabled": "on",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    # Verify new settings were applied
    new_settings = test_app.state.settings
    assert new_settings.general.max_history_rows == 5000
    assert new_settings.general.request_timeout == 60
    assert new_settings.general.page_size == 100
    assert new_settings.general.tracking_window_minutes == 120


def test_save_settings_drain_timeout_round_trip(client, test_app):
    """POST /settings with shutdown_drain_timeout persists the float value (75-02 D-03)."""
    response = client.post(
        "/settings",
        data={
            "log_level": "info",
            "hard_max_per_cycle": "0",
            "max_history_rows": "1000",
            "request_timeout": "30",
            "page_size": "50",
            "tracking_window_minutes": "60",
            "shutdown_drain_timeout": "120.5",
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "",
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "30",
            "radarr__Default__search_missing_count": "5",
            "radarr__Default__search_cutoff_count": "5",
            "radarr__Default__missing_tag": "",
            "radarr__Default__cutoff_tag": "",
            "sonarr__Default__url": "http://sonarr:8989",
            "sonarr__Default__api_key": "",
            "sonarr__Default__enabled": "on",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    new_settings = test_app.state.settings
    assert new_settings.general.shutdown_drain_timeout == 120.5


def test_save_settings_drain_timeout_clamp_floor(client, test_app):
    """POST /settings with shutdown_drain_timeout below 1.0 clamps to 1.0 (75-02 D-03)."""
    response = client.post(
        "/settings",
        data={
            "log_level": "info",
            "hard_max_per_cycle": "0",
            "max_history_rows": "1000",
            "request_timeout": "30",
            "page_size": "50",
            "tracking_window_minutes": "60",
            "shutdown_drain_timeout": "0.5",
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "",
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "30",
            "radarr__Default__search_missing_count": "5",
            "radarr__Default__search_cutoff_count": "5",
            "radarr__Default__missing_tag": "",
            "radarr__Default__cutoff_tag": "",
            "sonarr__Default__url": "http://sonarr:8989",
            "sonarr__Default__api_key": "",
            "sonarr__Default__enabled": "on",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    new_settings = test_app.state.settings
    assert new_settings.general.shutdown_drain_timeout == 1.0


async def test_history_outcome_badge_colors(test_app):
    """History partial renders correct color classes for grabbed/partial/unresolved outcomes (STATS-05)."""
    db = test_app.state.db
    await insert_search_entry(db, "Radarr", "missing", "Grabbed Movie", outcome="grabbed")
    await insert_search_entry(db, "Sonarr", "missing", "Partial Show", outcome="partial")
    await insert_search_entry(db, "Radarr", "cutoff", "Unresolved Movie", outcome="unresolved")

    with TestClient(test_app) as tc:
        response = tc.get("/partials/history-results")
    assert response.status_code == 200
    assert "bg-green-500/20" in response.text, "Grabbed outcome should use green badge"
    assert "bg-amber-500/20" in response.text, "Partial outcome should use amber badge"
    assert "bg-gray-500/20" in response.text, "Unresolved outcome should use gray badge"


def test_format_duration_none():
    """_format_duration(None) returns '---' (STATS-04)."""
    from triggarr.web.routes import _format_duration

    assert _format_duration(None) == "---"


def test_format_duration_under_60():
    """_format_duration(30) returns '< 1m' (STATS-04)."""
    from triggarr.web.routes import _format_duration

    assert _format_duration(30) == "< 1m"


def test_format_duration_minutes():
    """_format_duration(300) returns '5m' (STATS-04)."""
    from triggarr.web.routes import _format_duration

    assert _format_duration(300) == "5m"


def test_format_duration_hours():
    """_format_duration(7500) returns '2h 5m' (STATS-04)."""
    from triggarr.web.routes import _format_duration

    assert _format_duration(7500) == "2h 5m"


# ---------------------------------------------------------------------------
# HARDEN-03: Temp file cleanup on os.replace failure
# ---------------------------------------------------------------------------


def test_save_settings_propagates_write_failure(test_app, tmp_path):
    """POST /settings returns 500 when _atomic_toml_write raises OSError (HARDEN-03)."""
    with TestClient(test_app, raise_server_exceptions=False) as tc, \
         patch("triggarr.web.routes._atomic_toml_write", side_effect=OSError("disk full")):
        response = tc.post(
            "/settings",
            data={
                "log_level": "info",
                "radarr__Default__url": "http://radarr:7878",
                "radarr__Default__api_key": "test-key",
                "radarr__Default__enabled": "on",
                "radarr__Default__search_interval": "30",
                "radarr__Default__search_missing_count": "5",
                "radarr__Default__search_cutoff_count": "5",
                "radarr__Default__missing_tag": "",
                "radarr__Default__cutoff_tag": "",
                "sonarr__Default__url": "",
                "sonarr__Default__api_key": "",
                "sonarr__Default__search_interval": "30",
                "sonarr__Default__search_missing_count": "5",
                "sonarr__Default__search_cutoff_count": "5",
                "sonarr__Default__missing_tag": "",
                "sonarr__Default__cutoff_tag": "",
            },
            follow_redirects=False,
        )
    # The OSError should propagate (500 error)
    assert response.status_code == 500


# ---------------------------------------------------------------------------
# CFG-01: Skip Unreleased Movies checkbox on settings page
# ---------------------------------------------------------------------------


def test_settings_page_shows_skip_unreleased_checkbox(client):
    """GET /settings response contains skip_unreleased checkbox input."""
    response = client.get("/settings")
    assert response.status_code == 200
    assert 'name="skip_unreleased"' in response.text, "Settings should show skip_unreleased checkbox"


def test_settings_page_skip_unreleased_checked_when_true(client):
    """GET /settings renders checkbox as checked when skip_unreleased=True (default)."""
    response = client.get("/settings")
    assert response.status_code == 200
    # Find the skip_unreleased input and verify it has checked attribute
    text = response.text
    import re
    match = re.search(r'<input[^>]*name="skip_unreleased"[^>]*>', text)
    assert match, "skip_unreleased checkbox input should exist"
    assert "checked" in match.group(0), "skip_unreleased checkbox should be checked when True"


def test_general_fields_submit_with_the_save_settings_form(client):
    """Every General-section control must associate with the same form the
    'Save Settings' button submits, or clicking Save drops them and they reset
    to form-defaults (e.g. skip_unreleased silently flips to False each save).

    Regression guard for the walkthrough finding: the General fields were in
    their own <form action=save_settings> with NO submit button, while the
    'Save Settings' button lived in a separate <form action=save_settings>
    holding only the instance fields. An HTML form submits only its associated
    controls, so the entire General section was unsavable from the UI.

    The General section cannot be literally nested in the instances <form> (the
    Security form sits between them and nested forms are illegal HTML), so the
    fix associates each General control with the instances form via the
    form="settings-form" attribute. This test pins that association: the
    instances <form> carries id="settings-form", the 'Save Settings' button is
    inside it, and every General control names that form.
    """
    text = client.get("/settings").text

    # The submitting form must declare the id the General fields reference.
    assert 'id="settings-form"' in text, "instances form must declare id=settings-form"

    # The 'Save Settings' submit button must be inside the form with that id
    # (i.e. after the <form id="settings-form"> open and before its </form>).
    form_open = text.find('id="settings-form"')
    save_idx = text.find("Save Settings")
    form_close = text.find("</form>", form_open)
    assert save_idx != -1, "'Save Settings' button should exist"
    assert form_open < save_idx < form_close, (
        "'Save Settings' button must live inside <form id=settings-form>"
    )

    # Every General control must carry form="settings-form" so it submits with
    # that form. skip_unreleased is the field the walkthrough caught resetting;
    # the rest are the other General controls that were equally unsavable.
    general_fields = [
        "skip_unreleased",
        "log_level",
        "hard_max_per_cycle",
        "max_history_rows",
        "request_timeout",
        "page_size",
        "tracking_window_minutes",
        "max_consecutive_failures",
    ]
    for name in general_fields:
        # Find the control's opening tag and confirm form="settings-form" is on it.
        idx = text.find(f'name="{name}"')
        assert idx != -1, f"General field {name!r} should exist on the settings page"
        tag_open = text.rfind("<", 0, idx)
        tag_close = text.find(">", idx)
        tag = text[tag_open:tag_close]
        assert 'form="settings-form"' in tag, (
            f"General field {name!r} must carry form=\"settings-form\" so it "
            f"submits with the Save Settings button; tag was: {tag}"
        )


def test_save_settings_skip_unreleased_on(client, test_app):
    """POST /settings with skip_unreleased=on saves True to config."""
    response = client.post(
        "/settings",
        data={
            "log_level": "info",
            "hard_max_per_cycle": "0",
            "max_history_rows": "1000",
            "request_timeout": "30",
            "page_size": "50",
            "tracking_window_minutes": "60",
            "skip_unreleased": "on",
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "",
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "30",
            "radarr__Default__search_missing_count": "5",
            "radarr__Default__search_cutoff_count": "5",
            "radarr__Default__missing_tag": "",
            "radarr__Default__cutoff_tag": "",
            "sonarr__Default__url": "http://sonarr:8989",
            "sonarr__Default__api_key": "",
            "sonarr__Default__enabled": "on",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    content = test_app.state.config_path.read_text()
    assert "skip_unreleased = true" in content, "TOML should contain skip_unreleased = true"


def test_build_app_context_includes_total_items(client, test_app):
    """_build_app_context shows missing_count as hero number in recessed sub-card."""
    test_app.state.triggarr_state["radarr"]["Default"]["missing_count"] = 30
    test_app.state.triggarr_state["radarr"]["Default"]["total_items"] = 1200
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert ">30<" in response.text.replace(" ", "").replace("\n", ""), "Missing count should render as hero number"


def test_build_app_context_no_total_items_fallback(client, test_app):
    """App card shows missing_count hero number even when total_items is absent."""
    test_app.state.triggarr_state["radarr"]["Default"]["missing_count"] = 42
    test_app.state.triggarr_state["radarr"]["Default"].pop("total_items", None)
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert ">42<" in response.text.replace(" ", "").replace("\n", ""), "Missing count should render as hero number"


def test_app_card_skip_indicator_shown(client, test_app):
    """App card shows amber skip badge using missing_monitored - missing_eligible (F1 fix)."""
    test_app.state.triggarr_state["radarr"]["Default"]["missing_count"] = 50
    test_app.state.triggarr_state["radarr"]["Default"]["missing_monitored"] = 42
    test_app.state.triggarr_state["radarr"]["Default"]["missing_eligible"] = 30
    test_app.state.settings.general.skip_unreleased = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    # Badge should show 42-30=12, NOT 50-30=20
    assert "12 skipped" in response.text, "Should show skip count badge using monitored count"
    assert "20 skipped" not in response.text, "Should NOT use raw missing_count for badge math"
    assert "text-amber-400" in response.text, "Skip badge should use amber styling"


def test_app_card_no_skip_when_disabled(client, test_app):
    """App card does NOT show skip badge when skip_unreleased is False (DASH-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["missing_eligible"] = 30
    test_app.state.triggarr_state["radarr"]["Default"]["missing_monitored"] = 42
    test_app.state.triggarr_state["radarr"]["Default"]["missing_count"] = 50
    test_app.state.settings.general.skip_unreleased = False
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "skipped (unreleased)" not in response.text, "No skip badge when skip_unreleased is off"


# ---------------------------------------------------------------------------
# INST-05/06, TAG-06: Multi-instance settings CRUD, tags, add/remove
# ---------------------------------------------------------------------------


@pytest.fixture
async def multi_instance_app(tmp_path):
    """Build a FastAPI app with multiple radarr instances for multi-instance tests."""
    log_buffer.clear()
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await init_db(db, db_path)
        app.state.db = db

        app.state.triggarr_state = {
            "radarr": {
                "Default": {"last_run": None, "connected": True},
                "4K": {"last_run": None, "connected": True},
            },
            "sonarr": {
                "Default": {"last_run": None, "connected": True},
            },
            "lidarr": {
                "Default": {"last_run": None, "connected": None},
            },
            "search_log": [],
        }

        app.state.settings = Settings(
            general=GeneralConfig(),
            radarr={
                "Default": InstanceConfig(
                    url="http://radarr:7878",
                    api_key="radarr-default-key",
                    enabled=True,
                    missing_tag="wanted",
                    cutoff_tag="upgrade",
                ),
                "4K": InstanceConfig(
                    url="http://radarr4k:7878",
                    api_key="radarr-4k-key",
                    enabled=False,
                    missing_tag="wanted-4k",
                    cutoff_tag="",
                ),
            },
            sonarr={
                "Default": InstanceConfig(
                    url="http://sonarr:8989",
                    api_key="sonarr-key",
                    enabled=True,
                ),
            },
        )

        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_job.next_run_time = None
        mock_scheduler.get_job.return_value = mock_job
        app.state.scheduler = mock_scheduler

        radarr_default_client = MagicMock()
        radarr_default_client.close = AsyncMock()
        radarr_4k_client = MagicMock()
        radarr_4k_client.close = AsyncMock()
        sonarr_client = MagicMock()
        sonarr_client.close = AsyncMock()
        app.state.radarr_clients = {"Default": radarr_default_client, "4K": radarr_4k_client}
        app.state.sonarr_clients = {"Default": sonarr_client}
        lidarr_client = MagicMock()
        lidarr_client.close = AsyncMock()
        app.state.lidarr_clients = {"Default": lidarr_client}

        app.state.config_path = tmp_path / "triggarr.toml"
        app.state.state_path = tmp_path / "state.json"
        app.state.search_lock = asyncio.Lock()
        app.state.search_lock_holder = None
        # SAFETY-03: failure counter + persistence flag (needed by _run_one_cycle)
        app.state.search_failures = {}
        app.state.persistence_degraded = False
        app.state.last_search_time = {}
        app.state.last_refresh_time = {}
        app.state.last_health_check = None
        # RES-03: tag cache (read by search_now resolver, popped by
        # save_settings / remove_instance invalidation).
        app.state.tag_cache = {}

        yield app


@pytest.fixture
def multi_client(multi_instance_app):
    """Create a TestClient for the multi-instance test app."""
    return TestClient(multi_instance_app)


def test_settings_lists_all_instances(multi_client):
    """GET /settings shows all configured instances (not just first per app type)."""
    response = multi_client.get("/settings")
    assert response.status_code == 200
    assert "Default" in response.text, "Settings should show Default instance"
    assert "4K" in response.text, "Settings should show 4K instance"


def test_settings_contains_tag_fields(multi_client):
    """GET /settings response contains missing_tag and cutoff_tag field names."""
    response = multi_client.get("/settings")
    assert response.status_code == 200
    assert "missing_tag" in response.text, "Settings should contain missing_tag fields"
    assert "cutoff_tag" in response.text, "Settings should contain cutoff_tag fields"


def test_settings_never_leaks_api_keys_multi(multi_client):
    """GET /settings with multiple instances never contains raw API key values."""
    response = multi_client.get("/settings")
    assert response.status_code == 200
    assert "radarr-default-key" not in response.text
    assert "radarr-4k-key" not in response.text
    assert "sonarr-key" not in response.text


def test_save_settings_multi_instance(multi_client, multi_instance_app):
    """POST /settings with multi-instance form fields saves all instances to TOML."""
    response = multi_client.post(
        "/settings",
        data={
            "log_level": "info",
            "hard_max_per_cycle": "0",
            "max_history_rows": "1000",
            "request_timeout": "30",
            "page_size": "50",
            "tracking_window_minutes": "60",
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "",
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "30",
            "radarr__Default__search_missing_count": "5",
            "radarr__Default__search_cutoff_count": "5",
            "radarr__Default__missing_tag": "wanted",
            "radarr__Default__cutoff_tag": "upgrade",
            "radarr__4K__url": "http://radarr4k:7878",
            "radarr__4K__api_key": "new-4k-key",
            "radarr__4K__enabled": "on",
            "radarr__4K__search_interval": "60",
            "radarr__4K__search_missing_count": "3",
            "radarr__4K__search_cutoff_count": "2",
            "radarr__4K__missing_tag": "wanted-4k",
            "radarr__4K__cutoff_tag": "",
            "sonarr__Default__url": "http://sonarr:8989",
            "sonarr__Default__api_key": "",
            "sonarr__Default__enabled": "on",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    content = multi_instance_app.state.config_path.read_text()
    assert "radarr4k" in content, "4K instance URL should be saved"
    assert "new-4k-key" in content, "New 4K API key should be saved"


def test_save_settings_preserves_api_keys_multi(multi_client, multi_instance_app):
    """POST /settings with empty api_key preserves existing keys for all instances."""
    response = multi_client.post(
        "/settings",
        data={
            "log_level": "info",
            "hard_max_per_cycle": "0",
            "max_history_rows": "1000",
            "request_timeout": "30",
            "page_size": "50",
            "tracking_window_minutes": "60",
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "",
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "30",
            "radarr__Default__search_missing_count": "5",
            "radarr__Default__search_cutoff_count": "5",
            "radarr__Default__missing_tag": "",
            "radarr__Default__cutoff_tag": "",
            "radarr__4K__url": "http://radarr4k:7878",
            "radarr__4K__api_key": "",
            "radarr__4K__enabled": "on",
            "radarr__4K__search_interval": "30",
            "radarr__4K__search_missing_count": "5",
            "radarr__4K__search_cutoff_count": "5",
            "radarr__4K__missing_tag": "",
            "radarr__4K__cutoff_tag": "",
            "sonarr__Default__url": "http://sonarr:8989",
            "sonarr__Default__api_key": "",
            "sonarr__Default__enabled": "on",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    content = multi_instance_app.state.config_path.read_text()
    assert "radarr-default-key" in content, "Default radarr key should be preserved"
    assert "radarr-4k-key" in content, "4K radarr key should be preserved"
    assert "sonarr-key" in content, "Sonarr key should be preserved"


def test_save_settings_tag_fields_preserved(multi_client, multi_instance_app):
    """POST /settings preserves tag field values for all instances."""
    response = multi_client.post(
        "/settings",
        data={
            "log_level": "info",
            "hard_max_per_cycle": "0",
            "max_history_rows": "1000",
            "request_timeout": "30",
            "page_size": "50",
            "tracking_window_minutes": "60",
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "",
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "30",
            "radarr__Default__search_missing_count": "5",
            "radarr__Default__search_cutoff_count": "5",
            "radarr__Default__missing_tag": "my-tag",
            "radarr__Default__cutoff_tag": "my-cutoff",
            "radarr__4K__url": "http://radarr4k:7878",
            "radarr__4K__api_key": "",
            "radarr__4K__search_interval": "30",
            "radarr__4K__search_missing_count": "5",
            "radarr__4K__search_cutoff_count": "5",
            "radarr__4K__missing_tag": "4k-tag",
            "radarr__4K__cutoff_tag": "",
            "sonarr__Default__url": "http://sonarr:8989",
            "sonarr__Default__api_key": "",
            "sonarr__Default__enabled": "on",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    new_settings = multi_instance_app.state.settings
    assert new_settings.radarr["Default"].missing_tag == "my-tag"
    assert new_settings.radarr["Default"].cutoff_tag == "my-cutoff"
    assert new_settings.radarr["4K"].missing_tag == "4k-tag"


def test_save_settings_enable_disable_per_instance(multi_client, multi_instance_app):
    """POST /settings handles enable/disable per instance (checkbox on/off)."""
    response = multi_client.post(
        "/settings",
        data={
            "log_level": "info",
            "hard_max_per_cycle": "0",
            "max_history_rows": "1000",
            "request_timeout": "30",
            "page_size": "50",
            "tracking_window_minutes": "60",
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "",
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "30",
            "radarr__Default__search_missing_count": "5",
            "radarr__Default__search_cutoff_count": "5",
            "radarr__Default__missing_tag": "",
            "radarr__Default__cutoff_tag": "",
            # 4K: no enabled checkbox = disabled
            "radarr__4K__url": "http://radarr4k:7878",
            "radarr__4K__api_key": "",
            "radarr__4K__search_interval": "30",
            "radarr__4K__search_missing_count": "5",
            "radarr__4K__search_cutoff_count": "5",
            "radarr__4K__missing_tag": "",
            "radarr__4K__cutoff_tag": "",
            "sonarr__Default__url": "http://sonarr:8989",
            "sonarr__Default__api_key": "",
            "sonarr__Default__enabled": "on",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    new_settings = multi_instance_app.state.settings
    assert new_settings.radarr["Default"].enabled is True
    assert new_settings.radarr["4K"].enabled is False


def test_tag_autocomplete_returns_options(multi_instance_app):
    """GET /api/tags/radarr/Default returns HTML option elements when client has tags."""
    from triggarr.clients.base import Tag

    mock_client = multi_instance_app.state.radarr_clients["Default"]
    mock_client.get_tags = AsyncMock(return_value=[Tag(id=1, label="wanted"), Tag(id=2, label="upgrade")])

    with TestClient(multi_instance_app) as tc:
        response = tc.get("/api/tags/radarr/Default")
    assert response.status_code == 200
    assert '<option value="wanted">' in response.text
    assert '<option value="upgrade">' in response.text


def test_tag_autocomplete_value_error_returns_empty(multi_instance_app):
    """GET /api/tags/radarr/Default returns 200 with an empty body on a malformed-JSON ValueError (D-03)."""
    mock_client = multi_instance_app.state.radarr_clients["Default"]
    mock_client.get_tags = AsyncMock(side_effect=ValueError("Expected JSON array from /api/v3/tag, got dict"))

    with TestClient(multi_instance_app) as tc:
        response = tc.get("/api/tags/radarr/Default")
    assert response.status_code == 200
    assert response.text == ""
    assert "Traceback" not in response.text
    assert "ValueError" not in response.text
    assert "Expecting value" not in response.text


def test_tag_autocomplete_json_decode_error_returns_empty(multi_instance_app):
    """GET /api/tags/radarr/Default returns 200 with an empty body on a JSONDecodeError (D-03)."""
    mock_client = multi_instance_app.state.radarr_clients["Default"]
    mock_client.get_tags = AsyncMock(side_effect=json.JSONDecodeError("Expecting value", "<html>", 0))

    with TestClient(multi_instance_app) as tc:
        response = tc.get("/api/tags/radarr/Default")
    assert response.status_code == 200
    assert response.text == ""
    assert "Traceback" not in response.text
    assert "ValueError" not in response.text
    assert "Expecting value" not in response.text


def test_tag_autocomplete_no_client(multi_instance_app):
    """GET /api/tags/radarr/Nonexistent returns empty string when no client exists."""
    with TestClient(multi_instance_app) as tc:
        response = tc.get("/api/tags/radarr/Nonexistent")
    assert response.status_code == 200
    assert response.text == ""


def test_tag_autocomplete_invalid_app(multi_instance_app):
    """GET /api/tags/invalid/Default returns empty string."""
    with TestClient(multi_instance_app) as tc:
        response = tc.get("/api/tags/invalid/Default")
    assert response.status_code == 200
    assert response.text == ""


def test_add_instance_happy_path(multi_instance_app):
    """POST /api/instance/add with valid name creates new instance entry."""
    with TestClient(multi_instance_app) as tc:
        response = tc.post(
            "/api/instance/add",
            data={"app_name": "radarr", "instance_name": "Anime"},
            follow_redirects=False,
        )
    assert response.status_code == 303
    assert "Anime" in multi_instance_app.state.settings.radarr


def test_add_instance_duplicate_rejected(multi_instance_app):
    """POST /api/instance/add with existing name returns error."""
    with TestClient(multi_instance_app) as tc:
        response = tc.post(
            "/api/instance/add",
            data={"app_name": "radarr", "instance_name": "Default"},
            follow_redirects=False,
        )
    assert response.status_code == 400
    assert "already exists" in response.text.lower()


def test_add_instance_max_limit(multi_instance_app):
    """POST /api/instance/add when at 5 instances returns error."""
    # Add 3 more to get to 5 (already have Default + 4K = 2)
    settings = multi_instance_app.state.settings
    for i in range(3):
        settings.radarr[f"Extra{i}"] = InstanceConfig()

    with TestClient(multi_instance_app) as tc:
        response = tc.post(
            "/api/instance/add",
            data={"app_name": "radarr", "instance_name": "TooMany"},
            follow_redirects=False,
        )
    assert response.status_code == 400
    assert "maximum" in response.text.lower()


def test_add_instance_assigns_fresh_id(multi_instance_app):
    """POST /api/instance/add assigns a fresh 32-hex id, distinct from every existing id (ATTR-03)."""
    settings = multi_instance_app.state.settings
    settings.radarr["Default"].id = "a" * 32
    settings.radarr["4K"].id = "b" * 32
    settings.sonarr["Default"].id = "c" * 32

    with TestClient(multi_instance_app) as tc:
        response = tc.post(
            "/api/instance/add",
            data={"app_name": "sonarr", "instance_name": "4K"},
            follow_redirects=False,
        )
    assert response.status_code == 303

    new_id = multi_instance_app.state.settings.sonarr["4K"].id
    assert re.fullmatch(r"[0-9a-f]{32}", new_id)
    existing_ids = {"a" * 32, "b" * 32, "c" * 32}
    assert new_id not in existing_ids
    assert multi_instance_app.state.settings.radarr["Default"].id == "a" * 32
    assert multi_instance_app.state.settings.radarr["4K"].id == "b" * 32
    assert multi_instance_app.state.settings.sonarr["Default"].id == "c" * 32


def test_remove_instance_happy_path(multi_instance_app):
    """POST /api/instance/remove removes instance and cleans up."""
    with TestClient(multi_instance_app) as tc:
        response = tc.post(
            "/api/instance/remove/radarr/4K",
            follow_redirects=False,
        )
    assert response.status_code == 303
    assert "4K" not in multi_instance_app.state.settings.radarr


def test_remove_instance_keeps_other_ids(multi_instance_app):
    """POST /api/instance/remove leaves the remaining instances' ids unchanged (ATTR-03)."""
    settings = multi_instance_app.state.settings
    settings.radarr["Default"].id = "a" * 32
    settings.radarr["4K"].id = "b" * 32
    settings.sonarr["Default"].id = "c" * 32

    with TestClient(multi_instance_app) as tc:
        response = tc.post(
            "/api/instance/remove/radarr/4K",
            follow_redirects=False,
        )
    assert response.status_code == 303
    assert "4K" not in multi_instance_app.state.settings.radarr
    assert multi_instance_app.state.settings.radarr["Default"].id == "a" * 32
    assert multi_instance_app.state.settings.sonarr["Default"].id == "c" * 32


def test_remove_instance_nonexistent(multi_instance_app):
    """POST /api/instance/remove for nonexistent instance returns error."""
    with TestClient(multi_instance_app) as tc:
        response = tc.post(
            "/api/instance/remove/radarr/Nonexistent",
            follow_redirects=False,
        )
    assert response.status_code == 400


def test_remove_instance_uses_hx_redirect_when_htmx(multi_instance_app):
    """SEC-01 / codex M0: HTMX callers receive HX-Redirect so the browser issues a
    full navigation. Without this, the body-swap of a fresh settings.html page
    would inherit the OLD CSP nonce -- the new `<script nonce="NEW">` would be
    blocked by the active document's CSP policy.
    """
    with TestClient(multi_instance_app) as tc:
        response = tc.post(
            "/api/instance/remove/radarr/4K",
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )
    assert response.status_code == 200
    assert response.headers.get("HX-Redirect", "").endswith("/settings")
    # Body should be empty (HTMX discards it before issuing the redirect).
    assert response.text == ""


def test_remove_instance_uses_303_for_non_htmx(multi_instance_app):
    """Backwards compat: non-HTMX callers (curl, browsers without HX-Request)
    still get a 303 + Location header.
    """
    with TestClient(multi_instance_app) as tc:
        response = tc.post(
            "/api/instance/remove/radarr/Default",
            follow_redirects=False,
        )
    assert response.status_code == 303
    assert response.headers.get("location", "").endswith("/settings")


@pytest.mark.parametrize("hx_header", [None, "true"], ids=["plain", "htmx"])
def test_remove_instance_write_failure_keeps_live_state(multi_instance_app, hx_header):
    """A failed settings write during removal leaves live settings, the
    scheduler job, the client registry, the state entry and the tag-cache
    entry exactly as before the attempt (D-02, D-03).
    """
    import time

    multi_instance_app.state.tag_cache[("radarr", "4K")] = ([], time.monotonic())
    original_4k = multi_instance_app.state.settings.radarr["4K"]

    headers = {"HX-Request": hx_header} if hx_header else {}
    with (
        TestClient(multi_instance_app, raise_server_exceptions=False) as tc,
        patch("triggarr.web.routes._atomic_toml_write", side_effect=OSError("disk full")),
    ):
        tc.post(
            "/api/instance/remove/radarr/4K",
            headers=headers,
            follow_redirects=False,
        )

    assert "4K" in multi_instance_app.state.settings.radarr
    assert multi_instance_app.state.settings.radarr["4K"] is original_4k
    multi_instance_app.state.scheduler.remove_job.assert_not_called()
    assert "4K" in multi_instance_app.state.radarr_clients
    multi_instance_app.state.radarr_clients["4K"].close.assert_not_awaited()
    assert "4K" in multi_instance_app.state.triggarr_state["radarr"]
    assert ("radarr", "4K") in multi_instance_app.state.tag_cache


async def test_remove_instance_concurrent_removals_both_persist(multi_instance_app):
    """Two concurrent removals of different instances both remain removed,
    live and on disk -- neither request's stale snapshot resurrects the
    other's removed instance (D-02, T-87-03b).
    """
    import tomllib

    settings = multi_instance_app.state.settings
    settings.radarr["Extra"] = InstanceConfig(
        url="http://radarr-extra:7878",
        api_key="radarr-extra-key",
        enabled=True,
    )
    multi_instance_app.state.radarr_clients["Extra"] = MagicMock(close=AsyncMock())
    multi_instance_app.state.triggarr_state["radarr"]["Extra"] = {"last_run": None, "connected": True}

    lock = multi_instance_app.state.search_lock
    await lock.acquire()

    async with httpx.AsyncClient(
        transport=ASGITransport(app=multi_instance_app), base_url="http://test"
    ) as ac:
        task_4k = asyncio.create_task(ac.post("/api/instance/remove/radarr/4K"))
        task_extra = asyncio.create_task(ac.post("/api/instance/remove/radarr/Extra"))

        for _ in range(200):
            if len(getattr(lock, "_waiters", None) or ()) == 2:
                break
            await asyncio.sleep(0)
        assert len(getattr(lock, "_waiters", None) or ()) == 2, (
            "both removal requests must be queued on search_lock before it is released"
        )

        lock.release()
        response_4k, response_extra = await asyncio.gather(task_4k, task_extra)

    assert response_4k.status_code == 303
    assert response_extra.status_code == 303
    assert "4K" not in multi_instance_app.state.settings.radarr
    assert "Extra" not in multi_instance_app.state.settings.radarr
    assert "Default" in multi_instance_app.state.settings.radarr

    on_disk = tomllib.loads(multi_instance_app.state.config_path.read_text())
    assert "4K" not in on_disk["radarr"]
    assert "Extra" not in on_disk["radarr"]
    assert "Default" in on_disk["radarr"]


async def test_remove_instance_concurrent_same_instance_second_is_not_found(multi_instance_app):
    """Two concurrent removals of the same instance: one succeeds, the other
    gets the existing not-found 400, and the client is closed exactly once.
    """
    client_4k = multi_instance_app.state.radarr_clients["4K"]
    lock = multi_instance_app.state.search_lock
    await lock.acquire()

    async with httpx.AsyncClient(
        transport=ASGITransport(app=multi_instance_app), base_url="http://test"
    ) as ac:
        task_a = asyncio.create_task(ac.post("/api/instance/remove/radarr/4K"))
        task_b = asyncio.create_task(ac.post("/api/instance/remove/radarr/4K"))

        for _ in range(200):
            if len(getattr(lock, "_waiters", None) or ()) == 2:
                break
            await asyncio.sleep(0)
        assert len(getattr(lock, "_waiters", None) or ()) == 2, (
            "both removal requests must be queued on search_lock before it is released"
        )

        lock.release()
        response_a, response_b = await asyncio.gather(task_a, task_b)

    statuses = sorted([response_a.status_code, response_b.status_code])
    assert statuses == [303, 400]
    not_found_response = response_a if response_a.status_code == 400 else response_b
    assert "Instance '4K' not found" in not_found_response.text
    assert client_4k.close.await_count == 1


async def test_add_instance_during_removal_write_does_not_resurrect_removed(multi_instance_app):
    """An Add Instance submitted while a removal is still writing the settings
    file must not bring the removed instance back (Codex F001).

    Sequence: the removal holds search_lock with its writer paused; Add
    Instance is submitted and gets as far as it can; the writer is released.
    Afterwards the removed instance is absent from the settings file, live
    settings, the client registry and state, and the added one is present.
    """
    import threading
    import tomllib

    from triggarr.config import _atomic_toml_write as real_atomic_write
    from triggarr.web.routes import validate_instance_name as real_validate_instance_name

    writer_started = threading.Event()
    release_writer = threading.Event()
    write_count = 0

    def gated_atomic_write(path, data, **kwargs):
        nonlocal write_count
        write_count += 1
        if write_count == 1:
            writer_started.set()
            if not release_writer.wait(10):
                raise RuntimeError("test gate timed out")
        return real_atomic_write(path, data, **kwargs)

    add_reached_validation = asyncio.Event()

    def recording_validate(name):
        # Add Instance has no await between this call and its wait for
        # search_lock, so once this fires the request has either already
        # taken its settings snapshot (unfixed code) or is about to queue on
        # the lock (fixed code).
        add_reached_validation.set()
        return real_validate_instance_name(name)

    client_4k = multi_instance_app.state.radarr_clients["4K"]

    try:
        with (
            patch("triggarr.web.routes._atomic_toml_write", side_effect=gated_atomic_write),
            patch("triggarr.web.routes.validate_instance_name", side_effect=recording_validate),
        ):
            async with httpx.AsyncClient(
                transport=ASGITransport(app=multi_instance_app), base_url="http://test"
            ) as ac:
                removal = asyncio.create_task(ac.post("/api/instance/remove/radarr/4K"))
                for _ in range(2000):
                    if writer_started.is_set():
                        break
                    await asyncio.sleep(0.005)
                assert writer_started.is_set(), "the removal's settings write must be in progress"
                assert "4K" in multi_instance_app.state.settings.radarr

                addition = asyncio.create_task(
                    ac.post("/api/instance/add", data={"app_name": "radarr", "instance_name": "Extra"})
                )
                await asyncio.wait_for(add_reached_validation.wait(), timeout=10)
                for _ in range(5):
                    await asyncio.sleep(0)
                assert not addition.done(), "Add Instance must wait for the removal to finish"

                release_writer.set()
                removal_response, add_response = await asyncio.gather(removal, addition)
    finally:
        release_writer.set()

    assert removal_response.status_code == 303
    assert add_response.status_code == 303

    on_disk = tomllib.loads(multi_instance_app.state.config_path.read_text())
    assert "4K" not in on_disk["radarr"]
    assert "Extra" in on_disk["radarr"]
    assert "Default" in on_disk["radarr"]

    live = multi_instance_app.state.settings.radarr
    assert "4K" not in live
    assert "Extra" in live
    assert "Default" in live

    assert "4K" not in multi_instance_app.state.radarr_clients
    assert client_4k.close.await_count == 1

    radarr_state = multi_instance_app.state.triggarr_state["radarr"]
    assert "4K" not in radarr_state
    assert "Extra" in radarr_state


async def test_general_settings_save_during_removal_write_does_not_resurrect_removed(multi_instance_app):
    """A general-only POST /settings submitted while a removal is still writing
    the settings file must not bring the removed instance back.

    Sequence: the removal holds search_lock with its writer paused; the
    settings save (log_level only, so every instance is preserved from the
    current settings) queues on the lock; the writer is released. Afterwards
    the removed instance is absent from the settings file, live settings, the
    client registry and the scheduler.
    """
    import threading
    import tomllib

    from triggarr.config import _atomic_toml_write as real_atomic_write

    settings = multi_instance_app.state.settings
    settings.radarr["4K"] = settings.radarr["4K"].model_copy(update={"enabled": True})

    writer_started = threading.Event()
    release_writer = threading.Event()
    write_count = 0

    def gated_atomic_write(path, data, **kwargs):
        nonlocal write_count
        write_count += 1
        if write_count == 1:
            writer_started.set()
            if not release_writer.wait(10):
                raise RuntimeError("test gate timed out")
        return real_atomic_write(path, data, **kwargs)

    client_4k = multi_instance_app.state.radarr_clients["4K"]
    scheduler = multi_instance_app.state.scheduler
    lock = multi_instance_app.state.search_lock

    try:
        with patch("triggarr.web.routes._atomic_toml_write", side_effect=gated_atomic_write):
            async with httpx.AsyncClient(
                transport=ASGITransport(app=multi_instance_app), base_url="http://test"
            ) as ac:
                removal = asyncio.create_task(ac.post("/api/instance/remove/radarr/4K"))
                for _ in range(2000):
                    if writer_started.is_set():
                        break
                    await asyncio.sleep(0.005)
                assert writer_started.is_set(), "the removal's settings write must be in progress"
                assert "4K" in multi_instance_app.state.settings.radarr

                save = asyncio.create_task(ac.post("/settings", data={"log_level": "info"}))
                for _ in range(2000):
                    if len(getattr(lock, "_waiters", None) or ()) == 1:
                        break
                    await asyncio.sleep(0.005)
                assert len(getattr(lock, "_waiters", None) or ()) == 1, (
                    "the settings save must be queued on search_lock behind the removal"
                )
                assert not save.done()

                release_writer.set()
                removal_response, save_response = await asyncio.gather(removal, save)
    finally:
        release_writer.set()

    assert removal_response.status_code == 303
    assert save_response.status_code == 303

    on_disk = tomllib.loads(multi_instance_app.state.config_path.read_text())
    assert "4K" not in on_disk["radarr"]
    assert "Default" in on_disk["radarr"]

    live = multi_instance_app.state.settings.radarr
    assert "4K" not in live
    assert "Default" in live
    assert multi_instance_app.state.settings.general.log_level == "info"

    assert "4K" not in multi_instance_app.state.radarr_clients
    assert client_4k.close.await_count == 1

    scheduled_ids = [c.args[0] for c in scheduler.reschedule_job.call_args_list] + [
        c.kwargs.get("id") for c in scheduler.add_job.call_args_list
    ]
    assert "radarr_4K_search" not in scheduled_ids


async def test_add_instance_duplicate_check_uses_settings_current_under_lock(multi_instance_app):
    """Two overlapping Add Instance requests for the same name: the duplicate
    check runs against the settings current once the lock is held, so exactly
    one is created and the other gets the existing 400 (Codex F001).
    """
    lock = multi_instance_app.state.search_lock
    await lock.acquire()
    try:
        async with httpx.AsyncClient(
            transport=ASGITransport(app=multi_instance_app), base_url="http://test"
        ) as ac:
            form = {"app_name": "radarr", "instance_name": "Extra"}
            task_a = asyncio.create_task(ac.post("/api/instance/add", data=form))
            task_b = asyncio.create_task(ac.post("/api/instance/add", data=form))
            for _ in range(50):
                await asyncio.sleep(0.005)
            assert not task_a.done()
            assert not task_b.done()

            lock.release()
            response_a, response_b = await asyncio.gather(task_a, task_b)
    finally:
        if lock.locked():
            lock.release()

    assert sorted([response_a.status_code, response_b.status_code]) == [303, 400]
    duplicate = response_a if response_a.status_code == 400 else response_b
    assert duplicate.text == "Instance 'Extra' already exists"
    assert "Extra" in multi_instance_app.state.settings.radarr


def test_remove_instance_real_write_failure_logs_one_error(multi_instance_app):
    """A failed real write during removal logs exactly one error-level entry,
    naming the app, the instance and the system reason; the writer's own
    "Config write failed" line is suppressed for this caller (D-07).
    """
    config_path = multi_instance_app.state.config_path
    pre_existing = b"placeholder"
    config_path.write_bytes(pre_existing)

    records: list = []
    handler_id = logger.add(lambda m: records.append(m.record), level="ERROR")
    try:
        with (
            TestClient(multi_instance_app, raise_server_exceptions=False) as tc,
            patch(
                "triggarr.config.os.replace",
                side_effect=OSError(errno.ENOSPC, "No space left on device"),
            ),
        ):
            tc.post(
                "/api/instance/remove/radarr/4K",
                headers={"HX-Request": "true"},
                follow_redirects=False,
            )
    finally:
        logger.remove(handler_id)

    assert len(records) == 1
    message = records[0]["message"]
    assert "radarr" in message
    assert "4K" in message
    assert "No space left on device" in message
    assert not any("Config write failed" in r["message"] for r in records)
    assert "4K" in multi_instance_app.state.settings.radarr

    remaining_tmp = list(config_path.parent.glob("*.tmp"))
    assert remaining_tmp == []
    assert config_path.read_bytes() == pre_existing


def test_remove_instance_write_failure_htmx_shows_message(multi_instance_app):
    """A failed save via htmx returns 200 with the fixed D-05 message and no
    HX-Redirect header, so htmx swaps the message into the row target
    (D-04, D-05, D-06).
    """
    with (
        TestClient(multi_instance_app, raise_server_exceptions=False) as tc,
        patch(
            "triggarr.web.routes._atomic_toml_write",
            side_effect=OSError("disk full: /secret/path/triggarr.toml"),
        ),
    ):
        response = tc.post(
            "/api/instance/remove/radarr/4K",
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert "HX-Redirect" not in response.headers
    assert response.text == (
        "'4K' was not removed: the settings file could not be saved. "
        "Nothing was changed. Check the Triggarr log for details."
    )


def test_remove_instance_write_failure_plain_returns_500(multi_instance_app):
    """A failed save via a direct, non-htmx POST returns a non-2xx response
    carrying the same D-05 wording and no Location header.
    """
    with (
        TestClient(multi_instance_app, raise_server_exceptions=False) as tc,
        patch("triggarr.web.routes._atomic_toml_write", side_effect=OSError("disk full")),
    ):
        response = tc.post(
            "/api/instance/remove/radarr/4K",
            follow_redirects=False,
        )

    assert response.status_code == 500
    assert "Location" not in response.headers
    assert response.text == (
        "'4K' was not removed: the settings file could not be saved. "
        "Nothing was changed. Check the Triggarr log for details."
    )


def test_remove_instance_write_failure_no_internal_detail(multi_instance_app):
    """The failed-removal response never leaks the exception, the config
    path, or a traceback (T-87-01).
    """
    with (
        TestClient(multi_instance_app, raise_server_exceptions=False) as tc,
        patch(
            "triggarr.web.routes._atomic_toml_write",
            side_effect=OSError("disk full: /secret/path/triggarr.toml"),
        ),
    ):
        response = tc.post(
            "/api/instance/remove/radarr/4K",
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )

    body = response.text
    assert "OSError" not in body
    assert "disk full" not in body
    assert "/secret/path" not in body
    assert "triggarr.toml" not in body
    assert "Traceback" not in body
    assert str(multi_instance_app.state.config_path) not in body


def test_remove_instance_write_failure_escapes_name(multi_instance_app):
    """The instance name in the D-05 message is html-escaped (T-87-02)."""
    multi_instance_app.state.settings.radarr["<b>&x"] = InstanceConfig(
        url="http://radarr-xss:7878",
        api_key="radarr-xss-key",
        enabled=True,
    )
    multi_instance_app.state.radarr_clients["<b>&x"] = MagicMock(close=AsyncMock())
    multi_instance_app.state.triggarr_state["radarr"]["<b>&x"] = {"last_run": None, "connected": True}

    with (
        TestClient(multi_instance_app, raise_server_exceptions=False) as tc,
        patch("triggarr.web.routes._atomic_toml_write", side_effect=OSError("disk full")),
    ):
        response = tc.post(
            "/api/instance/remove/radarr/%3Cb%3E%26x",
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert response.text.startswith("'&lt;b&gt;&amp;x' was not removed")
    assert "<b>" not in response.text


@pytest.mark.parametrize(
    ("hx_header", "expected_status"),
    [(None, 500), ("true", 200)],
    ids=["plain", "htmx"],
)
def test_remove_instance_unexpected_write_error_keeps_live_state(multi_instance_app, hx_header, expected_status):
    """A non-OSError failure of the settings write is handled like an OSError
    one: live state is untouched and the fixed D-05 response is returned with
    no internal detail (WR-02a).
    """
    import time

    multi_instance_app.state.tag_cache[("radarr", "4K")] = ([], time.monotonic())
    original_4k = multi_instance_app.state.settings.radarr["4K"]

    headers = {"HX-Request": hx_header} if hx_header else {}
    with (
        TestClient(multi_instance_app, raise_server_exceptions=False) as tc,
        patch(
            "triggarr.web.routes._atomic_toml_write",
            side_effect=TypeError("cannot serialize SENTINEL-DETAIL-5d1e at /secret/path/triggarr.toml"),
        ),
    ):
        response = tc.post(
            "/api/instance/remove/radarr/4K",
            headers=headers,
            follow_redirects=False,
        )

    assert response.status_code == expected_status
    assert "HX-Redirect" not in response.headers
    assert "Location" not in response.headers
    assert response.text == (
        "'4K' was not removed: the settings file could not be saved. "
        "Nothing was changed. Check the Triggarr log for details."
    )
    assert "TypeError" not in response.text
    assert "SENTINEL-DETAIL-5d1e" not in response.text
    assert "Traceback" not in response.text

    assert multi_instance_app.state.settings.radarr["4K"] is original_4k
    multi_instance_app.state.scheduler.remove_job.assert_not_called()
    assert "4K" in multi_instance_app.state.radarr_clients
    multi_instance_app.state.radarr_clients["4K"].close.assert_not_awaited()
    assert "4K" in multi_instance_app.state.triggarr_state["radarr"]
    assert ("radarr", "4K") in multi_instance_app.state.tag_cache


def test_remove_instance_unexpected_real_write_error_logs_one_error(multi_instance_app):
    """A non-OSError failure inside the real writer yields exactly one
    error-level entry overall (D-07), logged by the route and naming the app,
    the instance and the system reason. The writer's own unexpected-error
    line is suppressed for this caller and no separate warning line carries
    the context (iteration 2 WR-01 / SA-01).
    """
    config_path = multi_instance_app.state.config_path
    pre_existing = b"placeholder"
    config_path.write_bytes(pre_existing)

    records: list = []
    handler_id = logger.add(lambda m: records.append(m.record), level="WARNING")
    try:
        with (
            TestClient(multi_instance_app, raise_server_exceptions=False) as tc,
            patch(
                "triggarr.config.tomli_w.dump",
                side_effect=TypeError("Object of type 'object' is not TOML serializable"),
            ),
        ):
            response = tc.post(
                "/api/instance/remove/radarr/4K",
                headers={"HX-Request": "true"},
                follow_redirects=False,
            )
    finally:
        logger.remove(handler_id)

    assert response.status_code == 200
    assert response.text.startswith("'4K' was not removed")

    errors = [r for r in records if r["level"].name == "ERROR"]
    assert len(errors) == 1
    message = errors[0]["message"]
    assert "radarr" in message
    assert "4K" in message
    assert "not TOML serializable" in message
    assert not any("Config write failed" in r["message"] for r in records)

    # The whole failure is that one entry: no adjacent warning line.
    assert [r["message"] for r in records if r["level"].name == "WARNING"] == []

    assert "4K" in multi_instance_app.state.settings.radarr
    assert list(config_path.parent.glob("*.tmp")) == []
    assert config_path.read_bytes() == pre_existing


@pytest.mark.parametrize(
    ("hx_header", "expected_status"),
    [(None, 500), ("true", 200)],
    ids=["plain", "htmx"],
)
async def test_remove_instance_write_never_starts_logs_one_error(multi_instance_app, hx_header, expected_status):
    """When the settings write never starts (run_in_executor itself raises,
    e.g. the host thread limit is reached), the removal still fails cleanly:
    exactly one error-level entry naming the app, the instance and the
    reason, the fixed D-05 response, and live state untouched (iteration 2
    WR-01).
    """
    original_4k = multi_instance_app.state.settings.radarr["4K"]
    headers = {"HX-Request": hx_header} if hx_header else {}

    records: list = []
    handler_id = logger.add(lambda m: records.append(m.record), level="WARNING")
    try:
        with (
            patch.object(
                asyncio.get_running_loop(),
                "run_in_executor",
                side_effect=RuntimeError("can't start new thread"),
            ),
            patch("triggarr.web.routes._atomic_toml_write") as writer,
        ):
            async with httpx.AsyncClient(
                transport=ASGITransport(app=multi_instance_app), base_url="http://test"
            ) as ac:
                response = await ac.post("/api/instance/remove/radarr/4K", headers=headers)
    finally:
        logger.remove(handler_id)

    writer.assert_not_called()

    assert response.status_code == expected_status
    assert "HX-Redirect" not in response.headers
    assert "Location" not in response.headers
    assert response.text == (
        "'4K' was not removed: the settings file could not be saved. "
        "Nothing was changed. Check the Triggarr log for details."
    )
    assert "RuntimeError" not in response.text
    assert "new thread" not in response.text

    errors = [r for r in records if r["level"].name == "ERROR"]
    assert len(errors) == 1
    message = errors[0]["message"]
    assert "radarr" in message
    assert "4K" in message
    assert "can't start new thread" in message
    # Nothing points at a log entry that does not exist.
    assert [r["message"] for r in records if r["level"].name == "WARNING"] == []

    assert multi_instance_app.state.settings.radarr["4K"] is original_4k
    multi_instance_app.state.scheduler.remove_job.assert_not_called()
    assert "4K" in multi_instance_app.state.radarr_clients
    multi_instance_app.state.radarr_clients["4K"].close.assert_not_awaited()
    assert "4K" in multi_instance_app.state.triggarr_state["radarr"]


@pytest.mark.parametrize(
    ("hx_header", "expected_status"),
    [(None, 500), ("true", 200)],
    ids=["plain", "htmx"],
)
async def test_remove_instance_refused_thread_start_does_not_write_later(
    multi_instance_app, hx_header, expected_status
):
    """When the operating system refuses the thread for the settings write,
    the thread pool has already queued the write. The removal answers "not
    removed", so that queued write must never run: after a later, successful
    use of the same executor the settings file still contains the instance
    (iteration 3 WR-01).

    Nothing is mocked above the thread-start level: the real loop, a real
    default executor and the real writer are used, and exactly one real
    thread start is refused.
    """
    app = multi_instance_app
    config_path = app.state.config_path
    _atomic_toml_write(config_path, _settings_to_dict(app.state.settings))
    on_disk_before = config_path.read_bytes()
    assert "4K" in tomllib.loads(on_disk_before.decode())["radarr"]
    original_4k = app.state.settings.radarr["4K"]

    # A fresh default executor has no idle worker, so the removal's write
    # must start a thread.
    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=2, thread_name_prefix="wr01-refused"))

    real_start = threading.Thread.start
    refused: list[str] = []

    def start_refusing_one(self):
        if self.name.startswith("wr01-refused") and not refused:
            refused.append(self.name)
            raise RuntimeError("can't start new thread")
        return real_start(self)

    headers = {"HX-Request": hx_header} if hx_header else {}
    records: list = []
    handler_id = logger.add(lambda m: records.append(m.record), level="DEBUG")
    try:
        with patch.object(threading.Thread, "start", start_refusing_one):
            async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post("/api/instance/remove/radarr/4K", headers=headers)

            assert len(refused) == 1
            # A later use of the same executor succeeds. Its worker thread
            # takes jobs in the order they were queued, so anything the
            # failed removal left behind has run by the time this returns.
            await loop.run_in_executor(None, lambda: None)
            assert len(refused) == 1
    finally:
        logger.remove(handler_id)

    assert response.status_code == expected_status
    assert "HX-Redirect" not in response.headers
    assert "Location" not in response.headers
    assert response.text == (
        "'4K' was not removed: the settings file could not be saved. "
        "Nothing was changed. Check the Triggarr log for details."
    )

    # The settings file still has the instance, byte for byte.
    assert config_path.read_bytes() == on_disk_before
    assert "4K" in tomllib.loads(config_path.read_text())["radarr"]
    assert list(config_path.parent.glob("*.tmp")) == []

    # So does the running app.
    assert app.state.settings.radarr["4K"] is original_4k
    app.state.scheduler.remove_job.assert_not_called()
    assert "4K" in app.state.radarr_clients
    app.state.radarr_clients["4K"].close.assert_not_awaited()
    assert "4K" in app.state.triggarr_state["radarr"]

    # One error entry saying the instance was kept; nothing says it was removed.
    notable = [r for r in records if r["level"].no >= logger.level("WARNING").no]
    assert len(notable) == 1
    assert notable[0]["level"].name == "ERROR"
    message = notable[0]["message"]
    assert "radarr" in message
    assert "4K" in message
    assert "instance kept" in message
    assert "can't start new thread" in message
    assert not any("Removed" in r["message"] for r in records)


async def test_remove_instance_refused_thread_start_with_write_already_running_reports_the_write(
    multi_instance_app,
):
    """The thread start is refused, but a worker that was busy at that moment
    has already picked the queued write up and is in the middle of it. The
    write cannot be called off any more, so the route must not answer "not
    removed": it waits for the write (without blocking the event loop) and
    reports what the write actually did. Here the write succeeds, so the
    removal succeeds and the file and the running app agree (iteration 3
    WR-01, the window the abandoned flag alone leaves open).
    """
    app = multi_instance_app
    config_path = app.state.config_path
    _atomic_toml_write(config_path, _settings_to_dict(app.state.settings))

    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=2, thread_name_prefix="wr01-running"))

    release_busy_worker = threading.Event()
    write_started = threading.Event()
    let_write_finish = threading.Event()

    # One worker is busy, so the removal's write is queued behind it and the
    # pool tries to start a second thread.
    busy = loop.run_in_executor(None, release_busy_worker.wait, 10)

    def slow_writer(*args, **kwargs):
        write_started.set()
        assert let_write_finish.wait(10)
        return _atomic_toml_write(*args, **kwargs)

    real_start = threading.Thread.start
    refused: list[str] = []

    def start_refusing_after_job_is_taken(self):
        if armed and self.name.startswith("wr01-running") and not refused:
            refused.append(self.name)
            # The busy worker frees up and takes the queued write before the
            # refusal reaches the route.
            release_busy_worker.set()
            assert write_started.wait(10)
            raise RuntimeError("can't start new thread")
        return real_start(self)

    armed = False
    records: list = []
    handler_id = logger.add(lambda m: records.append(m.record), level="WARNING")
    try:
        with (
            patch.object(threading.Thread, "start", start_refusing_after_job_is_taken),
            patch("triggarr.web.routes._atomic_toml_write", side_effect=slow_writer),
        ):
            armed = True
            async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                request_task = asyncio.create_task(ac.post("/api/instance/remove/radarr/4K"))
                try:
                    # The write is still running: no answer yet, and the event
                    # loop keeps turning (these sleeps return).
                    for _ in range(20):
                        await asyncio.sleep(0.005)
                    assert len(refused) == 1
                    assert not request_task.done()
                    assert "4K" in app.state.settings.radarr
                finally:
                    let_write_finish.set()
                response = await request_task
            await busy
    finally:
        release_busy_worker.set()
        let_write_finish.set()
        logger.remove(handler_id)

    # The write went through, so the removal is real and reported as such.
    assert response.status_code == 303
    assert "4K" not in tomllib.loads(config_path.read_text())["radarr"]
    assert "4K" not in app.state.settings.radarr
    assert "4K" not in app.state.radarr_clients
    assert "4K" not in app.state.triggarr_state["radarr"]

    # Not a failed removal: no error entry. The refused thread start is still
    # on record, as one warning naming the app and the instance.
    assert [r["message"] for r in records if r["level"].name == "ERROR"] == []
    warnings = [r["message"] for r in records if r["level"].name == "WARNING"]
    assert len(warnings) == 1
    assert "radarr" in warnings[0]
    assert "4K" in warnings[0]
    assert "can't start new thread" in warnings[0]


def test_remove_instance_settings_build_failure_logs_one_error(multi_instance_app):
    """A failure while building the post-removal settings data (before the
    writer runs) is also a failed removal: one error-level entry naming the
    app, the instance and the reason, and the fixed D-05 response (WR-02a).
    """
    records: list = []
    handler_id = logger.add(lambda m: records.append(m.record), level="ERROR")
    try:
        with (
            TestClient(multi_instance_app, raise_server_exceptions=False) as tc,
            patch("triggarr.web.routes._settings_to_dict", side_effect=ValueError("bad settings shape")),
            patch("triggarr.web.routes._atomic_toml_write") as writer,
        ):
            response = tc.post(
                "/api/instance/remove/radarr/4K",
                headers={"HX-Request": "true"},
                follow_redirects=False,
            )
    finally:
        logger.remove(handler_id)

    assert response.status_code == 200
    assert response.text.startswith("'4K' was not removed")
    assert "bad settings shape" not in response.text
    writer.assert_not_called()

    assert len(records) == 1
    message = records[0]["message"]
    assert "radarr" in message
    assert "4K" in message
    assert "bad settings shape" in message
    assert "4K" in multi_instance_app.state.settings.radarr


def test_remove_instance_not_found_htmx_redirects_like_success(multi_instance_app):
    """An htmx removal of an instance that no longer exists (already removed in
    another tab) answers like a successful removal -- empty 200 + HX-Redirect to
    the settings page -- so the stale row disappears (WR-02b).
    """
    with TestClient(multi_instance_app) as tc:
        response = tc.post(
            "/api/instance/remove/radarr/%3Cb%3E%26gone",
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert response.headers.get("HX-Redirect", "").endswith("/settings")
    assert response.text == ""
    assert set(multi_instance_app.state.settings.radarr) == {"Default", "4K"}
    multi_instance_app.state.scheduler.remove_job.assert_not_called()


def test_remove_instance_not_found_plain_keeps_400_and_escapes_name(multi_instance_app):
    """A direct, non-htmx removal of a missing instance keeps the 400 with the
    escaped instance name (WR-02b leaves the plain path unchanged).
    """
    with TestClient(multi_instance_app) as tc:
        response = tc.post(
            "/api/instance/remove/radarr/%3Cb%3E%26gone",
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert "HX-Redirect" not in response.headers
    assert response.text == "Instance '&lt;b&gt;&amp;gone' not found"


async def test_remove_instance_concurrent_same_instance_htmx_second_redirects(multi_instance_app):
    """Two concurrent htmx removals of the same instance: both answer with the
    success redirect, the instance is removed once and its client is closed
    exactly once (WR-02b).
    """
    client_4k = multi_instance_app.state.radarr_clients["4K"]
    lock = multi_instance_app.state.search_lock
    await lock.acquire()

    async with httpx.AsyncClient(
        transport=ASGITransport(app=multi_instance_app), base_url="http://test"
    ) as ac:
        hx = {"HX-Request": "true"}
        task_a = asyncio.create_task(ac.post("/api/instance/remove/radarr/4K", headers=hx))
        task_b = asyncio.create_task(ac.post("/api/instance/remove/radarr/4K", headers=hx))

        for _ in range(200):
            if len(getattr(lock, "_waiters", None) or ()) == 2:
                break
            await asyncio.sleep(0)
        assert len(getattr(lock, "_waiters", None) or ()) == 2, (
            "both removal requests must be queued on search_lock before it is released"
        )

        lock.release()
        response_a, response_b = await asyncio.gather(task_a, task_b)

    for response in (response_a, response_b):
        assert response.status_code == 200
        assert response.headers.get("HX-Redirect", "").endswith("/settings")
        assert response.text == ""
    assert "4K" not in multi_instance_app.state.settings.radarr
    assert client_4k.close.await_count == 1


def test_settings_clears_row_error_slot_when_remove_request_starts(multi_client):
    """The page's nonce'd script empties a row's error slot when a new Remove
    request starts, so an old failure message cannot outlive a later attempt
    whose response htmx does not swap (WR-02c). No inline handler is used.
    """
    response = multi_client.get("/settings")
    assert response.status_code == 200
    html = response.text

    script = re.search(r'<script nonce="[^"]*">(.*?)</script>', html[html.find('class="remove-error') :], re.DOTALL)
    assert script is not None
    body = script.group(1)
    assert "htmx:beforeRequest" in body
    assert ".remove-error" in body
    assert "textContent = ''" in body

    # CSP nonce discipline: the instance rows carry no inline event handlers.
    summary_blocks = re.findall(r"<summary\b.*?</summary>", html, re.DOTALL)
    assert summary_blocks
    for block in summary_blocks:
        assert "hx-on" not in block
        assert not re.search(r"\son[a-z]+\s*=", block)


def test_remove_instance_scheduler_failure_still_completes(multi_instance_app):
    """Once the settings file is saved, a scheduler.remove_job failure does
    not stop the removal from completing: the user still sees the normal
    success response and every other tidy-up step still runs (D-15, D-16).
    """
    client_4k = multi_instance_app.state.radarr_clients["4K"]
    multi_instance_app.state.scheduler.remove_job.side_effect = RuntimeError("job gone")

    records: list = []
    handler_id = logger.add(lambda m: records.append(m.record), level="ERROR")
    try:
        with (
            TestClient(multi_instance_app, raise_server_exceptions=False) as tc,
            patch("triggarr.web.routes._atomic_toml_write", return_value=None),
        ):
            response = tc.post(
                "/api/instance/remove/radarr/4K",
                headers={"HX-Request": "true"},
                follow_redirects=False,
            )
    finally:
        logger.remove(handler_id)

    assert response.status_code == 200
    assert response.headers.get("HX-Redirect", "").endswith("/settings")
    assert "4K" not in multi_instance_app.state.settings.radarr
    assert "4K" not in multi_instance_app.state.radarr_clients
    assert client_4k.close.await_count == 1
    assert "4K" not in multi_instance_app.state.triggarr_state["radarr"]
    assert ("radarr", "4K") not in multi_instance_app.state.tag_cache

    assert len(records) == 1
    message = records[0]["message"]
    assert "radarr" in message
    assert "4K" in message
    assert "job gone" in message


def test_remove_instance_close_failure_still_succeeds(multi_instance_app):
    """Once the settings file is saved, a client.close() failure does not
    stop the removal from completing: the user still sees the normal
    success response and the removal is otherwise complete (D-15, D-16).
    """
    multi_instance_app.state.radarr_clients["4K"].close = AsyncMock(side_effect=RuntimeError("close boom"))

    records: list = []
    handler_id = logger.add(lambda m: records.append(m.record), level="ERROR")
    try:
        with (
            TestClient(multi_instance_app, raise_server_exceptions=False) as tc,
            patch("triggarr.web.routes._atomic_toml_write", return_value=None),
        ):
            response = tc.post(
                "/api/instance/remove/radarr/4K",
                follow_redirects=False,
            )
    finally:
        logger.remove(handler_id)

    assert response.status_code == 303
    assert response.headers.get("location", "").endswith("/settings")
    assert "4K" not in multi_instance_app.state.settings.radarr
    assert "4K" not in multi_instance_app.state.radarr_clients
    assert "4K" not in multi_instance_app.state.triggarr_state["radarr"]
    assert ("radarr", "4K") not in multi_instance_app.state.tag_cache

    assert len(records) == 1
    message = records[0]["message"]
    assert "radarr" in message
    assert "4K" in message
    assert "close boom" in message


def test_settings_remove_button_targets_row_error_slot(multi_client, multi_instance_app):
    """Each instance's Remove button targets a row-local error slot instead of
    the page body, so a failed removal can show its message on that row
    without a reload (D-04, D-06).
    """
    response = multi_client.get("/settings")
    assert response.status_code == 200
    html = response.text

    settings = multi_instance_app.state.settings
    expected_count = sum(len(getattr(settings, app)) for app in APP_TYPES)

    # Every instance row's Remove button is retargeted off body/outerHTML.
    assert html.count('hx-target="next .remove-error"') == expected_count
    assert html.count('hx-target="body"') == 0

    # Every instance row has exactly one row-local error slot, empty on load.
    assert html.count('class="remove-error') == expected_count
    assert re.findall(r'<span class="remove-error[^"]*"[^>]*></span>', html).__len__() == expected_count

    # Each slot appears after its Remove button and before the matching </summary>.
    summary_blocks = re.findall(r"<summary\b.*?</summary>", html, re.DOTALL)
    assert len(summary_blocks) == expected_count
    for block in summary_blocks:
        remove_idx = block.find('hx-target="next .remove-error"')
        slot_idx = block.find('class="remove-error')
        assert remove_idx != -1, f"Remove button retarget missing from row: {block}"
        assert slot_idx != -1, f"remove-error slot missing from row: {block}"
        assert remove_idx < slot_idx, "error slot must come after the Remove button"

    # IN-01: the slot sits inside <summary>, so it must opt out of the
    # click-to-toggle like the Remove button does; clicking or selecting the
    # message must not collapse the instance's <details>.
    slot_tags = re.findall(r'<span class="remove-error[^>]*>', html)
    assert len(slot_tags) == expected_count
    for tag in slot_tags:
        assert "data-stop-propagation" in tag
    # stopPropagation alone does not stop a <summary> from toggling when the
    # clicked element is not itself interactive (checked in headless Chrome), so
    # the page script must also cancel the click's default action for the slot.
    script = re.search(r'<script nonce="[^"]*">(.*?)</script>', html[html.find('class="remove-error') :], re.DOTALL)
    assert script is not None
    assert re.search(r"remove-error'\)\)\s*e\.preventDefault\(\)", script.group(1))


def test_no_new_body_swap_html_targets():
    """SEC-01 defense-in-depth: no template may use `hx-target="body"` or
    `hx-target="html"` any more. The settings.html Remove button now targets
    a row-local slot (Phase 87) instead of the page body. Any future addition
    of `hx-target="body"`/`"html"` must come with a paired HX-Redirect
    response or a non-script-bearing partial template, or it will silently
    break CSP-nonce inheritance on the swapped-in page.
    """
    from pathlib import Path
    matches: list[str] = []
    templates_dir = Path(__file__).resolve().parent.parent / "triggarr" / "templates"
    for path in templates_dir.rglob("*.html"):
        for line_num, line in enumerate(path.read_text().splitlines(), start=1):
            if 'hx-target="body"' in line or 'hx-target="html"' in line:
                matches.append(f"{path}:{line_num}")
    assert len(matches) == 0, (
        f"No template may use hx-target=body/html (SEC-01: a body swap inherits the old CSP "
        f"nonce); pair any new one with an HX-Redirect response or a non-script-bearing "
        f"partial. Found {len(matches)}: {matches}"
    )


def test_app_card_no_skip_when_equal(client, test_app):
    """App card does NOT show skip badge when missing_monitored == missing_eligible (DASH-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["missing_monitored"] = 42
    test_app.state.triggarr_state["radarr"]["Default"]["missing_eligible"] = 42
    test_app.state.triggarr_state["radarr"]["Default"]["missing_count"] = 50
    test_app.state.settings.general.skip_unreleased = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "skipped (unreleased)" not in response.text, "No skip badge when monitored == eligible"


def test_app_card_eligible_total_display(client, test_app):
    """App card shows missing_count as hero number in recessed sub-card."""
    test_app.state.triggarr_state["radarr"]["Default"]["missing_count"] = 50
    test_app.state.triggarr_state["radarr"]["Default"]["total_items"] = 1500
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert ">50<" in response.text.replace(" ", "").replace("\n", ""), "Missing count should render as hero number"


def test_app_card_sonarr_no_skip_badge(client, test_app):
    """Sonarr card does NOT show skip badge even when eligible < total (DASH-02)."""
    test_app.state.triggarr_state["sonarr"]["Default"]["missing_eligible"] = 5
    test_app.state.triggarr_state["sonarr"]["Default"]["missing_count"] = 10
    test_app.state.settings.general.skip_unreleased = True
    response = client.get("/partials/app-card/sonarr/Default")
    assert response.status_code == 200
    assert "skipped (unreleased)" not in response.text, "Sonarr should not show skip badge"


# ---------------------------------------------------------------------------
# BUG-07 / BUG-11: Input validation (instance_filter cap, instance_name length)
# ---------------------------------------------------------------------------


async def test_history_results_caps_instance_filter_at_10(test_app):
    """GET /partials/history-results caps instance_filter to 10 items max (BUG-07)."""
    db = test_app.state.db
    # Insert entries for 12 different instances
    for i in range(12):
        await insert_search_entry(db, "Radarr", "missing", f"Movie {i}", instance_id=f"Inst{i}")

    # Request with 12 instance filters -- only first 10 should be used
    filter_param = ",".join(f"Inst{i}" for i in range(12))
    with TestClient(test_app) as tc:
        response = tc.get(f"/partials/history-results?instance={filter_param}")
    assert response.status_code == 200
    # Inst10 and Inst11 should NOT be in the results (capped at 10)
    assert "Movie 10" not in response.text, "Instance filter should be capped at 10"
    assert "Movie 11" not in response.text, "Instance filter should be capped at 10"


def test_search_now_rejects_long_instance_name(client):
    """POST /api/search-now with instance_name > 64 chars returns 400 (BUG-11)."""
    long_name = "A" * 65
    response = client.post(f"/api/search-now/radarr/{long_name}")
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    assert "Instance name too long" in response.text


def test_app_card_rejects_long_instance_name(client):
    """GET /partials/app-card with instance_name > 64 chars returns 400 (BUG-11)."""
    long_name = "A" * 65
    response = client.get(f"/partials/app-card/radarr/{long_name}")
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    assert "Instance name too long" in response.text


def test_search_now_accepts_valid_length_instance_name(client, test_app):
    """POST /api/search-now with instance_name <= 64 chars proceeds normally (BUG-11)."""
    valid_name = "A" * 64
    # The instance won't be found in enabled instances, so we expect 400 "Instance not enabled"
    # but NOT "Instance name too long"
    response = client.post(f"/api/search-now/radarr/{valid_name}")
    assert response.status_code == 400
    assert "Instance not enabled" in response.text
    assert "Instance name too long" not in response.text


# ---------------------------------------------------------------------------
# BUG-05: Settings save must preserve all instances, not just the first
# ---------------------------------------------------------------------------


def test_save_settings_preserves_non_edited_instances(test_app, tmp_path):
    """POST /settings with 2 radarr instances preserves both in written config (BUG-05)."""
    # Configure 2 radarr instances: Default (first) and 4K
    test_app.state.settings = Settings(
        general=GeneralConfig(skip_unreleased=True, tracking_delay_seconds=90),
        radarr={
            "Default": InstanceConfig(
                url="http://radarr:7878", api_key="default-key", enabled=True,
                search_interval=30, search_missing_count=5, search_cutoff_count=5,
            ),
            "4K": InstanceConfig(
                url="http://radarr4k:7878", api_key="4k-key", enabled=True,
                search_interval=60, search_missing_count=10, search_cutoff_count=3,
            ),
        },
        sonarr={
            "Default": InstanceConfig(
                url="http://sonarr:8989", api_key="sonarr-key", enabled=True,
            ),
        },
    )
    # Need matching clients for scheduler update logic
    radarr_default_client = MagicMock()
    radarr_default_client.close = AsyncMock()
    radarr_4k_client = MagicMock()
    radarr_4k_client.close = AsyncMock()
    test_app.state.radarr_clients = {"Default": radarr_default_client, "4K": radarr_4k_client}

    with TestClient(test_app) as tc:
        response = tc.post(
            "/settings",
            data={
                "log_level": "info",
                "hard_max_per_cycle": "0",
                "max_history_rows": "1000",
                "request_timeout": "30",
                "page_size": "50",
                "tracking_window_minutes": "60",
                "skip_unreleased": "on",
                "radarr__Default__url": "http://radarr:7878",
                "radarr__Default__api_key": "",  # keep existing
                "radarr__Default__enabled": "on",
                "radarr__Default__search_interval": "30",
                "radarr__Default__search_missing_count": "5",
                "radarr__Default__search_cutoff_count": "5",
                "radarr__Default__missing_tag": "",
                "radarr__Default__cutoff_tag": "",
                "radarr__4K__url": "http://radarr4k:7878",
                "radarr__4K__api_key": "",
                "radarr__4K__enabled": "on",
                "radarr__4K__search_interval": "60",
                "radarr__4K__search_missing_count": "10",
                "radarr__4K__search_cutoff_count": "3",
                "radarr__4K__missing_tag": "",
                "radarr__4K__cutoff_tag": "",
                "sonarr__Default__url": "http://sonarr:8989",
                "sonarr__Default__api_key": "",
                "sonarr__Default__enabled": "on",
                "sonarr__Default__search_interval": "30",
                "sonarr__Default__search_missing_count": "5",
                "sonarr__Default__search_cutoff_count": "5",
                "sonarr__Default__missing_tag": "",
                "sonarr__Default__cutoff_tag": "",
            },
            follow_redirects=False,
        )
    assert response.status_code == 303

    import tomllib
    with open(test_app.state.config_path, "rb") as f:
        written = tomllib.load(f)

    # Both radarr instances must be preserved
    assert "Default" in written["radarr"], "Default radarr instance should be preserved"
    assert "4K" in written["radarr"], "4K radarr instance should be preserved"
    # 4K instance should retain its submitted settings
    assert written["radarr"]["4K"]["url"] == "http://radarr4k:7878"
    assert written["radarr"]["4K"]["api_key"] == "4k-key"
    assert written["radarr"]["4K"]["search_interval"] == 60
    assert written["radarr"]["4K"]["search_missing_count"] == 10
    assert written["radarr"]["4K"]["search_cutoff_count"] == 3


def test_save_settings_preserves_tag_fields(test_app, tmp_path):
    """POST /settings preserves missing_tag and cutoff_tag on non-edited instances (BUG-05)."""
    test_app.state.settings = Settings(
        general=GeneralConfig(skip_unreleased=True, tracking_delay_seconds=90),
        radarr={
            "Default": InstanceConfig(
                url="http://radarr:7878", api_key="default-key", enabled=True,
                missing_tag="triggarr", cutoff_tag="upgrade",
            ),
            "4K": InstanceConfig(
                url="http://radarr4k:7878", api_key="4k-key", enabled=True,
                missing_tag="4k-tag", cutoff_tag="4k-upgrade",
            ),
        },
        sonarr={"Default": InstanceConfig(url="http://sonarr:8989", api_key="sonarr-key", enabled=True)},
    )
    radarr_default_client = MagicMock()
    radarr_default_client.close = AsyncMock()
    radarr_4k_client = MagicMock()
    radarr_4k_client.close = AsyncMock()
    test_app.state.radarr_clients = {"Default": radarr_default_client, "4K": radarr_4k_client}

    with TestClient(test_app) as tc:
        response = tc.post(
            "/settings",
            data={
                "log_level": "info",
                "radarr__Default__url": "http://radarr:7878",
                "radarr__Default__api_key": "",
                "radarr__Default__enabled": "on",
                "radarr__Default__search_interval": "30",
                "radarr__Default__search_missing_count": "5",
                "radarr__Default__search_cutoff_count": "5",
                "radarr__Default__missing_tag": "triggarr",
                "radarr__Default__cutoff_tag": "upgrade",
                "radarr__4K__url": "http://radarr4k:7878",
                "radarr__4K__api_key": "",
                "radarr__4K__enabled": "on",
                "radarr__4K__search_interval": "30",
                "radarr__4K__search_missing_count": "5",
                "radarr__4K__search_cutoff_count": "5",
                "radarr__4K__missing_tag": "4k-tag",
                "radarr__4K__cutoff_tag": "4k-upgrade",
                "sonarr__Default__url": "http://sonarr:8989",
                "sonarr__Default__api_key": "",
                "sonarr__Default__enabled": "on",
                "sonarr__Default__search_interval": "30",
                "sonarr__Default__search_missing_count": "5",
                "sonarr__Default__search_cutoff_count": "5",
                "sonarr__Default__missing_tag": "",
                "sonarr__Default__cutoff_tag": "",
            },
            follow_redirects=False,
        )
    assert response.status_code == 303

    import tomllib
    with open(test_app.state.config_path, "rb") as f:
        written = tomllib.load(f)

    # Tag fields should be preserved from form submission
    assert written["radarr"]["4K"]["missing_tag"] == "4k-tag"
    assert written["radarr"]["4K"]["cutoff_tag"] == "4k-upgrade"
    assert written["radarr"]["Default"]["missing_tag"] == "triggarr"
    assert written["radarr"]["Default"]["cutoff_tag"] == "upgrade"


def test_save_settings_preserves_id_with_instance_fields(test_app, tmp_path):
    """POST /settings with {app}__{inst}__* fields for every instance keeps each id (ATTR-03)."""
    radarr_id = "a" * 32
    sonarr_id = "b" * 32
    test_app.state.settings = Settings(
        general=GeneralConfig(skip_unreleased=True, tracking_delay_seconds=90),
        radarr={
            "Default": InstanceConfig(
                url="http://radarr:7878", api_key="default-key", enabled=True, id=radarr_id,
            ),
        },
        sonarr={
            "Default": InstanceConfig(
                url="http://sonarr:8989", api_key="sonarr-key", enabled=True, id=sonarr_id,
            ),
        },
    )
    radarr_default_client = MagicMock()
    radarr_default_client.close = AsyncMock()
    test_app.state.radarr_clients = {"Default": radarr_default_client}

    with TestClient(test_app) as tc:
        response = tc.post(
            "/settings",
            data={
                "log_level": "info",
                "radarr__Default__url": "http://radarr:7878",
                "radarr__Default__api_key": "",
                "radarr__Default__enabled": "on",
                "radarr__Default__search_interval": "30",
                "radarr__Default__search_missing_count": "5",
                "radarr__Default__search_cutoff_count": "5",
                "radarr__Default__missing_tag": "",
                "radarr__Default__cutoff_tag": "",
                "sonarr__Default__url": "http://sonarr:8989",
                "sonarr__Default__api_key": "",
                "sonarr__Default__enabled": "on",
                "sonarr__Default__search_interval": "30",
                "sonarr__Default__search_missing_count": "5",
                "sonarr__Default__search_cutoff_count": "5",
                "sonarr__Default__missing_tag": "",
                "sonarr__Default__cutoff_tag": "",
            },
            follow_redirects=False,
        )
    assert response.status_code == 303

    import tomllib
    with open(test_app.state.config_path, "rb") as f:
        written = tomllib.load(f)

    assert written["radarr"]["Default"]["id"] == radarr_id
    assert written["sonarr"]["Default"]["id"] == sonarr_id
    assert test_app.state.settings.radarr["Default"].id == radarr_id
    assert test_app.state.settings.sonarr["Default"].id == sonarr_id


def test_save_settings_preserves_id_without_instance_fields(test_app, tmp_path):
    """POST /settings with only general fields (preserve branch) keeps every id unchanged (ATTR-03)."""
    radarr_id = "a" * 32
    sonarr_id = "b" * 32
    test_app.state.settings = Settings(
        general=GeneralConfig(skip_unreleased=True, tracking_delay_seconds=90),
        radarr={
            "Default": InstanceConfig(
                url="http://radarr:7878", api_key="default-key", enabled=True, id=radarr_id,
            ),
        },
        sonarr={
            "Default": InstanceConfig(
                url="http://sonarr:8989", api_key="sonarr-key", enabled=True, id=sonarr_id,
            ),
        },
    )
    radarr_default_client = MagicMock()
    radarr_default_client.close = AsyncMock()
    test_app.state.radarr_clients = {"Default": radarr_default_client}

    with TestClient(test_app) as tc:
        response = tc.post(
            "/settings",
            data={"log_level": "info"},
            follow_redirects=False,
        )
    assert response.status_code == 303

    import tomllib
    with open(test_app.state.config_path, "rb") as f:
        written = tomllib.load(f)

    assert written["radarr"]["Default"]["id"] == radarr_id
    assert written["sonarr"]["Default"]["id"] == sonarr_id
    assert test_app.state.settings.radarr["Default"].id == radarr_id
    assert test_app.state.settings.sonarr["Default"].id == sonarr_id


def test_save_settings_new_form_instance_gets_id(test_app, tmp_path):
    """A sonarr instance name submitted via form but absent from current settings gets a fresh id (ATTR-03)."""
    sonarr_id = "b" * 32
    test_app.state.settings = Settings(
        general=GeneralConfig(skip_unreleased=True, tracking_delay_seconds=90),
        radarr={},
        sonarr={
            "Default": InstanceConfig(
                url="http://sonarr:8989", api_key="sonarr-key", enabled=True, id=sonarr_id,
            ),
        },
    )
    test_app.state.radarr_clients = {}

    with TestClient(test_app) as tc:
        response = tc.post(
            "/settings",
            data={
                "log_level": "info",
                "sonarr__Default__url": "http://sonarr:8989",
                "sonarr__Default__api_key": "",
                "sonarr__Default__enabled": "on",
                "sonarr__Default__search_interval": "30",
                "sonarr__Default__search_missing_count": "5",
                "sonarr__Default__search_cutoff_count": "5",
                "sonarr__Default__missing_tag": "",
                "sonarr__Default__cutoff_tag": "",
                "sonarr__NewOne__url": "http://sonarr-new:8989",
                "sonarr__NewOne__api_key": "new-key",
                "sonarr__NewOne__enabled": "on",
                "sonarr__NewOne__search_interval": "30",
                "sonarr__NewOne__search_missing_count": "5",
                "sonarr__NewOne__search_cutoff_count": "5",
                "sonarr__NewOne__missing_tag": "",
                "sonarr__NewOne__cutoff_tag": "",
            },
            follow_redirects=False,
        )
    assert response.status_code == 303

    import tomllib
    with open(test_app.state.config_path, "rb") as f:
        written = tomllib.load(f)

    assert written["sonarr"]["Default"]["id"] == sonarr_id
    new_id = written["sonarr"]["NewOne"]["id"]
    assert re.fullmatch(r"[0-9a-f]{32}", new_id)
    assert new_id != sonarr_id
    assert test_app.state.settings.sonarr["NewOne"].id == new_id


def test_save_settings_uses_atomic_toml_write(test_app, tmp_path):
    """POST /settings writes config using _atomic_toml_write, not manual tempfile (BUG-05 dedup)."""
    with TestClient(test_app) as tc, \
         patch("triggarr.web.routes._atomic_toml_write") as mock_write, \
         patch("triggarr.web.routes.os.chmod"):
        tc.post(
            "/settings",
            data={
                "log_level": "info",
                "radarr__Default__url": "http://radarr:7878",
                "radarr__Default__api_key": "test-key",
                "radarr__Default__enabled": "on",
                "radarr__Default__search_interval": "30",
                "radarr__Default__search_missing_count": "5",
                "radarr__Default__search_cutoff_count": "5",
                "radarr__Default__missing_tag": "",
                "radarr__Default__cutoff_tag": "",
                "sonarr__Default__url": "",
                "sonarr__Default__api_key": "",
                "sonarr__Default__search_interval": "30",
                "sonarr__Default__search_missing_count": "5",
                "sonarr__Default__search_cutoff_count": "5",
                "sonarr__Default__missing_tag": "",
                "sonarr__Default__cutoff_tag": "",
            },
            follow_redirects=False,
        )
    mock_write.assert_called_once()
    call_args = mock_write.call_args
    assert call_args[0][0] == test_app.state.config_path


def test_save_settings_skip_unreleased_off(client, test_app):
    """POST /settings WITHOUT skip_unreleased in form data saves False."""
    response = client.post(
        "/settings",
        data={
            "log_level": "info",
            "hard_max_per_cycle": "0",
            "max_history_rows": "1000",
            "request_timeout": "30",
            "page_size": "50",
            "tracking_window_minutes": "60",
            # NOTE: skip_unreleased deliberately omitted (unchecked checkbox)
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "",
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "30",
            "radarr__Default__search_missing_count": "5",
            "radarr__Default__search_cutoff_count": "5",
            "radarr__Default__missing_tag": "",
            "radarr__Default__cutoff_tag": "",
            "sonarr__Default__url": "http://sonarr:8989",
            "sonarr__Default__api_key": "",
            "sonarr__Default__enabled": "on",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    content = test_app.state.config_path.read_text()
    assert "skip_unreleased = false" in content, "TOML should contain skip_unreleased = false"


# ---------------------------------------------------------------------------
# BUG-03: save_settings missing state entry for runtime-added instances
# ---------------------------------------------------------------------------


def test_save_settings_creates_state_for_new_instance(client, test_app, tmp_path):
    """After save_settings adds a new enabled instance, state contains default entry (BUG-03)."""
    # Start with NO state entries for radarr
    test_app.state.triggarr_state = {"radarr": {}, "sonarr": {}, "search_log": []}

    response = client.post(
        "/settings",
        data={
            "log_level": "info",
            "hard_max_per_cycle": "0",
            "max_history_rows": "1000",
            "request_timeout": "30",
            "page_size": "50",
            "tracking_window_minutes": "60",
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "test-key",
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "30",
            "radarr__Default__search_missing_count": "5",
            "radarr__Default__search_cutoff_count": "5",
            "radarr__Default__missing_tag": "",
            "radarr__Default__cutoff_tag": "",
            "sonarr__Default__url": "http://sonarr:8989",
            "sonarr__Default__api_key": "test-key",
            "sonarr__Default__enabled": "on",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    # State should now have entries for the enabled instances
    state = test_app.state.triggarr_state
    assert "Default" in state.get("radarr", {}), "State should have Default radarr entry after save_settings"
    # New instances carry empty searched-logs (cursor fields removed in v2.11)
    assert state["radarr"]["Default"]["missing_searched"] == []
    assert "Default" in state.get("sonarr", {}), "State should have Default sonarr entry after save_settings"


def test_save_settings_persists_state_to_disk(client, test_app, tmp_path):
    """After save_settings adds new instances, save_state is called to persist (BUG-03)."""
    test_app.state.triggarr_state = {"radarr": {}, "sonarr": {}, "search_log": []}

    with patch("triggarr.web.routes.save_state") as mock_save:
        response = client.post(
            "/settings",
            data={
                "log_level": "info",
                "hard_max_per_cycle": "0",
                "max_history_rows": "1000",
                "request_timeout": "30",
                "page_size": "50",
                "tracking_window_minutes": "60",
                "radarr__Default__url": "http://radarr:7878",
                "radarr__Default__api_key": "test-key",
                "radarr__Default__enabled": "on",
                "radarr__Default__search_interval": "30",
                "radarr__Default__search_missing_count": "5",
                "radarr__Default__search_cutoff_count": "5",
                "radarr__Default__missing_tag": "",
                "radarr__Default__cutoff_tag": "",
                "sonarr__Default__url": "http://sonarr:8989",
                "sonarr__Default__api_key": "test-key",
                "sonarr__Default__enabled": "on",
                "sonarr__Default__search_interval": "30",
                "sonarr__Default__search_missing_count": "5",
                "sonarr__Default__search_cutoff_count": "5",
                "sonarr__Default__missing_tag": "",
                "sonarr__Default__cutoff_tag": "",
            },
            follow_redirects=False,
        )
    assert response.status_code == 303
    # save_state should have been called to persist new state entries
    assert mock_save.called, "save_state should be called after adding new instance state entries"


# ---------------------------------------------------------------------------
# BUG-04: CSS selector injection via unsanitized card IDs
# ---------------------------------------------------------------------------


def test_sanitize_card_id_special_chars():
    """_sanitize_card_id replaces dots and hashes with hyphens (BUG-04)."""
    from triggarr.web.routes import _sanitize_card_id

    assert _sanitize_card_id("radarr-My.Instance#1") == "radarr-My-Instance-1"


def test_sanitize_card_id_safe_chars():
    """_sanitize_card_id leaves alphanumeric, hyphens, and underscores unchanged (BUG-04)."""
    from triggarr.web.routes import _sanitize_card_id

    assert _sanitize_card_id("radarr-Default") == "radarr-Default"


def test_build_app_context_uses_sanitized_card_id(client, test_app):
    """_build_app_context returns sanitized card_id for special-character instance names (BUG-04)."""
    # Add an instance with special characters in the name
    test_app.state.settings.radarr["My.4K#1"] = InstanceConfig(
        url="http://radarr4k:7878", api_key="key", enabled=True,
    )
    test_app.state.triggarr_state["radarr"]["My.4K#1"] = {"connected": True}

    # Test via partial endpoint (which calls _build_app_context internally)
    response = client.get("/partials/app-card/radarr/My.4K%231")
    # The card_id in the rendered HTML should be sanitized
    assert "radarr-My-4K-1" in response.text, "Card ID should be sanitized"
    assert "radarr-My.4K#1" not in response.text, "Unsanitized card ID should not appear"


# ---------------------------------------------------------------------------
# Phase 42: Health summary, stats instance filter, tag_warnings passthrough
# ---------------------------------------------------------------------------


def test_health_summary_counts(client, test_app):
    """GET /partials/health-summary returns HTML with connected/disconnected/pending counts."""
    # Radarr Default is connected=True, Sonarr/Lidarr Default is connected=None (pending)
    response = client.get("/partials/health-summary")
    assert response.status_code == 200
    # New strip format wraps count in <span class="font-semibold">N</span> label
    assert ">1</span> connected" in response.text
    assert ">2</span> pending" in response.text


def test_health_summary_excludes_disabled(client, test_app):
    """Health summary excludes disabled instances from count."""
    # Add a disabled instance
    test_app.state.settings.radarr["Disabled4K"] = InstanceConfig(
        url="http://radarr4k:7878", api_key="key", enabled=False,
    )
    test_app.state.triggarr_state["radarr"]["Disabled4K"] = {"connected": False}

    response = client.get("/partials/health-summary")
    assert response.status_code == 200
    # Disabled instance should not show in counts - still 1 connected, 0 disconnected
    assert ">1</span> connected" in response.text
    assert ">0</span> disconnected" in response.text


def test_health_summary_disconnected(client, test_app):
    """Health summary treats connected=False as disconnected."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    response = client.get("/partials/health-summary")
    assert response.status_code == 200
    assert ">1</span> disconnected" in response.text


def test_stats_row_instance_filter(client, test_app):
    """GET /partials/stats-row?instance=radarr/Default passes app + instance_stable_id to get_dashboard_stats."""
    test_app.state.settings.radarr["Default"].id = "radarr-default-id"
    with patch("triggarr.web.routes.get_dashboard_stats", new_callable=AsyncMock) as mock_stats:
        mock_stats.return_value = {
            "overall_rate": None, "radarr_rate": None, "sonarr_rate": None, "lidarr_rate": None,
            "movies_found": 0, "movies_updated": 0,
            "episodes_found": 0, "episodes_updated": 0, "albums_found": 0, "albums_updated": 0,
            "avg_time_to_grab_seconds": None,
        }
        response = client.get("/partials/stats-row?instance=radarr/Default")
        assert response.status_code == 200
        mock_stats.assert_awaited_once()
        call_kwargs = mock_stats.call_args
        assert call_kwargs[1].get("app") == "Radarr"
        assert call_kwargs[1].get("instance_stable_id") == "radarr-default-id"


def test_stats_row_no_filter(client, test_app):
    """GET /partials/stats-row without ?instance= calls get_dashboard_stats with instance_id=None."""
    with patch("triggarr.web.routes.get_dashboard_stats", new_callable=AsyncMock) as mock_stats:
        mock_stats.return_value = {
            "overall_rate": None, "radarr_rate": None, "sonarr_rate": None, "lidarr_rate": None,
            "movies_found": 0, "movies_updated": 0,
            "episodes_found": 0, "episodes_updated": 0, "albums_found": 0, "albums_updated": 0,
            "avg_time_to_grab_seconds": None,
        }
        response = client.get("/partials/stats-row")
        assert response.status_code == 200
        mock_stats.assert_awaited_once()
        call_kwargs = mock_stats.call_args
        assert call_kwargs[1].get("instance_id") is None


def test_app_context_includes_tag_warnings(client, test_app):
    """_build_app_context includes tag_warnings from app_state (defaults to [])."""
    # Default state has no tag_warnings key -- should default to []
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    # Set tag_warnings in state and verify it flows through
    test_app.state.triggarr_state["radarr"]["Default"]["tag_warnings"] = [
        {"tag": "nonexistent", "field": "missing"}
    ]
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200


def test_dashboard_includes_all_instances_and_health(client, test_app):
    """Dashboard route includes health context and all_instances list."""
    response = client.get("/")
    assert response.status_code == 200


def test_dashboard_migration_banner_uses_runtime_config_path(client, test_app, tmp_path):
    """Dashboard migration banner follows app.state.config_path, not import-time CONFIG_DIR."""
    test_app.state.config_path = tmp_path / "triggarr.toml"
    marker = tmp_path / ".migrated"
    marker.touch()

    response = client.get("/")

    assert response.status_code == 200
    assert "Config migrated to v2.3 format" in response.text


def test_dismiss_migration(client, test_app, tmp_path):
    """DELETE /api/dismiss-migration deletes .migrated marker and returns empty HTML."""
    test_app.state.config_path = tmp_path / "triggarr.toml"
    marker = tmp_path / ".migrated"
    marker.touch()

    response = client.delete("/api/dismiss-migration", headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert response.text == ""
    assert not marker.exists()


def test_dismiss_migration_no_file(client, test_app, tmp_path):
    """DELETE /api/dismiss-migration succeeds even if .migrated does not exist."""
    test_app.state.config_path = tmp_path / "triggarr.toml"

    response = client.delete("/api/dismiss-migration", headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert response.text == ""


def test_dismiss_migration_csrf_rejects_non_htmx(client, test_app, tmp_path):
    """DELETE /api/dismiss-migration returns 403 without HX-Request header."""
    test_app.state.config_path = tmp_path / "triggarr.toml"
    marker = tmp_path / ".migrated"
    marker.touch()

    response = client.delete("/api/dismiss-migration")

    assert response.status_code == 403
    # File should NOT have been deleted
    assert marker.exists()


def test_dismiss_migration_csrf_allows_htmx(client, test_app, tmp_path):
    """DELETE /api/dismiss-migration succeeds with HX-Request header."""
    test_app.state.config_path = tmp_path / "triggarr.toml"
    marker = tmp_path / ".migrated"
    marker.touch()

    response = client.delete("/api/dismiss-migration", headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert not marker.exists()


# ---------------------------------------------------------------------------
# Lidarr template integration
# ---------------------------------------------------------------------------


def test_settings_page_shows_lidarr_section(client, test_app):
    """Settings page includes a Lidarr section with correct port placeholder."""
    response = client.get("/settings")
    assert response.status_code == 200
    assert "lidarr" in response.text.lower()
    assert "8686" in response.text


def test_history_filter_includes_lidarr(client, test_app):
    """History page filter bar includes a Lidarr pill."""
    response = client.get("/history")
    assert response.status_code == 200
    assert "Lidarr" in response.text


def test_dashboard_empty_state_mentions_lidarr(client, test_app):
    """Dashboard empty state mentions Lidarr alongside Radarr and Sonarr."""
    # Disable all apps to trigger empty state
    test_app.state.settings = make_settings(
        radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False,
    )
    response = client.get("/")
    assert response.status_code == 200
    assert "Lidarr" in response.text


def test_stats_row_includes_albums(client, test_app):
    """Stats row partial includes Albums card when not filtered to a specific app."""
    with patch("triggarr.web.routes.get_dashboard_stats", new_callable=AsyncMock) as mock_stats:
        mock_stats.return_value = {
            "overall_rate": 50.0, "radarr_rate": 60.0, "sonarr_rate": 40.0, "lidarr_rate": 70.0,
            "movies_found": 5, "movies_updated": 2,
            "episodes_found": 10, "episodes_updated": 3,
            "albums_found": 8, "albums_updated": 1,
            "avg_time_to_grab_seconds": 120.0,
        }
        response = client.get("/partials/stats-row")
        assert response.status_code == 200
        assert "Albums" in response.text
        assert "8" in response.text  # albums_found


# --- Changelog ---


def test_changelog_route_returns_html(client, test_app):
    """GET /changelog returns 200 with HTML content."""
    response = client.get("/changelog")
    assert response.status_code == 200
    assert "v2.6.0" in response.text or "changelog" in response.text.lower()


def test_changelog_route_latest_only(client, test_app):
    """GET /changelog?latest=true returns only the newest version."""
    response = client.get("/changelog?latest=true")
    assert response.status_code == 200
    full = client.get("/changelog")
    # If full changelog has multiple versions, latest should have exactly 1
    if "not available" not in full.text and full.text.count("changelog-version") > 1:
        assert len(response.text) < len(full.text)
        assert response.text.count("changelog-version") == 1


def test_changelog_link_in_nav(client, test_app):
    """Dashboard page includes changelog link in the nav bar."""
    response = client.get("/")
    assert response.status_code == 200
    assert "/changelog" in response.text
    assert "changelog-modal" in response.text


# --- SAFETY-05 / TEST-03: concurrent settings save serialization ---


async def test_concurrent_settings_save_serialized(test_app, tmp_path):
    """SAFETY-05 / TEST-03: two concurrent POST /settings cannot interleave.

    The route handler acquires request.app.state.search_lock before dispatching
    _atomic_toml_write via run_in_executor. The second concurrent request must
    wait for the first to release the lock; the recorded call order must be
    [enter, exit, enter, exit], never [enter, enter, exit, exit].

    Uses httpx.AsyncClient + ASGITransport because the synchronous TestClient
    cannot fire two truly concurrent requests on the same event loop
    (RESEARCH 64-RESEARCH.md Pitfall 2). This is a new pattern for web tests
    in this repo -- precedent for ASGITransport-style drivers exists in
    tests/test_startup.py:257 (MockTransport) and tests/test_clients.py.
    """
    import time

    from triggarr.config import _atomic_toml_write as real_atomic_write

    call_order: list[str] = []

    def slow_atomic_write(path, data):
        call_order.append("enter")
        time.sleep(0.05)  # block the executor thread to force lock contention
        call_order.append("exit")
        return real_atomic_write(path, data)

    # Two schema-complete form payloads that differ only in log_level so we
    # can confirm the final config reflects one save (not a hybrid).
    def _form(log_level: str) -> dict[str, str]:
        return {
            "log_level": log_level,
            "hard_max_per_cycle": "0",
            "max_history_rows": "5000",
            "request_timeout": "60",
            "page_size": "100",
            "tracking_window_minutes": "120",
            "radarr__Default__url": "http://radarr:7878",
            "radarr__Default__api_key": "",
            "radarr__Default__enabled": "on",
            "radarr__Default__search_interval": "30",
            "radarr__Default__search_missing_count": "5",
            "radarr__Default__search_cutoff_count": "5",
            "radarr__Default__missing_tag": "",
            "radarr__Default__cutoff_tag": "",
            "sonarr__Default__url": "http://sonarr:8989",
            "sonarr__Default__api_key": "",
            "sonarr__Default__enabled": "on",
            "sonarr__Default__search_interval": "30",
            "sonarr__Default__search_missing_count": "5",
            "sonarr__Default__search_cutoff_count": "5",
            "sonarr__Default__missing_tag": "",
            "sonarr__Default__cutoff_tag": "",
        }

    form_a = _form("info")
    form_b = _form("debug")

    with patch("triggarr.web.routes._atomic_toml_write", side_effect=slow_atomic_write):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://test",
        ) as ac:
            r1, r2 = await asyncio.gather(
                ac.post("/settings", data=form_a, follow_redirects=False),
                ac.post("/settings", data=form_b, follow_redirects=False),
            )

    assert r1.status_code == 303, f"First request status={r1.status_code} body={r1.text[:200]}"
    assert r2.status_code == 303, f"Second request status={r2.status_code} body={r2.text[:200]}"
    assert call_order == ["enter", "exit", "enter", "exit"], (
        f"Lock did not serialize writes; call_order={call_order}. "
        "If [enter, enter, exit, exit], the asyncio.Lock is missing or no-op."
    )


def test_csp_nonce_matches_html_script_tag(test_app):
    """SEC-01 D-02 (Pitfall 5): the nonce value in the CSP response header must
    match the nonce value in the rendered HTML's <script nonce="..."> tags
    for the SAME request. Without this parity, the browser blocks the inline
    scripts even though both sides "have a nonce".

    This is the single most important automated check in SEC-01 -- httpx.TestClient
    does not enforce CSP at runtime, but it CAN verify the contract that the
    middleware-generated nonce and the template-rendered nonce are the same
    string within one request. The default test_app fixture does NOT mount
    SecurityHeadersMiddleware (production does, per triggarr/__main__.py:69);
    this test mounts it explicitly so the response carries the CSP header.
    """
    import re

    from triggarr.web.middleware import SecurityHeadersMiddleware

    test_app.add_middleware(SecurityHeadersMiddleware)

    with TestClient(test_app) as tc:
        response = tc.get("/")
    assert response.status_code == 200
    csp = response.headers["Content-Security-Policy"]
    header_match = re.search(r"'nonce-([A-Za-z0-9_-]+)'", csp)
    assert header_match, f"CSP header missing nonce: {csp}"
    header_nonce = header_match.group(1)

    # Find at least one <script nonce="..."> in the rendered HTML
    body_match = re.search(r'<script nonce="([A-Za-z0-9_-]+)"', response.text)
    assert body_match, "rendered HTML missing <script nonce=...> tag"
    body_nonce = body_match.group(1)

    assert header_nonce == body_nonce, (
        f"CSP header nonce ({header_nonce!r}) does NOT match rendered script nonce ({body_nonce!r}); "
        "this would cause the browser to silently block all inline scripts"
    )


# ---------------------------------------------------------------------------
# 78-04 / D-06: staleness moved from last_success to last_checked; R-05: the
# confirmed-search time is last_successful_search, which never falls back to
# the legacy last_success value.
# ---------------------------------------------------------------------------


def test_exact_time_filter_formats_iso_timestamp():
    """_exact_time_filter turns an ISO Z timestamp into 'YYYY-MM-DD HH:MM:SS UTC'."""
    from triggarr.web.routes import _exact_time_filter

    assert _exact_time_filter("2026-04-13T14:32:10Z") == "2026-04-13 14:32:10 UTC"


def test_exact_time_filter_empty_for_none_and_empty_string():
    """_exact_time_filter returns '' for falsy input (None or '')."""
    from triggarr.web.routes import _exact_time_filter

    assert _exact_time_filter(None) == ""
    assert _exact_time_filter("") == ""


def test_build_app_context_last_checked_equals_last_run(client, test_app):
    """ctx['last_checked'] mirrors the state's last_run value (D-04)."""
    from unittest.mock import MagicMock

    from fastapi import Request

    from triggarr.web.routes import _build_app_context

    test_app.state.triggarr_state["radarr"]["Default"]["last_run"] = "2026-04-13T14:32:10Z"

    mock_request = MagicMock(spec=Request)
    mock_request.app = test_app
    ctx = _build_app_context(mock_request, "radarr", "Default")
    assert ctx is not None
    assert ctx["last_checked"] == "2026-04-13T14:32:10Z"


def test_build_app_context_last_checked_stale_false_on_never(client, test_app):
    """last_checked_stale is False when last_run is None -- never amber on Never (D-06)."""
    from unittest.mock import MagicMock

    from fastapi import Request

    from triggarr.web.routes import _build_app_context

    test_app.state.triggarr_state["radarr"]["Default"]["last_run"] = None

    mock_request = MagicMock(spec=Request)
    mock_request.app = test_app
    ctx = _build_app_context(mock_request, "radarr", "Default")
    assert ctx is not None
    assert ctx["last_checked"] is None
    assert ctx["last_checked_stale"] is False


def test_build_app_context_last_checked_stale_true_when_old(client, test_app):
    """last_checked_stale is True when last_run is older than 2x the search interval (D-06)."""
    from datetime import UTC, datetime, timedelta
    from unittest.mock import MagicMock

    from fastapi import Request

    from triggarr.web.routes import _build_app_context

    # Default search_interval is 30 min; 2x = 60 min. Use 90 min ago = stale.
    old_ts = (datetime.now(UTC) - timedelta(minutes=90)).isoformat().replace("+00:00", "Z")
    test_app.state.triggarr_state["radarr"]["Default"]["last_run"] = old_ts

    mock_request = MagicMock(spec=Request)
    mock_request.app = test_app
    ctx = _build_app_context(mock_request, "radarr", "Default")
    assert ctx is not None
    assert ctx["last_checked_stale"] is True


def test_build_app_context_last_checked_stale_false_when_recent(client, test_app):
    """last_checked_stale is False when last_run is within 2x the search interval (D-06)."""
    from datetime import UTC, datetime, timedelta
    from unittest.mock import MagicMock

    from fastapi import Request

    from triggarr.web.routes import _build_app_context

    # Default search_interval is 30 min; 2x = 60 min. Use 5 min ago = fresh.
    fresh_ts = (datetime.now(UTC) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    test_app.state.triggarr_state["radarr"]["Default"]["last_run"] = fresh_ts

    mock_request = MagicMock(spec=Request)
    mock_request.app = test_app
    ctx = _build_app_context(mock_request, "radarr", "Default")
    assert ctx is not None
    assert ctx["last_checked_stale"] is False


def test_build_app_context_last_checked_stale_false_on_unparseable(client, test_app):
    """A garbage last_run value never renders amber (D-06)."""
    from unittest.mock import MagicMock

    from fastapi import Request

    from triggarr.web.routes import _build_app_context

    test_app.state.triggarr_state["radarr"]["Default"]["last_run"] = "not-a-timestamp"

    mock_request = MagicMock(spec=Request)
    mock_request.app = test_app
    ctx = _build_app_context(mock_request, "radarr", "Default")
    assert ctx is not None
    assert ctx["last_checked_stale"] is False


def test_build_app_context_no_last_cycle_is_none(client, test_app):
    """ctx['last_cycle'] is None when the instance state has no last_cycle record."""
    from unittest.mock import MagicMock

    from fastapi import Request

    from triggarr.web.routes import _build_app_context

    test_app.state.triggarr_state["radarr"]["Default"].pop("last_cycle", None)

    mock_request = MagicMock(spec=Request)
    mock_request.app = test_app
    ctx = _build_app_context(mock_request, "radarr", "Default")
    assert ctx is not None
    assert ctx["last_cycle"] is None


def test_build_app_context_last_cycle_is_cycle_view_output(client, test_app):
    """ctx['last_cycle'] is the cycle_view() rendering of a persisted last_cycle record."""
    from unittest.mock import MagicMock

    from fastapi import Request

    from triggarr.web.routes import _build_app_context

    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = {
        "grade": "success",
        "accepted": 5,
        "failed": 0,
        "malformed_skipped": 0,
        "persistence_failed": 0,
        "failure_reasons": [],
        "unevaluated": [],
        "eligible": {},
        "fetch_error": None,
        "finished_at": "2026-04-13T14:32:10Z",
    }

    mock_request = MagicMock(spec=Request)
    mock_request.app = test_app
    ctx = _build_app_context(mock_request, "radarr", "Default")
    assert ctx is not None
    assert ctx["last_cycle"] is not None
    assert ctx["last_cycle"]["grade"] == "success"
    assert ctx["last_cycle"]["grade_label"] == "Success"
    assert ctx["last_cycle"]["accepted"] == 5


def test_build_app_context_legacy_last_success_true_without_last_cycle(client, test_app):
    """legacy_last_success is True iff last_cycle is None and last_success is set (D-14)."""
    from unittest.mock import MagicMock

    from fastapi import Request

    from triggarr.web.routes import _build_app_context

    test_app.state.triggarr_state["radarr"]["Default"].pop("last_cycle", None)
    test_app.state.triggarr_state["radarr"]["Default"]["last_success"] = "2026-01-01T00:00:00Z"

    mock_request = MagicMock(spec=Request)
    mock_request.app = test_app
    ctx = _build_app_context(mock_request, "radarr", "Default")
    assert ctx is not None
    assert ctx["legacy_last_success"] is True


def test_build_app_context_legacy_last_success_false_with_last_cycle(client, test_app):
    """R-05: once a last_cycle record exists, the legacy last_success value never fills the
    confirmed slot -- legacy_last_success is False and last_successful_search is None.
    """
    from unittest.mock import MagicMock

    from fastapi import Request

    from triggarr.web.routes import _build_app_context

    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = {
        "grade": "nothing_needed",
        "accepted": 0,
        "failed": 0,
        "malformed_skipped": 0,
        "persistence_failed": 0,
        "failure_reasons": [],
        "unevaluated": [],
        "eligible": {},
        "fetch_error": None,
        "finished_at": "2026-04-13T14:32:10Z",
    }
    test_app.state.triggarr_state["radarr"]["Default"]["last_success"] = "2026-01-01T00:00:00Z"
    test_app.state.triggarr_state["radarr"]["Default"]["last_successful_search"] = None

    mock_request = MagicMock(spec=Request)
    mock_request.app = test_app
    ctx = _build_app_context(mock_request, "radarr", "Default")
    assert ctx is not None
    assert ctx["legacy_last_success"] is False
    assert ctx["last_successful_search"] is None


def test_build_app_context_last_successful_search_from_state(client, test_app):
    """ctx['last_successful_search'] mirrors the state field verbatim (R-05)."""
    from unittest.mock import MagicMock

    from fastapi import Request

    from triggarr.web.routes import _build_app_context

    test_app.state.triggarr_state["radarr"]["Default"]["last_successful_search"] = "2026-04-13T14:00:00Z"

    mock_request = MagicMock(spec=Request)
    mock_request.app = test_app
    ctx = _build_app_context(mock_request, "radarr", "Default")
    assert ctx is not None
    assert ctx["last_successful_search"] == "2026-04-13T14:00:00Z"


def test_build_app_context_app_label_capitalized(client, test_app):
    """ctx['app_label'] is the capitalized app name (e.g. 'Radarr')."""
    from unittest.mock import MagicMock

    from fastapi import Request

    from triggarr.web.routes import _build_app_context

    mock_request = MagicMock(spec=Request)
    mock_request.app = test_app
    ctx = _build_app_context(mock_request, "radarr", "Default")
    assert ctx is not None
    assert ctx["app_label"] == "Radarr"


def test_build_app_context_no_longer_exposes_last_success_stale(client, test_app):
    """D-06: Last successful search is never amber -- the key is removed from the context."""
    from unittest.mock import MagicMock

    from fastapi import Request

    from triggarr.web.routes import _build_app_context

    mock_request = MagicMock(spec=Request)
    mock_request.app = test_app
    ctx = _build_app_context(mock_request, "radarr", "Default")
    assert ctx is not None
    assert "last_success_stale" not in ctx


# ---------------------------------------------------------------------------
# RES-03 (Plan 67-02): tag cache invalidation on save / remove + search_now wiring
# ---------------------------------------------------------------------------


def _multi_form_data(**overrides) -> dict:
    """Baseline multi-instance settings form (Default + 4K radarr, Default sonarr).

    Mirrors the existing config in multi_instance_app so save_settings is a
    no-op unless overridden. Pass keyword overrides like
    radarr__4K__url='http://changed:7878' to mutate a single field.
    """
    data = {
        "log_level": "info",
        "hard_max_per_cycle": "0",
        "max_history_rows": "1000",
        "request_timeout": "30",
        "page_size": "50",
        "tracking_window_minutes": "60",
        "radarr__Default__url": "http://radarr:7878",
        "radarr__Default__api_key": "",
        "radarr__Default__enabled": "on",
        "radarr__Default__search_interval": "30",
        "radarr__Default__search_missing_count": "5",
        "radarr__Default__search_cutoff_count": "5",
        "radarr__Default__missing_tag": "wanted",
        "radarr__Default__cutoff_tag": "upgrade",
        "radarr__4K__url": "http://radarr4k:7878",
        "radarr__4K__api_key": "",
        "radarr__4K__enabled": "on",
        "radarr__4K__search_interval": "30",
        "radarr__4K__search_missing_count": "5",
        "radarr__4K__search_cutoff_count": "5",
        "radarr__4K__missing_tag": "wanted-4k",
        "radarr__4K__cutoff_tag": "",
        "sonarr__Default__url": "http://sonarr:8989",
        "sonarr__Default__api_key": "",
        "sonarr__Default__enabled": "on",
        "sonarr__Default__search_interval": "30",
        "sonarr__Default__search_missing_count": "5",
        "sonarr__Default__search_cutoff_count": "5",
        "sonarr__Default__missing_tag": "",
        "sonarr__Default__cutoff_tag": "",
    }
    data.update(overrides)
    return data


def test_save_settings_invalidates_changed_instance_cache(multi_client, multi_instance_app):
    """RES-03 (D-08): a changed url/api_key/missing_tag/cutoff_tag pops that cache entry."""
    import time

    multi_instance_app.state.tag_cache[("radarr", "Default")] = ([], time.monotonic())
    multi_instance_app.state.tag_cache[("radarr", "4K")] = ([], time.monotonic())

    # Change the 4K instance's missing_tag -> only its entry should be popped.
    response = multi_client.post(
        "/settings",
        data=_multi_form_data(radarr__4K__missing_tag="changed-tag"),
        follow_redirects=False,
    )
    assert response.status_code == 303

    assert ("radarr", "4K") not in multi_instance_app.state.tag_cache, (
        "Changed instance's cache entry should be invalidated"
    )


def test_save_settings_preserves_unchanged_instance_cache(multi_client, multi_instance_app):
    """RES-03 (D-08): an instance with no cache-relevant change keeps its entry."""
    import time

    multi_instance_app.state.tag_cache[("radarr", "Default")] = ([], time.monotonic())
    multi_instance_app.state.tag_cache[("radarr", "4K")] = ([], time.monotonic())

    # Change ONLY 4K's missing_tag; Default is submitted unchanged.
    response = multi_client.post(
        "/settings",
        data=_multi_form_data(radarr__4K__missing_tag="changed-tag"),
        follow_redirects=False,
    )
    assert response.status_code == 303

    assert ("radarr", "Default") in multi_instance_app.state.tag_cache, (
        "Unchanged instance's cache entry should be preserved"
    )


def test_remove_instance_invalidates_tag_cache(multi_instance_app):
    """RES-03 (Pitfall 5): removing via the endpoint pops the instance's cache entry."""
    import time

    multi_instance_app.state.tag_cache[("radarr", "4K")] = ([], time.monotonic())

    with TestClient(multi_instance_app) as tc:
        response = tc.post("/api/instance/remove/radarr/4K", follow_redirects=False)
    assert response.status_code == 303
    assert ("radarr", "4K") not in multi_instance_app.state.tag_cache, (
        "Removed instance's cache entry should be cleared"
    )


def test_save_settings_form_removal_invalidates_tag_cache(multi_client, multi_instance_app):
    """RES-03 (Codex finding B): omitting an instance from the form pops its cache entry.

    The 4K instance is dropped from the submission (no radarr__4K__* fields), so
    save_settings' removal loop treats new_cfg as None. Its stale cache key must
    be popped so a later instance reusing the '4K' name within the TTL cannot
    receive the old instance's cached tags.
    """
    import time

    multi_instance_app.state.tag_cache[("radarr", "4K")] = ([], time.monotonic())

    # Build a form WITHOUT any radarr__4K__* fields (4K removed via form).
    data = _multi_form_data()
    for key in list(data.keys()):
        if key.startswith("radarr__4K__"):
            del data[key]

    response = multi_client.post("/settings", data=data, follow_redirects=False)
    assert response.status_code == 303

    assert ("radarr", "4K") not in multi_instance_app.state.tag_cache, (
        "Form-removed instance's cache entry should be cleared (finding B)"
    )


def test_search_now_refetches_when_cached_list_lacks_configured_tag(multi_instance_app):
    """vibe-check bugs-001: a manual search refetches a fresh cached list that lacks a configured tag."""
    import time

    from triggarr.clients.base import Tag

    radarr_client = multi_instance_app.state.radarr_clients["Default"]
    radarr_client.get_tags = AsyncMock(return_value=[Tag(id=1, label="wanted"), Tag(id=2, label="upgrade")])
    radarr_client.get_wanted_missing = AsyncMock(return_value=[])
    radarr_client.get_wanted_cutoff = AsyncMock(return_value=[])
    radarr_client.get_library_count = AsyncMock(return_value=0)
    radarr_client.search_movies = AsyncMock()

    # Cached before 'upgrade' was created in Radarr.
    multi_instance_app.state.tag_cache[("radarr", "Default")] = ([Tag(id=1, label="wanted")], time.monotonic())

    with (
        patch("triggarr.web.routes.save_state"),
        TestClient(multi_instance_app) as tc,
    ):
        response = tc.post("/api/search-now/radarr/Default")

    assert response.status_code == 200
    radarr_client.get_tags.assert_awaited_once()
    assert multi_instance_app.state.triggarr_state["radarr"]["Default"]["tag_warnings"] == []
    cached_tags, _ = multi_instance_app.state.tag_cache[("radarr", "Default")]
    assert sorted(t.label for t in cached_tags) == ["upgrade", "wanted"]


def test_refresh_counts_refetches_when_cached_list_lacks_configured_tag(multi_instance_app):
    """vibe-check bugs-001: a count refresh refetches a fresh cached list that lacks a configured tag."""
    import time

    from triggarr.clients.base import Tag

    radarr_client = multi_instance_app.state.radarr_clients["Default"]
    radarr_client.get_tags = AsyncMock(return_value=[Tag(id=1, label="wanted"), Tag(id=2, label="upgrade")])
    radarr_client.get_wanted_missing = AsyncMock(return_value=[])
    radarr_client.get_wanted_cutoff = AsyncMock(return_value=[])
    radarr_client.get_library_count = AsyncMock(return_value=0)

    multi_instance_app.state.tag_cache[("radarr", "Default")] = ([Tag(id=1, label="wanted")], time.monotonic())

    with TestClient(multi_instance_app) as tc:
        response = tc.post("/api/refresh-counts/radarr/Default")

    assert response.status_code == 200
    radarr_client.get_tags.assert_awaited_once()
    assert multi_instance_app.state.triggarr_state["radarr"]["Default"]["tag_warnings"] == []


def test_search_now_reuses_warm_tag_cache(multi_instance_app):
    """RES-03: a manual search reuses a warm cache entry instead of calling get_tags.

    The Default radarr instance has missing_tag='wanted'. With a fresh cache
    entry pre-populated, search_now's resolver returns the cached tags so the
    real client.get_tags() is never awaited.
    """
    import time

    from triggarr.clients.base import Tag

    radarr_client = multi_instance_app.state.radarr_clients["Default"]
    radarr_client.get_tags = AsyncMock(return_value=[Tag(id=1, label="wanted"), Tag(id=2, label="upgrade")])
    radarr_client.get_wanted_missing = AsyncMock(return_value=[])
    radarr_client.get_wanted_cutoff = AsyncMock(return_value=[])
    radarr_client.get_library_count = AsyncMock(return_value=0)
    radarr_client.search_movies = AsyncMock()

    # Warm cache entry for (radarr, Default) covering both configured tags
    # (a cached list lacking a configured tag is refetched -- PR #26 bugs-001).
    multi_instance_app.state.tag_cache[("radarr", "Default")] = (
        [Tag(id=1, label="wanted"), Tag(id=2, label="upgrade")],
        time.monotonic(),
    )

    with (
        patch("triggarr.web.routes.save_state"),
        TestClient(multi_instance_app) as tc,
    ):
        response = tc.post("/api/search-now/radarr/Default")

    assert response.status_code == 200
    radarr_client.get_tags.assert_not_awaited()
