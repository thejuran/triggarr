---
id: M001
title: "Portable Config Directory & Documentation Refresh"
status: complete
completed_at: 2026-05-06T00:03:54.007Z
key_decisions:
  - Kept Docker/default `/config` behavior unchanged because runtime references are intentional defaults/backward compatibility, not defects.
  - Verified portable config-directory behavior through focused boundary tests and operational probes rather than unnecessary production path changes.
  - Centralized session-cookie Secure decisions on ASGI `request.url.scheme` via `triggarr/web/security.py:is_secure_request(...)`; Uvicorn proxy-header handling is the only trusted forwarded-proto translation boundary.
  - Used documentation-accuracy tests to guard high-risk operator claims in README/SECURITY and README TOML examples.
  - Canonically superseded the stale S02/T04 secure-cookie wording through S04/S06 evidence rather than applying unsafe direct forwarded-proto guidance.
  - Recorded human documentation UAT and `/deep-review` as unresolved needs-attention gates rather than inventing approval in auto-mode.
key_files:
  - triggarr/web/security.py
  - triggarr/web/routes.py
  - triggarr/web/middleware.py
  - tests/test_config_dir.py
  - tests/test_startup.py
  - tests/test_auth_routes.py
  - tests/test_auth_middleware.py
  - tests/test_root_path.py
  - tests/test_docs_accuracy.py
  - README.md
  - SECURITY.md
  - TODO.md
  - .gsd/DEFERRED-BACKLOG.md
  - .gsd/milestones/M001/slices/S02/S02-SUMMARY.md
  - .gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md
  - .gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md
  - .gsd/milestones/M001/slices/S05/S05-UAT-GATE.md
  - .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md
  - .gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md
  - .gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md
  - .gsd/milestones/M001/slices/S06/S06-HUMAN-UAT-GATE.md
  - .gsd/milestones/M001/slices/S06/S06-VALIDATION-EVIDENCE.md
lessons_learned:
  - Set `TRIGGARR_CONFIG_DIR` before importing modules with import-time path constants; changing it afterward only affects dynamic helper calls, not frozen constants.
  - A docs review packet is not human UAT. Autonomous agents must preserve unresolved human approval/deep-review gates as needs-attention rather than converting mechanical diagnostics into release approval.
  - When GSD history contains a closed slice with stale placeholder evidence, canonical supersession artifacts and a controlled slice reopen can repair task state without mutating user source.
  - High-risk deployment/security documentation should have executable guardrails; `tests/test_docs_accuracy.py` now prevents regression to unsafe External-auth or direct forwarded-proto trust claims.
---

# M001: Portable Config Directory & Documentation Refresh

**Verified Triggarr's portable config-directory contract, refreshed and guarded README/SECURITY/TODO documentation, reconciled auth/proxy trust-boundary behavior, and closed the milestone with fresh mechanical evidence while preserving the unresolved human UAT/deep-review release gate as needs-attention.**

## What Happened

## What Happened

M001 converted the stale configurable-config-directory TODO into verified current behavior and aligned the project documentation with that behavior. S01 audited the runtime path consumers and proved that an absolute `TRIGGARR_CONFIG_DIR` controls `triggarr.toml`, `state.json`, and the derived `triggarr.db` location when set before Triggarr imports/startup, while `/config` remains the Docker/default fallback and relative paths fail early. The audit found no production hardcoded `/config` defect, so the slice added focused tests and operational probes rather than changing runtime path code.

S02 refreshed documentation and backlog state. It produced a source-backed docs audit, updated README install/config/security guidance for Docker `/config`, standalone absolute `TRIGGARR_CONFIG_DIR`, nested per-instance TOML, and current auth modes, and retired stale TODO/backlog claims. A historical S02 closeout issue left a placeholder summary and pending T04; this completion retry repaired that state by reopening S02, re-recording T01-T04 from the task evidence, and closing T04 as superseded by S04/S06 rather than applying stale unsafe direct `X-Forwarded-Proto` wording.

S03 assembled initial integrated evidence and surfaced two important caveats: autonomous mode could not obtain human documentation UAT, and auth/proxy secure-cookie documentation needed remediation before release. S04 repaired those validation gaps. Runtime session-cookie `Secure` decisions were centralized in `triggarr/web/security.py:is_secure_request(...)` and now use the ASGI request scheme; Uvicorn proxy-header processing, constrained by `TRUSTED_PROXY_IPS`, is the sole boundary that may translate trusted forwarded-proto information. README and SECURITY now state that External auth is safe only behind an upstream authentication/authorization layer with direct Triggarr access blocked, and docs-accuracy tests lock those high-risk operator claims.

S05 and S06 turned the remaining validation posture into explicit evidence rather than false approval. S05 produced a human-readable docs review packet, unresolved UAT/deep-review gate artifact, and blocked release-gate evidence index. S06 added requirement-scope coverage, canonical S02 supersession instructions, a human UAT gate record, a validation evidence index, and machine-readable gate state showing that mechanical checks pass but human release approval is still not present. This completion keeps that truth intact: M001 is mechanically complete, but release/pass validation still needs a real human documentation decision and `/deep-review` completion or explicit human deferral.

## Code-Change Verification

The current retry is running on `main`, so the merge-base-to-HEAD branch diff contains no non-`.gsd/` files. Per retry instructions, that is treated as a retry-on-main self-diff, not as proof that implementation work is missing. Milestone-scoped commit evidence proves non-`.gsd/` changes: `a3f09ad` touched `README.md`, `tests/test_config_dir.py`, and `tests/test_startup.py`; `40d7baa` touched `SECURITY.md` and `TODO.md`; `5e6b4c0` touched `triggarr/web/security.py`, `triggarr/web/routes.py`, `triggarr/web/middleware.py`, and auth/proxy tests; and `ea9826a` touched `README.md`, `SECURITY.md`, and `tests/test_docs_accuracy.py`.

