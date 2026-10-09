"""Phase 61 App Cards tests.

Locks CARD-01 through CARD-04: app-type colored borders, sectioned layout
with header/body/footer, recessed sub-cards, connection pills with borders,
full-width Search Now with app-colored hover, and unreachable error message.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from triggarr.db import init_db, insert_search_entry
from triggarr.log_buffer import log_buffer
from triggarr.models.config import GeneralConfig
from triggarr.web.routes import STATIC_DIR, router


@pytest.fixture
async def test_app(tmp_path):
    """Build a minimal FastAPI app with mocked state for card testing."""
    log_buffer.clear()
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await init_db(db, db_path)
        await insert_search_entry(db, "Radarr", "missing", "Test Movie")
        app.state.db = db

        app.state.triggarr_state = {
            "radarr": {
                "Default": {
                    "last_run": "2026-04-13T14:32:10Z",
                    "connected": True,
                    "unreachable_since": None,
                    "missing_count": 42,
                    "cutoff_count": 7,
                    "total_items": 100,
                    "missing_pass": 0,
                    "cutoff_pass": 0,
                },
            },
            "sonarr": {
                "Default": {
                    "last_run": None,
                    "connected": None,
                    "unreachable_since": None,
                    "missing_count": None,
                    "cutoff_count": None,
                },
            },
            "lidarr": {
                "Default": {
                    "last_run": None,
                    "connected": None,
                    "unreachable_since": None,
                    "missing_count": None,
                    "cutoff_count": None,
                },
            },
            "search_log": [],
        }

        app.state.settings = make_settings(
            radarr_url="http://radarr:7878",
            radarr_api_key="test-radarr-key",
            radarr_enabled=True,
            sonarr_url="http://sonarr:8989",
            sonarr_api_key="test-sonarr-key",
            sonarr_enabled=True,
            general=GeneralConfig(skip_unreleased=True, tracking_delay_seconds=90),
        )

        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_job.next_run_time = None
        mock_scheduler.get_job.return_value = mock_job
        app.state.scheduler = mock_scheduler

        radarr_client = MagicMock()
        radarr_client.close = AsyncMock()
        sonarr_client = MagicMock()
        sonarr_client.close = AsyncMock()
        lidarr_client = MagicMock()
        lidarr_client.close = AsyncMock()
        app.state.radarr_clients = {"Default": radarr_client}
        app.state.sonarr_clients = {"Default": sonarr_client}
        app.state.lidarr_clients = {"Default": lidarr_client}

        app.state.config_path = tmp_path / "triggarr.toml"
        app.state.state_path = tmp_path / "state.json"
        app.state.search_lock = asyncio.Lock()
        app.state.last_search_time = {}
        app.state.last_health_check = None

        yield app


@pytest.fixture
def client(test_app):
    """Create a TestClient for the test app."""
    return TestClient(test_app)


# ---------------------------------------------------------------------------
# CARD-01: App-type colored left borders
# ---------------------------------------------------------------------------


def test_connected_pill_unified_shape(client, test_app):
    """Connected state shows green pill with rounded shape and border (CARD-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    pill = "rounded text-[10px] font-bold uppercase tracking-wider"
    assert pill in response.text
    assert "bg-triggarr-primary/10 text-triggarr-primary" in response.text
    assert "Connected" in response.text
    assert "border border-triggarr-primary/20" in response.text


def test_unreachable_pill_unified_shape(client, test_app):
    """Unreachable state shows red pill with rounded shape and border (CARD-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    pill = "rounded text-[10px] font-bold uppercase tracking-wider"
    assert pill in response.text
    assert "bg-triggarr-danger/10 text-triggarr-danger" in response.text
    assert "Unreachable" in response.text
    assert "border border-triggarr-danger/20" in response.text


def test_waiting_pill_unified_shape(client, test_app):
    """Waiting state shows muted pill with rounded shape (CARD-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = None
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    pill = "rounded text-[10px] font-bold uppercase tracking-wider"
    assert pill in response.text
    assert "bg-triggarr-border/40 text-triggarr-muted" in response.text
    assert "Waiting..." in response.text


# ---------------------------------------------------------------------------
# CARD-02: Schedule row with Last Run / Next Run
# ---------------------------------------------------------------------------


def test_schedule_row_present(client, test_app):
    """Schedule row shows Last checked and Next Run with font-mono (CARD-02, 78-04/D-04).

    The schedule row uses mb-1 (not mb-4) since the Last successful search row
    below it provides the visual separation; that row itself carries mb-4. The
    exact clock time now lives in the hover-tooltip title (D-05), not inline.
    """
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["last_run"] = "2026-04-13T14:32:10Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Last checked" in response.text
    assert "font-mono text-triggarr-muted mb-1 flex justify-between" in response.text
    assert "14:32:10" in response.text, "Exact time must appear in the title tooltip"


def test_schedule_row_unreachable_no_schedule(client, test_app):
    """When unreachable, schedule row is not shown (body replaced with error message)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Last checked" not in response.text
    assert "API connection failed." in response.text


# ---------------------------------------------------------------------------
# CARD-03: Pass pill badges
# ---------------------------------------------------------------------------


def test_pass_pill_displayed(client, test_app):
    """Pass pill badge shows when pass > 0 (CARD-03)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["missing_pass"] = 2
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "pass 2" in response.text
    assert "text-[10px] bg-triggarr-border/60" in response.text


def test_pass_pill_hidden_when_zero(client, test_app):
    """Pass pill badge hidden when pass is 0 (CARD-03)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["missing_pass"] = 0
    test_app.state.triggarr_state["radarr"]["Default"]["cutoff_pass"] = 0
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "pass 0" not in response.text
    assert "bg-triggarr-border/60" not in response.text


# ---------------------------------------------------------------------------
# CARD-04: Hover elevation
# ---------------------------------------------------------------------------


def test_card_has_hover_classes(client, test_app):
    """All cards have card-hover and shadow-sm classes (CARD-04)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "card-hover" in response.text
    assert "shadow-sm" in response.text


# ---------------------------------------------------------------------------
# CARD-05: Danger stripes on unreachable cards
# ---------------------------------------------------------------------------


def test_unreachable_card_danger_stripes(client, test_app):
    """Unreachable cards show danger stripes (CARD-05)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "danger-stripes" in response.text


def test_connected_card_no_danger_stripes(client, test_app):
    """Connected cards do not show danger stripes (CARD-05)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "danger-stripes" not in response.text


def test_unreachable_card_shows_error_not_stats(client, test_app):
    """Unreachable cards show error message instead of stats grid."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "API connection failed." in response.text
    assert "Missing" not in response.text  # stats grid not shown for unreachable


# ---------------------------------------------------------------------------
# CARD-06: Retry button on unreachable, Search Now on connected
# ---------------------------------------------------------------------------


def test_unreachable_card_retry_button(client, test_app):
    """Unreachable cards show Retry Connection button (CARD-06)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Retry Connection" in response.text
    assert "bg-triggarr-card hover:bg-triggarr-elevated" in response.text
    assert "ph ph-arrows-clockwise" in response.text
    assert "Search Now" not in response.text


def test_connected_card_search_now_button(client, test_app):
    """Connected cards show Search Now button with Phosphor icon (CARD-06)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Search Now" in response.text
    assert "ph ph-magnifying-glass" in response.text
    assert "bg-triggarr-elevated" in response.text
    assert "group-hover:text-triggarr-radarr" in response.text
    assert "Retry Connection" not in response.text


# ---------------------------------------------------------------------------
# CARD-07: Connection pill border styles (replaces dot-pulse)
# ---------------------------------------------------------------------------


def test_connected_pill_has_border(client, test_app):
    """Connected pill has border and tracking-wider text (CARD-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "border border-triggarr-primary/20" in response.text
    assert "tracking-wider" in response.text


def test_unreachable_pill_has_danger_border(client, test_app):
    """Unreachable pill has danger-colored border (CARD-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "border border-triggarr-danger/20" in response.text


# ---------------------------------------------------------------------------
# CARD-01: App-type border colors
# ---------------------------------------------------------------------------


def test_app_card_radarr_border_color(client, test_app):
    """Radarr app card has orange left border (CARD-01)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "border-l-triggarr-radarr" in response.text
    assert "border-l-triggarr-green" not in response.text  # no longer green for connected


def test_app_card_unreachable_border_color(client, test_app):
    """Unreachable app card has red left border regardless of app type (CARD-01)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "border-l-triggarr-danger" in response.text


# ---------------------------------------------------------------------------
# CARD-02: Header border-bottom separator
# ---------------------------------------------------------------------------


def test_card_header_border_bottom(client, test_app):
    """App card header has border-bottom separator (CARD-02)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "p-4 border-b border-triggarr-border/50" in response.text
    assert "text-[15px]" in response.text  # title font size


# ---------------------------------------------------------------------------
# CARD-03: Recessed sub-cards
# ---------------------------------------------------------------------------


def test_recessed_subcards(client, test_app):
    """Missing and Cutoff stats are in recessed sub-cards (CARD-03)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "bg-triggarr-bg/50 border border-triggarr-border/50 rounded p-2.5" in response.text
    assert "text-lg font-bold text-triggarr-text" in response.text
    assert "text-[10px] text-triggarr-muted uppercase tracking-wider" in response.text


# ---------------------------------------------------------------------------
# CARD-04: Search Now app-colored hover
# ---------------------------------------------------------------------------


def test_search_button_app_colored_hover(client, test_app):
    """Search Now button has app-colored hover on icon (CARD-04)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "group-hover:text-triggarr-radarr" in response.text
    assert "ph ph-magnifying-glass" in response.text
    assert "bg-triggarr-elevated" in response.text


# ---------------------------------------------------------------------------
# Unreachable body error message
# ---------------------------------------------------------------------------


def test_unreachable_body_error_message(client, test_app):
    """Unreachable card body shows centered error message with warning icon."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "ph ph-warning-circle" in response.text
    assert "API connection failed." in response.text
    assert "Check API key or network setup." in response.text


# ---------------------------------------------------------------------------
# Footer section
# ---------------------------------------------------------------------------


def test_footer_section_background(client, test_app):
    """Footer section has bg-triggarr-bg/30 background (CARD-04)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "bg-triggarr-bg/30 border-t border-triggarr-border/50" in response.text


# ---------------------------------------------------------------------------
# LAYOUT-01: 3-column grid at xl breakpoint
# ---------------------------------------------------------------------------


def test_dashboard_grid_three_columns(client):
    """Dashboard grid wrapper has xl:grid-cols-3 class (LAYOUT-01)."""
    response = client.get("/")
    assert response.status_code == 200
    assert "xl:grid-cols-3" in response.text


# ---------------------------------------------------------------------------
# CSS rules exist in input.css
# ---------------------------------------------------------------------------


def test_css_has_card_hover_rule():
    """input.css contains .card-hover rule with elevated background."""
    css_path = STATIC_DIR / "css" / "input.css"
    css = css_path.read_text()
    assert ".card-hover" in css
    assert "background-color: #233346" in css


def test_css_has_danger_stripes_rule():
    """input.css contains .danger-stripes rule with gradient."""
    css_path = STATIC_DIR / "css" / "input.css"
    css = css_path.read_text()
    assert ".danger-stripes" in css
    assert "repeating-linear-gradient" in css


# ---------------------------------------------------------------------------
# D-25: Tag warning uses SVG icon
# ---------------------------------------------------------------------------


def test_tag_warning_uses_svg_icon(client, test_app):
    """Tag warning badge uses SVG icon instead of HTML entity (D-25)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["tag_warnings"] = [
        {"field": "missing", "tag": "hdr"},
    ]
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "<svg" in response.text
    assert "&#9888;" not in response.text


# ---------------------------------------------------------------------------
# 78-04: Honest cycle outcomes on the dashboard card (D-03..D-15, R-05)
# ---------------------------------------------------------------------------


def _last_cycle_record(**overrides) -> dict:
    """Build a raw persisted LastCycleRecord dict for template tests (78-04 Task 2)."""
    from datetime import UTC, datetime, timedelta

    record = {
        "grade": "success",
        "accepted": 0,
        "failed": 0,
        "malformed_skipped": 0,
        "persistence_failed": 0,
        "failure_reasons": [],
        "unevaluated": [],
        "eligible": {},
        "fetch_error": None,
        "finished_at": (datetime.now(UTC) - timedelta(minutes=8)).isoformat().replace("+00:00", "Z"),
    }
    record.update(overrides)
    return record


def test_grade_line_success_renders_green_no_detail(client, test_app):
    """Success grade renders counts in green with no detail panel (D-03/D-07)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="success", accepted=5, failed=0,
    )
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Success · 5 accepted, 0 failed ·" in response.text
    assert "text-triggarr-green" in response.text
    assert "data-cycle-detail" not in response.text


def test_grade_line_partial_renders_amber_with_detail(client, test_app):
    """Partial grade renders amber with a grouped, countable detail panel (D-03/D-07/D-09)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="partial",
        accepted=4,
        failed=1,
        failure_reasons=[{"reason": "HTTP 500", "count": 3}],
    )
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Partial · 4 accepted, 1 failed" in response.text
    assert "text-amber-400" in response.text
    assert "data-cycle-detail" in response.text
    assert "Show 1 failure reason" in response.text
    assert "Command rejected by Radarr (HTTP 500)" in response.text
    assert "&times;3" in response.text


def test_grade_line_failed_renders_red_with_detail(client, test_app):
    """Failed grade renders red with a detail panel (D-03/D-07)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="failed",
        accepted=0,
        failed=2,
        failure_reasons=[{"reason": "HTTP 500", "count": 2}],
    )
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Failed · 0 accepted, 2 failed" in response.text
    assert "text-triggarr-danger" in response.text
    assert "data-cycle-detail" in response.text


def test_grade_line_nothing_needed_no_counts_no_detail(client, test_app):
    """Nothing needed searching shows no counts and no detail panel (D-08/D-12)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="nothing_needed", accepted=0, failed=0,
    )
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Nothing needed searching ·" in response.text
    assert "accepted" not in response.text
    assert "data-cycle-detail" not in response.text


def test_grade_line_precedes_tag_warning_and_last_checked(client, test_app):
    """D-03/Pitfall 6: the grade line is the first row, before the tag badge and Last checked."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["tag_warnings"] = [
        {"field": "missing", "tag": "hdr"},
    ]
    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="success", accepted=5, failed=0,
    )
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    grade_index = response.text.index("Success ·")
    tag_index = response.text.index("not found")
    last_checked_index = response.text.index("Last checked")
    assert grade_index < tag_index
    assert grade_index < last_checked_index


