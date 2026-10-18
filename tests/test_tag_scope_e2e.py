"""End-to-end proof: real engine -> real card/refresh routes (Phase 79-03).

Each test drives the REAL ``run_*_cycle``/``refresh_*_counts`` engine
functions against an ``AsyncMock`` *arr client plus a real aiosqlite db
(cycle tests) or the real ``/api/refresh-counts`` route (refresh tests),
then renders the resulting state through the actual
``/partials/app-card/{app}/{instance}`` route and asserts on the HTML.

This is deliberately an integration test, not a unit test on
``_resolve_tag_scope``, ``cycle_view``, or ``_scoped_count_unknown`` in
isolation (those are covered by tests/test_search.py, tests/test_refresh_counts.py,
and tests/test_app_cards.py) -- it proves the cycle path, the refresh path, the
grade, the detail-panel reason, the badge, and the unknown-vs-last-good progress
denominator (fresh, inactive, legacy) are all wired together correctly through
the real routes.
"""

from __future__ import annotations

import asyncio
import html
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from triggarr.db import init_db
from triggarr.models.arr import Tag
from triggarr.models.config import GeneralConfig, InstanceConfig, Settings
from triggarr.search.engine import run_lidarr_cycle, run_radarr_cycle, run_sonarr_cycle
from triggarr.state import _default_instance_state, _default_state
from triggarr.web.routes import STATIC_DIR, router


