"""Tests for triggarr.tracking -- tracking orchestrator that resolves search outcomes.

Covers: Radarr grabbed/unresolved, Sonarr grabbed/partial/unresolved,
partial->grabbed upgrade, window-expired terminal, error handling,
empty DB, cutoff queue stat counters, exception sanitization (DRSEC-07),
per-instance tracking isolation (S06), and ownership-aware Sonarr
attribution -- exclusion, season match, distinct-episode counting,
accumulation and atomic persistence (ATTR-01, ATTR-02, ATTR-04, ATTR-05).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import httpx
import pytest
from loguru import logger

from triggarr.attribution import ensure_cutover_recorded
from triggarr.db import get_owned_grabs, init_db, insert_search_entry
from triggarr.models.arr import EpisodeSummary, GrabEvent
from triggarr.search.engine import _sanitize_exc
from triggarr.tracking import _lidarr_outcome, run_tracking_check


def _grab(
    grab_id: int,
    date: datetime,
    source: str = "Release.1080p",
    season_number: int | None = 1,
    episode_id: int | None = None,
    series_id: int | None = None,
) -> GrabEvent:
    """Helper to build a GrabEvent with ISO date string and Sonarr episode identity.

    ``episode_id`` defaults to ``grab_id`` when not given. Callers tracking a
    specific Sonarr series should pass ``series_id`` explicitly (matching the
    item_id the test queries) so the grab's identity is trustworthy.
    """
    if episode_id is None:
        episode_id = grab_id
    episode = EpisodeSummary(id=episode_id, seriesId=series_id, seasonNumber=season_number)
    return GrabEvent(
        id=grab_id,
        date=date.isoformat().replace("+00:00", "Z"),
        eventType="grabbed",
        sourceTitle=source,
        episodeId=episode_id,
        seriesId=series_id,
        episode=episode,
    )


async def _init_db(tmp_path):
    """Create a test database with migrations applied, return (db, db_path)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    return db, db_path


async def _insert_entry(
    db,
    *,
    app: str = "Radarr",
    queue_type: str = "missing",
    item_name: str = "Test Item",
    item_id: int = 1,
    outcome: str = "searched",
    missing_count: int | None = None,
    instance_id: str = "Default",
    instance_stable_id: str | None = "sid-test",
    season_number: int | None = 1,
    timestamp: datetime | None = None,
) -> int:
    """Insert a search entry, optionally override timestamp, return its id."""
    await insert_search_entry(
        db,
        app,
        queue_type,
        item_name,
        outcome=outcome,
        item_id=item_id,
        season_number=season_number,
        missing_count=missing_count,
        instance_id=instance_id,
        instance_stable_id=instance_stable_id,
    )
    # Get the last inserted row id.
    async with db.execute("SELECT last_insert_rowid()") as cursor:
        row_id = (await cursor.fetchone())[0]
    # Override timestamp if provided.
    if timestamp is not None:
        ts = timestamp.isoformat().replace("+00:00", "Z")
        await db.execute("UPDATE search_history SET timestamp = ? WHERE id = ?", (ts, row_id))
        await db.commit()
    return row_id


async def _get_outcome(db, row_id: int) -> str:
    """Read the outcome column for a specific search_history row."""
    async with db.execute("SELECT outcome FROM search_history WHERE id = ?", (row_id,)) as cursor:
        row = await cursor.fetchone()
    return row[0]


async def _get_detail(db, row_id: int) -> str:
    """Read the detail column for a specific search_history row."""
    async with db.execute("SELECT detail FROM search_history WHERE id = ?", (row_id,)) as cursor:
        row = await cursor.fetchone()
    return row[0]


