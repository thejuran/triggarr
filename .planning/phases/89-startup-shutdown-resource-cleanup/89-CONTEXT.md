# Phase 89: Startup & Shutdown Resource Cleanup - Context

**Gathered:** 2026-11-18
**Status:** Ready for planning

<domain>
## Phase Boundary

The FastAPI lifespan built by `create_lifespan` (`triggarr/search/scheduler.py`) closes what it opened on every path. A startup that fails partway (database upgrade, attribution cutover, client construction, job scheduling, scheduler start) closes the database connection, every *arr client already constructed and the scheduler if it was started, then re-raises the original error so the process exits promptly instead of hanging on the aiosqlite worker thread. At shutdown, one client failing to close never stops the remaining clients or the database from closing, and the failure is logged sanitized. Requirements: LIFE-01, LIFE-02, LIFE-03. Built-image proof belongs to Phase 92. The other cancellation and close items deferred from Phase 87 (settings routes, `_close_removed_client`) are not part of this phase.

</domain>

<decisions>
## Implementation Decisions

### Carried forward (milestone standing rules and prior phases, not re-asked)
- **D-01:** No new runtime dependency (stdlib only, e.g. `contextlib.AsyncExitStack`, `asyncio.timeout`). Each fix lands with a regression test that fails on the unfixed code.
- **D-02:** (Phase 87 D-16 pattern) When one cleanup step fails, every remaining cleanup step still runs, and each failure is logged with secrets redacted by the existing loguru sink.
- **D-03:** The original startup error is re-raised unchanged. Startup still fails loudly; only the leak is fixed (research PITFALLS.md Pitfall 6 warning signs). The fix must cover every setup step after the database opens, not only `init_db`/`run_migrations`.
- **D-04:** The existing shutdown order stays: stop the scheduler, drain the search lock (existing `shutdown_drain_timeout` behavior unchanged), close clients, close the database, log "Search engine stopped".

### Failed-startup log
- **D-05:** The original startup error stays first and unchanged in the log. After cleanup, one summary line states that startup failed and what was closed (for example "Startup failed; closed the database and 3 connections before exiting"). No per-step success lines.
- **D-06:** A cleanup step that itself fails during a failed startup is logged at warning level naming what failed (redacted reason). The original startup error stays the reported cause and is the exception that propagates.

### Shutdown close failure
- **D-07:** A client that fails to close at shutdown gets one warning-level line naming the app, the instance and the reason (exception type plus redacted message; never a URL with credentials or an API key), then shutdown continues. Example shape: "Shutdown: could not close Sonarr/'anime' connection (AssertionError); continuing." The catch is broad (`Exception`), because the in-flight-close failure is not guaranteed to be an `httpx` type (TEST-04 finding, research Pitfall 7).
- **D-08:** No new summary line at the end of shutdown; the existing "Search engine stopped" ending stays.

### Hung cleanup cap
- **D-09:** Each close step (each client, the database, during failed startup and shutdown) is bounded by a short fixed limit of about 5 seconds: a module constant, not a new config setting. A step that overruns is logged as a warning naming the step, and cleanup moves on to the next step.
- **D-10:** No forced process exit. The fix is to close resources properly; Triggarr does not add an `os._exit`-style guard that would hide future leaks.

### How it's proven
- **D-11:** In-process tests in this phase only (pattern: `async with lifespan_fn(app)` as in `tests/test_scheduler.py`). For each failure stage (database upgrade, cutover, client construction, job scheduling/scheduler start), assert that the original error propagates, the database is actually closed, every client constructed so far is closed, and the scheduler is not running. A shutdown test makes one client's close raise and asserts the later clients and the database still close and a warning is logged. The built-image demonstration is Phase 92 (SMOKE), which already exercises repeated failed upgrades.
- **D-12:** The failed-startup test also asserts that the aiosqlite background worker thread has stopped (no leftover non-daemon thread from the connection), not only that `close()` was called on a mock. That thread is the actual cause of the container hang (research Pitfall 6).

