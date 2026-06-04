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
import pytest
from loguru import logger
from pydantic import TypeAdapter, ValidationError

from tests.conftest import make_settings
from triggarr.db import init_db
from triggarr.models.arr import Tag
from triggarr.models.config import InstanceConfig
from triggarr.search.engine import (
    _lidarr_tags,
    cap_batch_sizes,
    deduplicate_to_seasons,
    filter_monitored,
    filter_sonarr_episodes,
    filter_unreleased_movies,
    prioritize_batch,
    resolve_tag_id,
    run_lidarr_cycle,
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


# SRCH-04 (batch exceeds available): Covered by test_slice_batch_batch_larger_than_remaining below.
# The search cycle functions call slice_batch() which handles this correctly -- items=[0,1,2],
# cursor=1, batch_size=10 -> batch=[1,2], new_cursor=0. No integration test needed.
#
# SRCH-05 (cursor past end): Covered by test_slice_batch_cursor_past_end above.
# Cursor resets to 0 and slices from beginning -- items=[0..4], cursor=99, batch_size=2 ->
# batch=[0,1], new_cursor=2. No integration test needed.


def test_slice_batch_batch_larger_than_remaining():
    items = list(range(3))
    batch, new_cursor = slice_batch(items, cursor=1, batch_size=10)
    assert batch == [1, 2]
    assert new_cursor == 0


# ---------------------------------------------------------------------------
# prioritize_batch (QUEUE-02/04/05/06/09/10)
# ---------------------------------------------------------------------------

# Shared fake key_fn for generic (Radarr/Lidarr-style) tests.
_id_key = lambda it: str(it["id"])  # noqa: E731
_sonarr_key = lambda s: f'{s["seriesId"]}:{s["seasonNumber"]}'  # noqa: E731


def _items(*ids: int) -> list[dict]:
    """Build a list of fake item dicts with numeric ids."""
    return [{"id": i} for i in ids]


def test_prioritize_batch_cold_start():
    """Empty log: batch == first N items in fetch order; new_log == their keys."""
    items = _items(1, 2, 3, 4, 5)
    batch, new_log, pass_completed = prioritize_batch(items, [], 3, _id_key)
    assert [it["id"] for it in batch] == [1, 2, 3]
    assert new_log == ["1", "2", "3"]
    assert pass_completed is False  # items 4 and 5 still unsearched


def test_prioritize_batch_cold_start_equivalence():
    """QUEUE-06: prioritize_batch(items, [], N, key_fn)[0] == slice_batch(items, 0, N)[0].

    This is the load-bearing cold-start behavior-preservation oracle:
    an empty searched-log must produce the same batch as the prior first-cycle cursor walk.
    """
    items = _items(10, 20, 30, 40, 50)
    for n in (0, 1, 3, 5, 7):
        pb_batch = prioritize_batch(items, [], n, _id_key)[0]
        sb_batch = slice_batch(items, 0, n)[0]
        assert pb_batch == sb_batch, f"cold-start divergence at N={n}: {pb_batch} != {sb_batch}"


def test_prioritize_batch_unsearched_first():
    """Items not in the log are taken before already-searched items (QUEUE-04)."""
    items = _items(1, 2, 3, 4, 5)
    # Items 2 and 4 have already been searched; 1, 3, 5 are unsearched
    log = ["2", "4"]
    # batch_size=2: should take from the 3 unsearched [1,3,5] first, not from [2,4]
    batch, new_log, pass_completed = prioritize_batch(items, log, 2, _id_key)
    # unsearched = [1, 3, 5] (fetch order); 2 slots → take 1, 3
    assert [it["id"] for it in batch] == [1, 3]
    assert pass_completed is False  # items 4, 5 still unsearched in this pass


def test_prioritize_batch_topup_oldest_first():
    """When unsearched < N, top up from already-searched oldest-first (QUEUE-05)."""
    items = _items(1, 2, 3, 4, 5)
    # Items 1, 2, 3 already searched (log order = 1 oldest, 3 newest)
    log = ["1", "2", "3"]
    # unsearched = [4, 5]; batch_size=3 → take 4,5 (2 slots), top up with oldest: 1
    # This means item 1 (oldest-searched) fills slot 3, NOT item 2 or 3
    batch, new_log, pass_completed = prioritize_batch(items, log, 3, _id_key)
    assert [it["id"] for it in batch] == [4, 5, 1]
    # new_log: 1 moved to tail (re-searched); 2 and 3 survive at front; 4 and 5 appended
    assert new_log == ["2", "3", "4", "5", "1"]
    # items 2 and 3 not in batch, but they were already in pruned log → still in new_log
    # eligible_ids = {1,2,3,4,5} ⊆ {2,3,4,5,1} → True, and batch is non-empty → pass_completed=True
    assert pass_completed is True


def test_prioritize_batch_pass_completion():
    """When the last unsearched item is batched, pass_completed is True (QUEUE-09)."""
    items = _items(1, 2, 3)
    # Items 1 and 2 already searched; 3 is the last unsearched
    log = ["1", "2"]
    batch, new_log, pass_completed = prioritize_batch(items, log, 3, _id_key)
    # batch = [3] (only unsearched), top up with 1, 2 → [3, 1, 2]
    assert {it["id"] for it in batch} == {1, 2, 3}
    assert pass_completed is True
    # new_log contains all eligible IDs
    assert set(new_log) == {"1", "2", "3"}


def test_prioritize_batch_mid_pass_no_completion():
    """When unsearched items remain after batch, pass_completed is False (QUEUE-09)."""
    items = _items(1, 2, 3, 4, 5)
    log = ["1"]  # only 1 searched; still need to search 2, 3, 4, 5
    batch, new_log, pass_completed = prioritize_batch(items, log, 2, _id_key)
    # unsearched = [2, 3, 4, 5]; batch = [2, 3]
    assert [it["id"] for it in batch] == [2, 3]
    assert pass_completed is False
    # log grew: 1 (survivor), 2, 3 appended
    assert new_log == ["1", "2", "3"]


def test_prioritize_batch_prune_departed_items():
    """Log entries for items no longer eligible are dropped, survivor order preserved (QUEUE-10)."""
    items = _items(1, 2, 4)  # item 3 has left (no longer eligible)
    log = ["1", "3", "2"]  # 3 was searched but is now gone
    batch, new_log, pass_completed = prioritize_batch(items, log, 5, _id_key)
    # pruned log: ["1", "2"] (3 dropped, order preserved)
    # unsearched = [4]; batch = [4, 1, 2] (4 unsearched first, then top up oldest: 1, 2)
    assert [it["id"] for it in batch] == [4, 1, 2]
    # new_log: 1 and 2 moved to tail (re-searched), 3 gone
    assert "3" not in new_log
    assert set(new_log) == {"1", "2", "4"}
    assert pass_completed is True


def test_prioritize_batch_research_recency():
    """A re-batched already-searched item moves to the log tail (most recent)."""
    items = _items(1, 2, 3)
    # All already searched, log order: 1 oldest, 3 newest
    log = ["1", "2", "3"]
    batch, new_log, pass_completed = prioritize_batch(items, log, 2, _id_key)
    # unsearched = []; top up from oldest: [1, 2]
    assert [it["id"] for it in batch] == [1, 2]
    # After re-batching 1 and 2, they move to tail; 3 stays as the front (oldest)
    assert new_log == ["3", "1", "2"]
    # All 3 eligible IDs remain in new_log (3 survived, 1 and 2 re-appended)
    # bool(batch)=True and {"1","2","3"} ⊆ {"3","1","2"} → pass_completed=True
    assert pass_completed is True


def test_prioritize_batch_empty_eligible():
    """Empty eligible list always returns ([], [], False) — no pass completion (Pitfall 2)."""
    batch, new_log, pass_completed = prioritize_batch([], ["1", "2"], 5, _id_key)
    assert batch == []
    assert new_log == []
    assert pass_completed is False


def test_prioritize_batch_eligible_smaller_than_batch():
    """All eligible items fit in one batch: pass_completed=True (non-empty batch guard)."""
    items = _items(1, 2)
    log = ["1"]  # item 2 still unsearched
    batch, new_log, pass_completed = prioritize_batch(items, log, 10, _id_key)
    # unsearched = [2]; top up with [1]; batch = [2, 1]
    assert {it["id"] for it in batch} == {1, 2}
    assert pass_completed is True
    assert set(new_log) == {"1", "2"}


def test_prioritize_batch_zero_batch_size_guard():
    """MED-1: batch_size=0 → batch==[], pass_completed=False, log NOT grown.

    Proves the bool(batch) guard prevents a zero-search pass reset when the
    pruned log already covers the entire eligible set.
    """
    items = _items(1, 2, 3)
    # Log already covers all eligible items
    log = ["1", "2", "3"]
    batch, new_log, pass_completed = prioritize_batch(items, log, 0, _id_key)
    assert batch == []
    assert pass_completed is False
    # Log must NOT have grown (no new entries appended)
    assert new_log == ["1", "2", "3"]


def test_prioritize_batch_negative_batch_size_guard():
    """MED-1 (defensive): batch_size<0 → batch==[], pass_completed=False, log NOT grown."""
    items = _items(1, 2, 3)
    log = ["1", "2", "3"]
    batch, new_log, pass_completed = prioritize_batch(items, log, -1, _id_key)
    assert batch == []
    assert pass_completed is False
    assert new_log == ["1", "2", "3"]


def test_prioritize_batch_key_fn_sonarr_composite():
    """QUEUE-02: Sonarr composite key distinguishes seasons of the same series."""
    # S1 and S2 of series 1 must be distinct keys
    s1_e1 = {"seriesId": 1, "seasonNumber": 1}
    s2_e1 = {"seriesId": 1, "seasonNumber": 2}
    specials = {"seriesId": 1, "seasonNumber": 0}  # D-09: Specials are ordinary key "1:0"
    items = [s1_e1, s2_e1, specials]
    # Nothing searched yet
    batch, new_log, pass_completed = prioritize_batch(items, [], 2, _sonarr_key)
    assert len(batch) == 2
    assert new_log == ["1:1", "1:2"]
    assert pass_completed is False  # specials (1:0) still unsearched

    # Now search with S1 already in log; S2 and Specials unsearched
    batch2, new_log2, pass_completed2 = prioritize_batch(items, ["1:1"], 2, _sonarr_key)
    # unsearched = [s2_e1, specials]; batch = [s2_e1, specials]
    assert new_log2 == ["1:1", "1:2", "1:0"]
    assert pass_completed2 is True  # all 3 now in log


def test_prioritize_batch_key_fn_radarr_int_to_str():
    """QUEUE-02: Radarr key_fn converts int id to str for uniform list[str] log."""
    items = [{"id": 101}, {"id": 202}]
    batch, new_log, _pc = prioritize_batch(items, [], 5, _id_key)
    assert new_log == ["101", "202"]
    for key in new_log:
        assert isinstance(key, str)


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


def _make_test_state():
    """Return a default per-instance state nested under 'Default'."""
    from triggarr.state import _default_instance_state

    state = _default_state()
    state["radarr"] = {"Default": _default_instance_state()}
    state["sonarr"] = {"Default": _default_instance_state()}
    state["lidarr"] = {"Default": _default_instance_state()}
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

    state = _make_test_state()
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

    state = _make_test_state()
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
        side_effect=[httpx.ConnectError("boom"), None]
    )

    state = _make_test_state()
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

    state = _make_test_state()
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

    state = _make_test_state()
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

    state = _make_test_state()
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
        side_effect=[httpx.ConnectError("boom"), None]
    )

    state = _make_test_state()
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

    state = _make_test_state()
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

    state = _make_test_state()
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

    state = _make_test_state()
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
        side_effect=[httpx.ConnectError("boom"), None, None]
    )

    state = _make_test_state()
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
    client.search_movies = AsyncMock(side_effect=httpx.ConnectError("API timeout"))

    state = _make_test_state()
    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    from triggarr.db import get_recent_searches

    searches = await get_recent_searches(db)
    assert len(searches) == 1
    assert searches[0]["name"] == "Movie Fail"
    assert searches[0]["outcome"] == "failed"
    assert "HTTP error" in searches[0]["detail"]
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
    client.search_season = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    state = _make_test_state()
    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    from triggarr.db import get_recent_searches

    searches = await get_recent_searches(db)
    assert len(searches) == 1
    assert "Show Fail" in searches[0]["name"]
    assert searches[0]["outcome"] == "failed"
    assert "HTTP error" in searches[0]["detail"]
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

    state = _make_test_state()
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

    state = _make_test_state()
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

    state = _make_test_state()
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

    state = _make_test_state()
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

    state = _make_test_state()
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

    state = _make_test_state()
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

    state = _make_test_state()
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

    state = _make_test_state()
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


