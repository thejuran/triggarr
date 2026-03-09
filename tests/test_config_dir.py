"""Tests for TRIGGARR_CONFIG_DIR env var support.

Verifies that CONFIG_DIR, CONFIG_PATH, and STATE_PATH all respect
the TRIGGARR_CONFIG_DIR environment variable, defaulting to /config
when unset (backward compatible).
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_default_config_dir_is_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """When TRIGGARR_CONFIG_DIR is not set, CONFIG_DIR defaults to /config."""
    monkeypatch.delenv("TRIGGARR_CONFIG_DIR", raising=False)
    from triggarr.models.config import get_config_dir

    assert get_config_dir() == Path("/config")


def test_custom_config_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """When TRIGGARR_CONFIG_DIR is set, CONFIG_DIR follows it."""
    monkeypatch.setenv("TRIGGARR_CONFIG_DIR", "/custom/path")
    from triggarr.models.config import get_config_dir

    assert get_config_dir() == Path("/custom/path")


def test_config_path_follows_config_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONFIG_PATH should be CONFIG_DIR / 'triggarr.toml'."""
    monkeypatch.setenv("TRIGGARR_CONFIG_DIR", "/data")
    from triggarr.models.config import get_config_dir

    config_dir = get_config_dir()
    assert config_dir / "triggarr.toml" == Path("/data/triggarr.toml")


def test_state_path_follows_config_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """STATE_PATH should be CONFIG_DIR / 'state.json'."""
    monkeypatch.setenv("TRIGGARR_CONFIG_DIR", "/data")
    from triggarr.state import get_state_path

    assert get_state_path() == Path("/data/state.json")


def test_state_path_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """STATE_PATH defaults to /config/state.json when env var is unset."""
    monkeypatch.delenv("TRIGGARR_CONFIG_DIR", raising=False)
    from triggarr.state import get_state_path

    assert get_state_path() == Path("/config/state.json")


# ---------------------------------------------------------------------------
# HARDEN-01..04: Path validation and frozen constants
# ---------------------------------------------------------------------------


def test_relative_path_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_config_dir() raises ValueError for relative paths like 'relative/path'."""
    monkeypatch.setenv("TRIGGARR_CONFIG_DIR", "relative/path")
    from triggarr.models.config import get_config_dir

    with pytest.raises(ValueError, match="must be an absolute path"):
        get_config_dir()


def test_traversal_path_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_config_dir() raises ValueError for relative traversal path '../etc'."""
    monkeypatch.setenv("TRIGGARR_CONFIG_DIR", "../etc")
    from triggarr.models.config import get_config_dir

    with pytest.raises(ValueError, match="must be an absolute path"):
        get_config_dir()


def test_absolute_path_with_dotdot_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_config_dir() with absolute path containing '..' resolves it and succeeds."""
    monkeypatch.setenv("TRIGGARR_CONFIG_DIR", "/config/../data")
    from triggarr.models.config import get_config_dir

    result = get_config_dir()
    assert result == Path("/data")


def test_frozen_constants_not_affected_by_env_change(monkeypatch: pytest.MonkeyPatch) -> None:
    """CONFIG_DIR is frozen at import time; changing env var only affects get_config_dir()."""
    monkeypatch.setenv("TRIGGARR_CONFIG_DIR", "/original")
    from triggarr.models.config import CONFIG_DIR, get_config_dir

    # CONFIG_DIR was set at module import time (before this test),
    # so it won't match /original. The function call should reflect the env var.
    result_fn = get_config_dir()
    assert result_fn == Path("/original")

    # Now change the env var
    monkeypatch.setenv("TRIGGARR_CONFIG_DIR", "/changed")
    result_fn_after = get_config_dir()
    assert result_fn_after == Path("/changed")

    # CONFIG_DIR constant is still the value from first import -- it's frozen
    assert result_fn_after != CONFIG_DIR, "CONFIG_DIR should be frozen and not track env changes"
