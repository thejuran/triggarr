"""TDD tests for _safe_next_url, _settings_to_dict, and integration tests for auth routes.

Tests cover:
- _safe_next_url: rejects absolute URLs, protocol-relative, backslash, non-slash prefix
- _settings_to_dict: includes auth section with SecretStr values extracted to plain strings
- Integration: setup flow (render, create credentials, errors, 404 after config)
- Integration: login flow (render, valid/invalid credentials, ?next=, open redirect, already-authed)
- Integration: logout (cookie clear, redirect)
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
from triggarr.models.config import AuthConfig, GeneralConfig, InstanceConfig
from triggarr.models.config import Settings as SettingsModel
from triggarr.web.middleware import AuthMiddleware
from triggarr.web.routes import _safe_next_url, _settings_to_dict, auth_state, router


@pytest.fixture(autouse=True)
def _reset_auth_state():
    """Reset module-level auth_state between tests to prevent order dependency."""
    original = dict(auth_state)
    yield
    auth_state.clear()
    auth_state.update(original)


# ---------------------------------------------------------------------------
# Integration test helpers
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
    """Create an AuthConfig with real credentials for route integration tests."""
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
# _safe_next_url tests
# ---------------------------------------------------------------------------


def test_safe_next_url_none_returns_root():
    """_safe_next_url(None) returns '/'."""
    assert _safe_next_url(None) == "/"


def test_safe_next_url_empty_returns_root():
    """_safe_next_url('') returns '/'."""
    assert _safe_next_url("") == "/"


def test_safe_next_url_valid_relative():
    """_safe_next_url('/settings') returns '/settings'."""
    assert _safe_next_url("/settings") == "/settings"


def test_safe_next_url_valid_relative_with_query():
    """_safe_next_url('/history?page=2') returns '/history?page=2'."""
    assert _safe_next_url("/history?page=2") == "/history?page=2"


def test_safe_next_url_rejects_http():
    """_safe_next_url('http://evil.com') returns '/'."""
    assert _safe_next_url("http://evil.com") == "/"


def test_safe_next_url_rejects_https():
    """_safe_next_url('https://evil.com') returns '/'."""
    assert _safe_next_url("https://evil.com") == "/"


def test_safe_next_url_rejects_protocol_relative():
    """_safe_next_url('//evil.com') returns '/'."""
    assert _safe_next_url("//evil.com") == "/"


def test_safe_next_url_rejects_backslash():
    r"""_safe_next_url('/foo\\bar') returns '/'."""
    assert _safe_next_url("/foo\\bar") == "/"


def test_safe_next_url_rejects_no_slash_prefix():
    """_safe_next_url('settings') returns '/'."""
    assert _safe_next_url("settings") == "/"


# ---------------------------------------------------------------------------
# _settings_to_dict auth extension tests
# ---------------------------------------------------------------------------


def _make_settings(**overrides) -> SettingsModel:
    """Build a Settings object with sensible defaults for testing.

    Uses model_construct to bypass TOML file source and validators.
    """
    defaults = {
        "general": GeneralConfig(),
        "auth": AuthConfig(),
        "radarr": {},
        "sonarr": {},
        "lidarr": {},
    }
    defaults.update(overrides)
    return SettingsModel.model_construct(**defaults)


def test_settings_to_dict_includes_auth_section():
    """_settings_to_dict includes auth section with plain string values from SecretStr."""
    settings = _make_settings(
        auth=AuthConfig(
            method="Forms",
            username="admin",
            password_hash=SecretStr("$2b$12$hashvalue"),
            api_key=SecretStr("abc123"),
            session_secret=SecretStr("secret456"),
        )
    )
    result = _settings_to_dict(settings)
    assert "auth" in result
    auth = result["auth"]
    assert auth["method"] == "Forms"
    assert auth["username"] == "admin"
    assert auth["password_hash"] == "$2b$12$hashvalue"
    assert auth["api_key"] == "abc123"
    assert auth["session_secret"] == "secret456"
    # Ensure plain strings, not SecretStr objects
    assert isinstance(auth["password_hash"], str)
    assert isinstance(auth["api_key"], str)
    assert isinstance(auth["session_secret"], str)


def test_settings_to_dict_auth_default_unconfigured():
    """Default AuthConfig produces auth section with empty string secret values."""
    settings = _make_settings()
    result = _settings_to_dict(settings)
    assert "auth" in result
    auth = result["auth"]
    assert auth["method"] == "Forms"
    assert auth["username"] == ""
    assert auth["password_hash"] == ""
    assert auth["api_key"] == ""
    assert auth["session_secret"] == ""


def test_settings_to_dict_preserves_existing_behavior():
    """_settings_to_dict still correctly serializes radarr instances with plain-string api_key."""
    settings = _make_settings(
        radarr={
            "4K Radarr": InstanceConfig(
                url="http://localhost:7878",
                api_key=SecretStr("radarr-key-123"),
                enabled=True,
            )
        }
    )
    result = _settings_to_dict(settings)
    assert "radarr" in result
    assert "4K Radarr" in result["radarr"]
    inst = result["radarr"]["4K Radarr"]
    assert inst["api_key"] == "radarr-key-123"
    assert isinstance(inst["api_key"], str)


# ---------------------------------------------------------------------------
# Integration tests: Setup routes
# ---------------------------------------------------------------------------


def test_setup_page_renders_when_needs_setup():
    """GET /setup with unconfigured auth returns 200 with welcome message."""
    app = _make_route_app()  # default AuthConfig -> needs_setup=True
    client = TestClient(app, follow_redirects=False)
    response = client.get("/setup")
    assert response.status_code == 200
    assert "Welcome to Triggarr" in response.text


def test_setup_page_returns_404_when_configured():
    """GET /setup with configured auth returns 404 (SETUP-04)."""
    app = _make_route_app(auth_config=_configured_auth())
    client = TestClient(app, follow_redirects=False)
    response = client.get("/setup")
    assert response.status_code == 404


def test_setup_post_creates_credentials(tmp_path: Path):
    """POST /setup with valid credentials creates account and shows API key."""
    # Create a minimal initial TOML config file
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text("[general]\nlog_level = \"info\"\n")

    app = _make_route_app(config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    response = client.post(
        "/setup",
        data={"username": "admin", "password": "test123", "confirm_password": "test123"},
    )
    assert response.status_code == 200
    assert "Account Created" in response.text
    assert "api-key-display" in response.text

    # Verify TOML file was updated with auth section
    with open(config_file, "rb") as f:
        toml_data = tomllib.load(f)
    assert "auth" in toml_data
    assert toml_data["auth"]["username"] == "admin"


def test_setup_post_password_mismatch_shows_error(tmp_path: Path):
    """POST /setup with mismatched passwords shows error."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text("[general]\nlog_level = \"info\"\n")

    app = _make_route_app(config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    response = client.post(
        "/setup",
        data={"username": "admin", "password": "test123", "confirm_password": "different"},
    )
    assert response.status_code == 200
    assert "Passwords do not match" in response.text


def test_setup_post_empty_password_shows_error(tmp_path: Path):
    """POST /setup with empty password shows error."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text("[general]\nlog_level = \"info\"\n")

    app = _make_route_app(config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    response = client.post(
        "/setup",
        data={"username": "admin", "password": "", "confirm_password": ""},
    )
    assert response.status_code == 200
    assert "Password is required" in response.text


def test_setup_post_sets_session_cookie(tmp_path: Path):
    """POST /setup with valid credentials sets triggarr_session cookie."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text("[general]\nlog_level = \"info\"\n")

    app = _make_route_app(config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    response = client.post(
        "/setup",
        data={"username": "admin", "password": "test123", "confirm_password": "test123"},
    )
    assert response.status_code == 200
    # Check Set-Cookie header contains triggarr_session
    set_cookie = response.headers.get("set-cookie", "")
    assert "triggarr_session" in set_cookie


def test_setup_post_returns_404_when_configured():
    """POST /setup with configured auth returns 404."""
    app = _make_route_app(auth_config=_configured_auth())
    client = TestClient(app, follow_redirects=False)
    response = client.post(
        "/setup",
        data={"username": "admin", "password": "test123", "confirm_password": "test123"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Integration tests: Login routes
# ---------------------------------------------------------------------------


def test_login_page_renders():
    """GET /login with configured auth returns 200 with Sign In."""
    app = _make_route_app(auth_config=_configured_auth())
    client = TestClient(app, follow_redirects=False)
    response = client.get("/login")
    assert response.status_code == 200
    assert "Sign In" in response.text


def test_login_page_redirects_when_authenticated():
    """GET /login with valid session cookie returns 302 redirect to / (D-06)."""
    auth = _configured_auth()
    app = _make_route_app(auth_config=auth)
    client = TestClient(app, follow_redirects=False)
    cookie = sign_session("admin", _TEST_SESSION_SECRET)
    response = client.get("/login", cookies={"triggarr_session": cookie})
    assert response.status_code == 302
    # Should redirect to dashboard (root)
    location = response.headers["location"]
    assert location.endswith("/")


def test_login_post_valid_credentials_redirects():
    """POST /login with correct credentials returns 303 with session cookie."""
    app = _make_route_app(auth_config=_configured_auth())
    client = TestClient(app, follow_redirects=False)
    response = client.post(
        "/login",
        data={"username": "admin", "password": _TEST_PASSWORD, "next": ""},
    )
    assert response.status_code == 303
    set_cookie = response.headers.get("set-cookie", "")
    assert "triggarr_session" in set_cookie


def test_login_post_invalid_credentials_shows_error():
    """POST /login with wrong password shows generic error with username pre-filled (D-04)."""
    app = _make_route_app(auth_config=_configured_auth())
    client = TestClient(app, follow_redirects=False)
    response = client.post(
        "/login",
        data={"username": "admin", "password": "wrongpassword", "next": ""},
    )
    assert response.status_code == 200
    assert "Invalid username or password" in response.text
    # Username should be pre-filled in the form
    assert 'value="admin"' in response.text


def test_login_post_respects_next_param():
    """POST /login with valid credentials and next=/settings redirects to /settings (D-05)."""
    app = _make_route_app(auth_config=_configured_auth())
    client = TestClient(app, follow_redirects=False)
    response = client.post(
        "/login",
        data={"username": "admin", "password": _TEST_PASSWORD, "next": "/settings"},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/settings"


def test_login_post_rejects_open_redirect_next():
    """POST /login with next=http://evil.com redirects to / not evil.com (T-56-14)."""
    app = _make_route_app(auth_config=_configured_auth())
    client = TestClient(app, follow_redirects=False)
    response = client.post(
        "/login",
        data={"username": "admin", "password": _TEST_PASSWORD, "next": "http://evil.com"},
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "evil.com" not in location
    # Should redirect to safe fallback
    assert location == "/"


# ---------------------------------------------------------------------------
# Integration tests: Logout route
# ---------------------------------------------------------------------------


def test_logout_clears_cookie_and_redirects():
    """POST /logout returns 303 redirect to /login with cookie deletion."""
    app = _make_route_app(auth_config=_configured_auth())
    client = TestClient(app, follow_redirects=False)
    # Login first to have a session
    cookie = sign_session("admin", _TEST_SESSION_SECRET)
    response = client.post("/logout", cookies={"triggarr_session": cookie})
    assert response.status_code == 303
    location = response.headers["location"]
    assert "/login" in location
    # Cookie should be deleted (max-age=0 or expires in past)
    set_cookie = response.headers.get("set-cookie", "")
    assert "triggarr_session" in set_cookie
    # Deletion indicated by max-age=0 or empty value
    assert 'max-age=0' in set_cookie.lower() or '="";' in set_cookie


# ---------------------------------------------------------------------------
# Integration tests: Security settings endpoints (57-01)
# ---------------------------------------------------------------------------


def test_change_password_success(tmp_path: Path):
    """POST /settings/password with valid credentials updates password and returns success partial."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')

    auth_cfg = _configured_auth()
    app = _make_route_app(auth_config=auth_cfg, config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    cookie = sign_session("admin", _TEST_SESSION_SECRET)

    response = client.post(
        "/settings/password",
        data={
            "current_password": _TEST_PASSWORD,
            "new_password": "newpass456",
            "confirm_password": "newpass456",
        },
        cookies={"triggarr_session": cookie},
    )
    assert response.status_code == 200
    assert "Password updated" in response.text
    # D-05: password inputs should NOT be pre-filled after success
    assert 'value="newpass456"' not in response.text
    assert 'value="' + _TEST_PASSWORD + '"' not in response.text


def test_change_password_wrong_current(tmp_path: Path):
    """POST /settings/password with wrong current password returns error."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')

    auth_cfg = _configured_auth()
    app = _make_route_app(auth_config=auth_cfg, config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    cookie = sign_session("admin", _TEST_SESSION_SECRET)

    response = client.post(
        "/settings/password",
        data={
            "current_password": "wrongpassword",
            "new_password": "newpass456",
            "confirm_password": "newpass456",
        },
        cookies={"triggarr_session": cookie},
    )
    assert response.status_code == 200
    assert "Current password is incorrect" in response.text


def test_change_password_mismatch(tmp_path: Path):
    """POST /settings/password with mismatched new/confirm returns error."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')

    auth_cfg = _configured_auth()
    app = _make_route_app(auth_config=auth_cfg, config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    cookie = sign_session("admin", _TEST_SESSION_SECRET)

    response = client.post(
        "/settings/password",
        data={
            "current_password": _TEST_PASSWORD,
            "new_password": "newpass456",
            "confirm_password": "different789",
        },
        cookies={"triggarr_session": cookie},
    )
    assert response.status_code == 200
    assert "Passwords do not match" in response.text


def test_change_password_empty_new(tmp_path: Path):
    """POST /settings/password with empty new password returns error."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')

    auth_cfg = _configured_auth()
    app = _make_route_app(auth_config=auth_cfg, config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    cookie = sign_session("admin", _TEST_SESSION_SECRET)

    response = client.post(
        "/settings/password",
        data={
            "current_password": _TEST_PASSWORD,
            "new_password": "",
            "confirm_password": "",
        },
        cookies={"triggarr_session": cookie},
    )
    assert response.status_code == 200
    assert "New password is required" in response.text


def test_security_save_method_basic(tmp_path: Path):
    """POST /settings/security with method=Basic updates config and redirects."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')

    auth_cfg = _configured_auth()
    app = _make_route_app(auth_config=auth_cfg, config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    cookie = sign_session("admin", _TEST_SESSION_SECRET)

    response = client.post(
        "/settings/security",
        data={"auth_method": "Basic"},
        cookies={"triggarr_session": cookie},
    )
    assert response.status_code == 303

    # Verify config was updated
    with open(config_file, "rb") as f:
        toml_data = tomllib.load(f)
    assert toml_data["auth"]["method"] == "Basic"


def test_security_save_method_external(tmp_path: Path):
    """POST /settings/security with method=External updates config and redirects."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')

    auth_cfg = _configured_auth()
    app = _make_route_app(auth_config=auth_cfg, config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    cookie = sign_session("admin", _TEST_SESSION_SECRET)

    response = client.post(
        "/settings/security",
        data={"auth_method": "External"},
        cookies={"triggarr_session": cookie},
    )
    assert response.status_code == 303


def test_security_save_rejects_disabled(tmp_path: Path):
    """POST /settings/security with method=Disabled is rejected; config unchanged."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n[auth]\nmethod = "Forms"\n')

    auth_cfg = _configured_auth()
    app = _make_route_app(auth_config=auth_cfg, config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    cookie = sign_session("admin", _TEST_SESSION_SECRET)

    response = client.post(
        "/settings/security",
        data={"auth_method": "Disabled"},
        cookies={"triggarr_session": cookie},
    )
    assert response.status_code == 303

    # Config should NOT have changed to Disabled
    with open(config_file, "rb") as f:
        toml_data = tomllib.load(f)
    assert toml_data["auth"]["method"] == "Forms"


def test_security_save_rejects_invalid(tmp_path: Path):
    """POST /settings/security with invalid method is rejected; config unchanged."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n[auth]\nmethod = "Forms"\n')

    auth_cfg = _configured_auth()
    app = _make_route_app(auth_config=auth_cfg, config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    cookie = sign_session("admin", _TEST_SESSION_SECRET)

    response = client.post(
        "/settings/security",
        data={"auth_method": "InvalidXYZ"},
        cookies={"triggarr_session": cookie},
    )
    assert response.status_code == 303

    # Config should NOT have changed
    with open(config_file, "rb") as f:
        toml_data = tomllib.load(f)
    assert toml_data["auth"]["method"] == "Forms"


def test_regenerate_api_key(tmp_path: Path):
    """POST /settings/api-key/regenerate returns new key that differs from original."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')

    auth_cfg = _configured_auth()
    app = _make_route_app(auth_config=auth_cfg, config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    cookie = sign_session("admin", _TEST_SESSION_SECRET)

    response = client.post(
        "/settings/api-key/regenerate",
        cookies={"triggarr_session": cookie},
    )
    assert response.status_code == 200
    assert "Key regenerated" in response.text
    # New key should be 32-char hex and differ from original
    import re as _re

    hex_match = _re.search(r"[0-9a-f]{32}", response.text)
    assert hex_match is not None, "Response should contain a 32-char hex key"
    new_key = hex_match.group()
    assert new_key != _TEST_API_KEY


def test_settings_page_auth_context(tmp_path: Path):
    """GET /settings includes auth method and username in response."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')

    auth_cfg = _configured_auth(method="Forms", username="admin")
    app = _make_route_app(auth_config=auth_cfg, config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    cookie = sign_session("admin", _TEST_SESSION_SECRET)

    response = client.get("/settings", cookies={"triggarr_session": cookie})
    assert response.status_code == 200
    # Auth context should be present -- check for security section elements
    assert "Forms" in response.text
    assert "password-section" in response.text
    assert "apikey-section" in response.text


def test_settings_page_disabled_banner(tmp_path: Path):
    """GET /settings with method=Disabled includes warning banner (SET-04)."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text('[general]\nlog_level = "info"\n')

    auth_cfg = _configured_auth(method="Disabled")
    app = _make_route_app(auth_config=auth_cfg, config_path=config_file)
    client = TestClient(app, follow_redirects=False)
    # With Disabled auth, middleware should let request through without cookie
    response = client.get("/settings")
    assert response.status_code == 200
    # Should contain warning banner text about disabled auth
    text_lower = response.text.lower()
    assert "disabled" in text_lower or "authentication" in text_lower
