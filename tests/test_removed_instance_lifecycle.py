"""End-to-end checks for the removed-instance pending-search lifecycle (RMINST-01..04).

Each scenario chains the real functions (close-out, startup sweep, tracking, the
pending cap, History data and dashboard stats) on a real migrated database for
Sonarr, Radarr and Lidarr. No network: grab history comes from an AsyncMock.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import aiosqlite
import pytest

from triggarr.attribution import ensure_cutover_recorded
from triggarr.db import (
    OUTCOME_INSTANCE_REMOVED,
    PENDING_CAP_MULTIPLIER,
    PendingCapExceeded,
    close_out_orphaned_pending_searches,
    close_out_removed_instance_searches,
    get_dashboard_stats,
    get_search_history,
    get_trackable_entries,
    init_db,
    insert_search_entry,
    update_outcome_and_stats,
)
from triggarr.models.arr import EpisodeSummary, GrabEvent
from triggarr.tracking import run_tracking_check
from triggarr.web import routes

APPS = [
    pytest.param("Sonarr", "episodes_found", id="sonarr"),
    pytest.param("Radarr", "movies_found", id="radarr"),
    pytest.param("Lidarr", "albums_found", id="lidarr"),
]
NAME = "Main"
OLD = "sid-old"
NEW = "sid-new"


async def _db(tmp_path):
    db_path = tmp_path / "lifecycle.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    return db


async def _insert(
    db, app, stable_id, *, outcome="searched", item_id=1, item_name="Item", max_rows=1000, minutes_ago=10,
) -> int:
    await insert_search_entry(
        db,
        app,
        "missing",
        item_name,
        outcome=outcome,
        item_id=item_id,
        season_number=1 if app == "Sonarr" else None,
        missing_count=1 if app == "Sonarr" else None,
        instance_id=NAME,
        instance_stable_id=stable_id,
        max_rows=max_rows,
    )
    async with db.execute("SELECT last_insert_rowid()") as cursor:
        row_id = (await cursor.fetchone())[0]
    ts = (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
    await db.execute("UPDATE search_history SET timestamp = ? WHERE id = ?", (ts, row_id))
    await db.commit()
    return row_id


async def _credit(db, app, stat_col, stable_id, row_id) -> None:
    """Resolve a row as grabbed and give its instance a lifetime credit."""
    await update_outcome_and_stats(
        db,
        row_id,
        "grabbed",
        "credited",
        app=app,
        queue_type="missing",
        instance_id=NAME,
        instance_stable_id=stable_id,
        stat_increments={stat_col: 1},
    )


async def _outcome(db, row_id) -> str:
    async with db.execute("SELECT outcome FROM search_history WHERE id = ?", (row_id,)) as cursor:
        return (await cursor.fetchone())[0]


async def _row(db, row_id) -> dict:
    async with db.execute("SELECT * FROM search_history WHERE id = ?", (row_id,)) as cursor:
        return dict(await cursor.fetchone())


async def _lifetime(db, app, stat_col, stable_id) -> int:
    async with db.execute(
        f"SELECT {stat_col} FROM lifetime_stats WHERE app = ? AND instance_stable_id = ?",  # noqa: S608
        (app, stable_id),
    ) as cursor:
        row = await cursor.fetchone()
    return 0 if row is None else row[0]


def _grab_for(app: str, item_id: int, when: datetime) -> GrabEvent:
    if app == "Sonarr":
        episode = EpisodeSummary(id=item_id, seriesId=item_id, seasonNumber=1)
        return GrabEvent(
            id=item_id,
            date=when.isoformat().replace("+00:00", "Z"),
            eventType="grabbed",
            sourceTitle="Release.1080p",
            episodeId=item_id,
            seriesId=item_id,
            episode=episode,
        )
    return GrabEvent(
        id=item_id, sourceTitle="Release.1080p", date=when.isoformat().replace("+00:00", "Z"), eventType="grabbed",
    )


def _matching_client(app: str) -> AsyncMock:
    """A client whose grab history matches whichever item it is asked about."""
    client = AsyncMock()

    async def _history(item_id, *args, **kwargs):
        return [_grab_for(app, item_id, datetime.now(UTC) - timedelta(minutes=5))]

    client.get_grab_history = AsyncMock(side_effect=_history)
    return client


def _asked_items(client: AsyncMock) -> list[int]:
    return [call.args[0] for call in client.get_grab_history.call_args_list]


@pytest.mark.parametrize(("app", "stat_col"), APPS)
async def test_removed_instance_lifecycle_end_to_end(tmp_path, app, stat_col):
    """Remove an instance with pending searches, reuse its name, track: nothing crosses over."""
    db = await _db(tmp_path)
    searched = await _insert(db, app, OLD, item_id=11, item_name="Old searched")
    partial = await _insert(db, app, OLD, outcome="partial", item_id=12, item_name="Old partial")
    grabbed = await _insert(db, app, OLD, item_id=13, item_name="Old grabbed")
    await _credit(db, app, stat_col, OLD, grabbed)
    old_total = await _lifetime(db, app, stat_col, OLD)
    assert old_total == 1

    closed = await close_out_removed_instance_searches(db, app=app, instance_stable_id=OLD, instance_id=NAME)
    assert closed == 2

    new_row = await _insert(db, app, NEW, item_id=21, item_name="New searched")

    for row_id in (searched, partial):
        row = await _row(db, row_id)
        assert row["outcome"] == OUTCOME_INSTANCE_REMOVED
        assert row["instance_id"] == NAME
    assert await _outcome(db, grabbed) == "grabbed"

    for kwargs in ({"instance_stable_id": OLD}, {"instance_stable_id": NEW}, {"instance_id": NAME}, {}):
        ids = {e["id"] for e in await get_trackable_entries(db, **kwargs)}
        assert searched not in ids
        assert partial not in ids

    client = _matching_client(app)
    counts = await run_tracking_check(db, client, app, NAME, tracking_window_minutes=60, instance_stable_id=NEW)

    assert counts["grabbed"] == 1
    assert _asked_items(client) == [21]
    assert await _outcome(db, new_row) == "grabbed"
    assert await _outcome(db, searched) == OUTCOME_INSTANCE_REMOVED
    assert await _outcome(db, partial) == OUTCOME_INSTANCE_REMOVED
    assert await _lifetime(db, app, stat_col, OLD) == old_total
    assert await _lifetime(db, app, stat_col, NEW) >= 1
    new_view = await get_dashboard_stats(db, app=app, instance_stable_id=NEW)
    assert new_view[stat_col] == await _lifetime(db, app, stat_col, NEW)
    assert new_view[f"{app.lower()}_rate"] == 100.0

    history = await get_search_history(db)
    by_id = {e["id"]: e for e in history["entries"]}
    for row_id in (searched, partial):
        assert by_id[row_id]["instance_id"] == NAME
        assert by_id[row_id]["outcome"] == OUTCOME_INSTANCE_REMOVED
        assert by_id[row_id]["is_legacy"] is False
    await db.close()


@pytest.mark.parametrize(("app", "stat_col"), APPS)
async def test_removed_instance_rows_do_not_block_new_instance_pending_cap(tmp_path, app, stat_col):
    """Closed-out rows leave the pending count, so a same-name instance gets its own full cap."""
    db = await _db(tmp_path)
    cap = PENDING_CAP_MULTIPLIER * 1
    for i in range(cap):
        await _insert(db, app, OLD, item_id=100 + i, max_rows=1)
    with pytest.raises(PendingCapExceeded):
        await _insert(db, app, OLD, item_id=199, max_rows=1)

    await close_out_removed_instance_searches(db, app=app, instance_stable_id=OLD, instance_id=NAME)

    for i in range(cap):
        await _insert(db, app, NEW, item_id=200 + i, max_rows=1)
    with pytest.raises(PendingCapExceeded):
        await _insert(db, app, NEW, item_id=299, max_rows=1)
    await db.close()


@pytest.mark.parametrize(("app", "stat_col"), APPS)
async def test_orphans_from_before_the_release_are_closed_at_startup_and_never_tracked(tmp_path, app, stat_col):
    """The startup sweep closes rows of unconfigured instances and rows with no stable ID."""
    db = await _db(tmp_path)
    if app == "Sonarr":
        await ensure_cutover_recorded(db, {})
    orphan_ids = [await _insert(db, app, OLD, item_id=31)]
    if app != "Sonarr":
        orphan_ids.append(await _insert(db, app, None, item_id=32))

    closed = await close_out_orphaned_pending_searches(db, configured={(app, NEW)})

    assert closed == len(orphan_ids)
    for row_id in orphan_ids:
        assert await _outcome(db, row_id) == OUTCOME_INSTANCE_REMOVED

    client = _matching_client(app)
    counts = await run_tracking_check(db, client, app, NAME, tracking_window_minutes=60, instance_stable_id=NEW)

    assert all(v == 0 for v in counts.values())
    assert _asked_items(client) == []
    assert await _lifetime(db, app, stat_col, NEW) == 0
    assert await _lifetime(db, app, stat_col, OLD) == 0
    await db.close()


@pytest.mark.parametrize(("app", "stat_col"), APPS)
async def test_last_instance_removed_with_failed_close_out_is_repaired_at_next_startup(tmp_path, app, stat_col):
    """With no instance configured any more, the sweep still closes the rows and spares Legacy ones."""
    db = await _db(tmp_path)
    legacy_id = None
    if app == "Sonarr":
        legacy_id = await _insert(db, app, OLD, item_id=40, item_name="Pre-cutover")
        await ensure_cutover_recorded(db, {})
    pending = [await _insert(db, app, OLD, item_id=41), await _insert(db, app, OLD, outcome="partial", item_id=42)]

    closed = await close_out_orphaned_pending_searches(db, configured=set())

    assert closed == len(pending)
    for row_id in pending:
        assert await _outcome(db, row_id) == OUTCOME_INSTANCE_REMOVED
    if legacy_id is not None:
        assert await _outcome(db, legacy_id) == "searched"
        history = await get_search_history(db)
        assert {e["id"]: e for e in history["entries"]}[legacy_id]["is_legacy"] is True

    assert await close_out_orphaned_pending_searches(db, configured=set()) == 0
    await db.close()


async def _removed_instance_with_figures(db, app, stat_col) -> None:
    """Old instance: a credited grab, a failed row, an instance_removed row, plus a legacy name-keyed total."""
    grabbed = await _insert(db, app, OLD, item_id=51, item_name="Old grabbed")
    await _credit(db, app, stat_col, OLD, grabbed)
    await _insert(db, app, OLD, outcome="failed", item_id=52, item_name="Old failed")
    await _insert(db, app, OLD, outcome=OUTCOME_INSTANCE_REMOVED, item_id=53, item_name="Old removed")
    await db.execute(
        f"INSERT INTO lifetime_stats (app, instance_id, instance_stable_id, {stat_col}, last_reset_at) "  # noqa: S608
        "VALUES (?, ?, '', 7, ?)",
        (app, NAME, datetime.now(UTC).isoformat().replace("+00:00", "Z")),
    )
    await db.commit()


@pytest.mark.parametrize(("app", "stat_col"), APPS)
async def test_same_name_instance_never_shows_removed_instance_stats(tmp_path, app, stat_col):
    """D-09: a new instance under an old name shows none of the removed instance's figures."""
    db = await _db(tmp_path)
    await _removed_instance_with_figures(db, app, stat_col)

    stats = await get_dashboard_stats(db, app=app, instance_stable_id=NEW)

    assert stats[f"{app.lower()}_rate"] is None
    assert stats["overall_rate"] is None
    for key in (
        "movies_found", "movies_updated", "episodes_found", "episodes_updated", "albums_found", "albums_updated",
    ):
        assert stats[key] == 0, key
    assert stats["avg_time_to_grab_seconds"] is None
    assert stats["overall_rate_includes_historical"] is False
    assert stats["sonarr_rate_includes_historical"] is False
    assert stats["avg_time_to_grab_includes_historical"] is False

    own = await _insert(db, app, NEW, item_id=61, item_name="New grabbed")
    await _credit(db, app, stat_col, NEW, own)
    stats = await get_dashboard_stats(db, app=app, instance_stable_id=NEW)
    assert stats[f"{app.lower()}_rate"] == 100.0
    assert stats["overall_rate"] == 100.0
    assert stats[stat_col] == 1
    await db.close()


