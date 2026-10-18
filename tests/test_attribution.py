"""Tests for the attribution cutover recording module.

Covers: exactly-once recording (including across restarts and after a
failed-then-retried v10 migration), the two persisted pre-fix facts (any
data vs. lifetime contribution) computed by stable ID rather than display
name, D-08's removed-instance global counting, and the v10-required guard.
"""

from __future__ import annotations

import io
import sqlite3

import aiosqlite
import pytest
from loguru import logger

from tests.migration_faults import STANDARD_MAPPING, V10_FAULT_POINTS, inject_v10_failure, seed_v9_db
from triggarr.attribution import ensure_cutover_recorded
from triggarr.db import MigrationRecoveryError, init_db, insert_search_entry

_LEFTOVER_SHAPE_SQL = (
    "CREATE TABLE lifetime_stats_v10 ("
    "app TEXT NOT NULL, instance_id TEXT NOT NULL DEFAULT 'Default', "
    "instance_stable_id TEXT NOT NULL DEFAULT '', "
    "movies_found INTEGER NOT NULL DEFAULT 0, movies_updated INTEGER NOT NULL DEFAULT 0, "
    "episodes_found INTEGER NOT NULL DEFAULT 0, episodes_updated INTEGER NOT NULL DEFAULT 0, "
    "last_reset_at TEXT NOT NULL, "
    "albums_found INTEGER NOT NULL DEFAULT 0, albums_updated INTEGER NOT NULL DEFAULT 0, "
    "PRIMARY KEY (app, instance_id, instance_stable_id))"
)
_LEFTOVER_COPY_SQL = (
    "INSERT INTO lifetime_stats_v10 "
    "(app, instance_id, movies_found, movies_updated, episodes_found, episodes_updated, "
    "last_reset_at, albums_found, albums_updated, instance_stable_id) "
    "SELECT app, instance_id, movies_found, movies_updated, episodes_found, episodes_updated, "
    "last_reset_at, albums_found, albums_updated, '' "
    "FROM lifetime_stats"
)


async def _init_test_db(tmp_path):
    """Create a test database with migrations applied, return (db, db_path)."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    return db, db_path


async def test_cutover_recorded_once(tmp_path):
    """ensure_cutover_recorded inserts exactly one row and is idempotent across calls and restarts."""
    db, db_path = await _init_test_db(tmp_path)
    await ensure_cutover_recorded(db, {"Main": "sid-a"})

    async with db.execute("SELECT cutover_at, legacy_max_history_id FROM attribution_cutover") as cursor:
        rows = await cursor.fetchall()
    assert len(rows) == 1
    first_cutover_at, first_max_id = rows[0]

    await ensure_cutover_recorded(db, {"Main": "sid-a"})
    async with db.execute("SELECT COUNT(*) FROM attribution_cutover") as cursor:
        assert (await cursor.fetchone())[0] == 1
    await db.close()

    db2 = await aiosqlite.connect(db_path)
    await init_db(db2, db_path)
    await ensure_cutover_recorded(db2, {"Main": "sid-a"})
    async with db2.execute("SELECT cutover_at, legacy_max_history_id FROM attribution_cutover") as cursor:
        rows = await cursor.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == first_cutover_at
    assert rows[0][1] == first_max_id
    await db2.close()


async def test_cutover_legacy_max_is_current_max_id(tmp_path):
    """legacy_max_history_id equals MAX(search_history.id) at cutover time."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Radarr", "missing", "Movie A")
    await insert_search_entry(db, "Radarr", "missing", "Movie B")
    await insert_search_entry(db, "Radarr", "missing", "Movie C")

    await ensure_cutover_recorded(db, {})

    async with db.execute("SELECT MAX(id) FROM search_history") as cursor:
        max_id = (await cursor.fetchone())[0]
    async with db.execute("SELECT legacy_max_history_id FROM attribution_cutover") as cursor:
        legacy_max = (await cursor.fetchone())[0]
    assert legacy_max == max_id
    await db.close()


async def test_cutover_legacy_max_is_zero_on_empty_table(tmp_path):
    """On an empty search_history table, legacy_max_history_id is 0."""
    db, db_path = await _init_test_db(tmp_path)
    await ensure_cutover_recorded(db, {})
    async with db.execute("SELECT legacy_max_history_id FROM attribution_cutover") as cursor:
        legacy_max = (await cursor.fetchone())[0]
    assert legacy_max == 0
    await db.close()


