"""Unit tests for the honest-outcome grading model (triggarr.search.outcome)."""

from __future__ import annotations

import json

from triggarr.search.outcome import (
    GRADE_FAILED,
    GRADE_LABELS,
    GRADE_NOTHING_NEEDED,
    GRADE_PARTIAL,
    GRADE_SUCCESS,
    CycleTally,
    active_queues,
    cycle_view,
    grade_cycle,
)

# --- grade_cycle: spec §3.1 grade table ---


def test_grade_cycle_success() -> None:
    """All active queues evaluated, >=1 accepted, nothing failed -> Success."""
    assert (
        grade_cycle(
            accepted=3,
            failed=0,
            malformed_skipped=0,
            unevaluated_active=0,
            fetch_failed=False,
            eligible_active=3,
        )
        == GRADE_SUCCESS
    )


def test_grade_cycle_partial_with_failures() -> None:
    """>=1 accepted but also >=1 failed -> Partial."""
    assert (
        grade_cycle(
            accepted=3,
            failed=1,
            malformed_skipped=0,
            unevaluated_active=0,
            fetch_failed=False,
            eligible_active=4,
        )
        == GRADE_PARTIAL
    )


def test_grade_cycle_partial_unevaluated_active_queue() -> None:
    """>=1 accepted but an active queue was unevaluated -> Partial."""
    assert (
        grade_cycle(
            accepted=2,
            failed=0,
            malformed_skipped=0,
            unevaluated_active=1,
            fetch_failed=False,
            eligible_active=2,
        )
        == GRADE_PARTIAL
    )


def test_grade_cycle_partial_malformed_skipped() -> None:
    """>=1 accepted but malformed records were skipped -> Partial."""
    assert (
        grade_cycle(
            accepted=2,
            failed=0,
            malformed_skipped=1,
            unevaluated_active=0,
            fetch_failed=False,
            eligible_active=2,
        )
        == GRADE_PARTIAL
    )


def test_grade_cycle_failed_all_failed() -> None:
    """0 accepted, >=1 failed -> Failed."""
    assert (
        grade_cycle(
            accepted=0,
            failed=2,
            malformed_skipped=0,
            unevaluated_active=0,
            fetch_failed=False,
            eligible_active=2,
        )
        == GRADE_FAILED
    )


def test_grade_cycle_failed_blocked_active_queue_and_empty_other() -> None:
    """A blocked active queue plus an empty other queue grades Failed, never Nothing needed."""
    assert (
        grade_cycle(
            accepted=0,
            failed=0,
            malformed_skipped=0,
            unevaluated_active=1,
            fetch_failed=False,
            eligible_active=0,
        )
        == GRADE_FAILED
    )


def test_grade_cycle_failed_malformed_skipped_with_nothing_accepted() -> None:
    """0 accepted, 0 failed, but malformed records skipped -> Failed (incomplete evaluation)."""
    assert (
        grade_cycle(
            accepted=0,
            failed=0,
            malformed_skipped=1,
            unevaluated_active=0,
            fetch_failed=False,
            eligible_active=0,
        )
        == GRADE_FAILED
    )


def test_grade_cycle_failed_fetch_failure() -> None:
    """A whole-cycle fetch failure grades Failed."""
    assert (
        grade_cycle(
            accepted=0,
            failed=0,
            malformed_skipped=0,
            unevaluated_active=0,
            fetch_failed=True,
            eligible_active=0,
        )
        == GRADE_FAILED
    )


def test_grade_cycle_nothing_needed() -> None:
    """Clean cycle with no eligible work anywhere -> Nothing needed searching."""
    assert (
        grade_cycle(
            accepted=0,
            failed=0,
            malformed_skipped=0,
            unevaluated_active=0,
            fetch_failed=False,
            eligible_active=0,
        )
        == GRADE_NOTHING_NEEDED
    )


def test_grade_cycle_failed_eligible_work_never_dispatched() -> None:
    """Amended R-01: eligible work existed but nothing was dispatched -> Failed, never Nothing needed."""
    assert (
        grade_cycle(
            accepted=0,
            failed=0,
            malformed_skipped=0,
            unevaluated_active=0,
            fetch_failed=False,
            eligible_active=4,
        )
        == GRADE_FAILED
    )


def test_grade_cycle_success_when_other_queue_starved_by_hard_max() -> None:
    """R-01 (original): a queue starved to zero by hard_max_per_cycle, next to an accepted queue, is still Success."""
    assert (
        grade_cycle(
            accepted=1,
            failed=0,
            malformed_skipped=0,
            unevaluated_active=0,
            fetch_failed=False,
            eligible_active=60,
        )
        == GRADE_SUCCESS
    )


# --- active_queues ---


def test_active_queues_missing_only() -> None:
    assert active_queues(5, 0) == ["missing"]


def test_active_queues_none_active() -> None:
    assert active_queues(0, 0) == []


def test_active_queues_both_active() -> None:
    assert active_queues(2, 3) == ["missing", "cutoff"]


# --- CycleTally ---


