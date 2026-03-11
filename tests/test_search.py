"""Comprehensive tests for search engine utility functions and cycle orchestrators.

Tests cover: filtering (monitored, air dates), batch slicing (normal,
wrap, empty, past-end cursor), deduplication (collapse, order, display
name, fallback), Sonarr-specific filtering (unmonitored, future, null,
past, malformed), async cycle orchestration (happy path, network
failure, per-item skip, cursor advancement) for both run_radarr_cycle
and run_sonarr_cycle, and per-cycle diagnostic summary logging.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import aiosqlite
import httpx
from loguru import logger

from tests.conftest import make_settings
from triggarr.db import init_db
from triggarr.models.arr import Tag
from triggarr.models.config import InstanceConfig
from triggarr.search.engine import (
    cap_batch_sizes,
    deduplicate_to_seasons,
    filter_monitored,
    filter_sonarr_episodes,
    filter_unreleased_movies,
    resolve_tag_id,
    run_radarr_cycle,
    run_sonarr_cycle,
    slice_batch,
)
from triggarr.state import _default_state

# ---------------------------------------------------------------------------
# filter_monitored
# ---------------------------------------------------------------------------


def test_filter_monitored_keeps_only_monitored():
    items = [
        {"id": 1, "monitored": True},
        {"id": 2, "monitored": False},
        {"id": 3},  # missing key
        {"id": 4, "monitored": True},
    ]
    result = filter_monitored(items)
    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["id"] == 4


def test_filter_monitored_empty_list():
    assert filter_monitored([]) == []


# ---------------------------------------------------------------------------
# slice_batch
# ---------------------------------------------------------------------------


def test_slice_batch_normal():
    items = list(range(10))
    batch, new_cursor = slice_batch(items, cursor=3, batch_size=2)
    assert batch == [3, 4]
    assert new_cursor == 5


def test_slice_batch_wraps_at_end():
    items = list(range(5))
    batch, new_cursor = slice_batch(items, cursor=3, batch_size=3)
    assert batch == [3, 4]
    assert new_cursor == 0


def test_slice_batch_cursor_past_end():
    items = list(range(5))
    batch, new_cursor = slice_batch(items, cursor=99, batch_size=2)
    assert batch == [0, 1]
    assert new_cursor == 2


def test_slice_batch_empty_list():
    batch, new_cursor = slice_batch([], cursor=0, batch_size=5)
    assert batch == []
    assert new_cursor == 0


def test_slice_batch_batch_larger_than_remaining():
    items = list(range(3))
    batch, new_cursor = slice_batch(items, cursor=1, batch_size=10)
    assert batch == [1, 2]
    assert new_cursor == 0


# ---------------------------------------------------------------------------
# deduplicate_to_seasons
# ---------------------------------------------------------------------------


def test_deduplicate_to_seasons_removes_duplicates():
    episodes = [
        {"seriesId": 1, "seasonNumber": 2, "series": {"title": "Show A"}},
        {"seriesId": 1, "seasonNumber": 2, "series": {"title": "Show A"}},
        {"seriesId": 1, "seasonNumber": 3, "series": {"title": "Show A"}},
    ]
    result = deduplicate_to_seasons(episodes)
    assert len(result) == 2
    assert result[0]["seasonNumber"] == 2
    assert result[0]["episode_count"] == 2  # Two episodes in season 2
    assert result[1]["seasonNumber"] == 3
    assert result[1]["episode_count"] == 1  # One episode in season 3


def test_deduplicate_to_seasons_preserves_order():
    episodes = [
        {"seriesId": 2, "seasonNumber": 1, "series": {"title": "Show B"}},
        {"seriesId": 1, "seasonNumber": 3, "series": {"title": "Show A"}},
        {"seriesId": 2, "seasonNumber": 1, "series": {"title": "Show B"}},
    ]
    result = deduplicate_to_seasons(episodes)
    assert len(result) == 2
    assert result[0]["seriesId"] == 2
    assert result[1]["seriesId"] == 1


def test_deduplicate_to_seasons_display_name_format():
    episodes = [
        {"seriesId": 5, "seasonNumber": 3, "series": {"title": "Breaking Bad"}},
    ]
    result = deduplicate_to_seasons(episodes)
    assert result[0]["display_name"] == "Breaking Bad - Season 3"


def test_deduplicate_to_seasons_missing_series_data():
    episodes = [
        {"seriesId": 42, "seasonNumber": 1},
    ]
    result = deduplicate_to_seasons(episodes)
    assert result[0]["display_name"] == "Series 42 - Season 1"
    assert result[0]["episode_count"] == 1


# ---------------------------------------------------------------------------
# filter_sonarr_episodes
# ---------------------------------------------------------------------------


def _make_episode(
    monitored: bool = True,
    air_date_utc: str | None = "2020-01-01T00:00:00Z",
) -> dict:
    """Helper to build a Sonarr episode dict."""
    ep: dict = {"monitored": monitored, "seriesId": 1, "seasonNumber": 1}
    if air_date_utc is not None:
        ep["airDateUtc"] = air_date_utc
    return ep


def test_filter_sonarr_episodes_excludes_unmonitored():
    episodes = [_make_episode(monitored=False)]
    assert filter_sonarr_episodes(episodes) == []


def test_filter_sonarr_episodes_excludes_future_air_date():
    future = (datetime.now(UTC) + timedelta(days=30)).isoformat().replace("+00:00", "Z")
    episodes = [_make_episode(air_date_utc=future)]
    assert filter_sonarr_episodes(episodes) == []


def test_filter_sonarr_episodes_excludes_null_air_date():
    ep = _make_episode()
    del ep["airDateUtc"]  # simulate missing / TBA
    assert filter_sonarr_episodes([ep]) == []


def test_filter_sonarr_episodes_keeps_past_monitored():
    episodes = [_make_episode(monitored=True, air_date_utc="2020-06-15T12:00:00Z")]
    result = filter_sonarr_episodes(episodes)
    assert len(result) == 1
    assert result[0]["airDateUtc"] == "2020-06-15T12:00:00Z"


def test_filter_sonarr_episodes_handles_unparseable_date():
    episodes = [_make_episode(air_date_utc="not-a-date")]
    result = filter_sonarr_episodes(episodes)
    assert result == []


# ---------------------------------------------------------------------------
# run_radarr_cycle (async orchestration)
# ---------------------------------------------------------------------------


def _cycle_settings(missing_count: int = 2, cutoff_count: int = 2):
    """Build Settings tuned for predictable batching in cycle tests."""
    return make_settings(
        search_missing_count=missing_count,
        search_cutoff_count=cutoff_count,
    )


def _cycle_instance_config(missing_count: int = 2, cutoff_count: int = 2):
    """Build an InstanceConfig tuned for predictable batching in cycle tests."""
    return InstanceConfig(
        url="http://radarr:7878",
        api_key="test-key",
        enabled=True,
        search_missing_count=missing_count,
        search_cutoff_count=cutoff_count,
    )


def _default_instance_state():
    """Return a default per-instance state nested under 'Default'."""
    state = _default_state()
    from triggarr.state import _default_instance_state as _dis
    state["radarr"] = {"Default": _dis()}
    state["sonarr"] = {"Default": _dis()}
    return state


async def test_run_radarr_cycle_happy_path(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 1, "title": "Movie A", "monitored": True},
            {"id": 2, "title": "Movie B", "monitored": True},
        ]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _default_instance_state()
    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    # Both movies searched (batch_size=2 covers both)
    assert client.search_movies.call_count == 2
    client.search_movies.assert_any_call([1])
    client.search_movies.assert_any_call([2])

    assert result["radarr"]["Default"]["last_run"] is not None
    assert result["radarr"]["Default"]["connected"] is True
    # 2 items, batch 2, cursor wraps to 0
    assert result["radarr"]["Default"]["missing_cursor"] == 0
    await db.close()


async def test_run_radarr_cycle_network_failure(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        side_effect=httpx.ConnectError("refused")
    )

    state = _default_instance_state()
    state["radarr"]["Default"]["missing_cursor"] = 5
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    assert result["radarr"]["Default"]["connected"] is False
    assert result["radarr"]["Default"]["unreachable_since"] is not None
    # Cursor unchanged on abort
    assert result["radarr"]["Default"]["missing_cursor"] == 5
    await db.close()


async def test_run_radarr_cycle_per_item_skip(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 1, "title": "Movie A", "monitored": True},
            {"id": 2, "title": "Movie B", "monitored": True},
        ]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    # First search raises, second succeeds
    client.search_movies = AsyncMock(
        side_effect=[Exception("boom"), None]
    )

    state = _default_instance_state()
    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    # Did not abort after first failure -- called twice
    assert client.search_movies.call_count == 2
    # Both searches logged to SQLite (failed + succeeded)
    from triggarr.db import get_recent_searches

    searches = await get_recent_searches(db)
    assert len(searches) == 2
    # Newest first: Movie B (searched), Movie A (failed)
    assert searches[0]["name"] == "Movie B"
    assert searches[0]["outcome"] == "searched"
    assert searches[1]["name"] == "Movie A"
    assert searches[1]["outcome"] == "failed"
    await db.close()


async def test_run_radarr_cycle_cursor_advancement(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    movies = [
        {"id": i, "title": f"Movie {i}", "monitored": True}
        for i in range(1, 6)
    ]

    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    # --- Run 1: cursor 0 -> 2 ---
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=movies)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _default_instance_state()
    state["radarr"]["Default"]["missing_cursor"] = 0

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["missing_cursor"] == 2

    # --- Run 2: cursor 2 -> 4 ---
    client.get_wanted_missing = AsyncMock(return_value=movies)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    result = await run_radarr_cycle(client, result, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["missing_cursor"] == 4

    # --- Run 3: cursor 4 -> wraps to 0 (only 1 item left, then wraps) ---
    client.get_wanted_missing = AsyncMock(return_value=movies)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    result = await run_radarr_cycle(client, result, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["missing_cursor"] == 0
    await db.close()


# ---------------------------------------------------------------------------
# run_sonarr_cycle (async orchestration)
# ---------------------------------------------------------------------------


def _make_sonarr_episode(
    series_id: int,
    season_number: int,
    series_title: str = "Show",
    episode_id: int = 1,
) -> dict:
    """Build a Sonarr episode dict suitable for cycle tests."""
    return {
        "id": episode_id,
        "seriesId": series_id,
        "seasonNumber": season_number,
        "monitored": True,
        "airDateUtc": "2020-01-01T00:00:00Z",
        "series": {"title": series_title},
    }


async def test_run_sonarr_cycle_happy_path(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    episodes = [
        _make_sonarr_episode(series_id=10, season_number=1, series_title="Show A", episode_id=100),
        _make_sonarr_episode(series_id=10, season_number=2, series_title="Show A", episode_id=101),
    ]

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=episodes)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_season = AsyncMock()

    state = _default_instance_state()
    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    # Two unique seasons from same series searched
    assert client.search_season.call_count == 2
    client.search_season.assert_any_call(10, 1)
    client.search_season.assert_any_call(10, 2)
    assert result["sonarr"]["Default"]["connected"] is True
    assert result["sonarr"]["Default"]["last_run"] is not None
    await db.close()


async def test_run_sonarr_cycle_network_failure(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        side_effect=httpx.ConnectError("refused")
    )

    state = _default_instance_state()
    state["sonarr"]["Default"]["missing_cursor"] = 3
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    assert result["sonarr"]["Default"]["connected"] is False
    assert result["sonarr"]["Default"]["unreachable_since"] is not None
    assert result["sonarr"]["Default"]["missing_cursor"] == 3
    await db.close()


async def test_run_sonarr_cycle_per_item_skip(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    # Two episodes from different series -> 2 unique seasons after dedup
    episodes = [
        _make_sonarr_episode(series_id=10, season_number=1, series_title="Show A", episode_id=100),
        _make_sonarr_episode(series_id=20, season_number=1, series_title="Show B", episode_id=200),
    ]

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=episodes)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    # First season search raises, second succeeds
    client.search_season = AsyncMock(
        side_effect=[Exception("boom"), None]
    )

    state = _default_instance_state()
    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    assert client.search_season.call_count == 2
    # Both searches logged to SQLite (failed + succeeded)
    from triggarr.db import get_recent_searches

    searches = await get_recent_searches(db)
    assert len(searches) == 2
    # Newest first: Show B (searched), Show A (failed)
    assert "Show B" in searches[0]["name"]
    assert searches[0]["outcome"] == "searched"
    assert "Show A" in searches[1]["name"]
    assert searches[1]["outcome"] == "failed"
    await db.close()


async def test_run_sonarr_cycle_cursor_advancement(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    # 4 episodes that deduplicate to 3 seasons
    episodes = [
        _make_sonarr_episode(series_id=10, season_number=1, series_title="Show A", episode_id=100),
        _make_sonarr_episode(series_id=10, season_number=2, series_title="Show A", episode_id=101),
        _make_sonarr_episode(series_id=20, season_number=1, series_title="Show B", episode_id=200),
        _make_sonarr_episode(series_id=10, season_number=1, series_title="Show A", episode_id=102),  # dup
    ]

    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    # --- Run 1: cursor 0 -> 2 ---
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=episodes)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_season = AsyncMock()

    state = _default_instance_state()
    state["sonarr"]["Default"]["missing_cursor"] = 0

    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
    assert result["sonarr"]["Default"]["missing_cursor"] == 2

    # --- Run 2: cursor 2 -> wraps to 0 (only 1 season left) ---
    client.get_wanted_missing = AsyncMock(return_value=episodes)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_season = AsyncMock()

    result = await run_sonarr_cycle(client, result, "Default", instance_config, settings, db)
    assert result["sonarr"]["Default"]["missing_cursor"] == 0
    await db.close()


# ---------------------------------------------------------------------------
# cap_batch_sizes
# ---------------------------------------------------------------------------


def test_cap_batch_sizes_unlimited():
    """hard_max=0 returns inputs unchanged (unlimited mode)."""
    assert cap_batch_sizes(5, 5, 0) == (5, 5)
    assert cap_batch_sizes(100, 50, 0) == (100, 50)
    assert cap_batch_sizes(0, 0, 0) == (0, 0)


def test_cap_batch_sizes_no_cap_needed():
    """Total within limit returns inputs unchanged."""
    assert cap_batch_sizes(3, 3, 10) == (3, 3)
    assert cap_batch_sizes(5, 5, 10) == (5, 5)
    assert cap_batch_sizes(1, 1, 100) == (1, 1)


def test_cap_batch_sizes_proportional_split():
    """Total exceeds limit, verify proportional reduction."""
    # 5+5=10 > 6 -> missing gets floor(5*6/10)=3, cutoff gets 6-3=3
    assert cap_batch_sizes(5, 5, 6) == (3, 3)
    # 8+2=10 > 5 -> missing gets floor(8*5/10)=4, cutoff gets 5-4=1
    assert cap_batch_sizes(8, 2, 5) == (4, 1)
    # 2+8=10 > 5 -> missing gets floor(2*5/10)=1, cutoff gets 5-1=4
    assert cap_batch_sizes(2, 8, 5) == (1, 4)


def test_cap_batch_sizes_one_zero():
    """One queue is 0, other gets full cap."""
    # missing=0, cutoff=10 > hard_max=5 -> missing floor(0*5/10)=0, cutoff=5
    assert cap_batch_sizes(0, 10, 5) == (0, 5)
    # missing=10, cutoff=0 > hard_max=5 -> missing floor(10*5/10)=5, cutoff=0
    assert cap_batch_sizes(10, 0, 5) == (5, 0)


def test_cap_batch_sizes_very_small_max():
    """hard_max=1 with both queues requesting items."""
    # 5+5=10 > 1 -> missing gets floor(5*1/10)=0, cutoff gets 1-0=1
    assert cap_batch_sizes(5, 5, 1) == (0, 1)
    # 1+1=2 > 1 -> missing gets floor(1*1/2)=0, cutoff gets 1-0=1
    assert cap_batch_sizes(1, 1, 1) == (0, 1)


# ---------------------------------------------------------------------------
# Diagnostic cycle logging
# ---------------------------------------------------------------------------


async def test_radarr_cycle_logs_diagnostic_summary(tmp_path):
    """Radarr cycle logs a summary with fetched/searched/skipped counts."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 1, "title": "Movie A", "monitored": True},
            {"id": 2, "title": "Movie B", "monitored": True},
            {"id": 3, "title": "Movie C", "monitored": True},
        ]
    )
    client.get_wanted_cutoff = AsyncMock(
        return_value=[
            {"id": 4, "title": "Movie D", "monitored": True},
            {"id": 5, "title": "Movie E", "monitored": True},
        ]
    )
    client.search_movies = AsyncMock()

    state = _default_instance_state()
    settings = _cycle_settings(missing_count=5, cutoff_count=5)
    instance_config = _cycle_instance_config(missing_count=5, cutoff_count=5)

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="INFO")
    try:
        await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    assert "Radarr: Cycle completed in" in output
    assert "5 fetched" in output
    assert "5 searched" in output
    assert "0 skipped" in output
    await db.close()


