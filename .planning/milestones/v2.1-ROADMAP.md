# Roadmap: Triggarr

## Overview

Triggarr is a single-process automation daemon that cycles through Radarr and Sonarr's wanted/cutoff-unmet lists on a configurable schedule, with closed-loop download tracking. Security invariants (no API key in any HTTP response) are established from day one and never relaxed.

## Milestones

- ✅ v1.0 MVP -- Phases 1-8 (shipped 2026-02-24) -- [archive](milestones/v1.0-ROADMAP.md)
- ✅ v1.1 Ship & Document -- Phases 9-12 (shipped 2026-02-24) -- [archive](milestones/v1.1-ROADMAP.md)
- ✅ v1.2 Polish & Harden -- Phases 13-16 (shipped 2026-02-24) -- [archive](milestones/v1.2-ROADMAP.md)
- ✅ v2.0 Closed-Loop Tracking -- Phases 17-22 (shipped 2026-03-09) -- [archive](milestones/v2.0-ROADMAP.md)
- 🚧 v2.0 Harden & Fix -- Phase 23-24 (in progress)

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

### v2.0 Harden & Fix (In Progress)

**Milestone Goal:** Fix deployment friction -- configurable config path and reverse proxy compatibility.

- [x] **Phase 23: Deploy Fixes** - Configurable config directory and reverse proxy CSS compatibility (completed 2026-03-09)
- [x] **Phase 24: Hardening** - Config path validation, temp file cleanup, freeze constraint docs and tests (completed 2026-03-09)

## Phase Details

### Phase 23: Deploy Fixes
**Goal**: Users can deploy Triggarr in any Docker environment without path or proxy workarounds
**Depends on**: Phase 22
**Requirements**: DEPLOY-01, DEPLOY-02
**Success Criteria** (what must be TRUE):
  1. User can set `TRIGGARR_CONFIG_DIR` env var and the container reads/writes config and database from that directory
  2. User can deploy behind a reverse proxy (e.g., Nginx, Caddy, Traefik) and all CSS/static assets load correctly without broken styles
  3. Existing deployments without `TRIGGARR_CONFIG_DIR` set continue to work with the default config path (backward compatible)
**Plans**: 1 plan

Plans:
- [x] 23-01-PLAN.md -- Configurable config directory and reverse proxy static asset support

### Phase 24: Hardening: config validation and temp file cleanup
**Goal**: Config path validation rejects misconfiguration at startup, temp file writes are safe, and freeze constraints are documented and tested
**Depends on**: Phase 23
**Requirements**: HARDEN-01, HARDEN-02, HARDEN-03, HARDEN-04
**Success Criteria** (what must be TRUE):
  1. Setting TRIGGARR_CONFIG_DIR to a relative or traversal path fails fast with a clear error
  2. Temp file is cleaned up if os.replace fails during settings save
  3. Module-level constant freeze constraint is documented in code comments
  4. Tests cover path validation and frozen constant behavior
**Plans**: 1 plan

Plans:
- [ ] 24-01-PLAN.md -- Config path validation, temp file cleanup, freeze docs and tests

## Progress

**Execution Order:**
Phase 23 -> Phase 24

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
| 23. Deploy Fixes | v2.0 | 1/1 | Complete | 2026-03-09 |
| 24. Hardening | 1/1 | Complete    | 2026-03-09 | - |
