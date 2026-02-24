# Architecture Patterns

**Domain:** Closed-loop download tracking integration + tech debt for search automation daemon
**Researched:** 2026-02-24
**Confidence:** MEDIUM-HIGH (API endpoints verified via OpenAPI specs, pyarr docs, Go starr library, and Sonarr GitHub issues; integration patterns derived from existing codebase analysis)

## Existing Architecture Summary

The current system follows a clean layered structure:

```
__main__.py  -->  startup.py  -->  scheduler.py (APScheduler lifespan)
                                        |
                                   engine.py (run_radarr_cycle / run_sonarr_cycle)
                                        |
                               +--------+--------+
                               |                  |
                          clients/             db.py (SQLite)
                     radarr.py  sonarr.py          |
                          |                   search_history table
                     base.py (httpx)

web/routes.py  <-->  app.state  <-->  state.py (JSON cursors)
templates/
```

Key characteristics:
- **app.state** is the central shared state object (settings, clients, fetcharr_state, scheduler, db_path, search_lock)
- **engine.py** cycle functions are pure-ish: they take (client, state, settings, db_path) and return updated state
- **scheduler.py** creates job closures that read from app.state at execution time (hot-reload friendly)
- **db.py** uses connection-per-operation pattern with aiosqlite (no pooling)
- **state.py** tracks cursors, pass counts, connection health, item counts in JSON
- **search_lock** (asyncio.Lock) serializes all search cycle mutations

## Recommended Architecture for v2.0

### Design Principle: Minimal New Components, Maximum Reuse

The existing architecture is well-structured. The closed-loop tracking feature should integrate as a **post-search phase within the existing cycle functions**, not as a separate subsystem. This avoids new scheduler jobs, new locks, and new timing coordination.

### Component Boundaries

| Component | Responsibility | Status | Communicates With |
|-----------|---------------|--------|-------------------|
| `clients/base.py` | HTTP client with retry, pagination | MODIFY: pass timeout from config | httpx, *arr APIs |
| `clients/radarr.py` | Radarr API operations | MODIFY: add `get_movie_history()` | base.py |
| `clients/sonarr.py` | Sonarr API operations | MODIFY: add `get_series_history()` | base.py |
| `search/engine.py` | Search cycle orchestration | MODIFY: add post-search tracking phase | clients, tracking, db, state |
| `search/scheduler.py` | APScheduler lifespan, app.state wiring | MODIFY: graceful shutdown for DB | engine, FastAPI |
| `tracking.py` | **NEW**: Outcome correlation logic | NEW: pure functions for matching searches to grabs | None (pure logic) |
| `db.py` | SQLite search history + stats CRUD | MODIFY: add outcome updates, lifetime stats table, bounded pruning config, shared connection | aiosqlite |
| `state.py` | JSON state persistence | NO CHANGE | filesystem |
| `web/routes.py` | Dashboard, history, settings routes | MODIFY: add stats display, health endpoint, rate limiting | app.state, db, templates |
| `web/middleware.py` | Origin-check CSRF | VERIFY: already covers settings POST | requests |
| `models/config.py` | Pydantic settings | MODIFY: add pageSize, history_max_rows, tracking_delay configs | TOML config |
| `models/arr.py` | *arr API response models | NO CHANGE (history responses are unstructured dicts) | Pydantic |

### Data Flow: Closed-Loop Tracking

The tracking flow integrates into the existing search cycle rather than running as a separate job.

```
run_radarr_cycle() / run_sonarr_cycle()
    |
    1. Fetch wanted lists (existing)
    2. Filter, batch, search (existing)
    3. Record search entries to DB with outcome="searched" (existing)
    4. >>> NEW: Collect entry IDs from step 3
    5. >>> NEW: Wait configurable delay (e.g. 60-120s)
    6. >>> NEW: For each searched item, poll *arr history API
    7. >>> NEW: Correlate history events to determine outcome
    8. >>> NEW: Update search_history rows with grabbed/partial/unresolved
    9. >>> NEW: Increment lifetime stats counters
    |
    Return updated state
```

