# Roadmap: Triggarr

## Overview

Triggarr is a single-process automation daemon that cycles through Radarr, Sonarr, and Lidarr's wanted/cutoff-unmet lists on a configurable schedule, with closed-loop download tracking. Security invariants (no API key in any HTTP response) are established from day one and never relaxed.

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
- ✅ v2.7 Dashboard Scale Refresh -- Phases 60-63 (shipped 2026-04-18) -- [archive](milestones/v2.7-ROADMAP.md)
- ✅ v2.8 Hardening & Observability -- Phases 64-67 (shipped 2026-06-01) -- [archive](milestones/v2.8-ROADMAP.md)
- 🚧 v2.9 Launch-Hardening / Sibling Consistency -- Phases 68-71 (in progress, started 2026-06-02)

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

<details>
<summary>v2.7 Dashboard Scale Refresh (Phases 60-63) -- SHIPPED 2026-04-18</summary>

- [x] Phase 60: Foundation & Header (3/3 plans) -- completed 2026-04-16
- [x] Phase 61: Stat Cards & App Cards (2/2 plans) -- completed 2026-04-16
- [x] Phase 62: Activity Rail & Log Viewer (2/2 plans) -- completed 2026-04-17
- [x] Phase 63: Header Favicon Icon (1/1 plan) -- completed 2026-04-17

</details>

<details>
<summary>v2.8 Hardening & Observability (Phases 64-67) -- SHIPPED 2026-06-01</summary>

- [x] Phase 64: Data Safety & Config Integrity (4/4 plans) -- completed 2026-05-26
- [x] Phase 65: Scheduler Hardening & Resilience (4/4 plans) -- completed 2026-05-26
- [x] Phase 66: Security Hardening (5/5 plans) -- completed 2026-05-26
- [x] Phase 67: Observability & CSRF Test Coverage (3/3 plans) -- completed 2026-05-31

Full phase details: [milestones/v2.8-ROADMAP.md](milestones/v2.8-ROADMAP.md)

</details>

## v2.9 Launch-Hardening / Sibling Consistency (Phases 68-71) -- IN PROGRESS

**Milestone goal:** Make Triggarr's public-facing surface — both the code a skeptical engineer reads and the presentation a visitor sees — hold up to the same scrutiny as its sibling project SeedSyncarr, so cross-referencing viewers see one coherent, serious author across both repos. Two largely-disjoint tracks (Python code vs. Markdown/docs/repo-metadata), each opening with its own hostile/discovery take that GATES the subsequent fix work. Spec: `docs/superpowers/specs/2026-06-02-launch-hardening-design.md`. Work isolated on a `launch-hardening` branch; merge + tag **v2.9.0** handled by the orchestrator at milestone-end (`release_intent=true`), not as a roadmap phase.

### Phases (summary)

- [ ] **Phase 68: Code-track hostile-reader discovery** -- Hostile "this is on Reddit" code sweep (ruff whole-tree + Shield SAST/secrets/dep-audit + git-history secrets scan + entry-point skim) → one triaged findings artifact classifying each finding fold-in vs parked; gates Phase 69's fix scope.
- [ ] **Phase 69: Code-track hardening** -- Close the curated known items (`.orchestrator.json` gitignore audit-and-close + SAFETY-03 manual/scheduled failure-counter unification with a covering test) plus every fold-in finding from Phase 68.
- [ ] **Phase 70: Presentation discovery** -- Cynical-reader teardown + codex adversarial pass against existing README/docs + same-author cross-repo consistency audit vs SeedSyncarr → critique artifacts that gate Phase 71's rewrite.
- [ ] **Phase 71: Presentation rewrite** -- Rewrite README / SECURITY.md / community-health files / repo-metadata text / release notes + in-app changelog driven by Phase 70's critique; fresh Playwright screenshots captured at the milestone-end NAS walkthrough.

### Phase Details

### Phase 68: Code-track hostile-reader discovery
**Goal**: A skeptical-engineer pass over the whole code surface (and full git history) has run and produced a single triaged findings artifact that decides what the code-hardening phase must fix
**Depends on**: Nothing (first phase of milestone)
**Requirements**: CDISC-01, CDISC-02, CDISC-03, CDISC-04, CDISC-05
**Success Criteria** (what must be TRUE):
  1. `ruff check triggarr/ tests/` has been run whole-tree with launch framing and its result is recorded in the findings artifact (CDISC-01)
  2. Shield (Semgrep SAST + gitleaks working-tree secrets + dependency audit) has been run and its findings are recorded in the artifact (CDISC-02)
  3. A gitleaks scan over the full git history has run; any secret found in past commits is recorded as highest-priority (and if none, that clean result is stated) (CDISC-03)
  4. The six highest-traffic entry-point files (`web/routes.py`, `search/scheduler.py`, `config.py`, `db.py`, `auth.py`, `startup.py`) have been skimmed with hostile framing and the notes are captured (CDISC-04)
  5. A single triaged findings artifact exists in which every finding is classified fold-in (fix this milestone) or parked (with written rationale) (CDISC-05)
