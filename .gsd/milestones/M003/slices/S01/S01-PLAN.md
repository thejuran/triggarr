# S01: Lidarr Client, Config & State

**Goal:** LidarrClient can interact with Lidarr API v1, and config/state models include `lidarr` as a third app type alongside radarr/sonarr.
**Demo:** Client tests pass for all Lidarr endpoints. Config with `[lidarr]` section loads correctly. State includes lidarr instances.

## Must-Haves

- LidarrClient extending ArrClient with Lidarr v1 API endpoints
- `Settings.lidarr: dict[str, InstanceConfig]` in config model
- `TriggarrState.lidarr: dict[str, AppState]` in state model
- All `("radarr", "sonarr")` tuples updated to include `"lidarr"` across config, state, and related code
- `_lidarr_tags(item)` tag accessor (tags on artist object, like Sonarr's series.tags)
- Tests for client, config, and state

## Proof Level

- This slice proves: contract
- Real runtime required: no (mocked API tests)
- Human/UAT required: no

## Verification

- `uv run pytest tests/ -x -q` — all tests pass including new Lidarr tests
- `uv run ruff check triggarr/ tests/` — lint clean

## Observability / Diagnostics

- Runtime signals: loguru messages from LidarrClient (follows existing pattern)
- Inspection surfaces: none new
- Failure visibility: follows existing error handling patterns
- Redaction constraints: SecretStr for API keys (existing pattern)

## Integration Closure

- Upstream surfaces consumed: `ArrClient` base class, `InstanceConfig`, `TriggarrState`
- New wiring introduced in this slice: LidarrClient class, `lidarr` in config/state models
- What remains before the milestone is truly usable end-to-end: search engine cycle (S02), scheduler + web UI (S03)

## Tasks

- [ ] **T01: Create LidarrClient** `est:30m`
  - Why: Need a client to interact with Lidarr API v1 endpoints
  - Files: `triggarr/clients/lidarr.py`, `triggarr/clients/__init__.py`
  - Do:
    1. Create `LidarrClient(ArrClient)` with `_app_name = "Lidarr"`
    2. `get_wanted_missing()` → `GET /api/v1/wanted/missing` with `includeArtist=true`
    3. `get_wanted_cutoff()` → `GET /api/v1/wanted/cutoff` with `includeArtist=true`
    4. `get_library_count()` → `GET /api/v1/artist` and count artists
    5. `get_grab_history(album_id)` → `GET /api/v1/history` with `albumId` and `eventType=grabbed`
    6. `search_albums(album_ids)` → `POST /api/v1/command` with `{"name": "AlbumSearch", "albumIds": [...]}`
    7. All paths use `/api/v1/` prefix (not v3)
  - Verify: `uv run pytest tests/test_lidarr_client.py -x -q`
  - Done when: all client methods tested with mocked responses

- [ ] **T02: Add lidarr to config and state models** `est:30m`
  - Why: Config and state need to recognize lidarr as a third app type
  - Files: `triggarr/models/config.py`, `triggarr/state.py`, `triggarr/config.py`
  - Do:
    1. Add `lidarr: dict[str, InstanceConfig] = {}` to `Settings`
    2. Update `validate_instances` to include `"lidarr"`
    3. Update `has_enabled_app` and `get_enabled_instances` to include `"lidarr"`
    4. Add `lidarr: dict[str, AppState]` to `TriggarrState`
    5. Update `build_initial_state()` to include `"lidarr"`
    6. Update `_is_flat_state()` and `_migrate_flat_state()` to include `"lidarr"`
    7. Update `load_state()` and `save_state()` to include `"lidarr"`
    8. Update config migration (`detect_and_migrate_v22`) if it has app-type hardcoded lists
    9. Add `_lidarr_tags(item)` to `triggarr/search/engine.py` — extract tags from `item["artist"]["tags"]`
  - Verify: `uv run pytest tests/ -x -q` — all existing + new tests pass
  - Done when: config with `[lidarr]` section loads, state includes lidarr instances, existing tests unbroken

## Files Likely Touched

- `triggarr/clients/lidarr.py` (new)
- `triggarr/clients/__init__.py`
- `triggarr/models/config.py`
- `triggarr/state.py`
- `triggarr/config.py`
- `triggarr/search/engine.py` (tag accessor only)
- `tests/test_lidarr_client.py` (new)
- `tests/test_config.py`
- `tests/test_state.py`
