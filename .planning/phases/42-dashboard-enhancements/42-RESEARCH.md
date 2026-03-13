# Phase 42: Dashboard Enhancements - Research

**Researched:** 2026-03-13
**Domain:** FastAPI + htmx + Jinja2 dashboard UI, aiosqlite queries
**Confidence:** HIGH

## Summary

This phase adds three dashboard features using the project's established stack: a health summary card, tag warning badges on app cards, and a per-instance stats filter dropdown. All three surface data that already exists in the application -- connection state in `triggarr_state`, tag resolution results in the search engine, and instance-scoped DB stats via `get_dashboard_stats(instance_id=...)`.

The main engineering challenge is the tag warning data path. Tag resolution currently happens inside `run_radarr_cycle` / `run_sonarr_cycle` and results are only logged, not stored. The tag resolution outcome (which tags are missing) needs to flow into the per-instance state dict (`ist`) so that `_build_app_context()` can pass it to templates. The health summary and stats filter are straightforward -- they compose existing data into new UI elements using established htmx partial patterns.

**Primary recommendation:** Store tag resolution state in `ist` (the per-instance state dict) during each search cycle, then surface all three features through new/extended htmx partials following the project's existing polling pattern.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Health summary card placed at top of dashboard, above existing app cards
- Shows connected/disconnected counts only (e.g., "3 connected, 1 down") -- no per-instance detail in the summary
- Always visible, even when all instances are healthy ("4/4 connected" in green)
- Disabled instances excluded from the count -- only enabled instances are tracked
- Uses existing htmx polling pattern for live updates
- Tag warning appears directly on the affected instance's app card (not in health summary or separate section)
- Checked/updated each search cycle -- tag resolution already happens, just surface the found/not-found result
- Shows which tag field is broken: "Warning Missing tag 'x' not found" or "Warning Cutoff tag 'y' not found"
- If both tags not found on same instance, combined single line: "Warning Tags not found: 'x' (missing), 'y' (cutoff)"
- Amber color scheme (bg-amber-500/20 text-amber-400) consistent with existing warning patterns
- Filter dropdown added above existing stats row -- default "All instances" shows aggregate (current behavior)
- Flat list: "All instances", "Radarr / Main", "Radarr / 4K", "Sonarr / Main", etc. -- no app-type grouping
- Dropdown change triggers htmx GET to `/partials/stats-row?instance=X`, swaps stats row content
- When filtered to a single instance, hide irrelevant cards (Radarr -> no Episodes card, Sonarr -> no Movies card)
- Uses existing `get_dashboard_stats(instance_id=...)` DB function -- already supports instance scoping

### Claude's Discretion
- Exact card spacing and responsive breakpoints
- htmx polling interval for health summary card (5s or 30s)
- How to persist the selected instance filter across polls (hx-vals, hidden input, or query param)
- Stats row grid adjustment when cards are hidden (3-col vs 4-col)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INST-07 | Dashboard shows an instance health summary card (connected/disconnected count) | Health summary computed from `triggarr_state` connection booleans; new partial + route handler |
| TAG-05 | Dashboard shows a warning badge when a configured tag is not found in the *arr instance | Tag resolution state stored in `ist` dict during search cycle; surfaced via `_build_app_context()` to `app_card.html` |
| OBS-03 | Per-instance effectiveness stats (grab rate, lifetime counts) displayed on dashboard | `get_dashboard_stats(instance_id=...)` already supports scoping; add dropdown filter + query param to stats row partial |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | current | Web framework + route handlers | Already in use throughout project |
| Jinja2 | current | HTML templating with htmx partials | Already in use, all templates are Jinja2 |
| htmx | CDN | Partial HTML swapping for live updates | Already loaded in `base.html`, all partials use `hx-get`/`hx-swap` |
| Tailwind CSS v4 | current | Utility-first CSS styling | Already configured with `triggarr-*` custom colors |
| aiosqlite | current | Async SQLite queries for stats | Already used for `get_dashboard_stats()` |

### Supporting
No new libraries needed. All features use existing dependencies.

## Architecture Patterns

### Recommended Project Structure
```
triggarr/
├── web/routes.py              # Add health_summary partial route, extend stats-row route with ?instance= param
├── templates/
│   ├── dashboard.html         # Add health summary include above app cards, add stats filter dropdown
│   └── partials/
│       ├── health_summary.html  # NEW: health summary card partial
│       ├── app_card.html        # EXTEND: add tag warning badge section
│       ├── stats_row.html       # EXTEND: handle hidden cards when instance-filtered
│       └── stats_filter.html    # NEW: instance filter dropdown (or inline in dashboard.html)
├── search/engine.py           # Store tag resolution state in ist dict
└── state.py                   # AppState TypedDict: add tag warning fields
```

