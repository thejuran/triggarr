# External Integrations

**Analysis Date:** 2026-06-01

## APIs & External Services

**Radarr:**
- Service: Radarr movie/media server
  - SDK/Client: `triggarr.clients.radarr:RadarrClient` (async httpx wrapper)
  - Auth: Via `api_key` SecretStr in config (injected into `X-Api-Key` header)
  - Endpoints:
    - `GET /api/v3/system/status` - Connection validation + version detection
    - `GET /api/v3/wanted/missing` - Fetch wanted/missing movies (paginated)
    - `GET /api/v3/wanted/cutoff` - Fetch movies below quality cutoff (paginated)
    - `GET /api/v3/movie` - Library count (single-page lightweight query)
    - `GET /api/v3/history/movie` - Per-movie grab history (event-filtered)
    - `GET /api/v3/tag` - Tag list for filtering
    - `POST /api/v3/command` - Trigger MoviesSearch command
  - Location: `triggarr/clients/radarr.py`

**Sonarr:**
- Service: Sonarr series/TV server
  - SDK/Client: `triggarr.clients.sonarr:SonarrClient` (async httpx wrapper)
  - Auth: Via `api_key` SecretStr in config (injected into `X-Api-Key` header)
  - Endpoints:
    - `GET /api/v3/system/status` - Connection validation + version detection (v3/v4)
    - `GET /api/v3/wanted/missing` - Fetch wanted/missing episodes (paginated, `includeSeries=true`)
    - `GET /api/v3/wanted/cutoff` - Fetch episodes below quality cutoff (paginated, `includeSeries=true`)
    - `GET /api/v3/series` - Non-paginated series list for episode count
    - `GET /api/v3/history/series` - Per-series grab history (event-filtered)
    - `GET /api/v3/tag` - Tag list for filtering
    - `POST /api/v3/command` - Trigger SeasonSearch command
  - Location: `triggarr/clients/sonarr.py`
  - Special: Detects API version (v3 vs v4) and logs version info

**Lidarr:**
- Service: Lidarr music server
  - SDK/Client: `triggarr.clients.lidarr:LidarrClient` (async httpx wrapper, stub implementation)
  - Auth: Via `api_key` SecretStr in config (injected into `X-Api-Key` header)
  - Location: `triggarr/clients/lidarr.py`
  - Note: Client exists but search/tracking not yet fully implemented

**GitHub:**
- Service: Release checks for Triggarr updates
  - API: `https://api.github.com/repos/thejuran/triggarr/releases/latest`
  - HTTP Client: `httpx.AsyncClient(timeout=10.0)`
  - Header: `Accept: application/vnd.github.v3+json`
  - Response: Extracts `tag_name`, `html_url`, `prerelease` flag
  - Failures: Silent (debug-logged only), non-blocking
  - Runs: Once at startup, then every 24h via APScheduler
  - Location: `triggarr/update_check.py:check_for_update()`

## Data Storage

**Databases:**
- SQLite (local file-based)
  - Connection: Async via `aiosqlite` (single long-lived connection per app lifespan)
  - File: `{TRIGGARR_CONFIG_DIR}/triggarr.db`
  - Migrations: Versioned schema evolution with backup-before-migrate
  - Schema: search_history, search_state, schema_version tables
  - Client: `aiosqlite.Connection` (no ORM — raw SQL + Pydantic models)
  - Location: `triggarr/db.py`
  - State: Search tracking, grab deduplication, history retention (capped at `max_history_rows`)

**File Storage:**
- Local filesystem only
  - Config: `{TRIGGARR_CONFIG_DIR}/triggarr.toml` (TOML format, atomic write-then-rename)
  - State: `{TRIGGARR_CONFIG_DIR}/triggarr.db` (SQLite)
  - Backups: `triggarr.toml.bak` (created during v2.2→v2.3 migration)
  - Migration marker: `.migrated` file (signals web UI banner)

**Caching:**
- None (stateless HTTP layer, search state in SQLite)

## Authentication & Identity

