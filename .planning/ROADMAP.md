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
- 🚧 **v2.4 Community Polish & Test Hardening** -- Phases 45-47 (in progress)

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

### 🚧 v2.4 Community Polish & Test Hardening (In Progress)

**Milestone Goal:** Add community health files for open-source readiness and harden test coverage for unhappy paths.

- [x] **Phase 45: Community Health & Repo Metadata** - Contributing guide, security policy, issue templates, PR template, and GitHub repo setup -- completed 2026-04-09
- [ ] **Phase 46: Test Hardening -- Infrastructure Failures** - Unhappy-path tests for connection failures and bad API responses
- [ ] **Phase 47: Test Hardening -- State & Search Edge Cases** - Unhappy-path tests for corrupt state/config and search logic edge cases

## Phase Details

### Phase 45: Community Health & Repo Metadata
**Goal**: Contributors and users can find clear guidance on how to report issues, submit changes, and report vulnerabilities
**Depends on**: Phase 44
**Requirements**: COMM-01, COMM-02, COMM-03, COMM-04, COMM-05, COMM-06, COMM-07, META-01, META-02
**Success Criteria** (what must be TRUE):
  1. A contributor visiting the repo can read CONTRIBUTING.md and understand how to fork, branch, run tests, lint, and open a PR
  2. A security researcher visiting the repo can read SECURITY.md and find vulnerability reporting instructions plus a summary of Triggarr's security model (SecretStr, CSRF, SSRF, input clamping, atomic writes, Docker hardening, loguru redaction)
  3. A user clicking "New Issue" sees structured bug report and feature request forms (not blank textarea), with blank issues disabled and a Discussions contact link
  4. A contributor opening a PR sees a template with a CI checklist
  5. The repo is discoverable via GitHub topics and has Discussions enabled with General and Q&A categories
**Plans**: 2 plans

Plans:
- [ ] 45-01-PLAN.md — Community health files (CONTRIBUTING.md, SECURITY.md, LICENSE)
- [ ] 45-02-PLAN.md — GitHub templates (issue forms, PR template) and repo metadata (topics, Discussions)

### Phase 46: Test Hardening -- Infrastructure Failures
**Goal**: The test suite verifies Triggarr handles network and API failures gracefully without crashing or corrupting state
**Depends on**: Phase 45
**Requirements**: CONN-01, CONN-02, CONN-03, CONN-04, API-01, API-02, API-03, API-04
**Success Criteria** (what must be TRUE):
  1. Tests pass that simulate unreachable instances (connection refused, timeout, DNS failure, SSL errors) and verify the app logs errors and continues operating
  2. Tests pass that simulate an instance going down mid-search-cycle and verify the cycle completes without crashing
  3. Tests pass that simulate malformed JSON, unexpected HTTP status codes (401, 403, 500, 502), and truncated paginated responses from *arr instances
  4. Tests pass that verify Sonarr v3/v4 API version mismatch edge cases are handled without exceptions
**Plans**: 2 plans

Plans:
- [ ] 46-01-PLAN.md — Connection failure tests (DNS, SSL, timeout, mid-cycle all-fail, unreachable_since)
- [ ] 46-02-PLAN.md — Bad API response tests (malformed JSON, 403/502 status, Sonarr version edge cases, truncated pagination)

### Phase 47: Test Hardening -- State & Search Edge Cases
**Goal**: The test suite verifies Triggarr recovers from corrupt persistent state and handles search logic boundary conditions correctly
**Depends on**: Phase 45
**Requirements**: STATE-01, STATE-02, STATE-03, STATE-04, SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05
**Success Criteria** (what must be TRUE):
  1. Tests pass that verify recovery from broken TOML config (syntax errors, missing required fields, wrong types) without data loss
  2. Tests pass that verify recovery from corrupt SQLite (locked DB, schema mismatch) and invalid JSON state files (truncated, wrong structure)
  3. Tests pass that verify config migration handles unexpected starting states (partial migration, unknown fields, missing sections)
  4. Tests pass that verify correct search behavior with empty queues, all items filtered by tags, nonexistent configured tags, batch size exceeding available items, and cursor position exceeding queue length
**Plans**: TBD

Plans:
- [ ] 47-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 45 → 46 → 47

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 45. Community Health & Repo Metadata | v2.4 | 2/2 | Complete | 2026-04-09 |
| 46. Test Hardening -- Infrastructure Failures | v2.4 | 0/2 | Not started | - |
| 47. Test Hardening -- State & Search Edge Cases | v2.4 | 0/? | Not started | - |
