# Technology Stack

**Project:** Triggarr v2.2 -- Skip Unreleased Media
**Researched:** 2026-03-09
**Scope:** NEW capability only -- filtering unreleased media by release dates

## Recommendation: Zero New Dependencies

This feature requires **no new libraries or stack changes**. Everything needed is already in the existing stack (Python stdlib `datetime`, existing httpx clients, existing TOML config system). The codebase already has a working pattern for date-based filtering in `filter_sonarr_episodes()` that serves as the direct template for the Radarr equivalent.

## Radarr API Date Fields

**Source:** Radarr source code (`MovieResource.cs` on develop branch) -- HIGH confidence

The Radarr `/api/v3/wanted/missing` and `/api/v3/wanted/cutoff` endpoints return movie records with these release date fields:

| JSON Field | C# Type | Description | Can Be Null |
|------------|---------|-------------|-------------|
| `inCinemas` | `DateTime?` | Theatrical release date | Yes |
| `physicalRelease` | `DateTime?` | Physical media (DVD/Blu-ray) release date | Yes |
| `digitalRelease` | `DateTime?` | Digital/streaming release date | Yes |
| `releaseDate` | `DateTime?` | Computed "primary" release date (read-only aggregate) | Yes |

**Format:** ISO 8601 datetime strings, e.g. `"2024-01-15T00:00:00Z"`. All fields are nullable -- movies with unknown release dates will have `null` for the corresponding field.

