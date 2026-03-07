# Project Research Summary

**Project:** Triggarr — Radarr/Sonarr search automation tool
**Domain:** *arr ecosystem automation daemon with minimal web UI
**Researched:** 2026-02-23
**Confidence:** HIGH

## Executive Summary

Triggarr is a focused single-purpose automation daemon: it cycles through Radarr's and Sonarr's wanted/cutoff-unmet lists on a configurable schedule and triggers searches in a controlled, rate-safe, round-robin fashion. The space is well-understood — Huntarr is the dominant tool but suffered a high-profile security failure (API keys returned from unauthenticated endpoints), and Triggarr's entire reason for existing is to do the same job correctly. The recommended approach is a single Python/FastAPI process with APScheduler v3 running inside the FastAPI lifespan, httpx AsyncClient for all *arr API calls, TOML config on a Docker volume, and SQLite (or JSON file) for persistent round-robin state. The web UI is htmx + Jinja2 server-side rendering — no JS build step, no framework, no auth surface.

The core business logic is straightforward and well-documented: fetch paginated wanted/cutoff lists from the *arr APIs, advance a persisted cursor through the list, trigger `MoviesSearch` (Radarr) or `SeasonSearch` (Sonarr) for the next N items. The Sonarr variant requires deduplicating episode records into unique (seriesId, seasonNumber) pairs before triggering searches — this is non-obvious but critical both for correctness and indexer health. All API keys must live server-side only and must never appear in any HTTP response, config GET endpoint, or log line. This is the one architectural invariant that cannot be compromised.

