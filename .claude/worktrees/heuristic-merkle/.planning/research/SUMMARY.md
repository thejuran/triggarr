# Project Research Summary

**Project:** Fetcharr v2.0 — Closed-Loop Download Tracking + Tech Debt
**Domain:** *arr search automation daemon — download outcome verification and lifetime stats
**Researched:** 2026-02-24
**Confidence:** HIGH

## Executive Summary

Fetcharr v2.0 transforms the existing fire-and-forget search automation daemon into a closed-loop system: it triggers searches in Radarr/Sonarr (as before) and then polls their history APIs to detect whether those searches actually resulted in grabs. The architecture research is clear that this tracking should integrate as a post-search phase within existing cycle functions — not as a separate scheduler job. The reasoning is solid: the `search_lock` already serializes cycle access, grabs appear in *arr history within 30-90 seconds of a search command, and a single-poll approach avoids coordination complexity between two jobs sharing state. The existing layered architecture (`engine` -> `clients` -> `db`) absorbs all new code cleanly, with only one new source file (`tracking.py`) containing pure correlation functions.

The stack research delivers excellent news: zero new PyPI dependencies are required. Every new capability — history polling, outcome correlation, lifetime stats, rate limiting, CSRF hardening, connection pooling, health check, graceful shutdown — is achievable with the existing stack (Python 3.13, FastAPI, httpx, APScheduler 3.x, aiosqlite, Jinja2, htmx, Tailwind CSS v4) plus stdlib. The Radarr and Sonarr history endpoints are well-documented REST calls verified against OpenAPI specs, and they fit the existing `ArrClient` pattern exactly. The 8 tech debt items are all internal code changes requiring no library additions.

The main risk is the correctness of grab attribution. The *arr history APIs provide no causal link between a search command and a subsequent grab — there is no `commandId` field on history records. Fetcharr must use timestamp-windowed correlation: record when each search fires, poll for grabs within a configurable window afterward, and attribute any grab within that window to fetcharr. This is probabilistic, not deterministic, and the implementation must protect against two well-documented failure modes: false positive attribution (organic RSS grabs counted as fetcharr-triggered) and pruning rows before correlation completes. Both are solvable with the strategies documented in PITFALLS.md and both must be addressed in Phase 1 before any tracking logic is layered on top.

## Key Findings

### Recommended Stack

The existing stack needs no additions. v2.0 is purely additive changes to existing files plus one new module. The critical insight from STACK.md is that all 8 tech debt items and the entire closed-loop tracking feature fit within the current dependency set. The two items most commonly over-engineered — rate limiting (often drives slowapi/Redis) and connection pooling (often drives aiosqlitepool) — are both resolvable with stdlib `time.monotonic()` and a single shared aiosqlite connection with WAL mode respectively. This is explicitly justified: fetcharr is a single-process, single-user local network tool, and the solutions that match that constraint are simpler and have zero new attack surface.

**Core technologies:**
- Python 3.13 + FastAPI: existing application framework — no change needed
- httpx (AsyncClient): used for new history endpoint calls — same retry logic, same timeout, same error handling as existing `ArrClient` methods
- aiosqlite: single shared connection with WAL mode replaces connection-per-operation — eliminates concurrent write contention, adds zero deps
- APScheduler 3.x: post-search tracking integrates as a delay within existing cycle functions — no new scheduler jobs needed
- Pydantic/pydantic-settings: new config fields (`tracking_delay_seconds`, `history_max_rows`, `page_size`, `request_timeout`) — backward compatible, existing configs work unchanged
- stdlib `time.monotonic()`: rate limiting on search-now endpoint — 4-line in-memory check, zero deps

**New API endpoints verified (HIGH confidence against OpenAPI specs):**
- Radarr: `GET /api/v3/history/movie?movieId={id}&eventType=1` — per-movie grab history
- Sonarr: `GET /api/v3/history/series?seriesId={id}&eventType=1` — per-series grab history
- `eventType=1` (Grabbed) is integer value 1 in both Radarr and Sonarr; higher enum values diverge between apps

### Expected Features

