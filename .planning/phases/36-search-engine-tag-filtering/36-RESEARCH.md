# Phase 36: Search Engine & Tag Filtering - Research

**Researched:** 2026-03-10
**Domain:** Tag-based item filtering in the search pipeline
**Confidence:** HIGH

## Summary

Phase 36 adds tag-based filtering to the search engine so that when a tag is configured for a queue, only items bearing that tag are included in the search cycle. This builds on Phase 35's tag resolution machinery (`resolve_tag_id()`, `ArrClient.get_tags()`, `Tag` model) and Phase 34's per-instance state and engine wiring.

The work has two parts: (1) adding `missing_tag` and `cutoff_tag` optional string fields to `InstanceConfig`, and (2) adding a `filter_by_tag()` pure function plus wiring it into `run_radarr_cycle()` and `run_sonarr_cycle()`. The critical subtlety is that Radarr movies carry tags directly on the movie object (`movie["tags"]` is a `list[int]`), while Sonarr episodes do NOT have tags -- tags live on the series object (`episode["series"]["tags"]` is a `list[int]`). The filtering function must account for this difference.

When no tag is configured (empty string, the default), the filter is a no-op and all items pass through, preserving existing behavior. When a configured tag name cannot be resolved (tag deleted from *arr), the cycle logs a warning and proceeds without filtering (fail-open), consistent with Phase 35's graceful failure pattern.

**Primary recommendation:** Add `missing_tag`/`cutoff_tag` fields to `InstanceConfig` (default empty string), create a `filter_by_tag()` pure function that takes items + tag_id + a tag-accessor callable, and wire tag resolution + filtering into both cycle functions after the existing `filter_monitored` step.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TAG-01 | User can configure a tag name per instance for the missing queue (only items with that tag are searched) | `missing_tag` field on `InstanceConfig` + `filter_by_tag()` applied after `filter_monitored()` in the missing queue section of both cycle functions |
| TAG-02 | User can configure a tag name per instance for the cutoff queue (only items with that tag are searched) | `cutoff_tag` field on `InstanceConfig` + `filter_by_tag()` applied after `filter_monitored()` in the cutoff queue section of both cycle functions |
| TAG-03 | When no tag is configured, all monitored items are searched (default behavior unchanged) | `missing_tag`/`cutoff_tag` default to `""`. When empty, `filter_by_tag()` is skipped entirely -- no API call to `/api/v3/tag` needed, no filtering applied |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | existing | InstanceConfig model extension | Already used for all config models |
| httpx | existing | Tag API calls via ArrClient | Already used by all client methods |
| loguru | existing | Warning logs for unresolved tags | Project convention |

### Supporting
No new libraries needed. All functionality builds on existing code from Phase 35.

## Architecture Patterns

### Recommended Project Structure
```
triggarr/
├── models/
│   └── config.py        # Add missing_tag, cutoff_tag to InstanceConfig
├── search/
│   └── engine.py         # Add filter_by_tag(), wire into cycle functions
└── (no other files changed)
```

### Pattern 1: Config Fields on InstanceConfig
**What:** Two new optional string fields for tag names
**When to use:** Configured per-instance in TOML
**Example:**
```python
# In triggarr/models/config.py, add to InstanceConfig:
class InstanceConfig(BaseModel):
    # ... existing fields ...
    missing_tag: str = ""   # Tag name for missing queue filter (empty = search all)
    cutoff_tag: str = ""    # Tag name for cutoff queue filter (empty = search all)
```

**TOML configuration:**
```toml
[radarr."4K Radarr"]
url = "http://radarr-4k:7878"
api_key = "abc123"
enabled = true
missing_tag = "triggarr"
cutoff_tag = ""
```

### Pattern 2: Pure Filter Function with Tag Accessor
**What:** A `filter_by_tag()` function that takes items, a resolved tag ID, and a callable that extracts the tag list from an item
**When to use:** Applied in both Radarr and Sonarr cycles, with different accessors
**Rationale:** Radarr items have `item["tags"]` directly. Sonarr episodes have `item["series"]["tags"]`. A callable accessor keeps the filter function generic.
**Example:**
```python
def filter_by_tag(
    items: list[dict],
    tag_id: int,
    get_tags: Callable[[dict], list[int]],
) -> list[dict]:
    """Filter items to only those bearing the given tag ID.

    Args:
        items: List of item dicts from *arr API.
        tag_id: Resolved numeric tag ID to filter by.
        get_tags: Callable that extracts the tag ID list from an item dict.

    Returns:
        Only items where tag_id is in the item's tag list.
    """
    return [item for item in items if tag_id in get_tags(item)]
```

