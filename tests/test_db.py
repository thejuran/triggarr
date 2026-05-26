"""Tests for SQLite search history persistence module.

Covers: database init, insert/retrieve, limit, pruning, migration system,
tracking columns, lifetime_stats, backfill migration, shared-connection
signatures, and multi-instance scoping.
"""

from __future__ import annotations

import io
from pathlib import Path

import aiosqlite
import pytest
from loguru import logger

from triggarr.db import (
    _migrate_v1,
    get_dashboard_stats,
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
    assert version == 9
    await db.close()


async def test_backup_created_on_migration(tmp_path):
    """Database backup file is created before migration runs."""
    db, db_path = await _init_test_db(tmp_path)
    backup = db_path.with_suffix(".v0-backup")
    assert backup.exists()
    await db.close()


async def test_lifetime_stats_table_seeded(tmp_path):
    """lifetime_stats table has Radarr, Sonarr, and Lidarr rows after migration."""
    db, db_path = await _init_test_db(tmp_path)
    db.row_factory = aiosqlite.Row
    async with db.execute("SELECT * FROM lifetime_stats ORDER BY app") as cursor:
        rows = await cursor.fetchall()
    db.row_factory = None
    assert len(rows) == 3
    apps = [r["app"] for r in rows]
    assert "Radarr" in apps
    assert "Sonarr" in apps
    assert "Lidarr" in apps
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
    assert tuple(rows[0]) == (42, None, None)
    assert tuple(rows[1]) == (100, 3, 5)
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


async def test_pending_inserts_rejected_when_cap_reached(tmp_path):
    """SAFETY-01b: pending inserts past 2x max_rows are rejected with a logged WARNING.

    Today, pending rows (outcome='searched') are exempt from the resolved-row
    trim (DEBT-03) because they represent in-flight tracking the search engine
    wants to resolve. That exemption created an unbounded-growth failure mode
    (Codex adversarial review F1): if Sonarr/Radarr is unreachable for an
    extended period, every search cycle adds more pending rows that are never
    resolved.

    The fix (per User Decision Path A in 64-REVIEWS.md): cap pending rows at
    2 * max_rows by REJECTING new pending inserts when the cap is reached.
    Eviction would lose tracking semantics, which was the original concern
    that drove deferral. Rejection + WARNING log lets the operator see the
    cap being hit and correlate it with a specific stalled tracker.
    """
    # Import lazily so the RED phase produces a clean test failure (not a
    # collection error) before Task 4 defines PendingCapExceeded.
    try:
        from triggarr.db import PendingCapExceeded
    except ImportError:
        pytest.fail(
            "PendingCapExceeded not yet defined in triggarr.db -- "
            "this test is RED until Task 4 ships the production-code guard."
        )

    db, db_path = await _init_test_db(tmp_path)
    max_rows = 5  # small for test speed; cap is 2*5 = 10 pending
    try:
        # Insert exactly 2 * max_rows pending entries (all should succeed).
        for i in range(2 * max_rows):
            await insert_search_entry(
                db,
                "Radarr",
                "missing",
                f"Pending {i}",
                outcome="searched",
                instance_id="Default",
                max_rows=max_rows,
            )

        # Confirm the cap is right at the boundary BEFORE the rejected insert.
        async with db.execute(
            "SELECT COUNT(*) FROM search_history WHERE outcome = 'searched'"
        ) as cursor:
            pending_before = (await cursor.fetchone())[0]
        assert pending_before == 2 * max_rows, (
            f"Setup invariant broken: expected {2 * max_rows} pending rows "
            f"before the rejected insert, got {pending_before}."
        )

        # The next pending insert must be rejected AND emit a WARNING.
        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="WARNING")
        try:
            with pytest.raises(PendingCapExceeded):
                await insert_search_entry(
                    db,
                    "Radarr",
                    "missing",
                    "Rejected entry",
                    outcome="searched",
                    instance_id="Default",
                    max_rows=max_rows,
                )
        finally:
            logger.remove(handler_id)

        log_text = sink.getvalue()
        assert "Rejected entry" in log_text, (
            f"WARNING log must name the rejected entry's item_name; "
            f"got: {log_text!r}"
        )
        assert "Radarr" in log_text, (
            f"WARNING log must name the app for operator correlation; "
            f"got: {log_text!r}"
        )

        # Pending count must be unchanged -- the rejected insert did NOT land.
        async with db.execute(
            "SELECT COUNT(*) FROM search_history WHERE outcome = 'searched'"
        ) as cursor:
            pending_after = (await cursor.fetchone())[0]
        assert pending_after == 2 * max_rows, (
            f"Rejected insert must NOT add a row; "
            f"expected {2 * max_rows} pending, got {pending_after}."
        )
    finally:
        await db.close()


