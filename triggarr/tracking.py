"""Tracking orchestrator -- polls *arr history APIs to detect grabs and resolve search outcomes.

Bridges the correlation engine (triggarr.correlation) with the DB layer (triggarr.db)
to close the loop: searched -> grabbed / partial / unresolved.

Sonarr tracking is ownership-aware (ATTR-01, ATTR-02, ATTR-04): pending
searches are selected by the instance's permanent stable ID (not its display
name, so a rename or a different server reusing an old name never misroutes
a pending search), grabs without a trustworthy Sonarr identity are skipped
and counted, grabs already credited to another search are excluded before
correlation, matching requires the same season, and distinct-episode counts
accumulate across tracking checks with ownership committed atomically in the
same transaction as every outcome/stat update.

Sonarr v5 (gap closure, SONARRV5-02/-03): a v5 grab-history record never
nests its episode/season identity (v4 does). When a candidate grab lacks a
valid nested season, Sonarr tracking resolves it from Sonarr's own episode
data before the identity gate runs: one ``get_series_episodes`` call per
series group per check (cached for that check, bounded by
``_MAX_SERIES_EPISODE_LISTS_PER_CHECK``), with a per-id ``get_episode``
fallback only for ids missing from that list (bounded by
``_MAX_EPISODE_ID_LOOKUPS_PER_CHECK``). Groups are processed in
earliest-window-end-first order so an exhausted budget starves the least
urgent group first. Resolution only ever credits a grab when the resolved
identity agrees with the grab and the tracked series -- any mismatch is
definitive (no credit, counted and logged, row resolves normally). A
transient problem (network/malformed/other HTTP error) never resolves a
row this check (mirrors a grab-history fetch failure) unless that row is
individually more than ``_TRANSIENT_ESCALATION_HOURS`` past its own window
end, in which case its unverifiable grabs are treated as definitive so the
row can finally resolve. A single circuit breaker (opened by any transport
error) stops all further episode requests for the rest of the check.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import aiosqlite
import httpx
import pydantic
from loguru import logger

from triggarr.clients.base import ArrClient, _sanitize_exc
from triggarr.clients.sonarr import SonarrClient
from triggarr.correlation import SearchRecord, _parse_iso, correlate_grabs, sonarr_identity_problem
from triggarr.db import OwnedGrab, get_owned_grabs, get_trackable_entries, update_outcome_and_stats
from triggarr.models.arr import EpisodeSummary, GrabEvent

# One list call per series covers a season pack or complete-series pack of
# any size, so needing to resolve more than 50 distinct series in a single
# tracking check is far above any normal tracking load.
_MAX_SERIES_EPISODE_LISTS_PER_CHECK = 50
# Per-id calls are only a fallback for episode ids missing from a
# successfully-fetched series list (rare: a deleted or moved episode), so a
# smaller budget than the series-list cap is enough.
_MAX_EPISODE_ID_LOOKUPS_PER_CHECK = 25
# A per-row bound derived from each row's own timestamp, not a new stored
# column or migration -- it survives restarts for free. 24h is about 48
# scheduled checks at the default 30-minute tracking interval.
_TRANSIENT_ESCALATION_HOURS = 24


async def run_tracking_check(
    db: aiosqlite.Connection,
    client: ArrClient,
    app_name: str,
    instance_id: str,
    tracking_window_minutes: int,
    *,
    instance_stable_id: str,
) -> dict[str, int]:
    """Poll *arr grab history and resolve pending search outcomes for one instance.

    Args:
        db: Open aiosqlite connection.
        client: The *arr client for this instance.
        app_name: Application name (e.g. "Radarr", "Sonarr").
        instance_id: Instance display name. Used for Radarr/Lidarr pending-search
            selection and for the name stored on a newly-created legacy
            lifetime_stats row.
        tracking_window_minutes: Minutes after a search to look for grabs.
        instance_stable_id: The instance's permanent Triggarr-assigned ID.
            For Sonarr this is the required key for pending-search selection
            and grab ownership (a rename or a different server reusing an
            old name must never misroute or double-credit a search); an
            empty value refuses to track rather than risk sharing ownership
            across instances. For Radarr/Lidarr it only keys lifetime stat
            increments (falling back to the legacy name-keyed row when
            empty); selection and outcome logic there are unchanged.

    Returns:
        Dict with counts: ``{"grabbed": N, "partial": N, "partial_expired": N,
        "unresolved": N, "errors": N, "identity_skipped": N}``.
        ``identity_skipped`` counts Sonarr grabs dropped for lacking a
        trustworthy episode/season identity; always present, always 0 for
        non-Sonarr apps.
    """
    counts: dict[str, int] = {
        "grabbed": 0,
        "partial": 0,
        "partial_expired": 0,
        "unresolved": 0,
        "errors": 0,
        "identity_skipped": 0,
    }

    if app_name == "Sonarr":
        return await _run_sonarr_tracking_check(
            db,
            client,
            instance_id,
            tracking_window_minutes,
            instance_stable_id=instance_stable_id,
            counts=counts,
        )

    entries = await get_trackable_entries(db, instance_id=instance_id)
    if not entries:
        logger.debug("Tracking[{inst}]: no pending entries", inst=instance_id)
        return counts

    now = datetime.now(UTC)

    # Group entries by item_id to share one API call per item.
    groups: dict[int, list[dict]] = {}
    for entry in entries:
        if entry["app"] != app_name:
            continue  # belt-and-suspenders: instance_id should already scope correctly
        groups.setdefault(entry["item_id"], []).append(entry)

    for item_id, group_entries in groups.items():
        # Fetch grab history -- network errors are non-fatal.
        try:
            grabs = await client.get_grab_history(item_id)
        except (httpx.HTTPError, pydantic.ValidationError) as exc:
            logger.warning(
                "Tracking[{inst}]: failed to fetch grab history for {app} item {id}: {exc}",
                inst=instance_id,
                app=app_name,
                id=item_id,
                exc=(
                    f"HTTP {exc.response.status_code}"
                    if isinstance(exc, httpx.HTTPStatusError)
                    else type(exc).__name__
                ),
            )
            counts["errors"] += len(group_entries)
            continue

        # Build SearchRecord list for correlation.
        searches = [
            SearchRecord(
                history_id=e["id"],
                item_id=e["item_id"],
                searched_at=_parse_timestamp(e["timestamp"]),
                missing_count=e["missing_count"],
            )
            for e in group_entries
        ]

        results = correlate_grabs(searches, grabs, tracking_window_minutes)

        # Resolve each entry using the correlation results.
        for entry, result in zip(group_entries, results, strict=True):
            window_end = _parse_timestamp(entry["timestamp"]) + timedelta(minutes=tracking_window_minutes)
            window_expired = now > window_end

            outcome, detail, stat_increments = _determine_outcome(
                app=app_name,
                queue_type=entry["queue_type"],
                current_outcome=entry["outcome"],
                missing_count=entry["missing_count"],
                grab_count=result.grab_count,
                matched_grabs=result.matched_grabs,
                window_expired=window_expired,
            )

            if outcome is None:
                # Still within window, no action needed.
                continue

            await update_outcome_and_stats(
                db,
                result.history_id,
                outcome,
                detail,
                app=app_name,
                queue_type=entry["queue_type"],
                instance_id=instance_id,
                instance_stable_id=instance_stable_id or None,
                stat_increments=stat_increments,
            )
            counts[outcome] = counts.get(outcome, 0) + 1

    return counts


# ---------------------------------------------------------------------------
# Sonarr v5 episode-identity resolution (gap closure, SONARRV5-02/-03)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _EpisodeLookupResult:
    """One episode lookup's outcome (series-list hit or per-id fallback).

    ``kind`` is one of ``"ok"`` (summary populated), ``"definitive"`` (the
    episode id itself is conclusively not creditable -- a 404 on the per-id
    endpoint), or ``"transient"`` (a network/malformed/budget problem that
    may resolve on a later check).
    """

    kind: str
    summary: EpisodeSummary | None = None
    reason: str = ""


@dataclass
class _CheckResolutionState:
    """Per-check resolution cache, request budgets and circuit breaker.

    Created fresh at the start of ``_run_sonarr_tracking_check`` and
    discarded on return -- never module-level, never stored on the client,
    so nothing here leaks between tracking checks or between instances.
    """

    episode_cache: dict[int, _EpisodeLookupResult] = field(default_factory=dict)
    series_list_calls: int = 0
    episode_lookup_calls: int = 0
    circuit_open: bool = False


@dataclass(frozen=True)
class _GrabResolution:
    """One candidate grab's resolution outcome for this check."""

    grab: GrabEvent
    outcome: str  # "gate" | "definitive" | "transient"
    reason: str = ""


