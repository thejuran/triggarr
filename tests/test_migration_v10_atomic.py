"""Tests for migration v10's atomic runner, leftover-table recovery, and failure injection.

Covers F1 (runner scope: v1-v9 unchanged, v10 runs inside the runner-owned
transaction), F2 (leftover ``lifetime_stats_v10`` recovery), F3 (the
13-point failure-injection rollback and clean-retry matrix) and F4 (an
older "v10 schema present, version not recorded" partial state).
"""

from __future__ import annotations

import io
import sqlite3

import aiosqlite
import pytest
from loguru import logger

import triggarr.db as db_module
from tests.migration_faults import (
    STANDARD_MAPPING,
    V10_FAULT_POINTS,
    counter_sums,
    inject_v10_failure,
    original_projection,
    seed_v9_db,
    snapshot,
)
from triggarr.db import (
    MIGRATIONS,
    MigrationRecoveryError,
    _apply_atomic_migration,
    _migrate_v10,
    get_schema_version,
    init_db,
)

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


async def _new_tables_and_columns_absent(db: aiosqlite.Connection) -> bool:
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
        "('grab_ownership', 'attribution_cutover', 'sonarr_instance_pre_fix')"
    ) as cursor:
        tables = {row[0] for row in await cursor.fetchall()}
    async with db.execute("PRAGMA table_info(search_history)") as cursor:
        sh_cols = {row[1] for row in await cursor.fetchall()}
    return not tables and "instance_stable_id" not in sh_cols


# ---------------------------------------------------------------------------
# F1: runner scope
# ---------------------------------------------------------------------------


async def test_v10_runner_scope_v1_to_v9_unchanged(tmp_path, monkeypatch):
    """v1-v9 run exactly as before; v10 alone runs inside the runner's transaction."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)

    calls: list[tuple[int, tuple, dict, bool]] = []

    def make_recorder(version, original_fn):
        async def recorder(db_arg, *args, **kwargs):
            calls.append((version, args, kwargs, db_arg.in_transaction))
            return await original_fn(db_arg, *args, **kwargs)

        return recorder

    for version, (desc, fn) in list(MIGRATIONS.items()):
        monkeypatch.setitem(MIGRATIONS, version, (desc, make_recorder(version, fn)))

    set_schema_version_calls: list[int] = []
    original_set_schema_version = db_module.set_schema_version

    async def spy_set_schema_version(db_arg, version):
        set_schema_version_calls.append(version)
        await original_set_schema_version(db_arg, version)

    monkeypatch.setattr(db_module, "set_schema_version", spy_set_schema_version)

    await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)

    v1_to_9 = [c for c in calls if c[0] != 10]
    assert [c[0] for c in v1_to_9] == list(range(1, 10))
    for _version, args, kwargs, in_tx in v1_to_9:
        assert args == ()
        assert kwargs == {}
        assert in_tx is False

    v10_calls = [c for c in calls if c[0] == 10]
    assert len(v10_calls) == 1
    _, args10, kwargs10, in_tx10 = v10_calls[0]
    assert args10 == ()
    assert "instance_stable_ids" in kwargs10
    assert in_tx10 is True

    assert set_schema_version_calls == list(range(1, 10))
    assert await get_schema_version(db) == 10
    await db.close()


async def test_v10_refuses_outside_transaction(tmp_path, monkeypatch):
    """Calling _migrate_v10 directly with no open transaction raises and changes nothing."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    before = await snapshot(db)

    assert db.in_transaction is False
    with pytest.raises(RuntimeError):
        await _migrate_v10(db, instance_stable_ids={})

    after = await snapshot(db)
    assert after == before
    await db.close()


