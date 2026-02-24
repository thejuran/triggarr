# Stack Research: v2.0 Additions

**Domain:** Closed-loop download tracking + tech debt resolution for existing Python/FastAPI search automation daemon
**Researched:** 2026-02-24
**Confidence:** HIGH (API endpoints verified against OpenAPI specs; library decisions informed by existing codebase patterns)
**Scope:** NEW capabilities only -- existing validated stack (Python 3.13, FastAPI, httpx, APScheduler 3.x, aiosqlite, Jinja2, htmx, Tailwind CSS v4) is not re-researched.

## Executive Summary

v2.0 needs **zero new PyPI dependencies**. Every new capability -- history polling, outcome correlation, lifetime stats, rate limiting, CSRF hardening, connection pooling, health check, graceful shutdown, request timeouts, configurable pageSize, bounded history -- is achievable with the existing stack plus stdlib. The Radarr/Sonarr history endpoints are well-documented REST calls that fit the existing `ArrClient` pattern perfectly. The 8 tech debt items are all internal code changes, not library additions.

## New API Endpoints Required

### Radarr History Endpoints

| Endpoint | Method | Purpose | Key Parameters |
|----------|--------|---------|----------------|
| `/api/v3/history` | GET | Paginated history with filters | `page`, `pageSize`, `sortKey`, `sortDirection`, `eventType` (int array), `movieIds` (int array), `includeMovie` (bool) |
| `/api/v3/history/movie` | GET | History for a specific movie | `movieId` (int), `eventType` (MovieHistoryEventType), `includeMovie` (bool) |

**MovieHistoryEventType filter values** (integer enum, 0-indexed):

| Value | Name | Meaning |
|-------|------|---------|
| 0 | Unknown | Unclassified event |
| 1 | Grabbed | Release grabbed from indexer (download started) |
| 2 | DownloadFolderImported | File imported from download client into library |
| 3 | DownloadFailed | Download failed |
| 4 | FileDeleted | Movie file deleted |
| 5 | FileRenamed | Movie file renamed |
| 6 | Ignored | Release ignored |

**Use `eventType=1` (Grabbed) for download detection.** This indicates a release was grabbed from an indexer -- exactly what "closed-loop" tracking needs. DownloadFolderImported (2) confirms the file was actually imported, useful for a "completed" badge later, but Grabbed is the primary signal.

**HistoryRecord response fields** (relevant subset):

```json
{
  "id": 12345,
  "movieId": 42,
  "sourceTitle": "Movie.Name.2024.1080p.BluRay.x264",
  "date": "2026-02-24T10:30:00Z",
  "eventType": "grabbed",
  "downloadId": "abc123def456",
  "data": {
    "indexer": "NZBgeek",
    "downloadClient": "SABnzbd"
  }
}
```

Source: Verified against Radarr OpenAPI spec at `https://raw.githubusercontent.com/Radarr/Radarr/develop/src/Radarr.Api.V3/openapi.json` and Go client `golift.io/starr/radarr` filter constants. HIGH confidence.

### Sonarr History Endpoints

| Endpoint | Method | Purpose | Key Parameters |
|----------|--------|---------|----------------|
| `/api/v3/history` | GET | Paginated history with filters | `page`, `pageSize`, `sortKey`, `sortDirection`, `eventType` (int array), `episodeId` (int), `seriesIds` (int array), `includeSeries` (bool), `includeEpisode` (bool) |
| `/api/v3/history/series` | GET | History for a specific series/season | `seriesId` (int), `seasonNumber` (int), `eventType` (EpisodeHistoryEventType), `includeSeries` (bool), `includeEpisode` (bool) |

**EpisodeHistoryEventType filter values** (integer enum, 0-indexed):

| Value | Name | Meaning |
|-------|------|---------|
| 0 | Unknown | Unclassified event |
| 1 | Grabbed | Release grabbed from indexer |
| 2 | SeriesFolderImported | Imported from series folder |
| 3 | DownloadFolderImported | File imported from download client |
| 4 | DownloadFailed | Download failed |
| 5 | Deleted | Episode file deleted |
| 6 | Renamed | Episode file renamed |
| 7 | ImportFailed | Import failed |

**Use `/api/v3/history/series` with `seriesId` + `seasonNumber` + `eventType=1`.** This is the ideal endpoint for fetcharr because searches are already at season level -- the history query mirrors the search scope exactly. No need to cross-reference individual episodeIds.

Source: Verified against Sonarr OpenAPI spec at `https://raw.githubusercontent.com/Sonarr/Sonarr/develop/src/Sonarr.Api.V3/openapi.json` and Go client `golift.io/starr/sonarr` filter constants (lines 23-31). Also cross-referenced with Sonarr issue #3587 confirming eventType filter support. HIGH confidence.

### Integration with Existing ArrClient

