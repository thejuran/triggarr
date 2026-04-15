---
phase: 59-security-hardening
plan: 01
subsystem: auth/rate-limiting
tags: [security, rate-limiting, brute-force-protection, tdd]
dependency_graph:
  requires: []
  provides: [login-rate-limiter, _check_rate_limit, _record_failure, _reset_rate_limiter]
  affects: [triggarr/web/routes.py, tests/test_auth_routes.py, tests/conftest.py]
tech_stack:
  added: []
  patterns: [sliding-window-rate-limit, module-level-dict, monotonic-timestamps]
key_files:
  created: []
  modified:
    - triggarr/web/routes.py
    - tests/test_auth_routes.py
    - tests/conftest.py
decisions:
  - "Module-level dict with time.monotonic() for sliding window -- simple, no dependencies, resets on restart"
  - "Rate check before credential verification -- prevents timing oracle on rate-limited requests"
  - "retry_after rounded up to nearest minute for user-friendly display"
metrics:
  duration: "3m 18s"
  completed: "2026-04-15T20:39:00Z"
  tasks: 1
  tests_added: 13
  tests_total: 786
  files_modified: 3
---

# Phase 59 Plan 01: TDD In-Memory Sliding Window Rate Limiter Summary

In-memory sliding window rate limiter on POST /login with 10-attempt/5-minute window per IP, implemented via TDD with 13 new tests covering unit helpers and route integration.

## Task Completion

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing rate limiter tests | 6805873 | tests/test_auth_routes.py, tests/conftest.py |
| 1 (GREEN) | Rate limiter implementation | 0297627 | triggarr/web/routes.py, tests/test_auth_routes.py |

## TDD Gate Compliance

- RED gate: `test(59-01)` commit 6805873 -- 13 tests written, all fail (ImportError)
- GREEN gate: `feat(59-01)` commit 0297627 -- all 13 rate limit tests pass, 786 total tests pass
- REFACTOR gate: skipped (code clean, no refactoring needed)

## What Was Built

### Rate Limiter Helpers (routes.py)

- `_login_failures: dict[str, list[float]]` -- module-level sliding window storage
- `_MAX_ATTEMPTS = 10` -- threshold before blocking
- `_WINDOW_SECONDS = 300` -- 5-minute sliding window
- `_check_rate_limit(ip)` -- prunes expired timestamps, returns (is_limited, retry_after_seconds)
- `_record_failure(ip)` -- appends time.monotonic() timestamp
- `_reset_rate_limiter()` -- clears all state (used by test fixture)

### Login Route Integration

- Rate check runs BEFORE credential verification in `login_post`
- Uses `request.client.host` for IP (direct connection IP, not X-Forwarded-For)
- Rate-limited response: 200 with login.html containing "Too many login attempts, try again in N minutes"
- Successful logins not counted toward rate limit
- Failed logins call `_record_failure(client_ip)` after credential check

### Test Coverage

- 8 unit tests for helper functions (check, record, reset, window expiry via monkeypatch)
- 4 integration tests for POST /login (10-failure threshold, under-threshold, successful-not-counted, blocked-before-credential-check)
- 1 conftest autouse fixture (_reset_rate_limit_state) ensures test isolation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing `import time` in test file**
- Found during: GREEN phase
- Issue: test_window_expiry_allows_retry used `time.monotonic` monkeypatch but `time` was not imported
- Fix: Added `import time` to test file imports
- Files modified: tests/test_auth_routes.py

**2. [Rule 1 - Bug] Unused import in test file**
- Found during: GREEN phase
- Issue: `import triggarr.web.routes as routes_mod` was unused (ruff F401)
- Fix: Removed unused import line
- Files modified: tests/test_auth_routes.py

## Decisions Made

1. **Module-level dict over external store**: Sliding window uses `dict[str, list[float]]` with `time.monotonic()` -- no Redis/SQLite dependency, resets on restart (acceptable for homelab single-user app per T-59-02 accept disposition)
2. **Rate check before credential verification**: Prevents timing oracle that could reveal whether a username exists when rate-limited
3. **Retry-after rounded to minutes**: `(retry_after + 59) // 60` gives user-friendly "try again in N minutes" message

## Verification

```
uv run pytest tests/test_auth_routes.py -x -q -k "rate" -> 13 passed
uv run pytest tests/ -x -q -> 786 passed
uv run ruff check triggarr/web/routes.py tests/test_auth_routes.py tests/conftest.py -> All checks passed
```

## Known Stubs

None.

## Self-Check: PASSED

- routes.py: FOUND
- test_auth_routes.py: FOUND
- conftest.py: FOUND
- Commit 6805873 (RED): FOUND
- Commit 0297627 (GREEN): FOUND
