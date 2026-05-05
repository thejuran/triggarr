# S06: Validation remediation: requirement scope, S02 evidence, and human UAT

**Goal:** Remediate M001 validation blockers without changing runtime behavior: produce an explicit milestone requirement-scope artifact, resolve or canonically supersede the S02 placeholder/pending-task inconsistency, record the true human documentation UAT and /deep-review gate state, and refresh focused/full/lint verification evidence for validation rerun.
**Demo:** After this: validation has an explicit requirement-scope coverage artifact, S02 placeholder/task-state inconsistency is resolved or accepted via canonical supersession, human documentation UAT/deep-review is approved or explicitly deferred only if a real human decision exists (otherwise recorded as unresolved/escalated with needs-attention posture), and focused/full/lint checks have fresh evidence for rerun validation.

## Must-Haves

- `S06-REQUIREMENT-SCOPE.md` gives a cold-reader milestone validator enough information to distinguish M001-touched acceptance criteria from historical validated/deferred/out-of-scope project requirements, including direct INST-04 migration proof if referenced.
- S02's blocker state is resolved by a canonical record: either `M001/S02/T04` is completed as superseded-by-S04 through GSD tooling, or `S06-S02-SUPERSESSION.md` explicitly instructs validation to use S02 task summaries plus `S04/tasks/T03-ASSESSMENT.md` instead of placeholder `S02-SUMMARY.md`.
- `S06-HUMAN-UAT-GATE.md` records a real human approval/change request/explicit deferral if one exists, or truthfully records unresolved/escalated status in auto-mode; it must not convert agent scans into human approval.
- `S06-VALIDATION-EVIDENCE.md` indexes fresh S06 command evidence for docs accuracy, config migration, config/state/startup/docs integration tests, full pytest, ruff, stale-claim scanning, and S06 artifact self-checks, with validation posture tied to the human-gate state.
- Threat surface: validation/release-gate artifacts could falsely green-light a release if human approval, secure-cookie trust boundaries, or S02 evidence are overstated; artifacts must not include real API keys, password hashes, session secrets, cookies, generated auth/session secrets, or secret environment values; human-gate text and historical GSD artifacts are untrusted until corroborated by current decisions and tracked tests.
- Requirement impact: no Active requirements exist. S06 preserves prior validated coverage for INST-01, INST-02, INST-04, OBS-02, OBS-03, and milestone-level portable-config/auth documentation acceptance without mutating requirement statuses. Re-verify tracked docs/config/startup tests, full tests, lint, stale-claim scan, and artifact self-checks. Honor `D001` and `D002`; do not reintroduce direct app-layer trust of `X-Forwarded-Proto` or apply stale S02/T04 wording.

## Proof Level

- This slice proves: This slice provides documentation/validation-evidence proof, not new live runtime integration proof. Runtime behavior is re-checked through existing tracked tests and lint; human/UAT proof can only be marked approved or deferred if a real human decision is available, otherwise the proof level must remain needs-attention/unresolved for that gate.

## Integration Closure

Upstream surfaces consumed: `.gsd/REQUIREMENTS.md`, `.gsd/milestones/M001/M001-VALIDATION.md`, S02 task summaries, `S04/tasks/T03-ASSESSMENT.md`, S05 review/gate/evidence artifacts, `README.md`, `SECURITY.md`, `TODO.md`, `tests/test_docs_accuracy.py`, `tests/test_config.py`, and `triggarr/config.py`. New runtime wiring introduced: none; the slice adds validation artifacts that close the evidence chain for M001 validation. Remaining before milestone pass: if no human decision exists, milestone validation should remain needs-attention until a human approves or explicitly defers documentation UAT/deep-review.

## Verification

- Objective slice verification must pass through fresh S06 evidence: `uv run pytest tests/test_docs_accuracy.py -q`; `uv run pytest tests/test_config.py -q -k 'v22 or migrate_v22 or ensure_config_calls_migration or toml_round_trip'`; `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py tests/test_docs_accuracy.py -q`; `uv run pytest tests/ -x -q`; `uv run ruff check triggarr/ tests/`; a no-match `rg` stale-claim scan over README/SECURITY/TODO/CONTRIBUTING/docs; and an artifact self-check confirming S06 scope, S02 repair/supersession, human gate, and validation evidence files exist with expected statuses. Diagnostics are the S06 artifacts and `.gsd/exec/*` transcripts referenced from `S06-VALIDATION-EVIDENCE.md`; redaction constraints prohibit storing secrets, cookies, hashes, or generated auth/session values.

## Tasks

