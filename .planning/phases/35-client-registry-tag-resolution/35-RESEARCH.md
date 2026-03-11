# Phase 35: Client Registry & Tag Resolution - Research

**Researched:** 2026-03-10
**Domain:** HTTP client lifecycle management, *arr tag API integration
**Confidence:** HIGH

## Summary

Phase 35 formalizes the client registry pattern that already exists in the scheduler (dict of clients keyed by instance name) and adds tag name-to-ID resolution via the *arr `/api/v3/tag` endpoint. The codebase already creates one `RadarrClient`/`SonarrClient` per enabled instance in the lifespan context manager (`scheduler.py` lines 171-188) and stores them on `app.state` as `radarr_clients` and `sonarr_clients`. The existing client dicts are already keyed by instance name.

The primary new work is (1) adding a `get_tags()` method to `ArrClient` that calls `GET /api/v3/tag` and returns a list of `Tag` models, (2) adding a `resolve_tag_id()` helper that maps a tag name (case-insensitive) to a numeric ID, and (3) wiring tag resolution into the search cycle so it runs at the start of each cycle. The `InstanceConfig` model needs `missing_tag` and `cutoff_tag` fields (optional strings), but those belong to Phase 36 (TAG-01/02/03). This phase only needs the resolution machinery -- the config fields and filtering logic come later.

**Primary recommendation:** Add `get_tags()` to `ArrClient` base class, create a `Tag` pydantic model, and add a `resolve_tags()` function that resolves configured tag names to IDs at the start of each search cycle, storing resolved IDs transiently (not persisted).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TAG-04 | Tag names are resolved to IDs via the *arr `/api/v3/tag` endpoint each cycle | ArrClient.get_tags() method + resolve_tag_id() helper called at cycle start; Tag pydantic model for API response; graceful fallback on missing tag name |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | existing | Async HTTP client (already in use) | Already used by ArrClient |
| pydantic | existing | Response model validation | Already used for API models |
| loguru | existing | Structured logging | Project convention |

### Supporting
No new libraries needed. All functionality builds on existing `ArrClient` base class and pydantic models.

## Architecture Patterns

### Recommended Project Structure
```
triggarr/
├── clients/
│   ├── base.py          # Add get_tags() method
│   ├── radarr.py        # No changes needed
│   └── sonarr.py        # No changes needed
├── models/
│   └── arr.py           # Add Tag model
└── search/
    └── engine.py         # Add resolve_tag_id() helper, wire into cycles
```

### Pattern 1: Tag Model in models/arr.py
**What:** Simple pydantic model for the *arr tag API response
**When to use:** Parsing `/api/v3/tag` responses
**Example:**
```python
# Source: Radarr/Sonarr OpenAPI spec, verified via golift.io/starr Go client
class Tag(BaseModel):
    """A tag from the *arr /api/v3/tag endpoint."""
    model_config = ConfigDict(extra="ignore")

    id: int
    label: str
```

### Pattern 2: get_tags() on ArrClient Base
**What:** Fetch all tags from the *arr instance via `GET /api/v3/tag`
**When to use:** Both Radarr and Sonarr share the same tag API format
**Example:**
```python
async def get_tags(self) -> list[Tag]:
    """Fetch all tags from the *arr instance."""
    response = await self.get("/api/v3/tag")
    data = response.json()
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array from /api/v3/tag, got {type(data).__name__}")
    return [Tag.model_validate(item) for item in data]
```

### Pattern 3: Tag Resolution Helper (Pure Function)
**What:** Resolve a tag name to its numeric ID from a list of tags
**When to use:** At the start of each search cycle, before filtering
**Example:**
```python
def resolve_tag_id(tag_name: str, tags: list[Tag]) -> int | None:
    """Resolve a tag name to its ID (case-insensitive).

    Returns None if the tag name is not found.
    """
    normalized = tag_name.strip().lower()
    for tag in tags:
        if tag.label.strip().lower() == normalized:
            return tag.id
    return None
```