### Pattern 1: Health Summary from State
**What:** Compute connected/disconnected counts by iterating `triggarr_state` for all enabled instances.
**When to use:** Dashboard rendering and health summary partial endpoint.
**Example:**
```python
# In routes.py -- build health summary context
def _build_health_summary(request: Request) -> dict:
    settings = request.app.state.settings
    state = request.app.state.triggarr_state
    connected = 0
    disconnected = 0
    for app_name in ("radarr", "sonarr"):
        for inst_name in settings.get_enabled_instances(app_name):
            ist = state.get(app_name, {}).get(inst_name, {})
            if ist.get("connected") is True:
                connected += 1
            else:
                disconnected += 1
    return {"connected": connected, "disconnected": disconnected, "total": connected + disconnected}
```

### Pattern 2: Tag State in ist Dict
**What:** Store tag resolution outcomes in the per-instance state dict during search cycles.
**When to use:** After tag resolution in `run_radarr_cycle` / `run_sonarr_cycle`.
**Example:**
```python
# In search/engine.py -- after tag resolution block
# Clear previous tag warnings at start of cycle
ist["tag_warnings"] = []

if instance_config.missing_tag:
    missing_tag_id = resolve_tag_id(instance_config.missing_tag, tags)
    if missing_tag_id is None and tag_fetch_ok:
        ist["tag_warnings"].append({"tag": instance_config.missing_tag, "field": "missing"})
        # ... existing warning log ...

if instance_config.cutoff_tag:
    cutoff_tag_id = resolve_tag_id(instance_config.cutoff_tag, tags)
    if cutoff_tag_id is None and tag_fetch_ok:
        ist["tag_warnings"].append({"tag": instance_config.cutoff_tag, "field": "cutoff"})
```

### Pattern 3: Stats Filter via Query Param
**What:** Add `?instance=X` query param to stats-row partial endpoint; pass through htmx `hx-vals`.
**When to use:** Instance filter dropdown on dashboard.
**Example:**
```python
# In routes.py -- extend partial_stats_row
@router.get("/partials/stats-row", response_class=HTMLResponse)
async def partial_stats_row(request: Request) -> HTMLResponse:
    instance_param = request.query_params.get("instance")
    instance_id = instance_param if instance_param else None
    stats = await get_dashboard_stats(request.app.state.db, instance_id=instance_id)
    # ...pass instance_id to template for card visibility logic
```

### Pattern 4: htmx Dropdown Swap
**What:** `<select>` with `hx-get` and `hx-include` to swap stats row on change.
**When to use:** Instance filter dropdown.
**Example:**
```html
<select name="instance"
        hx-get="/partials/stats-row"
        hx-target="#stats-row"
        hx-swap="outerHTML"
        hx-include="this"
        class="bg-triggarr-card border border-triggarr-border rounded text-sm px-2 py-1 text-white">
  <option value="">All instances</option>
  {% for inst in all_instances %}
  <option value="{{ inst.id }}">{{ inst.label }}</option>
  {% endfor %}
</select>
```

### Pattern 5: Preserving Filter Across Polls
**What:** The stats row polls every 30s via `hx-trigger="every 30s"`. The selected instance filter must persist across polls.
**Recommendation:** Use `hx-include` on the stats row div to include the dropdown's current value in each poll request. This is the cleanest htmx approach -- no hidden inputs or JS needed.
**Example:**
```html
<div id="stats-row"
     hx-get="/partials/stats-row"
     hx-trigger="every 30s"
     hx-swap="outerHTML"
     hx-include="[name='instance']">
```
**Caveat:** The dropdown lives OUTSIDE the stats row div (above it), so `hx-include` with a CSS selector targeting the dropdown by name will work. The dropdown itself must NOT be inside the swapped element, or it will reset on each poll.

### Anti-Patterns to Avoid
- **Storing tag warnings in settings/config:** Tag state is runtime-only, not configuration. Store in `triggarr_state` (the `ist` dict), not in `InstanceConfig`.
- **Separate API endpoint for health data:** The health summary is computed from in-memory state, not a DB query. A simple helper function called during template rendering is sufficient.
- **JavaScript-heavy filter logic:** Use htmx `hx-get` with query params. No custom JS needed for the dropdown filter.
- **Rebuilding stats row HTML in two different templates:** Keep one `stats_row.html` partial that handles both filtered and aggregate views via template conditionals.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Live polling | Custom WebSocket or JS timer | htmx `hx-trigger="every Ns"` | Already established in all existing partials |
| Instance enumeration | Custom config parser | `settings.get_enabled_instances(app_name)` | Already handles enabled/disabled filtering |
| Stats scoping | Custom SQL queries | `get_dashboard_stats(instance_id=...)` | Already accepts optional instance_id parameter |
| Card ID generation | Manual string cleaning | `_sanitize_card_id()` | Already handles special characters for HTML id safety |

