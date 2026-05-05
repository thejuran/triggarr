"""AuthMiddleware tests -- includes Phase 58 gap-fill.

Traceability:
  SC-1 (middleware enforcement): test_health_no_auth, test_health_returns_ok_body,
      test_unauth_browser_redirect_includes_next_deep_path
  SC-3 (session lifecycle): test_wrong_secret_cookie_rejected_by_middleware,
      test_expired_cookie_rejected_by_middleware
  SC-4 (auth modes): test_forms_to_basic_transition_session_still_valid,
      test_any_to_disabled_transition_passes_through,
      test_disabled_to_forms_transition_requires_login,
      test_api_key_works_in_basic_mode, test_api_key_works_in_external_mode,
      test_disabled_mode_logs_warning
  SC-5 (API key): test_missing_api_key_api_returns_401_json,
      test_empty_api_key_does_not_pass, test_whitespace_api_key_does_not_pass,
      test_invalid_api_key_returns_401_json_not_redirect
"""

from __future__ import annotations

import base64
import time
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from triggarr.auth import generate_session_secret, hash_password, sign_session
from triggarr.models.config import AuthConfig
from triggarr.web.middleware import AuthMiddleware


def _make_auth_app(auth_config: AuthConfig | None = None) -> FastAPI:
    """Build a minimal FastAPI app with AuthMiddleware for testing."""
    app = FastAPI()
    app.add_middleware(AuthMiddleware)

    settings = MagicMock()
    settings.auth = auth_config or AuthConfig()
    app.state.settings = settings

    @app.get("/")
    async def index():
        return {"page": "home"}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/static/css/output.css")
    async def static_css():
        return {"file": "css"}

    @app.get("/login")
    async def login():
        return {"page": "login"}

    @app.get("/setup")
    async def setup():
        return {"page": "setup"}

    @app.get("/settings")
    async def settings_page():
        return {"page": "settings"}

    return app


# ---------------------------------------------------------------------------
# Fixtures: reusable auth configs
# ---------------------------------------------------------------------------

_SESSION_SECRET = generate_session_secret()
_PASSWORD = "test-password-123"
_PASSWORD_HASH = hash_password(_PASSWORD)
_API_KEY = "abcdef1234567890abcdef1234567890"


def _configured_auth(
    method: str = "Forms",
    username: str = "admin",
    password_hash: str = _PASSWORD_HASH,
    api_key: str = _API_KEY,
    session_secret: str = _SESSION_SECRET,
) -> AuthConfig:
    """Create an AuthConfig with real credentials for testing."""
    return AuthConfig(
        method=method,
        username=username,
        password_hash=SecretStr(password_hash),
        api_key=SecretStr(api_key),
        session_secret=SecretStr(session_secret),
    )


def _valid_session_cookie() -> str:
    """Generate a valid signed session cookie value."""
    return sign_session("admin", _SESSION_SECRET)


def _basic_auth_header(username: str = "admin", password: str = _PASSWORD) -> str:
    """Generate a Basic auth Authorization header value."""
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {encoded}"


def _set_cookie_has_secure_attribute(set_cookie: str) -> bool:
    """Return True when Set-Cookie includes Secure as an attribute."""
    return "secure" in {part.strip().lower() for part in set_cookie.split(";")[1:]}


# ---------------------------------------------------------------------------
# Exempt path tests
# ---------------------------------------------------------------------------


def test_health_no_auth():
    """GET /health passes through without authentication (exempt path)."""
    client = TestClient(_make_auth_app())
    response = client.get("/health")
    assert response.status_code == 200


def test_static_no_auth():
    """GET /static/css/output.css passes through without authentication (exempt path)."""
    client = TestClient(_make_auth_app())
    response = client.get("/static/css/output.css")
    assert response.status_code == 200


def test_login_no_auth():
    """GET /login passes through without authentication (exempt path)."""
    client = TestClient(_make_auth_app())
    response = client.get("/login")
    assert response.status_code == 200


def test_setup_no_auth():
    """GET /setup passes through without authentication (exempt path)."""
    client = TestClient(_make_auth_app())
    response = client.get("/setup")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Needs-setup tests
# ---------------------------------------------------------------------------


def test_needs_setup_browser_redirects_to_setup():
    """When needs_setup is true, browser requests redirect to /setup."""
    # Default AuthConfig has empty username -> needs_setup is True
    client = TestClient(_make_auth_app(), follow_redirects=False)
    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 302
    assert response.headers["location"] == "/setup"


