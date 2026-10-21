"""Pure correlation functions for matching *arr grabs to triggarr searches.

All functions are pure (no I/O, no DB access) apart from diagnostic log
lines emitted when a single grab is skipped for a malformed date or an
untrustworthy Sonarr identity. They accept search records and grab events
as inputs and return correlation results. Phase 20 handles integration --
reading from DB and writing outcome updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from loguru import logger

from triggarr.clients.base import _sanitize_exc
from triggarr.models.arr import GrabEvent


@dataclass
class SearchRecord:
    """Minimal search record for correlation (extracted from DB row).

    Attributes:
        history_id: Primary key from search_history table.
        item_id: movieId (Radarr) or seriesId (Sonarr).
        searched_at: When the search was triggered (ISO string parsed to datetime).
        missing_count: Number of missing episodes at search time (Sonarr only, None for Radarr).
        season_number: The canonical Sonarr season this search targeted
            (search_history.season_number). None for Radarr/Lidarr, or
            for a Sonarr search whose season is unknown -- either way the
            search then matches nothing when match_season=True.
    """

    history_id: int
    item_id: int
    searched_at: datetime
    missing_count: int | None = None
    season_number: int | None = None

    def __post_init__(self) -> None:
        if self.searched_at.tzinfo is None:
            msg = "searched_at must be timezone-aware, got naive datetime"
            raise ValueError(msg)


@dataclass
class CorrelationResult:
    """Result of correlating grab history against a single search record.

    Attributes:
        history_id: Primary key of the search_history row.
        grab_count: Number of grab events matched to this search.
        matched_grabs: The GrabEvent objects that were matched.
    """

    history_id: int
    grab_count: int
    matched_grabs: list[GrabEvent]


def correlate_grabs(
    searches: list[SearchRecord],
    grabs: list[GrabEvent],
    tracking_window_minutes: int,
    *,
    match_season: bool = False,
) -> list[CorrelationResult]:
    """Correlate grab events to triggarr-triggered searches.

    For each search record, find grab events that:
    1. Occurred AFTER the search time
    2. Occurred WITHIN the tracking window (inclusive boundary)
    3. When match_season is True, also pass the Sonarr identity gate
       (sonarr_identity_problem) and carry the same canonical season as
       the search.

    When multiple searches exist for the same item, only the MOST RECENT
    search gets credit for grabs in its window.

    Args:
        searches: Search records to correlate (all for the same item_id).
        grabs: Grab events from *arr history API (all for the same item).
        tracking_window_minutes: How long after a search to look for grabs.
        match_season: Sonarr only (default False). When True, a grab must
            also pass sonarr_identity_problem(grab, search.item_id) and
            have a canonical season equal to the search's season_number.
            A grab that fails the identity gate for every search in this
            call is logged once and never matches. Never enabled for
            Radarr/Lidarr, which have no season concept.

    Returns:
        One CorrelationResult per search record, with grab_count and matched grabs.
    """
    if not searches:
        return []

    # Parse grab dates once up front. A malformed or naive date is skipped
    # individually so one bad grab never drops the rest of the group.
    parsed_grabs: list[tuple[GrabEvent, datetime]] = []
    for grab in grabs:
        try:
            parsed_grabs.append((grab, _parse_iso(grab.date)))
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Tracking: skipped grab event {grab_id} -- malformed date ({reason})",
                grab_id=grab.id,
                reason=_sanitize_exc(exc),
            )
            continue

    # Identity-gate pass: a grab untrustworthy for every search in this call
    # is logged once here, independent of time-window matching below.
    if match_season:
        for grab, _grab_time in parsed_grabs:
            reasons = {sonarr_identity_problem(grab, search.item_id) for search in searches}
            if None in reasons:
                continue
            reason = sonarr_identity_problem(grab, searches[0].item_id)
            logger.warning(
                "Tracking: skipped grab event {grab_id} -- {reason}",
                grab_id=grab.id,
                reason=reason,
            )

    # Process searches most-recent-first so the newest search "claims" grabs
    # before older searches can.  This implements the user decision that the
    # most recent search gets credit for overlapping windows.
    sorted_searches = sorted(searches, key=lambda s: s.searched_at, reverse=True)
    claimed: set[int] = set()
    results_by_id: dict[int, CorrelationResult] = {}

    window = timedelta(minutes=tracking_window_minutes)

    for search in sorted_searches:
        window_start = search.searched_at
        window_end = search.searched_at + window
        matched: list[GrabEvent] = []

        for grab, grab_time in parsed_grabs:
            if grab.id in claimed:
                continue
            if match_season:
                if sonarr_identity_problem(grab, search.item_id) is not None:
                    continue
                if (
                    search.season_number is None
                    or grab.episode is None
                    or grab.episode.seasonNumber != search.season_number
                ):
                    continue
            if grab_time >= window_start and grab_time <= window_end:
                matched.append(grab)
                claimed.add(grab.id)

        results_by_id[search.history_id] = CorrelationResult(
            history_id=search.history_id,
            grab_count=len(matched),
            matched_grabs=matched,
        )

    # Return results in the original input order (not the reversed processing order).
    return [results_by_id[s.history_id] for s in searches]


def sonarr_identity_problem(grab: GrabEvent, series_id: int) -> str | None:
    """Return why a Sonarr grab's identity cannot be trusted, or None if it can.

    Checks only Sonarr's own canonical identity fields -- the top-level
    episodeId/seriesId and the nested episode's id/seriesId/seasonNumber.
    Never reads the release title or any alternate-numbering field. Used
    by correlate_grabs's season-aware matching gate, and reused by
    Plan 04's tracking to skip and count untrustworthy grabs.

    Args:
        grab: The grab event to check.
        series_id: The series the grab is being considered against
            (normally the search's item_id).

    Returns:
        None when the grab's identity is trustworthy and matches
        series_id, otherwise one of: "missing episode id", "invalid
        episode id", "missing season", "conflicting episode id",
        "missing series id", "series mismatch".
    """
    if grab.episodeId is None:
        return "missing episode id"
    if grab.episodeId <= 0:
        return "invalid episode id"
    if grab.episode is None or grab.episode.seasonNumber is None or grab.episode.seasonNumber < 0:
        return "missing season"
    if grab.episode.id is not None and grab.episode.id != grab.episodeId:
        return "conflicting episode id"
    if grab.seriesId is None and grab.episode.seriesId is None:
        return "missing series id"
    if grab.seriesId is not None and grab.seriesId != series_id:
        return "series mismatch"
    if grab.episode.seriesId is not None and grab.episode.seriesId != series_id:
        return "series mismatch"
    return None


def _parse_iso(date_str: str) -> datetime:
    """Parse an ISO 8601 date string to a timezone-aware datetime.

    Raises:
        ValueError: If the string is not a valid ISO 8601 date, or parses
            to a naive (timezone-less) datetime.
    """
    # *arr APIs return "Z" suffix; fromisoformat needs "+00:00"
    parsed = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        msg = "grab date must be timezone-aware, got naive datetime"
        raise ValueError(msg)
    return parsed
