# Requirements: Triggarr v2.5 Dashboard UI Refresh

**Defined:** 2026-04-10
**Core Value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.

**Design contract:** `.aidesigner/enhanced-mockup-v3.html` — treat as spec. Extract tokens precisely, replace illustrative content with real Jinja data.

## v2.5 Requirements

Requirements for the Dashboard UI Refresh milestone. Each maps to exactly one roadmap phase. This is a pure presentation refresh — no backend data shapes change, no new endpoints, no schema migration.

### Foundations

- [ ] **FOUND-01**: Keyboard user sees a consistent triggarr-green focus ring around every focused interactive element (buttons, inputs, selects, links) via a global `:focus-visible` outline
- [ ] **FOUND-02**: User with OS-level `prefers-reduced-motion` enabled sees all transitions and animations reduced to near-zero duration via a global CSS media query
- [ ] **FOUND-03**: User sees monospace surfaces (application log rows, timestamps, TAILING indicators) rendered in Geist Mono loaded from Google Fonts
- [ ] **FOUND-04**: User sees the main page content container widened from `max-w-5xl` to `max-w-7xl` on desktop to accommodate the new activity rail without cramping the main column
- [ ] **FOUND-05**: User sees a new elevation token (`--color-triggarr-card-elevated` = #233346) applied on hover states of interactive cards

### Navigation

- [ ] **NAV-01**: User sees the top navigation bar remain visible with a backdrop-blur effect while scrolling long pages (Dashboard, History, Settings)
- [ ] **NAV-02**: User sees a green underline beneath the active page tab (Dashboard / History / Settings) so the current location is unambiguous
- [ ] **NAV-03**: User sees a pulsing green dot next to the "update available" chip in the nav when a new Triggarr release is detected

### Stats & Health

- [ ] **STATS-01**: User sees a compact one-line health strip showing `N connected / N disconnected / N pending / Last sync {timestamp}` at the top of the dashboard, replacing the previous full-width health card
- [ ] **STATS-02**: User sees the Grab Rate card occupy 2 grid columns (vs 1 for other stat cards) with a large `text-4xl` percentage as the headline number
- [ ] **STATS-03**: User sees a colored health badge (Healthy / Warn / Critical) on the Grab Rate card, thresholded against the overall grab rate
- [ ] **STATS-04**: User sees per-app grab rates as color-coded horizontal bars (one bar per configured *arr type) inside the Grab Rate card, replacing the previous `R: 85% S: 72% L: --%` text line
- [ ] **STATS-05**: User sees subtle shadow elevation (`shadow-sm`) on all stat cards and app cards

### App Cards

- [ ] **CARD-01**: User sees a single unified connection pill shape for every state (Connected / Unreachable / Waiting) in the header of each app card, with the state and context readable at a glance
- [ ] **CARD-02**: User sees the Last Run and Next Run timestamps in a dedicated schedule row directly below the card header, above the missing/cutoff stats grid
- [ ] **CARD-03**: User sees queue pass counts displayed as compact pill badges (e.g. `pass 2`) next to the cursor position, replacing the previous parenthetical ordinal text (e.g. `(2nd pass)`)
- [ ] **CARD-04**: User sees app cards transition to an elevated background (`triggarr-card-elevated`) and shadow on hover
- [ ] **CARD-05**: User sees diagonal red danger stripes as a subtle background pattern on app cards whose instance is unreachable
- [ ] **CARD-06**: User sees a red "Retry" button replacing the "Search Now" button on unreachable instance cards
- [ ] **CARD-07**: User sees a pulsing green dot inside the connection pill while the card is live-refreshing via htmx polling

### Layout

- [ ] **LAYOUT-01**: User with 3+ configured instances sees the services grid switch from 2 columns to 3 columns at the `xl:` breakpoint (≥1280px)

### Application Log

- [ ] **LOG-01**: User sees Application Log rows rendered in Geist Mono with column-aligned timestamp, level, source, and message fields
- [ ] **LOG-02**: User sees an always-visible `TAILING` indicator (Geist Mono label + pulsing green dot) in the log header to signal live updates
- [ ] **LOG-03**: User sees ERROR log rows with a red-tinted background and a red left border, and DEBUG log rows dimmed with reduced opacity
- [ ] **LOG-04**: User sees colored per-app source tags (`[Radarr]` orange, `[Sonarr]` blue, `[Lidarr]` green) in each log row where the source is identifiable
- [ ] **LOG-05**: User can click an expand icon in the log header to transform the Application Log into a fixed bottom-pinned terminal pane that stays visible while the dashboard scrolls, with a subtle scanline effect
- [ ] **LOG-06**: User can click a collapse icon from the expanded terminal pane to return the log to its inline position in the dashboard

### Recent Activity Rail

- [ ] **RAIL-01**: User on a viewport ≥1280px wide sees a new sticky Recent Activity rail docked on the right side of the dashboard; the rail stays in place while the main content scrolls
- [ ] **RAIL-02**: User sees recent search activity as a vertical timeline in the rail, with colored dots (green/amber/blue/gray/red) connected by a vertical line
- [ ] **RAIL-03**: User sees each rail entry showing: per-app badge (colored), title, outcome pill with icon (grabbed/partial/searched/unresolved/failed), queue type, and relative timestamp
- [ ] **RAIL-04**: User sees a "LIVE" indicator and filter button in the rail header, and a "View full history →" link in the footer that navigates to the History page
- [ ] **RAIL-05**: User on a viewport narrower than `xl:` sees the main dashboard full-width with the rail hidden entirely
- [ ] **RAIL-06**: The rail is populated by the same `search_log` / search-history data as the current inline Search Log — no new backend endpoint is introduced
- [ ] **RAIL-07**: The previous inline `partials/search_log.html` section is removed from the dashboard; its role is served by the rail on wide screens and by the History page on narrow screens

### Docs & Metadata

- [ ] **DOCS-01**: README documents Lidarr as a first-class supported *arr alongside Radarr and Sonarr (install notes, config reference, screenshots)
- [ ] **DOCS-02**: README dashboard screenshots are refreshed to reflect the v2.5 visual direction
- [ ] **DOCS-03**: Key Decisions in PROJECT.md records the rationale for the new rail + expandable log architecture (sticky positioning, data reuse, vanilla JS)

## Future Requirements

Deferred to a later milestone. Tracked but not in this roadmap.

### Visual polish

- **FUT-01**: Small sparkline chart showing grab rate trend (7-day) inside the hero Grab Rate card
- **FUT-02**: Keyboard shortcut overlay (`?` opens help modal listing shortcuts)
- **FUT-03**: Optional `prefers-color-scheme: light` variant for users who prefer light themes

### Interaction

- **FUT-04**: Log filter panel (by level, by source app) inside the expanded terminal pane
- **FUT-05**: Click-to-pin individual log rows (keeps them visible while new entries stream in)
- **FUT-06**: Mobile-specific bottom sheet for the Recent Activity feed when the rail is hidden

## Out of Scope

Explicitly excluded from v2.5 to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Backend data-shape changes | Pure presentation refresh — data model unchanged |
| New API endpoints | Reuse existing `search_log`, stats, and health endpoints |
| Database schema changes | None required for this milestone |
| New Python dependencies | Vanilla JS + CSS are sufficient; Geist Mono is a Google Fonts import only |
| JavaScript framework (React/Vue/Alpine) | htmx + vanilla JS handles the expandable log and rail |
| Real-time WebSocket log streaming | htmx polling is sufficient; WebSocket would add failure modes and deployment complexity |
| Grafana/Linear-style overhaul | Kept existing slate-900/triggarr-green palette intentionally — the AIDesigner full-redesign reference (`mcp-latest.html`) was deliberately not adopted |
| Header CPU/RAM sparklines | Not actionable for users, adds a polling endpoint |
| User avatar / account chip | Triggarr has no user accounts; adding one would violate the no-auth core decision |
| Queue Rules tab | No such feature in Triggarr; the redesign's nav entry was an AIDesigner invention |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 48 | Done |
| FOUND-02 | Phase 48 | Done |
| FOUND-03 | Phase 48 | Done |
| FOUND-04 | Phase 48 | Done |
| FOUND-05 | Phase 48 | Done |
| NAV-01 | Phase 48 | Done |
| NAV-02 | Phase 48 | Done |
| NAV-03 | Phase 48 | Done |
| STATS-01 | Phase 49 | Pending |
| STATS-02 | Phase 49 | Pending |
| STATS-03 | Phase 49 | Pending |
| STATS-04 | Phase 49 | Pending |
| STATS-05 | Phase 49 | Pending |
| CARD-01 | Phase 50 | Pending |
| CARD-02 | Phase 50 | Pending |
| CARD-03 | Phase 50 | Pending |
| CARD-04 | Phase 50 | Pending |
| CARD-05 | Phase 50 | Pending |
| CARD-06 | Phase 50 | Pending |
| CARD-07 | Phase 50 | Pending |
| LAYOUT-01 | Phase 50 | Pending |
| LOG-01 | Phase 51 | Pending |
| LOG-02 | Phase 51 | Pending |
| LOG-03 | Phase 51 | Pending |
| LOG-04 | Phase 51 | Pending |
| LOG-05 | Phase 51 | Pending |
| LOG-06 | Phase 51 | Pending |
| RAIL-01 | Phase 52 | Pending |
| RAIL-02 | Phase 52 | Pending |
| RAIL-03 | Phase 52 | Pending |
| RAIL-04 | Phase 52 | Pending |
| RAIL-05 | Phase 52 | Pending |
| RAIL-06 | Phase 52 | Pending |
| RAIL-07 | Phase 52 | Pending |
| DOCS-01 | Phase 53 | Pending |
| DOCS-02 | Phase 53 | Pending |
| DOCS-03 | Phase 53 | Pending |

**Coverage:**
- v2.5 requirements: 37 total
- Mapped to phases: 37 ✓
- Unmapped: 0

**Phase distribution:**
- Phase 48 (Foundations & Navigation Chrome): 8 requirements (FOUND-01..05, NAV-01..03)
- Phase 49 (Stats & Health Strip): 5 requirements (STATS-01..05)
- Phase 50 (App Cards & Services Grid): 8 requirements (CARD-01..07, LAYOUT-01)
- Phase 51 (Application Log Redesign): 6 requirements (LOG-01..06)
- Phase 52 (Recent Activity Rail): 7 requirements (RAIL-01..07)
- Phase 53 (Docs & Metadata): 3 requirements (DOCS-01..03)

---
*Requirements defined: 2026-04-10*
*Last updated: 2026-04-10 — traceability populated by roadmapper*
