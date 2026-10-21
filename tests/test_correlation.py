"""Tests for triggarr.correlation -- pure grab-to-search correlation logic."""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

import pytest
from loguru import logger

from tests.sonarr_fixtures import load_sonarr_fixture
from triggarr.correlation import SearchRecord, _parse_iso, correlate_grabs, sonarr_identity_problem
from triggarr.models.arr import EpisodeSummary, GrabEvent


def _search(
    history_id: int,
    item_id: int,
    searched_at: datetime,
    missing_count: int | None = None,
    season_number: int | None = None,
) -> SearchRecord:
    """Helper to build a SearchRecord."""
    return SearchRecord(
        history_id=history_id,
        item_id=item_id,
        searched_at=searched_at,
        missing_count=missing_count,
        season_number=season_number,
    )


def _grab(
    grab_id: int,
    date: datetime,
    source: str = "Release.1080p",
    season_number: int | None = None,
    episode_id: int | None = None,
    series_id: int | None = None,
) -> GrabEvent:
    """Helper to build a GrabEvent with ISO date string, optionally with Sonarr episode identity."""
    episode = (
        EpisodeSummary(id=episode_id, seriesId=series_id, seasonNumber=season_number)
        if season_number is not None
        else None
    )
    return GrabEvent(
        id=grab_id,
        date=date.isoformat().replace("+00:00", "Z"),
        eventType="grabbed",
        sourceTitle=source,
        episodeId=episode_id,
        seriesId=series_id,
        episode=episode,
    )


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


