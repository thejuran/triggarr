---
phase: 85-follow-on-ci-improvements-acceptance-usability
plan: "19"
subsystem: ci
tags: [review-evidence, acceptance, backlog, validation, hand-off]

# Dependency graph
requires:
  - phase: 85-follow-on-ci-improvements-acceptance-usability
    plan: "01..18"
    provides: "every requirement/decision artifact this plan verifies and records evidence for (os-scan-gate.cjs, coverage-provenance.cjs, review-register.cjs, codex-fallback.cjs, acceptance-readiness.cjs, the trust boundary, the drift guard, the negative-demonstration prep, etc.)"
provides:
  - "85-REVIEW-EVIDENCE.md: full local verification record on LOCAL_HEAD 4f4783398e912d0a7c4f37197462505382449d5e, a requirement-evidence table, D-07 status, ACCEPT-03 case-by-case proof, six explicitly PENDING GitHub-only items (P1-P6), the phase PR's pre-review classification, a RISK-01/02 note, five disclosures, and a 15-step ordered hand-off"
  - "MAINTENANCE.md: both Phase-85 carry-forward sections replaced with 'Resolved in Phase 85' (named plan + commit per item) and 'Still open after Phase 85' (the two unfolded items, verbatim)"
  - "85-VALIDATION.md: a real per-task verification map (one row per 85-01..85-19 task), the Wave 0 checklist ticked, and 85-19's own P1-P6 added to Manual-Only"
affects: ["the hand-off steps that follow this plan: exact-head coverage, BM/Codex review, push, PR, negative demonstration, acceptance, merge, post-merge evidence"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Verification-method substitution precedent reused a third time: linux/amd64 Docker build on this machine segfaults under QEMU for the uv binary (documented in 85-08, 85-12); this plan substituted linux/arm64 again rather than treating it as a new defect"

key-files:
  created:
    - .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW-EVIDENCE.md
  modified:
    - .planning/backlog/MAINTENANCE.md
    - .planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-VALIDATION.md

key-decisions:
  - "D-07 status recorded honestly as split: delivered now for trusted heads (85-13/85-14/85-17), not yet delivered for untrusted heads (bot/fork PRs) until Phase 85.1 ships the isolated review; the interim rule (CI + untrusted-refused INCOMPLETE + owner-approved D-16 fallback) is in force meanwhile"
  - "MAINTENANCE.md's untrusted-heads item is recorded as 'moved to Phase 85.1', never as resolved, to avoid overclaiming D-07 for bot/fork PRs"
  - "85-VALIDATION.md's nyquist_compliant/wave_0_complete left false with one named gap (85-19-T3 not yet executed when the map was written), rather than set true prospectively before that task actually ran"
  - "Phase PR classification recorded as code with classes_present [code, sensitive, ordinary-docs], per the Mixed-changes rule in docs/review-classification-policy.md -- sensitive content is never diluted by the larger ordinary-docs file count"

requirements-completed: [CIMAINT-01, CIMAINT-02, CIMAINT-03, CIMAINT-04, CIMAINT-05, CIMAINT-06, CIMAINT-07, ACCEPT-01, ACCEPT-02, ACCEPT-03]

# Metrics
duration: ~35min active execution (full pytest ran twice, once plain and once with branch coverage, plus a Docker build and a Trivy-adjacent lockfile check); task commits span 7 minutes (10:45-10:53 ET)
completed: 2026-10-27
---

# Phase 85 Plan 19: Phase Closeout Evidence and Hand-off Summary

**Verified the full local suite and the exact-head coverage procedure on the phase's final local head, wrote the honest evidence record (what's proved locally vs. what only GitHub can still show, with six items explicitly PENDING), classified the phase PR with a RISK-01 note and five disclosures, resolved the folded backlog items, filled in the real per-task validation map, and wrote the 15-step hand-off that the orchestrator performs next — this plan pushed nothing, opened no PR, and submitted no approval.**

## Performance

- **Started:** 2026-10-27 (approx. 10:20 ET, before the first verification command)
- **Completed:** 2026-10-27T14:52:52Z (last commit)
- **Task commits:** 3 (all complete), spanning 10:45:44-10:52:52 ET (~7 min between commits)
- **Total active execution:** ~35 min, dominated by two full pytest runs (85s plain, 93s with `--cov-branch`), a Docker image build, and reading 20+ prior-plan artifacts
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments

- Ran the full local suite on `LOCAL_HEAD 4f4783398e912d0a7c4f37197462505382449d5e`: `uv run pytest tests/ -x -q` (2564 passed, 85.04s), `node --test .github/scripts/*.test.cjs .claude/plugins/planchk-router/test/planchk-router.test.mjs` (326 passed, 0 failed), `uv run ruff check triggarr/ tests/` (clean), `actionlint` (zero findings), and the Docker build + `image_lock_consistency.py` lockfile check (image built on `linux/arm64` after the `linux/amd64` build hit the same documented QEMU segfault as Plans 85-08/85-12; checker reported a match).
- Proved the exact-head coverage procedure (checker B09) end to end on this head: `write-local` and `check` both exited 0 against `LOCAL_HEAD`, with `branches-valid="1364"` confirming branch coverage was actually collected.
- Ran three read-only `gh api` checks (branch-protection ruleset, CodeQL default-setup, `allow_auto_merge`) confirming no GitHub setting needs to change and none was changed.
- Wrote `85-REVIEW-EVIDENCE.md`: a requirement-by-requirement evidence table for CIMAINT-01..07/ACCEPT-01..03, an honest D-07 status split (trusted heads delivered now; untrusted heads deferred to Phase 85.1), the ACCEPT-03 case-by-case proof (3 of 4 cases by permanent test, the mixed case pending the real phase PR), six explicitly PENDING GitHub-only items (P1-P6, each with the exact evidence fields to capture), a pre-review classification JSON, a five-part RISK-01 note (HIGH) plus a RISK-02 vibe-check recommendation, five disclosures, and a 15-step ordered hand-off naming every step "not performed by any plan."
- Replaced both of `MAINTENANCE.md`'s Phase-85 carry-forward sections with "Resolved in Phase 85" (11 items, each naming the plan and commit that closed it) and "Still open after Phase 85" (the two items the owner did not fold in, kept verbatim); recorded the untrusted-heads Codex review as moved to Phase 85.1 rather than resolved.
- Rebuilt `85-VALIDATION.md`'s Per-Task Verification Map into a real one-row-per-task table covering all 85-01 through 85-19 tasks, ticked all five Wave 0 checklist items (all now exist on disk), kept a requirement-level rollup for quick reference, and added 85-19's own P1-P6 to the Manual-Only table.

## Task Commits

1. **Task 1: Full local verification and the evidence record with honest pending items** — `7d08ae4` (docs)
2. **Task 2: Resolve folded backlog items and fill the validation map** — `e6e190c` (docs)
3. **Task 3: PR classification, pre-review RISK-01 note, disclosures and the ordered hand-off** — `8df67d2` (docs)

## Files Created/Modified

- `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW-EVIDENCE.md` — created; the full phase evidence record (see Accomplishments)
- `.planning/backlog/MAINTENANCE.md` — both Phase-85 carry-forward sections replaced with "Resolved in Phase 85" / "Still open after Phase 85"; "Updated" date bumped to 2026-10-27
- `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-VALIDATION.md` — real per-task table, ticked Wave 0 checklist, 85-19 P1-P6 added to Manual-Only; `nyquist_compliant`/`wave_0_complete` left `false` with one named gap

## Decisions Made

