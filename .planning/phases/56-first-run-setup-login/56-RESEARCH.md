# Phase 56: First-Run Setup & Login - Research

**Researched:** 2026-04-14
**Domain:** FastAPI route handlers, Jinja2 templates, session cookie management, TOML config persistence
**Confidence:** HIGH

## Summary

Phase 56 implements three route handlers (login, setup, logout) and three Jinja2 templates (base-auth.html, login.html, setup.html) plus a nav bar modification for conditional logout. All cryptographic helpers (hash_password, verify_password, sign_session, validate_session, generate_api_key, generate_session_secret) already exist in `triggarr/auth.py`. The AuthMiddleware already handles needs-setup redirect and exempt path whitelisting for /login and /setup prefixes. The middleware needs one update: appending `?next=` to login redirects.

The core work is form handling (POST routes with validation), TOML config writing (setup completion persists `[auth]` section), session cookie setting (on both setup completion and login success), and template creation following the AIDesigner pixel-exact spec. The `_settings_to_dict` helper in routes.py currently does NOT serialize the `auth` section -- the setup route must build the auth TOML dict manually, extracting SecretStr values.

**Primary recommendation:** Structure as three plans: (1) templates + base-auth layout, (2) route handlers (setup, login, logout) with config persistence and `?next=` middleware update, (3) nav bar logout link + tests.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** After submitting credentials (username + password with confirmation), the user sees a success screen with the auto-generated API key, a copy button, and a "Continue to Dashboard" button. User is auto-logged in (session cookie set) but stays on the setup success view to copy the key first.
- **D-02:** Copy button uses `navigator.clipboard.writeText()` with visual feedback (button text changes to "Copied"). Falls back to selecting the text if clipboard API is unavailable. Vanilla JS, no dependencies.
- **D-03:** Password validation: minimum 1 character (non-empty). No complexity rules. Password confirmation field must match.
- **D-04:** Login errors shown as inline red text below the form: "Invalid username or password". Generic message. Page re-renders with username pre-filled.
- **D-05:** After successful login, redirect to the original page via `?next=` query param. Middleware stores the original URL in `?next=` on the `/login` redirect. Falls back to dashboard (`/`) if no `?next=` param.
- **D-06:** If an already-authenticated user navigates to `/login`, redirect to dashboard.
- **D-07:** Login and setup pages use a standalone minimal layout -- centered card on dark background, no nav bar. A new `base-auth.html` template provides shared `<head>` with `{% block content %}` slot.
- **D-08:** AIDesigner MCP generates the HTML artifacts for login, setup, and setup-success pages. Implementation must match pixel-exact.
- **D-09:** Logout is instant -- POST to `/logout`, clears session cookie, redirects to `/login`. No confirmation dialog.
- **D-10:** Logout uses POST form submission (not GET link). Prevents CSRF via existing OriginCheckMiddleware.
- **D-11:** Logout link only visible when auth is active (Forms or Basic mode).
- **D-12:** Logout link placement and visual style determined by AIDesigner.