**Why post-search delay within the cycle, not a separate job:**
- Avoids coordination complexity between two jobs sharing state
- The delay is bounded and configurable (default 90 seconds) -- not a long-running poll
- Grabs typically appear in *arr history within 30-60 seconds of a search command
- The search_lock already serializes cycle access; no new locking needed
- If the delay causes issues with short intervals, it can be set to 0 to disable tracking

**Why not a separate tracking module with its own scheduler job:**
- Would require its own lock or coordination with search_lock
- Would need to track "which searches to check" separately from the cycle
- Would need its own error handling, retry, and state management
- Adds architectural complexity for a feature that naturally fits the search cycle flow
- The search_lock already prevents overlapping cycles; a delay within a cycle is safe

### New Module: `tracking.py`

This is the only new source file. It contains pure functions for outcome correlation -- no I/O, no state mutation, no client calls.

```python
# fetcharr/tracking.py
"""Outcome correlation: match *arr history events to fetcharr searches."""

from __future__ import annotations
from datetime import datetime

# --- Radarr eventType integer values ---
# 0=unknown, 1=grabbed, 2=downloadFolderImported, 3=downloadFailed,
# 4=movieFileDeleted, 5=movieFolderImported, 6=movieFileRenamed, 7=downloadIgnored

RADARR_GRABBED = 1

# --- Sonarr eventType integer values ---
# 0=unknown, 1=grabbed, 2=seriesFolderImported, 3=downloadFolderImported,
# 4=downloadFailed, 5=deleted, 6=renamed, 7=importFailed

SONARR_GRABBED = 1


def classify_radarr_outcome(
    movie_id: int,
    search_time: str,
    history_records: list[dict],
) -> str:
    """Determine if a Radarr movie was grabbed after a search.

    Returns: "grabbed" or "unresolved"
    """
    # Filter to grabbed events after search_time for this movie
    # If any grabbed event exists with date > search_time -> "grabbed"
    # Otherwise -> "unresolved"
    ...


def classify_sonarr_outcome(
    series_id: int,
    season_number: int,
    search_time: str,
    history_records: list[dict],
    wanted_episode_ids: list[int],
) -> tuple[str, int]:
    """Determine if a Sonarr season search resulted in grabs.

    Returns: ("grabbed"|"partial"|"unresolved", grabbed_count)
    - "grabbed" = all wanted episodes in this season were grabbed
    - "partial" = some but not all wanted episodes were grabbed
    - "unresolved" = no grabs detected for any wanted episode
    """
    # Filter to grabbed events after search_time
    # Extract episodeId from each grabbed event
    # Compare grabbed episode IDs to wanted_episode_ids
    # All grabbed -> "grabbed", some -> "partial", none -> "unresolved"
    ...
```

**Key design decisions for tracking.py:**
- Pure functions, no I/O -- highly testable without mocks
- Takes pre-fetched history records as input (engine.py does the API calls)
- Radarr is binary: movie was grabbed or not
- Sonarr is ternary: all wanted episodes grabbed, some grabbed, or none grabbed
- Returns grabbed count for Sonarr so lifetime stats can track individual episodes

### Database Schema Changes

#### Existing `search_history` table -- no schema change needed

The existing schema already has `outcome` and `detail` columns (added in v1.2 migration). Current values:
- outcome: "searched" | "failed"
- detail: "search triggered" | error message

New outcome values after tracking:
- "grabbed" -- search resulted in a grab for this item
- "partial" -- Sonarr season search: some but not all wanted episodes grabbed
- "unresolved" -- no grab detected within tracking window

The `id` column in search_history is the update target: `UPDATE search_history SET outcome = ?, detail = ? WHERE id = ?`.

#### New `lifetime_stats` table

