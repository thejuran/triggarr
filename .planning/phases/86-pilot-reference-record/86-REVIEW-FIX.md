---
phase: 86-pilot-reference-record
fixed_at: 2026-11-14T06:02:13Z
review_path: .planning/phases/86-pilot-reference-record/86-REVIEW.md
iteration: 1
findings_in_scope: 17
fixed: 17
skipped: 0
rejected: 0
status: all_fixed
---

# Phase 86: Code Review Fix Report

**Fixed at:** 2026-11-14T06:02:13Z
**Source review:** `.planning/phases/86-pilot-reference-record/86-REVIEW.md`
**Iteration:** 1
**Base:** `6ba6a51` on `phase-86-pilot-reference-record`; commits made directly on that branch (no worktree).

**Summary:**
- Findings in scope: 17 (1 critical, 8 warning, 5 info, 3 set-aside items brought into scope by ruling)
- Fixed: 17
- Skipped: 0
- Rejected: 0

All changes are to documentation and agent-instruction text. No application code, test, or `.github/` file was changed. Five items are left for a ruling; see the last section.

## Rulings applied

The review set three items aside for a ruling. The fixes follow the rulings given with the fix request:

- **R1 (CR-01 / SA-01):** vibe-check is required when a checkpoint's risk is assessed high; it is not run routinely below high risk. One vibe-check at high risk, not an extra one on top. Instruction-enforced, not GitHub-enforced.
- **R2 (WR-04):** the Codex-incomplete fallback is unchanged and applies to any head; bot/fork PRs are the standing case.
- **R3 (WR-03):** a per-head `Vibe-check status` fill-in field in the checkpoint template, with the standing rule in the guidance text.
- **R4 (WR-01, WR-02, SA-03):** stale "decide later" wording updated to the 2026-11-14 decisions.
- **R5 (WR-05..08, IN-01..05):** adoption-guide facts corrected after checking each.
- **R6 (SA-02):** two self-contradictions in the pilot record corrected, with the bar, decision lines and decisions log untouched.

## Fixed Issues

### CR-01 / SA-01 / WR-01 / WR-03 / WR-04: one statement of the vibe-check rule everywhere

Committed together because they edit the same sentences.

**Files modified:** `CLAUDE.md`, `docs/review-checkpoint-record.md`, `docs/review-classification-policy.md`, `docs/bm-greptile-codex-blueprint.md`, `docs/buildomator-greptile-pilot.md`, `docs/review-workflow-adoption.md`
**Commit:** `05516b0`
**Status:** fixed: requires human verification (these are instruction semantics; no test checks them)
**Applied fix:**
- `CLAUDE.md`: the "Review workflow" bullet now says the checkpoint carries, whenever risk is high, the required vibe-check (RISK-02) with a record that it ran and where its report is. The rollout paragraph states the rule in the R1 words, drops "an extra vibe-check", and states the fallback for any head with bot/fork PRs as the standing case. Nothing else in the file changed.
- `docs/review-checkpoint-record.md`: the template's "Recommendation" and "Owner's decision" fields are replaced by a "Required vibe-check" line (rationale and scope); the fixed policy prose is replaced by a `Vibe-check status` field with exactly three cases (ran because risk is high, with report location; not run because risk is below high; ran as the owner-approved Codex fallback for this head, with report location). The standing rule moved to a new bullet in "Rules". The REVIEW-06 rule (former line 126) and the acceptance checklist line (former line 179) use the same three cases.
- `docs/review-classification-policy.md`: the sensitive row, the code row and the mixed-changes paragraph say "the required vibe-check when risk is assessed high"; the code row no longer lists routine vibe-check.
- `docs/bm-greptile-codex-blueprint.md`: a dated note (2026-11-14) after the "Until then" sentence records both PILOT-03 decisions, names what in the document it supersedes, and points to the pilot record. The October 18 text is otherwise unchanged.
- `docs/buildomator-greptile-pilot.md`: the two sentences that told the owner to run vibe-check on every application-code checkpoint now state the rule, dated, and the any-head fallback.
- `docs/review-workflow-adoption.md`: step 5, instruction item 6, owner decision 1 and the checklist line use the same rule; item 6 states the fallback for any pull request.

