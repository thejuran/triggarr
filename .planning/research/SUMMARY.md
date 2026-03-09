# Project Research Summary

**Project:** Triggarr v2.3 -- Multi-Instance & Tag Filtering
**Domain:** Search automation daemon -- multi-instance *arr ecosystem integration
**Researched:** 2026-03-09
**Confidence:** HIGH

## Executive Summary

Triggarr v2.3 adds multi-instance support (multiple Radarr/Sonarr servers) and tag-based filtering (search only tagged items) to an existing, well-tested search automation daemon. The good news: zero new dependencies are needed. The entire feature set is achievable by refactoring config, state, database schema, and client management using the existing stack (FastAPI, httpx, Pydantic, APScheduler, aiosqlite). TOML's native `[[array-of-tables]]` syntax handles multi-instance config cleanly, and the *arr tag API (`GET /api/v3/tag`) provides the tag name-to-ID resolution needed for filtering.

The recommended approach is a strict dependency-ordered build: config model first (everything depends on it), then state migration, then client registry with tag resolution, then search engine changes, then database schema, then scheduler/tracking, and finally UI. This order is non-negotiable because each layer depends on the one before it. The config model restructure is the single biggest change -- moving from hardcoded `[radarr]`/`[sonarr]` sections to a dynamic `[[instances]]` list with an `app_type` discriminator. Every other module (state, scheduler, engine, DB, tracking, routes) fans out from this change.

The top risks are: (1) config migration breaking existing v2.2 users on upgrade -- mitigated by auto-detecting old format and converting with a backup; (2) state cursor collision between instances of the same app type -- mitigated by keying state by instance ID instead of app name; (3) tracking cross-contamination where grab detection queries the wrong *arr server -- mitigated by storing instance_id in the database and using it for client lookup. Tag filtering must be client-side (the *arr wanted endpoints do not support server-side tag filtering), and tag IDs must be resolved per-cycle (not cached long-term) because *arr tag IDs are auto-incrementing and unstable across delete/recreate.

## Key Findings

### Recommended Stack

No new libraries. The existing stack handles everything. See `.planning/research/STACK.md` for full details.

**Core technologies (unchanged):**
- **Pydantic + pydantic-settings[toml]:** Config model restructure -- `list[InstanceConfig]` with `app_type` discriminator, tag fields as strings
- **httpx:** One async client per instance, plus new `get_tags()` method on base `ArrClient` for tag resolution
- **APScheduler 3.x:** One interval job per enabled instance, keyed by `f"{instance_id}_search"`
- **aiosqlite:** Schema migration v6 adds `instance_id TEXT` column; existing migration system handles this
- **tomli-w:** Writes back multi-instance config using TOML `[[instances]]` array-of-tables syntax

**Critical version note:** No version changes required. All capabilities come from restructuring how existing libraries are used.

### Expected Features

See `.planning/research/FEATURES.md` for full analysis and competitor comparison.

**Must have (table stakes):**
- Named instances with independent URL, API key, schedule, and batch sizes
- Backward-compatible config parsing (old `[radarr]`/`[sonarr]` format auto-migrates)
- Per-instance state (cursors, connection health) -- no cross-contamination
- Tag-based filtering for missing and cutoff queues (separate tag per queue per instance)
- No-tag-configured = search everything (existing behavior preserved)
- Dashboard showing all instances with per-instance status
- Search history scoped per instance name
- DB migration adding instance_id to search_history and lifetime_stats

**Should have (differentiators):**
- Web UI instance management (add/edit/remove via settings page)
- Tag name autocomplete from *arr API (prevents typos)
- Per-instance effectiveness stats (grab rates per instance)

**Defer (v2.4+):**
- Cross-instance search deduplication (high complexity, marginal value)
- Dynamic instance hot-add without restart (engineering effort not justified)

**Key differentiator:** Tag-based filtering combined with closed-loop grab tracking is unique in the *arr ecosystem. Huntarr searches everything with no filtering. Triggarr lets users scope searches to tagged items only.

### Architecture Approach

The architecture shifts from hardcoded dual-client (one Radarr, one Sonarr) to a dynamic instance registry pattern. See `.planning/research/ARCHITECTURE.md` for full component breakdown and data flow diagrams.

**Major components changing:**
1. **Config model** -- `Settings.instances: list[InstanceConfig]` replaces `Settings.radarr` / `Settings.sonarr`; backward-compat migration layer
2. **State model** -- `TriggarrState.instances: dict[str, AppState]` keyed by slugified instance name; old format auto-migrated
3. **Client registry** -- `app.state.clients: dict[str, ArrClient]` replaces individual client attributes; new `get_tags()` / `resolve_tag_id()` on base class
4. **Search engine** -- `filter_by_tag()` added to pipeline between monitored filter and release filter; cycle functions receive instance_id and per-instance config
5. **Database** -- Migration v6 adds `instance_id` column; `lifetime_stats` gets composite primary key `(app, instance_id)`
6. **Scheduler** -- Dynamic job creation per enabled instance; single shared search_lock serializes all cycles (intentional for indexer courtesy)
7. **Web layer** -- Dashboard renders N instance cards; settings supports N instances; history adds instance filter

