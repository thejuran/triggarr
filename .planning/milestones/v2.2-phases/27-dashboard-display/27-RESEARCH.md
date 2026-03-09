# Phase 27: Dashboard Display - Research

**Researched:** 2026-03-09
**Domain:** FastAPI + htmx + Jinja2 dashboard UI (eligible vs total counts)
**Confidence:** HIGH

## Summary

This phase adds two dashboard indicators to app cards: (1) eligible vs total item counts for the missing queue, and (2) a skip-count indicator when items are being filtered out by `skip_unreleased`. The implementation is straightforward because the data pipeline is already in place -- the search engine already filters items and the state dict already stores `missing_count` (total). The gap is that the **post-filter count (eligible) is not stored**, so it never reaches the template.

The fix requires changes in three layers: engine stores eligible count in state, routes pass it to template context, and the app card template displays it. No new libraries, no architectural changes, no new API calls needed.

**Primary recommendation:** Add `missing_eligible` field to `AppState`, populate it in `run_radarr_cycle` after filtering, thread it through `_build_app_context`, and display it in `app_card.html` with a conditional skip indicator.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DASH-01 | Dashboard shows eligible vs total item counts per app | Engine stores eligible count in state after filtering; app card template shows "X eligible of Y total" |
| DASH-02 | Skip-count indicator visible on app cards when items are being skipped | Template conditionally renders skip badge when `missing_eligible < missing_count` and `skip_unreleased` is enabled |
</phase_requirements>

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | existing | Web framework + routes | Already used |
| Jinja2 | existing | HTML templates with htmx | Already used |
| htmx | existing | Partial updates via polling | Already used (5s poll on app cards) |
| Tailwind CSS v4 | existing | Styling | Already used |

### Supporting
No new libraries needed. This is purely a data-threading and template change.

## Architecture Patterns

### Data Flow (current)
```
Radarr API -> missing (raw list)
  -> filter_monitored() -> filter_unreleased_movies() -> slice_batch() -> search

State stores: missing_count = len(raw list)  [line 271 engine.py]
State does NOT store: len(filtered list)
```

### Data Flow (target)
```
Radarr API -> missing (raw list)
  -> state["radarr"]["missing_count"] = len(missing)          # total (already exists)
  -> filter_monitored(missing)
  -> filter_unreleased_movies(missing)  [if skip_unreleased]
  -> state["radarr"]["missing_eligible"] = len(missing)        # NEW: eligible count
  -> slice_batch() -> search
```

### Pattern 1: State field addition
**What:** Add `missing_eligible` to `AppState` TypedDict
**When to use:** After filtering, before slicing

The `AppState` TypedDict in `triggarr/state.py` line 36 needs one new optional field:
```python
class AppState(TypedDict, total=False):
    # ... existing fields ...
    missing_eligible: int | None  # Missing items after skip-unreleased filtering
```

### Pattern 2: Engine state update
**What:** Store eligible count after filtering completes
**Where:** `run_radarr_cycle` in `triggarr/search/engine.py`, after line 294

```python
# After filtering (line ~294 in engine.py):
missing = filter_monitored(missing)
if settings.general.skip_unreleased:
    missing = filter_unreleased_movies(missing)
state["radarr"]["missing_eligible"] = len(missing)  # NEW
```

For Sonarr, the eligible count comes after `filter_sonarr_episodes` + `deduplicate_to_seasons`. However, Sonarr's filtering is episode-based (air dates), not the `skip_unreleased` toggle. The skip indicator (DASH-02) should only show for Radarr when `skip_unreleased` is active, since Sonarr always filters unaired episodes regardless of the toggle.

**Decision point:** Should we also show eligible vs total for Sonarr? Sonarr already filters unaired episodes unconditionally. The requirement says "per app" so we should show it for both, but the skip indicator (DASH-02) should clarify it's about unreleased filtering specifically.

**Recommendation:** Show eligible/total for both apps (both already filter). Only show the "skipped" badge on Radarr when `skip_unreleased` is enabled AND items are actually being skipped. For Sonarr, show eligible/total counts but no special "skip" badge since its filtering is always-on and expected.

