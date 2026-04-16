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
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import httpx
import jinja2
import pydantic
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import SecretStr

from triggarr.auth import (
    COOKIE_MAX_AGE,
    generate_api_key,
    generate_session_secret,
    hash_password,
    sign_session,
    validate_session,
    verify_password,
)
from triggarr.changelog import read_changelog
from triggarr.clients.lidarr import LidarrClient
from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.config import _atomic_toml_write, load_settings
from triggarr.db import get_dashboard_stats, get_recent_searches, get_search_history
from triggarr.log_buffer import log_buffer
from triggarr.logging import setup_logging
from triggarr.models.config import APP_TYPES, CONFIG_DIR, AuthConfig, InstanceConfig
from triggarr.models.config import Settings as SettingsModel
from triggarr.search.engine import run_lidarr_cycle, run_radarr_cycle, run_sonarr_cycle
from triggarr.search.scheduler import make_search_job
from triggarr.startup import collect_secrets
from triggarr.state import _default_instance_state, save_state
from triggarr.version import get_display_version
from triggarr.web.validation import safe_int, safe_log_level, validate_arr_url, validate_instance_name

_PKG_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = _PKG_DIR / "templates"
STATIC_DIR = _PKG_DIR / "static"

_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
)
templates = Jinja2Templates(env=_jinja_env)
templates.env.globals["triggarr_version"] = get_display_version()
# Shared mutable dict for update info. The scheduler lifespan assigns this
# same object to app.state.update_info so both sides share it without
# the scheduler needing to import from routes.
update_info: dict = {}
templates.env.globals["update_info"] = update_info
# Shared mutable dict for auth display state. Plan 03's route handlers populate it
# from settings on startup and after config changes. Templates use auth_state.active
# for conditional logout link visibility (D-11).
auth_state: dict = {"active": False}
templates.env.globals["auth_state"] = auth_state


def _is_secure_context(request: Request) -> bool:
    """True when the request arrived over HTTPS (direct or via reverse proxy)."""
    if request.url.scheme == "https":
        return True
    return request.headers.get("x-forwarded-proto", "") == "https"


def _sync_auth_state(settings: SettingsModel) -> None:
    """Update auth_state dict for template conditional rendering (D-11)."""
    auth_state["active"] = settings.auth.method in ("Forms", "Basic") and not settings.auth.needs_setup
    auth_state["method"] = settings.auth.method


def _relative_time_filter(iso_timestamp: str) -> str:
    """Jinja2 filter: ISO timestamp string -> 'Just now' / '3m ago' style."""
    if not iso_timestamp:
        return ""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return iso_timestamp[:19].replace("T", " ")
    return _relative_time(dt, short_threshold=True)


def _relative_time(dt: datetime | None, *, short_threshold: bool = False) -> str:
    """Format a datetime as a short relative string (e.g. '2s ago', '1m ago').

    When *short_threshold* is True, deltas under 10 seconds return 'Just now'.
    """
    if dt is None:
        return "never"
    delta = datetime.now(UTC) - dt
    seconds = int(delta.total_seconds())
    if seconds < 0 or (short_threshold and seconds < 10):
        return "Just now"
    if seconds < 60:
        return f"{seconds}s ago"
    elif seconds < 3600:
        return f"{seconds // 60}m ago"
    elif seconds < 86400:
        return f"{seconds // 3600}h ago"
    else:
        return f"{seconds // 86400}d ago"


templates.env.filters["relative_time"] = _relative_time_filter
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


def _safe_next_url(next_param: str | None) -> str:
    """Validate ?next= param, rejecting open redirects. Returns safe URL or '/'.

    Rejects absolute URLs (http/https), protocol-relative URLs (//),
    backslash URLs, and paths not starting with '/'. Checks both raw and
    percent-decoded forms to prevent bypass via URL encoding.
    """
    if not next_param:
        return "/"
    # Check both raw and decoded forms to prevent percent-encoding bypass
    from urllib.parse import unquote

    decoded = unquote(next_param)
    fully_decoded = unquote(decoded)
    for value in (next_param, decoded, fully_decoded):
        if value.startswith(("http://", "https://", "//")):
            return "/"
        if "\\" in value:
            return "/"
        if "\x00" in value:
            return "/"
    if not next_param.startswith("/"):
        return "/"
    return next_param


