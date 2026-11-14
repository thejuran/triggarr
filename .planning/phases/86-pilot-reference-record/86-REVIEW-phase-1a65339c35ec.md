---
phase: 86-pilot-reference-record
reviewed: 2026-11-14T06:09:12Z
head: 1a65339c35ec80b216a27afe0354df1cd5a395b1
diff_base: origin/main
depth: standard
iteration: 2
files_reviewed: 6
files_reviewed_list:
  - CLAUDE.md
  - docs/review-checkpoint-record.md
  - docs/review-classification-policy.md
  - docs/bm-greptile-codex-blueprint.md
  - docs/buildomator-greptile-pilot.md
  - docs/review-workflow-adoption.md
findings:
  critical: 0
  warning: 3
  info: 8
  total: 11
status: issues_found
---

# Phase 86: Code Review Report (iteration 2)

**Reviewed:** 2026-11-14T06:09:12Z
**Head:** `1a65339c35ec80b216a27afe0354df1cd5a395b1` (branch `phase-86-pilot-reference-record`, diff base `origin/main`)
**Depth:** standard (requested standard, ran standard)
**Iteration:** 2 (fresh full review after one batched fix round)
**Files Reviewed:** 6
**Status:** issues_found

## Summary

The PR changes no application code. Outside `.planning/` it adds `docs/review-workflow-adoption.md`, edits the vibe-check wording in `CLAUDE.md`, the checkpoint record, the classification policy, the blueprint and the Greptile pilot doc, and scrubs one home path in a `.gsd` UAT file. All six reviewed files were read in full, along with `docs/codex-adversarial-review-contract.md`, `docs/owner-cli-acceptance.md`, `86-PILOT-RECORD.md`, the iteration-1 report and the fix report (read-only).

The fix round did what it set out to do: the six files now state one rule. No blocker was found. Three things still need attention:

- The docs cite the pilot record as the source of "required at high risk", but the pilot record does not contain that ruling; it still says "recommendation" (WR-01).
- The new per-head `Vibe-check status` field cannot express two states that will occur, including the PR #36 case the decision was based on (WR-02).
- Vibe-check is now mandatory at high risk, but no instruction says who starts it, and `CLAUDE.md` still says its standing instruction authorizes only the Codex run (WR-03).

### Iteration-1 findings: all resolved at this head

| ID | Result | Where checked |
|---|---|---|
| CR-01 | Resolved. All six files say "required when risk is assessed high"; no "recommendation / owner's decision" wording is left in the edited passages. Residue: WR-01, IN-01. | `CLAUDE.md:53-55,93-101`; record `:56-64,126,179`; policy `:14,15,21`; pilot doc `:36,83`; guide `:21,87,111,140`; blueprint `:47` |
| WR-01 | Resolved. | pilot doc `:36,83`; policy `:15,21`; blueprint `:47` |
| WR-02 | Resolved. | record `:3` |
| WR-03 | Resolved: a per-head `Vibe-check status` field exists and the standing rule moved to "Rules". New gap: WR-02 below. | record `:64,126` |
| WR-04 | Resolved: fallback stated for any head, bot/fork as the standing case. | `CLAUDE.md:98-101`; record `:66,126`; guide `:87`; pilot doc `:83` |
| WR-05 | Resolved. Matches pilot doc `:29,69`. | guide `:31,61,63,136` |
| WR-06 | Resolved. Matches pilot record `:239,295,346`. | guide `:105` |
| WR-07 | Resolved, with one overstatement left (IN-04). | guide `:103` |
| WR-08 | Resolved. | guide `:51,55,89` |
| IN-01 | Resolved. | guide `:69` |
| IN-02 | Resolved. | guide `:31,91,109` |
| IN-03 | Resolved. | guide `:97` |
| IN-04 | Resolved (terms); see IN-08 for a remaining mismatch on the proof bar. | guide `:85,139` |
| IN-05 | Resolved. | guide `:97,107` |

### Checks that came back clean

