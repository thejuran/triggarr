# SECURITY.md — Phase 59: Security Hardening (SHIELD-001 through SHIELD-011)

**Phase:** 59 — security-hardening-address-shield-findings-shield-001-throug
**ASVS Level:** 1
**Verified:** 2026-04-15
**Threats Closed:** 14/14

---

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-59-01 | Elevation of Privilege | mitigate | CLOSED | `triggarr/web/routes.py:1138-1214` — `_login_failures` dict, `_MAX_ATTEMPTS=10`, `_WINDOW_SECONDS=300`, `_check_rate_limit()` called before credential verification in `login_post` |
| T-59-02 | Denial of Service | accept | CLOSED | See Accepted Risks log below |
| T-59-03 | Spoofing | accept | CLOSED | See Accepted Risks log below |
| T-59-04 | Tampering | mitigate | CLOSED | `triggarr/web/validation.py:91-100` — `addr.ipv4_mapped` check with loopback/link-local/unspecified/multicast blocking on mapped IPv4 address |
| T-59-05 | Tampering | mitigate | CLOSED | `triggarr/web/validation.py:88` — `addr.is_multicast` added to existing SSRF blocking condition, covers IPv4 and IPv6 multicast |
| T-59-06 | Spoofing | mitigate | CLOSED | `triggarr/web/middleware.py:46` — `frame-ancestors 'none'` in CSP; `triggarr/web/middleware.py:34` — `X-Frame-Options: DENY` |
| T-59-07 | Information Disclosure | mitigate | CLOSED | `triggarr/web/middleware.py:40-47` — CSP header with `script-src 'self' 'unsafe-inline'`; external scripts blocked by `default-src 'self'`; `unsafe-inline` required for htmx |
| T-59-08 | Repudiation | mitigate | CLOSED | `triggarr/web/middleware.py:94-95,115-121` — `_disabled_warned_at: float = 0.0`, `_DISABLED_WARN_INTERVAL: float = 60.0`; periodic warning fires every 60s via `time.monotonic()` |
| T-59-09 | Tampering | accept | CLOSED | See Accepted Risks log below |
| T-59-10 | Information Disclosure | mitigate | CLOSED | `triggarr/web/routes.py:407` — `"auth_api_key_set": bool(settings.auth.api_key.get_secret_value())` replaces raw key in template context; `triggarr/templates/partials/security_apikey.html:5` — masked `"********************************"` placeholder |
| T-59-11 | Information Disclosure | mitigate | CLOSED | `triggarr/web/routes.py:1240` — `logger.warning("Login failed: invalid credentials")` — no user-controlled username in log output (stronger than planned `username_match=` pattern) |
| T-59-12 | Tampering | mitigate | CLOSED | `triggarr/web/routes.py:1105` — `logger.info("Setup completed")` — generic message, no username parameter |
| T-59-13 | Information Disclosure | accept | CLOSED | See Accepted Risks log below |
| T-59-14 | Tampering | accept | CLOSED | See Accepted Risks log below |

---

## Accepted Risks

| Threat ID | Category | Risk Description | Rationale | Owner |
|-----------|----------|-----------------|-----------|-------|
| T-59-02 | Denial of Service | `_login_failures` module-level dict could grow unbounded under sustained IP-cycling attacks | Homelab single-user app with limited internet exposure; dict prunes expired entries on each check; dict resets on restart; `_MAX_TRACKED_IPS=10000` eviction cap implemented (routes.py:1170-1176) | thejuran |
| T-59-03 | Spoofing | Client IP sourced from `request.client.host`; when uvicorn runs with `proxy_headers=True` and `TRUSTED_PROXY_IPS=*`, X-Forwarded-For can be spoofed to bypass rate limiting | Reverse proxy users have rate limiting applied at the proxy layer; direct-connection users see real IP; risk is documented in code comment at routes.py:1196-1198 | thejuran |
| T-59-09 | Tampering | XSS via changelog content rendered outside Jinja2 autoescape | `html.escape()` applied to all user-visible text at changelog.py:107,118,130; `parse_changelog` docstring at changelog.py:71-77 documents this as the sole XSS boundary and requires future insertions to also use `html.escape()` | thejuran |
| T-59-13 | Information Disclosure | Active sessions are not invalidated when the user changes their password | Single-user homelab app; sessions expire after 30 days; session secret rotation (via triggarr.toml update) is available to force invalidation; risk is proportionate to deployment context | thejuran |
| T-59-14 | Tampering | CSRF protection relies on SameSite=Lax cookies and OriginCheckMiddleware rather than synchronizer tokens | SameSite=Lax prevents cross-site form submissions in all modern browsers; OriginCheckMiddleware (middleware.py:51-76) validates Origin/Referer on all mutating methods; combination provides ASVS L1-equivalent protection for a homelab app | thejuran |

---

## Unregistered Threat Flags

None. All threat flags from SUMMARY.md files map to registered threat IDs in the threat register.

---

## Notes

- T-59-11 implementation deviates from plan: plan specified `username_match={matched}` format; implementation uses `"Login failed: invalid credentials"` with no user data at all. The implementation is strictly stronger — no user-controlled data reaches the log at any point.
- T-59-02 implementation adds an eviction cap (`_MAX_TRACKED_IPS=10000`) not specified in the original plan, providing additional DoS hardening beyond the accepted disposition.
