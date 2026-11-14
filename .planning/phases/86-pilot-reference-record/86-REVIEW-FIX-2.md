---
phase: 86-pilot-reference-record
fixed_at: 2026-11-14T15:47:39Z
review_path: .planning/phases/86-pilot-reference-record/86-REVIEW-phase-1a65339c35ec.md
codex_report_path: .planning/phases/86-pilot-reference-record/codex/1a65339c35ec-phase-a1.last.json
iteration: 2
findings_in_scope: 15
fixed: 14
skipped: 1
rejected: 0
status: partial
---

# Phase 86: Code Review Fix Report (iteration 2)

**Fixed at:** 2026-11-14T15:47:39Z
**Source review:** `.planning/phases/86-pilot-reference-record/86-REVIEW-phase-1a65339c35ec.md` (BM iteration 2, head `1a65339c35ec`)
**Codex report:** `.planning/phases/86-pilot-reference-record/codex/1a65339c35ec-phase-a1.last.json` (read only; nothing under `codex/` was edited)
**Iteration:** 2 (the last planned round)
**Base:** `139200e` on `phase-86-pilot-reference-record`; commits made directly on that branch (no worktree, no temp branch).

**Summary:**
- Findings in scope: 15 (BM: 3 warning, 8 info, 2 set-aside items with rulings; Codex: 1 medium, 1 low)
- Fixed: 14
- Skipped: 1 (SA-02: no change, by ruling)
- Rejected: 0

No application code, test or `.github/` file was changed. `docs/codex-adversarial-review-contract.md` and `docs/owner-cli-acceptance.md` were not changed. Six items are left for a ruling; the first one matters most (the publication gate does not pass on this branch, for a reason that predates this round).

## Owner decisions applied (2026-11-14, after iteration 2)

- **D-A:** the owner selected the offered option "Claude runs it": Claude starts the required high-risk vibe-check automatically, right after the BM review and the paired Codex pass, on the same exact commit, without asking each time; the owner decides what to do with its findings.
- **D-B:** the owner selected the offered option "One more round, then stop".
- **D-C:** owner message, word for word: "keep the extra doc edits in this PR".
- **D-D:** "required at high risk, not a recommendation the owner may decline" comes from the recommendation as presented before the owner's reply "take all recommendations".

D-A and D-B are selections from offered options, not the owner's free text, and are recorded that way.

## Fixed Issues

### WR-01: The docs cite the pilot record for "required at high risk", and the pilot record does not say it

**Files modified:** `.planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md`, `docs/review-workflow-adoption.md`, `docs/bm-greptile-codex-blueprint.md`, `docs/buildomator-greptile-pilot.md`
**Commit:** `cef7222`
**Applied fix:**
- Pilot record: the dated Corrections section gains a subsection "Added 2026-11-14, after code review iteration 2" with entries 3 to 6 (D-D, D-A, D-B, D-C). The owner decisions log gains three phase-level rows (D-A, D-B, D-C) in the existing "phase-level; not attributable to PR #54 or #55" format.
- Guide: "recorded verbatim in the pilot record" became "recorded in the pilot record named above: its PILOT-03 decision lines and owner decisions log, plus its dated Corrections section". One more sentence in the guide said "the owner's verbatim decisions"; it now says "recorded decisions".
- Blueprint note and Greptile pilot doc: the pointer now names the decision lines plus the Corrections section.
- **Hard constraints, checked:**
  - The `## Retirement bar (D-15, fixed before results)` section is byte-identical to commit `bbabaf8`: 594 bytes each, same SHA-256 `d3ae6696da05f7cb2eeaba56f6ee00f1a0783caf17fc4f2c31460dbad541ada5`, `cmp` clean.
  - The diff of the pilot record against `139200e` is 49 added lines and 0 removed lines, so the three `Owner decision (PILOT-03 decision N)` lines and every existing log row are unchanged.
  - No PR scorecard changed. The scorecards count owner effort as "this PR's rows" in the log; the three new rows are phase-level and belong to no PR.

### WR-03 / IN-06: Who starts the required vibe-check; the undefined "vibe-check line"

