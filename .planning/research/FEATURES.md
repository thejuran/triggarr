# Feature Research: v2.0 Closed-Loop Download Tracking

**Domain:** *arr search automation tool -- download verification and lifetime stats
**Researched:** 2026-02-24
**Confidence:** HIGH for API mechanics (verified against Radarr/Sonarr source code + Go/Python SDK docs + pyarr docs); MEDIUM for UX patterns (informed by ecosystem analysis, no canonical reference for "search effectiveness" dashboards)

## Context

Fetcharr v1.2 is fire-and-forget: it triggers searches in Radarr/Sonarr and records "searched" or "failed" outcomes. v2.0 closes the loop by polling *arr history APIs to detect whether triggered searches actually resulted in grabs, then displays per-item and aggregate effectiveness metrics on the dashboard.

This research focuses exclusively on the NEW v2.0 features. v1.x table stakes (search triggering, round-robin, config editor, search history) are already shipped and documented in the v1.0 research.

---

## Table Stakes (v2.0 Scope)

Features that make closed-loop tracking feel complete. Missing any of these = the feature feels half-built.

| Feature | Why Expected | Complexity | Dependencies |
|---------|--------------|------------|--------------|
| Poll Radarr history for grab events after search | Without this, "closed-loop" is meaningless -- users need to see that searches found something | MEDIUM | Radarr client + existing search history DB |
| Poll Sonarr history for grab events after search | Symmetry with Radarr -- both apps must be tracked | MEDIUM | Sonarr client + existing search history DB |
| Correlate grabs to fetcharr-triggered searches | Must distinguish fetcharr-triggered grabs from organic Radarr/Sonarr activity (RSS grabs, manual searches) | HIGH | Timestamp-windowed queries + item ID matching |
| Update search history entries with grabbed outcome | Users need to see which "searched" entries resolved to actual downloads | LOW | DB schema migration to support outcome updates |
| "Grabbed" badge on search history entries | Visual confirmation that a search produced a result | LOW | Existing outcome badge system (searched/failed badges already exist) |
| "Partial" badge for Sonarr season searches | Season search may grab some but not all missing episodes -- users need to know | MEDIUM | Sonarr episode-level history analysis per season |
| "Unresolved" state for searches that found nothing | Implicit state: searched entries that never get updated to grabbed/partial within the tracking window | LOW | Timeout-based resolution (configurable window) |
| Aggregate search effectiveness on dashboard | "X of Y searches resulted in grabs" -- the headline metric for whether fetcharr is working | LOW | COUNT query on search_history grouped by outcome |
| Lifetime stats: movies found, movies updated | Radarr-specific counters: "found" = missing item grabbed, "updated" = cutoff item grabbed | LOW | Aggregation queries on tracked grab events |
| Lifetime stats: episodes found, episodes updated | Sonarr-specific counters: same distinction as Radarr | LOW | Same pattern as Radarr stats |
| Lifetime stats count only fetcharr-triggered grabs | Must not inflate stats with organic *arr activity | LOW | Already enforced by the correlation logic |

## Differentiators (v2.0 Scope)

Features that go beyond "it works" to "it works well." Not expected, but valued.

| Feature | Value Proposition | Complexity | Dependencies |
|---------|-------------------|------------|--------------|
| Configurable tracking window | Let users control how long to wait for grabs after a search (default: ~60 min). Different indexers/download clients have different speeds | LOW | Config setting, used in polling scheduler |
| Configurable poll interval for history checks | Separate from search interval -- polling history every 5 min is reasonable even if searches run every 30 min | LOW | Config setting for tracking poll frequency |
| Per-app effectiveness breakdown | "Radarr: 72% grab rate, Sonarr: 45% grab rate" helps users tune their setup | LOW | Group-by-app aggregation on existing data |
| Grab source metadata (quality, indexer) | Show what quality was grabbed and from which indexer -- helps users understand their profile effectiveness | MEDIUM | Parse the `data` field from history records (contains indexer, quality, size) |
| Time-to-grab metric | "Average time from search to grab: 12 min" -- helps users understand download pipeline speed | LOW | Timestamp arithmetic between search entry and grab detection |
| Dashboard sparkline or mini-chart for grab rate trend | Visual trend of effectiveness over time (last 7 days) | MEDIUM | Time-bucketed aggregation + minimal JS chart (or htmx-compatible SVG) |

