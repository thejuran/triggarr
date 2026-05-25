<!-- refreshed: 2026-05-25 -->
# Architecture

**Analysis Date:** 2026-05-25

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                      FastAPI Web Server (uvicorn)                         │
│         `triggarr/__main__.py` port 8484, stateless request handling      │
└────────────────┬───────────────────────────────────────────────┬─────────┘
                 │                                               │
    ┌────────────▼────────────┐                  ┌──────────────▼─────┐
    │   Web Routes Layer      │                  │  Authentication     │
    │  `triggarr/web/`        │                  │  `triggarr/auth.py` │
    ├────────────────────────┤                  │  Forms/Basic/API    │
    │ • Jinja2 templates      │                  │  D-11: Policy       │
    │ • HTmx form handlers    │                  │                     │
    │ • JSON API endpoints    │                  └─────────────────────┘
    │ • Settings dashboard    │
    │ • Config editor         │
    └────────────┬────────────┘
                 │
    ┌────────────▼────────────────────────────────────────────┐
    │         Middleware Stack (FIFO order, LIFO response)     │
    ├────────────────────────────────────────────────────────┤
    │ 1. SecurityHeadersMiddleware (response headers)          │
    │ 2. OriginCheckMiddleware (CSRF via Origin/Referer)      │
    │ 3. AuthMiddleware (deny-all + whitelist)                │
    │    `triggarr/web/middleware.py`                         │
    └────────────┬────────────────────────────────────────────┘
                 │
    ┌────────────▼──────────────────────┐
    │      Scheduler / Search Engine     │
    ├───────────────────────────────────┤
    │ APScheduler + asyncio.Lock        │
    │ `triggarr/search/scheduler.py`    │
    │                                   │
    │ Interval jobs per instance:       │
    │ • RadarrClient (search cycles)    │
    │ • SonarrClient (search cycles)    │
    │ • LidarrClient (search cycles)    │
    │ `triggarr/search/engine.py`       │
    │                                   │
    │ Tracking check (post-search)      │
    │ `triggarr/tracking.py`            │
    └────────┬──────────┬───────────────┘
             │          │
    ┌────────▼──┐   ┌───▼────────────┐
    │ Clients    │   │ Persistence    │
    └────────────┘   └────────────────┘
         │                │
    ┌────▼─────────────┐  │
    │ HTTP Clients:    │  │
    │ • RadarrClient   │  │
    │ • SonarrClient   │  │
    │ • LidarrClient   │  │
    │ `triggarr/       │  │
    │  clients/`       │  │
    │                  │  │
    │ Base: ArrClient  │  │
    │ • Pagination     │  │
    │ • Retry logic    │  │
    │ • Validation     │  │
    └────────┬─────────┘  │
             │             │
    ┌────────▼──────────┐  │
    │ External APIs:    │  │
    │ • Radarr REST API │  │
    │ • Sonarr REST API │  │
    │ • Lidarr REST API │  │
    └───────────────────┘  │
                            │
    ┌───────────────────────▼──────────────┐
    │     Persistence Layer                │
    ├───────────────────────────────────────┤
    │ Config:                               │
    │ • TOML parsing & validation           │
    │ • `triggarr/config.py`                │
    │ • Atomic write-then-rename            │
    │ • v2.2→v2.3 migration                │
    │                                       │
    │ State:                                │
    │ • JSON cursor/history tracking        │
    │ • `triggarr/state.py`                 │
    │ • Per-instance state dicts            │
    │                                       │
    │ Search History (SQLite):              │
    │ • `triggarr/db.py`                    │
    │ • Versioned migrations (WAL mode)     │
    │ • Tracking outcomes + grab events     │
    └───────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Entry Point | Load config, validate connections, create lifespan, start uvicorn | `triggarr/__main__.py` |
| Config Layer | TOML loading, generation, migration, atomic persistence | `triggarr/config.py` |
| Settings Model | Pydantic schema for [general], [auth], [radarr], [sonarr], [lidarr] | `triggarr/models/config.py` |
| Startup Orchestration | Logging setup, secret redaction, connection validation, banner | `triggarr/startup.py` |
| Scheduler | APScheduler lifespan integration, job creation, client lifecycle | `triggarr/search/scheduler.py` |
| Search Engine | Filtering, batching, dedup, cycle orchestration per app type | `triggarr/search/engine.py` |
| HTTP Clients | Async httpx wrappers for Radarr/Sonarr/Lidarr REST APIs | `triggarr/clients/base.py`, `radarr.py`, `sonarr.py`, `lidarr.py` |
| State Persistence | JSON-based cursor/history tracking with atomic writes | `triggarr/state.py` |
| Database | SQLite search history + grab event tracking with migrations | `triggarr/db.py` |
| Web Routes | FastAPI endpoints, template rendering, config editor, API responses | `triggarr/web/routes.py` |
| Middleware | Auth enforcement, CSRF, security headers, path whitelisting | `triggarr/web/middleware.py` |
| Authentication | Session signing, password hashing, API key validation | `triggarr/auth.py` |
| Logging | Loguru setup with secret redaction sink | `triggarr/logging.py` |
| Tracking | Post-search grab event correlation and outcome resolution | `triggarr/tracking.py` |
| Update Check | Background async check for new releases | `triggarr/update_check.py` |