async def _get_stat(
    db, app: str, column: str, instance_id: str = "Default", instance_stable_id: str = "sid-test",
) -> int:
    """Read a specific stat value from lifetime_stats for an app+instance+stable-id.

    Relies on ``init_db``'s connection-wide ``row_factory = aiosqlite.Row``
    (never toggles it) so a mid-test call never breaks a later
    ``run_tracking_check`` call on the same shared connection.
    """
    async with db.execute(
        f"SELECT {column} FROM lifetime_stats WHERE app = ? AND instance_id = ? AND instance_stable_id = ?",  # noqa: S608
        (app, instance_id, instance_stable_id),
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        return 0
    return row[column]


# ---------------------------------------------------------------------------
# Test 1: Radarr grabbed
# ---------------------------------------------------------------------------


async def test_radarr_grabbed(tmp_path):
    """Radarr entry with grab within window resolves to 'grabbed' with stat increment."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=30)
    row_id = await _insert_entry(db, app="Radarr", item_id=42, timestamp=searched_at)

    radarr = AsyncMock()
    grab_time = searched_at + timedelta(minutes=10)
    radarr.get_grab_history.return_value = [_grab(100, grab_time, source="Movie.2024.1080p")]

    counts = await run_tracking_check(
        db, radarr, "Radarr", "Default", tracking_window_minutes=60, instance_stable_id="sid-test",
    )

    assert await _get_outcome(db, row_id) == "grabbed"
    assert "Movie.2024.1080p" in await _get_detail(db, row_id)
    assert await _get_stat(db, "Radarr", "movies_found") == 1
    assert counts["grabbed"] == 1
    await db.close()


# ---------------------------------------------------------------------------
# Test 2: Radarr unresolved (window expired)
# ---------------------------------------------------------------------------


async def test_radarr_unresolved_window_expired(tmp_path):
    """Radarr entry past window with no grabs resolves to 'unresolved'."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=120)
    row_id = await _insert_entry(db, app="Radarr", item_id=42, timestamp=searched_at)

    radarr = AsyncMock()
    radarr.get_grab_history.return_value = []

    counts = await run_tracking_check(
        db, radarr, "Radarr", "Default", tracking_window_minutes=60, instance_stable_id="sid-test",
    )

    assert await _get_outcome(db, row_id) == "unresolved"
    assert await _get_stat(db, "Radarr", "movies_found") == 0
    assert counts["unresolved"] == 1
    await db.close()


# ---------------------------------------------------------------------------
# Test 3: Radarr still within window, no grabs
# ---------------------------------------------------------------------------


async def test_radarr_still_within_window_no_grabs(tmp_path):
    """Radarr entry within window and no grabs stays 'searched'."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=5)
    row_id = await _insert_entry(db, app="Radarr", item_id=42, timestamp=searched_at)

    radarr = AsyncMock()
    radarr.get_grab_history.return_value = []

    counts = await run_tracking_check(
        db, radarr, "Radarr", "Default", tracking_window_minutes=60, instance_stable_id="sid-test",
    )

    assert await _get_outcome(db, row_id) == "searched"
    assert counts == {
        "grabbed": 0, "partial": 0, "partial_expired": 0, "unresolved": 0, "errors": 0, "identity_skipped": 0,
    }
    await db.close()


# ---------------------------------------------------------------------------
# Test 4: Sonarr grabbed (all episodes)
# ---------------------------------------------------------------------------


async def test_sonarr_grabbed_all_episodes(tmp_path):
    """Sonarr entry with all expected grabs resolves to 'grabbed' with stat increment."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=30)
    row_id = await _insert_entry(
        db, app="Sonarr", item_id=100, missing_count=3, timestamp=searched_at,
    )

    sonarr = AsyncMock()
    sonarr.get_grab_history.return_value = [
        _grab(10, searched_at + timedelta(minutes=5), series_id=100),
        _grab(11, searched_at + timedelta(minutes=6), series_id=100),
        _grab(12, searched_at + timedelta(minutes=7), series_id=100),
    ]

    counts = await run_tracking_check(
        db, sonarr, "Sonarr", "Default", tracking_window_minutes=60, instance_stable_id="sid-test",
    )

    assert await _get_outcome(db, row_id) == "grabbed"
    assert "3/3" in await _get_detail(db, row_id)
    assert await _get_stat(db, "Sonarr", "episodes_found") == 3
    assert counts["grabbed"] == 1
    await db.close()


# ---------------------------------------------------------------------------
# Test 5: Sonarr partial (some episodes, within window)
# ---------------------------------------------------------------------------


async def test_sonarr_partial_some_episodes(tmp_path):
    """Sonarr entry with some grabs within window transitions to 'partial', no stat increment."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=10)
    row_id = await _insert_entry(
        db, app="Sonarr", item_id=100, missing_count=5, timestamp=searched_at,
    )

    sonarr = AsyncMock()
    sonarr.get_grab_history.return_value = [
        _grab(10, searched_at + timedelta(minutes=3), series_id=100),
        _grab(11, searched_at + timedelta(minutes=4), series_id=100),
    ]

    counts = await run_tracking_check(
        db, sonarr, "Sonarr", "Default", tracking_window_minutes=60, instance_stable_id="sid-test",
    )

    assert await _get_outcome(db, row_id) == "partial"
    assert "2/5" in await _get_detail(db, row_id)
    # No stat increment for non-terminal partial.
    assert await _get_stat(db, "Sonarr", "episodes_found") == 0
    assert counts["partial"] == 1
    await db.close()


# ---------------------------------------------------------------------------
# Test 6: Sonarr partial -> grabbed upgrade
# ---------------------------------------------------------------------------


async def test_sonarr_partial_to_grabbed_upgrade(tmp_path):
    """Sonarr entry with outcome='partial' upgrades to 'grabbed' when all episodes resolve."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=30)
    row_id = await _insert_entry(
        db, app="Sonarr", item_id=100, missing_count=3, outcome="partial", timestamp=searched_at,
    )

    sonarr = AsyncMock()
    sonarr.get_grab_history.return_value = [
        _grab(10, searched_at + timedelta(minutes=5), series_id=100),
        _grab(11, searched_at + timedelta(minutes=6), series_id=100),
        _grab(12, searched_at + timedelta(minutes=7), series_id=100),
    ]

    counts = await run_tracking_check(
        db, sonarr, "Sonarr", "Default", tracking_window_minutes=60, instance_stable_id="sid-test",
    )

    assert await _get_outcome(db, row_id) == "grabbed"
    assert "3/3" in await _get_detail(db, row_id)
    assert await _get_stat(db, "Sonarr", "episodes_found") == 3
    assert counts["grabbed"] == 1
    await db.close()


# ---------------------------------------------------------------------------
# Test 7: Sonarr partial at window expired (terminal state)
# ---------------------------------------------------------------------------


async def test_sonarr_partial_window_expired_terminal(tmp_path):
    """Sonarr partial entry at window expiry is terminal -- stats increment."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=120)
    row_id = await _insert_entry(
        db, app="Sonarr", item_id=100, missing_count=5, outcome="partial", timestamp=searched_at,
    )

    sonarr = AsyncMock()
    sonarr.get_grab_history.return_value = [
        _grab(10, searched_at + timedelta(minutes=5), series_id=100),
        _grab(11, searched_at + timedelta(minutes=6), series_id=100),
    ]

    counts = await run_tracking_check(
        db, sonarr, "Sonarr", "Default", tracking_window_minutes=60, instance_stable_id="sid-test",
    )

    assert await _get_outcome(db, row_id) == "partial_expired"
    detail = await _get_detail(db, row_id)
    assert "2/5" in detail
    assert "window expired" in detail
    assert await _get_stat(db, "Sonarr", "episodes_found") == 2
    assert counts["partial_expired"] == 1
    await db.close()


# ---------------------------------------------------------------------------
# Test 7b: Sonarr partial expired must NOT double-count stats on re-run
# ---------------------------------------------------------------------------


async def test_sonarr_partial_expired_no_double_count(tmp_path):
    """Running tracking twice on an expired partial must not increment stats twice.

    Regression test: prior to the fix, every tracking cycle re-incremented
    stats for expired partial entries because the outcome stayed 'partial'
    and re-entered the tracking query on the next cycle.
    """
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=120)
    row_id = await _insert_entry(
        db, app="Sonarr", item_id=100, missing_count=5, outcome="partial", timestamp=searched_at,
    )

    sonarr = AsyncMock()
    sonarr.get_grab_history.return_value = [
        _grab(10, searched_at + timedelta(minutes=5), series_id=100),
        _grab(11, searched_at + timedelta(minutes=6), series_id=100),
    ]

    # First tracking cycle -- should apply stats and transition to partial_expired.
    counts1 = await run_tracking_check(
        db, sonarr, "Sonarr", "Default", tracking_window_minutes=60, instance_stable_id="sid-test",
    )
    assert await _get_outcome(db, row_id) == "partial_expired"
    assert await _get_stat(db, "Sonarr", "episodes_found") == 2
    assert counts1["partial_expired"] == 1

    # Second tracking cycle -- entry is partial_expired, excluded from tracking query.
    counts2 = await run_tracking_check(
        db, sonarr, "Sonarr", "Default", tracking_window_minutes=60, instance_stable_id="sid-test",
    )
    assert await _get_stat(db, "Sonarr", "episodes_found") == 2  # still 2, not 4
    assert counts2.get("partial_expired", 0) == 0  # no new resolutions
    await db.close()


# ---------------------------------------------------------------------------
# Test 8: Tracking failure is non-fatal
# ---------------------------------------------------------------------------


async def test_tracking_failure_nonfatal(tmp_path):
    """Network error during grab history fetch is non-fatal -- entry stays searched."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=30)
    row_id = await _insert_entry(db, app="Radarr", item_id=42, timestamp=searched_at)

    radarr = AsyncMock()
    radarr.get_grab_history.side_effect = httpx.ConnectError("Connection refused")

    counts = await run_tracking_check(
        db, radarr, "Radarr", "Default", tracking_window_minutes=60, instance_stable_id="sid-test",
    )

    assert await _get_outcome(db, row_id) == "searched"
    assert counts["errors"] == 1
    assert counts["grabbed"] == 0
    await db.close()


# ---------------------------------------------------------------------------
# ROBUST-01: Malformed grab date during tracking does not abort the job
# ---------------------------------------------------------------------------


async def test_run_tracking_check_malformed_grab_date_does_not_abort(tmp_path):
    """A malformed grab date for one item does not abort tracking for other items.

    Item A's only grab has a malformed date -- correlate_grabs must skip it
    individually instead of raising, so item A expires as the existing
    'unresolved' outcome at window end. Item B's valid grab in the same
    tracking run still resolves normally to 'grabbed'.
    """
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=120)  # window (60min) already expired

    row_a = await _insert_entry(db, app="Radarr", item_id=501, timestamp=searched_at)
    row_b = await _insert_entry(db, app="Radarr", item_id=502, timestamp=searched_at)

    def _grab_history(item_id: int) -> list[GrabEvent]:
        if item_id == 501:
            return [GrabEvent(id=1, date="not-a-date", eventType="grabbed", sourceTitle="Bad.Release")]
        return [_grab(2, searched_at + timedelta(minutes=10), source="Good.Release")]

    radarr = AsyncMock()
    radarr.get_grab_history.side_effect = _grab_history

    counts = await run_tracking_check(
        db, radarr, "Radarr", "Default", tracking_window_minutes=60, instance_stable_id="sid-test",
    )

    assert await _get_outcome(db, row_a) == "unresolved"
    assert await _get_outcome(db, row_b) == "grabbed"
    assert counts["unresolved"] == 1
    assert counts["grabbed"] == 1
    assert counts["errors"] == 0
    await db.close()


