# Phase 2: Search Engine - Research

**Researched:** 2026-02-23
**Domain:** Scheduled task automation, *arr API command integration, round-robin queue management
**Confidence:** HIGH

## Summary

Phase 2 builds the core search engine that cycles through Radarr and Sonarr wanted/missing and cutoff-unmet items on a configurable schedule. The Phase 1 foundation provides async HTTP clients with paginated fetching, atomic JSON state persistence, and TOML configuration -- all directly usable as building blocks.

The technical challenge decomposes into three clean concerns: (1) fetching and filtering item lists from *arr APIs, slicing batches via round-robin cursors, and issuing search commands, (2) deduplicating Sonarr episodes to season-level before searching, and (3) wiring scheduled execution via APScheduler's AsyncIOScheduler integrated through FastAPI's lifespan context manager. All three are well-understood patterns with high-confidence implementation paths.

**Primary recommendation:** Use APScheduler 3.x AsyncIOScheduler with interval triggers, wired through FastAPI's `@asynccontextmanager` lifespan. Keep search logic as pure async functions that receive clients and state as arguments for testability. Persist state after each cycle, not after each individual item search.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Re-fetch item lists from *arr at the start of every cycle -- always current, grabbed items disappear immediately
- Cursor stores a position index (not item ID) -- simple, predictable, self-correcting on wrap
- On wrap past end of list, cursor resets to 0 silently -- no log entry for wrap events
- Missing and cutoff-unmet run on the same timer per app, interleaved -- one interval triggers a batch of missing then a batch of cutoff-unmet
- Default search interval: 30 minutes per app
- Default batch size: 5 items per queue per cycle
- Radarr and Sonarr share the same defaults but are independently configurable
- First search cycle runs immediately on startup -- no waiting for the first interval
- Individual item search failure: skip and continue -- log the failure, advance cursor past it, search remaining items in batch
- *arr unreachable mid-cycle: abort entire cycle, try again at next interval -- no retry loop
- On abort, cursor stays in place -- next successful cycle picks up exactly where this one left off
- Radarr and Sonarr cycles are independent -- one app failing does not block the other
- Keep last 50 entries in state file (bounded, oldest evicted)
- Each entry contains: item name, timestamp, app (Radarr/Sonarr), queue type (missing/cutoff-unmet)
- Sonarr entries show "Show Title - Season N" format (e.g., "Breaking Bad - Season 3")
- Log entries go to both stdout (structured logging) and state file (for Web UI in Phase 3)