- **D-07 status split honestly:** trusted heads (owner-authored PRs, local checkpoints) get the full paired BM + Codex review now, via `verify_trust()` (85-13); untrusted heads (bot/fork PRs) do not yet, by owner decision 2026-10-27 splitting the isolated review into Phase 85.1. No document in this phase claims an untrusted head gets a complete Codex review.
- **MAINTENANCE.md's untrusted-heads carry-forward item is "moved to Phase 85.1," never "resolved"** — this phase delivers the interim rule (CI + INCOMPLETE record + owner-approved fallback), not the isolated review itself.
- **`85-VALIDATION.md`'s `nyquist_compliant`/`wave_0_complete` stayed `false`** rather than being set `true` in anticipation of Task 3 (which had not yet run when Task 2 wrote the file). The one gap is named explicitly in the per-task table (`85-19-T3 ... pending`) rather than silently assumed to resolve itself.
- **Phase PR classification is `code`** with `classes_present: [code, sensitive, ordinary-docs]` — per `docs/review-classification-policy.md`'s Mixed-changes rule, sensitive review/CI-machinery content (workflows, `.github/scripts/*.cjs`, the Codex harness, acceptance/release docs, every `*-PLAN.md` phase/quick plan file) is never diluted toward a lower class just because most of the ~160 changed files are ordinary planning prose.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Docker build substituted `linux/arm64` for the plan's `linux/amd64` after an identical, already-documented QEMU segfault**
- **Found during:** Task 1, the local Docker build + lockfile consistency check step
- **Issue:** `docker build --platform linux/amd64 -t triggarr:p85-19-final .` crashed inside the Dockerfile's `deps` stage the instant the pip-installed `uv==0.12.17` binary executed (`qemu: uncaught target signal 11 (Segmentation fault)`, exit 139) — the identical failure already recorded as a deviation in Plans 85-08 and 85-12's SUMMARY.md on this same machine.
- **Fix:** Built with `docker build --platform linux/arm64 -t triggarr:p85-19-final .` instead (this Mac's native platform); it succeeded, and the lockfile consistency check ran against that image exactly as the `docker` job's steps do, exiting 0 ("Image dependencies match uv.lock").
- **Cost if wrong:** The compared dependency set (`pip freeze` vs. `uv export` of `uv.lock`) is architecture-independent for this image's pure-Python runtime dependencies; if an amd64-specific wheel resolution existed, this substitution could in principle miss a mismatch unique to it. No such risk is identified. The real, non-emulated amd64 answer arrives for free once the phase PR's own CI run executes this step on GitHub's actual x86_64 runners (recorded as PENDING, P1).
- **Files modified:** none — verification-method substitution only; all scratch files were written under `/tmp`, removed after evidence capture, and `git status --porcelain` was empty throughout.
- **Commit:** recorded in `7d08ae4` (no separate code commit needed).

---

**Total deviations:** 1 auto-fixed (1 blocking — local verification platform substitution, the third occurrence of this exact precedent in this phase after Plans 85-08 and 85-12).
**Impact on plan:** No change to any repository file's content. The substitution only affects which CPU architecture ran this plan's one-time local proof.

## Issues Encountered

None beyond the deviation above. All other verification commands (pytest, node --test, ruff, actionlint, the exact-head coverage write/check, and the three read-only `gh api` checks) ran and passed on the first attempt.

## User Setup Required

None — no external service configuration required. This plan is read-only against GitHub (three `gh api` GET calls) and write-only against local `.planning/`/`docs/` files; it made no push, no `gh pr create`, no `gh variable set`, and no `pending_deployments` call, as its own acceptance criteria require.

## Known Stubs

None. This plan writes evidence, backlog and validation documents only; no product code, UI, or data-flow stub was introduced.

## Threat Flags

None — this plan introduces no new network endpoint, auth path, file-access pattern, or schema change. It only records evidence about surfaces other plans already introduced (and already flagged in their own SUMMARY.md files, where applicable).

## Next Phase Readiness

- `85-REVIEW-EVIDENCE.md` is complete and ready for the hand-off sequence it describes: exact-head coverage on H1, BM phase-execution review, the paired Codex pass (expecting `audited_inputs_changed_in_diff` to fire, since this phase changed grader files), a RISK-02 vibe-check decision, the `/deep-review` offer, the end-of-phase push and PR, the negative demonstration (85-18's prepared patch) with the owner's go-ahead, the restore push, a fresh review on the restored head, the register migration, readiness check, owner acceptance, merge, and the post-merge P3/P4/P5 items.
- `MAINTENANCE.md` and `85-VALIDATION.md` both reflect the phase's real, verified state as of this plan; no further Phase 85 plan touches either file.
- The one open item inside this plan's own scope — `85-19-T3`'s status in `85-VALIDATION.md` showing "pending" even though Task 3 has since completed — is a known, documented artifact of write-ordering (Task 2 wrote the file before Task 3 ran) and is not re-opened, per the plan's file-scoping (Task 3's `<files>` list does not include `85-VALIDATION.md`). A later plan or the orchestrator may update it if desired; this plan does not.
- No blockers. Nothing was pushed, no PR was opened, and no acceptance was requested or submitted.

---
*Phase: 85-follow-on-ci-improvements-acceptance-usability*
*Completed: 2026-10-27*

## Self-Check: PASSED

- FOUND: `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW-EVIDENCE.md`
- FOUND: `.planning/backlog/MAINTENANCE.md` (modified, contains "Resolved in Phase 85" and "Still open after Phase 85")
- FOUND: `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-VALIDATION.md` (modified, contains "85-19" rows)
- FOUND commit: `7d08ae4` (docs(85-19): record phase verification and pending GitHub evidence)
- FOUND commit: `e6e190c` (docs(85-19): resolve folded backlog items and complete the validation map (D-15))
- FOUND commit: `8df67d2` (docs(85-19): classify the phase PR and record the risk note, disclosures and hand-off)
