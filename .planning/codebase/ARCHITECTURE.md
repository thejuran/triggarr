<!-- refreshed: 2026-06-01 -->
# Architecture

**Analysis Date:** 2026-06-01

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           HTTP Server (Uvicorn)                              │
│                         Entry: triggarr/__main__.py                          │
├──────────────────────────────┬──────────────────────────────────────────────┤
│   Middleware Stack           │          FastAPI Routes & UI                  │
│  (Auth, CSRF, Security)      │  `triggarr/web/routes.py`                    │
│  `triggarr/web/middleware.py`│  (Dashboard, Settings, Search Trigger)       │
└──────────────┬───────────────┴──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FastAPI Lifespan Context Manager                          │
│           `triggarr/search/scheduler.py::create_lifespan()`                 │
│     Manages: Scheduler startup, client init, app.state, shutdown drain      │
├──────────────────────────────┬──────────────────────────────────────────────┤
│   APScheduler (asyncio)      │   HTTP Clients (long-lived)                  │
│   Runs interval jobs for:    │   For each enabled *arr instance:            │
│   - radarr_*_search          │   - RadarrClient                             │
│   - sonarr_*_search          │   - SonarrClient                             │
│   - lidarr_*_search          │   - LidarrClient                             │
│   - update_check             │   `triggarr/clients/base.py`                 │
└──────────┬───────────────────┴──────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Search Execution Layer                                    │
│              Per-job closure: `make_search_job()` factory                    │
│   Job closure includes:                                                      │
│   - Search cycle orchestration (`run_radarr_cycle`, etc.)                   │
│   - State mutation (cursor advance, connected flag)                         │
│   - Failure escalation (consecutive-failure tracking)                       │
│   - State persistence (atomic JSON + atomic SQLite writes)                  │
│   - Tracking check (resolve pending search outcomes)                        │
│   - Tag cache lookup (RES-03: TTL-based per-instance)                       │
└──────────────┬──────────────────────────────────────────────────────────────┘
               │
               ├──────────────────────────────────────────────────────────────┐
               │                                                              │
               ▼                                                              ▼
     ┌──────────────────────┐                              ┌──────────────────┐
     │ Search Engine Cycles │                              │  Persistence     │
     │ (engine.py)          │                              │  (State + DB)    │
     │ - Filter monitored   │                              │                  │
     │ - Resolve tags       │◄──────────────────────────────│ Read/Write       │
     │ - Slice batch        │                              │ `state.py`       │
     │ - Deduplicate        │                              │ `db.py`          │
     │ - Query API          │                              │ `config.py`      │
     │ - Trigger search     │                              │                  │
     │ - Record result      │                              │ Atomic writes:   │
     │ - Update state       │                              │ - TOML config    │
     └──────────────────────┘                              │ - JSON state     │
                                                           │ - SQLite history │
                                                           └──────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Entry Point | Async app lifecycle, uvicorn config, middleware stack | `triggarr/__main__.py` |
| Config Loading | TOML parsing, validation, v2.2→v2.3 migration | `triggarr/config.py` |
| Pydantic Models | Settings, instance config, app/auth validation | `triggarr/models/config.py` |
| State Persistence | JSON cursors/timing, atomic write-then-rename | `triggarr/state.py` |
| Startup Sequence | Config ensure, logging setup, connection validation, banner | `triggarr/startup.py` |
| Scheduler Lifespan | APScheduler setup, client creation, job scheduling, graceful shutdown | `triggarr/search/scheduler.py` |
| Search Job Factory | Closure that reads app.state at runtime, encapsulates cycle + failure escalation | `triggarr/search/scheduler.py::make_search_job()` |
| Search Engine | Filter logic, batch slicing, dedup, API orchestration, state mutation | `triggarr/search/engine.py` |
| Radarr Client | Paginated fetch, tag resolution, wanted/missing/cutoff endpoints | `triggarr/clients/radarr.py` |
| Sonarr Client | Paginated fetch, episode dedup to seasons, API v3 detection | `triggarr/clients/sonarr.py` |
| Lidarr Client | Paginated fetch, artist/album hierarchy | `triggarr/clients/lidarr.py` |
| Base Client | Async httpx wrapper, retry logic, response parsing, pagination | `triggarr/clients/base.py` |
| Database | SQLite search history, schema versioning, lifetime stats | `triggarr/db.py` |
| Web Routes | Dashboard, settings CRUD, search trigger, htmx partials | `triggarr/web/routes.py` |
| Middleware | Security headers + CSP nonce, CSRF (Origin/Referer check), auth gate | `triggarr/web/middleware.py` |
| Auth | Session + Basic + API-key + External modes, password hashing | `triggarr/auth.py` |
| Logging | Loguru setup with secret redaction, custom log buffer | `triggarr/logging.py` |
| Tracking | Correlate pending searches with history grab events | `triggarr/tracking.py` |