**Plans**: 1 plan
- [ ] 68-01-PLAN.md — Hostile-reader sweep (ruff whole-tree + Shield SAST/secrets/dep-audit + full-history gitleaks + entry-point skim) captured and triaged into 68-FINDINGS.md

### Phase 69: Code-track hardening
**Goal**: The curated known code holes are closed and every fold-in finding from discovery is fixed, so a skeptical repo browser finds no sloppy-tooling tell and no correctness asymmetry between manual and scheduled searches
**Depends on**: Phase 68 (the triaged findings artifact defines the fold-in fix scope)
**Requirements**: CHARD-01, CHARD-02, CHARD-03, CHARD-04
**Success Criteria** (what must be TRUE):
  1. `.orchestrator.json` is git-ignored and a `git status --ignored` / `git ls-files` re-scan confirms no untracked transient or accidentally-tracked editor/tooling artifact remains (audit-and-close, no already-ignored entries re-added) (CHARD-01)
  2. Manual search via `/search-now/{app}/{instance}` and scheduled cycles share one failure-counting path, so a manual-search failure increments and resets the consecutive-failure counter identically to scheduled cycles, and the `# TODO` at `scheduler.py:~325` is gone (CHARD-02)
  3. A test proves manual-search failure increment/reset, and no existing scheduler failure-counter test is deleted or skipped (CHARD-03)
  4. Every discovery finding marked fold-in (from CDISC-05) is fixed; every parked finding is recorded with rationale in the findings artifact (CHARD-04)
**Plans**: TBD

### Phase 70: Presentation discovery
**Goal**: A hostile reading of Triggarr's presentation has run — cynical-reader teardown, codex adversarial pass against the existing README/docs, and a same-author consistency audit against SeedSyncarr — producing critique artifacts that drive (and gate) the rewrite
**Depends on**: Phase 69 (sequenced after the code track for a clean single-threaded milestone; disjoint files mean no hard file coupling)
**Requirements**: PDISC-01, PDISC-02, PDISC-03
**Success Criteria** (what must be TRUE):
  1. A framed cynical-reader ("r/selfhosted commenter") teardown of Triggarr's positioning, credibility, and first impression exists as a written artifact (PDISC-01)
  2. A codex adversarial pass against the existing README + docs has run and its findings — technical-claims accuracy, broken/incomplete install/quickstart, unsupported assertions — are captured (PDISC-02)
  3. A same-author cross-repo consistency audit against SeedSyncarr (README structure, security-posture framing, badge style, "what this is" one-liner) is recorded as a list of divergences to reconcile (PDISC-03)
**Plans**: TBD
**UI hint**: yes

### Phase 71: Presentation rewrite
**Goal**: Triggarr's public presentation has been rebuilt to survive the teardown and reconciled with SeedSyncarr, so genuine quality is evident within 30 seconds and the two repos read as one coherent author
**Depends on**: Phase 70 (the critique + consistency-audit artifacts drive the rewrite)
**Requirements**: PREW-01, PREW-02, PREW-03, PREW-04, PREW-05, PREW-06, PREW-07
**Success Criteria** (what must be TRUE):
  1. The README is rewritten to survive the teardown — instantly-clear one-liner, current screenshots above the fold, honest feature list, install/quickstart verified accurate against current behavior, security posture stated as a selling point (PREW-01)
  2. Fresh, real screenshots (dashboard, search history, settings) are captured via Playwright during the NAS walkthrough against the deployed branch build with representative data and no exposed API keys/hostnames/credentials, and README image refs + alt text are updated to match (PREW-02; verification completes at the milestone-end walkthrough deploy)
  3. SECURITY.md is reconciled with the v2.8/v2.8.1 hardening (CSP nonces, session-secret rotation on password change, `apikey=` rejection, Basic-auth control-char validation) and reads as an honest, mature threat-model + reporting policy (PREW-03)
  4. Community-health files (CONTRIBUTING.md, issue/PR templates, LICENSE) are confirmed present and accurate, with any gaps fixed (PREW-04); GitHub repo-metadata text (About, topics/tags, homepage) is drafted as copy-paste text for manual application (PREW-05)
  5. A clean v2.9.0 release-notes entry is written and the in-app changelog is updated to match (PREW-06); Triggarr's quality signals (one-liner, section ordering, security framing) are reconciled against SeedSyncarr so the two repos read as one coherent author (PREW-07)
**Plans**: TBD
**UI hint**: yes

### Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 68. Code-track hostile-reader discovery | 0/1 | Not started | - |
| 69. Code-track hardening | 0/? | Not started | - |
| 70. Presentation discovery | 0/? | Not started | - |
| 71. Presentation rewrite | 0/? | Not started | - |