async def test_sonarr_cycle_logs_diagnostic_summary(tmp_path):
    """Sonarr cycle logs a summary with fetched/searched/skipped counts."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    episodes = [
        _make_sonarr_episode(series_id=10, season_number=1, series_title="Show A", episode_id=100),
        _make_sonarr_episode(series_id=10, season_number=2, series_title="Show A", episode_id=101),
        _make_sonarr_episode(series_id=20, season_number=1, series_title="Show B", episode_id=200),
    ]

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=episodes)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_season = AsyncMock()

    state = _default_instance_state()
    settings = _cycle_settings(missing_count=5, cutoff_count=5)
    instance_config = _cycle_instance_config(missing_count=5, cutoff_count=5)

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="INFO")
    try:
        await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    assert "Sonarr: Cycle completed in" in output
    # 3 episodes fetched (raw count before filtering/dedup)
    assert "3 fetched" in output
    assert "searched" in output
    assert "skipped" in output
    await db.close()


async def test_radarr_cycle_counts_skipped_on_search_failure(tmp_path):
    """Radarr cycle diagnostic summary correctly counts skipped items."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 1, "title": "Movie A", "monitored": True},
            {"id": 2, "title": "Movie B", "monitored": True},
            {"id": 3, "title": "Movie C", "monitored": True},
        ]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    # First search fails, second and third succeed
    client.search_movies = AsyncMock(
        side_effect=[Exception("boom"), None, None]
    )

    state = _default_instance_state()
    settings = _cycle_settings(missing_count=5, cutoff_count=5)
    instance_config = _cycle_instance_config(missing_count=5, cutoff_count=5)

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="INFO")
    try:
        await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    assert "Radarr: Cycle completed in" in output
    assert "3 fetched" in output
    assert "2 searched" in output
    assert "1 skipped" in output
    await db.close()