### WR-02: Checkpoint record still says the FUT-03 decision is pending

**Files modified:** `docs/review-checkpoint-record.md`
**Commit:** `8aab3c9`
**Applied fix:** Line 3 now records the 2026-11-14 decision: BM/Codex completion stays the owner's manual check at acceptance; FUT-03 was not chosen.

### SA-03: Planning text that still describes routine vibe-check as in force

**Files modified:** `.planning/REQUIREMENTS.md`
**Commit:** `46d8f8c`
**Applied fix:** Only the first standing-rule sentence changed: it now reads in the past tense and carries the 2026-11-14 outcome. No requirement was ticked or reworded.

### SA-02: The pilot record contradicts itself on two points

**Files modified:** `.planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md`
**Commit:** `7d12f42`
**Applied fix:**
- PR #36 scorecard, vibe-check row, and the matching cross-PR summary cell: 0 at the time of PR #36 (all 25 findings `nonblocking_debt`, none reproduced then); 2 later confirmed by reproduction when fixed in PR #44, citing `b0e1ee4` ("Verified: with both pins bumped, the old tests fail 2 and the new pass 87/87") and `3b3713b` ("Verified: passes with the phase dir moved away"). Both messages were read with `git show -s`.
- PILOT-03 "Across the rest of the pilot": PR #44 now says vibe-check did not run; the PR #55 part says one unproven test-gap note that BM also noted (`86-REVIEW-EVIDENCE.md`: `vibe-check:46c39194249d:cov-001` is "same gap as `bm:…:WR-01`").
- PILOT-03 PR #36 items cite the same reproduction proof for D-09.
- A dated "Corrections (2026-11-14, after code review iteration 1)" section was added at the end.
- **Bar check:** the `## Retirement bar (D-15, fixed before results)` section is byte-identical to commit `bbabaf8` (594 bytes each, same SHA-256 `d3ae6696…541ada5`, `cmp` clean).
- The three `Owner decision (PILOT-03 decision N)` lines and every row of the owner decisions log are unchanged. The optional alignment of decision 1's descriptive clause was not made.

### WR-05: Guide says GitHub has no setting for full-SHA action pinning

**Files modified:** `docs/review-workflow-adoption.md`
**Commit:** `7abdef0`
**Applied fix:** "How to set it up" now names the repository Actions setting and says GitHub refuses to run a workflow with an unpinned action; the limits paragraph says it stops the run rather than the merge. The checklist item includes turning the setting on. The section intro now says what was read live and when. Live reads on 2026-11-14 (read-only): `gh api repos/thejuran/triggarr/actions/permissions` returned `{"enabled":true,"allowed_actions":"all","sha_pinning_required":true}`; the ruleset (active, no bypass actors, strict checks `CI ready`, `Review acceptance`, `CodeQL`, required deployment to `review-acceptance`), the environment (`can_admins_bypass: false`, one required reviewer, `prevent_self_review: false`) and code-scanning default setup (`configured`) were also re-read.

### WR-06 / WR-07 / IN-05: Pilot claims not supported by the pilot record

Committed together because they are adjacent sentences in "What the pilot showed".

**Files modified:** `docs/review-workflow-adoption.md`
**Commit:** `0db8601`
**Applied fix:** Three of five PRs are described as scored afterwards from committed evidence, two as run fresh. The two PR #36 catches are described as CI traps (a routine dependency update would have made required tests fail and blocked merges; a test read tool versions from a planning file that archiving would delete), confirmed by reproduction when fixed. PR #48's one finding is stated as a false positive; PR #55 as one test-coverage observation BM also made; PR #44 as not run. "The one time Codex could not finish" is narrowed to the one pilot pull request.