# ---------------------------------------------------------------------------
# Test 9: No trackable entries
# ---------------------------------------------------------------------------


async def test_no_trackable_entries(tmp_path):
    """Fresh DB with no entries returns all-zero counts without calling client."""
    db, _ = await _init_db(tmp_path)

    radarr = AsyncMock()

    counts = await run_tracking_check(
        db, radarr, "Radarr", "Default", tracking_window_minutes=60, instance_stable_id="sid-test",
    )

    assert counts == {
        "grabbed": 0, "partial": 0, "partial_expired": 0, "unresolved": 0, "errors": 0, "identity_skipped": 0,
    }
    radarr.get_grab_history.assert_not_called()
    await db.close()


# ---------------------------------------------------------------------------
# Test 10: Cutoff queue uses 'updated' counter
# ---------------------------------------------------------------------------


async def test_cutoff_queue_uses_updated_counter(tmp_path):
    """Radarr cutoff entry increments movies_updated (not movies_found)."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=30)
    row_id = await _insert_entry(
        db, app="Radarr", queue_type="cutoff", item_id=42, timestamp=searched_at,
    )

    radarr = AsyncMock()
    radarr.get_grab_history.return_value = [_grab(100, searched_at + timedelta(minutes=10))]

    counts = await run_tracking_check(
        db, radarr, "Radarr", "Default", tracking_window_minutes=60, instance_stable_id="sid-test",
    )

    assert await _get_outcome(db, row_id) == "grabbed"
    assert await _get_stat(db, "Radarr", "movies_updated") == 1
    assert await _get_stat(db, "Radarr", "movies_found") == 0
    assert counts["grabbed"] == 1
    await db.close()


# ---------------------------------------------------------------------------
# DRSEC-07: Exception sanitization tests
# ---------------------------------------------------------------------------


def test_sanitize_exc_http_status_error():
    """HTTPStatusError produces 'HTTP {status_code}' without leaking URL."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_request = MagicMock()
    exc = httpx.HTTPStatusError("Not found", request=mock_request, response=mock_response)
    result = _sanitize_exc(exc)
    assert result == "HTTP 404"
    assert "Not found" not in result  # raw message excluded


def test_sanitize_exc_timeout():
    """TimeoutException produces 'request timeout' without leaking URL."""
    exc = httpx.ReadTimeout("Timed out reading http://internal:7878/api/v3/command")
    result = _sanitize_exc(exc)
    assert result == "request timeout"
    assert "internal" not in result  # URL not leaked


