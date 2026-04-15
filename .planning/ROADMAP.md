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
- ✅ v2.4 Community Polish & Test Hardening -- Phases 45-47 (shipped 2026-04-09) -- [archive](milestones/v2.4-ROADMAP.md)
- ✅ v2.5 Dashboard UI Refresh -- Phases 48-53 (shipped 2026-04-13)
- 🚧 **v2.6 Built-In Authentication** -- Phases 54-58 (in progress)

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

### v2.6 Built-In Authentication (In Progress)

**Milestone Goal:** Add *arr-style built-in authentication -- secure by default with Forms/Basic/External/Disabled modes, first-run setup, API key, and signed session cookies.

- [x] **Phase 54: Auth Config & Helpers** - Pydantic AuthConfig model, bcrypt password hashing, itsdangerous cookie signing, API key generation (completed 2026-04-14)
- [x] **Phase 55: Auth Middleware & Health Endpoint** - Deny-all middleware with path whitelist, API key validation, unauthenticated /health, redirect vs 401 logic (completed 2026-04-15)
- [x] **Phase 56: First-Run Setup & Login** - Setup page with credential creation, login page with Forms/Basic modes, session cookie management, first-run redirect guard (completed 2026-04-15)
- [ ] **Phase 57: Settings Security & Nav Logout** - Settings security section for password/auth-mode/API-key management, nav bar logout, disabled-auth warning
- [ ] **Phase 58: Auth Test Suite** - Comprehensive tests for all auth paths, middleware enforcement, session lifecycle, and edge cases

## Phase Details

### Phase 54: Auth Config & Helpers
**Goal**: Auth primitives exist in the codebase -- config model, password hashing, cookie signing, and API key generation -- ready for the middleware and UI layers to consume
**Depends on**: Nothing (first phase of v2.6, foundation for all subsequent phases)
**Requirements**: SETUP-03 (API key generation), LOGIN-02 (cookie signing primitives), LOGIN-05 (disabled mode config)
**Plans:** 2/2 plans complete
Plans:
- [x] 54-01-PLAN.md -- AuthConfig model, dependencies, collect_secrets extension
- [x] 54-02-PLAN.md -- Auth helper functions (TDD: password hashing, cookie signing, token generation)
**Success Criteria** (what must be TRUE):
  1. triggarr.toml supports an `[auth]` section with fields for auth_method, username, password_hash, api_key, and session_secret, validated by an AuthConfig pydantic model
  2. A helper function accepts a plaintext password and returns a bcrypt hash, and a verify function confirms a plaintext password against a stored hash
  3. A helper function generates a cryptographically random API key string suitable for X-Api-Key authentication
  4. A helper function creates a signed session cookie value using itsdangerous with a configurable 30-day expiry, and a corresponding function validates/decodes it
  5. When auth_method is set to "disabled" in config, the AuthConfig model accepts it and the value persists through config save/load round-trips

### Phase 55: Auth Middleware & Health Endpoint
**Goal**: Every route in the application requires authentication by default, with correct handling for API keys, unauthenticated health checks, and browser vs API redirect behavior
**Depends on**: Phase 54 (consumes AuthConfig, cookie validation, API key check, password verify)
**Requirements**: MID-01, MID-02, MID-03, MID-04, LOGIN-03, LOGIN-04
**Success Criteria** (what must be TRUE):
  1. An unauthenticated browser request to any protected route (e.g., `/`, `/settings`, `/history`) receives a 302 redirect to `/login`
  2. An unauthenticated API request (Accept: application/json or X-Api-Key header present but invalid) to any protected route receives a 401 JSON response
  3. A request with a valid `X-Api-Key` header passes through the middleware and reaches the protected route
  4. `GET /health` returns `{"status": "ok"}` with 200 without any authentication
  5. When auth_method is "basic", the middleware returns a 401 with `WWW-Authenticate: Basic` header instead of redirecting to `/login`; when auth_method is "external", the middleware trusts the request as authenticated (reverse proxy delegation)
**Plans:** 2/2 plans complete
Plans:
- [x] 55-01-PLAN.md -- AuthMiddleware TDD (deny-all dispatch with D-10 check order, all auth modes)
- [x] 55-02-PLAN.md -- Health endpoint + middleware registration wiring

