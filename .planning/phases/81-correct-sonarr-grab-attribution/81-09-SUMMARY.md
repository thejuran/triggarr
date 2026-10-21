---
phase: 81-correct-sonarr-grab-attribution
plan: 09
subsystem: database
tags: [jinja2, htmx, dashboard, attribution, disclosure, planning-reconciliation]

# Dependency graph
requires:
  - phase: 81-05
    provides: "get_dashboard_stats app+stable-ID scoping, get_attribution_disclosure, stats_row.html cutover note and historical-estimate labels, history/activity-rail Legacy label — the disclosure this plan verified on screen"
  - phase: 81-13
    provides: "Live tag/pagination evidence on both sandboxes and the owner's disposition of the unauthorized upgradeAllowed deviation, both read into this plan's REQUIREMENTS/ROADMAP/STATE reconciliation"
provides:
  - "On-screen owner confirmation of the ATTR-06 disclosure (cutover note, historical-estimate labels, Legacy history label) across a pre-fix-data instance and a fresh instance, via two /walkthrough observe-and-report runs"
  - "Two owner-approved bounded scope additions closing real UX gaps the disclosure review surfaced: the time-to-grab stats card retitled away from its stale 'Next Scan' label, and an hx-sync fix for a genuine instance-selector/poll race that could leave a stale disclosure on screen"
  - "D-13 reconciliation: REQUIREMENTS.md ties each Phase 81 requirement's checkbox to its own evidence (ATTR-01..06, SONARRV5-01, SONARRV5-03 complete; SONARRV5-02 open with every unverified-live scenario listed); ROADMAP.md and STATE.md match, with Phase 81 correctly left unchecked/incomplete pending review and merge"
  - "81-LIVE-MATRIX.md '## Owner review (disclosure)' and '## Status' sections — the latter the authoritative, per-D-11-item pass/open summary that REQUIREMENTS.md's note and this plan's reconciliation both read from"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Local-only disclosure verification: two throwaway Triggarr instances (seeded pre-fix data vs. fresh install), bound to 127.0.0.1, fake API keys, auth disabled, never touching the NAS or a real *arr instance — a reusable pattern for any future on-screen review of dashboard-only behavior"

key-files:
  created: []
  modified:
    - .planning/phases/81-correct-sonarr-grab-attribution/81-LIVE-MATRIX.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
    - .planning/STATE.md

key-decisions:
  - "Task 1 ran two full Triggarr processes (not just template snippets) against scratch config dirs and a scratch-seeded database, reusing production startup/lifespan code exactly (a standalone scratch runner script that only parameterizes the port, not product code) — so the owner reviewed the actual rendered application, not a mockup"
  - "Task 2's owner on-screen review surfaced two real, in-scope UX problems (stale card title, selector/poll race); both were accepted as bounded Phase 81 scope additions rather than deferred, fixed under TDD (e996322 test, 09421ab fix), and independently re-verified by this plan (full suite 1999 passed, ruff clean) before being recorded as evidence rather than taken on claim alone"
  - "Task 3 ticks each requirement independently against its own plan-SUMMARY evidence (ATTR-01..05, SONARRV5-01, SONARRV5-03) rather than block-approving all Phase 81 requirements once any one passed; SONARRV5-02 is evaluated solely against 81-LIVE-MATRIX.md's '## Status' section, which stays authoritative over any single requirement note"
  - "STATE.md and ROADMAP.md edits were left uncommitted in the working tree (not staged, not committed) because both files carry unrelated in-flight owner edits mixed into the same files; only .planning/phases/81-correct-sonarr-grab-attribution/81-LIVE-MATRIX.md and this SUMMARY were committed, via git add -f (both are .planning/ paths excluded by .git/info/exclude but already-or-newly tracked)"

patterns-established:
  - "Requirement-by-requirement completion tracking under D-13: tick only what a plan's own SUMMARY evidence supports, leave an explicit unverified-scenario note under any requirement that stays open, and treat the phase's own acceptance-matrix '## Status' section as the single source of truth for a compatibility-verification requirement rather than re-deriving it ad hoc in REQUIREMENTS/ROADMAP/STATE"

