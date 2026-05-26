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
- 🔄 **v2.8 Hardening & Observability -- Phases 64-67 (in progress)**

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

### v2.8 Hardening & Observability (Phases 64-67)

- [x] **Phase 64: Data Safety & Config Integrity** - Enforce search history bounds (resolved + pending separately), harden atomic config writes, prove concurrent config save lock with AST-verified coverage, test corrupted TOML recovery (completed 2026-05-26)
- [ ] **Phase 65: Scheduler Hardening & Resilience** - Narrow scheduler exception handler to expected types, add consecutive-failure escalation, extend graceful shutdown timeout, test async client cleanup
- [ ] **Phase 66: Security Hardening** - Remove CSP unsafe-inline via nonce migration, reject apikey= in *arr URLs, harden Basic auth header decoding, validate session secret at startup
- [ ] **Phase 67: Observability & CSRF Test Coverage** - Surface last-successful-search per app on dashboard, cache tag lists with 1h TTL, add OriginCheckMiddleware test suite

## Phase Details

### Phase 64: Data Safety & Config Integrity
**Goal**: Config writes and database growth are safe under concurrent access and in error conditions
**Depends on**: Nothing (first phase of v2.8; all items touch persistence layer independently of scheduler/security)
**Requirements**: SAFETY-01, SAFETY-01b, SAFETY-04, SAFETY-05, TEST-02, TEST-03
**Success Criteria** (what must be TRUE):
  1. The SQLite search history table's **resolved rows** (`outcome != 'searched'`) never exceed `max_history_rows`; resolved rows over the limit are trimmed immediately after each insert without blocking the search cycle (SAFETY-01)
  1b. The SQLite search history table's **pending rows** (`outcome = 'searched'`) never exceed `2 × max_history_rows`; when the bound would be exceeded, new pending inserts are rejected (or oldest pending rows are evicted with a logged warning) so that a stalled tracker cannot grow the table unboundedly (SAFETY-01b — added per Codex adversarial review F1, 2026-05-25)
  2. A failed `os.replace()` during config save produces a logged OSError rather than silently swallowing the failure; a `FileNotFoundError` during temp file cleanup continues to be suppressed (SAFETY-04)
  3. Two simultaneous PUT requests to the config save endpoint cannot interleave — the second waits for the first to complete and the resulting config file reflects exactly one of the two saves atomically (SAFETY-05)
  4. Starting the application with a TOML file containing a syntax error or invalid UTF-8 produces a clear, actionable error message that includes the path of the backup file the user can restore from (TEST-02)
  5. The concurrent config save test passes (`pytest`) confirming the SAFETY-05 lock prevents interleaved writes (TEST-03)
  6. Every call to `_atomic_toml_write` in `triggarr/web/routes.py` is lexically dominated by `async with request.app.state.search_lock` — verified by an AST audit script run in CI, not by a line-distance grep (SAFETY-05 audit hardening — added per Codex adversarial review F3)
**Plans:** 4/4 plans complete
- [x] 64-01-PLAN.md — SAFETY-04: harden `_atomic_toml_write` OSError handling (log non-FNF cleanup errors + log `os.replace` failures with path)
- [x] 64-02-PLAN.md — TEST-02: friendly TOML-corruption handler in `ensure_config` (syntax error + invalid UTF-8 + backup-path hint)
- [x] 64-03-PLAN.md — SAFETY-05 + TEST-03: concurrent POST `/settings` test via `ASGITransport` + **AST audit script** verifying every `_atomic_toml_write` call is lexically dominated by `async with request.app.state.search_lock` (per Codex F3)
- [x] 64-04-PLAN.md — SAFETY-01 + SAFETY-01b: docstring on `insert_search_entry` + soak test for resolved-row cap (SAFETY-01) **plus** pending-row cap via `PendingCapExceeded` exception when pending count would exceed `2 × max_history_rows` (SAFETY-01b, per Codex F1)

### Phase 65: Scheduler Hardening & Resilience
**Goal**: Scheduler jobs fail safely, alert on repeated failures, and shut down without leaving in-flight work in an unknown state
**Depends on**: Phase 64 (config lock established; scheduler can safely read fresh config)
**Requirements**: SAFETY-02, SAFETY-03, RES-01, TEST-04
**Success Criteria** (what must be TRUE):
  1. A search cycle that throws an unexpected exception type (e.g., `RuntimeError`, `MemoryError`) is no longer silently caught; only `httpx.HTTPError`, `pydantic.ValidationError`, `aiosqlite.Error`, and `OSError` are handled — others propagate to the APScheduler error handler
  2. After N consecutive failures on a single job (default N=5, configurable), the log level escalates from WARNING to ERROR so the user can see the repeated failure without inspecting every individual line
  3. Graceful shutdown waits up to 60 seconds (extended from 35s) for the search lock to drain; if a cycle is still holding the lock when the timeout fires, the specific job identifier and elapsed runtime are logged before forced close
  4. The async client cleanup test confirms that calling `aclose()` on a client with in-flight requests does not hang and that any in-flight responses raise cleanly rather than leaving the event loop blocked
