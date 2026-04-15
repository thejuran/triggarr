---
phase: 56-first-run-setup-login
plan: 01
subsystem: auth-routes
tags: [auth, security, tdd, open-redirect, settings-serialization]
dependency_graph:
  requires: []
  provides: [_safe_next_url, _settings_to_dict-auth-extension]
  affects: [login-route, setup-route, settings-save]
tech_stack:
  added: []
  patterns: [open-redirect-prevention, secretstr-extraction]
key_files:
  created:
    - tests/test_auth_routes.py
  modified:
    - triggarr/web/routes.py
decisions:
  - "_safe_next_url uses startswith-based rejection (no urllib parse) for simplicity and security"
  - "Auth section placed after app instances loop in _settings_to_dict for logical grouping"
metrics:
  duration: 108s
  completed: "2026-04-15T02:02:10Z"
  tasks: 1
  files: 2
---

# Phase 56 Plan 01: TDD _safe_next_url and _settings_to_dict Auth Extension Summary

TDD pure functions: _safe_next_url blocks open redirect attacks on ?next= param; _settings_to_dict auth extension prevents credential loss on settings save.

## Task Summary

| Task | Name | Commit(s) | Files |
|------|------|-----------|-------|
| 1 (RED) | Failing tests for _safe_next_url and _settings_to_dict auth | 63e65df | tests/test_auth_routes.py |
| 1 (GREEN) | Implement _safe_next_url and _settings_to_dict auth extension | 6475d87 | triggarr/web/routes.py, tests/test_auth_routes.py |

## What Was Built

### _safe_next_url(next_param: str | None) -> str

Open redirect prevention for the `?next=` login parameter. Rejects:
- Absolute URLs (`http://`, `https://`)
- Protocol-relative URLs (`//`)
- Backslash URLs (`\`)
- Non-slash-prefixed paths (e.g., `settings` without leading `/`)

Returns the original path unchanged if valid, or `/` as safe fallback.

### _settings_to_dict auth extension

Extended the existing `_settings_to_dict` function to include the `auth` section when serializing Settings to TOML-compatible dict. Extracts `SecretStr` values (`password_hash`, `api_key`, `session_secret`) to plain strings at the serialization boundary. Prevents Pitfall 6 where a settings save after setup would strip the `[auth]` section from TOML.

## Test Coverage

- 9 tests for `_safe_next_url` (None, empty, valid relative, valid with query, http, https, protocol-relative, backslash, no-slash-prefix)
- 3 tests for `_settings_to_dict` auth (configured auth, default unconfigured, regression for existing radarr behavior)
- 12 new tests total, 726 full suite green

## TDD Gate Compliance

- RED gate: `test(56-01)` commit 63e65df -- tests fail with ImportError (function not yet implemented)
- GREEN gate: `feat(56-01)` commit 6475d87 -- all 12 tests pass
- REFACTOR gate: skipped (functions are minimal, no cleanup needed)

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

- `uv run pytest tests/test_auth_routes.py -x -q` -- 12 passed
- `uv run pytest tests/ -x -q` -- 726 passed
- `uv run ruff check triggarr/web/routes.py tests/test_auth_routes.py` -- all checks passed

## Self-Check: PASSED

All files exist, all commits found, all content markers verified.
