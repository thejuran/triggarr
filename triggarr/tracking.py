"""Tracking orchestrator -- polls *arr history APIs to detect grabs and resolve search outcomes.

Bridges the correlation engine (triggarr.correlation) with the DB layer (triggarr.db)
to close the loop: searched -> grabbed / partial / unresolved.

Sonarr tracking is ownership-aware (ATTR-01, ATTR-02, ATTR-04): pending
searches are selected by the instance's permanent stable ID (not its display
name, so a rename or a different server reusing an old name never misroutes
a pending search), grabs without a trustworthy Sonarr identity are skipped
and counted, grabs already credited to another search are excluded before
correlation, matching requires the same season, and distinct-episode counts
accumulate across tracking checks with ownership committed atomically in the
same transaction as every outcome/stat update.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

import aiosqlite
import httpx
import pydantic
from loguru import logger

from triggarr.clients.base import ArrClient
from triggarr.correlation import SearchRecord, correlate_grabs, sonarr_identity_problem
from triggarr.db import OwnedGrab, get_owned_grabs, get_trackable_entries, update_outcome_and_stats
from triggarr.models.arr import GrabEvent


async def run_tracking_check(
    db: aiosqlite.Connection,
    client: ArrClient,
    app_name: str,
    instance_id: str,
    tracking_window_minutes: int,
    *,
    instance_stable_id: str,
) -> dict[str, int]:
    """Poll *arr grab history and resolve pending search outcomes for one instance.

    Args:
        db: Open aiosqlite connection.
        client: The *arr client for this instance.
        app_name: Application name (e.g. "Radarr", "Sonarr").
        instance_id: Instance display name. Used for Radarr/Lidarr pending-search
            selection and for the name stored on a newly-created legacy
            lifetime_stats row.
        tracking_window_minutes: Minutes after a search to look for grabs.
        instance_stable_id: The instance's permanent Triggarr-assigned ID.
            For Sonarr this is the required key for pending-search selection
            and grab ownership (a rename or a different server reusing an
            old name must never misroute or double-credit a search); an
            empty value refuses to track rather than risk sharing ownership
            across instances. For Radarr/Lidarr it only keys lifetime stat
            increments (falling back to the legacy name-keyed row when
            empty); selection and outcome logic there are unchanged.

    Returns:
        Dict with counts: ``{"grabbed": N, "partial": N, "partial_expired": N,
        "unresolved": N, "errors": N, "identity_skipped": N}``.
        ``identity_skipped`` counts Sonarr grabs dropped for lacking a
        trustworthy episode/season identity; always present, always 0 for
        non-Sonarr apps.
    """
    counts: dict[str, int] = {
        "grabbed": 0,
        "partial": 0,
        "partial_expired": 0,
        "unresolved": 0,
        "errors": 0,
        "identity_skipped": 0,
    }

    if app_name == "Sonarr":
        return await _run_sonarr_tracking_check(
            db,
            client,
            instance_id,
            tracking_window_minutes,
            instance_stable_id=instance_stable_id,
            counts=counts,
        )

    entries = await get_trackable_entries(db, instance_id=instance_id)
    if not entries:
        logger.debug("Tracking[{inst}]: no pending entries", inst=instance_id)
        return counts

    now = datetime.now(UTC)

    # Group entries by item_id to share one API call per item.
    groups: dict[int, list[dict]] = {}
    for entry in entries:
        if entry["app"] != app_name:
            continue  # belt-and-suspenders: instance_id should already scope correctly
        groups.setdefault(entry["item_id"], []).append(entry)

    for item_id, group_entries in groups.items():
        # Fetch grab history -- network errors are non-fatal.
        try:
            grabs = await client.get_grab_history(item_id)
        except (httpx.HTTPError, pydantic.ValidationError) as exc:
            logger.warning(
                "Tracking[{inst}]: failed to fetch grab history for {app} item {id}: {exc}",
                inst=instance_id,
                app=app_name,
                id=item_id,
                exc=(
                    f"HTTP {exc.response.status_code}"
                    if isinstance(exc, httpx.HTTPStatusError)
                    else type(exc).__name__
                ),
            )
            counts["errors"] += len(group_entries)
            continue

        # Build SearchRecord list for correlation.
        searches = [
            SearchRecord(
                history_id=e["id"],
                item_id=e["item_id"],
                searched_at=_parse_timestamp(e["timestamp"]),
                missing_count=e["missing_count"],
            )
            for e in group_entries
        ]

        results = correlate_grabs(searches, grabs, tracking_window_minutes)

        # Resolve each entry using the correlation results.
        for entry, result in zip(group_entries, results, strict=True):
            window_end = _parse_timestamp(entry["timestamp"]) + timedelta(minutes=tracking_window_minutes)
            window_expired = now > window_end

            outcome, detail, stat_increments = _determine_outcome(
                app=app_name,
                queue_type=entry["queue_type"],
                current_outcome=entry["outcome"],
                missing_count=entry["missing_count"],
                grab_count=result.grab_count,
                matched_grabs=result.matched_grabs,
                window_expired=window_expired,
            )

            if outcome is None:
                # Still within window, no action needed.
                continue

            await update_outcome_and_stats(
                db,
                result.history_id,
                outcome,
                detail,
                app=app_name,
                queue_type=entry["queue_type"],
                instance_id=instance_id,
                instance_stable_id=instance_stable_id or None,
                stat_increments=stat_increments,
            )
            counts[outcome] = counts.get(outcome, 0) + 1

    return counts


async def _run_sonarr_tracking_check(
    db: aiosqlite.Connection,
    client: ArrClient,
    instance_id: str,
    tracking_window_minutes: int,
    *,
    instance_stable_id,
    counts: dict[str, int],
) -> dict[str, int]:
    """Ownership-aware Sonarr tracking (ATTR-01, ATTR-02, ATTR-04, R1, R2, R6).

    Selects pending searches by the instance's stable ID (never the display
    name), drops grabs without a trustworthy episode/season identity,
    excludes grabs already owned by another search for the same series,
    requires the matching season, counts distinct Sonarr episodes
    (accumulating ownership from previous checks with newly-matched grabs
    this check), and persists ownership atomically with every outcome/stat
    write.
    """
    if not instance_stable_id:
        # Never share ownership between instances: refuse to track rather
        # than risk crediting the wrong server's searches.
        pending_entries = await get_trackable_entries(db, instance_id=instance_id)
        pending_count = sum(1 for e in pending_entries if e["app"] == "Sonarr")
        logger.error(
            "Tracking[{inst}]: Sonarr instance has no stable ID yet -- skipping {count} pending entries",
            inst=instance_id,
            count=pending_count,
        )
        counts["errors"] += pending_count
        return counts

    entries = await get_trackable_entries(db, instance_stable_id=instance_stable_id)
    if not entries:
        logger.debug("Tracking[{inst}]: no pending entries", inst=instance_id)
        return counts

    now = datetime.now(UTC)

    groups: dict[int, list[dict]] = {}
    for entry in entries:
        if entry["app"] != "Sonarr":
            continue  # belt-and-suspenders: instance_stable_id should already scope correctly
        groups.setdefault(entry["item_id"], []).append(entry)

    for series_id, group_entries in groups.items():
        try:
            grabs = await client.get_grab_history(series_id)
        except (httpx.HTTPError, pydantic.ValidationError) as exc:
            logger.warning(
                "Tracking[{inst}]: failed to fetch grab history for Sonarr item {id}: {exc}",
                inst=instance_id,
                id=series_id,
                exc=(
                    f"HTTP {exc.response.status_code}"
                    if isinstance(exc, httpx.HTTPStatusError)
                    else type(exc).__name__
                ),
            )
            counts["errors"] += len(group_entries)
            continue

        # Identity gate (R2, R6): a grab without a trustworthy Sonarr
        # identity can never be credited, and must never inflate a count.
        trustworthy_grabs: list[GrabEvent] = []
        for grab in grabs:
            reason = sonarr_identity_problem(grab, series_id)
            if reason is not None:
                logger.warning(
                    "Tracking[{inst}]: skipped grab {grab_id} for series {series} -- {reason}",
                    inst=instance_id,
                    grab_id=grab.id,
                    series=series_id,
                    reason=reason,
                )
                counts["identity_skipped"] += 1
                continue
            trustworthy_grabs.append(grab)

        # Exclude grabs already owned by any search for this series (ATTR-02):
        # never re-credit a grab, regardless of which search originally
        # claimed it or whether that search's history row still exists.
        owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id=instance_stable_id, series_id=series_id)
        owned_grab_ids = {o.grab_id for o in owned}
        candidate_grabs = [g for g in trustworthy_grabs if g.id not in owned_grab_ids]

        searches = [
            SearchRecord(
                history_id=e["id"],
                item_id=e["item_id"],
                searched_at=_parse_timestamp(e["timestamp"]),
                missing_count=e["missing_count"],
                season_number=e["season_number"],
            )
            for e in group_entries
        ]

        results = correlate_grabs(searches, candidate_grabs, tracking_window_minutes, match_season=True)

        for entry, result in zip(group_entries, results, strict=True):
            window_end = _parse_timestamp(entry["timestamp"]) + timedelta(minutes=tracking_window_minutes)
            window_expired = now > window_end

            previous = [o for o in owned if o.history_id == entry["id"]]
            new_grabs = result.matched_grabs

            # Distinct-episode accumulation (ATTR-04): the Sonarr episodeId
            # is the only counting key -- a repeat grab of the same episode
            # (season-pack re-grab) must never count twice, and no grab-id
            # fallback is ever used.
            episode_ids: set[int] = set()
            for record in previous:
                if record.episode_id is not None:
                    episode_ids.add(record.episode_id)
                else:
                    logger.warning(
                        "Tracking[{inst}]: owned grab {grab_id} has no episode id, ignoring for count",
                        inst=instance_id,
                        grab_id=record.grab_id,
                    )
            for grab in new_grabs:
                if grab.episodeId is not None:
                    episode_ids.add(grab.episodeId)
            grab_count = len(episode_ids)

            outcome, detail, stat_increments = _determine_outcome(
                app="Sonarr",
                queue_type=entry["queue_type"],
                current_outcome=entry["outcome"],
                missing_count=entry["missing_count"],
                grab_count=grab_count,
                matched_grabs=new_grabs,
                window_expired=window_expired,
            )

            owned_grabs = [
                OwnedGrab(
                    grab_id=grab.id,
                    episode_id=grab.episodeId,
                    series_id=series_id,
                    season_number=entry["season_number"],
                )
                for grab in new_grabs
            ]

            if outcome is None:
                # Still within window and not yet fully resolved. When new
                # grabs were matched this check, persist their ownership and
                # the updated progress detail now (in the same kind of
                # transaction as a resolution) so no other search can claim
                # them before the next check -- but never rewrite a row when
                # nothing new was found.
                if owned_grabs and entry["outcome"] == "partial" and not window_expired:
                    expected = entry["missing_count"] if entry["missing_count"] is not None else 0
                    progress_detail = f"partial: {grab_count}/{expected} episodes"
                    try:
                        await update_outcome_and_stats(
                            db,
                            entry["id"],
                            "partial",
                            progress_detail,
                            app="Sonarr",
                            queue_type=entry["queue_type"],
                            instance_id=instance_id,
                            instance_stable_id=instance_stable_id,
                            stat_increments=None,
                            owned_grabs=owned_grabs,
                        )
                    except sqlite3.IntegrityError:
                        logger.warning(
                            "Tracking[{inst}]: grab already owned for history_id {hid}",
                            inst=instance_id,
                            hid=entry["id"],
                        )
                        counts["errors"] += 1
                continue

            try:
                await update_outcome_and_stats(
                    db,
                    result.history_id,
                    outcome,
                    detail,
                    app="Sonarr",
                    queue_type=entry["queue_type"],
                    instance_id=instance_id,
                    instance_stable_id=instance_stable_id,
                    stat_increments=stat_increments,
                    owned_grabs=owned_grabs,
                )
            except sqlite3.IntegrityError:
                logger.warning(
                    "Tracking[{inst}]: grab already owned for history_id {hid}",
                    inst=instance_id,
                    hid=entry["id"],
                )
                counts["errors"] += 1
                continue
            counts[outcome] = counts.get(outcome, 0) + 1

    return counts


def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO timestamp string to a timezone-aware datetime."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _determine_outcome(
    *,
    app: str,
    queue_type: str,
    current_outcome: str,
    missing_count: int | None,
    grab_count: int,
    matched_grabs: list[GrabEvent],
    window_expired: bool,
) -> tuple[str | None, str, dict[str, int] | None]:
    """Determine the new outcome for a single search entry.

    Returns:
        Tuple of (outcome, detail, stat_increments). outcome is None
        if no update should be made (still waiting within window).
    """
    if app == "Radarr":
        return _radarr_outcome(queue_type, grab_count, matched_grabs, window_expired)
    if app == "Sonarr":
        return _sonarr_outcome(queue_type, current_outcome, missing_count, grab_count, matched_grabs, window_expired)
    if app == "Lidarr":
        return _lidarr_outcome(queue_type, grab_count, matched_grabs, window_expired)
    return None, "", None


def _radarr_outcome(
    queue_type: str,
    grab_count: int,
    matched_grabs: list[GrabEvent],
    window_expired: bool,
) -> tuple[str | None, str, dict[str, int] | None]:
    """Radarr outcome logic -- binary: grabbed or unresolved."""
    if grab_count > 0:
        source = (matched_grabs[0].sourceTitle or "unknown")[:200]
        detail = f"grabbed: {source}"
        stat_key = "movies_found" if queue_type == "missing" else "movies_updated"
        return "grabbed", detail, {stat_key: 1}

    if window_expired:
        return "unresolved", "no grabs detected within tracking window", None

    # Still within window, no grabs yet -- keep waiting.
    return None, "", None


def _sonarr_outcome(
    queue_type: str,
    current_outcome: str,
    missing_count: int | None,
    grab_count: int,
    matched_grabs: list[GrabEvent],
    window_expired: bool,
) -> tuple[str | None, str, dict[str, int] | None]:
    """Sonarr outcome logic -- three-state: grabbed, partial, or unresolved."""
    expected = missing_count if missing_count is not None else 0

    stat_key = "episodes_found" if queue_type == "missing" else "episodes_updated"

    # missing_count was None -- any grab means fully resolved.
    if expected == 0:
        if grab_count > 0:
            detail = f"grabbed: {grab_count} episodes"
            return "grabbed", detail, {stat_key: grab_count}
        if window_expired:
            return "unresolved", "no grabs detected within tracking window", None
        return None, "", None

    # All episodes resolved.
    if grab_count >= expected:
        detail = f"grabbed: {grab_count}/{expected} episodes"
        return "grabbed", detail, {stat_key: grab_count}

    # Some but not all episodes grabbed.
    if grab_count > 0 and grab_count < expected:
        # Partial grabs exist.
        if window_expired:
            if current_outcome == "partial_expired":
                # Already resolved as terminal partial -- no-op to prevent
                # double-counting stats on subsequent tracking cycles.
                return None, "", None
            # Terminal state: partial at window expiry -> increment stats once.
            detail = f"partial: {grab_count}/{expected} episodes (window expired)"
            return "partial_expired", detail, {stat_key: grab_count}

        if current_outcome == "searched":
            # First detection of partial grabs.
            detail = f"partial: {grab_count}/{expected} episodes"
            return "partial", detail, None

        # Already partial, not yet expired -- no-op (keep waiting).
        return None, "", None

    # No grabs at all.
    if window_expired:
        return "unresolved", "no grabs detected within tracking window", None

    # Still within window, no grabs yet -- keep waiting.
    return None, "", None


def _lidarr_outcome(
    queue_type: str,
    grab_count: int,
    matched_grabs: list[GrabEvent],
    window_expired: bool,
) -> tuple[str | None, str, dict[str, int] | None]:
    """Lidarr outcome logic -- binary: grabbed or unresolved.

    Albums are atomic search units (like Radarr movies), so the outcome
    is straightforward: either the album was grabbed or it wasn't.
    """
    if grab_count > 0:
        source = (matched_grabs[0].sourceTitle or "unknown")[:200]
        detail = f"grabbed: {source}"
        stat_key = "albums_found" if queue_type == "missing" else "albums_updated"
        return "grabbed", detail, {stat_key: 1}

    if window_expired:
        return "unresolved", "no grabs detected within tracking window", None

    # Still within window, no grabs yet -- keep waiting.
    return None, "", None