# ---------------------------------------------------------------------------
# filter_by_tag and tag accessors (Phase 36)
# ---------------------------------------------------------------------------


def test_filter_by_tag_radarr():
    """filter_by_tag with _radarr_tags returns only items with matching tag ID."""
    from triggarr.search.engine import _radarr_tags, filter_by_tag

    items = [
        {"id": 1, "title": "Movie A", "tags": [1, 2, 3]},
        {"id": 2, "title": "Movie B", "tags": [4, 5]},
        {"id": 3, "title": "Movie C", "tags": [2, 6]},
    ]
    result = filter_by_tag(items, 2, _radarr_tags)
    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["id"] == 3


def test_filter_by_tag_sonarr():
    """filter_by_tag with _sonarr_tags returns only episodes with matching series tag."""
    from triggarr.search.engine import _sonarr_tags, filter_by_tag

    items = [
        {"episodeId": 100, "series": {"tags": [5, 6]}},
        {"episodeId": 101, "series": {"tags": [7]}},
        {"episodeId": 102, "series": {"tags": [5, 8]}},
    ]
    result = filter_by_tag(items, 5, _sonarr_tags)
    assert len(result) == 2
    assert result[0]["episodeId"] == 100
    assert result[1]["episodeId"] == 102


def test_filter_by_tag_empty_list():
    """filter_by_tag with empty items list returns empty list."""
    from triggarr.search.engine import _radarr_tags, filter_by_tag

    result = filter_by_tag([], 1, _radarr_tags)
    assert result == []


