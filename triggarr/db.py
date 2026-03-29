"""SQLite-backed search history persistence.

All public functions accept an ``aiosqlite.Connection`` instead of a
``Path``, so callers share a single long-lived connection opened during
the application lifespan.  A versioned migration system ensures safe,
logged, version-tracked schema evolution with backup-before-migrate.
"""

from __future__ import annotations

import contextlib
import math
import re
import shutil
import sqlite3
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite
from loguru import logger

# Migration registry: version -> (description, migration_fn)
# Populated after migration functions are defined below.
MIGRATIONS: dict[int, tuple[str, Callable[[aiosqlite.Connection], Awaitable[None]]]] = {}


# ---------------------------------------------------------------------------
# Schema version helpers
# ---------------------------------------------------------------------------


async def get_schema_version(db: aiosqlite.Connection) -> int:
    """Read current schema version from schema_version table."""
    await db.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL DEFAULT 0)")
    async with db.execute("SELECT version FROM schema_version") as cursor:
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
    if db_path.exists():
        shutil.copy2(db_path, backup_path)
        logger.info("Database backed up to {path}", path=backup_path)
    for version in sorted(MIGRATIONS.keys()):
        if version <= current:
            continue
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
    for col, default in (("outcome", "'searched'"), ("detail", "NULL")):
        with contextlib.suppress(sqlite3.OperationalError):
            await db.execute(f"ALTER TABLE search_history ADD COLUMN {col} TEXT DEFAULT {default}")
    await db.commit()


async def _migrate_v2(db: aiosqlite.Connection) -> None:
    """Add item_id, season_number, missing_count columns for tracking correlation."""
    for col, col_type in (("item_id", "INTEGER"), ("season_number", "INTEGER"), ("missing_count", "INTEGER")):
        with contextlib.suppress(sqlite3.OperationalError):
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


async def _migrate_v5(db: aiosqlite.Connection) -> None:
    """Add resolved_at column for time-to-grab calculation."""
    with contextlib.suppress(sqlite3.OperationalError):
        await db.execute("ALTER TABLE search_history ADD COLUMN resolved_at TEXT DEFAULT NULL")
    await db.commit()


async def _migrate_v6(db: aiosqlite.Connection) -> None:
    """Add instance_id column to search_history for multi-instance scoping."""
    with contextlib.suppress(sqlite3.OperationalError):
        await db.execute("ALTER TABLE search_history ADD COLUMN instance_id TEXT DEFAULT 'Default'")
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_search_history_instance_id "
        "ON search_history(instance_id, timestamp DESC)"
    )
    await db.commit()


async def _migrate_v7(db: aiosqlite.Connection) -> None:
    """Rebuild lifetime_stats with composite (app, instance_id) primary key."""
    # 1. Create new table with composite key
    await db.execute("""
        CREATE TABLE IF NOT EXISTS lifetime_stats_new (
            app TEXT NOT NULL,
            instance_id TEXT NOT NULL DEFAULT 'Default',
            movies_found INTEGER NOT NULL DEFAULT 0,
            movies_updated INTEGER NOT NULL DEFAULT 0,
            episodes_found INTEGER NOT NULL DEFAULT 0,
            episodes_updated INTEGER NOT NULL DEFAULT 0,
            last_reset_at TEXT NOT NULL,
            PRIMARY KEY (app, instance_id)
        )
    """)
    # 2. Copy existing rows with instance_id='Default'
    await db.execute("""
        INSERT OR IGNORE INTO lifetime_stats_new
            (app, instance_id, movies_found, movies_updated, episodes_found, episodes_updated, last_reset_at)
        SELECT app, 'Default', movies_found, movies_updated, episodes_found, episodes_updated, last_reset_at
        FROM lifetime_stats
    """)
    # 3. Drop old table, rename new
    await db.execute("DROP TABLE lifetime_stats")
    await db.execute("ALTER TABLE lifetime_stats_new RENAME TO lifetime_stats")
    await db.commit()