### Claude's Discretion
- Exact APScheduler job configuration and lifespan wiring
- Internal data structures for queue management
- Structured logging format details
- State file schema evolution from Phase 1

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SRCH-01 | Fetch wanted (missing) items from Radarr | RadarrClient.get_wanted_missing() already exists; returns list[dict] with `id`, `title`, `monitored` fields |
| SRCH-02 | Fetch cutoff unmet items from Radarr | RadarrClient.get_wanted_cutoff() already exists; returns list[dict] with same fields |
| SRCH-03 | Fetch wanted (missing) items from Sonarr | SonarrClient.get_wanted_missing() already exists with includeSeries=true; returns episodes with `seriesId`, `seasonNumber`, `monitored`, `airDateUtc`, and nested `series.title` |
| SRCH-04 | Fetch cutoff unmet items from Sonarr | SonarrClient.get_wanted_cutoff() already exists with includeSeries=true; same episode structure |
| SRCH-05 | Round-robin sequential cycling with wrap | Position-index cursor with modulo arithmetic; state.py already persists cursors |
| SRCH-06 | Sonarr SeasonSearch at season level | POST /api/v3/command with `{"name": "SeasonSearch", "seriesId": N, "seasonNumber": N}`; episode deduplication to (seriesId, seasonNumber) pairs |
| SRCH-07 | Separate cursors per queue per app | Four independent cursors: radarr.missing_cursor, radarr.cutoff_cursor, sonarr.missing_cursor, sonarr.cutoff_cursor; state schema already has missing_cursor and cutoff_cursor per app |
| SRCH-08 | Cursor positions persist across restarts | load_state/save_state already implemented with atomic writes; cursors read on startup, written after each cycle |
| SRCH-09 | Unmonitored items filtered out | Filter on `record["monitored"] == True` before adding to queue |
| SRCH-10 | Future air date items filtered from Sonarr | Filter on `airDateUtc` -- exclude episodes where airDateUtc is null (TBA) or in the future relative to now |
| SRCH-11 | Search log shows human-readable names | Radarr: `record["title"]`; Sonarr: `f"{record['series']['title']} - Season {record['seasonNumber']}"` |
| CONF-01 | Configurable items per cycle per app | New config fields: `radarr.search_missing_count`, `radarr.search_cutoff_count` (and same for sonarr), defaulting to 5 |
| CONF-02 | Configurable search interval per app | New config fields: `radarr.search_interval` and `sonarr.search_interval` in minutes, defaulting to 30 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| APScheduler | 3.11.2 | Interval-based job scheduling | Mature, stable, AsyncIOScheduler integrates directly with asyncio event loop; 3.x is production-stable (4.x still alpha) |
| httpx | (existing) | Async HTTP client for *arr API calls | Already in use from Phase 1; ArrClient wraps it |
| loguru | (existing) | Structured logging with redaction | Already configured from Phase 1 |
| pydantic | (existing) | Config models and validation | Already in use for Settings and API response models |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| datetime (stdlib) | -- | Timestamp comparison for future air date filtering | Comparing airDateUtc against UTC now |
| json (stdlib) | -- | State file persistence | Already used in state.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| APScheduler | asyncio.create_task + asyncio.sleep loop | Simpler but no job management, no graceful shutdown coordination, no missed-fire handling |
| APScheduler | Celery / Dramatiq | Massive overkill -- requires external broker (Redis/RabbitMQ); this is a single-process scheduler |

**Installation:**
```bash
pip install apscheduler
```
Or add `"apscheduler>=3.11,<4"` to `pyproject.toml` dependencies.

## Architecture Patterns

### Recommended Project Structure
```
fetcharr/
├── __init__.py
├── __main__.py           # Entry point (modify for lifespan)
├── config.py             # TOML loading (add search config fields)
├── logging.py            # Loguru setup (unchanged)
├── startup.py            # Startup sequence (modify for search engine init)
├── state.py              # JSON state persistence (extend schema)
├── clients/
│   ├── base.py           # ArrClient with paginated fetch + retry
│   ├── radarr.py         # RadarrClient (add search_movies method)
│   └── sonarr.py         # SonarrClient (add search_season method)
├── models/
│   ├── arr.py            # API response models (unchanged)
│   └── config.py         # Settings models (add search config)
└── search/
    ├── __init__.py
    ├── engine.py          # Core search cycle logic (fetch, filter, slice, search, log)
    └── scheduler.py       # APScheduler setup, lifespan wiring, job definitions
```

### Pattern 1: Search Cycle as Pure Async Function
**What:** Each search cycle is a standalone async function that receives its dependencies (client, state, settings) as arguments rather than accessing globals.
**When to use:** Always -- this makes the function independently testable without needing a running scheduler or FastAPI app.
**Example:**
```python
async def run_radarr_cycle(
    client: RadarrClient,
    state: FetcharrState,
    settings: Settings,
) -> FetcharrState:
    """Run one Radarr search cycle: missing batch then cutoff batch."""
    # 1. Fetch current wanted lists
    missing = await client.get_wanted_missing()
    cutoff = await client.get_wanted_cutoff()

    # 2. Filter: monitored only
    missing = [m for m in missing if m.get("monitored", False)]
    cutoff = [c for c in cutoff if c.get("monitored", False)]

    # 3. Slice batch from cursor position
    cursor = state["radarr"]["missing_cursor"]
    batch = missing[cursor:cursor + settings.radarr.search_missing_count]

    # 4. Search each item, skip on failure
    for movie in batch:
        try:
            await client.search_movies([movie["id"]])
            log_search(state, "Radarr", "missing", movie["title"])
        except Exception:
            logger.warning("Failed to search: {title}", title=movie["title"])

    # 5. Advance cursor (wrap on end)
    new_cursor = cursor + len(batch)
    if new_cursor >= len(missing):
        new_cursor = 0
    state["radarr"]["missing_cursor"] = new_cursor

    # ... repeat for cutoff queue ...
    return state
```

