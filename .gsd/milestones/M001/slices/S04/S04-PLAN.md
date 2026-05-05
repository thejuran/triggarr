# S04: Remediate documentation accuracy and evidence artifacts

**Goal:** Remediate the auth/proxy documentation accuracy gap by making secure-cookie handling align with the trusted proxy boundary, tightening External-auth operator guidance, and producing a new S04 evidence trail that supersedes the known S02 placeholder summary before rerunning focused/full verification.
**Demo:** After this: README/SECURITY external-auth and secure-cookie trust-boundary guidance is reconciled with implementation, S02 delivery evidence is repaired or superseded with a real artifact trail, requirement coverage is explicitly scoped/proven for touched requirements, and focused/full/lint verification has been rerun.

## Must-Haves

- ## Must-Haves
- Secure-cookie decisions in runtime cookie-setting paths rely on the ASGI request scheme (`request.url.scheme`) rather than directly trusting `X-Forwarded-Proto`; Uvicorn remains the single place where forwarded proto is accepted according to `TRUSTED_PROXY_IPS`.
- Focused auth/proxy tests prove secure cookies are set for HTTPS requests and are not set for plain HTTP requests that merely spoof `X-Forwarded-Proto: https`; Basic-auth middleware and Forms route cookie paths are covered.
- `README.md` and `SECURITY.md` tell operators that `auth.method = "External"` is only safe after an upstream layer enforces authentication/authorization and direct access to Triggarr is blocked.
- `README.md` and `SECURITY.md` describe secure-cookie behavior accurately: cookies are secure when the ASGI scheme is HTTPS, including when Uvicorn has accepted forwarded proto from a trusted proxy; docs must not imply that application route code separately validates `X-Forwarded-Proto`.
- A tracked docs-accuracy test file (`tests/test_docs_accuracy.py`) verifies the External-auth guidance, secure-cookie wording guardrails, stale TODO markers in tracked docs, and README TOML example parsing through `Settings.model_validate(...)`.
- The S02 delivery evidence inconsistency is explicitly superseded in a new S04 evidence assessment, citing the real S02 task summaries and explaining that S04 does not rely on the placeholder `S02-SUMMARY.md` as authoritative evidence.
- Fresh focused auth/proxy tests, config-dir/state/startup regression tests, docs-accuracy tests, full pytest, and ruff lint all pass before slice completion.
- ## Threat Surface
- **Abuse**: A direct client can spoof `X-Forwarded-Proto: https` unless application code avoids reading that header directly. `External` auth can become a full auth bypass if an operator exposes Triggarr directly while relying on upstream auth.
- **Data exposure**: Triggarr session cookies, API keys configured in TOML, password hashes, and generated session/API secrets must not be exposed in docs, logs, test output, or HTML. Docs should use placeholders only.
- **Input trust**: HTTP headers are untrusted at the app layer. Forwarded headers are trusted only after Uvicorn proxy-header processing from `TRUSTED_PROXY_IPS`; docs and tests must preserve that boundary.
- ## Requirement Impact
- **Requirements touched**: No Active requirements exist. This slice supports milestone-level documentation accuracy and evidence acceptance; validated TAG/INST/OBS requirements are compatibility constraints only and are not reimplemented here.
- **Re-verify**: Auth cookie behavior, Uvicorn proxy-header configuration, tracked documentation claims, README TOML example parsing, portable config-dir regressions, full test suite, and lint.
- **Decisions revisited**: Existing auth/security posture has evolved since v1.0 "no auth"; this slice should record the secure-cookie trusted-proxy boundary as the current security decision rather than silently relying on stale D004 wording.

## Proof Level

- This slice proves: - This slice proves: code-level contract plus documentation/evidence final-assembly for the remediated auth/proxy docs gap.
- Real runtime required: no live reverse proxy is required; `tests/test_root_path.py` proves Uvicorn is configured for proxy header trust and auth tests prove app-level cookie behavior under direct TestClient requests.
- Human/UAT required: no for S04; human documentation UAT and release/deep-review remain S05 responsibilities.

