# Phase 21: Dashboard & Stats - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Surface tracking outcomes and lifetime effectiveness metrics in the web UI. Users can see at a glance how effective their search automation is, with per-item outcome badges in search history and aggregate lifetime stats on the dashboard. Also wire the new config fields (tracking window, timeout, pageSize, max rows) into the settings form.

</domain>

<decisions>
## Implementation Decisions

### Stats card layout
- 4 compact stat cards in a row above the app cards: Grab Rate, Movies, Episodes, Time-to-Grab
- Grab Rate card shows overall percentage + per-app breakdown (R: X% S: Y%)
- Movies card shows total with found + updated breakdown
- Episodes card shows total with found + updated breakdown
- Time-to-Grab card shows human-readable average ("2h 15m", "45m", "< 1m")
- Stats row auto-refreshes via htmx polling every 30 seconds
- Empty state: show all 4 cards with dash values ("—") when no data exists yet

### Outcome badges
- Traffic light color scheme for search history outcome pills:
  - searched = blue (existing)
  - failed = red (existing)
  - grabbed = green (new)
  - partial = amber/yellow (new)
  - unresolved = gray (new)
- Contextual tooltips on each badge explaining the state:
  - grabbed: "Download detected within tracking window"
  - partial: "Some episodes grabbed, not all"
  - unresolved: "No grabs detected before window expired"
- Detail field shown in existing title tooltip on hover (no layout changes)
- Add grabbed/partial/unresolved as filterable outcome pills in history filter bar

### Time-to-grab metric
- Average of all grabbed entries: mean of (grab_detected_at - search_timestamp)
- Global average only (not per-app breakdown)
- Human-readable adaptive format: "2h 15m", "45m", "< 1m" depending on magnitude
- Computed from search_history timestamps at query time

### Settings UI
- New config fields added to existing General section (no new section)
- Fields: tracking_window_seconds, request_timeout, page_size, max_history_rows
- Short gray hint text below each input (matching existing "0 = unlimited" pattern)
- Changes take effect immediately via hot-reload (no restart required)

### Claude's Discretion
- Exact Tailwind classes and spacing for stat cards
- DB query structure for effectiveness and time-to-grab calculations
- htmx partial endpoint naming for stats row
- Hint text wording for each settings field

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `lifetime_stats` table already in SQLite with movies_found/updated, episodes_found/updated per app
- `update_outcome_and_stats` in db.py atomically writes outcome + stat increments
- `search_history` table has outcome column with grabbed/partial/unresolved values from Phase 20
- `app_card.html` partial with htmx polling pattern (hx-get + hx-trigger="every 5s")
- `history_results.html` has toggle-pill filter pattern for outcome filtering
- `get_search_history` in db.py supports outcome_filter parameter (just needs new values in template)
- Settings form in `settings.html` has existing General section with input + hint pattern

### Established Patterns
- htmx polling: partials return full HTML fragments, swapped via hx-swap="outerHTML"
- Toggle-pill filters: URL param manipulation in Jinja2, no JS framework
- Dark theme: bg-fetcharr-card, border-fetcharr-border, text-fetcharr-muted, text-fetcharr-green
- Badge pills: text-xs font-medium px-2.5 py-1 rounded-full with color variants
- Stats display: text-xs uppercase tracking-wide label + text-sm font-medium value

### Integration Points
- `dashboard.html` template: stats row inserts before the app cards grid
- `routes.py` dashboard route: needs to query lifetime_stats + effectiveness from DB
- New htmx partial endpoint for stats row (30s polling)
- `history_results.html` outcome filter: extend pill list with 3 new values
- `settings.html` General section: add 4 new form inputs
- `save_settings` route: handle new form fields in POST handler

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 21-dashboard-stats*
*Context gathered: 2026-03-06*
