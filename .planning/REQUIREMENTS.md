# Requirements: Triggarr v2.6 Built-In Authentication

**Defined:** 2026-04-14
**Core Value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.

**Design spec:** `docs/superpowers/specs/2026-04-14-built-in-auth-design.md`
**UI approach:** AIDesigner generates HTML artifacts for login, setup, and settings security pages; implementation matches pixel-exact.

## v2.6 Requirements

Requirements for the Built-In Authentication milestone. Each maps to exactly one roadmap phase. Adds *arr-style auth — secure by default with Forms/Basic/External/Disabled modes.

### First-Run Setup

- [ ] **SETUP-01**: User launching Triggarr for the first time is redirected to a setup page from all routes
- [ ] **SETUP-02**: User can create credentials (username + password with confirmation) via the setup form
- [ ] **SETUP-03**: User sees an auto-generated API key with a copy button after completing setup
- [ ] **SETUP-04**: Setup page returns 404 after auth is configured (one-time only)

### Login & Sessions

- [ ] **LOGIN-01**: User can log in via a Forms login page with username and password
- [ ] **LOGIN-02**: User session persists via signed cookie with 30-day expiry across browser restarts
- [ ] **LOGIN-03**: User can switch auth method to Basic (browser native WWW-Authenticate popup)
- [ ] **LOGIN-04**: User can switch auth method to External for reverse proxy delegation (Authelia/Authentik)
- [ ] **LOGIN-05**: User can disable auth via config file only (not UI), with startup warning logged every 60s
- [ ] **LOGIN-06**: User can log out via a button in the nav bar, clearing the session cookie

### Middleware & API

- [ ] **MID-01**: All routes require authentication by default (deny-all middleware with path whitelist)
- [ ] **MID-02**: User can authenticate API requests via `X-Api-Key` header
- [ ] **MID-03**: `GET /health` returns `{"status": "ok"}` without authentication for uptime monitors
- [ ] **MID-04**: Unauthenticated browser requests redirect to `/login`; unauthenticated API requests return 401 JSON

### Settings UI

- [ ] **SET-01**: User can change auth method (Forms/Basic/External) from the Settings security section
- [ ] **SET-02**: User can change password via current + new + confirm form in Settings
- [ ] **SET-03**: User can view (masked), copy, and regenerate the API key from Settings
- [ ] **SET-04**: User sees a warning banner in Settings if auth is disabled via config file

### UI Design

- [ ] **UI-01**: Login page generated via AIDesigner as HTML artifact; implementation matches pixel-exact
- [ ] **UI-02**: Setup page generated via AIDesigner as HTML artifact; implementation matches pixel-exact
- [ ] **UI-03**: Settings security section generated via AIDesigner as HTML artifact; implementation matches pixel-exact

## Future Requirements

Deferred to a later milestone. Tracked but not in this roadmap.

### Auth enhancements

- **FUT-01**: Rate limiting on login endpoint (brute-force protection)
- **FUT-02**: Remember-me checkbox with configurable session duration
- **FUT-03**: Session activity log (last login time, IP)
- **FUT-04**: LDAP/OIDC integration for enterprise environments

## Out of Scope

Explicitly excluded from v2.6 to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Multi-user accounts | Single-user app — one set of credentials sufficient |
| OAuth / SSO | Forms/Basic/External modes cover all homelab auth patterns |
| Rate limiting on login | Reverse proxy handles this; defer to future if needed |
| Password complexity rules | Single-user self-hosted — user manages their own security |
| Email-based password reset | No email infrastructure; single-user resets via config file |
| Two-factor authentication | Overkill for single-user homelab tool; External mode delegates to 2FA-capable proxies |
| Session revocation UI | Single-user; changing password or session secret invalidates all sessions |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SETUP-01 | — | Pending |
| SETUP-02 | — | Pending |
| SETUP-03 | — | Pending |
| SETUP-04 | — | Pending |
| LOGIN-01 | — | Pending |
| LOGIN-02 | — | Pending |
| LOGIN-03 | — | Pending |
| LOGIN-04 | — | Pending |
| LOGIN-05 | — | Pending |
| LOGIN-06 | — | Pending |
| MID-01 | — | Pending |
| MID-02 | — | Pending |
| MID-03 | — | Pending |
| MID-04 | — | Pending |
| SET-01 | — | Pending |
| SET-02 | — | Pending |
| SET-03 | — | Pending |
| SET-04 | — | Pending |
| UI-01 | — | Pending |
| UI-02 | — | Pending |
| UI-03 | — | Pending |

**Coverage:**
- v2.6 requirements: 21 total
- Mapped to phases: 0
- Unmapped: 21 ⚠️

---
*Requirements defined: 2026-04-14*
*Last updated: 2026-04-14 after initial definition*