## Common Pitfalls

### Pitfall 1: Dropdown Reset on Stats Row Poll
**What goes wrong:** If the instance filter dropdown is placed inside the stats row div, it gets replaced on every 30s poll, resetting the user's selection.
**Why it happens:** htmx `outerHTML` swap replaces the entire target element.
**How to avoid:** Place the dropdown OUTSIDE the `#stats-row` div. Use `hx-include="[name='instance']"` on the stats row to include the dropdown value in poll requests.
**Warning signs:** User reports filter keeps resetting every 30 seconds.

### Pitfall 2: Tag Warnings Before First Cycle
**What goes wrong:** Tag warnings are empty until the first search cycle runs, even if tags are misconfigured.
**Why it happens:** Tag resolution only runs during search cycles, not at startup.
**How to avoid:** This is acceptable behavior -- document it. The app card already shows "Waiting..." before first cycle. Tag warnings will appear after the first cycle completes.
**Warning signs:** User sees no warning immediately after configuring a bad tag name.

### Pitfall 3: State Dict Keys Not in TypedDict
**What goes wrong:** Adding `tag_warnings` to the `ist` dict without updating `AppState` TypedDict causes type checker warnings.
**Why it happens:** `AppState` is a `TypedDict` that defines expected keys.
**How to avoid:** Add `tag_warnings` field to `AppState` in `state.py`.

### Pitfall 4: Instance ID Mismatch Between Config and DB
**What goes wrong:** Stats filter shows wrong data because instance_id in `lifetime_stats` doesn't match the instance name from settings.
**Why it happens:** Instance names are case-sensitive. DB was seeded with "Default" (capital D).
**How to avoid:** Use exact instance names from `settings.get_enabled_instances()` for both the dropdown options and the query parameter. The DB `instance_id` column matches instance names exactly.

### Pitfall 5: Health Summary Counting Instances Not Yet Checked
**What goes wrong:** New instances (never cycled) show as "disconnected" because `connected` is `None`.
**Why it happens:** `_default_instance_state()` doesn't set `connected`, so it defaults to `None`.
**How to avoid:** Treat `connected=None` as a separate "pending" state, not as disconnected. Count only `True`/`False` values. Display "3 connected, 1 down" only for instances with definitive state. Alternatively, count `None` as disconnected since the user decided "disabled instances excluded" -- but `None` means "enabled but not yet checked", which is different from "checked and failed".

### Pitfall 6: Hiding Stats Cards Changes Grid Layout
**What goes wrong:** Hiding the Movies or Episodes card when filtering to a single instance type breaks the 4-column grid alignment.
**Why it happens:** Tailwind `grid-cols-4` expects 4 children; with 3 visible, the layout shifts.
**How to avoid:** Adjust grid classes based on visible card count. Use `grid-cols-2 md:grid-cols-3` when one card is hidden, or keep 4-column grid and replace the hidden card with an empty placeholder.

## Code Examples

### Health Summary Partial Template
```html
<!-- partials/health_summary.html -->
<div id="health-summary"
     hx-get="{{ request.url_for('partial_health_summary') }}"
     hx-trigger="every 5s"
     hx-swap="outerHTML"
     class="bg-triggarr-card rounded-lg border border-triggarr-border p-4 mb-4">
  <div class="flex items-center gap-3">
    <span class="text-xs uppercase tracking-wide text-triggarr-muted">Instance Health</span>
    {% if health.disconnected == 0 %}
      <span class="text-sm font-medium text-triggarr-green">{{ health.total }}/{{ health.total }} connected</span>
    {% else %}
      <span class="text-sm font-medium">
        <span class="text-triggarr-green">{{ health.connected }} connected</span>,
        <span class="text-red-400">{{ health.disconnected }} down</span>
      </span>
    {% endif %}
  </div>
</div>
```

### Tag Warning Badge in App Card
```html
<!-- Inside app_card.html, after the header div -->
{% if app.tag_warnings %}
  <div class="bg-amber-500/20 text-amber-400 text-xs px-3 py-1.5 rounded mb-3">
    {% if app.tag_warnings | length == 1 %}
      &#9888; {{ app.tag_warnings[0].field | capitalize }} tag '{{ app.tag_warnings[0].tag }}' not found
    {% else %}
      &#9888; Tags not found: '{{ app.tag_warnings[0].tag }}' ({{ app.tag_warnings[0].field }}), '{{ app.tag_warnings[1].tag }}' ({{ app.tag_warnings[1].field }})
    {% endif %}
  </div>
{% endif %}
```

