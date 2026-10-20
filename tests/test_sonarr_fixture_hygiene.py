"""Sanitization and labelling guard for every Sonarr fixture (Phase 81, gap closure).

This test fails the suite if any committed Sonarr fixture leaks a credential,
a real host, a real filesystem path, or an indexer/download identifier, and
pins the one fact the whole gap-closure plan rests on: live Sonarr v5 never
nests an ``episode`` object in its grab-history response.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sonarr"

_HEX40_RE = re.compile(r"[0-9A-Fa-f]{40}")
_BANNED_SUBSTRINGS = ("http", "/home/", "/data/", "usbx", "maguffynas", "apikey")
_BANNED_KEYS = {"downloadUrl", "guid", "torrentInfoHash", "indexer"}


def _fixture_paths() -> list[Path]:
    return sorted(_FIXTURES_DIR.glob("*.json"))


def _walk_keys(obj: Any) -> list[str]:
    """Return every dict key found at any depth in obj."""
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            found.append(key)
            found.extend(_walk_keys(value))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_walk_keys(item))
    return found


def test_every_fixture_is_valid_json_and_labelled() -> None:
    """Every fixture parses as JSON and is explicitly labelled never-live-evidence."""
    paths = _fixture_paths()
    assert paths, "expected at least one fixture under tests/fixtures/sonarr/"

    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)  # fails the test on invalid JSON
        meta = payload["_meta"]
        assert meta["live_evidence"] is False, f"{path.name}: must be live_evidence: false"
        assert meta.get("origin") in {"live-capture", "synthesized"}, (
            f"{path.name}: _meta.origin must be 'live-capture' or 'synthesized', got {meta.get('origin')!r}"
        )


def test_no_fixture_leaks_a_credential_host_or_path() -> None:
    """No fixture contains a 40-hex string, a URL, a sandbox path, host, or API-key marker."""
    for path in _fixture_paths():
        text = path.read_text(encoding="utf-8")

        assert not _HEX40_RE.search(text), f"{path.name}: contains a 40-hex string (info hash or similar secret)"

        lowered = text.lower()
        for marker in _BANNED_SUBSTRINGS:
            assert marker not in lowered, f"{path.name}: contains banned substring {marker!r}"


def test_no_fixture_contains_banned_download_keys() -> None:
    """No fixture contains downloadUrl, guid, torrentInfoHash or indexer keys at any depth."""
    for path in _fixture_paths():
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        keys = set(_walk_keys(payload))
        leaked = keys & _BANNED_KEYS
        assert not leaked, f"{path.name}: contains banned key(s) {leaked!r}"


def test_live_v5_history_has_no_nested_episode_key() -> None:
    """Pins the live finding: Sonarr v5's grab-history response never nests an episode object."""
    with (_FIXTURES_DIR / "history_season_pack_v5.json").open("r", encoding="utf-8") as f:
        payload = json.load(f)

    assert payload["_meta"]["origin"] == "live-capture"
    records = payload["records"]
    assert records, "expected at least one captured history record"
    for record in records:
        assert "episode" not in record, (
            "history_season_pack_v5.json record gained a nested 'episode' key -- "
            "this contradicts the live v5 finding this fixture exists to pin"
        )

    # Whether every history episodeId is present in episodes_v5.json's episode
    # map is an observed fact recorded in 81-10-SUMMARY.md, not enforced here --
    # a missing id is exactly what the per-id GET /api/v3/episode/{id} fallback
    # exists to cover, so this test does not hard-require full coverage.


def test_episodes_v5_series_list_is_well_formed() -> None:
    """episodes_v5.json's series_list for series 1 is non-empty and internally consistent."""
    with (_FIXTURES_DIR / "episodes_v5.json").open("r", encoding="utf-8") as f:
        payload = json.load(f)

    series_list = payload["series_list"]["1"]
    assert series_list, "expected a non-empty episode list for series 1"
    for entry in series_list:
        assert entry["seriesId"] == 1, f"series_list entry {entry.get('id')} has seriesId != 1"
