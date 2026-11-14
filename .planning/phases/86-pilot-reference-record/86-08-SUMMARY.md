---
phase: 86-pilot-reference-record
plan: 08
status: complete
subsystem: review-workflow
tags: [pilot, vibe-check, bm-codex, acceptance-gate, owner-decision]

requires:
  - phase: 86-pilot-reference-record
    provides: "86-07's merged PR #54 and 86-10's merged PR #55, both with exact-head review evidence in 86-REVIEW-EVIDENCE.md"
provides:
  - "All five pilot PRs scored with the seven D-10 metrics per reviewer (PILOT-01 complete)"
  - "D-05 category gap recorded (UI category covered only by a no-visible-difference template refactor)"
  - "Both pilot backlog items in MAINTENANCE.md marked resolved with their merged PR numbers"
  - "Claude's PILOT-03 recommendation, applying the pre-registered D-15 bar mechanically to the pilot evidence"
  - "The owner's three PILOT-03 decisions recorded verbatim with date (PILOT-03 complete)"
affects: [86-09]

tech-stack:
  added: []
  patterns:
    - "Phase-level owner decisions (not attributable to a single pilot PR) get their own rows in the Owner decisions log, labeled 'phase-level; not attributable to PR #N', so they never change a PR scorecard's owner-effort count (which is defined as that PR's row count in the same table)."

key-files:
  modified:
    - .planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md
    - .planning/backlog/MAINTENANCE.md

key-decisions:
  - "PILOT-03 decision 1 — owner reply \"take all recommendations\" (2026-11-14), adopting Claude's recommendation as presented: routine vibe-check on every \"code\"-class PR ends; vibe-check becomes a required step only at high-risk checkpoints (the same RISK-02 trigger). The D-16 standing items (bot/fork Codex-fallback; RISK-02's high-risk vibe-check recommendation) are unchanged by this decision."
  - "PILOT-03 decision 2 — owner reply \"take all recommendations\" (2026-11-14), adopting Claude's recommendation as presented: the BM/Codex completion check at acceptance stays the owner's manual checklist review (option a). The acceptance-gate extension (FUT-03) was not chosen — it remains scheduled as FUT-03, not built in Phase 86."
  - "PILOT-03 decision 3 — owner reply \"take all recommendations\" (2026-11-14), adopting Claude's recommendation as presented: YES, 86-09's Phase 86 PR will update the vibe-check sentences in CLAUDE.md's \"Review-workflow rollout\" paragraph and in docs/review-checkpoint-record.md to match decision 1, rather than leaving that as a recorded follow-up. This is noted in the record as making the Phase 86 PR an instruction change, classified sensitive."

requirements-completed: [PILOT-01, PILOT-03]

duration: 10min
completed: 2026-11-14
---

# Phase 86 Plan 08: Pilot scorecards complete and the owner's PILOT-03 decisions recorded

**All five pilot PRs are scored on the seven D-10 metrics; the owner adopted Claude's PILOT-03 recommendation in full — routine vibe-check ends in favor of a high-risk-only trigger, the manual BM/Codex completion check stays as-is, and the instruction-text update rides in the Phase 86 PR rather than a follow-up.**

## Performance

- **Duration (this continuation):** ~10 min (Task 3 recording + summary; Tasks 1-2 were completed in a prior session)
- **Completed:** 2026-11-14T05:28:12Z
- **Tasks:** 3/3 (Tasks 1 and 2 committed in a prior session; Task 3 completed in this session)
- **Files modified:** 2 (`86-PILOT-RECORD.md`, `.planning/backlog/MAINTENANCE.md`)

## Accomplishments

