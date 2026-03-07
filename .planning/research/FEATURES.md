# Feature Research

**Domain:** *arr search automation tool (Radarr + Sonarr)
**Researched:** 2026-02-23
**Confidence:** HIGH (core search mechanics verified against pyarr docs + Servarr wiki + Huntarr source analysis; differentiator/anti-feature rationale is MEDIUM — informed by ecosystem analysis but no single canonical source)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Connect to Radarr via URL + API key | Every *arr tool does this; it's the only integration point | LOW | POST to `/api/v3/command`, GET from `/api/v3/wanted/missing` and `/api/v3/wanted/cutoff` |
| Connect to Sonarr via URL + API key | Same as Radarr — baseline requirement | LOW | Same API pattern; separate endpoints |
| Fetch wanted (missing) items from Radarr | Users run this tool because their media is missing | LOW | `GET /api/v3/wanted/missing` with `page`/`pageSize` pagination |
| Fetch cutoff unmet items from Radarr | Quality upgrades are the second core use case | LOW | `GET /api/v3/wanted/cutoff` with same pagination pattern |
| Fetch wanted (missing) items from Sonarr | Same as Radarr — symmetry is expected | LOW | `GET /api/v3/wanted/missing` |
| Fetch cutoff unmet items from Sonarr | Same as Radarr | LOW | `GET /api/v3/wanted/cutoff` |
| Trigger search command for individual Radarr items | Core action — without this, the tool does nothing | LOW | `POST /api/v3/command` with `{name: "MoviesSearch", movieIds: [id]}` |
| Trigger search command for Sonarr at season level | Season-level is the right granularity — episode-by-episode hammers indexers; full-show search is too coarse | LOW | `POST /api/v3/command` with `{name: "SeasonSearch", seriesId: id, seasonNumber: n}` |
| Configurable items-per-cycle per app | Without this users can't tune for their indexer limits | LOW | Simple integer config; separate for Radarr and Sonarr |
| Configurable search interval per app | Users have different indexer rate limits and download speeds | LOW | Schedule-driven; separate interval per app |
| Round-robin sequential cycling through items | Ensures every item gets searched eventually (vs random, which leaves some items perpetually skipped) | LOW | Persist cursor/position across cycles; wrap at end of list |
| Web UI: last run time + next scheduled run | Users need confidence the tool is running | LOW | Two timestamps on the main page |
| Web UI: recent search history log | Users need to see what was searched and when | LOW | Append-only log; show item name, type (missing/cutoff), timestamp |
| Web UI: current queue position (round-robin cursor) | Users need to see progress through the list | LOW | Show "position X of Y" for each app |
| Web UI: wanted/cutoff item counts | Users want to know how much work remains | LOW | Show count per list type per app; fetch live from *arr |
| Config editor in the web UI | Users need to change settings without editing files or restarting the container | MEDIUM | Form-based; persist to config file on disk |
| API keys stored server-side only, never returned by any HTTP endpoint | This is the entire reason the project exists; Huntarr's failure was exposing these via unauthenticated endpoints | LOW | Server renders config forms; no endpoint returns raw key values |
| Docker container + docker-compose | Self-hosters expect Docker-first deployment | LOW | Standard Dockerfile + compose file; single service |
| Persistent state across container restarts | Round-robin position must survive restarts | LOW | Persist cursor to a file or SQLite; don't reset on every start |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Explicit security model documented in README | Users burned by Huntarr actively want assurance that keys are safe; this is a trust-building differentiator | LOW | Document exactly what is/isn't returned by any endpoint; no implementation cost |
| Separation of missing vs cutoff unmet queues with independent round-robins | Prevents cutoff upgrades from starving missing-content searches and vice versa; gives user control over ratio | MEDIUM | Maintain two cursors per app; config controls how many of each type per cycle |
| Graceful degradation when *arr is unreachable | Other tools fail silently or crash; showing "Radarr unreachable since [time]" is table stakes for reliability | LOW | Catch connection errors; display status on UI; retry on next cycle |
| Human-readable log format with item names (not just IDs) | Huntarr logs raw IDs; users want to see "Searched: Breaking Bad S03 (missing)" | LOW | Resolve ID to name before logging; requires one extra API call |
| Configurable skip of future-air-date items | Prevents pointless searches for unaired episodes; Sonarr has this data in the API response | LOW | Filter items where `airDateUtc` is in the future before adding to queue |
| Configurable monitored-only filter | Searching unmonitored items wastes indexer quota; users almost always want this | LOW | Filter items where `monitored == false` before adding to queue |
| Hard limit on max items queued per cycle (safety ceiling) | Prevents accidental hammering if misconfigured; "items per cycle" + hard ceiling = belt and suspenders | LOW | Add a configurable max ceiling enforced before triggering any searches |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| User accounts / authentication | "What if someone accesses my UI?" | No auth = no passwords to store = no credential attack surface. This tool is for local network / Tailscale use. Adding auth reintroduces the exact class of vulnerability that killed Huntarr (password storage, session management, 2FA bypass). | Run on Tailscale or behind a VPN. Trust your network perimeter. |
| Multi-instance support (multiple Radarr/Sonarr) | Power users have multiple instances | Multiplies configuration complexity significantly; cursor management per-instance is non-trivial; the user's setup is single-instance. | Document how to run two containers if someone needs this. |
| Lidarr / Readarr / Whisparr support | "While you're at it..." | Scope creep. Radarr + Sonarr cover the primary use case. Each new *arr app requires understanding its own API nuances. | Explicitly out of scope; document in README. |
| Notifications (Discord, Telegram, Apprise) | Users want to be notified of searches | Adds a third-party library dependency (Apprise) and configuration surface area. The web UI log already provides this information. | Web UI log is sufficient; users can tail container logs if they want alerts. |
| Prowlarr integration / indexer stats | "Show me which indexers are working" | Indexer management is out of scope; Prowlarr has its own UI. Adding it blurs the tool's purpose. | Use Prowlarr's own UI. |
| Download queue management (pause when full) | "Don't search if downloads are backed up" | The *arr apps themselves manage download queues. Adding queue logic means Triggarr must now poll qBitTorrent/SABnzbd too. | Trust *arr to handle its own queue; searches that find nothing just time out. |
| "Swaparr"-style stalled download detection | Huntarr added this to pad features | Completely outside the search automation scope; requires download client integration. | Use decluttarr for this purpose. |
| Media discovery / TMDB browsing ("Requestarr") | Huntarr added a media request UI | This is Overseerr's job, not a search automation tool's job. | Use Overseerr or Jellyseerr. |
| Storage monitoring / pause when disk full | "Don't search if disk is nearly full" | Adds system-level dependency; complicates the Docker container (needs volume mounts for disk checks); edge case optimization. | *arr apps refuse to import when disk is full anyway. |
| RSS feed monitoring | "Check new releases in real-time" | Duplicates what *arr already does via RSS sync. The value of this tool is backlog filling, not new-release monitoring. | Sonarr/Radarr already do RSS monitoring natively. |
| Web UI authentication (login form) | "Secure the UI" | Same problem as user accounts above. If the network is trusted, auth is overhead. If it isn't, the tool shouldn't be exposed at all. | Tailscale ACLs or nginx basic auth at the reverse proxy layer. |

