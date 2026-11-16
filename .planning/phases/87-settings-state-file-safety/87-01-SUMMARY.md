---
phase: 87-settings-state-file-safety
plan: 01
subsystem: api
tags: [fastapi, asyncio, atomic-write, loguru, concurrency]

# Dependency graph
requires: []
provides:
  - "remove_instance reads settings and re-checks existence inside search_lock, builds the post-removal Settings via model_copy, writes it with _atomic_toml_write, and only swaps live settings in and runs cleanup after the write succeeds"
  - "_atomic_toml_write accepts a keyword-only log_failure flag (default True) so a caller that logs its own contextual error can suppress the writer's generic line"
  - "A failed removal returns the fixed D-05 message (escaped instance name, no internal detail): 200 for htmx, 500 for a direct POST"
  - "Post-save tidy-up steps (scheduler job removal, client close) are isolated so one failing step never blocks another or turns a completed removal into a 500"
affects: [87-02, 90]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "read-under-lock, build-copy, write, swap-after-success (mirrors add_instance/save_settings)"
    - "keyword-only log_failure flag on a shared writer so one call site can own its own contextual error log"
    - "always-200-for-htmx / non-2xx-for-direct-POST failure response, no HX-Redirect, D-05 fixed wording"
    - "each post-commit cleanup step wrapped in its own try/except Exception with logger.error, no re-raise"

key-files:
  created: []
  modified:
    - triggarr/web/routes.py
    - triggarr/config.py
    - tests/test_web.py
    - tests/test_config.py

key-decisions:
  - "Followed 87-CONTEXT.md D-02/D-03/D-07/D-15/D-16 and 87-PATTERNS.md target shape as written; no re-validation via SettingsModel added to remove_instance since deleting a key cannot create invalid config (Pitfall F)"
  - "Chose the htmx-200 / plain-500 split for the failure response per Claude's Discretion in 87-CONTEXT.md, matching 87-RESEARCH.md's htmx 2.0.8 responseHandling finding"

patterns-established:
  - "log_failure=False on _atomic_toml_write: a caller passes this when it logs its own richer contextual error, so one failed write produces exactly one error-level log entry overall"

requirements-completed: [CONSIST-01, CONSIST-02]

# Metrics
duration: 25min
completed: 2026-11-15
---

# Phase 87 Plan 01: Safe Instance Removal Summary

**Reordered `remove_instance` to read-under-lock/build/write/swap, added a suppressible `log_failure` flag to `_atomic_toml_write`, and gave failed removals the fixed D-05 message with one contextual error log, independent of post-save cleanup failures.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-11-15T22:51:00Z (approx, first test run)
- **Completed:** 2026-11-15T22:59:29Z
- **Tasks:** 3
- **Files modified:** 4 (`triggarr/web/routes.py`, `triggarr/config.py`, `tests/test_web.py`, `tests/test_config.py`)

## Accomplishments