# ---------------------------------------------------------------------------
# Outcome logging in DB (failed searches)
# ---------------------------------------------------------------------------


async def test_radarr_cycle_logs_failed_search_to_db(tmp_path):
    """Radarr cycle records failed searches in DB with outcome and detail."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 1, "title": "Movie Fail", "monitored": True},
        ]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock(side_effect=Exception("API timeout"))

    state = _default_instance_state()
    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    from triggarr.db import get_recent_searches

    searches = await get_recent_searches(db)
    assert len(searches) == 1
    assert searches[0]["name"] == "Movie Fail"
    assert searches[0]["outcome"] == "failed"
    assert searches[0]["detail"] == "Exception"
    await db.close()


async def test_sonarr_cycle_logs_failed_search_to_db(tmp_path):
    """Sonarr cycle records failed searches in DB with outcome and detail."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    episodes = [
        _make_sonarr_episode(series_id=10, season_number=1, series_title="Show Fail", episode_id=100),
    ]

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=episodes)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_season = AsyncMock(side_effect=Exception("Connection refused"))

    state = _default_instance_state()
    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    from triggarr.db import get_recent_searches

    searches = await get_recent_searches(db)
    assert len(searches) == 1
    assert "Show Fail" in searches[0]["name"]
    assert searches[0]["outcome"] == "failed"
    assert searches[0]["detail"] == "Exception"
    await db.close()


