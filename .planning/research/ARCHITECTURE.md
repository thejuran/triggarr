# Architecture Research: Multi-Instance & Tag Filtering

**Domain:** Search automation daemon -- multi-instance *arr integration
**Researched:** 2026-03-09
**Confidence:** HIGH (based on full codebase audit + API verification)

## Current Architecture (Baseline)

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Web Layer (htmx)                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │Dashboard │  │Settings  │  │History   │  │Partials  │            │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
├───────┴──────────────┴────────────┴──────────────┴───────────────────┤
│                     app.state (shared mutable)                       │
│  settings | triggarr_state | radarr_client | sonarr_client           │
│  scheduler | search_lock | db | last_search_time                     │
├──────────────────────────────────────────────────────────────────────┤
│                      Scheduler (APScheduler)                         │
│  radarr_search (interval job) | sonarr_search (interval job)         │
├──────────────────────────────────────────────────────────────────────┤
│                Search Engine + Tracking                              │
│  run_radarr_cycle() | run_sonarr_cycle() | run_tracking_check()      │
├──────────────────────────────────────────────────────────────────────┤
│                    API Clients                                       │
│  ┌──────────────┐  ┌──────────────┐                                  │
│  │ RadarrClient │  │ SonarrClient │                                  │
│  └──────────────┘  └──────────────┘                                  │
├──────────────────────────────────────────────────────────────────────┤
│                    Persistence                                       │
│  ┌──────────┐  ┌──────────┐                                          │
│  │state.json│  │triggarr.db│                                         │
│  │(cursors) │  │(history) │                                          │
│  └──────────┘  └──────────┘                                          │
└──────────────────────────────────────────────────────────────────────┘
```

### Current Assumptions Broken by Multi-Instance

| Assumption | Where Hardcoded | Impact |
|-----------|-----------------|--------|
| One Radarr, one Sonarr | `Settings.radarr: ArrConfig`, `Settings.sonarr: ArrConfig` | Config model must support N instances |
| State keyed by `"radarr"` / `"sonarr"` | `TriggarrState`, `AppState` TypedDicts, `_default_state()` | State must be keyed by instance ID |
| Two clients on `app.state` | `app.state.radarr_client`, `app.state.sonarr_client` | Need a client registry/dict |
| Two scheduler jobs | `radarr_search`, `sonarr_search` job IDs | Dynamic job IDs per instance |
| Tracking uses hardcoded client lookup | `_get_client()` dispatches on `"Radarr"` / `"Sonarr"` string | Must resolve by instance ID |
| Dashboard iterates `("radarr", "sonarr")` | `routes.py` loops, `_build_app_context()` | Must iterate dynamic instance list |
| Settings form has 2 app sections | `settings.html`, `save_settings()` | Must render/parse N instances |
| Search history `app` column is `"Radarr"` / `"Sonarr"` | `insert_search_entry()`, `get_dashboard_stats()` | Needs instance identifier column |
| `collect_secrets()` iterates 2 apps | `startup.py` | Must iterate all instances |

## Target Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Web Layer (htmx)                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │Dashboard │  │Settings  │  │History   │  │Partials  │            │
│  │(N cards) │  │(N inst.) │  │(+filter) │  │(per-inst)│            │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
├───────┴──────────────┴────────────┴──────────────┴───────────────────┤
│                     app.state (shared mutable)                       │
│  settings | triggarr_state | clients: dict[str, ArrClient]           │
│  scheduler | search_lock | db | last_search_time: dict               │
├──────────────────────────────────────────────────────────────────────┤
│                      Scheduler (APScheduler)                         │
│  {instance_id}_search (interval job) -- one per enabled instance     │
├──────────────────────────────────────────────────────────────────────┤
│                Search Engine + Tracking                              │
│  run_radarr_cycle(instance_id) | run_sonarr_cycle(instance_id)       │
│  filter_by_tags() | run_tracking_check(clients_dict)                 │
├──────────────────────────────────────────────────────────────────────┤
│                    API Clients (dynamic registry)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ RadarrClient │  │ RadarrClient │  │ SonarrClient │  ...           │
│  │ "radarr-4k"  │  │ "radarr-hd"  │  │ "sonarr-main"│               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
├──────────────────────────────────────────────────────────────────────┤
│                    Persistence                                       │
│  ┌──────────┐  ┌──────────┐                                          │
│  │state.json│  │triggarr.db│                                         │
│  │(per-inst)│  │(+inst_id)│                                          │
│  └──────────┘  └──────────┘                                          │
└──────────────────────────────────────────────────────────────────────┘
```