Committed together because they edit the same sentences.

**Files modified:** `CLAUDE.md`, `docs/review-checkpoint-record.md`, `docs/buildomator-greptile-pilot.md`, `docs/review-workflow-adoption.md`
**Commit:** `465765a`
**Status:** fixed: requires human verification (instruction semantics; no test checks them)
**Applied fix:**
- `CLAUDE.md`, "Review-workflow rollout (v2.13)" paragraph: now says Claude starts the required vibe-check automatically, right after the BM review and the paired Codex pass, on the same exact commit, without asking first, and records it per head; the owner decides what to do with its findings; it never substitutes for Codex, never waives a finding and never reduces coverage. The fallback is stated as "a different thing": vibe-check counts as the Codex fallback only with the owner's explicit approval for that head.
- `CLAUDE.md`, standing-authorization sentence: now "authorizes only running the read-only Codex review and, at a high-risk checkpoint, the required vibe-check; it approves no PR and waives no review."
- No other sentence in `CLAUDE.md` was touched.
- Checkpoint record, "Rules": the same statement, in the same words.
- Greptile pilot doc: "Vibe-check is run by the owner" now says the owner ran it in the two pilot rounds listed there and that Claude starts the required one since 2026-11-14; routine-workflow step 2 carries the same statement and the fallback distinction.
- Guide, instruction-enforced item 6: the same statement and the fallback distinction, in the guide's plain wording.
- IN-06: "BM's risk note still states the vibe-check line" is replaced in `CLAUDE.md` and in the record's rule by "the checkpoint record's Vibe-check (RISK-02) section states the rationale and scope of the required vibe-check", split into separate sentences so it no longer reads as a three-item list.

### WR-02: The `Vibe-check status` field cannot express two states that will occur

**Files modified:** `docs/review-checkpoint-record.md`
**Commit:** `16d5b82`
**Status:** fixed: requires human verification (instruction semantics)
**Applied fix:** The template field and its acceptance-checklist mirror now have four cases: not run because risk is below high; REQUIRED, NOT YET RUN (PENDING) because risk is high, which blocks acceptance; ran because risk is high, with report location; ran as the owner-approved Codex fallback for this head, with report location. A sentence under the field, the checklist line and the rule all say that when risk is high and Codex stayed incomplete on the same head, one vibe-check run on that exact head serves both purposes, the record states both, and the fallback half still needs the owner's explicit approval. The rule also says a high-risk head whose vibe-check has not run is never recorded as complete and blocks acceptance the same way a pending Codex pass does.

### IN-07: The one-line fallback summary is narrower than the contract

**Files modified:** `docs/review-checkpoint-record.md`
**Commit:** `6c8f412`
**Applied fix:** The rule now says "unless it runs as the owner-approved Codex fallback under `docs/codex-adversarial-review-contract.md` (most often a Codex pass that stays INCOMPLETE/PENDING after its retry; bot/fork PRs are the standing case)". The contract's "Owner-approved fallback" section was read to confirm it has the further cases the review named. `CLAUDE.md` and the pilot doc keep their permissive summaries, as the review's fix asked for the record only.

### IN-01: The blueprint's update note lists the superseded passages, and the list is incomplete

**Files modified:** `docs/bm-greptile-codex-blueprint.md`
**Commit:** `1c95866`
**Applied fix:** The parenthetical now also names every later mention of a high-risk vibe-check recommendation or the owner's choice on it: "Required implementation in the next CI milestone", Triggarr rollout step 5 and the adoption checklist.

### IN-02: The mixed-changes paragraph can be read as two vibe-checks on one PR

**Files modified:** `docs/review-classification-policy.md`
**Commit:** `16924c2`
**Applied fix:** The required vibe-check is named once: "...and one required vibe-check for the head when its risk is assessed high (RISK-02)."

### IN-03: The guide's one-page sequence puts the risk note after the review it sets the depth for

