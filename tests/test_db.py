"""Tests for SQLite search history persistence module.

Covers: database init, insert/retrieve, limit, pruning, migration system,
tracking columns, lifetime_stats, backfill migration, and shared-connection
signatures.
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from fetcharr.db import (
    _migrate_v1,
    get_recent_searches,
    get_schema_version,
    get_search_history,
    get_trackable_entries,
    init_db,
    insert_search_entry,
    migrate_from_state,
    update_outcome_and_stats,
)


async def _init_test_db(tmp_path):
    """Create a test database with migrations applied, return (db, db_path)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    return db, db_path


# ---------------------------------------------------------------------------
# Basic init and CRUD tests
# ---------------------------------------------------------------------------


async def test_init_db_creates_table(tmp_path):
    """init_db creates the search_history table and index."""
    db, db_path = await _init_test_db(tmp_path)
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='search_history'"
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "search_history"
    await db.close()


async def test_insert_and_retrieve(tmp_path):
    """Inserted entries are retrieved in newest-first order with correct keys."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Radarr", "missing", "Movie A")
    await insert_search_entry(db, "Sonarr", "cutoff", "Show B")
    await insert_search_entry(db, "Radarr", "missing", "Movie C")

    results = await get_recent_searches(db)
    assert len(results) == 3
    # Newest first (by id DESC)
    assert results[0]["name"] == "Movie C"
    assert results[1]["name"] == "Show B"
    assert results[2]["name"] == "Movie A"

    # Verify all expected keys present
    for entry in results:
        assert "name" in entry
        assert "timestamp" in entry
        assert "app" in entry
        assert "queue_type" in entry

    await db.close()


async def test_get_recent_searches_limit(tmp_path):
    """get_recent_searches respects the limit parameter."""
    db, db_path = await _init_test_db(tmp_path)

    for i in range(10):
        await insert_search_entry(db, "Radarr", "missing", f"Movie {i}")

    results = await get_recent_searches(db, limit=3)
    assert len(results) == 3
    # Should be the 3 most recent
    assert results[0]["name"] == "Movie 9"
    assert results[1]["name"] == "Movie 8"
    assert results[2]["name"] == "Movie 7"
    await db.close()


async def test_insert_prunes_old_entries(tmp_path):
    """Inserting beyond max_rows resolved entries prunes the oldest resolved rows."""
    db, db_path = await _init_test_db(tmp_path)

    # Insert 510 entries with outcome='failed' (resolved, so prunable)
    for i in range(510):
        await insert_search_entry(db, "Radarr", "missing", f"Movie {i}", outcome="failed", max_rows=500)

    async with db.execute("SELECT COUNT(*) FROM search_history") as cursor:
        row = await cursor.fetchone()
    assert row[0] == 500
    await db.close()


async def test_migrate_from_state(tmp_path):
    """migrate_from_state inserts entries from state.json format into SQLite."""
    db, db_path = await _init_test_db(tmp_path)

    search_log = [
        {"name": "Movie A", "timestamp": "2026-01-15T10:30:00Z", "app": "Radarr", "queue_type": "missing"},
        {"name": "Show B", "timestamp": "2026-01-15T10:31:00Z", "app": "Sonarr", "queue_type": "cutoff"},
    ]

    count = await migrate_from_state(db, search_log)
    assert count == 2

    results = await get_recent_searches(db)
    assert len(results) == 2
    names = {r["name"] for r in results}
    assert names == {"Movie A", "Show B"}
    await db.close()


async def test_migrate_empty_log(tmp_path):
    """migrate_from_state with empty list returns 0 and inserts nothing."""
    db, db_path = await _init_test_db(tmp_path)

    count = await migrate_from_state(db, [])
    assert count == 0

    results = await get_recent_searches(db)
    assert results == []
    await db.close()


async def test_get_recent_searches_empty_db(tmp_path):
    """get_recent_searches on empty database returns empty list."""
    db, db_path = await _init_test_db(tmp_path)

    results = await get_recent_searches(db)
    assert results == []
    await db.close()


# ---------------------------------------------------------------------------
# Outcome / detail column tests
# ---------------------------------------------------------------------------


async def test_insert_with_outcome_and_detail(tmp_path):
    """Insert an entry with explicit outcome and detail, verify retrieval."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(
        db, "Radarr", "missing", "Movie X",
        outcome="failed", detail="Connection refused",
    )

    results = await get_recent_searches(db)
    assert len(results) == 1
    assert results[0]["outcome"] == "failed"
    assert results[0]["detail"] == "Connection refused"
    await db.close()