def test_sanitize_exc_generic():
    """Unknown exception produces only the type name, not str(exc)."""
    exc = RuntimeError("/var/lib/triggarr/data/secret.db: permission denied")
    result = _sanitize_exc(exc)
    assert result == "RuntimeError"
    assert "secret" not in result  # path not leaked
    assert "permission" not in result


# ---------------------------------------------------------------------------
# DRQUAL-05: SearchRecord rejects naive datetimes
# ---------------------------------------------------------------------------


def test_search_record_rejects_naive_datetime():
    """SearchRecord raises ValueError when searched_at lacks timezone info."""
    from triggarr.correlation import SearchRecord

    with pytest.raises(ValueError, match="timezone-aware"):
        SearchRecord(history_id=1, item_id=1, searched_at=datetime(2024, 1, 1, 12, 0))


# ---------------------------------------------------------------------------
# DRQUAL-06: missing_count=0 is not conflated with None
# ---------------------------------------------------------------------------


async def test_sonarr_missing_count_zero_vs_none(tmp_path):
    """missing_count=0 is treated as 0 (not conflated with None)."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=30)
    # Insert with explicit missing_count=0
    row_id = await _insert_entry(
        db, app="Sonarr", item_id=200, missing_count=0, timestamp=searched_at,
    )
    sonarr = AsyncMock()
    grab_time = searched_at + timedelta(minutes=5)
    sonarr.get_grab_history.return_value = [_grab(50, grab_time, series_id=200)]
    counts = await run_tracking_check(
        db, sonarr, "Sonarr", "Default", tracking_window_minutes=60, instance_stable_id="sid-test",
    )
    # With expected=0, any grab means grabbed
    assert await _get_outcome(db, row_id) == "grabbed"
    assert counts["grabbed"] == 1
    await db.close()


# ---------------------------------------------------------------------------
# S06: Per-instance tracking isolation
# ---------------------------------------------------------------------------


async def test_per_instance_tracking_isolation(tmp_path):
    """Tracking for one instance does not resolve entries from another instance."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=30)

    # Insert entries for two different Radarr instances
    row_4k = await _insert_entry(
        db, app="Radarr", item_id=42, instance_id="4K", timestamp=searched_at,
    )
    row_1080p = await _insert_entry(
        db, app="Radarr", item_id=99, instance_id="1080p", timestamp=searched_at,
    )

    # Client for 4K instance — returns a grab
    radarr_4k = AsyncMock()
    radarr_4k.get_grab_history.return_value = [
        _grab(100, searched_at + timedelta(minutes=10), source="Movie.4K"),
    ]

    # Run tracking for 4K only
    counts = await run_tracking_check(
        db, radarr_4k, "Radarr", "4K", tracking_window_minutes=60, instance_stable_id="sid-test",
    )

    # 4K entry resolved
    assert await _get_outcome(db, row_4k) == "grabbed"
    assert counts["grabbed"] == 1

    # 1080p entry untouched
    assert await _get_outcome(db, row_1080p) == "searched"
    await db.close()


async def test_per_instance_stats_isolation(tmp_path):
    """Tracking increments stats for the correct instance only."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=30)

    row_id = await _insert_entry(
        db, app="Radarr", item_id=42, instance_id="4K", timestamp=searched_at,
    )

    radarr = AsyncMock()
    radarr.get_grab_history.return_value = [
        _grab(100, searched_at + timedelta(minutes=10)),
    ]

    await run_tracking_check(
        db, radarr, "Radarr", "4K", tracking_window_minutes=60, instance_stable_id="sid-test",
    )

    assert await _get_outcome(db, row_id) == "grabbed"
    # 4K instance stats incremented
    assert await _get_stat(db, "Radarr", "movies_found", instance_id="4K") == 1
    # Default instance stats untouched
    assert await _get_stat(db, "Radarr", "movies_found", instance_id="Default") == 0
    await db.close()


# ---------------------------------------------------------------------------
# Phase 81: Ownership-aware Sonarr tracking (ATTR-01, ATTR-02, ATTR-04, ATTR-05, R1, R2, R6)
# ---------------------------------------------------------------------------


async def test_original_repro_season_one_grab_credits_once(tmp_path):
    """Original bug reproduction: one Season 1 grab credits only the Season 1 search, once."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=10)

    row_s1 = await _insert_entry(
        db, app="Sonarr", item_id=10, missing_count=1, season_number=1,
        instance_stable_id="sid-main", timestamp=searched_at,
    )
    row_s2 = await _insert_entry(
        db, app="Sonarr", item_id=10, missing_count=1, season_number=2,
        instance_stable_id="sid-main", timestamp=searched_at,
    )

    sonarr = AsyncMock()
    grab = _grab(9001, searched_at + timedelta(minutes=2), season_number=1, series_id=10)
    sonarr.get_grab_history.return_value = [grab]

    counts = await run_tracking_check(
        db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )

    assert await _get_outcome(db, row_s1) == "grabbed"
    assert await _get_outcome(db, row_s2) == "searched"
    assert await _get_stat(db, "Sonarr", "episodes_found", instance_id="Main", instance_stable_id="sid-main") == 1
    assert counts["grabbed"] == 1
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=10)
    assert len(owned) == 1

    # Push S2's search further into the past so its window has now expired,
    # while the same grab is returned again on the second check.
    expired_ts = (datetime.now(UTC) - timedelta(minutes=200)).isoformat().replace("+00:00", "Z")
    await db.execute("UPDATE search_history SET timestamp = ? WHERE id = ?", (expired_ts, row_s2))
    await db.commit()

    counts2 = await run_tracking_check(
        db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )
    assert await _get_outcome(db, row_s2) == "unresolved"
    assert await _get_stat(db, "Sonarr", "episodes_found", instance_id="Main", instance_stable_id="sid-main") == 1
    assert counts2["unresolved"] == 1
    owned_after = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=10)
    assert len(owned_after) == 1
    await db.close()