def test_filter_by_tag_no_match():
    """filter_by_tag where no items match returns empty list."""
    from triggarr.search.engine import _radarr_tags, filter_by_tag

    items = [
        {"id": 1, "tags": [1, 2]},
        {"id": 2, "tags": [3, 4]},
    ]
    result = filter_by_tag(items, 99, _radarr_tags)
    assert result == []


def test_radarr_tags_accessor():
    """_radarr_tags returns item.get('tags', [])."""
    from triggarr.search.engine import _radarr_tags

    assert _radarr_tags({"tags": [1, 2, 3]}) == [1, 2, 3]
    assert _radarr_tags({}) == []


def test_sonarr_tags_accessor():
    """_sonarr_tags returns item.get('series', {}).get('tags', [])."""
    from triggarr.search.engine import _sonarr_tags

    assert _sonarr_tags({"series": {"tags": [5, 6]}}) == [5, 6]
    assert _sonarr_tags({}) == []
    assert _sonarr_tags({"series": {}}) == []


def test_sonarr_tag_filter_before_dedup():
    """Sonarr tag filtering must happen BEFORE deduplication.

    Episodes have series.tags but deduplicated season dicts do not.
    """
    from triggarr.search.engine import _sonarr_tags, filter_by_tag

    # Episodes with series.tags -- filterable
    episodes = [
        {"episodeId": 1, "seriesId": 10, "seasonNumber": 1, "series": {"title": "Show A", "tags": [5]}},
        {"episodeId": 2, "seriesId": 20, "seasonNumber": 1, "series": {"title": "Show B", "tags": [6]}},
    ]
    filtered = filter_by_tag(episodes, 5, _sonarr_tags)
    assert len(filtered) == 1
    assert filtered[0]["seriesId"] == 10

    # Deduplicated dicts lose series.tags -- cannot filter
    from triggarr.search.engine import deduplicate_to_seasons

    deduped = deduplicate_to_seasons(episodes)
    deduped_filtered = filter_by_tag(deduped, 5, _sonarr_tags)
    assert deduped_filtered == []  # No series.tags on deduped dicts


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


# ---------------------------------------------------------------------------
# TAG-01/TAG-02/TAG-03: Radarr cycle tag filtering integration
# ---------------------------------------------------------------------------


async def test_radarr_cycle_missing_tag_filters(tmp_path):
    """Radarr cycle with missing_tag configured filters missing items by tag."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[
        Tag(id=5, label="triggarr"),
        Tag(id=6, label="other"),
    ])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True, "tags": [5]},
        {"id": 2, "title": "Movie B", "monitored": True, "tags": [6]},
        {"id": 3, "title": "Movie C", "monitored": True, "tags": [5, 6]},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="triggarr",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    # Only movies with tag 5 (Movie A, Movie C) should be searched
    assert client.search_movies.call_count == 2
    client.search_movies.assert_any_call([1])
    client.search_movies.assert_any_call([3])
    client.get_tags.assert_awaited_once()
    await db.close()


async def test_radarr_cycle_cutoff_tag_filters(tmp_path):
    """Radarr cycle with cutoff_tag configured filters cutoff items by tag."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[
        Tag(id=5, label="triggarr"),
        Tag(id=6, label="other"),
    ])
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=[
        {"id": 10, "title": "Cutoff A", "monitored": True, "tags": [5]},
        {"id": 11, "title": "Cutoff B", "monitored": True, "tags": [6]},
        {"id": 12, "title": "Cutoff C", "monitored": True, "tags": [5]},
    ])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        cutoff_tag="triggarr",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    # Only cutoff items with tag 5 (Cutoff A, Cutoff C) should be searched
    assert client.search_movies.call_count == 2
    client.search_movies.assert_any_call([10])
    client.search_movies.assert_any_call([12])
    await db.close()


async def test_radarr_cycle_no_tag_searches_all(tmp_path):
    """Radarr cycle with no tags configured searches all monitored items."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True, "tags": [5]},
        {"id": 2, "title": "Movie B", "monitored": True, "tags": [6]},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="", cutoff_tag="",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    # All items searched, get_tags NOT called
    assert client.search_movies.call_count == 2
    client.get_tags.assert_not_awaited()
    await db.close()


async def test_no_tag_api_call_when_unconfigured(tmp_path):
    """Explicit check that get_tags is never called when both tags are empty."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[
        {"id": 2, "title": "Movie B", "monitored": True},
    ])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    client.get_tags.assert_not_awaited()
    await db.close()