**JSON naming convention:** Radarr uses camelCase serialization globally (C# PascalCase properties become camelCase in JSON). Confirmed by Go client struct tags (`json:"inCinemas"`, `json:"physicalRelease"`) and Python client implementations.

### Which Fields to Use for Skip Logic

Use `digitalRelease` and `physicalRelease` because these represent when a movie becomes available for download in acceptable quality. `inCinemas` is NOT useful for skip logic -- a movie in cinemas is not available for quality downloads (only cam recordings, which is exactly what we want to avoid).

**Decision:** A movie is searchable when at least one of `digitalRelease` or `physicalRelease` is non-null and in the past. Skip when:
- Both `digitalRelease` and `physicalRelease` are null (unknown release = assume unreleased), OR
- Both non-null dates are in the future, OR
- The only non-null date is in the future

In other words: `min(digitalRelease, physicalRelease)` must be in the past (considering only non-null values). If both are null, skip.

### Edge Case: Both Dates Null

Movies with no release date information (both `digitalRelease` and `physicalRelease` are null) should be **skipped** when the toggle is enabled. These are typically announced/pre-production titles with no availability timeline. Searching for them produces only cam recordings or mismarked content -- exactly the problem this feature solves.

### Do NOT Use `releaseDate`

The `releaseDate` field is a computed aggregate that Radarr derives internally. Its logic depends on `minimumAvailability` settings and may include `inCinemas` dates, which would defeat the purpose. Use `digitalRelease` and `physicalRelease` explicitly for full control.

## Sonarr API Date Fields

**Source:** Sonarr source code (`EpisodeResource.cs` on develop branch) -- HIGH confidence

The Sonarr `/api/v3/wanted/missing` and `/api/v3/wanted/cutoff` endpoints return episode records with:

| JSON Field | C# Type | Description | Can Be Null |
|------------|---------|-------------|-------------|
| `airDate` | `string` | Local air date (format: `"YYYY-MM-DD"`) | Yes |
| `airDateUtc` | `DateTime?` | UTC air date/time (ISO 8601) | Yes |

### Already Implemented -- Hardcoded in Existing Code

**The codebase already filters Sonarr episodes by air date.** The `filter_sonarr_episodes()` function in `triggarr/search/engine.py` (lines 145-173) already:
- Skips episodes where `airDateUtc` is `None` (TBA episodes)
- Skips episodes where `airDateUtc` is in the future
- Uses `datetime.fromisoformat()` with the `Z` -> `+00:00` replacement pattern

This means the Sonarr side of skip-unreleased is **already implemented as hardcoded behavior**. The v2.2 feature needs to:
1. Make this behavior conditional on the `skip_unreleased` setting (when disabled, allow unaired episodes through)
2. Add the equivalent Radarr filtering (which does not exist yet)

## Python Date Handling

### Pattern to Follow (Already Established)

The codebase has a proven date parsing pattern in `filter_sonarr_episodes()`:

```python
from datetime import UTC, datetime

# Parse ISO 8601 from *arr API responses
air_date = datetime.fromisoformat(air_date_str.replace("Z", "+00:00"))

# Compare against current time
now = datetime.now(UTC)
if air_date > now:
    # Skip -- not yet released
    continue
```

### Key Considerations

| Concern | Approach | Notes |
|---------|----------|-------|
| Timezone handling | Always use `datetime.now(UTC)` and parse with timezone info | Already established in codebase |
| `"Z"` suffix | Replace with `"+00:00"` before `fromisoformat()` | Python 3.11+ handles `Z` natively, but the replace pattern is already used and is safe |
| Null dates | Check for `None` before parsing | Both Radarr and Sonarr can return null for date fields |
| Invalid dates | Catch `ValueError` and `AttributeError` | Already handled in existing pattern |
| Date-only strings | Not an issue | Radarr returns full datetime; Sonarr's `airDate` is date-only but we use `airDateUtc` |

### Python 3.11+ `fromisoformat` Note

Python 3.11 expanded `datetime.fromisoformat()` to handle the `Z` suffix directly. Since Triggarr targets Python 3.13, the `.replace("Z", "+00:00")` is technically unnecessary but harmless. Keep it for consistency with the existing codebase pattern -- do not change the existing code just to remove the replace.

## Config Addition

One new boolean field on `GeneralConfig`:

```python
class GeneralConfig(BaseModel):
    skip_unreleased: bool = True  # Skip unreleased media during search cycles
```

In TOML:
```toml
[general]
skip_unreleased = true
```

**Default: `True`** (skip unreleased). This is the safe default -- users who want to search for unreleased content must explicitly opt out. The feature description in PROJECT.md confirms: "Default: enabled (skip unreleased)".

No new config sections, no new config models. Just one boolean.

## What NOT to Add

| Temptation | Why Not |
|------------|---------|
| `python-dateutil` | stdlib `datetime.fromisoformat()` handles all *arr date formats |
| `arrow` or `pendulum` | Overkill for simple UTC comparisons already handled by stdlib |
| New Pydantic models for movie dates | Items flow as `dict[str, Any]` through the pipeline -- adding typed models for 3 optional fields is unnecessary churn |
| Per-app `skip_unreleased` toggle | One toggle is sufficient. Wanting to search unreleased movies but not unaired episodes (or vice versa) is a niche case not worth the config complexity |
| Configurable "release date offset" (e.g., skip until N days after release) | Feature creep. The toggle is binary: released or not. Users wanting offset logic can disable the toggle |
| `releaseDate` field from Radarr | Computed aggregate that may include `inCinemas` -- defeats the purpose of avoiding cam recordings |

## Installation

No changes to `pyproject.toml`. No new packages.

```bash
# Nothing to install -- zero new dependencies
```

## Existing Dependencies That Cover Everything

| Existing Dependency | v2.2 Use | Notes |
|---------------------|----------|-------|
| Python stdlib `datetime` | Parse ISO 8601 dates, compare against UTC now | Already used in `filter_sonarr_episodes()` |
| Pydantic / pydantic-settings | One new `bool` field on `GeneralConfig` | Existing pattern |
| Jinja2 / htmx | Toggle control in settings UI | Existing pattern (same as per-app enable/disable) |

## Sources

- Radarr `MovieResource.cs` (release date fields): https://github.com/Radarr/Radarr/blob/develop/src/Radarr.Api.V3/Movies/MovieResource.cs (HIGH confidence -- primary source)
- Radarr `Movie.cs` (metadata model): https://github.com/Radarr/Radarr/blob/develop/src/NzbDrone.Core/Movies/Movie.cs (HIGH confidence)
- Sonarr `EpisodeResource.cs` (air date fields): https://github.com/Sonarr/Sonarr/blob/develop/src/Sonarr.Api.V3/Episodes/EpisodeResource.cs (HIGH confidence -- primary source)
- Go Radarr client confirming camelCase JSON tags: https://pkg.go.dev/github.com/SkYNewZ/radarr (MEDIUM confidence -- third-party but confirms naming)
- Radarr API docs: https://radarr.video/docs/api/ (HIGH confidence -- official docs)
- Existing codebase `triggarr/search/engine.py` lines 145-173: `filter_sonarr_episodes()` (HIGH confidence -- verified in source)

---
*Stack research for: Triggarr v2.2 -- Skip Unreleased Media*
*Researched: 2026-03-09*
