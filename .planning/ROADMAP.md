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
- [ ] **Phase 79: Tag-Scoped Searches Stay in Scope** - An unresolved tag skips its queue instead of searching everything
- [ ] **Phase 80: Cycle Robustness & Sonarr Season Dedup** - A malformed record can't wedge a cycle; a Sonarr season gets at most one dispatch per cycle
- [ ] **Phase 81: Correct Sonarr Grab Attribution** - Grabs credit the matching series+season exactly once, ever, with an honest stats cutover note

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

**Plans**: TBD

### Phase 80: Cycle Robustness & Sonarr Season Dedup

**Goal**: One malformed *arr record can no longer wedge a whole cycle, and a Sonarr season eligible for both the missing and upgrade queues gets searched at most once per cycle.
**Depends on**: Phase 78 (grading model — malformed-record counts and persistence warnings feed into the cycle grade)
**Requirements**: ROBUST-01, ROBUST-02, ROBUST-03, ROBUST-04, DEDUP-01, DEDUP-02
**Success Criteria** (what must be TRUE):

  1. A malformed *arr record (null nested series/artist, malformed or naive grab date, non-string version) is skipped and logged; the cycle completes and its state persists.
  2. A failure in any history insert — on the failure path or the success path — is logged and never aborts the batch; an accepted command whose history insert fails still counts as accepted, still updates "last successful search," and shows the persistence warning instead of being retried.
  3. Tag autocomplete returns its documented empty-`<datalist>` fallback instead of a 500 when the upstream response is malformed.
  4. Within one Sonarr cycle, each (series, season) receives at most one engine dispatch across the missing and upgrade queues — claimed on attempt even if that command fails — while the upgrade batch still fills to its limit from other eligible seasons and the excluded season's position in the upgrade searched-log is unchanged.

**Plans**: TBD

### Phase 81: Correct Sonarr Grab Attribution

**Goal**: A Sonarr grab credits exactly the search that earned it — matching series and season, counted at most once ever — with effectiveness stats that honestly disclose the correction.
**Depends on**: Nothing (independent of Phases 79/80 per spec §5; carries the only DB migration and config addition)
**Requirements**: ATTR-01, ATTR-02, ATTR-03, ATTR-04, ATTR-05, ATTR-06
**Success Criteria** (what must be TRUE):

  1. A Sonarr grab credits a search only when both series and season match, and each grab is credited at most once, ever, keyed by (app, stable per-instance ID, grab ID) — holding across colliding grab IDs from different instances, instance renames, process restarts, and history pruning.
  2. Each instance has a permanent Triggarr-assigned ID generated at creation, backfilled for existing instances on first load, and unchanged by renames.
  3. Search↔grab ownership commits in the same transaction as the outcome/stat update; later tracking checks accumulate a search's previously-owned grabs and count distinct episodes.
  4. Pre-cutover pending searches keep their existing rows and counters, are excluded from corrected attribution and from the active pending cap, and display as "Legacy — tracking discontinued."
  5. Sonarr effectiveness stats show the attribution-corrected cutover note and label totals that include pre-cutover data as "Lifetime — includes historical estimates"; the cutover is recorded exactly once, only after the migration succeeds.

**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 72. Password Reset Backend & Token Lifecycle | 3/3 | Complete   | 2026-06-03 |
| 73. Password Reset UI | 1/1 | Complete   | 2026-06-03 |
| 74. Count-Only Refresh | 3/3 | Complete   | 2026-06-04 |
| 75. Drain-Timeout Config Parity & Deferred-Record Correction | 4/4 | Complete   | 2026-06-04 |
| 76. Never-Searched-First Search Queue | 3/3 | Complete    | 2026-06-04 |
| 77. Secret & Reset-Token Log Hygiene | 5/5 | Complete    | 2026-10-08 |
| 78. Honest Cycle Outcomes | 5/5 | Complete   | 2026-10-09 |
| 79. Tag-Scoped Searches Stay in Scope | 0/TBD | Not started | - |
| 80. Cycle Robustness & Sonarr Season Dedup | 0/TBD | Not started | - |
| 81. Correct Sonarr Grab Attribution | 0/TBD | Not started | - |

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

