"""Rendered-HTML tests for the attribution cutover disclosure and legacy labeling.

Covers Phase 81 Plan 05: the cutover note and historical-estimate labels
(D-01..D-08, R3, R4, S1) on the dashboard and stats-row partial, and
"Legacy -- tracking discontinued" labeling in History and the activity
rail (ATTR-05, D-04).
"""

from __future__ import annotations

import asyncio
import re
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from tests.migration_faults import original_projection
from triggarr.attribution import ensure_cutover_recorded
from triggarr.db import init_db, insert_search_entry
from triggarr.log_buffer import log_buffer
from triggarr.models.config import InstanceConfig
from triggarr.web.routes import STATIC_DIR, router


def _renders_number(text: str, value: int) -> bool:
    """True if *value* appears as a standalone rendered number (tolerates surrounding whitespace/newlines)."""
    return re.search(rf">\s*{value}\s*<", text) is not None


@pytest.fixture(autouse=True)
def _clear_log_buffer():
    """Reset shared log_buffer before and after each test."""
    log_buffer.clear()
    yield
    log_buffer.clear()


@pytest.fixture
async def app_env(tmp_path):
    """Build a minimal FastAPI app with a real, fully-migrated db for rendered-route tests."""
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await init_db(db, db_path)
        app.state.db = db

        app.state.settings = make_settings()
        app.state.triggarr_state = {"search_log": []}

        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_job.next_run_time = None
        mock_scheduler.get_job.return_value = mock_job
        app.state.scheduler = mock_scheduler

        app.state.config_path = tmp_path / "triggarr.toml"
        app.state.state_path = tmp_path / "state.json"
        app.state.search_lock = asyncio.Lock()
        app.state.search_lock_holder = None
        app.state.search_failures = {}
        app.state.persistence_degraded = False
        app.state.last_search_time = {}
        app.state.last_refresh_time = {}
        app.state.last_health_check = None
        app.state.tag_cache = {}

        yield app, db


def _add_instance(settings, app_type: str, name: str, *, instance_id: str, url: str | None = None) -> None:
    """Add (or replace) an enabled instance with an explicit stable id."""
    getattr(settings, app_type)[name] = InstanceConfig(
        url=url or f"http://{app_type}-{name.lower()}:9999",
        api_key="test-key",
        enabled=True,
        id=instance_id,
    )


# ---------------------------------------------------------------------------
# Dashboard (all-apps) disclosure rendering
# ---------------------------------------------------------------------------


async def test_dashboard_global_pre_fix_shows_note_and_lifetime_label_once(app_env):
    """All-apps dashboard with pre-fix data shows the note once and the lifetime label on Series."""
    app, db = app_env
    app.state.settings.sonarr["Default"].id = "sid-s"
    await insert_search_entry(db, "Sonarr", "missing", "Show A", outcome="grabbed", instance_stable_id="sid-s")
    await db.execute("UPDATE search_history SET resolved_at = ? WHERE id = 1", ("2026-01-02T00:00:00Z",))
    await db.execute(
        "UPDATE lifetime_stats SET instance_stable_id = 'sid-s', episodes_found = 5 "
        "WHERE app = 'Sonarr' AND instance_id = 'Default'"
    )
    await db.commit()
    await ensure_cutover_recorded(db, {"Default": "sid-s"})

    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    text = response.text

    assert text.count("Attribution corrected on") == 1
    assert text.count("Lifetime — includes historical estimates") == 1

    series_idx = text.index(">Series<")
    next_scan_idx = text.index(">Next Scan<")
    label_idx = text.index("Lifetime — includes historical estimates")
    assert series_idx < label_idx < next_scan_idx

    stats_row_idx = text.index('id="stats-row"')
    note_idx = text.index("Attribution corrected on")
    assert note_idx > stats_row_idx

    # The note sits in a plain muted paragraph, never a dismiss control.
    fragment = text[note_idx - 200 : note_idx + 200]
    assert "<button" not in fragment.lower()
    assert "dismiss" not in fragment.lower()


async def test_dashboard_fresh_install_no_note_no_label(app_env):
    """A fresh install (cutover recorded with no pre-fix data) shows neither the note nor any label."""
    app, db = app_env
    await ensure_cutover_recorded(db, {})

    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Attribution corrected on" not in response.text
    assert "includes historical estimates" not in response.text.lower()


