# Built-In Authentication

## Overview

Add optional built-in authentication to Triggarr following the *arr ecosystem pattern: secure by default, with Forms/Basic/External/Disabled modes. First-run setup creates credentials and an API key. Single new dependency (`bcrypt`).

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Credential storage | `[auth]` section in `triggarr.toml` | Single-file config pattern, password is bcrypt-hashed |
| First-run experience | Redirect to `/setup` page | Matches Sonarr/Radarr, works in Docker |
| Session management | Signed cookies via `itsdangerous` | Stateless, no DB changes, already a Starlette transitive dep |
| Protected scope | Everything except `/health` | Uptime monitors need unauthenticated health check |
| Enforcement mechanism | Starlette middleware (deny-all + whitelist) | Matches existing middleware pattern, impossible to forget auth on new routes |

## Config Schema

New `[auth]` section in `triggarr.toml`:

```toml
[auth]
method = "Forms"           # Forms | Basic | External | Disabled
username = "admin"
password_hash = "$2b$12$..." # bcrypt hash, written by setup/settings
api_key = "a1b2c3d4..."     # auto-generated 32-char hex token
```

- `method` controls enforcement mode
- `password_hash` is never plaintext — setup page hashes before writing
- `api_key` is generated once at setup, visible in Settings, regenerable
- When `method = "External"`, middleware trusts the request is pre-authenticated by reverse proxy
- When `method = "Disabled"`, startup logs a prominent warning every 60 seconds

### Pydantic Model

```python
class AuthConfig(BaseModel):
    method: Literal["Forms", "Basic", "External", "Disabled"] = "Forms"
    username: str = ""
    password_hash: str = ""
    api_key: str = ""
```

Added as `auth: AuthConfig = AuthConfig()` on `Settings`. When `auth.username` is empty, the app is in "needs setup" state.

## Auth Flow

```
Request arrives
  -> AuthMiddleware checks path
    -> /health, /static, /login, /setup -> pass through (whitelist)
    -> Everything else:
      -> Has valid session cookie? -> pass through
      -> Has valid X-Api-Key header? -> pass through
      -> method = External? -> pass through
      -> method = Disabled? -> pass through
      -> Else -> redirect to /login (browser) or 401 JSON (API/htmx)
```

### Browser vs API Detection

Middleware checks the `Accept` header:
- Contains `text/html` -> redirect to `/login`
- Otherwise -> return `{"detail": "Authentication required"}` with 401

## First-Run Setup

1. App starts, loads config, finds no `[auth]` section (or empty `username`)
2. `AuthMiddleware` detects "needs setup" state -> redirects all non-exempt routes to `/setup`
3. `/setup` page renders a form: username, password, confirm password
4. On submit:
   - Validate password confirmation matches
   - Bcrypt hash the password
   - Generate 32-character hex API key via `secrets.token_hex(16)`
   - Write `[auth]` section to config via existing atomic TOML write
   - Show API key once with copy button
   - Redirect to `/login`
5. `/setup` returns 404 after auth is configured (one-time only)

## Login Page

- Route: `GET /login` renders form, `POST /login` validates credentials
- Form fields: username, password
- On success: set signed cookie, redirect to `/` (or `?next=` URL)
- On failure: re-render with error message (htmx partial for consistency)
- Cookie: `triggarr_session`, signed with `itsdangerous.TimestampSigner` using a server-generated secret key, 30-day max age
- Logout: `POST /logout` clears cookie, redirects to `/login`

### Session Secret

A random session secret is generated on first setup and stored in `triggarr.toml`:

```toml
[auth]
session_secret = "random-64-char-hex"
```

Generated via `secrets.token_hex(32)`. Persists across restarts so sessions survive container recreation.

## Basic Auth Mode

When `method = "Basic"`:
- Middleware sends `WWW-Authenticate: Basic realm="Triggarr"` on 401
- Browser shows native credential popup
- Same username/password_hash, different UX (no login page)
- Session cookie still set after successful Basic auth to avoid re-prompting

## External Auth Mode

