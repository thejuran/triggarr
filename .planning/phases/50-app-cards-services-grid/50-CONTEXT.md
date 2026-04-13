# Phase 50: App Cards & Services Grid - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Redesign every app service card with: (1) a unified connection pill for all states (Connected/Unreachable/Waiting), (2) a dedicated schedule row for Last Run / Next Run timestamps, (3) compact `pass N` pill badges replacing ordinal text, (4) hover elevation using the Phase 48 token, (5) diagonal red danger stripes on unreachable cards with a Retry button, (6) a pulsing green dot inside the connection pill during live-refresh, and (7) a 3-column grid at the `xl:` breakpoint for 3+ instances.

No stats changes (Phase 49 done), no log changes (Phase 51), no activity rail (Phase 52). This phase touches `app_card.html`, `input.css` (card-hover + danger-stripes CSS), `dashboard.html` (grid classes), and the `_build_app_context()` route helper.

</domain>

<decisions>
## Implementation Decisions

### Connection pill — unified shape for all states (CARD-01, CARD-07)
- **D-01:** Replace the three distinct HTML structures (green dot, red badge, "Waiting..." text) with a SINGLE `<span class="inline-flex items-center gap-1.5 text-[11px] font-medium px-2 py-0.5 rounded-full ...">` pill shape. Mockup L271-274 is the exact spec.
- **D-02:** State colors:
  - **Connected:** `bg-triggarr-green/15 text-triggarr-green` — inner dot `bg-triggarr-green dot-pulse` — label "Connected"
  - **Unreachable:** `bg-red-500/15 text-red-400` — inner dot `bg-red-500` (no pulse) — label "Unreachable {relative_time}" (e.g. "Unreachable 2h")
  - **Waiting:** `bg-triggarr-border/40 text-triggarr-muted` — inner dot `bg-triggarr-muted` (no pulse) — label "Waiting..."
- **D-03:** The pulsing green dot (`dot-pulse` class from Phase 48) is inside the pill, visible only in the Connected state. It pulses while the card's htmx polling is active (every 5s). Mockup L272.
- **D-04:** Inner dot size: `w-1.5 h-1.5 rounded-full`. Pill uses `rounded-full` for capsule shape.

### Schedule row (CARD-02)
- **D-05:** Move Last Run and Next Run OUT of the 2×2 stats grid and INTO a dedicated schedule row directly below the card header. Mockup L276-279.
- **D-06:** Schedule row markup: `<div class="mt-3 flex items-center justify-between text-xs text-triggarr-muted border-b border-triggarr-border/50 pb-3">` with `Last run <span class="text-triggarr-text">{time}</span>` left, `Next run <span class="text-triggarr-text">{time}</span>` right.
- **D-07:** When unreachable, Next Run shows `—` (em dash). Last Run still shows the last known time.
- **D-08:** Time format: HH:MM:SS for last run, HH:MM for next run (consistent with mockup). Use existing `app.last_run` and `app.next_run` values from the route. Claude's discretion on exact formatting implementation.

### Pass pills (CARD-03)
- **D-09:** Replace `(2nd pass)` ordinal text with a compact pill badge: `<span class="text-[10px] bg-triggarr-border/60 text-triggarr-muted px-1.5 py-0 rounded">pass {N}</span>`. Mockup L286.
- **D-10:** Pill sits inline next to the cursor position text (e.g. "12 of 38 [pass 2]") in a `flex items-center gap-1.5` row.
- **D-11:** Show pass pill only when pass > 0. When pass is 0 or undefined, show nothing (no "pass 0" pill).