# ---------------------------------------------------------------------------
# /partials/stats-row per-instance disclosure
# ---------------------------------------------------------------------------


async def test_stats_row_sonarr_instance_with_pre_fix_shows_note_label_and_rate_labels(app_env):
    """A Sonarr instance view with pre-fix data and pre-fix resolved rows shows note, lifetime label,
    and 'Includes historical estimates' beside the Sonarr bar and the overall rate."""
    app, db = app_env
    _add_instance(app.state.settings, "sonarr", "Main", instance_id="sid-main")
    await insert_search_entry(
        db, "Sonarr", "missing", "Show A", outcome="unresolved",
        instance_id="Main", instance_stable_id="sid-main",
    )
    await db.execute(
        "UPDATE lifetime_stats SET instance_stable_id = 'sid-main', episodes_found = 2 "
        "WHERE app = 'Sonarr' AND instance_id = 'Default'"
    )
    await db.commit()
    await ensure_cutover_recorded(db, {"Main": "sid-main"})

    with TestClient(app) as client:
        response = client.get("/partials/stats-row?instance=sonarr/Main")
    assert response.status_code == 200
    text = response.text

    assert "Attribution corrected on" in text
    assert "Lifetime — includes historical estimates" in text
    assert text.count("Includes historical estimates") == 2


async def test_stats_row_sonarr_instance_without_pre_fix_shows_nothing(app_env):
    """A Sonarr instance with no pre-fix data shows none of the note or labels."""
    app, db = app_env
    _add_instance(app.state.settings, "sonarr", "New", instance_id="sid-new")
    await ensure_cutover_recorded(db, {"New": "sid-new"})

    with TestClient(app) as client:
        response = client.get("/partials/stats-row?instance=sonarr/New")
    assert response.status_code == 200
    text = response.text
    assert "Attribution corrected on" not in text
    assert "includes historical estimates" not in text.lower()


async def test_stats_row_radarr_instance_with_global_pre_fix_shows_nothing(app_env):
    """A Radarr instance view shows no note and no lifetime label even with global Sonarr pre-fix data."""
    app, db = app_env
    app.state.settings.radarr["Default"].id = "sid-r"
    app.state.settings.sonarr["Default"].id = "sid-s"
    await insert_search_entry(db, "Sonarr", "missing", "Show A", outcome="grabbed", instance_stable_id="sid-s")
    await db.execute(
        "UPDATE lifetime_stats SET instance_stable_id = 'sid-s', episodes_found = 4 "
        "WHERE app = 'Sonarr' AND instance_id = 'Default'"
    )
    await db.commit()
    await ensure_cutover_recorded(db, {"Default": "sid-s"})

    with TestClient(app) as client:
        response = client.get("/partials/stats-row?instance=radarr/Default")
    assert response.status_code == 200
    text = response.text
    assert "Attribution corrected on" not in text
    assert "includes historical estimates" not in text.lower()


async def test_stats_row_rename_shows_history_and_disclosure(app_env):
    """Renamed instance (S1 a): the view under the new name shows the historical totals and disclosure."""
    app, db = app_env
    await insert_search_entry(
        db, "Sonarr", "missing", "Old Show", outcome="grabbed",
        instance_id="Old", instance_stable_id="sid-a",
    )
    await db.execute("UPDATE search_history SET resolved_at = ? WHERE id = 1", ("2026-01-02T00:00:00Z",))
    await insert_search_entry(
        db, "Sonarr", "missing", "Old Show B", outcome="unresolved",
        instance_id="Old", instance_stable_id="sid-a",
    )
    await db.execute(
        "UPDATE lifetime_stats SET instance_id = 'Old', instance_stable_id = 'sid-a', episodes_found = 7 "
        "WHERE app = 'Sonarr' AND instance_id = 'Default'"
    )
    await db.commit()
    await ensure_cutover_recorded(db, {"Old": "sid-a"})

    # Rename: "New" now owns sid-a; "Old" is a different, clean server reusing the old name.
    _add_instance(app.state.settings, "sonarr", "New", instance_id="sid-a")
    _add_instance(app.state.settings, "sonarr", "Old", instance_id="sid-c")

    with TestClient(app) as client:
        response = client.get("/partials/stats-row?instance=sonarr/New")
    assert response.status_code == 200
    text = response.text
    assert _renders_number(text, 7)
    assert "Attribution corrected on" in text
    assert "Lifetime — includes historical estimates" in text
    assert "Includes historical estimates" in text