### Extending _build_app_context for Tag Warnings
```python
# In routes.py -- add to _build_app_context return dict
return {
    # ... existing keys ...
    "tag_warnings": app_state.get("tag_warnings", []),
}
```

### Stats Row with Instance Awareness
```python
# In routes.py -- extend partial_stats_row
@router.get("/partials/stats-row", response_class=HTMLResponse)
async def partial_stats_row(request: Request) -> HTMLResponse:
    instance_param = request.query_params.get("instance")
    instance_id = instance_param if instance_param else None
    stats = await get_dashboard_stats(request.app.state.db, instance_id=instance_id)
    time_to_grab = _format_duration(stats["avg_time_to_grab_seconds"])

    # Determine which app type this instance belongs to (for card visibility)
    instance_app_type = None
    if instance_id:
        settings = request.app.state.settings
        for app_name in ("radarr", "sonarr"):
            if instance_id in getattr(settings, app_name):
                instance_app_type = app_name
                break

    return templates.TemplateResponse(
        request=request,
        name="partials/stats_row.html",
        context={
            "stats": stats,
            "time_to_grab": time_to_grab,
            "instance_app_type": instance_app_type,
        },
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Flat state (single instance) | Nested per-instance state | v2.3 Phase 33 | All state lookups use `state[app][instance]` |
| `lifetime_stats` single PK | Composite `(app, instance_id)` PK | v2.3 Phase 34 (migration v7) | Stats already support per-instance queries |
| No tag filtering | Tag filtering with `resolve_tag_id()` | v2.3 Phase 35-36 | Tag resolution runs each cycle, results logged but not stored in state |

## Open Questions

1. **Health summary polling interval: 5s or 30s?**
   - What we know: App cards poll at 5s, stats row at 30s. Health state changes are driven by search cycles (minutes apart).
   - What's unclear: Whether 5s is worth the overhead for something that changes infrequently.
   - Recommendation: Use 30s. Health state only changes when a search cycle runs (every N minutes). 5s polling would create unnecessary requests. The app cards already show per-instance connection status at 5s if users need immediate feedback.

2. **How to handle `connected=None` in health count?**
   - What we know: `None` means "enabled but never checked" (fresh instance). The user decided disabled instances are excluded.
   - What's unclear: Whether `None` should count as disconnected or be a third state.
   - Recommendation: Show as "pending" -- neither connected nor disconnected. Display as "3 connected, 1 pending" or simply exclude from count until first check. This is more honest than counting as disconnected.

3. **Instance filter dropdown: what value identifies an instance?**
   - What we know: Instance names are unique within an app type but could overlap across app types (e.g., both Radarr and Sonarr could have a "Main" instance).
   - What's unclear: Whether to use instance_name alone or a compound key.
   - Recommendation: Use compound key format `{app_type}/{instance_name}` (e.g., `radarr/Main`) in the dropdown value. Parse in the route handler. This avoids ambiguity. The DB `instance_id` column stores just the instance name, but queries already filter by app via the `app` column in `search_history`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (asyncio_mode=auto) |
| Config file | `pyproject.toml` |
| Quick run command | `uv run pytest tests/test_web.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INST-07 | Health summary card shows connected/disconnected counts | unit | `uv run pytest tests/test_web.py -x -q -k health_summary` | Wave 0 |
| TAG-05 | Tag warning badge appears on app card when tag not found | unit | `uv run pytest tests/test_web.py -x -q -k tag_warning` | Wave 0 |
| OBS-03 | Stats row filters by instance when dropdown selected | unit | `uv run pytest tests/test_web.py -x -q -k stats_instance` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_web.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] Health summary partial tests in `tests/test_web.py` -- covers INST-07
- [ ] Tag warning rendering tests in `tests/test_web.py` -- covers TAG-05
- [ ] Instance-filtered stats partial tests in `tests/test_web.py` -- covers OBS-03
- [ ] Tag warning state storage tests in `tests/test_search.py` -- covers TAG-05 data path

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `triggarr/web/routes.py`, `triggarr/db.py`, `triggarr/search/engine.py`, `triggarr/state.py`
- Codebase inspection: `triggarr/templates/dashboard.html`, `triggarr/templates/partials/app_card.html`, `triggarr/templates/partials/stats_row.html`
- Codebase inspection: `triggarr/models/config.py` -- InstanceConfig with tag fields

### Secondary (MEDIUM confidence)
- htmx `hx-include` behavior for cross-element value inclusion -- well-established htmx pattern

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all existing project dependencies, no new libraries
- Architecture: HIGH - extends established htmx partial pattern used throughout the project
- Pitfalls: HIGH - identified from direct code inspection of state management and template rendering
- Tag data path: HIGH - verified that tag resolution results are currently logged but not stored in state

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable -- internal project patterns, no external dependency changes)