- **Rule agreement (points 1-3):** every statement of the vibe-check rule in the six files agrees with the owner's rule. `docs/codex-adversarial-review-contract.md` (`:147-151,160`) and `docs/owner-cli-acceptance.md` (`:15`, "applicable vibe-check/UAT") are consistent with it and needed no change.
- **No other protection weakened:** Codex pairing (`CLAUDE.md:45-52`, record `:128`), classification (`CLAUDE.md:43-44`, policy ground rules), one record per head (record `:7-13`), exact-commit acceptance (`CLAUDE.md:109-117`, record `:193`) and Greptile's optional status (`CLAUDE.md:101-103`, pilot doc `:28,72`) are unchanged in meaning. The diff touches none of those sentences except the REVIEW-06 bullet (record `:125`), which is now more specific, not weaker.
- **FUT-03 (point 3):** stated correctly in record `:3,193`, blueprint `:47`, guide `:112`.
- **A per-head record of whether vibe-check ran exists:** record `:64`, mirrored in the checklist `:179`.
- **Pilot facts in the guide:** the five-PR description, the controlled comparison, the PR #36 account, the "other three" paragraph and both owner decisions match `86-PILOT-RECORD.md` (`:182-186,237-239,262-264,293-295,311-313,344-346,442-447`), except IN-04.
- **Live-config statements vs. other docs:** required checks, strict mode, environment protection, admin bypass off, SHA-pinning setting and CodeQL default setup in the guide agree with pilot doc `:28,29,69,71`. GitHub was not re-read live in this iteration; the comparison is against the repository's own docs and the fix report's recorded reads.
- **GitHub-enforced vs. instruction-enforced:** every item is on the correct side. The vibe-check rule is labelled instruction-enforced (record `:126`, guide item 6).
- **Broken references:** none. Every relative Markdown link in the six files resolves; every named `docs/`, `tests/`, `.github/scripts/`, `.claude/`, `docker/` and `.planning/` path exists; `86-PILOT-RECORD.md` and `86-09-SUMMARY.md` are tracked. Internal cross-references in the guide (`:21,55,91,111`) point at real headings or items.
- **Private infrastructure:** none in the six files or the scrubbed UAT file (searched for home paths, local username, NAS and tailnet names, private IP ranges, SSH targets).
- **Doc-guard tests:** the six doc-guard test files pass at this head (61 passed: `test_review_checkpoint_record.py`, `test_review_instructions.py`, `test_acceptance_docs.py`, `test_docs_accuracy.py`, `test_repository_hygiene.py`, `test_review_machinery_lists.py`). The full suite was not run by this review.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: The docs cite the pilot record for "required at high risk", and the pilot record does not say it

**File:** `docs/review-workflow-adoption.md:109-111`; `docs/bm-greptile-codex-blueprint.md:47`; `docs/buildomator-greptile-pilot.md:36`
**Issue:** Three passages name `86-PILOT-RECORD.md` as where the rule is recorded:

- guide `:109` — "The owner's decisions (2026-11-14, recorded verbatim in the pilot record named above)", followed at `:111` by "Vibe-check is required when a checkpoint's risk is assessed high".
- blueprint `:47` — "the owner decided; the record is `.planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md`. ... Vibe-check is required when a checkpoint's risk is assessed high".
- pilot doc `:36` — "(owner decision, PILOT-03, 2026-11-14, recorded in `...86-PILOT-RECORD.md`; ...)".

The record says something different. Its verbatim owner quote is "take all recommendations", and its decision line reads "the D-16 standing items (bot/fork fallback; RISK-02's high-risk recommendation) stay unchanged" (`86-PILOT-RECORD.md:628`; also `:48-52`, `:556-560`, "BM still recommends an extra vibe-check"). The clarification that the high-risk vibe-check is required and cannot be declined is not in the record at all. Its dated Corrections section (`:634-659`) covers only the two scorecard contradictions. The only places that ruling is written down are `86-REVIEW-FIX.md` ("Rulings applied", R1) and one sentence in `.planning/REQUIREMENTS.md:11`.

Effect: anyone who follows the pointer to check the rule finds "recommendation" in the cited source and "required" in the instructions, with nothing in the record explaining the difference. This is the same disagreement iteration 1 raised as CR-01, moved from between the instruction files to between the instructions and their cited evidence. The accepted "historical wording predates the corrections note" does not cover it, because the corrections note does not state the ruling.

**Fix:** Add a third dated entry to the pilot record's Corrections section that records the owner's clarification with its date and the owner's words, for example: "3. **Decision 1, clarified by the owner on 2026-11-14.** At high risk the vibe-check is required, one per head, not a recommendation the owner may decline. The wording above that calls it a recommendation predates this clarification." Then change guide `:109` from "recorded verbatim in the pilot record named above" to "recorded in the pilot record named above (decisions, plus its dated Corrections section)". No decision line, owner quotation or bar text needs to change.

