# External Integrations

**Analysis Date:** 2026-05-25

## APIs & External Services

**Radarr API:**
- Service: Radarr (movie PVR)
- What it's used for: Fetch wanted/missing and cutoff movies; trigger movie searches; retrieve grab history for tracking
- SDK/Client: Custom async client `triggarr.clients.radarr.RadarrClient`
- Auth: X-Api-Key header (from config `radarr.[instance].api_key` as SecretStr)
- Endpoints:
  - `GET /api/v3/wanted/missing` - Paginated list of wanted but missing movies
  - `GET /api/v3/wanted/cutoff` - Movies that don't meet quality cutoff
  - `GET /api/v3/movie` - Library statistics (page size 1 to fetch total count)
  - `GET /api/v3/history/movie?movieId={id}&eventType=grabbed` - Grab history for a movie
  - `POST /api/v3/command` - Trigger MoviesSearch command with movie IDs

**Sonarr API:**
- Service: Sonarr (TV/episode PVR)
- What it's used for: Fetch wanted/missing and cutoff episodes; trigger episode searches; retrieve grab history; detect Sonarr v3 vs v4
- SDK/Client: Custom async client `triggarr.clients.sonarr.SonarrClient`
- Auth: X-Api-Key header (from config `sonarr.[instance].api_key` as SecretStr)
- Endpoints:
  - `GET /api/v3/wanted/missing?includeSeries=true` - Wanted episodes with series context
  - `GET /api/v3/wanted/cutoff?includeSeries=true` - Episodes below quality cutoff
  - `GET /api/v3/episode?episodeId={id}` - Episode details for filtering
  - `GET /api/v3/series` - Library stats (pagination to count total episodes)
  - `GET /api/v3/history/episode?episodeId={id}&eventType=grabbed` - Grab history
  - `POST /api/v3/command` - Trigger SeriesSearch command with season IDs
  - `GET /api/v3/system/status` - Version detection (v3 vs v4)

**Lidarr API:**
- Service: Lidarr (music PVR)
- What it's used for: Fetch wanted/missing and cutoff albums; trigger album searches; retrieve grab history
- SDK/Client: Custom async client `triggarr.clients.lidarr.LidarrClient`
- Auth: X-Api-Key header (from config `lidarr.[instance].api_key` as SecretStr)
- Endpoints:
  - `GET /api/v1/wanted/missing` - Wanted but missing albums
  - `GET /api/v1/wanted/cutoff` - Albums below quality cutoff
  - `GET /api/v1/album` - Library statistics
  - `GET /api/v1/history/album?albumId={id}&eventType=grabbed` - Grab history
  - `POST /api/v1/command` - Trigger AlbumSearch command with album IDs

**GitHub API:**
- Service: GitHub Releases API
- What it's used for: Check for available updates (once at startup, then every 24h via APScheduler)
- Endpoint: `GET https://api.github.com/repos/thejuran/triggarr/releases/latest`
- Headers: `Accept: application/vnd.github.v3+json`
- Logic: Version comparison with pre-release filtering (skips -dev, -rc, -alpha, -beta tags)
- Implementation: `triggarr.update_check.check_for_update()` (silent failures logged at debug level)

## Data Storage

**Databases:**
- SQLite 3 (built-in, async via aiosqlite)
  - File: `/config/search_history.db` (created on first run)
  - Client: `aiosqlite.Connection` (async context manager)
  - Migrations: Versioned schema migrations (v0 → current) with backup-before-migrate
  - Tables: `search_history`, `lifetime_stats`, `schema_version`
  - Used for: Search execution history (date, queue type, app, instance, items found/updated), lifetime aggregate statistics per app/instance

**File Storage:**
- Local filesystem only (no cloud storage)
  - `/config/triggarr.toml` - Application configuration (atomic write-then-rename)
  - `/config/state.json` - Per-instance cursor positions and queue statistics (atomic write-then-rename)
  - `/config/.migrated` - Marker file after v2.2→v2.3 config migration
  - `/config/triggarr.toml.bak` - Backup of pre-migration v2.2 config (if migrated)

**Caching:**
- None - No external cache layer; httpx connection pooling provides in-process HTTP session pooling

## Authentication & Identity

