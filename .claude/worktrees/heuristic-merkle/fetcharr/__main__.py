"""Entry point for ``python -m fetcharr``."""

from __future__ import annotations

import asyncio

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger

from fetcharr.models.config import CONFIG_PATH
from fetcharr.search.scheduler import create_lifespan
from fetcharr.state import STATE_PATH
from fetcharr.web.middleware import OriginCheckMiddleware
from fetcharr.web.routes import STATIC_DIR, router


def main() -> None:
    """Run Fetcharr: startup, scheduler, and HTTP server.

    Calls the async entry point which handles configuration loading,
    connection validation, and uvicorn serving with APScheduler-driven
    search cycles managed through the FastAPI lifespan.
    """
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Fetcharr stopped by user")


async def _run() -> None:
    """Async entry point: startup then serve with lifespan-managed scheduler."""
    from fetcharr.startup import startup

    settings = await startup()

    app = FastAPI(lifespan=create_lifespan(settings, STATE_PATH, CONFIG_PATH))
    app.add_middleware(OriginCheckMiddleware)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    main()
