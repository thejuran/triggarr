"""Integration tests proving the upgrade path end-to-end (R-05).

Each test starts from a pre-upgrade state.json (legacy ``last_success``, no
``last_cycle``), loads it via ``load_state``, runs the REAL engine cycle
function against an ``AsyncMock`` *arr client plus a real aiosqlite db, then
renders the resulting state through the actual
``/partials/app-card/{app}/{instance}`` route and asserts on the HTML.

This is deliberately an integration test, not a unit test on ``cycle_view``
or ``_build_app_context`` in isolation (those are covered by
tests/test_search.py and tests/test_app_cards.py) -- it proves the pre-upgrade
``last_success`` value never renders as a confirmed search once the engine
has run, for an empty cycle, a cycle whose commands failed, and a cycle that
could not even reach the *arr.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from triggarr.db import init_db
from triggarr.search.engine import run_lidarr_cycle, run_radarr_cycle, run_sonarr_cycle
from triggarr.state import load_state
from triggarr.web.routes import STATIC_DIR, _exact_time_filter, router


@pytest.fixture
def card_app(tmp_path):
    """Minimal FastAPI app for rendering /partials/app-card/* (mirrors tests/test_app_cards.py).

    No database is attached -- the card route never touches app.state.db;
    each test opens its own real aiosqlite connection to drive the engine.
    """
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    app.state.settings = make_settings()
    app.state.triggarr_state = {}

    mock_scheduler = MagicMock()
    mock_job = MagicMock()
    mock_job.next_run_time = None
    mock_scheduler.get_job.return_value = mock_job
    app.state.scheduler = mock_scheduler

    app.state.config_path = tmp_path / "triggarr.toml"
    app.state.state_path = tmp_path / "state.json"
    app.state.search_lock = asyncio.Lock()
    app.state.last_search_time = {}
    app.state.last_health_check = None

    return app


@pytest.fixture
def card_client(card_app):
    return TestClient(card_app)


def _write_pre_upgrade_state(tmp_path: Path, app_name: str) -> Path:
    """Write a pre-upgrade state.json: {app_name}/Default has a legacy last_success, no last_cycle."""
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                app_name: {
                    "Default": {
                        "last_success": "2026-01-01T00:00:00Z",
                        "last_run": "2026-01-01T00:00:00Z",
                        "connected": True,
                    }
                }
            }
        )
    )
    return state_file


def _success_row(response_text: str) -> str:
    """Isolate the 'Last successful search:' / 'Last success (legacy):' row's value."""
    return response_text.split("Last successful search:")[1].split("</div>")[0]


async def test_upgrade_then_empty_cycle_never_shows_legacy_as_confirmed(tmp_path, card_app, card_client):
    """R-05: Radarr's empty first cycle after upgrade never shows the legacy value as confirmed."""
    state_file = _write_pre_upgrade_state(tmp_path, "radarr")
    loaded = load_state(state_file)
    settings = make_settings()
    card_app.state.settings = settings
    card_app.state.triggarr_state = loaded

    # Before the first new-model cycle: "Not run yet" + the legacy label (D-14).
    pre_response = card_client.get("/partials/app-card/radarr/Default")
    assert pre_response.status_code == 200
    assert "Not run yet" in pre_response.text
    assert "Last success (legacy):" in pre_response.text

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=0)
    instance_config = settings.get_enabled_instances("radarr")["Default"]

    result = await run_radarr_cycle(client, loaded, "Default", instance_config, settings, db)
    await db.close()

    card_app.state.triggarr_state = result
    response = card_client.get("/partials/app-card/radarr/Default")

    assert response.status_code == 200
    assert "Nothing needed searching" in response.text
    assert "Last successful search:" in response.text
    assert "Never" in _success_row(response.text)
    assert "Last success (legacy)" not in response.text
    assert "2026-01-01 00:00:00 UTC" not in response.text
    # The legacy value is kept verbatim in state for the downgrade fallback (78-01 <rollback>).
    assert result["radarr"]["Default"]["last_success"] == "2026-01-01T00:00:00Z"


async def test_upgrade_then_failed_commands_never_shows_legacy_as_confirmed(tmp_path, card_app, card_client):
    """R-05: a cycle whose only outcome is failed commands never shows the legacy value as confirmed."""
    state_file = _write_pre_upgrade_state(tmp_path, "radarr")
    loaded = load_state(state_file)
    settings = make_settings()
    card_app.state.settings = settings
    card_app.state.triggarr_state = loaded

    pre_response = card_client.get("/partials/app-card/radarr/Default")
    assert "Not run yet" in pre_response.text
    assert "Last success (legacy):" in pre_response.text

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    request = httpx.Request("POST", "http://test/api/v3/command")
    response_500 = httpx.Response(500, request=request)
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Movie A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=1)
    client.search_movies = AsyncMock(
        side_effect=httpx.HTTPStatusError("Internal Server Error", request=request, response=response_500)
    )
    instance_config = settings.get_enabled_instances("radarr")["Default"]

    result = await run_radarr_cycle(client, loaded, "Default", instance_config, settings, db)
    await db.close()

    card_app.state.triggarr_state = result
    response = card_client.get("/partials/app-card/radarr/Default")

    assert response.status_code == 200
    assert "Failed · 0 accepted, 1 failed" in response.text
    assert "Last successful search:" in response.text
    assert "Never" in _success_row(response.text)
    assert "2026-01-01 00:00:00 UTC" not in response.text


async def test_upgrade_then_fetch_failure_never_shows_legacy_as_confirmed(tmp_path, card_app, card_client):
    """R-05: a cycle that can't even reach Radarr never shows the legacy value as confirmed."""
    state_file = _write_pre_upgrade_state(tmp_path, "radarr")
    loaded = load_state(state_file)
    settings = make_settings()
    card_app.state.settings = settings
    card_app.state.triggarr_state = loaded

    pre_response = card_client.get("/partials/app-card/radarr/Default")
    assert "Not run yet" in pre_response.text
    assert "Last success (legacy):" in pre_response.text

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))
    instance_config = settings.get_enabled_instances("radarr")["Default"]

    result = await run_radarr_cycle(client, loaded, "Default", instance_config, settings, db)
    await db.close()

    card_app.state.triggarr_state = result
    response = card_client.get("/partials/app-card/radarr/Default")

    assert response.status_code == 200
    assert "Failed · couldn't reach Radarr" in response.text
    assert "Last successful search:" in response.text
    assert "Never" in _success_row(response.text)
    assert "2026-01-01 00:00:00 UTC" not in response.text


async def test_upgrade_then_success_shows_new_time(tmp_path, card_app, card_client):
    """R-05: once a cycle accepts >=1 command, the confirmed time is the new one, never the legacy value."""
    state_file = _write_pre_upgrade_state(tmp_path, "radarr")
    loaded = load_state(state_file)
    settings = make_settings()
    card_app.state.settings = settings
    card_app.state.triggarr_state = loaded

    pre_response = card_client.get("/partials/app-card/radarr/Default")
    assert "Not run yet" in pre_response.text
    assert "Last success (legacy):" in pre_response.text

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Movie A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=1)
    client.search_movies = AsyncMock()
    instance_config = settings.get_enabled_instances("radarr")["Default"]

    result = await run_radarr_cycle(client, loaded, "Default", instance_config, settings, db)
    await db.close()

    card_app.state.triggarr_state = result
    response = card_client.get("/partials/app-card/radarr/Default")

    assert response.status_code == 200
    assert "Success · 1 accepted, 0 failed" in response.text
    confirmed = result["radarr"]["Default"]["last_successful_search"]
    assert confirmed is not None
    assert f'title="{_exact_time_filter(confirmed)}"' in response.text
    assert "2026-01-01 00:00:00 UTC" not in response.text


async def test_upgrade_then_empty_cycle_sonarr(tmp_path, card_app, card_client):
    """R-05: Sonarr's empty first cycle after upgrade never shows the legacy value as confirmed."""
    state_file = _write_pre_upgrade_state(tmp_path, "sonarr")
    loaded = load_state(state_file)
    settings = make_settings()
    card_app.state.settings = settings
    card_app.state.triggarr_state = loaded

    pre_response = card_client.get("/partials/app-card/sonarr/Default")
    assert "Not run yet" in pre_response.text
    assert "Last success (legacy):" in pre_response.text

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=0)
    instance_config = settings.get_enabled_instances("sonarr")["Default"]

    result = await run_sonarr_cycle(client, loaded, "Default", instance_config, settings, db)
    await db.close()

    card_app.state.triggarr_state = result
    response = card_client.get("/partials/app-card/sonarr/Default")

    assert response.status_code == 200
    assert "Nothing needed searching" in response.text
    assert "Last successful search:" in response.text
    assert "Never" in _success_row(response.text)
    assert "2026-01-01 00:00:00 UTC" not in response.text


async def test_upgrade_then_empty_cycle_lidarr(tmp_path, card_app, card_client):
    """R-05: Lidarr's empty first cycle after upgrade never shows the legacy value as confirmed."""
    state_file = _write_pre_upgrade_state(tmp_path, "lidarr")
    loaded = load_state(state_file)
    settings = make_settings()
    card_app.state.settings = settings
    card_app.state.triggarr_state = loaded

    pre_response = card_client.get("/partials/app-card/lidarr/Default")
    assert "Not run yet" in pre_response.text
    assert "Last success (legacy):" in pre_response.text

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=0)
    instance_config = settings.get_enabled_instances("lidarr")["Default"]

    result = await run_lidarr_cycle(client, loaded, "Default", instance_config, settings, db)
    await db.close()

    card_app.state.triggarr_state = result
    response = card_client.get("/partials/app-card/lidarr/Default")

    assert response.status_code == 200
    assert "Nothing needed searching" in response.text
    assert "Last successful search:" in response.text
    assert "Never" in _success_row(response.text)
    assert "2026-01-01 00:00:00 UTC" not in response.text
