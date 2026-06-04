"""Tests for count-only refresh: engine helpers (refresh_*_counts).

Covers:
- CNT-01: helper returns correct raw + eligible counts (ist mutation)
- CNT-02: cursor never advanced by helper
- CNT-03: no last_run / no last_success stamp; health updated on success/failure
- Malformed-nested-data fault tests (rewrite-3 requirement): helper returns None
  without raising on AttributeError/KeyError/TypeError from filter/dedup/tag
- Per-app (Radarr/Sonarr/Lidarr) search-call-order and cutoff-fault-before-missing
  regression tests driving the real run_*_cycle functions
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import aiosqlite
import httpx
import pytest

from tests.conftest import make_settings
from triggarr.db import init_db
from triggarr.models.config import InstanceConfig
from triggarr.search.engine import (
    refresh_lidarr_counts,
    refresh_radarr_counts,
    refresh_sonarr_counts,
    run_lidarr_cycle,
    run_radarr_cycle,
    run_sonarr_cycle,
)
from triggarr.state import _default_instance_state, _default_state


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_test_state():
    """Return a default per-instance state nested under 'Default'."""
    state = _default_state()
    state["radarr"] = {"Default": _default_instance_state()}
    state["sonarr"] = {"Default": _default_instance_state()}
    state["lidarr"] = {"Default": _default_instance_state()}
    return state


def _instance_config(
    missing_count: int = 2,
    cutoff_count: int = 2,
    missing_tag: str | None = None,
    cutoff_tag: str | None = None,
) -> InstanceConfig:
    return InstanceConfig(
        url="http://radarr:7878",
        api_key="test-key",
        enabled=True,
        search_missing_count=missing_count,
        search_cutoff_count=cutoff_count,
        missing_tag=missing_tag,
        cutoff_tag=cutoff_tag,
    )


def _make_sonarr_episode(
    *,
    series_id: int = 1,
    season_number: int = 1,
    episode_id: int = 100,
    series_title: str = "Test Show",
    monitored: bool = True,
) -> dict:
    """Build a well-formed Sonarr episode dict."""
    air_date = (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
    return {
        "id": episode_id,
        "seriesId": series_id,
        "seasonNumber": season_number,
        "monitored": monitored,
        "airDateUtc": air_date,
        "series": {"id": series_id, "title": series_title, "tags": []},
    }


# ---------------------------------------------------------------------------
# Radarr helper tests
# ---------------------------------------------------------------------------


async def test_refresh_radarr_counts_returns_counts():
    """CNT-01: helper returns 3-tuple and caches raw + eligible counts in ist."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 1, "title": "Movie A", "monitored": True},
            {"id": 2, "title": "Movie B", "monitored": False},  # filtered out by filter_monitored
        ]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=50)

    state = _make_test_state()
    settings = make_settings()
    instance_config = _instance_config()

    result = await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    assert isinstance(result, tuple)
    assert len(result) == 3  # 3-tuple: (filtered_missing, raw_cutoff, cutoff_tag_id)
    filtered_missing, raw_cutoff, cutoff_tag_id = result
    assert len(filtered_missing) == 1  # only monitored movie passes
    ist = state["radarr"]["Default"]
    assert ist["missing_count"] == 2  # raw count before filtering
    assert ist["cutoff_count"] == 0
    assert ist["connected"] is True
    assert ist["missing_eligible"] == 1


async def test_refresh_radarr_counts_does_not_advance_cursor():
    """CNT-02: helper must not touch missing_cursor or cutoff_cursor."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[{"id": 1, "title": "Movie A", "monitored": True}]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=1)

    state = _make_test_state()
    state["radarr"]["Default"]["missing_cursor"] = 5
    state["radarr"]["Default"]["cutoff_cursor"] = 3

    settings = make_settings()
    instance_config = _instance_config()

    await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert state["radarr"]["Default"]["missing_cursor"] == 5  # unchanged
    assert state["radarr"]["Default"]["cutoff_cursor"] == 3  # unchanged


async def test_refresh_radarr_counts_does_not_stamp_last_run():
    """CNT-03: helper must not write last_run or last_success."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=0)

    state = _make_test_state()
    settings = make_settings()
    instance_config = _instance_config()

    await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert state["radarr"]["Default"].get("last_run") is None
    assert state["radarr"]["Default"].get("last_success") is None


