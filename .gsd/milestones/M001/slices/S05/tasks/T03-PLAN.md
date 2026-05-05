---
estimated_steps: 1
estimated_files: 10
skills_used: []
---

# T03: Capture blocked-gate verification evidence without claiming release readiness

Read the current `S05-UAT-GATE.md` status. If the gate is `approved` or `deferred`, run the fresh release-gate verification suite and write `S05-RELEASE-GATE-EVIDENCE.md` as passing/ready only if all commands pass. If the gate is `unresolved` or `changes-requested`, do not treat this as release approval: write `S05-RELEASE-GATE-EVIDENCE.md` as a blocked-gate evidence index that records the gate status, explains that human UAT and `/deep-review` remain unresolved or require changes, and optionally includes fresh mechanical regression evidence as supporting diagnostics only. In all cases, the evidence index must include command, exit code, verdict, and `.gsd/exec` stdout/stderr artifact path for each command that is run, and must state whether milestone validation should be `pass`, `needs-attention`, or `needs-remediation` based on both the human gate and mechanical results. Do not mutate README/SECURITY/TODO after an approval or deferral without rerunning docs guardrails and refreshing the gate note.

## Inputs

- `.gsd/milestones/M001/slices/S05/S05-UAT-GATE.md`
- `.gsd/milestones/M001/slices/S05/S05-DOCS-REVIEW-PACKET.md`
- `.gsd/milestones/M001/slices/S05/tasks/T02-SUMMARY.md`
- `README.md`
- `SECURITY.md`
- `TODO.md`
- `tests/test_docs_accuracy.py`
- `tests/test_config_dir.py`
- `tests/test_state.py`
- `tests/test_startup.py`

## Expected Output

- `.gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md`
- `.gsd/exec/*.stdout`
- `.gsd/exec/*.stderr`

## Verification

test -s .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md && grep -q 'Gate status:' .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md && grep -q 'uv run pytest tests/test_docs_accuracy.py -q' .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md && grep -q 'uv run pytest tests/ -x -q' .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md && grep -q 'uv run ruff check triggarr/ tests/' .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md && grep -E 'Release readiness: (ready|blocked|needs-remediation)' .gsd/milestones/M001/slices/S05/S05-RELEASE-GATE-EVIDENCE.md

## Observability Impact

Adds the final inspection surface for validation: command outcomes, gsd_exec artifact paths, stale-scan status, and explicit release-readiness caveats.
