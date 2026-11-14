---
phase: 86-pilot-reference-record
reviewed: 2026-11-14T00:00:00Z
head: 48c96896caf5aebf43318d4ef2e440f8a0c44176
diff_base: origin/main
depth: standard
files_reviewed: 3
files_reviewed_list:
  - CLAUDE.md
  - docs/review-checkpoint-record.md
  - docs/review-workflow-adoption.md
findings:
  critical: 1
  warning: 8
  info: 5
  total: 14
status: issues_found
---

# Phase 86: Code Review Report

**Reviewed:** 2026-11-14 (time of day not recorded)
**Head:** `48c96896caf5aebf43318d4ef2e440f8a0c44176` (branch `phase-86-pilot-reference-record`, diff base `origin/main`)
**Depth:** standard (requested standard, ran standard)
**Files Reviewed:** 3
**Status:** issues_found

## Summary

The PR changes no application code. Outside `.planning/` it adds `docs/review-workflow-adoption.md`, rewrites the vibe-check sentences in `CLAUDE.md` (lines 93-98), replaces the "Routine vibe-check status" line in `docs/review-checkpoint-record.md` (line 65), and scrubs one home path in `.gsd/milestones/M001/slices/S03/S03-UAT.md`. Two of the three reviewed files are agent instructions, so a wrong or ambiguous sentence is treated as a defect.

Main concerns:

- The edited instructions do not say one thing about a high-risk checkpoint. `CLAUDE.md` says vibe-check is "required"; the checkpoint record, the rest of `CLAUDE.md`, the classification policy and the blueprint all still say it is recommended and the owner decides. The owner's recorded decision does not settle which was meant (CR-01).
- The decision was written into two files only. Four other instruction or policy passages still describe routine vibe-check as running, one of them unconditionally (WR-01, WR-02).
- The adoption guide states that GitHub has no setting for full-SHA action pinning. This repository has that setting turned on (confirmed live), and its own pilot doc says so (WR-05).
- Two pilot claims in the guide are not supported by the pilot record (WR-06, WR-07).

Checks that came back clean:

- **Broken links (check 4):** none. Every relative link in `CLAUDE.md` and `docs/review-checkpoint-record.md` resolves, and every `docs/`, `tests/` and `.github/scripts/` path they name exists. The adoption guide contains no Markdown links; the two paths it names exist. (Three dangling prose cross-references are in IN-02.)
- **Private infrastructure (check 5):** none found in the three reviewed files or in the scrubbed UAT file (searched for home paths, the local username, NAS and tailnet names, private IP ranges, SSH targets). The scrub to `~/triggarr` is correct. `thejuran` and SeedSyncarr are already public in `README.md`.
- **Consumers of the template (part of check 2):** no test or workflow parses the edited line. The six doc-guard test files that read these docs pass at this head (61 passed: `test_review_checkpoint_record.py`, `test_review_instructions.py`, `test_acceptance_docs.py`, `test_docs_accuracy.py`, `test_repository_hygiene.py`, `test_review_machinery_lists.py`). The full test suite was not run.
- **Decision 2 (FUT-03 not chosen):** stated correctly in the guide (line 112) and in the checkpoint record's line 193; the one stale line is WR-02.

Live GitHub settings read for check 3 (read-only): Actions permissions (`sha_pinning_required: true`), the `review-acceptance` environment's protection rules (`prevent_self_review: false`, one required reviewer), and code-scanning default setup (`configured`). The ruleset itself was not re-read; its contents are taken from `86-09-SUMMARY.md` and `docs/buildomator-greptile-pilot.md:28`, which agree with the guide.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: The instructions give two answers on whether vibe-check at high risk is required or only recommended

**File:** `CLAUDE.md:94-98` (also `docs/review-checkpoint-record.md:65`, `docs/review-workflow-adoption.md:21,87,111,140`)
**Issue:** The new `CLAUDE.md` sentence says "vibe-check is now required only at a high-risk checkpoint (RISK-02)". Every other statement of the same rule, edited or not, says it is a recommendation the owner then decides on:

