---
estimated_steps: 5
estimated_files: 10
skills_used:
  - write-docs
  - verify-before-complete
---

# T02: Repair or canonically supersede S02 evidence inconsistency

Resolve the S02 blocker by either completing the residual S02/T04 task as superseded-by-S04 or writing a canonical S06 supersession artifact if GSD tooling rejects task completion under a closed slice.

Expected executor skills/frontmatter: `write-docs`, `verify-before-complete`.

Steps:
1. Read S02 task summaries, the S02 placeholder summary, the stale S02/T04 plan, `D001`/`D002`, and `S04/tasks/T03-ASSESSMENT.md`.
2. First try `gsd_task_complete` for `M001/S02/T04` with a narrative that S04 superseded T04, no source edits are required, and old direct `X-Forwarded-Proto` wording must not be implemented.
3. If the tool rejects completion, write `.gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md` explaining the residual DB/task-count mismatch and declaring the canonical validation evidence trail.
4. In either path, cite S02 T01/T02/T03 summaries, `S04/tasks/T03-ASSESSMENT.md`, `D001`, `D002`, and `tests/test_docs_accuracy.py` as the evidence chain; do not cite `S02-SUMMARY.md` as proof except as the historical blocker.
5. Do not reopen S02; reopening would reset completed tasks and create needless rework.

Must-haves:
- The artifact or task summary explicitly says the old S02/T04 secure-cookie wording is superseded and unsafe to apply.
- The validation instruction is unambiguous: use S02 task summaries plus S04 T03 assessment, not the placeholder S02 summary.
- The result is compatible with `gsd_milestone_status` whether S02 pending count is repaired or merely canonically accepted.

Failure Modes (Q5):
- Dependency: GSD task completion. On tool rejection, do not force DB state; write the fallback supersession artifact and quote the rejection class without dumping secrets.
- Dependency: stale S02 wording. On encountering forwarded-proto wording that conflicts with D001/D002, treat it as superseded and document that treatment.

Negative Tests (Q7):
- Verify no S06 artifact says direct app routes trust `X-Forwarded-Proto` or that secure cookies are based on a raw forwarded header.
- Verify the fallback artifact exists if S02 still has a pending task after the completion attempt.

Verification:
- `gsd_milestone_status` for M001 shows either S02 pending count is zero or `.gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md` exists and contains `canonical supersession`.
- `rg -n "S04/tasks/T03-ASSESSMENT|D001|D002|canonical supersession|S02-SUMMARY" .gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md .gsd/milestones/M001/slices/S02/tasks/T04-SUMMARY.md`

## Inputs

- `.gsd/DECISIONS.md`
- `.gsd/milestones/M001/slices/S02/S02-SUMMARY.md`
- `.gsd/milestones/M001/slices/S02/tasks/T01-SUMMARY.md`
- `.gsd/milestones/M001/slices/S02/tasks/T02-SUMMARY.md`
- `.gsd/milestones/M001/slices/S02/tasks/T03-SUMMARY.md`
- `.gsd/milestones/M001/slices/S02/tasks/T04-PLAN.md`
- `.gsd/milestones/M001/slices/S04/tasks/T03-ASSESSMENT.md`
- `tests/test_docs_accuracy.py`

## Expected Output

- `.gsd/milestones/M001/slices/S02/tasks/T04-SUMMARY.md`
- `.gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md`

## Verification

Use gsd_milestone_status for M001; pass if S02 pending count is 0, otherwise require `test -s .gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md` and `rg -n "canonical supersession|S04/tasks/T03-ASSESSMENT|D001|D002|S02-SUMMARY" .gsd/milestones/M001/slices/S06/S06-S02-SUPERSESSION.md`.

## Observability Impact

Adds a canonical trail for future validators to inspect S02's repaired or accepted state without relying on inconsistent task counts or the placeholder S02 summary.
