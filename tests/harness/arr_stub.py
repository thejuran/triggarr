"""Minimal stdlib-only stub *arr HTTP service for CI smoke and browser tests.

Answers the narrow set of *arr endpoints Triggarr's startup validation, count
refresh, and search cycle call, with a runtime-togglable connected/disconnected
state via a control endpoint. Stdlib-only (http.server, json, threading) so it
can run inside the shipped image's Python with no extra packages installed --
Plan 04 mounts this module read-only into a disposable stub container next to
the audited image under test. Not shipped in the product image itself
(tests/ is excluded via .dockerignore).
"""

from __future__ import annotations

import argparse
import json
import os
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

_PAGINATED_PATHS = (
    "/api/v3/wanted/missing",
    "/api/v3/wanted/cutoff",
    "/api/v3/movie",
)
_EMPTY_LIST_PATHS = (
    "/api/v3/tag",
    "/api/v3/history/movie",
)
_STATUS_PATHS = ("/api/v3/system/status",)


def _paginated_envelope() -> dict[str, Any]:
    """Return an empty PaginatedResponse envelope (page/pageSize/sortKey/totalRecords/records)."""
    return {"page": 1, "pageSize": 1, "sortKey": "id", "totalRecords": 0, "records": []}


class _StubState:
    """Mutable, lock-protected state shared across request handler instances."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.up = True
        self.api_requests = 0

    def record_api_request(self) -> None:
        with self._lock:
            self.api_requests += 1

    def snapshot(self) -> tuple[bool, int]:
        with self._lock:
            return self.up, self.api_requests

    def set_up(self, value: bool) -> None:
        with self._lock:
            self.up = value


def _make_handler(api_key: str, state: _StubState) -> type[BaseHTTPRequestHandler]:
    """Build a BaseHTTPRequestHandler subclass closing over this server's api_key and state."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "TriggarrArrStub/1.0"

        def log_message(self, format: str, *args: Any) -> None:
            """No-op: never write a request line (or its headers) anywhere (T-82-07)."""
            return

        def _send_json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_body(self) -> bytes:
            length = int(self.headers.get("Content-Length", 0) or 0)
            return self.rfile.read(length) if length else b""

        def _authorized(self) -> bool:
            return self.headers.get("X-Api-Key") == api_key

        def _handle_control_state_get(self) -> None:
            up, count = state.snapshot()
            self._send_json(HTTPStatus.OK, {"up": up, "api_requests": count})

        def _handle_control_state_post(self) -> None:
            raw = self._read_body()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON body"})
                return
            if not isinstance(payload, dict) or not isinstance(payload.get("up"), bool):
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "'up' must be a boolean"})
                return
            state.set_up(payload["up"])
            self._send_json(HTTPStatus.OK, {"up": payload["up"]})

        def _handle_api_get(self, path: str) -> None:
            state.record_api_request()
            if not self._authorized():
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            up, _ = state.snapshot()
            if not up:
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "service unavailable"})
                return
            if path in _STATUS_PATHS:
                self._send_json(HTTPStatus.OK, {"version": "5.0.0.0", "appName": "TriggarrArrStub"})
                return
            if path in _PAGINATED_PATHS:
                self._send_json(HTTPStatus.OK, _paginated_envelope())
                return
            if path in _EMPTY_LIST_PATHS:
                self._send_json(HTTPStatus.OK, [])
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def _handle_api_post(self, path: str) -> None:
            state.record_api_request()
            if not self._authorized():
                self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
                return
            up, _ = state.snapshot()
            if not up:
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "service unavailable"})
                return
            if path == "/api/v3/command":
                self._send_json(HTTPStatus.CREATED, {"id": 1})
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler method name
            path = self.path.split("?", 1)[0]
            if path == "/__control/state":
                self._handle_control_state_get()
                return
            if path.startswith("/api/"):
                self._handle_api_get(path)
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler method name
            path = self.path.split("?", 1)[0]
            if path == "/__control/state":
                self._handle_control_state_post()
                return
            if path.startswith("/api/"):
                self._handle_api_post(path)
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    return Handler


def build_server(host: str, port: int, api_key: str) -> ThreadingHTTPServer:
    """Build a stub *arr ThreadingHTTPServer bound to (host, port).

    The caller is responsible for serving it (typically from a background
    thread) and shutting it down, e.g.::

        server = build_server("127.0.0.1", 0, "test-stub-key")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        ...
        server.shutdown()
        server.server_close()
    """
    state = _StubState()
    handler = _make_handler(api_key, state)
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    """Run the stub as a standalone script (Plan 04's stub container entry point)."""
    parser = argparse.ArgumentParser(description="Stub *arr HTTP service for CI smoke tests.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()
    api_key = os.environ.get("STUB_API_KEY", "")
    server = build_server(args.host, args.port, api_key)
    server.serve_forever()


if __name__ == "__main__":
    main()