**Tag accessors:**
```python
# Radarr: tags are directly on the movie object
def _radarr_tags(item: dict) -> list[int]:
    return item.get("tags", [])

# Sonarr: tags are on the series object (NOT the episode object)
def _sonarr_tags(item: dict) -> list[int]:
    return item.get("series", {}).get("tags", [])
```

### Pattern 3: Tag Resolution and Filtering Wiring in Cycle Functions
**What:** At the top of each cycle function, resolve tag names to IDs (if configured), then apply filtering after `filter_monitored()`
**When to use:** In `run_radarr_cycle()` and `run_sonarr_cycle()`
**Example:**
```python
# Inside run_radarr_cycle, after fetching items but before batch processing:

# Resolve tags (only if at least one tag is configured)
missing_tag_id: int | None = None
cutoff_tag_id: int | None = None
if instance_config.missing_tag or instance_config.cutoff_tag:
    try:
        tags = await client.get_tags()
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning(
            "Radarr: Failed to fetch tags -- skipping tag filtering: {exc}",
            exc=exc,
        )
        tags = []

    if instance_config.missing_tag:
        missing_tag_id = resolve_tag_id(instance_config.missing_tag, tags)
        if missing_tag_id is None and tags:
            logger.warning(
                "Radarr: Tag '{tag}' not found -- searching all missing items",
                tag=instance_config.missing_tag,
            )

    if instance_config.cutoff_tag:
        cutoff_tag_id = resolve_tag_id(instance_config.cutoff_tag, tags)
        if cutoff_tag_id is None and tags:
            logger.warning(
                "Radarr: Tag '{tag}' not found -- searching all cutoff items",
                tag=instance_config.cutoff_tag,
            )

# --- Missing queue ---
missing = filter_monitored(missing)
if missing_tag_id is not None:
    missing = filter_by_tag(missing, missing_tag_id, _radarr_tags)
# ... rest of missing queue processing ...

# --- Cutoff queue ---
cutoff = filter_monitored(cutoff)
if cutoff_tag_id is not None:
    cutoff = filter_by_tag(cutoff, cutoff_tag_id, _radarr_tags)
# ... rest of cutoff queue processing ...
```

### Pattern 4: Sonarr Tag Access from Series Object
**What:** Sonarr's wanted/missing and wanted/cutoff endpoints return episode objects. Tags are NOT on episodes -- they are on the `series` sub-object.
**Critical detail:** The Sonarr client already requests `includeSeries=true` (see `sonarr.py` lines 59, 69), so `episode["series"]` is populated. Tags are at `episode["series"]["tags"]`.
**Verification:** Confirmed via golift.io/starr Go SDK -- `Episode` struct has no `Tags` field; `Series` struct has `Tags []int`.

### Anti-Patterns to Avoid
- **Reading tags from Sonarr episode objects:** Episodes do NOT have tags. Only the parent series has tags. Always access via `episode["series"]["tags"]`.
- **Failing closed on tag resolution failure:** If tags cannot be fetched or the configured tag name is not found, proceed without filtering (search all items). This is fail-open by design -- better to search too much than too little.
- **Calling get_tags() when no tags are configured:** If both `missing_tag` and `cutoff_tag` are empty, skip the tag API call entirely. No unnecessary network requests.
- **Applying tag filter after deduplication (Sonarr):** For Sonarr, tag filtering must happen BEFORE `deduplicate_to_seasons()`. The tag is on the series (accessible via each episode), and filtering after deduplication loses access to the `series.tags` data.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tag name-to-ID resolution | Custom lookup | Existing `resolve_tag_id()` from Phase 35 | Already tested, handles case insensitivity and whitespace |
| Tag fetching | New HTTP call | Existing `ArrClient.get_tags()` from Phase 35 | Already handles retry, error handling, model validation |
| Config defaults | Complex migration | Pydantic default values (`""`) | TOML files without tag fields parse cleanly with defaults |

## Common Pitfalls

### Pitfall 1: Sonarr Tag Location
**What goes wrong:** Code tries to read `episode["tags"]` which does not exist on Sonarr episode objects
**Why it happens:** Radarr movies have tags directly; easy to assume episodes do too
**How to avoid:** Always use `episode["series"]["tags"]` for Sonarr. Verified via Go SDK: Episode struct has no Tags field.
**Warning signs:** Tag filtering appears to find zero matches for Sonarr despite series having the tag

### Pitfall 2: Tag Filtering After Sonarr Deduplication
**What goes wrong:** `deduplicate_to_seasons()` creates new dicts with only `seriesId`, `seasonNumber`, `display_name`, `episode_count` -- no `series` sub-object, so tag filtering fails
**Why it happens:** Applying filter_by_tag after deduplicate_to_seasons loses the series data
**How to avoid:** Apply tag filtering to episodes BEFORE calling `deduplicate_to_seasons()`. The filter works on the raw episode list which still has the `series` sub-object.
**Warning signs:** KeyError or empty results when filtering deduplicated Sonarr data

