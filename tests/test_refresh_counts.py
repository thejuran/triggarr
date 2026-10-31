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
import io
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from loguru import logger

from tests.conftest import make_settings
from triggarr.db import init_db
from triggarr.models.arr import Tag
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
# Malformed-record skip tests (D-02/D-02a): a malformed record no longer
# disconnects the whole instance -- it is skipped and logged per item via
# _screen_queue, matching what the scheduled cycles already do, and the
# surviving good record in the same page is still counted.
# ---------------------------------------------------------------------------


async def test_refresh_sonarr_counts_malformed_cutoff_record_skipped_stays_connected():
    """D-02: a malformed cutoff episode (series=non-dict) is skipped per item via
    _screen_queue before deduplicate_to_seasons ever sees it -- the instance stays
    connected and the good missing episode is still counted."""
    good_ep = _make_sonarr_episode(series_id=10, season_number=1, episode_id=100)
    # Malformed cutoff: series is a non-dict string -- _screen_queue's nested_key
    # check catches this before deduplicate_to_seasons would raise AttributeError.
    malformed_cutoff_ep = {
        "id": 999,
        "seriesId": 1,
        "seasonNumber": 2,
        "monitored": True,
        "airDateUtc": (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "series": "not-a-dict",
    }

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[good_ep])
    client.get_wanted_cutoff = AsyncMock(return_value=[malformed_cutoff_ep])
    client.get_library_count = AsyncMock(return_value=10)

    state = _make_test_state()
    settings = make_settings()
    instance_config = _instance_config()

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        result = await refresh_sonarr_counts(client, state, "Default", instance_config, settings)
    finally:
        logger.remove(handler_id)

    assert result is not None
    ist = state["sonarr"]["Default"]
    assert ist["connected"] is True
    assert ist["unreachable_since"] is None
    assert ist["missing_eligible"] == 1
    assert ist["missing_searchable"] == 1
    assert ist["cutoff_searchable"] == 0
    log_text = sink.getvalue()
    assert "Skipped 1" in log_text
    assert "upgrade-queue" in log_text


async def test_refresh_sonarr_counts_malformed_missing_record_skipped_stays_connected():
    """D-02: a malformed missing episode (series=non-dict) is skipped per item
    alongside a good missing episode in the same queue -- the instance stays
    connected and only the good episode is counted."""
    malformed_missing_ep = {
        "id": 100,
        "seriesId": 10,
        "seasonNumber": 1,
        "monitored": True,
        "airDateUtc": (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        "series": "not-a-dict",
    }
    good_missing_ep = _make_sonarr_episode(series_id=20, season_number=1, episode_id=200)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[malformed_missing_ep, good_missing_ep])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=5)

    state = _make_test_state()
    settings = make_settings()
    instance_config = _instance_config()

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        result = await refresh_sonarr_counts(client, state, "Default", instance_config, settings)
    finally:
        logger.remove(handler_id)

    assert result is not None
    ist = state["sonarr"]["Default"]
    assert ist["connected"] is True
    assert ist["unreachable_since"] is None
    assert ist["missing_eligible"] == 1  # good episode only
    log_text = sink.getvalue()
    assert "Skipped 1" in log_text
    assert "missing-queue" in log_text


@pytest.mark.parametrize("queue", ["missing", "cutoff"])
async def test_refresh_sonarr_counts_unmonitored_tzless_airdate_not_logged_as_malformed(queue):
    """D-02: like run_sonarr_cycle, the refresh drops unmonitored episodes before
    the airDateUtc screen, so an unmonitored episode with a timezone-less air
    date is never logged as a skipped malformed record (86-03 WR-01)."""
    unmonitored_ep = _make_sonarr_episode(series_id=5, episode_id=5, monitored=False)
    unmonitored_ep["airDateUtc"] = "2026-01-01T00:00:00"  # no timezone
    good_ep = _make_sonarr_episode(series_id=6, episode_id=6)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        return_value=[unmonitored_ep, good_ep] if queue == "missing" else [good_ep]
    )
    client.get_wanted_cutoff = AsyncMock(return_value=[unmonitored_ep] if queue == "cutoff" else [])
    client.get_library_count = AsyncMock(return_value=2)

    state = _make_test_state()
    settings = make_settings()
    instance_config = _instance_config()

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        result = await refresh_sonarr_counts(client, state, "Default", instance_config, settings)
    finally:
        logger.remove(handler_id)

    assert result is not None
    ist = state["sonarr"]["Default"]
    assert ist["connected"] is True
    assert ist["missing_eligible"] == 1
    assert "malformed date" not in sink.getvalue()


