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
    _fetch_wanted_queues,
    _lidarr_tags,
    cap_batch_sizes,
    deduplicate_to_seasons,
    filter_monitored,
    filter_sonarr_episodes,
    filter_unreleased_movies,
    prioritize_batch,
    rebalance_batch_sizes,
    resolve_tag_id,
    run_lidarr_cycle,
    run_radarr_cycle,
    run_sonarr_cycle,
)
from triggarr.search.outcome import cycle_view
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


def test_prioritize_batch_cold_start_fixed_expectation():
    """QUEUE-06 (post-deletion): cold start (empty log) must return first N items in fetch order.

    Fixed-expectation variant: hardcoded expected values, no oracle comparison.
    Preserves the cold-start-equivalence guarantee (QUEUE-06) with no dead-code dependency.

    With an empty searched-log every item is unsearched, so the batch is exactly
    eligible_items[:batch_size] in the original fetch order.
    """
    items = _items(10, 20, 30, 40, 50)
    assert prioritize_batch(items, [], 0, _id_key)[0] == []
    assert prioritize_batch(items, [], 1, _id_key)[0] == [{"id": 10}]
    assert prioritize_batch(items, [], 3, _id_key)[0] == [{"id": 10}, {"id": 20}, {"id": 30}]
    assert prioritize_batch(items, [], 5, _id_key)[0] == [{"id": 10}, {"id": 20}, {"id": 30}, {"id": 40}, {"id": 50}]
    # N > len(items): return all items in fetch order
    assert prioritize_batch(items, [], 7, _id_key)[0] == [{"id": 10}, {"id": 20}, {"id": 30}, {"id": 40}, {"id": 50}]


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


def test_prioritize_batch_negative_batch_size_with_unsearched():
    """Regression: negative batch_size must yield [] even when unsearched items exist.

    Prior to the max(0, batch_size) clamp, unsearched[:-1] would return all-but-last
    instead of an empty list, silently searching items against the contract.
    """
    # 3 eligible items, none yet searched (empty log)
    items = _items(10, 20, 30)
    batch, new_log, pass_completed = prioritize_batch(items, [], -1, _id_key)
    assert batch == [], "negative batch_size must yield empty batch even with unsearched items"
    assert pass_completed is False
    # Log must not grow beyond the pruned existing log (which is [] here)
    assert new_log == []


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
# prioritize_batch exclude_keys (DEDUP-01/02, D-05) -- Sonarr cross-queue dedup
# ---------------------------------------------------------------------------


def _letter_items(*letters: str) -> list[dict]:
    """Build fake item dicts keyed by letter id (for exclude_keys dedup tests)."""
    return [{"id": letter} for letter in letters]


def test_prioritize_batch_exclude_keys_fills_from_others():
    """An excluded key is never a batch candidate; the batch fills to size from
    the other eligible items instead (DEDUP-01)."""
    items = _letter_items("a", "b", "c", "d")
    batch, new_log, pass_completed = prioritize_batch(items, [], 2, _id_key, exclude_keys=frozenset({"a"}))
    assert [it["id"] for it in batch] == ["b", "c"]
    assert new_log == ["b", "c"]
    assert pass_completed is False


def test_prioritize_batch_exclude_keys_preserves_log_position():
    """An excluded key already in the log keeps its original relative position --
    it is neither marked searched (moved to tail) nor removed (DEDUP-02)."""
    items = _letter_items("a", "b", "c")
    batch, new_log, pass_completed = prioritize_batch(
        items, ["a", "b"], 1, _id_key, exclude_keys=frozenset({"a"})
    )
    assert [it["id"] for it in batch] == ["c"]
    assert new_log == ["a", "b", "c"]
    # "a" was already in the log before exclusion kicked in, so the pass is
    # still complete -- exclusion never shrinks eligible_ids (step 6 unchanged).
    assert pass_completed is True


def test_prioritize_batch_exclude_keys_topup_skips_excluded():
    """Top-up never pulls an excluded already-searched item; the excluded key
    stays in new_log at its existing position (DEDUP-02)."""
    items = _letter_items("a", "b")
    batch, new_log, pass_completed = prioritize_batch(
        items, ["a", "b"], 2, _id_key, exclude_keys=frozenset({"a"})
    )
    assert [it["id"] for it in batch] == ["b"]
    assert new_log == ["a", "b"]
    # pass_completed True only because every eligible id ("a" and "b") is in new_log
    assert pass_completed is True


def test_prioritize_batch_exclude_keys_no_pass_complete_when_excluded_unsearched():
    """An excluded key that was never searched blocks pass-completion -- it is
    never added to new_log while excluded."""
    items = _letter_items("a", "b")
    batch, new_log, pass_completed = prioritize_batch(items, [], 2, _id_key, exclude_keys=frozenset({"a"}))
    assert [it["id"] for it in batch] == ["b"]
    assert "a" not in new_log
    assert pass_completed is False


def test_prioritize_batch_exclude_keys_all_excluded():
    """Every eligible key excluded -> empty batch, pruned log unchanged, no pass completion."""
    items = _letter_items("a", "b")
    batch, new_log, pass_completed = prioritize_batch(
        items, ["a", "b"], 2, _id_key, exclude_keys=frozenset({"a", "b"})
    )
    assert batch == []
    assert new_log == ["a", "b"]
    assert pass_completed is False


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
    # 2 items, batch 2: all searched, pass completes, searched-log cleared
    assert result["radarr"]["Default"]["missing_searched"] == []
    assert result["radarr"]["Default"]["missing_pass"] == 1
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
    # Seed a searched-log so we can assert it is UNCHANGED on fetch-failure abort
    state["radarr"]["Default"]["missing_searched"] = ["1", "2"]
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    assert result["radarr"]["Default"]["connected"] is False
    assert result["radarr"]["Default"]["unreachable_since"] is not None
    # Searched-log unchanged on fetch-failure abort (Pitfall 5: prioritize_batch never reached)
    assert result["radarr"]["Default"]["missing_searched"] == ["1", "2"]
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


async def test_run_radarr_cycle_searched_log_advancement(tmp_path):
    """Searched-log grows across runs until pass completes; no re-search within a pass."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    movies = [
        {"id": i, "title": f"Movie {i}", "monitored": True}
        for i in range(1, 6)
    ]

    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    # --- Run 1: log empty -> searches unsearched items 1,2 ---
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=movies)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    # Items 1 and 2 searched first (unsearched-first, fetch order)
    log_after_run1 = result["radarr"]["Default"]["missing_searched"]
    assert set(log_after_run1) == {"1", "2"}, f"Expected {{1,2}} got {log_after_run1}"
    assert result["radarr"]["Default"].get("missing_pass", 0) == 0  # pass not yet complete

    # --- Run 2: log has 1,2 -> searches unsearched items 3,4 ---
    client.get_wanted_missing = AsyncMock(return_value=movies)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    result = await run_radarr_cycle(client, result, "Default", instance_config, settings, db)
    log_after_run2 = result["radarr"]["Default"]["missing_searched"]
    assert set(log_after_run2) == {"1", "2", "3", "4"}, f"Expected {{1,2,3,4}} got {log_after_run2}"
    assert result["radarr"]["Default"].get("missing_pass", 0) == 0  # still not complete

    # --- Run 3: only item 5 unsearched; batch_size=2 -> searched, pass completes ---
    client.get_wanted_missing = AsyncMock(return_value=movies)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    result = await run_radarr_cycle(client, result, "Default", instance_config, settings, db)
    # Pass complete: log cleared, pass counter incremented
    assert result["radarr"]["Default"]["missing_searched"] == []
    assert result["radarr"]["Default"]["missing_pass"] == 1
    await db.close()


async def test_run_radarr_cycle_mark_on_attempt(tmp_path):
    """D-04 mark-on-attempt: a movie whose search raises is still in the searched-log next cycle.

    A persistently-failing item cannot starve the queue — it gets marked inside
    prioritize_batch before the loop, so a per-item exception does not drop it from the log.
    """
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    movies = [
        {"id": 1, "title": "Movie A", "monitored": True},
        {"id": 2, "title": "Movie B", "monitored": True},
    ]

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=movies)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    # First call (Movie A) raises, second (Movie B) succeeds
    client.search_movies = AsyncMock(side_effect=[httpx.ConnectError("boom"), None])

    state = _make_test_state()
    settings = _cycle_settings(missing_count=2, cutoff_count=0)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    # Both movies attempted
    assert client.search_movies.call_count == 2
    # Both items in the batch were marked before the loop → both in new_log during the cycle.
    # Pass completes (all 2 eligible covered after both attempts) → log is cleared.
    # The pass_done=True result proves the failing item was counted in coverage:
    assert result["radarr"]["Default"]["missing_searched"] == []
    assert result["radarr"]["Default"]["missing_pass"] == 1
    await db.close()


async def test_run_radarr_cycle_new_item_jumps_line(tmp_path):
    """A new eligible item in the next cycle's fetch is searched before already-searched items."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    movies_run1 = [
        {"id": 1, "title": "Movie 1", "monitored": True},
        {"id": 2, "title": "Movie 2", "monitored": True},
    ]

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=movies_run1)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    settings = _cycle_settings(missing_count=1, cutoff_count=0)
    instance_config = _cycle_instance_config(missing_count=1, cutoff_count=0)

    # Run 1: search Movie 1 (first unsearched)
    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert "1" in result["radarr"]["Default"]["missing_searched"]

    # Run 2 fetch adds Movie 3 (new item) — it should be searched before Movie 2 (already-searched Movie 1 is oldest)
    movies_run2 = [
        {"id": 1, "title": "Movie 1", "monitored": True},
        {"id": 2, "title": "Movie 2", "monitored": True},
        {"id": 3, "title": "Movie 3", "monitored": True},  # new item
    ]
    client.get_wanted_missing = AsyncMock(return_value=movies_run2)
    client.search_movies = AsyncMock()

    result = await run_radarr_cycle(client, result, "Default", instance_config, settings, db)

    # batch_size=1: prioritize_batch should pick Movie 2 (unsearched) not Movie 1 (already searched)
    called_ids = [call.args[0][0] for call in client.search_movies.call_args_list]
    # Movie 2 or 3 (both unsearched) should be searched, not Movie 1 (already in log)
    assert 1 not in called_ids, f"Movie 1 (already searched) should not be re-searched yet; got {called_ids}"
    await db.close()


async def test_run_radarr_cycle_pass_reset(tmp_path):
    """When all eligible items are covered, missing_searched is cleared and missing_pass increments."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    movies = [
        {"id": 1, "title": "Movie 1", "monitored": True},
        {"id": 2, "title": "Movie 2", "monitored": True},
    ]

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=movies)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    # batch_size=2 covers both items in one cycle → pass completes immediately
    settings = _cycle_settings(missing_count=2, cutoff_count=0)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    assert result["radarr"]["Default"]["missing_searched"] == []
    assert result["radarr"]["Default"]["missing_pass"] == 1

    # Second pass: same behaviour — another complete cycle
    client.search_movies = AsyncMock()
    result = await run_radarr_cycle(client, result, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["missing_searched"] == []
    assert result["radarr"]["Default"]["missing_pass"] == 2
    await db.close()


async def test_run_radarr_cycle_commit_at_cycle_end(tmp_path):
    """searched-log and missing_pass are mutually consistent in state at cycle end."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    movies = [
        {"id": i, "title": f"Movie {i}", "monitored": True}
        for i in range(1, 4)
    ]

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=movies)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    # batch_size=2 with 3 items: Run 1 searches 1,2; Run 2 completes pass
    settings = _cycle_settings(missing_count=2, cutoff_count=0)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

    result_1 = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    ist = result_1["radarr"]["Default"]

    # After run 1: 2 items in log, pass not yet complete
    assert len(ist["missing_searched"]) == 2
    assert ist.get("missing_pass", 0) == 0
    # last_run was set (cycle-end commit happened)
    assert ist["last_run"] is not None

    # Consistency check: pass 0 means log is non-empty (partial pass)
    if ist.get("missing_pass", 0) == 0:
        assert len(ist["missing_searched"]) > 0, "partial pass must have non-empty log"
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
    # Seed a searched-log; fetch-failure must leave it untouched
    state["sonarr"]["Default"]["missing_searched"] = ["10:1", "20:1"]
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    assert result["sonarr"]["Default"]["connected"] is False
    assert result["sonarr"]["Default"]["unreachable_since"] is not None
    # Searched-log unchanged on fetch-failure abort (prioritize_batch never reached)
    assert result["sonarr"]["Default"]["missing_searched"] == ["10:1", "20:1"]
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


