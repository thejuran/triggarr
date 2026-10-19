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

from tests.migration_faults import STANDARD_MAPPING, original_projection, seed_v9_db, snapshot
from triggarr.db import (
    OwnedGrab,
    OwnedGrabRecord,
    PendingCapExceeded,
    _apply_atomic_migration,
    _migrate_v1,
    _migrate_v10,
    get_dashboard_stats,
    get_owned_grabs,
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
    assert version == 10
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


# ---------------------------------------------------------------------------
# R-08 (Phase 78 Plan 02 Task 4): insert_search_entry rolls back on failure
# ---------------------------------------------------------------------------

_FAIL_PRUNE_TRIGGER_SQL = (
    "CREATE TRIGGER fail_prune BEFORE DELETE ON search_history "
    "BEGIN SELECT RAISE(ABORT, 'injected prune failure'); END"
)


class _CommitFailingConnection:
    """Test-local proxy: wraps a real aiosqlite connection so ``commit()`` raises
    without committing (R-08 fault injection for insert_search_entry).

    ``execute`` delegates to the real connection unchanged (returning the
    real awaitable/async-context-manager); ``rollback`` delegates unless
    ``fail_rollback`` is set; everything else forwards via ``__getattr__``.
    """

    def __init__(self, real: aiosqlite.Connection, *, fail_rollback: bool = False) -> None:
        self._real = real
        self._fail_rollback = fail_rollback

    def execute(self, *args, **kwargs):
        return self._real.execute(*args, **kwargs)

    async def commit(self) -> None:
        raise aiosqlite.OperationalError("injected commit failure")

    async def rollback(self) -> None:
        if self._fail_rollback:
            raise aiosqlite.OperationalError("injected rollback failure")
        await self._real.rollback()

    def __getattr__(self, name):
        return getattr(self._real, name)


async def test_insert_rolls_back_when_prune_fails(tmp_path):
    """R-08: a prune-DELETE failure after a successful INSERT rolls back the whole transaction."""
    db, db_path = await _init_test_db(tmp_path)
    try:
        for i in range(2):
            await insert_search_entry(db, "Radarr", "missing", f"Resolved {i}", outcome="failed")
        await db.execute(_FAIL_PRUNE_TRIGGER_SQL)
        await db.commit()

        with pytest.raises(aiosqlite.Error):
            await insert_search_entry(db, "Radarr", "missing", "Phantom", outcome="searched", max_rows=1)

        assert db.in_transaction is False
        async with db.execute(
            "SELECT COUNT(*) FROM search_history WHERE item_name = 'Phantom'"
        ) as cursor:
            row = await cursor.fetchone()
        assert row[0] == 0
    finally:
        await db.close()


async def test_insert_after_failed_prune_commits_no_phantom(tmp_path):
    """R-08: after a rolled-back prune failure, a later successful insert commits no phantom row."""
    db, db_path = await _init_test_db(tmp_path)
    db2 = None
    try:
        for i in range(2):
            await insert_search_entry(db, "Radarr", "missing", f"Resolved {i}", outcome="failed")
        await db.execute(_FAIL_PRUNE_TRIGGER_SQL)
        await db.commit()

        with pytest.raises(aiosqlite.Error):
            await insert_search_entry(db, "Radarr", "missing", "Phantom", outcome="searched", max_rows=1)

        await db.execute("DROP TRIGGER fail_prune")
        await db.commit()

        await insert_search_entry(db, "Radarr", "missing", "Real", outcome="searched", max_rows=1)

        # Open a second, independent connection so only committed data is visible.
        db2 = await aiosqlite.connect(db_path)
        async with db2.execute("SELECT COUNT(*) FROM search_history WHERE item_name = 'Real'") as cursor:
            real_count = (await cursor.fetchone())[0]
        async with db2.execute("SELECT COUNT(*) FROM search_history WHERE item_name = 'Phantom'") as cursor:
            phantom_count = (await cursor.fetchone())[0]
        assert real_count == 1
        assert phantom_count == 0
    finally:
        if db2 is not None:
            await db2.close()
        await db.close()


async def test_insert_rolls_back_when_commit_fails(tmp_path):
    """R-08: a commit failure after a successful INSERT rolls back; a later insert still succeeds."""
    db, db_path = await _init_test_db(tmp_path)
    try:
        proxy = _CommitFailingConnection(db)
        with pytest.raises(aiosqlite.OperationalError, match="injected commit failure"):
            await insert_search_entry(proxy, "Radarr", "missing", "Phantom", outcome="searched")

        assert db.in_transaction is False
        async with db.execute("SELECT COUNT(*) FROM search_history WHERE item_name = 'Phantom'") as cursor:
            row = await cursor.fetchone()
        assert row[0] == 0

        await insert_search_entry(db, "Radarr", "missing", "Real", outcome="searched")
        async with db.execute("SELECT COUNT(*) FROM search_history") as cursor:
            total = (await cursor.fetchone())[0]
        assert total == 1
    finally:
        await db.close()


async def test_pending_cap_ignores_rolled_back_rows(tmp_path):
    """R-08: a rolled-back pending insert must not count toward the pending-cap check."""
    db, db_path = await _init_test_db(tmp_path)
    try:
        max_rows = 1  # cap = 2 * 1 = 2
        # Seed at the default (large) max_rows so the inline resolved-row trim doesn't
        # prune these seed rows before the trigger is even installed.
        await insert_search_entry(db, "Radarr", "missing", "Seed Pending", outcome="searched")
        for i in range(2):
            await insert_search_entry(db, "Radarr", "missing", f"Resolved {i}", outcome="failed")

        await db.execute(_FAIL_PRUNE_TRIGGER_SQL)
        await db.commit()

        with pytest.raises(aiosqlite.Error):
            await insert_search_entry(
                db, "Radarr", "missing", "FailedPendingPrune", outcome="searched", max_rows=max_rows,
            )
        assert db.in_transaction is False

        await db.execute("DROP TRIGGER fail_prune")
        await db.commit()

        # Must NOT raise PendingCapExceeded -- the rolled-back row must not count toward the cap.
        await insert_search_entry(db, "Radarr", "missing", "Second Pending", outcome="searched", max_rows=max_rows)

        async with db.execute("SELECT COUNT(*) FROM search_history WHERE outcome = 'searched'") as cursor:
            pending_count = (await cursor.fetchone())[0]
        assert pending_count == 2
    finally:
        await db.close()


async def test_insert_rollback_failure_logged_original_error_raised(tmp_path):
    """R-08: if rollback itself fails, an ERROR is logged and the ORIGINAL error still propagates."""
    db, db_path = await _init_test_db(tmp_path)
    try:
        proxy = _CommitFailingConnection(db, fail_rollback=True)

        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="ERROR")
        try:
            with pytest.raises(aiosqlite.OperationalError, match="injected commit failure"):
                await insert_search_entry(proxy, "Radarr", "missing", "Phantom", outcome="searched")
        finally:
            logger.remove(handler_id)

        assert "rollback failed" in sink.getvalue()
    finally:
        await db.close()