### Claude's Discretion
- Exact route handler structure (single router file vs separate auth routes file)
- Cookie attributes (path, httpOnly, secure, SameSite) -- follow security best practices
- Setup form field ordering and HTML structure (within AIDesigner's design)
- How `?next=` param is validated (must reject open redirects)
- Whether setup success is a separate route or same route with state

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SETUP-01 | User launching Triggarr for the first time is redirected to setup from all routes | AuthMiddleware already handles this (line 92-95 in middleware.py). Verified working in test_auth_middleware.py. |
| SETUP-02 | User can create credentials (username + password with confirmation) via setup form | POST /setup route with form parsing, bcrypt hashing via existing `hash_password()`, atomic TOML write |
| SETUP-03 | User sees auto-generated API key with copy button after completing setup | Setup success view with `generate_api_key()` output, clipboard JS per D-02 |
| SETUP-04 | Setup page returns 404 after auth is configured (one-time only) | GET /setup checks `auth.needs_setup`; returns 404 if False |
| LOGIN-01 | User can log in via Forms login page with username and password | POST /login with `verify_password()`, form re-render on failure per D-04 |
| LOGIN-02 | Session persists via signed cookie with 30-day expiry across browser restarts | `sign_session()` + `set_cookie()` with `max_age=COOKIE_MAX_AGE` (2592000s). Already tested. |
| LOGIN-06 | User can log out via nav bar button clearing session cookie | POST /logout deletes `triggarr_session` cookie, redirects to /login |
| UI-01 | Login page matches AIDesigner HTML artifact pixel-exact | `login.html` extends `base-auth.html`, follows 56-UI-SPEC.md contract |
| UI-02 | Setup page matches AIDesigner HTML artifact pixel-exact | `setup.html` extends `base-auth.html`, follows 56-UI-SPEC.md contract |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Python 3.11+, ruff linting (E, F, I, UP, B, SIM), line length 120
- SecretStr for all API keys -- `.get_secret_value()` only at HTTP client init or TOML serialization
- Loguru for logging (never print/logging module)
- Atomic file writes (write-then-rename) for config via `_atomic_toml_write()`
- pytest-asyncio with asyncio_mode=auto
- Deep review convention before pushing

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Setup form rendering | Frontend Server (FastAPI + Jinja2) | -- | Server-rendered HTML, no client-side framework |
| Credential creation + hashing | API / Backend (route handler) | -- | bcrypt hashing, TOML persistence, session signing -- all server-side |
| Login authentication | API / Backend (route handler) | -- | Password verification, session cookie creation -- server-only |
| Session cookie management | API / Backend (route handler) | Browser (cookie storage) | Server signs/validates; browser stores httpOnly cookie |
| Logout | API / Backend (route handler) | -- | Cookie deletion + redirect is server-side |
| Clipboard copy (API key) | Browser / Client | -- | `navigator.clipboard.writeText()` is browser-only JS |
| `?next=` redirect | API / Backend (middleware) | -- | Middleware appends param; login route validates and redirects |
| Auth-conditional nav | Frontend Server (Jinja2) | -- | Template conditional rendering based on server-side auth state |

## Standard Stack

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | project dep | Route handlers, form parsing, Request/Response | Already used for all routes [VERIFIED: routes.py] |
| Jinja2 | project dep | Template rendering | Already used for all pages [VERIFIED: routes.py] |
| bcrypt | project dep | Password hashing (12 rounds) | Already in auth.py [VERIFIED: auth.py] |
| itsdangerous | project dep | Signed session cookies (TimestampSigner) | Already in auth.py [VERIFIED: auth.py] |
| tomli_w | project dep | TOML writing for config persistence | Already in config.py [VERIFIED: config.py] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| starlette | transitive (via FastAPI) | RedirectResponse, HTMLResponse, Request | Route return types [VERIFIED: routes.py imports] |
| secrets | stdlib | `compare_digest` for timing-safe comparison | Already used in middleware [VERIFIED: middleware.py] |

No new dependencies needed. [VERIFIED: all imports exist in codebase]

## Architecture Patterns

### System Architecture Diagram

```
Browser Request
    |
    v
AuthMiddleware (middleware.py)
    |-- needs_setup? --> 302 /setup
    |-- exempt path? --> pass through
    |-- has session cookie? --> pass through
    |-- no auth? --> 302 /login?next={original_url}   <-- NEW: append ?next=
    |
    v
Route Handler (routes.py)
    |
    |-- GET /setup  --> needs_setup? render setup.html : 404
    |-- POST /setup --> validate form, hash password, generate API key,
    |                   write [auth] to TOML, set session cookie,
    |                   render setup success view
    |-- GET /login  --> has valid session? redirect / : render login.html
    |-- POST /login --> verify credentials, set cookie, redirect ?next= or /
    |-- POST /logout --> delete cookie, redirect /login
    |
    v
Config Persistence (config.py)
    |-- _atomic_toml_write() persists [auth] section
    |-- load_settings() reloads into app.state.settings
```

### Recommended File Structure

```
triggarr/
  templates/
    base-auth.html          # NEW: minimal auth layout (no nav)
    login.html              # NEW: extends base-auth.html
    setup.html              # NEW: extends base-auth.html (form + success states)
  web/
    routes.py               # MODIFY: add /login, /setup, /logout routes
    middleware.py            # MODIFY: add ?next= to login redirect
  templates/
    base.html               # MODIFY: add conditional logout link
```

### Pattern 1: Form POST Handler with Validation

**What:** Standard pattern for form-based route handlers in this project
**When to use:** All three POST routes (setup, login, logout)
**Example:**
```python
# Source: triggarr/web/routes.py save_settings pattern (line 419-511)
@router.post("/login")
async def login_post(request: Request) -> Response:
    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")
    # ... validate, then either re-render with error or redirect
```
[VERIFIED: existing save_settings handler at line 419]

### Pattern 2: Auth Config TOML Serialization

**What:** Writing auth section to TOML requires explicit SecretStr extraction
**When to use:** Setup completion writing `[auth]` to config
**Critical detail:** `AuthConfig.model_dump()` returns `SecretStr` objects, NOT plain strings. TOML serializer will fail on SecretStr. Must extract values manually.
**Example:**
```python
# Build auth dict for TOML (extract SecretStr values)
auth_dict = {
    "method": auth_config.method,
    "username": auth_config.username,
    "password_hash": auth_config.password_hash.get_secret_value(),
    "api_key": auth_config.api_key.get_secret_value(),
    "session_secret": auth_config.session_secret.get_secret_value(),
}
```
[VERIFIED: model_dump() returns SecretStr objects -- tested via Python REPL]

### Pattern 3: Settings Reload After Config Write

**What:** After writing TOML, reload settings into `app.state.settings`
**When to use:** After setup completion writes `[auth]` section
**Example:**
```python
# Source: triggarr/web/routes.py line 507-511
await asyncio.get_running_loop().run_in_executor(
    None, _atomic_toml_write, config_path, full_config_dict
)
request.app.state.settings = load_settings(config_path)
```
[VERIFIED: save_settings handler uses this pattern]

### Pattern 4: `?next=` Validation (Open Redirect Prevention)

**What:** Validate the `?next=` parameter to prevent open redirect attacks
**When to use:** Login POST handler before redirecting
**Example:**
```python
def _safe_next_url(next_param: str | None) -> str:
    """Validate ?next= param, rejecting open redirects. Returns safe URL or '/'."""
    if not next_param:
        return "/"
    # Reject absolute URLs, protocol-relative URLs, and non-path characters
    if next_param.startswith(("http://", "https://", "//")) or "\\" in next_param:
        return "/"
    # Must start with /
    if not next_param.startswith("/"):
        return "/"
    return next_param
```
[ASSUMED: standard open redirect prevention pattern]

### Pattern 5: Existing `_settings_to_dict` Needs Auth Section

**What:** The current `_settings_to_dict()` (line 140-154) does NOT include the `[auth]` section in its output
**When to use:** Setup must either extend `_settings_to_dict` or build the full config dict independently
**Critical detail:** Setup writes the entire config (not just auth), because `_atomic_toml_write` replaces the file. Must merge auth dict with existing general/instance config.
[VERIFIED: _settings_to_dict at line 140-154 only serializes general + app instances]

### Anti-Patterns to Avoid
- **Storing plaintext password in TOML:** Always use `hash_password()` before writing. Never log the password.
- **Using GET for logout:** Must be POST to prevent CSRF and accidental logout via link prefetch. D-10 is explicit.
- **Redirecting to arbitrary `?next=` URLs:** Must validate to prevent open redirect. Reject absolute URLs.
- **Calling `.get_secret_value()` outside TOML serialization:** Per CLAUDE.md SecretStr discipline.
- **Using `model_dump()` for TOML auth serialization:** Returns SecretStr objects that tomli_w cannot serialize. Must extract manually.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom hash function | `triggarr.auth.hash_password()` (bcrypt 12 rounds) | Already exists, tested, constant-time |
| Session cookies | Custom token format | `triggarr.auth.sign_session()` (itsdangerous) | Already exists, handles expiry, HMAC-signed |
| CSRF protection | Custom token middleware | Existing `OriginCheckMiddleware` | Already handles all POST/PUT/PATCH/DELETE |
| Atomic file writes | Raw `open().write()` | `triggarr.config._atomic_toml_write()` | Handles fsync, directory fsync, cleanup on failure |
| API key generation | Custom random string | `triggarr.auth.generate_api_key()` | CSPRNG, tested, correct format |
| Clipboard copy | External JS library | Vanilla `navigator.clipboard.writeText()` | D-02 specifies vanilla JS, browser API sufficient |

**Key insight:** Every cryptographic and persistence primitive this phase needs already exists and is tested. The phase is pure integration -- wiring existing helpers into route handlers and templates.

## Common Pitfalls

### Pitfall 1: SecretStr in TOML Serialization
**What goes wrong:** `tomli_w.dump()` raises `TypeError` when encountering a `SecretStr` object instead of a plain string
**Why it happens:** `AuthConfig.model_dump()` preserves `SecretStr` wrappers. The existing `_settings_to_dict()` only handles instance API keys, not auth fields.
**How to avoid:** Build auth dict manually with `.get_secret_value()` calls, or extend `_settings_to_dict()` to include auth section
**Warning signs:** `TypeError: can't convert SecretStr to TOML value` during setup POST

### Pitfall 2: Settings Not Reloaded After Setup
**What goes wrong:** After writing `[auth]` to TOML, the middleware still sees `needs_setup=True` because `app.state.settings` wasn't updated
**Why it happens:** File write doesn't automatically update in-memory state
**How to avoid:** Call `load_settings(config_path)` after `_atomic_toml_write()` and assign to `request.app.state.settings`
**Warning signs:** User stuck in redirect loop to /setup after completing setup

### Pitfall 3: Missing `?next=` Open Redirect Validation
**What goes wrong:** Attacker crafts `?next=https://evil.com` to redirect user after login
**Why it happens:** Trusting user-supplied redirect URL without validation
**How to avoid:** Only allow relative paths starting with `/`, reject protocol-relative (`//`) and absolute URLs
**Warning signs:** Login redirect goes to external domain

### Pitfall 4: Cookie `secure` Flag in Dev
**What goes wrong:** Session cookie not sent over HTTP in development (only HTTPS)
**Why it happens:** Setting `secure=True` unconditionally
**How to avoid:** The existing middleware sets `secure=True` in Basic auth cookie setting (line 156). For consistency, do the same. In Docker behind reverse proxy (the standard deployment), HTTPS is handled by the proxy.
**Warning signs:** Login works but session doesn't persist on page reload over HTTP
[VERIFIED: middleware.py line 156 sets secure=True for Basic auth cookies]

### Pitfall 5: Setup Race Condition
**What goes wrong:** Two simultaneous setup POST requests could both succeed, overwriting each other
**Why it happens:** No lock between needs_setup check and config write
**How to avoid:** Use `request.app.state.search_lock` (same lock pattern as save_settings) to serialize config mutations. Check `needs_setup` again inside the lock.
**Warning signs:** Unlikely in single-user app, but defense-in-depth
[VERIFIED: save_settings uses search_lock at line 506]

### Pitfall 6: `_settings_to_dict` Drops Auth Section
**What goes wrong:** After setup writes auth config, a subsequent settings save via the existing save_settings route strips the `[auth]` section from the TOML file because `_settings_to_dict()` doesn't include it
**Why it happens:** `_settings_to_dict()` only serializes `general` + app instances (verified at line 140-154)
**How to avoid:** Update `_settings_to_dict()` to include the auth section with SecretStr extraction. This is critical -- without it, the first settings save after setup will delete the user's credentials.
**Warning signs:** User logs in, changes a setting, and is suddenly redirected to /setup again

## Code Examples

### Setup POST Handler (Core Logic)
```python
# Source: Derived from existing patterns in routes.py
@router.post("/setup")
async def setup_post(request: Request) -> Response:
    auth = request.app.state.settings.auth
    if not auth.needs_setup:
        return Response(status_code=404)

    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")
    confirm = form.get("confirm_password", "")

    errors = {}
    if not username:
        errors["username"] = "Username is required"
    if not password:
        errors["password"] = "Password is required"
    elif password != confirm:
        errors["confirm_password"] = "Passwords do not match"

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="setup.html",
            context={"errors": errors, "username": username},
        )

    # Create credentials
    password_hash = hash_password(password)
    api_key = generate_api_key()
    session_secret = generate_session_secret()

    new_auth = AuthConfig(
        method="Forms",
        username=username,
        password_hash=SecretStr(password_hash),
        api_key=SecretStr(api_key),
        session_secret=SecretStr(session_secret),
    )

    # Persist to TOML (merge with existing config)
    config_path = request.app.state.config_path
    async with request.app.state.search_lock:
        existing = load_settings(config_path)
        config_dict = _settings_to_dict_with_auth(existing, new_auth)
        await asyncio.get_running_loop().run_in_executor(
            None, _atomic_toml_write, config_path, config_dict
        )
        os.chmod(config_path, 0o600)
        request.app.state.settings = load_settings(config_path)

    # Auto-login: set session cookie
    session_value = sign_session(username, session_secret)
    response = templates.TemplateResponse(
        request=request,
        name="setup.html",
        context={"setup_complete": True, "api_key": api_key, "username": username},
    )
    response.set_cookie(
        "triggarr_session",
        session_value,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=True,
    )
    return response
```
[ASSUMED: implementation pattern -- actual code will follow this structure]

### Middleware ?next= Update
```python
# Source: triggarr/web/middleware.py line 122-124 (current fallback)
# BEFORE:
return RedirectResponse("/login", status_code=302)

# AFTER:
from urllib.parse import quote
next_url = quote(str(request.url.path), safe="/")
return RedirectResponse(f"/login?next={next_url}", status_code=302)
```
[VERIFIED: current redirect at middleware.py line 123 has no ?next=]

### Copy Button JS (Vanilla)
```javascript
// Source: D-02 decision
function copyApiKey(btn) {
    var text = document.getElementById('api-key-display').textContent;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function() {
            btn.textContent = 'Copied!';
            setTimeout(function() { btn.textContent = 'Copy'; }, 2000);
        });
    } else {
        // Fallback: select text
        var range = document.createRange();
        range.selectNodeContents(document.getElementById('api-key-display'));
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(range);
        btn.textContent = 'Copied!';
        setTimeout(function() { btn.textContent = 'Copy'; }, 2000);
    }
}
```
[ASSUMED: standard clipboard API pattern]

### Nav Bar Conditional Logout
```html
<!-- Source: D-10, D-11 from CONTEXT.md + base.html structure -->
{% if auth_active %}
<form method="post" action="{{ request.url_for('logout') }}" class="inline">
  <button type="submit"
          class="text-triggarr-muted hover:text-white text-sm transition-colors cursor-pointer">
    Logout
  </button>
</form>
{% endif %}
```
[VERIFIED: base.html nav structure at line 38-51]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom session token format | itsdangerous TimestampSigner | Already in auth.py | No change needed, production-ready |
| sha256 password hash | bcrypt 12 rounds | Already in auth.py | No change needed, industry standard |

**Deprecated/outdated:**
- None relevant -- all auth primitives are current and already implemented.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Open redirect prevention via path-only validation is sufficient | Architecture Patterns (Pattern 4) | LOW -- standard practice, but edge cases with encoded chars possible |
| A2 | `secure=True` cookie flag works in Docker behind reverse proxy | Pitfalls (Pitfall 4) | MEDIUM -- if users access directly over HTTP without proxy, sessions won't persist. Matches existing middleware behavior. |
| A3 | `search_lock` is the appropriate lock for config mutations during setup | Pitfalls (Pitfall 5) | LOW -- same pattern as save_settings, already proven |

**If this table is empty:** N/A -- three assumptions listed above.

## Open Questions

1. **Should `_settings_to_dict()` be updated to include auth, or should setup build its own config dict?**
   - What we know: Current `_settings_to_dict()` at line 140-154 excludes auth entirely. The save_settings route uses it.
   - What's unclear: Whether updating it now vs deferring to Phase 57 (settings security section) is better
   - Recommendation: Update it now -- Pitfall 6 means the first settings save after setup would delete auth. This is a correctness bug, not a nice-to-have.

2. **Should auth routes go in routes.py or a separate auth_routes.py?**
   - What we know: CONTEXT.md lists this as Claude's discretion. routes.py is already large (~940 lines).
   - What's unclear: Whether the team prefers consolidation or separation
   - Recommendation: Add to routes.py for consistency (single router pattern), but group auth routes together with a clear section comment. Can refactor later if routes.py grows unwieldy.

3. **How should `auth_active` template variable be provided to base.html?**
   - What we know: Every route using base.html needs this variable for the conditional logout link
   - What's unclear: Whether to add it as a Jinja2 global (like `triggarr_version`) or pass per-request
   - Recommendation: Add as a Jinja2 global that reads from `app.state.settings.auth` at render time, or use a middleware/context processor pattern. A Jinja2 global function is cleanest since it avoids modifying every existing route handler.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (asyncio_mode=auto) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_auth_routes.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SETUP-01 | First-run redirects to /setup | integration | `uv run pytest tests/test_auth_middleware.py -x -q` | existing (partial) |
| SETUP-02 | Setup form creates credentials | integration | `uv run pytest tests/test_auth_routes.py::test_setup_post_creates_credentials -x` | Wave 0 |
| SETUP-03 | API key shown after setup | integration | `uv run pytest tests/test_auth_routes.py::test_setup_success_shows_api_key -x` | Wave 0 |
| SETUP-04 | Setup returns 404 after config | integration | `uv run pytest tests/test_auth_routes.py::test_setup_returns_404_when_configured -x` | Wave 0 |
| LOGIN-01 | Login with username/password | integration | `uv run pytest tests/test_auth_routes.py::test_login_valid_credentials -x` | Wave 0 |
| LOGIN-02 | Session cookie 30-day expiry | unit | `uv run pytest tests/test_auth_helpers.py -x -q` | existing |
| LOGIN-06 | Logout clears cookie | integration | `uv run pytest tests/test_auth_routes.py::test_logout_clears_session -x` | Wave 0 |
| UI-01 | Login page renders | smoke | `uv run pytest tests/test_auth_routes.py::test_login_page_renders -x` | Wave 0 |
| UI-02 | Setup page renders | smoke | `uv run pytest tests/test_auth_routes.py::test_setup_page_renders -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_auth_routes.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_auth_routes.py` -- covers SETUP-02, SETUP-03, SETUP-04, LOGIN-01, LOGIN-06, UI-01, UI-02
- [ ] Test app factory that mounts real routes with mock config (similar to `_make_auth_app` in test_auth_middleware.py but with actual route handlers)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | bcrypt 12 rounds (auth.py), timing-safe comparison (secrets.compare_digest) |
| V3 Session Management | yes | itsdangerous TimestampSigner, 30-day max_age, httpOnly+SameSite+Secure cookie |
| V4 Access Control | yes | AuthMiddleware deny-all with whitelist (middleware.py) |
| V5 Input Validation | yes | Password match validation, username non-empty, `?next=` open redirect prevention |
| V6 Cryptography | no | No custom crypto -- bcrypt and itsdangerous handle it |

### Known Threat Patterns for FastAPI + Cookie Auth

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| CSRF on login/setup/logout | Tampering | OriginCheckMiddleware (already active) [VERIFIED] |
| Open redirect via `?next=` | Spoofing | Validate relative-path-only, reject absolute/protocol-relative URLs |
| Session fixation | Elevation | New session generated on login (sign_session creates fresh signature) |
| Credential brute force | Tampering | Out of scope for v2.6 (FUT-01). bcrypt is slow by design (~250ms/attempt). |
| Cookie theft (XSS) | Information Disclosure | httpOnly=True prevents JS access. CSP not in scope but recommended future. |
| Timing attack on password | Information Disclosure | bcrypt is constant-time. Generic error message per D-04. |

## Sources

### Primary (HIGH confidence)
- `triggarr/auth.py` -- All crypto helpers verified by reading source
- `triggarr/web/middleware.py` -- AuthMiddleware dispatch order, exempt paths, cookie attributes verified
- `triggarr/web/routes.py` -- Form handling pattern, _settings_to_dict gap, TemplateResponse pattern verified
- `triggarr/models/config.py` -- AuthConfig model, needs_setup property, SecretStr fields verified
- `triggarr/config.py` -- _atomic_toml_write, load_settings verified
- `tests/test_auth_helpers.py` -- Existing test patterns for auth functions verified
- `tests/test_auth_middleware.py` -- Test app factory pattern for middleware testing verified
- `.planning/phases/56-first-run-setup-login/56-CONTEXT.md` -- All 12 decisions verified
- `.planning/phases/56-first-run-setup-login/56-UI-SPEC.md` -- Template structure, page inventory verified
- `docs/superpowers/specs/2026-04-14-built-in-auth-design.md` -- Full design spec verified

### Secondary (MEDIUM confidence)
- None needed -- all findings come from direct codebase inspection

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in project, verified via source
- Architecture: HIGH - all patterns verified against existing codebase
- Pitfalls: HIGH - pitfall 6 (_settings_to_dict gap) verified via source inspection

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (stable -- no external API changes expected)
