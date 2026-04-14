# Roadmap: Triggarr

## Overview

Triggarr is a single-process automation daemon that cycles through Radarr and Sonarr's wanted/cutoff-unmet lists on a configurable schedule, with closed-loop download tracking. Security invariants (no API key in any HTTP response) are established from day one and never relaxed.

## Milestones

- ✅ v1.0 MVP -- Phases 1-8 (shipped 2026-02-24) -- [archive](milestones/v1.0-ROADMAP.md)
- ✅ v1.1 Ship & Document -- Phases 9-12 (shipped 2026-02-24) -- [archive](milestones/v1.1-ROADMAP.md)
- ✅ v1.2 Polish & Harden -- Phases 13-16 (shipped 2026-02-24) -- [archive](milestones/v1.2-ROADMAP.md)
- ✅ v2.0 Closed-Loop Tracking -- Phases 17-22 (shipped 2026-03-09) -- [archive](milestones/v2.0-ROADMAP.md)
- ✅ v2.1 Harden & Fix -- Phases 23-24 (shipped 2026-03-09) -- [archive](milestones/v2.1-ROADMAP.md)
- ✅ v2.2 Skip Unreleased Media -- Phases 25-28 (shipped 2026-03-09) -- [archive](milestones/v2.2-ROADMAP.md)
- ✅ v2.3 Multi-Instance & Tag Filtering -- Phases 33-44 (shipped 2026-03-14) -- [archive](milestones/v2.3-ROADMAP.md)
- ✅ v2.4 Community Polish & Test Hardening -- Phases 45-47 (shipped 2026-04-09) -- [archive](milestones/v2.4-ROADMAP.md)
- 🚧 v2.5 Dashboard UI Refresh -- Phases 48-53 (in progress, started 2026-04-10)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-8) -- SHIPPED 2026-02-24</summary>

- [x] Phase 1: Foundation (3/3 plans) -- completed 2026-02-23
- [x] Phase 2: Search Engine (3/3 plans) -- completed 2026-02-24
- [x] Phase 3: Web UI (3/3 plans) -- completed 2026-02-24
- [x] Phase 4: Docker (1/1 plan) -- completed 2026-02-24
- [x] Phase 5: Security Hardening (2/2 plans) -- completed 2026-02-24
- [x] Phase 6: Bug Fixes & Resilience (3/3 plans) -- completed 2026-02-24
- [x] Phase 7: Test Coverage (2/2 plans) -- completed 2026-02-24
- [x] Phase 8: Tech Debt Cleanup (1/1 plan) -- completed 2026-02-24

</details>

<details>
<summary>v1.1 Ship & Document (Phases 9-12) -- SHIPPED 2026-02-24</summary>

- [x] Phase 9: CI/CD Pipeline (1/1 plan) -- completed 2026-02-24
- [x] Phase 10: Release Pipeline (1/1 plan) -- completed 2026-02-24
- [x] Phase 11: Search Enhancements (2/2 plans) -- completed 2026-02-24
- [x] Phase 12: Documentation (1/1 plan) -- completed 2026-02-24

</details>

<details>
<summary>v1.2 Polish & Harden (Phases 13-16) -- SHIPPED 2026-02-24</summary>

- [x] Phase 13: CI & Search Diagnostics (2/2 plans) -- completed 2026-02-24
- [x] Phase 14: Dashboard Observability (2/2 plans) -- completed 2026-02-24
- [x] Phase 15: Search History UI (2/2 plans) -- completed 2026-02-24
- [x] Phase 16: Deep Code Review (2/2 plans) -- completed 2026-02-24

</details>

<details>
<summary>v2.0 Closed-Loop Tracking (Phases 17-22) -- SHIPPED 2026-03-09</summary>

- [x] Phase 17: Foundation & DB Preparation (3/3 plans) -- completed 2026-02-25
- [x] Phase 18: Security & Operations (2/2 plans) -- completed 2026-02-25
- [x] Phase 19: Tracking Infrastructure (2/2 plans) -- completed 2026-02-25
- [x] Phase 20: Tracking Integration (3/3 plans) -- completed 2026-02-25
- [x] Phase 20.1: Deep Review — Security & Safety (2/2 plans) -- completed 2026-02-26
- [x] Phase 20.2: Deep Review — Code Quality (2/2 plans) -- completed 2026-02-26
- [x] Phase 21: Dashboard & Stats (2/2 plans) -- completed 2026-03-07
- [x] Phase 22: Rename to Triggarr (2/2 plans) -- completed 2026-03-07

</details>

<details>
<summary>v2.1 Harden & Fix (Phases 23-24) -- SHIPPED 2026-03-09</summary>

