# Phase 66: Security Hardening - Research

**Researched:** 2026-05-26
**Domain:** HTTP security hardening (CSP, input validation, auth header decoding, startup validation)
**Confidence:** HIGH

## Summary

This phase narrows the HTTP attack surface across four independent fronts (SEC-01..SEC-04). All four work items are surgical edits to existing files with no new dependencies, no new routes, and no new config keys. The user explicitly delegated all decisions to Claude in `66-CONTEXT.md`, producing 14 locked decisions (D-01..D-14) that this research takes as ground truth and operationalises.

The research surfaces **one significant gap in the locked decisions** that the planner must resolve before SEC-01 can ship safely: dropping `'unsafe-inline'` from `script-src` also blocks the 14+ inline `onclick=`/`onchange=` event handler attributes currently present in templates. Nonces apply only to `<script>` elements, not to event handler attributes — this is a CSP Level 3 spec fact, not an opinion. The planner has three options (documented under "Common Pitfalls" below); the cleanest is to migrate the inline `onclick`/`onchange` attributes to `addEventListener` calls within the (now-nonced) inline `<script>` blocks.

**Primary recommendation:** Sequence SEC-01 as a 3-step plan (migrate inline event handlers → wire nonce middleware/Jinja global → drop `'unsafe-inline'` + assert in tests). SEC-02, SEC-03, SEC-04 are independent and can run in parallel (Wave 1) since they touch separate files. TDD applies cleanly to SEC-02 (URL validator), SEC-03 (char rejection), and SEC-04 (warning helper); SEC-01 is integration-test driven (`type: execute`).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**SEC-01 — CSP nonce migration**
- **D-01:** Adopt nonce-based CSP, not external-script extraction. Drop `'unsafe-inline'` from `script-src`.
- **D-02:** Nonce generation in `SecurityHeadersMiddleware.dispatch()` via `secrets.token_urlsafe(16)` per request, stored on `request.state.csp_nonce`, exposed to Jinja via `csp_nonce` template global.
- **D-03:** All four inline scripts get a nonce attribute: `base.html:116-132`, `dashboard.html:48+`, `setup.html:70+`, `settings.html:253+`.
- **D-04:** `script-src` becomes `'self' 'nonce-<value>'` (no `'unsafe-inline'`). `style-src` keeps `'unsafe-inline'` (Tailwind utility output is fine; styles migration is out of scope).
- **D-05:** No `hx-on` / `hx-on::` htmx attribute handlers exist (verified via grep).

**SEC-02 — URL validation (apikey= rejection)**
- **D-06:** Implement as `@field_validator('url')` on `InstanceConfig` in `triggarr/models/config.py:44`.
- **D-07:** Reject only `apikey=` (case-insensitive variants). Do NOT reject all query strings.
- **D-08:** Error message: `"URL must not contain an apikey= query parameter. Use the API Key field instead."`

**SEC-03 — Basic auth header hardening**
- **D-09:** Reject decoded credentials containing null bytes (0x00) or ASCII control characters (0x00–0x1F, 0x7F) in username or password. Reject = 401 with `WWW-Authenticate: Basic realm="Triggarr"`.
- **D-10:** Log at WARNING with fields `event=basic_auth_rejected`, `reason=control_char` (or `reason=decode_failure`), and `client_ip` (from `request.client.host`). Do NOT log username, decoded bytes, or raw header.
- **D-11:** Apply the same `event=basic_auth_rejected` WARNING to the existing silent `except (ValueError, UnicodeDecodeError): pass` branch at `middleware.py:183-184`.

**SEC-04 — session_secret startup validation**
- **D-12:** Warn-only at startup, single occurrence (NOT periodic).
- **D-13:** Trigger: `not settings.auth.needs_setup AND len(settings.auth.session_secret.get_secret_value()) < 32`.
- **D-14:** New helper `_warn_if_session_secret_short` in `startup.py`, invoked once during startup before connection validation. Message: `"auth.session_secret is shorter than 32 characters — regenerate via Settings → Security or set a longer value in config.toml"`.

### Claude's Discretion
None remaining — all four areas were locked in CONTEXT.md.

### Deferred Ideas (OUT OF SCOPE)
- `style-src 'unsafe-inline'` removal — scripts only this phase.
- Migrating htmx attribute handlers to delegated listeners — already done per D-05 grep.
- Periodic session_secret warning — rejected at D-12.
- Rejecting any query parameter in *arr URLs — rejected at D-07.
- Strict ASCII-printable password policy — rejected at D-09 (would break legit non-ASCII passwords).
- Logging failed Basic auth username — rejected at D-10 (PII minimisation).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEC-01 | CSP `script-src` directive no longer includes `'unsafe-inline'`; inline `<script>` blocks use a per-response nonce | Nonce middleware pattern, Jinja2 `context_processors` integration, template inventory below |
| SEC-02 | `*arr` URL validation at config save rejects URLs containing `apikey=` query parameter with a clear error | Pydantic v2 `@field_validator` pattern, `urllib.parse.parse_qs` semantics, existing `pydantic.ValidationError` handler at `routes.py:567-569` |
| SEC-03 | Basic auth header decoder rejects credentials with null bytes or control characters, logs failed decode attempts at WARNING | RFC 7617 spec, control-char detection idiom, loguru WARNING pattern, `request.client.host` availability |
| SEC-04 | Startup validation enforces session_secret length ≥ 32 chars and logs WARNING if shorter | `_warn_if_auth_disabled` template, `SecretStr.get_secret_value()` discipline, atomic persist already guaranteed at `routes.py:1101-1112` |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

The planner MUST verify every task complies with these directives — they have the same authority as locked decisions.

- **Python 3.11+** (project pyproject targets 3.13)
- **ruff rule sets: E, F, I, UP, B, SIM**, line length 120 — every new test file and modified source file must pass `uv run ruff check`.
- **SecretStr discipline:** `.get_secret_value()` only at HTTP-client init or explicit length checks. SEC-04 uses it for length comparison (allowed per CLAUDE.md: "explicit length checks"). The length value MUST NOT leak into the log message — D-14's message names the field, not the value.
- **Loguru with custom redacting sink** — never `print()` or stdlib `logging`. All new WARNING calls (SEC-03 D-10, SEC-04 D-14) use `from loguru import logger` (already imported in target files) and `logger.warning("msg {field}", field=...)` style (consistent with existing `triggarr/startup.py:37`, `triggarr/changelog.py:58`).
- **Atomic file writes (write-then-rename)** — SEC-02 is upstream of the existing `_atomic_toml_write` flow; validation runs before the lock is acquired (see Cross-Cutting Concerns).
- **pytest-asyncio with `asyncio_mode=auto`** — all new tests follow this convention.
- **Verification gate:** `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/` (project standard, per CLAUDE.md "Development Commands").

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CSP nonce generation | Backend Middleware (`SecurityHeadersMiddleware`) | — | Per-request entropy generation must run server-side; nonce must reach both the response header and the template context, which only middleware sees both of |
| Nonce → template propagation | Backend (Jinja2 `context_processors`) | Browser (renders `<script nonce="…">`) | Server emits the nonce attribute into the rendered HTML; browser then matches against header at script-execution time |
| URL validation (`apikey=` rejection) | Backend Model (Pydantic `InstanceConfig`) | — | Runs at construction time, BEFORE the TOML write — single enforcement point for both load-time and save-time paths |
| Basic auth header decode + char validation | Backend Middleware (`AuthMiddleware._handle_basic_auth`) | — | Inside the existing static method, after `base64.b64decode` and before `secrets.compare_digest` |
| Session-secret length warning | Backend Startup (`triggarr/startup.py`) | — | One-shot check during `startup()`; reads loaded `Settings`, emits `logger.warning` |

