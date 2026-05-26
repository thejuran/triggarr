---
phase: 65-scheduler-hardening-resilience
plan: 02
subsystem: scheduler
tags: [scheduler, config, failure-counter, observability, durability, safety-03]

# Dependency graph
requires:
  - phase: 65-scheduler-hardening-resilience
    plan: 01
    provides: narrowed make_search_job outer except + EVENT_JOB_ERROR listener (hook points 65-02 builds on)
provides:
  - GeneralConfig.max_consecutive_failures field (pydantic-bounded 1..100, default 5)
  - DEFAULT_CONFIG commented template line for max_consecutive_failures
  - POST /settings safe_int handler + GET context entry
  - settings.html number input (min=1 max=100)
  - app.state.search_failures dict[str, int] init in create_lifespan
  - app.state.persistence_degraded bool init in create_lifespan
  - _record_cycle_failure(app, job_id, app_name, reason) helper (WARNING/ERROR escalation)
  - _evaluate_cycle_outcome(app, app_name, instance_name, job_id) helper (reads engine connected flag)
  - make_search_job split: narrow-tuple cycle catch (OSError REMOVED) + post-cycle outcome eval + dedicated persistence try/except (OSError, aiosqlite.Error) that logs ERROR, sets persistence_degraded=True, and re-raises
  - 1 new pydantic default-value test + 6 new scheduler tests (outage-driven + raise-driven + threshold + reset + per-instance + persistence)
affects: [65-03-PLAN.md, 65-04-PLAN.md]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cycle-outcome counter pattern: scheduler reads state[app][inst]['connected'] post-cycle, not raised exceptions"
    - "Split try/except for cycle vs persistence so durability failures are never counted as transient blips"
    - "httpx.MockTransport real-cycle integration tests (drive run_radarr_cycle for real, not patch it)"

key-files:
  created: []
  modified:
    - triggarr/models/config.py
    - triggarr/config.py
    - triggarr/web/routes.py
    - triggarr/templates/settings.html
    - triggarr/search/scheduler.py
    - tests/test_config.py
    - tests/test_scheduler.py

key-decisions:
  - "Codex finding 1 closed via option (b) from REVIEWS.md: scheduler reads state[app][inst]['connected'] after each cycle to detect real *arr outages. No engine contract change."
  - "Codex finding 2 closed by splitting persistence into its own try/except (OSError, aiosqlite.Error) with ERROR log + persistence_degraded flag + re-raise; OSError REMOVED from the cycle-error catch."
  - "Used Field(default=5, ge=1, le=100) over @field_validator for terseness — out-of-bounds values still raise pydantic.ValidationError as required by the test."
  - "Counter escalation uses >= (count == threshold IS ERROR) per RESEARCH A6 — the threshold represents 'the Nth failure escalates'."
  - "Counter reset (cycle success) happens BEFORE persistence so a cycle-success counter reset is independent of persistence outcome (which sets its own persistence_degraded flag)."
  - "Manual search-now reset behavior DEFERRED — search_now in routes.py bypasses make_search_job; a TODO(SAFETY-03) is documented in _evaluate_cycle_outcome for a follow-up plan to extract a shared cycle helper."
  - "persistence_degraded is observable state ONLY in this phase — no /health endpoint surfacing yet (Codex finding 2 explicitly scoped to flag-only)."
  - "Outage-driven tests use a real RadarrClient wired to httpx.MockTransport (pattern from tests/test_clients.py:83-97) and DO NOT patch run_radarr_cycle. Tracking and save_state ARE patched in those tests to keep the AsyncMock db lightweight."

patterns-established:
  - "Module-level scheduler helpers `_record_cycle_failure` / `_evaluate_cycle_outcome` follow the same conventions as `_on_job_error` (module-level, test-importable)"
  - "httpx.MockTransport-driven scheduler integration tests: build a real client, swap its `_client.transport`, drive `make_search_job` end-to-end through `run_radarr_cycle`. Patch `triggarr.clients.base.asyncio.sleep` to avoid the 2s retry backoff."

requirements-completed: [SAFETY-03]

# Metrics
duration: 9min26s
completed: 2026-05-25
---

# Phase 65 Plan 02: SAFETY-03 Consecutive-Failure Counter + Split Persistence Error Branch Summary

**Added a per-job consecutive-failure counter on `app.state.search_failures` driven by the engine's `connected` flag, so REAL *arr outages (not just rare narrow-tuple raises) escalate from WARNING to ERROR at `general.max_consecutive_failures` (default 5, bounded 1..100). Split persistence failures into their own try/except branch with immediate ERROR log + `persistence_degraded` flag + re-raise, ensuring durability problems are never counted as transient *arr blips.**

## Performance