### WR-02: The `Vibe-check status` field cannot express two states that will occur

**File:** `docs/review-checkpoint-record.md:64` (same three values at `:179`)
**Issue:** The field offers exactly three values: ran because risk is high; not run because risk is below high; ran as the owner-approved Codex fallback. Two reachable states have no value:

1. **Risk is high and vibe-check has not run yet (or could not finish).** The record is written per head and updated as evidence arrives (`:13`), and Codex has an explicit PENDING status for this situation (`:128`). Vibe-check has none. At a high-risk head an agent filling the template before vibe-check completes has no truthful option; the nearest ones are "ran" and "not run because risk is below high", both false. The acceptance checklist line (`:179`) has the same gap, so a required-but-missing vibe-check is not visibly incomplete there unless someone remembers to add it under "Incomplete items".
2. **Risk is high and Codex stayed INCOMPLETE on the same head.** This is PR #36, the case the owner's decision rests on (`86-PILOT-RECORD.md:264,531-533`). The values are written as alternatives, and nothing says whether one vibe-check serves as both the required high-risk review and the Codex fallback, or whether two are needed. `:66` says vibe-check "never reduces required coverage", which an agent could read as requiring two.

**Fix:** Extend the field and the checklist line, and add one sentence to the rule at `:126`:

```markdown
- **Vibe-check status:** <ran because risk is high: report location | REQUIRED, NOT YET RUN (risk is high): blocks acceptance | not run because risk is below high | ran as the owner-approved Codex fallback for this head: report location | ran because risk is high and also recorded as this head's owner-approved Codex fallback: report location>
```

Rule sentence: "When risk is high and Codex stays INCOMPLETE/PENDING on the same head, one vibe-check on that head serves both purposes if the owner approves it as the fallback; the record says so. A high-risk head whose vibe-check has not run is recorded as REQUIRED, NOT YET RUN, never as complete." Whether one pass may serve both is the owner's call; one pass is what happened on PR #36.

### WR-03: Vibe-check is now mandatory at high risk, but no instruction says who starts it

**File:** `CLAUDE.md:71-72,93-98`; `docs/review-checkpoint-record.md:126`; `docs/buildomator-greptile-pilot.md:56,83`
**Issue:** Before this PR the sentences named an actor: "the owner runs vibe-check" (old pilot doc `:36,83`). The replacements are passive: "Vibe-check is required when a checkpoint's risk is assessed high" (`CLAUDE.md:94-95`, record `:126`, pilot doc `:83`). What remains on the question points in different directions:

- `CLAUDE.md:71-72` — "This standing instruction authorizes only running the read-only Codex review". Read strictly, Claude is not authorized to start a vibe-check on its own.
- pilot doc `:56` — "Vibe-check is run by the owner."
- `CLAUDE.md:96-98` — the vibe-check is "not a recommendation the owner may decline", which reads as "do not ask, it just happens".
- blueprint `:103` ("does not automatically launch vibe-check") sits in a section the 2026-11-14 note supersedes, so it no longer answers the question either way.

Effect at the next high-risk checkpoint: the agent either launches a multi-agent review without being told it may, or waits for the owner to run something the owner believes is automatic, and the checkpoint stalls. The memory note in use says it runs locally right after BM review and the paired Codex pass, but that is not in the repository's instructions.

**Fix:** Add one sentence to `CLAUDE.md` after "...where its report is." (`:98`) and mirror it in record `:126`, naming the actor and the timing. If the intended behavior is that Claude runs it: "Claude runs it on the same frozen head after BM's review and the paired Codex pass, without asking first, and reports the result." Then widen `CLAUDE.md:71` to "authorizes only running the read-only Codex review and, at high risk, the required vibe-check". If the owner runs it instead, say that, and say Claude asks for it and records REQUIRED, NOT YET RUN until the report arrives. Which of the two is a decision for the owner; the instructions need to state one.

## Info

### IN-01: The blueprint's update note lists the superseded passages, and the list is incomplete

