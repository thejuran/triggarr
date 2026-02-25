"""Pure correlation functions for matching *arr grabs to fetcharr searches.

All functions are pure (no I/O, no DB access). They accept search records
and grab events as inputs and return correlation results. Phase 20 handles
integration -- reading from DB and writing outcome updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fetcharr.models.arr import GrabEvent


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
    """Correlate grab events to fetcharr-triggered searches.

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
    raise NotImplementedError
