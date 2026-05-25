# Technology Stack

**Analysis Date:** 2026-05-25

## Languages

**Primary:**
- Python 3.11+ - Core application logic, API server, scheduling, and search engine

**Secondary:**
- HTML/Jinja2 - Web UI templates
- Tailwind CSS v4 - Styling (compiled during build to `triggarr/static/css/output.css`)

## Runtime

**Environment:**
- Python 3.13 (Dockerfile uses `python:3.13-slim`)
- Docker containerization with multi-stage build (Tailwind CSS builder + production image)
- uv - Package manager and dependency management (replaces pip/pip-tools)

**Package Manager:**
- uv with `pyproject.toml` configuration
- Lockfile: `uv.lock` (present, provides reproducible installs)

## Frameworks

**Core:**
- FastAPI 0.115+ - HTTP API framework and web server
- Uvicorn [standard] - ASGI application server (runs on port 8484)
- APScheduler 3.11.x - Job scheduling for automated search cycles

**Frontend:**
- Jinja2 - Server-side template rendering
- htmx - HTML attribute-driven dynamic frontend interactions
- Tailwind CSS v4.2.1 - Utility-first CSS framework (build pinned in Dockerfile)
- pytailwindcss - Tailwind CLI wrapper for build processes

**Testing:**
- pytest 9.0.3+ - Test runner
- pytest-asyncio - Async test support with `asyncio_mode=auto`

**Build/Dev:**
- Ruff - Fast Python linter (E, F, I, UP, B, SIM rules; line length 120)
- Hatchling - Build backend for PyPI packaging

## Key Dependencies

**Critical:**
- httpx - Async HTTP client for Radarr/Sonarr/Lidarr API communication with connection pooling and timeout control
- pydantic-settings[toml] - TOML configuration loading and Pydantic v2 settings validation
- aiosqlite - Async SQLite driver for search history persistence
- loguru - Structured logging with custom redacting sink for API key safety

**Infrastructure:**
- uvicorn[standard] - ASGI server with uvloop, httptools optimizations
- fastapi - Async web framework (includes Starlette, Pydantic)
- apscheduler - APScheduler for periodic search scheduling
- aiofiles - Async file I/O (used for config/state file writes)

**Security & Auth:**
- bcrypt - Password hashing with 12 rounds (v5.0.0)
- itsdangerous - Cryptographic signing for session cookies (TimestampSigner-based)
- SecretStr (from pydantic) - Type-safe secret value handling for API keys

**Configuration & Serialization:**
- tomli-w - Atomic TOML writing for config persistence
- tomllib (Python 3.11+ stdlib) - TOML parsing
- python-multipart 0.0.27+ - Multipart form handling for FastAPI
- jinja2 - HTML template rendering

## Configuration

**Environment:**
- `TRIGGARR_CONFIG_DIR` (optional, default `/config`) - Base directory for `triggarr.toml` and state files
- `ROOT_PATH` (optional, default empty) - Root path for reverse proxy support
- `TRUSTED_PROXY_IPS` (optional, default `127.0.0.1`) - Comma-separated IPs trusted for X-Forwarded-* headers; use `*` only behind controlled reverse proxy
- `PUID` / `PGID` (Docker, optional, default 1000) - User/group ID for container execution
- `TAILWINDCSS_VERSION` (Dockerfile, pinned to `v4.2.1`) - Tailwind CSS binary version for reproducible CSS builds

**Build:**
- `pyproject.toml` - Project metadata, dependencies, and build configuration
- `Dockerfile` - Multi-stage Docker build (builder stage for Tailwind CSS, production stage with slim Python image)
- `.dockerignore` - Build context exclusions (prevents .git, .venv, etc. in image)
- `entrypoint.sh` - Container startup script with PUID/PGID privilege management

## Platform Requirements

**Development:**
```bash
uv sync --extra dev                    # Install with dev dependencies
uv run pytest tests/ -x -q             # Run tests with asyncio_mode=auto
uv run ruff check triggarr/ tests/     # Lint with Ruff (E,F,I,UP,B,SIM)
uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css --watch
```

**Production:**
- Docker image: `ghcr.io/thejuran/triggarr` (published from GitHub Actions)
- Container port: 8484 (HTTP)
- Volume mount: `/config` - Config directory (holds `triggarr.toml`, `state.json`, `search_history.db`)
- Health check: HTTP GET `http://localhost:8484/health` (30s interval, 5s timeout, 3 retries)
- Non-root user: `triggarr` or UID from `PUID` (Linux capability: dropped via entrypoint.sh)

---

*Stack analysis: 2026-05-25*
