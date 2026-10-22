---
phase: 83-paired-bm-codex-review-risk-based-depth
plan: "04"
subsystem: process
tags: [review-classification, documentation, planning, codex, policy]

# Dependency graph
requires: []
provides:
  - "docs/review-classification-policy.md: content-based ordinary-docs/sensitive/code classification policy (REVIEW-07) with per-head classification record format"
  - "Amended REVIEW-08 (REQUIREMENTS.md) and Phase 83 criterion 7 (ROADMAP.md) reflecting the owner's D-14 demonstration-scope decision"
affects: [83-06 (CLAUDE.md pointer to this policy), 83-10 (classifying the phase PR against this policy), 85 (ACCEPT-03 GitHub-side mechanism for this policy)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Content-based classification (ordinary-docs/sensitive/code), never file-extension-based"
    - "Per-head classification record carried in the PR checkpoint comment, not a GitHub repository variable (mirrors REVIEW_DISPOSITIONS register shape from docs/buildomator-greptile-pilot.md)"
    - "Classify-upward-when-in-doubt rule for mixed/ambiguous content"

key-files:
  created:
    - docs/review-classification-policy.md
  modified:
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md

key-decisions:
  - "REVIEW-08 and Phase 83 criterion 7 now demonstrate classification on Phase 83's own sensitive-docs/mixed PR instead of a separate ordinary-docs PR (owner decision 2026-10-22, D-14), because D-13 means docs-only PRs are no longer opened to demonstrate the ordinary-docs case standalone"

requirements-completed: [REVIEW-07, REVIEW-08]

# Metrics
duration: ~10min
completed: 2026-10-22
---

# Phase 83 Plan 04: Review Classification Policy & D-14 Scope Amendment Summary

**Content-based review-classification policy (ordinary-docs/sensitive/code, classify-upward-when-in-doubt) plus the owner's D-14 amendment removing the ordinary-docs-PR demonstration from REVIEW-08/criterion 7**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-10-22T18:45:21Z
- **Tasks:** 2 completed
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments
- Wrote `docs/review-classification-policy.md`: defines the three classes (ordinary-docs, sensitive, code) by content rather than file extension, states the mixed-PR "most consequential class" rule, records the D-18/D-13/D-14 ground rules, and specifies the per-head JSON classification record with one worked example per class plus an upward-reclassification example.
- Amended `.planning/REQUIREMENTS.md` REVIEW-08 and `.planning/ROADMAP.md` Phase 83 criterion 7 so both now say the classification demonstration runs on Phase 83's own sensitive-docs/mixed PR, with the owner's 2026-10-22 D-14 decision recorded inline. ACCEPT-03 and all other text in both files left untouched.

## Task Commits

1. **Task 1: Write the review-classification policy** - `2c39cfd` (docs)
2. **Task 2: Record the D-14 scope change in REQUIREMENTS.md and ROADMAP.md** - `949f8d1` (docs)

_No plan-metadata commit was made separately; this SUMMARY.md is committed on its own per the final_commit step._

## Files Created/Modified
- `docs/review-classification-policy.md` - New policy: Principle, Classes table, Mixed changes, Ground rules (D-18/D-13/D-14 plus standing bullets), Classification record (JSON shape + 4 worked examples)
- `.planning/REQUIREMENTS.md` - REVIEW-08's trailing demonstration clause amended; "Last updated" footer refreshed to 2026-10-22
- `.planning/ROADMAP.md` - Phase 83 success criterion 7's demonstration clause amended to match

## Decisions Made
- Kept the policy's per-head classification record in the PR checkpoint comment rather than a GitHub repository variable, per D-10 and the plan's explicit instruction, adapting (not reusing) the `REVIEW_DISPOSITIONS` register shape from `docs/buildomator-greptile-pilot.md`.
- Left ACCEPT-03's existing "an ordinary-docs PR, a sensitive-docs PR" four-case language in `.planning/REQUIREMENTS.md` untouched — it describes Phase 85's GitHub-mechanism verification cases, which are unaffected by Phase 83's D-14 demonstration-scope change.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing literal phrase "classify upward" in the policy text**
- **Found during:** Task 1 verification (acceptance criteria grep)
- **Issue:** The Ground rules section wrote "classifies upward" (inflected form), not the literal "classify upward" string the acceptance criteria requires.
- **Fix:** Reworded D-18's ground rule to "When in doubt, classify upward (toward the more consequential class)."
- **Files modified:** docs/review-classification-policy.md
- **Verification:** `grep -q "classify upward" docs/review-classification-policy.md` now matches.
- **Committed in:** `2c39cfd` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug/wording fix)
**Impact on plan:** Cosmetic wording fix only; no scope change.

## Issues Encountered

**Acceptance-criteria arithmetic note (non-blocking):** Task 2's acceptance criteria state `grep -c "Phase 83 D-14" .planning/REQUIREMENTS.md` should be `1`, but the task's own `<action>` text explicitly specifies verbatim replacement strings that place the phrase "Phase 83 D-14" in REVIEW-08's demonstration clause (line 53) *and* in the "Last updated" footer (line 140) — both exact strings were given word-for-word in the plan's `<context>` "Exact text to amend" block and in Task 2's `<action>`. The actual count is 2, matching the plan's own literal instructions exactly. All other acceptance checks (the 0/0 "ordinary-docs PR and a sensitive-docs PR" grep, the `owner decision 2026-10-22` count ≥1, the ACCEPT-03 four-case phrase still present exactly once, and `git diff HEAD~1 --stat` listing only the two intended files) passed as specified. I followed the plan's verbatim text rather than altering the wording to force the count down to 1, since the verbatim text was given as the authoritative content to write.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `docs/review-classification-policy.md` is ready for Plan 06 to point to from `CLAUDE.md` (per CONTEXT.md's "Keep CLAUDE.md concise" discretion — the policy is referenced, not restated inline).
- `.planning/REQUIREMENTS.md` and `.planning/ROADMAP.md` now consistently describe Phase 83's own sensitive-docs/mixed PR as the REVIEW-08/criterion-7 demonstration target, which Plan 10 (classify the phase PR) will need to satisfy.
- `.planning/STATE.md` and `.planning/config.json` were not touched by this plan, per the binding rules; STATE.md tracking is the orchestrator's responsibility.
- Full test suite run: `uv run pytest tests/ -x -q` → 2171 passed, 38 warnings, in 102.08s (run after both task commits, on the current HEAD at that time). `uv run pytest tests/test_docs_accuracy.py -q` → 5 passed (this suite does not reference the new policy doc; it checks README/SECURITY/TODO only, confirmed unaffected).

---
*Phase: 83-paired-bm-codex-review-risk-based-depth*
*Completed: 2026-10-22*

## Self-Check: PASSED

- FOUND: docs/review-classification-policy.md
- FOUND: .planning/phases/83-paired-bm-codex-review-risk-based-depth/83-04-SUMMARY.md
- FOUND: 2c39cfd (git log --oneline --all)
- FOUND: 949f8d1 (git log --oneline --all)