## Pattern Overview

**Overall:** Async daemon with scheduled jobs + stateless web UI

**Key Characteristics:**
- **Async-first:** Everything uses `asyncio` and `aiofiles`/`aiosqlite` for non-blocking I/O
- **Single-threaded event loop:** APScheduler runs jobs via asyncio executor, not thread pool
- **Shared state via app.state:** Clients, settings, state, and DB exposed to routes without coupling
- **Atomic file writes:** All persistent changes (config, state, DB) use write-then-rename
- **Job-based concurrency:** Search cycles protected by `asyncio.Lock` to prevent overlapping runs
- **Multi-instance:** Each app type (Radarr/Sonarr/Lidarr) can have multiple named instances with independent schedules and cursors

## Layers

**Presentation Layer:**
- Purpose: Serve web UI via FastAPI, handle form submissions, return JSON responses
- Location: `triggarr/web/routes.py`, `triggarr/templates/`, `triggarr/static/`
- Contains: Route handlers, Jinja2 templates, htmx form fragments, Tailwind CSS
- Depends on: Models (config, arr), search engine, database, auth
- Used by: HTTP clients (browsers, mobile clients)

**Application Layer:**
- Purpose: Orchestrate search cycles, manage scheduler lifecycle, expose shared state
- Location: `triggarr/search/scheduler.py`, `triggarr/search/engine.py`, `triggarr/tracking.py`
- Contains: Job factories, cycle orchestrators, search history insertion
- Depends on: HTTP clients, database, state, settings
- Used by: Middleware, routes (manual search trigger)

**Domain / Business Logic Layer:**
- Purpose: Core algorithms for filtering, batching, dedup, tag resolution
- Location: `triggarr/search/engine.py` (pure functions)
- Contains: `filter_by_tag()`, `filter_monitored()`, `slice_batch()`, `cap_batch_sizes()`, `resolve_tag_id()`
- Depends on: Models
- Used by: Search cycles

**Data Access Layer:**
- Purpose: HTTP API communication, state/config persistence, database operations
- Location: `triggarr/clients/base.py` + subclasses, `triggarr/config.py`, `triggarr/state.py`, `triggarr/db.py`
- Contains: Async HTTP client wrapper, TOML parsing, JSON state I/O, SQLite queries
- Depends on: Models, pydantic validation, httpx/aiosqlite libraries
- Used by: Application layer, routes, startup

**Configuration & Model Layer:**
- Purpose: Define schema, validation rules, and defaults
- Location: `triggarr/models/config.py`, `triggarr/models/arr.py`
- Contains: Pydantic BaseModel/BaseSettings, SecretStr fields, validators
- Depends on: pydantic library
- Used by: All layers

**Middleware & Security Layer:**
- Purpose: Request/response gating, auth enforcement, CSRF prevention, header injection
- Location: `triggarr/web/middleware.py`, `triggarr/auth.py`, `triggarr/web/security.py`
- Contains: HTTPMiddleware subclasses, session/password/API key validation
- Depends on: Models, itsdangerous/bcrypt libraries
- Used by: FastAPI app

## Data Flow

### Primary Request Path (Web Dashboard View)

1. Browser GET `/` (`triggarr/web/routes.py:get_dashboard`) - render dashboard template
2. AuthMiddleware checks session cookie or redirects to `/login` (`triggarr/web/middleware.py:AuthMiddleware`)
3. Route reads `app.state.triggarr_state` (current cursor, stats) and `app.state.db` (recent searches)
4. Jinja2 renders `dashboard.html` with passed state (instance cards, search log)
5. Template includes htmx polling: `hx-get="/dashboard/card/{app}/{instance}"` every 15s
6. Browser makes polling requests → partial handler rebuilds card HTML with live stats
7. Response returned to browser

### Config Editor (Web Settings Form)

1. Browser POST `/settings/save` with form data (`triggarr/web/routes.py:post_settings_save`)
2. AuthMiddleware validates session (or redirects)
3. Route handler parses + validates form fields using Pydantic models
4. Settings atomically written to TOML via `_atomic_toml_write()` (`triggarr/config.py`)
5. Scheduler clients and state reloaded from updated config (hot-reload via `app.state.settings = new_settings`)
6. Jobs rescheduled if intervals changed
7. Redirect to `/settings` with success banner

