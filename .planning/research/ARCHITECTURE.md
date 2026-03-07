# Architecture Research

**Domain:** *arr automation tool — search scheduling daemon with minimal web UI
**Researched:** 2026-02-23
**Confidence:** HIGH (API details verified via official docs/pyarr source; patterns verified via Huntarr analysis + FastAPI/APScheduler community)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Docker Container                            │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    FastAPI Application                        │   │
│  │                                                               │   │
│  │  ┌────────────────┐          ┌──────────────────────────┐    │   │
│  │  │  Web UI Layer  │          │    API Router Layer       │    │   │
│  │  │  (htmx/Jinja2) │          │  (status/config/history) │    │   │
│  │  └───────┬────────┘          └────────────┬─────────────┘    │   │
│  │          │  reads state                   │  reads/writes    │   │
│  │          └───────────────┬────────────────┘                  │   │
│  │                          ▼                                    │   │
│  │              ┌───────────────────────┐                       │   │
│  │              │    State Store        │                       │   │
│  │              │  (SQLite or JSON)     │                       │   │
│  │              │  - round-robin pos    │                       │   │
│  │              │  - search history     │                       │   │
│  │              │  - last/next run      │                       │   │
│  │              └───────────┬───────────┘                       │   │
│  │                          │  reads/writes                     │   │
│  │              ┌───────────▼───────────┐                       │   │
│  │              │   Scheduler Engine    │                       │   │
│  │              │   (APScheduler /      │                       │   │
│  │              │  asyncio loop)        │                       │   │
│  │              └───────────┬───────────┘                       │   │
│  │                          │  triggers                         │   │
│  │            ┌─────────────┴──────────────┐                   │   │
│  │            ▼                            ▼                   │   │
│  │  ┌─────────────────┐         ┌─────────────────┐           │   │
│  │  │  Radarr Client  │         │  Sonarr Client  │           │   │
│  │  │  (search logic) │         │  (search logic) │           │   │
│  │  └────────┬────────┘         └────────┬────────┘           │   │
│  │           │                           │                     │   │
│  └───────────┼───────────────────────────┼─────────────────────┘   │
│              │  HTTP (httpx)             │  HTTP (httpx)            │
└──────────────┼───────────────────────────┼──────────────────────────┘
               ▼                           ▼
      ┌─────────────────┐        ┌─────────────────┐
      │  Radarr Instance│        │  Sonarr Instance│
      │  :7878           │        │  :8989           │
      └─────────────────┘        └─────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Boundary |
|-----------|----------------|----------|
| Web UI Layer | Render status page, history log, queue position, config form — htmx fragments, no JS state | Read-only to state store; config writes via form POST |
| API Router | Serve htmx partial HTML responses for UI polling, handle config form submission | Never expose API keys in any response |
| State Store | Persist round-robin position per app, search history, last/next run time, item counts | SQLite file on Docker volume; single writer (scheduler) |
| Scheduler Engine | Run search cycles on configured intervals; update state after each cycle | Owns the search loop; other components read state passively |
| Radarr Client | Fetch wanted/cutoff-unmet lists, trigger MoviesSearch commands | Calls Radarr API only; API key lives here, never leaves |
| Sonarr Client | Fetch missing/cutoff-unmet lists, deduplicate by season, trigger SeasonSearch commands | Calls Sonarr API only; API key lives here, never leaves |
| Config Layer | Load/save YAML or TOML config; provide typed settings to all components | Config file on Docker volume; API keys read-only at startup |

## Recommended Project Structure