@dataclass
class _GroupResolutionResult:
    """Partitioned resolution results for one series group's candidate grabs."""

    gate_grabs: list[GrabEvent]
    definitive_skips: list[tuple[GrabEvent, str]]
    transient: list[tuple[GrabEvent, str]]


def _needs_episode_resolution(grab: GrabEvent) -> bool:
    """True when a grab lacks a valid nested season and must be resolved.

    A v4-shaped grab (nested ``episode`` with a valid ``seasonNumber``)
    never needs resolution and never triggers an episode request.
    """
    if grab.episode is None:
        return True
    season = grab.episode.seasonNumber
    return season is None or season < 0


def _eligible_for_resolution_attempt(grab: GrabEvent, series_id: int) -> bool:
    """True when a grab needing resolution has enough identity to attempt it.

    A grab with no positive top-level ``episodeId`` or a top-level
    ``seriesId`` that already disagrees with the tracked series is left
    alone -- the unchanged identity gate (``sonarr_identity_problem``)
    reports the existing reason for it, no resolution attempt is wasted.
    """
    if grab.episodeId is None or grab.episodeId <= 0:
        return False
    return grab.seriesId is None or grab.seriesId == series_id


def _verify_resolved_summary(grab: GrabEvent, series_id: int, summary: EpisodeSummary) -> str | None:
    """Return a definitive-failure reason if a resolved summary disagrees with the grab.

    Checks the resolved episode's id/seriesId/seasonNumber against the
    grab's own top-level and (if present) nested identity fields. Returns
    None when everything agrees and the summary carries a valid season --
    the grab may then be safely credited.
    """
    if summary.id != grab.episodeId:
        return "episode lookup conflicting episode id"
    if grab.episode is not None and grab.episode.id is not None and summary.id != grab.episode.id:
        return "episode lookup conflicting episode id"
    if summary.seriesId is None or summary.seriesId != series_id:
        return "episode lookup series mismatch"
    if grab.seriesId is not None and summary.seriesId != grab.seriesId:
        return "episode lookup series mismatch"
    if grab.episode is not None and grab.episode.seriesId is not None and summary.seriesId != grab.episode.seriesId:
        return "episode lookup series mismatch"
    if summary.seasonNumber is None or summary.seasonNumber < 0:
        return "episode lookup missing season"
    return None


