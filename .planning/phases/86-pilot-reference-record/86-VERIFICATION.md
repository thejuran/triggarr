---
phase: 86-pilot-reference-record
verified: 2026-11-14T17:06:43Z
status: human_needed
score: 4/4 roadmap success criteria verified; 4/4 requirements (PILOT-01..04) satisfied
has_blocking_gaps: false
overrides_applied: 0
human_verification:
  - test: "Push branch phase-86-pilot-reference-record and open the Phase 86 PR against main."
    expected: "PR opens with the classification (sensitive: CLAUDE.md, docs/review-checkpoint-record.md and the other review-policy docs; ordinary-docs: the adoption guide and planning files), carrying the reviewed head 63a5b45b4a33... (plus the follow-up checkpoint-record commit 4d49dcf, which only adds evidence files)."
    why_human: "Pushing and opening a PR is an irreversible, human-authorized action; this verification is read-only per its instructions and the project's one-PR-per-phase / push-budget rules reserve pushing for the owner's explicit go-ahead."
  - test: "Run CI on the pushed phase PR head and confirm CI ready, CodeQL and the other required jobs pass."
    expected: "All required checks pass the same way they did on the five pilot PRs (CI ready, CodeQL, actionlint, browser-e2e, dependencies, docker, image-smoke, lint, os-scan, secrets, test)."
    why_human: "CI only runs on a pushed head; nothing to run yet locally beyond the local pytest/ruff/publication-gate checks already executed (see Behavioral Spot-Checks)."
  - test: "Owner exact-commit acceptance of the Phase 86 PR's final pushed head, per docs/owner-cli-acceptance.md, followed by the owner's merge."
    expected: "Owner approves the exact SHA and run; Claude never infers approval or merges on its own."
    why_human: "This is the standing acceptance gate for every PR in this repository; it cannot be satisfied before the PR exists and CI has run on it."
  - test: "Check the Roadmaps page for 'Planning files disagree' warnings once Phase 86 is actually ticked complete."
    expected: "No red disagreement box; Phase 86 shows as in review until it is actually merged, then complete."
    why_human: "No tool access to the rendered Roadmaps page from this session; STATE.md/ROADMAP.md were read directly and found internally consistent (see Gaps Summary), but the rendered page itself was not opened."
  - test: "Greptile review on the pushed phase PR head, if it chooses to run (free-tier, optional since 2026-10-22)."
    expected: "If it runs, it finishes successfully and its findings get current-head dispositions; if it doesn't run, that is disclosed in the PR per standing policy."
    why_human: "Greptile only runs against a pushed GitHub PR; nothing to check before the push."
---

# Phase 86: Pilot & Reference Record Verification Report

**Phase Goal:** Prove the paired workflow on real PRs, record the owner's retirement/extension decisions, and leave reusable guidance for other repositories.
**Verified:** 2026-11-14T17:06:43Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Scope note: the phase branch is the Phase 86 PR, not yet pushed

