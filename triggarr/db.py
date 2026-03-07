"""SQLite-backed search history persistence.

Replaces the in-memory bounded search_log list with durable storage
on the /config volume.  Uses aiosqlite for async access with a
connection-per-operation pattern (lightweight for local file I/O).
"""

from __future__ import annotations

import contextlib
import math
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
from loguru import logger

DB_PATH = Path("/config/triggarr.db")


async def init_db(db_path: Path = DB_PATH) -> None:
    """Create the search_history table and index if they do not exist.

    Args:
        db_path: Path to the SQLite database file.
    """
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                app TEXT NOT NULL,
                queue_type TEXT NOT NULL,
                item_name TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_search_history_timestamp
            ON search_history(timestamp DESC)
            """
        )
        await db.commit()
    await _migrate_add_outcome_columns(db_path)
    logger.debug("Search history database initialized at {path}", path=db_path)


async def _migrate_add_outcome_columns(db_path: Path) -> None:
    """Add outcome and detail columns to search_history if they do not exist.

    Each ALTER is wrapped in try/except to handle the case where the
    column already exists (SQLite raises "duplicate column name").

    Args:
        db_path: Path to the SQLite database file.
    """
    async with aiosqlite.connect(db_path) as db:
        for col, default in (("outcome", "NULL"), ("detail", "NULL")):
            with contextlib.suppress(Exception):
                await db.execute(
                    f"ALTER TABLE search_history ADD COLUMN {col} TEXT DEFAULT {default}"
                )
        await db.commit()


async def insert_search_entry(
    db_path: Path,
    app: str,
    queue_type: str,
    item_name: str,
    *,
    outcome: str = "searched",
    detail: str = "",
) -> None:
    """Insert a search log entry and prune old rows beyond 500.

    Args:
        db_path: Path to the SQLite database file.
        app: Application name (e.g. "Radarr", "Sonarr").
        queue_type: Queue type (e.g. "missing", "cutoff").
        item_name: Human-readable name of the searched item.
        outcome: Search outcome (e.g. "searched", "failed").
        detail: Additional detail text (e.g. error message).
    """
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO search_history (timestamp, app, queue_type, item_name, outcome, detail) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (timestamp, app, queue_type, item_name, outcome, detail),
        )
        await db.execute(
            """
            DELETE FROM search_history
            WHERE id NOT IN (
                SELECT id FROM search_history ORDER BY id DESC LIMIT 500
            )
            """
        )
        await db.commit()


async def get_recent_searches(db_path: Path, limit: int = 50) -> list[dict]:
    """Return the most recent search history entries.

    Args:
        db_path: Path to the SQLite database file.
        limit: Maximum number of entries to return.

    Returns:
        List of dicts with keys: name, timestamp, app, queue_type, outcome, detail.
        Ordered newest-first (by id DESC).
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT timestamp, app, queue_type, item_name, outcome, detail "
            "FROM search_history ORDER BY id DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
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
    db_path: Path,
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
        db_path: Path to the SQLite database file.
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

    async with aiosqlite.connect(db_path) as db:
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


async def migrate_from_state(db_path: Path, search_log: list[dict]) -> int:
    """Migrate search_log entries from state.json into SQLite.

    Args:
        db_path: Path to the SQLite database file.
        search_log: List of dicts with name, timestamp, app, queue_type keys.

    Returns:
        Number of entries migrated.
    """
    if not search_log:
        return 0

    async with aiosqlite.connect(db_path) as db:
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
