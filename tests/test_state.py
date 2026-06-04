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
            "Default": AppState(missing_searched=["1", "2"], last_run="2026-01-15T10:00:00Z"),
            "4K": AppState(cutoff_searched=["3"], last_run="2026-01-15T11:00:00Z"),
        },
        sonarr={
            "Default": AppState(missing_pass=3, last_run="2026-01-15T10:05:00Z"),
        },
        search_log=[],
    )

    save_state(state, state_file)
    loaded = load_state(state_file)

    assert loaded["radarr"]["Default"]["missing_searched"] == ["1", "2"]
    assert loaded["radarr"]["Default"]["cutoff_searched"] == []
    assert loaded["radarr"]["4K"]["cutoff_searched"] == ["3"]
    assert loaded["radarr"]["4K"]["missing_searched"] == []
    assert loaded["sonarr"]["Default"]["missing_pass"] == 3
    assert "missing_cursor" not in loaded["radarr"]["Default"]
    assert "cutoff_cursor" not in loaded["radarr"]["Default"]


def test_v22_state_migration(tmp_path: Path) -> None:
    """v2.2 flat state.json auto-migrates to nested per-instance format with 'Default' key.

    The v2.2 fixture legitimately contains missing_cursor (that's how _is_v22_state_format
    detects the old format), but after _migrate_v22_state + _merge_defaults the legacy
    cursor keys are stripped. Only non-cursor fields survive in the merged output.
    """
    state_file = tmp_path / "state.json"
    v22_state = {
        "radarr": {"missing_cursor": 5, "cutoff_cursor": 2, "last_run": "2026-01-15T10:00:00Z"},
        "sonarr": {"missing_cursor": 3, "cutoff_cursor": 0, "last_run": None},
        "search_log": [],
    }
    state_file.write_text(json.dumps(v22_state))

    loaded = load_state(state_file)

    # Cursor keys are STRIPPED by _merge_defaults (HIGH-1)
    assert "missing_cursor" not in loaded["radarr"]["Default"]
    assert "cutoff_cursor" not in loaded["radarr"]["Default"]
    assert "missing_cursor" not in loaded["sonarr"]["Default"]
    assert "cutoff_cursor" not in loaded["sonarr"]["Default"]
    # Non-cursor fields survive
    assert loaded["radarr"]["Default"]["last_run"] == "2026-01-15T10:00:00Z"
    # Searched-logs default to empty
    assert loaded["radarr"]["Default"]["missing_searched"] == []
    assert loaded["sonarr"]["Default"]["missing_searched"] == []


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
            "Default": AppState(missing_searched=["1"], last_run=None),
            "OldInstance": AppState(missing_searched=["99"], last_run=None),
        },
        sonarr={
            "Default": AppState(missing_searched=[], last_run=None),
        },
        search_log=[],
    )

    cleaned = cleanup_orphaned_instances(state, settings)

    assert "Default" in cleaned["radarr"]
    assert "OldInstance" not in cleaned["radarr"]
    assert "Default" in cleaned["sonarr"]


def test_no_cross_contamination(tmp_path: Path) -> None:
    """Two instances of the same app type do not share or corrupt each other's searched-logs."""
    state_file = tmp_path / "state.json"
    state = TriggarrState(
        radarr={
            "A": AppState(missing_searched=["10", "5"], last_run=None),
            "B": AppState(missing_searched=["20"], cutoff_searched=["15"], last_run=None),
        },
        sonarr={},
        search_log=[],
    )

    # Modify A's log only
    state["radarr"]["A"]["missing_searched"] = ["99"]

    save_state(state, state_file)
    loaded = load_state(state_file)

    assert loaded["radarr"]["A"]["missing_searched"] == ["99"]
    assert loaded["radarr"]["B"]["missing_searched"] == ["20"]  # Unchanged
    assert loaded["radarr"]["B"]["cutoff_searched"] == ["15"]  # Unchanged


def test_default_state_without_settings() -> None:
    """_default_state() with no args returns empty dicts for radarr/sonarr."""
    state = _default_state()

    assert state["radarr"] == {}
    assert state["sonarr"] == {}
    assert state["search_log"] == []


