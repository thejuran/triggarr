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
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite
from loguru import logger

from triggarr.models.config import APP_TYPES

# SAFETY-01b: pending-row cap multiplier. The pending-row bound is
# PENDING_CAP_MULTIPLIER * max_rows (default 2 * 1000 = 2000). Headroom
# of 2x covers transient tracking backlog during normal operation while
# still bounding the stalled-tracker failure mode (Sonarr/Radarr
# unreachable for extended period -> pending rows accumulate forever).
# Kept as a module constant rather than a config field intentionally:
# operator-tunable would create a foot-gun (raise the cap -> disk fills).
PENDING_CAP_MULTIPLIER: int = 2


class PendingCapExceeded(Exception):
    """Raised by insert_search_entry when a pending insert would exceed the SAFETY-01b cap.

    The cap is ``PENDING_CAP_MULTIPLIER * max_rows`` (default 2 * 1000 = 2000).
    Carries the rejected entry's identifiers so callers can correlate the
    cap being hit with a specific stalled tracker.
    """

    def __init__(
        self,
        app: str,
        instance_id: str,
        item_name: str,
        pending_count: int,
        cap: int,
    ) -> None:
        self.app = app
        self.instance_id = instance_id
        self.item_name = item_name
        self.pending_count = pending_count
        self.cap = cap
        super().__init__(
            f"Pending-row cap reached for {app}/{instance_id}: "
            f"{pending_count} pending >= {cap} (rejecting {item_name!r})"
        )


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


# Versions that run inside the runner's own explicit transaction instead of
# committing themselves. sqlite3's legacy transaction control (the mode
# aiosqlite uses by default) only opens an implicit transaction before
# INSERT/UPDATE/DELETE statements, never before DDL -- a CREATE, DROP or
# ALTER issued with no transaction open commits itself immediately. v10
# rebuilds lifetime_stats (a DDL-heavy change), so it opens its own explicit
# transaction before any of its statements run and that same transaction
# also records the version, making the whole upgrade all-or-nothing. v1-v9
# deliberately keep committing themselves, exactly as they always have.
_ATOMIC_MIGRATIONS = frozenset({10})

# Versions whose migration function needs the name -> stable-instance-ID
# mapping (built from the already-backfilled config) in addition to the
# connection. Today this is the same set as _ATOMIC_MIGRATIONS, but the two
# concerns are independent, so they're tracked separately.
_MIGRATIONS_WITH_INSTANCE_IDS = frozenset({10})


class MigrationRecoveryError(RuntimeError):
    """Raised when a migration finds a leftover partial state it cannot safely resolve itself."""


async def _apply_atomic_migration(
    db: aiosqlite.Connection,
    version: int,
    fn: Callable[..., Awaitable[None]],
    *,
    instance_stable_ids: Mapping[tuple[str, str], str] | None,
    earliest_backup: Path | None,
) -> None:
    """Run one migration and its version record inside a single explicit transaction.

    Opens the transaction, runs the migration function, records the new
    schema version inline (not via set_schema_version, which would commit
    on its own), and issues the single commit for all of it. On any
    exception the transaction is rolled back, one error line is logged
    (never including any stable-ID value), and the original exception is
    re-raised so the caller's startup fails instead of continuing on a
    half-applied schema.

    Raises:
        RuntimeError: if a transaction is already open when this is called
            (fails closed rather than committing someone else's pending
            work).
    """
    if db.in_transaction:
        msg = f"migration v{version} cannot start: a transaction is already open"
        raise RuntimeError(msg)

    await db.execute("BEGIN IMMEDIATE")
    try:
        if version in _MIGRATIONS_WITH_INSTANCE_IDS:
            await fn(db, instance_stable_ids=instance_stable_ids or {})
        else:
            await fn(db)
        await db.execute("UPDATE schema_version SET version = ?", (version,))
        await db.commit()
    except Exception as exc:
        try:
            await db.rollback()
        except Exception as rollback_exc:
            logger.error(
                "Rollback after failed v{version} migration also failed: {exc_type}",
                version=version,
                exc_type=type(rollback_exc).__name__,
            )
        exc_detail = type(exc).__name__
        if isinstance(exc, MigrationRecoveryError):
            exc_detail = f"{exc_detail}: {exc}"
        backup_desc = str(earliest_backup) if earliest_backup is not None else "no backup: new database"
        logger.error(
            "Migration v{version} failed and was rolled back; schema remains at the previous "
            "version ({exc_detail}); restore from {backup} if recovery is needed",
            version=version,
            exc_detail=exc_detail,
            backup=backup_desc,
        )
        raise