async def test_pending_cap_is_scoped_per_instance(tmp_path):
    """DEEP-02 (pass-1 follow-up): the pending-row cap must be scoped per
    (app, instance_id), not a global SELECT COUNT(*) over the whole table.

    Without this test, the production query at db.py::insert_search_entry
    could regress to a global COUNT and the existing single-instance test
    (test_pending_inserts_rejected_when_cap_reached) would still pass --
    masking a cross-instance interference bug where a stalled tracker on
    instance A could starve a healthy instance B.
    """
    from triggarr.db import PendingCapExceeded

    db, _ = await _init_test_db(tmp_path)
    max_rows = 5  # cap = 2 * 5 = 10 pending per instance
    try:
        # Fill Default to its per-instance cap.
        for i in range(2 * max_rows):
            await insert_search_entry(
                db,
                "Radarr",
                "missing",
                f"DefaultPending {i}",
                outcome="searched",
                instance_id="Default",
                max_rows=max_rows,
            )

        # A further Default insert must be rejected (per-instance cap reached).
        with pytest.raises(PendingCapExceeded):
            await insert_search_entry(
                db,
                "Radarr",
                "missing",
                "DefaultOverflow",
                outcome="searched",
                instance_id="Default",
                max_rows=max_rows,
            )

        # Secondary is empty and must still accept new pending inserts even
        # though Default is at its cap.
        await insert_search_entry(
            db,
            "Radarr",
            "missing",
            "SecondaryPending",
            outcome="searched",
            instance_id="Secondary",
            max_rows=max_rows,
        )

        # Same scoping must hold across apps: Sonarr/Default is independent.
        await insert_search_entry(
            db,
            "Sonarr",
            "missing",
            "SonarrPending",
            outcome="searched",
            instance_id="Default",
            max_rows=max_rows,
        )

        # Verify each instance bucket independently.
        async with db.execute(
            "SELECT COUNT(*) FROM search_history "
            "WHERE outcome = 'searched' AND app = 'Radarr' AND instance_id = 'Default'"
        ) as cursor:
            assert (await cursor.fetchone())[0] == 2 * max_rows
        async with db.execute(
            "SELECT COUNT(*) FROM search_history "
            "WHERE outcome = 'searched' AND app = 'Radarr' AND instance_id = 'Secondary'"
        ) as cursor:
            assert (await cursor.fetchone())[0] == 1
        async with db.execute(
            "SELECT COUNT(*) FROM search_history "
            "WHERE outcome = 'searched' AND app = 'Sonarr' AND instance_id = 'Default'"
        ) as cursor:
            assert (await cursor.fetchone())[0] == 1
    finally:
        await db.close()