## Pattern Overview

**Overall:** Event-driven daemon with HTTP UI management layer and async background scheduler.

**Key Characteristics:**
- **Lifespan-driven**: FastAPI `lifespan=` context manager owns scheduler and client lifecycle
- **Job closure pattern**: Each scheduled job reads app.state at execution time (enables hot-reload without restart)
- **Atomic persistence**: All state writes (JSON, TOML, SQLite) are atomic via write-then-rename (file) or transaction + commit
- **Async throughout**: asyncio event loop, httpx async clients, aiosqlite for DB
- **Narrow exception handling**: Cycle catch tuple is explicitly narrow (`httpx.HTTPError`, `pydantic.ValidationError`, `aiosqlite.Error`) to surface code bugs to the scheduler's EVENT_JOB_ERROR listener
- **Per-job failure tracking**: Consecutive-failure counter per scheduled job instance; threshold-based escalation from WARNING to ERROR
- **Graceful shutdown drain**: Configurable timeout (`TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT`, default 60s) that holds the lock and logs which job is stuck

## Layers

**HTTP Server:**
- Purpose: Serve web UI (dashboard, settings editor) and manage configuration
- Location: `triggarr/__main__.py`, `triggarr/web/routes.py`
- Contains: FastAPI app, uvicorn config, middleware stack, route handlers, Jinja2 templates
- Depends on: Settings (config), app.state (scheduler reference), auth module
- Used by: Web browsers, API clients (X-Api-Key or Basic auth), htmx polling

**Middleware & Security:**
- Purpose: Gate requests with auth checks, apply security headers, validate CSRF
- Location: `triggarr/web/middleware.py`, `triggarr/auth.py`
- Contains: AuthMiddleware (session/basic/API-key validation), OriginCheckMiddleware (CSRF), SecurityHeadersMiddleware (CSP nonce + headers)
- Depends on: Config (auth settings), request headers
- Used by: All HTTP handlers

**Scheduler & Job Orchestration:**
- Purpose: Periodically trigger search cycles on a fixed interval per instance
- Location: `triggarr/search/scheduler.py`, `triggarr/search/engine.py`
- Contains: APScheduler integration, job factory, cycle functions (run_radarr_cycle, etc.), batch slicing, filtering
- Depends on: Settings, state, clients, DB, app.state
- Used by: FastAPI lifespan startup/shutdown, failure escalation system

**Data Access:**
- Purpose: Persistent storage for configuration, state cursors, search history
- Location: `triggarr/config.py`, `triggarr/state.py`, `triggarr/db.py`
- Contains: TOML parsing + validation, JSON state file I/O, SQLite schema + migrations, atomic write patterns
- Depends on: Pydantic models, pathlib
- Used by: Startup, scheduler jobs, settings editor

**API Clients:**
- Purpose: Communicate with Radarr/Sonarr/Lidarr instances
- Location: `triggarr/clients/base.py`, `triggarr/clients/radarr.py`, `triggarr/clients/sonarr.py`, `triggarr/clients/lidarr.py`
- Contains: Async httpx wrappers, retry logic, pagination, tag fetching, history correlation
- Depends on: httpx, Pydantic models
- Used by: Search cycles, search-now endpoint, tag autocomplete, connection validation

## Data Flow

### Primary Request Path: Scheduled Search Cycle