async def run_migrations(
    db: aiosqlite.Connection,
    db_path: Path,
    *,
    instance_stable_ids: Mapping[tuple[str, str], str] | None = None,
) -> None:
    """Run pending schema migrations with backup-before-migrate.

    Args:
        db: Open aiosqlite connection.
        db_path: Path to the SQLite database file (needed for backup).
        instance_stable_ids: Optional mapping of (stored title-case app,
            instance name) -> stable instance ID, used only by migrations
            in ``_MIGRATIONS_WITH_INSTANCE_IDS`` (today, only v10). The
            caller's lifespan builds this from the already-backfilled
            config; ``None`` (fresh installs, most tests) means no
            association is attempted.
    """
    current = await get_schema_version(db)
    if not MIGRATIONS:
        return
    target = max(MIGRATIONS.keys())
    if current >= target:
        logger.debug("Schema is up to date (v{v})", v=current)
        return

    # Backup before first migration (user decision: backup-before-migrate).
    # The canonical backup name is never overwritten -- if it already exists
    # (e.g. a prior failed attempt), a second, timestamped backup is written
    # alongside it, so the recovery error below can always point at the
    # earliest backup taken before any failed attempt.
    backup_path = db_path.with_suffix(f".v{current}-backup")
    earliest_backup: Path | None = None
    if db_path.exists():
        if backup_path.exists():
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            timestamped_path = db_path.with_suffix(f".v{current}-backup-{stamp}")
            shutil.copy2(db_path, timestamped_path)
            logger.info(
                "Database backed up to {path} (earlier backup preserved at {earlier})",
                path=timestamped_path,
                earlier=backup_path,
            )
            earliest_backup = backup_path
        else:
            shutil.copy2(db_path, backup_path)
            logger.info("Database backed up to {path}", path=backup_path)
            earliest_backup = backup_path

    for version in sorted(MIGRATIONS.keys()):
        if version <= current:
            continue
        desc, fn = MIGRATIONS[version]
        logger.info("Migrating schema v{old} -> v{new}: {desc}", old=version - 1, new=version, desc=desc)
        if version in _ATOMIC_MIGRATIONS:
            await _apply_atomic_migration(
                db, version, fn, instance_stable_ids=instance_stable_ids, earliest_backup=earliest_backup
            )
        elif version in _MIGRATIONS_WITH_INSTANCE_IDS:
            await fn(db, instance_stable_ids=instance_stable_ids or {})
            await set_schema_version(db, version)
        else:
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


async def _migrate_v9(db: aiosqlite.Connection) -> None:
    """Add Lidarr album stat columns and seed row for lifetime_stats."""
    with contextlib.suppress(sqlite3.OperationalError):
        await db.execute("ALTER TABLE lifetime_stats ADD COLUMN albums_found INTEGER NOT NULL DEFAULT 0")
    with contextlib.suppress(sqlite3.OperationalError):
        await db.execute("ALTER TABLE lifetime_stats ADD COLUMN albums_updated INTEGER NOT NULL DEFAULT 0")
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    await db.execute(
        "INSERT OR IGNORE INTO lifetime_stats (app, instance_id, last_reset_at) VALUES (?, ?, ?)",
        ("Lidarr", "Default", now),
    )
    await db.commit()


# v9's exact lifetime_stats shape, used by the leftover-recovery check below:
# only when the live table still matches this shape is a leftover partial
# copy provably safe to discard.
_V9_LIFETIME_STATS_COLUMNS = frozenset({
    "app", "instance_id", "movies_found", "movies_updated",
    "episodes_found", "episodes_updated", "last_reset_at",
    "albums_found", "albums_updated",
})
_V9_LIFETIME_STATS_PK = ("app", "instance_id")