# ---------------------------------------------------------------------------
# filter_unreleased_movies
# ---------------------------------------------------------------------------


def _movie(title: str, digital: str | None = None, physical: str | None = None) -> dict:
    """Build a Radarr movie dict with optional release dates."""
    m: dict = {"title": title}
    if digital is not None:
        m["digitalRelease"] = digital
    if physical is not None:
        m["physicalRelease"] = physical
    return m


def _past_iso() -> str:
    """Return an ISO date string 30 days in the past."""
    return (datetime.now(UTC) - timedelta(days=30)).isoformat().replace("+00:00", "Z")


def _future_iso() -> str:
    """Return an ISO date string 30 days in the future."""
    return (datetime.now(UTC) + timedelta(days=30)).isoformat().replace("+00:00", "Z")


def test_filter_unreleased_past_digital_passes():
    """Movie with past digitalRelease passes through."""
    movies = [_movie("Released Digital", digital=_past_iso())]
    assert filter_unreleased_movies(movies) == movies


def test_filter_unreleased_past_physical_passes():
    """Movie with past physicalRelease passes through."""
    movies = [_movie("Released Physical", physical=_past_iso())]
    assert filter_unreleased_movies(movies) == movies


def test_filter_unreleased_both_future_skipped():
    """Movie with both dates in the future is skipped."""
    movies = [_movie("Unreleased", digital=_future_iso(), physical=_future_iso())]
    assert filter_unreleased_movies(movies) == []