**Key pattern: Slugified Instance ID.** User provides a human name ("Radarr 4K"), the app derives a stable slug ("radarr-4k") for internal keying in state, DB, scheduler, and client registry. This survives config reordering but not instance renaming.

### Critical Pitfalls

See `.planning/research/PITFALLS.md` for full analysis with recovery strategies.

1. **Config migration destroys existing setups** -- Auto-detect old `[radarr]` dict format, convert to `[[instances]]` list, back up original file before rewriting. Must preserve raw API key strings (not Pydantic SecretStr objects).
2. **State cursor collision between instances** -- Key state by instance_id, not app type. Two Radarr instances writing to `state["radarr"]` will corrupt each other's cursors. Migration must remap old keys to default instance.
3. **Tracking cross-contamination** -- `_get_client()` dispatches by app name, not instance. With two Radarr instances, tracking queries the wrong server 50% of the time. Store instance_id in DB, pass clients dict to tracking.
4. **Tag ID instability** -- *arr tag IDs are auto-incrementing and change on delete/recreate. Resolve tag name to ID at the start of every cycle, not just at startup. Fail-open (search all) when tag not found, with dashboard warning.
5. **Sonarr tag path asymmetry** -- Sonarr tags are on the series object, not episodes. Filter must use `episode["series"]["tags"]`, not `episode["tags"]`. This asymmetry is a common source of bugs in *arr ecosystem tools.

## Implications for Roadmap

Based on research, suggested phase structure (7 phases):

### Phase 1: Config Model + Migration
**Rationale:** Everything depends on the config model. Cannot change clients, scheduler, engine, or DB without the new config shape. Must be first.
**Delivers:** New `InstanceConfig` model, `[[instances]]` TOML loading/saving, old-format auto-migration with backup, instance_id derivation (slugify), tag field definitions, config validation (unique names per app type).
**Addresses:** Named instances, backward-compatible config, tag config fields.
**Avoids:** Config migration breaking existing users (Pitfall 2).

### Phase 2: State Model + Migration
**Rationale:** Engine and scheduler need the new state shape. State depends on instance IDs from config.
**Delivers:** `TriggarrState.instances` dict keyed by instance_id, old state.json migration, per-instance cursor isolation.
**Addresses:** Independent round-robin cursors per instance.
**Avoids:** State cursor collision (Pitfall 3).

### Phase 3: Client Registry + Tag Resolution
**Rationale:** Engine changes need the client registry. Tag resolution is needed before search filtering.
**Delivers:** `app.state.clients` dict, `get_tags()` / `resolve_tag_id()` on ArrClient base, lifespan creates N clients.
**Addresses:** Per-instance API clients, tag name-to-ID resolution.
**Avoids:** Tag ID instability (Pitfall 4) by resolving per-cycle.

### Phase 4: Search Engine + Tag Filtering
**Rationale:** Core feature. Needs config, state, and client registry in place.
**Delivers:** `filter_by_tag()` function, modified cycle signatures accepting instance_id, tag filtering in pipeline (after monitored, before release filter), per-instance state access in cycles.
**Addresses:** Tag-based filtering for missing and cutoff queues, no-tag = search all.
**Avoids:** Client-side-only filtering (Pitfall 5), Sonarr tag path asymmetry (Pitfall 5 detail).

### Phase 5: Database Schema + Queries
**Rationale:** Can parallel with Phase 4 conceptually, but logically follows engine knowing about instance_id.
**Delivers:** Migration v6 (instance_id column on search_history, lifetime_stats composite key), updated CRUD functions, per-instance history queries.
**Addresses:** Search history scoped per instance, per-instance stats.
**Avoids:** DB losing instance attribution (Pitfall 4).

### Phase 6: Scheduler + Tracking Updates
**Rationale:** Wires engine changes into the running application. Needs phases 3-5.
**Delivers:** Dynamic job creation per instance, updated `make_search_job` closures, tracking with clients dict and instance_id lookup, updated startup sequence (N clients, N jobs, collect all secrets).
**Addresses:** Per-instance schedules, correct tracking correlation.
**Avoids:** Tracking cross-contamination (Pitfall 7), APScheduler duplicate job IDs.

### Phase 7: Web UI Updates
**Rationale:** UI is the integration layer. Needs all backend changes in place.
**Delivers:** Dashboard with N instance cards (grouped by app type), settings page for N instances, history page with instance filter, search-now per instance, partials per instance.
**Addresses:** Dashboard showing all instances, per-instance search-now, visual instance distinction.
**Avoids:** UX pitfalls (cluttered dashboard, ambiguous buttons, mixed history).

### Phase Ordering Rationale

