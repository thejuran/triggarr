# S04: Remediate documentation accuracy and evidence artifacts — UAT

**Milestone:** M001
**Written:** 2026-05-05T22:48:50.187Z

## UAT Type

Automated acceptance/UAT for S04 remediation. This UAT proves code-level and documentation-level acceptance criteria without requiring a live reverse proxy or a human documentation review. Human docs-review and release/deep-review acceptance remain assigned to S05.

## Preconditions

- Repository dependencies are installed with `uv sync --extra dev`.
- Tests run from the repository root.
- No real API keys, password hashes, generated session secrets, or operator tokens are used; only test fixtures/placeholders are acceptable.

## Test Case 1 — Direct HTTP clients cannot spoof secure-cookie state

1. Run `uv run pytest tests/test_auth_routes.py tests/test_auth_middleware.py tests/test_root_path.py -q`.
2. Confirm Forms setup/login/logout cookie tests pass for HTTPS requests.
3. Confirm Basic-auth session cookie tests pass for HTTPS requests.
4. Confirm direct HTTP requests with `X-Forwarded-Proto: https` do not cause app-layer cookie paths to set `Secure`.

Expected outcome: all focused auth/proxy tests pass; spoofed forwarded-proto is not trusted by route or middleware cookie code.

## Test Case 2 — Trusted proxy boundary remains at Uvicorn

1. Inspect `triggarr/__main__.py` through the focused root-path tests.
2. Confirm Uvicorn remains configured with proxy header handling and `forwarded_allow_ips` from `TRUSTED_PROXY_IPS`.
3. Confirm runtime cookie paths use ASGI scheme via `is_secure_request(...)` rather than direct forwarded-header reads.

Expected outcome: Uvicorn is the single accepted forwarded-proto boundary; application code consumes only the normalized ASGI scheme.

## Test Case 3 — Operator docs accurately describe External auth

1. Run `uv run pytest tests/test_docs_accuracy.py -q`.
2. Confirm README and SECURITY guidance state External auth requires upstream authentication/authorization.
3. Confirm README and SECURITY guidance state direct access to Triggarr must be blocked when using External auth.

Expected outcome: docs tests pass and prevent future removal of the External-auth safety boundary.

## Test Case 4 — Secure-cookie docs avoid overclaiming route-level header validation

1. Run `uv run pytest tests/test_docs_accuracy.py -q`.
2. Confirm docs describe secure cookies as ASGI-scheme based.
3. Confirm docs describe forwarded proto as trusted only after Uvicorn accepts it from trusted proxy IPs.
4. Confirm docs do not imply route or middleware code separately validates `X-Forwarded-Proto`.

Expected outcome: docs wording stays aligned with implementation and the trusted-proxy boundary.

## Test Case 5 — README examples stay executable as configuration

1. Run `uv run pytest tests/test_docs_accuracy.py -q`.
2. Confirm README TOML examples parse with `tomllib.loads(...)`.
3. Confirm the parsed examples validate through `Settings.model_validate(...)`.

Expected outcome: documented configuration examples remain compatible with the real Settings model.

## Test Case 6 — Evidence gap is superseded for downstream milestone validation

1. Open `.gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md`.
2. Confirm it explicitly states S04 supersedes the known S02 placeholder summary.
3. Confirm it cites the real S02 task summaries as the artifact trail and does not rely on the placeholder S02 summary as authoritative evidence.

Expected outcome: downstream validation can use S04's assessment and task summaries as the evidence source for S02-related documentation delivery.

## Regression Test Case 7 — Portable config behavior remains intact

1. Run `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py tests/test_docs_accuracy.py -q`.
2. Confirm config-dir, state, startup, and docs-accuracy regressions all pass.

Expected outcome: S04 auth/docs changes do not regress the portable `TRIGGARR_CONFIG_DIR` behavior proven by earlier slices.

## Final Acceptance Gate

1. Run `uv run pytest tests/ -x -q`.
2. Run `uv run ruff check triggarr/ tests/`.

Expected outcome: full pytest and lint both pass. Existing Starlette TestClient cookie deprecation warnings may appear but must not be new failures.

## Not Proven By This UAT

- A live reverse-proxy deployment with real client IP/proxy IP topology; S04 relies on `tests/test_root_path.py` and Uvicorn configuration checks rather than starting Nginx/Traefik/Caddy.
- Human readability or release-manager acceptance of README/SECURITY/TODO changes; that is S05.
- `/deep-review` before pushing or release tagging; that is S05.
- Performance or load behavior of authentication middleware; S04 changed trust-boundary logic and docs, not throughput-sensitive paths.
