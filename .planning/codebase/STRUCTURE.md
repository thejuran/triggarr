# Codebase Structure

**Analysis Date:** 2026-05-25

## Directory Layout

```
triggarr/                                # Main package root
├── __init__.py                          # Package init (empty)
├── __main__.py                          # CLI entry point: main() and _run()
├── auth.py                              # Session, password, API key validation (D-11)
├── changelog.py                         # Parse CHANGELOG.md for display
├── config.py                            # TOML loading, defaults, v2.2→v2.3 migration
├── correlation.py                       # DEPRECATED (migrated to db.py)
├── db.py                                # SQLite search history + migrations (SRCH-13)
├── log_buffer.py                        # Recent log messages for web UI
├── logging.py                           # Loguru setup with secret redaction
├── startup.py                           # Startup orchestration (validation, banner)
├── state.py                             # JSON cursor/history tracking (atomic writes)
├── tracking.py                          # Post-search grab event correlation
├── update_check.py                      # Background version check (async)
├── version.py                           # __version__ constant
│
├── models/
│   ├── __init__.py
│   ├── config.py                        # Pydantic: Settings, InstanceConfig, AuthConfig
│   └── arr.py                           # Pydantic: Tag, SystemStatus, GrabEvent, etc.
│
├── clients/
│   ├── __init__.py
│   ├── base.py                          # ArrClient base class (pagination, retry)
│   ├── radarr.py                        # RadarrClient (wanted/missing, cutoff)
│   ├── sonarr.py                        # SonarrClient (series, seasons)
│   └── lidarr.py                        # LidarrClient (artists, albums)
│
├── search/
│   ├── __init__.py
│   ├── scheduler.py                     # APScheduler lifespan, job factory
│   └── engine.py                        # Search cycles, filtering, batching
│
├── web/
│   ├── __init__.py
│   ├── routes.py                        # FastAPI routes, template rendering
│   ├── middleware.py                    # Auth, CSRF, security headers
│   ├── security.py                      # Secure request detection
│   └── validation.py                    # Form input sanitization
│
├── templates/
│   ├── base.html                        # Base layout (nav, footer)
│   ├── base-auth.html                   # Auth layout (login, setup forms)
│   ├── dashboard.html                   # Main dashboard page
│   ├── history.html                     # Search history page
│   ├── login.html                       # Login form
│   ├── setup.html                       # Initial auth setup form
│   ├── settings.html                    # Config editor form
│   └── partials/
│       ├── app-card.html                # Instance status card (htmx target)
│       ├── search-log-row.html          # Search history row
│       ├── settings-*.html              # Settings form partials (radarr, sonarr, etc.)
│       └── [others]                     # Form fragments, modals
│
├── static/
│   ├── css/
│   │   ├── input.css                    # Tailwind source (dev)
│   │   └── output.css                   # Compiled CSS (Dockerfile builder stage)
│   ├── js/
│   │   └── [helpers]                    # Minimal JS (htmx handles most interactivity)
│   ├── fonts/
│   │   └── [webfonts]                   # System fonts or custom typefaces
│   └── vendor/
│       ├── htmx.min.js                  # HTmx library (form fragments)
│       └── phosphor/                    # Phosphor icon set (SVG)
│
└── [tests]/                             # Test suite (sibling to triggarr/ in project)
    ├── conftest.py                      # Pytest fixtures
    ├── test_*.py                        # Test modules
    └── [fixtures]/                      # Test data
```

## Directory Purposes

**triggarr/ (root):**
- Purpose: Main package entry point and core app logic
- Contains: CLI entry point, startup, state/config persistence, logging setup
- Key files: `__main__.py`, `startup.py`, `config.py`, `state.py`

**triggarr/models/:**
- Purpose: Pydantic schema definitions for configuration and API models
- Contains: Settings, InstanceConfig, AuthConfig, arr API models (Tag, GrabEvent, etc.)
- Key files: `config.py` (base schemas), `arr.py` (API models)

