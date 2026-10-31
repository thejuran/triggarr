# Phase 86 Pilot Record

## Purpose and status

This record is the Phase 86 pilot evidence and decision log for PILOT-01..04.
It exists so the owner's PILOT-03 decision (retire routine vibe-check or not;
keep BM/Codex completion a manual owner check or extend the acceptance gate
to require it) can be made from a method and a bar that were fixed before any
comparison result existed, not fitted to the results afterward — the
blueprint's "set criteria before running the comparison" rule
(`docs/bm-greptile-codex-blueprint.md`).

Status as this section is written (86-01, Task 1): the retirement bar and the
PILOT-02 comparison method below are committed now, before any Refresh-counts
code, review, or comparison result exists. The scorecards for the three
already-merged pilot PRs (#48, #36, #44) are filled next, from committed
evidence only (86-01, Task 2). The two new pilot PRs, the PILOT-02 comparison
itself, and the owner's PILOT-03 decisions are filled by later plans, named at
each placeholder below.

Public-repository note: this phase branch is pushed to a public GitHub
repository. No private-infrastructure identifier of any kind appears
anywhere in this record (2026-10-21 published-history rule).

## Retirement bar (D-15, fixed before results)

> The bar is fixed now, before any comparison result exists. Recommend **retiring routine vibe-check only if, on the fresh comparison and across the pilot, vibe-check found no proven defect (D-09) that BM + Codex missed.** If it found one, recommend keeping routine vibe-check, or keeping it for the risk level where it made the unique catch. The owner makes the final decision; the bar shapes Claude's recommendation only.

Committed before any Refresh-counts code, review or comparison result
existed; see this commit's position in `git log`.

## Standing items unaffected by PILOT-03 (D-16)

Two things in the current review process stay in force no matter what the
owner decides in PILOT-03 (D-16):

1. **Bot/fork PRs keep the vibe-check fallback.** A bot or fork PR's Codex
   pass stays inspection-only; when it is INCOMPLETE/PENDING after one retry,
   the owner's per-PR approved vibe-check (or another independent reviewer)
   fallback is still how that head gets accepted. Source: this phase's own
   D-16 (`86-CONTEXT.md`), recording the owner's 2026-10-30 decision to close
   Phase 85.1 as an exception ("Keep vibe-check fallback" —
   `.planning/phases/85.1-isolated-codex-review-for-untrusted-prs/85.1-REVIEW-EVIDENCE.md`,
   "Owner decision (2026-10-30): keep the vibe-check fallback; close Phase
   85.1 as an exception"), under the fallback mechanism Phase 85 D-16 defined
   (`.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-CONTEXT.md`
   D-16, "Codex fallback definition").
2. **BM still recommends an extra vibe-check at high risk (RISK-02).** Every
   checkpoint's risk note still carries an explicit vibe-check recommendation
   when risk is assessed high. Source: Phase 83
   (`.planning/phases/83-paired-bm-codex-review-risk-based-depth/83-CONTEXT.md`;
   `.planning/REQUIREMENTS.md` RISK-01/RISK-02).

Phase 83's model change (83-CONTEXT D-02) is recorded separately in the
measurement rules below; it is not a D-16 standing item, but it bears on how
any pre-Phase-83 evidence is read.

## PILOT-02 comparison method (pre-registered)

The fresh, independent comparison (PILOT-02) runs on the **Refresh-counts
PR**, at its first committed head (H1), before any fix lands:

1. Vibe-check runs `/vibe-check:deep-review` on H1, independently, with
   coverage prepared first per `docs/review-checkpoint-record.md` "Coverage
   evidence for vibe-check" (a CI artifact for the exact head when one
   exists, otherwise exact-head local coverage, checked and only then copied
   to the vibe-check worktree root). Its output is saved before BM or Codex
   runs. Claude does not open Codex's `.last.json` or BM's findings list
   before invoking vibe-check, and does not summarize either into vibe-check's
   prompt or framing.
2. BM code review (standard) runs on H1, followed automatically by the
   paired, read-only Codex pass on the same exact head (Phase 83 D-06). No
   vibe-check output is passed to either.
3. Both reviewers' H1 findings are recorded into the comparison table
   **before** any triage-fixing starts. Every finding from both reviewers is
   judged with D-09's proof-based rule at this point: a finding counts as a
   **confirmed consequential defect** only if a failing test or a
   reproduction demonstrates it; every other finding is labeled **false
   positive** (with the reason) or **unproven** (with the reason). The owner
   approves the tally, not the code — the owner is not asked to adjudicate
   the code itself.
4. One batched revision fixes the confirmed defects (the standing triage
   flow), producing a new head (H_final). The PILOT-02 comparison has already
   concluded at H1 and is not reopened by this fix round.
5. Routine vibe-check (the standing "code"-class rule, while the owner keeps
   it) plus a fresh BM review and a fresh paired Codex pass run on H_final —
   this is the PR's ordinary acceptance evidence, kept separate from the
   PILOT-02 comparison that already happened at H1. Running vibe-check twice,
   on two different heads of the same PR, is the intended outcome here, not a
   redundancy to remove (D-06's second sentence).

Other pre-registered terms:

- **D-07 (size):** the Refresh-counts PR counts as "substantial" for
  PILOT-02 because it changes real state/error-path logic across three apps
  now (Sonarr, Lidarr and, per the owner's 2026-10-30 extension D-02a,
  Radarr), with a regression test for each. Its size is recorded honestly as
  moderate, not inflated to "large" to make the comparison look more
  dramatic.
- **D-08 (why #48 cannot be the comparison):** PR #48 is excluded as
  PILOT-02 comparison evidence. Its vibe-check ran only on its final head,
  after five BM/Codex fix rounds
  (`.planning/phases/85.1-isolated-codex-review-for-untrusted-prs/85.1-REVIEW-EVIDENCE.md`)
  — by then vibe-check could only confirm or miss defects BM+Codex had
  already found and the owner had already seen, which proves nothing about
  independent coverage. #48's vibe-check result is cited in its own scorecard
  below; that limitation is stated there, and it is never used as comparison
  evidence, not comparison evidence for PILOT-02.
- **D-09 (proof-based judging):** as above — confirmed only with a failing
  test or a reproduction; everything else is false_positive or unproven,
  each with its reason recorded; the owner adjudicates the tally, never the
  code.

## Measurement rules (D-10..D-14)

For each pilot PR and each reviewer that ran (BM, Codex, vibe-check,
Greptile when it ran), the scorecards below record seven columns (D-10):

1. Confirmed consequential defects
2. False positives
3. Later-found misses
4. Revision rounds
5. Review time
6. Observable usage/cost
7. Owner effort

Rules applied to every cell:

- **D-11 (existing PRs — #48, #36, #44):** a count goes in only if a
  committed record states it. A finding the record dispositions as fixed,
  with a reproduction or a regression test showing it was real, counts as a
  confirmed consequential defect (D-09). A finding dispositioned false
  positive counts as a false positive. Anything else — nonblocking_debt,
  pending, accepted residual, partially fixed — is recorded as "unproven
  (record does not say)" rather than guessed at. Review time, usage/cost, and
  owner effort are marked **"not recorded"** wherever no committed record
  states them. They are never estimated or rebuilt from commit or comment
  timestamps.
- **D-12 (owner effort, new PRs only):** on the two new pilot PRs, owner
  effort is the number of decisions or approvals Claude brings to the owner
  on that PR, logged as they happen — never self-reported minutes. Counting
  rule (locked here so both new PRs' owner-effort numbers are comparable):
  count each distinct yes/no or choice the owner has to make — approving the
  exact commit counts as 1; a fix-vs-accept-as-is choice counts as 1; a
  RISK-02 vibe-check recommendation response counts as 1; a push approval
  counts as 1; a Codex-fallback approval counts as 1. A multi-line checklist
  message that asks one question (for example, the single acceptance
  checklist) counts once, not once per line. This rule is written once, here,
  rather than re-derived per PR. It is **not** applied retroactively to
  #48/#36/#44: their owner-decision quotes are preserved verbatim in the
  per-PR scorecards below as the committed record, but are not tallied under
  this rule, since the rule did not exist when those decisions were made and
  reconstructing a count now would be estimating, which D-11 forbids.
- **D-13 (usage/cost):** usage/cost is wall-clock time plus whatever usage or
  token counts each tool actually prints. If a tool reports nothing, the
  cell says so. No dollar estimates, on any PR.
- **D-14 (later-found misses, cutoff):** a later-found miss counts if a
  later review round, another reviewer, CI, or production finds it before
  the Phase 86 PR is accepted. This cutoff is short for the newest PRs in
  this pilot — the Refresh-counts and card-template PRs will have had only
  days, not the weeks #48/#36/#44 have had, for anything to surface after
  their own review. That asymmetry is recorded, not smoothed over.
- **Live measurement on the two new PRs:** review time for the Refresh-counts
  and card-template PRs is measured live — start and end UTC times are
  written down when each reviewer's run starts and finishes, never rebuilt
  afterward from a commit timestamp.
- **Model-change caveat (83-CONTEXT D-02):** BM's `sonnet`/`haiku` tiers
  moved to Claude Sonnet 5.5/Haiku 5.5 as part of the same update that turned
  on `workflow.code_review` (Phase 83). All five pilot PRs post-date that
  change. Any comparison in this record or the adoption guide that cites
  review evidence from before Phase 83 states that the models and the review
  settings changed together at that point, so a difference in finding
  quality is never attributed purely to "the paired workflow vs. vibe-check"
  without that caveat.

## Pilot set and categories (D-01, D-05)

The pilot set has five PRs (D-01):

| PR | Phase | Size | Category (D-05) | Status as of this commit |
|---|---|---|---|---|
| #48 | 85.1 | large | security-sensitive; larger change | merged 2026-10-30 |
| #36 | 85 | large | larger change; the pilot's large-PR failure-mode evidence (Codex INCOMPLETE for size) | merged 2026-10-28 |
| #44 | 85 follow-up | small | small fix | merged 2026-10-28 |
| Refresh-counts fix | 86 (new) | moderate | state/error-path logic | not yet opened |
| Card-template structured kind | 86 (new) | moderate | UI | not yet opened |

Category coverage (D-05): small fix is #44; state/error-path logic is the
Refresh-counts PR; UI is the card-template PR; security-sensitive is #48;
larger change is covered by both #36 and #48. Every category named in D-05
has at least one PR; none is stretched to fill a category it does not fit.

### Gaps

None recorded yet.

## Scorecards

Filled in by plan 86-01 Task 2.

## PILOT-02 comparison result

Filled in by plan 86-03.

## Owner decisions log

Filled in by all plans.

## PILOT-03 recommendation and decisions

Filled in by plan 86-08.