async def test_pending_cap_rejection_still_no_write(tmp_path):
    """Regression: the pending-cap rejection path still raises PendingCapExceeded with no open transaction."""
    db, db_path = await _init_test_db(tmp_path)
    try:
        max_rows = 1  # cap = 2 * 1 = 2
        for i in range(2):
            await insert_search_entry(db, "Radarr", "missing", f"Pending {i}", outcome="searched", max_rows=max_rows)

        with pytest.raises(PendingCapExceeded):
            await insert_search_entry(db, "Radarr", "missing", "Rejected", outcome="searched", max_rows=max_rows)

        assert db.in_transaction is False
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
    assert version == 10

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


# ---------------------------------------------------------------------------
# Phase 81 Plan 05: get_dashboard_stats app + stable-ID scoping, legacy
# exclusion from rates (D-07), and per-metric historical flags (D-06)
# ---------------------------------------------------------------------------


async def _insert_cutover_row(db: aiosqlite.Connection, legacy_max_history_id: int) -> None:
    """Insert an attribution_cutover row directly (the two pre-fix fact columns are unused by
    get_dashboard_stats -- only legacy_max_history_id drives _LEGACY_MAX_ID_SQL)."""
    await db.execute(
        "INSERT INTO attribution_cutover "
        "(id, cutover_at, legacy_max_history_id, any_pre_fix_sonarr_data, pre_fix_sonarr_lifetime) "
        "VALUES (1, '2026-01-01T00:00:00Z', ?, 0, 0)",
        (legacy_max_history_id,),
    )
    await db.commit()


async def test_dashboard_stats_excludes_legacy_from_rates(tmp_path):
    """Legacy pending Sonarr rows (pre-cutover 'searched'/'partial') leave both rate denominators (D-07)."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", outcome="grabbed")  # id 1
    await insert_search_entry(db, "Sonarr", "missing", "Show B", outcome="unresolved")  # id 2
    await insert_search_entry(db, "Sonarr", "missing", "Show C", outcome="searched")  # id 3, legacy pending
    await insert_search_entry(db, "Sonarr", "missing", "Show D", outcome="partial")  # id 4, legacy pending
    await _insert_cutover_row(db, legacy_max_history_id=4)
    await insert_search_entry(db, "Sonarr", "missing", "Show E", outcome="grabbed")  # id 5, post-cutover
    await insert_search_entry(db, "Radarr", "missing", "Movie A", outcome="unresolved")  # id 6

    stats = await get_dashboard_stats(db)
    assert stats["sonarr_rate"] == pytest.approx(2 / 3 * 100)
    assert stats["overall_rate"] == pytest.approx(2 / 4 * 100)

    async with db.execute("SELECT outcome FROM search_history WHERE id IN (3, 4) ORDER BY id") as cursor:
        rows = await cursor.fetchall()
    assert [row[0] for row in rows] == ["searched", "partial"]
    await db.close()


async def test_dashboard_stats_keeps_resolved_historical_rows(tmp_path):
    """Resolved pre-cutover rows (not legacy pending) still count toward the rate."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", outcome="grabbed")  # id 1
    await insert_search_entry(db, "Sonarr", "missing", "Show B", outcome="unresolved")  # id 2
    await _insert_cutover_row(db, legacy_max_history_id=2)

    stats = await get_dashboard_stats(db)
    assert stats["sonarr_rate"] == pytest.approx(50.0)
    await db.close()


async def test_dashboard_stats_historical_flags_rate(tmp_path):
    """A resolved pre-fix Sonarr row trips both rate historical flags."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", outcome="grabbed")  # id 1
    await _insert_cutover_row(db, legacy_max_history_id=1)

    stats = await get_dashboard_stats(db)
    assert stats["sonarr_rate_includes_historical"] is True
    assert stats["overall_rate_includes_historical"] is True
    await db.close()


async def test_dashboard_stats_historical_flags_rate_false_when_only_legacy_pending_or_failed(tmp_path):
    """When the only pre-fix Sonarr rows are legacy-pending or 'failed', both rate flags are False."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", outcome="searched")  # id 1, legacy pending
    await insert_search_entry(db, "Sonarr", "missing", "Show B", outcome="failed")  # id 2
    await _insert_cutover_row(db, legacy_max_history_id=2)

    stats = await get_dashboard_stats(db)
    assert stats["sonarr_rate_includes_historical"] is False
    assert stats["overall_rate_includes_historical"] is False
    await db.close()


async def test_dashboard_stats_historical_flags_ttg_only_grabbed(tmp_path):
    """TTG flag stays False when the only pre-fix Sonarr row doesn't qualify for the TTG query."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", outcome="unresolved")  # id 1
    await _insert_cutover_row(db, legacy_max_history_id=1)

    stats = await get_dashboard_stats(db)
    assert stats["sonarr_rate_includes_historical"] is True
    assert stats["overall_rate_includes_historical"] is True
    assert stats["avg_time_to_grab_includes_historical"] is False
    await db.close()


async def test_dashboard_stats_historical_flags_ttg_true_when_grabbed_with_resolved_at(tmp_path):
    """TTG flag is True when a pre-fix Sonarr row is grabbed and has a resolved_at timestamp."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", outcome="grabbed")  # id 1
    await db.execute("UPDATE search_history SET resolved_at = ? WHERE id = 1", ("2026-01-02T00:00:00Z",))
    await db.commit()
    await _insert_cutover_row(db, legacy_max_history_id=1)

    stats = await get_dashboard_stats(db)
    assert stats["avg_time_to_grab_includes_historical"] is True
    await db.close()