async def test_stats_row_name_reuse_shows_nothing_historical(app_env):
    """A different clean server reusing the old name (S1 b) shows nothing historical; stored data untouched."""
    app, db = app_env
    await insert_search_entry(
        db, "Sonarr", "missing", "Old Show", outcome="grabbed",
        instance_id="Old", instance_stable_id="sid-a",
    )
    await db.execute("UPDATE search_history SET resolved_at = ? WHERE id = 1", ("2026-01-02T00:00:00Z",))
    await insert_search_entry(
        db, "Sonarr", "missing", "Old Show B", outcome="unresolved",
        instance_id="Old", instance_stable_id="sid-a",
    )
    await db.execute(
        "UPDATE lifetime_stats SET instance_id = 'Old', instance_stable_id = 'sid-a', episodes_found = 7 "
        "WHERE app = 'Sonarr' AND instance_id = 'Default'"
    )
    await db.commit()
    await ensure_cutover_recorded(db, {"Old": "sid-a"})

    before = await original_projection(db)

    _add_instance(app.state.settings, "sonarr", "New", instance_id="sid-a")
    _add_instance(app.state.settings, "sonarr", "Old", instance_id="sid-c")

    with TestClient(app) as client:
        response = client.get("/partials/stats-row?instance=sonarr/Old")
    assert response.status_code == 200
    text = response.text
    assert "Attribution corrected on" not in text
    assert "includes historical estimates" not in text.lower()

    after = await original_projection(db)
    assert after == before


async def test_stats_row_shared_name_radarr_and_sonarr(app_env):
    """A Radarr instance and a Sonarr instance sharing the display name 'Default' never contaminate
    each other's figures or disclosure (R3)."""
    app, db = app_env
    app.state.settings.radarr["Default"].id = "sid-r"
    app.state.settings.sonarr["Default"].id = "sid-s"
    await insert_search_entry(
        db, "Radarr", "missing", "Movie A", outcome="unresolved",
        instance_id="Default", instance_stable_id="sid-r",
    )
    await insert_search_entry(
        db, "Sonarr", "missing", "Show A", outcome="grabbed",
        instance_id="Default", instance_stable_id="sid-s",
    )
    await db.execute("UPDATE search_history SET resolved_at = ? WHERE id = 2", ("2026-01-02T00:00:00Z",))
    await db.execute(
        "UPDATE lifetime_stats SET instance_stable_id = 'sid-s', episodes_found = 6 "
        "WHERE app = 'Sonarr' AND instance_id = 'Default'"
    )
    await db.commit()
    await ensure_cutover_recorded(db, {"Default": "sid-s"})

    with TestClient(app) as client:
        radarr_response = client.get("/partials/stats-row?instance=radarr/Default")
        sonarr_response = client.get("/partials/stats-row?instance=sonarr/Default")

    assert radarr_response.status_code == 200
    radarr_text = radarr_response.text
    # The combined name-only 50% value must never leak into the Radarr-scoped view.
    assert ">0<" in radarr_text
    assert ">50<" not in radarr_text
    assert "Attribution corrected on" not in radarr_text
    assert "includes historical estimates" not in radarr_text.lower()

    assert sonarr_response.status_code == 200
    sonarr_text = sonarr_response.text
    assert ">100<" in sonarr_text
    assert ">50<" not in sonarr_text
    assert "Attribution corrected on" in sonarr_text
    assert "Lifetime — includes historical estimates" in sonarr_text
    assert "Includes historical estimates" in sonarr_text


async def test_stats_row_legacy_pending_only_no_lifetime_label(app_env):
    """An instance with only a legacy pending row (zero lifetime_stats) shows the note but never
    the lifetime label (R4)."""
    app, db = app_env
    _add_instance(app.state.settings, "sonarr", "Main", instance_id="sid-main")
    await insert_search_entry(
        db, "Sonarr", "missing", "Pending Show", outcome="searched",
        instance_id="Main", instance_stable_id="sid-main",
    )
    await db.commit()
    await ensure_cutover_recorded(db, {"Main": "sid-main"})

    with TestClient(app) as client:
        dashboard_response = client.get("/")
        instance_response = client.get("/partials/stats-row?instance=sonarr/Main")

    assert "Attribution corrected on" in dashboard_response.text
    assert "Lifetime — includes historical estimates" not in dashboard_response.text

    assert "Attribution corrected on" in instance_response.text
    assert "Lifetime — includes historical estimates" not in instance_response.text


