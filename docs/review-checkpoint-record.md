# Review checkpoint record

Active from Phase 83 (v2.13). Owner-checked; GitHub does not enforce BM/Codex records (PILOT-03/FUT-03 decide later).

## Where the record lives

The authoritative record is **one comment per head SHA** on the phase PR (D-10), posted with:

```bash
gh pr comment N --body-file FILE
```

A new head always gets a **new** comment. Earlier heads' comments are never edited or deleted — the per-head audit trail is the point. Additional evidence arriving for a head that already has a comment (for example, a Codex retry completing, or a Greptile check finishing after the comment was first posted) edits **that head's own comment** by its comment id, never a different head's comment and never with `gh pr comment --edit-last`:

```bash
gh api --method PATCH repos/thejuran/triggarr/issues/comments/ID --field body@FILE
```

Before a PR exists (a local checkpoint not yet pushed, or the negative-case demonstration in D-17), the same record is kept in the phase folder's `NN-REVIEW-EVIDENCE.md` under one heading per head SHA, using the same template below.

A **durable copy** of every posted comment is also written into the phase folder alongside the phase-closeout docs, so the record outlives GitHub. Posting a comment costs no push and no Greptile review — it is free to write as often as evidence changes.

Finding dispositions live in this record, not in a GitHub repository variable, so bot thread resolution never erases them. The `REVIEW_DISPOSITIONS` repository variable described in `docs/buildomator-greptile-pilot.md` keeps holding Greptile dispositions only; it is unchanged by this record.

## Template

Each checkpoint record is a single fenced markdown block. It starts with a marker line naming the exact head it covers, so a reader (or a future script) can locate the record for a specific SHA without parsing prose:

```markdown
<!-- review-checkpoint head=FULL_SHA -->

### Commit identities

| Field | Value |
|---|---|
| PR head SHA | `<full 40-char sha>` |
| PR base SHA | `<full 40-char sha>` |
| Tested SHA (if different from PR head) | `<full 40-char sha> or "same as PR head"` |
| Codex inspected head (`inspected_head_sha`) | `<full 40-char sha>` |
| Codex inspected base (`inspected_base_sha`) | `<full 40-char sha>` |

Reconciliation: <one line explaining any difference among the fields above, or "All fields match; no reconciliation needed.">

### Classification

<the docs/review-classification-policy.md per-head JSON record for this head, including `supersedes_head` set to the prior head's SHA when this record reclassifies an earlier one, or `null` for the first record on this PR>

### Risk note (RISK-01)

- **Scope:** <repository/PR, full head/base SHAs, affected behavior, whether this review covers the whole PR or a follow-up diff>
- **Risk:** low | moderate | high — <concrete failure scenarios and likely consequences>
- **Recommended review:** <BM depth: quick/standard/deep, plus specialist focus where useful, plus full-PR vs. targeted follow-up scope>
- **Required evidence:** <targeted regressions, container/browser checks, migration/recovery checks, or human UAT appropriate to the behavior>
- **What this recommendation cannot establish:** <named limits, not a declaration that uncertain behavior is safe>

### Vibe-check (RISK-02)

<when risk is high:>
- **Recommendation:** <explicit vibe-check recommendation with rationale and scope>
- **Owner's decision:** "<the owner's decision, quoted verbatim>"

<when risk is not high:>
- Risk below high: no additional vibe-check recommended.

- **Routine vibe-check status:** <whether routine vibe-check ran for this code change, while the owner keeps that standing rule>

Vibe-check never substitutes for Codex or Greptile, never waives a finding and never reduces required coverage.

### BM review

| Field | Value |
|---|---|
| Path | phase execution \| quick task \| explicit `/bm:code-review` \| review after fixes |
| Requested depth | `quick` \| `standard` \| `deep` |
| Actual depth | `quick` \| `standard` \| `deep` (disclosed even when it differs from requested) |
| Large-scope warning | <the verbatim BM warning text if BM printed one, or "not printed"> |
| Responsible files | `.planning/config.json` key: `workflow.code_review_depth` (or the quick-task hardcode); BM workflow file/step: `<file>:<step>` |
| Report location | `<path to REVIEW.md or equivalent>` |
| Status | complete \| not run \| skipped (`workflow.code_review=false`) |

### Codex

| Field | Value |
|---|---|
| Status | complete \| INCOMPLETE/PENDING, with reasons |
| Attempts | 1 \| 2 |
| Raw output paths | `.jsonl`, `.last.json`, `.status.json` under `.planning/phases/<phase-dir>/codex/<head12>-<label>-a<attempt>` |
| Coverage | <as reported> |
| Exclusions | <as reported> |
| Commands run | <as reported, with exit codes> |
| Limitations | <as reported> |

Findings:

| Qualified ID | Severity | Location | Reproduced / hypothesis | Title |
|---|---|---|---|---|
| `codex:<head12>:a<attempt>:F001` | <severity> | `<file:line>` | reproduced \| hypothesis | <title> |

### Greptile

<ran on this head, with check conclusion> | <not run on this head>

### CI

| Required check | Run ID | Result |
|---|---|---|
| <check name> | <run id> | <result> |

### Dispositions

| Qualified ID | Source | Head | Decision | Evidence | Verified SHA |
|---|---|---|---|---|---|
| `codex:<head12>:a<attempt>:F001` | codex \| bm \| greptile | `<head sha>` | fixed \| false_positive \| nonblocking_debt | <evidence> | `<sha where verified>` |

### Incomplete items

<each incomplete item in plain words, or "None.">
```

