"""Core search engine: utility functions and search cycle orchestrators.

Pure functions for filtering, batching, and deduplication, plus async
cycle functions that compose them with API client calls to drive the
automated search behaviour for Radarr, Sonarr, and Lidarr.  Search
history is persisted to SQLite via the ``triggarr.db`` module.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from datetime import UTC, datetime

import aiosqlite
import httpx
import pydantic
from loguru import logger

from triggarr.clients.lidarr import LidarrClient
from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.db import insert_search_entry
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


def slice_batch(items: list, cursor: int, batch_size: int) -> tuple[list, int]:
    """Slice a batch starting at cursor position with wrap-around.

    If cursor is past the end of the list, wraps to 0.
    Callers are responsible for logging wrap-around events.

    Args:
        items: Full list of items to batch from.
        cursor: Current position in the list.
        batch_size: Maximum number of items to return.

    Returns:
        Tuple of (batch, new_cursor). New cursor wraps to 0
        when it reaches or passes the end of the list.
    """
    if not items:
        return [], 0
    if cursor >= len(items):
        cursor = 0
    batch = items[cursor : cursor + batch_size]
    new_cursor = cursor + len(batch)
    if new_cursor >= len(items):
        new_cursor = 0
    return batch, new_cursor


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
    if instance_name not in state["radarr"]:
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
            tags = await client.get_tags()
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
    cursor = ist["missing_cursor"]
    batch, new_cursor = slice_batch(missing, cursor, missing_limit)
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
    ist["missing_cursor"] = new_cursor
    if new_cursor == 0 and batch:
        ist["missing_pass"] = ist.get("missing_pass", 0) + 1
        pass_num = ist["missing_pass"]
        logger.info("Radarr: Missing queue wrapped around — starting pass {p}", p=pass_num)

    # --- Cutoff queue ---
    cutoff = filter_monitored(cutoff)
    if cutoff_tag_id is not None:
        cutoff = filter_by_tag(cutoff, cutoff_tag_id, _radarr_tags)
        logger.debug("Radarr: Tag filter applied -- {n} cutoff items match tag", n=len(cutoff))
    cursor = ist["cutoff_cursor"]
    batch, new_cursor = slice_batch(cutoff, cursor, cutoff_limit)
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
    ist["cutoff_cursor"] = new_cursor
    if new_cursor == 0 and batch:
        ist["cutoff_pass"] = ist.get("cutoff_pass", 0) + 1
        pass_num = ist["cutoff_pass"]
        logger.info("Radarr: Cutoff queue wrapped around — starting pass {p}", p=pass_num)

    # --- Diagnostic summary ---
    elapsed = time.monotonic() - cycle_start
    logger.info(
        "Radarr: Cycle completed in {elapsed:.1f}s -- {fetched} fetched, {searched} searched, {skipped} skipped",
        elapsed=elapsed,
        fetched=ist["missing_count"] + ist["cutoff_count"],
        searched=searched_count,
        skipped=skipped_count,
    )

    # --- Update last_run ---
    ist["last_run"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return state


async def run_sonarr_cycle(
    client: SonarrClient,
    state: TriggarrState,
    instance_name: str,
    instance_config: InstanceConfig,
    settings: Settings,
    db: aiosqlite.Connection,
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
    if instance_name not in state["sonarr"]:
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
            tags = await client.get_tags()
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
    cursor = ist["missing_cursor"]
    batch, new_cursor = slice_batch(missing_seasons, cursor, missing_limit)
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
    ist["missing_cursor"] = new_cursor
    if new_cursor == 0 and batch:
        ist["missing_pass"] = ist.get("missing_pass", 0) + 1
        pass_num = ist["missing_pass"]
        logger.info("Sonarr: Missing queue wrapped around — starting pass {p}", p=pass_num)

    # --- Cutoff queue ---
    cutoff_episodes = filter_sonarr_episodes(cutoff_episodes)
    if cutoff_tag_id is not None:
        cutoff_episodes = filter_by_tag(cutoff_episodes, cutoff_tag_id, _sonarr_tags)
        logger.debug("Sonarr: Tag filter applied -- {n} cutoff episodes match tag", n=len(cutoff_episodes))
    cutoff_seasons = deduplicate_to_seasons(cutoff_episodes)
    ist["cutoff_searchable"] = len(cutoff_seasons)
    cursor = ist["cutoff_cursor"]
    batch, new_cursor = slice_batch(cutoff_seasons, cursor, cutoff_limit)
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
    ist["cutoff_cursor"] = new_cursor
    if new_cursor == 0 and batch:
        ist["cutoff_pass"] = ist.get("cutoff_pass", 0) + 1
        pass_num = ist["cutoff_pass"]
        logger.info("Sonarr: Cutoff queue wrapped around — starting pass {p}", p=pass_num)

    # --- Diagnostic summary ---
    elapsed = time.monotonic() - cycle_start
    logger.info(
        "Sonarr: Cycle completed in {elapsed:.1f}s -- {fetched} fetched, {searched} searched, {skipped} skipped",
        elapsed=elapsed,
        fetched=ist["missing_count"] + ist["cutoff_count"],
        searched=searched_count,
        skipped=skipped_count,
    )

    # --- Update last_run ---
    ist["last_run"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return state


async def run_lidarr_cycle(
    client: LidarrClient,
    state: TriggarrState,
    instance_name: str,
    instance_config: InstanceConfig,
    settings: Settings,
    db: aiosqlite.Connection,
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
    if instance_name not in state["lidarr"]:
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
            tags = await client.get_tags()
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
    cursor = ist["missing_cursor"]
    batch, new_cursor = slice_batch(missing, cursor, missing_limit)
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
    ist["missing_cursor"] = new_cursor
    if new_cursor == 0 and batch:
        ist["missing_pass"] = ist.get("missing_pass", 0) + 1
        pass_num = ist["missing_pass"]
        logger.info("Lidarr: Missing queue wrapped around — starting pass {p}", p=pass_num)

    # --- Cutoff queue ---
    cutoff = filter_monitored(cutoff)
    if cutoff_tag_id is not None:
        cutoff = filter_by_tag(cutoff, cutoff_tag_id, _lidarr_tags)
        logger.debug("Lidarr: Tag filter applied -- {n} cutoff items match tag", n=len(cutoff))
    cursor = ist["cutoff_cursor"]
    batch, new_cursor = slice_batch(cutoff, cursor, cutoff_limit)
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
    ist["cutoff_cursor"] = new_cursor
    if new_cursor == 0 and batch:
        ist["cutoff_pass"] = ist.get("cutoff_pass", 0) + 1
        pass_num = ist["cutoff_pass"]
        logger.info("Lidarr: Cutoff queue wrapped around — starting pass {p}", p=pass_num)

    # --- Diagnostic summary ---
    elapsed = time.monotonic() - cycle_start
    logger.info(
        "Lidarr: Cycle completed in {elapsed:.1f}s -- {fetched} fetched, {searched} searched, {skipped} skipped",
        elapsed=elapsed,
        fetched=ist["missing_count"] + ist["cutoff_count"],
        searched=searched_count,
        skipped=skipped_count,
    )

    # --- Update last_run ---
    ist["last_run"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return state