- **Strict dependency chain:** Config (1) -> State (2) -> Clients (3) -> Engine (4) -> DB (5) -> Scheduler (6) -> UI (7). Each layer builds on the previous.
- **Phases 4 and 5 could run in parallel** since they share a dependency on Phase 3 but not on each other. However, sequential is safer for a single developer.
- **Migration phases (1, 2, 5) are front-loaded** because upgrade safety for existing v2.2 users is non-negotiable.
- **UI is last** because it integrates all backend changes and is easier to build when the data model is stable.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (Config):** Needs careful validation of pydantic-settings behavior with TOML `[[array]]` syntax and `list[InstanceConfig]` -- test this early before committing to the approach.
- **Phase 7 (UI):** Multi-instance settings form is the most complex UI change. Tabbed/accordion pattern for N instances needs design thought.

Phases with standard patterns (skip research-phase):
- **Phase 2 (State):** Pure JSON restructuring with known migration pattern.
- **Phase 3 (Clients):** Trivial dict-based registry, well-understood httpx patterns.
- **Phase 4 (Engine):** Tag filtering is simple list comprehension; pipeline position is clear.
- **Phase 5 (DB):** SQLite ALTER TABLE ADD COLUMN is well-documented; existing migration system proven through v1-v5.
- **Phase 6 (Scheduler):** APScheduler dynamic jobs are well-documented; closure pattern already established.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new deps; all capabilities verified against existing library docs and TOML spec |
| Features | HIGH | Competitor analysis (Huntarr, Recyclarr, Notifiarr) confirms feature expectations; *arr tag API verified via Go SDK type definitions and multiple client libraries |
| Architecture | HIGH | Full codebase audit of all 13 source files; every hardcoded assumption identified and migration path designed |
| Pitfalls | HIGH | Pitfalls grounded in specific code locations and confirmed by real issues in other *arr ecosystem tools (syncarr#77, Radarr#7704) |

**Overall confidence:** HIGH

### Gaps to Address

- **Pydantic-settings TOML `[[array]]` parsing:** Confidence is high conceptually, but the exact behavior of pydantic-settings loading a `list[InstanceConfig]` from TOML `[[instances]]` should be validated with a quick spike in Phase 1 before committing to the approach. If it does not work natively, a custom `model_validator` on `Settings` can parse raw TOML first.
- **Config editor rewrite scope:** The current settings form is a flat form for two apps. Multi-instance needs a dynamic list-of-forms with add/remove. The exact htmx pattern (inline editing? tabbed? accordion?) is not researched yet -- address in Phase 7 planning.
- **Per-instance vs global search_lock:** PITFALLS.md recommends per-instance locks for concurrency. ARCHITECTURE.md recommends keeping the single lock for indexer courtesy. Recommendation: **start with single lock** (simpler, safer) and only add per-instance locks if cycle delays become a measured problem with 4+ instances.
- **Live tag API verification:** Tag field presence on wanted/missing responses verified via SDK type definitions, not live API call. Verify against a real Radarr/Sonarr instance during Phase 4 implementation.

## Sources

### Primary (HIGH confidence)
- Full codebase audit of all 13 Triggarr source files (v2.2)
- [golift.io/starr Go SDK](https://pkg.go.dev/golift.io/starr/sonarr) -- Series.Tags as `[]int`, Episode has no tags field
- [SkYNewZ/radarr Go SDK](https://pkg.go.dev/github.com/SkYNewZ/radarr) -- Movie.Tags as `[]int`
- [Syncarr#77](https://github.com/syncarr/syncarr/issues/77) -- tag filtering implementation issues
- [Radarr#7704](https://github.com/Radarr/Radarr/issues/7704) -- wanted endpoint lacks server-side tag filtering
- [TOML spec: array of tables](https://toml.io/en/v1.0.0#array-of-tables)

### Secondary (MEDIUM confidence)
- [Radarr API Docs (Swagger)](https://radarr.video/docs/api/) -- OpenAPI spec
- [Sonarr API Docs](https://sonarr.tv/docs/api/) -- OpenAPI spec
- [Recyclarr configuration docs](https://recyclarr.dev/wiki/yaml/config-reference/) -- multi-instance patterns
- [Huntarr DeepWiki](https://deepwiki.com/plexguide/Huntarr.io) -- competitor feature analysis
- [Notifiarr client configuration](https://notifiarr.wiki/pages/client/configuration/) -- multi-instance patterns
- [pyarr SDK docs](https://docs.totaldebug.uk/pyarr/modules/sonarr.html) -- tag methods
- [ArrAPI documentation](https://arrapi.kometa.wiki/en/latest/radarr.html) -- tag field types

### Tertiary (LOW confidence)
- [Radarr#11146](https://github.com/Radarr/Radarr/issues/11146) -- browser localStorage conflicts (different domain but instructive)
- [Bazarr#404](https://github.com/morpheus65535/bazarr/issues/404) -- multi-instance challenges

---
*Research completed: 2026-03-09*
*Ready for roadmap: yes*