async def test_refresh_radarr_counts_malformed_tag_record_skipped_stays_connected():
    """D-02a: tag configured + one item with non-iterable tags is skipped per
    item before filter_by_tag ever sees it -- the instance stays connected and
    the good tagged, monitored item is still counted."""
    malformed_item = {"id": 1, "title": "Movie A", "monitored": True, "tags": 5}
    good_item = {"id": 2, "title": "Movie B", "monitored": True, "tags": [42]}
    # Configure a tag so filter_by_tag is actually called
    instance_config = _instance_config(missing_tag="mytag")

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[malformed_item, good_item])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=1)
    # Return a tag that resolves so filter_by_tag runs
    client.get_tags = AsyncMock(return_value=[Tag(id=42, label="mytag")])

    state = _make_test_state()
    settings = make_settings()

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        result = await refresh_radarr_counts(client, state, "Default", instance_config, settings)
    finally:
        logger.remove(handler_id)

    assert result is not None
    ist = state["radarr"]["Default"]
    assert ist["connected"] is True
    assert ist["unreachable_since"] is None
    assert ist["missing_eligible"] == 1
    assert ist["missing_monitored"] == 1  # counts only the good item
    log_text = sink.getvalue()
    assert "Skipped 1" in log_text
    assert "missing-queue" in log_text


async def test_refresh_lidarr_counts_malformed_artist_record_skipped_stays_connected():
    """D-02: tag configured + one album whose artist is not a dict is skipped
    per item before filter_by_tag ever sees it -- the instance stays connected
    and the good tagged, monitored album is still counted."""
    malformed_album = {"id": 1, "title": "Album A", "monitored": True, "artist": "not-a-dict"}
    good_album = {"id": 2, "title": "Album B", "monitored": True, "artist": {"id": 5, "tags": [42]}}
    instance_config = _instance_config(missing_tag="mytag")

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[malformed_album, good_album])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=1)
    client.get_tags = AsyncMock(return_value=[Tag(id=42, label="mytag")])

    state = _make_test_state()
    settings = make_settings()

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        result = await refresh_lidarr_counts(client, state, "Default", instance_config, settings)
    finally:
        logger.remove(handler_id)

    assert result is not None
    ist = state["lidarr"]["Default"]
    assert ist["connected"] is True
    assert ist["unreachable_since"] is None
    assert ist["missing_eligible"] == 1
    log_text = sink.getvalue()
    assert "Skipped 1" in log_text
    assert "missing-queue" in log_text


# ---------------------------------------------------------------------------
# Phase 79-03: never-widen refresh counts for unresolved tags (Radarr, Lidarr)
# ---------------------------------------------------------------------------


async def test_refresh_radarr_counts_unresolved_tag_keeps_last_good_counts():
    """R5: an unresolved missing tag keeps last-good scoped counts; raw count still refreshes."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True},
        {"id": 2, "title": "Movie B", "monitored": True},
        {"id": 3, "title": "Movie C", "monitored": True},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="other")])

    state = _make_test_state()
    ist = state["radarr"]["Default"]
    ist["missing_monitored"] = 9
    ist["missing_eligible"] = 7
    ist["scoped_count_tags"] = {"missing": "gone"}
    instance_config = _instance_config(missing_tag="gone")
    settings = make_settings()

    result = await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    assert ist["missing_count"] == 3  # raw count is pre-filter, always refreshes
    assert ist["missing_monitored"] == 9
    assert ist["missing_eligible"] == 7
    assert ist["tag_warnings"] == [{"tag": "gone", "field": "missing", "reason": "not_found"}]
    assert ist["scoped_count_tags"] == {"missing": "gone"}
    assert ist["unresolved_tag_scopes"] == {"missing": "gone"}


async def test_refresh_radarr_counts_tag_fetch_failure_keeps_last_good_counts():
    """R5: a tag-fetch failure keeps last-good scoped counts; connected stays True."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Movie A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(side_effect=httpx.ConnectError("refused"))

    state = _make_test_state()
    ist = state["radarr"]["Default"]
    ist["missing_monitored"] = 9
    ist["missing_eligible"] = 7
    instance_config = _instance_config(missing_tag="4k")
    settings = make_settings()

    result = await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    assert ist["connected"] is True
    assert ist["missing_monitored"] == 9
    assert ist["missing_eligible"] == 7
    assert ist["tag_warnings"] == [{"tag": "4k", "field": "missing", "reason": "fetch_failed"}]


async def test_refresh_radarr_counts_inactive_queue_unresolved_tag_never_widens():
    """D-04/OQ1: an inactive queue's unresolved tag never widens, warns, or marks evaluated."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Movie A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[])

    state = _make_test_state()
    ist = state["radarr"]["Default"]
    ist["missing_monitored"] = 9
    ist["missing_eligible"] = 7
    instance_config = _instance_config(missing_count=0, missing_tag="gone")
    settings = make_settings()

    result = await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    assert ist["missing_monitored"] == 9
    assert ist["missing_eligible"] == 7
    assert ist["tag_warnings"] == []
    assert ist["unresolved_tag_scopes"] == {"missing": "gone"}


async def test_refresh_radarr_counts_missing_unresolved_cutoff_resolves_refreshes_other_queue():
    """TAGSCOPE-01: a missing-side unresolved tag never blocks the cutoff queue's own refresh."""
    raw_cutoff = [
        {"id": 2, "title": "Movie B", "monitored": True, "tags": [5]},
        {"id": 3, "title": "Movie C", "monitored": True, "tags": []},
    ]
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Movie A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=raw_cutoff)
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="4k")])

    state = _make_test_state()
    ist = state["radarr"]["Default"]
    ist["missing_monitored"] = 9
    ist["missing_eligible"] = 7
    instance_config = _instance_config(missing_tag="gone", cutoff_tag="4k")
    settings = make_settings()

    result = await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    filtered_missing, cutoff_result, cutoff_tag_id = result
    assert filtered_missing == []
    assert cutoff_tag_id == 5
    assert cutoff_result == raw_cutoff  # cutoff's scope resolved -- not emptied
    assert ist["missing_monitored"] == 9
    assert ist["missing_eligible"] == 7


