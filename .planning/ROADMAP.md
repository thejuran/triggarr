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
- ✅ v2.5 Dashboard UI Refresh -- Phases 48-53 (shipped 2026-04-13) -- [archive](milestones/v2.5-ROADMAP.md)
- ✅ v2.6 Built-In Authentication -- Phases 54-59 (shipped 2026-04-15) -- [archive](milestones/v2.6-ROADMAP.md)
- 🚧 **v2.7 Dashboard Scale Refresh** -- Phases 60-62 (in progress)

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

<details>
<summary>v2.5 Dashboard UI Refresh (Phases 48-53) -- SHIPPED 2026-04-13</summary>

- [x] Phase 48: Foundations & Navigation Chrome (3/3 plans) -- completed 2026-04-13
- [x] Phase 49: Stats & Health Strip (3/3 plans) -- completed 2026-04-13
- [x] Phase 50: App Cards & Services Grid (2/2 plans) -- completed 2026-04-13
- [x] Phase 51: Application Log Redesign (3/3 plans) -- completed 2026-04-13
- [x] Phase 52: Recent Activity Rail (2/2 plans) -- completed 2026-04-13
- [x] Phase 53: Docs & Metadata (2/2 plans) -- completed 2026-04-13

</details>

<details>
<summary>v2.6 Built-In Authentication (Phases 54-59) -- SHIPPED 2026-04-15</summary>

- [x] Phase 54: Auth Config & Helpers (2/2 plans) -- completed 2026-04-14
- [x] Phase 55: Auth Middleware & Health Endpoint (2/2 plans) -- completed 2026-04-15
- [x] Phase 56: First-Run Setup & Login (4/4 plans) -- completed 2026-04-15
- [x] Phase 57: Settings Security & Nav Logout (2/2 plans) -- completed 2026-04-15
- [x] Phase 58: Auth Test Suite (2/2 plans) -- completed 2026-04-15
- [x] Phase 59: Security Hardening (4/4 plans) -- completed 2026-04-15

</details>

### v2.7 Dashboard Scale Refresh (In Progress)

**Milestone Goal:** Pixel-exact port of the finalized AIDesigner artifact to Triggarr's Jinja2/Tailwind templates -- spacious header with Phosphor icons, scaled stat cards, refined app cards with colored borders, card-based activity rail, and updated log viewer.

- [x] **Phase 60: Foundation & Header** - Font discipline, Phosphor icons, spacious header with nav icons, status pill, and favicon (completed 2026-04-16)
- [ ] **Phase 61: Stat Cards & App Cards** - Scaled stat cards with hero numbers and mini bars, refined app cards with colored borders
- [ ] **Phase 62: Activity Rail & Log Viewer** - Card-based activity rail with fading opacity, refined log viewer controls

## Phase Details

### Phase 60: Foundation & Header
**Goal**: Users see a spacious, icon-rich header with correct font discipline across the entire dashboard
**Depends on**: Nothing (first phase of v2.7)
**Requirements**: FONT-01, FONT-02, HDR-01, HDR-02, HDR-03, HDR-04, HDR-05, HDR-06
**Success Criteria** (what must be TRUE):
  1. Body text throughout the dashboard renders in system sans-serif; Geist Mono appears only on designated elements (version badge, TAILING/LIVE labels, log viewer body, log filter, activity rail badges/timestamps, schedule rows)
  2. Header has visibly increased vertical padding and each navigation link displays a Phosphor icon beside its label at text-[15px]
  3. Navigation links are center-aligned with gap-6 spacing, and the logout link is visually separated by a pipe divider with a sign-out icon
  4. A "Connection Stable" status pill with pulsing green dot appears on the right side of the header
  5. A favicon/app icon appears to the left of the "Triggarr" logo text in the header
**Plans**: 3 plans
Plans:
- [x] 60-01-PLAN.md -- Vendor Phosphor Icons, add CSS color tokens, font discipline foundation
- [x] 60-02-PLAN.md -- Header restructure with three-zone layout, nav icons, logout divider
- [x] 60-03-PLAN.md -- Connection status pill wiring and phase test suite
**UI hint**: yes

### Phase 61: Stat Cards & App Cards
**Goal**: Users see larger, more spacious stat cards and app cards with colored accents matching the design artifact
**Depends on**: Phase 60
**Requirements**: STAT-01, STAT-02, STAT-03, STAT-04, CARD-01, CARD-02, CARD-03, CARD-04
**Success Criteria** (what must be TRUE):
  1. Stat cards display hero numbers at text-[32px]/text-[36px] scale with p-5 padding, and the Grab Rate card includes per-app mini progress bars (orange for Radarr, blue for Sonarr)
  2. Movies/Series/Next Scan stat cards show colored Phosphor icons matching their respective app type
  3. App cards have a colored left border per app type (orange Radarr, blue Sonarr, red unreachable) with title and connection status pill separated by a bottom border
  4. App card missing/cutoff stats appear in recessed sub-cards and the Search Now button uses an app-colored hover accent
**Plans**: 2 plans
Plans:
- [x] 61-01-PLAN.md -- CSS tokens, stat card scaling with Phosphor icons and horizontal mini bars
- [ ] 61-02-PLAN.md -- App card sectioned layout with colored borders, recessed sub-cards, and app-colored buttons
**UI hint**: yes

### Phase 62: Activity Rail & Log Viewer
**Goal**: Users see a refined activity rail with card-based entries and an updated log viewer with icon-based controls
**Depends on**: Phase 61
**Requirements**: RAIL-01, RAIL-02, RAIL-03, LOG-01, LOG-02, LOG-03
**Success Criteria** (what must be TRUE):
  1. Activity rail items render as card-based entries with speech bubble pointers and colored timeline dots; app badges use font-mono with colored dot indicators
  2. Older activity rail entries visually fade with decreasing opacity
  3. Log viewer header displays Phosphor icons for pause/expand controls, the TAILING badge uses font-mono with a pulsing green dot, and the log level filter uses a font-mono styled select dropdown
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 60 -> 61 -> 62

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 60. Foundation & Header | v2.7 | 3/3 | Complete    | 2026-04-16 |
| 61. Stat Cards & App Cards | v2.7 | 1/2 | In Progress|  |
| 62. Activity Rail & Log Viewer | v2.7 | 0/TBD | Not started | - |
