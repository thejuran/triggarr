"""Atomic JSON state persistence for Triggarr.

State tracks searched-log positions and search history
across container restarts. All writes use atomic write-then-rename
to prevent corruption if the process crashes mid-write.

v2.3: State is nested per-instance -- each configured instance
(e.g., "Default", "4K Radarr") maintains independent searched-logs.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from loguru import logger

from triggarr.models.config import APP_TYPES

if TYPE_CHECKING:
    from triggarr.models.config import Settings


def get_state_path() -> Path:
    """Return the state file path, derived from TRIGGARR_CONFIG_DIR env var.

    Defaults to /config/state.json when the env var is not set.
    """
    from triggarr.models.config import get_config_dir

    return get_config_dir() / "state.json"


STATE_PATH = get_state_path()
# NOTE: STATE_PATH is evaluated once at first import.
# Changing TRIGGARR_CONFIG_DIR after import has no effect on this constant.
# Functions accept path parameters to allow testing without module reload.


class AppState(TypedDict, total=False):
    """Per-instance searched-log and timing state."""

    missing_pass: int  # How many times missing queue has completed a full pass (0-based, first pass sets to 1)
    cutoff_pass: int  # How many times cutoff queue has completed a full pass (0-based, first pass sets to 1)
    missing_searched: list[str]  # Ordered searched-log (oldest first) for the missing queue
    cutoff_searched: list[str]  # Ordered searched-log (oldest first) for the cutoff queue
    last_run: str | None  # ISO timestamp
    last_success: str | None  # ISO timestamp — last cycle that reached connected=True
    connected: bool | None  # True after successful fetch, False after failure
    unreachable_since: str | None  # ISO timestamp of first failure, None when healthy
    missing_count: int | None  # Total wanted-missing items (before filtering)
    missing_eligible: int | None  # Items eligible for search (after filtering)
    missing_monitored: int | None  # Monitored items before tag/unreleased filtering
    missing_searchable: int | None  # Searchable units (Sonarr: seasons after dedup; None for Radarr)
    cutoff_count: int | None  # Total cutoff-unmet items (before filtering)
    cutoff_searchable: int | None  # Searchable units for cutoff (Sonarr: seasons; None for Radarr)
    total_items: int | None  # Total library items (Radarr: movies, Sonarr: episodes)
    tag_warnings: list[dict]  # Tag resolution warnings: [{"tag": name, "field": "missing"|"cutoff"}]


class TriggarrState(TypedDict, total=False):
    """Top-level application state with per-instance cursors.

    radarr, sonarr, and lidarr map instance names to their AppState:
    {"Default": AppState(...), "4K Radarr": AppState(...)}
    """

    radarr: dict[str, AppState]
    sonarr: dict[str, AppState]
    lidarr: dict[str, AppState]
    search_log: list[dict]  # deprecated: migrated to SQLite (SRCH-13), kept for migration compat


def _default_instance_state() -> AppState:
    """Return a fresh AppState for a single instance with empty searched-logs."""
    return AppState(
        missing_searched=[],
        cutoff_searched=[],
        last_run=None,
        last_success=None,
    )


def _default_state(settings: Settings | None = None) -> TriggarrState:
    """Return a fresh default state.

    Without settings: returns empty dicts for radarr/sonarr.
    With settings: populates per-instance entries from configured instance names.
    """
    if settings is None:
        return TriggarrState(radarr={}, sonarr={}, lidarr={}, search_log=[])

    state: TriggarrState = TriggarrState(search_log=[])
    for app_type in APP_TYPES:
        instances = getattr(settings, app_type, {})
        state[app_type] = {name: _default_instance_state() for name in instances}  # type: ignore[literal-required]
    return state


def _is_v22_state_format(data: dict) -> bool:
    """Check if state uses v2.2 flat format (AppState directly under radarr/sonarr).

    v2.2 format has keys like "missing_cursor" directly under radarr/sonarr.
    v2.3 format has instance names (e.g., "Default") under radarr/sonarr.

    Only checks radarr/sonarr — lidarr is new in v2.3 and never had flat state.
    """
    for section in ("radarr", "sonarr"):
        section_data = data.get(section, {})
        if isinstance(section_data, dict) and "missing_cursor" in section_data:
            return True
    return False


def _migrate_v22_state(data: dict) -> dict:
    """Transform v2.2 flat state to v2.3 per-instance format.

    Wraps each flat AppState into {"Default": AppState} to match
    the Phase 33 config migration naming convention.

    Only migrates radarr/sonarr — lidarr is new in v2.3 and never had flat state.
    """
    result = dict(data)
    for section in ("radarr", "sonarr"):
        section_data = result.get(section, {})
        if isinstance(section_data, dict) and "missing_cursor" in section_data:
            result[section] = {"Default": section_data}
    return result


def _merge_defaults(loaded: dict) -> TriggarrState:
    """Merge loaded state over defaults so missing keys get default values.

    Performs a two-level-deep merge: iterates instance names within each
    app key, and merges each instance's AppState against _default_instance_state().
    """
    defaults = _default_state()

    for app_key in APP_TYPES:
        loaded_section = loaded.get(app_key, {})
        if isinstance(loaded_section, dict):
            merged_section: dict[str, AppState] = {}
            for instance_name, instance_data in loaded_section.items():
                if isinstance(instance_data, dict):
                    merged = {**_default_instance_state(), **instance_data}
                    # HIGH-1: strip legacy cursor keys that pre-upgrade state.json may carry.
                    # {**defaults, **instance_data} preserves unknown keys; without this pop
                    # save_state would write them back indefinitely.
                    for legacy_key in ("missing_cursor", "cutoff_cursor"):
                        merged.pop(legacy_key, None)
                    merged_section[instance_name] = merged
                else:
                    merged_section[instance_name] = _default_instance_state()
            defaults[app_key] = merged_section

    if "search_log" in loaded and isinstance(loaded["search_log"], list):
        defaults["search_log"] = loaded["search_log"]

    return defaults


def load_state(state_path: Path | None = None) -> TriggarrState:
    """Load state from a JSON file.

    If the file does not exist, returns a default empty state.
    Automatically migrates v2.2 flat format to v2.3 nested format.

    Args:
        state_path: Path to the state JSON file. When omitted, derived from
            the current TRIGGARR_CONFIG_DIR value.

    Returns:
        Parsed state dictionary.
    """
    resolved_state_path = state_path or get_state_path()
    if not resolved_state_path.exists():
        return _default_state()

    try:
        with open(resolved_state_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt state file at {path} -- resetting to defaults", path=resolved_state_path)
        return _default_state()

    if _is_v22_state_format(data):
        logger.info("Migrating v2.2 state to v2.3 per-instance format")
        data = _migrate_v22_state(data)

    return _merge_defaults(data)


def save_state(state: TriggarrState, state_path: Path | None = None) -> None:
    """Atomically write state to disk.

    Uses write-to-temp-file then ``os.replace()`` to ensure the state
    file is never left in a partially written state. This prevents
    corruption if the process crashes mid-write.

    Args:
        state: State dictionary to persist.
        state_path: Destination path for the state file. When omitted, derived
            from the current TRIGGARR_CONFIG_DIR value.
    """
    resolved_state_path = state_path or get_state_path()
    parent = resolved_state_path.parent
    parent.mkdir(parents=True, exist_ok=True)

    dir_fd = None
    renamed = False
    fd, tmp_path = tempfile.mkstemp(dir=parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, resolved_state_path)
        renamed = True
        # fsync the directory to ensure rename is durable (matches config.py)
        dir_fd = os.open(parent, os.O_RDONLY)
        os.fsync(dir_fd)
    except OSError as exc:
        if renamed:
            logger.warning(
                "State written but directory fsync failed: {path} - {exc}",
                path=resolved_state_path,
                exc=exc,
            )
            return
        logger.error(
            "State write failed: {path} - {exc}",
            path=resolved_state_path,
            exc=exc,
        )
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        except OSError as cleanup_exc:
            logger.error(
                "Failed to clean up temp file {tmp} during state write: {exc}",
                tmp=tmp_path,
                exc=cleanup_exc,
            )
        raise
    except Exception as exc:
        logger.error(
            "State write failed (unexpected error): {path} - {exc}",
            path=resolved_state_path,
            exc=exc,
        )
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        except OSError as cleanup_exc:
            logger.error(
                "Failed to clean up temp file {tmp} during state write: {exc}",
                tmp=tmp_path,
                exc=cleanup_exc,
            )
        raise
    finally:
        if dir_fd is not None:
            os.close(dir_fd)


def cleanup_orphaned_instances(state: TriggarrState, settings: Settings) -> TriggarrState:
    """Remove state entries for instances not in current config.

    Compares instance names in state against configured instance names
    in settings, removing any that are no longer configured.

    Returns a new dict -- the input state is not mutated.

    Args:
        state: Current application state.
        settings: Current application settings.

    Returns:
        New state dict with orphaned instance entries removed.
    """
    result = dict(state)
    for app_type in APP_TYPES:
        configured_names = set(getattr(settings, app_type, {}).keys())
        current = result.get(app_type, {})
        result[app_type] = {k: v for k, v in current.items() if k in configured_names}
    return result
