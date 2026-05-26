# Phase 65: Scheduler Hardening & Resilience - Research

**Researched:** 2026-05-25
**Domain:** Python async / APScheduler / httpx lifecycle / asyncio.Lock shutdown drain
**Confidence:** HIGH

## Summary

This phase narrows the over-broad exception handler in `make_search_job` (scheduler.py:124), adds a per-job consecutive-failure counter that escalates the log level from WARNING to ERROR after N failures (default 5, configurable via `general.max_consecutive_failures`), extends the lifespan shutdown lock-drain from 35s to 60s with structured logging of the holder identity, and adds a test that proves `httpx.AsyncClient.aclose()` does not hang when called against in-flight requests.

The codebase already provides the scaffolding:
- `app.state.search_lock` exists and is universally honored (verified in Phase 64).
- The job factory `make_search_job` produces a closure with a stable `job_id = f"{app_name}_{inst_name}_search"` (scheduler.py:240) — that string is the natural key for both the failure counter and the shutdown "who holds the lock" log.
- `app.state.last_search_time: dict[str, float]` is the established pattern for per-job in-memory state on `app.state` — the new failure counter should mirror it.
- The pre-existing exception narrowing pattern `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` is used 22 times in `triggarr/search/engine.py` and is the canonical set to adopt for the search-cycle handler.
- APScheduler 3.11.x exposes `EVENT_JOB_ERROR` and `JobExecutionEvent(code, job_id, jobstore, scheduled_run_time, retval, exception, traceback)` — verified by `import inspect; inspect.signature(JobExecutionEvent)` against the installed package.

**Primary recommendation:** Narrow the `except Exception:` at scheduler.py:124 to `except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:`, route the catch through a `_record_failure(app, job_id, exc)` helper that bumps `app.state.search_failures[job_id]`, escalates to `logger.error` when count >= N (read from `settings.general.max_consecutive_failures`, default 5), and resets the counter on the next success. Wire an APScheduler `EVENT_JOB_ERROR` listener that just calls `logger.error(...)` for the un-narrowed exception types that now propagate. Extend the lifespan drain timeout to 60s and record `app.state.search_lock_holder = (job_id, monotonic_start)` inside the `async with app.state.search_lock:` block so the timeout branch can log who held it and for how long. Add a `tests/test_clients.py` test that fires 3 slow requests via `httpx.MockTransport + asyncio.sleep`, cancels them, then awaits `client.close()` under `asyncio.wait_for(..., timeout=2.0)` to prove non-hang behavior.

## User Constraints (from CONTEXT.md)

No CONTEXT.md exists for Phase 65 — this is the pre-planning research pass. Constraints are inherited from `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, and project conventions in `./CLAUDE.md`.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SAFETY-02 | Scheduler exception handler catches only `httpx.HTTPError`, `pydantic.ValidationError`, `aiosqlite.Error`, `OSError` — not bare `Exception` | Patch `triggarr/search/scheduler.py:124-129`; the narrowed tuple already appears 22× in `engine.py` and is the project's established discriminator |
| SAFETY-03 | Consecutive-failure counter per job; escalate WARNING→ERROR after N (default 5, configurable) | New in-memory `dict[str, int]` on `app.state.search_failures`, mirrors `app.state.last_search_time` pattern; new `general.max_consecutive_failures: int = 5` field |
| RES-01 | Graceful shutdown waits up to 60s (was 35s) for `search_lock` to drain; logs holder identity + elapsed runtime on timeout | Bump `scheduler.py:280` timeout, add `app.state.search_lock_holder` tracking in `make_search_job` (set before `cycle_fn`, clear in `finally`) |
| TEST-04 | Async client cleanup is tested for in-flight requests at shutdown — `aclose()` does not hang and in-flight responses raise cleanly | New test in `tests/test_clients.py` using `httpx.MockTransport` with `asyncio.sleep` handler + `asyncio.wait_for(..., timeout=2.0)` around close |

## Project Constraints (from CLAUDE.md)

Directives from `./CLAUDE.md` and `~/.claude/CLAUDE.md` that bound this work:

- **Loguru only.** No `print()`, no stdlib `logging`. New log lines use `loguru.logger.{warning,error}` with `{}` placeholders.
- **Specific exception types.** Never `except Exception:` (that's exactly what SAFETY-02 forbids in the narrowed handler) and never bare `except:`. The new APScheduler listener must also discriminate — it logs the type but does not swallow.
- **pytest-asyncio with `asyncio_mode = "auto"`** (pyproject.toml:38). New `async def test_...` need no decorator.
- **ruff (E, F, I, UP, B, SIM), line length 120.** New code must pass.
- **SecretStr discipline.** No new code touches API keys; failure logs must NOT include the cycle exception's repr if that repr could contain a URL with credentials. `httpx.HTTPError` subclasses carry the request URL — verify the existing `_sanitize_exc(exc)` helper in `engine.py:31` (already in use) is appropriate for failure-counter log lines.
- **No mixing business logic with infrastructure.** Keep the failure-counter logic in scheduler.py (the infrastructure layer); do not push it into engine.py cycle functions.
- **Atomic file writes.** Not directly applicable — no new file writes in this phase. The new `max_consecutive_failures` config field goes through the existing `_atomic_toml_write` + `app.state.search_lock` path.
- **Never log sensitive data.** Failure log lines may include `job_id` (safe — no secrets), exception type (safe), and `_sanitize_exc(exc)` output (safe — strips URL/body). Do NOT log `str(exc)` directly for `httpx.HTTPError` because the exception's `request.url` may carry an `apikey=` query parameter in pathological cases (SEC-02 will reject these at save time in Phase 66, but for now don't rely on that).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Exception narrowing in search-cycle wrapper | Scheduler infrastructure (`triggarr/search/scheduler.py:make_search_job`) | Search engine (`engine.py` already discriminates inside each cycle fn) | The job wrapper is the last line of defense before APScheduler; engine functions catch their own expected types per-call already |
| Consecutive-failure tracking | `app.state.search_failures` (in-memory dict, lifespan-scoped) | — | Mirrors `app.state.last_search_time` precedent; fresh-start each boot is correct (no persistence) |
| Log-level escalation policy | Scheduler infrastructure (new `_record_failure` helper) | Loguru sink (no change) | Policy is "after N failures, escalate" — local to the wrapper; loguru level filtering is independent |
| Job identity | `job_id = f"{app_name}_{inst_name}_search"` (scheduler.py:240, routes.py:596) | APScheduler `event.job_id` (for listener) | String key is already consistent across scheduler.py and routes.py |
| Shutdown lock drain | FastAPI lifespan `finally` block (`triggarr/search/scheduler.py:274-293`) | — | Already the canonical shutdown path — extend in place |
| Lock-holder tracking | `app.state.search_lock_holder: tuple[str, float] \| None` | — | New piece of app-state, written inside the lock acquisition in `make_search_job`, read by shutdown timeout branch |
| HTTP client cleanup | `triggarr/clients/base.py:ArrClient.close` (delegates to `httpx.AsyncClient.aclose`) | Scheduler shutdown loop (`scheduler.py:286-288`) | Cleanup is already correct under the *non-in-flight* assumption; the lock drain (RES-01) ensures we hit it in that state. TEST-04 proves the assumption holds at the httpx layer |

## Standard Stack

This phase introduces **no new dependencies**. All required libraries are already in `pyproject.toml`:

| Library | Version (from pyproject) | Purpose | Already Used? |
|---------|-------------------------|---------|---------------|
| `apscheduler` | `>=3.11,<4` (line 17) | Cron-driven async jobs | Yes — scheduler.py:21 |
| `httpx` | unpinned (transitive + direct) | Async HTTP, MockTransport for tests | Yes — clients/base.py:9 |
| `pydantic` | unpinned (via pydantic-settings) | Validation error type | Yes — clients/base.py:10, scheduler.py:20 |
| `aiosqlite` | unpinned | Async SQLite errors | Yes — scheduler.py:18 |
| `loguru` | unpinned | Logging | Yes — everywhere |
| `pytest`, `pytest-asyncio` | dev | Test framework, `asyncio_mode="auto"` | Yes |

**Version verification:**
```bash
$ uv run python -c "from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent; import inspect; print(EVENT_JOB_ERROR, inspect.signature(JobExecutionEvent))"
8192 (code, job_id, jobstore, scheduled_run_time, retval=None, exception=None, traceback=None)
```
EVENT_JOB_ERROR code is `8192`. JobExecutionEvent attributes confirmed against the installed `apscheduler>=3.11,<4`. [VERIFIED: local Python REPL against pinned dependency]

**Installation:** None required.

## Package Legitimacy Audit

Not applicable — this phase adds zero new packages. All work is inside `triggarr/search/scheduler.py`, `triggarr/models/config.py` (one new field), `triggarr/config.py` (one new DEFAULT_CONFIG comment line), and `tests/`.

## Domain Investigation — Current State

### A. Exception handling in `make_search_job` (the SAFETY-02 target)

**File:** `triggarr/search/scheduler.py:72-131`

Current shape (verified by reading the full function):

```python
async def job() -> None:
    clients = getattr(app.state, f"{app_name}_clients", {})
    client = clients.get(instance_name)
    if client is None:
        return
    instance_config = app.state.settings.get_enabled_instances(app_name).get(instance_name)
    if instance_config is None:
        return
    async with app.state.search_lock:
        try:
            app.state.triggarr_state = await cycle_fn(...)
            await asyncio.get_running_loop().run_in_executor(None, save_state, ...)
            # --- Tracking check: resolve pending search outcomes ---
            try:
                tracking_result = await run_tracking_check(...)
                ...
            except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as tracking_exc:
                logger.warning("Tracking: check failed -- {exc}", exc=tracking_exc)
        except Exception as exc:                              # <-- SAFETY-02 target
            logger.error(
                "{app}: Unhandled error in search cycle -- {exc}",
                app=app_name.title(),
                exc=exc,
            )
