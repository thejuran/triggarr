---
phase: 65-scheduler-hardening-resilience
verified: 2026-05-25
verifier: orchestrator-inline
status: passed
must_haves_verified: 4/4
requirements_traced: SAFETY-02, SAFETY-03, RES-01, TEST-04
test_count: 906
ruff: clean
code_review: 6/10 critical+warning findings fixed; 4 skipped as design decisions
---

# Phase 65 Verification: Scheduler Hardening & Resilience

**Verified:** 2026-05-25 (inline by orchestrator after two verifier-agent network disconnects)
**Status:** ✓ Passed
**Plans complete:** 4/4 (65-01, 65-02, 65-03, 65-04)

## Verification approach

Two attempts to spawn the gsd-verifier subagent failed with `API Error: socket connection closed unexpectedly` after ~16 and ~21 minutes of work. Each phase requirement is concrete and grep-verifiable, so verification was completed inline against the live codebase on main (HEAD: `323ee65`).

## Success criteria

### 1. SAFETY-02 — Narrow scheduler exception handling ✓

> "A search cycle that throws an unexpected exception type (e.g., RuntimeError, MemoryError) is no longer silently caught; only httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, and OSError are handled — others propagate to the APScheduler error handler."

Verified by inspecting `triggarr/search/scheduler.py`:
- `from apscheduler.events import EVENT_JOB_ERROR` imported at line 35.
- `_on_job_error` listener registered before `scheduler.start()` (line 492 context).
- Narrow tuple `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` is the only `except` at the outer try in `make_search_job`.
- New tests in `tests/test_scheduler.py`: `test_make_search_job_unexpected_exception_propagates`, `test_make_search_job_httperror_swallowed`, `test_event_job_error_listener_logs_unexpected_exception` (all pass).
- Post-review fix CR-01 added `_sanitize_exc(...)` to tracking-exception logging path.

### 2. SAFETY-03 — Per-job consecutive-failure counter with escalation ✓

> "After N consecutive failures on a single job (default N=5, configurable), the log level escalates from WARNING to ERROR."

Verified by inspecting `triggarr/models/config.py:85` and `triggarr/search/scheduler.py`:
- `max_consecutive_failures: int = Field(default=5, ge=1, le=100)` on `GeneralConfig` (line 85).
- `app.state.search_failures = {}` initialised at startup (line 445).
- Counter increment + threshold check + WARNING→ERROR escalation in `_evaluate_cycle_outcome` (lines 255–262, threshold at 262).
- Counter reset on success (line 312).
- Settings UI input added in `triggarr/templates/settings.html`; form-handler bounded `safe_int(..., 5, 1, 100)` in `triggarr/web/routes.py`.
- Codex finding 2 (split persistence-error branch) closed: persistence failures do NOT increment the counter.

### 3. RES-01 — Configurable shutdown drain with holder identity ✓

> "Graceful shutdown waits up to 60 seconds (extended from 35s) for the search lock to drain; if a cycle is still holding the lock when the timeout fires, the specific job identifier and elapsed runtime are logged before forced close."

Verified by inspecting `triggarr/search/scheduler.py`:
- `_SHUTDOWN_DRAIN_TIMEOUT: float = _read_shutdown_drain_timeout()` (line 81).
- `_read_shutdown_drain_timeout` reads `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` env var, defaults to `60.0`, clamps `>= 1.0` (lines 59–80).
- `app.state.search_lock_holder = (job_id, time.monotonic())` set inside the lock (line 131); cleared in `finally` (line 242).
- Shutdown drain logs INFO on entry and WARNING with holder identity + elapsed runtime on timeout.
- `docker-compose.yml`: `stop_grace_period: 90s` added.
- `README.md` documents `--stop-timeout` and systemd `TimeoutStopSec`.
- Post-review fix WR-01 switched `asyncio.wait_for(lock.acquire(), ...)` to `asyncio.timeout()` to close the cancellation footgun.

### 4. TEST-04 — In-flight aclose() contract test ✓

> "The async client cleanup test confirms that calling aclose() on a client with in-flight requests does not hang and that any in-flight responses raise cleanly rather than leaving the event loop blocked."

Verified by inspecting `tests/test_clients.py`:
- 3 new tests added:
  - `test_aclose_with_mocktransport_returns_quickly_after_cancel` (cheap unit regression).
  - `test_aclose_with_real_asgi_transport_in_flight_returns_within_2s` (production contract: returns within 2s, no exceptions from close).
  - `test_aclose_with_real_asgi_transport_no_cancel_raises_specific_exception` (pins httpx's exact in-flight exception class via `_HTTPX_INFLIGHT_NO_CANCEL_EXC` module constant — 5/5 deterministic on httpx 0.28.1).
- Uses `httpx.ASGITransport` (real production code path), not just MockTransport (Codex finding 4 closed).

## Requirements traceability

| Req ID     | Status   | Anchor                                                                 |
|------------|----------|------------------------------------------------------------------------|
| SAFETY-02  | ✓ Done   | `triggarr/search/scheduler.py` narrow tuple + `EVENT_JOB_ERROR`        |
| SAFETY-03  | ✓ Done   | `GeneralConfig.max_consecutive_failures` + `app.state.search_failures` |
| RES-01     | ✓ Done   | `_SHUTDOWN_DRAIN_TIMEOUT` + `search_lock_holder` tracking              |
| TEST-04    | ✓ Done   | `tests/test_clients.py` ASGITransport tests                            |

REQUIREMENTS.md still marks these as `[ ]` (pending). The `phase.complete` step will update the traceability table.

## Test & lint state

- `uv run pytest tests/ -x -q` → **906 passed**, 27 warnings (pre-existing starlette deprecation, not from this phase).
- `uv run ruff check triggarr/ tests/` → **All checks passed!**
- TDD discipline: plans 65-01, 65-02, 65-03 each have separate `test(65-XX): ...` (RED) and `feat(65-XX): ...` (GREEN) commits. Plan 65-04 is the documented pure-test exemption (TEST-04: "the test IS the deliverable").

## Code review outcome

`65-REVIEW.md` flagged 1 Critical + 9 Warnings + 5 Info. The `--fix` pass resolved 6 (CR-01, WR-01, WR-04, WR-05, WR-08, WR-09). Four warnings were skipped with rationale in `65-REVIEW-FIX.md`:

- **WR-02** (connected=None treated as success) — preserves documented semantics; explicit failure modes set `connected=False`.
- **WR-03** (no force-cancel of in-flight cycles on timeout) — design choice: rely on host SIGKILL after the configured grace period.
- **WR-06** (`>=` vs `>` threshold) — verified by existing tests, matches intended escalation semantics.
- **WR-07** (entry-time holder log) — deliberate observability for the SIGKILL window.

None of the skipped items invalidate any of the four success criteria.

## Human verification

None required. All four success criteria are exercised by automated tests in the 906-test suite. The new shutdown path and consecutive-failure escalation could be eyeballed in a live container if desired, but the behavior contracts are pinned by tests, so this is optional.