class TestSeasonAwareCorrelation:
    """Season-aware Sonarr correlation and the sonarr_identity_problem gate (ATTR-01, SONARRV5-03)."""

    def test_correlate_season_aware_matches_correct_season(self) -> None:
        """Original bug repro: a season-1 grab only credits the season-1 search, never season-2."""
        search_s1 = _search(1, 10, T0, season_number=1)
        search_s2 = _search(2, 10, T0 + timedelta(minutes=1), season_number=2)
        grabs = [_grab(100, T0 + timedelta(minutes=5), season_number=1, episode_id=55, series_id=10)]

        results = correlate_grabs([search_s1, search_s2], grabs, WINDOW, match_season=True)

        result_s1 = next(r for r in results if r.history_id == 1)
        result_s2 = next(r for r in results if r.history_id == 2)
        assert result_s1.grab_count == 1
        assert result_s2.grab_count == 0

    def test_correlate_season_aware_missing_season_skipped_with_warning(self) -> None:
        """A grab with no episode (so no season) is skipped; WARNING names only the grab id and reason."""
        search_s1 = _search(1, 10, T0, season_number=1)
        grabs = [
            GrabEvent(
                id=100,
                date=(T0 + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
                eventType="grabbed",
                sourceTitle="Secret.Release.Title",
                episodeId=55,
                seriesId=10,
            ),
            _grab(101, T0 + timedelta(minutes=5), season_number=1, episode_id=56, series_id=10),
        ]

        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="WARNING")
        try:
            results = correlate_grabs([search_s1], grabs, WINDOW, match_season=True)
            output = sink.getvalue()
        finally:
            logger.remove(handler_id)

        assert results[0].grab_count == 1
        assert results[0].matched_grabs[0].id == 101
        assert "100" in output
        assert "missing season" in output
        assert "Secret.Release.Title" not in output

    def test_correlate_season_search_without_season_number_matches_nothing(self) -> None:
        """match_season=True and SearchRecord.season_number is None -> that search matches nothing."""
        search_s1 = _search(1, 10, T0, season_number=None)
        grabs = [_grab(100, T0 + timedelta(minutes=5), season_number=1, episode_id=55, series_id=10)]

        results = correlate_grabs([search_s1], grabs, WINDOW, match_season=True)

        assert results[0].grab_count == 0

    def test_correlate_match_season_false_ignores_season_mismatch(self) -> None:
        """Default match_season=False ignores season entirely (Radarr/Lidarr behaviour unchanged)."""
        search_s1 = _search(1, 10, T0, season_number=1)
        grabs = [_grab(100, T0 + timedelta(minutes=5), season_number=2, episode_id=55, series_id=10)]

        results = correlate_grabs([search_s1], grabs, WINDOW)

        assert results[0].grab_count == 1

    def test_correlate_season_same_season_claiming_still_applies(self) -> None:
        """Two same-season searches in one call: most-recent-first claiming still applies."""
        search_a = _search(1, 10, T0, season_number=1)
        search_b = _search(2, 10, T0 + timedelta(minutes=30), season_number=1)
        grabs = [_grab(100, T0 + timedelta(minutes=35), season_number=1, episode_id=55, series_id=10)]

        results = correlate_grabs([search_a, search_b], grabs, WINDOW, match_season=True)

        result_a = next(r for r in results if r.history_id == 1)
        result_b = next(r for r in results if r.history_id == 2)
        assert result_b.grab_count == 1
        assert result_a.grab_count == 0

    def test_season_series_mismatch_rejected(self) -> None:
        """A grab whose seriesId (top-level or episode) differs from the search's series is rejected (R6)."""
        search = _search(1, 10, T0, season_number=1)

        grab_top_mismatch = _grab(100, T0 + timedelta(minutes=5), season_number=1, episode_id=55, series_id=99)
        grab_episode_mismatch = GrabEvent(
            id=101,
            date=(T0 + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            eventType="grabbed",
            sourceTitle="Release.1080p",
            episodeId=56,
            seriesId=10,
            episode=EpisodeSummary(id=56, seriesId=99, seasonNumber=1),
        )

        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="WARNING")
        try:
            results = correlate_grabs(
                [search], [grab_top_mismatch, grab_episode_mismatch], WINDOW, match_season=True
            )
            output = sink.getvalue()
        finally:
            logger.remove(handler_id)

        assert results[0].grab_count == 0
        assert "100" in output
        assert "101" in output
        assert "series mismatch" in output

    def test_season_series_missing_rejected(self) -> None:
        """A grab with neither seriesId nor episode.seriesId is rejected (fail closed); either alone is enough."""
        search = _search(1, 10, T0, season_number=1)

        grab_neither = GrabEvent(
            id=100,
            date=(T0 + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            eventType="grabbed",
            sourceTitle="Release.1080p",
            episodeId=55,
            episode=EpisodeSummary(id=55, seasonNumber=1),
        )
        grab_episode_series_only = GrabEvent(
            id=101,
            date=(T0 + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            eventType="grabbed",
            sourceTitle="Release.1080p",
            episodeId=56,
            episode=EpisodeSummary(id=56, seriesId=10, seasonNumber=1),
        )
        grab_top_series_only = _grab(102, T0 + timedelta(minutes=5), season_number=1, episode_id=57, series_id=10)

        results = correlate_grabs(
            [search], [grab_neither, grab_episode_series_only, grab_top_series_only], WINDOW, match_season=True
        )

        matched_ids = {g.id for g in results[0].matched_grabs}
        assert 100 not in matched_ids
        assert 101 in matched_ids
        assert 102 in matched_ids

    def test_season_conflicting_episode_id_rejected(self) -> None:
        """episode.id conflicting with the top-level episodeId is rejected (R2)."""
        search = _search(1, 10, T0, season_number=1)
        grab = GrabEvent(
            id=100,
            date=(T0 + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            eventType="grabbed",
            sourceTitle="Release.1080p",
            episodeId=9001,
            seriesId=10,
            episode=EpisodeSummary(id=9002, seriesId=10, seasonNumber=1),
        )

        results = correlate_grabs([search], [grab], WINDOW, match_season=True)

        assert results[0].grab_count == 0

    def test_season_missing_or_invalid_episode_id_rejected(self) -> None:
        """A missing or non-positive episodeId is rejected (R2)."""
        search = _search(1, 10, T0, season_number=1)
        grab_missing = GrabEvent(
            id=100,
            date=(T0 + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            eventType="grabbed",
            sourceTitle="Release.1080p",
            seriesId=10,
            episode=EpisodeSummary(seriesId=10, seasonNumber=1),
        )
        grab_zero = _grab(101, T0 + timedelta(minutes=5), season_number=1, episode_id=0, series_id=10)

        results = correlate_grabs([search], [grab_missing, grab_zero], WINDOW, match_season=True)

        assert results[0].grab_count == 0

    def test_correlate_alternate_order_scene_numbering_ignored(self) -> None:
        """Alternate-order fixture: alternate-numbered records credit only their canonical season (D-12)."""
        records = load_sonarr_fixture("history_alternate_order_nested_synth")
        grabs = [GrabEvent.model_validate(r) for r in records]

        searched_at = datetime(2026, 4, 1, 6, 59, 0, tzinfo=UTC)
        search_s1 = _search(1, 404, searched_at, season_number=1)
        search_s2 = _search(2, 404, searched_at, season_number=2)

        results = correlate_grabs([search_s1, search_s2], grabs, tracking_window_minutes=10080, match_season=True)

        result_s1 = next(r for r in results if r.history_id == 1)
        result_s2 = next(r for r in results if r.history_id == 2)

        assert result_s1.grab_count == 3
        assert {g.id for g in result_s1.matched_grabs} == {9301, 9302, 9303}
        assert result_s2.grab_count == 1
        assert result_s2.matched_grabs[0].id == 9304

    def test_correlate_multi_season_pack_fixture_splits_by_season(self) -> None:
        """Multi-season pack fixture: each season's search gets exactly its own three records (ATTR-01)."""
        records = load_sonarr_fixture("history_multi_season_pack_nested_synth")
        grabs = [GrabEvent.model_validate(r) for r in records]

        searched_at = datetime(2026, 3, 1, 7, 59, 0, tzinfo=UTC)
        search_s1 = _search(1, 303, searched_at, season_number=1)
        search_s2 = _search(2, 303, searched_at, season_number=2)

        results = correlate_grabs([search_s1, search_s2], grabs, tracking_window_minutes=60, match_season=True)

        result_s1 = next(r for r in results if r.history_id == 1)
        result_s2 = next(r for r in results if r.history_id == 2)

        assert result_s1.grab_count == 3
        assert {g.id for g in result_s1.matched_grabs} == {9201, 9202, 9203}
        assert result_s2.grab_count == 3
        assert {g.id for g in result_s2.matched_grabs} == {9204, 9205, 9206}
        s1_ids = {g.id for g in result_s1.matched_grabs}
        s2_ids = {g.id for g in result_s2.matched_grabs}
        assert s1_ids.isdisjoint(s2_ids)

    def test_correlate_season_pack_fixture_matches_all_including_repeat(self) -> None:
        """Season-pack fixture: a single season-1 search matches all 7 records (repeat grab included)."""
        records = load_sonarr_fixture("history_season_pack_nested_synth")
        grabs = [GrabEvent.model_validate(r) for r in records]

        searched_at = datetime(2026, 2, 1, 8, 59, 0, tzinfo=UTC)
        search_s1 = _search(1, 202, searched_at, season_number=1)

        results = correlate_grabs([search_s1], grabs, tracking_window_minutes=1500, match_season=True)

        assert results[0].grab_count == 7
        matched_ids = {g.id for g in results[0].matched_grabs}
        assert matched_ids == {9101, 9102, 9103, 9104, 9105, 9106, 9107}


class TestSonarrIdentityProblem:
    """Direct unit tests for the pure sonarr_identity_problem helper (R2, R6)."""

    def test_sonarr_identity_problem_trustworthy_returns_none(self) -> None:
        """A fully trustworthy grab returns None."""
        grab = _grab(1, T0, season_number=1, episode_id=55, series_id=10)
        assert sonarr_identity_problem(grab, series_id=10) is None


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
