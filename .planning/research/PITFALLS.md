# Pitfalls Research

**Domain:** Radarr/Sonarr search automation tool (*arr ecosystem)
**Researched:** 2026-02-23
**Confidence:** HIGH (critical security pitfalls verified against primary sources; API behavior verified against official docs and real-world issue trackers)

---

## Critical Pitfalls

### Pitfall 1: API Keys Returned by Any HTTP Endpoint

**What goes wrong:**
Any endpoint that echoes back configuration — even for diagnostic purposes — leaks the Radarr and Sonarr API keys to whoever can reach the web UI. This is exactly what destroyed Huntarr: `POST /api/settings/general` required no authentication and its response body included every connected app's API key in plaintext. A reviewer documented this as a single unauthenticated request returning credentials for 10+ integrated applications simultaneously.

**Why it happens:**
Developers treat internal homelab tools as "trusted network only" and conflate "no auth needed for the UI" with "no need to protect what the API returns." Config endpoints that show current settings naturally include whatever was configured. The mistake is not distinguishing between *reading* config server-side (fine) and *returning* secrets in HTTP responses (never acceptable).

**How to avoid:**
Never include API key values in any HTTP response body, ever. Store keys in a server-side config file. Config editor endpoints receive new values via POST but never return existing key values — return masked representations (`••••••••` or last 4 chars) only. The UI config form pre-populates fields as empty or masked; it does not round-trip the actual key. Apply this rule to all endpoints, including status, health-check, and debug endpoints.

**Warning signs:**
- Any GET endpoint returns a config object that includes `radarr_api_key`, `sonarr_api_key`, or similar fields
- Browser DevTools network tab shows API key values in response JSON
- The config form auto-fills key fields with the actual stored value (requires a GET that returns it)

**Phase to address:** Phase 1 (Core API client + config) — establish the pattern immediately; retrofitting secret-hiding is error-prone and easy to miss.

---

### Pitfall 2: Indexer Rate Limit Exhaustion via Search Flooding

**What goes wrong:**
Triggering too many searches in rapid succession causes Radarr/Sonarr to hammer indexers until they temporarily (or permanently) ban the IP or API key. Free indexers commonly cap at 100–200 API hits per 24 hours. A naive automation tool that searches 20+ items per cycle with a short interval can exhaust a free indexer's daily quota in minutes, silently — searches appear to fire but return nothing because the indexer is blocked. Worse, some indexers issue lifetime bans for repeated violations.

**Why it happens:**
The automation tool fires search *commands* at Radarr/Sonarr, which appear to succeed (202 Accepted). But Radarr/Sonarr then queries indexers, and those indexer calls hit rate limits. The automation tool never sees the downstream failure. Developers assume "command accepted = search happened."

**How to avoid:**
Default search intervals to conservative values — a minimum of 15 minutes between cycles, with 60 minutes as a safer default. Keep per-cycle item counts low (3–5 items) by default. Document that users with large libraries should increase intervals, not decrease them. Do not add a "search all now" button without a prominent warning. Radarr/Sonarr's own backoff logic partially mitigates this, but the automation layer should not make it worse.

**Warning signs:**
- Search cycles completing faster than 5 minutes
- Per-cycle item counts configurable to very high values without guardrails
- No minimum interval enforcement in the scheduler

**Phase to address:** Phase 1 (Search scheduler core) — default values and interval validation must be baked in from the start; do not leave minimums as "TBD" or allow 0.

---

### Pitfall 3: Hardcoded or Version-Assumed API Command Names

**What goes wrong:**
The Radarr and Sonarr API command names for triggering searches have historically had inconsistencies (`MovieSearch` vs `MoviesSearch`), and the parameter format changed between versions. Scripts written for one version silently fail or throw 400 errors on another. Specifically: Sonarr v4 enforces `Content-Type: application/json` strictly, requires numeric IDs as integers (not strings), and the `/api/command` endpoint behavior differs from v3. Automation tools written against Sonarr v3 break on v4 without clear error messages.

**Why it happens:**
Developers test against one version and assume stability. The *arr apps version rapidly; Sonarr v4 was released with meaningful API changes. The correct command names are not prominently documented — they require reading source code or community issues. Community docs sometimes reference old command names (`MovieSearch` singular) that don't work.