async def test_owned_grab_not_recredited_to_second_search(tmp_path):
    """A grab owned by search A is never credited to a later pending search B for the same series."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=10)

    row_a = await _insert_entry(
        db, app="Sonarr", item_id=20, missing_count=1, season_number=1,
        instance_stable_id="sid-main", timestamp=searched_at,
    )

    sonarr = AsyncMock()
    grab = _grab(5001, searched_at + timedelta(minutes=2), season_number=1, series_id=20)
    sonarr.get_grab_history.return_value = [grab]

    counts = await run_tracking_check(
        db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )
    assert await _get_outcome(db, row_a) == "grabbed"
    assert counts["grabbed"] == 1

    # A second pending S1 search, inserted later, whose window also covers grab G.
    row_b = await _insert_entry(
        db, app="Sonarr", item_id=20, missing_count=1, season_number=1,
        instance_stable_id="sid-main", timestamp=searched_at + timedelta(minutes=1),
    )

    counts2 = await run_tracking_check(
        db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )
    assert await _get_outcome(db, row_b) == "searched"  # not credited
    assert counts2["grabbed"] == 0
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=20)
    assert len(owned) == 1
    await db.close()


async def test_cross_instance_same_grab_id_credited_independently(tmp_path):
    """Identical grab IDs from two different Sonarr instances are credited independently."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=10)

    row_main = await _insert_entry(
        db, app="Sonarr", item_id=30, missing_count=1, season_number=1,
        instance_id="Main", instance_stable_id="sid-a", timestamp=searched_at,
    )
    row_other = await _insert_entry(
        db, app="Sonarr", item_id=30, missing_count=1, season_number=1,
        instance_id="Other", instance_stable_id="sid-b", timestamp=searched_at,
    )

    client_main = AsyncMock()
    client_main.get_grab_history.return_value = [
        _grab(501, searched_at + timedelta(minutes=2), season_number=1, series_id=30),
    ]
    client_other = AsyncMock()
    client_other.get_grab_history.return_value = [
        _grab(501, searched_at + timedelta(minutes=2), season_number=1, series_id=30),
    ]

    counts_main = await run_tracking_check(
        db, client_main, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-a",
    )
    counts_other = await run_tracking_check(
        db, client_other, "Sonarr", "Other", tracking_window_minutes=60, instance_stable_id="sid-b",
    )

    assert await _get_outcome(db, row_main) == "grabbed"
    assert await _get_outcome(db, row_other) == "grabbed"
    assert counts_main["grabbed"] == 1
    assert counts_other["grabbed"] == 1
    owned_a = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-a", series_id=30)
    owned_b = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-b", series_id=30)
    assert len(owned_a) == 1
    assert len(owned_b) == 1
    await db.close()


