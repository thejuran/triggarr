---
phase: 65-scheduler-hardening-resilience
plan: 01
subsystem: scheduler
tags: [scheduler, exception-handling, apscheduler, observability, safety-02]

# Dependency graph
requires:
  - phase: 64-data-safety-config-integrity
    provides: max_history_rows end-to-end pattern (model + DEFAULT_CONFIG + routes + tests) mirrored later by 65-02 for max_consecutive_failures
provides:
  - Narrowed make_search_job outer except from broad Exception to the canonical four-type tuple (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)
  - Module-level _on_job_error(event) listener with httpx/pydantic sanitization split
  - scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR) registration before scheduler.start() in create_lifespan
  - Inverted test_make_search_job_unexpected_exception_propagates + sibling test_make_search_job_httperror_swallowed + new test_event_job_error_listener_logs_unexpected_exception
affects: [65-02-PLAN.md, 65-03-PLAN.md, 65-04-PLAN.md]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "APScheduler event listener registration (first add_listener call in repo)"
    - "Module-level _on_job_error function (not closure) for test importability"
    - "Sanitization split: _sanitize_exc for httpx/pydantic; str() for other types"

key-files:
  created: []
  modified:
    - triggarr/search/scheduler.py
    - tests/test_scheduler.py
    - tests/test_config_dir.py

key-decisions:
  - "Module-level _on_job_error (not a closure inside create_lifespan) so tests can import it via `from triggarr.search.scheduler import _on_job_error`"
  - "Preserved existing logger.error body inside narrowed except — 65-02 will replace that body with the failure-counter + escalation logic"
  - "Deliberately did NOT add `import time` here per Codex finding 5 — `time` lives in 65-03 where it is used for monotonic elapsed measurement; adding here would trigger F401 unused-import and break ruff gate"
  - "Used PEP 604 union (`httpx.HTTPError | pydantic.ValidationError`) inside isinstance — satisfies ruff UP038 preference"
  - "Updated test_search_job_tracking_failure_nonfatal from RuntimeError to httpx.ConnectError side_effect — RuntimeError relied on the buggy broad except; httpx.ConnectError is the realistic tracking-outage path and is in the inner tracking narrow tuple"

patterns-established:
  - "APScheduler EVENT_JOB_ERROR listener pattern: define module-level fn, add_listener before scheduler.start()"
  - "Cross-module `_`-prefixed import inside scheduler.py: `from triggarr.search.engine import _sanitize_exc` (precedent: `from triggarr.web.routes import _sync_auth_state`)"

requirements-completed: [SAFETY-02]

# Metrics
duration: 7min
completed: 2026-05-25
---

# Phase 65 Plan 01: Scheduler Narrow Exception + EVENT_JOB_ERROR Listener Summary

**Narrowed `make_search_job` outer except to the canonical four-type tuple and wired an APScheduler `EVENT_JOB_ERROR` listener so code-bug exceptions (RuntimeError, KeyError, etc.) become operator-visible at ERROR level instead of disappearing into APScheduler's stdlib-logging silence.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-26T02:28:49Z
- **Completed:** 2026-05-26T02:35:41Z
- **Tasks:** 3 (RED → GREEN → REFACTOR)
- **Files modified:** 3

## Accomplishments

