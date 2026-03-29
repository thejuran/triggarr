"""Web UI routes for Triggarr dashboard and settings.

Provides the main dashboard page with htmx-polling app cards and search log,
a config editor with masked API keys and hot-reload, a search-now trigger,
and partial endpoints for htmx fragment updates.
"""

from __future__ import annotations

import asyncio
import html
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import httpx
import pydantic
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.config import _atomic_toml_write
from triggarr.db import get_dashboard_stats, get_recent_searches, get_search_history
from triggarr.log_buffer import log_buffer
from triggarr.logging import setup_logging
from triggarr.models.config import CONFIG_DIR
from triggarr.models.config import Settings as SettingsModel
from triggarr.search.engine import run_radarr_cycle, run_sonarr_cycle
from triggarr.search.scheduler import make_search_job
from triggarr.startup import collect_secrets
from triggarr.state import save_state
from triggarr.version import get_display_version
from triggarr.web.validation import safe_int, safe_log_level, validate_arr_url, validate_instance_name

_PKG_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = _PKG_DIR / "templates"
STATIC_DIR = _PKG_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR), autoescape=True)
templates.env.globals["triggarr_version"] = get_display_version()
# Shared mutable dict for update info. The scheduler lifespan assigns this
# same object to app.state.update_info so both sides share it without
# the scheduler needing to import from routes.
update_info: dict = {}
templates.env.globals["update_info"] = update_info
router = APIRouter()

SEARCH_RATE_LIMIT_SECONDS = 10

# Regex for multi-instance form field names: {app}__{instance}__{field}


def _sanitize_card_id(raw: str) -> str:
    """Sanitize a string for use as an HTML id / CSS selector target.

    Replaces any character that is not alphanumeric, hyphen, or underscore
    with a hyphen.  This prevents CSS selector injection when instance names
    contain dots, hashes, spaces, or other special characters.

    Args:
        raw: Raw string (e.g. "radarr-My.Instance#1").

    Returns:
        Sanitized string safe for use as an HTML id attribute.
    """
    return re.sub(r"[^a-zA-Z0-9_-]", "-", raw)


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


def _settings_to_dict(settings: SettingsModel) -> dict:
    """Convert Settings to a plain dict suitable for TOML serialization.

    Extracts SecretStr values so they serialize as plain strings.
    """
    result: dict = {"general": settings.general.model_dump()}
    for app_name in ("radarr", "sonarr"):
        instances = getattr(settings, app_name)
        result[app_name] = {}
        for inst_name, cfg in instances.items():
            d = cfg.model_dump()
            d["api_key"] = cfg.api_key.get_secret_value()
            result[app_name][inst_name] = d
    return result


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


def _build_app_context(request: Request, app_name: str, instance_name: str | None = None) -> dict | None:
    """Build a template context dict for a single app instance.

    Args:
        request: The incoming FastAPI request (used to access app.state).
        app_name: One of "radarr" or "sonarr".
        instance_name: Specific instance name. If None, uses first enabled.

    Returns:
        Dict with name, instance, last_run, next_run, missing_cursor, cutoff_cursor
        or None if app/instance is not enabled.
    """
    settings = request.app.state.settings
    enabled = settings.get_enabled_instances(app_name)
    if not enabled:
        return None

    if instance_name is None:
        instance_name = next(iter(enabled))
    elif instance_name not in enabled:
        return None

    state = request.app.state.triggarr_state
    app_state = state.get(app_name, {}).get(instance_name, {})

    # Determine next_run from scheduler job (per-instance job ID)
    next_run = None
    scheduler = request.app.state.scheduler
    job = scheduler.get_job(f"{app_name}_{instance_name}_search")
    if job and job.next_run_time:
        next_run = job.next_run_time.isoformat()

    return {
        "name": app_name,
        "instance": instance_name,
        "card_id": _sanitize_card_id(f"{app_name}-{instance_name}"),
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
        "total_items": app_state.get("total_items"),
        "skip_unreleased": settings.general.skip_unreleased,
        "tag_warnings": app_state.get("tag_warnings", []),
    }