async def test_v10_atomic_refuses_open_transaction(tmp_path, monkeypatch):
    """_apply_atomic_migration refuses to start when an implicit transaction is already open."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row

    await db.execute(
        "INSERT INTO search_history (timestamp, app, queue_type, item_name) VALUES (?, ?, ?, ?)",
        ("2026-01-01T00:00:00Z", "Radarr", "missing", "Uncommitted Movie"),
    )
    assert db.in_transaction is True

    with pytest.raises(RuntimeError):
        await _apply_atomic_migration(
            db, 10, _migrate_v10, instance_stable_ids=STANDARD_MAPPING, earliest_backup=None
        )

    await db.rollback()
    async with db.execute(
        "SELECT COUNT(*) FROM search_history WHERE item_name = 'Uncommitted Movie'"
    ) as cursor:
        count = (await cursor.fetchone())[0]
    assert count == 0
    assert await get_schema_version(db) == 9
    await db.close()


# ---------------------------------------------------------------------------
# F3: 13-point failure injection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("point", sorted(V10_FAULT_POINTS))
async def test_v10_fault_rolls_back(tmp_path, monkeypatch, point):
    """A failure at any of the 13 v10 fault points leaves an intact v9 database after reopening."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)

    seed_check = await aiosqlite.connect(db_path)
    seed_check.row_factory = aiosqlite.Row
    before = await snapshot(seed_check)
    await seed_check.close()

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA synchronous=NORMAL")
    state = inject_v10_failure(monkeypatch, db, point)

    with pytest.raises(sqlite3.OperationalError):
        await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)
    assert state.fired is True, f"fault point {point!r} was never reached"
    await db.close()

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    after = await snapshot(db)
    assert await _new_tables_and_columns_absent(db)
    await db.close()

    assert after == before
    assert after["schema_version"] == 9


@pytest.mark.parametrize("point", sorted(V10_FAULT_POINTS))
async def test_v10_retry_after_fault_succeeds(tmp_path, monkeypatch, point):
    """After a failure at any fault point, a clean retry completes v10 without duplicating totals."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)

    seed_check = await aiosqlite.connect(db_path)
    seed_check.row_factory = aiosqlite.Row
    before_projection = await original_projection(seed_check)
    before_sums = await counter_sums(seed_check)
    await seed_check.close()

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    state = inject_v10_failure(monkeypatch, db, point)
    with pytest.raises(sqlite3.OperationalError):
        await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)
    assert state.fired is True, f"fault point {point!r} was never reached"
    await db.close()

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)

    assert await get_schema_version(db) == 10

    after_projection = await original_projection(db)
    assert after_projection == before_projection
    after_sums = await counter_sums(db)
    assert after_sums == before_sums

    async with db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lifetime_stats_v10'"
    ) as cursor:
        assert await cursor.fetchone() is None

    async with db.execute(
        "SELECT instance_stable_id FROM search_history WHERE app='Sonarr' AND instance_id='Old'"
    ) as cursor:
        rows = await cursor.fetchall()
    assert rows and all(r[0] == "sid-a" for r in rows)

    async with db.execute(
        "SELECT instance_stable_id FROM lifetime_stats WHERE app='Sonarr' AND instance_id='Old'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row[0] == "sid-a"

    async with db.execute(
        "SELECT instance_stable_id FROM search_history WHERE app='Radarr' AND instance_id='Default'"
    ) as cursor:
        rows = await cursor.fetchall()
    assert rows and all(r[0] == "sid-r" for r in rows)

    async with db.execute(
        "SELECT instance_stable_id FROM lifetime_stats WHERE app='Radarr' AND instance_id='Default'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row[0] == "sid-r"

    async with db.execute(
        "SELECT instance_stable_id FROM search_history WHERE app='Sonarr' AND instance_id='Gone'"
    ) as cursor:
        rows = await cursor.fetchall()
    assert rows and all(r[0] is None for r in rows)

    async with db.execute(
        "SELECT instance_stable_id FROM lifetime_stats WHERE app='Sonarr' AND instance_id='Gone'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row[0] == ""

    for index_name in (
        "idx_grab_ownership_series",
        "idx_search_history_instance_stable_id",
        "idx_lifetime_stats_app_stable_id",
    ):
        async with db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name=?", (index_name,)
        ) as cursor:
            count = (await cursor.fetchone())[0]
        assert count == 1, f"{index_name} present {count} times"

    await db.close()


async def test_v10_fault_logs_rollback(tmp_path, monkeypatch):
    """A v10 failure logs one ERROR line naming v10, the rollback, and the canonical backup -- no IDs."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    inject_v10_failure(monkeypatch, db, "record_version")

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="ERROR")
    try:
        with pytest.raises(sqlite3.OperationalError):
            await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)
    finally:
        logger.remove(handler_id)
    await db.close()

    log_text = sink.getvalue()
    v10_lines = [line for line in log_text.splitlines() if "v10" in line]
    assert len(v10_lines) == 1, f"expected exactly one v10 error line, got: {log_text!r}"
    line = v10_lines[0]
    assert "rolled back" in line
    assert ".v9-backup" in line
    assert "sid-a" not in line
    assert "sid-r" not in line