async def test_cutover_pre_fix_per_instance(tmp_path):
    """Per-instance flags follow the stable ID; the global flags also see unassociated rows."""
    db, db_path = await _init_test_db(tmp_path)
    await db.execute(
        "INSERT INTO search_history "
        "(timestamp, app, queue_type, item_name, outcome, instance_id, instance_stable_id) "
        "VALUES (?, 'Sonarr', 'missing', 'Show A', 'grabbed', 'Main', 'sid-a')",
        ("2026-01-01T00:00:00Z",),
    )
    await db.execute(
        "UPDATE lifetime_stats SET instance_id = 'Old', episodes_found = 4 "
        "WHERE app = 'Sonarr' AND instance_id = 'Default'"
    )
    await db.commit()

    await ensure_cutover_recorded(db, {"Main": "sid-a", "4K": "sid-b"})

    async with db.execute(
        "SELECT has_pre_fix_data, lifetime_includes_pre_fix FROM sonarr_instance_pre_fix "
        "WHERE instance_stable_id = 'sid-a'"
    ) as cursor:
        row = await cursor.fetchone()
    assert tuple(row) == (1, 0)

    async with db.execute(
        "SELECT has_pre_fix_data, lifetime_includes_pre_fix FROM sonarr_instance_pre_fix "
        "WHERE instance_stable_id = 'sid-b'"
    ) as cursor:
        row = await cursor.fetchone()
    assert tuple(row) == (0, 0)

    async with db.execute(
        "SELECT any_pre_fix_sonarr_data, pre_fix_sonarr_lifetime FROM attribution_cutover"
    ) as cursor:
        row = await cursor.fetchone()
    assert tuple(row) == (1, 1)
    await db.close()


async def test_cutover_pre_fix_follows_stable_id_not_name(tmp_path):
    """Pre-fix facts are computed by stable ID, not by the name currently stored on the row."""
    db, db_path = await _init_test_db(tmp_path)
    await db.execute(
        "INSERT INTO search_history "
        "(timestamp, app, queue_type, item_name, outcome, instance_id, instance_stable_id) "
        "VALUES (?, 'Sonarr', 'missing', 'Old Show', 'grabbed', 'Old', 'sid-a')",
        ("2026-01-01T00:00:00Z",),
    )
    await db.execute(
        "UPDATE lifetime_stats SET instance_id = 'Old', instance_stable_id = 'sid-a', episodes_found = 5 "
        "WHERE app = 'Sonarr' AND instance_id = 'Default'"
    )
    await db.commit()

    # "New" is the instance that actually owns sid-a; "Old" is a different
    # server (sid-c) that happens to reuse the old display name.
    await ensure_cutover_recorded(db, {"New": "sid-a", "Old": "sid-c"})

    async with db.execute(
        "SELECT has_pre_fix_data, lifetime_includes_pre_fix FROM sonarr_instance_pre_fix "
        "WHERE instance_stable_id = 'sid-a'"
    ) as cursor:
        row = await cursor.fetchone()
    assert tuple(row) == (1, 1)

    async with db.execute(
        "SELECT has_pre_fix_data, lifetime_includes_pre_fix FROM sonarr_instance_pre_fix "
        "WHERE instance_stable_id = 'sid-c'"
    ) as cursor:
        row = await cursor.fetchone()
    assert tuple(row) == (0, 0)
    await db.close()


async def test_cutover_pre_fix_lifetime_only(tmp_path):
    """No search_history rows but a non-zero associated lifetime_stats row still trips both flags."""
    db, db_path = await _init_test_db(tmp_path)
    await db.execute(
        "UPDATE lifetime_stats SET instance_stable_id = 'sid-a', episodes_updated = 2 "
        "WHERE app = 'Sonarr' AND instance_id = 'Default'"
    )
    await db.commit()

    await ensure_cutover_recorded(db, {"Main": "sid-a"})

    async with db.execute(
        "SELECT has_pre_fix_data, lifetime_includes_pre_fix FROM sonarr_instance_pre_fix "
        "WHERE instance_stable_id = 'sid-a'"
    ) as cursor:
        row = await cursor.fetchone()
    assert tuple(row) == (1, 1)

    async with db.execute(
        "SELECT any_pre_fix_sonarr_data, pre_fix_sonarr_lifetime FROM attribution_cutover"
    ) as cursor:
        row = await cursor.fetchone()
    assert tuple(row) == (1, 1)
    await db.close()