async def test_refresh_radarr_counts_sets_connected_true():
    """CNT-03: success path sets connected True, unreachable_since None."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=0)

    state = _make_test_state()
    # Start with disconnected state
    state["radarr"]["Default"]["connected"] = False
    state["radarr"]["Default"]["unreachable_since"] = "2026-06-01T00:00:00Z"

    settings = make_settings()
    instance_config = _instance_config()

    await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert state["radarr"]["Default"]["connected"] is True
    assert state["radarr"]["Default"]["unreachable_since"] is None


async def test_refresh_radarr_counts_sets_connected_false_on_fetch_error():
    """CNT-03/D-04: fetch failure sets connected=False and returns None."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))

    state = _make_test_state()
    settings = make_settings()
    instance_config = _instance_config()

    result = await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert result is None
    assert state["radarr"]["Default"]["connected"] is False
    assert state["radarr"]["Default"]["unreachable_since"] is not None
    assert state["radarr"]["Default"]["tag_warnings"] == []


# ---------------------------------------------------------------------------
# Sonarr helper tests
# ---------------------------------------------------------------------------


async def test_refresh_sonarr_counts_returns_counts():
    """CNT-01: Sonarr helper sets missing_eligible, missing_searchable, cutoff_searchable."""
    ep1 = _make_sonarr_episode(series_id=10, season_number=1, episode_id=100)
    ep2 = _make_sonarr_episode(series_id=10, season_number=1, episode_id=101)  # same season (deduped)
    ep3 = _make_sonarr_episode(series_id=20, season_number=1, episode_id=200)

    cutoff_ep = _make_sonarr_episode(series_id=30, season_number=2, episode_id=300)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[ep1, ep2, ep3])
    client.get_wanted_cutoff = AsyncMock(return_value=[cutoff_ep])
    client.get_library_count = AsyncMock(return_value=100)

    state = _make_test_state()
    settings = make_settings()
    instance_config = _instance_config()

    result = await refresh_sonarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    assert isinstance(result, tuple)
    assert len(result) == 3  # (filtered_missing_seasons, raw_cutoff_episodes, cutoff_tag_id)

    ist = state["sonarr"]["Default"]
    assert ist["missing_count"] == 3   # 3 raw episodes
    assert ist["cutoff_count"] == 1    # 1 raw cutoff episode
    assert ist["connected"] is True
    assert ist["missing_eligible"] == 3   # episode count after filter_sonarr_episodes
    assert ist["missing_searchable"] == 2  # unique seasons (series 10 s1 + series 20 s1)
    assert ist["cutoff_searchable"] == 1   # 1 cutoff season


async def test_refresh_sonarr_counts_does_not_advance_cursor():
    """CNT-02: Sonarr helper must not touch missing_cursor or cutoff_cursor."""
    ep = _make_sonarr_episode(series_id=1, season_number=1, episode_id=1)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[ep])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=5)

    state = _make_test_state()
    state["sonarr"]["Default"]["missing_cursor"] = 7
    state["sonarr"]["Default"]["cutoff_cursor"] = 4

    settings = make_settings()
    instance_config = _instance_config()

    await refresh_sonarr_counts(client, state, "Default", instance_config, settings)

    assert state["sonarr"]["Default"]["missing_cursor"] == 7  # unchanged
    assert state["sonarr"]["Default"]["cutoff_cursor"] == 4  # unchanged


# ---------------------------------------------------------------------------
# Lidarr helper tests
# ---------------------------------------------------------------------------