- `CLAUDE.md:54-55` — "an explicit vibe-check recommendation with the owner's recorded decision whenever risk is high".
- `CLAUDE.md:97-98` (same paragraph as the new sentence) — "BM still recommends an extra vibe-check whenever a checkpoint's risk comes out high".
- `docs/review-checkpoint-record.md:58-60` — the template still has "Recommendation" and "Owner's decision" fields; line 65 (new) says vibe-check "runs only when recommended above"; line 179 still offers "not selected for this checkpoint".
- `docs/review-classification-policy.md:14` — "a vibe-check recommendation when risk is high (RISK-02)".
- `docs/bm-greptile-codex-blueprint.md:62,79` — "Owner selected vibe-check?" and "vibe-check runs when the owner selects it".
- `.planning/REQUIREMENTS.md:58` — RISK-02 is "recommends ... and records the owner's decision".
- The guide itself uses three wordings: "recommends ... and records what the owner decided" (21), "only recommended, and then required" (87), "a recommended extra step" (111, 140).

The owner's recorded decision (`86-PILOT-RECORD.md:620`) is "keep vibe-check, but scoped to high-risk checkpoints only", described at lines 529-530 and 548-552 as "the same trigger RISK-02 already uses". That supports "recommended, owner decides" at least as well as "required"; it does not say the owner can no longer decline.

Effect: at a high-risk checkpoint where the owner answers "no" to the recommendation, an agent following `CLAUDE.md:94-95` should treat the head as not ready for acceptance, while an agent following the template and checklist should record "not selected" and proceed. `docs/owner-cli-acceptance.md:15` makes "applicable vibe-check" an acceptance prerequisite, so the two readings give different acceptance outcomes.

A second ambiguity in the same sentence pair: with routine vibe-check gone, "an extra vibe-check" (`CLAUDE.md:98`, record line 65) no longer has anything to be extra to. Read next to "required", it can be taken as two vibe-checks at high risk. The pilot record (548-552) says it is the same single trigger, but that clarification did not make it into the instruction text.

**Fix:** This needs the owner's ruling first (it is a product decision, see SA-01): either (A) mandatory at high risk, or (B) recommended at high risk with the owner deciding each time. Then use one wording everywhere. For (B), which is what the unedited text and RISK-02 already say:

```markdown
Routine vibe-check on every "code"-class PR ended by owner decision in Phase 86
(PILOT-03, 2026-11-14). Vibe-check now runs in two cases only: when BM recommends it
at a high-risk checkpoint and the owner selects it (RISK-02), and as the owner-approved
fallback when Codex stays INCOMPLETE/PENDING after its retry.
```

For (A), `CLAUDE.md:54-55`, the template's "Owner's decision" field (line 60), the checklist's "not selected for this checkpoint" (line 179), policy line 14 and the guide's lines 21, 111 and 140 all have to change to say the owner cannot decline. In both cases drop the word "extra".

## Warnings

### WR-01: Unedited instruction and policy text still says routine vibe-check runs

**File:** `docs/buildomator-greptile-pilot.md:36,83`; `docs/review-classification-policy.md:15,21`; `docs/bm-greptile-codex-blueprint.md:4,11,45`
**Issue:** The decision was written into `CLAUDE.md` and the checkpoint record only. These passages now disagree with them:

- `docs/buildomator-greptile-pilot.md:36` — "For application-code pilot checkpoints, the owner runs vibe-check in parallel on the same SHA." Line 83 (routine workflow step 2) — "For application-code pilot work, the owner runs vibe-check independently on the same SHA". Both are unconditional, and `CLAUDE.md:68-69` sends the agent to this file "for the full protections". This is a direct contradiction.
- `docs/review-classification-policy.md:15` — the code row's required review is "The current full process: ... and routine vibe-check while the owner keeps it (standing rule until PILOT-03)". Line 21 repeats "routine vibe-check while the owner still requires it". The wording is conditional, but `CLAUDE.md:43` makes this policy the source for what review a PR gets, and it still lists routine vibe-check as part of the current process without saying the condition has ended.
- `docs/bm-greptile-codex-blueprint.md:45` — "Until then, every checkpoint keeps the current Greptile + manual vibe-check process." The condition (owner agrees to retire routine vibe-check) is now met, but the document does not say so, and its status line (4) still reads "Proposed".

The disagreement fails toward more review rather than less, which is why this is not graded higher, but an agent reading the policy or the pilot doc will still expect a vibe-check on every code PR and may report its absence as incomplete evidence.

**Fix:** In this PR, update the two pilot-doc sentences and the two policy sentences to the wording chosen under CR-01 (for example, policy line 15: "BM code review with paired Codex, Greptile when it runs, CI, plus RISK-01/RISK-02; routine vibe-check ended 2026-11-14 (PILOT-03)"). Add a dated note to the blueprint's line 45 that the owner made this decision on 2026-11-14. These are sensitive files under the policy, which this PR already is.

