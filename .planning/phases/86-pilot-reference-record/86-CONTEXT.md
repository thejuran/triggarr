# Phase 86: Pilot & Reference Record - Context

**Gathered:** 2026-10-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Prove the paired BM + Codex review workflow on 3-5 real PRs, run one fair side-by-side comparison against vibe-check, record the owner's PILOT-03 decisions (retire routine vibe-check or not; keep BM/Codex completion as a manual owner check or extend the acceptance gate), and write reusable adoption guidance for other repositories (PILOT-01..04).

Pilot PRs come only from this milestone's own PRs and already-recorded backlog work. No product change is invented to fill a category. The current review process (routine vibe-check where required, exact-commit owner acceptance, Greptile while free credits last) stays in force on every pilot PR until the owner retires part of it in PILOT-03.

</domain>

<decisions>
## Implementation Decisions

### Pilot set (PILOT-01)
- **D-01:** The pilot set has five PRs. Three already merged after Phase 83 and two are new:
  - **#48** (Phase 85.1, large, security-sensitive)
  - **#36** (Phase 85, large; its Codex pass was INCOMPLETE because of the PR's size and the owner approved the vibe-check fallback, which counts as evidence of how the workflow fails on very large PRs)
  - **#44** (small fix: Phase 85 follow-up)
  - **New: Refresh-counts fix** (state/error-path logic, product code)
  - **New: Card-template structured reason kind** (UI template)
