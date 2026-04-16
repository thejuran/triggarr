"""Phase 60 header redesign tests.

Verifies font discipline (FONT-01, FONT-02), header layout (HDR-01 through HDR-04),
and connection status pill (HDR-05). HDR-06 is deferred per D-05.
"""

from __future__ import annotations

import asyncio
import re
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
from triggarr.web.routes import STATIC_DIR, auth_state, router

TEMPLATES_DIR = STATIC_DIR.parent / "templates"


@pytest.fixture
async def test_app(tmp_path):
    """Build a minimal FastAPI app with mocked state for route testing."""
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
                    "last_run": "2026-01-15T10:30:00Z",
                    "connected": True,
                    "unreachable_since": None,
                    "missing_count": 42,
                    "missing_searchable": 40,
                    "cutoff_count": 5,
                    "cutoff_searchable": 3,
                    "total_items": 100,
                    "tag_warnings": [],
                }
            },
            "sonarr": {
                "Default": {
                    "missing_cursor": 0,
                    "cutoff_cursor": 0,
                    "last_run": None,
                    "connected": True,
                    "unreachable_since": None,
                    "missing_count": 10,
                    "missing_searchable": 8,
                    "cutoff_count": 2,
                    "cutoff_searchable": 1,
                    "total_items": 50,
                    "tag_warnings": [],
                }
            },
            "lidarr": {},
        }

        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_job.next_run_time = None
        mock_scheduler.get_job.return_value = mock_job
        mock_scheduler.get_jobs.return_value = []
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

        app.state.settings = make_settings(
            radarr_url="http://radarr:7878",
            radarr_api_key="test-radarr-key",
            radarr_enabled=True,
            sonarr_url="http://sonarr:8989",
            sonarr_api_key="test-sonarr-key",
            sonarr_enabled=True,
            general=GeneralConfig(skip_unreleased=True, tracking_delay_seconds=90),
        )

        app.state.config_path = tmp_path / "triggarr.toml"
        app.state.state_path = tmp_path / "state.json"
        app.state.search_lock = asyncio.Lock()
        app.state.last_search_time = {}
        app.state.last_health_check = None

        yield app


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


# --- FONT-01: Body uses system sans-serif ---


def test_body_has_font_sans_class(client):
    """FONT-01: Body element has font-sans class for system sans-serif."""
    response = client.get("/")
    assert response.status_code == 200
    body_match = re.search(r'<body[^>]*class="([^"]*)"', response.text)
    assert body_match is not None
    body_classes = body_match.group(1)
    assert "font-sans" in body_classes
    assert "font-mono" not in body_classes
    assert "font-geist-mono" not in body_classes


# --- FONT-02: Geist Mono only on designated elements ---


def test_version_badge_uses_font_geist_mono(client):
    """FONT-02: Version badge in header uses font-geist-mono."""
    response = client.get("/")
    assert response.status_code == 200
    assert "font-geist-mono" in response.text


# --- HDR-01: Header padding ---


def test_header_has_py4_padding(client):
    """HDR-01: Header inner div uses py-4 padding."""
    response = client.get("/")
    assert response.status_code == 200
    assert "py-4" in response.text
    # Old py-3 must NOT be in the header area
    assert "py-3 flex items-center" not in response.text


# --- HDR-02: Nav links with Phosphor icons at text-[15px] ---


def test_nav_has_phosphor_icons(client):
    """HDR-02: Navigation links have Phosphor icon elements."""
    response = client.get("/")
    assert response.status_code == 200
    assert "ph ph-squares-four" in response.text      # Dashboard
    assert "ph ph-clock-counter-clockwise" in response.text  # History
    assert "ph ph-gear" in response.text                # Settings


def test_nav_links_use_text_15px(client):
    """HDR-02: Nav links use text-[15px] font size."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text-[15px]" in response.text


# --- HDR-03: Center-aligned nav with gap-6 ---


def test_nav_center_aligned_absolute(client):
    """HDR-03: Nav uses absolute centering with gap-6."""
    response = client.get("/")
    assert response.status_code == 200
    assert "gap-6 absolute left-1/2 -translate-x-1/2" in response.text


def test_header_has_w64_zones(client):
    """HDR-03/D-03: Header has w-64 fixed-width zones."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.text.count("w-64 shrink-0") >= 2


# --- HDR-04: Logout divider and sign-out icon ---


