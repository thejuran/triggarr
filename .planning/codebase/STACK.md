# Technology Stack

**Analysis Date:** 2026-06-01

## Languages

**Primary:**
- Python 3.11+ - Core application logic, async daemon, API clients
- HTML/Jinja2 3.11+ - Web UI templates with htmx integration
- CSS v4 - Tailwind CSS v4.2.1 via pytailwindcss (compiled, minified in Docker)
- JavaScript (minimal) - Bundled with Tailwind/htmx, no build pipeline

## Runtime

**Environment:**
- Python 3.13-slim (Docker production) / Python 3.11+ (development)

**Package Manager:**
- `uv` (lockfile: `uv.lock`)
- Lockfile present at `uv.lock` (197KB, auto-generated)

## Frameworks

**Core:**
- FastAPI 0.100+ - Async HTTP server (8484 default port, ASGI via Uvicorn)
- Uvicorn[standard] - ASGI server with native proxy header support

**Web & UI:**
- Jinja2 3.11+ - Template engine for HTML rendering
- htmx (included in static assets) - AJAX/hypermedia interactions
- Tailwind CSS v4.2.1 - Utility-first CSS framework, compiled at build time

**Scheduling & Automation:**
- APScheduler 3.11+ - Event-driven search scheduling with cron/interval support

**Database & State:**
- aiosqlite - Async SQLite wrapper (versioned migrations, search history + state persistence)
- aiofiles - Async file I/O for config/state writes

**Authentication & Security:**
- bcrypt - Password hashing (12 rounds)
- itsdangerous - Session cookie signing (TimestampSigner)
- Pydantic SecretStr - Type-safe secret storage (never logged/exposed)

**Testing:**
- pytest 9.0.3+ - Test runner
- pytest-asyncio - Async test support (`asyncio_mode=auto`)

**Development & Linting:**
- ruff - Fast linter/formatter (rules: E, F, I, UP, B, SIM; line length 120)
- pytailwindcss - Tailwind CSS compiler (`tailwindcss_install` + CLI)

## Key Dependencies

**Critical:**
- httpx - Async HTTP client for Radarr/Sonarr/Lidarr API calls + GitHub update checks
  - 30s default timeout, retry logic on transient failures (2s backoff)
  - API key injection into X-Api-Key header + Content-Type: application/json
- pydantic-settings[toml] - Config validation + TOML file loading
- loguru - Structured logging with custom redacting sink (secrets masked in full output + tracebacks)
- tomli-w - Atomic TOML serialization (write-then-rename pattern for config)

**Infrastructure:**
- python-multipart 0.0.27+ - Form data parsing for web UI settings POST
- jinja2 - Template rendering (no auto-escaping for htmx/inline JS)

## Configuration

**Environment:**
- `TRIGGARR_CONFIG_DIR` - Config directory (default: `/config`, must be absolute)
- `ROOT_PATH` - Reverse proxy prefix (empty string if not set)
- `TRUSTED_PROXY_IPS` - CSV of IPs to trust X-Forwarded-For/Proto from (default: `127.0.0.1`, special value `*`)

**Build:**
- `pyproject.toml` - Project metadata, dependencies, tool configs
- `Dockerfile` - Multi-stage: Tailwind CSS compilation stage → production runtime
- `entrypoint.sh` - Non-root user privilege drop (`triggarr_default` fallback)

## Platform Requirements

**Development:**
```bash
uv sync --extra dev              # install with dev deps
uv run pytest tests/ -x -q       # test
uv run ruff check triggarr/ tests/  # lint (120 char line)
uv run tailwindcss -w            # CSS watch (v4.2.1)
docker build -t triggarr:local . # Docker build
```

**Production:**
- Docker container (ghcr.io/thejuran/triggarr)
- Single-threaded asyncio event loop (no threading model)
- SQLite database at `{TRIGGARR_CONFIG_DIR}/triggarr.db` (with migrations)
- Config file at `{TRIGGARR_CONFIG_DIR}/triggarr.toml`
- Secrets stored as environment variables → injected via SecretStr
- Health check endpoint: `GET /health` (200 OK when ready)
- Exposed port: 8484

## Data Flow at Startup

1. `uv run python -m triggarr` → `triggarr/__main__.py:main()`
2. Load config from `triggarr.toml` via Pydantic Settings TOML loader
3. Validate all Radarr/Sonarr/Lidarr instances (URL + API key via httpx)
4. Initialize SQLite database + run versioned migrations
5. Start APScheduler with lifespan-managed background search cycles
6. Mount FastAPI app with auth/CSRF/security middlewares
7. Serve on `0.0.0.0:8484` with optional reverse proxy prefix

---

*Stack analysis: 2026-06-01*