## Component Changes: Detailed Breakdown

### 1. Config Model (`models/config.py`)

**Change type:** RESTRUCTURE (breaking)

**Current:**
```python
class Settings(BaseSettings):
    general: GeneralConfig
    radarr: ArrConfig      # single instance
    sonarr: ArrConfig      # single instance
```

**Target:**
```python
class InstanceConfig(BaseModel):
    """Configuration for one *arr instance."""
    name: str                              # Human-readable name (e.g. "Radarr 4K")
    app_type: Literal["radarr", "sonarr"]  # Which *arr app
    url: str = ""
    api_key: SecretStr = SecretStr("")
    enabled: bool = False
    search_interval: int = 30
    search_missing_count: int = 5
    search_cutoff_count: int = 5
    # Tag filtering (new)
    missing_tag: str = ""     # Tag name for missing queue filter (empty = all)
    cutoff_tag: str = ""      # Tag name for cutoff queue filter (empty = all)

class Settings(BaseSettings):
    general: GeneralConfig
    instances: list[InstanceConfig] = []
```

**Key design decisions:**

- **`instances` as a list, not a dict.** TOML `[[instances]]` array-of-tables is the natural TOML structure. A dict requires `[instances.radarr-4k]` which is less ergonomic. The list preserves insertion order for dashboard display.
- **`app_type` discriminator.** Each instance declares whether it is Radarr or Sonarr. This replaces the hardcoded `[radarr]` / `[sonarr]` sections.
- **`name` as human label, derived `instance_id` for internal use.** The `instance_id` should be derived (slugified name) for internal keying. Use a validator to ensure uniqueness across the list.
- **Tag fields are strings (tag names), not IDs.** Users configure tag names ("triggarr-missing"); the app resolves to IDs via `/api/v3/tag` at runtime. This is more user-friendly than requiring numeric IDs. IDs can change if a tag is deleted and recreated.
- **Backward compatibility:** A migration path should detect old-format `[radarr]` / `[sonarr]` sections and auto-convert to `[[instances]]` on first load, rewriting the config file with a logged deprecation warning.

**TOML structure:**
```toml
[general]
log_level = "info"

[[instances]]
name = "Radarr 4K"
app_type = "radarr"
url = "http://radarr-4k:7878"
api_key = "abc123"
enabled = true
search_interval = 30
search_missing_count = 5
search_cutoff_count = 5
missing_tag = "triggarr-missing"
cutoff_tag = ""

[[instances]]
name = "Sonarr"
app_type = "sonarr"
url = "http://sonarr:8989"
api_key = "def456"
enabled = true
```

### 2. State Model (`state.py`)

**Change type:** RESTRUCTURE (breaking)

**Current:** State is keyed by `"radarr"` and `"sonarr"` as hardcoded top-level keys.

**Target:** State keyed by instance ID (slugified name).

```python
class TriggarrState(TypedDict, total=False):
    instances: dict[str, AppState]  # instance_id -> per-instance state
    search_log: list[dict]          # deprecated, kept for migration compat
```

**Migration:** On load, detect old-format keys (`"radarr"`, `"sonarr"`) and remap to the new instance IDs. One-time, logged.

### 3. API Clients (`clients/`)