## Feature Dependencies

```
[Radarr API connection]
    └──required by──> [Fetch wanted/missing items]
    └──required by──> [Fetch cutoff unmet items]
    └──required by──> [Trigger search command]

[Sonarr API connection]
    └──required by──> [Fetch wanted/missing items (Sonarr)]
    └──required by──> [Fetch cutoff unmet items (Sonarr)]
    └──required by──> [Trigger season search command]

[Fetch items from *arr]
    └──required by──> [Round-robin queue population]

[Round-robin queue population]
    └──required by──> [Trigger search commands]
    └──required by──> [Web UI: queue position display]
    └──required by──> [Web UI: item counts]

[Trigger search commands]
    └──required by──> [Web UI: search history log]

[Persistent state]
    └──enhances──> [Round-robin queue population] (cursor survives restarts)

[Config editor in web UI]
    └──enhances──> [All configurable settings] (no file editing required)

[Configurable monitored-only filter]
    └──modifies──> [Fetch items from *arr] (filters before queue population)

[Configurable skip future air dates]
    └──modifies──> [Fetch items from Sonarr] (filter Sonarr wanted list only)
```

### Dependency Notes

- **Fetch items requires API connection:** Without a working connection to Radarr/Sonarr, nothing else works. Connection validation must be the first thing that runs on startup.
- **Round-robin requires fetched items:** The queue is populated from *arr API responses. The cursor position tracks progress through that list.
- **Search history requires search execution:** Logging is a side effect of search trigger calls; can't log what hasn't been triggered.
- **Persistent state enhances round-robin:** Without persistence, the cursor resets on every container restart and the first N items get searched repeatedly while later items are never reached.
- **Monitored-only and skip-future filters modify fetch, not search:** Apply filters at fetch time (before populating the round-robin queue), not at search time. This keeps the queue clean.

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept.