def test_default_state_with_settings() -> None:
    """_default_state(settings) returns per-instance entries with empty searched-logs for each configured instance."""
    from tests.conftest import make_settings

    settings = make_settings()
    state = _default_state(settings)

    assert "Default" in state["radarr"]
    assert state["radarr"]["Default"]["missing_searched"] == []
    assert state["radarr"]["Default"]["cutoff_searched"] == []
    assert state["radarr"]["Default"]["last_run"] is None
    assert "Default" in state["sonarr"]
    assert state["sonarr"]["Default"]["missing_searched"] == []
    # Cursor fields are gone
    assert "missing_cursor" not in state["radarr"]["Default"]
    assert "cutoff_cursor" not in state["radarr"]["Default"]


def test_merge_defaults_nested(tmp_path: Path) -> None:
    """Partial nested state (missing some AppState fields) gets missing fields filled with defaults.

    Legacy cursor keys are stripped; non-cursor fields and new searched-log fields default correctly.
    """
    state_file = tmp_path / "state.json"
    partial_state = {
        "radarr": {
            # Simulates an on-disk state that still has legacy cursor keys
            "Default": {"missing_cursor": 42, "missing_pass": 3},
        },
        "sonarr": {
            "Default": {},
        },
    }
    state_file.write_text(json.dumps(partial_state))

    loaded = load_state(state_file)

    # Legacy cursor keys STRIPPED (HIGH-1)
    assert "missing_cursor" not in loaded["radarr"]["Default"]
    assert "cutoff_cursor" not in loaded["radarr"]["Default"]
    # Non-cursor fields preserved
    assert loaded["radarr"]["Default"]["missing_pass"] == 3
    # Searched-logs filled from defaults
    assert loaded["radarr"]["Default"]["missing_searched"] == []
    assert loaded["radarr"]["Default"]["last_run"] is None
    # Sonarr defaults filled
    assert loaded["sonarr"]["Default"]["missing_searched"] == []
    assert "missing_cursor" not in loaded["sonarr"]["Default"]


# --- Updated existing tests for nested format ---


def test_state_round_trip(tmp_path: Path) -> None:
    """State saved and loaded back retains all searched-log values (nested format)."""
    state_file = tmp_path / "state.json"
    state = TriggarrState(
        radarr={"Default": AppState(missing_searched=["42", "7"], last_run="2026-01-15T10:00:00Z")},
        sonarr={"Default": AppState(cutoff_searched=["100", "25"], last_run="2026-01-15T10:05:00Z")},
        search_log=[{"action": "search", "count": 5}],
    )

    save_state(state, state_file)
    loaded = load_state(state_file)

    assert loaded["radarr"]["Default"]["missing_searched"] == ["42", "7"]
    assert loaded["radarr"]["Default"]["cutoff_searched"] == []
    assert loaded["radarr"]["Default"]["last_run"] == "2026-01-15T10:00:00Z"
    assert loaded["sonarr"]["Default"]["cutoff_searched"] == ["100", "25"]
    assert loaded["sonarr"]["Default"]["missing_searched"] == []
    assert loaded["search_log"] == [{"action": "search", "count": 5}]
    # Cursor fields are gone
    assert "missing_cursor" not in loaded["radarr"]["Default"]
    assert "cutoff_cursor" not in loaded["radarr"]["Default"]


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
        radarr={"Default": AppState(missing_searched=["1"], last_run=None)},
        sonarr={"Default": AppState(cutoff_searched=["3"], last_run=None)},
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
        radarr={"Default": AppState(missing_searched=[], last_run=None)},
        sonarr={"Default": AppState(cutoff_searched=[], last_run=None)},
        search_log=[],
    )

    save_state(state, state_file)

    assert state_file.exists()
    loaded = load_state(state_file)
    assert loaded["radarr"]["Default"]["missing_searched"] == []


def test_state_corrupt_recovers_to_defaults(tmp_path: Path) -> None:
    """Corrupt state file recovers to default state instead of crashing."""
    state_file = tmp_path / "state.json"
    state_file.write_text("not valid json")

    state = load_state(state_file)

    assert state["radarr"] == {}
    assert state["sonarr"] == {}
    assert state["search_log"] == []


def test_state_schema_migration_fills_missing_keys(tmp_path: Path) -> None:
    """Old nested state file missing new keys loads successfully with defaults filled in.

    Legacy cursor keys are stripped; searched-log fields default to empty.
    """
    state_file = tmp_path / "state.json"
    partial_state = {
        "radarr": {"Default": {"missing_cursor": 42, "missing_pass": 5}},
        "sonarr": {"Default": {}},
    }
    state_file.write_text(json.dumps(partial_state))

    state = load_state(state_file)

    # Legacy cursor keys stripped (HIGH-1)
    assert "missing_cursor" not in state["radarr"]["Default"]
    assert "cutoff_cursor" not in state["radarr"]["Default"]
    # Non-cursor fields preserved
    assert state["radarr"]["Default"]["missing_pass"] == 5
    # Searched-logs filled from defaults
    assert state["radarr"]["Default"]["missing_searched"] == []
    assert state["radarr"]["Default"]["last_run"] is None
    # Sonarr filled from defaults
    assert state["sonarr"]["Default"]["missing_searched"] == []
    assert state["sonarr"]["Default"]["last_run"] is None
    # search_log filled from defaults
    assert state["search_log"] == []