**Change type:** MINOR (no structural changes to client classes)

The `RadarrClient` and `SonarrClient` classes themselves do not change. They are already instance-agnostic -- they take a `base_url` and `api_key` and talk to one *arr server.

**New: Tag resolution method on `ArrClient` base class.**

```python
async def get_tags(self) -> list[dict]:
    """Fetch all tags from /api/v3/tag."""
    response = await self.get("/api/v3/tag")
    return response.json()

async def resolve_tag_id(self, tag_name: str) -> int | None:
    """Resolve a tag name to its ID. Returns None if not found."""
    tags = await self.get_tags()
    for tag in tags:
        if tag.get("label", "").lower() == tag_name.lower():
            return tag["id"]
    return None
```

Both Radarr and Sonarr share the same `/api/v3/tag` endpoint schema, so this belongs on the base class.

**Storage change:** `app.state` replaces individual client attributes with a dict.

```python
# Current
app.state.radarr_client = RadarrClient(...)
app.state.sonarr_client = SonarrClient(...)

# Target
app.state.clients: dict[str, ArrClient] = {
    "radarr-4k": RadarrClient(...),
    "sonarr-main": SonarrClient(...),
}
```

### 4. Tag-Based Filtering (`search/engine.py`)

**Change type:** NEW FUNCTION + cycle modification

**How tags work in the *arr APIs:**

- Radarr: Each movie object from `/api/v3/wanted/missing` includes a `tags` field -- an array of integer tag IDs (e.g., `[1, 3]`). There is NO server-side tag filter parameter on the wanted endpoints.
- Sonarr: Each episode object from `/api/v3/wanted/missing` with `includeSeries=true` includes the series data, which has a `tags` field on the series object (at `episode["series"]["tags"]`).
- Both apps have a `/api/v3/tag` endpoint that returns `[{"id": 1, "label": "triggarr-missing"}, ...]`.

**Filtering strategy:** Client-side filtering after fetch. This is the only option since the wanted/missing endpoints do not support server-side tag filtering.

```python
def filter_by_tag(items: list[dict], tag_id: int, tag_path: str = "tags") -> list[dict]:
    """Filter items to those containing the given tag ID.

    Args:
        items: List of item dicts from *arr API.
        tag_id: The resolved tag ID to filter on.
        tag_path: Dot-path to the tags array. For Radarr movies, "tags".
                  For Sonarr episodes with includeSeries, "series.tags".
    """
    result = []
    for item in items:
        obj = item
        for key in tag_path.split("."):
            obj = obj.get(key, {}) if isinstance(obj, dict) else {}
        if isinstance(obj, list) and tag_id in obj:
            result.append(item)
    return result
```

**Pipeline position in cycle functions:**

```
fetch items
  -> filter_monitored()            # existing
  -> filter_by_tag()               # NEW: if tag configured, filter here
  -> filter_unreleased_movies()    # existing (Radarr only)
  -> deduplicate_to_seasons()      # existing (Sonarr only)
  -> slice_batch()                 # existing
  -> search                        # existing
```

Tag filtering goes after monitored filtering but before release filtering. Rationale: tags are a deliberate user opt-in, so they should narrow the set before any further processing. An item without the tag should never reach the release filter or cursor.

**Tag ID caching:** Resolve tag name to ID once at cycle start (before the fetch loop). If resolution fails (tag does not exist in *arr), log a warning and skip filtering for that queue (fail-open, not fail-closed -- same philosophy as null release dates in v2.2).

### 5. Search Engine Cycle Functions (`search/engine.py`)

**Change type:** MODIFY signatures and internal logic

**Current:** `run_radarr_cycle(client, state, settings, db)` -- accesses settings directly.

**Target:** `run_radarr_cycle(client, instance_id, instance_config, general_config, state, db)` -- receives per-instance config.