def test_filter_unreleased_one_past_one_future_passes():
    """Movie with one past date and one future date passes through."""
    movies = [_movie("Mixed", digital=_past_iso(), physical=_future_iso())]
    assert filter_unreleased_movies(movies) == movies


def test_filter_unreleased_both_null_passes():
    """Movie with both dates null passes through (not blackholed) [FILT-03]."""
    movies = [_movie("Unknown")]
    assert filter_unreleased_movies(movies) == movies


def test_filter_unreleased_one_null_one_future_skipped():
    """Movie with one null date and one future date is skipped."""
    movies = [_movie("Null+Future", physical=_future_iso())]
    assert filter_unreleased_movies(movies) == []


def test_filter_unreleased_one_null_one_past_passes():
    """Movie with one null date and one past date passes through."""
    movies = [_movie("Null+Past", digital=_past_iso())]
    assert filter_unreleased_movies(movies) == movies


def test_filter_unreleased_unparseable_date_treated_as_null():
    """Movie with unparseable date string treated as null."""
    movies = [_movie("BadDate", digital="not-a-date", physical="also-bad")]
    assert filter_unreleased_movies(movies) == movies


def test_filter_unreleased_empty_list():
    """Empty list returns empty list."""
    assert filter_unreleased_movies([]) == []