- [x] **T01: Write requirement-scope coverage artifact** `est:45m`
  Create the milestone-scope requirement coverage artifact that retires the false premise that M001/S06 must re-prove every historically validated project requirement.
  - Files: `.gsd/REQUIREMENTS.md`, `.gsd/milestones/M001/M001-VALIDATION.md`, `triggarr/config.py`, `tests/test_config.py`, `.gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md`
  - Verify: test -s .gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md && rg -n "Active requirements|INST-04|detect_and_migrate_v22|validation treatment|milestone validator" .gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md

- [x] **T02: Repair or canonically supersede S02 evidence inconsistency** `est:45m`
  Resolve the S02 blocker by either completing the residual S02/T04 task as superseded-by-S04 or writing a canonical S06 supersession artifact if GSD tooling rejects task completion under a closed slice.
  - Files: `.gsd/DECISIONS.md`, `.gsd/milestones/M001/slices/S02/S02-SUMMARY.md`, `.gsd/milestones/M001/slices/S02/tasks/T01-SUMMARY.md`, `.gsd/milestones/M001/slices/S02/tasks/T02-SUMMARY.md`, `.gsd/milestones/M001/slices/S02/tasks/T03-SUMMARY.md`, `.gsd/milestones/M001/slices/S02/tasks/T04-PLAN.md`, `.gsd/milestones/M001/slices/S02/tasks/T04-SUMMARY.md`, `.gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md`, `.gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md`, `tests/test_docs_accuracy.py`
  - Verify: Use gsd_milestone_status for M001; pass if S02 pending count is 0, otherwise require `test -s .gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md` and `rg -n "canonical supersession|S04/tasks/T03-ASSESSMENT|D001|D002|S02-SUMMARY" .gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md`.

- [ ] **T03: Record human UAT and deep-review gate truthfully** `est:30m`
  Create the S06 human-gate artifact that records the real state of documentation UAT and `/deep-review` without fabricating approval in auto-mode.
  - Files: `.gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md`, `.gsd/milestones/M001/slices/S05/S05-UAT-GATE.md`, `.gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md`, `README.md`, `SECURITY.md`, `TODO.md`, `.gsd/milestones/M001/slices/S06/S06-HUMAN-UAT-GATE.md`
  - Verify: test -s .gsd/milestones/M001/slices/S06/S06-HUMAN-UAT-GATE.md && rg -n "Gate status|Human UAT|/deep-review|needs-attention|unresolved|human source" .gsd/milestones/M001/slices/S06/S06-HUMAN-UAT-GATE.md

- [ ] **T04: Refresh validation evidence index and rerun readiness checks** `est:1h`
  Rerun the focused/full mechanical verification suite after S06 artifacts exist and write a single evidence index that validation can consume without rediscovering the S02/S05 history.
  - Files: `.gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md`, `.gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md`, `.gsd/milestones/M001/slices/S02/tasks/T04-SUMMARY.md`, `.gsd/milestones/M001/slices/S06/S06-HUMAN-UAT-GATE.md`, `.gsd/milestones/M001/slices/S06/S06-VALIDATION-EVIDENCE.md`, `tests/test_docs_accuracy.py`, `tests/test_config.py`, `tests/test_config_dir.py`, `tests/test_state.py`, `tests/test_startup.py`
  - Verify: Run the listed pytest, ruff, stale-claim scan, and S06 artifact self-check through gsd_exec; then require `test -s .gsd/milestones/M001/slices/S06/S06-VALIDATION-EVIDENCE.md` and evidence index entries for each command.

## Files Likely Touched

- .gsd/REQUIREMENTS.md
- .gsd/milestones/M001/M001-VALIDATION.md
- triggarr/config.py
- tests/test_config.py
- .gsd/milestones/M001/slices/S06/S06-REQUIREMENT-SCOPE.md
- .gsd/DECISIONS.md
- .gsd/milestones/M001/slices/S02/S02-SUMMARY.md
- .gsd/milestones/M001/slices/S02/tasks/T01-SUMMARY.md
- .gsd/milestones/M001/slices/S02/tasks/T02-SUMMARY.md
- .gsd/milestones/M001/slices/S02/tasks/T03-SUMMARY.md
- .gsd/milestones/M001/slices/S02/tasks/T04-PLAN.md
- .gsd/milestones/M001/slices/S02/tasks/T04-SUMMARY.md
- .gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md
- .gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md
- tests/test_docs_accuracy.py
- .gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md
- .gsd/milestones/M001/slices/S05/S05-UAT-GATE.md
- .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md
- README.md
- SECURITY.md
- TODO.md
- .gsd/milestones/M001/slices/S06/S06-HUMAN-UAT-GATE.md
- .gsd/milestones/M001/slices/S06/S06-VALIDATION-EVIDENCE.md
- tests/test_config_dir.py
- tests/test_state.py
- tests/test_startup.py