**How to avoid:**
Use the correct, verified command names: `MoviesSearch` (plural, with `movieIds` array) for Radarr; `SeasonSearch` (with `seriesId` and `seasonNumber`) for Sonarr. Always send `Content-Type: application/json` explicitly. Always send numeric IDs as integers, not strings. On startup, query `/api/v3/system/status` to detect the app version and log it — this provides a diagnostic breadcrumb if command formats need adjustment later. Test against both Sonarr v3 and v4 build paths if possible.

**Warning signs:**
- API calls return 400 Bad Request with no body
- Commands appear accepted but no search activity appears in Radarr/Sonarr's activity queue
- Missing `Content-Type: application/json` header on POST requests

**Phase to address:** Phase 1 (Core API client) — get command names right before building the scheduler on top of them.

---

### Pitfall 4: API Keys Logged in Application Logs or HTTP Debug Output

**What goes wrong:**
Python HTTP clients (httpx, requests) can log full request URLs and headers in debug mode. If the Radarr/Sonarr API key is passed as a URL query parameter (`?apikey=...`), it appears in every log line. Even with header-based auth, enabling HTTP debug logging dumps all headers including `X-Api-Key`. Logs are often visible in Docker's `docker logs` output, readable by any user with Docker access.

**Why it happens:**
Developers enable verbose logging for debugging and forget to disable it, or use `?apikey=` query param format (which both Radarr and Sonarr support for backwards compatibility) rather than the header form. Query-param API keys also appear in Radarr/Sonarr's own access logs.

**How to avoid:**
Always pass API keys via the `X-Api-Key` header, never as a query parameter. In the httpx client setup, configure a custom logging filter that redacts the `X-Api-Key` header value before log output. Never enable full HTTP request/response debug logging in production Docker builds. Log the *action* (e.g., "Triggering search for movie 42") not the *request* (URL + headers).

**Warning signs:**
- Log output contains `apikey=` query strings
- Log output shows raw HTTP headers
- Any `logging.basicConfig(level=logging.DEBUG)` or httpx debug mode in production code

**Phase to address:** Phase 1 (Core API client) — establish logging patterns before writing any HTTP call code.

---

## Moderate Pitfalls

### Pitfall 5: Round-Robin State Lost on Container Restart

**What goes wrong:**
The round-robin position tracker (which item to search next) lives in memory. When the Docker container restarts — whether from a crash, image update, or host reboot — the position resets to zero. The tool re-searches the first N items in the list repeatedly while the rest of the library never gets searched. For libraries with hundreds of items, this means only the first few items ever benefit from the automation.

**Why it happens:**
In-memory state is the simplest implementation. Developers treat restarts as rare events in homelab contexts, but container restarts are actually common: Docker image updates, OS reboots, and container health check failures all trigger them.

**How to avoid:**
Persist round-robin state to a file (JSON or SQLite) on every cycle advance, stored in a Docker volume. On startup, load the saved position and validate it against current item count (if saved position exceeds current count, reset to 0). This is a 10-line addition that prevents the entire failure mode. The state file should be in `/config` or `/data` alongside the main config, mapped to a named Docker volume.

**Warning signs:**
- Round-robin position stored only in a Python variable or in-memory dict
- No Docker volume mapping for a state/data directory
- No state file written after each cycle

**Phase to address:** Phase 2 (Scheduler + round-robin logic) — design persistence in from day one; adding it after the fact requires careful migration.

---

### Pitfall 6: Searching Sonarr at Series Level Instead of Season Level

**What goes wrong:**
Triggering a `SeriesSearch` for an entire show with many seasons generates one indexer query per episode (Sonarr iterates episode-by-episode before trying season packs). A show with 10 seasons x 22 episodes = 220 indexer API hits for a single "search" command. This independently exhausts indexer rate limits, makes searches take forever, and prevents season packs from being found efficiently (because Sonarr finds no individual episodes and gives up before discovering the pack). The PROJECT.md explicitly calls out season-level search as a design decision — but the wrong Sonarr command is easy to pick accidentally.

**Why it happens:**
`SeriesSearch` is the obvious "search this show" command. The more correct `SeasonSearch` (which requests a specific season by number) is less intuitive. Developers familiar with Radarr's simpler per-movie model apply the same "search whole thing" approach to Sonarr.

**How to avoid:**
Use `SeasonSearch` with explicit `seasonNumber` — not `SeriesSearch`. When fetching Sonarr wanted items, group missing episodes by `(seriesId, seasonNumber)` pairs and issue one `SeasonSearch` per pair. Never issue a `SeriesSearch`. Test with a show that has multiple seasons and verify only one command per season appears in Sonarr's activity queue.

