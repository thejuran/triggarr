"""Honest per-cycle outcome grading (spec §3.1).

Pure functions plus a small per-cycle tally used by the search engine, the
scheduler and the dashboard to grade a cycle Success / Partial / Failed /
Nothing needed searching, replacing the previous unconditional last_run /
last_success stamp. Phase 79 reports an unresolved tag by calling
``CycleTally.mark_unevaluated``; Phase 80 reports malformed *arr records by
calling ``CycleTally.record_malformed``. Neither phase needs to reshape the
persisted record this module builds.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from triggarr.state import LastCycleRecord

GRADE_SUCCESS = "success"
GRADE_PARTIAL = "partial"
GRADE_FAILED = "failed"
GRADE_NOTHING_NEEDED = "nothing_needed"

GRADE_LABELS: dict[str, str] = {
    GRADE_SUCCESS: "Success",
    GRADE_PARTIAL: "Partial",
    GRADE_FAILED: "Failed",
    GRADE_NOTHING_NEEDED: "Nothing needed searching",
}

QUEUES: tuple[str, ...] = ("missing", "cutoff")


def grade_cycle(
    *,
    accepted: int,
    failed: int,
    malformed_skipped: int,
    unevaluated_active: int,
    fetch_failed: bool,
    eligible_active: int,
) -> str:
    """Grade a single cycle per spec §3.1's four rows.

    All parameters are keyword-only and required so no caller can forget the
    eligible-work input (amended R-01).

    Per R-01 (original): a queue starved to zero dispatches by
    ``hard_max_per_cycle`` while another active queue was searched still
    counts as evaluated -- configured throttling is not a failure.

    Per R-01 (amended): zero dispatches while eligible work existed must
    never read as Nothing needed searching. The engine's batch-size
    rebalancing (Plans 02/03) makes that case unreachable whenever
    ``hard_max_per_cycle`` >= 1; this function's ``eligible_active == 0``
    requirement for Nothing needed searching is the backstop for any case
    that rebalancing cannot prevent (e.g. hard_max disabled but the engine
    still dispatched nothing).

    The backstop grades Failed, not Partial: spec §3.1's Partial row
    requires >=1 accepted, and "the engine did no work while work existed"
    should count toward the SAFETY-03 alert. This supersedes RESEARCH Open
    Question 1's "Partial" recommendation.
    """
    incomplete = fetch_failed or unevaluated_active > 0 or malformed_skipped > 0
    if accepted >= 1:
        return GRADE_SUCCESS if failed == 0 and not incomplete else GRADE_PARTIAL
    if failed > 0 or incomplete or eligible_active > 0:
        return GRADE_FAILED
    return GRADE_NOTHING_NEEDED


def active_queues(missing_count: int, cutoff_count: int) -> list[str]:
    """Return the queues whose configured (pre-hard-max) search count is > 0."""
    counts = {"missing": missing_count, "cutoff": cutoff_count}
    return [queue for queue in QUEUES if counts[queue] > 0]


@dataclass
class CycleTally:
    """Accumulates one cycle's per-item outcomes, then builds a persisted record.

    Threaded through a cycle function from its first line to its last;
    ``to_record`` applies the spec §3.1 grade table exactly once, at the
    point the caller would otherwise stamp last_run/last_success unconditionally.
    """

    accepted: int = 0
    failed: int = 0
    malformed_skipped: int = 0
    persistence_failed: int = 0
    failure_reasons: dict[str, int] = field(default_factory=dict)
    unevaluated: list[dict[str, str]] = field(default_factory=list)
    eligible: dict[str, int] = field(default_factory=dict)
    fetch_error: str | None = None

    def record_accepted(self) -> None:
        """Record one *arr search command the instance accepted."""
        self.accepted += 1

    def record_failed(self, reason: str) -> None:
        """Record one failed search command. ``reason`` must already be sanitized."""
        self.failed += 1
        self.failure_reasons[reason] = self.failure_reasons.get(reason, 0) + 1

    def record_persistence_failure(self) -> None:
        """Record an accepted command whose history row was not saved (D-15 / R-02).

        Never changes the grade (OUTCOME-06).
        """
        self.persistence_failed += 1

    def record_malformed(self, count: int = 1) -> None:
        """Phase 80 hook: tally *arr records skipped for being malformed."""
        self.malformed_skipped += count

    def mark_unevaluated(self, queue: str, reason: str) -> None:
        """Phase 79 hook: record that an active queue could not be evaluated."""
        if queue not in QUEUES:
            raise ValueError(f"queue must be one of {QUEUES}, got {queue!r}")
        self.unevaluated.append({"queue": queue, "reason": reason})

    def record_fetch_failure(self, reason: str) -> None:
        """Record that the whole-cycle fetch failed. ``reason`` must already be sanitized."""
        self.fetch_error = reason

    def record_eligible(self, queue: str, count: int) -> None:
        """R-01 (amended): record the eligible-item count a queue's filter chain produced.

        Called once per queue after that queue's filter chain, passing the
        number of items ``prioritize_batch`` may draw from (for Sonarr, seasons).
        """
        if queue not in QUEUES:
            raise ValueError(f"queue must be one of {QUEUES}, got {queue!r}")
        self.eligible[queue] = max(0, count)

    def to_record(self, *, active_queues: Iterable[str], finished_at: str) -> LastCycleRecord:
        """Build the persisted record and compute its grade.

        ``unevaluated`` and ``eligible`` are both restricted to ``active_queues``;
        a queue that is both eligible-recorded and marked unevaluated is excluded
        from ``eligible`` (unevaluated wins).
        """
        active = list(active_queues)
        filtered_unevaluated = [entry for entry in self.unevaluated if entry["queue"] in active]
        unevaluated_queues = {entry["queue"] for entry in filtered_unevaluated}
        eligible = {queue: self.eligible.get(queue, 0) for queue in active if queue not in unevaluated_queues}

        grade = grade_cycle(
            accepted=self.accepted,
            failed=self.failed,
            malformed_skipped=self.malformed_skipped,
            unevaluated_active=len(filtered_unevaluated),
            fetch_failed=self.fetch_error is not None,
            eligible_active=sum(eligible.values()),
        )

        failure_reasons = [
            {"reason": reason, "count": count}
            for reason, count in sorted(self.failure_reasons.items(), key=lambda item: (-item[1], item[0]))
        ]

        return {
            "grade": grade,
            "accepted": self.accepted,
            "failed": self.failed,
            "malformed_skipped": self.malformed_skipped,
            "persistence_failed": self.persistence_failed,
            "failure_reasons": failure_reasons,
            "unevaluated": filtered_unevaluated,
            "eligible": eligible,
            "fetch_error": self.fetch_error,
            "finished_at": finished_at,
        }