## Decision Re-evaluation

| Decision | Still valid? | Evidence | Follow-up |
|---|---:|---|---|
| D001 — Secure-cookie trusted-proxy boundary belongs at Uvicorn/ASGI scheme handling, not route-level raw header checks. | Yes | S04 implemented `is_secure_request(...)`, removed app-layer direct `X-Forwarded-Proto` decisions, updated README/SECURITY, and added auth/proxy tests plus docs guardrails. | Revisit only if Uvicorn/proxy deployment support changes. |
| D002 — Runtime cookie-setting code uses `request.url.scheme`; only Uvicorn proxy-header processing may translate trusted forwarded-proto headers according to `TRUSTED_PROXY_IPS`. | Yes | S04 verification found no direct forwarded-proto header lookup in routes/middleware/security code, and focused auth/proxy tests plus S06/fresh completion evidence continue to pass. | Keep docs/tests in sync for any future auth middleware changes. |

## Cross-Slice Synthesis

S01 produced the portable config-directory contract that S02/S03 documented and verified. S04 superseded the unsafe or incomplete S02 evidence path and tightened security documentation and runtime behavior around the proxy trust boundary. S05/S06 preserved the release/UAT distinction so downstream agents do not mistake passing tests for human approval. The assembled result is a mechanically verified portable-config/docs/security milestone with a deliberately explicit needs-attention human gate for release readiness.

## Success Criteria Results

- [x] **Custom absolute `TRIGGARR_CONFIG_DIR` controls config and state paths without regressing Docker `/config`.** Evidence: S01 summary reports focused config/state/startup coverage and operational temp-dir probes; fresh completion verification `.gsd/exec/49286bf6-d4d9-41c1-a4fe-dafe3ba5f4c8.stdout` passed `focused_config_startup` (`32 passed`) and printed `config_path`, `state_path`, and derived `db_path` under a temp absolute config directory. `/config` remains the env-unset default per S01.
- [x] **README and adjacent docs describe current nested multi-instance config, standalone config-directory behavior, and auth/security posture accurately.** Evidence: S02 task summaries and repaired S02 summary provide the README/TODO/SECURITY update trail; S04 remediated External-auth and secure-cookie trust-boundary wording; `tests/test_docs_accuracy.py` guards README TOML and security claims; fresh completion verification passed `focused_auth_proxy_docs` (`116 passed`) and full tests.
- [x] **Stale TODO entry retired or rewritten.** Evidence: S02/T03 retired the configurable-config-directory TODO; S06 validation evidence records a clean stale-claim scan; docs-accuracy tests continue to pass.
- [x] **Final verification includes focused tests, full tests, lint, operational config-dir check, and a docs-review/UAT gate.** Evidence: fresh completion verification `.gsd/exec/49286bf6-d4d9-41c1-a4fe-dafe3ba5f4c8.stdout` exited 0 after focused config/startup tests, focused auth/proxy/docs tests, `uv run pytest tests/ -x -q` (`873 passed`), `uv run ruff check triggarr/ tests/` (`All checks passed!`), and operational config-dir smoke. The docs-review/UAT gate exists as `S05-UAT-GATE.md` and `S06-HUMAN-UAT-GATE.md`; it is intentionally unresolved/not approved in autonomous mode, so release/pass validation remains needs-attention until a human decision exists.

## Definition of Done Results

- [x] **All roadmap slices are checked complete.** `.gsd/milestones/M001/M001-ROADMAP.md` lists S01 through S06 as `[x]`; `gsd_milestone_status` now reports all six slices with status `complete`.
- [x] **All slice tasks are complete.** After repairing S02's residual bookkeeping, `gsd_milestone_status` reports S01-S06 with zero pending tasks.
- [x] **Slice summaries exist and are authoritative.** S01-S06 summary files are present. The former S02 placeholder was replaced with a canonical S02 summary that records T04 as superseded by S04/S06 evidence.
- [x] **Cross-slice integration points work.** S01's config-dir contract feeds docs and operational smoke; S04 reconciles auth/proxy runtime and docs; S05/S06 evidence separates mechanical readiness from human release approval. Fresh completion verification passed focused, full, lint, and operational checks.
- [x] **Release caveats preserved.** Human docs UAT and `/deep-review` are not claimed as approved; they remain follow-ups and keep release validation needs-attention.

## Requirement Outcomes

No requirement status transitions were made during milestone completion. `.gsd/REQUIREMENTS.md` already has no Active requirements; S06's requirement-scope artifact states that M001 validation is bounded to portable config-directory behavior, documentation accuracy, stale TODO hygiene, S02 evidence supersession, human UAT/deep-review gate handling, and preservation of touched historical requirements. INST-04 migration/config compatibility remains supported by implementation and focused tests; historical validated INST/TAG/OBS/VER requirements remain preserved rather than re-opened; deferred and out-of-scope requirements remain unchanged.

## Deviations

Runtime portable config-directory production code did not need changes because the behavior was already implemented; the milestone focused on proof and documentation. S02's first slice summary was a historical placeholder with a residual pending T04; the completion retry reopened S02 only to record canonical task state and replace the placeholder with a supersession-aware summary. Human documentation UAT and `/deep-review` could not be resolved in autonomous mode and remain needs-attention release gates.

## Follow-ups

A human should review `README.md`, `SECURITY.md`, and `TODO.md` using the S05/S06 review scope and record approval, change request, or explicit deferral. Before push/tag/release, offer and run `/deep-review` or record a human deferral with scope and caveats.
