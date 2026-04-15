# Phase 55: Auth Middleware & Health Endpoint - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Every route in the application requires authentication by default via a deny-all middleware with path whitelist. Correct handling for API keys, session cookies, Basic auth, External auth, Disabled mode, unauthenticated /health endpoint, and browser vs API redirect behavior. No login page, no setup page UI, no settings -- those are Phase 56/57.

</domain>

<decisions>
## Implementation Decisions

### Middleware Placement
- **D-01:** AuthMiddleware class lives in `triggarr/web/middleware.py` alongside existing SecurityHeadersMiddleware and OriginCheckMiddleware. One file, all middleware.
- **D-02:** Config access via `request.app.state.settings.auth` -- store settings on `app.state` during startup. Matches FastAPI convention, allows config to update if settings are reloaded.
- **D-03:** AuthMiddleware handles both authentication enforcement AND first-run setup redirect. Single enforcement point -- impossible to miss a route.

### Needs-Setup Redirect
- **D-04:** When `auth.needs_setup` is true, browser requests to non-exempt routes get 302 redirect to `/setup`. API requests (non-browser) get 401 JSON: `{"detail": "Setup required", "setup_url": "/setup"}`.
- **D-05:** `/setup` stays in the exempt whitelist permanently. The route handler (Phase 56) checks `auth.needs_setup` and returns 404 if setup is already complete. Middleware doesn't need to know setup state for whitelist logic.

### Health Endpoint
- **D-06:** `GET /health` returns minimal `{"status": "ok"}` with 200. No version, no instance health, no uptime -- uptime monitors only need a 200 response.
- **D-07:** Health route lives in existing `triggarr/web/routes.py`. It's a 2-line function, no separate file needed.

### Basic Auth Session
- **D-08:** Middleware validates Basic auth credentials inline -- decodes `Authorization: Basic` header, calls `verify_password()` directly, sets session cookie on the response if valid. No redirect to /login needed.
- **D-09:** Valid session cookie takes priority over auth mode. If a user has a valid session cookie, they're authenticated regardless of whether mode is Forms or Basic. Avoids re-prompting after first Basic auth (design spec: "session cookie still set to avoid re-prompting").

### Auth Check Order (from design spec + decisions above)
- **D-10:** Middleware check order for non-exempt paths:
  1. `needs_setup` true? -> redirect to /setup (browser) or 401 setup-required JSON (API)
  2. `is_disabled` true? -> pass through
  3. `method == "External"`? -> pass through
  4. Valid session cookie? -> pass through
  5. Valid `X-Api-Key` header? -> pass through
  6. `method == "Basic"`? -> check Authorization header, validate, set cookie if valid, or return 401 with WWW-Authenticate
  7. Else -> redirect to /login (browser) or 401 JSON (API)

### Claude's Discretion
- Exact middleware class structure (single dispatch method vs helper methods for each check)
- Whether to use Starlette's BaseHTTPMiddleware or pure ASGI middleware
- Error response JSON structure beyond the minimum fields specified
- How to attach settings to app.state (lifespan vs startup event)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Specification
- `docs/superpowers/specs/2026-04-14-built-in-auth-design.md` -- Full auth design: config schema, auth flow, session management, all four modes, exempt paths, file manifest

### Phase 54 Context
- `.planning/phases/54-auth-config-helpers/54-CONTEXT.md` -- AuthConfig decisions, helper module structure, SecretStr discipline

### Existing Code (must understand before modifying)
- `triggarr/web/middleware.py` -- Where AuthMiddleware will be added (D-01); existing SecurityHeadersMiddleware and OriginCheckMiddleware as pattern reference
- `triggarr/__main__.py` -- Where middleware is registered via app.add_middleware(); where app.state.settings should be set (D-02)
- `triggarr/auth.py` -- Auth helpers consumed by middleware: validate_session(), verify_password()
- `triggarr/models/config.py` -- AuthConfig with needs_setup/is_disabled properties
- `triggarr/web/routes.py` -- Where /health endpoint will be added (D-07)

### Requirements
- `.planning/REQUIREMENTS.md` -- MID-01, MID-02, MID-03, MID-04, LOGIN-03, LOGIN-04 mapped to this phase

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `BaseHTTPMiddleware` pattern from existing SecurityHeadersMiddleware/OriginCheckMiddleware
- `validate_session()` in triggarr/auth.py -- validates signed session cookies
- `verify_password()` in triggarr/auth.py -- bcrypt password verification for Basic auth
- `AuthConfig.needs_setup` / `AuthConfig.is_disabled` properties -- ready to use in middleware checks

### Established Patterns
- Middleware uses Starlette `BaseHTTPMiddleware` with `dispatch()` method
- Middleware registered in `__main__.py` via `app.add_middleware()`
- Settings loaded in `startup()` and passed to `create_lifespan()`
- Routes use FastAPI `APIRouter` in `triggarr/web/routes.py`

### Integration Points
- `triggarr/web/middleware.py` -- add AuthMiddleware class
- `triggarr/__main__.py` -- register AuthMiddleware, attach settings to app.state
- `triggarr/web/routes.py` -- add GET /health endpoint
- `triggarr/search/scheduler.py` -- lifespan function where settings are available; may need to set app.state.settings here

</code_context>

<specifics>
## Specific Ideas

- Exempt path prefixes per design spec: `/health`, `/static`, `/login`, `/setup`
- Browser detection via `Accept: text/html` header (design spec)
- Basic auth realm: `Triggarr` (design spec: `WWW-Authenticate: Basic realm="Triggarr"`)
- Session cookie name: `triggarr_session` (design spec)
- API key header: `X-Api-Key` (design spec, matches *arr convention)
- Cookie signing uses `auth.session_secret.get_secret_value()` for the secret
- API key comparison uses `auth.api_key.get_secret_value()` -- use `secrets.compare_digest()` for timing-safe comparison

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 55-auth-middleware-health-endpoint*
*Context gathered: 2026-04-14*