**Plans:** 3/4 plans executed
- [x] 65-01-PLAN.md — SAFETY-02: narrow scheduler exception handler to `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` + register APScheduler `EVENT_JOB_ERROR` listener so non-narrow-tuple exceptions become operator-visible (Wave 1)
- [x] 65-02-PLAN.md — SAFETY-03: add `general.max_consecutive_failures` config field (default 5, bounds 1..100) + per-(app,instance) failure counter on `app.state.search_failures` with WARNING→ERROR escalation at threshold (Wave 2)
- [ ] 65-03-PLAN.md — RES-01: extract `_SHUTDOWN_DRAIN_TIMEOUT = 60.0` module constant (extended from 35s) + track `app.state.search_lock_holder` inside the lock + log holder job_id + elapsed runtime on shutdown timeout (Wave 3)
- [x] 65-04-PLAN.md — TEST-04: pin httpx `AsyncClient.aclose()` behavior with in-flight requests (cancel-then-close pattern + documented RuntimeError-on-no-cancel pattern) — pure test work (Wave 1, parallel with 65-01)

### Phase 66: Security Hardening
**Goal**: The application's HTTP attack surface is narrowed: inline scripts are gone, credential-containing URLs are rejected at save time, and session and Basic auth handling are defensively validated
**Depends on**: Phase 64 (config save path is locked before adding URL validation there)
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04
**Success Criteria** (what must be TRUE):
  1. The CSP `script-src` directive no longer contains `'unsafe-inline'`; all inline `<script>` blocks in base and page templates are replaced with external static JS files or nonce-tagged script elements, verified by inspecting the `Content-Security-Policy` response header on any page
  2. Submitting a Radarr/Sonarr/Lidarr URL that contains an `apikey=` query parameter in the settings form is rejected with a clear validation error before the config file is written
  3. A Basic auth header whose decoded credentials contain null bytes or other control characters is rejected with a 401 and the failed decode attempt is logged at WARNING — it does not reach the password comparison step
  4. On startup, if the session secret is shorter than 32 characters, or if it was auto-generated and not yet persisted to the config file, a WARNING is logged naming the problem and the recommended remediation
**Plans**: TBD

### Phase 67: Observability & CSRF Test Coverage
**Goal**: Users can see at a glance whether searches are succeeding per app, tag resolution no longer adds a round-trip every cycle, and the CSRF middleware is verified against adversarial header scenarios
**Depends on**: Phase 65 (scheduler records last-successful-search timestamps; Phase 64 config lock is available for cache invalidation on instance config save)
**Requirements**: RES-02, RES-03, TEST-01
**Success Criteria** (what must be TRUE):
  1. The dashboard shows a "last successful search" timestamp for each enabled app type (Radarr, Sonarr, Lidarr); when the timestamp is more than 2× the configured interval in the past, it is visually flagged as stale (e.g., amber color or "stale" badge)
  2. Tag lists fetched from `*arr` instances are cached in `app.state` and reused for up to 1 hour; saving instance config in the settings UI immediately invalidates the cache for that instance so the next cycle fetches fresh tags
  3. The `OriginCheckMiddleware` test suite covers at minimum: missing Origin header, missing Referer header, both headers absent, scheme mismatch, and spoofed-host scenarios — all tests pass and none rely on internal middleware state
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 60. Foundation & Header | v2.7 | 3/3 | Complete | 2026-04-16 |
| 61. Stat Cards & App Cards | v2.7 | 2/2 | Complete | 2026-04-16 |
| 62. Activity Rail & Log Viewer | v2.7 | 2/2 | Complete | 2026-04-17 |
| 63. Header Favicon Icon | v2.7 | 1/1 | Complete | 2026-04-17 |
| 64. Data Safety & Config Integrity | v2.8 | 4/4 | Complete   | 2026-05-26 |
| 65. Scheduler Hardening & Resilience | v2.8 | 3/4 | In Progress|  |
| 66. Security Hardening | v2.8 | 0/? | Not started | - |
| 67. Observability & CSRF Test Coverage | v2.8 | 0/? | Not started | - |