**Auth Provider:**
- Custom (built-in to Triggarr)
  - Method: Forms (web UI login), Basic (HTTP Basic Auth), External (delegated), Disabled (public)
  - Implementation: `triggarr.auth` module
    - Password hashing: bcrypt (12 rounds, 72-byte limit)
    - Session cookies: TimestampSigner (30-day max age)
    - API keys: 32-char hex (CSPRNG generated)
    - Session secrets: 64-char hex (CSPRNG generated)
  - Storage: Config file (`triggarr.toml`, `[auth]` section)
    - `username` - Login username (empty = needs setup)
    - `password_hash` - Bcrypt hash (SecretStr)
    - `api_key` - API key (SecretStr)
    - `session_secret` - Session signing secret (SecretStr)
  - Location: `triggarr/auth.py`, `triggarr/models/config.py:AuthConfig`

**Middleware Stack:**
- `AuthMiddleware` - Session/Basic/API key validation (runs last, closest to handler)
- `OriginCheckMiddleware` - CSRF token validation (X-Csrf-Token header)
- `SecurityHeadersMiddleware` - Response security headers (CSP, X-Frame-Options, etc.)

## Monitoring & Observability

**Error Tracking:**
- None (no external service integration)

**Logs:**
- Approach: Loguru with custom redacting sink
  - Format: `YYYY-MM-DD HH:mm:ss LEVEL message` (human-readable)
  - Secrets: All API keys and passwords redacted as `[REDACTED]` (including exception tracebacks)
  - Output: stderr by default
  - Verbosity: Configurable via `[general].log_level` (debug/info/warning/error)
  - In-memory buffer: LogEntry objects captured for web UI log viewer (capped, secrets pre-redacted)
  - Location: `triggarr/logging.py:setup_logging()`, `triggarr/log_buffer.py`

## CI/CD & Deployment

**Hosting:**
- Docker container (ghcr.io/thejuran/triggarr)
- No external CI/CD integration detected (GitHub Actions may be used externally, not in codebase)

**Container Registry:**
- GitHub Container Registry (ghcr.io/thejuran/triggarr)

## Environment Configuration

**Required env vars:**
- `TRIGGARR_CONFIG_DIR` (optional, default `/config`) - Config directory path
- `ROOT_PATH` (optional, default empty) - Reverse proxy prefix (for nested deployments)
- `TRUSTED_PROXY_IPS` (optional, default `127.0.0.1`) - Proxies to trust for X-Forwarded-* headers

**Secrets location:**
- TOML config file (managed through web UI)
  - `[radarr.Instance].api_key` - Radarr API key
  - `[sonarr.Instance].api_key` - Sonarr API key
  - `[lidarr.Instance].api_key` - Lidarr API key
  - `[auth].password_hash` - Bcrypt password hash
  - `[auth].api_key` - Triggarr API key
  - `[auth].session_secret` - Session signing secret
- SecretStr discipline: Keys are stored as `SecretStr` in memory, only exposed via `.get_secret_value()` at HTTP client init
- Never logged: Custom redacting sink masks all secrets from stdout/stderr + exception tracebacks

## Webhooks & Callbacks

**Incoming:**
- None (Triggarr pulls from Radarr/Sonarr, does not receive webhooks)

**Outgoing:**
- None (Triggarr triggers search commands via Radarr/Sonarr API, no outbound webhooks)

## HTTP Client Configuration

**httpx Settings:**
- Base client: `httpx.AsyncClient(base_url, headers, timeout)`
- Timeout: 30s default (configurable via `[general].request_timeout`)
- Headers: `X-Api-Key: {api_key}`, `Content-Type: application/json`
- Retry logic: Single retry on transient failures (2s backoff between attempts)
  - Catches: `httpx.HTTPStatusError`, `httpx.TransportError` (connection/timeout)
  - Logs: Debug on first failure, warning if retry also fails
- Response parsing: Pydantic validation (GrabEvent, SystemStatus, Tag, PaginatedResponse)
- Lifecycle: Context manager (`async with`) for resource cleanup

---

*Integration audit: 2026-06-01*