1. **Scheduler triggers job** (`triggarr/search/scheduler.py::make_search_job()` returned closure, registered at lifespan startup)
   - Job reads app.state.{app_name}_clients and app.state.settings at execution time
   - Records job_id and start time in app.state.search_lock_holder for graceful shutdown tracking

2. **Acquire search_lock** (`asyncio.Lock`, enforces one search cycle at a time)
   - Serializes scheduled cycles and config-save operations (SAFETY-05)

3. **Resolve tag cache** (RES-03: TTL-based, 1-hour default)
   - Read or fetch tags, store in app.state.tag_cache with time.monotonic() timestamp
   - Invalidated on instance config changes or removal

4. **Invoke cycle function** (`run_radarr_cycle`, `run_sonarr_cycle`, or `run_lidarr_cycle`)
   - Client.get_wanted_missing() / get_wanted_cutoff() — paginated API fetch
   - Filter by monitored status
   - Filter by tag (if configured)
   - Cap batch sizes (hard_max_per_cycle)
   - Slice cursor-based batch
   - For each item: trigger search (client.command_search) and log to DB (insert_search_entry)
   - Update app.state.triggarr_state (cursors, last_run, connected flag)

5. **Evaluate cycle outcome** (`_evaluate_cycle_outcome`)
   - Read app.state[app_name][instance]["connected"] flag
   - If False: increment app.state.search_failures[job_id] (consecutive-failure counter)
   - If True or unknown: reset counter to 0
   - May escalate WARNING→ERROR if counter >= threshold (app.state.settings.general.max_consecutive_failures)

6. **Persist state** (atomic write-then-rename)
   - Call save_state(app.state.triggarr_state, state_path) in executor (non-blocking)
   - On success: reset app.state.persistence_degraded to False
   - On OSError/aiosqlite.Error: set app.state.persistence_degraded to True, log ERROR, re-raise for EVENT_JOB_ERROR listener

7. **Run tracking check** (resolve pending searches from prior cycles)
   - Query DB for pending items
   - Correlate with history grab events
   - Update DB outcome column (grabbed, partial, unresolved)
   - Log summary

8. **Release search_lock** (finally block)
   - Clear app.state.search_lock_holder = None

9. **If exception raised** (not swallowed by narrow-tuple catch)
   - APScheduler's EVENT_JOB_ERROR listener (_on_job_error) logs at ERROR level
   - Sanitizes httpx/pydantic exceptions to avoid logging API URLs with credentials

### Secondary Flow: Manual Search via Web UI

1. **POST /search_now** (routes.py::search_now)
   - Rate-limit check (10s between searches per instance)
   - Invoke cycle_fn directly (bypasses scheduler job factory)
   - Manually build tag resolver (reads app.state.tag_cache)
   - **NOTE**: Does NOT currently go through make_search_job, so does NOT increment/reset failure counter (SAFETY-03 TODO)

2. **Return partial** (htmx card update)
   - Render app card partial with updated state snapshot

### Tertiary Flow: Config Save

1. **POST /settings** (routes.py::save_settings)
   - Acquire app.state.search_lock (serializes with scheduler)
   - Validate InstanceConfig (Pydantic raises on invalid URL/api_key)
   - Extract SecretStr values via .get_secret_value() (only for TOML serialization)
   - Call _atomic_toml_write(config_path, data) — temp write + fsync + rename
   - Reload settings from disk
   - Invalidate tag_cache for changed instances
   - Update app.state.settings (live for next cycle)
   - Return redirect to /settings

**State Management:**

- **app.state.triggarr_state**: JSON-serializable dict (TriggarrState TypedDict)
  - Tracks per-instance cursors, timings, connection status, tag warnings
  - Loaded at startup, mutated by cycles, persisted after each cycle
  - Backup: search history copied to SQLite post-v2.3 (see db.py::migrate_from_state)

- **app.state.settings**: Pydantic Settings model
  - Immutable snapshot, replaced on config save
  - Read-only from cycle/route handlers (no in-place mutation)

- **app.state.search_failures**: dict[job_id, count]
  - Per-job consecutive-failure counter
  - Incremented on cycle failure, reset on success
  - Compared to max_consecutive_failures to escalate ERROR level

- **app.state.persistence_degraded**: bool
  - Set to True on save_state OSError
  - Reset to False on next successful save
  - Flags durability issues to operator (WR-09)