async def test_radarr_tag_resolution_failure_searches_all(tmp_path):
    """Radarr cycle with tag not found in tag list searches all items (fail-open)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[
        Tag(id=5, label="existing-tag"),
    ])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True, "tags": [5]},
        {"id": 2, "title": "Movie B", "monitored": True, "tags": []},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="nonexistent",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    # Tag not found -> fail-open, all monitored items searched
    assert client.search_movies.call_count == 2
    await db.close()


# ---------------------------------------------------------------------------
# TAG-01/TAG-02/TAG-03: Sonarr cycle tag filtering integration
# ---------------------------------------------------------------------------


def _make_tagged_sonarr_episode(
    series_id: int,
    season_number: int,
    series_title: str = "Show",
    episode_id: int = 1,
    series_tags: list[int] | None = None,
) -> dict:
    """Build a Sonarr episode dict with series tags for tag filtering tests."""
    return {
        "id": episode_id,
        "seriesId": series_id,
        "seasonNumber": season_number,
        "monitored": True,
        "airDateUtc": "2025-01-01T00:00:00Z",
        "series": {"title": series_title, "tags": series_tags or []},
    }


async def test_sonarr_cycle_missing_tag_filters(tmp_path):
    """Sonarr cycle with missing_tag filters episodes by series.tags BEFORE dedup."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=10, label="triggarr")])
    # Series A (tags [10]): 2 episodes -> passes tag filter
    # Series B (no tags): 2 episodes -> filtered out
    _ep = _make_tagged_sonarr_episode
    client.get_wanted_missing = AsyncMock(return_value=[
        _ep(series_id=100, season_number=1, series_title="Show A", episode_id=1, series_tags=[10]),
        _ep(series_id=100, season_number=1, series_title="Show A", episode_id=2, series_tags=[10]),
        _ep(series_id=200, season_number=1, series_title="Show B", episode_id=3, series_tags=[]),
        _ep(series_id=200, season_number=2, series_title="Show B", episode_id=4, series_tags=[]),
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_season = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://sonarr:8989", api_key="test-key", enabled=True,
        search_missing_count=10, search_cutoff_count=10,
        missing_tag="triggarr",
    )
    settings = _cycle_settings(missing_count=10, cutoff_count=10)

    await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    # Only Series A's season 1 should be searched (after tag filter + dedup)
    assert client.search_season.call_count == 1
    client.search_season.assert_called_once_with(100, 1)
    client.get_tags.assert_awaited_once()
    await db.close()


async def test_sonarr_cycle_cutoff_tag_filters(tmp_path):
    """Sonarr cycle with cutoff_tag filters cutoff episodes by series.tags."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=10, label="triggarr")])
    client.get_wanted_missing = AsyncMock(return_value=[])
    # Series A (tags [10]): 1 episode -> passes; Series B (no tags): 1 episode -> filtered
    _ep = _make_tagged_sonarr_episode
    client.get_wanted_cutoff = AsyncMock(return_value=[
        _ep(series_id=100, season_number=1, series_title="Show A", episode_id=1, series_tags=[10]),
        _ep(series_id=200, season_number=1, series_title="Show B", episode_id=2, series_tags=[]),
    ])
    client.search_season = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://sonarr:8989", api_key="test-key", enabled=True,
        search_missing_count=10, search_cutoff_count=10,
        cutoff_tag="triggarr",
    )
    settings = _cycle_settings(missing_count=10, cutoff_count=10)

    await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    # Only Series A searched in cutoff queue
    assert client.search_season.call_count == 1
    client.search_season.assert_called_once_with(100, 1)
    await db.close()


async def test_sonarr_cycle_no_tag_searches_all(tmp_path):
    """Sonarr cycle with no tags configured searches all, get_tags NOT called."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[])
    _ep = _make_tagged_sonarr_episode
    client.get_wanted_missing = AsyncMock(return_value=[
        _ep(series_id=100, season_number=1, series_title="Show A", episode_id=1, series_tags=[10]),
        _ep(series_id=200, season_number=1, series_title="Show B", episode_id=2, series_tags=[]),
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_season = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://sonarr:8989", api_key="test-key", enabled=True,
        search_missing_count=10, search_cutoff_count=10,
        missing_tag="", cutoff_tag="",
    )
    settings = _cycle_settings(missing_count=10, cutoff_count=10)

    await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    # Both series searched (2 seasons after dedup)
    assert client.search_season.call_count == 2
    client.get_tags.assert_not_awaited()
    await db.close()


async def test_sonarr_tag_resolution_failure_searches_all(tmp_path):
    """Sonarr cycle with tag not found in tag list searches all (fail-open)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=10, label="existing-tag")])
    _ep = _make_tagged_sonarr_episode
    client.get_wanted_missing = AsyncMock(return_value=[
        _ep(series_id=100, season_number=1, series_title="Show A", episode_id=1, series_tags=[10]),
        _ep(series_id=200, season_number=1, series_title="Show B", episode_id=2, series_tags=[]),
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_season = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://sonarr:8989", api_key="test-key", enabled=True,
        search_missing_count=10, search_cutoff_count=10,
        missing_tag="nonexistent",
    )
    settings = _cycle_settings(missing_count=10, cutoff_count=10)

    await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    # Tag not found -> fail-open, all seasons searched
    assert client.search_season.call_count == 2
    await db.close()


# ---------------------------------------------------------------------------
# BUG-02: engine.py KeyError -- setdefault guard for missing instance state
# ---------------------------------------------------------------------------


async def test_radarr_cycle_missing_instance_state_skips(tmp_path):
    """run_radarr_cycle with instance_name NOT in state skips gracefully."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=[])

    # State has radarr key but NO entry for "NewInstance"
    state = _default_state()  # radarr: {}, sonarr: {}
    instance_config = _cycle_instance_config()
    settings = _cycle_settings()

    # This should NOT raise KeyError -- skips early instead
    result = await run_radarr_cycle(client, state, "NewInstance", instance_config, settings, db)

    # Should NOT have created state entry (returns early)
    assert "NewInstance" not in result["radarr"]
    # API calls should not have been made
    client.get_wanted_missing.assert_not_awaited()
    await db.close()


async def test_sonarr_cycle_missing_instance_state_skips(tmp_path):
    """run_sonarr_cycle with instance_name NOT in state skips gracefully."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=[])

    # State has sonarr key but NO entry for "NewInstance"
    state = _default_state()
    instance_config = _cycle_instance_config()
    settings = _cycle_settings()

    # This should NOT raise KeyError -- skips early instead
    result = await run_sonarr_cycle(client, state, "NewInstance", instance_config, settings, db)

    assert "NewInstance" not in result["sonarr"]
    client.get_wanted_missing.assert_not_awaited()
    await db.close()


# ---------------------------------------------------------------------------
# BUG-08: Tag fetch failure logging (no false "tag not found" warning)
# ---------------------------------------------------------------------------


async def test_radarr_tag_fetch_failure_no_tag_not_found_warning(tmp_path):
    """When get_tags() raises, 'tag not found' warning must NOT fire (BUG-08)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[{"id": 1, "title": "Movie A", "monitored": True}]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()
    client.get_tags = AsyncMock(side_effect=httpx.ConnectError("refused"))

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="triggarr",
    )
    settings = _cycle_settings()

    # Capture log output
    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        logger.remove(handler_id)

    log_output = sink.getvalue()
    assert "Failed to fetch tags" in log_output, "Should log tag fetch failure"
    assert "not found" not in log_output, "Should NOT log 'tag not found' when fetch failed"
    await db.close()


async def test_radarr_tag_fetch_success_empty_list_no_tag_not_found(tmp_path):
    """When get_tags() succeeds with empty list, 'tag not found' warning SHOULD fire (BUG-08).

    This distinguishes a successful fetch returning no tags from a failed fetch.
    """
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[{"id": 1, "title": "Movie A", "monitored": True}]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()
    # Successful fetch, but empty tag list
    client.get_tags = AsyncMock(return_value=[])

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="triggarr",
    )
    settings = _cycle_settings()

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        logger.remove(handler_id)

    log_output = sink.getvalue()
    # With tag_fetch_ok=True, "tag not found" warning SHOULD fire for empty tag list
    assert "not found" in log_output, "Should log 'tag not found' when fetch succeeded but tag missing"
    assert "Failed to fetch tags" not in log_output, "Should NOT log fetch failure"
    await db.close()


