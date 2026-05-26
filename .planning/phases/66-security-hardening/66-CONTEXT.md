# Phase 66: Security Hardening - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Narrow the application's HTTP attack surface across four independent fronts:

1. **SEC-01:** Remove `'unsafe-inline'` from CSP `script-src` by adopting nonce-based CSP (all inline `<script>` blocks in templates carry a per-request nonce that matches the response header).
2. **SEC-02:** Reject Radarr/Sonarr/Lidarr URLs that contain an `apikey=` query parameter at config-save time, before the TOML write.
3. **SEC-03:** Reject Basic auth headers whose decoded credentials contain null bytes or ASCII control characters with a 401 + WARNING log, before the password comparison step.
4. **SEC-04:** At startup, log a WARNING if the persisted session_secret is shorter than 32 characters.

All four items are scoped to the existing `triggarr/web/middleware.py`, `triggarr/models/config.py`, `triggarr/auth.py`, `triggarr/startup.py`, and template files. No new dependencies. No new routes. No new config keys (SEC-04 reuses existing `auth.session_secret`).

The user explicitly delegated all gray-area decisions ("take your recommendations for all"), so the four locked decisions below are Claude's discretion calls grounded in codebase evidence, the v2.8 audit (CONCERNS.md), and OWASP/idiomatic patterns.

</domain>

<decisions>
## Implementation Decisions

### SEC-01 — CSP nonce migration
- **D-01:** Adopt **nonce-based CSP**, not external-script extraction. Drop `'unsafe-inline'` from `script-src`.
  - **Why:** Two of the four inline scripts use Jinja `{{ request.url_for(...) }}` interpolation (`base.html:123` changelog modal, `dashboard.html:48+` log viewer controls). Extracting them to external `.js` files requires adding `data-*` attributes or `window.*` globals just to pass URLs — that's mechanical churn with no security gain. Nonce-based CSP is the OWASP-recommended modern pattern and the `SecurityHeadersMiddleware` at `triggarr/web/middleware.py:25-49` already owns CSP composition.
- **D-02:** Nonce generation happens in `SecurityHeadersMiddleware.dispatch()` via `secrets.token_urlsafe(16)` per request, stored on `request.state.csp_nonce`, and exposed to Jinja templates via a `csp_nonce` template global that reads `request.state.csp_nonce`.
  - **Why:** Single source of truth (the middleware), and Jinja templates can reference it as `<script nonce="{{ csp_nonce() }}">…</script>` without needing per-route context plumbing.
- **D-03:** **All four inline scripts get a nonce attribute.** Inventory: `base.html:116-132` (changelog modal), `dashboard.html:48+` (log viewer controls + expand/pause), `setup.html:70+` (copy API key), `settings.html:253+` (auth method warning + API key toggle).
- **D-04:** `script-src` becomes `'self' 'nonce-<value>'` (no `'unsafe-inline'`). `style-src` keeps `'unsafe-inline'` for now — Tailwind utility output is fine, and migrating styles is out of scope for SEC-01. Document this explicitly in the CSP comment.
- **D-05:** No `hx-on` / `hx-on::` htmx attribute handlers exist in templates (verified via `grep -rnE "hx-on|hx-on::" triggarr/templates/`) — htmx attribute handlers are NOT a blocker for dropping `'unsafe-inline'`. Future htmx event handling must use the delegated `htmx:afterSwap`-style pattern already used in `dashboard.html`.

### SEC-02 — URL validation (apikey= rejection)
- **D-06:** Implement as a **Pydantic `@field_validator('url')`** on `InstanceConfig` in `triggarr/models/config.py:44`. Validation runs at config load AND at every settings POST that round-trips through `InstanceConfig` construction (already the path used by `triggarr/web/routes.py` settings save handlers).
  - **Why:** ROADMAP success criteria #2 requires "rejected with a clear validation error before the config file is written." A Pydantic validator raises `ValidationError` which the existing settings POST handler already converts into a 400 with field-level errors. No new error-handling plumbing.
- **D-07:** **Reject only `apikey=`** (and its case variants: `apiKey=`, `APIKEY=`, etc.). Do NOT reject all query strings.
  - **Why:** Legitimate use cases include reverse-proxy mount paths and *arr instances on subpaths; broader query-string rejection would break valid setups. Narrow rule: parse `url` via `urllib.parse.urlparse` + `parse_qs`, reject if any key matches `^apikey$` case-insensitive.
- **D-08:** Error message: `"URL must not contain an apikey= query parameter. Use the API Key field instead."` — actionable, names the field they should use.

### SEC-03 — Basic auth header hardening
- **D-09:** Reject decoded credentials containing **null bytes (0x00) or ASCII control characters (0x00–0x1F, 0x7F)** in either the username or password component, after base64 decode at `triggarr/web/middleware.py:165`. Reject = return 401 with `WWW-Authenticate: Basic realm="Triggarr"` (same as existing decode-failure path).
  - **Why:** RFC 7617 §2.1 says user-id MUST NOT contain colon and clients SHOULD NOT send control chars, but the spec does not require server enforcement. The risk is downstream: bcrypt and some comparison routines have historically had quirks around null bytes. Conservative rejection matches the CONCERNS.md recommendation #1 without being aggressive enough to reject legitimate non-ASCII passwords (which are valid UTF-8 outside the control-char range).
