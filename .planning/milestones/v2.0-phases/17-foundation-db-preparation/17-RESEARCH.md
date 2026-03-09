# Phase 17: Foundation & DB Preparation - Research

**Researched:** 2026-02-24
**Domain:** SQLite schema migration, connection management, configurable settings
**Confidence:** HIGH

## Summary

Phase 17 is pure infrastructure work: upgrading the SQLite layer from connection-per-operation to a shared connection in WAL mode, extending the search_history schema with columns needed for downstream tracking correlation, adding configurable settings for tracking window/timeout/pageSize/max_rows, making pruning tracking-aware, and creating a lifetime_stats table. No UI changes, no tracking logic, no polling -- those belong to Phases 19-21.

The existing codebase uses `aiosqlite` with a fresh `aiosqlite.connect()` call per function in `db.py`. The migration to a shared connection means opening the connection once during lifespan startup and passing it (or storing it on `app.state`) so all `db.py` functions use it. WAL mode is a single `PRAGMA journal_mode=WAL` executed once on the shared connection at init time -- it persists to the database file, so subsequent connections also inherit it. The schema migration system uses a dedicated `schema_version` table (user decision) with an integer version, checked on startup.

**Primary recommendation:** Refactor `db.py` to accept a `Connection` object rather than a `Path`, open the connection once in the lifespan, set WAL mode, run schema migrations (with backup-before-migrate), and store the connection on `app.state.db`. Add new columns and tables via numbered migration functions.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **lifetime_stats table shape**: Four counters (movies_found, movies_updated, episodes_found, episodes_updated), one row per app (Radarr row + Sonarr row) keyed by app name, includes last_reset_at timestamp column, users can reset stats via a settings button (zeroes counters, updates last_reset_at)
- **Pruning behavior**: Pending rows (outcome='searched') exempt from pruning -- always kept until they resolve. No hard ceiling on pending rows. Pruning runs after each search cycle (not on startup, not on a separate schedule). Default max_rows = 1000. Existing v1.x rows (lacking outcome column) backfilled as 'unresolved' during migration, making them immediately eligible for pruning
- **Migration strategy**: Auto-migrate on startup. Schema version tracked in a dedicated meta table (integer version, compare on startup). Back up DB file before migrating (copy to fetcharr.db.v1-backup or similar). Log each migration step via Loguru so users see "Migrating schema v1 -> v2: adding outcome column..." in Docker logs

### Claude's Discretion
- Config defaults for tracking window, request timeout, and pageSize (researcher/planner can determine sensible values)
- Exact schema_version table design
- Backup file naming convention
- WAL mode activation approach (PRAGMA on connection init)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEBT-03 | Configurable max rows for search history table (bounded growth) | Add `max_history_rows` to `GeneralConfig` (default 1000 per user decision). Pass to pruning logic in `insert_search_entry`. Pruning must exempt rows with outcome='searched'. |
| DEBT-04 | Persistent SQLite connection with WAL mode (replaces connection-per-operation) | Open `aiosqlite.connect()` once in lifespan, run `PRAGMA journal_mode=WAL`, store on `app.state.db`. Refactor all `db.py` functions from `async with aiosqlite.connect(path)` to accept a `Connection` parameter. |
| DEBT-07 | Configurable request timeout on outbound HTTP calls | Add `request_timeout` to `GeneralConfig` (default 30.0s). Pass to `ArrClient.__init__()` when constructing clients in lifespan and settings save handler. |
| DEBT-08 | Configurable pageSize for *arr API pagination | Add `page_size` to `GeneralConfig` (default 50). Pass to `get_paginated()` calls in client methods. |
| TRACK-07 | User can configure tracking window duration and poll interval via settings | Add `tracking_window_minutes` to `GeneralConfig` (default 60). Add `tracking_poll_seconds` to `GeneralConfig` (default 90). These are stored in TOML config and surfaced in settings UI (Phase 19-21 will consume them). This phase only adds the config fields; no polling logic yet. |
| TRACK-08 | System stores item IDs and expected missing counts at search time for correlation | Add `item_id` (INTEGER), `season_number` (INTEGER, nullable), and `missing_count` (INTEGER, nullable) columns to search_history. Populate at insert time in `run_radarr_cycle` (item_id=movie.id) and `run_sonarr_cycle` (item_id=season.seriesId, season_number=season.seasonNumber, missing_count=episode count for that season). |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiosqlite | 0.20+ (installed) | Async SQLite access | Already in use; wraps stdlib sqlite3 with asyncio thread bridge |
| pydantic-settings | installed | TOML config with validation | Already in use for Settings model |
| loguru | installed | Structured logging | Already in use throughout codebase |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shutil (stdlib) | 3.11+ | DB file backup before migration | `shutil.copy2()` for backup-before-migrate |
| sqlite3 (stdlib) | 3.11+ | Underlying SQLite engine | Accessed through aiosqlite; PRAGMA support built in |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Dedicated schema_version table | `PRAGMA user_version` | Built-in to SQLite, zero table overhead. User decided on meta table -- follow that decision. |
| aiosqlite shared connection | SQLAlchemy async + aiosqlite | Massive overkill for this project; zero new dependencies is a v2.0 constraint. |

