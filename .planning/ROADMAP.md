# Roadmap: Fetcharr

## Overview

Fetcharr is a single-process automation daemon that cycles through Radarr and Sonarr's wanted/cutoff-unmet lists on a configurable schedule. Security invariants (no API key in any HTTP response) are established from day one and never relaxed.

## Milestones

- ✅ v1.0 MVP -- Phases 1-8 (shipped 2026-02-24) -- [archive](milestones/v1.0-ROADMAP.md)
- ✅ v1.1 Ship & Document -- Phases 9-12 (shipped 2026-02-24) -- [archive](milestones/v1.1-ROADMAP.md)
- ✅ v1.2 Polish & Harden -- Phases 13-16 (shipped 2026-02-24) -- [archive](milestones/v1.2-ROADMAP.md)
- 🚧 v2.0 Closed-Loop Tracking -- Phases 17-21 (incl. 20.1, 20.2) (in progress)

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
- [x] **Phase 19: Tracking Infrastructure** - History polling clients and pure correlation functions for both apps (completed 2026-02-25)
- [x] **Phase 20: Tracking Integration** - Wire tracking into search cycles with outcome updates and lifetime stat increments (completed 2026-02-25)
- [ ] **Phase 20.1: Deep Review — Security & Safety** - Fix async race conditions, XSS, migration correctness, and exception sanitization
- [ ] **Phase 20.2: Deep Review — Code Quality** - Type annotations, off-by-one fixes, dead code cleanup, and config consistency
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

### Phase 20.1: Deep Review — Security & Safety
**Goal**: All security vulnerabilities and data-correctness bugs identified by deep code review are resolved before shipping
**Depends on**: Phase 20
**Requirements**: DRSEC-01, DRSEC-02, DRSEC-03, DRSEC-04, DRSEC-05, DRSEC-06, DRSEC-07, DRSEC-08
**Success Criteria** (what must be TRUE):
  1. `db.row_factory` is never mutated on the shared connection without a `try/finally` guard (or is set on cursor instead)
  2. All dynamic values in `hx-get` URL attributes use `| urlencode` filter
  3. Rate limiter timestamp is written inside `search_lock`, preventing concurrent bypass
  4. `run_migrations` handles a non-existent database file gracefully on fresh install
  5. Migration v1 sets `DEFAULT 'searched'` so v4 backfill only catches truly pre-v1 rows
  6. Migration functions suppress only `sqlite3.OperationalError`, not all exceptions
  7. Exception details stored in `detail` field use sanitized type-based summaries, not raw `str(exc)`
  8. `sourceTitle` from external APIs is truncated before storage in `detail` field
**Plans**: 2 plans

Plans:
- [ ] 20.1-01-PLAN.md — DB safety fixes (row_factory, migration backup, suppress scope, v4 backfill, cursor cleanup)
- [ ] 20.1-02-PLAN.md — Security fixes (XSS urlencode, rate limiter race, str(exc) sanitization, sourceTitle truncation)

### Phase 20.2: Deep Review — Code Quality
**Goal**: All code quality issues from deep review are resolved: type safety, correctness, and consistency
**Depends on**: Phase 20.1
**Requirements**: DRQUAL-01 through DRQUAL-12
**Success Criteria** (what must be TRUE):
  1. `run_tracking_check` and all helpers have full type annotations (`aiosqlite.Connection`, `RadarrClient | None`, `list[GrabEvent]`)
  2. Pass counter starts at 0 so first wrap-around correctly logs "pass 1"
  3. Tracking exception handler in scheduler catches specific types, not bare `except Exception`
  4. Tracking summary logged from exactly one location per cycle (not duplicated)
  5. `SearchRecord` rejects naive datetimes via `__post_init__` validation
  6. `missing_count or 0` replaced with explicit `None` check
  7. Migration loop tolerates version gaps via `sorted(MIGRATIONS.keys())`
  8. `_sonarr_outcome` handles `expected == 0` case at top without dead branch
  9. All cursors use `async with` consistently
  10. Zero ruff violations across `fetcharr/` and `tests/`
  11. `tracking_poll_seconds` config renamed or removed to match actual behavior
  12. `at_least_one_search_count` model validator reinstated on `ArrConfig`
**Plans**: 2 plans

Plans:
- [ ] 20.2-01-PLAN.md — Tracking & correlation cleanup (types, naive datetime guard, or-0, dead branch, duplicate log)
- [ ] 20.2-02-PLAN.md — Engine, scheduler & config fixes (pass counter, except scope, tracking_poll_seconds, model validator, ruff, cursor)

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
Phases execute in numeric order: 17 > 18 > 19 > 20 > 20.1 > 20.2 > 21
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
| 19. Tracking Infrastructure | 2/2 | Complete    | 2026-02-25 | - |
| 20. Tracking Integration | 3/3 | Complete    | 2026-02-25 | - |
| 20.1 Deep Review — Security & Safety | 1/2 | In Progress|  | - |
| 20.2 Deep Review — Code Quality | v2.0 | 0/2 | Not started | - |
| 21. Dashboard & Stats | v2.0 | 0/? | Not started | - |