async def _get_episode_cached(
    client: SonarrClient, episode_id: int, state: _CheckResolutionState,
) -> _EpisodeLookupResult:
    """Resolve one episode id via the per-id fallback, cached for this check."""
    cached = state.episode_cache.get(episode_id)
    if cached is not None:
        return cached

    if state.circuit_open:
        result = _EpisodeLookupResult("transient", reason="never attempted: circuit open")
    elif state.episode_lookup_calls >= _MAX_EPISODE_ID_LOOKUPS_PER_CHECK:
        result = _EpisodeLookupResult("transient", reason="never attempted: budget")
    else:
        state.episode_lookup_calls += 1
        try:
            summary = await client.get_episode(episode_id)
            result = _EpisodeLookupResult("ok", summary=summary)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                result = _EpisodeLookupResult("definitive", reason="episode lookup not found")
            else:
                result = _EpisodeLookupResult("transient", reason=_sanitize_exc(exc))
        except httpx.TransportError as exc:
            state.circuit_open = True
            result = _EpisodeLookupResult("transient", reason=_sanitize_exc(exc))
        except (httpx.HTTPError, pydantic.ValidationError, ValueError) as exc:
            result = _EpisodeLookupResult("transient", reason=_sanitize_exc(exc))

    state.episode_cache[episode_id] = result
    return result


