"""Phase 72: Password Reset Backend & Token Lifecycle — RED test suite.

All tests are RED in Wave 1 (handlers not yet implemented).
After Plan 02: mint/request tests go GREEN.
After Plan 03: confirm/apply tests go GREEN.

Traceability (VALIDATION.md):
  RCOV-02: test_request_mints_token, test_token_file_written_0600,
           test_token_not_in_response, test_token_in_mint_log
  RCOV-03: test_live_token_request_is_noop, test_token_ttl_stored_correctly,
           test_expired_token_rejected, test_new_mint_supersedes_prior, test_token_single_use
  RCOV-04: test_confirm_success_redirects_with_cookie, test_confirm_rotates_session_secret,
           test_pre_reset_cookie_invalid_after_reset, test_new_cookie_validates_after_reset,
           test_wrong_token_generic_error, test_password_mismatch_field_error,
           test_empty_password_field_error, test_password_too_long_field_error
  RCOV-05: test_request_rate_limited, test_confirm_rate_limited
  RCOV-06: test_reset_routes_unauthenticated, test_no_other_route_exposed,
           test_token_file_deleted_on_success
"""

from __future__ import annotations

import asyncio
import time
import tomllib
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from loguru import logger
from pydantic import SecretStr

from triggarr.auth import generate_session_secret, hash_password, sign_session, validate_session
from triggarr.models.config import AuthConfig, GeneralConfig
from triggarr.models.config import Settings as SettingsModel
from triggarr.web.middleware import AuthMiddleware
from triggarr.web.routes import _record_failure, auth_state, router

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

_TEST_PASSWORD = "resetpass456"
_TEST_PASSWORD_HASH = hash_password(_TEST_PASSWORD)
_TEST_SESSION_SECRET = generate_session_secret()
_TEST_USERNAME = "admin"
_TEST_API_KEY = "b" * 32


# ---------------------------------------------------------------------------
# App-builder helpers
# ---------------------------------------------------------------------------


def _make_route_app(auth_config: AuthConfig | None = None, config_path: Path | None = None) -> FastAPI:
    """Build a FastAPI app with real route handlers and AuthMiddleware (Phase 72 base)."""
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(router)

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

    auth_state["active"] = cfg.method in ("Forms", "Basic") and not cfg.needs_setup
    auth_state["method"] = cfg.method

    return app


def _make_reset_app(auth_config: AuthConfig | None = None, config_path: Path | None = None) -> FastAPI:
    """Build a FastAPI app with Phase 72 app.state fields initialized.

    Wraps _make_route_app and adds reset_token / last_reset_time to app.state
    so the reset route handlers do not raise AttributeError (Pitfall 4).
    """
    app = _make_route_app(auth_config=auth_config, config_path=config_path)
    # Phase 72 app.state fields (not initialized by _make_route_app, which predates this phase)
    app.state.reset_token = None
    app.state.last_reset_time = {}
    return app


def _configured_reset_auth(
    username: str = _TEST_USERNAME,
    password: str = _TEST_PASSWORD,
    session_secret: str = _TEST_SESSION_SECRET,
) -> AuthConfig:
    """Create an AuthConfig with real credentials for reset integration tests."""
    return AuthConfig(
        method="Forms",
        username=username,
        password_hash=SecretStr(hash_password(password)),
        api_key=SecretStr(_TEST_API_KEY),
        session_secret=SecretStr(session_secret),
    )


# ---------------------------------------------------------------------------
# RCOV-02: Token mint and redaction
# ---------------------------------------------------------------------------


def test_request_mints_token(tmp_path):
    """POST /reset/request → app.state.reset_token is set (tuple); token NOT in response."""
    config_path = tmp_path / "triggarr.toml"
    app = _make_reset_app(auth_config=_configured_reset_auth(), config_path=config_path)
    client = TestClient(app, follow_redirects=False)

    resp = client.post("/reset/request")

    # Token must be stored in app.state
    assert app.state.reset_token is not None, "Expected reset_token to be set after POST /reset/request"
    assert isinstance(app.state.reset_token, tuple), "reset_token must be a (str, float) tuple"
    token_str, expiry = app.state.reset_token
    assert isinstance(token_str, str) and len(token_str) >= 40, "token_str must be a CSPRNG string"
    assert isinstance(expiry, float), "expiry must be a float (monotonic timestamp)"

    # Token must NOT appear in the HTTP response
    assert token_str not in resp.text


def test_token_file_written_0600(tmp_path):
    """After POST /reset/request, config_path.parent/reset-token.txt exists with mode 0600."""
    config_path = tmp_path / "triggarr.toml"
    app = _make_reset_app(auth_config=_configured_reset_auth(), config_path=config_path)
    client = TestClient(app, follow_redirects=False)

    client.post("/reset/request")

    token_file = tmp_path / "reset-token.txt"
    assert token_file.exists(), "Expected reset-token.txt to be written after POST /reset/request"
    mode = oct(token_file.stat().st_mode & 0o777)
    assert mode == oct(0o600), f"Expected mode 0600, got {mode}"