async def _v10_resolve_leftover_lifetime_stats(db: aiosqlite.Connection) -> None:
    """Resolve a leftover lifetime_stats_v10 from a previously interrupted upgrade attempt.

    Does nothing if no leftover table exists. If a leftover exists and the
    live lifetime_stats table still has the exact v9 column set and primary
    key, the leftover is a disposable partial copy and is dropped so the
    rebuild below can proceed. Otherwise the live table is missing or has
    some other shape -- which can only mean a prior attempt already dropped
    the original before this leftover could be confirmed safe -- so this
    raises before touching anything, naming both tables and pointing at the
    earliest pre-migration backup. This runs inside the caller's single
    transaction and therefore never finalizes anything on its own: it issues
    no transaction-ending statement, and an error here is never papered over.
    """
    async with db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'lifetime_stats_v10'"
    ) as cursor:
        leftover_exists = await cursor.fetchone() is not None
    if not leftover_exists:
        return

    async with db.execute("PRAGMA table_info(lifetime_stats)") as cursor:
        original_columns = await cursor.fetchall()

    original_is_v9_shape = False
    if original_columns:
        names = {row[1] for row in original_columns}
        pk_ordinal = {row[1]: row[5] for row in original_columns}
        original_is_v9_shape = (
            names == _V9_LIFETIME_STATS_COLUMNS
            and pk_ordinal.get("app") == 1
            and pk_ordinal.get("instance_id") == 2
            and all(pk_ordinal.get(col) == 0 for col in names if col not in _V9_LIFETIME_STATS_PK)
        )

    if not original_is_v9_shape:
        msg = (
            "lifetime_stats_v10 exists but lifetime_stats is missing or not in the expected shape; "
            "lifetime_stats_v10 may be the only surviving copy of lifetime totals and was not "
            "touched -- restore from the earliest pre-migration backup (the .v9-backup file next "
            "to the database) or inspect both tables before retrying"
        )
        raise MigrationRecoveryError(msg)

    await db.execute("DROP TABLE lifetime_stats_v10")
    logger.warning(
        "Discarded a leftover lifetime_stats_v10 partial copy from an interrupted upgrade "
        "(the original lifetime_stats was verified intact first)"
    )


async def _migrate_v10(db: aiosqlite.Connection, *, instance_stable_ids: Mapping[tuple[str, str], str]) -> None:
    """Add grab ownership, the attribution cutover marker and stable-ID association.

    The runner owns this migration's transaction and its version record
    (see _apply_atomic_migration): every statement below either runs or
    none of them do, together with the schema_version update that follows
    this function's return. Because of that, the "schema fully present but
    version still 9" state that an older, non-atomic build could leave
    cannot arise once a database has migrated through this path -- every
    guard below (table/index existence, a column-presence check before the
    lifetime_stats rebuild) exists only to make a *rerun* of this same
    transaction a no-op, not to recover from a partial version record that
    this runner never produces.

    Every change here is additive: a new nullable column on search_history,
    a key-widening rebuild of lifetime_stats that copies every existing
    value unchanged, and three new tables. No existing outcome, detail,
    counter or name is ever modified, and nothing is ever deleted from
    search_history or lifetime_stats.
    """
    if not db.in_transaction:
        msg = "migration v10 must run inside the runner's transaction"
        raise RuntimeError(msg)

    # Ownership: durable, independent of search_history so pruning or a
    # restart can never lose a credited grab. Deliberately no referential
    # constraint back to search_history -- ownership must outlive the
    # search row that earned it.
    await db.execute(
        "CREATE TABLE IF NOT EXISTS grab_ownership ("
        "app TEXT NOT NULL, instance_stable_id TEXT NOT NULL, grab_id INTEGER NOT NULL, "
        "history_id INTEGER NOT NULL, series_id INTEGER, season_number INTEGER, "
        "episode_id INTEGER, credited_at TEXT NOT NULL, "
        "PRIMARY KEY (app, instance_stable_id, grab_id))"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_grab_ownership_series "
        "ON grab_ownership(app, instance_stable_id, series_id)"
    )

    # Cutover bookkeeping: recorded later, exactly once, by
    # triggarr.attribution.ensure_cutover_recorded -- this migration only
    # creates the tables and never writes a row into either.
    await db.execute(
        "CREATE TABLE IF NOT EXISTS attribution_cutover ("
        "id INTEGER PRIMARY KEY CHECK (id = 1), cutover_at TEXT NOT NULL, "
        "legacy_max_history_id INTEGER NOT NULL, any_pre_fix_sonarr_data INTEGER NOT NULL, "
        "pre_fix_sonarr_lifetime INTEGER NOT NULL)"
    )
    await db.execute(
        "CREATE TABLE IF NOT EXISTS sonarr_instance_pre_fix ("
        "instance_stable_id TEXT PRIMARY KEY, has_pre_fix_data INTEGER NOT NULL, "
        "lifetime_includes_pre_fix INTEGER NOT NULL)"
    )

    # search_history gains the association column. Guarded by a column
    # check (not a suppressed error) so a rerun of this same transaction is
    # a no-op.
    async with db.execute("PRAGMA table_info(search_history)") as cursor:
        search_history_columns = await cursor.fetchall()
    if not any(row[1] == "instance_stable_id" for row in search_history_columns):
        await db.execute("ALTER TABLE search_history ADD COLUMN instance_stable_id TEXT")
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_search_history_instance_stable_id "
        "ON search_history(instance_stable_id)"
    )

    # Resolve any leftover partial copy from a previously interrupted
    # upgrade before attempting the rebuild below.
    await _v10_resolve_leftover_lifetime_stats(db)

    # lifetime_stats needs its primary key widened to include the stable
    # ID, which SQLite cannot do with ALTER TABLE -- so, like _migrate_v7,
    # this rebuilds the table with an explicit column copy. Guarded by a
    # column check so a rerun is a no-op. Every original value moves
    # across unchanged; nothing here is recomputed.
    async with db.execute("PRAGMA table_info(lifetime_stats)") as cursor:
        lifetime_stats_columns = await cursor.fetchall()
    if not any(row[1] == "instance_stable_id" for row in lifetime_stats_columns):
        await db.execute(
            "CREATE TABLE lifetime_stats_v10 ("
            "app TEXT NOT NULL, instance_id TEXT NOT NULL DEFAULT 'Default', "
            "instance_stable_id TEXT NOT NULL DEFAULT '', "
            "movies_found INTEGER NOT NULL DEFAULT 0, movies_updated INTEGER NOT NULL DEFAULT 0, "
            "episodes_found INTEGER NOT NULL DEFAULT 0, episodes_updated INTEGER NOT NULL DEFAULT 0, "
            "last_reset_at TEXT NOT NULL, "
            "albums_found INTEGER NOT NULL DEFAULT 0, albums_updated INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (app, instance_id, instance_stable_id))"
        )
        await db.execute(
            "INSERT INTO lifetime_stats_v10 "
            "(app, instance_id, movies_found, movies_updated, episodes_found, episodes_updated, "
            "last_reset_at, albums_found, albums_updated, instance_stable_id) "
            "SELECT app, instance_id, movies_found, movies_updated, episodes_found, episodes_updated, "
            "last_reset_at, albums_found, albums_updated, '' "
            "FROM lifetime_stats"
        )
        await db.execute("DROP TABLE lifetime_stats")
        await db.execute("ALTER TABLE lifetime_stats_v10 RENAME TO lifetime_stats")

    # Association: set the stable ID on existing rows of configured
    # instances. These are the only UPDATE statements in this migration,
    # and each one sets only the association column -- nothing else about
    # an existing row ever changes.
    associated = 0
    for (app, name), stable_id in instance_stable_ids.items():
        if not stable_id:
            continue
        await db.execute(
            "UPDATE search_history SET instance_stable_id = ? "
            "WHERE app = ? AND instance_id = ? AND instance_stable_id IS NULL",
            (stable_id, app, name),
        )
        await db.execute(
            "UPDATE lifetime_stats SET instance_stable_id = ? "
            "WHERE app = ? AND instance_id = ? AND instance_stable_id = ''",
            (stable_id, app, name),
        )
        associated += 1

    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_lifetime_stats_app_stable_id "
        "ON lifetime_stats(app, instance_stable_id) WHERE instance_stable_id != ''"
    )

    logger.info("Migration v10: associated {count} existing instance name(s) with stable IDs", count=associated)


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
    9: ("add Lidarr album stats columns", _migrate_v9),
    10: ("add grab ownership, attribution cutover and stable-id association", _migrate_v10),
}


