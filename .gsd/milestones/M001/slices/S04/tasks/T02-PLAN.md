---
estimated_steps: 4
estimated_files: 3
skills_used:
  - write-docs
  - security-review
  - verify-before-complete
---

# T02: Rewrite auth/proxy docs and add docs-accuracy tests

Expected task-plan frontmatter skills_used: `write-docs`, `security-review`, `verify-before-complete`.

Update the operator-facing documentation after the runtime trust boundary is fixed, then lock the key claims with tracked tests so the docs do not drift again.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|------------|------------------------|
| README TOML examples | Fail docs-accuracy tests by parsing TOML with `tomllib.loads(...)` and validating via `Settings.model_validate(...)` | N/A | Fail with a test explaining which TOML block is invalid |
| Operator auth guidance | Fail docs-accuracy tests when External-auth docs omit upstream authentication/authorization or blocked direct access | N/A | Fail static text guardrails rather than relying on exact prose |

## Load Profile

- **Shared resources**: repository docs only.
- **Per-operation cost**: reading tracked markdown files and parsing README TOML snippets during tests.
- **10x breakpoint**: none expected; keep tests deterministic and filesystem-only.

## Negative Tests

- **Malformed inputs**: invalid README TOML examples must fail `tests/test_docs_accuracy.py`.
- **Error paths**: stale "no authentication"/config-dir TODO claims in tracked docs must fail the docs test.
- **Boundary conditions**: docs may mention `X-Forwarded-Proto`, but must not claim app route code directly trusts it; wording should tie it to ASGI scheme/Uvicorn trusted-proxy processing.

## Steps

1. Rewrite README auth mode, reverse-proxy, and secure-cookie-adjacent wording for a fresh operator: `External` means Triggarr bypasses local auth because an upstream identity/authz layer is responsible, and direct access to port 8484 must be blocked.
2. Rewrite SECURITY auth/cookie bullets to state that cookies are marked Secure when the ASGI request scheme is HTTPS, including when Uvicorn accepts forwarded proto from a configured trusted proxy; avoid implementation-history prose and avoid file paths in trunk docs.
3. Add `tests/test_docs_accuracy.py` with real assertions over tracked files only (`README.md`, `SECURITY.md`, `TODO.md`): External-auth guidance includes authentication/authorization plus blocked direct access, secure-cookie wording does not describe direct app-layer header trust, stale configurable-config TODO/no-auth claims are absent, and README TOML examples parse through `Settings.model_validate(...)`.
4. Keep all examples placeholder-only and preserve documented startup-level env var boundaries (`TRIGGARR_CONFIG_DIR`, `TRUSTED_PROXY_IPS`, `ROOT_PATH`) without claiming arbitrary TOML env overrides.

## Must-Haves

- [ ] README tells reverse-proxy/SSO operators to enable `External` only after upstream authn/authz is enforced and direct access is blocked.
- [ ] SECURITY describes cookie Secure behavior through ASGI scheme/Uvicorn trusted-proxy processing, not direct route-level `X-Forwarded-Proto` trust.
- [ ] Docs tests read only tracked project files and avoid `.gsd/` or other ignored artifacts as fixtures.
- [ ] README TOML validation uses `tomllib.loads(...)` plus `Settings.model_validate(...)`, not a nonexistent `model_validate_toml` API.

## Inputs

- `README.md`
- `SECURITY.md`
- `TODO.md`
- `triggarr/config.py`

## Expected Output

- `README.md`
- `SECURITY.md`
- `tests/test_docs_accuracy.py`

## Verification

uv run pytest tests/test_docs_accuracy.py -q

## Observability Impact

- Signals added/changed: docs-accuracy tests become the diagnostic signal for stale README/SECURITY claims.
- How a future agent inspects this: run `uv run pytest tests/test_docs_accuracy.py -q` and read the assertion failure for the stale or missing claim.
- Failure state exposed: invalid README TOML, missing External-auth trust-boundary guidance, or inaccurate secure-cookie wording.
