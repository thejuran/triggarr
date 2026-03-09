# Phase 1: Foundation - Research

**Researched:** 2026-02-23
**Domain:** Python config/settings, httpx async HTTP clients, Radarr/Sonarr API integration
**Confidence:** HIGH

## Summary

Phase 1 builds the infrastructure layer for Fetcharr: a TOML configuration file parsed into Pydantic settings, a JSON state file with atomic writes, and httpx-based async API clients for Radarr and Sonarr. The tech choices are well-established Python patterns with mature libraries. The Radarr/Sonarr APIs follow identical conventions (`/api/v3/wanted/missing`, `/api/v3/wanted/cutoff`, `/api/v3/system/status`) with standard pagination, making a shared base client viable.

The main complexity is pagination exhaustion (fetching all pages of potentially large wanted lists) and the security invariant: API keys must live exclusively in the `X-Api-Key` header and never appear in any log line, URL, or HTTP response body. Loguru's filter mechanism and Pydantic's `SecretStr` type together enforce this at the framework level rather than relying on developer discipline.

**Primary recommendation:** Use `pydantic-settings[toml]` with `TomlConfigSettingsSource` for config parsing, `httpx.AsyncClient` with `base_url` and default `X-Api-Key` header per app, and `loguru` with a redaction filter that strips any value matching a configured API key from all log output.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Config lives at `/config/fetcharr.toml` -- single fixed path, Docker-friendly
- Flat TOML structure: `[general]` for global settings, `[radarr]` and `[sonarr]` sections for per-app connection config (url, api_key, enabled)
- When config file is missing on startup, generate a commented default config file and exit with a message telling the user to edit it
- Search-related settings (batch sizes, intervals) are not in Phase 1 config -- added in Phase 2 when the search engine is built
- If Radarr or Sonarr is unreachable on startup, log a warning and keep running -- don't exit
- Run with whatever apps are configured -- if user only has Radarr, Sonarr section can be empty/omitted
- Print a startup summary banner showing app name, version, connected apps, and key settings
- At least one app must be configured -- exit with error if both are missing/empty
- Human-readable log lines: `2026-02-23 14:30:00 INFO  Connected to Radarr at http://radarr:7878`
- Use loguru for logging
- Default log level: INFO; debug level available via `log_level = "debug"` in config
- API keys are NEVER logged -- not even partially masked. Complete absence from all log output.
- API call failures: retry once with short delay, then log and skip
- HTTP timeout: 30 seconds for all *arr API calls
- Runtime disconnects: warn and continue each cycle, reconnect automatically when app comes back
- State file uses atomic write (write-then-rename) to prevent corruption on crash