async def test_insert_default_outcome(tmp_path):
    """Insert without specifying outcome/detail uses defaults."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Radarr", "missing", "Movie Y")

    results = await get_recent_searches(db)
    assert len(results) == 1
    assert results[0]["outcome"] == "searched"
    assert results[0]["detail"] == ""
    await db.close()


async def test_migration_preserves_existing_rows(tmp_path):
    """Calling init_db twice (re-migration) preserves existing rows."""
    db, db_path = await _init_test_db(tmp_path)

    # Insert an entry before second init_db call
    await insert_search_entry(db, "Sonarr", "cutoff", "Show Z")

    # Close and reopen connection, call init_db again (idempotent)
    await db.close()
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    results = await get_recent_searches(db)
    assert len(results) == 1
    assert results[0]["name"] == "Show Z"
    # Entry inserted after migration has outcome populated
    assert results[0]["outcome"] == "searched"
    await db.close()


# ---------------------------------------------------------------------------
# Search history filtering and pagination tests (SRCH-14)
# ---------------------------------------------------------------------------


async def test_get_search_history_default_returns_all(tmp_path):
    """get_search_history with no filters returns all entries, newest-first."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Radarr", "missing", "Movie A")
    await insert_search_entry(db, "Sonarr", "cutoff", "Show B")
    await insert_search_entry(db, "Radarr", "missing", "Movie C", outcome="failed")

    result = await get_search_history(db)
    assert result["total"] == 3
    assert result["page"] == 1
    assert result["per_page"] == 50
    assert result["total_pages"] == 1
    assert len(result["entries"]) == 3
    # Newest first (by id DESC)
    assert result["entries"][0]["name"] == "Movie C"
    assert result["entries"][1]["name"] == "Show B"
    assert result["entries"][2]["name"] == "Movie A"
    await db.close()


async def test_get_search_history_filter_by_app(tmp_path):
    """get_search_history with app_filter returns only matching app entries."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Radarr", "missing", "Movie A")
    await insert_search_entry(db, "Radarr", "cutoff", "Movie B")
    await insert_search_entry(db, "Sonarr", "missing", "Show C")

    result = await get_search_history(db, app_filter=["Radarr"])
    assert result["total"] == 2
    assert all(e["app"] == "Radarr" for e in result["entries"])
    await db.close()


async def test_get_search_history_filter_by_queue_type(tmp_path):
    """get_search_history with queue_filter returns only matching queue type entries."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Radarr", "missing", "Movie A")
    await insert_search_entry(db, "Radarr", "cutoff", "Movie B")
    await insert_search_entry(db, "Sonarr", "cutoff", "Show C")

    result = await get_search_history(db, queue_filter=["cutoff"])
    assert result["total"] == 2
    assert all(e["queue_type"] == "cutoff" for e in result["entries"])
    await db.close()


async def test_get_search_history_filter_by_outcome(tmp_path):
    """get_search_history with outcome_filter returns only matching outcome entries."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Radarr", "missing", "Movie A", outcome="searched")
    await insert_search_entry(db, "Radarr", "missing", "Movie B", outcome="failed")
    await insert_search_entry(db, "Sonarr", "cutoff", "Show C", outcome="failed")

    result = await get_search_history(db, outcome_filter=["failed"])
    assert result["total"] == 2
    assert all(e["outcome"] == "failed" for e in result["entries"])
    await db.close()


async def test_get_search_history_text_search(tmp_path):
    """get_search_history with search_text filters by case-insensitive substring."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Radarr", "missing", "The Matrix")
    await insert_search_entry(db, "Radarr", "missing", "Matrix Reloaded")
    await insert_search_entry(db, "Radarr", "missing", "Inception")

    result = await get_search_history(db, search_text="matrix")
    assert result["total"] == 2
    await db.close()