```
triggarr/
├── app/
│   ├── main.py               # FastAPI app factory, lifespan, scheduler startup
│   ├── config.py             # Settings model (Pydantic), load/save config file
│   ├── scheduler.py          # APScheduler setup, job registration, interval management
│   ├── state.py              # SQLite state: round-robin positions, history, run times
│   ├── clients/
│   │   ├── base.py           # Shared httpx client, auth header, error handling
│   │   ├── radarr.py         # Radarr API calls: wanted, cutoff, search command
│   │   └── sonarr.py         # Sonarr API calls: wanted, cutoff, SeasonSearch
│   ├── search/
│   │   ├── radarr_cycle.py   # Radarr round-robin logic: fetch list, slice, trigger search
│   │   └── sonarr_cycle.py   # Sonarr round-robin logic: fetch list, dedupe seasons, trigger
│   ├── routers/
│   │   ├── ui.py             # Full-page and htmx partial HTML routes (status, history)
│   │   └── config.py         # Config form GET/POST routes
│   └── templates/
│       ├── base.html         # Layout, htmx CDN, Tailwind CDN
│       ├── index.html        # Status dashboard (last run, next run, counts, queue pos)
│       ├── history.html      # Recent search log table
│       ├── config.html       # Config editor form
│       └── partials/
│           ├── status_card.html    # htmx-polled status fragment
│           ├── history_rows.html   # htmx-polled log rows
│           └── queue_position.html # htmx-polled round-robin position
├── data/                     # Docker volume mount point
│   ├── config.yaml           # User config: URLs, API keys, intervals, per-app limits
│   └── state.db              # SQLite state file
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

### Structure Rationale

- **app/clients/:** Isolates all *arr API knowledge. Radarr and Sonarr clients are separate because their APIs differ (especially season-level search). Base client holds httpx session and auth header injection.
- **app/search/:** Contains the round-robin cycle logic separately from the API client. This separation means cycle logic can be tested without live *arr instances.
- **app/routers/:** UI routes and config routes are distinct. UI routes never write state; config routes never expose API keys in responses.
- **data/:** Single Docker volume for both config and state. Keeps user data outside the container image.

## Architectural Patterns

### Pattern 1: Single-Process Scheduler with In-Process Background Loop

**What:** Run the APScheduler `AsyncIOScheduler` inside the same FastAPI process using the lifespan context manager. The scheduler fires the Radarr and Sonarr search cycles as async jobs at their configured intervals.

**When to use:** Always, for this project. A single Docker container with one process is the right model. There is no multi-worker gunicorn deployment, so the double-scheduler problem (APScheduler fires once per gunicorn worker) does not apply.

**Trade-offs:** Simple. No Redis, no Celery, no separate worker process. State is in SQLite, which is safe because there is exactly one writer (the scheduler) and many readers (the web UI).

**Example:**
```python
# app/main.py
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from app.scheduler import register_jobs

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    register_jobs(scheduler)
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
```

### Pattern 2: Round-Robin Position Stored in SQLite, Not in Memory

**What:** The current search position for each app (Radarr, Sonarr missing, Sonarr cutoff) is persisted in SQLite as a single integer offset per app-queue combination. On each cycle, fetch the full list from the *arr API, slice from the stored offset, advance the offset, and save it back.

**When to use:** Always. Storing position in memory means a container restart loses the round-robin position and starts from item 0 again. SQLite makes restarts transparent.

**Trade-offs:** Adds a tiny SQLite write per cycle. Worth it — the alternative is silent position loss on restart, which defeats the purpose of round-robin (ensuring every item eventually gets searched).

**Example:**
```python
# app/state.py
def get_position(app: str, queue: str) -> int:
    """Return current round-robin offset for this app+queue."""
    ...

def set_position(app: str, queue: str, position: int) -> None:
    """Persist the new offset after a cycle completes."""
    ...

# app/search/radarr_cycle.py
async def run_radarr_missing_cycle(settings, state, client):
    items = await client.get_wanted_missing()   # full list
    total = len(items)
    if total == 0:
        return
    pos = state.get_position("radarr", "missing")
    batch = items[pos : pos + settings.radarr.items_per_cycle]
    # Wrap around if needed
    if len(batch) < settings.radarr.items_per_cycle and pos > 0:
        batch += items[: settings.radarr.items_per_cycle - len(batch)]
    movie_ids = [m["id"] for m in batch]
    await client.search_movies(movie_ids)
    new_pos = (pos + settings.radarr.items_per_cycle) % total
    state.set_position("radarr", "missing", new_pos)
    state.add_history_entry("radarr", "missing", movie_ids)