- Filled in the Refresh-counts (PR #54) and Card-template (PR #55) scorecards with all seven D-10 metrics per reviewer, added a cross-PR summary table, and recorded the D-05 UI-category gap honestly (a no-visible-difference template refactor, not a demonstration of visible-UI review coverage).
- Resolved both pilot-related backlog items in `MAINTENANCE.md` with their merged PR numbers (PR #54, PR #55); left SA-01 and SA-12 untouched.
- Wrote the PILOT-03 recommendation by applying the D-15 bar (fixed before any result existed, confirmed byte-identical to the 86-01 commit) mechanically to the full pilot evidence.
- Presented both recommendations plus a third question about instruction-text timing to the owner at the Task 3 checkpoint; recorded all three decisions verbatim with date, each in its own clearly labeled line and as its own phase-level row in the Owner decisions log.

## For 86-09

86-09 must:

1. **Stop treating routine vibe-check as a required step on every "code"-class PR.** Scope the required vibe-check trigger to high-risk checkpoints only (the same condition RISK-02 already uses to recommend an extra vibe-check). The D-16 standing items — bot/fork PRs keep the vibe-check fallback when Codex stays INCOMPLETE/PENDING after retry, and BM still recommends an extra vibe-check at high risk — are unchanged.
2. **Make no change to the acceptance gate.** The manual owner check (the acceptance checklist in `docs/review-checkpoint-record.md`) stays as the BM/Codex completion check. FUT-03 (a mechanical gate extension) is not built in Phase 86.
3. **Update the instruction text in the same Phase 86 PR, not as a follow-up:** the vibe-check sentences in `CLAUDE.md`'s "Review-workflow rollout" paragraph and in `docs/review-checkpoint-record.md` must be brought in line with decision 1 (high-risk-only trigger, D-16 items unchanged). This makes the Phase 86 PR an instruction change — classify it as sensitive per the repo's review-classification policy, with the review and acceptance steps that classification implies.

## Task Commits

1. **Task 1: Scorecards for the two new PRs, gap check, backlog items settled** - `7d7ac26` (docs) — completed in a prior session
2. **Task 2: Write the PILOT-03 recommendation from the fixed bar** - `e375521` (docs) — completed in a prior session
3. **Task 3: Owner's PILOT-03 decisions** - `5003c6e` (docs) — completed in this session

**Plan metadata:** (this summary) `docs(86-08): complete plan summary`

## Files Created/Modified

- `.planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md` — Task 1 added the Refresh-counts and Card-template scorecards, the cross-PR summary table, and the D-05 gap note; Task 2 added the PILOT-03 recommendation (Decisions 1 and 2) under the bar-check; Task 3 replaced both "pending" lines with the owner's verbatim decisions, added a new decision 3 line, and logged all three as phase-level rows in the Owner decisions log.
- `.planning/backlog/MAINTENANCE.md` — Task 1 marked the "Refresh counts vs. scheduled cycles on a malformed record" and "Card-template text-matching refactor" items resolved, each with its merged PR number and merge SHA.

## Decisions Made

See `key-decisions` in the frontmatter above for the three PILOT-03 decisions in full, each with the owner's verbatim reply and date.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Resolved a tally/listed-findings mismatch in 86-REVIEW-EVIDENCE.md by using the Dispositions table, not the prose tally line**
- **Found during:** Task 1 (Card-template PR #55 scorecard)
- **Issue:** `86-REVIEW-EVIDENCE.md`'s H1 tally line for the Card-template PR reads "unproven 5 BM-side (WR-01, IN-01, IN-02, SA-01; Codex 0)" — the parenthetical names only 4 findings (WR-01, IN-01, IN-02, SA-01) while the count says 5, an internal inconsistency in a committed record.
- **Fix:** Rather than propagate the ambiguous "5" into the scorecard, the scorecard's BM row was built directly from the two heads' Dispositions tables (the authoritative per-finding record): H1 lists `bm:46c39194249d:WR-01`, `IN-01`, `IN-02`, `SA-01` (4 rows); the integration head lists `bm:5d58264e93a2:WR-01`, `IN-01`, `IN-02`, `IN-03` (4 rows, SA-01 not raised again, IN-03 new). The scorecard names the union across both heads — WR-01, IN-01, IN-02, IN-03, SA-01 (5 distinct findings) — all dispositioned `nonblocking_debt`/unproven, none fixed or false_positive.
- **Cost if wrong:** If the undercount in the source tally line were instead a real missing finding (not a counting slip), the scorecard's confirmed-defects-by-BM figure (0) would still be correct, since every listed finding across both heads is unproven/nonblocking_debt either way — this reconciliation only affects which finding IDs are named, not any count that feeds the PILOT-03 recommendation.
- **Files modified:** `.planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md` (PR #55 scorecard, committed in Task 1)
- **Verification:** Cross-checked both heads' Dispositions tables in `86-REVIEW-EVIDENCE.md` line by line against the scorecard's finding list.
- **Committed in:** `7d7ac26` (Task 1 commit)

**2. [Rule 3 - Blocking] Used `git add -f` to stage the modified record file**
- **Found during:** Task 3 commit
- **Issue:** A local `.git/info/exclude` entry matches `.planning/`, so a plain `git add` silently skips files under that path.
- **Fix:** Staged `86-PILOT-RECORD.md` explicitly with `git add -f` for the Task 3 commit (and this applies to the new `86-08-SUMMARY.md` as well, which is also under the excluded path).
- **Cost if wrong:** None observed — this is a staging mechanic, not a content change; `git status --short` after each add/commit confirmed exactly the intended file was staged and no unrelated excluded file was swept in.
- **Files modified:** none beyond what each task already modified
- **Verification:** `git status --short` before and after each `git add -f` showed only the intended file staged.
- **Committed in:** `5003c6e` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 bug reconciliation, 1 blocking mechanic)
**Impact on plan:** Neither changes any number that feeds the PILOT-03 recommendation or the owner's decisions. No scope creep.

## Issues Encountered

None beyond the two deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- PILOT-01 and PILOT-03 are both complete; the pilot record (`86-PILOT-RECORD.md`) is the full evidence and decision trail for 86-09.
- 86-09 has a concrete, unambiguous mandate: narrow the vibe-check trigger to high-risk checkpoints in both `CLAUDE.md` and `docs/review-checkpoint-record.md`, make no acceptance-gate change, and treat the resulting PR as a sensitive instruction change under the repo's own classification policy.
- The `## Retirement bar (D-15, fixed before results)` section in `86-PILOT-RECORD.md` was re-checked byte-identical to commit `bbabaf8be53a85e60431dbb03d71c837a6b1afb5` after this plan's edits (`git diff bbabaf8be53a85e60431dbb03d71c837a6b1afb5 HEAD -- .planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md`, filtered to that section only, shows no added or removed line).

## Self-Check: PASSED

- `.planning/phases/86-pilot-reference-record/86-08-SUMMARY.md` — FOUND
- `.planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md` — FOUND
- `.planning/backlog/MAINTENANCE.md` — FOUND
- Commit `7d7ac26` (Task 1) — FOUND in `git log --oneline --all`
- Commit `e375521` (Task 2) — FOUND in `git log --oneline --all`
- Commit `5003c6e` (Task 3) — FOUND in `git log --oneline --all`
- Task 3 automated verify (`! grep -n "Owner decision (PILOT-03 decision [12]): pending" ... && grep -c "Owner decision (PILOT-03 decision [12])" ...`) — ran, exit 0, printed `2`
- Retirement bar byte-identity re-check against `bbabaf8be53a85e60431dbb03d71c837a6b1afb5` — ran, no diff lines inside the section
- Public-repo leak grep (`/Users/`, `/home/`, username, NAS/tailnet names) on this summary and on the committed diff — ran, no matches

---
*Phase: 86-pilot-reference-record*
*Completed: 2026-11-14*
