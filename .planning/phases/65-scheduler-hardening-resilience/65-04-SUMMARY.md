---
phase: 65-scheduler-hardening-resilience
plan: 04
subsystem: testing
tags: [testing, httpx, async, client-lifecycle, asgi-transport, codex-finding-4]

# Dependency graph
requires: []
provides:
  - "TEST-04: three pinned tests for ArrClient.close() / httpx.AsyncClient.aclose() in-flight contract"
  - "_HTTPX_INFLIGHT_NO_CANCEL_EXC module constant (AssertionError @ httpx 0.28.1) for future-proofing the in-flight contract"
  - "_build_slow_asgi_app: bare-ASGI test helper (~20 LOC, no Starlette/FastAPI dependency)"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "httpx.ASGITransport for in-process contract tests against the production async close machinery (no port/process management vs uvicorn)"
    - "Module-level pinned-exception constant with empirical-observation comment so future library upgrades that change the contract fail deliberately"

key-files:
  created: []
  modified:
    - tests/test_clients.py

key-decisions:
  - "Use httpx.ASGITransport (real production transport) for the two contract tests instead of only httpx.MockTransport (in-memory bypass) — Codex finding 4 closed"
  - "Pin the in-flight no-cancel exception class to a single AssertionError via isinstance — eliminates the prior 4-class hedging acceptance (Codex finding 4 closed)"
  - "Empirically observed the exception class via 5-run live probe before writing the assertion (5/5 deterministic AssertionError on httpx 0.28.1)"
  - "Keep MockTransport regression test as cheap unit-level coverage, honestly renamed to reflect what it proves (mock path does not hang after cancel)"
  - "Use 0.5s sleep in the no-cancel test's ASGI handler so the handler completes naturally and the ASGITransport assertion fires within the 3s test budget (vs 10s for the cancel-then-close path where cancellation aborts the sleep)"
  - "Bare-ASGI callable (~20 LOC) instead of adding starlette as a test dep — zero new dependencies"
  - "Use `_request_with_retry` (the method invoked by production code paths) rather than a non-existent `client.get()` for consistency with the rest of the file"

patterns-established:
  - "Test placement: TEST-04 block placed immediately after the existing `_request_with_retry` tests (lines 124-138) for grouping"
  - "ASGI helper as test-local factory function (not production code) — documented in the docstring"

requirements-completed: [TEST-04]

# Metrics
duration: 7min
completed: 2026-05-26
---

# Phase 65 Plan 04: TEST-04 in-flight aclose() contract Summary

**Pin httpx.AsyncClient.aclose() in-flight contract with real ASGITransport — single-class isinstance check replaces 4-class hedging (Codex finding 4 closed).**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-26T02:29:16Z
- **Completed:** 2026-05-26T02:36:16Z
- **Tasks:** 1
- **Files modified:** 1
- **Commits:** 1 (`abfd666`)

## Accomplishments

- Added three new tests to `tests/test_clients.py` covering the `ArrClient.close()` / `httpx.AsyncClient.aclose()` in-flight contract:
  1. **`test_aclose_with_mocktransport_returns_quickly_after_cancel`** (renamed unit-level regression check, MockTransport path)
  2. **`test_aclose_with_real_asgi_transport_in_flight_returns_within_2s`** (new real-transport contract test, cancel-then-close happy path)
  3. **`test_aclose_with_real_asgi_transport_no_cancel_raises_specific_exception`** (new real-transport contract test, no-cancel path with pinned exception class)
- Ran a 5-run live probe against `httpx==0.28.1` to determine the deterministic exception class raised on the in-flight task when `aclose()` is called without prior cancellation: **`AssertionError`** (5/5 runs), thrown from `httpx._transports.asgi:181` (`assert response_complete.is_set()` after the ASGI handler returns without sending a complete response).
- Added a module-level `_HTTPX_INFLIGHT_NO_CANCEL_EXC: type[BaseException] = AssertionError` constant with an empirical-observation comment (httpx version + observation date) so a future httpx upgrade that intentionally changes the contract surfaces test 3 as a deliberate failure rather than as a silent shutdown behavior change in production.
- Added a `_build_slow_asgi_app(request_started, sleep_seconds)` bare-ASGI factory (no Starlette/FastAPI dependency) routing `/slow`, `/fast`, and 404.
- Added two top-of-file imports (`asyncio`, `contextlib`) in alphabetical order per ruff `I`.

## Task Commits

Single task, committed atomically:

1. **Task 1 (RED): Add three TEST-04 in-flight aclose tests** — `abfd666` (test)

## Test Results

- **3 new tests pass** (`uv run pytest tests/test_clients.py -k "aclose" -x`)
- **Full file passes**: 54 / 54 (`uv run pytest tests/test_clients.py -x -q`)
- **Full suite passes**: **894 / 894** (was 891 before; +3 new tests)
- **Per-new-test wall-clock duration:**
  - `test_aclose_with_mocktransport_returns_quickly_after_cancel`: ~0.02 s
  - `test_aclose_with_real_asgi_transport_in_flight_returns_within_2s`: < 0.005 s
  - `test_aclose_with_real_asgi_transport_no_cancel_raises_specific_exception`: ~0.51 s (bounded by the 0.5 s `/slow` handler sleep)
- Each test completes well under the 3 s acceptance budget; no test approaches the 2 s `asyncio.wait_for(client.close(), timeout=2.0)` guard.