- [x] Phase 23: Deploy Fixes (1/1 plan) -- completed 2026-03-09
- [x] Phase 24: Hardening (1/1 plan) -- completed 2026-03-09

</details>

<details>
<summary>v2.2 Skip Unreleased Media (Phases 25-28) -- SHIPPED 2026-03-09</summary>

- [x] Phase 25: Filter Foundation (1/1 plan) -- completed 2026-03-09
- [x] Phase 26: Settings UI & Engine Integration (1/1 plan) -- completed 2026-03-09
- [x] Phase 27: Dashboard Display (1/1 plan) -- completed 2026-03-09
- [x] Phase 28: Fix Code Review Findings (2/2 plans) -- completed 2026-03-09

</details>

<details>
<summary>v2.3 Multi-Instance & Tag Filtering (Phases 33-44) -- SHIPPED 2026-03-14</summary>

- [x] Phase 33: Config Model & Migration (2/2 plans) -- completed 2026-03-11
- [x] Phase 34: State Model & Cursor Isolation (2/2 plans) -- completed 2026-03-11
- [x] Phase 35: Client Registry & Tag Resolution (1/1 plan) -- completed 2026-03-11
- [x] Phase 36: Search Engine & Tag Filtering (2/2 plans) -- completed 2026-03-11
- [x] Phase 37: Database Schema & Instance Scoping (1/1 plan) -- completed 2026-03-11
- [x] Phase 38: Scheduler & Tracking Wiring (1/1 plan) -- completed 2026-03-11
- [x] Phase 39: Web UI Integration (1/1 plan) -- completed 2026-03-11
- [x] Phase 40: Fix Multi-Instance Bugs (3/3 plans) -- completed 2026-03-12
- [x] Phase 41: Multi-Instance Settings UI (1/1 plan) -- completed 2026-03-12
- [x] Phase 42: Dashboard Enhancements (2/2 plans) -- completed 2026-03-13
- [x] Phase 43: Update Notification & Cleanup (1/1 plan) -- completed 2026-03-13
- [x] Phase 44: Deep Review Fixes (1/1 plan) -- completed 2026-03-14

</details>

<details>
<summary>v2.4 Community Polish & Test Hardening (Phases 45-47) -- SHIPPED 2026-04-09</summary>

- [x] Phase 45: Community Health & Repo Metadata (2/2 plans) -- completed 2026-04-09
- [x] Phase 46: Test Hardening -- Infrastructure Failures (2/2 plans) -- completed 2026-04-09
- [x] Phase 47: Test Hardening -- State & Search Edge Cases (2/2 plans) -- completed 2026-04-09

</details>

<details open>
<summary>v2.5 Dashboard UI Refresh (Phases 48-53) -- IN PROGRESS</summary>

- [x] **Phase 48: Foundations & Navigation Chrome** — Global tokens, focus ring, reduced-motion, Geist Mono, wider container, sticky nav with active-tab underline and update dot
- [ ] **Phase 49: Stats & Health Strip** — One-line health strip, hero Grab Rate card with health badge and per-app bar chart, card elevation
- [ ] **Phase 50: App Cards & Services Grid** — Unified connection pill, schedule row, pass pills, hover elevation, danger stripes, Retry button, live dot, 3-col xl grid
- [ ] **Phase 51: Application Log Redesign** — Geist Mono rows, TAILING indicator, level styling, source tags, expandable bottom terminal pane
- [ ] **Phase 52: Recent Activity Rail** — New sticky right rail with timeline, entries, header/footer, xl-only visibility, inline search-log removal
- [ ] **Phase 53: Docs & Metadata** — README Lidarr docs, refreshed screenshots, architecture decision log entry

</details>

## Phase Details

### Phase 48: Foundations & Navigation Chrome

**Goal**: User sees the design-system scaffolding for v2.5 — accessibility primitives, new typography, wider layout container, new elevation token, and a sticky navigation bar with clear active-state feedback — applied globally across every page.
**Depends on**: Nothing (first phase of v2.5, foundational for all subsequent phases)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, NAV-01, NAV-02, NAV-03
**Success Criteria** (what must be TRUE):
  1. Keyboard user tabbing through any page sees a consistent triggarr-green focus ring around every focused interactive element (buttons, inputs, selects, links)
  2. User with OS-level reduced-motion enabled loads the dashboard and observes that hover transitions, pulses, and animations are effectively flattened
  3. User sees monospace surfaces across the site rendered in Geist Mono loaded from Google Fonts, and the main dashboard column extends to `max-w-7xl` on desktop
  4. User scrolling the Dashboard, History, or Settings page sees the top nav bar remain pinned with a backdrop-blur effect and a green underline under the active tab
  5. When an update is available, user sees a pulsing green dot next to the update-available chip in the nav