Both history endpoints fit the existing `ArrClient.get()` and `ArrClient.get_paginated()` methods perfectly. New methods on `RadarrClient` and `SonarrClient`:

```python
# RadarrClient -- add to fetcharr/clients/radarr.py
async def get_history_for_movie(self, movie_id: int, event_type: int = 1) -> list[dict]:
    """Fetch grabbed history events for a specific movie."""
    response = await self.get(
        "/api/v3/history/movie",
        params={"movieId": movie_id, "eventType": event_type, "includeMovie": False},
    )
    return response.json()

# SonarrClient -- add to fetcharr/clients/sonarr.py
async def get_history_for_season(
    self, series_id: int, season_number: int, event_type: int = 1
) -> list[dict]:
    """Fetch grabbed history events for a specific series/season."""
    response = await self.get(
        "/api/v3/history/series",
        params={
            "seriesId": series_id,
            "seasonNumber": season_number,
            "eventType": event_type,
            "includeSeries": False,
            "includeEpisode": False,
        },
    )
    return response.json()
```

No new HTTP client, no new request pattern, no new dependencies. Same retry logic, same timeout, same error handling.

## Tech Debt Resolution Stack

All 8 tech debt items require **zero new dependencies**. Here is the implementation approach for each:

### 1. Rate Limiting on search-now Endpoint

**Approach:** Simple in-memory time-based throttle using stdlib `time.monotonic()`.

**Why NOT slowapi/Redis:** Fetcharr is a single-process, single-user local network tool. Adding slowapi (which depends on the `limits` library, which supports Redis/memcached backends) is massive overkill. A 4-line in-memory check is sufficient and adds zero dependencies.

```python
# In web/routes.py or web/middleware.py
import time

_last_search_now: dict[str, float] = {}
SEARCH_NOW_COOLDOWN = 10.0  # seconds

def check_rate_limit(app_name: str) -> bool:
    """Return True if rate limit allows the request."""
    now = time.monotonic()
    if now - _last_search_now.get(app_name, 0) < SEARCH_NOW_COOLDOWN:
        return False
    _last_search_now[app_name] = now
    return True
```

**Why this works:** Single uvicorn process, no workers, single event loop. The dict is shared across all requests. No race conditions because async Python is cooperative (no preemption within a coroutine). The cooldown resets after each successful trigger.

### 2. CSRF Protection on Settings POST

**Approach:** Extend existing `OriginCheckMiddleware` -- it already validates Origin/Referer headers on all POST requests. The tech debt item was flagged before this middleware existed. Verify the settings POST route is covered (it is -- the middleware applies to all POST methods), and document it.

**Why NOT token-based CSRF:** Token-based CSRF requires sessions/cookies. Fetcharr has no authentication, no cookies, no sessions. Origin/Referer validation is the correct CSRF defense for cookie-less applications. This is already implemented in `fetcharr/web/middleware.py`. The tech debt resolution is verification + test coverage, not new code.

### 3. Connection Pooling for aiosqlite

**Approach:** Single shared `aiosqlite.Connection` held in `app.state`, opened at lifespan startup, closed at lifespan shutdown. Replace the current connection-per-operation pattern (`async with aiosqlite.connect(db_path) as db:` on every call) with the shared connection.

**Why NOT aiosqlitepool:** aiosqlitepool v1.0.0 (released July 2025) is a connection pool -- but connection pooling for SQLite is fundamentally different from PostgreSQL/MySQL pooling. SQLite serializes all writes to a single file via a file lock. A "pool" of SQLite connections provides no write concurrency benefit. The only benefit is avoiding the ~0.5ms connection open/close overhead per operation.

For fetcharr's workload (~5-10 DB operations per search cycle, ~2-3 per UI request), the overhead of opening/closing is negligible. A single persistent connection is the simplest pattern that eliminates the overhead entirely:

```python
# In scheduler.py lifespan
db_conn = await aiosqlite.connect(db_path)
db_conn.row_factory = aiosqlite.Row
app.state.db_conn = db_conn

# In finally block
await app.state.db_conn.close()
```

All `db.py` functions change from `async with aiosqlite.connect(db_path) as db:` to accepting the connection directly. WAL mode should be enabled for concurrent read/write:

```python
await db_conn.execute("PRAGMA journal_mode=WAL")
```

### 4. Health Check Endpoint

**Approach:** Add a `GET /health` route to `web/routes.py` returning JSON `{"status": "ok"}` with 200. Update Dockerfile HEALTHCHECK to use this endpoint instead of hitting the dashboard.

```python
@router.get("/health")
async def health_check():
    return {"status": "ok"}
```

Update Dockerfile:
```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1
```