def _sonarr_episode(
    *,
    series_id: int = 1,
    season_number: int = 1,
    episode_id: int = 100,
    monitored: bool = True,
    tags: list[int] | None = None,
) -> dict:
    """Build a well-formed Sonarr episode dict."""
    air_date = (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    return {
        "id": episode_id,
        "seriesId": series_id,
        "seasonNumber": season_number,
        "monitored": monitored,
        "airDateUtc": air_date,
        "series": {"id": series_id, "title": "Test Show", "tags": tags or []},
    }


@pytest.fixture
def card_app(tmp_path):
    """Minimal FastAPI app for both the card route and the refresh route.

    No database is attached -- neither route touches app.state.db; each
    cycle test opens its own real aiosqlite connection to drive the engine.
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
    app.state.last_refresh_time = {}
    app.state.last_health_check = None
    app.state.tag_cache = {}

    # AsyncMock clients so the POST /api/refresh-counts route can drive the
    # real refresh_*_counts functions end to end (child attributes of an
    # AsyncMock are themselves AsyncMock, so `await client.get_tags()` etc.
    # work without further configuration).
    app.state.radarr_clients = {"Default": AsyncMock()}
    app.state.sonarr_clients = {"Default": AsyncMock()}
    app.state.lidarr_clients = {"Default": AsyncMock()}

    return app


@pytest.fixture
def card_client(card_app):
    return TestClient(card_app)


# ---------------------------------------------------------------------------
# Original end-to-end proofs: skip, grade, detail reason, badge
# ---------------------------------------------------------------------------


async def test_e2e_radarr_unresolved_tag_card_shows_skip_and_failed_grade(tmp_path, card_app, card_client):
    """Real cycle, real card: an unresolved missing tag skips the queue and grades Failed."""
    settings = make_settings()
    card_app.state.settings = settings
    state = _default_state()
    state["radarr"] = {"Default": _default_instance_state()}

    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="4k",
    )
    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True},
        {"id": 2, "title": "Movie B", "monitored": True},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=2)
    client.search_movies = AsyncMock()

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        await db.close()

    client.search_movies.assert_not_awaited()
    card_app.state.triggarr_state = result
    response = card_client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    text = html.unescape(response.text)
    assert "Missing queue skipped" in text
    assert "tag '4k' not found" in text
    assert "Failed" in text
    assert "Missing queue not evaluated: tag '4k' not found" in text
    assert "Nothing needed" not in text


async def test_e2e_badge_clears_after_tag_resolves(tmp_path, card_app, card_client):
    """Real cycle, real card: the skip badge disappears once the tag resolves on a later cycle."""
    settings = make_settings()
    card_app.state.settings = settings
    state = _default_state()
    state["radarr"] = {"Default": _default_instance_state()}

    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="4k",
    )
    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True, "tags": []},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=1)
    client.search_movies = AsyncMock()

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        state = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        card_app.state.triggarr_state = state
        first_response = card_client.get("/partials/app-card/radarr/Default")
        assert "queue skipped" in html.unescape(first_response.text)

        # Cycle 2: the tag now resolves and the previously-skipped item is tagged.
        client.get_tags = AsyncMock(return_value=[Tag(id=5, label="4k")])
        client.get_wanted_missing = AsyncMock(return_value=[
            {"id": 1, "title": "Movie A", "monitored": True, "tags": [5]},
        ])
        state = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        await db.close()

    client.search_movies.assert_awaited_with([1])
    card_app.state.triggarr_state = state
    second_response = card_client.get("/partials/app-card/radarr/Default")
    assert second_response.status_code == 200
    assert "queue skipped" not in html.unescape(second_response.text)


async def test_e2e_sonarr_fetch_failure_card_names_app(tmp_path, card_app, card_client):
    """Real cycle, real card: a tag-fetch failure names Sonarr and never leaks the secret-bearing URL."""
    settings = make_settings()
    card_app.state.settings = settings
    state = _default_state()
    state["sonarr"] = {"Default": _default_instance_state()}

    instance_config = InstanceConfig(
        url="http://sonarr:8989", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        cutoff_tag="hd",
    )
    client = AsyncMock()
    client.get_tags = AsyncMock(side_effect=httpx.ConnectError("x apikey=SECRET9"))
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=[_sonarr_episode(series_id=1, episode_id=100)])
    client.get_library_count = AsyncMock(return_value=1)
    client.search_season = AsyncMock()

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        await db.close()

    card_app.state.triggarr_state = result
    response = card_client.get("/partials/app-card/sonarr/Default")
    assert response.status_code == 200
    assert "SECRET9" not in response.text
    text = html.unescape(response.text)
    assert "Cutoff queue skipped" in text
    assert "couldn't load tags from Sonarr" in text
    assert "Cutoff unmet queue not evaluated: couldn't load tags" in text


async def test_e2e_lidarr_partial_when_other_queue_accepted(tmp_path, card_app, card_client):
    """Real cycle, real card: a skipped missing queue plus an accepted cutoff queue grades Partial."""
    settings = make_settings()
    card_app.state.settings = settings
    state = _default_state()
    state["lidarr"] = {"Default": _default_instance_state()}

    instance_config = InstanceConfig(
        url="http://lidarr:8686", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="gone",
    )
    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Album A", "monitored": True},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[
        {"id": 2, "title": "Album B", "monitored": True},
    ])
    client.get_library_count = AsyncMock(return_value=2)
    client.search_albums = AsyncMock()

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        await db.close()

    card_app.state.triggarr_state = result
    response = card_client.get("/partials/app-card/lidarr/Default")
    assert response.status_code == 200
    assert "Partial" in html.unescape(response.text)


# ---------------------------------------------------------------------------
# Revision-1: unknown-scope proofs (fresh, inactive, legacy, last-good)
# ---------------------------------------------------------------------------


async def test_e2e_fresh_unresolved_tag_active_shows_unknown_progress(tmp_path, card_app, card_client):
    """Real cycle, real card: a fresh instance with no scoped counts ever shows the em dash, not the raw count."""
    settings = make_settings()
    card_app.state.settings = settings
    state = _default_state()
    state["radarr"] = {"Default": _default_instance_state()}

    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="4k",
    )
    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[])
    client.get_wanted_missing = AsyncMock(
        return_value=[{"id": i, "title": f"Movie {i}", "monitored": True} for i in range(500)]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=500)
    client.search_movies = AsyncMock()

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        await db.close()

    card_app.state.triggarr_state = result
    response = card_client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    text = html.unescape(response.text)
    assert "0 of —" in text
    assert "of 500" not in text


async def test_e2e_fresh_unresolved_tag_inactive_shows_unknown_progress(tmp_path, card_app, card_client):
    """Real cycle, real card (OQ1): an inactive queue's unresolved tag also shows the em dash, no badge."""
    settings = make_settings()
    card_app.state.settings = settings
    state = _default_state()
    state["radarr"] = {"Default": _default_instance_state()}

    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=0, search_cutoff_count=5,
        missing_tag="4k",
    )
    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[])
    client.get_wanted_missing = AsyncMock(
        return_value=[{"id": i, "title": f"Movie {i}", "monitored": True} for i in range(500)]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=500)
    client.search_movies = AsyncMock()

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        await db.close()

    card_app.state.triggarr_state = result
    response = card_client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    text = html.unescape(response.text)
    assert "queue skipped" not in text
    assert "0 of —" in text
    assert "of 500" not in text