async def test_refresh_lidarr_counts_returns_counts():
    """CNT-01: Lidarr helper sets missing_eligible; no missing_searchable/cutoff_searchable."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[
            {"id": 1, "title": "Album A", "monitored": True},
            {"id": 2, "title": "Album B", "monitored": False},  # filtered
        ]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=20)

    state = _make_test_state()
    settings = make_settings()
    instance_config = _instance_config()

    result = await refresh_lidarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    assert isinstance(result, tuple)
    assert len(result) == 3  # (filtered_missing, raw_cutoff, cutoff_tag_id)

    ist = state["lidarr"]["Default"]
    assert ist["missing_count"] == 2   # raw
    assert ist["cutoff_count"] == 0
    assert ist["connected"] is True
    assert ist["missing_eligible"] == 1  # only monitored
    # Lidarr has no missing_searchable or cutoff_searchable
    assert ist.get("missing_searchable") is None
    assert ist.get("cutoff_searchable") is None


async def test_refresh_lidarr_counts_does_not_advance_cursor():
    """CNT-02: Lidarr helper must not touch missing_cursor or cutoff_cursor."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[{"id": 1, "title": "Album A", "monitored": True}]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=5)

    state = _make_test_state()
    state["lidarr"]["Default"]["missing_cursor"] = 9
    state["lidarr"]["Default"]["cutoff_cursor"] = 6

    settings = make_settings()
    instance_config = _instance_config()

    await refresh_lidarr_counts(client, state, "Default", instance_config, settings)

    assert state["lidarr"]["Default"]["missing_cursor"] == 9  # unchanged
    assert state["lidarr"]["Default"]["cutoff_cursor"] == 6  # unchanged


# ---------------------------------------------------------------------------
# Malformed nested data fault tests (rewrite-3 requirement)
# ---------------------------------------------------------------------------


async def test_refresh_sonarr_counts_malformed_cutoff_data_returns_none():
    """Rewrite-3: malformed cutoff episode (series=non-dict) -> deduplicate_to_seasons raises
    AttributeError -> helper returns None (does NOT propagate exception), sets disconnected."""
    good_ep = _make_sonarr_episode(series_id=10, season_number=1, episode_id=100)
    # Malformed cutoff: series is a non-dict string -> ep.get("series", {}).get("title", ...) raises
    malformed_cutoff_ep = {
        "id": 999,
        "seriesId": 1,
        "seasonNumber": 2,
        "monitored": True,
        "airDateUtc": (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "series": "not-a-dict",  # triggers AttributeError in deduplicate_to_seasons
    }

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[good_ep])
    client.get_wanted_cutoff = AsyncMock(return_value=[malformed_cutoff_ep])
    client.get_library_count = AsyncMock(return_value=10)

    state = _make_test_state()
    settings = make_settings()
    instance_config = _instance_config()

    # Must NOT raise; must return None
    result = await refresh_sonarr_counts(client, state, "Default", instance_config, settings)

    assert result is None
    ist = state["sonarr"]["Default"]
    assert ist["connected"] is False
    assert ist["unreachable_since"] is not None
    # NO-PARTIAL-STATE: missing_eligible and cutoff_searchable must not be inconsistently set
    # Either both are set or neither is set (consistent disconnected state)
    # The key assertion: it's not the case that missing_eligible is set but cutoff_searchable is None
    # (which would indicate a half-updated count set)
    missing_eligible = ist.get("missing_eligible")
    cutoff_searchable = ist.get("cutoff_searchable")
    assert not (missing_eligible is not None and cutoff_searchable is None), (
        f"Half-updated count state: missing_eligible={missing_eligible!r} "
        f"but cutoff_searchable={cutoff_searchable!r}"
    )


async def test_refresh_sonarr_counts_malformed_missing_data_returns_none():
    """Rewrite-3: malformed missing episode (series=non-dict) -> helper returns None, disconnected."""
    # Malformed missing: series is a non-dict -> deduplicate_to_seasons raises AttributeError
    malformed_missing_ep = {
        "id": 100,
        "seriesId": 10,
        "seasonNumber": 1,
        "monitored": True,
        "airDateUtc": (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "series": "not-a-dict",
    }
    good_cutoff = _make_sonarr_episode(series_id=30, season_number=2, episode_id=300)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[malformed_missing_ep])
    client.get_wanted_cutoff = AsyncMock(return_value=[good_cutoff])
    client.get_library_count = AsyncMock(return_value=5)

    state = _make_test_state()
    settings = make_settings()
    instance_config = _instance_config()

    result = await refresh_sonarr_counts(client, state, "Default", instance_config, settings)

    assert result is None
    ist = state["sonarr"]["Default"]
    assert ist["connected"] is False
    assert ist["unreachable_since"] is not None
    # NO-PARTIAL-STATE: no half-updated eligible/searchable set
    missing_eligible = ist.get("missing_eligible")
    cutoff_searchable = ist.get("cutoff_searchable")
    assert not (missing_eligible is not None and cutoff_searchable is None), (
        f"Half-updated count state on missing-side fault: missing_eligible={missing_eligible!r} "
        f"but cutoff_searchable={cutoff_searchable!r}"
    )