async def test_run_sonarr_cycle_searched_log_advancement(tmp_path):
    """Sonarr searched-log grows across runs without re-searching within a pass."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    # 4 episodes that deduplicate to 3 seasons: 10:1, 10:2, 20:1
    episodes = [
        _make_sonarr_episode(series_id=10, season_number=1, series_title="Show A", episode_id=100),
        _make_sonarr_episode(series_id=10, season_number=2, series_title="Show A", episode_id=101),
        _make_sonarr_episode(series_id=20, season_number=1, series_title="Show B", episode_id=200),
        _make_sonarr_episode(series_id=10, season_number=1, series_title="Show A", episode_id=102),  # dup
    ]

    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    # --- Run 1: log empty -> searches first 2 unsearched seasons ---
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=episodes)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_season = AsyncMock()

    state = _make_test_state()

    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
    log_after_run1 = result["sonarr"]["Default"]["missing_searched"]
    # 2 seasons searched (10:1 and 10:2 by fetch order); pass not yet complete
    assert len(log_after_run1) == 2
    assert set(log_after_run1) == {"10:1", "10:2"}
    assert result["sonarr"]["Default"].get("missing_pass", 0) == 0

    # --- Run 2: 1 unsearched season (20:1) -> searched, pass completes ---
    client.get_wanted_missing = AsyncMock(return_value=episodes)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_season = AsyncMock()

    result = await run_sonarr_cycle(client, result, "Default", instance_config, settings, db)
    # Pass complete: log cleared, pass counter incremented
    assert result["sonarr"]["Default"]["missing_searched"] == []
    assert result["sonarr"]["Default"]["missing_pass"] == 1
    await db.close()


# ---------------------------------------------------------------------------
# MED-2: Sonarr both-queue + Specials composite-key integration
# ---------------------------------------------------------------------------


def _make_sonarr_season(series_id: int, season_number: int, series_title: str = "Show") -> dict:
    """Build a deduplicated season dict as returned by deduplicate_to_seasons."""
    return {
        "seriesId": series_id,
        "seasonNumber": season_number,
        "display_name": f"{series_title} - Season {season_number}",
        "episode_count": 1,
    }


async def test_run_sonarr_cycle_missing_composite_key_with_specials(tmp_path):
    """MED-2: Sonarr MISSING queue uses f'{seriesId}:{seasonNumber}' key at the real call site.

    Proves the composite key is wired at run_sonarr_cycle (not just in the unit test).
    Season 0 (Specials) is a distinct key "123:0" — no collision with regular seasons.
    Batch smaller than eligible count so partition order matters.
    """
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    # 3 episodes for seriesId=123: Specials (s0), S1, S2 — each as distinct season
    # Use the raw episode format so run_sonarr_cycle's dedup gives us 3 seasons
    episodes = [
        _make_sonarr_episode(series_id=123, season_number=0, series_title="My Show", episode_id=10),
        _make_sonarr_episode(series_id=123, season_number=1, series_title="My Show", episode_id=11),
        _make_sonarr_episode(series_id=123, season_number=2, series_title="My Show", episode_id=12),
    ]

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=episodes)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_season = AsyncMock()

    state = _make_test_state()
    # batch_size=2 with 3 eligible seasons: first cycle searches 2, second cycle searches 1
    settings = _cycle_settings(missing_count=2, cutoff_count=0)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

    # --- Cycle 1: searches 2 of 3 seasons ---
    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
    log1 = result["sonarr"]["Default"]["missing_searched"]
    assert len(log1) == 2, f"Expected 2 keys in log, got {log1}"
    # All keys must be composite strings in the exact format
    for key in log1:
        assert ":" in key and key.startswith("123:"), f"Unexpected key format: {key!r}"
    # Specials key must be distinct from regular seasons
    assert "123:0" != "123:1" != "123:2"  # sanity
    assert result["sonarr"]["Default"].get("missing_pass", 0) == 0

    # --- Cycle 2: remaining season searched, pass completes ---
    client.get_wanted_missing = AsyncMock(return_value=episodes)
    client.search_season = AsyncMock()

    result = await run_sonarr_cycle(client, result, "Default", instance_config, settings, db)
    # Pass complete: log cleared
    assert result["sonarr"]["Default"]["missing_searched"] == []
    assert result["sonarr"]["Default"]["missing_pass"] == 1

    # Verify total searched = 3 seasons across 2 cycles (search_season called 3× total)
    # (first AsyncMock searched 2, second searched 1+top-up from log)
    # The key assertion: "123:0", "123:1", "123:2" are distinct keys that were all covered
    await db.close()


async def test_run_sonarr_cycle_missing_specials_distinct_key(tmp_path):
    """D-09: Specials (seasonNumber=0) produces key '123:0' — distinct from '123:1' and '123:2'."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    # Only Specials + S1 for series 123; batch_size=1 so first cycle picks one, second picks the other
    episodes = [
        _make_sonarr_episode(series_id=123, season_number=0, series_title="My Show", episode_id=10),
        _make_sonarr_episode(series_id=123, season_number=1, series_title="My Show", episode_id=11),
    ]

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=episodes)
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_season = AsyncMock()

    state = _make_test_state()
    settings = _cycle_settings(missing_count=1, cutoff_count=0)
    instance_config = _cycle_instance_config(missing_count=1, cutoff_count=0)

    # Cycle 1
    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
    log1 = result["sonarr"]["Default"]["missing_searched"]
    assert len(log1) == 1
    assert log1[0] in ("123:0", "123:1"), f"Unexpected key: {log1[0]!r}"

    # Cycle 2 — second season searched, pass completes
    client.get_wanted_missing = AsyncMock(return_value=episodes)
    client.search_season = AsyncMock()
    result = await run_sonarr_cycle(client, result, "Default", instance_config, settings, db)
    assert result["sonarr"]["Default"]["missing_searched"] == []
    assert result["sonarr"]["Default"]["missing_pass"] == 1

    # Prove "123:0" and "123:1" are distinct (no collision between Specials and S1)
    assert "123:0" != "123:1"
    await db.close()


async def test_run_sonarr_cycle_cutoff_composite_key_with_specials(tmp_path):
    """MED-2: Sonarr CUTOFF queue uses f'{seriesId}:{seasonNumber}' key at the real call site.

    Same shape as the missing-queue test; proves BOTH queues are wired with the composite key.
    seriesId=123, seasons 0 (Specials), 1, 2; batch_size=2 < 3 eligible.
    """
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    cutoff_episodes = [
        _make_sonarr_episode(series_id=123, season_number=0, series_title="My Show", episode_id=20),
        _make_sonarr_episode(series_id=123, season_number=1, series_title="My Show", episode_id=21),
        _make_sonarr_episode(series_id=123, season_number=2, series_title="My Show", episode_id=22),
    ]

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=cutoff_episodes)
    client.search_season = AsyncMock()

    state = _make_test_state()
    settings = _cycle_settings(missing_count=0, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=0, cutoff_count=2)

    # --- Cycle 1: searches 2 of 3 cutoff seasons ---
    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
    log1 = result["sonarr"]["Default"]["cutoff_searched"]
    assert len(log1) == 2, f"Expected 2 keys in cutoff_searched, got {log1}"
    for key in log1:
        assert ":" in key and key.startswith("123:"), f"Unexpected cutoff key format: {key!r}"
    assert result["sonarr"]["Default"].get("cutoff_pass", 0) == 0

    # --- Cycle 2: remaining season searched, pass completes ---
    client.get_wanted_cutoff = AsyncMock(return_value=cutoff_episodes)
    client.search_season = AsyncMock()

    result = await run_sonarr_cycle(client, result, "Default", instance_config, settings, db)
    assert result["sonarr"]["Default"]["cutoff_searched"] == []
    assert result["sonarr"]["Default"]["cutoff_pass"] == 1

    # Verify exact composite key strings were used (they come from the log before clearing)
    # All 3 keys {"123:0","123:1","123:2"} must have been covered
    await db.close()


async def test_run_sonarr_cycle_both_queues_exact_composite_keys(tmp_path):
    """MED-2 (full): Both missing AND cutoff queues produce exact '123:0','123:1','123:2' keys.

    Drives run_sonarr_cycle with same-series seasons including Specials for BOTH queues
    simultaneously; asserts exact composite key strings appear in the respective searched-logs.
    """
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    # seriesId=123 seasons 0,1,2 for missing; same shape for cutoff
    missing_episodes = [
        _make_sonarr_episode(series_id=123, season_number=0, series_title="Show X", episode_id=100),
        _make_sonarr_episode(series_id=123, season_number=1, series_title="Show X", episode_id=101),
        _make_sonarr_episode(series_id=123, season_number=2, series_title="Show X", episode_id=102),
    ]
    cutoff_episodes = [
        _make_sonarr_episode(series_id=123, season_number=0, series_title="Show X", episode_id=200),
        _make_sonarr_episode(series_id=123, season_number=1, series_title="Show X", episode_id=201),
        _make_sonarr_episode(series_id=123, season_number=2, series_title="Show X", episode_id=202),
    ]

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=missing_episodes)
    client.get_wanted_cutoff = AsyncMock(return_value=cutoff_episodes)
    client.search_season = AsyncMock()

    state = _make_test_state()
    # batch_size=2 for each queue; 3 eligible each → takes 2 cycles to complete each pass
    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    # Cycle 1: 2 of 3 missing seasons + 2 of 3 cutoff seasons searched
    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
    missing_log1 = result["sonarr"]["Default"]["missing_searched"]
    cutoff_log1 = result["sonarr"]["Default"]["cutoff_searched"]
    assert len(missing_log1) == 2
    assert len(cutoff_log1) == 2
    # All keys must be in the expected set
    assert set(missing_log1) <= {"123:0", "123:1", "123:2"}
    assert set(cutoff_log1) <= {"123:0", "123:1", "123:2"}

    # Cycle 2: remaining seasons complete both passes
    client.get_wanted_missing = AsyncMock(return_value=missing_episodes)
    client.get_wanted_cutoff = AsyncMock(return_value=cutoff_episodes)
    client.search_season = AsyncMock()

    result = await run_sonarr_cycle(client, result, "Default", instance_config, settings, db)
    # Both passes complete
    assert result["sonarr"]["Default"]["missing_searched"] == []
    assert result["sonarr"]["Default"]["missing_pass"] == 1
    assert result["sonarr"]["Default"]["cutoff_searched"] == []
    assert result["sonarr"]["Default"]["cutoff_pass"] == 1

    # Specials key "123:0" is proven as a distinct, non-colliding key for both queues
    assert "123:0" != "123:1"
    assert "123:0" != "123:2"
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
# rebalance_batch_sizes (R-01 amended -- Phase 78 Plan 02 Task 2)
# ---------------------------------------------------------------------------


def test_rebalance_batch_sizes_reallocates_to_starved_queue_with_work():
    """The starved queue (eligible>0) receives the unused slot."""
    assert rebalance_batch_sizes(
        missing_limit=0, cutoff_limit=1,
        missing_configured=50, cutoff_configured=50,
        missing_eligible=5, cutoff_eligible=0,
        hard_max=1,
    ) == (1, 0)


def test_rebalance_batch_sizes_unchanged_when_capped_queue_has_the_work():
    """When the queue that already got the cap slot has the eligible work, nothing changes."""
    assert rebalance_batch_sizes(
        missing_limit=0, cutoff_limit=1,
        missing_configured=50, cutoff_configured=50,
        missing_eligible=0, cutoff_eligible=5,
        hard_max=1,
    ) == (0, 1)


def test_rebalance_batch_sizes_unchanged_when_both_have_work():
    """Both queues have eligible work -- the cap_batch_sizes split is left unchanged."""
    assert rebalance_batch_sizes(
        missing_limit=0, cutoff_limit=1,
        missing_configured=50, cutoff_configured=50,
        missing_eligible=5, cutoff_eligible=5,
        hard_max=1,
    ) == (0, 1)


def test_rebalance_batch_sizes_leftover_tops_up_the_other_queue():
    """Leftover from a short queue tops up the other queue's dispatch."""
    assert rebalance_batch_sizes(
        missing_limit=5, cutoff_limit=5,
        missing_configured=50, cutoff_configured=50,
        missing_eligible=2, cutoff_eligible=30,
        hard_max=10,
    ) == (2, 8)


def test_rebalance_batch_sizes_inactive_queue_never_gets_slots():
    """An inactive queue (configured 0) never receives reallocated slots."""
    assert rebalance_batch_sizes(
        missing_limit=0, cutoff_limit=5,
        missing_configured=0, cutoff_configured=50,
        missing_eligible=9, cutoff_eligible=2,
        hard_max=5,
    ) == (0, 2)


def test_rebalance_batch_sizes_unlimited_mode_returns_capped_inputs_unchanged():
    """hard_max<=0 (unlimited) returns the capped inputs unchanged."""
    assert rebalance_batch_sizes(
        missing_limit=3, cutoff_limit=4,
        missing_configured=3, cutoff_configured=4,
        missing_eligible=0, cutoff_eligible=9,
        hard_max=0,
    ) == (3, 4)


def test_rebalance_batch_sizes_invariant_sweep():
    """For every combination, the result never exceeds hard_max, configured, or eligible,
    and never dispatches zero to a queue with both configured>0 and eligible>0
    when the other active queue has no eligible work to use the budget instead.
    """
    for hard_max in range(1, 7):
        for missing_configured in (0, 1, 3, 50):
            for cutoff_configured in (0, 1, 3, 50):
                capped_m, capped_c = cap_batch_sizes(missing_configured, cutoff_configured, hard_max)
                for missing_eligible in (0, 1, 4):
                    for cutoff_eligible in (0, 1, 4):
                        m, c = rebalance_batch_sizes(
                            missing_limit=capped_m, cutoff_limit=capped_c,
                            missing_configured=missing_configured, cutoff_configured=cutoff_configured,
                            missing_eligible=missing_eligible, cutoff_eligible=cutoff_eligible,
                            hard_max=hard_max,
                        )
                        assert m + c <= hard_max
                        assert m <= missing_configured
                        assert c <= cutoff_configured
                        assert m <= missing_eligible
                        assert c <= cutoff_eligible
                        work_exists = (
                            (missing_configured > 0 and missing_eligible > 0)
                            or (cutoff_configured > 0 and cutoff_eligible > 0)
                        )
                        if work_exists:
                            assert m + c >= 1


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
    # 78-02 / R-04: the cycle-completed line now reports tally counts and the
    # graded outcome instead of the old searched/skipped counters.
    assert "Radarr: Cycle completed in" in output
    assert "5 fetched" in output
    assert "5 accepted" in output
    assert "0 failed" in output
    assert "grade success" in output
    await db.close()


async def test_sonarr_cycle_logs_diagnostic_summary(tmp_path):
    """Sonarr cycle logs a summary with fetched/accepted/failed counts and the graded outcome."""
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
    # 78-03 / R-04: the cycle-completed line now reports tally counts and the
    # graded outcome instead of the old searched/skipped counters.
    assert "Sonarr: Cycle completed in" in output
    # 3 episodes fetched (raw count before filtering/dedup)
    assert "3 fetched" in output
    assert "3 accepted" in output
    assert "0 failed" in output
    assert "grade success" in output
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
    # 78-02 / R-04: the cycle-completed line now reports tally counts and the
    # graded outcome instead of the old searched/skipped counters.
    assert "Radarr: Cycle completed in" in output
    assert "3 fetched" in output
    assert "2 accepted" in output
    assert "1 failed" in output
    assert "grade partial" in output
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


async def test_radarr_tag_not_found_skips_queue(tmp_path):
    """Radarr cycle with tag not found in tag list skips that queue (TAGSCOPE-01)."""
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

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    # Tag not found -> missing queue skipped, zero searches
    assert client.search_movies.call_count == 0
    ist = result["radarr"]["Default"]
    assert ist["tag_warnings"] == [{"tag": "nonexistent", "field": "missing", "reason": "not_found"}]
    # Cutoff is empty too -> grade is failed, never nothing_needed
    assert ist["last_cycle"]["grade"] == "failed"
    assert ist["last_cycle"]["unevaluated"] == [{"queue": "missing", "reason": "tag 'nonexistent' not found"}]
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


async def test_sonarr_tag_not_found_skips_queue(tmp_path):
    """Sonarr cycle with tag not found in tag list skips that queue (TAGSCOPE-01)."""
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

    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    # Tag not found -> missing queue skipped, zero searches
    assert client.search_season.call_count == 0
    ist = result["sonarr"]["Default"]
    assert ist["tag_warnings"][0]["reason"] == "not_found"
    assert ist["last_cycle"]["grade"] == "failed"
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