### Pattern 2: Sonarr Episode-to-Season Deduplication
**What:** Sonarr returns episode-level records from wanted/missing. Multiple episodes from the same season of the same series must be deduplicated to a single (seriesId, seasonNumber) pair before issuing SeasonSearch commands.
**When to use:** Always when processing Sonarr queues -- searching at episode level would hammer indexers and is explicitly excluded by requirements.
**Example:**
```python
def deduplicate_to_seasons(
    episodes: list[dict],
) -> list[dict]:
    """Deduplicate episode records to unique (seriesId, seasonNumber) pairs.

    Returns a list of dicts with seriesId, seasonNumber, and display_name
    for logging. Order is preserved (first occurrence wins).
    """
    seen: set[tuple[int, int]] = set()
    seasons: list[dict] = []
    for ep in episodes:
        key = (ep["seriesId"], ep["seasonNumber"])
        if key not in seen:
            seen.add(key)
            series_title = ep.get("series", {}).get("title", f"Series {ep['seriesId']}")
            seasons.append({
                "seriesId": ep["seriesId"],
                "seasonNumber": ep["seasonNumber"],
                "display_name": f"{series_title} - Season {ep['seasonNumber']}",
            })
    return seasons
```

### Pattern 3: APScheduler Lifespan Integration
**What:** Create AsyncIOScheduler in the FastAPI lifespan context manager, add interval jobs, and let it manage the event loop integration.
**When to use:** For wiring the periodic search cycles.
**Example:**
```python
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()

    # Add jobs with configurable intervals
    scheduler.add_job(
        radarr_cycle_wrapper,
        "interval",
        minutes=settings.radarr.search_interval,
        id="radarr_search",
        next_run_time=datetime.now(),  # Run immediately on startup
    )
    scheduler.add_job(
        sonarr_cycle_wrapper,
        "interval",
        minutes=settings.sonarr.search_interval,
        id="sonarr_search",
        next_run_time=datetime.now(),  # Run immediately on startup
    )

    scheduler.start()
    yield
    scheduler.shutdown(wait=False)

app = FastAPI(lifespan=lifespan)
```

### Pattern 4: Bounded Search Log with Eviction
**What:** The search log is a bounded list (max 50 entries). New entries are appended; when the list exceeds the cap, the oldest entries are evicted.
**When to use:** Every time a search action is logged.
**Example:**
```python
SEARCH_LOG_MAX = 50

def append_search_log(
    state: FetcharrState,
    app: str,
    queue_type: str,
    item_name: str,
) -> None:
    """Append a search log entry and evict oldest if over cap."""
    entry = {
        "name": item_name,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "app": app,
        "queue_type": queue_type,
    }
    state["search_log"].append(entry)
    # Evict oldest entries beyond cap
    if len(state["search_log"]) > SEARCH_LOG_MAX:
        state["search_log"] = state["search_log"][-SEARCH_LOG_MAX:]
```