### WR-08: Guide overstates what the protected environment proves

**Files modified:** `docs/review-workflow-adoption.md`
**Commit:** `b6e1d84`
**Applied fix:** GitHub-enforced side: the named approver's account approved this run for this commit. Instruction-enforced side (item 7): that a person made the decision, since an agent relaying the owner's explicit approval submits it with the owner's credentials.

### IN-01: CodeQL setup description

**Files modified:** `docs/review-workflow-adoption.md`
**Commit:** `c916603`
**Applied fix:** Describes default setup, with no workflow file. Checked: no CodeQL workflow under `.github/workflows/` (only `ci.yml`, `release.yml`, `review-acceptance.yml`); live state `configured`.

### IN-02: Three dangling cross-references

**Files modified:** `docs/review-workflow-adoption.md`
**Commit:** `e940901`
**Applied fix:** Names `86-09-SUMMARY.md` and where it is; points the Greptile reference at the "Greptile's free-tier posture" bullet; "linked above" became "named above". The word "verbatim" was dropped by mistake in this commit and restored in `a3e8133`.

### IN-03: Evidence pointer is a phase-folder path

**Files modified:** `docs/review-workflow-adoption.md`
**Commit:** `a3e8133`
**Applied fix:** Adds that the path is inside the milestone's phase folder and may move under `.planning/milestones/` when the milestone is archived.

### IN-04: Triage categories differ from the instruction text

**Files modified:** `docs/review-workflow-adoption.md`
**Commit:** `54330cc`
**Applied fix:** Uses "nonblocking debt" in item 5 and the checklist, and maps it once to the pilot's "unproven" label.

## Verification

- Doc-guard subset (`uv run pytest tests/ -q -k "checkpoint or contract or doc or classification or review"`): 849 passed, 1 skipped, 2433 deselected. Run before the first commit and again on the final state.
- Full suite (`uv run pytest tests/ -q`): 3282 passed, 1 skipped. Run before the first commit and again on the final state.
- `uv run ruff check triggarr/ tests/`: All checks passed.
- No doc-guard test pinned any wording that was changed; no test was edited.
- Private-infrastructure search of every edited file: no match.

A fresh BM review and paired Codex pass on the new head were not run by this fixer.

## Left for a ruling

1. **`.planning/REQUIREMENTS.md` RISK-02 (line 58)** still reads "explicitly recommends an additional vibe-check ... and records the owner's decision". It now disagrees with the instruction text. Requirement wording was outside what the rulings allowed to change.
2. **Checkpoint template: "Owner's decision" field removed.** R1 says the high-risk vibe-check is no longer something the owner may decline, so the field quoting the owner's decision on a recommendation was replaced by the status field. RISK-02 as written still asks for a recorded owner decision (item 1). If the field should stay in some form, it needs to be put back.
3. **Pilot record, cross-PR summary, PR #36 row: "Codex 1 (fixed in PR #44)".** The scorecard says that defect was fixed at `2f2e8fc`, and `2f2e8fc` is an ancestor of PR #36's own final head, so it was fixed in PR #36. Not corrected: R6 limited edits to the two named contradictions.
4. **Pilot record wording that predates R1 and was left as history:** the "Standing items unaffected by PILOT-03 (D-16)" section and the recommendation's D-16 list still say "BM still recommends an extra vibe-check", and the decision lines still describe RISK-02 as a "high-risk recommendation". The recommendation's plain-terms paragraph also speaks of catching "a broken pin", where the scorecards say tests would have broken. `86-08-SUMMARY.md` and `86-09-SUMMARY.md` carry the same earlier wording.
5. **Blueprint status line** still reads "Proposed; implementation begins after Triggarr's current milestone." The dated note was added in the body; the status line was not touched.

---

_Fixed: 2026-11-14T06:02:13Z_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 1_
