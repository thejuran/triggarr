"""Loader for sanitized Sonarr grab-history fixtures (Phase 81, D-12).

Fixtures live under ``tests/fixtures/sonarr/`` and are synthesized from the
Sonarr v3 OpenAPI HistoryResource/EpisodeResource schema -- never captured
from a live instance. Each fixture file is labelled with ``live_evidence:
false`` so it is never mistaken for live verification evidence; this loader
asserts that label is present.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "sonarr"


def _load(name: str) -> dict[str, Any]:
    path = _FIXTURES_DIR / f"{name}.json"
    with path.open("r", encoding="utf-8") as f:
        payload: dict[str, Any] = json.load(f)
    assert payload["_meta"]["live_evidence"] is False, (
        f"fixture {name!r} must be labelled live_evidence: false (fixtures are never live evidence)"
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
