---
phase: 90-removed-instance-pending-search-lifecycle
plan: 08
subsystem: testing
tags: [lifecycle, end-to-end, stats, planning-docs]
requires:
  - phase: 90-removed-instance-pending-search-lifecycle
    provides: close-out, startup sweep, stable-ID tracking, in-lock revalidation (plans 90-01..07)
provides:
  - Three-app end-to-end lifecycle tests and the D-09 same-name stats verification
  - RMINST wording widened to Sonarr, Radarr and Lidarr in requirements, roadmap and state
  - Maintenance backlog resolution notes and the retention-by-owner-decision entry
affects: [phase 90 review, next CHANGELOG entry]
tech-stack:
  added: []
  patterns: [one scenario per app chaining the real functions on a migrated database]
key-files:
  created: [tests/test_removed_instance_lifecycle.py]
  modified: [.planning/REQUIREMENTS.md, .planning/ROADMAP.md, .planning/STATE.md, .planning/backlog/MAINTENANCE.md]
key-decisions:
  - "No CHANGELOG entry in this phase; release-note material is recorded below instead"
  - "All four RMINST requirements are left Pending until the phase is reviewed and merged"
requirements-completed: []
duration: 25min
completed: 2026-11-18
---

# Phase 90 Plan 08: Lifecycle verification and planning wording Summary

One new test file proves removal, name reuse, tracking, the pending cap, History data and dashboard stats end to end for Sonarr, Radarr and Lidarr, and the planning files now state the widened three-app scope.

## Commits
- 915629ef test(90-08): end-to-end removed-instance lifecycle for all three apps
- 03b1bd48 docs(90-08): widen RMINST wording to all three apps and update the backlog

## Verification (observed)
- `uv run pytest tests/test_removed_instance_lifecycle.py -q`: 19 passed (6 parametrized tests x 3 apps + 1). `ruff` on the file clean. These are verification tests over finished code; they passed when written (no RED phase, as the plan states).
- No file under `triggarr/` changed in this plan.
- Task 2 verify: `tests/test_docs_accuracy.py` + `tests/test_repository_hygiene.py` 8 passed; the grep checks: no `[x] RMINST`, no ticked Phase 90, the 🔨 count in ROADMAP.md unchanged at 2 (list line plus active-milestone heading, one milestone), STATE.md diff limited to `last_updated` and the Phase 90 table row in the task commit, `CHANGELOG.md` untouched.
- Phase gate: `uv run pytest tests/ -x -q` 3517 passed, 1 skipped; `uv run ruff check triggarr/ tests/` clean; `git diff --quiet main -- pyproject.toml uv.lock` exit 0.

## D-09 verification result
- Sonarr: PASS. A new instance under the old name (new stable ID) shows grab rate None, overall rate None, all lifetime totals 0, time-to-grab None, historical flags False, despite a credited grab, a failed row, an `instance_removed` row and a legacy name-keyed lifetime row (found-count 7) for the old instance; after its own credited grab it shows exactly 100.0 and found-count 1.
- Radarr: PASS. Same observations.
- Lidarr: PASS. Same observations.
No defect found, so no D-09 backlog entry and no xfail.

Residual b (recorded in tests): the database helper's name-only mode (`instance_id="Main"` with no stable ID) does include the old instance's figures. No view reaches it: in `partial_stats_row` a non-empty `instance` parameter either resolves to an enabled instance with a stable ID (scoped by `app` and `instance_stable_id=cfg.id`) or is rejected with 400, so the `instance_id=instance_id` call only ever runs with None (the unfiltered aggregate). The unfiltered view intentionally keeps removed instances' lifetime totals (D-09), pinned by `test_unfiltered_stats_view_keeps_removed_instance_lifetime_totals`.

## Requirement status reconciliation
All RMINST-01..04 are Pending (unticked, traceability "Pending"). Reasoning: the plan forbids this plan from ticking anything, and docs/PLANNING-FORMAT.md says to tick only when a phase is finished (merged/verified); Phase 90 is executed but not reviewed or merged. Delivered code does cover all four (01: 90-02/04/05; 02: 90-01/03/07; 03: 90-03/07 plus this plan's tests; 04: 90-02/06), and the lifecycle test confirms them, but ticking waits for the phase review. RMINST-02 had been ticked Complete by an earlier plan; I reverted it to Pending (checkbox and traceability row) for consistency. The 90-03 SUMMARY's `requirements-completed: [RMINST-03]` is left as that plan's historical record; it does not mean the requirement is closed phase-wide.

## Release-note material (for the next CHANGELOG entry)
- Searches still pending when an instance is removed now end as "Instance removed" in History and the activity rail, with a filter option.
- A new instance that reuses a removed instance's name no longer checks or takes credit for the old instance's searches (Radarr and Lidarr previously did).
- At the first start after upgrading, pending searches left behind by previously removed instances are closed the same way.
- These searches are left out of grab-rate figures.
- A scheduled or manual search that was waiting to run when its instance was removed no longer runs.

## Deviations from Plan
**1. [Rule 1 - Test fault] Raw lifetime_stats insert needed `last_reset_at`** (Task 1): the legacy name-keyed row insert violated a NOT NULL column; added the timestamp. Cost if wrong: test-only.

**2. [Reconciliation] RMINST-02 reverted from Complete to Pending**, per the lead's reconciliation instruction and the no-tick rule above. Cost if wrong: re-tick at phase close.

**3. [Bookkeeping] STATE.md plan-position update after the task commit** (see below), done by hand without bm-sdk writers; percent set from phases (3 of 6 = 50) because the plan-based figure (93) misrepresented a six-phase milestone. Cost if wrong: cosmetic on the Roadmaps card.

## Roadmaps page check
The Roadmaps page cannot be opened from the executor, so the display (item 6 of the PLANNING-FORMAT checklist) was not verified. Checklist items 1-5 were checked by reading the files: `last_updated` refreshed, `Phase:` starts with 90, one 🔨 milestone (v2.14) matching STATE, no phase ticked, status says executing.

## Known Stubs
None.

## Self-Check: PASSED
tests/test_removed_instance_lifecycle.py exists; commits 915629ef and 03b1bd48 exist.
