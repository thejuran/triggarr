---
phase: 82-ci-tests-what-we-ship
plan: "08"
subsystem: ci-release-safety
tags: [github-actions, ci-wiring, codeql, release-identity, playwright, required-checks]

# Dependency graph
requires:
  - phase: 82-07
    provides: "image-smoke and browser-e2e jobs wired into ci.yml and joined to CI ready / REQUIRED_JOBS"
provides:
  - "docs/ci-negative-demonstrations.md: reproduction recipes and failure policy for the broken-entrypoint and pill-regression demonstrations (D-08, D-09, D-15, D-16, D-32, D-33)"
  - "82-CI-EVIDENCE.md: pre-push /deep-review record (3 passes, APPROVED); three real GitHub CI runs of image-smoke/browser-e2e on PR #33 across the CodeQL fix-and-dismiss cycle; D-34 commit identities reconciled for all three; D-14 budget measured for the first two; a green final-head confirmation with CodeQL passing"
  - "A closed required-check history: CodeQL alerts #13/#14 fixed in 6c8354e; alert #15 (a false-positive on a one-way scrypt digest) dismissed by owner decision 2026-10-21; 0 open code-scanning alerts on the PR head"
affects: ["82-09 (release-safeguard evidence record; this head's required-check set, CI ready and CodeQL, is now green and available as a clean basis)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Required-check stop discipline: a failing required GitHub check (even one outside the plan's own ci.yml changes, and even after a good-faith fix attempt) halts the plan without a further auto-fix attempt or push, per the authorization boundary -- used twice in this plan before the owner's dismissal closed the loop"

key-files:
  created:
    - docs/ci-negative-demonstrations.md
  modified:
    - .planning/phases/82-ci-tests-what-we-ship/82-CI-EVIDENCE.md

key-decisions:
  - "Task 3 stopped twice on required-check (CodeQL) failures rather than attempting a further fix itself: the authorization boundary forbids changing tests/assertions or pushing a fix when a required check fails, and requires recording and stopping instead"
  - "Verified each stage's alert state via the code-scanning API rather than assuming from the diff: confirmed #13/#14 state:fixed after 6c8354e, then confirmed #15 state:dismissed with the exact dismissed_reason/dismissed_comment the owner specified, before declaring the check closed"
  - "Computed the D-14 budget for the first two runs (2m57s, then 2m23s added) against the same pre-phase main baseline and confirmed both are well under the ~5 minute target; the third run is a docs-only head with no new code to re-budget, so only its per-job conclusions were recorded"

requirements-completed: [CISHIP-01, CISHIP-02, CISHIP-03, CISHIP-04]

# Metrics
duration: ~95min (Task 3 across three rounds; Tasks 1-2 completed in a prior session)
completed: 2026-10-21
---

# Phase 82 Plan 08: CI Review Workflow, Push Evidence, and Budget Measurement Summary

**Pushed PR #33 three times across a CodeQL fix-and-dismiss cycle and recorded real GitHub runs each time: all required `ci.yml` jobs green throughout, D-14 budget under 3 minutes added on both code-bearing runs, and the branch ruleset's required `CodeQL` check now passes after the owner fixed the two real plaintext-credential findings (`6c8354e`) and dismissed one scrypt-digest false positive (alert #15, 2026-10-21) -- the PR head's required checks (`CI ready`, `CodeQL`) are green.**

## Performance

- **Duration:** ~95 min (this session, Task 3 across three rounds; Tasks 1-2 were completed in a prior session per the objective)
- **Completed:** 2026-10-21
- **Tasks:** 3 of 3 complete
- **Files modified:** 2 (`82-CI-EVIDENCE.md` and this `82-08-SUMMARY.md`, this session, across all three rounds; `docs/ci-negative-demonstrations.md` was created in Task 1, prior session; the CodeQL fix `6c8354e` was authored and committed by the owner, outside this execution; the alert #15 dismissal was performed by the owner directly via the GitHub API, outside this execution)

## Status: COMPLETE

Tasks 1 and 2 were already complete when this execution started (Task 1 commit `3d28bc0`; Task 2 decision/outcome recorded at `3315a88`, owner chose `/deep-review`, 3 passes, APPROVED). This execution covered Task 3 across three rounds, ending with the PR head's required checks green:

**Round 1:** pushed the branch (`3fa038a..3315a88`), watched the first real GitHub CI run ([39697729420](https://github.com/thejuran/triggarr/actions/runs/39697729420)), collected and reconciled all D-34 commit identities, verified the audited image artifact locally, measured the D-14 budget (2m57s added), and recorded all of it in `82-CI-EVIDENCE.md`. All 8 `ci.yml` jobs succeeded. The branch ruleset's `CodeQL` check failed with two new high-severity `py/clear-text-storage-sensitive-data` alerts (#13, #14) in a Plan 06 e2e probe file. Stopped per the authorization boundary.

**Round 2:** the owner supplied a fix, commit `6c8354e` (verified locally by the owner: 2160 unit tests, ruff clean, capture-guard unit tests 5/5, browser suite green). Verified branch/HEAD/clean tree, pushed (`3315a88..6c8354e`), watched the second real GitHub CI run ([39699460532](https://github.com/thejuran/triggarr/actions/runs/39699460532)), collected and reconciled D-34 identities again, verified the new audited image artifact, measured the budget again (2m23s added), and checked the CodeQL result. All 8 `ci.yml` jobs succeeded again. Alerts #13 and #14 were confirmed `fixed` via the code-scanning API. However, `CodeQL` still failed overall: the fix's own replacement line (writing a salted scrypt fingerprint of the API key to disk) triggered a new alert, #15, on the same rule. Stopped again per the authorization boundary; recorded locally, not pushed.

**Round 3 (this message):** the owner dismissed alert #15 as a false positive via the GitHub API (`dismissed_reason: "false positive"`, with a recorded rationale -- the digest is a one-way salted hash of a disposable per-run test credential, not a recoverable secret). Verified branch/HEAD/clean tree (`f41c065`), recorded the "Alert #15 disposition" subsection in `82-CI-EVIDENCE.md`, committed (`3f8f5f7`), and pushed (`6c8354e..3f8f5f7`, carrying the two prior local-only evidence commits plus this one). Watched the third real GitHub CI run ([39700561470](https://github.com/thejuran/triggarr/actions/runs/39700561470)): all 8 `ci.yml` jobs succeeded, and `CodeQL` itself now passes (consistent with 0 open code-scanning alerts on `refs/pull/33/head`). Recorded a "Final head checks" subsection, then set this plan to complete and committed -- but, per an owner plan change received mid-task, held the resulting docs-only commit locally rather than pushing it, to avoid starting a second `Greptile Review`/CI run while Greptile was still reviewing `3f8f5f7`. It will be pushed with Plan 82-09's next push instead.

## Accomplishments

- **Round 1:** Pushed `ci-review-workflow` to PR #33 (`3fa038a..3315a88`); all 8 `ci.yml` jobs green; D-34 identities reconciled (tested SHA `16faed9...` = merge of head `3315a88...` into base `81eb550...`); image identity verified locally; D-14 budget 2m57s added; discovered CodeQL alerts #13/#14.
- **Round 2:** Pushed `ci-review-workflow` to PR #33 (`3315a88..6c8354e`), carrying the owner's CodeQL fix. All 8 `ci.yml` jobs green again; D-34 identities reconciled again (tested SHA `03c94f2...`); image identity verified; D-14 budget 2m23s added. `browser-e2e`'s credential_pages run exercised the fixed probe path end to end (6 passed, 0 skipped/failed/errored), confirming the new password-via-environment / fingerprint-via-digest-file mechanism works under CI. Confirmed via the code-scanning API that alerts #13/#14 are genuinely `fixed`. Found and recorded new alert #15.
- **Round 3:** Recorded the owner's dismissal of alert #15 (verified via `gh api repos/thejuran/triggarr/code-scanning/alerts/15`: `state: dismissed`, `dismissed_by: thejuran`, `dismissed_reason: "false positive"`, `dismissed_comment` matching the owner's exact text; confirmed 0 open alerts on the ref). Pushed `ci-review-workflow` to PR #33 (`6c8354e..3f8f5f7`). Watched the third CI run: all 8 `ci.yml` jobs green, and `CodeQL` itself now `pass`.
- Across all three rounds, D-34 commit identities (PR head, PR base, tested SHA, image revision label, image ID, image.tar sha256) were collected, reconciled against the `pull_request` merge commit's parents, and verified against the downloaded `audited-image` artifact; the loaded Docker image tag was removed from the local daemon each time.
- The CISHIP-03 rehearsal (matching/mismatched/malformed/missing) and the browser-e2e junit gate (credential_pages >= 6, pages >= 1, zero skips) both passed on every code-bearing run (rounds 1 and 2).

## Task Commits

1. **Task 1: Write the reproduction recipes and failure policy** - `3d28bc0` (docs) -- completed in a prior session
2. **Task 2: Pre-push technical review decision** - `3315a88` (docs) plus fix commits `a59bb3b`, `d05b1b3`, `ea3a973`, `2d85236`, `d3e46ab`, `131a598`, `1133126` -- completed in a prior session
3. **Task 3, round 1: push, first real run, budget** - `1a0fdae` (docs)
4. **Task 3, round 1 continued: plan summary (superseded)** - `399e6ec` (docs)
5. **CodeQL fix (owner-authored, not part of this execution's task scope)** - `6c8354e` (fix)
6. **Task 3, round 2: second real run, fixed/open alert breakdown** - `9df705b` (docs)
7. **Task 3, round 2 continued: fill in own commit hash** - `f41c065` (docs)
8. **Task 3, round 3: record alert #15 dismissal** - `3f8f5f7` (docs)
9. **Task 3, round 3 continued: final head checks, status complete** - *(this commit)*

## Files Created/Modified
- `docs/ci-negative-demonstrations.md` - Reproduction recipes and failure policy (Task 1, prior session; unchanged this session)
- `.planning/phases/82-ci-tests-what-we-ship/82-CI-EVIDENCE.md` - Added "First real GitHub run," "Second GitHub run (after CodeQL fix 6c8354e)" (with its "Alert #15 disposition" subsection), and "Final head checks" sections/subsections: commit identities, reconciliation, CI evidence, review evidence, budget measurement, and the full CodeQL required-check history (two fixed, one dismissed) across all three runs
- `.planning/phases/82-ci-tests-what-we-ship/82-08-SUMMARY.md` - This file, rewritten to cover all three rounds and the final complete status

## Decisions Made
See `key-decisions` in the frontmatter: stopped at each CodeQL result rather than auto-fixing or pushing again (out of this task's scope and explicitly forbidden by the authorization boundary on a required-check failure); verified each stage's alert state via the code-scanning API rather than assuming from intent; confirmed the D-14 budget is not exceeded on either code-bearing run.

## Deviations from Plan

None in the Rule 1-4 sense -- this execution made no code changes itself in any round (Task 3 is push-and-record only; the fix commit `6c8354e` was authored and verified by the owner, and the alert #15 dismissal was performed by the owner directly via the GitHub API, both outside this execution). The CodeQL findings are not deviations this plan introduced; alert #15 was a side effect of the owner's fix for #13/#14, surfaced by this plan's required-check verification rather than by any code this execution wrote, and its dismissal is an explicit, recorded owner decision rather than an auto-fix.

## Assumption Drift (advisory)

- **Found during:** Task 3 round 1, immediately after the first push, while running `gh pr checks 33 --required` per the plan's verify step.
- **Planned assumption:** The plan's acceptance criteria and verify command assume the first real GitHub run would be judged green on the eight `ci.yml` jobs it explicitly lists, with Greptile/Review acceptance/CodeQL treated as background checks whose results are "recorded, not paused on."
- **Actual:** `CodeQL` is itself one of the branch ruleset's four required status checks (confirmed via `repos/thejuran/triggarr/rules/branches/main`), and it failed at the first and second heads for two different reasons before finally passing at the third.
- **Why it matters:** The authorization boundary's stop condition ("if any required job fails ... STOP") is written broadly enough to cover any required check, not only the `ci.yml` ones the plan's acceptance criteria enumerate, and the coordinator's later instructions confirmed this reading explicitly each round. The fix-then-rescan-then-dismiss sequence also shows that resolving a security finding is not always a single step: a fix can introduce a new finding of the same class, and closing the loop can legitimately require a human judgment call (dismissal with rationale) rather than more code.

## Issues Encountered (all resolved)

- **CodeQL required-check failure, round 1 (resolved by the owner's fix):** Alerts #13/#14, `py/clear-text-storage-sensitive-data`, lines 38 and 51 of the probe (the plaintext password-file and raw-API-key-file writes). Confirmed `fixed` at commit `3315a882e2e98d2a3a81752708bb0ec8269e3f88` (i.e., resolved by `6c8354e`).
- **CodeQL required-check failure, round 2 (resolved by owner dismissal):** New alert #15, same rule, `tests/e2e/probes/probe_setup_fails_before_registration.py:53`, flagging the fix's own `Path(digest_file).write_text(secret_fingerprint(api_key, salt_hex))` line. CodeQL's static taint analysis for this query does not recognize `hashlib.scrypt` as a sanitizing transform, so it still treated the one-way salted digest as "sensitive data stored as clear text" even though the digest cannot be reversed to recover the key. The owner dismissed it as a false positive (2026-10-21, `dismissed_reason: "false positive"`, rationale recorded in `82-CI-EVIDENCE.md`'s "Alert #15 disposition" subsection). Verified via the code-scanning API: `state: dismissed`, `dismissed_by: thejuran`, comment text matches exactly; 0 open alerts remain on the PR head.

## User Setup Required

None - no external service configuration required for Task 3. The scratch directory used for local image verification (`/private/tmp/claude-501/-Users-julianamacbook-triggarr/72ccd835-a846-4599-a5e0-d8ba995139ed/scratchpad/ci82`) holds the round-2 `audited-image` artifact files from the last code-bearing run (round 3 made no code changes, so no new image was built or downloaded for it). The loaded Docker image tag was removed from the local daemon after each identity check. No NAS or other image was touched.

## Known Stubs

None - this plan's Task 3 is CI push/evidence/measurement only; no UI, no data flows, no product code (the CodeQL fix `6c8354e` was owner-authored test-only infrastructure, not product code).

## Threat Flags

None beyond this plan's own `<threat_model>` (T-82-36 through T-82-39, T-82-45), all of which this execution's own conduct satisfies across all three rounds: pushed only `ci-review-workflow`, no force push, never `main` (T-82-36); run IDs/attempts/SHAs/log lines copied into `82-CI-EVIDENCE.md` for every run (T-82-37); no merge or owner-acceptance submission attempted, `review-acceptance` environment never touched (T-82-38); evidence contains only SMOKE/rehearsal/result lines and alert metadata, no credentials (T-82-39); all five D-34 identity fields recorded separately with an explicit reconciliation line for each code-bearing run (T-82-45). The owner's fix commit reduces secret-handling risk in the e2e probe (no more plaintext password/API-key files), verified via the code-scanning API rather than by reading the diff alone; the owner's dismissal of alert #15 is a recorded, rationale-bearing decision, not a silent suppression.

## Next Phase Readiness

- **Ready for Plan 09.** The PR head (`3f8f5f7532d2f26266e947a0aca7a8d563c76b67` at the time of this record) has a green required-check set as far as this plan can observe synchronously: all 8 `ci.yml` jobs and `CodeQL` both pass. `Greptile Review` and `Review acceptance` were `pending` at the time of this record -- not paused on, not touched, consistent with D-35(2)/(3) (their results bind to the head SHA whenever they complete; owner acceptance is a separate, later step outside this plan).
- **This final docs-only commit (the "Final head checks" section plus this SUMMARY) is committed locally and deliberately held, not pushed.** All required `ci.yml` jobs and `CodeQL` pass at the current pushed head (`3f8f5f7`), so the push would otherwise be unconditionally authorized -- but the owner changed plan after that: pushing a docs-only commit now would start another `Greptile Review` and CI run while Greptile is still actively reviewing `3f8f5f7`. This commit will be pushed together with Plan 82-09's next push, rather than on its own.
- `main` was not touched; no force push; no `review-acceptance` approval was requested, submitted, or inferred; the `review-acceptance` environment was never written to.

---
*Phase: 82-ci-tests-what-we-ship*
*Completed: 2026-10-21*

## Self-Check: PASSED

- FOUND: docs/ci-negative-demonstrations.md
- FOUND: .planning/phases/82-ci-tests-what-we-ship/82-CI-EVIDENCE.md
- FOUND commit: 3d28bc0 (docs(82-08): add CI negative-demonstration recipes and failure policy)
- FOUND commit: 3315a88 (docs(82-08): record pre-push deep-review decision and outcome)
- FOUND commit: 1a0fdae (docs(82-08): record first GitHub CI run and CodeQL required-check stop)
- FOUND commit: 399e6ec (docs(82-08): add plan summary (partial, CodeQL required-check stop))
- FOUND commit: 6c8354e (fix(82): stop the capture-policy probe writing credentials to disk)
- FOUND commit: 9df705b (docs(82-08): record second GitHub run; CodeQL fix resolves 2, opens 1)
- FOUND commit: f41c065 (docs(82-08): fill in this plan's own commit hash in the summary)
- FOUND commit: 3f8f5f7 (docs(82-08): record owner dismissal of CodeQL alert #15)
