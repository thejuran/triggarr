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