**Warning signs:**
- Any use of `SeriesSearch` command name in code
- Sonarr activity queue shows many simultaneous episode-level searches after triggering automation
- Search cycles take much longer for Sonarr than for Radarr

**Phase to address:** Phase 2 (Search command implementation) — the correct grouping logic needs to be part of the initial Sonarr search implementation, not a patch.

---

### Pitfall 7: Docker Networking — Using `localhost` for Container-to-Container URLs

**What goes wrong:**
The tool's container cannot reach Radarr or Sonarr via `http://localhost:7878` because each container has its own network namespace. `localhost` inside the Triggarr container refers to Triggarr itself, not the host. Users copy their Radarr URL from their browser (which points to `localhost` from the host machine) and paste it into Triggarr config, then get connection refused errors that look like Radarr is broken.

**Why it happens:**
In a homelab context, users naturally think of their URLs as "the address I use in my browser." The Docker networking distinction between host network and container bridge network is non-obvious to casual users.

**How to avoid:**
Document this prominently in the setup guide: "Use your Radarr/Sonarr container name or host IP, not localhost." Validate the configured URL on startup and emit a clear error if connection fails: "Cannot reach Radarr at http://localhost:7878 — if running in Docker, use the container name or host IP instead." Consider adding a connection test endpoint in the UI that shows the exact error message from the connection attempt.

**Warning signs:**
- `localhost` or `127.0.0.1` in configured URLs when deployed in Docker
- Connection refused errors that clear up when using the host machine's IP directly
- Users reporting "it worked until I moved to Docker"

**Phase to address:** Phase 3 (Docker packaging) — add the startup validation and error messaging as part of Dockerization.

---

### Pitfall 8: Fetching the Entire Wanted List Every Cycle Instead of Paginating

**What goes wrong:**
`/api/v3/wanted/missing` and `/api/v3/wanted/cutoff` are paginated endpoints. Fetching a single page with a large `pageSize` to "get everything" has two failure modes: (1) for very large libraries (1000+ items), the response can hit memory limits or timeouts; (2) the default `pageSize` of 10 is very small, so naive implementations that don't set `pageSize` only ever see the first 10 items, and the round-robin never reaches items 11+.

**Why it happens:**
Developers test with small libraries (10–20 items) where one request returns everything. The pagination issue only manifests at scale. The default `pageSize=10` is small enough that the bug is invisible during development.

**How to avoid:**
During the initial load, paginate through all pages with a moderate `pageSize` (100 is safe) until `totalRecords` is reached. Cache the full list in memory for the duration of one cycle; don't re-fetch mid-cycle. On subsequent cycles (at the next scheduled run), re-fetch from scratch to pick up newly added or completed items. Log the total item count fetched so the user can see if something is wrong.

**Warning signs:**
- `pageSize` not set in API requests (defaults to 10, hides items 11+)
- Single API request expected to return all items for large libraries
- Round-robin position never advances past item 10

**Phase to address:** Phase 2 (Wanted list fetching) — pagination must be implemented from the start, not added when a user reports missing items.

---

## Minor Pitfalls

### Pitfall 9: No Startup Connectivity Check

**What goes wrong:**
The tool starts up, the scheduler fires, and the search cycle fails silently because Radarr is unreachable (misconfigured URL, Radarr not yet started, wrong API key). The user sees no searches happening but no error either, and has to check logs to understand why.

**Prevention:**
On startup, issue a test request to `/api/v3/system/status` for both Radarr and Sonarr. If either fails, log a clear error (not just an exception traceback) and surface it in the UI. Do not abort startup — the tool should keep retrying, as Radarr/Sonarr might start up a few seconds later. But the error should be prominently visible.

**Phase to address:** Phase 1 (Core API client).

---

### Pitfall 10: APScheduler Initialized Before the FastAPI Event Loop

**What goes wrong:**
APScheduler's `AsyncIOScheduler` must share the event loop with FastAPI/uvicorn. Initializing the scheduler at module import time (outside `lifespan`) creates a scheduler attached to no event loop or a different one, causing jobs to silently not run or to throw `RuntimeError: no running event loop`.