### WR-02: Checkpoint record still says the FUT-03 decision is pending

**File:** `docs/review-checkpoint-record.md:3`
**Issue:** "Owner-checked; GitHub does not enforce BM/Codex records (PILOT-03/FUT-03 decide later)." PILOT-03 decided this on 2026-11-14: the manual owner check stays and FUT-03 was not chosen (`86-PILOT-RECORD.md:622`, `.planning/REQUIREMENTS.md:79`). Line 65 of the same file cites the PILOT-03 decision as made, so the file now says both "decided" and "decide later".
**Fix:** Replace the parenthetical with "(owner decision, PILOT-03, 2026-11-14: stays a manual owner check; the FUT-03 gate extension was not chosen)".

### WR-03: The template lost its only per-head vibe-check status field

**File:** `docs/review-checkpoint-record.md:65`
**Issue:** The replaced line was a placeholder filled in per checkpoint ("whether routine vibe-check ran for this code change"). It is now fixed policy prose inside the fenced template, so:

1. Nothing in the template records whether vibe-check actually ran on this head, or where its report is. When risk is high the template captures the recommendation and the owner's decision (59-60) but not the outcome. The acceptance checklist expects a "Vibe-check: <status ...>" (179) and the rules require a new head to get "its own ... vibe-check" when applicable (126), yet the per-head record has no field to carry that. The Codex "Fallback" row (86) covers only the fallback case.
2. The same standing-policy sentence is copied verbatim into every PR comment, where it is not evidence about that head.

No test or script reads this line, so nothing breaks mechanically.
**Fix:** Move the policy sentence out of the fenced template into the "Rules" section, and put a fillable field in its place:

```markdown
- **Vibe-check on this head:** not run (risk below high) | not run (owner declined) | ran — <report location, result> | ran as Codex fallback — see Fallback row
```

### WR-04: New wording narrows the Codex fallback to bot/fork PRs and contradicts the next paragraph

**File:** `docs/review-checkpoint-record.md:65` and `CLAUDE.md:94-97` (also `docs/review-workflow-adoption.md:87`)
**Issue:** Both edited passages say vibe-check now runs or is required "only" at a high-risk checkpoint, and then name the fallback as a bot/fork carve-out. The contract's fallback is not limited to bot/fork heads: `docs/codex-adversarial-review-contract.md:151` begins "For a trusted head, this fallback applies only when the Codex pass stays INCOMPLETE/PENDING after its one automatic retry", and `docs/review-checkpoint-record.md:67`, two lines below the edit, says the owner may approve vibe-check as the fallback "for that exact head" without restriction. Read literally, the new text removes the vibe-check fallback for an owner-authored PR that is not high-risk and whose Codex pass cannot finish.

That is the case the pilot's decision rested on: PR #36 was an owner PR, not a bot or fork PR, and its vibe-check ran as the Codex fallback (`86-PILOT-RECORD.md:264,506-510`). The guide has the same mismatch at line 87: rule (a) is stated for "a bot or fork pull request", but its "what breaks if skipped" example (a PR too large for one pass) is PR #36.
**Fix:** State the fallback for any head, and keep the bot/fork sentence as the D-16 standing item: "...and, for any head, as the owner-approved fallback when Codex stays INCOMPLETE/PENDING after its retry (bot/fork PRs included, D-16)." Remove "only" or scope it to the high-risk trigger.

### WR-05: Guide says GitHub has no setting for full-SHA action pinning; this repository uses that setting

**File:** `docs/review-workflow-adoption.md:61` (also lines 31, 136)
**Issue:** Under "GitHub-enforced requirements", the pinning item says "there is no GitHub setting for this; it's a convention enforced by whoever reviews workflow-file changes". That is false for this repository and contradicts the section it sits in:

- Live: `gh api repos/thejuran/triggarr/actions/permissions` returns `"sha_pinning_required": true`.
- `docs/buildomator-greptile-pilot.md:69` — "GitHub now requires full-SHA action pins at repository level", with a negative probe that was rejected at job setup (also line 29).