def test_needs_setup_api_returns_401_with_setup_url():
    """When needs_setup is true, API requests get 401 with setup_url."""
    client = TestClient(_make_auth_app())
    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Setup required"
    assert data["setup_url"] == "/setup"


# ---------------------------------------------------------------------------
# Disabled mode tests
# ---------------------------------------------------------------------------


def test_disabled_mode_passes_through():
    """When method is Disabled, all requests pass through unconditionally."""
    auth = _configured_auth(method="Disabled")
    client = TestClient(_make_auth_app(auth))
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"page": "home"}


# ---------------------------------------------------------------------------
# External mode tests
# ---------------------------------------------------------------------------


def test_external_mode_passes_through():
    """When method is External, all requests pass through unconditionally."""
    auth = _configured_auth(method="External")
    client = TestClient(_make_auth_app(auth))
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"page": "home"}


# ---------------------------------------------------------------------------
# Session cookie tests
# ---------------------------------------------------------------------------


def test_valid_session_cookie_passes_through():
    """Request with valid session cookie passes through regardless of method."""
    auth = _configured_auth()
    client = TestClient(_make_auth_app(auth))
    cookie = _valid_session_cookie()
    response = client.get("/", cookies={"triggarr_session": cookie})
    assert response.status_code == 200
    assert response.json() == {"page": "home"}


# ---------------------------------------------------------------------------
# API key tests
# ---------------------------------------------------------------------------


def test_valid_api_key_passes_through():
    """Request with valid X-Api-Key header passes through."""
    auth = _configured_auth()
    client = TestClient(_make_auth_app(auth))
    response = client.get("/", headers={"X-Api-Key": _API_KEY})
    assert response.status_code == 200
    assert response.json() == {"page": "home"}


def test_invalid_api_key_does_not_pass():
    """Request with invalid X-Api-Key header does not get 200."""
    auth = _configured_auth()
    client = TestClient(_make_auth_app(auth), follow_redirects=False)
    response = client.get("/", headers={"X-Api-Key": "wrong-key", "Accept": "text/html"})
    assert response.status_code != 200


# ---------------------------------------------------------------------------
# Basic auth tests
# ---------------------------------------------------------------------------


def test_basic_auth_valid_credentials_passes():
    """Basic mode with valid Authorization header returns 200."""
    auth = _configured_auth(method="Basic")
    client = TestClient(_make_auth_app(auth))
    response = client.get("/", headers={"Authorization": _basic_auth_header()})
    assert response.status_code == 200
    assert response.json() == {"page": "home"}


def test_basic_auth_valid_sets_session_cookie():
    """Basic mode with valid credentials sets triggarr_session cookie."""
    auth = _configured_auth(method="Basic")
    client = TestClient(_make_auth_app(auth))
    response = client.get("/", headers={"Authorization": _basic_auth_header()})
    assert response.status_code == 200
    assert "triggarr_session" in response.cookies


def test_basic_auth_ignores_spoofed_forwarded_proto_for_secure_cookie():
    """HTTP Basic auth with spoofed X-Forwarded-Proto must not set Secure."""
    auth = _configured_auth(method="Basic")
    client = TestClient(_make_auth_app(auth))
    response = client.get(
        "/",
        headers={"Authorization": _basic_auth_header(), "X-Forwarded-Proto": "https"},
    )
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "triggarr_session" in set_cookie
    assert not _set_cookie_has_secure_attribute(set_cookie)


def test_basic_auth_https_sets_secure_session_cookie():
    """HTTPS Basic auth sets a Secure session cookie."""
    auth = _configured_auth(method="Basic")
    client = TestClient(_make_auth_app(auth), base_url="https://testserver")
    response = client.get("/", headers={"Authorization": _basic_auth_header()})
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "triggarr_session" in set_cookie
    assert _set_cookie_has_secure_attribute(set_cookie)


def test_basic_auth_missing_authorization_returns_401():
    """Basic mode with no Authorization header returns 401 with WWW-Authenticate."""
    auth = _configured_auth(method="Basic")
    client = TestClient(_make_auth_app(auth))
    response = client.get("/")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == 'Basic realm="Triggarr"'


