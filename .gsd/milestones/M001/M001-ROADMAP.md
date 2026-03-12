# M001: Multi-Instance & Tag Filtering

**Vision:** Support multiple Radarr/Sonarr instances with per-instance tag-based search filtering, scoped observability, and version display.

## Success Criteria

- User can define and manage multiple named Radarr/Sonarr instances, each with independent URL, API key, schedule, and batch sizes
- Existing v2.2 configs auto-migrate to multi-instance format on upgrade without data loss
- Tag-based filtering narrows search scope per instance per queue, with no-tag defaulting to search-all
- Each instance runs on its own schedule with independent round-robin cursors
- Dashboard shows per-instance status cards, effectiveness stats, and version info
- Search history is scoped per instance with filtering

## Key Risks / Unknowns

- pydantic-settings behavior with TOML `[[array]]` syntax and `list[InstanceConfig]` — needs validation early
- Multi-instance settings form UI pattern (tabbed/accordion) — design thought needed for Phase 39
- APScheduler per-instance job management — dynamic add/remove without restart

## Proof Strategy

- pydantic-settings TOML parsing → retired in S01 by building the real config model with tests
- APScheduler dynamic jobs → retire in S06 by wiring real per-instance schedulers
- UI pattern → retire in S07 by building the multi-instance settings form

## Verification Classes

- Contract verification: pytest test suite (371+ tests), ruff lint
- Integration verification: cycle function tests with mocked *arr APIs
- Operational verification: Docker build, config migration on upgrade
- UAT / human verification: multi-instance dashboard visual check in browser

## Milestone Definition of Done

This milestone is complete only when all are true:

- All 7 slices delivered and verified
- Multiple instances can be configured, scheduled, and monitored independently
- Tag filtering works end-to-end for both Radarr and Sonarr
- Search history is instance-scoped with per-instance filtering
- Dashboard shows per-instance health, stats, and version info
- Existing v2.2 users upgrade seamlessly with auto-migration
- All tests pass, lint clean, Docker builds successfully

## Requirement Coverage

- Covers: INST-01, INST-02, INST-03, INST-04, INST-05, INST-06, INST-07, TAG-01, TAG-02, TAG-03, TAG-04, TAG-05, TAG-06, OBS-01, OBS-02, OBS-03, VER-01, VER-02
- Partially covers: none
- Leaves for later: DEFER-01, DEFER-02
- Orphan risks: none

## Slices

- [x] **S01: Config Model & Migration** `risk:high` `depends:[]`
  > After this: Multiple named instances can be defined in TOML config, and v2.2 configs auto-migrate on startup. Proven by 42 config tests.
- [x] **S02: State Model & Cursor Isolation** `risk:high` `depends:[S01]`
  > After this: Each instance has independent round-robin cursors that persist across restarts. Proven by per-instance state tests and engine/scheduler wiring.
- [x] **S03: Client Registry & Tag Resolution** `risk:medium` `depends:[S01]`
  > After this: Tag names are resolved to IDs via *arr API. Proven by get_tags() and resolve_tag_id() tests.
- [x] **S04: Search Engine Tag Filtering** `risk:medium` `depends:[S02,S03]`
  > After this: Search cycles filter items by configured tags. Proven by 9 integration tests in cycle functions.
- [x] **S05: Database Schema & Instance Scoping** `risk:medium` `depends:[S01]`
  > After this: Search history entries include instance_id, stats are per-instance, history page can filter by instance.
- [ ] **S06: Scheduler & Tracking Wiring** `risk:high` `depends:[S03,S04,S05]`
  > After this: Each enabled instance runs on its own APScheduler job, grab tracking queries the correct instance, enable/disable takes effect without restart.
- [ ] **S07: Web UI Integration** `risk:high` `depends:[S06]`
  > After this: Users can manage instances, view per-instance status, configure tag filters with autocomplete, and see version info — all from the web UI.

## Boundary Map

### S01 → S02

Produces:
- `InstanceConfig` model with per-instance URL, API key, schedule, and batch sizes
- `Settings` with `dict[str, InstanceConfig]` for radarr/sonarr
- `detect_and_migrate_v22()` for seamless upgrade
- `_atomic_toml_write()` helper for safe config writes

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- `InstanceConfig` with `missing_tag` and `cutoff_tag` string fields

Consumes:
- nothing (first slice)

### S03 → S04

Produces:
- `Tag` model and `ArrClient.get_tags()` method
- `resolve_tag_id(tag_name, tags) -> Optional[int]` pure function

Consumes:
- `InstanceConfig` tag fields from S01

### S02 + S03 + S04 → S06

Produces:
- Per-instance state cursors (S02)
- Client registry with get_tags() (S03)
- Tag-filtered cycle functions (S04)

Consumes:
- All of the above

### S01 → S05

Produces:
- Instance names from config model

Consumes:
- `Settings` with instance IDs

### S06 → S07

Produces:
- Per-instance APScheduler jobs
- Per-instance tracking correlation
- Instance-scoped DB queries

Consumes:
- Everything from S01–S06