```

**Concrete file:line anchors:**

- Bare `except Exception as exc:` at **scheduler.py:124** — this is the SAFETY-02 fix target.
- The narrower tuple already exists in the inner tracking handler at **scheduler.py:119** — `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)`. Adopt the same tuple for the outer handler.
- `logger.error` call at **scheduler.py:125-129** stays; just narrow what reaches it.
- Imports at the top of scheduler.py (lines 18-23) already include `aiosqlite`, `httpx`, `pydantic` — no new imports needed for SAFETY-02.

**Why the narrowing is safe:** `engine.py` already catches the narrow tuple at every external boundary (verified: 22 occurrences via `grep -n "except (httpx.HTTPError" engine.py`). The only exceptions that should bubble out of `cycle_fn` are:
- `PendingCapExceeded` (now caught explicitly inside each cycle since the review-pass-1 commit c91f0cb — verified at engine.py:416, 465, 650, 705, 893, 943).
- The exact tuple we're narrowing to (which we still want to handle gracefully).
- Truly unexpected: `RuntimeError`, `MemoryError`, `KeyError` from a code bug, `asyncio.CancelledError` (shutdown signal).

`asyncio.CancelledError` is a special case in Python 3.8+ — it inherits from `BaseException`, not `Exception`, so it would NOT be caught by either the old `except Exception` or the new narrowed tuple. Both are correct on this point. The shutdown drain (RES-01) is the mechanism that handles cancellation; this handler doesn't need to.

**Failing test that proves current overly-broad behavior:**

`tests/test_scheduler.py:35-55` (`test_make_search_job_exception_swallowed`) asserts that the wrapper swallows a `RuntimeError`. **This test will need to be inverted** to assert the opposite (RuntimeError propagates) once SAFETY-02 is in place. The planner must include this test edit in the plan — it is not optional.

A second test that asserts a narrow-type IS swallowed (e.g., `httpx.ConnectError`) should be added to keep coverage of the kept-behavior path.

### B. APScheduler integration (the EVENT_JOB_ERROR question)

**Current state:** Triggarr does NOT register any `add_listener` calls. `AsyncIOScheduler` runs jobs and APScheduler logs exceptions at WARNING level on the `apscheduler.executors.default` logger — but Triggarr uses loguru, and loguru does not intercept stdlib `logging` by default. So a RuntimeError that propagates out of `make_search_job` after Phase 65 narrowing would land in APScheduler's internal logging and effectively disappear from Triggarr's log stream.

**Verified by:** `grep -rn "EVENT_JOB\|add_listener" triggarr/` returns zero hits.

**Wiring needed:** Register a listener inside `create_lifespan`, after `scheduler.start()` (around scheduler.py:255), before the lifespan yields. The listener function receives a `JobExecutionEvent` with `event.job_id`, `event.exception`, `event.traceback`. The natural action is `logger.error("{job}: unexpected job failure: {type}: {exc}", job=event.job_id, type=type(event.exception).__name__, exc=event.exception)`.

**Important behavioral note (from APScheduler discussion #1016):** *"If you catch the exception inside the coroutine job, EVENT_JOB_ERROR won't fire because from APScheduler's perspective the job completed successfully."* This means SAFETY-02's narrowing is what *makes* EVENT_JOB_ERROR fire for unexpected types — the two features are coupled. Currently, the broad `except Exception` swallows everything and EVENT_JOB_ERROR never fires.

**Import paths:**
```python
from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent
```
JobExecutionEvent is imported only for type-hinting the listener parameter; can be omitted if using `def on_job_error(event):` without annotation. ruff's `UP` rules would let it pass either way.

### C. Consecutive-failure counter (SAFETY-03)

**Storage decision — recommended: in-memory dict on `app.state`.**

Three options were considered:

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| `app.state.search_failures: dict[str, int]` | Mirrors `app.state.last_search_time` precedent at scheduler.py:221; zero new persistence; lifespan-scoped (correct lifetime); single uvicorn worker means no cross-process state | Lost on restart (acceptable — fresh start IS the correct semantic for "consecutive") | **Recommended** |
| New SQLite table | Survives restart; queryable | Asymmetric with `last_search_time` (which is in-memory); persistence implies "consecutive across restarts" which is the wrong semantic (a restart should reset the counter, not preserve it) | Reject |
| `app.state.triggarr_state` (the JSON-persisted state) | Already persisted | Same semantic problem as SQLite; expands state schema; needs migration | Reject |

**Job identity:** Use the existing `job_id = f"{app_name}_{inst_name}_search"` string (defined at scheduler.py:240). It is already the APScheduler job ID, already used as a key in routes.py for scheduler.get_job/remove_job (lines 596, 607, 625), and is stable across restarts (deterministic from config). Pass it through `make_search_job` as a closure variable — it is already available at the call site (scheduler.py:239-247).

**Persistence across restarts:** Fresh-start each boot. The phrase "consecutive failures" semantically resets when the daemon restarts. This is also the safest default — a long-stopped instance that fails to restart cleanly doesn't immediately escalate to ERROR on the first new failure.

**Counter lifecycle:**
1. On lifespan startup (`create_lifespan` after `scheduler.start()`): `app.state.search_failures = {}` (empty dict). Optionally pre-populate with `{job_id: 0 for job_id in ...}` for clarity, but `dict.get(job_id, 0)` is sufficient.
2. On cycle success (inside the `try:` block, after `save_state` returns): `app.state.search_failures[job_id] = 0`. Reset is essential — a transient blip should not push us toward escalation forever.
3. On caught exception (the narrowed tuple): `count = app.state.search_failures.get(job_id, 0) + 1; app.state.search_failures[job_id] = count`; then `log_level = "error" if count >= settings.general.max_consecutive_failures else "warning"`; `getattr(logger, log_level)(...)`.

**Per-instance scoping:** Each `(app_type, instance_name)` pair is a distinct job_id, so the counter is naturally per-instance. A Radarr/Default failure does not affect Sonarr/4K's counter. This matches the per-instance scoping precedent established in commit 28b22b7 ("scope pending-row cap query to (app, instance_id)").

### D. Configurable N (the new `max_consecutive_failures` field)

**Location in config:**

- **`triggarr/models/config.py:73-85`** (GeneralConfig class) — add field after `tracking_delay_seconds`:
  ```python
  max_consecutive_failures: int = 5  # SAFETY-03: escalate WARNING→ERROR after N failures
  ```
  Existing field naming convention: snake_case, descriptive, with units in the name when applicable (`tracking_window_minutes`, `request_timeout`, `page_size`). `max_consecutive_failures` follows that pattern.

- **`triggarr/config.py:DEFAULT_CONFIG`** (lines 22-48) — add commented line in `[general]` section:
  ```toml
  # max_consecutive_failures = 5
  ```
  Place after the existing `# tracking_delay_seconds = 90` line. The commented form matches the pattern of other tunable-but-rarely-touched general settings.

