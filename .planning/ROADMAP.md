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
- 🚧 v2.10 Recovery, Counts & Config Parity -- Phases 72-75 (in progress)

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

### 🚧 v2.10 Recovery, Counts & Config Parity (Phases 72-75) -- IN PROGRESS

- [x] **Phase 72: Password Reset Backend & Token Lifecycle** (0/3 plans) - Filesystem-token reset endpoints, in-memory single-use token, session rotation, rate-limit, middleware exemption (completed 2026-06-03)
- [ ] **Phase 73: Password Reset UI** - "Forgot password?" affordance on the login page plus the styled request/confirm reset pages
- [ ] **Phase 74: Count-Only Refresh** - Extract the fetch+count+filter helper and expose a per-card "Refresh counts" button + `POST /api/refresh-counts` that updates counts without searching or advancing the cursor
- [ ] **Phase 75: Drain-Timeout Config Parity & Deferred-Record Correction** - `shutdown_drain_timeout` config field + settings input with env-override precedence, and the DEBT-06/07/08/03 deferred-record correction

## Phase Details

### Phase 72: Password Reset Backend & Token Lifecycle
**Goal**: A locked-out operator with host access can mint a reset token and use it to set a new password — entirely through HTTP, without hand-editing `triggarr.toml` — while a remote attacker hitting the same endpoints gains nothing.
**Depends on**: Nothing (first phase of milestone; builds on shipped v2.6 auth)
**Requirements**: RCOV-02, RCOV-03, RCOV-04, RCOV-05, RCOV-06
**Success Criteria** (what must be TRUE):
  1. Requesting a reset writes a CSPRNG token to the application log AND to a `0600` `<config_dir>/reset-token.txt`, and the token value never appears in any HTTP response body (request returns only a neutral "check your logs/volume" confirmation).
  2. Submitting a valid, unexpired token plus a matching new password sets a new bcrypt hash, rotates `session_secret` (so any cookie signed with the old secret is rejected), deletes the token file, and auto-logs-in the user with a fresh cookie that lands on the dashboard.
  3. A token is rejected (generic "invalid or expired" error, no state change) when it is wrong, expired past its 15-minute TTL, already used once, or superseded by a newer mint.
  4. Hitting `/reset/request` or `/reset/confirm` while logged out succeeds (routes are exempt from the auth middleware) yet no other authenticated route becomes reachable, and both endpoints throttle rapid repeat calls.
**Plans**: 3 plans
- [x] 72-01-PLAN.md — Foundation: RED test_reset.py (20 tests), generate_reset_token(), /reset middleware exemption, rate-limit constants, app.state init, minimal reset.html
- [x] 72-02-PLAN.md — Reset-request path: reset_request_page (GET) + reset_request_post (POST mint) + atomic 0600 token-file write + 60s rate-limit
- [x] 72-03-PLAN.md — Reset-confirm path: reset_confirm_post (apply) mirroring change_password — in-lock token validation, session rotation, auto-login, token-file delete, 5s rate-limit

### Phase 73: Password Reset UI
**Goal**: A locked-out user discovers and completes the recovery flow from the browser, with reset pages that look and behave like the existing login/setup pages.
**Depends on**: Phase 72
**Requirements**: RCOV-01
**Success Criteria** (what must be TRUE):
  1. The login page shows a "Forgot password?" link only when auth is already configured (`not needs_setup`); during first-run setup the link is absent.
  2. Following that link reaches a reset-request page styled to match `login.html`/`setup.html`, and submitting it shows the neutral confirmation telling the operator where to read the token.
  3. The reset-confirm page accepts the token + new password + confirmation, surfaces field-level errors (mismatch, empty, over the 72-byte bcrypt limit) inline, and on success transitions the user to the logged-in dashboard.
**Plans**: TBD
**UI hint**: yes