```sql
CREATE TABLE IF NOT EXISTS lifetime_stats (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL DEFAULT 0
);

-- Pre-populated keys:
-- radarr_movies_found      (missing movies grabbed via fetcharr search)
-- radarr_movies_upgraded    (cutoff movies grabbed via fetcharr search)
-- sonarr_episodes_found     (missing episodes grabbed via fetcharr search)
-- sonarr_episodes_upgraded  (cutoff episodes grabbed via fetcharr search)
```

**Why a separate table, not state.json:**
- Stats must survive state.json resets (which happen on corruption)
- Stats are append-only counters -- natural fit for SQLite atomic updates
- Avoids bloating state.json with data that should never be lost
- Keeps state.json focused on ephemeral runtime state (cursors, health)

**Why not aggregate from search_history:**
- search_history is pruned (currently at 500 rows, will become configurable)
- Lifetime stats must persist beyond pruning
- COUNT queries on pruned data would undercount
- Separate counter table is O(1) read vs O(n) aggregation

#### New db.py functions

```python
async def update_search_outcome(db_path: Path, entry_id: int, outcome: str, detail: str) -> None:
    """Update outcome and detail for a search history entry."""

async def increment_stat(db_path: Path, key: str, amount: int = 1) -> None:
    """Atomically increment a lifetime stats counter."""

async def get_lifetime_stats(db_path: Path) -> dict[str, int]:
    """Return all lifetime stats as a dict."""
```

#### Modified: insert_search_entry returns row ID

```python
async def insert_search_entry(...) -> int:
    """Insert a search log entry and return the inserted row ID."""
    # ... existing insert logic ...
    # After insert, retrieve last_insert_rowid()
    # Return the ID so engine.py can pass it to update_search_outcome later
```

This is a backward-compatible change (callers that ignore the return value continue working).

### *arr History API Integration

#### Radarr History Polling

**Endpoint:** `GET /api/v3/history/movie?movieId={id}&eventType=1`
- `movieId`: The Radarr movie database ID (same ID used in MoviesSearch command)
- `eventType=1`: Filter to "grabbed" events only (integer enum, confirmed)
- Returns: List of history records (not paginated for per-movie endpoint)

Each record contains: `id`, `movieId`, `date` (ISO), `eventType` (int), `sourceTitle`, `quality`, `downloadId`, `data` (dict with indexer info).

**Confidence: MEDIUM** -- Endpoint path confirmed via Radarr OpenAPI spec reference to `/history/movie` and DeepWiki analysis. Parameter names confirmed via pyarr `get_movie_history(id, event_type)` docs. Integer enum values inferred from Sonarr (same *arr codebase lineage) and Go starr library.

New client method:
```python
# clients/radarr.py
async def get_movie_history(self, movie_id: int, event_type: int | None = None) -> list[dict]:
    """Fetch history records for a specific movie."""
    params: dict[str, Any] = {"movieId": movie_id}
    if event_type is not None:
        params["eventType"] = event_type
    response = await self.get("/api/v3/history/movie", params=params)
    return response.json()
```

#### Sonarr History Polling

**Endpoint:** `GET /api/v3/history/series?seriesId={id}&eventType=1`
- `seriesId`: The Sonarr series database ID (same ID from the wanted endpoint records)
- `eventType=1`: Filter to "grabbed" events only (integer enum)
- Returns: History records for all episodes in the series (includes `episodeId` field)

Each record contains: `id`, `seriesId`, `episodeId`, `date` (ISO), `eventType` (int), `sourceTitle`, `quality`, `downloadId`, `data` (dict).

**Confidence: MEDIUM-HIGH** -- Endpoint confirmed via Sonarr GitHub issue #4727 (the `/history/series` endpoint exists, `seriesId` param works, `includeSeries`/`includeEpisode` bug was fixed). Integer enum confirmed: 1=Grabbed per Go starr library constants and Sonarr GitHub issue #3587 where a maintainer confirmed "the gui use eventType=3" for DownloadFolderImported.