- **D-02:** Refresh-counts behavior (owner decision): when one Sonarr or Lidarr record is malformed, "Refresh counts" **skips that record**, keeps the instance connected and logs the skip, matching what scheduled cycles already do. No new dashboard warning. Add a regression test for each app (Sonarr and Lidarr). This settles the open "Refresh counts vs. scheduled cycles" item in `.planning/backlog/MAINTENANCE.md`.
- **D-03:** The card-template PR is the backlog's "Card-template text-matching refactor": `cycle_grade.html` stops classifying reason rows by matching `outcome.py`'s display text and uses a structured kind field instead. Visible text and grade colors are unchanged. Record it honestly as a UI-template change with no visible difference. The pilot's "UI or security-sensitive" category is also covered by #48 (security-sensitive).
- **D-04:** **Each new fix ships as its own PR**, cut from `main`, so each gets a clean per-PR scorecard. This is a deliberate, recorded exception to one-PR-per-phase, for pilot PRs only. The Phase 86 records, scorecards and adoption guide ship in the Phase 86 PR (branch `phase-86-pilot-reference-record`, which also carries the held planning commits). Each pilot PR goes through the full current process: classification, BM review plus the paired Codex pass, a RISK-01 note, routine vibe-check where required, the checkpoint comment, and exact-commit owner acceptance.
- **D-05:** Categories are covered as follows: small fix (#44), state/error-path logic (Refresh-counts), UI (card template), security-sensitive (#48), larger change (#36, #48). Write down any category that turns out not to fit the evidence as a gap rather than stretching a PR to fill it.

### Vibe-check comparison (PILOT-02)
- **D-06:** The fresh comparison runs on the **Refresh-counts PR**. Vibe-check and BM + Codex each review the **same first head, before any fixes, independently**: neither sees the other's output. Compare what each caught. Routine vibe-check is still owed on that PR's final head where the current process requires it.
- **D-07:** Refresh-counts counts as "substantial" for PILOT-02 because it changes real state/error-path logic in two apps, with tests. Record its size honestly as moderate.
- **D-08:** #48 is **not** used as the comparison. Its vibe-check ran only on the final head, after five BM/Codex fix rounds, so it cannot show what vibe-check would catch independently. If #48's vibe-check result is cited at all, state that limitation.
- **D-09:** **Proof-based judging.** A finding counts as a *confirmed consequential defect* only if a failing test or a reproduction demonstrates it. Every other finding is labeled *false positive* or *unproven*, with the reason. The owner approves the tally, not the code (the owner does not adjudicate code).

### What to measure (PILOT-01)
- **D-10:** For each pilot PR and each reviewer (BM, Codex, vibe-check, Greptile when it ran), record: confirmed consequential defects, false positives, later-found misses, revision rounds, review time, observable usage/cost, and owner effort.
- **D-11:** For the existing PRs (#48, #36, #44), fill in only what the committed records prove (findings, dispositions, rounds). Mark missing review time, usage and owner effort as **"not recorded"**. Never estimate or rebuild them from timestamps.
- **D-12:** Owner effort on new PRs is the **number of decisions or approvals Claude brought to the owner** on that PR, logged as they happen. No self-reported minutes.
- **D-13:** Usage/cost is **wall-clock time plus whatever usage or token counts each tool actually prints**. If a tool reports nothing, say so. No dollar estimates.
- **D-14:** A later-found miss counts if a later review round, another reviewer, CI or production finds it **before the Phase 86 PR is accepted**. State this cutoff, and that it is short for the newest PRs.

### Retirement bar (PILOT-03), set before results
- **D-15:** The bar is fixed now, before any comparison result exists. Recommend **retiring routine vibe-check only if, on the fresh comparison and across the pilot, vibe-check found no proven defect (D-09) that BM + Codex missed.** If it found one, recommend keeping routine vibe-check, or keeping it for the risk level where it made the unique catch. The owner makes the final decision; the bar shapes Claude's recommendation only.
- **D-16:** These two things stay whatever PILOT-03 decides: bot/fork PRs keep the vibe-check fallback (Phase 85.1 owner exception, D-16 of that phase), and BM still recommends an extra vibe-check at high risk (RISK-02, Phase 83).
- **D-17:** The second PILOT-03 decision is left to the end of the phase: does BM/Codex completion stay a manual owner check, or is the acceptance gate extended to require those reports? Claude brings a recommendation with the evidence. Recording the owner's decision completes the requirement. If the owner chooses extension, it is scheduled as FUT-03 and not built in this phase unless the owner pulls it in.

### Adoption guide (PILOT-04)
- **D-18:** Write it as `docs/review-workflow-adoption.md` in this repository, for the owner's other projects (e.g. SeedSyncarr). It separates GitHub-enforced requirements from instruction-enforced ones and lists what not to copy blindly. No private infrastructure details: the repo is public, so follow the 2026-10-21 published-history rule.

### Claude's Discretion
- Scorecard format and where it lives inside the phase directory (e.g. `86-PILOT-RECORD.md`), and the per-PR table layout.
- The order of the two new PRs, and the exact wording of the adoption guide.
- How #36's and #48's multi-round records are condensed into scorecard rows, as long as each number traces back to a committed record.

</decisions>

<specifics>
## Specific Ideas

- The owner is a product manager. The pilot results and the PILOT-03 recommendation must be written so they can be decided on without reading code: the tradeoff in user impact, risk, time and maintenance burden.
- The bar in D-15 must be quoted verbatim in the pilot record *before* the comparison runs, so it cannot be fitted to the results (the blueprint's "set criteria before running the comparison" rule).
- The models changed together with the review settings in Phase 83 (83-CONTEXT D-02). Note this wherever older and newer review results are compared.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Pilot scope and decisions
- `.planning/REQUIREMENTS.md`: PILOT-01..04, FUT-03, and the standing rule that the current review process stays until PILOT-03
- `.planning/ROADMAP.md` § "Phase 86: Pilot & Reference Record": success criteria
- `docs/bm-greptile-codex-blueprint.md`: pilot steps 8-9, the "set criteria before results" rule, acceptance-gap note (manual BM/Codex completion check)

### Review process every pilot PR follows
- `docs/buildomator-greptile-pilot.md`: routine BM workflow, register shape, pilot checklist
- `docs/review-checkpoint-record.md`: one PR comment per head SHA, RISK-01 note, vibe-check recommendation + owner decision
- `docs/review-classification-policy.md`: content-based classification against the exact head
- `docs/codex-adversarial-review-contract.md`: paired Codex pass, owner-approved fallback, untrusted-PR fallback
- `docs/owner-cli-acceptance.md`: exact-commit owner acceptance transport

### Evidence for the existing pilot PRs
- `.planning/phases/85.1-isolated-codex-review-for-untrusted-prs/85.1-REVIEW-EVIDENCE.md`: PR #48 per-head BM/Codex/vibe-check records and dispositions
- `.planning/phases/85-follow-on-ci-improvements-acceptance-usability/85-REVIEW-EVIDENCE.md` and `85-REVIEW.iter*.md`: PR #36 records (Codex incomplete for size; vibe-check fallback)
- PR #44 checkpoint comment on GitHub (`gh pr view 44 --comments`) plus its Phase 85 follow-up records
- `.planning/phases/83-paired-bm-codex-review-risk-based-depth/83-CONTEXT.md` D-02: model change recorded with the BM update

### Backlog sources for the new PRs
- `.planning/backlog/MAINTENANCE.md`: "Refresh counts vs. scheduled cycles on a malformed record" and "Card-template text-matching refactor"

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_screen_queue` (`triggarr/search/engine.py:167`): the per-item malformed-record skip-and-count helper that scheduled cycles already use (ROBUST-01/04). The Refresh-counts fix should reuse it, not add a parallel path.
- `malformed_skipped` / `malformed_by_queue` in `triggarr/state.py:49-52`: existing counters for skipped records.

### Established Patterns
- `refresh_sonarr_counts` (`engine.py:1981`) and `refresh_lidarr_counts` (`engine.py:2108`) catch `(AttributeError, KeyError, TypeError)` around the filter/tag phase (`engine.py:2091`, `engine.py:2211`) and treat it as a whole-instance data failure: disconnected, return None. Their docstring "FAILURE CONTRACT (b)" must be updated to match the new behavior. Phase 79 D-05 (an unresolved tag scope keeps its last good counts) must be preserved.
- `refresh_radarr_counts` (`engine.py:1859`): check whether it has the same coarse guard. The backlog names only Sonarr and Lidarr.
- `triggarr/templates/partials/cycle_grade.html` lines 32-36 choose the summary label ("detail(s)", "skipped record(s)", "failure reason(s)") and classify rows by matching display strings from `triggarr/search/outcome.py`.

### Integration Points
- The pilot record and the PILOT-03 decision go in the Phase 86 phase directory. The adoption guide goes in `docs/`.
- New pilot PRs create their own checkpoint comments and register slices (`REVIEW_DISPOSITIONS`/`REVIEW_BLOCKERS`), following existing practice.

</code_context>

<deferred>
## Deferred Ideas

- SA-12 (opt-in FastAPI OpenTelemetry auto-configure can fail startup) and SA-01 (pin CI's uv version): considered as pilot PRs and not chosen. They stay in `.planning/backlog/MAINTENANCE.md` with their decisions still pending.
- Dollar-cost estimates and self-reported owner minutes: not collected (D-12, D-13).
- Tracking later-found misses past Phase 86 acceptance (e.g. through the next release): not in scope (D-14).

</deferred>

---

*Phase: 86-pilot-reference-record*
*Context gathered: 2026-10-30*