### Pattern 4: Per-Cycle Resolution (Not Cached)
**What:** Resolve tags fresh each cycle rather than caching at startup
**When to use:** This is the requirement -- "resolved each cycle" per TAG-04
**Rationale:** Tags can be created/deleted in the *arr UI between cycles. Resolving each cycle ensures consistency without a cache invalidation strategy. The `/api/v3/tag` endpoint is lightweight (typically <10 tags, <1KB response).

### Anti-Patterns to Avoid
- **Caching tag IDs at startup:** TAG-04 explicitly says "each cycle". Tags can change in the *arr UI.
- **Storing resolved tag IDs in state.json:** Tag IDs are transient; re-resolve each cycle.
- **Adding tag fields to InstanceConfig in this phase:** TAG-01/02/03 (Phase 36) add the config fields. This phase only builds the resolution machinery.
- **Crashing on missing tag:** Success criterion 3 requires graceful failure (log warning, skip filtering).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP requests | Custom urllib/aiohttp | Existing ArrClient.get() | Already handles retry, headers, timeout |
| JSON parsing | Manual dict access | Pydantic Tag model | Validates response shape, type safety |
| Case-insensitive matching | Complex regex | `str.strip().lower()` comparison | Simple, correct, no edge cases |

## Common Pitfalls

### Pitfall 1: Case Sensitivity in Tag Matching
**What goes wrong:** User configures tag "4K" but *arr stores it as "4k" -- resolution fails
**Why it happens:** *arr normalizes tag labels to lowercase on creation
**How to avoid:** Always compare case-insensitively (`str.lower()`)
**Warning signs:** Tag appears in *arr UI but resolution returns None

### Pitfall 2: Tag Resolution Failure Blocking Search
**What goes wrong:** Tag API call fails (network error) and entire search cycle is skipped
**Why it happens:** Tag resolution is called before filtering; unhandled exception propagates
**How to avoid:** Catch httpx.HTTPError and pydantic.ValidationError in tag resolution; on failure, log warning and proceed without tag filtering (search all items)
**Warning signs:** Search cycles stop running when *arr is temporarily unreachable

### Pitfall 3: Adding Config Fields Too Early
**What goes wrong:** Phase 35 adds `missing_tag` and `cutoff_tag` to InstanceConfig, breaking TOML parsing for users who haven't configured tags
**Why it happens:** Scope creep from Phase 36 into Phase 35
**How to avoid:** Phase 35 builds the resolution API only. Phase 36 adds config fields and wires them together. The resolution function accepts a tag name string parameter -- it doesn't read config directly.

### Pitfall 4: Tag API Not Available
**What goes wrong:** Very old *arr versions might not have `/api/v3/tag`
**Why it happens:** Unlikely but possible with ancient installations
**How to avoid:** The existing `_request_with_retry` handles HTTP errors. A 404 from the tag endpoint should be caught and logged, not crash the app.

## Code Examples

### Complete Tag Model
```python
# In triggarr/models/arr.py
class Tag(BaseModel):
    """A tag from the *arr /api/v3/tag endpoint.

    Both Radarr and Sonarr return the same {id, label} format.
    """
    model_config = ConfigDict(extra="ignore")

    id: int
    label: str
```

### Complete get_tags() Method
```python
# In triggarr/clients/base.py
from triggarr.models.arr import Tag

async def get_tags(self) -> list[Tag]:
    """Fetch all tags from the *arr instance.

    Calls GET /api/v3/tag which returns a flat JSON array
    of {id, label} objects.
    """
    data = await self.get_json_list("/api/v3/tag")
    return [Tag.model_validate(item) for item in data]
```

### Tag Resolution in Search Cycle
```python
# In triggarr/search/engine.py
from triggarr.models.arr import Tag

def resolve_tag_id(tag_name: str, tags: list[Tag]) -> int | None:
    """Resolve a tag name to its numeric ID (case-insensitive).

    Returns None if the tag name is not found in the tag list.
    """
    normalized = tag_name.strip().lower()
    for tag in tags:
        if tag.label.strip().lower() == normalized:
            return tag.id
    return None
```

