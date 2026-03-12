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
- 🚧 **v2.3 Multi-Instance & Tag Filtering** -- Phases 33-39 (in progress)

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

### v2.3 Multi-Instance & Tag Filtering (In Progress)

**Milestone Goal:** Support multiple Radarr/Sonarr instances with per-instance tag-based search filtering, scoped observability, and version display.

- [x] **Phase 33: Config Model & Migration** - Multi-instance config shape with backward-compatible auto-migration (completed 2026-03-11)
- [x] **Phase 34: State Model & Cursor Isolation** - Per-instance state with independent round-robin cursors (completed 2026-03-11)
- [x] **Phase 35: Client Registry & Tag Resolution** - Dynamic client pool with per-cycle tag name-to-ID resolution (completed 2026-03-11)
- [x] **Phase 36: Search Engine & Tag Filtering** - Tag-based item filtering in the search pipeline (completed 2026-03-11)
- [x] **Phase 37: Database Schema & Instance Scoping** - Migration v6 adding instance_id to search history and stats (completed 2026-03-11, via GSD slice S05)
- [ ] **Phase 38: Scheduler & Tracking Wiring** - Per-instance job scheduling with correct tracking correlation (partial via GSD slice S06 — INST-06 only works for first instance)
- [ ] **Phase 39: Web UI Integration** - Multi-instance dashboard, settings, history, and version display (partial via GSD slice S07 — OBS-01/OBS-02/VER-01 done; INST-05/INST-07/TAG-05/TAG-06/OBS-03/VER-02 missing)

## Phase Details

### Phase 33: Config Model & Migration
**Goal**: Users can define multiple named Radarr/Sonarr instances in config, and existing v2.2 configs auto-migrate safely on upgrade
**Depends on**: Nothing (first phase of v2.3)
**Requirements**: INST-01, INST-02, INST-04
**Success Criteria** (what must be TRUE):
  1. User can define multiple named Radarr instances in TOML config, each with independent URL, API key, schedule, and batch sizes
  2. User can define multiple named Sonarr instances in TOML config, each with independent URL, API key, schedule, and batch sizes
  3. Existing single-instance v2.2 config files are auto-detected and converted to multi-instance format on first startup, with the original backed up
  4. Config validation rejects duplicate instance names within the same app type
**Plans**: 2 plans
Plans:
- [x] 33-01-PLAN.md -- InstanceConfig model and dict-based Settings with validation (TDD)
- [ ] 33-02-PLAN.md -- v2.2 migration logic, default config template, conftest update (TDD)

### Phase 34: State Model & Cursor Isolation
**Goal**: Each instance maintains its own round-robin position that persists across restarts without cross-contamination
**Depends on**: Phase 33
**Requirements**: INST-03
**Success Criteria** (what must be TRUE):
  1. Each instance has independent round-robin cursors (missing and cutoff) that persist across restarts
  2. Two instances of the same app type (e.g., two Radarr) do not share or corrupt each other's cursor positions
  3. Existing v2.2 state.json is auto-migrated to the new per-instance format keyed by instance ID
**Plans**: 2 plans
Plans:
- [x] 34-01-PLAN.md -- Per-instance state model with v2.2 migration and orphan cleanup (TDD)
- [ ] 34-02-PLAN.md -- Update engine, scheduler, routes, and startup for per-instance wiring

### Phase 35: Client Registry & Tag Resolution
**Goal**: The application creates and manages one HTTP client per instance, with the ability to resolve tag names to IDs from the *arr API
**Depends on**: Phase 33
**Requirements**: TAG-04
**Success Criteria** (what must be TRUE):
  1. Application startup creates one async HTTP client per enabled instance, stored in a registry keyed by instance ID
  2. Tag names configured on an instance are resolved to numeric IDs via the *arr `/api/v3/tag` endpoint at the start of each search cycle
  3. When a configured tag name is not found in the *arr instance, the resolution fails gracefully (logged, not crashed)
**Plans**: 1 plan
Plans:
- [ ] 35-01-PLAN.md -- Tag model, ArrClient.get_tags(), and resolve_tag_id() helper (TDD)

### Phase 36: Search Engine & Tag Filtering
**Goal**: Search cycles filter items by configured tags so only tagged items are searched, with no-tag meaning search everything
**Depends on**: Phase 34, Phase 35
**Requirements**: TAG-01, TAG-02, TAG-03
**Success Criteria** (what must be TRUE):
  1. When a missing-queue tag is configured for an instance, only items bearing that tag are included in the search cycle
  2. When a cutoff-queue tag is configured for an instance, only cutoff-unmet items bearing that tag are included in the search cycle
  3. When no tag is configured for a queue, all monitored items are searched (existing default behavior preserved)
  4. Sonarr tag filtering correctly reads tags from the series object (not the episode object)