async def test_get_search_history_combined_filters(tmp_path):
    """get_search_history with multiple filters returns entries matching ALL filters."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Radarr", "missing", "Movie A")
    await insert_search_entry(db, "Radarr", "cutoff", "Movie B")
    await insert_search_entry(db, "Sonarr", "missing", "Show C")
    await insert_search_entry(db, "Sonarr", "cutoff", "Show D")

    result = await get_search_history(db, app_filter=["Radarr"], queue_filter=["missing"])
    assert result["total"] == 1
    assert result["entries"][0]["name"] == "Movie A"
    assert result["entries"][0]["app"] == "Radarr"
    assert result["entries"][0]["queue_type"] == "missing"
    await db.close()


async def test_get_search_history_pagination(tmp_path):
    """get_search_history paginates correctly across multiple pages."""
    db, db_path = await _init_test_db(tmp_path)

    for i in range(75):
        await insert_search_entry(db, "Radarr", "missing", f"Movie {i}")

    # Page 1
    result = await get_search_history(db, page=1)
    assert len(result["entries"]) == 50
    assert result["total"] == 75
    assert result["total_pages"] == 2

    # Page 2
    result2 = await get_search_history(db, page=2)
    assert len(result2["entries"]) == 25
    await db.close()


async def test_get_search_history_empty_db(tmp_path):
    """get_search_history on empty database returns zero entries and total_pages == 1."""
    db, db_path = await _init_test_db(tmp_path)

    result = await get_search_history(db)
    assert result["total"] == 0
    assert result["entries"] == []
    assert result["total_pages"] == 1
    await db.close()


async def test_get_search_history_entries_have_id(tmp_path):
    """get_search_history entries include 'id' key."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Radarr", "missing", "Movie A")

    result = await get_search_history(db)
    assert len(result["entries"]) == 1
    assert "id" in result["entries"][0]
    await db.close()


# ---------------------------------------------------------------------------
# W5 regression: ZeroDivisionError on per_page=0 (Phase 16 code review)
# ---------------------------------------------------------------------------


async def test_get_search_history_zero_per_page_defaults(tmp_path):
    """per_page=0 defaults to 50 instead of causing ZeroDivisionError."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Radarr", "missing", "Movie A")

    result = await get_search_history(db, per_page=0)
    assert result["per_page"] == 50
    assert result["total_pages"] >= 1
    assert len(result["entries"]) == 1
    await db.close()


# ---------------------------------------------------------------------------
# Migration system and tracking feature tests (Phase 17)
# ---------------------------------------------------------------------------


async def test_schema_version_tracked(tmp_path):
    """Schema version is tracked and reaches the expected final version."""
    db, db_path = await _init_test_db(tmp_path)
    version = await get_schema_version(db)
    assert version == 4
    await db.close()


async def test_backup_created_on_migration(tmp_path):
    """Database backup file is created before migration runs."""
    db, db_path = await _init_test_db(tmp_path)
    backup = db_path.with_suffix(".v0-backup")
    assert backup.exists()
    await db.close()


async def test_lifetime_stats_table_seeded(tmp_path):
    """lifetime_stats table has Radarr and Sonarr rows after migration."""
    db, db_path = await _init_test_db(tmp_path)
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT * FROM lifetime_stats ORDER BY app") as cursor:
        rows = await cursor.fetchall()
    db.row_factory = None
    assert len(rows) == 2
    assert rows[0]["app"] == "Radarr"
    assert rows[1]["app"] == "Sonarr"
    assert rows[0]["movies_found"] == 0
    assert rows[0]["last_reset_at"] is not None
    await db.close()


async def test_insert_with_tracking_fields(tmp_path):
    """insert_search_entry stores item_id, season_number, missing_count."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Radarr", "missing", "Movie X", item_id=42)
    await insert_search_entry(db, "Sonarr", "missing", "Show Y", item_id=100, season_number=3, missing_count=5)
    async with db.execute("SELECT item_id, season_number, missing_count FROM search_history ORDER BY id") as cursor:
        rows = await cursor.fetchall()
    assert rows[0] == (42, None, None)
    assert rows[1] == (100, 3, 5)
    await db.close()


