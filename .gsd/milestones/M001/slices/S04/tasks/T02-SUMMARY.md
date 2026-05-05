---
id: T02
parent: S04
milestone: M001
key_files:
  - README.md
  - SECURITY.md
  - tests/test_docs_accuracy.py
key_decisions:
  - Docs-accuracy tests now lock the operator-facing External-auth and secure-cookie trusted-proxy boundary claims.
  - README TOML examples are validated through `tomllib.loads(...)` and `Settings.model_validate(...)` rather than any nonexistent TOML-specific Pydantic API.
duration: 
verification_result: passed
completed_at: 2026-05-05T22:40:10.256Z
blocker_discovered: false
---

# T02: Tightened External-auth and trusted-proxy cookie docs with tracked docs-accuracy tests.

**Tightened External-auth and trusted-proxy cookie docs with tracked docs-accuracy tests.**

## What Happened

Rewrote README operator guidance so `External` is described as a local-auth bypass that is safe only after an upstream reverse proxy or SSO layer enforces authentication and authorization and direct access to port 8484 is blocked. Updated README reverse-proxy wording to explain that Uvicorn accepts forwarded client/scheme headers from `TRUSTED_PROXY_IPS`, that accepted `X-Forwarded-Proto` becomes the ASGI request scheme used by scheme-aware behavior such as Secure cookie emission, and that direct access should remain blocked. Updated SECURITY auth/cookie bullets and deployment recommendations to use the same upstream-authn/authz and ASGI-scheme trusted-proxy boundary. Added `tests/test_docs_accuracy.py`, which reads only tracked docs (`README.md`, `SECURITY.md`, `TODO.md`), guards External-auth and secure-cookie wording, rejects known stale no-auth/config-dir claims, and parses README TOML examples with `tomllib.loads(...)` plus `Settings.model_validate(...)`. The docs cold-read target was a fresh operator configuring auth/reverse proxy; after the edit, the actionable guidance is to choose External only with enforced upstream authn/authz and blocked direct access.

## Verification

Required docs check passed: `uv run pytest tests/test_docs_accuracy.py -q` reported 4 passed. Focused S04 auth/proxy/docs regression suite passed: `uv run pytest tests/test_auth_routes.py tests/test_auth_middleware.py tests/test_root_path.py tests/test_docs_accuracy.py -q` reported 116 passed with 21 existing TestClient cookie deprecation warnings. Ruff passed for the new docs test, and LSP diagnostics reported no issues for `tests/test_docs_accuracy.py`. Security review found no introduced secret exposure in examples; docs use placeholders and describe trusted-proxy handling without route-level `X-Forwarded-Proto` trust.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_docs_accuracy.py -q` | 0 | ✅ pass | 611ms |
| 2 | `uv run pytest tests/test_auth_routes.py tests/test_auth_middleware.py tests/test_root_path.py tests/test_docs_accuracy.py -q` | 0 | ✅ pass | 12333ms |
| 3 | `uv run ruff check tests/test_docs_accuracy.py` | 0 | ✅ pass | 38ms |

## Deviations

None.

## Known Issues

The focused auth/proxy suite still emits existing TestClient per-request cookie deprecation warnings from pre-existing tests; this task did not refactor that unrelated warning source.

## Files Created/Modified

- `README.md`
- `SECURITY.md`
- `tests/test_docs_accuracy.py`
