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
from triggarr.state import TriggarrState, load_state, save_state
from triggarr.tracking import run_tracking_check


def make_search_job(
    app: FastAPI, app_name: str, state_path: Path
) -> Callable[[], Coroutine]:
    """Create an async job function that reads client/state/settings from app.state.

    The returned closure reads all shared objects from ``app.state`` at
    execution time rather than capturing them at creation time.  This
    allows the config editor (Plan 03) to swap clients and settings
    without restarting the scheduler.

    Args:
        app: The FastAPI application instance.
        app_name: One of "radarr" or "sonarr".
        state_path: Path to the JSON state file for persistence.

    Returns:
        An async callable suitable for ``scheduler.add_job()``.
    """
    cycle_fn = run_radarr_cycle if app_name == "radarr" else run_sonarr_cycle

    async def job() -> None:
        client = getattr(app.state, f"{app_name}_client", None)
        if client is None:
            return
        async with app.state.search_lock:
            try:
                app.state.triggarr_state = await cycle_fn(
                    client,
                    app.state.triggarr_state,
                    app.state.settings,
                    app.state.db,
                )
                save_state(app.state.triggarr_state, state_path)
                # --- Tracking check: resolve pending search outcomes ---
                try:
                    tracking_result = await run_tracking_check(
                        app.state.db,
                        getattr(app.state, "radarr_client", None),
                        getattr(app.state, "sonarr_client", None),
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

        radarr_client: RadarrClient | None = None
        sonarr_client: SonarrClient | None = None

        # --- Create long-lived clients for enabled apps ---
        if settings.radarr.enabled:
            radarr_client = RadarrClient(
                base_url=settings.radarr.url,
                api_key=settings.radarr.api_key.get_secret_value(),
                timeout=settings.general.request_timeout,
                page_size=settings.general.page_size,
            )

        if settings.sonarr.enabled:
            sonarr_client = SonarrClient(
                base_url=settings.sonarr.url,
                api_key=settings.sonarr.api_key.get_secret_value(),
                timeout=settings.general.request_timeout,
                page_size=settings.general.page_size,
            )

        # --- Expose all shared state on app.state ---
        app.state.triggarr_state = state
        app.state.settings = settings
        app.state.db = db
        app.state.scheduler = scheduler
        app.state.radarr_client = radarr_client
        app.state.sonarr_client = sonarr_client
        app.state.config_path = config_path
        app.state.state_path = state_path
        app.state.search_lock = asyncio.Lock()
        app.state.last_search_time: dict[str, float] = {}

        # --- Schedule jobs for enabled apps using make_search_job ---
        for name in ("radarr", "sonarr"):
            app_config = getattr(settings, name)
            if app_config.enabled:
                job_fn = make_search_job(app, name, state_path)
                scheduler.add_job(
                    job_fn,
                    "interval",
                    minutes=app_config.search_interval,
                    id=f"{name}_search",
                    next_run_time=datetime.now(UTC),
                )
                logger.info(
                    "Scheduled {app} search every {interval}m (first run: now)",
                    app=name.title(),
                    interval=app_config.search_interval,
                )

        scheduler.start()

        try:
            yield
        finally:
            # 1. Stop scheduler from scheduling new jobs (does NOT wait for async jobs)
            scheduler.shutdown(wait=False)

            # 2. Drain any in-flight search cycle before closing resources (DEBT-06)
            # AsyncIOScheduler.shutdown(wait=True) only waits on ThreadPoolExecutor,
            # not async jobs.  search_lock is the correct synchronization primitive
            # for this codebase's async cycles.
            try:
                await asyncio.wait_for(app.state.search_lock.acquire(), timeout=35.0)
                app.state.search_lock.release()
            except TimeoutError:
                logger.warning("Shutdown: search cycle did not finish in 35s — forcing close")

            # 3. Close HTTP clients (app.state versions — may have been replaced by config editor)
            for name in ("radarr", "sonarr"):
                client = getattr(app.state, f"{name}_client", None)
                if client:
                    await client.close()

            # 4. Close shared database connection (all writes complete per step 2)
            await app.state.db.close()

            logger.info("Search engine stopped")

    return lifespan
