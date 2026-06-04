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

from triggarr.clients.lidarr import LidarrClient
from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.db import PendingCapExceeded, insert_search_entry
from triggarr.models.arr import Tag
from triggarr.models.config import InstanceConfig, Settings
from triggarr.state import TriggarrState


def _sanitize_exc(exc: Exception) -> str:
    """Return a safe, type-based summary of an exception for storage.

    Avoids storing raw str(exc) which may contain internal paths, URLs,
    or API keys that bypass the loguru redacting sink.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.TimeoutException):
        return "request timeout"
    if isinstance(exc, httpx.HTTPError):
        return f"HTTP error: {type(exc).__name__}"
    if isinstance(exc, pydantic.ValidationError):
        return f"validation error ({exc.error_count()} issues)"
    return type(exc).__name__


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

    try:
        missing = await client.get_wanted_missing()
        cutoff = await client.get_wanted_cutoff()
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning("Radarr: Cycle aborted -- {exc}", exc=_sanitize_exc(exc))
        ist["connected"] = False
        ist["tag_warnings"] = []
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
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

    # Cache raw item counts before filtering (WEBU-04)
    ist["missing_count"] = len(missing)
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

    searched_count = 0
    skipped_count = 0

    # --- Missing queue ---
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
    batch, new_log, pass_done = prioritize_batch(
        missing, ist.get("missing_searched", []), missing_limit,
        key_fn=lambda m: str(m["id"]),
    )
    for movie in batch:
        try:
            await client.search_movies([movie["id"]])
            await insert_search_entry(
                db, "Radarr", "missing", movie["title"],
                outcome="searched", detail="search triggered",
                item_id=movie["id"],
                instance_id=instance_name,
                max_rows=settings.general.max_history_rows,
            )
            logger.info("Radarr: Searched {title} (missing)", title=movie["title"])
            searched_count += 1
        except PendingCapExceeded as cap_exc:
            logger.warning(
                "Skipping search history insert -- pending-row cap reached "
                "for {app}/{instance} {item!r}",
                app=cap_exc.app,
                instance=cap_exc.instance_id,
                item=cap_exc.item_name,
            )
            skipped_count += 1
            continue
        except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
            logger.warning(
                "Radarr: Failed to search {title}: {exc}",
                title=movie.get("title", "unknown"),
                exc=_sanitize_exc(exc),
            )
            await insert_search_entry(
                db, "Radarr", "missing", movie.get("title", "unknown"),
                outcome="failed", detail=_sanitize_exc(exc),
                item_id=movie.get("id"),
                instance_id=instance_name,
                max_rows=settings.general.max_history_rows,
            )
            skipped_count += 1
    ist["missing_searched"] = [] if pass_done else new_log
    if pass_done:
        ist["missing_pass"] = ist.get("missing_pass", 0) + 1
        logger.info(
            "Radarr: Missing pass {p} complete ({n} searched)",
            p=ist["missing_pass"],
            n=len(new_log),
        )

    # --- Cutoff queue ---
    cutoff = filter_monitored(cutoff)
    if cutoff_tag_id is not None:
        cutoff = filter_by_tag(cutoff, cutoff_tag_id, _radarr_tags)
        logger.debug("Radarr: Tag filter applied -- {n} cutoff items match tag", n=len(cutoff))
    batch, new_log, pass_done = prioritize_batch(
        cutoff, ist.get("cutoff_searched", []), cutoff_limit,
        key_fn=lambda m: str(m["id"]),
    )
    for movie in batch:
        try:
            await client.search_movies([movie["id"]])
            await insert_search_entry(
                db, "Radarr", "cutoff", movie["title"],
                outcome="searched", detail="search triggered",
                item_id=movie["id"],
                instance_id=instance_name,
                max_rows=settings.general.max_history_rows,
            )
            logger.info("Radarr: Searched {title} (cutoff)", title=movie["title"])
            searched_count += 1
        except PendingCapExceeded as cap_exc:
            logger.warning(
                "Skipping search history insert -- pending-row cap reached "
                "for {app}/{instance} {item!r}",
                app=cap_exc.app,
                instance=cap_exc.instance_id,
                item=cap_exc.item_name,
            )
            skipped_count += 1
            continue
        except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
            logger.warning(
                "Radarr: Failed to search {title}: {exc}",
                title=movie.get("title", "unknown"),
                exc=_sanitize_exc(exc),
            )
            await insert_search_entry(
                db, "Radarr", "cutoff", movie.get("title", "unknown"),
                outcome="failed", detail=_sanitize_exc(exc),
                item_id=movie.get("id"),
                instance_id=instance_name,
                max_rows=settings.general.max_history_rows,
            )
            skipped_count += 1
    ist["cutoff_searched"] = [] if pass_done else new_log
    if pass_done:
        ist["cutoff_pass"] = ist.get("cutoff_pass", 0) + 1
        logger.info(
            "Radarr: Cutoff pass {p} complete ({n} searched)",
            p=ist["cutoff_pass"],
            n=len(new_log),
        )

    # --- Diagnostic summary ---
    elapsed = time.monotonic() - cycle_start
    logger.info(
        "Radarr: Cycle completed in {elapsed:.1f}s -- {fetched} fetched, {searched} searched, {skipped} skipped",
        elapsed=elapsed,
        fetched=ist["missing_count"] + ist["cutoff_count"],
        searched=searched_count,
        skipped=skipped_count,
    )

    # --- Update last_run and last_success ---
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    ist["last_run"] = now_iso
    ist["last_success"] = now_iso
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

    try:
        missing_episodes = await client.get_wanted_missing()
        cutoff_episodes = await client.get_wanted_cutoff()
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning("Sonarr: Cycle aborted -- {exc}", exc=_sanitize_exc(exc))
        ist["connected"] = False
        ist["tag_warnings"] = []
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
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

    # Cache raw item counts before filtering (WEBU-04)
    ist["missing_count"] = len(missing_episodes)
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

    searched_count = 0
    skipped_count = 0

    # --- Missing queue ---
    missing_episodes = filter_sonarr_episodes(missing_episodes)
    if missing_tag_id is not None:
        missing_episodes = filter_by_tag(missing_episodes, missing_tag_id, _sonarr_tags)
        logger.debug("Sonarr: Tag filter applied -- {n} missing episodes match tag", n=len(missing_episodes))
    missing_seasons = deduplicate_to_seasons(missing_episodes)
    ist["missing_eligible"] = len(missing_episodes)
    ist["missing_searchable"] = len(missing_seasons)
    batch, new_log, pass_done = prioritize_batch(
        missing_seasons, ist.get("missing_searched", []), missing_limit,
        key_fn=lambda s: f'{s["seriesId"]}:{s["seasonNumber"]}',
    )
    for season in batch:
        try:
            await client.search_season(season["seriesId"], season["seasonNumber"])
            await insert_search_entry(
                db, "Sonarr", "missing", season["display_name"],
                outcome="searched", detail="search triggered",
                item_id=season["seriesId"],
                season_number=season["seasonNumber"],
                missing_count=season["episode_count"],
                instance_id=instance_name,
                max_rows=settings.general.max_history_rows,
            )
            logger.info("Sonarr: Searched {name} (missing)", name=season["display_name"])
            searched_count += 1
        except PendingCapExceeded as cap_exc:
            logger.warning(
                "Skipping search history insert -- pending-row cap reached "
                "for {app}/{instance} {item!r}",
                app=cap_exc.app,
                instance=cap_exc.instance_id,
                item=cap_exc.item_name,
            )
            skipped_count += 1
            continue
        except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
            logger.warning(
                "Sonarr: Failed to search {name}: {exc}",
                name=season.get("display_name", "unknown"),
                exc=_sanitize_exc(exc),
            )
            await insert_search_entry(
                db, "Sonarr", "missing", season.get("display_name", "unknown"),
                outcome="failed", detail=_sanitize_exc(exc),
                item_id=season.get("seriesId"),
                season_number=season.get("seasonNumber"),
                missing_count=season.get("episode_count"),
                instance_id=instance_name,
                max_rows=settings.general.max_history_rows,
            )
            skipped_count += 1
    ist["missing_searched"] = [] if pass_done else new_log
    if pass_done:
        ist["missing_pass"] = ist.get("missing_pass", 0) + 1
        logger.info(
            "Sonarr: Missing pass {p} complete ({n} searched)",
            p=ist["missing_pass"],
            n=len(new_log),
        )

    # --- Cutoff queue ---
    cutoff_episodes = filter_sonarr_episodes(cutoff_episodes)
    if cutoff_tag_id is not None:
        cutoff_episodes = filter_by_tag(cutoff_episodes, cutoff_tag_id, _sonarr_tags)
        logger.debug("Sonarr: Tag filter applied -- {n} cutoff episodes match tag", n=len(cutoff_episodes))
    cutoff_seasons = deduplicate_to_seasons(cutoff_episodes)
    ist["cutoff_searchable"] = len(cutoff_seasons)
    batch, new_log, pass_done = prioritize_batch(
        cutoff_seasons, ist.get("cutoff_searched", []), cutoff_limit,
        key_fn=lambda s: f'{s["seriesId"]}:{s["seasonNumber"]}',
    )
    for season in batch:
        try:
            await client.search_season(season["seriesId"], season["seasonNumber"])
            await insert_search_entry(
                db, "Sonarr", "cutoff", season["display_name"],
                outcome="searched", detail="search triggered",
                item_id=season["seriesId"],
                season_number=season["seasonNumber"],
                missing_count=season["episode_count"],
                instance_id=instance_name,
                max_rows=settings.general.max_history_rows,
            )
            logger.info("Sonarr: Searched {name} (cutoff)", name=season["display_name"])
            searched_count += 1
        except PendingCapExceeded as cap_exc:
            logger.warning(
                "Skipping search history insert -- pending-row cap reached "
                "for {app}/{instance} {item!r}",
                app=cap_exc.app,
                instance=cap_exc.instance_id,
                item=cap_exc.item_name,
            )
            skipped_count += 1
            continue
        except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
            logger.warning(
                "Sonarr: Failed to search {name}: {exc}",
                name=season.get("display_name", "unknown"),
                exc=_sanitize_exc(exc),
            )
            await insert_search_entry(
                db, "Sonarr", "cutoff", season.get("display_name", "unknown"),
                outcome="failed", detail=_sanitize_exc(exc),
                item_id=season.get("seriesId"),
                season_number=season.get("seasonNumber"),
                missing_count=season.get("episode_count"),
                instance_id=instance_name,
                max_rows=settings.general.max_history_rows,
            )
            skipped_count += 1
    ist["cutoff_searched"] = [] if pass_done else new_log
    if pass_done:
        ist["cutoff_pass"] = ist.get("cutoff_pass", 0) + 1
        logger.info(
            "Sonarr: Cutoff pass {p} complete ({n} searched)",
            p=ist["cutoff_pass"],
            n=len(new_log),
        )

    # --- Diagnostic summary ---
    elapsed = time.monotonic() - cycle_start
    logger.info(
        "Sonarr: Cycle completed in {elapsed:.1f}s -- {fetched} fetched, {searched} searched, {skipped} skipped",
        elapsed=elapsed,
        fetched=ist["missing_count"] + ist["cutoff_count"],
        searched=searched_count,
        skipped=skipped_count,
    )

    # --- Update last_run and last_success ---
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    ist["last_run"] = now_iso
    ist["last_success"] = now_iso
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

    try:
        missing = await client.get_wanted_missing()
        cutoff = await client.get_wanted_cutoff()
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning("Lidarr: Cycle aborted -- {exc}", exc=_sanitize_exc(exc))
        ist["connected"] = False
        ist["tag_warnings"] = []
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
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

    # Cache raw item counts before filtering
    ist["missing_count"] = len(missing)
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

    searched_count = 0
    skipped_count = 0

    # --- Missing queue ---
    missing = filter_monitored(missing)
    ist["missing_monitored"] = len(missing)
    if missing_tag_id is not None:
        missing = filter_by_tag(missing, missing_tag_id, _lidarr_tags)
        logger.debug("Lidarr: Tag filter applied -- {n} missing items match tag", n=len(missing))
    ist["missing_eligible"] = len(missing)
    batch, new_log, pass_done = prioritize_batch(
        missing, ist.get("missing_searched", []), missing_limit,
        key_fn=lambda a: str(a["id"]),
    )
    for album in batch:
        title = album.get("title", "unknown")
        try:
            await client.search_albums([album["id"]])
            await insert_search_entry(
                db, "Lidarr", "missing", title,
                outcome="searched", detail="search triggered",
                item_id=album["id"],
                instance_id=instance_name,
                max_rows=settings.general.max_history_rows,
            )
            logger.info("Lidarr: Searched {title} (missing)", title=title)
            searched_count += 1
        except PendingCapExceeded as cap_exc:
            logger.warning(
                "Skipping search history insert -- pending-row cap reached "
                "for {app}/{instance} {item!r}",
                app=cap_exc.app,
                instance=cap_exc.instance_id,
                item=cap_exc.item_name,
            )
            skipped_count += 1
            continue
        except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
            logger.warning(
                "Lidarr: Failed to search {title}: {exc}",
                title=title,
                exc=_sanitize_exc(exc),
            )
            await insert_search_entry(
                db, "Lidarr", "missing", title,
                outcome="failed", detail=_sanitize_exc(exc),
                item_id=album.get("id"),
                instance_id=instance_name,
                max_rows=settings.general.max_history_rows,
            )
            skipped_count += 1
    ist["missing_searched"] = [] if pass_done else new_log
    if pass_done:
        ist["missing_pass"] = ist.get("missing_pass", 0) + 1
        logger.info(
            "Lidarr: Missing pass {p} complete ({n} searched)",
            p=ist["missing_pass"],
            n=len(new_log),
        )

    # --- Cutoff queue ---
    cutoff = filter_monitored(cutoff)
    if cutoff_tag_id is not None:
        cutoff = filter_by_tag(cutoff, cutoff_tag_id, _lidarr_tags)
        logger.debug("Lidarr: Tag filter applied -- {n} cutoff items match tag", n=len(cutoff))
    batch, new_log, pass_done = prioritize_batch(
        cutoff, ist.get("cutoff_searched", []), cutoff_limit,
        key_fn=lambda a: str(a["id"]),
    )
    for album in batch:
        title = album.get("title", "unknown")
        try:
            await client.search_albums([album["id"]])
            await insert_search_entry(
                db, "Lidarr", "cutoff", title,
                outcome="searched", detail="search triggered",
                item_id=album["id"],
                instance_id=instance_name,
                max_rows=settings.general.max_history_rows,
            )
            logger.info("Lidarr: Searched {title} (cutoff)", title=title)
            searched_count += 1
        except PendingCapExceeded as cap_exc:
            logger.warning(
                "Skipping search history insert -- pending-row cap reached "
                "for {app}/{instance} {item!r}",
                app=cap_exc.app,
                instance=cap_exc.instance_id,
                item=cap_exc.item_name,
            )
            skipped_count += 1
            continue
        except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
            logger.warning(
                "Lidarr: Failed to search {title}: {exc}",
                title=title,
                exc=_sanitize_exc(exc),
            )
            await insert_search_entry(
                db, "Lidarr", "cutoff", title,
                outcome="failed", detail=_sanitize_exc(exc),
                item_id=album.get("id"),
                instance_id=instance_name,
                max_rows=settings.general.max_history_rows,
            )
            skipped_count += 1
    ist["cutoff_searched"] = [] if pass_done else new_log
    if pass_done:
        ist["cutoff_pass"] = ist.get("cutoff_pass", 0) + 1
        logger.info(
            "Lidarr: Cutoff pass {p} complete ({n} searched)",
            p=ist["cutoff_pass"],
            n=len(new_log),
        )

    # --- Diagnostic summary ---
    elapsed = time.monotonic() - cycle_start
    logger.info(
        "Lidarr: Cycle completed in {elapsed:.1f}s -- {fetched} fetched, {searched} searched, {skipped} skipped",
        elapsed=elapsed,
        fetched=ist["missing_count"] + ist["cutoff_count"],
        searched=searched_count,
        skipped=skipped_count,
    )

    # --- Update last_run and last_success ---
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    ist["last_run"] = now_iso
    ist["last_success"] = now_iso
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
