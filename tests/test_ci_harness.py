"""Unit tests for the CI test harness: the stub *arr service and the HTTP checks.

These tests exercise `tests/harness/arr_stub.py` directly (as a real, locally bound
HTTP server) and `tests/harness/checks.py` against a tiny fake "triggarr" server whose
per-path responses each test configures -- they do not start the real Triggarr app.
Plan 04's shipped-image smoke job and Plans 05/06's browser suite reuse `checks.py`
against the real, real audited image.
"""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from tests.harness import arr_stub, checks

_STUB_API_KEY = "test-stub-key"


# ---------------------------------------------------------------------------
# arr_stub fixture: a real stub *arr server bound to an ephemeral port
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_base() -> str:
    """Start arr_stub.build_server on an ephemeral port in a daemon thread."""
    server = arr_stub.build_server("127.0.0.1", 0, _STUB_API_KEY)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


def _stub_get(base: str, path: str, api_key: str | None = _STUB_API_KEY) -> tuple[int, dict[str, Any] | list[Any]]:
    import urllib.error
    import urllib.request

    headers = {"X-Api-Key": api_key} if api_key is not None else {}
    request = urllib.request.Request(base + path, headers=headers, method="GET")
    try:
        response = urllib.request.urlopen(request, timeout=10)
        return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _stub_post(base: str, path: str, payload: bytes, api_key: str | None = _STUB_API_KEY) -> tuple[int, Any]:
    import urllib.error
    import urllib.request

    headers = {"X-Api-Key": api_key} if api_key is not None else {}
    headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base + path, data=payload, headers=headers, method="POST")
    try:
        response = urllib.request.urlopen(request, timeout=10)
        return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_stub_system_status_with_correct_key(stub_base: str) -> None:
    status, body = _stub_get(stub_base, "/api/v3/system/status")
    assert status == 200
    assert isinstance(body, dict)
    assert isinstance(body.get("version"), str)


def test_stub_wanted_missing_envelope(stub_base: str) -> None:
    status, body = _stub_get(stub_base, "/api/v3/wanted/missing")
    assert status == 200
    assert body["totalRecords"] == 0
    assert body["records"] == []


def test_stub_wanted_cutoff_envelope(stub_base: str) -> None:
    status, body = _stub_get(stub_base, "/api/v3/wanted/cutoff")
    assert status == 200
    assert body["totalRecords"] == 0
    assert body["records"] == []


def test_stub_movie_envelope(stub_base: str) -> None:
    status, body = _stub_get(stub_base, "/api/v3/movie")
    assert status == 200
    assert body["totalRecords"] == 0
    assert body["records"] == []


def test_stub_tag_empty_list(stub_base: str) -> None:
    status, body = _stub_get(stub_base, "/api/v3/tag")
    assert status == 200
    assert body == []


def test_stub_history_movie_empty_list(stub_base: str) -> None:
    status, body = _stub_get(stub_base, "/api/v3/history/movie")
    assert status == 200
    assert body == []


def test_stub_command_returns_201_with_integer_id(stub_base: str) -> None:
    status, body = _stub_post(stub_base, "/api/v3/command", b'{"name": "MoviesSearch", "movieIds": [1]}')
    assert status == 201
    assert isinstance(body["id"], int)


def test_stub_rejects_missing_api_key(stub_base: str) -> None:
    status, _ = _stub_get(stub_base, "/api/v3/system/status", api_key=None)
    assert status == 401


def test_stub_rejects_wrong_api_key(stub_base: str) -> None:
    status, _ = _stub_get(stub_base, "/api/v3/system/status", api_key="wrong-key")
    assert status == 401


def test_stub_control_state_down_then_api_returns_503(stub_base: str) -> None:
    status, body = _stub_post(stub_base, "/__control/state", b'{"up": false}', api_key=None)
    assert status == 200
    assert body == {"up": False}

    status, _ = _stub_get(stub_base, "/api/v3/system/status")
    assert status == 503


def test_stub_control_state_up_restores_200(stub_base: str) -> None:
    _stub_post(stub_base, "/__control/state", b'{"up": false}', api_key=None)
    status, body = _stub_post(stub_base, "/__control/state", b'{"up": true}', api_key=None)
    assert status == 200
    assert body == {"up": True}

    status, _ = _stub_get(stub_base, "/api/v3/system/status")
    assert status == 200


