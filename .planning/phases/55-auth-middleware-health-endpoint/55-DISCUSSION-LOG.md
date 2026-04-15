# Phase 55: Auth Middleware & Health Endpoint - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-04-14
**Phase:** 55-auth-middleware-health-endpoint
**Areas discussed:** Middleware placement, Needs-setup redirect, Health endpoint scope, Basic auth session

---

## Middleware Placement

### File Location

| Option | Description | Selected |
|--------|-------------|----------|
| Existing middleware.py | Add to triggarr/web/middleware.py alongside SecurityHeaders and OriginCheck | :heavy_check_mark: |
| New auth_middleware.py | Separate file for auth middleware, cleaner separation | |

**User's choice:** Existing middleware.py
**Notes:** Keeps all middleware in one file, consistent with existing pattern.

### Config Access

| Option | Description | Selected |
|--------|-------------|----------|
| app.state | Store settings on app.state, middleware reads request.app.state.settings.auth | :heavy_check_mark: |
| Constructor injection | Pass AuthConfig to constructor at registration time | |
| You decide | Claude picks best approach | |

**User's choice:** app.state
**Notes:** Matches FastAPI convention, allows config updates if settings are reloaded.

### Setup Guard

| Option | Description | Selected |
|--------|-------------|----------|
| Middleware handles both | AuthMiddleware checks needs_setup first, single enforcement point | :heavy_check_mark: |
| Separate setup middleware | Dedicated SetupGuardMiddleware before AuthMiddleware | |

**User's choice:** Middleware handles both
**Notes:** Single enforcement point, impossible to miss a route.

---

## Needs-Setup Redirect

### API Handling During Setup

| Option | Description | Selected |
|--------|-------------|----------|
| JSON 401 with setup hint | Return 401 {"detail": "Setup required", "setup_url": "/setup"} | :heavy_check_mark: |
| Redirect everything to /setup | Even API requests get 302 | |
| 503 Service Unavailable | Return 503 since app isn't fully configured | |

**User's choice:** JSON 401 with setup hint
**Notes:** API callers learn they need browser setup. Clear and actionable.

### Setup Path After Config

| Option | Description | Selected |
|--------|-------------|----------|
| Always exempt, route returns 404 | /setup stays in whitelist, route handler checks needs_setup | :heavy_check_mark: |
| Middleware blocks /setup after config | Middleware removes /setup from whitelist when configured | |

**User's choice:** Always exempt, route returns 404
**Notes:** Simpler middleware logic, route handler owns the 404 decision.

---

## Health Endpoint Scope

### Response Body

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal {"status": "ok"} | Per design spec, uptime monitors only need 200 | :heavy_check_mark: |
| Include version | Add version field, slightly more useful for monitoring | |
| Rich health check | Version, uptime, instance connectivity | |

**User's choice:** Minimal {"status": "ok"}
**Notes:** Per design spec. No version info exposed to unauthenticated callers.

### Route Location

| Option | Description | Selected |
|--------|-------------|----------|
| In existing routes.py | Add to triggarr/web/routes.py, 2-line function | :heavy_check_mark: |
| New health.py file | Own APIRouter in separate file | |

**User's choice:** In existing routes.py
**Notes:** Too simple for its own file.

---

## Basic Auth Session

### Credential Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Middleware validates inline | Decode Basic header, call verify_password(), set cookie if valid | :heavy_check_mark: |
| Redirect to /login POST | Forward to login handler, reuses login logic | |

**User's choice:** Middleware validates inline
**Notes:** Self-contained, no redirect hop needed.

### Cookie Priority

| Option | Description | Selected |
|--------|-------------|----------|
| Cookie takes priority | Valid session cookie = authenticated regardless of mode | :heavy_check_mark: |
| Always challenge in Basic mode | Ignore cookies when mode is Basic | |

**User's choice:** Cookie takes priority
**Notes:** Design spec says "session cookie still set to avoid re-prompting." Cookie-first avoids unnecessary challenges.

---

## Claude's Discretion

- Exact middleware class structure (single dispatch vs helpers)
- BaseHTTPMiddleware vs pure ASGI middleware
- Error response JSON structure beyond minimum fields
- How to attach settings to app.state

## Deferred Ideas

None -- discussion stayed within phase scope.