**Must have (table stakes — v2.0 incomplete without these):**
- Poll Radarr history for grab events after fetcharr-triggered searches
- Poll Sonarr history for grab events after fetcharr-triggered searches
- Correlate grabs to fetcharr searches via timestamp + item ID window matching
- Update search history entries with `grabbed` / `partial` / `unresolved` outcomes
- Visual outcome badges (`grabbed`, `partial`, `unresolved`) on search history entries
- `partial` badge for Sonarr season searches (some but not all missing episodes grabbed)
- Aggregate search effectiveness percentage on dashboard
- Lifetime stats counters: movies found, movies upgraded, episodes found, episodes upgraded
- Rate limiting on search-now endpoint (prevents indexer hammering)
- Health check endpoint (`/health`) with accurate status reporting
- Graceful shutdown (WAL connection closed, clients closed on SIGTERM)

**Should have (differentiators — complete v2.0 but not blocking):**
- Configurable tracking window and poll interval via `fetcharr.toml`
- Per-app effectiveness breakdown (Radarr: X%, Sonarr: Y%)
- Configurable `page_size`, `history_max_rows`, `request_timeout` (tech debt hardening)
- Settings UI controls for new config options
- Color-coded outcome badges (green grabbed, yellow partial, gray unresolved, red failed)
- Tooltips explaining "unresolved" and "partial" states

