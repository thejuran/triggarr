# Phase 59: Security Hardening - Research

**Researched:** 2026-04-15
**Domain:** Security hardening / OWASP remediation for FastAPI + htmx app
**Confidence:** HIGH

## Summary

This phase addresses 11 findings from the Shield security assessment (`reports/security-2026-04-15.md`). All changes are confined to existing files -- no new modules or dependencies. The fixes fall into three categories: (1) security header and rate limiting additions to middleware/routes, (2) data exposure fixes for API key and log sanitization, and (3) housekeeping for test fixtures and documentation.

The codebase is well-structured for these changes. `SecurityHeadersMiddleware` already has the right injection point for CSP. The login route has a clear failure path for rate limiting. `validate_arr_url` has the exact infrastructure for IPv6 extension. All 774 existing tests pass, providing a safety net for refactoring.

**Primary recommendation:** Implement in dependency order -- CSP header and log sanitization first (zero coupling), then API key exposure fix (template + route), then rate limiter (new logic + tests), then SSRF hardening, then test fixture cleanup last.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** In-memory sliding window rate limiter on POST /login. Track failed attempts per IP in a module-level dict with timestamps. 10 attempts per 5-minute window. Returns 429 when exceeded.
- **D-02:** On rate limit hit, re-render the login template with error message "Too many login attempts, try again in X minutes" -- consistent with other login error rendering. No plain 429 response.
- **D-03:** No persistence -- rate limit state resets on app restart.
- **D-04:** Stop passing raw API key to settings template context. Replace `auth_api_key: settings.auth.api_key.get_secret_value()` with `auth_api_key_set: bool(...)`.
- **D-05:** Reveal-on-regen only -- the API key is shown in full only immediately after regeneration via the existing `revealed=True` flash path.
- **D-06:** No new "show key" endpoint needed.
- **D-07:** CSP header: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'`.
- **D-08:** `unsafe-inline` required for both scripts and styles. Enforce immediately -- no report-only phase.
- **D-09:** `frame-ancestors 'none'` replaces X-Frame-Options DENY behavior.
- **D-10:** Add IPv4-mapped IPv6 address checks to `validate_arr_url`. Check `addr.ipv4_mapped` on IPv6 addresses and validate mapped address against same blocklist. Also block multicast.
- **D-11:** SHIELD-005: Replace username in login failure log with boolean match indicator.
- **D-12:** SHIELD-011: Replace username in setup completion log with generic message.
- **D-13:** Add `.gitleaksignore` file. Optionally rename test constants to clearly fake values.
- **D-14:** Change auth-disabled warning from one-time to periodic re-logging.
- **D-15:** Add code comment documenting `html.escape()` in `parse_changelog` as security boundary.
- **D-16:** SHIELD-008 risk-accepted (sessions not invalidated on password change).
- **D-17:** SHIELD-006 risk-accepted (CSRF tokens not needed).

### Claude's Discretion
- Internal structure of the rate limiter (helper functions, cleanup of stale entries)
- Exact wording of rate limit error message on login page
- Whether to update existing tests or add new tests for the security changes
- Organization of fixes across PLAN.md files (by severity, by file, or by category)

### Deferred Ideas (OUT OF SCOPE)
None.
</user_constraints>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CSP header (SHIELD-001) | Frontend Server (middleware) | -- | Response header set in SecurityHeadersMiddleware |
| API key exposure (SHIELD-002) | Frontend Server (routes+template) | -- | Route context variable + Jinja2 template change |
| Rate limiting (SHIELD-003) | Frontend Server (routes) | -- | In-memory per-IP tracking in login POST handler |
| Test fixture cleanup (SHIELD-004) | Build artifacts | -- | .gitleaksignore + test constant renames |
| Log sanitization (SHIELD-005, 011) | Frontend Server (routes) | -- | Logger call argument changes |
| SSRF hardening (SHIELD-007) | Frontend Server (validation) | -- | IP address validation in validate_arr_url |
| Auth-disabled warning (SHIELD-009) | Frontend Server (middleware) | -- | AuthMiddleware logging frequency |
| Changelog comment (SHIELD-010) | Frontend Server (changelog) | -- | Code comment only |