**triggarr/clients/:**
- Purpose: Async HTTP wrappers for *arr application REST APIs
- Contains: Base client with pagination/retry, Radarr/Sonarr/Lidarr subclasses
- Key files: `base.py` (abstract + shared logic), `radarr.py`, `sonarr.py`, `lidarr.py`

**triggarr/search/:**
- Purpose: Search orchestration and scheduling logic
- Contains: APScheduler integration, job factories, search cycles, filtering/batching
- Key files: `scheduler.py` (lifespan, jobs), `engine.py` (cycles, filters)

**triggarr/web/:**
- Purpose: Web server routes, middleware, and request handling
- Contains: FastAPI route handlers, auth middleware, security layers
- Key files: `routes.py` (handlers), `middleware.py` (auth/CSRF), `security.py` (validation)

**triggarr/templates/:**
- Purpose: Jinja2 HTML templates for UI rendering
- Contains: Base layouts, page templates, htmx form fragments
- Key files: `base.html` (layout), `dashboard.html` (home), `settings.html` (config editor), `partials/` (fragments)

**triggarr/static/:**
- Purpose: Static assets (CSS, JavaScript, fonts, icons)
- Contains: Tailwind CSS output, htmx library, Phosphor icons
- Key files: `css/output.css` (compiled Tailwind), `vendor/htmx.min.js`

## Key File Locations

**Entry Points:**
- `triggarr/__main__.py`: CLI entry point (`main()`) and async server start (`_run()`)
- `triggarr/startup.py`: Startup sequence (config load, validation, logging setup)
- `triggarr/web/routes.py`: FastAPI app creation and route registration (via `create_lifespan()`)

**Configuration:**
- `triggarr/config.py`: TOML loading, defaults, atomic writes, v2.2 migration
- `triggarr/models/config.py`: Pydantic Settings schema and validators
- `triggarr/models/arr.py`: Pydantic models for *arr API responses (Tag, GrabEvent, etc.)

**Core Logic:**
- `triggarr/search/scheduler.py`: APScheduler lifespan integration, job creation per instance
- `triggarr/search/engine.py`: Pure functions for filtering/batching + cycle orchestrators
- `triggarr/clients/base.py`: Base async HTTP client with pagination and retry logic
- `triggarr/clients/radarr.py`, `sonarr.py`, `lidarr.py`: App-specific endpoint methods

**State & Persistence:**
- `triggarr/state.py`: JSON state loading/saving with atomic writes
- `triggarr/db.py`: SQLite database + migration system for search history
- `triggarr/tracking.py`: Grab event correlation and outcome resolution

**Web & UI:**
- `triggarr/web/routes.py`: All HTTP endpoint handlers and template rendering
- `triggarr/web/middleware.py`: Auth, CSRF, security headers
- `triggarr/templates/base.html`: Base layout (nav, footer, shared blocks)
- `triggarr/templates/dashboard.html`: Home page with instance status cards
- `triggarr/templates/settings.html`: Config editor form

**Testing:**
- `tests/test_*.py`: Test modules (unit, integration, e2e)
- `tests/conftest.py`: Pytest fixtures and shared setup

## Naming Conventions

**Files:**
- Entry points: `__main__.py`, `__init__.py`
- Core modules: `{domain}.py` (e.g., `config.py`, `state.py`, `auth.py`)
- Package subdirs: `{layer}/` (e.g., `clients/`, `web/`, `search/`)
- Tests: `test_{module}.py` (e.g., `test_config.py`, `test_scheduler.py`)
- Templates: `{page}.html` (e.g., `dashboard.html`), `{page}_partial.html` for fragments
- Partials: `partials/{component}.html` (e.g., `partials/app-card.html`)

**Directories:**
- Package modules: PascalCase for packages (`triggarr/web/`, `triggarr/models/`)
- Logical grouping: snake_case for roles (e.g., `search/`, `clients/`)
- Static assets: `static/{css,js,fonts,vendor}/`
- Config templates: `templates/`, `templates/partials/`

