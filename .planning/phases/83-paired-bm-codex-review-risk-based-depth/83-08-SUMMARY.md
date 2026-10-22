---
phase: 83-paired-bm-codex-review-risk-based-depth
plan: "08"
subsystem: review-workflow
tags: [explicit-code-review, codex-review, review-evidence, triage, negative-demonstrations, checker-hardening]

# Dependency graph
requires:
  - phase: 83-paired-bm-codex-review-risk-based-depth (Plan 06)
    provides: "docs/review-checkpoint-record.md's template, docs/review-classification-policy.md, docs/codex-adversarial-review-contract.md"
  - phase: 83-paired-bm-codex-review-risk-based-depth (Plan 07)
    provides: "First real-work fill of the checkpoint-record template (head a7995baf187e); two confirmed defects already queued for Plan 09 (WR-01/WR-02 on the dashboard card)"
provides:
  - "83-REVIEW.md: BM's explicit /bm:code-review 83 run at standard depth (no --depth flag), 12 files, 13 findings (2 critical, 5 warning, 6 info) plus 2 set-aside items"
  - "codex/d501a68316b2-explicit-a1.{jsonl,last.json,status.json}: the paired Codex pass's raw output on the same frozen head, 2 reproduced findings, all 12 REVIEW-04 fields present"
  - "83-REVIEW-EVIDENCE.md: new section 'Explicit /bm:code-review path -- head d501a68316b2' with full triage of 17 findings (13 BM + 2 Codex + 2 set-aside), including two owner rulings (SA-01, WR-04) and two cross-head duplicate findings identified"
  - "83-DEMONSTRATIONS.md: six local negative-case recipes proving a missing, twice-timed-out, stale, wrong-commit, or unparseable Codex report is always reported incomplete, never clean -- Recipe 2 is a real codex exec invocation under a 5s timeout, not a simulated one"
