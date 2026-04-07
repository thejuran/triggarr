# M003: Lidarr Support

**Vision:** Triggarr manages automated music searches in Lidarr alongside movies (Radarr) and TV (Sonarr), with the same round-robin scheduling, closed-loop tracking, tag filtering, and dashboard visibility.

## Success Criteria

- Lidarr instances can be configured in TOML with URL, API key, schedule, batch sizes, and tag filters
- Search cycles run on schedule: fetch wanted/missing and wanted/cutoff albums, search in batches with round-robin cursors
- Grab tracking correlates Lidarr history events to search entries
- Dashboard shows per-instance Lidarr cards with health, queue sizes, and effectiveness stats
- Search history includes Lidarr entries with per-instance filtering
- Settings UI allows adding/editing/removing Lidarr instances
- Existing Radarr/Sonarr functionality unchanged (no regressions)

## Key Risks / Unknowns

- Lidarr API v1 path prefix vs v3 — base client hardcodes nothing, but cycle function needs correct paths
- Lidarr history endpoint shape — need to confirm GrabEvent model compatibility
- Wanted/missing response shape — does it include artist data for tag filtering, or need `includeArtist`?

## Proof Strategy

- API v1 paths → retire in S01 by building real LidarrClient with tests against mocked responses
- History/GrabEvent compat → retire in S02 by testing grab correlation with Lidarr history fixtures
- Wanted response shape → retire in S01 by examining Lidarr API docs and testing with fixtures

## Verification Classes

- Contract verification: pytest test suite covering client, config, state, cycle, tracking, routes
- Integration verification: search cycle tests with mocked Lidarr API
- Operational verification: Docker build, full app startup with Lidarr config
- UAT / human verification: dashboard with Lidarr cards visible in browser

## Milestone Definition of Done

This milestone is complete only when all are true:

- All 3 slices delivered and verified
- Lidarr instances configurable, schedulable, and visible in dashboard
- Tag filtering works for Lidarr (tags on artists)
- Search history is instance-scoped for Lidarr
- All existing Radarr/Sonarr tests still pass
- Docker builds successfully

## Requirement Coverage

- Covers: new Lidarr capability (no prior requirement IDs)
- Partially covers: none
- Leaves for later: Readarr, other *arr apps
- Orphan risks: none

## Slices

- [x] **S01: Lidarr Client, Config & State** `risk:high` `depends:[]`
  > After this: LidarrClient can fetch wanted/missing, wanted/cutoff, tags, history, and trigger album searches. Config and state models include `lidarr` alongside radarr/sonarr. Proven by client + config + state tests.
- [x] **S02: Search Engine & Tracking** `risk:medium` `depends:[S01]`
  > After this: `run_lidarr_cycle` executes album-level search with round-robin cursors, tag filtering, and grab tracking. Proven by cycle function tests and tracking correlation tests.
- [x] **S03: Scheduler & Web UI** `risk:medium` `depends:[S02]`
  > After this: Lidarr instances run on APScheduler jobs, dashboard shows Lidarr cards, settings form supports Lidarr, search history filters by Lidarr. Proven by scheduler tests, route tests, and browser verification.

## Boundary Map

### S01 → S02

Produces:
- `LidarrClient` with `get_wanted_missing()`, `get_wanted_cutoff()`, `get_tags()`, `get_grab_history(artist_id)`, `search_albums(album_ids)`, `get_library_count()`
- `Settings.lidarr: dict[str, InstanceConfig]` in config model
- `TriggarrState.lidarr: dict[str, AppState]` in state model
- `_lidarr_tags(item)` tag accessor function (tags on artist object)

Consumes:
- nothing (first slice)

### S02 → S03

Produces:
- `run_lidarr_cycle()` async function matching run_radarr_cycle signature
- Lidarr tracking integration in `check_for_grabs()`

Consumes:
- LidarrClient, config, state from S01

### S03

Produces:
- Lidarr APScheduler jobs via existing per-instance scheduler
- Dashboard cards, settings form, history filtering for Lidarr in web routes + templates

Consumes:
- Everything from S01 + S02