```

### Pattern 3: Sonarr Season Deduplication Before Search

**What:** The Sonarr `/api/v3/wanted/missing` endpoint returns individual episode records. A show with 5 missing episodes across 2 seasons would return 5 records. Before triggering searches, deduplicate to unique (seriesId, seasonNumber) pairs so each season is searched only once per cycle.

**When to use:** Always for Sonarr. Searching the same season 5 times for 5 missing episodes hammers the indexer unnecessarily and counts against API rate limits.

**Trade-offs:** Means the "items per cycle" setting for Sonarr controls seasons searched, not episodes. This needs to be documented clearly in the UI.

**Example:**
```python
# app/search/sonarr_cycle.py
async def run_sonarr_missing_cycle(settings, state, client):
    episodes = await client.get_wanted_missing()
    # Deduplicate to unique seasons
    seen = set()
    seasons = []
    for ep in episodes:
        key = (ep["seriesId"], ep["seasonNumber"])
        if key not in seen:
            seen.add(key)
            seasons.append({"seriesId": ep["seriesId"], "seasonNumber": ep["seasonNumber"]})

    pos = state.get_position("sonarr", "missing")
    batch = seasons[pos : pos + settings.sonarr.items_per_cycle]
    for season in batch:
        await client.season_search(season["seriesId"], season["seasonNumber"])
    new_pos = (pos + settings.sonarr.items_per_cycle) % max(len(seasons), 1)
    state.set_position("sonarr", "missing", new_pos)
```

### Pattern 4: API Key Isolation via Config-Only Read at Startup

**What:** API keys are loaded from config file into a Pydantic Settings object at startup. They are stored only in the in-process settings object. No route, template, or API response ever serializes or echoes the settings object back to the client.

**When to use:** Always, without exception. This is the core security invariant that justifies building Triggarr instead of using Huntarr.

**Trade-offs:** Config file must be readable by the container user. The config UI form must accept new values and write them back without exposing the current values in an HTML `value=""` attribute. Use placeholder text ("configured" or "••••••••") instead.

## Data Flow

### Search Cycle Flow (Radarr example)

```
APScheduler interval fires
    ↓
radarr_cycle.run() called
    ↓
RarrClient.get_wanted_missing()
    → GET /api/v3/wanted/missing?page=1&pageSize=500
    ← [{id, title, ...}, ...]
    ↓
RarrClient.get_cutoff_unmet()  (separate queue, separate cycle)
    → GET /api/v3/wanted/cutoff?page=1&pageSize=500
    ← [{id, title, ...}, ...]
    ↓
State.get_position("radarr", "missing") → offset int
    ↓
Slice items[offset : offset + n]
    ↓
RarrClient.search_movies([id1, id2, ...])
    → POST /api/v3/command {"name": "MoviesSearch", "movieIds": [...]}
    ← {"id": command_id, "status": "started"}
    ↓
State.set_position("radarr", "missing", new_offset)
State.add_history("radarr", "missing", searched_ids, timestamp)
State.set_last_run("radarr", now)
State.set_next_run("radarr", now + interval)
```

### UI Status Poll Flow (htmx)

```
Browser loads /  (full page render, Jinja2)
    ↓
htmx hx-get="/partials/status" hx-trigger="every 30s"
    → GET /partials/status
    ← HTML fragment: last run, next run, queue position, item counts
    ↓ (swapped into DOM by htmx)
No JavaScript state management required
```

### Config Save Flow

```
User edits config form at /config
    ↓
Form POST to /config
    ↓
FastAPI route validates input (Pydantic)
    ↓
Write config.yaml to disk (API keys included, but only written, not returned)
    ↓
Reload settings object in-process
    ↓
Reschedule APScheduler jobs with new intervals
    ↓