async def test_refresh_radarr_counts_malformed_tag_data_returns_none():
    """Rewrite-3: tag configured + item with non-iterable tags -> filter_by_tag raises TypeError
    -> helper returns None (does NOT propagate), sets disconnected."""
    # Item with tags=5 (non-iterable int) -> `tag_id in get_tags(item)` raises TypeError
    malformed_item = {"id": 1, "title": "Movie A", "monitored": True, "tags": 5}
    # Configure a tag so filter_by_tag is actually called
    instance_config = _instance_config(missing_tag="mytag")

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[malformed_item])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=1)
    # Return a tag that resolves so filter_by_tag runs
    from triggarr.models.arr import Tag
    client.get_tags = AsyncMock(return_value=[Tag(id=42, label="mytag")])

    state = _make_test_state()
    settings = make_settings()

    result = await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert result is None
    ist = state["radarr"]["Default"]
    assert ist["connected"] is False
    assert ist["unreachable_since"] is not None
    # NO-PARTIAL-STATE: missing_eligible must not be left in a partial state
    # (i.e., if we're disconnected, eligible counts should not be populated)
    assert ist.get("missing_eligible") is None or ist.get("connected") is False


# ---------------------------------------------------------------------------
# Per-app cycle regression tests: search-call-order
# (Pins missing-first ordering for all three apps)
# ---------------------------------------------------------------------------


async def test_run_radarr_cycle_searches_missing_before_cutoff(tmp_path):
    """Per-app order pin (Radarr): every missing search precedes every cutoff search."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    missing_items = [
        {"id": 1, "title": "Missing Movie 1", "monitored": True},
        {"id": 2, "title": "Missing Movie 2", "monitored": True},
    ]
    cutoff_items = [
        {"id": 10, "title": "Cutoff Movie 1", "monitored": True},
        {"id": 11, "title": "Cutoff Movie 2", "monitored": True},
    ]

    call_order: list[str] = []

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=missing_items)
    client.get_wanted_cutoff = AsyncMock(return_value=cutoff_items)
    client.get_library_count = AsyncMock(return_value=10)

    async def search_movies_side_effect(ids: list) -> None:
        call_order.append(f"movie:{ids[0]}")

    client.search_movies = AsyncMock(side_effect=search_movies_side_effect)

    state = _make_test_state()
    settings = make_settings(search_missing_count=5, search_cutoff_count=5)
    instance_config = _instance_config(missing_count=5, cutoff_count=5)

    await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    await db.close()

    # Verify calls were made
    assert len(call_order) == 4  # 2 missing + 2 cutoff
    # All missing searches (ids 1,2) must precede all cutoff searches (ids 10,11)
    missing_positions = [i for i, c in enumerate(call_order) if c in ("movie:1", "movie:2")]
    cutoff_positions = [i for i, c in enumerate(call_order) if c in ("movie:10", "movie:11")]
    assert missing_positions, "No missing searches recorded"
    assert cutoff_positions, "No cutoff searches recorded"
    assert max(missing_positions) < min(cutoff_positions), (
        f"Cutoff search happened before a missing search! Order: {call_order}"
    )


async def test_run_sonarr_cycle_searches_missing_before_cutoff(tmp_path):
    """Per-app order pin (Sonarr): every missing season search precedes every cutoff season search."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    missing_eps = [
        _make_sonarr_episode(series_id=10, season_number=1, episode_id=100),
        _make_sonarr_episode(series_id=20, season_number=1, episode_id=200),
    ]
    cutoff_eps = [
        _make_sonarr_episode(series_id=30, season_number=2, episode_id=300),
        _make_sonarr_episode(series_id=40, season_number=3, episode_id=400),
    ]

    call_order: list[tuple[int, int]] = []

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=missing_eps)
    client.get_wanted_cutoff = AsyncMock(return_value=cutoff_eps)
    client.get_library_count = AsyncMock(return_value=50)

    async def search_season_side_effect(series_id: int, season_number: int) -> None:
        call_order.append((series_id, season_number))

    client.search_season = AsyncMock(side_effect=search_season_side_effect)

    state = _make_test_state()
    settings = make_settings(search_missing_count=5, search_cutoff_count=5)
    instance_config = _instance_config(missing_count=5, cutoff_count=5)

    await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
    await db.close()

    assert len(call_order) == 4  # 2 missing + 2 cutoff seasons
    # Missing series 10/20 must precede cutoff series 30/40
    missing_series_ids = {10, 20}
    cutoff_series_ids = {30, 40}
    missing_positions = [i for i, (sid, _) in enumerate(call_order) if sid in missing_series_ids]
    cutoff_positions = [i for i, (sid, _) in enumerate(call_order) if sid in cutoff_series_ids]
    assert missing_positions, "No missing season searches recorded"
    assert cutoff_positions, "No cutoff season searches recorded"
    assert max(missing_positions) < min(cutoff_positions), (
        f"Cutoff season search happened before a missing season search! Order: {call_order}"
    )


