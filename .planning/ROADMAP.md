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
- ✅ v2.13 CI & Review Workflow -- Phases 82-86 (shipped 2026-11-14) -- [archive](milestones/v2.13-ROADMAP.md)
- 🔨 v2.14 Reliability -- Phases 87-92 (in progress)

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

<details>
<summary>✅ v2.13 CI & Review Workflow (Phases 82-86) -- SHIPPED 2026-11-14</summary>

- [x] Phase 82: CI Tests What We Ship (9/9 plans) -- completed 2026-10-22
- [x] Phase 83: Paired BM + Codex Review & Risk-Based Depth (10/10 plans) -- completed 2026-10-23
- [x] Phase 84: Codex Plan-Checker Investigation (7/7 plans) -- completed 2026-10-26
- [x] Phase 85: Follow-on CI Improvements & Acceptance Usability (19/19 plans) -- completed 2026-10-28
- [x] Phase 85.1: Isolated Codex Review for Untrusted PRs (INSERTED) (10/10 plans) -- completed 2026-10-30 as an owner exception (live criterion 3 unmet)
- [x] Phase 86: Pilot & Reference Record (10/10 plans) -- completed 2026-11-14

CI now tests the exact image it publishes (startup, browser regressions, release-version identity) behind one required gate; every BM code review is paired with an independent exact-commit Codex pass, with review depth and vibe-check set by risk and a content-based classification for docs changes; dependency, image-scan, workflow-lint, coverage and publish-permission hardening; an acceptance register that is safe under concurrent PRs; a five-PR pilot, the owner's decision to end routine vibe-check (required at high risk only), and an adoption guide for other repositories. Not a versioned release: production stays on v2.12.0 until the next release is cut.

Full phase details: [milestones/v2.13-ROADMAP.md](milestones/v2.13-ROADMAP.md) · Audit: [milestones/v2.13-MILESTONE-AUDIT.md](milestones/v2.13-MILESTONE-AUDIT.md)

</details>

### 🔨 v2.14 Reliability (Phases 87-92, in progress)

**Goal:** Keep scheduled searching and saved state correct through failed writes, ambiguous network responses, partial startup and shutdown.

