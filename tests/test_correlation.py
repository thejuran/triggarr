"""Tests for triggarr.correlation -- pure grab-to-search correlation logic."""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

import pytest
from loguru import logger

from triggarr.correlation import SearchRecord, _parse_iso, correlate_grabs
from triggarr.models.arr import GrabEvent


def _search(history_id: int, item_id: int, searched_at: datetime, missing_count: int | None = None) -> SearchRecord:
    """Helper to build a SearchRecord."""
    return SearchRecord(history_id=history_id, item_id=item_id, searched_at=searched_at, missing_count=missing_count)


def _grab(grab_id: int, date: datetime, source: str = "Release.1080p") -> GrabEvent:
    """Helper to build a GrabEvent with ISO date string."""
    return GrabEvent(id=grab_id, date=date.isoformat().replace("+00:00", "Z"), eventType="grabbed", sourceTitle=source)


# -- T=0 base time for all tests --
T0 = datetime(2026, 2, 25, 12, 0, 0, tzinfo=UTC)
WINDOW = 60  # 60-minute tracking window


class TestCorrelateGrabs:
    """Test suite for correlate_grabs pure function."""

    def test_correlate_single_search_single_grab_within_window(self) -> None:
        """One search at T=0, one grab at T+30min, window=60min -> grab_count=1."""
        searches = [_search(1, 100, T0)]
        grabs = [_grab(10, T0 + timedelta(minutes=30))]

        results = correlate_grabs(searches, grabs, WINDOW)

        assert len(results) == 1
        assert results[0].history_id == 1
        assert results[0].grab_count == 1
        assert len(results[0].matched_grabs) == 1
        assert results[0].matched_grabs[0].id == 10

    def test_correlate_single_search_grab_outside_window(self) -> None:
        """One search at T=0, one grab at T+90min, window=60min -> grab_count=0."""
        searches = [_search(1, 100, T0)]
        grabs = [_grab(10, T0 + timedelta(minutes=90))]

        results = correlate_grabs(searches, grabs, WINDOW)

        assert len(results) == 1
        assert results[0].grab_count == 0
        assert results[0].matched_grabs == []

    def test_correlate_single_search_no_grabs(self) -> None:
        """One search at T=0, no grabs -> grab_count=0."""
        searches = [_search(1, 100, T0)]

        results = correlate_grabs(searches, [], WINDOW)

        assert len(results) == 1
        assert results[0].grab_count == 0
        assert results[0].matched_grabs == []

    def test_correlate_grab_at_exact_boundary_inclusive(self) -> None:
        """Grab at exactly T+60min with window=60min -> included (inclusive boundary)."""
        searches = [_search(1, 100, T0)]
        grabs = [_grab(10, T0 + timedelta(minutes=60))]

        results = correlate_grabs(searches, grabs, WINDOW)

        assert results[0].grab_count == 1
        assert results[0].matched_grabs[0].id == 10

    def test_correlate_grab_before_search_time_excluded(self) -> None:
        """Grab at T-10min (before search) -> excluded."""
        searches = [_search(1, 100, T0)]
        grabs = [_grab(10, T0 - timedelta(minutes=10))]

        results = correlate_grabs(searches, grabs, WINDOW)

        assert results[0].grab_count == 0
        assert results[0].matched_grabs == []

    def test_correlate_multiple_grabs_within_window(self) -> None:
        """Three grabs within window -> grab_count=3."""
        searches = [_search(1, 100, T0)]
        grabs = [
            _grab(10, T0 + timedelta(minutes=10)),
            _grab(11, T0 + timedelta(minutes=20)),
            _grab(12, T0 + timedelta(minutes=30)),
        ]

        results = correlate_grabs(searches, grabs, WINDOW)

        assert results[0].grab_count == 3
        assert len(results[0].matched_grabs) == 3
        matched_ids = {g.id for g in results[0].matched_grabs}
        assert matched_ids == {10, 11, 12}

    def test_correlate_most_recent_search_gets_credit(self) -> None:
        """Two searches for same item; grab in overlapping window -> most recent search gets credit."""
        search_a = _search(1, 100, T0)
        search_b = _search(2, 100, T0 + timedelta(minutes=30))
        grabs = [_grab(10, T0 + timedelta(minutes=35))]

        results = correlate_grabs([search_a, search_b], grabs, WINDOW)

        # search B (most recent) gets the grab
        result_a = next(r for r in results if r.history_id == 1)
        result_b = next(r for r in results if r.history_id == 2)
        assert result_b.grab_count == 1
        assert result_a.grab_count == 0

    def test_correlate_multiple_searches_different_windows(self) -> None:
        """Two searches far apart; each gets its own grab."""
        search_a = _search(1, 100, T0)
        search_b = _search(2, 100, T0 + timedelta(minutes=120))
        grabs = [
            _grab(10, T0 + timedelta(minutes=10)),
            _grab(11, T0 + timedelta(minutes=130)),
        ]

        results = correlate_grabs([search_a, search_b], grabs, WINDOW)

        result_a = next(r for r in results if r.history_id == 1)
        result_b = next(r for r in results if r.history_id == 2)
        assert result_a.grab_count == 1
        assert result_a.matched_grabs[0].id == 10
        assert result_b.grab_count == 1
        assert result_b.matched_grabs[0].id == 11

    def test_correlate_returns_one_result_per_search(self) -> None:
        """Three searches -> three results, each with correct history_id."""
        searches = [
            _search(1, 100, T0),
            _search(2, 100, T0 + timedelta(minutes=120)),
            _search(3, 100, T0 + timedelta(minutes=240)),
        ]
        grabs = [_grab(10, T0 + timedelta(minutes=10))]

        results = correlate_grabs(searches, grabs, WINDOW)

        assert len(results) == 3
        result_ids = {r.history_id for r in results}
        assert result_ids == {1, 2, 3}

    def test_correlate_empty_searches_returns_empty(self) -> None:
        """Empty searches list -> empty results."""
        grabs = [_grab(10, T0 + timedelta(minutes=10))]

        results = correlate_grabs([], grabs, WINDOW)

        assert results == []

    def test_correlate_missing_count_passed_through(self) -> None:
        """Sonarr search with missing_count set still correlates grabs correctly."""
        searches = [_search(1, 200, T0, missing_count=5)]
        grabs = [_grab(10, T0 + timedelta(minutes=15))]

        results = correlate_grabs(searches, grabs, WINDOW)

        assert results[0].history_id == 1
        assert results[0].grab_count == 1

    def test_correlate_grabs_skips_malformed_date_keeps_others(self) -> None:
        """A malformed grab date is skipped; the other valid grabs in the group still correlate."""
        searches = [_search(1, 100, T0)]
        grabs = [
            _grab(1, T0 + timedelta(minutes=5)),
            GrabEvent(id=2, date="not-a-date", eventType="grabbed", sourceTitle="Bad.Release"),
            _grab(3, T0 + timedelta(minutes=10)),
        ]

        results = correlate_grabs(searches, grabs, WINDOW)

        assert results[0].grab_count == 2
        matched_ids = {g.id for g in results[0].matched_grabs}
        assert matched_ids == {1, 3}

    def test_correlate_grabs_skips_naive_date(self) -> None:
        """A naive (timezone-less) grab date is skipped exactly like a malformed string."""
        searches = [_search(1, 100, T0)]
        grabs = [
            _grab(1, T0 + timedelta(minutes=5)),
            GrabEvent(id=2, date="2026-02-25T12:05:00", eventType="grabbed", sourceTitle="Naive.Release"),
        ]

        results = correlate_grabs(searches, grabs, WINDOW)

        assert results[0].grab_count == 1
        assert results[0].matched_grabs[0].id == 1

    def test_correlate_grabs_all_malformed_yields_zero(self) -> None:
        """When every grab for a group is malformed, each result has grab_count 0."""
        searches = [_search(1, 100, T0), _search(2, 100, T0 + timedelta(minutes=30))]
        grabs = [
            GrabEvent(id=1, date="not-a-date", eventType="grabbed", sourceTitle="Bad.1"),
            GrabEvent(id=2, date="2026-02-25T12:05:00", eventType="grabbed", sourceTitle="Bad.2"),
        ]

        results = correlate_grabs(searches, grabs, WINDOW)

        assert len(results) == 2
        for result in results:
            assert result.grab_count == 0
            assert result.matched_grabs == []

    def test_correlate_grabs_malformed_logs_warning(self) -> None:
        """A skipped malformed grab logs a WARNING naming the grab id and exception type, never sourceTitle."""
        searches = [_search(1, 100, T0)]
        grabs = [
            GrabEvent(id=2, date="not-a-date", eventType="grabbed", sourceTitle="Secret.Release.Title"),
        ]

        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="WARNING")
        try:
            correlate_grabs(searches, grabs, WINDOW)
            output = sink.getvalue()
        finally:
            logger.remove(handler_id)

        assert "2" in output
        assert "ValueError" in output
        assert "Secret.Release.Title" not in output


class TestParseIso:
    """Test suite for _parse_iso -- ISO 8601 parsing with tz-aware enforcement."""

    def test_parse_iso_z_suffix_is_tz_aware_utc(self) -> None:
        """A 'Z'-suffixed string still parses to a tz-aware UTC datetime (unchanged)."""
        parsed = _parse_iso("2026-02-25T12:00:00Z")

        assert parsed.tzinfo is not None
        assert parsed == T0

    def test_parse_iso_naive_raises(self) -> None:
        """A naive (timezone-less) ISO string raises ValueError."""
        with pytest.raises(ValueError, match="timezone-aware"):
            _parse_iso("2026-02-25T12:00:00")
