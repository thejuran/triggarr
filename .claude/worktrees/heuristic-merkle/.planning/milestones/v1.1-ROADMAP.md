# Roadmap: Fetcharr

## Overview

Fetcharr is a single-process automation daemon that cycles through Radarr and Sonarr's wanted/cutoff-unmet lists on a configurable schedule. Security invariants (no API key in any HTTP response) are established from day one and never relaxed.

## Milestones

- ✅ **v1.0 MVP** — Phases 1-8 (shipped 2026-02-24) — [archive](milestones/v1.0-ROADMAP.md)
- 🚧 **v1.1 Ship & Document** — Phases 9-12 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-8) — SHIPPED 2026-02-24</summary>

- [x] Phase 1: Foundation (3/3 plans) — completed 2026-02-23
- [x] Phase 2: Search Engine (3/3 plans) — completed 2026-02-24
- [x] Phase 3: Web UI (3/3 plans) — completed 2026-02-24
- [x] Phase 4: Docker (1/1 plan) — completed 2026-02-24
- [x] Phase 5: Security Hardening (2/2 plans) — completed 2026-02-24
- [x] Phase 6: Bug Fixes & Resilience (3/3 plans) — completed 2026-02-24
- [x] Phase 7: Test Coverage (2/2 plans) — completed 2026-02-24
- [x] Phase 8: Tech Debt Cleanup (1/1 plan) — completed 2026-02-24

</details>

### v1.1 Ship & Document

- [x] **Phase 9: CI/CD Pipeline** - GitHub Actions for testing, linting, and Docker build validation (completed 2026-02-24)
- [x] **Phase 10: Release Pipeline** - Automated Docker image publishing and code review convention (completed 2026-02-24)
- [x] **Phase 11: Search Enhancements** - Hard max limit and persistent search history (completed 2026-02-24)
- [x] **Phase 12: Documentation** - README with install guide, config reference, security model, and screenshots (completed 2026-02-24)

## Phase Details

### Phase 9: CI/CD Pipeline
**Goal**: Every push and PR is automatically validated for correctness, style, and buildability
**Depends on**: Phase 8 (v1.0 codebase complete)
**Requirements**: CICD-01, CICD-02, CICD-03
**Success Criteria** (what must be TRUE):
  1. Pushing a commit to main or opening a PR triggers pytest and all 115+ tests pass
  2. Ruff linting runs on every PR and push to main, failing the build on violations
  3. Docker image builds successfully as part of CI (build validated, not pushed)
**Plans:** 1/1 plans complete
Plans:
- [ ] 09-01-PLAN.md — Ruff config + GitHub Actions CI workflow (pytest, ruff, Docker build)

### Phase 10: Release Pipeline
**Goal**: Docker images are automatically published on push and release, with a documented review convention
**Depends on**: Phase 9
**Requirements**: RELS-01, RELS-02, RELS-03
**Success Criteria** (what must be TRUE):
  1. Pushing to main builds and pushes ghcr.io/thejuran/fetcharr:dev automatically
  2. Pushing a version tag (e.g., v1.1.0) builds and pushes both :latest and the version-tagged image to ghcr.io
  3. CLAUDE.md contains the deep code review convention so Claude offers /deep-review before push
**Plans:** 1/1 plans complete
Plans:
- [ ] 10-01-PLAN.md — GHCR release workflow + CLAUDE.md deep review convention

### Phase 11: Search Enhancements
**Goal**: Users have a safety ceiling on search volume and persistent search history that survives restarts
**Depends on**: Phase 8 (v1.0 codebase; independent of CI/CD phases)
**Requirements**: SRCH-12, SRCH-13
**Success Criteria** (what must be TRUE):
  1. User can configure a hard max items per cycle that caps the per-app counts regardless of individual settings
  2. The hard max is visible and editable in the web UI config editor with validation
  3. Search history is stored in SQLite and survives container restarts (not lost on reboot)
  4. Existing in-memory search log is replaced by or backed by SQLite storage
**Plans:** 2/2 plans complete
Plans:
- [ ] 11-01-PLAN.md — Hard max items per cycle (config + engine + UI + tests)
- [ ] 11-02-PLAN.md — SQLite persistent search history (db module + migration + wiring + tests)

### Phase 12: Documentation
**Goal**: A new user can install and configure Fetcharr from the README alone
**Depends on**: Phase 11 (screenshots capture final feature set)
**Requirements**: DOCS-01, DOCS-02, DOCS-03, DOCS-04
**Success Criteria** (what must be TRUE):
  1. README contains Docker pull command and a working docker-compose.yml example that a new user can copy-paste to run Fetcharr
  2. Every TOML config field is documented with its default value, valid range, and description
  3. README explains the security model — what is protected, what is not, and why there is no authentication
  4. README includes screenshots of the dashboard and config editor showing the actual running UI
**Plans:** 1/1 plans complete
Plans:
- [ ] 12-01-PLAN.md — README with install guide, config reference, security model, and screenshot placeholders

## Progress

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
| 9. CI/CD Pipeline | v1.1 | Complete    | 2026-02-24 | - |
| 10. Release Pipeline | 1/1 | Complete    | 2026-02-24 | - |
| 11. Search Enhancements | 2/2 | Complete    | 2026-02-24 | - |
| 12. Documentation | 1/1 | Complete    | 2026-02-24 | - |