## Rules

- Requested depth and actual depth are always both recorded. A BM depth reduction (for example, the >50-file deep-to-standard downgrade, or the quick-task path's hardcoded `quick` depth regardless of `workflow.code_review_depth`) is reported as what actually ran — it is never labelled with the requested depth (REVIEW-05).
- A large high-risk review that BM would downgrade is split into explicit scopes, or gets additional review, rather than being accepted at the downgraded depth unexamined.
- Evidence from an earlier head never counts for a later head (REVIEW-06). A new head needs its own BM review, its own Codex pass, and (when applicable) its own Greptile review and vibe-check.
- The head stays frozen while independent reviews run — no further commits land on that SHA while BM, Codex, Greptile, or vibe-check are still assessing it.
- When BM cannot invoke Codex, or Codex has not yet returned a report, the record shows `Codex: PENDING, requested for FULL_SHA` until a report arrives (REVIEW-03). This is never written as "clean," "skipped and fine," or any other status that could be read as complete.
- The risk note is refreshed whenever a revision changes the SHA or materially changes the risk (RISK-01) — it is not reused unchanged across heads.

## Before any re-review

BM's re-review loop (`/bm:code-review <N> --fix --auto`) does keep history: before each iteration overwrites `REVIEW.md` and `REVIEW-FIX.md`, it copies them to `*.iterN.md` backups (BM 5.0.3, `~/.claude/plugins/cache/gsd-plugin/bm/5.0.3/workflows/code-review-fix.md`, step `auto_iteration_loop`, lines 270-275; see also `docs/bm-review-baseline-2026-10-22.md`). Those backups are named by iteration number, not by head SHA, and BM does not commit them, so they cannot show which head a review covered. The snapshot below is therefore still required (D-08, REVIEW-06): before triggering any re-review, first snapshot the current review by head SHA:

```bash
cp "${PHASE_DIR}/${PADDED_PHASE}-REVIEW.md" \
   "${PHASE_DIR}/${PADDED_PHASE}-REVIEW-${OLD_HEAD_SHA:0:12}.md"
```

The earlier Codex report files need no separate snapshot step — they are already stored per head under `.planning/phases/<phase-dir>/codex/<head12>-<label>-a<attempt>` and are never overwritten by a later head's run.

After the re-review completes, add an "Original vs. refreshed findings" table to the checkpoint record for the new head, so a reader can see which findings from the prior head were confirmed fixed, which were false positives, and which carried forward.

## Triage

When Codex (or BM) reports findings (D-08):

- Claude reproduces plausible defects and classifies each finding as a **confirmed defect**, a **false positive** (with evidence), or **nonblocking debt**.
- Confirmed defects are fixed in **one batched revision**, which then gets fresh tests, a fresh BM review, and a fresh Codex review on the new head — never a partial fix pushed ahead of the others.
- There is no automatic cross-agent fix loop beyond this one batched revision and its one fresh round of reviews.
- The owner sees the original Codex report plus the dispositions before acceptance — dispositions never replace the original report in what the owner is shown.

## Owner acceptance checklist

At acceptance time, the owner gets one checklist message in the CLI:

```markdown
Repository: thejuran/triggarr
PR: #<N>
Full head SHA: <full 40-char sha>
Full base SHA: <full 40-char sha>

Review status on this head:
- BM: <status, requested vs. actual depth>
- Codex: <status, from docs/codex-adversarial-review-contract.md Invocation step 6 / tests/codex_report_status.py>
- Greptile: <status, or "did not run on this head">
- Vibe-check: <status, or "not selected for this checkpoint">
- CI: <status>

Findings and dispositions:
- <qualified ID>: <decision> — <evidence>
(repeat per finding, or "No findings.")

Incomplete items:
- <each incomplete item in plain words, or "None.">
```

This checklist is the manual BM/Codex completion check (D-12). Approval itself still follows [owner CLI acceptance](owner-cli-acceptance.md) unchanged — this checklist only assembles the evidence that procedure's step 1 and step 4 require; it adds no new authorization path.