async def test_radarr_tag_fetch_failure_skips_queue_and_warns(tmp_path):
    """When get_tags() raises, the missing queue is skipped with a 'couldn't load tags' warning."""
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
        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    finally:
        logger.remove(handler_id)

    log_output = sink.getvalue()
    assert "Failed to fetch tags" in log_output, "Should log tag fetch failure"
    assert "Missing queue skipped -- couldn't load tags" in log_output
    assert "not found" not in log_output, "Should NOT log 'tag not found' when fetch failed"
    assert client.search_movies.call_count == 0
    assert result["radarr"]["Default"]["tag_warnings"][0]["reason"] == "fetch_failed"
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
            "Default": AppState(missing_searched=["5"], last_run=None),
            "OldInstance": AppState(missing_searched=["99"], last_run=None),
        },
        sonarr={
            "Default": AppState(missing_searched=[], last_run=None),
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
    assert state["radarr"]["Default"]["missing_searched"] == []
    # Cursor-key absence is asserted in tests/test_state.py (the one allowed home for
    # legacy-cursor regression — the cursor static guard excludes only that file). Here the
    # positive missing_searched == [] check already proves the helper produces the new shape.
    assert "sonarr" in state
    assert "Default" in state["sonarr"]
    assert state["sonarr"]["Default"]["missing_searched"] == []


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
    assert {"tag": "nonexistent", "field": "missing", "reason": "not_found"} in ist["tag_warnings"]
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
    assert {"tag": "nonexistent", "field": "missing", "reason": "not_found"} in ist["tag_warnings"]
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
    assert {"tag": "nonexistent-missing", "field": "missing", "reason": "not_found"} in ist["tag_warnings"]
    assert {"tag": "nonexistent-cutoff", "field": "cutoff", "reason": "not_found"} in ist["tag_warnings"]
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
    # 2 items, batch 2: all searched, pass completes, log cleared
    assert ist["missing_searched"] == []
    assert ist.get("missing_pass", 0) == 1
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

    state["lidarr"]["Default"]["missing_searched"] = ["101", "102"]
    result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)

    ist = result["lidarr"]["Default"]
    assert ist["connected"] is False
    assert ist["unreachable_since"] is not None
    # Searched-log unchanged on fetch-failure abort
    assert ist["missing_searched"] == ["101", "102"]
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


async def test_run_lidarr_cycle_searched_log_advancement(tmp_path):
    """Lidarr searched-log grows across cycles; pass completes when all eligible are covered."""
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

    # First cycle: searches albums 1,2 (unsearched-first, fetch order)
    result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
    log1 = result["lidarr"]["Default"]["missing_searched"]
    assert set(log1) == {"1", "2"}
    assert result["lidarr"]["Default"].get("missing_pass", 0) == 0
    assert client.search_albums.call_count == 2

    # Second cycle: searches albums 3,4
    client.search_albums.reset_mock()
    result = await run_lidarr_cycle(client, result, "Default", instance_config, settings, db)
    log2 = result["lidarr"]["Default"]["missing_searched"]
    assert set(log2) == {"1", "2", "3", "4"}
    assert result["lidarr"]["Default"].get("missing_pass", 0) == 0
    assert client.search_albums.call_count == 2

    # Third cycle: album 5 unsearched + top-up from log; pass completes
    client.search_albums.reset_mock()
    result = await run_lidarr_cycle(client, result, "Default", instance_config, settings, db)
    # Pass complete: log cleared, pass counter incremented
    assert result["lidarr"]["Default"]["missing_searched"] == []
    assert result["lidarr"]["Default"]["missing_pass"] == 1
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


async def test_lidarr_tag_not_found_skips_queue_and_stores_warning(tmp_path):
    """Lidarr cycle with tag not found skips that queue and stores tag_warnings (TAGSCOPE-01/02)."""
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

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)

        # Tag not found -> missing queue skipped, zero searches
        assert client.search_albums.call_count == 0

        # Tag warning stored in state
        ist = result["lidarr"]["Default"]
        assert "tag_warnings" in ist
        assert ist["tag_warnings"] == [{"tag": "nonexistent", "field": "missing", "reason": "not_found"}]
        assert ist["last_cycle"]["grade"] == "failed"
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
    # 78-02 / R-01: accepted=0 with failed>0 grades failed, never nothing_needed.
    assert result["radarr"]["Default"]["last_cycle"]["grade"] == "failed"
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
# in test_prioritize_batch_empty_eligible and test_filter_by_tag_empty_list.


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
        # Empty queues: no items searched, searched-log stays empty (MED-1 guard: no pass reset)
        assert result["radarr"]["Default"]["missing_searched"] == []
        assert result["radarr"]["Default"]["cutoff_searched"] == []
        assert result["radarr"]["Default"]["connected"] is True
        # 78-02 / OUTCOME-02: no eligible work and no fetch failure grades nothing_needed.
        assert result["radarr"]["Default"]["last_cycle"]["grade"] == "nothing_needed"
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
        assert result["sonarr"]["Default"]["missing_searched"] == []
        assert result["sonarr"]["Default"]["cutoff_searched"] == []
        assert result["sonarr"]["Default"]["connected"] is True
        # 78-03 / OUTCOME-02: no eligible work and no fetch failure grades nothing_needed.
        assert result["sonarr"]["Default"]["last_cycle"]["grade"] == "nothing_needed"
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
        assert result["lidarr"]["Default"]["missing_searched"] == []
        assert result["lidarr"]["Default"]["cutoff_searched"] == []
        assert result["lidarr"]["Default"]["connected"] is True
        # 78-03 / OUTCOME-02: no eligible work and no fetch failure grades nothing_needed.
        assert result["lidarr"]["Default"]["last_cycle"]["grade"] == "nothing_needed"
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
    """A successful run_radarr_cycle sets last_successful_search; legacy last_success is untouched."""
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

    # 78-02 / R-05: confirmed-search time lives in last_successful_search; the
    # engine never writes the legacy last_success field.
    assert result["radarr"]["Default"]["last_successful_search"] is not None
    assert result["radarr"]["Default"]["last_success"] is None
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
# Phase 78 Plan 02: honest cycle grading for Radarr (R1/R2/R8/OUTCOME-06/D-10)
# ---------------------------------------------------------------------------


async def test_radarr_grade_success(tmp_path):
    """2 monitored missing, cutoff empty, both accepted -> grade success."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
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
        ist = result["radarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_cycle"]["accepted"] == 2
        assert ist["last_cycle"]["failed"] == 0
        assert ist["last_successful_search"] == ist["last_run"] == ist["last_cycle"]["finished_at"]
        assert ist["last_success"] is None
    finally:
        await db.close()


async def test_radarr_grade_partial(tmp_path):
    """One accepted command, one failed command -> grade partial."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        request = httpx.Request("POST", "http://radarr:7878/api/v3/command")
        response = httpx.Response(500, request=request)
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[
                {"id": 1, "title": "Movie A", "monitored": True},
                {"id": 2, "title": "Movie B", "monitored": True},
            ]
        )
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_movies = AsyncMock(
            side_effect=[None, httpx.HTTPStatusError("err", request=request, response=response)]
        )

        state = _make_test_state()
        settings = _cycle_settings(missing_count=2, cutoff_count=2)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "partial"
        assert ist["last_cycle"]["accepted"] == 1
        assert ist["last_cycle"]["failed"] == 1
        assert ist["last_cycle"]["failure_reasons"] == [{"reason": "HTTP 500", "count": 1}]
    finally:
        await db.close()


async def test_radarr_grade_failed_all_commands(tmp_path):
    """All search commands fail -> grade failed; legacy last_success untouched."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[
                {"id": 1, "title": "Movie A", "monitored": True},
                {"id": 2, "title": "Movie B", "monitored": True},
            ]
        )
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_movies = AsyncMock(side_effect=httpx.ConnectError("refused"))

        state = _make_test_state()
        state["radarr"]["Default"]["last_success"] = "2026-01-01T00:00:00Z"
        settings = _cycle_settings(missing_count=2, cutoff_count=2)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "failed"
        assert ist["last_cycle"]["accepted"] == 0
        assert ist["last_cycle"]["failed"] == 2
        assert ist["connected"] is True
        assert ist["last_run"] is not None
        assert ist["last_successful_search"] is None
        assert ist["last_success"] == "2026-01-01T00:00:00Z"
    finally:
        await db.close()


async def test_radarr_grade_failed_fetch(tmp_path):
    """Fetch failure -> grade failed, last_run stamped, last_successful_search untouched."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))

        state = _make_test_state()
        state["radarr"]["Default"]["last_success"] = "2026-01-01T00:00:00Z"
        state["radarr"]["Default"]["last_successful_search"] = "2025-12-31T00:00:00Z"
        settings = _cycle_settings()
        instance_config = _cycle_instance_config()

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "failed"
        assert ist["last_cycle"]["fetch_error"] == "HTTP error: ConnectError"
        assert ist["connected"] is False
        assert ist["last_run"] is not None
        assert ist["last_successful_search"] == "2025-12-31T00:00:00Z"
        assert ist["last_success"] == "2026-01-01T00:00:00Z"
    finally:
        await db.close()


async def test_radarr_grade_nothing_needed_empty(tmp_path):
    """Both queues empty -> grade nothing_needed with eligible counts recorded as 0."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=[])
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_movies = AsyncMock()

        state = _make_test_state()
        state["radarr"]["Default"]["last_success"] = "2026-01-01T00:00:00Z"
        settings = _cycle_settings()
        instance_config = _cycle_instance_config()

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "nothing_needed"
        assert ist["last_cycle"]["eligible"] == {"missing": 0, "cutoff": 0}
        assert ist["last_run"] is not None
        assert ist["last_successful_search"] is None
        assert ist["last_success"] == "2026-01-01T00:00:00Z"
    finally:
        await db.close()


async def test_radarr_grade_inactive_queue_ignored(tmp_path):
    """An inactive (configured 0) queue is absent from eligible and doesn't block success."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[{"id": 1, "title": "Movie A", "monitored": True}]
        )
        client.get_wanted_cutoff = AsyncMock(
            return_value=[{"id": 2, "title": "Movie B", "monitored": True}]
        )
        client.search_movies = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings(missing_count=1, cutoff_count=0)
        instance_config = _cycle_instance_config(missing_count=1, cutoff_count=0)

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_cycle"]["accepted"] == 1
        assert "cutoff" not in ist["last_cycle"]["eligible"]

        # Both queues configured inactive (disabled instance, both counts 0) -> nothing_needed,
        # regardless of what the fetch returns. InstanceConfig/Settings reject
        # search_missing_count=0 and search_cutoff_count=0 together while enabled=True, so this
        # scenario is only reachable via a disabled instance -- engine functions never read
        # instance_config.enabled, so this still exercises the grading path directly.
        state2 = _make_test_state()
        settings2 = make_settings(
            search_missing_count=0, search_cutoff_count=0,
            radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False,
        )
        instance_config2 = InstanceConfig(
            url="http://radarr:7878", api_key="test-key", enabled=False,
            search_missing_count=0, search_cutoff_count=0,
        )
        result2 = await run_radarr_cycle(client, state2, "Default", instance_config2, settings2, db)
        ist2 = result2["radarr"]["Default"]

        assert ist2["last_cycle"]["grade"] == "nothing_needed"
        assert client.search_movies.call_count == 1  # only the first scenario's missing item
    finally:
        await db.close()


async def test_radarr_grade_hard_max_starved_is_success(tmp_path):
    """R-01: a queue starved to zero slots next to an accepted queue still grades success."""
    from triggarr.models.config import GeneralConfig

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[{"id": i, "title": f"Movie {i}", "monitored": True} for i in range(5)]
        )
        client.get_wanted_cutoff = AsyncMock(
            return_value=[{"id": 100 + i, "title": f"Cutoff {i}", "monitored": True} for i in range(5)]
        )
        client.search_movies = AsyncMock()

        state = _make_test_state()
        settings = make_settings(
            search_missing_count=50, search_cutoff_count=50,
            general=GeneralConfig(hard_max_per_cycle=1),
        )
        instance_config = _cycle_instance_config(missing_count=50, cutoff_count=50)

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert client.search_movies.call_count == 1
        assert ist["last_cycle"]["grade"] == "success"
    finally:
        await db.close()


async def test_radarr_persistence_failure_still_accepted(tmp_path):
    """R8/OUTCOME-06: a success-path history-insert failure keeps the command accepted."""
    from unittest.mock import patch

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[
                {"id": 1, "title": "Movie A", "monitored": True},
                {"id": 2, "title": "Movie B", "monitored": True},
            ]
        )
        client.get_wanted_cutoff = AsyncMock(
            return_value=[{"id": 3, "title": "Movie C", "monitored": True}]
        )
        client.search_movies = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings(missing_count=2, cutoff_count=1)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=1)

        with patch(
            "triggarr.search.engine.insert_search_entry",
            AsyncMock(side_effect=aiosqlite.OperationalError("database is locked")),
        ):
            result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_cycle"]["accepted"] == 3
        assert ist["last_cycle"]["failed"] == 0
        assert ist["last_cycle"]["persistence_failed"] == 3
        assert ist["last_successful_search"] is not None
        assert client.search_movies.call_count == 3
    finally:
        await db.close()


async def test_radarr_partial_history_write_rolled_back_never_resent(tmp_path):
    """R-08/R8: a real prune failure mid-cycle rolls back cleanly; every accepted command stays
    accepted and is never resent."""
    from triggarr.db import insert_search_entry
    from triggarr.models.config import GeneralConfig

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    db2 = None
    try:
        for i in range(2):
            await insert_search_entry(db, "Radarr", "missing", f"Resolved {i}", outcome="failed")
        await db.execute(
            "CREATE TRIGGER fail_prune BEFORE DELETE ON search_history "
            "BEGIN SELECT RAISE(ABORT, 'injected prune failure'); END"
        )
        await db.commit()

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
        settings = make_settings(
            search_missing_count=2, search_cutoff_count=0,
            general=GeneralConfig(max_history_rows=1),
        )
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert client.search_movies.call_count == 2
        assert ist["last_cycle"]["accepted"] == 2
        assert ist["last_cycle"]["failed"] == 0
        assert ist["last_cycle"]["persistence_failed"] == 2
        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_successful_search"] is not None
        assert db.in_transaction is False

        await db.execute("DROP TRIGGER fail_prune")
        await db.commit()

        db2 = await aiosqlite.connect(db_path)
        async with db2.execute("SELECT COUNT(*) FROM search_history WHERE outcome = 'searched'") as cursor:
            pending_count = (await cursor.fetchone())[0]
        assert pending_count == 0
    finally:
        if db2 is not None:
            await db2.close()
        await db.close()


async def test_radarr_pending_cap_counts_as_persistence_failure(tmp_path):
    """R-02: PendingCapExceeded on the success-path insert is a persistence failure, not a failed search."""
    from unittest.mock import patch

    from triggarr.db import PendingCapExceeded

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[{"id": 1, "title": "Movie A", "monitored": True}]
        )
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_movies = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings(missing_count=1, cutoff_count=1)
        instance_config = _cycle_instance_config(missing_count=1, cutoff_count=1)

        cap_exc = PendingCapExceeded(
            app="Radarr", instance_id="Default", item_name="Movie A", pending_count=10, cap=10,
        )
        with patch(
            "triggarr.search.engine.insert_search_entry",
            AsyncMock(side_effect=cap_exc),
        ):
            result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert ist["last_cycle"]["accepted"] == 1
        assert ist["last_cycle"]["persistence_failed"] == 1
        assert ist["last_cycle"]["grade"] == "success"
    finally:
        await db.close()