async def test_refresh_radarr_counts_unresolved_tag_never_touches_grade():
    """D-01 refresh invariant: never writes last_cycle/last_run/last_successful_search/last_success."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Movie A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[])

    state = _make_test_state()
    ist = state["radarr"]["Default"]
    ist["last_cycle"] = {"grade": "success"}
    ist["last_run"] = "2026-01-01T00:00:00Z"
    ist["last_successful_search"] = "2026-01-01T00:00:00Z"
    ist["last_success"] = "2026-01-01T00:00:00Z"
    instance_config = _instance_config(missing_tag="gone")
    settings = make_settings()

    await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert ist["last_cycle"] == {"grade": "success"}
    assert ist["last_run"] == "2026-01-01T00:00:00Z"
    assert ist["last_successful_search"] == "2026-01-01T00:00:00Z"
    assert ist["last_success"] == "2026-01-01T00:00:00Z"


async def test_refresh_radarr_counts_resolved_tag_stamps_scoped_counts():
    """D-05 revision 1: a resolved missing tag stamps scoped_count_tags['missing']."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True, "tags": [7]},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[Tag(id=7, label="4k")])

    state = _make_test_state()
    instance_config = _instance_config(missing_tag="4k")
    settings = make_settings()

    result = await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    assert state["radarr"]["Default"]["scoped_count_tags"]["missing"] == "4k"


async def test_refresh_radarr_counts_skipped_missing_survives_cutoff_data_fault(monkeypatch):
    """D-05 revision 2: a cutoff-side data fault never erases a skipped missing queue's counts.

    D-02a note: non-iterable tags are now skipped per item by _screen_queue
    rather than reaching filter_by_tag, so this fault is forced directly on
    filter_by_tag to still exercise the "other unexpected fault" backstop.
    """
    import triggarr.search.engine as engine

    state = _make_test_state()
    ist = state["radarr"]["Default"]
    ist["missing_monitored"] = 9
    ist["missing_eligible"] = 7
    ist["scoped_count_tags"] = {"missing": "gone"}
    instance_config = _instance_config(missing_tag="gone", cutoff_tag="4k")
    settings = make_settings()

    def _boom(*_args, **_kwargs):
        raise TypeError("unexpected shape")

    monkeypatch.setattr(engine, "filter_by_tag", _boom)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Movie A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=[{"id": 2, "title": "Movie B", "monitored": True, "tags": [5]}])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="4k")])

    # Refresh 1: an unexpected fault in the cutoff chain's filter_by_tag (backstop).
    result1 = await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert result1 is None
    assert ist["connected"] is False
    assert ist["missing_monitored"] == 9
    assert ist["missing_eligible"] == 7
    assert ist["scoped_count_tags"] == {"missing": "gone"}
    assert ist["unresolved_tag_scopes"] == {"missing": "gone"}

    # Refresh 2: fault removed; missing tag still unresolved.
    monkeypatch.undo()
    client.get_wanted_cutoff = AsyncMock(return_value=[
        {"id": 2, "title": "Movie B", "monitored": True, "tags": [5]},
    ])

    result2 = await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert result2 is not None
    assert ist["connected"] is True
    assert ist["missing_monitored"] == 9
    assert ist["missing_eligible"] == 7
    assert ist["scoped_count_tags"]["missing"] == "gone"


async def test_refresh_radarr_counts_resolved_missing_still_cleared_on_its_own_data_fault(monkeypatch):
    """D-05 revision 2 regression: a resolved missing queue's own data fault still clears it.

    D-02a note: a non-object record is now skipped per item by _screen_queue
    rather than reaching filter_monitored, so this fault is forced directly on
    filter_monitored to still exercise the "other unexpected fault" backstop.
    """
    import triggarr.search.engine as engine

    state = _make_test_state()
    ist = state["radarr"]["Default"]
    ist["missing_eligible"] = 7
    instance_config = _instance_config(cutoff_tag="gone")
    settings = make_settings()

    def _boom(*_args, **_kwargs):
        raise TypeError("unexpected shape")

    monkeypatch.setattr(engine, "filter_monitored", _boom)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Movie A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[])

    result = await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert result is None
    assert ist["connected"] is False
    assert ist["missing_monitored"] is None
    assert ist["missing_eligible"] is None


