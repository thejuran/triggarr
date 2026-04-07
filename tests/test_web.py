"""Test suite for web UI routes.

Covers dashboard rendering, settings form (masked API keys, TOML write,
key preservation, PRG redirect), htmx partials, and search-now validation.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

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
    db = await aiosqlite.connect(db_path)
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

    # Rate limit state (needed by search_now rate limiter — DEBT-01)
    app.state.last_search_time = {}

    return app


@pytest.fixture
def client(test_app):
    """Create a TestClient for the test app."""
    return TestClient(test_app)


def test_dashboard_returns_200(client):
    """GET / returns 200 and contains app name."""
    response = client.get("/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert "Radarr" in response.text, "Dashboard should display Radarr card"


def test_dashboard_shows_search_log(client):
    """GET / response contains search log entry."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Test Movie" in response.text, "Dashboard should show search log entry"


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


def test_search_log_partial_returns_200(client):
    """GET /partials/search-log returns 200."""
    response = client.get("/partials/search-log")
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
        "triggarr.web.routes.run_radarr_cycle",
        new=AsyncMock(return_value=test_app.state.triggarr_state),
    ), patch(
        "triggarr.web.routes.save_state",
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


async def test_search_log_shows_outcome_badge(test_app, tmp_path):
    """Search log partial shows outcome badge for entries (WEBU-11)."""
    # Insert a failed search entry
    db = test_app.state.db
    await insert_search_entry(
        db, "Radarr", "missing", "Failed Movie",
        outcome="failed", detail="Connection refused",
    )

    with TestClient(test_app) as tc:
        response = tc.get("/partials/search-log")
    assert response.status_code == 200
    assert "failed" in response.text, "Search log should show failed outcome badge"
    assert "bg-red-500/20" in response.text, "Failed outcome should use red styling"


def test_dashboard_shows_log_viewer_section(client):
    """GET / response contains the Application Log section heading."""
    # Add a sample log entry so the viewer has content
    log_buffer.add(LogEntry("2026-01-15 10:30:00", "INFO", "Test log message for dashboard"))
    response = client.get("/")
    assert response.status_code == 200
    assert "Application Log" in response.text, "Dashboard should show Application Log section"
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
    assert "text-yellow-400" in response.text, "WARNING should use yellow color"


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
    assert "text-white" in a_tag, "History nav link should have active text-white class"


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
    empty_db = await aiosqlite.connect(empty_db_path)
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
        "triggarr.web.routes.run_radarr_cycle",
        new=AsyncMock(return_value=test_app.state.triggarr_state),
    ), patch("triggarr.web.routes.save_state"):
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
        "triggarr.web.routes.run_radarr_cycle",
        new=AsyncMock(return_value=test_app.state.triggarr_state),
    ), patch("triggarr.web.routes.save_state"):
        response = client.post("/api/search-now/radarr/Default")
    assert response.status_code == 200, f"Expected 200 after window expired, got {response.status_code}"


# ---------------------------------------------------------------------------
# DEBT-05: /health endpoint
# ---------------------------------------------------------------------------


def test_health_all_connected_returns_200(client, test_app):
    """GET /health returns 200 when all enabled instances have connected=True."""
    test_app.state.triggarr_state = {
        "radarr": {"Default": {"connected": True}},
        "sonarr": {"Default": {"connected": True}},
        "lidarr": {"Default": {"connected": True}},
    }
    response = client.get("/health")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert data["status"] == "ok"


def test_health_unreachable_app_returns_503(client, test_app):
    """GET /health returns 503 when an enabled instance has connected=False."""
    test_app.state.triggarr_state = {
        "radarr": {"Default": {"connected": False}},
        "sonarr": {"Default": {"connected": True}},
        "lidarr": {"Default": {"connected": True}},
    }
    response = client.get("/health")
    assert response.status_code == 503, f"Expected 503, got {response.status_code}"
    data = response.json()
    assert data["status"] == "unhealthy"
    assert "radarr" in data["unreachable"]


def test_health_not_yet_verified_returns_503(client, test_app):
    """GET /health returns 503 when an enabled instance has connected=None (never run)."""
    test_app.state.triggarr_state = {
        "radarr": {"Default": {"connected": True}},
        "sonarr": {"Default": {"connected": None}},
        "lidarr": {"Default": {"connected": True}},
    }
    response = client.get("/health")
    assert response.status_code == 503, f"Expected 503, got {response.status_code}"
    data = response.json()
    assert "sonarr" in data["unreachable"]