async def test_insert_caps_at_max_rows_over_large_soak(tmp_path):
    """SAFETY-01: steady-state cap holds across 2x max_rows resolved inserts.

    The inline trim in insert_search_entry deletes resolved rows beyond
    max_rows after every insert. After inserting twice max_rows resolved
    entries, the table must contain exactly max_rows resolved rows,
    proving the trim runs after every insert and not only after some
    inserts.
    """
    db, db_path = await _init_test_db(tmp_path)
    max_rows = 1000
    try:
        for i in range(2 * max_rows):
            await insert_search_entry(
                db,
                "Radarr",
                "missing",
                f"Movie {i}",
                outcome="failed",
                max_rows=max_rows,
            )

        async with db.execute(
            "SELECT COUNT(*) FROM search_history WHERE COALESCE(outcome, 'searched') != 'searched'"
        ) as cursor:
            resolved_count = (await cursor.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM search_history") as cursor:
            total_count = (await cursor.fetchone())[0]

        assert resolved_count == max_rows, (
            f"Resolved rows should be capped at {max_rows}, got {resolved_count}"
        )
        assert total_count == max_rows, (
            f"Total rows should equal resolved count (no pending in this test), got {total_count}"
        )
    finally:
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


async def test_row_factory_set_globally_at_init(tmp_path):
    """row_factory is set to aiosqlite.Row at init_db time and stays set."""
    db, db_path = await _init_test_db(tmp_path)

    # init_db sets row_factory globally
    assert db.row_factory is aiosqlite.Row, "row_factory not set at init"

    # Insert a trackable entry so all three functions have data to query
    await insert_search_entry(db, "Radarr", "missing", "Movie A", outcome="searched", item_id=1)

    # row_factory remains aiosqlite.Row after each call
    await get_recent_searches(db)
    assert db.row_factory is aiosqlite.Row, "row_factory changed after get_recent_searches"

    await get_search_history(db)
    assert db.row_factory is aiosqlite.Row, "row_factory changed after get_search_history"

    await get_trackable_entries(db)
    assert db.row_factory is aiosqlite.Row, "row_factory changed after get_trackable_entries"
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
    assert version == 9

    # Verify no backup file was created (guard skipped the copy)
    backup = db_path.with_suffix(".v0-backup")
    assert not backup.exists(), "No backup should be created when db_path.exists() is False"
    await db.close()


async def test_migration_loop_tolerates_gaps(tmp_path):
    """Migration loop skips missing version numbers without KeyError."""
    from triggarr.db import MIGRATIONS, run_migrations

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


# ---------------------------------------------------------------------------
# Multi-instance scoping tests (S05)
# ---------------------------------------------------------------------------


async def test_insert_with_instance_id(tmp_path):
    """insert_search_entry stores instance_id in the row."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Radarr", "missing", "Movie A", instance_id="4K")
    await insert_search_entry(db, "Radarr", "missing", "Movie B", instance_id="1080p")
    await insert_search_entry(db, "Radarr", "missing", "Movie C")  # default

    async with db.execute("SELECT item_name, instance_id FROM search_history ORDER BY id") as cursor:
        rows = await cursor.fetchall()
    assert tuple(rows[0]) == ("Movie A", "4K")
    assert tuple(rows[1]) == ("Movie B", "1080p")
    assert tuple(rows[2]) == ("Movie C", "Default")
    await db.close()


async def test_get_recent_searches_instance_filter(tmp_path):
    """get_recent_searches with instance_id returns only matching entries."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Radarr", "missing", "Movie A", instance_id="4K")
    await insert_search_entry(db, "Radarr", "missing", "Movie B", instance_id="1080p")
    await insert_search_entry(db, "Sonarr", "missing", "Show C", instance_id="4K")

    results = await get_recent_searches(db, instance_id="4K")
    assert len(results) == 2
    names = {r["name"] for r in results}
    assert names == {"Movie A", "Show C"}
    assert all(r["instance_id"] == "4K" for r in results)

    # Without filter returns all
    all_results = await get_recent_searches(db)
    assert len(all_results) == 3
    await db.close()


async def test_get_recent_searches_includes_instance_id(tmp_path):
    """get_recent_searches includes instance_id in returned dicts."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Radarr", "missing", "Movie A", instance_id="Anime")

    results = await get_recent_searches(db)
    assert len(results) == 1
    assert results[0]["instance_id"] == "Anime"
    await db.close()


async def test_get_search_history_instance_filter(tmp_path):
    """get_search_history with instance_filter returns only matching instances."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Radarr", "missing", "Movie A", instance_id="4K")
    await insert_search_entry(db, "Radarr", "missing", "Movie B", instance_id="1080p")
    await insert_search_entry(db, "Sonarr", "missing", "Show C", instance_id="4K")

    result = await get_search_history(db, instance_filter=["4K"])
    assert result["total"] == 2
    assert all(e["instance_id"] == "4K" for e in result["entries"])

    # Multiple instance filter
    result = await get_search_history(db, instance_filter=["4K", "1080p"])
    assert result["total"] == 3
    await db.close()


async def test_get_search_history_combined_instance_and_app_filter(tmp_path):
    """get_search_history combines instance_filter with app_filter."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Radarr", "missing", "Movie A", instance_id="4K")
    await insert_search_entry(db, "Sonarr", "missing", "Show B", instance_id="4K")
    await insert_search_entry(db, "Radarr", "missing", "Movie C", instance_id="1080p")

    result = await get_search_history(db, app_filter=["Radarr"], instance_filter=["4K"])
    assert result["total"] == 1
    assert result["entries"][0]["name"] == "Movie A"
    await db.close()


async def test_get_search_history_entries_include_instance_id(tmp_path):
    """get_search_history entries include instance_id key."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Radarr", "missing", "Movie A", instance_id="TestInst")

    result = await get_search_history(db)
    assert result["entries"][0]["instance_id"] == "TestInst"
    await db.close()


