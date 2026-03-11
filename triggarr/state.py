"""Atomic JSON state persistence for Triggarr.

State tracks round-robin cursor positions and search history
across container restarts. All writes use atomic write-then-rename
to prevent corruption if the process crashes mid-write.

v2.3: State is nested per-instance -- each configured instance
(e.g., "Default", "4K Radarr") maintains independent cursors.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from loguru import logger

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
    """Per-instance cursor and timing state."""

    missing_cursor: int
    cutoff_cursor: int
    missing_pass: int  # How many times missing queue has wrapped around (0-based, first wrap sets to 1)
    cutoff_pass: int  # How many times cutoff queue has wrapped around (0-based, first wrap sets to 1)
    last_run: str | None  # ISO timestamp
    connected: bool | None  # True after successful fetch, False after failure
    unreachable_since: str | None  # ISO timestamp of first failure, None when healthy
    missing_count: int | None  # Total wanted-missing items (before filtering)
    missing_eligible: int | None  # Items eligible for search (after filtering)
    missing_monitored: int | None  # Monitored items before unreleased filtering (Radarr only)
    missing_searchable: int | None  # Searchable units (Sonarr: seasons after dedup; None for Radarr)
    cutoff_count: int | None  # Total cutoff-unmet items (before filtering)
    cutoff_searchable: int | None  # Searchable units for cutoff (Sonarr: seasons; None for Radarr)


class TriggarrState(TypedDict, total=False):
    """Top-level application state with per-instance cursors.

    radarr and sonarr map instance names to their AppState:
    {"Default": AppState(...), "4K Radarr": AppState(...)}
    """

    radarr: dict[str, AppState]
    sonarr: dict[str, AppState]
    search_log: list[dict]  # deprecated: migrated to SQLite (SRCH-13), kept for migration compat


def _default_instance_state() -> AppState:
    """Return a fresh AppState for a single instance at cursor 0."""
    return AppState(missing_cursor=0, cutoff_cursor=0, last_run=None)


def _default_state(settings: Settings | None = None) -> TriggarrState:
    """Return a fresh default state.

    Without settings: returns empty dicts for radarr/sonarr.
    With settings: populates per-instance entries from configured instance names.
    """
    if settings is None:
        return TriggarrState(radarr={}, sonarr={}, search_log=[])

    state: TriggarrState = TriggarrState(search_log=[])
    for app_type in ("radarr", "sonarr"):
        instances = getattr(settings, app_type, {})
        state[app_type] = {name: _default_instance_state() for name in instances}  # type: ignore[literal-required]
    return state


def _is_v22_state_format(data: dict) -> bool:
    """Check if state uses v2.2 flat format (AppState directly under radarr/sonarr).

    v2.2 format has keys like "missing_cursor" directly under radarr/sonarr.
    v2.3 format has instance names (e.g., "Default") under radarr/sonarr.
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

    for app_key in ("radarr", "sonarr"):
        loaded_section = loaded.get(app_key, {})
        if isinstance(loaded_section, dict):
            merged_section: dict[str, AppState] = {}
            for instance_name, instance_data in loaded_section.items():
                if isinstance(instance_data, dict):
                    merged_section[instance_name] = {**_default_instance_state(), **instance_data}
                else:
                    merged_section[instance_name] = _default_instance_state()
            defaults[app_key] = merged_section

    if "search_log" in loaded and isinstance(loaded["search_log"], list):
        defaults["search_log"] = loaded["search_log"]

    return defaults


def load_state(state_path: Path = STATE_PATH) -> TriggarrState:
    """Load state from a JSON file.

    If the file does not exist, returns a default empty state.
    Automatically migrates v2.2 flat format to v2.3 nested format.

    Args:
        state_path: Path to the state JSON file.

    Returns:
        Parsed state dictionary.
    """
    if not state_path.exists():
        return _default_state()

    try:
        with open(state_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt state file at {} -- resetting to defaults", state_path)
        return _default_state()

    if _is_v22_state_format(data):
        logger.info("Migrating v2.2 state to v2.3 per-instance format")
        data = _migrate_v22_state(data)

    return _merge_defaults(data)


def save_state(state: TriggarrState, state_path: Path = STATE_PATH) -> None:
    """Atomically write state to disk.

    Uses write-to-temp-file then ``os.replace()`` to ensure the state
    file is never left in a partially written state. This prevents
    corruption if the process crashes mid-write.

    Args:
        state: State dictionary to persist.
        state_path: Destination path for the state file.
    """
    parent = state_path.parent
    parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w", dir=parent, suffix=".tmp", delete=False
    ) as tmp:
        json.dump(state, tmp, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())

    try:
        os.replace(tmp.name, state_path)
    except OSError:
        with contextlib.suppress(OSError):
            os.unlink(tmp.name)
        raise


def cleanup_orphaned_instances(state: TriggarrState, settings: Settings) -> TriggarrState:
    """Remove state entries for instances not in current config.

    Compares instance names in state against configured instance names
    in settings, removing any that are no longer configured.

    Args:
        state: Current application state.
        settings: Current application settings.

    Returns:
        State with orphaned instance entries removed.
    """
    for app_type in ("radarr", "sonarr"):
        configured_names = set(getattr(settings, app_type, {}).keys())
        state_section = state.get(app_type, {})  # type: ignore[literal-required]
        orphans = [name for name in state_section if name not in configured_names]
        for orphan in orphans:
            del state_section[orphan]
    return state