## Standard Stack

### Core
No new dependencies. All fixes use Python stdlib and existing project libraries.

| Library | Version | Purpose | Already Installed |
|---------|---------|---------|-------------------|
| Python `ipaddress` | stdlib | IPv4-mapped IPv6 validation | Yes (stdlib) |
| Python `time` | stdlib | `time.monotonic()` for rate limiter timestamps | Yes (stdlib) |
| Python `collections` | stdlib | Optional `defaultdict` for rate limiter | Yes (stdlib) |
| Loguru | existing | Logging changes | Yes |
| Jinja2 | existing | Template rendering changes | Yes |

[VERIFIED: uv.lock and pyproject.toml in project]

## Architecture Patterns

### System Architecture Diagram

```
HTTP Request
    |
    v
SecurityHeadersMiddleware  <-- SHIELD-001: Add CSP header here
    |
    v
OriginCheckMiddleware      (no changes -- SHIELD-006 risk-accepted)
    |
    v
AuthMiddleware             <-- SHIELD-009: Periodic disabled warning here
    |
    v
Router dispatch
    |
    +-> POST /login        <-- SHIELD-003: Rate limiter check before auth
    |   |                      SHIELD-005: Sanitize failure log
    |   v
    |   login_post()
    |
    +-> POST /setup        <-- SHIELD-011: Sanitize completion log
    |   v
    |   setup_post()
    |
    +-> GET /settings      <-- SHIELD-002: Stop passing raw API key
    |   v
    |   settings_page()
    |   |
    |   v
    |   security_apikey.html  <-- Template: show placeholder, not key
    |
    +-> save_settings()    (URL validation)
        |
        v
        validate_arr_url() <-- SHIELD-007: IPv6 mapped address check
```

### Pattern 1: In-Memory Sliding Window Rate Limiter

**What:** Module-level dict tracking failed login timestamps per IP. On each login attempt, prune expired entries (older than window), count remaining, reject if over threshold.

**When to use:** Single-process apps where persistence is unnecessary.

**Example:**
```python
# Source: D-01, D-02, D-03 from CONTEXT.md
import time

_login_failures: dict[str, list[float]] = {}
_MAX_ATTEMPTS = 10
_WINDOW_SECONDS = 300  # 5 minutes

def _check_rate_limit(ip: str) -> tuple[bool, int]:
    """Check if IP is rate-limited. Returns (is_limited, retry_after_seconds)."""
    now = time.monotonic()
    timestamps = _login_failures.get(ip, [])
    # Prune expired entries
    timestamps = [t for t in timestamps if now - t < _WINDOW_SECONDS]
    _login_failures[ip] = timestamps
    if len(timestamps) >= _MAX_ATTEMPTS:
        oldest = min(timestamps)
        retry_after = int(_WINDOW_SECONDS - (now - oldest)) + 1
        return (True, retry_after)
    return (False, 0)

def _record_failure(ip: str) -> None:
    """Record a failed login attempt for rate limiting."""
    now = time.monotonic()
    if ip not in _login_failures:
        _login_failures[ip] = []
    _login_failures[ip].append(now)
```

[VERIFIED: `time.monotonic()` tested on this system, returns float]

**Key design notes:**
- Use `time.monotonic()` not `time.time()` -- monotonic clock is immune to system clock changes [VERIFIED: Python docs]
- Prune on every check to prevent unbounded memory growth
- The `retry_after` calculation gives the user a meaningful "try again in X minutes" message per D-02
- Module-level dict means state is per-process, resets on restart (acceptable per D-03)

### Pattern 2: CSP Header Addition

**What:** Single line addition to existing SecurityHeadersMiddleware.

**Example:**
```python
# Source: D-07, D-08, D-09
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'"
)
```

[ASSUMED: `unsafe-inline` is needed for htmx inline event handlers and Tailwind v4 inline styles. Verified by user decision D-08.]

**Note on X-Frame-Options:** The existing `X-Frame-Options: SAMEORIGIN` (line 33) should be updated to `DENY` to match `frame-ancestors 'none'` in CSP, OR removed since CSP `frame-ancestors` supersedes it. Per D-09, the CSP directive is the canonical one. Keep X-Frame-Options as `DENY` for browsers that don't support CSP Level 2.