async def test_pruning_preserves_pending_rows(tmp_path):
    """Pruning does not delete rows with outcome='searched' even when over max_rows."""
    db, db_path = await _init_test_db(tmp_path)
    # Insert 5 pending (searched) rows
    for i in range(5):
        await insert_search_entry(db, "Radarr", "missing", f"Pending {i}", outcome="searched", max_rows=3)
    # Insert 5 resolved rows
    for i in range(5):
        await insert_search_entry(db, "Radarr", "missing", f"Resolved {i}", outcome="grabbed", max_rows=3)
    # Count: all 5 pending should survive, only 3 resolved should survive
    async with db.execute("SELECT COUNT(*) FROM search_history WHERE outcome = 'searched'") as cursor:
        pending = (await cursor.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM search_history WHERE outcome != 'searched'") as cursor:
        resolved = (await cursor.fetchone())[0]
    assert pending == 5  # All pending preserved
    assert resolved == 3  # Capped at max_rows
    await db.close()


async def test_backfill_sets_unresolved(tmp_path):
    """Rows inserted before v1 migration get DEFAULT 'searched' for outcome.

    With the corrected v1 migration (DEFAULT 'searched'), pre-existing rows
    receive 'searched' when the column is added.  The v4 backfill only
    catches rows with NULL outcome (truly pre-v1 rows that were inserted
    by a version that predated the DEFAULT fix).
    """
    db_path = tmp_path / "test.db"
    # Create a v0 database manually (no migrations, just base table)
    db = await aiosqlite.connect(db_path)
    await db.execute("""
        CREATE TABLE search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            app TEXT NOT NULL,
            queue_type TEXT NOT NULL,
            item_name TEXT NOT NULL
        )
    """)
    await db.execute(
        "INSERT INTO search_history (timestamp, app, queue_type, item_name) "
        "VALUES ('2026-01-01', 'Radarr', 'missing', 'Old Movie')"
    )
    await db.commit()
    # Now run init_db which triggers migrations
    await init_db(db, db_path)
    async with db.execute("SELECT outcome FROM search_history WHERE item_name = 'Old Movie'") as cursor:
        row = await cursor.fetchone()
    # v1 migration sets DEFAULT 'searched', so pre-existing rows get 'searched'
    assert row[0] == "searched"
    await db.close()


# ---------------------------------------------------------------------------
# Tracking query and outcome update tests (Phase 20)
# ---------------------------------------------------------------------------


async def test_get_trackable_entries_returns_searched_and_partial(tmp_path):
    """Only entries with outcome 'searched' or 'partial' and non-null item_id are returned."""
    db, db_path = await _init_test_db(tmp_path)

    # Trackable: searched + item_id
    await insert_search_entry(db, "Radarr", "missing", "Movie A", outcome="searched", item_id=1)
    # Trackable: partial + item_id
    await insert_search_entry(db, "Sonarr", "missing", "Show B", outcome="partial", item_id=2)
    # Not trackable: grabbed
    await insert_search_entry(db, "Radarr", "missing", "Movie C", outcome="grabbed", item_id=3)
    # Not trackable: unresolved
    await insert_search_entry(db, "Radarr", "missing", "Movie D", outcome="unresolved", item_id=4)
    # Not trackable: failed
    await insert_search_entry(db, "Radarr", "missing", "Movie E", outcome="failed", item_id=5)
    # Not trackable: searched but item_id is None
    await insert_search_entry(db, "Radarr", "missing", "Movie F", outcome="searched")

    results = await get_trackable_entries(db)
    assert len(results) == 2
    names = {r["app"] + ":" + str(r["item_id"]) for r in results}
    assert names == {"Radarr:1", "Sonarr:2"}
    await db.close()


async def test_get_trackable_entries_returns_correct_fields(tmp_path):
    """Returned dicts have all expected keys with correct values."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(
        db, "Sonarr", "missing", "Show X",
        outcome="searched", item_id=42, season_number=3, missing_count=5,
    )

    results = await get_trackable_entries(db)
    assert len(results) == 1
    entry = results[0]
    assert "id" in entry
    assert entry["app"] == "Sonarr"
    assert entry["queue_type"] == "missing"
    assert entry["item_id"] == 42
    assert entry["season_number"] == 3
    assert entry["missing_count"] == 5
    assert entry["timestamp"] is not None
    await db.close()


async def test_get_trackable_entries_empty_table(tmp_path):
    """Returns empty list on fresh database with no search entries."""
    db, db_path = await _init_test_db(tmp_path)

    results = await get_trackable_entries(db)
    assert results == []
    await db.close()


async def test_get_trackable_entries_ordered_by_id(tmp_path):
    """Returned entries are ordered by id ASC (oldest first)."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Radarr", "missing", "Movie First", outcome="searched", item_id=10)
    await insert_search_entry(db, "Radarr", "missing", "Movie Second", outcome="searched", item_id=20)
    await insert_search_entry(db, "Radarr", "missing", "Movie Third", outcome="searched", item_id=30)

    results = await get_trackable_entries(db)
    assert len(results) == 3
    assert results[0]["item_id"] == 10
    assert results[1]["item_id"] == 20
    assert results[2]["item_id"] == 30
    await db.close()


