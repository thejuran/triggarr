# Phase 42: Dashboard Enhancements - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Dashboard shows instance health summary, tag warning badges, and per-instance effectiveness stats. Covers requirements INST-07, TAG-05, OBS-03. No new data collection — surfaces existing data (connection state, tag resolution results, instance-scoped DB stats) in the dashboard UI.

</domain>

<decisions>
## Implementation Decisions

### Health summary card
- Placed at top of dashboard, above existing app cards
- Shows connected/disconnected counts only (e.g., "3 connected, 1 down") — no per-instance detail in the summary
- Always visible, even when all instances are healthy ("4/4 connected" in green)
- Disabled instances excluded from the count — only enabled instances are tracked
- Uses existing htmx polling pattern for live updates

### Tag warning badges
- Warning appears directly on the affected instance's app card (not in health summary or separate section)
- Checked/updated each search cycle — tag resolution already happens, just surface the found/not-found result
- Shows which tag field is broken: "⚠ Missing tag 'x' not found" or "⚠ Cutoff tag 'y' not found"
- If both tags not found on same instance, combined single line: "⚠ Tags not found: 'x' (missing), 'y' (cutoff)"
- Amber color scheme (bg-amber-500/20 text-amber-400) consistent with existing warning patterns

### Per-instance stats breakdown
- Filter dropdown added above existing stats row — default "All instances" shows aggregate (current behavior)
- Flat list: "All instances", "Radarr / Main", "Radarr / 4K", "Sonarr / Main", etc. — no app-type grouping
- Dropdown change triggers htmx GET to `/partials/stats-row?instance=X`, swaps stats row content
- When filtered to a single instance, hide irrelevant cards (Radarr → no Episodes card, Sonarr → no Movies card)
- Uses existing `get_dashboard_stats(instance_id=...)` DB function — already supports instance scoping

### Claude's Discretion
- Exact card spacing and responsive breakpoints
- htmx polling interval for health summary card (5s or 30s)
- How to persist the selected instance filter across polls (hx-vals, hidden input, or query param)
- Stats row grid adjustment when cards are hidden (3-col vs 4-col)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_dashboard_stats(instance_id=...)` in `triggarr/db.py` — already accepts optional instance_id for scoped queries
- `_build_app_context()` in `triggarr/web/routes.py` — builds per-instance template context including connection state
- `_sanitize_card_id()` — safe HTML id generation from instance names
- `resolve_tag_id()` in `triggarr/search/engine.py` — already logs warnings when tag not found
- Existing amber badge pattern: `bg-amber-500/20 text-amber-400` used elsewhere

### Established Patterns
- htmx partials with `hx-trigger="every Ns"` and `hx-swap="outerHTML"` for live updates
- Card wrapper: `bg-triggarr-card rounded-lg border border-triggarr-border p-4 md:p-5`
- Stats row partial at `/partials/stats-row` with 4-column responsive grid
- App card partial at `/partials/app-card/{app_name}/{instance_name}` with per-instance routing
- Status badges: green (connected), red (unreachable), amber (warning)

### Integration Points
- Health summary: new partial rendered above app cards in `dashboard.html`
- Tag warnings: extend `app_card.html` partial, pass tag resolution state through `_build_app_context()`
- Stats filter: extend `stats_row.html` partial, add dropdown + query param to route handler
- Tag state needs to flow from search engine → app state → template context (new data path)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 42-dashboard-enhancements*
*Context gathered: 2026-03-13*
