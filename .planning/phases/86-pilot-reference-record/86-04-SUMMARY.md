---
phase: 86-pilot-reference-record
plan: 04
subsystem: search-engine
tags: [pilot, refresh-counts, sonarr, batched-revision, bm-review, codex, vibe-check]

requires:
  - phase: 86-pilot-reference-record
    provides: "86-03 confirmed defect (BM WR-01 = vibe-check arch-001) with its proving test; owner-approved tally"
provides:
  - "H_final 1062097a7676fddcdde3caf500f96ba1ea04d65c on pilot-refresh-counts-skip-malformed (local, not pushed)"
  - "H_final review-checkpoint record: BM standard, paired Codex complete (0 findings), routine vibe-check pass 2 (carried defect resolved on recheck)"
affects: [86-07]

key-files:
  modified:
    - triggarr/search/engine.py
    - tests/test_refresh_counts.py
    - .planning/phases/86-pilot-reference-record/86-REVIEW-EVIDENCE.md
  created:
    - .planning/phases/86-pilot-reference-record/86-REVIEW-refresh-1062097a7676.md
    - .planning/phases/86-pilot-reference-record/vibe-check/1062097a7676-refresh-routine.{md,json}
    - .planning/phases/86-pilot-reference-record/codex/1062097a7676-pilot-refresh-final-a1.{prompt.txt,meta.json,jsonl,last.json,status.json,pytest.txt}

key-decisions:
  - "Only the one confirmed defect was fixed. Unproven findings stayed as labeled debt, per the plan and the approved tally."
  - "Routine vibe-check ran as stock pass 2: the H1 state existed, so it reviewed H1..H_final and rechecked every carried H1 finding at H_final. It was not forced into a fresh full pass."
  - "BM SA-01 (skips visible only in System Logs) was recorded as already decided by owner D-02 ('No new dashboard warning'), not re-asked."
  - "BM H_final WR-01 is the H1 WR-02 mismatch with more examples. It stays nonblocking debt: no caller reads the returned cutoff list, so this is not a new confirmed defect and there is no owner fix-vs-debt decision."

requirements-completed: []

duration: ~25 min
completed: 2026-10-30
---

# Phase 86 Plan 04: Refresh-counts batched revision and final-head reviews

**One batched revision fixed the single confirmed defect. Fresh BM, paired Codex and routine vibe-check on the final head found no new confirmed defect.**

## Revision (Task 1)

- `a794c8a` test(86-04): `test_refresh_sonarr_counts_unmonitored_tzless_airdate_not_logged_as_malformed[missing|cutoff]`. It failed on H1 for both queues ("Sonarr: Skipped 1 … malformed date data (ids=[5])").
- `1062097` fix(86-04): `refresh_sonarr_counts` calls `filter_monitored` before the `airDateUtc` screen on both chains, matching `run_sonarr_cycle`. Findings: `bm:03182462100e:WR-01`, vibe-check arch-001 (+bugs-001, imp-001).
- Final-head gate, with HEAD asserted at `H_final: 1062097a7676fddcdde3caf500f96ba1ea04d65c` before and after: `uv run pytest tests/ -x -q` gave 3281 passed, 1 skipped; `uv run ruff check triggarr/ tests/` was clean.
- `git diff --name-only origin/main..pilot-refresh-counts-skip-malformed` lists only `triggarr/search/engine.py`, `tests/test_refresh_counts.py` and `tests/test_malformed_records_client_path.py`. Both commits are plain `commit:` reflog entries. Nothing was pushed.

## Final-head reviews (Task 2)

- **BM (standard/standard):** 0 critical, 2 warnings, 3 info, 1 set aside.
  - WR-01: the returned cutoff list is not fully screened. This is H1 WR-02 again, nonblocking.
  - WR-02: the filter chains are duplicated. Design debt.
  - SA-01: settled by D-02.
- **Codex `pilot-refresh-final` a1:** complete, verdict no-findings, inspected head = H_final.
- **Routine vibe-check (pass 2):**
  - The Sonarr ordering finding was resolved on recheck by architecture, bugs and impact.
  - Test-sufficiency kept the two H1 test-gap rows open: Warning 82 (Sonarr missing-tag path untested) and Medium 72 (returned cutoff list not asserted).
  - Codex (inside vibe-check) approved.
- No new confirmed defect, so the Triage rule raises no owner decision.

Dispositions, an "Original vs. refreshed findings" table and per-reviewer timings are in `86-REVIEW-EVIDENCE.md` under `### Head 1062097a7676…`. Its "PR comment" line is left for 86-07.

## Deviations

- While on the pilot branch, the phase folder had to be recreated (`mkdir -p`) for untracked outputs. Its tracked files exist only on the phase branch.
- The vibe-check phase files were not re-Read on this second invocation: the same plugin version's files were already loaded in this session for the H1 run.

## Commits

- `a794c8a` test(86-04): reproduce confirmed review findings on the Refresh-counts PR (pilot branch)
- `1062097` fix(86-04): address confirmed review findings on the Refresh-counts PR (pilot branch)
- `786c59b` docs(86-04): final-head review record for the Refresh-counts PR