New client method:
```python
# clients/sonarr.py
async def get_series_history(self, series_id: int, event_type: int | None = None) -> list[dict]:
    """Fetch history records for a specific series."""
    params: dict[str, Any] = {"seriesId": series_id}
    if event_type is not None:
        params["eventType"] = event_type
    response = await self.get("/api/v3/history/series", params=params)
    return response.json()
```

#### Sonarr eventType Integer Enum (verified)

From Sonarr GitHub issue #3587 and Go starr library:
```
Unknown = 0
Grabbed = 1
SeriesFolderImported = 2
DownloadFolderImported = 3
DownloadFailed = 4
EpisodeFileDeleted = 5
EpisodeFileRenamed = 6
DownloadIgnored = 7
```

Radarr uses the same integer mapping pattern (same *arr codebase lineage):
```
Unknown = 0
Grabbed = 1
DownloadFolderImported = 2 (or 3, verify during implementation)
DownloadFailed = 3 (or 4)
MovieFileDeleted = 4 (or 5)
MovieFolderImported = 5
MovieFileRenamed = 6
DownloadIgnored = 7
```

**Note:** Radarr integer values may differ slightly from Sonarr. The string names are confirmed; integer mappings should be verified against a live Radarr instance during implementation by calling `/api/v3/history?eventType=1` and checking the results.

#### Tracking Window

After searching, wait `tracking_delay_seconds` (default: 90, configurable via `[general]` section) then poll history. Only consider history events with `date` after the search timestamp. This is a single poll, not a recurring check.

**Rationale for single-poll approach:**
- Grabs typically appear in *arr history within seconds to ~60s of the search command
- A 90-second delay is generous enough for network/indexer delays
- "Unresolved" is an honest outcome -- it means "no grab detected in our window"
- Avoids retry/backoff complexity specifically for tracking
- Users who want tighter tracking can adjust the delay; set to 0 to disable entirely

### Integration of Tech Debt Items

#### 1. Rate Limiting on search-now endpoint

**Where:** `web/routes.py` -- `search_now()` handler
**How:** Simple in-memory timestamp check per app. No library needed.

```python
# Track last search-now time per app on app.state
# Reject with 429 if called within 60 seconds of last trigger for same app
app.state.last_search_now: dict[str, float] = {}  # app_name -> monotonic timestamp
```

**Integration point:** Add check at top of `search_now()`, initialize dict in lifespan. Return HTMLResponse with a "Rate limited" message and the existing app card partial.

**Why not a library:** Single endpoint, single rate limit rule. A dict with `time.monotonic()` comparison is far simpler than adding slowapi or similar.

#### 2. CSRF Protection on settings POST

**Where:** `web/middleware.py` -- OriginCheckMiddleware
**Current state:** The middleware already validates Origin/Referer on ALL POST requests (line 25: `if request.method == "POST"`), including `/settings`. Per PROJECT.md key decision: "Origin/Referer CSRF over tokens -- No auth/sessions means no cookies to protect."

**Action needed:** Verify the middleware covers `/settings` POST during implementation. The current code applies to all POSTs unconditionally, so this tech debt item may already be resolved. If there is any gap, it would be in edge cases (missing both Origin and Referer headers, which the middleware currently allows through).

#### 3. Bounded Search History Table Growth

**Where:** `db.py` -- `insert_search_entry()`, `models/config.py`
**How:** Replace hardcoded `LIMIT 500` with configurable `history_max_rows` from settings.

```python
# models/config.py - GeneralConfig
history_max_rows: int = 5000  # Up from hardcoded 500, configurable

# db.py - insert_search_entry() accepts max_rows parameter
```

**Integration point:** The `insert_search_entry()` function needs to accept the max_rows value. Since it already receives `db_path`, adding another parameter is straightforward. The engine.py call sites pass `settings.general.history_max_rows`.

