"""APScheduler integration with FastAPI lifespan for automated search cycles.

Creates interval jobs for Radarr and Sonarr search cycles, managed through
FastAPI's lifespan context manager.  Shared state is exposed on ``app.state``
so that web routes can read it without coupling.  The ``make_search_job``
factory creates job closures that read from ``app.state`` rather than
capturing variables, enabling future hot-reload of clients and settings.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import httpx
import pydantic
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from loguru import logger

from triggarr.clients.base import ArrClient
from triggarr.clients.lidarr import LidarrClient
from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.db import init_db, migrate_from_state
from triggarr.models.config import APP_TYPES, Settings
from triggarr.search.engine import run_lidarr_cycle, run_radarr_cycle, run_sonarr_cycle
from triggarr.state import (
    TriggarrState,
    _default_instance_state,
    cleanup_orphaned_instances,
    load_state,
    save_state,
)
from triggarr.tracking import run_tracking_check
from triggarr.update_check import check_for_update


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
            try:
                app.state.triggarr_state = await cycle_fn(
                    client,
                    app.state.triggarr_state,
                    instance_name,
                    instance_config,
                    app.state.settings,
                    app.state.db,
                )
                await asyncio.get_running_loop().run_in_executor(
                    None, save_state, app.state.triggarr_state, state_path
                )
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
                except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as tracking_exc:
                    logger.warning(
                        "Tracking: check failed -- {exc}",
                        exc=tracking_exc,
                    )
            except Exception as exc:
                logger.error(
                    "{app}: Unhandled error in search cycle -- {exc}",
                    app=app_name.title(),
                    exc=exc,
                )

    return job


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
        app.state.last_search_time: dict[str, float] = {}
        app.state.last_health_check = None

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

    return lifespan