async def test_rename_does_not_recredit(tmp_path):
    """A rename (same stable ID, new display name) never recredits an already-owned grab."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=10)

    row_a = await _insert_entry(
        db, app="Sonarr", item_id=40, missing_count=1, season_number=1,
        instance_id="Old", instance_stable_id="sid-a", timestamp=searched_at,
    )

    sonarr = AsyncMock()
    grab = _grab(6001, searched_at + timedelta(minutes=2), season_number=1, series_id=40)
    sonarr.get_grab_history.return_value = [grab]

    await run_tracking_check(
        db, sonarr, "Sonarr", "Old", tracking_window_minutes=60, instance_stable_id="sid-a",
    )
    assert await _get_outcome(db, row_a) == "grabbed"

    row_b = await _insert_entry(
        db, app="Sonarr", item_id=40, missing_count=1, season_number=1,
        instance_id="New", instance_stable_id="sid-a", timestamp=searched_at + timedelta(minutes=1),
    )

    counts = await run_tracking_check(
        db, sonarr, "Sonarr", "New", tracking_window_minutes=60, instance_stable_id="sid-a",
    )
    assert await _get_outcome(db, row_b) == "searched"
    assert counts["grabbed"] == 0
    await db.close()


async def test_rename_during_partial_tracking_completes(tmp_path):
    """R1: a search that starts partial under one name completes after a rename, same stable ID."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=5)

    row_id = await _insert_entry(
        db, app="Sonarr", item_id=50, missing_count=3, season_number=1,
        instance_id="Old", instance_stable_id="sid-a", timestamp=searched_at,
    )

    sonarr = AsyncMock()
    sonarr.get_grab_history.return_value = [
        _grab(7001, searched_at + timedelta(minutes=1), season_number=1, series_id=50, episode_id=1),
        _grab(7002, searched_at + timedelta(minutes=1), season_number=1, series_id=50, episode_id=2),
    ]

    counts1 = await run_tracking_check(
        db, sonarr, "Sonarr", "Old", tracking_window_minutes=60, instance_stable_id="sid-a",
    )
    assert await _get_outcome(db, row_id) == "partial"
    assert "2/3" in await _get_detail(db, row_id)
    assert counts1["partial"] == 1
    owned_after_check1 = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-a", series_id=50)
    assert len(owned_after_check1) == 2

    # Rename: same stable ID, new display name. Third episode now appears.
    sonarr.get_grab_history.return_value = [
        _grab(7001, searched_at + timedelta(minutes=1), season_number=1, series_id=50, episode_id=1),
        _grab(7002, searched_at + timedelta(minutes=1), season_number=1, series_id=50, episode_id=2),
        _grab(7003, searched_at + timedelta(minutes=2), season_number=1, series_id=50, episode_id=3),
    ]

    counts2 = await run_tracking_check(
        db, sonarr, "Sonarr", "New", tracking_window_minutes=60, instance_stable_id="sid-a",
    )
    assert await _get_outcome(db, row_id) == "grabbed"
    assert "3/3" in await _get_detail(db, row_id)
    assert counts2["grabbed"] == 1
    owned_after_check2 = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-a", series_id=50)
    assert len(owned_after_check2) == 3

    # The lifetime increment lands on the single row keyed by stable ID
    # "sid-a" -- nothing existed before this check, so it is created now
    # (under "New", the display name in effect at creation time).
    assert await _get_stat(db, "Sonarr", "episodes_found", instance_id="New", instance_stable_id="sid-a") == 3
    async with db.execute(
        "SELECT COUNT(*) FROM lifetime_stats WHERE app = 'Sonarr' AND instance_stable_id = 'sid-a'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row[0] == 1
    await db.close()


async def test_radarr_lifetime_increment_uses_stable_id(tmp_path):
    """S1: a Radarr lifetime increment lands on the (Radarr, stable ID) row."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=30)
    row_id = await _insert_entry(
        db, app="Radarr", item_id=42, instance_id="Default", instance_stable_id="sid-r", timestamp=searched_at,
    )

    radarr = AsyncMock()
    radarr.get_grab_history.return_value = [_grab(100, searched_at + timedelta(minutes=10))]

    counts = await run_tracking_check(
        db, radarr, "Radarr", "Default", tracking_window_minutes=60, instance_stable_id="sid-r",
    )

    assert await _get_outcome(db, row_id) == "grabbed"
    assert await _get_stat(db, "Radarr", "movies_found", instance_stable_id="sid-r") == 1
    assert counts["grabbed"] == 1
    await db.close()


async def test_old_name_reuse_by_different_server_isolated(tmp_path):
    """R1: a different server reusing an old display name never sees or credits that search."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=5)

    row_id = await _insert_entry(
        db, app="Sonarr", item_id=10, missing_count=3, season_number=1, outcome="partial",
        instance_id="Old", instance_stable_id="sid-a", timestamp=searched_at,
    )
    original_detail = "partial: 1/3 episodes"
    await db.execute("UPDATE search_history SET detail = ? WHERE id = ?", (original_detail, row_id))
    await db.commit()
    # A pre-existing owned grab for the sid-a search.
    await db.execute(
        "INSERT INTO grab_ownership "
        "(app, instance_stable_id, grab_id, history_id, series_id, season_number, episode_id, credited_at) "
        "VALUES ('Sonarr', 'sid-a', 9999, ?, 10, 1, 1, '2026-01-01T00:00:00Z')",
        (row_id,),
    )
    await db.commit()

    new_server_client = AsyncMock()
    new_server_client.get_grab_history.return_value = [
        _grab(8001, searched_at + timedelta(minutes=1), season_number=1, series_id=10, episode_id=2),
        _grab(8002, searched_at + timedelta(minutes=1), season_number=1, series_id=10, episode_id=3),
    ]

    counts = await run_tracking_check(
        db, new_server_client, "Sonarr", "Old", tracking_window_minutes=60, instance_stable_id="sid-c",
    )

    new_server_client.get_grab_history.assert_not_called()
    assert await _get_outcome(db, row_id) == "partial"
    assert await _get_detail(db, row_id) == original_detail
    owned_c = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-c", series_id=10)
    assert len(owned_c) == 0
    assert counts["grabbed"] == 0
    assert counts["partial"] == 0
    await db.close()


async def test_missing_episode_ids_do_not_inflate_count(tmp_path):
    """R2: grabs with no episode id are never credited and are counted as identity_skipped."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=5)
    row_id = await _insert_entry(
        db, app="Sonarr", item_id=60, missing_count=2, season_number=1,
        instance_stable_id="sid-main", timestamp=searched_at,
    )

    grab1 = GrabEvent(
        id=9101, date=(searched_at + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        eventType="grabbed", sourceTitle="Ep.Release",
        episodeId=None, seriesId=60, episode=EpisodeSummary(id=None, seriesId=60, seasonNumber=1),
    )
    grab2 = GrabEvent(
        id=9102, date=(searched_at + timedelta(minutes=2)).isoformat().replace("+00:00", "Z"),
        eventType="grabbed", sourceTitle="Ep.Release",
        episodeId=None, seriesId=60, episode=EpisodeSummary(id=None, seriesId=60, seasonNumber=1),
    )
    sonarr = AsyncMock()
    sonarr.get_grab_history.return_value = [grab1, grab2]

    counts = await run_tracking_check(
        db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )

    assert await _get_outcome(db, row_id) == "searched"
    assert counts["identity_skipped"] == 2
    assert counts["grabbed"] == 0
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=60)
    assert len(owned) == 0
    await db.close()


async def test_conflicting_or_mismatched_identity_skipped(tmp_path):
    """R2, R6: grabs with conflicting or mismatched identity are skipped and counted, never credited."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=5)
    row_id = await _insert_entry(
        db, app="Sonarr", item_id=70, missing_count=3, season_number=1,
        instance_stable_id="sid-main", timestamp=searched_at,
    )

    conflicting_episode_id = GrabEvent(
        id=9201, date=(searched_at + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        eventType="grabbed", sourceTitle="Ep.Release",
        episodeId=1, seriesId=70, episode=EpisodeSummary(id=2, seriesId=70, seasonNumber=1),
    )
    series_mismatch_top = GrabEvent(
        id=9202, date=(searched_at + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        eventType="grabbed", sourceTitle="Ep.Release",
        episodeId=3, seriesId=999, episode=EpisodeSummary(id=3, seriesId=70, seasonNumber=1),
    )
    no_series_id = GrabEvent(
        id=9203, date=(searched_at + timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        eventType="grabbed", sourceTitle="Ep.Release",
        episodeId=4, seriesId=None, episode=EpisodeSummary(id=4, seriesId=None, seasonNumber=1),
    )
    sonarr = AsyncMock()
    sonarr.get_grab_history.return_value = [conflicting_episode_id, series_mismatch_top, no_series_id]

    counts = await run_tracking_check(
        db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )

    assert counts["identity_skipped"] == 3
    assert counts["grabbed"] == 0
    assert await _get_outcome(db, row_id) == "searched"
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=70)
    assert len(owned) == 0
    await db.close()


async def test_pruned_owner_does_not_recredit(tmp_path):
    """A credited search's history row being pruned never allows a later search to recredit its grab."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=10)

    row_a = await _insert_entry(
        db, app="Sonarr", item_id=80, missing_count=1, season_number=1,
        instance_stable_id="sid-main", timestamp=searched_at,
    )
    sonarr = AsyncMock()
    grab = _grab(8301, searched_at + timedelta(minutes=2), season_number=1, series_id=80)
    sonarr.get_grab_history.return_value = [grab]

    await run_tracking_check(
        db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )
    assert await _get_outcome(db, row_a) == "grabbed"

    # Prune A's row (resolved rows are trimmed independently of ownership).
    await db.execute("DELETE FROM search_history WHERE id = ?", (row_a,))
    await db.commit()

    row_b = await _insert_entry(
        db, app="Sonarr", item_id=80, missing_count=1, season_number=1,
        instance_stable_id="sid-main", timestamp=searched_at + timedelta(minutes=1),
    )

    counts = await run_tracking_check(
        db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )

    assert await _get_outcome(db, row_b) == "searched"
    assert counts["grabbed"] == 0
    await db.close()


async def test_restart_does_not_recredit(tmp_path):
    """Closing and reopening the database never recredits a grab already owned."""
    db, db_path = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=10)

    row_a = await _insert_entry(
        db, app="Sonarr", item_id=90, missing_count=1, season_number=1,
        instance_stable_id="sid-main", timestamp=searched_at,
    )
    sonarr = AsyncMock()
    grab = _grab(8401, searched_at + timedelta(minutes=2), season_number=1, series_id=90)
    sonarr.get_grab_history.return_value = [grab]

    await run_tracking_check(
        db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )
    assert await _get_outcome(db, row_a) == "grabbed"
    await db.close()

    # Restart: reopen the same database file (mirrors production lifespan,
    # which always re-runs init_db on startup -- idempotent, and sets
    # row_factory on the new connection).
    db2 = await aiosqlite.connect(db_path)
    await init_db(db2, db_path)
    row_b = await _insert_entry(
        db2, app="Sonarr", item_id=90, missing_count=1, season_number=1,
        instance_stable_id="sid-main", timestamp=searched_at + timedelta(minutes=1),
    )

    counts = await run_tracking_check(
        db2, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )

    assert await _get_outcome(db2, row_b) == "searched"
    assert counts["grabbed"] == 0
    await db2.close()


async def test_partial_accumulates_to_complete(tmp_path):
    """ATTR-04: distinct-episode progress accumulates across checks until the search completes."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=5)
    row_id = await _insert_entry(
        db, app="Sonarr", item_id=95, missing_count=4, season_number=1,
        instance_stable_id="sid-main", timestamp=searched_at,
    )

    sonarr = AsyncMock()
    sonarr.get_grab_history.return_value = [
        _grab(8501, searched_at + timedelta(minutes=1), season_number=1, series_id=95, episode_id=1),
        _grab(8502, searched_at + timedelta(minutes=1), season_number=1, series_id=95, episode_id=2),
    ]
    counts1 = await run_tracking_check(
        db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )
    assert await _get_outcome(db, row_id) == "partial"
    assert "2/4" in await _get_detail(db, row_id)
    assert counts1["partial"] == 1
    owned1 = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=95)
    assert len(owned1) == 2

    sonarr.get_grab_history.return_value = [
        _grab(8501, searched_at + timedelta(minutes=1), season_number=1, series_id=95, episode_id=1),
        _grab(8502, searched_at + timedelta(minutes=1), season_number=1, series_id=95, episode_id=2),
        _grab(8503, searched_at + timedelta(minutes=2), season_number=1, series_id=95, episode_id=3),
    ]
    counts2 = await run_tracking_check(
        db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )
    assert await _get_outcome(db, row_id) == "partial"
    assert await _get_detail(db, row_id) == "partial: 3/4 episodes"
    assert counts2.get("partial", 0) == 0  # progress persisted silently, not re-counted
    assert counts2.get("grabbed", 0) == 0
    owned2 = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=95)
    assert len(owned2) == 3
    assert await _get_stat(db, "Sonarr", "episodes_found", instance_stable_id="sid-main") == 0

    sonarr.get_grab_history.return_value = [
        _grab(8501, searched_at + timedelta(minutes=1), season_number=1, series_id=95, episode_id=1),
        _grab(8502, searched_at + timedelta(minutes=1), season_number=1, series_id=95, episode_id=2),
        _grab(8503, searched_at + timedelta(minutes=2), season_number=1, series_id=95, episode_id=3),
        _grab(8504, searched_at + timedelta(minutes=3), season_number=1, series_id=95, episode_id=4),
    ]
    counts3 = await run_tracking_check(
        db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )
    assert await _get_outcome(db, row_id) == "grabbed"
    assert counts3["grabbed"] == 1
    assert await _get_stat(db, "Sonarr", "episodes_found", instance_id="Main", instance_stable_id="sid-main") == 4
    owned3 = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=95)
    assert len(owned3) == 4
    await db.close()