### Pattern 3: Route context threading
**What:** Pass `missing_eligible` and `skip_unreleased` through `_build_app_context`
**Where:** `triggarr/web/routes.py` line 95-135

```python
def _build_app_context(request: Request, app_name: str) -> dict | None:
    # ... existing code ...
    return {
        # ... existing fields ...
        "missing_eligible": app_state.get("missing_eligible"),
        "skip_unreleased": settings.general.skip_unreleased,  # needed for conditional display
    }
```

### Pattern 4: Template display
**What:** Show eligible/total in app card, with conditional skip badge
**Where:** `triggarr/templates/partials/app_card.html` lines 33-41

Current template shows:
```html
<span class="text-xs uppercase tracking-wide text-triggarr-muted">Missing</span>
<p class="text-sm font-medium">{{ app.missing_count if app.missing_count is not none else '&mdash;' }} items</p>
```

Target template pattern:
```html
<span class="text-xs uppercase tracking-wide text-triggarr-muted">Missing</span>
<p class="text-sm font-medium">
  {% if app.missing_eligible is not none and app.missing_count is not none %}
    {{ app.missing_eligible }} of {{ app.missing_count }} items
  {% elif app.missing_count is not none %}
    {{ app.missing_count }} items
  {% else %}
    &mdash;
  {% endif %}
</p>
{% if app.skip_unreleased and app.missing_eligible is not none and app.missing_count is not none and app.missing_eligible < app.missing_count %}
  <p class="text-xs text-amber-400">
    {{ app.missing_count - app.missing_eligible }} skipped (unreleased)
  </p>
{% endif %}
```

### Pattern 5: htmx polling (existing, no changes needed)
The app card already polls every 5 seconds via `hx-get` + `hx-trigger="every 5s"`. The eligible count will automatically refresh because `_build_app_context` reads from `app.state.triggarr_state` which is updated each search cycle.

### Anti-Patterns to Avoid
- **Computing eligible count in the template or route:** The count must be computed in the engine where the filtering happens. Computing it elsewhere would duplicate filter logic.
- **Adding a separate API endpoint for counts:** The existing polling mechanism already refreshes the card; no need for a separate endpoint.
- **Storing skip_unreleased in per-app state:** It's a global setting, pass it from settings, not state.
- **Showing skip indicator when skip_unreleased is disabled:** Would be confusing -- if the toggle is off, eligible should equal total.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Real-time count updates | WebSocket push | htmx polling (already in place) | 5s poll is sufficient for a dashboard; WebSocket adds complexity for no benefit |
| Eligible count computation | Separate counting pass | Store len() after filter_unreleased_movies in engine | Filter is already applied, just save the result |

## Common Pitfalls

### Pitfall 1: Eligible count not initialized until first search cycle
**What goes wrong:** App cards show missing_eligible as None until the first search cycle runs, creating a confusing display.
**Why it happens:** State only updates during `run_radarr_cycle`. Before first cycle, `missing_eligible` is not in state.
**How to avoid:** Template must handle None gracefully -- fall back to showing just the total count without eligible/total split. The template pattern above already handles this.
**Warning signs:** Dashboard shows "None of 42 items" instead of "42 items".

### Pitfall 2: Sonarr eligible count semantics
**What goes wrong:** Showing "X skipped (unreleased)" on Sonarr card when the skip_unreleased toggle only affects Radarr.
**Why it happens:** Sonarr filters by air date unconditionally (not controlled by `skip_unreleased` toggle).
**How to avoid:** Only show the "skipped (unreleased)" badge on Radarr. For Sonarr, show eligible/total but label the filter differently or omit the special badge.
**Warning signs:** User disables skip_unreleased but Sonarr still shows skipped items.