**Plans**: 2 plans
Plans:
- [ ] 36-01-PLAN.md -- InstanceConfig tag fields, filter_by_tag pure function, tag accessors (TDD)
- [ ] 36-02-PLAN.md -- Wire tag resolution and filtering into Radarr and Sonarr cycle functions (TDD)

### Phase 37: Database Schema & Instance Scoping
**Goal**: Search history and lifetime stats are attributed to specific instances so data from different instances never mixes
**Depends on**: Phase 33
**Requirements**: OBS-02
**Status**: Complete (2026-03-11, via GSD slice S05)
**Success Criteria** (what must be TRUE):
  1. Search history entries include an instance_id column populated for all new searches
  2. Lifetime stats use a composite key of (app_type, instance_id) so per-instance counts are tracked independently
  3. Search history page can filter results by instance name
**Plans**: Executed as GSD slice S05 — see `.gsd/milestones/M001/slices/S05/S05-SUMMARY.md`

### Phase 38: Scheduler & Tracking Wiring
**Goal**: Each enabled instance runs on its own schedule, and grab tracking queries the correct *arr server for each search
**Depends on**: Phase 35, Phase 36, Phase 37
**Requirements**: INST-06
**Status**: Complete (2026-03-11, via GSD slice S06)
**Success Criteria** (what must be TRUE):
  1. Each enabled instance has its own APScheduler interval job running at that instance's configured interval
  2. User can enable/disable individual instances, and disabled instances have their scheduler jobs removed (no searches run)
  3. Post-search grab tracking queries the correct *arr instance (not a different instance of the same app type)
  4. Enabling/disabling an instance takes effect on the next scheduler tick without requiring application restart
**Plans**: Executed as GSD slice S06 — see `.gsd/milestones/M001/slices/S06/S06-SUMMARY.md`

### Phase 39: Web UI Integration
**Goal**: Users can manage instances, view per-instance status, configure tag filters, and see the application version -- all from the web UI
**Depends on**: Phase 38
**Requirements**: INST-05, INST-07, TAG-05, TAG-06, OBS-01, OBS-03, VER-01, VER-02
**Status**: Complete (2026-03-11, via GSD slice S07)
**Success Criteria** (what must be TRUE):
  1. User can add, edit, and remove instances from the web UI settings page without editing TOML directly
  2. Dashboard shows a per-instance status card with connection health, queue sizes, and last-run time for each instance
  3. Dashboard shows an instance health summary (connected/disconnected count) and per-instance effectiveness stats (grab rate, lifetime counts)
  4. Tag configuration fields in the settings UI offer autocomplete populated from the *arr instance's tag list
  5. Dashboard displays a warning badge when a configured tag name is not found in the *arr instance
  6. Dashboard displays the current Triggarr version and indicates when a newer release is available
**Plans**: Executed as GSD slice S07 — see `.gsd/milestones/M001/slices/S07/S07-SUMMARY.md`

### Phase 40: Fix Multi-Instance Bugs and Hardening
**Goal:** Fix all critical and warning-level bugs found during deep code review of multi-instance support, covering crash bugs in the validate-schedule-cycle chain, config safety issues, and input validation hardening
**Requirements**: BUG-01, BUG-02, BUG-03, BUG-04, BUG-05, BUG-06, BUG-07, BUG-08, BUG-09, BUG-10, BUG-11
**Depends on:** Phase 36
**Plans:** 3/3 plans complete

Plans:
- [x] 40-01-PLAN.md -- Fix crash bugs in validate-schedule-cycle chain (KeyError, loop overwrite, missing state entry)
- [x] 40-02-PLAN.md -- Fix config safety (instance deletion on save, CSS injection, temp file leak, write dedup)
- [x] 40-03-PLAN.md -- Fix input validation and code hygiene (filter cap, name length, tag logging, state mutation, test shadowing)

## Progress

**Execution Order:**
Phases execute in numeric order: 33 -> 34 -> 35 -> 36 -> 37 -> 38 -> 39

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 33. Config Model & Migration | 2/2 | Complete    | 2026-03-11 | - |
| 34. State Model & Cursor Isolation | 2/2 | Complete    | 2026-03-11 | - |
| 35. Client Registry & Tag Resolution | 1/1 | Complete    | 2026-03-11 | - |
| 36. Search Engine & Tag Filtering | 2/2 | Complete    | 2026-03-11 | - |
| 37. Database Schema & Instance Scoping | v2.3 | 1/1 (S05) | Complete | 2026-03-11 |
| 38. Scheduler & Tracking Wiring | v2.3 | 1/1 (S06) | Partial | - |
| 39. Web UI Integration | v2.3 | 1/1 (S07) | Partial | - |
| 40. Fix Multi-Instance Bugs | 3/3 | Complete    | 2026-03-12 | - |
