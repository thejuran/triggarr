"""Tests for SQLite search history persistence module.

Covers: database init, insert/retrieve, limit, pruning,
migration from state.json, empty state, and empty database.
"""

from __future__ import annotations

import aiosqlite

from triggarr.db import get_recent_searches, get_search_history, init_db, insert_search_entry, migrate_from_state


async def test_init_db_creates_table(tmp_path):
    """init_db creates the search_history table and index."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='search_history'"
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "search_history"


async def test_insert_and_retrieve(tmp_path):
    """Inserted entries are retrieved in newest-first order with correct keys."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    await insert_search_entry(db_path, "Radarr", "missing", "Movie A")
    await insert_search_entry(db_path, "Sonarr", "cutoff", "Show B")
    await insert_search_entry(db_path, "Radarr", "missing", "Movie C")

    results = await get_recent_searches(db_path)
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


async def test_get_recent_searches_limit(tmp_path):
    """get_recent_searches respects the limit parameter."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    for i in range(10):
        await insert_search_entry(db_path, "Radarr", "missing", f"Movie {i}")

    results = await get_recent_searches(db_path, limit=3)
    assert len(results) == 3
    # Should be the 3 most recent
    assert results[0]["name"] == "Movie 9"
    assert results[1]["name"] == "Movie 8"
    assert results[2]["name"] == "Movie 7"


async def test_insert_prunes_old_entries(tmp_path):
    """Inserting beyond 500 entries prunes the oldest rows."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    for i in range(510):
        await insert_search_entry(db_path, "Radarr", "missing", f"Movie {i}")

    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM search_history")
        row = await cursor.fetchone()
    assert row[0] == 500


async def test_migrate_from_state(tmp_path):
    """migrate_from_state inserts entries from state.json format into SQLite."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    search_log = [
        {"name": "Movie A", "timestamp": "2026-01-15T10:30:00Z", "app": "Radarr", "queue_type": "missing"},
        {"name": "Show B", "timestamp": "2026-01-15T10:31:00Z", "app": "Sonarr", "queue_type": "cutoff"},
    ]

    count = await migrate_from_state(db_path, search_log)
    assert count == 2

    results = await get_recent_searches(db_path)
    assert len(results) == 2
    names = {r["name"] for r in results}
    assert names == {"Movie A", "Show B"}


async def test_migrate_empty_log(tmp_path):
    """migrate_from_state with empty list returns 0 and inserts nothing."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    count = await migrate_from_state(db_path, [])
    assert count == 0

    results = await get_recent_searches(db_path)
    assert results == []


async def test_get_recent_searches_empty_db(tmp_path):
    """get_recent_searches on empty database returns empty list."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    results = await get_recent_searches(db_path)
    assert results == []


# ---------------------------------------------------------------------------
# Outcome / detail column tests
# ---------------------------------------------------------------------------


async def test_insert_with_outcome_and_detail(tmp_path):
    """Insert an entry with explicit outcome and detail, verify retrieval."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    await insert_search_entry(
        db_path, "Radarr", "missing", "Movie X",
        outcome="failed", detail="Connection refused",
    )

    results = await get_recent_searches(db_path)
    assert len(results) == 1
    assert results[0]["outcome"] == "failed"
    assert results[0]["detail"] == "Connection refused"


async def test_insert_default_outcome(tmp_path):
    """Insert without specifying outcome/detail uses defaults."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    await insert_search_entry(db_path, "Radarr", "missing", "Movie Y")

    results = await get_recent_searches(db_path)
    assert len(results) == 1
    assert results[0]["outcome"] == "searched"
    assert results[0]["detail"] == ""


async def test_migration_preserves_existing_rows(tmp_path):
    """Calling init_db twice (re-migration) preserves existing rows."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    # Insert an entry before second init_db call
    await insert_search_entry(db_path, "Sonarr", "cutoff", "Show Z")

    # Second init_db triggers migration again (columns already exist)
    await init_db(db_path)

    results = await get_recent_searches(db_path)
    assert len(results) == 1
    assert results[0]["name"] == "Show Z"
    # Entry inserted after migration has outcome populated
    assert results[0]["outcome"] == "searched"


# ---------------------------------------------------------------------------
# Search history filtering and pagination tests (SRCH-14)
# ---------------------------------------------------------------------------