async def _get_series_episode_map(
    client: SonarrClient, series_id: int, state: _CheckResolutionState,
) -> dict[int, EpisodeSummary] | _EpisodeLookupResult:
    """Fetch one series' episode list and build an episodeId -> EpisodeSummary map.

    Returns a dict on success (entries with an invalid id, a seriesId that
    disagrees with this series, or an invalid season are ignored), or an
    ``_EpisodeLookupResult`` with ``kind == "transient"`` on any failure --
    a whole-list failure is never "definitive" (an individual episode id
    might still resolve via the per-id fallback once the list itself is
    available again).
    """
    if state.circuit_open:
        return _EpisodeLookupResult("transient", reason="never attempted: circuit open")
    if state.series_list_calls >= _MAX_SERIES_EPISODE_LISTS_PER_CHECK:
        return _EpisodeLookupResult("transient", reason="never attempted: budget")

    state.series_list_calls += 1
    try:
        episodes = await client.get_series_episodes(series_id)
    except httpx.TransportError as exc:
        state.circuit_open = True
        return _EpisodeLookupResult("transient", reason=_sanitize_exc(exc))
    except (httpx.HTTPError, pydantic.ValidationError, ValueError) as exc:
        return _EpisodeLookupResult("transient", reason=_sanitize_exc(exc))

    mapping: dict[int, EpisodeSummary] = {}
    for ep in episodes:
        if ep.id is None or ep.id <= 0:
            continue
        if ep.seriesId != series_id:
            continue
        if ep.seasonNumber is None or ep.seasonNumber < 0:
            continue
        mapping[ep.id] = ep
    return mapping


async def _resolve_grab_episode(
    grab: GrabEvent,
    series_id: int,
    series_map: dict[int, EpisodeSummary],
    client: SonarrClient,
    state: _CheckResolutionState,
) -> _GrabResolution:
    """Resolve one grab's episode identity from a successfully-fetched series map."""
    entry = series_map.get(grab.episodeId)
    lookup = _EpisodeLookupResult("ok", summary=entry) if entry is not None else await _get_episode_cached(
        client, grab.episodeId, state,
    )

    if lookup.kind == "transient":
        return _GrabResolution(grab, "transient", lookup.reason)
    if lookup.kind == "definitive":
        return _GrabResolution(grab, "definitive", lookup.reason)

    summary = lookup.summary
    if summary is None:
        # Defensive only: kind == "ok" always carries a summary.
        return _GrabResolution(grab, "transient", "internal error: missing episode summary")
    verify_reason = _verify_resolved_summary(grab, series_id, summary)
    if verify_reason is not None:
        return _GrabResolution(grab, "definitive", verify_reason)
    resolved_grab = grab.model_copy(update={"episode": summary})
    return _GrabResolution(resolved_grab, "gate")


