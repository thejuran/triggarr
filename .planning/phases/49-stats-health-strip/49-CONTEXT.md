# Phase 49: Stats & Health Strip - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the existing full-width health card and flat stats row with: (1) a compact one-line health strip showing instance connection status + last sync timestamp, (2) a hero Grab Rate card spanning 2 grid columns with a large percentage, health badge, and per-app color-coded bar chart, and (3) subtle `shadow-sm` elevation on all stat cards.

No app card changes (Phase 50), no log changes (Phase 51), no rail (Phase 52). This phase touches `health_summary.html`, `stats_row.html`, `input.css` (mini-bar styles), and their backing route functions.

</domain>

<decisions>
## Implementation Decisions

### Health strip layout (STATS-01)
- **D-01:** The health strip is NOT a card — it's a bare `<div class="flex items-center justify-between text-xs mb-4 px-1">` sitting above the stats grid. Mockup L195-212 is the exact spec.
- **D-02:** Each status uses a colored dot (green for connected, red for disconnected, gray/border for pending) followed by a bold count and label. Layout: `flex items-center gap-4` for the left group, "Last sync" timestamp right-aligned.
- **D-03:** Replace the existing `partials/health_summary.html` with the new strip markup. Keep the same htmx polling endpoint (`/partials/health-summary`) and `hx-trigger="every 30s"`.
- **D-04:** "Last sync" timestamp: Claude's discretion on computation. Reasonable approach: track the latest successful health check timestamp in app state and render as relative time ("2s ago", "1m ago"). If no backend change is acceptable, use the htmx poll interval as an approximation.

### Grab Rate hero card (STATS-02, STATS-04)
- **D-05:** Grab Rate card uses `md:col-span-2` in the existing `grid-cols-2 md:grid-cols-5` grid. Mockup L217-243 is the exact spec.
- **D-06:** Card has a subtle gradient overlay: `absolute inset-0 bg-gradient-to-br from-triggarr-green/5 to-transparent pointer-events-none` with content in a `relative` wrapper.
- **D-07:** Headline number is `text-4xl font-bold leading-none` with the `%` suffix in `text-2xl text-triggarr-muted`.
- **D-08:** Per-app bars use a `.mini-bar` CSS class defined in `input.css`: `height: 6px; border-radius: 3px; background: #334155; overflow: hidden;` with an inner `<span>` at percentage width. Mockup L61-62 defines the exact CSS.
- **D-09:** Each bar row: app label (`text-[11px] w-12 font-medium`), bar (`flex-1`), percentage (`text-[11px] text-triggarr-muted w-8 text-right`). Layout: `flex items-center gap-3`.
- **D-10:** The hero card stays `col-span-2` regardless of instance filter state — it always shows the overall grab rate. Per-app bars show only the app types that have data (skip bars with no rate).

### Health badge thresholds (STATS-03)
- **D-11:** Badge sits top-right of the Grab Rate card: `text-[10px] px-2 py-0.5 rounded-full`. Mockup L222.
- **D-12:** Threshold values — Claude's discretion. Recommended defaults:
  - **Healthy** (>=70%): `bg-triggarr-green/15 text-triggarr-green`
  - **Warn** (>=40%): `bg-amber-500/15 text-amber-400`
  - **Critical** (<40%): `bg-red-500/15 text-red-400`
- **D-13:** When no grab rate data exists (no searches yet), show no badge or show a neutral "No data" badge.

### Per-app bar colors (STATS-04)
- **D-14:** Follow mockup exactly — these are the canonical app colors for v2.5:
  - Radarr: orange-400 / #fb923c (label `text-orange-400`, bar background `#fb923c`)
  - Sonarr: blue-400 / #60a5fa (label `text-blue-400`, bar background `#60a5fa`)
  - Lidarr: green-400 / #4ade80 (label `text-green-400`, bar background `#4ade80`)
- **D-15:** These colors are used in bar inline styles (`style="width: N%; background: #hex"`), not Tailwind classes, because the width is dynamic.

### Card elevation (STATS-05)
- **D-16:** Add `shadow-sm` to ALL stat cards (Grab Rate, Movies, Episodes, Albums, Time to Grab). Mockup shows it on every card in the stats row.
- **D-17:** The existing `bg-triggarr-card rounded-lg border border-triggarr-border p-4` pattern gets `shadow-sm` appended. Hero card uses `p-5` (slightly more padding).