### Pattern 3: API Key Exposure Fix

**What:** Change route context from raw key to boolean, update template to show placeholder.

**Current code** (routes.py line 401):
```python
"auth_api_key": settings.auth.api_key.get_secret_value(),
```

**Fix:**
```python
"auth_api_key_set": bool(settings.auth.api_key.get_secret_value()),
```

**Template change** (security_apikey.html):
- Currently line 5: `{% set display_key = auth_api_key if auth_api_key is defined else "" %}`
- The revealed path (line 2-3) uses `api_key` from the regeneration endpoint context -- this path is unaffected
- Non-revealed path needs to show a masked placeholder like `"********************************"` instead of the real key

[VERIFIED: Current template at `triggarr/templates/partials/security_apikey.html` lines 1-6]

**Copy button behavior:** The copy button currently reads `input.value` which contains the real key from server-rendered HTML. After this fix, the copy button should either be hidden when the key is not revealed, or show a tooltip saying "Regenerate to reveal key". The toggle-visibility eye icon also needs updating -- it currently toggles between password/text type, but after this fix the value itself is just asterisks.

### Pattern 4: IPv4-Mapped IPv6 Validation

**What:** Extend `validate_arr_url` to check IPv4-mapped IPv6 addresses against the same blocklist.

**Example:**
```python
# Source: D-10, validated against Python ipaddress module
try:
    addr = ipaddress.ip_address(hostname)
    if addr.is_link_local or addr.is_loopback or addr.is_unspecified or addr.is_multicast:
        return (False, "Blocked address")
    # Check IPv4-mapped IPv6 addresses (e.g., ::ffff:127.0.0.1)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        mapped = addr.ipv4_mapped
        if mapped.is_link_local or mapped.is_loopback or mapped.is_unspecified or mapped.is_multicast:
            return (False, "Blocked address")
except ValueError:
    pass
```

[VERIFIED: `ipaddress.IPv6Address('::ffff:127.0.0.1').ipv4_mapped.is_loopback` returns `True` -- tested on this system]
[VERIFIED: `ipaddress.IPv6Address('::ffff:169.254.169.254').ipv4_mapped.is_link_local` returns `True` -- tested on this system]

### Pattern 5: Auth-Disabled Periodic Warning

**What:** Replace one-time `_disabled_warned` flag with periodic logging.

**Current code** (middleware.py lines 82, 102-107):
```python
_disabled_warned: bool = False
...
if not AuthMiddleware._disabled_warned:
    logger.warning("Authentication is disabled...")
    AuthMiddleware._disabled_warned = True
```

**Fix approach:** Use a timestamp instead of boolean. Log the warning if more than N seconds have elapsed since the last warning. The design spec says "every 60 seconds" (LOGIN-05).

```python
_disabled_warned_at: float = 0.0
_DISABLED_WARN_INTERVAL = 60.0  # seconds

# In dispatch:
now = time.monotonic()
if now - AuthMiddleware._disabled_warned_at >= _DISABLED_WARN_INTERVAL:
    logger.warning("Authentication is disabled...")
    AuthMiddleware._disabled_warned_at = now
```

**Test impact:** `tests/conftest.py` line 13-17 resets `_disabled_warned` before each test. This fixture needs updating to reset `_disabled_warned_at = 0.0` instead. Test `test_disabled_mode_logs_warning` in `test_auth_middleware.py:480` checks for the warning -- should still pass with periodic logging.

### Anti-Patterns to Avoid
- **Leaking state across test runs:** Rate limiter module-level dict persists between tests. Add a `_reset_rate_limiter()` helper and call it in conftest.py, or clear the dict in test fixtures.
- **time.time() for rate limiting:** System clock can be adjusted; always use `time.monotonic()`.
- **Blocking the event loop in rate limiter:** The rate limiter is pure dict operations, no I/O -- this is fine. Do NOT add `asyncio.sleep()` delays in the rate limit check itself (the sleep in the Shield proposal is for after failed auth, which is a separate concern).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limiting | Redis/external store | Module-level dict + time.monotonic() | Single-process homelab app, persistence unnecessary per D-03 |
| CSP generation | CSP builder library | String literal | Policy is static, one line, no dynamic content |
| IPv6 validation | Custom parsing | Python `ipaddress` stdlib | Battle-tested stdlib handles all edge cases |