**File:** `docs/bm-greptile-codex-blueprint.md:47` (unlisted: `:121,122,174,191`)
**Issue:** The note names the diagram steps, the paragraph after the diagram, the "Risk-based review recommendation" section and the "Until then" sentence, then says "The rest of this document is left as written". Four other sentences describe the high-risk vibe-check as a recommendation with the owner's choice and are not in the list: `:121` ("must also suggest vibe-check ... record the owner's choice"), `:122`, `:174` and `:191` ("high-risk vibe-check recommendation(s)"). The note's general clause covers them in spirit; the explicit list reads as complete and leaves them out.
**Fix:** Add "and every later mention of a high-risk vibe-check recommendation or the owner's choice on it (Required implementation, Triggarr rollout step 5, the adoption checklist)" to the parenthetical.

### IN-02: The mixed-changes paragraph can be read as two vibe-checks on one PR

**File:** `docs/review-classification-policy.md:21`
**Issue:** "...the full code-review path from the code row (... and the required vibe-check when risk is assessed high), plus the sensitive-content risk assessment (RISK-01, with the required vibe-check when risk is assessed high per RISK-02) ... Neither class's requirements are dropped because the other is present." Before the fix these were two different things (routine vibe-check, and a recommendation). Now the same requirement is named twice and joined by "plus", which invites running one per class. The rule is one vibe-check per high-risk head.
**Fix:** Name it once: "...(BM code review with paired Codex, Greptile when it runs, and CI), plus the sensitive-content risk assessment (RISK-01) covering the sensitive changes specifically, and one required vibe-check for the head when its risk is assessed high (RISK-02)."

### IN-03: The guide's one-page sequence puts the risk note after the review it sets the depth for

**File:** `docs/review-workflow-adoption.md:20-21,27`
**Issue:** Step 4 is BM review plus Codex; step 5 is the risk note. The risk note's "Recommended review" field sets BM's depth (`docs/review-checkpoint-record.md:52`; blueprint target sequence step 2, `:34`), so it comes before BM's review. Line 27 says "Steps 4-8 repeat on a fresh commit"; classification (step 3) is also redone when the head changes (`docs/review-classification-policy.md:25`).
**Fix:** Swap steps 4 and 5 (risk note first, with the vibe-check sentence kept in it), and change line 27 to "Steps 3-8 repeat".

### IN-04: "blocks every merge" overstates the first PR #36 catch

**File:** `docs/review-workflow-adoption.md:103`
**Issue:** "a routine automated dependency update would have made required tests fail, which blocks every merge until someone fixes it". The pilot record says the update breaks "the pinned-SHA no-skip tests" (`86-PILOT-RECORD.md:272-274,512-518`), and the fix commit `b0e1ee4` says the literal SHAs "made every such update fail the required test job". That blocks those dependency-update PRs. Nothing in the record says other PRs would be blocked.
**Fix:** "...would have made required tests fail on every such update, so those updates could not merge until someone fixed the tests".

### IN-05: "every third-party action" is narrower than what the GitHub setting enforces

**File:** `docs/review-workflow-adoption.md:59,136`
**Issue:** The guide says to pin "every third-party action" and then to turn on the repository setting. The setting rejects any unpinned action, including GitHub's own: this repository's negative probe was rejected for `actions/checkout@v6` (`docs/buildomator-greptile-pilot.md:69`). An adopter who pins only what they consider third-party and then turns the setting on will find every workflow refusing to start.
**Fix:** Say "every action, including GitHub's own `actions/*`" in both places, and add "pin first, then turn the setting on" to the checklist item.

### IN-06: "the vibe-check line" is not a defined thing, and the rule sentence that uses it is hard to parse

**File:** `CLAUDE.md:96`; `docs/review-checkpoint-record.md:126`
**Issue:** "BM's risk note still states the vibe-check line (RISK-02)". The template's risk note (`:48-54`) has no vibe-check line; vibe-check has its own section (`:56-64`). In record `:126` the sentence "At high risk the risk note states the vibe-check line (RISK-02), that one vibe-check is required rather than a recommendation the owner may decline, and the template's `Vibe-check status` field records..." can be read as a list of three things the risk note states.
**Fix:** "At high risk the checkpoint record's Vibe-check (RISK-02) section states the rationale and scope of the required vibe-check. That vibe-check is required, not a recommendation the owner may decline. The `Vibe-check status` field records that it ran and where its report is." Use the same wording in `CLAUDE.md:96-98`.

### IN-07: The one-line fallback summary is narrower than the contract and than the same file's own checklist note