When `method = "External"`:
- Middleware passes all requests through (auth delegated to reverse proxy)
- API key still active for programmatic access
- No login page, no session cookies
- Startup logs: `"Auth method: External — trusting reverse proxy for authentication"`

## Disabled Mode

When `method = "Disabled"`:
- Middleware passes all requests through
- Startup logs a warning every 60 seconds: `"Authentication is DISABLED — all endpoints are accessible without credentials"`
- Settings UI shows a red warning banner
- Can only be set via config file edit, not via Settings UI (deliberate friction)

## API Key

- 32-character hex token (`secrets.token_hex(16)`)
- Generated at first-run setup
- Accepted via `X-Api-Key` request header (matches *arr convention)
- Works in all auth modes (even External/Disabled, for tooling consistency)
- Regenerable from Settings page (POST endpoint writes new key to config)

## Health Endpoint

- `GET /health` -> `{"status": "ok"}` (200)
- Always unauthenticated, regardless of auth mode
- Used by uptime monitors (Uptime Kuma, Gatus, etc.)

## Exempt Paths (Middleware Whitelist)

```python
EXEMPT_PREFIXES = (
    "/health",
    "/static",
    "/login",
    "/setup",
)
```

All other paths require authentication.

## Settings UI

New "Security" section on the Settings page:

- **Auth method** dropdown: Forms / Basic / External (no Disabled option — config file only)
- **Change password** form: current password, new password, confirm
- **API key** display (masked by default) with copy and regenerate buttons
- **Warning banner** if method is Disabled (shown if set via config file)

## Login Page Design

Follows Triggarr's existing dark theme:
- Centered card on dark background
- Triggarr logo/name at top
- Username and password fields with existing input styles
- "Sign In" button with existing button styles
- Error message area for invalid credentials
- Minimal — no "forgot password", no "remember me" (single-user app)

## Setup Page Design

Same centered card approach:
- "Welcome to Triggarr" heading
- Username field (pre-filled with "admin")
- Password + Confirm password fields
- "Create Account" button
- After submit: success card showing the generated API key with copy button and "Continue to Login" link

## Nav Changes

- Add "Logout" link to nav bar (right side) when authenticated
- Show username in nav when in Forms/Basic mode

## Dependencies

| Package | Purpose | Size |
|---------|---------|------|
| `bcrypt` | Password hashing | ~30KB, no transitive deps |

`itsdangerous` is already available via Starlette.

## Files to Create/Modify

### New Files
- `triggarr/middleware/auth.py` — AuthMiddleware class
- `triggarr/auth.py` — password hashing, cookie signing, API key validation helpers
- `triggarr/templates/login.html` — login page template
- `triggarr/templates/setup.html` — first-run setup template
- `tests/test_auth.py` — auth middleware, login, setup, API key tests

### Modified Files
- `triggarr/models/config.py` — add `AuthConfig` model and `auth` field to `Settings`
- `triggarr/__main__.py` — add `AuthMiddleware` to middleware stack
- `triggarr/web/routes.py` — add `/login`, `/logout`, `/setup`, `/health` routes; add auth settings endpoints
- `triggarr/templates/base.html` — add logout link to nav
- `triggarr/templates/settings.html` — add Security section
- `triggarr/startup.py` — add auth status to startup log
- `pyproject.toml` — add `bcrypt` dependency

## Error Handling

- Invalid credentials: re-render login with "Invalid username or password" (no timing oracle — bcrypt is constant-time)
- Expired cookie: redirect to login (cookie max_age handles this)
- Invalid API key: 401 JSON response
- Setup with auth already configured: 404
- Password change with wrong current password: error message, no change

## Security Considerations

- Bcrypt with default work factor (12 rounds) for password hashing
- `secrets.token_hex` for API key and session secret generation (CSPRNG)
- Cookie signed with HMAC (itsdangerous) — tamper-proof
- Cookie set with `httponly=True`, `samesite=Lax`, `secure=True` when behind HTTPS
- No plaintext passwords stored anywhere
- Rate limiting not included in v1 — reverse proxy can handle this (documented)
- CSRF protection already exists via OriginCheckMiddleware
