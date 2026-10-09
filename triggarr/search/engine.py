"""Core search engine: utility functions and search cycle orchestrators.

Pure functions for filtering, batching, and deduplication, plus async
cycle functions that compose them with API client calls to drive the
automated search behaviour for Radarr, Sonarr, and Lidarr.  Search
history is persisted to SQLite via the ``triggarr.db`` module.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Awaitable, Callable
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
) -> tuple[list, list[str], bool]:
    """Assemble a batch: never-searched first (fetch order), then top up
    already-searched oldest-first.

    Implements the never-searched-first dispatch algorithm (QUEUE-04/05/08/09/10):
    1. Build the set of eligible IDs from the current fetch.
    2. Prune the searched-log to currently-eligible IDs (QUEUE-10).
    3. Partition eligible items into unsearched and already-searched.
    4. Fill batch with unsearched[:batch_size]; if short, top up from the pruned
       log front (oldest-searched-first) until full or exhausted (QUEUE-05).
    5. Mark every batched item on attempt — append keys to the log; a re-searched
       item moves to the tail (most-recent) (QUEUE-08).
    6. Pass-complete check (MED-1): pass_completed = bool(batch) AND every eligible
       ID is in the new log.  The bool(batch) guard is MANDATORY — it prevents a
       zero-search pass reset when batch_size<=0 and the pruned log already covers
       a tiny eligible set (matches the old ``if new_cursor == 0 and batch`` wrap
       guard).

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

    Returns:
        Tuple of (batch, new_searched_log, pass_completed).
        ``new_searched_log`` has all departed items pruned and all batched items
        appended (marking on attempt).  ``pass_completed`` is True only when this
        call produced a non-empty batch AND every eligible ID is now in the log.
    """
    if not eligible_items:
        return [], [], False

    eligible_ids = {key_fn(it) for it in eligible_items}
    # 2. Prune log to currently-eligible IDs only (QUEUE-10)
    log = [i for i in searched_log if i in eligible_ids]
    logset = set(log)

    # 3. Partition into unsearched (fetch order) and already-searched
    unsearched = [it for it in eligible_items if key_fn(it) not in logset]
    searched = [it for it in eligible_items if key_fn(it) in logset]

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

    # 6. Pass-complete: bool(batch) is MANDATORY (MED-1)
    pass_completed = bool(batch) and eligible_ids.issubset(set(new_log))

    return batch, new_log, pass_completed



def deduplicate_to_seasons(episodes: list[dict]) -> list[dict]:
    """Deduplicate Sonarr episode records to unique (seriesId, seasonNumber) pairs.

    Order is preserved (first occurrence wins). Returns dicts with
    ``seriesId``, ``seasonNumber``, ``display_name``, and ``episode_count`` keys.

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

        # Either date in the past -> released
        if (digital is not None and digital <= now) or (physical is not None and physical <= now):
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
            fetch_missing=client.get_wanted_missing,
            fetch_cutoff=client.get_wanted_cutoff,
            missing_active=missing_active,
            cutoff_active=cutoff_active,
            app_label="Radarr",
        )
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning("Radarr: Cycle aborted -- {exc}", exc=_sanitize_exc(exc))
        ist["connected"] = False
        ist["tag_warnings"] = []
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
            )
        tally.record_fetch_failure(_sanitize_exc(exc))
        _finalize_cycle(ist, tally, instance_config)
        return state

    if missing is None and cutoff is None:
        # R-07: both queues are inactive and neither fetch could refresh its
        # count. That is real evidence the host is unreachable, but nothing
        # was configured to search this cycle -- grade nothing_needed (no
        # active queues), never Failed.
        logger.warning(
            "Radarr: both queues inactive and neither could be fetched -- "
            "marked unreachable; not graded Failed"
        )
        ist["connected"] = False
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
            )
        _finalize_cycle(ist, tally, instance_config)
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
    missing_limit = instance_config.search_missing_count
    cutoff_limit = instance_config.search_cutoff_count
    hard_max = settings.general.hard_max_per_cycle
    orig_missing, orig_cutoff = missing_limit, cutoff_limit
    missing_limit, cutoff_limit = cap_batch_sizes(missing_limit, cutoff_limit, hard_max)
    if hard_max > 0 and (missing_limit != orig_missing or cutoff_limit != orig_cutoff):
        logger.debug(
            "Radarr: Hard max {max} applied -- missing={m}, cutoff={c}",
            max=hard_max,
            m=missing_limit,
            c=cutoff_limit,
        )

    # --- Tag resolution (only when at least one tag is configured) ---
    missing_tag_id: int | None = None
    cutoff_tag_id: int | None = None
    ist["tag_warnings"] = []
    if instance_config.missing_tag or instance_config.cutoff_tag:
        tag_fetch_ok = False
        try:
            # RES-03: resolve via the cache-aware resolver when supplied
            # (scheduler/search_now), else fall back to the direct client call
            # (backward-compatible None default — keeps existing tests passing).
            tags = await get_tags_fn() if get_tags_fn is not None else await client.get_tags()
            tag_fetch_ok = True
        except (httpx.HTTPError, pydantic.ValidationError) as exc:
            logger.warning(
                "Radarr: Failed to fetch tags -- skipping tag filtering: {exc}",
                exc=_sanitize_exc(exc),
            )
            tags = []

        if instance_config.missing_tag:
            missing_tag_id = resolve_tag_id(instance_config.missing_tag, tags)
            if missing_tag_id is None and tag_fetch_ok:
                logger.warning(
                    "Radarr: Tag '{tag}' not found -- searching all missing items",
                    tag=instance_config.missing_tag,
                )
                ist["tag_warnings"].append({"tag": instance_config.missing_tag, "field": "missing"})

        if instance_config.cutoff_tag:
            cutoff_tag_id = resolve_tag_id(instance_config.cutoff_tag, tags)
            if cutoff_tag_id is None and tag_fetch_ok:
                logger.warning(
                    "Radarr: Tag '{tag}' not found -- searching all cutoff items",
                    tag=instance_config.cutoff_tag,
                )
                ist["tag_warnings"].append({"tag": instance_config.cutoff_tag, "field": "cutoff"})

    # --- Missing queue: filter chain (guarded -- None means the fetch
    # didn't run or failed, R-07; the previous eligible/monitored counts
    # and searched-log stay untouched rather than being wiped to zero) ---
    if missing is not None:
        missing = filter_monitored(missing)
        ist["missing_monitored"] = len(missing)
        if missing_tag_id is not None:
            missing = filter_by_tag(missing, missing_tag_id, _radarr_tags)
            logger.debug("Radarr: Tag filter applied -- {n} missing items match tag", n=len(missing))
        if settings.general.skip_unreleased:
            missing = filter_unreleased_movies(missing)
            skipped_unreleased = ist["missing_monitored"] - len(missing)
            if skipped_unreleased > 0:
                logger.info("Radarr: {n} unreleased movies skipped", n=skipped_unreleased)
        ist["missing_eligible"] = len(missing)

    # --- Cutoff queue: filter chain (moved up so both queues' eligible
    # counts are known before rebalancing hard-max slots, R-01 amended).
    # Guarded against malformed nested records (e.g. non-iterable tags):
    # a cutoff-side data fault must never block the missing queue's
    # dispatch below -- this is the pre-existing per-app guarantee this
    # reordering must not regress. Phase 80 owns richer per-item
    # malformed-record counting; this is just the crash guard. On a fault
    # the queue is left unprocessed (None): never dispatched, its
    # searched-log untouched, and -- when active -- marked unevaluated so
    # the cycle can never grade Nothing needed searching (spec 3.1). ---
    if cutoff is not None:
        try:
            cutoff = filter_monitored(cutoff)
            if cutoff_tag_id is not None:
                cutoff = filter_by_tag(cutoff, cutoff_tag_id, _radarr_tags)
                logger.debug("Radarr: Tag filter applied -- {n} cutoff items match tag", n=len(cutoff))
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
    capped_missing_limit, capped_cutoff_limit = missing_limit, cutoff_limit
    missing_limit, cutoff_limit = rebalance_batch_sizes(
        missing_limit=missing_limit,
        cutoff_limit=cutoff_limit,
        missing_configured=orig_missing,
        cutoff_configured=orig_cutoff,
        missing_eligible=missing_eligible_count,
        cutoff_eligible=cutoff_eligible_count,
        hard_max=hard_max,
    )
    if hard_max > 0 and (missing_limit, cutoff_limit) != (capped_missing_limit, capped_cutoff_limit):
        logger.debug(
            "Radarr: Hard max {max} rebalanced to queues with work -- missing={m}, cutoff={c}",
            max=hard_max,
            m=missing_limit,
            c=cutoff_limit,
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
            fetch_missing=client.get_wanted_missing,
            fetch_cutoff=client.get_wanted_cutoff,
            missing_active=missing_active,
            cutoff_active=cutoff_active,
            app_label="Sonarr",
        )
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning("Sonarr: Cycle aborted -- {exc}", exc=_sanitize_exc(exc))
        ist["connected"] = False
        ist["tag_warnings"] = []
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
            )
        tally.record_fetch_failure(_sanitize_exc(exc))
        _finalize_cycle(ist, tally, instance_config)
        return state

    if missing_episodes is None and cutoff_episodes is None:
        # R-07: both queues are inactive and neither fetch could refresh its
        # count. That is real evidence the host is unreachable, but nothing
        # was configured to search this cycle -- grade nothing_needed (no
        # active queues), never Failed.
        logger.warning(
            "Sonarr: both queues inactive and neither could be fetched -- "
            "marked unreachable; not graded Failed"
        )
        ist["connected"] = False
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
            )
        _finalize_cycle(ist, tally, instance_config)
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
    missing_limit = instance_config.search_missing_count
    cutoff_limit = instance_config.search_cutoff_count
    hard_max = settings.general.hard_max_per_cycle
    orig_missing, orig_cutoff = missing_limit, cutoff_limit
    missing_limit, cutoff_limit = cap_batch_sizes(missing_limit, cutoff_limit, hard_max)
    if hard_max > 0 and (missing_limit != orig_missing or cutoff_limit != orig_cutoff):
        logger.debug(
            "Sonarr: Hard max {max} applied -- missing={m}, cutoff={c}",
            max=hard_max,
            m=missing_limit,
            c=cutoff_limit,
        )

    # --- Tag resolution (only when at least one tag is configured) ---
    missing_tag_id: int | None = None
    cutoff_tag_id: int | None = None
    ist["tag_warnings"] = []
    if instance_config.missing_tag or instance_config.cutoff_tag:
        tag_fetch_ok = False
        try:
            # RES-03: resolve via the cache-aware resolver when supplied
            # (scheduler/search_now), else fall back to the direct client call
            # (backward-compatible None default — keeps existing tests passing).
            tags = await get_tags_fn() if get_tags_fn is not None else await client.get_tags()
            tag_fetch_ok = True
        except (httpx.HTTPError, pydantic.ValidationError) as exc:
            logger.warning(
                "Sonarr: Failed to fetch tags -- skipping tag filtering: {exc}",
                exc=_sanitize_exc(exc),
            )
            tags = []

        if instance_config.missing_tag:
            missing_tag_id = resolve_tag_id(instance_config.missing_tag, tags)
            if missing_tag_id is None and tag_fetch_ok:
                logger.warning(
                    "Sonarr: Tag '{tag}' not found -- searching all missing items",
                    tag=instance_config.missing_tag,
                )
                ist["tag_warnings"].append({"tag": instance_config.missing_tag, "field": "missing"})

        if instance_config.cutoff_tag:
            cutoff_tag_id = resolve_tag_id(instance_config.cutoff_tag, tags)
            if cutoff_tag_id is None and tag_fetch_ok:
                logger.warning(
                    "Sonarr: Tag '{tag}' not found -- searching all cutoff items",
                    tag=instance_config.cutoff_tag,
                )
                ist["tag_warnings"].append({"tag": instance_config.cutoff_tag, "field": "cutoff"})

    # --- Missing queue: filter chain (guarded -- None means the fetch
    # didn't run or failed, R-07; the previous eligible/searchable counts
    # and searched-log stay untouched rather than being wiped to zero) ---
    missing_seasons: list[dict] = []
    if missing_episodes is not None:
        missing_episodes = filter_sonarr_episodes(missing_episodes)
        if missing_tag_id is not None:
            missing_episodes = filter_by_tag(missing_episodes, missing_tag_id, _sonarr_tags)
            logger.debug("Sonarr: Tag filter applied -- {n} missing episodes match tag", n=len(missing_episodes))
        missing_seasons = deduplicate_to_seasons(missing_episodes)
        ist["missing_eligible"] = len(missing_episodes)
        ist["missing_searchable"] = len(missing_seasons)

    # --- Cutoff queue: filter chain (moved up so both queues' eligible
    # counts are known before rebalancing hard-max slots, R-01 amended).
    # Guarded against malformed nested records (e.g. a non-dict "series"):
    # a cutoff-side data fault must never block the missing queue's
    # dispatch below -- this is the pre-existing per-app guarantee this
    # reordering must not regress. Phase 80 owns richer per-item
    # malformed-record counting; this is just the crash guard. On a fault
    # the queue is left unprocessed (None): never dispatched, its
    # searched-log and searchable count untouched, and -- when active --
    # marked unevaluated so the cycle can never grade Nothing needed
    # searching (spec 3.1). ---
    cutoff_seasons: list[dict] = []
    if cutoff_episodes is not None:
        try:
            cutoff_episodes = filter_sonarr_episodes(cutoff_episodes)
            if cutoff_tag_id is not None:
                cutoff_episodes = filter_by_tag(cutoff_episodes, cutoff_tag_id, _sonarr_tags)
                logger.debug("Sonarr: Tag filter applied -- {n} cutoff episodes match tag", n=len(cutoff_episodes))
            cutoff_seasons = deduplicate_to_seasons(cutoff_episodes)
            ist["cutoff_searchable"] = len(cutoff_seasons)
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
    capped_missing_limit, capped_cutoff_limit = missing_limit, cutoff_limit
    missing_limit, cutoff_limit = rebalance_batch_sizes(
        missing_limit=missing_limit,
        cutoff_limit=cutoff_limit,
        missing_configured=orig_missing,
        cutoff_configured=orig_cutoff,
        missing_eligible=len(missing_seasons),
        cutoff_eligible=len(cutoff_seasons),
        hard_max=hard_max,
    )
    if hard_max > 0 and (missing_limit, cutoff_limit) != (capped_missing_limit, capped_cutoff_limit):
        logger.debug(
            "Sonarr: Hard max {max} rebalanced to queues with work -- missing={m}, cutoff={c}",
            max=hard_max,
            m=missing_limit,
            c=cutoff_limit,
        )

    # --- Missing queue: dispatch (guarded -- a None queue is never dispatched,
    # and its searched-log is left exactly as it was, R-07) ---
    if missing_episodes is not None:
        batch, new_log, pass_done = prioritize_batch(
            missing_seasons, ist.get("missing_searched", []), missing_limit,
            key_fn=lambda s: f'{s["seriesId"]}:{s["seasonNumber"]}',
        )
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
        batch, new_log, pass_done = prioritize_batch(
            cutoff_seasons, ist.get("cutoff_searched", []), cutoff_limit,
            key_fn=lambda s: f'{s["seriesId"]}:{s["seasonNumber"]}',
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
            fetch_missing=client.get_wanted_missing,
            fetch_cutoff=client.get_wanted_cutoff,
            missing_active=missing_active,
            cutoff_active=cutoff_active,
            app_label="Lidarr",
        )
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning("Lidarr: Cycle aborted -- {exc}", exc=_sanitize_exc(exc))
        ist["connected"] = False
        ist["tag_warnings"] = []
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
            )
        tally.record_fetch_failure(_sanitize_exc(exc))
        _finalize_cycle(ist, tally, instance_config)
        return state

    if missing is None and cutoff is None:
        # R-07: both queues are inactive and neither fetch could refresh its
        # count. That is real evidence the host is unreachable, but nothing
        # was configured to search this cycle -- grade nothing_needed (no
        # active queues), never Failed.
        logger.warning(
            "Lidarr: both queues inactive and neither could be fetched -- "
            "marked unreachable; not graded Failed"
        )
        ist["connected"] = False
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
            )
        _finalize_cycle(ist, tally, instance_config)
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
    missing_limit = instance_config.search_missing_count
    cutoff_limit = instance_config.search_cutoff_count
    hard_max = settings.general.hard_max_per_cycle
    orig_missing, orig_cutoff = missing_limit, cutoff_limit
    missing_limit, cutoff_limit = cap_batch_sizes(missing_limit, cutoff_limit, hard_max)
    if hard_max > 0 and (missing_limit != orig_missing or cutoff_limit != orig_cutoff):
        logger.debug(
            "Lidarr: Hard max {max} applied -- missing={m}, cutoff={c}",
            max=hard_max,
            m=missing_limit,
            c=cutoff_limit,
        )

    # --- Tag resolution (only when at least one tag is configured) ---
    missing_tag_id: int | None = None
    cutoff_tag_id: int | None = None
    ist["tag_warnings"] = []
    if instance_config.missing_tag or instance_config.cutoff_tag:
        tag_fetch_ok = False
        try:
            # RES-03: resolve via the cache-aware resolver when supplied
            # (scheduler/search_now), else fall back to the direct client call
            # (backward-compatible None default — keeps existing tests passing).
            tags = await get_tags_fn() if get_tags_fn is not None else await client.get_tags()
            tag_fetch_ok = True
        except (httpx.HTTPError, pydantic.ValidationError) as exc:
            logger.warning(
                "Lidarr: Failed to fetch tags -- skipping tag filtering: {exc}",
                exc=_sanitize_exc(exc),
            )
            tags = []

        if instance_config.missing_tag:
            missing_tag_id = resolve_tag_id(instance_config.missing_tag, tags)
            if missing_tag_id is None and tag_fetch_ok:
                logger.warning(
                    "Lidarr: Tag '{tag}' not found -- searching all missing items",
                    tag=instance_config.missing_tag,
                )
                ist["tag_warnings"].append({"tag": instance_config.missing_tag, "field": "missing"})

        if instance_config.cutoff_tag:
            cutoff_tag_id = resolve_tag_id(instance_config.cutoff_tag, tags)
            if cutoff_tag_id is None and tag_fetch_ok:
                logger.warning(
                    "Lidarr: Tag '{tag}' not found -- searching all cutoff items",
                    tag=instance_config.cutoff_tag,
                )
                ist["tag_warnings"].append({"tag": instance_config.cutoff_tag, "field": "cutoff"})

    # --- Missing queue: filter chain (guarded -- None means the fetch
    # didn't run or failed, R-07; the previous eligible/monitored counts
    # and searched-log stay untouched rather than being wiped to zero) ---
    if missing is not None:
        missing = filter_monitored(missing)
        ist["missing_monitored"] = len(missing)
        if missing_tag_id is not None:
            missing = filter_by_tag(missing, missing_tag_id, _lidarr_tags)
            logger.debug("Lidarr: Tag filter applied -- {n} missing items match tag", n=len(missing))
        ist["missing_eligible"] = len(missing)

    # --- Cutoff queue: filter chain (moved up so both queues' eligible
    # counts are known before rebalancing hard-max slots, R-01 amended).
    # Guarded against malformed nested records (e.g. non-iterable tags):
    # a cutoff-side data fault must never block the missing queue's
    # dispatch below -- this is the pre-existing per-app guarantee this
    # reordering must not regress. Phase 80 owns richer per-item
    # malformed-record counting; this is just the crash guard. On a fault
    # the queue is left unprocessed (None): never dispatched, its
    # searched-log untouched, and -- when active -- marked unevaluated so
    # the cycle can never grade Nothing needed searching (spec 3.1). ---
    if cutoff is not None:
        try:
            cutoff = filter_monitored(cutoff)
            if cutoff_tag_id is not None:
                cutoff = filter_by_tag(cutoff, cutoff_tag_id, _lidarr_tags)
                logger.debug("Lidarr: Tag filter applied -- {n} cutoff items match tag", n=len(cutoff))
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
    capped_missing_limit, capped_cutoff_limit = missing_limit, cutoff_limit
    missing_limit, cutoff_limit = rebalance_batch_sizes(
        missing_limit=missing_limit,
        cutoff_limit=cutoff_limit,
        missing_configured=orig_missing,
        cutoff_configured=orig_cutoff,
        missing_eligible=missing_eligible_count,
        cutoff_eligible=cutoff_eligible_count,
        hard_max=hard_max,
    )
    if hard_max > 0 and (missing_limit, cutoff_limit) != (capped_missing_limit, capped_cutoff_limit):
        logger.debug(
            "Lidarr: Hard max {max} rebalanced to queues with work -- missing={m}, cutoff={c}",
            max=hard_max,
            m=missing_limit,
            c=cutoff_limit,
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
          on a malformed nested record -> sets connected=False + unreachable_since,
          clears eligible count fields, returns None (never propagates to caller).

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
        ist["connected"] = False
        ist["tag_warnings"] = []
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
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
    missing_tag_id: int | None = None
    cutoff_tag_id: int | None = None
    try:
        ist["tag_warnings"] = []
        if instance_config.missing_tag or instance_config.cutoff_tag:
            tag_fetch_ok = False
            try:
                tags = await get_tags_fn() if get_tags_fn is not None else await client.get_tags()
                tag_fetch_ok = True
            except (httpx.HTTPError, pydantic.ValidationError) as exc:
                logger.warning(
                    "Radarr: Failed to fetch tags for count refresh -- skipping tag filtering: {exc}",
                    exc=_sanitize_exc(exc),
                )
                tags = []

            if instance_config.missing_tag:
                missing_tag_id = resolve_tag_id(instance_config.missing_tag, tags)
                if missing_tag_id is None and tag_fetch_ok:
                    logger.warning(
                        "Radarr: Tag '{tag}' not found -- counting all missing items",
                        tag=instance_config.missing_tag,
                    )
                    ist["tag_warnings"].append({"tag": instance_config.missing_tag, "field": "missing"})

            if instance_config.cutoff_tag:
                cutoff_tag_id = resolve_tag_id(instance_config.cutoff_tag, tags)
                if cutoff_tag_id is None and tag_fetch_ok:
                    logger.warning(
                        "Radarr: Tag '{tag}' not found -- counting all cutoff items",
                        tag=instance_config.cutoff_tag,
                    )
                    ist["tag_warnings"].append({"tag": instance_config.cutoff_tag, "field": "cutoff"})

        # Missing filter chain (compute into locals first, then commit to ist)
        filtered_missing = filter_monitored(missing)
        missing_monitored_count = len(filtered_missing)
        if missing_tag_id is not None:
            filtered_missing = filter_by_tag(filtered_missing, missing_tag_id, _radarr_tags)
        if settings.general.skip_unreleased:
            filtered_missing = filter_unreleased_movies(filtered_missing)
        missing_eligible_count = len(filtered_missing)

        # Cutoff filter chain on a local copy (Radarr has no cutoff_searchable ist write)
        filtered_cutoff = filter_monitored(cutoff)
        if cutoff_tag_id is not None:
            filtered_cutoff = filter_by_tag(filtered_cutoff, cutoff_tag_id, _radarr_tags)

        # Commit eligible counts to ist only after successful filtering (no-partial-state guarantee)
        ist["missing_monitored"] = missing_monitored_count
        ist["missing_eligible"] = missing_eligible_count

    except (AttributeError, KeyError, TypeError) as exc:
        # Malformed nested record (non-dict series/artist, non-iterable tags, etc.)
        # Treat as upstream-DATA failure: same disconnected outcome as a fetch failure.
        logger.warning(
            "Radarr: Count refresh data fault ({etype}) -- treating as disconnected",
            etype=type(exc).__name__,
        )
        ist["connected"] = False
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        # Clear eligible counts so no half-updated set is left behind
        ist["missing_monitored"] = None
        ist["missing_eligible"] = None
        return None

    return (filtered_missing, cutoff, cutoff_tag_id)


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
          on a malformed nested record -> sets connected=False + unreachable_since,
          clears eligible/searchable count fields, returns None (never propagates to caller).

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
        ist["connected"] = False
        ist["tag_warnings"] = []
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
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
    missing_tag_id: int | None = None
    cutoff_tag_id: int | None = None
    try:
        ist["tag_warnings"] = []
        if instance_config.missing_tag or instance_config.cutoff_tag:
            tag_fetch_ok = False
            try:
                tags = await get_tags_fn() if get_tags_fn is not None else await client.get_tags()
                tag_fetch_ok = True
            except (httpx.HTTPError, pydantic.ValidationError) as exc:
                logger.warning(
                    "Sonarr: Failed to fetch tags for count refresh -- skipping tag filtering: {exc}",
                    exc=_sanitize_exc(exc),
                )
                tags = []

            if instance_config.missing_tag:
                missing_tag_id = resolve_tag_id(instance_config.missing_tag, tags)
                if missing_tag_id is None and tag_fetch_ok:
                    logger.warning(
                        "Sonarr: Tag '{tag}' not found -- counting all missing items",
                        tag=instance_config.missing_tag,
                    )
                    ist["tag_warnings"].append({"tag": instance_config.missing_tag, "field": "missing"})

            if instance_config.cutoff_tag:
                cutoff_tag_id = resolve_tag_id(instance_config.cutoff_tag, tags)
                if cutoff_tag_id is None and tag_fetch_ok:
                    logger.warning(
                        "Sonarr: Tag '{tag}' not found -- counting all cutoff items",
                        tag=instance_config.cutoff_tag,
                    )
                    ist["tag_warnings"].append({"tag": instance_config.cutoff_tag, "field": "cutoff"})

        # Missing filter/dedup chain (compute into locals first, then commit to ist)
        filtered_missing = filter_sonarr_episodes(missing_episodes)
        if missing_tag_id is not None:
            filtered_missing = filter_by_tag(filtered_missing, missing_tag_id, _sonarr_tags)
        missing_seasons = deduplicate_to_seasons(filtered_missing)
        missing_eligible_count = len(filtered_missing)
        missing_searchable_count = len(missing_seasons)

        # Cutoff filter/dedup chain on a local copy
        filtered_cutoff = filter_sonarr_episodes(cutoff_episodes)
        if cutoff_tag_id is not None:
            filtered_cutoff = filter_by_tag(filtered_cutoff, cutoff_tag_id, _sonarr_tags)
        cutoff_seasons = deduplicate_to_seasons(filtered_cutoff)
        cutoff_searchable_count = len(cutoff_seasons)

        # Commit eligible/searchable counts to ist only after successful filtering
        # (no-partial-state guarantee: either all three are committed or none are)
        ist["missing_eligible"] = missing_eligible_count
        ist["missing_searchable"] = missing_searchable_count
        ist["cutoff_searchable"] = cutoff_searchable_count

    except (AttributeError, KeyError, TypeError) as exc:
        # Malformed nested record (non-dict series, non-iterable tags, etc.)
        # Treat as upstream-DATA failure: same disconnected outcome as a fetch failure.
        logger.warning(
            "Sonarr: Count refresh data fault ({etype}) -- treating as disconnected",
            etype=type(exc).__name__,
        )
        ist["connected"] = False
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        # Clear eligible/searchable counts so no half-updated set is left behind
        ist["missing_eligible"] = None
        ist["missing_searchable"] = None
        ist["cutoff_searchable"] = None
        return None

    return (missing_seasons, cutoff_episodes, cutoff_tag_id)


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
          on a malformed nested record -> sets connected=False + unreachable_since,
          clears eligible count fields, returns None (never propagates to caller).

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
        ist["connected"] = False
        ist["tag_warnings"] = []
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
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
    missing_tag_id: int | None = None
    cutoff_tag_id: int | None = None
    try:
        ist["tag_warnings"] = []
        if instance_config.missing_tag or instance_config.cutoff_tag:
            tag_fetch_ok = False
            try:
                tags = await get_tags_fn() if get_tags_fn is not None else await client.get_tags()
                tag_fetch_ok = True
            except (httpx.HTTPError, pydantic.ValidationError) as exc:
                logger.warning(
                    "Lidarr: Failed to fetch tags for count refresh -- skipping tag filtering: {exc}",
                    exc=_sanitize_exc(exc),
                )
                tags = []

            if instance_config.missing_tag:
                missing_tag_id = resolve_tag_id(instance_config.missing_tag, tags)
                if missing_tag_id is None and tag_fetch_ok:
                    logger.warning(
                        "Lidarr: Tag '{tag}' not found -- counting all missing items",
                        tag=instance_config.missing_tag,
                    )
                    ist["tag_warnings"].append({"tag": instance_config.missing_tag, "field": "missing"})

            if instance_config.cutoff_tag:
                cutoff_tag_id = resolve_tag_id(instance_config.cutoff_tag, tags)
                if cutoff_tag_id is None and tag_fetch_ok:
                    logger.warning(
                        "Lidarr: Tag '{tag}' not found -- counting all cutoff items",
                        tag=instance_config.cutoff_tag,
                    )
                    ist["tag_warnings"].append({"tag": instance_config.cutoff_tag, "field": "cutoff"})

        # Missing filter chain (compute into locals first, then commit to ist)
        filtered_missing = filter_monitored(missing)
        missing_monitored_count = len(filtered_missing)
        if missing_tag_id is not None:
            filtered_missing = filter_by_tag(filtered_missing, missing_tag_id, _lidarr_tags)
        missing_eligible_count = len(filtered_missing)

        # Cutoff filter chain on a local copy (Lidarr has no cutoff_searchable ist write)
        filtered_cutoff = filter_monitored(cutoff)
        if cutoff_tag_id is not None:
            filtered_cutoff = filter_by_tag(filtered_cutoff, cutoff_tag_id, _lidarr_tags)

        # Commit eligible counts to ist only after successful filtering (no-partial-state guarantee)
        ist["missing_monitored"] = missing_monitored_count
        ist["missing_eligible"] = missing_eligible_count

    except (AttributeError, KeyError, TypeError) as exc:
        # Malformed nested record -> upstream-DATA failure: same disconnected outcome as fetch failure.
        logger.warning(
            "Lidarr: Count refresh data fault ({etype}) -- treating as disconnected",
            etype=type(exc).__name__,
        )
        ist["connected"] = False
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        # Clear eligible counts so no half-updated set is left behind
        ist["missing_monitored"] = None
        ist["missing_eligible"] = None
        return None

    return (filtered_missing, cutoff, cutoff_tag_id)
