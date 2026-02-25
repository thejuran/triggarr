"""Core search engine: utility functions and search cycle orchestrators.

Pure functions for filtering, batching, and deduplication, plus async
cycle functions that compose them with API client calls to drive the
automated search behaviour for Radarr and Sonarr.  Search history is
persisted to SQLite via the ``fetcharr.db`` module.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import aiosqlite
import httpx
import pydantic
from loguru import logger

from fetcharr.clients.radarr import RadarrClient
from fetcharr.clients.sonarr import SonarrClient
from fetcharr.db import insert_search_entry
from fetcharr.models.config import Settings
from fetcharr.state import FetcharrState


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


async def run_radarr_cycle(
    client: RadarrClient,
    state: FetcharrState,
    settings: Settings,
    db: aiosqlite.Connection,
) -> FetcharrState:
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
        settings: Application settings with batch size configuration.
        db: Open aiosqlite connection for search history persistence.

    Returns:
        Updated state with new cursor positions and last_run timestamp.
    """
    cycle_start = time.monotonic()

    try:
        missing = await client.get_wanted_missing()
        cutoff = await client.get_wanted_cutoff()
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning("Radarr: Cycle aborted -- {exc}", exc=exc)
        state["radarr"]["connected"] = False
        if not state["radarr"].get("unreachable_since"):
            state["radarr"]["unreachable_since"] = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
            )
        return state

    # Track connection health (WEBU-06)
    state["radarr"]["connected"] = True
    state["radarr"]["unreachable_since"] = None

    # Cache raw item counts before filtering (WEBU-04)
    state["radarr"]["missing_count"] = len(missing)
    state["radarr"]["cutoff_count"] = len(cutoff)

    # Apply hard max cap (SRCH-12)
    missing_limit = settings.radarr.search_missing_count
    cutoff_limit = settings.radarr.search_cutoff_count
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

    searched_count = 0
    skipped_count = 0

    # --- Missing queue ---
    missing = filter_monitored(missing)
    cursor = state["radarr"]["missing_cursor"]
    batch, new_cursor = slice_batch(missing, cursor, missing_limit)
    for movie in batch:
        try:
            await client.search_movies([movie["id"]])
            await insert_search_entry(
                db, "Radarr", "missing", movie["title"],
                outcome="searched", detail="search triggered",
                item_id=movie["id"],
                max_rows=settings.general.max_history_rows,
            )
            logger.info("Radarr: Searched {title} (missing)", title=movie["title"])
            searched_count += 1
        except Exception as exc:
            logger.warning(
                "Radarr: Failed to search {title}: {exc}",
                title=movie.get("title", "unknown"),
                exc=exc,
            )
            await insert_search_entry(
                db, "Radarr", "missing", movie.get("title", "unknown"),
                outcome="failed", detail=_sanitize_exc(exc),
                item_id=movie.get("id"),
                max_rows=settings.general.max_history_rows,
            )
            skipped_count += 1
    state["radarr"]["missing_cursor"] = new_cursor
    if new_cursor == 0 and batch:
        state["radarr"]["missing_pass"] = state["radarr"].get("missing_pass", 1) + 1
        pass_num = state["radarr"]["missing_pass"]
        logger.info("Radarr: Missing queue wrapped around — starting pass {p}", p=pass_num)

    # --- Cutoff queue ---
    cutoff = filter_monitored(cutoff)
    cursor = state["radarr"]["cutoff_cursor"]
    batch, new_cursor = slice_batch(cutoff, cursor, cutoff_limit)
    for movie in batch:
        try:
            await client.search_movies([movie["id"]])
            await insert_search_entry(
                db, "Radarr", "cutoff", movie["title"],
                outcome="searched", detail="search triggered",
                item_id=movie["id"],
                max_rows=settings.general.max_history_rows,
            )
            logger.info("Radarr: Searched {title} (cutoff)", title=movie["title"])
            searched_count += 1
        except Exception as exc:
            logger.warning(
                "Radarr: Failed to search {title}: {exc}",
                title=movie.get("title", "unknown"),
                exc=exc,
            )
            await insert_search_entry(
                db, "Radarr", "cutoff", movie.get("title", "unknown"),
                outcome="failed", detail=_sanitize_exc(exc),
                item_id=movie.get("id"),
                max_rows=settings.general.max_history_rows,
            )
            skipped_count += 1
    state["radarr"]["cutoff_cursor"] = new_cursor
    if new_cursor == 0 and batch:
        state["radarr"]["cutoff_pass"] = state["radarr"].get("cutoff_pass", 1) + 1
        pass_num = state["radarr"]["cutoff_pass"]
        logger.info("Radarr: Cutoff queue wrapped around — starting pass {p}", p=pass_num)

    # --- Diagnostic summary ---
    elapsed = time.monotonic() - cycle_start
    logger.info(
        "Radarr: Cycle completed in {elapsed:.1f}s -- {fetched} fetched, {searched} searched, {skipped} skipped",
        elapsed=elapsed,
        fetched=state["radarr"]["missing_count"] + state["radarr"]["cutoff_count"],
        searched=searched_count,
        skipped=skipped_count,
    )

    # --- Update last_run ---
    state["radarr"]["last_run"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return state


async def run_sonarr_cycle(
    client: SonarrClient,
    state: FetcharrState,
    settings: Settings,
    db: aiosqlite.Connection,
) -> FetcharrState:
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
        settings: Application settings with batch size configuration.
        db: Open aiosqlite connection for search history persistence.

    Returns:
        Updated state with new cursor positions and last_run timestamp.
    """
    cycle_start = time.monotonic()

    try:
        missing_episodes = await client.get_wanted_missing()
        cutoff_episodes = await client.get_wanted_cutoff()
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning("Sonarr: Cycle aborted -- {exc}", exc=exc)
        state["sonarr"]["connected"] = False
        if not state["sonarr"].get("unreachable_since"):
            state["sonarr"]["unreachable_since"] = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
            )
        return state

    # Track connection health (WEBU-06)
    state["sonarr"]["connected"] = True
    state["sonarr"]["unreachable_since"] = None

    # Cache raw item counts before filtering (WEBU-04)
    state["sonarr"]["missing_count"] = len(missing_episodes)
    state["sonarr"]["cutoff_count"] = len(cutoff_episodes)

    # Apply hard max cap (SRCH-12)
    missing_limit = settings.sonarr.search_missing_count
    cutoff_limit = settings.sonarr.search_cutoff_count
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

    searched_count = 0
    skipped_count = 0

    # --- Missing queue ---
    missing_episodes = filter_sonarr_episodes(missing_episodes)
    missing_seasons = deduplicate_to_seasons(missing_episodes)
    cursor = state["sonarr"]["missing_cursor"]
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
                max_rows=settings.general.max_history_rows,
            )
            logger.info("Sonarr: Searched {name} (missing)", name=season["display_name"])
            searched_count += 1
        except Exception as exc:
            logger.warning(
                "Sonarr: Failed to search {name}: {exc}",
                name=season.get("display_name", "unknown"),
                exc=exc,
            )
            await insert_search_entry(
                db, "Sonarr", "missing", season.get("display_name", "unknown"),
                outcome="failed", detail=_sanitize_exc(exc),
                item_id=season.get("seriesId"),
                season_number=season.get("seasonNumber"),
                missing_count=season.get("episode_count"),
                max_rows=settings.general.max_history_rows,
            )
            skipped_count += 1
    state["sonarr"]["missing_cursor"] = new_cursor
    if new_cursor == 0 and batch:
        state["sonarr"]["missing_pass"] = state["sonarr"].get("missing_pass", 1) + 1
        pass_num = state["sonarr"]["missing_pass"]
        logger.info("Sonarr: Missing queue wrapped around — starting pass {p}", p=pass_num)

    # --- Cutoff queue ---
    cutoff_episodes = filter_sonarr_episodes(cutoff_episodes)
    cutoff_seasons = deduplicate_to_seasons(cutoff_episodes)
    cursor = state["sonarr"]["cutoff_cursor"]
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
                max_rows=settings.general.max_history_rows,
            )
            logger.info("Sonarr: Searched {name} (cutoff)", name=season["display_name"])
            searched_count += 1
        except Exception as exc:
            logger.warning(
                "Sonarr: Failed to search {name}: {exc}",
                name=season.get("display_name", "unknown"),
                exc=exc,
            )
            await insert_search_entry(
                db, "Sonarr", "cutoff", season.get("display_name", "unknown"),
                outcome="failed", detail=_sanitize_exc(exc),
                item_id=season.get("seriesId"),
                season_number=season.get("seasonNumber"),
                missing_count=season.get("episode_count"),
                max_rows=settings.general.max_history_rows,
            )
            skipped_count += 1
    state["sonarr"]["cutoff_cursor"] = new_cursor
    if new_cursor == 0 and batch:
        state["sonarr"]["cutoff_pass"] = state["sonarr"].get("cutoff_pass", 1) + 1
        pass_num = state["sonarr"]["cutoff_pass"]
        logger.info("Sonarr: Cutoff queue wrapped around — starting pass {p}", p=pass_num)

    # --- Diagnostic summary ---
    elapsed = time.monotonic() - cycle_start
    logger.info(
        "Sonarr: Cycle completed in {elapsed:.1f}s -- {fetched} fetched, {searched} searched, {skipped} skipped",
        elapsed=elapsed,
        fetched=state["sonarr"]["missing_count"] + state["sonarr"]["cutoff_count"],
        searched=searched_count,
        skipped=skipped_count,
    )

    # --- Update last_run ---
    state["sonarr"]["last_run"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return state
