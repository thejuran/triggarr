"""Startup orchestration for Fetcharr.

Coordinates config loading, logging setup with secret redaction,
connection validation, and startup banner display.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from fetcharr import __version__
from fetcharr.clients.radarr import RadarrClient
from fetcharr.clients.sonarr import SonarrClient
from fetcharr.config import ensure_config
from fetcharr.logging import setup_logging
from fetcharr.models.config import CONFIG_PATH, Settings

LOCALHOST_PATTERNS = {"localhost", "127.0.0.1", "::1"}


def check_localhost_urls(settings: Settings) -> None:
    """Warn if any enabled app's URL points to localhost.

    Inside Docker, ``localhost`` refers to the container itself, not the
    host machine.  This is the most common networking mistake for new
    self-hosters.  The warning fires before connection validation so the
    user sees a clear explanation rather than a mysterious timeout.
    """
    for name in ("radarr", "sonarr"):
        cfg = getattr(settings, name)
        if not cfg.enabled:
            continue
        hostname = urlparse(cfg.url).hostname
        if hostname and hostname in LOCALHOST_PATTERNS:
            logger.warning(
                "{app} URL ({url}) uses localhost, which inside Docker "
                "refers to the container itself, not your host machine. "
                "Use 'host.docker.internal' (Docker Desktop) or the "
                "container/service name (e.g. 'http://{app_lower}:{port}') instead.",
                app=name.title(),
                url=cfg.url,
                app_lower=name,
                port="7878" if name == "radarr" else "8989",
            )


def collect_secrets(settings: Settings) -> list[str]:
    """Extract API key values from all configured apps.

    This is the ONLY place where ``get_secret_value()`` is called for
    logging purposes.  The returned list is passed to the redaction
    filter so secrets never appear in log output.

    Args:
        settings: Loaded application settings.

    Returns:
        List of non-empty secret strings for the redaction filter.
    """
    secrets: list[str] = []
    for app in (settings.radarr, settings.sonarr):
        value = app.api_key.get_secret_value()
        if value:
            secrets.append(value)
    return secrets


def print_banner(settings: Settings) -> None:
    """Log the startup banner showing version and configured apps.

    Displays the Fetcharr version, log level, and connection status
    for each *arr application (URL or "disabled").
    """
    radarr_status = settings.radarr.url if settings.radarr.enabled else "disabled"
    sonarr_status = settings.sonarr.url if settings.sonarr.enabled else "disabled"

    logger.info("==================================================")
    logger.info("Fetcharr v{version}", version=__version__)
    logger.info("Log level: {level}", level=settings.general.log_level)
    logger.info("Radarr: {status}", status=radarr_status)
    logger.info("Sonarr: {status}", status=sonarr_status)
    logger.info("==================================================")


async def validate_connections(settings: Settings) -> dict[str, bool]:
    """Validate connections to all enabled *arr applications.

    For each enabled app, creates a temporary client, calls
    ``validate_connection()``, and closes the client.  These clients
    are temporary -- the scheduler creates its own long-lived clients
    that persist for the lifetime of the application.

    Per locked decision: unreachable apps log a warning but do NOT
    cause the process to exit.

    Args:
        settings: Loaded application settings.

    Returns:
        Dict mapping app name to connection result (True/False).
        Only includes enabled apps.
    """
    results: dict[str, bool] = {}

    if settings.radarr.enabled:
        client = RadarrClient(
            base_url=settings.radarr.url,
            api_key=settings.radarr.api_key.get_secret_value(),
        )
        try:
            results["radarr"] = await client.validate_connection()
        finally:
            await client.close()

    if settings.sonarr.enabled:
        client = SonarrClient(
            base_url=settings.sonarr.url,
            api_key=settings.sonarr.api_key.get_secret_value(),
        )
        try:
            results["sonarr"] = await client.validate_connection()
            if results["sonarr"]:
                try:
                    api_version = await client.detect_api_version()
                    logger.info("Sonarr: Detected API {version}", version=api_version)
                except Exception:
                    logger.warning("Sonarr: API version detection failed -- assuming v3")
                    logger.info("Sonarr: Detected API {version}", version="v3")
        finally:
            await client.close()

    return results


async def startup(config_path: Path | None = None) -> Settings:
    """Run the full Fetcharr startup sequence.

    1. Load (or generate) configuration from TOML
    2. Collect API key secrets for log redaction
    3. Set up loguru logging with redaction filter
    4. Print startup banner
    5. Validate connections to enabled *arr apps
    6. Log connection summary

    Args:
        config_path: Optional path to config file.  Defaults to
            ``/config/fetcharr.toml`` in production; tests pass a
            temp directory path for isolation.

    Returns:
        Validated Settings instance for use by the rest of the app.
    """
    path = config_path or CONFIG_PATH

    # 1. Config loading (exits if missing, generating default template)
    settings = ensure_config(path)

    # 2. Collect secrets for redaction
    secrets = collect_secrets(settings)

    # 3. Set up logging with redaction
    setup_logging(settings.general.log_level, secrets)

    # 4. Print banner
    print_banner(settings)

    # 4.5 Warn if no apps configured (first-run scenario)
    if not settings.has_enabled_app:
        logger.warning(
            "No apps configured -- visit http://localhost:8080/settings to "
            "add your Radarr/Sonarr connection"
        )
        return settings

    # 4.6 Warn about localhost URLs (common Docker networking mistake)
    check_localhost_urls(settings)

    # 5. Validate connections
    results = await validate_connections(settings)

    # 6. Log summary
    for app_name, connected in results.items():
        if connected:
            logger.info("{app}: Connection validated", app=app_name.title())
        else:
            logger.warning("{app}: Connection failed -- will retry during search", app=app_name.title())

    return settings