async def test_refresh_radarr_counts_tag_resolution_fault_keeps_tagged_queue_counts():
    """D-05 revision 2: a fault during tag resolution itself leaves the tagged queue's counts alone."""
    state = _make_test_state()
    ist = state["radarr"]["Default"]
    ist["missing_monitored"] = 9
    ist["missing_eligible"] = 7
    ist["scoped_count_tags"] = {"missing": "gone"}
    instance_config = _instance_config(missing_tag="gone")
    settings = make_settings()

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Movie A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    # resolve_tag_id accesses .label -- a plain string has none, raising AttributeError
    # *inside* _resolve_tag_scope, before the `scope =` assignment completes.
    client.get_tags = AsyncMock(return_value=["not-a-tag"])

    result = await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert result is None
    assert ist["connected"] is False
    assert ist["missing_monitored"] == 9
    assert ist["missing_eligible"] == 7
    assert ist["scoped_count_tags"] == {"missing": "gone"}


async def test_refresh_lidarr_counts_unresolved_tag_keeps_last_good_counts():
    """R5: an unresolved missing tag keeps last-good scoped counts; raw count still refreshes."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Album A", "monitored": True},
        {"id": 2, "title": "Album B", "monitored": True},
        {"id": 3, "title": "Album C", "monitored": True},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="other")])

    state = _make_test_state()
    ist = state["lidarr"]["Default"]
    ist["missing_monitored"] = 9
    ist["missing_eligible"] = 7
    ist["scoped_count_tags"] = {"missing": "gone"}
    instance_config = _instance_config(missing_tag="gone")
    settings = make_settings()

    result = await refresh_lidarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    assert ist["missing_count"] == 3
    assert ist["missing_monitored"] == 9
    assert ist["missing_eligible"] == 7
    assert ist["tag_warnings"] == [{"tag": "gone", "field": "missing", "reason": "not_found"}]
    assert ist["scoped_count_tags"] == {"missing": "gone"}
    assert ist["unresolved_tag_scopes"] == {"missing": "gone"}


async def test_refresh_lidarr_counts_tag_fetch_failure_keeps_last_good_counts():
    """R5: a tag-fetch failure keeps last-good scoped counts; connected stays True."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Album A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(side_effect=httpx.ConnectError("refused"))

    state = _make_test_state()
    ist = state["lidarr"]["Default"]
    ist["missing_monitored"] = 9
    ist["missing_eligible"] = 7
    instance_config = _instance_config(missing_tag="4k")
    settings = make_settings()

    result = await refresh_lidarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    assert ist["connected"] is True
    assert ist["missing_monitored"] == 9
    assert ist["missing_eligible"] == 7
    assert ist["tag_warnings"] == [{"tag": "4k", "field": "missing", "reason": "fetch_failed"}]


async def test_refresh_lidarr_counts_inactive_queue_unresolved_tag_never_widens():
    """D-04/OQ1: an inactive queue's unresolved tag never widens, warns, or marks evaluated."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Album A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[])

    state = _make_test_state()
    ist = state["lidarr"]["Default"]
    ist["missing_monitored"] = 9
    ist["missing_eligible"] = 7
    instance_config = _instance_config(missing_count=0, missing_tag="gone")
    settings = make_settings()

    result = await refresh_lidarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    assert ist["missing_monitored"] == 9
    assert ist["missing_eligible"] == 7
    assert ist["tag_warnings"] == []
    assert ist["unresolved_tag_scopes"] == {"missing": "gone"}


async def test_refresh_lidarr_counts_unresolved_tag_never_touches_grade():
    """D-01 refresh invariant: never writes last_cycle/last_run/last_successful_search/last_success."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Album A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[])

    state = _make_test_state()
    ist = state["lidarr"]["Default"]
    ist["last_cycle"] = {"grade": "success"}
    ist["last_run"] = "2026-01-01T00:00:00Z"
    ist["last_successful_search"] = "2026-01-01T00:00:00Z"
    ist["last_success"] = "2026-01-01T00:00:00Z"
    instance_config = _instance_config(missing_tag="gone")
    settings = make_settings()

    await refresh_lidarr_counts(client, state, "Default", instance_config, settings)

    assert ist["last_cycle"] == {"grade": "success"}
    assert ist["last_run"] == "2026-01-01T00:00:00Z"
    assert ist["last_successful_search"] == "2026-01-01T00:00:00Z"
    assert ist["last_success"] == "2026-01-01T00:00:00Z"