- **SAFETY-02 closed:** `except Exception` in `make_search_job` replaced with the canonical `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` tuple used 22× in `engine.py`. Code-bug exceptions now propagate to APScheduler.
- **EVENT_JOB_ERROR listener wired:** Module-level `_on_job_error` logs propagated exceptions at ERROR level with job_id + type name + sanitized exception message. Routes httpx/pydantic exceptions through `_sanitize_exc` to strip `apikey=` query params; uses `str(exc)` for other types (Triggarr's non-httpx exceptions do not carry secrets).
- **Test coverage:** 3 new/inverted tests confirm both branches (narrow-tuple swallow + non-narrow propagation + listener logging).
- **Codex finding 5 honoured:** `import time` deliberately deferred to 65-03 where it is actually used; ruff F401 clean here.
- **No regression:** Full project suite (893 tests) and ruff (`triggarr/ tests/`) green.

## Task Commits

Each task was committed atomically as RED → GREEN → REFACTOR:

1. **Task 1 (RED): add failing tests** — `da30103` (test)
2. **Task 2 (GREEN): narrow except + register listener** — `436ec81` (feat)
3. **Task 3 (REFACTOR): inline SAFETY-02 comment** — `01c6262` (refactor)

## Files Created/Modified

- `triggarr/search/scheduler.py` (+41 lines) — Narrow exception tuple, module-level `_on_job_error`, listener registration, inline SAFETY-02 comment.
- `tests/test_scheduler.py` (+102 / −3 lines) — Inverted swallow→propagation test, two new sibling tests, fixture additions (`search_failures`, `search_lock_holder`, `db` MagicMock), updated `test_search_job_tracking_failure_nonfatal` to use `httpx.ConnectError`.
- `tests/test_config_dir.py` (+6 lines) — Added `add_listener` stub to `_FakeScheduler` test double (Rule 3 — production change required matching mock surface).

## Decisions Made

- **Module-level `_on_job_error` over closure:** Tests must import it directly to dispatch synthetic `JobExecutionEvent` instances. Closure inside `create_lifespan` would force tests to spin up the full lifespan to access it.
- **Sanitization split:** Researched (RESEARCH §B, Open Question 3) — httpx exceptions can leak `apikey=` from `request.url`, so route through `_sanitize_exc`. Other exception types (RuntimeError, KeyError) do not carry secrets in Triggarr's codebase; `str(exc)` is safe.
- **`isinstance(exc, httpx.HTTPError | pydantic.ValidationError)`:** PEP 604 union — satisfies ruff UP038 (prefer `X | Y` over `(X, Y)` for isinstance). Python 3.10+; project is 3.11+.
- **Did not add `import time`:** Codex finding 5 (REVIEWS.md) explicitly flagged the prior draft for trying to pre-add this import. `time` lives in 65-03 where it is used for `time.monotonic()`. Adding it here would trigger ruff F401 and break the plan's own ruff gate.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `app.state.db` MagicMock added to new test fixtures**
- **Found during:** Task 2 (running GREEN tests)
- **Issue:** `make_search_job`'s call to `cycle_fn(client, state, instance, config, settings, app.state.db)` evaluates `app.state.db` BEFORE the mocked `side_effect=RuntimeError` fires (Python evaluates all argument expressions, then invokes the call). Without `app.state.db` set, `getattr` raises `AttributeError`. The prior broad `except Exception` masked this — with the narrow tuple, `AttributeError` propagates and the test fails with the wrong exception. The plan's Task 1 fixture spec didn't anticipate this.
- **Fix:** Added `app.state.db = MagicMock()` to both `test_make_search_job_unexpected_exception_propagates` and `test_make_search_job_httperror_swallowed` fixtures.
- **Files modified:** `tests/test_scheduler.py`
- **Verification:** Tests now fail correctly with `RuntimeError` (RED) and pass correctly after GREEN.
- **Committed in:** `436ec81` (Task 2 GREEN commit)

**2. [Rule 3 - Blocking] Pre-existing `test_search_job_tracking_failure_nonfatal` updated**
- **Found during:** Task 2 (running full scheduler suite)
- **Issue:** The pre-existing test patched `run_tracking_check` with `side_effect=RuntimeError("tracking exploded")` and asserted "should NOT raise". This passed only because the broad `except Exception` swallowed RuntimeError. Under SAFETY-02's narrow tuple, RuntimeError correctly propagates — making this test a regression. The plan claimed "all existing scheduler tests except the inverted test continue to pass" but didn't catch this case.
- **Fix:** Changed `side_effect` to `httpx.ConnectError("tracking unreachable")` — which IS in the inner tracking narrow tuple (line 119, `as tracking_exc:`) and is the realistic tracking-outage failure path. The test's original intent (verify `save_state` runs before tracking, and tracking failures don't crash the job) is preserved with the realistic exception type.
- **Files modified:** `tests/test_scheduler.py`
- **Verification:** Test now passes; intent (save-state-then-tracking ordering) intact.
- **Committed in:** `436ec81` (Task 2 GREEN commit)