### Instance filter interaction
- **D-18:** The existing instance filter dropdown in `stats_row.html` remains functional. When filtered to a specific app type, hide irrelevant stat cards (Movies when Sonarr-only, etc.) — this behavior already exists. The hero Grab Rate card always shows.
- **D-19:** Per-app bars in the hero card: when filtered to a single app, still show all app bars (the card is "overall" context). Claude's discretion if this feels wrong — could highlight the filtered app.

### Claude's Discretion
- "Last sync" timestamp computation approach (D-04)
- Exact health badge threshold values (D-12 provides recommendations)
- No-data badge behavior (D-13)
- Whether to highlight the filtered app's bar in the hero card (D-19)
- Test file structure (extend existing test or new file)
- Whether Albums card needs Lidarr-specific label treatment

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design contract
- `.aidesigner/enhanced-mockup-v3.html` L195-212 — compact health strip: exact markup, classes, dot colors, "Last sync" placement
- `.aidesigner/enhanced-mockup-v3.html` L214-262 — stats row with hero Grab Rate card: grid layout, col-span-2, gradient overlay, text-4xl headline, per-app bar chart, mini-bar CSS, Movies/Episodes/Time to Grab cards
- `.aidesigner/enhanced-mockup-v3.html` L61-62 — `.mini-bar` CSS definition (6px height, rounded, slate background)

### Requirements
- `.planning/REQUIREMENTS.md` STATS-01..05 — five stats/health requirements with user-observable outcomes
- `.planning/REQUIREMENTS.md` Out of Scope — no backend data-shape changes, no new endpoints

### Prior phase context
- `.planning/phases/48-foundations-navigation-chrome/48-CONTEXT.md` — Phase 48 decisions, especially D-15 (elevation token defined but applied here), D-03 (mockup is the spec)

### Existing code (read before modifying)
- `triggarr/templates/partials/health_summary.html` — current health card (being replaced with strip)
- `triggarr/templates/partials/stats_row.html` — current stats grid (being restructured with hero card)
- `triggarr/web/routes.py` `_build_health_summary()` — health data computation
- `triggarr/web/routes.py` `partial_stats_row()` — stats endpoint with instance filtering
- `triggarr/static/css/input.css` — where `.mini-bar` styles go

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`_build_health_summary()`** in `routes.py:203` — already computes `connected`, `disconnected`, `pending`, `total` counts from enabled instances. Strip just renders these differently.
- **`partial_stats_row()`** in `routes.py:812` — already handles instance filtering, computes per-app rates (`stats.radarr_rate`, `stats.sonarr_rate`, `stats.lidarr_rate`), and passes `time_to_grab`. Hero card consumes these same values.
- **`stats.overall_rate`** — already computed server-side, currently shown as `"%.0f" | format(stats.overall_rate)`. Hero card just renders it bigger.
- **htmx polling pattern** — both partials already use `hx-get` + `hx-trigger="every 30s"` + `hx-swap="outerHTML"`. Same pattern continues.

### Established Patterns
- **Partial-per-section** — each dashboard section is its own htmx-polled partial template. Health strip and stats row stay as separate partials.
- **Instance filter via query param** — `?instance=radarr/default` scopes the stats row. The hero card ignores this (shows overall).
- **Tailwind v4 `@theme` tokens** — new mini-bar background color should use the existing `triggarr-border` or `slate-700` equivalent, not a hardcoded hex in the template.

### Integration Points
- `dashboard.html` — includes `health_summary.html` and `stats_row.html` as partials. Layout order: health strip -> stats row -> services grid.
- `input.css` — `.mini-bar` and `.mini-bar > span` styles go here (like `.dot-pulse` in Phase 48).
- `output.css` — must be rebuilt after adding mini-bar styles.

</code_context>

<specifics>
## Specific Ideas

- Mockup gradient overlay on hero card (`from-triggarr-green/5 to-transparent`) gives a subtle branded feel — follow exactly.
- The `%` suffix is deliberately smaller (`text-2xl`) and muted — creates visual hierarchy within the number.
- Mini-bar track color `#334155` (slate-700) matches the dark theme. Could use `bg-triggarr-border` if it maps to the same value for consistency.
- Health strip is intentionally NOT a card (no background, no border, no padding) — it's just text with dots. This makes it feel like metadata, not a dashboard section.

</specifics>

<deferred>
## Deferred Ideas

- **Sparkline trend chart in Grab Rate card** — FUT-01 in REQUIREMENTS.md, explicitly deferred to a later milestone.
- **App card `shadow-sm` and hover elevation** — STATS-05 says "all stat cards and app cards" but app card changes are Phase 50's scope. This phase adds `shadow-sm` to stat cards only.

</deferred>

---

*Phase: 49-stats-health-strip*
*Context gathered: 2026-04-13*
