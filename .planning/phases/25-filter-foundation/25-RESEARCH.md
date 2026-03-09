# Phase 25: Filter Foundation - Research

**Researched:** 2026-03-09
**Domain:** Radarr release-date filtering, Pydantic config modeling, pure function design
**Confidence:** HIGH

## Summary

This phase adds a `skip_unreleased` boolean to `GeneralConfig` and implements a pure filter function that identifies unreleased Radarr movies based on `digitalRelease` and `physicalRelease` date fields. The codebase already has a near-identical pattern in `filter_sonarr_episodes()` (engine.py:145-173) which filters by air date using `datetime.fromisoformat()` with Z replacement. The new function follows the same structure but with different field names and inverted null-handling semantics (Sonarr skips null dates; Radarr passes them through per user decision).

No new dependencies are needed. The work is entirely within existing files (`models/config.py`, `config.py`) and a new filter function in `search/engine.py`. Phase 26 handles wiring the filter into the engine cycle and UI -- this phase is purely model + function + tests.

**Primary recommendation:** Follow the `filter_sonarr_episodes()` pattern exactly -- pure function taking `list[dict]`, returning `list[dict]`, with comprehensive edge-case tests covering null dates, past dates, future dates, and mixed scenarios.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Use `digitalRelease` and `physicalRelease` fields only (NOT `inCinemas` or `status`)
- A movie is "released" if either date is in the past (whichever comes first)
- Movies with null/missing dates for both fields pass through (searched, not blackholed)
- Date parsing uses `datetime.fromisoformat()` with Z replacement, matching existing Sonarr pattern
- Filter applies to Radarr missing queue ONLY -- cutoff queue items already have files
- Sonarr unaired-episode filtering (`filter_sonarr_episodes`) stays unconditional and unchanged
- `skip_unreleased: bool = True` on `GeneralConfig` in models/config.py
- Default: enabled (skip unreleased)

### Claude's Discretion
- Default config template presentation (commented vs active in DEFAULT_CONFIG)
- Filter function naming convention (following existing patterns)
- Logging verbosity for skipped items
- Test strategy and edge case coverage

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CFG-02 | Skip-unreleased setting persists in TOML config file with default enabled | Add `skip_unreleased: bool = True` to `GeneralConfig` model, add commented line to `DEFAULT_CONFIG` template. Pydantic + TOML round-trip already works for all existing fields. |
| FILT-01 | When enabled, Radarr missing-queue items are skipped if no digital or physical release date has passed | New pure filter function checks `digitalRelease` and `physicalRelease` fields. Skip when both are null-or-future. Pass when either is in the past. |
| FILT-02 | When enabled, Sonarr unaired episodes are skipped (existing behavior made conditional on toggle) | CONTEXT.md locks this: Sonarr filtering remains **unconditional and unchanged**. No new Sonarr filter logic added in this phase. The existing `filter_sonarr_episodes()` is not touched. |
| FILT-03 | Movies with null/missing release dates are still searched (not silently blackholed) | User decision: null/missing dates = pass through. The filter only skips movies where both dates are present AND both are in the future. |
| FILT-04 | Cutoff-unmet items are never filtered (already have files, proven released) | Filter function only applies to missing queue. Cutoff queue is structurally excluded -- Phase 26 will only call the filter on the missing list, not the cutoff list. This phase's function signature and docs make this clear. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | (existing) | Config model with `skip_unreleased` field | Already used for all config models. Adding a field is trivial. |
| datetime (stdlib) | 3.11+ | Date comparison for release dates | Already used in `filter_sonarr_episodes()`. Same `fromisoformat` + Z replacement pattern. |
| loguru | (existing) | Logging skipped items | Project standard. All engine functions use it. |

### Supporting
No new libraries needed. Everything is stdlib + existing dependencies.

### Alternatives Considered
None -- locked decisions eliminate alternatives.

## Architecture Patterns

### Recommended Project Structure
No new files needed. Changes go in existing files:
```
triggarr/
  models/config.py      # Add skip_unreleased field to GeneralConfig
  config.py             # Add commented line to DEFAULT_CONFIG template
  search/engine.py      # Add filter_unreleased_movies() function
tests/
  test_search.py        # Add filter tests (or new test_filter.py)
  test_config.py        # Add config persistence test
```

