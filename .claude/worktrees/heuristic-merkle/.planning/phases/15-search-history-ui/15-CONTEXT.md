# Phase 15: Search History UI - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Dedicated page where users browse and filter their complete search history beyond the dashboard's 20-entry log. Includes navigation to the page, filtering by app/queue type, and pagination. No editing or deleting history entries — read-only view.

</domain>

<decisions>
## Implementation Decisions

### Entry display & detail
- Same compact single-line row format as the dashboard search log
- Columns: row number/ID, app badge, item name, queue type, outcome badge, absolute timestamp
- Failed entries show the "failed" badge only — no inline error detail or tooltip
- Absolute timestamp format (YYYY-MM-DD HH:MM:SS), consistent with dashboard

### Filter interactions
- Toggle pill buttons for all filter groups (not dropdowns or selects)
- Multi-select with "All" as default state — toggle individual options off/on
- Three filter groups: App (Radarr/Sonarr), Queue type (missing/cutoff), Outcome (searched/failed)
- Text search box for filtering by item name (movie/show title)
- Outcome filter goes beyond SRCH-14 requirements but user explicitly requested it

### Pagination style
- Traditional numbered page controls (prev/next + page numbers)
- 50 entries per page
- Pagination controls at the bottom of the list only
- Total count indicator: "Showing 1-50 of 347 results"

### Navigation & page layout
- New "History" link added to nav bar (between Dashboard and Settings)
- Simple page title ("Search History") followed directly by filters, then results
- No summary stats or header chrome — get to the data fast
- htmx partial swaps for filter changes and pagination (no full page reloads)
- Consistent with dashboard's htmx patterns

### Empty state
- Simple message: "No search history yet. Searches will appear here after your first scheduled run."
- No action links — just informative text

### Claude's Discretion
- Exact filter bar layout and spacing
- htmx trigger and swap mechanics
- Backend query implementation and API endpoint design
- Loading state during filter/page changes

</decisions>

<specifics>
## Specific Ideas

- Row format should mirror the dashboard search_log.html partial closely — app badge color coding (orange for Radarr, blue for Sonarr), green/red outcome badges
- Filters should feel immediate and responsive via htmx, not require a "submit" action

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-search-history-ui*
*Context gathered: 2026-02-24*
