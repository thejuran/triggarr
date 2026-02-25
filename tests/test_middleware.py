"""Test suite for Origin/Referer CSRF middleware.

Covers cross-origin rejection, same-origin pass-through, missing header
allowance, and non-POST method bypass.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fetcharr.web.middleware import OriginCheckMiddleware


def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with OriginCheckMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(OriginCheckMiddleware)

    @app.post("/test")
    async def post_endpoint():
        return {"status": "ok"}

    @app.get("/test")
    async def get_endpoint():
        return {"status": "ok"}

    return app


client = TestClient(_make_app())


def test_post_matching_origin_passes():
    """POST with Origin matching Host should return 200."""
    response = client.post(
        "/test",
        headers={"Origin": "http://testserver", "Host": "testserver"},
    )
    assert response.status_code == 200


def test_post_mismatched_origin_returns_403():
    """POST with Origin not matching Host should return 403."""
    response = client.post(
        "/test",
        headers={"Origin": "http://evil.com", "Host": "testserver"},
    )
    assert response.status_code == 403


def test_post_matching_referer_passes():
    """POST with Referer matching Host (no Origin) should return 200."""
    response = client.post(
        "/test",
        headers={"Referer": "http://testserver/settings", "Host": "testserver"},
    )
    assert response.status_code == 200


def test_post_mismatched_referer_returns_403():
    """POST with Referer not matching Host (no Origin) should return 403."""
    response = client.post(
        "/test",
        headers={"Referer": "http://evil.com/page", "Host": "testserver"},
    )
    assert response.status_code == 403


def test_post_no_origin_no_referer_passes():
    """POST with neither Origin nor Referer should return 200 (same-origin behavior)."""
    response = client.post("/test", headers={"Host": "testserver"})
    assert response.status_code == 200


def test_get_with_mismatched_origin_passes():
    """GET request with mismatched Origin should return 200 (non-POST passes through)."""
    response = client.get(
        "/test",
        headers={"Origin": "http://evil.com", "Host": "testserver"},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# DEBT-02: Integration test — OriginCheckMiddleware wired to real /settings route
# ---------------------------------------------------------------------------


def _make_settings_app() -> FastAPI:
    """Build a FastAPI app with router + OriginCheckMiddleware, mimicking real app wiring.

    This mirrors the registration order in fetcharr/__main__.py:
      app.add_middleware(OriginCheckMiddleware)
      app.include_router(router)
    """
    import asyncio
    import pathlib
    import tempfile
    from unittest.mock import MagicMock

    from fastapi.staticfiles import StaticFiles

    from fetcharr.web.routes import STATIC_DIR, router as fetcharr_router

    app = FastAPI()
    app.add_middleware(OriginCheckMiddleware)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(fetcharr_router)

    # Minimal app.state needed by the settings route handler
    mock_settings = MagicMock()
    mock_settings.radarr.enabled = True
    mock_settings.radarr.url = "http://radarr:7878"
    mock_settings.radarr.api_key.get_secret_value.return_value = "test-key"
    mock_settings.radarr.search_interval = 30
    mock_settings.radarr.search_missing_count = 5
    mock_settings.radarr.search_cutoff_count = 5
    mock_settings.sonarr.enabled = False
    mock_settings.sonarr.url = ""
    mock_settings.sonarr.api_key.get_secret_value.return_value = ""
    mock_settings.sonarr.search_interval = 30
    mock_settings.sonarr.search_missing_count = 5
    mock_settings.sonarr.search_cutoff_count = 5
    mock_settings.general.log_level = "info"
    mock_settings.general.hard_max_per_cycle = 0
    mock_settings.general.max_history_rows = 1000
    mock_settings.general.request_timeout = 30.0
    mock_settings.general.page_size = 50
    mock_settings.general.tracking_window_minutes = 60
    mock_settings.general.tracking_poll_seconds = 90
    app.state.settings = mock_settings
    app.state.scheduler = MagicMock()
    app.state.search_lock = asyncio.Lock()
    app.state.last_search_time = {}
    app.state.config_path = pathlib.Path(tempfile.mktemp(suffix=".toml"))
    app.state.state_path = pathlib.Path(tempfile.mktemp(suffix=".json"))

    return app


def test_settings_post_cross_origin_rejected():
    """POST /settings with mismatched Origin returns 403 (middleware wired to real route)."""
    app = _make_settings_app()
    tc = TestClient(app)
    response = tc.post(
        "/settings",
        data={"log_level": "info"},
        headers={"Origin": "http://evil.com", "Host": "testserver"},
    )
    assert response.status_code == 403, (
        f"Expected 403 for cross-origin POST to /settings, got {response.status_code}. "
        "OriginCheckMiddleware may not be wired to the router."
    )


def test_settings_post_same_origin_passes():
    """POST /settings with matching Origin passes middleware (may redirect or 303)."""
    app = _make_settings_app()
    tc = TestClient(app, raise_server_exceptions=False)
    response = tc.post(
        "/settings",
        data={"log_level": "info"},
        headers={"Origin": "http://testserver", "Host": "testserver"},
        follow_redirects=False,
    )
    # Middleware should pass; route may redirect (303) or fail on missing state — either is fine
    # What matters: NOT 403 from middleware
    assert response.status_code != 403, (
        f"POST /settings with same-origin Origin should not return 403, got {response.status_code}"
    )
