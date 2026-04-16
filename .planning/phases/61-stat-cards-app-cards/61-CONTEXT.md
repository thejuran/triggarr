# Phase 61: Stat Cards & App Cards - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Scale up stat cards with hero numbers, colored Phosphor icons, and per-app mini progress bars. Refine app cards with colored left borders, header connection pills, recessed sub-cards, and app-colored Search Now buttons. All changes match the AIDesigner artifact pixel-exactly where possible.

</domain>

<decisions>
## Implementation Decisions

### Stat Card Scaling
- **D-01:** Uniform text-[32px] for ALL stat card hero numbers (including Grab Rate). Do not use text-[36px] — keep consistent sizing across all cards.
- **D-02:** Match Phosphor icons from the AIDesigner artifact exactly. Inspect design.html to determine which icon each card uses — do not guess or use semantic alternatives.
- **D-03:** Keep the Next Scan card with its existing countdown timer behavior. Restyle to match artifact scale and spacing but preserve the current data wiring.

### Mini Progress Bars
- **D-04:** Match the artifact's mini progress bar styling exactly — inspect design.html for bar height, corner radius, label placement, and spacing. Use existing triggarr-radarr (orange #f59e0b) and triggarr-sonarr (blue #3b82f6) color tokens. Keep the existing data wiring in stats_row.html.

### App Card Structure
- **D-05:** App card connection status displays as a small pill badge in the card header row, next to the instance title, separated by a bottom border per CARD-02.
- **D-06:** Recessed sub-cards for Missing/Cutoff stats match the artifact exactly — inspect design.html for exact bg treatment, padding, border radius, and internal layout.
- **D-07:** Lidarr app cards use green (triggarr-green #22c55e) for their left border and accents, distinct from Radarr orange and Sonarr blue.
- **D-08:** Search Now button uses app-colored hover accent per CARD-04.

### Artifact Fidelity
- **D-09:** Pixel-exact match to the AIDesigner artifact where possible. Inspect design.html class-by-class and replicate Tailwind classes, spacing, and colors. Only deviate for dynamic content or responsive behavior.
- **D-10:** Keep current responsive breakpoints (grid-cols-1 md:cols-2 xl:cols-3 for app cards). Do not change responsive behavior unless the artifact explicitly suggests different breakpoints.

### Claude's Discretion
- Exact card subtitle layout for STAT-04 (match artifact)
- How to integrate colored Phosphor icons into existing stat card template structure
- Card shadow/elevation treatment if artifact uses one
- Handling of Lidarr-specific stat cards (Albums) icon and accent color

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Spec
- `.aidesigner/runs/2026-04-16T00-05-51-229Z-triggarr-full-dashboard-redesign-v3-/design.html` — Finalized AIDesigner artifact; pixel-exact source of truth for all visual changes. Inspect card sections for exact classes.

### Requirements
- `.planning/REQUIREMENTS.md` §Stat Cards (STAT-01 through STAT-04) — Stat card scaling requirements
- `.planning/REQUIREMENTS.md` §App Cards (CARD-01 through CARD-04) — App card structure requirements

### Existing Templates (modify in place)
- `triggarr/templates/partials/stats_row.html` — Current stat cards with Grab Rate hero, mini bars, and app-type cards
- `triggarr/templates/partials/app_card.html` — Current app cards with border-l-4, connection dot, stats grid
- `triggarr/templates/dashboard.html` — Dashboard layout containing stat and app card sections

### Prior Phase Context
- `.planning/phases/60-foundation-header/60-CONTEXT.md` — Phase 60 decisions (Phosphor Icons vendored, color tokens established)

### Existing CSS
- `triggarr/static/css/input.css` — Tailwind theme with triggarr-radarr, triggarr-sonarr, triggarr-danger, triggarr-green color tokens

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phosphor Icons vendored at `static/vendor/phosphor/` — use `<i class="ph ph-icon-name">` markup
- Color tokens: `triggarr-radarr` (#f59e0b), `triggarr-sonarr` (#3b82f6), `triggarr-danger` (#ef4444), `triggarr-green` (#22c55e), `triggarr-primaryDark` (#16a34a)
- `dot-pulse` CSS animation for pulsing green dots
- `font-geist-mono` for monospace elements (timestamps, badges)
- Existing mini progress bars in stats_row.html with percentage width calculation

### Established Patterns
- htmx partials with `hx-trigger="every Ns"` and `hx-swap="outerHTML"` for live updates
- `_build_app_context()` in routes.py builds per-instance data for app cards
- `partial_stats_row()` accepts `?instance=app/name` query param for filtering
- `partial_app_card()` renders single instance card with full state data
- Dark theme: `bg-triggarr-card` cards, `border-triggarr-border` dividers, `text-triggarr-muted` labels

### Integration Points
- `dashboard.html` stat row section — modify layout/grid for artifact spacing
- `stats_row.html` — primary modification target for stat card scaling
- `app_card.html` — primary modification target for app card refinements
- `routes.py` dashboard route already passes all needed data (apps, stats, health)
- Existing tests: `tests/test_stats_health.py` (mini bars), `tests/test_app_cards.py` (card structure)

</code_context>

<specifics>
## Specific Ideas

- Artifact stat cards use `p-5` padding (current uses `p-4`) — increase across all stat cards
- Artifact app cards have colored left border matching app type, not connection status
- Current app cards use green border for connected and red for unreachable — change to always use app-type color (orange Radarr, blue Sonarr, green Lidarr) with red only for unreachable state
- Artifact Search Now button has app-colored hover, not the current generic green hover
- Mini bars in artifact may have rounded ends — inspect design.html for `rounded-full` vs `rounded-sm`

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 61-stat-cards-app-cards*
*Context gathered: 2026-04-15*