### Pitfall 3: State migration -- old state files missing new field
**What goes wrong:** Existing state.json files don't have `missing_eligible`, causing KeyError or display issues.
**Why it happens:** TypedDict with `total=False` means field is optional. `.get()` with default handles this.
**How to avoid:** Always use `app_state.get("missing_eligible")` with no required default. The `_merge_defaults` function in state.py handles shallow merge but new keys not in defaults are fine since TypedDict fields are optional.

### Pitfall 4: Skip indicator appears when no items are actually skipped
**What goes wrong:** Badge shows "0 skipped" when eligible == total.
**Why it happens:** Condition only checks `skip_unreleased` toggle without checking actual counts.
**How to avoid:** Template condition must check `missing_eligible < missing_count` before showing the badge.

## Code Examples

### Engine change (run_radarr_cycle, after line ~294)
```python
# Source: triggarr/search/engine.py line 292-294 (existing)
missing = filter_monitored(missing)
if settings.general.skip_unreleased:
    missing = filter_unreleased_movies(missing)
# NEW: Store eligible count after filtering
state["radarr"]["missing_eligible"] = len(missing)
```

### Engine change (run_sonarr_cycle, after line ~443)
```python
# Source: triggarr/search/engine.py line 442-443 (existing)
missing_episodes = filter_sonarr_episodes(missing_episodes)
missing_seasons = deduplicate_to_seasons(missing_episodes)
# NEW: Store eligible count (season-level, after dedup)
state["sonarr"]["missing_eligible"] = len(missing_seasons)
```

### Route context (add to _build_app_context return dict)
```python
# Source: triggarr/web/routes.py line 123-135
"missing_eligible": app_state.get("missing_eligible"),
"skip_unreleased": settings.general.skip_unreleased,
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Only total counts shown | Eligible vs total (this phase) | Phase 27 | Users see filtering impact |
| No filter feedback | Skip indicator badge | Phase 27 | Users know items are being skipped |

## Open Questions

1. **Sonarr eligible display label**
   - What we know: Sonarr always filters unaired episodes regardless of toggle. The skip_unreleased toggle only affects Radarr.
   - What's unclear: Should Sonarr show a similar "X filtered (unaired)" badge, or just the counts?
   - Recommendation: Show eligible/total counts for both apps. Only show "skipped (unreleased)" badge for Radarr. Sonarr's filtering is expected behavior and doesn't need a special indicator.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (asyncio_mode=auto) |
| Config file | pyproject.toml |
| Quick run command | `uv run pytest tests/test_search.py tests/test_web.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DASH-01 | Engine stores missing_eligible in state after filtering | unit | `uv run pytest tests/test_search.py -x -q -k eligible` | No -- Wave 0 |
| DASH-01 | Route passes missing_eligible to template context | unit | `uv run pytest tests/test_web.py -x -q -k eligible` | No -- Wave 0 |
| DASH-02 | Skip badge appears when eligible < total and skip_unreleased on | unit | `uv run pytest tests/test_web.py -x -q -k skip_indicator` | No -- Wave 0 |
| DASH-02 | No badge when skip_unreleased off or eligible == total | unit | `uv run pytest tests/test_web.py -x -q -k no_skip` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_search.py tests/test_web.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_search.py` -- add tests for `missing_eligible` being set in state during `run_radarr_cycle` and `run_sonarr_cycle`
- [ ] `tests/test_web.py` -- add tests for `_build_app_context` including `missing_eligible` and `skip_unreleased` in context, and app card rendering with skip indicator

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `triggarr/search/engine.py` -- filter logic and state updates
- Direct codebase inspection: `triggarr/state.py` -- AppState TypedDict definition
- Direct codebase inspection: `triggarr/web/routes.py` -- `_build_app_context` and partial endpoints
- Direct codebase inspection: `triggarr/templates/partials/app_card.html` -- current card template
- Direct codebase inspection: `triggarr/models/config.py` -- `skip_unreleased` setting definition

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies, all existing tech
- Architecture: HIGH - clear data flow, simple state field addition
- Pitfalls: HIGH - well-understood from codebase analysis (None handling, Sonarr semantics)

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable internal architecture)
