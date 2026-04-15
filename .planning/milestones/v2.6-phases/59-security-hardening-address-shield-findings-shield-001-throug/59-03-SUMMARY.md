---
phase: 59-security-hardening
plan: 03
subsystem: security-headers/auth-warning
tags: [security, csp, x-frame-options, auth-warning, xss-documentation]
dependency_graph:
  requires: [59-01]
  provides: [csp-header, x-frame-deny, periodic-auth-warning, changelog-security-docs]
  affects: [triggarr/web/middleware.py, triggarr/changelog.py, tests/test_middleware.py, tests/test_auth_middleware.py, tests/conftest.py]
tech_stack:
  added: []
  patterns: [monotonic-timestamp-interval, csp-header-middleware]
key_files:
  created: []
  modified:
    - triggarr/web/middleware.py
    - triggarr/changelog.py
    - tests/test_middleware.py
    - tests/test_auth_middleware.py
    - tests/conftest.py
decisions:
  - "CSP uses unsafe-inline for script-src and style-src because htmx requires inline scripts"
  - "time.monotonic for periodic warning interval -- not wall clock, immune to NTP jumps"
metrics:
  duration: "3m 40s"
  completed: "2026-04-15T20:55:00Z"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 3
  tests_total: 797
  files_modified: 5
---

# Phase 59 Plan 03: Security Headers + Auth Warning + Changelog Docs Summary

CSP header with frame-ancestors none, X-Frame-Options DENY, periodic auth-disabled warning every 60s via time.monotonic, and XSS security boundary documentation in parse_changelog docstring.

## Task Completion

| Task | Name | Type | Commit(s) | Files |
|------|------|------|-----------|-------|
| 1 (RED) | CSP + X-Frame-Options failing tests | tdd | 6607045 | tests/test_middleware.py |
| 1 (GREEN) | CSP + X-Frame-Options implementation | tdd | db877eb | triggarr/web/middleware.py |
| 2 | Auth-disabled periodic warning + conftest + changelog | auto | e2a47bb | triggarr/web/middleware.py, tests/conftest.py, tests/test_auth_middleware.py, triggarr/changelog.py |

## TDD Gate Compliance

- RED gate: `test(59-03)` commit 6607045 -- 3 tests written, CSP test fails with KeyError (header missing)
- GREEN gate: `feat(59-03)` commit db877eb -- all 11 middleware tests pass
- REFACTOR gate: skipped (implementation minimal, no cleanup needed)

## What Was Built

### SecurityHeadersMiddleware (D-07, D-08, D-09)

- Added `Content-Security-Policy` header to all responses:
  - `default-src 'self'` -- baseline restriction
  - `script-src 'self' 'unsafe-inline'` -- required for htmx inline scripts
  - `style-src 'self' 'unsafe-inline'` -- required for Tailwind inline styles
  - `img-src 'self' data:` -- allows data: URIs for inline images
  - `connect-src 'self'` -- restricts fetch/XHR to same origin
  - `frame-ancestors 'none'` -- prevents clickjacking (matches X-Frame-Options)
- Changed `X-Frame-Options` from `SAMEORIGIN` to `DENY` to match CSP frame-ancestors directive

### Auth-Disabled Periodic Warning (D-14)

- Replaced `_disabled_warned: bool` with `_disabled_warned_at: float` (monotonic timestamp)
- Added `_DISABLED_WARN_INTERVAL: float = 60.0` class constant
- Warning now fires every 60 seconds instead of only once at first request
- Uses `time.monotonic()` for interval tracking (immune to wall clock changes)
- Updated conftest.py fixture to reset `_disabled_warned_at = 0.0`
- Updated test to verify periodic behavior with mocked time (3 requests: t=100 logs, t=110 suppressed, t=200 logs again)

### Changelog Security Boundary Documentation (D-15)

- Added security boundary docstring to `parse_changelog` explaining that `html.escape()` is the sole XSS defense since the output bypasses Jinja2 autoescape

## Deviations from Plan

None -- plan executed exactly as written.

## Decisions Made

1. **CSP uses unsafe-inline**: htmx requires inline scripts and Tailwind uses inline styles; CSP still blocks external scripts/styles which is the primary vector
2. **time.monotonic for interval**: Not wall clock -- immune to NTP jumps, appropriate for interval measurement

## Verification

```
uv run pytest tests/test_middleware.py -x -q           -> 11 passed
uv run pytest tests/test_auth_middleware.py -x -q      -> 35 passed
uv run pytest tests/ -x -q                             -> 797 passed
uv run ruff check triggarr/web/middleware.py triggarr/changelog.py tests/ -> All checks passed
```

## Known Stubs

None.

## Self-Check: PASSED

- [x] triggarr/web/middleware.py contains `Content-Security-Policy`
- [x] triggarr/web/middleware.py contains `"DENY"`
- [x] triggarr/web/middleware.py does NOT contain `SAMEORIGIN`
- [x] triggarr/web/middleware.py contains `_disabled_warned_at`
- [x] triggarr/web/middleware.py contains `import time`
- [x] tests/conftest.py contains `_disabled_warned_at = 0.0`
- [x] triggarr/changelog.py contains `Security boundary`
- [x] Commit 6607045 (RED): FOUND
- [x] Commit db877eb (GREEN): FOUND
- [x] Commit e2a47bb (Task 2): FOUND
- [x] 797 tests pass
- [x] No ruff violations