def _build_health_summary(request: Request) -> dict:
    """Compute health summary counts from enabled instances in triggarr_state.

    Args:
        request: The incoming FastAPI request (used to access app.state).

    Returns:
        Dict with connected, disconnected, pending, and total counts.
    """
    settings = request.app.state.settings
    state = request.app.state.triggarr_state
    connected = 0
    disconnected = 0
    pending = 0

    for app_name in ("radarr", "sonarr"):
        for inst_name in settings.get_enabled_instances(app_name):
            ist = state.get(app_name, {}).get(inst_name, {})
            conn = ist.get("connected")
            if conn is True:
                connected += 1
            elif conn is False:
                disconnected += 1
            else:
                pending += 1

    return {
        "connected": connected,
        "disconnected": disconnected,
        "pending": pending,
        "total": connected + disconnected + pending,
    }


def _build_all_instances(settings: SettingsModel) -> list[dict]:
    """Build a list of enabled instances for dropdown filters.

    Args:
        settings: Application settings.

    Returns:
        List of dicts with value and label keys for each enabled instance.
    """
    instances: list[dict] = []
    for app_name in ("radarr", "sonarr"):
        for inst_name in settings.get_enabled_instances(app_name):
            instances.append({
                "value": f"{app_name}/{inst_name}",
                "label": f"{app_name.title()} / {inst_name}",
            })
    return instances


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render the dashboard page with per-instance status cards and search log."""
    apps: list[dict] = []
    settings = request.app.state.settings
    for app_name in ("radarr", "sonarr"):
        for inst_name in settings.get_enabled_instances(app_name):
            ctx = _build_app_context(request, app_name, inst_name)
            if ctx is not None:
                apps.append(ctx)

    search_log = await get_recent_searches(request.app.state.db)
    log_entries = log_buffer.get_recent(30)
    stats = await get_dashboard_stats(request.app.state.db)
    time_to_grab = _format_duration(stats["avg_time_to_grab_seconds"])
    health = _build_health_summary(request)
    all_instances = _build_all_instances(settings)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "apps": apps,
            "search_log": search_log,
            "log_entries": log_entries,
            "stats": stats,
            "time_to_grab": time_to_grab,
            "health": health,
            "all_instances": all_instances,
            "selected_instance": "",
            "instance_app_type": None,
            "show_migration_banner": (CONFIG_DIR / ".migrated").exists(),
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    """Render the settings page with all instances per app type and masked API keys."""
    settings = request.app.state.settings
    apps: dict[str, dict] = {}
    for name in ("radarr", "sonarr"):
        instances = getattr(settings, name)
        apps[name] = {}
        for inst_name, cfg in instances.items():
            apps[name][inst_name] = {
                "url": cfg.url,
                "has_api_key": bool(cfg.api_key),
                "enabled": cfg.enabled,
                "search_interval": cfg.search_interval,
                "search_missing_count": cfg.search_missing_count,
                "search_cutoff_count": cfg.search_cutoff_count,
                "missing_tag": cfg.missing_tag,
                "cutoff_tag": cfg.cutoff_tag,
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
            "active_instances": [],
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
    instance_filter = _split_filter_param(params.get("instance"))
    if instance_filter:
        instance_filter = instance_filter[:10]
        # Strip trailing slashes and reject empty/whitespace-only values
        instance_filter = [v.rstrip("/") for v in instance_filter if v.rstrip("/")]
        if not instance_filter:
            instance_filter = None
    search_text = params.get("search", "")

    result = await get_search_history(
        request.app.state.db,
        page=page,
        app_filter=app_filter,
        queue_filter=queue_filter,
        outcome_filter=outcome_filter,
        instance_filter=instance_filter,
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
            "active_instances": instance_filter or [],
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

    # Parse multi-instance form fields using {app}__{instance}__{field} convention
    parsed_instances: dict[str, dict[str, dict[str, str]]] = {"radarr": {}, "sonarr": {}}
    for key in form:
        parts = key.split("__", 2)
        if len(parts) == 3 and parts[0] in parsed_instances:
            app_name, inst_name, field = parts
            parsed_instances[app_name].setdefault(inst_name, {})[field] = form[key]

    for name in ("radarr", "sonarr"):
        current_instances = getattr(current_settings, name)
        new_config[name] = {}

        if parsed_instances[name]:
            # Multi-instance form data present -- parse all instances
            for inst_name, fields in parsed_instances[name].items():
                current_cfg = current_instances.get(inst_name)

                url = fields.get("url", "").strip()
                valid, err = validate_arr_url(url)
                if not valid:
                    logger.warning("{name}/{inst}: URL rejected -- {err}", name=name.title(), inst=inst_name, err=err)
                    return RedirectResponse(url=request.url_for("settings_page"), status_code=303)

                submitted_key = fields.get("api_key", "").strip()
                # Preserve API key when field is empty
                if not submitted_key and current_cfg:
                    submitted_key = current_cfg.api_key.get_secret_value()

                new_config[name][inst_name] = {
                    "url": url,
                    "api_key": submitted_key,
                    "enabled": fields.get("enabled") == "on",
                    "search_interval": safe_int(fields.get("search_interval"), 30, 1, 1440),
                    "search_missing_count": safe_int(fields.get("search_missing_count"), 5, 0, 100),
                    "search_cutoff_count": safe_int(fields.get("search_cutoff_count"), 5, 0, 100),
                    "missing_tag": fields.get("missing_tag", "").strip(),
                    "cutoff_tag": fields.get("cutoff_tag", "").strip(),
                }
        else:
            # No multi-instance form data -- preserve all existing instances unchanged
            for inst_name, existing_cfg in current_instances.items():
                new_config[name][inst_name] = {
                    "url": existing_cfg.url,
                    "api_key": existing_cfg.api_key.get_secret_value(),
                    "enabled": existing_cfg.enabled,
                    "search_interval": existing_cfg.search_interval,
                    "search_missing_count": existing_cfg.search_missing_count,
                    "search_cutoff_count": existing_cfg.search_cutoff_count,
                    "missing_tag": existing_cfg.missing_tag,
                    "cutoff_tag": existing_cfg.cutoff_tag,
                }

    # Validate BEFORE writing to disk (QUAL-02)
    try:
        new_settings = SettingsModel(**new_config)
    except pydantic.ValidationError as exc:
        logger.warning("Invalid settings rejected: {exc}", exc=exc)
        return RedirectResponse(url=request.url_for("settings_page"), status_code=303)

    # Config is valid -- write to disk using shared atomic helper (BUG-05 dedup)
    _atomic_toml_write(config_path, new_config)
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
        client_class = RadarrClient if name == "radarr" else SonarrClient

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
            key_changed = old_cfg is None or new_cfg.api_key != old_cfg.api_key

            if url_changed or key_changed or inst_name not in clients_dict:
                old_client = clients_dict.pop(inst_name, None)
                if old_client:
                    await old_client.close()
                clients_dict[inst_name] = client_class(
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

        # Ensure state entry exists for newly enabled instances (BUG-03)
        triggarr_state = request.app.state.triggarr_state
        triggarr_state.setdefault(name, {})
        for inst_name, new_cfg in new_instances.items():
            if new_cfg.enabled and inst_name not in triggarr_state[name]:
                from triggarr.state import _default_instance_state

                triggarr_state[name][inst_name] = _default_instance_state()

        setattr(request.app.state, f"{name}_clients", clients_dict)

    # Persist state with any new instance entries
    await asyncio.get_event_loop().run_in_executor(
        None, save_state, request.app.state.triggarr_state, state_path
    )

    return RedirectResponse(url=request.url_for("settings_page"), status_code=303)


@router.get("/api/tags/{app_name}/{instance_name}", response_class=HTMLResponse)
async def tag_autocomplete(request: Request, app_name: str, instance_name: str) -> HTMLResponse:
    """Return HTML option elements for tag autocomplete from an *arr instance.

    Used by datalist inputs in the settings form via htmx hx-get on focus.
    Returns empty HTML if the app/instance is invalid or client unavailable.
    """
    if app_name not in ("radarr", "sonarr"):
        return HTMLResponse("")
    if len(instance_name) > 64:
        return HTMLResponse("")

    clients = getattr(request.app.state, f"{app_name}_clients", {})
    client = clients.get(instance_name)
    if client is None:
        return HTMLResponse("")

    try:
        tags = await client.get_tags()
        options = "".join(f'<option value="{html.escape(tag.label)}">' for tag in tags)
        return HTMLResponse(options)
    except (httpx.HTTPError, pydantic.ValidationError):
        return HTMLResponse("")


@router.post("/api/instance/add", response_model=None)
async def add_instance(request: Request):
    """Add a new instance for an app type with default settings.

    Validates the instance name, enforces the max-5-per-app limit,
    and rejects duplicate names.  On success, writes updated config
    to TOML and redirects to the settings page.
    """
    form = await request.form()
    app_name = form.get("app_name", "").strip()
    instance_name = form.get("instance_name", "").strip()

    if app_name not in ("radarr", "sonarr"):
        return HTMLResponse("Invalid app type", status_code=400)

    valid, err = validate_instance_name(instance_name)
    if not valid:
        return HTMLResponse(err, status_code=400)

    settings = request.app.state.settings
    instances = getattr(settings, app_name)

    if instance_name in instances:
        return HTMLResponse(f"Instance '{html.escape(instance_name)}' already exists", status_code=400)
    if len(instances) >= 5:
        return HTMLResponse("Maximum 5 instances per app type", status_code=400)

    # Build new config dict, add instance, and validate before mutating live state
    from triggarr.models.config import InstanceConfig

    config_path = request.app.state.config_path
    config_dict = _settings_to_dict(settings)
    config_dict[app_name][instance_name] = InstanceConfig().model_dump()
    config_dict[app_name][instance_name]["api_key"] = ""
    try:
        new_settings = SettingsModel(**config_dict)
    except pydantic.ValidationError as exc:
        logger.warning("Invalid settings rejected on add_instance: {exc}", exc=exc)
        return HTMLResponse(f"Validation error: {html.escape(str(exc))}", status_code=400)
    _atomic_toml_write(config_path, config_dict)
    request.app.state.settings = new_settings

    # Create state entry for the new instance
    from triggarr.state import _default_instance_state

    triggarr_state = request.app.state.triggarr_state
    triggarr_state.setdefault(app_name, {})
    triggarr_state[app_name][instance_name] = _default_instance_state()

    return RedirectResponse(url=request.url_for("settings_page"), status_code=303)


@router.post("/api/instance/remove/{app_name}/{instance_name}", response_model=None)
async def remove_instance(request: Request, app_name: str, instance_name: str):
    """Remove an instance from an app type.

    Cleans up the scheduler job, client connection, and state entry.
    Writes updated config to TOML and redirects to settings page.
    """
    if app_name not in ("radarr", "sonarr"):
        return HTMLResponse("Invalid app type", status_code=400)
    if len(instance_name) > 64:
        return HTMLResponse("Instance name too long", status_code=400)

    settings = request.app.state.settings
    instances = getattr(settings, app_name)

    if instance_name not in instances:
        return HTMLResponse(f"Instance '{html.escape(instance_name)}' not found", status_code=400)

    # Acquire search_lock to prevent races with in-flight search jobs
    async with request.app.state.search_lock:
        # Remove instance from settings
        del instances[instance_name]

        # Write updated config to TOML
        config_path = request.app.state.config_path
        config_dict = _settings_to_dict(settings)
        _atomic_toml_write(config_path, config_dict)

        # Clean up scheduler job
        scheduler = request.app.state.scheduler
        job_id = f"{app_name}_{instance_name}_search"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        # Clean up client
        clients_dict = getattr(request.app.state, f"{app_name}_clients", {})
        client = clients_dict.pop(instance_name, None)
        if client:
            await client.close()

        # Clean up state entry
        triggarr_state = request.app.state.triggarr_state
        if app_name in triggarr_state:
            triggarr_state[app_name].pop(instance_name, None)

    return RedirectResponse(url=request.url_for("settings_page"), status_code=303)


@router.post("/api/search-now/{app_name}/{instance_name}", response_class=HTMLResponse)
async def search_now(request: Request, app_name: str, instance_name: str) -> HTMLResponse:
    """Trigger an immediate search cycle for a specific instance and return updated card."""
    if len(instance_name) > 64:
        return HTMLResponse("Instance name too long", status_code=400)
    if app_name not in ("radarr", "sonarr"):
        return HTMLResponse("Invalid app", status_code=400)

    clients = getattr(request.app.state, f"{app_name}_clients", {})
    enabled = request.app.state.settings.get_enabled_instances(app_name)
    if instance_name not in enabled or instance_name not in clients:
        return HTMLResponse("Instance not enabled", status_code=400)
    client = clients[instance_name]
    instance_config = enabled[instance_name]

    # Optimistic rate limit check BEFORE lock (fast-fail for obvious cases)
    rate_key = f"{app_name}_{instance_name}"
    now = time.monotonic()
    last = request.app.state.last_search_time.get(rate_key, 0.0)
    if now - last < SEARCH_RATE_LIMIT_SECONDS:
        logger.info("{name}/{inst}: Manual search rate-limited", name=app_name.title(), inst=instance_name)
        return HTMLResponse("Rate limited — try again shortly", status_code=429)

    cycle_fn = run_radarr_cycle if app_name == "radarr" else run_sonarr_cycle
    async with request.app.state.search_lock:
        # Re-check inside lock to prevent concurrent bypass (DRSEC-03)
        now = time.monotonic()
        last = request.app.state.last_search_time.get(rate_key, 0.0)
        if now - last < SEARCH_RATE_LIMIT_SECONDS:
            logger.info(
                "{name}/{inst}: Manual search rate-limited (after lock)",
                name=app_name.title(), inst=instance_name,
            )
            return HTMLResponse("Rate limited — try again shortly", status_code=429)
        request.app.state.last_search_time[rate_key] = now

        try:
            request.app.state.triggarr_state = await cycle_fn(
                client,
                request.app.state.triggarr_state,
                instance_name,
                instance_config,
                request.app.state.settings,
                request.app.state.db,
            )
            await asyncio.get_event_loop().run_in_executor(
                None, save_state, request.app.state.triggarr_state, request.app.state.state_path
            )
            logger.info("{name}/{inst}: Manual search triggered", name=app_name.title(), inst=instance_name)
        except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
            logger.error(
                "{name}/{inst}: Manual search failed -- {exc}",
                name=app_name.title(),
                inst=instance_name,
                exc=exc,
            )

    # Return updated card partial
    app_data = _build_app_context(request, app_name, instance_name)
    return templates.TemplateResponse(
        request=request,
        name="partials/app_card.html",
        context={"app": app_data},
    )


@router.get("/partials/app-card/{app_name}/{instance_name}", response_class=HTMLResponse)
async def partial_app_card(request: Request, app_name: str, instance_name: str) -> HTMLResponse:
    """Return an HTML fragment for a single app instance status card (htmx partial)."""
    if len(instance_name) > 64:
        return HTMLResponse("Instance name too long", status_code=400)
    app_data = _build_app_context(request, app_name, instance_name)
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


@router.get("/partials/health-summary", response_class=HTMLResponse)
async def partial_health_summary(request: Request) -> HTMLResponse:
    """Return an HTML fragment for the health summary (htmx partial)."""
    health = _build_health_summary(request)
    return templates.TemplateResponse(
        request=request,
        name="partials/health_summary.html",
        context={"health": health},
    )


@router.get("/partials/stats-row", response_class=HTMLResponse)
async def partial_stats_row(request: Request) -> HTMLResponse:
    """Return an HTML fragment for the dashboard stats row (htmx partial).

    Accepts optional ?instance=app/name query param to scope stats to a
    specific instance. Also builds all_instances list for dropdown filter.
    """
    instance_param = request.query_params.get("instance")
    instance_id: str | None = None
    instance_app_type: str | None = None

    if instance_param:
        if "/" in instance_param:
            app_type, inst_name = instance_param.split("/", 1)
            instance_id = inst_name
            instance_app_type = app_type
        else:
            instance_id = instance_param
            # Determine app type by checking which app has this instance
            settings = request.app.state.settings
            for app_name in ("radarr", "sonarr"):
                if instance_id in settings.get_enabled_instances(app_name):
                    instance_app_type = app_name
                    break

    stats = await get_dashboard_stats(request.app.state.db, instance_id=instance_id)
    time_to_grab = _format_duration(stats["avg_time_to_grab_seconds"])
    all_instances = _build_all_instances(request.app.state.settings)
    return templates.TemplateResponse(
        request=request,
        name="partials/stats_row.html",
        context={
            "stats": stats,
            "time_to_grab": time_to_grab,
            "all_instances": all_instances,
            "selected_instance": instance_param or "",
            "instance_app_type": instance_app_type,
        },
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


@router.delete("/api/dismiss-migration", response_class=HTMLResponse)
async def dismiss_migration(request: Request) -> HTMLResponse:
    """Dismiss the migration banner by deleting the .migrated marker file.

    Returns empty HTML so hx-swap="outerHTML" removes the banner element.
    Succeeds even if .migrated does not exist (missing_ok=True).
    Rejects non-htmx requests with 403 to prevent CSRF.
    """
    if not request.headers.get("HX-Request"):
        return HTMLResponse("Forbidden", status_code=403)
    (CONFIG_DIR / ".migrated").unlink(missing_ok=True)
    return HTMLResponse("")
