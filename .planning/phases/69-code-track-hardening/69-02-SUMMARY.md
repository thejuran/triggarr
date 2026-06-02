---
phase: 69-code-track-hardening
plan: "02"
subsystem: dependencies, auth-middleware-tests
tags: [security, cve, starlette, fastapi, auth-middleware, regression-test]
dependency_graph:
  requires: []
  provides: [starlette>=1.0.1 resolved, PYSEC-2026-161 closed, BadHost regression test]
  affects: [pyproject.toml, uv.lock, tests/test_auth_middleware.py]
tech_stack:
  added: []
  patterns: [explicit direct starlette floor in pyproject.toml, Host-header regression test pattern]
key_files:
  created: []
  modified:
    - pyproject.toml
    - uv.lock
    - tests/test_auth_middleware.py
decisions:
  - "D-05 (corrected): Used explicit starlette>=1.0.1 as PRIMARY constraint alongside fastapi>=0.136.3; fastapi bump alone would not force the patched starlette since fastapi metadata only requires starlette>=0.46.0"
  - "D-06: Full test suite (966 tests) green + ruff clean after starlette 0.x->1.x major — breakage gate passed with no API surface issues"
  - "starlette resolved to 1.2.1 (uv resolved latest compatible, well above the 1.0.1 floor)"
  - "BadHost test uses TestClient follow_redirects=False + Assert(status=302) + Assert(location=/login?next=/settings) pattern mirroring test_unauth_browser_redirect_includes_next_deep_path"
metrics:
  duration: ~8 minutes
  completed: "2026-06-02T19:02:29Z"
  tasks_completed: 2
  files_changed: 3
---

# Phase 69 Plan 02: Starlette CVE Closure + BadHost Regression Guard Summary

**One-liner:** Explicit starlette>=1.0.1 floor closes PYSEC-2026-161 (Host-header auth-bypass class); BadHost regression test makes the property verifiable as a behavioral guarantee, not just a pip-audit result.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add starlette>=1.0.1 floor + fastapi>=0.136.3 pin, re-lock, verify breakage gate | 5bbe638 | pyproject.toml, uv.lock |
| 2 | Add BadHost/spoofed-Host regression test for PYSEC-2026-161 auth-bypass class | 79f5b8c | tests/test_auth_middleware.py |

## What Was Built

### Task 1: starlette CVE remediation (CHARD-04 / P68-FI-002)

`pyproject.toml` now carries:
- `"fastapi>=0.136.3"` — fastapi pin for starlette 1.x API compatibility (was bare `"fastapi"`)
- `"starlette>=1.0.1"` — explicit direct floor: the PRIMARY CVE-closing constraint

`uv lock` resolved:
- `fastapi` 0.133.0 → 0.136.3
- `starlette` 0.52.1 → 1.2.1 (PYSEC-2026-161 patched version)

Breakage gate (D-06) results:
- `uv run pytest tests/ -x -q` → **966 passed, 0 failed** (965 prior + 1 new BadHost test)
- `uv run ruff check triggarr/ tests/` → **All checks passed**
- pip-audit on `uv export` → **CLEAN** (no known vulnerabilities)

Pre-bump TemplateResponse audit: all `TemplateResponse` calls in `triggarr/web/routes.py` use `request=request, name=...` keyword form — no old positional-signature calls. All starlette 1.0 removals (deprecated `@app.route()`, `on_event()`, `allow_redirects` on TestClient, positional TemplateResponse, etc.) are unused by Triggarr.

Starlette 1.2.1 introduced a `StarletteDeprecationWarning` recommending `httpx2` instead of `httpx` for TestClient, and a `DeprecationWarning` for per-request cookie setting — both are warnings only, no test failures.

### Task 2: BadHost regression test (CHARD-04 / P68-FI-002 verifiability)

Added `test_spoofed_host_protected_route_still_redirects_with_routed_next` to `tests/test_auth_middleware.py` after `test_unauth_browser_redirect_includes_next_deep_path` (mirroring its fixture pattern).

The test asserts three cases using `TestClient(_make_auth_app(_configured_auth()), follow_redirects=False)`:
1. `Host: evil.example.com` on `/settings` → `302`, `location == "/login?next=/settings"` (spoofed Host does not flip exempt-prefix matching)
2. `Host: evil.example.com/login` on `/settings` → `302`, `location == "/login?next=/settings"` (Host embedding exempt-looking `/login` suffix cannot smuggle an exempt prefix)
3. `Host: evil.example.com` on `/health` → `200` pass-through (proves decision keys off `request.url.path`, not reconstructed URL)

All three cases verify that `AuthMiddleware.dispatch` at `middleware.py:109` (`path = request.url.path`) and `middleware.py:156` (`next_url = quote(str(request.url.path), safe="/")`) read the routed path — immune to Host header manipulation.

Test count: 42 → 43 (exactly +1, no existing test deleted or skipped).

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| starlette floor present | `grep -q 'starlette>=1.0.1' pyproject.toml` | PASS |
| starlette resolved >= 1.0.1 | `importlib.metadata.version('starlette')` | 1.2.1 |
| Full test suite | `uv run pytest tests/ -x -q` | 966 passed |
| Ruff | `uv run ruff check triggarr/ tests/` | Clean |
| pip-audit | `uv export ... \| pip-audit -r ... --format json` | CLEAN |
| BadHost test | `uv run pytest tests/test_auth_middleware.py -k "spoofed_host" -x -q` | 1 passed |
| TemplateResponse audit | `grep -rn "TemplateResponse" triggarr/ tests/` | All use keyword form |

## Deviations from Plan

### Auto-applied: Corrected CVE-closing mechanism (per plan frontmatter D-05 note)

The plan frontmatter explicitly documents this as a corrected mechanism vs. the original D-05 decision. The executor applied it as specified: **explicit `starlette>=1.0.1` direct constraint** as the primary mechanism alongside `fastapi>=0.136.3`. A fastapi bump alone would not reliably force starlette 1.x since fastapi's published metadata only requires `starlette>=0.46.0` — uv could legally resolve starlette 0.52.1 (still vulnerable).

No other deviations.

## Known Stubs

None. Both tasks produce verifiable, wired behavior: the pyproject.toml constraint directly controls the locked starlette version; the BadHost test exercises live middleware behavior with no mocking.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced. The changes close an existing CVE and add a regression test for a previously-identified threat class.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| pyproject.toml exists | FOUND |
| uv.lock exists | FOUND |
| tests/test_auth_middleware.py exists | FOUND |
| 69-02-SUMMARY.md exists | FOUND |
| Commit 5bbe638 (Task 1) | FOUND |
| Commit 79f5b8c (Task 2) | FOUND |
| starlette>=1.0.1 in pyproject.toml | PRESENT |
| fastapi>=0.136.3 in pyproject.toml | PRESENT |
| def test_spoofed_host in test file | PRESENT |