## Common Pitfalls

### Pitfall 1: Template Variable Name Mismatch After API Key Fix
**What goes wrong:** The `security_apikey.html` partial uses `auth_api_key` in non-revealed path and `api_key` in revealed path. Renaming the context variable to `auth_api_key_set` (boolean) will break the non-revealed display unless the template is updated to use a placeholder string.
**Why it happens:** Two different rendering paths (settings page load vs. post-regen htmx swap) pass different context variables.
**How to avoid:** Trace both rendering paths: (1) `settings_page()` in routes.py passes context for full page load, (2) `regenerate_api_key_endpoint()` passes context for htmx partial swap with `revealed=True`. Only path (1) changes.
**Warning signs:** API key section shows empty input instead of placeholder after fix.

### Pitfall 2: Rate Limiter Memory Growth
**What goes wrong:** If stale entries are never pruned, the `_login_failures` dict grows unboundedly under sustained attack from many IPs.
**Why it happens:** Only pruning on check for a specific IP doesn't clean other IPs' entries.
**How to avoid:** Also prune globally on a periodic basis, or limit total dict size. For a homelab app, pruning on each check is sufficient -- attack surface is very limited.
**Warning signs:** Memory usage growing over time in long-running instances.

### Pitfall 3: conftest.py Fixture Not Updated
**What goes wrong:** Existing `_reset_disabled_warned` fixture in `tests/conftest.py` resets `AuthMiddleware._disabled_warned = False`. After changing to `_disabled_warned_at`, this fixture silently does nothing (sets a non-existent attribute), causing test pollution.
**Why it happens:** Python allows setting arbitrary attributes on classes without error.
**How to avoid:** Update conftest.py to reset `_disabled_warned_at = 0.0`. Add a rate limiter reset fixture too.
**Warning signs:** Tests pass individually but fail when run together.

### Pitfall 4: CSP Breaking htmx Functionality
**What goes wrong:** CSP `script-src` without `unsafe-inline` blocks htmx inline event handlers like `hx-trigger`, `hx-get`, etc.
**Why it happens:** htmx uses inline event handler attributes which are treated as inline scripts by strict CSP.
**How to avoid:** D-08 correctly specifies `'unsafe-inline'` for script-src. Verify by loading the settings page and dashboard after CSP is added.
**Warning signs:** Console errors like "Refused to execute inline event handler" in browser dev tools.

### Pitfall 5: X-Frame-Options Inconsistency
**What goes wrong:** Current code sets `X-Frame-Options: SAMEORIGIN` (line 33) but CSP will set `frame-ancestors 'none'`. These contradict each other.
**Why it happens:** X-Frame-Options predates CSP frame-ancestors. Browsers use CSP when both are present, but the inconsistency is confusing.
**How to avoid:** Update X-Frame-Options to `DENY` to match `frame-ancestors 'none'`.

## Code Examples

### Log Sanitization (SHIELD-005)

**Current** (routes.py line 1158):
```python
logger.warning("Login failed for user {username}", username=username)
```

**Fix:**
```python
logger.warning(
    "Login failed: username_match={matched}",
    matched=bool(username and secrets.compare_digest(username, auth.username)),
)
```
[VERIFIED: Current code at routes.py:1158]

Note: Use `secrets.compare_digest` for the match check to avoid timing oracle -- consistent with existing pattern at line 1139.

### Log Sanitization (SHIELD-011)

**Current** (routes.py line 1099):
```python
logger.info("Setup completed for user {username}", username=username)
```

**Fix:**
```python
logger.info("Setup completed")
```
[VERIFIED: Current code at routes.py:1099]

### Changelog Comment (SHIELD-010)

