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


def test_config_path_follows_current_config_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_config_path() should derive triggarr.toml from the current config dir."""
    monkeypatch.setenv("TRIGGARR_CONFIG_DIR", "/data")
    from triggarr.models.config import get_config_path

    assert get_config_path() == Path("/data/triggarr.toml")


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


def test_default_state_read_write_paths_follow_current_config_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Default load_state()/save_state() paths derive from the current config dir."""
    monkeypatch.setenv("TRIGGARR_CONFIG_DIR", str(tmp_path))
    from triggarr.state import TriggarrState, load_state, save_state

    expected_path = tmp_path / "state.json"
    state = TriggarrState(radarr={}, sonarr={}, lidarr={}, search_log=[])

    save_state(state)
    loaded = load_state()

    assert expected_path.exists()
    assert loaded == state


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


async def test_lifespan_derives_sqlite_path_from_injected_state_path(tmp_path: Path) -> None:
    """create_lifespan() should place triggarr.db beside the injected state path."""
    from unittest.mock import AsyncMock, patch

    from fastapi import FastAPI

    from triggarr.models.config import Settings
    from triggarr.search.scheduler import create_lifespan

    state_path = tmp_path / "custom-config" / "state.json"
    config_path = tmp_path / "custom-config" / "triggarr.toml"
    expected_db_path = state_path.parent / "triggarr.db"

    fake_db = AsyncMock()
    fake_scheduler = _FakeScheduler()

    app = FastAPI(lifespan=create_lifespan(Settings(), state_path, config_path))
    lifespan = app.router.lifespan_context

    with (
        patch("triggarr.search.scheduler.aiosqlite.connect", AsyncMock(return_value=fake_db)) as mock_connect,
        patch("triggarr.search.scheduler.init_db", new_callable=AsyncMock) as mock_init_db,
        patch("triggarr.search.scheduler.AsyncIOScheduler", return_value=fake_scheduler),
    ):
        async with lifespan(app):
            assert app.state.config_path == config_path
            assert app.state.state_path == state_path

    mock_connect.assert_awaited_once_with(expected_db_path)
    mock_init_db.assert_awaited_once_with(fake_db, expected_db_path)
    assert fake_scheduler.started is True
    assert fake_scheduler.shutdown_wait is False


class _FakeScheduler:
    """Small scheduler stand-in for lifespan path wiring tests."""

    def __init__(self) -> None:
        self.started = False
        self.shutdown_wait: bool | None = None
        self.jobs: list[tuple[tuple, dict]] = []

    def add_job(self, *args, **kwargs) -> None:
        self.jobs.append((args, kwargs))

    def start(self) -> None:
        self.started = True

    def shutdown(self, wait: bool = True) -> None:
        self.shutdown_wait = wait
