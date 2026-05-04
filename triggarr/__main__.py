"""Entry point for ``python -m triggarr``."""

from __future__ import annotations

import asyncio
import os

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger

from triggarr.models.config import get_config_path
from triggarr.search.scheduler import create_lifespan
from triggarr.state import get_state_path
from triggarr.web.middleware import AuthMiddleware, OriginCheckMiddleware, SecurityHeadersMiddleware
from triggarr.web.routes import STATIC_DIR, router


def get_root_path() -> str:
    """Return the root path for reverse proxy support.

    Reads the ROOT_PATH env var. Defaults to empty string (no prefix).
    """
    return os.environ.get("ROOT_PATH", "")


def get_trusted_proxy_ips() -> str:
    """Return trusted proxy IPs for uvicorn forwarded_allow_ips.

    Reads the TRUSTED_PROXY_IPS env var. Defaults to 127.0.0.1.
    """
    return os.environ.get("TRUSTED_PROXY_IPS", "127.0.0.1")


def main() -> None:
    """Run Triggarr: startup, scheduler, and HTTP server.

    Calls the async entry point which handles configuration loading,
    connection validation, and uvicorn serving with APScheduler-driven
    search cycles managed through the FastAPI lifespan.
    """
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Triggarr stopped by user")


async def _run() -> None:
    """Async entry point: startup then serve with lifespan-managed scheduler."""
    from triggarr.startup import startup

    config_path = get_config_path()
    state_path = get_state_path()
    settings = await startup(config_path)

    root_path = get_root_path()
    if root_path:
        logger.info("Root path: {path}", path=root_path)

    trusted = get_trusted_proxy_ips()
    if trusted == "*":
        logger.warning(
            "TRUSTED_PROXY_IPS=* trusts ALL proxies — only use this if Triggarr is "
            "behind a controlled reverse proxy with no direct external access"
        )

    app = FastAPI(lifespan=create_lifespan(settings, state_path, config_path))
    app.add_middleware(SecurityHeadersMiddleware)   # runs 3rd (response headers)
    app.add_middleware(OriginCheckMiddleware)        # runs 2nd (CSRF)
    app.add_middleware(AuthMiddleware)               # runs 1st (auth gate) -- MUST BE LAST
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8484,
        log_level="warning",
        root_path=root_path,
        proxy_headers=True,
        forwarded_allow_ips=get_trusted_proxy_ips(),
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    main()