**Files modified:** `docs/review-workflow-adoption.md`
**Commit:** `0a2cd9a`
**Applied fix:** Steps 4 and 5 are swapped (risk note first, vibe-check sentence kept in it, with a clause that the vibe-check itself runs right after the review in step 5). "Steps 4-8 repeat" became "Steps 3-8 repeat". No other step number is referenced anywhere in the guide.

### IN-04: "blocks every merge" overstates the first PR #36 catch

**Files modified:** `docs/review-workflow-adoption.md`
**Commit:** `8fbfb04`
**Applied fix:** Now "would have made required tests fail on every such update, so those updates could not merge until someone fixed the tests". Checked against the message of `b0e1ee4` ("the literal SHAs made every such update fail the required test job").

### IN-05: "every third-party action" is narrower than what the GitHub setting enforces

**Files modified:** `docs/review-workflow-adoption.md`
**Commit:** `92db3fe`
**Applied fix:** The section and the checklist item now say every action, including GitHub's own `actions/*`, and say to pin first and turn the setting on afterwards. Checked: every `uses:` line in the three workflow files, GitHub's own actions included, is pinned to a 40-character SHA, so "this repository pins every action, GitHub's own included" is true.

### IN-08: The guide presents the pilot's proof bar as a standing instruction

**Files modified:** `docs/review-workflow-adoption.md`
**Commit:** `e6eec8e`
**Applied fix:** Item 5 now states what the instruction text says (Claude tries to reproduce each plausible finding and records it as a confirmed defect, a false positive or nonblocking debt) and labels the failing-test-or-reproduction bar as the pilot's measurement rule for its scorecards.

### SA-01: The CI reference-baseline plan still describes the high-risk vibe-check as a recommendation

**Files modified:** `docs/ci-reference-baseline-plan.md`
**Commit:** `a5e6880`
**Applied fix:** One dated note under the status line says the plan's vibe-check wording was superseded by the owner's 2026-11-14 PILOT-03 decision (required at high risk; Claude runs it) and points to `CLAUDE.md` and the pilot record. The plan's body is unchanged.

### Codex F001 (medium): Scan staged content before authorizing publication

**Files modified:** `.planning/phases/86-pilot-reference-record/86-publication-gate.sh`, `.planning/phases/86-pilot-reference-record/86-publication-gate-selftest.sh`
**Commit:** `d61cf2a`
**Outcome of reproduction:** confirmed by reproduction.

Reproduction, in a disposable git repository in a scratch directory outside this repository (nothing sensitive was staged here):

1. Four fixture files staged, one of them a vibe-check report containing a fake Unix home-directory path.
2. Control run of the gate: BLOCKED, "public-infrastructure check: matching files listed above", exit 1.
3. Working copy of that one file overwritten with a redacted line, not staged. `git status --short` showed `AM` for it, and `git show` of the staged copy still printed the fake path.
4. Gate run: `publication gate: PASS (4 tracked artifacts)`, exit 0. An ordinary commit at that point would have published the fake path.

**Applied fix:** After its existing checks, the gate now runs `git diff --name-only --exit-code` over the covered paths and blocks when the index and the working tree differ ("index and working tree differ for the files listed above: stage the scanned content, then re-run"); any other git error also blocks. This is the smaller of the two fixes Codex suggested: every existing check keeps reading the working tree, and the new check guarantees that what was scanned is what is staged. The hand-review record `86-REVIEW-EVIDENCE.md` is one of the covered paths, so it is included.

**Self-test, case added first.** Against the unfixed gate:

```
FAIL staged match with a redacted working copy blocks (wanted block 'index and working tree differ', exit 0: )
ok   passes once the redacted copy is staged
selftest: 24 passed, 1 failed
```

After the fix:

```
ok   file name with a space blocks
ok   staged match with a redacted working copy blocks
ok   passes once the redacted copy is staged
selftest: 25 passed, 0 failed
```

The scratch reproduction, re-run against the fixed gate, is BLOCKED with the new reason, exit 1. One existing self-test case ("accepted entry for the exact path passes") edited its fixture after staging; it now stages the edit before running the gate, which is what the new rule requires. The other 22 existing cases are unchanged.

### Codex F002 (low): Preserve the redaction operation when anonymizing the plan

