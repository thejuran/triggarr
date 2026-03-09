# Feature Research: Multi-Instance & Tag Filtering

**Domain:** *arr ecosystem search automation (multi-instance extension)
**Researched:** 2026-03-09
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist once "multi-instance support" is advertised. Missing these = product feels broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Named instances with independent URL/API key | Every multi-instance tool (Recyclarr, Notifiarr, Huntarr) uses named instances. Users name them by purpose: "radarr-4k", "sonarr-anime". | MEDIUM | Config model changes from single `[radarr]`/`[sonarr]` sections to named sub-tables like `[radarr.NAME]`. Recyclarr uses named keys under `radarr:` YAML; Notifiarr uses numbered `[[radarr]]` blocks. |
| Per-instance search schedule and batch sizes | Users run different cadences for different instances (4K = slower, anime = faster). Huntarr supports independent schedules and caps per instance. | LOW | Already have `search_interval`, `search_missing_count`, `search_cutoff_count` per ArrConfig -- just replicate per instance. |
| Per-instance enable/disable toggle | Users temporarily disable an instance without removing config. Already exists for single-instance. | LOW | Already implemented in `ArrConfig.enabled`. |
| Independent round-robin cursors per instance | Each instance manages its own library; cursors must not cross. | MEDIUM | State model must change from `state["radarr"]` to `state["radarr"]["instance_name"]`. Existing state migration needed. |
| Dashboard shows all instances with per-instance status | Users need to see which instances are connected, last-run times, queue sizes. | MEDIUM | Dashboard cards must iterate over instances. htmx polling already handles status -- just need to template N cards instead of 2. |
| Search history scoped per instance | When filtering history, users want to see "radarr-4k" vs "radarr-hd" separately, not just "Radarr". | LOW | DB `app` column currently stores "Radarr"/"Sonarr". Change to store instance name (e.g. "radarr-4k"). Existing filter UI toggle pattern works. |
| Backward-compatible single-instance config | Users upgrading from v2.2 must not need to rewrite their config. Old `[radarr]` section must still work. | MEDIUM | Detect old format and treat it as a single unnamed instance. Critical for upgrade path. |
| Tag-based filtering for missing queue | Core requirement. Users tag movies/shows in Radarr/Sonarr and only search items with matching tag. Common pattern: "triggarr-missing" tag. | MEDIUM | Radarr/Sonarr API returns `tags: [int]` on each item in wanted/missing. Triggarr fetches `/api/v3/tag` to resolve tag names to IDs, then filters locally after fetch. |
| Tag-based filtering for cutoff queue | Same as missing but for upgrade searches. Separate tag config (e.g. "triggarr-upgrade") because users may want different policies. | LOW | Same mechanism as missing tag filter, applied to cutoff items. |
| Default = search everything when no tag configured | Users who don't care about tags should not be affected. Empty tag config = current behavior. | LOW | Filter function is a no-op when tag list is empty. |

### Differentiators (Competitive Advantage)

Features that set Triggarr apart from Huntarr and similar tools. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Web UI instance management (add/edit/remove) | Huntarr has a web UI for instance management. Triggarr already has a config editor -- extending it for multi-instance is natural. | HIGH | Current config editor is a flat form. Multi-instance needs a list-of-forms pattern with add/remove. TOML serialization with comments is already solved. |
| Tag name autocomplete from *arr API | When configuring tag filters, show available tags fetched from the instance. Prevents typos and invalid tag names. | MEDIUM | Fetch `/api/v3/tag` and populate a dropdown/datalist. Requires the instance to be connected first. |
| Per-instance effectiveness stats | Track grab rates separately for each instance. "My 4K instance finds 40% of searches, HD finds 70%." | LOW | Already track stats per `app` column. Changing to per-instance-name gives this for free. |
| Cross-instance search deduplication | If the same movie exists in radarr-hd and radarr-4k, don't search both in the same cycle (indexer courtesy). | HIGH | Requires cross-instance item correlation by TMDB/TVDB ID. Marginal value since indexers handle dedup. |
| Instance health summary card | Single dashboard card showing "3/4 instances connected" with quick expand to see which is down. | LOW | Aggregate view over per-instance state. Nice UX touch. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems or violate Triggarr's philosophy.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Auto-discover *arr instances via network scan | "Just find my instances automatically" | SSRF risk, unreliable on different network topologies, violates zero-credential-exposure principle. Huntarr doesn't do this either. | Manual config with clear docs. |
| Centralized tag management (create/assign tags in *arr from Triggarr) | "Let me manage tags from one place" | Write operations to *arr API expand attack surface. Triggarr is read+search-only by design. Tags should be managed in the *arr UI where users already work. | Read-only tag fetching for filter config. |
| Shared schedule across all instances of same type | "All my Radarr instances should search at the same time" | Defeats the purpose of per-instance config. Simultaneous searches hammer indexers. | Independent schedules with offset defaults. |
| Dynamic instance addition without restart | "Hot-add an instance while running" | APScheduler job management during runtime is error-prone. Config reload complexity. Current pattern: edit config, restart. | Restart required for config changes (current behavior). |
| Priority ordering between instances | "Search 4K instance first, then HD" | Adds scheduling complexity. Round-robin already ensures fairness. Independent schedules handle different cadences. | Independent per-instance schedules. |
| Tag-based exclusion (search everything EXCEPT items with tag) | "Skip items tagged 'no-search'" | Inverse logic is confusing. Inclusive filtering is clearer: "only search items with this tag." | Include-only tag filtering. |
| Webhook receiver for instance registration | "My *arr instances should register with Triggarr" | Adds network listener, increases attack surface, requires *arr-side configuration. | Pull-based config only. |