- **`triggarr/web/routes.py:494-507`** (POST /settings handler `new_config["general"]` dict) — add:
  ```python
  "max_consecutive_failures": safe_int(form.get("max_consecutive_failures"), 5, 1, 100),
  ```
  Lower bound 1 (zero would mean "escalate immediately" — pointless), upper bound 100 (no operator would set this higher; defends against typos).

- **`triggarr/web/routes.py:395-403`** (the dict that builds the settings form template context) — add `"max_consecutive_failures": settings.general.max_consecutive_failures`.

- **Settings template** (`triggarr/web/templates/settings.html` likely; planner should grep for `max_history_rows` to find the right spot) — add an `<input>` to expose the field in the UI. Convention: number input with min/max attributes matching the route validation bounds.

**Read site:** Inside `make_search_job` closure, read `app.state.settings.general.max_consecutive_failures` at exception-catch time (not at job-factory time) so a config edit takes effect on the next failure without a restart.

### E. Shutdown timeout 35s → 60s + holder logging (RES-01)

**Current state — `triggarr/search/scheduler.py:272-293`:**

```python
try:
    yield
finally:
    # 1. Stop scheduler from scheduling new jobs (does NOT wait for async jobs)
    scheduler.shutdown(wait=False)

    # 2. Drain any in-flight search cycle before closing resources (DEBT-06)
    try:
        await asyncio.wait_for(app.state.search_lock.acquire(), timeout=35.0)
        app.state.search_lock.release()
    except TimeoutError:
        logger.warning("Shutdown: search cycle did not finish in 35s — forcing close")

    # 3. Close HTTP clients (all instances)
    for app_type in APP_TYPES:
        for client in getattr(app.state, f"{app_type}_clients", {}).values():
            await client.close()

    # 4. Close shared database connection (all writes complete per step 2)
    await app.state.db.close()

    logger.info("Search engine stopped")
```

**Two changes required:**

1. **Bump timeout 35.0 → 60.0** at scheduler.py:280. This is a one-line change.

2. **Track which job holds the lock + when it acquired it.** The current warning message ("search cycle did not finish in 35s") is non-actionable — the operator cannot tell which Radarr/Sonarr/Lidarr instance is stuck. Add:

   - In `make_search_job`, immediately after `async with app.state.search_lock:` (currently scheduler.py:80), set:
     ```python
     app.state.search_lock_holder = (job_id, time.monotonic())
     ```
     Use a `try/finally` to clear it: `app.state.search_lock_holder = None` in the finally branch (placed alongside the existing `try`/`except Exception` structure).
   - In `create_lifespan` initialization, declare `app.state.search_lock_holder: tuple[str, float] | None = None` (near the other `app.state.*` initializations around scheduler.py:200-228).
   - In the shutdown TimeoutError branch, read the holder and log it:
     ```python
     except TimeoutError:
         holder = getattr(app.state, "search_lock_holder", None)
         if holder:
             job_id, started = holder
             elapsed = time.monotonic() - started
             logger.warning(
                 "Shutdown: search cycle did not finish in 60s — job={job} elapsed={elapsed:.1f}s — forcing close",
                 job=job_id, elapsed=elapsed,
             )
         else:
             logger.warning("Shutdown: search lock did not drain in 60s but no holder recorded — forcing close")
     ```

**Race safety:** Reading `search_lock_holder` after the timeout fires is safe in single-event-loop asyncio because the job task is still alive (otherwise the lock would have been released). The reader and writer never interleave because:
- Writer is inside `async with app.state.search_lock:` (only one writer at a time).
- Reader runs in the finally block after `scheduler.shutdown(wait=False)` — the scheduler will not start new jobs.

**Why `time.monotonic`** not `time.time`: monotonic does not jump backward on NTP correction; it is the correct primitive for elapsed-time measurements. Already used in `engine.py:cycle_start = time.monotonic()` at line 304.

**Existing test impact:** `tests/test_scheduler.py:63-89` (`test_shutdown_drains_search_lock`) and `:92-112` (`test_shutdown_proceeds_after_lock_released`) — both pass under the no-contention path. Neither asserts the holder log message. **Add a new test** that simulates a never-releasing lock (acquire it, then trigger lifespan exit without releasing) and asserts the holder/elapsed warning fires. Use `asyncio.wait_for` with a short timeout patched to 0.1s (via `monkeypatch` of the `60.0` constant) so the test does not actually wait 60 seconds.

### F. httpx client lifecycle and the aclose() hang risk (TEST-04)

**Current state — `triggarr/clients/base.py:26-36, 275-283`:**

- Clients are constructed in the lifespan once per enabled instance (scheduler.py:188-198) and stored on `app.state.{radarr,sonarr,lidarr}_clients[instance_name]`. They are long-lived singletons, not per-cycle.
- `ArrClient.close()` (base.py:275-277) just calls `await self._client.aclose()` on the underlying `httpx.AsyncClient`.
- At shutdown, the lifespan iterates all instances and calls `await client.close()` (scheduler.py:286-288).

**The hang risk:** Per the httpx discussion #2093 and #2138, `AsyncClient.aclose()` raises `RuntimeError: The connection pool was closed while N HTTP requests/responses were still in-flight` when there are pending requests. **But the failure mode is "raise", not "hang"** — at least at the httpx layer. The hang risk is upstream: if `await aclose()` is awaited while a `request()` is still running on the same connection pool, httpx may wait briefly on the pool semaphore before deciding to abort. In our case, RES-01's lock drain ensures the search cycle has completed (or been forcibly cancelled by `scheduler.shutdown(wait=False)`) before we hit `await client.close()`. So in normal operation we never call `aclose` with truly in-flight requests.

**What TEST-04 must prove:**
1. Call `aclose()` while requests ARE in flight (forced by mock).
2. The `aclose()` call completes within a bounded time (use `asyncio.wait_for(client.close(), timeout=2.0)`).
3. The in-flight request task raises cleanly (a httpx exception, not a hang).

**Test pattern (recommended):**