## Integration Closure

- Upstream surfaces consumed: Uvicorn startup proxy-header configuration in `triggarr/__main__.py`, auth cookie paths in `triggarr/web/routes.py` and `triggarr/web/middleware.py`, operator docs in `README.md` and `SECURITY.md`, and prior evidence in `.gsd/milestones/M001/slices/S02/`.
- New wiring introduced in this slice: a shared secure-request helper is wired into both Forms route cookie setting and Basic-auth middleware cookie setting; docs-accuracy tests become part of the project test suite.
- What remains before the milestone is truly usable end-to-end: S05 must collect human documentation UAT and decide whether to run `/deep-review` before release/push.

## Verification

- Runtime signals: no new production logs or metrics are required; behavior is diagnosed through explicit cookie assertions and existing trusted-proxy startup tests.
- Inspection surfaces: `tests/test_auth_routes.py`, `tests/test_auth_middleware.py`, `tests/test_root_path.py`, `tests/test_docs_accuracy.py`, fresh `gsd_exec` verification artifacts, and the S04 evidence assessment.
- Failure visibility: failed tests should identify whether the issue is app-layer header trust, Uvicorn proxy configuration, External-auth documentation, README TOML validity, or stale evidence.
- Redaction constraints: never print or persist real API keys, password hashes, generated session secrets, or configured tokens in tests/docs/evidence.

## Tasks

- [x] **T01: Align secure-cookie trust boundary with ASGI scheme** `est:1h30m`
  Expected task-plan frontmatter skills_used: `security-review`, `tdd`, `verify-before-complete`.
  - Files: `triggarr/web/routes.py`, `triggarr/web/middleware.py`, `triggarr/web/security.py`, `tests/test_auth_routes.py`, `tests/test_auth_middleware.py`, `tests/test_root_path.py`
  - Verify: uv run pytest tests/test_auth_routes.py tests/test_auth_middleware.py tests/test_root_path.py -q

- [x] **T02: Rewrite auth/proxy docs and add docs-accuracy tests** `est:1h15m`
  Expected task-plan frontmatter skills_used: `write-docs`, `security-review`, `verify-before-complete`.
  - Files: `README.md`, `SECURITY.md`, `TODO.md`, `tests/test_docs_accuracy.py`, `triggarr/config.py`
  - Verify: uv run pytest tests/test_docs_accuracy.py -q

- [x] **T03: Supersede S02 evidence gap and rerun final verification** `est:1h`
  Expected task-plan frontmatter skills_used: `verify-before-complete`, `write-docs`, `test`.
  - Files: `.gsd/milestones/M001/slices/S02/S02-SUMMARY.md`, `.gsd/milestones/M001/slices/S02/tasks/T01-SUMMARY.md`, `.gsd/milestones/M001/slices/S02/tasks/T02-SUMMARY.md`, `.gsd/milestones/M001/slices/S02/tasks/T03-SUMMARY.md`, `.gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md`, `tests/test_docs_accuracy.py`
  - Verify: uv run pytest tests/test_auth_routes.py tests/test_auth_middleware.py tests/test_root_path.py -q && uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py tests/test_docs_accuracy.py -q && uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/

## Files Likely Touched

- triggarr/web/routes.py
- triggarr/web/middleware.py
- triggarr/web/security.py
- tests/test_auth_routes.py
- tests/test_auth_middleware.py
- tests/test_root_path.py
- README.md
- SECURITY.md
- TODO.md
- tests/test_docs_accuracy.py
- triggarr/config.py
- .gsd/milestones/M001/slices/S02/S02-SUMMARY.md
- .gsd/milestones/M001/slices/S02/tasks/T01-SUMMARY.md
- .gsd/milestones/M001/slices/S02/tasks/T02-SUMMARY.md
- .gsd/milestones/M001/slices/S02/tasks/T03-SUMMARY.md
- .gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md