### Anti-Patterns to Avoid
- **Searching at episode level in Sonarr:** Triggers one search per episode instead of per season, hammering indexers. Always deduplicate to (seriesId, seasonNumber) first.
- **Storing cursor as item ID instead of position index:** Breaks when items are grabbed (removed from list). Position index naturally handles list changes because the list is re-fetched every cycle.
- **Retrying failed cycles in a loop:** User decision is explicit -- abort on *arr unreachable, try again at next scheduled interval. No retry loops.
- **Shared cursor state between missing and cutoff queues:** Each queue has its own independent cursor. Advancing missing does not touch cutoff.
- **Saving state after each individual item search:** Unnecessarily thrashes disk. Save once after each complete cycle.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Interval scheduling | Custom asyncio.sleep loop with error handling | APScheduler AsyncIOScheduler | Handles missed fires, graceful shutdown, timezone-aware scheduling out of the box |
| Atomic file writes | Manual temp file + rename | Existing state.py save_state() | Already implemented with os.replace and fsync |
| HTTP retry logic | Custom retry decorator | Existing ArrClient._request_with_retry() | Already handles single retry with 2s backoff for all HTTP methods |
| Paginated fetching | Manual page iteration | Existing ArrClient.get_paginated() | Already handles pagination termination on empty page or total record count |

**Key insight:** Phase 1 already built the hard infrastructure (HTTP client with retry, paginated fetching, atomic state writes, config loading). Phase 2's job is orchestration logic on top of these building blocks, not rebuilding plumbing.

## Common Pitfalls

### Pitfall 1: Cursor Drift When List Size Changes Between Fetch and Search
**What goes wrong:** Items are fetched, filtered, and a batch is sliced. Between fetching and the next cycle, items may be grabbed (downloaded), changing the list. The cursor position from last cycle may now point past the end of the shorter list.
**Why it happens:** The list is re-fetched every cycle, and its length can shrink as items are successfully downloaded.
**How to avoid:** After re-fetching and filtering, clamp the cursor to `min(cursor, len(items))`. If cursor >= len(items), wrap to 0. The user decision explicitly states "on wrap past end, reset to 0 silently."
**Warning signs:** Cursor position is larger than list length in logs.

### Pitfall 2: Sonarr airDateUtc is Null for TBA Episodes
**What goes wrong:** Some Sonarr episodes have `airDateUtc` set to `null` (no air date announced). Trying to parse this as a datetime or compare it to now raises an error.
**Why it happens:** Sonarr creates episode placeholders for announced but undated episodes (e.g., "Season 3, TBA").
**How to avoid:** Treat null airDateUtc as "future" -- filter out episodes where airDateUtc is None or where the parsed datetime is in the future.
**Warning signs:** TypeError or AttributeError when processing Sonarr episodes.

### Pitfall 3: APScheduler Job Runs Before State is Loaded
**What goes wrong:** If the scheduler starts jobs before the startup sequence completes (config loaded, connections validated, state loaded), jobs crash.
**Why it happens:** APScheduler starts executing jobs as soon as `scheduler.start()` is called if `next_run_time` is set to now.
**How to avoid:** Complete all startup initialization (load config, validate connections, load state, create clients) before calling `scheduler.start()`. The lifespan context manager should do startup work first, then start the scheduler.
**Warning signs:** KeyError or AttributeError in the first job execution.

### Pitfall 4: Sonarr includeSeries=true Not Set
**What goes wrong:** Without `includeSeries=true`, episode records lack the nested `series` object, so `episode["series"]["title"]` raises KeyError. Season-level deduplication and human-readable logging both fail.
**Why it happens:** The Sonarr API defaults to not including series data in episode records.
**How to avoid:** Already handled -- SonarrClient.get_wanted_missing() and get_wanted_cutoff() pass `extra_params={"includeSeries": "true"}`. Verify this remains in place.
**Warning signs:** KeyError on "series" when accessing episode records.

### Pitfall 5: MoviesSearch Command Expects Array, Not Single ID
**What goes wrong:** Passing a single integer instead of an array to `movieIds` causes a 400 error from Radarr.
**Why it happens:** The API schema defines movieIds as `array[int]`, not a single int.
**How to avoid:** Always wrap movie IDs in a list: `{"name": "MoviesSearch", "movieIds": [movie_id]}`. For batch searches, pass multiple IDs: `{"name": "MoviesSearch", "movieIds": [id1, id2, id3]}`.
**Warning signs:** HTTP 400 Bad Request from Radarr command endpoint.