Changes within cycle functions:
1. State access changes from `state["radarr"]` to `state["instances"][instance_id]`.
2. Settings access changes from `settings.radarr.search_missing_count` to `instance_config.search_missing_count`.
3. Add tag resolution and filtering step before the existing pipeline.
4. Search history entries include instance_id (see DB section).
5. Log messages include instance name for disambiguation (e.g., "Radarr 4K: Searched..." instead of "Radarr: Searched...").

### 6. Scheduler (`search/scheduler.py`)

**Change type:** MODIFY -- dynamic job creation

**Current:** Loops over `("radarr", "sonarr")` and creates two jobs.

**Target:** Loops over `settings.instances` and creates one job per enabled instance.

```python
for inst in settings.instances:
    if not inst.enabled:
        continue
    instance_id = slugify(inst.name)
    job_fn = make_search_job(app, instance_id, state_path)
    scheduler.add_job(
        job_fn,
        "interval",
        minutes=inst.search_interval,
        id=f"{instance_id}_search",
        next_run_time=datetime.now(UTC),
    )
```

**`make_search_job` changes:** The closure reads the client and instance config from `app.state.clients[instance_id]` and looks up the matching instance in `app.state.settings.instances` at execution time. Same lazy-read pattern as today.

**Lifespan changes:**
- Create N clients, store in `app.state.clients` dict.
- Schedule N jobs.
- Shutdown: close all clients in the dict.
- The single `search_lock` is shared across all instances. This serializes all search cycles, preventing concurrent API hammering. This is intentional and matches the current design philosophy.

### 7. Database (`db.py`)

**Change type:** MIGRATION (schema v6)

**New column:** `instance_id TEXT` on `search_history` table.

```sql
ALTER TABLE search_history ADD COLUMN instance_id TEXT DEFAULT NULL;
```

The `app` column remains (still useful for display: "Radarr" vs "Sonarr"). The `instance_id` column identifies which specific instance triggered the search. Old rows have `NULL` instance_id (acceptable -- they predate multi-instance).

**`lifetime_stats` table:** Currently seeded with rows for "Radarr" and "Sonarr". For multi-instance, the primary key changes from `app` to `instance_id`. Migration v6 should rename existing rows to match instance IDs from the config migration.

**Query changes:**
- `get_dashboard_stats()`: Group by instance_id instead of (or in addition to) app.
- `get_trackable_entries()`: Include instance_id in returned dicts.
- `get_search_history()`: Add instance_id to filterable columns.
- `insert_search_entry()`: Accept and store instance_id parameter.

### 8. Tracking (`tracking.py`)

**Change type:** MODIFY -- client lookup

**Current:** `_get_client()` dispatches on `"Radarr"` / `"Sonarr"` string to find the client.

**Target:** Tracking entries in DB include `instance_id`. The tracking function receives the full clients dict and looks up `clients[instance_id]`.

```python
async def run_tracking_check(
    db: aiosqlite.Connection,
    clients: dict[str, ArrClient],
    tracking_window_minutes: int,
) -> dict[str, int]:
```

### 9. Web Routes (`web/routes.py`)

**Change type:** MODIFY -- iterate instances

**Dashboard:** Instead of iterating `("radarr", "sonarr")`, iterate `settings.instances` and build one card context per enabled instance.

**Settings page:** Render a dynamic list of instance configuration forms. Support add/remove instance via htmx. Each form section has: name, app_type dropdown, url, api_key, enabled, interval, counts, missing_tag, cutoff_tag.

**Search-now endpoint:** Change `app_name` path param to `instance_id`.

**History page:** Add instance filter alongside existing app/queue/outcome filters.

**Partials:** `partial_app_card/{instance_id}` instead of `partial_app_card/{app_name}`.

### 10. Startup (`startup.py`)

**Change type:** MODIFY -- iterate instances

- `collect_secrets()`: Iterate `settings.instances` instead of `(settings.radarr, settings.sonarr)`.
- `validate_connections()`: Create temp client per enabled instance, validate, close.
- `check_localhost_urls()`: Check each instance's URL.
- `print_banner()`: List all instances with their status.

