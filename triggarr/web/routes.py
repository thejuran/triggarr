"""Web UI routes for Triggarr dashboard and settings.

Provides the main dashboard page with htmx-polling app cards and search log,
a config editor with masked API keys and hot-reload, a search-now trigger,
and partial endpoints for htmx fragment updates.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import pydantic
import tomli_w
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.db import get_dashboard_stats, get_recent_searches, get_search_history
from triggarr.log_buffer import log_buffer
from triggarr.logging import setup_logging
from triggarr.models.config import Settings as SettingsModel
from triggarr.search.engine import run_radarr_cycle, run_sonarr_cycle
from triggarr.search.scheduler import make_search_job
from triggarr.startup import collect_secrets
from triggarr.state import save_state
from triggarr.web.validation import safe_int, safe_log_level, validate_arr_url

_PKG_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = _PKG_DIR / "templates"
STATIC_DIR = _PKG_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter()

SEARCH_RATE_LIMIT_SECONDS = 10


def _format_duration(seconds: float | None) -> str:
    """Format a duration in seconds as a human-readable string.

    Args:
        seconds: Duration in seconds, or None if no data.

    Returns:
        "---" if None, "< 1m" if < 60, "{X}m" if < 3600, "{X}h {Y}m" otherwise.
    """
    if seconds is None:
        return "---"
    if seconds < 60:
        return "< 1m"
    minutes = int(seconds // 60)
    if seconds < 3600:
        return f"{minutes}m"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    return f"{hours}h {remaining_minutes}m"


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    """Health probe for container orchestrators.

    Returns 200 when all enabled instances are reachable (connected=True),
    503 when any enabled instance is unreachable or not yet verified.
    If no apps are enabled, returns 200 (valid configuration, waiting for setup).
    """
    settings = request.app.state.settings
    state = request.app.state.triggarr_state
    problems: list[str] = []

    for app_name in ("radarr", "sonarr"):
        for inst_name, _cfg in settings.get_enabled_instances(app_name).items():
            inst_state = state.get(app_name, {}).get(inst_name, {})
            connected = inst_state.get("connected")
            if connected is not True:  # None (never run) or False (unreachable) -> unhealthy
                problems.append(app_name)

    if problems:
        return JSONResponse(
            {"status": "unhealthy", "unreachable": problems},
            status_code=503,
        )
    return JSONResponse({"status": "ok"})


def _build_app_context(request: Request, app_name: str) -> dict | None:
    """Build a template context dict for a single app.

    Returns None if the app has no enabled instances. For multi-instance
    configs, shows the first enabled instance's state (Phase 39 adds
    full multi-instance dashboard).

    Args:
        request: The incoming FastAPI request (used to access app.state).
        app_name: One of "radarr" or "sonarr".

    Returns:
        Dict with name, last_run, next_run, missing_cursor, cutoff_cursor
        or None if app is not enabled.
    """
    settings = request.app.state.settings
    enabled = settings.get_enabled_instances(app_name)
    if not enabled:
        return None

    # Use first enabled instance for dashboard display (Phase 39: multi-instance UI)
    first_instance_name = next(iter(enabled))

    state = request.app.state.triggarr_state
    app_state = state.get(app_name, {}).get(first_instance_name, {})

    # Determine next_run from scheduler job (per-instance job ID)
    next_run = None
    scheduler = request.app.state.scheduler
    job = scheduler.get_job(f"{app_name}_{first_instance_name}_search")
    if job and job.next_run_time:
        next_run = job.next_run_time.isoformat()

    return {
        "name": app_name,
        "last_run": app_state.get("last_run"),
        "next_run": next_run,
        "missing_cursor": app_state.get("missing_cursor", 0),
        "cutoff_cursor": app_state.get("cutoff_cursor", 0),
        "missing_pass": app_state.get("missing_pass", 0),
        "cutoff_pass": app_state.get("cutoff_pass", 0),
        "connected": app_state.get("connected"),
        "unreachable_since": app_state.get("unreachable_since"),
        "missing_count": app_state.get("missing_count"),
        "missing_eligible": app_state.get("missing_eligible"),
        "missing_monitored": app_state.get("missing_monitored"),
        "missing_searchable": app_state.get("missing_searchable"),
        "cutoff_count": app_state.get("cutoff_count"),
        "cutoff_searchable": app_state.get("cutoff_searchable"),
        "skip_unreleased": settings.general.skip_unreleased,
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render the dashboard page with app status cards and search log."""
    apps: list[dict] = []
    for name in ("radarr", "sonarr"):
        ctx = _build_app_context(request, name)
        if ctx is not None:
            apps.append(ctx)

    search_log = await get_recent_searches(request.app.state.db)
    log_entries = log_buffer.get_recent(30)
    stats = await get_dashboard_stats(request.app.state.db)
    time_to_grab = _format_duration(stats["avg_time_to_grab_seconds"])

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "apps": apps,
            "search_log": search_log,
            "log_entries": log_entries,
            "stats": stats,
            "time_to_grab": time_to_grab,
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    """Render the settings page with pre-filled form and masked API keys.

    For now, shows the first instance per app type (Phase 39 adds
    multi-instance settings UI).
    """
    settings = request.app.state.settings
    apps = {}
    for name in ("radarr", "sonarr"):
        instances = getattr(settings, name)
        if instances:
            # Show first instance for settings form (Phase 39: multi-instance editing)
            first_name = next(iter(instances))
            cfg = instances[first_name]
        else:
            # No instances configured -- show empty defaults
            from triggarr.models.config import InstanceConfig
            cfg = InstanceConfig()
        apps[name] = {
            "url": cfg.url,
            "has_api_key": bool(cfg.api_key.get_secret_value()),
            "enabled": cfg.enabled,
            "search_interval": cfg.search_interval,
            "search_missing_count": cfg.search_missing_count,
            "search_cutoff_count": cfg.search_cutoff_count,
        }
    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "apps": apps,
            "log_level": settings.general.log_level,
            "hard_max_per_cycle": settings.general.hard_max_per_cycle,
            "max_history_rows": settings.general.max_history_rows,
            "request_timeout": settings.general.request_timeout,
            "page_size": settings.general.page_size,
            "tracking_window_minutes": settings.general.tracking_window_minutes,
            "tracking_delay_seconds": settings.general.tracking_delay_seconds,
            "skip_unreleased": settings.general.skip_unreleased,
        },
    )