### Phase 999.3: Reset token must not reach the in-UI log viewer (BACKLOG — promoted to v2.12 Phase 77)

**Status:** Promoted into v2.12 as Phase 77. Retained here for historical context.
**Source:** `/deep-review --all` 2026-06-26 (security, highest real-world risk).
**Goal:** [Captured for future planning] The password-reset token is logged at WARNING (`routes.py:~1840`), and `buffer_sink` (logging.py) captures WARNING messages into `log_buffer`, which `GET /partials/log-viewer` serves to the browser. The token is intentionally excluded from `collect_secrets`/redaction so operators can read it from `docker logs` — but that also means an authenticated user (or anyone, when auth is set to Disabled) can read it from the web log viewer and complete a password reset to take over the account. The in-code comment says "the token MUST NOT appear in any HTTP response," which this contradicts. PROJECT.md authorizes the *docker-logs* channel, not the *web-viewer* exposure. Fix direction: redact the active reset token from `buffer_sink` (add it to the live redaction set while a token is outstanding), or log the token only to the stderr sink and never to the buffer sink.
**Requirements:** LOGSEC-01..02 (v2.12)
**Plans:** 0 plans

Plans:

- [x] Promoted to v2.12 Phase 77
 (completed 2026-10-08)
### Phase 999.4: Run bcrypt off the event loop (BACKLOG)

**Source:** `/deep-review --all` 2026-06-26 (framework-fastapi, async-blocking).
**Goal:** [Captured for future planning] `hash_password` and `verify_password` (bcrypt, 12 rounds, ~200-500ms CPU) are called synchronously on the asyncio event loop, serializing every other concurrent request for the duration. Sites: `routes.py:~1292` (setup_post), `~1467` (login_post — the hot path every unauthenticated request hits), `~1550/~1560` (change_password), `~1954` (reset_confirm_post), and `middleware.py:~193` (AuthMiddleware Basic-auth path). Fix direction: wrap each call in `await asyncio.get_running_loop().run_in_executor(None, fn, ...)` (or `asyncio.to_thread`). Cheap fix, outsized impact under any concurrency.
**Requirements:** TBD
**Plans:** 0 plans

Plans:

- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.5: Harden *arr API-response handling so one bad record can't wedge a cycle (BACKLOG — promoted to v2.12 Phase 80)

**Status:** Promoted into v2.12 as Phase 80. Retained here for historical context.
**Source:** `/deep-review --all` 2026-06-26 (bugs/language-python, robustness — 3 agents independently flagged the cycle-wedge).
**Goal:** [Captured for future planning] Several paths let a single malformed/unexpected *arr API record abort a whole tracking-or-search cycle (state never persists, search cursor never advances → the instance is wedged every cycle until the bad record ages out). `_run_one_cycle`'s catch tuple is only `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error)`, so `AttributeError`/`KeyError`/`TypeError`/`ValueError` escape to APScheduler as "code bugs." Specific cases: (a) `engine.py:~699` — `run_*_cycle` doesn't guard the null-nested-`series`/`artist` filter/dedup/tag block that `refresh_*_counts` already guards with `except (AttributeError, KeyError, TypeError)`; mirror that guard. (b) `correlation.py:~117` — `_parse_iso` raises `ValueError` (or yields a naive datetime → `TypeError` on the tz-aware compare) on a malformed/naive grab date; validate `GrabEvent.date` at the boundary or skip-and-log per grab. (c) `sonarr.py:~42` — `detect_api_version` does `data["version"].startswith(...)` and a non-string version raises `AttributeError`/`TypeError` that aborts startup connection validation; coerce `str()` or widen the catch. (d) `engine.py:~489` (×6 sites) — the failure-path `insert_search_entry` is itself unguarded, so a double-fault (DB degraded when the recovery insert also fails) aborts the whole batch; wrap it in its own suppress+log. (e) `routes.py:~769` — `tag_autocomplete` catches only `(httpx.HTTPError, pydantic.ValidationError)` but `get_json_list` can raise plain `ValueError`/`json.JSONDecodeError`, yielding a 500 instead of the documented empty-`<datalist>` fallback; add `ValueError`.
**Requirements:** ROBUST-01..04 (v2.12)
**Plans:** 0 plans

