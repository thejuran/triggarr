# Phase 59: Security Hardening — Address Shield findings (SHIELD-001 through SHIELD-011) - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Address 11 security findings from the Shield assessment (reports/security-2026-04-15.md). Fix HIGH and MEDIUM findings that are actionable, risk-accept findings where current defenses are sufficient for a single-user homelab app. LOW findings get lightweight fixes. No new features — only hardening existing auth infrastructure from Phases 54-58.

</domain>

<decisions>
## Implementation Decisions

### Rate Limiting (SHIELD-003)
- **D-01:** In-memory sliding window rate limiter on POST /login. Track failed attempts per IP in a module-level dict with timestamps. 10 attempts per 5-minute window. Returns 429 when exceeded.
- **D-02:** On rate limit hit, re-render the login template with error message "Too many login attempts, try again in X minutes" — consistent with other login error rendering. No plain 429 response.
- **D-03:** No persistence — rate limit state resets on app restart. Acceptable for single-user homelab deployment.

### API Key Exposure (SHIELD-002)
- **D-04:** Stop passing raw API key to settings template context. Replace `auth_api_key: settings.auth.api_key.get_secret_value()` with `auth_api_key_set: bool(...)`.
- **D-05:** Reveal-on-regen only — the API key is shown in full only immediately after regeneration via the existing `revealed=True` flash path. Settings page shows masked placeholder otherwise.
- **D-06:** No new "show key" endpoint needed.

### Content-Security-Policy (SHIELD-001)
- **D-07:** Add CSP header to SecurityHeadersMiddleware. Pragmatic policy: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'`.
- **D-08:** `unsafe-inline` required for both scripts (htmx inline event handlers) and styles (Tailwind v4 may inject inline styles). Enforce immediately — no report-only phase.
- **D-09:** `frame-ancestors 'none'` replaces the existing X-Frame-Options DENY behavior with CSP equivalent.

### SSRF Hardening (SHIELD-007)
- **D-10:** Add IPv4-mapped IPv6 address checks to `validate_arr_url`. Check `addr.ipv4_mapped` on IPv6 addresses and validate the mapped address against the same blocklist. Also block multicast addresses.

### Log Sanitization (SHIELD-005, SHIELD-011)
- **D-11:** SHIELD-005: Replace username in login failure log with boolean match indicator: `logger.warning("Login failed: username_match={matched}", matched=bool(...))`.
- **D-12:** SHIELD-011: Replace username in setup completion log with generic message: `logger.info("Setup completed")` — no user-controlled input in log messages.

### Test Fixture Cleanup (SHIELD-004)
- **D-13:** Add `.gitleaksignore` file to suppress false positives on test fixture API keys. Optionally rename test constants to clearly fake values like `test-only-not-a-real-key-00000000`.

### Auth-Disabled Warning (SHIELD-009)
- **D-14:** Change from one-time warning to periodic re-logging. Log the "auth disabled" warning on a reasonable interval (e.g., every request or every N minutes) instead of suppressing after first emit.

### Changelog innerHTML (SHIELD-010)
- **D-15:** Add a code comment documenting that `html.escape()` in `parse_changelog` is the security boundary. No code change needed — the existing escaping is sufficient but the fragility should be documented.

### Risk-Accepted Findings
- **D-16:** SHIELD-008 (sessions not invalidated on password change): Risk-accepted. Single-user app — session secret rotation on password change adds complexity without meaningful security benefit. Existing 30-day expiry is sufficient.
- **D-17:** SHIELD-006 (CSRF tokens): Risk-accepted. SameSite=Lax cookies + OriginCheckMiddleware provide sufficient CSRF protection for a single-user homelab app. Synchronizer tokens are overengineering for this threat model.

### Claude's Discretion
- Internal structure of the rate limiter (helper functions, cleanup of stale entries)
- Exact wording of rate limit error message on login page
- Whether to update existing tests or add new tests for the security changes
- Organization of fixes across PLAN.md files (by severity, by file, or by category)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Security Assessment
- `reports/security-2026-04-15.md` — Full Shield findings with proposed fixes, CWE/OWASP classifications, and compliance impact

### Auth Design Specification
- `docs/superpowers/specs/2026-04-14-built-in-auth-design.md` — Auth design: all four modes, middleware spec, session management

### Files to Modify
- `triggarr/web/middleware.py` — SecurityHeadersMiddleware (CSP), AuthMiddleware (disabled warning), OriginCheckMiddleware
- `triggarr/web/routes.py` — Login rate limiting, API key exposure, log sanitization
- `triggarr/web/validation.py` — SSRF IPv6 hardening
- `triggarr/templates/settings.html` — API key masked placeholder (template side of SHIELD-002)

### Prior Phase Context
- `.planning/phases/55-auth-middleware-health-endpoint/55-CONTEXT.md` — Middleware placement, auth check order
- `.planning/phases/58-auth-test-suite/58-CONTEXT.md` — Test organization, existing test file inventory

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SecurityHeadersMiddleware` in `middleware.py` — already sets X-Frame-Options, X-Content-Type-Options, Referrer-Policy. CSP header adds one more line.
- `validate_arr_url` in `validation.py` — already has IP address blocking infrastructure. IPv6 check extends existing pattern.
- Login route in `routes.py` — has clear failure path where rate limiting hooks in.

### Established Patterns
- Loguru with redacting sink for all logging (no print/logging module)
- SecretStr for API keys — `.get_secret_value()` only at HTTP client init
- `html.escape()` for user-controlled content in HTML responses

### Integration Points
- Rate limiter module-level state in `routes.py` (or extracted to a small helper)
- Settings template needs update to stop receiving raw API key
- Test files may need updates for changed log messages and new rate limit behavior

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 59-security-hardening-address-shield-findings-shield-001-throug*
*Context gathered: 2026-04-15*