Redirect to / (PRG pattern — prevents form resubmission on refresh)
```

### Key Data Flows

1. **Scheduler → Clients → *arr APIs:** One-way during search cycle. Scheduler is the only component that writes to the *arr APIs. No *arr writes come from the UI layer.
2. **Clients → State:** Scheduler writes search results to SQLite after each cycle. State is the single source of truth for what the UI displays.
3. **UI → State (read-only):** All UI routes query SQLite for display data. No UI route reads from live *arr API — avoids latency and avoids exposing API key material.
4. **Config form → Config file → Settings object → Scheduler:** Config changes flow from form → disk → in-memory settings → scheduler rescheduling. API keys flow from disk → memory only; they never flow back to the browser.

## Integration Points

### External Services

| Service | Integration Pattern | Key Endpoints | Notes |
|---------|---------------------|---------------|-------|
| Radarr | httpx AsyncClient, X-Api-Key header | GET /api/v3/wanted/missing, GET /api/v3/wanted/cutoff, POST /api/v3/command | `MoviesSearch` command takes `movieIds: list[int]`; API key in header, never query param |
| Sonarr | httpx AsyncClient, X-Api-Key header | GET /api/v3/wanted/missing, GET /api/v3/wanted/cutoff, POST /api/v3/command | `SeasonSearch` command takes `seriesId: int, seasonNumber: int`; deduplicate episodes to seasons first |

### Radarr API Commands (verified)

```python
# Fetch wanted missing (added in Radarr v5+, merged PR #10015 May 2024)
GET /api/v3/wanted/missing?page=1&pageSize=500&monitored=true

# Fetch cutoff unmet
GET /api/v3/wanted/cutoff?page=1&pageSize=500&monitored=true

# Trigger search for specific movies
POST /api/v3/command
{"name": "MoviesSearch", "movieIds": [123, 456, 789]}
```

### Sonarr API Commands (verified)

```python
# Fetch missing episodes (returns episode-level records)
GET /api/v3/wanted/missing?page=1&pageSize=500

# Fetch cutoff unmet episodes
GET /api/v3/wanted/cutoff?page=1&pageSize=500

# Trigger season search (deduplicate episodes to seasons first)
POST /api/v3/command
{"name": "SeasonSearch", "seriesId": 42, "seasonNumber": 3}
```

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Scheduler ↔ Clients | Direct async function call | Scheduler owns the clients; calls are in-process |
| Clients ↔ *arr APIs | httpx async HTTP | One persistent client per app; connection pooling via httpx.AsyncClient |
| Scheduler ↔ State | SQLite (direct, synchronous) | Scheduler is the only writer; use `aiosqlite` or `sqlite3` with thread safety |
| UI Routes ↔ State | SQLite (read-only queries) | Multiple concurrent readers safe in SQLite WAL mode |
| Config Form ↔ Config File | YAML file read/write | Lock file or atomic write to avoid partial config on crash |

## Suggested Build Order

The dependency graph dictates a clear bottom-up build order:

```
1. Config Layer      (everything reads config)
       ↓
2. State Store       (scheduler writes; UI reads)
       ↓
3. API Clients       (Radarr, Sonarr — can be tested against live instances)
       ↓
4. Search Cycle Logic (uses clients + state; testable with mock clients)
       ↓
5. Scheduler Engine  (wires cycle logic to timing; uses config for intervals)
       ↓
6. FastAPI App + Routers (reads state; no writes except config)
       ↓
7. Web UI Templates  (reads from routes; htmx polling for live updates)
       ↓