async def test_get_trackable_entries_instance_filter(tmp_path):
    """get_trackable_entries with instance_id returns only matching entries."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(
        db, "Radarr", "missing", "Movie A", outcome="searched", item_id=1, instance_id="4K",
    )
    await insert_search_entry(
        db, "Radarr", "missing", "Movie B", outcome="searched", item_id=2, instance_id="1080p",
    )

    results = await get_trackable_entries(db, instance_id="4K")
    assert len(results) == 1
    assert results[0]["item_id"] == 1
    assert results[0]["instance_id"] == "4K"

    # Without filter returns all
    all_results = await get_trackable_entries(db)
    assert len(all_results) == 2
    await db.close()


async def test_get_trackable_entries_includes_instance_id(tmp_path):
    """get_trackable_entries includes instance_id in returned dicts."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(
        db, "Radarr", "missing", "Movie A", outcome="searched", item_id=1, instance_id="Anime",
    )

    results = await get_trackable_entries(db)
    assert len(results) == 1
    assert results[0]["instance_id"] == "Anime"
    await db.close()


async def test_update_outcome_and_stats_instance_scoped(tmp_path):
    """update_outcome_and_stats increments the correct instance's lifetime stats."""
    db, db_path = await _init_test_db(tmp_path)

    # Insert entries for two instances
    await insert_search_entry(
        db, "Radarr", "missing", "Movie A", outcome="searched", item_id=1, instance_id="4K",
    )
    await insert_search_entry(
        db, "Radarr", "missing", "Movie B", outcome="searched", item_id=2, instance_id="1080p",
    )

    entries = await get_trackable_entries(db)
    entry_4k = next(e for e in entries if e["instance_id"] == "4K")
    entry_1080p = next(e for e in entries if e["instance_id"] == "1080p")

    # Resolve 4K entry
    await update_outcome_and_stats(
        db, entry_4k["id"], "grabbed", "grabbed: test",
        app="Radarr", queue_type="missing", instance_id="4K",
        stat_increments={"movies_found": 1},
    )
    # Resolve 1080p entry
    await update_outcome_and_stats(
        db, entry_1080p["id"], "grabbed", "grabbed: test",
        app="Radarr", queue_type="missing", instance_id="1080p",
        stat_increments={"movies_found": 3},
    )

    # Verify per-instance stats
    async with db.execute(
        "SELECT instance_id, movies_found FROM lifetime_stats WHERE app = 'Radarr' ORDER BY instance_id",
    ) as cursor:
        rows = await cursor.fetchall()

    stats = {row[0]: row[1] for row in rows}
    assert stats["4K"] == 1
    assert stats["1080p"] == 3
    await db.close()


async def test_get_dashboard_stats_instance_scoped(tmp_path):
    """get_dashboard_stats with instance_id returns stats for that instance only."""
    db, db_path = await _init_test_db(tmp_path)

    # Insert grabbed entry for 4K and unresolved for 1080p
    await insert_search_entry(
        db, "Radarr", "missing", "Movie A", outcome="searched", item_id=1, instance_id="4K",
    )
    await insert_search_entry(
        db, "Radarr", "missing", "Movie B", outcome="searched", item_id=2, instance_id="1080p",
    )

    # Resolve 4K as grabbed
    entries = await get_trackable_entries(db, instance_id="4K")
    await update_outcome_and_stats(
        db, entries[0]["id"], "grabbed", "grabbed: test",
        app="Radarr", queue_type="missing", instance_id="4K",
        stat_increments={"movies_found": 1},
    )

    # Resolve 1080p as unresolved
    entries = await get_trackable_entries(db, instance_id="1080p")
    await update_outcome_and_stats(
        db, entries[0]["id"], "unresolved", "no grabs",
        app="Radarr", queue_type="missing", instance_id="1080p",
    )

    # 4K stats: 100% grab rate, 1 movie found
    stats_4k = await get_dashboard_stats(db, instance_id="4K")
    assert stats_4k["radarr_rate"] == 100.0
    assert stats_4k["movies_found"] == 1

    # 1080p stats: 0% grab rate, 0 movies found
    stats_1080p = await get_dashboard_stats(db, instance_id="1080p")
    assert stats_1080p["radarr_rate"] == 0.0
    assert stats_1080p["movies_found"] == 0

    # Overall stats: 50% grab rate, 1 movie found
    stats_all = await get_dashboard_stats(db)
    assert stats_all["radarr_rate"] == pytest.approx(50.0)
    assert stats_all["movies_found"] == 1
    await db.close()