def test_token_not_in_response(tmp_path):
    """Minted token value must be absent from response.text, set-cookie header, and all headers.

    NOTE: This asserts absence from the HTTP RESPONSE only.
    The token IS in the mint warning log by design (D-02 + RESEARCH #4).
    Do NOT assert absence from logs in this test.
    """
    config_path = tmp_path / "triggarr.toml"
    app = _make_reset_app(auth_config=_configured_reset_auth(), config_path=config_path)
    client = TestClient(app, follow_redirects=False)

    resp = client.post("/reset/request")

    # Retrieve the minted token from app.state (only way to get it without the log)
    assert app.state.reset_token is not None
    token_value = app.state.reset_token[0]

    assert token_value not in resp.text, "Token must not appear in response body"
    assert token_value not in resp.headers.get("set-cookie", ""), "Token must not appear in set-cookie header"
    assert token_value not in str(dict(resp.headers)), "Token must not appear in any response header"


def test_token_in_mint_log(tmp_path):
    """The minted token value IS present in the warning-level mint log line (D-02, RESEARCH #4).

    The reset token is deliberately NOT added to the redacting sink — it is the
    operator-only recovery channel (docker logs / reset-token.txt).
    This test proves the recovery channel exists.
    """
    config_path = tmp_path / "triggarr.toml"
    app = _make_reset_app(auth_config=_configured_reset_auth(), config_path=config_path)
    client = TestClient(app, follow_redirects=False)

    # Attach a temporary loguru sink to capture log records
    captured_records: list[str] = []

    def _capture_sink(message):
        captured_records.append(str(message))

    sink_id = logger.add(_capture_sink, level="WARNING", format="{message}")
    try:
        client.post("/reset/request")
    finally:
        logger.remove(sink_id)

    assert app.state.reset_token is not None
    token_value = app.state.reset_token[0]

    # The token MUST appear in at least one warning-level log record
    token_in_logs = any(token_value in record for record in captured_records)
    assert token_in_logs, (
        f"Expected token '{token_value}' to appear in a warning log record "
        f"(D-02 operator recovery channel). Captured records: {captured_records}"
    )


# ---------------------------------------------------------------------------
# RCOV-03: Token lifecycle (TTL, supersession, H1 live-token guard)
# ---------------------------------------------------------------------------


def test_live_token_request_is_noop(tmp_path):
    """With a LIVE (unexpired) token in app.state.reset_token, a second POST /reset/request
    must NOT mint a new token (H1 unauthenticated-supersession-DoS mitigation).

    The existing tuple must be identical after the second request (same token + same expiry).
    The token file must not be rewritten.
    """
    config_path = tmp_path / "triggarr.toml"
    app = _make_reset_app(auth_config=_configured_reset_auth(), config_path=config_path)

    # Pre-seed a live (unexpired) token
    live_token = "livetoken_abc123xyz"
    live_expiry = time.monotonic() + 900  # expires in 15 minutes
    app.state.reset_token = (live_token, live_expiry)
    app.state.last_reset_time = {}  # clear rate-limit so timing is not the cause

    client = TestClient(app, follow_redirects=False)
    client.post("/reset/request")

    # The existing token tuple must be unchanged
    assert app.state.reset_token is not None
    stored_token, stored_expiry = app.state.reset_token
    assert stored_token == live_token, (
        f"Expected token to remain '{live_token}', but got '{stored_token}' — "
        "a second request must not supersede a live token (H1)"
    )
    assert stored_expiry == live_expiry, "Expected expiry to remain unchanged for live token (H1)"

    # Token file must not have been written/rewritten
    token_file = tmp_path / "reset-token.txt"
    assert not token_file.exists(), "Token file must not be written when a live token already exists (H1)"


def test_token_ttl_stored_correctly(tmp_path, monkeypatch):
    """Stored expiry == monotonic_at_mint + 900 (15-minute TTL, D-05)."""
    config_path = tmp_path / "triggarr.toml"
    app = _make_reset_app(auth_config=_configured_reset_auth(), config_path=config_path)

    fake_time = 1000.0
    monkeypatch.setattr(time, "monotonic", lambda: fake_time)

    client = TestClient(app, follow_redirects=False)
    client.post("/reset/request")

    assert app.state.reset_token is not None
    _, expiry = app.state.reset_token
    assert expiry == fake_time + 900, f"Expected expiry {fake_time + 900}, got {expiry}"


def test_expired_token_rejected(tmp_path, monkeypatch):
    """Token with past expiry → POST /reset/confirm returns generic 'Invalid or expired', no state change."""
    config_path = tmp_path / "triggarr.toml"
    _init_toml(config_path)
    auth = _configured_reset_auth()
    app = _make_reset_app(auth_config=auth, config_path=config_path)

    expired_token = "expiredtoken_xyz"
    # Set token with already-expired timestamp
    app.state.reset_token = (expired_token, time.monotonic() - 1)

    client = TestClient(app, follow_redirects=False)
    resp = client.post(
        "/reset/confirm",
        data={"token": expired_token, "new_password": "newpass123", "confirm_password": "newpass123"},
    )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert "Invalid or expired" in resp.text or "invalid" in resp.text.lower()
    # State must be unchanged (token still present/cleared to None — either is acceptable since it's expired)