- [ ] Connect to Radarr (URL + API key, validated on startup) — without this nothing works
- [ ] Connect to Sonarr (URL + API key, validated on startup) — same
- [ ] Fetch wanted/missing and cutoff unmet items from both apps — the data source for all searching
- [ ] Populate round-robin queues (separate queues for missing and cutoff per app) — the core scheduling mechanism
- [ ] Trigger searches: `MoviesSearch` for Radarr, `SeasonSearch` for Sonarr — the core action
- [ ] Configurable items-per-cycle per app (missing count, cutoff count) — prevents indexer abuse
- [ ] Configurable interval per app — allows tuning for different rate limits
- [ ] Persist round-robin cursor across restarts — without this, same first N items are searched on every restart
- [ ] API keys never returned by any HTTP endpoint — the entire security rationale for this project
- [ ] Minimal web UI: last run, next run, item counts, queue position, recent log — confirms the tool is working
- [ ] Web UI config editor — users must be able to change settings without editing files
- [ ] Docker container + docker-compose — standard deployment

### Add After Validation (v1.x)

Features to add once core is working.

- [ ] Monitored-only filter — add when users report searching unmonitored items wastes quota (high probability trigger)
- [ ] Skip future air dates filter — add when users report pointless searches for unaired Sonarr episodes
- [ ] Graceful degradation display — add when users report confusion about silent failures
- [ ] Human-readable log format (item names, not IDs) — add when users complain logs are opaque

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] Per-app enable/disable toggle — allows users to temporarily disable one app without changing config; low demand at v1 scale
- [ ] Manual "search now" button in UI — bypasses scheduler for one-off searches; useful but not needed for the automation use case
- [ ] Search history persistence beyond in-memory log — SQLite storage for longer history; v1 in-memory log is sufficient

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Radarr + Sonarr API connections | HIGH | LOW | P1 |
| Fetch wanted/cutoff items | HIGH | LOW | P1 |
| Round-robin search triggering | HIGH | LOW | P1 |
| Season-level Sonarr search | HIGH | LOW | P1 |
| Configurable items/cycle + interval | HIGH | LOW | P1 |
| Persistent cursor state | HIGH | LOW | P1 |
| API key security (never returned) | HIGH | LOW | P1 |
| Web UI: run times + item counts + log | HIGH | LOW | P1 |
| Web UI config editor | HIGH | MEDIUM | P1 |
| Docker + docker-compose | HIGH | LOW | P1 |
| Monitored-only filter | MEDIUM | LOW | P2 |
| Skip future air dates filter | MEDIUM | LOW | P2 |
| Graceful degradation display | MEDIUM | LOW | P2 |
| Human-readable log (names not IDs) | MEDIUM | LOW | P2 |
| Per-app enable/disable toggle | LOW | LOW | P3 |
| Manual "search now" button | LOW | LOW | P3 |
| Persistent search history (SQLite) | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Huntarr | Missarr (l3uddz) | Triggarr (our approach) |
|---------|---------|-----------------|------------------------|
| Core search automation | Yes — over-engineered with many *arr apps | Yes — minimal CLI, Go binary | Yes — Python/FastAPI, Radarr + Sonarr only |
| User accounts + 2FA | Yes — critical vulnerability surface | No | No — deliberate; local network tool |
| API key exposure risk | CRITICAL (unauthenticated endpoint returns all keys) | Low (CLI tool, no web server) | Zero — keys never returned by any endpoint |
| Web UI | Yes — glassmorphism design, complex dashboard | No | Yes — minimal htmx/Jinja2 status + config |
| Season-level Sonarr search | Yes (Season Packs mode) | Yes | Yes — season level only, not episode or full show |
| Configurable batch size | Yes | Yes (config file) | Yes |
| Configurable interval | Yes | Yes | Yes |
| Round-robin / sequential | Yes | Yes | Yes |
| Persistent cursor | Yes | Unknown | Yes |
| Monitored-only filter | Yes | Unknown | Yes (P2) |
| Download queue management | Yes (Swaparr) | No | No — deliberately out of scope |
| Multi-*arr app support | Yes (5+ apps) | Radarr + Sonarr | Radarr + Sonarr only |
| Notifications (Apprise) | Yes | No | No — out of scope |
| Docker support | Yes | No (binary only) | Yes |
| Security posture | FAILED | Good (no web server) | Good (server-side config only) |