def test_filter_unreleased_mixed_list():
    """Mixed list filters correctly (released + unreleased + null)."""
    movies = [
        _movie("Released", digital=_past_iso()),
        _movie("Unreleased", digital=_future_iso(), physical=_future_iso()),
        _movie("Unknown"),
    ]
    result = filter_unreleased_movies(movies)
    assert len(result) == 2
    assert result[0]["title"] == "Released"
    assert result[1]["title"] == "Unknown"


# ---------------------------------------------------------------------------
# CFG-01: Conditional filter_unreleased_movies in run_radarr_cycle
# ---------------------------------------------------------------------------


async def test_run_radarr_cycle_skip_unreleased_enabled(tmp_path):
    """With skip_unreleased=True, run_radarr_cycle calls filter_unreleased_movies on missing queue."""
    from unittest.mock import patch

    from triggarr.models.config import GeneralConfig

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[{"id": 1, "title": "Movie A", "monitored": True}]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _default_instance_state()
    settings = make_settings(general=GeneralConfig(skip_unreleased=True))
    instance_config = InstanceConfig(url="http://radarr:7878", api_key="test-key", enabled=True)

    with patch(
        "triggarr.search.engine.filter_unreleased_movies",
        wraps=filter_unreleased_movies,
    ) as spy:
        await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        spy.assert_called_once()

    await db.close()


