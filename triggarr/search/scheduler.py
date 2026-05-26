"""APScheduler integration with FastAPI lifespan for automated search cycles.

Creates interval jobs for Radarr and Sonarr search cycles, managed through
FastAPI's lifespan context manager.  Shared state is exposed on ``app.state``
so that web routes can read it without coupling.  The ``make_search_job``
factory creates job closures that read from ``app.state`` rather than
capturing variables, enabling future hot-reload of clients and settings.

Phase 65 hardening layered on top of the original wiring:
- SAFETY-02 (65-01): narrow-tuple cycle except + EVENT_JOB_ERROR listener so
  code-bug exceptions escape APScheduler's default silence.
- SAFETY-03 (65-02): per-job consecutive-failure counter on
  ``app.state.search_failures`` driven by the engine's ``connected`` flag;
  split persistence branch with ``app.state.persistence_degraded`` flag.
- RES-01 (65-03): configurable shutdown drain (``_SHUTDOWN_DRAIN_TIMEOUT``,
  env-overridable via ``TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT``) + holder identity
  on ``app.state.search_lock_holder``; INFO-on-entry and WARNING-on-timeout
  shutdown logs both name the stuck cycle and elapsed runtime so operators
  see what was draining even if Docker SIGKILLs mid-drain.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import httpx
import pydantic
from apscheduler.events import EVENT_JOB_ERROR
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from loguru import logger

from triggarr.clients.base import ArrClient
from triggarr.clients.lidarr import LidarrClient
from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.db import init_db, migrate_from_state
from triggarr.models.config import APP_TYPES, Settings
from triggarr.search.engine import _sanitize_exc, run_lidarr_cycle, run_radarr_cycle, run_sonarr_cycle
from triggarr.state import (
    TriggarrState,
    _default_instance_state,
    cleanup_orphaned_instances,
    load_state,
    save_state,
)
from triggarr.tracking import run_tracking_check
from triggarr.update_check import check_for_update


def _read_shutdown_drain_timeout() -> float:
    """RES-01 (Codex finding 3): read TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT env var.

    Defaults to 60.0s. Clamped to >= 1.0 so a misconfiguration (e.g. setting
    the env var to "0") cannot disable the shutdown drain entirely.
    Malformed values fall back to the default rather than crashing import.

    Recommended deployment: set the host process manager's stop-timeout
    greater than this value (e.g. docker-compose stop_grace_period: 90s,
    docker run --stop-timeout 90, systemd TimeoutStopSec=90) so the
    in-process drain has time to complete before SIGKILL.
    """
    raw = os.environ.get("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", "60.0")
    try:
        value = float(raw)
    except (ValueError, TypeError):
        value = 60.0
    return max(value, 1.0)


# RES-01 (Codex finding 3): configurable; default 60.0s; clamped >= 1.0 to
# prevent misconfig disabling drain entirely. Recommended deployment: set
# docker-compose stop_grace_period > this value (default 90s).
_SHUTDOWN_DRAIN_TIMEOUT: float = _read_shutdown_drain_timeout()


def make_search_job(
    app: FastAPI, app_name: str, instance_name: str, state_path: Path
) -> Callable[[], Awaitable[None]]:
    """Create an async job function that reads client/state/settings from app.state.

    The returned closure reads all shared objects from ``app.state`` at
    execution time rather than capturing them at creation time.  This
    allows the config editor (Plan 03) to swap clients and settings
    without restarting the scheduler.

    Args:
        app: The FastAPI application instance.
        app_name: One of the APP_TYPES values ("radarr", "sonarr", "lidarr").
        instance_name: Name of this instance (e.g., "Default", "4K").
        state_path: Path to the JSON state file for persistence.

    Returns:
        An async callable suitable for ``scheduler.add_job()``.
    """
    cycle_fns = {"radarr": run_radarr_cycle, "sonarr": run_sonarr_cycle, "lidarr": run_lidarr_cycle}
    cycle_fn = cycle_fns.get(app_name)
    if cycle_fn is None:
        logger.warning("{app}: search cycle not implemented yet, skipping", app=app_name.title())

        async def job() -> None:
            return

        return job

    async def job() -> None:
        clients = getattr(app.state, f"{app_name}_clients", {})
        client = clients.get(instance_name)
        if client is None:
            return
        instance_config = app.state.settings.get_enabled_instances(app_name).get(instance_name)
        if instance_config is None:
            return
        async with app.state.search_lock:
            # SAFETY-03: per-job consecutive-failure counter key; also reused
            # by plan 65-03 (lock-holder identity). Assigned first so every
            # branch below can reference it.
            job_id = f"{app_name}_{instance_name}_search"
            # RES-01: record holder identity INSIDE the lock so the shutdown
            # drain can name the stuck cycle. Cleared in the outer finally
            # below — runs even when a propagated exception (RuntimeError
            # from SAFETY-02, re-raised OSError/aiosqlite.Error from the
            # persistence branch below) escapes through.
            app.state.search_lock_holder = (job_id, time.monotonic())
            try:
                # --- Cycle execution (narrow-tuple catch; OSError REMOVED — Codex
                # finding 2: OSError is durability, not transient *arr blip). ---
                try:
                    app.state.triggarr_state = await cycle_fn(
                        client,
                        app.state.triggarr_state,
                        instance_name,
                        instance_config,
                        app.state.settings,
                        app.state.db,
                    )
                # SAFETY-02: narrow tuple — code-bug exceptions (RuntimeError,
                # KeyError, etc.) intentionally propagate to APScheduler's
                # EVENT_JOB_ERROR listener (_on_job_error). Do NOT add
                # asyncio.CancelledError here: it is BaseException, not Exception,
                # and the shutdown drain depends on its propagation.
                # SAFETY-03 (Codex finding 2): OSError moved to the dedicated
                # persistence branch below; persistence durability failures must
                # not be conflated with transient *arr cycle blips.
                except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error) as exc:
                    _record_cycle_failure(app, job_id, app_name, reason=_sanitize_exc(exc))
                    return

                # SAFETY-03 (Codex finding 1): cycle outcome derived from
                # state[app][inst][connected] — covers the REAL *arr outage path
                # where the engine catches httpx.HTTPError internally, sets
                # connected = False, and returns state without raising.
                _evaluate_cycle_outcome(app, app_name, instance_name, job_id)

                # SAFETY-03 (Codex finding 2): persistence is its own try/except.
                # OSError / aiosqlite.Error here are durability failures, NOT
                # transient *arr blips. Log ERROR immediately (no threshold gate),
                # mark persistence_degraded, and re-raise so EVENT_JOB_ERROR also
                # logs with job_id context. The counter is NOT incremented.
                try:
                    await asyncio.get_running_loop().run_in_executor(
                        None, save_state, app.state.triggarr_state, state_path
                    )
                except (OSError, aiosqlite.Error) as persist_exc:
                    app.state.persistence_degraded = True
                    logger.error(
                        "{app}: persistence failed -- {exc}",
                        app=app_name.title(),
                        exc=_sanitize_exc(persist_exc),
                    )
                    raise

                # --- Tracking check: resolve pending search outcomes for this instance ---
                try:
                    tracking_result = await run_tracking_check(
                        app.state.db,
                        client,
                        app_name.title(),
                        instance_name,
                        app.state.settings.general.tracking_window_minutes,
                    )
                    resolved = (
                        tracking_result["grabbed"]
                        + tracking_result["partial"]
                        + tracking_result.get("partial_expired", 0)
                        + tracking_result["unresolved"]
                    )
                    if resolved > 0 or tracking_result["errors"] > 0:
                        logger.info(
                            "Tracking: {grabbed} grabbed, {partial} partial, "
                            "{partial_expired} partial_expired, "
                            "{unresolved} unresolved, {errors} errors",
                            grabbed=tracking_result["grabbed"],
                            partial=tracking_result["partial"],
                            partial_expired=tracking_result.get("partial_expired", 0),
                            unresolved=tracking_result["unresolved"],
                            errors=tracking_result["errors"],
                        )
                except (
                    httpx.HTTPError,
                    pydantic.ValidationError,
                    aiosqlite.Error,
                    OSError,
                ) as tracking_exc:
                    # CR-01: match the sanitization split applied in
                    # `_on_job_error` (see its docstring): httpx/pydantic
                    # exceptions route through `_sanitize_exc` to strip
                    # `request.url` credentials that may carry `?apikey=`
                    # query parameters on legacy *arr installs. aiosqlite
                    # and OSError messages do not carry secrets, so plain
                    # `str(exc)` keeps them readable for debugging.
                    logger.warning(
                        "Tracking: check failed -- {exc}",
                        exc=(
                            _sanitize_exc(tracking_exc)
                            if isinstance(
                                tracking_exc,
                                httpx.HTTPError | pydantic.ValidationError,
                            )
                            else str(tracking_exc)
                        ),
                    )
            finally:
                # RES-01: clear holder regardless of how we exit the in-lock
                # body (success, narrow-tuple swallow + return, persistence
                # re-raise, or propagated unexpected exception).
                app.state.search_lock_holder = None

    return job


def _record_cycle_failure(app: FastAPI, job_id: str, app_name: str, reason: str) -> int:
    """SAFETY-03: increment the per-job failure counter and log at the appropriate level.

    Uses ``>=`` (per RESEARCH A6: count==threshold IS ERROR — the threshold
    represents "the Nth failure escalates"). Returns the new count for
    testability.

    Args:
        app: FastAPI app holding ``app.state.search_failures`` and ``app.state.settings``.
        job_id: ``f"{app_name}_{instance_name}_search"`` — the counter key.
        app_name: Lower-case *arr name ("radarr", "sonarr", "lidarr").
        reason: Pre-sanitized human-readable failure reason for the log line.
    """
    count = app.state.search_failures.get(job_id, 0) + 1
    app.state.search_failures[job_id] = count
    threshold = app.state.settings.general.max_consecutive_failures
    # SAFETY-03: >= per RESEARCH A6 (count==threshold IS ERROR)
    log_fn = logger.error if count >= threshold else logger.warning
    log_fn(
        "{app}: search cycle failed ({count}/{threshold}) -- {reason}",
        app=app_name.title(),
        count=count,
        threshold=threshold,
        reason=reason,
    )
    return count


def _evaluate_cycle_outcome(app: FastAPI, app_name: str, instance_name: str, job_id: str) -> bool:
    """SAFETY-03 (Codex finding 1): derive cycle outcome from the engine's `connected` signal.

    Production engine cycles catch ``httpx.HTTPError`` / ``pydantic.ValidationError``
    internally, set ``state[app][inst]["connected"] = False``, and return state
    rather than raising. The scheduler MUST observe this outcome to count
    real *arr outages — the rare narrow-tuple raise path alone is not enough.

    Returns True on success (counter reset), False on failure (counter
    incremented + escalation logged). Missing or None ``connected`` is treated
    as success (do not double-count first-ever cycle before the engine sets
    the flag).

    NOTE: This helper is invoked only from `make_search_job` (the APScheduler
    job factory). The manual-search-now endpoint in `triggarr/web/routes.py`
    invokes `cycle_fn(...)` directly and bypasses `make_search_job`, so a
    successful manual search does NOT currently reset the per-job counter,
    and a failing manual search does NOT currently increment it.
    TODO(SAFETY-03): refactor `search_now` to go through `make_search_job`
    (or extract a shared `_run_one_cycle(app, app_name, instance_name)`
    helper) so manual and scheduled searches share the same counter
    semantics. Deferred to a follow-up plan in v2.8 to keep this plan's
    diff focused on the scheduler path.
    """
    # SAFETY-03 (Codex finding 1): cycle outcome derived from state[app][inst][connected],
    # not from raised exceptions.
    connected = (
        app.state.triggarr_state.get(app_name, {})
        .get(instance_name, {})
        .get("connected")
    )
    if connected is False:
        _record_cycle_failure(app, job_id, app_name, reason="instance unreachable")
        return False
    # connected is True or unknown — treat as success to avoid double-counting.
    # SAFETY-03: manual searches via search_now bypass this reset (see TODO
    # above). The cycle counter is per-scheduler-job today.
    app.state.search_failures[job_id] = 0
    return True


def _on_job_error(event) -> None:
    """SAFETY-02: log propagated job exceptions at ERROR level.

    Registered via ``add_listener`` on the AsyncIOScheduler so that
    exceptions which fall outside the narrow tuple in ``make_search_job``
    (RuntimeError, KeyError, etc.) become operator-visible instead of
    disappearing into APScheduler's stdlib-logging silence.

    Sanitization split: httpx/pydantic exceptions route through
    ``_sanitize_exc`` (engine.py) to strip ``request.url`` credentials that
    may contain ``apikey=`` query parameters. All other exception types use
    ``str(exc)`` — Triggarr's non-httpx exceptions do not carry secrets.
    """
    exc = event.exception
    exc_repr = (
        _sanitize_exc(exc)
        if isinstance(exc, httpx.HTTPError | pydantic.ValidationError)
        else str(exc)
    )
    logger.error(
        "Job {job} failed unexpectedly: {type}: {exc}",
        job=event.job_id,
        type=type(exc).__name__,
        exc=exc_repr,
    )


def create_lifespan(
    settings: Settings, state_path: Path, config_path: Path
) -> Callable[..., AsyncIterator[None]]:
    """Build a FastAPI lifespan context manager wired to APScheduler.

    Creates long-lived API clients for enabled apps, schedules interval
    jobs for each, and ensures clean shutdown of both the scheduler and
    clients on application exit.  All shared objects are exposed on
    ``app.state`` for web route access.

    Args:
        settings: Application settings with app configs and intervals.
        state_path: Path to the JSON state file for persistence.
        config_path: Path to the TOML configuration file.

    Returns:
        An async context manager suitable for ``FastAPI(lifespan=...)``.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        state: TriggarrState = load_state(state_path)
        scheduler = AsyncIOScheduler()

        # Clean up orphaned instances and ensure new instances get default state
        state = cleanup_orphaned_instances(state, settings)
        for app_type in APP_TYPES:
            instances = getattr(settings, app_type, {})
            for inst_name in instances:
                if inst_name not in state.get(app_type, {}):
                    if app_type not in state:
                        state[app_type] = {}  # type: ignore[literal-required]
                    state[app_type][inst_name] = _default_instance_state()  # type: ignore[literal-required]

        # Initialize search history database with shared WAL connection
        db_path = state_path.parent / "triggarr.db"
        db = await aiosqlite.connect(db_path)
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await init_db(db, db_path)

        # Migrate existing search_log from state.json to SQLite (one-time)
        if state.get("search_log"):
            migrated = await migrate_from_state(db, state["search_log"])
            if migrated > 0:
                state["search_log"] = []
                await asyncio.get_running_loop().run_in_executor(None, save_state, state, state_path)

        # --- Create long-lived clients for enabled instances ---
        client_classes: dict[str, type[ArrClient]] = {
            "radarr": RadarrClient, "sonarr": SonarrClient, "lidarr": LidarrClient,
        }
        all_clients: dict[str, dict[str, ArrClient]] = {}

        for app_type in APP_TYPES:
            clients: dict[str, ArrClient] = {}
            cls = client_classes[app_type]
            for inst_name, cfg in settings.get_enabled_instances(app_type).items():
                clients[inst_name] = cls(
                    base_url=cfg.url,
                    api_key=cfg.api_key.get_secret_value(),
                    timeout=settings.general.request_timeout,
                    page_size=settings.general.page_size,
                )
            all_clients[app_type] = clients

        # --- Expose all shared state on app.state ---
        app.state.triggarr_state = state
        app.state.settings = settings
        app.state.db = db
        app.state.scheduler = scheduler
        app.state.radarr_clients = all_clients.get("radarr", {})
        app.state.sonarr_clients = all_clients.get("sonarr", {})
        app.state.lidarr_clients = all_clients.get("lidarr", {})
        app.state.config_path = config_path
        app.state.state_path = state_path
        # search_lock serializes (a) search cycles in scheduler.make_search_job and
        # (b) every config-save call to _atomic_toml_write in triggarr.web.routes.
        # SAFETY-05 (Assumption A1): this asyncio.Lock is correct only because
        # Triggarr runs a single uvicorn worker (__main__.py constructs uvicorn.Config
        # without workers=N). Adding --workers >1 would silently break serialization
        # because asyncio.Lock is per-event-loop. If you ever introduce multi-worker
        # uvicorn, replace this with a file-level lock (fcntl.flock) or a process-level
        # primitive. Verified statically by tests/audit_lock_coverage.py (AST audit of
        # routes.py) and dynamically by
        # tests/test_web.py::test_concurrent_settings_save_serialized.
        app.state.search_lock = asyncio.Lock()
        # WR-05: `app.state` is starlette.datastructures.State -- a
        # SimpleNamespace-like __dict__ container with no class slot to
        # attach __annotations__. Inline `: type = value` annotations on
        # these attributes were misleading: they are discarded at runtime
        # and not stored anywhere consultable. Document the intended types
        # in comments instead so readers do not infer enforcement that
        # does not exist.
        # last_search_time: dict[str, float]  (key: rate-limit token, value: monotonic ts)
        app.state.last_search_time = {}
        app.state.last_health_check = None
        # SAFETY-03: per-job consecutive-failure counter keyed by
        # f"{app_name}_{instance_name}_search". Incremented when the engine
        # cycle returns with connected=False or when the narrow-tuple cycle
        # catch fires; reset on cycle success.
        # search_failures: dict[str, int]
        app.state.search_failures = {}
        # SAFETY-03 (Codex finding 2): set to True when save_state raises
        # OSError/aiosqlite.Error mid-persistence. Observable state only in
        # this phase; future phase may surface via /health endpoint.
        # persistence_degraded: bool
        app.state.persistence_degraded = False
        # RES-01 (Codex finding 3): tuple[str, float] | None holding the
        # currently-running cycle's (job_id, monotonic_start). Set INSIDE
        # `async with search_lock` in make_search_job; cleared in the same
        # block's finally. Read by the shutdown drain to log which instance
        # is stuck and how long it's been running.
        # search_lock_holder: tuple[str, float] | None
        app.state.search_lock_holder = None

        # Import update_info dict once at lifespan start (not inside job)
        # to avoid circular import during scheduler ticks.
        from triggarr.web.routes import update_info as _update_info

        app.state.update_info = _update_info

        # Sync auth_state at startup so the nav bar logout link renders
        # correctly for users whose session cookie is still valid after restart.
        from triggarr.web.routes import _sync_auth_state

        _sync_auth_state(settings)

        # --- Schedule jobs for enabled instances using make_search_job ---
        for app_name in APP_TYPES:
            for inst_name, cfg in settings.get_enabled_instances(app_name).items():
                job_fn = make_search_job(app, app_name, inst_name, state_path)
                job_id = f"{app_name}_{inst_name}_search"
                scheduler.add_job(
                    job_fn,
                    "interval",
                    minutes=cfg.search_interval,
                    id=job_id,
                    next_run_time=datetime.now(UTC),
                )
                logger.info(
                    "Scheduled {app}/{instance} search every {interval}m (first run: now)",
                    app=app_name.title(),
                    instance=inst_name,
                    interval=cfg.search_interval,
                )

        # SAFETY-02: surface non-narrow-tuple exceptions that propagate out of
        # make_search_job (RuntimeError, KeyError, etc.) by routing them through
        # the EVENT_JOB_ERROR listener instead of APScheduler's silent default.
        scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
        scheduler.start()

        async def update_check_job() -> None:
            result = await check_for_update()
            if result is not None:
                app.state.update_info.update(result)
                if result["update_available"]:
                    logger.info("Update available: v{version}", version=result["latest_version"])

        scheduler.add_job(
            update_check_job,
            "interval",
            hours=24,
            id="update_check",
            next_run_time=datetime.now(UTC),
        )

        try:
            yield
        finally:
            # 1. Stop scheduler from scheduling new jobs (does NOT wait for async jobs)
            scheduler.shutdown(wait=False)

            # 2. Drain any in-flight search cycle before closing resources (DEBT-06)
            # RES-01 (Codex finding 3): log holder identity on entry to the drain
            # so the operator sees which instance is stuck even if Docker SIGKILLs
            # the process before the timeout fires. Then await with the
            # configurable timeout; log a structured WARNING on timeout.
            holder = getattr(app.state, "search_lock_holder", None)
            if holder:
                job_id, started = holder
                elapsed = time.monotonic() - started
                logger.info(
                    "Shutdown: draining search lock (timeout={t}s); holder={job} elapsed={e:.1f}s",
                    t=_SHUTDOWN_DRAIN_TIMEOUT,
                    job=job_id,
                    e=elapsed,
                )
            else:
                logger.info(
                    "Shutdown: draining search lock (timeout={t}s); no current holder",
                    t=_SHUTDOWN_DRAIN_TIMEOUT,
                )
            # WR-01: use `asyncio.timeout()` (Python 3.11+) instead of
            # `asyncio.wait_for(lock.acquire(), ...)`. The wait_for idiom
            # has a documented footgun: if it is *cancelled* (not timed
            # out), the underlying acquire() task may complete after
            # wait_for has unwound, leaving the lock acquired with no
            # matching release. Shutdown is exactly where a higher-level
            # cancel (uvicorn reload, test re-entry) is most likely to
            # interleave with this code path. `asyncio.timeout()` does
            # not have this race: the acquire() runs in the caller's
            # frame, so a cancel propagates as CancelledError before any
            # state is committed.
            acquired = False
            try:
                try:
                    async with asyncio.timeout(_SHUTDOWN_DRAIN_TIMEOUT):
                        await app.state.search_lock.acquire()
                        acquired = True
                except TimeoutError:
                    # Re-read holder defensively: a race could have cleared
                    # it if the cycle finished but a different caller
                    # reacquired the lock before our timeout hit zero.
                    holder = getattr(app.state, "search_lock_holder", None)
                    if holder:
                        job_id, started = holder
                        elapsed = time.monotonic() - started
                        logger.warning(
                            "Shutdown: search cycle did not finish in {timeout}s -- "
                            "job={job} elapsed={elapsed:.1f}s -- forcing close",
                            timeout=_SHUTDOWN_DRAIN_TIMEOUT,
                            job=job_id,
                            elapsed=elapsed,
                        )
                    else:
                        logger.warning(
                            "Shutdown: search lock did not drain in {timeout}s "
                            "(no holder recorded) -- forcing close",
                            timeout=_SHUTDOWN_DRAIN_TIMEOUT,
                        )
            finally:
                # WR-01: release only when acquire actually succeeded. A
                # bare `lock.release()` on an unlocked lock raises
                # RuntimeError and would crash the rest of the lifespan
                # shutdown (client close, db close).
                if acquired:
                    app.state.search_lock.release()

            # 3. Close HTTP clients (all instances)
            for app_type in APP_TYPES:
                for client in getattr(app.state, f"{app_type}_clients", {}).values():
                    await client.close()

            # 4. Close shared database connection (all writes complete per step 2)
            await app.state.db.close()

            logger.info("Search engine stopped")

    return lifespan