- **Duration:** ~9 min 26 s
- **Started:** 2026-05-26T02:41:19Z
- **Completed:** 2026-05-26T02:50:45Z
- **Tasks:** 3 (RED → GREEN → REFACTOR)
- **Files modified:** 7 (4 source + 1 template + 2 tests)
- **Test delta:** 896 → 903 (+7)

## Accomplishments

- **SAFETY-03 closed:** Per-job consecutive-failure counter on `app.state.search_failures[f"{app}_{instance}_search"]` increments on every failed cycle and resets on success. Escalation from WARNING to ERROR fires at `count >= max_consecutive_failures`.
- **Codex finding 1 closed:** Counter observes REAL *arr outages by reading the engine's `state[app][inst]["connected"]` flag after each cycle. The previous plan draft only fired on rare narrow-tuple raises; production engines catch httpx errors internally and return state with `connected=False`, so the old design would never escalate during a sustained Radarr/Sonarr/Lidarr outage.
- **Codex finding 2 closed:** Persistence is wrapped in its own try/except (`OSError`, `aiosqlite.Error`). `OSError` was REMOVED from the cycle's narrow-tuple catch. Persistence failures log at ERROR immediately (no threshold gate), set `app.state.persistence_degraded = True`, and re-raise so APScheduler's `EVENT_JOB_ERROR` listener (added in 65-01) also logs with `job_id` context. The counter is NOT incremented for persistence failures — durability is not a transient blip.
- **End-to-end config plumbing:** `max_consecutive_failures` flows from settings.html → POST /settings → safe_int(form, 5, 1, 100) → TOML → `GeneralConfig` (pydantic `Field(ge=1, le=100)`) → scheduler read-at-failure-time so config edits take effect on the next failure without restart.
- **Tests-first via real-cycle integration:** Outage tests drive a real `RadarrClient` wired to `httpx.MockTransport` returning 503. The real `run_radarr_cycle` executes, catches `httpx.HTTPStatusError`, sets `connected=False`, and returns state — proving the counter is wired to the production path, not a synthetic shortcut.
- **No regression:** Full project suite (903 tests) and ruff (`triggarr/ tests/`) green.

## Task Commits

Each task was committed atomically as RED → GREEN → REFACTOR:

1. **Task 1 (RED): add failing tests** — `7daa421` (test)
2. **Task 2 (GREEN): config field + cycle-outcome counter + split persistence** — `b94081c` (feat)
3. **Task 3 (REFACTOR): document counter lifecycle + manual-search TODO** — `34f418e` (refactor)

## Files Created/Modified

- `triggarr/models/config.py` (+3 / −1) — `from pydantic import Field` added; `GeneralConfig.max_consecutive_failures: int = Field(default=5, ge=1, le=100)` inserted after `tracking_delay_seconds`.
- `triggarr/config.py` (+1) — commented `# max_consecutive_failures = 5` line in `DEFAULT_CONFIG`.
- `triggarr/web/routes.py` (+2) — context-dict entry on GET render; `safe_int(form.get("max_consecutive_failures"), 5, 1, 100)` on POST /settings.
- `triggarr/templates/settings.html` (+7) — number input with min=1 max=100, helper text explaining warning→error escalation.
- `triggarr/search/scheduler.py` (+183 / −36) — `app.state.search_failures` + `app.state.persistence_degraded` init in `create_lifespan`; `_record_cycle_failure` + `_evaluate_cycle_outcome` module-level helpers; `make_search_job` refactored (narrow-tuple cycle catch with OSError REMOVED; post-cycle outcome eval; dedicated persistence try/except that logs ERROR + sets degraded flag + re-raises).
- `tests/test_config.py` (+17) — `test_general_config_default_max_consecutive_failures` with default + bounds assertions.
- `tests/test_scheduler.py` (+410 / −1) — 6 new tests + `_build_outage_app` helper + new imports (`RadarrClient`, `InstanceConfig`, `Settings`, `_default_instance_state`). `_make_app_with_db` fixture also seeded with the new state attrs.

## Decisions Made

- **Codex finding 1 — counter sources from `state.connected`, not raised exceptions.** The previous plan draft hooked the counter to the narrow-tuple `except` branch. But `run_radarr_cycle`/`run_sonarr_cycle`/`run_lidarr_cycle` already catch `httpx.HTTPError`/`pydantic.ValidationError` internally, set `state[app][inst]["connected"] = False`, and RETURN state instead of raising. The old design would never have escalated during a real outage. The fix reads the engine's `connected` flag after the cycle returns. The rare narrow-tuple raise path (e.g., `aiosqlite.Error` escaping the engine) still feeds the same counter via `_record_cycle_failure` inside the except block.