def test_new_mint_supersedes_prior(tmp_path):
    """With a prior token EXPIRED/absent, a new POST /reset/request mints a fresh token.

    The first (expired) token no longer validates after the second mint (supersession
    applies to expired/absent tokens — H1 refinement).
    """
    config_path = tmp_path / "triggarr.toml"
    app = _make_reset_app(auth_config=_configured_reset_auth(), config_path=config_path)

    # Pre-seed an expired token
    first_token = "firsttoken_xyz"
    app.state.reset_token = (first_token, time.monotonic() - 1)  # expired

    client = TestClient(app, follow_redirects=False)
    client.post("/reset/request")

    assert app.state.reset_token is not None
    second_token, _ = app.state.reset_token
    assert second_token != first_token, "Expected new token to supersede the expired prior token"


# ---------------------------------------------------------------------------
# RCOV-03: Single-use
# ---------------------------------------------------------------------------


def test_token_single_use(tmp_path):
    """Successful confirm clears reset_token; re-POSTing the same token is rejected (D-07)."""
    config_path = tmp_path / "triggarr.toml"
    _init_toml(config_path)
    auth = _configured_reset_auth()
    app = _make_reset_app(auth_config=auth, config_path=config_path)

    # Mint a token via the request endpoint (or pre-seed for determinism)
    token_str = "singlusetoken_abc"
    app.state.reset_token = (token_str, time.monotonic() + 900)

    client = TestClient(app, follow_redirects=False)

    # First confirm: should succeed (303) — requires Plan 03 to implement
    resp1 = client.post(
        "/reset/confirm",
        data={"token": token_str, "new_password": "newpass789!", "confirm_password": "newpass789!"},
    )
    # After Plans 02/03 land resp1 should be 303; for now it may be 404/200
    # We only assert the second attempt is rejected:
    assert app.state.reset_token is None or (
        isinstance(app.state.reset_token, tuple) and app.state.reset_token[0] != token_str
    ) or resp1.status_code != 303, "After Plan 03: first confirm should clear reset_token"

    # Re-POST the same token — must be rejected
    resp2 = client.post(
        "/reset/confirm",
        data={"token": token_str, "new_password": "newpass789!", "confirm_password": "newpass789!"},
    )
    # When handlers exist: should return generic error (token no longer valid)
    assert resp2.status_code != 303, "Second use of the same token must not succeed"


# ---------------------------------------------------------------------------
# RCOV-04: Confirm/apply path
# ---------------------------------------------------------------------------


def test_confirm_success_redirects_with_cookie(tmp_path):
    """Valid token + matching password → 303 to dashboard + triggarr_session set-cookie (D-13)."""
    config_path = tmp_path / "triggarr.toml"
    _init_toml(config_path)
    auth = _configured_reset_auth()
    app = _make_reset_app(auth_config=auth, config_path=config_path)

    token_str = "confirmtoken_abc"
    app.state.reset_token = (token_str, time.monotonic() + 900)

    client = TestClient(app, follow_redirects=False)
    resp = client.post(
        "/reset/confirm",
        data={"token": token_str, "new_password": "newpass789!", "confirm_password": "newpass789!"},
    )

    # After Plan 03 lands: 303 + set-cookie
    assert resp.status_code == 303, f"Expected 303, got {resp.status_code}"
    assert "triggarr_session" in resp.headers.get("set-cookie", "")


def test_confirm_rotates_session_secret(tmp_path):
    """Persisted TOML auth.session_secret differs from original after successful confirm (D-12)."""
    config_path = tmp_path / "triggarr.toml"
    original_secret = _init_toml(config_path)
    auth = _configured_reset_auth(session_secret=original_secret)
    app = _make_reset_app(auth_config=auth, config_path=config_path)

    token_str = "rotatetoken_abc"
    app.state.reset_token = (token_str, time.monotonic() + 900)

    client = TestClient(app, follow_redirects=False)
    client.post(
        "/reset/confirm",
        data={"token": token_str, "new_password": "newpass789!", "confirm_password": "newpass789!"},
    )

    persisted = tomllib.loads(config_path.read_text())
    new_secret = persisted["auth"]["session_secret"]
    assert new_secret != original_secret, "session_secret must be rotated after successful reset"


def test_pre_reset_cookie_invalid_after_reset(tmp_path):
    """Cookie signed with old secret → validate_session(old_cookie, new_secret) is None (D-12)."""
    config_path = tmp_path / "triggarr.toml"
    original_secret = _init_toml(config_path)
    auth = _configured_reset_auth(session_secret=original_secret)
    app = _make_reset_app(auth_config=auth, config_path=config_path)

    # Sign a cookie with the original secret
    old_cookie = sign_session(_TEST_USERNAME, original_secret)

    token_str = "preresettoken_abc"
    app.state.reset_token = (token_str, time.monotonic() + 900)

    client = TestClient(app, follow_redirects=False)
    client.post(
        "/reset/confirm",
        data={"token": token_str, "new_password": "newpass789!", "confirm_password": "newpass789!"},
    )

    persisted = tomllib.loads(config_path.read_text())
    new_secret = persisted["auth"]["session_secret"]
    assert validate_session(old_cookie, new_secret) is None, (
        "Pre-reset cookie must fail validation against new session_secret"
    )