### Pitfall 6: Config Schema Not Backward-Compatible
**What goes wrong:** Adding new required fields to the TOML config (search_interval, search_missing_count, etc.) breaks existing config files that don't have these fields.
**Why it happens:** Users upgrading from Phase 1 have a config file without the new [radarr]/[sonarr] search fields.
**How to avoid:** All new config fields MUST have sensible defaults (search_interval=30, search_missing_count=5, search_cutoff_count=5). Use Pydantic's `Field(default=...)` so the config loads even if the new fields are absent.
**Warning signs:** ValidationError on startup with existing config files.

## Code Examples

### Radarr MoviesSearch Command
```python
# POST /api/v3/command
# Body: {"name": "MoviesSearch", "movieIds": [123, 456, 789]}
# Source: Radarr OpenAPI spec + Huntarr implementation + Go starr package

async def search_movies(self, movie_ids: list[int]) -> httpx.Response:
    """Trigger a MoviesSearch command for the given movie IDs."""
    return await self.post(
        "/api/v3/command",
        json_data={"name": "MoviesSearch", "movieIds": movie_ids},
    )
```

### Sonarr SeasonSearch Command
```python
# POST /api/v3/command
# Body: {"name": "SeasonSearch", "seriesId": 123, "seasonNumber": 1}
# Source: Sonarr wiki + Go starr package CommandRequest struct

async def search_season(self, series_id: int, season_number: int) -> httpx.Response:
    """Trigger a SeasonSearch command for a specific season."""
    return await self.post(
        "/api/v3/command",
        json_data={
            "name": "SeasonSearch",
            "seriesId": series_id,
            "seasonNumber": season_number,
        },
    )
```

### Sonarr Future Air Date Filtering
```python
from datetime import datetime, timezone

def filter_sonarr_episodes(episodes: list[dict]) -> list[dict]:
    """Filter out unmonitored and future/TBA episodes."""
    now = datetime.now(timezone.utc)
    filtered = []
    for ep in episodes:
        # Skip unmonitored
        if not ep.get("monitored", False):
            continue
        # Skip future or TBA episodes
        air_date_str = ep.get("airDateUtc")
        if air_date_str is None:
            continue  # TBA = treat as future
        try:
            air_date = datetime.fromisoformat(air_date_str.replace("Z", "+00:00"))
            if air_date > now:
                continue  # Future episode
        except (ValueError, TypeError):
            continue  # Unparseable date = skip
        filtered.append(ep)
    return filtered
```

### Round-Robin Batch Slicing
```python
def slice_batch(items: list, cursor: int, batch_size: int) -> tuple[list, int]:
    """Slice a batch from items starting at cursor, returning new cursor.

    If cursor is past end of list, wraps to 0.
    Returns (batch, new_cursor).
    """
    if not items:
        return [], 0

    # Clamp cursor to list bounds
    if cursor >= len(items):
        cursor = 0

    batch = items[cursor:cursor + batch_size]
    new_cursor = cursor + len(batch)

    # Wrap if we've reached the end
    if new_cursor >= len(items):
        new_cursor = 0

    return batch, new_cursor
```

### Config Model Extension
```python
# Added to ArrConfig in models/config.py
class ArrConfig(BaseModel):
    url: str = ""
    api_key: SecretStr = SecretStr("")
    enabled: bool = False
    search_interval: int = 30          # minutes between search cycles
    search_missing_count: int = 5      # items per missing batch
    search_cutoff_count: int = 5       # items per cutoff batch
```