def test_stub_control_state_get_returns_up_and_request_count(stub_base: str) -> None:
    _stub_get(stub_base, "/api/v3/system/status")
    _stub_get(stub_base, "/api/v3/tag")
    status, body = _stub_get(stub_base, "/__control/state", api_key=None)
    assert status == 200
    assert body["up"] is True
    assert body["api_requests"] >= 2


def test_stub_control_state_post_invalid_json_returns_400(stub_base: str) -> None:
    status, _ = _stub_post(stub_base, "/__control/state", b"not-json{", api_key=None)
    assert status == 400

    # State is unchanged -- still up.
    status, body = _stub_get(stub_base, "/__control/state", api_key=None)
    assert body["up"] is True


def test_stub_control_state_post_non_boolean_up_returns_400(stub_base: str) -> None:
    status, _ = _stub_post(stub_base, "/__control/state", b'{"up": "yes"}', api_key=None)
    assert status == 400

    status, body = _stub_get(stub_base, "/__control/state", api_key=None)
    assert body["up"] is True


def test_stub_unknown_path_returns_404(stub_base: str) -> None:
    status, _ = _stub_get(stub_base, "/api/v3/does-not-exist")
    assert status == 404

    status, _ = _stub_get(stub_base, "/totally/unknown", api_key=None)
    assert status == 404


def test_stub_never_logs_request_lines(stub_base: str, capsys: pytest.CaptureFixture[str]) -> None:
    """The stub's log_message is a no-op, so a request never writes to stdout/stderr."""
    capsys.readouterr()  # Clear any output from fixture setup.
    _stub_get(stub_base, "/api/v3/system/status")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


# ---------------------------------------------------------------------------
# fake "triggarr" fixture: a tiny configurable server for checks.py tests
# ---------------------------------------------------------------------------


class _FakeServerState:
    """Mutable per-test state for the fake triggarr server: configured responses and recorded request headers."""

    def __init__(self) -> None:
        self.responses: dict[tuple[str, str], tuple[int, dict[str, str], bytes]] = {}
        self.requests: list[dict[str, str]] = []

    def set_response(
        self, method: str, path: str, status: int, headers: dict[str, str] | None = None, body: bytes = b""
    ) -> None:
        self.responses[(method, path)] = (status, headers or {}, body)