def test_logout_has_css_pipe_divider(client):
    """HDR-04: Pipe divider is a CSS element, not a text character."""
    original = dict(auth_state)
    auth_state["active"] = True
    try:
        response = client.get("/")
        assert response.status_code == 200
        assert "w-px h-4 bg-triggarr-border" in response.text
        # Old text pipe must be gone
        assert '<span class="text-triggarr-border">|</span>' not in response.text
    finally:
        auth_state.clear()
        auth_state.update(original)


def test_logout_has_sign_out_icon(client):
    """HDR-04: Logout button has ph-sign-out icon."""
    original = dict(auth_state)
    auth_state["active"] = True
    try:
        response = client.get("/")
        assert response.status_code == 200
        assert "ph ph-sign-out" in response.text
    finally:
        auth_state.clear()
        auth_state.update(original)


def test_logout_is_post_form(client):
    """Security: Logout remains a POST form for CSRF protection."""
    original = dict(auth_state)
    auth_state["active"] = True
    try:
        response = client.get("/")
        assert response.status_code == 200
        assert 'method="post"' in response.text
    finally:
        auth_state.clear()
        auth_state.update(original)


def test_logout_hover_red(client):
    """HDR-04: Logout hover transitions to red-400."""
    original = dict(auth_state)
    auth_state["active"] = True
    try:
        response = client.get("/")
        assert response.status_code == 200
        assert "hover:text-red-400" in response.text
    finally:
        auth_state.clear()
        auth_state.update(original)


# --- HDR-05: Connection status pill ---


def test_connection_pill_partial_endpoint(client):
    """HDR-05: Connection pill partial endpoint returns healthy state."""
    response = client.get("/partials/connection-pill")
    assert response.status_code == 200
    assert "Connection Stable" in response.text
    assert "dot-pulse" in response.text


def test_connection_pill_disconnected_state(test_app):
    """HDR-05/D-06: Pill shows 'Connection Issue' when instance disconnected."""
    # Set one instance to disconnected
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    client = TestClient(test_app)
    response = client.get("/partials/connection-pill")
    assert response.status_code == 200
    assert "Connection Issue" in response.text
    assert "bg-triggarr-danger" in response.text
    # Disconnected state should NOT have dot-pulse
    # Disconnected state must not have pulse animation
    assert "dot-pulse" not in response.text


def test_connection_pill_loaded_via_htmx_in_header(client):
    """HDR-05: Header right zone loads connection pill via htmx."""
    response = client.get("/")
    assert response.status_code == 200
    assert "connection-pill" in response.text
    assert 'hx-get="' in response.text and "partials/connection-pill" in response.text
    assert 'hx-trigger="load, every 30s"' in response.text


# --- Static asset existence ---


def test_phosphor_font_files_vendored():
    """Phosphor CSS and WOFF2 files exist in vendor directory."""
    assert (STATIC_DIR / "vendor" / "phosphor" / "style.css").exists()
    assert (STATIC_DIR / "vendor" / "phosphor" / "Phosphor.woff2").exists()


def test_phosphor_css_linked_in_base_html():
    """Phosphor CSS is linked in base.html head."""
    base_html = (TEMPLATES_DIR / "base.html").read_text()
    assert "vendor/phosphor" in base_html


def test_input_css_has_new_color_tokens():
    """New color tokens exist in input.css @theme block."""
    css = (STATIC_DIR / "css" / "input.css").read_text()
    assert "--color-triggarr-radarr: #f59e0b" in css
    assert "--color-triggarr-sonarr: #3b82f6" in css
    assert "--color-triggarr-danger: #ef4444" in css
    assert "--color-triggarr-primaryDark: #16a34a" in css


# --- Header structure ---


def test_header_uses_artifact_background(client):
    """Header uses bg-triggarr-bg/95 not bg-triggarr-card/80."""
    response = client.get("/")
    assert response.status_code == 200
    assert "bg-triggarr-bg/95" in response.text
    assert "bg-triggarr-card/80" not in response.text


def test_header_uses_z50(client):
    """Header uses z-50 (artifact value)."""
    response = client.get("/")
    assert response.status_code == 200
    assert "z-50" in response.text


def test_active_nav_has_bottom_bar(client):
    """Active nav link has the green bottom indicator bar."""
    response = client.get("/")
    assert response.status_code == 200
    assert "-bottom-[21px]" in response.text
    assert "bg-triggarr-green" in response.text