### Claude's Discretion
- Mechanism: `AsyncExitStack` around acquisition and release (research STACK.md, Capability 2, recommends it for both halves) or explicit tracked try/except, as long as D-02 to D-10 hold.
- Exact value of the per-step cap (about 5s) and its constant name; how a timed-out database close interacts with D-12 (if the cap fires on a db close, the worker thread may remain; the planner decides how this is logged and tested).
- Exact wording of the D-05, D-06 and D-07 log lines within the redaction rules.
- Whether the scheduler is shut down via the same unwind (it is only started near the end of setup; LIFE-03 requires it is not left running).
- Test fixtures and how setup steps are made to fail (patching `init_db`, `ensure_cutover_recorded`, a client class, `scheduler.start`).

</decisions>

<specifics>
## Specific Ideas

- Crash-loop context: a failed upgrade (Phase 88's case) should now fail fast and restart in seconds, not wait for Docker's `stop_grace_period: 90s` kill on every attempt.
- The operator always sees the real cause first; cleanup lines are secondary (warnings).

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and scope
- `.planning/REQUIREMENTS.md` — LIFE-01, LIFE-02, LIFE-03
- `.planning/ROADMAP.md` — Phase 89 section, success criteria

### Research (v2.14)
- `.planning/research/PITFALLS.md` — Pitfall 6 (failed startup leaks; aiosqlite non-daemon worker thread hangs the process), Pitfall 7 (shutdown close loop has no per-client isolation), Pitfall 8 (do not parallelize closes with TaskGroup)
- `.planning/research/STACK.md` — Capability 2 (2a/2b): Starlette 1.10.0 lifespan semantics, `AsyncExitStack` unwind behavior, what not to use (anyio rewrite)
- `.planning/research/SUMMARY.md` — Phase 3 rationale: startup and shutdown halves stay in one phase

### Prior phase decisions
- `.planning/phases/87-settings-state-file-safety/87-CONTEXT.md` — D-15/D-16 (every tidy-up step runs; failures logged redacted)
- `.planning/phases/88-bounded-upgrade-backups-telemetry-regression/88-CONTEXT.md` — D-09 (cleanup failures at warning level, not error), D-12 (in-process tests; built image in Phase 92)

### Deferred items not in scope
- `.planning/backlog/MAINTENANCE.md` — Phase 87 deep-review deferrals (settings-route cancellation, `_close_removed_client` self-cancel, blocking set-aside copy at startup)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `create_lifespan` / `lifespan` in `triggarr/search/scheduler.py` (about lines 460-760): opens the db at `aiosqlite.connect`, runs `init_db`, `migrate_from_state`, `ensure_cutover_recorded`, constructs clients, sets `app.state`, schedules jobs, `scheduler.start()`, adds `update_check`; the `try: yield / finally:` only wraps the shutdown.
- Shutdown drain using `asyncio.timeout()` (WR-01 comment explains why not `wait_for`): reuse the same idiom for the per-step cap.
- `ArrClient.close()` (`triggarr/clients/base.py`) delegates to `httpx.AsyncClient.aclose()`.

### Established Patterns
- Loguru with redacting sink; never print/logging. Brace-style keyword log arguments.
- `tests/test_scheduler.py` drives the lifespan directly (`async with lifespan_fn(app): ...`); `tests/test_clients.py` TEST-04 pins the in-flight close `AssertionError` on httpx 0.28.1.
- Phase 87 `_close_removed_client` logs a failed close per instance; match its wording style.

### Integration Points
- `triggarr/__main__.py` runs startup before the lifespan; uvicorn sets `should_exit` on `lifespan.startup.failed`.
- Phase 92 smoke tests will exercise the failed-upgrade path on the built image.

</code_context>

<deferred>
## Deferred Ideas

None new. Phase 87's cancellation and close deferrals stay in `.planning/backlog/MAINTENANCE.md` and are not folded in.

</deferred>

---

*Phase: 89-startup-shutdown-resource-cleanup*
*Context gathered: 2026-11-18*
