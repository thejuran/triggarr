# Architecture Patterns

**Domain:** Skip-unreleased-media filter integration into Triggarr search pipeline
**Researched:** 2026-03-09
**Confidence:** HIGH (based on direct codebase analysis + Radarr API field verification)

## Current Search Pipeline

```
Radarr:
  fetch wanted/missing + cutoff
    --> filter_monitored()
    --> slice_batch(cursor, batch_size)
    --> search each item

Sonarr:
  fetch wanted/missing + cutoff
    --> filter_sonarr_episodes()  [monitored + airDateUtc check]
    --> deduplicate_to_seasons()
    --> slice_batch(cursor, batch_size)
    --> search each item
```

Key observation: Sonarr already unconditionally filters future/unaired episodes via `filter_sonarr_episodes()` (engine.py lines 145-173). The `airDateUtc` check rejects episodes without an air date or with a future air date. Radarr has no equivalent release-date filter.

## Recommended Architecture: Filter Before Cursor

### Proposed Pipeline

```
Radarr:
  fetch wanted/missing + cutoff
    --> filter_monitored()
    --> filter_unreleased_movies()  [NEW, conditional on skip_unreleased]
    --> slice_batch(cursor, batch_size)
    --> search each item

Sonarr:
  fetch wanted/missing + cutoff
    --> filter_monitored()          [extracted from filter_sonarr_episodes]
    --> filter_unaired_episodes()   [extracted, conditional on skip_unreleased]
    --> deduplicate_to_seasons()
    --> slice_batch(cursor, batch_size)
    --> search each item
```

### Why This Location (After Fetch, Before Cursor)

Three candidate locations were evaluated:

| Location | Verdict | Rationale |
|----------|---------|-----------|
| At fetch time (in API client) | WRONG | Client layer has no access to settings. Pushes domain logic into HTTP layer. Release dates are already in the response. |
| After `slice_batch` (post-cursor) | WRONG | If cursor selects 5 items and 3 are unreleased, only 2 get searched. User configured 5. Cursor advances past valid items without searching them. Batch size becomes unpredictable. |
| Before `slice_batch` (pre-cursor) | CORRECT | Filtered list becomes the queue the cursor operates on. Batch sizes are respected. Follows the exact pattern of existing `filter_monitored`. |

### Component Boundaries

| Component | Responsibility | Change |
|-----------|---------------|--------|
| `triggarr/search/engine.py` | Search cycle orchestration, filtering | Add `filter_unreleased_movies()` and `_has_past_date()` helper. Refactor `filter_sonarr_episodes` into separate monitored + unaired filters. Wire conditional application. |
| `triggarr/models/config.py` | Pydantic settings models | Add `skip_unreleased: bool = True` to `GeneralConfig` |
| `triggarr/config.py` | TOML template and loading | Add commented `skip_unreleased` line to `DEFAULT_CONFIG` |
| `triggarr/templates/settings.html` | Web UI config editor | Add checkbox toggle in General section |
| `triggarr/web/routes.py` | Settings form handling | Parse `skip_unreleased` checkbox, pass to template context |
| `triggarr/state.py` | Cursor state persistence | **No changes** |
| `triggarr/clients/` | API clients | **No changes** |

## Cursor Behavior: No Changes Required

The cursor positions do NOT need special handling for skipped items. Here is why:

Every cycle rebuilds the filtered list fresh from a new API fetch:
1. Fetch all items from API
2. Filter to only valid items (monitored, released, etc.)
3. Cursor slices from the filtered list
4. Cursor advances by items-searched

Since the filtered list is rebuilt every cycle:
- A movie that gains a release date between cycles appears in the filtered list; the cursor naturally reaches it
- If the filtered list shrinks, the existing `if cursor >= len(items): cursor = 0` guard in `slice_batch` wraps safely
- Pass counters and wrap-around logging reference the filtered list length and continue working
- The "X of Y" dashboard display already shows position relative to current queue size

