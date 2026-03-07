"""Test suite for Origin/Referer CSRF middleware.

Covers cross-origin rejection, same-origin pass-through, missing header
allowance, and non-POST method bypass.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from triggarr.web.middleware import OriginCheckMiddleware


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