**Defer (v2.1+):**
- Grab source metadata display (quality, indexer name) per search entry
- Time-to-grab metric (average seconds from search to grab)
- Dashboard sparkline/chart for grab rate trend over time
- Per-indexer effectiveness aggregation (Prowlarr's job)
- Automated re-search of unresolved items (round-robin already handles naturally)
- Historical backfill of pre-fetcharr grabs (impossible to attribute correctly)

**Anti-features (explicitly excluded):**
- Download client integration (qBit/SAB polling) — out of scope; *arr apps manage download clients
- Webhook receiver for *arr notifications — adds bidirectional coupling and attack surface
- Full import tracking (downloadFolderImported) — two-phase tracking for marginal value
- Cookie-based CSRF tokens — sessionless app; Origin/Referer validation is the correct approach
- slowapi/Redis for rate limiting — single-user local tool; in-memory timestamp check is sufficient

### Architecture Approach

The architecture recommendation is minimal new components with maximum reuse of the existing layered structure (`__main__.py` -> `startup.py` -> `scheduler.py` -> `engine.py` -> `clients/` + `db.py`). The closed-loop tracking integrates as a post-search phase inside `run_radarr_cycle()` and `run_sonarr_cycle()` — after all searches fire, wait `tracking_delay_seconds` (default 90, configurable), then poll *arr history per searched item, classify outcomes, update DB rows, and increment lifetime stats. The single shared `search_lock` already serializes cycle access so no new locking is needed. Only one new file is created (`tracking.py` — pure correlation functions, no I/O, highly testable).

**Major components and changes:**
1. `tracking.py` (NEW) — pure functions `classify_radarr_outcome()` and `classify_sonarr_outcome()` that take pre-fetched history records and return outcome strings; no I/O, no state mutation
2. `db.py` (MODIFY) — shared connection via `get_connection()` / WAL mode; new `update_search_outcome()`, `increment_stat()`, `get_lifetime_stats()`; `insert_search_entry()` returns row ID; pruning excludes `outcome='searched'` rows
3. `clients/radarr.py` + `clients/sonarr.py` (MODIFY) — add `get_movie_history()` and `get_series_history()` methods; per-app event type constants
4. `search/engine.py` (MODIFY) — post-search tracking phase; collect entry IDs from inserts; wire correlation logic
5. `web/routes.py` (MODIFY) — `/health` endpoint with state-based status reporting; rate limit dict on `app.state`; lifetime stats display
6. `models/config.py` (MODIFY) — new config fields with backward-compatible defaults
7. `lifetime_stats` SQLite table (NEW) — key/value counter table; atomic increments; survives `state.json` resets

**Critical schema dependency:** `search_history` currently does not store `movieId` / `seriesId` / `seasonNumber` / `tracked_until`. Without these, grab correlation is impossible. This schema migration is the absolute first deliverable.

### Critical Pitfalls

1. **False positive grab attribution** — Organic RSS grabs appear in *arr history after a fetcharr search on the same item, inflating lifetime stats. Prevention: tight configurable time window (default 30 min); timestamp-windowed correlation only; document that stats are probabilistic.

2. **Pruning search history rows before correlation completes** — The existing auto-prune deletes `searched` entries that the history poller needs to UPDATE. Prevention: change pruning logic to exclude `outcome='searched'` rows; add secondary limit that marks aged pending rows as `unresolved` before pruning.

3. **SQLite write contention from concurrent writers** — Adding a history polling phase creates two async writers without the current single-writer guarantee. Prevention: enable WAL mode + `busy_timeout=5000` in `init_db()` before adding any new writers; use a single shared connection.

4. **Sonarr season correlation complexity** — "Partial" vs "grabbed" determination requires recording how many episodes were missing at search time, not just the total season episode count. Prevention: store `missing_episode_count` at search time; compare grabbed episode count to recorded missing count.

5. **Lifetime stats double-counting on container restart** — In-memory counters reset and re-process old grab events on restart. Prevention: store lifetime stats in SQLite `lifetime_stats` table (not `state.json`); persist high-water marks; make stats derivable from `search_history` via `COUNT WHERE outcome='grabbed'`.

## Implications for Roadmap

Based on combined research, the dependency chain dictates phase ordering. The architecture research provides an explicit 5-phase build order that matches the feature priority table in FEATURES.md and maps directly to pitfall prevention requirements in PITFALLS.md.

### Phase 1: Foundation and DB Preparation

**Rationale:** The schema migration and WAL mode enablement are hard prerequisites for every subsequent phase. Building history polling on top of a connection-per-operation pattern without WAL mode will produce intermittent "database is locked" errors under concurrent access. Building correlation logic without `item_id` and `season_number` columns is impossible. These changes must land first.

**Delivers:** DB shared connection with WAL mode; search history schema extended with `item_id`, `season_number`, `tracked_until`; `insert_search_entry()` returns row ID; pruning excludes pending rows; `lifetime_stats` table created; configurable `page_size`, `history_max_rows`, `request_timeout` added to config models.

**Addresses:** All prerequisite table stakes (schema migration, configurable pagination/timeout/row-limit).

**Avoids:** SQLite write contention (Pitfall 5), pruning-vs-correlation race (Pitfall 10 in PITFALLS.md).

### Phase 2: Security and Operations (Tech Debt)

**Rationale:** Tech debt items are small, independent, and improve production safety before the larger tracking feature lands. Rate limiting and health check need to be in place before v2.0 is called releasable. Each item is self-contained and can be implemented, tested, and verified in isolation with no dependencies on tracking logic.

**Delivers:** Rate limiting on search-now (in-memory `time.monotonic()` check, 429 with message); CSRF middleware verification and documentation; `/health` endpoint returning 503 when *arr unreachable; graceful shutdown cleanup (WAL connection close in lifespan `finally`); Dockerfile `STOPSIGNAL SIGTERM`.

**Addresses:** All 8 tech debt table-stakes features.

**Avoids:** Health check false positive (PITFALLS.md Pitfall 12), CSRF scope ambiguity (Pitfall 6), graceful shutdown data corruption (Pitfall 9).

### Phase 3: Tracking Infrastructure

**Rationale:** With DB foundation in place and connections managed correctly, the core tracking components can be built in isolation and fully tested before wiring into the search engine. `tracking.py` pure functions are testable without any mock I/O. The new client history methods follow the exact same pattern as existing client methods and can be independently verified against live *arr instances.

**Delivers:** `RadarrClient.get_movie_history()` and `SonarrClient.get_series_history()` methods with per-app event type constants; `tracking.py` with `classify_radarr_outcome()` and `classify_sonarr_outcome()` pure functions; `update_search_outcome()`, `increment_stat()`, `get_lifetime_stats()` in `db.py`.

**Addresses:** History polling capability for both Radarr and Sonarr; per-app API asymmetry handling.

**Avoids:** Radarr/Sonarr API asymmetry (PITFALLS.md Pitfall 3), pagination mishandling (Pitfall 2), history timeout surfacing as crashes (Pitfall 13).

### Phase 4: Tracking Integration

**Rationale:** With infrastructure tested in isolation, wiring into `engine.py` is straightforward. The post-search delay pattern is fully spec'd in ARCHITECTURE.md with explicit code examples. This phase activates the core v2.0 feature — closed-loop tracking becomes live.

**Delivers:** Post-search tracking phase in `run_radarr_cycle()` and `run_sonarr_cycle()`; `tracking_delay_seconds` config field (default 90s, 0 disables tracking); Sonarr partial detection comparing grabbed-count to missing-count-at-search-time; outcome updates flowing to `search_history` rows; lifetime stats incrementing on confirmed grabs; tracking failures non-fatal (log at debug, retain "searched" outcome).

**Addresses:** Core tracking table stakes (correlation, outcome updates, partial detection, lifetime stats).

**Avoids:** False positive attribution (PITFALLS.md Pitfall 1), Sonarr season correlation complexity (Pitfall 4), stats double-counting (Pitfall 11), history polling frequency abuse (Pitfall 8).

### Phase 5: Dashboard Integration

**Rationale:** Presentation changes are lowest risk and depend entirely on Phases 3-4 having produced real data. Template changes are isolated to `templates/` and do not touch business logic. Stats cards and badges can be built and visually verified end-to-end once correlation data flows.

**Delivers:** Color-coded outcome badges in search history UI; aggregate effectiveness stats display (X of Y searches resulted in grabs, by app); lifetime stats cards on dashboard; settings UI controls for new config options; tooltips explaining "unresolved" and "partial" states; "partial (3 of 5 episodes)" detail in badge labels.

**Addresses:** Dashboard and badge features; configurable tracking window; per-app effectiveness breakdown; UX clarity for new outcome states.

**Avoids:** UX pitfalls (unexplained "unresolved" badge, ambiguous "partial" without episode counts).

### Phase Ordering Rationale

- Foundation before everything else: WAL mode and schema migration are prerequisites — building on connection-per-op without WAL guarantees intermittent failures once two async paths write to the same DB
- Tech debt before tracking: small independent items removed from the tracking phase to keep phases focused; security/ops hardening belongs before a complex new feature ships
- Infrastructure before integration: `tracking.py` pure functions can be fully unit-tested in Phase 3; Phase 4 integration depends on them being correct and client methods being verified
- Dashboard last: presentation requires data; data requires the correlation pipeline; template changes are reversible and low-risk

### Research Flags

Phases with well-documented patterns (skip research-phase during planning):
- **Phase 1 (Foundation):** Standard aiosqlite and SQLite WAL patterns; Pydantic config additions are routine; schema migration follows established codebase pattern with `contextlib.suppress` guards
- **Phase 2 (Tech Debt):** Each item explicitly documented in STACK.md and ARCHITECTURE.md with code examples; no novel patterns
- **Phase 5 (Dashboard):** Standard htmx template modifications; no new technology

Phases that may benefit from targeted implementation verification:
- **Phase 3 (Tracking Infrastructure):** Radarr event type integer values beyond `grabbed=1` should be verified against a live instance — ARCHITECTURE.md flags MEDIUM confidence on exact Radarr integers; Sonarr values are HIGH confidence. Verify before finalizing per-app enum constants.
- **Phase 4 (Tracking Integration):** The post-search delay within a cycle extends cycle duration significantly (90s default). Verify behavior with short search intervals (<10 min) before release; document the interaction in config comments.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new dependencies confirmed; all existing library capabilities verified against official docs and OpenAPI specs; no version conflicts |
| Features | HIGH (API mechanics) / MEDIUM (UX patterns) | History API fields and endpoints verified against Radarr/Sonarr OpenAPI specs, Go SDK, and pyarr docs; "search effectiveness" dashboard UX has no canonical reference but is straightforward to implement |
| Architecture | MEDIUM-HIGH | Integration pattern (post-search phase) is well-reasoned from codebase analysis; Radarr history endpoint confirmed via OpenAPI; some exact query parameter behavior needs live instance verification |
| Pitfalls | HIGH | Critical pitfalls verified against official SQLite docs, Radarr/Sonarr issue trackers, and direct codebase analysis; mitigation strategies are concrete and code-level |

**Overall confidence:** HIGH

### Gaps to Address

- **Radarr `MovieHistoryEventType` integer values beyond `grabbed=1`:** ARCHITECTURE.md notes these may differ from Sonarr. The `grabbed` value (1) is confirmed for both apps; `downloadFolderImported` is 2 in Radarr but 3 in Sonarr. For v2.0 (grab detection only via `eventType=1`), this gap does not block implementation. If import detection is ever added, verify against a live Radarr instance first.
- **Sonarr `includeSeries`/`includeEpisode` parameter status:** FEATURES.md notes these were broken in older Sonarr versions (issue #4727 closed as completed). Since fetcharr does not need the expanded objects (only episode IDs for correlation), excluding these params avoids any residual risk entirely.
- **Tracking delay interaction with short search intervals:** If a user configures a 5-minute search interval and a 90-second tracking delay, the tracking delay consumes 30% of the cycle window. The `search_lock` prevents overlapping cycles, but cycle start times will drift. Document this in config comments rather than engineer around it.
- **Sonarr season pack grab counting:** Season pack grabs in Sonarr are expected to create one history event per episode within the pack. The correlation logic assumes this. Verify against a live Sonarr instance during Phase 4 implementation before marking season correlation complete.

## Sources

### Primary (HIGH confidence)
- Radarr OpenAPI specification — `https://raw.githubusercontent.com/Radarr/Radarr/develop/src/Radarr.Api.V3/openapi.json` — `/history`, `/history/movie`, `/history/since` endpoints; query parameters; response schema
- Sonarr OpenAPI specification — `https://raw.githubusercontent.com/Sonarr/Sonarr/develop/src/Sonarr.Api.V3/openapi.json` — `/history`, `/history/series` endpoints; eventType filter
- Sonarr GitHub issue #3587 — confirms Sonarr EpisodeHistoryEventType integer enum: Unknown=0, Grabbed=1, SeriesFolderImported=2, DownloadFolderImported=3, DownloadFailed=4, Deleted=5, Renamed=6, DownloadIgnored=7
- pyarr Radarr docs — `https://docs.totaldebug.uk/pyarr/modules/radarr.html` — MovieHistoryEventType values; `get_movie_history(id, event_type)` signature
- Sonarr EpisodeHistory.cs source — definitive enum values and field definitions
- SQLite WAL mode documentation — `https://sqlite.org/wal.html` — WAL mode concurrency behavior; PRAGMA journal_mode=WAL
- Fetcharr codebase (direct analysis, 2026-02-24) — `db.py`, `engine.py`, `state.py`, `routes.py`, `middleware.py`, `scheduler.py`
- FastAPI lifespan events docs — `https://fastapi.tiangolo.com/advanced/events/` — shutdown lifecycle
- httpx timeout docs — `https://www.python-httpx.org/advanced/timeouts/` — Timeout class behavior

### Secondary (MEDIUM confidence)
- golift/starr Sonarr package — `https://pkg.go.dev/golift.io/starr/sonarr` — HistoryRecord struct; FilterGrabbed=1 constant
- Go Radarr SDK (SkYNewZ) — `https://pkg.go.dev/github.com/SkYNewZ/radarr` — Record struct with field definitions including `downloadId` omitempty
- Sonarr GitHub issue #4727 — `/history/series` endpoint; `seriesId` param; `includeSeries`/`includeEpisode` fix confirmed
- Sonarr GitHub issue #4759 — command API does not link to resulting history events; confirms poll-based approach required
- DeepWiki Radarr REST API — `/history/since` endpoint existence; HistoryService architecture
- FastAPI graceful shutdown discussion #6912 — confirms uvicorn handles SIGTERM via lifespan; custom handlers risk interference
- arr-tracker-source-tagger — downloadId correlation approach for grab-to-import matching
- aiosqlite "database is locked" prevention — WAL mode + busy_timeout resolves concurrent write issues

### Tertiary (LOW confidence)
- Huntarr fork (zephyrnux) — competitor analysis; no grab tracking in competitor; command completion monitoring only
- Huntarr security incident coverage (2026-02-24) — competitor context; main repo deleted post-incident
- aiosqlitepool GitHub — connection pooling for aiosqlite; evaluated and rejected as overkill for fetcharr's workload

---
*Research completed: 2026-02-24*
*Ready for roadmap: yes*