The `missing_count` and `cutoff_count` in state are cached before filtering (engine.py lines 219-221) and represent raw API counts. This is correct -- the dashboard should show total wanted count, not filtered count.

## Radarr Release Date Fields

Radarr movie objects from wanted/missing and wanted/cutoff APIs include:

| Field | Type | When Present |
|-------|------|-------------|
| `digitalRelease` | ISO 8601 string or null | Populated when digital release date is known |
| `physicalRelease` | ISO 8601 string or null | Populated when physical release date is known |
| `inCinemas` | ISO 8601 string or null | Populated when theatrical date is known |
| `status` | string | Always (`"announced"`, `"inCinemas"`, `"released"`, `"deleted"`) |

**Filtering logic:** A movie is considered released if EITHER `digitalRelease` OR `physicalRelease` is in the past. Movies with neither date set are skipped.

`inCinemas` is deliberately NOT used. A movie being in cinemas does not mean digital copies are available. Searching yields cam recordings, which is exactly what users want to avoid.

`status` is deliberately NOT used as the sole filter. Radarr's `status` field can lag behind actual availability. Using the actual date fields is more precise.

## Sonarr: Refactoring Existing Filter

The existing `filter_sonarr_episodes` combines two concerns:
1. Monitored check (`ep.get("monitored", False)`)
2. Air date check (`airDateUtc` must be in the past)

For the `skip_unreleased` toggle to work, these must be separated:

- `filter_monitored()` -- already exists as a separate function, used by Radarr. Reuse for Sonarr.
- `filter_unaired_episodes()` -- extracted from `filter_sonarr_episodes`. Applied conditionally based on `skip_unreleased`.

This refactor is backward-compatible: when `skip_unreleased=True` (the default), behavior is identical to current code. When `skip_unreleased=False`, only the monitored filter applies.

## Config Integration

### GeneralConfig Addition

```python
class GeneralConfig(BaseModel):
    # ... existing fields ...
    skip_unreleased: bool = True  # Skip unreleased movies and unaired episodes
```

Placed in `[general]` because it applies to both Radarr and Sonarr. A per-app toggle is unnecessary complexity.

### TOML Template Addition

```toml
[general]
# skip_unreleased = true   # Skip movies without digital/physical release and unaired episodes
```

### Settings UI Addition

A checkbox in the General section, following the existing enable/disable toggle pattern:

```html
<div>
    <label class="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" name="skip_unreleased"
               {% if skip_unreleased %}checked{% endif %}
               class="accent-triggarr-green w-4 h-4">
        <span class="text-sm">Skip Unreleased Media</span>
    </label>
    <p class="text-xs text-triggarr-muted mt-1">
        Skip movies without a digital/physical release date and episodes that haven't aired.
    </p>
</div>
```

### Settings Save Handler

Parse `skip_unreleased` from form data as checkbox (present = True, absent = False). Same pattern as existing `{name}_enabled` checkboxes in `save_settings` route.

## Patterns to Follow

### Pattern 1: Pure Filter Function

Each filter is a pure function: list in, filtered list out. Testable without mocks, composable.

```python
def filter_unreleased_movies(movies: list[dict]) -> list[dict]:
    """Filter out movies without a past digital or physical release date."""
    now = datetime.now(UTC)
    result: list[dict] = []
    for movie in movies:
        digital = movie.get("digitalRelease")
        physical = movie.get("physicalRelease")
        if _has_past_date(digital, now) or _has_past_date(physical, now):
            result.append(movie)
    return result


def _has_past_date(date_str: str | None, now: datetime) -> bool:
    """Check if a date string represents a past date."""
    if date_str is None:
        return False
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return False
    return dt <= now
```

### Pattern 2: Conditional Filter with Debug Logging