async def test_season_pack_repeat_grab_counts_episode_once(tmp_path):
    """A repeated grab of the same episode (season-pack re-grab) counts once, but both grabs are owned."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=5)
    row_id = await _insert_entry(
        db, app="Sonarr", item_id=96, missing_count=3, season_number=1,
        instance_stable_id="sid-main", timestamp=searched_at,
    )

    sonarr = AsyncMock()
    sonarr.get_grab_history.return_value = [
        _grab(8601, searched_at + timedelta(minutes=1), season_number=1, series_id=96, episode_id=1),
        _grab(8602, searched_at + timedelta(minutes=1), season_number=1, series_id=96, episode_id=2),
        _grab(8603, searched_at + timedelta(minutes=1), season_number=1, series_id=96, episode_id=3),
        _grab(8604, searched_at + timedelta(minutes=2), season_number=1, series_id=96, episode_id=3),
    ]

    counts = await run_tracking_check(
        db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )

    assert await _get_outcome(db, row_id) == "grabbed"
    assert "3/3" in await _get_detail(db, row_id)
    assert counts["grabbed"] == 1
    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-main", series_id=96)
    assert len(owned) == 4
    assert {o.grab_id for o in owned} == {8601, 8602, 8603, 8604}
    await db.close()


async def test_legacy_pending_not_tracked(tmp_path):
    """A pre-cutover pending Sonarr row is frozen and never picked up for tracking."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=5)
    row_id = await _insert_entry(
        db, app="Sonarr", item_id=97, missing_count=1, season_number=1,
        instance_stable_id="sid-main", timestamp=searched_at,
    )
    await ensure_cutover_recorded(db, {"Main": "sid-main"})

    sonarr = AsyncMock()
    sonarr.get_grab_history.return_value = [
        _grab(8701, searched_at + timedelta(minutes=1), season_number=1, series_id=97),
    ]

    counts = await run_tracking_check(
        db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )

    sonarr.get_grab_history.assert_not_called()
    assert await _get_outcome(db, row_id) == "searched"
    assert counts["grabbed"] == 0
    assert counts["errors"] == 0
    await db.close()