def test_cycle_tally_record_failed_groups_and_sorts_reasons() -> None:
    tally = CycleTally()
    tally.record_failed("HTTP 500")
    tally.record_failed("HTTP 500")
    tally.record_failed("request timeout")
    record = tally.to_record(active_queues=["missing"], finished_at="2026-10-08T12:00:00Z")
    assert record["failure_reasons"] == [
        {"reason": "HTTP 500", "count": 2},
        {"reason": "request timeout", "count": 1},
    ]


def test_cycle_tally_mark_unevaluated_drops_inactive_queue() -> None:
    tally = CycleTally()
    tally.mark_unevaluated("cutoff", "tag 'x' not found")
    record = tally.to_record(active_queues=["missing"], finished_at="2026-10-08T12:00:00Z")
    assert record["unevaluated"] == []
    assert record["grade"] == GRADE_NOTHING_NEEDED


def test_cycle_tally_mark_unevaluated_invalid_queue_raises() -> None:
    tally = CycleTally()
    try:
        tally.mark_unevaluated("bogus", "r")
    except ValueError:
        return
    raise AssertionError("expected ValueError for an invalid queue name")


def test_cycle_tally_record_eligible_restricted_to_active_queues() -> None:
    tally = CycleTally()
    tally.record_eligible("missing", 3)
    tally.record_eligible("cutoff", 0)
    full_record = tally.to_record(active_queues=["missing", "cutoff"], finished_at="2026-10-08T12:00:00Z")
    assert full_record["grade"] == GRADE_FAILED
    assert full_record["eligible"] == {"missing": 3, "cutoff": 0}

    partial_record = tally.to_record(active_queues=["cutoff"], finished_at="2026-10-08T12:00:00Z")
    assert partial_record["eligible"] == {"cutoff": 0}
    assert partial_record["grade"] == GRADE_NOTHING_NEEDED


def test_cycle_tally_record_eligible_excluded_when_unevaluated() -> None:
    """A queue that is both eligible-recorded and marked unevaluated: unevaluated wins."""
    tally = CycleTally()
    tally.record_eligible("missing", 5)
    tally.mark_unevaluated("missing", "tag not found")
    record = tally.to_record(active_queues=["missing"], finished_at="2026-10-08T12:00:00Z")
    assert record["eligible"] == {}


def test_cycle_tally_record_eligible_invalid_queue_raises() -> None:
    tally = CycleTally()
    try:
        tally.record_eligible("bogus", 1)
    except ValueError:
        return
    raise AssertionError("expected ValueError for an invalid queue name")


def test_cycle_tally_record_persistence_failure_never_changes_grade() -> None:
    tally = CycleTally()
    tally.record_accepted()
    tally.record_accepted()
    tally.record_accepted()
    tally.record_persistence_failure()
    tally.record_persistence_failure()
    tally.record_persistence_failure()
    record = tally.to_record(active_queues=[], finished_at="2026-10-08T12:00:00Z")
    assert record["persistence_failed"] == 3
    assert record["grade"] == GRADE_SUCCESS


def test_cycle_tally_record_fetch_failure_grades_failed() -> None:
    tally = CycleTally()
    tally.record_fetch_failure("HTTP 503")
    record = tally.to_record(active_queues=["missing", "cutoff"], finished_at="2026-10-08T12:00:00Z")
    assert record["grade"] == GRADE_FAILED
    assert record["fetch_error"] == "HTTP 503"
    assert record["accepted"] == 0
    assert record["failed"] == 0


def test_cycle_tally_to_record_exact_keys_and_json_serializable() -> None:
    tally = CycleTally()
    tally.record_accepted()
    record = tally.to_record(active_queues=["missing"], finished_at="2026-10-08T12:00:00Z")
    assert set(record.keys()) == {
        "grade",
        "accepted",
        "failed",
        "malformed_skipped",
        "persistence_failed",
        "failure_reasons",
        "unevaluated",
        "eligible",
        "fetch_error",
        "finished_at",
    }
    json.dumps(record)  # must not raise


def test_grade_labels_contains_nothing_needed_searching() -> None:
    assert GRADE_LABELS[GRADE_NOTHING_NEEDED] == "Nothing needed searching"


# --- cycle_view: display composer (D-09/D-10/D-12) ---


def test_cycle_view_none_record_is_none() -> None:
    assert cycle_view(None, "Radarr") is None


def test_cycle_view_garbage_string_record_is_none() -> None:
    assert cycle_view("garbage", "Radarr") is None


def test_cycle_view_invalid_grade_is_none() -> None:
    assert cycle_view({"grade": "weird"}, "Radarr") is None


def test_cycle_view_partial_http_status_reason() -> None:
    record = {
        "grade": "partial",
        "accepted": 4,
        "failed": 1,
        "failure_reasons": [{"reason": "HTTP 500", "count": 3}],
    }
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert view["reasons"] == [{"text": "Command rejected by Radarr (HTTP 500)", "count": 3}]
    assert view["grade_label"] == "Partial"
    assert view["has_detail"] is True
    assert view["reason_count"] == 1


def test_cycle_view_non_http_reason_wording() -> None:
    record = {
        "grade": "partial",
        "accepted": 1,
        "failed": 1,
        "failure_reasons": [{"reason": "request timeout", "count": 1}],
    }
    view = cycle_view(record, "Sonarr")
    assert view is not None
    assert view["reasons"][0]["text"] == "Search command to Sonarr failed (request timeout)"


