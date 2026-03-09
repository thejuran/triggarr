# Roadmap: Fetcharr

## Overview

Fetcharr is a single-process automation daemon that cycles through Radarr and Sonarr's wanted/cutoff-unmet lists on a configurable schedule. Security invariants (no API key in any HTTP response) are established from day one and never relaxed.

## Milestones

- v1.0 MVP -- Phases 1-8 (shipped 2026-02-24) -- [archive](milestones/v1.0-ROADMAP.md)
- v1.1 Ship & Document -- Phases 9-12 (shipped 2026-02-24) -- [archive](milestones/v1.1-ROADMAP.md)
- **v1.2 Polish & Harden** -- Phases 13-16 (in progress)

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

### v1.2 Polish & Harden

**Milestone Goal:** Harden search resilience, improve dashboard observability, and ship CI to GitHub.

- [x] **Phase 13: CI & Search Diagnostics** - Push CI to GitHub and add backend search diagnostic logging (completed 2026-02-24)
- [x] **Phase 14: Dashboard Observability** - Enhance dashboard with position progress, app logs, and search detail (completed 2026-02-24)
- [x] **Phase 15: Search History UI** - Browsable search history with filtering and pagination (completed 2026-02-24)
- [x] **Phase 16: Deep Code Review** - Comprehensive code review of v1.2 changes with fix recommendations (completed 2026-02-24)

## Phase Details

### Phase 16: Deep Code Review
**Goal**: All warning-level (80+) issues from v1.2 code review are fixed and documented
**Depends on**: Phase 15
**Success Criteria** (what must be TRUE):
  1. All warning-level (80+) issues from the review are addressed
  2. All CLAUDE.md compliance violations are fixed
  3. Tests pass after fixes (`pytest tests/ -x`)
**Plans**: 2 plans
**Report**: [16-REVIEW.md](phases/16-deep-code-review/16-REVIEW.md)

Plans:
- [ ] 16-01-PLAN.md -- Security and DB fixes (W1 XSS, W4 cursors, W5 zero division, W7 SSRF) with regression tests
- [ ] 16-02-PLAN.md -- Routes fixes (W2 atomic write, W3 page validation, W8 narrow except) and review doc update

### Phase 13: CI & Search Diagnostics
**Goal**: CI runs on GitHub remote runners and search cycles produce diagnostic logs for troubleshooting
**Depends on**: Phase 12
**Requirements**: CICD-04, SRCH-15, SRCH-16
**Success Criteria** (what must be TRUE):
  1. CI workflow runs on GitHub Actions and all tests pass on remote runners
  2. Fetcharr logs the detected Sonarr API version (v3 or v4) at startup
  3. Each search cycle logs the total item count fetched so users can detect pageSize truncation in large libraries
**Plans**: 2 plans

Plans:
- [ ] 13-01-PLAN.md -- CI workflow hardening with caching for remote runners
- [ ] 13-02-PLAN.md -- Sonarr API version detection and per-cycle diagnostic logging

### Phase 14: Dashboard Observability
**Goal**: Users can see detailed search progress, outcomes, and application logs directly in the web dashboard
**Depends on**: Phase 13
**Requirements**: WEBU-09, WEBU-10, WEBU-11
**Success Criteria** (what must be TRUE):
  1. Dashboard position labels display "X of Y" format (e.g., "3 of 47") instead of bare cursor numbers
  2. A dedicated section in the dashboard shows recent application log messages from loguru
  3. Search log entries display outcome/detail information (e.g., search triggered, error encountered) alongside item name and timestamp
**Plans**: 2 plans

Plans:
- [ ] 14-01-PLAN.md -- Position labels ("X of Y") and search log outcome/detail
- [ ] 14-02-PLAN.md -- Application log viewer section with loguru ring buffer

### Phase 15: Search History UI
**Goal**: Users can browse and filter their complete search history beyond the dashboard's recent log
**Depends on**: Phase 14
**Requirements**: SRCH-14
**Success Criteria** (what must be TRUE):
  1. User can navigate to a search history page from the dashboard
  2. User can filter search history by app (Radarr/Sonarr) and queue type (missing/cutoff)
  3. Search history displays with pagination so large histories remain navigable
**Plans**: 2 plans

Plans:
- [ ] 15-01-PLAN.md -- Backend query with filtering/pagination, history page template, nav link, htmx partial
- [ ] 15-02-PLAN.md -- Tests for search history query, route, and template rendering

## Progress

**Execution Order:**
Phases execute in numeric order: 13 -> 14 -> 15 -> 16

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
| 13. CI & Search Diagnostics | 2/2 | Complete    | 2026-02-24 | - |
| 14. Dashboard Observability | 2/2 | Complete    | 2026-02-24 | - |
| 15. Search History UI | 2/2 | Complete    | 2026-02-24 | - |
| 16. Deep Code Review | 2/2 | Complete    | 2026-02-24 | - |