8. Docker + Compose  (packages everything; volume mounts for data/)
```

**Rationale for this order:**
- Config and State must exist before any other component can function.
- API clients should be buildable and manually testable before the scheduler wires them to a timer.
- Search cycle logic is the core business logic — test it in isolation before attaching timing.
- The web UI is pure read-only display, so it can be built last against real state data.
- Docker packaging is the final step because it wraps a working application, not a development concern.

## Anti-Patterns

### Anti-Pattern 1: Exposing API Keys in Any HTTP Response

**What people do:** Return the full settings object from a `/api/config` endpoint, or pre-fill the config form `<input value="{{ settings.radarr_api_key }}">`.

**Why it's wrong:** This is exactly what Huntarr did — API keys were returned from unauthenticated API endpoints, visible to anyone on the network. Triggarr exists specifically because of this failure.

**Do this instead:** Config form shows placeholder text ("configured" or masked "••••••••"). Only write new key to file if the form field is non-empty. `/api/config` endpoint returns config without the `api_key` fields.

### Anti-Pattern 2: Fetching Fresh Lists from *arr on Every UI Request

**What people do:** The status page makes a live call to Radarr/Sonarr to show current wanted counts, queue position, etc. on every page load.

**Why it's wrong:** Adds latency to UI (every page load waits for *arr API). If *arr is down, the UI is broken. Exposes API call pattern to UI timing.

**Do this instead:** UI reads from the SQLite state store, which the scheduler updates after each cycle. The UI shows "last known" counts with a timestamp. Counts may be minutes old, which is fine for a status dashboard.

### Anti-Pattern 3: Triggering MissingMoviesSearch or missingEpisodeSearch Commands

**What people do:** Use the bulk "search all missing" commands (`MissingMoviesSearch`, `missingEpisodeSearch`) because they seem convenient.

**Why it's wrong:** These commands search every missing item in a single call, ignoring the configurable batch size and interval design. They hammer indexers, can get the user banned, and defeat the entire purpose of controlled round-robin searching.

**Do this instead:** Always use `MoviesSearch` with a specific `movieIds` list for Radarr, and `SeasonSearch` with specific `seriesId`+`seasonNumber` for Sonarr.

### Anti-Pattern 4: Storing Round-Robin Position in Memory Only

**What people do:** Keep a Python integer counter in a module-level variable or class attribute.

**Why it's wrong:** Container restarts (routine in homelab environments) silently reset position to 0. Every restart means the first N items always get searched, and items near the end of the list may never get searched if cycles happen to restart frequently.

**Do this instead:** Persist position in SQLite after every cycle. The overhead is negligible (one write per cycle, which happens every N minutes).

### Anti-Pattern 5: Per-Episode Search for Sonarr

**What people do:** Fetch missing episode list, iterate, fire one `EpisodeSearch` per episode ID.

**Why it's wrong:** One season with 10 missing episodes fires 10 API search commands. This hammers indexers and triggers rate limiting. Sonarr's season pack search is the correct unit for batch searching.

**Do this instead:** Deduplicate episode records to unique (seriesId, seasonNumber) pairs, then fire one `SeasonSearch` per unique season. Season packs are typically available as single releases anyway.

## Scaling Considerations

This tool is explicitly single-instance, single-user, local network. Scaling is not a concern. However:

| Concern | At current scale (1 Radarr + 1 Sonarr) | If scope expanded |
|---------|------------------------------------------|-------------------|
| *arr API rate limits | Not an issue with configured intervals (minutes) | Add sleep between individual commands in a batch |
| SQLite concurrency | WAL mode handles 1 writer + N readers trivially | Irrelevant — still 1 writer |
| Container restarts | Position survives via SQLite | Already handled |
| Config changes | Scheduler reschedules in-process | Already handled |

## Sources

- Radarr API /wanted/missing endpoint: [GitHub Issue #7704](https://github.com/Radarr/Radarr/issues/7704) — confirmed added May 2024 via PR #10015 (MEDIUM confidence — GitHub issue, verified closed/merged)
- Radarr MoviesSearch command body: [GitHub Issue #3315](https://github.com/Radarr/Radarr/issues/3315), [Huntarr-Radarr api.py](https://github.com/plexguide/Huntarr-Radarr/blob/main/api.py) (MEDIUM confidence — community-verified examples)
- Sonarr SeasonSearch command: [Sonarr Wiki Command](https://github.com/Sonarr/Sonarr/wiki/Command), [pyarr source](https://docs.totaldebug.uk/pyarr/_modules/pyarr/sonarr.html) (MEDIUM confidence — wiki + library source)
- Huntarr architecture analysis: [DeepWiki — System Architecture](https://deepwiki.com/plexguide/Huntarr.io/2-system-architecture), [Media Processing](https://deepwiki.com/plexguide/Huntarr.io/5-media-processing) (MEDIUM confidence — third-party analysis of open-source code)
- APScheduler + FastAPI lifespan: [APScheduler PyPI](https://pypi.org/project/APScheduler/), [BetterStack APScheduler guide](https://betterstack.com/community/guides/scaling-python/apscheduler-scheduled-tasks/) (HIGH confidence — official PyPI + verified tutorial)
- httpx async client: [httpx official docs](https://www.python-httpx.org/async/) (HIGH confidence — official docs)

---
*Architecture research for: Triggarr — Radarr/Sonarr search automation daemon*
*Researched: 2026-02-23*
