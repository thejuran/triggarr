"""Tests for TRIGGARR_CONFIG_DIR env var support.

Verifies that CONFIG_DIR, CONFIG_PATH, and STATE_PATH all respect
the TRIGGARR_CONFIG_DIR environment variable, defaulting to /config
when unset (backward compatible).
"""

from __future__ import annotations

from pathlib import Path


def test_default_config_dir_is_config(monkeypatch: "pytest.MonkeyPatch") -> None:
    """When TRIGGARR_CONFIG_DIR is not set, CONFIG_DIR defaults to /config."""
    monkeypatch.delenv("TRIGGARR_CONFIG_DIR", raising=False)
    from triggarr.models.config import get_config_dir

    assert get_config_dir() == Path("/config")


def test_custom_config_dir(monkeypatch: "pytest.MonkeyPatch") -> None:
    """When TRIGGARR_CONFIG_DIR is set, CONFIG_DIR follows it."""
    monkeypatch.setenv("TRIGGARR_CONFIG_DIR", "/custom/path")
    from triggarr.models.config import get_config_dir

    assert get_config_dir() == Path("/custom/path")


def test_config_path_follows_config_dir(monkeypatch: "pytest.MonkeyPatch") -> None:
    """CONFIG_PATH should be CONFIG_DIR / 'triggarr.toml'."""
    monkeypatch.setenv("TRIGGARR_CONFIG_DIR", "/data")
    from triggarr.models.config import get_config_dir

    config_dir = get_config_dir()
    assert config_dir / "triggarr.toml" == Path("/data/triggarr.toml")


def test_state_path_follows_config_dir(monkeypatch: "pytest.MonkeyPatch") -> None:
    """STATE_PATH should be CONFIG_DIR / 'state.json'."""
    monkeypatch.setenv("TRIGGARR_CONFIG_DIR", "/data")
    from triggarr.state import get_state_path

    assert get_state_path() == Path("/data/state.json")


def test_state_path_default(monkeypatch: "pytest.MonkeyPatch") -> None:
    """STATE_PATH defaults to /config/state.json when env var is unset."""
    monkeypatch.delenv("TRIGGARR_CONFIG_DIR", raising=False)
    from triggarr.state import get_state_path

    assert get_state_path() == Path("/config/state.json")