# ---------------------------------------------------------------------------
# BUG-09: cleanup_orphaned_instances immutability
# ---------------------------------------------------------------------------


def test_cleanup_orphaned_instances_does_not_mutate_input():
    """cleanup_orphaned_instances returns new dict without mutating input (BUG-09)."""
    from tests.conftest import make_settings
    from triggarr.state import AppState, TriggarrState, cleanup_orphaned_instances

    settings = make_settings()
    state = TriggarrState(
        radarr={
            "Default": AppState(missing_cursor=5, cutoff_cursor=2, last_run=None),
            "OldInstance": AppState(missing_cursor=99, cutoff_cursor=88, last_run=None),
        },
        sonarr={
            "Default": AppState(missing_cursor=3, cutoff_cursor=0, last_run=None),
        },
        search_log=[],
    )

    # Keep a reference to the original radarr dict
    original_radarr = state["radarr"]

    result = cleanup_orphaned_instances(state, settings)

    # Result should not contain orphan
    assert "OldInstance" not in result["radarr"]
    assert "Default" in result["radarr"]

    # Input must NOT be mutated
    assert "OldInstance" in original_radarr, "Original state dict must not be mutated"
    assert state is not result, "Should return a new dict, not the same object"


# ---------------------------------------------------------------------------
# BUG-10: Test helper rename (_make_test_state)
# ---------------------------------------------------------------------------


def test_make_test_state_helper_works():
    """_make_test_state helper produces valid state with Default instances (BUG-10)."""
    state = _make_test_state()
    assert "radarr" in state
    assert "Default" in state["radarr"]
    assert state["radarr"]["Default"]["missing_cursor"] == 0
    assert "sonarr" in state
    assert "Default" in state["sonarr"]
    assert state["sonarr"]["Default"]["missing_cursor"] == 0


# ---------------------------------------------------------------------------
# TAG-05: Tag warning state storage
# ---------------------------------------------------------------------------


async def test_tag_warning_state_stored_when_tag_not_found_radarr(tmp_path):
    """Radarr cycle stores tag_warnings with {tag, field} dicts when configured tag is not found."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="existing-tag")])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True, "tags": [5]},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="nonexistent",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    ist = state["radarr"]["Default"]
    assert "tag_warnings" in ist
    assert {"tag": "nonexistent", "field": "missing"} in ist["tag_warnings"]
    await db.close()


async def test_tag_warning_state_stored_when_tag_not_found_sonarr(tmp_path):
    """Sonarr cycle stores tag_warnings with {tag, field} dicts when configured tag is not found."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    _ep = _make_tagged_sonarr_episode
    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=10, label="existing-tag")])
    client.get_wanted_missing = AsyncMock(return_value=[
        _ep(series_id=100, season_number=1, series_title="Show A", episode_id=1, series_tags=[10]),
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_season = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://sonarr:8989", api_key="test-key", enabled=True,
        search_missing_count=10, search_cutoff_count=10,
        missing_tag="nonexistent",
    )
    settings = _cycle_settings(missing_count=10, cutoff_count=10)

    await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    ist = state["sonarr"]["Default"]
    assert "tag_warnings" in ist
    assert {"tag": "nonexistent", "field": "missing"} in ist["tag_warnings"]
    await db.close()


async def test_tag_warning_state_empty_when_tags_resolve(tmp_path):
    """Radarr cycle stores empty tag_warnings when configured tags resolve successfully."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="triggarr")])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True, "tags": [5]},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="triggarr",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    ist = state["radarr"]["Default"]
    assert "tag_warnings" in ist
    assert ist["tag_warnings"] == []
    await db.close()


async def test_tag_warning_state_empty_when_no_tags_configured(tmp_path):
    """Radarr cycle stores tag_warnings=[] when no tags are configured."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="", cutoff_tag="",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    ist = state["radarr"]["Default"]
    assert "tag_warnings" in ist
    assert ist["tag_warnings"] == []
    await db.close()


async def test_tag_warning_state_cleared_each_cycle(tmp_path):
    """Tag warnings are cleared at start of each cycle (not accumulated)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="existing-tag")])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True, "tags": [5]},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="nonexistent",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    # Run cycle twice
    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert len(state["radarr"]["Default"]["tag_warnings"]) == 1

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    # Should still be 1, not 2 (no accumulation)
    assert len(state["radarr"]["Default"]["tag_warnings"]) == 1
    await db.close()


async def test_tag_warning_state_cutoff_tag_not_found(tmp_path):
    """Radarr cycle stores cutoff tag warning when cutoff tag is not found."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="existing-tag")])
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True, "tags": [5]},
    ])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="nonexistent-missing",
        cutoff_tag="nonexistent-cutoff",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    ist = state["radarr"]["Default"]
    assert {"tag": "nonexistent-missing", "field": "missing"} in ist["tag_warnings"]
    assert {"tag": "nonexistent-cutoff", "field": "cutoff"} in ist["tag_warnings"]
    await db.close()


