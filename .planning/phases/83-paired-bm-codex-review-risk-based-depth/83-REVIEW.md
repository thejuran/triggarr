---
phase: 83-paired-bm-codex-review-risk-based-depth
reviewed: 2026-10-23T20:00:00Z
depth: standard
review_head: d90c1c135dacec904c7df183a2d3ff7071699f24
diff_base: 6f3841aaae4f2511efe6796f7f5c7ad50b423f90
previous_review: 83-REVIEW-385baa75ac1b.md
files_reviewed: 18
files_reviewed_list:
  - .planning/config.json
  - .claude/schemas/codex-review-findings.schema.json
  - CLAUDE.md
  - docs/bm-review-baseline-2026-10-22.md
  - docs/buildomator-greptile-pilot.md
  - docs/codex-adversarial-review-contract.md
  - docs/owner-cli-acceptance.md
  - docs/review-checkpoint-record.md
  - docs/review-classification-policy.md
  - tests/codex_report_status.py
  - tests/codex_review_run.py
  - tests/test_app_cards.py
  - tests/test_codex_report_status.py
  - tests/test_codex_review_contract.py
  - tests/test_codex_review_run.py
  - tests/test_review_checkpoint_record.py
  - tests/test_review_instructions.py
  - triggarr/templates/partials/cycle_grade.html
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
carried_from_previous:
  fixed_verified: 0
  still_present: 7
  still_present_carried_phase_85: 6
  set_aside_ruled: 0
status: issues_found
---

# Phase 83: Code Review Report (round 7 re-review)

**Reviewed:** 2026-10-23T20:00:00Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found (1 new Warning, 2 new Info; no blockers)

## Summary

This round re-reviews local head `d90c1c135dacec904c7df183a2d3ff7071699f24` against `83-REVIEW-385baa75ac1b.md`. Since `385baa7`, only two commits change in-scope files:
- `304a5f2` adds `test_acceptance_codex_exception_is_an_approved_fallback_only` to `tests/test_review_instructions.py`.
- `4e1d471` rewrites the Codex clause in `docs/owner-cli-acceptance.md` step 1. Only an owner-approved fallback review recorded for this exact head can now stand in for an INCOMPLETE/PENDING Codex pass, and a wait or retry-later choice blocks acceptance.

`git diff 385baa7..d90c1c1` confirms that no other in-scope file changed (the rest of the diff is under `.planning/`). `test_review_instructions.py`, `test_codex_review_contract.py` and `test_review_checkpoint_record.py` pass: 34 passed.

The new wording closes the gap it targets: a "wait" or "retry later" choice can no longer be read as satisfying the acceptance prerequisite. It agrees with the contract's Failure rule on the three options and on never treating INCOMPLETE/PENDING as complete. The new test pins the new wording and checks that the old wording is gone.

The new Warning is that acceptance now depends on an "owner-approved fallback review", and the governing documents disagree about what that can be:
- The contract's only named example of a fallback is vibe-check.
- The checkpoint record says vibe-check never substitutes for Codex.
- The checkpoint record has no field for recording a fallback.

## Previous findings status (83-REVIEW-385baa75ac1b.md)

| ID | Status | Evidence |
|----|--------|----------|
| WR-01 (SIGTERM/SIGHUP leaves a codex/pytest group running after `start_new_session`) | **Still present** | `tests/codex_review_run.py` is unchanged since `385baa7`. No signal handler was added, and there is no SIGTERM test. |
| IN-01 (`_kill_group` suppresses only `ProcessLookupError`; macOS raises EPERM for a group holding only a zombie) | **Still present** | Unchanged. |
| IN-02 (docstring says "any other interruption"; grandchildren still running after a normal exit are never killed) | **Still present** | Unchanged. |
| IN-03 (contract not updated for process-group kill / blank `commands_run` rule) | **Still present** | `docs/codex-adversarial-review-contract.md` is unchanged since `385baa7`. Step 4.4 still says "Python's subprocess timeout". |
| IN-01 r5 (Ctrl-C leaves a reserved attempt with no `.status.json`) | **Still present, partly mitigated** | Unchanged since the round-6 assessment. |
| IN-02 r5 (RunnerError invariant rests on a comment; the reservation can half-succeed) | **Still present** | Unchanged. |
| IN-03 r5 (locale encoding rather than UTF-8) | **Still present** | Unchanged. |
| WR-03 (PR judged by its own checker) | Still present, carried to Phase 85 per owner | No base-checker run. |
| WR-04 (raw `.jsonl` exposes the home path; docstring overclaims) | Still present, carried to Phase 85 per owner | Unchanged. |
| IN-01 r4 (template matches display text) | Still present, carried to Phase 85 per owner | `cycle_grade.html` is unchanged. |
| IN-02 r4 (no `pr_url` / `scope` comparison) | Still present, carried to Phase 85 per owner | Unchanged. |
| IN-03 r4 (stale untrusted clause in prompt) | Still present, carried to Phase 85 per owner | Unchanged. |
| IN-04 r4 (`diff_argv` used only by tests; substring guards) | Still present, carried to Phase 85 per owner | Unchanged. The new test is also a substring guard, which is acceptable for a docs drift test. |