Line 31 claims every item in the section "was re-checked against this repository's live GitHub configuration". The commands listed in `86-09-SUMMARY.md` did not include the Actions permissions; pinning was checked only by grepping workflow files. So the claim at line 31 is overstated for this item, and a reader adopting the guide is told to rely on reviewers for something GitHub can enforce. The checklist item at line 136 likewise omits turning the setting on. (Note: GitHub blocks the workflow run, not the merge directly, so line 31's "GitHub itself blocks a merge" is loose for this item.)
**Fix:** Rewrite "How to set it up" to: "turn on 'Require actions to be pinned to a full-length commit SHA' in the repository's Actions settings; GitHub then refuses to run a workflow that uses an unpinned action. A test that fails on an unpinned `uses:` line is a useful second check." Add the setting to the checklist item at line 136.

### WR-06: "The other three pull requests" claim does not match the pilot record

**File:** `docs/review-workflow-adoption.md:105`
**Issue:** "On the other three pull requests (the small fix and the user-interface change), vibe-check found nothing beyond test-coverage observations that BM or Codex also noted." Three problems:

1. It says three and names two.
2. Vibe-check did not run on the small fix (PR #44): `86-PILOT-RECORD.md:295` — "not run — risk assessed moderate, not high"; line 378 lists only BM and Codex as the reviewers that ran.
3. The third PR (#48) is not described. Its vibe-check ran once, on the final head only, and its one reported finding was a false positive (`86-PILOT-RECORD.md:239,242-245,376`), which is not a "test-coverage observation".

**Fix:** "On the security-sensitive change, vibe-check ran once, on the final commit, and its one reported finding was a false positive. On the user-interface change it found nothing beyond a test-coverage observation. It did not run on the small fix, which was assessed as moderate risk."

### WR-07: The first of the two PR #36 catches is mischaracterized

**File:** `docs/review-workflow-adoption.md:103`
**Issue:** The guide describes it as "an automated dependency-update process that would have quietly broken a security-relevant pin". The record says the opposite direction: Dependabot's update would rewrite the pinned SHAs and thereby break the tests that assert on them (`86-PILOT-RECORD.md:272-274`, "breaking the pinned-SHA no-skip tests"; 511-515, fixed by "anchoring the test on a stable prefix"). A failing test is not quiet, and the pin itself was not what broke. The second catch is described as "a configuration file that an unrelated cleanup would have deleted"; the record says a phase planning file holding tool pins that milestone archiving would delete (274-276, 516-520), which is close enough but less precise than it could be.
**Fix:** "a routine automated dependency update that would have broken the tests guarding the pinned action versions, and a test that read tool versions from a planning file that milestone archiving would later have deleted".

### WR-08: Guide overstates what the protected environment proves about a human approving

**File:** `docs/review-workflow-adoption.md:51`
**Issue:** "In effect, this makes 'did a specific real person explicitly click approve on this exact commit' a GitHub-enforced fact, not just a social expectation." GitHub enforces that the named account approved the deployment. In this repository the agent may submit that approval with the owner's credentials (`CLAUDE.md:108-114`, `docs/owner-cli-acceptance.md`), so whether a person actually decided is instruction-enforced, which the guide itself lists as item 7 on the instruction side (line 89). Line 55 partly corrects this ("from that person's account") but does not say that an agent holding the account's credentials can submit it.
**Fix:** Change line 51 to "makes 'the named approver's account approved this workflow run for this commit' a GitHub-enforced fact", and add to line 55: "If an AI agent can act with the approver's credentials, GitHub cannot tell the agent's submission from the person's; that part is instruction-enforced (item 7 below)."

## Info

### IN-01: CodeQL setup description does not match how this repository runs it

**File:** `docs/review-workflow-adoption.md:69`
**Issue:** "GitHub adds a workflow that runs it". This repository uses CodeQL default setup (live state `configured`; no CodeQL workflow file exists under `.github/workflows/`). Default setup adds no workflow file; only advanced setup does.
**Fix:** "choose default setup; GitHub runs the scan itself, with no workflow file to maintain, and reports a 'CodeQL' check".

### IN-02: Three dangling cross-references in the guide

**File:** `docs/review-workflow-adoption.md:31,91,109`
**Issue:** Line 31 — "commands listed in this plan's summary": the guide is a standalone public doc and does not say which plan (it is `86-09-SUMMARY.md`). Line 91 — "see 'Greptile' below": no heading by that name; the text is the "Greptile's free-tier posture" bullet. Line 109 — "the pilot record linked above": it is named as a path at line 97, not linked.
**Fix:** Name the summary file at line 31; point line 91 at "What not to copy blindly"; make line 97 a real relative link or change line 109 to "named above".

### IN-03: The guide's evidence pointer is a phase-folder path that milestone archiving moves

**File:** `docs/review-workflow-adoption.md:97`
**Issue:** `.planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md` exists now, but earlier milestones' phase folders live under `.planning/milestones/vX-phases/`, so this path stops resolving when v2.13 is archived. This is the same class of trap the pilot itself recorded for PR #36 (a tracked file depending on a phase planning path). No test reads the path.
**Fix:** Add "(moved under `.planning/milestones/` once v2.13 is archived)", or copy the short result tables the guide relies on into the guide.

### IN-04: Triage categories in the guide differ from the repository's own instruction text

**File:** `docs/review-workflow-adoption.md:85,139`
**Issue:** The guide presents "confirmed only with a failing test or reproduction; otherwise false positive or 'unproven'" as a rule the instruction files impose (line 75). The instruction files use confirmed defect / false positive / nonblocking debt (`docs/review-checkpoint-record.md:115,150`) and say "Claude reproduces plausible defects". "Unproven" is the pilot's own measurement label (D-09), not a standing instruction.
**Fix:** Either use the repository's three categories, or say the "unproven" label was the pilot's measurement rule.

### IN-05: Two loose pilot statements

**File:** `docs/review-workflow-adoption.md:97,107`
**Issue:** Line 97 says five PRs were run "through the exact process above". Three of the five were already merged and were scored afterwards from committed evidence (`86-PILOT-RECORD.md:15-17,221-224`), vibe-check did not run on one of them, and Greptile ran on none. Line 107 says "The one time Codex genuinely could not finish"; the record's claim is narrower (1 of 5 pilot PRs at acceptance time, line 584), and the guide's own line 121 mentions another incomplete Codex review outside the pilot set.
**Fix:** Line 97: "This repository scored five real pull requests against this process: three already merged, from their recorded evidence, and two run fresh." Line 107: "On the one pilot pull request where Codex could not finish".

## Convention (advisory, non-blocking)

The convention checker ran and returned three file-name-casing items (`CLAUDE.md`, `docs/review-checkpoint-record.md`, `docs/review-workflow-adoption.md` "should be camel"). The rule packs apply to JS/TS sources; these are Markdown files, `CLAUDE.md` is a fixed name, and every file in `docs/` is kebab-case. They are recorded here as tool output only, are not counted in the totals, and no change is recommended.

## Set aside (needs ruling)

### SA-01: Was decision 1 "mandatory at high risk" or "recommended at high risk, owner decides"?

**Where:** `86-PILOT-RECORD.md:529-552,620`; drives CR-01 (`CLAUDE.md:94-95`)
**Why excluded:** This is the owner's decision to state, not something a review can infer. The record's wording fits both readings.
**Effect if left as is:** At a high-risk checkpoint where the owner declines the vibe-check, one instruction says the head cannot be accepted and the others say it can.
**Needs:** Ruling from the owner: (A) mandatory at high risk, or (B) recommended at high risk with the owner's recorded decision. CR-01's fix follows from the answer.

### SA-02: The pilot record contradicts itself on two points the guide relies on

**Where:** `.planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md:264` vs `506-520`; `295,378` vs `503-505`
**Why excluded:** `.planning/` is outside this review's file scope.
**Effect if left as is:** (1) PR #36's vibe-check scorecard row reads "0 confirmed via reproduction" with all 25 findings as nonblocking debt, while the decision section calls two of them "confirmed consequential defects"; the guide's "two real problems" (line 103) rests on the second, and the decision to keep vibe-check at high risk rests on it too. (2) The decision section says vibe-check "found nothing beyond unproven test-gap notes" on PR #44, while the scorecard says it did not run there; WR-06 traces to this.
**Needs:** Ruling on whether to correct the record in this PR (in scope / defer / accept).

### SA-03: Planning text that still describes routine vibe-check as in force

**Where:** `.planning/REQUIREMENTS.md:11`
**Why excluded:** Planning file, outside scope; the wording is conditional on PILOT-03.
**Effect if left as is:** A reader of REQUIREMENTS sees the pre-decision process described as current.
**Needs:** In scope / defer / accept.

---

_Reviewed: 2026-11-14_
_Head: 48c96896caf5aebf43318d4ef2e440f8a0c44176_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_

## Head note (orchestrator, 2026-11-14)

This review ran at `48c96896caf5aebf43318d4ef2e440f8a0c44176`, a merge of `origin/main` into the phase branch. That merge was then redone as `500f6218ec4eb093e0b2f991962f3ec920adaed4` so git records it as a local commit operation (the paired Codex trust check requires that). `git diff 48c9689 500f621` is empty: the two commits have identical content, so every finding and line number above applies unchanged to `500f621`.