### Phase 56: First-Run Setup & Login
**Goal**: Users launching Triggarr for the first time are guided through credential creation, and returning users can log in via the Forms login page with persistent sessions
**Depends on**: Phase 55 (middleware allows setup/login routes through whitelist)
**Requirements**: SETUP-01, SETUP-02, SETUP-03, SETUP-04, LOGIN-01, LOGIN-02, LOGIN-06, UI-01, UI-02
**Success Criteria** (what must be TRUE):
  1. User launching Triggarr with no credentials configured is redirected from every route to the `/setup` page, where they create a username, password (with confirmation), and see an auto-generated API key with a copy button
  2. After completing setup, the user is automatically logged in and redirected to the dashboard; subsequent visits to `/setup` return 404
  3. User can log in at `/login` with username and password; a valid login creates a signed session cookie that persists across browser restarts for 30 days
  4. User can click a logout button in the nav bar that clears the session cookie and redirects to `/login`
  5. Login and setup pages match AIDesigner HTML artifacts pixel-exact (design generated via AIDesigner, implemented faithfully in Jinja2 templates)
**Plans:** 4/4 plans complete
Plans:
- [x] 56-01-PLAN.md -- TDD: _safe_next_url open redirect prevention + _settings_to_dict auth extension
- [x] 56-02-PLAN.md -- Jinja2 templates (base-auth.html, login.html, setup.html) + nav bar logout
- [x] 56-03-PLAN.md -- Route handlers (setup, login, logout) + middleware ?next= update
- [x] 56-04-PLAN.md -- TDD: Integration tests for all auth route handlers

### Phase 57: Settings Security & Nav Logout
**Goal**: Users can manage their authentication settings -- change password, switch auth mode, view/copy/regenerate API key -- from a dedicated security section in Settings
**Depends on**: Phase 56 (user must be logged in to access settings; nav logout already wired)
**Requirements**: SET-01, SET-02, SET-03, SET-04, LOGIN-05, UI-03
**Success Criteria** (what must be TRUE):
  1. User sees a Security section on the Settings page with controls for auth method (Forms/Basic/External dropdown), password change (current + new + confirm), and API key management (masked display, copy button, regenerate button)
  2. User can change auth method from Settings and the change takes effect on next request (e.g., switching to Basic causes subsequent unauthenticated requests to get WWW-Authenticate popup)
  3. User can change password by entering current password, new password, and confirmation; incorrect current password is rejected with a clear error
  4. User sees a warning banner in the Settings security section when auth is disabled via config file, explaining that auth mode can only be changed back from the config file
  5. Settings security section matches AIDesigner HTML artifact pixel-exact
**Plans**: TBD
**UI hint**: yes

### Phase 58: Auth Test Suite
**Goal**: All authentication paths are covered by automated tests -- middleware enforcement, session lifecycle, setup flow, login/logout, API key auth, auth mode switching, and edge cases
**Depends on**: Phase 57 (all auth features implemented)
**Requirements**: (verification phase -- validates all requirements indirectly)
**Success Criteria** (what must be TRUE):
  1. Tests verify that unauthenticated requests to protected routes get redirected (browser) or receive 401 (API), and that /health is always accessible
  2. Tests verify the complete first-run setup flow: redirect to /setup, credential creation, API key display, /setup returns 404 after configuration
  3. Tests verify login with valid/invalid credentials, session cookie creation and validation, 30-day expiry, and logout clearing the cookie
  4. Tests verify all four auth modes (Forms redirect, Basic WWW-Authenticate, External pass-through, Disabled with warning log) behave correctly
  5. Tests verify API key authentication via X-Api-Key header, including valid key, invalid key, and missing key scenarios
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 54 -> 55 -> 56 -> 57 -> 58

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 54. Auth Config & Helpers | 2/2 | Complete    | 2026-04-15 |
| 55. Auth Middleware & Health Endpoint | 2/2 | Complete    | 2026-04-15 |
| 56. First-Run Setup & Login | 4/4 | Complete   | 2026-04-15 |
| 57. Settings Security & Nav Logout | 0/? | Not started | - |
| 58. Auth Test Suite | 0/? | Not started | - |
