# Phase 51: Application Log Redesign - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Rebuild the Application Log panel with a Geist Mono monospace grid, level-coloured rows, colored per-app source tags, a live TAILING indicator, and an expandable bottom-pinned terminal pane with scanline effect. Additionally, add pause and level-filter controls to the log header.

</domain>

<decisions>
## Implementation Decisions

### Source Tag Extraction
- **D-01:** Parse app source (`[Radarr]`, `[Sonarr]`, `[Lidarr]`) from the message text in the Jinja2 template using a template filter or inline logic. No changes to `LogEntry` dataclass or `log_buffer.py` backend.

### Terminal Pane Toggle
- **D-02:** Implement expand/collapse via pure CSS class toggle — add/remove `expanded` class on `#log-viewer` and `log-expanded` class on `<body>` via a small inline `onclick` handler. No Alpine.js or new JS dependencies.
- **D-03:** Terminal pane height: 320px when expanded, fixed to bottom of viewport (z-40).

### Auto-Scroll Behavior
- **D-04:** Always auto-scroll to the latest log entry (pin to bottom). Standard terminal behavior matching the TAILING indicator promise.

### Pause and Filter Controls
- **D-05:** Include a Pause button in the log header that stops htmx polling when toggled. Visual indicator when paused.
- **D-06:** Include a level-filter dropdown in the log header: All / ERROR / WARNING / INFO / DEBUG. Simple single-select dropdown, not multi-filter.

### Scanline Visual Intensity
- **D-07:** Full retro terminal aesthetic — scanlines at 25% opacity on near-black (#050505) background with `mix-blend-mode: overlay`. Scanline animation: 8-second linear cycle, translateY bottom-to-top.

### Carried Forward
- **D-08:** Geist Mono font already loaded as `font-geist-mono` utility (Phase 48 D-02..D-07)
- **D-09:** `.dot-pulse` animation reused for TAILING indicator (Phase 48 D-27..D-28)
- **D-10:** Per-app colors: Radarr `text-orange-400`, Sonarr `text-blue-400`, Lidarr `text-green-400` (Phase 49 D-14..D-15)

### Claude's Discretion
- Exact SVG icons for expand/collapse/pause/filter buttons
- Pause button visual state (toggled appearance)
- Filter dropdown styling (consistent with existing UI patterns)
- Scanline gradient exact CSS values (reference mockup at `.aidesigner/enhanced-mockup-v3.html` lines 76-101)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Contract
- `.aidesigner/enhanced-mockup-v3.html` — Full mockup with terminal pane CSS (L80-122), scanline animation (L76-101), log row styling (L446-493), header layout (L422-441)

### Current Implementation
- `triggarr/templates/partials/log_viewer.html` — Current log viewer partial (htmx polling, basic level colors)
- `triggarr/log_buffer.py` — Ring buffer with LogEntry(timestamp, level, message), thread-safe
- `triggarr/web/routes.py` L872-879 — `partial_log_viewer()` route
- `triggarr/logging.py` L72-84 — `buffer_sink()` loguru integration

### Styling
- `triggarr/static/css/input.css` — Existing CSS rules (.dot-pulse, .card-hover, font-face blocks)

### Prior Phase Context
- `.planning/phases/48-foundations-navigation-chrome/48-CONTEXT.md` — Geist Mono setup, .dot-pulse definition
- `.planning/phases/49-stats-health-strip/49-CONTEXT.md` — Per-app color palette

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `font-geist-mono` utility class: Geist Mono 400+500 weights loaded via @font-face
- `.dot-pulse` + `@keyframes dot-ring-pulse`: Ready for TAILING indicator
- Per-app color tokens: `text-orange-400` (Radarr), `text-blue-400` (Sonarr), `text-green-400` (Lidarr)
- htmx polling pattern: `hx-trigger="every 5s"` already in use

### Established Patterns
- Tailwind v4 dark theme with `triggarr-*` custom color tokens
- htmx partials served from FastAPI routes, swapped via `hx-swap="outerHTML"`
- CSS custom classes defined in `input.css` (`.card-hover`, `.danger-stripes`, `.dot-pulse`)

### Integration Points
- `dashboard.html` includes `partials/log_viewer.html` — the partial is the redesign target
- `partial_log_viewer()` route serves the htmx partial with `log_buffer.get_recent(30)`
- Log entries flow: loguru → `buffer_sink()` → `log_buffer` ring deque → template rendering

</code_context>

<specifics>
## Specific Ideas

- Mockup at `.aidesigner/enhanced-mockup-v3.html` has detailed CSS for terminal pane, scanlines, and row styling — use as the design reference
- Column widths from mockup: timestamp `w-14`, level `w-14`, source `w-20` (all with `shrink-0`)
- ERROR rows: `bg-red-500/5 border-l-2 border-l-red-500 pl-2 -ml-[2px]`
- DEBUG rows: `opacity-60` on entire row
- TAILING badge: `text-[10px] font-geist-mono text-triggarr-green bg-triggarr-green/10 px-1.5 rounded`

</specifics>

<deferred>
## Deferred Ideas

- Source-based filtering (filter by Radarr/Sonarr/Lidarr) — keep it simple with level-only filter for now
- Log search/grep functionality
- Log entry click-to-copy or click-to-expand detail view
- Log persistence / history beyond the 200-entry ring buffer

</deferred>

---

*Phase: 51-application-log-redesign*
*Context gathered: 2026-04-13*