Add comment above `parse_changelog` function:
```python
def parse_changelog(text: str, *, latest_only: bool = False) -> str:
    """Parse changelog markdown text into HTML.

    Security boundary: All user-visible text is passed through html.escape()
    before insertion into HTML output. This function returns HTMLResponse
    content that bypasses Jinja2 autoescape, so the html.escape() calls
    on lines 101, 112, and 124 are the sole XSS defense. Any new text
    insertion MUST also use html.escape().
    ...
```
[VERIFIED: html.escape() calls at changelog.py lines 101, 112, 124]

### .gitleaksignore File

```
# Test fixture API keys -- not real credentials
tests/test_auth_middleware.py
tests/test_auth_routes.py
tests/test_auth_integration.py
tests/test_auth_config.py
```
[VERIFIED: gitleaks findings reference these test files]

## Test Impact Analysis

### Files Requiring Test Updates

| Test File | What Changes | Why |
|-----------|-------------|-----|
| `tests/conftest.py` | Reset `_disabled_warned_at` instead of `_disabled_warned`; add rate limiter reset | Fixture name change + new module state |
| `tests/test_auth_middleware.py` | Update `test_disabled_mode_logs_warning` for periodic behavior; add CSP header test | SHIELD-009 behavior change; SHIELD-001 new header |
| `tests/test_auth_routes.py` | Add rate limiter tests (10 attempts, 429 response, window expiry); update settings context assertion for `auth_api_key_set` | SHIELD-003 new behavior; SHIELD-002 context change |
| `tests/test_validation.py` | Add IPv4-mapped IPv6 tests, multicast tests | SHIELD-007 new validation |
| `tests/test_middleware.py` | Add CSP header assertion to existing security headers test | SHIELD-001 |

### New Tests Needed

| Test | Validates |
|------|-----------|
| Rate limit: 10 failures then 429 | D-01 core behavior |
| Rate limit: window expiry allows retry | D-01 window mechanics |
| Rate limit: successful login not counted | Only failures tracked |
| Rate limit: error message in HTML response | D-02 UX requirement |
| CSP header present on responses | SHIELD-001 |
| Settings page does NOT contain raw API key | SHIELD-002 |
| Settings page has `auth_api_key_set` boolean | D-04 |
| IPv6 mapped loopback blocked | SHIELD-007 |
| IPv6 mapped link-local blocked | SHIELD-007 |
| Multicast address blocked | SHIELD-007 |
| Login failure log does not contain username | SHIELD-005 |
| Setup log does not contain username | SHIELD-011 |

### Existing Tests That Must Still Pass

All 774 tests currently pass. Key tests to watch:
- `test_auth_routes.py`: Tests that assert on settings page context keys will break when `auth_api_key` changes to `auth_api_key_set`
- `test_auth_middleware.py:test_disabled_mode_logs_warning`: Will need update for periodic warning
- `test_validation.py`: Existing SSRF tests must still pass after IPv6 additions

[VERIFIED: 774 tests pass as of research time]

## Implementation Dependencies (Ordering)