async def test_refresh_lidarr_counts_resolved_tag_stamps_scoped_counts():
    """D-05 revision 1: a resolved missing tag stamps scoped_count_tags['missing']."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Album A", "monitored": True, "artist": {"tags": [7]}},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[Tag(id=7, label="4k")])

    state = _make_test_state()
    instance_config = _instance_config(missing_tag="4k")
    settings = make_settings()

    result = await refresh_lidarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    assert state["lidarr"]["Default"]["scoped_count_tags"]["missing"] == "4k"


async def test_refresh_lidarr_counts_skipped_missing_survives_cutoff_data_fault(monkeypatch):
    """D-05 revision 2: a cutoff-side data fault never erases a skipped missing queue's counts.

    D-02 note: non-iterable artist.tags is now skipped per item by
    _screen_queue rather than reaching filter_by_tag, so this fault is forced
    directly on filter_by_tag to still exercise the "other unexpected fault"
    backstop.
    """
    import triggarr.search.engine as engine

    state = _make_test_state()
    ist = state["lidarr"]["Default"]
    ist["missing_monitored"] = 9
    ist["missing_eligible"] = 7
    ist["scoped_count_tags"] = {"missing": "gone"}
    instance_config = _instance_config(missing_tag="gone", cutoff_tag="4k")
    settings = make_settings()

    def _boom(*_args, **_kwargs):
        raise TypeError("unexpected shape")

    monkeypatch.setattr(engine, "filter_by_tag", _boom)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Album A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=[
        {"id": 2, "title": "Album B", "monitored": True, "artist": {"tags": [5]}},
    ])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="4k")])

    # Refresh 1: an unexpected fault in the cutoff chain's filter_by_tag (backstop).
    result1 = await refresh_lidarr_counts(client, state, "Default", instance_config, settings)

    assert result1 is None
    assert ist["connected"] is False
    assert ist["missing_monitored"] == 9
    assert ist["missing_eligible"] == 7
    assert ist["scoped_count_tags"] == {"missing": "gone"}
    assert ist["unresolved_tag_scopes"] == {"missing": "gone"}

    # Refresh 2: fault removed; missing tag still unresolved.
    monkeypatch.undo()
    client.get_wanted_cutoff = AsyncMock(return_value=[
        {"id": 2, "title": "Album B", "monitored": True, "artist": {"tags": [5]}},
    ])

    result2 = await refresh_lidarr_counts(client, state, "Default", instance_config, settings)

    assert result2 is not None
    assert ist["connected"] is True
    assert ist["missing_monitored"] == 9
    assert ist["missing_eligible"] == 7
    assert ist["scoped_count_tags"]["missing"] == "gone"


async def test_refresh_lidarr_counts_resolved_missing_still_cleared_on_its_own_data_fault(monkeypatch):
    """D-05 revision 2 regression: a resolved missing queue's own data fault still clears it.

    D-02 note: a non-object record is now skipped per item by _screen_queue
    rather than reaching filter_monitored, so this fault is forced directly on
    filter_monitored to still exercise the "other unexpected fault" backstop.
    """
    import triggarr.search.engine as engine

    state = _make_test_state()
    ist = state["lidarr"]["Default"]
    ist["missing_eligible"] = 7
    instance_config = _instance_config(cutoff_tag="gone")
    settings = make_settings()

    def _boom(*_args, **_kwargs):
        raise TypeError("unexpected shape")

    monkeypatch.setattr(engine, "filter_monitored", _boom)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Album A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[])

    result = await refresh_lidarr_counts(client, state, "Default", instance_config, settings)

    assert result is None
    assert ist["connected"] is False
    assert ist["missing_monitored"] is None
    assert ist["missing_eligible"] is None


async def test_refresh_lidarr_counts_tag_resolution_fault_keeps_tagged_queue_counts():
    """D-05 revision 2: a fault during tag resolution itself leaves the tagged queue's counts alone."""
    state = _make_test_state()
    ist = state["lidarr"]["Default"]
    ist["missing_monitored"] = 9
    ist["missing_eligible"] = 7
    ist["scoped_count_tags"] = {"missing": "gone"}
    instance_config = _instance_config(missing_tag="gone")
    settings = make_settings()

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "Album A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=["not-a-tag"])

    result = await refresh_lidarr_counts(client, state, "Default", instance_config, settings)

    assert result is None
    assert ist["connected"] is False
    assert ist["missing_monitored"] == 9
    assert ist["missing_eligible"] == 7
    assert ist["scoped_count_tags"] == {"missing": "gone"}


# ---------------------------------------------------------------------------
# Phase 79-03: never-widen refresh counts for unresolved tags (Sonarr)
# ---------------------------------------------------------------------------


async def test_refresh_sonarr_counts_unresolved_missing_tag_keeps_missing_counts_refreshes_cutoff():
    """R5: a missing-side unresolved tag keeps missing counts; the cutoff queue still refreshes scoped."""
    missing_ep = _make_sonarr_episode(series_id=1, season_number=1, episode_id=1)
    cutoff_ep_tagged = _make_sonarr_episode(series_id=10, season_number=1, episode_id=100)
    cutoff_ep_tagged["series"]["tags"] = [5]
    cutoff_ep_untagged = _make_sonarr_episode(series_id=20, season_number=1, episode_id=200)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[missing_ep])
    client.get_wanted_cutoff = AsyncMock(return_value=[cutoff_ep_tagged, cutoff_ep_untagged])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[Tag(id=5, label="4k")])

    state = _make_test_state()
    ist = state["sonarr"]["Default"]
    ist["missing_eligible"] = 7
    ist["missing_searchable"] = 3
    ist["cutoff_searchable"] = 2
    ist["scoped_count_tags"] = {"missing": "gone"}
    instance_config = _instance_config(missing_tag="gone", cutoff_tag="4k")
    settings = make_settings()

    result = await refresh_sonarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    assert ist["missing_eligible"] == 7
    assert ist["missing_searchable"] == 3
    assert ist["cutoff_searchable"] == 1  # only the tagged episode's season, refreshed
    assert ist["tag_warnings"] == [{"tag": "gone", "field": "missing", "reason": "not_found"}]
    assert ist["scoped_count_tags"]["cutoff"] == "4k"
    assert ist["scoped_count_tags"]["missing"] == "gone"


