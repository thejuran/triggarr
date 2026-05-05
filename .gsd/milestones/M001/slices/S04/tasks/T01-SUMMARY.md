---
id: T01
parent: S04
milestone: M001
key_files:
  - triggarr/web/security.py
  - triggarr/web/routes.py
  - triggarr/web/middleware.py
  - tests/test_auth_routes.py
  - tests/test_auth_middleware.py
key_decisions:
  - Session-cookie Secure decisions are centralized on `request.url.scheme == "https"`; direct `X-Forwarded-Proto` reads are not used by runtime cookie paths.
duration: 
verification_result: passed
completed_at: 2026-05-05T22:36:22.783Z
blocker_discovered: false
---

# T01: Centralized session-cookie Secure decisions on ASGI scheme and covered spoofed forwarded-proto cases.

**Centralized session-cookie Secure decisions on ASGI scheme and covered spoofed forwarded-proto cases.**

## What Happened

Added `triggarr/web/security.py` with `is_secure_request(request)` so cookie security decisions use only `request.url.scheme`; its docstring documents that Uvicorn/trusted proxy processing owns accepted forwarded-proto translation. Removed route-level `_is_secure_context()` and replaced setup, login, logout, and Basic-auth middleware cookie paths with the shared helper. Added regression coverage for HTTP requests spoofing `X-Forwarded-Proto: https` and HTTPS-positive coverage for Forms setup/login/logout cookies plus Basic-auth session cookies. The red/green checks confirmed the old implementation set `Secure` from spoofed headers in login and Basic-auth paths before the helper change, then passed after the helper was wired in. Security review scope was the session-cookie trust boundary; the concrete exploit path was spoofing `X-Forwarded-Proto` on direct HTTP requests to influence `Secure`, and the remediation keeps app-layer code from reading that header directly.

## Verification

Fresh verification passed after the last code change: required task command `uv run pytest tests/test_auth_routes.py tests/test_auth_middleware.py tests/test_root_path.py -q` reported 112 passed; scoped `ruff check` reported all checks passed; static `rg` assertion confirmed no `x-forwarded-proto` or `_is_secure_context` references remain in runtime cookie files. The required pytest command emitted 21 existing TestClient per-request cookie deprecation warnings but exited 0.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_auth_routes.py tests/test_auth_middleware.py tests/test_root_path.py -q` | 0 | ✅ pass | 12459ms |
| 2 | `uv run ruff check triggarr/web/security.py triggarr/web/routes.py triggarr/web/middleware.py tests/test_auth_routes.py tests/test_auth_middleware.py` | 0 | ✅ pass | 36ms |
| 3 | `if rg -n 'x-forwarded-proto|_is_secure_context' triggarr/web/routes.py triggarr/web/middleware.py triggarr/web/security.py; then exit 1; else echo 'No direct forwarded-proto trust remains in runtime cookie files.'; fi` | 0 | ✅ pass | 42ms |

## Deviations

None.

## Known Issues

The focused pytest command still emits existing TestClient per-request cookie deprecation warnings from tests that pass cookies per request; this task did not refactor that unrelated warning source.

## Files Created/Modified

- `triggarr/web/security.py`
- `triggarr/web/routes.py`
- `triggarr/web/middleware.py`
- `tests/test_auth_routes.py`
- `tests/test_auth_middleware.py`