@router.get("/history", response_class=HTMLResponse)
async def history_page(request: Request) -> HTMLResponse:
    """Render the search history page with full filtering and pagination."""
    result = await get_search_history(request.app.state.db)
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "result": result,
            "active_apps": [],
            "active_queues": [],
            "active_outcomes": [],
            "search_text": "",
        },
    )


def _split_filter_param(value: str | None) -> list[str] | None:
    """Split a comma-separated query param into a list, or None if empty.

    Args:
        value: Raw query param string (e.g. "Radarr,Sonarr").

    Returns:
        List of non-empty strings, or None if value is absent/empty.
    """
    if not value:
        return None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts or None


@router.get("/partials/history-results", response_class=HTMLResponse)
async def partial_history_results(request: Request) -> HTMLResponse:
    """Return the history results partial with filter and pagination support."""
    params = request.query_params
    page = safe_int(params.get("page"), default=1, minimum=1, maximum=10_000)
    app_filter = _split_filter_param(params.get("app"))
    queue_filter = _split_filter_param(params.get("queue"))
    outcome_filter = _split_filter_param(params.get("outcome"))
    search_text = params.get("search", "")

    result = await get_search_history(
        request.app.state.db,
        page=page,
        app_filter=app_filter,
        queue_filter=queue_filter,
        outcome_filter=outcome_filter,
        search_text=search_text,
    )

    return templates.TemplateResponse(
        request=request,
        name="partials/history_results.html",
        context={
            "result": result,
            "active_apps": app_filter or [],
            "active_queues": queue_filter or [],
            "active_outcomes": outcome_filter or [],
            "search_text": search_text,
        },
    )


