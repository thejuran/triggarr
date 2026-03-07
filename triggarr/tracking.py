"""Tracking orchestrator -- polls *arr history APIs to detect grabs and resolve search outcomes.

Bridges the correlation engine (triggarr.correlation) with the DB layer (triggarr.db)
to close the loop: searched -> grabbed / partial / unresolved.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import aiosqlite
import httpx
import pydantic
from loguru import logger

from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.correlation import SearchRecord, correlate_grabs
from triggarr.db import get_trackable_entries, update_outcome_and_stats
from triggarr.models.arr import GrabEvent


async def run_tracking_check(
    db: aiosqlite.Connection,
    radarr_client: RadarrClient | None,
    sonarr_client: SonarrClient | None,
    tracking_window_minutes: int,
) -> dict[str, int]:
    """Poll *arr grab history and resolve pending search outcomes.

    Args:
        db: Open aiosqlite connection.
        radarr_client: RadarrClient instance, or None if Radarr is not enabled.
        sonarr_client: SonarrClient instance, or None if Sonarr is not enabled.
        tracking_window_minutes: Minutes after a search to look for grabs.

    Returns:
        Dict with counts: ``{"grabbed": N, "partial": N, "unresolved": N, "errors": N}``.
    """
    counts: dict[str, int] = {"grabbed": 0, "partial": 0, "unresolved": 0, "errors": 0}

    entries = await get_trackable_entries(db)
    if not entries:
        logger.debug("Tracking: no pending entries")
        return counts

    now = datetime.now(UTC)

    # Group entries by (app, item_id) to share one API call per item.
    groups: dict[tuple[str, int], list[dict]] = {}
    for entry in entries:
        key = (entry["app"], entry["item_id"])
        groups.setdefault(key, []).append(entry)

    for (app, item_id), group_entries in groups.items():
        # Pick the right client for this app.
        client = _get_client(app, radarr_client, sonarr_client)
        if client is None:
            continue

        # Fetch grab history -- network errors are non-fatal.
        try:
            grabs = await client.get_grab_history(item_id)
        except (httpx.HTTPError, pydantic.ValidationError) as exc:
            logger.warning(
                "Tracking: failed to fetch grab history for {app} item {id}: {exc}",
                app=app,
                id=item_id,
                exc=exc,
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
                app=app,
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
                app=app,
                queue_type=entry["queue_type"],
                stat_increments=stat_increments,
            )
            counts[outcome] = counts.get(outcome, 0) + 1

    return counts


def _get_client(
    app: str, radarr_client: RadarrClient | None, sonarr_client: SonarrClient | None,
) -> RadarrClient | SonarrClient | None:
    """Return the appropriate client for the given app name, or None."""
    if app == "Radarr":
        return radarr_client
    if app == "Sonarr":
        return sonarr_client
    return None


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
            # Terminal state: partial at window expiry -> increment stats.
            detail = f"partial: {grab_count}/{expected} episodes (window expired)"
            return "partial", detail, {stat_key: grab_count}

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
