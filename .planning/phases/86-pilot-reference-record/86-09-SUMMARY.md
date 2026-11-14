---
phase: 86-pilot-reference-record
plan: 09
status: complete
subsystem: review-workflow
tags: [pilot, adoption-guide, pilot-03-follow-through, planning-handoff]

requires:
  - phase: 86-pilot-reference-record
    provides: "86-08's five scorecards and the owner's three verbatim PILOT-03 decisions (2026-11-14) in 86-PILOT-RECORD.md"
provides:
  - "docs/review-workflow-adoption.md: reusable GitHub-enforced vs. instruction-enforced adoption guidance for the owner's other repositories (PILOT-04), re-verified against this repository's live GitHub configuration"
  - "PILOT-03 decision 1 put into instruction text: the vibe-check sentences in CLAUDE.md's 'Review-workflow rollout' paragraph and in docs/review-checkpoint-record.md now state that routine vibe-check on every 'code'-class PR ended, vibe-check is required only at high-risk checkpoints, and the D-16 standing items are unchanged"
  - "PILOT-03 decision 2 (FUT-03 not chosen) recorded on the FUT-03 line in REQUIREMENTS.md"
  - "Planning files (STATE.md, ROADMAP.md) updated for the hand-off to Phase 86's once-per-phase review and PR"
affects: []

tech-stack:
  added: []
  patterns:
    - "Adoption-guide pattern: pair each GitHub-enforced control with what it does and does not prove, re-verified against live gh api output rather than carried forward from research notes"

key-files:
  created:
    - docs/review-workflow-adoption.md
  modified:
    - CLAUDE.md
    - docs/review-checkpoint-record.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .planning/STATE.md

key-decisions:
  - "Owner's PILOT-03 decision 1 (2026-11-14, \"take all recommendations\", recorded verbatim in 86-PILOT-RECORD.md and 86-08-SUMMARY.md) is now live in instruction text: routine vibe-check on every \"code\"-class PR ends; vibe-check is required only at a high-risk checkpoint (RISK-02). The D-16 standing items (bot/fork Codex-fallback; BM's high-risk vibe-check recommendation) are explicitly unchanged in both edited sentences."
  - "Owner's PILOT-03 decision 2 (not chosen): the FUT-03 acceptance-gate extension was not chosen; REQUIREMENTS.md's FUT-03 line now says so, dated, with no new ROADMAP backlog entry added (per the owner_decisions instruction, the \"not chosen\" branch takes no further action)."
  - "STATE.md's completed_plans counter is reconciled to 65 (55 before Phase 86 plus all ten of Phase 86's plans, counting this plan). An earlier tooling pass had it at 63, undercounting by one relative to the nine Phase 86 plans (86-01..86-07, 86-10, 86-08) already finished before this plan started; corrected here rather than carried forward."

requirements-completed: [PILOT-04]

duration: ~30min
completed: 2026-11-14
---

# Phase 86 Plan 09: Adoption guide and PILOT-03 follow-through

**Writes the reusable adoption guide for the owner's other repositories, puts the owner's PILOT-03 decision into the vibe-check instruction text, records the FUT-03 "not chosen" decision, and hands the finished Phase 86 plan set off to its once-per-phase review and PR.**

## Performance