async def test_dashboard_stats_historical_flags_scoped_to_view(tmp_path):
    """Historical flags are scoped by (app, instance_stable_id), not raised by an unrelated instance."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(
        db, "Sonarr", "missing", "Show A", outcome="grabbed", instance_stable_id="sid-main",
    )  # id 1
    await db.execute("UPDATE search_history SET resolved_at = ? WHERE id = 1", ("2026-01-02T00:00:00Z",))
    await db.commit()
    await _insert_cutover_row(db, legacy_max_history_id=1)

    stats_4k = await get_dashboard_stats(db, app="Sonarr", instance_stable_id="sid-4k")
    assert stats_4k["sonarr_rate_includes_historical"] is False
    assert stats_4k["overall_rate_includes_historical"] is False
    assert stats_4k["avg_time_to_grab_includes_historical"] is False

    stats_main = await get_dashboard_stats(db, app="Sonarr", instance_stable_id="sid-main")
    assert stats_main["sonarr_rate_includes_historical"] is True
    assert stats_main["overall_rate_includes_historical"] is True
    assert stats_main["avg_time_to_grab_includes_historical"] is True
    await db.close()


async def test_dashboard_stats_shared_name_scoped_by_app(tmp_path):
    """A Radarr instance and a Sonarr instance sharing the display name 'Default' never contaminate
    each other's rates, lifetime totals or historical flags once scoped by app + stable ID (R3)."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(
        db, "Radarr", "missing", "Movie A", outcome="unresolved",
        instance_id="Default", instance_stable_id="sid-r",
    )  # id 1
    await insert_search_entry(
        db, "Sonarr", "missing", "Show A", outcome="grabbed",
        instance_id="Default", instance_stable_id="sid-s",
    )  # id 2
    await db.execute("UPDATE search_history SET resolved_at = ? WHERE id = 2", ("2026-01-02T00:00:00Z",))
    await db.execute(
        "UPDATE lifetime_stats SET instance_stable_id = ?, movies_found = 0 "
        "WHERE app = 'Radarr' AND instance_id = 'Default'", ("sid-r",),
    )
    await db.execute(
        "UPDATE lifetime_stats SET instance_stable_id = ?, episodes_found = 5 "
        "WHERE app = 'Sonarr' AND instance_id = 'Default'", ("sid-s",),
    )
    await db.commit()
    await _insert_cutover_row(db, legacy_max_history_id=2)

    stats_r = await get_dashboard_stats(db, app="Radarr", instance_stable_id="sid-r")
    assert stats_r["overall_rate"] == 0.0
    assert stats_r["radarr_rate"] == 0.0
    assert stats_r["sonarr_rate"] is None
    assert stats_r["episodes_found"] == 0
    assert stats_r["overall_rate_includes_historical"] is False
    assert stats_r["sonarr_rate_includes_historical"] is False
    assert stats_r["avg_time_to_grab_includes_historical"] is False

    stats_s = await get_dashboard_stats(db, app="Sonarr", instance_stable_id="sid-s")
    assert stats_s["overall_rate"] == 100.0
    assert stats_s["sonarr_rate"] == 100.0
    assert stats_s["radarr_rate"] is None
    assert stats_s["episodes_found"] == 5
    assert stats_s["overall_rate_includes_historical"] is True
    assert stats_s["sonarr_rate_includes_historical"] is True
    assert stats_s["avg_time_to_grab_includes_historical"] is True

    stats_combined = await get_dashboard_stats(db, instance_id="Default")
    assert stats_combined["overall_rate"] == 50.0
    await db.close()


async def test_dashboard_stats_follows_stable_id_after_rename(tmp_path):
    """Displayed figures follow the stable ID through a rename, and a different server reusing the
    old name gets none of the original history or flags (S1)."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(
        db, "Sonarr", "missing", "Old Show", outcome="grabbed",
        instance_id="Old", instance_stable_id="sid-a",
    )  # id 1
    await db.execute("UPDATE search_history SET resolved_at = ? WHERE id = 1", ("2026-01-02T00:00:00Z",))
    await db.execute(
        "UPDATE lifetime_stats SET instance_id = 'Old', instance_stable_id = 'sid-a', episodes_found = 7 "
        "WHERE app = 'Sonarr' AND instance_id = 'Default'"
    )
    await db.commit()
    await _insert_cutover_row(db, legacy_max_history_id=1)

    stats_a = await get_dashboard_stats(db, app="Sonarr", instance_stable_id="sid-a")
    assert stats_a["episodes_found"] == 7
    assert stats_a["sonarr_rate"] == 100.0
    assert stats_a["sonarr_rate_includes_historical"] is True
    assert stats_a["overall_rate_includes_historical"] is True
    assert stats_a["avg_time_to_grab_includes_historical"] is True

    stats_c = await get_dashboard_stats(db, app="Sonarr", instance_stable_id="sid-c")
    assert stats_c["episodes_found"] == 0
    assert stats_c["sonarr_rate"] is None
    assert stats_c["sonarr_rate_includes_historical"] is False
    assert stats_c["overall_rate_includes_historical"] is False
    assert stats_c["avg_time_to_grab_includes_historical"] is False
    await db.close()


async def test_dashboard_stats_ignores_unassociated_rows_per_instance(tmp_path):
    """Unassociated rows (NULL/'' stable id) count only in the all-apps call, never per-instance (S1)."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Removed Show", outcome="grabbed")
    await db.commit()

    stats_all = await get_dashboard_stats(db)
    assert stats_all["sonarr_rate"] == 100.0

    stats_scoped = await get_dashboard_stats(db, app="Sonarr", instance_stable_id="sid-anything")
    assert stats_scoped["sonarr_rate"] is None
    await db.close()


async def test_dashboard_stats_scope_args_validated(tmp_path):
    """Invalid scope-argument combinations raise ValueError."""
    db, db_path = await _init_test_db(tmp_path)
    with pytest.raises(ValueError):
        await get_dashboard_stats(db, app="Sonarr")
    with pytest.raises(ValueError):
        await get_dashboard_stats(db, instance_stable_id="sid-a")
    with pytest.raises(ValueError):
        await get_dashboard_stats(db, app="Sonarr", instance_stable_id="")
    with pytest.raises(ValueError):
        await get_dashboard_stats(db, instance_id="Default", app="Sonarr")
    with pytest.raises(ValueError):
        await get_dashboard_stats(db, instance_id="Default", instance_stable_id="sid-a")
    await db.close()


