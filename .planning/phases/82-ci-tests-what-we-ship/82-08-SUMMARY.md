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
  - "82-CI-EVIDENCE.md: pre-push /deep-review record (3 passes, APPROVED), two real GitHub CI runs of image-smoke/browser-e2e on PR #33 (before and after a CodeQL fix), D-34 commit identities reconciled for both, and the D-14 budget measured for both"
  - "A recorded, still-open required-check stop: CodeQL's original two alerts are fixed, but the fix commit introduces one new high-severity clear-text-storage alert on its own replacement write"
affects: ["82-09 (release-safeguard evidence record; inherits the open CodeQL finding as a blocker to clear before any final-head owner acceptance)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Required-check stop discipline: a failing required GitHub check (even one outside the plan's own ci.yml changes, and even after a good-faith fix attempt) halts the plan without a further auto-fix attempt or push, per the authorization boundary"

key-files:
  created:
    - docs/ci-negative-demonstrations.md
  modified:
    - .planning/phases/82-ci-tests-what-we-ship/82-CI-EVIDENCE.md

key-decisions:
  - "Task 3 stopped twice, both times on required-check (CodeQL) failures rather than attempting a further fix itself: the authorization boundary forbids changing tests/assertions or pushing a fix when a required check fails, and requires recording and stopping instead"
  - "Verified the owner's fix commit (6c8354e) resolved the original two alerts (#13/#14 both confirmed state: fixed via the code-scanning API) before confirming CodeQL still fails overall, so the partial improvement is documented accurately rather than reported as a wash"
  - "Computed the D-14 budget for both runs (2m57s added, then 2m23s added) against the same pre-phase main baseline and confirmed both are well under the ~5 minute target, so no budget-exceeded stop applies independently of the CodeQL stop"

requirements-completed: []

# Metrics
duration: ~70min (Task 3 portion across both rounds; Tasks 1-2 completed in a prior session)
completed: 2026-10-21
---

# Phase 82 Plan 08: CI Review Workflow, Push Evidence, and Budget Measurement Summary

**Pushed PR #33 twice and recorded two real GitHub runs of image-smoke/browser-e2e (all required ci.yml jobs green both times, rehearsal and junit evidence captured, D-14 budget under 3 minutes added both times) -- stopped both times per the plan's authorization boundary because the branch ruleset's required CodeQL check keeps failing: the owner's fix resolved the original two alerts but introduced one new high-severity alert on its own replacement code.**

## Performance

- **Duration:** ~70 min (this session, Task 3 across both rounds; Tasks 1-2 were completed in a prior session per the objective)
- **Completed:** 2026-10-21
- **Tasks:** 2 of 3 complete (Task 1 and Task 2 done previously; Task 3 reached its push/evidence/budget goals twice but has not yet reached a fully green required-check set)
- **Files modified:** 2 (`82-CI-EVIDENCE.md` and this `82-08-SUMMARY.md`, this session; `docs/ci-negative-demonstrations.md` was created in Task 1, prior session; the CodeQL fix itself, `6c8354e`, was authored and committed by the owner, outside this execution)

## Status: PARTIAL (stopped at a required-check failure, not a plan checkpoint)

Tasks 1 and 2 were already complete when this execution started (Task 1 commit `3d28bc0`; Task 2 decision/outcome recorded at `3315a88`, owner chose `/deep-review`, 3 passes, APPROVED). This execution covered Task 3 in two rounds:

**Round 1:** pushed the branch (`3fa038a..3315a88`), watched the first real GitHub CI run ([39697729420](https://github.com/thejuran/triggarr/actions/runs/39697729420)), collected and reconciled all D-34 commit identities, verified the audited image artifact locally, measured the D-14 budget, and recorded all of it in `82-CI-EVIDENCE.md`. All 8 `ci.yml` jobs succeeded. The branch ruleset's `CodeQL` check failed with two new high-severity `py/clear-text-storage-sensitive-data` alerts (#13, #14) in a Plan 06 e2e probe file. Stopped per the authorization boundary.

**Round 2 (this message):** the owner supplied a fix, commit `6c8354e` (verified locally by the owner: 2160 unit tests, ruff clean, capture-guard unit tests 5/5, browser suite green), on top of this plan's two local-only evidence commits. Verified branch/HEAD/clean tree, pushed (`3315a88..6c8354e`), watched the second real GitHub CI run ([39699460532](https://github.com/thejuran/triggarr/actions/runs/39699460532)), collected and reconciled D-34 identities again, verified the new audited image artifact, measured the budget again, and checked the CodeQL result. All 8 `ci.yml` jobs succeeded again. Alerts #13 and #14 are confirmed `fixed` (via `most_recent_instance.state` on the code-scanning API). However, `CodeQL` still fails overall: the fix's own replacement line (writing a salted scrypt fingerprint of the API key to disk) triggered a **new** alert, #15, on the same rule. Per the authorization boundary and the coordinator's explicit instruction ("if any required job or CodeQL fails ... do NOT push a fix, and STOP"), this execution recorded the new finding and stopped again rather than attempting a further fix or a third push.

## Accomplishments

- **Round 1:** Pushed `ci-review-workflow` to PR #33 (`3fa038a..3315a88`); all 8 `ci.yml` jobs green (`test` 2m6s, `lint` 10s, `secrets` 9s, `dependencies` 10s, `docker` 1m6s, `image-smoke` 30s, `browser-e2e` 1m24s, `CI ready` 3s); D-34 identities reconciled (tested SHA `16faed9...` = merge of head `3315a88...` into base `81eb550...`); image identity verified locally (ID `sha256:84783d0b...`, revision label matches tested SHA); D-14 budget 2m57s added (well under 5 min); discovered CodeQL alerts #13/#14.
- **Round 2:** Verified `git rev-parse HEAD` = `6c8354e932292bc5fdb6609388d32a673ba6070f` on a clean tree before pushing. Pushed `ci-review-workflow` to PR #33 (`3315a88..6c8354e`), carrying the two local evidence commits plus the owner's fix. Watched run [39699460532](https://github.com/thejuran/triggarr/actions/runs/39699460532): all 8 `ci.yml` jobs green again (`test` 2m8s, `lint` 8s, `secrets` 9s, `dependencies` 12s, `docker` 35s, `image-smoke` 38s, `browser-e2e` 1m22s, `CI ready` 3s). D-34 identities reconciled again (tested SHA `03c94f2...` = merge of head `6c8354e...` into base `81eb550...`); image identity verified locally (ID `sha256:f0a89c53...`, revision label matches tested SHA, loaded tag removed afterward). D-14 budget 2m23s added (well under 5 min). `browser-e2e`'s credential_pages run now exercises the fixed probe path end to end (6 passed, 0 skipped/failed/errored), confirming the new password-via-environment / fingerprint-via-digest-file mechanism works under CI, not just locally.
- Confirmed via the code-scanning API that alerts #13 and #14 are genuinely `fixed` (not just superseded or renumbered) at commit `3315a882e2e98d2a3a81752708bb0ec8269e3f88` (the commit immediately before `6c8354e` landed).
- Found and recorded the new alert (#15): `tests/e2e/probes/probe_setup_fails_before_registration.py:53`, the fix's own `Path(digest_file).write_text(secret_fingerprint(api_key, salt_hex))` line -- CodeQL's taint tracking still treats a `hashlib.scrypt`-derived digest as tainted by the original `api_key` source, since it does not recognize that hash as a sanitizer for this query.

## Task Commits

1. **Task 1: Write the reproduction recipes and failure policy** - `3d28bc0` (docs) -- completed in a prior session
2. **Task 2: Pre-push technical review decision** - `3315a88` (docs; the deep-review decision/outcome record) plus the review's own fix commits `a59bb3b`, `d05b1b3`, `ea3a973`, `2d85236`, `d3e46ab`, `131a598`, `1133126` -- completed in a prior session
3. **Task 3, round 1: Push to PR #33, record the first real run, measure the budget** - `1a0fdae` (docs; this session)
4. **Task 3, round 1 continued: plan summary** - `399e6ec` (docs; this session, superseded by this file's current content)
5. **CodeQL fix (owner-authored, not part of this execution's task scope)** - `6c8354e` (fix)
6. **Task 3, round 2: record the second real run, CodeQL resolution status, and this summary** - `9df705b` (docs)

## Files Created/Modified
- `docs/ci-negative-demonstrations.md` - Reproduction recipes and failure policy (Task 1, prior session; unchanged this session)
- `.planning/phases/82-ci-tests-what-we-ship/82-CI-EVIDENCE.md` - Added "First real GitHub run" (round 1) and "Second GitHub run (after CodeQL fix 6c8354e)" sections: commit identities, reconciliation, CI evidence (tested SHA), review evidence (PR head), budget measurement, and the CodeQL required-check status for both runs, including the fixed/open alert breakdown for round 2
- `.planning/phases/82-ci-tests-what-we-ship/82-08-SUMMARY.md` - This file, rewritten to cover both rounds

## Decisions Made
See `key-decisions` in the frontmatter: stopped at each CodeQL result rather than auto-fixing or pushing again (out of this task's scope and explicitly forbidden by the authorization boundary on a required-check failure); verified the fixed/open alert breakdown precisely rather than treating "CodeQL still fails" as a total non-improvement; confirmed the D-14 budget is not exceeded on either run so no separate budget stop applies.

## Deviations from Plan

None in the Rule 1-4 sense -- this execution made no code changes itself in either round (Task 3 is push-and-record only; the fix commit `6c8354e` was authored and verified by the owner, outside this execution). The CodeQL findings are not deviations this plan introduced; alert #15 is a side effect of the owner's fix for #13/#14, surfaced by this plan's required-check verification rather than by any code this execution wrote.

## Assumption Drift (advisory)

- **Found during:** Task 3 round 1, immediately after the first push, while running `gh pr checks 33 --required` per the plan's verify step.
- **Planned assumption:** The plan's acceptance criteria and verify command assume the first real GitHub run would be judged green on the eight `ci.yml` jobs it explicitly lists, with Greptile/Review acceptance/CodeQL treated as background checks whose results are "recorded, not paused on."
- **Actual:** `CodeQL` is itself one of the branch ruleset's four required status checks (confirmed via `repos/thejuran/triggarr/rules/branches/main`), and it failed at both the first and second head, each time for a different reason.
- **Why it matters:** The authorization boundary's stop condition ("if any required job fails ... STOP") is written broadly enough to cover any required check, not only the `ci.yml` ones the plan's acceptance criteria enumerate, and the coordinator's round-2 instructions confirmed this reading explicitly ("if any required job or CodeQL fails ... STOP"). Round 2 additionally shows that a security-finding fix is not automatically a clean resolution -- the replacement code must itself be re-scanned, not just assumed clean because it addresses the original report's intent.

## Issues Encountered

- **CodeQL required-check failure, round 1 (resolved by the owner's fix, see below):** Alerts #13/#14, `py/clear-text-storage-sensitive-data`, lines 38 and 51 of the probe (the plaintext password-file and raw-API-key-file writes). Confirmed `fixed` at commit `3315a882e2e98d2a3a81752708bb0ec8269e3f88` (i.e., resolved by `6c8354e`).
- **CodeQL required-check failure, round 2 (still open, not resolved by this execution):** New alert #15, same rule, `tests/e2e/probes/probe_setup_fails_before_registration.py:53`, flagging the fix's own `Path(digest_file).write_text(secret_fingerprint(api_key, salt_hex))` line. CodeQL's static taint analysis for this query does not recognize `hashlib.scrypt` as a sanitizing transform, so it still treats the one-way salted digest as "sensitive data stored as clear text" even though the digest cannot be reversed to recover the key. See "CodeQL at the new head -- still failing" in `82-CI-EVIDENCE.md` for the full record (check run, analysis run, annotation text). This needs an owner decision: a CodeQL-recognized suppression with a written rationale (the digest is one-way, not the secret itself), a dismissal of alert #15 with a recorded reason, or a further structural change avoiding any on-disk write of the derived value (e.g. an in-memory/IPC handoff instead of a digest file). Not decided here -- outside this task's authorized scope (no further code changes, no third push).

## User Setup Required

None - no external service configuration required for Task 3 itself. The scratch directory used for local image verification (`/private/tmp/claude-501/-Users-julianamacbook-triggarr/72ccd835-a846-4599-a5e0-d8ba995139ed/scratchpad/ci82`) holds the round-2 `audited-image` artifact files (`image.tar`, `image.tar.sha256`, `image-id.txt`, `image-requirements.txt`; the round-1 files were removed before the round-2 download). The loaded Docker image tag was removed from the local daemon after each round's identity check. No NAS or other image was touched.

## Known Stubs

None - this plan's Task 3 is CI push/evidence/measurement only; no UI, no data flows, no product code (the CodeQL fix itself, `6c8354e`, was owner-authored and is test-only infrastructure, not product code).

## Threat Flags

None beyond this plan's own `<threat_model>` (T-82-36 through T-82-39, T-82-45), all of which this execution's own conduct satisfies across both rounds: pushed only `ci-review-workflow`, no force push, never `main` (T-82-36); run IDs/attempts/SHAs/log lines copied into `82-CI-EVIDENCE.md` for both runs (T-82-37); no merge or owner-acceptance submission attempted (T-82-38); evidence contains only SMOKE/rehearsal/result lines, no credentials (T-82-39); all five D-34 identity fields recorded separately with an explicit reconciliation line for both runs (T-82-45). The owner's fix commit itself reduces secret-handling risk in the e2e probe (no more plaintext password/API-key files), which this execution verified via the code-scanning API rather than by reading the diff alone.

## Next Phase Readiness

- **Not ready for Plan 09 / final owner acceptance as-is.** Alert #15 is an open required-check failure on the current head (`6c8354e932292bc5fdb6609388d32a673ba6070f`) that would otherwise be the basis for the phase's release-safeguard evidence record. It must be dispositioned (further fix, CodeQL-recognized suppression with rationale, or a recorded dismissal) and a fresh CI run obtained before Plan 09 can rely on this head, or before any owner acceptance per `docs/owner-cli-acceptance.md`.
- All CI evidence this plan was asked to capture for the `ci.yml` jobs themselves (test/lint/docker/secrets/dependencies/image-smoke/browser-e2e/CI ready, D-34 identities, D-31a rehearsal, D-14 budget) is complete and green for **both** recorded runs, and does not need to be re-collected once alert #15 is resolved -- only a fresh CI run on the resolving commit needs a new identity/evidence pass (a third "Third GitHub run" section, following the same pattern).
- **This docs-only commit (evidence + this summary) is deliberately NOT pushed.** The coordinator's round-2 instructions ask for a plain push of the final docs commit, but only as the "all required jobs and CodeQL pass" branch of step 6; the same message's closing limits ("if any required job or CodeQL fails ... do NOT push a fix ... and STOP") govern this outcome, since `CodeQL` is still failing (alert #15) on the head this evidence describes. Pushing would also start one more CI run against a head that is already known to carry an open required-check failure, which is exactly what the stop condition exists to avoid. The evidence and this summary are committed locally only; a push is deferred until alert #15 is resolved and a clean round can be pushed and watched together.
- `main` was not touched; no force push; no `review-acceptance` approval was requested, submitted, or inferred.

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
