# Phase 62: Activity Rail & Log Viewer - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Restyle the activity rail to card-based entries with speech bubble pointers, colored timeline dots, and position-based opacity fading. Update the log viewer with Phosphor icon controls, refined styling, "System Logs" title, and keyword-based GRAB row highlights. All changes match the AIDesigner artifact pixel-exactly, with one override: LIVE badge stays green instead of artifact's red.

</domain>

<decisions>
## Implementation Decisions

### Activity Rail Card Styling
- **D-01:** Card style determined by outcome type, not position or recency:
  - Grabbed/partial → solid card (`bg-triggarr-card`, solid `border-triggarr-border`)
  - Searched/failed/unresolved → dashed card (`bg-triggarr-bg`, `border-dashed border-triggarr-border`)
- **D-02:** Timeline dot colors follow outcome:
  - Grabbed = `bg-triggarr-primary` (green)
  - Partial = amber (`bg-amber-400`)
  - Searched = `bg-yellow-500`
  - Failed = `bg-red-500`
  - Unresolved = `bg-gray-500`
- **D-03:** Each card has a speech bubble pointer — `absolute -left-[5px] top-4 w-2 h-2 rotate-45` element matching the card's background color and border style (solid or dashed matching the card).
- **D-04:** Timeline dots use the artifact's double-circle pattern: outer `w-7 h-7 rounded-full bg-triggarr-card border-2 border-triggarr-bg` containing inner `w-2.5 h-2.5 rounded-full` with outcome color.
- **D-05:** Vertical timeline line: `absolute left-[38px] top-6 bottom-6 w-px bg-triggarr-border` connecting dots.
- **D-06:** App badge row inside card uses `w-1.5 h-1.5 rounded-full` app-colored dot + `text-[10px] font-mono text-triggarr-muted uppercase tracking-wider font-bold` label (existing app-color pattern carries forward).

### Opacity Fading (RAIL-03)
- **D-07:** Position-based stepped fading matching artifact exactly:
  - Entries 1-2: 100% (no opacity class)
  - Entry 3: `opacity-75`
  - Entry 4+: `opacity-60`
  - Implement via Jinja2 loop index conditional classes.

### LIVE Badge Color Override
- **D-08:** Override artifact's red (`bg-red-400/text-red-400`) with green (`bg-triggarr-green/text-triggarr-green`) for the LIVE badge in the activity rail header. Green = active/healthy is the established UI pattern, consistent with TAILING badge and connection status pill.

### Activity Rail Header & Footer
- **D-09:** Header uses artifact styling: `text-[13px] font-bold uppercase tracking-widest text-triggarr-muted` for "Recent Activity" title. Sticky header with `bg-triggarr-bg/95 backdrop-blur-md`.
- **D-10:** Footer "View full history" link uses `ph-arrow-right` Phosphor icon with hover translate animation, matching artifact.

### Log Viewer Restyling
- **D-11:** Rename title from "Application Log" to "System Logs". Add `ph-terminal-window` Phosphor icon before title.
- **D-12:** Replace inline SVGs for pause/expand buttons with Phosphor icons: `ph-pause` and `ph-corners-out`. Size `text-[15px]`.
- **D-13:** TAILING badge wrapped in border container: `px-2 py-0.5 rounded bg-triggarr-bg border border-triggarr-border` with `pulse-dot`/`dot-pulse` animation.
- **D-14:** Level filter dropdown uses format "Level: INFO", "Level: WARN", "Level: ERROR", "Level: DEBUG" with `font-mono bg-triggarr-bg border border-triggarr-border text-[11px]` styling.
- **D-15:** Vertical divider `w-px h-4 bg-triggarr-border` between filter dropdown and control buttons.
- **D-16:** Log container uses `bg-[#0b1120]` dark background with `bg-triggarr-card` header bar.

### GRAB Row Highlight
- **D-17:** Detect grab-related log messages by keyword content (messages containing "grabbed", "found release", "sent to client", or similar grab indicators). Apply green highlight treatment: `bg-triggarr-primary/10 border-l-2 border-triggarr-primary` with `[GRAB]` level label in `text-triggarr-primary font-bold`.
- **D-18:** Non-grab log rows use `hover:bg-white/5` with group hover transitions matching artifact. Row layout: timestamp + level tag + message with `text-[13px] leading-relaxed`.