### Hover elevation (CARD-04)
- **D-12:** Add `.card-hover` class to every app card div. CSS defined in `input.css`: `transition: background-color 150ms ease, box-shadow 150ms ease; &:hover { background-color: #233346; box-shadow: 0 8px 24px -12px rgba(0,0,0,0.6); }`. Mockup L43-44.
- **D-13:** Uses the Phase 48 `triggarr-card-elevated` token value (#233346) for hover background. Keep `background-color` in the CSS rule (not Tailwind class) so the transition animates smoothly.
- **D-14:** Add `shadow-sm` to all app cards (matching Phase 49 stat cards). Mockup L268.

### Unreachable card treatment (CARD-05, CARD-06)
- **D-15:** Add `.danger-stripes` class to the card's outer div when `app.connected == false`. CSS in `input.css`: diagonal red striped background using `repeating-linear-gradient(135deg, rgba(239,68,68,0.05) 0px, rgba(239,68,68,0.05) 6px, transparent 6px, transparent 12px)`. Mockup L65-73.
- **D-16:** Card also gets `relative overflow-hidden` for proper stripe containment. Mockup L387.
- **D-17:** Stats grid (Missing/Cutoff numbers) gets `opacity-60` when unreachable. Mockup L399.
- **D-18:** Replace "Search Now" button with a red "Retry" button: `<button class="bg-red-500/15 text-red-400 text-xs font-medium px-3 py-1.5 rounded hover:bg-red-500/25 transition-colors flex items-center gap-1.5">` with a refresh SVG icon. Mockup L412-415.
- **D-19:** Retry button triggers the same `search_now` POST endpoint as "Search Now" — it's a visual rename, same action. The scheduler will attempt to reconnect on the next search cycle.
- **D-20:** Left border changes from `border-l-triggarr-green` to `border-l-red-500` when unreachable. Already exists in current code.

### Grid layout (LAYOUT-01)
- **D-21:** Change the services grid from `grid-cols-1 md:grid-cols-2` to `grid-cols-1 md:grid-cols-2 xl:grid-cols-3`. Mockup L265.
- **D-22:** This is a CSS-only change in `dashboard.html` on the grid wrapper div. No backend changes needed.
- **D-23:** When card count isn't divisible by 3 on wide screens, the last row simply has fewer cards — standard CSS grid behavior, no special handling needed.

### Tag warning badge
- **D-24:** Keep the existing tag warning badge as-is. Mockup L315-318 shows it between header and schedule row: `<div class="bg-amber-500/15 text-amber-400 text-xs px-3 py-1.5 rounded mt-3 flex items-center gap-2">` with a warning SVG icon.
- **D-25:** Update the warning badge to use the mockup's SVG icon instead of the `&#9888;` HTML entity. Claude's discretion on exact SVG.

### Claude's Discretion
- Time formatting implementation for schedule row (D-08)
- Whether to add `transform` to `.card-hover` transition for a subtle scale effect (mockup CSS includes it but the effect is barely visible)
- SVG icon for tag warning badge (D-25)
- Test file structure (new file vs extending test_web.py)
- Whether Retry button needs a separate route endpoint or reuses `search_now`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design contract
- `.aidesigner/enhanced-mockup-v3.html` L264-417 — complete app card markup for all states (connected, unreachable, with tag warning)
- `.aidesigner/enhanced-mockup-v3.html` L43-44 — `.card-hover` CSS definition
- `.aidesigner/enhanced-mockup-v3.html` L46-59 — `.dot-pulse` CSS definition (already in input.css)
- `.aidesigner/enhanced-mockup-v3.html` L64-73 — `.danger-stripes` CSS definition

### Requirements
- `.planning/REQUIREMENTS.md` CARD-01..07, LAYOUT-01 — eight requirements with user-observable outcomes

### Prior phase context
- `.planning/phases/48-foundations-navigation-chrome/48-CONTEXT.md` — D-15 (elevation token), D-01 (input.css @theme pattern), D-03 (mockup = spec)
- `.planning/phases/49-stats-health-strip/49-CONTEXT.md` — D-14/D-15 (per-app colors), D-16 (shadow-sm pattern)

### Existing code (read before modifying)
- `triggarr/templates/partials/app_card.html` — current card template (being restructured)
- `triggarr/templates/dashboard.html` — grid wrapper div (adding xl:grid-cols-3)
- `triggarr/web/routes.py` `_build_app_context()` — app card data builder
- `triggarr/web/routes.py` `partial_app_card()` — htmx partial endpoint
- `triggarr/static/css/input.css` — where .card-hover and .danger-stripes go

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`.dot-pulse` class** in `input.css` (Phase 48) — reuse for connected pill's pulsing dot
- **`shadow-sm` pattern** (Phase 49) — apply to all app cards
- **`_build_app_context()`** in `routes.py` — already computes `connected`, `last_run`, `next_run`, `unreachable_since`, `missing_pass`, `cutoff_pass`, all cursor positions
- **`search_now` endpoint** — reuse as-is for Retry button action

### Established Patterns
- **Partial-per-card** — each app card is its own htmx-polled partial (`hx-get` + `hx-trigger="every 5s"` + `hx-swap="outerHTML"`)
- **Tailwind v4 `@theme` tokens** — new CSS classes (`.card-hover`, `.danger-stripes`) go in `input.css` following the Phase 48/49 pattern
- **Conditional classes in Jinja2** — current card already uses `{% if app.connected == false %}` for left border color

### Integration Points
- `dashboard.html` — grid wrapper: `grid-cols-1 md:grid-cols-2` → add `xl:grid-cols-3`
- `app_card.html` — complete template rewrite (header, schedule row, stats grid, controls)
- `input.css` — add `.card-hover` and `.danger-stripes` CSS rules
- `output.css` — must be rebuilt after CSS additions

</code_context>

<specifics>
## Specific Ideas

- The mockup's connection pill gradient from green to red states creates clear visual hierarchy — follow the exact color tokens
- `danger-stripes` pattern uses very subtle 5% opacity red — don't make it more intense
- The pass pill's `bg-triggarr-border/60` background blends with the dark theme — test visibility
- Schedule row's `border-b border-triggarr-border/50` creates a subtle separator between header zone and stats grid

</specifics>

<deferred>
## Deferred Ideas

- **Sparkline trend in app cards** — FUT-01 in REQUIREMENTS.md, deferred to later milestone
- **Keyboard shortcut for cycling cards** — FUT-02, deferred
- **App card collapse/expand** — not in mockup or requirements, would be a new capability

</deferred>

---

*Phase: 50-app-cards-services-grid*
*Context gathered: 2026-04-13*
