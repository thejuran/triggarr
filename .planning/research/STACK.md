# Stack Research

**Domain:** Lightweight Python Docker tool — Radarr/Sonarr search automation with minimal web UI
**Researched:** 2026-02-23
**Confidence:** HIGH (all versions verified against PyPI/official sources)

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.13-slim (Docker) | Runtime | Latest stable; uvicorn 0.41.0 dropped 3.9 support, requires 3.10+; 3.13-slim gives the newest stdlib tomllib + performance gains with minimal image size |
| FastAPI | 0.132.0 | HTTP server + UI endpoints | Handles both API routes and Jinja2 template routes in a single framework; async-native so scheduler and HTTP client don't block each other; matches existing user stack (VolvLog) |
| Uvicorn | 0.41.0 | ASGI server | FastAPI's standard server; install with `uvicorn[standard]` to get uvloop for better async perf; single-process is correct here (no horizontal scaling needed) |
| Jinja2 | (bundled with FastAPI[standard]) | HTML templating | Server-side rendering, no JS build step, pairs directly with htmx fragment responses |
| htmx | 2.0.7 (CDN) | Client-side interactivity | Delivers dynamic UI updates (live log refresh, status polling) without a JavaScript framework; served from CDN to avoid Node.js in the container |

### Scheduler

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| APScheduler | 3.11.2 | Background search scheduling | v3 is the current stable (v4 is still in alpha, 4.0.0a6 as of April 2025); `AsyncIOScheduler` runs on FastAPI's asyncio event loop without spawning extra threads; interval jobs with configurable delay per-app map directly to the round-robin search requirement |

Do NOT use APScheduler v4. It is alpha-only (4.0.0a6), has a completely rewritten API incompatible with v3, and is not production-ready as of February 2026.

### HTTP Client (Radarr/Sonarr API calls)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| httpx | 0.28.1 | Async HTTP client for Radarr/Sonarr API | Async-native (`AsyncClient`) so API calls don't block the event loop during scheduled runs; supports connection pooling and timeout configuration; no third-party arr library needed — raw httpx calls against the documented v3 REST endpoints give full control and zero wrapper abstraction surprises |

Do NOT use `requests`. It is synchronous and will block the asyncio event loop during API calls, causing scheduler drift and UI freezes.

Do NOT use third-party arr client libraries (`pyarr`, `radarr-py`, `aiopyarr`). They add maintenance risk and abstraction layers for an API surface you fully control. Radarr and Sonarr both expose clean, stable REST endpoints that httpx calls directly with 20 lines of code.

### Configuration Storage

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| tomllib | stdlib (Python 3.11+) | Read config.toml at startup | Built into Python 3.11+, no extra dependency; TOML is human-readable with comment support, ideal for config files users edit directly in Docker volume mounts |
| tomli-w | 1.2.0 | Write config.toml (UI edits) | The write-only counterpart to tomllib; tomllib is read-only by design, so tomli-w handles config saves from the web UI; simple, focused, no extra surface area |

JSON is an alternative but lacks comment support — users will want to annotate their config (e.g., `# searches per cycle`). YAML adds indentation-sensitivity risk. TOML is the right call.

### State Persistence

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| JSON files | stdlib | Round-robin position + search history log | No database needed for this scope. Persist state as a JSON file in the Docker volume (same directory as config.toml). Round-robin position = one integer. History = a bounded list of log entries. SQLite would be overkill and adds a migration story. |

This is explicitly NOT a database project. The state is: (1) which item index to search next, per app, and (2) a rolling log of recent searches. Both fit in a single JSON file with atomic write (write to `.tmp` then `os.replace`).

### CSS Styling

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Tailwind CSS v4 (pytailwindcss) | pytailwindcss 0.3.0 / Tailwind 4.x | Utility CSS for the status UI | pytailwindcss provides the standalone Tailwind CLI installable via pip — no Node.js in the container; run `tailwindcss` in a Docker build step to produce a single compiled CSS file; output is static and served from `/static/`; matches VolvLog approach |

Alternative: Tailwind CDN Play script (`@tailwindcss/browser@4`). This works with zero build step but is explicitly "for development only" per Tailwind's own docs — not recommended for production. Use pytailwindcss in the Docker build stage instead.

Alternative: Plain CSS. Valid for a tool this small. Use Tailwind because user has prior experience with it (VolvLog uses Tailwind v4) and it eliminates hand-rolling responsive layout.

### Development Tools

| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| pytest | latest | Test runner | Standard Python testing |
| pytest-asyncio | 1.3.0 | Async test support | Required for testing async FastAPI routes and the async scheduler interactions; v1.0+ removed `event_loop` fixture — use `@pytest.mark.anyio` pattern |
| httpx (AsyncClient) | 0.28.1 | Test client for FastAPI | FastAPI's `TestClient` wraps httpx; use `AsyncClient` with `ASGITransport` for async tests |
| ruff | latest | Linter + formatter | Replaces flake8 + black; single tool, fast |

## Radarr/Sonarr API Reference

This is the source-of-truth for what we call. Verified against OpenAPI specs.

### Radarr v3 Endpoints (httpx calls)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /api/v3/wanted/missing` | GET | Fetch missing movies; params: `page`, `pageSize`, `monitored=true` |
| `GET /api/v3/wanted/cutoff` | GET | Fetch cutoff-unmet movies; params: `page`, `pageSize`, `monitored=true` |
| `POST /api/v3/command` | POST | Trigger search; body: `{"name": "MoviesSearch", "movieIds": [id]}` |
| `POST /api/v3/command` | POST | Bulk missing search: `{"name": "MissingMoviesSearch"}` |
| `POST /api/v3/command` | POST | Bulk cutoff search: `{"name": "CutOffUnmetMoviesSearch", "filterKey": "monitored", "filterValue": "true"}` |

### Sonarr v3 Endpoints (httpx calls)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /api/v3/wanted/missing` | GET | Fetch missing episodes; params: `page`, `pageSize`, `monitored=true` |
| `GET /api/v3/wanted/cutoff` | GET | Fetch cutoff-unmet episodes; params: `page`, `pageSize`, `monitored=true` |
| `POST /api/v3/command` | POST | Season search: `{"name": "SeasonSearch", "seriesId": id, "seasonNumber": n}` |
| `POST /api/v3/command` | POST | Episode search: `{"name": "EpisodeSearch", "episodeIds": [id]}` |

Note: Sonarr searches at the season level, not show level — this aligns with the project requirement ("Sonarr searches at season level, not entire show"). Episodes share a `seasonNumber` and `seriesId` which can be extracted from the wanted/missing response. Group episodes by `(seriesId, seasonNumber)` before triggering commands.

Note: Sonarr also has a v5 API but v3 remains fully supported and is what the installed base uses. Use v3 unless there's a specific reason to migrate.

## Installation

```bash
# Core runtime
pip install "fastapi[standard]"  # includes uvicorn, jinja2, python-multipart
pip install httpx
pip install APScheduler==3.11.2
pip install pydantic-settings==2.13.1
pip install tomli-w==1.2.0

# CSS build (in Docker build stage only)
pip install pytailwindcss==0.3.0

# Dev
pip install pytest pytest-asyncio==1.3.0 ruff
```

