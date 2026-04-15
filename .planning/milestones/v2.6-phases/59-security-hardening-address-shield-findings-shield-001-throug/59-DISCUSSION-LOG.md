# Phase 59: Security Hardening — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-15
**Phase:** 59-security-hardening-address-shield-findings-shield-001-throug
**Areas discussed:** Rate limiting strategy, API key exposure fix, CSP policy strictness, CSRF token approach

---

## Rate Limiting Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| In-memory sliding window | Track failed attempts per IP in a dict with timestamps. 10 attempts per 5 min window. Returns 429 on exceed. Simple, no external deps, resets on restart. | ✓ |
| Fixed delay on failure | Add asyncio.sleep(1-2s) after every failed login. No tracking needed but slower defense. | |
| Both: window + delay | Sliding window for hard cutoff plus 0.5s delay on each failure. Belt and suspenders. | |

**User's choice:** In-memory sliding window (Recommended)
**Notes:** None

### Follow-up: Rate limit UX

| Option | Description | Selected |
|--------|-------------|----------|
| Login page with error message | Re-render login template with 'Too many attempts, try again in X minutes'. Consistent with other login errors. | ✓ |
| Plain 429 response | Simple 429 HTML/JSON response. Minimal, no template rendering needed. | |

**User's choice:** Login page with error message
**Notes:** None

---

## API Key Exposure Fix

| Option | Description | Selected |
|--------|-------------|----------|
| Reveal-on-regen only | Settings page shows masked placeholder. Key only shown after regeneration via existing revealed=True flash path. No new endpoint. | ✓ |
| Separate fetch endpoint | Masked placeholder with a 'Show key' button hitting an authenticated JSON endpoint. More flexible but adds new endpoint. | |

**User's choice:** Reveal-on-regen only (Recommended)
**Notes:** None

### Follow-up: Session invalidation on password change (SHIELD-008)

| Option | Description | Selected |
|--------|-------------|----------|
| Rotate session secret | Generate new session_secret on password change. All existing cookies become invalid. User must re-login on all devices. | |
| Keep current behavior | Don't rotate secret. Existing sessions stay valid for up to 30 days. Accept as risk-accepted for single-user app. | ✓ |

**User's choice:** Keep current behavior
**Notes:** Risk-accepted. Single-user app — session rotation adds complexity without meaningful benefit.

---

## CSP Policy Strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Pragmatic with unsafe-inline | Allow 'unsafe-inline' for scripts (htmx) and 'self' for everything else. frame-ancestors 'none'. | ✓ |
| Strict with nonces | Generate per-request nonces for inline scripts. More secure but requires template changes. | |
| Report-only first | Deploy as report-only initially to log violations. Switch to enforcing after confirming no breakage. | |

**User's choice:** Pragmatic with unsafe-inline (Recommended)
**Notes:** None

### Follow-up: Style-src inline

| Option | Description | Selected |
|--------|-------------|----------|
| Allow unsafe-inline for styles too | style-src 'self' 'unsafe-inline'. Covers inline style attributes from Tailwind or htmx. | ✓ |
| Self only for styles | style-src 'self'. Stricter but may break inline style= attributes. | |

**User's choice:** Allow unsafe-inline for styles too
**Notes:** None

---

## CSRF Token Approach

| Option | Description | Selected |
|--------|-------------|----------|
| Accept current defenses | SameSite=Lax + OriginCheckMiddleware already block cross-site submissions. Risk-accept SHIELD-006. | ✓ |
| Add CSRF tokens to sensitive forms | Synchronizer tokens on password change, API key regen, settings save. Full defense-in-depth. | |
| Double-submit cookie pattern | Lighter than synchronizer tokens. Set CSRF cookie, require it as form field. Middle ground. | |

**User's choice:** Accept current defenses (Recommended)
**Notes:** Risk-accepted for single-user homelab app.

---

## Claude's Discretion

- Internal structure of rate limiter
- Exact error message wording
- Test organization for security changes
- Plan file organization

## Deferred Ideas

None — discussion stayed within phase scope.