**Plans**: 3 plans
- [ ] 48-01-PLAN.md — CSS foundations: tokens, focus-visible, reduced-motion, self-hosted Geist Mono, dot-pulse utility, rebuilt output.css (FOUND-01, FOUND-02, FOUND-03, FOUND-05)
- [ ] 48-02-PLAN.md — base.html chrome: sticky nav, max-w-7xl container, centralized active-tab via request.url.path, pulsing dot inside update chip, remove nav_*_class blocks from child templates (FOUND-04, NAV-01, NAV-02, NAV-03)
- [ ] 48-03-PLAN.md — Verification: tests/test_ui_foundations.py with template smoke tests + CSS-compilation assertion (no new deps)
**UI hint**: yes

### Phase 49: Stats & Health Strip

**Goal**: User sees the top of the dashboard restructured around a compact instance-health strip and a hero Grab Rate card that dominates the stats row with a large percentage, a health badge, and per-app color-coded bars.
**Depends on**: Phase 48 (uses elevation token, wider container, Geist Mono for timestamps)
**Requirements**: STATS-01, STATS-02, STATS-03, STATS-04, STATS-05
**Success Criteria** (what must be TRUE):
  1. User sees a single-line health strip at the top of the dashboard showing `N connected / N disconnected / N pending / Last sync {timestamp}`, replacing the previous full-width health card
  2. User sees the Grab Rate card spanning 2 grid columns with a `text-4xl` headline percentage and a Healthy/Warn/Critical badge thresholded against the overall rate
  3. User sees per-app grab rates rendered as color-coded horizontal bars inside the Grab Rate card (one bar per configured *arr type), replacing the previous `R: 85% S: 72% L: --%` text line
  4. User sees subtle `shadow-sm` elevation on every stat card giving the stats row a layered, tactile feel
**Plans**: 3 plans
- [ ] 49-01-PLAN.md — Health strip replacement + mini-bar CSS: replace health_summary.html card with compact strip, add _relative_time helper to routes.py, add .mini-bar CSS to input.css, rebuild output.css (STATS-01, STATS-04)
- [ ] 49-02-PLAN.md — Hero Grab Rate card + card elevation: restructure stats_row.html with col-span-2 hero card, gradient overlay, health badge, per-app color-coded mini-bars, shadow-sm on all stat cards (STATS-02, STATS-03, STATS-04, STATS-05)
- [ ] 49-03-PLAN.md — Tests: test_stats_health.py validating health strip structure, hero card layout, badge rendering, bar colors, and shadow-sm elevation (STATS-01..05)
**UI hint**: yes

### Phase 50: App Cards & Services Grid

**Goal**: User sees every Services card refreshed with a unified connection pill, a dedicated schedule row, compact pass pills, hover elevation, unreachable-state visual treatment (danger stripes + Retry button), a live-refresh dot, and a 3-column grid on wide screens.
**Depends on**: Phase 48 (elevation token, focus ring, wider container)
**Requirements**: CARD-01, CARD-02, CARD-03, CARD-04, CARD-05, CARD-06, CARD-07, LAYOUT-01
**Success Criteria** (what must be TRUE):
  1. User sees a single unified connection pill shape in the header of every app card for all states (Connected / Unreachable / Waiting), with state and context readable at a glance
  2. User sees Last Run and Next Run timestamps in a dedicated schedule row directly below the card header, and queue pass counts rendered as compact `pass 2` pill badges next to the cursor position
  3. User hovering any app card sees it transition to the elevated background and shadow; user sees a pulsing green dot inside the connection pill while the card live-refreshes via htmx polling
  4. User sees app cards for unreachable instances rendered with diagonal red danger stripes and a red "Retry" button replacing the "Search Now" button
  5. User with 3+ configured instances on a viewport ≥1280px sees the Services grid switch from 2 columns to 3 columns
**Plans**: 2 plans
- [ ] 50-01-PLAN.md — CSS additions (.card-hover, .danger-stripes) + complete app_card.html rewrite with unified pills, schedule row, pass pills, danger stripes, Retry button + dashboard.html xl:grid-cols-3 (CARD-01..07, LAYOUT-01)
- [ ] 50-02-PLAN.md — Tests: test_app_cards.py validating connection pills, schedule row, pass pills, hover classes, danger stripes, Retry button, dot-pulse, and 3-col grid (CARD-01..07, LAYOUT-01)
**UI hint**: yes

### Phase 51: Application Log Redesign