**Prevention:**
Initialize and start APScheduler inside the FastAPI `lifespan` context manager (or `startup` event). Pass the scheduler instance via app state (`app.state.scheduler`). Start with `scheduler.start()` inside lifespan and `scheduler.shutdown()` on shutdown. Do not create schedulers at module import time.

**Phase to address:** Phase 2 (Scheduler implementation).

---

### Pitfall 11: Config File Containing API Keys Baked into Docker Image

**What goes wrong:**
If the config file with API keys is `COPY`-ed into the Docker image during build (e.g., copying a `config.yaml` from the repo), those keys are embedded in every image layer. They're recoverable via `docker history` or image extraction even after overwriting with a volume mount.

**Prevention:**
Never COPY config files containing secrets into the image. The config file must live entirely in a Docker volume (`/config` directory). Ship the image with only a config *template* or *schema*; the actual values come at runtime via volume mount. Document that `/config` must be a named volume, not the container filesystem.

**Phase to address:** Phase 3 (Docker packaging).

---

### Pitfall 12: htmx Polling Hammering the Status Endpoint

**What goes wrong:**
A `hx-trigger="every 5s"` on the status display polls a FastAPI endpoint every 5 seconds, indefinitely, for every open browser tab. With multiple browser tabs or tabs left open overnight, this generates continuous load on the server and creates unnecessary log noise. If the status endpoint internally queries Radarr/Sonarr for live data, it also generates unnecessary API traffic.

**Prevention:**
The status endpoint should serve data from in-memory state (last run time, next run time, recent log, queue position) updated by the scheduler — it should never call out to Radarr/Sonarr. Keep polling interval at 30 seconds minimum. Consider SSE (Server-Sent Events) for push-based updates instead of polling, which avoids the repeated-request overhead. If using polling, ensure the endpoint is cheap: just read from an in-memory dict, no DB or external calls.

**Phase to address:** Phase 4 (Web UI).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| In-memory round-robin state | Simpler code | State lost on every restart; items after first-N never searched | Never — add file persistence from the start |
| Single-page API fetch without pagination | Less code | Items 11+ never seen on default page size; breaks silently | Never — always paginate |
| API key as query param (`?apikey=`) | Works in browser testing | Key appears in every log line, Radarr/Sonarr access logs, browser history | Never — use `X-Api-Key` header exclusively |
| `SeriesSearch` instead of `SeasonSearch` | Simpler command | Indexer rate limit exhaustion; season packs not found | Never |
| Returning masked config on GET but full value available in response | Passes quick review | Any future developer adds the key to a debug endpoint without realizing | Never — establish zero-key-in-response rule unconditionally |
| No minimum interval enforcement | User flexibility | Users set 1-minute intervals, hammer indexers, get banned | Never — enforce a minimum of 5 minutes with documentation recommending 60 |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Radarr `POST /api/v3/command` | Using command name `MovieSearch` (singular) | Use `MoviesSearch` (plural) with `movieIds: [int]` array |
| Sonarr `POST /api/v3/command` | Using `SeriesSearch` for whole-show search | Use `SeasonSearch` with `seriesId: int, seasonNumber: int` |
| Both apps, v4 | Missing `Content-Type: application/json` header on POST | Always set `Content-Type: application/json` explicitly |
| Both apps, all versions | Passing `apikey` as URL query parameter | Use `X-Api-Key: {key}` request header exclusively |
| Both apps | Assuming 200 OK = search actually ran successfully | 202 Accepted means command queued; check `/api/v3/command/{id}` for completion status |
| Both apps | Fetching all wanted items in one request | Use paginated requests with `page` + `pageSize=100` and iterate until all pages loaded |
| Docker networking | Using `http://localhost:7878` as Radarr URL | Use container service name (`http://radarr:7878`) or host IP |
| Radarr/Sonarr version detection | Assuming API shape is stable across versions | Query `/api/v3/system/status` on startup; log `version` for diagnostics |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Fetching wanted list on every search trigger instead of once per cycle | Radarr/Sonarr hit with N reads per cycle | Fetch once at cycle start, cache for duration of cycle | Any library size — unnecessary from day one |
| HTTP client not reused across requests | Slow response times; new TCP connection per request | Use a single `httpx.AsyncClient` instance with keep-alive for the app lifetime | More noticeable as cycle frequency increases |
| No timeout on httpx requests | Search cycle hangs indefinitely if Radarr is slow | Set `httpx.Timeout(connect=5.0, read=30.0, write=10.0)` | Any time Radarr takes longer than expected |
| SSE connections accumulate without cleanup | Memory grows over time with open tabs | Implement connection cleanup on client disconnect; use async generators with `try/finally` | Multiple browser tabs or long-running sessions |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Any HTTP response body contains API key values | API key exposure to anyone who can reach the UI or intercept traffic; exact attack vector that made Huntarr dangerous | Strict server-side rule: never serialize API key values into response JSON |
| API key in URL query parameter | Key appears in Radarr/Sonarr access logs, Python httpx debug logs, Docker log output, browser history | Always use `X-Api-Key` header |
| API key stored in Docker environment variable | Visible in `docker inspect`, process environment, docker-compose.yml committed to git | Store in config file on Docker volume; read from file at startup, not from env |
| Config file COPY'd into Docker image | Keys baked into image layers, recoverable via `docker history` | Volume-mount config only; never COPY it during build |
| HTTP debug logging enabled in production | Full request/response with headers (including `X-Api-Key`) in Docker logs | Disable httpx debug logging; log actions not HTTP wire traffic |
| Startup validation skipped | Misconfigured keys silently fail; user assumes tool is working | Test connectivity on startup; surface failure in UI |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No visible indication of last search time | User cannot tell if the tool is working | Show "Last searched: 3 minutes ago" prominently; update via htmx poll |
| Error from Radarr/Sonarr only visible in Docker logs | Users don't know searches are failing | Surface connectivity status and last error in the UI status area |
| Round-robin position shown as raw index | Confusing ("Position: 47") | Show "Searching item 47 of 312 wanted movies" |
| Config save requires container restart | Users change intervals and wonder why nothing happened | Apply new intervals immediately without restart; reload config in-process |
| "Search All Now" button with no rate-limit warning | Users click it, hammer indexers, get banned | Either omit the button or show a warning about indexer limits before triggering |