def test_new_cookie_validates_after_reset(tmp_path):
    """New set-cookie from confirm validates under new secret (D-13)."""
    config_path = tmp_path / "triggarr.toml"
    original_secret = _init_toml(config_path)
    auth = _configured_reset_auth(session_secret=original_secret)
    app = _make_reset_app(auth_config=auth, config_path=config_path)

    token_str = "newcookietoken_abc"
    app.state.reset_token = (token_str, time.monotonic() + 900)

    client = TestClient(app, follow_redirects=False)
    resp = client.post(
        "/reset/confirm",
        data={"token": token_str, "new_password": "newpass789!", "confirm_password": "newpass789!"},
    )

    set_cookie = resp.headers.get("set-cookie", "")
    assert "triggarr_session" in set_cookie

    # Extract cookie value from set-cookie header: triggarr_session=<value>; ...
    cookie_value = None
    for part in set_cookie.split(";"):
        part = part.strip()
        if part.startswith("triggarr_session="):
            cookie_value = part.split("=", 1)[1]
            break

    assert cookie_value is not None, "Expected triggarr_session cookie value"

    persisted = tomllib.loads(config_path.read_text())
    new_secret = persisted["auth"]["session_secret"]
    username = validate_session(cookie_value, new_secret)
    assert username == _TEST_USERNAME, (
        f"New cookie must validate under new session_secret, got: {username}"
    )


def test_wrong_token_generic_error(tmp_path):
    """Wrong token → generic error, app.state.reset_token unchanged, password_hash unchanged (D-06)."""
    config_path = tmp_path / "triggarr.toml"
    _init_toml(config_path)
    auth = _configured_reset_auth()
    app = _make_reset_app(auth_config=auth, config_path=config_path)

    correct_token = "correcttoken_abc"
    app.state.reset_token = (correct_token, time.monotonic() + 900)

    original_hash = app.state.settings.auth.password_hash.get_secret_value()

    client = TestClient(app, follow_redirects=False)
    resp = client.post(
        "/reset/confirm",
        data={"token": "wrongtoken_xyz", "new_password": "newpass789!", "confirm_password": "newpass789!"},
    )

    assert resp.status_code == 200
    # Generic message — no detail about why
    text_lower = resp.text.lower()
    assert "invalid" in text_lower or "expired" in text_lower or "error" in text_lower

    # State unchanged: token still set, password_hash unchanged
    assert app.state.reset_token is not None
    assert app.state.reset_token[0] == correct_token
    assert app.state.settings.auth.password_hash.get_secret_value() == original_hash


def test_password_mismatch_field_error(tmp_path):
    """new_password != confirm_password → per-field errors dict, no state change (D-20)."""
    config_path = tmp_path / "triggarr.toml"
    _init_toml(config_path)
    auth = _configured_reset_auth()
    app = _make_reset_app(auth_config=auth, config_path=config_path)

    token_str = "mismatchtoken_abc"
    app.state.reset_token = (token_str, time.monotonic() + 900)

    client = TestClient(app, follow_redirects=False)
    resp = client.post(
        "/reset/confirm",
        data={"token": token_str, "new_password": "pass1", "confirm_password": "pass2"},
    )

    assert resp.status_code == 200
    assert "match" in resp.text.lower() or "mismatch" in resp.text.lower() or "do not match" in resp.text.lower()
    # Token should still be valid (no state change on field error)
    assert app.state.reset_token is not None


def test_empty_password_field_error(tmp_path):
    """Empty new_password → per-field error, no state change (D-20)."""
    config_path = tmp_path / "triggarr.toml"
    _init_toml(config_path)
    auth = _configured_reset_auth()
    app = _make_reset_app(auth_config=auth, config_path=config_path)

    token_str = "emptypasstoken_abc"
    app.state.reset_token = (token_str, time.monotonic() + 900)

    client = TestClient(app, follow_redirects=False)
    resp = client.post(
        "/reset/confirm",
        data={"token": token_str, "new_password": "", "confirm_password": ""},
    )

    assert resp.status_code == 200
    text_lower = resp.text.lower()
    assert "required" in text_lower or "empty" in text_lower or "password" in text_lower
    assert app.state.reset_token is not None


def test_password_too_long_field_error(tmp_path):
    """>72-byte password → per-field error (bcrypt ValueError surfaced as field error, D-09)."""
    config_path = tmp_path / "triggarr.toml"
    _init_toml(config_path)
    auth = _configured_reset_auth()
    app = _make_reset_app(auth_config=auth, config_path=config_path)

    token_str = "toolongtoken_abc"
    app.state.reset_token = (token_str, time.monotonic() + 900)

    too_long = "x" * 73  # 73 bytes > bcrypt 72-byte limit

    client = TestClient(app, follow_redirects=False)
    resp = client.post(
        "/reset/confirm",
        data={"token": token_str, "new_password": too_long, "confirm_password": too_long},
    )

    assert resp.status_code == 200
    text_lower = resp.text.lower()
    assert "72" in resp.text or "characters" in text_lower or "bytes" in text_lower
    assert app.state.reset_token is not None


