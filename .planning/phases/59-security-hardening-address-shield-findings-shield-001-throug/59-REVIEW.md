---
phase: 59-security-hardening
reviewed: 2026-04-15T12:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - .gitleaksignore
  - tests/conftest.py
  - tests/test_auth_middleware.py
  - tests/test_auth_routes.py
  - tests/test_middleware.py
  - tests/test_validation.py
  - triggarr/changelog.py
  - triggarr/templates/partials/security_apikey.html
  - triggarr/web/middleware.py
  - triggarr/web/routes.py
  - triggarr/web/validation.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 59: Code Review Report

**Reviewed:** 2026-04-15T12:00:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 59 implements security hardening across multiple SHIELD findings: rate limiting on POST /login, SSRF hardening (IPv4-mapped IPv6 and multicast blocking), CSP/X-Frame-Options headers, auth-disabled periodic warnings, API key exposure fix (boolean flag instead of raw key), login failure log sanitization, and .gitleaksignore for test fixtures.

The implementation is solid overall. The SSRF hardening in `validation.py` correctly handles IPv4-mapped IPv6 addresses and multicast ranges. The rate limiter logic is correct and well-tested. CSP headers and X-Frame-Options are properly set. The API key exposure fix correctly passes a boolean to templates instead of the raw key. Log sanitization removes usernames from failure logs.

Two warnings found: the in-memory rate limiter dict has no upper bound on tracked IPs (potential resource exhaustion under sustained attack), and the successful login log still includes the plaintext username which is inconsistent with the sanitization goal for failure logs. Two informational items noted.

## Warnings

### WR-01: Rate limiter dict has no eviction bound for tracked IPs

**File:** `triggarr/web/routes.py:1130`
**Issue:** `_login_failures` is a plain `dict[str, list[float]]` with no upper bound on the number of tracked IPs. While expired timestamps within each IP are pruned during `_check_rate_limit`, the IP keys themselves are never evicted. An attacker rotating source IPs can grow this dict without limit. In a Docker container with constrained memory, sustained distributed brute-force could exhaust memory over time.
**Fix:** Add a maximum IP count with LRU eviction. For example, cap at 10,000 entries and evict the oldest when exceeded:
```python
_MAX_TRACKED_IPS = 10_000

def _record_failure(ip: str) -> None:
    """Record a failed login attempt for rate limiting."""
    now = time.monotonic()
    if ip not in _login_failures:
        # Evict oldest entry if at capacity
        if len(_login_failures) >= _MAX_TRACKED_IPS:
            oldest_ip = min(_login_failures, key=lambda k: _login_failures[k][-1] if _login_failures[k] else 0)
            del _login_failures[oldest_ip]
        _login_failures[ip] = []
    _login_failures[ip].append(now)
```

### WR-02: Successful login log leaks plaintext username

**File:** `triggarr/web/routes.py:1204`
**Issue:** The success log `logger.info("Login successful for user {username}", username=username)` emits the actual username in cleartext. While SHIELD-005 correctly sanitized the *failure* log (line 1209-1211) to avoid leaking usernames, the *success* log still includes it. If the redacting sink is not yet configured to redact usernames (it targets API keys and passwords), usernames appear in log output. This is inconsistent with the sanitization goal.
**Fix:** Log success without the username, or use a generic marker:
```python
logger.info("Login successful")
```

## Info

### IN-01: Short-circuit in credential check leaks username validity via timing

**File:** `triggarr/web/routes.py:1186-1191`
**Issue:** The credential verification uses Python's `and` short-circuit: `username and password and secrets.compare_digest(username, auth.username) and verify_password(...)`. If `username` is empty or `password` is empty, `verify_password` (bcrypt) is never called, making the response measurably faster (~0.1s vs ~0.3s). An attacker can distinguish empty vs non-empty credentials by timing. This is low severity since the login form UX makes it obvious, and the rate limiter mitigates automated exploitation.
**Fix:** Consider always running `verify_password` against a dummy hash when credentials are empty to normalize timing, or accept this as low risk given the rate limiter.

### IN-02: Test file uses module-level TestClient instantiation

**File:** `tests/test_middleware.py:31`
**Issue:** `client = TestClient(_make_app())` is instantiated at module import time rather than in a fixture or per-test. This works but means the test app is shared across all tests in the first group, which could cause subtle order-dependent issues if middleware state is ever added.
**Fix:** Move to a fixture or per-test instantiation for isolation, matching the pattern used in other test files.

---

_Reviewed: 2026-04-15T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