```python
async def test_aclose_does_not_hang_with_in_flight_requests() -> None:
    """TEST-04: ArrClient.close() completes within 2s even with pending requests.

    Proves RES-01 + TEST-04: the shutdown drain (extended to 60s in lifespan)
    is sufficient because aclose() itself does not block indefinitely on a
    pending request — it cancels the connection pool and the awaiting task
    surfaces an httpx exception.
    """
    request_started = asyncio.Event()

    async def slow_handler(request: httpx.Request) -> httpx.Response:
        request_started.set()
        await asyncio.sleep(10)  # would block forever if not interrupted
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(slow_handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")

    # Start a request in the background; do NOT await it yet
    pending = asyncio.create_task(client.get("/slow"))
    await request_started.wait()  # ensure the request is actually in-flight

    # Cancel the pending request first (the recommended pattern per httpx #2093)
    pending.cancel()
    with contextlib.suppress(asyncio.CancelledError, httpx.HTTPError):
        await pending

    # Now close MUST complete within 2 seconds
    await asyncio.wait_for(client.close(), timeout=2.0)
```

**Important nuance:** The httpx project's official guidance (#2093) is "cancel pending tasks before aclose, then close." TEST-04's success criterion is "aclose() does not hang AND in-flight responses raise cleanly." We satisfy this by (a) cancelling the pending task, (b) verifying it surfaces a `CancelledError` or `httpx` exception (not a hang), and (c) verifying `close()` completes within the timeout.

**Variant test (optional but recommended):** Call `await client.close()` WITHOUT cancelling first, wrapped in `pytest.raises(RuntimeError)` and `asyncio.wait_for(..., timeout=2.0)`. This proves the documented httpx behavior holds in our version. If httpx ever changes behavior, this test will surface it.

## Implementation Approach (per success criterion, with file:line anchors)

### Success #1: SAFETY-02 — Narrow scheduler exception handler

**Files touched:**
- `triggarr/search/scheduler.py:124` — change `except Exception as exc:` to `except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:`. Imports already in place at lines 18-20.
- `triggarr/search/scheduler.py` (around line 255, after `scheduler.start()`) — register `EVENT_JOB_ERROR` listener for the now-propagating types:
  ```python
  from apscheduler.events import EVENT_JOB_ERROR
  def _on_job_error(event):
      logger.error(
          "Job {job} failed unexpectedly: {type}: {exc}",
          job=event.job_id,
          type=type(event.exception).__name__,
          exc=event.exception,
      )
  scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
  ```
- `tests/test_scheduler.py:35-55` — **invert the assertion** in `test_make_search_job_exception_swallowed` (rename to `test_make_search_job_unexpected_exception_propagates`); assert `pytest.raises(RuntimeError)`. Add a sibling test `test_make_search_job_httperror_swallowed` that asserts a `httpx.ConnectError` IS caught and logged.

**Why narrow tuple is sufficient:** `engine.py` catches the same tuple at every outbound boundary (22 sites). Anything that escapes those is a code bug (KeyError, AttributeError, RuntimeError) or a runtime/system failure (MemoryError) — both of which SHOULD propagate to APScheduler's error handler so the operator sees them in the log via the new listener.

### Success #2: SAFETY-03 — Consecutive-failure counter + escalation

**Files touched:**
- `triggarr/models/config.py:85` — add `max_consecutive_failures: int = 5` to `GeneralConfig`.
- `triggarr/config.py:32` — add `# max_consecutive_failures = 5` to DEFAULT_CONFIG template (in `[general]` block after `# tracking_delay_seconds = 90`).
- `triggarr/search/scheduler.py` (in `create_lifespan` near line 221) — initialize `app.state.search_failures: dict[str, int] = {}`.
- `triggarr/search/scheduler.py:124-129` — in the new narrowed except branch:
  ```python
  except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
      job_id = f"{app_name}_{instance_name}_search"  # already passed to add_job
      count = app.state.search_failures.get(job_id, 0) + 1
      app.state.search_failures[job_id] = count
      threshold = app.state.settings.general.max_consecutive_failures
      log_fn = logger.error if count >= threshold else logger.warning
      log_fn(
          "{app}: search cycle failed ({count}/{threshold}) -- {exc}",
          app=app_name.title(),
          count=count,
          threshold=threshold,
          exc=_sanitize_exc(exc),  # see note below
      )
  ```
- `triggarr/search/scheduler.py` (after a successful cycle, inside the try block) — reset counter:
  ```python
  app.state.search_failures[job_id] = 0  # reset on success
  ```
  Place this after `save_state` returns successfully, but before the tracking block (a tracking failure should NOT prevent a search-cycle success from resetting the counter, since the cycle itself succeeded).
- `triggarr/web/routes.py:500` — add `"max_consecutive_failures": safe_int(form.get("max_consecutive_failures"), 5, 1, 100)` to the general dict.
- `triggarr/web/routes.py:395-403` — add to template context dict.
- Settings template — add input field (planner: find by grepping `max_history_rows`).

**Note on `_sanitize_exc`:** Defined at `triggarr/search/engine.py:31-71`. Returns a redacted summary of the exception ("HTTPStatusError 401", "ValidationError 3 errors", etc.) so that secrets in `httpx.HTTPError.request.url` cannot leak. This is the right primitive for failure-log messages. The scheduler can `from triggarr.search.engine import _sanitize_exc` — there is precedent for cross-module reuse of `_`-prefixed helpers in this repo (verified: `_sync_auth_state` imported into scheduler.py:232).

Alternative: bring `_sanitize_exc` into a new `triggarr.search._common` module or rename it without the underscore. The planner can decide on the cleaner refactor.

**Tests to add:**
- `test_failure_counter_increments_on_cycle_exception` — call job 3 times with `cycle_fn=AsyncMock(side_effect=httpx.ConnectError("x"))`, assert `app.state.search_failures[job_id] == 3`.
- `test_failure_counter_escalates_at_threshold` — set `max_consecutive_failures=3`, drive 3 failures, capture log via loguru sink, assert the 3rd message has `ERROR` level (or whatever record attribute loguru exposes), the first 2 are WARNING.
- `test_failure_counter_resets_on_success` — fail twice, succeed once, fail again, assert count is 1 after the final failure.
- `test_failure_counter_per_instance` — fail Radarr/Default, succeed Radarr/4K, assert Radarr/4K's counter is 0 and Radarr/Default's is 1 — proves per-job-id scoping.

**Loguru level capture pattern:** `tests/test_startup.py:261-267` uses `logger.add(sink, format="{message}", level="WARNING")`. For level discrimination, use `format="{level} | {message}"` or the structured record dict via `logger.add(sink, serialize=True)`.

### Success #3: RES-01 — Shutdown timeout 35s → 60s + holder logging

**Files touched:**
- `triggarr/search/scheduler.py:280` — change `timeout=35.0` → `timeout=60.0`.
- `triggarr/search/scheduler.py` (near line 221, with other `app.state.*` initialization) — add `app.state.search_lock_holder: tuple[str, float] | None = None`.
- `triggarr/search/scheduler.py:80-130` (inside `make_search_job`, inside the `async with app.state.search_lock:` block) — set holder before `cycle_fn`, clear in `finally`:
  ```python
  async with app.state.search_lock:
      job_id = f"{app_name}_{instance_name}_search"
      app.state.search_lock_holder = (job_id, time.monotonic())
      try:
          ... (existing cycle + tracking + save) ...
      except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
          ... (failure-counter logic from Success #2) ...
      finally:
          app.state.search_lock_holder = None
  ```