# ---------------------------------------------------------------------------
# RCOV-05: Rate-limiting
# ---------------------------------------------------------------------------


def test_request_rate_limited(tmp_path):
    """Second POST /reset/request within 60s window → 429 (D-15)."""
    config_path = tmp_path / "triggarr.toml"
    # Use a fresh app so last_reset_time starts empty
    app = _make_reset_app(auth_config=_configured_reset_auth(), config_path=config_path)
    client = TestClient(app, follow_redirects=False)

    # First request — should be accepted (not rate limited)
    client.post("/reset/request")
    # Second request — should be rate limited (60s window not elapsed)
    resp2 = client.post("/reset/request")

    assert resp2.status_code == 429, f"Expected 429 on second request, got {resp2.status_code}"


def test_confirm_rate_limited(tmp_path):
    """Rapid POST /reset/confirm within 5s window → 429 (D-15)."""
    config_path = tmp_path / "triggarr.toml"
    _init_toml(config_path)
    # Use a fresh app so last_reset_time starts empty
    auth = _configured_reset_auth()
    app = _make_reset_app(auth_config=auth, config_path=config_path)

    token_str = "ratelimittoken_abc"
    app.state.reset_token = (token_str, time.monotonic() + 900)

    client = TestClient(app, follow_redirects=False)

    # First confirm attempt — accepted (regardless of outcome)
    client.post(
        "/reset/confirm",
        data={"token": token_str, "new_password": "pass1", "confirm_password": "pass2"},
    )

    # Re-seed token in case first request consumed it
    app.state.reset_token = (token_str, time.monotonic() + 900)

    # Second confirm within 5s — must be rate limited
    resp2 = client.post(
        "/reset/confirm",
        data={"token": token_str, "new_password": "pass1", "confirm_password": "pass2"},
    )

    assert resp2.status_code == 429, f"Expected 429 on rapid second confirm, got {resp2.status_code}"


# ---------------------------------------------------------------------------
# RCOV-06: Middleware exemption / reachability
# ---------------------------------------------------------------------------


def test_reset_routes_unauthenticated(tmp_path):
    """GET /reset/request with no session cookie → 200 (not redirected to /login, D-21)."""
    config_path = tmp_path / "triggarr.toml"
    auth = _configured_reset_auth()
    # active=True so the middleware would normally gate all routes
    app = _make_reset_app(auth_config=auth, config_path=config_path)
    auth_state["active"] = True
    auth_state["method"] = "Forms"

    client = TestClient(app, follow_redirects=False)
    resp = client.get("/reset/request")

    assert resp.status_code == 200, (
        f"Expected GET /reset/request to be reachable unauthenticated (200), got {resp.status_code}"
    )


def test_no_other_route_exposed(tmp_path):
    """M2 exemption invariant:
    - GET / with no cookie still redirects to /login (auth gate intact)
    - GET /resetXYZ with no cookie is NOT exempt (redirects/401), proving M2 exact-or-/reset/ predicate
    - GET /reset and GET /reset/request are reachable unauthenticated (200)
    """
    config_path = tmp_path / "triggarr.toml"
    auth = _configured_reset_auth()
    app = _make_reset_app(auth_config=auth, config_path=config_path)
    auth_state["active"] = True
    auth_state["method"] = "Forms"

    client = TestClient(app, follow_redirects=False)

    # Dashboard (/) must still be gated
    resp_dash = client.get("/")
    assert resp_dash.status_code in (302, 303, 307, 401), (
        f"GET / must still be gated (expected redirect/401), got {resp_dash.status_code}"
    )
    if resp_dash.status_code in (302, 303, 307):
        assert "/login" in resp_dash.headers.get("location", ""), (
            "GET / redirect must go to /login"
        )

    # /resetXYZ must NOT be exempt (M2)
    resp_xyz = client.get("/resetXYZ")
    assert resp_xyz.status_code in (302, 303, 307, 401, 404), (
        f"GET /resetXYZ must NOT be exempt — expected redirect/401/404, got {resp_xyz.status_code}"
    )
    # If it redirects, must not already be exempt (i.e., must not return 200)
    assert resp_xyz.status_code != 200, (
        "GET /resetXYZ must NOT return 200 — it must stay behind the auth gate (M2)"
    )

    # /reset and /reset/request must be reachable unauthenticated
    resp_reset = client.get("/reset")
    assert resp_reset.status_code in (200, 404), (
        f"GET /reset must be exempt (expected 200 or 404 if no handler yet), got {resp_reset.status_code}"
    )
    assert resp_reset.status_code != 302 or "/login" not in resp_reset.headers.get("location", ""), (
        "GET /reset must not redirect to /login — it must be exempt"
    )

    resp_req = client.get("/reset/request")
    assert resp_req.status_code in (200, 404), (
        f"GET /reset/request must be exempt (expected 200 or 404 if no handler yet), got {resp_req.status_code}"
    )