### Pattern 1: Pure Filter Function (follow `filter_sonarr_episodes`)
**What:** A standalone function that takes `list[dict]` and returns `list[dict]`, with no side effects except logging.
**When to use:** All item filtering in the search engine.
**Example:**
```python
# Source: existing pattern at triggarr/search/engine.py:145-173
def filter_unreleased_movies(movies: list[dict]) -> list[dict]:
    """Filter out Radarr movies that have not been released digitally or physically.

    A movie is considered released if either digitalRelease or physicalRelease
    is in the past. Movies with BOTH dates null/missing pass through (not blackholed).
    Movies with BOTH dates in the future are skipped.

    Args:
        movies: List of movie dicts from Radarr wanted/missing API.

    Returns:
        Movies eligible for searching (released or unknown release date).
    """
    now = datetime.now(UTC)
    result: list[dict] = []
    for movie in movies:
        digital = movie.get("digitalRelease")
        physical = movie.get("physicalRelease")

        # Both null/missing -- pass through (don't blackhole unknowns)
        if digital is None and physical is None:
            result.append(movie)
            continue

        # Check if either date is in the past
        released = False
        for date_str in (digital, physical):
            if date_str is None:
                continue
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue  # Unparseable date -- treat as if not set
            if dt <= now:
                released = True
                break

        if released:
            result.append(movie)
        else:
            logger.debug(
                "Radarr: Skipping unreleased movie {title}",
                title=movie.get("title", "unknown"),
            )

    return result
```

### Pattern 2: Config Field Addition
**What:** Adding a boolean field with default to `GeneralConfig` Pydantic model.
**When to use:** All new config options.
**Example:**
```python
# Source: existing pattern at triggarr/models/config.py:56-66
class GeneralConfig(BaseModel):
    """Global application settings."""
    log_level: str = "info"
    # ... existing fields ...
    skip_unreleased: bool = True  # Skip unreleased Radarr movies in missing queue
```

### Pattern 3: DEFAULT_CONFIG Template Line
**What:** Commented-out line in the TOML template for optional config values.
**When to use:** Config options with sensible defaults that most users won't change.
**Example:**
```python
# Source: existing pattern at triggarr/config.py:20-25
# In DEFAULT_CONFIG string, under [general] section:
# skip_unreleased = true    # Skip Radarr movies without a past digital/physical release date
```

### Anti-Patterns to Avoid
- **Using `inCinemas` or `status` field:** Locked decision -- only `digitalRelease` and `physicalRelease`.
- **Blackholing null dates:** Movies with no release date info MUST pass through per user decision.
- **Filtering cutoff queue:** Cutoff items already have files and must never be filtered.
- **Modifying `filter_sonarr_episodes`:** Sonarr filtering stays unconditional and unchanged.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Date parsing | Custom date parser | `datetime.fromisoformat()` with Z replacement | Already established pattern, handles ISO 8601 |
| Config persistence | Manual TOML writing | Pydantic model field + existing TOML infrastructure | Adding a field to the model is all that's needed |
| Timezone handling | Manual UTC offset math | `datetime.now(UTC)` comparison | Already used throughout codebase |

## Common Pitfalls

### Pitfall 1: Treating Null Dates as "Unreleased" (Blackholing)
**What goes wrong:** Movies with no release date metadata never get searched, even if they are available.
**Why it happens:** Tempting to assume no-date = unreleased. But Radarr metadata can be incomplete for indie/foreign films.
**How to avoid:** User decision is clear: both dates null = pass through. Only skip when dates ARE present AND both are in the future.
**Warning signs:** Test coverage missing the "both null" case.

### Pitfall 2: Filtering Cutoff Queue Items
**What goes wrong:** Movies in the cutoff queue (already have a file, want upgrade) get filtered out because they lack release date metadata.
**Why it happens:** Applying the filter to both queues instead of just missing.
**How to avoid:** The filter function itself is queue-agnostic. Phase 26 ensures it is only called on the missing queue. This phase's docstring and tests should make this clear.
**Warning signs:** Function being called on cutoff list in tests.

### Pitfall 3: Date Comparison Without Timezone Awareness
**What goes wrong:** Naive datetime comparison fails or produces wrong results.
**Why it happens:** `fromisoformat()` with Z replacement produces timezone-aware datetimes; comparing with naive `datetime.now()` raises TypeError.
**How to avoid:** Always use `datetime.now(UTC)` for the "now" reference. Already established in `filter_sonarr_episodes()`.
**Warning signs:** TypeError in date comparison tests.

### Pitfall 4: Unparseable Date Strings
**What goes wrong:** Radarr occasionally returns malformed date strings or empty strings.
**Why it happens:** Metadata quality varies across movie databases.
**How to avoid:** Wrap `fromisoformat()` in try/except for `ValueError` and `AttributeError` (matching Sonarr pattern). Treat unparseable as if the field were null.
**Warning signs:** Filter crashes on edge-case movie data.

### Pitfall 5: Forgetting `<= now` vs `< now`
**What goes wrong:** A movie released today (release date = today) gets skipped.
**Why it happens:** Using `>` instead of `>=` for the comparison, or `<` instead of `<=`.
**How to avoid:** Use `dt <= now` to consider "today" as released. The Radarr dates are full ISO timestamps (not just dates), so a movie released at midnight today will have a datetime in the past by midday.
**Warning signs:** Test for "release date is today" failing.