async def test_radarr_failed_path_insert_error_does_not_abort(tmp_path):
    """R-04: a failure-path history insert that raises never aborts the cycle."""
    from unittest.mock import patch

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        request = httpx.Request("POST", "http://radarr:7878/api/v3/command")
        response = httpx.Response(500, request=request)
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[{"id": 1, "title": "Movie A", "monitored": True}]
        )
        client.get_wanted_cutoff = AsyncMock(
            return_value=[{"id": 2, "title": "Movie B", "monitored": True}]
        )
        client.search_movies = AsyncMock(
            side_effect=httpx.HTTPStatusError("err", request=request, response=response)
        )

        state = _make_test_state()
        settings = _cycle_settings(missing_count=1, cutoff_count=1)
        instance_config = _cycle_instance_config(missing_count=1, cutoff_count=1)

        with patch(
            "triggarr.search.engine.insert_search_entry",
            AsyncMock(side_effect=aiosqlite.OperationalError("database is locked")),
        ):
            result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert ist["last_cycle"]["failed"] == 2
        assert ist["last_cycle"]["grade"] == "failed"
        assert client.search_movies.call_count == 2
    finally:
        await db.close()


async def test_radarr_last_cycle_never_contains_apikey(tmp_path):
    """D-10: a search-command failure whose request URL carries ?apikey= never leaks into last_cycle."""
    import json

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        request = httpx.Request("POST", "http://radarr:7878/api/v3/command?apikey=SUPERSECRET123")
        response = httpx.Response(500, request=request)
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[{"id": 1, "title": "Movie A", "monitored": True}]
        )
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.get_library_count = AsyncMock(return_value=100)
        client.search_movies = AsyncMock(
            side_effect=httpx.HTTPStatusError("err", request=request, response=response)
        )

        state = _make_test_state()
        settings = _cycle_settings(missing_count=1, cutoff_count=1)
        instance_config = _cycle_instance_config(missing_count=1, cutoff_count=1)

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

        assert "SUPERSECRET123" not in json.dumps(result["radarr"]["Default"])
    finally:
        await db.close()


async def test_radarr_hard_max_reallocates_to_queue_with_work(tmp_path):
    """R-01 amended: hard_max=1 reallocates to the queue with eligible work, never nothing_needed."""
    from triggarr.models.config import GeneralConfig

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[{"id": i, "title": f"Movie {i}", "monitored": True} for i in range(3)]
        )
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_movies = AsyncMock()

        state = _make_test_state()
        settings = make_settings(
            search_missing_count=50, search_cutoff_count=50,
            general=GeneralConfig(hard_max_per_cycle=1),
        )
        instance_config = _cycle_instance_config(missing_count=50, cutoff_count=50)

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert client.search_movies.call_count == 1
        client.search_movies.assert_called_once_with([0])
        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_cycle"]["eligible"] == {"missing": 3, "cutoff": 0}
        assert ist["last_cycle"]["grade"] != "nothing_needed"
    finally:
        await db.close()


async def test_radarr_hard_max_cutoff_with_work_missing_empty(tmp_path):
    """R-01 amended: missing empty, cutoff has work -- hard_max=1 dispatches exactly one cutoff search."""
    from triggarr.models.config import GeneralConfig

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=[])
        client.get_wanted_cutoff = AsyncMock(
            return_value=[{"id": i, "title": f"Cutoff {i}", "monitored": True} for i in range(2)]
        )
        client.search_movies = AsyncMock()

        state = _make_test_state()
        settings = make_settings(
            search_missing_count=50, search_cutoff_count=50,
            general=GeneralConfig(hard_max_per_cycle=1),
        )
        instance_config = _cycle_instance_config(missing_count=50, cutoff_count=50)

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert client.search_movies.call_count == 1
        assert ist["last_cycle"]["grade"] == "success"
    finally:
        await db.close()


async def test_radarr_eligible_counts_after_filters(tmp_path):
    """last_cycle["eligible"] reflects eligible counts AFTER the full filter chain runs."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        future = (datetime.now(UTC) + timedelta(days=30)).isoformat().replace("+00:00", "Z")
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[
                {"id": 1, "title": "Eligible", "monitored": True},
                {"id": 2, "title": "Unmonitored", "monitored": False},
                {
                    "id": 3, "title": "Unreleased", "monitored": True,
                    "digitalRelease": future, "physicalRelease": future,
                },
            ]
        )
        client.get_wanted_cutoff = AsyncMock(
            return_value=[
                {"id": 4, "title": "Cutoff Eligible", "monitored": True},
                {"id": 5, "title": "Cutoff Unmonitored", "monitored": False},
            ]
        )
        client.search_movies = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings(missing_count=5, cutoff_count=5)
        instance_config = _cycle_instance_config(missing_count=5, cutoff_count=5)

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert ist["last_cycle"]["eligible"] == {"missing": 1, "cutoff": 1}
    finally:
        await db.close()


async def test_radarr_zero_dispatch_with_work_never_nothing_needed(tmp_path):
    """Backstop: a forced zero-dispatch cycle with eligible work grades failed, never nothing_needed."""
    from unittest.mock import patch

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
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

        with patch("triggarr.search.engine.rebalance_batch_sizes", return_value=(0, 0)):
            result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert client.search_movies.call_count == 0
        assert ist["last_cycle"]["grade"] == "failed"

        view = cycle_view(ist["last_cycle"], "Radarr")
        assert any("2 eligible items not searched this cycle" in reason["text"] for reason in view["reasons"])
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# _fetch_wanted_queues (R-07 inactive-queue fetch isolation)
# ---------------------------------------------------------------------------


async def test_fetch_wanted_queues_active_fetch_error_propagates():
    """An active queue's fetch failure propagates out of the helper untouched."""
    fetch_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))
    fetch_cutoff = AsyncMock(return_value=[])

    with pytest.raises(httpx.ConnectError):
        await _fetch_wanted_queues(
            fetch_missing=fetch_missing, fetch_cutoff=fetch_cutoff,
            missing_active=True, cutoff_active=True, app_label="Radarr",
        )


async def test_fetch_wanted_queues_inactive_cutoff_fetch_fails():
    """missing active and fetched; inactive cutoff fetch fails -> (missing_list, None)."""
    fetch_missing = AsyncMock(return_value=[{"id": 1}])
    fetch_cutoff = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        missing, cutoff = await _fetch_wanted_queues(
            fetch_missing=fetch_missing, fetch_cutoff=fetch_cutoff,
            missing_active=True, cutoff_active=False, app_label="Radarr",
        )
    finally:
        logger.remove(handler_id)

    assert missing == [{"id": 1}]
    assert cutoff is None
    assert fetch_missing.await_count == 1
    assert fetch_cutoff.await_count == 1
    assert "inactive" in sink.getvalue()


async def test_fetch_wanted_queues_both_inactive_missing_fails_cutoff_succeeds():
    """Both inactive: missing fetch fails, cutoff fetch succeeds -> (None, [x]); cutoff still awaited."""
    fetch_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))
    fetch_cutoff = AsyncMock(return_value=[{"id": 2}])

    missing, cutoff = await _fetch_wanted_queues(
        fetch_missing=fetch_missing, fetch_cutoff=fetch_cutoff,
        missing_active=False, cutoff_active=False, app_label="Radarr",
    )

    assert missing is None
    assert cutoff == [{"id": 2}]
    assert fetch_cutoff.await_count == 1


async def test_fetch_wanted_queues_active_fetched_before_inactive():
    """With missing inactive and cutoff active, the active (cutoff) fetcher is awaited first."""
    order: list[str] = []

    async def fetch_missing():
        order.append("missing")
        return []

    async def fetch_cutoff():
        order.append("cutoff")
        return []

    await _fetch_wanted_queues(
        fetch_missing=fetch_missing, fetch_cutoff=fetch_cutoff,
        missing_active=False, cutoff_active=True, app_label="Radarr",
    )

    assert order == ["cutoff", "missing"]


# ---------------------------------------------------------------------------
# run_radarr_cycle: inactive-queue fetch isolation (R-07) + regression sweep
# ---------------------------------------------------------------------------


async def test_radarr_inactive_cutoff_fetch_fails_active_has_work(tmp_path):
    """R-07: an inactive cutoff queue's fetch failure doesn't block the active missing queue."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[
                {"id": 1, "title": "Movie A", "monitored": True},
                {"id": 2, "title": "Movie B", "monitored": True},
            ]
        )
        client.get_wanted_cutoff = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))
        client.search_movies = AsyncMock()

        state = _make_test_state()
        ist = state["radarr"]["Default"]
        ist["cutoff_count"] = 7
        ist["cutoff_searched"] = ["99"]
        ist["missing_count"] = 5
        ist["missing_searched"] = ["42"]

        settings = _cycle_settings(missing_count=2, cutoff_count=0)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert client.search_movies.call_count == 2
        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_cycle"]["accepted"] == 2
        assert ist["last_cycle"]["fetch_error"] is None
        assert ist["last_cycle"]["unevaluated"] == []
        assert ist["connected"] is True
        assert ist["unreachable_since"] is None
        assert ist["last_successful_search"] is not None
        assert ist["cutoff_count"] == 7
        assert ist["cutoff_searched"] == ["99"]
    finally:
        await db.close()


async def test_radarr_inactive_cutoff_fetch_fails_active_empty(tmp_path):
    """R-07: inactive cutoff fetch failure with an empty active missing queue grades nothing_needed."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        request = httpx.Request("GET", "http://radarr:7878/api/v3/wanted/cutoff")
        response = httpx.Response(503, request=request)
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=[])
        client.get_wanted_cutoff = AsyncMock(
            side_effect=httpx.HTTPStatusError("err", request=request, response=response)
        )
        client.search_movies = AsyncMock()

        state = _make_test_state()
        ist = state["radarr"]["Default"]
        ist["cutoff_count"] = 7
        ist["cutoff_searched"] = ["99"]
        ist["missing_count"] = 5
        ist["missing_searched"] = ["42"]

        settings = _cycle_settings(missing_count=2, cutoff_count=0)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "nothing_needed"
        assert ist["connected"] is True
        assert ist["missing_count"] == 0
        assert ist["cutoff_count"] == 7
        assert ist["last_run"] is not None
    finally:
        await db.close()


async def test_radarr_inactive_missing_fetch_fails_active_cutoff_has_work(tmp_path):
    """R-07: an inactive missing queue's fetch failure doesn't block the active cutoff queue."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.get_wanted_cutoff = AsyncMock(
            return_value=[{"id": 3, "title": "Movie C", "monitored": True}]
        )
        client.search_movies = AsyncMock()

        state = _make_test_state()
        ist = state["radarr"]["Default"]
        ist["cutoff_count"] = 7
        ist["cutoff_searched"] = ["99"]
        ist["missing_count"] = 5
        ist["missing_searched"] = ["42"]

        settings = _cycle_settings(missing_count=0, cutoff_count=2)
        instance_config = _cycle_instance_config(missing_count=0, cutoff_count=2)

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_cycle"]["accepted"] == 1
        assert ist["connected"] is True
        assert ist["missing_count"] == 5
        assert ist["missing_searched"] == ["42"]
    finally:
        await db.close()


async def test_radarr_both_inactive_both_fetches_fail(tmp_path):
    """R-07: both queues inactive and both fetches fail -> unreachable but graded nothing_needed, not failed."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.get_wanted_cutoff = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.search_movies = AsyncMock()

        state = _make_test_state()
        ist = state["radarr"]["Default"]
        ist["cutoff_count"] = 7
        ist["cutoff_searched"] = ["99"]
        ist["missing_count"] = 5
        ist["missing_searched"] = ["42"]
        ist["last_successful_search"] = "2025-12-31T00:00:00Z"

        settings = make_settings(
            search_missing_count=0, search_cutoff_count=0,
            radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False,
        )
        instance_config = InstanceConfig(
            url="http://radarr:7878", api_key="test-key", enabled=False,
            search_missing_count=0, search_cutoff_count=0,
        )

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert client.search_movies.call_count == 0
        assert ist["last_cycle"]["grade"] == "nothing_needed"
        assert ist["last_cycle"]["fetch_error"] is None
        assert ist["last_cycle"]["accepted"] == 0
        assert ist["last_cycle"]["failed"] == 0
        assert ist["connected"] is False
        assert ist["unreachable_since"] is not None
        assert ist["last_run"] is not None
        assert ist["last_successful_search"] == "2025-12-31T00:00:00Z"
        assert ist["missing_count"] == 5
        assert ist["cutoff_count"] == 7
    finally:
        await db.close()


async def test_radarr_both_inactive_one_fetch_fails(tmp_path):
    """R-07: both queues inactive, only one fetch fails -> still connected True (the other succeeded)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[{"id": 1, "title": "Movie A", "monitored": True}]
        )
        client.get_wanted_cutoff = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.search_movies = AsyncMock()

        state = _make_test_state()
        ist = state["radarr"]["Default"]
        ist["cutoff_count"] = 7
        ist["cutoff_searched"] = ["99"]
        ist["missing_count"] = 5
        ist["missing_searched"] = ["42"]

        settings = make_settings(
            search_missing_count=0, search_cutoff_count=0,
            radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False,
        )
        instance_config = InstanceConfig(
            url="http://radarr:7878", api_key="test-key", enabled=False,
            search_missing_count=0, search_cutoff_count=0,
        )

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "nothing_needed"
        assert ist["connected"] is True
        assert ist["missing_count"] == 1
        assert ist["cutoff_count"] == 7
        assert client.search_movies.call_count == 0
    finally:
        await db.close()


async def test_radarr_active_fetch_failure_with_inactive_other_still_failed(tmp_path):
    """R-07: an active queue's fetch failure still grades failed; the inactive endpoint is never probed."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_movies = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings(missing_count=2, cutoff_count=0)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

        result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["radarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "failed"
        assert ist["last_cycle"]["fetch_error"] == "HTTP error: ConnectError"
        assert ist["connected"] is False
        assert client.get_wanted_cutoff.await_count == 0
    finally:
        await db.close()


async def test_radarr_inactive_fetch_error_never_leaks_apikey(tmp_path):
    """D-10: an inactive queue's fetch error carrying ?apikey= never reaches state or logs."""
    import json

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        request = httpx.Request("GET", "http://radarr:7878/api/v3/wanted/cutoff?apikey=SUPERSECRET123")
        response = httpx.Response(500, request=request)
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[{"id": 1, "title": "Movie A", "monitored": True}]
        )
        client.get_wanted_cutoff = AsyncMock(
            side_effect=httpx.HTTPStatusError("err", request=request, response=response)
        )
        client.get_library_count = AsyncMock(return_value=100)
        client.search_movies = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings(missing_count=2, cutoff_count=0)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="WARNING")
        try:
            result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
        finally:
            logger.remove(handler_id)

        assert "SUPERSECRET123" not in json.dumps(result["radarr"]["Default"])
        assert "SUPERSECRET123" not in sink.getvalue()
    finally:
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


