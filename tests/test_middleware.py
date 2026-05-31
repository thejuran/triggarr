"""Test suite for Origin/Referer CSRF middleware.

Covers cross-origin rejection, same-origin pass-through, missing header
allowance, and non-POST method bypass.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from triggarr.web.middleware import OriginCheckMiddleware, SecurityHeadersMiddleware


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
# CSRF scenario tests — ROADMAP Phase 67 named cases (Plan 67-03)
# ---------------------------------------------------------------------------


def test_post_missing_origin_with_matching_referer_passes():
    """POST with no Origin but matching Referer should return 200.

    When Origin is absent, the middleware falls through to the Referer branch.
    A Referer whose netloc matches the Host is permitted (same-origin behavior).
    """
    response = client.post(
        "/test",
        headers={"Referer": "http://testserver/page", "Host": "testserver"},
    )
    assert response.status_code == 200


def test_post_missing_referer_with_matching_origin_passes():
    """POST with matching Origin but no Referer should return 200.

    Browsers do not always send Referer. When Origin matches Host, the Referer
    branch is never evaluated; the request is allowed.
    """
    response = client.post(
        "/test",
        headers={"Origin": "http://testserver", "Host": "testserver"},
    )
    assert response.status_code == 200


def test_post_scheme_mismatch_is_allowed():
    """POST with https Origin vs http Host (same netloc) should return 200.

    The middleware compares urlparse(origin).netloc against the raw Host header.
    urlparse strips the scheme, so 'https://testserver' yields netloc 'testserver',
    which equals Host 'testserver' — the check passes.

    This PINS the current ALLOW behavior per D-10. In Triggarr's single-origin
    deployment model this is NOT a security bypass: an attacker cannot cause a
    browser to emit a same-host Origin under a scheme they control.

    Do NOT change this test to assert 403 — scheme comparison is intentionally
    absent from OriginCheckMiddleware (D-10).
    """
    response = client.post(
        "/test",
        headers={"Origin": "https://testserver", "Host": "testserver"},
    )
    assert response.status_code == 200


def test_post_suffix_spoof_returns_403():
    """POST with a suffix-spoofed Origin (testserver.evil.com) should return 403.

    urlparse('https://testserver.evil.com').netloc == 'testserver.evil.com', which
    does not equal Host 'testserver'. Regression-locks the netloc-equality guard
    against suffix-spoof attempts (D-11).
    """
    response = client.post(
        "/test",
        headers={"Origin": "https://testserver.evil.com", "Host": "testserver"},
    )
    assert response.status_code == 403


def test_post_port_mismatch_returns_403():
    """POST with a port-appended Origin (testserver:8080) should return 403.

    urlparse('http://testserver:8080').netloc == 'testserver:8080', which does not
    equal Host 'testserver'. Regression-locks the netloc-equality guard against
    port-mismatch attempts (D-11).
    """
    response = client.post(
        "/test",
        headers={"Origin": "http://testserver:8080", "Host": "testserver"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# DEBT-02: Integration test — OriginCheckMiddleware wired to real /settings route
# ---------------------------------------------------------------------------


def _make_settings_app() -> FastAPI:
    """Build a FastAPI app with router + OriginCheckMiddleware, mimicking real app wiring.

    This mirrors the registration order in triggarr/__main__.py:
      app.add_middleware(OriginCheckMiddleware)
      app.include_router(router)
    """
    import asyncio
    import pathlib
    import tempfile
    from unittest.mock import MagicMock

    from fastapi.staticfiles import StaticFiles

    from triggarr.web.routes import STATIC_DIR
    from triggarr.web.routes import router as triggarr_router

    app = FastAPI()
    app.add_middleware(OriginCheckMiddleware)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(triggarr_router)

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
    mock_settings.general.tracking_delay_seconds = 90
    app.state.settings = mock_settings
    app.state.scheduler = MagicMock()
    app.state.search_lock = asyncio.Lock()
    app.state.last_search_time = {}
    app.state.config_path = pathlib.Path(tempfile.mkdtemp()) / "config.toml"
    app.state.state_path = pathlib.Path(tempfile.mkdtemp()) / "state.json"

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


# ---------------------------------------------------------------------------
# SecurityHeadersMiddleware tests (Phase 59 Plan 03, D-07/D-08/D-09)
# ---------------------------------------------------------------------------


def _make_security_headers_app() -> FastAPI:
    """Build a minimal FastAPI app with SecurityHeadersMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    return app


def test_security_headers_csp_present():
    """Response includes Content-Security-Policy header with correct directives.

    Updated 2026-05-26 (SEC-01 / 66-05): script-src now contains a per-request
    nonce instead of 'unsafe-inline'. Full-string equality is no longer
    appropriate because the nonce varies per request; switch to directive-level
    substring checks. D-01 drops 'unsafe-inline' from script-src; D-04 keeps
    'unsafe-inline' on style-src.
    """
    client = TestClient(_make_security_headers_app())
    response = client.get("/test")
    assert response.status_code == 200
    csp = response.headers["Content-Security-Policy"]

    # All directives present (substring-level)
    assert "default-src 'self'" in csp
    assert "script-src 'self' 'nonce-" in csp, "D-02: script-src must carry a per-request nonce"
    assert "style-src 'self' 'unsafe-inline'" in csp, "D-04: style-src retains unsafe-inline"
    assert "img-src 'self' data:" in csp
    assert "connect-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp

    # D-01: 'unsafe-inline' must NOT be in the script-src directive specifically.
    # Slice on `;` to isolate script-src so style-src's unsafe-inline doesn't
    # false-positive the negative check.
    script_src_segment = csp.split("script-src")[1].split(";")[0]
    assert "'unsafe-inline'" not in script_src_segment, "D-01: 'unsafe-inline' dropped from script-src"


def test_csp_nonce_changes_per_request():
    """SEC-01 D-02 regression guard: two consecutive requests receive two different nonces.

    Without this, an accidental caching of the nonce (e.g. as a Jinja `globals` entry)
    would silently make every page share the same value -- defeating the per-request
    contract.
    """
    client = TestClient(_make_security_headers_app())
    r1 = client.get("/test")
    r2 = client.get("/test")
    import re
    m1 = re.search(r"'nonce-([A-Za-z0-9_-]+)'", r1.headers["Content-Security-Policy"])
    m2 = re.search(r"'nonce-([A-Za-z0-9_-]+)'", r2.headers["Content-Security-Policy"])
    assert m1 and m2, "both responses must carry a nonce in script-src"
    assert m1.group(1) != m2.group(1), "two consecutive requests must produce two different nonces"


def test_security_headers_x_frame_options_deny():
    """X-Frame-Options is DENY (not SAMEORIGIN)."""
    client = TestClient(_make_security_headers_app())
    response = client.get("/test")
    assert response.headers["X-Frame-Options"] == "DENY"


def test_security_headers_existing_headers_unchanged():
    """X-Content-Type-Options and Referrer-Policy remain correct."""
    client = TestClient(_make_security_headers_app())
    response = client.get("/test")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "same-origin"