def test_state_schema_migration_preserves_all_existing(tmp_path: Path) -> None:
    """A valid nested state file still loads correctly with non-cursor values preserved.

    Legacy cursor keys in the file are stripped on load; all other fields survive.
    """
    state_file = tmp_path / "state.json"
    complete_state = {
        "radarr": {
            "Default": {
                "missing_cursor": 42,  # legacy — will be stripped
                "cutoff_cursor": 7,    # legacy — will be stripped
                "missing_pass": 3,
                "missing_searched": ["1", "2"],
                "last_run": "2026-01-15T10:00:00Z",
            },
        },
        "sonarr": {
            "Default": {
                "missing_cursor": 100,  # legacy — will be stripped
                "cutoff_cursor": 25,    # legacy — will be stripped
                "cutoff_searched": ["99"],
                "last_run": "2026-01-15T10:05:00Z",
            },
        },
        "search_log": [{"action": "search", "count": 5}],
    }
    state_file.write_text(json.dumps(complete_state))

    state = load_state(state_file)

    # Cursor keys stripped (HIGH-1)
    assert "missing_cursor" not in state["radarr"]["Default"]
    assert "cutoff_cursor" not in state["radarr"]["Default"]
    assert "missing_cursor" not in state["sonarr"]["Default"]
    assert "cutoff_cursor" not in state["sonarr"]["Default"]
    # Non-cursor fields preserved
    assert state["radarr"]["Default"]["missing_pass"] == 3
    assert state["radarr"]["Default"]["missing_searched"] == ["1", "2"]
    assert state["radarr"]["Default"]["last_run"] == "2026-01-15T10:00:00Z"
    assert state["sonarr"]["Default"]["cutoff_searched"] == ["99"]
    assert state["sonarr"]["Default"]["last_run"] == "2026-01-15T10:05:00Z"
    assert state["search_log"] == [{"action": "search", "count": 5}]