async def test_refresh_sonarr_counts_tag_fetch_failure_keeps_all_scoped_counts():
    """R5: a tag-fetch failure keeps all scoped counts; connected stays True."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[_make_sonarr_episode(series_id=1, episode_id=1)])
    client.get_wanted_cutoff = AsyncMock(return_value=[_make_sonarr_episode(series_id=2, episode_id=2)])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(side_effect=httpx.ConnectError("refused"))

    state = _make_test_state()
    ist = state["sonarr"]["Default"]
    ist["missing_eligible"] = 7
    ist["missing_searchable"] = 3
    ist["cutoff_searchable"] = 2
    instance_config = _instance_config(missing_tag="4k", cutoff_tag="hd")
    settings = make_settings()

    result = await refresh_sonarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    assert ist["connected"] is True
    assert ist["missing_eligible"] == 7
    assert ist["missing_searchable"] == 3
    assert ist["cutoff_searchable"] == 2
    assert ist["tag_warnings"] == [
        {"tag": "4k", "field": "missing", "reason": "fetch_failed"},
        {"tag": "hd", "field": "cutoff", "reason": "fetch_failed"},
    ]


async def test_refresh_sonarr_counts_inactive_cutoff_unresolved_never_widens():
    """D-04/OQ1: an inactive cutoff queue's unresolved tag never widens, warns, or marks evaluated."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=[_make_sonarr_episode(series_id=1, episode_id=1)])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[])

    state = _make_test_state()
    ist = state["sonarr"]["Default"]
    ist["cutoff_searchable"] = 2
    instance_config = _instance_config(cutoff_count=0, cutoff_tag="gone")
    settings = make_settings()

    result = await refresh_sonarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    assert ist["cutoff_searchable"] == 2
    assert ist["tag_warnings"] == []
    assert ist["unresolved_tag_scopes"] == {"cutoff": "gone"}


async def test_refresh_sonarr_counts_skipped_missing_survives_cutoff_data_fault(monkeypatch):
    """D-05 revision 2: a cutoff-side data fault never erases a skipped missing queue's counts.

    D-02 note: a malformed "series" record is now skipped per item by
    _screen_queue before deduplicate_to_seasons ever sees it, so this fault is
    forced directly on deduplicate_to_seasons to still exercise the "other
    unexpected fault" backstop.
    """
    import triggarr.search.engine as engine

    state = _make_test_state()
    ist = state["sonarr"]["Default"]
    ist["missing_eligible"] = 7
    ist["missing_searchable"] = 3
    ist["cutoff_searchable"] = 2
    ist["scoped_count_tags"] = {"missing": "gone", "cutoff": "c"}
    instance_config = _instance_config(missing_tag="gone")
    settings = make_settings()

    def _boom(*_args, **_kwargs):
        raise TypeError("unexpected shape")

    monkeypatch.setattr(engine, "deduplicate_to_seasons", _boom)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[_make_sonarr_episode(series_id=5, episode_id=5)])
    client.get_wanted_cutoff = AsyncMock(
        return_value=[_make_sonarr_episode(series_id=1, season_number=2, episode_id=999)]
    )
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[])

    # Refresh 1: an unexpected fault in the cutoff chain's deduplicate_to_seasons (backstop).
    result1 = await refresh_sonarr_counts(client, state, "Default", instance_config, settings)

    assert result1 is None
    assert ist["connected"] is False
    assert ist["missing_eligible"] == 7
    assert ist["missing_searchable"] == 3
    assert ist["scoped_count_tags"]["missing"] == "gone"
    assert ist["cutoff_searchable"] is None  # cutoff's scope resolved -- cleared on its own fault

    # Refresh 2: fault removed; missing tag still unresolved.
    monkeypatch.undo()
    client.get_wanted_cutoff = AsyncMock(return_value=[_make_sonarr_episode(series_id=30, episode_id=300)])

    result2 = await refresh_sonarr_counts(client, state, "Default", instance_config, settings)

    assert result2 is not None
    assert ist["missing_eligible"] == 7
    assert ist["missing_searchable"] == 3
    assert ist["scoped_count_tags"]["missing"] == "gone"
    assert ist["cutoff_searchable"] == 1