**Files modified:** `.planning/phases/84-codex-plan-checker-investigation/84-02-PLAN.md`
**Commit:** `a1080e0`
**Applied fix:** One phrase: "a redaction that replaces ~ with ~" became "a redaction that replaces the expanded home directory (the value of `str(Path.home())`) with the literal `~`". No personal path was reintroduced and nothing else in that already-executed plan changed (1 line, per `git diff --stat`). Codex also suggested adding a redaction assertion to the plan's self-test list; that was not done, because the ruling limited the change to this one phrase.

## Skipped Issues

### SA-02: Does the release-time `/deep-review` offer still stand below high risk?

**File:** `CLAUDE.md:24-39`
**Reason:** No change, by ruling: the `/deep-review` offer before pushing to main or creating a release tag stays exactly as it is, as a separate standing rule. The edited sentences were checked for whether any could be read as cancelling it. They speak only of the vibe-check required at a high-risk checkpoint and of the Codex fallback, and `CLAUDE.md` already says the offer "is separate from per-checkpoint review". No clause was added and the Deep Code Review Convention section was not touched.
**Original issue:** At a release from a below-high-risk head, one section tells Claude to recommend a deep review and the template says "no vibe-check required or recommended".

## Verification

- Full suite (`uv run pytest tests/ -q`), on the final state: `3282 passed, 1 skipped, 38 warnings in 87.99s`.
- `uv run ruff check triggarr/ tests/`: `All checks passed!`
- The six doc-guard test files, run after the instruction edits: 61 passed. No doc-guard test pinned any changed wording; no test was edited.
- Gate self-test: 25 passed, 0 failed. `bash -n` clean on both scripts.
- Bar byte-identity: identical to `bbabaf8` (details under WR-01).
- Private-identifier search of every changed file: the only matches are the two gate scripts, which contain the search patterns and placeholder fixtures by design (already the case before this round).

A fresh BM review, the paired Codex pass and, if the head is assessed high risk, the vibe-check were not run by this fixer.

## Left for a ruling

1. **The publication gate does not pass on this branch, and did not at `139200e` before this round.** Run on the real repository it reports BLOCKED on three files committed in `139200e`: the iteration-2 review snapshot and the two Codex output files for head `1a65339c35ec`. Every match was inspected: the review's sentence listing what it searched for uses one of the gate's blocked words, and the Codex files quote the gate's own search pattern and placeholder fixture paths and hosts. None is a real private identifier. Nothing was changed: the Codex files are immutable evidence, and the review snapshot is a per-head record. This fix report was worded so that it adds no new match. Needs: a decision on how these three are handled before the push (record them as reviewed false matches, or change how the gate treats placeholders), since the gate has no hand-review exception for this check.
2. **`86-01-PLAN.md` embeds the gate script's text**, which now differs from the fixed script by the new check. The plan is already executed and was not edited.
3. **Blueprint.** It was not in the list of files to update for D-A, so its dated note says the vibe-check is required but not who starts it, and a sentence in its superseded section still reads "does not automatically launch vibe-check". The note's widened list (IN-01) does not name that sentence by its section, though "Risk-based review recommendation at each checkpoint" covers it.
4. **`CLAUDE.md` "Review workflow" bullet on the checkpoint record** was not among the sentences named for editing and is unchanged. It is consistent with the new text but does not itself say who starts the vibe-check.
5. **Log rows for D-B and D-C: the Question column is a neutral description of the subject**, because the exact question shown to the owner was not available to this fixer. The Answer column uses only the option label and the owner's own message as given. If the exact question text should be recorded, those two cells need it.
6. **Carried over from round 1, still open:** `.planning/REQUIREMENTS.md` RISK-02 still reads "explicitly recommends an additional vibe-check ... and records the owner's decision"; the blueprint status line still reads "Proposed". The guide's adoption checklist still advises adopters to define a failing-test-or-reproduction rule, which is advice to the adopter and was left.

---

_Fixed: 2026-11-14T15:47:39Z_
_Fixer: Claude (bm-code-fixer)_
_Iteration: 2_
