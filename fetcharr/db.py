"""SQLite-backed search history persistence.

All public functions accept an ``aiosqlite.Connection`` instead of a
``Path``, so callers share a single long-lived connection opened during
the application lifespan.  A versioned migration system ensures safe,
logged, version-tracked schema evolution with backup-before-migrate.
"""

from __future__ import annotations

import contextlib
import math
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
from loguru import logger

# Migration registry: version -> (description, migration_fn)
# Populated after migration functions are defined below.
MIGRATIONS: dict[int, tuple[str, Callable]] = {}


# ---------------------------------------------------------------------------
# Schema version helpers
# ---------------------------------------------------------------------------


async def get_schema_version(db: aiosqlite.Connection) -> int:
    """Read current schema version from schema_version table."""
    await db.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL DEFAULT 0)")
    cursor = await db.execute("SELECT version FROM schema_version")
    row = await cursor.fetchone()
    if row is None:
        await db.execute("INSERT INTO schema_version (version) VALUES (0)")
        await db.commit()
        return 0
    return row[0]


async def set_schema_version(db: aiosqlite.Connection, version: int) -> None:
    """Update the stored schema version."""
    await db.execute("UPDATE schema_version SET version = ?", (version,))
    await db.commit()


async def run_migrations(db: aiosqlite.Connection, db_path: Path) -> None:
    """Run pending schema migrations with backup-before-migrate."""
    current = await get_schema_version(db)
    if not MIGRATIONS:
        return
    target = max(MIGRATIONS.keys())
    if current >= target:
        logger.debug("Schema is up to date (v{v})", v=current)
        return
    # Backup before first migration (user decision: backup-before-migrate)
    backup_path = db_path.with_suffix(f".v{current}-backup")
    shutil.copy2(db_path, backup_path)
    logger.info("Database backed up to {path}", path=backup_path)
    for version in range(current + 1, target + 1):
        desc, fn = MIGRATIONS[version]
        logger.info("Migrating schema v{old} -> v{new}: {desc}", old=version - 1, new=version, desc=desc)
        await fn(db)
        await set_schema_version(db, version)
    logger.info("Schema migration complete (now v{v})", v=target)


# ---------------------------------------------------------------------------
# Migration functions
# ---------------------------------------------------------------------------


async def _migrate_v1(db: aiosqlite.Connection) -> None:
    """Add outcome and detail columns to search_history."""
    for col, default in (("outcome", "NULL"), ("detail", "NULL")):
        with contextlib.suppress(Exception):
            await db.execute(f"ALTER TABLE search_history ADD COLUMN {col} TEXT DEFAULT {default}")
    await db.commit()


async def _migrate_v2(db: aiosqlite.Connection) -> None:
    """Add item_id, season_number, missing_count columns for tracking correlation."""
    for col, col_type in (("item_id", "INTEGER"), ("season_number", "INTEGER"), ("missing_count", "INTEGER")):
        with contextlib.suppress(Exception):
            await db.execute(f"ALTER TABLE search_history ADD COLUMN {col} {col_type} DEFAULT NULL")
    await db.commit()


async def _migrate_v3(db: aiosqlite.Connection) -> None:
    """Create lifetime_stats table with seed rows for each app."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS lifetime_stats (
            app TEXT PRIMARY KEY,
            movies_found INTEGER NOT NULL DEFAULT 0,
            movies_updated INTEGER NOT NULL DEFAULT 0,
            episodes_found INTEGER NOT NULL DEFAULT 0,
            episodes_updated INTEGER NOT NULL DEFAULT 0,
            last_reset_at TEXT NOT NULL
        )
    """)
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    for app_name in ("Radarr", "Sonarr"):
        await db.execute(
            "INSERT OR IGNORE INTO lifetime_stats (app, last_reset_at) VALUES (?, ?)",
            (app_name, now),
        )
    await db.commit()


async def _migrate_v4(db: aiosqlite.Connection) -> None:
    """Backfill existing rows with NULL outcome to 'unresolved'."""
    cursor = await db.execute("UPDATE search_history SET outcome = 'unresolved' WHERE outcome IS NULL")
    await db.commit()
    logger.info("Backfilled {count} rows with outcome='unresolved'", count=cursor.rowcount)


# Register migrations after functions are defined
MIGRATIONS = {
    1: ("add outcome and detail columns", _migrate_v1),
    2: ("add item_id, season_number, missing_count columns", _migrate_v2),
    3: ("create lifetime_stats table", _migrate_v3),
    4: ("backfill existing rows as unresolved", _migrate_v4),
}


# ---------------------------------------------------------------------------
# Database init
# ---------------------------------------------------------------------------