## Feature Dependencies

```
[Multi-instance config model]
    |
    +--requires--> [Per-instance state management]
    |                   |
    |                   +--requires--> [State migration from v2.2 format]
    |
    +--requires--> [Per-instance scheduler jobs]
    |
    +--enables--> [Per-instance dashboard cards]
    |                 |
    |                 +--enables--> [Instance health summary]
    |
    +--enables--> [Per-instance search history]
    |
    +--enables--> [Tag-based filtering]
                      |
                      +--requires--> [Tag resolution (name -> ID via API)]
                      |
                      +--enables--> [Tag name autocomplete in UI]
                      |
                      +--enables--> [Per-instance effectiveness stats]

[Backward-compatible config parsing]
    +--required-by--> [Multi-instance config model]

[Web UI instance management]
    +--requires--> [Multi-instance config model]
    +--requires--> [TOML serialization for instance arrays]
```

### Dependency Notes

- **Multi-instance config model requires per-instance state management:** Each instance needs its own cursors, connection health, and timing state. Without this, instances would fight over shared cursors.
- **Tag-based filtering requires tag resolution:** Radarr/Sonarr items have `tags: [1, 3, 7]` (integer IDs). Users configure by name ("triggarr-missing"). Must call `/api/v3/tag` to build a name-to-ID mapping at startup/cycle start.
- **Backward-compatible config parsing required by multi-instance config:** If old `[radarr]` config breaks on upgrade, users will be locked out. Must detect and handle gracefully.
- **Web UI instance management requires TOML serialization for instance arrays:** Current config editor writes a flat TOML. Multi-instance needs `[radarr.NAME]` sub-table syntax.

## MVP Definition (v2.3 Scope)

### Must Have

- [ ] Multi-instance config model with named instances -- core architectural change
- [ ] Backward-compatible config parsing (old single-instance format still works)
- [ ] Per-instance state (cursors, connection health, timing)
- [ ] State migration from v2.2 single-instance format
- [ ] Per-instance APScheduler jobs with independent schedules
- [ ] Tag-based filtering for missing queue (configurable tag name per instance)
- [ ] Tag-based filtering for cutoff queue (separate configurable tag name per instance)
- [ ] No-tag = search everything (default behavior unchanged)
- [ ] Tag name-to-ID resolution via `/api/v3/tag` endpoint
- [ ] Dashboard showing all instances
- [ ] Search history scoped per instance name
- [ ] DB migration to add `instance_name` column to search_history and lifetime_stats

### Add After Core Works

- [ ] Web UI instance management (add/edit/remove instances) -- current TOML editing is sufficient initially
- [ ] Tag name autocomplete from *arr API -- nice UX, not blocking
- [ ] Instance health summary card -- aggregate view

### Defer

- [ ] Cross-instance search deduplication -- marginal value, high complexity
- [ ] Dynamic instance hot-add without restart -- engineering effort not justified

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Multi-instance config model | HIGH | HIGH | P1 |
| Backward-compatible config parsing | HIGH | MEDIUM | P1 |
| Per-instance state and cursors | HIGH | MEDIUM | P1 |
| Per-instance scheduler jobs | HIGH | MEDIUM | P1 |
| Tag filtering (missing queue) | HIGH | MEDIUM | P1 |
| Tag filtering (cutoff queue) | MEDIUM | LOW | P1 |
| Tag name-to-ID resolution | HIGH | LOW | P1 |
| Dashboard per-instance cards | HIGH | MEDIUM | P1 |
| Search history per instance | MEDIUM | LOW | P1 |
| State migration (v2.2 upgrade) | HIGH | MEDIUM | P1 |
| DB schema migration (instance_name) | HIGH | MEDIUM | P1 |
| Web UI instance management | MEDIUM | HIGH | P2 |
| Tag autocomplete in UI | LOW | MEDIUM | P2 |
| Instance health summary | LOW | LOW | P3 |
| Cross-instance dedup | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for v2.3 launch
- P2: Should have, add if time permits
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Huntarr | Recyclarr | Notifiarr | Triggarr v2.3 Plan |
|---------|---------|-----------|-----------|-------------------|
| Multi-instance | Yes, web UI add/remove | Yes, YAML named instances | Yes, numbered env vars or `[[app]]` blocks | TOML named sub-tables with backward compat |
| Instance naming | Implicit (by order or URL) | Explicit names under `radarr:` key | Numbered (1, 2, 3...) | Explicit names: `[radarr.my-4k]` |
| Per-instance schedule | Yes, independent | N/A (sync tool, not scheduler) | N/A (notification tool) | Yes, independent per instance |
| Tag-based filtering | No (searches all items) | N/A (syncs profiles, not searches) | N/A | Yes, per-instance tag filter for missing and cutoff |
| Closed-loop tracking | No | N/A | Notifications only | Yes (existing), scoped per instance |
| Config format | JSON via web UI | YAML with secrets file | Config file or env vars | TOML with backward compat |
| Indexer rate protection | Hourly caps | N/A | N/A | Round-robin + batch sizing + hard max |

