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

Checked against evidence on 2026-11-14: the **UI** category (D-05) is covered
only by the card-template PR (#55), and 86-05's divergence analysis found no
reachable divergence between the old text-matching classification and the
new structured-`kind` classification for any input the application's own
code produces (see that PR's scorecard, "D-03 note", below). So the pilot
has no PR that shows the paired review process catching, or missing, a
defect in something a user would actually see rendered differently; "UI
coverage" here means a template refactor behaved identically, not that a
visible UI change was exercised. This is recorded as a gap rather than
stretched to claim visible-UI review coverage.

The other four D-05 categories hold up against the evidence without a
misfit: small fix (#44), state/error-path logic (Refresh-counts, #54,
moderate size across three apps per D-07/D-02a), security-sensitive (#48),
and larger change (#36 and #48, both reviewed as whole-PR passes with
multiple fix rounds).

## Scorecards

Columns are the D-10 metrics. Counting method (per the Measurement rules
above): a finding dispositioned *fixed*, with a reproduction or regression
test, counts as a confirmed consequential defect; a finding dispositioned
*false_positive* counts as a false positive; anything else recorded against
a finding (`nonblocking_debt`, pending, accepted residual, partially fixed)
is counted as **unproven (record does not say)** rather than guessed at.
Revision rounds count distinct reviewed heads/attempts, not individual
findings. Review time, usage/cost and owner effort read **not recorded**
unless a cited source states the value (D-11); owner-effort's counting rule
(D-12) is not applied retroactively to these three PRs (see Measurement
rules above) — their recorded owner decisions are quoted, not tallied.

### PR #48 — Isolated Codex review for untrusted PRs (security-sensitive; larger change)

Final PR head `82b34111f6c71903f4ad9e4db8c8956ced598a59`, merged
2026-10-30T21:16:10Z. Counts below are totaled across the whole PR's review
history — 7 reviewed local-checkpoint/PR heads
(`cc33f1578995` → `0aeeedaa4f89` → `2aa2cc81e110` → `c7c34a56209e` →
`3eda4277ebae` → `f033b7e391e8` → `82b34111f6c7`), i.e. 5 fix rounds between
the first and final head (D-08).

| Reviewer | Confirmed defects | False positives | Later-found misses | Revision rounds | Review time | Usage/cost | Owner effort |
|---|---|---|---|---|---|---|---|
| BM | 22 (CR-01, WR-01/02/04-08/10, WR-01-03, SA-03, IN-03, WR-01, SA-04, IN-05, IN-07, IN-01-04 — each dispositioned `fixed` with BM's next-iteration verification) | 0 | none recorded (D-14 cutoff: Phase 86 PR acceptance) | 7 BM review iterations across the 7 heads above | not recorded | not recorded | not recorded (D-12 postdates this record; see Measurement rules) |
| Codex | 9 (`a2:F001`, `a2:F002`, `a1:F002` at `cc33f15`; `a1:F001` at `0aeeedaa`; `F001`, `F002` at `2aa2cc8`; `a1:F001`, `a2:F001` at `c7c34a5`; `a1:F001` at `3eda427` — each dispositioned `fixed`) | 0 | none recorded (D-14 cutoff) | 7 attempts/heads (2 attempts each at `cc33f15`, `c7c34a5`, `f033b7e`; 1 each elsewhere) | not recorded | not recorded (per-head command counts are logged in each head's own `.last.json` under `codex/`, but no committed record totals them for the PR) | not recorded |
| vibe-check | 0 | 1 (`tests/codex_review_run.py:3445` git-read item — owner dismissed, verified via a scratch-repo reproduction) | none recorded (D-14 cutoff) | 1 (ran only on the final head `82b34111f6c7`, after the 5 fix rounds above) | not recorded | 13 raised, 2 reported, 11 filtered (as reported by `/vibe-check:deep-review`) | not recorded |
| Greptile | n/a | n/a | n/a | n/a | n/a | did not run (committed record says "pending on this head (optional; free tier only)"; `gh pr checks 48` shows no Greptile check on the merged head) | n/a |

**D-08 note on the vibe-check row:** the vibe-check result above ran only on
the final head, after five BM/Codex fix rounds already found and fixed by
the owner's review — it is cited here as PR #48's own scorecard color only,
and is **not comparison evidence** for the PILOT-02 fresh-head comparison.

1 item is still open as an accepted residual rather than fixed or
false-positive at merge (`codex:82b34111f6c7:a2:F001`, low severity, owner
"backlog F001; push and open the PR") — counted above as neither confirmed
nor false positive (folded into "unproven" territory, not tallied as a
separate column per the D-10 column set).

Sources: `.planning/phases/85.1-isolated-codex-review-for-untrusted-prs/85.1-REVIEW-EVIDENCE.md` (all seven per-head records and their Dispositions tables); `gh pr view 48 --json additions,deletions,changedFiles,mergedAt`; `gh pr checks 48`.

### PR #36 — Phase 85 follow-on CI improvements & acceptance usability (larger change; large-PR failure-mode evidence)

Final PR head `5a97e1f98982b47672ba108e357a024e0f2a44e2`, merged
2026-10-28T20:01:20Z (195 changed files, +31530/-293).

| Reviewer | Confirmed defects | False positives | Later-found misses | Revision rounds | Review time | Usage/cost | Owner effort |
|---|---|---|---|---|---|---|---|
| BM | 8 (iteration-1's 2 critical + 4 warning, fixed across rounds 1-4 at `252fe61`/`094028e`/`eae6d34`, counted as 6 by the record's own count rather than itemized; plus iteration-6's WR-01/WR-02, fixed at `06ac793`/`684ae13`) | 0 | 2 (the two CI traps the vibe-check fallback review found and this PR's own BM passes did not flag — see vibe-check row; fixed post-merge in PR #44) | 8 BM review iterations (iteration 1, phase-execution; iterations 2-5, fix-round re-reviews; iterations 6-8, post-push) | not recorded | not recorded | not recorded |
| Codex | 1 (`codex:fb8da6e2abe5:a1:F001`/`a2:F001`, drain-timeout bytes/str `TypeError`, fixed at `2f2e8fc` with a regression test that failed before and passed after) | 0 | 2 (same two CI traps the vibe-check fallback found; Codex's own two attempts on this head did not flag them — INCOMPLETE/PENDING: both attempts self-declared incomplete, diff and 27 plan files exceeded output limits) | 2 attempts (`a1`, `a2`), both INCOMPLETE/PENDING — no completed Codex round on this PR (**D-01: this is the pilot's recorded evidence of how the workflow fails on very large PRs**) | not recorded | commands run: a1 28, a2 19 (as reported in `.last.json`) | not recorded |
| vibe-check | 0 confirmed via reproduction (25 findings total, all dispositioned `nonblocking_debt` — 18 deferred, 7 accepted, 0 critical/warning) | 0 | 0 (it found the misses itself, before BM/Codex's own passes concluded) | 1 full deep-review pass (8 lanes), run as the **owner-approved fallback for Codex's incomplete pass**, not as routine vibe-check | not recorded | 25 findings raised (as reported); 0 critical/0 warning | not recorded |
| Greptile | n/a | n/a | n/a | n/a | n/a | did not run (committed record: "not run on this head (optional since 2026-10-22)"; confirmed by `gh pr checks 36`) | n/a |

**D-01 note on the Codex row:** PR #36's Codex pass never completed (diff too
large for one pass, even across 2 attempts); the owner approved vibe-check as
the recorded fallback. This is the pilot's own documented instance of the
paired workflow failing on a very large PR, named in D-01.

**Later-found-misses detail:** two CI traps — "Dependabot's github-actions
group rewrites checkout/setup-buildx pins, breaking the pinned-SHA no-skip
tests" and "the CI wiring test reads tool pins from a phase planning file
that archiving would delete" — were among the vibe-check fallback review's
25 findings (named `impact-001` and `arch-002`/`impact-002` in PR #44's own
checkpoint comment) and were fixed post-merge in PR #44
(`b0e1ee4`, `3b3713b`). Neither BM's nor Codex's own passes on PR #36 flagged
either one; both are later-found misses against the D-14 cutoff (Phase 86 PR
acceptance has not yet occurred, so the cutoff has not closed).

Sources: `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-CHECKPOINT-5a97e1f98982.md`; `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW-EVIDENCE.md` ("Post-plan review record", "Post-execution deep review and BM iterations 6-7", "Accepted residual risk"); `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-VERIFICATION.md` (post-merge note); `gh pr view 36 --json additions,deletions,changedFiles,mergedAt`; `gh pr checks 36`; PR #44 checkpoint comment (`gh pr view 44 --comments`).

### PR #44 — Phase 85 follow-up: Dependabot-safe no-skip tests, archive-safe tool pins (small fix)

Single PR head `0385e717049cf90a82c6e23b04fa53d4a83b19e9`, merged
2026-10-28T20:22:24Z (23 changed files, +1224/-67). This PR is itself the fix
for the two later-found misses recorded against PR #36's BM and Codex rows
above.

| Reviewer | Confirmed defects | False positives | Later-found misses | Revision rounds | Review time | Usage/cost | Owner effort |
|---|---|---|---|---|---|---|---|
| BM | 0 (1 info item, `bm:85:it9:IN-05`, dispositioned `nonblocking_debt` — unproven, not a confirmed defect) | 0 | none recorded (D-14 cutoff; this PR is only ~2 days old as of Phase 86 planning, so the window for anything new to surface is short — see D-14's own caveat) | 1 (single head, no fix round needed) | not recorded | not recorded | not recorded |
| Codex | 0 | 0 | none recorded | 1 attempt, complete, `verdict: no-findings` | not recorded | not recorded | not recorded |
| vibe-check | n/a | n/a | n/a | n/a | n/a | not run — risk assessed moderate, not high; no additional vibe-check recommended | n/a |
| Greptile | n/a | n/a | n/a | n/a | n/a | did not run (committed record: "not run on this head (optional)"; confirmed by `gh pr checks 44`) | n/a |

Sources: PR #44 checkpoint comment (`gh pr view 44 --comments`); `gh pr view 44 --json additions,deletions,changedFiles,mergedAt,commits`; `gh pr checks 44`.

### PR #54 — Refresh counts skip malformed records (state/error-path logic)

Comparison head (H1) `03182462100e9f71defc9408245410d2b99110a5`; accepted
and merged final head `1062097a7676fddcdde3caf500f96ba1ea04d65c`, merged
2026-11-14T03:23:00Z, merge commit `b80c3e26cf9456dde7245350d7033f6feb94db0f`.
One finding-driven fix round (the 86-04 batched revision that fixed the
confirmed defect found at H1); no integration head, since this PR merged
first and nothing else landed on main ahead of it.

| Reviewer | Confirmed defects | False positives | Later-found misses | Revision rounds | Review time | Usage/cost | Owner effort |
|---|---|---|---|---|---|---|---|
| BM | 1 (`bm:03182462100e:WR-01`: Sonarr logs misleading "skipped malformed record" warnings for unmonitored episodes it would never search; confirmed by proof test P1; fixed in the 86-04 revision, verified fixed at H_final by the regression test, a vibe-check recheck and BM/Codex's own H_final passes raising nothing on it) | 0 | none recorded (D-14 cutoff: the Phase 86 PR is not yet accepted as of this writing) | 1 (the 86-04 batched revision) | H1 2026-10-31T00:42:59Z–00:45:20Z (2 min 21 s); H_final 2026-10-31T01:09:28Z–01:11:46Z (2 min 18 s) | Tool printed none at either head; harness reported 76k reviewer subagent tokens at H1, 83k at H_final | 4 |
| Codex | 0 (verdict `no-findings`, complete, at both H1 and H_final) | 0 | none recorded | 1 (86-04 batched revision; Codex ran one complete attempt at each of H1 and H_final) | H1 2026-10-31T00:45:25Z–00:48:04Z (2 min 39 s, incl. ~93 s full-suite run); H_final 2026-10-31T01:09:19Z–01:11:51Z (2 min 32 s, incl. full-suite run) | H1 `.jsonl` `turn.completed`: input 630,831 tokens (543,360 cached), output 3,626, reasoning 149. H_final: input 529,508 tokens (446,208 cached), output 3,072, reasoning 144 | 4 |
| vibe-check | 1 (`VC-arch-001` + `bugs-001`/`imp-001` merged: the same Sonarr ordering defect BM also reached independently at H1; confirmed by proof test P1 — not a unique catch, both sides found it) | 0 | 0 (the other four H1 findings, cov-001..004, were judged unproven rather than missed; nothing has surfaced later as of this writing) | 1 (86-04 batched revision); ran as the pre-registered PILOT-02 comparison pass at H1 and as the routine pass 2 at H_final | H1 2026-10-31T00:36:29Z–00:42:38Z (6 min 9 s, plus 110 s coverage prep); H_final 2026-10-31T01:12:05Z–01:16:57Z (4 min 52 s, plus 111 s coverage prep) | Tool itself printed none at either head. Harness subagent tokens — H1: triage 48k, bugs 104k, security 100k, architecture 102k, impact 101k, test-sufficiency 94k, compliance 107k, language-python 112k, framework-fastapi 104k. H_final: triage 85k, bugs 70k, security 73k, architecture 62k, impact 66k, test-sufficiency 73k, compliance 77k, language-python 79k, framework-fastapi 72k | 4 |
| Greptile | n/a | n/a | n/a | n/a | n/a | did not run on either head (not pushed at H1; "optional since 2026-10-22" at the pushed, accepted head per PR #54's durable checkpoint comment) | n/a |

**D-07/D-02a note:** this PR's H1 vibe-check run is the pre-registered
PILOT-02 fresh comparison (see "PILOT-02 comparison method" and "PILOT-02
comparison result" below). Its size is recorded as moderate across all
three apps — Sonarr, Lidarr and, per the owner's 2026-10-30 D-02a extension,
Radarr — not inflated to large to make the comparison look more dramatic.

Owner effort (4) is the count of this PR's rows in "## Owner decisions log"
below: the PILOT-02 tally approval, the push approval, the acceptance
approval, and the merge approval.

Sources: `86-REVIEW-EVIDENCE.md` (Refresh-counts PR, heads `03182462100e`
and `1062097a7676`, their Dispositions tables and "Review time and usage at
H_final" table); `86-PILOT-RECORD.md` "PILOT-02 comparison result" and
"Owner decisions log"; `gh pr view 54 --json mergedAt,mergeCommit`.

### PR #55 — Card-template structured reason kind (UI)

Pre-integration head (H1) `46c39194249d1e7bcd2362a91d238d0997539f3f`;
integration head `5d58264e93a21b100d01e80503b9a7d064253d36` (origin/main
merged in once after PR #54, and PR #57 — a maintenance fix, not a pilot
PR — merged); accepted and merged final head is the same integration head,
merged 2026-11-14T05:05:32Z, merge commit
`7f6b5d4b567c06ce9a4764b94352366ef008c22b`. No finding-driven fix round:
D-09 triage found no confirmed defect at H1 or at the integration head, so
H_final = H1 = H_merge throughout.

| Reviewer | Confirmed defects | False positives | Later-found misses | Revision rounds | Review time | Usage/cost | Owner effort |
|---|---|---|---|---|---|---|---|
| BM | 0 (every finding at both H1 and the integration head — WR-01, IN-01, IN-02, IN-03, SA-01 — dispositioned `nonblocking_debt`/unproven, none fixed or false_positive) | 0 | 0 | 0 (no confirmed defect, no fix round) | H1 2026-10-31T01:31:38Z–01:33:37Z (1 min 59 s); integration head 2026-11-14T04:43:50Z–04:46:14Z (2 min 24 s) | Tool printed none at either head; harness reported 44k reviewer subagent tokens at H1, 72k at the integration head | 3 |
| Codex | 0 (verdict `no-findings`, complete, at both H1 and the integration head) | 0 | 0 | 0 | H1 2026-10-31T01:31:31Z–01:33:42Z (2 min 11 s, incl. full-suite run); integration head 2026-11-14T04:43:40Z–04:45:52Z (2 min 12 s) | H1 `.jsonl` `turn.completed`: input 220,995 tokens (153,856 cached), output 2,097, reasoning 123. Integration head: none printed | 3 |
| vibe-check | 0 (H1's one Medium — no rendering test for the template switch — was unproven/nonblocking_debt, not confirmed; rechecked and reported resolved at the integration head) | 0 | 0 | 0 | H1 2026-10-31T01:33:37Z–01:37:46Z (4 min 9 s, plus 105 s coverage prep); integration head coverage prep 2026-11-14T04:47Z–04:50Z (~3 min), review 04:50:37Z–04:56:01Z (5 min 24 s) | H1: tool printed none; harness subagent tokens triage 50k, bugs 72k, security 77k, architecture 69k, impact 73k, test-sufficiency 68k, compliance 84k, language-python 72k. Integration head: tool printed none; harness reported about 620k subagent tokens across triage and 7 lanes (per-lane breakdown not itemized in the source record) | 3 |
| Greptile | n/a | n/a | n/a | n/a | n/a | did not run on either head | n/a |

Integration re-reviews: 1 (`5d58264e93a2`) — origin/main (carrying PR #54
and PR #57) was merged into the PR branch once, with a plain two-parent
merge commit and no conflicts. No confirmed defect was found at that head,
so this is a re-review, not a revision round; its review time, usage and
owner-effort figures above already include the integration-head part
(marked "integration head" in each cell).

**D-03 note:** this PR is the backlog's "Card-template text-matching
refactor". `cycle_grade.html` now classifies reason rows by a structured
`kind` field instead of matching `outcome.py`'s rendered display strings.
86-05's divergence analysis found no reachable divergence between the old
and new classification for any input the application's own code produces —
honestly, a UI-template change with no visible difference, not a case that
exercised visible-UI review coverage (see "Gaps" above).

Owner effort (3) is the count of this PR's rows in "## Owner decisions log"
below: the push approval, the acceptance approval, and the merge approval.

Sources: `86-REVIEW-EVIDENCE.md` (Card-template PR, heads `46c39194249d`
and `5d58264e93a2`, their Dispositions tables and review-time tables, plus
"Card-template PR: integration with main (86-10)"); `86-PILOT-RECORD.md`
"Owner decisions log"; `gh pr view 55 --json mergedAt,mergeCommit`.

### Cross-PR summary

| PR | Category (D-05) | Reviewers that ran | Confirmed defects found by each | Unique catches |
|---|---|---|---|---|
| #48 | security-sensitive; larger change | BM, Codex, vibe-check (final head only, D-08) | BM 22; Codex 9; vibe-check 0 | none (vibe-check's one reported item was a false positive) |
| #36 | larger change; large-PR failure-mode evidence | BM; Codex (both attempts INCOMPLETE/PENDING for size); vibe-check (owner-approved fallback) | BM 8; Codex 1 (fixed in PR #44); vibe-check 0 confirmed via reproduction | vibe-check 2 (the two CI traps neither BM's nor Codex's own passes on this PR flagged; fixed post-merge in PR #44) |
| #44 | small fix | BM; Codex | BM 0; Codex 0 | none |
| Refresh-counts (#54) | state/error-path logic | vibe-check (PILOT-02 comparison + routine pass 2); BM; Codex | BM 1; Codex 0; vibe-check 1 (same defect as BM, found independently) | none — both sides caught the one real defect; neither missed one the other found |
| Card-template (#55) | UI | BM; Codex; vibe-check (two passes) | BM 0; Codex 0; vibe-check 0 | none |

## PILOT-02 comparison result

**Comparison head H1:** `03182462100e9f71defc9408245410d2b99110a5`
(branch `pilot-refresh-counts-skip-malformed`, base `d5a4467a4c38f8f675fb057d9a77bcc3030c379d`).
All three reviewers completed on H1. They ran in the pre-registered order:
vibe-check first, then BM, then the paired Codex pass. No vibe-check output
reached BM or Codex (the Codex prompt contains no vibe-check text), and H1 was
not changed while any of them ran. The comparison is complete.

Every finding was judged by proof (D-09). Proof tests were written against H1 and
not committed; they are listed with their results in `86-REVIEW-EVIDENCE.md`
(Refresh-counts PR, H1, "Proof tests used for D-09 judging").

| Finding ID | Reviewer | Summary (plain words) | Label (D-09) | Proof or reason | Unique to |
|---|---|---|---|---|---|
| VC-arch-001 (+ bugs-001, imp-001 merged) | vibe-check | On Sonarr, Refresh counts checks air dates before it drops unmonitored episodes, so it logs "skipped malformed record" warnings the scheduled cycle never logs. Counts are unaffected. | confirmed consequential defect | Proof test P1 fails at H1 on both queues: "Sonarr: Skipped 1 missing-queue record(s) with malformed date data (ids=[5])" for an unmonitored episode. These are misleading warnings in System Logs. | — (also BM WR-01) |
| VC-cov-001 | vibe-check | No test covers the Sonarr missing-queue tag screening step. | unproven | The test gap is real (coverage shows L2117/L2121 never run). One test written for the gap (P3: a series whose tags are not a list, with a missing-queue tag set) passes at H1. That shows only that the specific case tested behaves correctly at H1; it does not establish that the surrounding code is correct in general, so no defect was demonstrated rather than none exists. | — |
| VC-cov-002 | vibe-check | No test checks that the returned upgrade-queue list is the screened one. | unproven | The test gap is real. One test written for the gap (P4: a null upgrade-queue record, all three apps) passes at H1. That shows only that the specific case tested behaves correctly at H1; it does not establish that the surrounding code is correct in general, so no defect was demonstrated rather than none exists. | — |
| VC-cov-003 (sub-threshold, filtered) | vibe-check | The new correction to the "monitored" count is never tested with a record actually dropped. | unproven | The test gap is real. Tests P5 (Radarr) and P5c (Lidarr), each dropping one record with no `id`, pass at H1, with the expected monitored and eligible counts for that case. That shows only that the specific case tested behaves correctly at H1; it does not establish that the surrounding code is correct in general, so no defect was demonstrated rather than none exists. | — |
| VC-cov-004 (sub-threshold, filtered) | vibe-check | Radarr/Lidarr never test the "upgrade-queue tag can't be resolved" path. | unproven | The test gap is real. Test P6 (one unresolvable upgrade-queue tag, Radarr and Lidarr) passes at H1: the returned list is empty and the instance stays connected. That shows only that the specific case tested behaves correctly at H1; it does not establish that the surrounding code is correct in general, so no defect was demonstrated rather than none exists. | — |
| BM WR-01 | BM | Same Sonarr ordering problem as VC-arch-001. | confirmed consequential defect | Proof test P1 (as above). BM also reproduced it with its own probe. | — (also vibe-check) |
| BM WR-02 | BM | The code comments promise the returned upgrade-queue list contains no malformed record, but records with a bad `id`/tags still come through. | unproven | The mismatch reproduces: P2 fails at H1 for Radarr and Lidarr. But no consequence can be shown, because the only caller (`routes.py`) discards that list. | — |
| BM IN-01 | BM | Radarr/Lidarr build a fully-filtered upgrade list and never use it. | unproven | Accurate when read at H1, but it has no effect on behavior (logs only), so there is no consequence to demonstrate. | — |
| BM IN-02 | BM | The end-to-end refresh test does not check the upgrade queue; there is no refresh test for a Radarr release date without a timezone or a non-integer `id`. | unproven | The test gap is real. Tests written for the named cases (P4, P5, P5b) pass at H1. That shows only that the specific case tested behaves correctly at H1; it does not establish that the surrounding code is correct in general, so no defect was demonstrated rather than none exists. | — |
| BM IN-03 | BM | Three tests call `monkeypatch.undo()` partway through, which would also undo any future shared fixture's patches. | unproven | Latent: no current fixture patches in that scope, so no failure can be reproduced. | — |
| (none) | Codex | Codex reported no findings (verdict `no-findings`, review complete). Its limitations note says the new real-client tests don't assert what survives in the upgrade queue, which is the same gap as VC-cov-002 and BM IN-02. | — | — | — |

**Per-reviewer tally**

| Reviewer | Confirmed | False positive | Unproven | Unique confirmed |
|---|---|---|---|---|
| vibe-check | 1 | 0 | 4 | 0 |
| BM | 1 | 0 | 4 | 0 |
| Codex | 0 | 0 | 0 | 0 |
| BM + Codex (paired side) | 1 | 0 | 4 | 0 |

**Review time and usage (measured live, D-13)**

| Reviewer | Start (UTC) | End (UTC) | Wall clock | Usage printed |
|---|---|---|---|---|
| vibe-check | 2026-10-31T00:36:29Z | 2026-10-31T00:42:38Z | 6 min 9 s (plus 110 s to prepare exact-head coverage beforehand) | The tool printed none. The harness reported subagent token totals: triage 48k, bugs 104k, security 100k, architecture 102k, impact 101k, test-sufficiency 94k, compliance 107k, language-python 112k, framework-fastapi 104k. Vibe-check's own Codex pass printed none. |
| BM | 2026-10-31T00:42:59Z | 2026-10-31T00:45:20Z | 2 min 21 s | The tool printed none. The harness reported 76k reviewer subagent tokens. |
| Codex (paired) | 2026-10-31T00:45:25Z | 2026-10-31T00:48:04Z | 2 min 39 s (including about 93 s for the full-suite run) | From the `.jsonl` `turn.completed` record: input 630,831 tokens (543,360 cached), output 3,626, reasoning 149 |

**In plain terms (for the owner).** Both sides found the same real problem:
Refresh counts on Sonarr puts misleading "skipped malformed record" warnings in
System Logs for episodes Triggarr would never search. Counts are not affected.
Vibe-check reached it through three of its reviewers at once; BM reached it on
its own and reproduced it. Neither side found a defect the other missed.

Beyond that shared catch, both sides pointed out the same kind of thing: places
where tests could be stronger. Vibe-check named four gaps and BM named one
broader one. I wrote one or two tests for each gap and every one passes at H1.
That shows those specific cases behave correctly; it does not prove the
surrounding code correct in general, so these stay "unproven" rather than
"false positive". BM also noticed that a code comment promises more than the code
does (the returned upgrade list can still hold a record with no ID). That is
true, but nothing uses that list today, so it has no effect yet. Codex found
nothing to report and noted the same test gap in passing.

On cost, vibe-check took a little longer: about 6 minutes, plus 2 minutes
to prepare coverage, against about 5 minutes for BM and Codex together. It also
ran nine model agents to the paired side's two.

Measured against the retirement bar committed before any of this ran: on this PR,
vibe-check found **no proven defect that BM + Codex missed.**

Owner tally decision (2026-10-30): "Approve tally for H1 0318246. Continue with 86-04. Correct the passing-test wording to avoid claiming broader correctness than the tests establish. This approves only the comparison tally; retirement remains a separate decision using the full pilot evidence, including PR #36’s two later-fixed misses."

Per that decision, the wording for the passing tests above was corrected before this record was committed: a passing test now supports only the case it covers. This approval covers the comparison tally only. The PILOT-03 retirement decision is separate and uses the full pilot evidence, including PR #36's two later-fixed misses.

## Owner decisions log

| PR | Date | Question | Answer |
|---|---|---|---|
| Refresh-counts (H1 `03182462100e`) | 2026-10-30 | Approve the PILOT-02 tally at H1 (86-03 Task 3)? | "Approve tally for H1 0318246. Continue with 86-04. Correct the passing-test wording to avoid claiming broader correctness than the tests establish. This approves only the comparison tally; retirement remains a separate decision using the full pilot evidence, including PR #36’s two later-fixed misses." |
| Refresh-counts (H_final `1062097a7676`) | 2026-10-30 | Push decision (86-07 Task 1): push both, run another /deep-review first, or hold one? (/deep-review offered; routine vibe-check deep review already on record for this head) | "push both" |
| Card-template (H_final `46c39194249d`) | 2026-10-30 | Push decision (86-07 Task 1): push both, run another /deep-review first, or hold one? Also offered: add the card rendering test first (not chosen) | "push both" |
| PR #54 Refresh-counts (`1062097a7676`) | 2026-10-30 | Owner acceptance (86-07 Task 3): approve review acceptance for PR #54 at the exact head and run? | "Approve review acceptance for PR #54 at 1062097a7676fddcdde3caf500f96ba1ea04d65c, run 41158788888." |
| PR #54 Refresh-counts (`1062097a7676`) | 2026-11-13 | Merge (86-07 Task 3): the session reported the PR accepted, all checks passing and ready for the owner to merge | "merge pr 54" (Claude ran the merge under the owner's account at the accepted head; merge commit `b80c3e26cf94`) |
| Main-CI fix (not a pilot PR) | 2026-11-13 | CI on main failed after the #54 merge for date-driven reasons: ship the fix as its own PR from main, or fold it into PR #55? | "1" (one separate fix PR from main) |
| PR #57 main-CI fix (`49403734406a`) | 2026-11-13 | Push decision: push now, run another /deep-review first, or hold? (/deep-review offered; routine vibe-check deep review already on record for this head) | "1" (push now) |
| PR #57 main-CI fix (`49403734406a`) | 2026-11-13 | CI's image scan failed on two HIGH `zlib1g` findings in the base image: upgrade the package in the Dockerfile, approve a time-limited exception, or wait for upstream? | "1" (upgrade the package in the Dockerfile) |
| PR #57 main-CI fix (`8e3d6b49f6b5`) | 2026-11-13 | Owner acceptance: approve review acceptance for PR #57 at the exact head and run? | "Approve review acceptance for PR #57 at 8e3d6b49f6b5a923d7ee7202c3d5e56f7ec233dc, run 43556379926" |
| PR #57 main-CI fix (`8e3d6b49f6b5`) | 2026-11-13 | Merge: the session reported the acceptance check passed and the PR mergeable, and asked whether the owner would merge or instruct the merge | "merge pr 57" (Claude ran the merge under the owner's account at the accepted head; merge commit `aeead4b601d7`) |
| PR #55 Card-template (`5d58264e93a2`, integration head) | 2026-11-14 | Owner acceptance (86-10 Task 3): approve review acceptance for PR #55 at the exact head and run? | "Approve review acceptance for PR #55 at 5d58264e93a21b100d01e80503b9a7d064253d36, run 43559074842" |
| PR #55 Card-template (`5d58264e93a2`, integration head) | 2026-11-14 | Merge (86-10 Task 3): the session reported the acceptance check passed and the PR mergeable, and asked whether the owner would merge or instruct the merge | "merge pr 55" (Claude ran the merge under the owner's account at the accepted head; merge commit `7f6b5d4b567c`) |
| PILOT-03 decision 1 (phase-level; not attributable to PR #54 or #55) | 2026-11-14 | PILOT-03 decision 1 (86-08 Task 3): retire routine vibe-check, keep it, or keep it only at a named risk level? | "take all recommendations" — adopting Claude's recommendation as presented: keep vibe-check, scoped to high-risk checkpoints only; stop running it on every "code"-class PR regardless of risk; the D-16 standing items are unchanged. |
| PILOT-03 decision 2 (phase-level; not attributable to PR #54 or #55) | 2026-11-14 | PILOT-03 decision 2 (86-08 Task 3): keep BM/Codex completion as a manual owner check, or extend the acceptance gate (FUT-03)? | "take all recommendations" — adopting Claude's recommendation as presented: keep the manual owner check (option a); the acceptance-gate extension (FUT-03) was not chosen. |
| PILOT-03 decision 3 (phase-level; not attributable to PR #54 or #55) | 2026-11-14 | PILOT-03 decision 3 (86-08 Task 3): since decision 1 changes the current process, should the Phase 86 PR also update the instruction text that puts it into effect (CLAUDE.md "Review-workflow rollout" paragraph; docs/review-checkpoint-record.md), or leave that as a recorded follow-up? | "take all recommendations" — adopting Claude's recommendation as presented: include the instruction-text update in the Phase 86 PR rather than leaving it as a follow-up; noted that this makes the Phase 86 PR an instruction change, classified sensitive. |

## PILOT-03 recommendation and decisions

**Bar check before writing this recommendation.** `git diff
bbabaf8be53a85e60431dbb03d71c837a6b1afb5 HEAD -- 86-PILOT-RECORD.md`, read
line by line for the "## Retirement bar (D-15, fixed before results)"
section only, shows no added or removed line inside it. The bar below is
unchanged since that commit (86-01 Task 1, 2026-10-30 — before any
Refresh-counts code, review or comparison result existed):

> The bar is fixed now, before any comparison result exists. Recommend **retiring routine vibe-check only if, on the fresh comparison and across the pilot, vibe-check found no proven defect (D-09) that BM + Codex missed.** If it found one, recommend keeping routine vibe-check, or keeping it for the risk level where it made the unique catch. The owner makes the final decision; the bar shapes Claude's recommendation only.

### Decision 1: routine vibe-check

The PILOT-02 comparison completed (see "PILOT-02 comparison result" above:
all three reviewers finished independently on H1, and the owner approved
the tally on 2026-10-30). Applying the bar mechanically:

**On the fresh comparison (Refresh-counts PR, H1):** vibe-check's one
confirmed consequential defect (`VC-arch-001` plus `bugs-001`/`imp-001`
merged — the Sonarr ordering warning) was also reached independently by BM
(`bm:03182462100e:WR-01`), which reproduced it with its own probe. Zero
unique catches on the fresh comparison.

**Across the rest of the pilot:**

- PR #48's vibe-check ran only on the final head, after five BM/Codex fix
  rounds had already found and fixed everything (D-08). It reported one
  finding, and that one was a false positive (owner-dismissed, verified via
  a scratch-repo reproduction). Cited here only with that D-08 limitation;
  no unique catch.
- PR #44 and both heads of the Card-template PR (#55): vibe-check found
  nothing beyond unproven test-gap notes that BM or Codex also noted. No
  unique catch.
- **PR #36:** vibe-check — running the full 8-lane deep review as the
  owner-approved fallback because Codex could not complete on this
  195-file diff — found two confirmed consequential defects that neither
  BM's eight review iterations nor Codex's two incomplete attempts on this
  PR ever flagged:
  1. Dependabot's `github-actions` group rewrites the pinned
     `checkout`/`setup-buildx` SHAs, breaking the pinned-SHA no-skip tests
     (named `impact-001` in PR #44's checkpoint comment). Confirmed: fixed
     post-merge in PR #44 (`b0e1ee4`), anchoring the test on a stable
     prefix instead of the exact pinned SHA.
  2. The CI wiring test reads Trivy/actionlint pins from a phase planning
     file that archiving the milestone would delete (named
     `arch-002`/`impact-002`). Confirmed: fixed post-merge in PR #44
     (`3b3713b`), moving the pins to a tracked non-planning file
     (`.github/tool-pins.env`).

  Both are within the D-14 cutoff (found and fixed before the Phase 86 PR
  is accepted). PR #36's own RISK-01 note assessed it **high** risk ("a
  defect in the gate/guard/harness can let an unreviewed head be accepted
  or block every merge").

So the bar's second branch applies: vibe-check found proven defects BM +
Codex missed, once, on a high-risk PR where Codex's own pass could not
complete at all. **My recommendation is to keep vibe-check, scoped to
high-risk checkpoints** (the same trigger RISK-02 already uses), rather
than keep running it on every "code"-class PR regardless of risk, which is
today's standing rule. Reasoning: the one place it added confirmed, unique
value in this pilot was exactly a high-risk, large-diff case where the
paired workflow's Codex half failed to complete; the one place it was
measured head-to-head against a *complete* paired workflow at moderate risk
(the fresh comparison), it cost more time and ran far more subagents (nine
versus two) for a catch both sides already had independently. Keeping it
everywhere, not just at high risk, is also a legitimate reading of the
bar's "or keeping it" branch — it is just not what this pilot's evidence
singles out.

**D-16 standing items (unaffected by this decision either way):**

1. **Bot/fork PRs keep the vibe-check fallback.** Per Phase 85.1's owner
   exception, a bot or fork PR's Codex pass that stays INCOMPLETE/PENDING
   after its retry is still accepted only through the owner-approved
   vibe-check (or another independent reviewer) fallback.
2. **BM still recommends an extra vibe-check whenever a checkpoint's own
   risk assessment comes out high (RISK-02).** This is the same trigger
   this recommendation proposes making the *only* one for "code"-class
   PRs generally, not an additional rule layered on top of a narrower
   routine one.

**In plain terms for the owner.** User impact: nothing here changes what
end users see; it is about how reliably Triggarr's own safety net catches
a broken pin or a future-breaking test before it ships, not about search or
refresh behavior. Risk: dropping vibe-check everywhere removes the only
reviewer that caught real problems on the one PR where the paired workflow
(BM + Codex) is proven not yet reliable — a very large, high-risk diff.
Time: vibe-check cost roughly 4-6 minutes per head in this pilot (sometimes
run twice on the same PR) and ran up to nine model agents versus BM and
Codex's two; narrowing it to high risk keeps that cost only where the
evidence shows it is worth paying. Maintenance: a universal rule is simpler
to state and follow (no risk judgment call); narrowing it to high risk
reuses a judgment the process already makes today for RISK-02, so it adds
no new kind of decision, just removes a second, broader trigger.

### Decision 2: BM/Codex completion check

Options:

- **(a) Keep the manual owner check** — the acceptance checklist
  (`docs/review-checkpoint-record.md`, "Owner acceptance checklist"), which
  already shows the owner BM's and Codex's status, requested versus actual
  depth, and any fallback, before the owner approves.
- **(b) Extend the existing acceptance gate** to mechanically require
  current, exact-head BM/Codex reports before the GitHub `review-acceptance`
  check can pass. If chosen, this is scheduled as **FUT-03**: its own later
  reviewed change to the gate, after this milestone, unless the owner
  explicitly pulls it in now.

Pilot evidence (the five pilot PRs — #48, #36, #44, #54, #55):

- Codex's report was missing, stale, or on the wrong commit at acceptance
  time on **1 of 5** pilot PRs: PR #36, where both Codex attempts stayed
  INCOMPLETE/PENDING because the diff was too large for one pass. The
  manual checklist surfaced that status in plain text, and the owner made
  a separate, explicit decision to approve the vibe-check deep review as
  the recorded fallback before acceptance proceeded ("Fallback via full
  deep review (Recommended)", then "Approve the vibe-check deep-review
  fallback for PR #36 at head 5a97e1f98982"). On the other four PRs (#48,
  #44, #54, #55), Codex was complete on the exact accepted head every
  time.
- The manual check cost one owner decision per PR at minimum (the
  acceptance approval itself) across all five PRs, plus the one extra
  fallback-approval decision on PR #36. It did not silently pass an
  incomplete report on any PR in this pilot — the one incompleteness case
  was caught and handled, not missed.
- **What an extension would prevent:** a human slip — approving a head
  whose Codex report the owner did not actually notice was missing, stale,
  or for the wrong commit. Nothing in this pilot shows that slip actually
  happening.
- **What an extension would not prevent:** it cannot judge whether a review
  was thorough or a fix correct (the blueprint's own limit,
  `docs/bm-greptile-codex-blueprint.md`: "A report-presence check can
  enforce completeness and SHA binding; it cannot prove the reviewer was
  thorough or a fix is correct"), and building it is itself a change to
  acceptance-gate code (`acceptance-readiness.cjs`/`review-acceptance.yml`)
  that would need its own review before being trusted to enforce anything.

**Claude's recommendation:** keep the manual owner check (option a). The
one incompleteness case this pilot produced was caught by the existing
checklist, not missed by it, so there is no pilot evidence yet that a human
slip is actually occurring. Extension would add new gate code to build,
test and maintain, for a failure mode this pilot has not shown happening.
If a future PR's incomplete or stale report ever does slip through the
manual checklist, that incident — not this pilot — is the trigger to
revisit FUT-03.

Owner decision (PILOT-03 decision 1): "take all recommendations" (owner, 2026-11-14), adopting Claude's recommendation as presented: keep vibe-check, but scoped to high-risk checkpoints only — stop running it on every "code"-class PR regardless of risk; the D-16 standing items (bot/fork fallback; RISK-02's high-risk recommendation) stay unchanged either way.

Owner decision (PILOT-03 decision 2): "take all recommendations" (owner, 2026-11-14), adopting Claude's recommendation as presented: keep the manual owner check (option a) as the BM/Codex completion check at acceptance; the acceptance-gate extension (FUT-03) was not chosen — scheduled as FUT-03, not built in Phase 86.

Owner decision (PILOT-03 decision 3): "take all recommendations" (owner, 2026-11-14), adopting Claude's recommendation as presented: the Phase 86 PR will include the update to the vibe-check sentences in CLAUDE.md's "Review-workflow rollout" paragraph and in `docs/review-checkpoint-record.md`, rather than leaving it as a recorded follow-up; noted that this makes the Phase 86 PR an instruction change, classified sensitive.