---

## "Looks Done But Isn't" Checklist

- [ ] **API key security:** Verify that GET /api/config (or similar) returns masked keys, not real values — check with curl, not just the UI
- [ ] **Round-robin persistence:** Stop the Docker container, restart it, verify round-robin resumes from saved position, not position 0
- [ ] **Pagination:** Add 15+ items to Radarr wanted list, verify all 15 are included in the fetched list (catches missing pagination with default pageSize=10)
- [ ] **Season-level search:** Add a multi-season show with missing episodes to Sonarr, trigger automation, verify Sonarr activity shows `SeasonSearch` commands (not `SeriesSearch` or individual episode searches)
- [ ] **Docker networking:** Deploy with docker-compose, configure Radarr URL as `localhost`, verify a clear error message appears rather than a cryptic connection refused
- [ ] **Indexer safety:** Set a 1-minute interval and verify the tool enforces the configured minimum, or documents clearly why not
- [ ] **Log cleanliness:** Enable application logging, trigger a search cycle, grep logs for API key values — none should appear
- [ ] **Version compatibility:** Test against both Sonarr v3 and v4 if possible; verify commands return 202 Accepted

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| API key exposed in HTTP responses | HIGH | Rotate all *arr API keys immediately; audit what was accessible; rebuild with correct implementation |
| Indexer ban from search flooding | MEDIUM | Change IP (if dynamic) or wait for ban expiration (hours to days); reduce default intervals; some indexers offer manual unban via support ticket |
| Round-robin state loss | LOW | State resets to 0; tool continues working but starts from beginning of list — no data loss |
| Wrong Sonarr command (SeriesSearch vs SeasonSearch) | LOW | Fix command name in code; no persistent damage, just ineffective searches |
| API key baked into Docker image | HIGH | Delete image from registry; rotate API keys; rebuild with volume-mounted config only |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| API keys in HTTP responses | Phase 1 (Core API client + config) | curl all GET endpoints, confirm no key values in response |
| API keys in logs | Phase 1 (Core API client + config) | Run with debug logging, grep logs for key values |
| Wrong Radarr command names | Phase 1 (Core API client) | Check Radarr activity queue shows commands after trigger |
| Wrong Sonarr command (SeriesSearch) | Phase 2 (Search implementation) | Sonarr activity shows SeasonSearch, not SeriesSearch |
| Indexer flooding defaults | Phase 2 (Scheduler) | Default config review; minimum interval enforcement |
| Round-robin state not persisted | Phase 2 (Scheduler + round-robin) | Restart container, verify position resumes |
| Wanted list pagination | Phase 2 (Wanted list fetching) | Library >10 items, verify all fetched |
| APScheduler event loop conflict | Phase 2 (Scheduler) | Scheduler jobs fire reliably after app start |
| Docker networking URL confusion | Phase 3 (Docker packaging) | Test with localhost URL, verify error message |
| Config file in Docker image | Phase 3 (Docker packaging) | `docker history` shows no config file layers |
| htmx polling overhead | Phase 4 (Web UI) | Status endpoint never calls Radarr/Sonarr; interval >= 30s |
| No startup connectivity check | Phase 1 (Core API client) | Misconfigure URL, verify UI shows clear error |