- **app.state.search_lock_holder**: (job_id, monotonic_start) | None
  - Set inside search_lock acquire in make_search_job
  - Cleared in finally block
  - Read by shutdown drain to log which instance is stuck (RES-01)

- **app.state.tag_cache**: dict[(app_name, instance_name), (tags, fetched_at)]
  - RES-03: Performance optimization for tag resolution
  - Invalidated on instance config change or removal
  - Uses time.monotonic() (not wall-clock) to avoid NTP-induced staleness

## Key Abstractions

**Search Job Closure:**
- Purpose: Encapsulate one scheduled search cycle with built-in failure tracking
- Examples: `triggarr/search/scheduler.py::make_search_job()` returns a closure
- Pattern: Factory returns async callable that reads app.state at runtime (enables config hot-reload)

**Cycle Function:**
- Purpose: Pure orchestrator that composes filters + API calls + state mutation
- Examples: `run_radarr_cycle()`, `run_sonarr_cycle()`, `run_lidarr_cycle()` in `triggarr/search/engine.py`
- Pattern: Receives client, state, config, DB; returns updated state (side-effects: logs, DB inserts)

**Atomic Write Pattern:**
- Purpose: Ensure no partial writes on crash/power loss
- Examples: `_atomic_toml_write()` in `triggarr/config.py`, `save_state()` in `triggarr/state.py`
- Pattern: Write to temp file in same filesystem, fsync, then rename (POSIX atomic on most filesystems)

**Tag Resolver:**
- Purpose: Resolve tag names to numeric IDs with caching
- Examples: `resolve_tag_id()` in `triggarr/search/engine.py`
- Pattern: Search tag list by case-insensitive label match; warn on miss

**Batch Cursor & Slicing:**
- Purpose: Round-robin distribute missing/cutoff items without repeated searches
- Examples: `slice_batch()` in `triggarr/search/engine.py`
- Pattern: Mutable cursor per app/instance in app.state.triggarr_state, wraps at end of list

## Entry Points

**CLI / Systemd / Docker:**
- Location: `triggarr/__main__.py::main()`
- Triggers: `python -m triggarr`
- Responsibilities: Wrap async entry point in asyncio.run(), handle KeyboardInterrupt

**Async Runtime Entry:**
- Location: `triggarr/__main__.py::_run()`
- Triggers: Called by main()
- Responsibilities: Load config, call startup(), construct FastAPI with lifespan, run uvicorn.Server.serve()

**FastAPI Lifespan Startup:**
- Location: `triggarr/search/scheduler.py::create_lifespan()` context manager __aenter__
- Triggers: On HTTP server startup
- Responsibilities: Load state, init DB, validate schema, migrate search_log, create clients, schedule jobs, start APScheduler

**FastAPI Lifespan Shutdown:**
- Location: `triggarr/search/scheduler.py::create_lifespan()` context manager __aexit__
- Triggers: On SIGTERM / graceful shutdown signal
- Responsibilities: Stop scheduler, drain search_lock (with timeout), close clients, close DB

## Architectural Constraints

- **Threading:** Single-threaded async event loop. uvicorn runs with workers=1 (no multiprocessing). asyncio.Lock in app.state assumes single event loop (see SAFETY-05 in scheduler.py).

- **Global state:** Module-level constants in scheduler.py (_SHUTDOWN_DRAIN_TIMEOUT, _TAG_CACHE_TTL_SECONDS). Auth.needs_setup and auth.is_disabled checked at request time to enable setup flow and Disabled mode.

- **Circular imports:** Avoided via lazy imports in _run() and lifespan. update_info and auth_state dicts imported into routes.py globals at module init, then shared into templates and app.state.

- **Lock coordination:** app.state.search_lock serializes (a) scheduled search cycles in make_search_job and (b) all config saves in routes.py::save_settings. Single asyncio.Lock is correct only with single uvicorn worker.

- **Shutdown window:** Drain timeout (_SHUTDOWN_DRAIN_TIMEOUT) must be less than the process manager's stop-timeout. Recommended: set docker-compose stop_grace_period > 60s (default), or docker run --stop-timeout > 60s.

