# Technology Stack

**Project:** Triggarr v2.3 -- Multi-Instance & Tag Filtering
**Researched:** 2026-03-09

## Core Finding: Zero New Dependencies

No new libraries are needed. Multi-instance support and tag-based filtering are achievable entirely with the existing stack plus refactoring of config, state, database schema, and client management. This continues the v2.0 pattern of "zero new dependencies."

## Existing Stack (Unchanged)

| Technology | Version | Purpose | Status for v2.3 |
|------------|---------|---------|------------------|
| Python | 3.13 | Runtime | No change |
| FastAPI | current | Web framework | No change |
| httpx | current | Async HTTP client | No change -- one client per instance |
| Pydantic | current | Config/validation | No change -- models extended |
| pydantic-settings[toml] | current | TOML config loading | No change -- config structure changes |
| APScheduler 3.x | >=3.11,<4 | Job scheduling | No change -- one job per instance |
| aiosqlite | current | Async SQLite | No change -- schema migration |
| Jinja2 | current | Templates | No change -- templates updated |
| htmx | vendored | Dynamic UI | No change |
| Tailwind CSS v4 | via pytailwindcss | Styling | No change |
| loguru | current | Logging | No change |
| tomli-w | current | TOML writing | No change -- config save |
| ruff | current | Linting | No change |

## New Capabilities from Existing Stack

### 1. Multi-Instance Config (pydantic + pydantic-settings + tomli-w)

**What changes:** The flat `[radarr]` / `[sonarr]` TOML sections become lists of instance tables.

**TOML structure (TOML array of tables):**
```toml
[[radarr]]
name = "radarr-4k"
url = "http://radarr-4k:7878"
api_key = "abc123"
enabled = true
search_interval = 30
search_missing_count = 5
search_cutoff_count = 5
tag_missing = ""           # empty = search all monitored missing
tag_cutoff = ""            # empty = search all monitored cutoff

[[radarr]]
name = "radarr-hd"
url = "http://radarr-hd:7878"
api_key = "def456"
enabled = true
tag_missing = "triggarr-missing"
tag_cutoff = "triggarr-upgrade"

[[sonarr]]
name = "sonarr-main"
url = "http://sonarr:8989"
api_key = "ghi789"
enabled = true
```

**Why `[[radarr]]` array-of-tables:** TOML natively supports this via `[[section]]` syntax. pydantic-settings can load this as `list[InstanceConfig]`. No custom parsing needed. tomli-w can write it back. This is the cleanest approach.

**Backward compatibility:** Single-instance `[radarr]` (table) and `[[radarr]]` (array-of-tables) are different TOML types. A migration path is needed: detect old format on load, convert to list-of-one internally, and optionally rewrite the file. Pydantic's `model_validator` can handle this.

**Confidence:** HIGH -- TOML array-of-tables is well-specified, pydantic handles `list[Model]` natively.

### 2. Tag-Based Filtering (httpx -- existing API calls)

**How Radarr/Sonarr tags work (verified via API docs and SDK source):**

- **Tag object:** `{id: int, label: string}` -- e.g., `{id: 3, label: "triggarr-missing"}`
- **Tag endpoint:** `GET /api/v3/tag` returns all tags as `[{id, label}]`
- **Movie object (Radarr):** Has `tags: int[]` field -- array of tag IDs. Present in `wanted/missing` and `wanted/cutoff` responses.
- **Series object (Sonarr):** Has `tags: int[]` field on the **series** object, NOT on episodes. The existing `includeSeries=true` parameter in Sonarr's `wanted/missing` already returns the series object nested in each episode, so tags are accessible at `episode["series"]["tags"]`.
- **Tag label validation:** Radarr/Sonarr enforce `[a-z0-9-]` only for tag labels (no spaces, uppercase, or special chars).

**Filtering approach -- client-side, not server-side:**
The wanted/missing and wanted/cutoff endpoints do NOT support server-side tag filtering. Filtering must happen client-side:

1. At startup (or periodically), call `GET /api/v3/tag` to resolve tag label to tag ID
2. After fetching wanted items, filter: keep only items where `tags` array contains the resolved tag ID
3. If tag label not found on the instance, log a warning and skip filtering (search all)

**No new library needed.** This is pure Python list filtering on the existing API response data that Triggarr already fetches.

**Confidence:** HIGH -- verified via Go SDK (`golift.io/starr`) type definitions showing `Series.Tags` as `[]int` and Episode having no tags field. Pyarr SDK confirms `get_tag()` / `create_tag()` methods. Radarr Go SDK confirms `Movie.Tags` as `[]int`.

### 3. Multi-Instance SQLite Schema (aiosqlite -- existing migration system)