def test_relabeled_rows_and_exact_time_title(client, test_app):
    """Rows read 'Last checked:'/'Last successful search:'; old labels gone; Next stays absolute.

    (D-04/D-05)
    """
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["last_run"] = "2026-04-13T14:32:10Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Last checked:" in response.text
    assert "Last successful search:" in response.text
    assert "Last run" not in response.text
    assert "Last OK" not in response.text
    assert 'title="2026-04-13 14:32:10 UTC"' in response.text


def test_last_checked_stale_renders_amber_last_successful_search_never_amber(client, test_app):
    """A stale Last checked is amber; a stale Last successful search is never amber (D-06)."""
    from datetime import UTC, datetime, timedelta

    old_ts = (datetime.now(UTC) - timedelta(minutes=90)).isoformat().replace("+00:00", "Z")
    recent_ts = (datetime.now(UTC) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["last_run"] = old_ts
    test_app.state.triggarr_state["radarr"]["Default"]["last_successful_search"] = old_ts
    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="success", accepted=1, failed=0, finished_at=recent_ts,
    )
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "text-amber-400" in response.text, "Stale Last checked must render amber"
    # Isolate the Last successful search row -- its value span must never carry amber.
    success_row = response.text.split("Last successful search:")[1].split("</div>")[0]
    assert "text-amber-400" not in success_row