async def test_tag_warnings_cleared_on_radarr_connectivity_failure(tmp_path):
    """Radarr cycle sets tag_warnings=[] when instance is unreachable."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(side_effect=httpx.HTTPError("Connection refused"))

    state = _make_test_state()
    # Pre-populate stale tag warnings
    state["radarr"]["Default"]["tag_warnings"] = [{"tag": "stale", "field": "missing"}]
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    ist = state["radarr"]["Default"]
    assert ist["tag_warnings"] == []
    assert ist["connected"] is False
    await db.close()


async def test_tag_warnings_cleared_on_sonarr_connectivity_failure(tmp_path):
    """Sonarr cycle sets tag_warnings=[] when instance is unreachable."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(side_effect=httpx.HTTPError("Connection refused"))

    state = _make_test_state()
    # Pre-populate stale tag warnings
    state["sonarr"]["Default"]["tag_warnings"] = [{"tag": "stale", "field": "missing"}]
    instance_config = InstanceConfig(
        url="http://sonarr:8989", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    ist = state["sonarr"]["Default"]
    assert ist["tag_warnings"] == []
    assert ist["connected"] is False
    await db.close()


# ---------------------------------------------------------------------------
# run_lidarr_cycle
# ---------------------------------------------------------------------------


async def test_run_lidarr_cycle_happy_path(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 101, "title": "Album A", "monitored": True},
            {"id": 102, "title": "Album B", "monitored": True},
        ]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=50)
    client.search_albums = AsyncMock()

    state = _make_test_state()
    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)

    assert client.search_albums.call_count == 2
    client.search_albums.assert_any_call([101])
    client.search_albums.assert_any_call([102])

    ist = result["lidarr"]["Default"]
    assert ist["last_run"] is not None
    assert ist["connected"] is True
    assert ist["missing_cursor"] == 0  # 2 items, batch 2, wraps
    assert ist["missing_count"] == 2
    assert ist["total_items"] == 50
    await db.close()


async def test_run_lidarr_cycle_network_failure(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))

    state = _make_test_state()
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)

    ist = result["lidarr"]["Default"]
    assert ist["connected"] is False
    assert ist["unreachable_since"] is not None
    assert ist["missing_cursor"] == 0  # unchanged
    client.search_albums.assert_not_called()
    await db.close()


async def test_run_lidarr_cycle_per_item_skip(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 201, "title": "Good Album", "monitored": True},
            {"id": 202, "title": "Bad Album", "monitored": True},
        ]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    # First call succeeds, second raises
    client.search_albums = AsyncMock(side_effect=[None, httpx.TimeoutException("timeout")])

    state = _make_test_state()
    settings = _cycle_settings(missing_count=5, cutoff_count=0)
    instance_config = _cycle_instance_config(missing_count=5, cutoff_count=0)

    result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)

    assert client.search_albums.call_count == 2  # both attempted
    ist = result["lidarr"]["Default"]
    assert ist["connected"] is True  # cycle didn't abort
    await db.close()


async def test_run_lidarr_cycle_cursor_advancement(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    albums = [
        {"id": i, "title": f"Album {i}", "monitored": True}
        for i in range(1, 6)
    ]

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=albums)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=20)
    client.search_albums = AsyncMock()

    state = _make_test_state()
    settings = _cycle_settings(missing_count=2, cutoff_count=0)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

    # First cycle: searches items 0,1 (albums 1,2)
    result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
    assert result["lidarr"]["Default"]["missing_cursor"] == 2
    assert client.search_albums.call_count == 2

    # Second cycle: searches items 2,3 (albums 3,4)
    client.search_albums.reset_mock()
    result = await run_lidarr_cycle(client, result, "Default", instance_config, settings, db)
    assert result["lidarr"]["Default"]["missing_cursor"] == 4
    assert client.search_albums.call_count == 2

    # Third cycle: searches item 4 (album 5), then wraps
    client.search_albums.reset_mock()
    result = await run_lidarr_cycle(client, result, "Default", instance_config, settings, db)
    assert result["lidarr"]["Default"]["missing_cursor"] == 0  # wrapped
    assert client.search_albums.call_count == 1
    await db.close()


async def test_run_lidarr_cycle_missing_instance_state_skips(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    state = _make_test_state()
    del state["lidarr"]["Default"]  # remove instance from state

    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)

    client.get_wanted_missing.assert_not_called()
    assert "Default" not in result["lidarr"]
    await db.close()


async def test_lidarr_cycle_missing_tag_filters(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 1, "title": "Tagged Album", "monitored": True, "artist": {"tags": [5]}},
            {"id": 2, "title": "Untagged Album", "monitored": True, "artist": {"tags": []}},
        ]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="music-tag")])
    client.search_albums = AsyncMock()

    state = _make_test_state()
    settings = _cycle_settings(missing_count=5, cutoff_count=0)
    instance_config = _cycle_instance_config(missing_count=5, cutoff_count=0)
    instance_config.missing_tag = "music-tag"

    result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)

    # Only the tagged album should be searched
    assert client.search_albums.call_count == 1
    client.search_albums.assert_called_once_with([1])
    assert result["lidarr"]["Default"]["missing_eligible"] == 1
    await db.close()


async def test_lidarr_tags_accessor():
    """Verify _lidarr_tags extracts tags from artist object."""
    album = {"id": 1, "title": "Test", "artist": {"tags": [3, 7]}}
    assert _lidarr_tags(album) == [3, 7]

    album_no_artist = {"id": 2, "title": "No Artist"}
    assert _lidarr_tags(album_no_artist) == []


async def test_lidarr_tag_resolution_failure_searches_all_and_stores_warning(tmp_path):
    """Lidarr cycle with tag not found searches all items (fail-open) and stores tag_warnings (SRCH-03)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    try:
        client = AsyncMock()
        client.get_tags = AsyncMock(return_value=[Tag(id=5, label="existing-tag")])
        client.get_wanted_missing = AsyncMock(return_value=[
            {"id": 1, "title": "Album A", "monitored": True, "artist": {"tags": [5]}},
            {"id": 2, "title": "Album B", "monitored": True, "artist": {"tags": []}},
        ])
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.get_library_count = AsyncMock(return_value=10)
        client.search_albums = AsyncMock()

        state = _make_test_state()
        instance_config = InstanceConfig(
            url="http://lidarr:8686", api_key="test-key", enabled=True,
            search_missing_count=5, search_cutoff_count=5,
            missing_tag="nonexistent",
        )
        settings = _cycle_settings(missing_count=5, cutoff_count=5)

        await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)

        # Tag not found -> fail-open, all monitored albums searched
        assert client.search_albums.call_count == 2

        # Tag warning stored in state
        ist = state["lidarr"]["Default"]
        assert "tag_warnings" in ist
        assert {"tag": "nonexistent", "field": "missing"} in ist["tag_warnings"]
    finally:
        await db.close()


async def test_tag_warnings_cleared_on_lidarr_connectivity_failure(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))

        state = _make_test_state()
        state["lidarr"]["Default"]["tag_warnings"] = [{"tag": "stale", "field": "missing"}]

        settings = _cycle_settings()
        instance_config = _cycle_instance_config()

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)

        ist = result["lidarr"]["Default"]
        assert ist["tag_warnings"] == []
        assert ist["connected"] is False
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Connection failure gap tests (Phase 46, Plan 01)
# ---------------------------------------------------------------------------


async def test_run_radarr_cycle_dns_failure(tmp_path):
    """Radarr cycle aborts gracefully on DNS resolution failure (CONN-02)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        side_effect=httpx.ConnectError("[Errno -2] Name or service not known")
    )

    state = _make_test_state()
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["connected"] is False
    await db.close()


