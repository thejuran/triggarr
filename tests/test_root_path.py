"""Tests for reverse proxy support (ROOT_PATH + proxy headers).

Verifies that when ROOT_PATH is set, uvicorn root_path is configured
and all URLs (static assets, nav links, htmx endpoints) respect the prefix.
Also verifies proxy_headers is enabled so X-Forwarded-Proto is respected.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_root_path_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """When ROOT_PATH is not set, root_path defaults to empty string."""
    monkeypatch.delenv("ROOT_PATH", raising=False)
    from triggarr.__main__ import get_root_path

    assert get_root_path() == ""


def test_root_path_custom(monkeypatch: pytest.MonkeyPatch) -> None:
    """When ROOT_PATH is set, it is returned."""
    monkeypatch.setenv("ROOT_PATH", "/triggarr")
    from triggarr.__main__ import get_root_path

    assert get_root_path() == "/triggarr"


def test_nav_links_use_url_for() -> None:
    """Nav links in base.html should use url_for instead of hardcoded paths."""
    base_html = Path(__file__).resolve().parent.parent / "triggarr" / "templates" / "base.html"
    content = base_html.read_text()

    # Should NOT have hardcoded nav links
    assert 'href="/"' not in content, "Dashboard link should use url_for, not hardcoded '/'"
    assert 'href="/history"' not in content, "History link should use url_for, not hardcoded '/history'"
    assert 'href="/settings"' not in content, "Settings link should use url_for, not hardcoded '/settings'"

    # Should use url_for (or request.url_for)
    assert "url_for" in content, "base.html should use url_for for nav links"


def test_proxy_headers_enabled() -> None:
    """Uvicorn config includes proxy_headers so X-Forwarded-Proto is respected."""
    import inspect

    from triggarr.__main__ import _run

    source = inspect.getsource(_run)
    assert "proxy_headers=True" in source
    assert "forwarded_allow_ips" in source
