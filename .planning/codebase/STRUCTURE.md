# Codebase Structure

**Analysis Date:** 2026-06-01

## Directory Layout

```
triggarr/
├── __main__.py              # CLI entry point: asyncio.run(_run())
├── __init__.py              # Package marker
├── startup.py               # Startup orchestration: config load, logging, validation
├── config.py                # TOML I/O, atomic writes, v2.2→v2.3 migration
├── state.py                 # JSON state persistence: cursors, timings
├── auth.py                  # Session + Basic + API-key auth, password hashing
├── logging.py               # Loguru setup with secret redaction
├── changelog.py             # Version history parsing
├── correlation.py           # Grab event correlation (tracking helper)
├── tracking.py              # Pending search resolution with history matching
├── update_check.py          # Version check against GitHub releases
├── version.py               # Display version helpers
├── db.py                    # SQLite search history, schema migrations
├── log_buffer.py            # In-memory log storage for UI
│
├── clients/                 # *arr API clients (httpx wrappers)
│   ├── __init__.py
│   ├── base.py              # ArrClient base: pagination, retry, status validation
│   ├── radarr.py            # RadarrClient: wanted/missing/cutoff endpoints
│   ├── sonarr.py            # SonarrClient: episode dedup, API version detection
│   └── lidarr.py            # LidarrClient: artist/album hierarchy
│
├── models/                  # Pydantic data models
│   ├── __init__.py
│   ├── config.py            # Settings, InstanceConfig, AuthConfig, GeneralConfig
│   └── arr.py               # PaginatedResponse, GrabEvent, Tag, SystemStatus
│
├── search/                  # Search orchestration & scheduling
│   ├── __init__.py
│   ├── scheduler.py         # APScheduler lifespan integration, job factory
│   │                        # - create_lifespan() context manager
│   │                        # - make_search_job() closure factory
│   │                        # - Graceful shutdown drain (RES-01)
│   │                        # - Failure escalation (SAFETY-03)
│   └── engine.py            # Search cycle logic
│                            # - Filters: monitored, tags, dates
│                            # - Batch: cursor, slice, dedup
│                            # - Cycles: run_radarr_cycle, run_sonarr_cycle, run_lidarr_cycle
│
├── web/                     # HTTP server & routes
│   ├── __init__.py
│   ├── routes.py            # GET/POST handlers, htmx partials
│   │                        # - /health, /, /dashboard, /settings, /history
│   │                        # - /search_now, /tag_autocomplete, +add/remove instance
│   │                        # - htmx partials: app_card, activity_rail, stats_row, etc.
│   ├── middleware.py        # SecurityHeadersMiddleware, OriginCheckMiddleware, AuthMiddleware
│   ├── security.py          # is_secure_request() for cookie Secure flag
│   └── validation.py        # Input validators: safe_int, safe_log_level, validate_arr_url
│
├── static/                  # CSS, JavaScript
│   ├── css/
│   │   ├── input.css        # Tailwind v4 input (built by tailwindcss CLI)
│   │   └── output.css       # Compiled Tailwind CSS (served to browser)
│   └── js/
│       └── app.js           # htmx setup, polling intervals
│
└── templates/               # Jinja2 templates
    ├── base.html            # Main layout (nav, sidebar, slots)
    ├── base-auth.html       # Auth-layer layout (login, setup, no sidebar)
    ├── dashboard.html       # Dashboard page: app cards, activity rail
    ├── history.html         # Search history page wrapper
    ├── settings.html        # Settings editor: instance forms, auth, general config
    ├── setup.html           # Initial auth setup wizard
    ├── login.html           # Login page (session auth)
    └── partials/            # htmx fragment responses
        ├── app_card.html    # Individual app status card (polling target)
        ├── activity_rail.html
        ├── stats_row.html
        ├── history_results.html
        ├── health_summary.html
        ├── connection_pill.html
        ├── instance_form.html  # Settings: single instance sub-form
        ├── auth_forms.html     # Settings: auth method options
        ├── general_form.html   # Settings: general config
        └── [others]
```

## Directory Purposes

