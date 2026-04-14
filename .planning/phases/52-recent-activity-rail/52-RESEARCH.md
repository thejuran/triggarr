# Phase 52: Recent Activity Rail - Research

**Researched:** 2026-04-13
**Domain:** Jinja2 templating, Tailwind CSS v4, htmx partials, sticky sidebar layout
**Confidence:** HIGH

## Summary

Phase 52 adds a sticky "Recent Activity" rail to the right side of the dashboard on viewports >= 1280px (`xl:` breakpoint). The rail replaces the current inline `partials/search_log.html` section, presenting the same `search_log` data as a vertical timeline with colored dots, per-app badges, outcome pills, queue-type labels, and relative timestamps. On narrow screens the rail is hidden entirely; users access history via the History page instead.

The implementation is purely frontend -- no new backend endpoints, no new data shapes. The existing `get_recent_searches()` DB function already returns all fields needed (name, timestamp, app, queue_type, outcome, detail). The main structural change is wrapping the dashboard's `<main>` content and the new `<aside>` rail in a flex container, which requires modifying `base.html` or `dashboard.html` to move the outer `max-w-7xl` container from `<main>` to a wrapper `<div>`.

**Primary recommendation:** Create a new `partials/activity_rail.html` partial with htmx self-polling, restructure the dashboard layout to a flex container with `<main>` + `<aside>`, remove the `search_log.html` include from `dashboard.html`, and add timeline CSS to `input.css`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RAIL-01 | Sticky rail on right side at >= 1280px viewport | Mockup uses `sticky top-20 max-h-[calc(100vh-6rem)]`; `hidden xl:flex` for breakpoint gating |
| RAIL-02 | Vertical timeline with colored dots connected by line | CSS `.timeline-item` and `.timeline-dot` patterns from mockup; colors map to outcome |
| RAIL-03 | Each entry: app badge, title, outcome pill with icon, queue type, relative timestamp | All fields available from `get_recent_searches()` return dict |
| RAIL-04 | LIVE indicator + filter button in header; "View full history" link in footer | Mockup provides exact markup; link targets History page route |
| RAIL-05 | Hidden on viewports < xl: (1280px) | `hidden xl:flex` on the aside element |
| RAIL-06 | Populated from same search_log data, no new backend endpoint | Reuse existing `/partials/search-log` route (renamed to activity-rail) or pass data from dashboard context |
| RAIL-07 | Remove inline search_log.html from dashboard | Delete `{% include "partials/search_log.html" %}` line from dashboard.html |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.11+, ruff linting (E, F, I, UP, B, SIM), line length 120
- No new Python dependencies -- vanilla JS + CSS + htmx only
- No JavaScript framework (React/Vue/Alpine) -- htmx + vanilla JS
- Tailwind CSS v4 with `@theme` directive for custom tokens
- SecretStr discipline for API keys
- Loguru for logging
- pytest-asyncio with asyncio_mode=auto
- Design contract: `.aidesigner/enhanced-mockup-v3.html` -- extract tokens precisely

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Jinja2 | (bundled with FastAPI) | Server-side HTML templates | Already used for all partials |
| htmx | 2.x (vendored) | Partial polling / swap | Already drives all dynamic updates |
| Tailwind CSS | v4 | Utility-first styling | Already configured with `@theme` tokens |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| aiosqlite | (existing) | SQLite async access | Already used by `get_recent_searches()` |

No new libraries needed. [VERIFIED: codebase inspection]

## Architecture Patterns

### Layout Restructure

The current `base.html` wraps all page content in:
```html
<main class="max-w-7xl mx-auto px-6 py-6">
  {% block content %}{% endblock %}
</main>
```

The mockup uses a flex wrapper pattern:
```html
<div class="max-w-7xl mx-auto px-6 py-6 flex gap-6 items-start">
  <main class="flex-1 min-w-0">
    {% block content %}{% endblock %}
  </main>
  {% block sidebar %}{% endblock %}
</div>
```

**Decision point:** Where to place the flex wrapper.