- **Codex finding 2 — persistence is a separate failure class.** `OSError` was REMOVED from the cycle's narrow-tuple catch. A dedicated `try/except (OSError, aiosqlite.Error)` wraps only the `save_state(...)` call. Durability failures log at ERROR immediately (no threshold gate), set `app.state.persistence_degraded = True`, and re-raise so `_on_job_error` (added in 65-01) also logs with `job_id`. The counter is NOT incremented for persistence failures — they are a different failure class and should not be drowned in the *arr-outage counter.

- **`Field(default=5, ge=1, le=100)` over `@field_validator`.** Both satisfy the out-of-bounds `pytest.raises(ValidationError)` assertion. `Field(ge/le)` is one line; the validator would be a four-line method. Defense-in-depth is preserved because `safe_int(..., 5, 1, 100)` at the route layer also clamps before the value reaches pydantic.

- **Escalation uses `>=`, not `>`.** Per RESEARCH §A6, the threshold semantics are "the Nth failure escalates", so `count == threshold` IS the ERROR line. Test `test_failure_counter_escalates_at_threshold` (`max_consecutive_failures=3`) asserts exactly two `WARNING |` lines plus an `ERROR | ` line containing `(3/3)`.

- **Counter reset before persistence.** `_evaluate_cycle_outcome` runs (and may reset the counter) BEFORE the persistence try/except. So a successful cycle that then fails to persist will still record the cycle success in `search_failures[job_id] = 0`, while `persistence_degraded = True` flips independently. This separation matters because a persistence failure is not evidence that the *arr instance is unhealthy.

- **Manual search-now NOT wired to the counter (yet).** `search_now` in `triggarr/web/routes.py` invokes `cycle_fn(...)` and `save_state(...)` directly instead of going through `make_search_job`. The plan flagged this for deferral; the source now carries a `TODO(SAFETY-03)` documenting the gap so a future plan can either route search-now through `make_search_job` or extract a shared `_run_one_cycle` helper.

- **Outage-driven tests patch `run_tracking_check` and `save_state` (Rule 3 — production path requires real DB/disk).** The real `run_radarr_cycle` runs end-to-end via `httpx.MockTransport`, but its post-cycle phases (tracking lookup + state persistence) need either a real aiosqlite connection or patches. The tests patch both with no-ops so the assertion focuses on the counter logic. Real DB integration is exercised by `test_search_job_runs_tracking_after_cycle` and friends.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `_make_app_with_db` fixture missing `app.state.search_failures` and `app.state.persistence_degraded`**

- **Found during:** Task 2 (running full project suite after GREEN)
- **Issue:** `_make_app_with_db` is used by the pre-existing tracking tests (`test_search_job_runs_tracking_after_cycle`, `test_search_job_tracking_failure_nonfatal`, `test_search_job_logs_tracking_results`). With the new `_evaluate_cycle_outcome` call inside `make_search_job`, those tests crashed with `AttributeError: 'State' object has no attribute 'search_failures'` because the fixture didn't seed the new attrs. Plan 65-01 hit the same pattern and added them to the new tests; this plan needed to also add them to the SHARED fixture.
- **Fix:** Added `app.state.search_failures = {}` and `app.state.persistence_degraded = False` to `_make_app_with_db`.
- **Files modified:** `tests/test_scheduler.py`
- **Verification:** Full suite 903 passing.
- **Committed in:** `b94081c` (Task 2 GREEN commit).

**2. [Rule 3 - Blocking] Outage tests needed `run_tracking_check` and `save_state` patched**