# ---------------------------------------------------------------------------
# F2: leftover lifetime_stats_v10 recovery
# ---------------------------------------------------------------------------


async def test_v10_recovers_leftover_partial_copy(tmp_path, monkeypatch):
    """A leftover partial copy is discarded when the original lifetime_stats is provably intact."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    before_projection = await original_projection(db)
    before_sums = await counter_sums(db)

    await db.execute(_LEFTOVER_SHAPE_SQL)
    await db.execute(_LEFTOVER_COPY_SQL + " WHERE app = 'Sonarr'")
    await db.commit()

    await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)

    assert await get_schema_version(db) == 10
    async with db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lifetime_stats_v10'"
    ) as cursor:
        assert await cursor.fetchone() is None

    after_projection = await original_projection(db)
    assert after_projection == before_projection
    after_sums = await counter_sums(db)
    assert after_sums == before_sums

    async with db.execute(
        "SELECT instance_stable_id FROM lifetime_stats WHERE app='Sonarr' AND instance_id='Old'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row[0] == "sid-a"
    await db.close()


async def test_v10_leftover_without_original_stops(tmp_path, monkeypatch):
    """A leftover copy with the original already dropped stops startup and touches nothing."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row

    await db.execute(_LEFTOVER_SHAPE_SQL)
    await db.execute(_LEFTOVER_COPY_SQL)
    await db.execute("DROP TABLE lifetime_stats")
    await db.commit()

    async with db.execute("PRAGMA table_info(lifetime_stats_v10)") as cursor:
        leftover_schema = [tuple(row) for row in await cursor.fetchall()]
    async with db.execute("SELECT * FROM lifetime_stats_v10 ORDER BY app, instance_id") as cursor:
        leftover_rows = [tuple(row) for row in await cursor.fetchall()]

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="ERROR")
    try:
        with pytest.raises(MigrationRecoveryError, match="lifetime_stats_v10"):
            await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)
    finally:
        logger.remove(handler_id)

    log_text = sink.getvalue()
    assert "lifetime_stats_v10" in log_text
    assert "lifetime_stats" in log_text
    assert "backup" in log_text.lower()
    await db.close()

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    async with db.execute("PRAGMA table_info(lifetime_stats_v10)") as cursor:
        schema_after = [tuple(row) for row in await cursor.fetchall()]
    async with db.execute("SELECT * FROM lifetime_stats_v10 ORDER BY app, instance_id") as cursor:
        rows_after = [tuple(row) for row in await cursor.fetchall()]
    assert schema_after == leftover_schema
    assert rows_after == leftover_rows

    assert await get_schema_version(db) == 9
    assert await _new_tables_and_columns_absent(db)
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='lifetime_stats'"
    ) as cursor:
        assert await cursor.fetchone() is None  # still dropped -- recovery touched nothing
    async with db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='attribution_cutover'"
    ) as cursor:
        assert await cursor.fetchone() is None
    await db.close()