async def _resolve_group_identities(
    client: SonarrClient,
    series_id: int,
    candidate_grabs: list[GrabEvent],
    group_entries: list[dict],
    tracking_window_minutes: int,
    state: _CheckResolutionState,
    instance_id: str,
) -> _GroupResolutionResult:
    """Partition one series group's candidate grabs for the identity gate.

    Grabs that already carry a valid season (v4-shaped, or already resolved
    on a prior check and now re-fetched unchanged) pass straight through.
    Grabs needing resolution whose date is unparseable or falls outside
    every pending row's window are dropped silently (never resolved, never
    logged beyond one debug count, never reaching the gate or correlate --
    they can never be credited by any currently-pending search). The
    remaining in-window grabs get one series-episode-list call (cached,
    capped, circuit-gated) with a per-id fallback only for ids missing from
    a successfully-fetched list.
    """
    window = timedelta(minutes=tracking_window_minutes)
    window_starts = [_parse_timestamp(e["timestamp"]) for e in group_entries]
    window_ends = [s + window for s in window_starts]

    gate_grabs: list[GrabEvent] = []
    definitive: list[tuple[GrabEvent, str]] = []
    transient: list[tuple[GrabEvent, str]] = []
    to_resolve: list[GrabEvent] = []
    dropped = 0

    for grab in candidate_grabs:
        if not _needs_episode_resolution(grab):
            gate_grabs.append(grab)
            continue
        if not _eligible_for_resolution_attempt(grab, series_id):
            # Let the unchanged identity gate report the existing reason.
            gate_grabs.append(grab)
            continue
        try:
            grab_time = _parse_iso(grab.date)
        except (ValueError, TypeError):
            dropped += 1
            continue
        if not any(start <= grab_time <= end for start, end in zip(window_starts, window_ends, strict=True)):
            dropped += 1
            continue
        to_resolve.append(grab)

    if dropped:
        logger.debug(
            "Tracking[{inst}]: dropped {count} out-of-window grab(s) needing episode "
            "identity resolution for Sonarr series {series}",
            inst=instance_id,
            count=dropped,
            series=series_id,
        )

    if to_resolve:
        series_map_or_failure = await _get_series_episode_map(client, series_id, state)
        if isinstance(series_map_or_failure, _EpisodeLookupResult):
            for grab in to_resolve:
                transient.append((grab, series_map_or_failure.reason))
        else:
            for grab in to_resolve:
                resolution = await _resolve_grab_episode(grab, series_id, series_map_or_failure, client, state)
                if resolution.outcome == "gate":
                    gate_grabs.append(resolution.grab)
                elif resolution.outcome == "definitive":
                    definitive.append((resolution.grab, resolution.reason))
                else:
                    transient.append((resolution.grab, resolution.reason))

    return _GroupResolutionResult(gate_grabs, definitive, transient)


def _split_escalation(
    group_entries: list[dict], now: datetime, tracking_window_minutes: int,
) -> tuple[set[int], set[int]]:
    """Split a group's pending rows into (escalated, held) by 24h-past-window-end.

    Escalated rows are individually more than ``_TRANSIENT_ESCALATION_HOURS``
    past their own window end; everything else is held (no write this
    check).
    """
    threshold = timedelta(hours=_TRANSIENT_ESCALATION_HOURS)
    escalated: set[int] = set()
    held: set[int] = set()
    for entry in group_entries:
        window_end = _parse_timestamp(entry["timestamp"]) + timedelta(minutes=tracking_window_minutes)
        if now - window_end > threshold:
            escalated.add(entry["id"])
        else:
            held.add(entry["id"])
    return escalated, held


def _log_identity_skip(instance_id: str, grab_id: int, series_id: int, reason: str, counts: dict[str, int]) -> None:
    """Log and count one grab skipped for an untrustworthy or unresolved identity.

    Shared by the unchanged ``sonarr_identity_problem`` gate and the new
    resolution-definitive-failure path so both use the exact same log line
    and counter.
    """
    logger.warning(
        "Tracking[{inst}]: skipped grab {grab_id} for series {series} -- {reason}",
        inst=instance_id,
        grab_id=grab_id,
        series=series_id,
        reason=reason,
    )
    counts["identity_skipped"] += 1