async def test_run_radarr_cycle_skip_unreleased_disabled(tmp_path):
    """With skip_unreleased=False, run_radarr_cycle does NOT call filter_unreleased_movies."""
    from unittest.mock import patch

    from triggarr.models.config import GeneralConfig

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[{"id": 1, "title": "Movie A", "monitored": True}]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _default_instance_state()
    settings = make_settings(general=GeneralConfig(skip_unreleased=False))
    instance_config = InstanceConfig(url="http://radarr:7878", api_key="test-key", enabled=True)

    with patch(
        "triggarr.search.engine.filter_unreleased_movies",
        wraps=filter_unreleased_movies,
    ) as spy:
        await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        spy.assert_not_called()

    await db.close()


async def test_run_radarr_cycle_eligible_count_skip_unreleased_enabled(tmp_path):
    """With skip_unreleased=True, missing_eligible reflects post-filter count (DASH-01)."""
    from triggarr.models.config import GeneralConfig

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    # 4 raw: 3 monitored, 1 unmonitored; of monitored: 1 unreleased
    future = (datetime.now(UTC) + timedelta(days=30)).isoformat().replace("+00:00", "Z")
    past = (datetime.now(UTC) - timedelta(days=30)).isoformat().replace("+00:00", "Z")
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 1, "title": "Released A", "monitored": True, "digitalRelease": past},
            {"id": 2, "title": "Released B", "monitored": True, "digitalRelease": past},
            {"id": 3, "title": "Unreleased C", "monitored": True, "digitalRelease": future, "physicalRelease": future},
            {"id": 4, "title": "Unmonitored D", "monitored": False, "digitalRelease": past},
        ]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _default_instance_state()
    settings = make_settings(general=GeneralConfig(skip_unreleased=True))
    instance_config = InstanceConfig(url="http://radarr:7878", api_key="test-key", enabled=True)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    # 4 raw, 3 monitored, 1 unreleased filtered -> 2 eligible
    assert result["radarr"]["Default"]["missing_monitored"] == 3
    assert result["radarr"]["Default"]["missing_eligible"] == 2
    await db.close()


async def test_run_radarr_cycle_eligible_count_skip_unreleased_disabled(tmp_path):
    """With skip_unreleased=False, missing_monitored is set and equals missing_eligible (DASH-01)."""
    from triggarr.models.config import GeneralConfig

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    # 3 movies, 2 monitored
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 1, "title": "Movie A", "monitored": True},
            {"id": 2, "title": "Movie B", "monitored": True},
            {"id": 3, "title": "Movie C", "monitored": False},
        ]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _default_instance_state()
    settings = make_settings(general=GeneralConfig(skip_unreleased=False))
    instance_config = InstanceConfig(url="http://radarr:7878", api_key="test-key", enabled=True)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    # 2 monitored, no unreleased filtering -> missing_monitored = missing_eligible = 2
    assert result["radarr"]["Default"]["missing_monitored"] == 2
    assert result["radarr"]["Default"]["missing_eligible"] == 2
    await db.close()