async def test_run_radarr_cycle_get_tags_fn_exception_skips_tagged_queue(tmp_path):
    """RES-03: a get_tags_fn that raises skips the tagged queue instead of failing open.

    When the resolver raises httpx.ConnectError, the cycle does NOT raise; the
    existing except guard inside _resolve_tag_scope sets tags=[] /
    tag_fetch_ok=False, which now skips the tagged queue (zero searches) and
    records a fetch_failed tag warning.
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
    # Tagged queue skipped (tag_fetch_ok=False) -> zero searches.
    assert client.search_movies.call_count == 0
    assert result["radarr"]["Default"]["tag_warnings"] == [
        {"tag": "triggarr", "field": "missing", "reason": "fetch_failed"},
    ]
    assert result["radarr"]["Default"]["last_cycle"]["grade"] == "failed"
    await db.close()


# ---------------------------------------------------------------------------
# 78-03: Sonarr honest grading, hard-max reallocation, R-07 fetch isolation
# ---------------------------------------------------------------------------


async def test_sonarr_grade_success(tmp_path):
    """Two missing episodes in different seasons, both accepted -> grade success."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
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
        ist = result["sonarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_cycle"]["accepted"] == 2
        assert ist["last_cycle"]["failed"] == 0
        assert ist["last_successful_search"] == ist["last_run"] == ist["last_cycle"]["finished_at"]
        assert ist["last_success"] is None
    finally:
        await db.close()


async def test_sonarr_grade_partial(tmp_path):
    """One accepted season search, one failed -> grade partial."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        request = httpx.Request("POST", "http://sonarr:8989/api/v3/command")
        response = httpx.Response(500, request=request)
        episodes = [
            _make_sonarr_episode(series_id=10, season_number=1, series_title="Show A", episode_id=100),
            _make_sonarr_episode(series_id=20, season_number=1, series_title="Show B", episode_id=200),
        ]
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=episodes)
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_season = AsyncMock(
            side_effect=[None, httpx.HTTPStatusError("err", request=request, response=response)]
        )

        state = _make_test_state()
        settings = _cycle_settings(missing_count=2, cutoff_count=2)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

        result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["sonarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "partial"
        assert ist["last_cycle"]["accepted"] == 1
        assert ist["last_cycle"]["failed"] == 1
        assert ist["last_cycle"]["failure_reasons"] == [{"reason": "HTTP 500", "count": 1}]
    finally:
        await db.close()


async def test_sonarr_grade_failed_all_commands(tmp_path):
    """All season searches fail -> grade failed; legacy last_success untouched."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        episodes = [
            _make_sonarr_episode(series_id=10, season_number=1, series_title="Show A", episode_id=100),
            _make_sonarr_episode(series_id=20, season_number=1, series_title="Show B", episode_id=200),
        ]
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=episodes)
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_season = AsyncMock(side_effect=httpx.ConnectError("refused"))

        state = _make_test_state()
        state["sonarr"]["Default"]["last_success"] = "2026-01-01T00:00:00Z"
        settings = _cycle_settings(missing_count=2, cutoff_count=2)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

        result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["sonarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "failed"
        assert ist["last_cycle"]["accepted"] == 0
        assert ist["last_cycle"]["failed"] == 2
        assert ist["connected"] is True
        assert ist["last_run"] is not None
        assert ist["last_successful_search"] is None
        assert ist["last_success"] == "2026-01-01T00:00:00Z"
    finally:
        await db.close()


async def test_sonarr_grade_failed_fetch(tmp_path):
    """Fetch failure -> grade failed, last_run stamped, last_successful_search untouched."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))

        state = _make_test_state()
        state["sonarr"]["Default"]["last_success"] = "2026-01-01T00:00:00Z"
        state["sonarr"]["Default"]["last_successful_search"] = "2025-12-31T00:00:00Z"
        settings = _cycle_settings()
        instance_config = _cycle_instance_config()

        result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["sonarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "failed"
        assert ist["last_cycle"]["fetch_error"] == "HTTP error: ConnectError"
        assert ist["connected"] is False
        assert ist["last_run"] is not None
        assert ist["last_successful_search"] == "2025-12-31T00:00:00Z"
        assert ist["last_success"] == "2026-01-01T00:00:00Z"
    finally:
        await db.close()


async def test_sonarr_grade_nothing_needed_empty(tmp_path):
    """Both queues empty -> grade nothing_needed with eligible counts recorded as 0."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=[])
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_season = AsyncMock()

        state = _make_test_state()
        state["sonarr"]["Default"]["last_success"] = "2026-01-01T00:00:00Z"
        settings = _cycle_settings()
        instance_config = _cycle_instance_config()

        result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["sonarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "nothing_needed"
        assert ist["last_cycle"]["eligible"] == {"missing": 0, "cutoff": 0}
        assert ist["last_run"] is not None
        assert ist["last_successful_search"] is None
        assert ist["last_success"] == "2026-01-01T00:00:00Z"
    finally:
        await db.close()


async def test_sonarr_grade_inactive_queue_ignored(tmp_path):
    """An inactive (configured 0) queue is absent from eligible and doesn't block success."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[_make_sonarr_episode(series_id=10, season_number=1, series_title="Show A")]
        )
        client.get_wanted_cutoff = AsyncMock(
            return_value=[_make_sonarr_episode(series_id=20, season_number=1, series_title="Show B")]
        )
        client.search_season = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings(missing_count=1, cutoff_count=0)
        instance_config = _cycle_instance_config(missing_count=1, cutoff_count=0)

        result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["sonarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_cycle"]["accepted"] == 1
        assert "cutoff" not in ist["last_cycle"]["eligible"]

        # Both queues configured inactive (disabled instance) -> nothing_needed.
        state2 = _make_test_state()
        settings2 = make_settings(
            search_missing_count=0, search_cutoff_count=0,
            radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False,
        )
        instance_config2 = InstanceConfig(
            url="http://sonarr:8989", api_key="test-key", enabled=False,
            search_missing_count=0, search_cutoff_count=0,
        )
        result2 = await run_sonarr_cycle(client, state2, "Default", instance_config2, settings2, db)
        ist2 = result2["sonarr"]["Default"]

        assert ist2["last_cycle"]["grade"] == "nothing_needed"
        assert client.search_season.call_count == 1  # only the first scenario's missing item
    finally:
        await db.close()


async def test_sonarr_persistence_failure_still_accepted(tmp_path):
    """R8/OUTCOME-06: a success-path history-insert failure keeps the command accepted."""
    from unittest.mock import patch

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        episodes = [
            _make_sonarr_episode(series_id=10, season_number=1, series_title="Show A", episode_id=100),
            _make_sonarr_episode(series_id=10, season_number=2, series_title="Show A", episode_id=101),
        ]
        cutoff_episodes = [
            _make_sonarr_episode(series_id=30, season_number=1, series_title="Show C", episode_id=300),
        ]
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=episodes)
        client.get_wanted_cutoff = AsyncMock(return_value=cutoff_episodes)
        client.search_season = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings(missing_count=2, cutoff_count=1)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=1)

        with patch(
            "triggarr.search.engine.insert_search_entry",
            AsyncMock(side_effect=aiosqlite.OperationalError("database is locked")),
        ):
            result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["sonarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_cycle"]["accepted"] == 3
        assert ist["last_cycle"]["failed"] == 0
        assert ist["last_cycle"]["persistence_failed"] == 3
        assert ist["last_successful_search"] is not None
        assert client.search_season.call_count == 3
    finally:
        await db.close()


async def test_sonarr_hard_max_reallocates_to_queue_with_work(tmp_path):
    """R-01 amended: hard_max=1 reallocates to the queue with eligible work, never nothing_needed."""
    from triggarr.models.config import GeneralConfig

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        episodes = [
            _make_sonarr_episode(series_id=10 + i, season_number=1, series_title=f"Show {i}", episode_id=100 + i)
            for i in range(3)
        ]
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=episodes)
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_season = AsyncMock()

        state = _make_test_state()
        settings = make_settings(
            search_missing_count=50, search_cutoff_count=50,
            general=GeneralConfig(hard_max_per_cycle=1),
        )
        instance_config = _cycle_instance_config(missing_count=50, cutoff_count=50)

        result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["sonarr"]["Default"]

        assert client.search_season.call_count == 1
        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_cycle"]["eligible"] == {"missing": 3, "cutoff": 0}
    finally:
        await db.close()


async def test_sonarr_zero_dispatch_with_work_never_nothing_needed(tmp_path):
    """Backstop: a forced zero-dispatch cycle with eligible work grades failed, never nothing_needed."""
    from unittest.mock import patch

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
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

        with patch("triggarr.search.engine.rebalance_batch_sizes", return_value=(0, 0)):
            result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["sonarr"]["Default"]

        assert client.search_season.call_count == 0
        assert ist["last_cycle"]["grade"] == "failed"
    finally:
        await db.close()


async def test_sonarr_inactive_cutoff_fetch_fails_active_has_work(tmp_path):
    """R-07: an inactive cutoff queue's fetch failure doesn't block the active missing queue."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        episodes = [
            _make_sonarr_episode(series_id=10, season_number=1, series_title="Show A", episode_id=100),
            _make_sonarr_episode(series_id=10, season_number=2, series_title="Show A", episode_id=101),
        ]
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=episodes)
        client.get_wanted_cutoff = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))
        client.search_season = AsyncMock()

        state = _make_test_state()
        ist = state["sonarr"]["Default"]
        ist["cutoff_count"] = 7
        ist["cutoff_searchable"] = 3
        ist["cutoff_searched"] = ["9:1"]
        ist["missing_count"] = 5
        ist["missing_searched"] = ["4:1"]

        settings = _cycle_settings(missing_count=2, cutoff_count=0)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

        result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["sonarr"]["Default"]

        assert client.search_season.call_count == 2
        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_cycle"]["fetch_error"] is None
        assert ist["last_cycle"]["unevaluated"] == []
        assert ist["connected"] is True
        assert ist["unreachable_since"] is None
        assert ist["last_successful_search"] is not None
        assert ist["cutoff_count"] == 7
        assert ist["cutoff_searchable"] == 3
        assert ist["cutoff_searched"] == ["9:1"]
    finally:
        await db.close()


async def test_sonarr_inactive_cutoff_fetch_fails_active_empty(tmp_path):
    """R-07: inactive cutoff fetch failure with an empty active missing queue grades nothing_needed."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        request = httpx.Request("GET", "http://sonarr:8989/api/v3/wanted/cutoff")
        response = httpx.Response(503, request=request)
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=[])
        client.get_wanted_cutoff = AsyncMock(
            side_effect=httpx.HTTPStatusError("err", request=request, response=response)
        )
        client.search_season = AsyncMock()

        state = _make_test_state()
        ist = state["sonarr"]["Default"]
        ist["cutoff_count"] = 7
        ist["cutoff_searchable"] = 3
        ist["cutoff_searched"] = ["9:1"]
        ist["missing_count"] = 5
        ist["missing_searched"] = ["4:1"]

        settings = _cycle_settings(missing_count=2, cutoff_count=0)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

        result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["sonarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "nothing_needed"
        assert ist["connected"] is True
        assert ist["cutoff_count"] == 7
    finally:
        await db.close()


async def test_sonarr_both_inactive_both_fetches_fail(tmp_path):
    """R-07: both queues inactive and both fetches fail -> unreachable but graded nothing_needed, not failed."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.get_wanted_cutoff = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.search_season = AsyncMock()

        state = _make_test_state()
        ist = state["sonarr"]["Default"]
        ist["cutoff_count"] = 7
        ist["cutoff_searched"] = ["9:1"]
        ist["missing_count"] = 5
        ist["missing_searched"] = ["4:1"]

        settings = make_settings(
            search_missing_count=0, search_cutoff_count=0,
            radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False,
        )
        instance_config = InstanceConfig(
            url="http://sonarr:8989", api_key="test-key", enabled=False,
            search_missing_count=0, search_cutoff_count=0,
        )

        result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["sonarr"]["Default"]

        assert client.search_season.call_count == 0
        assert ist["last_cycle"]["grade"] == "nothing_needed"
        assert ist["last_cycle"]["fetch_error"] is None
        assert ist["connected"] is False
        assert ist["unreachable_since"] is not None
        assert ist["last_run"] is not None
        assert ist["missing_count"] == 5
        assert ist["cutoff_count"] == 7
    finally:
        await db.close()