**triggarr/**
- Purpose: Root package, entry point is __main__.py
- Contains: Core orchestration, config/state I/O, startup sequence
- Key files: `__main__.py`, `startup.py`, `config.py`, `state.py`

**triggarr/clients/**
- Purpose: Async HTTP wrappers for Radarr/Sonarr/Lidarr APIs
- Contains: Base client class, app-specific subclasses, pagination/retry logic
- Key files: `base.py` (defines ArrClient), `radarr.py`, `sonarr.py`, `lidarr.py`

**triggarr/models/**
- Purpose: Pydantic validation models for config and API responses
- Contains: Settings, InstanceConfig, AuthConfig, API response envelopes
- Key files: `config.py` (settings schema), `arr.py` (API response types)

**triggarr/search/**
- Purpose: Scheduled search cycle orchestration and cycle logic
- Contains: APScheduler integration, job factory, filter/batch/dedup functions, cycle functions
- Key files: `scheduler.py` (lifespan + jobs), `engine.py` (cycle logic)

**triggarr/web/**
- Purpose: HTTP server, authentication, request validation
- Contains: FastAPI routes, middleware, security helpers, input validators
- Key files: `routes.py` (all endpoints), `middleware.py` (auth + CSRF + security headers)

**triggarr/static/**
- Purpose: Frontend assets (CSS, JavaScript)
- Contains: Tailwind CSS output (built from input.css), htmx polling setup
- Key files: `css/output.css` (served to browser), `js/app.js` (client-side behavior)

**triggarr/templates/**
- Purpose: Jinja2 HTML templates and htmx fragments
- Contains: Page layouts, forms, dynamic partials for polling updates
- Key files: `base.html` (main layout), `dashboard.html` (main page), `settings.html` (config editor)

## Key File Locations

**Entry Points:**
- `triggarr/__main__.py`: CLI entry point (main() and _run())
- `triggarr/search/scheduler.py::create_lifespan()`: FastAPI lifespan (startup/shutdown)

**Configuration:**
- `triggarr/config.py`: TOML loading, default generation, atomic writes
- `triggarr/models/config.py`: Pydantic settings + instance config schema
- `triggarr/startup.py`: Startup sequence (load config, validate, print banner)

**Core Logic:**
- `triggarr/search/scheduler.py::make_search_job()`: Job factory closure
- `triggarr/search/engine.py`: run_radarr_cycle, run_sonarr_cycle, run_lidarr_cycle
- `triggarr/clients/base.py`: Base ArrClient class with pagination/retry

**Testing:**
- Tests live in `tests/` directory (sibling to `triggarr/`)
- Test fixtures in `tests/fixtures/` (temp dirs, mock apps, etc.)
- Test patterns: pytest-asyncio with asyncio_mode=auto

**Persistence:**
- `triggarr/state.py`: JSON state file I/O, cursor tracking
- `triggarr/db.py`: SQLite search history, schema versioning
- `triggarr/config.py::_atomic_toml_write()`: Atomic config writes

**Web UI:**
- `triggarr/web/routes.py`: All GET/POST handlers and htmx endpoints
- `triggarr/templates/dashboard.html`: Main UI page
- `triggarr/templates/settings.html`: Settings editor
- `triggarr/templates/partials/`: htmx fragment responses

**Authentication:**
- `triggarr/auth.py`: Session signing, password hashing, API key generation
- `triggarr/web/middleware.py::AuthMiddleware`: Request-time auth checks

## Naming Conventions

**Files:**
- Modules are lowercase with underscores: `search_engine.py` is `search/engine.py`
- Package directories are lowercase: `triggarr/clients/`, `triggarr/web/`
- HTML templates are lowercase: `dashboard.html`, `base.html`
- Partials are in `partials/` subdirectory: `partials/app_card.html`

**Functions:**
- Async functions are async def: `async def run_radarr_cycle(...)`
- Private/internal functions start with `_`: `_atomic_toml_write()`, `_record_cycle_failure()`
- Factory functions are named make_*: `make_search_job()`
- Handler functions are named {action}_{resource}: `search_now()`, `save_settings()`, `add_instance()`

**Variables:**
- Module constants are UPPER_CASE: `EXEMPT_PREFIXES`, `_SHUTDOWN_DRAIN_TIMEOUT`
- Classes are PascalCase: `RadarrClient`, `InstanceConfig`, `AuthMiddleware`
- Instances/variables are snake_case: `instance_name`, `search_interval`, `client`
- Secrets are SecretStr (Pydantic): `api_key: SecretStr`, never plain str

**Types:**
- Pydantic models live in `models/`: `models/config.py`, `models/arr.py`
- TypedDict (runtime type hints) in `state.py`: `AppState`, `TriggarrState`
- Protocol abstractions in docstrings, not separate files

## Where to Add New Code

**New Feature (e.g., add Lidarr to dashboard):**
- Primary code: `triggarr/search/engine.py::run_lidarr_cycle()` (cycle logic)
- Client: `triggarr/clients/lidarr.py::LidarrClient` (API wrapper)
- Config: `triggarr/models/config.py::Settings.lidarr` (instance config)
- Scheduler: Already generic in `triggarr/search/scheduler.py` (no changes needed)
- Routes: `triggarr/web/routes.py` (dashboard context builder, already generic)
- Templates: `triggarr/templates/partials/app_card.html` (already generic)
- Tests: `tests/test_lidarr_cycle.py`, `tests/test_lidarr_client.py`

**New Endpoint (e.g., /api/stats):**
- Add route handler to `triggarr/web/routes.py`: `@router.get("/api/stats")`
- If it returns HTML (htmx): use templates from `triggarr/templates/` and `Jinja2Templates.TemplateResponse()`
- If it returns JSON: use `JSONResponse()`
- Add auth check via `AuthMiddleware` (automatic — all routes behind auth unless in `EXEMPT_PREFIXES`)
- Tests: `tests/test_web.py` or new `tests/test_api_stats.py`

**New Component/Module (e.g., notification system):**
- Implementation: Create new file in appropriate directory
  - Business logic: `triggarr/notify.py` (if cross-cutting) or `triggarr/search/notify.py` (if search-related)
  - API wrapper: `triggarr/clients/discord.py` (if external service)
  - Config: Add fields to `triggarr/models/config.py::GeneralConfig` or new subsection
- Integration: Call from affected layers
  - Post-cycle: Call in `triggarr/search/engine.py` cycle functions
  - Post-search: Call in `triggarr/search/scheduler.py::make_search_job()`
  - On error: Call in error handlers
- Secrets: Use SecretStr for API keys, extract in `triggarr/startup.py::collect_secrets()`
- Tests: `tests/test_notify.py`

**Utilities / Shared Helpers:**
- Filtering/batching logic: `triggarr/search/engine.py` (already home to filter_monitored, slice_batch, etc.)
- Validation: `triggarr/web/validation.py` (safe_int, safe_log_level, validate_arr_url)
- Time/date formatting: `triggarr/web/routes.py` (_relative_time, _format_duration) or extract to `triggarr/util.py`
- DB helpers: `triggarr/db.py` (all schema + query functions in one place)
- Logging: `triggarr/logging.py` (setup_logging) + `triggarr/log_buffer.py` (in-memory storage)

**Tests:**
- Unit tests: `tests/test_{module}.py` mirrors `triggarr/{module}.py`
  - Example: `tests/test_engine.py` tests `triggarr/search/engine.py`
- Integration tests: `tests/test_{feature}.py` for cross-module flows
  - Example: `tests/test_radarr_search_integration.py` tests full cycle from scheduler to DB
- Fixtures: `tests/fixtures/` or inline `@pytest.fixture` in test files
- Conftest: `tests/conftest.py` for shared fixtures (mock clients, temp dirs, etc.)
- Run: `uv run pytest tests/ -x -q`

## Special Directories

**triggarr/static/css/**
- Purpose: Generated Tailwind CSS
- Generated: Yes (by tailwindcss CLI: `tailwindcss -i input.css -o output.css --watch`)
- Committed: Yes (output.css committed to avoid build step in Docker)
- Development: Edit `input.css`, run tailwindcss in watch mode, output.css auto-updates

**triggarr/templates/partials/**
- Purpose: htmx fragment responses (not standalone pages)
- Generated: No
- Committed: Yes
- Pattern: Each partial is a complete HTML snippet, no <html>/<body> wrapper
- Usage: Returns via `Jinja2Templates.TemplateResponse(...)` with status 200
- Naming: `{noun}_{descriptor}.html` (app_card.html, activity_rail.html)

**.planning/codebase/**
- Purpose: Generated by /gsd:map-codebase (this directory)
- Generated: Yes (ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md)
- Committed: Yes
- Consumed by: /gsd:plan-phase (reads context), /gsd:execute-phase (enforces patterns)

---

*Structure analysis: 2026-06-01*