def test_cycle_view_unevaluated_missing_queue_row() -> None:
    record = {
        "grade": "partial",
        "accepted": 1,
        "failed": 0,
        "unevaluated": [{"queue": "missing", "reason": "tag 'x' not found"}],
    }
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert view["reasons"][0]["text"] == "Missing queue not evaluated: tag 'x' not found"


def test_cycle_view_unevaluated_cutoff_queue_row() -> None:
    record = {
        "grade": "partial",
        "accepted": 1,
        "failed": 0,
        "unevaluated": [{"queue": "cutoff", "reason": "tag 'x' not found"}],
    }
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert view["reasons"][0]["text"] == "Cutoff unmet queue not evaluated: tag 'x' not found"


def test_cycle_view_malformed_skipped_plural() -> None:
    record = {"grade": "partial", "accepted": 1, "failed": 0, "malformed_skipped": 2}
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert {"text": "2 malformed records skipped", "count": 1} in view["reasons"]


def test_cycle_view_malformed_skipped_singular() -> None:
    record = {"grade": "partial", "accepted": 1, "failed": 0, "malformed_skipped": 1}
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert {"text": "1 malformed record skipped", "count": 1} in view["reasons"]


def test_cycle_view_fetch_error_row() -> None:
    record = {"grade": "failed", "accepted": 0, "failed": 0, "fetch_error": "HTTP 503"}
    view = cycle_view(record, "Lidarr")
    assert view is not None
    assert view["fetch_failed"] is True
    assert {"text": "Couldn't reach Lidarr (HTTP 503)", "count": 1} in view["reasons"]


def test_cycle_view_success_has_detail_false() -> None:
    record = {"grade": "success", "accepted": 3, "failed": 0}
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert view["has_detail"] is False


def test_cycle_view_nothing_needed_has_detail_false() -> None:
    record = {"grade": "nothing_needed", "accepted": 0, "failed": 0}
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert view["has_detail"] is False


def test_cycle_view_failed_with_reasons_has_detail_true() -> None:
    record = {
        "grade": "failed",
        "accepted": 0,
        "failed": 2,
        "failure_reasons": [{"reason": "HTTP 500", "count": 2}],
    }
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert view["has_detail"] is True


def test_cycle_view_non_int_counts_normalize_to_zero() -> None:
    record = {"grade": "success", "accepted": "x", "failed": None}
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert view["accepted"] == 0
    assert view["failed"] == 0


def test_cycle_view_reason_text_truncated_to_120_chars() -> None:
    long_reason = "x" * 200
    record = {
        "grade": "partial",
        "accepted": 1,
        "failed": 1,
        "failure_reasons": [{"reason": long_reason, "count": 1}],
    }
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert len(view["reasons"][0]["text"]) == 120


def test_cycle_view_persistence_failed_passthrough() -> None:
    record = {"grade": "success", "accepted": 2, "failed": 0, "persistence_failed": 2}
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert view["persistence_failed"] == 2


def test_cycle_view_persistence_failed_missing_key_defaults_zero() -> None:
    record = {"grade": "success", "accepted": 2, "failed": 0}
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert view["persistence_failed"] == 0


def test_cycle_view_eligible_backstop_row_plural() -> None:
    record = {
        "grade": "failed",
        "accepted": 0,
        "failed": 0,
        "eligible": {"missing": 3, "cutoff": 0},
    }
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert {"text": "3 eligible items not searched this cycle", "count": 1} in view["reasons"]
    assert view["has_detail"] is True


def test_cycle_view_eligible_backstop_row_singular() -> None:
    record = {
        "grade": "failed",
        "accepted": 0,
        "failed": 0,
        "eligible": {"missing": 1},
    }
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert {"text": "1 eligible item not searched this cycle", "count": 1} in view["reasons"]


def test_cycle_view_eligible_backstop_never_on_nothing_needed() -> None:
    record = {
        "grade": "nothing_needed",
        "accepted": 0,
        "failed": 0,
        "eligible": {"missing": 0, "cutoff": 0},
    }
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert view["reasons"] == []


def test_cycle_view_eligible_non_dict_treated_as_empty() -> None:
    record = {"grade": "failed", "accepted": 0, "failed": 0, "eligible": "not-a-dict"}
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert view["reasons"] == []


def test_cycle_view_unhashable_unevaluated_queue_is_skipped() -> None:
    """A tampered unevaluated entry whose queue is a list/dict never crashes the card."""
    record = {
        "grade": "partial",
        "accepted": 1,
        "failed": 0,
        "unevaluated": [
            {"queue": ["cutoff"], "reason": "x"},
            {"queue": {"q": "missing"}, "reason": "y"},
            {"queue": "cutoff", "reason": "malformed data (TypeError)"},
        ],
    }
    view = cycle_view(record, "Radarr")
    assert view is not None
    assert view["reasons"] == [
        {"text": "Cutoff unmet queue not evaluated: malformed data (TypeError)", "count": 1}
    ]