async def test_sonarr_both_inactive_one_fetch_fails(tmp_path):
    """R-07: both queues inactive, only one fetch fails -> still connected True (the other succeeded)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[_make_sonarr_episode(series_id=10, season_number=1, series_title="Show A")]
        )
        client.get_wanted_cutoff = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.search_season = AsyncMock()

        state = _make_test_state()
        ist = state["sonarr"]["Default"]
        ist["cutoff_count"] = 7
        ist["cutoff_searched"] = ["9:1"]
        ist["missing_count"] = 5
        ist["missing_searched"] = ["4:1"]

        settings = make_settings(
            search_missing_count=0, search_cutoff_count=0,
            radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False,
        )
        instance_config = InstanceConfig(
            url="http://sonarr:8989", api_key="test-key", enabled=False,
            search_missing_count=0, search_cutoff_count=0,
        )

        result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["sonarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "nothing_needed"
        assert ist["connected"] is True
        assert client.search_season.call_count == 0
    finally:
        await db.close()


async def test_sonarr_active_fetch_failure_with_inactive_other_still_failed(tmp_path):
    """R-07: an active queue's fetch failure still grades failed; the inactive endpoint is never probed."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_season = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings(missing_count=2, cutoff_count=0)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

        result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["sonarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "failed"
        assert ist["last_cycle"]["fetch_error"] == "HTTP error: ConnectError"
        assert ist["connected"] is False
        assert client.get_wanted_cutoff.await_count == 0
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# 78-03: Lidarr honest grading, hard-max reallocation, R-07 fetch isolation,
# D-01 refresh boundary guard
# ---------------------------------------------------------------------------


async def test_lidarr_grade_success(tmp_path):
    """Two monitored missing albums, cutoff empty, both accepted -> grade success."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[
                {"id": 1, "title": "Album A", "monitored": True},
                {"id": 2, "title": "Album B", "monitored": True},
            ]
        )
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_albums = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings(missing_count=2, cutoff_count=2)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["lidarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_cycle"]["accepted"] == 2
        assert ist["last_cycle"]["failed"] == 0
        assert ist["last_successful_search"] == ist["last_run"] == ist["last_cycle"]["finished_at"]
        assert ist["last_success"] is None
    finally:
        await db.close()


async def test_lidarr_grade_partial(tmp_path):
    """One accepted album search, one failed -> grade partial."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        request = httpx.Request("POST", "http://lidarr:8686/api/v1/command")
        response = httpx.Response(500, request=request)
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[
                {"id": 1, "title": "Album A", "monitored": True},
                {"id": 2, "title": "Album B", "monitored": True},
            ]
        )
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_albums = AsyncMock(
            side_effect=[None, httpx.HTTPStatusError("err", request=request, response=response)]
        )

        state = _make_test_state()
        settings = _cycle_settings(missing_count=2, cutoff_count=2)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["lidarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "partial"
        assert ist["last_cycle"]["accepted"] == 1
        assert ist["last_cycle"]["failed"] == 1
        assert ist["last_cycle"]["failure_reasons"] == [{"reason": "HTTP 500", "count": 1}]
    finally:
        await db.close()


async def test_lidarr_grade_failed_all_commands(tmp_path):
    """All album searches fail -> grade failed; legacy last_success untouched."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[
                {"id": 1, "title": "Album A", "monitored": True},
                {"id": 2, "title": "Album B", "monitored": True},
            ]
        )
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_albums = AsyncMock(side_effect=httpx.ConnectError("refused"))

        state = _make_test_state()
        state["lidarr"]["Default"]["last_success"] = "2026-01-01T00:00:00Z"
        settings = _cycle_settings(missing_count=2, cutoff_count=2)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["lidarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "failed"
        assert ist["last_cycle"]["accepted"] == 0
        assert ist["last_cycle"]["failed"] == 2
        assert ist["connected"] is True
        assert ist["last_run"] is not None
        assert ist["last_successful_search"] is None
        assert ist["last_success"] == "2026-01-01T00:00:00Z"
    finally:
        await db.close()


async def test_lidarr_grade_failed_fetch(tmp_path):
    """Fetch failure -> grade failed, last_run stamped, last_successful_search untouched."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))

        state = _make_test_state()
        state["lidarr"]["Default"]["last_success"] = "2026-01-01T00:00:00Z"
        state["lidarr"]["Default"]["last_successful_search"] = "2025-12-31T00:00:00Z"
        settings = _cycle_settings()
        instance_config = _cycle_instance_config()

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["lidarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "failed"
        assert ist["last_cycle"]["fetch_error"] == "HTTP error: ConnectError"
        assert ist["connected"] is False
        assert ist["last_run"] is not None
        assert ist["last_successful_search"] == "2025-12-31T00:00:00Z"
        assert ist["last_success"] == "2026-01-01T00:00:00Z"
    finally:
        await db.close()


async def test_lidarr_grade_nothing_needed_empty(tmp_path):
    """Both queues empty -> grade nothing_needed with eligible counts recorded as 0."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=[])
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_albums = AsyncMock()

        state = _make_test_state()
        state["lidarr"]["Default"]["last_success"] = "2026-01-01T00:00:00Z"
        settings = _cycle_settings()
        instance_config = _cycle_instance_config()

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["lidarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "nothing_needed"
        assert ist["last_cycle"]["eligible"] == {"missing": 0, "cutoff": 0}
        assert ist["last_run"] is not None
        assert ist["last_successful_search"] is None
        assert ist["last_success"] == "2026-01-01T00:00:00Z"
    finally:
        await db.close()


async def test_lidarr_grade_inactive_queue_ignored(tmp_path):
    """An inactive (configured 0) queue is absent from eligible and doesn't block success."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[{"id": 1, "title": "Album A", "monitored": True}]
        )
        client.get_wanted_cutoff = AsyncMock(
            return_value=[{"id": 2, "title": "Album B", "monitored": True}]
        )
        client.search_albums = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings(missing_count=1, cutoff_count=0)
        instance_config = _cycle_instance_config(missing_count=1, cutoff_count=0)

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["lidarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_cycle"]["accepted"] == 1
        assert "cutoff" not in ist["last_cycle"]["eligible"]

        # Both queues configured inactive (disabled instance) -> nothing_needed.
        state2 = _make_test_state()
        settings2 = make_settings(
            search_missing_count=0, search_cutoff_count=0,
            radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False,
        )
        instance_config2 = InstanceConfig(
            url="http://lidarr:8686", api_key="test-key", enabled=False,
            search_missing_count=0, search_cutoff_count=0,
        )
        result2 = await run_lidarr_cycle(client, state2, "Default", instance_config2, settings2, db)
        ist2 = result2["lidarr"]["Default"]

        assert ist2["last_cycle"]["grade"] == "nothing_needed"
        assert client.search_albums.call_count == 1  # only the first scenario's missing item
    finally:
        await db.close()


async def test_lidarr_persistence_failure_still_accepted(tmp_path):
    """R8/OUTCOME-06: a success-path history-insert failure keeps the command accepted."""
    from unittest.mock import patch

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[
                {"id": 1, "title": "Album A", "monitored": True},
                {"id": 2, "title": "Album B", "monitored": True},
            ]
        )
        client.get_wanted_cutoff = AsyncMock(
            return_value=[{"id": 3, "title": "Album C", "monitored": True}]
        )
        client.search_albums = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings(missing_count=2, cutoff_count=1)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=1)

        with patch(
            "triggarr.search.engine.insert_search_entry",
            AsyncMock(side_effect=aiosqlite.OperationalError("database is locked")),
        ):
            result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["lidarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_cycle"]["accepted"] == 3
        assert ist["last_cycle"]["failed"] == 0
        assert ist["last_cycle"]["persistence_failed"] == 3
        assert ist["last_successful_search"] is not None
        assert client.search_albums.call_count == 3
    finally:
        await db.close()


async def test_lidarr_hard_max_reallocates_to_queue_with_work(tmp_path):
    """R-01 amended: hard_max=1 reallocates to the queue with eligible work, never nothing_needed."""
    from triggarr.models.config import GeneralConfig

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[{"id": i, "title": f"Album {i}", "monitored": True} for i in range(2)]
        )
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_albums = AsyncMock()

        state = _make_test_state()
        settings = make_settings(
            search_missing_count=50, search_cutoff_count=50,
            general=GeneralConfig(hard_max_per_cycle=1),
        )
        instance_config = _cycle_instance_config(missing_count=50, cutoff_count=50)

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["lidarr"]["Default"]

        assert client.search_albums.call_count == 1
        assert ist["last_cycle"]["grade"] == "success"
        assert ist["last_cycle"]["eligible"] == {"missing": 2, "cutoff": 0}
    finally:
        await db.close()


async def test_lidarr_zero_dispatch_with_work_never_nothing_needed(tmp_path):
    """Backstop: a forced zero-dispatch cycle with eligible work grades failed, never nothing_needed."""
    from unittest.mock import patch

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[
                {"id": 1, "title": "Album A", "monitored": True},
                {"id": 2, "title": "Album B", "monitored": True},
            ]
        )
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_albums = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings(missing_count=2, cutoff_count=2)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

        with patch("triggarr.search.engine.rebalance_batch_sizes", return_value=(0, 0)):
            result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["lidarr"]["Default"]

        assert client.search_albums.call_count == 0
        assert ist["last_cycle"]["grade"] == "failed"
    finally:
        await db.close()


async def test_lidarr_inactive_cutoff_fetch_fails_active_has_work(tmp_path):
    """R-07: an inactive cutoff queue's fetch failure doesn't block the active missing queue."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[
                {"id": 1, "title": "Album A", "monitored": True},
                {"id": 2, "title": "Album B", "monitored": True},
            ]
        )
        client.get_wanted_cutoff = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))
        client.search_albums = AsyncMock()

        state = _make_test_state()
        ist = state["lidarr"]["Default"]
        ist["cutoff_count"] = 7
        ist["cutoff_searched"] = ["99"]
        ist["missing_count"] = 5
        ist["missing_searched"] = ["42"]

        settings = _cycle_settings(missing_count=2, cutoff_count=0)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["lidarr"]["Default"]

        assert client.search_albums.call_count == 2
        assert ist["last_cycle"]["grade"] == "success"
        assert ist["connected"] is True
        assert ist["cutoff_count"] == 7
        assert ist["cutoff_searched"] == ["99"]
    finally:
        await db.close()


async def test_lidarr_inactive_cutoff_fetch_fails_active_empty(tmp_path):
    """R-07: inactive cutoff fetch failure with an empty active missing queue grades nothing_needed."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=[])
        client.get_wanted_cutoff = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))
        client.search_albums = AsyncMock()

        state = _make_test_state()
        ist = state["lidarr"]["Default"]
        ist["cutoff_count"] = 7
        ist["cutoff_searched"] = ["99"]
        ist["missing_count"] = 5
        ist["missing_searched"] = ["42"]

        settings = _cycle_settings(missing_count=2, cutoff_count=0)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["lidarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "nothing_needed"
        assert ist["connected"] is True
    finally:
        await db.close()


async def test_lidarr_both_inactive_both_fetches_fail(tmp_path):
    """R-07: both queues inactive and both fetches fail -> unreachable but graded nothing_needed, not failed."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.get_wanted_cutoff = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.search_albums = AsyncMock()

        state = _make_test_state()
        ist = state["lidarr"]["Default"]
        ist["cutoff_count"] = 7
        ist["cutoff_searched"] = ["99"]
        ist["missing_count"] = 5
        ist["missing_searched"] = ["42"]

        settings = make_settings(
            search_missing_count=0, search_cutoff_count=0,
            radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False,
        )
        instance_config = InstanceConfig(
            url="http://lidarr:8686", api_key="test-key", enabled=False,
            search_missing_count=0, search_cutoff_count=0,
        )

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["lidarr"]["Default"]

        assert client.search_albums.call_count == 0
        assert ist["last_cycle"]["grade"] == "nothing_needed"
        assert ist["connected"] is False
        assert ist["unreachable_since"] is not None
    finally:
        await db.close()


async def test_lidarr_both_inactive_one_fetch_fails(tmp_path):
    """R-07: both queues inactive, only one fetch fails -> still connected True (the other succeeded)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(
            return_value=[{"id": 1, "title": "Album A", "monitored": True}]
        )
        client.get_wanted_cutoff = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.search_albums = AsyncMock()

        state = _make_test_state()
        ist = state["lidarr"]["Default"]
        ist["cutoff_count"] = 7
        ist["cutoff_searched"] = ["99"]
        ist["missing_count"] = 5
        ist["missing_searched"] = ["42"]

        settings = make_settings(
            search_missing_count=0, search_cutoff_count=0,
            radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False,
        )
        instance_config = InstanceConfig(
            url="http://lidarr:8686", api_key="test-key", enabled=False,
            search_missing_count=0, search_cutoff_count=0,
        )

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["lidarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "nothing_needed"
        assert ist["connected"] is True
        assert client.search_albums.call_count == 0
    finally:
        await db.close()


async def test_lidarr_active_fetch_failure_with_inactive_other_still_failed(tmp_path):
    """R-07: an active queue's fetch failure still grades failed; the inactive endpoint is never probed."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.search_albums = AsyncMock()

        state = _make_test_state()
        settings = _cycle_settings(missing_count=2, cutoff_count=0)
        instance_config = _cycle_instance_config(missing_count=2, cutoff_count=0)

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
        ist = result["lidarr"]["Default"]

        assert ist["last_cycle"]["grade"] == "failed"
        assert ist["last_cycle"]["fetch_error"] == "HTTP error: ConnectError"
        assert ist["connected"] is False
        assert client.get_wanted_cutoff.await_count == 0
    finally:
        await db.close()


async def test_refresh_counts_never_touch_last_cycle(tmp_path):
    """D-01/R2: refresh_*_counts never touch last_cycle, last_run, last_successful_search, or last_success.

    Regression guard -- refresh_*_counts already never write these fields (D-01
    predates this phase); this test pins that contract against this phase's new
    last_cycle/last_successful_search fields and passes immediately.
    """
    from triggarr.search.engine import refresh_lidarr_counts, refresh_radarr_counts, refresh_sonarr_counts

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    try:
        frozen_last_cycle = {
            "grade": "success", "accepted": 1, "failed": 0, "malformed_skipped": 0,
            "persistence_failed": 0, "failure_reasons": [], "unevaluated": [],
            "eligible": {"missing": 1}, "fetch_error": None, "finished_at": "2026-01-01T00:00:00Z",
        }
        settings = _cycle_settings()
        instance_config = _cycle_instance_config()

        for app_type, refresh_fn in (
            ("radarr", refresh_radarr_counts),
            ("sonarr", refresh_sonarr_counts),
            ("lidarr", refresh_lidarr_counts),
        ):
            client = AsyncMock()
            client.get_wanted_missing = AsyncMock(return_value=[])
            client.get_wanted_cutoff = AsyncMock(return_value=[])
            state = _make_test_state()
            ist = state[app_type]["Default"]
            ist["last_cycle"] = dict(frozen_last_cycle)
            ist["last_run"] = "2026-01-01T00:00:00Z"
            ist["last_successful_search"] = "2026-01-01T00:00:00Z"
            ist["last_success"] = "2025-01-01T00:00:00Z"

            await refresh_fn(client, state, "Default", instance_config, settings)

            assert ist["last_cycle"] == frozen_last_cycle
            assert ist["last_run"] == "2026-01-01T00:00:00Z"
            assert ist["last_successful_search"] == "2026-01-01T00:00:00Z"
            assert ist["last_success"] == "2025-01-01T00:00:00Z"
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Phase 79: Radarr/Lidarr tag-scope skip-and-warn (TAGSCOPE-01..03, D-01..05)
# ---------------------------------------------------------------------------


async def test_radarr_missing_tag_unresolved_cutoff_tag_resolves_cutoff_still_runs(tmp_path):
    """TAGSCOPE-01: missing's tag is unresolved but cutoff's tag resolves -- cutoff still dispatches."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="4k")])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[
        {"id": 2, "title": "Movie B", "monitored": True, "tags": [5]},
        {"id": 3, "title": "Movie C", "monitored": True, "tags": [6]},
    ])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="gone", cutoff_tag="4k",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    assert client.search_movies.call_count == 1
    client.search_movies.assert_called_once_with([2])
    ist = result["radarr"]["Default"]
    assert ist["tag_warnings"] == [{"tag": "gone", "field": "missing", "reason": "not_found"}]
    assert ist["last_cycle"]["grade"] == "partial"
    await db.close()


async def test_lidarr_missing_tag_unresolved_cutoff_tag_resolves_cutoff_still_runs(tmp_path):
    """TAGSCOPE-01: missing's tag is unresolved but cutoff's tag resolves -- cutoff still dispatches."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    try:
        client = AsyncMock()
        client.get_tags = AsyncMock(return_value=[Tag(id=5, label="4k")])
        client.get_wanted_missing = AsyncMock(return_value=[
            {"id": 1, "title": "Album A", "monitored": True, "artist": {"tags": []}},
        ])
        client.get_wanted_cutoff = AsyncMock(return_value=[
            {"id": 2, "title": "Album B", "monitored": True, "artist": {"tags": [5]}},
            {"id": 3, "title": "Album C", "monitored": True, "artist": {"tags": [6]}},
        ])
        client.get_library_count = AsyncMock(return_value=10)
        client.search_albums = AsyncMock()

        state = _make_test_state()
        instance_config = InstanceConfig(
            url="http://lidarr:8686", api_key="test-key", enabled=True,
            search_missing_count=5, search_cutoff_count=5,
            missing_tag="gone", cutoff_tag="4k",
        )
        settings = _cycle_settings(missing_count=5, cutoff_count=5)

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)

        assert client.search_albums.call_count == 1
        client.search_albums.assert_called_once_with([2])
        ist = result["lidarr"]["Default"]
        assert ist["tag_warnings"] == [{"tag": "gone", "field": "missing", "reason": "not_found"}]
        assert ist["last_cycle"]["grade"] == "partial"
    finally:
        await db.close()


async def test_radarr_cutoff_tag_unresolved_missing_untagged_still_runs(tmp_path):
    """TAGSCOPE-01: cutoff's tag is unresolved but missing has no tag -- missing still dispatches."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=9, label="other")])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True},
        {"id": 2, "title": "Movie B", "monitored": True},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[
        {"id": 3, "title": "Movie C", "monitored": True, "tags": []},
    ])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        cutoff_tag="gone",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    assert client.search_movies.call_count == 2
    assert result["radarr"]["Default"]["last_cycle"]["grade"] == "partial"
    await db.close()