def test_stats_row_bare_unknown_name_rejected(app_env):
    """A bare instance name matching no enabled instance is rejected, like the app/name form."""
    app, _db = app_env
    with TestClient(app) as client:
        response = client.get("/partials/stats-row?instance=Nope")
    assert response.status_code == 400


async def test_stats_row_avg_ttg_label_absent_when_not_flagged(app_env):
    """The avg time-to-grab label does not show when the only pre-fix row isn't grabbed+resolved."""
    app, db = app_env
    _add_instance(app.state.settings, "sonarr", "Main", instance_id="sid-main")
    # Pre-fix row is resolved (trips the rate flags) but not 'grabbed', so TTG stays unflagged.
    await insert_search_entry(
        db, "Sonarr", "missing", "Show A", outcome="unresolved",
        instance_id="Main", instance_stable_id="sid-main",
    )
    await db.commit()
    await ensure_cutover_recorded(db, {"Main": "sid-main"})

    with TestClient(app) as client:
        response = client.get("/partials/stats-row?instance=sonarr/Main")
    assert response.status_code == 200
    text = response.text
    # Only the overall-rate and Sonarr-bar labels show; the TTG one does not.
    assert text.count("Includes historical estimates") == 2


async def test_stats_row_avg_ttg_label_present_when_flagged(app_env):
    """The avg time-to-grab label shows when a pre-fix row is grabbed and has resolved_at."""
    app, db = app_env
    _add_instance(app.state.settings, "sonarr", "Main", instance_id="sid-main")
    await insert_search_entry(
        db, "Sonarr", "missing", "Show A", outcome="grabbed",
        instance_id="Main", instance_stable_id="sid-main",
    )
    await db.execute("UPDATE search_history SET resolved_at = ? WHERE id = 1", ("2026-01-02T00:00:00Z",))
    await db.commit()
    # legacy_max_history_id captures id 1 as pre-fix at cutover time.
    await ensure_cutover_recorded(db, {"Main": "sid-main"})

    with TestClient(app) as client:
        response = client.get("/partials/stats-row?instance=sonarr/Main")
    assert response.status_code == 200
    assert response.text.count("Includes historical estimates") == 3


async def test_stats_row_polling_refresh_single_note_element(app_env):
    """A polling refresh never duplicates the note: exactly one #stats-row element, note inside it."""
    app, db = app_env
    app.state.settings.sonarr["Default"].id = "sid-s"
    await insert_search_entry(db, "Sonarr", "missing", "Show A", outcome="grabbed", instance_stable_id="sid-s")
    await db.execute(
        "UPDATE lifetime_stats SET instance_stable_id = 'sid-s', episodes_found = 1 "
        "WHERE app = 'Sonarr' AND instance_id = 'Default'"
    )
    await db.commit()
    await ensure_cutover_recorded(db, {"Default": "sid-s"})

    with TestClient(app) as client:
        response = client.get("/partials/stats-row")
    assert response.status_code == 200
    text = response.text
    assert text.count('id="stats-row"') == 1
    assert "Attribution corrected on" in text


def test_stats_row_existing_mocked_dict_without_new_keys_still_renders(app_env):
    """Existing tests that patch get_dashboard_stats with dicts lacking the new keys still pass."""
    app, _db = app_env
    with (
        TestClient(app) as client,
        patch("triggarr.web.routes.get_dashboard_stats", new_callable=AsyncMock) as mock_stats,
    ):
        mock_stats.return_value = {
            "overall_rate": None, "radarr_rate": None, "sonarr_rate": None, "lidarr_rate": None,
            "movies_found": 0, "movies_updated": 0,
            "episodes_found": 0, "episodes_updated": 0, "albums_found": 0, "albums_updated": 0,
            "avg_time_to_grab_seconds": None,
        }
        response = client.get("/partials/stats-row")
    assert response.status_code == 200
    assert "Includes historical estimates" not in response.text
    assert "Lifetime — includes historical estimates" not in response.text