async def _run_sonarr_tracking_check(
    db: aiosqlite.Connection,
    client: ArrClient,
    instance_id: str,
    tracking_window_minutes: int,
    *,
    instance_stable_id,
    counts: dict[str, int],
) -> dict[str, int]:
    """Ownership-aware Sonarr tracking (ATTR-01, ATTR-02, ATTR-04, R1, R2, R6).

    Selects pending searches by the instance's stable ID (never the display
    name), drops grabs without a trustworthy episode/season identity,
    excludes grabs already owned by another search for the same series,
    requires the matching season, counts distinct Sonarr episodes
    (accumulating ownership from previous checks with newly-matched grabs
    this check), and persists ownership atomically with every outcome/stat
    write.
    """
    if not instance_stable_id:
        # Never share ownership between instances: refuse to track rather
        # than risk crediting the wrong server's searches.
        pending_entries = await get_trackable_entries(db, instance_id=instance_id)
        pending_count = sum(1 for e in pending_entries if e["app"] == "Sonarr")
        logger.error(
            "Tracking[{inst}]: Sonarr instance has no stable ID yet -- skipping {count} pending entries",
            inst=instance_id,
            count=pending_count,
        )
        counts["errors"] += pending_count
        return counts

    entries = await get_trackable_entries(db, instance_stable_id=instance_stable_id)
    if not entries:
        logger.debug("Tracking[{inst}]: no pending entries", inst=instance_id)
        return counts

    now = datetime.now(UTC)

    groups: dict[int, list[dict]] = {}
    for entry in entries:
        if entry["app"] != "Sonarr":
            continue  # belt-and-suspenders: instance_stable_id should already scope correctly
        groups.setdefault(entry["item_id"], []).append(entry)

    # Expired-window groups first, so an exhausted per-check budget starves
    # the least urgent group rather than whichever happened to sort first.
    ordered_groups = sorted(
        groups.items(),
        key=lambda kv: min(
            _parse_timestamp(e["timestamp"]) + timedelta(minutes=tracking_window_minutes) for e in kv[1]
        ),
    )

    resolution_state = _CheckResolutionState()

    for series_id, group_entries in ordered_groups:
        try:
            grabs = await client.get_grab_history(series_id)
        except (httpx.HTTPError, pydantic.ValidationError) as exc:
            logger.warning(
                "Tracking[{inst}]: failed to fetch grab history for Sonarr item {id}: {exc}",
                inst=instance_id,
                id=series_id,
                exc=(
                    f"HTTP {exc.response.status_code}"
                    if isinstance(exc, httpx.HTTPStatusError)
                    else type(exc).__name__
                ),
            )
            counts["errors"] += len(group_entries)
            continue

        # Exclude grabs already owned by any search for this series (ATTR-02)
        # BEFORE resolution: never re-credit a grab, and never spend an
        # episode request re-resolving one that's already owned.
        owned = await get_owned_grabs(db, app="Sonarr", instance_stable_id=instance_stable_id, series_id=series_id)
        owned_grab_ids = {o.grab_id for o in owned}
        candidate_grabs = [g for g in grabs if g.id not in owned_grab_ids]

        group_resolution = (
            await _resolve_group_identities(
                client, series_id, candidate_grabs, group_entries, tracking_window_minutes,
                resolution_state, instance_id,
            )
            if isinstance(client, SonarrClient)
            else _GroupResolutionResult(candidate_grabs, [], [])
        )

        # Definitive skips are final regardless of what happens to the rest of
        # the group, so log and count them before any transient deferral.
        for grab, reason in group_resolution.definitive_skips:
            _log_identity_skip(instance_id, grab.id, series_id, reason, counts)

        held_ids: set[int] = set()
        if group_resolution.transient:
            escalated_ids, held_ids = _split_escalation(group_entries, now, tracking_window_minutes)
            if not escalated_ids:
                logger.warning(
                    "Tracking[{inst}]: deferred Sonarr item {id} -- episode identity lookup "
                    "unavailable ({reason})",
                    inst=instance_id,
                    id=series_id,
                    reason=group_resolution.transient[0][1],
                )
                counts["errors"] += len(group_entries)
                continue

            for grab, reason in group_resolution.transient:
                _log_identity_skip(
                    instance_id, grab.id, series_id, f"episode identity unavailable after escalation: {reason}", counts
                )
            max_hours = max(
                (now - (_parse_timestamp(e["timestamp"]) + timedelta(minutes=tracking_window_minutes)))
                .total_seconds()
                / 3600
                for e in group_entries
                if e["id"] in escalated_ids
            )
            logger.warning(
                "Tracking[{inst}]: episode identity still unavailable {hours}h after window for "
                "Sonarr item {id} -- resolving {n} row(s) without unverified grabs",
                inst=instance_id,
                hours=round(max_hours, 1),
                id=series_id,
                n=len(escalated_ids),
            )

        # Identity gate (R2, R6): a grab without a trustworthy Sonarr
        # identity can never be credited, and must never inflate a count.
        trustworthy_grabs: list[GrabEvent] = []
        for grab in group_resolution.gate_grabs:
            reason = sonarr_identity_problem(grab, series_id)
            if reason is not None:
                _log_identity_skip(instance_id, grab.id, series_id, reason, counts)
                continue
            trustworthy_grabs.append(grab)

        searches = [
            SearchRecord(
                history_id=e["id"],
                item_id=e["item_id"],
                searched_at=_parse_timestamp(e["timestamp"]),
                missing_count=e["missing_count"],
                season_number=e["season_number"],
            )
            for e in group_entries
        ]

        results = correlate_grabs(searches, trustworthy_grabs, tracking_window_minutes, match_season=True)

        for entry, result in zip(group_entries, results, strict=True):
            if entry["id"] in held_ids:
                # A sibling row in this group escalated, but this row has
                # not yet been pending 24h past its own window end -- no
                # write this check, mirroring a grab-history fetch failure.
                counts["errors"] += 1
                continue

            window_end = _parse_timestamp(entry["timestamp"]) + timedelta(minutes=tracking_window_minutes)
            window_expired = now > window_end

            previous = [o for o in owned if o.history_id == entry["id"]]
            new_grabs = result.matched_grabs

            # Distinct-episode accumulation (ATTR-04): the Sonarr episodeId
            # is the only counting key -- a repeat grab of the same episode
            # (season-pack re-grab) must never count twice, and no grab-id
            # fallback is ever used.
            episode_ids: set[int] = set()
            for record in previous:
                if record.episode_id is not None:
                    episode_ids.add(record.episode_id)
                else:
                    logger.warning(
                        "Tracking[{inst}]: owned grab {grab_id} has no episode id, ignoring for count",
                        inst=instance_id,
                        grab_id=record.grab_id,
                    )
            for grab in new_grabs:
                if grab.episodeId is not None:
                    episode_ids.add(grab.episodeId)
            grab_count = len(episode_ids)

            outcome, detail, stat_increments = _determine_outcome(
                app="Sonarr",
                queue_type=entry["queue_type"],
                current_outcome=entry["outcome"],
                missing_count=entry["missing_count"],
                grab_count=grab_count,
                matched_grabs=new_grabs,
                window_expired=window_expired,
            )

            owned_grabs = [
                OwnedGrab(
                    grab_id=grab.id,
                    episode_id=grab.episodeId,
                    series_id=series_id,
                    season_number=entry["season_number"],
                )
                for grab in new_grabs
            ]

            if outcome is None:
                # Still within window and not yet fully resolved. When new
                # grabs were matched this check, persist their ownership and
                # the updated progress detail now (in the same kind of
                # transaction as a resolution) so no other search can claim
                # them before the next check -- but never rewrite a row when
                # nothing new was found.
                if owned_grabs and entry["outcome"] == "partial" and not window_expired:
                    expected = entry["missing_count"] if entry["missing_count"] is not None else 0
                    progress_detail = f"partial: {grab_count}/{expected} episodes"
                    try:
                        await update_outcome_and_stats(
                            db,
                            entry["id"],
                            "partial",
                            progress_detail,
                            app="Sonarr",
                            queue_type=entry["queue_type"],
                            instance_id=instance_id,
                            instance_stable_id=instance_stable_id,
                            stat_increments=None,
                            owned_grabs=owned_grabs,
                        )
                    except sqlite3.IntegrityError:
                        logger.warning(
                            "Tracking[{inst}]: grab already owned for history_id {hid}",
                            inst=instance_id,
                            hid=entry["id"],
                        )
                        counts["errors"] += 1
                continue

            try:
                await update_outcome_and_stats(
                    db,
                    result.history_id,
                    outcome,
                    detail,
                    app="Sonarr",
                    queue_type=entry["queue_type"],
                    instance_id=instance_id,
                    instance_stable_id=instance_stable_id,
                    stat_increments=stat_increments,
                    owned_grabs=owned_grabs,
                )
            except sqlite3.IntegrityError:
                logger.warning(
                    "Tracking[{inst}]: grab already owned for history_id {hid}",
                    inst=instance_id,
                    hid=entry["id"],
                )
                counts["errors"] += 1
                continue
            counts[outcome] = counts.get(outcome, 0) + 1

    return counts


