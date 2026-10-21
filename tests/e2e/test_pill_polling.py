"""Behavioral connection-pill regression test (D-02, D-28, D-29).

The existing guard in tests/test_header_redesign.py only checks template text.
This test proves the runtime behavior: requests stay bounded with no request
loop, polling continues on a schedule, and the pill actually reflects a real
backend state change between polls.

Renders no credential or API-key page: a session cookie is obtained over
plain HTTP (never a rendered login form) and injected into the browser
context before any page is loaded; the only page visited is "/", and the
only partial polled is the connection pill -- neither shows a credential or
an API key. This test file carries no capture-restricting marker.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import Credentials, SensitiveRegistry, StubControl, TriggarrContainer
from tests.harness import checks

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page

PILL_PATH = "/partials/connection-pill"


def _wait_for_startup_connected(page: Page, base_url: str, *, timeout_seconds: float) -> None:
    """Poll the pill partial directly (no DOM) until the startup cycle reaches the stub."""
    deadline = time.monotonic() + timeout_seconds
    last_body = ""
    while time.monotonic() < deadline:
        response = page.request.get(f"{base_url}{PILL_PATH}")
        last_body = response.text()
        if "Connection Stable" in last_body:
            return
        time.sleep(1.0)
    pytest.fail(f"stub never reported connected within {timeout_seconds}s; last pill body: {last_body!r}")


def _wait_for_request_count(pill_requests: list[str], minimum: int, *, timeout_seconds: float) -> None:
    """Poll the recorded request list (real time) until it reaches ``minimum`` entries.

    A "request" event fires once the browser sends the request, not once the
    response has been processed into the DOM -- this only proves a scheduled
    tick actually fired a new fetch, not that the swap has happened yet.
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if len(pill_requests) >= minimum:
            return
        time.sleep(0.25)
    pytest.fail(
        f"connection pill did not refresh after a scheduled interval: "
        f"expected at least {minimum} requests, saw {len(pill_requests)}"
    )


def _wait_for_pill_text(page: Page, expected: str, *, timeout_seconds: float) -> None:
    """Poll the pill's rendered text (real time) until it contains ``expected``.

    The browser clock only virtualizes JS timers, never network I/O, so the
    real HTTP round-trip triggered by a fired tick still takes real wall-clock
    time to land in the DOM after ``fast_forward`` returns.
    """
    deadline = time.monotonic() + timeout_seconds
    seen = ""
    while time.monotonic() < deadline:
        seen = page.locator("#connection-pill").inner_text()
        if expected in seen:
            return
        time.sleep(0.25)
    pytest.fail(f"connection pill did not refresh after a scheduled interval: expected {expected!r}, saw {seen!r}")


def test_connection_pill_polls_on_schedule_without_loop_and_shows_new_state(
    admin_container: TriggarrContainer,
    stub_control: StubControl,
    credentials: Credentials,
    sensitive_registry: SensitiveRegistry,
    page: Page,
    context: BrowserContext,
) -> None:
    """Bounded requests, continued polling on schedule, and a real state change (D-28)."""
    base_url = admin_container.url

    # 1. Authenticate over plain HTTP (no rendered login form); inject the cookie.
    cookie = checks.login(base_url, credentials.username, credentials.password)
    sensitive_registry.register(cookie)
    context.add_cookies([{"name": "triggarr_session", "value": cookie, "url": base_url}])

    # 2. Wait (bounded real time) for the startup search cycle to reach the stub.
    _wait_for_startup_connected(page, base_url, timeout_seconds=45)

    # 3. Track every pill request, install the clock, then load the page.
    pill_requests: list[str] = []
    page.on("request", lambda request: pill_requests.append(request.url) if PILL_PATH in request.url else None)
    page.clock.install()
    page.goto(f"{base_url}/")
    expect(page.locator("#connection-pill")).to_contain_text("Connection Stable", timeout=10_000)

    # 4. Loop guard: real time only, clock still paused -- no scheduled tick is due.
    time.sleep(3)
    looped_count = len(pill_requests)
    assert 1 <= looped_count <= 2, f"connection pill request loop: {looped_count} requests without any scheduled tick"

    # 5. Change backend state: stub goes down, a count refresh records the instance as disconnected.
    stub_control.set_up(False)
    refresh_response = page.request.post(f"{base_url}/api/refresh-counts/radarr/ci-stub")
    assert refresh_response.status == 200, f"refresh-counts returned {refresh_response.status}"

    # 6. First scheduled tick: advance the browser clock past the 30s interval.
    page.clock.fast_forward("00:31")
    _wait_for_request_count(pill_requests, looped_count + 1, timeout_seconds=10)
    _wait_for_pill_text(page, "Connection Issue", timeout_seconds=10)

    # 7. Second scheduled tick: polling continues on schedule, not just once.
    page.clock.fast_forward("00:31")
    _wait_for_request_count(pill_requests, looped_count + 2, timeout_seconds=10)

    # 8. Bounded total: a range with tolerance, never an exact count at a fragile deadline (D-28).
    final_count = len(pill_requests)
    assert 3 <= final_count <= 5, f"expected 3-5 total pill requests after two scheduled ticks, saw {final_count}"
