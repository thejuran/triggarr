"""Honest per-cycle outcome grading (spec §3.1).

Pure functions plus a small per-cycle tally used by the search engine, the
scheduler and the dashboard to grade a cycle Success / Partial / Failed /
Nothing needed searching, replacing the previous unconditional last_run /
last_success stamp. Phase 79 reports an unresolved tag by calling
``CycleTally.mark_unevaluated``; Phase 80 reports malformed *arr records by
calling ``CycleTally.record_malformed(queue, count)`` -- the persisted
record gains one additive field, ``malformed_by_queue``, breaking the
existing ``malformed_skipped`` aggregate down per active queue.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from triggarr.state import LastCycleRecord

_HTTP_STATUS_RE = re.compile(r"^HTTP \d{3}$")
_MAX_REASON_LENGTH = 120
_UNEVALUATED_QUEUE_LABELS: dict[str, str] = {"missing": "Missing", "cutoff": "Cutoff unmet"}
# D-07 card wording for per-queue malformed rows -- distinct wording from
# _UNEVALUATED_QUEUE_LABELS above, do not reuse that dict for this text.
_MALFORMED_QUEUE_LABELS: dict[str, str] = {"missing": "missing-queue", "cutoff": "upgrade-queue"}

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
    malformed_by_queue: dict[str, int] = field(default_factory=dict)
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

    def record_malformed(self, queue: str, count: int = 1) -> None:
        """Phase 80 hook: tally *arr records skipped for being malformed, per queue.

        ``queue`` must be one of ``QUEUES``, validated identically to
        ``mark_unevaluated``. Counts recorded against a queue that turns out
        to be inactive are dropped at ``to_record`` (spec 3.1: inactive
        queues are ignored for grading).
        """
        if queue not in QUEUES:
            raise ValueError(f"queue must be one of {QUEUES}, got {queue!r}")
        self.malformed_by_queue[queue] = self.malformed_by_queue.get(queue, 0) + count
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
        from ``eligible`` (unevaluated wins). ``malformed_by_queue`` is also
        restricted to ``active_queues``; the aggregate ``malformed_skipped``
        passed to ``grade_cycle`` and persisted is derived from that filtered
        per-queue breakdown, not the raw lifetime total (spec 3.1: inactive
        queues are ignored for grading).
        """
        active = list(active_queues)
        filtered_unevaluated = [entry for entry in self.unevaluated if entry["queue"] in active]
        unevaluated_queues = {entry["queue"] for entry in filtered_unevaluated}
        eligible = {queue: self.eligible.get(queue, 0) for queue in active if queue not in unevaluated_queues}
        malformed_by_queue = {
            queue: self.malformed_by_queue[queue] for queue in active if self.malformed_by_queue.get(queue, 0) > 0
        }
        malformed_skipped = sum(malformed_by_queue.values())

        grade = grade_cycle(
            accepted=self.accepted,
            failed=self.failed,
            malformed_skipped=malformed_skipped,
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
            "malformed_skipped": malformed_skipped,
            "malformed_by_queue": malformed_by_queue,
            "persistence_failed": self.persistence_failed,
            "failure_reasons": failure_reasons,
            "unevaluated": filtered_unevaluated,
            "eligible": eligible,
            "fetch_error": self.fetch_error,
            "finished_at": finished_at,
        }


def _as_count(value: object) -> int:
    """Coerce a tampered-record value to a non-negative int, defaulting to 0."""
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


def _truncate(text: str, limit: int = _MAX_REASON_LENGTH) -> str:
    """Truncate reason text so a tampered/oversized record can't blow up the card."""
    return text if len(text) <= limit else text[:limit]


