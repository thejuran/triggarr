"""Tests for state load/save with atomic write."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from triggarr.state import (
    AppState,
    TriggarrState,
    _default_state,
    _is_v22_state_format,
    cleanup_orphaned_instances,
    load_state,
    save_state,
)

# --- New nested-format tests ---


def test_nested_state_round_trip(tmp_path: Path) -> None:
    """Create state with multiple radarr instances, save and load -- both preserved."""
    state_file = tmp_path / "state.json"
    state = TriggarrState(
        radarr={
            "Default": AppState(missing_cursor=42, cutoff_cursor=7, last_run="2026-01-15T10:00:00Z"),
            "4K": AppState(missing_cursor=10, cutoff_cursor=3, last_run="2026-01-15T11:00:00Z"),
        },
        sonarr={
            "Default": AppState(missing_cursor=100, cutoff_cursor=25, last_run="2026-01-15T10:05:00Z"),
        },
        search_log=[],
    )

    save_state(state, state_file)
    loaded = load_state(state_file)

    assert loaded["radarr"]["Default"]["missing_cursor"] == 42
    assert loaded["radarr"]["Default"]["cutoff_cursor"] == 7
    assert loaded["radarr"]["4K"]["missing_cursor"] == 10
    assert loaded["radarr"]["4K"]["cutoff_cursor"] == 3
    assert loaded["sonarr"]["Default"]["missing_cursor"] == 100
    assert loaded["sonarr"]["Default"]["cutoff_cursor"] == 25


def test_v22_state_migration(tmp_path: Path) -> None:
    """v2.2 flat state.json auto-migrates to nested per-instance format with 'Default' key."""
    state_file = tmp_path / "state.json"
    v22_state = {
        "radarr": {"missing_cursor": 5, "cutoff_cursor": 2, "last_run": "2026-01-15T10:00:00Z"},
        "sonarr": {"missing_cursor": 3, "cutoff_cursor": 0, "last_run": None},
        "search_log": [],
    }
    state_file.write_text(json.dumps(v22_state))

    loaded = load_state(state_file)

    assert loaded["radarr"]["Default"]["missing_cursor"] == 5
    assert loaded["radarr"]["Default"]["cutoff_cursor"] == 2
    assert loaded["radarr"]["Default"]["last_run"] == "2026-01-15T10:00:00Z"
    assert loaded["sonarr"]["Default"]["missing_cursor"] == 3
    assert loaded["sonarr"]["Default"]["cutoff_cursor"] == 0


def test_is_v22_state_format_detection() -> None:
    """_is_v22_state_format returns True for flat format, False for nested."""
    flat = {
        "radarr": {"missing_cursor": 5, "cutoff_cursor": 2},
        "sonarr": {"missing_cursor": 3, "cutoff_cursor": 0},
    }
    assert _is_v22_state_format(flat) is True

    nested = {
        "radarr": {"Default": {"missing_cursor": 5, "cutoff_cursor": 2}},
        "sonarr": {"Default": {"missing_cursor": 3, "cutoff_cursor": 0}},
    }
    assert _is_v22_state_format(nested) is False

    empty = {"radarr": {}, "sonarr": {}}
    assert _is_v22_state_format(empty) is False


def test_orphan_cleanup(tmp_path: Path) -> None:
    """Orphaned instance state entries are removed when they do not match configured instance names."""
    from tests.conftest import make_settings

    settings = make_settings()
    state = TriggarrState(
        radarr={
            "Default": AppState(missing_cursor=5, cutoff_cursor=2, last_run=None),
            "OldInstance": AppState(missing_cursor=99, cutoff_cursor=88, last_run=None),
        },
        sonarr={
            "Default": AppState(missing_cursor=3, cutoff_cursor=0, last_run=None),
        },
        search_log=[],
    )

    cleaned = cleanup_orphaned_instances(state, settings)

    assert "Default" in cleaned["radarr"]
    assert "OldInstance" not in cleaned["radarr"]
    assert "Default" in cleaned["sonarr"]


def test_no_cross_contamination(tmp_path: Path) -> None:
    """Two instances of the same app type do not share or corrupt each other's cursors."""
    state_file = tmp_path / "state.json"
    state = TriggarrState(
        radarr={
            "A": AppState(missing_cursor=10, cutoff_cursor=5, last_run=None),
            "B": AppState(missing_cursor=20, cutoff_cursor=15, last_run=None),
        },
        sonarr={},
        search_log=[],
    )

    # Modify A's cursor only
    state["radarr"]["A"]["missing_cursor"] = 99

    save_state(state, state_file)
    loaded = load_state(state_file)

    assert loaded["radarr"]["A"]["missing_cursor"] == 99
    assert loaded["radarr"]["B"]["missing_cursor"] == 20  # Unchanged
    assert loaded["radarr"]["B"]["cutoff_cursor"] == 15  # Unchanged