**Option A (recommended):** Modify `base.html` to add the flex wrapper and a `{% block sidebar %}` that defaults to empty. Only dashboard.html fills the sidebar block. Other pages (History, Settings) render full-width by default since they don't override `sidebar`. This is the cleanest approach because `max-w-7xl` currently lives in base.html.

**Option B:** Override the entire content wrapper in dashboard.html. More self-contained but duplicates the container classes.

[VERIFIED: codebase -- base.html line 87, mockup line 178]

### New Partial: `partials/activity_rail.html`

The rail partial should be self-contained with htmx self-polling:
```html
<aside id="activity-rail"
       hx-get="{{ request.url_for('partial_activity_rail') }}"
       hx-trigger="every 5s"
       hx-swap="outerHTML"
       class="hidden xl:flex w-80 shrink-0 flex-col ...">
  <!-- header, timeline entries, footer -->
</aside>
```

This mirrors the existing pattern used by `search_log.html`, `app_card.html`, `log_viewer.html`, and `stats_row.html` -- all use `hx-get` + `hx-trigger="every 5s"` + `hx-swap="outerHTML"`. [VERIFIED: codebase inspection]

### Route Changes

**Option A (minimal, recommended):** Rename the existing `/partials/search-log` route to `/partials/activity-rail` and point it at the new template. The old route is only referenced from `search_log.html` which is being deleted.

**Option B:** Create a new route alongside the old one. Unnecessary since RAIL-07 removes the old partial.

The route function is simple -- it calls `get_recent_searches(db)` and passes to the template. The data shape already includes all needed fields: `name`, `timestamp`, `app`, `queue_type`, `outcome`, `detail`. [VERIFIED: db.py line 365]

### Relative Timestamps

The mockup shows "Just now", "1m ago", "3m ago", "2h ago". The codebase already has `_relative_time()` in `routes.py` (line 203) that produces "2s ago", "1m ago", "1h ago". However, it takes a `datetime` object, while `search_log` entries have ISO string timestamps.

Two approaches:
1. **Jinja filter (recommended):** Register a `relative_time` template filter that parses the ISO timestamp string and formats it. This keeps the template clean: `{{ entry.timestamp | relative_time }}`.
2. **Pre-process in route:** Convert timestamps before passing to template. More code in the route.

The existing `_relative_time` function can be adapted. It currently returns "Xs ago" for < 60s; the mockup shows "Just now" for very recent entries, so the filter should handle that case.

[VERIFIED: routes.py line 203-214]

### Timeline CSS

The mockup defines these CSS rules (extract precisely per design contract):

```css
/* Activity timeline rail */
.timeline-item { position: relative; padding-left: 1.25rem; }
.timeline-item::before {
  content: '';
  position: absolute;
  left: 0.3rem;
  top: 0.5rem;
  bottom: -1rem;
  width: 2px;
  background: #334155;
  border-radius: 1px;
}
.timeline-item:last-child::before { bottom: auto; height: 0.5rem; }
.timeline-dot {
  position: absolute;
  left: 0;
  top: 0.4rem;
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 9999px;
  border: 2px solid #1e293b;
}
```

These go into `input.css` alongside the existing `.dot-pulse`, `.card-hover`, etc. [VERIFIED: mockup lines 130-151]

### Outcome-to-Color Mapping

From the mockup (matches existing `search_log.html` colors):

| Outcome | Dot Color | Pill Text/BG | Glow |
|---------|-----------|-------------|------|
| grabbed | `bg-triggarr-green` | green | `shadow-[0_0_6px_rgba(34,197,94,0.6)]` |
| partial | `bg-amber-400` | amber | none |
| searched | `bg-blue-400` | blue | none |
| unresolved | `bg-gray-500` | gray | none |
| failed | `bg-red-500` | red | `shadow-[0_0_6px_rgba(239,68,68,0.7)]` |

[VERIFIED: mockup lines 556-672]

### Outcome-to-Icon Mapping (SVG)