async def test_run_radarr_cycle_ssl_error(tmp_path):
    """Radarr cycle aborts gracefully on SSL/TLS error (CONN-03)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        side_effect=httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED]")
    )

    state = _make_test_state()
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["connected"] is False
    await db.close()


async def test_run_radarr_cycle_timeout_aborts(tmp_path):
    """Radarr cycle aborts gracefully on timeout during fetch (CONN-01 gap)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        side_effect=httpx.TimeoutException("timed out")
    )

    state = _make_test_state()
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["connected"] is False
    await db.close()


async def test_run_radarr_cycle_sets_unreachable_since(tmp_path):
    """Radarr cycle sets unreachable_since on first connection failure (CONN-01 gap)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        side_effect=httpx.ConnectError("refused")
    )

    state = _make_test_state()
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["unreachable_since"] is not None
    assert isinstance(result["radarr"]["Default"]["unreachable_since"], str)
    await db.close()


async def test_run_radarr_cycle_preserves_unreachable_since(tmp_path):
    """Radarr cycle preserves existing unreachable_since on repeat failure (CONN-01 gap)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        side_effect=httpx.ConnectError("refused")
    )

    state = _make_test_state()
    state["radarr"]["Default"]["unreachable_since"] = "2026-01-01T00:00:00Z"
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["unreachable_since"] == "2026-01-01T00:00:00Z"
    await db.close()


async def test_run_radarr_cycle_all_searches_fail(tmp_path):
    """Radarr cycle completes without crash when all search commands fail (CONN-04 gap)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 1, "monitored": True, "title": "M1"},
            {"id": 2, "monitored": True, "title": "M2"},
        ]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=100)
    client.get_tags = AsyncMock(return_value=[])
    client.search_movies = AsyncMock(side_effect=httpx.ConnectError("instance down"))
    client.get_grab_history = AsyncMock(return_value=[])

    state = _make_test_state()
    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    # Fetch succeeded so connected is True
    assert result["radarr"]["Default"]["connected"] is True
    # Both items attempted (even though both failed)
    assert client.search_movies.call_count == 2
    await db.close()


# ---------------------------------------------------------------------------
# Bad API response cycle tests (Phase 46, Plan 02)
# ---------------------------------------------------------------------------


async def test_run_radarr_cycle_403_aborts(tmp_path):
    """Radarr cycle aborts gracefully on 403 Forbidden during fetch (API-02)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    request = httpx.Request("GET", "http://test/api/v3/wanted/missing")
    response = httpx.Response(403, request=request)
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        side_effect=httpx.HTTPStatusError("Forbidden", request=request, response=response)
    )

    state = _make_test_state()
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["connected"] is False
    await db.close()


async def test_run_radarr_cycle_502_aborts(tmp_path):
    """Radarr cycle aborts gracefully on 502 Bad Gateway during fetch (API-02)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    request = httpx.Request("GET", "http://test/api/v3/wanted/missing")
    response = httpx.Response(502, request=request)
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        side_effect=httpx.HTTPStatusError("Bad Gateway", request=request, response=response)
    )

    state = _make_test_state()
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["connected"] is False
    await db.close()


async def test_run_radarr_cycle_403_per_item_skip(tmp_path):
    """Radarr cycle continues when per-item search gets 403 Forbidden (API-02)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 1, "monitored": True, "title": "M1"},
            {"id": 2, "monitored": True, "title": "M2"},
        ]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=100)
    client.get_tags = AsyncMock(return_value=[])
    search_request = httpx.Request("POST", "http://test/api/v3/command")
    search_response = httpx.Response(403, request=search_request)
    client.search_movies = AsyncMock(
        side_effect=httpx.HTTPStatusError("Forbidden", request=search_request, response=search_response)
    )
    client.get_grab_history = AsyncMock(return_value=[])

    state = _make_test_state()
    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    # Fetch succeeded so connected is True (only per-item search failed)
    assert result["radarr"]["Default"]["connected"] is True
    # Both items attempted
    assert client.search_movies.call_count == 2
    await db.close()


async def test_run_radarr_cycle_malformed_json_aborts(tmp_path):
    """Radarr cycle aborts gracefully on malformed JSON / ValidationError during fetch (API-01)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    # Capture a real ValidationError to use as side_effect
    with pytest.raises(ValidationError) as exc_info:
        TypeAdapter(int).validate_python("not_int")
    client.get_wanted_missing = AsyncMock(side_effect=exc_info.value)

    state = _make_test_state()
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["connected"] is False
    await db.close()


# --- Empty queue and tag filtering edge cases (SRCH-01, SRCH-02) ---
# These provide integration-level confidence that empty/fully-filtered queues
# propagate correctly through the full cycle, complementing unit-level coverage
# in test_slice_batch_empty_list and test_filter_by_tag_empty_list.


async def test_run_radarr_cycle_empty_queues(tmp_path):
    """Radarr cycle with empty missing and cutoff queues makes zero searches (SRCH-01)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=[])
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_movies = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings()
        instance_config = _cycle_instance_config()

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

        assert client.search_movies.call_count == 0
        assert result["radarr"]["Default"]["missing_cursor"] == 0
        assert result["radarr"]["Default"]["cutoff_cursor"] == 0
        assert result["radarr"]["Default"]["connected"] is True
    finally:
        await db.close()