def cycle_view(record: object, app_label: str) -> dict | None:
    """Turn a persisted LastCycleRecord (or a tampered/garbage value) into a render-ready dict.

    Validates at the boundary, because state.json is read from disk: returns
    None unless ``record`` is a dict whose "grade" is a key of GRADE_LABELS --
    a malformed persisted record renders as "Not run yet", never crashes.

    Reasons are grouped sanitized strings (D-09/D-10): fetch failure, then one
    row per failure reason, then one row per unevaluated queue, then
    malformed-record row(s), then (only for a clean Failed-by-amended-R-01
    cycle) a row explaining eligible work that was never dispatched. Inputs
    are already-sanitized strings; Jinja autoescape handles HTML, and media
    titles never appear here.

    Malformed rows (D-07/D-10): when ``malformed_by_queue`` is a dict, one row
    is rendered per active queue with a positive count, worded "1 {queue}
    record skipped -- malformed data" / "{n} {queue} records skipped --
    malformed data", in fixed ``QUEUES`` order. A legacy record that carries
    only the aggregate ``malformed_skipped`` integer (no ``malformed_by_queue``
    key, or a tampered/unusable value) falls back to the original generic
    "N malformed record(s) skipped" row, so pre-Phase-80 state still renders.
    """
    if not isinstance(record, dict):
        return None
    grade = record.get("grade")
    if not isinstance(grade, str) or grade not in GRADE_LABELS:
        return None

    accepted = _as_count(record.get("accepted"))
    failed = _as_count(record.get("failed"))
    malformed_skipped = _as_count(record.get("malformed_skipped"))
    persistence_failed = _as_count(record.get("persistence_failed"))

    raw_finished_at = record.get("finished_at")
    finished_at = raw_finished_at if isinstance(raw_finished_at, str) else None

    reasons: list[dict[str, object]] = []

    fetch_error = record.get("fetch_error")
    fetch_failed = isinstance(fetch_error, str) and bool(fetch_error)
    if fetch_failed:
        reasons.append({"text": _truncate(f"Couldn't reach {app_label} ({fetch_error})"), "count": 1})

    raw_failure_reasons = record.get("failure_reasons")
    if isinstance(raw_failure_reasons, list):
        for entry in raw_failure_reasons:
            if not isinstance(entry, dict):
                continue
            reason = entry.get("reason")
            if not isinstance(reason, str):
                continue
            count = _as_count(entry.get("count"))
            if _HTTP_STATUS_RE.match(reason):
                text = f"Command rejected by {app_label} ({reason})"
            else:
                text = f"Search command to {app_label} failed ({reason})"
            reasons.append({"text": _truncate(text), "count": count})

    raw_unevaluated = record.get("unevaluated")
    unevaluated_rows = 0
    if isinstance(raw_unevaluated, list):
        for entry in raw_unevaluated:
            if not isinstance(entry, dict):
                continue
            reason = entry.get("reason")
            if not isinstance(reason, str):
                continue
            queue = entry.get("queue")
            # A tampered list/dict queue is unhashable -- check the type before the lookup.
            label = _UNEVALUATED_QUEUE_LABELS.get(queue) if isinstance(queue, str) else None
            if label is None:
                continue
            reasons.append({"text": _truncate(f"{label} queue not evaluated: {reason}"), "count": 1})
            unevaluated_rows += 1

    raw_malformed_by_queue = record.get("malformed_by_queue")
    malformed_rows_appended = 0
    if isinstance(raw_malformed_by_queue, dict):
        for queue in QUEUES:
            n = _as_count(raw_malformed_by_queue.get(queue))
            if n <= 0:
                continue
            label = _MALFORMED_QUEUE_LABELS[queue]
            if n == 1:
                text = f"1 {label} record skipped — malformed data"
            else:
                text = f"{n} {label} records skipped — malformed data"
            reasons.append({"text": _truncate(text), "count": 1})
            malformed_rows_appended += 1

    if malformed_rows_appended == 0 and malformed_skipped > 0:
        if malformed_skipped == 1:
            text = "1 malformed record skipped"
        else:
            text = f"{malformed_skipped} malformed records skipped"
        reasons.append({"text": _truncate(text), "count": 1})

    # Amended R-01 backstop: explain a clean Failed grade caused by eligible
    # work that never got dispatched, so the card is never blank.
    if (
        grade == GRADE_FAILED
        and accepted == 0
        and failed == 0
        and not fetch_failed
        and unevaluated_rows == 0
        and malformed_skipped == 0
    ):
        raw_eligible = record.get("eligible")
        eligible_map = raw_eligible if isinstance(raw_eligible, dict) else {}
        eligible_total = sum(_as_count(value) for value in eligible_map.values())
        if eligible_total > 0:
            text = (
                "1 eligible item not searched this cycle"
                if eligible_total == 1
                else f"{eligible_total} eligible items not searched this cycle"
            )
            reasons.append({"text": _truncate(text), "count": 1})

    has_detail = (grade in (GRADE_PARTIAL, GRADE_FAILED) or unevaluated_rows > 0) and len(reasons) > 0

    return {
        "grade": grade,
        "grade_label": GRADE_LABELS[grade],
        "accepted": accepted,
        "failed": failed,
        "persistence_failed": persistence_failed,
        "malformed_skipped": malformed_skipped,
        "finished_at": finished_at,
        "fetch_failed": fetch_failed,
        "reasons": reasons,
        "reason_count": len(reasons),
        "has_detail": has_detail,
    }