| Outcome | Icon Description | SVG |
|---------|-----------------|-----|
| grabbed | Checkmark | `<polyline points="20 6 9 17 4 12"/>` |
| partial | Clock/alert circle | `<circle cx="12" cy="12" r="10"/><path d="M12 6v6"/>` |
| searched | Magnifying glass | `<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>` |
| unresolved | Warning circle | `<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>` |
| failed | X circle | `<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>` |

[VERIFIED: mockup lines 564-651]

### Per-App Badge Colors

| App | Text | Background |
|-----|------|------------|
| Radarr | `text-orange-400` | `bg-orange-500/10` |
| Sonarr | `text-blue-400` | `bg-blue-500/10` |
| Lidarr | `text-green-400` | `bg-green-500/10` |

[VERIFIED: mockup -- same as existing search_log.html]

### Rail Aside Classes (from mockup)

```
hidden xl:flex w-80 shrink-0 flex-col bg-triggarr-card rounded-lg border border-triggarr-border shadow-sm overflow-hidden sticky top-20 max-h-[calc(100vh-6rem)]
```

Key properties:
- `hidden xl:flex` -- hidden below 1280px, flex column on xl+
- `w-80` (320px) -- fixed width
- `sticky top-20` -- sticks 5rem from top (below the nav which is ~60px + padding)
- `max-h-[calc(100vh-6rem)]` -- fills viewport minus nav height
- `shrink-0` -- prevents flex shrink

[VERIFIED: mockup line 539]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Relative timestamps | Manual string formatting in each template | Jinja2 template filter registered once | Reusable, testable, consistent |
| Timeline vertical line | Complex absolute positioning guesswork | Exact CSS from mockup (`.timeline-item::before`) | Pixel-perfect from design contract |
| Sticky sidebar | JavaScript scroll listeners | CSS `position: sticky` | Native, no JS needed, well-supported |
| Responsive hiding | JavaScript media queries | Tailwind `hidden xl:flex` | CSS-only, no layout shift |

## Common Pitfalls

### Pitfall 1: Sticky Not Working Inside Overflow Container
**What goes wrong:** `position: sticky` fails silently if any ancestor has `overflow: hidden` or `overflow: auto`.
**Why it happens:** Sticky elements need a scrollable ancestor that is the viewport or has explicit overflow-y scrolling.
**How to avoid:** The flex wrapper div must NOT have `overflow: hidden`. The `<aside>` sticks relative to the viewport scroll.
**Warning signs:** Rail scrolls with content instead of staying fixed.

### Pitfall 2: Layout Breakage on Non-Dashboard Pages
**What goes wrong:** Adding flex wrapper in `base.html` could affect Settings and History pages.
**Why it happens:** Those pages don't have a sidebar block, so the flex container has only one child.
**How to avoid:** Use `{% block sidebar %}{% endblock %}` that defaults empty. A single flex child with `flex-1 min-w-0` behaves identically to a non-flex block layout.
**Warning signs:** Settings or History pages look different after the change.

### Pitfall 3: Rail Content Overflows on Short Viewports
**What goes wrong:** If `max-h-[calc(100vh-6rem)]` leaves insufficient space, the inner scroll area has minimal room.
**Why it happens:** Nav height + padding can vary.
**How to avoid:** The mockup's `max-h-[calc(100vh-6rem)]` with `overflow-y-auto` on the timeline container handles this. The inner `<div class="flex-1 overflow-y-auto">` scrolls independently.
**Warning signs:** Timeline entries clipped without scrollbar.

### Pitfall 4: htmx outerHTML Swap Breaks Sticky State
**What goes wrong:** When htmx replaces the `<aside>` via outerHTML swap, the browser recalculates sticky positioning. Scroll position inside the rail resets.
**Why it happens:** outerHTML replaces the entire element including its scroll state.
**How to avoid:** This is acceptable for a 5-second polling feed -- the rail shows newest items at top, so reset-to-top is actually desired. If users notice flickering, `hx-swap="innerHTML"` on an inner container is an alternative, but adds complexity.
**Warning signs:** Visible flicker on swap. Consider `hx-swap="morph"` if htmx-ext-morph is available, but vanilla outerHTML is fine for v1.