def test_basic_auth_invalid_credentials_returns_401():
    """Basic mode with wrong password returns 401 with WWW-Authenticate."""
    auth = _configured_auth(method="Basic")
    client = TestClient(_make_auth_app(auth))
    response = client.get("/", headers={"Authorization": _basic_auth_header(password="wrong")})
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == 'Basic realm="Triggarr"'


def test_basic_auth_wrong_username_returns_401():
    """Basic mode with wrong username returns 401 with WWW-Authenticate."""
    auth = _configured_auth(method="Basic")
    client = TestClient(_make_auth_app(auth))
    response = client.get("/", headers={"Authorization": _basic_auth_header(username="notadmin")})
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == 'Basic realm="Triggarr"'


def test_basic_auth_malformed_header_returns_401():
    """Basic mode with malformed Authorization header returns 401 (not 500)."""
    auth = _configured_auth(method="Basic")
    client = TestClient(_make_auth_app(auth))
    # Invalid base64
    response = client.get("/", headers={"Authorization": "Basic !!!not-base64!!!"})
    assert response.status_code == 401


def test_basic_auth_missing_colon_returns_401():
    """Basic mode with base64 value missing colon separator returns 401."""
    auth = _configured_auth(method="Basic")
    client = TestClient(_make_auth_app(auth))
    encoded = base64.b64encode(b"nocolon").decode()
    response = client.get("/", headers={"Authorization": f"Basic {encoded}"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Fallback (Forms mode, no valid auth) tests
# ---------------------------------------------------------------------------


def test_unauth_browser_redirects_to_login():
    """Unauthenticated browser request to protected route gets 302 to /login."""
    auth = _configured_auth()
    client = TestClient(_make_auth_app(auth), follow_redirects=False)
    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 302
    assert response.headers["location"] == "/login?next=/"


def test_unauth_api_returns_401():
    """Unauthenticated API request to protected route gets 401 JSON."""
    auth = _configured_auth()
    client = TestClient(_make_auth_app(auth))
    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


# ---------------------------------------------------------------------------
# Edge case: session cookie works even in Basic mode
# ---------------------------------------------------------------------------


def test_session_cookie_works_in_basic_mode():
    """Valid session cookie passes through even when method is Basic."""
    auth = _configured_auth(method="Basic")
    client = TestClient(_make_auth_app(auth))
    cookie = _valid_session_cookie()
    response = client.get("/", cookies={"triggarr_session": cookie})
    assert response.status_code == 200
    assert response.json() == {"page": "home"}


# ---------------------------------------------------------------------------
# Phase 58 gap-fill: SC-1 additional tests
# ---------------------------------------------------------------------------


def test_health_returns_ok_body():
    """GET /health returns JSON body {"status": "ok"} (not just 200 status)."""
    client = TestClient(_make_auth_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unauth_browser_redirect_includes_next_deep_path():
    """Unauthenticated browser redirect preserves deeper paths like /settings."""
    auth = _configured_auth()
    client = TestClient(_make_auth_app(auth), follow_redirects=False)
    response = client.get("/settings", headers={"Accept": "text/html"})
    assert response.status_code == 302
    assert response.headers["location"] == "/login?next=/settings"


# ---------------------------------------------------------------------------
# Phase 58 gap-fill: SC-3 session edge cases at middleware level
# ---------------------------------------------------------------------------


def test_wrong_secret_cookie_rejected_by_middleware():
    """Cookie signed with a different secret is rejected at the middleware level (D-07)."""
    different_secret = generate_session_secret()
    auth = _configured_auth()
    client = TestClient(_make_auth_app(auth), follow_redirects=False)
    wrong_cookie = sign_session("admin", different_secret)
    response = client.get("/", cookies={"triggarr_session": wrong_cookie}, headers={"Accept": "text/html"})
    assert response.status_code == 302
    assert "/login" in response.headers["location"]


def test_expired_cookie_rejected_by_middleware():
    """Expired session cookie is rejected at the middleware level."""
    auth = _configured_auth()
    cookie = _valid_session_cookie()

    app = _make_auth_app(auth)
    client = TestClient(app, follow_redirects=False)
    # Patch time.time used by itsdangerous during unsign to simulate 31 days elapsed
    with patch("time.time", return_value=time.time() + 31 * 24 * 60 * 60):
        response = client.get("/", cookies={"triggarr_session": cookie}, headers={"Accept": "text/html"})
    assert response.status_code == 302
    assert "/login" in response.headers["location"]


# ---------------------------------------------------------------------------
# Phase 58 gap-fill: SC-4 auth mode transitions (D-10)
# ---------------------------------------------------------------------------


def test_forms_to_basic_transition_session_still_valid():
    """Session cookie created in Forms mode still authenticates in Basic mode."""
    cookie = _valid_session_cookie()
    auth = _configured_auth(method="Basic")
    client = TestClient(_make_auth_app(auth))
    response = client.get("/", cookies={"triggarr_session": cookie})
    assert response.status_code == 200
    assert response.json() == {"page": "home"}


def test_any_to_disabled_transition_passes_through():
    """Switching to Disabled mode passes requests through without auth."""
    auth = _configured_auth(method="Disabled")
    client = TestClient(_make_auth_app(auth))
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"page": "home"}


def test_disabled_to_forms_transition_requires_login():
    """Switching from Disabled back to Forms re-requires login."""
    auth = _configured_auth(method="Forms")
    client = TestClient(_make_auth_app(auth), follow_redirects=False)
    response = client.get("/", headers={"Accept": "text/html"})
    assert response.status_code == 302
    assert "/login" in response.headers["location"]


def test_api_key_works_in_basic_mode():
    """X-Api-Key header authenticates when method is Basic."""
    auth = _configured_auth(method="Basic")
    client = TestClient(_make_auth_app(auth))
    response = client.get("/", headers={"X-Api-Key": _API_KEY})
    assert response.status_code == 200


def test_api_key_works_in_external_mode():
    """X-Api-Key still works in External mode (External passes through anyway)."""
    auth = _configured_auth(method="External")
    client = TestClient(_make_auth_app(auth))
    response = client.get("/", headers={"X-Api-Key": _API_KEY})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Phase 58 gap-fill: SC-5 API key edge cases (D-06)
# ---------------------------------------------------------------------------


def test_missing_api_key_api_returns_401_json():
    """API request with no key, no cookie, no basic auth returns 401 JSON."""
    auth = _configured_auth()
    client = TestClient(_make_auth_app(auth))
    response = client.get("/", headers={"Accept": "application/json"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_empty_api_key_does_not_pass():
    """Empty string X-Api-Key header does not authenticate."""
    auth = _configured_auth()
    client = TestClient(_make_auth_app(auth))
    response = client.get("/", headers={"X-Api-Key": "", "Accept": "application/json"})
    assert response.status_code == 401


def test_whitespace_api_key_does_not_pass():
    """Whitespace-only X-Api-Key header does not authenticate."""
    auth = _configured_auth()
    client = TestClient(_make_auth_app(auth))
    response = client.get("/", headers={"X-Api-Key": "   ", "Accept": "application/json"})
    assert response.status_code == 401


def test_invalid_api_key_returns_401_json_not_redirect():
    """Invalid API key with Accept: application/json returns 401 JSON, not redirect."""
    auth = _configured_auth()
    client = TestClient(_make_auth_app(auth))
    response = client.get("/", headers={"X-Api-Key": "wrong-key-value", "Accept": "application/json"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


# ---------------------------------------------------------------------------
# Phase 58 gap-fill: SC-4 disabled mode warning log (D-11 / LOGIN-05)
# ---------------------------------------------------------------------------


def test_disabled_mode_logs_warning_periodically():
    """Disabled mode logs a warning periodically (every 60s), not just once."""
    auth = _configured_auth(method="Disabled")
    client = TestClient(_make_auth_app(auth))
    with (
        patch("triggarr.web.middleware.logger") as mock_logger,
        patch("triggarr.web.middleware.time") as mock_time,
    ):
        # First request at t=100 -> should log (0.0 + 60 <= 100)
        mock_time.monotonic.return_value = 100.0
        client.get("/")
        assert mock_logger.warning.call_count == 1
        assert "disabled" in mock_logger.warning.call_args.args[0].lower()

        # Second request at t=110 -> should NOT log (only 10s since last)
        mock_time.monotonic.return_value = 110.0
        client.get("/")
        assert mock_logger.warning.call_count == 1

        # Third request at t=200 -> should log again (100s since last > 60s)
        mock_time.monotonic.return_value = 200.0
        client.get("/")
        assert mock_logger.warning.call_count == 2
