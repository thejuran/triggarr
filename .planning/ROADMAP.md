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
- ✅ v2.9 Launch-Hardening / Sibling Consistency -- Phases 68-71 (shipped 2026-06-03) -- [archive](milestones/v2.9-ROADMAP.md)
- ✅ v2.10 Recovery, Counts & Config Parity -- Phases 72-75 (shipped 2026-06-04) -- [archive](milestones/v2.10-ROADMAP.md)
- ✅ v2.11 Never-Searched-First Search Queue Priority -- Phase 76 (shipped 2026-06-04) -- [archive](milestones/v2.11-ROADMAP.md)
- ✅ v2.12 Search Correctness & Trustworthy Feedback -- Phases 77-81 (shipped 2026-10-21) -- [archive](milestones/v2.12-ROADMAP.md)

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

<details>
<summary>✅ v2.9 Launch-Hardening / Sibling Consistency (Phases 68-71) -- SHIPPED 2026-06-03</summary>

- [x] Phase 68: Code-track hostile-reader discovery (1/1 plan) -- completed 2026-06-02
- [x] Phase 69: Code-track hardening (3/3 plans) -- completed 2026-06-02
- [x] Phase 70: Presentation discovery (1/1 plan) -- completed 2026-06-02
- [x] Phase 71: Presentation rewrite (6/6 plans) -- completed 2026-06-02

Full phase details: [milestones/v2.9-ROADMAP.md](milestones/v2.9-ROADMAP.md)

</details>

<details>
<summary>✅ v2.10 Recovery, Counts & Config Parity (Phases 72-75) -- SHIPPED 2026-06-04</summary>

- [x] Phase 72: Password Reset Backend & Token Lifecycle (3/3 plans) -- completed 2026-06-03
- [x] Phase 73: Password Reset UI (1/1 plan) -- completed 2026-06-03
- [x] Phase 74: Count-Only Refresh (3/3 plans) -- completed 2026-06-04
- [x] Phase 75: Drain-Timeout Config Parity & Deferred-Record Correction (4/4 plans) -- completed 2026-06-04

Full phase details: [milestones/v2.10-ROADMAP.md](milestones/v2.10-ROADMAP.md)

</details>

<details>
<summary>✅ v2.11 Never-Searched-First Search Queue Priority (Phase 76) -- SHIPPED 2026-06-04</summary>

- [x] Phase 76: Never-Searched-First Search Queue (3/3 plans) -- completed 2026-06-04

Replaced the integer-cursor walk with an ordered per-instance searched-log on `AppState` + a pure `prioritize_batch()` dispatcher (never-searched-first, top-up oldest-searched-first, mark-on-attempt, reset-per-pass, prune-to-eligible, commit-at-cycle-end); `_merge_defaults` strips legacy cursor keys on load; `slice_batch` removed. QUEUE-01..11.

Full phase details: [milestones/v2.11-ROADMAP.md](milestones/v2.11-ROADMAP.md)

</details>

<details>
<summary>✅ v2.12 Search Correctness & Trustworthy Feedback (Phases 77-81) -- SHIPPED 2026-10-21</summary>

- [x] Phase 77: Secret & Reset-Token Log Hygiene (5/5 plans) -- completed 2026-10-08
- [x] Phase 78: Honest Cycle Outcomes (5/5 plans) -- completed 2026-10-09
- [x] Phase 79: Tag-Scoped Searches Stay in Scope (4/4 plans) -- completed 2026-10-18
- [x] Phase 80: Cycle Robustness & Sonarr Season Dedup (5/5 plans) -- completed 2026-10-18
- [x] Phase 81: Correct Sonarr Grab Attribution + v5 Compatibility (14/14 plans) -- completed 2026-10-21

