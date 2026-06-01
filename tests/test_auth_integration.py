"""Cross-cutting auth integration tests -- Phase 58.

Tests multi-step flows that span setup, login, middleware, and session management.
Verifies that all auth modules cooperate correctly end-to-end.

Traceability:
  SC-2 (setup flow) + SC-3 (login/session) + SC-5 (API key):
      test_full_setup_login_use_logout_flow
  SC-5 (API key): test_setup_then_api_key_access
  SC-3 (session lifecycle): test_password_change_invalidates_old_sessions
"""

from __future__ import annotations

import asyncio
import tomllib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from pydantic import SecretStr

from triggarr.auth import generate_session_secret, hash_password, sign_session
from triggarr.models.config import AuthConfig, GeneralConfig
from triggarr.models.config import Settings as SettingsModel
from triggarr.web.middleware import AuthMiddleware
from triggarr.web.routes import auth_state, router

# Protected route used for integration assertions. /settings only needs
# app.state.settings (no DB/scheduler), making it ideal for auth flow tests.
_PROTECTED_ROUTE = "/settings"


@pytest.fixture(autouse=True)
def _reset_auth_state():
    """Reset module-level auth_state between tests to prevent order dependency."""
    original = dict(auth_state)
    yield
    auth_state.clear()
    auth_state.update(original)


# ---------------------------------------------------------------------------
# Integration test helpers (duplicated from test_auth_routes.py -- module-level)
# ---------------------------------------------------------------------------

_TEST_PASSWORD = "testpass123"
_TEST_PASSWORD_HASH = hash_password(_TEST_PASSWORD)
_TEST_SESSION_SECRET = generate_session_secret()
_TEST_API_KEY = "a" * 32


def _configured_auth(
    method: str = "Forms",
    username: str = "admin",
    password_hash: str = _TEST_PASSWORD_HASH,
    api_key: str = _TEST_API_KEY,
    session_secret: str = _TEST_SESSION_SECRET,
) -> AuthConfig:
    """Create an AuthConfig with real credentials for integration tests."""
    return AuthConfig(
        method=method,
        username=username,
        password_hash=SecretStr(password_hash),
        api_key=SecretStr(api_key),
        session_secret=SecretStr(session_secret),
    )


def _make_route_app(auth_config: AuthConfig | None = None, config_path: Path | None = None) -> FastAPI:
    """Build a FastAPI app with real route handlers and AuthMiddleware for integration tests."""
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(router)

    # Mount static files so templates can resolve CSS links
    static_dir = Path(__file__).resolve().parent.parent / "triggarr" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    cfg = auth_config or AuthConfig()
    settings = SettingsModel.model_construct(
        general=GeneralConfig(),
        auth=cfg,
        radarr={},
        sonarr={},
        lidarr={},
    )
    app.state.settings = settings
    app.state.config_path = config_path or Path("/tmp/test-triggarr.toml")
    app.state.search_lock = asyncio.Lock()

    # Sync auth_state for template rendering
    auth_state["active"] = cfg.method in ("Forms", "Basic") and not cfg.needs_setup
    auth_state["method"] = cfg.method

    return app


# ---------------------------------------------------------------------------
# Integration tests: Multi-step flows
# ---------------------------------------------------------------------------


def test_full_setup_login_use_logout_flow(tmp_path: Path):
    """Complete flow: setup creates creds, login works, logout blocks access."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')
    app = _make_route_app(config_path=config_file)
    client = TestClient(app, follow_redirects=False)

    # Step 1: Unconfigured -> redirects to /setup
    resp = client.get(_PROTECTED_ROUTE, headers={"Accept": "text/html"})
    assert resp.status_code == 302
    assert "/setup" in resp.headers["location"]

    # Step 2: Complete setup
    resp = client.post(
        "/setup",
        data={"username": "admin", "password": "mypass123", "confirm_password": "mypass123"},
    )
    assert resp.status_code == 200
    assert "Account Created" in resp.text or "api-key" in resp.text.lower()
    session_cookie = resp.cookies.get("triggarr_session")
    assert session_cookie  # Setup auto-logs in

    # Step 3: Access protected route with session cookie from setup
    resp = client.get(_PROTECTED_ROUTE, cookies={"triggarr_session": session_cookie})
    assert resp.status_code == 200

    # Step 4: Logout
    resp = client.post("/logout", cookies={"triggarr_session": session_cookie})
    assert resp.status_code == 303
    assert "/login" in resp.headers["location"]

    # Step 5: Access denied after logout
    resp = client.get(_PROTECTED_ROUTE, headers={"Accept": "text/html"})
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]

    # Step 6: Manual login with the credentials created during setup
    resp = client.post(
        "/login",
        data={"username": "admin", "password": "mypass123"},
    )
    assert resp.status_code in (302, 303)  # redirect to dashboard
    new_cookie = resp.cookies.get("triggarr_session")
    assert new_cookie

    # Step 7: Access protected route with new session cookie
    resp = client.get(_PROTECTED_ROUTE, cookies={"triggarr_session": new_cookie})
    assert resp.status_code == 200


def test_setup_then_api_key_access(tmp_path: Path):
    """After setup, the generated API key authenticates API requests."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')
    app = _make_route_app(config_path=config_file)
    client = TestClient(app, follow_redirects=False)

    # Step 1: Complete setup
    resp = client.post(
        "/setup",
        data={"username": "admin", "password": "mypass123", "confirm_password": "mypass123"},
    )
    assert resp.status_code == 200

    # Step 2: Read the API key from the saved config
    saved_config = tomllib.loads(config_file.read_text())
    api_key = saved_config["auth"]["api_key"]
    assert api_key  # non-empty

    # Step 3: Use API key to access a protected route
    # The setup POST handler updates app.state.settings via load_settings(),
    # so the middleware will see the new API key on subsequent requests.
    resp = client.get(_PROTECTED_ROUTE, headers={"X-Api-Key": api_key})
    assert resp.status_code == 200


def test_password_change_invalidates_old_sessions(tmp_path: Path):
    """Password change rotates the session secret, so pre-change cookies are evicted.

    Reversal of prior behavior (pre-2026-05-31 this test asserted old cookies kept
    working). Changing the password is a standard way to lock out a possibly-compromised
    session, so every cookie signed with the old secret must stop validating.
    """
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')
    auth_cfg = _configured_auth()
    app = _make_route_app(auth_config=auth_cfg, config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    cookie = sign_session("admin", _TEST_SESSION_SECRET)

    # Step 1: Verify session works before password change
    resp = client.get(_PROTECTED_ROUTE, cookies={"triggarr_session": cookie})
    assert resp.status_code == 200

    # Step 2: Change password
    resp = client.post(
        "/settings/password",
        data={
            "current_password": _TEST_PASSWORD,
            "new_password": "new-password-456",
            "confirm_password": "new-password-456",
        },
        cookies={"triggarr_session": cookie},
    )
    assert resp.status_code == 200
    text_lower = resp.text.lower()
    assert "updated" in text_lower or "success" in text_lower or "changed" in text_lower

    # Step 3: The pre-change cookie is now rejected (session secret rotated).
    # Pass the stale cookie explicitly so the auto-reissued client cookie does not mask it.
    # A browser request (Accept: text/html) with an invalid cookie hits the Forms-mode
    # fallback, which redirects to /login with 302 (middleware.py step 7). Assert that
    # exact behavior rather than a broad "not 200" disjunction.
    resp = client.get(
        _PROTECTED_ROUTE,
        cookies={"triggarr_session": cookie},
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["location"]