- [x] **Phase 87: Settings & State-File Safety** (merged 2026-11-16, PR #62) - A failed settings write during instance removal never corrupts live state, and a non-object state file recovers instead of crashing
- [x] **Phase 88: Bounded Upgrade Backups & Telemetry Regression** (merged 2026-11-17, PR #63) - Pre-upgrade backups stay capped through a crash loop, and a permanent test pins the telemetry-variable fix
- [x] **Phase 89: Startup & Shutdown Resource Cleanup** (merged 2026-11-19 UTC, PR #64) - A partial startup closes what it opened, and one failed client close never blocks the rest from closing
- [ ] **Phase 90: Removed-Instance Pending-Search Lifecycle** - A removed Sonarr instance's leftover pending searches get a defined "Instance removed" outcome, never credited to a reused name (8 plans written and checked 2026-11-18; ready to execute)
- [ ] **Phase 91: Search-Command Delivery Confidence** - A timed-out search command is never blindly resent, and an unconfirmed outcome is tracked honestly instead of silently passing or failing
- [ ] **Phase 92: Built-Image Recovery Demonstration** - CI proves on the real built image that state-file corruption and repeated failed upgrades both recover correctly

**Done when:** targeted write-failure, malformed-state, partial-startup, shutdown and response-loss regressions pass with the existing suite, and an isolated built-image smoke test demonstrates restart/recovery behavior. Residual delivery limitations are recorded explicitly; exactly-once behavior is not claimed without evidence.

### Phase 87: Settings & State-File Safety
**Goal**: Removing an instance can't corrupt live settings when the disk write fails, and a corrupted-but-valid state file recovers to defaults instead of crashing.
**Depends on**: Nothing (first phase of this milestone)
**Requirements**: CONSIST-01, CONSIST-02, CONSIST-03
**Success Criteria** (what must be TRUE):
  1. When removing an instance fails to save the settings file, the instance keeps its existing settings, schedule and live connection exactly as before the attempt.
  2. When that save fails, the user sees an error stating the instance was not removed, with no internal detail exposed.
  3. When the saved state file holds valid JSON that is not an object (`[]`, `42`, `null`), Triggarr starts with default state and logs a warning instead of crashing.
**Plans**: 3 plans in 2 waves

**Wave 1**
- [x] 87-01-PLAN.md — instance removal saves the settings file before changing anything live; fixed-wording failure response and a single log entry (CONSIST-01, CONSIST-02)
- [x] 87-03-PLAN.md — a state file whose top level is not an object starts with default state, logs a warning and is set aside as one copy (CONSIST-03)

**Wave 2** *(blocked on Wave 1: 87-01)*
- [x] 87-02-PLAN.md — the removal error shows on the instance row without a page reload; audit and follow-up records in the maintenance backlog (CONSIST-02)

### Phase 88: Bounded Upgrade Backups & Telemetry Regression
**Goal**: Pre-upgrade database backups stay bounded through a crash loop, and the telemetry environment variable can never again crash startup.
**Depends on**: Nothing (independent of Phase 87; sequenced second per research as equally small, isolated work)
**Requirements**: BKUP-01, BKUP-02, TELEM-01, TELEM-02
**Success Criteria** (what must be TRUE):
  1. After repeated failed upgrade attempts, only the original pre-upgrade backup plus at most the 3 most recent later backups remain.
  2. Pruning never removes the original backup or the one just written, orders backups by the timestamp in their names, and a pruning failure is logged without blocking startup.
  3. An automated test pins that Triggarr starts and serves requests with `FASTAPI_OTEL_AUTO_CONFIGURE` and an OTLP endpoint set in the environment.
  4. The documentation states plainly that telemetry export is unsupported and nothing is exported.
**Plans**: 2 plans in 2 waves

**Wave 1**
- [x] 88-01-PLAN.md — repeated failed upgrades keep the original backup plus the 3 most recent retry copies, chosen by the timestamp in the name; a pruning failure is logged as a warning and never blocks startup (BKUP-01, BKUP-02)

**Wave 2** *(blocked on Wave 1: 88-01)*
- [x] 88-02-PLAN.md — a permanent test pins that startup and /health survive the telemetry variables, and the README states telemetry export is unsupported (TELEM-01, TELEM-02)

### Phase 89: Startup & Shutdown Resource Cleanup
**Goal**: A startup that fails partway closes everything it already opened, and a shutdown where one connection fails to close still closes the rest.
**Depends on**: Nothing (self-contained; sequenced after Phases 87-88 so the reorder-don't-rebuild pattern is proven first)
**Requirements**: LIFE-01, LIFE-02, LIFE-03
**Success Criteria** (what must be TRUE):
  1. When startup fails partway through, Triggarr closes the database and every connection already opened, and the process exits promptly rather than hanging.
  2. When one *arr connection fails to close at shutdown, the remaining connections and the database still close, and the failure is logged sanitized.
  3. After a failed startup, the scheduler is not left running.
**Plans**: 2 plans in 2 waves

**Wave 1**
- [x] 89-01-PLAN.md — shared non-raising, 5s-capped close helpers; at shutdown one client's failed or hung close never stops the remaining clients or the database from closing, logged as one sanitized warning (LIFE-02)

**Wave 2** *(blocked on Wave 1: 89-01; same files)*
- [x] 89-02-PLAN.md — a startup that fails after the database opens closes the database and every client built so far, stops the scheduler only if it was started, logs one summary line and re-raises the original error; the aiosqlite worker thread is proven stopped (LIFE-01, LIFE-03)

### Phase 90: Removed-Instance Pending-Search Lifecycle
**Goal**: A removed Sonarr instance's leftover pending searches get a defined, visible end state, and a reused instance name never inherits them.
**Depends on**: Phase 87 (reuses the settings-write-ordering fix in the same instance-removal route)
**Requirements**: RMINST-01, RMINST-02, RMINST-03, RMINST-04
**Success Criteria** (what must be TRUE):
  1. When a Sonarr instance is removed, its still-pending searches get the final outcome "Instance removed," stay visible in History, and read as distinct from "Legacy."
  2. "Instance removed" searches no longer count toward the pending-search limit and are never checked or credited again.
  3. A new instance added under the same name never selects, displays as its own in-progress work, or receives credit for the removed instance's searches.
  4. Pending searches already orphaned by a removal before this release reach the same "Instance removed" outcome at the next upgrade or startup.
**Plans**: 8 plans in 8 waves (one plan per wave, run strictly in order in a single working tree)

**Wave 1**
- [x] 90-01-PLAN.md — one shared rule for which searches are pending, and "instance_removed" as a finished outcome left out of the pending limit, tracking and grab rate (RMINST-02)

**Wave 2** *(blocked on Wave 1: 90-01)*
- [x] 90-02-PLAN.md — database close-out of a removed instance's pending searches by its own stable ID, and the orphan check used at startup (also with zero instances configured), neither ever leaving a half-done write behind (RMINST-01, RMINST-04)

**Wave 3** *(blocked on Wave 2: 90-02)*
- [x] 90-03-PLAN.md — Radarr and Lidarr select pending searches by stable instance ID like Sonarr, so a reused name inherits nothing (RMINST-03, RMINST-02)

**Wave 4** *(blocked on Wave 3: 90-03)*
- [x] 90-04-PLAN.md — "Instance removed" badge, tooltip and filter option in History and the activity rail, kept apart from Legacy (RMINST-01, RMINST-03)

**Wave 5** *(blocked on Wave 4: 90-04)*
- [ ] 90-05-PLAN.md — removing an instance (Remove action or Save Settings) closes its pending searches after the settings write, without ever failing the removal or leaking a secret into the logs (RMINST-01, RMINST-02)

**Wave 6** *(blocked on Wave 5: 90-05)*
- [ ] 90-06-PLAN.md — every startup closes pending searches no configured instance owns, after the cutover and before the scheduler, sparing disabled and Legacy rows, also when no instance is configured (RMINST-04)

**Wave 7** *(blocked on Wave 6: 90-06)*
- [ ] 90-07-PLAN.md — a scheduled or manual search that was waiting to run when its instance was removed, or replaced under the same name, is turned away (RMINST-01, RMINST-02, RMINST-03)

**Wave 8** *(blocked on Wave 7: 90-07)*
- [ ] 90-08-PLAN.md — end-to-end lifecycle tests for Sonarr, Radarr and Lidarr, same-name stats verification, requirement and roadmap wording for all three apps, backlog records (RMINST-01, RMINST-02, RMINST-03, RMINST-04)

### Phase 91: Search-Command Delivery Confidence
**Goal**: A search command is retried only when it's actually safe, and a command whose outcome is unknown is tracked honestly instead of counted as success or failure.
**Depends on**: Nothing additional (self-contained; sequenced last among the fixes as the largest blast radius, per research)
**Requirements**: DELIV-01, DELIV-02, DELIV-03, DELIV-04, DELIV-05, DELIV-06, DELIV-07
**Success Criteria** (what must be TRUE):
  1. A search command whose request may have reached the *arr app (the response timed out or the connection dropped after sending) is never automatically resent; a command that provably never left Triggarr is still retried, and read requests keep their existing retry.
  2. A search command with unknown delivery is recorded as "unconfirmed" — distinct from accepted and failed — in the cycle result and in search history.
  3. Unconfirmed commands never grade a cycle Failed and never add to the consecutive-failure counter; a cycle containing any unconfirmed command grades Partial at worst.
  4. The instance card shows how many commands in the last cycle were unconfirmed.
  5. An item whose search command was unconfirmed counts as attempted for queue ordering, and the documentation states plainly that a duplicate search is made unlikely (not impossible) and that an unconfirmed command may or may not have run.
**Plans**: TBD

### Phase 92: Built-Image Recovery Demonstration
**Goal**: CI proves, on the real built image, that Triggarr actually recovers from a corrupted state file and that repeated failed upgrades don't pile up backups.
**Depends on**: Phases 87, 88, 89, 90, 91 (validates the real fixes; written last so it demonstrates behavior rather than anticipating it)
**Requirements**: SMOKE-01, SMOKE-02, SMOKE-03
**Success Criteria** (what must be TRUE):
  1. The built-image CI check restarts the container with a non-object state file in place and confirms it comes back healthy.
  2. The built-image CI check simulates repeated failed upgrade attempts and confirms a bounded number of backups remain, with the original still present.
  3. Each recovery demonstration injects a real fault and fails on a build that lacks the corresponding fix.
**Plans**: TBD

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
| 82. CI Tests What We Ship | 9/9 | Complete | 2026-10-22 |
| 83. Paired BM + Codex Review & Risk-Based Depth | 10/10 | Complete | 2026-10-23 |
| 84. Codex Plan-Checker Investigation | 6/7 (84-06 not performed) | Complete (comparison invalid: post-review input; adoption not recommended, owner override to adopt; activation pending as quick task) | 2026-10-26 |
| 85. Follow-on CI Improvements & Acceptance Usability | 19/19 | Complete (merged PR #36; Codex incomplete for size, owner-approved vibe-check fallback; UAT P5 at next release) | 2026-10-28 |
| 85.1. Isolated Codex Review for Untrusted PRs (INSERTED) | 10/10 | Complete as an owner exception (PR #48; live run on PR #52 INCOMPLETE: default Codex model is code-mode-only; vibe-check fallback kept) | 2026-10-30 |
| 86. Pilot & Reference Record | 10/10 | Complete (merged PR #59; PILOT-01..04 satisfied; routine vibe-check retired in favor of a high-risk-only trigger, FUT-03 not chosen) | 2026-11-14 |
| 87. Settings & State-File Safety | 3/3 | Complete (merged PR #62) | 2026-11-16 |
| 88. Bounded Upgrade Backups & Telemetry Regression | 2/2 | Complete (merged PR #63) | 2026-11-17 |
| 89. Startup & Shutdown Resource Cleanup | 2/2 | Executed; verifier 22/22; in review, PR #64 open | - |
| 90. Removed-Instance Pending-Search Lifecycle | 4/8 | In Progress|  |
| 91. Search-Command Delivery Confidence | TBD | Not started | - |
| 92. Built-Image Recovery Demonstration | TBD | Not started | - |

## Next milestone: Authentication Safety & Responsiveness

**Goal:** Keep authentication responsive and close demonstrated boundary defects without redesigning the authentication system.

- [ ] **Password hashing (999.4):** move synchronous bcrypt work off the shared event loop across async login/setup/password/reset and Basic-auth paths, preserving authentication and rate limiting. Verify other requests and scheduled work can progress during hashing.
- [ ] **Auth-boundary review (999.10, narrowed):** validate missing-Origin/Referer mutation handling, auth-exempt path matching, trusted-proxy/rate-limit behavior, and cookie/CSP behavior in supported deployments. Reproduce issues and establish prerequisites before choosing fixes; older proposals are not requirements.
- [ ] **Compatibility verification:** verify browser login/setup/reset/logout and existing API-key/Basic clients, plus supported reverse-proxy deployments, for the boundaries changed. No new auth modes or speculative security settings; HX-Request alone is not proof of CSRF protection.

**Done when:** demonstrated defects have focused regression tests, authentication remains compatible, bcrypt work no longer stalls unrelated async work, and relevant deployed browser checks pass. If review finds an active credential exposure or exploitable bypass, fix it promptly rather than waiting for this milestone.

**Sequence:** follows Reliability; release version and phase numbers assigned during planning.

## Following milestone: UI Redesign

**Goal:** Make every screen answer "is it working, and what's next?" at a glance. Do this by removing repeated and unexplained labels, making status and actions clearer, and making the app usable at phone width. Keep the current dark look, the htmx + Tailwind v4 stack and all existing behavior.

**Design reference:** [mockups in docs/design/ui-redesign](../docs/design/ui-redesign/README.md): a PNG and static HTML for each screen, listed by artboard name below. Editable source: the [Triggarr Redesign canvas](https://claude.ai/artifact/RWWVHSdV2TL51oU1EpwL8C) (claude.ai, private to the owner). Numbers are live values from 2026-10-21. `[N]` and `[YOUR VALUE]` mark values that weren't captured, and the "[Example title]" rows only show what the outcome tags look like.

- [ ] **Header and navigation:** Show the wordmark in full, with no version badge on top of it. Merge "v2.11.0" and "v2.11.1 available" into one update pill. Replace "Connection Stable" with "2 of 2 apps connected" and remove the duplicate connected/disconnected/pending row. Move Logout out of the page nav into a labelled icon button. Files: [base.html](../triggarr/templates/base.html), [connection_pill.html](../triggarr/templates/partials/connection_pill.html), [health_summary.html](../triggarr/templates/partials/health_summary.html). Artboard: [Dashboard](../docs/design/ui-redesign/desktop-dashboard.png). Done when: the header fits at 390 px and 1280 px with nothing overlapping, and connection status appears only once.
- [ ] **Dashboard stats and notices:** Replace the four "includes historical estimates" captions with one asterisk and one footnote. Hide Lidarr in the grab-rate breakdown when no Lidarr instance is configured. Remove the empty "Last sync" label, or give it a value. Show the attribution-correction text as a dismissible notice. Keep the Phase 81 disclosure meaning intact. Files: [stats_row.html](../triggarr/templates/partials/stats_row.html), [migration_banner.html](../triggarr/templates/partials/migration_banner.html), [dashboard.html](../triggarr/templates/dashboard.html). Done when: no label renders without a value, the disclosure is still visible until dismissed, and the existing stats tests pass.
- [ ] **Instance cards:** Show the last-run time once, in one line with the result and the next run. Show each queue as a progress bar with a plain label such as "Pass 19 · 68 of 112 eligible searched". Make "Search now" the primary button and "Refresh counts" secondary. Before relabelling, confirm in code what the second number means ("112" against a total of 729) and word the label to match. Files: [app_card.html](../triggarr/templates/partials/app_card.html), [cycle_grade.html](../triggarr/templates/partials/cycle_grade.html). Done when: the labels are confirmed against the code, and cycle grades and failure-reason expanders behave as before (see the "Card reasons label" item in [maintenance](backlog/MAINTENANCE.md)).
- [ ] **History list:** Add outcome tiles with counts that also work as filters. Give filter chips a visible selected state, add "Clear all", group rows by day, and add a date filter. Shorten "Legacy — tracking discontinued" to "Legacy" with a tooltip, and show Grabbed in green as the success tag. Files: [history.html](../triggarr/templates/history.html), [history_results.html](../triggarr/templates/partials/history_results.html), [routes.py `history_page` / `partial_history_results`](../triggarr/web/routes.py). Artboards: [History](../docs/design/ui-redesign/desktop-history.png), [History, phone](../docs/design/ui-redesign/phone-history.png). Done when: existing filter URLs and query parameters keep working, and the counts match the filtered results.
- [ ] **Consistent timestamps:** History showed 17:52 for a cycle that the log viewer showed at 13:52 (2026-10-21). That suggests History displays UTC and the log viewer local time. Confirm in [routes.py](../triggarr/web/routes.py) (timestamp formatting around lines 126 and 163), then pick one timezone for display and label it. If confirmed, this is a user-facing bug: consider moving it into [maintenance](backlog/MAINTENANCE.md) rather than waiting for this milestone. Done when: a regression test pins the display timezone, and the dashboard, History and logs agree.
- [ ] **Settings sections and one save:** Give Settings a section sidebar: General, Security, then Radarr, Sonarr and Lidarr under "Apps". Lidarr shows "Set up" when it has no instance. Show help text beside each field, and fold rarely used settings (request timeout, page size, max consecutive failures, shutdown drain timeout) under "Advanced". Replace the separate Save and "Save Settings" buttons with one save bar that appears on change (unsaved count, Discard, Save). Password change keeps its own action. Instance pages get instance tabs, a "Test connection" button that doesn't save, and Remove moved into a separate red-outlined box with a confirmation step. Files: [settings.html](../triggarr/templates/settings.html), [security_password.html](../triggarr/templates/partials/security_password.html), [security_apikey.html](../triggarr/templates/partials/security_apikey.html). Artboards: [Settings › General](../docs/design/ui-redesign/desktop-settings-general.png), [Settings › Security](../docs/design/ui-redesign/desktop-settings-security.png), [Settings › Radarr instance](../docs/design/ui-redesign/desktop-settings-radarr-instance.png). Done when: config is still validated before every write (atomic writes, TOML comments preserved), no API key appears in HTML, and an existing endpoint backs "Test connection" (or one is added under the SecretStr rules in CLAUDE.md).
- [ ] **Phone layout:** Add a slim top bar and a Dashboard / History / Settings bar at the bottom. Stats go into a 2×2 grid, instance cards stack with full-width action buttons, History rows become two-line cards with sideways-scrolling filters and "Load 50 more", and Settings shows grouped fields with the save bar fixed to the bottom. Artboards: [Dashboard, phone](../docs/design/ui-redesign/phone-dashboard.png), [History, phone](../docs/design/ui-redesign/phone-history.png), [Settings, phone](../docs/design/ui-redesign/phone-settings-general.png). Done when: no screen scrolls sideways at 390 px, and every touch target is at least 44 px.
- [ ] **Login page polish:** Use a darker green for the button and focus ring so the white text reads more easily. Use a real wordmark instead of small green text. Raise the contrast of "Forgot password?". File: [login.html](../triggarr/templates/login.html) (plus [setup.html](../triggarr/templates/setup.html) and [reset.html](../triggarr/templates/reset.html) for consistency). Done when: login, setup and reset still pass their existing tests and browser checks.
- [ ] **Accessibility and screenshots:** Body text and the small grey labels reach a 4.5:1 contrast ratio. Controls are real buttons and links with visible focus, and icon-only buttons have labels. Update [docs/screenshots](../docs/screenshots/) and the README images, and close the README-screenshot task in [TODO.md](../TODO.md). Done when: a contrast check of the new palette is recorded and the screenshots match the shipped UI.

**Done when:** every item above is complete with its own check. The full suite and ruff pass. A browser walkthrough at 1280 px and 390 px is recorded against the design canvas, and any intentional differences from the mockups are written down. Behavior, config format and API responses are unchanged, except for the timestamp fix if item 5 confirms it.

**Sequence:** follows Authentication Safety & Responsiveness unless the owner reorders it. Release version and phase numbers are assigned during milestone planning. This entry starts no implementation and doesn't change v2.12 scope.

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