**Current schema (single instance):**
```sql
search_history (
    id, timestamp, app, queue_type, item_name,
    outcome, detail, item_id, season_number, missing_count, resolved_at
)
lifetime_stats (
    app PRIMARY KEY, movies_found, movies_updated,
    episodes_found, episodes_updated, last_reset_at
)
```

**Problem:** The `app` column stores "Radarr" or "Sonarr" -- no instance discrimination. The `lifetime_stats` table uses `app` as primary key, so only one row per app type.

**Required migration (v6):**

```sql
-- Add instance_id to search_history for per-instance filtering
ALTER TABLE search_history ADD COLUMN instance_id TEXT DEFAULT NULL;

-- Create index for per-instance queries
CREATE INDEX idx_search_history_instance ON search_history(instance_id);

-- Recreate lifetime_stats with composite key (app + instance_id)
-- SQLite doesn't support ALTER TABLE to change PRIMARY KEY, so:
CREATE TABLE lifetime_stats_v2 (
    app TEXT NOT NULL,
    instance_id TEXT NOT NULL,
    movies_found INTEGER NOT NULL DEFAULT 0,
    movies_updated INTEGER NOT NULL DEFAULT 0,
    episodes_found INTEGER NOT NULL DEFAULT 0,
    episodes_updated INTEGER NOT NULL DEFAULT 0,
    last_reset_at TEXT NOT NULL,
    PRIMARY KEY (app, instance_id)
);
-- Migrate existing rows with default instance_id
INSERT INTO lifetime_stats_v2
    SELECT app, 'default', movies_found, movies_updated,
           episodes_found, episodes_updated, last_reset_at
    FROM lifetime_stats;
DROP TABLE lifetime_stats;
ALTER TABLE lifetime_stats_v2 RENAME TO lifetime_stats;
```

**`instance_id` value:** Use the user-provided `name` field from config (e.g., "radarr-4k"). This is human-readable and stable across restarts. Enforce uniqueness per app type in config validation.

**Backward compat:** Existing rows get `instance_id = NULL` or a default value. Queries without instance filter continue to work (dashboard shows aggregate or per-instance based on UI selection).

**Confidence:** HIGH -- the existing migration system (v1-v5) handles this pattern well. `ALTER TABLE ADD COLUMN` is safe in SQLite.

### 4. Multi-Instance State (JSON state file)

**Current state structure:**
```json
{
    "radarr": {"missing_cursor": 0, "cutoff_cursor": 0, ...},
    "sonarr": {"missing_cursor": 0, "cutoff_cursor": 0, ...}
}
```

**Required change:** State must be keyed by instance ID, not app type.

```json
{
    "instances": {
        "radarr-4k": {"missing_cursor": 0, "cutoff_cursor": 0, "app_type": "radarr", ...},
        "radarr-hd": {"missing_cursor": 0, "cutoff_cursor": 0, "app_type": "radarr", ...},
        "sonarr-main": {"missing_cursor": 0, "cutoff_cursor": 0, "app_type": "sonarr", ...}
    }
}
```

**Migration:** The existing `_merge_defaults` pattern handles missing keys gracefully. Detect old format (has "radarr"/"sonarr" top-level keys without "instances"), migrate to new format with auto-generated instance names.

**Confidence:** HIGH -- pure JSON restructuring, existing atomic write pattern preserved.

### 5. Multi-Instance Scheduling (APScheduler 3.x)

**Current:** Two jobs: `radarr_search` and `sonarr_search`.

**Required change:** One job per instance, keyed by instance ID:
```python
scheduler.add_job(job_fn, "interval", minutes=interval, id=f"{instance_id}_search")
```

**No APScheduler changes needed.** The scheduler already supports arbitrary job IDs and multiple interval jobs. Each instance gets its own `make_search_job` closure reading its own client/state.

**Confidence:** HIGH -- APScheduler 3.x handles this natively.

### 6. Multi-Instance HTTP Clients (httpx)

**Current:** One `RadarrClient` and one `SonarrClient` stored on `app.state`.

**Required change:** Dictionary of clients keyed by instance ID:
```python
app.state.clients: dict[str, ArrClient] = {
    "radarr-4k": RadarrClient(...),
    "radarr-hd": RadarrClient(...),
    "sonarr-main": SonarrClient(...),
}
```

Each client needs a `get_tags()` method added to the base `ArrClient`:
```python
async def get_tags(self) -> list[dict[str, Any]]:
    """Fetch all tags from the *arr instance."""
    response = await self.get("/api/v3/tag")
    return response.json()
```

**Tag resolution cache:** Store resolved tag label -> ID mapping per instance at startup and refresh on config reload. This avoids calling `/api/v3/tag` on every search cycle.

