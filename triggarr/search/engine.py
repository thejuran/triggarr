"""Core search engine: utility functions and search cycle orchestrators.

Pure functions for filtering, batching, and deduplication, plus async
cycle functions that compose them with API client calls to drive the
automated search behaviour for Radarr, Sonarr, and Lidarr.  Search
history is persisted to SQLite via the ``triggarr.db`` module.
"""

from __future__ import annotations

import contextlib
import functools
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import aiosqlite
import httpx
import pydantic
from loguru import logger

from triggarr.clients.base import _sanitize_exc
from triggarr.clients.lidarr import LidarrClient
from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.db import PendingCapExceeded, insert_search_entry
from triggarr.models.arr import Tag
from triggarr.models.config import InstanceConfig, Settings
from triggarr.search.outcome import CycleTally, active_queues
from triggarr.state import AppState, TriggarrState


def resolve_tag_id(tag_name: str, tags: list[Tag]) -> int | None:
    """Resolve a tag name to its numeric ID (case-insensitive, whitespace-stripped).

    Returns None if the tag name is not found in the tag list.
    """
    normalized = tag_name.strip().lower()
    for tag in tags:
        if tag.label.strip().lower() == normalized:
            return tag.id
    return None


def filter_by_tag(
    items: list[dict],
    tag_id: int,
    get_tags: Callable[[dict], list[int]],
) -> list[dict]:
    """Filter items to only those bearing the given tag ID.

    Args:
        items: List of item dicts from the *arr API.
        tag_id: Numeric tag ID to filter by.
        get_tags: Callable that extracts a list of tag IDs from an item dict.

    Returns:
        Only items where ``tag_id`` is present in ``get_tags(item)``.
    """
    return [item for item in items if tag_id in get_tags(item)]


def _radarr_tags(item: dict) -> list[int]:
    """Extract tag IDs from a Radarr movie dict."""
    return item.get("tags", [])


def _sonarr_tags(item: dict) -> list[int]:
    """Extract tag IDs from a Sonarr episode dict (via series object)."""
    return item.get("series", {}).get("tags", [])


def _lidarr_tags(item: dict) -> list[int]:
    """Extract tag IDs from a Lidarr album dict (via artist object)."""
    return item.get("artist", {}).get("tags", [])


