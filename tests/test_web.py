"""Test suite for web UI routes.

Covers dashboard rendering, settings form (masked API keys, TOML write,
key preservation, PRG redirect), htmx partials, and search-now validation.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from triggarr.db import init_db, insert_search_entry
from triggarr.log_buffer import LogEntry, log_buffer
from triggarr.web.routes import STATIC_DIR, router


@pytest.fixture
async def test_app(tmp_path):
    """Build a minimal FastAPI app with mocked state for route testing."""
    log_buffer.clear()  # Prevent test pollution from module-level singleton
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    # Initialize SQLite search history database for tests
    db_path = tmp_path / "test.db"
    await init_db(db_path)
    await insert_search_entry(db_path, "Radarr", "missing", "Test Movie")
    app.state.db_path = db_path

    # Mock triggarr state
    app.state.triggarr_state = {
        "radarr": {
            "missing_cursor": 3,
            "cutoff_cursor": 1,
            "last_run": "2026-01-15T10:30:00Z",
            "connected": True,
            "unreachable_since": None,
            "missing_count": 42,
            "cutoff_count": 7,
        },
        "sonarr": {
            "missing_cursor": 0,
            "cutoff_cursor": 0,
            "last_run": None,
            "connected": None,
            "unreachable_since": None,
            "missing_count": None,
            "cutoff_count": None,
        },
        "search_log": [],
    }

    # Mock settings with SecretStr-like api_key
    mock_settings = MagicMock()
    mock_settings.radarr.enabled = True
    mock_settings.radarr.url = "http://radarr:7878"
    mock_settings.radarr.api_key.get_secret_value.return_value = "test-radarr-key"
    mock_settings.radarr.search_interval = 30
    mock_settings.radarr.search_missing_count = 5
    mock_settings.radarr.search_cutoff_count = 5
    mock_settings.sonarr.enabled = True
    mock_settings.sonarr.url = "http://sonarr:8989"
    mock_settings.sonarr.api_key.get_secret_value.return_value = "test-sonarr-key"
    mock_settings.sonarr.search_interval = 30
    mock_settings.sonarr.search_missing_count = 5
    mock_settings.sonarr.search_cutoff_count = 5
    mock_settings.general.log_level = "info"
    app.state.settings = mock_settings

    # Mock scheduler
    mock_scheduler = MagicMock()
    mock_job = MagicMock()
    mock_job.next_run_time = None
    mock_scheduler.get_job.return_value = mock_job
    app.state.scheduler = mock_scheduler

    # Mock clients (close() is async, so needs AsyncMock)
    radarr_client = MagicMock()
    radarr_client.close = AsyncMock()
    app.state.radarr_client = radarr_client
    sonarr_client = MagicMock()
    sonarr_client.close = AsyncMock()
    app.state.sonarr_client = sonarr_client

    # Paths
    app.state.config_path = tmp_path / "triggarr.toml"
    app.state.state_path = tmp_path / "state.json"

    # Search lock (needed by search_now endpoint)
    app.state.search_lock = asyncio.Lock()

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
    """GET /partials/app-card/radarr returns 200."""
    response = client.get("/partials/app-card/radarr")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"


def test_app_card_partial_has_htmx_attributes(client):
    """App card partial contains htmx polling attributes."""
    response = client.get("/partials/app-card/radarr")
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
            "radarr_url": "http://radarr:7878",
            "radarr_api_key": "new-key",
            "radarr_enabled": "on",
            "radarr_search_interval": "15",
            "radarr_search_missing_count": "10",
            "radarr_search_cutoff_count": "3",
            "sonarr_url": "",
            "sonarr_api_key": "",
            "sonarr_search_interval": "30",
            "sonarr_search_missing_count": "5",
            "sonarr_search_cutoff_count": "5",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, f"Expected 303 redirect, got {response.status_code}"
    assert response.headers["location"] == "/settings"

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
            "radarr_url": "http://radarr:7878",
            "radarr_api_key": "",  # Empty = keep existing
            "radarr_enabled": "on",
            "radarr_search_interval": "30",
            "radarr_search_missing_count": "5",
            "radarr_search_cutoff_count": "5",
            "sonarr_url": "http://sonarr:8989",
            "sonarr_api_key": "",  # Empty = keep existing
            "sonarr_enabled": "on",
            "sonarr_search_interval": "30",
            "sonarr_search_missing_count": "5",
            "sonarr_search_cutoff_count": "5",
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
            "radarr_url": "http://radarr:7878",
            "radarr_api_key": "brand-new-key",  # Explicit new key
            "radarr_enabled": "on",
            "radarr_search_interval": "30",
            "radarr_search_missing_count": "5",
            "radarr_search_cutoff_count": "5",
            "sonarr_url": "http://sonarr:8989",
            "sonarr_api_key": "",
            "sonarr_enabled": "on",
            "sonarr_search_interval": "30",
            "sonarr_search_missing_count": "5",
            "sonarr_search_cutoff_count": "5",
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
            "radarr_url": "http://radarr:7878",
            "radarr_api_key": "test-key",
            "radarr_enabled": "on",
            "radarr_search_interval": "30",
            "radarr_search_missing_count": "0",
            "radarr_search_cutoff_count": "0",
            "sonarr_url": "",
            "sonarr_api_key": "",
            "sonarr_search_interval": "30",
            "sonarr_search_missing_count": "5",
            "sonarr_search_cutoff_count": "5",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, f"Expected 303 redirect, got {response.status_code}"
    assert response.headers["location"] == "/settings"
    # Config file should NOT have been written (validation rejected the request)
    assert not test_app.state.config_path.exists(), "Config should not be written when both counts are 0"


def test_save_settings_accepts_zero_missing_with_positive_cutoff(client, test_app, tmp_path):
    """POST /settings with missing=0, cutoff=5 for enabled app writes config successfully."""
    response = client.post(
        "/settings",
        data={
            "log_level": "info",
            "hard_max_per_cycle": "0",
            "radarr_url": "http://radarr:7878",
            "radarr_api_key": "test-key",
            "radarr_enabled": "on",
            "radarr_search_interval": "30",
            "radarr_search_missing_count": "0",
            "radarr_search_cutoff_count": "5",
            "sonarr_url": "",
            "sonarr_api_key": "",
            "sonarr_search_interval": "30",
            "sonarr_search_missing_count": "5",
            "sonarr_search_cutoff_count": "5",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, f"Expected 303 redirect, got {response.status_code}"
    assert response.headers["location"] == "/settings"
    # Config file SHOULD have been written (0 missing is valid when cutoff > 0)
    assert test_app.state.config_path.exists(), "Config should be written when one count is positive"
    content = test_app.state.config_path.read_text()
    assert "radarr" in content, "TOML should contain radarr section"


def test_search_now_invalid_app(client):
    """POST /api/search-now/invalid returns 400."""
    response = client.post("/api/search-now/invalid")
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
        response = client.post("/api/search-now/radarr")
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
    db_path = test_app.state.db_path
    await insert_search_entry(
        db_path, "Radarr", "missing", "Failed Movie",
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
    assert 'href="/history"' in response.text
    # The history page sets nav_history_class to text-white (active)
    # Find the <a> tag containing href="/history" and check its class
    text = response.text
    history_link_start = text.index('href="/history"')
    a_start = text.rfind("<a", 0, history_link_start)
    # Get the full <a> tag (up to closing >)
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
    db_path = test_app.state.db_path
    for i in range(60):
        await insert_search_entry(db_path, "Radarr", "missing", f"Bulk Movie {i}")

    with TestClient(test_app) as tc:
        response = tc.get("/partials/history-results?page=2")
    assert response.status_code == 200
    # Pagination controls should be present (Previous / Next links or page numbers)
    assert "Previous" in response.text


async def test_history_page_empty_state(test_app, tmp_path):
    """GET /history with empty DB shows 'No search history yet' message."""
    # Create a fresh empty DB at a different tmp_path
    empty_db = tmp_path / "empty.db"
    await init_db(empty_db)
    test_app.state.db_path = empty_db

    with TestClient(test_app) as tc:
        response = tc.get("/history")
    assert response.status_code == 200
    assert "No search history yet" in response.text


def test_dashboard_nav_has_history_link(client):
    """GET / dashboard nav bar contains History link."""
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/history"' in response.text


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
