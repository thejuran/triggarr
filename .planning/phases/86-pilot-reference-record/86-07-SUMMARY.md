---
phase: 86-pilot-reference-record
plan: 07
subsystem: review-workflow
tags: [pilot, push, checkpoint-comment, owner-acceptance, merge]

requires:
  - phase: 86-pilot-reference-record
    provides: "86-04 Refresh-counts H_final 1062097a7676fddcdde3caf500f96ba1ea04d65c and 86-06 card-template H_final 46c39194249d1e7bcd2362a91d238d0997539f3f, both review-complete"
provides:
  - "PR #54 (Refresh-counts) accepted by the owner on its exact head and merged: merge commit b80c3e26cf9456dde7245350d7033f6feb94db0f"
  - "PR #55 (card-template) open at 46c39194249d1e7bcd2362a91d238d0997539f3f with a per-head checkpoint comment, handed to 86-10"
affects: [86-10, 86-08]

key-files:
  modified:
    - .planning/phases/86-pilot-reference-record/86-REVIEW-EVIDENCE.md
    - .planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md

key-decisions:
  - "Owner chose 'push both' at the push decision; both pilot PRs were pushed in one batch and opened ready for review."
  - "Owner approved review acceptance for PR #54 at the exact head and run; attempt 1 of the acceptance run predated the register write, so it was cancelled and attempt 2 was the one approved."
  - "The owner instructed 'merge pr 54' in the Claude CLI session and Claude ran the merge under the owner's account, pinned to the accepted head. The plan had the owner run the merge personally; the decision was still the owner's."

requirements-completed: []

completed: 2026-11-13
---

# Phase 86 Plan 07: Push both pilot PRs; accept and merge the first

**Both new pilot PRs are public with per-head checkpoint comments. The Refresh-counts PR (#54) went through the full current review process end to end and is merged. The card-template PR (#55) waits for 86-10.**

## Results

| | PR #54 Refresh-counts | PR #55 Card-template |
|---|---|---|
| Branch | `pilot-refresh-counts-skip-malformed` | `pilot-card-reason-kind` |
| Head | `1062097a7676fddcdde3caf500f96ba1ea04d65c` | `46c39194249d1e7bcd2362a91d238d0997539f3f` |
| CI run | 41158788891 (all passing) | 41158791610 (non-acceptance checks passing) |
| Review acceptance run | 41158788888, attempt 2: success | 41158791675: not presented |
| Checkpoint comment | issuecomment-6537692648 | issuecomment-6537692830 |
| State | Merged 2026-11-14T03:23:00Z, merge commit `b80c3e26cf9456dde7245350d7033f6feb94db0f` | Open, behind main |

- Main moved from `d5a4467` to `b80c3e2`.
- Greptile did not run on either head (optional).
- Owner decisions logged in `86-PILOT-RECORD.md`: push decision, acceptance, merge.

## Deviations

- **Merge executed by Claude on the owner's instruction.** The plan (Task 3, T-86-22) had the owner run the merge. The owner instead replied "merge pr 54" in the session. Claude rechecked the head, checks and main, then merged with `--match-head-commit` on the accepted SHA. Recorded in `86-REVIEW-EVIDENCE.md` under "PR #54 acceptance".
- **Two-week gap.** Acceptance was submitted 2026-10-30; the merge happened 2026-11-13. Head, checks and main were unchanged in between (rechecked before the merge).

## For 86-10

PR #55 is open at `46c39194249d1e7bcd2362a91d238d0997539f3f` and behind main (`b80c3e2`). Merge main in without rebasing, then gather fresh exact-head evidence before presenting acceptance.

## Commits

- `1195263` docs(86-07): record owner push decision for both pilot PRs
- `b505cf3` docs(86-07): pilot PR checkpoint records for PR #54 and PR #55
- `74b9ac6` docs(86-07): record owner acceptance of PR #54
- docs(86-07): record acceptance and merge of the first pilot PR (this commit)