The round-4 SA-01 to SA-03 items remain ruled by the owner (2026-10-23) and are not repeated.

## Narrative Findings (AI reviewer)

### Warnings

#### WR-01: Acceptance now requires an "owner-approved fallback review", but the only fallback the contract names is one the checkpoint record forbids, and the record has no place to put one

**Files:**
- `docs/owner-cli-acceptance.md:15` (step 1)
- `docs/codex-adversarial-review-contract.md:93` (Failure rule)
- `docs/review-checkpoint-record.md:67`, `:81-92` (Codex table), `:128`

**Issue:**
- After `4e1d471`, the only way to accept a head whose Codex pass is INCOMPLETE/PENDING is "an owner-approved fallback review recorded for this exact head under that contract".
- The contract's Failure rule (`:93`) defines that option as "approve a fallback such as vibe-check (D-09)". Vibe-check is the only example given anywhere.
- `docs/review-checkpoint-record.md:67` says: "Vibe-check never substitutes for Codex or Greptile, never waives a finding and never reduces required coverage."
- The two rules contradict each other, and the acceptance step now depends on the contradiction. An operator following the contract can record vibe-check as the fallback and present the head for acceptance, while the record template says that does not count. An operator following the record has no defined fallback at all.
- "Recorded for this exact head" also has no defined location. The Codex table's Status field allows only `complete | INCOMPLETE/PENDING, with reasons | PENDING — untrusted source`. There is no field for the fallback type, the owner's verbatim approval, or the head the fallback reviewed. Step 1 therefore asks the operator to confirm a record that the template never produces.
- This matters most for the untrusted-source path (`contract:54`, `record:128`): all Dependabot PRs go through it until Phase 85. "Wait" or "retry later (after Phase 85)" now blocks acceptance, so every Dependabot PR now has to go through this undefined fallback. That includes the security patch releases required by the global release rule.
- The rule fails closed, because with no recorded fallback acceptance is blocked. That is why this is not a blocker. The effect is still a governing-document contradiction exactly where the owner makes the acceptance decision.

**Fix (needs an owner decision on what may be a fallback; the wording can follow):**
1. Make the contract `:93` and the record `:67` agree. Either:
   - drop "such as vibe-check" and name the allowed fallbacks, for example "a fresh independent review of this exact head that the owner names and approves"; or
   - qualify `:67` with: "except when the owner explicitly approves it as the Codex fallback for that head under the contract's Failure rule".
2. Add a row to the checkpoint record's Codex table, with a drift test in `tests/test_review_checkpoint_record.py`:
   ```markdown
   | Owner-approved fallback | none \| <fallback review, its report location, the head SHA it reviewed, and the owner's decision quoted verbatim> |
   ```
3. Add the acceptance consequence to the contract's Failure rule: "Only an approved fallback recorded for this exact head lets acceptance proceed; wait and retry-later keep it blocked." That way the governing contract, not only the acceptance procedure, states it.

### Info

#### IN-01: The acceptance consequence of "wait / retry later" is stated only in the acceptance doc, not in the two documents it cites

**Files:** `docs/codex-adversarial-review-contract.md:54`, `:93`; `docs/review-checkpoint-record.md:128`, `:178`
**Issue:**
- Step 1 says the Codex status is assessed "per `docs/codex-adversarial-review-contract.md`" and "under that contract", but the new rule ("a wait or retry-later choice blocks acceptance") exists only in `owner-cli-acceptance.md`.
- The contract and the checkpoint record both offer the three choices as if they were equivalent, and the record's closing checklist (`:178`) says it "assembles the evidence that procedure's step 1 ... require[s]". Neither tells the owner, at the moment of choosing, that two of the three choices stop the PR from being accepted.
- These rules are not contradictory, but the owner may pick "wait" without knowing that it blocks acceptance.
- The new test guards only the acceptance doc, so the documents can drift further apart.

**Fix:** Covered by fix item 3 of WR-01. Also add a clause to `record:128`: "wait or retry later leaves the head unacceptable until Codex completes or a fallback is approved." Add a contract drift assertion for it.

#### IN-02: The pilot checklist's approval precondition still omits the paired Codex review

**File:** `docs/buildomator-greptile-pilot.md:85`
**Issue:** Step 4 says "Approve only after CI, the current Greptile review when one ran, and any applicable vibe-check/UAT are complete." It does not mention the Codex pass, which `owner-cli-acceptance.md` step 1 now gates on, with the narrowed fallback rule. Someone approving through the GitHub UI route described in the same sentence reads the shorter list.
**Fix:** Add "the paired Codex review for this head (complete, or an owner-approved fallback recorded per `docs/codex-adversarial-review-contract.md`)" to that list. Extend `test_acceptance_prerequisites_include_the_paired_codex_review`, or add a sibling test, to cover the pilot doc.

## Set aside (needs ruling)

None.

---

_Reviewed: 2026-10-23T20:00:00Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