Per this repository's one-PR-per-phase and push-budget rules (CLAUDE.md "Review workflow"), the Phase 86 PR is the `phase-86-pilot-reference-record` branch itself, held locally and pushed only at phase end. HEAD at verification time is `4d49dcfaad46346e09029971de8a3c92a394cb3c`, one commit after the reviewed checkpoint `63a5b45b4a33ae84e7a34313d05275812d4d4650` that adds only evidence/record files (no code or instruction changes — confirmed by diff, see "Local review-loop checkpoint" below). The branch is confirmed not pushed (`git ls-remote origin phase-86-pilot-reference-record` returns nothing; no PR found for this head via `gh pr list`). Consequently "PR not pushed," "CI not yet run on the phase PR," "owner acceptance of the phase PR pending," and "Roadmaps page not independently checked" are expected end-of-phase steps, not gaps — they are listed under Human Verification Required, not Gaps.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth (ROADMAP Success Criterion) | Status | Evidence |
|---|---|---|---|
| 1 | 3-5 representative PRs run under the paired workflow, covering small fix / state-error-path / UI-or-security-sensitive / larger-change categories (or gaps recorded), each with per-reviewer metrics | ✓ VERIFIED | Five PRs: #48 (security-sensitive, large), #36 (larger change, large-PR Codex-incomplete evidence), #44 (small fix), #54 Refresh-counts (state/error-path, moderate), #55 Card-template (UI). All five confirmed `MERGED` via `gh pr view --json state,mergedAt,mergeCommit`, merge commits confirmed ancestors of HEAD via `git merge-base --is-ancestor`. Per-reviewer D-10 scorecards (confirmed defects, false positives, later-found misses, revision rounds, review time, usage/cost, owner effort) present for all five in `86-PILOT-RECORD.md` "Scorecards". UI category gap honestly recorded: card-template PR exercises the refactor but 86-05's divergence analysis found no reachable visible difference, so "UI coverage" is template-only — recorded under "### Gaps" in the pilot record rather than overstated. |
| 2 | At least one substantial pilot PR gets a recorded, fair side-by-side comparison of vibe-check against the paired workflow, in addition to routine vibe-check | ✓ VERIFIED | Refresh-counts PR, head `03182462100e...` (H1): vibe-check, BM and Codex all ran independently before any fix (pre-registered method in `86-PILOT-RECORD.md`). Codex **completed** at H1 (`verdict: no-findings`), which the plan's own must-have (86-03) requires for the comparison to count as valid — confirmed in the record and in `86-REVIEW-EVIDENCE.md`. Owner approved the tally verbatim ("Approve tally for H1 0318246. Continue with 86-04. ..."). Result: zero unique catches either way on the fresh comparison; one unique vibe-check catch elsewhere in the pilot (PR #36, high-risk, Codex-incomplete case). |
| 3 | The owner's decisions are recorded: retire routine vibe-check or not; keep BM/Codex completion a manual check or extend the acceptance gate (FUT-03) | ✓ VERIFIED | Both decisions quoted verbatim with date in `86-PILOT-RECORD.md` "## PILOT-03 recommendation and decisions" and the owner decisions log: Decision 1 (keep vibe-check, scoped to high risk only) and Decision 2 (keep the manual owner check; FUT-03 not chosen). REQUIREMENTS.md's FUT-03 entry and standing-rules paragraph already reflect this verbatim, dated 2026-11-14. |
| 4 | Reusable adoption guidance for other repositories is written, distinguishing instruction-enforced from GitHub-enforced requirements and listing what not to copy blindly | ✓ VERIFIED | `docs/review-workflow-adoption.md` exists with `## GitHub-enforced requirements`, `## Instruction-enforced requirements`, and `## What not to copy blindly` sections. Every GitHub-enforced claim in the guide was independently re-checked in this verification against live settings: `gh api repos/thejuran/triggarr/rulesets/14805779` (required checks `CI ready`/`Review acceptance`/`CodeQL`, strict status checks, required-deployments to `review-acceptance`), `gh api repos/thejuran/triggarr/actions/permissions` (`sha_pinning_required: true`), `gh api repos/thejuran/triggarr/code-scanning/default-setup` (`state: configured`), `gh api repos/thejuran/triggarr/environments/review-acceptance` (required reviewer `thejuran`, `prevent_self_review: false`, `can_admins_bypass: false`). All matched the guide's text exactly — no drift found. |

**Score:** 4/4 roadmap success criteria verified.

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|---|---|---|---|---|
| PILOT-01 | 86-02, 86-03, 86-04, 86-06, 86-07, 86-08, 86-10 | 3-5 representative PRs, per-reviewer metrics | ✓ SATISFIED | See Truth #1 above; scorecards + cross-PR summary table in `86-PILOT-RECORD.md`. |
| PILOT-02 | 86-01, 86-03, 86-04 | Fair side-by-side comparison on a substantial PR | ✓ SATISFIED | See Truth #2 above; comparison method pre-registered before results, Codex completed on H1. |
| PILOT-03 | 86-01, 86-08, 86-09 | Owner's two decisions recorded | ✓ SATISFIED | See Truth #3 above; both decisions quoted verbatim with date. |
| PILOT-04 | 86-09 | Reusable adoption guidance | ✓ SATISFIED | See Truth #4 above; GitHub-enforced claims independently re-verified live. |

No orphaned requirements: every PILOT-01..04 ID declared across the ten plans' frontmatter matches REQUIREMENTS.md's Phase 86 traceability rows exactly, and no additional Phase-86-mapped requirement ID exists in REQUIREMENTS.md that isn't claimed by a plan.

### Retirement bar integrity check (D-15)

`git diff bbabaf8be53a85e60431dbb03d71c837a6b1afb5 HEAD -- .planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md`, restricted to the "## Retirement bar (D-15, fixed before results)" section only: **byte-identical**, no added or removed line. Confirmed by independently extracting the section from both revisions and diffing them (`diff` exit 0). This satisfies the "bar fixed before results" rule the PILOT-03 recommendation depends on.

### 86-09 scope-widening check