requirements-completed: [ATTR-06]  # SONARRV5-02 stays open per D-13 -- see 81-LIVE-MATRIX.md "## Status" and REQUIREMENTS.md for every unverified-live scenario. ATTR-01..05, SONARRV5-01 and SONARRV5-03 were also ticked complete in REQUIREMENTS.md this plan, on the evidence already produced by plans 81-01..81-04 and 81-02 respectively (not newly produced here) -- listed here only once since this field tracks this plan's own completed requirement, ATTR-06.

# Metrics
duration: ~90min (across the session, including the owner review interval)
completed: 2026-10-21
---

# Phase 81 Plan 09: Disclosure On-Screen Check & D-13 Status Reconciliation Summary

**Two local scratch Triggarr instances proved the ATTR-06 disclosure on screen in both pre-fix and fresh states; the owner's review caught and approved two bounded UX fixes (stats-card retitle, selector/poll hx-sync race); REQUIREMENTS/ROADMAP/STATE now tick only what each plan's evidence supports, with SONARRV5-02 and Phase 81 explicitly left open/incomplete per D-13.**

## Performance

- **Duration:** ~90 min (Task 1 build+seed+serve, Task 2 owner review interval via two `/walkthrough` runs, Task 3 reconciliation)
- **Completed:** 2026-10-21
- **Tasks:** 3 (all complete)
- **Files modified:** 4 (`81-LIVE-MATRIX.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`)

## Accomplishments