async def test_cutover_legacy_pending_only(tmp_path):
    """A pending-only Sonarr row trips has_pre_fix_data (the note) but not lifetime_includes_pre_fix (R4)."""
    db, db_path = await _init_test_db(tmp_path)
    await db.execute(
        "INSERT INTO search_history "
        "(timestamp, app, queue_type, item_name, outcome, instance_id, instance_stable_id) "
        "VALUES (?, 'Sonarr', 'missing', 'Pending Show', 'searched', 'Main', 'sid-a')",
        ("2026-01-01T00:00:00Z",),
    )
    await db.commit()

    await ensure_cutover_recorded(db, {"Main": "sid-a"})

    async with db.execute(
        "SELECT has_pre_fix_data, lifetime_includes_pre_fix FROM sonarr_instance_pre_fix "
        "WHERE instance_stable_id = 'sid-a'"
    ) as cursor:
        row = await cursor.fetchone()
    assert tuple(row) == (1, 0)

    async with db.execute(
        "SELECT any_pre_fix_sonarr_data, pre_fix_sonarr_lifetime FROM attribution_cutover"
    ) as cursor:
        row = await cursor.fetchone()
    assert tuple(row) == (1, 0)
    await db.close()


async def test_cutover_fresh_install_no_pre_fix(tmp_path):
    """A fresh install with only zero-valued seeded lifetime_stats and Radarr history has no pre-fix data."""
    db, db_path = await _init_test_db(tmp_path)
    await insert_search_entry(db, "Radarr", "missing", "Movie A")

    await ensure_cutover_recorded(db, {"Main": "sid-a"})

    async with db.execute(
        "SELECT any_pre_fix_sonarr_data, pre_fix_sonarr_lifetime FROM attribution_cutover"
    ) as cursor:
        row = await cursor.fetchone()
    assert tuple(row) == (0, 0)

    async with db.execute(
        "SELECT has_pre_fix_data, lifetime_includes_pre_fix FROM sonarr_instance_pre_fix "
        "WHERE instance_stable_id = 'sid-a'"
    ) as cursor:
        row = await cursor.fetchone()
    assert tuple(row) == (0, 0)
    await db.close()


async def test_cutover_removed_instance_counts_globally(tmp_path):
    """Unassociated Sonarr data from a removed instance still trips the global flags (D-08)."""
    db, db_path = await _init_test_db(tmp_path)
    await db.execute(
        "INSERT INTO search_history (timestamp, app, queue_type, item_name, outcome, instance_id) "
        "VALUES (?, 'Sonarr', 'missing', 'Removed Show', 'grabbed', 'Removed')",
        ("2026-01-01T00:00:00Z",),
    )
    await db.execute(
        "UPDATE lifetime_stats SET instance_id = 'Removed', episodes_found = 6 "
        "WHERE app = 'Sonarr' AND instance_id = 'Default'"
    )
    await db.commit()

    await ensure_cutover_recorded(db, {"Main": "sid-a"})

    async with db.execute(
        "SELECT any_pre_fix_sonarr_data, pre_fix_sonarr_lifetime FROM attribution_cutover"
    ) as cursor:
        row = await cursor.fetchone()
    assert tuple(row) == (1, 1)

    async with db.execute(
        "SELECT has_pre_fix_data, lifetime_includes_pre_fix FROM sonarr_instance_pre_fix "
        "WHERE instance_stable_id = 'sid-a'"
    ) as cursor:
        row = await cursor.fetchone()
    assert tuple(row) == (0, 0)
    await db.close()