async def test_update_outcome_changes_search_history_row(tmp_path):
    """update_outcome_and_stats changes the outcome and detail on the search_history row."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Radarr", "missing", "Movie A", outcome="searched", item_id=1)
    entries = await get_trackable_entries(db)
    hid = entries[0]["id"]

    await update_outcome_and_stats(db, hid, "grabbed", "Found 1 grab", app="Radarr", queue_type="missing")

    async with db.execute("SELECT outcome, detail FROM search_history WHERE id = ?", (hid,)) as cursor:
        row = await cursor.fetchone()
    assert row[0] == "grabbed"
    assert row[1] == "Found 1 grab"
    await db.close()


async def test_update_outcome_with_stat_increments(tmp_path):
    """update_outcome_and_stats increments lifetime_stats atomically with outcome change."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Radarr", "missing", "Movie A", outcome="searched", item_id=1)
    entries = await get_trackable_entries(db)
    hid = entries[0]["id"]

    await update_outcome_and_stats(
        db, hid, "grabbed", "1 grab",
        app="Radarr", queue_type="missing",
        stat_increments={"movies_found": 1},
    )

    # Verify outcome updated
    async with db.execute("SELECT outcome FROM search_history WHERE id = ?", (hid,)) as cursor:
        row = await cursor.fetchone()
    assert row[0] == "grabbed"

    # Verify stats incremented
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT movies_found FROM lifetime_stats WHERE app = 'Radarr'") as cursor:
        stats_row = await cursor.fetchone()
    db.row_factory = None
    assert stats_row["movies_found"] == 1
    await db.close()


async def test_update_outcome_with_multiple_stat_increments(tmp_path):
    """Multiple stat columns can be incremented in a single call."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Sonarr", "missing", "Show A", outcome="searched", item_id=1)
    entries = await get_trackable_entries(db)
    hid = entries[0]["id"]

    await update_outcome_and_stats(
        db, hid, "partial", "3 of 5 episodes grabbed",
        app="Sonarr", queue_type="missing",
        stat_increments={"episodes_found": 3},
    )

    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT episodes_found FROM lifetime_stats WHERE app = 'Sonarr'") as cursor:
        stats_row = await cursor.fetchone()
    db.row_factory = None
    assert stats_row["episodes_found"] == 3
    await db.close()


async def test_update_outcome_no_stats(tmp_path):
    """update_outcome_and_stats without stat_increments only changes outcome."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Radarr", "missing", "Movie A", outcome="searched", item_id=1)
    entries = await get_trackable_entries(db)
    hid = entries[0]["id"]

    await update_outcome_and_stats(
        db, hid, "unresolved", "No grabs found",
        app="Radarr", queue_type="missing",
    )

    # Verify outcome changed
    async with db.execute("SELECT outcome FROM search_history WHERE id = ?", (hid,)) as cursor:
        row = await cursor.fetchone()
    assert row[0] == "unresolved"

    # Verify stats unchanged (still 0)
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT movies_found, movies_updated FROM lifetime_stats WHERE app = 'Radarr'") as cursor:
        stats_row = await cursor.fetchone()
    db.row_factory = None
    assert stats_row["movies_found"] == 0
    assert stats_row["movies_updated"] == 0
    await db.close()


async def test_update_outcome_rejects_unknown_stat_column(tmp_path):
    """update_outcome_and_stats raises ValueError for unknown stat column names."""
    db, db_path = await _init_test_db(tmp_path)

    await insert_search_entry(db, "Radarr", "missing", "Movie A", outcome="searched", item_id=1)
    entries = await get_trackable_entries(db)
    hid = entries[0]["id"]

    with pytest.raises(ValueError, match="Unknown stat column"):
        await update_outcome_and_stats(
            db, hid, "grabbed", "test",
            app="Radarr", queue_type="missing",
            stat_increments={"bogus_col": 1},
        )
    await db.close()