async def test_get_search_history_default_returns_all(tmp_path):
    """get_search_history with no filters returns all entries, newest-first."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    await insert_search_entry(db_path, "Radarr", "missing", "Movie A")
    await insert_search_entry(db_path, "Sonarr", "cutoff", "Show B")
    await insert_search_entry(db_path, "Radarr", "missing", "Movie C", outcome="failed")

    result = await get_search_history(db_path)
    assert result["total"] == 3
    assert result["page"] == 1
    assert result["per_page"] == 50
    assert result["total_pages"] == 1
    assert len(result["entries"]) == 3
    # Newest first (by id DESC)
    assert result["entries"][0]["name"] == "Movie C"
    assert result["entries"][1]["name"] == "Show B"
    assert result["entries"][2]["name"] == "Movie A"


async def test_get_search_history_filter_by_app(tmp_path):
    """get_search_history with app_filter returns only matching app entries."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    await insert_search_entry(db_path, "Radarr", "missing", "Movie A")
    await insert_search_entry(db_path, "Radarr", "cutoff", "Movie B")
    await insert_search_entry(db_path, "Sonarr", "missing", "Show C")

    result = await get_search_history(db_path, app_filter=["Radarr"])
    assert result["total"] == 2
    assert all(e["app"] == "Radarr" for e in result["entries"])


async def test_get_search_history_filter_by_queue_type(tmp_path):
    """get_search_history with queue_filter returns only matching queue type entries."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    await insert_search_entry(db_path, "Radarr", "missing", "Movie A")
    await insert_search_entry(db_path, "Radarr", "cutoff", "Movie B")
    await insert_search_entry(db_path, "Sonarr", "cutoff", "Show C")

    result = await get_search_history(db_path, queue_filter=["cutoff"])
    assert result["total"] == 2
    assert all(e["queue_type"] == "cutoff" for e in result["entries"])


async def test_get_search_history_filter_by_outcome(tmp_path):
    """get_search_history with outcome_filter returns only matching outcome entries."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    await insert_search_entry(db_path, "Radarr", "missing", "Movie A", outcome="searched")
    await insert_search_entry(db_path, "Radarr", "missing", "Movie B", outcome="failed")
    await insert_search_entry(db_path, "Sonarr", "cutoff", "Show C", outcome="failed")

    result = await get_search_history(db_path, outcome_filter=["failed"])
    assert result["total"] == 2
    assert all(e["outcome"] == "failed" for e in result["entries"])


async def test_get_search_history_text_search(tmp_path):
    """get_search_history with search_text filters by case-insensitive substring."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    await insert_search_entry(db_path, "Radarr", "missing", "The Matrix")
    await insert_search_entry(db_path, "Radarr", "missing", "Matrix Reloaded")
    await insert_search_entry(db_path, "Radarr", "missing", "Inception")

    result = await get_search_history(db_path, search_text="matrix")
    assert result["total"] == 2


async def test_get_search_history_combined_filters(tmp_path):
    """get_search_history with multiple filters returns entries matching ALL filters."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    await insert_search_entry(db_path, "Radarr", "missing", "Movie A")
    await insert_search_entry(db_path, "Radarr", "cutoff", "Movie B")
    await insert_search_entry(db_path, "Sonarr", "missing", "Show C")
    await insert_search_entry(db_path, "Sonarr", "cutoff", "Show D")

    result = await get_search_history(db_path, app_filter=["Radarr"], queue_filter=["missing"])
    assert result["total"] == 1
    assert result["entries"][0]["name"] == "Movie A"
    assert result["entries"][0]["app"] == "Radarr"
    assert result["entries"][0]["queue_type"] == "missing"


async def test_get_search_history_pagination(tmp_path):
    """get_search_history paginates correctly across multiple pages."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    for i in range(75):
        await insert_search_entry(db_path, "Radarr", "missing", f"Movie {i}")

    # Page 1
    result = await get_search_history(db_path, page=1)
    assert len(result["entries"]) == 50
    assert result["total"] == 75
    assert result["total_pages"] == 2

    # Page 2
    result2 = await get_search_history(db_path, page=2)
    assert len(result2["entries"]) == 25


async def test_get_search_history_empty_db(tmp_path):
    """get_search_history on empty database returns zero entries and total_pages == 1."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    result = await get_search_history(db_path)
    assert result["total"] == 0
    assert result["entries"] == []
    assert result["total_pages"] == 1


async def test_get_search_history_entries_have_id(tmp_path):
    """get_search_history entries include 'id' key."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    await insert_search_entry(db_path, "Radarr", "missing", "Movie A")

    result = await get_search_history(db_path)
    assert len(result["entries"]) == 1
    assert "id" in result["entries"][0]


# ---------------------------------------------------------------------------
# W5 regression: ZeroDivisionError on per_page=0 (Phase 16 code review)
# ---------------------------------------------------------------------------


async def test_get_search_history_zero_per_page_defaults(tmp_path):
    """per_page=0 defaults to 50 instead of causing ZeroDivisionError."""
    db_path = tmp_path / "test.db"
    await init_db(db_path)

    await insert_search_entry(db_path, "Radarr", "missing", "Movie A")

    result = await get_search_history(db_path, per_page=0)
    assert result["per_page"] == 50
    assert result["total_pages"] >= 1
    assert len(result["entries"]) == 1