def test_default_state_without_settings() -> None:
    """_default_state() with no args returns empty dicts for radarr/sonarr."""
    state = _default_state()

    assert state["radarr"] == {}
    assert state["sonarr"] == {}
    assert state["search_log"] == []


def test_default_state_with_settings() -> None:
    """_default_state(settings) returns per-instance entries at cursor 0 for each configured instance."""
    from tests.conftest import make_settings

    settings = make_settings()
    state = _default_state(settings)

    assert "Default" in state["radarr"]
    assert state["radarr"]["Default"]["missing_cursor"] == 0
    assert state["radarr"]["Default"]["cutoff_cursor"] == 0
    assert state["radarr"]["Default"]["last_run"] is None
    assert "Default" in state["sonarr"]
    assert state["sonarr"]["Default"]["missing_cursor"] == 0


def test_merge_defaults_nested(tmp_path: Path) -> None:
    """Partial nested state (missing some AppState fields) gets missing fields filled with defaults."""
    state_file = tmp_path / "state.json"
    partial_state = {
        "radarr": {
            "Default": {"missing_cursor": 42},
        },
        "sonarr": {
            "Default": {},
        },
    }
    state_file.write_text(json.dumps(partial_state))

    loaded = load_state(state_file)

    # Preserved from file
    assert loaded["radarr"]["Default"]["missing_cursor"] == 42
    # Filled from defaults
    assert loaded["radarr"]["Default"]["cutoff_cursor"] == 0
    assert loaded["radarr"]["Default"]["last_run"] is None
    # Sonarr default filled
    assert loaded["sonarr"]["Default"]["missing_cursor"] == 0
    assert loaded["sonarr"]["Default"]["cutoff_cursor"] == 0


# --- Updated existing tests for nested format ---


def test_state_round_trip(tmp_path: Path) -> None:
    """State saved and loaded back retains all cursor values (nested format)."""
    state_file = tmp_path / "state.json"
    state = TriggarrState(
        radarr={"Default": AppState(missing_cursor=42, cutoff_cursor=7, last_run="2026-01-15T10:00:00Z")},
        sonarr={"Default": AppState(missing_cursor=100, cutoff_cursor=25, last_run="2026-01-15T10:05:00Z")},
        search_log=[{"action": "search", "count": 5}],
    )

    save_state(state, state_file)
    loaded = load_state(state_file)

    assert loaded["radarr"]["Default"]["missing_cursor"] == 42
    assert loaded["radarr"]["Default"]["cutoff_cursor"] == 7
    assert loaded["radarr"]["Default"]["last_run"] == "2026-01-15T10:00:00Z"
    assert loaded["sonarr"]["Default"]["missing_cursor"] == 100
    assert loaded["sonarr"]["Default"]["cutoff_cursor"] == 25
    assert loaded["search_log"] == [{"action": "search", "count": 5}]


def test_state_default_on_missing_file(tmp_path: Path) -> None:
    """Loading from nonexistent path returns default state with empty dicts."""
    state_file = tmp_path / "nonexistent" / "state.json"

    state = load_state(state_file)

    assert state["radarr"] == {}
    assert state["sonarr"] == {}
    assert state["search_log"] == []


def test_state_atomic_write(tmp_path: Path) -> None:
    """After save, state file exists and no .tmp files remain."""
    state_file = tmp_path / "state.json"
    state = TriggarrState(
        radarr={"Default": AppState(missing_cursor=1, cutoff_cursor=2, last_run=None)},
        sonarr={"Default": AppState(missing_cursor=3, cutoff_cursor=4, last_run=None)},
        search_log=[],
    )

    save_state(state, state_file)

    assert state_file.exists()
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0


def test_state_creates_parent_dirs(tmp_path: Path) -> None:
    """Saving to a path with non-existent parents creates them."""
    state_file = tmp_path / "deep" / "nested" / "state.json"
    state = TriggarrState(
        radarr={"Default": AppState(missing_cursor=0, cutoff_cursor=0, last_run=None)},
        sonarr={"Default": AppState(missing_cursor=0, cutoff_cursor=0, last_run=None)},
        search_log=[],
    )

    save_state(state, state_file)

    assert state_file.exists()
    loaded = load_state(state_file)
    assert loaded["radarr"]["Default"]["missing_cursor"] == 0


def test_state_corrupt_recovers_to_defaults(tmp_path: Path) -> None:
    """Corrupt state file recovers to default state instead of crashing."""
    state_file = tmp_path / "state.json"
    state_file.write_text("not valid json")

    state = load_state(state_file)

    assert state["radarr"] == {}
    assert state["sonarr"] == {}
    assert state["search_log"] == []


