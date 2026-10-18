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
- 🔨 v2.12 Search Correctness & Trustworthy Feedback -- Phases 77-81 (in progress)

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

### 🔨 v2.12 Search Correctness & Trustworthy Feedback (Phases 77-81, in progress)

**Milestone Goal:** Make Triggarr search exactly what the user configured and report honestly what happened — no silent scope widening, no misattributed stats, no false "success" status — and close the two highest-stakes log-exposure gaps.

**Source of truth:** `docs/superpowers/specs/2026-10-08-search-correctness-design.md` (locked grading definitions §3, per-phase behavior + acceptance §4).

- [x] **Phase 77: Secret & Reset-Token Log Hygiene** - Reset token never reaches the in-app log viewer; *arr HTTP errors always logged with secrets redacted (completed 2026-10-08)
- [x] **Phase 78: Honest Cycle Outcomes** - Each instance's last cycle grades Success/Partial/Failed/Nothing-needed, shown honestly on the dashboard (completed 2026-10-09)
- [x] **Phase 79: Tag-Scoped Searches Stay in Scope** - An unresolved tag skips its queue instead of searching everything (completed 2026-10-18)
- [x] **Phase 80: Cycle Robustness & Sonarr Season Dedup** - A malformed record can't wedge a cycle; a Sonarr season gets at most one dispatch per cycle (completed 2026-10-18)
- [ ] **Phase 81: Correct Sonarr Grab Attribution** - Grabs credit the matching series+season exactly once, ever, with an honest stats cutover note

### Milestone status — reviewed 2026-10-18

Status below is reconciled against plan SUMMARY files, phase VERIFICATION/HUMAN-UAT records, REQUIREMENTS.md, merged PRs and the deployed build. Phases 77–79 merged via PR #26 (merge commit `c914cbc`, 2026-10-18), published as `ghcr.io/thejuran/triggarr:main` and deployed to production (running `c914cbc` verified). The connection-pill polling loop found by the walkthrough (pre-existing since Phase 60) was fixed in PR #27 (`d41b484`). The version badge still reads v2.11.0; the bump belongs to the v2.12 release process, and `c914cbc` identifies the tested build until then.