**Installation:**
No new dependencies needed. All changes use existing packages and stdlib.

## Architecture Patterns

### Recommended Project Structure
No new files needed. Changes are to existing modules:
```
fetcharr/
├── db.py              # Refactor: shared connection, migration system, new columns/tables
├── config.py          # Add new setting keys to DEFAULT_CONFIG template
├── models/config.py   # Add fields to GeneralConfig
├── search/engine.py   # Pass item_id, season_number, missing_count to insert_search_entry
├── search/scheduler.py # Open shared connection in lifespan, store on app.state
├── clients/base.py    # Accept timeout and page_size from settings
├── web/routes.py      # Pass new settings to client constructors, close db on shutdown
```

### Pattern 1: Shared Connection Lifecycle
**What:** Open `aiosqlite.connect()` once during FastAPI lifespan startup, store on `app.state.db`, close in lifespan teardown.
**When to use:** Always -- replaces the current connection-per-operation pattern.
**Example:**
```python
# In scheduler.py create_lifespan -> lifespan()
db = await aiosqlite.connect(db_path)
await db.execute("PRAGMA journal_mode=WAL")
await db.execute("PRAGMA synchronous=NORMAL")  # Safe with WAL
app.state.db = db

# In teardown
await app.state.db.close()
```
**Source:** [SQLite WAL documentation](https://sqlite.org/wal.html), [aiosqlite docs](https://aiosqlite.omnilib.dev/en/latest/)

### Pattern 2: Sequential Schema Migration
**What:** Check current schema version on startup, run each needed migration function in order, update version after each.
**When to use:** Every startup -- idempotent by design (skips already-applied migrations).
**Example:**
```python
async def get_schema_version(db: aiosqlite.Connection) -> int:
    """Read current schema version from meta table."""
    await db.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
    )
    cursor = await db.execute("SELECT version FROM schema_version")
    row = await cursor.fetchone()
    if row is None:
        await db.execute("INSERT INTO schema_version (version) VALUES (0)")
        await db.commit()
        return 0
    return row[0]

async def set_schema_version(db: aiosqlite.Connection, version: int) -> None:
    await db.execute("UPDATE schema_version SET version = ?", (version,))
    await db.commit()

# Migration registry: version -> (description, migration_fn)
MIGRATIONS = {
    1: ("add outcome and detail columns", migrate_v1_to_v2),
    2: ("add item_id, season_number, missing_count columns", migrate_v2_to_v3),
    3: ("create lifetime_stats table", migrate_v3_to_v4),
    4: ("backfill existing rows as unresolved", migrate_v4_to_v5),
}

async def run_migrations(db: aiosqlite.Connection, db_path: Path) -> None:
    current = await get_schema_version(db)
    target = max(MIGRATIONS.keys())
    if current >= target:
        return
    # Backup before first migration
    backup_path = db_path.with_suffix(f".v{current}-backup")
    shutil.copy2(db_path, backup_path)
    logger.info("Database backed up to {path}", path=backup_path)
    for version in range(current + 1, target + 1):
        desc, fn = MIGRATIONS[version]
        logger.info("Migrating schema v{old} -> v{new}: {desc}",
                     old=version - 1, new=version, desc=desc)
        await fn(db)
        await set_schema_version(db, version)
```

### Pattern 3: Tracking-Aware Pruning
**What:** Modify the DELETE query in `insert_search_entry` to preserve rows with `outcome='searched'` (pending tracking).
**When to use:** Every insert -- replaces current unconditional prune.
**Example:**
```python
# Current: DELETE WHERE id NOT IN (SELECT id ... LIMIT 500)
# New: DELETE WHERE id NOT IN (SELECT id ... LIMIT ?)
#      AND COALESCE(outcome, 'searched') != 'searched'
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
```
**Note:** The pruning logic only counts and limits *resolved* rows. Pending rows (outcome='searched') are always preserved, regardless of count. This means the actual table size can exceed max_rows temporarily while tracking entries await resolution.

### Pattern 4: Refactoring db.py Function Signatures
**What:** Change all `db.py` functions from accepting `db_path: Path` to accepting `db: aiosqlite.Connection`.
**When to use:** All functions that currently open their own connection.
**Example:**
```python
# Before
async def insert_search_entry(db_path: Path, app: str, ...) -> None:
    async with aiosqlite.connect(db_path) as db:
        ...

# After
async def insert_search_entry(db: aiosqlite.Connection, app: str, ...) -> None:
    await db.execute(...)
    await db.commit()
```
**Impact:** All callers must pass `app.state.db` instead of `app.state.db_path`. Affects: `search/engine.py` (run_radarr_cycle, run_sonarr_cycle), `search/scheduler.py` (lifespan init), `web/routes.py` (dashboard, history, search-now).

### Anti-Patterns to Avoid
- **Opening connections inside hot paths:** Never create a new `aiosqlite.connect()` in cycle functions or route handlers. Use the shared connection from `app.state.db`.
- **Running PRAGMA after WAL is already set:** WAL mode persists to the database file. Running `PRAGMA journal_mode=WAL` on every connection is harmless but unnecessary after first set. Run it once during init for clarity.
- **Mixing sync and async DB calls:** All SQLite access must go through `aiosqlite`. Never use `sqlite3` directly in the async event loop.
- **Forgetting to commit after migration steps:** Each migration must `await db.commit()` before updating the schema version. Without this, ALTERs may not persist.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DB file backup | Custom binary copy | `shutil.copy2()` | Preserves metadata, handles edge cases, one line |
| Schema version tracking | Ad-hoc column checks | Dedicated version table with integer counter | The try/except ALTER pattern in current code is fragile; a version number makes migration order explicit |
| WAL mode enablement | Custom journaling | `PRAGMA journal_mode=WAL` | SQLite's built-in WAL is production-proven; never attempt custom write-ahead logging |
| TOML comment preservation | String manipulation | `tomli_w.dumps()` (already used) | Current config write path already handles this |

**Key insight:** This phase is about plumbing, not novel engineering. Every component uses stdlib or already-installed libraries. The complexity is in getting the migration order right and ensuring all callers are updated to use the shared connection.

## Common Pitfalls

### Pitfall 1: Forgetting to Close the Shared Connection
**What goes wrong:** Database file left locked after process exit, causing "database is locked" on restart.
**Why it happens:** The lifespan teardown doesn't call `await db.close()`.
**How to avoid:** Close the connection in the `finally` block of the lifespan context manager, alongside scheduler shutdown and client closure.
**Warning signs:** "database is locked" errors on container restart.

### Pitfall 2: Migration Backup Race Condition
**What goes wrong:** Backup is taken while aiosqlite has the connection open, potentially capturing a partial WAL state.
**Why it happens:** `shutil.copy2()` copies the main database file but not the WAL/SHM files.
**How to avoid:** Run backup *before* opening the shared connection. In the lifespan: (1) check schema version with a temporary connection, (2) if migration needed, close temp connection, backup the file, (3) open the shared connection, (4) run migrations. Alternatively, checkpoint WAL first with `PRAGMA wal_checkpoint(TRUNCATE)` before backup.
**Warning signs:** Restored backup is missing recent data.

### Pitfall 3: Test Isolation with Shared Connection
**What goes wrong:** Tests that previously created isolated connections per call now share a connection, causing state leakage between tests.
**Why it happens:** The `db.py` functions no longer open/close their own connections.
**How to avoid:** Test fixtures must create a fresh `aiosqlite.connect()` per test (using `tmp_path`), run `init_db` on it, and pass it directly. Each test gets its own database file and connection.
**Warning signs:** Tests pass individually but fail in sequence.

### Pitfall 4: Pruning Logic Accidentally Deleting Pending Rows
**What goes wrong:** Rows with `outcome='searched'` get pruned before tracking can resolve them.
**Why it happens:** The WHERE clause doesn't correctly exclude pending rows.
**How to avoid:** Use `COALESCE(outcome, 'searched')` in the pruning query to handle NULL outcomes from legacy data. Test with mixed pending/resolved rows.
**Warning signs:** Tracking phases (19-20) report "no matching search entry" for recently searched items.

### Pitfall 5: Backfill Migration Marking Existing Rows Incorrectly
**What goes wrong:** Existing v1.x rows (which have `outcome=NULL` from the old ALTER migration) get treated as "pending" instead of "unresolved", exempting them from pruning forever.
**Why it happens:** The backfill migration doesn't run, or runs after the pruning logic is already checking for `outcome='searched'`.
**How to avoid:** Migration step must UPDATE all rows with NULL outcome to 'unresolved'. This must run during the schema migration sequence, before the app's normal pruning logic starts.
**Warning signs:** Row count never decreases despite pruning being configured.

### Pitfall 6: Settings Not Reaching Client Constructors
**What goes wrong:** New config fields (request_timeout, page_size) are added to the model but never passed to the httpx client or get_paginated() calls.
**Why it happens:** Client construction in lifespan and settings-save handler uses hardcoded defaults.
**How to avoid:** Thread settings values through every client construction site: lifespan startup, settings POST handler client recreation, and search-now.
**Warning signs:** Changing timeout/pageSize in settings has no effect.

## Code Examples

### WAL Mode Activation
```python
# Source: SQLite WAL docs (https://sqlite.org/wal.html)
# Run once on the shared connection during init
async def init_shared_connection(db_path: Path) -> aiosqlite.Connection:
    db = await aiosqlite.connect(db_path)
    # WAL mode persists to the file; this is idempotent
    await db.execute("PRAGMA journal_mode=WAL")
    # NORMAL sync is safe with WAL and faster than FULL
    await db.execute("PRAGMA synchronous=NORMAL")
    return db
```

### Schema Version Table
```python
# Claude's discretion: simple single-row table
async def ensure_schema_version_table(db: aiosqlite.Connection) -> None:
    await db.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "  version INTEGER NOT NULL DEFAULT 0"
        ")"
    )
    cursor = await db.execute("SELECT COUNT(*) FROM schema_version")
    count = (await cursor.fetchone())[0]
    if count == 0:
        await db.execute("INSERT INTO schema_version (version) VALUES (0)")
    await db.commit()
```

### lifetime_stats Table Creation
```python
# Source: User decision in CONTEXT.md
async def create_lifetime_stats_table(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS lifetime_stats (
            app TEXT PRIMARY KEY,
            movies_found INTEGER NOT NULL DEFAULT 0,
            movies_updated INTEGER NOT NULL DEFAULT 0,
            episodes_found INTEGER NOT NULL DEFAULT 0,
            episodes_updated INTEGER NOT NULL DEFAULT 0,
            last_reset_at TEXT NOT NULL
        )
        """
    )
    # Seed rows for each app
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    for app_name in ("Radarr", "Sonarr"):
        await db.execute(
            "INSERT OR IGNORE INTO lifetime_stats (app, last_reset_at) VALUES (?, ?)",
            (app_name, now),
        )
    await db.commit()
```

### New Search History Columns (Migration)
```python
async def migrate_add_tracking_columns(db: aiosqlite.Connection) -> None:
    """Add item_id, season_number, missing_count to search_history."""
    for col, col_type, default in (
        ("item_id", "INTEGER", "NULL"),
        ("season_number", "INTEGER", "NULL"),
        ("missing_count", "INTEGER", "NULL"),
    ):
        with contextlib.suppress(Exception):
            await db.execute(
                f"ALTER TABLE search_history ADD COLUMN {col} {col_type} DEFAULT {default}"
            )
    await db.commit()
```

### Backfill Existing Rows
```python
async def backfill_unresolved_outcomes(db: aiosqlite.Connection) -> None:
    """Set outcome='unresolved' on all rows where outcome is NULL."""
    result = await db.execute(
        "UPDATE search_history SET outcome = 'unresolved' WHERE outcome IS NULL"
    )
    await db.commit()
    logger.info("Backfilled {count} rows with outcome='unresolved'", count=result.rowcount)
```

### Updated insert_search_entry with Tracking-Aware Pruning
```python
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
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    await db.execute(
        "INSERT INTO search_history "
        "(timestamp, app, queue_type, item_name, outcome, detail, item_id, season_number, missing_count) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (timestamp, app, queue_type, item_name, outcome, detail, item_id, season_number, missing_count),
    )
    # Tracking-aware pruning: only prune resolved rows, keep pending (outcome='searched')
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
```

### GeneralConfig with New Settings
```python
class GeneralConfig(BaseModel):
    """Global application settings."""
    log_level: str = "info"
    hard_max_per_cycle: int = 0
    # New in Phase 17
    max_history_rows: int = 1000       # DEBT-03: configurable pruning limit
    request_timeout: float = 30.0      # DEBT-07: outbound HTTP timeout in seconds
    page_size: int = 50                # DEBT-08: *arr API pagination size
    tracking_window_minutes: int = 60  # TRACK-07: how long to wait for grabs
    tracking_poll_seconds: int = 90    # TRACK-07: poll interval for grab detection
```

### Passing Configurable Timeout and PageSize to Clients
```python
# In lifespan client construction
if settings.radarr.enabled:
    radarr_client = RadarrClient(
        base_url=settings.radarr.url,
        api_key=settings.radarr.api_key.get_secret_value(),
        timeout=settings.general.request_timeout,
        page_size=settings.general.page_size,
    )

# In ArrClient.__init__, store page_size for get_paginated default
class ArrClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0, page_size: int = 50) -> None:
        self._page_size = page_size
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
            timeout=httpx.Timeout(timeout),
        )

    async def get_paginated(self, path: str, page_size: int | None = None, ...) -> list:
        effective_page_size = page_size or self._page_size
        ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Connection-per-operation (`aiosqlite.connect()` per call) | Shared connection stored on app.state | v2.0 (this phase) | Eliminates repeated open/close overhead; required for WAL mode benefits |
| Hardcoded prune limit (500) | Configurable `max_history_rows` in TOML | v2.0 (this phase) | Users control DB growth; default raised to 1000 |
| try/except ALTER for migrations | Version-tracked sequential migration system | v2.0 (this phase) | Explicit ordering, idempotent, logged, with backup |
| Hardcoded 30s timeout, 50 pageSize | Configurable via `[general]` TOML section | v2.0 (this phase) | Users with slow networks or large libraries can tune |

**Deprecated/outdated:**
- `DB_PATH` module constant in `db.py`: replaced by path derived from `state_path.parent` in lifespan (already done)
- `_migrate_add_outcome_columns()` function: will be folded into the migration system as migration v1
- `app.state.db_path`: replaced by `app.state.db` (the connection object)

## Open Questions

1. **Pruning semantics: count resolved rows only or total rows?**
   - What we know: User decided max_rows = 1000, pending rows exempt. The pruning query deletes resolved rows beyond the limit.
   - What's unclear: Does the user expect the 1000 limit to apply to resolved rows only (so total can exceed 1000 with pending), or total rows including pending?
   - Recommendation: Implement as "1000 resolved rows max, pending rows always preserved" -- this matches the stated behavior ("pending rows exempt from pruning"). Document this clearly in the config comment.

2. **Tracking config fields: add to settings UI in this phase?**
   - What we know: TRACK-07 says "user can configure tracking window duration and poll interval via settings". The phase description says "no UI changes".
   - What's unclear: Whether the settings form should expose tracking_window_minutes and tracking_poll_seconds now or in a later phase.
   - Recommendation: Add the fields to GeneralConfig and DEFAULT_CONFIG now (so they're configurable via TOML file edit). Defer settings UI exposure to Phase 19+ when the tracking features actually exist. This keeps the phase boundary clean.

3. **Default tracking_poll_seconds value**
   - What we know: STATE.md mentions "90s default" for tracking delay. The CONTEXT.md doesn't specify exact defaults.
   - What's unclear: Whether 90s is confirmed as the desired default.
   - Recommendation: Use 90 seconds as default. It's referenced in STATE.md's accumulated context and balances API load against responsiveness.

## Sources

### Primary (HIGH confidence)
- [SQLite WAL documentation](https://sqlite.org/wal.html) - WAL mode behavior, persistence, concurrency model, PRAGMA syntax
- [SQLite PRAGMA reference](https://sqlite.org/pragma.html) - journal_mode, synchronous, user_version PRAGMAs
- [aiosqlite documentation](https://aiosqlite.omnilib.dev/en/latest/) - Connection API, thread model, context managers
- Codebase direct inspection: `fetcharr/db.py`, `fetcharr/config.py`, `fetcharr/models/config.py`, `fetcharr/clients/base.py`, `fetcharr/search/scheduler.py`, `fetcharr/search/engine.py`, `fetcharr/web/routes.py`

### Secondary (MEDIUM confidence)
- [Simon Willison's WAL mode TIL](https://til.simonwillison.net/sqlite/enabling-wal-mode) - Practical WAL enablement patterns
- [SQLite migrations with PRAGMA user_version](https://levlaz.org/sqlite-db-migrations-with-pragma-user_version/) - Schema versioning patterns (used for comparison; user chose meta table instead)
- [suckless SQLite schema migrations in Python](https://eskerda.com/sqlite-schema-migrations-python/) - Migration runner design patterns

### Tertiary (LOW confidence)
- None -- all findings verified against primary sources or codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed and in use; zero new dependencies
- Architecture: HIGH - patterns verified against aiosqlite docs and SQLite WAL documentation; shared connection is the standard aiosqlite usage pattern
- Pitfalls: HIGH - identified from direct codebase analysis (6 specific callers to update, migration ordering requirements, pruning logic edge cases)

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (stable domain; no fast-moving dependencies)
