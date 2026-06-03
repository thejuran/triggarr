---
phase: 69-code-track-hardening
plan: "03"
subsystem: search-scheduler
tags: [safety-03, chard-02, chard-03, tdd, refactor, counter-unification]
dependency_graph:
  requires: []
  provides: [_run_one_cycle-helper, manual-search-counter-parity]
  affects: [triggarr/search/scheduler.py, triggarr/web/routes.py, tests/test_scheduler.py, tests/test_web.py]
tech_stack:
  added: []
  patterns: [shared-helper-under-held-lock, mechanical-lift-extraction, tdd-red-green-refactor]
key_files:
  created: []
  modified:
    - triggarr/search/scheduler.py
    - triggarr/web/routes.py
    - tests/test_scheduler.py
    - tests/test_web.py
decisions:
  - "D-01: extracted _run_one_cycle as shared helper; both callers (job() and search_now) hold search_lock externally; helper acquires NO lock"
  - "D-02: removed TODO(SAFETY-03) block and bypass comment from _evaluate_cycle_outcome; replaced with accurate one-liner"
  - "D-03: mechanical lift of lines 163-218 from job() into _run_one_cycle; call order preserved (cycle_fn → _evaluate_cycle_outcome → persistence)"
  - "D-04: three new tests added to test_scheduler.py; no existing test deleted or skipped"
  - "Rule 1 auto-fix: updated 3 test_web.py tests patching the now-removed routes.run_radarr_cycle to scheduler.run_radarr_cycle; added search_failures/search_lock_holder/persistence_degraded to both test fixtures"
metrics:
  duration: "~20 minutes"
  completed: "2026-06-02T19:09:49Z"
  tasks_completed: 3
  files_modified: 4
---

# Phase 69 Plan 03: Shared `_run_one_cycle` helper unifying manual + scheduled failure-counter semantics (SAFETY-03) Summary

Resolved P68-FI-003 / SAFETY-03 (CHARD-02/03): extracted `_run_one_cycle` as a shared cycle body called by both the APScheduler `job()` and the manual `search_now` route so manual-search failures now increment and successes reset `app.state.search_failures[job_id]` identically to scheduled cycles.

## What Was Built

### `triggarr/search/scheduler.py` — new `_run_one_cycle` helper

Added `async def _run_one_cycle(app, app_name, instance_name, client, instance_config, state_path, get_tags_fn) -> None` immediately before `_on_job_error`. The helper:

- Constructs `job_id = f"{app_name}_{instance_name}_search"` and dispatches to the correct cycle function via the same `cycle_fns` dict used by the original `job()`.
- Contains the three-phase body lifted verbatim from `job()` lines 163-218: narrow-tuple cycle catch calling `_record_cycle_failure`, `_evaluate_cycle_outcome` reading updated state, and the dedicated OSError/persistence try/except that sets `persistence_degraded` and re-raises.
- **Acquires NO lock.** Both callers hold `app.state.search_lock` before entering the helper; a second acquisition of the single-worker `asyncio.Lock` would deadlock.

`make_search_job`'s `job()` closure was updated to call `_run_one_cycle(...)` in place of the lifted inline body. The tracking check block (lines 221-269) stays in `job()` only — manual searches do not run tracking (Open Question 1 resolution). Observable scheduled-path behavior is byte-for-byte equivalent; all 6 existing tests confirm this.

### `triggarr/web/routes.py` — `search_now` routed through `_run_one_cycle`

- Added `_run_one_cycle` to the scheduler import at line 50.
- Removed the now-unused `run_radarr_cycle`, `run_sonarr_cycle`, `run_lidarr_cycle` imports (dispatch ownership moved to `_run_one_cycle`).
- Removed the `cycle_fns` / `cycle_fn` dispatch block and the flat `cycle_fn(...)` + `save_state(...)` call inside the lock.
- Replaced with `await _run_one_cycle(request.app, app_name, instance_name, client, instance_config, request.app.state.state_path, _get_tags_cached)` inside the **existing** `async with request.app.state.search_lock:` — no second lock acquisition.
- The outer `try/except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` wraps `_run_one_cycle`, logs the failure (CR-01 sanitization split), and falls through to `templates.TemplateResponse(...)` — the handler **always returns HTTP 200 + app_card partial**, never 500 (RESEARCH Pitfall 3 preserved).

### `tests/test_scheduler.py` — 3 new CHARD-03 tests

Added `_build_manual_app` helper (returns `(app, real_client, instance_config)` instead of `(app, job)`) and three tests:

- `test_search_now_failure_counter_increment`: two `_run_one_cycle` calls each inside `async with app.state.search_lock:` with a 503-returning MockTransport → counter == 2 and `connected is False`.
- `test_search_now_failure_counter_resets_on_success`: fail then success (cycle-counter dict controls handler) → counter trajectories 1 → 0.
- `test_search_now_failure_returns_card_200`: drives the actual `search_now` route via `TestClient` + 503 MockTransport → asserts HTTP 200 + card body (never 500). HTTP-contract regression guard.

No `_record_cycle_failure` or `_evaluate_cycle_outcome` patches — counter logic exercised end-to-end.

### `tests/test_web.py` — fixture and patch updates (Rule 1 auto-fix)

Updated the `test_app` and `multi_instance_app` fixtures to add `app.state.search_failures = {}`, `app.state.persistence_degraded = False`, and `app.state.search_lock_holder = None` (required by `_run_one_cycle` path now called from `search_now`). Updated 3 tests that patched the now-removed `triggarr.web.routes.run_radarr_cycle` to patch `triggarr.search.scheduler.run_radarr_cycle` (where dispatch now lives).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated 3 test_web.py tests patching removed symbol**
- **Found during:** Task 2 (GREEN) - ruff reported F401 unused imports on cycle functions; test_web.py tests patched `triggarr.web.routes.run_radarr_cycle` which no longer exists after the import removal.
- **Issue:** Removing `run_radarr_cycle/sonarr/lidarr` imports from routes.py broke 3 existing test_web.py tests that patched them at that namespace.
- **Fix:** Updated patch targets to `triggarr.search.scheduler.run_radarr_cycle` (where dispatch lives); added missing state attributes to both test fixtures.
- **Files modified:** `tests/test_web.py`
- **Commit:** aecaf5a

**2. [Rule 1 - Bug] Fixed `test_search_now_failure_counter_resets_on_success` handler logic**
- **Found during:** Task 2 (GREEN) first run.
- **Issue:** Initial test used `call_count["n"]` which incremented on every HTTP request including retries; the retry hit the "success" response before the second explicit cycle call, causing counter to be 0 after the first `_run_one_cycle` call.
- **Fix:** Changed to explicit `cycle["n"]` dict set by the test before each call (same pattern as `test_failure_counter_resets_on_success`).
- **Files modified:** `tests/test_scheduler.py`
- **Commit:** aecaf5a

## TDD Gate Compliance

| Gate | Commit | Verified |
|------|--------|----------|
| RED — `test(69-03)` | 75944b8 | ImportError on `_run_one_cycle` (not yet defined) |
| GREEN — `feat(69-03)` | aecaf5a | All 9 scheduler tests + 121 web tests pass |
| REFACTOR — `refactor(69-03)` | d423a41 | Full suite 968 tests pass; TODO removed |

## Verification Results

```
grep -rn "TODO(SAFETY-03)" triggarr/    → nothing (PASS)
_run_one_cycle body: no search_lock acquisition (PASS)
uv run pytest tests/test_scheduler.py -x -q    → 24 passed (6 existing + 3 new + 15 others)
uv run pytest tests/ -k "search_now and failure" -x    → 3 passed
uv run pytest tests/ -x -q    → 968 passed
uv run ruff check triggarr/ tests/    → All checks passed
uv run pytest tests/test_web.py -k "concurrent_settings_save_serialized" -x    → 1 passed
```

Test count: 6 pre-existing scheduler failure-counter tests + 3 new manual-path tests = 9 scheduler failure-counter tests total.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundary changes introduced. The change is strictly internal to the cycle execution body under the existing `search_lock`. The `_run_one_cycle` helper receives an already-constructed `ArrClient` (no new `get_secret_value()` calls). T-69-07/08/09/10 from the plan's threat register are all mitigated by the implementation.

## Self-Check: PASSED

- [x] `69-03-SUMMARY.md` exists at `.planning/phases/69-code-track-hardening/69-03-SUMMARY.md`
- [x] RED commit 75944b8 exists: `test(69-03): add failing manual-search counter + HTTP-200-contract tests for _run_one_cycle`
- [x] GREEN commit aecaf5a exists: `feat(69-03): extract _run_one_cycle (no lock acquire); route manual + scheduled searches through it (SAFETY-03)`
- [x] REFACTOR commit d423a41 exists: `refactor(69-03): remove resolved TODO(SAFETY-03) bypass notes`
- [x] `grep -rn "TODO(SAFETY-03)" triggarr/` returns nothing
- [x] `_run_one_cycle` body contains no `search_lock` acquisition
- [x] 968 tests pass; ruff clean
