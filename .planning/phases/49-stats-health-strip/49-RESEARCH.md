# Phase 49: Stats & Health Strip - Research

**Researched:** 2026-04-13
**Domain:** Jinja2 templates, Tailwind CSS v4, htmx partials, FastAPI route handlers
**Confidence:** HIGH

## Summary

Phase 49 restructures two existing htmx-polled dashboard partials: the health summary (full-width card becomes a compact one-line strip) and the stats row (flat grid becomes a hero Grab Rate card with per-app bars, plus elevated stat cards). All backend data is already computed and available -- `_build_health_summary()` returns connected/disconnected/pending counts, and `get_dashboard_stats()` returns `overall_rate`, per-app rates (`radarr_rate`, `sonarr_rate`, `lidarr_rate`), lifetime counts, and avg time-to-grab. No new endpoints or data shapes are needed.

The implementation is purely template restructuring plus a small CSS addition (`.mini-bar` styles in `input.css`). The existing htmx polling (`hx-trigger="every 30s"`) and partial swap pattern continues unchanged. The only discretionary backend consideration is whether to track a "last sync" timestamp for the health strip -- the simplest approach uses the htmx poll interval as a proxy.

**Primary recommendation:** Implement as 2-3 plans: (1) health strip replacement + CSS mini-bar addition, (2) hero Grab Rate card + card elevation, with tests validating the HTML structure of both partials.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Health strip is NOT a card -- bare `<div class="flex items-center justify-between text-xs mb-4 px-1">` above stats grid
- D-02: Colored dots (green connected, red disconnected, gray/border pending) with bold count + label, flex layout with gap-4
- D-03: Replace existing `partials/health_summary.html`, keep same htmx polling endpoint and trigger
- D-05: Grab Rate card uses `md:col-span-2` in `grid-cols-2 md:grid-cols-5` grid
- D-06: Subtle gradient overlay `absolute inset-0 bg-gradient-to-br from-triggarr-green/5 to-transparent`
- D-07: Headline number `text-4xl font-bold leading-none` with `%` in `text-2xl text-triggarr-muted`
- D-08: `.mini-bar` CSS: `height: 6px; border-radius: 3px; background: #334155; overflow: hidden;` with inner span
- D-09: Bar row layout: label `text-[11px] w-12 font-medium`, bar `flex-1`, percentage `text-[11px] text-triggarr-muted w-8 text-right`, flex with gap-3
- D-10: Hero card always `col-span-2`, always shows overall rate, per-app bars only for types with data
- D-11: Badge `text-[10px] px-2 py-0.5 rounded-full` top-right of Grab Rate card
- D-14: App colors -- Radarr: orange-400/#fb923c, Sonarr: blue-400/#60a5fa, Lidarr: green-400/#4ade80
- D-15: Colors via inline styles (`style="width: N%; background: #hex"`), not Tailwind classes
- D-16: `shadow-sm` on ALL stat cards
- D-17: Existing card pattern gets `shadow-sm` appended; hero card uses `p-5`
- D-18: Instance filter dropdown remains functional, existing hide/show behavior unchanged
- D-19: Per-app bars in hero card show all app bars regardless of filter

### Claude's Discretion
- "Last sync" timestamp computation approach (D-04)
- Exact health badge threshold values (D-12 recommends >=70% Healthy, >=40% Warn, <40% Critical)
- No-data badge behavior (D-13)
- Whether to highlight the filtered app's bar in the hero card (D-19)
- Test file structure (extend existing test or new file)
- Whether Albums card needs Lidarr-specific label treatment