### Claude's Discretion
- Startup API key validation approach (full test call vs URL-only check)
- Pydantic model structure and validation details
- httpx client configuration (connection pooling, retry backoff timing)
- State file location within /config volume
- Exact startup banner format

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONN-01 | User can configure Radarr connection via URL + API key, validated on startup | Pydantic settings with `[radarr]` TOML section; httpx AsyncClient with `base_url` + `X-Api-Key` header; `/api/v3/system/status` for validation |
| CONN-02 | User can configure Sonarr connection via URL + API key, validated on startup | Same pattern as CONN-01; Sonarr uses identical `/api/v3/system/status` endpoint |
| SECR-01 | API keys are stored server-side only and never returned by any HTTP endpoint | Pydantic `SecretStr` for api_key fields; loguru redaction filter; keys only in `X-Api-Key` header, never in URLs; no HTTP endpoints in Phase 1 (established as invariant for Phase 3) |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| [pydantic](https://docs.pydantic.dev/) | 2.x (latest) | Data validation and settings models | Industry standard for Python config/validation; `SecretStr` type prevents accidental key exposure |
| [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | 2.x (latest) | TOML config file loading | Official Pydantic extension with built-in `TomlConfigSettingsSource` |
| [httpx](https://www.python-httpx.org/) | 0.28.x | Async HTTP client for *arr API calls | Modern async-native HTTP client; supports `base_url`, default headers, configurable timeouts |
| [loguru](https://loguru.readthedocs.io/) | 0.7.x | Logging | Zero-config sensible defaults, custom format strings, filter functions for redaction |
| [tomllib](https://docs.python.org/3/library/tomllib.html) | stdlib (3.11+) | TOML parsing (used by pydantic-settings internally) | Standard library since Python 3.11; no external dependency needed for reading |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tomli-w | 1.x | TOML writing | Only for generating the default config file on first run (tomllib is read-only) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pydantic-settings TOML | Raw tomllib + manual validation | Loses type safety, default values, SecretStr; more code to maintain |
| httpx | aiohttp | httpx has cleaner API, base_url support, built-in timeout objects; aiohttp is more mature but more verbose |
| loguru | stdlib logging | loguru is dramatically simpler for custom formats and filters; stdlib logging requires handler/formatter boilerplate |

**Installation:**
```bash
pip install "pydantic-settings[toml]" httpx loguru tomli-w
```

Note: `pydantic-settings[toml]` pulls in `pydantic`, `tomli` (backport, though stdlib `tomllib` is used on Python 3.11+). `tomli-w` is only needed for writing the default config template.

## Architecture Patterns

### Recommended Project Structure
```
fetcharr/
├── __init__.py          # Package root, __version__
├── __main__.py          # Entry point: python -m fetcharr
├── config.py            # Pydantic settings model, TOML loading, default generation
├── logging.py           # Loguru setup: format, level, redaction filter
├── state.py             # JSON state file: load, save (atomic write)
├── clients/
│   ├── __init__.py
│   ├── base.py          # Shared ArrClient base (httpx.AsyncClient wrapper)
│   ├── radarr.py        # RadarrClient: wanted/missing, wanted/cutoff, system/status
│   └── sonarr.py        # SonarrClient: wanted/missing, wanted/cutoff, system/status
└── models/
    ├── __init__.py
    ├── config.py         # Pydantic models for TOML sections
    └── arr.py            # Response models for *arr API data
```

### Pattern 1: Pydantic Settings with TOML Source
**What:** Single `Settings` class loads from `/config/fetcharr.toml` with `TomlConfigSettingsSource`
**When to use:** Config loading at startup
**Example:**
```python
# Source: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, TomlConfigSettingsSource

class ArrConfig(BaseModel):
    url: str = ""
    api_key: SecretStr = SecretStr("")
    enabled: bool = False

class GeneralConfig(BaseModel):
    log_level: str = "info"

class Settings(BaseSettings):
    general: GeneralConfig = GeneralConfig()
    radarr: ArrConfig = ArrConfig()
    sonarr: ArrConfig = ArrConfig()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (TomlConfigSettingsSource(settings_cls, toml_file="/config/fetcharr.toml"),)
```

### Pattern 2: httpx AsyncClient with Base URL and Default Headers
**What:** Long-lived `AsyncClient` per *arr app with `base_url` and `X-Api-Key` header baked in
**When to use:** All *arr API calls
**Example:**
```python
# Source: https://www.python-httpx.org/advanced/clients/
import httpx

class ArrClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Api-Key": api_key},
            timeout=httpx.Timeout(timeout),
        )

    async def get_paginated(self, path: str, page_size: int = 50) -> list[dict]:
        """Fetch all pages from a paginated *arr endpoint."""
        all_records = []
        page = 1
        while True:
            resp = await self._client.get(
                path,
                params={"page": page, "pageSize": page_size, "sortKey": "id"},
            )
            resp.raise_for_status()
            data = resp.json()
            all_records.extend(data["records"])
            if page * page_size >= data["totalRecords"]:
                break
            page += 1
        return all_records

    async def close(self):
        await self._client.aclose()
```

### Pattern 3: Loguru Redaction Filter
**What:** Filter function that strips API key values from all log output
**When to use:** Configured once at startup, applied to all sinks
**Example:**
```python
# Source: https://loguru.readthedocs.io/en/stable/api/logger.html
from loguru import logger
import sys

def create_redaction_filter(secrets: list[str]):
    """Create a filter that redacts secret values from log messages."""
    def redact(record):
        for secret in secrets:
            if secret and secret in record["message"]:
                record["message"] = record["message"].replace(secret, "[REDACTED]")
        return True
    return redact

def setup_logging(level: str, secrets: list[str]):
    logger.remove()  # Remove default handler (ID 0)
    logger.add(
        sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss} {level:<8} {message}",
        level=level.upper(),
        filter=create_redaction_filter(secrets),
        colorize=True,
    )
```

### Pattern 4: Atomic JSON State File Write
**What:** Write to temp file in same directory, then `os.replace()` for atomic swap
**When to use:** Every state file update (cursor positions, last-run times)
**Example:**
```python
# Source: https://docs.python.org/3/library/os.html#os.replace
import json
import os
import tempfile
from pathlib import Path

STATE_PATH = Path("/config/state.json")

def save_state(state: dict) -> None:
    """Atomically write state to disk."""
    parent = STATE_PATH.parent
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=parent, suffix=".tmp", delete=False
    ) as tmp:
        json.dump(state, tmp, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp.name, STATE_PATH)
```

### Anti-Patterns to Avoid
- **API key in URL query params:** Never use `?apikey=XXX` in URLs. Always use `X-Api-Key` header. The httpx `base_url` + `headers` pattern makes this natural.
- **Creating a new AsyncClient per request:** Kills connection pooling and TLS handshake reuse. Create one long-lived client per *arr app.
- **Partial key masking in logs:** `api_key=abc***xyz` still leaks information. The decision is complete absence, not masking.
- **Writing state file directly (no atomic swap):** A crash mid-write corrupts the file. Always write-then-rename.
- **Blocking I/O in async context:** Use `httpx.AsyncClient` (not `httpx.Client`) since the app will be async (FastAPI).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Config file parsing + validation | Custom TOML parser + manual type checking | `pydantic-settings[toml]` with `TomlConfigSettingsSource` | Handles type coercion, defaults, validation errors with clear messages |
| Secret redaction in logs | String replacement in every log call | Loguru filter function applied globally | Single point of enforcement; impossible to forget |
| HTTP client with retries | Custom retry loop around raw httpx calls | httpx with `raise_for_status()` + simple try/except retry wrapper | Keep retry logic in one place in the base client |
| Pagination exhaustion | Custom page-counting logic per endpoint | Shared `get_paginated()` method on base client | Both Radarr and Sonarr use identical pagination shape |
| Atomic file write | Manual file I/O with error handling | `tempfile.NamedTemporaryFile` + `os.replace()` | stdlib pattern; handles edge cases (same filesystem, atomic rename) |

**Key insight:** The *arr APIs (Radarr and Sonarr) share nearly identical endpoint patterns, pagination shapes, and authentication. A shared base client with app-specific subclasses avoids duplicating HTTP, pagination, and error handling logic.

## Common Pitfalls

### Pitfall 1: API Key Leaking into Exception Tracebacks
**What goes wrong:** An httpx request fails, and the traceback includes the full URL or headers containing the API key.
**Why it happens:** Default exception formatting includes request details. Loguru's `@logger.catch` or Python's default traceback printer will dump headers.
**How to avoid:** The redaction filter on loguru catches message-level leaks. For exception tracebacks, ensure `logger.exception()` is used (goes through the same sink/filter pipeline). Do NOT use `traceback.print_exc()` which bypasses loguru.
**Warning signs:** API keys appearing in Docker container logs.

### Pitfall 2: Pagination Off-by-One / Infinite Loop
**What goes wrong:** Pagination loop never terminates, or misses the last page of results.
**Why it happens:** Radarr/Sonarr use 1-indexed pages. If `totalRecords` is 0, the first request returns an empty `records` array but the loop might try to fetch page 2.
**How to avoid:** Check `len(records) == 0` OR `page * page_size >= totalRecords` as termination conditions. Handle `totalRecords: 0` as an immediate return.
**Warning signs:** API call counts growing unboundedly; log messages showing "fetched page 500 of..."

### Pitfall 3: Sonarr v4 Strict Content-Type Enforcement
**What goes wrong:** POST requests to Sonarr v4 fail with 415 Unsupported Media Type.
**Why it happens:** Sonarr v4 enforces `Content-Type: application/json` on POST requests more strictly than v3.
**How to avoid:** Always set `Content-Type: application/json` in default headers for the httpx client. httpx does this automatically when using `json=` parameter in `.post()`, but be explicit in default headers as a safety net.
**Warning signs:** Command POST requests returning 415 errors.

### Pitfall 4: Config File Missing on First Run
**What goes wrong:** App crashes with an unhelpful FileNotFoundError on first Docker run.
**Why it happens:** No config file exists yet on the mounted volume.
**How to avoid:** Check for config file existence before parsing. If missing, write a commented default template using `tomli-w` and exit with a helpful message. This is a locked user decision.
**Warning signs:** Users opening GitHub issues saying "it crashed on first run."

### Pitfall 5: Connection Validation Blocking Startup
**What goes wrong:** If Radarr/Sonarr is slow to start (common in Docker Compose), Fetcharr hangs or fails on startup validation.
**Why it happens:** The validation HTTP call blocks with a long timeout.
**How to avoid:** Use the 30-second timeout for validation calls. On failure, log a warning and continue -- don't exit. The user decided "warn and keep running."
**Warning signs:** Fetcharr container restarting in a loop because it exits before *arr is ready.

### Pitfall 6: SecretStr Serialization Gotcha
**What goes wrong:** `SecretStr` renders as `**********` when converted to string, but `.get_secret_value()` is needed to extract the actual key for API calls.
**Why it happens:** Pydantic's `SecretStr` deliberately hides the value in `__repr__`, `__str__`, and JSON serialization.
**How to avoid:** Call `.get_secret_value()` only where the key is needed (httpx client init). Everywhere else, the obfuscated form is what you want.
**Warning signs:** API calls failing with auth errors because the literal string `**********` was sent as the key.

## Code Examples

### Default Config File Generation
```python
# When /config/fetcharr.toml doesn't exist, write this and exit
DEFAULT_CONFIG = """\
# Fetcharr Configuration
# Edit this file and restart Fetcharr.

[general]
# Log level: debug, info, warning, error
log_level = "info"

[radarr]
# Radarr connection settings
url = ""           # e.g. "http://radarr:7878"
api_key = ""       # From Radarr > Settings > General > API Key
enabled = false

[sonarr]
# Sonarr connection settings
url = ""           # e.g. "http://sonarr:8989"
api_key = ""       # From Sonarr > Settings > General > API Key
enabled = false
"""
```

### Startup Validation Flow
```python
async def validate_connection(client: ArrClient, app_name: str) -> bool:
    """Validate *arr connection by calling /api/v3/system/status."""
    try:
        resp = await client.get("/api/v3/system/status")
        resp.raise_for_status()
        status = resp.json()
        version = status.get("version", "unknown")
        logger.info(f"Connected to {app_name} v{version}")
        return True
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.error(f"{app_name}: API key is invalid (401 Unauthorized)")
        else:
            logger.warning(f"{app_name}: HTTP {e.response.status_code} during connection check")
        return False
    except httpx.ConnectError:
        logger.warning(f"{app_name}: Connection refused at configured URL")
        return False
    except httpx.TimeoutException:
        logger.warning(f"{app_name}: Connection timed out (30s)")
        return False
```

### Radarr/Sonarr Paginated Wanted Fetching
```python
# Radarr: GET /api/v3/wanted/missing?page=1&pageSize=50&sortKey=id
# Radarr: GET /api/v3/wanted/cutoff?page=1&pageSize=50&sortKey=id
# Sonarr: GET /api/v3/wanted/missing?page=1&pageSize=50&sortKey=id&includeSeries=true
# Sonarr: GET /api/v3/wanted/cutoff?page=1&pageSize=50&sortKey=id&includeSeries=true

# Response shape (identical for both apps, both endpoints):
# {
#   "page": 1,
#   "pageSize": 50,
#   "sortKey": "id",
#   "sortDirection": "ascending",
#   "totalRecords": 142,
#   "records": [ ... ]
# }
```

### Startup Summary Banner
```python
def print_banner(version: str, settings: Settings):
    logger.info("=" * 50)
    logger.info(f"Fetcharr v{version}")
    logger.info(f"Log level: {settings.general.log_level}")
    if settings.radarr.enabled:
        logger.info(f"Radarr: {settings.radarr.url}")
    else:
        logger.info("Radarr: disabled")
    if settings.sonarr.enabled:
        logger.info(f"Sonarr: {settings.sonarr.url}")
    else:
        logger.info("Sonarr: disabled")
    logger.info("=" * 50)
```

## *arr API Reference

### Shared Conventions (Radarr and Sonarr)
- **Base path prefix:** `/api/v3/`
- **Authentication:** `X-Api-Key: <key>` header on every request
- **Pagination shape:** `{ page, pageSize, sortKey, sortDirection, totalRecords, records[] }`
- **Pages are 1-indexed** (first page is `page=1`)
- **Default pageSize:** 10 (override to 50 or higher for efficiency)
- **sortKey:** Use `"id"` for deterministic ordering

### Endpoints Used in Phase 1

| App | Endpoint | Method | Purpose | Key Params |
|-----|----------|--------|---------|------------|
| Both | `/api/v3/system/status` | GET | Validate connection + get version | None |
| Radarr | `/api/v3/wanted/missing` | GET | Movies without files | `page`, `pageSize`, `sortKey`, `sortDirection`, `monitored` |
| Radarr | `/api/v3/wanted/cutoff` | GET | Movies below quality cutoff | `page`, `pageSize`, `sortKey`, `sortDirection`, `monitored` |
| Sonarr | `/api/v3/wanted/missing` | GET | Episodes without files | `page`, `pageSize`, `sortKey`, `sortDirection`, `includeSeries` |
| Sonarr | `/api/v3/wanted/cutoff` | GET | Episodes below quality cutoff | `page`, `pageSize`, `sortKey`, `sortDirection`, `includeSeries` |

### Radarr `wanted/missing` Record Shape (key fields)
```json
{
  "id": 123,
  "title": "Movie Title",
  "year": 2024,
  "tmdbId": 456789,
  "monitored": true,
  "hasFile": false
}
```

### Sonarr `wanted/missing` Record Shape (key fields)
```json
{
  "id": 789,
  "seriesId": 12,
  "seasonNumber": 3,
  "episodeNumber": 5,
  "title": "Episode Title",
  "monitored": true,
  "hasFile": false,
  "series": { "title": "Show Name", "id": 12 }
}
```

Note: Sonarr records include `series` object when `includeSeries=true`. This is needed in Phase 2 for human-readable log messages and season-level deduplication.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `toml` PyPI package | `tomllib` stdlib (Python 3.11+) | Python 3.11 (Oct 2022) | No external dependency for TOML reading |
| `requests` for HTTP | `httpx` with async support | httpx 0.23+ (2022) | Native async, `base_url`, built-in timeout objects |
| Radarr: fetch all movies + client-side filter | `/api/v3/wanted/missing` dedicated endpoint | Radarr PR #10015 (May 2024) | Server-side filtering; no need to fetch entire library |
| pydantic v1 Settings | pydantic-settings v2 with TOML source | pydantic v2 (Jul 2023) | Separate package, built-in TOML support via extras |

**Deprecated/outdated:**
- `toml` PyPI package: Abandoned; use `tomllib` (stdlib) or `tomli` (backport)
- Radarr API v1/v2: Obsolete; current Radarr uses API v3 exclusively
- `pydantic[settings]` (v1 extra): Replaced by standalone `pydantic-settings` package in v2

## Open Questions

1. **Radarr `wanted/missing` availability on older versions**
   - What we know: The endpoint was added via PR #10015 (merged May 2024). Current Radarr versions have it.
   - What's unclear: Exact minimum Radarr version that includes this endpoint.
   - Recommendation: Use the endpoint. If a user reports 404, the startup validation step will catch it and log a clear error. Document minimum Radarr version once confirmed.

2. **Sonarr `wanted/cutoff` `monitored` parameter**
   - What we know: Sonarr's `wanted/missing` endpoint returns monitored episodes by default. The `monitored` query parameter exists on Radarr's endpoints.
   - What's unclear: Whether Sonarr's cutoff/missing endpoints accept a `monitored` filter parameter or always return only monitored items.
   - Recommendation: Default behavior (monitored-only) is what we want. Don't pass `monitored` param for Sonarr; if needed, filter client-side. Phase 2 filters unmonitored items regardless.

3. **Retry backoff timing (Claude's discretion)**
   - What we know: User wants "retry once with short delay."
   - Recommendation: 2-second delay before retry. Simple and predictable. No exponential backoff needed for a single retry.

## Sources

### Primary (HIGH confidence)
- [pydantic-settings TOML docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) - `TomlConfigSettingsSource` API, `settings_customise_sources` pattern, `SecretStr` usage
- [httpx official docs - Timeouts](https://www.python-httpx.org/advanced/timeouts/) - `httpx.Timeout` configuration, default 5s, per-request overrides
- [httpx official docs - Clients](https://www.python-httpx.org/advanced/clients/) - `AsyncClient` with `base_url`, default `headers`, connection pooling
- [httpx official docs - Resource Limits](https://www.python-httpx.org/advanced/resource-limits/) - Default pool limits (100 max connections, 20 keepalive)
- [loguru API docs](https://loguru.readthedocs.io/en/stable/api/logger.html) - `logger.remove()`, `logger.add()` with format/level/filter, `{time:YYYY-MM-DD HH:mm:ss}` format tokens
- [Python tomllib docs](https://docs.python.org/3/library/tomllib.html) - stdlib TOML parser, read-only, Python 3.11+
- [tomli-w PyPI](https://pypi.org/project/tomli-w/) - Write companion to tomllib
- [Python os.replace docs](https://docs.python.org/3/library/os.html#os.replace) - Atomic file rename, cross-platform

### Secondary (MEDIUM confidence)
- [Radarr API docs](https://radarr.video/docs/api/) + [Radarr GitHub issue #7704](https://github.com/Radarr/Radarr/issues/7704) - `/api/v3/wanted/missing` endpoint confirmed added via PR #10015
- [Radarr DeepWiki REST API](https://deepwiki.com/radarr/radarr/4.1-rest-api) - Endpoint paths, `X-Api-Key` authentication, `/api/v3/system/status` response shape
- [Huntarr DeepWiki Radarr Integration](https://deepwiki.com/plexguide/Huntarr.io/5.3-radarr-integration) - Confirms `/api/v3/wanted/missing` and `/api/v3/wanted/cutoff` paths used in production
- [Sonarr GitHub issue #4950](https://github.com/Sonarr/Sonarr/issues/4950) - `wanted/missing` default sortKey behavior
- [pyarr Sonarr source](https://docs.totaldebug.uk/pyarr/_modules/pyarr/sonarr.html) - `wanted/missing` endpoint path, pagination params (`page`, `pageSize`, `sortKey`, `sortDirection`, `includeSeries`)
- [pydantic-settings PyPI](https://pypi.org/project/pydantic-settings/) - `[toml]` extra dependency, latest release Feb 2026
- [Radarr MoviesSearch command](https://github.com/Radarr/Radarr/issues/3315) - `{"name": "MoviesSearch", "movieIds": [id]}` body format (Phase 2 reference)

### Tertiary (LOW confidence)
- Sonarr `wanted/cutoff` `monitored` parameter: Not explicitly confirmed in available docs; behavior inferred from Radarr's identical parameter and pyarr implementation patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are well-documented, widely used, and verified via official docs
- Architecture: HIGH - Patterns verified from official httpx/pydantic/loguru documentation; *arr API shapes confirmed from multiple client implementations
- Pitfalls: HIGH - Drawn from real GitHub issues (Sonarr v4 content-type, Radarr pagination) and established Python patterns (atomic write, SecretStr)

**Research date:** 2026-02-23
**Valid until:** 2026-03-23 (stable domain, mature libraries)