## Code Examples

### Existing Pattern: filter_sonarr_episodes (reference)
```python
# Source: triggarr/search/engine.py:145-173
def filter_sonarr_episodes(episodes: list[dict]) -> list[dict]:
    now = datetime.now(UTC)
    result: list[dict] = []
    for ep in episodes:
        if not ep.get("monitored", False):
            continue
        air_date_str = ep.get("airDateUtc")
        if air_date_str is None:
            continue  # Sonarr: null = skip (TBA)
        try:
            air_date = datetime.fromisoformat(air_date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if air_date > now:
            continue
        result.append(ep)
    return result
```

Key difference for Radarr filter: null dates = pass through (not skip).

### Existing Pattern: GeneralConfig field
```python
# Source: triggarr/models/config.py:56-66
class GeneralConfig(BaseModel):
    log_level: str = "info"
    hard_max_per_cycle: int = 0
    max_history_rows: int = 1000
    request_timeout: float = 30.0
    page_size: int = 50
    tracking_window_minutes: int = 60
    tracking_delay_seconds: int = 90
```

### Existing Pattern: DEFAULT_CONFIG commented line
```python
# Source: triggarr/config.py:20-25
# hard_max_per_cycle = 0   # 0 = unlimited; caps total items searched per app per cycle
# max_history_rows = 1000   # Maximum resolved rows kept in search history
```

### Test Factory Pattern
```python
# Source: tests/conftest.py:9-44
from tests.conftest import make_settings
settings = make_settings(general=GeneralConfig(skip_unreleased=True))
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Search all Radarr missing items | Filter by release dates before searching | v2.2 (this milestone) | Prevents cam recordings from being grabbed |

## Open Questions

1. **Function naming: `filter_unreleased_movies` vs `filter_radarr_unreleased`?**
   - What we know: Existing patterns use `filter_monitored` (generic) and `filter_sonarr_episodes` (app-specific).
   - Recommendation: Use `filter_unreleased_movies` -- it's Radarr-specific by nature (only Radarr has movie objects with these fields), and follows the `filter_<what>_<items>` naming pattern.

2. **Should the filter log a summary count or per-item?**
   - What we know: `filter_sonarr_episodes` does not log individual skips. The cycle function logs a summary.
   - Recommendation: Log per-item at DEBUG level (helpful for troubleshooting) and let the cycle function (Phase 26) log the aggregate count at INFO level.

3. **DEFAULT_CONFIG: commented or active?**
   - What we know: All optional fields with non-default values are commented in DEFAULT_CONFIG. `log_level` is the only active line under `[general]`.
   - Recommendation: Add as commented line (`# skip_unreleased = true`) since the default (true) is the desired behavior for most users. Only users who want to disable it need to uncomment and change to false.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (asyncio_mode=auto) |
| Config file | pyproject.toml |
| Quick run command | `uv run pytest tests/test_search.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CFG-02 | skip_unreleased field defaults to True, persists in TOML | unit | `uv run pytest tests/test_config.py -x -q -k skip_unreleased` | No -- Wave 0 |
| FILT-01 | Movies with future-only digital/physical dates are skipped | unit | `uv run pytest tests/test_search.py -x -q -k unreleased` | No -- Wave 0 |
| FILT-03 | Movies with null dates pass through | unit | `uv run pytest tests/test_search.py -x -q -k null` | No -- Wave 0 |
| FILT-04 | Cutoff items structurally excluded (docstring + no cutoff test calls filter) | unit | `uv run pytest tests/test_search.py -x -q -k unreleased` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_search.py tests/test_config.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] Tests for `filter_unreleased_movies()` in `tests/test_search.py` -- covers FILT-01, FILT-03, FILT-04
- [ ] Test for `skip_unreleased` config field persistence in `tests/test_config.py` -- covers CFG-02
- [ ] No new framework or fixture needs -- existing `make_settings` and test infrastructure sufficient

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `triggarr/search/engine.py` -- existing filter functions, date parsing patterns
- Codebase inspection: `triggarr/models/config.py` -- GeneralConfig model, Pydantic field patterns
- Codebase inspection: `triggarr/config.py` -- DEFAULT_CONFIG template, TOML persistence
- Codebase inspection: `tests/test_search.py`, `tests/test_config.py`, `tests/conftest.py` -- test patterns

### Secondary (MEDIUM confidence)
- `.planning/research/FEATURES.md`, `STACK.md`, `ARCHITECTURE.md`, `PITFALLS.md` -- prior milestone research on Radarr API fields and filtering logic

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all existing patterns
- Architecture: HIGH -- direct parallel to existing `filter_sonarr_episodes()` function
- Pitfalls: HIGH -- well-documented in prior research and user discussion; null-date handling explicitly decided

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable domain, no external API changes expected)