## Data Flow: Multi-Instance Search Cycle

```
Scheduler fires {instance_id}_search job
    |
    v
make_search_job closure reads from app.state:
    client = app.state.clients[instance_id]
    instance_config = find_instance(app.state.settings, instance_id)
    general_config = app.state.settings.general
    |
    v
acquire search_lock (shared across all instances)
    |
    v
Determine cycle function: run_radarr_cycle or run_sonarr_cycle
based on instance_config.app_type
    |
    v
CYCLE FUNCTION:
    1. Resolve tag IDs (if missing_tag or cutoff_tag configured)
       -> GET /api/v3/tag -> find tag by label -> cache tag_id
    2. Fetch wanted/missing + wanted/cutoff from *arr API
    3. Pipeline:
       missing items -> filter_monitored -> filter_by_tag(missing_tag_id)
                     -> filter_unreleased (Radarr) -> slice_batch -> search
       cutoff items  -> filter_monitored -> filter_by_tag(cutoff_tag_id)
                     -> slice_batch -> search
    4. Record searches in DB with instance_id
    5. Run tracking check (pass clients dict)
    6. Save state with per-instance cursors
    |
    v
release search_lock
```

## Architectural Patterns

### Pattern 1: Instance Registry on app.state

**What:** Replace individual `radarr_client` / `sonarr_client` attributes with a `clients: dict[str, ArrClient]` dict keyed by instance_id.

**When to use:** Whenever the number of components is dynamic (not known at compile time).

**Trade-offs:**
- Pro: No code changes needed when adding the 5th instance.
- Pro: Hot-reload (settings save) just updates the dict.
- Con: Dict access is slightly less explicit than named attributes.
- Con: Must handle missing keys gracefully.

This is the correct pattern because the number of instances is user-configured and can change at runtime via the settings editor.

### Pattern 2: Config Migration (Old Format to New)

**What:** Detect old `[radarr]` / `[sonarr]` TOML sections, auto-convert to `[[instances]]` array, rewrite config file.

**When to use:** When changing config schema in a backward-incompatible way for an app with existing users.

**Implementation:**
```python
def migrate_config_format(data: dict) -> dict:
    """Convert old single-instance config to multi-instance format."""
    if "instances" in data:
        return data  # Already new format
    instances = []
    for app_type in ("radarr", "sonarr"):
        if app_type in data:
            cfg = data.pop(app_type)
            cfg["name"] = app_type.title()
            cfg["app_type"] = app_type
            instances.append(cfg)
    data["instances"] = instances
    return data
```

**Trade-offs:**
- Pro: Existing users do not have to manually rewrite config.
- Pro: Clear deprecation path.
- Con: Migration code must be maintained until old format is dropped.

### Pattern 3: Fail-Open Tag Filtering

**What:** When a configured tag name does not resolve to an ID (tag does not exist in *arr), skip filtering and search all items, with a logged warning.

**When to use:** When the filter is additive (narrows results) and the safe default is "no filter."

**Rationale:** Same philosophy as the existing null-release-date handling (v2.2). A misconfigured tag name should not silently stop all searches. The user sees the warning in logs and can correct the tag name.

### Pattern 4: Slugified Instance ID

**What:** Derive `instance_id` from the user-provided `name` field by lowercasing and replacing non-alphanumeric characters with hyphens.

**When to use:** When human-readable names must map to stable internal keys used in state files, DB columns, and scheduler job IDs.

**Implementation:**
```python
import re

def slugify(name: str) -> str:
    """Convert a human name to a stable slug for internal keying."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "instance"
```

**Trade-offs:**
- Pro: Survives config reordering (unlike index-based IDs).
- Pro: Human-readable in logs and state files.
- Con: Rename of instance name changes the ID, orphaning old state/history. Mitigate by warning on name change.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Separate Config Sections Per Instance Type