async def test_dashboard_stats_historical_flags_ignore_other_apps(tmp_path):
    """Only pre-fix Radarr rows existing never trips any Sonarr-only historical flag."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Radarr", "missing", "Movie A", outcome="grabbed")  # id 1
    await db.execute("UPDATE search_history SET resolved_at = ? WHERE id = 1", ("2026-01-02T00:00:00Z",))
    await db.commit()
    await _insert_cutover_row(db, legacy_max_history_id=1)

    stats = await get_dashboard_stats(db)
    assert stats["sonarr_rate_includes_historical"] is False
    assert stats["overall_rate_includes_historical"] is False
    assert stats["avg_time_to_grab_includes_historical"] is False
    await db.close()


async def test_dashboard_stats_no_cutover_no_flags(tmp_path):
    """With no cutover row recorded, historical flags are False and rates compute exactly as before Phase 81."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", outcome="grabbed")
    await insert_search_entry(db, "Sonarr", "missing", "Show B", outcome="unresolved")
    await db.commit()

    stats = await get_dashboard_stats(db)
    assert stats["sonarr_rate"] == 50.0
    assert stats["sonarr_rate_includes_historical"] is False
    assert stats["overall_rate_includes_historical"] is False
    assert stats["avg_time_to_grab_includes_historical"] is False
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


# ---------------------------------------------------------------------------
# Migration v10: grab ownership, attribution cutover, stable-ID association
# ---------------------------------------------------------------------------


async def test_migration_v10_creates_attribution_tables(tmp_path):
    """v10 creates grab_ownership/attribution_cutover/sonarr_instance_pre_fix and their indexes."""
    db, db_path = await _init_test_db(tmp_path)

    for table in ("grab_ownership", "attribution_cutover", "sonarr_instance_pre_fix"):
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ) as cursor:
            assert await cursor.fetchone() is not None, f"missing table {table}"

    for index in (
        "idx_grab_ownership_series",
        "idx_search_history_instance_stable_id",
        "idx_lifetime_stats_app_stable_id",
    ):
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index,)
        ) as cursor:
            assert await cursor.fetchone() is not None, f"missing index {index}"

    async with db.execute("PRAGMA table_info(search_history)") as cursor:
        sh_cols = {row[1] for row in await cursor.fetchall()}
    assert "instance_stable_id" in sh_cols

    async with db.execute("PRAGMA table_info(lifetime_stats)") as cursor:
        ls_cols = {row[1] for row in await cursor.fetchall()}
    assert "instance_stable_id" in ls_cols

    async with db.execute("PRAGMA table_info(attribution_cutover)") as cursor:
        cutover_cols = {row[1] for row in await cursor.fetchall()}
    assert {"any_pre_fix_sonarr_data", "pre_fix_sonarr_lifetime"} <= cutover_cols

    async with db.execute("PRAGMA table_info(sonarr_instance_pre_fix)") as cursor:
        pre_fix_cols = {row[1] for row in await cursor.fetchall()}
    assert {"has_pre_fix_data", "lifetime_includes_pre_fix"} <= pre_fix_cols

    assert await get_schema_version(db) == 10

    async with db.execute("SELECT COUNT(*) FROM attribution_cutover") as cursor:
        count = (await cursor.fetchone())[0]
    assert count == 0
    await db.close()


