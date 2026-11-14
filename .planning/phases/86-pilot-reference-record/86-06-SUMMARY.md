---
phase: 86-pilot-reference-record
plan: 06
subsystem: review-workflow
tags: [pilot, card-template, bm-review, codex, vibe-check, d-09]

requires:
  - phase: 86-pilot-reference-record
    provides: "86-05 card-template H1 46c39194249d1e7bcd2362a91d238d0997539f3f and its no-reachable-divergence conclusion"
provides:
  - "Card-template PR per-head review record: classification, RISK-01 (low), BM standard, paired Codex complete (0 findings), routine vibe-check, D-09 labels"
  - "H_final = H1 (no confirmed defects, no revision)"
affects: [86-07, 86-10, 86-08]

key-files:
  modified:
    - .planning/phases/86-pilot-reference-record/86-REVIEW-EVIDENCE.md
  created:
    - .planning/phases/86-pilot-reference-record/86-REVIEW-card-46c39194249d.md
    - .planning/phases/86-pilot-reference-record/vibe-check/46c39194249d-card-routine.{md,json}
    - .planning/phases/86-pilot-reference-record/codex/46c39194249d-pilot-card-a1.{prompt.txt,meta.json,last.json,status.json,pytest.txt}

key-decisions:
  - "BM WR-01 and vibe-check cov-001 (no rendering test for the template switch) are labeled unproven under D-09. The gap is real and reproduced: swapping in the old template still passed all 148 card and outcome tests. No defect was found; the new template behaves correctly."
  - "The Codex .jsonl transcript was withheld under the publication gate: it contains a local user name in an `ls -l` event. It was moved out of the repository and not edited. The graded report is published, and Codex completion is graded from it."
  - "No confirmed defect, so H_final = H1 and no revision was made, as the plan requires."

requirements-completed: []

duration: ~25 min
completed: 2026-10-30
---

# Phase 86 Plan 06: Card-template PR review record

**The card-template PR's first head went through the full review process: BM, paired Codex and routine vibe-check. None of them found a product defect, so H_final = H1.**

H_final: 46c39194249d1e7bcd2362a91d238d0997539f3f

## Results

- **BM (standard/standard):**
  - WR-01: no card test checks that the template uses `kind`. Reproduced. Labeled unproven, since it is a test gap and not a defect.
  - IN-01: the kind names are string literals.
  - IN-02: the test hardcodes "malformed".
  - SA-01: a tampered record can show two explanations. This predates the PR.
- **Codex `pilot-card` a1:** complete, verdict no-findings, inspected head = H1. Its limitations note names the same template-wording test gap.
- **Routine vibe-check (pass 1):** 1 Medium (the same rendering-test gap) and 3 below the reporting threshold. Bugs, impact and Codex-in-vibe-check each confirmed that grouping is unchanged for well-formed records.
- **D-09:** 0 confirmed, 0 false positive; every finding unproven, with reasons.

## Owner-facing note

The PR's one point is the template switch, and no test pins it. A card test that fails under the old template is a cheap addition. BM drafted one (`test_card_groups_by_kind_not_text`). The plan doesn't do it automatically, because D-09 counts it as a test gap rather than a confirmed defect. Whether to add it before the push in 86-07 is the owner's call.

## Deviations

- The Codex `.jsonl` was withheld; see key-decisions. It is listed under "Withheld files" in `86-REVIEW-EVIDENCE.md`.
- The routine vibe-check's coverage run overlapped BM and Codex. This is not the comparison PR, so order and overlap don't matter here.

## Commits

- `9d965e3` docs(86-06): first-head review record for the card-template PR
- `9f5fb5b` docs(86-06): card-template PR final head is H1 (no confirmed defects)
