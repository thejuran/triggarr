"""Loader for sanitized Sonarr grab-history and episode fixtures (Phase 81, D-12).

Fixtures live under ``tests/fixtures/sonarr/`` and come from one of two
origins, recorded in each file's ``_meta.origin``:

- ``"live-capture"``: a read-only GET response from the isolated Sonarr v5
  sandbox, sanitized (data cleared, download identifiers redacted) before
  being committed. This proves the real v5 response *shape* -- it is still
  never live verification evidence for Phase 81 attribution (D-12); that
  lives in ``81-LIVE-MATRIX.md``.
- ``"synthesized"``: built from the Sonarr v3 OpenAPI
  HistoryResource/EpisodeResource schema, never captured from a live
  instance. Used for scenarios the sandbox cannot produce (the pre-v5
  nested-episode shape, multi-season packs, alternate series orders).

Every fixture, regardless of origin, is labelled ``live_evidence: false`` so
none can ever be mistaken for live verification evidence; this loader asserts
that label and the origin-specific metadata are present.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sonarr"

_VALID_ORIGINS = {"live-capture", "synthesized"}


def _load(name: str) -> dict[str, Any]:
    path = _FIXTURES_DIR / f"{name}.json"
    with path.open("r", encoding="utf-8") as f:
        payload: dict[str, Any] = json.load(f)
    meta = payload["_meta"]

    assert meta["live_evidence"] is False, (
        f"fixture {name!r} must be labelled live_evidence: false (fixtures are never live evidence)"
    )

    origin = meta.get("origin")
    assert origin in _VALID_ORIGINS, (
        f"fixture {name!r} must have _meta.origin in {_VALID_ORIGINS!r}, got {origin!r}"
    )

    if origin == "live-capture":
        assert meta.get("captured_at"), f"fixture {name!r} is live-capture but missing _meta.captured_at"
        assert meta.get("sonarr_version"), f"fixture {name!r} is live-capture but missing _meta.sonarr_version"
        assert meta.get("sanitized_fields"), f"fixture {name!r} is live-capture but missing _meta.sanitized_fields"
        assert meta.get("sanitized") is True, f"fixture {name!r} is live-capture but _meta.sanitized is not True"
    else:
        source = meta.get("source", "")
        assert "synthesized" in source, (
            f"fixture {name!r} is labelled origin: synthesized but _meta.source doesn't say so: {source!r}"
        )

    return payload


def load_sonarr_fixture(name: str) -> list[dict[str, Any]]:
    """Load the ``records`` list from a sanitized Sonarr history fixture."""
    records: list[dict[str, Any]] = _load(name)["records"]
    return records


def load_sonarr_fixture_meta(name: str) -> dict[str, Any]:
    """Load the ``_meta`` object from a sanitized Sonarr history fixture."""
    meta: dict[str, Any] = _load(name)["_meta"]
    return meta


def load_sonarr_episode_fixture(name: str) -> dict[int, dict[str, Any]]:
    """Load the ``episodes`` map (per-episode-id lookups) from a sanitized fixture.

    Keys are coerced to ``int`` (the JSON file stores them as strings).
    """
    episodes: dict[str, dict[str, Any]] = _load(name)["episodes"]
    return {int(episode_id): episode for episode_id, episode in episodes.items()}


def load_sonarr_series_episode_list(name: str, series_id: int) -> list[dict[str, Any]]:
    """Load the series-wide episode list for ``series_id`` from a sanitized fixture."""
    series_list: dict[str, list[dict[str, Any]]] = _load(name)["series_list"]
    episodes: list[dict[str, Any]] = series_list[str(series_id)]
    return episodes
