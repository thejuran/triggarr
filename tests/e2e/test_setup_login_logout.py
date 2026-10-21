"""Browser assertions of D-25's three flows: first-run setup, login, logout.

Replicates tests/test_auth_integration.py::test_full_setup_login_use_logout_flow
as real browser interactions against a fresh container of the exact shipped
image, instead of FastAPI's TestClient.

Every test here renders a credential or API-key page (setup, login, logout),
so the whole module is marked credential_pages: tests/e2e/conftest.py's
capture-policy guard (D-33) refuses to run any of these with tracing,
screenshots or video enabled.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Browser, Page, expect

from tests.e2e.conftest import Credentials, SensitiveRegistry, TriggarrContainer

pytestmark = pytest.mark.credential_pages


def test_first_run_setup_creates_admin_and_closes_setup(
    page: Page,
    triggarr_container: TriggarrContainer,
    credentials: Credentials,
    sensitive_registry: SensitiveRegistry,
    browser: Browser,
) -> None:
    """Fresh container -> setup creates the admin -> dashboard; /setup then redirects to /login."""
    page.goto(f"{triggarr_container.url}/")
    expect(page).to_have_url(re.compile(r"/setup$"))

    page.fill("#username", credentials.username)
    page.fill("#password", credentials.password)
    page.fill("#confirm_password", credentials.password)
    page.click("button[type=submit]")

    expect(page.get_by_text("Account Created")).to_be_visible()
    api_key = page.locator("#api-key-display").inner_text()
    sensitive_registry.register(api_key)

    page.goto(f"{triggarr_container.url}/")
    expect(page).to_have_title("Dashboard - Triggarr")

    # Setup is no longer available afterward -- a brand-new browser context
    # (no session cookie) hitting /setup is redirected to /login.
    fresh_context = browser.new_context()
    try:
        fresh_page = fresh_context.new_page()
        fresh_page.goto(f"{triggarr_container.url}/setup")
        expect(fresh_page).to_have_url(re.compile(r"/login"))
        for cookie in fresh_context.cookies():
            if cookie["name"] == "triggarr_session":
                sensitive_registry.register(cookie["value"])
    finally:
        fresh_context.close()


def test_wrong_password_keeps_protected_pages_locked(
    page: Page,
    admin_container: TriggarrContainer,
    credentials: Credentials,
) -> None:
    """A wrong password leaves the user on /login with an error and issues no session."""
    page.goto(f"{admin_container.url}/login")
    page.fill("#username", credentials.username)
    page.fill("#password", "this-is-not-the-right-password")
    page.click("button[type=submit]")

    expect(page.get_by_text("Invalid username or password")).to_be_visible()
    expect(page).to_have_url(re.compile(r"/login$"))
    assert not any(cookie["name"] == "triggarr_session" for cookie in page.context.cookies())

    page.goto(f"{admin_container.url}/")
    expect(page).to_have_url(re.compile(r"/login"))


def test_valid_login_reaches_dashboard(
    page: Page,
    admin_container: TriggarrContainer,
    credentials: Credentials,
    sensitive_registry: SensitiveRegistry,
) -> None:
    """Valid credentials reach the dashboard."""
    page.goto(f"{admin_container.url}/login")
    page.fill("#username", credentials.username)
    page.fill("#password", credentials.password)
    page.click("button[type=submit]")

    expect(page).to_have_title("Dashboard - Triggarr")
    for cookie in page.context.cookies():
        if cookie["name"] == "triggarr_session":
            sensitive_registry.register(cookie["value"])


def test_logout_ends_session(
    page: Page,
    admin_container: TriggarrContainer,
    credentials: Credentials,
    sensitive_registry: SensitiveRegistry,
) -> None:
    """Logout returns to /login and a fresh request to a protected page redirects to /login."""
    page.goto(f"{admin_container.url}/login")
    page.fill("#username", credentials.username)
    page.fill("#password", credentials.password)
    page.click("button[type=submit]")
    expect(page).to_have_title("Dashboard - Triggarr")
    for cookie in page.context.cookies():
        if cookie["name"] == "triggarr_session":
            sensitive_registry.register(cookie["value"])

    page.get_by_role("button", name="Logout").click()

    expect(page).to_have_url(re.compile(r"/login$"))
    assert not any(cookie["name"] == "triggarr_session" for cookie in page.context.cookies())

    page.goto(f"{admin_container.url}/")
    expect(page).to_have_url(re.compile(r"/login"))