async def test_e2e_last_good_count_survives_unresolve(tmp_path, card_app, card_client):
    """Real cycle, real card: a scoped count learned while resolved survives a later unresolve."""
    settings = make_settings()
    card_app.state.settings = settings
    state = _default_state()
    state["radarr"] = {"Default": _default_instance_state()}

    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="4k",
    )
    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="4k")])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie 1", "monitored": True, "tags": [5]},
        {"id": 2, "title": "Movie 2", "monitored": True, "tags": [5]},
        {"id": 3, "title": "Movie 3", "monitored": True, "tags": [5]},
        {"id": 4, "title": "Movie 4", "monitored": True, "tags": []},
        {"id": 5, "title": "Movie 5", "monitored": True, "tags": []},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=5)
    client.search_movies = AsyncMock()

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        state = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        card_app.state.triggarr_state = state
        first_response = card_client.get("/partials/app-card/radarr/Default")
        assert "of 3" in html.unescape(first_response.text)

        # Cycle 2: the tag no longer resolves.
        client.get_tags = AsyncMock(return_value=[])
        state = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        await db.close()

    card_app.state.triggarr_state = state
    second_response = card_client.get("/partials/app-card/radarr/Default")
    assert second_response.status_code == 200
    text = html.unescape(second_response.text)
    assert "of 3" in text
    assert "of 5" not in text


async def test_e2e_legacy_fail_open_state_refresh_shows_unknown(card_app, card_client):
    """Real refresh route, real card: legacy fail-open state (no provenance stamp) is never trusted."""
    settings = Settings(
        general=GeneralConfig(),
        radarr={"Default": InstanceConfig(
            url="http://radarr:7878", api_key="test-key", enabled=True,
            search_missing_count=5, search_cutoff_count=5,
            missing_tag="4k",
        )},
        sonarr={},
        lidarr={},
    )
    card_app.state.settings = settings
    card_app.state.triggarr_state = {
        "radarr": {
            "Default": {
                **_default_instance_state(),
                "connected": True,
                "missing_count": 500,
                "missing_eligible": 500,
                "missing_monitored": 500,
                "cutoff_count": 0,
                "tag_warnings": [{"tag": "4k", "field": "missing"}],
            },
        },
        "sonarr": {},
        "lidarr": {},
        "search_log": [],
    }

    client = card_app.state.radarr_clients["Default"]
    client.get_wanted_missing = AsyncMock(
        return_value=[{"id": i, "title": f"Movie {i}", "monitored": True} for i in range(500)]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=500)
    client.get_tags = AsyncMock(return_value=[])

    response = card_client.post("/api/refresh-counts/radarr/Default")

    assert response.status_code == 200
    text = html.unescape(response.text)
    assert "0 of —" in text
    assert "of 500" not in text
    # The pre-existing scoped count is kept (never rewritten), just not displayed.
    assert card_app.state.triggarr_state["radarr"]["Default"]["missing_eligible"] == 500


async def test_e2e_refresh_route_shows_same_badge_and_keeps_counts(card_app, card_client):
    """Real refresh route, real card: the refresh path shows the same skip badge and keeps last-good counts."""
    settings = Settings(
        general=GeneralConfig(),
        radarr={"Default": InstanceConfig(
            url="http://radarr:7878", api_key="test-key", enabled=True,
            search_missing_count=5, search_cutoff_count=5,
            missing_tag="gone",
        )},
        sonarr={},
        lidarr={},
    )
    card_app.state.settings = settings
    card_app.state.triggarr_state = {
        "radarr": {
            "Default": {
                **_default_instance_state(),
                "connected": True,
                "missing_count": 2,
                "missing_eligible": 7,
                "missing_monitored": 9,
                "cutoff_count": 0,
                "tag_warnings": [],
            },
        },
        "sonarr": {},
        "lidarr": {},
        "search_log": [],
    }

    client = card_app.state.radarr_clients["Default"]
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Movie A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=1)
    client.get_tags = AsyncMock(return_value=[])

    response = card_client.post("/api/refresh-counts/radarr/Default")

    assert response.status_code == 200
    text = html.unescape(response.text)
    assert "Missing queue skipped" in text
    assert card_app.state.triggarr_state["radarr"]["Default"]["missing_eligible"] == 7


# ---------------------------------------------------------------------------
# PR #26 review checkpoint: a saved scoped count is shown only under the tag
# it was computed for (Greptile 4305219336, vibe-check arch-001)
# ---------------------------------------------------------------------------


