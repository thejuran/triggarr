"""Tests for triggarr.tracking -- tracking orchestrator that resolves search outcomes.

Covers: Radarr grabbed/unresolved, Sonarr grabbed/partial/unresolved,
partial->grabbed upgrade, window-expired terminal, error handling,
empty DB, cutoff queue stat counters, exception sanitization (DRSEC-07),
and per-instance tracking isolation (S06).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import httpx
import pytest

from triggarr.db import init_db, insert_search_entry
from triggarr.models.arr import GrabEvent
from triggarr.search.engine import _sanitize_exc
from triggarr.tracking import run_tracking_check


def _grab(grab_id: int, date: datetime, source: str = "Release.1080p") -> GrabEvent:
    """Helper to build a GrabEvent with ISO date string."""
    return GrabEvent(
        id=grab_id,
        date=date.isoformat().replace("+00:00", "Z"),
        eventType="grabbed",
        sourceTitle=source,
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
        missing_count=missing_count,
        instance_id=instance_id,
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


async def _get_stat(db, app: str, column: str, instance_id: str = "Default") -> int:
    """Read a specific stat value from lifetime_stats for an app+instance."""
    db.row_factory = aiosqlite.Row
    async with db.execute(
        f"SELECT {column} FROM lifetime_stats WHERE app = ? AND instance_id = ?",  # noqa: S608
        (app, instance_id),
    ) as cursor:
        row = await cursor.fetchone()
    db.row_factory = None
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

    counts = await run_tracking_check(db, radarr, "Radarr", "Default", tracking_window_minutes=60)

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

    counts = await run_tracking_check(db, radarr, "Radarr", "Default", tracking_window_minutes=60)

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

    counts = await run_tracking_check(db, radarr, "Radarr", "Default", tracking_window_minutes=60)

    assert await _get_outcome(db, row_id) == "searched"
    assert counts == {"grabbed": 0, "partial": 0, "partial_expired": 0, "unresolved": 0, "errors": 0}
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
        _grab(10, searched_at + timedelta(minutes=5)),
        _grab(11, searched_at + timedelta(minutes=6)),
        _grab(12, searched_at + timedelta(minutes=7)),
    ]

    counts = await run_tracking_check(db, sonarr, "Sonarr", "Default", tracking_window_minutes=60)

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
        _grab(10, searched_at + timedelta(minutes=3)),
        _grab(11, searched_at + timedelta(minutes=4)),
    ]

    counts = await run_tracking_check(db, sonarr, "Sonarr", "Default", tracking_window_minutes=60)

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
        _grab(10, searched_at + timedelta(minutes=5)),
        _grab(11, searched_at + timedelta(minutes=6)),
        _grab(12, searched_at + timedelta(minutes=7)),
    ]

    counts = await run_tracking_check(db, sonarr, "Sonarr", "Default", tracking_window_minutes=60)

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
        _grab(10, searched_at + timedelta(minutes=5)),
        _grab(11, searched_at + timedelta(minutes=6)),
    ]

    counts = await run_tracking_check(db, sonarr, "Sonarr", "Default", tracking_window_minutes=60)

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
        _grab(10, searched_at + timedelta(minutes=5)),
        _grab(11, searched_at + timedelta(minutes=6)),
    ]

    # First tracking cycle -- should apply stats and transition to partial_expired.
    counts1 = await run_tracking_check(db, sonarr, "Sonarr", "Default", tracking_window_minutes=60)
    assert await _get_outcome(db, row_id) == "partial_expired"
    assert await _get_stat(db, "Sonarr", "episodes_found") == 2
    assert counts1["partial_expired"] == 1

    # Second tracking cycle -- entry is partial_expired, excluded from tracking query.
    counts2 = await run_tracking_check(db, sonarr, "Sonarr", "Default", tracking_window_minutes=60)
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

    counts = await run_tracking_check(db, radarr, "Radarr", "Default", tracking_window_minutes=60)

    assert await _get_outcome(db, row_id) == "searched"
    assert counts["errors"] == 1
    assert counts["grabbed"] == 0
    await db.close()


# ---------------------------------------------------------------------------
# Test 9: No trackable entries
# ---------------------------------------------------------------------------


async def test_no_trackable_entries(tmp_path):
    """Fresh DB with no entries returns all-zero counts without calling client."""
    db, _ = await _init_db(tmp_path)

    radarr = AsyncMock()

    counts = await run_tracking_check(db, radarr, "Radarr", "Default", tracking_window_minutes=60)

    assert counts == {"grabbed": 0, "partial": 0, "partial_expired": 0, "unresolved": 0, "errors": 0}
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

    counts = await run_tracking_check(db, radarr, "Radarr", "Default", tracking_window_minutes=60)

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
    sonarr.get_grab_history.return_value = [_grab(50, grab_time)]
    counts = await run_tracking_check(db, sonarr, "Sonarr", "Default", tracking_window_minutes=60)
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
    counts = await run_tracking_check(db, radarr_4k, "Radarr", "4K", tracking_window_minutes=60)

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

    await run_tracking_check(db, radarr, "Radarr", "4K", tracking_window_minutes=60)

    assert await _get_outcome(db, row_id) == "grabbed"
    # 4K instance stats incremented
    assert await _get_stat(db, "Radarr", "movies_found", instance_id="4K") == 1
    # Default instance stats untouched
    assert await _get_stat(db, "Radarr", "movies_found", instance_id="Default") == 0
    await db.close()