def _make_fake_handler(state: _FakeServerState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _handle(self, method: str) -> None:
            path = self.path.split("?", 1)[0]
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length:
                self.rfile.read(length)
            state.requests.append(dict(self.headers.items()))
            key = (method, path)
            if key not in state.responses:
                self.send_response(HTTPStatus.NOT_FOUND)
                self.end_headers()
                return
            status, headers, body = state.responses[key]
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            self._handle("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._handle("POST")

    return Handler


@pytest.fixture
def fake_server() -> tuple[_FakeServerState, str]:
    """A fake "triggarr" ThreadingHTTPServer whose per-path responses each test configures."""
    state = _FakeServerState()
    handler = _make_fake_handler(state)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()


# ---------------------------------------------------------------------------
# checks.check_health
# ---------------------------------------------------------------------------


def test_check_health_passes(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("GET", "/health", 200, body=b'{"status": "ok"}')
    checks.check_health(base)  # Does not raise.


def test_check_health_fails_on_wrong_body(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("GET", "/health", 200, body=b'{"status": "degraded"}')
    with pytest.raises(checks.SmokeCheckError) as excinfo:
        checks.check_health(base)
    assert excinfo.value.reason == "health"


def test_check_health_fails_on_500(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("GET", "/health", 500, body=b"internal error")
    with pytest.raises(checks.SmokeCheckError) as excinfo:
        checks.check_health(base)
    assert excinfo.value.reason == "health"


# ---------------------------------------------------------------------------
# checks.check_static_assets
# ---------------------------------------------------------------------------


def test_check_static_assets_passes(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    for path in checks.STATIC_ASSETS:
        state.set_response("GET", path, 200, body=b"body-content")
    checks.check_static_assets(base)  # Does not raise.


def test_check_static_assets_fails_on_404(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    for path in checks.STATIC_ASSETS:
        state.set_response("GET", path, 200, body=b"body-content")
    missing_path = checks.STATIC_ASSETS[0]
    state.set_response("GET", missing_path, 404, body=b"")
    with pytest.raises(checks.SmokeCheckError) as excinfo:
        checks.check_static_assets(base)
    assert excinfo.value.reason == "static-asset-missing"
    assert missing_path in str(excinfo.value)


def test_check_static_assets_fails_on_empty_body(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    for path in checks.STATIC_ASSETS:
        state.set_response("GET", path, 200, body=b"body-content")
    empty_path = checks.STATIC_ASSETS[-1]
    state.set_response("GET", empty_path, 200, body=b"")
    with pytest.raises(checks.SmokeCheckError) as excinfo:
        checks.check_static_assets(base)
    assert excinfo.value.reason == "static-asset-missing"
    assert empty_path in str(excinfo.value)


# ---------------------------------------------------------------------------
# checks.check_setup_available / complete_setup / check_setup_closed
# ---------------------------------------------------------------------------


def test_check_setup_available_passes(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("GET", "/setup", 200, body=b'<input name="confirm_password">')
    checks.check_setup_available(base)  # Does not raise.


def test_check_setup_available_fails(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("GET", "/setup", 302, headers={"Location": "/login?setup=done"})
    with pytest.raises(checks.SmokeCheckError) as excinfo:
        checks.check_setup_available(base)
    assert excinfo.value.reason == "setup-unavailable"


def test_complete_setup_returns_cookie_value(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response(
        "POST",
        "/setup",
        200,
        headers={"Set-Cookie": f"{checks.SESSION_COOKIE}=abc123; HttpOnly; Path=/"},
        body=b"Account Created",
    )
    cookie = checks.complete_setup(base, "admin", "irrelevant-test-password")
    assert cookie == "abc123"


def test_complete_setup_fails_without_cookie(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("POST", "/setup", 200, body=b"Account Created")
    with pytest.raises(checks.SmokeCheckError) as excinfo:
        checks.complete_setup(base, "admin", "irrelevant-test-password")
    assert excinfo.value.reason == "setup-failed"


def test_check_setup_closed_passes(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("GET", "/setup", 302, headers={"Location": "/login?setup=done"})
    checks.check_setup_closed(base)  # Does not raise.


def test_check_setup_closed_fails_when_still_open(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("GET", "/setup", 200, body=b'<input name="confirm_password">')
    with pytest.raises(checks.SmokeCheckError) as excinfo:
        checks.check_setup_closed(base)
    assert excinfo.value.reason == "setup-still-open"


# ---------------------------------------------------------------------------
# checks.check_login_rejected / login
# ---------------------------------------------------------------------------


def test_check_login_rejected_passes(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("POST", "/login", 200, body=b"Invalid username or password")
    checks.check_login_rejected(base, "admin", "wrong-test-password")  # Does not raise.


def test_check_login_rejected_fails_when_cookie_issued(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response(
        "POST",
        "/login",
        303,
        headers={"Set-Cookie": f"{checks.SESSION_COOKIE}=should-not-happen; Path=/", "Location": "/"},
    )
    with pytest.raises(checks.SmokeCheckError) as excinfo:
        checks.check_login_rejected(base, "admin", "wrong-test-password")
    assert excinfo.value.reason == "login-accepted-wrong-password"


def test_login_returns_cookie_value(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response(
        "POST",
        "/login",
        303,
        headers={"Set-Cookie": f"{checks.SESSION_COOKIE}=xyz789; Path=/", "Location": "/"},
    )
    cookie = checks.login(base, "admin", "correct-test-password")
    assert cookie == "xyz789"


def test_login_fails_without_redirect(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("POST", "/login", 200, body=b"Invalid username or password")
    with pytest.raises(checks.SmokeCheckError) as excinfo:
        checks.login(base, "admin", "wrong-test-password")
    assert excinfo.value.reason == "login-failed"


# ---------------------------------------------------------------------------
# checks.check_dashboard / check_protected_redirects_to_login
# ---------------------------------------------------------------------------


def test_check_dashboard_passes(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("GET", "/", 200, body=b"<title>Dashboard - Triggarr</title>")
    checks.check_dashboard(base, "some-session-cookie")  # Does not raise.


def test_check_dashboard_fails_on_redirect(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("GET", "/", 302, headers={"Location": "/login"})
    with pytest.raises(checks.SmokeCheckError) as excinfo:
        checks.check_dashboard(base, "stale-session-cookie")
    assert excinfo.value.reason == "dashboard-unreachable"


def test_check_protected_redirects_to_login_passes(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("GET", "/", 302, headers={"Location": "/login?next=%2F"})
    checks.check_protected_redirects_to_login(base)  # Does not raise.


def test_check_protected_redirects_to_login_fails_when_open(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("GET", "/", 200, body=b"<title>Dashboard - Triggarr</title>")
    with pytest.raises(checks.SmokeCheckError) as excinfo:
        checks.check_protected_redirects_to_login(base)
    assert excinfo.value.reason == "protected-page-open"


# ---------------------------------------------------------------------------
# No Origin/Referer headers; redirects never auto-followed
# ---------------------------------------------------------------------------


def test_complete_setup_and_login_send_no_origin_or_referer(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response(
        "POST",
        "/setup",
        200,
        headers={"Set-Cookie": f"{checks.SESSION_COOKIE}=abc123; Path=/"},
        body=b"Account Created",
    )
    state.set_response(
        "POST",
        "/login",
        303,
        headers={"Set-Cookie": f"{checks.SESSION_COOKIE}=xyz789; Path=/", "Location": "/"},
    )

    checks.complete_setup(base, "admin", "irrelevant-test-password")
    checks.login(base, "admin", "irrelevant-test-password")

    assert len(state.requests) == 2
    for headers in state.requests:
        lowered = {k.lower() for k in headers}
        assert "origin" not in lowered
        assert "referer" not in lowered


def test_check_setup_closed_does_not_follow_redirect(fake_server: tuple[_FakeServerState, str]) -> None:
    """A real redirect target is never requested -- only the /setup response itself is inspected."""
    state, base = fake_server
    state.set_response("GET", "/setup", 302, headers={"Location": "/login?setup=done"})
    # No response configured for /login -- if the check followed the redirect, this would 404
    # and the check would (incorrectly) interpret that as still-open or raise an unrelated error.
    checks.check_setup_closed(base)  # Does not raise.


# ---------------------------------------------------------------------------
# expect_failure (D-03)
# ---------------------------------------------------------------------------


def test_expect_failure_passes_on_matching_reason(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    for path in checks.STATIC_ASSETS:
        state.set_response("GET", path, 404)
    checks.expect_failure("static-asset-missing", checks.check_static_assets, base)  # Does not raise.


def test_expect_failure_fails_when_check_passes(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("GET", "/health", 200, body=b'{"status": "ok"}')
    with pytest.raises(checks.SmokeCheckError) as excinfo:
        checks.expect_failure("health", checks.check_health, base)
    assert excinfo.value.reason == "negative-harness"


def test_expect_failure_fails_on_different_reason(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    state.set_response("GET", "/health", 500)
    with pytest.raises(checks.SmokeCheckError) as excinfo:
        checks.expect_failure("static-asset-missing", checks.check_health, base)
    assert excinfo.value.reason == "negative-harness"


# ---------------------------------------------------------------------------
# SmokeCheckError formatting and secrecy
# ---------------------------------------------------------------------------


def test_smoke_check_error_str_format() -> None:
    error = checks.SmokeCheckError("health", "expected 200, got 500")
    assert str(error) == "[health] expected 200, got 500"


def test_smoke_check_error_never_includes_password_or_cookie(fake_server: tuple[_FakeServerState, str]) -> None:
    state, base = fake_server
    secret_password = "super-secret-test-password-999"
    state.set_response("POST", "/setup", 200, body=b"Account Created")  # No cookie -> setup-failed.
    with pytest.raises(checks.SmokeCheckError) as excinfo:
        checks.complete_setup(base, "admin", secret_password)
    assert secret_password not in str(excinfo.value)

    state.set_response(
        "POST",
        "/login",
        303,
        headers={"Set-Cookie": f"{checks.SESSION_COOKIE}=top-secret-cookie-value; Path=/", "Location": "/"},
    )
    cookie = checks.login(base, "admin", secret_password)
    with pytest.raises(checks.SmokeCheckError) as excinfo:
        checks.check_dashboard(base, cookie)
    assert cookie not in str(excinfo.value)
