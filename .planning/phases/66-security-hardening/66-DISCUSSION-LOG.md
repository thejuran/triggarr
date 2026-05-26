# Phase 66: Security Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions captured in `66-CONTEXT.md` — this log preserves the analysis.

**Date:** 2026-05-26
**Phase:** 66-security-hardening
**Mode:** discuss (standard, single-turn delegated)

## Areas Presented

Four gray areas were generated from the phase's success criteria + CONCERNS.md audit findings:

1. **SEC-01 CSP nonce migration strategy** — external-script extraction vs nonce-based CSP, given 4 inline `<script>` blocks across base/dashboard/setup/settings templates with 2 of them using Jinja `{{ url_for }}` interpolation.
2. **SEC-02 URL validation: strict vs lenient** — reject `apikey=` only vs reject any query string; strict reject at save vs strip-and-warn.
3. **SEC-03 Basic auth char policy** — null bytes + control chars only vs strict ASCII-printable; log fields (IP only vs IP + username).
4. **SEC-04 session_secret validation: warn vs fail** — warn-only vs hard-fail; once at startup vs periodic; how to detect "auto-generated and not persisted."

## User Response

> "take your recommendations for all"

User explicitly delegated all four gray areas to Claude's discretion.

## Recommendations Made and Locked

| Area | Recommendation | Rationale anchor |
|------|----------------|------------------|
| SEC-01 | Nonce-based CSP, drop `'unsafe-inline'` from `script-src`, keep `'unsafe-inline'` in `style-src` for now | OWASP modern pattern; existing Jinja URL interpolation in 2 of 4 scripts would require data-attribute plumbing if externalized |
| SEC-01 | Nonce gen in `SecurityHeadersMiddleware.dispatch()` via `secrets.token_urlsafe(16)`, stored on `request.state.csp_nonce`, exposed via Jinja global `csp_nonce()` | Single source of truth; no per-route plumbing |
| SEC-02 | Pydantic `@field_validator('url')` on `InstanceConfig`; reject only case-insensitive `apikey=` query keys | ROADMAP success criteria #2 says "rejected with a clear validation error before the config file is written"; broader query rejection would break reverse-proxy mount paths |
| SEC-02 | Error message names the API Key field as the remediation | Actionable error guidance |
| SEC-03 | Reject null bytes + ASCII control chars (0x00–0x1F, 0x7F) in decoded username/password; do NOT enforce strict ASCII-printable | RFC 7617 does not require server enforcement; control-char rejection is the conservative fix for the actual risk (bcrypt null-byte quirks); strict ASCII-printable would reject legitimate non-ASCII passwords |
| SEC-03 | Log at WARNING with `event`, `reason`, `client_ip` only — no username, no decoded bytes | PII minimization; matches PROJECT D-07 SecretStr discipline |
| SEC-03 | Also add WARNING log to existing silent `except (ValueError, UnicodeDecodeError): pass` at middleware.py:183-184 | Closes the "currently silent on decode error" gap from CONCERNS.md without scope expansion |
| SEC-04 | Warn-only, single occurrence at startup, NOT periodic | Hard-fail breaks first-run setup flow; transient misconfiguration warrants warn-once, not the periodic Disabled-mode pattern |
| SEC-04 | Trigger: `not needs_setup AND len(session_secret) < 32` | The `needs_setup` guard prevents false positives during pre-setup; routes.py:1089-1112 confirms setup always persists atomically, so "auto-generated and not persisted" is unreachable |
| SEC-04 | New helper `_warn_if_session_secret_short` modeled on existing `_warn_if_auth_disabled` at startup.py:27-37 | Proven pattern in same file |

## Scope Boundary Observations

The four ROADMAP success criteria for Phase 66 are tightly specified. CONCERNS.md provides file:line pointers for every item. There was no scope-creep candidate raised during the analysis — the four items are independent, all fall in the existing security layer, and none implies new routes/dependencies/config keys.

## Deferred (out of scope for Phase 66)

- `style-src 'unsafe-inline'` removal — script-only nonce migration in this phase
- Periodic session_secret warning (Disabled-mode-style)
- Rejecting any query parameter in *arr URLs
- Strict ASCII-printable password policy
- Logging the failed Basic auth username

## Codebase Evidence Gathered

- `triggarr/web/middleware.py:25-49` SecurityHeadersMiddleware (CSP composition)
- `triggarr/web/middleware.py:157-188` _handle_basic_auth (base64 decode + bcrypt verify)
- `triggarr/models/config.py:44-70` InstanceConfig with existing `@model_validator` patterns
- `triggarr/models/config.py:90-111` AuthConfig with `session_secret: SecretStr`
- `triggarr/auth.py:61-67` generate_session_secret (64-char hex)
- `triggarr/web/routes.py:1086-1117` setup flow (atomic persistence inside search_lock)
- `triggarr/startup.py:27-37` _warn_if_auth_disabled (warning pattern)
- `triggarr/templates/{base,dashboard,setup,settings}.html` inline `<script>` inventory (4 blocks)
- `grep -rnE "hx-on|hx-on::" triggarr/templates/` → 0 hits (no inline htmx event handlers)

## Outcome

CONTEXT.md written with 14 locked decisions (D-01..D-14) across SEC-01..SEC-04. No Claude's-Discretion residual. Ready for `/gsd:plan-phase 66`.