**Why 5000 default:** At ~10 searches/cycle, 30-min intervals, 500 rows is only ~1 day of history. 5000 gives ~10 days, more useful for tracking analysis. SQLite handles this without issue.

#### 4. Connection Pooling for aiosqlite

**Where:** `db.py` -- all functions currently use `async with aiosqlite.connect()` per operation
**How:** Use a module-level shared connection with WAL mode, initialized in `init_db()` and closed on shutdown.

```python
# db.py
_connection: aiosqlite.Connection | None = None

async def get_connection(db_path: Path) -> aiosqlite.Connection:
    """Return the shared connection, creating it if needed."""
    global _connection
    if _connection is None:
        _connection = await aiosqlite.connect(db_path)
        await _connection.execute("PRAGMA journal_mode=WAL")
        await _connection.execute("PRAGMA synchronous=NORMAL")
    return _connection

async def close_connection() -> None:
    """Close the shared connection. Called from lifespan shutdown."""
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None
```

**Integration points:**
- `init_db()` initializes the shared connection and sets WAL pragmas
- All db functions use `get_connection()` instead of `async with aiosqlite.connect()`
- `close_connection()` is called from the lifespan `finally` block in scheduler.py
- Must handle explicit `commit()` calls since the connection is long-lived

**Why a single shared connection, not a pool:**
- aiosqlite already runs SQLite in a background thread -- it IS the async bridge
- SQLite serializes writes regardless of connection count
- A pool adds complexity without benefit for single-writer workload
- WAL mode enables concurrent reads with the single connection
- aiosqlitepool exists but is overkill (~5-10 queries/minute)

**Why WAL mode:**
- Enables reads while writes are in progress (dashboard polling during search cycles)
- `synchronous=NORMAL` is safe with WAL and faster than default FULL
- Standard SQLite best practice for server-like workloads

#### 5. Health Check Endpoint

**Where:** `web/routes.py` -- new `GET /health` route
**How:** Return 200 with JSON body showing app health status.

```python
@router.get("/health")
async def health_check(request: Request) -> dict:
    state = request.app.state.fetcharr_state
    return {
        "status": "ok",
        "radarr": {"connected": state.get("radarr", {}).get("connected")},
        "sonarr": {"connected": state.get("sonarr", {}).get("connected")},
    }
```

**Integration points:**
- Add route to existing router in routes.py
- Update Dockerfile HEALTHCHECK directive: `HEALTHCHECK CMD curl -f http://localhost:8080/health || exit 1`
- No authentication needed (consistent with existing no-auth design)

#### 6. Graceful Shutdown Handler

**Where:** `search/scheduler.py` -- lifespan `finally` block
**Current state:** The lifespan already handles shutdown (scheduler.shutdown, client.close).
**How:** Add SQLite connection cleanup and shutdown timing.

```python
finally:
    scheduler.shutdown(wait=False)
    for name in ("radarr", "sonarr"):
        client = getattr(app.state, f"{name}_client", None)
        if client:
            await client.close()
    await close_connection()  # NEW: close shared SQLite connection
    logger.info("Search engine stopped")
```

**Why no custom SIGTERM handler:** Uvicorn already handles SIGTERM by triggering FastAPI lifespan shutdown. The lifespan `finally` block IS the graceful shutdown handler. Custom signal handlers risk interfering with uvicorn's reload mechanism (confirmed via FastAPI GitHub discussion #6912).

#### 7. Request Timeout on Outbound HTTP Calls

**Where:** `clients/base.py`, `models/config.py`, `search/scheduler.py`
**Current state:** The base client already accepts `timeout: float = 30.0` and creates `httpx.Timeout(timeout)`. The value is hardcoded at client construction.
**How:** Add `request_timeout` to ArrConfig, pass through to client construction.