async def test_cutover_skips_empty_stable_id(tmp_path):
    """A mapping entry with an empty stable ID is skipped with a warning; the cutover still records."""
    db, db_path = await _init_test_db(tmp_path)
    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        await ensure_cutover_recorded(db, {"Main": ""})
    finally:
        logger.remove(handler_id)

    log_text = sink.getvalue()
    assert "Main" in log_text

    async with db.execute("SELECT COUNT(*) FROM sonarr_instance_pre_fix WHERE instance_stable_id = ''") as cursor:
        assert (await cursor.fetchone())[0] == 0
    async with db.execute("SELECT COUNT(*) FROM attribution_cutover") as cursor:
        assert (await cursor.fetchone())[0] == 1
    await db.close()


async def test_cutover_requires_v10(tmp_path, monkeypatch):
    """ensure_cutover_recorded refuses to run against a pre-v10 schema and writes nothing."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row

    with pytest.raises(RuntimeError, match="v10"):
        await ensure_cutover_recorded(db, {"Main": "sid-a"})

    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='attribution_cutover'"
    ) as cursor:
        assert await cursor.fetchone() is None
    await db.close()


async def test_cutover_failure_rolls_back(tmp_path, monkeypatch):
    """A failure while writing the per-instance flags rolls back the attribution_cutover insert too."""
    db, db_path = await _init_test_db(tmp_path)
    original_execute = db.execute

    def fake_execute(sql, parameters=None):
        if isinstance(sql, str) and "INSERT OR REPLACE INTO sonarr_instance_pre_fix" in sql:
            msg = "injected failure"
            raise sqlite3.OperationalError(msg)
        return original_execute(sql, parameters)

    monkeypatch.setattr(db, "execute", fake_execute)

    with pytest.raises(sqlite3.OperationalError):
        await ensure_cutover_recorded(db, {"Main": "sid-a"})
    await db.close()

    db2 = await aiosqlite.connect(db_path)
    async with db2.execute("SELECT COUNT(*) FROM attribution_cutover") as cursor:
        assert (await cursor.fetchone())[0] == 0
    await db2.close()


@pytest.mark.parametrize("point", sorted(V10_FAULT_POINTS))
async def test_cutover_once_after_failed_then_retried_v10(tmp_path, monkeypatch, point):
    """The cutover is never recorded after a failed v10, and exactly once after a clean retry."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    inject_v10_failure(monkeypatch, db, point)
    with pytest.raises(sqlite3.OperationalError):
        await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)

    with pytest.raises(RuntimeError):
        await ensure_cutover_recorded(db, {"Old": "sid-a"})
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='attribution_cutover'"
    ) as cursor:
        assert await cursor.fetchone() is None
    await db.close()

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)
    await ensure_cutover_recorded(db, {"Old": "sid-a"})
    await ensure_cutover_recorded(db, {"Old": "sid-a"})
    await db.close()

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)
    await ensure_cutover_recorded(db, {"Old": "sid-a"})

    async with db.execute("SELECT COUNT(*) FROM attribution_cutover") as cursor:
        assert (await cursor.fetchone())[0] == 1

    async with db.execute(
        "SELECT legacy_max_history_id, any_pre_fix_sonarr_data, pre_fix_sonarr_lifetime "
        "FROM attribution_cutover"
    ) as cursor:
        row = await cursor.fetchone()
    async with db.execute("SELECT MAX(id) FROM search_history") as cursor:
        max_id = (await cursor.fetchone())[0]
    assert row["legacy_max_history_id"] == max_id
    assert row["any_pre_fix_sonarr_data"] == 1
    assert row["pre_fix_sonarr_lifetime"] == 1

    async with db.execute(
        "SELECT COUNT(*) FROM sonarr_instance_pre_fix WHERE instance_stable_id = 'sid-a'"
    ) as cursor:
        assert (await cursor.fetchone())[0] == 1
    await db.close()


async def test_cutover_refused_after_recovery_error(tmp_path, monkeypatch):
    """After a MigrationRecoveryError (F2b), the cutover guard still refuses and writes nothing."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row

    await db.execute(_LEFTOVER_SHAPE_SQL)
    await db.execute(_LEFTOVER_COPY_SQL)
    await db.execute("DROP TABLE lifetime_stats")
    await db.commit()

    with pytest.raises(MigrationRecoveryError):
        await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)

    with pytest.raises(RuntimeError):
        await ensure_cutover_recorded(db, {"Old": "sid-a"})

    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='attribution_cutover'"
    ) as cursor:
        assert await cursor.fetchone() is None
    await db.close()