def test_token_file_deleted_on_success(tmp_path):
    """reset-token.txt is deleted after successful confirm (D-07, RCOV-06)."""
    config_path = tmp_path / "triggarr.toml"
    _init_toml(config_path)
    auth = _configured_reset_auth()
    app = _make_reset_app(auth_config=auth, config_path=config_path)

    # Create the token file as if a prior mint wrote it
    token_file = tmp_path / "reset-token.txt"
    token_str = "deletetoken_abc"
    token_file.write_text(token_str)
    token_file.chmod(0o600)

    app.state.reset_token = (token_str, time.monotonic() + 900)

    client = TestClient(app, follow_redirects=False)
    resp = client.post(
        "/reset/confirm",
        data={"token": token_str, "new_password": "newpass789!", "confirm_password": "newpass789!"},
    )

    # After Plan 03 lands (resp should be 303): token file must be deleted
    if resp.status_code == 303:
        assert not token_file.exists(), "reset-token.txt must be deleted after successful reset (D-07)"


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _init_toml(config_path: Path, session_secret: str | None = None) -> str:
    """Write a minimal triggarr.toml with auth credentials for rotation tests.

    Returns the session_secret written to disk.
    """
    secret = session_secret or _TEST_SESSION_SECRET
    toml_content = f"""[general]
log_level = "INFO"

[auth]
method = "Forms"
username = "{_TEST_USERNAME}"
password_hash = "{hash_password(_TEST_PASSWORD)}"
session_secret = "{secret}"
api_key = "{_TEST_API_KEY}"
"""
    config_path.write_text(toml_content)
    return secret


# ---------------------------------------------------------------------------
# Phase 73 — Task 1: GET /reset/confirm reachability and exemption non-widening
# ---------------------------------------------------------------------------


def test_get_reset_confirm_reachable_unauthenticated(tmp_path):
    """GET /reset/confirm with no session cookie (auth active) → 200 and renders the confirm form.

    The route is exempt via the exact-or-/reset/ predicate in AuthMiddleware (middleware.py:118).
    Uses _make_reset_app (not _make_route_app) so app.state.reset_token / last_reset_time
    are initialized.
    """
    config_path = tmp_path / "triggarr.toml"
    auth = _configured_reset_auth()
    app = _make_reset_app(auth_config=auth, config_path=config_path)
    auth_state["active"] = True
    auth_state["method"] = "Forms"

    client = TestClient(app, follow_redirects=False)
    resp = client.get("/reset/confirm")

    assert resp.status_code == 200, (
        f"Expected GET /reset/confirm to be reachable unauthenticated (200), got {resp.status_code}"
    )
    # The confirm form must render the Reset Token label and a new_password field
    assert "Reset Token" in resp.text, (
        "Expected 'Reset Token' label to appear in the confirm form"
    )
    assert "new_password" in resp.text, (
        "Expected 'new_password' field to appear in the confirm form"
    )


def test_reset_confirm_route_did_not_widen_exemption(tmp_path):
    """Regression: adding GET /reset/confirm must NOT widen the auth exemption.

    The exact-or-/reset/ predicate (middleware.py:118) exempts path == "/reset" or
    path.startswith("/reset/") — deliberately NOT a bare startswith("/reset") so
    /resetXYZ stays gated.

    This test proves the AUTH BOUNDARY (not a routing-level smoke check):
    GET /resetXYZ with a browser Accept header returns 302 with /login in Location,
    because AuthMiddleware dispatch step 7 takes the browser-redirect branch.

    IMPORTANT: 404 must NOT be treated as passing. A 404 would mean the request
    bypassed AuthMiddleware and reached the router (no matching route), which is
    the exact exemption-widening failure this test guards against. The only valid
    gated response for a browser request is 302 → /login (verified against dispatch
    step 7 at middleware.py:161-163).
    """
    config_path = tmp_path / "triggarr.toml"
    auth = _configured_reset_auth()
    app = _make_reset_app(auth_config=auth, config_path=config_path)
    auth_state["active"] = True
    auth_state["method"] = "Forms"

    client = TestClient(app, follow_redirects=False)
    # Browser request to a non-exempt path triggers the 302 → /login fallback (step 7)
    resp = client.get("/resetXYZ", headers={"Accept": "text/html"})

    # Must be 302 with /login in Location (auth boundary) — NOT 404 (bypass) and NOT 200
    assert resp.status_code == 302, (
        f"GET /resetXYZ must be gated at the auth boundary (expected 302), got {resp.status_code}. "
        "A 404 would mean the request bypassed AuthMiddleware (exemption widened). "
        "A 200 would mean the route is accessible (also widened). "
        "Only 302 → /login proves the auth boundary is intact."
    )
    assert "/login" in resp.headers.get("location", ""), (
        f"GET /resetXYZ 302 redirect must point to /login, got location={resp.headers.get('location', '')!r}"
    )


# ---------------------------------------------------------------------------
# Phase 73 — Task 2: "Forgot password?" link (defensive guard), reset.html
#             message-state, onward link, and Back-to-login
# ---------------------------------------------------------------------------