- `remove_instance` no longer mutates live settings before the write succeeds: the settings read, the not-found re-check, and the delete-and-copy all happen inside `search_lock`, and `request.app.state.settings` is only swapped in after `_atomic_toml_write` returns. A failed write now leaves settings, the scheduler job, the client registry, the state entry and the tag-cache entry exactly as they were (CONSIST-01, D-02, D-03).
- Two concurrent removals of different instances both persist, live and on disk; two concurrent removals of the same instance resolve to one success and one existing 400 "not found", with the client closed exactly once -- proven by lock-held concurrency tests using `httpx.AsyncClient` + `ASGITransport` and a `lock._waiters` spin-wait (T-87-03b).
- `_atomic_toml_write` gained a keyword-only `log_failure: bool = True` parameter; `remove_instance` is the only caller that passes `log_failure=False`, since it logs its own one-line contextual error (app, instance, exception type and message) and the writer's generic "Config write failed" line would otherwise duplicate it (D-07).
- A failed removal now returns the exact fixed sentence from D-05 (`'<name>' was not removed: the settings file could not be saved. Nothing was changed. Check the Triggarr log for details.`), with the instance name `html.escape`d: 200 for an htmx request (no `HX-Redirect`, so htmx's default `responseHandling` swaps it into the row target) and 500 for a direct POST. No internal detail (exception text, path, exception type) ever reaches the response body (T-87-01, T-87-02).
- Post-save tidy-up is now resilient: the scheduler-job removal and the post-lock `client.close()` are each wrapped in their own `try/except Exception`, logging the app/instance/reason without re-raising. A failing tidy-up step no longer turns a completed removal into a 500 -- the user still sees the normal success response, and every other step still runs (D-15, D-16).

## Task Commits

Each task's RED/GREEN steps were committed atomically:

1. **Task 1: Read-under-lock, write-before-mutate reorder with full-postcondition and concurrency regression tests**
   - `0be5a730` test(87-01): add failing tests for removal write-failure and same-instance race
   - `2791c75f` fix(87-01): write settings before mutating live state in remove_instance
2. **Task 2: One error log entry (real writer) and the fixed D-05 failure response**
   - `599d56b4` test(87-01): add failing tests for removal failure log and message
   - `95a120ef` feat(87-01): one error log and fixed not-removed message on failed removal
3. **Task 3: Independent post-save tidy-up steps**
   - `6ac79c27` test(87-01): add failing tests for removal tidy-up resilience
   - `5d021e8a` fix(87-01): keep removal tidy-up steps independent

_Note: Task 1's GREEN step had an intermediate scratch edit (in-place delete replaced with a copy-and-write, settings read still before the lock) that was deliberately not committed -- it exists only as RED evidence for the different-instance concurrency test, per the plan's `<action>`. The committed `fix` already contains the final, fully-locked shape._

## Per-Test Pre-Fix Outcomes (D-01)

**Task 1 RED (against the original, unfixed code):**

| Test | Pre-fix outcome | Matches plan prediction |
|------|------------------|---------------------------|
| `test_remove_instance_write_failure_keeps_live_state[plain]` | FAILED -- `AssertionError: assert '4K' in {...}`. `del instances[instance_name]` ran before the write, so the patched `OSError` left "4K" already removed from live settings. | Yes |
| `test_remove_instance_write_failure_keeps_live_state[htmx]` | FAILED -- same assertion, same cause. | Yes |
| `test_remove_instance_concurrent_same_instance_second_is_not_found` | FAILED -- `KeyError: '4K'` raised from `del instances[instance_name]` inside the route (both queued requests passed the pre-lock not-found check; the first request's `del` succeeded, the second's raised `KeyError`, which propagated out of `asyncio.gather` as an uncaught exception rather than ever producing the expected `[303, 400]` pair). | Yes |
| `test_remove_instance_concurrent_removals_both_persist` | PASSED (1 passed) -- the in-place delete on one shared dict meant no stale snapshot existed yet. | Yes |

**Task 1 GREEN step 1 (intermediate scratch, not committed): settings read still before the lock, delete replaced with copy-and-write**

| Test | Outcome | Matches plan prediction |
|------|---------|---------------------------|
| `test_remove_instance_concurrent_removals_both_persist` | FAILED -- `AssertionError: assert '4K' not in {...}`. The second request's stale pre-lock snapshot (read before the first request's lock acquisition) still contained "4K", so its write resurrected it. | Yes -- this is the different-instance test's recorded RED evidence per the plan's `<action>` instructions. |

After moving the settings read and not-found check inside the lock (GREEN step 2, the committed fix), both concurrency tests and the write-failure test pass, along with all 6 pre-existing `test_remove_instance_*` tests (unmodified).