- **Duration:** approximately 30 minutes (not separately instrumented at session start; estimated from the two task commits' timestamps and the file-reading work preceding them)
- **Completed:** 2026-11-14T05:38Z
- **Tasks:** 2/2
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments

- Re-read this repository's live GitHub configuration (ruleset, required status checks, protected environment, action pinning, repository visibility) before writing the adoption guide, rather than trusting earlier research notes — see "GitHub configuration checked live" below for every command run and what it returned.
- Wrote `docs/review-workflow-adoption.md`: a product-reader-facing guide with `## Who this is for`, `## The workflow in one page`, `## GitHub-enforced requirements`, `## Instruction-enforced requirements`, `## What the pilot showed`, `## What not to copy blindly`, and `## Adoption checklist` sections, citing `86-PILOT-RECORD.md` for every pilot figure and citing the owner's verbatim PILOT-03 decisions.
- Edited only the vibe-check sentences in CLAUDE.md's "Review-workflow rollout (v2.13)" paragraph and in `docs/review-checkpoint-record.md`'s checkpoint-record template, to state the owner's PILOT-03 decision 1, its date (2026-11-14), and the two D-16 standing items that don't change either way.
- Recorded PILOT-03 decision 2 (FUT-03 not chosen) on the FUT-03 line in `.planning/REQUIREMENTS.md`, dated, with no new backlog entry (per the owner's instruction, the "not chosen" branch takes no further planning action).
- Updated `.planning/ROADMAP.md`: Phase 86 stays unticked (it is executed, not complete); added one line under its plan list naming the two merged pilot PRs (#54, #55) by number.
- Updated `.planning/STATE.md` by hand: refreshed `last_updated`; `Phase:` reads "86 (Pilot & Reference Record) — executed, in review" (contains none of complete/done/await); `Plan: 10 of 10 finished`; reconciled `progress.total_plans: 65` / `progress.completed_plans: 65` (correcting an earlier undercount, documented below); left `completed_phases`/`percent` at 5/71 (phase-based, unchanged, since Phase 86 is in review, not complete); rewrote Operator Next Steps' first bullet to point at the once-per-phase review and Phase 86 PR, the D-14 later-found-misses update before acceptance, then the milestone audit; also refreshed the stale Session Continuity block (it still named a finished 86-08 as "next").

## GitHub configuration checked live

Commands run during Task 1, with what each returned (full output quoted in the return message to the orchestrator):

- `gh api repos/thejuran/triggarr/rulesets` → one ruleset, id `14805779` ("Main Branch Rules"), active, targets the default branch.
- `gh api repos/thejuran/triggarr/rulesets/14805779` → requires pull requests (`required_approving_review_count: 0`, i.e. self-approval permitted — this repository is solo-maintained), blocks deletion and non-fast-forward pushes, requires **strict** (branch-must-be-current) status checks named exactly `CI ready`, `Review acceptance` (both `integration_id: 15368`, the GitHub Actions app) and `CodeQL` (`integration_id: 57789`), and requires a deployment to the `review-acceptance` environment. `bypass_actors` is empty; `current_user_can_bypass: "never"`.
- `gh api repos/thejuran/triggarr/environments` → one environment, `review-acceptance` (id `24603039178`), `required_reviewers` protection naming `thejuran`, `can_admins_bypass: false`.
- `cat greptile.json` → confirms the free-tier posture described in the guide (`effort: "apex"`, review triggers on open/push/rebase and drafts; no tier/cost field, matching the "optional, free tier" description).
- `grep -rn "uses:" .github/workflows/*.yml` and `grep -n "^name:"` on `ci.yml`/`review-acceptance.yml` → every third-party action is pinned to a full 40-character commit SHA with a version comment; workflow names match the required-check names above.
- `gh api repos/thejuran/triggarr --jq '.visibility, .private'` → `public`, `false` — confirms the repository is public, consistent with the publication constraints this guide and the rest of the phase follow.

**Live vs. documented:** no difference found. Every GitHub-enforced item the guide describes matches what the live API returned; nothing in `docs/bm-greptile-codex-blueprint.md` or `docs/buildomator-greptile-pilot.md` had drifted from the live configuration by the time this plan ran.

## Task Commits

1. **Task 1: Write docs/review-workflow-adoption.md** - `627d3d2` (docs)
2. **Task 2: PILOT-03 follow-through and planning-file hand-off** - `10163ca` (docs)

**Plan metadata:** (this summary, committed separately per the final-commit step)

## Files Created/Modified

- `docs/review-workflow-adoption.md` (created) — the adoption guide described above.
- `CLAUDE.md` (modified) — only the vibe-check sentence(s) in the "Review-workflow rollout (v2.13)" paragraph; everything else in the file is unchanged (confirmed by `git diff`, reproduced in the return message).
- `docs/review-checkpoint-record.md` (modified) — only the "Routine vibe-check status" template line; everything else is unchanged (confirmed by `git diff`, reproduced in the return message).
- `.planning/REQUIREMENTS.md` (modified) — one sentence appended to the FUT-03 line.
- `.planning/ROADMAP.md` (modified) — one line added under Phase 86's plan list naming the two merged pilot PRs; the `- [ ] **Phase 86` tick is unchanged.
- `.planning/STATE.md` (modified) — frontmatter (`status`, `stopped_at`, `last_updated`, `last_activity`, `progress.completed_plans`), the "Current focus" line, the "Current Position" block, the first Operator Next Steps bullet, and the Session Continuity block.

## Decisions Made

See `key-decisions` in the frontmatter above. In full: the owner's PILOT-03 decisions were recorded verbatim with date in `86-PILOT-RECORD.md` and `86-08-SUMMARY.md` during the prior plan; this plan's own decision was narrowly procedural — reading `.git/info/exclude`'s local `.planning/` exclusion correctly (continuing the established pattern from 86-08) and reconciling the STATE.md plan counter (see Deviations).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] STATE.md's `completed_plans` counter was undercounted before this plan started**
- **Found during:** Task 2, while computing the target `progress.completed_plans` value per the plan's explicit instruction.
- **Issue:** STATE.md read `completed_plans: 63` going into this plan. Phase 86 has ten plans; nine of them (86-01 through 86-07, plus 86-10 and 86-08, per the phase's documented execution order where 86-10 runs between 86-07 and 86-08) were already finished before this plan started. With 55 plans complete before Phase 86 (per the plan's own stated arithmetic: `total_plans: 65` = 55 + 10), nine finished Phase 86 plans should have made `completed_plans` 64, not 63 — a one-plan undercount somewhere in an earlier automated update.
- **Fix:** Set `completed_plans: 65` directly (55 + all ten Phase 86 plans, counting this plan as completed by this commit), per the plan's explicit target value, rather than incrementing from the stale 63.
- **Cost if wrong:** Low. This is a single integer in a progress-tracking field read by the Roadmaps display page (per `docs/PLANNING-FORMAT.md`) and by no code path that gates anything. If the undercount's root cause recurs, the next phase's plan-count arithmetic should re-derive the "plans before this phase" baseline from ROADMAP.md's per-phase plan counts rather than trusting the running STATE.md total.
- **Files modified:** `.planning/STATE.md` (frontmatter `progress.completed_plans`)
- **Verification:** Re-derived the arithmetic from ROADMAP.md's own v2.13-milestone phase plan-count headers (the milestone STATE.md's `progress` counters track, continuing phase numbering from v2.12 but not counting v2.12's own completed plans): Phase 82 (9 plans) + Phase 83 (10) + Phase 84 (7 plans named, including 84-06 which the owner ruled "not performed" when the phase closed) + Phase 85 (19) + Phase 85.1 (10) = 55, matching `total_plans: 65` minus Phase 86's 10 — and matching the plan's own stated "55 before Phase 86." Cross-checked against the automated verify command's exit status.
- **Committed in:** `10163ca` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (progress-counter reconciliation, flagged by the plan itself as a possible pre-existing miscount)
**Impact on plan:** No scope change. The plan's own text anticipated and instructed this exact correction ("if earlier tooling already changed these numbers, correct them to these values and say so in the SUMMARY").

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None — no external service configuration required. The owner's next action is the phase's once-per-phase review and the Phase 86 PR (classification, BM code review with the paired read-only Codex pass, a RISK-01 note and vibe-check recommendation, the `/deep-review` offer, and exact-commit owner acceptance), which this plan explicitly does not perform — per the plan's objective note, that happens after this plan, on the phase branch.

## PLANNING-FORMAT.md Checklist Result

Checked by inspection (items 1-5 of `docs/PLANNING-FORMAT.md`'s "Checklist after any planning update"; item 6, opening the live Roadmaps page, was **not checked** — this session has no access to that page, so its display is not claimed to have been verified):

1. **STATE.md front matter reflects today:** PASS. `milestone: v2.13` unchanged and still matches ROADMAP's one 🔨 entry; `status` now reads "Phase 86 executed -- both pilot PRs merged (#54, #55); PILOT-01..04 recorded; Phase 86 PR next, in review" (no complete/done/await); `stopped_at` names this plan as the stopping point; `last_updated: "2026-11-14T05:36:37Z"` is today (UTC).
2. **STATE.md `Phase:` starts with the current phase number:** PASS. `Phase: 86 (Pilot & Reference Record) — executed, in review`.
3. **ROADMAP.md has exactly one 🔨 milestone, matching STATE's milestone:** PASS. `🔨 v2.13 CI & Review Workflow -- Phases 82-86 (in progress)` is the only 🔨 line in the Milestones list, and it is v2.13, matching STATE.md's `milestone: v2.13`.
4. **Phase ticks match STATE.md (nothing ticked that STATE still calls in review):** PASS. Both ROADMAP occurrences of Phase 86 (`- [ ] **Phase 86: Pilot & Reference Record**` in the top-level Milestones phase list, and the identical line in the "Phase 86:" detail section's plan list heading) remain unticked, consistent with STATE.md calling the phase "executed, in review" rather than complete.
5. **Agreed future milestones use the prescribed section headings:** PASS. `## Following milestone: Reliability`, `## Later milestone: Authentication Safety & Responsiveness` and `## Later milestone: UI Redesign` all use a recognized heading form (`Following milestone:` / `Later milestone:`) per the format guide.
6. **Live Roadmaps page shows no "Planning files disagree" box:** NOT CHECKED. This session has no browser or page-fetch access to verify the live display; reporting this limitation rather than claiming the page was opened.

**Separately observed, out of this plan's edit scope:** the informal "## Progress" table near the bottom of ROADMAP.md (not one of the five sections `docs/PLANNING-FORMAT.md` describes, and explicitly stated there to be ignored by the page) still reads "| 86. Pilot & Reference Record | 0/10 | Planned | - |", which is stale relative to the now-finished ten plans. This plan's ROADMAP.md edit scope was narrowly specified as "keep Phase 86 unticked; add one line under its plan list noting the two pilot PRs by number," and the binding project rules for this plan restrict STATE/ROADMAP/REQUIREMENTS edits to exactly what the plan specifies and nothing beyond it, so this stale row was left untouched rather than fixed. Flagging it here for whoever next edits ROADMAP.md's Progress table.

## Next Phase Readiness

- All ten Phase 86 plans are finished. Per this plan's objective note, the next step is the phase's once-per-phase review and PR on `phase-86-pilot-reference-record`: classify the PR per `docs/review-classification-policy.md` (this PR touches `CLAUDE.md` and `docs/review-checkpoint-record.md`, both sensitive per that policy, so it classifies as at least `sensitive`, with `code`/`docs` content also present from the rest of the phase's planning and pilot-record commits — classification is the review step's job, not this plan's), BM code review with the paired read-only Codex pass, a RISK-01 note and vibe-check recommendation with the owner's decision, the `/deep-review` offer, one push and one ready-for-review PR, a per-head checkpoint comment, and exact-commit owner acceptance.
- Before that acceptance, `86-PILOT-RECORD.md` should be updated with any later-found misses up to the D-14 cutoff, per this plan's objective note.
- The phase branch should be brought up to date with `main` via `git merge origin/main` (not rebase) before that PR, per the objective note, so cited planning commit SHAs stay valid — not done in this plan, since this plan made no claim about main having moved.

## Self-Check: PASSED

- `docs/review-workflow-adoption.md` — FOUND
- Commit `627d3d2` (Task 1) — FOUND in `git log --oneline --all`
- Commit `10163ca` (Task 2) — FOUND in `git log --oneline --all`
- Task 1 automated verify (heading/citation greps plus private-infrastructure negative greps) — ran, exit 0
- Task 2 automated verify (STATE.md front matter, ROADMAP tick count, REQUIREMENTS FUT-03 line) — ran, exit 0
- `git diff -- CLAUDE.md` and `git diff -- docs/review-checkpoint-record.md` (pre-commit) — inspected by hand; each diff touches only the vibe-check sentence(s) described above, nothing else in either file
- Post-commit deletion check (`git diff --diff-filter=D --name-only HEAD~1 HEAD`) after both commits — ran, empty both times (no unintended deletions)
- `git status --short` after both commits — ran, clean both times (no stray untracked files)

---
*Phase: 86-pilot-reference-record*
*Completed: 2026-11-14*