---

## Sources

- [Huntarr Security Review — rfsbraz/huntarr-security-review](https://github.com/rfsbraz/huntarr-security-review/blob/main/Huntarr.io_SECURITY_REVIEW.md) — PRIMARY: documented 21 vulnerabilities, 7 critical including API key exposure via unauthenticated endpoint (HIGH confidence — primary source)
- [Huntarr passwords and API keys exposed — Lemmy.World community discussion](https://lemmy.world/post/43496203/22308768) — Community analysis of Huntarr failure modes (HIGH confidence — multiple independent confirmations)
- [Huntarr security discussion — Hacker News](https://news.ycombinator.com/item?id=47128452) — Community lessons on OSS security practices
- [Indexers with API Limits — Sonarr Forums](https://forums.sonarr.tv/t/indexers-with-api-limits/5289) — Indexer rate limit documentation (MEDIUM confidence)
- [Too many API hits on indexer — Sonarr Forums](https://forums.sonarr.tv/t/too-many-api-hits-on-indexer/17466) — Real-world rate limit exhaustion reports (MEDIUM confidence)
- [Indexers: limit number of API requests — Radarr GitHub Issue #3184](https://github.com/Radarr/Radarr/issues/3184) — Official tracking of rate limit concerns (HIGH confidence)
- [How to set up indexers with limited API — TRaSH Guides](https://trash-guides.info/Prowlarr/prowlarr-setup-limited-api/) — Community best practice for rate limit avoidance (MEDIUM confidence)
- [Need help with v4 API command changes — Sonarr Forums](https://forums.sonarr.tv/t/need-some-help-with-changes-in-v4-api-commands/33092) — v3 to v4 breaking changes, Content-Type requirement (MEDIUM confidence — confirmed by multiple users)
- [Sonarr v4 Released — Sonarr Forums](https://forums.sonarr.tv/t/sonarr-v4-released/33089) — Official v4 release notes
- [MoviesSearch command not working — Radarr GitHub Issue #3315](https://github.com/Radarr/Radarr/issues/3315) — Command name gotchas (HIGH confidence — official repo)
- [Season search vs episode search — Sonarr Forums](https://forums.sonarr.tv/t/episodes-not-automatically-searched-at-season-level/27587) — Season-level search behavior (MEDIUM confidence)
- [Api Paging and filtering — Radarr GitHub Issue #5246](https://github.com/Radarr/Radarr/issues/5246) — Pagination behavior for large libraries (HIGH confidence)
- [Add /wanted/missing API endpoint — Radarr GitHub Issue #7704](https://github.com/Radarr/Radarr/issues/7704) — Wanted list API documentation (HIGH confidence)
- [Sonarr gets connection refused from localhost in Docker — linuxserver/docker-sonarr Issue #165](https://github.com/linuxserver/docker-sonarr/issues/165) — Docker networking pitfall (HIGH confidence — widely reproduced)
- [Docker Secrets documentation — Docker Docs](https://docs.docker.com/compose/how-tos/use-secrets/) — Secret management best practices (HIGH confidence — official)
- [AsyncIOScheduler won't run if initialized before uvicorn — APScheduler Issue #484](https://github.com/agronholm/apscheduler/issues/484) — Event loop initialization gotcha (HIGH confidence — official repo)
- [HTTPX Timeouts documentation](https://www.python-httpx.org/advanced/timeouts/) — HTTP client timeout configuration (HIGH confidence — official)
- [Radarr API OpenAPI spec](https://raw.githubusercontent.com/Radarr/Radarr/develop/src/Radarr.Api.V3/openapi.json) — Endpoint shapes and pagination parameters (HIGH confidence — official)

---
*Pitfalls research for: Radarr/Sonarr search automation (*arr ecosystem)*
*Researched: 2026-02-23*
