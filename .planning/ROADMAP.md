# Roadmap: Triggarr

## Overview

Triggarr is a single-process automation daemon that cycles through Radarr and Sonarr's wanted/cutoff-unmet lists on a configurable schedule, with closed-loop download tracking. Security invariants (no API key in any HTTP response) are established from day one and never relaxed.

## Milestones

- ✅ v1.0 MVP -- Phases 1-8 (shipped 2026-02-24) -- [archive](milestones/v1.0-ROADMAP.md)
- ✅ v1.1 Ship & Document -- Phases 9-12 (shipped 2026-02-24) -- [archive](milestones/v1.1-ROADMAP.md)
- ✅ v1.2 Polish & Harden -- Phases 13-16 (shipped 2026-02-24) -- [archive](milestones/v1.2-ROADMAP.md)
- ✅ v2.0 Closed-Loop Tracking -- Phases 17-22 (shipped 2026-03-09) -- [archive](milestones/v2.0-ROADMAP.md)
- ✅ v2.1 Harden & Fix -- Phases 23-24 (shipped 2026-03-09) -- [archive](milestones/v2.1-ROADMAP.md)
- **v2.2 Skip Unreleased Media -- Phases 25-27 (complete)**

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

### v2.2 Skip Unreleased Media

- [x] **Phase 25: Filter Foundation** - Config model field and pure filter functions with comprehensive edge-case tests (completed 2026-03-09)
- [x] **Phase 26: Settings UI & Engine Integration** - Web UI toggle, form save/load, and conditional filter wiring into search pipeline (completed 2026-03-09)
- [x] **Phase 27: Dashboard Display** - Eligible-count tracking and skip-count indicators on app cards (completed 2026-03-09)

## Phase Details

### Phase 25: Filter Foundation
**Goal**: The skip-unreleased config option exists and the filtering logic correctly identifies unreleased movies
**Depends on**: Phase 24
**Requirements**: CFG-02, FILT-01, FILT-02, FILT-03, FILT-04
**Success Criteria** (what must be TRUE):
  1. `skip_unreleased` boolean field exists in GeneralConfig with default `true`, persists in TOML config file
  2. Radarr movies without a past digital or physical release date are identified for skipping (filter function returns only eligible movies)
  3. Movies with null/missing release dates pass through the filter and are searched (not silently blackholed)
  4. Sonarr unaired-episode filtering remains unconditional and unchanged (no new Sonarr filter logic added)
  5. Cutoff-unmet items are never passed through the release-date filter
**Plans:** 1/1 plans complete

Plans:
- [x] 25-01-PLAN.md -- Config field, filter function, and comprehensive tests (TDD)

### Phase 26: Settings UI & Engine Integration
**Goal**: Users can toggle skip-unreleased from the web UI and the filter activates conditionally in the search pipeline
**Depends on**: Phase 25
**Requirements**: CFG-01
**Success Criteria** (what must be TRUE):
  1. User can enable/disable skip-unreleased via a checkbox toggle on the settings page
  2. Toggle state saves correctly and survives settings page reload (three-location round-trip: model, template, route)
  3. When enabled, Radarr missing-queue searches skip movies without a past release date (filter runs after filter_monitored, before cursor/slice_batch)
  4. When disabled, all monitored Radarr missing items are searched regardless of release date
**Plans:** 1/1 plans complete

Plans:
- [x] 26-01-PLAN.md -- Settings UI toggle + engine pipeline conditional filter wiring

### Phase 27: Dashboard Display
**Goal**: Users can see how many items are eligible vs total and when items are being skipped
**Depends on**: Phase 26
**Requirements**: DASH-01, DASH-02
**Success Criteria** (what must be TRUE):
  1. Dashboard app cards show eligible item count alongside total count (e.g., "X eligible of Y total")
  2. When items are being skipped, a skip-count indicator is visible on the relevant app card
  3. When skip-unreleased is disabled or no items are skipped, no misleading skip indicator appears
**Plans:** 1/1 plans complete

Plans:
- [x] 27-01-PLAN.md -- Eligible-count state tracking, route threading, and app card display with skip badge

## Progress

**Execution Order:**
Phases execute in numeric order: 25 -> 26 -> 27

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 3/3 | Complete | 2026-02-23 |
| 2. Search Engine | v1.0 | 3/3 | Complete | 2026-02-24 |
| 3. Web UI | v1.0 | 3/3 | Complete | 2026-02-24 |
| 4. Docker | v1.0 | 1/1 | Complete | 2026-02-24 |
| 5. Security Hardening | v1.0 | 2/2 | Complete | 2026-02-24 |
| 6. Bug Fixes & Resilience | v1.0 | 3/3 | Complete | 2026-02-24 |
| 7. Test Coverage | v1.0 | 2/2 | Complete | 2026-02-24 |
| 8. Tech Debt Cleanup | v1.0 | 1/1 | Complete | 2026-02-24 |
| 9. CI/CD Pipeline | v1.1 | 1/1 | Complete | 2026-02-24 |
| 10. Release Pipeline | v1.1 | 1/1 | Complete | 2026-02-24 |
| 11. Search Enhancements | v1.1 | 2/2 | Complete | 2026-02-24 |
| 12. Documentation | v1.1 | 1/1 | Complete | 2026-02-24 |
| 13. CI & Search Diagnostics | v1.2 | 2/2 | Complete | 2026-02-24 |
| 14. Dashboard Observability | v1.2 | 2/2 | Complete | 2026-02-24 |
| 15. Search History UI | v1.2 | 2/2 | Complete | 2026-02-24 |
| 16. Deep Code Review | v1.2 | 2/2 | Complete | 2026-02-24 |
| 17. Foundation & DB Preparation | v2.0 | 3/3 | Complete | 2026-02-25 |
| 18. Security & Operations | v2.0 | 2/2 | Complete | 2026-02-25 |
| 19. Tracking Infrastructure | v2.0 | 2/2 | Complete | 2026-02-25 |
| 20. Tracking Integration | v2.0 | 3/3 | Complete | 2026-02-25 |
| 20.1 Deep Review — Security | v2.0 | 2/2 | Complete | 2026-02-26 |
| 20.2 Deep Review — Quality | v2.0 | 2/2 | Complete | 2026-02-26 |
| 21. Dashboard & Stats | v2.0 | 2/2 | Complete | 2026-03-07 |
| 22. Rename to Triggarr | v2.0 | 2/2 | Complete | 2026-03-07 |
| 23. Deploy Fixes | v2.1 | 1/1 | Complete | 2026-03-09 |
| 24. Hardening | v2.1 | 1/1 | Complete | 2026-03-09 |
| 25. Filter Foundation | v2.2 | 1/1 | Complete | 2026-03-09 |
| 26. Settings UI & Engine Integration | v2.2 | 1/1 | Complete | 2026-03-09 |
| 27. Dashboard Display | v2.2 | Complete    | 2026-03-09 | 2026-03-09 |
