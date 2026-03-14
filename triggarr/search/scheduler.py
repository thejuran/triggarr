"""APScheduler integration with FastAPI lifespan for automated search cycles.

Creates interval jobs for Radarr and Sonarr search cycles, managed through
FastAPI's lifespan context manager.  Shared state is exposed on ``app.state``
so that web routes can read it without coupling.  The ``make_search_job``
factory creates job closures that read from ``app.state`` rather than
capturing variables, enabling future hot-reload of clients and settings.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import httpx
import pydantic
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from loguru import logger

from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.db import init_db, migrate_from_state
from triggarr.models.config import Settings
from triggarr.search.engine import run_radarr_cycle, run_sonarr_cycle
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
) -> Callable[[], Coroutine]:
    """Create an async job function that reads client/state/settings from app.state.

    The returned closure reads all shared objects from ``app.state`` at
    execution time rather than capturing them at creation time.  This
    allows the config editor (Plan 03) to swap clients and settings
    without restarting the scheduler.

    Args:
        app: The FastAPI application instance.
        app_name: One of "radarr" or "sonarr".
        instance_name: Name of this instance (e.g., "Default", "4K").
        state_path: Path to the JSON state file for persistence.

    Returns:
        An async callable suitable for ``scheduler.add_job()``.
    """
    cycle_fn = run_radarr_cycle if app_name == "radarr" else run_sonarr_cycle

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
                save_state(app.state.triggarr_state, state_path)
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
                        + tracking_result["unresolved"]
                    )
                    if resolved > 0 or tracking_result["errors"] > 0:
                        logger.info(
                            "Tracking: {grabbed} grabbed, {partial} partial, "
                            "{unresolved} unresolved, {errors} errors",
                            grabbed=tracking_result["grabbed"],
                            partial=tracking_result["partial"],
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
        for app_type in ("radarr", "sonarr"):
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
                save_state(state, state_path)

        # --- Create long-lived clients for enabled instances ---
        radarr_clients: dict[str, RadarrClient] = {}
        sonarr_clients: dict[str, SonarrClient] = {}

        for inst_name, cfg in settings.get_enabled_instances("radarr").items():
            radarr_clients[inst_name] = RadarrClient(
                base_url=cfg.url,
                api_key=cfg.api_key.get_secret_value(),
                timeout=settings.general.request_timeout,
                page_size=settings.general.page_size,
            )

        for inst_name, cfg in settings.get_enabled_instances("sonarr").items():
            sonarr_clients[inst_name] = SonarrClient(
                base_url=cfg.url,
                api_key=cfg.api_key.get_secret_value(),
                timeout=settings.general.request_timeout,
                page_size=settings.general.page_size,
            )

        # --- Expose all shared state on app.state ---
        app.state.triggarr_state = state
        app.state.settings = settings
        app.state.db = db
        app.state.scheduler = scheduler
        app.state.radarr_clients = radarr_clients
        app.state.sonarr_clients = sonarr_clients
        app.state.config_path = config_path
        app.state.state_path = state_path
        app.state.search_lock = asyncio.Lock()
        app.state.last_search_time: dict[str, float] = {}

        # --- Schedule jobs for enabled instances using make_search_job ---
        for app_name in ("radarr", "sonarr"):
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

        async def update_check_job():
            from triggarr.web.routes import _update_info

            result = await check_for_update()
            if result is not None:
                _update_info.update(result)
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
            for client in app.state.radarr_clients.values():
                await client.close()
            for client in app.state.sonarr_clients.values():
                await client.close()

            # 4. Close shared database connection (all writes complete per step 2)
            await app.state.db.close()

            logger.info("Search engine stopped")

    return lifespan
