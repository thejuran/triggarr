---
phase: 81-correct-sonarr-grab-attribution
plan: 11
subsystem: search-correctness
tags: [sonarr, tracking, attribution, v5, episode-identity, httpx, gap-closure]

# Dependency graph
requires:
  - phase: 81-10
    provides: "Sanitized live-captured v5 fixtures (history_season_pack_v5.json, episodes_v5.json) and their loaders (load_sonarr_series_episode_list, load_sonarr_episode_fixture)"
  - phase: 81-04
    provides: "Ownership-aware Sonarr tracking (_run_sonarr_tracking_check, get_owned_grabs, update_outcome_and_stats owned_grabs), sonarr_identity_problem gate, correlate_grabs(match_season=True)"
  - phase: 81-07
    provides: "The live v5 identity-gap finding and the owner's directed fix shape (list-first resolution with series verification, cached per check, skip on failure)"
provides:
  - "SonarrClient.get_series_episodes(series_id) and get_episode(episode_id): single-request, no-retry calls to Sonarr's episode endpoints"
  - "Per-check verified episode-identity resolution in _run_sonarr_tracking_check: one series-episode-list call per group per check (cached, capped), per-id fallback only for ids missing from that list (capped), expired-window-first group ordering, a single circuit breaker, per-row 24h transient escalation, and owned-grab exclusion moved before resolution"
  - "25 real-client-path v5 regressions (tests/test_attribution_client_path.py) plus 7 SonarrClient tests (tests/test_clients.py) covering season packs of any size, repeat checks, distinct-episode caching, per-id fallback and its 404, list-entry validation, transient deferral/healing, the circuit breaker, budget caps, per-row escalation, each definitive mismatch case, nested-episode-without-season resolution, out-of-window bounding, and v4-unchanged"