Search exactly what the user configured and report honestly what happened. Reset tokens and *arr secrets stay out of the in-app logs; each cycle is graded Success/Partial/Failed/Nothing needed; an unresolved tag skips its queue; one malformed record no longer wedges a cycle and a Sonarr season gets at most one dispatch per cycle; Sonarr grabs credit only the matching series+season, once, counting distinct episodes, with stable instance IDs and an honest stats cutover note; Sonarr v5 compatibility verified live on isolated v5/v4 sandboxes. Released as v2.12.0 (PRs #26-#30; tag on dbb38fa).

Full phase details: [milestones/v2.12-ROADMAP.md](milestones/v2.12-ROADMAP.md)

</details>

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 72. Password Reset Backend & Token Lifecycle | 3/3 | Complete   | 2026-06-03 |
| 73. Password Reset UI | 1/1 | Complete   | 2026-06-03 |
| 74. Count-Only Refresh | 3/3 | Complete   | 2026-06-04 |
| 75. Drain-Timeout Config Parity & Deferred-Record Correction | 4/4 | Complete   | 2026-06-04 |
| 76. Never-Searched-First Search Queue | 3/3 | Complete    | 2026-06-04 |
| 77. Secret & Reset-Token Log Hygiene | 5/5 | Complete | 2026-10-08 (merged/deployed 2026-10-18) |
| 78. Honest Cycle Outcomes | 5/5 | Complete (UAT partial: fixture for amber/legacy) | 2026-10-09 (merged/deployed 2026-10-18) |
| 79. Tag-Scoped Searches Stay in Scope | 4/4 | Complete (79-3 automated only) | 2026-10-18 |
| 80. Cycle Robustness & Sonarr Season Dedup | 5/5 | Complete (scheduled-cycle check passed 2026-10-21: 24 consecutive 180-min cycles, 0 failed, no duplicate season dispatch) | 2026-10-18 |
| 81. Correct Sonarr Grab Attribution + v5 Compatibility | 14/14 | Complete (multi-season pack and alternate series order unverified-live under D-12) | 2026-10-21 |

## Next milestone after v2.12: CI & Review Workflow

**Goal:** Make Triggarr the reference for meaningful CI, publication of the tested artifact, and BM-led review with an independent Codex pass and risk-based vibe-check recommendations.

- [ ] **CI reference baseline:** implement and verify the bounded shipped-image startup, browser regression, and release-version checks in [the CI plan](../docs/ci-reference-baseline-plan.md). Plan the remaining dependency, audit, maintenance, and permissions improvements from that plan with explicit scope and acceptance criteria.
- [ ] **BM + Codex review pairing:** implement [the review blueprint](../docs/bm-greptile-codex-blueprint.md), updating `CLAUDE.md` and supported BM configuration/instructions so every BM code review has an independent Codex pass on the review checkpoint. Demonstrate normal, quick-task, and revision paths; missing or stale review evidence remains incomplete.
- [ ] **Codex plan-checker routing (investigation):** evaluate the owner-preferred, narrowly scoped `agent.spawn` mod hook for `bm:bm-plan-checker` through model-gateway, retaining BM's original agent and checking loop. Runtime support on inspected Claude Code 2.1.281 and end-to-end routing are unverified. Follow [the recorded investigation and pilot checks](../docs/bm-greptile-codex-blueprint.md#deferred-investigation-codex-plan-checker-through-model-gateway); include the [blind original-Phase-81 comparison](../docs/bm-greptile-codex-blueprint.md#blind-comparison-original-phase-81-plans) with matched context, reproduction checks and a separate revision round. Recover and hash the original ignored plans first; no activation during v2.12.
- [ ] **Risk-based review depth:** BM recommends depth at each checkpoint and explicitly suggests vibe-check when risk is high, recording the owner's choice. Keep Greptile and exact-commit owner acceptance; do not build another orchestrator.
- [ ] **Reference verification:** demonstrate claimed CI failure gates and review handoffs, preserve exact-artifact publication, and record pilot results and reusable guidance for other repositories. Distinguish instruction-based review requirements from GitHub-enforced checks.

**Done when:** the selected CI baseline checks have positive and negative verification evidence; the actual BM controls demonstrate paired Codex review and high-risk vibe-check recommendations; review evidence matches the final commit; existing safeguards remain intact; publication and deployment evidence are recorded separately when applicable.

**Sequence:** immediately follows v2.12 closeout, before Reliability. Read both linked plans during milestone planning; assign release version and phase numbers then. This entry does not activate workflow changes during v2.12.

## Following milestone: Reliability

**Goal:** Keep scheduled searching and saved state correct through failed writes, ambiguous network responses, partial startup and shutdown.

- [ ] **State/config consistency (999.9):** write validated replacement settings before removing an instance from live state. Failed writes must preserve settings, jobs and clients. Recover safely from non-object state JSON (`[]`, `42`, `null`).
- [ ] **Resource lifecycle (999.13, narrowed):** close resources opened during failed startup; a client-close failure must not prevent other clients or the database from closing. Correct cursor lifetime issues locally if confirmed. No blanket I/O/offloading rewrite.
- [ ] **Search-command delivery (POST-retry semantics):** prevent blind retries from duplicating an already-accepted search after a response timeout. Distinguish confirmed acceptance from unknown delivery and retain safe read retries; no generic retry framework.

**Done when:** targeted write-failure, malformed-state, partial-startup, shutdown and response-loss regressions pass with the existing suite; an isolated built-image smoke test demonstrates restart/recovery behavior. Record residual delivery limitations explicitly rather than claiming exactly-once behavior without evidence.

**Sequence:** follows CI & Review Workflow. Check current implementation before planning each carried-forward fix. Release version and phase numbers are assigned during milestone planning; no implementation is started by this organization.

## Later milestone: Authentication Safety & Responsiveness

**Goal:** Keep authentication responsive and close demonstrated boundary defects without redesigning the authentication system.

- [ ] **Password hashing (999.4):** move synchronous bcrypt work off the shared event loop across async login/setup/password/reset and Basic-auth paths, preserving authentication and rate limiting. Verify other requests and scheduled work can progress during hashing.
- [ ] **Auth-boundary review (999.10, narrowed):** validate missing-Origin/Referer mutation handling, auth-exempt path matching, trusted-proxy/rate-limit behavior, and cookie/CSP behavior in supported deployments. Reproduce issues and establish prerequisites before choosing fixes; older proposals are not requirements.
- [ ] **Compatibility verification:** verify browser login/setup/reset/logout and existing API-key/Basic clients, plus supported reverse-proxy deployments, for the boundaries changed. No new auth modes or speculative security settings; HX-Request alone is not proof of CSRF protection.

**Done when:** demonstrated defects have focused regression tests, authentication remains compatible, bcrypt work no longer stalls unrelated async work, and relevant deployed browser checks pass. If review finds an active credential exposure or exploitable bypass, fix it promptly rather than waiting for this milestone.

**Sequence:** follows Reliability; release version and phase numbers assigned during planning.

## Backlog

### Phase 999.14: Deferred: Migrate the Sonarr client to the v5 API before v3 is retired (BACKLOG)

**Goal:** Keep Sonarr support working when Sonarr removes its `/api/v3` routes. Triggarr calls `/api/v3` with API-key auth today; Sonarr v5 still serves v3, and Phase 81 deliberately kept those routes (no blanket v5 migration in v2.12).
**Scope when promoted:** track Sonarr's v3 deprecation/removal timeline; migrate the existing flows (system status, tags, missing/cutoff pagination, series counts, SeasonSearch, grab-history tracking with episode identity — v5 uses `includeSubresources` instead of `includeSeries`/`includeEpisode`), select routes from the detected version, keep v4 support while needed, and re-run the live v4/v5 matrix. Background: Phase 81 research (v5 OpenAPI differences).
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /bm:review-backlog when ready)

## Planning boundaries and maintenance

Keep the existing single-process architecture, SQLite and the current product scope. Finish v2.12 and its outstanding verification before starting these milestones. Routine maintenance and change-time safeguards live in [maintenance](backlog/MAINTENANCE.md), including the separately approved-after-v2.12 workflow discussion.

[Earlier backlog and closed decisions](backlog/archive/2026-10-18/README.md) are preserved outside this active work list.