async def test_refresh_sonarr_counts_skipped_cutoff_survives_missing_data_fault(monkeypatch):
    """D-05 revision 2: a missing-side data fault never erases a skipped cutoff queue's counts.

    D-02 note: a malformed "series" record is now skipped per item by
    _screen_queue before deduplicate_to_seasons ever sees it, so this fault is
    forced directly on deduplicate_to_seasons to still exercise the "other
    unexpected fault" backstop.
    """
    import triggarr.search.engine as engine

    state = _make_test_state()
    ist = state["sonarr"]["Default"]
    ist["missing_eligible"] = 7
    ist["missing_searchable"] = 3
    ist["cutoff_searchable"] = 2
    ist["scoped_count_tags"] = {"missing": "m", "cutoff": "c"}
    instance_config = _instance_config(cutoff_tag="gone")
    settings = make_settings()

    def _boom(*_args, **_kwargs):
        raise TypeError("unexpected shape")

    monkeypatch.setattr(engine, "deduplicate_to_seasons", _boom)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[_make_sonarr_episode(series_id=9, episode_id=500)])
    client.get_wanted_cutoff = AsyncMock(return_value=[_make_sonarr_episode(series_id=7, episode_id=7)])
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[])

    result = await refresh_sonarr_counts(client, state, "Default", instance_config, settings)

    assert result is None
    assert ist["connected"] is False
    assert ist["cutoff_searchable"] == 2
    assert ist["scoped_count_tags"]["cutoff"] == "c"
    assert ist["missing_eligible"] is None
    assert ist["missing_searchable"] is None


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
# Cutoff filter-chain fault: the active cutoff queue is marked unevaluated, never
# graded Nothing needed searching, and its searched-log progress is preserved.
# ---------------------------------------------------------------------------


def _faulting_cutoff_case(app: str, monkeypatch):
    """Return (run_fn, client, instance_config kwargs) whose cutoff filter chain faults.

    Phase 80: every malformed record shape Radarr and Lidarr can deliver is now a
    per-item skip (_screen_queue), so no data shape reaches their coarse backstop.
    For those two apps the fault is forced in the tag filter (only the cutoff
    queue is tag-scoped here), which still exercises the backstop's grading and
    searched-log preservation. Sonarr's untagged cutoff queue faults in season
    dedup instead, where its old unhashable-seriesId shape used to fault.
    """
    import triggarr.search.engine as engine
    from triggarr.models.arr import Tag

    def _boom(*_args, **_kwargs):
        raise TypeError("unexpected shape")

    client = AsyncMock()
    client.get_library_count = AsyncMock(return_value=10)
    client.get_tags = AsyncMock(return_value=[Tag(id=1, label="cutoff-tag")])
    if app == "radarr":
        client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "M", "monitored": True}])
        client.get_wanted_cutoff = AsyncMock(
            return_value=[{"id": 10, "title": "C", "monitored": True, "tags": [1]}]
        )
        client.search_movies = AsyncMock(return_value=None)
        monkeypatch.setattr(engine, "filter_by_tag", _boom)
        return run_radarr_cycle, client, {"cutoff_tag": "cutoff-tag"}
    if app == "sonarr":
        client.get_wanted_missing = AsyncMock(
            return_value=[_make_sonarr_episode(series_id=5, season_number=1, episode_id=50)]
        )
        # Phase 80: a non-integer seriesId (the list that used to fault
        # season dedup here) is now a per-item malformed skip (_screen_queue),
        # so the fault is forced in season dedup for the cutoff queue only --
        # the same step the old data faulted in; missing still dedups normally.
        real_dedup = engine.deduplicate_to_seasons

        def _dedup_faults_on_cutoff(episodes):
            if any(ep.get("seriesId") == 30 for ep in episodes):
                raise TypeError("unexpected shape")
            return real_dedup(episodes)

        client.get_wanted_cutoff = AsyncMock(
            return_value=[_make_sonarr_episode(series_id=30, season_number=2, episode_id=999)]
        )
        client.search_season = AsyncMock(return_value=None)
        monkeypatch.setattr(engine, "deduplicate_to_seasons", _dedup_faults_on_cutoff)
        return run_sonarr_cycle, client, {}
    client.get_wanted_missing = AsyncMock(return_value=[{"id": 1, "title": "A", "monitored": True}])
    client.get_wanted_cutoff = AsyncMock(
        return_value=[{"id": 10, "title": "C", "monitored": True, "artist": {"tags": [1]}}]
    )
    client.search_albums = AsyncMock(return_value=None)
    monkeypatch.setattr(engine, "filter_by_tag", _boom)
    return run_lidarr_cycle, client, {"cutoff_tag": "cutoff-tag"}