The primary risks are security (API key exposure, replicating Huntarr's mistake) and indexer health (triggering too many searches with defaults that are too aggressive). Both risks are addressed by design decisions that must be established in Phase 1 and never relaxed: zero key material in any HTTP response, conservative default intervals (60 minutes recommended), conservative default batch sizes (3–5 items), and `X-Api-Key` header auth exclusively. The build order is dictated by the dependency graph: Config → State → API Clients → Search Cycle Logic → Scheduler → FastAPI Routes → Web UI → Docker. Do not invert this order.

## Key Findings

### Recommended Stack

The stack is lean and consistent with the user's existing projects (FastAPI, htmx, Tailwind v4). Python 3.13-slim Docker image is the correct runtime; FastAPI 0.132.0 with Uvicorn 0.41.0 handles both API and UI routes in a single async process. APScheduler 3.11.2 (not v4 — it is alpha-only) runs the search cycles as async jobs sharing FastAPI's event loop via the `@asynccontextmanager` lifespan pattern. All *arr API calls use `httpx.AsyncClient` — synchronous `requests` is explicitly ruled out as it blocks the event loop. Config is TOML (stdlib `tomllib` + `tomli-w` 1.2.0); state is a JSON file or SQLite in the Docker volume. CSS is Tailwind v4 built at Docker image build time via `pytailwindcss` — no Node.js in the container.

**Core technologies:**
- Python 3.13-slim: Runtime — latest stable, uvloop support, minimal image size
- FastAPI 0.132.0: Web framework — async-native, handles both htmx routes and API, no extra server needed
- APScheduler 3.11.2: Scheduler — `AsyncIOScheduler` shares FastAPI's event loop; v4 is alpha, do not use
- httpx 0.28.1: HTTP client — async-native, `AsyncClient` with connection pooling and configurable timeouts
- tomllib (stdlib) + tomli-w 1.2.0: Config — TOML with comment support; read-only stdlib + write-capable tomli-w
- JSON file (stdlib): State — round-robin cursor + bounded search history log; SQLite is overkill for this scope
- Jinja2 + htmx 2.0.7: UI layer — server-side rendering, no JS framework, htmx for live status polling
- pytailwindcss 0.3.0: CSS build — Tailwind v4 in Docker build stage only; no Node.js in production image

See full stack details: `.planning/research/STACK.md`

### Expected Features

The feature set is tightly scoped. The competitive differentiation against Huntarr is not features — it is security and correctness. Do not add features that introduce auth surfaces, third-party libraries, or scope outside search automation.

**Must have (table stakes):**
- Radarr + Sonarr API connections (URL + API key, validated on startup)
- Fetch wanted/missing and cutoff-unmet lists from both apps (paginated — pageSize must be set explicitly)
- Round-robin search triggering: `MoviesSearch` for Radarr, `SeasonSearch` (not SeriesSearch, not EpisodeSearch) for Sonarr
- Separate round-robin queues for missing vs cutoff-unmet per app (independent cursors)
- Configurable items-per-cycle and interval per app
- Persistent round-robin cursor (survives container restarts)
- API keys never returned by any HTTP endpoint — ever
- Web UI: last run, next run, queue position, item counts, recent search log
- Web UI config editor (no file editing required)
- Docker container + docker-compose

**Should have (competitive differentiators):**
- Graceful degradation display ("Radarr unreachable since [time]") — not silent failure
- Human-readable log (item names, not raw IDs)
- Monitored-only filter (skip unmonitored items before queuing)
- Skip future air date items filter (Sonarr only — prevents pointless searches for unaired episodes)
- Hard ceiling on max items per cycle (safety cap against misconfiguration)
- Security model documented in README (explicit trust-building for users burned by Huntarr)

**Defer (v2+):**
- Per-app enable/disable toggle
- Manual "search now" button
- Persistent search history beyond in-memory log (SQLite storage for longer history)

**Anti-features to reject explicitly:**
- User accounts / authentication (reintroduces credential attack surface; use Tailscale/VPN)
- Multi-instance support (scope creep; document "run two containers" as workaround)
- Lidarr/Readarr/Whisparr support (each *arr has API nuances; out of scope)
- Notifications (Apprise dependency; web UI log is sufficient)
- Download queue management / stalled download detection (decluttarr's job)
- Media discovery / TMDB browsing (Overseerr's job)

See full feature analysis: `.planning/research/FEATURES.md`

### Architecture Approach

Single-process Docker container: one FastAPI app running under Uvicorn, with APScheduler's `AsyncIOScheduler` started inside the FastAPI lifespan context manager. The scheduler owns the search loop and is the only writer to the state store. The web UI is read-only — it queries SQLite state, never calls out to Radarr/Sonarr live. This separation means UI latency is never affected by *arr availability.

**Major components:**
1. Config Layer (`app/config.py`) — Load/save TOML config; Pydantic Settings model; API keys loaded once at startup, never returned
2. State Store (`app/state.py`) — SQLite (or JSON) for round-robin positions, search history, last/next run times; single writer (scheduler), multiple readers (UI)
3. API Clients (`app/clients/radarr.py`, `app/clients/sonarr.py`) — httpx AsyncClient per app; X-Api-Key header; paginated fetching; command name correctness enforced here
4. Search Cycle Logic (`app/search/radarr_cycle.py`, `app/search/sonarr_cycle.py`) — Round-robin cursor advance; Sonarr episode deduplication to seasons; batch slicing with wrap-around
5. Scheduler Engine (`app/scheduler.py`) — APScheduler job registration using FastAPI lifespan; interval configuration from settings; jobs call cycle logic
6. FastAPI Routers + UI (`app/routers/`, `app/templates/`) — htmx partial responses for status polling; config form POST/GET; PRG pattern on config save; no API key values in any response
7. Docker + Compose — Multi-stage build (pytailwindcss in builder stage, production image with static CSS); data/ volume for config + state

**Build order (dictated by dependency graph):**
Config → State → API Clients → Search Cycle Logic → Scheduler → FastAPI Routes → Web UI → Docker

See full architecture details: `.planning/research/ARCHITECTURE.md`

### Critical Pitfalls

1. **API keys in HTTP responses** — The Huntarr failure. Zero tolerance: no API key values in any response body, config GET endpoint, or HTML `value=""` attribute. Config form shows masked placeholders. Establish this as a rule in Phase 1 and never revisit. Verify by curling all GET endpoints and checking browser DevTools.

2. **Indexer rate limit exhaustion** — Default intervals must be conservative (60-minute recommended, 5-minute enforced minimum). Default batch size 3–5 items. No "search all now" button without prominent rate-limit warning. Many free indexers cap at 100–200 API hits per 24 hours; an aggressive tool can exhaust that in minutes silently (202 Accepted from *arr does not mean indexer success).

3. **Wrong Sonarr command or search granularity** — `SeasonSearch` with explicit `seriesId` + `seasonNumber` only. Never `SeriesSearch` (hammers indexers episode-by-episode). Never `EpisodeSearch` per episode (same problem). Deduplicate episode records to unique (seriesId, seasonNumber) pairs before triggering any search. Verify by checking Sonarr's activity queue after automation runs.

4. **API keys in logs** — Pass API keys via `X-Api-Key` header only, never query param. Disable httpx debug-level logging in production. Log actions ("Triggering search for movie 42"), not HTTP wire traffic. Grep Docker logs for key values as a verification step.

5. **Round-robin state lost on container restart** — In-memory state silently resets to position 0 on every restart. Always persist cursor to the state file in the Docker volume. Validate saved position against current item count on startup (reset to 0 if position exceeds count). This is a 10-line fix that prevents the entire failure mode.

See full pitfall analysis: `.planning/research/PITFALLS.md`

## Implications for Roadmap

Based on the combined research, the dependency graph from ARCHITECTURE.md and the pitfall-to-phase mapping from PITFALLS.md dictate a clear 4-phase structure for v1.0.

### Phase 1: Foundation — Config, State, and API Clients

**Rationale:** Config and State are prerequisites for every other component. API Clients must be correct (right command names, header auth, pagination) before anything is built on top of them. Security invariants (no API key in responses, X-Api-Key header only, no debug logging) must be established here — retrofitting them later is error-prone.

**Delivers:** Working connection to Radarr and Sonarr; startup validation; paginated list fetching; correct command names; config TOML load/save; state persistence foundation; zero API key leakage established as a verified invariant.

**Addresses (from FEATURES.md):** Radarr + Sonarr API connections, fetch wanted/missing and cutoff-unmet, API key security, persistent state scaffolding.

**Avoids (from PITFALLS.md):** API key exposure in responses (Pitfall 1), API key in logs (Pitfall 4), wrong command names (Pitfall 3), pagination bug (Pitfall 8), no startup connectivity check (Pitfall 9).

**Research flag:** No additional research needed — API endpoints verified, command names confirmed, auth pattern established.

---

### Phase 2: Search Engine — Scheduler, Round-Robin, and Cycle Logic

**Rationale:** With config, state, and clients in place, the core automation logic can be built: APScheduler wired into FastAPI lifespan, round-robin cursor management, Sonarr season deduplication, batch slicing, state writes after each cycle. This is the product's core value — everything else is scaffolding or display.

**Delivers:** Fully functional search automation. Radarr cycles through wanted/cutoff lists at configured intervals and batch sizes. Sonarr cycles through seasons (not episodes, not series). Round-robin position persists across restarts. Configurable items-per-cycle and interval per app.

**Addresses (from FEATURES.md):** Round-robin search triggering, separate missing/cutoff queues, configurable intervals and batch sizes, persistent cursor, season-level Sonarr search.

**Avoids (from PITFALLS.md):** APScheduler event loop conflict (Pitfall 10 — initialize inside lifespan), round-robin state loss (Pitfall 5 — persist to SQLite/JSON), wrong Sonarr search granularity (Pitfall 6 — SeasonSearch only), indexer flooding defaults (Pitfall 2 — conservative defaults enforced), pagination bug (Pitfall 8 — paginate from Phase 1 client already handles this).

**Research flag:** No additional research needed — APScheduler lifespan pattern verified, Sonarr deduplication logic documented with working examples.

---

### Phase 3: Web UI and Config Editor

**Rationale:** The UI reads from state (written by the scheduler in Phase 2). Building UI after the data layer means the templates render real data from day one, not mocks. The config editor completes the user-facing loop: change settings in the UI, scheduler reschedules without restart.

**Delivers:** htmx/Jinja2 status dashboard (last run, next run, queue position per app, item counts, recent search log), config editor form (POST saves to disk and reschedules), htmx polling at 30s intervals, PRG pattern on config save, masked API key display in forms.

**Addresses (from FEATURES.md):** Web UI status display, config editor, human-readable log (item names), graceful degradation display, monitored-only filter toggle, skip-future-air-date filter.

**Avoids (from PITFALLS.md):** API key exposure in form `value=` attributes (Pitfall 1 — use placeholders), htmx polling hammering (Pitfall 12 — 30s minimum interval, endpoint reads state not live *arr), no visible indication of last search time (UX pitfall — surface prominently).

**Research flag:** No additional research needed — htmx polling patterns, PRG pattern, and Jinja2 config form pattern are standard and well-documented.

---

### Phase 4: Docker Packaging and Release

**Rationale:** Docker is the delivery format for self-hosters. It must be built last because it packages a working application. Multi-stage build (CSS compilation in builder stage) keeps the production image clean. Volume configuration, networking documentation, and startup error messaging complete the user experience.

**Delivers:** Multi-stage Dockerfile, docker-compose.yml, data/ volume for config + state, startup networking validation with clear error messages, README with security model documentation, config template (never COPY actual config into image), release-ready artifact.

**Addresses (from FEATURES.md):** Docker container + docker-compose, security model documented in README, explicit statement of what is and is not returned by any endpoint.

**Avoids (from PITFALLS.md):** Config file COPY'd into Docker image (Pitfall 11 — volume-mount only, never COPY), Docker networking URL confusion (Pitfall 7 — startup check with clear error for localhost URLs), API key baked into image layers (security table — config must be runtime-only).

**Research flag:** No additional research needed — Docker multi-stage build and docker-compose patterns are standard. Networking pitfall is documented with exact messaging to use.

---

### Phase Ordering Rationale

- Config and State must precede everything else (all components read config; scheduler writes state)
- API Clients must be correct before the Scheduler is built on top of them — wrong command names discovered early are trivial to fix; discovered after scheduler integration are harder
- Search Cycle Logic is the core product — it belongs in Phase 2 alongside the Scheduler that drives it, not split across phases
- Web UI is deliberately last because it is read-only display; it can be built quickly against real state data produced by Phase 2
- Docker packaging is always the final step — wrap a working application, not a development environment
- Security invariants (Pitfalls 1 and 4) are Phase 1 concerns, not Phase 3 add-ons — this is the most important sequencing decision

### Research Flags

Phases with standard patterns (skip `research-phase`):
- **Phase 1:** All API endpoints verified against official Radarr/Sonarr specs; command names confirmed; auth pattern established
- **Phase 2:** APScheduler lifespan pattern verified and documented with working code examples; Sonarr season deduplication logic fully specified
- **Phase 3:** htmx polling, Jinja2 templating, PRG pattern — all standard, well-documented
- **Phase 4:** Docker multi-stage build and docker-compose — standard homelab patterns; no novel integrations

No phases require deeper research. All critical API behaviors, pitfalls, and patterns were resolved during initial research. Implementation confidence is HIGH across all phases.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All package versions verified against PyPI on 2026-02-23; API endpoints verified against official OpenAPI specs |
| Features | HIGH (core), MEDIUM (differentiators) | Core search mechanics verified via official docs + real-world implementations; differentiator rationale based on ecosystem analysis |
| Architecture | HIGH | API details verified via official docs and pyarr source; APScheduler + FastAPI lifespan pattern verified against official repos |
| Pitfalls | HIGH | Critical security pitfalls verified against primary source (rfsbraz/huntarr-security-review); API pitfalls verified against official issue trackers and forum posts with multiple independent confirmations |

**Overall confidence:** HIGH

### Gaps to Address

- **Sonarr v3 vs v4 API compatibility:** Research noted that Sonarr v4 enforces `Content-Type: application/json` strictly and may have command name differences. If the user runs Sonarr v4, the startup `/api/v3/system/status` version check should log the version, and HTTP client should always set `Content-Type: application/json` on POST requests. No additional research needed — mitigation is clear and low-cost.

- **pageSize ceiling for large libraries:** Research recommends pageSize=100 for paginated fetching, but very large libraries (1000+ items) may require testing. Log the total item count fetched each cycle so users can diagnose unexpected truncation. No blocker for implementation.

- **JSON file vs SQLite for state:** Research recommends JSON file for simplicity (one integer per cursor + bounded log list), while ARCHITECTURE.md shows SQLite in diagrams. Either works; the implementation decision can be made during Phase 1 planning based on whether write-safety (atomic file replace) is preferred over query convenience. Recommend JSON with atomic write (`os.replace` after writing to `.tmp`) for maximum simplicity.

## Sources

### Primary (HIGH confidence)
- Radarr API OpenAPI spec — https://raw.githubusercontent.com/Radarr/Radarr/develop/src/Radarr.Api.V3/openapi.json — endpoint shapes, pagination parameters, command names
- Huntarr security review — https://github.com/rfsbraz/huntarr-security-review/blob/main/Huntarr.io_SECURITY_REVIEW.md — documented 21 vulnerabilities; API key exposure attack vector
- pyarr Sonarr API docs — https://docs.totaldebug.uk/pyarr/modules/sonarr.html — SeasonSearch command name and parameter shape verified
- APScheduler PyPI — https://pypi.org/project/APScheduler/ — v3.11.2 stable, v4 alpha status confirmed
- FastAPI PyPI — https://pypi.org/project/fastapi/ — version 0.132.0 verified
- Uvicorn PyPI — https://pypi.org/project/uvicorn/ — version 0.41.0 verified, Python 3.9 drop confirmed
- httpx PyPI — https://pypi.org/project/httpx/ — version 0.28.1 verified
- Tailwind CDN production caveat — https://tailwindcss.com/docs/installation/play-cdn — "not for production" documented officially
- APScheduler event loop issue — https://github.com/agronholm/apscheduler/issues/484 — event loop initialization gotcha confirmed
- Radarr pagination — https://github.com/Radarr/Radarr/issues/5246 — pagination behavior for large libraries

### Secondary (MEDIUM confidence)
- Huntarr DeepWiki — https://deepwiki.com/plexguide/Huntarr.io/1-introduction-to-huntarr — competitor feature baseline via code analysis
- Huntarr community security discussion — https://news.ycombinator.com/item?id=47128452 — community lessons on OSS security
- Sonarr v4 API breaking changes — https://forums.sonarr.tv/t/need-some-help-with-changes-in-v4-api-commands/33092 — Content-Type enforcement confirmed by multiple users
- TRaSH Guides indexer rate limit avoidance — https://trash-guides.info/Prowlarr/prowlarr-setup-limited-api/ — conservative defaults rationale
- BetterStack APScheduler guide — https://betterstack.com/community/guides/scaling-python/apscheduler-scheduled-tasks/ — FastAPI lifespan pattern verified
- seasonarr GitHub — https://github.com/d3v1l1989/seasonarr — confirms SeasonSearch API command works in practice

### Tertiary (LOW confidence)
- ElfHosted Triggarr/Huntarr context — https://store.elfhosted.com/blog/2025/04/09/feaar-the-huntarr-and-the-shim/ — single managed-hosting perspective on feature usage; not used as decision input

---
*Research completed: 2026-02-23*
*Ready for roadmap: yes*