@router.post("/settings")
async def save_settings(request: Request) -> RedirectResponse:
    """Save settings from form data: write TOML, reload, update scheduler."""
    form = await request.form()
    current_settings = request.app.state.settings
    config_path = request.app.state.config_path
    state_path = request.app.state.state_path
    scheduler = request.app.state.scheduler

    # Build new config dict from form data
    new_config: dict = {
        "general": {
            "log_level": safe_log_level(form.get("log_level")),
            "hard_max_per_cycle": safe_int(form.get("hard_max_per_cycle"), 0, 0, 1000),
            "max_history_rows": safe_int(form.get("max_history_rows"), 1000, 0, 100_000),
            "request_timeout": safe_int(form.get("request_timeout"), 30, 5, 300),
            "page_size": safe_int(form.get("page_size"), 50, 10, 500),
            "tracking_window_minutes": safe_int(form.get("tracking_window_minutes"), 60, 5, 1440),
            "tracking_delay_seconds": current_settings.general.tracking_delay_seconds,
            "skip_unreleased": form.get("skip_unreleased") == "on",
        },
    }

    for name in ("radarr", "sonarr"):
        # Get first existing instance's config for key preservation
        current_instances = getattr(current_settings, name)
        if current_instances:
            first_inst_name = next(iter(current_instances))
            current_cfg = current_instances[first_inst_name]
        else:
            from triggarr.models.config import InstanceConfig
            first_inst_name = "Default"
            current_cfg = InstanceConfig()

        submitted_key = form.get(f"{name}_api_key", "").strip()

        # Validate URL before accepting it
        url = form.get(f"{name}_url", "").strip()
        valid, err = validate_arr_url(url)
        if not valid:
            logger.warning("{name}: URL rejected -- {err}", name=name.title(), err=err)
            return RedirectResponse(url=request.url_for("settings_page"), status_code=303)

        # Save as single instance under existing name (Phase 39: multi-instance editing)
        new_config[name] = {
            first_inst_name: {
                "url": url,
                "api_key": submitted_key if submitted_key else current_cfg.api_key.get_secret_value(),
                "enabled": form.get(f"{name}_enabled") == "on",
                "search_interval": safe_int(form.get(f"{name}_search_interval"), 30, 1, 1440),
                "search_missing_count": safe_int(form.get(f"{name}_search_missing_count"), 5, 0, 100),
                "search_cutoff_count": safe_int(form.get(f"{name}_search_cutoff_count"), 5, 0, 100),
            },
        }

    # Validate BEFORE writing to disk (QUAL-02)
    try:
        new_settings = SettingsModel(**new_config)
    except pydantic.ValidationError as exc:
        logger.warning("Invalid settings rejected: {exc}", exc=exc)
        return RedirectResponse(url=request.url_for("settings_page"), status_code=303)

    # Config is valid -- write to disk
    content = tomli_w.dumps(new_config)
    with tempfile.NamedTemporaryFile(mode="w", dir=config_path.parent, suffix=".tmp", delete=False) as tmp:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
    try:
        os.replace(tmp.name, str(config_path))
    except OSError:
        with contextlib.suppress(OSError):
            os.unlink(tmp.name)
        raise
    os.chmod(config_path, 0o600)
    request.app.state.settings = new_settings

    # Refresh log redaction with new secrets (QUAL-05)
    secrets = collect_secrets(new_settings)
    setup_logging(new_settings.general.log_level, secrets)

    # Handle scheduler updates for each app's instances
    for name in ("radarr", "sonarr"):
        new_instances = getattr(new_settings, name)
        old_instances = getattr(current_settings, name)
        clients_dict = getattr(request.app.state, f"{name}_clients", {})
        ClientClass = RadarrClient if name == "radarr" else SonarrClient

        # Close clients for removed/disabled instances
        for inst_name in list(clients_dict.keys()):
            new_cfg = new_instances.get(inst_name)
            if new_cfg is None or not new_cfg.enabled:
                job_id = f"{name}_{inst_name}_search"
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)
                client = clients_dict.pop(inst_name, None)
                if client:
                    await client.close()

        # Update/create clients for enabled instances
        for inst_name, new_cfg in new_instances.items():
            if not new_cfg.enabled:
                continue
            job_id = f"{name}_{inst_name}_search"
            old_cfg = old_instances.get(inst_name)

            # Check if client needs recreation
            url_changed = old_cfg is None or new_cfg.url != old_cfg.url
            key_changed = old_cfg is None or (
                new_cfg.api_key.get_secret_value()
                != old_cfg.api_key.get_secret_value()
            )

            if url_changed or key_changed or inst_name not in clients_dict:
                old_client = clients_dict.pop(inst_name, None)
                if old_client:
                    await old_client.close()
                clients_dict[inst_name] = ClientClass(
                    base_url=new_cfg.url,
                    api_key=new_cfg.api_key.get_secret_value(),
                    timeout=new_settings.general.request_timeout,
                    page_size=new_settings.general.page_size,
                )

            existing_job = scheduler.get_job(job_id)
            if existing_job:
                scheduler.reschedule_job(
                    job_id,
                    trigger="interval",
                    minutes=new_cfg.search_interval,
                )
            else:
                job_fn = make_search_job(request.app, name, inst_name, state_path)
                scheduler.add_job(
                    job_fn,
                    "interval",
                    minutes=new_cfg.search_interval,
                    id=job_id,
                    next_run_time=datetime.now(UTC),
                )
                logger.info(
                    "Enabled {name}/{inst} search every {interval}m",
                    name=name.title(),
                    inst=inst_name,
                    interval=new_cfg.search_interval,
                )

        setattr(request.app.state, f"{name}_clients", clients_dict)

    return RedirectResponse(url=request.url_for("settings_page"), status_code=303)