# ---------------------------------------------------------------------------
# Deep-review safety fixes (Phase 20.1)
# ---------------------------------------------------------------------------


async def test_row_factory_restored_after_successful_calls(tmp_path):
    """row_factory is None after successful calls to all three row_factory-using functions."""
    db, db_path = await _init_test_db(tmp_path)

    # Insert a trackable entry so all three functions have data to query
    await insert_search_entry(db, "Radarr", "missing", "Movie A", outcome="searched", item_id=1)

    # get_recent_searches
    await get_recent_searches(db)
    assert db.row_factory is None, "row_factory not reset after get_recent_searches"

    # get_search_history
    await get_search_history(db)
    assert db.row_factory is None, "row_factory not reset after get_search_history"

    # get_trackable_entries
    await get_trackable_entries(db)
    assert db.row_factory is None, "row_factory not reset after get_trackable_entries"
    await db.close()


async def test_row_factory_restored_on_exception(tmp_path, monkeypatch):
    """row_factory is reset to None even when query execution raises an exception."""
    db, db_path = await _init_test_db(tmp_path)

    class _FailingContextManager:
        """Mimics aiosqlite's execute() return: async context manager that raises on __aenter__."""

        async def __aenter__(self):
            raise aiosqlite.OperationalError("simulated query failure")

        async def __aexit__(self, *args):
            pass

    def _failing_execute(*args, **kwargs):
        return _FailingContextManager()

    monkeypatch.setattr(db, "execute", _failing_execute)

    with pytest.raises(aiosqlite.OperationalError, match="simulated query failure"):
        await get_recent_searches(db)
    assert db.row_factory is None, "row_factory not reset after exception in get_recent_searches"

    with pytest.raises(aiosqlite.OperationalError, match="simulated query failure"):
        await get_search_history(db)
    assert db.row_factory is None, "row_factory not reset after exception in get_search_history"

    with pytest.raises(aiosqlite.OperationalError, match="simulated query failure"):
        await get_trackable_entries(db)
    assert db.row_factory is None, "row_factory not reset after exception in get_trackable_entries"

    await db.close()


async def test_run_migrations_fresh_install(tmp_path, monkeypatch):
    """Fresh install: run_migrations skips backup when db_path.exists() is False."""
    db_path = tmp_path / "fresh.db"

    # Connect and initialise via init_db, but patch Path.exists on the
    # db_path so that the backup guard in run_migrations sees it as missing.
    # This simulates the edge case where the file does not yet exist on disk.
    original_exists = Path.exists

    def _patched_exists(self):
        if self == db_path:
            return False
        return original_exists(self)

    monkeypatch.setattr(Path, "exists", _patched_exists)

    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    # Verify migrations ran to completion (no FileNotFoundError)
    version = await get_schema_version(db)
    assert version == 4

    # Verify no backup file was created (guard skipped the copy)
    backup = db_path.with_suffix(".v0-backup")
    assert not backup.exists(), "No backup should be created when db_path.exists() is False"
    await db.close()


async def test_migration_loop_tolerates_gaps(tmp_path):
    """Migration loop skips missing version numbers without KeyError."""
    from fetcharr.db import MIGRATIONS, run_migrations

    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await db.execute(
        "CREATE TABLE IF NOT EXISTS search_history "
        "(id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, "
        "app TEXT NOT NULL, queue_type TEXT NOT NULL, "
        "item_name TEXT NOT NULL)"
    )
    await db.execute(
        "CREATE TABLE IF NOT EXISTS schema_version "
        "(version INTEGER NOT NULL DEFAULT 0)"
    )
    await db.execute("INSERT INTO schema_version (version) VALUES (0)")
    await db.commit()
    await run_migrations(db, db_path)
    version = await get_schema_version(db)
    assert version == max(MIGRATIONS.keys())
    await db.close()


async def test_migration_suppresses_only_operational_error(tmp_path):
    """Re-running _migrate_v1 is idempotent -- OperationalError is suppressed."""
    db, db_path = await _init_test_db(tmp_path)

    # Columns already exist from init_db, so ALTER TABLE should raise
    # sqlite3.OperationalError ("duplicate column") but it is suppressed
    await _migrate_v1(db)  # should not raise

    # Verify the table still works correctly
    results = await get_recent_searches(db)
    assert isinstance(results, list)
    await db.close()