**Task 2 RED (against Task 1's committed code):**

| Test | Pre-fix outcome | Matches plan prediction |
|------|------------------|---------------------------|
| `test_atomic_toml_write_log_failure_false_suppresses_primary_line` | FAILED -- `TypeError: _atomic_toml_write() got an unexpected keyword argument 'log_failure'`. | Yes |
| `test_remove_instance_real_write_failure_logs_one_error` | FAILED -- `len(records) == 1` passed, but `assert "radarr" in message` failed: the one ERROR record was the writer's own generic "Config write failed: {path} - {exc}" line, which names neither the app nor the instance. | Yes |
| `test_remove_instance_write_failure_htmx_shows_message` | FAILED -- interim response was `500` with body `"Instance was not removed"`, not `200` with the D-05 sentence. | Yes |
| `test_remove_instance_write_failure_plain_returns_500` | FAILED -- status code already matched (`500 == 500`), but `response.text == "Instance was not removed"` did not equal the D-05 sentence. | Yes |
| `test_remove_instance_write_failure_escapes_name` | FAILED -- `assert response.status_code == 200` failed (`500 == 200`); the interim response never echoes the instance name at all. | Yes |
| `test_remove_instance_write_failure_no_internal_detail` | PASSED -- the interim body `"Instance was not removed"` already contains none of the forbidden strings. Recorded as an **existing-passing safety guard** (T-87-01), not a new failing regression, per the plan's `<action>`. | Yes |

**Task 3 RED (against Task 2's committed code):**

| Test | Pre-fix outcome | Matches plan prediction |
|------|------------------|---------------------------|
| `test_remove_instance_scheduler_failure_still_completes` | FAILED (not captured as a formal assertion failure message in this run but confirmed failing via the paired run below: status was `500`, not `200` with `HX-Redirect`) -- `scheduler.remove_job` raising `RuntimeError` propagated uncaught through the route. | Yes |
| `test_remove_instance_close_failure_still_succeeds` | FAILED -- `assert response.status_code == 303` -> `AssertionError: assert 500 == 303`. `client.close()` raising propagated uncaught. | Yes |

All RED runs above were captured by running each new test (or small group) individually against the code state at that point in the plan, before the corresponding GREEN commit.

## Files Created/Modified

- `triggarr/web/routes.py` -- `remove_instance` reordered to read/re-check-under-lock -> build copy -> write (with `log_failure=False`) -> swap -> isolated cleanup; new module-level `_removal_failed_response` helper; `import functools` added.
- `triggarr/config.py` -- `_atomic_toml_write` gained `*, log_failure: bool = True`; the primary "Config write failed" log line is now conditional on it. No other branch (dir-fsync warning, temp-cleanup error, unexpected-error branch) changed.
- `tests/test_web.py` -- 10 new tests covering write-failure postconditions, both concurrency races, the real-writer one-error-entry guarantee, the D-05 response content/status/escaping, and post-save cleanup resilience. Added `import errno` and `from loguru import logger` to the module's top-level imports.
- `tests/test_config.py` -- 1 new test (`test_atomic_toml_write_log_failure_false_suppresses_primary_line`); `test_atomic_toml_write_logs_os_replace_failure` is unmodified (verified via `git diff`, additions only).

## Decisions Made

- No `SettingsModel(**config_dict)` re-validation added to `remove_instance` (unlike `add_instance`): removing a key cannot produce an invalid config, so the extra validation step and its untestable-in-practice `ValidationError` branch were deliberately omitted, per 87-RESEARCH.md's resolved Open Question and the plan's explicit instruction.
- The htmx-200 / direct-POST-500 split for the failure response (Claude's Discretion in 87-CONTEXT.md) was implemented exactly as the plan's interfaces section specified, matching `change_password`'s "always-200-for-htmx, differentiate by content" precedent while keeping a direct POST honest with a non-2xx status.
- `add_instance` and `save_settings` were left unchanged -- they already read settings before taking the lock too, but fixing them is out of scope for this plan (87-02 Task 2 records this in MAINTENANCE.md per D-13).

## Deviations from Plan

None - plan executed exactly as written, including the Task 1 scratch-and-discard intermediate step used purely to produce the different-instance concurrency test's RED evidence.

## Assumption Drift (advisory)

None.

## Issues Encountered

None. One self-correction during implementation: the inline comment originally added next to the `log_failure=False` call site literally contained the substring `log_failure=False`, which would have made `grep -n "log_failure=False" triggarr/web/routes.py` return two lines instead of the one required by the plan's acceptance criteria. Reworded the comment before committing; verified with the exact grep command afterward.

## Threat Flags

None beyond what 87-01-PLAN.md's own `<threat_model>` already covers (T-87-01 through T-87-06) -- no new network endpoint, auth path, file-access pattern, or schema change was introduced.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `remove_instance`'s response contract (D-05 message, htmx-200/direct-500 split, no `HX-Redirect` on failure) is now stable for 87-02 to wire a row-level display on top of in `settings.html`.
- The lock audit (`tests/audit_lock_coverage.py`) still reports `covered: 8 / 8, uncovered: 0`.
- Full suite: `3294 passed, 1 skipped` (the skip is pre-existing and unrelated to this plan); `ruff check triggarr/ tests/` reports `All checks passed!`.
- No blockers for 87-02 or Phase 90 (both build on this route).

---
*Phase: 87-settings-state-file-safety*
*Completed: 2026-11-15*

## Self-Check: PASSED

- `.planning/phases/87-settings-state-file-safety/87-01-SUMMARY.md` -- FOUND
- `0be5a730` (test: removal write-failure and same-instance race) -- FOUND
- `2791c75f` (fix: write settings before mutating live state) -- FOUND
- `599d56b4` (test: removal failure log and message) -- FOUND
- `95a120ef` (feat: one error log and fixed not-removed message) -- FOUND
- `6ac79c27` (test: removal tidy-up resilience) -- FOUND
- `5d021e8a` (fix: keep removal tidy-up steps independent) -- FOUND
