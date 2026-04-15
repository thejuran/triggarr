# Phase 56: First-Run Setup & Login - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Users launching Triggarr for the first time are guided through credential creation via a setup page, and returning users can log in via the Forms login page with persistent sessions. Includes setup page, login page, logout mechanism, session cookie management, and first-run redirect guard. No settings UI, no auth mode switching -- those are Phase 57.

</domain>

<decisions>
## Implementation Decisions

### Setup Completion Flow
- **D-01:** After submitting credentials (username + password with confirmation), the user sees a **success screen with the auto-generated API key**, a copy button, and a "Continue to Dashboard" button. User is auto-logged in (session cookie set) but stays on the setup success view to copy the key first.
- **D-02:** Copy button uses `navigator.clipboard.writeText()` with visual feedback (button text changes to "Copied"). Falls back to selecting the text if clipboard API is unavailable. Vanilla JS, no dependencies.
- **D-03:** Password validation: **minimum 1 character** (non-empty). No complexity rules. Matches Out of Scope decision: "Password complexity rules -- single-user self-hosted, user manages their own security." Password confirmation field must match.

### Login Page Behavior
- **D-04:** Login errors shown as **inline red text below the form**: "Invalid username or password". Generic message (no hint whether username or password was wrong). Page re-renders with username pre-filled.
- **D-05:** After successful login, redirect to the **original page via `?next=` query param**. Middleware stores the original URL in `?next=` on the `/login` redirect. Falls back to dashboard (`/`) if no `?next=` param.
- **D-06:** If an already-authenticated user navigates to `/login`, **redirect to dashboard**. No reason to show the login form to a logged-in user.

### Template Structure
- **D-07:** Login and setup pages use a **standalone minimal layout** -- centered card on dark background, no nav bar, no app chrome. A new `base-auth.html` template provides shared `<head>` (CSS, favicon, viewport) with a `{% block content %}` slot. `login.html` and `setup.html` extend `base-auth.html`.
- **D-08:** **AIDesigner MCP generates the HTML artifacts** for login, setup, and setup-success pages. Implementation must match pixel-exact. The AIDesigner output is the hard spec -- no freestyling the visual design.

### Logout & Nav Integration
- **D-09:** Logout is **instant** -- click triggers POST to `/logout`, clears session cookie, redirects to `/login`. No confirmation dialog. Single-user app.
- **D-10:** Logout uses **POST form submission** (not GET link). Prevents CSRF via existing OriginCheckMiddleware. Follows REST convention (state-changing = POST). Can use htmx `hx-post` or a small `<form>`.
- **D-11:** Logout link **only visible when auth is active** (Forms or Basic mode). Hidden when auth_method is Disabled or External (reverse proxy manages sessions in those modes).
- **D-12:** Logout link placement and visual style determined by **AIDesigner** when generating/updating the nav bar design.

### Claude's Discretion
- Exact route handler structure (single router file vs separate auth routes file)
- Cookie attributes (path, httpOnly, secure, SameSite) -- follow security best practices
- Setup form field ordering and HTML structure (within AIDesigner's design)
- How `?next=` param is validated (must reject open redirects)
- Whether setup success is a separate route or same route with state

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Specification
- `docs/superpowers/specs/2026-04-14-built-in-auth-design.md` -- Full auth design: config schema, auth flow, session management, all four modes, setup flow, file manifest

### Prior Phase Context
- `.planning/phases/54-auth-config-helpers/54-CONTEXT.md` -- AuthConfig model, helper module (hash_password, sign_session, generate_api_key, etc.), SecretStr discipline, TOML serialization
- `.planning/phases/55-auth-middleware-health-endpoint/55-CONTEXT.md` -- Middleware placement, needs-setup redirect (D-04/D-05), exempt path whitelist, auth check order (D-10), Basic auth session handling

### Existing Code (must understand before modifying)
- `triggarr/auth.py` -- Auth helpers: hash_password, verify_password, sign_session, validate_session, generate_api_key, generate_session_secret, COOKIE_MAX_AGE
- `triggarr/web/middleware.py` -- AuthMiddleware with EXEMPT_PREFIXES (/health, /static, /login, /setup), needs-setup redirect, session/API key validation
- `triggarr/web/routes.py` -- Existing route handlers, Jinja2 TemplateResponse pattern, where /login, /setup, /logout routes will be added
- `triggarr/models/config.py` -- AuthConfig model with needs_setup/is_disabled properties
- `triggarr/config.py` -- _atomic_toml_write(), load_settings() for writing auth config on setup completion
- `triggarr/templates/base.html` -- Existing nav bar template (logout link will be added here conditionally)

### Requirements
- `.planning/REQUIREMENTS.md` -- SETUP-01, SETUP-02, SETUP-03, SETUP-04, LOGIN-01, LOGIN-02, LOGIN-06, UI-01, UI-02 mapped to this phase

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `triggarr/auth.py` -- All crypto helpers ready: hash_password, verify_password, sign_session, validate_session, generate_api_key, generate_session_secret
- `triggarr/web/middleware.py` -- AuthMiddleware already handles needs-setup redirect and exempt path whitelist; /setup and /login already exempt
- `triggarr/config.py` -- `_atomic_toml_write()` for persisting auth config after setup; `load_settings()` for reloading
- Existing `TemplateResponse` pattern in `routes.py` for rendering Jinja2 templates
- Tailwind CSS v4 with custom `triggarr-*` color tokens already configured

### Established Patterns
- Routes use FastAPI `APIRouter` in `triggarr/web/routes.py`
- Templates in `triggarr/templates/` extending `base.html`
- `request.url_for()` everywhere for root_path-aware URLs
- htmx for dynamic interactions (polling, form submissions)
- SecretStr `.get_secret_value()` only at HTTP client init or TOML serialization

### Integration Points
- `triggarr/web/routes.py` -- Add GET/POST /login, GET/POST /setup, POST /logout routes
- `triggarr/templates/` -- Add base-auth.html, login.html, setup.html templates
- `triggarr/templates/base.html` -- Add conditional logout link in nav bar
- `triggarr/config.py` -- Setup completion writes [auth] section to triggarr.toml
- `triggarr/__main__.py` -- May need to reload settings after setup writes config

</code_context>

<specifics>
## Specific Ideas

- AIDesigner MCP generates HTML artifacts for login, setup, and setup-success pages -- these are the hard spec, implemented pixel-exact in Jinja2 templates
- API key display on setup success: monospace font, full 32-char hex visible, copy button with clipboard API
- Session cookie name: `triggarr_session` (from design spec)
- Login POST to `/login`, Setup POST to `/setup`, Logout POST to `/logout`
- `?next=` param on login redirect must be validated to prevent open redirect attacks (reject absolute URLs, only allow relative paths)
- Nav bar logout link conditionally rendered: `{% if auth_method in ("Forms", "Basic") %}`

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 56-first-run-setup-login*
*Context gathered: 2026-04-14*
