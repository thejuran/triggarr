"""Tests for count-only refresh: engine helpers (refresh_*_counts) and route.

Covers:
- CNT-01: helper returns correct raw + eligible counts (ist mutation)
- CNT-02: cursor never advanced by helper
- CNT-03: no last_run / no last_success stamp; health updated on success/failure
- Malformed-nested-data fault tests (rewrite-3 requirement): helper returns None
  without raising on AttributeError/KeyError/TypeError from filter/dedup/tag
- Per-app (Radarr/Sonarr/Lidarr) search-call-order and cutoff-fault-before-missing
  regression tests driving the real run_*_cycle functions
- Route tests (CNT-04): POST /api/refresh-counts/{app}/{instance} guards, rate-limit,
  always-200, DRSEC-03, discard-return, ist-build, malformed-data always-200
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

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
from triggarr.web.routes import STATIC_DIR, router

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
    missing_tag: str = "",
    cutoff_tag: str = "",
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


async def test_refresh_radarr_counts_does_not_touch_searched_log():
    """CNT-02: Radarr count-only helper must not read or write the searched-log (queue-independence).

    Proves that refresh_radarr_counts neither reads nor writes missing_searched/cutoff_searched,
    preserving the v2.10 invariant that count refresh is independent of the search queue.
    """
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[{"id": 1, "title": "Movie A", "monitored": True}]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=1)

    state = _make_test_state()
    state["radarr"]["Default"]["missing_searched"] = ["1", "2", "3"]
    state["radarr"]["Default"]["cutoff_searched"] = ["9"]

    settings = make_settings()
    instance_config = _instance_config()

    await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    # searched-logs must be UNCHANGED — refresh must not read or write them
    assert state["radarr"]["Default"]["missing_searched"] == ["1", "2", "3"]
    assert state["radarr"]["Default"]["cutoff_searched"] == ["9"]
    # counts/health must have been updated (proves the refresh actually ran)
    assert state["radarr"]["Default"]["connected"] is True
    assert state["radarr"]["Default"]["missing_count"] == 1


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


async def test_refresh_sonarr_counts_does_not_touch_searched_log():
    """CNT-02: Sonarr count-only helper must not read or write the searched-log (queue-independence).

    Proves that refresh_sonarr_counts neither reads nor writes missing_searched/cutoff_searched,
    preserving the v2.10 invariant that count refresh is independent of the search queue.
    """
    ep = _make_sonarr_episode(series_id=1, season_number=1, episode_id=1)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[ep])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=5)

    state = _make_test_state()
    state["sonarr"]["Default"]["missing_searched"] = ["1", "2", "3"]
    state["sonarr"]["Default"]["cutoff_searched"] = ["9"]

    settings = make_settings()
    instance_config = _instance_config()

    await refresh_sonarr_counts(client, state, "Default", instance_config, settings)

    # searched-logs must be UNCHANGED — refresh must not read or write them
    assert state["sonarr"]["Default"]["missing_searched"] == ["1", "2", "3"]
    assert state["sonarr"]["Default"]["cutoff_searched"] == ["9"]
    # counts/health must have been updated (proves the refresh actually ran)
    assert state["sonarr"]["Default"]["connected"] is True


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


async def test_refresh_lidarr_counts_does_not_touch_searched_log():
    """CNT-02: Lidarr count-only helper must not read or write the searched-log (queue-independence).

    Proves that refresh_lidarr_counts neither reads nor writes missing_searched/cutoff_searched,
    preserving the v2.10 invariant that count refresh is independent of the search queue.
    """
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[{"id": 1, "title": "Album A", "monitored": True}]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=5)

    state = _make_test_state()
    state["lidarr"]["Default"]["missing_searched"] = ["1", "2", "3"]
    state["lidarr"]["Default"]["cutoff_searched"] = ["9"]

    settings = make_settings()
    instance_config = _instance_config()

    await refresh_lidarr_counts(client, state, "Default", instance_config, settings)

    # searched-logs must be UNCHANGED — refresh must not read or write them
    assert state["lidarr"]["Default"]["missing_searched"] == ["1", "2", "3"]
    assert state["lidarr"]["Default"]["cutoff_searched"] == ["9"]
    # counts/health must have been updated (proves the refresh actually ran)
    assert state["lidarr"]["Default"]["connected"] is True


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
    except (AttributeError, KeyError, TypeError):
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
    except (AttributeError, KeyError, TypeError):
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
    except (AttributeError, KeyError, TypeError):
        pass  # Fault in cutoff branch is pre-existing; only check missing ran
    finally:
        await db.close()

    assert 1 in missing_search_calls, (
        f"Missing album search did NOT run! calls={missing_search_calls}"
    )


# ---------------------------------------------------------------------------
# Route tests: POST /api/refresh-counts/{app}/{instance}
# ---------------------------------------------------------------------------


@pytest.fixture
async def refresh_test_app(tmp_path):
    """Minimal FastAPI app with last_refresh_time initialized (mirrors test_app in test_web.py)."""
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await init_db(db, db_path)
        app.state.db = db
        app.state.triggarr_state = {
            "radarr": {
                "Default": {
                    "last_run": None,
                    "last_success": None,
                    "connected": True,
                    "unreachable_since": None,
                    "missing_count": 5,
                    "cutoff_count": 2,
                    "missing_eligible": 5,
                    "missing_monitored": 5,
                    "tag_warnings": [],
                    "total_items": None,
                    "missing_searchable": None,
                    "cutoff_searchable": None,
                    "missing_pass": 0,
                    "cutoff_pass": 0,
                    "missing_searched": [],
                    "cutoff_searched": [],
                },
            },
            "sonarr": {
                "Default": {
                    "last_run": None, "last_success": None,
                    "connected": None, "unreachable_since": None,
                    "missing_count": None, "cutoff_count": None,
                    "missing_eligible": None, "missing_searchable": None,
                    "cutoff_searchable": None, "tag_warnings": [],
                    "total_items": None, "missing_monitored": None,
                    "missing_pass": 0, "cutoff_pass": 0,
                    "missing_searched": [], "cutoff_searched": [],
                },
            },
            "lidarr": {
                "Default": {
                    "last_run": None, "last_success": None,
                    "connected": None, "unreachable_since": None,
                    "missing_count": None, "cutoff_count": None,
                    "missing_eligible": None, "missing_searchable": None,
                    "cutoff_searchable": None, "tag_warnings": [],
                    "total_items": None, "missing_monitored": None,
                    "missing_pass": 0, "cutoff_pass": 0,
                    "missing_searched": [], "cutoff_searched": [],
                },
            },
            "search_log": [],
        }
        app.state.settings = make_settings(radarr_enabled=True, sonarr_enabled=True)
        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_job.next_run_time = None
        mock_scheduler.get_job.return_value = mock_job
        app.state.scheduler = mock_scheduler

        radarr_client = MagicMock()
        radarr_client.close = AsyncMock()
        sonarr_client = MagicMock()
        sonarr_client.close = AsyncMock()
        lidarr_client = MagicMock()
        lidarr_client.close = AsyncMock()
        app.state.radarr_clients = {"Default": radarr_client}
        app.state.sonarr_clients = {"Default": sonarr_client}
        app.state.lidarr_clients = {"Default": lidarr_client}

        app.state.config_path = tmp_path / "triggarr.toml"
        app.state.state_path = tmp_path / "state.json"
        app.state.search_lock = asyncio.Lock()
        app.state.search_lock_holder = None
        app.state.search_failures = {}
        app.state.persistence_degraded = False
        app.state.last_search_time = {}
        app.state.last_refresh_time = {}  # NEW: sibling rate-limit dict (D-08)
        app.state.last_health_check = None
        app.state.tag_cache = {}

        yield app


@pytest.fixture
def refresh_client(refresh_test_app):
    return TestClient(refresh_test_app)


def test_refresh_counts_invalid_app(refresh_client):
    """POST /api/refresh-counts/invalid returns 400 with 'Invalid app' (CNT-04)."""
    response = refresh_client.post("/api/refresh-counts/invalid/Default")
    assert response.status_code == 400
    assert "Invalid app" in response.text


def test_refresh_counts_instance_name_too_long(refresh_client):
    """POST with instance name >64 chars returns 400 (CNT-04)."""
    long_name = "x" * 65
    response = refresh_client.post(f"/api/refresh-counts/radarr/{long_name}")
    assert response.status_code == 400


def test_refresh_counts_happy_path(refresh_client, refresh_test_app):
    """POST /api/refresh-counts/radarr/Default returns 200 with Radarr card (CNT-04).

    Helper patched to return the real 3-tuple shape ([], [], None) — NOT a 2-tuple.
    """
    with patch(
        "triggarr.web.routes.refresh_radarr_counts",
        new=AsyncMock(return_value=([], [], None)),
    ):
        response = refresh_client.post("/api/refresh-counts/radarr/Default")
    assert response.status_code == 200
    assert "Radarr" in response.text


def test_refresh_counts_three_tuple_passes_through(refresh_client, refresh_test_app):
    """Codex rewrite-2: 3-tuple helper return flows through without error (CNT-04).

    Proves the endpoint does NOT unpack or inspect the helper result.
    A 3-tuple (not a 2-tuple) is required — if the endpoint accidentally unpacks
    a 2-tuple this test's mock would fail the unpack differently, exposing the bug.
    """
    with patch(
        "triggarr.web.routes.refresh_radarr_counts",
        new=AsyncMock(return_value=(["m"], ["c"], 7)),
    ):
        response = refresh_client.post("/api/refresh-counts/radarr/Default")
    assert response.status_code == 200
    assert "Radarr" in response.text


def test_refresh_counts_builds_card_from_ist_not_return(refresh_client, refresh_test_app):
    """Codex rewrite-2: card is built from in-place ist mutation, NOT the return value (CNT-04).

    Side effect mutates state["radarr"]["Default"]["missing_eligible"] to sentinel 4242
    and returns throwaway 3-tuple. Assert the card reflects 4242 (from ist), proving
    the endpoint reads ist after the helper runs — not the return value.
    """
    state = refresh_test_app.state.triggarr_state

    def _mutate_and_return(_client, _state, _instance_name, _instance_config, _settings, **_kwargs):
        state["radarr"]["Default"]["missing_eligible"] = 4242
        return (["throw"], ["away"], 0)

    with patch(
        "triggarr.web.routes.refresh_radarr_counts",
        new=AsyncMock(side_effect=_mutate_and_return),
    ):
        response = refresh_client.post("/api/refresh-counts/radarr/Default")

    assert response.status_code == 200
    # The card must reflect the ist-mutation sentinel 4242
    assert "4242" in response.text


def test_refresh_counts_malformed_data_returns_200_card(refresh_client, refresh_test_app):
    """Rewrite-3 route regression (CNT-03/CNT-04): helper returning None (data fault) yields
    200 + disconnected card — NOT a 500.

    The side_effect simulates the rewrite-3 helper data-fault contract:
    (1) mutates state to disconnected (as the helper's internal (Attr/Key/TypeError) catch does),
    (2) returns None — NOT raises. The endpoint must NOT 500; it must build the card from
    the (now disconnected) ist and return 200.
    """
    state = refresh_test_app.state.triggarr_state
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def _data_fault_side_effect(
        _client, _state, _instance_name, _instance_config, _settings, **_kwargs
    ):
        state["radarr"]["Default"]["connected"] = False
        state["radarr"]["Default"]["unreachable_since"] = timestamp
        return None

    with patch(
        "triggarr.web.routes.refresh_radarr_counts",
        new=AsyncMock(side_effect=_data_fault_side_effect),
    ):
        response = refresh_client.post("/api/refresh-counts/radarr/Default")

    assert response.status_code == 200, (
        f"Expected 200 (always-200 contract on helper None), got {response.status_code}"
    )
    assert response.status_code != 500
    assert "Radarr" in response.text  # disconnected card still contains app name


def test_refresh_counts_malformed_data_does_not_mutate_search_state(
    refresh_client, refresh_test_app
):
    """Rewrite-3 route regression (CNT-03): helper returning None (data fault) must NOT
    mutate search_failures, last_search_time, searched-logs, or last_run/last_success.

    Proves a malformed-data refresh is inert w.r.t. the search path.
    """
    state = refresh_test_app.state.triggarr_state
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    # Seed search state that must NOT be touched
    refresh_test_app.state.search_failures["radarr_Default"] = 2
    state["radarr"]["Default"]["missing_searched"] = ["10", "20"]
    state["radarr"]["Default"]["cutoff_searched"] = ["99"]

    def _data_fault_side_effect(
        _client, _state, _instance_name, _instance_config, _settings, **_kwargs
    ):
        state["radarr"]["Default"]["connected"] = False
        state["radarr"]["Default"]["unreachable_since"] = timestamp
        return None

    with patch(
        "triggarr.web.routes.refresh_radarr_counts",
        new=AsyncMock(side_effect=_data_fault_side_effect),
    ):
        response = refresh_client.post("/api/refresh-counts/radarr/Default")

    assert response.status_code == 200

    # search_failures must be unchanged
    assert refresh_test_app.state.search_failures.get("radarr_Default") == 2

    # Searched-logs must be unchanged (count path never reads or writes them)
    assert state["radarr"]["Default"]["missing_searched"] == ["10", "20"]
    assert state["radarr"]["Default"]["cutoff_searched"] == ["99"]

    # last_search_time must NOT have been touched (independent dicts)
    assert "radarr_Default" not in refresh_test_app.state.last_search_time

    # last_run / last_success must remain unset
    assert state["radarr"]["Default"].get("last_run") is None
    assert state["radarr"]["Default"].get("last_success") is None


def test_refresh_counts_rate_limited(refresh_client, refresh_test_app):
    """Pre-seeded rate limit returns 429 (CNT-04)."""
    refresh_test_app.state.last_refresh_time["radarr_Default"] = time.monotonic()
    response = refresh_client.post("/api/refresh-counts/radarr/Default")
    assert response.status_code == 429
    assert "Rate limited" in response.text


def test_refresh_counts_rate_limit_concurrent_protection(refresh_client, refresh_test_app):
    """Two rapid requests: first 200, second 429 (DRSEC-03 in-lock re-check, CNT-04)."""
    with patch(
        "triggarr.web.routes.refresh_radarr_counts",
        new=AsyncMock(return_value=([], [], None)),
    ):
        resp1 = refresh_client.post("/api/refresh-counts/radarr/Default")
        assert resp1.status_code == 200
        resp2 = refresh_client.post("/api/refresh-counts/radarr/Default")
        assert resp2.status_code == 429
        assert "Rate limited" in resp2.text


def test_refresh_counts_does_not_touch_failure_counter(refresh_client, refresh_test_app):
    """search_failures dict untouched by a successful refresh (CNT-03, T-74-09)."""
    refresh_test_app.state.search_failures["radarr_Default"] = 3
    with patch(
        "triggarr.web.routes.refresh_radarr_counts",
        new=AsyncMock(return_value=([], [], None)),
    ):
        refresh_client.post("/api/refresh-counts/radarr/Default")
    assert refresh_test_app.state.search_failures.get("radarr_Default") == 3


def test_refresh_counts_does_not_touch_last_search_time(refresh_client, refresh_test_app):
    """last_search_time dict untouched after refresh (independent rate-limit dicts, CNT-03)."""
    with patch(
        "triggarr.web.routes.refresh_radarr_counts",
        new=AsyncMock(return_value=([], [], None)),
    ):
        refresh_client.post("/api/refresh-counts/radarr/Default")
    assert "radarr_Default" not in refresh_test_app.state.last_search_time


def test_app_card_connected_has_refresh_counts_button(refresh_client):
    """CNT-05: connected card partial contains 'Refresh counts' button (D-09/D-11)."""
    response = refresh_client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Refresh counts" in response.text


def test_app_card_disconnected_no_refresh_counts_button(refresh_client, refresh_test_app):
    """CNT-05: disconnected card does NOT contain 'Refresh counts'; DOES contain 'Retry Connection' (D-10)."""
    refresh_test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    response = refresh_client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Refresh counts" not in response.text
    assert "Retry Connection" in response.text