### Automated Search Cycle (Scheduled Job)

1. APScheduler fires interval job for `{app}_{instance}_search` (e.g., `radarr_Default_search`)
2. Job closure (`make_search_job()`) reads current client, settings, state from `app.state` at execution time
3. Calls `run_radarr_cycle()` (or sonarr/lidarr variant) with client, state, settings
4. Cycle:
   a. Fetches wanted/missing queue via client API (`get_wanted_missing()`)
   b. Applies tag filters if configured (resolve tag ID → `filter_by_tag()`)
   c. Filters monitored items only (`filter_monitored()`)
   d. Slices batch starting at cursor with wrap-around detection (`slice_batch()`)
   e. Caps total batch size if hard_max configured (`cap_batch_sizes()`)
   f. Triggers search command via client POST (`search_movies()`)
   g. Logs search entry to SQLite (`insert_search_entry()`)
   h. Updates state cursor and stats
5. State saved atomically to JSON (`save_state()`)
6. Tracking check runs (post-search grab event correlation)
7. Results logged with redacted values

### State Persistence Flow

1. State loaded from JSON at startup (`load_state()`) or defaults created
2. Per-instance cursors tracked: `radarr.Default.missing_cursor = 5`, etc.
3. After each search cycle, state updated in memory and persisted via `save_state()` with write-then-rename
4. On container restart, state reloaded → cursors resume from last known position
5. v2.2 flat format auto-migrated to v2.3 nested format on load

**State Management:**
- In-memory: `app.state.triggarr_state` dict (loaded once, updated in-place)
- Disk: `/config/state.json` (atomic write after each cycle)
- Database: `/config/triggarr.db` (SQLite WAL mode, async aiosqlite)

## Key Abstractions

**ArrClient (Base HTTP Client):**
- Purpose: Shared async httpx wrapper for Radarr/Sonarr/Lidarr with retry + pagination
- Examples: `RadarrClient`, `SonarrClient`, `LidarrClient` (`triggarr/clients/`)
- Pattern: Abstract base class with abstract methods + concrete app-specific subclasses
- Key methods: `_request_with_retry()`, `get()`, `post()`, `get_paginated()`, `validate_connection()`

**Settings (Pydantic BaseSettings):**
- Purpose: Type-safe config schema with validation and defaults
- Examples: `GeneralConfig`, `AuthConfig`, `InstanceConfig` (`triggarr/models/config.py`)
- Pattern: Nested Pydantic models with model validators for cross-field rules
- Key methods: `get_enabled_instances()`, `@model_validator` decorators

**Job Factory (make_search_job):**
- Purpose: Create closures that read from `app.state` at execution time (hot-reload safe)
- Pattern: Higher-order function returning async callable
- Key: Avoids capturing variables; reads clients/settings/state fresh on each job execution

**Atomic File I/O:**
- Purpose: Prevent corruption from mid-write crashes
- Pattern: Write to temp file in same directory, fsync, rename atomically
- Examples: `_atomic_toml_write()` (config.py), `save_state()` (state.py)

## Entry Points

**CLI Entry Point:**
- Location: `triggarr/__main__.py:main()`
- Triggers: `python -m triggarr` or Docker `entrypoint.sh`
- Responsibilities: Catch KeyboardInterrupt, call `_run()` async entry point

**Async Entry Point:**
- Location: `triggarr/__main__.py:_run()`
- Triggers: Called by `main()`
- Responsibilities: 
  1. Call `startup()` to load config, validate connections, setup logging
  2. Load root_path and trusted proxy IPs from env
  3. Create FastAPI app with lifespan context manager
  4. Mount static files and include router
  5. Create uvicorn.Server and serve

**Startup Sequence:**
- Location: `triggarr/startup.py:startup()`
- Triggers: Called by `_run()` before server start
- Responsibilities:
  1. Ensure config exists (generate default if missing)
  2. Collect secrets for log redaction
  3. Setup loguru with redaction filter
  4. Print startup banner
  5. Check for localhost URL mistakes
  6. Validate connections to all enabled *arr instances
  7. Return Settings object

**Lifespan Manager:**
- Location: `triggarr/search/scheduler.py:create_lifespan()`
- Triggers: FastAPI calls on startup/shutdown
- Responsibilities:
  1. **Startup:** Load state, init database, create long-lived clients, schedule jobs, start APScheduler
  2. **Shutdown:** Cancel scheduler, close all clients, close database connection