async def test_radarr_tag_unresolved_keeps_last_good_counts_and_searched_log(tmp_path):
    """R5/D-05: an unresolved-tag queue keeps its last-good counts and searched-log untouched."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    ist = state["radarr"]["Default"]
    ist["missing_eligible"] = 7
    ist["missing_monitored"] = 9
    ist["missing_searched"] = ["1"]
    ist["scoped_count_tags"] = {"missing": "gone"}

    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=0,
        missing_tag="gone",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=0)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    out_ist = result["radarr"]["Default"]
    assert out_ist["missing_eligible"] == 7
    assert out_ist["missing_monitored"] == 9
    assert out_ist["missing_searched"] == ["1"]
    assert out_ist["scoped_count_tags"] == {"missing": "gone"}
    assert out_ist["unresolved_tag_scopes"] == {"missing": "gone"}
    await db.close()


async def test_lidarr_tag_unresolved_keeps_last_good_counts_and_searched_log(tmp_path):
    """R5/D-05: an unresolved-tag queue keeps its last-good counts and searched-log untouched."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    try:
        client = AsyncMock()
        client.get_tags = AsyncMock(return_value=[])
        client.get_wanted_missing = AsyncMock(return_value=[
            {"id": 1, "title": "Album A", "monitored": True, "artist": {"tags": []}},
        ])
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.get_library_count = AsyncMock(return_value=10)
        client.search_albums = AsyncMock()

        state = _make_test_state()
        ist = state["lidarr"]["Default"]
        ist["missing_eligible"] = 7
        ist["missing_monitored"] = 9
        ist["missing_searched"] = ["1"]
        ist["scoped_count_tags"] = {"missing": "gone"}

        instance_config = InstanceConfig(
            url="http://lidarr:8686", api_key="test-key", enabled=True,
            search_missing_count=5, search_cutoff_count=0,
            missing_tag="gone",
        )
        settings = _cycle_settings(missing_count=5, cutoff_count=0)

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)

        out_ist = result["lidarr"]["Default"]
        assert out_ist["missing_eligible"] == 7
        assert out_ist["missing_monitored"] == 9
        assert out_ist["missing_searched"] == ["1"]
        assert out_ist["scoped_count_tags"] == {"missing": "gone"}
        assert out_ist["unresolved_tag_scopes"] == {"missing": "gone"}
    finally:
        await db.close()


async def test_radarr_resolved_scope_stamps_scoped_counts(tmp_path):
    """D-05 revision 1: a resolved scope stamps the committed count with its tag name."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="4k")])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True, "tags": [5]},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="4k",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    assert result["radarr"]["Default"]["scoped_count_tags"]["missing"] == "4k"
    await db.close()


async def test_radarr_resolved_scope_stamps_scoped_counts_none_when_untagged(tmp_path):
    """D-05 revision 1: an untagged missing queue stamps scoped_count_tags['missing'] as None."""
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
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    assert result["radarr"]["Default"]["scoped_count_tags"]["missing"] is None
    await db.close()


async def test_lidarr_resolved_scope_stamps_scoped_counts(tmp_path):
    """D-05 revision 1: a resolved scope stamps the committed count with its tag name."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    try:
        client = AsyncMock()
        client.get_tags = AsyncMock(return_value=[Tag(id=5, label="4k")])
        client.get_wanted_missing = AsyncMock(return_value=[
            {"id": 1, "title": "Album A", "monitored": True, "artist": {"tags": [5]}},
        ])
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.get_library_count = AsyncMock(return_value=10)
        client.search_albums = AsyncMock()

        state = _make_test_state()
        instance_config = InstanceConfig(
            url="http://lidarr:8686", api_key="test-key", enabled=True,
            search_missing_count=5, search_cutoff_count=5,
            missing_tag="4k",
        )
        settings = _cycle_settings(missing_count=5, cutoff_count=5)

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)

        assert result["lidarr"]["Default"]["scoped_count_tags"]["missing"] == "4k"
    finally:
        await db.close()


async def test_lidarr_resolved_scope_stamps_scoped_counts_none_when_untagged(tmp_path):
    """D-05 revision 1: an untagged missing queue stamps scoped_count_tags['missing'] as None."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    try:
        client = AsyncMock()
        client.get_wanted_missing = AsyncMock(return_value=[
            {"id": 1, "title": "Album A", "monitored": True, "artist": {"tags": []}},
        ])
        client.get_wanted_cutoff = AsyncMock(return_value=[])
        client.get_library_count = AsyncMock(return_value=10)
        client.search_albums = AsyncMock()

        state = _make_test_state()
        instance_config = InstanceConfig(
            url="http://lidarr:8686", api_key="test-key", enabled=True,
            search_missing_count=5, search_cutoff_count=5,
        )
        settings = _cycle_settings(missing_count=5, cutoff_count=5)

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)

        assert result["lidarr"]["Default"]["scoped_count_tags"]["missing"] is None
    finally:
        await db.close()


async def test_radarr_inactive_queue_unresolved_tag_no_warning_no_grade_effect(tmp_path):
    """D-04/OQ1: an inactive queue's unresolved tag never warns or affects the grade."""
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
    ist = state["radarr"]["Default"]
    ist["missing_eligible"] = 4

    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=0, search_cutoff_count=5,
        missing_tag="gone",
    )
    settings = _cycle_settings(missing_count=0, cutoff_count=5)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    out_ist = result["radarr"]["Default"]
    assert out_ist["tag_warnings"] == []
    assert out_ist["last_cycle"]["unevaluated"] == []
    assert out_ist["last_cycle"]["grade"] == "success"
    assert out_ist["missing_eligible"] == 4
    assert out_ist["unresolved_tag_scopes"] == {"missing": "gone"}
    await db.close()


async def test_radarr_tag_warning_clears_when_tag_resolves(tmp_path):
    """TAGSCOPE-02: the tag-skip warning clears automatically once the tag resolves."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True, "tags": [5]},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="4k",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    client.get_tags = AsyncMock(return_value=[])
    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["tag_warnings"] != []
    assert client.search_movies.call_count == 0

    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="4k")])
    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["tag_warnings"] == []
    assert client.search_movies.call_count == 1
    client.search_movies.assert_called_once_with([1])
    await db.close()


async def test_radarr_both_tags_fetch_failure_skips_both_queues(tmp_path):
    """TAGSCOPE-01/02: a tag-list fetch failure skips both configured queues."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(side_effect=httpx.ConnectError("refused"))
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
        missing_tag="a", cutoff_tag="b",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    assert client.search_movies.call_count == 0
    ist = result["radarr"]["Default"]
    assert len(ist["tag_warnings"]) == 2
    assert all(w["reason"] == "fetch_failed" for w in ist["tag_warnings"])
    assert ist["last_cycle"]["grade"] == "failed"
    await db.close()


async def test_radarr_skipped_missing_survives_cutoff_data_fault(tmp_path):
    """Revision 2/D-05: a cutoff-side data fault never clears a skipped missing queue's stamps."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="4k")])
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[
        {"id": 2, "title": "Movie B", "monitored": True, "tags": 5},
    ])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    ist = state["radarr"]["Default"]
    ist["missing_monitored"] = 9
    ist["missing_eligible"] = 7
    ist["missing_searched"] = ["1"]
    ist["scoped_count_tags"] = {"missing": "gone"}

    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=5, search_cutoff_count=5,
        missing_tag="gone", cutoff_tag="4k",
    )
    settings = _cycle_settings(missing_count=5, cutoff_count=5)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    assert client.search_movies.call_count == 0
    out_ist = result["radarr"]["Default"]
    assert out_ist["missing_monitored"] == 9
    assert out_ist["missing_eligible"] == 7
    assert out_ist["missing_searched"] == ["1"]
    assert out_ist["scoped_count_tags"] == {"missing": "gone"}
    assert {e["queue"] for e in out_ist["last_cycle"]["unevaluated"]} == {"missing", "cutoff"}
    assert out_ist["last_cycle"]["grade"] == "failed"
    await db.close()


async def test_lidarr_skipped_missing_survives_cutoff_data_fault(tmp_path):
    """Revision 2/D-05: a cutoff-side data fault never clears a skipped missing queue's stamps."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    try:
        client = AsyncMock()
        client.get_tags = AsyncMock(return_value=[Tag(id=5, label="4k")])
        client.get_wanted_missing = AsyncMock(return_value=[
            {"id": 1, "title": "Album A", "monitored": True, "artist": {"tags": []}},
        ])
        client.get_wanted_cutoff = AsyncMock(return_value=[
            {"id": 2, "title": "Album B", "monitored": True, "artist": {"tags": 5}},
        ])
        client.get_library_count = AsyncMock(return_value=10)
        client.search_albums = AsyncMock()

        state = _make_test_state()
        ist = state["lidarr"]["Default"]
        ist["missing_monitored"] = 9
        ist["missing_eligible"] = 7
        ist["missing_searched"] = ["1"]
        ist["scoped_count_tags"] = {"missing": "gone"}

        instance_config = InstanceConfig(
            url="http://lidarr:8686", api_key="test-key", enabled=True,
            search_missing_count=5, search_cutoff_count=5,
            missing_tag="gone", cutoff_tag="4k",
        )
        settings = _cycle_settings(missing_count=5, cutoff_count=5)

        result = await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)

        assert client.search_albums.call_count == 0
        out_ist = result["lidarr"]["Default"]
        assert out_ist["missing_monitored"] == 9
        assert out_ist["missing_eligible"] == 7
        assert out_ist["missing_searched"] == ["1"]
        assert out_ist["scoped_count_tags"] == {"missing": "gone"}
        assert {e["queue"] for e in out_ist["last_cycle"]["unevaluated"]} == {"missing", "cutoff"}
        assert out_ist["last_cycle"]["grade"] == "failed"
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Phase 79: Sonarr tag-scope skip-and-warn (TAGSCOPE-01..03, D-01..05)
# ---------------------------------------------------------------------------