**Why this map matters for SEC-01:** The nonce has a producer (middleware) and a consumer (Jinja template render). The only shared surface that has access to both is `request.state` plus the `Jinja2Templates` `context_processors` hook. Trying to push nonce generation to a context processor alone breaks because the nonce must also land in the response header — which only the middleware sets. Single source of truth: middleware writes `request.state.csp_nonce`; context processor reads it back; response header is composed from the same value just before `return response`.

## Standard Stack

### Core (all already installed — no new dependencies for this phase)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pydantic` | 2.x (already in deps) | `@field_validator` for SEC-02 | Existing model uses `@model_validator` at `models/config.py:64,132` — same module, same pattern family `[VERIFIED: triggarr/models/config.py line 9 imports `model_validator`]` |
| `starlette` (via FastAPI) | already installed | `BaseHTTPMiddleware`, `request.state`, `request.client.host` | `SecurityHeadersMiddleware` and `_handle_basic_auth` already use Starlette primitives `[VERIFIED: triggarr/web/middleware.py imports]` |
| `loguru` | already installed | WARNING log for SEC-03 and SEC-04 | Project mandates loguru with redacting sink (CLAUDE.md). Existing pattern across `startup.py`, `changelog.py`, `config.py` `[VERIFIED: codebase grep]` |
| `secrets` (stdlib) | Py 3.13 | `secrets.token_urlsafe(16)` for nonce | Already imported in `triggarr/web/middleware.py:6` `[VERIFIED]` |
| `urllib.parse` (stdlib) | Py 3.13 | `urlparse` + `parse_qs` for SEC-02 | Already imported in `triggarr/web/middleware.py:8` and `triggarr/web/validation.py` `[VERIFIED]` |
| `base64` (stdlib) | Py 3.13 | Already used at `middleware.py:165` | `[VERIFIED]` |