def test_save_state_cleans_temp_on_replace_failure(tmp_path: Path) -> None:
    """Temp files from failed os.replace calls are cleaned up, not left as orphans."""
    state_file = tmp_path / "state.json"
    state = TriggarrState(
        radarr={"Default": AppState(missing_searched=["1"], last_run=None)},
        sonarr={"Default": AppState(cutoff_searched=["3"], last_run=None)},
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


# ---------------------------------------------------------------------------
# RES-02: last_success field tests
# ---------------------------------------------------------------------------


def test_last_success_persists_round_trip(tmp_path: Path) -> None:
    """last_success value survives save_state -> load_state round-trip intact."""
    state_file = tmp_path / "state.json"
    state = TriggarrState(
        radarr={
            "Default": AppState(
                missing_searched=[],
                cutoff_searched=[],
                last_run="2026-05-31T10:00:00Z",
                last_success="2026-05-31T10:00:00Z",
            )
        },
        sonarr={},
        search_log=[],
    )

    save_state(state, state_file)
    loaded = load_state(state_file)

    assert loaded["radarr"]["Default"]["last_success"] == "2026-05-31T10:00:00Z"


def test_last_success_defaults_to_none_for_fresh_state(tmp_path: Path) -> None:
    """Loading a state JSON without last_success key yields None via _merge_defaults."""
    state_file = tmp_path / "state.json"
    # Old-format state without last_success key
    partial_state = {
        "radarr": {
            "Default": {"missing_cursor": 5, "cutoff_cursor": 2, "last_run": "2026-05-31T09:00:00Z"},
        },
        "sonarr": {},
        "search_log": [],
    }
    state_file.write_text(json.dumps(partial_state))

    loaded = load_state(state_file)

    assert loaded["radarr"]["Default"].get("last_success") is None


# ---------------------------------------------------------------------------
# QUEUE-01/03: searched-log round-trip, default-state, back-compat (Plan 01)
# ---------------------------------------------------------------------------


def test_searched_log_round_trip(tmp_path: Path) -> None:
    """Searched-log fields survive save_state -> load_state intact (QUEUE-01)."""
    state_file = tmp_path / "state.json"
    state = TriggarrState(
        radarr={
            "Default": AppState(
                missing_searched=["1", "2"],
                cutoff_searched=["9"],
                last_run="2026-06-04T10:00:00Z",
            )
        },
        sonarr={},
        search_log=[],
    )

    save_state(state, state_file)
    loaded = load_state(state_file)

    assert loaded["radarr"]["Default"]["missing_searched"] == ["1", "2"]
    assert loaded["radarr"]["Default"]["cutoff_searched"] == ["9"]
    # Cursor fields are gone (removed in Plan 02)
    assert "missing_cursor" not in loaded["radarr"]["Default"]
    assert "cutoff_cursor" not in loaded["radarr"]["Default"]


def test_default_instance_state_has_empty_searched_logs() -> None:
    """_default_instance_state() seeds missing_searched=[] and cutoff_searched=[] (QUEUE-01)."""
    from triggarr.state import _default_instance_state

    state = _default_instance_state()
    assert state["missing_searched"] == []
    assert state["cutoff_searched"] == []
    # Cursor fields removed in Plan 02 (this plan)
    assert "missing_cursor" not in state
    assert "cutoff_cursor" not in state


def test_default_state_with_settings_includes_searched_logs() -> None:
    """A freshly-merged instance via _default_state(settings) carries empty searched-logs."""
    from tests.conftest import make_settings

    settings = make_settings()
    state = _default_state(settings)
    assert state["radarr"]["Default"]["missing_searched"] == []
    assert state["radarr"]["Default"]["cutoff_searched"] == []


def test_back_compat_load_pre_upgrade_state(tmp_path: Path) -> None:
    """Pre-upgrade state.json with cursor keys but no searched-logs loads clean (QUEUE-03).

    Cursor keys are stripped on load by _merge_defaults (HIGH-1).
    Searched-logs default to empty (everything-unsearched semantics).
    missing_pass is carried forward.
    """
    state_file = tmp_path / "state.json"
    pre_upgrade = {
        "radarr": {
            "Default": {
                "missing_cursor": 7,
                "cutoff_cursor": 3,
                "missing_pass": 2,
            }
        }
    }
    state_file.write_text(json.dumps(pre_upgrade))

    loaded = load_state(state_file)

    # New fields default to empty (everything-unsearched semantics)
    assert loaded["radarr"]["Default"]["missing_searched"] == []
    assert loaded["radarr"]["Default"]["cutoff_searched"] == []
    # Pass counter carried forward
    assert loaded["radarr"]["Default"]["missing_pass"] == 2
    # Cursor keys stripped by _merge_defaults (HIGH-1)
    assert "missing_cursor" not in loaded["radarr"]["Default"]
    assert "cutoff_cursor" not in loaded["radarr"]["Default"]


def test_strip_on_load_save_round_trip(tmp_path: Path) -> None:
    """HIGH-1: legacy cursor keys are absent from the WRITTEN JSON after a load→save round-trip.

    Proves that _merge_defaults actively pops cursor keys on load and that save_state
    never writes them back — even when the pre-upgrade state.json carries non-zero
    cursor values alongside existing searched-log entries.
    """
    state_file = tmp_path / "state.json"
    save_file = tmp_path / "saved_state.json"

    # Pre-upgrade state.json: cursor keys present, alongside new searched-log fields
    pre_upgrade = {
        "radarr": {
            "Default": {
                "missing_cursor": 7,
                "cutoff_cursor": 3,
                "missing_pass": 2,
                "missing_searched": ["1"],
            }
        }
    }
    state_file.write_text(json.dumps(pre_upgrade))

    # Load the pre-upgrade file
    loaded = load_state(state_file)

    # Save to a different path so we can inspect what was written
    save_state(loaded, save_file)

    # Re-read the WRITTEN JSON file directly (not the in-memory object)
    with open(save_file, encoding="utf-8") as f:
        written = json.load(f)

    saved_instance = written["radarr"]["Default"]

    # HIGH-1: cursor keys MUST be absent from the written JSON
    assert "missing_cursor" not in saved_instance, (
        "missing_cursor survived load→save round-trip — strip in _merge_defaults is broken"
    )
    assert "cutoff_cursor" not in saved_instance, (
        "cutoff_cursor survived load→save round-trip — strip in _merge_defaults is broken"
    )

    # Non-cursor fields MUST survive
    assert saved_instance["missing_pass"] == 2
    assert saved_instance["missing_searched"] == ["1"]
