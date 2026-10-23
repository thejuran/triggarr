---
phase: 83-paired-bm-codex-review-risk-based-depth
plan: "06"
subsystem: review-workflow
tags: [claude-md, codex, review-classification, guard-test, repository-instructions]

# Dependency graph
requires:
  - phase: 83-paired-bm-codex-review-risk-based-depth (Plan 02)
    provides: "docs/codex-adversarial-review-contract.md (the fixed Codex prompt/invocation CLAUDE.md now points to)"
  - phase: 83-paired-bm-codex-review-risk-based-depth (Plan 03)
    provides: "tests/codex_report_status.py (the checker docs/review-checkpoint-record.md's Codex section cites)"
  - phase: 83-paired-bm-codex-review-risk-based-depth (Plan 04)
    provides: "docs/review-classification-policy.md (the classification policy CLAUDE.md now points to)"
  - phase: 83-paired-bm-codex-review-risk-based-depth (Plan 05)
    provides: "docs/bm-review-baseline-2026-10-22.md's \"Installed behavior re-check\" (the disclosed gaps CLAUDE.md's Review workflow bullets fill)"
provides:
  - "docs/review-checkpoint-record.md: the one-comment-per-head-SHA PR evidence record template (D-10), snapshot-before-re-review rule (REVIEW-06), triage rules (D-08) and owner acceptance checklist template (D-12)"
  - "CLAUDE.md \"Review workflow\" section: classification pointer, automatic Codex-pairing instruction naming all four BM review paths, checkpoint-record pointer, and the three disclosed installed-behavior gaps as standing instructions"
  - "CLAUDE.md \"Review-workflow rollout (v2.13)\" section replacing the expired \"Deferred review-workflow proposal\""
  - "docs/buildomator-greptile-pilot.md \"Routine BM workflow\" now links the classification policy and checkpoint record"
  - "tests/test_review_instructions.py: a 4-test guard pinning the three review-doc links and five existing hard constraints in CLAUDE.md"