### Pitfall 5: Removing search_log.html Breaks Tests
**What goes wrong:** Existing tests assert on search log content in dashboard response.
**Why it happens:** `test_dashboard_shows_search_log` (test_web.py:134) checks for "Test Movie" in the dashboard. `test_search_log_partial_returns_200` (test_web.py:173) hits `/partials/search-log`.
**How to avoid:** Update tests: the dashboard test should check for search log entries in the rail. The partial route test should be updated to `/partials/activity-rail`.
**Warning signs:** Test failures on CI after removing search_log.html.

## Code Examples

### Rail Entry Template Pattern (from mockup)
```jinja2
{# Source: .aidesigner/enhanced-mockup-v3.html lines 556-570 #}
<div class="timeline-item">
  <span class="timeline-dot {{ dot_color }} {{ dot_glow }}"></span>
  <div class="flex items-center justify-between mb-1">
    <span class="text-[10px] font-geist-mono font-semibold uppercase {{ app_color }} {{ app_bg }} px-1.5 rounded">
      {{ entry.app }}{% if entry.instance_id and entry.instance_id != 'Default' %} &middot; {{ entry.instance_id }}{% endif %}
    </span>
    <span class="text-[10px] text-triggarr-muted font-geist-mono">{{ entry.timestamp | relative_time }}</span>
  </div>
  <p class="text-sm font-medium text-triggarr-text leading-tight">{{ entry.name }}</p>
  <div class="flex items-center gap-2 text-xs mt-1.5">
    <span class="inline-flex items-center gap-1 {{ pill_text }} {{ pill_bg }} border {{ pill_border }} px-1.5 py-0.5 rounded-sm">
      {{ outcome_icon | safe }}
      {{ entry.outcome }}
    </span>
    <span class="text-[10px] text-triggarr-muted font-geist-mono truncate">{{ entry.queue_type }}</span>
  </div>
</div>
```

### Dashboard Layout Restructure
```jinja2
{# base.html -- replace current <main> wrapper #}
<div class="max-w-7xl mx-auto px-6 py-6 flex gap-6 items-start">
  <main class="flex-1 min-w-0">
    {% block content %}{% endblock %}
  </main>
  {% block sidebar %}{% endblock %}
</div>
```

```jinja2
{# dashboard.html -- add sidebar block #}
{% block sidebar %}
{% include "partials/activity_rail.html" %}
{% endblock %}
```

### Relative Time Jinja Filter
```python
# Source: adapted from routes.py _relative_time (line 203)
from datetime import datetime, UTC

def relative_time_filter(iso_timestamp: str) -> str:
    """Jinja2 filter: ISO timestamp string -> '3m ago' style."""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return iso_timestamp[:19].replace("T", " ")
    delta = datetime.now(UTC) - dt
    seconds = int(delta.total_seconds())
    if seconds < 10:
        return "Just now"
    elif seconds < 60:
        return f"{seconds}s ago"
    elif seconds < 3600:
        return f"{seconds // 60}m ago"
    elif seconds < 86400:
        return f"{seconds // 3600}h ago"
    else:
        return f"{seconds // 86400}d ago"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Inline search_log table in dashboard | Sticky sidebar rail (this phase) | Phase 52 | Dashboard layout changes from single-column to flex with sidebar on xl+ |
| Flat list with border separators | Timeline with dots + vertical line | Phase 52 | More visual hierarchy, matches design contract |
| Absolute timestamp `2024-01-15T10:30:00` | Relative timestamp "3m ago" | Phase 52 | Better UX, quicker scanning |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `top-20` (5rem) is sufficient offset for the sticky nav | Architecture Patterns | Rail overlaps nav -- adjust to match actual nav height |
| A2 | htmx outerHTML swap scroll-reset is acceptable for the rail | Pitfalls | Users may find it jarring -- switch to innerHTML swap on inner container |
| A3 | Filter button in rail header is decorative for this phase (no filter logic) | Requirements | If filter is expected to work, needs additional JS + route params |

## Open Questions

1. **Filter button behavior**
   - What we know: The mockup shows a filter icon button in the rail header. RAIL-04 says "filter button" but no requirement specifies what it filters or how.
   - What's unclear: Is the filter functional in Phase 52, or a placeholder for FUT-06?
   - Recommendation: Render the button visually but make it non-functional (no click handler). Document as future enhancement. This aligns with FUT-04/FUT-06 being deferred.

2. **Number of entries to show in rail**
   - What we know: Current `search_log.html` shows 20 entries (`search_log[:20]`). The mockup shows ~7 entries in the visible area.
   - What's unclear: Should the rail show all 20 (scrollable) or fewer?
   - Recommendation: Keep 20 entries. The rail has `overflow-y-auto` so users can scroll. The mockup naturally fits ~7 visible entries in the `max-h` constraint.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` (asyncio_mode=auto) |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RAIL-01 | Rail aside element present with sticky/xl classes | unit | `uv run pytest tests/test_activity_rail.py::test_rail_has_sticky_classes -x` | Wave 0 |