Plans:

- [ ] Promoted to v2.12 Phase 80

### Phase 999.6: Close secret-redaction gaps across all log paths (BACKLOG — promoted to v2.12 Phase 77)

**Status:** Promoted into v2.12 as Phase 77. Retained here for historical context.
**Source:** `/deep-review --all` 2026-06-26 (compliance/security — SecretStr discipline per CLAUDE.md).
**Goal:** [Captured for future planning] A few paths can let a secret or its diagnostic context escape the redaction discipline. (a) `sonarr.py:~49` — `detect_api_version` logs `httpx.HTTPError` via `logger.warning(exc=exc)` WITHOUT `_sanitize_exc`; on legacy Sonarr installs the apikey rides in the request URL embedded in the exception, so it could land in logs and the web viewer. `_sanitize_exc` is applied consistently elsewhere; apply it here. (b) `logging.py` `buffer_sink` redacts only `record["message"]`, not the full formatted output, so secrets in exception *tracebacks* aren't redacted before reaching the web log viewer (mitigated today since tracebacks aren't in `record["message"]`, but latent). (c) `clients/base.py:~26` — `ArrClient.__init__` accepts `api_key: str` (plaintext) rather than `SecretStr`, so a repr/traceback/debug dump could expose it; accept `SecretStr` and `get_secret_value()` only at the header-construction site. (d) `routes.py:~451` — `bool(settings.auth.api_key.get_secret_value())` extracts the plaintext just for a bool check; use `bool(settings.auth.api_key)` (SecretStr is truthy when non-empty). (e) `state.py:~185` — `load_state` swallows the load exception logging only the path, not `exc`; add `exc=exc` so the failure is diagnosable.
**Requirements:** LOGSEC-03 (v2.12)
**Plans:** 0 plans

Plans:

- [ ] Promoted to v2.12 Phase 77

### Phase 999.7: Centralize the {radarr,sonarr,lidarr} client-dispatch registry (BACKLOG)

**Source:** `/deep-review --all` 2026-06-26 (architecture/impact, duplication — flagged in 3 chunks).
**Goal:** [Captured for future planning] The literal app-type→client-class mapping `{"radarr": RadarrClient, "sonarr": SonarrClient, "lidarr": LidarrClient}` is hand-written verbatim in `routes.py:~641`, `startup.py:~148`, and `scheduler.py:~468`, plus duplicated `cycle_fns` dicts in `scheduler.py` (`make_search_job` and `_run_one_cycle`). None is derived from `APP_TYPES`. Adding a fourth *arr requires editing every site; miss one and `routes.py:641` `KeyError`s at runtime mid-mutation (a 500 during a settings save) while the updated startup/scheduler boot fine. Fix direction: a single `CLIENT_CLASSES` registry beside `APP_TYPES` (resolving classes at call-time so existing test monkeypatches of `RadarrClient`/etc. still work), consumed by all three sites, plus a test asserting `set(CLIENT_CLASSES) == set(APP_TYPES)`. Also resolves the related `routes.py` reach into private `_run_one_cycle`/`_TAG_CACHE_TTL_SECONDS` (promote to public or extract a `search/cycle.py`).
**Requirements:** TBD
**Plans:** 0 plans

Plans:

- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.8: Consolidate the atomic-write ceremony + 0o600 chmod into one helper (BACKLOG)