async def test_migration_v10_preserves_existing_rows(tmp_path, monkeypatch):
    """With no mapping, v10 associates nothing and changes zero existing column values."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    before = await original_projection(db)

    await init_db(db, db_path)

    after = await original_projection(db)
    assert after == before

    async with db.execute("SELECT instance_stable_id FROM search_history") as cursor:
        rows = await cursor.fetchall()
    assert rows and all(row[0] is None for row in rows)

    async with db.execute("SELECT instance_stable_id FROM lifetime_stats") as cursor:
        rows = await cursor.fetchall()
    assert rows and all(row[0] == "" for row in rows)
    await db.close()


async def test_migration_v10_associates_stable_ids(tmp_path, monkeypatch):
    """Mapped (app, name) rows get the stable ID in both tables; unmapped rows stay empty/NULL."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    before = await original_projection(db)

    await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)

    after = await original_projection(db)
    assert after == before

    async with db.execute(
        "SELECT instance_stable_id FROM search_history WHERE app = 'Sonarr' AND instance_id = 'Old'"
    ) as cursor:
        rows = await cursor.fetchall()
    assert rows and all(row[0] == "sid-a" for row in rows)

    async with db.execute(
        "SELECT instance_stable_id FROM search_history WHERE app = 'Sonarr' AND instance_id = 'Gone'"
    ) as cursor:
        rows = await cursor.fetchall()
    assert rows and all(row[0] is None for row in rows)

    async with db.execute(
        "SELECT instance_stable_id FROM lifetime_stats WHERE app = 'Sonarr' AND instance_id = 'Old'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row[0] == "sid-a"

    async with db.execute(
        "SELECT instance_stable_id FROM lifetime_stats WHERE app = 'Sonarr' AND instance_id = 'Gone'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row[0] == ""

    async with db.execute(
        "SELECT instance_stable_id FROM search_history WHERE app = 'Radarr' AND instance_id = 'Default'"
    ) as cursor:
        rows = await cursor.fetchall()
    assert rows and all(row[0] == "sid-r" for row in rows)

    async with db.execute(
        "SELECT instance_stable_id FROM lifetime_stats WHERE app = 'Radarr' AND instance_id = 'Default'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row[0] == "sid-r"

    assert await get_schema_version(db) == 10
    await db.close()


async def test_migration_v10_mapping_ignores_other_apps_and_empty_ids(tmp_path, monkeypatch):
    """A mapping entry for a different app and one with an empty stable ID are both ignored."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row

    mapping = {("Radarr", "Old"): "sid-x", ("Sonarr", "Gone"): ""}
    await init_db(db, db_path, instance_stable_ids=mapping)

    async with db.execute(
        "SELECT instance_stable_id FROM search_history WHERE app = 'Sonarr' AND instance_id = 'Old'"
    ) as cursor:
        rows = await cursor.fetchall()
    assert rows and all(row[0] is None for row in rows)

    async with db.execute(
        "SELECT instance_stable_id FROM search_history WHERE app = 'Sonarr' AND instance_id = 'Gone'"
    ) as cursor:
        rows = await cursor.fetchall()
    assert rows and all(row[0] is None for row in rows)
    await db.close()


async def test_migration_v10_rerun_is_noop(tmp_path, monkeypatch):
    """Re-running _apply_atomic_migration for v10 on an already-migrated DB changes nothing."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)

    before = await snapshot(db)

    await _apply_atomic_migration(
        db, 10, _migrate_v10, instance_stable_ids=STANDARD_MAPPING, earliest_backup=None
    )

    after = await snapshot(db)
    assert after == before
    assert await get_schema_version(db) == 10
    await db.close()


async def test_migration_v10_no_foreign_key(tmp_path):
    """grab_ownership declares no FOREIGN KEY, so pruning search_history can never cascade into it."""
    db, db_path = await _init_test_db(tmp_path)
    async with db.execute("PRAGMA foreign_key_list(grab_ownership)") as cursor:
        rows = await cursor.fetchall()
    assert rows == []
    await db.close()


# ---------------------------------------------------------------------------
# Stable-ID selection, pending cap, and frozen legacy pending rows
# ---------------------------------------------------------------------------


async def _insert_cutover(db, legacy_max_history_id: int) -> None:
    """Insert a minimal attribution_cutover row directly, as the tests are told to."""
    await db.execute(
        "INSERT INTO attribution_cutover "
        "(id, cutover_at, legacy_max_history_id, any_pre_fix_sonarr_data, pre_fix_sonarr_lifetime) "
        "VALUES (1, ?, ?, 1, 0)",
        ("2026-01-01T00:00:00Z", legacy_max_history_id),
    )
    await db.commit()


async def test_insert_search_entry_records_stable_id(tmp_path):
    """insert_search_entry stores the stable ID; omitting it or passing '' stores NULL."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", instance_id="Main", instance_stable_id="sid-a")
    await insert_search_entry(db, "Sonarr", "missing", "Show B", instance_id="Main")
    await insert_search_entry(db, "Sonarr", "missing", "Show C", instance_id="Main", instance_stable_id="")

    async with db.execute("SELECT item_name, instance_stable_id FROM search_history ORDER BY id") as cursor:
        rows = await cursor.fetchall()
    by_name = {row[0]: row[1] for row in rows}
    assert by_name["Show A"] == "sid-a"
    assert by_name["Show B"] is None
    assert by_name["Show C"] is None
    await db.close()


async def test_trackable_by_stable_id_follows_rename(tmp_path):
    """get_trackable_entries(instance_stable_id=...) follows identity, not the display name."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(
        db, "Sonarr", "missing", "Old Show", item_id=1, instance_id="Old", instance_stable_id="sid-a",
    )
    await insert_search_entry(db, "Radarr", "missing", "Movie A", item_id=2, instance_id="Original")

    by_stable = await get_trackable_entries(db, instance_stable_id="sid-a")
    assert {e["item_id"] for e in by_stable} == {1}

    by_other_stable = await get_trackable_entries(db, instance_stable_id="sid-c")
    assert by_other_stable == []

    # Radarr/Lidarr callers (out of scope for stable-ID scoping) still select by name.
    by_name = await get_trackable_entries(db, instance_id="Original")
    assert {e["item_id"] for e in by_name} == {2}
    await db.close()


async def test_trackable_stable_id_and_name_are_exclusive(tmp_path):
    """Passing both instance_id and instance_stable_id to get_trackable_entries raises ValueError."""
    db, db_path = await _init_test_db(tmp_path)
    with pytest.raises(ValueError, match="instance_id"):
        await get_trackable_entries(db, instance_id="Old", instance_stable_id="sid-a")
    await db.close()


async def test_pending_cap_counts_by_stable_id(tmp_path):
    """The pending cap scoped by stable ID follows identity: renames count, name reuse doesn't."""
    db, db_path = await _init_test_db(tmp_path)
    max_rows = 2  # cap = 2 * PENDING_CAP_MULTIPLIER = 4
    for i in range(4):
        await insert_search_entry(
            db,
            "Sonarr",
            "missing",
            f"Old Show {i}",
            instance_id="Old",
            instance_stable_id="sid-a",
            max_rows=max_rows,
        )

    # A different server that reuses the name "Old" has its own stable ID and is not capped.
    await insert_search_entry(
        db, "Sonarr", "missing", "New Server Show", instance_id="Old", instance_stable_id="sid-c", max_rows=max_rows,
    )

    with pytest.raises(PendingCapExceeded):
        await insert_search_entry(
            db,
            "Sonarr",
            "missing",
            "One Too Many",
            instance_id="New Name",  # renamed instance, same stable ID still capped
            instance_stable_id="sid-a",
            max_rows=max_rows,
        )
    await db.close()


async def test_legacy_pending_excluded_from_trackable(tmp_path):
    """Pre-cutover pending Sonarr rows are excluded from tracking; everything else is unaffected."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Legacy Searched", item_id=1, outcome="searched")
    await insert_search_entry(db, "Sonarr", "missing", "Legacy Partial", item_id=2, outcome="partial")
    legacy_max_id = 2
    await insert_search_entry(db, "Sonarr", "missing", "Post-cutover Searched", item_id=3, outcome="searched")
    await insert_search_entry(db, "Radarr", "missing", "Legacy Radarr Searched", item_id=4, outcome="searched")

    await _insert_cutover(db, legacy_max_id)

    entries = await get_trackable_entries(db)
    item_ids = {e["item_id"] for e in entries}
    assert item_ids == {3, 4}
    await db.close()


async def test_legacy_pending_excluded_from_cap(tmp_path):
    """Legacy Sonarr pending rows don't count toward the pending cap; post-cutover rows still do."""
    db, db_path = await _init_test_db(tmp_path)
    max_rows = 1  # cap = PENDING_CAP_MULTIPLIER * 1 = 2
    await insert_search_entry(db, "Sonarr", "missing", "Legacy A", instance_id="Default", max_rows=max_rows)
    await insert_search_entry(db, "Sonarr", "missing", "Legacy B", instance_id="Default", max_rows=max_rows)
    async with db.execute("SELECT MAX(id) FROM search_history") as cursor:
        legacy_max_id = (await cursor.fetchone())[0]
    await _insert_cutover(db, legacy_max_id)

    # Legacy rows already fill the cap, but a new post-cutover insert still succeeds.
    await insert_search_entry(db, "Sonarr", "missing", "Post A", instance_id="Default", max_rows=max_rows)
    await insert_search_entry(db, "Sonarr", "missing", "Post B", instance_id="Default", max_rows=max_rows)

    with pytest.raises(PendingCapExceeded):
        await insert_search_entry(db, "Sonarr", "missing", "Post C", instance_id="Default", max_rows=max_rows)
    await db.close()


async def test_legacy_pending_rows_untouched(tmp_path):
    """Legacy rows keep their outcome, detail and resolved_at, and lifetime_stats stay unchanged."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Legacy Searched", item_id=1, outcome="searched")
    await _insert_cutover(db, 1)

    async with db.execute("SELECT * FROM lifetime_stats ORDER BY app, instance_id") as cursor:
        before_stats = [tuple(row) for row in await cursor.fetchall()]

    await get_trackable_entries(db)
    await insert_search_entry(db, "Sonarr", "missing", "Post Searched", item_id=2, outcome="searched")

    async with db.execute(
        "SELECT outcome, detail, resolved_at FROM search_history WHERE item_name = 'Legacy Searched'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row["outcome"] == "searched"
    assert row["detail"] in (None, "")
    assert row["resolved_at"] is None

    async with db.execute("SELECT * FROM lifetime_stats ORDER BY app, instance_id") as cursor:
        after_stats = [tuple(row) for row in await cursor.fetchall()]
    assert after_stats == before_stats
    await db.close()


async def test_legacy_pending_flag_in_listings(tmp_path):
    """get_search_history and get_recent_searches flag pre-cutover pending Sonarr rows as legacy."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Legacy Searched", item_id=1, outcome="searched")
    await insert_search_entry(db, "Sonarr", "missing", "Legacy Resolved", item_id=2, outcome="grabbed")
    legacy_max_id = 2
    await insert_search_entry(db, "Sonarr", "missing", "Post Searched", item_id=3, outcome="searched")
    await insert_search_entry(db, "Radarr", "missing", "Legacy Radarr Searched", item_id=4, outcome="searched")

    await _insert_cutover(db, legacy_max_id)

    history = await get_search_history(db, per_page=50)
    flags = {e["name"]: e["is_legacy"] for e in history["entries"]}
    assert flags["Legacy Searched"] is True
    assert flags["Legacy Resolved"] is False
    assert flags["Post Searched"] is False
    assert flags["Legacy Radarr Searched"] is False

    recent = await get_recent_searches(db, limit=50)
    recent_flags = {e["name"]: e["is_legacy"] for e in recent}
    assert recent_flags["Legacy Searched"] is True
    assert recent_flags["Legacy Resolved"] is False
    assert recent_flags["Post Searched"] is False
    assert recent_flags["Legacy Radarr Searched"] is False
    await db.close()


async def test_no_legacy_pending_without_cutover_row(tmp_path):
    """With no attribution_cutover row, nothing is legacy and tracking/cap behave as before."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Pending Show", item_id=1, outcome="searched")

    entries = await get_trackable_entries(db)
    assert {e["item_id"] for e in entries} == {1}

    history = await get_search_history(db, per_page=50)
    assert all(e["is_legacy"] is False for e in history["entries"])

    recent = await get_recent_searches(db, limit=50)
    assert all(e["is_legacy"] is False for e in recent)
    await db.close()


# ---------------------------------------------------------------------------
# Grab ownership: atomic with outcome/stats, keyed by (app, stable ID, grab ID)
# ---------------------------------------------------------------------------


async def test_update_outcome_and_stats_ownership_commits_together(tmp_path):
    """Ownership rows commit in the same transaction as the outcome/stat update."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", item_id=10, outcome="searched")

    owned_grabs = [OwnedGrab(501, 9001, 10, 1), OwnedGrab(502, 9002, 10, 1)]
    await update_outcome_and_stats(
        db,
        1,
        "grabbed",
        "grabbed: 2/2 episodes",
        app="Sonarr",
        queue_type="missing",
        instance_stable_id="sid-a",
        stat_increments={"episodes_found": 2},
        owned_grabs=owned_grabs,
    )

    async with db.execute("SELECT outcome FROM search_history WHERE id = 1") as cursor:
        row = await cursor.fetchone()
    assert row["outcome"] == "grabbed"

    async with db.execute(
        "SELECT episodes_found FROM lifetime_stats WHERE app = 'Sonarr' AND instance_stable_id = 'sid-a'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row["episodes_found"] == 2

    async with db.execute(
        "SELECT grab_id, history_id, series_id, season_number, episode_id FROM grab_ownership "
        "WHERE app = 'Sonarr' AND instance_stable_id = 'sid-a' ORDER BY grab_id"
    ) as cursor:
        rows = await cursor.fetchall()
    assert [tuple(r) for r in rows] == [(501, 1, 10, 1, 9001), (502, 1, 10, 1, 9002)]
    await db.close()


async def test_update_outcome_and_stats_ownership_rollback_on_failure(tmp_path):
    """An already-owned grab_id rolls back the outcome/stat update too -- all or nothing."""
    import sqlite3

    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", item_id=10, outcome="searched")
    await update_outcome_and_stats(
        db,
        1,
        "grabbed",
        "grabbed: 1/1 episodes",
        app="Sonarr",
        queue_type="missing",
        instance_stable_id="sid-a",
        stat_increments={"episodes_found": 1},
        owned_grabs=[OwnedGrab(501, 9001, 10, 1)],
    )

    async with db.execute(
        "SELECT outcome, detail, resolved_at FROM search_history WHERE id = 1"
    ) as cursor:
        before_history = tuple(await cursor.fetchone())
    async with db.execute(
        "SELECT * FROM lifetime_stats WHERE app = 'Sonarr' AND instance_stable_id = 'sid-a'"
    ) as cursor:
        before_stats = tuple(await cursor.fetchone())

    await insert_search_entry(db, "Sonarr", "missing", "Show B", item_id=11, outcome="searched")
    with pytest.raises(sqlite3.IntegrityError):
        await update_outcome_and_stats(
            db,
            2,
            "grabbed",
            "grabbed: 1/1 episodes",
            app="Sonarr",
            queue_type="missing",
            instance_stable_id="sid-a",
            stat_increments={"episodes_found": 1},
            owned_grabs=[OwnedGrab(501, 9002, 11, 1)],  # grab_id 501 already owned by sid-a
        )

    async with db.execute(
        "SELECT outcome, detail, resolved_at FROM search_history WHERE id = 1"
    ) as cursor:
        after_history = tuple(await cursor.fetchone())
    async with db.execute(
        "SELECT * FROM lifetime_stats WHERE app = 'Sonarr' AND instance_stable_id = 'sid-a'"
    ) as cursor:
        after_stats = tuple(await cursor.fetchone())
    assert after_history == before_history
    assert after_stats == before_stats

    async with db.execute(
        "SELECT outcome FROM search_history WHERE id = 2"
    ) as cursor:
        row = await cursor.fetchone()
    assert row["outcome"] == "searched"  # the failed update never landed

    async with db.execute(
        "SELECT COUNT(*) FROM grab_ownership WHERE app = 'Sonarr' AND instance_stable_id = 'sid-a'"
    ) as cursor:
        count = (await cursor.fetchone())[0]
    assert count == 1  # only the original grab_id 501 row, nothing from the failed call
    await db.close()


async def test_update_outcome_and_stats_ownership_requires_stable_id(tmp_path):
    """Non-empty owned_grabs with no stable ID raises ValueError before any write."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", item_id=10, outcome="searched")

    for bad_stable_id in (None, ""):
        with pytest.raises(ValueError, match="instance_stable_id"):
            await update_outcome_and_stats(
                db,
                1,
                "grabbed",
                "grabbed: 1/1 episodes",
                app="Sonarr",
                queue_type="missing",
                instance_stable_id=bad_stable_id,
                owned_grabs=[OwnedGrab(501, 9001, 10, 1)],
            )

    async with db.execute("SELECT outcome FROM search_history WHERE id = 1") as cursor:
        row = await cursor.fetchone()
    assert row["outcome"] == "searched"  # unchanged -- the ValueError fired before any write
    await db.close()


async def test_update_outcome_and_stats_without_ownership_unchanged(tmp_path):
    """Calling update_outcome_and_stats with no new kwargs behaves exactly as before (Radarr/Lidarr)."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Radarr", "missing", "Movie A", item_id=10, outcome="searched")
    await update_outcome_and_stats(
        db, 1, "grabbed", "grabbed", app="Radarr", queue_type="missing", stat_increments={"movies_found": 1},
    )

    async with db.execute("SELECT outcome FROM search_history WHERE id = 1") as cursor:
        row = await cursor.fetchone()
    assert row["outcome"] == "grabbed"

    async with db.execute(
        "SELECT movies_found FROM lifetime_stats WHERE app = 'Radarr' AND instance_id = 'Default'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row["movies_found"] == 1

    async with db.execute("SELECT COUNT(*) FROM grab_ownership") as cursor:
        count = (await cursor.fetchone())[0]
    assert count == 0
    await db.close()


async def test_ownership_cross_instance_same_grab_id(tmp_path):
    """The same grab_id for two different stable instance IDs is stored independently."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", item_id=10, outcome="searched")
    await insert_search_entry(db, "Sonarr", "missing", "Show B", item_id=20, outcome="searched")

    await update_outcome_and_stats(
        db, 1, "grabbed", "grabbed", app="Sonarr", queue_type="missing",
        instance_stable_id="sid-a", owned_grabs=[OwnedGrab(501, 9001, 10, 1)],
    )
    await update_outcome_and_stats(
        db, 2, "grabbed", "grabbed", app="Sonarr", queue_type="missing",
        instance_stable_id="sid-b", owned_grabs=[OwnedGrab(501, 9002, 20, 1)],
    )

    async with db.execute(
        "SELECT instance_stable_id, history_id FROM grab_ownership "
        "WHERE grab_id = 501 ORDER BY instance_stable_id"
    ) as cursor:
        rows = await cursor.fetchall()
    assert [tuple(r) for r in rows] == [("sid-a", 1), ("sid-b", 2)]
    await db.close()


async def test_ownership_survives_pruning(tmp_path):
    """grab_ownership has no reference to search_history, so pruning the owner row leaves it intact."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", item_id=10, outcome="searched", max_rows=1)
    await update_outcome_and_stats(
        db, 1, "grabbed", "grabbed", app="Sonarr", queue_type="missing",
        instance_stable_id="sid-a", owned_grabs=[OwnedGrab(501, 9001, 10, 1)],
    )

    # Insert enough resolved rows to prune the owner row out of search_history (max_rows=1).
    for i in range(3):
        await insert_search_entry(
            db, "Sonarr", "missing", f"Filler {i}", item_id=20 + i, outcome="grabbed", max_rows=1,
        )

    async with db.execute("SELECT COUNT(*) FROM search_history WHERE id = 1") as cursor:
        assert (await cursor.fetchone())[0] == 0  # owner row was pruned

    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-a", series_id=10)
    assert owned == [OwnedGrabRecord(501, 1, 9001)]
    await db.close()