### Graceful Tag Resolution at Cycle Start
```python
# Pattern for use in run_radarr_cycle / run_sonarr_cycle
# (wiring happens when Phase 36 adds config fields)
try:
    tags = await client.get_tags()
except (httpx.HTTPError, pydantic.ValidationError) as exc:
    logger.warning(
        "{app}: Failed to fetch tags -- skipping tag filtering: {exc}",
        app=app_name,
        exc=exc,
    )
    tags = []  # Proceed without tag filtering
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single client per app type | Dict of clients per instance | v2.3 Phase 34 | Already done in scheduler.py |
| No tag support | Tag resolution per cycle | v2.3 Phase 35 | New capability |

## Open Questions

1. **Where should resolve_tag_id live?**
   - What we know: It's a pure function that takes a name and tag list
   - What's unclear: Should it be in engine.py, base.py, or a new tags.py?
   - Recommendation: Put it in engine.py alongside existing filter functions (filter_monitored, filter_unreleased_movies). It follows the same pattern: pure function used during search cycles.

2. **Should get_tags() use get_json_list() or direct get()?**
   - What we know: The tag endpoint returns a flat JSON array (not paginated)
   - What's unclear: Whether get_json_list() provides enough value
   - Recommendation: Use `get_json_list()` -- it already exists in ArrClient for exactly this pattern (flat JSON array endpoints) and includes the isinstance check and debug logging.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (asyncio_mode=auto) |
| Config file | pyproject.toml (existing) |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TAG-04a | Tag model parses {id, label} response | unit | `uv run pytest tests/test_clients.py::test_tag_model_parses_response -x` | No -- Wave 0 |
| TAG-04b | get_tags() returns Tag list from API | unit | `uv run pytest tests/test_clients.py::test_get_tags_returns_tag_list -x` | No -- Wave 0 |
| TAG-04c | resolve_tag_id finds tag case-insensitively | unit | `uv run pytest tests/test_search.py::test_resolve_tag_id_case_insensitive -x` | No -- Wave 0 |
| TAG-04d | resolve_tag_id returns None for missing tag | unit | `uv run pytest tests/test_search.py::test_resolve_tag_id_missing_returns_none -x` | No -- Wave 0 |
| TAG-04e | Tag resolution failure logged, not crashed | unit | `uv run pytest tests/test_search.py::test_tag_resolution_failure_graceful -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] Tag model tests in `tests/test_clients.py`
- [ ] get_tags() mock transport tests in `tests/test_clients.py`
- [ ] resolve_tag_id() tests in `tests/test_search.py`
- [ ] Graceful failure tests in `tests/test_search.py`

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `triggarr/clients/base.py`, `triggarr/clients/radarr.py`, `triggarr/clients/sonarr.py`, `triggarr/search/scheduler.py`, `triggarr/search/engine.py`, `triggarr/models/arr.py`, `triggarr/models/config.py`
- [golift.io/starr Go package](https://pkg.go.dev/golift.io/starr) - Tag struct definition `{id int, label string}` confirmed
- [Radarr OpenAPI spec](https://raw.githubusercontent.com/Radarr/Radarr/develop/src/Radarr.Api.V3/openapi.json) - Confirmed GET/POST/PUT/DELETE /api/v3/tag endpoints exist

### Secondary (MEDIUM confidence)
- [Radarr API Docs](https://radarr.video/docs/api/) - Tag endpoints exist in v3 API
- [Sonarr API Docs](https://sonarr.tv/docs/api/) - Same tag API format as Radarr

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new libraries, all existing patterns
- Architecture: HIGH - extends existing ArrClient with one new method, follows get_json_list pattern
- Pitfalls: HIGH - case sensitivity and graceful failure are well-understood patterns
- Tag API format: HIGH - verified via Go client library (golift.io/starr) and Radarr OpenAPI spec

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (stable domain, *arr API v3 is mature)