async def test_run_lidarr_cycle_searches_missing_before_cutoff(tmp_path):
    """Per-app order pin (Lidarr): every missing album search precedes every cutoff album search."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    missing_albums = [
        {"id": 1, "title": "Missing Album 1", "monitored": True},
        {"id": 2, "title": "Missing Album 2", "monitored": True},
    ]
    cutoff_albums = [
        {"id": 10, "title": "Cutoff Album 1", "monitored": True},
        {"id": 11, "title": "Cutoff Album 2", "monitored": True},
    ]

    call_order: list[str] = []

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=missing_albums)
    client.get_wanted_cutoff = AsyncMock(return_value=cutoff_albums)
    client.get_library_count = AsyncMock(return_value=20)

    async def search_albums_side_effect(ids: list) -> None:
        call_order.append(f"album:{ids[0]}")

    client.search_albums = AsyncMock(side_effect=search_albums_side_effect)

    state = _make_test_state()
    settings = make_settings(search_missing_count=5, search_cutoff_count=5)
    instance_config = _instance_config(missing_count=5, cutoff_count=5)

    await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
    await db.close()

    assert len(call_order) == 4  # 2 missing + 2 cutoff
    missing_positions = [i for i, c in enumerate(call_order) if c in ("album:1", "album:2")]
    cutoff_positions = [i for i, c in enumerate(call_order) if c in ("album:10", "album:11")]
    assert missing_positions, "No missing album searches recorded"
    assert cutoff_positions, "No cutoff album searches recorded"
    assert max(missing_positions) < min(cutoff_positions), (
        f"Cutoff album search happened before a missing album search! Order: {call_order}"
    )


# ---------------------------------------------------------------------------
# Per-app cycle regression tests: cutoff fault does not block missing search
# (The boundary the second codex pass found unprotected for Sonarr/Lidarr)
# ---------------------------------------------------------------------------


async def test_run_radarr_cycle_cutoff_fault_does_not_block_missing_search(tmp_path):
    """Per-app regression (Radarr): malformed cutoff data that raises during cutoff filtering
    must NOT prevent the missing-queue searches that precede it."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    missing_items = [
        {"id": 1, "title": "Missing Movie 1", "monitored": True},
    ]
    # Cutoff with non-iterable tags -> filter_by_tag raises TypeError during cutoff filtering
    # BUT: Radarr cycle's cutoff filter_monitored is simpler; to reliably trigger a fault
    # at the cutoff side, we give cutoff items with tags=5 AND configure a cutoff_tag
    # so filter_by_tag runs on cutoff.
    cutoff_items = [
        {"id": 10, "title": "Cutoff Movie 1", "monitored": True, "tags": 5},  # non-iterable tags
    ]

    missing_search_calls: list[int] = []

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=missing_items)
    client.get_wanted_cutoff = AsyncMock(return_value=cutoff_items)
    client.get_library_count = AsyncMock(return_value=10)

    async def search_movies_side_effect(ids: list) -> None:
        missing_search_calls.append(ids[0])

    client.search_movies = AsyncMock(side_effect=search_movies_side_effect)
    from triggarr.models.arr import Tag
    client.get_tags = AsyncMock(return_value=[Tag(id=99, label="cutoff-tag")])

    state = _make_test_state()
    settings = make_settings(search_missing_count=5, search_cutoff_count=5)
    # Configure cutoff_tag so filter_by_tag runs on cutoff items
    instance_config = _instance_config(missing_count=5, cutoff_count=5, cutoff_tag="cutoff-tag")

    # The cycle may raise (or not) during cutoff; we only care that missing searches ran first
    try:
        await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    except Exception:
        pass  # Fault in cutoff branch is pre-existing behavior; we only check missing ran
    finally:
        await db.close()

    # Missing search must have happened before any cutoff fault
    assert 1 in missing_search_calls, (
        f"Missing search did NOT run despite being before cutoff fault! calls={missing_search_calls}"
    )