### Deferred Ideas (OUT OF SCOPE)
- Sparkline trend chart in Grab Rate card (FUT-01)
- App card shadow-sm and hover elevation (Phase 50 scope)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STATS-01 | Compact one-line health strip with N connected/disconnected/pending + Last sync timestamp | Existing `_build_health_summary()` already returns counts; template replacement in `health_summary.html`; mockup L195-212 is exact spec |
| STATS-02 | Grab Rate card spans 2 grid columns with text-4xl headline | Existing `stats.overall_rate` already computed; `md:col-span-2` in existing grid; mockup L217-243 |
| STATS-03 | Colored health badge (Healthy/Warn/Critical) thresholded on overall rate | Simple Jinja conditional on `stats.overall_rate`; threshold values at Claude's discretion |
| STATS-04 | Per-app grab rates as color-coded horizontal bars | Existing `stats.radarr_rate`, `stats.sonarr_rate`, `stats.lidarr_rate` available; `.mini-bar` CSS needed |
| STATS-05 | Subtle shadow-sm elevation on all stat cards | Append `shadow-sm` to existing card class strings in `stats_row.html` |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.11+, ruff linting (E, F, I, UP, B, SIM), line length 120
- SecretStr for API keys (not relevant to this phase but must not regress)
- Loguru for logging (not print/logging module)
- pytest-asyncio with asyncio_mode=auto
- CSS rebuild: `uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css`
- Tests: `uv run pytest tests/ -x -q`
- Lint: `uv run ruff check triggarr/ tests/`

## Standard Stack

No new libraries needed. This phase modifies existing files only.

### Core (already in project)
| Library | Purpose | Relevance |
|---------|---------|-----------|
| FastAPI + Jinja2 | Template rendering | Route handlers return rendered partials [VERIFIED: codebase] |
| htmx | Partial swap + polling | `hx-get` + `hx-trigger="every 30s"` pattern continues unchanged [VERIFIED: codebase] |
| Tailwind CSS v4 | Utility classes | `@theme` tokens in `input.css`, `shadow-sm` is a built-in utility [VERIFIED: codebase] |

**Installation:** None required. No new dependencies.

## Architecture Patterns

### Existing Project Structure (files modified)
```
triggarr/
  templates/
    partials/
      health_summary.html    # REPLACE contents (strip markup)
      stats_row.html          # RESTRUCTURE (hero card + elevation)
    dashboard.html            # NO CHANGES (includes stay same)
  static/css/
    input.css                 # ADD .mini-bar styles
    output.css                # REBUILD after input.css change
  web/
    routes.py                 # MINOR: possibly add last_sync to health context
tests/
  test_ui_foundations.py      # REFERENCE pattern for new test file
```

### Pattern 1: htmx Partial Replacement
**What:** Each dashboard section is a self-contained HTML partial with its own `hx-get` endpoint and `hx-trigger` for polling. The outer `<div>` has `id`, `hx-get`, `hx-trigger`, and `hx-swap="outerHTML"`. [VERIFIED: codebase -- health_summary.html and stats_row.html both follow this]
**When to use:** All dashboard sections.
**Key constraint:** The outermost element of the partial MUST have the same `id` as the `hx-target` or be the swap target itself (outerHTML). Changing the root element's id would break htmx polling.

### Pattern 2: Template Data Flow
**What:** Route handler computes data dict, passes to `templates.TemplateResponse` as context. Template accesses via Jinja2 variables. [VERIFIED: codebase]
**Example:**
```python
# routes.py -- partial_health_summary
health = _build_health_summary(request)
return templates.TemplateResponse(
    request=request,
    name="partials/health_summary.html",
    context={"health": health},
)
```
The health dict already contains `connected`, `disconnected`, `pending`, `total`. No changes needed for the strip -- just render differently.

### Pattern 3: Test Pattern (Phase 48 style)
**What:** TestClient against a minimal FastAPI app with mocked state. Assert HTML fragments via string matching on `response.text`. [VERIFIED: codebase -- test_ui_foundations.py]
**Key details:**
- Fixture `test_app` builds full app with real DB (aiosqlite in tmp_path), mocked scheduler/clients
- Tests use `client.get("/")` for dashboard or `client.get("/partials/health-summary")` for direct partial
- Assertions: `assert "class-name" in response.text`, `assert "text-content" in response.text`