async def test_migration_v6_adds_instance_id_column(tmp_path):
    """Migration v6 adds instance_id column with 'Default' as default value."""
    db, db_path = await _init_test_db(tmp_path)
    # Existing entries from init_db should have 'Default' as instance_id
    await insert_search_entry(db, "Radarr", "missing", "Pre-migration Movie")

    async with db.execute("SELECT instance_id FROM search_history") as cursor:
        rows = await cursor.fetchall()
    assert all(row[0] == "Default" for row in rows)

    # Verify index exists
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_search_history_instance_id'",
    ) as cursor:
        idx = await cursor.fetchone()
    assert idx is not None
    await db.close()


async def test_migration_v7_lifetime_stats_composite_key(tmp_path):
    """Migration v7 rebuilds lifetime_stats with (app, instance_id) composite key."""
    db, db_path = await _init_test_db(tmp_path)

    # Default rows should exist
    async with db.execute(
        "SELECT app, instance_id FROM lifetime_stats ORDER BY app",
    ) as cursor:
        rows = await cursor.fetchall()
    assert len(rows) == 3
    apps = [(r[0], r[1]) for r in rows]
    assert ("Lidarr", "Default") in apps
    assert ("Radarr", "Default") in apps
    assert ("Sonarr", "Default") in apps

    # Can insert new instance rows without violating PK
    now = "2026-01-01T00:00:00Z"
    await db.execute(
        "INSERT INTO lifetime_stats (app, instance_id, last_reset_at) VALUES (?, ?, ?)",
        ("Radarr", "4K", now),
    )
    await db.execute(
        "INSERT INTO lifetime_stats (app, instance_id, last_reset_at) VALUES (?, ?, ?)",
        ("Radarr", "1080p", now),
    )
    await db.commit()

    async with db.execute("SELECT COUNT(*) FROM lifetime_stats WHERE app = 'Radarr'") as cursor:
        count = (await cursor.fetchone())[0]
    assert count == 3  # Default + 4K + 1080p
    await db.close()


async def test_row_factory_persists_after_instance_scoped_queries(tmp_path):
    """row_factory remains aiosqlite.Row after instance-scoped query functions."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Radarr", "missing", "Movie A", instance_id="4K")

    await get_recent_searches(db, instance_id="4K")
    assert db.row_factory is aiosqlite.Row, "row_factory changed after instance-scoped get_recent_searches"

    await get_trackable_entries(db, instance_id="4K")
    assert db.row_factory is aiosqlite.Row, "row_factory changed after instance-scoped get_trackable_entries"

    await get_dashboard_stats(db, instance_id="4K")
    assert db.row_factory is aiosqlite.Row, "row_factory changed after instance-scoped get_dashboard_stats"
    await db.close()


# --- Corrupt/invalid database tests ---


async def test_init_db_corrupt_file_raises_database_error(tmp_path: Path) -> None:
    """Corrupt SQLite file (random bytes) raises DatabaseError on first SQL execution."""
    import sqlite3

    db_path = tmp_path / "corrupt.db"
    db_path.write_bytes(bytes(range(256)))

    db = await aiosqlite.connect(db_path)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            await init_db(db, db_path)
    finally:
        await db.close()


async def test_init_db_locked_database(tmp_path: Path) -> None:
    """Locked database raises OperationalError with zero busy_timeout."""
    import sqlite3

    db_path = tmp_path / "locked.db"

    # Create a valid DB first
    db1 = await aiosqlite.connect(db_path)
    await init_db(db1, db_path)
    await db1.close()

    # Hold an exclusive lock with a second connection
    db2 = await aiosqlite.connect(db_path)
    try:
        await db2.execute("BEGIN EXCLUSIVE")

        # Third connection with zero timeout should fail immediately
        db3 = await aiosqlite.connect(db_path)
        try:
            await db3.execute("PRAGMA busy_timeout = 0")
            with pytest.raises(sqlite3.OperationalError, match="database is locked"):
                await init_db(db3, db_path)
        finally:
            await db3.close()
    finally:
        await db2.execute("ROLLBACK")
        await db2.close()


async def test_get_schema_version_on_empty_db(tmp_path: Path) -> None:
    """get_schema_version on fresh DB creates table and returns 0."""
    db_path = tmp_path / "empty.db"
    db = await aiosqlite.connect(db_path)
    try:
        version = await get_schema_version(db)
        assert version == 0
    finally:
        await db.close()