The current Dockerfile already has a HEALTHCHECK hitting `/` -- the dashboard route does template rendering and a DB query, which is heavier than needed. A lightweight `/health` is more appropriate. No new dependency needed; stdlib `urllib.request` in the HEALTHCHECK CMD is already used.

### 5. Graceful Shutdown Handler

**Approach:** The FastAPI lifespan `finally` block already handles shutdown cleanup (scheduler stop, client close). What is missing is SIGTERM signal handling to ensure the lifespan cleanup runs when Docker sends SIGTERM (which it does on `docker stop`).

Uvicorn already handles SIGTERM by default -- it triggers a graceful shutdown that allows the lifespan `__aexit__` to run. The fix is:

1. Ensure the Dockerfile uses exec form (it does: `ENTRYPOINT ["/entrypoint.sh"]`), so PID 1 receives SIGTERM.
2. Verify entrypoint.sh uses `exec` to replace the shell process so uvicorn is PID 1.
3. Add a STOPSIGNAL directive to the Dockerfile.

```dockerfile
STOPSIGNAL SIGTERM
```

If the entrypoint shell script does NOT `exec`, add `exec` before the Python command. No new Python library needed -- uvicorn's built-in signal handling + FastAPI's lifespan context manager already provide graceful shutdown.

### 6. Request Timeout on Outbound HTTP Calls

**Already implemented.** The `ArrClient.__init__` already sets `timeout=httpx.Timeout(timeout)` with a default of 30.0 seconds. This applies to all outbound calls (wanted/missing, wanted/cutoff, command triggers).

The tech debt resolution is to:
1. Make the timeout configurable via `fetcharr.toml` (e.g., `[general] request_timeout = 30`).
2. Add specific timeout tuning for history polling (may want a shorter timeout since history calls are less critical than search triggers).

No new library -- httpx's `Timeout` class already supports per-request overrides:
```python
response = await self._client.request(method, path, timeout=httpx.Timeout(15.0), **kwargs)
```

### 7. Configurable pageSize Defaults

**Approach:** Add `page_size` field to `ArrConfig` Pydantic model (default 50). Pass through to `get_paginated()` calls.

```python
class ArrConfig(BaseModel):
    page_size: int = 50  # pageSize for *arr API pagination
```

Currently hardcoded as `page_size: int = 50` in `ArrClient.get_paginated()`. Change call sites to pass `settings.radarr.page_size` instead. No new library.

### 8. Bounded Search History Table Growth

**Already implemented.** The `insert_search_entry()` function in `db.py` already prunes to 500 rows after each insert:

```python
await db.execute(
    "DELETE FROM search_history WHERE id NOT IN ("
    "    SELECT id FROM search_history ORDER BY id DESC LIMIT 500"
    ")"
)
```

The tech debt resolution is to make the 500 limit configurable:
1. Add `history_max_rows` to `GeneralConfig` (default 500).
2. Pass the setting to `insert_search_entry()` instead of hardcoding 500.

No new library.

## New SQLite Tables/Columns

### Lifetime Stats Table

```sql
CREATE TABLE IF NOT EXISTS lifetime_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_key TEXT NOT NULL UNIQUE,
    stat_value INTEGER NOT NULL DEFAULT 0
);
```

Keys: `radarr_movies_found`, `radarr_movies_updated`, `sonarr_episodes_found`, `sonarr_episodes_updated`.

Increment atomically: `UPDATE lifetime_stats SET stat_value = stat_value + 1 WHERE stat_key = ?`

### Search History Columns (for outcome tracking)

The `outcome` and `detail` columns already exist (added in v1.0 migration). Outcome values will expand:

| Outcome | Meaning | When Set |
|---------|---------|----------|
| `searched` | Search triggered, no outcome yet | At search time (existing) |
| `failed` | Search command failed | At search time (existing) |
| `grabbed` | All items from search were grabbed | After history poll confirms grab |
| `partial` | Some but not all items grabbed (Sonarr season) | After history poll shows partial season grab |
| `unresolved` | Polling window expired with no grab detected | After timeout (e.g., 2 hours post-search) |

No schema migration needed -- `outcome` is already TEXT, and these are just new string values.

## What NOT to Add

| Library | Why Someone Might Suggest It | Why Not |
|---------|------------------------------|---------|
| slowapi | Rate limiting on search-now | Overkill for single-user local tool; in-memory `time.monotonic()` check is 4 lines, zero deps |
| aiosqlitepool | Connection pooling for SQLite | SQLite does not benefit from connection pools the way PostgreSQL does; single persistent connection is simpler and sufficient |
| redis / memcached | Rate limit state storage | Single-process app; in-memory dict is correct |
| celery / dramatiq | Background task queue | APScheduler already handles scheduled polling; adding a task queue is architectural overkill |
| SQLAlchemy / databases | ORM for lifetime stats | 3 tables with 5 queries total; raw aiosqlite with hand-written SQL is clearer and has zero abstraction overhead |
| python-jose / itsdangerous | CSRF tokens | No sessions/cookies means no token-based CSRF; Origin/Referer validation is the correct approach |
| limits (standalone) | Rate limiting primitives | Only needed if using multiple rate limit algorithms or persistence; a simple cooldown timer is sufficient |