affects: [83-10 (classifying the phase PR against the policy CLAUDE.md now links), 83-REVIEW-EVIDENCE.md (uses this plan's checkpoint-record template)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Guard test for agent instructions: a stdlib-only pytest module asserts both presence of new doc links and persistence of pre-existing hard-constraint strings in CLAUDE.md, so a future restructure cannot silently drop either"
    - "Restructure named CLAUDE.md sections rather than find-and-replace a literal string, since no literal \"every PR\" string existed (confirmed by grep) -- the blanket framing was conceptual"

key-files:
  created:
    - docs/review-checkpoint-record.md
    - tests/test_review_instructions.py
  modified:
    - CLAUDE.md
    - docs/buildomator-greptile-pilot.md

key-decisions:
  - "The required grep scan (\"every (PR|push|change)|all PRs|each PR\") across CLAUDE.md, docs/buildomator-greptile-pilot.md, docs/owner-cli-acceptance.md, greptile.json, .claude/agents, .claude/commands found exactly one hit: docs/buildomator-greptile-pilot.md line 78, \"Every push to a PR uses one of Greptile's limited free reviews...\". Judged this to describe Greptile's own per-push billing behavior (push-budget management), not a mandate that every PR gets full review regardless of content -- left unchanged, disclosed in both the Task 2 commit message and here rather than silently passed over"
  - "Kept the three disclosed Plan 05 installed-behavior gaps (quick-task --full requirement, phase-execution once-per-phase timing, quick-task hardcoded `quick` depth) as three short CLAUDE.md bullets rather than one combined paragraph, so each is independently greppable and matches the plan's \"one gap-fill bullet for each difference\" instruction"
  - "Single commit for Task 2 (test file + CLAUDE.md + pilot doc) rather than separate RED/GREEN commits: the plan's own <action> text specifies one commit message (\"docs(83-06): wire paired review and classification into CLAUDE.md\") for this instruction-guard task, distinct from Plan 02/03's schema+behavior TDD tasks which specified two commits explicitly. The RED-then-GREEN discipline was still followed (test written and confirmed failing for the right reason before any CLAUDE.md edit)"

patterns-established:
  - "Pattern: an agent-instructions guard test (tests/test_review_instructions.py) is the reusable shape for pinning future CLAUDE.md restructures -- assert both new required links exist and known hard-constraint strings survive"

requirements-completed: [REVIEW-02, REVIEW-03, REVIEW-05, REVIEW-06, REVIEW-08, RISK-01, RISK-02]

# Metrics
duration: ~8min
completed: 2026-10-22
---

# Phase 83 Plan 06: Wire Paired Review Into CLAUDE.md Summary

**Wrote the PR checkpoint-record procedure (one comment per head SHA, RISK-01/RISK-02, triage, owner acceptance checklist) and restructured CLAUDE.md's review sections to point at it and at the classification policy and Codex contract, guarded by a 4-test suite, while preserving every existing hard constraint.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-10-22T19:03:12Z
- **Completed:** 2026-10-22T19:10:42Z
- **Tasks:** 2
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- Wrote `docs/review-checkpoint-record.md`: "Where the record lives" (one comment per head SHA, `gh pr comment`/`gh api PATCH`, pre-PR fallback to the phase folder, durable copy, dispositions surviving bot-thread resolution), the full fenced checkpoint template (commit identities, classification, RISK-01 risk note, RISK-02 vibe-check section, BM review table, Codex table + findings table, Greptile, CI, dispositions table, incomplete items), "Rules" (requested-vs-actual depth, evidence-per-head, PENDING wording), "Before any re-review" (the `REVIEW.md` snapshot command plus the "Original vs. refreshed findings" table requirement), "Triage" (D-08's reproduce/classify/batch-fix/no-auto-loop rules), and the "Owner acceptance checklist" fenced CLI-message template.
- Ran the required repository-wide grep for unconditional "every PR/push/change" review wording before editing; found and disclosed the one hit (Greptile's own push-budget sentence, unrelated to classification).
- Wrote `tests/test_review_instructions.py` first, confirmed it failed for the right reason (CLAUDE.md didn't yet link the new docs), then restructured CLAUDE.md: replaced "Buildomator + Greptile pilot" with "Review workflow" (classification pointer, automatic Codex-pairing instruction naming phase execution/quick task/`/bm:code-review`/review after fixes, checkpoint-record pointer, the three disclosed gap-fill bullets, the preserved hard-constraint paragraph, and a limiting sentence bounding the standing instruction's authority) and replaced "Deferred review-workflow proposal — after v2.12" with "Review-workflow rollout (v2.13)". Added one sentence to `docs/buildomator-greptile-pilot.md`'s "Routine BM workflow" linking the new policy and record docs.
- Confirmed the guard test green (4 passed), `uv run ruff check tests/` clean, and the full suite green.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write the checkpoint-record procedure** - `652b569` (docs)
2. **Task 2: Restructure CLAUDE.md and the pilot doc's routine workflow, with a guard test** - `719359a` (docs)

**Plan metadata:** this SUMMARY.md commit (docs: complete plan)

## Files Created/Modified

- `docs/review-checkpoint-record.md` - PR checkpoint-record procedure: where the record lives, the fenced template, rules, the pre-re-review snapshot step, triage, and the owner acceptance checklist template
- `CLAUDE.md` - "Review workflow" replaces "Buildomator + Greptile pilot"; "Review-workflow rollout (v2.13)" replaces "Deferred review-workflow proposal — after v2.12"; one added sentence in "Deep Code Review Convention"; "Development Commands", "Code Conventions", "Planning file format", and "Active owner approval through Claude CLI" unchanged
- `docs/buildomator-greptile-pilot.md` - One added sentence in "Routine BM workflow" linking the classification policy and checkpoint record; activation checklist, register shape, and protections text unchanged
- `tests/test_review_instructions.py` - 4 tests: review-doc links exist and are linked, five hard constraints survive, the Codex-pairing instruction names all four BM paths, the pilot doc links the policy

## Decisions Made

- Disclosed the one grep hit for unconditional review wording (`docs/buildomator-greptile-pilot.md` line 78, Greptile's per-push billing sentence) as out of scope rather than editing it, since it describes Greptile's own automatic-review cost behavior, not a mandate that every PR receives full review regardless of content.
- Wrote the three Plan 05 installed-behavior gaps as three separate, independently greppable CLAUDE.md bullets (quick-task `--full` requirement; phase-execution once-per-phase timing; quick-task hardcoded `quick` depth) rather than folding them into prose, per the plan's "one gap-fill bullet for each difference" instruction.
- Used a single commit for Task 2 covering the guard test plus both doc edits, matching the plan's own single commit-message instruction for this task, while still performing the RED-then-edit sequence the `tdd="true"` attribute requires.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Acceptance-criteria verify command undercounted at first draft**
- **Found during:** Task 1 verification
- **Issue:** The initial doc text used "one PR comment per head SHA" where the plan's verify command greps for the literal substring "one comment per head SHA"; the mismatch left the grep's distinct-matching-line count at 4, one short of the required minimum of 5.
- **Fix:** Reworded the opening sentence of "Where the record lives" to "The authoritative record is **one comment per head SHA** on the phase PR (D-10)", making the literal phrase present on its own matched line without changing its meaning.
- **Cost if wrong:** None observed — purely a wording/grep-count fix with no behavior or scope change; re-verified the count reached 5 and all other acceptance strings were unaffected.
- **Files modified:** docs/review-checkpoint-record.md
- **Commit:** `652b569` (Task 1 commit; fixed before committing)

**2. [Rule 1 - Bug] Line-wrap split the literal string "Greptile is optional" across a newline**
- **Found during:** Task 2 verification (`test_claude_md_keeps_hard_constraints`)
- **Issue:** The first draft of the new "Review-workflow rollout (v2.13)" section wrapped prose at the paragraph's natural word boundary, which happened to place a newline between "is" and "optional", so the exact-substring check for "Greptile is optional" failed even though the sentence's meaning was unchanged and present.
- **Fix:** Re-wrapped the paragraph so "Greptile is optional" stays on one line.
- **Cost if wrong:** None observed — cosmetic re-wrap only; re-ran the guard test and confirmed all 4 tests pass afterward.
- **Files modified:** CLAUDE.md
- **Commit:** `719359a` (Task 2 commit; fixed before committing)

---

**Total deviations:** 2 auto-fixed (both wording/line-wrap fixes caught by the task's own verification step before committing; no scope change)

## Issues Encountered

None beyond the two auto-fixed wording issues above, both caught by running the plan's own verification commands before committing rather than assuming the first draft passed.

## User Setup Required

None — no external service configuration required. This plan creates/edits documentation and a test file only; no `.planning/config.json` key, BM setting, or STATE.md/ROADMAP.md field was touched (binding rule honored: no `bm-sdk` STATE/ROADMAP writers were run, and `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/config.json` are untouched by this plan — confirmed via `git status --short` after both commits).

## Verification Results

- `uv run pytest tests/test_review_instructions.py -x -q` → 4 passed
- `uv run pytest tests/ -x -q` → 2205 passed, 38 pre-existing warnings (same warnings as Plan 05's baseline run; no new warnings), 90.79s
- `uv run ruff check triggarr/ tests/` → All checks passed
- `grep -c "^## Buildomator + Greptile pilot\|^## Deferred review-workflow proposal" CLAUDE.md` → 0 (exit 1, no match, as expected for `grep -c` on zero matches)
- `grep -c "^## Review workflow" CLAUDE.md` → 1
- `grep -c "This standing permission does not approve any pending PR" CLAUDE.md` → 1
- `git diff HEAD~1 -- docs/buildomator-greptile-pilot.md` (against `719359a`) → additions only, both inside "Routine BM workflow"
- `git diff --diff-filter=D --name-only HEAD~1 HEAD` after each commit → empty (no unexpected deletions)
- `grep -c "one comment per head SHA\|review-checkpoint head=\|Owner acceptance checklist\|Before any re-review\|codex_report_status.py" docs/review-checkpoint-record.md` → 5
- CLAUDE.md links all three review docs (`docs/review-classification-policy.md`, `docs/codex-adversarial-review-contract.md`, `docs/review-checkpoint-record.md`) and each exists on disk — confirmed

## Threat Model Disposition

All four T-83-19..22 threats from the plan's threat model were mitigated as specified:
- **T-83-19** (Codex instruction read as broader authority): the limiting sentence "This standing instruction authorizes only running the read-only Codex review; it approves no PR and waives no review." is present in CLAUDE.md's "Review workflow" section.
- **T-83-20** (restructure silently drops a safeguard): `tests/test_review_instructions.py::test_claude_md_keeps_hard_constraints` pins all five required strings; the owner-CLI-acceptance section was left byte-for-byte untouched.
- **T-83-21** (evidence edited across heads): `docs/review-checkpoint-record.md` states a new head always gets a new comment, earlier heads' comments are never edited or deleted, and contains no instruction to use `--edit-last` (confirmed by grep).
- **T-83-22** (information disclosure via PR comments): the template carries only SHAs, paths, and findings; no raw-output-scanning step was altered by this plan (that step lives in Plan 02's contract, unchanged here).

No new threat surface (network endpoints, auth paths, file access patterns, or schema changes at trust boundaries) was introduced by this plan — it is documentation and a stdlib-only read-only test file.

## Known Stubs

None. This plan's deliverables are policy/procedure documentation and a guard test; there is no application code or UI with a data-wiring gap to track.

## Next Phase Readiness

- `docs/review-checkpoint-record.md`'s template is ready for Plan 10 (classifying and recording the Phase 83 PR itself) and for `83-REVIEW-EVIDENCE.md`/`83-DEMONSTRATIONS.md` to use directly.
- CLAUDE.md now points every future session at the classification policy, the Codex contract, and the checkpoint record, with the three disclosed Plan 05 gaps recorded as standing instructions rather than left as institutional knowledge.
- `tests/test_review_instructions.py` will catch a future restructure that drops a doc link or a hard constraint, without needing a human to re-read the whole file.
- No blockers. `.planning/STATE.md`, `.planning/ROADMAP.md`, and `.planning/config.json` were not modified by this plan.

---
*Phase: 83-paired-bm-codex-review-risk-based-depth*
*Completed: 2026-10-22*

## Self-Check: PASSED

- FOUND: docs/review-checkpoint-record.md
- FOUND: tests/test_review_instructions.py
- FOUND: CLAUDE.md
- FOUND: docs/buildomator-greptile-pilot.md
- FOUND: .planning/phases/83-paired-bm-codex-review-risk-based-depth/83-06-SUMMARY.md
- FOUND commit `652b569` (Task 1)
- FOUND commit `719359a` (Task 2)