## Anti-Features (v2.0 Scope)

Features to explicitly NOT build for download tracking.

| Anti-Feature | Why Tempting | Why Problematic | What to Do Instead |
|--------------|-------------|-----------------|-------------------|
| Download client integration (qBit/SAB polling) | "Track actual download progress" | Massively expands scope: new credentials, new APIs, new failure modes. The *arr apps already manage download clients. Fetcharr should only ask *arr "did you grab this?" not track the actual download pipeline. | Poll *arr history only. The "grabbed" event in history is sufficient proof. |
| Webhook receiver for *arr grab notifications | "Real-time grab detection instead of polling" | Requires fetcharr to expose a callback endpoint, which means *arr must be configured to POST to fetcharr. Adds bidirectional coupling, network config complexity, and a new attack surface (unauthenticated webhook ingestion). | Poll-based approach is simpler, requires zero *arr configuration changes, and runs on the same timer loop already used for searches. |
| Full import tracking (downloadFolderImported) | "Track when the file actually arrives in the library" | Two-phase tracking (grab + import) adds significant complexity for marginal user value. Users care about "did my search find something?" not "did qBittorrent finish downloading it?" The latter is visible in *arr's own Activity tab. | Track grabs only. Import is *arr's concern. If needed later, it is a natural extension of the grab tracking table. |
| Per-indexer effectiveness stats | "Which indexer grabs the most?" | Requires parsing the indexer field from history data and maintaining per-indexer aggregations. This is Prowlarr's job. | Show indexer name in grab detail metadata (differentiator above) but do not aggregate per-indexer stats. |
| Automated re-search of unresolved items | "If a search didn't grab, try again" | The round-robin already handles this -- the item stays in the wanted list and will be searched again on the next pass. Adding explicit retry logic creates duplicate search risk and indexer abuse. | Trust the round-robin. Unresolved items will naturally be re-searched. |
| Historical backfill of pre-fetcharr grabs | "Show lifetime stats including grabs from before fetcharr was installed" | Impossible to attribute grabs to fetcharr if fetcharr wasn't running when they happened. Mixing organic grabs with triggered grabs defeats the purpose of the metric. | Start counting from first fetcharr-triggered search. Document this clearly. |

## Feature Dependencies (v2.0)

```
[Existing: search_history table with outcome column]
    required by --> [Grab tracking: update outcome to "grabbed"/"partial"]

[Existing: RadarrClient + SonarrClient]
    required by --> [New: get_movie_history() method on RadarrClient]
    required by --> [New: get_series_history() / get_history_since() on SonarrClient]

[New: history polling scheduler (separate from search scheduler)]
    required by --> [Correlate grabs to fetcharr searches]
    required by --> [Aggregate stats calculation]

[New: grab correlation logic]
    required by --> [Update search_history outcome to grabbed/partial]
    required by --> [Lifetime stats counters]
    required by --> [Dashboard effectiveness display]

[New: search_history schema changes]
    - Add: item_id (INT) -- Radarr movieId or Sonarr seriesId for correlation
    - Add: season_number (INT, nullable) -- for Sonarr season-level correlation
    - Add: tracked_until (TEXT, nullable) -- when to stop polling for this entry
    required by --> [Grab correlation logic]

[New: lifetime_stats table or aggregation queries]
    required by --> [Dashboard stats cards]

[Existing: dashboard htmx polling]
    required by --> [Stats cards display]
    required by --> [Effectiveness percentage display]
```

### Critical Dependency Chain

The most important dependency is **storing item IDs at search time**. Currently, `insert_search_entry()` stores `app`, `queue_type`, `item_name`, `outcome`, and `detail` -- but NOT the Radarr `movieId` or Sonarr `seriesId`/`seasonNumber`. Without these IDs, there is no way to correlate history events back to specific searches.