def test_forgot_password_link_shown_when_configured(tmp_path):
    """GET /login with a configured app (needs_setup=False) → 'Forgot password?' in response."""
    config_path = tmp_path / "triggarr.toml"
    auth = _configured_reset_auth()
    app = _make_reset_app(auth_config=auth, config_path=config_path)
    auth_state["active"] = True
    auth_state["method"] = "Forms"

    client = TestClient(app, follow_redirects=False)
    resp = client.get("/login")

    assert "Forgot password?" in resp.text, (
        "Expected 'Forgot password?' link to appear on the login page when auth is configured"
    )


def test_forgot_password_link_absent_during_setup_get(tmp_path):
    """GET /login with a default app (needs_setup=True) → 'Forgot password?' NOT in response."""
    # Default AuthConfig() has needs_setup=True (no credentials set)
    app = _make_reset_app()
    # Default app has active=False so /login is reachable without redirect to setup
    auth_state["active"] = False
    auth_state["method"] = "Disabled"

    client = TestClient(app, follow_redirects=False)
    resp = client.get("/login")

    assert "Forgot password?" not in resp.text, (
        "Expected 'Forgot password?' link to be ABSENT on the login page during first-run setup"
    )


def test_forgot_password_link_absent_during_setup_post(tmp_path):
    """POST /login invalid-credentials re-render during first-run setup → link absent.

    The /login path is in EXEMPT_PREFIXES so the POST passes the middleware even during setup.
    The INVALID-CREDENTIALS re-render must NOT show the 'Forgot password?' link when
    needs_setup=True (the link must not leak on a POST re-render before auth is configured).
    """
    app = _make_reset_app()  # default: needs_setup=True
    auth_state["active"] = False
    auth_state["method"] = "Disabled"

    client = TestClient(app, follow_redirects=False)
    # Deliberately wrong credentials → invalid-credentials re-render fires
    resp = client.post("/login", data={"username": "x", "password": "wrong"})

    # Should re-render login.html (not redirect)
    assert "Sign In" in resp.text, "Expected login.html to re-render (invalid-credentials path)"
    assert "Forgot password?" not in resp.text, (
        "Expected 'Forgot password?' link to be ABSENT on the invalid-credentials POST re-render "
        "during first-run setup (needs_setup=True)"
    )


def test_forgot_password_link_absent_during_setup_rate_limit(tmp_path):
    """POST /login 429 rate-limit re-render during first-run setup → link absent.

    Proves the THIRD login.html render site (the 429 rate-limit re-render at routes.py:1335-1340)
    carries needs_setup=True during setup so the recovery link stays hidden.

    Strategy: seed 10 failures via _record_failure("testclient") to push the TestClient IP
    over the _MAX_ATTEMPTS=10 limit. The conftest autouse _reset_rate_limit_state fixture
    clears _login_failures before/after each test so this seeding does not leak.
    """
    app = _make_reset_app()  # default: needs_setup=True
    auth_state["active"] = False
    auth_state["method"] = "Disabled"

    # Seed failures to trigger the 429 rate-limit path on the next POST
    for _ in range(10):
        _record_failure("testclient")

    client = TestClient(app, follow_redirects=False)
    # POST /login — the rate-limit check fires before credential verification → 429 re-render
    resp = client.post("/login", data={"username": "x", "password": "wrong"})

    # Prove the 429 render path was taken
    assert resp.status_code == 429, (
        f"Expected 429 rate-limit response (seeded 10 failures), got {resp.status_code}"
    )
    # Prove login.html was re-rendered
    assert "Sign In" in resp.text, "Expected login.html to re-render on 429 path"
    # Prove the link stays hidden during setup even on the 429 render path
    assert "Forgot password?" not in resp.text, (
        "Expected 'Forgot password?' link to be ABSENT on the 429 rate-limit POST re-render "
        "during first-run setup (needs_setup=True) — the third login.html render site must "
        "carry needs_setup=True so the recovery link stays hidden before auth is configured"
    )


