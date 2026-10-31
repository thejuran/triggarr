---
phase: 86-pilot-reference-record
plan: 02
subsystem: api
tags: [radarr, sonarr, lidarr, refresh-counts, malformed-records, screen-queue, tdd]

# Dependency graph
requires:
  - phase: 86-pilot-reference-record (plan 01)
    provides: "86-PILOT-RECORD.md pre-registration (D-15 bar, PILOT-02 method) committed before this plan's code exists"
provides:
  - "pilot-refresh-counts-skip-malformed branch (cut from origin/main d5a4467), tip H1 = 0318246, holding the Refresh-counts PR's product diff for the PILOT-01 new-PR slot and the PILOT-02 vibe-check-vs-paired comparison subject"
  - "refresh_radarr_counts/refresh_sonarr_counts/refresh_lidarr_counts now skip one malformed wanted record per item (via _screen_queue, reusing the scheduled cycles' exact pattern) instead of disconnecting the whole instance"
affects: [86-03, 86-04, 86-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Throwaway, never-persisted CycleTally() instantiated locally inside a refresh_*_counts helper so _screen_queue can log/count per-item skips without a signature change to the shared helper or a new dashboard warning"
    - "A refresh helper's returned tuple carries the base-screened list (post-_screen_queue, pre-filter) for a queue instead of the raw fetch, so a non-object record never flows out through the tuple"

key-files:
  created: []
  modified:
    - triggarr/search/engine.py
    - tests/test_refresh_counts.py
    - tests/test_malformed_records_client_path.py

key-decisions:
  - "Six pre-existing 'D-05 revision 2' tests (Radarr/Sonarr/Lidarr) used a malformed-shape fixture (non-iterable tags, non-dict artist/series, bare string record) purely as a mechanism to force the old whole-instance-disconnect path for a different feature (cutoff-side/missing-side fault isolation). Since D-02/D-02a now intercepts exactly those shapes before they reach the old broad except, these six were rewritten to force the same 'other unexpected fault' via monkeypatch (engine.filter_by_tag / engine.filter_monitored / engine.deduplicate_to_seasons) instead, preserving every original assertion and intent unchanged."
  - "Each refresh helper's cutoff tuple slot now returns the post-base-screen list instead of the raw fetched list (Radarr and Sonarr previously returned the raw fetch unconditionally); verified this doesn't break the one existing test asserting list-equality against the raw cutoff fetch, since that fixture was already well-formed."

requirements-completed: [PILOT-01]

# Metrics
duration: ~9min
completed: 2026-10-30
---

# Phase 86 Plan 02: Refresh Counts Skip-Per-Record Summary

**All three `refresh_*_counts` helpers now fetch with `allow_non_object_records=True` and screen every wanted-queue record through the shared `_screen_queue` helper, so one malformed Radarr/Sonarr/Lidarr record is skipped and logged instead of disconnecting the whole instance.**

## Performance

- **Duration:** ~9 min (commit-to-commit: RED at 20:25:34, GREEN at 20:28:04; total including the full-suite gate run (~90s) and branch setup: ~9 min)
- **Started:** 2026-10-30T20:20:00-04:00 (approximate, branch creation)
- **Completed:** 2026-10-30T20:29:00-04:00
- **Tasks:** 3/3 completed
- **Files modified:** 3 (1 product file, 2 test files)

## Accomplishments

- `refresh_radarr_counts`, `refresh_sonarr_counts`, `refresh_lidarr_counts` each fetch with `allow_non_object_records=True` (matching the scheduled cycles' `functools.partial` pattern) and insert `_screen_queue` calls immediately before every filter/tag/dedup step the matching `run_*_cycle` already screens before, so a malformed record is skipped and logged per item rather than aborting the whole refresh.
- A throwaway, never-persisted `CycleTally()` lets each helper reuse `_screen_queue` (whose `tally` parameter is required, not `Optional`) without touching the shared helper's signature and without surfacing any new dashboard warning (D-02/D-02a).
- Seven behavior tests (RED) pinned the new per-item-skip contract across Sonarr (cutoff and missing), Radarr (tag), Lidarr (new regression test), and the real-client non-object-record path (parametrized over all three apps) — all seven failed for the right reason (assertion, not collection error) before the implementation existed, confirming the TDD gate.
- Six guard tests (always green) pin that an invalid wanted-list envelope or an HTTP error from the wanted endpoint still disconnects the instance — enabling non-object records never widens the fetch-failure contract.
- Six pre-existing tests whose malformed-shape fixtures happened to double as triggers for the OLD disconnect path (for an unrelated feature — D-05's tag-unresolved/cutoff-survives-missing-fault guarantees) were updated to force the same "other unexpected fault" via `monkeypatch` instead, so their original intent and every original assertion survive the behavior change unmodified.
- Full suite (3279 passed, 1 unrelated opt-in skip) and `ruff check triggarr/ tests/` both passed with `HEAD` asserted at the pilot branch tip (H1) before the checkout moved back to the phase branch.

## Task Commits

Each task was committed atomically on `pilot-refresh-counts-skip-malformed` (cut from `origin/main` at `d5a4467`):

1. **Task 1 (RED): Rewrite the old-behavior tests and add the Lidarr filter-phase regression test** - `7f5680a` (test)
2. **Task 2 (GREEN): Screen per item in all three refresh helpers and update the failure contract** - `0318246` (feat)
3. **Task 3: Final-head gate on H1, then restore the phase checkout** - no commit (verification + checkout only)

No `refactor(86-02):` commit was needed — tests and ruff were clean after Task 2's implementation with no follow-up cleanup required.

**H1: `03182462100e9f71defc9408245410d2b99110a5`**

## Files Created/Modified

- `triggarr/search/engine.py` - All three `refresh_*_counts` helpers: FETCH phase now passes `allow_non_object_records=True`; FILTER/TAG(/DEDUP) phase inserts `_screen_queue` calls per queue stage (mirroring `run_radarr_cycle`/`run_sonarr_cycle`/`run_lidarr_cycle`'s exact screening chains) via a local throwaway `CycleTally()`; the existing broad `except (AttributeError, KeyError, TypeError)` is kept as the backstop for any other unexpected fault; FAILURE CONTRACT docstrings updated; each helper's cutoff tuple slot now returns the base-screened list instead of the raw fetch
- `tests/test_refresh_counts.py` - Three malformed tests renamed and rewritten to assert skip-and-stay-connected (Sonarr cutoff, Sonarr missing, Radarr tag); new Lidarr malformed-artist regression test added; six "D-05 revision 2" tests' fixtures switched from malformed-data-shape triggers to `monkeypatch`-forced faults
- `tests/test_malformed_records_client_path.py` - `test_refresh_counts_unchanged_for_non_object_record` renamed to `test_refresh_counts_skips_non_object_record` and parametrized over all three apps, driving the real client over `httpx.MockTransport`; two new parametrized guard tests (`test_refresh_counts_invalid_envelope_still_disconnects`, `test_refresh_counts_http_error_still_disconnects`) added; `test_wanted_fetch_default_still_rejects_non_object_records`'s docstring corrected to no longer name count refresh as a strict caller

## Decisions Made

- See `key-decisions` in frontmatter: the six "D-05 revision 2" test fixture rewrites and the cutoff-tuple-slot base-screening change.
- `skip_unreleased` defaults to `True` in `GeneralConfig`, so the Radarr test fixtures deliberately omit `digitalRelease`/`physicalRelease` fields (both-missing passes through per the existing `filter_unreleased_movies` contract) rather than needing to configure it off.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Six existing tests needed fixture changes to stay green under the new per-item-skip behavior**
- **Found during:** Task 1 (RED), while implementing the designated four test rewrites and tracing the new `_screen_queue` chains against the full existing test file
- **Issue:** `test_refresh_radarr_counts_skipped_missing_survives_cutoff_data_fault`, `test_refresh_radarr_counts_resolved_missing_still_cleared_on_its_own_data_fault`, `test_refresh_lidarr_counts_skipped_missing_survives_cutoff_data_fault`, `test_refresh_lidarr_counts_resolved_missing_still_cleared_on_its_own_data_fault`, `test_refresh_sonarr_counts_skipped_missing_survives_cutoff_data_fault`, and `test_refresh_sonarr_counts_skipped_cutoff_survives_missing_data_fault` all used a malformed-record shape (non-iterable `tags`, non-dict `artist`/`series`, or a bare string item) purely as a mechanism to force the OLD whole-instance-disconnect path, in service of testing an unrelated guarantee (Phase 79 D-05: a cutoff-side or missing-side fault must not erase the other queue's preserved/skipped counts). The plan's Task 1 action text explicitly said to leave these "tag-unresolved... tests... untouched," but once `_screen_queue` is reused in Task 2, these exact malformed shapes are now intercepted and skipped per item instead of raising — so each test's `result is None` / `connected is False` assertion would start failing, and the full suite would not be green at the Task 3 gate.
- **Fix:** Rewrote each test's fixture to force the same "other unexpected fault" via `monkeypatch.setattr(engine, <fn>, _boom)` on `filter_by_tag`, `filter_monitored`, or `deduplicate_to_seasons` (the exact function the malformed shape used to make raise), using well-formed records otherwise. Every original assertion, docstring intent, and D-05 guarantee under test is unchanged; only the fault-injection mechanism moved from "malformed data shape" to "monkeypatched function." Two of the six tests make a second refresh call after the fault is removed (`monkeypatch.undo()`), matching their original two-call shape.
- **Cost if wrong:** If this fixture correction were skipped or done incorrectly, the full-suite gate in Task 3 would fail (or, worse, silently stop testing the D-05 guarantee these tests exist for) — either blocking the plan from completing or leaving the tag-unresolved/cutoff-survives-fault contract unverified going forward.
- **Files modified:** `tests/test_refresh_counts.py`
- **Commit:** `7f5680a` (Task 1 / RED commit, since these are fixture-only changes that pass both before and after Task 2's implementation)

---

**Total deviations:** 1 auto-fixed (Rule 1 — six test fixtures updated to preserve coverage of a guarantee the plan didn't anticipate colliding with).
**Impact on plan:** Necessary to keep the full test suite green after the intended behavior change; no scope creep — no new behavior was added beyond what D-02/D-02a specify, only test *mechanism* was adjusted.

## Issues Encountered

None beyond the deviation above. One ruff line-length violation (123 > 120 chars) was caught by the pre-commit hook during the RED commit attempt and fixed inline before committing (not counted as a deviation — mechanical formatting, not a behavior or test-intent change).

## Next Phase Readiness

- `pilot-refresh-counts-skip-malformed` branch exists locally (not pushed), tip at H1 (`0318246`), ready for 86-03's paired BM+Codex review and the independent, same-head vibe-check comparison (PILOT-02).
- No PR opened yet — per the plan, this plan only produces the branch and H1; opening the PR, running reviews, and owner acceptance are 86-03/86-04's responsibility.
- The branch's merge-base with `origin/main` is exactly `origin/main`'s tip at cut time (`d5a4467`), confirming clean branch provenance for the Codex trust check.

---
*Phase: 86-pilot-reference-record*
*Completed: 2026-10-30*