## Anti-Patterns

### Bare Exception Swallow (Avoided)

**What happens:** A search cycle fails (httpx.HTTPError), swallows the exception without logging, and returns silently.

**Why it's wrong:** Operator has no visibility into transient *arr outages. May accumulate without notification.

**Do this instead:** Use narrow-tuple catch in make_search_job::job (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error). Log immediately in the catch block. Use _record_cycle_failure() to increment per-job counter. Let unexpected exceptions (RuntimeError, KeyError, etc.) propagate to APScheduler's EVENT_JOB_ERROR listener.

### Implicit Config Reload (Avoided)

**What happens:** A cycle function captures the client or settings at job creation time. Config changes are not visible to running cycles.

**Why it's wrong:** Users change Radarr URL mid-session, but the old URL is baked into the closure and never changes.

**Do this instead:** Use the job factory pattern in make_search_job. The returned closure reads app.state.{app_name}_clients and app.state.settings at execution time (not capture time). Config saves update app.state.settings in place, visible to the next cycle.

### Unguarded Cursor Mutation (Avoided)

**What happens:** Two concurrent cycles both read cursor=0, slice the same batch, and write cursor=5 twice (loss of progress).

**Why it's wrong:** Without synchronization, batch distribution is unpredictable and duplicated work occurs.

**Do this instead:** All cycles operate within app.state.search_lock (asyncio.Lock). Single-threaded event loop + lock enforces mutual exclusion. Cursor is advanced atomically within the lock.

### Direct SQLite Writes Without Transactions (Avoided)

**What happens:** An insert_search_entry call raises OSError halfway through. Table is partially updated, tracking fails, query results are inconsistent.

**Why it's wrong:** Durability is broken. Pending-row cap becomes stale. History queries see partial state.

**Do this instead:** All DB operations in db.py use aiosqlite (async), wrap multi-operation sequences in explicit transactions (db.execute() then db.commit()), and catch OSError/aiosqlite.Error at the call site. PendingCapExceeded exception stops the insert if pending rows exceed the cap.

## Error Handling

**Strategy:** Fail-open for transient issues (network blips, *arr temporary unavailability), fail-closed for permanent config errors (bad URL, invalid API key).

**Patterns:**

- **Transient *arr outage:** Cycle catch tuple swallows httpx.HTTPError (network, timeout, HTTP status), increments failure counter, returns gracefully. Next cycle retries. Operator sees WARNING after N consecutive failures → ERROR after exceeding threshold.

- **Config validation error:** Pydantic raises during settings load or POST validation. Return 422 Unprocessable Entity to web UI. Do not persist to disk.

- **Durability error (OSError):** save_state or DB insert raises OSError (disk full, permission denied, etc.). Set app.state.persistence_degraded = True. Log ERROR immediately. Re-raise to EVENT_JOB_ERROR listener. Operator sees ERROR + degraded flag → should investigate disk space or permissions.

- **Code bug (RuntimeError, KeyError, etc.):** Not caught by narrow-tuple in cycle. Propagates to APScheduler's EVENT_JOB_ERROR listener. Logged at ERROR with job_id context. Operator sees clear ERROR message (not silent disappearance).

## Cross-Cutting Concerns

**Logging:** Loguru with custom redacting sink (triggarr/logging.py). All API keys extracted at startup via collect_secrets() and added to redaction list. HTTP client retry logs at DEBUG, failures at WARNING/ERROR. Never log full request/response bodies (may contain credentials).

**Validation:** Pydantic models throughout (Settings, InstanceConfig, GrabEvent, Tag, etc.). Field validators reject embedded API keys in URLs (SEC-02 D-06). at_least_one_search_count validator ensures meaningful batch sizes. reject_apikey_in_url validator runs before config persistence.

**Authentication:** Auth module (triggarr/auth.py) provides session + Basic + API-key modes. Middleware checks in order: session cookie → X-Api-Key header → Basic Authorization header. Timing-safe compare (secrets.compare_digest) prevents timing attacks. AuthMiddleware._handle_basic_auth validates and signs session cookie. Passwords hashed with argon2-cffi.

---

*Architecture analysis: 2026-06-01*