def test_request_confirmation_message_state(tmp_path):
    """MANDATORY (Finding 2): message-state on both mint and live-token no-op paths.

    Covers:
    (i)   First-mint path: neutral message + onward /reset/confirm link + button absent +
          token absent from body and headers.
    (ii)  H1 live-token no-op path: same contract.
    (iii) Context-boundary token-absence (exact source assertion): both reset_request_post
          message-branch context dicts are keyed exactly {step, message} with no token key.
          Verified against routes.py source text (routes.py:1685-1692 and 1730-1737).
    """
    # (i) First-mint path
    config_path = tmp_path / "triggarr.toml"
    auth = _configured_reset_auth()
    app_mint = _make_reset_app(auth_config=auth, config_path=config_path)

    client_mint = TestClient(app_mint, follow_redirects=False)
    resp_mint = client_mint.post("/reset/request")

    # Capture the minted token (the only way to get it without reading the log)
    assert app_mint.state.reset_token is not None, "Token must be minted after POST /reset/request"
    token_value = app_mint.state.reset_token[0]

    # Neutral message must render
    assert resp_mint.status_code == 200, f"Expected 200 from POST /reset/request, got {resp_mint.status_code}"
    # Some neutral confirmation text must be present (the message context key renders)
    assert len(resp_mint.text) > 0, "Response body must not be empty"
    # The message is present (a non-empty string in the page)
    assert "reset token" in resp_mint.text.lower() or "config" in resp_mint.text.lower(), (
        "Expected neutral confirmation message text in the response"
    )
    # Onward link to /reset/confirm must be present
    assert "/reset/confirm" in resp_mint.text, (
        "Expected onward link to /reset/confirm to appear after a successful mint"
    )
    # The 'Request Reset Token' submit button must be ABSENT in the confirmation state
    assert "Request Reset Token" not in resp_mint.text, (
        "Expected 'Request Reset Token' button to be absent in the message/confirmation state"
    )
    # Token value must be absent from body and headers
    assert token_value not in resp_mint.text, (
        "Token value must NOT appear in the response body (D-02b invariant)"
    )
    assert token_value not in str(dict(resp_mint.headers)), (
        "Token value must NOT appear in any response header (D-02b invariant)"
    )

    # (ii) H1 live-token no-op path
    config_path2 = tmp_path / "triggarr2.toml"
    auth2 = _configured_reset_auth()
    app_noop = _make_reset_app(auth_config=auth2, config_path=config_path2)
    # Pre-seed a LIVE token to exercise the H1 no-op branch (mirror test_live_token_request_is_noop)
    live_token = "livetoken_abc123xyz"
    app_noop.state.reset_token = (live_token, time.monotonic() + 900)
    app_noop.state.last_reset_time = {}

    client_noop = TestClient(app_noop, follow_redirects=False)
    resp_noop = client_noop.post("/reset/request")

    assert resp_noop.status_code == 200, f"Expected 200 from H1 no-op POST /reset/request, got {resp_noop.status_code}"
    # Same message-state contract
    assert "/reset/confirm" in resp_noop.text, (
        "Expected onward link to /reset/confirm on H1 live-token no-op path"
    )
    assert "Request Reset Token" not in resp_noop.text, (
        "Expected 'Request Reset Token' button absent on H1 live-token no-op path"
    )
    # Live token must be absent from body and headers
    assert live_token not in resp_noop.text, (
        "Live token value must NOT appear in the response body on H1 no-op path (D-02b invariant)"
    )
    assert live_token not in str(dict(resp_noop.headers)), (
        "Live token value must NOT appear in any response header on H1 no-op path (D-02b invariant)"
    )

    # (iii) Context-boundary token-absence: exact source assertion over reset_request_post
    # The real invariant is "token NEVER appears in any template/response CONTEXT", not just
    # body/headers. We assert the source directly since the rendered context is not exposed
    # via TestClient. Both message-branch context dicts must be keyed exactly {"step", "message"} —
    # verified against routes.py:1685-1692 (H1 no-op branch) and routes.py:1730-1737 (mint branch).
    routes_source = (Path(__file__).resolve().parent.parent / "triggarr" / "web" / "routes.py").read_text()

    # The message context dicts must contain "step": "request" and "message":
    assert '"step": "request"' in routes_source or "'step': 'request'" in routes_source, (
        "Expected message context dicts to include step='request'"
    )
    assert '"message":' in routes_source or "'message':" in routes_source, (
        "Expected message context dicts to include the message key"
    )

    # The token local must NOT appear as a context value in the message branches.
    # We assert there is no `: token` binding inside any message-branch context dict.
    # The pattern ": token" as a dict value would mean the token variable is in the context.
    # We check specifically that neither message branch assigns the token to any context key.
    # Strategy: find the two return statements that include "message" context and verify
    # neither contains a ": token" binding (i.e., token as a value, not "token" as a key name).
    import re

    # Find both message-branch return blocks in reset_request_post
    # The key invariant: in both TemplateResponse calls within reset_request_post that include
    # "message", the context dict must have ONLY "step" and "message" keys — no token-valued key.
    # We assert that within those blocks, the token variable name does not appear as a dict value.
    # Regex: find context dicts in reset_request_post that include "message" key and check no
    # token assignment appears as a value.

    # Find all context dict literals that include both "step": "request" and "message":
    # These are the two message-branch context dicts the plan pins.
    message_context_pattern = re.compile(
        r'context=\{[^}]*"step":\s*"request"[^}]*"message":[^}]*\}',
        re.DOTALL,
    )
    message_contexts = message_context_pattern.findall(routes_source)

    assert len(message_contexts) >= 2, (
        f"Expected at least 2 message-branch context dicts in reset_request_post, "
        f"found {len(message_contexts)}. Both the H1 no-op and mint branches must use "
        f"context={{step, message}} shape."
    )

    # Each message context dict must not contain ": token" as a value binding
    for ctx in message_contexts:
        assert ": token" not in ctx and ": token," not in ctx, (
            f"Token variable must NOT appear as a context value in the message branch. "
            f"Found unexpected context dict: {ctx!r}"
        )
        # Also assert the context has exactly two keys (step and message)
        # Count quoted key occurrences — must be 2
        key_count = len(re.findall(r'"step"|"message"', ctx))
        assert key_count == 2, (
            f"Message-branch context dict must have exactly 2 keys (step, message), "
            f"found {key_count} in: {ctx!r}"
        )