def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO timestamp string to a timezone-aware datetime."""
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _determine_outcome(
    *,
    app: str,
    queue_type: str,
    current_outcome: str,
    missing_count: int | None,
    grab_count: int,
    matched_grabs: list[GrabEvent],
    window_expired: bool,
) -> tuple[str | None, str, dict[str, int] | None]:
    """Determine the new outcome for a single search entry.

    Returns:
        Tuple of (outcome, detail, stat_increments). outcome is None
        if no update should be made (still waiting within window).
    """
    if app == "Radarr":
        return _radarr_outcome(queue_type, grab_count, matched_grabs, window_expired)
    if app == "Sonarr":
        return _sonarr_outcome(queue_type, current_outcome, missing_count, grab_count, matched_grabs, window_expired)
    if app == "Lidarr":
        return _lidarr_outcome(queue_type, grab_count, matched_grabs, window_expired)
    return None, "", None


def _radarr_outcome(
    queue_type: str,
    grab_count: int,
    matched_grabs: list[GrabEvent],
    window_expired: bool,
) -> tuple[str | None, str, dict[str, int] | None]:
    """Radarr outcome logic -- binary: grabbed or unresolved."""
    if grab_count > 0:
        source = (matched_grabs[0].sourceTitle or "unknown")[:200]
        detail = f"grabbed: {source}"
        stat_key = "movies_found" if queue_type == "missing" else "movies_updated"
        return "grabbed", detail, {stat_key: 1}

    if window_expired:
        return "unresolved", "no grabs detected within tracking window", None

    # Still within window, no grabs yet -- keep waiting.
    return None, "", None


def _sonarr_outcome(
    queue_type: str,
    current_outcome: str,
    missing_count: int | None,
    grab_count: int,
    matched_grabs: list[GrabEvent],
    window_expired: bool,
) -> tuple[str | None, str, dict[str, int] | None]:
    """Sonarr outcome logic -- three-state: grabbed, partial, or unresolved."""
    expected = missing_count if missing_count is not None else 0

    stat_key = "episodes_found" if queue_type == "missing" else "episodes_updated"

    # missing_count was None -- any grab means fully resolved.
    if expected == 0:
        if grab_count > 0:
            detail = f"grabbed: {grab_count} episodes"
            return "grabbed", detail, {stat_key: grab_count}
        if window_expired:
            return "unresolved", "no grabs detected within tracking window", None
        return None, "", None

    # All episodes resolved.
    if grab_count >= expected:
        detail = f"grabbed: {grab_count}/{expected} episodes"
        return "grabbed", detail, {stat_key: grab_count}

    # Some but not all episodes grabbed.
    if grab_count > 0 and grab_count < expected:
        # Partial grabs exist.
        if window_expired:
            if current_outcome == "partial_expired":
                # Already resolved as terminal partial -- no-op to prevent
                # double-counting stats on subsequent tracking cycles.
                return None, "", None
            # Terminal state: partial at window expiry -> increment stats once.
            detail = f"partial: {grab_count}/{expected} episodes (window expired)"
            return "partial_expired", detail, {stat_key: grab_count}

        if current_outcome == "searched":
            # First detection of partial grabs.
            detail = f"partial: {grab_count}/{expected} episodes"
            return "partial", detail, None

        # Already partial, not yet expired -- no-op (keep waiting).
        return None, "", None

    # No grabs at all.
    if window_expired:
        return "unresolved", "no grabs detected within tracking window", None

    # Still within window, no grabs yet -- keep waiting.
    return None, "", None


def _lidarr_outcome(
    queue_type: str,
    grab_count: int,
    matched_grabs: list[GrabEvent],
    window_expired: bool,
) -> tuple[str | None, str, dict[str, int] | None]:
    """Lidarr outcome logic -- binary: grabbed or unresolved.

    Albums are atomic search units (like Radarr movies), so the outcome
    is straightforward: either the album was grabbed or it wasn't.
    """
    if grab_count > 0:
        source = (matched_grabs[0].sourceTitle or "unknown")[:200]
        detail = f"grabbed: {source}"
        stat_key = "albums_found" if queue_type == "missing" else "albums_updated"
        return "grabbed", detail, {stat_key: 1}

    if window_expired:
        return "unresolved", "no grabs detected within tracking window", None

    # Still within window, no grabs yet -- keep waiting.
    return None, "", None