- `triggarr/search/scheduler.py:282-283` (the TimeoutError branch in lifespan shutdown) — replace single-line warning with structured warning that reads `search_lock_holder`. Code shown in Domain Investigation §E above.
- Add `import time` to scheduler.py top (verify it's not already there — line check).

**Tests to add:**
- `test_shutdown_timeout_logs_holder_identity` — patch `app.state.search_lock_holder = ("radarr_Default_search", time.monotonic() - 100.0)` then trigger lifespan exit while holding the lock (acquire without releasing); patch the timeout to 0.1s; assert the log message contains `radarr_Default_search` and a value ≥100 seconds.
- `test_shutdown_drains_search_lock` (existing at test_scheduler.py:63) — re-verify it still passes with the new timeout value (60s) under the no-contention path.

### Success #4: TEST-04 — Async client cleanup does not hang

**Files touched:**
- `tests/test_clients.py` — add at least one test (see Domain Investigation §F for the recommended pattern). Place near the existing `test_request_with_retry_*` tests (line 80+) since they share the `_ConcreteClient + MockTransport` setup.

**Imports needed at the top of test_clients.py:**
- `import asyncio` — likely already present, verify
- `import contextlib` — for `suppress(asyncio.CancelledError, ...)`
- `import httpx` — already present (line 9)

**Why `MockTransport` not real HTTP:** Mock transports are deterministic and never actually open sockets — the test stays fast and hermetic. The `MockTransport` handler can be `async def` since httpx 0.27+; if the installed version is older, the handler must be sync but can use `asyncio.sleep` via `asyncio.get_event_loop().run_until_complete` — verify the installed httpx version supports async handlers (it does: confirmed by `httpx.MockTransport` accepting `Awaitable[Response]` handlers since 0.20). 

[VERIFIED via local Python]: `httpx.MockTransport` accepts async handlers.

## Patterns to Mirror

### Per-instance `app.state` dict (precedent for `search_failures`)
**Source:** `triggarr/search/scheduler.py:221`
```python
app.state.last_search_time: dict[str, float] = {}
```
Used in `routes.py:818-839` (rate-limit check on search-now endpoint). Same shape, same lifecycle (lifespan-scoped, per-job-id keyed). New `app.state.search_failures: dict[str, int] = {}` follows the same pattern verbatim.

### Narrow exception tuple discrimination
**Source:** `triggarr/search/engine.py:426` (and 21 others)
```python
except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
```
This is the canonical tuple. Reuse exactly — do not add or remove types without justification.

### `_sanitize_exc(exc)` for safe error logging
**Source:** `triggarr/search/engine.py:31-71`
Strips request bodies and URLs from exception reprs so secrets cannot leak into logs. Reuse in the failure-counter log line.

### loguru sink capture in tests
**Source:** `tests/test_startup.py:261-267`
```python
sink = io.StringIO()
handler_id = logger.add(sink, format="{message}", level="WARNING")
try:
    ...
finally:
    logger.remove(handler_id)
assert "expected text" in sink.getvalue()
```
For level discrimination (SAFETY-03 escalation tests), use `format="{level} | {message}"`.

### `httpx.MockTransport` with sync handler
**Source:** `tests/test_clients.py:86-97`
```python
def handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"ok": True})

transport = httpx.MockTransport(handler)
client = _ConcreteClient(base_url="http://test", api_key="key")
client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
```
Extend with an async handler for TEST-04 (see §F).

### Job ID derivation
**Source:** `triggarr/web/routes.py:596, 607`; `triggarr/search/scheduler.py:240`
```python
job_id = f"{app_name}_{inst_name}_search"
```
Use the exact same f-string; do NOT introduce a new identifier scheme.

### APScheduler add_job pattern (already in place)
**Source:** `triggarr/search/scheduler.py:241-247`
```python
scheduler.add_job(
    job_fn,
    "interval",
    minutes=cfg.search_interval,
    id=job_id,
    next_run_time=datetime.now(UTC),
)
```
The new `add_listener` call goes near `scheduler.start()` (line 255), AFTER `add_job` so the listener is in place before jobs can fire.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-job execution event hooks | Custom wrapper that records every cycle outcome to a separate table | `scheduler.add_listener(fn, EVENT_JOB_ERROR \| EVENT_JOB_EXECUTED)` | APScheduler 3.x already publishes these events; building a parallel mechanism creates two sources of truth |
| Exception sanitization | New regex stripper for secrets | Existing `_sanitize_exc` in `engine.py:31` | Already battle-tested; redacts the same patterns we need |
| Async lock with holder tracking | `asyncio.Lock` subclass that records current holder | Plain `asyncio.Lock` + sibling `app.state.search_lock_holder: tuple \| None` | Lock subclasses are fragile; sibling state is one tuple + a finally clause |
| HTTP client cleanup with timeout | Custom drain loop that polls in-flight count | `asyncio.wait_for(client.close(), timeout=N)` | One line; the wait_for is the cancellation primitive |
| Configurable threshold storage | New TOML section `[scheduler]` | Add field to existing `[general]` (GeneralConfig) | One field doesn't justify a new section; existing precedent has all tunable knobs in `[general]` |
| Failure persistence | SQLite table for consecutive-failure history | In-memory `dict[str, int]` on app.state | "Consecutive" semantics reset on restart; persistence implies wrong semantic |
| Lifespan shutdown ordering | Custom shutdown signal handler | Existing FastAPI lifespan `finally` block | Already correct; just extend the timeout |

**Key insight:** APScheduler 3.x's event system is the right abstraction for "the job failed unexpectedly." We were not using it. Wiring it up is one `add_listener` call plus a 5-line callback. That's the right pattern for SAFETY-02's now-propagating types.

## Common Pitfalls

### Pitfall 1: Forgetting to reset the failure counter on success
**What goes wrong:** Counter monotonically grows; first failure after a long success streak immediately escalates to ERROR.
**Why it happens:** Easy to add the increment branch without remembering the reset branch.
**How to avoid:** The reset MUST live in the success path inside the same `try:` block. Add an explicit test (`test_failure_counter_resets_on_success`) that fails-twice-then-succeeds-then-fails-once and asserts count==1.
**Warning signs:** Production ERROR-level logs appearing after a single transient httpx failure.

### Pitfall 2: APScheduler `EVENT_JOB_ERROR` listener does not fire if we still catch broadly
**What goes wrong:** Plan applies SAFETY-02 narrowing but forgets to register the listener; unexpected types now propagate but nothing logs them.
**Why it happens:** The two pieces (narrowing + listener) are functionally coupled but live in different functions (`job()` vs `lifespan`).
**How to avoid:** Plan them in the same task. Verify by a test that injects a `RuntimeError` via the cycle and asserts a log line containing `"failed unexpectedly: RuntimeError"`.
**Warning signs:** A bug-class exception (KeyError, RuntimeError) silently disappears in production — operator sees nothing.

### Pitfall 3: `time.monotonic()` not `time.time()` for elapsed measurement
**What goes wrong:** NTP correction jumps the wall clock backward; elapsed runtime in the shutdown log becomes negative.
**How to avoid:** Use `time.monotonic()`. Already the precedent (`engine.py:304`).
**Warning signs:** Log message reads "elapsed=-3.2s — forcing close".

### Pitfall 4: Tracking `search_lock_holder` outside the lock
**What goes wrong:** Setting `app.state.search_lock_holder = (job_id, ...)` BEFORE `async with app.state.search_lock:` lets two jobs both record themselves as holder.
**How to avoid:** The assignment must be INSIDE the `async with` block. The clear (`= None`) lives in the same `try/finally` (also inside the lock).
**Warning signs:** Shutdown log message names the wrong job.

### Pitfall 5: `httpx.AsyncClient.aclose()` raises, doesn't hang — but the wait is real
**What goes wrong:** Test assumes `aclose()` returns instantly; in reality httpx waits briefly on the connection pool.
**How to avoid:** TEST-04 must wrap `client.close()` in `asyncio.wait_for(..., timeout=2.0)` — short enough to catch a real hang, long enough to allow httpx's normal cleanup.
**Warning signs:** Test passes locally but flakes in CI with `TimeoutError`.

### Pitfall 6: The existing `test_make_search_job_exception_swallowed` will FAIL after SAFETY-02
**What goes wrong:** A test from before the narrowing actively asserts the old behavior; the plan must update it, not just add new tests.
**How to avoid:** The plan MUST include an edit to `tests/test_scheduler.py:35-55` — invert the assertion. Otherwise pytest will fail at the SAFETY-02 commit.
**Warning signs:** Plan-checker should catch this; if missed, CI will fail on the SAFETY-02 task and block the wave.

### Pitfall 7: `asyncio.CancelledError` is NOT in the narrowed tuple — by design
**What goes wrong:** Someone "fixes" the missing CancelledError by adding it to the except tuple.
**How to avoid:** CancelledError is `BaseException`, not `Exception`. It is the shutdown signal — letting it propagate is correct (it unwinds the `async with app.state.search_lock:` cleanly, which is what the drain depends on). Document this in a comment.
**Warning signs:** Shutdown drain never completes because a cycle catches its own cancellation.

### Pitfall 8: Loguru level format string in tests
**What goes wrong:** Default `format="{message}"` capture does NOT include the level. Asserting "ERROR" in the sink output silently fails.
**How to avoid:** Use `format="{level} | {message}"` when the test discriminates on level (SAFETY-03 escalation tests). Or use `logger.add(sink, serialize=True)` and parse JSON records.
**Warning signs:** SAFETY-03 escalation test passes even when escalation is broken.

### Pitfall 9: `app.state.search_failures` not initialized for newly-added instances
**What goes wrong:** A new Radarr instance added at runtime via POST /api/instance/add doesn't have a key in the failures dict; `.get(job_id, 0)` handles that, but a `[job_id]` write would KeyError.
**How to avoid:** Always read with `.get(job_id, 0)`; writes (`[job_id] = count`) are always safe because dict creates the key. No initialization needed at instance-add time.

## Code Examples (verified patterns from this repo + APScheduler docs)

### Existing job factory (the function being modified)
```python
# Source: triggarr/search/scheduler.py:72-131 (current state)
async def job() -> None:
    clients = getattr(app.state, f"{app_name}_clients", {})
    client = clients.get(instance_name)
    if client is None:
        return
    instance_config = app.state.settings.get_enabled_instances(app_name).get(instance_name)
    if instance_config is None:
        return
    async with app.state.search_lock:
        try:
            app.state.triggarr_state = await cycle_fn(...)
            await asyncio.get_running_loop().run_in_executor(None, save_state, ...)
            try:
                tracking_result = await run_tracking_check(...)
                ...
            except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as tracking_exc:
                logger.warning("Tracking: check failed -- {exc}", exc=tracking_exc)
        except Exception as exc:                                # <-- SAFETY-02 target
            logger.error("{app}: Unhandled error in search cycle -- {exc}", app=app_name.title(), exc=exc)
```

### Proposed wrapper after Phase 65 (illustrative — planner refines)
```python
# After Phase 65:
async with app.state.search_lock:
    job_id = f"{app_name}_{instance_name}_search"
    app.state.search_lock_holder = (job_id, time.monotonic())
    try:
        app.state.triggarr_state = await cycle_fn(...)
        await asyncio.get_running_loop().run_in_executor(None, save_state, ...)
        app.state.search_failures[job_id] = 0  # SAFETY-03: reset on success
        try:
            tracking_result = await run_tracking_check(...)
            ...
        except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as tracking_exc:
            logger.warning("Tracking: check failed -- {exc}", exc=tracking_exc)
    except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:  # SAFETY-02
        count = app.state.search_failures.get(job_id, 0) + 1                              # SAFETY-03
        app.state.search_failures[job_id] = count
        threshold = app.state.settings.general.max_consecutive_failures
        log_fn = logger.error if count >= threshold else logger.warning
        log_fn(
            "{app}: search cycle failed ({count}/{threshold}) -- {exc}",
            app=app_name.title(), count=count, threshold=threshold, exc=_sanitize_exc(exc),
        )
    finally:
        app.state.search_lock_holder = None                                                # RES-01
```

### APScheduler EVENT_JOB_ERROR listener
```python
# Source: apscheduler.events docs + verified inspect.signature
# Place in create_lifespan, after scheduler.start() (around scheduler.py:255)
from apscheduler.events import EVENT_JOB_ERROR

def _on_job_error(event):
    logger.error(
        "Job {job} failed unexpectedly: {type}: {exc}",
        job=event.job_id,
        type=type(event.exception).__name__,
        exc=event.exception,
    )

scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
```

### httpx async handler for TEST-04
```python
# Source: tests/test_clients.py:86-97 pattern extended with async handler
# Verified: httpx.MockTransport accepts async handlers in httpx 0.20+
async def slow_handler(request: httpx.Request) -> httpx.Response:
    await asyncio.sleep(10)
    return httpx.Response(200)

transport = httpx.MockTransport(slow_handler)
client = _ConcreteClient(base_url="http://test", api_key="key")
client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
```

### Shutdown drain with holder logging
```python
# After Phase 65 (triggarr/search/scheduler.py:278-289):
try:
    await asyncio.wait_for(app.state.search_lock.acquire(), timeout=60.0)
    app.state.search_lock.release()
except TimeoutError:
    holder = getattr(app.state, "search_lock_holder", None)
    if holder:
        job_id, started = holder
        elapsed = time.monotonic() - started
        logger.warning(
            "Shutdown: search cycle did not finish in 60s -- job={job} elapsed={elapsed:.1f}s -- forcing close",
            job=job_id, elapsed=elapsed,
        )
    else:
        logger.warning("Shutdown: search lock did not drain in 60s (no holder recorded) -- forcing close")
```

## Runtime State Inventory

Not a rename/refactor/migration phase. The only runtime state changes:

| Category | Items | Action Required |
|----------|-------|------------------|
| Stored data | None — `app.state.search_failures` is in-memory; `search_lock_holder` is in-memory. No database schema change. No `triggarr.toml` schema break (new `max_consecutive_failures` field has a default; old configs load unchanged). | None |
| Live service config | None — APScheduler jobs are rebuilt on every lifespan from config; the new `EVENT_JOB_ERROR` listener attaches at startup. | None |
| OS-registered state | None — no systemd, no cron, no Windows tasks. | None |
| Secrets/env vars | None — no new env vars, no SOPS keys, no API keys touched. | None |
| Build artifacts | None — no `pyproject.toml` change (no new deps); existing wheels/Docker images unaffected. | None |

**Backward compatibility:** A user's existing `triggarr.toml` continues to work unchanged. The new `max_consecutive_failures` field defaults to 5 if absent (pydantic field default). Existing scheduler behavior changes in two operator-visible ways: (1) genuinely unexpected exceptions now log a single `"Job X failed unexpectedly: TypeName: ..."` line at ERROR level (was: silent), and (2) repeated transient failures escalate from WARNING to ERROR after 5 consecutive — that's the intended behavior of SAFETY-03.

## Environment Availability

This phase has no new external dependencies. All libraries are already declared in `pyproject.toml` and installed by `uv sync --extra dev`. No tool, service, or runtime probe is required.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `apscheduler` (EVENT_JOB_ERROR listener API) | SAFETY-02 listener wiring | ✓ | 3.11.2.post1 (per `pyproject.toml: apscheduler>=3.11,<4`) | — |
| `httpx.MockTransport` (async handler) | TEST-04 in-flight test | ✓ | bundled with httpx (already a transitive dep) | — |
| `loguru` level filtering in tests | SAFETY-03 escalation tests | ✓ | already used at tests/test_startup.py:261 | — |

No missing dependencies. No fallbacks required.

## Validation Architecture

`workflow.nyquist_validation` not set in `.planning/config.json` → treated as enabled → including this section.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3+ with pytest-asyncio (asyncio_mode="auto", pyproject.toml:38) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`); no separate pytest.ini |
| Quick run command | `uv run pytest tests/test_scheduler.py tests/test_clients.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SAFETY-02 | Unexpected exception type propagates (no longer silently caught) | unit | `uv run pytest tests/test_scheduler.py::test_make_search_job_unexpected_exception_propagates -x` | ❌ — Wave 0 (rename + invert existing `test_make_search_job_exception_swallowed`) |
| SAFETY-02 | Narrow-tuple exception IS still caught and logged | unit | `uv run pytest tests/test_scheduler.py::test_make_search_job_httperror_swallowed -x` | ❌ — Wave 0 (new test) |
| SAFETY-02 | EVENT_JOB_ERROR listener fires on propagated exception | integration | `uv run pytest tests/test_scheduler.py::test_event_job_error_listener_logs_unexpected_exception -x` | ❌ — Wave 0 (new test) |
| SAFETY-03 | Failure counter increments per cycle exception | unit | `uv run pytest tests/test_scheduler.py::test_failure_counter_increments_on_cycle_exception -x` | ❌ — Wave 0 (new test) |
| SAFETY-03 | Failure counter escalates WARNING→ERROR at threshold | unit | `uv run pytest tests/test_scheduler.py::test_failure_counter_escalates_at_threshold -x` | ❌ — Wave 0 (new test) |
| SAFETY-03 | Failure counter resets on successful cycle | unit | `uv run pytest tests/test_scheduler.py::test_failure_counter_resets_on_success -x` | ❌ — Wave 0 (new test) |
| SAFETY-03 | Counter is per-(app, instance), not global | unit | `uv run pytest tests/test_scheduler.py::test_failure_counter_per_instance_scoped -x` | ❌ — Wave 0 (new test) |
| SAFETY-03 | New `max_consecutive_failures` config field loads with default 5 | unit | `uv run pytest tests/test_config.py::test_general_config_default_max_consecutive_failures -x` | ❌ — Wave 0 (new test) |
| RES-01 | Shutdown timeout is 60s (was 35s) | unit | `uv run pytest tests/test_scheduler.py::test_shutdown_timeout_is_60s -x` | ❌ — Wave 0 (new test, asserts on the constant or via patched timeout) |
| RES-01 | Shutdown timeout branch logs holder job_id + elapsed | unit | `uv run pytest tests/test_scheduler.py::test_shutdown_timeout_logs_holder_identity -x` | ❌ — Wave 0 (new test) |
| RES-01 | Existing graceful-shutdown tests still pass with new timeout | regression | `uv run pytest tests/test_scheduler.py::test_shutdown_drains_search_lock tests/test_scheduler.py::test_shutdown_proceeds_after_lock_released -x` | ✅ |
| TEST-04 | `aclose()` does not hang with cancelled in-flight requests | unit | `uv run pytest tests/test_clients.py::test_aclose_does_not_hang_with_in_flight_requests -x` | ❌ — Wave 0 (new test) |
| TEST-04 | `aclose()` raises RuntimeError when called without first cancelling in-flight requests (httpx documented behavior) | unit | `uv run pytest tests/test_clients.py::test_aclose_raises_when_requests_in_flight -x` | ❌ — Wave 0 (new test, optional behavioral assertion) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_scheduler.py tests/test_clients.py -x -q` (fast — these two files only).
- **Per wave merge:** `uv run pytest tests/ -x -q` (full suite — ~20s historically, per Phase 64 verification).
- **Phase gate:** Full suite green AND `uv run ruff check triggarr/ tests/` clean before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_scheduler.py` — needs ~7 new tests covering SAFETY-02 / SAFETY-03 / RES-01 (listed above). The existing file pattern (loguru sink + AsyncMock cycle + FastAPI app fixture) is already established.
- [ ] `tests/test_clients.py` — needs 1-2 new tests for TEST-04 (in-flight aclose pattern). The existing `_ConcreteClient + MockTransport` pattern is already established (line 21+).
- [ ] `tests/test_config.py` — needs 1 new test for the `max_consecutive_failures` default. The existing config-test pattern is well-established (Phase 64 added 7 new tests here).
- [ ] **Edit (not add):** `tests/test_scheduler.py:35-55` — `test_make_search_job_exception_swallowed` must be inverted to assert propagation. This is a behavioral change, not a deletion — keep the test infrastructure, invert the assertion.

No framework install needed — pytest + pytest-asyncio + loguru are all in `pyproject.toml [project.optional-dependencies] dev`.

## Security Domain

`security_enforcement` not explicitly disabled in `.planning/config.json` → including this section.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 65 changes nothing in auth path |
| V3 Session Management | no | No session handling change |
| V4 Access Control | no | No new endpoints, no changes to auth gates |
| V5 Input Validation | yes (minimal) | New `max_consecutive_failures` form field → existing `safe_int(form.get("max_consecutive_failures"), 5, 1, 100)` pydantic-validated path (the same primitive used for `max_history_rows` in routes.py:500) |
| V6 Cryptography | no | No new crypto |
| V7 Error Handling | yes | The new EVENT_JOB_ERROR listener logs `event.exception` — must NOT include request bodies or API keys. Use `_sanitize_exc(event.exception)` if the exception is an `httpx.HTTPError` subtype; for other types, `type(exc).__name__` + `str(exc)` is generally safe because non-httpx exceptions in our code don't carry secrets. |
| V8 Data Protection | yes | The new in-memory `app.state.search_failures` dict contains only job_id strings + int counts — no secrets. The `search_lock_holder` tuple contains a job_id string + float timestamp — no secrets. Neither is persisted. |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secrets leaking into structured logs via `exc=event.exception` | Information Disclosure | Sanitize httpx exceptions via `_sanitize_exc(exc)` (already in use at engine.py:31); never log raw `str(httpx.HTTPError)` because the exception's `request.url` may carry credentials. Verified: `_sanitize_exc` strips the URL and body, returning only `(type, status_code, error_count)`. |
| Operator-controlled `max_consecutive_failures` causes integer overflow or DoS | Tampering | `safe_int(form.get(...), 5, 1, 100)` already enforces 1 ≤ N ≤ 100 at route-handler ingress; pydantic re-validates at config load. |
| Failure counter accumulation across an attacker-induced restart loop | Availability | Counter resets on each restart by design (in-memory). An attacker who can crash Triggarr resets the counter to 0 each time, never reaching the ERROR threshold. **This is acceptable** — the operator will see Triggarr restarting in container logs (a stronger signal than the failure-counter ERROR line). |
| EVENT_JOB_ERROR listener exception crashes the scheduler | DoS | APScheduler 3.x isolates listener exceptions (verified: docs state listeners are called in a `try/except Exception` internally). Still, keep the listener body simple — just a `logger.error` call. |

## Sources

### Primary (HIGH confidence)
- `triggarr/search/scheduler.py` (full read) — `make_search_job`, `create_lifespan`, shutdown drain, search_lock initialization
- `triggarr/clients/base.py` (full read) — `ArrClient.__init__`, `close()`, `__aexit__`
- `triggarr/search/engine.py:300-405, 31-71` — narrow exception tuple usage (22 sites), `_sanitize_exc` helper
- `triggarr/web/routes.py:486-650, 596-607, 818-839` — POST /settings form handling, job_id naming, `last_search_time` precedent
- `triggarr/models/config.py:73-87` — GeneralConfig fields
- `triggarr/config.py:22-48` — DEFAULT_CONFIG template
- `triggarr/__main__.py:75-83` — single-worker uvicorn confirmation
- `pyproject.toml:17` — `apscheduler>=3.11,<4` pin
- `tests/test_scheduler.py:24-89` — existing exception-swallow test (target for inversion), graceful-shutdown tests
- `tests/test_clients.py:1-120` — `_ConcreteClient` + `MockTransport` patterns
- `tests/conftest.py:29-77` — `make_settings` factory
- `.planning/phases/64-data-safety-config-integrity/64-VERIFICATION.md` — Phase 64 lock semantics, AST-audit precedent
- `.planning/phases/64-data-safety-config-integrity/64-RESEARCH.md` — narrow exception tuple pattern history
- Local REPL: `from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent; inspect.signature(JobExecutionEvent)` — confirmed event code 8192, signature `(code, job_id, jobstore, scheduled_run_time, retval=None, exception=None, traceback=None)`

### Secondary (MEDIUM confidence)
- [APScheduler 3.x scheduler events docs](https://apscheduler.readthedocs.io/en/3.x/userguide.html#scheduler-events) — `add_listener(fn, EVENT_JOB_ERROR)` API
- [APScheduler 3.x events module reference](https://apscheduler.readthedocs.io/en/3.x/modules/events.html) — JobExecutionEvent attributes
- [APScheduler discussion #1016](https://github.com/agronholm/apscheduler/discussions/1016) — async coroutine job exceptions DO fire EVENT_JOB_ERROR (only if not caught inside the job)
- [httpx discussion #2093 — Completing Requests After AsyncClient.aclose()](https://github.com/encode/httpx/discussions/2093) — aclose raises RuntimeError on in-flight; recommended pattern is to cancel tasks first
- [httpx discussion #2138 — connection pool was closed while N requests in-flight](https://github.com/encode/httpx/discussions/2138) — confirms the RuntimeError text

### Tertiary (LOW confidence)
- None — every claim is either backed by a local code read, a local REPL verification, or an official-docs URL.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The existing `_sanitize_exc(exc)` in engine.py is safe to import from scheduler.py despite the `_` prefix | Implementation Approach §2 | If project convention forbids cross-module `_` imports, the planner can rename or re-export. Precedent for cross-module `_` import exists at scheduler.py:232 (`_sync_auth_state` from routes.py). LOW risk. |
| A2 | `httpx.MockTransport` accepts async handlers in the installed httpx version | TEST-04 / Implementation §F | Verified by reading httpx source: async handlers supported since 0.20. If wrong, fall back to a sync handler that uses `asyncio.Future` set from another task. LOW risk. |
| A3 | APScheduler's `EVENT_JOB_ERROR` fires for async (coroutine) jobs, not just sync jobs | Implementation §1 | Verified via discussion #1016 quote: "If you catch the exception inside the coroutine job, EVENT_JOB_ERROR won't fire" — implies that if you DON'T catch, it does fire. HIGH confidence. |
| A4 | Single-uvicorn-worker assumption (from Phase 64) holds for Phase 65 | RES-01 (search_lock semantics) | Verified — no change to `__main__.py` since Phase 64 ship. HIGH confidence; same comment block at scheduler.py:210-219 still applies. |
| A5 | Fresh-start semantics for the consecutive-failure counter is correct (vs. persistence) | SAFETY-03 storage decision | If a future v2.9 wants "failures across restart" the counter would need SQLite backing. v2.8 ROADMAP does not request this. The phrasing "consecutive" is itself the argument for fresh-start. HIGH confidence. |
| A6 | The phrase "after N consecutive failures... the log level escalates from WARNING to ERROR" means: failures 1..N-1 log at WARNING, failure N (and beyond, while still consecutive) logs at ERROR | SAFETY-03 escalation policy | The success criterion is "after N", which I read as "starting at the Nth failure." An alternative reading is "after the Nth failure, escalate the *next* one" — i.e., failures 1..N at WARNING, failures N+1+ at ERROR. The planner should confirm with the user in `/gsd:discuss-phase` if uncertain. **MEDIUM risk** — if interpretation B is preferred, change `>=` to `>` in one place. |
| A7 | The new `max_consecutive_failures` field defaults to 5 (matching the success criterion) | SAFETY-03 config | Locked by REQUIREMENTS.md ("default 5, configurable"). HIGH confidence. |

## Open Questions

1. **Should the failure counter also be reset when the user manually triggers a search via the "Search Now" button?**
   - What we know: `POST /api/search-now/{app}/{inst}` calls into the same cycle path, eventually hitting `make_search_job`'s wrapper logic.
   - What's unclear: Whether a manual-search success should clear the counter the same way a scheduled-job success does.
   - Recommendation: YES — the counter tracks per-job-id consecutive failures regardless of triggering source. A successful manual run should reset. The code naturally does this because the reset is inside the cycle's success branch. Document this in a comment so a future maintainer doesn't try to differentiate.

2. **Should the EVENT_JOB_ERROR listener also count toward the consecutive-failure threshold?**
   - What we know: An unexpected exception (e.g., RuntimeError) now bypasses the narrowed handler and reaches APScheduler. The narrowed handler is what increments the counter. So a RuntimeError does NOT bump the counter today under the proposed design.
   - What's unclear: Is that the right behavior? A RuntimeError is arguably a worse failure than a transient httpx error — it should probably also count.
   - Recommendation: Defer to user. The simplest design (counter only tracks expected-type failures) is what's proposed above. A more aggressive design (listener also calls `app.state.search_failures[job_id] += 1`) is one extra line. Either is defensible. The REQUIREMENTS.md phrasing "consecutive failures on a single job" is ambiguous on this point. Surface in `/gsd:discuss-phase`.

3. **Does the EVENT_JOB_ERROR listener need to log the `traceback` attribute as well as `exception`?**
   - What we know: `event.traceback` is a pre-formatted string. Logging both `exception` and `traceback` is redundant if loguru is configured with `backtrace=True` (which it is by default in Triggarr's `setup_logging`).
   - Recommendation: Just log `type(event.exception).__name__ + str(event.exception)`. If a stack trace is desired, use `logger.opt(exception=event.exception).error(...)` — but that's only useful if the operator is debugging, and for a production homelab tool, the type+message is sufficient.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `except Exception` as the catch-all in async job wrappers | Narrow tuple `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` matching the engine's per-call discrimination | Already adopted in `engine.py` (22 sites) | Phase 65 brings scheduler.py into line with engine.py |
| No APScheduler event listener (silent on unexpected job failures) | `scheduler.add_listener(fn, EVENT_JOB_ERROR)` with loguru error log | New in Phase 65 | Operator sees unexpected exception types (RuntimeError, KeyError, MemoryError) for the first time |
| Failure threshold logged identically every time | Per-job consecutive-failure counter with WARNING→ERROR escalation at N=5 | New in Phase 65 | Repeated failures become operator-visible without spamming on transient blips |
| 35s shutdown lock-drain timeout | 60s | New in Phase 65 | Longer cycles (large multi-instance setups) complete cleanly more often |
| Generic "search cycle did not finish" warning | Identifies job_id + elapsed runtime | New in Phase 65 | Operator can identify which instance is stuck without correlating against scheduler logs |

**Deprecated/outdated:** Nothing being removed. Pure additive hardening + one narrowing.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; APScheduler API verified against installed version via local REPL
- Current state of all four targets (exception block, lock drain, counter storage, client cleanup): HIGH — full read of scheduler.py, clients/base.py, models/config.py; grep-verified across codebase
- Implementation approach per criterion: HIGH — mirrors existing patterns (per-instance `app.state.*` dicts, narrow exception tuple, loguru sink-capture tests)
- Pitfall #6 (existing test must be inverted): HIGH — verified by reading tests/test_scheduler.py
- A6 (interpretation of "after N" — boundary off-by-one): MEDIUM — surface in discuss-phase if planner is uncertain
- Test strategy: HIGH for SAFETY-02/SAFETY-03/RES-01 (existing patterns), MEDIUM for TEST-04 (httpx in-flight test is a new pattern in this repo, but `MockTransport + asyncio` is well-supported)

**Research date:** 2026-05-25
**Valid until:** 2026-06-24 (30 days — stable internal hardening, no fast-moving dependencies)