async def _migrate_v8(db: aiosqlite.Connection) -> None:
    """Recompute episode stats from search_history to fix double-counting bug.

    Prior to this fix, expired partial Sonarr entries re-incremented
    episodes_found/episodes_updated on every tracking cycle.  This migration
    recomputes the correct totals from search_history detail strings and
    also renames any 'partial' entries with '(window expired)' in their
    detail to the new 'partial_expired' terminal outcome.
    """
    # 1. Rename lingering partial entries that already expired to partial_expired
    await db.execute(
        "UPDATE search_history SET outcome = 'partial_expired' "
        "WHERE outcome = 'partial' AND detail LIKE '%(window expired)%'"
    )

    # 2. Recompute episode stats from resolved search_history entries.
    #    For Sonarr grabbed/partial_expired, parse grab_count from detail string
    #    (format: "grabbed: N/M episodes" or "partial: N/M episodes (window expired)")
    #    For entries without parseable counts, use missing_count or 1 as fallback.
    async with db.execute(
        "SELECT app, instance_id, queue_type, outcome, detail, missing_count "
        "FROM search_history "
        "WHERE app = 'Sonarr' AND outcome IN ('grabbed', 'partial_expired')"
    ) as cursor:
        rows = await cursor.fetchall()

    # Accumulate correct totals per (app, instance_id)
    episode_stats: dict[tuple[str, str], dict[str, int]] = {}
    for row in rows:
        app, inst, queue_type, outcome, detail, missing_count = row
        key = (app, inst or "Default")
        if key not in episode_stats:
            episode_stats[key] = {"episodes_found": 0, "episodes_updated": 0}

        stat_col = "episodes_found" if queue_type == "missing" else "episodes_updated"

        # Parse grab count from detail string
        count = 0
        if detail:
            # Match patterns like "grabbed: 3/5 episodes" or "partial: 2/5 episodes"
            m = re.search(r"(?:grabbed|partial):\s*(\d+)", detail)
            if m:
                count = int(m.group(1))
        if count == 0:
            # Fallback: use missing_count or 1
            count = missing_count if missing_count and missing_count > 0 else 1

        episode_stats[key][stat_col] += count

    # 3. Reset and reapply episode stats
    for (app, inst), stats in episode_stats.items():
        await db.execute(
            "UPDATE lifetime_stats SET episodes_found = ?, episodes_updated = ? "
            "WHERE app = ? AND instance_id = ?",
            (stats["episodes_found"], stats["episodes_updated"], app, inst),
        )

    await db.commit()
    total_fixed = len(rows)
    logger.info("Recomputed episode stats from {n} Sonarr entries", n=total_fixed)