def test_not_run_yet_and_last_successful_search_never(client, test_app):
    """No last_cycle and no last_success renders 'Not run yet' and Never (D-14)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"].pop("last_cycle", None)
    test_app.state.triggarr_state["radarr"]["Default"].pop("last_success", None)
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Not run yet" in response.text
    assert "Last successful search:" in response.text
    assert "Never" in response.text


def test_legacy_last_success_label_disappears_after_first_cycle(client, test_app):
    """A pre-upgrade last_success shows '(legacy)' until the first new cycle completes (D-14)."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"].pop("last_cycle", None)
    test_app.state.triggarr_state["radarr"]["Default"]["last_success"] = "2026-01-01T00:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Last success (legacy):" in response.text
    assert "Last successful search:" not in response.text

    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="nothing_needed", accepted=0, failed=0,
    )
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Last success (legacy)" not in response.text


def test_r05_connected_body_never_shows_legacy_value_once_last_cycle_exists(client, test_app):
    """R-05 (connected body): the legacy last_success value never fills the confirmed slot."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="nothing_needed", accepted=0, failed=0,
    )
    test_app.state.triggarr_state["radarr"]["Default"]["last_success"] = "2026-01-01T00:00:00Z"
    test_app.state.triggarr_state["radarr"]["Default"]["last_successful_search"] = None
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Last successful search:" in response.text
    success_row = response.text.split("Last successful search:")[1].split("</div>")[0]
    assert "Never" in success_row
    assert "Last success (legacy)" not in response.text
    assert "2026-01-01 00:00:00 UTC" not in response.text


def test_r05_connected_body_confirmed_time_not_legacy_value(client, test_app):
    """R-05 (connected body): a confirmed last_successful_search renders its own exact time."""
    from datetime import UTC, datetime, timedelta

    recent_ts = (datetime.now(UTC) - timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="success", accepted=1, failed=0,
    )
    test_app.state.triggarr_state["radarr"]["Default"]["last_successful_search"] = recent_ts
    test_app.state.triggarr_state["radarr"]["Default"]["last_success"] = "2026-01-01T00:00:00Z"
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    from triggarr.web.routes import _exact_time_filter

    assert _exact_time_filter(recent_ts) in response.text
    assert "2026-01-01 00:00:00 UTC" not in response.text


def test_r05_unreachable_body_never_shows_legacy_value(client, test_app):
    """R-05 (unreachable body): Last successful search never falls back to the legacy value."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="failed", accepted=0, failed=0, fetch_error="HTTP error: ConnectError",
    )
    test_app.state.triggarr_state["radarr"]["Default"]["last_success"] = "2026-01-01T00:00:00Z"
    test_app.state.triggarr_state["radarr"]["Default"]["last_successful_search"] = None
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Last successful search:" in response.text
    success_row = response.text.split("Last successful search:")[1].split("</div>")[0]
    assert "Never" in success_row
    assert "2026-01-01 00:00:00 UTC" not in response.text