```dockerfile
# Recommended Dockerfile pattern (multi-stage for CSS)
FROM python:3.13-slim AS builder
RUN pip install pytailwindcss
COPY src/static/input.css src/static/input.css
COPY src/templates src/templates
RUN tailwindcss -i src/static/input.css -o src/static/style.css --minify

FROM python:3.13-slim
COPY --from=builder src/static/style.css /app/static/style.css
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ /app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Web framework | FastAPI | Flask (what Huntarr uses) | Flask is synchronous; async scheduler + sync HTTP server requires threading workarounds; FastAPI's async model eliminates this entirely |
| Web framework | FastAPI | Starlette (bare) | FastAPI is built on Starlette; adds routing ergonomics, OpenAPI docs, and type validation for free; no reason to drop down |
| Scheduler | APScheduler 3.x | APScheduler 4.x | v4 is alpha (4.0.0a6); completely new API; not production-ready as of Feb 2026 |
| Scheduler | APScheduler | asyncio.create_task + sleep loop | Viable for simple intervals but no pause/resume, no missed-fire handling, harder to test |
| HTTP client | httpx | aiohttp | httpx has cleaner API, built-in timeout config, and is already a FastAPI/Starlette ecosystem choice; aiohttp has more deps |
| HTTP client | httpx | arr wrapper libs (pyarr, radarr-py) | Wrapper libs have incomplete endpoint coverage, version lag, and abstract away the API behavior you need to reason about |
| Config format | TOML (tomllib + tomli-w) | JSON | JSON has no comment support; users editing config in a volume mount will want comments |
| Config format | TOML | YAML | YAML's indentation-sensitivity is a user error trap for non-developers |
| Config format | TOML | pydantic-settings (.env) | .env files suit 12-factor apps with many environment variables; a single structured config file with multiple nested sections (radarr, sonarr, schedule) maps better to TOML |
| State storage | JSON file | SQLite | SQLite is correct for relational data with queries; round-robin index + bounded log is not relational data; JSON file is simpler, has no migration story |
| State storage | JSON file | Redis | External dependency; massively over-engineered for persisting one integer and a list |
| CSS | pytailwindcss (build step) | Tailwind CDN browser script | CDN Play is explicitly "not for production" per Tailwind docs; adds runtime CSS parsing overhead |
| CSS | Tailwind v4 | Plain CSS | Valid choice but Tailwind gives responsive utilities that would require manual work |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `requests` library | Synchronous; blocks the asyncio event loop during API calls to Radarr/Sonarr; causes scheduler drift and freezes htmx polling | `httpx.AsyncClient` |
| APScheduler v4 | Alpha software (4.0.0a6), completely redesigned API, not production-ready | `APScheduler==3.11.2` |
| Third-party arr client libraries | Version lag, incomplete coverage, add abstraction layer that masks API errors; the arr v3 REST APIs are simple enough to call directly | Raw `httpx` calls |
| SQLite / any database | Overkill for persisting a round-robin index and a log list; adds schema migrations, connection management, file locking complexity | JSON state file with atomic writes |
| `@app.on_event("startup")` / `@app.on_event("shutdown")` | Deprecated in FastAPI; will be removed | `@asynccontextmanager` lifespan function |
| Gunicorn | Multi-process; APScheduler `AsyncIOScheduler` must run in a single process to avoid multiple scheduler instances triggering duplicate searches | `uvicorn` directly |
| Tailwind CDN browser script (`@tailwindcss/browser`) | Documented as "not for production"; parses CSS at runtime in the browser | `pytailwindcss` in Docker build stage |

## Version Compatibility

| Package | Compatible With | Notes |
|---------|----------------|-------|
| FastAPI 0.132.0 | Python 3.10+ | Requires 3.10 minimum; use 3.13-slim Docker image |
| Uvicorn 0.41.0 | Python 3.10+ | Dropped Python 3.9 in 0.40.0 (Dec 2025) |
| APScheduler 3.11.2 | Python 3.8+ | v3.x asyncio scheduler works with Python 3.13 |
| pytest-asyncio 1.3.0 | Python 3.10+ | v1.0+ removed `event_loop` fixture; use `anyio` markers |
| pytailwindcss 0.3.0 | Python 3.11+ | Build-time only; not in production image |
| httpx 0.28.1 | Python 3.8+ | No compatibility issues; 1.0 dev versions exist but not stable |
| tomli-w 1.2.0 | Python 3.8+ | Pairs with stdlib `tomllib` (Python 3.11+); for Python <3.11 use `tomli` backport |

## Sources

- FastAPI 0.132.0 — verified at https://pypi.org/project/fastapi/ (2026-02-23)
- Uvicorn 0.41.0 — verified at https://pypi.org/project/uvicorn/ (2026-02-23)
- APScheduler 3.11.2 stable, v4 alpha only — verified at https://pypi.org/project/APScheduler/ (2026-02-23)
- httpx 0.28.1 — verified at https://pypi.org/project/httpx/ (2026-02-23)
- pydantic-settings 2.13.1 — verified at https://pypi.org/project/pydantic-settings/ (2026-02-23)
- tomli-w 1.2.0 — verified at https://pypi.org/project/tomli-w/ (2026-02-23)
- pytest-asyncio 1.3.0 — verified at https://pypi.org/project/pytest-asyncio/ (2026-02-23)
- pytailwindcss 0.3.0 — verified at https://pypi.org/project/pytailwindcss/ (2026-02-23)
- htmx 2.0.7 (latest stable 2.x) — verified at https://github.com/bigskysoftware/htmx/releases
- Radarr API endpoints — verified against https://raw.githubusercontent.com/Radarr/Radarr/develop/src/Radarr.Api.V3/openapi.json
- Sonarr API — https://sonarr.tv/docs/api/
- FastAPI Docker guidance — https://fastapi.tiangolo.com/deployment/docker/ (MEDIUM confidence — official docs)
- APScheduler + FastAPI lifespan pattern — https://www.nashruddinamin.com/blog/running-scheduled-jobs-in-fastapi (MEDIUM confidence — verified against FastAPI lifespan docs)
- Huntarr architecture analysis — https://deepwiki.com/plexguide/Huntarr.io/1-introduction-to-huntarr (MEDIUM confidence — third-party wiki analysis)
- Tailwind CDN production caveat — https://tailwindcss.com/docs/installation/play-cdn (HIGH confidence — official docs)

---
*Stack research for: Triggarr — Python/FastAPI Radarr/Sonarr search automation tool*
*Researched: 2026-02-23*