## Existing Dependencies That Cover Everything

| Existing Dependency | v2.0 Use | Already In pyproject.toml |
|---------------------|----------|---------------------------|
| httpx | History endpoint polling (same AsyncClient, same retry logic) | Yes |
| aiosqlite | Lifetime stats table, outcome updates, bounded history config | Yes |
| APScheduler 3.x | Schedule history polling job (new interval job alongside existing search jobs) | Yes |
| Pydantic / pydantic-settings | New config fields (page_size, history_max_rows, request_timeout, poll_interval, poll_window) | Yes |
| FastAPI | Health check route, rate-limited search-now | Yes |
| Jinja2 / htmx | Outcome badges, lifetime stats cards, effectiveness stats | Yes |
| loguru | Logging for poll results, outcome transitions | Yes |

## New Configuration Fields

Add to `fetcharr.toml` via Pydantic models:

```toml
[general]
# Existing
log_level = "info"
hard_max_per_cycle = 0

# New for v2.0
request_timeout = 30        # Seconds for outbound HTTP calls (already implemented, just configurable now)
history_max_rows = 500       # Max search history rows in SQLite (already implemented, just configurable now)
poll_delay = 120             # Seconds after search before first history poll
poll_window = 7200           # Seconds to keep polling for grabs (2 hours)
poll_interval = 300          # Seconds between poll checks (5 minutes)

[radarr]
page_size = 50               # pageSize for Radarr API pagination

[sonarr]
page_size = 50               # pageSize for Sonarr API pagination
```

All fields have sensible defaults that maintain backward compatibility -- existing `fetcharr.toml` files work unchanged.

## Version Compatibility

No new packages means no new compatibility concerns. The only thing to verify:

| Concern | Status |
|---------|--------|
| Radarr v3 history API stability | Stable -- used by Radarr's own UI since v3.0; no deprecation signals |
| Sonarr v3 history/series API stability | Stable -- `/api/v3/history/series` works on both Sonarr v3 and v4 (v4 maintains v3 API compat) |
| aiosqlite single persistent connection | Supported -- aiosqlite Connection object is designed for reuse; WAL mode enables concurrent reads during writes |
| APScheduler multiple interval jobs | Supported -- scheduler can run N independent interval jobs; adding a poll job alongside search jobs is standard usage |

## Sources

- Radarr OpenAPI specification -- https://raw.githubusercontent.com/Radarr/Radarr/develop/src/Radarr.Api.V3/openapi.json (HIGH confidence, primary source)
- Sonarr OpenAPI specification -- https://raw.githubusercontent.com/Sonarr/Sonarr/develop/src/Sonarr.Api.V3/openapi.json (HIGH confidence, primary source)
- Radarr MovieHistoryEventType filter constants -- https://pkg.go.dev/golift.io/starr/radarr (HIGH confidence, verified against OpenAPI)
- Sonarr EpisodeHistoryEventType filter constants -- https://pkg.go.dev/golift.io/starr/sonarr (HIGH confidence, verified against Sonarr source ref in comment)
- Sonarr eventType filter support confirmation -- https://github.com/Sonarr/Sonarr/issues/3587 (HIGH confidence, official repo issue)
- Sonarr history/series includeSeries parameter -- https://github.com/Sonarr/Sonarr/issues/4727 (MEDIUM confidence, issue discussion)
- aiosqlite 0.22.1 -- https://pypi.org/project/aiosqlite/ (HIGH confidence, verified 2026-02-24)
- aiosqlitepool assessment -- https://github.com/slaily/aiosqlitepool (MEDIUM confidence, evaluated and rejected)
- FastAPI lifespan shutdown -- https://fastapi.tiangolo.com/advanced/events/ (HIGH confidence, official docs)
- FastAPI graceful shutdown discussion -- https://github.com/fastapi/fastapi/discussions/6912 (MEDIUM confidence, community discussion)
- httpx timeout configuration -- https://www.python-httpx.org/advanced/timeouts/ (HIGH confidence, official docs)
- slowapi assessment -- https://github.com/laurentS/slowapi (MEDIUM confidence, evaluated and rejected for this use case)
- Radarr API docs portal -- https://radarr.video/docs/api/ (HIGH confidence, official docs)
- Sonarr API docs portal -- https://sonarr.tv/docs/api/ (HIGH confidence, official docs)

---
*Stack research for: Fetcharr v2.0 -- closed-loop download tracking + tech debt*
*Researched: 2026-02-24*