async def test_run_sonarr_cycle_eligible_count(tmp_path):
    """Sonarr missing_eligible = filtered episodes, missing_searchable = seasons (DASH-01)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    # 3 episodes -> 2 unique seasons after dedup (series 10 s1 has 2 eps)
    episodes = [
        _make_sonarr_episode(series_id=10, season_number=1, series_title="Show A", episode_id=100),
        _make_sonarr_episode(series_id=10, season_number=1, series_title="Show A", episode_id=101),
        _make_sonarr_episode(series_id=20, season_number=1, series_title="Show B", episode_id=200),
    ]

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=episodes)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_season = AsyncMock()

    state = _default_instance_state()
    settings = _cycle_settings(missing_count=5, cutoff_count=5)
    instance_config = _cycle_instance_config(missing_count=5, cutoff_count=5)

    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    # 3 filtered episodes, 2 seasons after dedup
    assert result["sonarr"]["Default"]["missing_eligible"] == 3
    assert result["sonarr"]["Default"]["missing_searchable"] == 2
    await db.close()


async def test_run_radarr_cycle_info_log_unreleased_skipped(tmp_path):
    """INFO log emitted when unreleased items are skipped during Radarr cycle."""
    from triggarr.models.config import GeneralConfig

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    future = (datetime.now(UTC) + timedelta(days=30)).isoformat().replace("+00:00", "Z")
    past = (datetime.now(UTC) - timedelta(days=30)).isoformat().replace("+00:00", "Z")
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 1, "title": "Released A", "monitored": True, "digitalRelease": past},
            {"id": 2, "title": "Unreleased B", "monitored": True, "digitalRelease": future, "physicalRelease": future},
        ]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _default_instance_state()
    settings = make_settings(general=GeneralConfig(skip_unreleased=True))
    instance_config = InstanceConfig(url="http://radarr:7878", api_key="test-key", enabled=True)

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="INFO")
    try:
        await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    assert "1 unreleased movies skipped" in output
    await db.close()


async def test_run_radarr_cycle_no_info_log_when_zero_unreleased(tmp_path):
    """No INFO log when zero items are filtered by unreleased filter."""
    from triggarr.models.config import GeneralConfig

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    past = (datetime.now(UTC) - timedelta(days=30)).isoformat().replace("+00:00", "Z")
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 1, "title": "Released A", "monitored": True, "digitalRelease": past},
            {"id": 2, "title": "Released B", "monitored": True, "digitalRelease": past},
        ]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _default_instance_state()
    settings = make_settings(general=GeneralConfig(skip_unreleased=True))
    instance_config = InstanceConfig(url="http://radarr:7878", api_key="test-key", enabled=True)

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="INFO")
    try:
        await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    assert "unreleased movies skipped" not in output
    await db.close()


async def test_run_radarr_cycle_skip_unreleased_never_filters_cutoff(tmp_path):
    """With skip_unreleased=True, filter_unreleased_movies called once (missing only), not cutoff."""
    from unittest.mock import patch

    from triggarr.models.config import GeneralConfig

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[{"id": 1, "title": "Movie A", "monitored": True}]
    )
    client.get_wanted_cutoff = AsyncMock(
        return_value=[{"id": 2, "title": "Movie B", "monitored": True}]
    )
    client.search_movies = AsyncMock()

    state = _default_instance_state()
    settings = make_settings(general=GeneralConfig(skip_unreleased=True))
    instance_config = InstanceConfig(url="http://radarr:7878", api_key="test-key", enabled=True)

    with patch(
        "triggarr.search.engine.filter_unreleased_movies",
        wraps=filter_unreleased_movies,
    ) as spy:
        await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        # Called exactly once (missing queue), not for cutoff queue
        assert spy.call_count == 1

    await db.close()


# ---------------------------------------------------------------------------
# resolve_tag_id (Phase 35)
# ---------------------------------------------------------------------------


def test_resolve_tag_id_exact_match():
    """resolve_tag_id returns tag ID for exact name match."""
    tags = [Tag(id=1, label="4k")]
    assert resolve_tag_id("4k", tags) == 1


def test_resolve_tag_id_case_insensitive():
    """resolve_tag_id matches tag name case-insensitively."""
    tags = [Tag(id=1, label="4k")]
    assert resolve_tag_id("4K", tags) == 1


def test_resolve_tag_id_strips_whitespace():
    """resolve_tag_id strips whitespace from both name and tag labels."""
    tags = [Tag(id=1, label=" 4k ")]
    assert resolve_tag_id(" 4K ", tags) == 1


def test_resolve_tag_id_missing_returns_none():
    """resolve_tag_id returns None when tag name is not found."""
    tags = [Tag(id=1, label="4k")]
    assert resolve_tag_id("missing", tags) is None


def test_resolve_tag_id_empty_tags_returns_none():
    """resolve_tag_id returns None when tag list is empty."""
    assert resolve_tag_id("anything", []) is None