```
Independent (can be done in any order):
  SHIELD-001 (CSP header)          -- middleware.py only
  SHIELD-005 (login log)           -- routes.py only
  SHIELD-011 (setup log)           -- routes.py only
  SHIELD-010 (changelog comment)   -- changelog.py only
  SHIELD-009 (disabled warning)    -- middleware.py + conftest.py

Depends on nothing but has template coupling:
  SHIELD-002 (API key exposure)    -- routes.py + security_apikey.html + test updates

Independent:
  SHIELD-003 (rate limiter)        -- routes.py + new tests + conftest.py
  SHIELD-007 (SSRF IPv6)           -- validation.py + test updates

Housekeeping (do last):
  SHIELD-004 (test fixtures)       -- .gitleaksignore + optional test renames
  SHIELD-006, 008 (risk-accepted)  -- no code changes, just documentation
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `unsafe-inline` is needed for htmx inline event handlers | Architecture Patterns (CSP) | CSP could break htmx functionality; easily testable in browser |
| A2 | `unsafe-inline` is needed for Tailwind v4 inline styles | Architecture Patterns (CSP) | Styles might not render; easily testable |
| A3 | X-Frame-Options should change from SAMEORIGIN to DENY to match frame-ancestors 'none' | Pitfall 5 | Minor inconsistency if wrong; browsers prefer CSP anyway |

## Open Questions

1. **Copy button behavior after API key masking**
   - What we know: Currently `copyApiKey()` copies `input.value` which is the real key. After fix, value will be a placeholder.
   - What's unclear: Should the copy button be hidden entirely when key is not revealed, or show a "not available" tooltip?
   - Recommendation: Hide the copy and eye-toggle buttons when `auth_api_key_set` is true but no revealed key. Show text like "Key hidden. Regenerate to reveal." This matches D-05 (reveal-on-regen only).

2. **Rate limiter test isolation**
   - What we know: Module-level dict persists between tests.
   - What's unclear: Best way to expose reset for testing -- function, or direct dict clear?
   - Recommendation: Add `_reset_rate_limiter()` function, call from conftest autouse fixture.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (asyncio_mode=auto) |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Finding | Behavior | Test Type | Automated Command | File Exists? |
|---------|----------|-----------|-------------------|-------------|
| SHIELD-001 | CSP header in responses | unit | `uv run pytest tests/test_middleware.py -x -q` | Yes (update) |
| SHIELD-002 | No raw API key in settings HTML | unit | `uv run pytest tests/test_auth_routes.py -x -q` | Yes (update) |
| SHIELD-003 | Rate limit after 10 failures | unit | `uv run pytest tests/test_auth_routes.py -x -q` | No (new tests) |
| SHIELD-004 | gitleaks clean | manual | `gitleaks detect --no-git` | N/A |
| SHIELD-005 | No username in login failure log | unit | `uv run pytest tests/test_auth_routes.py -x -q` | No (new test) |
| SHIELD-007 | IPv6 mapped addresses blocked | unit | `uv run pytest tests/test_validation.py -x -q` | Yes (extend) |
| SHIELD-009 | Periodic disabled warning | unit | `uv run pytest tests/test_auth_middleware.py -x -q` | Yes (update) |
| SHIELD-010 | Comment in parse_changelog | manual | code review | N/A |
| SHIELD-011 | No username in setup log | unit | `uv run pytest tests/test_auth_routes.py -x -q` | No (new test) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] Rate limiter test fixtures (reset function + conftest autouse)
- [ ] conftest.py update for `_disabled_warned_at` reset

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | Rate limiting (SHIELD-003), log sanitization (SHIELD-005, 011) |
| V3 Session Management | No (risk-accepted SHIELD-008) | Existing 30-day expiry |
| V4 Access Control | No (risk-accepted SHIELD-006) | Existing OriginCheckMiddleware |
| V5 Input Validation | Yes | SSRF hardening (SHIELD-007) |
| V6 Cryptography | No | No crypto changes |
| V14 Configuration | Yes | CSP header (SHIELD-001), security headers |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Brute-force login | Elevation of Privilege | Rate limiting (D-01) |
| API key exfiltration via XSS | Information Disclosure | Remove key from HTML (D-04) + CSP (D-07) |
| SSRF via IPv6 bypass | Tampering | IPv4-mapped validation (D-10) |
| Log injection via username | Tampering | Remove user input from logs (D-11, D-12) |
| Clickjacking | Spoofing | frame-ancestors 'none' (D-09) |

## Sources

### Primary (HIGH confidence)
- `triggarr/web/middleware.py` -- current SecurityHeadersMiddleware, AuthMiddleware implementation
- `triggarr/web/routes.py` -- current login, setup, settings route implementations
- `triggarr/web/validation.py` -- current SSRF validation
- `triggarr/templates/partials/security_apikey.html` -- current API key template
- `triggarr/changelog.py` -- current parse_changelog with html.escape
- `tests/conftest.py` -- current test fixtures
- `reports/security-2026-04-15.md` -- Shield assessment findings
- Python `ipaddress` module -- verified IPv4-mapped behavior on this system

### Secondary (MEDIUM confidence)
- `docs/superpowers/specs/2026-04-14-built-in-auth-design.md` -- auth design spec

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all stdlib
- Architecture: HIGH -- all changes are small modifications to existing well-understood code
- Pitfalls: HIGH -- traced all code paths, identified template coupling and test fixture issues

**Research date:** 2026-04-15
**Valid until:** 2026-05-15 (stable -- no external dependencies or fast-moving APIs)