**Source:** `/deep-review --all` 2026-06-26 (architecture, duplication).
**Goal:** [Captured for future planning] The full atomic write-then-rename sequence (mkstemp → write → flush → fsync → os.replace → parent-dir fsync → tiered OSError/cleanup) is implemented FOUR times with divergent cleanup/ownership bookkeeping: `config._atomic_toml_write`, `config.generate_default_config`, `state.save_state`, and the reset-token writer in `routes.py`. They're kept in sync only by hand and "matches config.py" comments. Separately, `routes.py` imports the PRIVATE `_atomic_toml_write` across the layer boundary at ~8 sites, and the `os.chmod(path, 0o600)` secret-protecting invariant is re-implemented at 6 of those call sites — one omission silently leaves the config world-readable with API keys in it. Fix direction: extract one `atomic_write(path, data|write_fn, *, mode=0o600)` primitive, and expose a public `config.save_settings(path, settings)` that does serialize + atomic-write + chmod 0o600 as one unit; replace all web-layer call sites with it.
**Requirements:** TBD
**Plans:** 0 plans

Plans:

- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.9: remove_instance write-then-swap + load_state non-dict guard (BACKLOG)

**Source:** `/deep-review --all` 2026-06-26 (bugs, state-mutation).
**Goal:** [Captured for future planning] Two in-memory-vs-disk consistency gaps. (a) `routes.py:~848` — `remove_instance` does `del instances[instance_name]` on the LIVE settings dict BEFORE the atomic disk write; if `_atomic_toml_write` raises (disk full/EACCES), in-memory settings has already lost the instance while disk still has it, and the scheduler/client/state teardown is skipped, orphaning a scheduler job and open httpx client. It's the lone outlier from the build-new-validated-then-swap pattern every other write handler uses (cf. `add_instance`); rebuild a new Settings, write first, swap only on success. (b) `state.py:~189` — `load_state` runs `json.load` (which accepts any valid JSON) then calls `data.get(...)`; a non-dict `state.json` (`[]`, `42`, `null`) raises `AttributeError` uncaught, defeating the documented reset-to-defaults safety net. Guard `isinstance(data, dict)`.
**Requirements:** TBD
**Plans:** 0 plans

Plans:

- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.10: Auth / CSRF / cookie hardening (BACKLOG)

**Source:** `/deep-review --all` 2026-06-26 (security/impact — several scored below the deep threshold but are real, lower-confidence/lower-blast-radius items worth a deliberate pass).
**Goal:** [Captured for future planning] A cluster of defense-in-depth gaps on the auth surface. (a) `middleware.py:~86` (`OriginCheckMiddleware`) — mutating requests are ALLOWED when both Origin and Referer are absent (the sole CSRF defense); a request crafted to omit both (e.g. `referrerPolicy=no-referrer`) passes, leaving only SameSite=Lax cookies, which don't cover non-top-level navigations. Consider a synchronizer token on sensitive forms or requiring `HX-Request` for htmx mutations. (b) `web/security.py:~15` — the session-cookie `Secure` flag is set only when `scheme=="https"`; deployed over plain HTTP (or with `TRUSTED_PROXY_IPS=*`, which is spoofable) the cookie is issued without `Secure`. Escalate the `TRUSTED_PROXY_IPS=*` warning to ERROR and/or add a `FORCE_SECURE_COOKIES` env for upstream-HTTPS deployments. (c) `middleware.py:~25` — `EXEMPT_PREFIXES` matches `/login`/`/setup` by bare `startswith` (unlike the hardened exact-or-`/reset/` predicate), so a future `/loginXYZ`/`/setup-wizard` route would silently bypass the auth gate; apply the same exact-or-trailing-slash predicate. (d) `routes.py:~1441` — the login (and reset-confirm) rate limiter keys on `request.client.host`; with `TRUSTED_PROXY_IPS=*` an attacker spoofs X-Forwarded-For per attempt to bypass the window — document/enforce the incompatibility. (e) `middleware.py:~54` — CSP `script-src 'self' 'nonce-…'` keeps `'self'`, so a same-origin script injection bypasses the nonce; add a nonce to the htmx `<script>` then drop `'self'`.
**Requirements:** TBD
**Plans:** 0 plans