```python
# models/config.py - ArrConfig
request_timeout: int = 30  # Seconds for outbound HTTP calls

# scheduler.py - pass timeout to client construction
radarr_client = RadarrClient(
    base_url=settings.radarr.url,
    api_key=settings.radarr.api_key.get_secret_value(),
    timeout=settings.radarr.request_timeout,
)
```

**Integration points:** scheduler.py (lifespan client creation), routes.py (config editor hot-reload client recreation). Both places already create clients; just add the timeout parameter.

#### 8. Configurable pageSize Defaults

**Where:** `models/config.py`, `clients/sonarr.py`, `clients/radarr.py`, `search/engine.py`
**Current state:** `get_paginated()` already accepts a `page_size` parameter (default 50). The default is hardcoded.
**How:** Add `page_size` to ArrConfig, pass through fetch method calls.

```python
# models/config.py - ArrConfig
page_size: int = 50  # Page size for API pagination requests

# clients/sonarr.py
async def get_wanted_missing(self, page_size: int = 50) -> list[dict]:
    return await self.get_paginated(
        "/api/v3/wanted/missing",
        page_size=page_size,
        extra_params={"includeSeries": "true"},
    )

# engine.py
missing = await client.get_wanted_missing(page_size=settings.radarr.page_size)
```

**Integration points:** Client methods need a `page_size` parameter threaded through from engine.py, which reads it from settings. Backward compatible since the parameter has a default value matching current behavior.

## Patterns to Follow

### Pattern 1: Post-Search Tracking Phase

**What:** After searching items in a cycle, wait for a configurable delay, then poll *arr history to determine outcomes.
**When:** Every search cycle, after all searches complete, if tracking is enabled.
**Why:** Keeps tracking tightly coupled to the search that triggered it. No separate job coordination.

```python
# In engine.py, after all searches in a cycle complete:
if settings.general.tracking_delay_seconds > 0 and searched_items:
    await asyncio.sleep(settings.general.tracking_delay_seconds)

    for entry_id, item_info in searched_items:
        try:
            history = await client.get_movie_history(item_info["id"], event_type=RADARR_GRABBED)
            outcome = classify_radarr_outcome(
                movie_id=item_info["id"],
                search_time=search_timestamp,
                history_records=history,
            )
            if outcome != "unresolved":
                await update_search_outcome(db_path, entry_id, outcome, detail_text)
                stat_key = "radarr_movies_found" if queue == "missing" else "radarr_movies_upgraded"
                await increment_stat(db_path, stat_key)
        except Exception as exc:
            logger.debug("Radarr: Tracking failed for {item}: {exc}", item=..., exc=exc)
            # Tracking failures are non-fatal; outcome stays "searched"
```

### Pattern 2: Return Entry IDs from insert_search_entry

**What:** Modify `insert_search_entry()` to return the inserted row ID.
**When:** Every search entry insertion.
**Why:** Enables the post-search tracking phase to update specific rows without fragile name/timestamp queries.

```python
async def insert_search_entry(...) -> int:
    """Insert a search log entry and return the row ID."""
    # ... existing insert and prune logic ...
    cursor = await db.execute("SELECT last_insert_rowid()")
    row = await cursor.fetchone()
    return row[0]
```

### Pattern 3: Config-Driven Behavior with Sensible Defaults

**What:** All new config options have defaults that match current behavior or are conservatively safe.
**When:** All new config additions.
**Why:** Existing config files keep working without changes. No behavior change until users opt in.

New config keys with defaults:
```toml
[general]
tracking_delay_seconds = 90   # 0 = disable tracking
history_max_rows = 5000       # was hardcoded 500

[radarr]
page_size = 50                # was hardcoded 50
request_timeout = 30          # was hardcoded 30

[sonarr]
page_size = 50
request_timeout = 30
```

### Pattern 4: Tracking Failures Are Non-Fatal

