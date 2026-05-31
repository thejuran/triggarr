---
phase: 67-observability-csrf-test-coverage
plan: "03"
subsystem: tests
tags: [csrf, middleware, tests, security]
dependency_graph:
  requires: []
  provides: [TEST-01]
  affects: [tests/test_middleware.py]
tech_stack:
  added: []
  patterns: [TestClient with crafted headers, status-only assertion]
key_files:
  created: []
  modified:
    - tests/test_middleware.py
decisions:
  - "scheme-mismatch test asserts 200 (ALLOW) per D-10 — scheme not compared in OriginCheckMiddleware; single-origin model makes this safe"
  - "both-absent test (test_post_no_origin_no_referer_passes) retained unchanged — D-09"
  - "all assertions on response.status_code only — no coupling to middleware internals (D-12)"
metrics:
  duration: "3m"
  completed: "2026-05-31"
  tasks_completed: 1
  tasks_total: 1
---

# Phase 67 Plan 03: CSRF Scenario Tests for OriginCheckMiddleware Summary

## One-liner

Five TestClient-driven regression tests pin every ROADMAP-named CSRF scenario for OriginCheckMiddleware: missing-header allow paths, scheme-mismatch ALLOW (D-10 pinned), and spoofed-host 403 rejection (D-11).

## What Was Built

Added five new test functions to `tests/test_middleware.py` after the existing OriginCheck suite, before the DEBT-02 integration section:

| Function | Headers | Expected | Purpose |
|---|---|---|---|
| `test_post_missing_origin_with_matching_referer_passes` | Referer matching, no Origin | 200 | Lock missing-Origin allow path |
| `test_post_missing_referer_with_matching_origin_passes` | Origin matching, no Referer | 200 | Lock missing-Referer allow path |
| `test_post_scheme_mismatch_is_allowed` | `https://testserver` Origin vs `testserver` Host | 200 | Pin D-10 scheme-strip ALLOW |
| `test_post_suffix_spoof_returns_403` | `https://testserver.evil.com` Origin | 403 | D-11 suffix-spoof rejection |
| `test_post_port_mismatch_returns_403` | `http://testserver:8080` Origin | 403 | D-11 port-mismatch rejection |

All tests reuse the module-level `client = TestClient(_make_app())` harness. No new harness, no middleware state access.

The `test_post_scheme_mismatch_is_allowed` function includes a full explanatory docstring documenting the intentional scheme-stripping behavior and explicitly stating "Do NOT change this test to assert 403 — scheme comparison is intentionally absent from OriginCheckMiddleware (D-10)."

## Verification

- `uv run pytest tests/test_middleware.py -k "missing_origin or missing_referer or scheme_mismatch or suffix_spoof or port_mismatch or no_origin_no_referer" -x -q` — 6 passed (5 new + retained both-absent)
- `uv run pytest tests/test_middleware.py -x -q` — 17 passed (full suite)
- `uv run ruff check tests/test_middleware.py` — All checks passed
- `git diff --stat triggarr/web/middleware.py` — empty (middleware untouched, D-09)

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

No new threat surface introduced (pure test-only change, no production code modified).

## Self-Check: PASSED

- tests/test_middleware.py modified: FOUND
- Commit 0cb19c5 exists: FOUND
- triggarr/web/middleware.py unchanged: CONFIRMED (git diff --stat empty)
- All 17 tests pass: CONFIRMED
- Ruff clean: CONFIRMED