**File:** `docs/review-checkpoint-record.md:126` (also `CLAUDE.md:98-100`, `docs/buildomator-greptile-pilot.md:83`)
**Issue:** The rule defines the fallback as "on any head whose Codex pass stays INCOMPLETE/PENDING after its retry". The contract opens the fallback in two further cases for untrusted heads: an attempt-1 result stopped by the CI-independence rule, with no retry, and a historical `untrusted-refused` record (`docs/codex-adversarial-review-contract.md:151`). Record `:191` also says a head that changes `.github/` from a fork or non-owner author is satisfied only by the fallback even when Codex is COMPLETE. The summaries are permissive ("the owner may approve"), so nothing is forbidden, but record `:126` reads as the definition of when a below-high-risk vibe-check may run.
**Fix:** In record `:126`, replace the colon clause with "unless it runs as the owner-approved Codex fallback under `docs/codex-adversarial-review-contract.md` (most often a Codex pass that stays INCOMPLETE/PENDING after its retry; bot/fork PRs are the standing case)".

### IN-08: The guide presents the pilot's proof bar as a standing instruction

**File:** `docs/review-workflow-adoption.md:85` (section intro at `:75`)
**Issue:** Item 5 sits under "true only because a written instruction file ... tells the AI agent to do them" and says a finding "only counts as a confirmed, real defect once a failing test or a concrete reproduction demonstrates it". The instruction text says "Claude reproduces plausible defects and classifies each finding" (`docs/review-checkpoint-record.md:150`); the failing-test-or-reproduction bar is the pilot's measurement rule D-09 (`86-PILOT-RECORD.md:109-112`). The fix round aligned the category names but not this.
**Fix:** Either add the bar to the checkpoint record's Triage section, or reword item 5: "Claude tries to reproduce each plausible finding and records it as a confirmed defect, a false positive (with the evidence) or nonblocking debt. The pilot applied a stricter bar for its scorecards: confirmed only with a failing test or a reproduction."

## Convention (advisory, non-blocking)

The convention checker ran and returned six file-name-casing items, one per reviewed file ("should be camel"). The rule packs apply to JS/TS sources; these are Markdown files, `CLAUDE.md` is a fixed name, and every file in `docs/` is kebab-case. They are recorded as tool output only, are not counted in the totals, and no change is recommended.

## Set aside (needs ruling)

### SA-01: The CI reference-baseline plan still describes the high-risk vibe-check as a recommendation, with no dated note

**Where:** `docs/ci-reference-baseline-plan.md:31,55,57,59,96` (linked from `CLAUDE.md:105`)
**Why excluded:** The file is outside this review's six-file scope, and the owner's confirmation of consistency edits named the classification policy, the blueprint and the Greptile pilot doc only.
**Effect if left as is:** `CLAUDE.md:105-106` says this plan "is implemented across Phases 82 and 85". It says BM must "explicitly recommend vibe-check whenever risk is high, recording the owner's choice" (`:31,96`), speaks of vibe-check "when selected" (`:55,59`), and says "no ... mandatory vibe-check" (`:57`). It is the blueprint's companion and has the same stale wording the blueprint's 2026-11-14 note was added to cover. Its own header calls it a deferred proposal, which limits the harm.
**Needs:** Ruling from the owner: add the same dated note to this file in this PR / defer / accept.

### SA-02: Does the release-time `/deep-review` offer still stand below high risk?

**Where:** `CLAUDE.md:24-39` against `CLAUDE.md:94-96` and `docs/review-checkpoint-record.md:62`
**Why excluded:** The Deep Code Review Convention section was not edited by this PR, and `CLAUDE.md:38-39` says the offer is separate from per-checkpoint review. Whether it survives the decision is a product choice.
**Effect if left as is:** Before pushing to main or creating a release tag, Claude must say "I recommend running /deep-review". The pilot record treats `/deep-review` and the vibe-check deep review as the same kind of pass ("/deep-review offered; routine vibe-check deep review already on record for this head", `86-PILOT-RECORD.md:458,463`). So at a release from a below-high-risk head, one section tells Claude to recommend a deep review and the template says "no vibe-check required or recommended". The owner will keep being offered the heavier review at every release tag regardless of risk.
**Needs:** Ruling from the owner: keep the release-time offer as a separate standing rule (and say so in one sentence) / scope it to high risk / remove it.

---

_Reviewed: 2026-11-14T06:09:12Z_
_Head: 1a65339c35ec80b216a27afe0354df1cd5a395b1_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
_Iteration: 2_