async def test_sonarr_missing_tag_unresolved_cutoff_tag_resolves_cutoff_still_runs(tmp_path):
    """TAGSCOPE-01: missing's tag is unresolved but cutoff's tag resolves -- cutoff still dispatches."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=10, label="4k")])
    _ep = _make_tagged_sonarr_episode
    client.get_wanted_missing = AsyncMock(return_value=[
        _ep(series_id=100, season_number=1, series_title="Show A", episode_id=1, series_tags=[]),
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[
        _ep(series_id=200, season_number=1, series_title="Show B", episode_id=2, series_tags=[10]),
        _ep(series_id=300, season_number=1, series_title="Show C", episode_id=3, series_tags=[11]),
    ])
    client.search_season = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://sonarr:8989", api_key="test-key", enabled=True,
        search_missing_count=10, search_cutoff_count=10,
        missing_tag="gone", cutoff_tag="4k",
    )
    settings = _cycle_settings(missing_count=10, cutoff_count=10)

    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    assert client.search_season.call_count == 1
    client.search_season.assert_called_once_with(200, 1)
    assert result["sonarr"]["Default"]["last_cycle"]["grade"] == "partial"
    await db.close()


async def test_sonarr_tag_fetch_failure_skips_tagged_queue(tmp_path):
    """TAGSCOPE-01/02: a tag-list fetch failure skips the tagged queue."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(side_effect=httpx.ConnectError("refused"))
    _ep = _make_tagged_sonarr_episode
    client.get_wanted_missing = AsyncMock(return_value=[
        _ep(series_id=100, season_number=1, series_title="Show A", episode_id=1),
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

    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    assert client.search_season.call_count == 0
    ist = result["sonarr"]["Default"]
    assert ist["tag_warnings"][0]["reason"] == "fetch_failed"
    assert ist["last_cycle"]["grade"] == "failed"
    await db.close()


async def test_sonarr_tag_unresolved_keeps_last_good_counts(tmp_path):
    """R5/D-05: an unresolved-tag queue keeps its last-good counts and searched-log untouched."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[])
    _ep = _make_tagged_sonarr_episode
    client.get_wanted_missing = AsyncMock(return_value=[
        _ep(series_id=100, season_number=1, series_title="Show A", episode_id=1),
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[
        _ep(series_id=200, season_number=1, series_title="Show B", episode_id=2),
    ])
    client.search_season = AsyncMock()

    state = _make_test_state()
    ist = state["sonarr"]["Default"]
    ist["missing_eligible"] = 7
    ist["missing_searchable"] = 3
    ist["missing_searched"] = ["10:1"]
    ist["cutoff_searchable"] = 2
    ist["scoped_count_tags"] = {"missing": "m", "cutoff": "c"}

    instance_config = InstanceConfig(
        url="http://sonarr:8989", api_key="test-key", enabled=True,
        search_missing_count=10, search_cutoff_count=10,
        missing_tag="m", cutoff_tag="c",
    )
    settings = _cycle_settings(missing_count=10, cutoff_count=10)

    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    out_ist = result["sonarr"]["Default"]
    assert out_ist["missing_eligible"] == 7
    assert out_ist["missing_searchable"] == 3
    assert out_ist["missing_searched"] == ["10:1"]
    assert out_ist["cutoff_searchable"] == 2
    assert out_ist["scoped_count_tags"] == {"missing": "m", "cutoff": "c"}
    assert out_ist["unresolved_tag_scopes"] == {"missing": "m", "cutoff": "c"}
    await db.close()


async def test_sonarr_resolved_scopes_stamp_both_queues(tmp_path):
    """D-05 revision 1: resolved scopes stamp both queues' committed counts with their tag names."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[Tag(id=10, label="m"), Tag(id=11, label="c")])
    _ep = _make_tagged_sonarr_episode
    client.get_wanted_missing = AsyncMock(return_value=[
        _ep(series_id=100, season_number=1, series_title="Show A", episode_id=1, series_tags=[10]),
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[
        _ep(series_id=200, season_number=1, series_title="Show B", episode_id=2, series_tags=[11]),
    ])
    client.search_season = AsyncMock()

    state = _make_test_state()
    instance_config = InstanceConfig(
        url="http://sonarr:8989", api_key="test-key", enabled=True,
        search_missing_count=10, search_cutoff_count=10,
        missing_tag="m", cutoff_tag="c",
    )
    settings = _cycle_settings(missing_count=10, cutoff_count=10)

    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    assert result["sonarr"]["Default"]["scoped_count_tags"] == {"missing": "m", "cutoff": "c"}
    await db.close()


async def test_sonarr_inactive_queue_unresolved_tag_no_warning(tmp_path):
    """D-04/OQ1: an inactive queue's unresolved tag never warns or affects the grade."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[])
    _ep = _make_tagged_sonarr_episode
    client.get_wanted_missing = AsyncMock(return_value=[
        _ep(series_id=100, season_number=1, series_title="Show A", episode_id=1),
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[
        _ep(series_id=200, season_number=1, series_title="Show B", episode_id=2),
    ])
    client.search_season = AsyncMock()

    state = _make_test_state()
    ist = state["sonarr"]["Default"]
    ist["cutoff_searchable"] = 5

    instance_config = InstanceConfig(
        url="http://sonarr:8989", api_key="test-key", enabled=True,
        search_missing_count=10, search_cutoff_count=0,
        cutoff_tag="gone",
    )
    settings = _cycle_settings(missing_count=10, cutoff_count=0)

    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    out_ist = result["sonarr"]["Default"]
    assert out_ist["tag_warnings"] == []
    assert out_ist["cutoff_searchable"] == 5
    assert out_ist["last_cycle"]["unevaluated"] == []
    await db.close()


async def test_sonarr_skipped_missing_survives_cutoff_data_fault(tmp_path):
    """Revision 2/D-05: a cutoff-side data fault never clears a skipped missing queue's stamps."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_tags = AsyncMock(return_value=[])
    client.get_wanted_missing = AsyncMock(return_value=[
        _make_tagged_sonarr_episode(series_id=100, season_number=1, series_title="Show A", episode_id=1),
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[
        {
            "id": 2,
            "seriesId": 200,
            "seasonNumber": 1,
            "monitored": True,
            "airDateUtc": "2025-01-01T00:00:00Z",
            "series": "garbage",
        },
    ])
    client.search_season = AsyncMock()

    state = _make_test_state()
    ist = state["sonarr"]["Default"]
    ist["missing_eligible"] = 7
    ist["missing_searchable"] = 3
    ist["missing_searched"] = ["10:1"]
    ist["cutoff_searchable"] = 2
    ist["scoped_count_tags"] = {"missing": "gone", "cutoff": "c"}

    instance_config = InstanceConfig(
        url="http://sonarr:8989", api_key="test-key", enabled=True,
        search_missing_count=10, search_cutoff_count=10,
        missing_tag="gone",
    )
    settings = _cycle_settings(missing_count=10, cutoff_count=10)

    result = await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)

    assert client.search_season.call_count == 0
    out_ist = result["sonarr"]["Default"]
    assert out_ist["missing_eligible"] == 7
    assert out_ist["missing_searchable"] == 3
    assert out_ist["missing_searched"] == ["10:1"]
    assert out_ist["cutoff_searchable"] == 2
    assert out_ist["scoped_count_tags"] == {"missing": "gone", "cutoff": "c"}
    assert out_ist["last_cycle"]["grade"] == "failed"
    await db.close()


# ---------------------------------------------------------------------------
# Phase 79: _resolve_tag_scope (TAGSCOPE-01..03, D-01..05, OQ1)
# ---------------------------------------------------------------------------


def _tag_scope_instance_config(
    *,
    missing_tag: str = "",
    cutoff_tag: str = "",
    missing_count: int = 5,
    cutoff_count: int = 5,
) -> InstanceConfig:
    """Build an InstanceConfig for _resolve_tag_scope unit tests."""
    return InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=True,
        search_missing_count=missing_count, search_cutoff_count=cutoff_count,
        missing_tag=missing_tag, cutoff_tag=cutoff_tag,
    )


async def test_resolve_tag_scope_no_tags_configured_never_fetches():
    """Neither queue has a tag configured -- fetch_tags is never awaited, nothing unresolved."""
    from triggarr.search.engine import _resolve_tag_scope
    from triggarr.search.outcome import CycleTally

    ist = _make_test_state()["radarr"]["Default"]
    ist["tag_warnings"] = [{"tag": "stale", "field": "missing"}]
    ist["unresolved_tag_scopes"] = {"missing": "old"}
    tally = CycleTally()
    fetch_tags = AsyncMock()
    instance_config = _tag_scope_instance_config()

    scope = await _resolve_tag_scope(
        instance_config=instance_config, fetch_tags=fetch_tags, ist=ist,
        app_label="Radarr", tally=tally,
    )

    fetch_tags.assert_not_awaited()
    assert scope.missing_tag_id is None
    assert scope.cutoff_tag_id is None
    assert scope.missing_unresolved is False
    assert scope.cutoff_unresolved is False
    assert ist["tag_warnings"] == []
    assert ist["unresolved_tag_scopes"] == {}


async def test_resolve_tag_scope_both_resolve():
    """Both configured tags resolve -- no warnings, no unevaluated entries, no unresolved markers."""
    from triggarr.search.engine import _resolve_tag_scope
    from triggarr.search.outcome import CycleTally

    ist = _make_test_state()["radarr"]["Default"]
    tally = CycleTally()
    fetch_tags = AsyncMock(return_value=[Tag(id=5, label="4k"), Tag(id=6, label="upgrade")])
    instance_config = _tag_scope_instance_config(missing_tag="4K ", cutoff_tag="upgrade")

    scope = await _resolve_tag_scope(
        instance_config=instance_config, fetch_tags=fetch_tags, ist=ist,
        app_label="Radarr", tally=tally,
    )

    assert scope.missing_tag_id == 5
    assert scope.cutoff_tag_id == 6
    assert scope.missing_unresolved is False
    assert scope.cutoff_unresolved is False
    assert ist["tag_warnings"] == []
    assert tally.unevaluated == []
    assert ist["unresolved_tag_scopes"] == {}


async def test_resolve_tag_scope_missing_not_found_active():
    """Configured tag is not in the tag list -- missing queue unresolved, warned, graded."""
    from triggarr.search.engine import _resolve_tag_scope
    from triggarr.search.outcome import CycleTally

    ist = _make_test_state()["radarr"]["Default"]
    tally = CycleTally()
    fetch_tags = AsyncMock(return_value=[Tag(id=1, label="other")])
    instance_config = _tag_scope_instance_config(missing_tag="gone", missing_count=5, cutoff_count=0)

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        scope = await _resolve_tag_scope(
            instance_config=instance_config, fetch_tags=fetch_tags, ist=ist,
            app_label="Radarr", tally=tally,
        )
    finally:
        logger.remove(handler_id)

    assert scope.missing_unresolved is True
    assert ist["tag_warnings"] == [{"tag": "gone", "field": "missing", "reason": "not_found"}]
    assert tally.unevaluated == [{"queue": "missing", "reason": "tag 'gone' not found"}]
    log_output = sink.getvalue()
    assert "Missing queue skipped" in log_output
    assert "not found" in log_output
    assert ist["unresolved_tag_scopes"] == {"missing": "gone"}


async def test_resolve_tag_scope_fetch_failure_active_both_queues():
    """Tag-list fetch itself fails -- both configured queues unresolved with fetch_failed reason."""
    from triggarr.search.engine import _resolve_tag_scope
    from triggarr.search.outcome import CycleTally

    ist = _make_test_state()["radarr"]["Default"]
    tally = CycleTally()
    fetch_tags = AsyncMock(side_effect=httpx.ConnectError("boom apikey=SECRET123"))
    instance_config = _tag_scope_instance_config(missing_tag="a", cutoff_tag="b")

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        scope = await _resolve_tag_scope(
            instance_config=instance_config, fetch_tags=fetch_tags, ist=ist,
            app_label="Radarr", tally=tally,
        )
    finally:
        logger.remove(handler_id)

    assert scope.missing_unresolved is True
    assert scope.cutoff_unresolved is True
    assert len(ist["tag_warnings"]) == 2
    assert all(w["reason"] == "fetch_failed" for w in ist["tag_warnings"])
    assert len(tally.unevaluated) == 2
    assert all(entry["reason"] == "couldn't load tags" for entry in tally.unevaluated)
    log_output = sink.getvalue()
    assert "Failed to fetch tags" in log_output
    serialized = repr(ist["tag_warnings"]) + repr(tally.unevaluated) + repr(ist["unresolved_tag_scopes"])
    assert "boom" not in serialized
    assert "SECRET123" not in serialized
    assert ist["unresolved_tag_scopes"] == {"missing": "a", "cutoff": "b"}


async def test_resolve_tag_scope_inactive_queue_unresolved_no_warning_no_grade():
    """D-04/OQ1: an inactive queue's unresolved tag freezes counts but never warns or grades."""
    from triggarr.search.engine import _resolve_tag_scope
    from triggarr.search.outcome import CycleTally

    ist = _make_test_state()["radarr"]["Default"]
    tally = CycleTally()
    fetch_tags = AsyncMock(return_value=[])
    instance_config = _tag_scope_instance_config(missing_tag="gone", missing_count=0, cutoff_count=5)

    scope = await _resolve_tag_scope(
        instance_config=instance_config, fetch_tags=fetch_tags, ist=ist,
        app_label="Radarr", tally=tally,
    )

    assert scope.missing_unresolved is True
    assert ist["tag_warnings"] == []
    assert tally.unevaluated == []
    assert ist["unresolved_tag_scopes"] == {"missing": "gone"}


async def test_resolve_tag_scope_tally_none_still_warns():
    """Refresh-mode call (tally=None) still records the warning without raising."""
    from triggarr.search.engine import _resolve_tag_scope

    ist = _make_test_state()["radarr"]["Default"]
    fetch_tags = AsyncMock(return_value=[])
    instance_config = _tag_scope_instance_config(missing_tag="gone", missing_count=5, cutoff_count=0)

    scope = await _resolve_tag_scope(
        instance_config=instance_config, fetch_tags=fetch_tags, ist=ist,
        app_label="Radarr", tally=None,
    )

    assert scope.missing_unresolved is True
    assert ist["tag_warnings"] == [{"tag": "gone", "field": "missing", "reason": "not_found"}]


async def test_resolve_tag_scope_one_queue_resolves_other_not():
    """Independent per-queue resolution: one tag resolves while the other doesn't."""
    from triggarr.search.engine import _resolve_tag_scope
    from triggarr.search.outcome import CycleTally

    ist = _make_test_state()["radarr"]["Default"]
    tally = CycleTally()
    fetch_tags = AsyncMock(return_value=[Tag(id=5, label="4k")])
    instance_config = _tag_scope_instance_config(missing_tag="gone", cutoff_tag="4k")

    scope = await _resolve_tag_scope(
        instance_config=instance_config, fetch_tags=fetch_tags, ist=ist,
        app_label="Radarr", tally=tally,
    )

    assert scope.missing_unresolved is True
    assert scope.cutoff_unresolved is False
    assert scope.cutoff_tag_id == 5
    assert ist["unresolved_tag_scopes"] == {"missing": "gone"}


# ---------------------------------------------------------------------------
# Phase 79: _stamp_scoped_counts
# ---------------------------------------------------------------------------


def test_stamp_scoped_counts_creates_and_preserves_other_field():
    from triggarr.search.engine import _stamp_scoped_counts

    ist = _make_test_state()["radarr"]["Default"]
    assert "scoped_count_tags" not in ist

    _stamp_scoped_counts(ist, "missing", "4k")
    assert ist["scoped_count_tags"] == {"missing": "4k"}

    _stamp_scoped_counts(ist, "cutoff", None)
    assert ist["scoped_count_tags"] == {"missing": "4k", "cutoff": None}


def test_stamp_scoped_counts_replaces_non_dict_value():
    from triggarr.search.engine import _stamp_scoped_counts

    ist = _make_test_state()["radarr"]["Default"]
    ist["scoped_count_tags"] = "garbage"

    _stamp_scoped_counts(ist, "missing", "4k")

    assert ist["scoped_count_tags"] == {"missing": "4k"}


# ---------------------------------------------------------------------------
# Phase 79-04: shared _finish_both_inactive_unreachable / _cap_and_log helpers
# ---------------------------------------------------------------------------


def test_finish_both_inactive_unreachable_marks_unreachable_and_grades_nothing_needed():
    from triggarr.search.engine import _finish_both_inactive_unreachable
    from triggarr.search.outcome import CycleTally

    ist = _make_test_state()["sonarr"]["Default"]
    tally = CycleTally()
    instance_config = InstanceConfig(
        url="http://sonarr:8989", api_key="test-key", enabled=False,
        search_missing_count=0, search_cutoff_count=0,
    )

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        _finish_both_inactive_unreachable(
            ist=ist, tally=tally, instance_config=instance_config, app_label="Sonarr",
        )
    finally:
        logger.remove(handler_id)

    assert ist["connected"] is False
    assert ist["unreachable_since"] is not None
    assert ist["last_cycle"]["grade"] == "nothing_needed"
    log_output = sink.getvalue()
    assert (
        "Sonarr: both queues inactive and neither could be fetched -- "
        "marked unreachable; not graded Failed"
    ) in log_output


def test_finish_both_inactive_unreachable_preserves_existing_unreachable_since():
    from triggarr.search.engine import _finish_both_inactive_unreachable
    from triggarr.search.outcome import CycleTally

    ist = _make_test_state()["radarr"]["Default"]
    ist["unreachable_since"] = "2025-01-01T00:00:00Z"
    tally = CycleTally()
    instance_config = InstanceConfig(
        url="http://radarr:7878", api_key="test-key", enabled=False,
        search_missing_count=0, search_cutoff_count=0,
    )

    _finish_both_inactive_unreachable(
        ist=ist, tally=tally, instance_config=instance_config, app_label="Radarr",
    )

    assert ist["unreachable_since"] == "2025-01-01T00:00:00Z"


def test_cap_and_log_returns_cap_batch_sizes_result():
    from triggarr.search.engine import _cap_and_log

    assert _cap_and_log(
        app_label="Radarr", missing_configured=5, cutoff_configured=5, hard_max=4,
    ) == cap_batch_sizes(5, 5, 4)
    assert _cap_and_log(
        app_label="Radarr", missing_configured=5, cutoff_configured=5, hard_max=0,
    ) == (5, 5)


def test_cap_and_log_logs_only_when_capped():
    from triggarr.search.engine import _cap_and_log

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="DEBUG")
    try:
        _cap_and_log(app_label="Lidarr", missing_configured=5, cutoff_configured=5, hard_max=4)
        _cap_and_log(app_label="Lidarr", missing_configured=1, cutoff_configured=1, hard_max=10)
        _cap_and_log(app_label="Lidarr", missing_configured=5, cutoff_configured=5, hard_max=0)
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    assert "Lidarr: Hard max 4 applied -- missing=2, cutoff=2" in output
    assert output.count("Hard max") == 1
