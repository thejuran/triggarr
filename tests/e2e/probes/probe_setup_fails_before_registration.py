"""Probe: setup fails before the generated API key is ever registered (D-33).

Deliberately asserts False right after reading the displayed API key and
before any ``SensitiveRegistry.register`` call -- proving the byte scanner
never even knows the key. Prevention (the credential_pages capture guard) is
the real guarantee here; the byte scanner is only an extra defence (Task 2)
and this probe shows it has nothing to find in this scenario because the
value was never registered, not because the scanner is clever.

File name does not match ``test_*.py`` so the normal browser-e2e run never
collects it -- it is only ever invoked directly as its own pytest target by
tests/e2e/test_capture_policy.py (subprocess) and
tests/test_e2e_capture_guard.py (subprocess, no Docker, no browser -- this
probe is never actually executed there because the capture guard rejects
the selection before any fixture runs).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from playwright.sync_api import Page

from tests.e2e.conftest import (
    PROBE_KEY_DIGEST_FILE_ENV,
    PROBE_KEY_SALT_ENV,
    Credentials,
    TriggarrContainer,
    api_key_handoff,
)

pytestmark = pytest.mark.credential_pages


def probe_setup_fails_before_registration(
    page: Page, triggarr_container: TriggarrContainer, credentials: Credentials
) -> None:
    page.goto(f"{triggarr_container.url}/")
    page.fill("#username", credentials.username)
    page.fill("#password", credentials.password)
    page.fill("#confirm_password", credentials.password)
    page.click("button[type=submit]")
    page.wait_for_selector("text=Account Created")

    api_key = page.locator("#api-key-display").inner_text()

    # Hand the parent only a salted fingerprint of the key, never the key itself -- and only for a value of the
    # real key shape, so a blank display leaves no file and the parent's check fails instead of passing.
    digest_file = os.environ.get(PROBE_KEY_DIGEST_FILE_ENV)
    salt_hex = os.environ.get(PROBE_KEY_SALT_ENV)
    if digest_file and salt_hex:
        digest = api_key_handoff(api_key, salt_hex)
        if digest is not None:
            Path(digest_file).write_text(digest)

    assert False, "probe: deliberate failure before registration"  # noqa: B011