def test_unreachable_card_shows_grade_line_and_last_successful_search(client, test_app):
    """D-13: unreachable card keeps its error body and shows the Failed grade line."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    test_app.state.triggarr_state["radarr"]["Default"]["unreachable_since"] = "2026-04-13T12:00:00Z"
    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="failed", accepted=0, failed=0, fetch_error="HTTP error: ConnectError",
    )
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "API connection failed." in response.text
    assert "Failed · couldn't reach Radarr ·" in response.text
    assert "Last successful search:" in response.text
    assert "Last OK" not in response.text


def test_persistence_warning_renders_and_clears(client, test_app):
    """D-15: persistence_failed renders the amber warning with correct pluralization."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True

    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="success", accepted=2, failed=0, persistence_failed=2,
    )
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "History not saved for 2 searches — stats may undercount" in response.text
    assert "text-triggarr-green" in response.text, "Persistence warning must not change grade color"

    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="success", accepted=1, failed=0, persistence_failed=1,
    )
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "History not saved for 1 search —" in response.text

    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="success", accepted=1, failed=0, persistence_failed=0,
    )
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "History not saved for" not in response.text


def test_reason_text_with_script_tag_is_escaped(client, test_app):
    """D-10: reason text is autoescaped, never rendered as raw HTML."""
    test_app.state.triggarr_state["radarr"]["Default"]["connected"] = True
    test_app.state.triggarr_state["radarr"]["Default"]["last_cycle"] = _last_cycle_record(
        grade="partial",
        accepted=1,
        failed=1,
        failure_reasons=[{"reason": "<script>alert(1)</script>", "count": 1}],
    )
    response = client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;" in response.text


# ---------------------------------------------------------------------------
# D-11 (78-04): detail panel open state survives the 5s htmx refresh
# ---------------------------------------------------------------------------


def test_dashboard_preserves_open_detail_panel_across_refresh(client):
    """Dashboard script remembers and re-opens [data-cycle-detail] panels after each
    htmx outerHTML card refresh, without hx-preserve (which would freeze stale
    failure reasons). This pins the markup/script contract; the live browser
    behavior is confirmed in the milestone-end NAS walkthrough (78-VALIDATION.md).
    """
    response = client.get("/")
    assert response.status_code == 200
    assert "data-cycle-detail" in response.text
    assert "addEventListener('toggle'" in response.text
    assert "openCycleDetails" in response.text
    assert 'nonce="' in response.text
