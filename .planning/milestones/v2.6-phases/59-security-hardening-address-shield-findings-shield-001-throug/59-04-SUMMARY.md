---
phase: 59-security-hardening
plan: 04
subsystem: web/auth
tags: [security, api-key-masking, log-sanitization, gitleaks]
dependency_graph:
  requires: [59-01]
  provides: [masked-api-key-settings, sanitized-auth-logs, gitleaks-suppression]
  affects: [triggarr/web/routes.py, triggarr/templates/partials/security_apikey.html]
tech_stack:
  added: []
  patterns: [boolean-flag-over-secret-passthrough, log-sanitization-via-boolean-match]
key_files:
  created:
    - .gitleaksignore
  modified:
    - triggarr/web/routes.py
    - triggarr/templates/partials/security_apikey.html
    - tests/test_auth_routes.py
decisions:
  - "Use auth_api_key_set boolean instead of passing raw API key to template context"
  - "Login failure log uses username_match boolean via secrets.compare_digest, not raw username"
  - "Setup completion log is fully generic with no user-controlled parameters"
  - "Eye-toggle and copy buttons hidden when API key is not revealed (asterisks only)"
metrics:
  duration: ~8m
  completed: 2026-04-15T21:00:31Z
  tasks: 2/2
  files: 4
---

# Phase 59 Plan 04: API Key Exposure Fix, Log Sanitization, and Gitleaks Suppression Summary

API key removed from settings template context (replaced with boolean), login/setup logs sanitized to exclude user-controlled strings, template shows masked placeholder with hidden controls when key not revealed, .gitleaksignore suppresses test fixture false positives.

## Task Summary

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | API key exposure fix + log sanitization in routes.py | 31e2f06 | triggarr/web/routes.py, tests/test_auth_routes.py |
| 2 | API key template masking + .gitleaksignore | ad7b7bf | triggarr/templates/partials/security_apikey.html, .gitleaksignore |

## Changes Made

### Task 1: API Key Exposure Fix + Log Sanitization

**API key exposure (D-04, D-05, D-06 / SHIELD-002):**
- Changed `"auth_api_key": settings.auth.api_key.get_secret_value()` to `"auth_api_key_set": bool(settings.auth.api_key.get_secret_value())` in settings_page template context
- Raw API key value no longer appears anywhere in settings page HTML

**Login failure log sanitization (D-11 / SHIELD-005):**
- Changed `logger.warning("Login failed for user {username}", username=username)` to use `username_match={matched}` with `bool(username and secrets.compare_digest(username, auth.username))`
- Attacker-controlled usernames no longer appear in log output

**Setup completion log sanitization (D-12 / SHIELD-011):**
- Changed `logger.info("Setup completed for user {username}", username=username)` to generic `logger.info("Setup completed")`

**Tests added (4 new tests):**
- `test_settings_page_context_uses_api_key_set_boolean` - verifies raw API key absent from HTML
- `test_settings_page_does_not_leak_raw_api_key` - verifies unique key string absent from response
- `test_login_failure_log_contains_username_match_not_raw_username` - verifies log sanitization
- `test_setup_completion_log_is_generic` - verifies generic setup log

### Task 2: Template Masking + Gitleaks Suppression

**Template update (SHIELD-002 template side):**
- Non-revealed path now shows `"********************************"` placeholder when `auth_api_key_set` is true, empty string when false
- Eye-toggle button wrapped in `{% if is_revealed %}` conditional - hidden when key is masked
- Copy button wrapped in `{% if is_revealed %}` conditional - hidden when key is masked
- Added helper text: "Key hidden. Regenerate to reveal." when key is set but not revealed
- Revealed path (from regen endpoint with `api_key` context var) unchanged

**Gitleaks suppression (D-13 / SHIELD-004):**
- Created `.gitleaksignore` with test file paths containing fixture API keys

## Deviations from Plan

None - plan executed exactly as written.

## Verification

- 798 tests passing (59 in test_auth_routes.py, including 4 new)
- ruff check: All checks passed
- No raw API key values in settings page HTML
- Log messages contain no user-controlled strings

## Decisions Made

1. **Boolean flag over secret passthrough**: Settings template receives `auth_api_key_set: bool` instead of the raw key string. The revealed path (after regeneration) still passes the actual key via a separate `api_key` context variable from the regen endpoint.
2. **secrets.compare_digest for log boolean**: Login failure log uses `secrets.compare_digest` to compute the `username_match` boolean, maintaining constant-time comparison even in the log path.

## TDD Gate Compliance

Task 1 used TDD flow. Tests were written to assert the new behavior (auth_api_key_set boolean, sanitized logs), confirmed they would fail against old code (raw API key in context, raw username in logs), then implementation was applied and all tests passed.

- RED: 4 failing tests targeting all three security changes
- GREEN: Implementation in routes.py, all tests pass
- Combined into single commit due to tight coupling

## Self-Check: PASSED

- All 4 key files exist on disk
- Commits 31e2f06 and ad7b7bf verified in git log
- 798 tests passing, ruff clean