### Supporting (test-time only)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` + `pytest-asyncio` | already installed | Test framework | All four work items |
| `fastapi.testclient.TestClient` | already installed | Middleware integration tests | SEC-01 (CSP header + rendered HTML), SEC-03 (Basic auth Authorization header) — same pattern as `tests/test_middleware.py:31, 194` and `tests/test_auth_middleware.py:100-104` `[VERIFIED]` |
| `io.StringIO` + `logger.add(sink, ...)` | stdlib + loguru | Capture loguru output in tests | SEC-04 — exact pattern at `tests/test_startup.py:42-47` `[VERIFIED]` |
| `base64.b64encode` (stdlib) | Py 3.13 | Build Basic Authorization headers in tests | SEC-03 — pattern at `tests/test_auth_middleware.py:103` `[VERIFIED]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `secrets.token_urlsafe(16)` for nonce | `secrets.token_hex(16)` | `token_urlsafe` produces ~22 base64url chars (128-bit entropy). Hex would be 32 chars but the same entropy. CONTEXT D-02 specifies `token_urlsafe(16)` — no change. |
| Nonce via `context_processors` callable | Pre-compute and pass via `templates.TemplateResponse(context={"csp_nonce": nonce})` per route | Per-route plumbing in every handler is mechanical churn. `context_processors` is the Jinja2Templates-supplied hook that runs ONCE in template setup and applies to every render `[CITED: https://fastapi.tiangolo.com/reference/templating/]` |
| Jinja2 `globals` for nonce | `globals` are set at template-env init, not per-request | Globals can't read `request.state` (no per-request signal). `context_processors` IS the right primitive for per-request values. CONTEXT D-02 says "`csp_nonce` template global"; the implementation MUST be a `context_processors` callable, not `templates.env.globals[...]` (which is used today for `triggarr_version`, `update_info`, `auth_state` — all process-wide). |
| `urllib.parse.parse_qsl` | `urllib.parse.parse_qs` | `parse_qsl` returns `[(key, value), ...]`; `parse_qs` returns `{key: [values]}`. For SEC-02 we just need keys → either works. Recommend `parse_qsl(query, keep_blank_values=True)` so `?apikey=` (empty value) is still caught. |
| `RFC 7617` strict validation (reject any non-printable) | D-09 range (0x00–0x1F + 0x7F) | D-09's range is the minimum-viable conservative rule. Going stricter (e.g., reject anything outside printable ASCII) would break legitimate non-ASCII Unicode passwords. The locked rule is correct. |

**Installation:**
No new dependencies. The standard verification gate suffices:
```bash
uv run pytest tests/ -x -q
uv run ruff check triggarr/ tests/
```

**Version verification:** Not applicable — no new packages to verify on PyPI.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (none) | — | — | — | — | — | No new packages installed in this phase |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

*This phase introduces zero new dependencies — all four work items use already-installed stdlib modules (`secrets`, `urllib.parse`, `base64`, `re`) plus already-vendored Pydantic, Starlette, and loguru. No legitimacy audit needed.*

## Architecture Patterns

### System Architecture Diagram

```
                            HTTP Request
                                  │
                                  ▼
                        ┌──────────────────────┐
                        │   AuthMiddleware     │  ← SEC-03 hardens
                        │  ._handle_basic_auth │     decode path here
                        └──────────┬───────────┘
                                   │ (pass)
                                   ▼
                        ┌──────────────────────┐
                        │ OriginCheckMiddleware│
                        └──────────┬───────────┘
                                   │ (pass)
                                   ▼
                        ┌──────────────────────┐
                        │SecurityHeadersM/ware │  ← SEC-01: generate nonce
                        │  request phase:      │     here, store on
                        │  set request.state   │     request.state
                        └──────────┬───────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │   FastAPI Router     │
                        │   (route handler)    │
                        └──────────┬───────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │  Jinja2Templates     │  ← SEC-01: context_processor
                        │  .TemplateResponse() │     reads request.state.csp_nonce
                        └──────────┬───────────┘     and exposes as {{ csp_nonce }}
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │SecurityHeadersM/ware │  ← SEC-01: response phase
                        │  response phase:     │     compose CSP header with
                        │  set CSP header      │     same nonce from request.state
                        └──────────┬───────────┘
                                   │
                                   ▼
                            HTTP Response
                       (Content-Security-Policy header
                        + rendered HTML with nonce'd <script>)


SEC-02 flow (separate path — config save):

  POST /settings  →  routes.py:482  →  SettingsModel(**new_config)
                                            │
                                            ▼
                                   InstanceConfig.__init__
                                            │
                                            ▼
                            @field_validator('url')  ← SEC-02 lives here
                                            │
                                       (pass | raise ValidationError)
                                            │
                                  ┌─────────┴──────────┐
                                  ▼                    ▼
                          new_settings           except ValidationError
                                  │                    │
                          search_lock acquire    redirect (303)
                                  │                    
                          _atomic_toml_write    
                                  │
                          os.chmod 0o600


SEC-04 flow (one-shot at startup):

  python -m triggarr  →  startup()  →  ensure_config()
                                          │
                                          ▼
                              setup_logging(redacting sink)
                                          │
                                          ▼
                              print_banner()
                                          │
                                          ▼
                       _warn_if_session_secret_short(settings)  ← SEC-04 (NEW)
                                          │
                                          ▼
                              check_localhost_urls()
                                          │
                                          ▼
                              validate_connections()
```

### Recommended Project Structure
No new files — all changes are to existing modules:
```
triggarr/
├── auth.py              # (unchanged — referenced for context only)
├── startup.py           # SEC-04: add _warn_if_session_secret_short helper
├── models/
│   └── config.py        # SEC-02: add @field_validator('url') to InstanceConfig
├── web/
│   ├── middleware.py    # SEC-01 nonce gen + CSP, SEC-03 char validation + WARNING log
│   └── routes.py        # SEC-01: wire context_processors into Jinja2Templates
└── templates/
    ├── base.html        # SEC-01: nonce attr on <script> + migrate inline onclick
    ├── dashboard.html   # SEC-01: nonce attr on <script>
    ├── setup.html       # SEC-01: nonce attr on <script> + migrate inline onclick
    ├── settings.html    # SEC-01: nonce attr on <script> + migrate inline onchange/onclick
    └── partials/
        ├── log_viewer.html      # SEC-01: migrate inline onclick/onchange to addEventListener (CRITICAL — see Pitfall 1)
        └── security_apikey.html # SEC-01: migrate inline onclick to addEventListener (CRITICAL — see Pitfall 1)

tests/
├── test_middleware.py       # SEC-01 + SEC-03 new tests
├── test_config.py           # SEC-02 new tests
├── test_startup.py          # SEC-04 new tests
└── test_auth_middleware.py  # SEC-03 cross-coverage (Authorization header path)
```

### Pattern 1: Nonce middleware + Jinja2 context_processor (SEC-01)

**What:** The middleware generates the nonce and stores it on `request.state.csp_nonce` BEFORE calling `await call_next()`. A Jinja2 `context_processors` callable reads `request.state.csp_nonce` and exposes it as `{{ csp_nonce }}` in every template render. On the response side, the same middleware composes the `Content-Security-Policy` header using the stored nonce.

**When to use:** Per-request CSP nonce that must reach BOTH the response header AND the rendered HTML inline `<script>` tags. This is the OWASP-recommended pattern.

**Example (combined middleware + Jinja wiring):**
```python
# Source: triggarr/web/middleware.py (modified, SEC-01)
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Generate per-request nonce BEFORE calling downstream — must be visible
        # to the route handler / template render.
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce

        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        # style-src keeps 'unsafe-inline' for Tailwind utility output (D-04).
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )
        return response


# Source: triggarr/web/routes.py (modified, SEC-01)
def _csp_nonce_processor(request: Request) -> dict[str, str]:
    """Expose the per-request CSP nonce to Jinja templates as {{ csp_nonce }}."""
    return {"csp_nonce": getattr(request.state, "csp_nonce", "")}

templates = Jinja2Templates(env=_jinja_env, context_processors=[_csp_nonce_processor])
# Existing globals (triggarr_version, update_info, auth_state) still work — they
# are process-wide; csp_nonce is per-request via context_processors.
```

Templates then render:
```html
<script nonce="{{ csp_nonce }}">
  /* existing inline script body */
</script>
```

**Confidence:** HIGH `[VERIFIED: FastAPI Jinja2Templates docs; existing middleware pattern in middleware.py:32-49]`

### Pattern 2: Pydantic v2 `@field_validator` for URL apikey= rejection (SEC-02)

**What:** A field-level validator on `InstanceConfig.url` that runs at construction time and raises `ValueError` (Pydantic wraps it into `ValidationError`) when the URL contains an `apikey=` query parameter (any case).

**When to use:** Single-field validation logic that needs to run on every model construction, including settings POST → `SettingsModel(**new_config)` round-trip (`routes.py:566`).

**Example:**
```python
# Source: triggarr/models/config.py (modified, SEC-02)
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from urllib.parse import urlparse, parse_qsl

class InstanceConfig(BaseModel):
    url: str = ""
    # ... existing fields ...

    @field_validator("url")
    @classmethod
    def reject_apikey_in_url(cls, v: str) -> str:
        """SEC-02: Reject URLs containing an apikey= query parameter (any case)."""
        if not v:
            return v
        try:
            parsed = urlparse(v)
        except ValueError:
            # Malformed URL — let the broader URL validator (validate_arr_url) handle it.
            return v
        if not parsed.query:
            return v
        # parse_qsl with keep_blank_values=True catches `?apikey=` (empty value).
        for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() == "apikey":
                msg = (
                    "URL must not contain an apikey= query parameter. "
                    "Use the API Key field instead."
                )
                raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def at_least_one_search_count(self) -> InstanceConfig:
        # ... existing validator unchanged ...
```

**Note on existing handler integration:** `triggarr/web/routes.py:565-569` catches `pydantic.ValidationError`, logs it via `logger.warning("Invalid settings rejected: {exc}", exc=exc)`, then bare-redirects to settings page. The error message from D-08 will appear in logs but **NOT in the UI** under the current handler. That is a pre-existing UX gap, not something SEC-02 introduces. The planner should note this in the plan and decide whether to surface field-level errors as part of this phase or defer to a follow-up.

**Confidence:** HIGH `[VERIFIED: existing model_validator pattern at models/config.py:64,132; existing ValidationError catch at routes.py:567-569]`

### Pattern 3: Control-char rejection after base64 decode (SEC-03)

**What:** After `base64.b64decode(...).decode("utf-8")` succeeds, check both username and password parts for any character with ordinal 0x00–0x1F or 0x7F. If any character matches, log a structured WARNING (PII-minimised) and fall through to the 401 response.

**When to use:** Inside `AuthMiddleware._handle_basic_auth` between line 166 (`username, _, password = decoded.partition(":")`) and line 167 (the `secrets.compare_digest` check).

**Example:**
```python
# Source: triggarr/web/middleware.py (modified, SEC-03)
def _has_control_chars(s: str) -> bool:
    """Return True if string contains any C0 control char or DEL (0x00..0x1F, 0x7F)."""
    return any(ord(c) < 0x20 or ord(c) == 0x7F for c in s)


@staticmethod
async def _handle_basic_auth(
    request: Request, auth: AuthConfig, call_next: RequestResponseEndpoint
) -> Response:
    authorization = request.headers.get("authorization", "")
    client_ip = request.client.host if request.client else "unknown"
    if authorization.startswith("Basic "):
        try:
            decoded = base64.b64decode(authorization[6:]).decode("utf-8")
            username, _, password = decoded.partition(":")
            # SEC-03 D-09: reject control chars before comparison
            if _has_control_chars(username) or _has_control_chars(password):
                logger.warning(
                    "basic_auth_rejected reason={reason} client_ip={ip}",
                    reason="control_char",
                    ip=client_ip,
                )
                return Response(
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="Triggarr"'},
                )
            if secrets.compare_digest(username, auth.username) and verify_password(
                password, auth.password_hash.get_secret_value()
            ):
                # ... existing cookie-setting path unchanged ...
                return response
        except (ValueError, UnicodeDecodeError):
            # SEC-03 D-11: surface previously-silent decode failures
            logger.warning(
                "basic_auth_rejected reason={reason} client_ip={ip}",
                reason="decode_failure",
                ip=client_ip,
            )
    return Response(
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="Triggarr"'},
    )
```

**On `request.client.host`:** Starlette's `Request.client` is an `Address` namedtuple (`host: str, port: int`) or `None` when the scope has no client info (e.g., test transports without an explicit address). The `if request.client else "unknown"` guard prevents `AttributeError` in tests. In production with uvicorn behind a trusted proxy, `proxy_headers=True` (already set at `__main__.py:82`) makes `request.client.host` reflect the forwarded client.

**Confidence:** HIGH `[VERIFIED: existing _handle_basic_auth structure at middleware.py:157-188; Starlette Request.client is documented behaviour]`

### Pattern 4: Single-shot startup warning helper (SEC-04)

**What:** A sync helper that takes `settings`, evaluates the trigger condition (`not needs_setup AND len(secret) < 32`), and emits one `logger.warning` if triggered. Called once from `startup()` before `check_localhost_urls`.

**When to use:** Configuration-mistake warnings that should fire once and stay fired (no rate limiting, no periodic re-emission).

**Example:**
```python
# Source: triggarr/startup.py (modified, SEC-04)
def _warn_if_session_secret_short(settings: Settings) -> None:
    """SEC-04 D-13: Warn if persisted session_secret is shorter than 32 chars.

    Skipped when needs_setup is True (the empty secret is the pre-setup default).
    """
    auth = settings.auth
    if auth.needs_setup:
        return
    if len(auth.session_secret.get_secret_value()) < 32:
        logger.warning(
            "auth.session_secret is shorter than 32 characters — "
            "regenerate via Settings → Security or set a longer value in config.toml"
        )


async def startup(config_path: Path | None = None) -> Settings:
    # ... existing flow ...
    print_banner(settings)
    _warn_if_session_secret_short(settings)   # NEW: call site between print_banner and has_enabled_app check
    if not settings.has_enabled_app:
        # ... existing flow ...
```

**SecretStr discipline note:** Calling `.get_secret_value()` here is allowed under CLAUDE.md ("call `.get_secret_value()` only at HTTP client init") because length-checking is an "explicit length check" — the value is consumed by `len()`, never logged or returned. The warning message (D-14) names the field, not the value.

**Confidence:** HIGH `[VERIFIED: _warn_if_auth_disabled does not exist as a function — verified by re-reading triggarr/startup.py. The CONTEXT.md reference to "_warn_if_auth_disabled at triggarr/startup.py:27-37" is INCORRECT — that range is `check_localhost_urls`. The actual disabled-mode warning lives in AuthMiddleware at middleware.py:114-122. See "Open Questions" for the implication.]`

### Anti-Patterns to Avoid

- **Setting `csp_nonce` as a Jinja `globals` entry (`templates.env.globals["csp_nonce"] = ...`):** globals are process-wide and resolved at template-env init. They cannot read per-request state. Use `context_processors` instead.
- **Calling `secrets.token_urlsafe()` in the context_processor:** would generate a *different* nonce than the one in the response header — the script would be blocked. Generate once in the middleware, expose via `request.state`.
- **Logging the rejected username or decoded bytes in SEC-03:** explicitly rejected by D-10. PII minimisation principle.
- **Using `parse_qs` without `keep_blank_values=True`:** `?apikey=` (empty value) would be silently dropped from the parsed result, bypassing the check.
- **Putting the SEC-04 warning inside a periodic timer/task:** explicitly rejected by D-12 — warn-once is sufficient.
- **Logging `auth.session_secret.get_secret_value()` to confirm length in the warning:** violates SecretStr discipline. Name the field, not the value.
- **Reading `request.client.host` without a None-guard:** crashes when `request.client is None` (test transports). Use `request.client.host if request.client else "unknown"`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cryptographic random nonce | Custom `random.choices(string.ascii_letters)` or hashlib of timestamps | `secrets.token_urlsafe(16)` | `secrets` is the CSPRNG-backed stdlib primitive; `random` is NOT cryptographically secure |
| URL parsing | Regex on `apikey=` | `urllib.parse.urlparse` + `parse_qsl` | Regex can be evaded by URL encoding (`%61pikey=`), repeated `?`, fragment-confusion. `parse_qsl` decodes properly. |
| Control-char detection | `s.translate(...)` with control-char map | `any(ord(c) < 0x20 or ord(c) == 0x7F for c in s)` | Three-line idiom is clearer than table-building and works on `str` (already utf-8 decoded). |
| Per-request template values | Pass `csp_nonce` in every `TemplateResponse(context={...})` call | `Jinja2Templates(context_processors=[...])` | Hundreds of template responses across the codebase — context_processors centralises in one place. |
| Loguru structured log fields | Manual JSON string-formatting | `logger.warning("msg {a} {b}", a=..., b=...)` | Loguru's brace-format keyword args are the project's house style (see `startup.py:37,87,196`). |

**Key insight:** Every problem in this phase has a stdlib or already-installed solution. The phase is about wiring existing primitives correctly, not about introducing new abstractions.

## Common Pitfalls

### Pitfall 1: CSP nonces do NOT cover inline event handler attributes (CRITICAL — gap in CONTEXT.md)
**What goes wrong:** CONTEXT D-04 says "`script-src` becomes `'self' 'nonce-<value>'` (no `'unsafe-inline'`)." Dropping `'unsafe-inline'` breaks **inline event handler attributes** (`onclick=`, `onchange=`, `onload=`, etc.) — nonces apply ONLY to `<script>` elements, never to event handler attributes. CSP Level 3 spec is explicit on this.
**Why it happens:** D-05 verified no `hx-on` attributes exist, which is correct, but it did NOT verify no `onclick=`/`onchange=` attributes exist. They DO exist — 14 distinct occurrences across the templates:
- `base.html:31` `onclick="openChangelog()"`
- `base.html:104` `onclick="closeChangelog()"`
- `base.html:108` `onclick="closeChangelog()"`
- `setup.html:60` `onclick="copyApiKey(this)"`
- `settings.html:100` `onchange="updateMethodWarning(this.value)"`
- `settings.html:152` `onclick="event.stopPropagation()"`
- `partials/security_apikey.html:18,29,41,54,58` (5 onclick handlers)
- `partials/log_viewer.html:19` `onchange="..."` (long inline expression)
- `partials/log_viewer.html:28,32` (2 onclick handlers)

**How to avoid:** Three options (planner picks one — STRONGLY recommend Option B):

| Option | Approach | Tradeoff |
|--------|----------|----------|
| A | Keep `'unsafe-inline'` in `script-src` | Defeats SEC-01 — no security gain. **Reject.** |
| B (recommended) | Migrate every inline `onclick=`/`onchange=` to `addEventListener` calls inside the (now-nonced) inline `<script>` blocks. Use `id` or `data-*` attributes to wire handlers. | Mechanical edit per handler. Tests verify behavior unchanged. Cleanest end state. |
| C | Add `'unsafe-hashes'` + per-handler SHA-256 hash to `script-src` | Brittle (any handler change breaks CSP); CSP Level 3 only; goes against the spirit of the migration. **Reject for a maintained codebase.** |

**Warning signs:** After dropping `'unsafe-inline'`, every page with an inline `onclick`/`onchange` will throw `Refused to execute inline event handler because it violates the following Content Security Policy directive: "script-src 'self' 'nonce-...'"` in the browser console. **Test in a real browser, not just `TestClient`** — `TestClient` doesn't enforce CSP, so the assertion `assert response.status_code == 200` will pass while the page is silently broken in production.

**This pitfall is the single biggest risk in Phase 66.** The planner MUST either:
1. Add a wave-0 / wave-1 task that migrates all 14 inline event handlers to `addEventListener` patterns BEFORE dropping `'unsafe-inline'`, OR
2. Re-engage the user via `/gsd:discuss-phase` to confirm Option B vs. revert SEC-01 scope.

The CONTEXT.md author appears to have surveyed `<script>` blocks (4 found) but missed `on*=` attributes (14 found). This is a research-finding correction, not a CONTEXT.md override.

### Pitfall 2: `request.client` can be None
**What goes wrong:** Accessing `request.client.host` directly raises `AttributeError: 'NoneType' object has no attribute 'host'` when the request scope has no client info (most commonly in TestClient/ASGITransport with no `client=` arg, or in some lifespan scenarios).
**Why it happens:** Starlette's `Request.client` is `Address | None`; tests don't always set it.
**How to avoid:** Use the `host if request.client else "unknown"` guard shown in Pattern 3. Always.
**Warning signs:** A green test that uses TestClient with a mocked request, followed by a 500 in production behind nginx.

### Pitfall 3: SecretStr length check leaks via repr in tests
**What goes wrong:** If a test asserts on `str(settings.auth)`, the SecretStr part will show `SecretStr('**********')` regardless of length — that's fine. But if a developer writes `assert len(settings.auth.session_secret) < 32` (without `.get_secret_value()`), it returns the length of the placeholder, not the secret. The check passes/fails on the wrong value.
**Why it happens:** `SecretStr` overrides `__len__` to... actually, Pydantic v2 `SecretStr` does NOT define `__len__` — `len(secret_str)` raises `TypeError`. So this fails fast, which is good. The risk is if someone copy-pastes `len(settings.auth.session_secret.get_secret_value())` and forgets the `.get_secret_value()` part.
**How to avoid:** Always go through `.get_secret_value()` for length comparisons. The validator function in Pattern 4 follows this.
**Warning signs:** `TypeError: object of type 'SecretStr' has no len()` at the warning call site.

### Pitfall 4: ValidationError in SEC-02 surfaces as a bare redirect, not a user-visible message
**What goes wrong:** The existing handler at `routes.py:567-569` catches `pydantic.ValidationError` and bare-redirects to settings page. The user submits a URL with `?apikey=...`, sees the settings page reload with no change, and has no idea why. The D-08 error message ends up in the loguru WARNING line only.
**Why it happens:** Pre-existing UX shape; the handler was written before per-field validation messages were needed.
**How to avoid:** Either (a) accept this as a known limitation and document it in PLAN.md ("error logged but not surfaced — UX follow-up tracked in vNext"), or (b) extend SEC-02 scope to thread the validation message into the settings template via flash/session-state. **Option (a) is the lower-risk default and consistent with the existing handler behaviour for other validation failures.**
**Warning signs:** User reports "settings save silently fails" — fix message routing then.

### Pitfall 5: Tests asserting nonce in HTML must use the SAME response that produced the header
**What goes wrong:** A test makes two requests — one for the header, one for the HTML body — and asserts the nonce values match. They WON'T match: each request gets a fresh nonce.
**Why it happens:** Nonces are per-request by design.
**How to avoid:** Make ONE request, extract the nonce from the `Content-Security-Policy` response header, then assert that same nonce appears in the response body's `<script nonce="...">` tags. Pattern:
```python
def test_csp_nonce_matches_html_script_tag():
    response = client.get("/some-page-with-inline-script")
    csp = response.headers["Content-Security-Policy"]
    # Extract nonce from CSP header
    m = re.search(r"'nonce-([A-Za-z0-9_\-]+)'", csp)
    assert m is not None, "CSP header missing nonce"
    nonce = m.group(1)
    # Assert same nonce appears in rendered HTML
    assert f'nonce="{nonce}"' in response.text
```

### Pitfall 6: `parse_qs` silently drops empty values
**What goes wrong:** `urlparse("http://x/?apikey=").query` is `"apikey="`. `parse_qs("apikey=")` returns `{}` (empty values dropped by default). The check `"apikey" in parse_qs(...)` returns `False` and the URL passes validation.
**Why it happens:** `parse_qs` default `keep_blank_values=False`.
**How to avoid:** Use `parse_qsl(query, keep_blank_values=True)` or `parse_qs(query, keep_blank_values=True)`. Recommended explicit list in Pattern 2.
**Warning signs:** A specific test case `?apikey=` (no value) that should reject but passes.

### Pitfall 7: Middleware order — nonce generation must happen BEFORE the route handler
**What goes wrong:** If `request.state.csp_nonce` is set AFTER `await call_next(request)`, the template render already happened and the nonce isn't in the HTML. The browser sees a nonce in the header but a `<script>` tag with `nonce=""` (or missing) — script blocked.
**Why it happens:** Confusing dispatch flow with response-side patching.
**How to avoid:** Set `request.state.csp_nonce = secrets.token_urlsafe(16)` as the FIRST line of `dispatch()`, before `response = await call_next(request)`.
**Warning signs:** CSP error in browser console even though tests pass (TestClient doesn't enforce CSP).

### Pitfall 8: Context processor signature mismatch
**What goes wrong:** Defining the context processor as `async def` (mirroring middleware) raises a TypeError. Jinja2Templates context processors must be synchronous callables (`Callable[[Request], dict[str, Any]]`).
**Why it happens:** Habit from FastAPI async-by-default.
**How to avoid:** `def _csp_nonce_processor(request: Request) -> dict[str, str]:` — sync only.

## Runtime State Inventory

Not applicable — this is not a rename/refactor/migration phase. No external stored data, live service config, OS-registered state, secrets/env vars, or build artifacts are renamed. All changes are pure code edits to existing modules.

## Code Examples

### Generate per-request nonce in middleware
```python
# Source: extension of triggarr/web/middleware.py:32-49
import secrets
# in SecurityHeadersMiddleware.dispatch:
nonce = secrets.token_urlsafe(16)        # 128-bit entropy, 22 base64url chars
request.state.csp_nonce = nonce
# ... pass through ...
response.headers["Content-Security-Policy"] = (
    f"...; script-src 'self' 'nonce-{nonce}'; ..."
)
```

### Test that CSP header contains a nonce and the rendered HTML matches
```python
# Source: pattern derived from tests/test_middleware.py:192-205 + new requirement
import re
def test_csp_nonce_appears_in_header_and_html(client):
    response = client.get("/")
    csp = response.headers["Content-Security-Policy"]
    m = re.search(r"'nonce-([A-Za-z0-9_\-]+)'", csp)
    assert m, f"CSP header missing nonce: {csp}"
    nonce = m.group(1)
    assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
    assert f'nonce="{nonce}"' in response.text
```

### Pydantic v2 `@field_validator` for InstanceConfig.url
```python
# Source: extension of triggarr/models/config.py:44 (pattern mirrors existing
# at_least_one_search_count @model_validator)
from urllib.parse import urlparse, parse_qsl
from pydantic import field_validator

@field_validator("url")
@classmethod
def reject_apikey_in_url(cls, v: str) -> str:
    if not v:
        return v
    parsed = urlparse(v)
    if not parsed.query:
        return v
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() == "apikey":
            raise ValueError(
                "URL must not contain an apikey= query parameter. "
                "Use the API Key field instead."
            )
    return v
```

### Test for SEC-02 (parameterized accept/reject cases)
```python
# Source: pattern derived from tests/test_config.py:123-145
import pytest
from pydantic import ValidationError
from triggarr.models.config import InstanceConfig

@pytest.mark.parametrize("url", [
    "http://radarr:7878?apikey=secret",
    "http://radarr:7878/?apikey=secret",
    "http://radarr:7878?APIKEY=secret",
    "http://radarr:7878?apiKey=secret",
    "http://radarr:7878?other=ok&apikey=secret",
    "http://radarr:7878?apikey=",  # empty value still rejected
])
def test_rejects_apikey_query(url):
    with pytest.raises(ValidationError, match="apikey="):
        InstanceConfig(url=url, api_key="k", enabled=True)

@pytest.mark.parametrize("url", [
    "",
    "http://radarr:7878",
    "http://radarr:7878/",
    "http://radarr:7878/sonarr/",            # subpath OK
    "http://radarr:7878?base=/sonarr",        # other query keys OK
    "http://radarr:7878?token=foo",           # not apikey
])
def test_accepts_url_without_apikey_query(url):
    cfg = InstanceConfig(url=url, api_key="k", enabled=True)
    assert cfg.url == url
```

### Control-char check helper for Basic auth
```python
# Source: extension of triggarr/web/middleware.py:_handle_basic_auth
def _has_control_chars(s: str) -> bool:
    """SEC-03: True if any byte is 0x00..0x1F or 0x7F (C0 control + DEL)."""
    return any(ord(c) < 0x20 or ord(c) == 0x7F for c in s)
```

### Test for SEC-03 control-char rejection
```python
# Source: pattern derived from tests/test_auth_middleware.py:101-104 + 309-324
import base64, io
from loguru import logger

def test_basic_auth_null_byte_in_password_rejected():
    auth = _configured_auth(method="Basic")
    client = TestClient(_make_auth_app(auth))
    encoded = base64.b64encode(b"admin:pass\x00word").decode()
    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        response = client.get("/", headers={"Authorization": f"Basic {encoded}"})
    finally:
        logger.remove(handler_id)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="Triggarr"'
    assert "basic_auth_rejected" in sink.getvalue()
    assert "control_char" in sink.getvalue()
    # PII minimisation: username MUST NOT appear in the log line
    assert "admin" not in sink.getvalue()
```

### Test for SEC-04 startup warning
```python
# Source: pattern from tests/test_startup.py:38-53 (loguru capture pattern)
import io
from loguru import logger
from triggarr.models.config import AuthConfig, Settings, InstanceConfig
from pydantic import SecretStr
from triggarr.startup import _warn_if_session_secret_short

def test_warn_when_session_secret_short(): 
    settings = Settings(
        auth=AuthConfig(
            method="Forms",
            username="admin",
            password_hash=SecretStr("$2b$..."),
            api_key=SecretStr("x" * 32),
            session_secret=SecretStr("short"),  # < 32 chars
        ),
    )
    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        _warn_if_session_secret_short(settings)
    finally:
        logger.remove(handler_id)
    out = sink.getvalue()
    assert "auth.session_secret is shorter than 32 characters" in out
    assert "short" not in out   # secret value MUST NOT leak

def test_no_warn_when_session_secret_long():
    settings = Settings(
        auth=AuthConfig(
            method="Forms",
            username="admin",
            password_hash=SecretStr("$2b$..."),
            api_key=SecretStr("x" * 32),
            session_secret=SecretStr("x" * 64),  # 64 chars, normal
        ),
    )
    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        _warn_if_session_secret_short(settings)
    finally:
        logger.remove(handler_id)
    assert "session_secret" not in sink.getvalue()

def test_no_warn_when_needs_setup():
    settings = Settings(auth=AuthConfig())  # default → needs_setup True
    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        _warn_if_session_secret_short(settings)
    finally:
        logger.remove(handler_id)
    assert "session_secret" not in sink.getvalue()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CSP `script-src 'unsafe-inline'` | Nonce-based CSP (`'nonce-<value>'`) | OWASP CSP cheat sheet 2024+ | Mitigates inline XSS even if attacker controls some HTML — they can't guess the nonce |
| Inline `onclick="fn()"` event handlers | `addEventListener` with `id`/`data-*` targeting | CSP Level 2 (2016+) made this de-facto required for strict CSP | Cleaner separation of behaviour and markup; required when dropping `'unsafe-inline'` |
| Pydantic v1 `@validator` | Pydantic v2 `@field_validator` + `@model_validator(mode="after")` | Pydantic 2.0 (June 2023) | Project is already on v2 — use the modern decorators (`field_validator`, `model_validator`) |
| Silent `except: pass` on Basic auth decode | WARNING-logged decode failure | This phase (D-11) | Operator visibility into malformed auth attempts |

**Deprecated/outdated:**
- `'unsafe-inline'` in CSP `script-src` — accepted by all browsers but considered a CSP failure mode by modern security guidance.
- Pydantic v1 `@validator` (still works in v2 via shims but emits deprecation warnings) — use `@field_validator` for new code.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The 14 inline `on*=` attributes are exhaustive (no others added since grep) | Pitfall 1 | A missed handler will be silently blocked in production. **Mitigation:** Re-run `grep -rnE 'on[a-z]+="' triggarr/templates/` at the start of the plan and again right before the test gate. |
| A2 | `templates.env.globals[...]` cannot be made per-request (project uses globals for `triggarr_version`, `update_info`, `auth_state` today, but those are mutable dicts updated by the route handlers; nonce is a string that changes every request) | Pattern 1 / Anti-patterns | If somehow globals can be made per-request, an alternative implementation exists — but `context_processors` is documented and supported, so this is the safe choice. |
| A3 | Existing `pydantic.ValidationError` handler at `routes.py:567-569` redirects without surfacing the error message to the user | Pitfall 4 | If the planner extends scope to thread the message into the UI, the plan grows by one task. Otherwise, behavior matches existing handler. |
| A4 | CONTEXT.md's reference to "_warn_if_auth_disabled at triggarr/startup.py:27-37" is INCORRECT — that function does not exist in startup.py. The disabled-mode warning lives in `AuthMiddleware._DISABLED_WARN_INTERVAL` at `triggarr/web/middleware.py:114-122` (request-time, rate-limited). | Pattern 4 / Open Questions | The "follow this exact shape" instruction in D-14 needs interpretation. The actual pattern to follow is the simpler `check_localhost_urls` at `startup.py:25-46` (sync helper, takes settings, emits logger.warning, called once from `startup()`). This is what Pattern 4 mirrors. The planner should NOT search for `_warn_if_auth_disabled` — it does not exist. |
| A5 | `request.client` is `None` in some test transports; `if request.client else "unknown"` is the safe guard | Pitfall 2 | Without the guard, tests that don't set a client crash. With the guard, observability is mildly degraded ("unknown" IP in logs) in those edge cases — acceptable. |

## Open Questions

1. **SEC-01 inline event handler migration scope — confirm Option B from Pitfall 1**
   - What we know: CONTEXT D-04 mandates dropping `'unsafe-inline'`; 14 `on*=` attributes exist; nonces don't cover them.
   - What's unclear: Is the user prepared for the extra mechanical work of migrating 14 handlers, or do they prefer to keep `'unsafe-inline'` (essentially cancelling SEC-01)?
   - Recommendation: The planner should add a checkpoint task or re-run `/gsd:discuss-phase` to confirm. Default assumption (this research): Option B (migrate to `addEventListener`).

2. **SEC-02 UX — surface validation error in the settings form?**
   - What we know: Existing `pydantic.ValidationError` handler logs + redirects, no UI surfacing.
   - What's unclear: Is silent redirect acceptable for SEC-02, or should the planner extend scope?
   - Recommendation: Document the limitation in PLAN.md, defer UI threading to a follow-up if needed. The locked decision D-08 specifies the message text, not the surfacing mechanism — text-in-log is sufficient to satisfy literal compliance.

3. **CONTEXT.md correction needed — `_warn_if_auth_disabled` reference**
   - What we know: CONTEXT.md D-14 references "`_warn_if_auth_disabled` at `triggarr/startup.py:27-37`" but that function does not exist; `startup.py:25-46` is `check_localhost_urls`.
   - What's unclear: Whether CONTEXT.md meant the AuthMiddleware periodic warning at `middleware.py:114-122` (rate-limited, in-request) or the sync helper pattern at `check_localhost_urls`.
   - Recommendation: Follow the simpler `check_localhost_urls` pattern (sync helper, takes settings, emits one WARNING, called from `startup()`). This is the most natural fit for D-12's "single occurrence, not periodic" constraint.

4. **`unknown` as fallback client IP — acceptable?**
   - What we know: `request.client` can be `None`; need a fallback string for the WARNING log.
   - What's unclear: Should it be `unknown`, `-`, or some other sentinel?
   - Recommendation: `"unknown"` — matches common log conventions and is human-readable.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | All work items | ✓ | 3.13 (project target) | — |
| pydantic | SEC-02 | ✓ | 2.x | — |
| starlette (via FastAPI) | SEC-01, SEC-03 | ✓ | already installed | — |
| loguru | SEC-03, SEC-04 | ✓ | already installed | — |
| pytest + pytest-asyncio | All tests | ✓ | already installed | — |
| ruff | Lint gate | ✓ | already installed | — |
| uv | Project runner | ✓ | per CLAUDE.md | — |

**Missing dependencies with no fallback:** none
**Missing dependencies with fallback:** none

No new packages are added in this phase. Standard verification gate: `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (`asyncio_mode=auto`) |
| Config file | `pyproject.toml` (project-level pytest config) |
| Quick run command | `uv run pytest tests/test_middleware.py tests/test_config.py tests/test_startup.py tests/test_auth_middleware.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEC-01 | CSP header drops `'unsafe-inline'` from script-src | integration | `uv run pytest tests/test_middleware.py::test_security_headers_csp_present -x` | EXISTS — update to assert new header |
| SEC-01 | CSP header contains `'nonce-<value>'` matching rendered `<script nonce=...>` | integration | `uv run pytest tests/test_middleware.py::test_csp_nonce_appears_in_header_and_html -x` | NEW — Wave 0 add to test_middleware.py |
| SEC-01 | No inline event handler attribute attempts execute (post-migration) | smoke / manual | `uv run pytest tests/test_middleware.py::test_no_unsafe_inline_in_script_src -x` + manual browser smoke | NEW — assert via header regex |
| SEC-02 | InstanceConfig rejects `?apikey=`, `?APIKEY=`, `?apiKey=` (parameterized) | unit | `uv run pytest tests/test_config.py::test_rejects_apikey_query -x` | NEW — Wave 0 add to test_config.py |
| SEC-02 | InstanceConfig accepts URLs without apikey query (parameterized) | unit | `uv run pytest tests/test_config.py::test_accepts_url_without_apikey_query -x` | NEW |
| SEC-02 | Settings POST with apikey-containing URL returns redirect, no TOML write | integration | `uv run pytest tests/test_auth_routes.py::test_settings_post_rejects_apikey_in_url -x` | NEW — Wave 0 add (cross-coverage) |
| SEC-03 | Null byte in password → 401 + WARNING with `reason=control_char` and `client_ip` | integration | `uv run pytest tests/test_auth_middleware.py::test_basic_auth_null_byte_in_password_rejected -x` | NEW |
| SEC-03 | Control char (0x01..0x1F) in username → 401 + WARNING | integration | `uv run pytest tests/test_auth_middleware.py::test_basic_auth_control_char_in_username_rejected -x` | NEW |
| SEC-03 | DEL (0x7F) in password → 401 + WARNING | integration | `uv run pytest tests/test_auth_middleware.py::test_basic_auth_del_in_password_rejected -x` | NEW |
| SEC-03 | Existing decode-failure path (invalid base64) now emits WARNING with `reason=decode_failure` | integration | `uv run pytest tests/test_auth_middleware.py::test_basic_auth_decode_failure_logs_warning -x` | NEW (modify existing `test_basic_auth_malformed_header_returns_401`) |
| SEC-03 | PII minimisation: username/password NEVER appear in log output (negative assertion) | integration | covered inside each SEC-03 test via `assert "admin" not in sink.getvalue()` | NEW |
| SEC-04 | session_secret < 32 chars and `not needs_setup` → WARNING fires | unit | `uv run pytest tests/test_startup.py::test_warn_when_session_secret_short -x` | NEW |
| SEC-04 | session_secret ≥ 32 chars → no warning | unit | `uv run pytest tests/test_startup.py::test_no_warn_when_session_secret_long -x` | NEW |
| SEC-04 | `needs_setup=True` (empty username) → no warning regardless of secret length | unit | `uv run pytest tests/test_startup.py::test_no_warn_when_needs_setup -x` | NEW |
| SEC-04 | secret value NEVER appears in log output | unit | covered via `assert "short" not in sink.getvalue()` inside short-secret test | NEW |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_middleware.py tests/test_config.py tests/test_startup.py tests/test_auth_middleware.py -x -q && uv run ruff check triggarr/ tests/`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work` plus a manual browser smoke test on `/`, `/setup`, `/settings`, `/login` to confirm no CSP errors in DevTools console (SEC-01 specific — `TestClient` does NOT enforce CSP).

### Wave 0 Gaps
- [ ] No new test files — all new tests extend existing files: `tests/test_middleware.py`, `tests/test_config.py`, `tests/test_startup.py`, `tests/test_auth_middleware.py`, `tests/test_auth_routes.py` (last one optional, for SEC-02 cross-coverage).
- [ ] No conftest.py changes required — existing fixtures (`_make_auth_app`, `_basic_auth_header`, `_configured_auth`, `_make_settings`) cover the new scenarios.
- [ ] No framework install needed — `uv sync --extra dev` is the existing one-time setup.
- [ ] **Manual browser-smoke checklist needed for SEC-01** (pytest cannot verify CSP enforcement). Plan must include a `checkpoint:human-verify` task asking the operator to open DevTools and confirm zero CSP violations on the four primary pages.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (SEC-03) | bcrypt (already in use via `auth.py`), timing-safe compare (`secrets.compare_digest`), Basic auth header char validation (SEC-03) |
| V3 Session Management | yes (SEC-04) | itsdangerous TimestampSigner (already in use), 30-day cookie TTL, `httponly` + `samesite=lax` (already in code), session secret length validation (SEC-04) |
| V4 Access Control | no | Phase 64's `search_lock` AST audit + existing AuthMiddleware deny-all are the project-level controls; no new authz logic in this phase |
| V5 Input Validation | yes (SEC-02) | Pydantic v2 `@field_validator` on InstanceConfig.url; existing `validate_arr_url` SSRF allowlist |
| V6 Cryptography | yes (SEC-01) | `secrets.token_urlsafe(16)` for nonces — stdlib CSPRNG, never hand-rolled |
| V7 Errors & Logging | yes (SEC-03 D-10, SEC-04 D-14) | loguru with redacting sink, PII minimisation (no usernames/secrets in WARNING logs) |
| V14 Configuration | yes (SEC-01 D-04) | CSP header tightening — `script-src` drops `'unsafe-inline'`; `frame-ancestors 'none'` already present |

### Known Threat Patterns for FastAPI + Jinja2 + Basic auth stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Inline XSS via injected `<script>` | Tampering (Integrity) | Nonce-based CSP (SEC-01) — even if attacker controls some HTML, they can't guess the nonce |
| API key leakage via URL query param logged in plaintext | Information Disclosure | URL validation rejects `?apikey=` at config save (SEC-02); existing redacting sink covers runtime exposure |
| Basic auth header smuggling (null bytes, CRLF) | Tampering / Spoofing | Control-char rejection after base64 decode (SEC-03 D-09); WWW-Authenticate response prevents auth state confusion |
| Session secret too short → brute-force feasible | Spoofing | Length validation at startup (SEC-04); itsdangerous HMAC over the secret |
| Silent decode failures hide attack reconnaissance | Repudiation | WARNING-level log on decode failure (SEC-03 D-11) |
| CSP bypass via inline event handlers | Tampering | Migrate inline `on*=` to `addEventListener` (see Pitfall 1) |

## Cross-Cutting Concerns

### Wave structure and sequencing

**Option A — Three waves (recommended given Pitfall 1 risk):**

```
Wave 0 (test scaffolding, optional — only if planner wants explicit Wave 0):
  - No file creations needed; existing test files have hooks.

Wave 1 (parallel, independent files):
  - 66-01-PLAN.md  SEC-02  models/config.py + tests/test_config.py        TDD
  - 66-02-PLAN.md  SEC-03  web/middleware.py + tests/test_auth_middleware.py TDD
  - 66-03-PLAN.md  SEC-04  startup.py + tests/test_startup.py            TDD

Wave 2 (depends on no other plan; runs after Wave 1 merges to keep CSP-drop atomic):
  - 66-04-PLAN.md  SEC-01  middleware.py + routes.py + 4 templates + 2 partials + tests/test_middleware.py
     Sub-tasks (sequential within plan):
       T1: Migrate inline on* attributes to addEventListener (templates only, no CSP change yet) - execute
       T2: Add nonce generation in middleware + context_processor wiring + Jinja2Templates(...) update - execute
       T3: Drop 'unsafe-inline' from script-src, update existing test_security_headers_csp_present - execute
       T4: Add new nonce-match test test_csp_nonce_appears_in_header_and_html - execute
       T5: Manual browser-smoke checkpoint:human-verify - checkpoint
```

**Option B — All four in parallel (faster, higher risk):**
SEC-01 and SEC-02/03/04 touch different files, so they CAN run in parallel. However, SEC-01 is significantly riskier (browser-runtime breakage from Pitfall 1) and benefits from staying as the final plan so the test suite from Waves 1's plans is green and uncontaminated by inline-handler refactors.

**Recommend Option A.** Reason: the SEC-01 plan should be the single point of attention when it lands; mixing it with the other three increases the chance of a missed inline handler going to production.

### Files touched (frontmatter)

| Plan | Files modified |
|------|----------------|
| SEC-01 (66-04) | `triggarr/web/middleware.py`, `triggarr/web/routes.py`, `triggarr/templates/base.html`, `triggarr/templates/dashboard.html`, `triggarr/templates/setup.html`, `triggarr/templates/settings.html`, `triggarr/templates/partials/log_viewer.html`, `triggarr/templates/partials/security_apikey.html`, `tests/test_middleware.py` |
| SEC-02 (66-01) | `triggarr/models/config.py`, `tests/test_config.py`, `tests/test_auth_routes.py` (optional cross-coverage) |
| SEC-03 (66-02) | `triggarr/web/middleware.py`, `tests/test_auth_middleware.py` |
| SEC-04 (66-03) | `triggarr/startup.py`, `tests/test_startup.py` |

Note that SEC-01 and SEC-03 BOTH modify `triggarr/web/middleware.py`. If running in parallel (Option B), there's a merge conflict risk on `middleware.py`. **In Option A (recommended), SEC-03 ships in Wave 1 and SEC-01 in Wave 2, so the SEC-01 plan rebases onto SEC-03's already-merged changes — no conflict.**

### TDD classification (workflow.tdd_mode=true)

| Plan | TDD eligibility | Type | Rationale |
|------|----------------|------|-----------|
| SEC-02 | strong | `tdd` (RED→GREEN→REFACTOR) | Pure logic with defined I/O. Write parametrized accept/reject tests first; implementation is 8 lines. |
| SEC-03 | strong | `tdd` (RED→GREEN→REFACTOR) | Pure logic for control-char detection + sanity tests for log output. Helper function (`_has_control_chars`) is testable in isolation; middleware integration tests cover the wiring. |
| SEC-04 | strong | `tdd` (RED→GREEN→REFACTOR) | Pure logic with logging side effect; loguru capture is the test idiom. |
| SEC-01 | weak (integration-driven) | `execute` (each sub-task) | Middleware side-effect + Jinja wiring + template edits. Tests are integration-level (TestClient + regex), not unit. RED→GREEN doesn't add value here; just write the implementation + green tests together. Template edits (T1, T2) are mechanical — `execute`. The manual checkpoint (T5) is unavoidable for SEC-01 because TestClient doesn't enforce CSP. |

### SecretStr discipline reaffirmation

SEC-04 calls `auth.session_secret.get_secret_value()` for length comparison. This is the ONLY new call site to `.get_secret_value()` in this phase. CLAUDE.md allows it under "explicit length checks." The value is consumed by `len()` and never logged, returned, or assigned to a non-SecretStr field. The warning message uses no value interpolation — it names the field and remediation, not the bad value.

### Concurrent config save interaction (Phase 64 lock)

Phase 64 established `app.state.search_lock` as the AST-verified lexical dominator of every `_atomic_toml_write` call in `routes.py`. SEC-02 runs at Pydantic model construction time (line 566: `SettingsModel(**new_config)`), which is BEFORE the lock is acquired (line 575: `async with request.app.state.search_lock:`). This is correct sequencing:

```
form parsed → SettingsModel(**new_config) → (Pydantic raises) → caught at 567-569 → redirect 303
              │
              ▼ (passes validation)
              acquire search_lock → _atomic_toml_write → release
```

No interaction with Phase 64's AST audit. The audit checks `_atomic_toml_write` callsites, not pre-validation logic.

### Verification gate

Standard project gate, per CLAUDE.md "Development Commands":
```bash
uv run pytest tests/ -x -q
uv run ruff check triggarr/ tests/
```

Plus SEC-01 manual checkpoint (browser DevTools, four pages: `/`, `/setup`, `/settings`, `/login` — confirm no CSP violation messages in console).

## Sources

### Primary (HIGH confidence)
- `triggarr/web/middleware.py:1-188` — current `SecurityHeadersMiddleware`, `OriginCheckMiddleware`, `AuthMiddleware` `[VERIFIED: file read]`
- `triggarr/models/config.py:1-167` — current `InstanceConfig`, `AuthConfig`, `Settings`, existing `@model_validator` pattern `[VERIFIED]`
- `triggarr/startup.py:1-200` — current `startup()` flow, `check_localhost_urls` pattern `[VERIFIED]`
- `triggarr/auth.py:1-106` — `generate_session_secret` (64-char hex), `verify_password`, `sign_session`, `validate_session` `[VERIFIED]`
- `triggarr/web/routes.py:1-100, 482-660, 1080-1140` — `Jinja2Templates` setup at line 60-75, settings POST handler, `_atomic_toml_write` callsite, setup persistence `[VERIFIED]`
- `triggarr/__main__.py:36-86` — middleware registration order, uvicorn config `[VERIFIED]`
- `triggarr/templates/base.html, dashboard.html, setup.html, settings.html`, plus `partials/log_viewer.html`, `partials/security_apikey.html` — exhaustive inventory of inline `<script>` AND `on*=` attributes `[VERIFIED: grep + read]`
- `tests/test_middleware.py:170-221` — existing CSP header test (`test_security_headers_csp_present`) `[VERIFIED]`
- `tests/test_auth_middleware.py:96-326` — existing Basic auth test patterns (`_basic_auth_header`, `_configured_auth`) `[VERIFIED]`
- `tests/test_startup.py:1-90` — existing loguru capture pattern (`io.StringIO` + `logger.add(sink, ...)`) `[VERIFIED]`
- `tests/test_config.py:113-145, 200-310` — existing `@model_validator` test pattern, `ValidationError` assertion idiom `[VERIFIED]`
- `.planning/phases/66-security-hardening/66-CONTEXT.md` — all 14 locked decisions D-01..D-14 `[VERIFIED]`
- `.planning/ROADMAP.md:193-203` — Phase 66 goal + success criteria 1-4 `[VERIFIED]`
- `.planning/REQUIREMENTS.md:20-24` — SEC-01..SEC-04 with file:line pointers `[VERIFIED]`
- `.planning/codebase/CONCERNS.md:63-87` — original audit pointers `[VERIFIED]`
- [FastAPI Jinja2Templates docs (context_processors signature)](https://fastapi.tiangolo.com/reference/templating/) `[CITED]`

### Secondary (MEDIUM confidence)
- [OWASP CSP Cheat Sheet (nonce length recommendations)](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html) `[CITED]`
- [MDN CSP script-src directive](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/script-src) `[CITED]`
- [content-security-policy.com — nonce primer](https://content-security-policy.com/nonce/) `[CITED]`
- [W3C CSP Level 3 spec](https://www.w3.org/TR/CSP3/) `[CITED]`
- [Starlette middleware execution order](https://www.starlette.io/middleware/) `[CITED]`
- [Django-CSP nonce docs (CSP nonce via context_processor — pattern reference)](https://django-csp.readthedocs.io/en/latest/nonce.html) `[CITED]`

### Tertiary (LOW confidence)
- None — every claim was either verified in the codebase or cross-referenced with the FastAPI / OWASP / W3C docs.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all primitives already present in codebase, verified by file reads.
- Architecture (nonce middleware + Jinja context_processor pattern): HIGH — confirmed via FastAPI docs + matches existing project conventions.
- Pitfalls: HIGH — Pitfall 1 (inline event handlers) is grep-verified, not theoretical; the other pitfalls are documented spec/library behaviour.
- TDD classification: HIGH — matches CLAUDE.md project guidance and existing `tests/test_config.py`, `tests/test_startup.py` patterns.

**Research date:** 2026-05-26
**Valid until:** 2026-06-25 (stable area — Pydantic v2, Starlette, FastAPI, CSP spec are all unchanged in foreseeable horizon)