Plans:

- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.11: validate_url_ssrf must not hard-fail startup on historical config (BACKLOG)

**Source:** `/deep-review --all` 2026-06-26 (impact, breaking-api).
**Goal:** [Captured for future planning] `InstanceConfig.validate_url_ssrf` (`models/config.py:~91`) runs unconditionally at config load and RAISES on failure. Because `Settings` loads `triggarr.toml` at startup, any future tightening of `BLOCKED_HOSTS`/`_BLOCKED_NETWORKS` in `web/validation.py` retroactively invalidates previously-accepted configs and aborts `Settings` construction — the daemon fails to start, and the very UI needed to fix the URL is behind the failed startup. Fix direction: treat the config-load blocklist as a frozen contract, or gate new rejections behind a migration path that warn-and-disables the offending instance rather than hard-failing the whole process. (Add a regression test loading a config with a now-blocked URL.)
**Requirements:** TBD
**Plans:** 0 plans

Plans:

- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.12: Harden changelog raw-HTML rendering (BACKLOG)

**Source:** `/deep-review --all` 2026-06-26 (security, XSS surface — restored from a scorer line-number false-drop).
**Goal:** [Captured for future planning] `changelog.py` `parse_changelog` builds raw HTML returned via `HTMLResponse` and injected into the DOM via htmx `innerHTML`, bypassing Jinja2 autoescape entirely. `html.escape()` on the three text-insertion points is the SOLE XSS defense — defensible today since `CHANGELOG.md` is a repo-controlled file, but the barrier is a single hand-maintained escape discipline (any future text insertion without `html.escape` becomes stored XSS, and a supply-chain-modified CHANGELOG.md would execute). Fix direction: render the changelog through a Jinja2 template with autoescape (wrap parsed fragments in `Markup`) instead of a hand-built `HTMLResponse`, or at minimum verify CSP nonce coverage on the swapped container and add a guard comment marking the escape calls as the security boundary.
**Requirements:** TBD
**Plans:** 0 plans

Plans:

- [ ] TBD (promote with /gsd:review-backlog when ready)

### Phase 999.13: Lifecycle & blocking-I/O correctness in the async paths (BACKLOG)

**Source:** `/deep-review --all` 2026-06-26 (language-python/framework-fastapi — resource handling & async-blocking).
**Goal:** [Captured for future planning] A set of lifecycle/blocking-I/O fixes in the scheduler/db async paths. (a) `scheduler.py:~455` — `aiosqlite.connect()` result is stored into `app.state.db` only at ~488; if any startup statement between (PRAGMA/init_db/migrate) raises, the lifespan `finally` calls `app.state.db.close()` before it's assigned → `AttributeError` and a leaked SQLite fd. Assign `app.state.db = db` immediately after connect (or guard the close with a None check). (b) `scheduler.py:~686` — shutdown closes HTTP clients in a bare loop then closes the DB; if any `client.close()` raises, `db.close()` is skipped, leaking the connection and skipping the WAL checkpoint. Wrap each client close in try/except (log+continue) and put `db.close()` in its own try/finally. (c) Blocking I/O on the event loop, not offloaded: `db.py:~103` `shutil.copy2` (migration backup) inside async `run_migrations`; `scheduler.py:~440` `load_state` in async lifespan; `routes.py:~1319` (×5) `load_settings` (TOML read+parse) in async handlers (or just assign the already-validated `new_settings` instead of re-reading from disk). Offload via `run_in_executor`/`asyncio.to_thread`. (d) `db.py:~159` — the `_migrate_v4` cursor isn't used as an `async with` context manager (unbounded cursor lifetime); align with the rest of the file.
**Requirements:** TBD
**Plans:** 0 plans

Plans:

- [ ] TBD (promote with /gsd:review-backlog when ready)