- **Found during:** Task 2 (running new tests for the first time)
- **Issue:** The outage tests use `app.state.db = AsyncMock()` (lightweight), but the production scheduler's flow continues past `_evaluate_cycle_outcome` into persistence and the tracking check. `run_tracking_check` calls `get_pending_history_entries(db, ...)` which uses `db.execute(...)` as an async context manager — the AsyncMock doesn't model that protocol, so the test crashed with `TypeError: 'coroutine' object does not support the asynchronous context manager protocol`. Similarly, `save_state` would try to write to disk. The plan said "Test fixtures must drive the cycle for real" but did not anticipate the post-cycle phases needing isolation.
- **Fix:** In each outage-driven test, patch `triggarr.search.scheduler.run_tracking_check` with `AsyncMock(return_value={...})` and `triggarr.search.scheduler.save_state` with `MagicMock()`. This keeps the real `run_radarr_cycle` running end-to-end (the test's stated invariant) while skipping the post-cycle phases that aren't under test.
- **Files modified:** `tests/test_scheduler.py`
- **Verification:** All 6 new scheduler tests pass; outage tests still drive `run_radarr_cycle` for real via MockTransport (verified by the `connected is False` assertion on cycle 1).
- **Committed in:** `b94081c` (Task 2 GREEN commit).

**3. [Rule 3 - Blocking] Success-cycle MockTransport handler missing `sortKey` field**

- **Found during:** Task 2 (running `test_failure_counter_resets_on_success`)
- **Issue:** The cycle-3 success path returned `{"page": 1, "pageSize": 50, "totalRecords": 0, "records": []}` — but `PaginatedResponse` (triggarr/models/arr.py:10-23) requires `sortKey` as a non-optional field. The pydantic validation error was caught inside `run_radarr_cycle` (which catches `pydantic.ValidationError`), so the cycle still reported as a failure (`connected=False`) on what was meant to be a success cycle. Counter trajectory was 1, 2, 3, 4 instead of 1, 2, 0, 1.
- **Fix:** Added `"sortKey": "id"` to the success-cycle payload (and the same fix to the per-instance test and persistence test handlers). Also added a special-case for `/api/v3/tag` returning a flat `[]` since `get_tags` calls `get_json_list`, not `get_paginated`.
- **Files modified:** `tests/test_scheduler.py`
- **Verification:** `test_failure_counter_resets_on_success` passes with the expected `[False, False, True, False]` connected trajectory and counter = 1 after F/F/S/F.
- **Committed in:** `b94081c` (Task 2 GREEN commit).

### Deferred Items

**1. Manual search-now does NOT feed the counter**

- **Found during:** Task 3 (sanity pass — read `search_now` in routes.py:802-870)
- **Issue:** `search_now` invokes `cycle_fn(...)` directly inside its own `async with search_lock` block, bypassing `make_search_job`. So a successful manual search does NOT reset the per-job counter; a failing manual search does NOT increment it. The counter is currently scheduler-only.
- **Status:** **DEFERRED** to a follow-up plan per Task 3 spec ("if the search-now handler bypasses make_search_job ... surface a `# TODO(SAFETY-03):` comment AND note the deferral in the SUMMARY").
- **Documented in source:** `triggarr/search/scheduler.py::_evaluate_cycle_outcome` carries a `TODO(SAFETY-03)` docstring block plus an adjacent inline comment beside the counter-reset line. The follow-up plan should either route `search_now` through `make_search_job` or extract a shared `_run_one_cycle(app, app_name, instance_name)` helper that both call sites invoke.

---

**Total deviations:** 3 auto-fixed (all Rule 3 — production path exposed missing test scaffolding), 1 deferred (manual search-now coverage).
**Impact on plan:** All auto-fixes preserve the plan's stated invariants (outage tests drive the real engine cycle; counter logic remains in `_record_cycle_failure` + `_evaluate_cycle_outcome`). No architectural change.

## Issues Encountered

None beyond the deviations listed above.

## User Setup Required

None — internal scheduler observability hardening. The new field appears in the settings UI but defaults to 5 and is bounded 1..100; existing configs continue to work unchanged.

## Next Phase Readiness

- **65-03 (RES-01 60s drain + lock holder):** Ready. The `job_id = f"{app_name}_{instance_name}_search"` assignment inside `make_search_job` is now the canonical place to expose the holder identity (65-03 spec already references this). `app.state.search_lock_holder` is referenced by the 65-01 test fixtures but not yet read by production — 65-03 will wire it.
- **65-04 (TEST-04 aclose):** Independent of this plan; no new dependencies introduced.
- **Manual search-now SAFETY-03 follow-up:** Best landed in v2.8 Phase 67 (Observability & CSRF) since it overlaps with RES-02 (last-successful-search dashboard).

## TDD Gate Compliance

Verified gate sequence in git log:
1. RED: `7daa421` `test(65-02): add failing tests…` — failing tests committed before implementation.
2. GREEN: `b94081c` `feat(65-02): add max_consecutive_failures config…` — implementation makes tests pass.
3. REFACTOR: `34f418e` `refactor(65-02): document SAFETY-03 counter lifecycle…` — comment-only cleanup, no behavioral change.

All three gates present, in order.

## Self-Check: PASSED

- Verified files exist:
  - `triggarr/models/config.py` — FOUND (max_consecutive_failures present)
  - `triggarr/config.py` — FOUND (commented template line present)
  - `triggarr/web/routes.py` — FOUND (form handler + context entry present)
  - `triggarr/templates/settings.html` — FOUND (number input present)
  - `triggarr/search/scheduler.py` — FOUND (init + helpers + split branches present)
  - `tests/test_config.py` — FOUND
  - `tests/test_scheduler.py` — FOUND
- Verified commits exist:
  - `7daa421` (Task 1 RED) — FOUND
  - `b94081c` (Task 2 GREEN) — FOUND
  - `34f418e` (Task 3 REFACTOR) — FOUND
- Verified tests pass: `uv run pytest tests/ -x -q` → 903 passed.
- Verified ruff clean: `uv run ruff check triggarr/ tests/` → All checks passed.

---
*Phase: 65-scheduler-hardening-resilience*
*Completed: 2026-05-25*