def _settings_to_dict(settings: SettingsModel) -> dict:
    """Convert Settings to a plain dict suitable for TOML serialization.

    This is the sole extraction point for SecretStr -> plain string outside of
    HTTP client init (see CLAUDE.md SecretStr convention).
    """
    result: dict = {"general": settings.general.model_dump()}
    for app_name in APP_TYPES:
        instances = getattr(settings, app_name)
        result[app_name] = {}
        for inst_name, cfg in instances.items():
            d = cfg.model_dump()
            d["api_key"] = cfg.api_key.get_secret_value()  # TOML serialization extraction
            result[app_name][inst_name] = d
    # Auth section: extract SecretStr values for TOML serialization
    auth = settings.auth
    result["auth"] = {
        "method": auth.method,
        "username": auth.username,
        "password_hash": auth.password_hash.get_secret_value(),
        "api_key": auth.api_key.get_secret_value(),
        "session_secret": auth.session_secret.get_secret_value(),
    }
    return result


@router.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint for uptime monitors."""
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

    for app_name in APP_TYPES:
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
    for app_name in APP_TYPES:
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
    for app_name in APP_TYPES:
        for inst_name in settings.get_enabled_instances(app_name):
            ctx = _build_app_context(request, app_name, inst_name)
            if ctx is not None:
                apps.append(ctx)

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
            "log_entries": log_entries,
            "stats": stats,
            "time_to_grab": time_to_grab,
            "health": health,
            "all_instances": all_instances,
            "selected_instance": "",
            "instance_app_type": None,
            "show_migration_banner": (CONFIG_DIR / ".migrated").exists(),
            "radarr_enabled": bool(settings.get_enabled_instances("radarr")),
            "sonarr_enabled": bool(settings.get_enabled_instances("sonarr")),
            "lidarr_enabled": bool(settings.get_enabled_instances("lidarr")),
        },
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    """Render the settings page with all instances per app type and masked API keys."""
    settings = request.app.state.settings
    apps: dict[str, dict] = {}
    for name in APP_TYPES:
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
            "auth_method": settings.auth.method,
            "auth_is_disabled": settings.auth.is_disabled,
            "auth_api_key_set": bool(settings.auth.api_key.get_secret_value()),
            "auth_username": settings.auth.username,
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
    search_text = (params.get("search", "") or "")[:200]

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
    parsed_instances: dict[str, dict[str, dict[str, str]]] = {app: {} for app in APP_TYPES}
    for key in form:
        parts = key.split("__", 2)
        if len(parts) == 3 and parts[0] in parsed_instances:
            app_name, inst_name, field = parts
            parsed_instances[app_name].setdefault(inst_name, {})[field] = form[key]

    for name in APP_TYPES:
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
                # Preserve API key when field is empty (keep SecretStr for validation)
                if not submitted_key and current_cfg:
                    submitted_key = current_cfg.api_key

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
            # Keep SecretStr objects; _settings_to_dict extracts for TOML write
            for inst_name, existing_cfg in current_instances.items():
                new_config[name][inst_name] = {
                    "url": existing_cfg.url,
                    "api_key": existing_cfg.api_key,
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

    # Config is valid -- serialize from validated model (SecretStr extraction in _settings_to_dict)
    # Acquire search_lock to prevent races with in-flight search jobs during mutation.
    # Collect stale clients to close AFTER releasing the lock (avoid holding lock during TCP teardown).
    clients_to_close: list = []
    async with request.app.state.search_lock:
        await asyncio.get_running_loop().run_in_executor(
            None, _atomic_toml_write, config_path, _settings_to_dict(new_settings)
        )
        os.chmod(config_path, 0o600)
        request.app.state.settings = new_settings
        _sync_auth_state(new_settings)

        # Refresh log redaction with new secrets (QUAL-05)
        secrets = collect_secrets(new_settings)
        setup_logging(new_settings.general.log_level, secrets)

        # Handle scheduler updates for each app's instances
        for name in APP_TYPES:
            new_instances = getattr(new_settings, name)
            old_instances = getattr(current_settings, name)
            clients_dict = getattr(request.app.state, f"{name}_clients", {})
            client_class = {"radarr": RadarrClient, "sonarr": SonarrClient, "lidarr": LidarrClient}[name]

            # Remove clients for removed/disabled instances (close deferred)
            for inst_name in list(clients_dict.keys()):
                new_cfg = new_instances.get(inst_name)
                if new_cfg is None or not new_cfg.enabled:
                    job_id = f"{name}_{inst_name}_search"
                    if scheduler.get_job(job_id):
                        scheduler.remove_job(job_id)
                    client = clients_dict.pop(inst_name, None)
                    if client:
                        clients_to_close.append(client)

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
                        clients_to_close.append(old_client)
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
                    triggarr_state[name][inst_name] = _default_instance_state()

            setattr(request.app.state, f"{name}_clients", clients_dict)

        # Persist state with any new instance entries
        await asyncio.get_running_loop().run_in_executor(
            None, save_state, request.app.state.triggarr_state, state_path
        )

    # Close stale clients outside the lock (TCP teardown doesn't need lock protection)
    for c in clients_to_close:
        await c.close()

    return RedirectResponse(url=request.url_for("settings_page"), status_code=303)


@router.get("/api/tags/{app_name}/{instance_name}", response_class=HTMLResponse)
async def tag_autocomplete(request: Request, app_name: str, instance_name: str) -> HTMLResponse:
    """Return HTML option elements for tag autocomplete from an *arr instance.

    Used by datalist inputs in the settings form via htmx hx-get on focus.
    Returns empty HTML if the app/instance is invalid or client unavailable.
    """
    if app_name not in APP_TYPES:
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
async def add_instance(request: Request) -> HTMLResponse | RedirectResponse:
    """Add a new instance for an app type with default settings.

    Validates the instance name, enforces the max-5-per-app limit,
    and rejects duplicate names.  On success, writes updated config
    to TOML and redirects to the settings page.
    """
    form = await request.form()
    app_name = form.get("app_name", "").strip()
    instance_name = form.get("instance_name", "").strip()

    if app_name not in APP_TYPES:
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
    config_path = request.app.state.config_path
    config_dict = _settings_to_dict(settings)
    config_dict[app_name][instance_name] = InstanceConfig().model_dump()
    config_dict[app_name][instance_name]["api_key"] = ""
    try:
        new_settings = SettingsModel(**config_dict)
    except pydantic.ValidationError as exc:
        logger.warning("Invalid settings rejected on add_instance: {exc}", exc=exc)
        return HTMLResponse("Validation error: invalid configuration", status_code=400)

    # Acquire search_lock to prevent races with in-flight search jobs
    async with request.app.state.search_lock:
        # Serialize from validated model to guarantee SecretStr extraction
        await asyncio.get_running_loop().run_in_executor(
            None, _atomic_toml_write, config_path, _settings_to_dict(new_settings)
        )
        request.app.state.settings = new_settings

        # Create state entry for the new instance
        triggarr_state = request.app.state.triggarr_state
        triggarr_state.setdefault(app_name, {})
        triggarr_state[app_name][instance_name] = _default_instance_state()

    return RedirectResponse(url=request.url_for("settings_page"), status_code=303)


@router.post("/api/instance/remove/{app_name}/{instance_name}", response_model=None)
async def remove_instance(request: Request, app_name: str, instance_name: str) -> HTMLResponse | RedirectResponse:
    """Remove an instance from an app type.

    Cleans up the scheduler job, client connection, and state entry.
    Writes updated config to TOML and redirects to settings page.
    """
    if app_name not in APP_TYPES:
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

        # Write updated config to TOML (offloaded to thread -- blocking I/O)
        config_path = request.app.state.config_path
        config_dict = _settings_to_dict(settings)
        await asyncio.get_running_loop().run_in_executor(
            None, _atomic_toml_write, config_path, config_dict
        )

        # Clean up scheduler job
        scheduler = request.app.state.scheduler
        job_id = f"{app_name}_{instance_name}_search"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        # Pop client from dict (close deferred to after lock release)
        clients_dict = getattr(request.app.state, f"{app_name}_clients", {})
        client = clients_dict.pop(instance_name, None)

        # Clean up state entry
        triggarr_state = request.app.state.triggarr_state
        if app_name in triggarr_state:
            triggarr_state[app_name].pop(instance_name, None)

    # Close stale client outside the lock (TCP teardown doesn't need lock protection)
    if client:
        await client.close()

    return RedirectResponse(url=request.url_for("settings_page"), status_code=303)


@router.post("/api/search-now/{app_name}/{instance_name}", response_class=HTMLResponse)
async def search_now(request: Request, app_name: str, instance_name: str) -> HTMLResponse:
    """Trigger an immediate search cycle for a specific instance and return updated card."""
    if len(instance_name) > 64:
        return HTMLResponse("Instance name too long", status_code=400)
    if app_name not in APP_TYPES:
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
        return HTMLResponse("Rate limited -- try again shortly", status_code=429)

    cycle_fns = {"radarr": run_radarr_cycle, "sonarr": run_sonarr_cycle, "lidarr": run_lidarr_cycle}
    cycle_fn = cycle_fns.get(app_name)
    if cycle_fn is None:
        logger.warning("{app}: search cycle not implemented yet", app=app_name.title())
        return HTMLResponse("Search not yet supported for this app type", status_code=501)

    async with request.app.state.search_lock:
        # Re-check inside lock to prevent concurrent bypass (DRSEC-03)
        now = time.monotonic()
        last = request.app.state.last_search_time.get(rate_key, 0.0)
        if now - last < SEARCH_RATE_LIMIT_SECONDS:
            logger.info(
                "{name}/{inst}: Manual search rate-limited (after lock)",
                name=app_name.title(), inst=instance_name,
            )
            return HTMLResponse("Rate limited -- try again shortly", status_code=429)
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
            await asyncio.get_running_loop().run_in_executor(
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


@router.get("/partials/activity-rail", response_class=HTMLResponse)
async def partial_activity_rail(request: Request) -> HTMLResponse:
    """Return an HTML fragment for the activity rail timeline (htmx partial)."""
    search_log = await get_recent_searches(request.app.state.db)
    return templates.TemplateResponse(
        request=request,
        name="partials/activity_rail.html",
        context={"search_log": search_log},
    )


@router.get("/partials/health-summary", response_class=HTMLResponse)
async def partial_health_summary(request: Request) -> HTMLResponse:
    """Return an HTML fragment for the health summary (htmx partial)."""
    health = _build_health_summary(request)
    # Track last health check time for "Last sync" display
    last_check = getattr(request.app.state, "last_health_check", None)
    last_sync = _relative_time(last_check)
    request.app.state.last_health_check = datetime.now(UTC)
    return templates.TemplateResponse(
        request=request,
        name="partials/health_summary.html",
        context={"health": health, "last_sync": last_sync},
    )


@router.get("/partials/connection-pill", response_class=HTMLResponse)
async def partial_connection_pill(request: Request) -> HTMLResponse:
    """Return an HTML fragment for the header connection status pill (htmx partial)."""
    health = _build_health_summary(request)
    return templates.TemplateResponse(
        request=request,
        name="partials/connection_pill.html",
        context={"health": health},
    )


@router.get("/partials/stats-row", response_class=HTMLResponse)
async def partial_stats_row(request: Request) -> HTMLResponse:
    """Return an HTML fragment for the dashboard stats row (htmx partial).

    Accepts optional ?instance=app/name query param to scope stats to a
    specific instance. Also builds all_instances list for dropdown filter.
    """
    instance_param = request.query_params.get("instance")
    if instance_param and len(instance_param) > 128:
        return HTMLResponse("Invalid instance parameter", status_code=400)
    instance_id: str | None = None
    instance_app_type: str | None = None

    if instance_param:
        if "/" in instance_param:
            app_type, inst_name = instance_param.split("/", 1)
            if app_type not in APP_TYPES:
                return HTMLResponse("Invalid instance parameter", status_code=400)
            enabled = request.app.state.settings.get_enabled_instances(app_type)
            if inst_name not in enabled:
                return HTMLResponse("Invalid instance parameter", status_code=400)
            instance_id = inst_name
            instance_app_type = app_type
        else:
            instance_id = instance_param
            # Determine app type by checking which app has this instance
            settings = request.app.state.settings
            for app_name in APP_TYPES:
                if instance_id in settings.get_enabled_instances(app_name):
                    instance_app_type = app_name
                    break

    stats = await get_dashboard_stats(request.app.state.db, instance_id=instance_id)
    time_to_grab = _format_duration(stats["avg_time_to_grab_seconds"])
    all_instances = _build_all_instances(request.app.state.settings)
    settings = request.app.state.settings
    return templates.TemplateResponse(
        request=request,
        name="partials/stats_row.html",
        context={
            "stats": stats,
            "time_to_grab": time_to_grab,
            "all_instances": all_instances,
            "selected_instance": instance_param or "",
            "instance_app_type": instance_app_type,
            "radarr_enabled": bool(settings.get_enabled_instances("radarr")),
            "sonarr_enabled": bool(settings.get_enabled_instances("sonarr")),
            "lidarr_enabled": bool(settings.get_enabled_instances("lidarr")),
        },
    )


@router.get("/partials/log-viewer", response_class=HTMLResponse)
async def partial_log_viewer(request: Request, level: str = "") -> HTMLResponse:
    """Return an HTML fragment for the application log viewer (htmx partial)."""
    _VALID_LEVELS = {"ERROR", "WARNING", "INFO", "DEBUG"}
    log_entries = log_buffer.get_recent(30)
    # Server-side level filter (per D-06, T-51-01)
    if level.upper() in _VALID_LEVELS:
        level = level.upper()
        log_entries = [e for e in log_entries if e.level == level]
    else:
        level = ""
    return templates.TemplateResponse(
        request=request,
        name="partials/log_viewer.html",
        context={"log_entries": log_entries, "selected_level": level},
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


@router.get("/changelog", response_class=HTMLResponse)
async def changelog(request: Request) -> HTMLResponse:
    """Return rendered changelog HTML for the modal.

    When called with ``?latest=true``, returns only the most recent
    version section.  Otherwise returns the full changelog.
    """
    latest_only = request.query_params.get("latest", "").lower() == "true"
    html_content = read_changelog(latest_only=latest_only)
    return HTMLResponse(html_content)


# --- Auth routes ---


@router.get("/setup", response_class=HTMLResponse, response_model=None)
async def setup_page(request: Request) -> HTMLResponse | RedirectResponse:
    """Render the first-run setup page, or redirect to login if already configured.

    When auth is already configured (needs_setup=False), redirects to /login
    with ?setup=done so the login page can show a helpful message instead of
    returning a bare 404 that gives the user no guidance.
    """
    auth = request.app.state.settings.auth
    if not auth.needs_setup:
        return RedirectResponse(url=str(request.url_for("login_page")) + "?setup=done", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="setup.html",
        context={"setup_complete": False, "errors": {}, "username": "admin"},
    )


@router.post("/setup", response_model=None)
async def setup_post(request: Request) -> HTMLResponse | RedirectResponse:
    """Process first-run setup: validate credentials, persist config, auto-login.

    If auth is already configured (race condition or stale form submission),
    redirects to /login instead of returning a bare 404.
    """
    auth = request.app.state.settings.auth
    if not auth.needs_setup:
        return RedirectResponse(url=str(request.url_for("login_page")) + "?setup=done", status_code=302)

    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")
    confirm = form.get("confirm_password", "")

    errors: dict[str, str] = {}
    if not username:
        errors["username"] = "Username is required"
    if not password:
        errors["password"] = "Password is required"
    elif password != confirm:
        errors["confirm_password"] = "Passwords do not match"

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="setup.html",
            context={"setup_complete": False, "errors": errors, "username": username},
        )

    # Create credentials
    password_hash = hash_password(password)
    api_key = generate_api_key()
    session_secret = generate_session_secret()

    new_auth = AuthConfig(
        method="Forms",
        username=username,
        password_hash=SecretStr(password_hash),
        api_key=SecretStr(api_key),
        session_secret=SecretStr(session_secret),
    )

    # Persist to TOML -- merge auth with existing config
    config_path = request.app.state.config_path
    async with request.app.state.search_lock:
        # Re-check inside lock to prevent race condition (Pitfall 5)
        current_settings = request.app.state.settings
        if not current_settings.auth.needs_setup:
            return RedirectResponse(url=str(request.url_for("login_page")) + "?setup=done", status_code=302)

        # Build new settings with auth configured
        updated = current_settings.model_copy(update={"auth": new_auth})
        config_dict = _settings_to_dict(updated)
        await asyncio.get_running_loop().run_in_executor(
            None, _atomic_toml_write, config_path, config_dict
        )
        os.chmod(config_path, 0o600)
        request.app.state.settings = load_settings(config_path)

    # Update auth_state for nav bar logout visibility
    _sync_auth_state(request.app.state.settings)

    # Refresh redacting sink so new credentials are never logged in cleartext
    _new_secrets = collect_secrets(request.app.state.settings)
    setup_logging(request.app.state.settings.general.log_level, _new_secrets)

    # Auto-login: set session cookie (D-01)
    session_value = sign_session(username, session_secret)
    response = templates.TemplateResponse(
        request=request,
        name="setup.html",
        context={"setup_complete": True, "api_key": api_key, "username": username},
    )
    response.set_cookie(
        "triggarr_session",
        session_value,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=_is_secure_context(request),
    )
    logger.info("Setup completed")
    return response


@router.get("/login", response_class=HTMLResponse, response_model=None)
async def login_page(request: Request) -> HTMLResponse | RedirectResponse:
    """Render login form, or redirect to dashboard if already authenticated (D-06)."""
    auth = request.app.state.settings.auth

    # Sync auth_state on page load (handles app restart without explicit sync)
    _sync_auth_state(request.app.state.settings)

    # D-06: already authenticated -> redirect to dashboard
    cookie = request.cookies.get("triggarr_session")
    username = validate_session(cookie, auth.session_secret.get_secret_value())
    if username:
        return RedirectResponse(url=request.url_for("dashboard"), status_code=302)

    raw_next = request.query_params.get("next", "")
    next_url = _safe_next_url(raw_next) if raw_next else ""

    # Show info message when redirected from /setup (setup already completed)
    info = None
    if request.query_params.get("setup") == "done":
        info = "Account setup has already been completed. Please sign in."

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None, "info": info, "username": "", "next_url": next_url},
    )


# ---------------------------------------------------------------------------
# Login rate limiter (SHIELD-003 / D-01, D-02, D-03)
# ---------------------------------------------------------------------------

# Thread safety: safe under single-worker asyncio (GIL + cooperative scheduling).
# If multiple workers are used, rate limiting should move to shared storage (e.g., Redis).
_login_failures: dict[str, list[float]] = {}
_MAX_TRACKED_IPS = 10_000
_MAX_ATTEMPTS = 10
_WINDOW_SECONDS = 300


def _check_rate_limit(ip: str) -> tuple[bool, int]:
    """Check if IP is rate-limited. Prunes expired entries as a side effect.

    Returns (is_limited, retry_after_seconds).
    """
    now = time.monotonic()
    raw = _login_failures.get(ip)
    if raw is None:
        return (False, 0)
    timestamps = [t for t in raw if now - t < _WINDOW_SECONDS]
    if timestamps:
        _login_failures[ip] = timestamps
    else:
        del _login_failures[ip]
        return (False, 0)
    if len(timestamps) >= _MAX_ATTEMPTS:
        oldest = min(timestamps)
        retry_after = int(_WINDOW_SECONDS - (now - oldest)) + 1
        return (True, retry_after)
    return (False, 0)


def _record_failure(ip: str) -> None:
    """Record a failed login attempt for rate limiting."""
    now = time.monotonic()
    if ip not in _login_failures:
        # Evict oldest entry if at capacity
        if len(_login_failures) >= _MAX_TRACKED_IPS:
            oldest_ip = min(
                _login_failures,
                key=lambda k: _login_failures[k][0] if _login_failures[k] else float("inf"),
            )
            del _login_failures[oldest_ip]
        _login_failures[ip] = []
    _login_failures[ip].append(now)


def _reset_rate_limiter() -> None:
    """Clear all rate limit state. Used by test fixtures."""
    _login_failures.clear()


@router.post("/login", response_model=None)
async def login_post(request: Request) -> HTMLResponse | RedirectResponse:
    """Authenticate credentials, set session cookie, redirect to ?next= or dashboard."""
    auth = request.app.state.settings.auth
    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")
    next_url = form.get("next", "")

    # Rate limit check (D-01, D-02) -- before credential verification
    # NOTE: client.host is resolved from X-Forwarded-For by uvicorn when proxy_headers=True.
    # If TRUSTED_PROXY_IPS=*, rate limiting can be bypassed by spoofing X-Forwarded-For.
    # In that configuration, rate limiting should be applied at the reverse proxy layer.
    client_ip = request.client.host if request.client else "unknown"
    is_limited, retry_after = _check_rate_limit(client_ip)
    if is_limited:
        minutes = (retry_after + 59) // 60  # round up to nearest minute
        resp = templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": f"Too many login attempts, try again in {minutes} minute{'s' if minutes != 1 else ''}",
                "info": None,
                "username": username,
                "next_url": _safe_next_url(next_url) if next_url else "",
            },
            status_code=429,
        )
        resp.headers["Retry-After"] = str(retry_after)
        return resp

    # Verify credentials
    if (
        username
        and password
        and secrets.compare_digest(username, auth.username)
        and verify_password(password, auth.password_hash.get_secret_value())
    ):
        # Success: set session cookie and redirect
        session_value = sign_session(username, auth.session_secret.get_secret_value())
        redirect_url = _safe_next_url(next_url) if next_url else str(request.url_for("dashboard"))
        response = RedirectResponse(url=redirect_url, status_code=303)
        response.set_cookie(
            "triggarr_session",
            session_value,
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=_is_secure_context(request),
        )
        logger.info("Login successful")
        return response

    # Failure: record for rate limiting, then re-render with error (D-04)
    _record_failure(client_ip)
    logger.warning("Login failed: invalid credentials")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": "Invalid username or password",
            "info": None,
            "username": username,
            "next_url": _safe_next_url(next_url) if next_url else "",
        },
    )


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    """Clear session cookie and redirect to login page (D-09)."""
    response = RedirectResponse(url=request.url_for("login_page"), status_code=303)
    response.delete_cookie(
        "triggarr_session",
        path="/",
        httponly=True,
        samesite="lax",
        secure=_is_secure_context(request),
    )
    logger.info("User logged out")
    return response


# ---------------------------------------------------------------------------
# Security settings endpoints (57-01)
# ---------------------------------------------------------------------------

_ALLOWED_AUTH_METHODS = {"Forms", "Basic", "External"}


@router.post("/settings/password")
async def change_password(request: Request) -> HTMLResponse:
    """Change user password with current-password verification."""
    form = await request.form()
    current_password = str(form.get("current_password", ""))
    new_password = str(form.get("new_password", ""))
    confirm_password = str(form.get("confirm_password", ""))

    errors: dict[str, str] = {}

    if not current_password:
        errors["current_password"] = "Current password is required"
    if not new_password:
        errors["new_password"] = "New password is required"
    elif new_password != confirm_password:
        errors["confirm_password"] = "Passwords do not match"

    if errors:
        return templates.TemplateResponse(
            request=request,
            name="partials/security_password.html",
            context={"errors": errors},
        )

    config_path = request.app.state.config_path
    async with request.app.state.search_lock:
        # Verify current password inside lock to prevent TOCTOU race (WR-01)
        current_settings = request.app.state.settings
        if not verify_password(current_password, current_settings.auth.password_hash.get_secret_value()):
            logger.warning("Password change failed: incorrect current password")
            return templates.TemplateResponse(
                request=request,
                name="partials/security_password.html",
                context={"errors": {"current_password": "Current password is incorrect"}},
            )

        # Hash and persist -- catch bcrypt 72-byte limit
        try:
            new_hash = hash_password(new_password)
        except ValueError:
            return templates.TemplateResponse(
                request=request,
                name="partials/security_password.html",
                context={"errors": {"new_password": "Password must be 72 characters or fewer"}},
            )
        new_auth = current_settings.auth.model_copy(update={"password_hash": SecretStr(new_hash)})
        updated = current_settings.model_copy(update={"auth": new_auth})
        config_dict = _settings_to_dict(updated)
        await asyncio.get_running_loop().run_in_executor(
            None, _atomic_toml_write, config_path, config_dict
        )
        os.chmod(config_path, 0o600)
        request.app.state.settings = load_settings(config_path)

    _sync_auth_state(request.app.state.settings)
    _new_secrets = collect_secrets(request.app.state.settings)
    setup_logging(request.app.state.settings.general.log_level, _new_secrets)

    # D-05: return fresh partial with empty password inputs (no value= attributes)
    return templates.TemplateResponse(
        request=request,
        name="partials/security_password.html",
        context={"success": "Password updated"},
    )


@router.post("/settings/security")
async def save_security(request: Request) -> RedirectResponse:
    """Save auth method selection. Rejects Disabled and unknown values (T-57-02, D-13)."""
    form = await request.form()
    auth_method = str(form.get("auth_method", ""))

    if auth_method not in _ALLOWED_AUTH_METHODS:
        # Reject invalid/disabled method -- redirect without change
        return RedirectResponse(url=request.url_for("settings_page"), status_code=303)

    config_path = request.app.state.config_path
    async with request.app.state.search_lock:
        current_settings = request.app.state.settings
        new_auth = current_settings.auth.model_copy(update={"method": auth_method})
        updated = current_settings.model_copy(update={"auth": new_auth})
        config_dict = _settings_to_dict(updated)
        await asyncio.get_running_loop().run_in_executor(
            None, _atomic_toml_write, config_path, config_dict
        )
        os.chmod(config_path, 0o600)
        request.app.state.settings = load_settings(config_path)

    _sync_auth_state(request.app.state.settings)
    _new_secrets = collect_secrets(request.app.state.settings)
    setup_logging(request.app.state.settings.general.log_level, _new_secrets)

    return RedirectResponse(url=request.url_for("settings_page"), status_code=303)


@router.post("/settings/api-key/regenerate")
async def regenerate_api_key_endpoint(request: Request) -> HTMLResponse:
    """Generate a new API key and return the revealed partial."""
    new_key = generate_api_key()

    config_path = request.app.state.config_path
    async with request.app.state.search_lock:
        current_settings = request.app.state.settings
        new_auth = current_settings.auth.model_copy(update={"api_key": SecretStr(new_key)})
        updated = current_settings.model_copy(update={"auth": new_auth})
        config_dict = _settings_to_dict(updated)
        await asyncio.get_running_loop().run_in_executor(
            None, _atomic_toml_write, config_path, config_dict
        )
        os.chmod(config_path, 0o600)
        request.app.state.settings = load_settings(config_path)

    _sync_auth_state(request.app.state.settings)
    _new_secrets = collect_secrets(request.app.state.settings)
    setup_logging(request.app.state.settings.general.log_level, _new_secrets)

    return templates.TemplateResponse(
        request=request,
        name="partials/security_apikey.html",
        context={"api_key": new_key, "revealed": True, "success": "Key regenerated"},
    )