### Phase 74: Count-Only Refresh
**Goal**: After a bulk quality-profile change, a user can see true post-change missing/cutoff/eligible counts on demand without launching a search wave or advancing the cursor.
**Depends on**: Nothing (disjoint from Tracks A and C; sequenced after the auth track for a clean single-threaded milestone)
**Requirements**: CNT-01, CNT-02, CNT-03, CNT-04, CNT-05
**Success Criteria** (what must be TRUE):
  1. Clicking "Refresh counts" on an app card updates that card's missing/cutoff/eligible counts and connection health in place, without triggering any indexer search.
  2. A count-only refresh never advances the search cursor (structural — slicing stays only in the cycle function), so the next scheduled cycle resumes exactly where it left off.
  3. A count-only refresh does not stamp `last_run`/`last_success` and does not touch the SAFETY-03 scheduled-search failure counter; a fetch failure flips the card to disconnected without escalating the scheduler.
  4. `POST /api/refresh-counts/{app}/{instance}` works for scripts and mirrors `search_now` (same `search_lock`, rate-limit, app/instance validation, and app-card partial response) minus the search, while existing scheduled-cycle search behavior is unchanged.
**Plans**: TBD
**UI hint**: yes

### Phase 75: Drain-Timeout Config Parity & Deferred-Record Correction
**Goal**: The settings UI reaches full config-knob parity — the graceful-shutdown drain timeout is editable in the UI with documented env-override precedence — and the stale deferred record is corrected to match shipped reality.
**Depends on**: Nothing (disjoint from Tracks A and B; sequenced last as the smallest rider)
**Requirements**: CFG-03, CFG-04, DOCS-01
**Success Criteria** (what must be TRUE):
  1. A user can set the graceful-shutdown drain timeout via a settings-UI numeric input bounded `>= 1.0`, and the value persists through the settings POST handler and reloads on the next page view.
  2. The configured drain timeout is used as the default at shutdown, `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` overrides it when set, and the `>= 1.0` clamp applies to both sources — with the precedence documented in the field help text.
  3. Project documentation and the deferred record state correctly that DEBT-07 (request timeout), DEBT-08 (page size), and DEBT-03 (search-history cap) were already shipped, and DEBT-06 (drain timeout) is now shipped.
**Plans**: TBD
**UI hint**: yes

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 72. Password Reset Backend & Token Lifecycle | 3/3 | Complete   | 2026-06-03 |
| 73. Password Reset UI | 0/? | Not started | - |
| 74. Count-Only Refresh | 0/? | Not started | - |
| 75. Drain-Timeout Config Parity & Deferred-Record Correction | 0/? | Not started | - |

## Backlog

### Phase 999.1: UI-based password recovery (BACKLOG — promoted to v2.10 Track A)

**Status:** Promoted into v2.10 as Phases 72-73 (Track A). Retained here for historical context.
**Goal:** [Captured for future planning] Self-service password reset flow in the Triggarr web UI so a locked-out user never has to hand-edit `triggarr.toml`. Context: a user got locked out after logging out and corrupted auth by typing a plaintext value into the bcrypt `password_hash` field (silent failure — bcrypt compare against a non-hash always rejects). Current recovery requires clearing `username`/`password_hash` in the TOML and re-running `/setup`. Single-user app, so likely a recovery mechanism gated on host/filesystem access (e.g. a one-time reset token written to the config volume or logs) rather than email-based reset.
**Requirements:** RCOV-01..06 (v2.10)
**Plans:** 0 plans

Plans:
- [ ] Promoted to v2.10 Phases 72-73

### Phase 999.2: Count-only / dry-run refresh without searching (BACKLOG — promoted to v2.10 Track B)

**Status:** Promoted into v2.10 as Phase 74 (Track B). Retained here for historical context.
**Goal:** [Captured for future planning] Surface accurate missing & cutoff-unmet counts on demand WITHOUT triggering any indexer searches or advancing the search cursor. Context: today counting and searching are a single inseparable pass (`engine.py` fetches the full missing/cutoff lists — the source of accurate counts — then immediately slices a batch off the cursor and searches it). After a bulk quality-profile change a user wants to see the true post-change counts without launching a search wave. The expensive part (querying *arr for the lists) already exists; this is the existing cycle with the `search_movies` loop short-circuited. Design notes: (a) must NOT advance the cursor (nothing was searched, else next real cycle silently skips items); (b) prefer a thin shared fetch helper used by both the real cycle and the count-only path over a `count_only` flag tangling the hot path; (c) surface as a per-instance "Refresh counts" button and/or API endpoint.
**Requirements:** CNT-01..05 (v2.10)
**Plans:** 0 plans

Plans:
- [ ] Promoted to v2.10 Phase 74
