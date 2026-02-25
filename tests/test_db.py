"""Tests for SQLite search history persistence module.

Covers: database init, insert/retrieve, limit, pruning, migration system,
tracking columns, lifetime_stats, backfill migration, and shared-connection
signatures.
"""

from __future__ import annotations

import aiosqlite

from fetcharr.db import (
    get_recent_searches,
    get_schema_version,
    get_search_history,
    init_db,
    insert_search_entry,
    migrate_from_state,
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
    """Rows inserted before migration (NULL outcome) get backfilled to 'unresolved'."""
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
    assert row[0] == "unresolved"
    await db.close()