**What people do:** `[radarr_instances]` and `[sonarr_instances]` as separate sections.
**Why it is wrong:** Duplicates the config schema. The only difference between a Radarr and Sonarr instance is the `app_type` field (and which cycle function runs). All other fields are identical.
**Do this instead:** Single `[[instances]]` array with an `app_type` discriminator.

### Anti-Pattern 2: Per-Instance Database Connections

**What people do:** Open a separate SQLite connection per instance.
**Why it is wrong:** SQLite is single-writer anyway. Multiple connections add complexity (WAL contention, connection management) with zero benefit.
**Do this instead:** Single shared connection, instance_id column for scoping queries.

### Anti-Pattern 3: Per-Instance Search Locks

**What people do:** Create an `asyncio.Lock()` per instance so cycles can run concurrently.
**Why it is wrong:** Concurrent API calls to multiple *arr instances could hammer the network and shared indexers. The single lock serializes cycles, which is the desired behavior for a polite search daemon.
**Do this instead:** Keep the single `search_lock`. If cycle durations become a problem with many instances, address it later as a concrete performance issue, not a premature optimization.

### Anti-Pattern 4: Storing Tag IDs in Config

**What people do:** Have users put numeric tag IDs in the config file.
**Why it is wrong:** Users do not know tag IDs. They know tag names. IDs can change if a tag is deleted and recreated.
**Do this instead:** Store tag names in config, resolve to IDs at runtime via the `/api/v3/tag` API.

### Anti-Pattern 5: Server-Side Tag Filtering

**What people do:** Assume the wanted/missing endpoint accepts a tag filter parameter.
**Why it is wrong:** The Radarr/Sonarr wanted/missing and wanted/cutoff API endpoints do not support tag-based query parameters. All filtering must be done client-side after fetching the full list.
**Do this instead:** Fetch all items, then filter in Python using the `tags` array on each item.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Radarr instances (N) | httpx async client, `/api/v3/*` | Tag endpoint: `/api/v3/tag` (GET, returns `[{id, label}]`). Movie objects have `tags: [int]` at top level. |
| Sonarr instances (N) | httpx async client, `/api/v3/*` | Same tag endpoint. Episode objects have tags at `series.tags` (when `includeSeries=true`). |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Config -> Clients | Instance list drives client creation | One client per enabled instance |
| Config -> Scheduler | Instance list drives job creation | One interval job per enabled instance |
| Config -> State | Instance IDs key state dict entries | State auto-creates entries for new instances |
| Engine -> DB | instance_id param on all DB writes | Enables per-instance history filtering |
| Tracking -> Clients | Clients dict lookup by instance_id | Replaces hardcoded app-name dispatch |
| Settings form -> Scheduler | Settings save triggers dynamic job add/remove/reschedule | Must handle add/remove of instances, not just enable/disable |

## Suggested Build Order

The build order is driven by dependency chains and testability.

### Phase 1: Config Model + Migration

**What:** Restructure `InstanceConfig`, `Settings`, config loading/saving, and default template. Add old-format migration. Add instance_id derivation (slugify). Add tag fields.

**Why first:** Everything depends on the config model. Cannot change clients, scheduler, or engine without the new config shape.

**Dependencies:** None.

**Test surface:** Config parsing, validation, migration from old format, instance_id uniqueness, tag field defaults.

### Phase 2: State Model + Migration

**What:** Restructure `TriggarrState` to use `instances: dict[str, AppState]`. Migrate old state.json format. Update `load_state()`, `save_state()`, `_default_state()`.

**Why second:** The engine and scheduler need the new state shape, but state depends on instance IDs from the config model.

**Dependencies:** Phase 1 (instance IDs).

**Test surface:** State load/save, old-format migration, default state creation for new instances.

### Phase 3: Client Registry + Tag Resolution