### Anti-Patterns to Avoid
- **Changing htmx endpoint URLs:** The health strip replaces `health_summary.html` content but must keep the same `hx-get` URL (`/partials/health-summary`) and `id="health-summary"`. Breaking these breaks live polling.
- **Adding new grid wrapper divs:** The stats_row.html root `<div id="stats-row">` must stay as the grid container. Don't wrap it in another div.
- **Hardcoding bar widths in Tailwind:** Per-app bar widths are dynamic percentages. Must use inline `style="width: N%"` -- Tailwind's `w-[N%]` won't work with Jinja variables in Tailwind v4 without safelist.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Horizontal progress bars | Canvas/SVG chart library | CSS `.mini-bar` with width% | 6px bars are trivially CSS; a charting lib would be massive overkill [VERIFIED: mockup uses pure CSS] |
| Health badge thresholds | Complex state machine | Simple Jinja if/elif/else | Three tiers with static thresholds need no library |
| Relative timestamps | moment.js or similar | Server-side string in Python | "Last sync 2s ago" can be computed at render time from state; no client-side JS needed |

## Common Pitfalls

### Pitfall 1: Grid column math with instance filtering
**What goes wrong:** When filtered to a single app type, some stat cards are hidden. If the grid stays `md:grid-cols-5`, remaining cards don't fill evenly.
**Why it happens:** The existing code already handles this with `{% if instance_app_type %}md:grid-cols-3{% else %}md:grid-cols-5{% endif %}`. The hero card's `md:col-span-2` works in both cases.
**How to avoid:** Keep the existing conditional grid column logic. Test with and without instance filter. [VERIFIED: existing stats_row.html L6]
**Warning signs:** Cards appearing at wrong widths on filtered view.

### Pitfall 2: Health strip htmx id mismatch
**What goes wrong:** If the new strip markup changes the root element's `id` from `health-summary`, htmx `hx-swap="outerHTML"` will fail to find the target on subsequent polls.
**How to avoid:** Keep `id="health-summary"` on the root div. Keep `hx-get`, `hx-trigger`, and `hx-swap` attributes identical.
**Warning signs:** Health strip stops updating after first poll cycle.

### Pitfall 3: Mini-bar CSS not compiled into output.css
**What goes wrong:** Adding `.mini-bar` to `input.css` but forgetting to rebuild `output.css` means styles won't apply.
**How to avoid:** Run `uv run tailwindcss -i triggarr/static/css/input.css -o triggarr/static/css/output.css` after editing input.css. The `.mini-bar` class uses plain CSS (not Tailwind utilities), so it goes through the CSS pipeline directly.
**Warning signs:** Bars render as full-height divs or invisible.

### Pitfall 4: Gradient overlay blocking clicks
**What goes wrong:** The `absolute inset-0` gradient overlay covers the entire card, potentially blocking pointer events.
**How to avoid:** Mockup specifies `pointer-events-none` on the overlay div. This is already in D-06. Don't forget it.

### Pitfall 5: Per-app bar with None rate
**What goes wrong:** If `stats.radarr_rate` is `None` (no search data yet), rendering `style="width: None%"` produces invalid CSS.
**How to avoid:** D-10 says "show only app types that have data." Wrap each bar row in `{% if stats.radarr_rate is not none %}`. The existing template already does a none check for the text line.

## Code Examples

### Health Strip Template (replacing health_summary.html)
```html
{# Source: mockup L195-212, adapted with Jinja variables #}
<div id="health-summary"
     hx-get="{{ request.url_for('partial_health_summary') }}"
     hx-trigger="every 30s"
     hx-swap="outerHTML"
     class="flex items-center justify-between text-xs mb-4 px-1">
  <div class="flex items-center gap-4">
    <span class="flex items-center gap-1.5">
      <span class="w-2 h-2 rounded-full bg-triggarr-green"></span>
      <span class="text-triggarr-text"><span class="font-semibold">{{ health.connected }}</span> connected</span>
    </span>
    <span class="flex items-center gap-1.5">
      <span class="w-2 h-2 rounded-full bg-red-500"></span>
      <span class="text-triggarr-text"><span class="font-semibold">{{ health.disconnected }}</span> disconnected</span>
    </span>
    <span class="flex items-center gap-1.5">
      <span class="w-2 h-2 rounded-full bg-triggarr-border"></span>
      <span class="text-triggarr-muted"><span class="font-semibold">{{ health.pending }}</span> pending</span>
    </span>
  </div>
  <span class="text-triggarr-muted font-geist-mono">Last sync {{ last_sync }}</span>
</div>
```

