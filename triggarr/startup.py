"""Startup orchestration for Triggarr.

Coordinates config loading, logging setup with secret redaction,
connection validation, and startup banner display.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from triggarr.clients.base import ArrClient
from triggarr.clients.lidarr import LidarrClient
from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.config import ensure_config
from triggarr.logging import setup_logging
from triggarr.models.config import APP_TYPES, Settings, get_config_path

LOCALHOST_PATTERNS = {"localhost", "127.0.0.1", "::1"}


def check_localhost_urls(settings: Settings) -> None:
    """Warn if any enabled instance's URL points to localhost.

    Inside Docker, ``localhost`` refers to the container itself, not the
    host machine.  This is the most common networking mistake for new
    self-hosters.  The warning fires before connection validation so the
    user sees a clear explanation rather than a mysterious timeout.
    """
    for name in APP_TYPES:
        for _inst, cfg in settings.get_enabled_instances(name).items():
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
                    port={"radarr": "7878", "sonarr": "8989", "lidarr": "8686"}.get(name, "8686"),
                )


def collect_secrets(settings: Settings) -> list[str]:
    """Extract API key values from all configured instances and auth secrets.

    This is the ONLY place where ``get_secret_value()`` is called for
    logging purposes.  The returned list is passed to the redaction
    filter so secrets never appear in log output.

    Args:
        settings: Loaded application settings.

    Returns:
        List of non-empty secret strings for the redaction filter.
    """
    secrets: list[str] = []
    for app_type in APP_TYPES:
        for cfg in getattr(settings, app_type).values():
            value = cfg.api_key.get_secret_value()
            if value:
                secrets.append(value)

    # Auth secrets (D-07: password_hash, api_key, session_secret)
    for field in (settings.auth.password_hash, settings.auth.api_key, settings.auth.session_secret):
        value = field.get_secret_value()
        if value:
            secrets.append(value)

    return secrets


def print_banner(settings: Settings) -> None:
    """Log the startup banner showing version and configured instances.

    Displays the Triggarr version, log level, and connection status
    for each *arr instance (URL or "disabled").
    """
    logger.info("==================================================")
    from triggarr.version import get_display_version

    logger.info("Triggarr {version}", version=get_display_version())
    logger.info("Log level: {level}", level=settings.general.log_level)
    for app_type in APP_TYPES:
        instances = getattr(settings, app_type)
        if not instances:
            logger.info("{app}: disabled", app=app_type.title())
        else:
            for inst_name, cfg in instances.items():
                status = cfg.url if cfg.enabled else "disabled"
                logger.info("{app}/{inst}: {status}", app=app_type.title(), inst=inst_name, status=status)
    logger.info("==================================================")


async def validate_connections(settings: Settings) -> dict[str, bool]:
    """Validate connections to all enabled *arr instances.

    For each enabled instance, creates a temporary client, calls
    ``validate_connection()``, and closes the client.  These clients
    are temporary -- the scheduler creates its own long-lived clients
    that persist for the lifetime of the application.

    Per locked decision: unreachable apps log a warning but do NOT
    cause the process to exit.

    Args:
        settings: Loaded application settings.

    Returns:
        Dict mapping app name to connection result (True/False).
        Only includes enabled apps (uses first enabled instance per type).
    """
    results: dict[str, bool] = {}

    # Build client class lookup from current module namespace so test patches
    # to RadarrClient / SonarrClient / LidarrClient are respected.
    client_classes: dict[str, type[ArrClient]] = {
        "radarr": RadarrClient, "sonarr": SonarrClient, "lidarr": LidarrClient,
    }

    for app_type in APP_TYPES:
        cls = client_classes[app_type]
        for inst_name, cfg in settings.get_enabled_instances(app_type).items():
            client = cls(
                base_url=cfg.url,
                api_key=cfg.api_key.get_secret_value(),
            )
            try:
                key = f"{app_type}/{inst_name}"
                results[key] = await client.validate_connection()
                # Sonarr-specific: detect API version for logging
                if results[key] and app_type == "sonarr" and hasattr(client, "detect_api_version"):
                    api_version = await client.detect_api_version()
                    logger.info("Sonarr: Detected API {version}", version=api_version)
            finally:
                await client.close()

    return results


async def startup(config_path: Path | None = None) -> Settings:
    """Run the full Triggarr startup sequence.

    1. Load (or generate) configuration from TOML
    2. Collect API key secrets for log redaction
    3. Set up loguru logging with redaction filter
    4. Print startup banner
    5. Validate connections to enabled *arr apps
    6. Log connection summary

    Args:
        config_path: Optional path to config file.  Defaults to
            ``/config/triggarr.toml`` in production; tests pass a
            temp directory path for isolation.

    Returns:
        Validated Settings instance for use by the rest of the app.
    """
    path = config_path or get_config_path()

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
            "No apps configured -- visit http://localhost:8484/settings to "
            "add your Radarr/Sonarr connection"
        )
        return settings

    # 4.6 Warn about localhost URLs (common Docker networking mistake)
    check_localhost_urls(settings)

    # 5. Validate connections
    results = await validate_connections(settings)

    # 6. Log summary
    for key, connected in results.items():
        app_label = key.replace("/", " ").title()
        if connected:
            logger.info("{app}: Connection validated", app=app_label)
        else:
            logger.warning("{app}: Connection failed -- will retry during search", app=app_label)

    return settings