**What:** Add `get_tags()` / `resolve_tag_id()` to `ArrClient` base. Change `app.state` to use `clients: dict[str, ArrClient]`. Update lifespan client creation loop.

**Why third:** Engine changes need the client registry. Tag resolution is needed before engine changes.

**Dependencies:** Phase 1 (instance configs for client creation).

**Test surface:** Tag resolution (found, not found, case-insensitive), client dict management.

### Phase 4: Search Engine + Tag Filtering

**What:** Add `filter_by_tag()`. Modify cycle function signatures to accept instance_id + instance_config. Update state access within cycles. Wire tag filtering into pipeline.

**Why fourth:** Core feature. Needs config model, state model, and client registry.

**Dependencies:** Phases 1-3.

**Test surface:** Tag filtering (match, no match, empty tag = no filter, nested path for Sonarr), cycle functions with instance_id, state updates per instance.

### Phase 5: Database Schema + Queries

**What:** Migration v6: add `instance_id` column to `search_history`, update `lifetime_stats` seeding. Update all CRUD functions to accept/return instance_id.

**Why fifth:** Can be done in parallel with Phase 4, but logically follows the engine knowing about instance_id.

**Dependencies:** Phase 1 (instance IDs).

**Test surface:** Migration, queries with instance_id filter, backward compat for NULL instance_id rows.

### Phase 6: Scheduler + Tracking Updates

**What:** Dynamic job creation per instance. Update `make_search_job` closure. Update tracking to use clients dict and instance_id. Update startup sequence.

**Why sixth:** Wires the engine changes into the running application.

**Dependencies:** Phases 3-5.

**Test surface:** Job creation/removal, tracking with instance_id resolution, startup with N instances.

### Phase 7: Web UI Updates

**What:** Dashboard renders N instance cards. Settings page supports add/remove/edit instances with tag fields. History page adds instance filter. Search-now uses instance_id. Partials updated.

**Why last:** UI is the integration layer. Needs all backend changes in place.

**Dependencies:** Phases 1-6.

**Test surface:** Route tests with multi-instance settings, settings form parsing, history filtering.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-3 instances | Current design is fine. Single lock, single DB connection. |
| 4-10 instances | Still fine. Cycle times may increase due to serial lock. Monitor cycle duration in logs. |
| 10+ instances | Consider per-instance locks OR a semaphore(N) to allow controlled parallelism. This is unlikely for a homelab tool. |

### First bottleneck: Total cycle time

With many instances running serially behind one lock, the last instance's "next run" could be significantly delayed. Mitigation: if this becomes real, add a semaphore(2) instead of a mutex lock, allowing 2 concurrent cycles. But for a homelab tool with 2-4 instances, this is not a concern.

## Sources

- Full codebase audit of all 13 source files in `triggarr/` (HIGH confidence)
- [Radarr API Docs](https://radarr.video/docs/api/) -- tag and movie endpoints (MEDIUM confidence -- doc UI confirmed, schema via third-party libs)
- [Sonarr API Docs](https://sonarr.tv/docs/api/) -- tag and series endpoints (MEDIUM confidence)
- [ArrAPI documentation](https://arrapi.kometa.wiki/en/latest/radarr.html) -- tag field structure confirmation: movie objects have `tags: [int]` (MEDIUM confidence)
- [Radarr Wiki: API:Movie](https://github.com/Radarr/Radarr/wiki/API:Movie) -- movie object schema (MEDIUM confidence)
- [Sonarr Wiki: Settings](https://wiki.servarr.com/sonarr/settings) -- tag management reference (MEDIUM confidence)
- Radarr/Sonarr `/api/v3/tag` endpoint returns `[{id: int, label: str}]` -- confirmed by multiple third-party client libraries (MEDIUM confidence, not verified against live API)

---
*Architecture research for: Triggarr v2.3 Multi-Instance & Tag Filtering*
*Researched: 2026-03-09*