def test_state_schema_migration_fills_missing_keys(tmp_path: Path) -> None:
    """Old nested state file missing new keys loads successfully with defaults filled in."""
    state_file = tmp_path / "state.json"
    partial_state = {
        "radarr": {"Default": {"missing_cursor": 42}},
        "sonarr": {"Default": {}},
    }
    state_file.write_text(json.dumps(partial_state))

    state = load_state(state_file)

    # Preserved from file
    assert state["radarr"]["Default"]["missing_cursor"] == 42
    # Filled from defaults
    assert state["radarr"]["Default"]["cutoff_cursor"] == 0
    assert state["radarr"]["Default"]["last_run"] is None
    # Sonarr filled from defaults
    assert state["sonarr"]["Default"]["missing_cursor"] == 0
    assert state["sonarr"]["Default"]["cutoff_cursor"] == 0
    assert state["sonarr"]["Default"]["last_run"] is None
    # search_log filled from defaults
    assert state["search_log"] == []


def test_state_schema_migration_preserves_all_existing(tmp_path: Path) -> None:
    """A valid nested state file still loads correctly with all values preserved."""
    state_file = tmp_path / "state.json"
    complete_state = {
        "radarr": {
            "Default": {
                "missing_cursor": 42,
                "cutoff_cursor": 7,
                "last_run": "2026-01-15T10:00:00Z",
            },
        },
        "sonarr": {
            "Default": {
                "missing_cursor": 100,
                "cutoff_cursor": 25,
                "last_run": "2026-01-15T10:05:00Z",
            },
        },
        "search_log": [{"action": "search", "count": 5}],
    }
    state_file.write_text(json.dumps(complete_state))

    state = load_state(state_file)

    assert state["radarr"]["Default"]["missing_cursor"] == 42
    assert state["radarr"]["Default"]["cutoff_cursor"] == 7
    assert state["radarr"]["Default"]["last_run"] == "2026-01-15T10:00:00Z"
    assert state["sonarr"]["Default"]["missing_cursor"] == 100
    assert state["sonarr"]["Default"]["cutoff_cursor"] == 25
    assert state["sonarr"]["Default"]["last_run"] == "2026-01-15T10:05:00Z"
    assert state["search_log"] == [{"action": "search", "count": 5}]


def test_save_state_cleans_temp_on_replace_failure(tmp_path: Path) -> None:
    """Temp files from failed os.replace calls are cleaned up, not left as orphans."""
    state_file = tmp_path / "state.json"
    state = TriggarrState(
        radarr={"Default": AppState(missing_cursor=1, cutoff_cursor=2, last_run=None)},
        sonarr={"Default": AppState(missing_cursor=3, cutoff_cursor=4, last_run=None)},
        search_log=[],
    )

    with (
        patch("triggarr.state.os.replace", side_effect=OSError("mock failure")),
        pytest.raises(OSError, match="mock failure"),
    ):
        save_state(state, state_file)

    # No .tmp files should remain after the failure
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0


# ---------------------------------------------------------------------------
# Invalid JSON state recovery tests (STATE-03)
# ---------------------------------------------------------------------------


def test_state_truncated_json_recovers(tmp_path: Path) -> None:
    """Truncated JSON state file recovers to defaults (JSONDecodeError caught)."""
    state_file = tmp_path / "state.json"
    state_file.write_text('{"radarr":')

    state = load_state(state_file)

    assert state["radarr"] == {}
    assert state["sonarr"] == {}
    assert state["search_log"] == []


def test_state_empty_file_recovers(tmp_path: Path) -> None:
    """Empty state file recovers to defaults (JSONDecodeError caught)."""
    state_file = tmp_path / "state.json"
    state_file.write_text("")

    state = load_state(state_file)

    assert state["radarr"] == {}
    assert state["sonarr"] == {}
    assert state["search_log"] == []


def test_state_wrong_structure_list_crashes(tmp_path: Path) -> None:
    """Valid JSON list (not dict) crashes in _is_v22_state_format with AttributeError.

    load_state catches JSONDecodeError and OSError but not AttributeError.
    A list is valid JSON but wrong structure -- .get() fails on list objects.
    This is a known gap (not ideal but acceptable for a single-user daemon).
    When load_state is hardened to handle non-dict roots, convert this test
    to assert recovery to defaults instead.
    """
    state_file = tmp_path / "state.json"
    state_file.write_text("[1, 2, 3]")

    with pytest.raises(AttributeError):
        load_state(state_file)


def test_state_wrong_nested_type_recovers(tmp_path: Path) -> None:
    """Valid JSON with wrong nested type (radarr as string) recovers gracefully.

    _merge_defaults checks isinstance(loaded_section, dict) at each app key.
    When radarr is a string, the isinstance check fails and defaults are used.
    """
    state_file = tmp_path / "state.json"
    state_file.write_text('{"radarr": "not_a_dict", "sonarr": {}}')

    state = load_state(state_file)

    # radarr is not a dict, so _merge_defaults skips it -> stays default empty
    assert state["radarr"] == {}
    assert state["sonarr"] == {}
    assert state["search_log"] == []