- **D-10:** **Log at WARNING level on rejection.** Log fields: `event=basic_auth_rejected`, `reason=control_char` (or `reason=decode_failure` for the existing path), and `client_ip` (from `request.client.host`). **Do NOT log the username, the decoded bytes, or the raw header.**
  - **Why:** ROADMAP success criteria #3 explicitly specifies WARNING. PII minimization: source IP is observability-relevant, username is not (and could leak via log aggregation).
- **D-11:** Apply the same `event=basic_auth_rejected` WARNING log to the existing `except (ValueError, UnicodeDecodeError): pass` branch at `middleware.py:183-184` (silent today). That closes the "currently silent on decode error" gap from CONCERNS.md without expanding scope.

### SEC-04 — session_secret startup validation
- **D-12:** **Warn-only at startup, single occurrence, not periodic.**
  - **Why:** Hard-fail breaks the first-run setup flow (during `needs_setup`, `session_secret` is empty by design). The Disabled-mode periodic warning at `triggarr/startup.py:30-37` exists because Disabled-mode is an actively-insecure operating state; a short session_secret is a configuration mistake that's either acceptable (the user knows) or actionable once (the user fixes it on next save).
- **D-13:** Trigger condition: `not settings.auth.needs_setup AND len(settings.auth.session_secret.get_secret_value()) < 32`. The `needs_setup` guard prevents false positives during the pre-setup state where `session_secret == ""` is normal.
  - **Why:** `triggarr/web/routes.py:1089-1112` shows setup ALWAYS persists the freshly-generated 64-char hex secret atomically inside `search_lock` before any subsequent request runs — so "auto-generated and not yet persisted" (the original CONCERNS recommendation #2) is unreachable in current code. The remaining risk is a user hand-editing the TOML to a short value.
- **D-14:** Warning location: `triggarr/startup.py` `_warn_if_auth_disabled`-adjacent helper (new function `_warn_if_session_secret_short`), invoked once during startup before the connection-validation block. Message: `"auth.session_secret is shorter than 32 characters — regenerate via Settings → Security or set a longer value in config.toml"` — names the remediation path.

### Claude's Discretion
All four items above were user-delegated ("take your recommendations for all"). No additional discretionary areas — every decision in this CONTEXT.md is locked.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & audit context
- `.planning/ROADMAP.md` §"Phase 66: Security Hardening" — Goal, depends-on (Phase 64 config lock), 4 success criteria
- `.planning/codebase/CONCERNS.md` §"Security Considerations" (lines 63-87) — Original audit findings for SEC-01..SEC-04 with file:line pointers and current mitigations

### Source files to be modified (file:line pointers)
- `triggarr/web/middleware.py:25-49` — `SecurityHeadersMiddleware` (SEC-01 nonce generation lives here; CSP header composed here)
- `triggarr/web/middleware.py:157-188` — `_handle_basic_auth` (SEC-03 char validation + WARNING log added here)
- `triggarr/models/config.py:44-70` — `InstanceConfig` (SEC-02 `@field_validator('url')` added here)
- `triggarr/auth.py:61-67` — `generate_session_secret` (SEC-04 reference: produces the 64-char secret that the validator length-checks against)
- `triggarr/startup.py:27-37` — `_warn_if_auth_disabled` pattern (SEC-04 follows this exact structure for the new `_warn_if_session_secret_short`)
- `triggarr/web/routes.py:1089-1112` — Setup persistence flow (SEC-04: confirms session_secret is always persisted atomically; "auto-generated and not yet persisted" is unreachable)

### Templates with inline scripts (SEC-01 inventory)
- `triggarr/templates/base.html:116-132` — Changelog modal handlers (uses `{{ url_for }}`)
- `triggarr/templates/dashboard.html:48+` — Log viewer controls (uses `{{ url_for }}` and htmx event listeners)
- `triggarr/templates/setup.html:70+` — Copy API key clipboard helper
- `triggarr/templates/settings.html:253+` — Auth method warning + API key visibility toggle

### Project conventions
- `CLAUDE.md` — Python 3.11+, ruff (E,F,I,UP,B,SIM), 120 line length, SecretStr discipline (no `.get_secret_value()` outside HTTP client init / explicit length checks), loguru with redacting sink, pytest-asyncio
- `.planning/PROJECT.md` §"Key Decisions" — D-07 SecretStr discipline; D-10 deny-all auth middleware order

### Test coverage expectations
- `tests/test_middleware.py` — Existing test patterns for CSP headers, Basic auth, Origin check (model new tests on these)
- `tests/test_config.py` — Existing model_validator test patterns (model new SEC-02 URL validator tests on these)
- `tests/test_startup.py` — Existing `_warn_if_auth_disabled` test pattern (model new SEC-04 warning test on this)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SecurityHeadersMiddleware` at `triggarr/web/middleware.py:25-49` is already the single owner of CSP composition. SEC-01 nonce work plugs into this single class — no new middleware class needed.
- `_handle_basic_auth` at `middleware.py:157-188` is already a static method with a clean try/except boundary at `163-184`. SEC-03 adds one validation check between `decoded = base64.b64decode(...)` (line 165) and `secrets.compare_digest(...)` (line 167) — minimal surgical change.
- Pydantic `@field_validator` and `@model_validator` patterns are already used in `models/config.py:64` (`at_least_one_search_count`) and `models/config.py:132` (`validate_instances`). SEC-02 follows the same pattern.
- `_warn_if_auth_disabled` at `triggarr/startup.py:27-37` is the proven pattern for startup-time WARNING emission. SEC-04 follows this exact shape.

### Established Patterns
- **SecretStr discipline (PROJECT D-07):** `password_hash`, `api_key`, `session_secret` are all `SecretStr`. The SEC-04 length check needs `.get_secret_value()` — that's allowed at the validation point, but must NOT leak the value into the log message (D-14's message names the field, not the value).
- **Atomic config writes:** `_atomic_toml_write` in `triggarr/web/routes.py` is already locked by `app.state.search_lock` (verified by Phase 64's AST audit). SEC-02 validator runs BEFORE the lock is acquired (Pydantic validation is part of `InstanceConfig` construction, which happens before the settings POST handler reaches the `async with search_lock` block).
- **Jinja templates use `{{ request.url_for(...) }}`** for all static asset and route URL generation. SEC-01 nonce template global must integrate with this same `templates` object configured in `triggarr/web/routes.py` (search for `Jinja2Templates(` and `templates.env.globals[...]`).
- **No `hx-on` attributes in templates** (verified via grep). htmx event handling uses `document.addEventListener('htmx:afterSwap', ...)` in inline scripts — those scripts get the nonce treatment under SEC-01 and continue to work.

### Integration Points
- **SEC-01 nonce → templates:** Middleware sets `request.state.csp_nonce` early in `dispatch()`. Jinja global `csp_nonce` callable reads `request.state.csp_nonce`. Templates render `<script nonce="{{ csp_nonce() }}">…</script>`. Tests assert `Content-Security-Policy` header contains the same nonce that the rendered HTML's `<script>` tag carries.
- **SEC-02 validator → settings POST:** `triggarr/web/routes.py` settings save handler already constructs `InstanceConfig(**form_data)` (or similar). Pydantic raises `ValidationError`, the handler already maps validation errors back to the settings form template. SEC-02 plugs into that existing error path.
- **SEC-03 WARNING log → loguru:** Existing loguru sink at `triggarr/logging_setup.py` (redacting sink). New WARNING line uses `logger.warning("basic_auth_rejected reason={reason} client_ip={ip}", ...)` — no PII fields means no new redaction config needed.
- **SEC-04 warning → startup.py main():** New helper `_warn_if_session_secret_short(settings)` called once from the main startup sequence, after `ensure_config()` returns and before connection validation. Same call-site shape as `_warn_if_auth_disabled`.

</code_context>

<specifics>
## Specific Ideas

- The user delegated all four areas to Claude's discretion ("take your recommendations for all"). No specific UI references, vendor patterns, or external products were named.
- One implicit specific preference inherited from prior milestones: PROJECT.md D-07 SecretStr discipline (no leaking `.get_secret_value()` content into logs) — SEC-03 D-10 and SEC-04 D-14 both honor this.

</specifics>

<deferred>
## Deferred Ideas

- **`style-src 'unsafe-inline'` removal** — SEC-01 D-04 explicitly scopes nonce migration to scripts only. Tailwind utility classes occasionally emit inline `style=` attributes; full style-CSP migration is its own future hardening pass.
- **Migrating htmx attribute handlers to delegated listeners (CONCERNS.md recommendation 2 for SEC-01)** — already done in this codebase per the `hx-on` grep result. No action needed.
- **Periodic session_secret warning (like Disabled-mode reminder)** — explicitly rejected at D-12 (warn-once is sufficient because misconfiguration is transient).
- **Rejecting any query parameter in *arr URLs (CONCERNS.md SEC-02 recommendation 2)** — explicitly rejected at D-07 (would break legitimate setups; narrow rule is `apikey=` only).
- **Strict ASCII-printable password policy for Basic auth (alternative SEC-03 path)** — explicitly rejected at D-09 (would reject legitimate non-ASCII passwords).
- **Logging the failed Basic auth username for forensics (alternative SEC-03 D-10 path)** — explicitly rejected (PII minimization).

</deferred>

---

*Phase: 66-security-hardening*
*Context gathered: 2026-05-26*
