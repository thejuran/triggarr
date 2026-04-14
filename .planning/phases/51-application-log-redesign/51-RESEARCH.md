# Phase 51: Application Log Redesign - Research

**Researched:** 2026-04-13
**Domain:** Jinja2 template + CSS + vanilla JS (htmx partial redesign)
**Confidence:** HIGH

## Summary

Phase 51 rebuilds the Application Log panel (`partials/log_viewer.html`) from a basic list into a terminal-style monospace grid with level-coloured rows, per-app source tags, a TAILING indicator, pause/filter controls, and an expandable bottom-pinned terminal pane with scanline effect.

The existing implementation is a 26-line Jinja2 partial with htmx polling (`every 5s`), served by `partial_log_viewer()` which pulls 30 entries from a 200-entry ring buffer. The backend (`log_buffer.py`, `logging.py`) remains unchanged per D-01 -- all source tag parsing happens in the template layer.

**Primary recommendation:** Rebuild the template in-place following the mockup CSS verbatim (lines 76-122, 420-496 of `enhanced-mockup-v3.html`), add the new CSS classes to `input.css`, add a small inline JS handler for expand/collapse/pause/filter, and extend the route to accept an optional `level` query parameter for server-side filtering.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Parse app source (`[Radarr]`, `[Sonarr]`, `[Lidarr]`) from message text in the Jinja2 template using a template filter or inline logic. No changes to `LogEntry` dataclass or `log_buffer.py` backend.
- **D-02:** Implement expand/collapse via pure CSS class toggle -- add/remove `expanded` class on `#log-viewer` and `log-expanded` class on `<body>` via a small inline `onclick` handler. No Alpine.js or new JS dependencies.
- **D-03:** Terminal pane height: 320px when expanded, fixed to bottom of viewport (z-40).
- **D-04:** Always auto-scroll to the latest log entry (pin to bottom). Standard terminal behavior matching the TAILING indicator promise.
- **D-05:** Include a Pause button in the log header that stops htmx polling when toggled. Visual indicator when paused.
- **D-06:** Include a level-filter dropdown in the log header: All / ERROR / WARNING / INFO / DEBUG. Simple single-select dropdown, not multi-filter.
- **D-07:** Full retro terminal aesthetic -- scanlines at 25% opacity on near-black (#050505) background with `mix-blend-mode: overlay`. Scanline animation: 8-second linear cycle, translateY bottom-to-top.
- **D-08:** Geist Mono font already loaded as `font-geist-mono` utility (Phase 48).
- **D-09:** `.dot-pulse` animation reused for TAILING indicator (Phase 48).
- **D-10:** Per-app colors: Radarr `text-orange-400`, Sonarr `text-blue-400`, Lidarr `text-green-400` (Phase 49).

### Claude's Discretion
- Exact SVG icons for expand/collapse/pause/filter buttons
- Pause button visual state (toggled appearance)
- Filter dropdown styling (consistent with existing UI patterns)
- Scanline gradient exact CSS values (reference mockup at `.aidesigner/enhanced-mockup-v3.html` lines 76-101)

### Deferred Ideas (OUT OF SCOPE)
- Source-based filtering (filter by Radarr/Sonarr/Lidarr)
- Log search/grep functionality
- Log entry click-to-copy or click-to-expand detail view
- Log persistence / history beyond the 200-entry ring buffer
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LOG-01 | Log rows rendered in Geist Mono with column-aligned timestamp, level, source, message | Mockup L446-493 provides exact column widths: timestamp `w-14`, level `w-14 shrink-0`, source `w-20 shrink-0`, message `break-all`. `font-geist-mono` already in `input.css`. |
| LOG-02 | Always-visible TAILING indicator (Geist Mono label + pulsing green dot) | Mockup L425-428 has exact markup. `.dot-pulse` animation already in `input.css`. |
| LOG-03 | ERROR rows red-tinted bg + red left border; DEBUG rows dimmed | Mockup L452-453: `bg-red-500/5 border-l-2 border-l-red-500 pl-2 -ml-[2px]`. DEBUG L470: `opacity-60`. |
| LOG-04 | Colored per-app source tags ([Radarr] orange, [Sonarr] blue, [Lidarr] green) | Source parsing from message text via Jinja2 (D-01). Log messages start with app name like `"Radarr: ..."` -- extract and map to color. |
| LOG-05 | Expand icon transforms log to fixed bottom-pinned terminal pane with scanline | Mockup L104-122 CSS for `#log-viewer.expanded`. Scanline CSS L76-101. JS toggle per D-02. |
| LOG-06 | Collapse icon returns log to inline dashboard position | Same toggle mechanism as LOG-05, reverse direction. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Tailwind CSS | v4 | Utility-first CSS | Already in use, `input.css` with `@theme` block [VERIFIED: input.css] |
| htmx | existing | Polling + partial swap | Already powers log viewer polling [VERIFIED: log_viewer.html] |
| Jinja2 | existing | Template rendering | FastAPI + Jinja2Templates [VERIFIED: routes.py] |
| Vanilla JS | -- | Expand/collapse/pause/filter | D-02 mandates no new JS deps |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Geist Mono | 400+500 | Monospace font | Already self-hosted via @font-face [VERIFIED: input.css L15-29] |

### Alternatives Considered
None -- all decisions are locked. No new dependencies introduced.

## Architecture Patterns

### File Changes
```
triggarr/
  static/css/input.css               # ADD: terminal-pane, scanline, expanded-log CSS
  templates/partials/log_viewer.html  # REWRITE: full redesign
  web/routes.py                       # MODIFY: add level query param to partial_log_viewer()
tests/
  test_web.py                         # UPDATE: existing log viewer tests for new markup
```

### Pattern 1: Source Tag Extraction in Jinja2
**What:** Parse app name from the log message text and render as a colored tag.
**When to use:** Every log row render.
**Implementation approach:**

Log messages follow the pattern `"Radarr: ..."` or `"Sonarr: ..."` as confirmed by grep of `triggarr/search/engine.py`. The Jinja2 template can use inline logic to detect and extract:

```jinja2
{# Source tag extraction - check message prefix #}
{% set source = '' %}
{% if entry.message.startswith('Radarr:') or entry.message.startswith('radarr/') %}
  {% set source = 'Radarr' %}
{% elif entry.message.startswith('Sonarr:') or entry.message.startswith('sonarr/') %}
  {% set source = 'Sonarr' %}
{% elif entry.message.startswith('Lidarr:') or entry.message.startswith('lidarr/') %}
  {% set source = 'Lidarr' %}
{% endif %}
```

Color mapping:
- Radarr: `text-orange-400`
- Sonarr: `text-blue-400`
- Lidarr: `text-green-400`
- No source: empty column (maintain alignment with `w-20 shrink-0`)

[VERIFIED: log message format confirmed via `triggarr/search/engine.py` grep]

### Pattern 2: Expand/Collapse via CSS Class Toggle
**What:** Toggle `expanded` class on `#log-viewer` and `log-expanded` on `<body>`.
**When to use:** User clicks expand/collapse button.

```javascript
// Inline onclick handler (no separate JS file needed)
function toggleLogExpand() {
  document.getElementById('log-viewer').classList.toggle('expanded');
  document.body.classList.toggle('log-expanded');
  // Auto-scroll to bottom after expanding
  var logBody = document.querySelector('.log-body');
  if (logBody) logBody.scrollTop = logBody.scrollHeight;
}
```

The CSS rules from the mockup handle the visual transition:
- `#log-viewer.expanded`: `position: fixed; bottom: 0; left: 0; right: 0; height: 320px; z-index: 40;`
- `body.log-expanded`: `padding-bottom: 320px;` (prevents content hiding behind pane)

[VERIFIED: mockup L104-122]

### Pattern 3: Pause htmx Polling
**What:** Stop/resume the `hx-trigger="every 5s"` polling.
**When to use:** User clicks pause button.

htmx provides `htmx.trigger()` control, but the simplest approach per the no-framework constraint:

```javascript
function toggleLogPause(btn) {
  var viewer = document.getElementById('log-viewer');
  var isPaused = viewer.hasAttribute('data-paused');
  if (isPaused) {
    viewer.removeAttribute('data-paused');
    viewer.setAttribute('hx-trigger', 'every 5s');
    htmx.process(viewer); // Re-register the trigger
  } else {
    viewer.setAttribute('data-paused', '');
    viewer.setAttribute('hx-trigger', 'none');
    htmx.process(viewer); // Update trigger to none
  }
}
```

**Important caveat:** When htmx swaps the partial (outerHTML), it replaces the entire `#log-viewer` div, which resets any JS state. The pause state must be preserved across swaps. Two approaches:

1. **Stop the swap entirely when paused** -- the simplest: set `hx-trigger="none"` which prevents any request.
2. **Use htmx events** -- listen for `htmx:beforeRequest` and cancel if paused.

Approach 1 is cleanest for the no-framework constraint. The pause button lives inside the partial, so on un-pause the first swap restores everything.

**Problem with outerHTML swap and pause state:** When the user un-pauses, the next poll will replace the entire div including the pause button state. The solution: store pause state on `<body>` as a data attribute (`data-log-paused`) rather than on the `#log-viewer` div, since body is never swapped.

[ASSUMED: htmx `hx-trigger="none"` stops polling -- standard htmx behavior]

### Pattern 4: Level Filter via Query Parameter
**What:** Server-side filtering by log level.
**When to use:** User selects a level from the dropdown.

The filter dropdown sets `hx-vals` or modifies the `hx-get` URL to include `?level=ERROR`. The route filters before rendering:

```python
@router.get("/partials/log-viewer", response_class=HTMLResponse)
async def partial_log_viewer(request: Request, level: str = "") -> HTMLResponse:
    log_entries = log_buffer.get_recent(30)
    if level:
        log_entries = [e for e in log_entries if e.level == level.upper()]
    return templates.TemplateResponse(
        request=request,
        name="partials/log_viewer.html",
        context={"log_entries": log_entries, "selected_level": level},
    )
```

The dropdown uses `hx-get` with the level parameter and triggers a swap. Like pause state, the selected filter must survive outerHTML swaps -- pass `selected_level` back to the template so the dropdown renders with the correct selection.

[VERIFIED: existing route pattern at routes.py L871-879]

### Pattern 5: Auto-Scroll to Bottom
**What:** Pin log scroll position to the latest entry.
**When to use:** After every htmx swap and on initial load.

```javascript
// After htmx swap, scroll log body to bottom
document.addEventListener('htmx:afterSwap', function(evt) {
  if (evt.detail.target.id === 'log-viewer') {
    var logBody = evt.detail.target.querySelector('.log-body');
    if (logBody) logBody.scrollTop = logBody.scrollHeight;
  }
});
```

This must be in `dashboard.html` (outside the partial) so it is not destroyed by outerHTML swaps.

[ASSUMED: standard htmx event pattern]

### Anti-Patterns to Avoid
- **Putting JS inside the partial:** Any `<script>` tag inside `log_viewer.html` will re-execute on every 5s poll swap. Event listeners and state must live outside the partial (in `dashboard.html` or `base.html`).
- **Storing state on the swapped element:** `#log-viewer` is replaced every 5s by outerHTML swap. State (pause, expanded, filter) must live on `<body>` data attributes or be passed through the template context.
- **Modifying LogEntry dataclass:** D-01 explicitly forbids backend changes. Source parsing is template-only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Polling control | Custom WebSocket | htmx `hx-trigger` with `none` value | D-02 mandates no new deps, htmx already handles polling |
| Scanline animation | Canvas-based effect | Pure CSS `@keyframes` + pseudo-element | Mockup already provides exact CSS, performant, no JS |
| Terminal pane positioning | Custom JS positioning | CSS `position: fixed` + class toggle | Browser-native, no layout thrashing |

## Common Pitfalls

### Pitfall 1: State Loss on htmx outerHTML Swap
**What goes wrong:** Pause state, expanded state, filter selection, and scroll position are lost every 5 seconds when htmx replaces the entire `#log-viewer` div.
**Why it happens:** `hx-swap="outerHTML"` replaces the target element and all its children, destroying any JS state or DOM mutations.
**How to avoid:** 
- Store UI state on `<body>` data attributes (`data-log-paused`, `data-log-expanded`, `data-log-level`).
- Re-apply state after each swap using `htmx:afterSwap` event listener in `dashboard.html`.
- Pass filter/pause state back through template context so the HTML renders correctly server-side.
**Warning signs:** Pause button resets to "play" state, filter dropdown resets to "All", expanded pane collapses on next poll.

### Pitfall 2: Scanline Overlay Intercepting Clicks
**What goes wrong:** The `.scanline-overlay` pseudo-element covers the log area and intercepts mouse events.
**Why it happens:** Absolute-positioned overlay without `pointer-events: none`.
**How to avoid:** The mockup correctly includes `pointer-events: none` on `.scanline-overlay` (L90). Verify this is preserved.
**Warning signs:** Log text not selectable, scroll not working in terminal pane.

### Pitfall 3: Source Tag Extraction Missing Patterns
**What goes wrong:** Some log messages don't get source tags even though they originate from an app.
**Why it happens:** Log messages use varied prefixes: `"Radarr: ..."`, `"radarr/default: ..."`, `"sonarr/4K: ..."`.
**How to avoid:** Match both `Appname:` and `appname/` patterns. Use case-insensitive comparison.
**Warning signs:** Source tag column empty for messages that clearly belong to an app.

### Pitfall 4: Expanded Pane Covers Nav Bar
**What goes wrong:** The fixed terminal pane at z-40 might conflict with the sticky nav bar.
**Why it happens:** z-index stacking context conflicts.
**How to avoid:** Phase 48 nav uses `z-50` (sticky). Terminal pane at `z-40` is correct -- it sits below the nav.
**Warning signs:** Nav disappears behind the terminal pane.

### Pitfall 5: Auto-Scroll Prevents Manual Scrolling
**What goes wrong:** User tries to scroll up to read older entries but gets yanked back to bottom on next poll.
**Why it happens:** D-04 says always auto-scroll. Every 5s swap triggers scroll-to-bottom.
**How to avoid:** D-04 is explicit -- always pin to bottom. This is intentional terminal behavior. The user can pause polling to read history.
**Warning signs:** N/A -- this is by design.

## Code Examples

### Log Row Markup (from mockup)
```html
<!-- Source: enhanced-mockup-v3.html L446-493 -->
<!-- Standard INFO row -->
<div class="flex items-start gap-2 py-1 border-b border-triggarr-border/30">
  <span class="text-triggarr-muted whitespace-nowrap">14:32:12</span>
  <span class="font-medium text-triggarr-green whitespace-nowrap w-14 shrink-0">INFO</span>
  <span class="text-orange-400 whitespace-nowrap w-20 shrink-0">[Radarr]</span>
  <span class="text-triggarr-text break-all">radarr/default: grabbed 12 items</span>
</div>

<!-- ERROR row with red tint -->
<div class="flex items-start gap-2 py-1 border-b border-triggarr-border/30 bg-red-500/5 border-l-2 border-l-red-500 pl-2 -ml-[2px]">
  <span class="text-triggarr-muted whitespace-nowrap">14:30:47</span>
  <span class="font-medium text-red-400 whitespace-nowrap w-14 shrink-0">ERROR</span>
  <span class="text-orange-400 whitespace-nowrap w-20 shrink-0">[Radarr]</span>
  <span class="text-triggarr-text break-all">connection refused</span>
</div>

<!-- DEBUG row dimmed -->
<div class="flex items-start gap-2 py-1 border-b border-triggarr-border/30 opacity-60">
  <span class="text-triggarr-muted whitespace-nowrap">14:29:47</span>
  <span class="font-medium text-triggarr-muted whitespace-nowrap w-14 shrink-0">DEBUG</span>
  <span class="text-green-400 whitespace-nowrap w-20 shrink-0">[Lidarr]</span>
  <span class="text-triggarr-text break-all">cursor advanced to 22</span>
</div>
```

### Terminal Pane CSS (from mockup)
```css
/* Source: enhanced-mockup-v3.html L76-122 */
@keyframes scanline {
  0%   { transform: translateY(-100%); }
  100% { transform: translateY(100%); }
}
.terminal-pane {
  background-color: #050505;
  background-image:
    radial-gradient(circle at center, transparent 0%, #000 120%),
    linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px);
  background-size: 100% 100%, 100% 4px;
}
.scanline-overlay {
  position: absolute; inset: 0;
  pointer-events: none; overflow: hidden;
  mix-blend-mode: overlay; opacity: 0.25;
}
.scanline-overlay::before {
  content: '';
  position: absolute; inset: -100% 0 0 0;
  background: linear-gradient(to bottom, transparent, rgba(34, 197, 94, 0.15), transparent);
  animation: scanline 8s linear infinite;
}
```

### TAILING Badge Markup (from mockup)
```html
<!-- Source: enhanced-mockup-v3.html L425-428 -->
<span class="text-[10px] font-geist-mono text-triggarr-green bg-triggarr-green/10 px-1.5 rounded flex items-center gap-1">
  <span class="w-1.5 h-1.5 bg-triggarr-green rounded-full dot-pulse"></span>
  TAILING
</span>
```

### Header Controls (from mockup)
```html
<!-- Source: enhanced-mockup-v3.html L431-439 -->
<!-- Pause button -->
<button type="button" title="Pause stream" class="p-1.5 text-triggarr-muted hover:text-white hover:bg-triggarr-border/40 rounded transition-colors">
  <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>
  </svg>
</button>
<!-- Filter button -->
<button type="button" title="Filter" class="p-1.5 text-triggarr-muted hover:text-white hover:bg-triggarr-border/40 rounded transition-colors">
  <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
  </svg>
</button>
<!-- Expand button -->
<button type="button" title="Expand log to terminal" class="p-1.5 text-triggarr-muted hover:text-white hover:bg-triggarr-border/40 rounded transition-colors">
  <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/>
    <line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/>
  </svg>
</button>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Basic list with level colors | Column-aligned monospace grid with source tags | Phase 51 | Better readability, app attribution |
| No expand option | Fixed bottom-pinned terminal pane | Phase 51 | Log stays visible during scrolling |
| No pause control | Pause button stops htmx polling | Phase 51 | Users can read history without auto-scroll |
| No level filter | Server-side level filter dropdown | Phase 51 | Reduces noise when debugging |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `hx-trigger="none"` stops htmx polling | Architecture Pattern 3 | Pause feature broken -- would need `htmx:beforeRequest` event cancellation instead |
| A2 | `htmx:afterSwap` fires after outerHTML swap with correct target | Architecture Pattern 5 | Auto-scroll broken -- would need `htmx:afterSettle` or MutationObserver |
| A3 | `htmx.process()` re-registers triggers on modified elements | Architecture Pattern 3 | Un-pause would not resume polling -- would need full page refresh |

**All three are standard htmx patterns that are well-documented. Risk is low.**

## Open Questions

1. **Timestamp format in source tag extraction**
   - What we know: Current template renders `entry.timestamp` as full `YYYY-MM-DD HH:MM:SS`. Mockup shows time-only `HH:MM:SS`.
   - What's unclear: Should the redesign switch to time-only display? The mockup uses short timestamps.
   - Recommendation: Follow mockup -- render time-only (`HH:MM:SS`) in the log rows. The date is redundant when tailing live. Can use Jinja2 string slicing: `{{ entry.timestamp[-8:] }}` or `{{ entry.timestamp.split(' ')[-1] }}`.

2. **Filter dropdown UX: button-activated or always-visible**
   - What we know: Mockup shows a filter icon button, D-06 says "level-filter dropdown".
   - What's unclear: Is it a `<select>` dropdown always visible, or a button that reveals a dropdown on click?
   - Recommendation: Use a `<select>` element styled to match the button aesthetic. Simple, accessible, no extra JS for open/close state. The filter icon in the mockup can be replaced with or accompanied by the select.

## Project Constraints (from CLAUDE.md)

- Python 3.11+, ruff linting (E, F, I, UP, B, SIM), line length 120
- SecretStr for all API keys (not relevant to this phase)
- Loguru for logging -- log_buffer.py and logging.py are the integration points (no changes per D-01)
- pytest-asyncio with asyncio_mode=auto
- No new Python dependencies
- Vanilla JS + CSS sufficient per Out of Scope rules

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` |
| Quick run command | `uv run pytest tests/test_web.py -x -q -k log` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LOG-01 | Monospace grid with column-aligned fields | unit (HTML assertions) | `uv run pytest tests/test_web.py -x -q -k test_log_viewer` | Partial -- existing tests check basic markup |
| LOG-02 | TAILING indicator with dot-pulse | unit (HTML assertion) | `uv run pytest tests/test_web.py -x -q -k test_log_viewer` | No -- needs new assertion |
| LOG-03 | ERROR red tint, DEBUG dimmed | unit (HTML assertion) | `uv run pytest tests/test_web.py -x -q -k test_log_viewer` | Partial -- existing test checks `text-red-400` |
| LOG-04 | Colored source tags | unit (HTML assertion) | `uv run pytest tests/test_web.py -x -q -k test_log_viewer` | No -- needs new test |
| LOG-05 | Expand button and terminal pane CSS classes | unit (HTML assertion) + manual (visual) | `uv run pytest tests/test_web.py -x -q -k test_log_viewer` | No -- needs new test |
| LOG-06 | Collapse button presence | unit (HTML assertion) | `uv run pytest tests/test_web.py -x -q -k test_log_viewer` | No -- needs new test |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_web.py -x -q -k log`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] Update `test_log_viewer_partial_shows_entries` for new markup structure (column widths, source tags)
- [ ] Add `test_log_viewer_tailing_indicator` -- assert TAILING badge + dot-pulse class
- [ ] Add `test_log_viewer_error_row_styling` -- assert `bg-red-500/5`, `border-l-red-500`
- [ ] Add `test_log_viewer_debug_row_dimmed` -- assert `opacity-60`
- [ ] Add `test_log_viewer_source_tags` -- assert colored source tags for Radarr/Sonarr/Lidarr messages
- [ ] Add `test_log_viewer_expand_button` -- assert expand button SVG present
- [ ] Add `test_log_viewer_level_filter` -- assert `?level=ERROR` filters results
- [ ] Add `test_log_viewer_scanline_overlay` -- assert `.scanline-overlay` div present

## Security Domain

No security-sensitive changes in this phase. The phase is purely presentational:
- No new endpoints (only adding a query param to existing)
- No user input that reaches the backend beyond a level enum (ERROR/WARNING/INFO/DEBUG)
- Log messages already pass through the redacting sink before reaching the buffer
- No authentication changes

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | Minimal | Level param should validate against known levels [ASSUMED] |
| V6 Cryptography | No | N/A |

The `level` query parameter should be validated server-side to only accept known values (ERROR, WARNING, INFO, DEBUG, or empty). Any other value should be treated as "All" (no filter). This prevents potential injection or unexpected behavior.

## Sources

### Primary (HIGH confidence)
- `triggarr/templates/partials/log_viewer.html` -- current implementation (26 lines)
- `triggarr/log_buffer.py` -- ring buffer with LogEntry dataclass
- `triggarr/web/routes.py` L871-879 -- partial_log_viewer route
- `triggarr/logging.py` L72-84 -- buffer_sink with redaction
- `triggarr/static/css/input.css` -- existing CSS rules, theme tokens
- `.aidesigner/enhanced-mockup-v3.html` L76-122, L420-496 -- design contract
- `triggarr/search/engine.py` -- confirmed log message format patterns

### Secondary (MEDIUM confidence)
- htmx documentation for `hx-trigger`, `htmx:afterSwap`, `htmx.process()` [ASSUMED from training]

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, everything already in the project
- Architecture: HIGH -- mockup provides exact CSS/HTML, patterns well-understood
- Pitfalls: HIGH -- htmx outerHTML swap state loss is well-known, mitigations documented

**Research date:** 2026-04-13
**Valid until:** 2026-05-13 (stable -- no external dependencies changing)