@pytest.mark.parametrize("app", ["radarr", "sonarr", "lidarr"])
async def test_cutoff_fault_cutoff_only_grades_failed_and_preserves_log(tmp_path, app, monkeypatch):
    """A cutoff-only instance whose cutoff filter chain faults grades Failed (unevaluated),
    never nothing_needed, and keeps its cutoff searched-log and pass count."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    run_fn, client, cfg_kwargs = _faulting_cutoff_case(app, monkeypatch)
    state = _make_test_state()
    ist = state[app]["Default"]
    ist["cutoff_searched"] = ["10", "30:2"]
    ist["cutoff_pass"] = 3
    ist["cutoff_searchable"] = 7
    settings = make_settings(search_missing_count=0, search_cutoff_count=5)
    instance_config = _instance_config(missing_count=0, cutoff_count=5, **cfg_kwargs)

    try:
        await run_fn(client, state, "Default", instance_config, settings, db)
    finally:
        await db.close()

    record = ist["last_cycle"]
    assert record["grade"] == "failed"
    assert record["accepted"] == 0
    assert [e["queue"] for e in record["unevaluated"]] == ["cutoff"]
    assert record["unevaluated"][0]["reason"].startswith("malformed data (")
    assert ist["cutoff_searched"] == ["10", "30:2"]
    assert ist["cutoff_pass"] == 3
    assert ist["cutoff_searchable"] == 7
    assert ist.get("last_successful_search") is None


@pytest.mark.parametrize("app", ["radarr", "sonarr", "lidarr"])
async def test_cutoff_fault_with_missing_work_grades_partial(tmp_path, app, monkeypatch):
    """When the missing queue is searched but the active cutoff queue faults, the cycle is
    Partial (not Success), and the cutoff searched-log is untouched."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    run_fn, client, cfg_kwargs = _faulting_cutoff_case(app, monkeypatch)
    state = _make_test_state()
    ist = state[app]["Default"]
    ist["cutoff_searched"] = ["10"]
    settings = make_settings(search_missing_count=5, search_cutoff_count=5)
    instance_config = _instance_config(missing_count=5, cutoff_count=5, **cfg_kwargs)

    try:
        await run_fn(client, state, "Default", instance_config, settings, db)
    finally:
        await db.close()

    record = ist["last_cycle"]
    assert record["accepted"] == 1
    assert record["grade"] == "partial"
    assert [e["queue"] for e in record["unevaluated"]] == ["cutoff"]
    assert ist["cutoff_searched"] == ["10"]


@pytest.mark.parametrize("app", ["radarr", "sonarr", "lidarr"])
async def test_cutoff_fault_on_inactive_cutoff_queue_not_marked_unevaluated(tmp_path, app, monkeypatch):
    """An inactive cutoff queue (count 0) that faults is ignored for grading."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    run_fn, client, cfg_kwargs = _faulting_cutoff_case(app, monkeypatch)
    state = _make_test_state()
    ist = state[app]["Default"]
    settings = make_settings(search_missing_count=5, search_cutoff_count=0)
    instance_config = _instance_config(missing_count=5, cutoff_count=0, **cfg_kwargs)

    try:
        await run_fn(client, state, "Default", instance_config, settings, db)
    finally:
        await db.close()

    record = ist["last_cycle"]
    assert record["unevaluated"] == []
    assert record["grade"] == "success"


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


def test_refresh_counts_route_preserves_grade_timestamps_and_counter(refresh_client, refresh_test_app):
    """D-01 / R2 (78-05): refresh-counts never touches the grade, either timestamp, or the counter.

    Regression guard, expected to pass on first run -- refresh_radarr_counts was
    already proven queue-independent and last_run/last_success-independent in
    Phase 74 (CNT-01..03); this pins the Phase 78 fields (last_cycle,
    last_successful_search) into the same guarantee at the route level.
    """
    state = refresh_test_app.state.triggarr_state
    seeded_last_cycle = {
        "grade": "failed",
        "accepted": 0,
        "failed": 2,
        "malformed_skipped": 0,
        "persistence_failed": 0,
        "failure_reasons": [{"reason": "HTTP 500", "count": 2}],
        "unevaluated": [],
        "eligible": {"missing": 2, "cutoff": 0},
        "fetch_error": None,
        "finished_at": "2026-01-01T00:00:00Z",
    }
    state["radarr"]["Default"]["last_cycle"] = seeded_last_cycle
    state["radarr"]["Default"]["last_run"] = "2026-01-01T00:00:00Z"
    state["radarr"]["Default"]["last_successful_search"] = "2025-12-31T00:00:00Z"
    state["radarr"]["Default"]["last_success"] = "2025-12-30T00:00:00Z"
    refresh_test_app.state.search_failures["radarr_Default_search"] = 2

    with patch(
        "triggarr.web.routes.refresh_radarr_counts",
        new=AsyncMock(return_value=([], [], None)),
    ):
        response = refresh_client.post("/api/refresh-counts/radarr/Default")

    assert response.status_code == 200
    assert state["radarr"]["Default"]["last_cycle"] == seeded_last_cycle
    assert state["radarr"]["Default"]["last_run"] == "2026-01-01T00:00:00Z"
    assert state["radarr"]["Default"]["last_successful_search"] == "2025-12-31T00:00:00Z"
    assert state["radarr"]["Default"]["last_success"] == "2025-12-30T00:00:00Z"
    assert refresh_test_app.state.search_failures["radarr_Default_search"] == 2


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
