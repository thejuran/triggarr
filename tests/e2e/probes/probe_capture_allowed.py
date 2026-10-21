"""Trivial probe with no fixtures and no credential_pages marker.

Used only to prove a non-credential-page selection with capture enabled is
allowed by the capture-policy guard (tests/e2e/conftest.py's
pytest_collection_finish) -- it never touches Docker, Playwright, or any
fixture, so its presence in a sentinel file proves setup actually ran.
"""

from __future__ import annotations


def probe_capture_allowed() -> None:
    assert True
