"""Atomic JSON state persistence for Fetcharr.

State tracks round-robin cursor positions and search history
across container restarts. All writes use atomic write-then-rename
to prevent corruption if the process crashes mid-write.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import TypedDict

from loguru import logger

STATE_PATH = Path("/config/state.json")


class AppState(TypedDict, total=False):
    """Per-app cursor and timing state."""

    missing_cursor: int
    cutoff_cursor: int
    missing_pass: int  # How many times missing queue has wrapped around (1-based)
    cutoff_pass: int  # How many times cutoff queue has wrapped around (1-based)
    last_run: str | None  # ISO timestamp
    connected: bool | None  # True after successful fetch, False after failure
    unreachable_since: str | None  # ISO timestamp of first failure, None when healthy
    missing_count: int | None  # Total wanted-missing items (before filtering)
    cutoff_count: int | None  # Total cutoff-unmet items (before filtering)


class FetcharrState(TypedDict, total=False):
    """Top-level application state."""

    radarr: AppState
    sonarr: AppState
    search_log: list[dict]  # deprecated: migrated to SQLite (SRCH-13), kept for migration compat


def _default_state() -> FetcharrState:
    """Return a fresh default state with both apps at cursor 0."""
    return FetcharrState(
        radarr=AppState(missing_cursor=0, cutoff_cursor=0, last_run=None),
        sonarr=AppState(missing_cursor=0, cutoff_cursor=0, last_run=None),
        search_log=[],
    )


def _merge_defaults(loaded: dict) -> FetcharrState:
    """Merge loaded state over defaults so missing keys get default values.

    Performs a shallow merge per app key. Only merges if the loaded value
    is the correct type (dict for apps, list for search_log).
    """
    defaults = _default_state()

    for app_key in ("radarr", "sonarr"):
        if app_key in loaded and isinstance(loaded[app_key], dict):
            defaults[app_key] = {**defaults[app_key], **loaded[app_key]}

    if "search_log" in loaded and isinstance(loaded["search_log"], list):
        defaults["search_log"] = loaded["search_log"]

    return defaults


def load_state(state_path: Path = STATE_PATH) -> FetcharrState:
    """Load state from a JSON file.

    If the file does not exist, returns a default empty state
    with both apps at cursor position 0.

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

    return _merge_defaults(data)


def save_state(state: FetcharrState, state_path: Path = STATE_PATH) -> None:
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