| RAIL-02 | Timeline items have timeline-dot and timeline-item classes | unit | `uv run pytest tests/test_activity_rail.py::test_timeline_dots_present -x` | Wave 0 |
| RAIL-03 | Entry shows app badge, title, outcome pill, queue type, timestamp | unit | `uv run pytest tests/test_activity_rail.py::test_entry_components -x` | Wave 0 |
| RAIL-04 | LIVE indicator and footer link present | unit | `uv run pytest tests/test_activity_rail.py::test_live_indicator_and_footer -x` | Wave 0 |
| RAIL-05 | Aside has hidden xl:flex classes | unit | `uv run pytest tests/test_activity_rail.py::test_hidden_below_xl -x` | Wave 0 |
| RAIL-06 | Partial route returns 200, uses search_log data | unit | `uv run pytest tests/test_activity_rail.py::test_partial_returns_200 -x` | Wave 0 |
| RAIL-07 | Dashboard no longer includes search_log.html | unit | `uv run pytest tests/test_activity_rail.py::test_no_inline_search_log -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_activity_rail.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_activity_rail.py` -- covers RAIL-01..07
- [ ] Update `tests/test_web.py` -- fix `test_dashboard_shows_search_log` and `test_search_log_partial_returns_200`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A |
| V5 Input Validation | yes | Jinja2 autoescaping (already enabled) |
| V6 Cryptography | no | N/A |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via search entry names | Tampering | Jinja2 autoescaping -- `{{ entry.name }}` is escaped by default |
| SVG injection via outcome icons | Tampering | Icons are hardcoded SVG strings in template, not user-supplied |

No new attack surface. The rail displays the same data as the existing search_log partial, using the same Jinja2 autoescaping. [VERIFIED: codebase]

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `triggarr/templates/partials/search_log.html`, `triggarr/templates/dashboard.html`, `triggarr/templates/base.html`
- Codebase inspection: `triggarr/web/routes.py` (dashboard route, partial_search_log route, _relative_time function)
- Codebase inspection: `triggarr/db.py` (get_recent_searches function, return shape)
- Codebase inspection: `triggarr/static/css/input.css` (existing theme tokens, CSS utilities)
- Design contract: `.aidesigner/enhanced-mockup-v3.html` (rail markup, timeline CSS, layout structure)

### Secondary (MEDIUM confidence)
- Tailwind CSS v4 `hidden xl:flex` responsive utility behavior [ASSUMED -- standard Tailwind]
- CSS `position: sticky` behavior with flex parents [ASSUMED -- standard CSS spec]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new libraries, all existing
- Architecture: HIGH - mockup provides exact markup, existing patterns for htmx partials
- Pitfalls: HIGH - identified from codebase analysis (test breakage, sticky positioning, layout impact)

**Research date:** 2026-04-13
**Valid until:** 2026-05-13 (stable -- no external dependency changes)