**This schema migration must happen first**, before any tracking logic can be built.

---

## How *arr History APIs Work (Research Findings)

### Radarr History API

**Endpoint:** `GET /api/v3/history/movie?movieId={id}&eventType=grabbed`

**HistoryResource fields** (HIGH confidence -- verified from Radarr source + Go SDK + pyarr):

```
id              INT       -- history record ID
movieId         INT       -- the movie this event is about
sourceTitle     STRING    -- release name that was grabbed
quality         OBJECT    -- quality profile of the grabbed release
qualityCutoffNotMet  BOOL -- whether this grab meets the cutoff
date            DATETIME  -- when the event occurred (ISO 8601)
eventType       STRING    -- one of the enum values below
downloadId      STRING    -- correlates grab to download client entry
data            OBJECT    -- extra metadata (indexer, size, protocol, etc.)
movie           OBJECT    -- full movie resource (if includeMovie=true)
```

**MovieHistoryEventType enum values** (HIGH confidence -- from pyarr docs):
- `unknown` (0)
- `grabbed` (1)
- `downloadFolderImported` (2)
- `downloadFailed` (3)
- `movieFileDeleted` (4)
- `movieFolderImported` (5)
- `movieFileRenamed` (6)
- `downloadIgnored` (7)

**Key endpoint:** `/api/v3/history/movie?movieId={id}&eventType=grabbed` returns all grab events for a specific movie. This is the primary endpoint for correlation.

**Alternative:** `/api/v3/history/since?date={iso8601}` returns all history events since a given date. Useful for batch polling but returns ALL event types for ALL movies -- requires client-side filtering.

### Sonarr History API

**Endpoint:** `GET /api/v3/history/series?seriesId={id}&eventType=1`

**HistoryRecord fields** (HIGH confidence -- verified from Sonarr source code EpisodeHistory.cs):

```
id                    INT       -- history record ID
episodeId             INT       -- specific episode this event is about
seriesId              INT       -- the series this event is about
sourceTitle           STRING    -- release name that was grabbed
quality               OBJECT    -- quality profile of the grabbed release
qualityCutoffNotMet   BOOL     -- whether this grab meets the cutoff
languageCutoffNotMet  BOOL     -- language cutoff check (v4+)
date                  DATETIME  -- when the event occurred (ISO 8601)
eventType             ENUM      -- one of the enum values below
downloadId            STRING    -- correlates grab to download client entry
data                  MAP       -- extra metadata (indexer, size, protocol, etc.)
episode               OBJECT    -- full episode resource (if includeEpisode=true)
series                OBJECT    -- full series resource (if includeSeries=true)
language              OBJECT    -- language info
```

**EpisodeHistoryEventType enum values** (HIGH confidence -- from Sonarr source code):
- `Unknown` = 0
- `Grabbed` = 1
- `SeriesFolderImported` = 2
- `DownloadFolderImported` = 3
- `DownloadFailed` = 4
- `EpisodeFileDeleted` = 5
- `EpisodeFileRenamed` = 6
- `DownloadIgnored` = 7

**Key endpoint:** `/api/v3/history/series?seriesId={id}&eventType=1&includeSeries=true&includeEpisode=true` returns grab events for a specific series. The `eventType` parameter uses the numeric enum value (1 = Grabbed).

**Sonarr nuance:** The `/history/series` endpoint's `includeSeries` and `includeEpisode` parameters were broken in older versions but fixed (GitHub issue #4727, closed as completed).

### Correlation Strategy

The *arr APIs do NOT provide a way to attribute a grab to a specific command invocation. The search command (MoviesSearch, SeasonSearch) is fire-and-forget -- it returns a command ID, but that command ID is not referenced in subsequent grab history events. There is no `commandId` field on history records.

**Recommended correlation approach: timestamp + item ID window matching.**

1. When fetcharr triggers a search, record `(item_id, search_timestamp)` in search_history
2. After a configurable delay (e.g., 5-15 minutes), poll `/api/v3/history/movie?movieId={id}&eventType=grabbed` or `/api/v3/history/series?seriesId={id}&eventType=1`
3. If any grab event exists with `date > search_timestamp`, attribute it to fetcharr
4. Mark the search_history entry as "grabbed" (or "partial" for Sonarr if not all episodes were resolved)
5. Stop polling for this entry after the tracking window expires (e.g., 60 minutes)

