---
id: S04
parent: M001
milestone: M001
provides:
  - A reconciled auth/proxy trust-boundary implementation and documentation set for S05 human docs UAT.
  - A durable S04 evidence trail that supersedes the S02 placeholder summary for milestone validation.
  - Fresh verification evidence for focused auth/proxy tests, portable config regressions, docs-accuracy tests, full pytest, and ruff lint.
requires:
  []
affects:
  - M001/S05
key_files:
  - triggarr/web/security.py
  - triggarr/web/routes.py
  - triggarr/web/middleware.py
  - tests/test_auth_routes.py
  - tests/test_auth_middleware.py
  - tests/test_root_path.py
  - README.md
  - SECURITY.md
  - TODO.md
  - tests/test_docs_accuracy.py
  - .gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md
  - .gsd/PROJECT.md
  - .gsd/DECISIONS.md
key_decisions:
  - D002 — Forwarded-proto trust for session-cookie Secure decisions belongs at Uvicorn proxy-header processing; runtime cookie-setting code uses ASGI `request.url.scheme` via `is_secure_request(...)`.
patterns_established:
  - Centralize web security predicates in `triggarr/web/security.py` so Forms routes and auth middleware share the same trust-boundary logic.
  - Use docs-accuracy tests to lock high-risk operator documentation claims, not just code behavior.
  - When a previous slice summary is known stale, supersede it with a new assessment that cites task-level artifacts rather than mutating history.
observability_surfaces:
  - No new production logs or metrics were added; failure visibility is provided by focused cookie assertions, `tests/test_root_path.py`, docs-accuracy tests, and the S04 evidence assessment.
drill_down_paths:
  - .gsd/milestones/M001/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S04/tasks/T03-SUMMARY.md
  - .gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md
  - .gsd/exec/7c8b154a-8165-4356-99c3-e34505c3fa0c.stdout
  - .gsd/exec/3be82cd1-4812-428b-a74d-9b8bd89e10bf.stdout
duration: ""
verification_result: passed
completed_at: 2026-05-05T22:48:50.186Z
blocker_discovered: false
---

# S04: Remediate documentation accuracy and evidence artifacts

**S04 reconciled secure-cookie behavior and auth/proxy documentation around the trusted ASGI/Uvicorn boundary, added docs-accuracy guardrails, superseded the stale S02 evidence gap, and reran full verification.**

## What Happened

This slice repaired the validation gaps found after S03. Runtime session-cookie Secure decisions are now centralized in `triggarr/web/security.py:is_secure_request(...)` and depend on `request.url.scheme == "https"`; Forms setup/login/logout routes and Basic-auth middleware use that helper rather than reading `X-Forwarded-Proto` directly. That preserves the intended trust boundary: only Uvicorn proxy-header processing, constrained by `TRUSTED_PROXY_IPS`, may translate forwarded proto into the ASGI scheme.

The documentation was updated to match that implementation. `README.md` and `SECURITY.md` now state that `auth.method = "External"` is safe only when an upstream layer enforces authentication and authorization and direct access to Triggarr is blocked. They also describe secure-cookie behavior as ASGI-scheme based, including the case where Uvicorn has accepted forwarded proto from a trusted proxy, without implying route-level `X-Forwarded-Proto` validation.

`tests/test_docs_accuracy.py` became a tracked guardrail for those operator-facing claims: it checks External-auth guidance, secure-cookie wording, stale TODO/doc markers, and README TOML examples parsed through `Settings.model_validate(...)`. S04 also added an evidence assessment at `.gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md` that explicitly supersedes the known S02 placeholder summary and cites the real S02 task artifacts instead of relying on the placeholder as authoritative evidence.

Closure review included three read-only subagents. The reviewer, security reviewer, and tester all reported no High/Critical blockers. No Active requirements existed to transition; S04 supports milestone-level documentation accuracy and evidence acceptance while preserving the already-validated TAG/INST/OBS compatibility constraints.

## Verification

Fresh S04 closure verification passed.

Automated verification evidence:
- `uv run pytest tests/test_auth_routes.py tests/test_auth_middleware.py tests/test_root_path.py -q` — 112 passed, 21 existing Starlette TestClient cookie deprecation warnings.
- `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py tests/test_docs_accuracy.py -q` — 56 passed.
- `uv run pytest tests/ -x -q` — 873 passed, 27 existing Starlette TestClient cookie deprecation warnings.
- `uv run ruff check triggarr/ tests/` — all checks passed.
- Targeted source check — no direct `X-Forwarded-Proto` header lookup patterns in `triggarr/web/routes.py`, `triggarr/web/middleware.py`, or `triggarr/web/security.py`; helper documentation may mention the header to describe the boundary.

Artifact paths:
- Full command output: `.gsd/exec/7c8b154a-8165-4356-99c3-e34505c3fa0c.stdout`.
- Runtime header-trust source check: `.gsd/exec/3be82cd1-4812-428b-a74d-9b8bd89e10bf.stdout`.

Read-only subagent closure checks:
- Reviewer: no High/Critical blockers; verified helper wiring, auth/proxy tests, docs guardrails, and S04 evidence assessment.
- Security: no High/Critical blockers; confirmed app-layer secure-cookie decisions use ASGI scheme, Uvicorn owns forwarded-header trust, and External-auth docs require upstream authn/authz plus blocked direct access.
- Tester: no closure-blocking coverage gaps; focused combined suite passed with 168 tests and only the known TestClient warnings.

## Requirements Advanced

- No Active requirements advanced; all tracked requirements were already validated/deferred/out-of-scope before S04. — 

## Requirements Validated

- Milestone documentation accuracy and evidence acceptance were validated for S04 scope; no requirement status transition was needed. — 

## New Requirements Surfaced

- None. No Active requirements existed; S04 supports milestone-level documentation accuracy/evidence acceptance.

## Requirements Invalidated or Re-scoped

- None. — 

## Operational Readiness

None.

## Deviations

None. S04 remained within the planned remediation scope. The only related follow-up is the already-planned S05 human documentation UAT and release/deep-review gate.

## Known Limitations

Existing Starlette TestClient per-request cookie deprecation warnings remain in auth tests. No live reverse proxy was started for S04; proxy behavior is proven through Uvicorn configuration tests and direct TestClient cookie behavior.

## Follow-ups

S05 must collect human review of README/SECURITY/TODO documentation changes and resolve whether `/deep-review` should run before release/push.

## Files Created/Modified

- `triggarr/web/security.py` — Added shared `is_secure_request(...)` helper based on ASGI request scheme.
- `triggarr/web/routes.py` — Forms setup/login/logout cookie paths use the shared secure-request helper.
- `triggarr/web/middleware.py` — Basic-auth session cookie path uses the shared secure-request helper.
- `tests/test_auth_routes.py` — Added HTTPS secure-cookie and spoofed forwarded-proto regression coverage for Forms routes.
- `tests/test_auth_middleware.py` — Added HTTPS secure-cookie and spoofed forwarded-proto regression coverage for Basic auth middleware.
- `README.md` — Updated External-auth and secure-cookie trusted-proxy guidance.
- `SECURITY.md` — Updated auth/proxy trust-boundary guidance.
- `tests/test_docs_accuracy.py` — Added guardrails for External-auth docs, secure-cookie wording, stale docs markers, and README TOML validation.
- `.gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md` — Recorded the S04 evidence assessment superseding the S02 placeholder summary.
- `.gsd/PROJECT.md` — Refreshed project state to reflect S04 completion and remaining S05 release gate.