async def test_sonarr_empty_stable_id_skips_tracking(tmp_path):
    """An empty stable ID refuses to track Sonarr entries rather than risk sharing ownership."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=5)
    await _insert_entry(
        db, app="Sonarr", item_id=98, missing_count=1, season_number=1,
        instance_id="Main", instance_stable_id=None, timestamp=searched_at,
    )
    await _insert_entry(
        db, app="Sonarr", item_id=99, missing_count=1, season_number=1,
        instance_id="Main", instance_stable_id=None, timestamp=searched_at,
    )

    sonarr = AsyncMock()

    captured: list[str] = []
    sink_id = logger.add(lambda m: captured.append(str(m)), level="ERROR")
    try:
        counts = await run_tracking_check(
            db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="",
        )
    finally:
        logger.remove(sink_id)

    sonarr.get_grab_history.assert_not_called()
    assert counts["errors"] == 2
    assert counts["grabbed"] == 0
    assert len(captured) == 1
    await db.close()


async def test_ownership_integrity_error_is_nonfatal(tmp_path):
    """An IntegrityError on one entry's ownership write is caught and counted, others still resolve."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=5)

    row_a = await _insert_entry(
        db, app="Sonarr", item_id=101, missing_count=1, season_number=1,
        instance_stable_id="sid-main", timestamp=searched_at,
    )
    row_b = await _insert_entry(
        db, app="Sonarr", item_id=102, missing_count=1, season_number=1,
        instance_stable_id="sid-main", timestamp=searched_at,
    )

    def _history(series_id: int) -> list[GrabEvent]:
        # Both series' history happens to carry the same grab id -- a
        # same-instance ownership collision that candidate exclusion
        # (scoped per series) cannot see coming.
        return [_grab(9301, searched_at + timedelta(minutes=1), season_number=1, series_id=series_id)]

    sonarr = AsyncMock()
    sonarr.get_grab_history.side_effect = _history

    counts = await run_tracking_check(
        db, sonarr, "Sonarr", "Main", tracking_window_minutes=60, instance_stable_id="sid-main",
    )

    assert await _get_outcome(db, row_a) == "grabbed"
    assert await _get_outcome(db, row_b) == "searched"
    assert counts["grabbed"] == 1
    assert counts["errors"] == 1
    await db.close()


# ---------------------------------------------------------------------------
# Lidarr outcome logic
# ---------------------------------------------------------------------------


def test_lidarr_grabbed_missing():
    """Lidarr missing grab returns albums_found stat."""
    grab = GrabEvent(id=1, sourceTitle="Artist - Album [FLAC]", date="2026-01-01T00:00:00Z", eventType="grabbed")
    outcome, detail, stats = _lidarr_outcome("missing", 1, [grab], window_expired=False)
    assert outcome == "grabbed"
    assert "Artist - Album [FLAC]" in detail
    assert stats == {"albums_found": 1}


def test_lidarr_grabbed_cutoff():
    """Lidarr cutoff grab returns albums_updated stat."""
    grab = GrabEvent(id=2, sourceTitle="Upgrade Release", date="2026-01-01T00:00:00Z", eventType="grabbed")
    outcome, detail, stats = _lidarr_outcome("cutoff", 1, [grab], window_expired=False)
    assert outcome == "grabbed"
    assert stats == {"albums_updated": 1}


def test_lidarr_unresolved_window_expired():
    """Lidarr returns unresolved when window expires with no grabs."""
    outcome, detail, stats = _lidarr_outcome("missing", 0, [], window_expired=True)
    assert outcome == "unresolved"
    assert "no grabs" in detail
    assert stats is None


def test_lidarr_within_window_no_grabs():
    """Lidarr returns None (keep waiting) within tracking window."""
    outcome, detail, stats = _lidarr_outcome("missing", 0, [], window_expired=False)
    assert outcome is None
    assert detail == ""
    assert stats is None


async def test_lidarr_tracking_integration(tmp_path):
    """Full integration: Lidarr entry gets resolved via run_tracking_check."""
    db, _ = await _init_db(tmp_path)

    # Insert a Lidarr search entry that's within tracking window
    await _insert_entry(
        db,
        app="Lidarr",
        queue_type="missing",
        item_name="Test Album",
        item_id=999,
        outcome="searched",
        instance_id="Default",
        timestamp=datetime.now(UTC) - timedelta(minutes=5),
    )

    client = AsyncMock()
    client.get_grab_history = AsyncMock(return_value=[
        GrabEvent(
            id=1, sourceTitle="Artist - Test Album [FLAC]",
            date=datetime.now(UTC).isoformat(), eventType="grabbed",
        ),
    ])

    result = await run_tracking_check(
        db, client, "Lidarr", "Default", tracking_window_minutes=30, instance_stable_id="sid-test",
    )

    assert result["grabbed"] == 1
    assert result["errors"] == 0

    # Verify the entry was updated
    async with db.execute("SELECT outcome FROM search_history WHERE item_id = 999") as cursor:
        row = await cursor.fetchone()
    assert row[0] == "grabbed"

    await db.close()