async def test_v10_leftover_with_unexpected_original_stops(tmp_path, monkeypatch):
    """A leftover copy alongside an original that isn't the exact v9 shape stops startup untouched."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row

    await db.execute("ALTER TABLE lifetime_stats ADD COLUMN mystery_column TEXT")
    await db.execute(_LEFTOVER_SHAPE_SQL)
    await db.commit()

    async with db.execute("SELECT COUNT(*) FROM lifetime_stats") as cursor:
        ls_count_before = (await cursor.fetchone())[0]
    async with db.execute("SELECT COUNT(*) FROM lifetime_stats_v10") as cursor:
        leftover_count_before = (await cursor.fetchone())[0]

    with pytest.raises(MigrationRecoveryError):
        await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)

    assert await get_schema_version(db) == 9
    async with db.execute("SELECT COUNT(*) FROM lifetime_stats") as cursor:
        assert (await cursor.fetchone())[0] == ls_count_before
    async with db.execute("SELECT COUNT(*) FROM lifetime_stats_v10") as cursor:
        assert (await cursor.fetchone())[0] == leftover_count_before
    async with db.execute("PRAGMA table_info(lifetime_stats)") as cursor:
        cols = {row[1] for row in await cursor.fetchall()}
    assert "mystery_column" in cols
    assert "instance_stable_id" not in cols
    await db.close()


async def test_v10_backup_never_overwrites_earlier_backup(tmp_path, monkeypatch):
    """A pre-existing canonical backup is preserved; a new timestamped backup is written alongside it."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    backup_path = db_path.with_suffix(".v9-backup")
    known_bytes = b"not a real database, just a marker"
    backup_path.write_bytes(known_bytes)

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    inject_v10_failure(monkeypatch, db, "copy")

    with pytest.raises(sqlite3.OperationalError):
        await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)
    await db.close()

    assert backup_path.read_bytes() == known_bytes

    timestamped = sorted(tmp_path.glob("test.v9-backup-*"))
    assert len(timestamped) == 1, f"expected exactly one timestamped backup, found {timestamped}"


async def test_v10_backup_writes_canonical_name_on_first_migration(tmp_path, monkeypatch):
    """A first-ever migration attempt (no pre-existing backup) still writes the canonical name."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    backup_path = db_path.with_suffix(".v9-backup")
    assert not backup_path.exists()

    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)
    await db.close()

    assert backup_path.exists()


# ---------------------------------------------------------------------------
# F4: older "schema present, version not recorded" partial state
# ---------------------------------------------------------------------------


async def test_v10_completes_older_partial_state(tmp_path, monkeypatch):
    """A DB with v10's schema fully present but schema_version still 9 completes idempotently."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    before_projection = await original_projection(db)
    before_sums = await counter_sums(db)

    await init_db(db, db_path, instance_stable_ids={("Sonarr", "Old"): "sid-a"})
    assert await get_schema_version(db) == 10

    # Simulate the pre-atomic-runner state: schema fully present, version not recorded.
    await db.execute("UPDATE schema_version SET version = 9")
    await db.commit()
    assert await get_schema_version(db) == 9

    await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)

    assert await get_schema_version(db) == 10
    after_projection = await original_projection(db)
    assert after_projection == before_projection
    after_sums = await counter_sums(db)
    assert after_sums == before_sums

    async with db.execute(
        "SELECT instance_stable_id FROM search_history WHERE app='Sonarr' AND instance_id='Old'"
    ) as cursor:
        rows = await cursor.fetchall()
    assert rows and all(r[0] == "sid-a" for r in rows)

    async with db.execute(
        "SELECT instance_stable_id FROM search_history WHERE app='Radarr' AND instance_id='Default'"
    ) as cursor:
        rows = await cursor.fetchall()
    assert rows and all(r[0] == "sid-r" for r in rows)

    async with db.execute(
        "SELECT instance_stable_id FROM lifetime_stats WHERE app='Radarr' AND instance_id='Default'"
    ) as cursor:
        row = await cursor.fetchone()
    assert row[0] == "sid-r"

    for index_name in (
        "idx_grab_ownership_series",
        "idx_search_history_instance_stable_id",
        "idx_lifetime_stats_app_stable_id",
    ):
        async with db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name=?", (index_name,)
        ) as cursor:
            count = (await cursor.fetchone())[0]
        assert count == 1

    async with db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='lifetime_stats_v10'"
    ) as cursor:
        assert await cursor.fetchone() is None

    async with db.execute("SELECT COUNT(*) FROM attribution_cutover") as cursor:
        assert (await cursor.fetchone())[0] == 0
    await db.close()


async def test_v10_older_partial_state_rerun_twice_is_stable(tmp_path, monkeypatch):
    """Running init_db again after older-partial-state recovery changes nothing further."""
    db_path = await seed_v9_db(tmp_path, monkeypatch)
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await init_db(db, db_path, instance_stable_ids={("Sonarr", "Old"): "sid-a"})
    await db.execute("UPDATE schema_version SET version = 9")
    await db.commit()
    await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)

    before = await snapshot(db)
    await init_db(db, db_path, instance_stable_ids=STANDARD_MAPPING)
    after = await snapshot(db)
    assert after == before
    await db.close()