def test_health_no_apps_enabled_returns_200(client, test_app):
    """GET /health returns 200 when no apps are enabled (valid awaiting-setup state)."""
    test_app.state.settings = make_settings(radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False)
    test_app.state.triggarr_state = {"radarr": {}, "sonarr": {}, "lidarr": {}}
    response = client.get("/health")
    assert response.status_code == 200, f"Expected 200 for no-apps-configured, got {response.status_code}"
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
    assert "Episodes" in response.text, "Dashboard should show Episodes card"
    assert "Time to Grab" in response.text, "Dashboard should show Time to Grab card"


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
    empty_db = await aiosqlite.connect(empty_db_path)
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
    """_build_app_context shows missing_count of total_items when both are available."""
    test_app.state.triggarr_state["radarr"]["Default"]["missing_count"] = 30
    test_app.state.triggarr_state["radarr"]["Default"]["total_items"] = 1200
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "30 of 1200" in response.text


def test_build_app_context_no_total_items_fallback(client, test_app):
    """App card shows 'X items' when total_items is not yet available (pre-first-cycle)."""
    test_app.state.triggarr_state["radarr"]["Default"]["missing_count"] = 42
    test_app.state.triggarr_state["radarr"]["Default"].pop("total_items", None)
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "42 items" in response.text, "Should fall back to count-only when total_items is None"


def test_app_card_skip_indicator_shown(client, test_app):
    """App card shows amber skip badge using missing_monitored - missing_eligible (F1 fix)."""
    test_app.state.triggarr_state["radarr"]["Default"]["missing_count"] = 50
    test_app.state.triggarr_state["radarr"]["Default"]["missing_monitored"] = 42
    test_app.state.triggarr_state["radarr"]["Default"]["missing_eligible"] = 30
    test_app.state.settings.general.skip_unreleased = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    # Badge should show 42-30=12, NOT 50-30=20
    assert "12 skipped (unreleased)" in response.text, "Should show skip count badge using monitored count"
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
    db = await aiosqlite.connect(db_path)
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

    app.state.config_path = tmp_path / "triggarr.toml"
    app.state.state_path = tmp_path / "state.json"
    app.state.search_lock = asyncio.Lock()
    app.state.last_search_time = {}

    return app


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
    """App card shows 'missing_count of total_items' for the missing section."""
    test_app.state.triggarr_state["radarr"]["Default"]["missing_count"] = 50
    test_app.state.triggarr_state["radarr"]["Default"]["total_items"] = 1500
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "50 of 1500" in response.text, "Should show missing_count of total_items"


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
    assert state["radarr"]["Default"]["missing_cursor"] == 0
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
    assert "1 connected" in response.text
    assert "2 pending" in response.text


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
    assert "1 connected" in response.text
    assert "0 disconnected" in response.text


def test_health_summary_disconnected(client, test_app):
    """Health summary treats connected=False as disconnected."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    response = client.get("/partials/health-summary")
    assert response.status_code == 200
    assert "1 disconnected" in response.text


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


def test_dismiss_migration(client, tmp_path):
    """DELETE /api/dismiss-migration deletes .migrated marker and returns empty HTML."""
    marker = tmp_path / ".migrated"
    marker.touch()

    with patch("triggarr.web.routes.CONFIG_DIR", tmp_path):
        response = client.delete("/api/dismiss-migration", headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert response.text == ""
    assert not marker.exists()


def test_dismiss_migration_no_file(client, tmp_path):
    """DELETE /api/dismiss-migration succeeds even if .migrated does not exist."""
    with patch("triggarr.web.routes.CONFIG_DIR", tmp_path):
        response = client.delete("/api/dismiss-migration", headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert response.text == ""


def test_dismiss_migration_csrf_rejects_non_htmx(client, tmp_path):
    """DELETE /api/dismiss-migration returns 403 without HX-Request header."""
    marker = tmp_path / ".migrated"
    marker.touch()
    with patch("triggarr.web.routes.CONFIG_DIR", tmp_path):
        response = client.delete("/api/dismiss-migration")

    assert response.status_code == 403
    # File should NOT have been deleted
    assert marker.exists()


def test_dismiss_migration_csrf_allows_htmx(client, tmp_path):
    """DELETE /api/dismiss-migration succeeds with HX-Request header."""
    marker = tmp_path / ".migrated"
    marker.touch()
    with patch("triggarr.web.routes.CONFIG_DIR", tmp_path):
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