async def test_name_only_stats_helper_mode_matches_old_rows_but_no_view_uses_it(tmp_path):
    """The name-only mode of the database helper matches old rows; no user-reachable view uses it.

    ``get_dashboard_stats(db, instance_id="Main")`` scopes by display name alone, so
    it does include a removed instance's figures. That is a capability of the
    database helper, not a path a user can reach. The stats route resolves a
    selected instance from server-side settings to its app and stable ID
    (``app=..., instance_stable_id=cfg.id``) and answers 400 when the instance is
    unknown, disabled or has no stable ID. With no instance selected it calls
    ``get_dashboard_stats(db, instance_id=instance_id)`` with ``instance_id`` None,
    which is the unfiltered aggregate.
    """
    db = await _db(tmp_path)
    await _removed_instance_with_figures(db, "Radarr", "movies_found")

    by_name = await get_dashboard_stats(db, instance_id=NAME)
    assert by_name["movies_found"] > 0

    source = inspect.getsource(routes.partial_stats_row)
    assert "instance_stable_id=cfg.id" in source
    assert source.count("get_dashboard_stats(") == 2
    assert "instance_id=instance_id" in source
    # The only way instance_id gets a value is from a resolved instance, and an
    # unresolved one is rejected before the call.
    assert "if cfg is None or not cfg.id:" in source
    assert 'return HTMLResponse("Invalid instance parameter", status_code=400)' in source
    await db.close()


@pytest.mark.parametrize(("app", "stat_col"), APPS)
async def test_unfiltered_stats_view_keeps_removed_instance_lifetime_totals(tmp_path, app, stat_col):
    """The unfiltered view is an all-time aggregate that intentionally keeps removed instances' totals.

    With no instance selected the stats view calls ``get_dashboard_stats(db)``. It
    sums lifetime totals across every instance that ever existed; removing an
    instance leaves its lifetime totals there (D-09: lifetime stats are not
    rewritten on removal). The ``instance_removed`` row does not count in the grab
    rate (D-06). This is separate from the per-instance view, where a same-name
    instance sees none of it.
    """
    db = await _db(tmp_path)
    grabbed = await _insert(db, app, OLD, item_id=71, item_name="Old grabbed")
    await _credit(db, app, stat_col, OLD, grabbed)
    await _insert(db, app, OLD, outcome=OUTCOME_INSTANCE_REMOVED, item_id=72, item_name="Old removed")

    stats = await get_dashboard_stats(db)

    assert stats[stat_col] == 1
    assert stats[f"{app.lower()}_rate"] == 100.0  # only the grabbed row counts; the removed one is left out
    await db.close()