**Functions:**
- Public: `snake_case` (e.g., `load_settings()`, `make_search_job()`)
- Private: `_snake_case` prefix (e.g., `_sanitize_exc()`, `_atomic_toml_write()`)
- Async: `async def` keyword, same naming (e.g., `async def startup()`, `async def run_radarr_cycle()`)

**Classes:**
- Models: `PascalCase` with no suffix (e.g., `Settings`, `InstanceConfig`, `RadarrClient`)
- Exceptions: `PascalCase` with `Error` or `Exception` suffix (none currently defined)

**Variables:**
- Constants: `UPPER_SNAKE_CASE` (e.g., `APP_TYPES`, `EXEMPT_PREFIXES`, `SEARCH_RATE_LIMIT_SECONDS`)
- Config dicts: `snake_case` (e.g., `app.state.radarr_clients`, `app.state.triggarr_state`)
- Loop variables: `snake_case` (e.g., `for app_type in APP_TYPES`)

## Where to Add New Code

**New Feature (e.g., Weekly Schedule Report):**
- Primary code: `triggarr/web/routes.py` (new route handler)
- Logic: `triggarr/search/engine.py` (new query function if needed)
- Template: `triggarr/templates/report.html` (new page template)
- Tests: `tests/test_web_routes.py` (test the handler)

**New App Type (e.g., Whisparr for comics):**
- Config model: Add field to `triggarr/models/config.py` (e.g., `whisparr: dict[str, InstanceConfig]`)
- Client: New file `triggarr/clients/whisparr.py` (subclass ArrClient)
- Search cycle: Add handler to `triggarr/search/engine.py` (e.g., `async def run_whisparr_cycle()`)
- Scheduler: Update `triggarr/search/scheduler.py` to create jobs for whisparr instances
- State: Update `triggarr/state.py` to initialize whisparr cursors
- Database: Update `triggarr/db.py` migration if tracking schema changes
- Web: Update `triggarr/web/routes.py` form handlers for whisparr config
- Tests: Add test files `tests/test_whisparr_client.py`, etc.

**New Component/Module (e.g., Notification System):**
- Implementation: New package `triggarr/notify/` with submodules (e.g., `webhook.py`, `discord.py`)
- Integration: Import and call from `triggarr/search/engine.py` after cycle completes
- Config: Add NotifyConfig section to `triggarr/models/config.py`
- State: Track notification outcomes in `triggarr/db.py` if history needed
- Tests: `tests/test_notify_*.py`

**Utilities (e.g., New Filter Function):**
- Shared helpers: `triggarr/search/engine.py` (if search-related)
- Validation helpers: `triggarr/web/validation.py` (if form input)
- Client utilities: `triggarr/clients/base.py` (if HTTP-related)
- Auth utilities: `triggarr/auth.py` (if auth-related)

## Special Directories

**triggarr/templates/:**
- Purpose: Jinja2 HTML templates for web UI
- Generated: No (hand-written)
- Committed: Yes
- Patterns: Base template inheritance, htmx attributes for form fragments
- Tailwind classes: Used for styling (compiled by Docker builder)

**triggarr/static/:**
- Purpose: Static assets served at `/static/{path}`
- Generated: `css/output.css` generated by Tailwind build (not in repo, generated in Dockerfile)
- Committed: Only source `css/input.css` + vendor libs (htmx, Phosphor)
- Mount: FastAPI `StaticFiles()` mount at line 72 of `__main__.py`

**tests/:**
- Purpose: Pytest test suite
- Generated: `.pytest_cache/`, `__pycache__/` (not committed)
- Committed: Yes (test files + fixtures)
- Fixtures: `conftest.py` provides temp config dir, temp state file, mock clients
- Run: `uv run pytest tests/ -x -q`

**.planning/**
- Purpose: GSD planning and codebase analysis documents
- Generated: Yes (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Committed: Yes (tracks architecture over time)

**.gsd/**
- Purpose: GSD orchestrator state and phase history
- Generated: Yes (auto-generated by /gsd commands)
- Committed: Yes (keeps audit trail)

---

*Structure analysis: 2026-05-25*