### Pitfall 3: Unreleased Movie Filter Interaction
**What goes wrong:** Tag filter and unreleased filter applied in wrong order, causing incorrect counts
**Why it happens:** Both are filtering steps on the missing queue
**How to avoid:** Apply filters in this order: `filter_monitored()` -> `filter_by_tag()` -> `filter_unreleased_movies()`. Tag filtering narrows the set first, then unreleased filtering removes future items. The `missing_eligible` count should reflect post-tag-filter, post-unreleased-filter count.
**Warning signs:** Diagnostic counts don't add up

### Pitfall 4: Unnecessary Tag API Calls
**What goes wrong:** Every cycle calls `get_tags()` even when no tags are configured
**Why it happens:** Not checking if tags are actually configured before calling
**How to avoid:** Only call `get_tags()` when `instance_config.missing_tag` or `instance_config.cutoff_tag` is non-empty

### Pitfall 5: TOML Backward Compatibility
**What goes wrong:** Existing configs without `missing_tag`/`cutoff_tag` fields fail to parse
**Why it happens:** New required fields without defaults
**How to avoid:** Default values are `""` (empty string). Pydantic fills in defaults for missing TOML keys. No migration needed.

## Code Examples

### InstanceConfig with Tag Fields
```python
# In triggarr/models/config.py
class InstanceConfig(BaseModel):
    url: str = ""
    api_key: SecretStr = SecretStr("")
    enabled: bool = False
    search_interval: int = 30
    search_missing_count: int = 5
    search_cutoff_count: int = 5
    # Tag filtering (Phase 36)
    missing_tag: str = ""   # Tag name for missing queue (empty = search all)
    cutoff_tag: str = ""    # Tag name for cutoff queue (empty = search all)
```

### filter_by_tag Pure Function
```python
from collections.abc import Callable

def filter_by_tag(
    items: list[dict],
    tag_id: int,
    get_tags: Callable[[dict], list[int]],
) -> list[dict]:
    """Filter items to only those bearing the given tag ID."""
    return [item for item in items if tag_id in get_tags(item)]

def _radarr_tags(item: dict) -> list[int]:
    """Extract tag IDs from a Radarr movie dict."""
    return item.get("tags", [])

def _sonarr_tags(item: dict) -> list[int]:
    """Extract tag IDs from a Sonarr episode dict (via series object)."""
    return item.get("series", {}).get("tags", [])
```

### Complete Radarr Missing Queue with Tag Filtering
```python
# --- Missing queue ---
missing = filter_monitored(missing)
ist["missing_monitored"] = len(missing)
if missing_tag_id is not None:
    missing = filter_by_tag(missing, missing_tag_id, _radarr_tags)
    logger.debug(
        "Radarr: Tag filter applied -- {n} items match tag",
        n=len(missing),
    )
if settings.general.skip_unreleased:
    missing = filter_unreleased_movies(missing)
    # ... existing unreleased skip logging ...
ist["missing_eligible"] = len(missing)
```