**Why this works:** Fetcharr is typically the only automation triggering searches at the time. Organic RSS grabs happen on their own schedule and are unlikely to coincide with fetcharr's search window for the same item. The timestamp window makes false attribution rare in practice.

**Where this can fail:** If a user manually searches in Radarr/Sonarr UI at the same moment fetcharr searches the same item, the manual grab would be attributed to fetcharr. This is an acceptable edge case -- the stats will be slightly inflated but not meaningfully wrong.

### Sonarr "Partial" Detection

For Sonarr season-level searches, "partial" means some but not all missing episodes in the season were grabbed. Detection approach:

1. At search time, query the wanted/missing endpoint to count how many episodes are missing for that (seriesId, seasonNumber)
2. Store the expected missing count alongside the search entry
3. At tracking time, count grab events for episodes in that season within the tracking window
4. If grabs > 0 but grabs < expected_missing, outcome = "partial"
5. If grabs >= expected_missing, outcome = "grabbed"

**Complexity note:** This requires storing `expected_missing_count` per search entry for Sonarr season searches. For Radarr movies, it is binary -- either the movie was grabbed or it was not.

---

## Tech Debt Features (v2.0 Scope)

These are the 8 deferred items from the v1.2 deep review. They are not features users will see on the dashboard, but they are required for production hardening.

| Feature | Why Needed | Complexity | Notes |
|---------|-----------|------------|-------|
| Rate limiting on search-now endpoint | Prevents users (or scripts) from hammering the manual search button and flooding indexers | LOW | Simple in-memory rate limiter (e.g., 1 request per 30 seconds per app) |
| CSRF protection on settings POST | The settings endpoint currently lacks CSRF protection -- existing Origin/Referer middleware may not cover all cases | LOW | Apply same Origin/Referer check already used elsewhere, or add a CSRF meta tag |
| Bounded search history table growth | Currently auto-prunes at 500 rows; needs to be configurable | LOW | Add config setting for max rows; update DELETE query |
| Connection pooling for aiosqlite | Current connection-per-operation pattern opens/closes DB on every call | MEDIUM | Shared connection or connection pool; must handle async context correctly |
| Health check endpoint | Container orchestrators (Docker, Kubernetes) need a /health endpoint | LOW | Return 200 if app is running and DB is accessible |
| Graceful shutdown handler | Clean up APScheduler, close httpx clients, flush logs on SIGTERM | LOW | Signal handler + cleanup function |
| Request timeout on outbound HTTP calls | Already partially handled by httpx timeout param, but needs explicit configuration | LOW | Make timeout configurable via settings |
| Configurable pageSize defaults | Currently hardcoded at 50; large libraries may benefit from larger page sizes | LOW | Add config setting, pass to get_paginated() |

---

## v2.0 Feature Prioritization