@router.post("/api/search-now/{app_name}", response_class=HTMLResponse)
async def search_now(request: Request, app_name: str) -> HTMLResponse:
    """Trigger an immediate search cycle for the given app and return updated card.

    Runs the cycle for the first enabled instance (Phase 39 adds
    per-instance search-now).
    """
    if app_name not in ("radarr", "sonarr"):
        return HTMLResponse("Invalid app", status_code=400)

    # Get first enabled instance's client
    clients = getattr(request.app.state, f"{app_name}_clients", {})
    enabled = request.app.state.settings.get_enabled_instances(app_name)
    if not enabled or not clients:
        return HTMLResponse("App not enabled", status_code=400)
    instance_name = next(iter(enabled))
    client = clients.get(instance_name)
    if client is None:
        return HTMLResponse("App not enabled", status_code=400)
    instance_config = enabled[instance_name]

    # Optimistic rate limit check BEFORE lock (fast-fail for obvious cases)
    now = time.monotonic()
    last = request.app.state.last_search_time.get(app_name, 0.0)
    if now - last < SEARCH_RATE_LIMIT_SECONDS:
        logger.info("{name}: Manual search rate-limited", name=app_name.title())
        return HTMLResponse("Rate limited — try again shortly", status_code=429)

    cycle_fn = run_radarr_cycle if app_name == "radarr" else run_sonarr_cycle
    async with request.app.state.search_lock:
        # Re-check inside lock to prevent concurrent bypass (DRSEC-03)
        now = time.monotonic()
        last = request.app.state.last_search_time.get(app_name, 0.0)
        if now - last < SEARCH_RATE_LIMIT_SECONDS:
            logger.info("{name}: Manual search rate-limited (after lock)", name=app_name.title())
            return HTMLResponse("Rate limited — try again shortly", status_code=429)
        request.app.state.last_search_time[app_name] = now

        try:
            request.app.state.triggarr_state = await cycle_fn(
                client,
                request.app.state.triggarr_state,
                instance_name,
                instance_config,
                request.app.state.settings,
                request.app.state.db,
            )
            save_state(
                request.app.state.triggarr_state,
                request.app.state.state_path,
            )
            logger.info("{name}: Manual search triggered", name=app_name.title())
        except Exception as exc:
            logger.error(
                "{name}: Manual search failed -- {exc}",
                name=app_name.title(),
                exc=exc,
            )

    # Return updated card partial
    app_data = _build_app_context(request, app_name)
    return templates.TemplateResponse(
        request=request,
        name="partials/app_card.html",
        context={"app": app_data},
    )


@router.get("/partials/app-card/{app_name}", response_class=HTMLResponse)
async def partial_app_card(request: Request, app_name: str) -> HTMLResponse:
    """Return an HTML fragment for a single app status card (htmx partial)."""
    app_data = _build_app_context(request, app_name)
    if app_data is None:
        return HTMLResponse("")

    return templates.TemplateResponse(
        request=request,
        name="partials/app_card.html",
        context={"app": app_data},
    )


@router.get("/partials/search-log", response_class=HTMLResponse)
async def partial_search_log(request: Request) -> HTMLResponse:
    """Return an HTML fragment for the search log (htmx partial)."""
    search_log = await get_recent_searches(request.app.state.db)

    return templates.TemplateResponse(
        request=request,
        name="partials/search_log.html",
        context={"search_log": search_log},
    )


@router.get("/partials/stats-row", response_class=HTMLResponse)
async def partial_stats_row(request: Request) -> HTMLResponse:
    """Return an HTML fragment for the dashboard stats row (htmx partial)."""
    stats = await get_dashboard_stats(request.app.state.db)
    time_to_grab = _format_duration(stats["avg_time_to_grab_seconds"])
    return templates.TemplateResponse(
        request=request,
        name="partials/stats_row.html",
        context={"stats": stats, "time_to_grab": time_to_grab},
    )


@router.get("/partials/log-viewer", response_class=HTMLResponse)
async def partial_log_viewer(request: Request) -> HTMLResponse:
    """Return an HTML fragment for the application log viewer (htmx partial)."""
    log_entries = log_buffer.get_recent(30)
    return templates.TemplateResponse(
        request=request,
        name="partials/log_viewer.html",
        context={"log_entries": log_entries},
    )