**Key differentiator for Triggarr:** Tag-based filtering combined with closed-loop grab tracking is unique in this space. Huntarr searches everything in each instance with no filtering capability. Triggarr lets users scope searches to tagged items only, which is valuable for large libraries where only a subset should be actively searched.

## *arr Ecosystem Tag Patterns

### How Tags Work in Radarr/Sonarr

Tags are simple label objects stored in the *arr database:
- **API endpoint:** `GET /api/v3/tag` returns all tags as `[{"id": 1, "label": "triggarr-missing"}, ...]`
- **Item association:** Each movie/series object has a `tags: [1, 3, 7]` field containing integer tag IDs
- **Wanted/missing response:** Items returned by `/api/v3/wanted/missing` include the `tags` array
- **Tags are instance-scoped:** Each Radarr/Sonarr instance has its own tag namespace
- **Tag creation:** Tags are created in the *arr UI under Settings > Tags. Triggarr should NOT create tags.

### How Ecosystem Tools Use Tags

- **Recyclarr:** Uses tags to scope quality profile syncs to specific media
- **Kometa/PMM:** Uses tags to control collection membership and metadata operations
- **Maintainerr:** Creates tags (e.g. "Maintainerr") to mark managed content for cleanup rules
- **Overseerr/Jellyseerr:** Can apply tags when adding media to *arr instances
- **Common user pattern:** Tag media by source/purpose: "overseerr", "sync", "4k-only", etc.

### Recommended Tag Filter Implementation

1. User creates tag(s) in Radarr/Sonarr UI (e.g. "triggarr-missing", "triggarr-upgrade")
2. User configures tag name in Triggarr instance config: `missing_tag = "triggarr-missing"`
3. At cycle start, Triggarr calls `GET /api/v3/tag` to resolve name to ID
4. After fetching wanted/missing items, filter to only items where `tags` array contains the resolved tag ID
5. Cache tag-ID mapping per instance (refresh on each cycle to handle tag renames)
6. If configured tag name doesn't exist in the *arr instance, log a warning and skip all searches for that queue (strict behavior -- don't silently search everything when user intended filtering)

### Important: Tags on Movies vs Series

- **Radarr:** Tags are on the **movie** object directly. The `tags` field appears on items from `/api/v3/wanted/missing`.
- **Sonarr:** Tags are on the **series** object, NOT on individual episodes. The `/api/v3/wanted/missing` endpoint returns **episodes**, each with an embedded `series` object. The tag filtering must check `episode["series"]["tags"]` not `episode["tags"]`.
- **This asymmetry is critical** and a common source of bugs in *arr ecosystem tools.

### User Workflows for Multi-Instance

Common multi-instance setups in the *arr community:
1. **Quality split:** radarr-hd (1080p) + radarr-4k (2160p) for same library. Most common pattern. Users want both qualities of the same content.
2. **Content split:** sonarr-tv + sonarr-anime with different profiles and indexers. Each instance has completely different content.
3. **User split:** radarr-family (clean content) + radarr-personal (everything). Less common but exists.

Users expect each instance to be independently configurable with no cross-contamination. The typical workflow:
- Add instance to tool config (URL + API key + name)
- Configure per-instance settings (schedule, batch size, tags)
- Each instance operates independently
- Dashboard shows all instances at once

## Sources

- [Recyclarr configuration docs](https://recyclarr.dev/wiki/yaml/config-reference/)
- [Recyclarr basic setup](https://recyclarr.dev/wiki/yaml/config-reference/basic/)
- [Notifiarr client configuration](https://notifiarr.wiki/pages/client/configuration/)
- [Huntarr.io DeepWiki](https://deepwiki.com/plexguide/Huntarr.io)
- [Huntarr Radarr docs](https://plexguide.github.io/Huntarr.io/apps/radarr.html)
- [Radarr API docs](https://radarr.video/docs/api/)
- [Sonarr API docs](https://sonarr.tv/docs/api/)
- [ArrAPI documentation (Kometa)](https://arrapi.kometa.wiki/)
- [Overseerr multi-instance issue](https://github.com/sct/overseerr/issues/3615)
- [Using tags in Sonarr/Radarr for selective sync](https://charlesthomas.dev/blog/using-tags-in-sonarr-and-radarr-to-selectively-sync-media-2025-04-19/)

---
*Feature research for: Triggarr v2.3 multi-instance & tag filtering*
*Researched: 2026-03-09*