**What:** If history polling or outcome classification fails for an item, log at debug level and move on. The search entry retains its "searched" outcome.
**When:** Any exception during the tracking phase.
**Why:** Tracking is observability, not core functionality. A failed tracking poll should never prevent the next search cycle or crash the application. The worst case is "searched" badges instead of "grabbed" badges.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Separate Tracking Scheduler Job
**What:** Running a periodic job that queries *arr history independently of search cycles.
**Why bad:** Requires tracking "which searches need checking," adds coordination between jobs sharing state via search_lock, needs its own error handling and retry logic, doubles the architectural complexity.
**Instead:** Track within the search cycle after a configurable delay.

### Anti-Pattern 2: Polling Full History Endpoint
**What:** Polling the paginated `/api/v3/history` endpoint to find grabs across all items.
**Why bad:** Scales poorly (history grows forever), includes non-fetcharr grabs (organic RSS grabs, manual searches), requires complex filtering and correlation.
**Instead:** Use per-movie (`/history/movie`) and per-series (`/history/series`) endpoints with `eventType=1` filter. Only check items actually searched this cycle.

### Anti-Pattern 3: Storing Lifetime Stats in state.json
**What:** Adding running counters to the JSON state file.
**Why bad:** state.json resets to defaults on corruption (the `_merge_defaults` function overwrites with zeros). Stats would be silently lost. JSON is not designed for frequent atomic counter increments.
**Instead:** Dedicated `lifetime_stats` SQLite table with `UPDATE ... SET value = value + ?`.

### Anti-Pattern 4: Connection Pool Library for SQLite
**What:** Using aiosqlitepool or multiple connections for the local SQLite database.
**Why bad:** SQLite serializes writes regardless of connection count. Multiple connections add overhead without throughput gain for this workload (~5-10 queries/minute). Connection pools solve a network database problem, not a local file problem.
**Instead:** Single shared connection with WAL mode. Close on shutdown.

### Anti-Pattern 5: Custom SIGTERM Signal Handler
**What:** Registering asyncio signal handlers for SIGTERM/SIGINT in __main__.py or startup.py.
**Why bad:** Uvicorn already handles these signals and triggers FastAPI lifespan shutdown. Custom handlers can break uvicorn's reload mechanism and cause double-shutdown or lost cleanup.
**Instead:** Use the lifespan `finally` block, which is already the shutdown handler. Confirmed via FastAPI community discussion.

## Build Order (Dependency-Aware)

The integration points create a natural dependency chain:

```
Phase 1: Foundation (no feature deps, enables everything after)
  - Connection pooling / shared connection + WAL (db.py)
  - Configurable pageSize (models/config.py, clients/, engine.py)
  - Request timeout config (models/config.py, clients/, scheduler.py)
  - Bounded history rows config (models/config.py, db.py)

Phase 2: Security and Operations (independent of tracking feature)
  - CSRF verification on settings POST (verify middleware.py coverage)
  - Rate limiting on search-now (routes.py)
  - Health check endpoint (routes.py, Dockerfile)
  - Graceful shutdown cleanup (scheduler.py, db.py)

Phase 3: Tracking Infrastructure (depends on Phase 1 for shared connection)
  - *arr history client methods (clients/radarr.py, clients/sonarr.py)
  - tracking.py pure correlation functions
  - Return entry IDs from insert_search_entry (db.py)
  - Outcome update function (db.py)
  - Lifetime stats table schema + CRUD (db.py)

Phase 4: Tracking Integration (depends on Phase 3)
  - Post-search tracking delay in engine.py cycles
  - Wire tracking into run_radarr_cycle
  - Wire tracking into run_sonarr_cycle
  - Tracking config (tracking_delay_seconds in models/config.py)

Phase 5: Dashboard Integration (depends on Phases 3-4 for data)
  - Outcome badges in search history UI (partials/history_results.html)
  - Lifetime stats cards on dashboard (dashboard.html, partials/)
  - Aggregate effectiveness stats display
  - Settings UI for new config options (tracking delay, history max, pageSize, timeout)
```