def _is_json_int(value: object) -> bool:
    """True for a JSON integer; bool is an int subclass in Python but not a JSON integer."""
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_filter_date(value: object) -> datetime | None:
    """Parse a date the way the date filters do; None when absent or unparseable."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_naive_date(value: object) -> bool:
    """True for a date string the date filters parse but cannot compare: no UTC offset.

    Uses the filters' own parse, so absent (None) and unparseable values stay
    False and keep their existing handling there.
    """
    parsed = _parse_filter_date(value)
    return parsed is not None and parsed.tzinfo is None


def _is_valid_past_date(value: object) -> bool:
    """True for a date with a UTC offset that is already in the past."""
    parsed = _parse_filter_date(value)
    return parsed is not None and parsed.tzinfo is not None and parsed <= datetime.now(UTC)


def _malformed_reason(
    item: object,
    *,
    key_fields: tuple[str, ...] = (),
    nested_key: str | None = None,
    tags_at: tuple[str, ...] | None = None,
    date_fields: tuple[str, ...] = (),
) -> str | None:
    """Why one wanted record cannot be processed safely, or None if it can (ROBUST-01).

    A record is malformed when it is not a dict or a field dispatch/dedup is
    keyed on (``key_fields``) is not a JSON integer -> ``"record"``. The search
    commands take ``int`` IDs (``search_movies``/``search_albums`` ``list[int]``,
    ``search_season(int, int)``), so missing, null, bool, float (even ``2.0``),
    string and list values are skipped, never coerced; any int is kept,
    including Sonarr season 0 (specials, D-09). When
    ``nested_key`` is present with a non-dict value (``.get(key, {})`` does not
    substitute an explicit null, RESEARCH.md Pitfall 1) -> ``nested_key``; or,
    on a tag-scoped queue, when the tags value at ``tags_at`` is present but
    not a list -> ``"tags"``; or when a ``date_fields`` value parses to a date
    with no UTC offset -> ``"date"`` (the date filters compare with an aware
    "now", and the timezone is never guessed). ``date_fields`` are
    alternatives -- the date filter keeps a record when ANY of them is in the
    past -- so a valid past date in one field decides and a timezone-less date
    in another is then never read, hence not malformed. An absent nested object, tags
    value or date is NOT malformed -- the display-title fallback, the tag
    extractors' ``[]`` default and the date filters already handle it. The
    reason names the log line only.
    """
    if not isinstance(item, dict) or not all(_is_json_int(item.get(field)) for field in key_fields):
        return "record"
    if nested_key is not None and nested_key in item and not isinstance(item[nested_key], dict):
        return nested_key
    if tags_at is not None:
        node: object = item
        for key in tags_at[:-1]:
            node = node.get(key, {}) if isinstance(node, dict) else None
        if isinstance(node, dict) and tags_at[-1] in node and not isinstance(node[tags_at[-1]], list):
            return "tags"
    if any(_is_naive_date(item.get(field)) for field in date_fields) and not any(
        _is_valid_past_date(item.get(field)) for field in date_fields
    ):
        return "date"
    return None


def _screen_queue(
    items: list,
    *,
    app_label: str,
    queue: str,
    tally: CycleTally,
    key_fields: tuple[str, ...] = (),
    nested_key: str | None = None,
    tags_at: tuple[str, ...] | None = None,
    date_fields: tuple[str, ...] = (),
) -> list[dict]:
    """Skip and count malformed records in one wanted queue, per item (ROBUST-01/04).

    The per-record check shared by all six cycle queues (Radarr, Sonarr,
    Lidarr x missing/cutoff), so one bad record never faults the rest of its
    queue. Each chain calls it in stages, each just before the step that reads
    the checked fields: with no checks it skips only non-object records (whose
    eligibility cannot be read), and every later stage sees only records the
    earlier eligibility checks kept -- so a record the queue would never search
    (unmonitored, out of tag scope, unaired, unreleased) is never counted for a
    field nothing reads. Skipped records are logged once per reason and counted
    against ``queue`` via ``tally.record_malformed``; valid records are returned
    in their original order.
    """
    valid: list[dict] = []
    skipped_by_reason: dict[str, list] = {}
    for item in items:
        reason = _malformed_reason(
            item, key_fields=key_fields, nested_key=nested_key, tags_at=tags_at, date_fields=date_fields
        )
        if reason is None:
            valid.append(item)
        else:
            skipped_by_reason.setdefault(reason, []).append(item)
    for reason, skipped in skipped_by_reason.items():
        _log_malformed_skip(app_label, queue, reason, skipped)
        tally.record_malformed(queue, len(skipped))
    return valid


def _log_malformed_skip(app_label: str, queue: str, nested_key: str, skipped: list) -> None:
    """Log one warning for a batch of malformed records skipped from one queue (D-08).

    Carries only the skip count and up to 10 record IDs (dict items' ``id``
    field, when present) -- never exception text, and no title text beyond
    what's already unavoidable elsewhere; the card never sees this, only
    the sanitized System Logs (D-07/D-08).
    """
    queue_label = "missing-queue" if queue == "missing" else "upgrade-queue"
    ids = [item.get("id") for item in skipped if isinstance(item, dict)][:10]
    logger.warning(
        "{app}: Skipped {n} {queue_label} record(s) with malformed {key} data (ids={ids})",
        app=app_label,
        n=len(skipped),
        queue_label=queue_label,
        key=nested_key,
        ids=ids,
    )


def cap_batch_sizes(missing_count: int, cutoff_count: int, hard_max: int) -> tuple[int, int]:
    """Cap total batch sizes to a hard maximum, splitting proportionally.

    When ``hard_max`` is 0 or negative (unlimited), the inputs are returned
    unchanged.  Otherwise the combined total is capped at ``hard_max`` with
    a proportional split: missing gets ``floor(missing / total * hard_max)``
    and cutoff gets the remainder, ensuring the cap is not exceeded.

    Args:
        missing_count: Requested missing-queue batch size.
        cutoff_count: Requested cutoff-queue batch size.
        hard_max: Maximum combined items (0 = unlimited).

    Returns:
        Tuple of (effective_missing, effective_cutoff).
    """
    if hard_max <= 0:
        return (missing_count, cutoff_count)
    total_requested = missing_count + cutoff_count
    if total_requested <= hard_max:
        return (missing_count, cutoff_count)
    # Proportional split, round down for missing, remainder to cutoff
    effective_missing = max(0, (missing_count * hard_max) // total_requested)
    effective_cutoff = hard_max - effective_missing
    return (effective_missing, effective_cutoff)


def rebalance_batch_sizes(
    *,
    missing_limit: int,
    cutoff_limit: int,
    missing_configured: int,
    cutoff_configured: int,
    missing_eligible: int,
    cutoff_eligible: int,
    hard_max: int,
) -> tuple[int, int]:
    """Reallocate unused hard-max budget to a starved queue with eligible work (amended R-01).

    ``cap_batch_sizes`` can give an active queue with eligible work zero
    slots while the other queue has no eligible work this cycle (e.g.
    ``missing_count=50, cutoff_count=50, hard_max=1`` -> ``(0, 1)``). If the
    cutoff queue then has nothing eligible, the cycle would dispatch zero
    commands despite real missing-queue work existing -- the exact
    counterexample from RESEARCH.md Pitfall 4. This reallocates any slot a
    queue cannot use (because it lacks eligible items) to the other queue,
    up to that queue's own configured count and eligible count, without
    ever exceeding ``hard_max`` in total.

    ``missing_limit``/``cutoff_limit`` are the already-capped values from
    ``cap_batch_sizes`` (pre-hard-max totals, i.e. ``missing_configured``/
    ``cutoff_configured``, are passed separately since the cap already
    consumed them). When ``hard_max <= 0`` (unlimited), the capped inputs
    are returned unchanged -- there is no budget to reallocate.
    """
    if hard_max <= 0:
        return (missing_limit, cutoff_limit)

    m = min(missing_limit, missing_eligible)
    c = min(cutoff_limit, cutoff_eligible)
    leftover = hard_max - m - c

    top_up_missing = max(0, min(leftover, min(missing_configured, missing_eligible) - m))
    m += top_up_missing
    leftover -= top_up_missing

    top_up_cutoff = max(0, min(leftover, min(cutoff_configured, cutoff_eligible) - c))
    c += top_up_cutoff

    return (m, c)


def filter_monitored(items: list[dict]) -> list[dict]:
    """Filter out items where ``monitored`` is not True.

    Works for both Radarr movies and Sonarr episodes.

    Args:
        items: List of item dicts from the *arr API.

    Returns:
        Only items with ``monitored`` set to True.
    """
    return [item for item in items if item.get("monitored", False)]


def prioritize_batch(
    eligible_items: list,
    searched_log: list[str],
    batch_size: int,
    key_fn: Callable[[dict], str],
    *,
    exclude_keys: frozenset[str] = frozenset(),
) -> tuple[list, list[str], bool]:
    """Assemble a batch: never-searched first (fetch order), then top up
    already-searched oldest-first.

    Implements the never-searched-first dispatch algorithm (QUEUE-04/05/08/09/10):
    1. Build the set of eligible IDs from the current fetch.
    2. Prune the searched-log to currently-eligible IDs (QUEUE-10).
    3. Partition eligible items into unsearched and already-searched. Exclusion
       (see ``exclude_keys``) is applied only at this step.
    4. Fill batch with unsearched[:batch_size]; if short, top up from the pruned
       log front (oldest-searched-first) until full or exhausted (QUEUE-05).
    5. Mark every batched item on attempt — append keys to the log; a re-searched
       item moves to the tail (most-recent) (QUEUE-08).
    6. Pass-complete check (MED-1, DEDUP-03): pass_completed = bool(batch) AND every
       eligible ID not in ``exclude_keys`` is in the new log.  An excluded key was
       attempted this cycle by another queue, so it counts as covered — but it is
       never inserted into the log.  The bool(batch) guard is MANDATORY — it
       prevents a zero-search pass reset when batch_size<=0 and the pruned log
       already covers a tiny eligible set (matches the old
       ``if new_cursor == 0 and batch`` wrap guard).

    Args:
        eligible_items: Full list of eligible items for this queue (fetch order,
            already filtered).  Must not be sorted by this function (D-10).
        searched_log: Ordered searched-log for this queue (oldest at front).
            Callers pass ``ist.get("<q>_searched", [])``.  Must NOT be a mutable
            default argument.
        batch_size: Maximum number of items to return.  May be 0 or negative
            (e.g., after hard_max proportional capping to zero).
        key_fn: Callable that extracts a stable string ID from an item dict.
            Radarr/Lidarr: ``lambda m: str(m["id"])``.
            Sonarr: ``lambda s: f'{s["seriesId"]}:{s["seasonNumber"]}'``.
        exclude_keys: Keys to keep out of this batch's candidacy (Sonarr
            cross-queue dedup, D-05). Excluded keys stay in the pruned log at
            their current position and are never marked on attempt; they count
            as covered for the pass-complete check (DEDUP-03).

    Returns:
        Tuple of (batch, new_searched_log, pass_completed).
        ``new_searched_log`` has all departed items pruned and all batched items
        appended (marking on attempt).  ``pass_completed`` is True only when this
        call produced a non-empty batch AND every eligible ID not in
        ``exclude_keys`` is now in the log.
    """
    if not eligible_items:
        return [], [], False

    eligible_ids = {key_fn(it) for it in eligible_items}
    # 2. Prune log to currently-eligible IDs only (QUEUE-10)
    log = [i for i in searched_log if i in eligible_ids]
    logset = set(log)

    # 3. Partition into unsearched (fetch order) and already-searched
    unsearched = [it for it in eligible_items if key_fn(it) not in logset and key_fn(it) not in exclude_keys]
    searched = [it for it in eligible_items if key_fn(it) in logset and key_fn(it) not in exclude_keys]

    # 4. Batch: unsearched first, top up oldest-searched-first (log front = oldest)
    # Clamp to max(0, batch_size) so a negative batch_size always yields [] even
    # when unsearched items exist (Python's unsearched[:-1] would return all-but-last).
    batch: list = unsearched[:max(0, batch_size)]
    if batch_size > 0 and len(batch) < batch_size:
        order = {key_fn(it): it for it in searched}
        for sid in log:
            if len(batch) >= batch_size:
                break
            if sid in order:
                batch.append(order[sid])

    # 5. Mark on attempt: re-searched keys move to tail (most-recent)
    batched_keys = {key_fn(it) for it in batch}
    new_log = [i for i in log if i not in batched_keys] + [key_fn(it) for it in batch]

    # 6. Pass-complete: bool(batch) is MANDATORY (MED-1); excluded keys count as
    # covered without being inserted into the log (DEDUP-03)
    pass_completed = bool(batch) and (eligible_ids - exclude_keys).issubset(set(new_log))

    return batch, new_log, pass_completed



def deduplicate_to_seasons(episodes: list[dict]) -> list[dict]:
    """Deduplicate Sonarr episode records to unique (seriesId, seasonNumber) pairs.

    Order is preserved (first occurrence wins). Returns dicts with
    ``seriesId``, ``seasonNumber``, ``display_name``, ``series_title``, and
    ``episode_count`` keys.

    Args:
        episodes: List of episode dicts from Sonarr API.

    Returns:
        List of season-level dicts for search commands.
    """
    seen: dict[tuple[int, int], dict] = {}
    seasons: list[dict] = []
    for ep in episodes:
        series_id = ep.get("seriesId")
        season_number = ep.get("seasonNumber")
        if series_id is None or season_number is None:
            continue
        key = (series_id, season_number)
        if key not in seen:
            title = ep.get("series", {}).get("title", f"Series {series_id}")
            entry = {
                "seriesId": series_id,
                "seasonNumber": season_number,
                "display_name": f"{title} - Season {season_number}",
                "series_title": title,
                "episode_count": 1,
            }
            seen[key] = entry
            seasons.append(entry)
        else:
            seen[key]["episode_count"] += 1
    return seasons


def filter_sonarr_episodes(episodes: list[dict]) -> list[dict]:
    """Filter Sonarr episodes: must be monitored with a past air date.

    Combines monitored filtering AND future/TBA air date filtering.
    Episodes without an air date (TBA) are treated as future and skipped.
    Episodes with unparseable air dates are also skipped.

    Args:
        episodes: List of episode dicts from Sonarr API.

    Returns:
        Only monitored episodes with a past air date.
    """
    now = datetime.now(UTC)
    result: list[dict] = []
    for ep in episodes:
        if not ep.get("monitored", False):
            continue
        air_date_str = ep.get("airDateUtc")
        if air_date_str is None:
            continue
        try:
            air_date = datetime.fromisoformat(air_date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if air_date > now:
            continue
        result.append(ep)
    return result


def filter_unreleased_movies(movies: list[dict]) -> list[dict]:
    """Filter out Radarr movies that have not been released digitally or physically.

    A movie is considered released if either digitalRelease or physicalRelease
    is in the past. Movies with BOTH dates null/missing pass through (not blackholed).
    Movies with BOTH dates in the future are skipped.

    This filter applies to missing-queue items only. Cutoff-unmet items already
    have files and must never be passed through this filter.

    Args:
        movies: List of movie dicts from Radarr wanted/missing API.

    Returns:
        Movies eligible for searching (released or unknown release date).
    """
    now = datetime.now(UTC)
    result: list[dict] = []
    for movie in movies:
        digital_str = movie.get("digitalRelease")
        physical_str = movie.get("physicalRelease")

        # Parse dates, treating unparseable values as None
        digital: datetime | None = None
        physical: datetime | None = None
        if digital_str is not None:
            with contextlib.suppress(ValueError, AttributeError):
                digital = datetime.fromisoformat(digital_str.replace("Z", "+00:00"))
        if physical_str is not None:
            with contextlib.suppress(ValueError, AttributeError):
                physical = datetime.fromisoformat(physical_str.replace("Z", "+00:00"))

        # Both null/unparseable -> pass through (don't blackhole)
        if digital is None and physical is None:
            result.append(movie)
            continue

        # Either date in the past -> released. Dates with a UTC offset are
        # compared first, so a valid past date decides whichever field holds
        # it and a timezone-less other date is never compared (it would raise).
        dates = sorted((d for d in (digital, physical) if d is not None), key=lambda d: d.tzinfo is None)
        if any(d <= now for d in dates):
            result.append(movie)
            continue

        # Both dates in the future (or one future + one null) -> skip
        logger.debug(
            "Radarr: Skipping unreleased movie {title}",
            title=movie.get("title", "unknown"),
        )
    return result


async def _search_and_record(
    *,
    command: Callable[[], Awaitable[object]],
    tally: CycleTally,
    db: aiosqlite.Connection,
    app_label: str,
    queue: str,
    item_name: str,
    instance_name: str,
    max_rows: int,
    item_id: int | None = None,
    season_number: int | None = None,
    missing_count: int | None = None,
    instance_stable_id: str | None = None,
) -> bool:
    """Run one *arr search command and record its outcome (R-04).

    Splits the *arr command call from the search-history insert into two
    independent error boundaries so a history-insert failure can never be
    mistaken for a failed search command and can never abort the cycle
    (OUTCOME-06). ``command`` is invoked at most once -- neither stage
    ever retries it.

    Returns True when the *arr command was accepted (regardless of whether
    its history insert succeeded), False when the command itself failed.
    """
    try:
        await command()
    except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
        reason = _sanitize_exc(exc)
        logger.warning(
            "{app}: Failed to search {name}: {exc}",
            app=app_label,
            name=item_name,
            exc=reason,
        )
        tally.record_failed(reason)
        try:
            await insert_search_entry(
                db, app_label, queue, item_name,
                outcome="failed", detail=reason,
                item_id=item_id,
                season_number=season_number,
                missing_count=missing_count,
                instance_id=instance_name,
                instance_stable_id=instance_stable_id,
                max_rows=max_rows,
            )
        except (aiosqlite.Error, OSError) as insert_exc:
            logger.warning(
                "{app}: Could not record failed search for {name}: {exc}",
                app=app_label,
                name=item_name,
                exc=_sanitize_exc(insert_exc),
            )
        return False

    # Command accepted -- the *arr committed to the search regardless of what
    # happens next (OUTCOME-06). tally.accepted is unconditional from here.
    tally.record_accepted()
    try:
        await insert_search_entry(
            db, app_label, queue, item_name,
            outcome="searched", detail="search triggered",
            item_id=item_id,
            season_number=season_number,
            missing_count=missing_count,
            instance_id=instance_name,
            instance_stable_id=instance_stable_id,
            max_rows=max_rows,
        )
        logger.info("{app}: Searched {name} ({queue})", app=app_label, name=item_name, queue=queue)
    except PendingCapExceeded as cap_exc:
        logger.warning(
            "Skipping search history insert -- pending-row cap reached "
            "for {app}/{instance} {item!r}",
            app=cap_exc.app,
            instance=cap_exc.instance_id,
            item=cap_exc.item_name,
        )
        tally.record_persistence_failure()
    except (aiosqlite.Error, OSError) as insert_exc:
        logger.warning(
            "{app}: Search accepted but history not saved for {name}: {exc}",
            app=app_label,
            name=item_name,
            exc=_sanitize_exc(insert_exc),
        )
        tally.record_persistence_failure()
    return True


def _finalize_cycle(ist: AppState, tally: CycleTally, instance_config: InstanceConfig) -> None:
    """Grade the cycle and stamp its timestamps (R-04/R-05/OUTCOME-01/02).

    Writes ``ist["last_cycle"]`` (graded via ``CycleTally.to_record`` per
    spec Sec 3.1), ``ist["last_run"]`` unconditionally ("last checked"), and
    ``ist["last_successful_search"]`` only when at least one command was
    accepted this cycle. Never writes the legacy ``ist["last_success"]``
    field (R-05) -- it stays frozen at its pre-upgrade value for the
    "Last success (legacy)" label and the documented downgrade fallback.
    """
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    ist["last_cycle"] = tally.to_record(
        active_queues=active_queues(instance_config.search_missing_count, instance_config.search_cutoff_count),
        finished_at=now_iso,
    )
    ist["last_run"] = now_iso
    if tally.accepted >= 1:
        ist["last_successful_search"] = now_iso


def _mark_unreachable(ist: AppState) -> None:
    """Mark an instance disconnected, stamping ``unreachable_since`` only if not already set.

    Shared by the cycle abort / R-07 paths and the count-refresh fetch / data-fault
    paths so the "first seen unreachable" timestamp is preserved identically everywhere.
    """
    ist["connected"] = False
    if not ist.get("unreachable_since"):
        ist["unreachable_since"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _finish_both_inactive_unreachable(
    *, ist: AppState, tally: CycleTally, instance_config: InstanceConfig, app_label: str
) -> None:
    """Finish a cycle whose queues are both inactive and both unfetchable (R-07).

    Both queues are inactive and neither fetch could refresh its count. That
    is real evidence the host is unreachable, but nothing was configured to
    search this cycle -- grade nothing_needed (no active queues), never Failed.

    Shared by the three cycle functions: marks the instance unreachable and
    finalizes the cycle. Callers still own the ``return state`` after calling
    this -- it leaves the caller's control flow untouched.
    """
    logger.warning(
        "{app}: both queues inactive and neither could be fetched -- "
        "marked unreachable; not graded Failed",
        app=app_label,
    )
    _mark_unreachable(ist)
    _finalize_cycle(ist, tally, instance_config)


def _cap_and_log(
    *, app_label: str, missing_configured: int, cutoff_configured: int, hard_max: int
) -> tuple[int, int]:
    """Apply the hard-max cap to a cycle's configured limits and log when it changed one (SRCH-12).

    Shared by the three cycle functions: calls ``cap_batch_sizes`` on the
    configured limits and logs at debug level only when the hard max actually
    changed a limit. Returns the (possibly capped) (missing_limit, cutoff_limit).
    """
    missing_limit, cutoff_limit = cap_batch_sizes(missing_configured, cutoff_configured, hard_max)
    if hard_max > 0 and (missing_limit != missing_configured or cutoff_limit != cutoff_configured):
        logger.debug(
            "{app}: Hard max {max} applied -- missing={m}, cutoff={c}",
            app=app_label,
            max=hard_max,
            m=missing_limit,
            c=cutoff_limit,
        )
    return missing_limit, cutoff_limit


def _rebalance_and_log(
    *,
    app_label: str,
    missing_limit: int,
    cutoff_limit: int,
    missing_configured: int,
    cutoff_configured: int,
    missing_eligible: int,
    cutoff_eligible: int,
    hard_max: int,
) -> tuple[int, int]:
    """Reallocate unused hard-max budget to a starved queue with work (R-01 amended).

    Shared by the three cycle functions: calls ``rebalance_batch_sizes`` on the
    already-capped limits and logs at debug level when the hard max moved budget
    between queues. Returns the (possibly rebalanced) (missing_limit, cutoff_limit).
    """
    new_missing, new_cutoff = rebalance_batch_sizes(
        missing_limit=missing_limit,
        cutoff_limit=cutoff_limit,
        missing_configured=missing_configured,
        cutoff_configured=cutoff_configured,
        missing_eligible=missing_eligible,
        cutoff_eligible=cutoff_eligible,
        hard_max=hard_max,
    )
    if hard_max > 0 and (new_missing, new_cutoff) != (missing_limit, cutoff_limit):
        logger.debug(
            "{app}: Hard max {max} rebalanced to queues with work -- missing={m}, cutoff={c}",
            app=app_label,
            max=hard_max,
            m=new_missing,
            c=new_cutoff,
        )
    return new_missing, new_cutoff


async def _fetch_wanted_queues(
    *,
    fetch_missing: Callable[[], Awaitable[list]],
    fetch_cutoff: Callable[[], Awaitable[list]],
    missing_active: bool,
    cutoff_active: bool,
    app_label: str,
) -> tuple[list | None, list | None]:
    """Fetch both wanted queues, isolating an inactive queue's fetch failure (R-07).

    Spec Sec 3.1: inactive queues (configured search count 0) are ignored
    for grading. Active queues are fetched first, with no try -- an
    exception there propagates to the caller's existing abort block,
    because an active queue that cannot be fetched is unevaluated, which
    is Failed. Fetching active queues first also means a dead host aborts
    before any inactive endpoint is probed.

    Inactive queues are fetched afterward, each in its own error boundary:
    a failure there is logged (sanitized) and that queue's result stays
    None -- its dashboard count stays stale rather than zeroed. This
    helper never grades a cycle and never touches the instance's
    reachability state.

    Returns (missing, cutoff); a queue is None only when it was neither
    active nor fetched successfully.
    """
    missing: list | None = None
    cutoff: list | None = None

    if missing_active:
        missing = await fetch_missing()
    if cutoff_active:
        cutoff = await fetch_cutoff()

    if not missing_active:
        try:
            missing = await fetch_missing()
        except (httpx.HTTPError, pydantic.ValidationError) as exc:
            logger.warning(
                "{app}: Missing queue is inactive (search count 0) -- could not refresh "
                "its count, keeping previous value: {exc}",
                app=app_label,
                exc=_sanitize_exc(exc),
            )
    if not cutoff_active:
        try:
            cutoff = await fetch_cutoff()
        except (httpx.HTTPError, pydantic.ValidationError) as exc:
            logger.warning(
                "{app}: Cutoff queue is inactive (search count 0) -- could not refresh "
                "its count, keeping previous value: {exc}",
                app=app_label,
                exc=_sanitize_exc(exc),
            )

    return missing, cutoff


@dataclass(frozen=True)
class _TagScope:
    """Per-queue tag-resolution result for one cycle (TAGSCOPE-01..03, D-01..05, OQ1).

    ``missing_unresolved``/``cutoff_unresolved`` is True whenever that
    queue's configured tag could not be resolved -- the tag no longer
    exists in the *arr's tag list, or the tag-list fetch itself failed --
    set for an active OR inactive queue (OQ1): callers must force that
    queue's working variable to ``None`` either way so its counts and
    searched-log are never widened to the unscoped set. The warning
    (``ist["tag_warnings"]``) and the grading call
    (``CycleTally.mark_unevaluated``) only fire for an active queue (D-04)
    -- that gating happens inside ``_resolve_tag_scope``, not here.
    """

    missing_tag_id: int | None
    cutoff_tag_id: int | None
    missing_unresolved: bool
    cutoff_unresolved: bool


async def _resolve_tag_scope(
    *,
    instance_config: InstanceConfig,
    fetch_tags: Callable[[], Awaitable[list[Tag]]],
    ist: AppState,
    app_label: str,
    tally: CycleTally | None,
) -> _TagScope:
    """Resolve each configured queue's tag, deciding resolved vs skipped.

    Shared by all three ``run_*_cycle`` functions. Always resets
    ``ist["tag_warnings"]`` and ``ist["unresolved_tag_scopes"]`` first --
    this is TAGSCOPE-02's auto-clear: a tag that resolves on a later cycle
    leaves no stale warning or marker behind.

    When neither queue has a tag configured, returns immediately without
    calling ``fetch_tags``. Otherwise awaits ``fetch_tags()`` inside the
    ``(httpx.HTTPError, pydantic.ValidationError, ValueError)`` catch tuple
    -- widened by ``ValueError`` only, for ``get_json_list``'s malformed-
    response raise (Phase 80, same bug class as ``tag_autocomplete``); the
    tuple is never widened to a bare catch-all, per spec Sec7 (D-03/T-79-03).
    A fetch failure unresolves every configured queue with the fixed reason
    "couldn't load tags"; a successful fetch that simply lacks the
    configured tag name unresolves it with ``f"tag '{name}' not found"``
    (D-02/D-03). Both reasons are
    derived from ``tag_fetch_ok``, never from the caught exception's text
    (D-02, CLAUDE.md absolute rule) -- only the log line carries
    ``_sanitize_exc(exc)``.

    For every unresolved queue -- active OR inactive -- records
    ``ist["unresolved_tag_scopes"][field] = name`` (OQ1/D-05 revision 1):
    this is how a caller (and, downstream, the dashboard card) knows a
    queue's scope is unresolved even when it's inactive and shows no
    warning badge. The warning entry and the ``tally.mark_unevaluated``
    grading call are gated on the queue being active (D-04) -- an inactive
    queue's unresolved tag never produces a visible warning or grade
    effect, but its working variable is still forced to ``None`` by the
    caller so its counts freeze (TAGSCOPE-01).
    """
    ist["tag_warnings"] = []
    ist["unresolved_tag_scopes"] = {}

    if not instance_config.missing_tag and not instance_config.cutoff_tag:
        return _TagScope(
            missing_tag_id=None,
            cutoff_tag_id=None,
            missing_unresolved=False,
            cutoff_unresolved=False,
        )

    tag_fetch_ok = False
    try:
        tags = await fetch_tags()
        tag_fetch_ok = True
    except (httpx.HTTPError, pydantic.ValidationError, ValueError) as exc:
        logger.warning(
            "{app}: Failed to fetch tags -- tag-scoped queues skipped this cycle: {exc}",
            app=app_label,
            exc=_sanitize_exc(exc),
        )
        tags = []

    missing_tag_id: int | None = None
    cutoff_tag_id: int | None = None
    missing_unresolved = False
    cutoff_unresolved = False

    for field, tag_name, queue_label in (
        ("missing", instance_config.missing_tag, "Missing"),
        ("cutoff", instance_config.cutoff_tag, "Cutoff"),
    ):
        if not tag_name:
            continue
        tag_id = resolve_tag_id(tag_name, tags)
        if tag_id is None:
            reason = f"tag '{tag_name}' not found" if tag_fetch_ok else "couldn't load tags"
            ist["unresolved_tag_scopes"][field] = tag_name
            active = getattr(instance_config, f"search_{field}_count") > 0
            if active:
                logger.warning(
                    "{app}: {queue} queue skipped -- {reason}",
                    app=app_label,
                    queue=queue_label,
                    reason=reason,
                )
                ist["tag_warnings"].append({
                    "tag": tag_name,
                    "field": field,
                    "reason": "not_found" if tag_fetch_ok else "fetch_failed",
                })
                if tally is not None:
                    tally.mark_unevaluated(field, reason)
            else:
                logger.debug(
                    "{app}: {queue} queue tag unresolved but inactive -- counts frozen, no warning",
                    app=app_label,
                    queue=queue_label,
                )
            if field == "missing":
                missing_unresolved = True
            else:
                cutoff_unresolved = True
        elif field == "missing":
            missing_tag_id = tag_id
        else:
            cutoff_tag_id = tag_id

    return _TagScope(
        missing_tag_id=missing_tag_id,
        cutoff_tag_id=cutoff_tag_id,
        missing_unresolved=missing_unresolved,
        cutoff_unresolved=cutoff_unresolved,
    )


def _stamp_scoped_counts(ist: AppState, field: str, tag_name: str | None) -> None:
    """Record the tag a committed scoped count was computed under (D-05 revision 1).

    Called at every scoped-count commit, never for a skipped queue -- the
    card trusts a kept count only if it was computed under the tag that is
    now configured. Replaces a missing or non-dict ``scoped_count_tags``
    value with a fresh dict first, preserving the other field's stamp.
    """
    existing = ist.get("scoped_count_tags")
    if not isinstance(existing, dict):
        existing = {}
    existing[field] = tag_name
    ist["scoped_count_tags"] = existing


def _clear_faulted_scoped_counts(
    ist: AppState,
    scope: _TagScope | None,
    instance_config: InstanceConfig,
    *,
    missing_fields: tuple[str, ...],
    cutoff_fields: tuple[str, ...],
) -> None:
    """Clear a refresh data fault's scoped counts without erasing a skipped queue's last-good counts (D-05).

    A malformed record in one queue must never widen OR erase the OTHER
    queue's counts when that queue's tag is unresolved -- or when its scope
    was never determined because the fault happened before/during tag
    resolution (``scope is None``). Only a queue whose tag scope RESOLVED
    this refresh has its listed fields cleared to None. Never reads or
    writes ``ist["scoped_count_tags"]`` or ``ist["unresolved_tag_scopes"]``
    -- the card (``routes._scoped_count_unknown``) shows a cleared scoped
    count as unknown for a tag-scoped queue, never the raw whole-library
    count. An untagged queue's cleared count falls back to the raw count,
    which is that queue's real scope.
    """
    missing_preserved = (scope is not None and scope.missing_unresolved) or (
        scope is None and bool(instance_config.missing_tag)
    )
    cutoff_preserved = (scope is not None and scope.cutoff_unresolved) or (
        scope is None and bool(instance_config.cutoff_tag)
    )
    if not missing_preserved:
        for field in missing_fields:
            ist[field] = None
    if not cutoff_preserved:
        for field in cutoff_fields:
            ist[field] = None


async def run_radarr_cycle(
    client: RadarrClient,
    state: TriggarrState,
    instance_name: str,
    instance_config: InstanceConfig,
    settings: Settings,
    db: aiosqlite.Connection,
    *,
    get_tags_fn: Callable[[], Awaitable[list[Tag]]] | None = None,
) -> TriggarrState:
    """Run one complete Radarr search cycle: missing batch then cutoff batch.

    Fetches the current wanted-missing and wanted-cutoff lists, filters
    to monitored items, slices a batch from each queue using independent
    cursors, triggers ``MoviesSearch`` for each movie, and logs the result.

    Individual search failures are logged and skipped (skip-and-continue).
    If the fetch calls themselves fail (network/HTTP errors), the entire
    cycle aborts and cursors remain unchanged.

    Args:
        client: Connected Radarr API client.
        state: Mutable application state (modified in place).
        instance_name: Name of this Radarr instance (e.g., "Default", "4K").
        instance_config: Configuration for this specific instance.
        settings: Application settings with general config (hard_max, skip_unreleased).
        db: Open aiosqlite connection for search history persistence.

    Returns:
        Updated state with new cursor positions and last_run timestamp.
    """
    cycle_start = time.monotonic()
    if instance_name not in state.get("radarr", {}):
        logger.warning("Radarr: instance {name} not in state -- skipping", name=instance_name)
        return state
    ist = state["radarr"][instance_name]
    tally = CycleTally()
    missing_active = instance_config.search_missing_count > 0
    cutoff_active = instance_config.search_cutoff_count > 0

    try:
        missing, cutoff = await _fetch_wanted_queues(
            # Non-object records come back as sent and are skipped per item
            # below (ROBUST-01); the default strict fetch would reject the page.
            fetch_missing=functools.partial(client.get_wanted_missing, allow_non_object_records=True),
            fetch_cutoff=functools.partial(client.get_wanted_cutoff, allow_non_object_records=True),
            missing_active=missing_active,
            cutoff_active=cutoff_active,
            app_label="Radarr",
        )
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning("Radarr: Cycle aborted -- {exc}", exc=_sanitize_exc(exc))
        _mark_unreachable(ist)
        ist["tag_warnings"] = []
        tally.record_fetch_failure(_sanitize_exc(exc))
        _finalize_cycle(ist, tally, instance_config)
        return state

    if missing is None and cutoff is None:
        # R-07: both queues inactive and neither could be fetched.
        _finish_both_inactive_unreachable(
            ist=ist, tally=tally, instance_config=instance_config, app_label="Radarr"
        )
        return state

    # Library count is cosmetic (dashboard denominator) -- never abort
    # the search cycle if it fails.
    try:
        total_items = await client.get_library_count()
    except (httpx.HTTPError, pydantic.ValidationError, ValueError):
        total_items = ist.get("total_items")  # keep previous value

    # Track connection health (WEBU-06)
    ist["connected"] = True
    ist["unreachable_since"] = None

    # Cache raw item counts before filtering (WEBU-04). A queue that could
    # not be fetched (inactive + failed) keeps its previous value (R-07).
    if missing is not None:
        ist["missing_count"] = len(missing)
    if cutoff is not None:
        ist["cutoff_count"] = len(cutoff)
    ist["total_items"] = total_items

    # Apply hard max cap (SRCH-12)
    hard_max = settings.general.hard_max_per_cycle
    orig_missing, orig_cutoff = instance_config.search_missing_count, instance_config.search_cutoff_count
    missing_limit, cutoff_limit = _cap_and_log(
        app_label="Radarr", missing_configured=orig_missing, cutoff_configured=orig_cutoff, hard_max=hard_max
    )

    # --- Tag resolution (only when at least one tag is configured) ---
    # RES-03: resolve via the cache-aware resolver when supplied
    # (scheduler/search_now), else fall back to the direct client call
    # (backward-compatible None default — keeps existing tests passing).
    scope = await _resolve_tag_scope(
        instance_config=instance_config,
        fetch_tags=get_tags_fn if get_tags_fn is not None else client.get_tags,
        ist=ist,
        app_label="Radarr",
        tally=tally,
    )
    # TAGSCOPE-01 / D-05 / OQ1 -- a tag-scoped queue whose tag can't be
    # resolved is never widened. None reuses the Phase 78 contract: no
    # dispatch, eligible/monitored counts and searched-log untouched.
    # Applies to inactive queues too; warning and grading were already
    # gated on active inside _resolve_tag_scope.
    if scope.missing_unresolved:
        missing = None
    if scope.cutoff_unresolved:
        cutoff = None

    # --- Missing queue: filter chain (guarded -- None means the fetch
    # didn't run or failed, R-07/TAGSCOPE-01; the previous eligible/monitored
    # counts and searched-log stay untouched rather than being wiped to zero).
    # Malformed records are skipped and counted per item (_screen_queue,
    # ROBUST-01), so the rest of the queue is still searched. Each field is
    # checked just before the step that reads it -- tags before the tag
    # filter, release dates before the unreleased filter, the ID before
    # dispatch -- so an unmonitored, out-of-scope or unreleased movie is never
    # counted as malformed for a field nothing reads. missing_monitored counts
    # monitored movies minus those skipped as malformed. The try/except below
    # is the backstop for any other unexpected shape, mirroring the cutoff
    # chain's guard. Counts are written to ist only once the whole chain has
    # succeeded, so a fault leaves the previous monitored/eligible pair intact. ---
    if missing is not None:
        try:
            missing = _screen_queue(missing, app_label="Radarr", queue="missing", tally=tally)
            missing = filter_monitored(missing)
            if scope.missing_tag_id is not None:
                missing = _screen_queue(missing, app_label="Radarr", queue="missing", tally=tally, tags_at=("tags",))
            missing_monitored = len(missing)
            if scope.missing_tag_id is not None:
                missing = filter_by_tag(missing, scope.missing_tag_id, _radarr_tags)
                logger.debug("Radarr: Tag filter applied -- {n} missing items match tag", n=len(missing))
            if settings.general.skip_unreleased:
                screened = _screen_queue(
                    missing, app_label="Radarr", queue="missing", tally=tally,
                    date_fields=("digitalRelease", "physicalRelease"),
                )
                missing_monitored -= len(missing) - len(screened)
                missing = filter_unreleased_movies(screened)
                skipped_unreleased = missing_monitored - len(missing)
                if skipped_unreleased > 0:
                    logger.info("Radarr: {n} unreleased movies skipped", n=skipped_unreleased)
            screened = _screen_queue(missing, app_label="Radarr", queue="missing", tally=tally, key_fields=("id",))
            missing_monitored -= len(missing) - len(screened)
            missing = screened
            ist["missing_monitored"] = missing_monitored
            ist["missing_eligible"] = len(missing)
            _stamp_scoped_counts(ist, "missing", instance_config.missing_tag or None)
        except (AttributeError, KeyError, TypeError) as exc:
            logger.warning(
                "Radarr: Missing queue filter chain faulted on malformed data ({etype}) -- "
                "skipping missing this cycle",
                etype=type(exc).__name__,
            )
            missing = None
            if missing_active:
                tally.mark_unevaluated("missing", f"malformed data ({type(exc).__name__})")

    # --- Cutoff queue: filter chain (moved up so both queues' eligible
    # counts are known before rebalancing hard-max slots, R-01 amended).
    # Guarded against malformed nested records (e.g. non-iterable tags):
    # a cutoff-side data fault must never block the missing queue's
    # dispatch below -- this is the pre-existing per-app guarantee this
    # reordering must not regress. Malformed records are skipped and counted
    # per item via _screen_queue, each field just before the step that reads
    # it; the try/except is the backstop for anything else. On a fault
    # the queue is left unprocessed (None): never dispatched, its
    # searched-log untouched, and -- when active -- marked unevaluated so
    # the cycle can never grade Nothing needed searching (spec 3.1). ---
    if cutoff is not None:
        try:
            cutoff = _screen_queue(cutoff, app_label="Radarr", queue="cutoff", tally=tally)
            cutoff = filter_monitored(cutoff)
            if scope.cutoff_tag_id is not None:
                cutoff = _screen_queue(cutoff, app_label="Radarr", queue="cutoff", tally=tally, tags_at=("tags",))
                cutoff = filter_by_tag(cutoff, scope.cutoff_tag_id, _radarr_tags)
                logger.debug("Radarr: Tag filter applied -- {n} cutoff items match tag", n=len(cutoff))
            cutoff = _screen_queue(cutoff, app_label="Radarr", queue="cutoff", tally=tally, key_fields=("id",))
        except (AttributeError, KeyError, TypeError) as exc:
            logger.warning(
                "Radarr: Cutoff queue filter chain faulted on malformed data ({etype}) -- "
                "skipping cutoff this cycle",
                etype=type(exc).__name__,
            )
            cutoff = None
            if cutoff_active:
                tally.mark_unevaluated("cutoff", f"malformed data ({type(exc).__name__})")

    missing_eligible_count = len(missing) if missing is not None else 0
    cutoff_eligible_count = len(cutoff) if cutoff is not None else 0
    tally.record_eligible("missing", missing_eligible_count)
    tally.record_eligible("cutoff", cutoff_eligible_count)

    # --- Reallocate unused hard-max budget to a starved queue with work (R-01 amended) ---
    missing_limit, cutoff_limit = _rebalance_and_log(
        app_label="Radarr",
        missing_limit=missing_limit,
        cutoff_limit=cutoff_limit,
        missing_configured=orig_missing,
        cutoff_configured=orig_cutoff,
        missing_eligible=missing_eligible_count,
        cutoff_eligible=cutoff_eligible_count,
        hard_max=hard_max,
    )

    # --- Missing queue: dispatch (guarded -- a None queue is never dispatched,
    # and its searched-log is left exactly as it was, R-07) ---
    if missing is not None:
        batch, new_log, pass_done = prioritize_batch(
            missing, ist.get("missing_searched", []), missing_limit,
            key_fn=lambda m: str(m["id"]),
        )
        for movie in batch:
            await _search_and_record(
                command=lambda mid=movie["id"]: client.search_movies([mid]),
                tally=tally,
                db=db,
                app_label="Radarr",
                queue="missing",
                item_name=movie.get("title", "unknown"),
                instance_name=instance_name,
                max_rows=settings.general.max_history_rows,
                item_id=movie.get("id"),
                instance_stable_id=instance_config.id,
            )
        ist["missing_searched"] = [] if pass_done else new_log
        if pass_done:
            ist["missing_pass"] = ist.get("missing_pass", 0) + 1
            logger.info(
                "Radarr: Missing pass {p} complete ({n} searched)",
                p=ist["missing_pass"],
                n=len(new_log),
            )

    # --- Cutoff queue: dispatch ---
    if cutoff is not None:
        batch, new_log, pass_done = prioritize_batch(
            cutoff, ist.get("cutoff_searched", []), cutoff_limit,
            key_fn=lambda m: str(m["id"]),
        )
        for movie in batch:
            await _search_and_record(
                command=lambda mid=movie["id"]: client.search_movies([mid]),
                tally=tally,
                db=db,
                app_label="Radarr",
                queue="cutoff",
                item_name=movie.get("title", "unknown"),
                instance_name=instance_name,
                max_rows=settings.general.max_history_rows,
                item_id=movie.get("id"),
                instance_stable_id=instance_config.id,
            )
        ist["cutoff_searched"] = [] if pass_done else new_log
        if pass_done:
            ist["cutoff_pass"] = ist.get("cutoff_pass", 0) + 1
            logger.info(
                "Radarr: Cutoff pass {p} complete ({n} searched)",
                p=ist["cutoff_pass"],
                n=len(new_log),
            )

    # --- Grade the cycle and stamp timestamps (R-04/R-05/OUTCOME-01/02) ---
    _finalize_cycle(ist, tally, instance_config)

    # --- Diagnostic summary ---
    elapsed = time.monotonic() - cycle_start
    logger.info(
        "Radarr: Cycle completed in {elapsed:.1f}s -- {fetched} fetched, {accepted} accepted, "
        "{failed} failed, {unsaved} history not saved -- grade {grade}",
        elapsed=elapsed,
        fetched=(ist.get("missing_count") or 0) + (ist.get("cutoff_count") or 0),
        accepted=tally.accepted,
        failed=tally.failed,
        unsaved=tally.persistence_failed,
        grade=ist["last_cycle"]["grade"],
    )

    return state


async def run_sonarr_cycle(
    client: SonarrClient,
    state: TriggarrState,
    instance_name: str,
    instance_config: InstanceConfig,
    settings: Settings,
    db: aiosqlite.Connection,
    *,
    get_tags_fn: Callable[[], Awaitable[list[Tag]]] | None = None,
) -> TriggarrState:
    """Run one complete Sonarr search cycle: missing batch then cutoff batch.

    Fetches the current wanted-missing and wanted-cutoff episode lists,
    filters to monitored episodes with past air dates, deduplicates to
    unique seasons, slices a batch from each queue using independent
    cursors, triggers ``SeasonSearch`` for each season, and logs the result.

    Individual search failures are logged and skipped (skip-and-continue).
    If the fetch calls themselves fail (network/HTTP errors), the entire
    cycle aborts and cursors remain unchanged.

    Args:
        client: Connected Sonarr API client.
        state: Mutable application state (modified in place).
        instance_name: Name of this Sonarr instance (e.g., "Default").
        instance_config: Configuration for this specific instance.
        settings: Application settings with general config (hard_max, etc.).
        db: Open aiosqlite connection for search history persistence.

    Returns:
        Updated state with new cursor positions and last_run timestamp.
    """
    cycle_start = time.monotonic()
    if instance_name not in state.get("sonarr", {}):
        logger.warning("Sonarr: instance {name} not in state -- skipping", name=instance_name)
        return state
    ist = state["sonarr"][instance_name]
    tally = CycleTally()
    missing_active = instance_config.search_missing_count > 0
    cutoff_active = instance_config.search_cutoff_count > 0

    try:
        missing_episodes, cutoff_episodes = await _fetch_wanted_queues(
            # Non-object records come back as sent and are skipped per item
            # below (ROBUST-01); the default strict fetch would reject the page.
            fetch_missing=functools.partial(client.get_wanted_missing, allow_non_object_records=True),
            fetch_cutoff=functools.partial(client.get_wanted_cutoff, allow_non_object_records=True),
            missing_active=missing_active,
            cutoff_active=cutoff_active,
            app_label="Sonarr",
        )
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning("Sonarr: Cycle aborted -- {exc}", exc=_sanitize_exc(exc))
        _mark_unreachable(ist)
        ist["tag_warnings"] = []
        tally.record_fetch_failure(_sanitize_exc(exc))
        _finalize_cycle(ist, tally, instance_config)
        return state

    if missing_episodes is None and cutoff_episodes is None:
        # R-07: both queues inactive and neither could be fetched.
        _finish_both_inactive_unreachable(
            ist=ist, tally=tally, instance_config=instance_config, app_label="Sonarr"
        )
        return state

    # Library count is cosmetic (dashboard denominator) -- never abort
    # the search cycle if it fails.
    try:
        total_items = await client.get_library_count()
    except (httpx.HTTPError, pydantic.ValidationError, ValueError):
        total_items = ist.get("total_items")  # keep previous value

    # Track connection health (WEBU-06)
    ist["connected"] = True
    ist["unreachable_since"] = None

    # Cache raw item counts before filtering (WEBU-04). A queue that could
    # not be fetched (inactive + failed) keeps its previous value (R-07).
    if missing_episodes is not None:
        ist["missing_count"] = len(missing_episodes)
    if cutoff_episodes is not None:
        ist["cutoff_count"] = len(cutoff_episodes)
    ist["total_items"] = total_items

    # Apply hard max cap (SRCH-12)
    hard_max = settings.general.hard_max_per_cycle
    orig_missing, orig_cutoff = instance_config.search_missing_count, instance_config.search_cutoff_count
    missing_limit, cutoff_limit = _cap_and_log(
        app_label="Sonarr", missing_configured=orig_missing, cutoff_configured=orig_cutoff, hard_max=hard_max
    )

    # --- Tag resolution (only when at least one tag is configured) ---
    # RES-03: resolve via the cache-aware resolver when supplied
    # (scheduler/search_now), else fall back to the direct client call
    # (backward-compatible None default — keeps existing tests passing).
    scope = await _resolve_tag_scope(
        instance_config=instance_config,
        fetch_tags=get_tags_fn if get_tags_fn is not None else client.get_tags,
        ist=ist,
        app_label="Sonarr",
        tally=tally,
    )
    # TAGSCOPE-01 / D-05 / OQ1 -- a tag-scoped queue whose tag can't be
    # resolved is never widened. None reuses the Phase 78 contract: no
    # dispatch, eligible/searchable counts and searched-log untouched.
    # Applies to inactive queues too; warning and grading were already
    # gated on active inside _resolve_tag_scope.
    if scope.missing_unresolved:
        missing_episodes = None
    if scope.cutoff_unresolved:
        cutoff_episodes = None

    # --- Missing queue: filter chain (guarded -- None means the fetch
    # didn't run or failed, R-07/TAGSCOPE-01; the previous eligible/searchable
    # counts and searched-log stay untouched rather than being wiped to zero).
    # Malformed records are skipped and counted per item via _screen_queue
    # (ROBUST-01), each field just before the step that reads it: the air date
    # for monitored episodes, the series and its tags before the tag filter,
    # seriesId/seasonNumber and the series before season dedup -- so an
    # unmonitored, unaired or out-of-scope episode is never counted for a
    # field nothing reads; the
    # try/except below is the backstop for any other unexpected fault,
    # mirroring the cutoff chain's existing guard. ---
    missing_seasons: list[dict] = []
    if missing_episodes is not None:
        try:
            missing_episodes = _screen_queue(missing_episodes, app_label="Sonarr", queue="missing", tally=tally)
            missing_episodes = filter_monitored(missing_episodes)
            missing_episodes = _screen_queue(
                missing_episodes, app_label="Sonarr", queue="missing", tally=tally, date_fields=("airDateUtc",)
            )
            missing_episodes = filter_sonarr_episodes(missing_episodes)
            if scope.missing_tag_id is not None:
                missing_episodes = _screen_queue(
                    missing_episodes, app_label="Sonarr", queue="missing", tally=tally,
                    nested_key="series", tags_at=("series", "tags"),
                )
                missing_episodes = filter_by_tag(missing_episodes, scope.missing_tag_id, _sonarr_tags)
                logger.debug("Sonarr: Tag filter applied -- {n} missing episodes match tag", n=len(missing_episodes))
            missing_episodes = _screen_queue(
                missing_episodes, app_label="Sonarr", queue="missing", tally=tally,
                key_fields=("seriesId", "seasonNumber"), nested_key="series",
            )
            missing_seasons = deduplicate_to_seasons(missing_episodes)
            ist["missing_eligible"] = len(missing_episodes)
            ist["missing_searchable"] = len(missing_seasons)
            _stamp_scoped_counts(ist, "missing", instance_config.missing_tag or None)
        except (AttributeError, KeyError, TypeError) as exc:
            logger.warning(
                "Sonarr: Missing queue filter chain faulted on malformed data ({etype}) -- "
                "skipping missing this cycle",
                etype=type(exc).__name__,
            )
            missing_seasons = []
            missing_episodes = None
            if missing_active:
                tally.mark_unevaluated("missing", f"malformed data ({type(exc).__name__})")

    # --- Cutoff queue: filter chain (moved up so both queues' eligible
    # counts are known before rebalancing hard-max slots, R-01 amended).
    # Malformed records are skipped and counted per item via _screen_queue,
    # each field just before the step that reads it, as in the missing chain
    # (ROBUST-01); the except below is the backstop for any other unexpected
    # fault -- a
    # cutoff-side data fault must never block the missing queue's dispatch
    # above, which is the pre-existing per-app guarantee this reordering
    # must not regress. On a fault the queue is left unprocessed (None):
    # never dispatched, its searched-log and searchable count untouched,
    # and -- when active -- marked unevaluated so the cycle can never
    # grade Nothing needed searching (spec 3.1). ---
    cutoff_seasons: list[dict] = []
    if cutoff_episodes is not None:
        try:
            cutoff_episodes = _screen_queue(cutoff_episodes, app_label="Sonarr", queue="cutoff", tally=tally)
            cutoff_episodes = filter_monitored(cutoff_episodes)
            cutoff_episodes = _screen_queue(
                cutoff_episodes, app_label="Sonarr", queue="cutoff", tally=tally, date_fields=("airDateUtc",)
            )
            cutoff_episodes = filter_sonarr_episodes(cutoff_episodes)
            if scope.cutoff_tag_id is not None:
                cutoff_episodes = _screen_queue(
                    cutoff_episodes, app_label="Sonarr", queue="cutoff", tally=tally,
                    nested_key="series", tags_at=("series", "tags"),
                )
                cutoff_episodes = filter_by_tag(cutoff_episodes, scope.cutoff_tag_id, _sonarr_tags)
                logger.debug("Sonarr: Tag filter applied -- {n} cutoff episodes match tag", n=len(cutoff_episodes))
            cutoff_episodes = _screen_queue(
                cutoff_episodes, app_label="Sonarr", queue="cutoff", tally=tally,
                key_fields=("seriesId", "seasonNumber"), nested_key="series",
            )
            cutoff_seasons = deduplicate_to_seasons(cutoff_episodes)
            ist["cutoff_searchable"] = len(cutoff_seasons)
            _stamp_scoped_counts(ist, "cutoff", instance_config.cutoff_tag or None)
        except (AttributeError, KeyError, TypeError) as exc:
            logger.warning(
                "Sonarr: Cutoff queue filter chain faulted on malformed data ({etype}) -- "
                "skipping cutoff this cycle",
                etype=type(exc).__name__,
            )
            cutoff_seasons = []
            cutoff_episodes = None
            if cutoff_active:
                tally.mark_unevaluated("cutoff", f"malformed data ({type(exc).__name__})")

    tally.record_eligible("missing", len(missing_seasons))
    tally.record_eligible("cutoff", len(cutoff_seasons))

    # --- Reallocate unused hard-max budget to a starved queue with work (R-01 amended) ---
    missing_limit, cutoff_limit = _rebalance_and_log(
        app_label="Sonarr",
        missing_limit=missing_limit,
        cutoff_limit=cutoff_limit,
        missing_configured=orig_missing,
        cutoff_configured=orig_cutoff,
        missing_eligible=len(missing_seasons),
        cutoff_eligible=len(cutoff_seasons),
        hard_max=hard_max,
    )

    def _season_key(s: dict) -> str:
        return f'{s["seriesId"]}:{s["seasonNumber"]}'

    # --- Missing queue: dispatch (guarded -- a None queue is never dispatched,
    # and its searched-log is left exactly as it was, R-07) ---
    # `claimed` holds the missing batch's keys, taken on attempt (D-05): it is
    # passed into the cutoff prioritize_batch call below as exclude_keys so a
    # season eligible for both queues gets at most one engine dispatch per
    # cycle. It is a local, cycle-scoped variable -- never persisted to `ist`.
    claimed: frozenset[str] = frozenset()
    if missing_episodes is not None:
        batch, new_log, pass_done = prioritize_batch(
            missing_seasons, ist.get("missing_searched", []), missing_limit,
            key_fn=_season_key,
        )
        # Claim happens unconditionally on attempt, independent of
        # _search_and_record's return value below (D-05: "even if its
        # command fails").
        claimed = frozenset(_season_key(s) for s in batch)
        for season in batch:
            await _search_and_record(
                command=lambda sid=season["seriesId"], sn=season["seasonNumber"]: client.search_season(sid, sn),
                tally=tally,
                db=db,
                app_label="Sonarr",
                queue="missing",
                item_name=season.get("display_name", "unknown"),
                instance_name=instance_name,
                max_rows=settings.general.max_history_rows,
                item_id=season.get("seriesId"),
                season_number=season.get("seasonNumber"),
                missing_count=season.get("episode_count"),
                instance_stable_id=instance_config.id,
            )
        ist["missing_searched"] = [] if pass_done else new_log
        if pass_done:
            ist["missing_pass"] = ist.get("missing_pass", 0) + 1
            logger.info(
                "Sonarr: Missing pass {p} complete ({n} searched)",
                p=ist["missing_pass"],
                n=len(new_log),
            )

    # --- Cutoff queue: dispatch ---
    if cutoff_episodes is not None:
        # `cutoff_seasons` is passed in FULL and unfiltered -- exclusion
        # happens inside prioritize_batch at the batch-candidacy step only
        # (exclude_keys). Pre-filtering this list before the call would drop
        # a claimed season out of eligible_ids and silently prune it from
        # cutoff_searched, breaking DEDUP-02's "neither marked as searched
        # nor removed" (RESEARCH Pitfall 3).
        if cutoff_limit > 0:
            for season in cutoff_seasons:
                if _season_key(season) in claimed:
                    logger.info(
                        "Sonarr: Upgrade queue skipped {series} S{season} —"
                        " already attempted by missing queue this cycle",
                        series=season.get("series_title", f"Series {season['seriesId']}"),
                        season=season["seasonNumber"],
                    )
        batch, new_log, pass_done = prioritize_batch(
            cutoff_seasons, ist.get("cutoff_searched", []), cutoff_limit,
            key_fn=_season_key, exclude_keys=claimed,
        )
        for season in batch:
            await _search_and_record(
                command=lambda sid=season["seriesId"], sn=season["seasonNumber"]: client.search_season(sid, sn),
                tally=tally,
                db=db,
                app_label="Sonarr",
                queue="cutoff",
                item_name=season.get("display_name", "unknown"),
                instance_name=instance_name,
                max_rows=settings.general.max_history_rows,
                item_id=season.get("seriesId"),
                season_number=season.get("seasonNumber"),
                missing_count=season.get("episode_count"),
                instance_stable_id=instance_config.id,
            )
        ist["cutoff_searched"] = [] if pass_done else new_log
        if pass_done:
            ist["cutoff_pass"] = ist.get("cutoff_pass", 0) + 1
            logger.info(
                "Sonarr: Cutoff pass {p} complete ({n} searched)",
                p=ist["cutoff_pass"],
                n=len(new_log),
            )

    # --- Grade the cycle and stamp timestamps (R-04/R-05/OUTCOME-01/02) ---
    _finalize_cycle(ist, tally, instance_config)

    # --- Diagnostic summary ---
    elapsed = time.monotonic() - cycle_start
    logger.info(
        "Sonarr: Cycle completed in {elapsed:.1f}s -- {fetched} fetched, {accepted} accepted, "
        "{failed} failed, {unsaved} history not saved -- grade {grade}",
        elapsed=elapsed,
        fetched=(ist.get("missing_count") or 0) + (ist.get("cutoff_count") or 0),
        accepted=tally.accepted,
        failed=tally.failed,
        unsaved=tally.persistence_failed,
        grade=ist["last_cycle"]["grade"],
    )

    return state


async def run_lidarr_cycle(
    client: LidarrClient,
    state: TriggarrState,
    instance_name: str,
    instance_config: InstanceConfig,
    settings: Settings,
    db: aiosqlite.Connection,
    *,
    get_tags_fn: Callable[[], Awaitable[list[Tag]]] | None = None,
) -> TriggarrState:
    """Run one complete Lidarr search cycle: missing batch then cutoff batch.

    Fetches the current wanted-missing and wanted-cutoff album lists,
    filters to monitored items, slices a batch from each queue using
    independent cursors, triggers ``AlbumSearch`` for each album, and
    logs the result.

    Albums are atomic search units (like Radarr movies), so no
    deduplication step is needed (unlike Sonarr episodes → seasons).

    Individual search failures are logged and skipped (skip-and-continue).
    If the fetch calls themselves fail (network/HTTP errors), the entire
    cycle aborts and cursors remain unchanged.

    Args:
        client: Connected Lidarr API client.
        state: Mutable application state (modified in place).
        instance_name: Name of this Lidarr instance (e.g., "Default").
        instance_config: Configuration for this specific instance.
        settings: Application settings with general config (hard_max, etc.).
        db: Open aiosqlite connection for search history persistence.

    Returns:
        Updated state with new cursor positions and last_run timestamp.
    """
    cycle_start = time.monotonic()
    if instance_name not in state.get("lidarr", {}):
        logger.warning("Lidarr: instance {name} not in state -- skipping", name=instance_name)
        return state
    ist = state["lidarr"][instance_name]
    tally = CycleTally()
    missing_active = instance_config.search_missing_count > 0
    cutoff_active = instance_config.search_cutoff_count > 0

    try:
        missing, cutoff = await _fetch_wanted_queues(
            # Non-object records come back as sent and are skipped per item
            # below (ROBUST-01); the default strict fetch would reject the page.
            fetch_missing=functools.partial(client.get_wanted_missing, allow_non_object_records=True),
            fetch_cutoff=functools.partial(client.get_wanted_cutoff, allow_non_object_records=True),
            missing_active=missing_active,
            cutoff_active=cutoff_active,
            app_label="Lidarr",
        )
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning("Lidarr: Cycle aborted -- {exc}", exc=_sanitize_exc(exc))
        _mark_unreachable(ist)
        ist["tag_warnings"] = []
        tally.record_fetch_failure(_sanitize_exc(exc))
        _finalize_cycle(ist, tally, instance_config)
        return state

    if missing is None and cutoff is None:
        # R-07: both queues inactive and neither could be fetched.
        _finish_both_inactive_unreachable(
            ist=ist, tally=tally, instance_config=instance_config, app_label="Lidarr"
        )
        return state

    # Library count is cosmetic (dashboard denominator) -- never abort
    # the search cycle if it fails.
    try:
        total_items = await client.get_library_count()
    except (httpx.HTTPError, pydantic.ValidationError, ValueError):
        total_items = ist.get("total_items")  # keep previous value

    # Track connection health
    ist["connected"] = True
    ist["unreachable_since"] = None

    # Cache raw item counts before filtering. A queue that could not be
    # fetched (inactive + failed) keeps its previous value (R-07).
    if missing is not None:
        ist["missing_count"] = len(missing)
    if cutoff is not None:
        ist["cutoff_count"] = len(cutoff)
    ist["total_items"] = total_items

    # Apply hard max cap
    hard_max = settings.general.hard_max_per_cycle
    orig_missing, orig_cutoff = instance_config.search_missing_count, instance_config.search_cutoff_count
    missing_limit, cutoff_limit = _cap_and_log(
        app_label="Lidarr", missing_configured=orig_missing, cutoff_configured=orig_cutoff, hard_max=hard_max
    )

    # --- Tag resolution (only when at least one tag is configured) ---
    # RES-03: resolve via the cache-aware resolver when supplied
    # (scheduler/search_now), else fall back to the direct client call
    # (backward-compatible None default — keeps existing tests passing).
    scope = await _resolve_tag_scope(
        instance_config=instance_config,
        fetch_tags=get_tags_fn if get_tags_fn is not None else client.get_tags,
        ist=ist,
        app_label="Lidarr",
        tally=tally,
    )
    # TAGSCOPE-01 / D-05 / OQ1 -- a tag-scoped queue whose tag can't be
    # resolved is never widened. None reuses the Phase 78 contract: no
    # dispatch, eligible/monitored counts and searched-log untouched.
    # Applies to inactive queues too; warning and grading were already
    # gated on active inside _resolve_tag_scope.
    if scope.missing_unresolved:
        missing = None
    if scope.cutoff_unresolved:
        cutoff = None

    # --- Missing queue: filter chain (guarded -- None means the fetch
    # didn't run or failed, R-07/TAGSCOPE-01; the previous eligible/monitored
    # counts and searched-log stay untouched rather than being wiped to zero).
    # Malformed records are skipped and counted per item (_screen_queue,
    # ROBUST-01), each field just before the step that reads it: the nested
    # "artist" object and its tags only on monitored albums of a tag-scoped
    # queue -- the only path that ever reads "artist" (Pitfall 4) -- and the ID
    # only on albums that reach dispatch, so an unmonitored or out-of-scope
    # album is never counted for a field nothing reads; missing_monitored
    # counts monitored albums minus those skipped as malformed. The try/except below is the backstop for any other
    # unexpected fault, mirroring the cutoff chain's existing guard. Counts are
    # written to ist only once the whole chain has succeeded, so a fault leaves
    # the previous monitored/eligible pair intact. ---
    if missing is not None:
        try:
            tagged = scope.missing_tag_id is not None
            missing = _screen_queue(missing, app_label="Lidarr", queue="missing", tally=tally)
            missing = filter_monitored(missing)
            if tagged:
                missing = _screen_queue(
                    missing, app_label="Lidarr", queue="missing", tally=tally,
                    nested_key="artist", tags_at=("artist", "tags"),
                )
            missing_monitored = len(missing)
            if tagged:
                missing = filter_by_tag(missing, scope.missing_tag_id, _lidarr_tags)
                logger.debug("Lidarr: Tag filter applied -- {n} missing items match tag", n=len(missing))
            screened = _screen_queue(missing, app_label="Lidarr", queue="missing", tally=tally, key_fields=("id",))
            missing_monitored -= len(missing) - len(screened)
            missing = screened
            ist["missing_monitored"] = missing_monitored
            ist["missing_eligible"] = len(missing)
            _stamp_scoped_counts(ist, "missing", instance_config.missing_tag or None)
        except (AttributeError, KeyError, TypeError) as exc:
            logger.warning(
                "Lidarr: Missing queue filter chain faulted on malformed data ({etype}) -- "
                "skipping missing this cycle",
                etype=type(exc).__name__,
            )
            missing = None
            if missing_active:
                tally.mark_unevaluated("missing", f"malformed data ({type(exc).__name__})")

    # --- Cutoff queue: filter chain (moved up so both queues' eligible
    # counts are known before rebalancing hard-max slots, R-01 amended).
    # Malformed records are skipped and counted per item via _screen_queue
    # (the nested "artist" object and its tags only when this queue has a tag
    # configured, Pitfall 4); the except below is the backstop for any other unexpected fault -- a
    # cutoff-side data fault must never block the missing queue's dispatch
    # above, which is the pre-existing per-app guarantee this reordering
    # must not regress. On a fault the queue is left unprocessed (None):
    # never dispatched, its searched-log untouched, and -- when active --
    # marked unevaluated so the cycle can never grade Nothing needed
    # searching (spec 3.1). ---
    if cutoff is not None:
        try:
            tagged = scope.cutoff_tag_id is not None
            cutoff = _screen_queue(cutoff, app_label="Lidarr", queue="cutoff", tally=tally)
            cutoff = filter_monitored(cutoff)
            if tagged:
                cutoff = _screen_queue(
                    cutoff, app_label="Lidarr", queue="cutoff", tally=tally,
                    nested_key="artist", tags_at=("artist", "tags"),
                )
                cutoff = filter_by_tag(cutoff, scope.cutoff_tag_id, _lidarr_tags)
                logger.debug("Lidarr: Tag filter applied -- {n} cutoff items match tag", n=len(cutoff))
            cutoff = _screen_queue(cutoff, app_label="Lidarr", queue="cutoff", tally=tally, key_fields=("id",))
        except (AttributeError, KeyError, TypeError) as exc:
            logger.warning(
                "Lidarr: Cutoff queue filter chain faulted on malformed data ({etype}) -- "
                "skipping cutoff this cycle",
                etype=type(exc).__name__,
            )
            cutoff = None
            if cutoff_active:
                tally.mark_unevaluated("cutoff", f"malformed data ({type(exc).__name__})")

    missing_eligible_count = len(missing) if missing is not None else 0
    cutoff_eligible_count = len(cutoff) if cutoff is not None else 0
    tally.record_eligible("missing", missing_eligible_count)
    tally.record_eligible("cutoff", cutoff_eligible_count)

    # --- Reallocate unused hard-max budget to a starved queue with work (R-01 amended) ---
    missing_limit, cutoff_limit = _rebalance_and_log(
        app_label="Lidarr",
        missing_limit=missing_limit,
        cutoff_limit=cutoff_limit,
        missing_configured=orig_missing,
        cutoff_configured=orig_cutoff,
        missing_eligible=missing_eligible_count,
        cutoff_eligible=cutoff_eligible_count,
        hard_max=hard_max,
    )

    # --- Missing queue: dispatch (guarded -- a None queue is never dispatched,
    # and its searched-log is left exactly as it was, R-07) ---
    if missing is not None:
        batch, new_log, pass_done = prioritize_batch(
            missing, ist.get("missing_searched", []), missing_limit,
            key_fn=lambda a: str(a["id"]),
        )
        for album in batch:
            await _search_and_record(
                command=lambda aid=album["id"]: client.search_albums([aid]),
                tally=tally,
                db=db,
                app_label="Lidarr",
                queue="missing",
                item_name=album.get("title", "unknown"),
                instance_name=instance_name,
                max_rows=settings.general.max_history_rows,
                item_id=album.get("id"),
                instance_stable_id=instance_config.id,
            )
        ist["missing_searched"] = [] if pass_done else new_log
        if pass_done:
            ist["missing_pass"] = ist.get("missing_pass", 0) + 1
            logger.info(
                "Lidarr: Missing pass {p} complete ({n} searched)",
                p=ist["missing_pass"],
                n=len(new_log),
            )

    # --- Cutoff queue: dispatch ---
    if cutoff is not None:
        batch, new_log, pass_done = prioritize_batch(
            cutoff, ist.get("cutoff_searched", []), cutoff_limit,
            key_fn=lambda a: str(a["id"]),
        )
        for album in batch:
            await _search_and_record(
                command=lambda aid=album["id"]: client.search_albums([aid]),
                tally=tally,
                db=db,
                app_label="Lidarr",
                queue="cutoff",
                item_name=album.get("title", "unknown"),
                instance_name=instance_name,
                max_rows=settings.general.max_history_rows,
                item_id=album.get("id"),
                instance_stable_id=instance_config.id,
            )
        ist["cutoff_searched"] = [] if pass_done else new_log
        if pass_done:
            ist["cutoff_pass"] = ist.get("cutoff_pass", 0) + 1
            logger.info(
                "Lidarr: Cutoff pass {p} complete ({n} searched)",
                p=ist["cutoff_pass"],
                n=len(new_log),
            )

    # --- Grade the cycle and stamp timestamps (R-04/R-05/OUTCOME-01/02) ---
    _finalize_cycle(ist, tally, instance_config)

    # --- Diagnostic summary ---
    elapsed = time.monotonic() - cycle_start
    logger.info(
        "Lidarr: Cycle completed in {elapsed:.1f}s -- {fetched} fetched, {accepted} accepted, "
        "{failed} failed, {unsaved} history not saved -- grade {grade}",
        elapsed=elapsed,
        fetched=(ist.get("missing_count") or 0) + (ist.get("cutoff_count") or 0),
        accepted=tally.accepted,
        failed=tally.failed,
        unsaved=tally.persistence_failed,
        grade=ist["last_cycle"]["grade"],
    )

    return state


# ---------------------------------------------------------------------------
# Count-only helpers (Plan 02 count endpoint — NOT called by run_*_cycle)
# ---------------------------------------------------------------------------


async def refresh_radarr_counts(
    client: RadarrClient,
    state: TriggarrState,
    instance_name: str,
    instance_config: InstanceConfig,
    settings: Settings,
    *,
    get_tags_fn: Callable[[], Awaitable[list[Tag]]] | None = None,
) -> tuple[list[dict], list[dict], int | None] | None:
    """Fetch Radarr counts and cache them in state without advancing the search cursor.

    Performs the full fetch -> raw-count -> health -> tag -> filter -> eligible-count
    work for Radarr and caches ALL count fields in ist = state["radarr"][instance_name]
    in place.  Does NOT read or write missing_searched/cutoff_searched,
    does NOT write last_run/last_success.

    FAILURE CONTRACT (extends D-04):
      (a) FETCH failure: sets connected=False + unreachable_since, returns None.
      (b) DATA failure: filter/tag phase raises (AttributeError, KeyError, TypeError)
          on a malformed nested record -- clears the scoped count fields of queues
          whose tag scope resolved; an unresolved or undetermined tag-scoped queue
          keeps its last good counts and stamp (Phase 79 D-05), returns None.
      (c) TAG UNRESOLVED (Phase 79 D-05/OQ1): that queue's scoped counts are left
          at their previous values, never widened, and its tuple slot is [].

    Args:
        client: Connected Radarr API client.
        state: Mutable application state (modified in place).
        instance_name: Name of this Radarr instance.
        instance_config: Configuration for this specific instance.
        settings: Application settings.
        get_tags_fn: Optional cache-aware tag resolver (RES-03 parity).

    Returns:
        3-tuple (filtered_missing, raw_cutoff, cutoff_tag_id) on success, or
        None on fetch failure or malformed-data fault.
    """
    if instance_name not in state.get("radarr", {}):
        logger.warning("Radarr: instance {name} not in state -- skipping count refresh", name=instance_name)
        return None
    ist = state["radarr"][instance_name]

    # --- FETCH PHASE ---
    try:
        missing = await client.get_wanted_missing()
        cutoff = await client.get_wanted_cutoff()
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning("Radarr: Count refresh aborted -- {exc}", exc=_sanitize_exc(exc))
        _mark_unreachable(ist)
        ist["tag_warnings"] = []
        return None

    # Library count is cosmetic -- never abort on failure.
    try:
        total_items = await client.get_library_count()
    except (httpx.HTTPError, pydantic.ValidationError, ValueError):
        total_items = ist.get("total_items")

    # Health + raw counts (always committed after a successful fetch)
    ist["connected"] = True
    ist["unreachable_since"] = None
    ist["missing_count"] = len(missing)
    ist["cutoff_count"] = len(cutoff)
    ist["total_items"] = total_items

    # --- FILTER/TAG PHASE (narrow catch: malformed nested record -> disconnected + None) ---
    scope: _TagScope | None = None
    try:
        scope = await _resolve_tag_scope(
            instance_config=instance_config,
            fetch_tags=get_tags_fn if get_tags_fn is not None else client.get_tags,
            ist=ist,
            app_label="Radarr",
            tally=None,
        )

        # Missing filter chain (compute into locals first, then commit after the
        # cutoff chain -- no-partial-state guarantee). A tag-unresolved queue
        # never widens past its last-good counts (TAGSCOPE-01/D-05).
        filtered_missing: list[dict] = []
        missing_monitored_count: int | None = None
        missing_eligible_count: int | None = None
        if not scope.missing_unresolved:
            filtered_missing = filter_monitored(missing)
            missing_monitored_count = len(filtered_missing)
            if scope.missing_tag_id is not None:
                filtered_missing = filter_by_tag(filtered_missing, scope.missing_tag_id, _radarr_tags)
            if settings.general.skip_unreleased:
                filtered_missing = filter_unreleased_movies(filtered_missing)
            missing_eligible_count = len(filtered_missing)

        # Cutoff filter chain on a local copy (Radarr has no cutoff_searchable ist write)
        filtered_cutoff: list[dict] = []
        if not scope.cutoff_unresolved:
            filtered_cutoff = filter_monitored(cutoff)
            if scope.cutoff_tag_id is not None:
                filtered_cutoff = filter_by_tag(filtered_cutoff, scope.cutoff_tag_id, _radarr_tags)

        # Commit eligible counts to ist only after successful filtering (no-partial-state
        # guarantee); a tag-unresolved missing queue's fields are never committed.
        if not scope.missing_unresolved:
            ist["missing_monitored"] = missing_monitored_count
            ist["missing_eligible"] = missing_eligible_count
            _stamp_scoped_counts(ist, "missing", instance_config.missing_tag or None)

    except (AttributeError, KeyError, TypeError) as exc:
        # Malformed nested record (non-dict series/artist, non-iterable tags, etc.)
        # Treat as upstream-DATA failure: same disconnected outcome as a fetch failure.
        logger.warning(
            "Radarr: Count refresh data fault ({etype}) -- treating as disconnected",
            etype=type(exc).__name__,
        )
        _mark_unreachable(ist)
        _clear_faulted_scoped_counts(ist, scope, instance_config,
            missing_fields=("missing_monitored", "missing_eligible"),
            cutoff_fields=(),
        )
        return None

    return (filtered_missing, cutoff if not scope.cutoff_unresolved else [], scope.cutoff_tag_id)


async def refresh_sonarr_counts(
    client: SonarrClient,
    state: TriggarrState,
    instance_name: str,
    instance_config: InstanceConfig,
    settings: Settings,
    *,
    get_tags_fn: Callable[[], Awaitable[list[Tag]]] | None = None,
) -> tuple[list[dict], list[dict], int | None] | None:
    """Fetch Sonarr counts and cache them in state without advancing the search cursor.

    Performs the full fetch -> raw-count -> health -> tag -> filter -> eligible-count
    work for Sonarr and caches ALL count fields in ist = state["sonarr"][instance_name]
    in place, including missing_eligible, missing_searchable, and cutoff_searchable.
    Does NOT read or write missing_searched/cutoff_searched,
    does NOT write last_run/last_success.

    FAILURE CONTRACT (extends D-04):
      (a) FETCH failure: sets connected=False + unreachable_since, returns None.
      (b) DATA failure: filter/dedup/tag phase raises (AttributeError, KeyError, TypeError)
          on a malformed nested record -- clears the scoped count fields of queues
          whose tag scope resolved; an unresolved or undetermined tag-scoped queue
          keeps its last good counts and stamp (Phase 79 D-05), returns None.
      (c) TAG UNRESOLVED (Phase 79 D-05/OQ1): that queue's scoped counts are left
          at their previous values, never widened, and its tuple slot is [].

    Args:
        client: Connected Sonarr API client.
        state: Mutable application state (modified in place).
        instance_name: Name of this Sonarr instance.
        instance_config: Configuration for this specific instance.
        settings: Application settings.
        get_tags_fn: Optional cache-aware tag resolver (RES-03 parity).

    Returns:
        3-tuple (filtered_missing_seasons, raw_cutoff_episodes, cutoff_tag_id) on success, or
        None on fetch failure or malformed-data fault.
    """
    if instance_name not in state.get("sonarr", {}):
        logger.warning("Sonarr: instance {name} not in state -- skipping count refresh", name=instance_name)
        return None
    ist = state["sonarr"][instance_name]

    # --- FETCH PHASE ---
    try:
        missing_episodes = await client.get_wanted_missing()
        cutoff_episodes = await client.get_wanted_cutoff()
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning("Sonarr: Count refresh aborted -- {exc}", exc=_sanitize_exc(exc))
        _mark_unreachable(ist)
        ist["tag_warnings"] = []
        return None

    # Library count is cosmetic -- never abort on failure.
    try:
        total_items = await client.get_library_count()
    except (httpx.HTTPError, pydantic.ValidationError, ValueError):
        total_items = ist.get("total_items")

    # Health + raw counts (always committed after a successful fetch)
    ist["connected"] = True
    ist["unreachable_since"] = None
    ist["missing_count"] = len(missing_episodes)
    ist["cutoff_count"] = len(cutoff_episodes)
    ist["total_items"] = total_items

    # --- FILTER/DEDUP/TAG PHASE (narrow catch: malformed nested record -> disconnected + None) ---
    scope: _TagScope | None = None
    try:
        scope = await _resolve_tag_scope(
            instance_config=instance_config,
            fetch_tags=get_tags_fn if get_tags_fn is not None else client.get_tags,
            ist=ist,
            app_label="Sonarr",
            tally=None,
        )

        # Missing filter/dedup chain (compute into locals; a tag-unresolved queue
        # never widens past its last-good counts, TAGSCOPE-01/D-05).
        missing_seasons: list[dict] = []
        missing_eligible_count: int | None = None
        missing_searchable_count: int | None = None
        if not scope.missing_unresolved:
            filtered_missing = filter_sonarr_episodes(missing_episodes)
            if scope.missing_tag_id is not None:
                filtered_missing = filter_by_tag(filtered_missing, scope.missing_tag_id, _sonarr_tags)
            missing_seasons = deduplicate_to_seasons(filtered_missing)
            missing_eligible_count = len(filtered_missing)
            missing_searchable_count = len(missing_seasons)

        # Cutoff filter/dedup chain on a local copy
        cutoff_seasons: list[dict] = []
        cutoff_searchable_count: int | None = None
        if not scope.cutoff_unresolved:
            filtered_cutoff = filter_sonarr_episodes(cutoff_episodes)
            if scope.cutoff_tag_id is not None:
                filtered_cutoff = filter_by_tag(filtered_cutoff, scope.cutoff_tag_id, _sonarr_tags)
            cutoff_seasons = deduplicate_to_seasons(filtered_cutoff)
            cutoff_searchable_count = len(cutoff_seasons)

        # Commit each queue's fields together, only after both chains succeed; a
        # tag-unresolved queue's fields are never committed.
        if not scope.missing_unresolved:
            ist["missing_eligible"] = missing_eligible_count
            ist["missing_searchable"] = missing_searchable_count
            _stamp_scoped_counts(ist, "missing", instance_config.missing_tag or None)
        if not scope.cutoff_unresolved:
            ist["cutoff_searchable"] = cutoff_searchable_count
            _stamp_scoped_counts(ist, "cutoff", instance_config.cutoff_tag or None)

    except (AttributeError, KeyError, TypeError) as exc:
        # Malformed nested record (non-dict series, non-iterable tags, etc.)
        # Treat as upstream-DATA failure: same disconnected outcome as a fetch failure.
        logger.warning(
            "Sonarr: Count refresh data fault ({etype}) -- treating as disconnected",
            etype=type(exc).__name__,
        )
        _mark_unreachable(ist)
        _clear_faulted_scoped_counts(ist, scope, instance_config,
            missing_fields=("missing_eligible", "missing_searchable"),
            cutoff_fields=("cutoff_searchable",),
        )
        return None

    return (missing_seasons, cutoff_episodes if not scope.cutoff_unresolved else [], scope.cutoff_tag_id)


async def refresh_lidarr_counts(
    client: LidarrClient,
    state: TriggarrState,
    instance_name: str,
    instance_config: InstanceConfig,
    settings: Settings,
    *,
    get_tags_fn: Callable[[], Awaitable[list[Tag]]] | None = None,
) -> tuple[list[dict], list[dict], int | None] | None:
    """Fetch Lidarr counts and cache them in state without advancing the search cursor.

    Performs the full fetch -> raw-count -> health -> tag -> filter -> eligible-count
    work for Lidarr and caches ALL count fields in ist = state["lidarr"][instance_name]
    in place.  Does NOT read or write missing_searched/cutoff_searched,
    does NOT write last_run/last_success.  Lidarr has no cutoff_searchable field.

    FAILURE CONTRACT (extends D-04):
      (a) FETCH failure: sets connected=False + unreachable_since, returns None.
      (b) DATA failure: filter/tag phase raises (AttributeError, KeyError, TypeError)
          on a malformed nested record -- clears the scoped count fields of queues
          whose tag scope resolved; an unresolved or undetermined tag-scoped queue
          keeps its last good counts and stamp (Phase 79 D-05), returns None.
      (c) TAG UNRESOLVED (Phase 79 D-05/OQ1): that queue's scoped counts are left
          at their previous values, never widened, and its tuple slot is [].

    Args:
        client: Connected Lidarr API client.
        state: Mutable application state (modified in place).
        instance_name: Name of this Lidarr instance.
        instance_config: Configuration for this specific instance.
        settings: Application settings.
        get_tags_fn: Optional cache-aware tag resolver (RES-03 parity).

    Returns:
        3-tuple (filtered_missing, raw_cutoff, cutoff_tag_id) on success, or
        None on fetch failure or malformed-data fault.
    """
    if instance_name not in state.get("lidarr", {}):
        logger.warning("Lidarr: instance {name} not in state -- skipping count refresh", name=instance_name)
        return None
    ist = state["lidarr"][instance_name]

    # --- FETCH PHASE ---
    try:
        missing = await client.get_wanted_missing()
        cutoff = await client.get_wanted_cutoff()
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning("Lidarr: Count refresh aborted -- {exc}", exc=_sanitize_exc(exc))
        _mark_unreachable(ist)
        ist["tag_warnings"] = []
        return None

    # Library count is cosmetic -- never abort on failure.
    try:
        total_items = await client.get_library_count()
    except (httpx.HTTPError, pydantic.ValidationError, ValueError):
        total_items = ist.get("total_items")

    # Health + raw counts (always committed after a successful fetch)
    ist["connected"] = True
    ist["unreachable_since"] = None
    ist["missing_count"] = len(missing)
    ist["cutoff_count"] = len(cutoff)
    ist["total_items"] = total_items

    # --- FILTER/TAG PHASE (narrow catch: malformed nested record -> disconnected + None) ---
    scope: _TagScope | None = None
    try:
        scope = await _resolve_tag_scope(
            instance_config=instance_config,
            fetch_tags=get_tags_fn if get_tags_fn is not None else client.get_tags,
            ist=ist,
            app_label="Lidarr",
            tally=None,
        )

        # Missing filter chain (compute into locals first, then commit after the
        # cutoff chain -- no-partial-state guarantee). A tag-unresolved queue
        # never widens past its last-good counts (TAGSCOPE-01/D-05).
        filtered_missing: list[dict] = []
        missing_monitored_count: int | None = None
        missing_eligible_count: int | None = None
        if not scope.missing_unresolved:
            filtered_missing = filter_monitored(missing)
            missing_monitored_count = len(filtered_missing)
            if scope.missing_tag_id is not None:
                filtered_missing = filter_by_tag(filtered_missing, scope.missing_tag_id, _lidarr_tags)
            missing_eligible_count = len(filtered_missing)

        # Cutoff filter chain on a local copy (Lidarr has no cutoff_searchable ist write)
        filtered_cutoff: list[dict] = []
        if not scope.cutoff_unresolved:
            filtered_cutoff = filter_monitored(cutoff)
            if scope.cutoff_tag_id is not None:
                filtered_cutoff = filter_by_tag(filtered_cutoff, scope.cutoff_tag_id, _lidarr_tags)

        # Commit eligible counts to ist only after successful filtering (no-partial-state
        # guarantee); a tag-unresolved missing queue's fields are never committed.
        if not scope.missing_unresolved:
            ist["missing_monitored"] = missing_monitored_count
            ist["missing_eligible"] = missing_eligible_count
            _stamp_scoped_counts(ist, "missing", instance_config.missing_tag or None)

    except (AttributeError, KeyError, TypeError) as exc:
        # Malformed nested record -> upstream-DATA failure: same disconnected outcome as fetch failure.
        logger.warning(
            "Lidarr: Count refresh data fault ({etype}) -- treating as disconnected",
            etype=type(exc).__name__,
        )
        _mark_unreachable(ist)
        _clear_faulted_scoped_counts(ist, scope, instance_config,
            missing_fields=("missing_monitored", "missing_eligible"),
            cutoff_fields=(),
        )
        return None

    return (filtered_missing, cutoff if not scope.cutoff_unresolved else [], scope.cutoff_tag_id)