### Mini-bar CSS (add to input.css)
```css
/* Source: mockup L61-62, per D-08 */
.mini-bar { height: 6px; border-radius: 3px; background: #334155; overflow: hidden; position: relative; }
.mini-bar > span { display: block; height: 100%; border-radius: 3px; }
```

### Hero Grab Rate Card (inside stats_row.html)
```html
{# Source: mockup L217-243, per D-05..D-15 #}
<div class="md:col-span-2 bg-triggarr-card rounded-lg border border-triggarr-border p-5 shadow-sm relative overflow-hidden">
  <div class="absolute inset-0 bg-gradient-to-br from-triggarr-green/5 to-transparent pointer-events-none"></div>
  <div class="relative">
    <div class="flex items-center justify-between">
      <span class="text-xs uppercase tracking-wide text-triggarr-muted">Grab Rate</span>
      {% if stats.overall_rate is not none %}
        {% if stats.overall_rate >= 70 %}
          <span class="text-[10px] px-2 py-0.5 rounded-full bg-triggarr-green/15 text-triggarr-green">Healthy</span>
        {% elif stats.overall_rate >= 40 %}
          <span class="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400">Warn</span>
        {% else %}
          <span class="text-[10px] px-2 py-0.5 rounded-full bg-red-500/15 text-red-400">Critical</span>
        {% endif %}
      {% endif %}
    </div>
    <p class="text-4xl font-bold mt-2 leading-none">
      {% if stats.overall_rate is not none %}{{ "%.0f" | format(stats.overall_rate) }}<span class="text-2xl text-triggarr-muted">%</span>{% else %}&mdash;{% endif %}
    </p>
    <div class="mt-4 space-y-2">
      {% if stats.radarr_rate is not none %}
      <div class="flex items-center gap-3">
        <span class="text-[11px] w-12 text-orange-400 font-medium">Radarr</span>
        <div class="mini-bar flex-1"><span style="width: {{ "%.0f" | format(stats.radarr_rate) }}%; background: #fb923c"></span></div>
        <span class="text-[11px] text-triggarr-muted w-8 text-right">{{ "%.0f" | format(stats.radarr_rate) }}%</span>
      </div>
      {% endif %}
      {# Sonarr and Lidarr bars follow same pattern with their colors #}
    </div>
  </div>
</div>
```

### Stat Card with Elevation (shadow-sm added)
```html
{# Source: D-16, D-17 -- existing pattern + shadow-sm #}
<div class="bg-triggarr-card rounded-lg border border-triggarr-border p-4 shadow-sm">
  <span class="text-xs uppercase tracking-wide text-triggarr-muted">Movies</span>
  ...
</div>
```

## Discretion Recommendations

### "Last sync" timestamp (D-04)
**Recommendation:** Track a `last_health_check` timestamp in `request.app.state.triggarr_state` (top-level key, not per-instance). Set it to `datetime.now(UTC)` each time `_build_health_summary()` is called. Render as relative time ("2s ago", "1m ago") using a simple helper function. This is a minimal backend change (one line to set, one helper to format). [ASSUMED -- simplest approach, no new endpoints]

**Alternative (simpler):** Don't track a timestamp at all. Show "Last sync: polling" or use the htmx poll interval statically ("~30s"). Downside: less informative.

**Recommended helper:**
```python
def _relative_time(dt: datetime | None) -> str:
    if dt is None:
        return "never"
    delta = datetime.now(timezone.utc) - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    elif seconds < 3600:
        return f"{seconds // 60}m ago"
    else:
        return f"{seconds // 3600}h ago"
```