**Web Routes:**
- Location: `triggarr/web/routes.py`
- Triggers: HTTP requests (GET/POST/PUT/DELETE)
- Key routes:
  - `GET /` → dashboard (home page with instance cards)
  - `GET /settings` → settings form
  - `POST /settings/save` → update config + hot-reload
  - `POST /search-now/{app}/{instance}` → trigger manual search
  - `GET /health` → simple health check
  - `GET /history` → search history view
  - `POST /login`, `GET /login` → auth entry points

## Architectural Constraints

- **Threading:** Single-threaded event loop (asyncio). APScheduler runs jobs via executor (no thread pool). Search cycles protected by `asyncio.Lock` to prevent overlapping runs on same instance.
- **Global state:** `app.state.*` object exposes clients, settings, state dict, database connection, scheduler. Routes access via `request.app.state` without injection.
- **Circular imports:** Avoided by lazy imports in route handlers (e.g., `from triggarr.startup import startup` inside `_run()`). Settings and state modules do not import from web/routes.
- **Database access:** Single `aiosqlite.Connection` object shared across all routes and scheduler. No connection pooling (single connection handles concurrent tasks via WAL mode).
- **Config hot-reload:** Config updated on disk + in-memory `app.state.settings`. Jobs read from `app.state` at execution time → no restart required.
- **Secrets in memory:** API keys held as `SecretStr` and called `.get_secret_value()` only at client init and log setup. Never logged or exposed to templates.

## Anti-Patterns

### Hardcoded API Keys in Logs

**What happens:** Early code passed raw API keys to logger calls, risking exposure in log files.
**Why it's wrong:** Secrets leaked to disk logs become permanent audit trail vulnerabilities.
**Do this instead:** Use `SecretStr` from pydantic, call `.get_secret_value()` only once at startup in `collect_secrets()` (`triggarr/startup.py`), pass secret list to loguru redaction filter. Never log the key itself. Example: `logger.info("Validated {app}", app="Radarr")` not `logger.info("Using key: {key}", key=api_key)`.

### Blocking File I/O in Async Routes

**What happens:** Using `open()` or `json.dump()` in route handlers would block the event loop.
**Why it's wrong:** Blocks all other requests/scheduler jobs during slow disk I/O.
**Do this instead:** Use `aiofiles` for file reads/writes, `json.loads()` with `run_in_executor()` for CPU-bound parsing. Example in `triggarr/web/routes.py`: config writes use `_atomic_toml_write()` wrapped in executor. State saves use `run_in_executor(None, save_state, ...)`.

### Database Writes During Config Reload

**What happens:** Config editor re-reads settings but doesn't wait for pending search jobs to finish.
**Why it's wrong:** Job reads stale settings mid-execution, writes corrupt state or uses wrong cursors.
**Do this instead:** Use `asyncio.Lock` to serialize access (`app.state.search_lock`). Config reload requests acquire lock before updating `app.state.settings`. Jobs acquire lock before reading settings/state. See `triggarr/search/scheduler.py:make_search_job()` where entire cycle runs under lock.

### Manual Search Bypass of Rate Limiting

**What happens:** User clicks "search now" repeatedly, hammering *arr API.
**Why it's wrong:** No protection against user error or automated abuse.
**Do this instead:** Rate limit via `SEARCH_RATE_LIMIT_SECONDS = 10` checked against `app.state.last_search_time[key]`. Reject requests within window with `429 Too Many Requests`. See `triggarr/web/routes.py:post_search_now()`.

## Error Handling

**Strategy:** Fail-open for connection errors (log warning, skip cycle, retry next interval), fail-closed for config errors (exit on startup).

**Patterns:**
- **HTTPError:** Caught by `_sanitize_exc()` → safe summary (e.g., "HTTP 429") stored in DB, never full response
- **ValidationError:** Caught as pydantic.ValidationError → error count stored, request retried next cycle
- **Config errors:** Caught by Pydantic validators → logged + process exits with code 1 before binding port
- **Database errors:** aiosqlite.Error caught in cycle and tracking → logged as warning, state persisted via JSON fallback
- **Unhandled in job:** Wrapped in try/except at job level → logged as error, state not corrupted, next cycle attempts again

## Cross-Cutting Concerns

**Logging:** Loguru with structured `{field}` syntax + secret redaction sink. Configured via `triggarr/logging.py:setup_logging()`. Secrets collected once in `startup.py` and passed to redaction filter.

**Validation:** Pydantic models enforce schema + business rules:
- Instance count capped at 5 per app type
- At least one search count positive when enabled
- API keys non-empty when instance enabled
- TOML parseable and structurally valid

**Authentication:** Three-tier approach:
1. Session cookie (browser, persistent, checked on every request)
2. X-Api-Key header (API clients, simple header check)
3. Basic auth (fallback for external integrations)
See `triggarr/web/middleware.py:AuthMiddleware` dispatch logic.

---

*Architecture analysis: 2026-05-25*