affects: [83-09 (the batched fix now covers the checker's generic schema-validation gap and CLI crash paths, three documentation gaps, the classification policy's apply-both ruling, and the dashboard-card wording ruling, in addition to the WR-01/WR-02 card fix already queued from Plan 07), 83-10 (PR classification work for the full phase diff can reuse this record's sensitive+code classification JSON as a worked example)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cross-head duplicate detection: a finding re-raised by a later BM run against code unchanged since an earlier head's own triage is cross-referenced to that earlier disposition, not re-triaged as new (bm:d501a68316b2:IN-01/IN-02 -> bm:a7995baf187e:WR-01/WR-02, confirmed via an empty git log between the two heads for the affected files)"
    - "Real-contract failure-rule demonstration: Recipe 2 substitutes timeout 5 for the contract's timeout 1800 inside the actual Invocation steps (real detached worktree, real codex exec, real checker), rather than fabricating a timeout result"

key-files:
  created:
    - .planning/phases/83-paired-bm-codex-review-risk-based-depth/83-DEMONSTRATIONS.md
  modified:
    - .planning/phases/83-paired-bm-codex-review-risk-based-depth/83-REVIEW-EVIDENCE.md
    - .planning/phases/83-paired-bm-codex-review-risk-based-depth/83-REVIEW.md (written by BM's reviewer before this session; committed by this plan)
    - .planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/d501a68316b2-explicit-a1.jsonl (written by the orchestrator's Codex invocation before this session; committed by this plan)
    - .planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/d501a68316b2-explicit-a1.last.json
    - .planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/d501a68316b2-explicit-a1.status.json

key-decisions:
  - "Classification for head d501a68316b2 recorded as 'sensitive' with classes_present [sensitive, code], applying the owner's 2026-10-22 WR-04 ruling ('Apply both') in practice ahead of Plan 09's policy-wording fix landing"
  - "bm:d501a68316b2:IN-01 and IN-02 cross-referenced as duplicates of the already-confirmed bm:a7995baf187e:WR-01/WR-02 (byte-identical code since that head), not re-triaged as new findings"
  - "bm:d501a68316b2:SA-02 (files outside BM's scope) resolved nonblocking for this head because Codex's own commands_run independently covered CLAUDE.md and docs/owner-cli-acceptance.md; BM's underlying SUMMARY.md-tier scoping quirk is recorded, not fixed, in this plan"
  - "Recipe 4's constructed mutation used the literal git rev-parse HEAD~1 value (which, one commit after Task 1's own checkpoint commit, happens to equal the previously-reviewed head) against the Task-2-time actual current head as --expected-head/--current-head, producing a genuine wrong-commit mismatch rather than a no-op"

patterns-established:
  - "Checkpoint-record Dispositions table entries for owner-ruled items quote the verbatim ruling inline in the Decision column (not just 'confirmed_defect'), so the ruling travels with the finding into Plan 09 without a second lookup"

requirements-completed: [REVIEW-02, REVIEW-03, REVIEW-04, REVIEW-05, RISK-01]

# Metrics
duration: ~50min (this session: Task 1 triage/reproduction/evidence-write/commit, Task 2 six demonstrations incl. a real timed-out codex exec/commit, full suite + ruff, summary)
completed: 2026-10-22
---

# Phase 83 Plan 08: Explicit Review Checkpoint, Full Triage, and Negative Demonstrations Summary

**Triaged all 17 findings from BM's explicit `/bm:code-review 83` run plus its paired Codex pass on head `d501a68316b2` (reproducing 15 of them directly, cross-confirming BM's checker finding with Codex's own, and cross-referencing two as duplicates of Plan 07's already-confirmed defects), then demonstrated six local negative cases — including a real `codex exec` killed twice by a 5-second timeout — proving an incomplete Codex report is never shown as clean.**

## Performance

- **Duration:** ~50 min (this session)
- **Completed:** 2026-10-22
- **Tasks:** 2 (Task 1 remainder: triage + evidence record + commit; Task 2: six negative demonstrations + commit)
- **Files modified/created this session:** 2 phase-level docs modified/extended (`83-REVIEW-EVIDENCE.md`, plus committing the orchestrator's pre-written `83-REVIEW.md` and 3 Codex raw-output files), 1 new file (`83-DEMONSTRATIONS.md`)

## Accomplishments

- **Task 1 (remainder):** Reproduced 15 of the 17 findings directly against the real code — the checker's own `assess_report`/CLI for the 11 checker-level findings (CR-01, CR-02, WR-01, WR-02, IN-03 [by read], IN-04, IN-05, plus Codex F001), the real `gh api` command for F002, and a direct code read confirming WR-03, WR-04, WR-05, IN-06, and SA-01's and SA-02's underlying claims. Identified and recorded the cross-confirmation `bm:CR-01 ≙ codex:F001` (same root cause, same file/lines) and two cross-head duplicates (`bm:d501a68316b2:IN-01/IN-02` are the same unchanged-code findings as the already-confirmed `bm:a7995baf187e:WR-01/WR-02` from Plan 07). Applied the two owner rulings received mid-task (SA-01 "failure wording on red cards"; WR-04 "apply both" review classes) directly into the Dispositions table. Appended the full "Explicit /bm:code-review path — head d501a68316b2" section to `83-REVIEW-EVIDENCE.md` per the checkpoint-record template, including the REVIEW-04 field-completeness table (all 12 top-level schema fields present, with counts), the BM scoping quirk (SUMMARY.md-tier scope misses `CLAUDE.md`), and the craft-skill non-insertion record. Ran `gitleaks detect --no-git --source` on `codex/` (no leaks) before `git add -f`-ing `83-REVIEW.md`, the evidence file, and the three Codex raw-output files.
- **Task 2:** Built all six negative-case recipes specified in the plan. Recipe 2 ran the real contract Invocation steps (detached worktree, `timeout 5 codex exec --sandbox read-only --ephemeral ...`, the real checker) twice, confirming both attempts were killed at ~5.03s (exit 124) with no `.last.json` written either time — a genuine, not simulated, demonstration of the failure rule's two-attempt exhaustion. Recipes 1, 3, 4, 5 ran the real checker against a missing path, Plan 07's real stale report, a constructed wrong-head copy of Task 1's report, and a byte-truncated copy of Task 1's report, respectively; all five checker-driven recipes (1, 3, 4, 5, plus both attempts of 2) returned `status: incomplete` with exit code 1 and a reason matching the case. Recipe 6 recorded the static `Codex: PENDING, requested for <full HEAD SHA>` evidence-record line and why it blocks the owner acceptance checklist. Confirmed `git ls-remote --heads origin paired-review` printed empty output both before and after Task 2 (no push), removed both demonstration worktrees with `git worktree remove --force`, and deleted every scratch file afterward.
- Ran `uv run pytest tests/ -x -q` (2215 passed) and `uv run ruff check triggarr/ tests/` (all checks passed) at the final head.

## Task Commits

1. **Task 1: Triage, explicit-path evidence record, commit** — `5d9a96f` (docs)
2. **Task 2: Six local negative demonstrations, commit** — `9debb8e` (docs)

**Plan metadata:** this SUMMARY.md commit (docs: complete plan)

## Files Created/Modified

- `.planning/phases/83-paired-bm-codex-review-risk-based-depth/83-REVIEW.md` — BM's explicit-review report (written by BM before this session; committed here)
- `.planning/phases/83-paired-bm-codex-review-risk-based-depth/83-REVIEW-EVIDENCE.md` — new "Explicit /bm:code-review path — head d501a68316b2" section: commit identities, classification, RISK-01/RISK-02, BM review table, Codex table/findings, REVIEW-04 field-completeness table, 17-row Dispositions table, Incomplete items
- `.planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/d501a68316b2-explicit-a1.jsonl` — full unedited Codex event stream (written by the orchestrator before this session; committed here)
- `.planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/d501a68316b2-explicit-a1.last.json` — Codex's final structured report (2 findings, all 12 schema fields present)
- `.planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/d501a68316b2-explicit-a1.status.json` — the checker's assessment of that report
- `.planning/phases/83-paired-bm-codex-review-risk-based-depth/83-DEMONSTRATIONS.md` — six negative-case recipes, none complete

## Decisions Made

- Recorded this head's classification as `sensitive` with `classes_present: [sensitive, code]`, applying the owner's WR-04 "Apply both" ruling in this record even though the policy document's own wording fix is deferred to Plan 09 — the ruling governs required review today, not only after the doc is edited.
- Cross-referenced `bm:d501a68316b2:IN-01`/`IN-02` to the already-confirmed `bm:a7995baf187e:WR-01`/`WR-02` from Plan 07 rather than triaging them as new findings, after confirming `git log a7995baf187e0e96c3f8152212060cedfc7fd921..d501a68316b2c3a032634741f8c73d373870e9f2 -- triggarr/templates/partials/cycle_grade.html triggarr/search/outcome.py` is empty (the code genuinely has not changed between the two heads).
- Resolved SA-02 (files outside BM's 12-file scope) as nonblocking for this specific head because Codex's own `commands_run` independently read and diffed both `CLAUDE.md` and `docs/owner-cli-acceptance.md` — the scope gap is real in BM's own file-listing step (recorded as a "scoping quirk," not fixed here) but did not leave this head's overall review substance missing those files.
- For Recipe 4, used the literal `git rev-parse HEAD~1` value from the plan's own instruction, evaluated at Task 2 time — this happens to resolve to the exact head Task 1's report was originally about (one commit, Task 1's own checkpoint commit, separates them) — and paired it with `--expected-head`/`--current-head` set to the Task-2-time actual current head, which produces a genuine "wrong commit" mismatch rather than a no-op mutation. See Assumption Drift below.

## Deviations from Plan

None — plan executed exactly as written. All 15 reproductions were read-only, using disposable scratch scripts and files in the session scratchpad (never committed, never touching `triggarr/` or `tests/`); the two detached worktrees created for Recipe 2 were each removed immediately after use; no source or test file was edited; no confirmed defect was fixed in this plan, per its explicit "no fixes in this plan" instruction (Task 1) and the negative-demonstration-only scope of Task 2.

## Assumption Drift (advisory)

- **Assumption drift:** "`git rev-parse HEAD~1` yields some arbitrary different commit for Recipe 4's mutation" → "at Task 2 time, `HEAD~1` resolves exactly to the head Task 1's own Codex report was about, because only one commit (Task 1's own checkpoint-record commit) separates them" (why: Task 1 commits its own evidence-record doc on top of the head it just reviewed, so "current head minus one" lands precisely back on that reviewed head — not a coincidence specific to this session, but a structural consequence of the plan's own task ordering). Resolved by keeping `--expected-head`/`--current-head` at the Task-2-time actual current head (per the explicit instruction to use the current HEAD at Task 2 time) rather than reusing the original report's own expected values, which is what makes the mutation a genuine "wrong commit" case instead of a no-op. **Cost if wrong:** if a future reader re-runs this recipe's literal command without re-deriving which head counts as "true," they could reproduce a no-op (mutated value equals expected value) and wrongly conclude the wrong-commit path is not exercised; this record spells out both resolved SHAs explicitly to prevent that.

## Issues Encountered

- A pre-existing `.claude/worktrees/review-*` set of detached worktrees (seven entries) was present in `git worktree list` throughout this session, unrelated to and not created by this plan. Verified they were untouched before and after Task 2's own `recipe2-wt-a1`/`recipe2-wt-a2` worktrees were created and removed.
- Codex's own Recipe-2 attempts produced partial `.jsonl` event streams (923 and 631 bytes) containing only startup/configuration-warning events before being killed by `timeout 5` — confirmed no partial `.last.json` was ever written in either attempt, so the checker's "missing report" reason (not "unparseable") is the correct, reproduced outcome for both.

## Verification Results

- `python3 -c "...len(json.load(...))..."` on `d501a68316b2-explicit-a1.last.json` → `12` (all REVIEW-04 top-level schema fields present)
- `gitleaks detect --no-git --source .planning/phases/83-paired-bm-codex-review-risk-based-depth/codex` → "no leaks found"
- `grep -c "^## Explicit /bm:code-review path" 83-REVIEW-EVIDENCE.md` → `1`
- CR-01 reproduction (9 mutated-field cases via `assess_report`) → all 9 returned `status=complete` with the exact counts/qualified-IDs the review claimed
- CR-02 reproduction (`id: 7`) → `finding_count=2, qualified_ids=('codex:aaaaaaaaaaaa:a1:F002',)` (1 ID for 2 findings)
- WR-01 reproduction (verdict/findings mismatch, both directions) → both `status=complete, reasons=()`
- WR-02 reproduction (non-UTF-8 file, directory path) → both raised an uncaught traceback, exit code `1`, no JSON payload
- IN-04 reproduction (`--attempt 0`, `--attempt -3`) → both accepted, `status=complete`
- IN-05 reproduction (`line_start: true`, whitespace-only `hypothesis`) → both passed their respective checks
- F002 reproduction (`gh api --method PATCH ... --field body@FILE`) → exited `1`, `invalid key: "body@FILE"`
- `grep -c "^### Recipe" 83-DEMONSTRATIONS.md` → `6`
- `grep -c '"status": "complete"' 83-DEMONSTRATIONS.md` → `0`
- `grep -vi "never .*clean\|not .*clean" 83-DEMONSTRATIONS.md | grep -ci "clean review"` → `0`
- `git ls-remote --heads origin paired-review` → empty, both before and after Task 2
- Recipe 2 attempt 1 and attempt 2: both `timeout 5 codex exec ...` → exit `124`, wall-clock ~5.03s each, no `.last.json` written; checker on each → `{"status": "incomplete", "reasons": ["codex exited 124", "missing report"], ...}`, exit `1`
- `git worktree list` after Task 2 → neither `recipe2-wt-a1` nor `recipe2-wt-a2` present
- `git diff --diff-filter=D --name-only HEAD~1 HEAD` after both Task 1 and Task 2 commits → empty both times (no unexpected deletions)
- `uv run pytest tests/ -x -q` → `2215 passed, 38 warnings in 68.91s`
- `uv run ruff check triggarr/ tests/` → "All checks passed!"

## Threat Model Disposition

All three plan threats mitigated as specified:
- **T-83-27** (Repudiation: constructed negative inputs mistaken for real ones): mitigated — every constructed input (missing-report path, wrong-head copy, truncated copy, the two timeout-forced `codex exec` attempts) stayed in the session scratchpad, labelled constructed throughout `83-DEMONSTRATIONS.md`, and was deleted after its output was captured verbatim; only the checker's real JSON output was recorded, never a constructed report itself.
- **T-83-28** (Tampering: a deliberately broken push): mitigated — `git ls-remote --heads origin paired-review` printed empty output both before Task 2 began and again after all six recipes; no push was performed.
- **T-83-29** (Information disclosure: raw Codex transcripts): mitigated — `gitleaks detect --no-git --source` on `codex/` reported no leaks before `git add -f`.

No new threat surface (network endpoints, auth paths, file access patterns, or schema changes at trust boundaries) was introduced by this plan — it is a triage, an evidence-record write, a negative-demonstration record, and raw-output storage; no application code or test file was touched.

## Known Stubs

None. This plan's deliverables are review-evidence records and a negative-demonstration record; no UI or data-wiring code was created or modified.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 09's batched fix now has a consolidated list spanning both reviewed heads: the dashboard-card structural fix (WR-01/WR-02 from Plan 07, reconfirmed here as IN-01/IN-02, plus the SA-01 owner-ruled wording change — all three touch `cycle_view()`/`cycle_grade.html` and should be fixed together), the checker's generic schema/type-validation gap (CR-01, CR-02, WR-01[checker], IN-03, IN-04, IN-05, cross-confirmed by Codex F001), the checker CLI's crash-instead-of-report-reason path (WR-02[checker]), three documentation accuracy/gap fixes (WR-03, WR-05, IN-06), the classification-policy wording fix applying the owner's WR-04 "Apply both" ruling, and the `gh api` command syntax fix (Codex F002). All carry `N/A (not fixed in this plan)` Verified SHA in the Dispositions table — none were fixed here, per the plan's explicit instruction.
- Per the triage procedure, Plan 09 fixes all of the above in one batched revision, then gets fresh tests, a fresh BM review, and a fresh Codex pass on the new head (REVIEW-06) — not a partial fix.
- Plan 10's PR classification work can cite this record's `sensitive`+`code` classification JSON for head `d501a68316b2` as a worked example of the owner's "Apply both" ruling in practice, alongside Plan 07's `code`-only example for a narrower sub-diff.
- No blockers. `.planning/config.json`, `.planning/STATE.md`, `.planning/ROADMAP.md`, and `.planning/REQUIREMENTS.md` were not touched by this session, per this plan's explicit scope (SUMMARY.md only) and the standing rule against running `bm-sdk` STATE/ROADMAP writers from this execution context.

---
*Phase: 83-paired-bm-codex-review-risk-based-depth*
*Completed: 2026-10-22*

## Self-Check: PASSED

- FOUND: .planning/phases/83-paired-bm-codex-review-risk-based-depth/83-REVIEW.md
- FOUND: .planning/phases/83-paired-bm-codex-review-risk-based-depth/83-REVIEW-EVIDENCE.md
- FOUND: .planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/d501a68316b2-explicit-a1.jsonl
- FOUND: .planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/d501a68316b2-explicit-a1.last.json
- FOUND: .planning/phases/83-paired-bm-codex-review-risk-based-depth/codex/d501a68316b2-explicit-a1.status.json
- FOUND: .planning/phases/83-paired-bm-codex-review-risk-based-depth/83-DEMONSTRATIONS.md
- FOUND commit `5d9a96f` (Task 1)
- FOUND commit `9debb8e` (Task 2)
