# Roadmap: Fetcharr

## Overview

Fetcharr is a single-process automation daemon that cycles through Radarr and Sonarr's wanted/cutoff-unmet lists on a configurable schedule. Security invariants (no API key in any HTTP response) are established from day one and never relaxed.

## Milestones

- ✅ v1.0 MVP -- Phases 1-8 (shipped 2026-02-24) -- [archive](milestones/v1.0-ROADMAP.md)
- ✅ v1.1 Ship & Document -- Phases 9-12 (shipped 2026-02-24) -- [archive](milestones/v1.1-ROADMAP.md)
- ✅ v1.2 Polish & Harden -- Phases 13-16 (shipped 2026-02-24) -- [archive](milestones/v1.2-ROADMAP.md)
- 🚧 v2.0 Closed-Loop Tracking -- Phases 17-21 (in progress)

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

### 🚧 v2.0 Closed-Loop Tracking (In Progress)

**Milestone Goal:** Evolve fetcharr from fire-and-forget to closed-loop: detect when searched items are actually grabbed, show per-item and aggregate feedback on the dashboard, track lifetime effectiveness stats, and resolve all deferred tech debt.

- [x] **Phase 17: Foundation & DB Preparation** - Schema migration, WAL mode, and config model additions required before tracking or tech debt work (completed 2026-02-25)
- [x] **Phase 18: Security & Operations** - Rate limiting, CSRF hardening, health check, and graceful shutdown (completed 2026-02-25)
- [ ] **Phase 19: Tracking Infrastructure** - History polling clients and pure correlation functions for both apps
- [ ] **Phase 20: Tracking Integration** - Wire tracking into search cycles with outcome updates and lifetime stat increments
- [ ] **Phase 21: Dashboard & Stats** - Outcome badges, effectiveness rates, lifetime stats cards, and time-to-grab metric

## Phase Details

### Phase 17: Foundation & DB Preparation
**Goal**: Database and config infrastructure supports tracking correlation and all new configurable behaviors
**Depends on**: Phase 16 (v1.2 complete)
**Requirements**: DEBT-03, DEBT-04, DEBT-07, DEBT-08, TRACK-07, TRACK-08
**Success Criteria** (what must be TRUE):
  1. Application starts with a single shared SQLite connection in WAL mode instead of connection-per-operation
  2. Search history entries store item ID, season number (Sonarr), and missing episode count at insert time
  3. User can configure tracking window duration, request timeout, pageSize, and max history rows via settings
  4. Pruning logic preserves rows with pending tracking status (outcome = "searched") to prevent correlation data loss
  5. A lifetime_stats table exists in SQLite and persists across container restarts
**Plans**: 3 plans

Plans:
- [ ] 17-01-PLAN.md — Config model additions (GeneralConfig fields + TOML template)
- [ ] 17-02-PLAN.md — Schema migration system + db.py refactor (shared connection, new tables/columns, tracking-aware pruning)
- [ ] 17-03-PLAN.md — Wire shared connection + configurable settings through all callers

### Phase 18: Security & Operations
**Goal**: Production safety hardening is complete before the tracking feature ships
**Depends on**: Phase 17
**Requirements**: DEBT-01, DEBT-02, DEBT-05, DEBT-06
**Success Criteria** (what must be TRUE):
  1. Rapid repeated clicks on "Search Now" return HTTP 429 after the first request within the rate limit window
  2. Settings POST requests without valid Origin/Referer headers are rejected
  3. Container orchestrators can probe /health and receive 200 when both apps are reachable, or 503 when either is unreachable
  4. Stopping the container with SIGTERM cleanly closes the database connection, HTTP clients, and scheduler without data loss
**Plans**: 2 plans

Plans:
- [ ] 18-01-PLAN.md — Rate limiter on search-now + GET /health endpoint + Dockerfile HEALTHCHECK update (DEBT-01, DEBT-05)
- [ ] 18-02-PLAN.md — Graceful shutdown lock-drain + CSRF /settings integration test (DEBT-02, DEBT-06)

### Phase 19: Tracking Infrastructure
**Goal**: Isolated, testable components exist for polling grab history and classifying outcomes for both Radarr and Sonarr
**Depends on**: Phase 17
**Requirements**: TRACK-01, TRACK-02, TRACK-03
**Success Criteria** (what must be TRUE):
  1. System can fetch grab history for a specific movie from Radarr filtered by event type
  2. System can fetch grab history for a specific series from Sonarr filtered by event type
  3. Pure correlation functions correctly match grabs to fetcharr searches using timestamp window and item ID, with unit tests covering match, no-match, and edge cases
**Plans**: TBD

Plans:
- [ ] 19-01: TBD

### Phase 20: Tracking Integration
**Goal**: Search cycles automatically detect and record whether triggered searches resulted in grabs
**Depends on**: Phase 18, Phase 19
**Requirements**: TRACK-04, TRACK-05, TRACK-06
**Success Criteria** (what must be TRUE):
  1. After a Radarr search, the search history entry updates from "searched" to "grabbed" when the movie appears in grab history within the tracking window
  2. After a Sonarr season search, the entry updates to "partial" when some but not all missing episodes are grabbed, and to "grabbed" when all missing episodes are resolved
  3. Entries that receive no grabs within the tracking window resolve to "unresolved" automatically
  4. Tracking failures (network errors, app downtime) are non-fatal -- the entry retains "searched" status and the cycle completes normally
**Plans**: TBD

Plans:
- [ ] 20-01: TBD

### Phase 21: Dashboard & Stats
**Goal**: Users can see at a glance how effective their search automation is, with per-item outcomes and aggregate lifetime stats
**Depends on**: Phase 20
**Requirements**: STATS-01, STATS-02, STATS-03, STATS-04, STATS-05
**Success Criteria** (what must be TRUE):
  1. Dashboard displays aggregate search effectiveness as a percentage (X of Y searches resulted in grabs) with per-app breakdown
  2. Dashboard shows lifetime stats cards: movies found, movies updated, episodes found, episodes updated -- counting only fetcharr-triggered grabs
  3. Dashboard shows average time-to-grab metric (mean duration from search to grab detection)
  4. Search history entries display color-coded outcome badges (grabbed/partial/unresolved) with tooltips explaining each state
  5. New config options (tracking window, timeout, pageSize, max rows) are editable in the settings UI
**Plans**: TBD

Plans:
- [ ] 21-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 17 > 18 > 19 > 20 > 21
(Phase 19 can execute in parallel with Phase 18 -- both depend only on Phase 17)

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
| 17. Foundation & DB Preparation | 3/3 | Complete    | 2026-02-25 | - |
| 18. Security & Operations | 2/2 | Complete    | 2026-02-25 | - |
| 19. Tracking Infrastructure | v2.0 | 0/? | Not started | - |
| 20. Tracking Integration | v2.0 | 0/? | Not started | - |
| 21. Dashboard & Stats | v2.0 | 0/? | Not started | - |
