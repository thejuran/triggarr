# Phase 89: Startup & Shutdown Resource Cleanup - Research

**Researched:** 2026-11-18
**Domain:** FastAPI/Starlette lifespan resource acquisition-and-release symmetry on top of `aiosqlite` + `httpx.AsyncClient` + APScheduler, in a single-process daemon that already has ~3300 tests
**Confidence:** HIGH — every claim below is read directly from `triggarr/search/scheduler.py`, `triggarr/clients/base.py`, the installed `aiosqlite`/`apscheduler`/`starlette`/`uvicorn` source in `.venv/`, or `contextlib`'s own CPython source (not training-data recall). No new library research was needed — this phase is stdlib-only per the milestone's standing rule.

## Plan-check corrections (2026-11-18, verified against the installed source and by probes)

These corrections take precedence over any older sketch further down in this file.

1. **Per-step cap (Pattern 2, Pitfall E).** `async with asyncio.timeout(cap): await close_fn()` does NOT deliver D-09 for `aiosqlite`. `Connection.close()` (`core.py:199-214`) awaits a second future in its own `finally:` (`future = self.stop(); if future: await future`). When the timeout cancels the first await, that `finally:` keeps waiting on the blocked worker thread, so the awaiting task cannot finish and the timeout block cannot exit. Probe (blocked worker, 0.2s cap): the `asyncio.timeout` form had not returned after 1.5s; `asyncio.wait({task}, timeout=0.2)` on an owned task returned at 0.2s. Selected design: `_safe_close` runs the close in a task it owns, waits with `asyncio.wait(..., timeout=_CLEANUP_STEP_TIMEOUT)`, and for a task still pending at the cap requests cancellation once, keeps a strong reference in `_ABANDONED_CLOSE_TASKS`, and attaches a done-callback that retrieves and logs the result sanitized. `asyncio.wait` never cancels on timeout, so the WR-01 objection to `asyncio.wait_for` does not apply. Stdlib only, no forced exit (D-10). A blocked worker can be simulated in-process without an OS lock by queueing a blocking callable with `conn._execute(threading.Event().wait)`.
2. **Scheduler state (Pattern 3, Pitfall C, LIFE-03).** `BaseScheduler.start()` assigns `self.state = STATE_RUNNING` at `base.py:213` and THEN logs (214), dispatches `EVENT_SCHEDULER_STARTED` (215) and calls `self.wakeup()` (217-218). The assignment is not the last operation, so `start()` raising does not prove the scheduler is stopped, and a flag set after `start()` returns misses that case. Probe: a subclass whose `wakeup()` raises makes `start()` raise with `running == True`. Also, `AsyncIOScheduler.shutdown()` (`asyncio.py:40-50`) only queues the real shutdown with `call_soon_threadsafe`: `running` is still True when `shutdown()` returns and False after one loop iteration. Selected design: failed-startup cleanup reads `scheduler.running`, calls shutdown only when it is True, yields one loop iteration, and re-reads `scheduler.running` before reporting the scheduler stopped. No `scheduler_started` flag.
3. **TEST-04 (Pitfall B).** `tests/test_clients.py:190-203` records that `close()` returns cleanly within milliseconds and that the `AssertionError` is raised on the in-flight request task, not by `close()`. TEST-04 therefore does not prove that `close()` raises `AssertionError`. The broad `Exception` catch stays because D-07 locks it and because failures around an in-flight close are demonstrably not httpx-typed; the synthetic "close raises AssertionError" tests prove only that the catch is broad and that later steps continue.
4. **D-05 chronology.** The cause must be the first failed-startup log line. The cleanup branch logs a sanitized cause line (`_sanitize_exc`, never `str(exc)`) before any cleanup step, then cleanup warnings, then exactly one summary line, then a bare `raise`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** No new runtime dependency (stdlib only, e.g. `contextlib.AsyncExitStack`, `asyncio.timeout`). Each fix lands with a regression test that fails on the unfixed code.
- **D-02:** (Phase 87 D-16 pattern) When one cleanup step fails, every remaining cleanup step still runs, and each failure is logged with secrets redacted by the existing loguru sink.
- **D-03:** The original startup error is re-raised unchanged. Startup still fails loudly; only the leak is fixed (research PITFALLS.md Pitfall 6 warning signs). The fix must cover every setup step after the database opens, not only `init_db`/`run_migrations`.
- **D-04:** The existing shutdown order stays: stop the scheduler, drain the search lock (existing `shutdown_drain_timeout` behavior unchanged), close clients, close the database, log "Search engine stopped".
- **D-05 (failed-startup log):** The original startup error stays first and unchanged in the log. After cleanup, one summary line states that startup failed and what was closed (for example "Startup failed; closed the database and 3 connections before exiting"). No per-step success lines.
- **D-06 (failed-startup log):** A cleanup step that itself fails during a failed startup is logged at warning level naming what failed (redacted reason). The original startup error stays the reported cause and is the exception that propagates.
- **D-07 (shutdown close failure):** A client that fails to close at shutdown gets one warning-level line naming the app, the instance and the reason (exception type plus redacted message; never a URL with credentials or an API key), then shutdown continues. Example shape: "Shutdown: could not close Sonarr/'anime' connection (AssertionError); continuing." The catch is broad (`Exception`), because the in-flight-close failure is not guaranteed to be an `httpx` type (TEST-04 finding, research Pitfall 7).
- **D-08 (shutdown close failure):** No new summary line at the end of shutdown; the existing "Search engine stopped" ending stays.
- **D-09 (hung cleanup cap):** Each close step (each client, the database, during failed startup and shutdown) is bounded by a short fixed limit of about 5 seconds: a module constant, not a new config setting. A step that overruns is logged as a warning naming the step, and cleanup moves on to the next step.
- **D-10 (hung cleanup cap):** No forced process exit. The fix is to close resources properly; Triggarr does not add an `os._exit`-style guard that would hide future leaks.
- **D-11 (how it's proven):** In-process tests in this phase only (pattern: `async with lifespan_fn(app)` as in `tests/test_scheduler.py`). For each failure stage (database upgrade, cutover, client construction, job scheduling/scheduler start), assert that the original error propagates, the database is actually closed, every client constructed so far is closed, and the scheduler is not running. A shutdown test makes one client's close raise and asserts the later clients and the database still close and a warning is logged. The built-image demonstration is Phase 92 (SMOKE), which already exercises repeated failed upgrades.
- **D-12 (how it's proven):** The failed-startup test also asserts that the aiosqlite background worker thread has stopped (no leftover non-daemon thread from the connection), not only that `close()` was called on a mock. That thread is the actual cause of the container hang (research Pitfall 6).

### Claude's Discretion

- Mechanism: `AsyncExitStack` around acquisition and release (research STACK.md, Capability 2, recommends it for both halves) or explicit tracked try/except, as long as D-02 to D-10 hold.
- Exact value of the per-step cap (about 5s) and its constant name; how a timed-out database close interacts with D-12 (if the cap fires on a db close, the worker thread may remain; the planner decides how this is logged and tested).
- Exact wording of the D-05, D-06 and D-07 log lines within the redaction rules.
- Whether the scheduler is shut down via the same unwind (it is only started near the end of setup; LIFE-03 requires it is not left running).
- Test fixtures and how setup steps are made to fail (patching `init_db`, `ensure_cutover_recorded`, a client class, `scheduler.start`).

### Deferred Ideas (OUT OF SCOPE)

None new. Phase 87's cancellation and close deferrals (`_close_removed_client` self-cancel, settings-route cancellation safety, startup set-aside copy blocking the loop) stay in `.planning/backlog/MAINTENANCE.md` and are not folded in. Built-image proof belongs to Phase 92.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LIFE-01 | When startup fails partway, Triggarr closes the database and every connection it had already opened, and the process exits promptly rather than hanging. | Starlette 1.10.0's `Router.lifespan` + uvicorn 0.54.0's `LifespanOn.main()` traced line-by-line below: confirms a pre-`yield` exception never reaches the generator's own `finally:`, and confirms uvicorn does **not** re-raise the failure — it only sets `should_exit=True` and returns. "Process exits promptly" is therefore only actually proven by verifying the aiosqlite worker thread (non-daemon) has stopped, not by verifying the exception propagated (it already does today). See "Why `db.close()` must actually run" and Pitfall A below. |
| LIFE-02 | When one *arr connection fails to close at shutdown, the remaining connections and the database are still closed, and the failure is logged sanitized. | Current shutdown loop (`scheduler.py:747-753`) has zero exception handling; confirmed from installed `httpx`/`aiosqlite` source that both `client.close()` and `db.close()` can raise. `_sanitize_exc` (already imported into `scheduler.py`) is the exact existing function that produces the D-07 wording's `(AssertionError)` shape with zero new code. See "Code Examples" and Pitfall B. |
| LIFE-03 | After a failed startup, the scheduler is not left running. | CORRECTED: `BaseScheduler.start()` sets `self.state = STATE_RUNNING` at `base.py:213`, after executors/jobstores/pending jobs succeed but BEFORE its logging, start-event dispatch and `wakeup()` (214-218). A scheduler that never reached `start()` is `STATE_STOPPED` and `shutdown()` on it raises `SchedulerNotRunningError`; a scheduler whose `start()` raised may be either stopped or already running. Cleanup therefore decides from the scheduler's actual state (`scheduler.running`), not from a flag set after `start()` returns, and confirms the state after the queued shutdown has run. See Pitfall C and the Plan-check corrections. |

</phase_requirements>

## Summary

`create_lifespan`'s `lifespan` generator (`triggarr/search/scheduler.py:479-757`) has no exception handling anywhere in its setup section (lines 496-667): it opens the `aiosqlite` connection, runs migrations, records the attribution cutover, constructs one `httpx.AsyncClient`-backed `ArrClient` per enabled instance, populates `app.state`, schedules every search job, and starts APScheduler — all before the `try: yield / finally:` block that holds 100% of today's cleanup code. Because `@asynccontextmanager` generators only run their `finally:` after `yield` is reached, any exception raised during that whole setup section propagates straight out of the context manager, bypassing the existing cleanup entirely. This is `AsyncExitStack`'s/`Router.lifespan`'s textbook unprotected-acquisition shape, confirmed directly against the installed Starlette 1.10.0 and uvicorn 0.54.0 source: Starlette reports the failure as `lifespan.startup.failed` and re-raises inside its own `main()` task, and uvicorn's `LifespanOn.main()` catches that `BaseException`, logs it, and **returns without re-raising** — `server.serve()` then returns normally. Nothing forces the process to exit; what actually determines whether the process exits promptly is whether any non-daemon OS thread is still alive, and `aiosqlite.Connection` (0.22.1, confirmed from installed source) starts an un-flagged (non-daemon) `threading.Thread` the moment it's awaited. If `db.close()` is never called, that thread blocks forever on its internal queue and the interpreter will not exit — this is the literal, verified mechanism behind "the container hangs," and it means the regression test for LIFE-01 must assert the worker thread actually stopped, not merely that the exception still propagates (it already does, today, with no fix at all).

The shutdown half (`scheduler.py:747-753`) has the mirror-image gap: a bare double `for` loop over every client's `close()` with no `try/except`, followed by an unguarded `await app.state.db.close()`. Both `httpx.AsyncClient.aclose()` and `aiosqlite.Connection.close()` are confirmed (from installed source) to be able to raise — and TEST-04 shows that failures around an in-flight close are not httpx-typed (CORRECTED: in TEST-04 `close()` itself returns cleanly and the `AssertionError` is raised on the in-flight request task, so TEST-04 does not prove that `close()` raises it), so a fix that narrows its `except` clause to `httpx.HTTPError` has no basis for assuming every close failure is httpx-typed; D-07 locks the broad catch. One client failing to close currently aborts every subsequent client's close *and* the database close, reproducing the same thread-hang mechanism as the startup gap.

A third, less obvious but verified-critical finding: `contextlib.AsyncExitStack` (the mechanism STACK.md recommends) does not simply "run every callback no matter what" in the way that sentence suggests — if a callback it manages raises, `AsyncExitStack.__aexit__` **replaces** the exception that will propagate with the callback's new exception (chaining the old one only via `__context__`, the "during handling of the above exception" footnote), confirmed by reading CPython's actual unwind loop. Used naively (`stack.push_async_callback(client.close)`), a single failing `client.close()` during a failed-startup unwind would make *that* close error — not the original migration/cutover/construction error — the one that propagates, directly violating D-03/D-05/D-06. The fix is mechanical and small: every callback registered with the exit stack (or, equivalently, every step in an explicit tracked loop) must swallow and log its own exception internally and never raise past its own boundary; `AsyncExitStack`'s acquisition-order bookkeeping is still useful, its default exception-propagation behavior is not what this phase wants.

**Primary recommendation (CORRECTED in two places by the Plan-check corrections above: the scheduler is guarded by its actual `scheduler.running` state rather than a `started` flag, and each step's cap is a bounded `asyncio.wait` on an owned task rather than `asyncio.timeout` around a direct await):** Track every opened resource (the `db` connection, and a single flat list of constructed `ArrClient` instances, and a `started: bool` flag for the scheduler) as plain local variables while setup proceeds, wrap the whole setup section in one `try/except Exception`, and on failure call one shared helper — `async def _safe_close(label: str, close_fn) -> bool` — for the scheduler (only if `started`), then every constructed client, then the db, each under its own `asyncio.timeout(_CLEANUP_STEP_TIMEOUT)`, logging a warning per step that fails or times out and one summary line at the end, then re-raising the original exception completely untouched (store it in a local variable before starting cleanup; never re-derive it from `sys.exc_info()` after a cleanup step's own except block has run, since that could silently rebind `exc`). Reuse this exact same `_safe_close` helper inside the existing shutdown `finally:` block's client-close loop and db-close call, so startup-failure cleanup and shutdown cleanup share one tested code path instead of two. `AsyncExitStack` may be used purely as a bookkeeping container for this (it is not required), but only if every pushed callback is itself one of these self-contained, non-raising wrappers — never a raw `client.close`/`db.close` reference.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Startup resource acquisition (db connect, migrations, cutover, client construction, job scheduling, scheduler start) | API/Backend (process lifecycle) | Database/Storage (aiosqlite connection + its worker thread) | `create_lifespan` is FastAPI/Starlette application-lifecycle code, not a route handler; the resource being protected (the `aiosqlite.Connection`'s background thread) is itself a storage-tier object whose lifecycle rules (non-daemon thread) are what make this an availability bug, not just tidiness |
| Failed-startup cleanup (close what was opened, re-raise original error) | API/Backend | Database/Storage, External client (httpx) | The cleanup loop spans three resource kinds owned by three different modules (`aiosqlite`, `httpx.AsyncClient` via `ArrClient`, `APScheduler`) but is orchestrated entirely inside the lifespan function — no browser/CDN tier involvement |
| Shutdown resource release (client close loop, db close) | API/Backend | External client (httpx), Database/Storage | Same orchestration point as above; this is the existing `finally:` block, already correctly scoped to the backend tier |
| Scheduler shutdown guard (don't call `shutdown()` on a never-started scheduler) | API/Backend | — | Pure in-process state-machine concern (APScheduler's own `STATE_STOPPED`/`STATE_RUNNING`); no other tier is involved |
| Logging of cleanup failures (sanitized) | API/Backend (cross-cutting) | — | Routes through the existing loguru redacting sink already wired at the process level; not a per-tier concern |

This phase has no browser/client, SSR, or CDN component — it is entirely backend process-lifecycle code. The table above is included for completeness per the planner's tier-sanity-check convention; there is no misassignment risk here since every capability already lives in exactly one file (`triggarr/search/scheduler.py`) in exactly one tier.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| Python stdlib `contextlib` (`AsyncExitStack`, optionally) | 3.11+ (stdlib) | Optional bookkeeping container for "acquire N things, release what's been acquired so far on failure" | Purpose-built for exactly this shape per its own docstring; already a documented pattern in STACK.md Capability 2a. **Caveat verified this session: its default per-callback exception handling is unsafe for this phase's requirements — see Pitfall D below before using it.** |
| Python stdlib `asyncio` (`asyncio.timeout`) | 3.11+ (stdlib) | Per-step cleanup cap (D-09) | Already the project's chosen idiom for exactly this kind of bounded-wait-during-shutdown (`scheduler.py:715`, with an explicit in-code comment on why `asyncio.timeout` is preferred over `asyncio.wait_for` for cancellation safety — the same reasoning applies here) |
| `aiosqlite` | 0.22.1 (pinned, `uv.lock`) | The db connection being protected | No version change needed; its `Connection.close()` behavior (re-raises, and unconditionally calls `self.stop()` in its own `finally:`) is verified directly from the installed source — see "Code Examples" |
| `httpx` | 0.28.1 (pinned, `uv.lock`) | The client connections being protected | No version change needed; `AsyncClient.aclose()` can raise, confirmed from installed source (TEST-04 is not evidence for this: there `close()` returns cleanly and the failure is on the in-flight request task) |
| `apscheduler` | 3.11.3 (pinned, `uv.lock`) | The scheduler being protected / guarded | No version change needed; `BaseScheduler.start()`/`.shutdown()` state-machine behavior verified directly from installed source |

No new dependency, no version bump. This matches the milestone's standing rule exactly.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `loguru` | (pinned, existing) | Warning/summary log lines for D-05/D-06/D-07 | Already in use throughout `scheduler.py`; new log lines follow the same keyword-argument brace-style convention already used (e.g. the shutdown-drain logs at lines 690-738) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Plain tracked local variables + one shared `_safe_close` helper | `contextlib.AsyncExitStack` with `push_async_callback` | `AsyncExitStack` adds LIFO-unwind bookkeeping "for free," but only if every pushed callback is itself exception-swallowing (see Pitfall D) — once that wrapping is added, the stack's main remaining benefit over a plain list is marginal. Either is acceptable per CONTEXT.md's Claude's Discretion; this research recommends the plain-list approach for its lower risk of someone later pushing a raw, raising callback and silently reintroducing D-03's bug. |
| Per-step `asyncio.timeout()` | `asyncio.wait_for()` | The codebase has already rejected `wait_for` for exactly this shutdown-adjacent use (WR-01 comment, `scheduler.py:701-711`): `wait_for`'s cancellation can race and leave state half-committed. The same reasoning transfers unchanged to the new per-step cap — use `asyncio.timeout()` everywhere in this phase, no exceptions. |
| Reading the scheduler's actual state (`scheduler.running`, i.e. `state != STATE_STOPPED`) | A local `started: bool` flag set only after `scheduler.start()` returns | CORRECTED: the flag is NOT equivalent. `self.state = STATE_RUNNING` is assigned at `base.py:213`, before `start()`'s logging, start-event dispatch and `wakeup()` (214-218), so `start()` can raise with the scheduler already running and the flag still False. Read `scheduler.running` (a public property, no import from apscheduler internals needed) and re-read it one loop iteration after requesting shutdown. |

**Installation:** none — no new packages.

**Version verification:** confirmed directly from `uv.lock` (not training data): `aiosqlite==0.22.1`, `httpx==0.28.1`, `apscheduler==3.11.3`, `starlette==1.10.0`, `fastapi==0.162.4`, `uvicorn==0.54.0`. All behavioral claims below were re-verified against the exact installed `.venv/` source for these versions during this research session, not assumed from STACK.md's prior pass (though they agree with it).

## Package Legitimacy Audit

Not applicable. This phase installs no new runtime or dev dependency (D-01, milestone standing rule). No `pip`/`npm`/`cargo` install commands are part of this phase's plan.

## Architecture Patterns

### System Architecture Diagram

```
                    create_lifespan(settings, state_path, config_path)
                                      |
                                      v
                     ACQUISITION (currently unprotected)
          +---------------------------------------------------------+
          |  1. aiosqlite.connect(db_path)  -------> db             |
          |     (starts a non-daemon worker thread on first await)  |
          |  2. init_db / run_migrations(db)                        |
          |  3. migrate_from_state (one-time, conditional)           |
          |  4. ensure_cutover_recorded(db, ...)  <- deliberately    |
          |     uncaught today; must stay fatal, just not leaky     |
          |  5. for app_type in (radarr, sonarr, lidarr):            |
          |       for instance in enabled:                          |
          |         ArrClient(...)  -------> append to flat list     |
          |  6. populate app.state.* (settings, db, clients, locks) |
          |  7. for app_type / instance: scheduler.add_job(...)      |
          |     (jobs queue as "pending" -- scheduler not running)   |
          |  8. scheduler.start()  -------> started = True on success|
          |  9. scheduler.add_job(update_check_job, ...)             |
          +---------------------------------------------------------+
                     |  exception at ANY step 1-9
                     v
          +---------------------------------------------------------+
          |  NEW: except Exception as startup_exc:                  |
          |    closed = 0                                            |
          |    if started: _safe_close("scheduler", scheduler.shutdown)|
          |    for client in created_clients (reverse order):        |
          |        if await _safe_close(label, client.close): closed+=1|
          |    if db is not None:                                    |
          |        if await _safe_close("database", db.close): closed+=1|
          |    logger.error("Startup failed; closed the database    |
          |                  and {closed} connection(s) before       |
          |                  exiting")                               |
          |    raise startup_exc   # D-03: unchanged, unreplaced      |
          +---------------------------------------------------------+
                     |  no exception (normal path)
                     v
                   yield  ---->  app serves requests  ---->  shutdown signal
                     |
                     v
          +---------------------------------------------------------+
          |  EXISTING finally: (unchanged order per D-04)            |
          |   1. scheduler.shutdown(wait=False)                      |
          |   2. drain search_lock (asyncio.timeout, unchanged)      |
          |   3. for client in all clients:                          |
          |        await _safe_close(label, client.close)  <- NEW:   |
          |          per-client try/except+timeout, continues on fail|
          |   4. await _safe_close("database", db.close)   <- NEW    |
          |   5. logger.info("Search engine stopped")                |
          +---------------------------------------------------------+
```

A reader can trace both the failure path (left branch, new) and the existing happy/shutdown path (right branch, unchanged in sequence, only hardened per-step) from this single diagram. The key structural change is that acquisition becomes trackable (a flat client list + a `started` flag + the `db` reference, all as plain locals) and both cleanup paths call into one shared `_safe_close` primitive instead of each loop having its own ad hoc (or absent) error handling.

### Recommended Project Structure

No new files or directories. All changes are inside `triggarr/search/scheduler.py`:

```
triggarr/search/scheduler.py
├── _read_shutdown_drain_timeout()      # existing, unchanged
├── _SHUTDOWN_DRAIN_TIMEOUT             # existing, unchanged
├── _CLEANUP_STEP_TIMEOUT: float = 5.0  # NEW module constant (D-09; exact name/value at planner's discretion)
├── _safe_close(label, close_fn) -> bool  # NEW shared helper (D-02/D-06/D-07/D-09)
└── create_lifespan()
    └── lifespan()
        ├── [setup section] now wrapped in try/except Exception  # NEW
        └── try: yield / finally: [shutdown section]             # existing, client/db loops hardened
```

### Pattern 1: Track resources as plain locals during acquisition, not on `app.state`

**What:** Maintain `db: aiosqlite.Connection | None = None`, `created_clients: list[tuple[str, str, ArrClient]] = []` (app_type, instance_name, client — enough for the D-07 "Sonarr/'anime'" wording), and `scheduler_started = False` as ordinary local variables inside the `lifespan` generator, updated immediately after each successful acquisition step.

**When to use:** Any time a failure-handling block needs "everything acquired so far," because `app.state.db`/`app.state.{app_type}_clients` are not actually assigned until line 549-553 — well after `db` is opened (496), migrations run (509), and the cutover is recorded (526). A failure in any of those early steps means `app.state.db` does not exist yet; reading it from an except block would raise `AttributeError` and mask the original error. Plain locals captured in the enclosing closure are available from the very first line they're assigned, regardless of whether `app.state` has been populated.

**Example:**
```python
# Source: derived from the existing triggarr/search/scheduler.py structure
# (lines 496, 534-544) plus Starlette's own `started` flag pattern,
# confirmed in .venv/.../starlette/routing.py:652-677
db: aiosqlite.Connection | None = None
created_clients: list[tuple[str, str, ArrClient]] = []
scheduler_started = False

try:
    db = await aiosqlite.connect(db_path)
    ...
    for app_type in APP_TYPES:
        cls = client_classes[app_type]
        for inst_name, cfg in settings.get_enabled_instances(app_type).items():
            client = cls(base_url=cfg.url, api_key=cfg.api_key, ...)
            created_clients.append((app_type, inst_name, client))
    ...
    scheduler.start()
    scheduler_started = True
    ...
except Exception as startup_exc:
    ...  # cleanup using db / created_clients / scheduler_started
    raise startup_exc
```

### Pattern 2: One shared, non-raising, timeout-capped close helper for both cleanup paths

**CORRECTED (see Plan-check corrections 1):** the `async with asyncio.timeout(...)` body in the example below is superseded. The helper runs `close_fn()` in an owned task and bounds its own wait with `asyncio.wait({task}, timeout=_CLEANUP_STEP_TIMEOUT)`; a task still pending at the cap is cancelled once, kept in `_ABANDONED_CLOSE_TASKS`, and observed by a done-callback. The signature also gained a leading `context` argument. The contract (never raises, one sanitized WARNING, returns success) is unchanged.

**What:** A single `async def _safe_close(label: str, close_fn: Callable[[], Awaitable[None]]) -> bool` that attempts `close_fn()` under `asyncio.timeout(_CLEANUP_STEP_TIMEOUT)`, logs a warning naming `label` and the sanitized reason on either a raised exception or a `TimeoutError`, and **always returns normally** (never raises) — returning `True`/`False` for "did this step actually succeed" so callers can count successes for the D-05 summary line.

**When to use:** Every single resource-close call in this phase — the scheduler shutdown, every client close, the db close — on both the failed-startup path and the existing shutdown `finally:` path. This is the one piece of new logic; everything else is wiring it in at the right points.

**Example:**
```python
# Source: derived from the existing _SHUTDOWN_DRAIN_TIMEOUT / asyncio.timeout()
# idiom already in triggarr/search/scheduler.py (lines 701-716), and from
# triggarr.search.engine._sanitize_exc (re-exported, already imported here
# as `_sanitize_exc` at scheduler.py:48-49) — confirmed its fallback branch
# (`return type(exc).__name__`) already produces exactly the D-07 example's
# "(AssertionError)" shape with no new sanitization code needed.
_CLEANUP_STEP_TIMEOUT: float = 5.0  # D-09; a module constant, not config


async def _safe_close(label: str, close_fn: Callable[[], Awaitable[None]]) -> bool:
    """Attempt one cleanup step; log and continue, never raise. Returns success."""
    try:
        async with asyncio.timeout(_CLEANUP_STEP_TIMEOUT):
            await close_fn()
        return True
    except Exception as exc:
        logger.warning(
            "Cleanup: {label} did not close cleanly ({exc})",
            label=label,
            exc=_sanitize_exc(exc),
        )
        return False
    except TimeoutError:
        logger.warning(
            "Cleanup: {label} did not close within {t}s; continuing",
            label=label,
            t=_CLEANUP_STEP_TIMEOUT,
        )
        return False
```
Note: in Python 3.11+, `asyncio.TimeoutError` **is** `TimeoutError`, and `TimeoutError` **is** a subclass of `OSError`, which **is** a subclass of `Exception` — so the bare `except Exception` above already catches the timeout case; the second `except TimeoutError` clause is redundant as written and shown here only to make the distinct log wording explicit. Either collapse to one `except Exception` branch with an `isinstance(exc, TimeoutError)` check inside for wording, or keep two clauses with `TimeoutError` first — do not rely on exception-type ordering being "more specific first" being required here, since both branches currently produce the same control flow (log + return False).

### Pattern 3: Guard scheduler shutdown with a tracked `started` flag, not a bare call

**CORRECTED (see Plan-check corrections 2):** guard on the scheduler's actual state (`scheduler.running`), not on a flag set after `start()` returns; `start()` can raise after setting `STATE_RUNNING`. After requesting shutdown, yield one loop iteration and re-read `scheduler.running`, because `AsyncIOScheduler.shutdown()` only queues the real shutdown. The flag-based text and example below are superseded; the "never call shutdown() on a scheduler that is not running" rule stands.

**What:** Never call `scheduler.shutdown()` (anywhere — failed-startup cleanup or the existing `finally:`) without first checking that `scheduler.start()` actually completed. The existing `finally:` block's `scheduler.shutdown(wait=False)` (line 673) is currently safe *only* because, on every path that reaches `yield`, `scheduler.start()` has already succeeded by construction — but a failed-startup cleanup path that runs *before* `yield` has no such guarantee, since the whole point is that setup may have failed before or at `scheduler.start()` itself.

**When to use:** In the new failed-startup except block, before calling `_safe_close("scheduler", lambda: asyncio.to_thread(scheduler.shutdown, wait=False))` — wait, `scheduler.shutdown()` is itself synchronous (confirmed from installed `BaseScheduler.shutdown()` source: no `async def`, no awaits inside) so it should be called directly, not wrapped in `asyncio.timeout` the same way as the async closes (a sync call inside `asyncio.timeout` doesn't yield control and can't actually be "timed out" mid-call — `_safe_close`'s timeout wrapping is only meaningful for genuinely async `close_fn`s). Guard it with the `started` flag and call it as a plain synchronous step, in its own try/except for logging consistency, but without the `asyncio.timeout` wrapper that doesn't apply to it.

**Example:**
```python
# Source: confirmed from .venv/.../apscheduler/schedulers/base.py:176-215 and
# :221-245 — CORRECTED: self.state is set to STATE_RUNNING at line 213, BEFORE
# start()'s logging, event dispatch and wakeup() (so start() can raise while
# running; guard on scheduler.running, not a flag). Superseded comment: only on the LAST line of a
# successful start(), and shutdown() raises SchedulerNotRunningError whenever
# self.state == STATE_STOPPED (its very first check).
if scheduler_started:
    try:
        scheduler.shutdown(wait=False)
    except Exception as exc:  # defensive; APScheduler's own shutdown() can itself raise
        logger.warning("Cleanup: scheduler shutdown failed ({exc})", exc=_sanitize_exc(exc))
# else: scheduler was never started -- LIFE-03 already holds trivially, and
# calling shutdown() here would raise SchedulerNotRunningError and, if not
# itself caught, would replace the original startup_exc (see Pitfall D).
```

### Anti-Patterns to Avoid

- **Pushing raw `client.close`/`db.close`/`scheduler.shutdown` references into an `AsyncExitStack` via `push_async_callback`:** the stack's unwind loop (confirmed from CPython's `contextlib.AsyncExitStack.__aexit__` source) replaces the propagating exception with any callback's own exception, breaking D-03/D-05/D-06 the moment one cleanup step itself fails during a failed-startup unwind. See Pitfall D below.
- **Calling `scheduler.shutdown()` unconditionally in the failed-startup cleanup path:** raises `SchedulerNotRunningError` whenever setup failed before or during `scheduler.start()` — the common case this phase targets (migration/cutover/client-construction failures all happen *before* `scheduler.start()` is ever reached) — and that new exception would itself need to not replace `startup_exc`. See Pitfall C.
- **Using `asyncio.wait_for()` for the per-step cap:** already rejected in this exact file (WR-01 comment) for a documented cancellation race; use `asyncio.timeout()` for consistency and correctness.
- **Reaching for `asyncio.TaskGroup`/`asyncio.gather` to "parallelize" the client-close loop:** out of scope per CONTEXT.md and STACK.md Pitfall 8 — `TaskGroup` raises `ExceptionGroup`, which nothing else in this codebase's narrow-tuple `except (httpx.HTTPError, ...)` style knows how to unwrap, and its default sibling-cancellation-on-first-failure behavior is the opposite of "every client gets a chance to close independently." Sequential closes of 1-15 clients have no measurable performance cost.
- **Classifying retry/close-safety decisions on the *sanitized* string instead of the live exception object:** not directly applicable to this phase (no retry logic here), but the same principle applies to the `started`/`scheduler_started` flag check — decide branch logic on the real boolean/state, sanitize only at the log call site.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| "Release everything acquired so far if a later acquisition fails" | A custom stack/registry class | `contextlib.AsyncExitStack` (optional, as pure bookkeeping) or a plain `list` of `(label, close_fn)` tuples | Stdlib already provides the registry; the only non-trivial part this phase actually needs to build is the non-raising wrapper around each callback (Pattern 2), which `AsyncExitStack` does not provide for you |
| Bounding how long a single cleanup step can block | A manual `threading`-based watchdog or `signal.alarm` | `asyncio.timeout()` (stdlib, already the project's idiom at `scheduler.py:715`) | Already proven correct and cancellation-safe in this exact file for a structurally identical problem (the shutdown lock drain) |
| Verifying a background thread actually stopped | Polling a custom "is it done" flag on the connection object | `aiosqlite.Connection._thread.is_alive()` after `Thread.join(timeout=...)` | `aiosqlite.Connection` already exposes `self._thread` (a stdlib `threading.Thread`); `Thread.join()` + `.is_alive()` is the standard, already-correct way to prove a thread has terminated — no new abstraction needed |
| Sanitizing a close-failure exception for logging | A new sanitize function scoped to this phase | `triggarr.clients.base._sanitize_exc` (already imported into `scheduler.py` via `triggarr.search.engine`) | Verified this session: its unconditional fallback branch (`return type(exc).__name__`) already produces exactly the `(AssertionError)` shape the D-07 example wording specifies, for any exception type it doesn't specifically recognize (httpx/pydantic) — zero new sanitization logic required |

**Key insight:** every primitive this phase needs — bounded registries, timeouts, thread-liveness checks, exception sanitization — already exists in the stdlib or in this exact codebase. The actual work is wiring (tracking resources as locals instead of on `app.state`, guarding the scheduler's shutdown call with a flag) and one small shared helper (`_safe_close`), not new infrastructure.

## Common Pitfalls

### Pitfall A: "The exception still propagates" is not evidence the fix works — it already propagates today

**What goes wrong:** A test that patches `init_db` to raise and asserts `pytest.raises(SomeError)` around `async with lifespan_fn(app): ...` will pass against both the current, broken code and a correctly fixed version — because the exception already propagates unprotected today (Pitfall 6's whole point is that nothing *catches* it, so of course it isn't swallowed). This kind of test proves nothing about LIFE-01.

**Why it happens:** It's the most obvious assertion to write, and it genuinely is a necessary (D-03) condition — just not a sufficient one.

**How to avoid:** Every failed-startup test must additionally assert the *positive* cleanup claims: (1) `db.close()` was actually awaited to completion — verified by checking the underlying `aiosqlite.Connection`'s worker thread stopped (`conn._thread.join(timeout=2); assert not conn._thread.is_alive()`), not just that a mock's `.close` was called; (2) every client constructed before the failure point has had `.close()` called (spy/mock each constructed client, or construct real `ArrClient`s against a mock transport and check `._client.is_closed`); (3) the scheduler is not in a running state (`scheduler.state != STATE_RUNNING` or the stand-in fake's own `started`/`shutdown_wait` flags, per the existing `_FakeScheduler` test double at `tests/test_scheduler.py:1946-1965`).

**Warning signs:** A new test with `pytest.raises(...)` and no other assertion inside the `with` block or after it.

**Test that catches it:** D-11/D-12 already specify this exact bar; see "Validation Architecture" below for concrete commands.

### Pitfall B: Narrowing the shutdown close loop's `except` clause to `httpx.HTTPError`

**What goes wrong:** CORRECTED: TEST-04 (`tests/test_clients.py:171-389`, already in the repo) empirically shows that calling `aclose()` on an `httpx.AsyncClient` with a request still in flight, without first cancelling that request, makes the IN-FLIGHT REQUEST TASK fail with `AssertionError` from inside `httpx/_transports/asgi.py`, while `close()` itself returns cleanly within milliseconds (`tests/test_clients.py:190-203`). It does not show `close()` raising. What it does establish is that failures around an in-flight close are not `httpx.HTTPError` subclasses, so there is no basis for assuming a failing `close()` is httpx-typed. A fix that writes `except httpx.HTTPError:` around each `client.close()` call would let any non-httpx failure from `close()` (transport, OS-level, or an assertion inside httpx) escape uncaught, reproducing the exact bug (one client's close failure aborting the rest).

**Why it happens:** `httpx.HTTPError` "feels" like the right scope for "an httpx client operation failed," and most of the time it would be — but failures around `close()` are documented by the project's own TEST-04 comment block (where the error lands on the in-flight request task, not on `close()`) as *not* guaranteed to be an httpx-shaped exception.

**How to avoid:** Catch broad `Exception` in `_safe_close` (per D-07's explicit instruction and Pattern 2 above). D-07 locks this — don't re-narrow it.

**Test that catches it:** A shutdown test with 2-3 registered clients where the first's `close()` is mocked to raise `AssertionError` (not an httpx exception) — the test from D-11 ("A shutdown test makes one client's close raise") should use a non-httpx exception class specifically, to prove the catch is actually broad, not accidentally narrow in a way the happy-path test wouldn't reveal. This synthetic test proves the breadth of the catch and the continuation of later steps only; it is not a reproduction of TEST-04.

### Pitfall C: Calling `scheduler.shutdown()` on a scheduler that never started raises `SchedulerNotRunningError` and can mask the real startup error

**What goes wrong:** Verified directly from the installed `apscheduler` 3.11.3 source (`schedulers/base.py:221-233`): `BaseScheduler.shutdown()`'s very first line is `if self.state == STATE_STOPPED: raise SchedulerNotRunningError`. A fresh `AsyncIOScheduler()` starts in `STATE_STOPPED` (`__init__`, line 124) and transitions to `STATE_RUNNING` at line 213 of `start()`. CORRECTED: line 213 is not the last operation; `start()` then logs (214), dispatches its start event (215) and calls `wakeup()` (217-218). If `scheduler.start()` is never reached (e.g. a migration failure happens first) or raises before line 213, the scheduler is still `STATE_STOPPED`; if it raises at 214-218 the scheduler is already running and must be stopped. If the new failed-startup cleanup code calls `scheduler.shutdown()` unconditionally (reasoning "LIFE-03 says shut it down on failure"), it will raise `SchedulerNotRunningError` on the much more common case where the scheduler was never running in the first place — and if that new exception isn't itself caught, it replaces `startup_exc` (see Pitfall D), corrupting exactly the error the operator needs to see.

**Why it happens:** LIFE-03's wording ("the scheduler is not left running") reads as an instruction to actively shut it down, but in the majority of failure stages (migration, cutover, client construction, pre-start job scheduling — everything that happens before line 652's `scheduler.start()`), the scheduler was simply never started, so the requirement already holds with zero action needed; "shut it down" is only the correct action for the one stage where `scheduler.start()` itself raises partway through, or a later step (the `update_check_job` `add_job()` call, which *does* run after `start()`) fails.

**How to avoid:** CORRECTED: gate the cleanup's `scheduler.shutdown()` call on the scheduler's actual state (`scheduler.running`, i.e. `state != STATE_STOPPED`), not on a flag set after `scheduler.start()` returns, then yield one loop iteration and re-read the state (the real shutdown is queued on the loop). This also directly answers the CONTEXT.md discretion item ("whether the scheduler is shut down via the same unwind") — yes, but only when the scheduler is running; otherwise LIFE-03 already holds and no call is made (or needed).

**Test that catches it:** D-11's failure-stage matrix must include at least one stage *before* `scheduler.start()` (e.g. `init_db` or client construction raising) and assert cleanup does **not** raise `SchedulerNotRunningError` itself and that `startup_exc` — the original injected error — is what actually propagates; and one stage *at or after* `scheduler.start()` (patch the `update_check_job`'s `scheduler.add_job` call, or `scheduler.start()` itself via the `AsyncIOScheduler` mock already used elsewhere in this file, to raise after a successful `start()`) asserting `scheduler.shutdown()` **was** called in that case; plus (CORRECTED) one stage with a REAL `AsyncIOScheduler` whose `start()` raises after the running-state transition (subclass overriding `wakeup()` to raise), asserting the scheduler's state is `STATE_STOPPED` after cleanup — a fake's shutdown flag proves only that a stop was requested.

### Pitfall D: `AsyncExitStack`'s callback-exception replacement silently breaks D-03/D-05/D-06

**What goes wrong:** Confirmed by reading CPython's `contextlib._BaseExitStack`/`AsyncExitStack.__aexit__` source directly this session: when unwinding, if a registered callback raises, the stack does `exc = new_exc` (replacing the exception that will ultimately be raised from `__aexit__`), only setting `new_exc.__context__ = old_exc` for traceback-chaining purposes. The exception actually raised out of the `async with AsyncExitStack() as stack:` block is **whichever callback failed last, not the exception that was already in flight when the block started unwinding**. If the failed-startup cleanup is built as `stack.push_async_callback(client.close)` for each client and `stack.push_async_callback(db.close)` for the db, and e.g. the second client's `close()` itself raises during the unwind triggered by a migration failure, the exception that actually propagates out of the lifespan is that second client's close error — not the migration failure. This directly violates D-03 ("the original startup error is re-raised unchanged") and D-06 ("the original startup error... is the exception that propagates").

**Why it happens:** The phrase "all opened connections will automatically be released... even if attempts to open a connection later in the list raise an exception" (from `AsyncExitStack`'s own docstring, and quoted in STACK.md) is true and is exactly the acquisition-failure case this phase cares about — but it describes callbacks running to completion, not what happens to the *exception value* when one of those callbacks itself fails. STACK.md's Capability 2a text describes the "every callback runs" guarantee correctly; it does not surface this exception-replacement nuance, which only matters once you ask "which exception ends up being raised" rather than "did every callback get a chance to run."

**How to avoid:** Never register a raw, potentially-raising callable with `AsyncExitStack` (or an explicit tracked loop) for this phase's purposes. Every registered close operation must be the `_safe_close` wrapper from Pattern 2, which catches everything internally and never raises past itself — at that point, `AsyncExitStack`'s unwind loop never sees a callback exception at all, so its replacement behavior never triggers, and the exact same plain-list approach (no `AsyncExitStack`) produces identical, simpler-to-reason-about behavior. If the planner chooses `AsyncExitStack` anyway (CONTEXT.md leaves this open), this wrapping is not optional — it is the only way `AsyncExitStack` satisfies D-03/D-06 in this phase.

**Warning signs:** `stack.push_async_callback(client.close)` or `stack.push_async_callback(db.close)` anywhere in a diff — i.e., the close method referenced directly rather than through `_safe_close` or an equivalent try/except wrapper.

**Test that catches it:** A failed-startup test where **two** things fail: the originating setup step (e.g. `init_db`) raises, AND one of the already-constructed clients' `close()` also raises during cleanup. Assert the exception that propagates out of `async with lifespan_fn(app):` is still the `init_db` exception (by type and/or message), not the client's close exception. This test would fail against a naive `AsyncExitStack` implementation using raw callbacks and pass against both the plain-list-with-`_safe_close` approach and a correctly-wrapped `AsyncExitStack` approach — making it the single most valuable new test in this phase for catching the specific trap CONTEXT.md flagged for this research to investigate.

### Pitfall E: A cap that fires on `db.close()` itself doesn't guarantee the worker thread actually stops — know the residual limitation

**What goes wrong:** `aiosqlite.Connection.close()` (confirmed from installed source, `core.py:199-212`) is `try: await self._execute(self._conn.close) ... finally: self._connection = None; future = self.stop(); if future: await future`. CORRECTED: if a cap implemented as `async with asyncio.timeout(_CLEANUP_STEP_TIMEOUT): await db.close()` fires while awaiting `self._execute(self._conn.close)`, the task is cancelled — but `close()`'s own `finally:` block still runs, calls `self.stop()` (enqueueing the stop sentinel) and then AWAITS the returned future. While the worker thread is blocked that future never resolves, so the cancelled task cannot finish and the `asyncio.timeout` block cannot exit: the cap does not hold (probe: not returned after 1.5s with a 0.2s cap). The earlier text here claimed the timeout bounded cleanup's own wait in this case; that claim was wrong. `_safe_close` must therefore bound its own wait on an owned task (`asyncio.wait(..., timeout=...)`) rather than await the close inside `asyncio.timeout` (Plan-check corrections 1). In the common case (the underlying `sqlite3` `.close()` call itself is not what's hanging — the 5s cap is firing because something upstream in the asyncio scheduling is slow, not because sqlite is wedged), the sentinel still gets processed shortly after and the thread still exits, just not within our 5-second window — a `Thread.join(timeout=...)` called slightly later in the test (or by the OS at actual process exit) would still observe it as stopped. In the genuinely pathological case (the underlying `sqlite3.Connection.close()` call itself is blocked, e.g. on a stuck OS-level file lock), the worker thread is wedged processing that one queued item and will never reach the stop sentinel — no asyncio-level timeout can un-wedge a separate OS thread blocked in C code, and D-10 explicitly forbids a forced-process-exit escape hatch for this.

**Why it happens:** `asyncio.timeout()` only ever cancels the *awaiting coroutine's* wait on a future, and only regains control when that coroutine actually finishes unwinding; it has no mechanism to interrupt a different OS thread that isn't cooperating with asyncio at all, and it cannot return while the cancelled coroutine keeps awaiting in a `finally:`.

**How to avoid:** Treat this as a known, documented residual limitation rather than something this phase's cap can fully close — D-09's cap exists to bound how long *cleanup as a whole* takes before moving on and re-raising the original error (satisfying "the process exits promptly" for the vastly more common case where every individual close actually succeeds quickly), not to guarantee thread termination in the pathological wedged-close case. The D-11/D-12 regression test should exercise the realistic case (a setup step raises; `db.close()` itself is not mocked to hang, it runs for real and completes within milliseconds) and assert the thread stops — this is what actually fixes Pitfall 6 as originally found (today, `db.close()` is simply *never called* on this path; once it is called, it overwhelmingly will complete normally). CORRECTED: a blocked worker thread CAN be simulated in-process without an OS-level lock (queue a blocking callable with `conn._execute(threading.Event().wait)` ahead of the close), and plan 89-01 adds that regression plus a synthetic close that waits again in its cancellation finalizer. The remaining residual limitation, consistent with D-10's rejection of a forced-exit workaround: the abandoned close task and the worker thread stay alive until the blockage clears, and a close still blocked at process exit can delay that exit.

**Test that catches it:** CORRECTED: `test_safe_close_returns_at_cap_when_close_waits_in_cancellation_finalizer` and `test_safe_close_returns_at_cap_on_wedged_real_aiosqlite_close` (plan 89-01 Task 1) and `test_shutdown_abandons_hung_client_close_after_cap` (Task 2): the helper returns at the cap and later cleanup proceeds before the finalizer / blocked worker is released.

## Code Examples

### Verified: `aiosqlite.Connection`'s worker thread is non-daemon and only stops via the sentinel `close()` enqueues

```python
# Source: .venv/lib/python3.11/site-packages/aiosqlite/core.py (installed aiosqlite 0.22.1)
# Connection.__init__ (no daemon=True passed to Thread):
self._thread = Thread(target=_connection_worker_thread, args=(self._tx,))
# Connection.__await__ starts it:
def __await__(self):
    self._thread.start()
    return self._connect().__await__()
# Connection.close():
async def close(self) -> None:
    if self._connection is None:
        return
    try:
        await self._execute(self._conn.close)
    except Exception:
        LOG.info("exception occurred while closing connection")
        raise
    finally:
        self._connection = None
        future = self.stop()      # enqueues _STOP_RUNNING_SENTINEL regardless
        if future:
            await future
```
A test can verify the thread actually stopped: `conn._thread.join(timeout=2.0); assert not conn._thread.is_alive()`. This is the only way to actually prove LIFE-01's "process exits promptly" claim, since checking that `close()` was *called* (e.g. on a `Mock`) proves nothing about the real `aiosqlite.Connection`'s thread.

### Verified: Starlette's lifespan driver never reaches the generator's own `finally:` on a pre-`yield` failure

```python
# Source: .venv/lib/python3.11/site-packages/starlette/routing.py (installed starlette 1.10.0), ~line 652-677
async def lifespan(self, scope, receive, send) -> None:
    started = False
    await receive()
    try:
        async with self.lifespan_context(app) as maybe_state:
            ...
            await send({"type": "lifespan.startup.complete"})
            started = True
            await receive()
    except BaseException:
        ...
        if started:
            await send({"type": "lifespan.shutdown.failed", ...})
        else:
            await send({"type": "lifespan.startup.failed", ...})
        raise
```
`self.lifespan_context(app)` is `create_lifespan`'s `@asynccontextmanager`-wrapped generator. If it raises before its own `yield`, `__aenter__` raises, `__aexit__` (the generator's `finally:`) is never entered — this is standard `@asynccontextmanager` semantics, confirmed here against the exact installed Starlette version in use.

### Verified: uvicorn does not re-raise a failed startup — it logs and returns, so only thread liveness determines whether the process actually exits

```python
# Source: .venv/lib/python3.11/site-packages/uvicorn/lifespan/on.py (installed uvicorn 0.54.0)
async def main(self) -> None:
    try:
        ...
        await app(scope, self.receive, self.send)
    except BaseException as exc:
        self.error_occurred = True
        ...  # logs, does NOT re-raise
    finally:
        self.startup_event.set()
        self.shutdown_event.set()

async def startup(self) -> None:
    ...
    if self.startup_failed or (self.error_occurred and self.config.lifespan == "on"):
        self.logger.error("Application startup failed. Exiting.")
        self.should_exit = True   # <-- no exception raised here either
    else:
        self.logger.info("Application startup complete.")
```
`server.serve()` sees `should_exit=True` and returns normally; `triggarr/__main__.py`'s `await server.serve()` then returns, `_run()` returns, `asyncio.run(_run())` returns, `main()` returns — **the Python process then waits for every non-daemon thread to finish before actually exiting.** This confirms, directly from the installed dependency chain Triggarr runs on, that "the exception propagated" and "the process exits promptly" are two different claims — only the aiosqlite worker thread's liveness determines the second one.

### Verified (CORRECTED): `BaseScheduler.start()` sets `STATE_RUNNING` before its logging, start event and `wakeup()`; `shutdown()` on a stopped scheduler raises

```python
# Source: .venv/lib/python3.11/site-packages/apscheduler/schedulers/base.py (installed apscheduler 3.11.3)
def start(self, paused=False):
    if self.state != STATE_STOPPED:
        raise SchedulerAlreadyRunningError
    ...  # executors, jobstores, pending jobs all processed here -- can raise
    self.state = STATE_PAUSED if paused else STATE_RUNNING   # <-- line 213, NOT the last operation
    self._logger.info("Scheduler started")                    # 214
    self._dispatch_event(SchedulerEvent(EVENT_SCHEDULER_STARTED))  # 215
    if not paused:
        self.wakeup()                                         # 217-218; a raise here leaves the scheduler RUNNING

def shutdown(self, wait=True):
    if self.state == STATE_STOPPED:
        raise SchedulerNotRunningError   # <-- first line
    ...
```

## State of the Art

| Old Approach (current code) | Current/Recommended Approach (this phase) | When Changed | Impact |
|---|---|---|---|
| Setup code runs fully unprotected before `try: yield / finally:` | Setup wrapped in its own `try/except Exception`, tracking resources as locals, with a shared `_safe_close` cleanup helper reused by both paths | This phase (89) | Closes the Pitfall 6 process-hang gap; no behavior change on the happy path |
| Shutdown's client-close loop has no per-client isolation | Each `client.close()` (and `db.close()`, and the guarded `scheduler.shutdown()`) wrapped individually via `_safe_close` | This phase (89) | Closes the Pitfall 7 "one failure skips everything after it" gap; existing shutdown *order* (D-04) is unchanged |

**Deprecated/outdated:** Nothing in the dependency stack is deprecated; this is purely an in-house code-structure fix, not a library migration.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The exact module constant name/value for the per-step cap (`_CLEANUP_STEP_TIMEOUT = 5.0`) is a naming suggestion, not a locked decision — CONTEXT.md explicitly leaves the exact value and name to the planner | Pattern 2, Standard Stack | None if the planner picks a different name/value; purely cosmetic |
| A2 | `scheduler.shutdown()` is synchronous and does not itself need `asyncio.timeout()` wrapping (confirmed: no `async def`, no `await` inside `BaseScheduler.shutdown()`'s installed source) — included as [VERIFIED] rather than assumed, but flagged here since it affects how literally `_safe_close` should be reused for this one call | Pattern 3 | Low — if wrapped anyway in a trivial `async def` lambda, `asyncio.timeout` would still work correctly (a timeout around a function that never yields simply never fires), so getting this "wrong" has no functional consequence, only a slightly misleading-looking cap that can't actually trigger |

No claim in this research about library *behavior* (Starlette's lifespan driver, uvicorn's lifespan handling, aiosqlite's thread model, APScheduler's state machine, `AsyncExitStack`'s unwind semantics) is `[ASSUMED]` — every one was re-verified against the exact installed source this session, cited with file paths above. The two rows above are the only genuinely open, non-verified choices, and both are low-risk/cosmetic per CONTEXT.md's own Claude's-Discretion framing.

**Cursor-lifetime recheck (REQUIREMENTS.md standing rule):** the aiosqlite "cursor-lifetime" concern named in the original roadmap wording for 999.13 was re-checked this session specifically for this phase's scope: every cursor-returning call in `triggarr/db.py` (8 call sites, e.g. lines 77, 594, 682, 700, 915, 1020, 1195, 1559) goes through `async with db.execute(...) as cursor:`, aiosqlite's own `@contextmanager`-wrapped helper that guarantees cursor cleanup on block exit. No raw, unmanaged cursor object is held across an `await` or across the connection's lifetime anywhere in the codebase. This confirms SUMMARY.md's "not found" conclusion and STATE.md's "closed/not-applicable" note — nothing in this phase's scope (startup/shutdown resource symmetry) is affected by or needs to address a cursor-lifetime issue; none exists in the current code.

## Open Questions (all RESOLVED)

1. **Exact wording of the D-05 summary line's "connection" count — does it count attempted closes or only successful ones?**
   - What we know: D-05's example is "Startup failed; closed the database and 3 connections before exiting." `_safe_close` returns a boolean per step, so both an "attempted" count (len of everything cleanup tried) and a "succeeded" count (sum of `True` returns) are trivially available.
   - What's unclear: whether a step that itself failed (and is already logged at warning level per D-06) should count toward the summary's number, or be excluded.
   - Recommendation: count successes only (sum of `True`), since D-06 already separately warns about any step that failed — the summary line's number should answer "how much actually got cleaned up," and double-counting a failed step as "closed" would be misleading to an operator reading only the summary line.
   - **RESOLVED (2026-11-18):** the summary counts successes only. "the scheduler" and "the database" are named only when their stop/close was observed to succeed, and the connection count is the number of client closes that returned success. Implemented in plan 89-02 Task 1 (`_describe_closed`), asserted by `test_startup_failure_cleanup_also_fails_still_raises_original` (1 of 2 connections) and `test_startup_failure_cleanup_also_fails_on_db_close` (no "the database").

2. **Does the D-11 test matrix need a dedicated "scheduler.start() itself raises" stage, separate from "a step after start() raises"?**
   - What we know: `scheduler.start()`'s internal pending-job processing (`_real_add_job` for each job queued via `add_job()` before `start()`) could itself raise before `self.state = STATE_RUNNING` is reached — this is a real, if rare, stage distinct from "update_check_job's `add_job()` fails after `start()` already succeeded."
   - What's unclear: whether triggering this specific internal-APScheduler failure mode is easy to simulate in a test (likely requires monkeypatching `AsyncIOScheduler.start` itself to raise, rather than constructing a genuinely malformed job) versus whether the existing `_FakeScheduler` test double (`tests/test_scheduler.py:1946-1965`, used via `patch("triggarr.search.scheduler.AsyncIOScheduler", return_value=_FakeScheduler())`) is sufficient by having its `.start()` raise.
   - Recommendation: use `_FakeScheduler` (or a variant with `.start()` raising) for this stage rather than trying to construct a real APScheduler internal failure — it already exists, is already the project's convention for scheduler-level lifespan tests, and directly exercises "the `started` flag must stay False when `start()` raises," which is the actual behavior under test, not APScheduler's internals.
   - **RESOLVED (2026-11-18):** yes, the scheduler-start failure stage is tested, in both forms. (a) `start()` fails before the running-state transition: a `_FakeScheduler` variant whose `start()` raises (`test_startup_failure_scheduler_start_raises_no_shutdown_call`) — the scheduler is not running and `shutdown()` is never called. (b) Partial start, `start()` fails after the running-state transition: a REAL `AsyncIOScheduler` subclass whose `wakeup()` raises (`test_startup_failure_partial_scheduler_start_is_stopped`) — cleanup must leave it actually `STATE_STOPPED` with the original error preserved. The recommendation above to rely on a `started` flag is superseded: cleanup reads `scheduler.running` (Plan-check corrections 2). Both are in plan 89-02 Task 2.

## Environment Availability

Skipped — this phase introduces no new external dependency, service, or tool. All behavior changes are internal to `triggarr/search/scheduler.py` using already-installed packages (`aiosqlite`, `httpx`, `apscheduler`, stdlib `asyncio`/`contextlib`).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio (`asyncio_mode = "auto"`, `pyproject.toml:43`) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/test_scheduler.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LIFE-01 | Failed startup (migration-stage) closes db; worker thread stopped; original error propagates unchanged | unit (in-process lifespan) | `uv run pytest tests/test_scheduler.py -k "startup_failure and init_db" -x -q` | ✅ `tests/test_scheduler.py` exists; new test function(s) to add |
| LIFE-01 | Failed startup (cutover-stage) closes db + already-built clients; worker thread stopped | unit | `uv run pytest tests/test_scheduler.py -k "startup_failure and cutover" -x -q` | ✅ same file, new test |
| LIFE-01 | Failed startup (client-construction-stage, Nth instance) closes db + every client built before the failure | unit | `uv run pytest tests/test_scheduler.py -k "startup_failure and client_construction" -x -q` | ✅ same file, new test |
| LIFE-01 | Failed startup where a cleanup step *also* fails (e.g. one client's close raises during cleanup) still re-raises the *original* error, not the cleanup error | unit — this is Pitfall D's regression test, the highest-value new test in this phase | `uv run pytest tests/test_scheduler.py -k "startup_failure and cleanup_also_fails" -x -q` | ✅ same file, new test |
| LIFE-02 | Shutdown: one client's `close()` raises a non-httpx exception (`AssertionError`); remaining clients and db still close; warning logged sanitized | unit | `uv run pytest tests/test_scheduler.py -k "shutdown and client_close_fails" -x -q` | ✅ same file, new test |
| LIFE-02 | Shutdown: db close itself fails; warning logged; "Search engine stopped" still logs (D-08: no new summary line) | unit | `uv run pytest tests/test_scheduler.py -k "shutdown and db_close_fails" -x -q` | ✅ same file, new test |
| LIFE-03 | Failed startup *before* `scheduler.start()` (e.g. `init_db` raises): cleanup does not call `scheduler.shutdown()` and does not raise `SchedulerNotRunningError` | unit (Pitfall C regression) | `uv run pytest tests/test_scheduler.py -k "startup_failure and scheduler_not_started" -x -q` | ✅ same file, new test |
| LIFE-03 | Failed startup *at or after* `scheduler.start()` (e.g. `update_check_job`'s `add_job` raises): cleanup calls `scheduler.shutdown()`; scheduler is left not-running | unit | `uv run pytest tests/test_scheduler.py -k "startup_failure and scheduler_started" -x -q` | ✅ same file, new test |

All seven rows above reuse the existing `async with lifespan_fn(app): ...` pattern (`tests/test_scheduler.py:974-998` and throughout), the existing `make_settings()`/`default_state()` factories (`tests/conftest.py:39-99`), the existing `_FakeScheduler` double (`tests/test_scheduler.py:1946-1965`) for the scheduler-stage tests, and the existing `io.StringIO()` + `logger.add(sink, ...)` pattern (e.g. `tests/test_scheduler.py:1228-1229`) for asserting on the D-05/D-06/D-07 log wording. No new test file, fixture infrastructure, or framework install is needed.

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_scheduler.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/bm:verify-work`

### Wave 0 Gaps

None — existing test infrastructure (`tests/test_scheduler.py`, `tests/conftest.py`'s `make_settings`/`default_state`, the `_FakeScheduler` double, the `io.StringIO()` log-capture pattern) covers everything this phase's new tests need. No new fixture, framework, or test file is required before implementation can start.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | Not touched by this phase |
| V3 Session Management | No | Not touched by this phase |
| V4 Access Control | No | Not touched by this phase |
| V5 Input Validation | No | No new user input surface |
| V6 Cryptography | No | Not touched by this phase |
| V7 Error Handling and Logging | Yes | New warning/summary log lines (D-05/D-06/D-07) must never include a raw exception message that could carry a URL with an embedded `apikey=` parameter (a known, already-documented concern elsewhere in this codebase, e.g. `_on_job_error`'s docstring at `scheduler.py:441-444`). Standard control: route every new log line's exception detail through the existing `triggarr.clients.base._sanitize_exc` (already imported into `scheduler.py`), never through raw `str(exc)`. Verified this session: its fallback branch already produces the exact `(AssertionError)`-style wording D-07 specifies for any non-httpx/pydantic exception, so this is a direct reuse, not new code. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A close-failure log line echoing a raw exception message that contains a legacy *arr instance's URL with an `apikey=` query parameter | Information Disclosure | Always call `_sanitize_exc(exc)` for the logged reason, never `str(exc)` or an f-string embedding the exception directly — this is the existing, already-audited project convention, not a new pattern to design |
| A hung non-daemon thread after a leaked `aiosqlite.Connection` keeping the process alive indefinitely on every restart attempt during a crash loop | Denial of Service (availability) | This is the actual bug this phase fixes (Pitfall 6/A above); the mitigation is the fix itself — closing every opened resource on every failed-startup path, bounded by `_CLEANUP_STEP_TIMEOUT` so cleanup itself cannot hang indefinitely (D-09/D-10) |

No new user-facing input, authentication, or authorization surface is introduced by this phase — it is pure process-lifecycle hardening. The two rows above are the complete, honestly-scoped security surface.

## Sources

### Primary (HIGH confidence — read directly this session)

- `triggarr/search/scheduler.py` (lines 1-90, 440-757) — current `create_lifespan`/`lifespan` structure, existing shutdown sequence, existing `_SHUTDOWN_DRAIN_TIMEOUT`/`asyncio.timeout()` idiom, existing `_sanitize_exc` import
- `triggarr/clients/base.py` (full file) — `ArrClient.close()`, `_sanitize_exc` canonical definition
- `triggarr/search/engine.py` (`_sanitize_exc` re-export, line 23) — confirms `scheduler.py`'s imported `_sanitize_exc` is the same function object defined in `clients/base.py`
- `triggarr/web/routes.py` (lines 1009-1039, 1237-1248) — `_close_removed_client` (Phase 87) wording precedent for close-failure log lines
- `triggarr/__main__.py` (lines 36-90) — confirms `server.serve()` is awaited with nothing downstream that would force a process exit independent of thread liveness
- `tests/test_scheduler.py` (lines 960-1046, 1940-1996) — existing lifespan test pattern (`async with lifespan_fn(app): ...`), existing `io.StringIO()` log-capture pattern, existing `_FakeScheduler` double
- `tests/conftest.py` (lines 39-99) — `make_settings()`/`default_state()` factories
- `tests/test_clients.py` (lines 171-389) — TEST-04, the empirical pin that an in-flight request task fails with `AssertionError` when the client is closed under it (`close()` itself returns cleanly)
- `.venv/lib/python3.11/site-packages/aiosqlite/core.py` (installed aiosqlite 0.22.1) — `Connection.__init__`/`__await__`/`stop`/`close`, `_connection_worker_thread` — confirms non-daemon `Thread`, confirms `close()`'s `finally:` unconditionally enqueues the stop sentinel
- `.venv/lib/python3.11/site-packages/starlette/routing.py` (installed starlette 1.10.0, ~lines 652-677) — `Router.lifespan`'s `started` flag and pre-`yield` exception handling
- `.venv/lib/python3.11/site-packages/uvicorn/lifespan/on.py` (installed uvicorn 0.54.0, full file read) — confirms `LifespanOn.main()` does not re-raise a startup failure; confirms `should_exit=True` is set without raising
- `.venv/lib/python3.11/site-packages/apscheduler/schedulers/base.py` (installed apscheduler 3.11.3, lines 115-268) — `BaseScheduler.__init__`/`start`/`shutdown`, `STATE_STOPPED`/`STATE_RUNNING` constants and transitions
- `.venv/lib/python3.11/site-packages/apscheduler/schedulers/asyncio.py` (installed apscheduler 3.11.3, lines 18-38) — `AsyncIOScheduler.start()` confirmed to delegate directly to `BaseScheduler.start()`
- Local CPython `contextlib.py` (`_BaseExitStack`, `AsyncExitStack`, read via `inspect.getsource` this session) — confirms the exact LIFO unwind loop and exception-replacement (`exc = new_exc`, chained via `__context__`) behavior underlying Pitfall D
- `uv.lock` — pinned versions: `aiosqlite==0.22.1`, `httpx==0.28.1`, `apscheduler==3.11.3`, `starlette==1.10.0`, `fastapi==0.162.4`, `uvicorn==0.54.0`
- `pyproject.toml` — `requires-python = ">=3.11"`, `target-version = "py311"`, `line-length = 120`, `asyncio_mode = "auto"`

### Secondary (MEDIUM confidence)

- `.planning/research/STACK.md` (Capability 2a/2b) — original `AsyncExitStack` recommendation; corroborated by this session's own direct source reads, with the exception-replacement caveat (Pitfall D) added as a refinement this session's deeper read surfaced
- `.planning/research/PITFALLS.md` (Pitfalls 6, 7, 8) — original pitfall writeups; corroborated and extended (Pitfalls C, D, E are new findings from this session's deeper verification, not restatements)

### Tertiary (LOW confidence)

None — every claim in this document traces to a primary source read this session.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies; every version and behavioral claim read from the installed package source, not assumed
- Architecture: HIGH — the acquisition/release asymmetry, the Starlette/uvicorn lifespan-failure handling chain, and the APScheduler state machine were all traced directly through installed source this session
- Pitfalls: HIGH — Pitfalls A, B, C, E restate and tighten PITFALLS.md's existing Pitfalls 6/7/8 with this session's own direct verification; Pitfall D (`AsyncExitStack` exception replacement) is a new finding, verified directly against CPython's own `contextlib` source, not inferred

**Research date:** 2026-11-18
**Valid until:** No external expiry — this is a closed, stdlib-only, pinned-dependency investigation of code already in the repository; the findings do not go stale on a calendar basis. Re-verify only if `aiosqlite`, `httpx`, `apscheduler`, `starlette`, `uvicorn`, or `fastapi` are version-bumped before this phase is planned/executed.

---
*Research for: Phase 89 - Startup & Shutdown Resource Cleanup*
*Researched: 2026-11-18*
