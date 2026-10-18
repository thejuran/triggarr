"""Shared fixtures and fault-injection helpers for v10 migration tests.

Not a test module itself (no ``test_*`` functions) -- imported by
``tests/test_db.py``, ``tests/test_migration_v10_atomic.py`` and
``tests/test_attribution.py``.  ``tests/`` is a package, so this module
is imported as ``tests.migration_faults``.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

import aiosqlite

from triggarr.db import MIGRATIONS, get_schema_version, init_db

# A representative mapping used by every fault-injection and recovery test:
# one Sonarr instance ("Old") and one Radarr instance ("Default") get stable
# IDs; everything else in the seed data (Sonarr "Gone", Lidarr "Default")
# stays unassociated so tests can prove unmapped rows are left alone.
STANDARD_MAPPING: dict[tuple[str, str], str] = {
    ("Sonarr", "Old"): "sid-a",
    ("Radarr", "Default"): "sid-r",
}

_SEED_TIMESTAMP = "2026-01-01T00:00:00Z"


async def seed_v9_db(tmp_path: Path, monkeypatch: Any) -> Path:
    """Build a v9 database with representative rows, then restore v10's registration.

    Removes ``MIGRATIONS[10]`` for the duration of the build (so ``init_db``
    stops at v9), seeds search_history and lifetime_stats rows across Sonarr
    ("Old" -- the instance a mapping will associate, and "Gone" -- an
    instance no configured mapping names), Radarr ("Default") and Lidarr
    ("Default"), then explicitly restores ``MIGRATIONS[10]`` (not via
    ``monkeypatch.undo()``, which would also undo any other patch the caller
    has made) before returning the database path.
    """
    db_path = tmp_path / "test.db"
    v10_entry = MIGRATIONS[10]
    monkeypatch.delitem(MIGRATIONS, 10)
    try:
        db = await aiosqlite.connect(db_path)
        try:
            await init_db(db, db_path)
            await _seed_search_history(db)
            await _seed_lifetime_stats(db)
            version = await get_schema_version(db)
            if version != 9:
                msg = f"seed_v9_db: expected schema v9 after seeding, got v{version}"
                raise AssertionError(msg)
        finally:
            await db.close()
    finally:
        MIGRATIONS[10] = v10_entry
    return db_path


async def _seed_search_history(db: aiosqlite.Connection) -> None:
    rows = [
        # Sonarr "Old": searched (pending), partial, grabbed-with-detail
        (_SEED_TIMESTAMP, "Sonarr", "missing", "Old Show A", "searched", "", 1, 1, 2, "Old"),
        (_SEED_TIMESTAMP, "Sonarr", "missing", "Old Show B", "partial", "partial: 1/2 episodes", 2, 1, 2, "Old"),
        (_SEED_TIMESTAMP, "Sonarr", "missing", "Old Show C", "grabbed", "grabbed: 2/2 episodes", 3, 1, 2, "Old"),
        # Sonarr "Gone": an instance no longer configured (no mapping entry)
        (_SEED_TIMESTAMP, "Sonarr", "missing", "Gone Show", "searched", "", 4, 1, 1, "Gone"),
        # Radarr "Default"
        (_SEED_TIMESTAMP, "Radarr", "missing", "Movie A", "grabbed", "grabbed", 5, None, None, "Default"),
        # Lidarr "Default" (never associated by any mapping in this phase)
        (_SEED_TIMESTAMP, "Lidarr", "missing", "Album A", "grabbed", "grabbed", 6, None, None, "Default"),
    ]
    for row in rows:
        await db.execute(
            "INSERT INTO search_history "
            "(timestamp, app, queue_type, item_name, outcome, detail, item_id, "
            "season_number, missing_count, instance_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
    await db.commit()


async def _seed_lifetime_stats(db: aiosqlite.Connection) -> None:
    # Default seed rows (Radarr/Sonarr/Lidarr "Default") already exist from
    # migrations v3/v7/v9 -- give them non-zero counters.
    await db.execute(
        "UPDATE lifetime_stats SET episodes_found = 4, episodes_updated = 1 "
        "WHERE app = 'Sonarr' AND instance_id = 'Default'"
    )
    await db.execute(
        "UPDATE lifetime_stats SET movies_found = 5, movies_updated = 2 "
        "WHERE app = 'Radarr' AND instance_id = 'Default'"
    )
    await db.execute(
        "UPDATE lifetime_stats SET albums_found = 7, albums_updated = 3 "
        "WHERE app = 'Lidarr' AND instance_id = 'Default'"
    )
    # New rows for the non-default named instances.
    await db.execute(
        "INSERT INTO lifetime_stats (app, instance_id, episodes_found, episodes_updated, last_reset_at) "
        "VALUES ('Sonarr', 'Old', 3, 1, ?)",
        (_SEED_TIMESTAMP,),
    )
    await db.execute(
        "INSERT INTO lifetime_stats (app, instance_id, episodes_found, episodes_updated, last_reset_at) "
        "VALUES ('Sonarr', 'Gone', 2, 0, ?)",
        (_SEED_TIMESTAMP,),
    )
    await db.commit()


async def _typed_rows(db: aiosqlite.Connection, table: str) -> list[tuple[Any, ...]]:
    """Return every row of *table* ordered by primary key, each value paired with its typeof()."""
    async with db.execute(f"PRAGMA table_info({table})") as cursor:
        columns = [row[1] for row in await cursor.fetchall()]
    select_cols = ", ".join(columns)
    typeof_cols = ", ".join(f"typeof({c})" for c in columns)
    order_by = "id" if table == "search_history" else "app, instance_id"
    async with db.execute(f"SELECT {select_cols}, {typeof_cols} FROM {table} ORDER BY {order_by}") as cursor:
        rows = await cursor.fetchall()
    n = len(columns)
    return [tuple(row[:n]) + tuple(row[n:]) for row in rows]


async def original_projection(db: aiosqlite.Connection) -> dict[str, list[tuple[Any, ...]]]:
    """Return only the v9 columns of search_history and lifetime_stats, in the same order."""
    async with db.execute(
        "SELECT id, timestamp, app, queue_type, item_name, outcome, detail, item_id, "
        "season_number, missing_count, resolved_at, instance_id "
        "FROM search_history ORDER BY id"
    ) as cursor:
        search_history = [tuple(row) for row in await cursor.fetchall()]
    async with db.execute(
        "SELECT app, instance_id, movies_found, movies_updated, episodes_found, episodes_updated, "
        "last_reset_at, albums_found, albums_updated "
        "FROM lifetime_stats ORDER BY app, instance_id"
    ) as cursor:
        lifetime_stats = [tuple(row) for row in await cursor.fetchall()]
    return {"search_history": search_history, "lifetime_stats": lifetime_stats}


async def counter_sums(db: aiosqlite.Connection) -> dict[str, tuple[int, ...]]:
    """Return per-app SUM of every lifetime_stats counter column."""
    async with db.execute(
        "SELECT app, SUM(movies_found), SUM(movies_updated), SUM(episodes_found), "
        "SUM(episodes_updated), SUM(albums_found), SUM(albums_updated) "
        "FROM lifetime_stats GROUP BY app ORDER BY app"
    ) as cursor:
        rows = await cursor.fetchall()
    return {row[0]: tuple(row[1:]) for row in rows}


async def snapshot(db: aiosqlite.Connection) -> dict[str, Any]:
    """Capture enough state to prove the database is byte-for-value unchanged after reopening."""
    version = await get_schema_version(db)
    async with db.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name") as cursor:
        master = [tuple(row) for row in await cursor.fetchall()]
    async with db.execute("PRAGMA table_info(search_history)") as cursor:
        sh_columns = [tuple(row) for row in await cursor.fetchall()]
    async with db.execute("PRAGMA table_info(lifetime_stats)") as cursor:
        ls_columns = [tuple(row) for row in await cursor.fetchall()]

    result: dict[str, Any] = {
        "schema_version": version,
        "sqlite_master": master,
        "search_history_columns": sh_columns,
        "lifetime_stats_columns": ls_columns,
        "search_history_rows": await _typed_rows(db, "search_history"),
        "lifetime_stats_rows": await _typed_rows(db, "lifetime_stats"),
    }

    async with db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'lifetime_stats_v10'"
    ) as cursor:
        has_leftover = await cursor.fetchone() is not None
    if has_leftover:
        async with db.execute("PRAGMA table_info(lifetime_stats_v10)") as cursor:
            result["lifetime_stats_v10_columns"] = [tuple(row) for row in await cursor.fetchall()]
        result["lifetime_stats_v10_rows"] = await _typed_rows(db, "lifetime_stats_v10")
    return result


# ---------------------------------------------------------------------------
# Fault injection
# ---------------------------------------------------------------------------

# Each regex is matched against the whitespace-normalized SQL text (runs of
# whitespace collapsed to one space, stripped) of every statement v10
# executes.  before_commit has no SQL text to match -- it fails the first
# commit() call issued after BEGIN IMMEDIATE has started (see
# inject_v10_failure below).
V10_FAULT_POINTS: dict[str, re.Pattern[str] | None] = {
    "create_grab_ownership": re.compile(r"^CREATE TABLE IF NOT EXISTS grab_ownership\b"),
    "index_grab_ownership_series": re.compile(r"^CREATE INDEX IF NOT EXISTS idx_grab_ownership_series\b"),
    "add_search_history_column": re.compile(r"^ALTER TABLE search_history ADD COLUMN instance_stable_id\b"),
    "index_search_history_stable_id": re.compile(
        r"^CREATE INDEX IF NOT EXISTS idx_search_history_instance_stable_id\b"
    ),
    "create_replacement": re.compile(r"^CREATE TABLE lifetime_stats_v10\b"),
    "copy": re.compile(r"^INSERT INTO lifetime_stats_v10\b"),
    "drop_original": re.compile(r"^DROP TABLE lifetime_stats$"),
    "rename": re.compile(r"^ALTER TABLE lifetime_stats_v10 RENAME TO lifetime_stats$"),
    "associate_search_history": re.compile(r"^UPDATE search_history SET instance_stable_id = \?"),
    "associate_lifetime_stats": re.compile(r"^UPDATE lifetime_stats SET instance_stable_id = \?"),
    "index_lifetime_stats_stable_id": re.compile(
        r"^CREATE UNIQUE INDEX IF NOT EXISTS idx_lifetime_stats_app_stable_id\b"
    ),
    "record_version": re.compile(r"^UPDATE schema_version SET version = \?"),
    "before_commit": None,
}

def _normalize_sql(sql: Any) -> str:
    if not isinstance(sql, str):
        return ""
    return re.sub(r"\s+", " ", sql).strip()


class FaultState:
    """Mutable record of whether the injected fault actually fired."""

    def __init__(self) -> None:
        self.fired = False
        self.began_transaction = False


def inject_v10_failure(monkeypatch: Any, db: aiosqlite.Connection, point: str) -> FaultState:
    """Make the v10 migration fail at *point*, the first time matching SQL executes.

    Replaces ``db.execute`` on the instance with a plain wrapper that calls
    the original and returns its result, except that the first statement
    whose normalized SQL matches the point's regex raises
    ``sqlite3.OperationalError`` synchronously and records that it fired --
    so a point the implementation never reaches cannot pass a test silently.
    For "before_commit", ``db.commit`` is also replaced so the first commit
    issued after BEGIN IMMEDIATE has started raises the same error (earlier
    commits, such as init_db's own, pass through untouched).
    """
    state = FaultState()
    pattern = V10_FAULT_POINTS[point]
    original_execute = db.execute
    original_commit = db.commit

    def fake_execute(sql: Any, parameters: Any = None) -> Any:
        normalized = _normalize_sql(sql)
        if point == "before_commit" and normalized == "BEGIN IMMEDIATE":
            state.began_transaction = True
        if pattern is not None and not state.fired and pattern.search(normalized):
            state.fired = True
            msg = f"injected failure at {point}"
            raise sqlite3.OperationalError(msg)
        return original_execute(sql, parameters)

    async def fake_commit() -> None:
        if point == "before_commit" and state.began_transaction and not state.fired:
            state.fired = True
            msg = f"injected failure at {point}"
            raise sqlite3.OperationalError(msg)
        await original_commit()

    monkeypatch.setattr(db, "execute", fake_execute)
    monkeypatch.setattr(db, "commit", fake_commit)
    return state