def _card_settings_for(instance_config: InstanceConfig) -> Settings:
    """Card-route settings whose Radarr Default instance matches the engine's config."""
    settings = make_settings()
    settings.radarr["Default"] = instance_config
    return settings


async def test_e2e_tag_change_then_inactive_fetch_failure_hides_old_tag_count(tmp_path, card_app, card_client):
    """A count computed under the old tag is never shown as the new tag's progress.

    Cutoff-only instance (missing inactive). The missing tag changes from 'old'
    to 'new'; the next cycle's inactive missing fetch fails while 'new'
    resolves, so no fresh count or stamp is written for the missing queue.
    """
    settings = make_settings()
    state = _default_state()
    state["radarr"] = {"Default": _default_instance_state()}

    old_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=0, search_cutoff_count=5,
        missing_tag="old",
    )
    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="old"), Tag(id=6, label="new")])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie 1", "monitored": True, "tags": [5]},
        {"id": 2, "title": "Movie 2", "monitored": True, "tags": [5]},
        {"id": 3, "title": "Movie 3", "monitored": True, "tags": [5]},
        {"id": 4, "title": "Movie 4", "monitored": True, "tags": []},
        {"id": 5, "title": "Movie 5", "monitored": True, "tags": []},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=5)
    client.search_movies = AsyncMock()

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        state = await run_radarr_cycle(client, state, "Default", old_config, settings, db)
        card_app.state.settings = _card_settings_for(old_config)
        card_app.state.triggarr_state = state
        first = html.unescape(card_client.get("/partials/app-card/radarr/Default").text)
        assert "0 of 3" in first

        new_config = old_config.model_copy(update={"missing_tag": "new"})
        client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("inactive fetch failed"))
        state = await run_radarr_cycle(client, state, "Default", new_config, settings, db)
    finally:
        await db.close()

    card_app.state.settings = _card_settings_for(new_config)
    card_app.state.triggarr_state = state
    response = card_client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    text = html.unescape(response.text)
    assert "0 of 3" not in text
    assert "0 of —" in text


async def test_e2e_legacy_state_then_aborted_cycle_never_shows_fail_open_count(tmp_path, card_app, card_client):
    """vibe-check arch-001 as reported: legacy fail-open state, then a cycle that aborts on fetch.

    The abort clears the legacy reason-less tag warning; no unresolved marker
    exists yet. The card must not show the legacy (possibly fail-open) count.
    """
    settings = make_settings()
    state = _default_state()
    legacy = _default_instance_state()
    legacy.update(
        connected=True,
        missing_count=500,
        missing_eligible=480,
        missing_monitored=500,
        tag_warnings=[{"tag": "4k", "field": "missing"}],
    )
    state["radarr"] = {"Default": legacy}

    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="4k",
    )
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("unreachable"))
    client.get_wanted_cutoff = AsyncMock(return_value=[])

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        state = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        await db.close()

    card_app.state.settings = _card_settings_for(instance_config)
    card_app.state.triggarr_state = state
    response = card_client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    text = html.unescape(response.text)
    assert "of 480" not in text
    assert "of 500" not in text


async def test_e2e_legacy_unstamped_count_hidden_after_inactive_fetch_failure(tmp_path, card_app, card_client):
    """arch-001 variant: a legacy unstamped count stays hidden while the instance is reachable.

    Legacy state whose reason-less warning was already cleared (any earlier
    connection abort does this). The missing queue is inactive and its fetch
    fails, so the cycle succeeds via the cutoff queue, the tag resolves, and
    no fresh missing count or stamp is written.
    """
    settings = make_settings()
    state = _default_state()
    legacy = _default_instance_state()
    legacy.update(
        connected=True,
        missing_count=500,
        missing_eligible=480,
        missing_monitored=500,
        tag_warnings=[],
    )
    state["radarr"] = {"Default": legacy}

    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=0, search_cutoff_count=5,
        missing_tag="4k",
    )
    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="4k")])
    client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("inactive fetch failed"))
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=500)
    client.search_movies = AsyncMock()

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        state = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        await db.close()

    assert state["radarr"]["Default"]["connected"] is True
    card_app.state.settings = _card_settings_for(instance_config)
    card_app.state.triggarr_state = state
    response = card_client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    text = html.unescape(response.text)
    assert "of 480" not in text
    assert "0 of —" in text