- **Task 1 — Local disclosure-check instances:** Built two throwaway Triggarr instances in the session scratchpad, never the NAS or a real *arr install: a "prefix" instance seeded with resolved Sonarr rows (one `grabbed` with `resolved_at` and a non-zero `lifetime_stats` increment, one `unresolved`), one pending row later frozen legacy by `ensure_cutover_recorded`, and a "fresh" instance with the same instance shape but no history. Both ran the real startup/lifespan code (a scratch runner script that only parameterizes the port — not product code) bound to `127.0.0.1` with fake API keys and auth disabled. Automated presence/absence greps confirmed every acceptance criterion before handoff: the prefix dashboard showed the cutover note exactly once and the Lifetime label once; the prefix Radarr partial showed neither; `/history` showed the Legacy label; the fresh instance showed none of it anywhere. `git status --porcelain` showed no new repo files from this task.
- **Task 2 — Owner on-screen review:** Conducted as two `/walkthrough` observe-and-report runs against the two local instances. The first run passed CP1-CP6 (note/labels present and correctly worded on the prefix instance and absent on Radarr/fresh, Legacy label on the frozen pending row, readable placement) and surfaced two items the owner chose to accept as bounded Phase 81 scope additions rather than defer: (1) the fourth stats card was titled "Next Scan" / "Scheduled automatically" while rendering the average time-to-grab, misreading the new historical-estimates label as if it qualified the scan schedule; (2) a genuine selector/poll race — an in-flight "All instances" poll landing between a Radarr selection's request and response left the Sonarr disclosure under a Radarr selection until the next poll, because the instance selector and the 30s stats-row poll both swapped `#stats-row` with no shared `hx-sync` scope. Both were fixed under TDD (`e996322` test RED, `09421ab` fix — card retitled "Average time to grab" / "From search to grab"; `hx-sync="#stats-row:replace"` on the selector, `hx-sync="this:drop"` on `#stats-row`) and independently re-verified here: `uv run pytest tests/ -q` → 1999 passed; `uv run ruff check triggarr/ tests/` → all checks passed. A re-verify `/walkthrough` run on `09421ab` then passed CP1-CP6 with 0 console errors. Owner response: "Accepted." Recorded in `81-LIVE-MATRIX.md` under "## Owner review (disclosure)", citing both walkthrough journal paths and the two commit hashes.
- **Task 3 — D-13 reconciliation:** Added `81-LIVE-MATRIX.md`'s "## Status" section, restating the Matrix's own per-D-11-item verdicts: D-11.1 (v5 core) and D-11.3 (v4 core) both OPEN on the same missing item (client-returned ID-set completeness/uniqueness for missing- and cutoff-queue pagination, never the real client's own returned records) plus v4 library counts never dedicatedly re-verified; D-11.2 (v5 season-pack attribution) PASS per the owner's 81-12 decision; the D-12 fixture-only rows (multi-season pack, alternate series order) listed separately as never required live. REQUIREMENTS.md now ticks ATTR-01..06, SONARRV5-01 and SONARRV5-03 against each plan's own SUMMARY evidence (cross-checked against the independently re-run full test suite), with ATTR-06 additionally carrying the Task 2 owner-approval note; SONARRV5-02 stays unticked with every unverified-live scenario listed as an indented note. ROADMAP.md's Phase 81 bullet, milestone-status row, plan-list tick (81-09 now `[x]`), Progress row and a new "81-09 closeout notes" paragraph all reflect 13/13 plans executed, SONARRV5-02 open, Phase 81 still unchecked and incomplete, with the two scope additions recorded by name and commit hash. STATE.md's frontmatter (`status`, `stopped_at`, `last_updated`, `last_activity`), Current Position and Operator Next Steps now say the same thing, while the Phase 80 scheduled-cycle note and every unrelated owner edit (the "CI & Review Workflow" `agent.spawn` sentence in STATE.md, the "Codex plan-checker routing (investigation)" bullet in ROADMAP.md) were left untouched.

## Task Commits

1. **Task 1: Local disclosure-check instances** — no commit (scratch-only task; no repo files were created or modified; `git status --porcelain` confirmed only the pre-existing unrelated owner edits remained throughout).
2. **Task 2: Owner on-screen review** — the two UX fixes the review approved were committed separately, by the process that ran the `/walkthrough` review and implemented the owner-approved scope additions: `e996322` (test RED) and `09421ab` (fix). This plan's own contribution for Task 2 is the evidence record in `81-LIVE-MATRIX.md` (see the combined commit below) — both commits and the full-suite/ruff claims were independently re-verified here before being recorded, not taken on claim.
3. **Task 3: D-13 reconciliation** — `.planning/REQUIREMENTS.md` was edited but is untracked (`git ls-files --error-unmatch` fails) and is intentionally left on disk, uncommitted, per the plan's own tracking rule. `.planning/STATE.md` and `.planning/ROADMAP.md` were edited but deliberately NOT staged or committed by this plan, because both files carry unrelated in-flight owner edits mixed into the same files (STATE.md's "CI & Review Workflow" sentence, ROADMAP.md's "Codex plan-checker routing (investigation)" bullet) that must never be staged or committed here; those edits are left in the working tree for the orchestrator to commit as separate, isolated hunks.

**Combined commit (Tasks 2+3 evidence, via `git add -f`):** `.planning/phases/81-correct-sonarr-grab-attribution/81-LIVE-MATRIX.md` (the "## Owner review (disclosure)" and "## Status" sections) and this `81-09-SUMMARY.md` — see the completion message for the hash.

## Files Created/Modified

- `.planning/phases/81-correct-sonarr-grab-attribution/81-LIVE-MATRIX.md` — added "## Owner review (disclosure)" (two `/walkthrough` run records, the two scope additions, commit hashes, independently re-verified test/ruff results, owner's verbatim "Accepted") and "## Status" (per-D-11-item pass/open summary, fixture-only rows listed separately, explicit SONARRV5-02-stays-open conclusion)
- `.planning/REQUIREMENTS.md` — ATTR-01..06, SONARRV5-01, SONARRV5-03 ticked complete (ATTR-06 carries the Task 2 approval note); SONARRV5-02 stays unticked with every unverified-live scenario listed; Traceability table Status column and the file's own "Last updated" line updated to match (untracked file; edited, not committed)
- `.planning/ROADMAP.md` — Phase 81 milestone bullet, milestone-status table row, 81-09 plan-list tick, Progress table row, and a new "81-09 closeout notes" paragraph recording the two scope additions by name and commit hash (edited, left uncommitted for the orchestrator)
- `.planning/STATE.md` — frontmatter `status`/`stopped_at`/`last_updated`/`last_activity`, Current Position (`Phase:`/`Plan:`/`Status:`/`Last activity:`), Session Continuity, and Operator Next Steps updated to the truthful 13/13-executed-but-incomplete-per-D-13 position (edited, left uncommitted for the orchestrator)

## Decisions Made

See `key-decisions` in the frontmatter above.

## Deviations from Plan

None - Task 1 and Task 2 executed exactly as the plan specified. Task 3 followed the plan's own Task 3 instructions as refined by an explicit, more conservative mid-task instruction (STATE.md/ROADMAP.md left uncommitted rather than committed via the plan's original "commit what git tracks" rule, given the unrelated owner edits mixed into those same files) — not a deviation from the plan's intent (D-13 honesty, preserving unrelated in-flight edits), but a stricter execution of it.

**Numeric progress block intentionally left untouched:** `STATE.md`'s frontmatter `progress:` block (`total_phases`, `completed_phases`, `total_plans`, `completed_plans`, `percent`) was not recalculated by hand. That recomputation is `state.update-progress`'s job, which this plan was explicitly barred from running; a manual guess risked being wrong (a spot check found the existing phase-by-phase plan counts across 72-80 don't sum to the frontmatter's current `total_plans: 32` even before adding Phase 81's 13, so the field's basis isn't reconstructable from this plan's context alone). Left as-is rather than guessed.

**Pre-existing stale text not touched (out of this plan's explicit scope):** `ROADMAP.md`'s "**Counts:**" paragraph under the milestone-status table still reads "(Phase 81's 9 plans are not yet executed)" and "19/28 currently defined plans have summaries" — both now stale (Phase 81 has 13 plans, all with summaries). This sentence wasn't among the cells Task 3 was asked to update (plan-list ticks, milestone-status row, Progress row, Phase 81 ROADMAP notes), and fixing it would require recomputing the whole-project plan/requirement denominators this plan has no mandate or full context to verify. Flagged here rather than silently edited.

## Issues Encountered

None. The mid-task instruction that directed Task 2's resolution and Task 3's execution referenced two git commits (`e996322`, `09421ab`) and two `/walkthrough` journal directories as evidence; both were independently verified before being recorded (commits inspected via `git show`, full suite and ruff re-run from scratch, journal files read directly) rather than taken on claim, per this project's definition-of-done rule.

## User Setup Required

None - no external service configuration required. The two local scratch instances (ports 8584/8585) were stopped at the start of Task 3, confirmed down by both process check and connection-refused health checks.

## Next Phase Readiness

- Phase 81 is fully executed (13/13 plans) but **remains incomplete per D-13**: SONARRV5-02 is open, with every unverified-live scenario listed in `REQUIREMENTS.md` and `81-LIVE-MATRIX.md`'s "## Status" section. No requirement or ROADMAP line claims full v5 support.
- Next step is an owner review/merge decision for the `phase-81-sonarr-attribution` branch. If a v2.12 release is considered while SONARRV5-02 is still open, D-14 requires an explicit owner scope exception — this plan does not supply one.
- `.planning/REQUIREMENTS.md`, `.planning/STATE.md` and `.planning/ROADMAP.md` all carry this plan's edits in the working tree; `REQUIREMENTS.md` stays untracked per the existing convention, and `STATE.md`/`ROADMAP.md` are left uncommitted (unrelated owner edits mixed in) for the orchestrator to commit as isolated hunks.
- The Roadmaps page itself was not opened or checked in this session; the PLANNING-FORMAT.md checklist was applied by reading the files directly (milestone/phase-tick/status consistency), not by viewing the rendered page. This limitation is reported rather than any display being claimed as verified.

---
*Phase: 81-correct-sonarr-grab-attribution*
*Completed: 2026-10-21*

## Self-Check: PASSED

All four modified/created planning files confirmed present on disk (`81-LIVE-MATRIX.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, and this `81-09-SUMMARY.md`). Both referenced commits (`e996322`, `09421ab`) confirmed present in `git log --oneline --all`. Both referenced `/walkthrough` journal files confirmed present and read directly (not taken on claim). The full test suite (1999 passed) and `uv run ruff check triggarr/ tests/` (all checks passed) were independently re-run at current HEAD, not merely cited. Both local scratch instances (ports 8584/8585) confirmed stopped: no `run_server.py` processes remain, and both `/health` endpoints now return connection-refused. `.planning/REQUIREMENTS.md` confirmed untracked (`git ls-files --error-unmatch` fails as expected) and was edited but not staged.