async def init_db(db: aiosqlite.Connection, db_path: Path) -> None:
    """Create base tables, run migrations.

    Args:
        db: Open aiosqlite connection.
        db_path: Path to the SQLite database file (needed for backup).
    """
    await db.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            app TEXT NOT NULL,
            queue_type TEXT NOT NULL,
            item_name TEXT NOT NULL
        )
    """)
    await db.execute("""
        CREATE INDEX IF NOT EXISTS idx_search_history_timestamp
        ON search_history(timestamp DESC)
    """)
    await db.commit()
    await run_migrations(db, db_path)
    logger.debug("Search history database initialized at {path}", path=db_path)


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


async def insert_search_entry(
    db: aiosqlite.Connection,
    app: str,
    queue_type: str,
    item_name: str,
    *,
    outcome: str = "searched",
    detail: str = "",
    item_id: int | None = None,
    season_number: int | None = None,
    missing_count: int | None = None,
    max_rows: int = 1000,
) -> None:
    """Insert a search log entry and prune resolved rows beyond *max_rows*.

    Args:
        db: Open aiosqlite connection.
        app: Application name (e.g. "Radarr", "Sonarr").
        queue_type: Queue type (e.g. "missing", "cutoff").
        item_name: Human-readable name of the searched item.
        outcome: Search outcome (e.g. "searched", "failed", "grabbed").
        detail: Additional detail text (e.g. error message).
        item_id: *arr item ID for tracking correlation.
        season_number: Season number (Sonarr only).
        missing_count: Number of missing episodes at search time (Sonarr only).
        max_rows: Maximum resolved rows to keep (pending rows are exempt).
    """
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    await db.execute(
        "INSERT INTO search_history "
        "(timestamp, app, queue_type, item_name, outcome, detail, item_id, season_number, missing_count) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (timestamp, app, queue_type, item_name, outcome, detail, item_id, season_number, missing_count),
    )
    # Tracking-aware pruning (DEBT-03): only prune resolved rows, preserve pending (outcome='searched')
    await db.execute(
        """
        DELETE FROM search_history
        WHERE COALESCE(outcome, 'searched') != 'searched'
        AND id NOT IN (
            SELECT id FROM search_history
            WHERE COALESCE(outcome, 'searched') != 'searched'
            ORDER BY id DESC LIMIT ?
        )
        """,
        (max_rows,),
    )
    await db.commit()


async def get_recent_searches(db: aiosqlite.Connection, limit: int = 50) -> list[dict]:
    """Return the most recent search history entries.

    Args:
        db: Open aiosqlite connection.
        limit: Maximum number of entries to return.

    Returns:
        List of dicts with keys: name, timestamp, app, queue_type, outcome, detail.
        Ordered newest-first (by id DESC).
    """
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT timestamp, app, queue_type, item_name, outcome, detail "
        "FROM search_history ORDER BY id DESC LIMIT ?",
        (limit,),
    ) as cursor:
        rows = await cursor.fetchall()
    db.row_factory = None
    return [
        {
            "name": row["item_name"],
            "timestamp": row["timestamp"],
            "app": row["app"],
            "queue_type": row["queue_type"],
            "outcome": row["outcome"] or "searched",
            "detail": row["detail"] or "",
        }
        for row in rows
    ]


async def get_search_history(
    db: aiosqlite.Connection,
    *,
    page: int = 1,
    per_page: int = 50,
    app_filter: list[str] | None = None,
    queue_filter: list[str] | None = None,
    outcome_filter: list[str] | None = None,
    search_text: str = "",
) -> dict:
    """Return paginated, filtered search history entries.

    Args:
        db: Open aiosqlite connection.
        page: 1-based page number.
        per_page: Number of entries per page.
        app_filter: Filter on app column (e.g. ["Radarr", "Sonarr"]).
        queue_filter: Filter on queue_type column (e.g. ["missing", "cutoff"]).
        outcome_filter: Filter on outcome column (e.g. ["searched", "failed"]).
        search_text: Case-insensitive substring match on item_name.

    Returns:
        Dict with keys: entries, total, page, per_page, total_pages.
    """
    if per_page < 1:
        per_page = 50
    if page < 1:
        page = 1

    conditions: list[str] = []
    params: list[str | int] = []

    if app_filter:
        placeholders = ", ".join("?" for _ in app_filter)
        conditions.append(f"app IN ({placeholders})")
        params.extend(app_filter)

    if queue_filter:
        placeholders = ", ".join("?" for _ in queue_filter)
        conditions.append(f"queue_type IN ({placeholders})")
        params.extend(queue_filter)

    if outcome_filter:
        placeholders = ", ".join("?" for _ in outcome_filter)
        conditions.append(f"COALESCE(outcome, 'searched') IN ({placeholders})")
        params.extend(outcome_filter)

    if search_text:
        conditions.append("item_name LIKE ?")
        params.append(f"%{search_text}%")

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    db.row_factory = aiosqlite.Row

    # Total count
    async with db.execute(
        f"SELECT COUNT(*) AS cnt FROM search_history{where_clause}",
        params,
    ) as cursor:
        row = await cursor.fetchone()
        total_count: int = row["cnt"]

    # Paginated results
    offset = (page - 1) * per_page
    async with db.execute(
        f"SELECT id, timestamp, app, queue_type, item_name, outcome, detail "
        f"FROM search_history{where_clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        [*params, per_page, offset],
    ) as cursor:
        rows = await cursor.fetchall()

    db.row_factory = None

    entries = [
        {
            "id": row["id"],
            "name": row["item_name"],
            "timestamp": row["timestamp"],
            "app": row["app"],
            "queue_type": row["queue_type"],
            "outcome": row["outcome"] or "searched",
            "detail": row["detail"] or "",
        }
        for row in rows
    ]

    return {
        "entries": entries,
        "total": total_count,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total_count / per_page) or 1,
    }


async def migrate_from_state(db: aiosqlite.Connection, search_log: list[dict]) -> int:
    """Migrate search_log entries from state.json into SQLite.

    Args:
        db: Open aiosqlite connection.
        search_log: List of dicts with name, timestamp, app, queue_type keys.

    Returns:
        Number of entries migrated.
    """
    if not search_log:
        return 0

    for entry in search_log:
        await db.execute(
            "INSERT INTO search_history (timestamp, app, queue_type, item_name) VALUES (?, ?, ?, ?)",
            (
                entry.get("timestamp", ""),
                entry.get("app", ""),
                entry.get("queue_type", ""),
                entry.get("name", ""),
            ),
        )
    await db.commit()

    count = len(search_log)
    logger.info(
        "Migrated {count} search log entries from state.json to SQLite",
        count=count,
    )
    return count