**Confidence:** HIGH -- trivial httpx addition.

## What NOT to Add

| Library | Why Not |
|---------|---------|
| SQLAlchemy / SQLModel | Overkill -- aiosqlite with raw SQL is already working well, migration system is proven |
| Redis | Single-user local tool, no shared state needed |
| Celery / dramatiq | APScheduler handles interval jobs fine for this use case |
| pydantic[multi] or similar | pydantic already handles `list[Model]` natively |
| toml (stdlib) | Already using tomllib (stdlib) for reading, tomli-w for writing |
| Any ORM | Adds complexity for ~6 queries total |

## Alternatives Considered

| Decision | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Instance identification | User-provided `name` field | Auto-generated UUID | Names are human-readable in UI and logs |
| Config format | TOML `[[array]]` of tables | Nested `[radarr.instance-name]` | Array-of-tables is cleaner, order-preserving, standard TOML |
| Tag resolution | At startup + cache | On every cycle | Wasteful -- tags rarely change; refresh on config reload is sufficient |
| Tag filtering location | After fetch, before monitored filter | Server-side API param | *arr APIs don't support server-side tag filtering on wanted endpoints |
| State key | Instance name string | Numeric index | Name is stable if user reorders instances in config |
| DB instance column | TEXT `instance_id` | INTEGER foreign key to instances table | No instances table needed; name string is sufficient and self-documenting |

## Radarr/Sonarr Tag API Reference

### Endpoints (both apps, identical)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v3/tag` | GET | List all tags -> `[{id: int, label: string}]` |
| `/api/v3/tag/{id}` | GET | Get single tag by ID |
| `/api/v3/tag` | POST | Create tag -> `{label: string}` |
| `/api/v3/tag/{id}` | PUT | Update tag |
| `/api/v3/tag/{id}` | DELETE | Delete tag |

### Tag Fields on Media Objects

| App | Object | Field | Type | Present in wanted/missing? |
|-----|--------|-------|------|---------------------------|
| Radarr | Movie | `tags` | `int[]` | YES -- movie objects in wanted/missing include tags |
| Sonarr | Series | `tags` | `int[]` | YES -- via `includeSeries=true` (already used), accessible at `episode["series"]["tags"]` |
| Sonarr | Episode | n/a | n/a | NO -- episodes do not have tags, only series do |

### Tag Label Constraints

- Radarr: `[a-z0-9-]` only (lowercase, digits, hyphens)
- Sonarr: Same pattern (shared Servarr codebase)

### Filtering Logic (Pseudocode)

```python
# At startup or config reload:
tags = await client.get_tags()  # GET /api/v3/tag
tag_map = {t["label"]: t["id"] for t in tags}
missing_tag_id = tag_map.get(config.tag_missing)  # e.g., "triggarr-missing" -> 3

# During search cycle:
items = await client.get_wanted_missing()
if missing_tag_id is not None:
    # Radarr: filter on movie["tags"]
    items = [m for m in items if missing_tag_id in m.get("tags", [])]
    # Sonarr: filter on episode["series"]["tags"]
    items = [e for e in items if missing_tag_id in e.get("series", {}).get("tags", [])]
# If no tag configured or tag not found on instance: search all (existing behavior)
```

## Installation

No changes to `pyproject.toml` dependencies:

```bash
# Existing (unchanged)
uv sync --extra dev
```

## Sources

- [Radarr API Docs (Swagger)](https://radarr.video/docs/api/) -- OpenAPI spec at `Radarr.Api.V3/openapi.json`
- [Radarr REST API - DeepWiki](https://deepwiki.com/radarr/radarr/4.1-rest-api) -- architectural overview
- [Sonarr API Docs](https://sonarr.tv/docs/api/) -- OpenAPI spec reference
- [golift.io/starr/sonarr Go SDK](https://pkg.go.dev/golift.io/starr/sonarr) -- Series.Tags typed as `[]int`, Episode has no tags field (HIGH confidence)
- [github.com/SkYNewZ/radarr Go SDK](https://pkg.go.dev/github.com/SkYNewZ/radarr) -- Movie.Tags typed as `[]int` (HIGH confidence)
- [pyarr SonarrAPI docs](https://docs.totaldebug.uk/pyarr/modules/sonarr.html) -- `get_tag()`, `create_tag()` method signatures (MEDIUM confidence)
- [ArrAPI documentation](https://arrapi.kometa.wiki/en/latest/radarr.html) -- tags as `Optional[List[Union[str, int, Tag]]]` in wrapper (MEDIUM confidence)
- [Radarr tag validation issue](https://github.com/seerr-team/seerr/issues/2317) -- tag label `[a-z0-9-]` constraint (MEDIUM confidence)