### Default Config Template Extension
```toml
[radarr]
url = ""
api_key = ""
enabled = false
# search_interval = 30       # Minutes between search cycles
# search_missing_count = 5   # Missing items to search per cycle
# search_cutoff_count = 5    # Cutoff items to search per cycle

[sonarr]
url = ""
api_key = ""
enabled = false
# search_interval = 30
# search_missing_count = 5
# search_cutoff_count = 5
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| APScheduler 4.x (alpha) | APScheduler 3.11.x (stable) | 4.x in alpha since 2023 | Use 3.x -- 4.x API is unstable and underdocumented; 3.x is production-proven |
| FastAPI @app.on_event("startup") | FastAPI lifespan context manager | FastAPI 0.93+ (2023) | on_event is deprecated; lifespan is the correct pattern |
| Synchronous BackgroundScheduler | AsyncIOScheduler | APScheduler 3.x | AsyncIOScheduler runs jobs on the asyncio event loop; BackgroundScheduler runs on a separate thread |

**Deprecated/outdated:**
- `@app.on_event("startup")` / `@app.on_event("shutdown")`: Deprecated in favor of lifespan context manager
- APScheduler 4.x: Still in alpha (4.0.0a6, April 2025); not production-ready

## Open Questions

1. **MoviesSearch: single command with multiple IDs vs. one command per movie?**
   - What we know: The API accepts `movieIds` as an array. Passing multiple IDs in one command triggers a single Radarr search job for all of them.
   - What's unclear: Whether searching 5 movies in one command vs. 5 separate commands affects indexer hit behavior differently from Radarr's perspective.
   - Recommendation: Use a single command with all batch IDs (`movieIds: [id1, id2, ...]`). This is what Huntarr does and reduces API calls. If individual failure tracking is needed, fall back to one command per movie. Start with batch approach; if per-item error logging is critical, iterate individually.

2. **Radarr wanted/missing vs. cutoff endpoint: are records already filtered to monitored?**
   - What we know: The `/api/v3/wanted/missing` endpoint returns movies without files. The `/api/v3/wanted/cutoff` returns movies not meeting quality cutoff.
   - What's unclear: Whether these endpoints already filter to only monitored items, or whether unmonitored items are included in the response.
   - Recommendation: Always filter on `monitored == True` client-side regardless. This is defensive and costs nothing since we already iterate the list. The requirement (SRCH-09) explicitly mandates this filtering.

## Sources

### Primary (HIGH confidence)
- [Go starr package - Sonarr types](https://pkg.go.dev/golift.io/starr/sonarr) - Episode struct with seriesId, seasonNumber, monitored, airDateUtc, series (nested); CommandRequest with name, seriesId, seasonNumber
- [Go starr package - Radarr types](https://pkg.go.dev/golift.io/starr/radarr) - CommandRequest with name, movieIds as []int64
- [APScheduler 3.x user guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) - AsyncIOScheduler, interval trigger, add_job API
- [APScheduler PyPI](https://pypi.org/project/APScheduler/) - Version 3.11.2 (Dec 2025), stable; 4.0.0a6 still alpha
- [FastAPI lifespan docs](https://fastapi.tiangolo.com/advanced/events/) - @asynccontextmanager lifespan pattern

### Secondary (MEDIUM confidence)
- [Huntarr Radarr integration](https://deepwiki.com/plexguide/Huntarr.io/5.3-radarr-integration) - MoviesSearch JSON body `{"name": "MoviesSearch", "movieIds": [...]}`; verified against Go starr package
- [Sentry - Schedule tasks with FastAPI](https://sentry.io/answers/schedule-tasks-with-fastapi/) - APScheduler + FastAPI lifespan pattern
- [Sonarr/Sonarr GitHub issues](https://github.com/Sonarr/Sonarr/issues/4950) - sortKey defaults, airDateUtc handling

### Tertiary (LOW confidence)
- None -- all findings cross-verified with at least two sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - APScheduler 3.x is well-documented, stable, and the standard Python scheduler. Phase 1 infrastructure covers all other needs.
- Architecture: HIGH - Pattern is straightforward (fetch, filter, slice, search, persist). All building blocks exist from Phase 1. Similar tools (Huntarr) validate the approach.
- Pitfalls: HIGH - Pitfalls identified from Sonarr API quirks (null airDateUtc), *arr command format requirements (movieIds as array), and config backward compatibility are well-documented.

**Research date:** 2026-02-23
**Valid until:** 2026-03-23 (stable domain, no fast-moving dependencies)