**Auth Provider:**
- Custom (built-in to Triggarr)
  - Implementation: Form-based, Basic HTTP, or External (reverse proxy) authentication
  - Methods supported: `Forms` (username + bcrypt password), `Basic` (HTTP auth headers), `External` (trust X-Remote-User header), `Disabled` (no auth)
  - Default: `Forms` with empty username (triggers "setup required" mode)
  - Passwords: Hashed with bcrypt (12 rounds via `triggarr.auth.hash_password()`)
  - Sessions: Signed cookies with 30-day TTL using TimestampSigner + session_secret
  - API Key: Optional 32-character hex key generated via `secrets.token_hex(16)` for programmatic access

**Configuration Storage:**
- Stored in `[auth]` section of `/config/triggarr.toml`:
  - `method` - Auth method (Forms/Basic/External/Disabled)
  - `username` - Username for Forms auth (empty = setup mode)
  - `password_hash` - SecretStr bcrypt hash
  - `api_key` - SecretStr 32-char hex key
  - `session_secret` - SecretStr 64-char hex for cookie signing

## Monitoring & Observability

**Error Tracking:**
- None (no external service)

**Logs:**
- Approach: Loguru with custom redacting sink
  - Output: stderr (captured by container logs)
  - Format: `YYYY-MM-DD HH:MM:SS LEVEL     Message` (human-readable)
  - Redaction: All secrets (API keys from config) replaced with `[REDACTED]` in logs and tracebacks
  - Setup: `triggarr.logging.setup_logging(level, secrets=list)` called during startup
  - Log level: Configurable via `[general] log_level` in config (default "info")
  - Buffering: In-memory log buffer for recent messages (used in web UI `/logs` endpoint)

## CI/CD & Deployment

**Hosting:**
- Docker registry: ghcr.io/thejuran/triggarr
- Container image: Multi-stage (Tailwind CSS builder + production)
  - Base: `python:3.13-slim`
  - Port: 8484 (exposed)
  - Entry: `entrypoint.sh` (drops privileges to PUID/PGID)

**CI Pipeline:**
- GitHub Actions (.github/workflows/)
  - Builds and pushes Docker image to GHCR on release/tag
  - Runs pytest and ruff checks before merge

## Environment Configuration

**Required env vars:**
- `TRIGGARR_CONFIG_DIR` (optional, default `/config`) - Config directory path
- App instances are configured in `triggarr.toml`, not env vars

**Secrets location:**
- Stored in `/config/triggarr.toml` as SecretStr fields
- Never log or expose in responses (redacted by logging sink)
- API keys stored as `pydantic.SecretStr` to prevent accidental string repr exposure
- Called `.get_secret_value()` only at httpx client initialization time

**No environment variable secrets:**
- Unlike traditional 12-factor, Triggarr stores secrets in TOML (better for container unpacking scenario)
- Env vars used only for deployment configuration (paths, proxy settings)

## Webhooks & Callbacks

**Incoming:**
- None - Triggarr is pull-based (polls Radarr/Sonarr/Lidarr on a schedule, no webhooks to receive)

**Outgoing:**
- None - Triggarr does not send webhooks to external services
- API calls are one-way: GET (fetch queue), POST (trigger search command)

## HTTP Client Configuration

**httpx AsyncClient:**
- Timeout: Configurable per request via `request_timeout` in `[general]` config (default 30s)
- Retry logic: Single retry on HTTP error or connection error, 2s delay between attempts (in `triggarr.clients.base.ArrClient._request_with_retry()`)
- Connection pooling: Built-in to httpx (async connection reuse across search cycles)
- Headers: `X-Api-Key` for API authentication, `Content-Type: application/json` for POST requests
- User-Agent: Not explicitly set (defaults to httpx user agent)

## Multi-Instance & Configuration

**Multiple instances per app:**
- Support: Up to 5 instances per app type (radarr, sonarr, lidarr)
- Structure: Nested TOML with instance names as keys:
  ```toml
  [radarr.Default]
  url = "http://radarr:7878"
  api_key = "abc123..."
  enabled = true
  
  [radarr."4K Radarr"]
  url = "http://radarr-4k:7878"
  api_key = "def456..."
  enabled = true
  ```
- Per-instance settings: URL, API key, search intervals, search counts, tag filters
- State isolation: Each instance maintains independent cursors and statistics in `state.json` and `search_history.db`

---

*Integration audit: 2026-05-25*