# ---------------------------------------------------------------------------
# Database init
# ---------------------------------------------------------------------------


async def init_db(
    db: aiosqlite.Connection,
    db_path: Path,
    *,
    instance_stable_ids: Mapping[tuple[str, str], str] | None = None,
) -> None:
    """Create base tables, run migrations.

    Args:
        db: Open aiosqlite connection.
        db_path: Path to the SQLite database file (needed for backup).
        instance_stable_ids: Optional mapping of (stored title-case app,
            instance name) -> stable instance ID, forwarded to migration
            v10 for associating existing rows with the already-backfilled
            config's stable IDs. ``None`` (the default, and every
            existing two-argument call site) means no association.
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
    await run_migrations(db, db_path, instance_stable_ids=instance_stable_ids)
    logger.debug("Search history database initialized at {path}", path=db_path)


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


# A pre-cutover pending Sonarr row is identified at query time by comparing
# its id to the cutover's recorded legacy_max_history_id, never by writing a
# flag onto the row. ids are AUTOINCREMENT and never reused, so this holds
# forever once a row is frozen -- unlike an ISO timestamp comparison, it
# isn't sensitive to same-second ordering. Defaults to 0 (nothing is legacy)
# when no cutover has been recorded yet.
_LEGACY_MAX_ID_SQL = "COALESCE((SELECT legacy_max_history_id FROM attribution_cutover WHERE id = 1), 0)"
_LEGACY_PENDING_SQL = (
    "(app = 'Sonarr' AND COALESCE(outcome, 'searched') IN ('searched', 'partial') AND id <= "
    + _LEGACY_MAX_ID_SQL
    + ")"
)


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
    instance_stable_id: str | None = None,
    max_rows: int = 1000,
) -> None:
    """Insert a search log entry, enforcing bounded growth on both row classes.

    Bounds:
        * Resolved rows (outcome != 'searched') are trimmed inline after
          every insert to keep their count <= max_rows. The trim runs in
          the same transaction as the insert (single ``db.commit()`` at
          the end), so the cap holds immediately on the next read. Closes
          SAFETY-01.
        * Pending rows (outcome == 'searched') are bounded separately at
          ``PENDING_CAP_MULTIPLIER * max_rows`` (default 2x). If the
          pending count is already at or above this cap, a new pending
          insert is REJECTED with ``PendingCapExceeded`` and a WARNING
          log line identifying the rejected entry (app, instance_id,
          item_name). This bounds the stalled-tracker failure mode
          (Sonarr/Radarr unreachable for extended period). Pending rows
          are also bounded by ``tracking_window_minutes`` (their natural
          resolution timeout). Closes SAFETY-01b.

    Raises:
        PendingCapExceeded: when ``outcome == 'searched'`` and the
            pending row count is already >= PENDING_CAP_MULTIPLIER *
            max_rows. The insert is rejected; existing pending rows are
            NOT evicted (eviction would lose tracking semantics).
        Exception: any database error raised by the INSERT, the prune
            DELETE, or the commit propagates after the transaction is
            rolled back, so no partial write stays pending on the shared
            connection (R-08).

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
        instance_stable_id: Stable per-instance ID (survives renames). When
            given, both the pending-cap count and the stored row are scoped
            by this identity instead of (or alongside) the display name --
            a renamed Sonarr instance keeps counting against the same cap,
            and a different server that reuses an old name gets its own.
            Falsy values (``None`` or ``""``) store ``NULL``.
        max_rows: Maximum resolved rows to keep. The pending cap is
            derived as ``PENDING_CAP_MULTIPLIER * max_rows``.
    """
    # SAFETY-01b: bound pending rows so a stalled tracker cannot grow
    # the table unboundedly. Resolved inserts bypass this guard -- they
    # are bounded by the resolved-row trim further below. Pre-cutover
    # legacy Sonarr pending rows are excluded from the count: they are
    # frozen and can never be resolved, so they must not count against a
    # cap meant to catch a *currently* stalled tracker.
    if outcome == "searched":
        cap = PENDING_CAP_MULTIPLIER * max_rows
        if instance_stable_id:
            cap_query = (
                "SELECT COUNT(*) FROM search_history "
                "WHERE outcome = 'searched' AND app = ? AND instance_stable_id = ? AND NOT " + _LEGACY_PENDING_SQL
            )
            cap_params: tuple[str, str] = (app, instance_stable_id)
        else:
            cap_query = (
                "SELECT COUNT(*) FROM search_history "
                "WHERE outcome = 'searched' AND app = ? AND instance_id = ? AND NOT " + _LEGACY_PENDING_SQL
            )
            cap_params = (app, instance_id)
        async with db.execute(cap_query, cap_params) as cursor:
            row = await cursor.fetchone()
        pending_count = row[0] if row is not None else 0
        if pending_count >= cap:
            logger.warning(
                "Pending-row cap reached -- rejecting search_history insert "
                "for {app}/{instance_id} {item_name!r} (pending={pending_count}, cap={cap}). "
                "Tracker may be stalled; check app reachability.",
                app=app,
                instance_id=instance_id,
                item_name=item_name,
                pending_count=pending_count,
                cap=cap,
            )
            raise PendingCapExceeded(
                app=app,
                instance_id=instance_id,
                item_name=item_name,
                pending_count=pending_count,
                cap=cap,
            )

    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        await db.execute(
            "INSERT INTO search_history "
            "(timestamp, app, queue_type, item_name, outcome, detail, item_id, season_number, "
            "missing_count, instance_id, instance_stable_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                timestamp, app, queue_type, item_name, outcome, detail,
                item_id, season_number, missing_count, instance_id, instance_stable_id or None,
            ),
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
    except Exception as exc:
        # R-08: any failure between the INSERT and the commit leaves the
        # transaction open on the shared connection; roll it back before
        # propagating so the next caller's insert can't commit this one's
        # row too, and so the pending-cap check above only ever counts
        # committed rows. Exception (not just aiosqlite.Error) because a
        # driver-thread OSError leaves the same open transaction.
        # asyncio.CancelledError is a BaseException and is intentionally
        # not caught here -- awaiting a rollback during cancellation is
        # unsafe, and closing the connection at shutdown discards an
        # uncommitted SQLite transaction anyway.
        try:
            await db.rollback()
        except Exception as rollback_exc:
            logger.error(
                "search_history rollback failed after insert error for {app}/{instance_id} {item_name!r}: "
                "{rollback_exc} (original: {exc_type})",
                app=app,
                instance_id=instance_id,
                item_name=item_name,
                rollback_exc=rollback_exc,
                exc_type=type(exc).__name__,
            )
        raise


async def get_recent_searches(
    db: aiosqlite.Connection, limit: int = 50, *, instance_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return the most recent search history entries.

    Args:
        db: Open aiosqlite connection.
        limit: Maximum number of entries to return.
        instance_id: If set, filter to entries from this instance only.

    Returns:
        List of dicts with keys: name, timestamp, app, queue_type, outcome,
        detail, instance_id, is_legacy (pre-cutover frozen Sonarr pending
        row). Ordered newest-first (by id DESC).
    """
    is_legacy_col = f"CASE WHEN {_LEGACY_PENDING_SQL} THEN 1 ELSE 0 END AS is_legacy"
    if instance_id is not None:
        query = (
            f"SELECT timestamp, app, queue_type, item_name, outcome, detail, instance_id, {is_legacy_col} "
            "FROM search_history WHERE instance_id = ? ORDER BY id DESC LIMIT ?"
        )
        params: tuple[str | int, ...] = (instance_id, limit)
    else:
        query = (
            f"SELECT timestamp, app, queue_type, item_name, outcome, detail, instance_id, {is_legacy_col} "
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
            "is_legacy": bool(row["is_legacy"]),
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
        f"SELECT id, timestamp, app, queue_type, item_name, outcome, detail, instance_id, "
        f"CASE WHEN {_LEGACY_PENDING_SQL} THEN 1 ELSE 0 END AS is_legacy "
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
            "is_legacy": bool(row["is_legacy"]),
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
    db: aiosqlite.Connection, *, instance_id: str | None = None, instance_stable_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return search history entries eligible for tracking resolution.

    Finds rows with outcome ``'searched'`` or ``'partial'`` that have a
    non-null ``item_id`` (entries without an item_id cannot be correlated
    with grab events). Pre-cutover frozen Sonarr pending rows (see
    ``_LEGACY_PENDING_SQL``) are always excluded -- they are "Legacy --
    tracking discontinued" and must never be picked up again.

    Sonarr callers should select by ``instance_stable_id`` so a rename or a
    different server reusing an old name can never misroute a pending
    search; Radarr/Lidarr callers (out of scope for this phase) keep
    selecting by display name.

    Args:
        db: Open aiosqlite connection.
        instance_id: If set, filter to entries from this instance's
            display name only.
        instance_stable_id: If set, filter to entries from this stable
            instance ID only (preferred for Sonarr).

    Raises:
        ValueError: if both instance_id and instance_stable_id are given --
            exactly one selection mode may be used at a time.

    Returns:
        List of dicts ordered by ``id ASC`` (oldest first) with keys:
        id, app, queue_type, item_id, season_number, missing_count, timestamp,
        outcome, instance_id, instance_stable_id.
    """
    if instance_id is not None and instance_stable_id is not None:
        msg = "get_trackable_entries: pass instance_id or instance_stable_id, not both"
        raise ValueError(msg)

    base = (
        "SELECT id, app, queue_type, item_id, season_number, missing_count, "
        "timestamp, outcome, instance_id, instance_stable_id "
        "FROM search_history "
        "WHERE outcome IN ('searched', 'partial') AND item_id IS NOT NULL "
        "AND NOT " + _LEGACY_PENDING_SQL
    )
    if instance_stable_id is not None:
        query = f"{base} AND instance_stable_id = ? ORDER BY id ASC"
        params: tuple[str | int, ...] = (instance_stable_id,)
    elif instance_id is not None:
        query = f"{base} AND instance_id = ? ORDER BY id ASC"
        params = (instance_id,)
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
            "instance_stable_id": row["instance_stable_id"],
        }
        for row in rows
    ]
    logger.debug("Found {count} trackable entries", count=len(result))
    return result


_ALLOWED_STAT_COLUMNS = frozenset({
    "movies_found", "movies_updated",
    "episodes_found", "episodes_updated",
    "albums_found", "albums_updated",
})


@dataclass(frozen=True)
class OwnedGrab:
    """A grab event to credit atomically with an outcome/stat update (ATTR-02, ATTR-04)."""

    grab_id: int
    episode_id: int | None
    series_id: int | None
    season_number: int | None


@dataclass(frozen=True)
class OwnedGrabRecord:
    """A previously credited grab, as returned by get_owned_grabs."""

    grab_id: int
    history_id: int
    episode_id: int | None


async def update_outcome_and_stats(
    db: aiosqlite.Connection,
    history_id: int,
    outcome: str,
    detail: str,
    *,
    app: str,
    queue_type: str,
    instance_id: str = "Default",
    instance_stable_id: str | None = None,
    stat_increments: dict[str, int] | None = None,
    owned_grabs: Sequence[OwnedGrab] = (),
) -> None:
    """Atomically update a search entry's outcome, lifetime stats and grab ownership.

    Performs all three writes in a single transaction so that a crash or an
    already-owned grab_id cannot leave the database inconsistent: either
    everything here lands, or none of it does.

    Args:
        db: Open aiosqlite connection.
        history_id: Primary key of the search_history row to update.
        outcome: New outcome value (e.g. "grabbed", "partial", "unresolved").
        detail: Human-readable detail string.
        app: Application name for lifetime_stats/ownership lookup.
        queue_type: Queue type (unused in SQL, kept for caller convenience/logging).
        instance_id: Instance display name. Used for the lifetime_stats
            lookup only when *instance_stable_id* is not given (legacy
            callers); stored as the row's name when a new stable-ID row is
            created.
        instance_stable_id: Stable per-instance ID. When given, lifetime
            increments and ownership are keyed by this identity instead of
            the display name: a rename keeps adding to the same row (whose
            stored name stays as it was), and a different server that
            reuses an old name gets its own row (enforced by the
            idx_lifetime_stats_app_stable_id partial unique index). Without
            one, increments fall back to the legacy ``(app, instance_id,
            '')`` row, created if missing.
        stat_increments: Optional mapping of column name to increment value,
            e.g. ``{"movies_found": 1}``.  Only columns in lifetime_stats are
            allowed; a ``ValueError`` is raised for unknown column names.
        owned_grabs: Grab events to credit in the same transaction. Each
            becomes one ``grab_ownership`` row keyed by (app,
            instance_stable_id, grab_id); a grab_id already owned by this
            instance raises ``sqlite3.IntegrityError`` and rolls back the
            whole call, crediting closed rather than double-counting.

    Raises:
        ValueError: If *stat_increments* contains a column name not in
            ``{movies_found, movies_updated, episodes_found, episodes_updated,
            albums_found, albums_updated}``, or if *owned_grabs* is
            non-empty and *instance_stable_id* is falsy.
    """
    if stat_increments:
        unknown = set(stat_increments.keys()) - _ALLOWED_STAT_COLUMNS
        if unknown:
            msg = f"Unknown stat column(s): {', '.join(sorted(unknown))}"
            raise ValueError(msg)

    if owned_grabs and not instance_stable_id:
        msg = "update_outcome_and_stats: owned_grabs requires a non-empty instance_stable_id"
        raise ValueError(msg)

    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    try:
        # 1. Update outcome and resolved_at timestamp
        await db.execute(
            "UPDATE search_history SET outcome = ?, detail = ?, resolved_at = ? WHERE id = ?",
            (outcome, detail, now, history_id),
        )

        # 2. Increment lifetime stats (if any), keyed by stable ID when given (S1).
        if stat_increments:
            if instance_stable_id:
                await db.execute(
                    "INSERT OR IGNORE INTO lifetime_stats "
                    "(app, instance_id, instance_stable_id, last_reset_at) VALUES (?, ?, ?, ?)",
                    (app, instance_id, instance_stable_id, now),
                )
                set_parts = [f"{col} = {col} + ?" for col in stat_increments]
                values = [*stat_increments.values(), app, instance_stable_id]
                await db.execute(
                    f"UPDATE lifetime_stats SET {', '.join(set_parts)} "  # noqa: S608
                    "WHERE app = ? AND instance_stable_id = ?",
                    values,
                )
            else:
                # Legacy path: the (app, name, '') row, created if missing.
                await db.execute(
                    "INSERT OR IGNORE INTO lifetime_stats "
                    "(app, instance_id, instance_stable_id, last_reset_at) VALUES (?, ?, '', ?)",
                    (app, instance_id, now),
                )
                set_parts = [f"{col} = {col} + ?" for col in stat_increments]
                values = [*stat_increments.values(), app, instance_id]
                await db.execute(
                    f"UPDATE lifetime_stats SET {', '.join(set_parts)} "  # noqa: S608
                    "WHERE app = ? AND instance_id = ? AND instance_stable_id = ''",
                    values,
                )

        # 3. Ownership (ATTR-02, ATTR-04). Plain INSERT, not OR IGNORE, so a
        # grab_id already owned by this instance fails the whole call
        # closed rather than silently double-counting. No referential
        # constraint back to search_history, so ownership survives pruning
        # and restarts.
        for grab in owned_grabs:
            await db.execute(
                "INSERT INTO grab_ownership "
                "(app, instance_stable_id, grab_id, history_id, series_id, season_number, "
                "episode_id, credited_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    app, instance_stable_id, grab.grab_id, history_id,
                    grab.series_id, grab.season_number, grab.episode_id, now,
                ),
            )

        # 4. Single commit for the whole transaction -- outcome, stats and
        # ownership all land together or none of them do.
        await db.commit()
    except Exception as exc:
        try:
            await db.rollback()
        except Exception as rollback_exc:
            logger.error(
                "update_outcome_and_stats rollback failed for history_id={hid}: {rollback_exc} "
                "(original: {exc_type})",
                hid=history_id,
                rollback_exc=rollback_exc,
                exc_type=type(exc).__name__,
            )
        raise
    logger.debug(
        "Updated history_id={hid} outcome={out} instance={inst} stats={stats} owned={owned}",
        hid=history_id,
        out=outcome,
        inst=instance_id,
        stats=stat_increments or {},
        owned=len(owned_grabs),
    )


async def get_owned_grabs(
    db: aiosqlite.Connection, *, app: str, instance_stable_id: str, series_id: int,
) -> list[OwnedGrabRecord]:
    """Return previously credited grabs for one (app, stable instance ID, series).

    Ownership rows carry no referential constraint back to search_history
    and are never pruned, so this reflects every grab ever credited for the
    series, regardless of whether the owning search_history row still exists.
    """
    async with db.execute(
        "SELECT grab_id, history_id, episode_id FROM grab_ownership "
        "WHERE app = ? AND instance_stable_id = ? AND series_id = ?",
        (app, instance_stable_id, series_id),
    ) as cursor:
        rows = await cursor.fetchall()
    return [OwnedGrabRecord(row["grab_id"], row["history_id"], row["episode_id"]) for row in rows]


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
        Dict with keys: overall_rate, radarr_rate, sonarr_rate, lidarr_rate,
        movies_found, movies_updated, episodes_found, episodes_updated,
        albums_found, albums_updated, avg_time_to_grab_seconds.
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
    app_rates: dict[str, float | None] = {app: None for app in APP_TYPES}

    for row in effectiveness_rows:
        app_name = row["app"]
        grabbed = row["grabbed_count"]
        count = row["total_count"]
        total_grabbed += grabbed
        total_count += count
        if count > 0:
            app_key = app_name.lower()
            if app_key in app_rates:
                app_rates[app_key] = (grabbed / count) * 100

    overall_rate: float | None = (total_grabbed / total_count * 100) if total_count > 0 else None

    # 2. Lifetime stats
    movies_found = 0
    movies_updated = 0
    episodes_found = 0
    episodes_updated = 0
    albums_found = 0
    albums_updated = 0

    if instance_id is not None:
        stats_query = (
            "SELECT movies_found, movies_updated, episodes_found, episodes_updated, "
            "albums_found, albums_updated "
            "FROM lifetime_stats WHERE instance_id = ?"
        )
        stats_params: tuple[str | int, ...] = (instance_id,)
    else:
        stats_query = (
            "SELECT movies_found, movies_updated, episodes_found, episodes_updated, "
            "albums_found, albums_updated FROM lifetime_stats"
        )
        stats_params = ()
    async with db.execute(stats_query, stats_params) as cursor:
        stats_rows = await cursor.fetchall()

    for row in stats_rows:
        movies_found += row["movies_found"]
        movies_updated += row["movies_updated"]
        episodes_found += row["episodes_found"]
        episodes_updated += row["episodes_updated"]
        albums_found += row["albums_found"]
        albums_updated += row["albums_updated"]

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
        "radarr_rate": app_rates.get("radarr"),
        "sonarr_rate": app_rates.get("sonarr"),
        "lidarr_rate": app_rates.get("lidarr"),
        "movies_found": movies_found,
        "movies_updated": movies_updated,
        "episodes_found": episodes_found,
        "episodes_updated": episodes_updated,
        "albums_found": albums_found,
        "albums_updated": albums_updated,
        "avg_time_to_grab_seconds": avg_seconds,
    }