## Ruff

`uv run ruff check tests/test_clients.py` → **All checks passed**.

## Files Modified

- `tests/test_clients.py` (+227 lines)
  - Added `import asyncio` and `import contextlib` at the top of the file (alphabetical)
  - Added the TEST-04 block immediately after the existing `_request_with_retry` tests
  - Added module-level constant `_HTTPX_INFLIGHT_NO_CANCEL_EXC` and helper `_build_slow_asgi_app`
  - Added three new async tests covering MockTransport (cheap regression) and ASGITransport (production contract) paths

## Decisions Made (with Codex finding traceability)

### Codex finding 4 — closed

- **Decision:** Keep the cheap MockTransport unit test for fast regression feedback, but rename it (`test_aclose_with_mocktransport_returns_quickly_after_cancel`) to honestly reflect what it proves (the mock path does not hang after cancel — NOT that production close is safe).
- **Decision:** Add at least one test using `httpx.ASGITransport` (real transport that exercises the production `AsyncHTTPTransport`-equivalent async connection-pool + close machinery). We added two ASGITransport tests: one for the cancel-then-close happy path, one for the no-cancel close path.
- **Decision:** Replace the prior four-class "accept any of {RuntimeError, cancellation, HTTPError, clean completion}" hedging acceptance with a single-class `isinstance(result[0], _HTTPX_INFLIGHT_NO_CANCEL_EXC)` check. The pinned class was determined empirically via a 5-run live probe (`AssertionError`, deterministic 5/5 on httpx 0.28.1, observed inside `httpx._transports.asgi:181` after the ASGI handler completes without sending a full response).
- **Empirical observation recorded for future auditability:**
  - **httpx version:** 0.28.1 (from `pyproject.toml` pin `>=0.27` resolved 2026-05-26)
  - **Observed exception class:** `AssertionError` (raised from `httpx._transports.asgi.ASGITransport.handle_async_request` line 181: `assert response_complete.is_set()`)
  - **Determinism:** 5/5 probe runs
  - **Update protocol:** if a future httpx release intentionally changes this behavior (e.g. surfaces `httpx.RemoteProtocolError` instead), test 3 will fail with a descriptive assertion message including the actual observed class; the operator updates `_HTTPX_INFLIGHT_NO_CANCEL_EXC` after auditing the upstream change.

### Other plan decisions

- **`_request_with_retry` over `client.get()`:** every existing async test in `tests/test_clients.py` uses `client._request_with_retry("GET", "/slow")`. We kept that convention to avoid introducing a divergent fixture shape. Note: `_request_with_retry` only catches `(httpx.HTTPStatusError, httpx.TransportError)`, so the `AssertionError` from `ASGITransport` propagates directly through it without triggering the retry path — fine for the contract pin.
- **`ASGITransport` over standing up a uvicorn / aiohttp test server:** zero extra dependencies (httpx already required), no port allocation, no process management, no flaky cleanup, and `ASGITransport` exercises the same async connection-pool + close machinery as a real socket-backed transport.
- **0.5 s sleep in the no-cancel test's `/slow` handler:** the `ASGITransport` assertion only trips after `await self.app(scope, receive, send)` returns. With a 10 s sleep the gather waits 10 s for the handler to complete naturally. 0.5 s is long enough to guarantee the request is in flight when `close()` is called (the handler sets `request_started` before the sleep), and short enough that the whole test completes in ~0.5 s — well inside the 3 s test-budget acceptance criterion. The cancel-then-close test keeps the default 10 s sleep because `pending.cancel()` aborts the sleep.
- **`asyncio.wait_for(client.close(), timeout=2.0)` is the key assertion in all three tests:** a hang in `close()` would surface as `TimeoutError` and fail the test fast. The 2 s timeout is ~1000× the expected close latency under in-process testing — large enough to absorb CI scheduler jitter, small enough that a regression fails quickly.
- **Test 3 wraps the gather in `asyncio.wait_for(..., timeout=2.0)`:** caps the test's total in-flight-wait budget independent of any change to the `/slow` handler sleep.
- **`finally` cleanup in every test:** if `pending.done()` is false after the assertions, cancel and consume — guarantees no leaked tasks across tests (relevant under `asyncio_mode=auto`).

## Deviations from Plan

None — plan executed exactly as written. The live probe selected `AssertionError` (a candidate not explicitly listed in the plan's `<behavior>` "Expected candidates" but allowed by "specific httpx exception class" wording), recorded with full context.

## Self-Check: PASSED

- File exists: `tests/test_clients.py` (modified) → FOUND
- Commit exists: `abfd666` → FOUND
- All three new test names grep == 1 → ✓
- `ASGITransport` count = 8 (≥2) → ✓
- `isinstance(result[0], _HTTPX_INFLIGHT_NO_CANCEL_EXC)` count = 1 → ✓
- Old hedging signature (`RuntimeError, asyncio.CancelledError, httpx.HTTPError`) count = 0 → ✓
- `asyncio.wait_for(client.close(), timeout=2.0)` count = 5 (≥2) → ✓
- `import contextlib` and `import asyncio` each count = 1 → ✓
- `uv run pytest tests/test_clients.py -k "aclose" -x` → 3 passed
- `uv run pytest tests/test_clients.py -x -q` → 54 passed
- `uv run pytest tests/ -x -q` → 894 passed
- `uv run ruff check tests/test_clients.py` → All checks passed