**Goal**: User sees the Application Log panel rebuilt around a Geist Mono monospace grid with a live TAILING indicator, level-coloured rows, colored per-app source tags, and the ability to expand the log into a fixed bottom-pinned terminal pane that stays visible while the dashboard scrolls.
**Depends on**: Phase 48 (Geist Mono font, elevation token, wider container)
**Requirements**: LOG-01, LOG-02, LOG-03, LOG-04, LOG-05, LOG-06
**Success Criteria** (what must be TRUE):
  1. User sees Application Log rows rendered in Geist Mono with column-aligned timestamp, level, source, and message fields
  2. User sees an always-visible `TAILING` indicator (Geist Mono label + pulsing green dot) in the log header, confirming live polling
  3. User sees ERROR rows with a red-tinted background and red left border, DEBUG rows dimmed, and `[Radarr]` / `[Sonarr]` / `[Lidarr]` source tags in their signature colors
  4. User can click an expand icon in the log header to promote the log to a fixed bottom-pinned terminal pane with a subtle scanline effect, and click a collapse icon to return it to its inline dashboard position
**Plans**: 3 plans
- [ ] 51-00-PLAN.md — Wave 0 test stubs: tests/test_log_viewer.py with 12 tests covering LOG-01 through LOG-06
- [ ] 51-01-PLAN.md — CSS terminal-pane/scanline/expanded classes + full log_viewer.html rewrite with monospace grid, source tags, TAILING, buttons (LOG-01..06)
- [ ] 51-02-PLAN.md — Route level filter param + dashboard.html JS for expand/collapse, pause, auto-scroll (LOG-04..06)
**UI hint**: yes

### Phase 52: Recent Activity Rail

**Goal**: User on wide screens sees a new sticky Recent Activity rail docked on the right of the dashboard — a vertical timeline of recent searches with colored dots, per-app badges, outcome pills, queue type, and relative timestamps — fed by the existing search-log data and hidden entirely on narrow screens. The previous inline Search Log partial is removed.
**Depends on**: Phase 48 (wider container needed to fit the rail), Phase 49 (stats layout), Phase 50 (grid layout)
**Requirements**: RAIL-01, RAIL-02, RAIL-03, RAIL-04, RAIL-05, RAIL-06, RAIL-07
**Success Criteria** (what must be TRUE):
  1. User on a viewport ≥1280px wide sees a sticky Recent Activity rail on the right side of the dashboard that stays in place while the main content scrolls
  2. User sees recent searches rendered as a vertical timeline in the rail, with colored dots (green/amber/blue/gray/red) connected by a vertical line
  3. User sees each rail entry showing a per-app badge, title, outcome pill with icon (grabbed/partial/searched/unresolved/failed), queue type, and relative timestamp; rail header shows a LIVE indicator and filter button, footer shows a "View full history →" link to the History page
  4. User on a viewport narrower than `xl:` sees the main dashboard full-width with the rail hidden entirely
  5. User sees no inline Search Log section on the dashboard anymore — the rail replaces it on wide screens and the History page serves narrow screens — and the rail is populated from the same `search_log` data with no new backend endpoint
**Plans**: 2 plans
Plans:
- [ ] 52-01-PLAN.md — Timeline CSS, relative_time Jinja filter, /partials/activity-rail route, activity_rail.html partial template, test stubs (RAIL-01..06)
- [ ] 52-02-PLAN.md — base.html flex wrapper with sidebar block, dashboard.html rail wiring, search_log.html removal, route cleanup, test updates (RAIL-01, RAIL-05, RAIL-06, RAIL-07)
**UI hint**: yes

### Phase 53: Docs & Metadata

**Goal**: User reading the README sees Lidarr documented as a first-class supported *arr alongside Radarr and Sonarr, with dashboard screenshots refreshed to reflect the v2.5 visual direction, and the architecture decision for the new rail + expandable log recorded in PROJECT.md Key Decisions.
**Depends on**: Phases 48–52 (screenshots must capture the finished v2.5 UI)
**Requirements**: DOCS-01, DOCS-02, DOCS-03
**Success Criteria** (what must be TRUE):
  1. User reading the README sees Lidarr documented alongside Radarr and Sonarr — install notes, config reference, and at least one screenshot include Lidarr as a first-class instance type
  2. User sees README dashboard screenshots refreshed to match the v2.5 visuals (sticky nav, hero Grab Rate card, unified app cards, Recent Activity rail, new Application Log)
  3. User reading PROJECT.md Key Decisions finds a new entry explaining the rationale for the sticky rail + expandable log architecture (sticky positioning, data reuse from existing search_log, vanilla JS only)
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 48. Foundations & Navigation Chrome | 3/3 | Complete | 2026-04-13 |
| 49. Stats & Health Strip | 0/3 | Planning complete | - |
| 50. App Cards & Services Grid | 0/2 | Planning complete | - |
| 51. Application Log Redesign | 0/0 | Not started | - |
| 52. Recent Activity Rail | 0/2 | Planning complete | - |
| 53. Docs & Metadata | 0/0 | Not started | - |