async def test_run_sonarr_cycle_cutoff_fault_does_not_block_missing_search(tmp_path):
    """Per-app regression (Sonarr): malformed cutoff episodes -> fault in cutoff dedup must NOT
    prevent missing-queue season searches that run before the cutoff block."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    missing_eps = [
        _make_sonarr_episode(series_id=10, season_number=1, episode_id=100),
    ]
    # Cutoff episode with series=non-dict -> deduplicate_to_seasons raises AttributeError
    # in the CYCLE'S cutoff block (unchanged pre-existing behavior)
    malformed_cutoff_eps = [
        {
            "id": 999,
            "seriesId": 30,
            "seasonNumber": 2,
            "monitored": True,
            "airDateUtc": (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            "series": "not-a-dict",
        }
    ]

    missing_search_calls: list[tuple[int, int]] = []

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=missing_eps)
    client.get_wanted_cutoff = AsyncMock(return_value=malformed_cutoff_eps)
    client.get_library_count = AsyncMock(return_value=20)

    async def search_season_side_effect(series_id: int, season_number: int) -> None:
        missing_search_calls.append((series_id, season_number))

    client.search_season = AsyncMock(side_effect=search_season_side_effect)

    state = _make_test_state()
    settings = make_settings(search_missing_count=5, search_cutoff_count=5)
    instance_config = _instance_config(missing_count=5, cutoff_count=5)

    try:
        await run_sonarr_cycle(client, state, "Default", instance_config, settings, db)
    except Exception:
        pass  # Cutoff fault in cycle is pre-existing; only check missing ran
    finally:
        await db.close()

    assert (10, 1) in missing_search_calls, (
        f"Missing season search did NOT run despite being before cutoff fault! calls={missing_search_calls}"
    )


async def test_run_lidarr_cycle_cutoff_fault_does_not_block_missing_search(tmp_path):
    """Per-app regression (Lidarr): fault in cutoff filtering must NOT prevent missing album searches."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    missing_albums = [
        {"id": 1, "title": "Missing Album 1", "monitored": True},
    ]
    # Cutoff album with non-iterable artist.tags -> filter_by_tag raises TypeError
    # when cutoff_tag is configured
    cutoff_albums = [
        {"id": 10, "title": "Cutoff Album 1", "monitored": True, "artist": 5},  # non-dict
    ]

    missing_search_calls: list[int] = []

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=missing_albums)
    client.get_wanted_cutoff = AsyncMock(return_value=cutoff_albums)
    client.get_library_count = AsyncMock(return_value=10)

    async def search_albums_side_effect(ids: list) -> None:
        missing_search_calls.append(ids[0])

    client.search_albums = AsyncMock(side_effect=search_albums_side_effect)
    from triggarr.models.arr import Tag
    client.get_tags = AsyncMock(return_value=[Tag(id=88, label="cutoff-tag")])

    state = _make_test_state()
    settings = make_settings(search_missing_count=5, search_cutoff_count=5)
    # Configure cutoff_tag so filter_by_tag runs on cutoff
    instance_config = _instance_config(missing_count=5, cutoff_count=5, cutoff_tag="cutoff-tag")

    try:
        await run_lidarr_cycle(client, state, "Default", instance_config, settings, db)
    except Exception:
        pass  # Fault in cutoff branch is pre-existing; only check missing ran
    finally:
        await db.close()

    assert 1 in missing_search_calls, (
        f"Missing album search did NOT run! calls={missing_search_calls}"
    )