async def test_ownership_survives_restart(tmp_path):
    """Ownership rows persist across a connection close and reopen."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", item_id=10, outcome="searched")
    await update_outcome_and_stats(
        db, 1, "grabbed", "grabbed", app="Sonarr", queue_type="missing",
        instance_stable_id="sid-a", owned_grabs=[OwnedGrab(501, 9001, 10, 1)],
    )
    await db.close()

    db2 = await aiosqlite.connect(db_path)
    await init_db(db2, db_path)
    owned = await get_owned_grabs(db2, app="Sonarr", instance_stable_id="sid-a", series_id=10)
    assert owned == [OwnedGrabRecord(501, 1, 9001)]
    await db2.close()


async def test_lifetime_increment_follows_stable_id_after_rename(tmp_path):
    """A rename keeps adding to the same stable-ID row; its stored name stays the old one."""
    db, db_path = await _init_test_db(tmp_path)
    await db.execute(
        "INSERT INTO lifetime_stats (app, instance_id, instance_stable_id, episodes_found, last_reset_at) "
        "VALUES ('Sonarr', 'Old', 'sid-a', 7, ?)",
        ("2026-01-01T00:00:00Z",),
    )
    await db.commit()
    async with db.execute("SELECT COUNT(*) FROM lifetime_stats") as cursor:
        count_before = (await cursor.fetchone())[0]

    await insert_search_entry(db, "Sonarr", "missing", "Show A", item_id=10, outcome="searched")
    await update_outcome_and_stats(
        db, 1, "grabbed", "grabbed", app="Sonarr", queue_type="missing", instance_id="New",
        instance_stable_id="sid-a", stat_increments={"episodes_found": 2},
    )

    async with db.execute(
        "SELECT instance_id, episodes_found FROM lifetime_stats WHERE app = 'Sonarr' AND instance_stable_id = 'sid-a'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row["instance_id"] == "Old"
    assert row["episodes_found"] == 9

    async with db.execute(
        "SELECT COUNT(*) FROM lifetime_stats WHERE instance_id = 'New'"
    ) as cursor:
        assert (await cursor.fetchone())[0] == 0

    async with db.execute("SELECT COUNT(*) FROM lifetime_stats") as cursor:
        assert (await cursor.fetchone())[0] == count_before
    await db.close()


async def test_lifetime_increment_name_reuse_gets_own_row(tmp_path):
    """A different server reusing an old name gets its own row; the original stable-ID row is untouched."""
    db, db_path = await _init_test_db(tmp_path)
    await db.execute(
        "INSERT INTO lifetime_stats (app, instance_id, instance_stable_id, episodes_found, last_reset_at) "
        "VALUES ('Sonarr', 'Old', 'sid-a', 7, ?)",
        ("2026-01-01T00:00:00Z",),
    )
    await db.commit()

    await insert_search_entry(db, "Sonarr", "missing", "Show A", item_id=10, outcome="searched")
    await update_outcome_and_stats(
        db, 1, "grabbed", "grabbed", app="Sonarr", queue_type="missing", instance_id="Old",
        instance_stable_id="sid-c", stat_increments={"episodes_found": 3},
    )

    async with db.execute(
        "SELECT episodes_found FROM lifetime_stats WHERE app = 'Sonarr' AND instance_stable_id = 'sid-c'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row["episodes_found"] == 3

    async with db.execute(
        "SELECT episodes_found FROM lifetime_stats WHERE app = 'Sonarr' AND instance_stable_id = 'sid-a'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row["episodes_found"] == 7
    await db.close()


async def test_lifetime_increment_never_touches_unassociated_rows(tmp_path):
    """An unassociated ('') row is never incremented again, whatever stable ID is used."""
    db, db_path = await _init_test_db(tmp_path)
    await db.execute(
        "UPDATE lifetime_stats SET instance_id = 'Gone', episodes_found = 4 "
        "WHERE app = 'Sonarr' AND instance_id = 'Default'"
    )
    await db.commit()

    await insert_search_entry(db, "Sonarr", "missing", "Show A", item_id=10, outcome="searched")
    await update_outcome_and_stats(
        db, 1, "grabbed", "grabbed", app="Sonarr", queue_type="missing", instance_id="Gone",
        instance_stable_id="sid-z", stat_increments={"episodes_found": 1},
    )

    async with db.execute(
        "SELECT episodes_found FROM lifetime_stats "
        "WHERE app = 'Sonarr' AND instance_id = 'Gone' AND instance_stable_id = ''"
    ) as cursor:
        row = await cursor.fetchone()
    assert row["episodes_found"] == 4
    await db.close()


async def test_lifetime_increment_without_stable_id_legacy_path(tmp_path):
    """With no stable ID, increments the legacy (app, name, '') row, creating it if missing."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", item_id=10, instance_id="Legacy", outcome="searched")
    await update_outcome_and_stats(
        db, 1, "grabbed", "grabbed", app="Sonarr", queue_type="missing", instance_id="Legacy",
        stat_increments={"episodes_found": 5},
    )

    async with db.execute(
        "SELECT episodes_found, instance_stable_id FROM lifetime_stats "
        "WHERE app = 'Sonarr' AND instance_id = 'Legacy'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row["episodes_found"] == 5
    assert row["instance_stable_id"] == ""
    await db.close()


async def test_lifetime_increment_rolls_back_with_ownership_failure(tmp_path):
    """The stable-ID lifetime row is unchanged when the ownership insert fails."""
    import sqlite3

    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", item_id=10, outcome="searched")
    await update_outcome_and_stats(
        db, 1, "grabbed", "grabbed", app="Sonarr", queue_type="missing",
        instance_stable_id="sid-a", stat_increments={"episodes_found": 1},
        owned_grabs=[OwnedGrab(501, 9001, 10, 1)],
    )
    async with db.execute(
        "SELECT episodes_found FROM lifetime_stats WHERE app = 'Sonarr' AND instance_stable_id = 'sid-a'"
    ) as cursor:
        before = (await cursor.fetchone())[0]

    await insert_search_entry(db, "Sonarr", "missing", "Show B", item_id=11, outcome="searched")
    with pytest.raises(sqlite3.IntegrityError):
        await update_outcome_and_stats(
            db, 2, "grabbed", "grabbed", app="Sonarr", queue_type="missing",
            instance_stable_id="sid-a", stat_increments={"episodes_found": 10},
            owned_grabs=[OwnedGrab(501, 9002, 11, 1)],
        )

    async with db.execute(
        "SELECT episodes_found FROM lifetime_stats WHERE app = 'Sonarr' AND instance_stable_id = 'sid-a'"
    ) as cursor:
        after = (await cursor.fetchone())[0]
    assert after == before
    await db.close()


async def test_get_owned_grabs_scoped(tmp_path):
    """get_owned_grabs returns only the given (app, stable ID, series) rows."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Sonarr", "missing", "Show A", item_id=10, outcome="searched")
    await insert_search_entry(db, "Sonarr", "missing", "Show B", item_id=20, outcome="searched")
    await update_outcome_and_stats(
        db, 1, "grabbed", "grabbed", app="Sonarr", queue_type="missing", instance_stable_id="sid-a",
        owned_grabs=[OwnedGrab(501, 9001, 10, 1), OwnedGrab(502, 9002, 10, 1)],
    )
    await update_outcome_and_stats(
        db, 2, "grabbed", "grabbed", app="Sonarr", queue_type="missing", instance_stable_id="sid-a",
        owned_grabs=[OwnedGrab(601, 9101, 20, 1)],
    )

    owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id="sid-a", series_id=10)
    assert set(owned) == {OwnedGrabRecord(501, 1, 9001), OwnedGrabRecord(502, 1, 9002)}
    await db.close()