| Feature | User Value | Complexity | Priority | Phase Suggestion |
|---------|------------|------------|----------|-----------------|
| Schema migration (add item_id, season_number, tracked_until) | Prerequisite | LOW | P0 | First |
| Store item IDs at search time in engine.py | Prerequisite | LOW | P0 | First |
| RadarrClient.get_movie_history() | Prerequisite | LOW | P0 | First |
| SonarrClient.get_series_history() | Prerequisite | LOW | P0 | First |
| History polling scheduler (separate from search scheduler) | HIGH | MEDIUM | P1 | After client methods |
| Grab correlation logic (timestamp + item ID matching) | HIGH | HIGH | P1 | Core tracking phase |
| Update search_history outcome to grabbed/partial/unresolved | HIGH | LOW | P1 | Core tracking phase |
| Grabbed/partial/unresolved badges in search history UI | HIGH | LOW | P1 | After correlation logic |
| Aggregate effectiveness stats on dashboard | HIGH | LOW | P1 | After tracking works |
| Lifetime stats cards (movies/episodes found/updated) | MEDIUM | LOW | P2 | After aggregate stats |
| Configurable tracking window + poll interval | MEDIUM | LOW | P2 | After core tracking |
| Per-app effectiveness breakdown | LOW | LOW | P2 | After aggregate stats |
| Grab source metadata display | LOW | MEDIUM | P3 | Defer unless easy |
| Time-to-grab metric | LOW | LOW | P3 | Defer unless easy |
| Rate limiting on search-now | MEDIUM | LOW | P1 | Tech debt phase |
| CSRF on settings POST | MEDIUM | LOW | P1 | Tech debt phase |
| Bounded history (configurable max) | LOW | LOW | P2 | Tech debt phase |
| Connection pooling aiosqlite | LOW | MEDIUM | P2 | Tech debt phase |
| Health check endpoint | MEDIUM | LOW | P1 | Tech debt phase |
| Graceful shutdown handler | MEDIUM | LOW | P1 | Tech debt phase |
| Request timeout (configurable) | LOW | LOW | P2 | Tech debt phase |
| Configurable pageSize | LOW | LOW | P2 | Tech debt phase |

**Priority key:**
- P0: Must be done first (prerequisites for everything else)
- P1: Core value -- without these, v2.0 is not a release
- P2: Should have -- complete the feature but not blocking
- P3: Nice to have -- defer to v2.1 if needed

## Recommended Phase Structure

1. **Schema + Client Methods** (prerequisites) -- DB migration, store item IDs, add history client methods
2. **Core Tracking** -- polling scheduler, grab correlation logic, outcome updates
3. **Dashboard + Badges** -- grabbed/partial/unresolved badges, aggregate stats, lifetime stats cards
4. **Tech Debt** -- rate limiting, CSRF, health check, graceful shutdown, remaining items
5. **Polish** -- configurable tracking window, per-app breakdown, optional metadata display

---

## Sources

### HIGH Confidence
- [Sonarr EpisodeHistory.cs source](https://github.com/Sonarr/Sonarr/blob/0cb8d93069d6310abd39ee2fe73219e17aa83fe6/src/NzbDrone.Core/History/EpisodeHistory.cs) -- definitive enum values and field definitions
- [pyarr RadarrAPI docs](https://docs.totaldebug.uk/pyarr/modules/radarr.html) -- get_movie_history() parameters and event types
- [golift/starr Sonarr package](https://pkg.go.dev/golift.io/starr/sonarr) -- HistoryRecord struct and filter constants
- [Go Radarr SDK (SkYNewZ)](https://pkg.go.dev/github.com/SkYNewZ/radarr) -- Record struct with full field definitions including Data type
- [Sonarr GitHub issue #3587](https://github.com/Sonarr/Sonarr/issues/3587) -- eventType filter confirmed working on /api/v3/ with numeric values
- [Sonarr GitHub issue #4727](https://github.com/Sonarr/Sonarr/issues/4727) -- includeSeries/includeEpisode params fixed on /history/series

### MEDIUM Confidence
- [arr-tracker-source-tagger](https://github.com/Procuria/arr-tracker-source-tagger) -- downloadId correlation approach for grab-to-import matching
- [Sonarr GitHub issue #4759](https://github.com/Sonarr/Sonarr/issues/4759) -- command API does not return actual job results, confirming poll-based approach needed
- [Radarr GitHub issue #7874](https://github.com/Radarr/Radarr/issues/7874) -- history/since endpoint fix cherry-picked from Sonarr
- [DeepWiki Radarr REST API](https://deepwiki.com/radarr/radarr/4.1-rest-api) -- history endpoint overview and downloadId correlation description
- [Huntarr fork (zephyrnux)](https://github.com/zephyrnux/huntarr) -- confirmed no grab tracking in competitor; monitors command completion only

### LOW Confidence
- [Huntarr security incident coverage](https://piunikaweb.com/2026/02/24/huntarr-security-vulnerability-arr-api-keys-exposed/) -- competitor context; main repo deleted

---
*Feature research for: Fetcharr v2.0 closed-loop download tracking*
*Researched: 2026-02-24*