**Phase ordering rationale:**
1. **Foundation first** -- connection pooling and config plumbing affect every later phase; building on top of connection-per-op then retrofitting is wasteful
2. **Security/ops second** -- independent of tracking, reduces operational risk early, and each item is small/focused
3. **Tracking infrastructure third** -- the core new capability, all pure functions and DB operations, highly testable in isolation
4. **Integration fourth** -- wires tracking into existing engine.py cycles; depends on both foundation and infrastructure being in place
5. **Dashboard last** -- pure presentation; the data must exist before it can be displayed; template changes are low-risk

## Scalability Considerations

| Concern | Current (v1.2) | After v2.0 | Notes |
|---------|----------------|------------|-------|
| DB connections | Open/close per op | Single shared + WAL | Sufficient for single-instance |
| History table size | Hardcoded 500 rows | Configurable (default 5000) | SQLite handles millions; prune keeps bounded |
| Tracking API calls | N/A | 1 call per searched item per cycle | At 10 items/cycle, adds ~10 API calls |
| Cycle duration | ~5-15s | ~95-135s with 90s tracking delay | Delay configurable; 0 disables |
| Memory | Minimal | Unchanged (no in-memory caching) | SQLite is disk-backed |

**Critical note on cycle duration:** The tracking delay (default 90s) significantly extends cycle time. At a 30-minute interval, 90s out of 1800s is 5% -- acceptable. But with very short intervals (5 minutes), the tracking delay should be considered. The scheduler already prevents overlapping cycles via `search_lock`, so this is safe but could delay the next cycle start. The config documentation should note this.

## Sources

- [Radarr API Documentation](https://radarr.video/docs/api/) -- OpenAPI spec confirms `/history`, `/history/movie`, `/history/since` endpoints
- [Sonarr API Documentation](https://sonarr.tv/docs/api/) -- OpenAPI spec confirms `/history`, `/history/series` endpoints with seriesId, eventType params
- [Sonarr GitHub Issue #3587](https://github.com/Sonarr/Sonarr/issues/3587) -- Confirms eventType integer enum: 0=Unknown, 1=Grabbed, 2=SeriesFolderImported, 3=DownloadFolderImported, 4=DownloadFailed, 5=Deleted, 6=Renamed, 7=ImportFailed
- [Sonarr GitHub Issue #4727](https://github.com/Sonarr/Sonarr/issues/4727) -- Confirms `/history/series` endpoint exists, `seriesId` param works, `includeSeries`/`includeEpisode` bug was fixed
- [Go starr library - Sonarr](https://pkg.go.dev/golift.io/starr/sonarr) -- HistoryRecord struct (seriesId, episodeId, eventType, date, sourceTitle, quality, downloadId), FilterGrabbed=1 constant
- [pyarr Radarr docs](https://docs.totaldebug.uk/pyarr/modules/radarr.html) -- `get_movie_history(id, event_type)` method confirms per-movie history endpoint exists with eventType filter
- [pyarr Sonarr docs](https://docs.totaldebug.uk/pyarr/modules/sonarr.html) -- `get_history()` method with episode ID filter
- [DeepWiki Radarr REST API](https://deepwiki.com/radarr/radarr/4.1-rest-api) -- Confirms `/history/since` and `/history/movie` endpoint existence, HistoryService event-driven architecture
- [aiosqlite docs](https://aiosqlite.omnilib.dev/) -- Connection management patterns, asyncio bridge design
- [aiosqlitepool](https://github.com/slaily/aiosqlitepool) -- Evaluated and rejected for this use case (single-writer, low-frequency workload)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) -- Lifespan-based shutdown pattern
- [FastAPI Graceful Shutdown Discussion #6912](https://github.com/fastapi/fastapi/discussions/6912) -- Confirms uvicorn handles SIGTERM via lifespan; custom handlers risk interference

---
*Architecture research for: Fetcharr v2.0 -- Closed-Loop Tracking + Tech Debt*
*Researched: 2026-02-24*