### Health badge thresholds (D-12)
**Recommendation:** Use the suggested defaults: >=70% Healthy, >=40% Warn, <40% Critical. These are reasonable for a media automation tool where grab rates typically range 60-95%. [ASSUMED -- reasonable defaults based on domain]

### No-data badge (D-13)
**Recommendation:** Show no badge when `overall_rate is None`. A "No data" badge would add visual noise to a fresh install. The empty dash (`---`) headline already signals no data. [ASSUMED]

### Filtered app bar highlighting (D-19)
**Recommendation:** Don't highlight. The hero card is "overall context" -- highlighting one bar would suggest the others are less relevant, which contradicts the card's purpose. Keep all bars equally styled. [ASSUMED]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio [VERIFIED: codebase] |
| Config file | pyproject.toml (asyncio_mode=auto) [VERIFIED: codebase] |
| Quick run command | `uv run pytest tests/test_stats_health.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STATS-01 | Health strip has colored dots, counts, "Last sync" | unit (HTML string match) | `uv run pytest tests/test_stats_health.py::test_health_strip_layout -x` | Wave 0 |
| STATS-01 | Health strip is NOT a card (no bg-triggarr-card) | unit (HTML string match) | `uv run pytest tests/test_stats_health.py::test_health_strip_not_a_card -x` | Wave 0 |
| STATS-02 | Grab Rate card has md:col-span-2 and text-4xl | unit (HTML string match) | `uv run pytest tests/test_stats_health.py::test_grab_rate_hero_layout -x` | Wave 0 |
| STATS-03 | Health badge renders correct tier | unit (HTML string match) | `uv run pytest tests/test_stats_health.py::test_health_badge_thresholds -x` | Wave 0 |
| STATS-04 | Per-app bars with correct colors | unit (HTML string match) | `uv run pytest tests/test_stats_health.py::test_per_app_bars -x` | Wave 0 |
| STATS-05 | All stat cards have shadow-sm | unit (HTML string match) | `uv run pytest tests/test_stats_health.py::test_stat_cards_have_shadow -x` | Wave 0 |

### Wave 0 Gaps
- [ ] `tests/test_stats_health.py` -- new file, follows `test_ui_foundations.py` fixture pattern
- [ ] Insert search entries for multiple apps to get per-app rate data in tests

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "Last sync" best implemented as a state timestamp set in `_build_health_summary()` | Discretion Recommendations | Low -- if rejected, can use static text or omit |
| A2 | Badge thresholds >=70/>=40/<40 are reasonable defaults | Discretion Recommendations | Low -- trivially adjustable constants |
| A3 | No badge for no-data state is better than "No data" badge | Discretion Recommendations | Low -- aesthetic preference, easy to change |
| A4 | Not highlighting filtered app bar is the right UX choice | Discretion Recommendations | Low -- can add highlight later if user wants it |

## Open Questions

1. **"Last sync" data source**
   - What we know: `_build_health_summary()` is called on every health poll (every 30s). We could timestamp each call.
   - What's unclear: Should this reflect the actual last *arr API health check (which may differ from the htmx poll), or is the poll time sufficient?
   - Recommendation: Use the poll call time. It's always within 30s of truth and requires no backend plumbing beyond one `datetime.now()` assignment.

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `triggarr/templates/partials/health_summary.html`, `stats_row.html`, `routes.py`, `input.css`, `db.py` -- verified all data availability and existing patterns
- `.aidesigner/enhanced-mockup-v3.html` L61-62, L195-262 -- exact CSS and HTML spec
- `49-CONTEXT.md` -- 19 locked decisions with specific class names and values

### Secondary (MEDIUM confidence)
- `test_ui_foundations.py` -- verified testing pattern for HTML string matching

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, all existing code verified
- Architecture: HIGH -- straightforward template replacement following established patterns
- Pitfalls: HIGH -- identified from direct codebase inspection of existing code
- Discretion items: MEDIUM -- reasonable defaults but user may have different preferences

**Research date:** 2026-04-13
**Valid until:** 2026-05-13 (stable -- no external dependencies to go stale)