# Register migrations after functions are defined
MIGRATIONS = {
    1: ("add outcome and detail columns", _migrate_v1),
    2: ("add item_id, season_number, missing_count columns", _migrate_v2),
    3: ("create lifetime_stats table", _migrate_v3),
    4: ("backfill existing rows as unresolved", _migrate_v4),
    5: ("add resolved_at column for time-to-grab", _migrate_v5),
    6: ("add instance_id to search_history", _migrate_v6),
    7: ("rebuild lifetime_stats with composite key", _migrate_v7),
    8: ("recompute episode stats and fix partial_expired outcomes", _migrate_v8),
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
    # Set row_factory globally so all queries return Row objects (dict-like access)
    # instead of plain tuples. This eliminates per-function row_factory mutation.
    db.row_factory = aiosqlite.Row

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
    instance_id: str = "Default",
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
        instance_id: Instance name for multi-instance scoping.
        max_rows: Maximum resolved rows to keep (pending rows are exempt).
    """
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    await db.execute(
        "INSERT INTO search_history "
        "(timestamp, app, queue_type, item_name, outcome, detail, item_id, season_number, missing_count, instance_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (timestamp, app, queue_type, item_name, outcome, detail, item_id, season_number, missing_count, instance_id),
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


async def get_recent_searches(
    db: aiosqlite.Connection, limit: int = 50, *, instance_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return the most recent search history entries.

    Args:
        db: Open aiosqlite connection.
        limit: Maximum number of entries to return.
        instance_id: If set, filter to entries from this instance only.

    Returns:
        List of dicts with keys: name, timestamp, app, queue_type, outcome, detail, instance_id.
        Ordered newest-first (by id DESC).
    """
    if instance_id is not None:
        query = (
            "SELECT timestamp, app, queue_type, item_name, outcome, detail, instance_id "
            "FROM search_history WHERE instance_id = ? ORDER BY id DESC LIMIT ?"
        )
        params: tuple[str | int, ...] = (instance_id, limit)
    else:
        query = (
            "SELECT timestamp, app, queue_type, item_name, outcome, detail, instance_id "
            "FROM search_history ORDER BY id DESC LIMIT ?"
        )
        params = (limit,)
    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
    return [
        {
            "name": row["item_name"],
            "timestamp": row["timestamp"],
            "app": row["app"],
            "queue_type": row["queue_type"],
            "outcome": row["outcome"] or "searched",
            "detail": row["detail"] or "",
            "instance_id": row["instance_id"] or "Default",
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
    instance_filter: list[str] | None = None,
    search_text: str = "",
) -> dict[str, Any]:
    """Return paginated, filtered search history entries.

    Args:
        db: Open aiosqlite connection.
        page: 1-based page number.
        per_page: Number of entries per page.
        app_filter: Filter on app column (e.g. ["Radarr", "Sonarr"]).
        queue_filter: Filter on queue_type column (e.g. ["missing", "cutoff"]).
        outcome_filter: Filter on outcome column (e.g. ["searched", "failed"]).
        instance_filter: Filter on instance_id column (e.g. ["4K", "Default"]).
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
        # Expand "partial" to include "partial_expired" (terminal partial state)
        expanded = list(outcome_filter)
        if "partial" in expanded and "partial_expired" not in expanded:
            expanded.append("partial_expired")
        placeholders = ", ".join("?" for _ in expanded)
        conditions.append(f"COALESCE(outcome, 'searched') IN ({placeholders})")
        params.extend(expanded)

    if instance_filter:
        placeholders = ", ".join("?" for _ in instance_filter)
        conditions.append(f"instance_id IN ({placeholders})")
        params.extend(instance_filter)

    if search_text:
        conditions.append("item_name LIKE ?")
        params.append(f"%{search_text}%")

    where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""

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
        f"SELECT id, timestamp, app, queue_type, item_name, outcome, detail, instance_id "
        f"FROM search_history{where_clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        [*params, per_page, offset],
    ) as cursor:
        rows = await cursor.fetchall()

    entries = [
        {
            "id": row["id"],
            "name": row["item_name"],
            "timestamp": row["timestamp"],
            "app": row["app"],
            "queue_type": row["queue_type"],
            "outcome": row["outcome"] or "searched",
            "detail": row["detail"] or "",
            "instance_id": row["instance_id"] or "Default",
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


async def get_trackable_entries(
    db: aiosqlite.Connection, *, instance_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return search history entries eligible for tracking resolution.

    Finds rows with outcome ``'searched'`` or ``'partial'`` that have a
    non-null ``item_id`` (entries without an item_id cannot be correlated
    with grab events).

    Args:
        db: Open aiosqlite connection.
        instance_id: If set, filter to entries from this instance only.

    Returns:
        List of dicts ordered by ``id ASC`` (oldest first) with keys:
        id, app, queue_type, item_id, season_number, missing_count, timestamp,
        outcome, instance_id.
    """
    base = (
        "SELECT id, app, queue_type, item_id, season_number, missing_count, "
        "timestamp, outcome, instance_id "
        "FROM search_history "
        "WHERE outcome IN ('searched', 'partial') AND item_id IS NOT NULL"
    )
    if instance_id is not None:
        query = f"{base} AND instance_id = ? ORDER BY id ASC"
        params: tuple[str | int, ...] = (instance_id,)
    else:
        query = f"{base} ORDER BY id ASC"
        params = ()
    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
    result = [
        {
            "id": row["id"],
            "app": row["app"],
            "queue_type": row["queue_type"],
            "item_id": row["item_id"],
            "season_number": row["season_number"],
            "missing_count": row["missing_count"],
            "timestamp": row["timestamp"],
            "outcome": row["outcome"],
            "instance_id": row["instance_id"] or "Default",
        }
        for row in rows
    ]
    logger.debug("Found {count} trackable entries", count=len(result))
    return result


_ALLOWED_STAT_COLUMNS = frozenset({"movies_found", "movies_updated", "episodes_found", "episodes_updated"})


async def update_outcome_and_stats(
    db: aiosqlite.Connection,
    history_id: int,
    outcome: str,
    detail: str,
    *,
    app: str,
    queue_type: str,
    instance_id: str = "Default",
    stat_increments: dict[str, int] | None = None,
) -> None:
    """Atomically update a search entry's outcome and increment lifetime stats.

    Performs both updates in a single transaction so that a crash between the
    outcome write and the stats write cannot leave the database inconsistent.

    Args:
        db: Open aiosqlite connection.
        history_id: Primary key of the search_history row to update.
        outcome: New outcome value (e.g. "grabbed", "partial", "unresolved").
        detail: Human-readable detail string.
        app: Application name for lifetime_stats lookup.
        queue_type: Queue type (unused in SQL, kept for caller convenience/logging).
        instance_id: Instance name for lifetime_stats composite key lookup.
        stat_increments: Optional mapping of column name to increment value,
            e.g. ``{"movies_found": 1}``.  Only columns in lifetime_stats are
            allowed; a ``ValueError`` is raised for unknown column names.

    Raises:
        ValueError: If *stat_increments* contains a column name not in
            ``{movies_found, movies_updated, episodes_found, episodes_updated}``.
    """
    if stat_increments:
        unknown = set(stat_increments.keys()) - _ALLOWED_STAT_COLUMNS
        if unknown:
            msg = f"Unknown stat column(s): {', '.join(sorted(unknown))}"
            raise ValueError(msg)

    # 1. Update outcome and resolved_at timestamp
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    await db.execute(
        "UPDATE search_history SET outcome = ?, detail = ?, resolved_at = ? WHERE id = ?",
        (outcome, detail, now, history_id),
    )

    # 2. Increment lifetime stats (if any) using composite key (app, instance_id)
    if stat_increments:
        # Ensure the stats row exists for this app+instance combo
        await db.execute(
            "INSERT OR IGNORE INTO lifetime_stats (app, instance_id, last_reset_at) VALUES (?, ?, ?)",
            (app, instance_id, now),
        )
        set_parts = [f"{col} = {col} + ?" for col in stat_increments]
        values = [*stat_increments.values(), app, instance_id]
        await db.execute(
            f"UPDATE lifetime_stats SET {', '.join(set_parts)} WHERE app = ? AND instance_id = ?",  # noqa: S608
            values,
        )

    # 3. Single commit for the whole transaction
    await db.commit()
    logger.debug(
        "Updated history_id={hid} outcome={out} instance={inst} stats={stats}",
        hid=history_id,
        out=outcome,
        inst=instance_id,
        stats=stat_increments or {},
    )


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


async def get_dashboard_stats(db: aiosqlite.Connection, *, instance_id: str | None = None) -> dict[str, Any]:
    """Compute aggregate dashboard statistics from search_history and lifetime_stats.

    Args:
        db: Open aiosqlite connection.
        instance_id: If set, scope stats to this instance only.

    Returns:
        Dict with keys: overall_rate, radarr_rate, sonarr_rate, movies_found,
        movies_updated, episodes_found, episodes_updated, avg_time_to_grab_seconds.
        Rate values are percentages (0-100) or None if no data.
    """
    # Build optional instance filter clause
    inst_clause = ""
    inst_params: tuple = ()
    if instance_id is not None:
        inst_clause = " AND instance_id = ?"
        inst_params = (instance_id,)

    # 1. Effectiveness: grab rate per app
    async with db.execute(
        "SELECT app, "
        "SUM(CASE WHEN outcome IN ('grabbed', 'partial', 'partial_expired') THEN 1 ELSE 0 END) AS grabbed_count, "
        "SUM(CASE WHEN outcome != 'failed' THEN 1 ELSE 0 END) AS total_count "
        "FROM search_history "
        f"WHERE outcome IS NOT NULL{inst_clause} "
        "GROUP BY app",
        inst_params,
    ) as cursor:
        effectiveness_rows = await cursor.fetchall()

    total_grabbed = 0
    total_count = 0
    radarr_rate: float | None = None
    sonarr_rate: float | None = None

    for row in effectiveness_rows:
        app_name = row["app"]
        grabbed = row["grabbed_count"]
        count = row["total_count"]
        total_grabbed += grabbed
        total_count += count
        if count > 0:
            rate = (grabbed / count) * 100
            if app_name.lower() == "radarr":
                radarr_rate = rate
            elif app_name.lower() == "sonarr":
                sonarr_rate = rate

    overall_rate: float | None = (total_grabbed / total_count * 100) if total_count > 0 else None

    # 2. Lifetime stats
    movies_found = 0
    movies_updated = 0
    episodes_found = 0
    episodes_updated = 0

    if instance_id is not None:
        stats_query = (
            "SELECT movies_found, movies_updated, episodes_found, episodes_updated "
            "FROM lifetime_stats WHERE instance_id = ?"
        )
        stats_params: tuple[str | int, ...] = (instance_id,)
    else:
        stats_query = "SELECT movies_found, movies_updated, episodes_found, episodes_updated FROM lifetime_stats"
        stats_params = ()
    async with db.execute(stats_query, stats_params) as cursor:
        stats_rows = await cursor.fetchall()

    for row in stats_rows:
        movies_found += row["movies_found"]
        movies_updated += row["movies_updated"]
        episodes_found += row["episodes_found"]
        episodes_updated += row["episodes_updated"]

    # 3. Time-to-grab average
    async with db.execute(
        "SELECT AVG((julianday(resolved_at) - julianday(timestamp)) * 86400) AS avg_seconds "
        "FROM search_history "
        f"WHERE outcome = 'grabbed' AND resolved_at IS NOT NULL{inst_clause}",
        inst_params,
    ) as cursor:
        ttg_row = await cursor.fetchone()

    avg_seconds: float | None = ttg_row[0] if ttg_row and ttg_row[0] is not None else None

    return {
        "overall_rate": overall_rate,
        "radarr_rate": radarr_rate,
        "sonarr_rate": sonarr_rate,
        "movies_found": movies_found,
        "movies_updated": movies_updated,
        "episodes_found": episodes_found,
        "episodes_updated": episodes_updated,
        "avg_time_to_grab_seconds": avg_seconds,
    }