**3. [Rule 3 - Blocking] `_FakeScheduler` in `tests/test_config_dir.py` missing `add_listener`**
- **Found during:** Task 2 (running full project suite)
- **Issue:** `test_lifespan_derives_sqlite_path_from_injected_state_path` injects a `_FakeScheduler` test double that mocks `AsyncIOScheduler` for lifespan wiring tests. With the new `scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)` call inside `create_lifespan`, the fake raised `AttributeError`.
- **Fix:** Added `add_listener(self, *args, **kwargs)` stub method to `_FakeScheduler` that appends to a `listeners` list (mirrors the existing `add_job` stub pattern). Added inline comment referencing SAFETY-02 + Phase 65-01.
- **Files modified:** `tests/test_config_dir.py`
- **Verification:** Test passes; `_FakeScheduler` surface now matches the AsyncIOScheduler methods called in `create_lifespan`.
- **Committed in:** `436ec81` (Task 2 GREEN commit)

**4. [Rule 1 - Lint] Ruff SIM108 — collapse if/else to ternary**
- **Found during:** Task 2 (ruff gate after GREEN)
- **Issue:** Initial `_on_job_error` body used an `if/else` block to choose between `_sanitize_exc(exc)` and `str(exc)`. Ruff SIM108 prefers a ternary expression here.
- **Fix:** Rewrote as `exc_repr = (_sanitize_exc(exc) if isinstance(exc, ...) else str(exc))`.
- **Files modified:** `triggarr/search/scheduler.py`
- **Verification:** `uv run ruff check` exits 0.
- **Committed in:** `436ec81` (Task 2 GREEN commit)

### Plan-text Imprecision (no code change needed)

**Acceptance criterion #1 in Task 2:** The plan expected `grep -c "except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:"` to return ≥2 ("one outer make_search_job branch added; one pre-existing inner tracking branch"). It returns 1 — because the pre-existing inner tracking branch (line 120) uses `as tracking_exc:`, not `as exc:`. Both narrow tuples exist; the plan literal didn't match the existing variable name. The spirit of the acceptance (both narrow tuples present) is satisfied. Documented for future plans.

---

**Total deviations:** 4 auto-fixed (3 blocking, 1 lint)
**Impact on plan:** All auto-fixes necessary to keep the existing suite green and satisfy ruff. No scope creep — every change is directly attributable to SAFETY-02 (narrow-tuple change exposing prior masked behaviour, or production change requiring matching mock surface).

## Issues Encountered

None beyond the deviations listed above.

## User Setup Required

None — purely internal scheduler hardening.

## Next Phase Readiness

- **65-02 (SAFETY-03 consecutive-failure counter):** Can proceed. The narrowed except is the hook point for the counter; the test fixtures now pre-initialize `app.state.search_failures` and `app.state.search_lock_holder` so the counter logic can drop in without re-touching every test.
- **65-03 (RES-01 60s drain + lock holder):** Can proceed. `import time` deferred here as planned; 65-03 owns it.
- **65-04 (TEST-04 aclose):** Independent of this plan; no blockers.

**Open follow-up (out of scope for this plan but worth flagging for the verifier):**
- Codex review (REVIEWS.md) flagged HIGH findings against 65-02 (counter misses real *arr outage paths) and 65-03 (Docker stop_grace_period). Those are the next-plan owners' responsibility.

## TDD Gate Compliance

Verified gate sequence in git log:
1. RED: `da30103` `test(65-01): add failing tests…` — failing tests committed before implementation.
2. GREEN: `436ec81` `feat(65-01): narrow scheduler exception handler…` — implementation makes tests pass.
3. REFACTOR: `01c6262` `refactor(65-01): document SAFETY-02 narrow exception tuple inline` — cleanup with no behavioural change.

All three gates present, in order.

## Self-Check: PASSED

- Verified files exist:
  - `triggarr/search/scheduler.py` — FOUND
  - `tests/test_scheduler.py` — FOUND
  - `tests/test_config_dir.py` — FOUND
- Verified commits exist:
  - `da30103` (Task 1 RED) — FOUND
  - `436ec81` (Task 2 GREEN) — FOUND
  - `01c6262` (Task 3 REFACTOR) — FOUND

---
*Phase: 65-scheduler-hardening-resilience*
*Completed: 2026-05-25*