### Complete Sonarr Missing Queue with Tag Filtering
```python
# --- Missing queue ---
missing_episodes = filter_sonarr_episodes(missing_episodes)
# Tag filter BEFORE deduplication (episodes still have series sub-object)
if missing_tag_id is not None:
    missing_episodes = filter_by_tag(missing_episodes, missing_tag_id, _sonarr_tags)
    logger.debug(
        "Sonarr: Tag filter applied -- {n} episodes match tag",
        n=len(missing_episodes),
    )
missing_seasons = deduplicate_to_seasons(missing_episodes)
ist["missing_eligible"] = len(missing_episodes)
ist["missing_searchable"] = len(missing_seasons)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Search all wanted items | Tag-based filtering per queue | v2.3 Phase 36 | Users can scope searches to tagged items only |
| No per-queue filtering config | `missing_tag` + `cutoff_tag` per instance | v2.3 Phase 36 | Independent tag control for each queue |

## Open Questions

1. **Should tag filtering counts be tracked in state for dashboard display?**
   - What we know: `missing_monitored` and `missing_eligible` already exist
   - What's unclear: Whether to add a `missing_tagged` count between monitored and eligible
   - Recommendation: Track post-tag-filter count as part of the existing `missing_eligible` / `missing_searchable` pipeline. A separate `missing_tagged` count could be added if the dashboard needs it (Phase 39 concern).

2. **Should the default config template include example tag fields?**
   - What we know: The default TOML template is generated with comments
   - What's unclear: Whether commented-out tag examples belong in default config
   - Recommendation: Include commented-out examples: `# missing_tag = ""` so users discover the feature.

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
| TAG-01a | InstanceConfig accepts missing_tag field | unit | `uv run pytest tests/test_config.py::test_instance_config_missing_tag -x` | No -- Wave 0 |
| TAG-01b | Radarr cycle filters missing items by tag | unit | `uv run pytest tests/test_search.py::test_radarr_cycle_missing_tag_filters -x` | No -- Wave 0 |
| TAG-01c | Sonarr cycle filters missing episodes by series tag | unit | `uv run pytest tests/test_search.py::test_sonarr_cycle_missing_tag_filters -x` | No -- Wave 0 |
| TAG-02a | InstanceConfig accepts cutoff_tag field | unit | `uv run pytest tests/test_config.py::test_instance_config_cutoff_tag -x` | No -- Wave 0 |
| TAG-02b | Radarr cycle filters cutoff items by tag | unit | `uv run pytest tests/test_search.py::test_radarr_cycle_cutoff_tag_filters -x` | No -- Wave 0 |
| TAG-02c | Sonarr cycle filters cutoff episodes by series tag | unit | `uv run pytest tests/test_search.py::test_sonarr_cycle_cutoff_tag_filters -x` | No -- Wave 0 |
| TAG-03a | No tag configured means all items searched (Radarr) | unit | `uv run pytest tests/test_search.py::test_radarr_cycle_no_tag_searches_all -x` | No -- Wave 0 |
| TAG-03b | No tag configured means all items searched (Sonarr) | unit | `uv run pytest tests/test_search.py::test_sonarr_cycle_no_tag_searches_all -x` | No -- Wave 0 |
| TAG-03c | No get_tags() call when tags not configured | unit | `uv run pytest tests/test_search.py::test_no_tag_api_call_when_unconfigured -x` | No -- Wave 0 |
| SC-04a | filter_by_tag with Radarr accessor | unit | `uv run pytest tests/test_search.py::test_filter_by_tag_radarr -x` | No -- Wave 0 |
| SC-04b | filter_by_tag with Sonarr accessor (series.tags) | unit | `uv run pytest tests/test_search.py::test_filter_by_tag_sonarr -x` | No -- Wave 0 |
| SC-04c | Sonarr tag filter before deduplication | unit | `uv run pytest tests/test_search.py::test_sonarr_tag_filter_before_dedup -x` | No -- Wave 0 |
| SC-04d | Tag resolution failure proceeds without filtering | unit | `uv run pytest tests/test_search.py::test_tag_resolution_failure_searches_all -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `missing_tag`/`cutoff_tag` field tests in `tests/test_config.py`
- [ ] `filter_by_tag()` unit tests in `tests/test_search.py`
- [ ] Radarr cycle tag filtering integration tests in `tests/test_search.py`
- [ ] Sonarr cycle tag filtering integration tests in `tests/test_search.py`
- [ ] No-tag default behavior regression tests in `tests/test_search.py`
- [ ] Tag resolution failure graceful handling tests in `tests/test_search.py`

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `triggarr/search/engine.py` (run_radarr_cycle, run_sonarr_cycle, filter_monitored, resolve_tag_id), `triggarr/models/config.py` (InstanceConfig), `triggarr/clients/base.py` (ArrClient.get_tags), `triggarr/clients/sonarr.py` (includeSeries=true), `triggarr/models/arr.py` (Tag model)
- Phase 35 research: `.planning/phases/35-client-registry-tag-resolution/35-RESEARCH.md`
- Architecture research: `.planning/research/ARCHITECTURE.md`, `.planning/research/STACK.md`
- [golift.io/starr/radarr Go SDK](https://pkg.go.dev/golift.io/starr/radarr) - Movie.Tags is `[]int`, confirmed
- [golift.io/starr/sonarr Go SDK](https://pkg.go.dev/golift.io/starr/sonarr) - Episode has NO Tags field; Series.Tags is `[]int`, confirmed

### Secondary (MEDIUM confidence)
- [Radarr API Docs](https://radarr.video/docs/api/) - Movie object structure
- [Sonarr API Docs](https://sonarr.tv/docs/api/) - Episode/Series object structure

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new libraries, all existing patterns
- Architecture: HIGH - extends existing cycle functions with one new filter step, follows established filter_monitored/filter_unreleased pattern exactly
- Pitfalls: HIGH - Sonarr tag location confirmed via Go SDK, filter ordering analyzed against existing code
- Tag API format: HIGH - verified via Go SDK (golift.io/starr), consistent with Phase 35 research

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (stable domain, *arr API v3 is mature)