86-09's own must-have scoped CLAUDE.md / `docs/review-checkpoint-record.md` edits to "only the vibe-check sentences." The actual diff from the pre-phase baseline (`d5a4467`) to HEAD for both files was inspected line by line: every added/changed sentence in both files is about the vibe-check rule (routine-vibe-check retirement, scoping to high risk, automatic Claude-initiated start, trusted/untrusted-head limits, the unchanged Codex-fallback case). The wider set of consistency edits (`docs/review-classification-policy.md`, `docs/bm-greptile-codex-blueprint.md`, `docs/buildomator-greptile-pilot.md`, `docs/ci-reference-baseline-plan.md`) were also diffed and are the same vibe-check-rule update propagated for consistency, not unrelated scope. The widening beyond 86-09's original single-plan scope rule is recorded: owner decision 2026-11-14, "keep the extra doc edits in this PR," plus the two offered-option selections ("Claude runs it"; "One more round, then stop") — all in `86-PILOT-RECORD.md`'s "Corrections (2026-11-14, after code review iteration 1)" / "Added 2026-11-14, after code review iteration 2" sections and the owner decisions log. Treated as a recorded, owner-approved widening, not a violation.

### Local review-loop checkpoint (post-86-09)

A review loop ran on the phase PR content after 86-09 finished: six BM iterations (`86-REVIEW.md` + `86-REVIEW-phase-*.md`), a paired read-only Codex pass per head (five attempts, all `complete`), and the required high-risk vibe-check (two passes, per the owner's 2026-11-14 decision that Claude starts it automatically at high risk). Final state at head `63a5b45b4a33...`, confirmed in `86-REVIEW-EVIDENCE.md`'s "Phase 86 PR (local checkpoint before the end-of-phase push)" section: BM 0 critical/0 warning/2 info (backlogged per the owner's "one more round, then stop" rule); Codex `verdict: no-findings`, `review_complete: true`; vibe-check pass 2, 0 reported. `git log 63a5b45b4a33..HEAD` shows exactly one further commit (`4d49dcf`), which only adds the checkpoint-record files themselves (`86-REVIEW-EVIDENCE.md` addition, `86-REVIEW-phase-63a5b45b4a33.md`, and the `codex/63a5b45b4a33-phase-a1.*` raw-output files) — confirmed via `git diff --stat`, no code or instruction-text changes. HEAD therefore reflects exactly what was reviewed.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `.planning/phases/86-pilot-reference-record/86-PILOT-RECORD.md` | Pre-registered bar/method, five scorecards, PILOT-02 result, PILOT-03 decisions, Corrections log | ✓ VERIFIED | 709 lines; all sections present and cross-checked against sources (gh output, REVIEW-EVIDENCE.md) in this verification. |
| `.planning/phases/86-pilot-reference-record/86-REVIEW-EVIDENCE.md` | Per-head checkpoint records for both new pilot PRs and the Phase 86 PR itself | ✓ VERIFIED | 1262 lines; durable copies match the live GitHub PR comments word-for-word (spot-checked via `gh pr view --json comments`). |
| `.planning/phases/86-pilot-reference-record/86-publication-gate.sh` + `-selftest.sh` | Fail-closed evidence-publication gate and its self-test | ✓ VERIFIED, WIRED | `bash 86-publication-gate.sh`: `PASS (95 tracked artifacts)`, exit 0. Self-test: `bash 86-publication-gate-selftest.sh 86-publication-gate.sh`: `selftest: 58 passed, 0 failed` — matches the number cited in the pilot record's own regression note. |
| `docs/review-workflow-adoption.md` | PILOT-04 reusable guidance | ✓ VERIFIED | Present, all required sections; GitHub-enforced claims independently re-verified live (see Truth #4). |
| `triggarr/search/engine.py` (refresh_radarr/sonarr/lidarr_counts) | Per-item malformed-record skip via `_screen_queue`, matching scheduled cycles (D-02/D-02a) | ✓ VERIFIED, SUBSTANTIVE | Real diff inspected (`git show 0318246...`): `allow_non_object_records=True` on fetch, `_screen_queue` calls inserted at each filter/tag site, throwaway `CycleTally`, updated FAILURE CONTRACT docstrings. Not a stub. |
| `tests/test_refresh_counts.py`, `tests/test_malformed_records_client_path.py` | Regression tests per app | ✓ VERIFIED, WIRED | Collected and passing as part of the full suite (3282 passed, 1 skipped). |
| `triggarr/search/outcome.py`, `triggarr/templates/partials/cycle_grade.html` | Structured `kind`/`skip_count` replacing text-matching classification (D-03) | ✓ VERIFIED, SUBSTANTIVE | Real diff inspected (`git show 46c3919...`): template now branches on `r.kind`, sums `r.skip_count`; `tests/test_app_cards.py` unmodified and still passing (per plan's own must-have, confirmed by its absence from the changed-file list and by the full suite pass). |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| PR #48/#36/#44/#54/#55 (`mergeCommit`) | HEAD (`4d49dcf`) | `git merge-base --is-ancestor` | ✓ WIRED | All five merge commits confirmed ancestors of HEAD; `#54`/`#55`/`#57` merge SHAs match `86-PILOT-RECORD.md`'s stated values exactly. |
| `86-PILOT-RECORD.md` / `86-REVIEW-EVIDENCE.md` durable copies | Live GitHub PR comments | `gh pr view --json comments` | ✓ WIRED | PR #54 (1 comment) and PR #55 (2 comments, matching its integration re-review) bodies match the durable copies verbatim (spot-checked header blocks). |
| `docs/review-workflow-adoption.md` GitHub-enforced claims | Live repo configuration | `gh api .../rulesets`, `.../actions/permissions`, `.../code-scanning/default-setup`, `.../environments/review-acceptance` | ✓ WIRED | Every cited fact (required checks, strict policy, SHA pinning, CodeQL default setup, required-reviewer/self-review/admin-bypass settings) matches live output exactly. |
| CLAUDE.md / docs/review-checkpoint-record.md edits | PILOT-03 decisions in `86-PILOT-RECORD.md` | diff inspection | ✓ WIRED | Every changed sentence traces to the vibe-check-rule decision; no unrelated instruction drift. |
| Backlog items ("Refresh counts vs. scheduled cycles", "Card-template text-matching refactor") | PR #54 / PR #55 merge commits | `.planning/backlog/MAINTENANCE.md` | ✓ WIRED | Both marked "Resolved" with the correct merge SHAs; SA-12 and the uv-version-pin SA-01 item left open/deferred as the plan required. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full test suite passes at HEAD | `uv run pytest tests/ -q` | `3282 passed, 1 skipped, 38 warnings in 86.48s` | ✓ PASS |
| Evidence publication gate passes at HEAD | `bash 86-publication-gate.sh` | `publication gate: PASS (95 tracked artifacts)`, exit 0 | ✓ PASS |
| Publication gate self-test | `bash 86-publication-gate-selftest.sh 86-publication-gate.sh` | `selftest: 58 passed, 0 failed` | ✓ PASS |
| Refresh-counts / card-template regression tests collect | `pytest --collect-only -q` on the four touched test files | 238 tests collected | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh`-style probes are declared by this phase's plans or SUMMARYs; the phase's own "probe" equivalent is the publication gate and its self-test, executed above as Behavioral Spot-Checks (both ran from the repository root with `bash`, per the plan's own invocation contract).

### Anti-Patterns Found

None. Every file touched by Phase 86 (`CLAUDE.md`, the five `docs/*.md` consistency edits, `docs/review-workflow-adoption.md`, `triggarr/search/engine.py`, `triggarr/search/outcome.py`, `triggarr/templates/partials/cycle_grade.html`, the four touched test files, the two publication-gate scripts) was scanned for `TBD|FIXME|XXX` — no matches. No placeholder/stub return patterns found in the two real code diffs inspected (`engine.py`, `outcome.py`/`cycle_grade.html`) — both are genuine behavioral changes with passing regression tests, not stubs.

**Incidental non-Phase-86 content on the branch (informational, not a gap):** the branch also carries `Dockerfile`/`uv.lock` changes (PR #57's `zlib1g`/`opentelemetry-api` security bumps, merged to main and pulled in by 86-10's no-rebase integration — expected and documented) and one pre-existing held planning-cleanup commit touching `.gsd/milestones/M001/slices/S03/S03-UAT.md` (a path-redaction fix, inherited from the `planning/cleanup-2026-10-30` branch this phase branch was cut from, per 86-CONTEXT D-04's note that the phase branch "also carries the held planning commits"). Neither is Phase 86's own deliverable; neither contradicts any Phase 86 must-have.

### Human Verification Required

See frontmatter `human_verification`. In plain terms: the phase's own work (the five pilot PRs, the comparison, the two owner decisions, the adoption guide, and the local review loop on the Phase 86 PR's content) is done and verified in the codebase. What remains is the standard end-of-phase sequence this project always runs on its own PR: push the branch, let CI run, get the owner's exact-commit acceptance, and have the owner merge — plus an independent check of the rendered Roadmaps page, which this session has no tool access to. None of these can be satisfied before the push happens, so none of them are gaps against the phase's own goal.

### Gaps Summary

No gaps. All four ROADMAP success criteria and all four requirement IDs (PILOT-01..04) are verified against live evidence (committed records, independently re-run `gh api`/`gh pr` queries, a from-scratch pytest run, and the publication gate's own self-test), not against SUMMARY.md narration. The one thing worth flagging to the orchestrator, per the task's own framing, rather than as a gap: `STATE.md` was last hand-updated at the end of plan 86-09 (before the post-86-09 review loop ran) and so does not yet mention that review loop or this verification — its "in review" status and unticked ROADMAP checkbox are still correct, just not current on the narrative details. REQUIREMENTS.md's PILOT-01..04 checkboxes and traceability rows remain "Pending," consistent with the phase not yet being complete (merged/verified) per `docs/PLANNING-FORMAT.md`'s tick rule.

---

*Verified: 2026-11-14T17:06:43Z*
*Verifier: Claude (bm-verifier)*