affects: [81-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "List-first identity resolution: one GET /api/v3/episode?seriesId=X per series group per tracking check (any pack size), with GET /api/v3/episode/{id} only as a fallback for ids missing from that list -- bounds request volume regardless of pack size"
    - "Per-check-only state (cache, budget counters, circuit flag) as a dataclass created at the top of _run_sonarr_tracking_check and discarded on return -- never module-level, never on the client, so nothing leaks between checks or instances"
    - "Group-level transient deferral with per-row 24h escalation: a transient resolution failure anywhere in a series group defers the whole group's writes (mirroring a grab-history fetch failure) unless some row is individually more than 24h past its own window end, in which case only that row's unverifiable grabs are treated as definitive and only that row is written"
    - "Owned-grab exclusion reordered before resolution (not just before correlation), so an already-credited episode is never re-resolved (and never re-spends a series-list/per-id request) on a repeat check"

key-files:
  created: []
  modified:
    - triggarr/clients/sonarr.py
    - triggarr/tracking.py
    - triggarr/models/arr.py
    - tests/test_attribution_client_path.py
    - tests/test_clients.py

key-decisions:
  - "List-level failures (any status, timeout, malformed body, ValidationError) are always transient, never definitive -- only a per-id 404 is a definitive 'episode lookup not found', since a missing/deleted/moved single episode is a real Sonarr state but a failing list call says nothing about any specific episode's identity"
  - "Per-id fallback is attempted only for an episode id confirmed absent from a successfully-fetched series list -- if the list call itself fails (transient), every grab needing resolution in that group becomes transient directly rather than falling back to N individual per-id calls, preserving the one-call-per-series request bound the owner specified"
  - "_MAX_SERIES_EPISODE_LISTS_PER_CHECK=50, _MAX_EPISODE_ID_LOOKUPS_PER_CHECK=25, _TRANSIENT_ESCALATION_HOURS=24: one list call covers a pack of any size so needing 50 in one check is far above normal load; per-id calls are a rare fallback so a smaller budget suffices; 24h is a per-row bound derived from each row's own timestamp (no new column/migration), about 48 scheduled checks at the default 30-minute interval"
  - "When any grab in a series group is transient and no row has escalated, the ENTIRE group's processing is skipped (no identity gate, no correlate, no counts beyond counts['errors'] += len(group_entries)) rather than partially reporting -- avoids counts that would differ run-to-run depending on which specific grabs happened to resolve before the one transient failure"
  - "Resolution uses isinstance(client, SonarrClient) as the sole gate, so existing AsyncMock-based Sonarr tracking tests (test_tracking.py) are unaffected -- they keep exercising the unchanged v4/generic identity-gate path exactly as before"

patterns-established:
  - "A failing list-level episode request is always transient (never definitive); only a per-id 404 is definitive -- keep this asymmetry if any future *arr endpoint gets a similar list+per-id fallback shape"

requirements-completed: []  # SONARRV5-02 stays explicitly open per D-13 -- this plan has no live evidence; Plan 81-12 provides it. SONARRV5-03/ATTR-01/ATTR-04 are satisfied by this plan's fixture-regression evidence but marking them complete is the orchestrator's call, not this plan's.

# Metrics
duration: ~70min (two commits 57s apart at the end of a longer research/design/implementation session; no explicit start-epoch was captured at spawn, so this is an estimate from session shape, not a precise measurement)
completed: 2026-10-19
---

# Phase 81 Plan 11: Sonarr v5 Episode-Identity Resolution Summary

**Sonarr v5 grabs (which never nest episode/season identity in grab history) are now resolved via one series-episode-list call per group per tracking check with a per-id fallback, verified against the grab and tracked series before crediting, with transient failures deferred (never silently resolved) and a strict per-row 24-hour escalation bound.**

## Performance

- **Duration:** ~70 min (estimate; see Metrics note above -- no start-epoch was captured at spawn)
- **Completed:** 2026-10-19
- **Tasks:** 2 (both complete: RED, then GREEN)
- **Files modified:** 5 (3 production, 2 test)

## Accomplishments

- **Task 1 (RED):** Extended `_SonarrHistoryFake` with series-episode-list and per-episode-id endpoints, override hooks for status code / exception / replacement body, and request recording. Added 25 `test_client_path_v5_*` real-client-path tests and 7 `SonarrClient` tests (`test_sonarr_get_episode_*` / `test_sonarr_get_series_episodes_*`). Confirmed RED by temporarily reverting the production files to HEAD and re-running: 31 of the 32 new tests failed for the right reason (missing `SonarrClient` methods, or -- for 5 "definitive identity" tests that would otherwise pass against the old generic "missing season" gate with zero episode requests made -- strengthened with explicit request-count assertions so they can't pass without a real resolution attempt); the 1 that passed pre-implementation (`test_client_path_v5_v4_shape_makes_zero_episode_requests`) is deliberately pinning *unchanged* v4 behavior and was expected to already hold. All 1962 pre-existing tests stayed green throughout. Restored the implementation via `git apply` of the saved patch and re-confirmed full green before the GREEN commit.
- **Task 2 (GREEN):** `SonarrClient.get_series_episodes`/`get_episode` (single request, no retry, direct `self._client.get`). `_run_sonarr_tracking_check` now: fetches grab history (unchanged failure branch) -> excludes owned grabs -> resolves identity for grabs needing it (`isinstance(client, SonarrClient)` gated) -> runs the unchanged `sonarr_identity_problem` gate -> correlates -> writes outcomes, with series groups ordered earliest-window-end-first. Resolution needs a grab whose nested episode is absent or lacks a valid season; it is skipped (one series-episode-list call per group, cached and budget-capped, per-id fallback only for ids missing from that list, also budget-capped) when the grab's own `episodeId`/`seriesId` are already known-bad (the unchanged gate reports those). Out-of-window needing-resolution grabs are dropped silently (debug-only) so request volume and identity-skip counts never move for grabs no pending search could ever claim. A resolved summary is verified (id, seriesId, nested id/seriesId, valid season) before being attached via `grab.model_copy(update={"episode": summary})`; any mismatch is a definitive skip. Any transient failure (network, malformed body, other HTTP error, or a budget-exhausted "never attempted") defers the whole group's writes (mirroring a grab-history fetch failure) unless some row is individually more than 24h past its own window end, in which case only that row escalates (its unverifiable grabs treated as definitive) while sibling rows in the same group still get no write. A circuit breaker opened by any `httpx.TransportError` stops all further episode requests for the rest of the check.

## Task Commits

1. **Task 1: RED - failing real-client-path tests for verified, bounded episode resolution**
   - `921f90d` test(81-11): add failing v5 episode-identity resolution regressions
2. **Task 2: GREEN - implement the client methods and per-check verified resolution**
   - `513cdcb` feat(81-11): resolve v5 grab identity via verified per-check episode lookups

_No separate refactor commit was needed -- the implementation passed full-suite and ruff verification on the first GREEN pass._

## Files Created/Modified

- `triggarr/clients/sonarr.py` -- `get_series_episodes(series_id)` (GET `/api/v3/episode?seriesId=X`, raises `ValueError` on a non-list body, skips non-dict entries) and `get_episode(episode_id)` (GET `/api/v3/episode/{id}`), both single-request with no retry
- `triggarr/tracking.py` -- `_MAX_SERIES_EPISODE_LISTS_PER_CHECK`, `_MAX_EPISODE_ID_LOOKUPS_PER_CHECK`, `_TRANSIENT_ESCALATION_HOURS` constants; `_CheckResolutionState`, `_EpisodeLookupResult`, `_GrabResolution`, `_GroupResolutionResult` dataclasses; `_needs_episode_resolution`, `_eligible_for_resolution_attempt`, `_verify_resolved_summary`, `_get_episode_cached`, `_get_series_episode_map`, `_resolve_grab_episode`, `_resolve_group_identities`, `_split_escalation`, `_log_identity_skip` helpers; `_run_sonarr_tracking_check` reordered (owned-exclusion before resolution before gate), group ordering by earliest window end, per-row escalation/held-row write suppression
- `triggarr/models/arr.py` -- `GrabEvent` docstring updated to describe v5's omission of the nested `episode` object and tracking's resolve-then-`model_copy` pattern (no field changes -- `EpisodeSummary` already had everything needed)
- `tests/test_attribution_client_path.py` -- extended `_SonarrHistoryFake` (series-episode-list + per-id endpoints, override hooks, default-200-empty-list / default-404-per-id semantics), `_list_requests`/`_per_id_requests`/`_shift_records`/`_assert_grab_in_window` helpers, 25 `test_client_path_v5_*` tests
- `tests/test_clients.py` -- 7 `test_sonarr_get_episode_*` / `test_sonarr_get_series_episodes_*` tests

## Decisions Made

See `key-decisions` in the frontmatter. In short: list-level failures are always transient (never definitive) and per-id fallback is attempted only against a successfully-fetched list (never as an automatic N-calls fallback when the list itself fails, to preserve the one-call-per-series request bound); the cap/escalation constants and their rationale are documented inline; a group-wide transient failure with no escalated row discards the whole check's worth of processing for that group rather than partially reporting; and resolution is strictly gated on `isinstance(client, SonarrClient)` so the existing mock-based Sonarr tracking test suite is entirely unaffected.

## Assumption Drift (advisory)

None material. The plan's interfaces section anticipated `GET /api/v3/episode/18 -> seasonNumber: 2`, which the live fixture confirmed exactly (`episodes_v5.json` episode 18: `seriesId: 1, seasonNumber: 2`).

## Deviations from Plan

None -- plan executed exactly as written, including the explicit design choices (list-first resolution, per-id fallback only for list-absent ids, owned-exclusion-before-gate reorder, expired-first group ordering, per-row 24h escalation, circuit breaker). The only judgment calls beyond the plan's literal action text were in the RED-phase test design itself (not deviations from the plan, but choices made while authoring the tests it called for): 5 of the "definitive identity" tests initially passed even against the pre-implementation code (because the old generic `sonarr_identity_problem` gate already reports "missing season" with the same externally-visible outcome for a v5-shaped record with no nested episode at all), so per the TDD fail-fast rule they were strengthened with explicit episode-request-count assertions before the RED commit, so they can only pass once the new resolution code path actually runs.

## Issues Encountered

- During the "transient...heals" scenario test authoring, popping the list-status override without also configuring the per-id fallback's episode data caused the "healthy" check to resolve via an unconfigured per-id 404 (a definitive failure) instead of actually crediting the grab -- fixed by configuring `fake.episodes[<id>]` alongside the test's recovery step, before the GREEN implementation was even restored. Caught during test authoring, not a deviation.

## User Setup Required

None -- no external service configuration required. This plan is code-only (no NAS or sandbox contact at all, per the plan's own scope).

## Next Phase Readiness

- The client/tracking-layer fix for the Sonarr v5 identity gap (found live in Plan 81-07) is implemented and fixture-regression-tested through the real `SonarrClient` -> `GrabEvent` -> `run_tracking_check` path, including the real v5 capture's exact shape (`history_season_pack_v5.json`, `episodes_v5.json` from Plan 81-10).
- **SONARRV5-02 stays open** (per D-13): this plan provides no live evidence. Plan 81-12 is expected to re-run the season-pack and tracking-check live matrix rows against this fix on the v5 sandbox.
- Full suite (1994 tests) and `ruff check triggarr/ tests/` both pass clean at the end of this plan.
- No blockers for Plan 81-12.

### Facts recorded for traceability

- **Design choice (owner review, 2026-10-19):** list-first resolution (`get_series_episodes` once per group per check) with `get_episode` as a per-id fallback only for ids missing from that list -- both hit Sonarr's episode endpoint, but the list form keeps request volume at one call per series regardless of pack size.
- **Cap values and rationale:** `_MAX_SERIES_EPISODE_LISTS_PER_CHECK=50` (one list covers any pack size; 50 series needing resolution in one check is far above normal load), `_MAX_EPISODE_ID_LOOKUPS_PER_CHECK=25` (per-id calls are a rare fallback only), `_TRANSIENT_ESCALATION_HOURS=24` (per-row, timestamp-derived, no new stored state).
- **Expired-first ordering:** series groups are processed in ascending earliest-window-end order so an exhausted per-check budget starves the least urgent group first.
- **Window bound:** a grab needing resolution is dropped silently (never resolved, never counted) if its date falls outside `[earliest pending searched_at, latest pending searched_at + window]` for its group -- bounds both request volume and identity-skip noise for history far outside anything currently pending.
- **Owned-before-gate reorder:** grab-ownership exclusion now happens before resolution (not just before correlation), so a repeat tracking check never re-resolves (and never re-spends a request on) an already-credited episode.
- **Per-row deferral and 24h escalation:** a transient failure anywhere in a series group defers the whole group's writes by default (mirroring a grab-history fetch failure); only a row individually more than 24h past its own window end escalates, crediting nothing for its unverifiable grabs (identity_skipped) but finally letting that one row resolve.
- **Circuit breaker:** any `httpx.TransportError` during an episode request stops all further episode requests (list or per-id, any series group) for the rest of that tracking check.

---
*Phase: 81-correct-sonarr-grab-attribution*
*Completed: 2026-10-19*

## Self-Check: PASSED

All 5 modified files confirmed present on disk (`triggarr/clients/sonarr.py`, `triggarr/tracking.py`, `triggarr/models/arr.py`, `tests/test_attribution_client_path.py`, `tests/test_clients.py`). Both commits (`921f90d`, `513cdcb`) confirmed present in `git log --oneline --all`. Full suite (`uv run pytest tests/ -x -q` -> 1994 passed) and `ruff check triggarr/ tests/` (-> all checks passed) re-run and confirmed immediately before writing this summary. `.planning/ROADMAP.md`, `.planning/STATE.md` and `docs/bm-greptile-codex-blueprint.md` were never staged or modified (confirmed via `git status --short` throughout). No NAS or sandbox contact occurred (confirmed: no `ssh`/NAS-targeting commands were run this plan).
