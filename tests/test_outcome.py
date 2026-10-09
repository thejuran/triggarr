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
