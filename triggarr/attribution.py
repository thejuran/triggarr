"""Attribution cutover recording.

Migration v10 adds the schema (grab_ownership, attribution_cutover,
sonarr_instance_pre_fix, the stable-ID association columns) but never
writes a cutover row itself -- it has no access to the name -> stable-ID
mapping until Plan 04's lifespan wiring builds it from the already-loaded
Settings, and the generic migration signature
(``Callable[[Connection], Awaitable[None]]``) has no room for that extra
argument. ``ensure_cutover_recorded`` lives outside the ``MIGRATIONS``
registry for exactly that reason: it runs once every startup, immediately
after ``init_db()`` has returned, and only *acts* the first time it finds
no existing ``attribution_cutover`` row.

Because the only way schema v10 can be present is for the runner's single
transaction (``triggarr.db._apply_atomic_migration``) to have committed, a
database whose schema_version is still 9 can never be followed by a
cutover -- including right after a failed v10 attempt. A later successful
retry starts this module's own idempotency check from scratch, so the
cutover is still recorded exactly once.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import aiosqlite
from loguru import logger

from triggarr.db import get_schema_version


async def _sonarr_lifetime_has_data(db: aiosqlite.Connection, *, instance_stable_id: str | None) -> bool:
    """Check whether any Sonarr lifetime_stats row (optionally scoped) has a non-zero episode count."""
    if instance_stable_id is None:
        query = "SELECT 1 FROM lifetime_stats WHERE app = 'Sonarr' AND (episodes_found + episodes_updated) > 0"
        params: tuple[str, ...] = ()
    else:
        query = (
            "SELECT 1 FROM lifetime_stats WHERE app = 'Sonarr' AND instance_stable_id = ? "
            "AND (episodes_found + episodes_updated) > 0"
        )
        params = (instance_stable_id,)
    async with db.execute(query, params) as cursor:
        return await cursor.fetchone() is not None


async def _sonarr_history_exists(db: aiosqlite.Connection, *, instance_stable_id: str | None) -> bool:
    """Check whether any Sonarr search_history row (optionally scoped) exists."""
    if instance_stable_id is None:
        query = "SELECT 1 FROM search_history WHERE app = 'Sonarr'"
        params: tuple[str, ...] = ()
    else:
        query = "SELECT 1 FROM search_history WHERE app = 'Sonarr' AND instance_stable_id = ?"
        params = (instance_stable_id,)
    async with db.execute(query, params) as cursor:
        return await cursor.fetchone() is not None


async def ensure_cutover_recorded(db: aiosqlite.Connection, sonarr_instances: Mapping[str, str]) -> None:
    """Record the attribution cutover exactly once, only after schema v10 has committed.

    Persists two separate facts, globally and per stable Sonarr instance ID
    (D-08's "including removed instances" requirement is why the global
    facts are computed across every lifetime_stats/search_history row,
    never filtered to configured instances):

    * has_pre_fix_data / any_pre_fix_sonarr_data -- any pre-fix Sonarr data
      exists at all (a search_history row, or a non-zero lifetime_stats
      row). Drives the disclosure note.
    * lifetime_includes_pre_fix / pre_fix_sonarr_lifetime -- pre-fix data
      actually contributed to a lifetime total (non-zero lifetime_stats).
      Drives only the "Lifetime -- includes historical estimates" label,
      so a legacy-pending-only instance (R4) never mislabels an otherwise
      entirely post-fix lifetime counter.

    Args:
        db: Open aiosqlite connection, already past schema v10.
        sonarr_instances: Mapping of instance display name -> stable
            instance ID (a plain mapping so this module does not depend on
            the Settings model). An entry with an empty stable ID is
            skipped with a warning naming the instance; the cutover row
            itself is still recorded.

    Raises:
        RuntimeError: if the schema has not reached v10 yet -- including
            right after a failed or recovery-blocked migration attempt,
            which the atomic runner always leaves at the previous version.
    """
    version = await get_schema_version(db)
    if version < 10:
        msg = "attribution cutover requires schema v10"
        raise RuntimeError(msg)

    async with db.execute("SELECT 1 FROM attribution_cutover WHERE id = 1") as cursor:
        if await cursor.fetchone() is not None:
            return  # already recorded -- exactly once, idempotent across restarts

    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    instance_count = 0
    any_pre_fix_sonarr_data = False
    try:
        async with db.execute("SELECT COALESCE(MAX(id), 0) FROM search_history") as cursor:
            legacy_max_history_id = (await cursor.fetchone())[0]

        pre_fix_sonarr_lifetime = await _sonarr_lifetime_has_data(db, instance_stable_id=None)
        any_pre_fix_sonarr_data = pre_fix_sonarr_lifetime or await _sonarr_history_exists(
            db, instance_stable_id=None
        )

        # The first write is this INSERT (DML, not DDL), so the driver's
        # implicit transaction covers every write in this function.
        await db.execute(
            "INSERT INTO attribution_cutover "
            "(id, cutover_at, legacy_max_history_id, any_pre_fix_sonarr_data, pre_fix_sonarr_lifetime) "
            "VALUES (1, ?, ?, ?, ?)",
            (now, legacy_max_history_id, int(any_pre_fix_sonarr_data), int(pre_fix_sonarr_lifetime)),
        )

        for name, stable_id in sonarr_instances.items():
            if not stable_id:
                logger.warning(
                    "Attribution cutover: instance {name!r} has no stable ID yet, skipping", name=name
                )
                continue
            lifetime_includes_pre_fix = await _sonarr_lifetime_has_data(db, instance_stable_id=stable_id)
            has_pre_fix_data = lifetime_includes_pre_fix or await _sonarr_history_exists(
                db, instance_stable_id=stable_id
            )
            await db.execute(
                "INSERT OR REPLACE INTO sonarr_instance_pre_fix "
                "(instance_stable_id, has_pre_fix_data, lifetime_includes_pre_fix) VALUES (?, ?, ?)",
                (stable_id, int(has_pre_fix_data), int(lifetime_includes_pre_fix)),
            )
            instance_count += 1

        await db.commit()
    except Exception as exc:
        try:
            await db.rollback()
        except Exception as rollback_exc:
            logger.error(
                "Attribution cutover rollback failed: {rollback_exc} (original: {exc_type})",
                rollback_exc=rollback_exc,
                exc_type=type(exc).__name__,
            )
        logger.error(
            "Attribution cutover failed and was rolled back: {exc_type}",
            exc_type=type(exc).__name__,
        )
        raise

    logger.info(
        "Attribution cutover recorded at {at} (pre-fix Sonarr data: {any_pre_fix}, instances: {count})",
        at=now,
        any_pre_fix=any_pre_fix_sonarr_data,
        count=instance_count,
    )


async def get_attribution_disclosure(
    db: aiosqlite.Connection, *, view_app: str | None = None, sonarr_stable_id: str | None = None,
) -> dict[str, Any]:
    """Resolve the cutover note and lifetime-label booleans for one dashboard view.

    These are two independent facts, each read from its own persisted
    column (R4): the note follows ``any_pre_fix_sonarr_data`` /
    ``has_pre_fix_data`` (any pre-fix Sonarr data exists at all, including
    frozen legacy pending rows); the lifetime label follows
    ``pre_fix_sonarr_lifetime`` / ``lifetime_includes_pre_fix`` (pre-fix
    data actually contributed to a lifetime total). A legacy-pending-only
    instance can show the note without ever showing the lifetime label.

    Args:
        db: Open aiosqlite connection.
        view_app: The dashboard view's app type ("radarr", "sonarr",
            "lidarr") or None for the all-apps view. None reads the global
            facts (which can include retained data from removed
            instances, D-08); "sonarr" reads the per-instance facts for
            sonarr_stable_id; "radarr"/"lidarr" never disclose at all
            (D-02), since neither app's data is ever pre-fix Sonarr data.
        sonarr_stable_id: The selected Sonarr instance's stable ID, only
            meaningful when view_app == "sonarr". Looked up from settings
            by the caller, never taken from the request (T-81-23).

    Returns:
        Dict with keys: show_cutover_note, cutover_date ("YYYY-MM-DD" or
        None), sonarr_lifetime_includes_historical.
    """
    async with db.execute(
        "SELECT cutover_at, any_pre_fix_sonarr_data, pre_fix_sonarr_lifetime FROM attribution_cutover WHERE id = 1"
    ) as cursor:
        cutover_row = await cursor.fetchone()

    if cutover_row is None:
        return {
            "show_cutover_note": False,
            "cutover_date": None,
            "sonarr_lifetime_includes_historical": False,
        }

    cutover_at, global_any_pre_fix, global_lifetime_pre_fix = cutover_row

    if view_app is not None and view_app != "sonarr":
        # Radarr/Lidarr views never disclose, even when the global flag is
        # set (D-02) -- neither app's data is ever pre-fix Sonarr data.
        return {
            "show_cutover_note": False,
            "cutover_date": None,
            "sonarr_lifetime_includes_historical": False,
        }

    if view_app == "sonarr":
        if not sonarr_stable_id:
            return {
                "show_cutover_note": False,
                "cutover_date": None,
                "sonarr_lifetime_includes_historical": False,
            }
        async with db.execute(
            "SELECT has_pre_fix_data, lifetime_includes_pre_fix FROM sonarr_instance_pre_fix "
            "WHERE instance_stable_id = ?",
            (sonarr_stable_id,),
        ) as cursor:
            instance_row = await cursor.fetchone()
        if instance_row is None:
            return {
                "show_cutover_note": False,
                "cutover_date": None,
                "sonarr_lifetime_includes_historical": False,
            }
        show_cutover_note = bool(instance_row[0])
        lifetime_includes_historical = bool(instance_row[1])
    else:
        # All-apps view (view_app is None): read the global facts, which
        # include retained lifetime_stats from removed instances (D-08).
        show_cutover_note = bool(global_any_pre_fix)
        lifetime_includes_historical = bool(global_lifetime_pre_fix)

    return {
        "show_cutover_note": show_cutover_note,
        "cutover_date": cutover_at[:10] if show_cutover_note else None,
        "sonarr_lifetime_includes_historical": lifetime_includes_historical,
    }
