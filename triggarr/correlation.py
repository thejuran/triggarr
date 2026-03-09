"""Pure correlation functions for matching *arr grabs to triggarr searches.

All functions are pure (no I/O, no DB access). They accept search records
and grab events as inputs and return correlation results. Phase 20 handles
integration -- reading from DB and writing outcome updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from triggarr.models.arr import GrabEvent


@dataclass
class SearchRecord:
    """Minimal search record for correlation (extracted from DB row).

    Attributes:
        history_id: Primary key from search_history table.
        item_id: movieId (Radarr) or seriesId (Sonarr).
        searched_at: When the search was triggered (ISO string parsed to datetime).
        missing_count: Number of missing episodes at search time (Sonarr only, None for Radarr).
    """

    history_id: int
    item_id: int
    searched_at: datetime
    missing_count: int | None = None

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
) -> list[CorrelationResult]:
    """Correlate grab events to triggarr-triggered searches.

    For each search record, find grab events that:
    1. Occurred AFTER the search time
    2. Occurred WITHIN the tracking window (inclusive boundary)

    When multiple searches exist for the same item, only the MOST RECENT
    search gets credit for grabs in its window.

    Args:
        searches: Search records to correlate (all for the same item_id).
        grabs: Grab events from *arr history API (all for the same item).
        tracking_window_minutes: How long after a search to look for grabs.

    Returns:
        One CorrelationResult per search record, with grab_count and matched grabs.
    """
    if not searches:
        return []

    # Parse grab dates once up front.
    parsed_grabs: list[tuple[GrabEvent, datetime]] = [
        (grab, _parse_iso(grab.date)) for grab in grabs
    ]

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


def _parse_iso(date_str: str) -> datetime:
    """Parse an ISO 8601 date string to a timezone-aware datetime."""
    # *arr APIs return "Z" suffix; fromisoformat needs "+00:00"
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