## Sources

- [Huntarr — plexguide/Huntarr.io GitHub](https://github.com/plexguide/Huntarr.io) — competitor feature baseline (MEDIUM confidence; repo was deleted/restored post-security incident)
- [Huntarr DeepWiki — Introduction](https://deepwiki.com/plexguide/Huntarr.io/1-introduction-to-huntarr) — comprehensive feature list from code analysis (MEDIUM confidence)
- [Huntarr Grokipedia page](https://grokipedia.com/page/Huntarr) — configuration options and UI features (MEDIUM confidence)
- [Huntarr security review — rfsbraz/huntarr-security-review](https://github.com/rfsbraz/huntarr-security-review/blob/main/Huntarr.io_SECURITY_REVIEW.md) — documented API key exposure via unauthenticated endpoint (HIGH confidence; independently verified)
- [Huntarr Hacker News discussion](https://news.ycombinator.com/item?id=47128452) — community reaction to security disclosure (MEDIUM confidence)
- [ProxmoxVE community discussion #12225](https://github.com/community-scripts/ProxmoxVE/discussions/12225) — "Remove Huntarr script — critical authentication bypass" (HIGH confidence)
- [missarr — l3uddz/missarr GitHub](https://github.com/l3uddz/missarr) — minimal alternative; confirms CLI-only approach is viable (MEDIUM confidence)
- [seasonarr — d3v1l1989/seasonarr GitHub](https://github.com/d3v1l1989/seasonarr) — confirms SeasonSearch API command exists and works (HIGH confidence)
- [pyarr Sonarr API docs](https://docs.totaldebug.uk/pyarr/modules/sonarr.html) — SeasonSearch, missingEpisodeSearch, EpisodeSearch command names (HIGH confidence)
- [pyarr Radarr models docs](https://docs.totaldebug.uk/pyarr/models/radarr.html) — MoviesSearch, MissingMoviesSearch, CutOffUnmetMoviesSearch command names (HIGH confidence)
- [Sonarr GitHub issue #4950 — /api/v3/wanted/missing sort key](https://github.com/Sonarr/Sonarr/issues/4950) — confirms pagination API shape (MEDIUM confidence)
- [Radarr API:Command wiki](https://github.com/Radarr/Radarr/wiki/API:Command) — command endpoint structure confirmed (MEDIUM confidence)
- [Servarr Wiki — Sonarr Wanted](https://wiki.servarr.com/sonarr/wanted) — UI-level description of missing and cutoff unmet sections (MEDIUM confidence)
- [ElfHosted — Feaar the Huntarr](https://store.elfhosted.com/blog/2025/04/09/feaar-the-huntarr-and-the-shim/) — community-level feature usage context (LOW confidence; single managed-hosting perspective)

---
*Feature research for: *arr search automation (Radarr + Sonarr)*
*Researched: 2026-02-23*
