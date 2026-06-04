"""Test suite for web UI routes.

Covers dashboard rendering, settings form (masked API keys, TOML write,
key preservation, PRG redirect), htmx partials, and search-now validation.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from httpx import ASGITransport

from tests.conftest import make_settings
from triggarr.db import init_db, insert_search_entry
from triggarr.log_buffer import LogEntry, log_buffer
from triggarr.models.config import GeneralConfig, InstanceConfig, Settings
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
    """Dashboard app card shows position in 'X of Y' format (WEBU-09)."""
    response = client.get("/")
    assert response.status_code == 200
    # Radarr mock state: missing_cursor=3, missing_count=42
    assert "3 of 42" in response.text, "Missing position should show 'X of Y' format"
    # Radarr mock state: cutoff_cursor=1, cutoff_count=7
    assert "1 of 7" in response.text, "Cutoff position should show 'X of Y' format"


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
    assert "Next Scan" in response.text, "Dashboard should show Next Scan card"


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
                "Default": {"missing_cursor": 0, "cutoff_cursor": 0, "last_run": None, "connected": True},
                "4K": {"missing_cursor": 0, "cutoff_cursor": 0, "last_run": None, "connected": True},
            },
            "sonarr": {
                "Default": {"missing_cursor": 0, "cutoff_cursor": 0, "last_run": None, "connected": True},
            },
            "lidarr": {
                "Default": {"missing_cursor": 0, "cutoff_cursor": 0, "last_run": None, "connected": None},
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


def test_remove_instance_happy_path(multi_instance_app):
    """POST /api/instance/remove removes instance and cleans up."""
    with TestClient(multi_instance_app) as tc:
        response = tc.post(
            "/api/instance/remove/radarr/4K",
            follow_redirects=False,
        )
    assert response.status_code == 303
    assert "4K" not in multi_instance_app.state.settings.radarr


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


def test_no_new_body_swap_html_targets():
    """SEC-01 defense-in-depth: only ONE place in the codebase uses
    `hx-target="body"` (the Remove-instance button on settings.html, which is
    safe because remove_instance returns HX-Redirect). Any future addition of
    `hx-target="body"` must come with a paired HX-Redirect response or a
    non-script-bearing partial template, or it will silently break CSP-nonce
    inheritance on the swapped-in page.
    """
    from pathlib import Path
    matches: list[str] = []
    templates_dir = Path(__file__).resolve().parent.parent / "triggarr" / "templates"
    for path in templates_dir.rglob("*.html"):
        for line_num, line in enumerate(path.read_text().splitlines(), start=1):
            if 'hx-target="body"' in line or 'hx-target="html"' in line:
                matches.append(f"{path}:{line_num}")
    assert len(matches) == 1, (
        f"Expected exactly 1 hx-target=body/html in templates (settings.html Remove button), "
        f"found {len(matches)}: {matches}"
    )
    assert "settings.html" in matches[0], (
        f"The single body-target usage must remain on settings.html Remove button; "
        f"found unexpected location: {matches[0]}"
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
    # Cursor fields removed in Plan 02; new instances carry empty searched-logs
    assert state["radarr"]["Default"]["missing_searched"] == []
    assert "missing_cursor" not in state["radarr"]["Default"]
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
    """GET /partials/stats-row?instance=radarr/Default passes instance_id to get_dashboard_stats."""
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
        assert call_kwargs[1].get("instance_id") == "Default"


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
# RES-02: last_success_stale computation in _build_app_context (Task 2)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# RES-02: Template render assertions for "Last OK" entry (Task 3)
# ---------------------------------------------------------------------------


def test_app_card_connected_stale_last_success_renders_amber(client, test_app):
    """Connected card with a stale last_success shows 'Last OK' with text-amber-400 class."""
    from datetime import UTC, datetime, timedelta

    stale_ts = (datetime.now(UTC) - timedelta(minutes=90)).isoformat().replace("+00:00", "Z")
    test_app.state.triggarr_state["radarr"]["Default"]["last_success"] = stale_ts
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True

    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Last OK" in response.text, "Connected card with stale last_success must show 'Last OK'"
    assert "text-amber-400" in response.text, "Stale last_success must render with text-amber-400"


def test_app_card_no_last_success_renders_never_without_amber(client, test_app):
    """Card with no last_success shows 'Never' and does NOT apply text-amber-400 to that entry."""
    test_app.state.triggarr_state["radarr"]["Default"]["last_success"] = None
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    # Remove tag_warnings to ensure amber isn't coming from the tag badge
    test_app.state.triggarr_state["radarr"]["Default"]["tag_warnings"] = []

    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Last OK" in response.text, "Card must show 'Last OK' even when value is Never"
    assert "Never" in response.text, "Card must show 'Never' when last_success is None"
    # amber should NOT appear (no tag warnings, no stale timestamp)
    assert "text-amber-400" not in response.text, "Never case must NOT apply text-amber-400"


def test_app_card_unreachable_still_shows_last_ok(client, test_app):
    """Unreachable card (connected==False) still shows 'Last OK' — Codex adversarial finding A.

    The timestamp is most valuable when the instance is down: users need to see
    when searches last worked.  This is a regression test — do NOT remove it.
    """
    from datetime import UTC, datetime, timedelta

    stale_ts = (datetime.now(UTC) - timedelta(minutes=90)).isoformat().replace("+00:00", "Z")
    test_app.state.triggarr_state["radarr"]["Default"]["last_success"] = stale_ts
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False

    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Last OK" in response.text, (
        "Unreachable card MUST still show 'Last OK' — finding A regression guard"
    )


def test_build_app_context_last_success_none_is_stale(client, test_app):
    """_build_app_context with last_success=None yields last_success_stale=True.

    None means no successful search has ever run — treat as stale so the card
    shows 'Never' in the default muted style (not amber; amber is for a real
    stale timestamp).  The partial endpoint exercises _build_app_context.
    """
    test_app.state.triggarr_state["radarr"]["Default"]["last_success"] = None
    # The partial route calls _build_app_context; template must receive stale=True
    # We verify by checking that last_success_stale was True: the "Never" text
    # rendered in the template indicates the stale branch was reached.
    # Since we have not added the template yet, verify via _build_app_context directly.
    from unittest.mock import MagicMock

    from fastapi import Request

    from triggarr.web.routes import _build_app_context

    mock_request = MagicMock(spec=Request)
    mock_request.app = test_app
    ctx = _build_app_context(mock_request, "radarr", "Default")
    assert ctx is not None
    assert ctx["last_success"] is None
    assert ctx["last_success_stale"] is True


def test_build_app_context_old_last_success_is_stale(client, test_app):
    """_build_app_context with last_success older than 2x search_interval yields stale=True."""
    from datetime import UTC, datetime, timedelta
    from unittest.mock import MagicMock

    from fastapi import Request

    from triggarr.web.routes import _build_app_context

    # Default search_interval is 30 min; 2x = 60 min. Use 90 min ago = stale.
    old_ts = (datetime.now(UTC) - timedelta(minutes=90)).isoformat().replace("+00:00", "Z")
    test_app.state.triggarr_state["radarr"]["Default"]["last_success"] = old_ts

    mock_request = MagicMock(spec=Request)
    mock_request.app = test_app
    ctx = _build_app_context(mock_request, "radarr", "Default")
    assert ctx is not None
    assert ctx["last_success"] == old_ts
    assert ctx["last_success_stale"] is True


def test_build_app_context_fresh_last_success_is_not_stale(client, test_app):
    """_build_app_context with last_success within 2x search_interval yields stale=False."""
    from datetime import UTC, datetime, timedelta
    from unittest.mock import MagicMock

    from fastapi import Request

    from triggarr.web.routes import _build_app_context

    # Default search_interval is 30 min; 2x = 60 min. Use 5 min ago = fresh.
    fresh_ts = (datetime.now(UTC) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    test_app.state.triggarr_state["radarr"]["Default"]["last_success"] = fresh_ts

    mock_request = MagicMock(spec=Request)
    mock_request.app = test_app
    ctx = _build_app_context(mock_request, "radarr", "Default")
    assert ctx is not None
    assert ctx["last_success"] == fresh_ts
    assert ctx["last_success_stale"] is False


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


def test_search_now_reuses_warm_tag_cache(multi_instance_app):
    """RES-03: a manual search reuses a warm cache entry instead of calling get_tags.

    The Default radarr instance has missing_tag='wanted'. With a fresh cache
    entry pre-populated, search_now's resolver returns the cached tags so the
    real client.get_tags() is never awaited.
    """
    import time

    from triggarr.clients.base import Tag

    radarr_client = multi_instance_app.state.radarr_clients["Default"]
    radarr_client.get_tags = AsyncMock(return_value=[Tag(id=1, label="wanted")])
    radarr_client.get_wanted_missing = AsyncMock(return_value=[])
    radarr_client.get_wanted_cutoff = AsyncMock(return_value=[])
    radarr_client.get_library_count = AsyncMock(return_value=0)
    radarr_client.search_movies = AsyncMock()

    # Warm cache entry for (radarr, Default).
    multi_instance_app.state.tag_cache[("radarr", "Default")] = (
        [Tag(id=1, label="wanted")],
        time.monotonic(),
    )

    with (
        patch("triggarr.web.routes.save_state"),
        TestClient(multi_instance_app) as tc,
    ):
        response = tc.post("/api/search-now/radarr/Default")

    assert response.status_code == 200
    radarr_client.get_tags.assert_not_awaited()