### Claude's Discretion
- Exact keyword list for GRAB row detection (grab/grabbed/found release/sent to client etc.)
- Whether to add `triggarr-elevated` token if it doesn't exist for card hover states
- Log row source tag extraction (current `[Radarr]`/`[Sonarr]`/`[Lidarr]` prefix detection can be kept or adjusted)
- How to handle the `scanline-overlay` — keep, remove, or adapt to new container style

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Spec
- `.aidesigner/runs/2026-04-16T00-05-51-229Z-triggarr-full-dashboard-redesign-v3-/design.html` — Finalized AIDesigner artifact; pixel-exact source of truth. Activity rail section starts at line ~295, log viewer at line ~242.

### Requirements
- `.planning/REQUIREMENTS.md` §Activity Rail (RAIL-01, RAIL-02, RAIL-03) — Activity rail requirements
- `.planning/REQUIREMENTS.md` §Log Viewer (LOG-01, LOG-02, LOG-03) — Log viewer requirements

### Existing Templates (modify in place)
- `triggarr/templates/partials/activity_rail.html` — Current activity rail with timeline dots, outcome pills, app badges
- `triggarr/templates/partials/log_viewer.html` — Current log viewer with TAILING badge, pause/expand buttons, level filter

### Existing CSS
- `triggarr/static/css/input.css` — Tailwind theme with color tokens, `dot-pulse` animation, `terminal-pane` styles, `timeline-item`/`timeline-dot` classes

### Prior Phase Context
- `.planning/phases/60-foundation-header/60-CONTEXT.md` — Phosphor Icons vendored, color tokens, dot-pulse animation
- `.planning/phases/61-stat-cards-app-cards/61-CONTEXT.md` — Stat/app card patterns, artifact fidelity standard (D-09)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phosphor Icons at `static/vendor/phosphor/` — `ph ph-pause`, `ph ph-corners-out`, `ph ph-terminal-window`, `ph ph-arrow-right`
- Color tokens: `triggarr-radarr` (#f59e0b), `triggarr-sonarr` (#3b82f6), `triggarr-green` (#22c55e), `triggarr-primary`
- `dot-pulse` CSS animation for pulsing dots (used in TAILING and LIVE badges)
- `font-geist-mono` class for monospace elements
- `relative_time` Jinja2 filter for timestamps

### Established Patterns
- htmx partials with `hx-trigger="every 5s"` and `hx-swap="outerHTML"` for live polling
- Outcome-based conditional rendering in Jinja2 (`{% if entry.outcome == 'grabbed' %}`)
- App-type color branching (`{% if entry.app == 'Radarr' %}` → orange, Sonarr → blue, Lidarr → green)
- `timeline-item` and `timeline-dot` CSS classes in input.css for current rail layout

### Integration Points
- `activity_rail.html` — primary modification target for card-based layout overhaul
- `log_viewer.html` — primary modification target for Phosphor icons and restyling
- `input.css` — may need to update `timeline-item`/`timeline-dot` classes or replace with inline Tailwind
- `toggleLogPause()` and `toggleLogExpand()` JS functions must remain wired to new Phosphor icon buttons

</code_context>

<specifics>
## Specific Ideas

- Artifact activity rail is an `<aside>` with `border-l` (left border separator from main content) rather than current rounded card approach — match artifact's sidebar treatment
- Artifact uses `space-y-6` between rail entries (current uses `space-y-4`) — more spacious
- Artifact rail header uses `px-6 py-5` (current uses `px-4 py-3`) — more padding
- Artifact card entries use `p-3` internal padding with `text-[13px]` title and `text-[10px]` badges
- Artifact log viewer uses `h-48` body height (current uses `max-h-64`) — slightly different sizing
- Outcome pill in artifact uses simple text badges without SVG icons (current has inline SVG checkmarks etc.) — simplify to text-only pills

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 62-activity-rail-log-viewer*
*Context gathered: 2026-04-16*