```python
# In run_radarr_cycle, after filter_monitored:
if settings.general.skip_unreleased:
    pre_count = len(missing)
    missing = filter_unreleased_movies(missing)
    skipped = pre_count - len(missing)
    if skipped > 0:
        logger.debug(
            "Radarr: Skipped {n} unreleased movies (missing queue)",
            n=skipped,
        )
```

### Pattern 3: Checkbox Form Pattern

Existing pattern in `save_settings` for boolean checkboxes. The `skip_unreleased` field follows the same approach as `{name}_enabled`:

```python
new_config["general"]["skip_unreleased"] = "skip_unreleased" in form
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Filtering After Cursor Slicing
Batch size becomes unpredictable. Cursor advances past valid items. Filter before slicing.

### Anti-Pattern 2: Using `inCinemas` as Release Indicator
In-cinema movies only have cam copies available. The point of skip-unreleased is to avoid cams.

### Anti-Pattern 3: Using `status` Field Alone
Radarr `status` can lag behind actual availability. Date fields are more precise.

### Anti-Pattern 4: Per-App Skip Toggle
Single `[general]` toggle is sufficient. Per-app doubles UI/config surface for no practical benefit.

### Anti-Pattern 5: Modifying `slice_batch` Logic
`slice_batch` is a pure, generic utility. Adding release-date awareness violates single responsibility and makes testing harder.

## Data Flow

### Radarr Cycle (skip_unreleased=True)

```
1. API fetch: get_wanted_missing() -> 200 movies
2. State: missing_count = 200 (raw, for dashboard)
3. filter_monitored() -> 180 movies
4. filter_unreleased_movies() -> 150 movies
5. slice_batch(150, cursor=45, batch=5) -> [45-49], cursor=50
6. search_movies() for each
7. save cursor=50
```

### Sonarr Cycle (skip_unreleased=True)

```
1. API fetch: get_wanted_missing() -> 500 episodes
2. State: missing_count = 500 (raw)
3. filter_monitored() -> 450 episodes
4. filter_unaired_episodes() -> 400 episodes
5. deduplicate_to_seasons() -> 80 seasons
6. slice_batch(80, cursor=20, batch=5) -> [20-24], cursor=25
7. search_season() for each
8. save cursor=25
```

## Suggested Build Order

Based on dependency analysis:

1. **Config model + TOML template** -- Add `skip_unreleased` to `GeneralConfig` and `DEFAULT_CONFIG`. Everything else depends on this. Tests: default value, TOML parsing with explicit true/false.

2. **Filter functions** -- Add `filter_unreleased_movies`, `_has_past_date`, and `filter_unaired_episodes` (extracted from `filter_sonarr_episodes`). All pure functions, fully testable with synthetic dicts. Tests: null dates, future dates, past dates, malformed dates, mixed scenarios.

3. **Engine integration** -- Wire filters into `run_radarr_cycle` and `run_sonarr_cycle` with conditional application. Add debug logging for skip counts. Tests: cycle with skip enabled/disabled, verify cursor behavior with filtered lists.

4. **Settings UI + save handler** -- Add checkbox to settings template, parse in `save_settings`, pass to template context. Tests: settings round-trip, checkbox state preservation.

## Sources

- Radarr movie fields (`digitalRelease`, `physicalRelease`, `inCinemas`): confirmed via [pycliarr docs](https://pycliarr.readthedocs.io/en/stable/source/pycliarr.api.radarr.html) and [Radarr API docs](https://radarr.video/docs/api/). Confidence: MEDIUM (multiple third-party libraries confirm fields exist; not verified against live API response).
- Sonarr `airDateUtc` field: confirmed by existing `filter_sonarr_episodes` in production code (engine.py line 163). Confidence: HIGH.
- All architecture decisions: based on direct analysis of the Triggarr codebase at v2.1. Confidence: HIGH.

---
*Architecture research for: Triggarr v2.2 -- Skip Unreleased Media*
*Researched: 2026-03-09*