| Phase | Implemented / completed | Remaining | Status |
|-------|-------------------------|-----------|--------|
| 77 — Secret & Reset-Token Log Hygiene | All 5 plans; token-free viewer messages, sanitized connection errors, SecretStr client boundary. Automated verification recorded. | None. Live UAT passed 2026-10-18 on the sandbox (same `c914cbc` image). | Complete — merged and deployed; UAT complete (live) |
| 78 — Honest Cycle Outcomes | All 5 plans; cycle grades, timestamps, persistence warnings, dashboard details, grade-driven failure counter. Automated verification recorded. | None open. 78-1 passed live. 78-2: green/red/gray grades and the post-first-cycle label passed live; amber Partial and the legacy-label states verified only by local fixture (owner-accepted). | Complete — merged and deployed; UAT partial (live + fixture) |
| 79 — Tag-Scoped Searches Stay in Scope | All 4 plans; shared tag-scope resolution, reworded badge/unknown-count card behavior, refresh never-widen + end-to-end proof, and the R-07/hard-max shared-helper cleanup. Automated verification recorded (12/12 must-haves, no gaps). | None open. 79-1 and 79-2 passed live on the sandbox (badge auto-clear also confirmed the PR #26 tag-cache refetch); 79-3 upstream tag-fetch failure has automated-test coverage only. | Complete — merged and deployed; UAT partial (79-3 automated only) |
| 80 — Cycle Robustness & Sonarr Season Dedup | All 5 plans; per-item malformed-record skips with per-queue card rows, per-grab date hardening, honest "unknown" Sonarr version, tag-autocomplete fallback, cross-queue Sonarr season dedup. Automated verification recorded (4/4 truths). | None open. Card UAT passed 2026-10-18 on a local build with a fake Sonarr (Partial + Failed); legacy single-count record covered by tests only. | Complete — on branch `cycle-robustness`, not yet merged or deployed |
| 81 — Correct Sonarr Grab Attribution + v5 Compatibility | Sandbox setup/connectivity reported in the external runbook; no completed implementation plans recorded. | Attribution ownership/migration, cutover note, version reporting, regression tests, live v4/v5 compatibility matrix. | Not started — planning required |

**Counts:** 3/5 phases complete, merged and deployed; 14/14 currently defined plans have summaries (Phases 80/81 still need plans, so 14/14 is not a milestone completion percentage). REQUIREMENTS.md marks 13/28 requirements complete. Public v2.12.0 release remains pending Phases 80–81, their verification, and the release version bump.

**Walkthrough evidence (2026-10-18):** `.planning/walkthroughs/20261018-023529-pending-live-human-checks/` (local, git-ignored). No searches ran during it, so it is not evidence of Sonarr v5 search compatibility; SONARRV5-01..03 remain open.

**Next work:** plan/execute Phase 80; plan/execute Phase 81 and its compatibility task (including the live v4/v5 search matrix); bump the version in the v2.12 release.

### Phase 77: Secret & Reset-Token Log Hygiene

**Goal**: Close the two highest-stakes log-exposure gaps — the reset token stays out of the web-facing log viewer, and *arr API keys never leak through HTTP-error log lines.
**Depends on**: Nothing (independent; sequenced first for risk reduction)
**Requirements**: LOGSEC-01, LOGSEC-02, LOGSEC-03
**Success Criteria** (what must be TRUE):

  1. The reset token is absent from the in-app log viewer buffer and from `/partials/log-viewer` output, while still readable from the stderr log (`docker logs`).
  2. The viewer stays redacted after the token is consumed, expires, or is replaced by a newly-issued token.
  3. Any *arr HTTP error whose request URL contains an API key — including Sonarr's `detect_api_version` on legacy installs — is logged through the existing sanitizer (`_sanitize_exc`), key redacted.

**Plans:** 5/5 plans complete
Plans:
**Wave 1**

- [x] 77-01-PLAN.md — create_buffer_sink: bound viewer_message divergence + one-line redacted exception summary, no tracebacks in viewer (wave 1)
- [x] 77-02-PLAN.md — relocate _sanitize_exc to clients.base; sanitize Sonarr detect_api_version warning (wave 1)
- [x] 77-03-PLAN.md — load_state corrupt-file warning names the reason without contents (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 77-04-PLAN.md — reset-token mint: viewer gets D-01 sentence only, stderr keeps token; lifecycle tests (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 77-05-PLAN.md — strict SecretStr api_key for *arr clients + auth_api_key_set truthiness; migrate 64 test sites (wave 3)

### Phase 78: Honest Cycle Outcomes

**Goal**: Every instance's last cycle is graded honestly — Success, Partial, Failed, or Nothing needed searching — and the dashboard, timestamps, and failure counter all reflect that grade instead of a blanket "last success" stamp.
**Depends on**: Nothing (independent of Phase 77; sequenced to define the grading model Phases 79 and 80 build on)
**Requirements**: OUTCOME-01, OUTCOME-02, OUTCOME-03, OUTCOME-04, OUTCOME-05, OUTCOME-06
**Success Criteria** (what must be TRUE):

  1. Each instance's last cycle is graded Success / Partial / Failed / Nothing needed searching per spec §3.1, correctly for Radarr, Sonarr, and Lidarr, including when a queue is inactive or the cycle found nothing eligible.
  2. The dashboard card reads "<Grade> · N accepted, M failed · <relative time>" — amber for Partial, red for Failed — with an expandable, sanitized failure-reason detail (no secrets, no stack traces).
  3. "Last successful search" updates only when ≥1 command was accepted; "last checked" updates on every cycle finish including Failed; connection health remains a separate signal from the grade.
  4. The consecutive-failure counter increments only on Failed and resets on Success, Partial, or Nothing needed searching.
  5. A pre-upgrade `last_success` timestamp displays as "Last success (legacy)" until the instance's first new cycle completes, and an accepted command whose history write fails still counts as accepted, still updates "last successful search," and surfaces a separate persistence warning instead of being retried.

**Plans:** 5/5 plans complete
**UI hint**: yes
Plans:
**Wave 1**

- [x] 78-01-PLAN.md — outcome model: grade_cycle (§3.1), CycleTally with Phase 79/80 hooks, cycle_view, LastCycleRecord + legacy-safe load (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 78-02-PLAN.md — engine helpers (_search_and_record split command/insert, _finalize_cycle) + Radarr honest grading, OUTCOME-06 persistence path (wave 2)
- [x] 78-04-PLAN.md — dashboard card: grade line/colors, Last checked staleness, legacy + Not run yet, unreachable grade, grouped detail panel kept open across refresh, persistence warning (wave 2)

**Wave 3** *(blocked on 78-02)*

- [x] 78-03-PLAN.md — Sonarr + Lidarr honest grading; refresh helpers proven untouched (wave 3)

**Wave 4** *(blocked on 78-02 and 78-03)*

- [x] 78-05-PLAN.md — SAFETY-03 counter driven by grade for scheduled + Search Now; refresh-counts route boundary (wave 4)

### Phase 79: Tag-Scoped Searches Stay in Scope

**Goal**: A queue whose configured tag can't be resolved is skipped outright, never silently widened to search the whole library.
**Depends on**: Phase 78 (grading model — a skipped queue must be reflected in the cycle grade)
**Requirements**: TAGSCOPE-01, TAGSCOPE-02, TAGSCOPE-03, TAGSCOPE-04
**Success Criteria** (what must be TRUE):

  1. When a queue's tag can't be resolved (fetch failed or tag no longer exists), that queue issues zero searches while the other queue still runs if its own scope resolves — true for Radarr, Sonarr, and Lidarr.
  2. A persistent card warning names the skipped queue and the reason, and clears automatically once the tag resolves on a later cycle.
  3. A skipped queue counts as unevaluated for grading; paired with an empty other queue, the cycle grades Failed, never "Nothing needed searching."
  4. README/docs no longer describe the old search-everything fallback.

**Plans**: 4 plans

Plans:
**Wave 1**

- [x] 79-01-PLAN.md — Shared `_resolve_tag_scope` helper; Radarr/Sonarr/Lidarr cycles skip unresolved-tag queues, grade them unevaluated, keep last good counts (wave 1)
- [x] 79-02-PLAN.md — Card badge names skipped queue + reason; README fail-open claim retired with docs regression test (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 79-03-PLAN.md — Refresh counts never widen (active or inactive queue); end-to-end engine-to-card proof (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 79-04-PLAN.md — Fold copied R-07 both-inactive and hard-max cap blocks into shared helpers, behavior-preserving (wave 3)

### Phase 80: Cycle Robustness & Sonarr Season Dedup

**Goal**: One malformed *arr record can no longer wedge a whole cycle, and a Sonarr season eligible for both the missing and upgrade queues gets searched at most once per cycle.
**Depends on**: Phase 78 (grading model — malformed-record counts and persistence warnings feed into the cycle grade)
**Requirements**: ROBUST-01, ROBUST-02, ROBUST-03, ROBUST-04, DEDUP-01, DEDUP-02
**Success Criteria** (what must be TRUE):

  1. A malformed *arr record (null nested series/artist, malformed or naive grab date, non-string version) is skipped and logged; the cycle completes and its state persists.
  2. A failure in any history insert — on the failure path or the success path — is logged and never aborts the batch; an accepted command whose history insert fails still counts as accepted, still updates "last successful search," and shows the persistence warning instead of being retried.
  3. Tag autocomplete returns its documented empty-`<datalist>` fallback instead of a 500 when the upstream response is malformed.
  4. Within one Sonarr cycle, each (series, season) receives at most one engine dispatch across the missing and upgrade queues — claimed on attempt even if that command fails — while the upgrade batch still fills to its limit from other eligible seasons and the excluded season's position in the upgrade searched-log is unchanged.

**Plans:** 5/5 plans complete
Plans:
**Wave 1**

- [x] 80-01-PLAN.md — per-queue malformed tally (record_malformed(queue)), additive malformed_by_queue record field, D-07 card rows with legacy fallback (wave 1)
- [x] 80-02-PLAN.md — correlation: skip malformed/naive grab dates per grab; tracking job no longer aborts (wave 1)
- [x] 80-03-PLAN.md — detect_api_version reports "unknown" when uncertain (visible change from v3 fallback); tag_autocomplete empty fallback on ValueError (wave 1)
- [x] 80-04-PLAN.md — Sonarr cross-queue season dedup: prioritize_batch exclude_keys + claim set + D-14 log (wave 1)

**Wave 2** *(blocked on 80-01 and 80-04)*

- [x] 80-05-PLAN.md — engine per-item malformed guards (Sonarr series, Lidarr tag-scoped artist), missing-side backstops, _resolve_tag_scope ValueError, ROBUST-02 three-app regression parity (wave 2)

### Phase 81: Correct Sonarr Grab Attribution

**Goal**: A Sonarr grab credits exactly the search that earned it — matching series and season, counted at most once ever — with effectiveness stats that honestly disclose the correction.
**Depends on**: Attribution work is independent of Phases 79/80; final v4/v5 compatibility verification follows Phase 80. Carries the only DB migration and config addition.
**Requirements**: ATTR-01, ATTR-02, ATTR-03, ATTR-04, ATTR-05, ATTR-06, SONARRV5-01, SONARRV5-02, SONARRV5-03
**Success Criteria** (what must be TRUE):

  1. A Sonarr grab credits a search only when both series and season match, and each grab is credited at most once, ever, keyed by (app, stable per-instance ID, grab ID) — holding across colliding grab IDs from different instances, instance renames, process restarts, and history pruning.
  2. Each instance has a permanent Triggarr-assigned ID generated at creation, backfilled for existing instances on first load, and unchanged by renames.
  3. Search↔grab ownership commits in the same transaction as the outcome/stat update; later tracking checks accumulate a search's previously-owned grabs and count distinct episodes.
  4. Pre-cutover pending searches keep their existing rows and counters, are excluded from corrected attribution and from the active pending cap, and display as "Legacy — tracking discontinued."
  5. Sonarr effectiveness stats show the attribution-corrected cutover note and label totals that include pre-cutover data as "Lifetime — includes historical estimates"; the cutover is recorded exactly once, only after the migration succeeds.

  6. Sonarr v5 is reported as v5 (not v3), with safe malformed-version handling and no automatic API-route switch.
  7. An isolated v4/v5 smoke matrix covers connection, tags, missing/cutoff pagination, counts, season commands, and grab tracking, recording exact builds and results. Alternate-order, season-pack, and multi-season attribution regression cases use Sonarr-returned identities and count distinct episodes correctly.

**Plans**: TBD. Include one bounded **Verify Sonarr v5 compatibility** task per the design spec's Phase 81 addendum (2026-10-12). Keep current v3 routes and API-key authentication unless testing demonstrates an incompatibility; fix only affected existing flows. No production NAS upgrade, new Sonarr feature integration, or blanket v5 API migration. Live compatibility must be verified before claiming support; unavailable scenarios remain documented as unverified and the task stays open.

### Phase 81 live test environment and remaining checks

**Environment reference:** [Sonarr v5 sandbox runbook](/Users/julianamacbook/Cowork/mediaserver/SANDBOX-sonarr-v5.md). The runbook reports isolation checks and connectivity passed on 2026-10-12 against Sonarr v5.0.0.2569. This is historical setup evidence, not proof of scheduled-search or attribution compatibility; recheck the current environment before testing.

- Separate compose project: `/volume1/docker/v5test`; sandbox data: `/volume1/data/v5test`; dedicated Triggarr config: `/volume1/docker/v5test/triggarr`.
- Triggarr UI: `http://maguffynas:8494` (host 8494 → container 8484). Sonarr address from Triggarr: `http://sonarr-v5:8989`; LAN: `http://maguffynas:8990`. Use the fresh v5 API key without placing it in reports. `sonarr:8989` is production and is not the v5 test target.
- The runbook reports authenticated connectivity to both API versions. Scheduled searching, pagination, deduplication, and corrected attribution remain unverified. SONARRV5-01..03 stay pending.
- Deploy and identify a Triggarr build containing the Phase 80/81 changes. A mutable `:main` tag or the update-check banner does not establish which code is running.
- Start with Triggarr disabled and test series unmonitored. After setup/configuration changes, run the runbook's isolation verification with the appropriate `SEARCHES=off/on` mode and Deluge destination check; require `ALL ISOLATION CHECKS PASSED` and `DELUGE DESTINATIONS PASSED` before controlled search testing. Deliberately monitor only the sandbox cases needed for the test, then restore the disabled/unmonitored baseline afterward.
- Keep download category `tv-v5test`, sandbox download/move destinations, Remove Completed/Failed off, and test-only webhook/config targets. Shared iplayarr remains search-only; do not deploy or modify production services for this Triggarr task.
- WUD can auto-update all test containers. Capture exact application versions, Triggarr commit/build identity, full image digests, and container start times before and after each run. Repeat any run interrupted by an update or restart. Record digests as evidence; do not change the runbook's tag-based deployment to digest pins.
- Run the existing Phase 81 smoke matrix: connection, tags, missing/cutoff pagination, library counts, one controlled season dispatch, scheduled cycle, and repeated tracking checks; include alternate-order and season/multi-season-pack attribution cases. Use an isolated v4 instance for mutating v4 comparison tests; no isolated v4 endpoint is currently documented, so that part remains pending until provisioned.
- Store sanitized results under `/volume1/docker/v5test/results/` and `/Users/julianamacbook/Cowork/mediaserver/v5test-results/`, linking the evidence from Phase 81 verification. Missing scenarios stay explicitly unverified; API reachability alone must never be reported as full v5 support.

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
| 80. Cycle Robustness & Sonarr Season Dedup | 5/5 | Complete | 2026-10-18 |
| 81. Correct Sonarr Grab Attribution + v5 Compatibility | 0/TBD | Not started; sandbox connectivity reported | - |

## Backlog

**Triage approved 2026-10-17.** Finish v2.12 first. Retained items below are unscheduled follow-ups, not a commitment to another broad hardening milestone. Retired means **won't do under current scope**; do not repeatedly carry it forward or create plans without the stated reopening evidence. Original 999.x findings came from the 2026-06-26 deep review; recheck current code before implementation.

### 999.4 — Keep: password hashing off the event loop

Move synchronous bcrypt work in async authentication/setup/reset paths off the shared event loop, preserving authentication and rate-limit behavior. Verify unrelated requests and scheduled work can progress during hashing. No auth redesign or new settings.

### 999.9 — Keep: state and config consistency

- Make instance removal write validated replacement settings before swapping live state; a failed write must preserve settings, scheduler jobs and clients.
- Guard non-object state JSON (`[]`, `42`, `null`) so loading follows the documented recovery path instead of raising on dictionary access.
- Require focused failure-path regression tests.

### 999.10 — Narrow: evidence-backed auth boundary review

Review cookie-authenticated mutations with missing Origin/Referer, auth-exempt path matching, trusted-proxy/rate-limit behavior, and cookie/CSP behavior in supported deployments. Reproduce each alleged defect and record its actual prerequisites before choosing a fix; older proposed remedies are not approved requirements. Keep API-key/Basic clients and supported reverse-proxy setups working. Do not automatically add auth modes, cookie settings, a CSP rewrite, or treat an HX-Request header alone as proof of CSRF protection.

### 999.13 — Narrow: startup/shutdown resource cleanup

Keep concrete failure-path work: ensure database/client resources opened during partial startup are closed, and failure closing one client does not prevent closing remaining resources or the DB. Verify with injected initialization/close failures. Fix cursor lifetime defects locally if confirmed. Drop the blanket async-I/O/offloading rewrite; reopen performance work only for measured stalls. This does not retire 999.4's known CPU-blocking auth work.

### POST-retry semantics — Keep: ambiguous command acceptance

An automatic POST retry after a response timeout can duplicate a command already accepted upstream. Establish explicit retry behavior for search commands, distinguish confirmed acceptance from unknown delivery, and test response-loss scenarios. Keep safe read retries; do not broaden into a generic retry framework. This remains outside v2.12's one-engine-dispatch guarantee.

### Maintenance rules — no standalone implementation phase

- **999.8 — atomic writes:** Retire consolidation of all writers/public APIs as a project. Preserve atomic replacement, appropriate secret-file permissions, cleanup and durability. Fix only demonstrated defects with focused tests. The current TOML writer uses `mkstemp`; omitting a later `chmod` does not by itself demonstrate world-readable output.
- **999.11 — URL validation compatibility:** When a future validation change rejects a previously supported configuration, ship a migration/recovery path and regression test with that change. Do not prebuild a generic migration system or weaken existing validation. No standalone task until such a change is proposed.

### Retired — won't do under current scope

| Item | Decision / reason | Reopen only when |
|------|-------------------|------------------|
| 999.7 — client registry and module reorganization | Retired as standalone architecture work; three supported apps do not justify a new abstraction project. | A new integration or demonstrated dispatch inconsistency requires it. |
| 999.12 — changelog renderer rewrite | Retired; all three text insertion points are escaped, the security boundary is documented, and 19 changelog tests passed during the 2026-10-17 review. Preserve those protections. | A reproducible escaping defect or new untrusted content path appears. |
| PERF-01/02 — per-endpoint timeout/page-size overrides | Retired; global settings already cover normal operation. | An observed endpoint-specific problem cannot be solved with existing settings. |
| PERF-03 — state streaming/compression | Retired; no measured state-size or memory problem. | Profiling demonstrates a material bottleneck. |
| SCALE-01 — more than five instances per app | Retired; no current deployment requirement. | An actual deployment needs more than five instances of one app. |
| SCALE-02 — archival/PostgreSQL | Retired; SQLite and bounded history fit a single-process utility. | A concrete retention or scale requirement exceeds SQLite/current retention. |
| AUDIT-01 — config audit log | Retired; limited value in the current single-user model. | A real operational accountability requirement emerges. |
| OBS-01 — scheduler dashboard | Retired; existing cards and cycle outcomes cover core operational feedback. | A recurring diagnostic need cannot be answered by existing status/history/logs. |
| UI-01/02/03 — pixel-exact verification | Retired as pixel-exact requirements; retain ordinary login, setup and security-settings usability checks. | A functional usability or accessibility regression is observed. |
| Unused `--color-triggarr-primaryDark` token | Retired as tracked work; optional cleanup while editing that stylesheet. | It causes an actual styling defect. |

### Promoted / historical — removed from active backlog

| Original item | Owning milestone/phase | Status |
|---------------|------------------------|--------|
| 999.1 — password recovery | v2.10, Phases 72–73; [archive](milestones/v2.10-ROADMAP.md) | Shipped; no duplicate backlog task. |
| 999.2 — count-only refresh | v2.10, Phase 74; [archive](milestones/v2.10-ROADMAP.md) | Shipped; no duplicate backlog task. |
| 999.3 — reset-token viewer exposure | v2.12, [Phase 77](#phase-77-secret--reset-token-log-hygiene) | Implementation complete; milestone NAS UAT remains pending. |
| 999.6 — log secret-redaction gaps | v2.12, [Phase 77](#phase-77-secret--reset-token-log-hygiene) | Implementation complete; no duplicate backlog task. |
| 999.5 — malformed upstream records | v2.12, [Phase 80](#phase-80-cycle-robustness--sonarr-season-dedup) | Pending in Phase 80, not retired or complete. |

### Other small follow-ups

Existing screenshot/CI maintenance in `TODO.md` is unchanged by this triage. The older v2.9 follow-up (URL-validation duplication, Retry-Connection button behavior, bug-report version options) remains unscheduled and must be revalidated before work; it is not part of a new hardening program.