async def test_run_sonarr_cycle_empty_queues(tmp_path):
    """Sonarr cycle with empty missing and cutoff queues makes zero searches (SRCH-01)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=[])
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_season = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings()
        instance_config = _cycle_instance_config()

        result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

        assert client.search_season.call_count == 0
        assert result["sonarr"]["Default"]["missing_cursor"] == 0
        assert result["sonarr"]["Default"]["cutoff_cursor"] == 0
        assert result["sonarr"]["Default"]["connected"] is True
    finally:
        await db.close()


async def test_run_lidarr_cycle_empty_queues(tmp_path):
    """Lidarr cycle with empty missing and cutoff queues makes zero searches (SRCH-01)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=[])
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.get_library_count = AsyncMock(return_value=0)
        client.search_albums = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings()
        instance_config = _cycle_instance_config()

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)

        assert client.search_albums.call_count == 0
        assert result["lidarr"]["Default"]["missing_cursor"] == 0
        assert result["lidarr"]["Default"]["cutoff_cursor"] == 0
        assert result["lidarr"]["Default"]["connected"] is True
    finally:
        await db.close()


async def test_radarr_cycle_all_filtered_by_tag(tmp_path):
    """Radarr cycle with all items filtered out by tag makes zero searches (SRCH-02)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    try:
        client = AsyncMock()
        client.get_tags = AsyncMock(return_value=[Tag(id=5, label="triggarr")])
        client.get_wanted_missing = AsyncMock(return_value=[
            {"id": 1, "title": "Movie A", "monitored": True, "tags": [99]},
            {"id": 2, "title": "Movie B", "monitored": True, "tags": [99]},
        ])
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        # Explicitly mock get_library_count to avoid relying on AsyncMock auto-return
        client.get_library_count = AsyncMock(return_value=0)
        client.search_movies = AsyncMock()

        state = _make_test_state()
        instance_config = InstanceConfig(
            url="http://radarr:7878", api_key="test-key", enabled=True,
            search_missing_count=5, search_cutoff_count=5,
            missing_tag="triggarr",
        )
        settings = _cycle_settings(missing_count=5, cutoff_count=5)

        await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

        assert client.search_movies.call_count == 0
    finally:
        await db.close()


async def test_sonarr_cycle_all_filtered_by_tag(tmp_path):
    """Sonarr cycle with all episodes filtered out by tag makes zero searches (SRCH-02)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    try:
        _ep = _make_tagged_sonarr_episode
        client = AsyncMock()
        client.get_tags = AsyncMock(return_value=[Tag(id=10, label="triggarr")])
        client.get_wanted_missing = AsyncMock(return_value=[
            _ep(series_id=100, season_number=1, series_title="Show A", episode_id=1, series_tags=[99]),
            _ep(series_id=200, season_number=1, series_title="Show B", episode_id=2, series_tags=[99]),
        ])
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        # Explicitly mock get_library_count to avoid relying on AsyncMock auto-return
        client.get_library_count = AsyncMock(return_value=0)
        client.search_season = AsyncMock()

        state = _make_test_state()
        instance_config = InstanceConfig(
            url="http://sonarr:8989", api_key="test-key", enabled=True,
            search_missing_count=10, search_cutoff_count=10,
            missing_tag="triggarr",
        )
        settings = _cycle_settings(missing_count=10, cutoff_count=10)

        await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

        assert client.search_season.call_count == 0
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# RES-02: last_success written only at cycle success point
# ---------------------------------------------------------------------------


async def test_run_radarr_cycle_writes_last_success_on_success(tmp_path):
    """A successful run_radarr_cycle sets last_success to a non-None ISO timestamp."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[{"id": 1, "title": "Movie A", "monitored": True}]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    settings = _cycle_settings(missing_count=1, cutoff_count=1)
    instance_config = _cycle_instance_config(missing_count=1, cutoff_count=1)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    assert result["radarr"]["Default"]["last_success"] is not None
    await db.close()


async def test_run_radarr_cycle_does_not_write_last_success_on_failure(tmp_path):
    """A cycle that fails on connection error leaves last_success as None."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))

    state = _make_test_state()
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    assert result["radarr"]["Default"].get("last_success") is None
    await db.close()


# ---------------------------------------------------------------------------
# RES-03: get_tags_fn resolver param on cycle fns (tag cache threading)
# ---------------------------------------------------------------------------


async def test_run_radarr_cycle_uses_get_tags_fn_when_provided(tmp_path):
    """RES-03: when get_tags_fn is supplied, the cycle calls it instead of client.get_tags.

    A tag-configured instance with a resolver passed in must route tag
    resolution through the resolver — client.get_tags() is NOT awaited.
    """
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=9, label="should-not-be-used")])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True, "tags": [5]},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    resolver = AsyncMock(return_value=[Tag(id=5, label="triggarr")])

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="triggarr",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    await run_radarr_cycle(
        client, state, "Default", instance_config, settings, db, get_tags_fn=resolver
    )

    resolver.assert_awaited_once()
    client.get_tags.assert_not_awaited()
    await db.close()


async def test_run_radarr_cycle_falls_back_to_client_get_tags_when_no_fn(tmp_path):
    """RES-03 (Pitfall 1): with no get_tags_fn (None default), the cycle uses client.get_tags.

    Backward compatibility — a tag-configured instance still fetches tags via
    the client when no resolver is provided.
    """
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="triggarr")])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True, "tags": [5]},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="triggarr",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    client.get_tags.assert_awaited_once()
    await db.close()


async def test_run_radarr_cycle_get_tags_fn_exception_suppresses_filtering(tmp_path):
    """RES-03 (Pitfall 2/3): a get_tags_fn that raises is handled by the existing guard.

    When the resolver raises httpx.ConnectError, the cycle does NOT raise; the
    existing except guard sets tags=[] / tag_fetch_ok=False so tag filtering is
    suppressed and all monitored items are searched (no tag warning recorded,
    because tag_fetch_ok is False).
    """
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="triggarr")])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True, "tags": [5]},
        {"id": 2, "title": "Movie B", "monitored": True, "tags": [6]},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    resolver = AsyncMock(side_effect=httpx.ConnectError("tag fetch boom"))

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="triggarr",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    # Must not raise — the cycle's existing except guard handles it.
    result = await run_radarr_cycle(
        client, state, "Default", instance_config, settings, db, get_tags_fn=resolver
    )

    resolver.assert_awaited_once()
    # Tag filtering suppressed (tag_fetch_ok=False) -> both monitored items searched.
    assert client.search_movies.call_count == 2
    # No tag warning recorded because the fetch failed (tag_fetch_ok=False).
    assert result["radarr"]["Default"]["tag_warnings"] == []
    await db.close()
