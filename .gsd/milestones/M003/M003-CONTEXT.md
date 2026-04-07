# M003: Lidarr Support — Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

## Project Description

Triggarr currently triggers automated searches in Radarr (movies) and Sonarr (TV). Users with Lidarr (music) want the same round-robin search, closed-loop tracking, and dashboard visibility for their music libraries.

## Why This Milestone

Lidarr is the third major *arr application and a frequent user request. The codebase already supports multi-instance configs per app type, so adding a third app type follows established patterns. The `("radarr", "sonarr")` tuple appears in ~15 places — this is a cross-cutting change but architecturally straightforward.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Configure one or more Lidarr instances in the TOML config with URL, API key, schedule, and tag filters
- See Lidarr dashboard cards with connection health, queue sizes, position labels, and grab effectiveness stats
- View Lidarr search history with per-instance filtering
- Edit Lidarr instance settings from the web UI

### Entry point / environment

- Entry point: `triggarr.toml` config file + web UI at http://localhost:8484
- Environment: Docker container or local dev
- Live dependencies involved: Lidarr API (HTTP)

## Completion Class

- Contract complete means: all tests pass for Lidarr client, cycle function, config, state, tracking, and routes
- Integration complete means: Lidarr search cycles run against mocked API, dashboard renders Lidarr cards
- Operational complete means: Docker builds, Lidarr instances can be configured and scheduled independently

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- A configured Lidarr instance runs search cycles on schedule, tracking grabs and updating dashboard
- The web UI shows Lidarr cards, history, and settings alongside existing Radarr/Sonarr instances
- Existing Radarr/Sonarr functionality is unaffected (no regressions)

## Risks and Unknowns

- Lidarr API v1 path prefix differs from Radarr/Sonarr v3 — base client may need adjustment
- Lidarr history endpoint shape — need to confirm `artistId` filter and GrabEvent compatibility
- Album-level search granularity — confirm wanted/missing returns albums (not tracks)
- Tags on artists — need tag accessor pattern (like Sonarr's series.tags)

## Existing Codebase / Prior Art

- `triggarr/clients/base.py` — ArrClient base class (shared HTTP, pagination, retry)
- `triggarr/clients/radarr.py` — RadarrClient (movie-level search, closest analog)
- `triggarr/clients/sonarr.py` — SonarrClient (series→season hierarchy, tag-on-series pattern)
- `triggarr/models/config.py` — Settings with `radarr`/`sonarr` dict[str, InstanceConfig]
- `triggarr/state.py` — TriggarrState with per-app-type dict[str, AppState]
- `triggarr/search/engine.py` — run_radarr_cycle, run_sonarr_cycle, filter/tag utilities
- `triggarr/search/scheduler.py` — per-instance APScheduler job creation
- `triggarr/tracking.py` — grab correlation per instance
- `triggarr/web/routes.py` — dashboard, settings, search-now, history routes
- `triggarr/db.py` — SQLite search history with instance_id scoping

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- New capability — no existing requirement IDs; this extends the product to a third app type

## Scope

### In Scope

- LidarrClient with album-level search, wanted/missing, wanted/cutoff, history, tags
- Lidarr in config model, state model, migration (existing configs get empty `[lidarr]`)
- run_lidarr_cycle search engine function with tag filtering
- Scheduler and tracking wiring for Lidarr instances
- Dashboard cards, settings form, history filtering for Lidarr
- Tests for all new code

### Out of Scope / Non-Goals

- Readarr or other *arr apps (future milestone if needed)
- Refactoring existing Radarr/Sonarr code into a more generic pattern (only if needed for Lidarr)
- Track-level search granularity (Lidarr searches at album level)

## Technical Constraints

- Must follow existing patterns: InstanceConfig, per-instance state, round-robin cursors
- Must not break existing Radarr/Sonarr functionality
- Lidarr API uses v1 prefix (not v3)
- No new Python dependencies

## Integration Points

- Lidarr API (HTTP) — album search, wanted lists, history, tags, system status
- SQLite database — search history entries with `app='lidarr'`
- APScheduler — per-instance Lidarr jobs
- Web UI templates — dashboard cards, settings sections, history filter options

## Open Questions

- Does Lidarr's wanted/missing return album objects with artist data embedded? (Need `includeArtist` param?)
- Does Lidarr have a `skip_unreleased` equivalent? (Albums with future release dates)
- What is the exact history endpoint path for per-artist history? (`/api/v1/history/artist`?)
