# Pitfalls Research

**Domain:** Closed-loop download tracking + tech debt for *arr search automation (v2.0 milestone)
**Researched:** 2026-02-24
**Confidence:** HIGH (history API behavior verified against OpenAPI spec and pyarr docs; integration pitfalls verified against codebase analysis; SQLite concurrency verified against official SQLite docs)

---

## Critical Pitfalls

### Pitfall 1: False Positive Grab Attribution -- Counting Organic Grabs as Fetcharr-Triggered

**What goes wrong:**
Fetcharr triggers a search for Movie X. Minutes later, polling the Radarr history endpoint finds a `grabbed` event for Movie X. Fetcharr marks it as "grabbed" and increments lifetime stats. But the grab was actually organic -- Radarr's own RSS sync grabbed it independently, or the user manually searched from the Radarr UI. Fetcharr takes credit for grabs it did not cause. Over time, lifetime stats become inflated and meaningless. The core requirement says "Lifetime stats only count fetcharr-triggered grabs, not organic Sonarr/Radarr activity."

**Why it happens:**
The Radarr/Sonarr history API returns all grab events for an item, regardless of what triggered them. There is no field that says "this grab was triggered by command ID X." The history record has `eventType`, `movieId`/`episodeId`, `date`, `downloadId`, and `sourceTitle` -- but no `triggeredByCommandId`. Developers assume "I searched for it, then it got grabbed, therefore I caused it" which is a temporal correlation fallacy.

**How to avoid:**
Use a tight time-window approach with these safeguards:
1. Record the exact UTC timestamp when each search command is issued (already stored in `search_history.timestamp`).
2. When polling history, only consider `grabbed` events whose `date` falls within a configurable window after the search timestamp (e.g., search_time to search_time + 30 minutes). Grabs outside this window are likely organic.
3. Store the `search_history.id` (the fetcharr DB row ID) alongside the search timestamp so grab events can be correlated back to a specific search entry.
4. For Sonarr season searches, a single `SeasonSearch` can produce multiple grab events (one per episode in the season). Track all of them against the same search entry.
5. Accept that this is probabilistic, not deterministic. Log when a grab is attributed and when one is skipped due to window expiry. Document that the window is configurable and that false positives are possible for items also on RSS watch lists.

**Warning signs:**
- Lifetime stats show a higher grabbed-rate than plausible (e.g., >80% of searches resulting in grabs)
- Grab events attributed to searches that happened hours ago
- No configurable window -- any grab for a searched item counts forever

**Phase to address:** Phase 1 (History polling + grab correlation) -- this is the foundational design decision for the entire tracking feature. Getting correlation wrong means every downstream metric is wrong.

---

### Pitfall 2: History Endpoint Pagination Mishandled -- Missing Grabs or Polling Entire History

**What goes wrong:**
Two failure modes:
1. **Under-fetching:** The Radarr/Sonarr history endpoint defaults to `pageSize=10`. If fetcharr polls for recent grabs with default pagination, it only sees the 10 most recent history events across ALL event types (renames, imports, deletes, grabs). During a busy period, 10 rename events can push the actual grab events off the first page, and fetcharr never sees them.
2. **Over-fetching:** Polling the full history endpoint without date bounds fetches the entire history, which grows unbounded. For a library with years of activity, this means multi-second responses and unnecessary load on the *arr application.

**Why it happens:**
Developers test with small libraries where the last 10 events include all grabs. In production, rename and import events vastly outnumber grab events, pushing grabs off the default first page. The OpenAPI spec shows `pageSize` defaults to 10, not 50 -- fetcharr's existing `get_paginated` uses 50, but a naive new history call might use API defaults.

**How to avoid:**
1. Use the `/api/v3/history` endpoint with `eventType` filter set to `1` (Grabbed). Both Radarr and Sonarr support `eventType` as a query parameter (integer enum value, not string). This dramatically reduces the result set.
2. For Radarr, prefer `/api/v3/history/movie?movieId={id}&eventType=grabbed` to scope to specific movies. For Sonarr, use the main `/api/v3/history` with `episodeId` or `seriesId` filter (Sonarr has `/api/v3/history/series?seriesId={id}`).
3. Use Radarr's `/api/v3/history/since?date={iso_date}` endpoint (if available) to scope to events since the last poll, rather than re-scanning full history.
4. Always explicitly set `pageSize` (use 50). Never rely on the API default of 10.
5. Track a "last polled" high-water mark (the most recent history event `id` or `date` seen) and only process events newer than that mark.

**Warning signs:**
- History polling does not filter by `eventType` -- fetching all event types
- No `pageSize` parameter in history API calls
- No high-water mark tracking -- every poll re-scans the same events
- History polling takes >2 seconds for small libraries

**Phase to address:** Phase 1 (History polling implementation) -- the polling strategy determines API load and correctness for the entire feature.

---

### Pitfall 3: Radarr vs. Sonarr History API Asymmetry -- Assuming Same Endpoints

**What goes wrong:**
Developers build the history polling for Radarr first, then copy-paste for Sonarr assuming the same endpoint structure. But the APIs differ:
- Radarr has `/api/v3/history/movie?movieId={id}` -- scoped to a single movie
- Sonarr has `/api/v3/history/series?seriesId={id}` -- scoped to a series (not episode)
- Radarr's enum: `MovieHistoryEventType` -- values: `unknown`(0), `grabbed`(1), `downloadFolderImported`(2), `downloadFailed`(3), `movieFileDeleted`(4), `movieFolderImported`(5), `movieFileRenamed`(6), `downloadIgnored`(7)
- Sonarr's enum: `EpisodeHistoryEventType` -- values: `unknown`(0), `grabbed`(1), `seriesFolderImported`(2), `downloadFolderImported`(3), `downloadFailed`(4), `episodeFileDeleted`(5), `episodeFileRenamed`(6), `downloadIgnored`(7)
- The integer values for `grabbed` are both `1`, but `downloadFolderImported` is `2` in Radarr and `3` in Sonarr. Hard-coding integer values without per-app mapping causes import detection to silently break.

**Why it happens:**
The base client pattern (both apps use `/api/v3/`) creates the illusion of identical APIs. The enum values look the same for `grabbed` (both `1`), so initial testing passes. The divergence only surfaces when checking import/completion events, which are needed for "partial" vs "grabbed" determination.

**How to avoid:**
Define separate enum mappings per app in code. Do not share a single `EVENT_TYPE_GRABBED = 1` constant across both apps without verification. Create app-specific history client methods on `RadarrClient` and `SonarrClient` rather than a shared base method. Verify both Radarr and Sonarr enum values against official sources before implementation. For v2.0, the primary need is `grabbed` (value `1` in both) -- but document the full mapping for future use.

**Warning signs:**
- A single shared constant like `GRABBED_EVENT_TYPE = 1` used for both apps without app context
- Copy-pasted history endpoint paths without checking per-app variants
- Import detection returning wrong results for one app but not the other

**Phase to address:** Phase 1 (History polling) -- model the per-app differences in the client layer from the start.

---

### Pitfall 4: Sonarr Season Search Correlation Complexity -- One Search, Many Grabs

**What goes wrong:**
Fetcharr triggers a `SeasonSearch` for "Breaking Bad - Season 3" (10 episodes missing). Sonarr may respond with:
- 10 individual episode grabs (one per episode)
- 1 season pack grab (all 10 episodes in one)
- 5 episode grabs + 0 for the other 5 (partial)
- A season pack grab that also covers episodes already owned (upgrade scenario)

Determining "grabbed" vs "partial" vs "unresolved" requires understanding which episodes were missing BEFORE the search, then checking how many of those specific episodes were grabbed. A naive approach that counts grab events against the total season episode count (not missing episode count) will always show "partial" for seasons where only some episodes were missing.

**Why it happens:**
The search is at season level but grabs are at episode level. There is no 1:1 relationship between "search" and "grab." Developers model it as "1 search = 1 expected grab" which works for Radarr (1 movie = 1 grab) but fails for Sonarr.

**How to avoid:**
1. When recording a Sonarr search in `search_history`, also record the count of missing episodes at search time (from the wanted/missing list). Store this as metadata (e.g., `detail` field or a new column).
2. When polling for grabs, count distinct `episodeId` values with `eventType=grabbed` for the `seriesId` + `seasonNumber` within the correlation window.
3. Compare grabbed episode count to the recorded missing episode count:
   - `grabbed_count >= missing_count` -> outcome = "grabbed"
   - `0 < grabbed_count < missing_count` -> outcome = "partial"
   - `grabbed_count == 0` after window expires -> outcome = "unresolved"
4. For season packs: Sonarr creates one grab event per episode within the pack, so counting distinct episodes still works.

**Warning signs:**
- Season searches always show "partial" even when season packs are grabbed
- No missing-episode-count recorded at search time
- Grab detection treats season searches identically to movie searches

**Phase to address:** Phase 2 (Outcome badge logic) -- requires Phase 1 history polling to be working first.

---

### Pitfall 5: SQLite Write Contention When Adding History Polling Alongside Search Writes

**What goes wrong:**
The current codebase uses connection-per-operation with aiosqlite (`async with aiosqlite.connect(db_path) as db`). Every `insert_search_entry` call opens a new connection, writes, and closes. This works because writes only happen during search cycles (sequential, under `search_lock`). Adding history polling introduces a second writer: the polling task runs on its own schedule and needs to UPDATE existing rows with grab outcomes. If a search cycle and a history poll overlap, both try to write simultaneously. SQLite's default journal mode allows only one writer at a time; the second writer gets `SQLITE_BUSY` ("database is locked") after a 5-second default timeout.

**Why it happens:**
The connection-per-operation pattern is fine for single-writer scenarios. The v1.x architecture has exactly one writer (the search cycle, protected by `search_lock`). Adding a second async task that writes to the same database breaks the single-writer assumption without any code signaling the problem -- it works in testing (low concurrency) and fails intermittently in production (higher concurrency, longer cycles).

**How to avoid:**
Before adding any new writers, make two changes:
1. **Enable WAL mode:** Execute `PRAGMA journal_mode=WAL` during `init_db()`. WAL mode allows concurrent readers while a writer is active, and reduces writer-vs-writer contention to just the write itself (not the full transaction). This is a one-line change with no downside for local SQLite.
2. **Set busy timeout:** Execute `PRAGMA busy_timeout=5000` on each connection open. This makes SQLite retry for up to 5 seconds instead of immediately failing with SQLITE_BUSY.
3. **Optionally share the search_lock:** If the history poller needs to update rows, have it acquire the same `search_lock` before writing. This serializes writes but guarantees no contention. The lock overhead is negligible for this workload (writes happen every 30+ minutes).
4. **Defer connection pooling:** aiosqlitepool exists but is overkill for fetcharr's write frequency (~10 writes per cycle, cycles every 30 minutes). WAL + busy timeout is sufficient. Connection pooling adds complexity without meaningful benefit at this scale.

**Warning signs:**
- Any `aiosqlite.OperationalError: database is locked` in logs
- History poller and search cycle running at the same time without coordination
- New async task writes to DB without acquiring `search_lock`

**Phase to address:** Phase 1 (DB preparation) -- enable WAL mode and busy timeout BEFORE adding the history poller. This is a prerequisite, not an afterthought.

---

### Pitfall 6: CSRF Middleware Scope Too Narrow -- Only Covering Some POST Endpoints

**What goes wrong:**
The existing `OriginCheckMiddleware` covers all POST requests via Origin/Referer validation. The v1.2 deep review flagged that the settings POST endpoint lacks CSRF protection. But the middleware IS applied -- the actual gap is more subtle: the middleware allows requests when NEITHER Origin NOR Referer is present (the "no header" case). This is correct for same-origin browser requests but means a CSRF attack from a non-browser context (e.g., `curl` or a script on the local network) bypasses the check entirely. For a no-auth app, this means anyone on the network can POST to `/settings` or `/api/search-now/{app}` without any validation.

**Why it happens:**
The Origin/Referer approach is the right pattern for a no-auth, no-session app. But the "allow when neither header present" clause exists because same-origin `<form>` submissions in some browsers omit both headers. Removing this clause would break legitimate form submissions. The real v1.2 tech debt item is not "add CSRF" but "ensure the existing CSRF middleware is correctly scoped" -- specifically, tightening the "no header" case is the actual fix.

**How to avoid:**
1. For the settings POST endpoint specifically, accept that the middleware already covers cross-origin browser attacks (the primary threat model).
2. The "no header" case is acceptable for a local-network-only tool with no auth. Document this as an intentional design decision, not a gap.
3. If tighter CSRF is desired, add a per-request custom header requirement (e.g., `X-Fetcharr-Request: 1`) on mutating endpoints. htmx can send custom headers via `hx-headers`. This blocks vanilla `<form>` CSRF without requiring cookies/sessions.
4. Do NOT add a cookie-based CSRF library (fastapi-csrf-protect, etc.) -- the app has no sessions, no cookies, and no auth. Adding cookie-based CSRF to a sessionless app creates complexity with zero security benefit.

**Warning signs:**
- Adding a CSRF token library to a sessionless app
- Removing the "allow when neither header present" clause (breaks form submissions)
- Not testing that htmx AJAX requests still pass the middleware after changes

**Phase to address:** Tech debt phase -- this is a documentation + minor hardening task, not a rewrite. Address alongside rate limiting.

---

## Moderate Pitfalls

### Pitfall 7: Rate Limiting on Search-Now Without Considering the Scheduler

**What goes wrong:**
The tech debt item says "rate limiting on search-now endpoint." A naive implementation adds a decorator like `@limiter.limit("1/minute")` to the `/api/search-now/{app_name}` endpoint. But the endpoint already acquires `search_lock` (shared with the scheduler). If a user clicks "Search Now" right before a scheduled cycle fires, the lock serializes them -- the manual search runs, then the scheduled search runs immediately after. The rate limiter only blocks repeated manual clicks, not the combined load of manual + scheduled searches hitting indexers in rapid succession.

**Why it happens:**
Rate limiting and scheduling are treated as independent concerns. The search-now endpoint fires a full search cycle (same as the scheduler). From the indexer's perspective, two full cycles back-to-back is the same whether triggered manually or scheduled.

**How to avoid:**
1. Rate limit the search-now endpoint to prevent button-mashing: 1 request per 60 seconds per app is reasonable.
2. Use a simple in-memory approach -- a dict of `{app_name: last_trigger_time}` checked before running the cycle. This is simpler than adding slowapi as a dependency.
3. After a manual search-now, consider rescheduling the next automatic cycle to avoid back-to-back runs. APScheduler supports `scheduler.reschedule_job()` to push the next run time forward.
4. Do NOT add Redis-backed rate limiting or slowapi -- this is a single-user local tool. An in-memory timestamp comparison is sufficient and dependency-free.

**Warning signs:**
- Adding slowapi or Redis for rate limiting a single endpoint
- Rate limiter only on the HTTP endpoint, not considering scheduler interaction
- No feedback to the user when rate-limited (silent failure)

**Phase to address:** Tech debt phase -- straightforward implementation, but must consider scheduler interaction.

---

### Pitfall 8: History Polling Interval Too Aggressive -- Hammering *arr Apps

**What goes wrong:**
History polling needs to check for grab events after each search. If it polls every 30 seconds (like htmx UI polling), it generates 2 API calls per poll (one per app) x 2 polls per minute = 4 extra API calls per minute, indefinitely. This doubles the API traffic to Radarr/Sonarr for no benefit outside the correlation window. Worse, if history polling paginates through results, each poll could be multiple requests.

**Why it happens:**
Developers want near-real-time grab detection. The htmx UI already polls every 30 seconds, so "add another 30-second poll" feels natural. But UI polling reads from local state (cheap); history polling makes outbound HTTP calls to external apps (expensive).

**How to avoid:**
1. Poll history only after a search cycle completes, not on a fixed timer. Schedule a one-shot history check 5-10 minutes after each search cycle.
2. Use Radarr's `/api/v3/history/since?date={last_search_time}` or filter by `movieId` to scope the query -- do not fetch all history.
3. For Sonarr, use `/api/v3/history/series?seriesId={id}` scoped to the specific series that was searched.
4. After the correlation window expires (e.g., 30 minutes post-search), stop polling for that search. Mark un-correlated searches as "unresolved."
5. A reasonable pattern: poll at 5 minutes post-search, then 15 minutes, then 30 minutes (exponential backoff). Three polls per search, not continuous.

**Warning signs:**
- History polling runs on a fixed interval independent of search cycles
- Polling frequency is < 5 minutes
- No scoping by movieId/seriesId -- fetching all history every poll
- Polling continues indefinitely for old searches

**Phase to address:** Phase 1 (History polling design) -- get the polling schedule right before building outcome logic on top.

---

### Pitfall 9: Graceful Shutdown Not Awaiting In-Flight Search Cycles

**What goes wrong:**
The current lifespan calls `scheduler.shutdown(wait=False)` and closes clients. If a search cycle is in progress when shutdown is triggered, it gets interrupted mid-cycle. The state may have been partially updated (some cursors advanced, some not). The interrupted search entries are in the DB but the state file may not have been saved, causing duplicate searches on restart. Adding history polling makes this worse -- a poll might be mid-UPDATE when shutdown fires.

**Why it happens:**
`scheduler.shutdown(wait=False)` is fast but unclean. `wait=True` would block until running jobs complete, but APScheduler 3.x `wait=True` can hang if a job is stuck. The current approach is a pragmatic choice that works for fire-and-forget searches but becomes problematic when state mutations (cursor advances, outcome updates) need to be atomic.

**How to avoid:**
1. Register a shutdown signal handler (SIGTERM, SIGINT) that sets a "shutting down" flag.
2. Check this flag at the start of each search cycle and history poll -- if set, skip the cycle and return early.
3. Use `scheduler.shutdown(wait=True)` with a short timeout. APScheduler 3.x does not support a timeout parameter on shutdown, but you can implement it by: (a) setting the flag, (b) giving running jobs 10 seconds to finish, (c) then shutting down.
4. Always save state after each cycle completes (already done). Ensure the save is the last operation in the cycle, not interleaved.
5. For the history poller, ensure UPDATE operations are idempotent -- re-applying the same grab attribution should be a no-op.

**Warning signs:**
- `scheduler.shutdown(wait=False)` with no signal handling
- State file saved mid-cycle rather than at cycle end
- Docker stop takes exactly 10 seconds (hitting SIGKILL because SIGTERM was not handled)

**Phase to address:** Tech debt phase (graceful shutdown) -- implement alongside health check endpoint.

---

### Pitfall 10: Bounded History Pruning Deleting Rows Before Grab Correlation Completes

**What goes wrong:**
The current `insert_search_entry` auto-prunes to 500 rows after each insert. If fetcharr searches many items per cycle (e.g., 10 missing + 10 cutoff = 20 per app = 40 total per cycle), the 500-row limit means the oldest entries are pruned after ~12 cycles. The history poller needs to UPDATE these rows with grab outcomes, but if the row has been pruned before the poller runs, the grab attribution is lost. The lifetime stats increment but the individual search entry no longer exists.

**Why it happens:**
The 500-row limit was designed for a "fire-and-forget" model where old search entries have no future use. With closed-loop tracking, entries have a lifecycle: `searched` -> `grabbed`/`partial`/`unresolved`. Pruning must not delete entries that are still in the "searched" (pending) state.

**How to avoid:**
1. Change the pruning logic: do not delete rows that have `outcome = 'searched'` (still pending correlation). Only prune rows with terminal outcomes (`grabbed`, `partial`, `unresolved`, `failed`).
2. Add a secondary safety limit: if pending rows exceed a threshold (e.g., 200), mark the oldest pending rows as `unresolved` (window expired) and then prune normally.
3. Make the pruning limit configurable (the tech debt item already calls for this). Default to 1000 rows for v2.0 since rows now carry more value.
4. Consider separating the pruning from the insert path -- run pruning on a schedule (e.g., once per hour) rather than on every insert.

**Warning signs:**
- Grab events found in *arr history but no corresponding search entry exists in fetcharr DB
- Lifetime stats show grabs for searches that no longer appear in the history UI
- High search volume causes rapid pruning (entries disappear within hours)

**Phase to address:** Phase 1 (DB schema changes) -- adjust pruning logic BEFORE adding the history poller that depends on rows persisting.

---

### Pitfall 11: Lifetime Stats Double-Counting on Container Restart

**What goes wrong:**
Lifetime stats (movies found, episodes found, etc.) need to persist across restarts. If stored in `state.json`, they load on startup. If the history poller re-processes old grab events on startup (because the high-water mark was not persisted), the same grabs get counted again, inflating lifetime stats.

**Why it happens:**
The poller's "last checked" timestamp or event ID lives in memory. On restart, it resets and re-scans history from the beginning (or from some default window), finding grabs that were already counted in a previous run.

**How to avoid:**
1. Store lifetime stats in SQLite (not `state.json`), in a dedicated `stats` table.
2. Persist the history polling high-water mark (last seen history event ID or timestamp) in the same `stats` table or in `state.json`.
3. On startup, load the high-water mark and resume polling from that point. Never re-process events before the high-water mark.
4. Make lifetime stats derivable from the search_history table where possible: `SELECT COUNT(*) FROM search_history WHERE outcome = 'grabbed' AND app = 'Radarr'`. This makes stats self-correcting -- they can be recalculated from the source of truth rather than maintained as a separate counter.

**Warning signs:**
- Lifetime stats stored as a counter in state.json with no deduplication
- No high-water mark persisted for the history poller
- Stats jump after container restart

**Phase to address:** Phase 2 (Lifetime stats) -- design the storage model to prevent double-counting from the start.

---

## Minor Pitfalls

### Pitfall 12: Health Check Endpoint Returning 200 When *arr Apps Are Unreachable

**What goes wrong:**
A `/health` endpoint that always returns 200 is useless for Docker HEALTHCHECK. If Radarr has been unreachable for 2 hours, the container still appears healthy. Docker/orchestrators think everything is fine and do not restart the container or alert.

**Prevention:**
Health check should report "unhealthy" if any enabled app has been unreachable for more than N consecutive cycles. The app already tracks `connected` and `unreachable_since` in state -- the health endpoint can check these. Return 200 for healthy, 503 for unhealthy. Docker HEALTHCHECK should use `curl --fail http://localhost:8080/health`.

**Phase to address:** Tech debt phase.

---

### Pitfall 13: Request Timeouts Not Applied to History Polling Calls

**What goes wrong:**
The existing `ArrClient` uses `httpx.Timeout(30.0)` for all requests. History API calls on large libraries can take longer than 30 seconds if the *arr app's database is large or under load. A timeout during history polling means grab events are missed for that poll cycle.

**Prevention:**
Use the same 30-second timeout but handle timeout errors gracefully in the history poller -- log a warning and retry on the next poll, rather than failing the entire correlation. Do not increase the timeout just for history calls; if history calls consistently timeout, the query is too broad (fix the query scope, not the timeout).

**Phase to address:** Phase 1 (History polling implementation).

---

### Pitfall 14: Configurable pageSize Not Propagated to New History API Calls

**What goes wrong:**
The tech debt item "Configurable pageSize defaults" applies to the existing `get_paginated()` calls for wanted/missing and wanted/cutoff. When adding history polling, developers may forget to use the same configurable pageSize for history API calls, leaving them hardcoded to a different value.

**Prevention:**
Add the pageSize configuration to the `GeneralConfig` model once, and use it everywhere -- wanted list fetching AND history polling. The ArrClient base class's `get_paginated()` already accepts `page_size` as a parameter; thread the config value through consistently.

**Phase to address:** Tech debt phase (configurable pageSize).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Fixed correlation window (no config) | Simpler code | Users with slow indexers miss grabs that arrive after window | MVP only -- make configurable by v2.1 |
| Lifetime stats as in-memory counter | No DB schema change | Stats lost on restart or double-counted | Never -- use SQLite or derivable query |
| Single `GRABBED_EVENT_TYPE = 1` for both apps | Less code | Breaks when checking other event types with different enum values | Never -- use per-app enum mapping |
| History poll on fixed timer | Simple scheduling | Wasted API calls when no searches pending | MVP only -- switch to post-search polling |
| Prune all rows equally regardless of outcome | Simpler DELETE | Loses pending entries before correlation | Never -- exclude pending rows from pruning |
| slowapi for rate limiting | Library handles edge cases | Adds a dependency for one endpoint on a single-user tool | Never for this project -- use in-memory timestamp |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Radarr history endpoint | Using `/api/v3/history` without `eventType` filter | Filter with `eventType=1` (grabbed) to avoid processing rename/import noise |
| Radarr per-movie history | Using paginated `/api/v3/history` for specific movies | Use `/api/v3/history/movie?movieId={id}` for targeted queries |
| Sonarr per-series history | Assuming same endpoint as Radarr | Use `/api/v3/history/series?seriesId={id}` -- different endpoint name |
| Sonarr eventType enum values | Assuming same integer values as Radarr | `downloadFolderImported` is 2 in Radarr but 3 in Sonarr -- verify per-app |
| History record `date` field | Treating as local time | Always UTC ISO 8601 format (e.g., `2026-02-24T10:30:00Z`) -- parse accordingly |
| History record `downloadId` field | Assuming always present | Field is optional (omitempty) -- may be null/absent for some event types |
| aiosqlite concurrent writes | Opening new connection for each write without WAL | Enable WAL mode + busy_timeout in `init_db()` before adding concurrent writers |
| SQLite schema migration | Using ALTER TABLE without duplicate column guard | Already handled in codebase -- keep the `contextlib.suppress(Exception)` pattern for new columns |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Polling full history without movieId/seriesId filter | Each poll fetches hundreds/thousands of records | Always scope history queries by item ID + eventType | Any library with >100 items |
| History polling on a 30-second fixed timer | 4+ outbound API calls per minute, indefinitely | Poll only after search cycles, with exponential backoff (5m, 15m, 30m) | Immediately -- continuous unnecessary load |
| Lifetime stats computed via full table scan | Dashboard load slows as search_history grows | Use a dedicated stats table or cached counters updated on writes | >5000 search history rows |
| Opening/closing aiosqlite connections on every DB operation | Connection overhead accumulates | Enable WAL mode to reduce lock contention; keep connection-per-op but with WAL | Under concurrent read+write load (UI polling + history poller + search cycle) |
| Auto-pruning on every INSERT (current 500 row DELETE) | DELETE runs a subquery on every insert | Prune on a schedule (hourly) or at lower frequency, not per-insert | Negligible now but compounds with higher write frequency |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| History API responses logged with full sourceTitle | Source titles can contain sensitive info (indexer names, release group details) | Apply the same loguru redacting sink pattern to history log output |
| Rate limiter exposing timing information | Rate limit headers reveal internal scheduling to network observers | Do not add `X-RateLimit-*` headers on a local-network tool -- return 429 with a human-readable message only |
| CSRF token library added to sessionless app | Complexity without benefit; cookie-based CSRF requires cookies/sessions that don't exist | Keep Origin/Referer middleware; add custom header requirement if tighter CSRF needed |
| downloadId field stored in DB without sanitization | downloadId comes from *arr API and could contain unexpected values | Validate downloadId as alphanumeric string before storage; truncate to reasonable length |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Outcome badges update with no visual feedback | User sees "searched" badge, refreshes, still "searched" -- doesn't know when to expect an update | Show "checking..." state during correlation window; tooltip: "Checking for grabs (5 min remaining)" |
| Lifetime stats with no reset option | Counter grows forever; user cannot reset after testing or reconfiguration | Add a "reset stats" action in settings (with confirmation) |
| "Unresolved" badge with no explanation | User sees "unresolved" and thinks something is broken | Tooltip: "No download detected within 30 minutes of search -- this is normal if no matching release was available" |
| Partial badge with no detail | "Partial" is ambiguous -- partial what? | Show "3 of 7 episodes grabbed" or "grabbed but below cutoff" in the detail field |
| History page shows raw "grabbed"/"partial" strings | Not visually distinct from "searched" | Use color-coded badges: green for grabbed, yellow for partial, gray for unresolved, red for failed |

---

## "Looks Done But Isn't" Checklist

- [ ] **Grab correlation:** Trigger a search, wait for grab, verify the specific search entry gets updated (not just lifetime stats) -- test with both Radarr and Sonarr
- [ ] **False positive prevention:** Have Radarr RSS grab something organically while fetcharr is running -- verify fetcharr does NOT count it as its own grab
- [ ] **Sonarr partial detection:** Search a season with 5 of 10 episodes missing. Grab 3 episodes. Verify outcome shows "partial (3 of 5)" not "partial (3 of 10)"
- [ ] **Container restart stats:** Check lifetime stats, restart container, verify stats are unchanged (no reset, no double-count)
- [ ] **Pruning safety:** Fill history to >500 rows with "searched" outcomes. Verify pending rows are NOT pruned before correlation completes
- [ ] **WAL mode enabled:** After init_db, verify `PRAGMA journal_mode` returns `wal`, not `delete`
- [ ] **Rate limiting feedback:** Click "Search Now" twice rapidly. Verify second click returns a clear "please wait" message, not a silent failure
- [ ] **Health check accuracy:** Disconnect Radarr (wrong URL), wait 2+ cycles, verify `/health` returns 503
- [ ] **Graceful shutdown:** Run `docker stop` during an active search cycle. Verify state is consistent on restart (no duplicate searches, cursors correct)
- [ ] **History API scoping:** In debug logs, verify history polls use `movieId`/`seriesId` filters, not unscoped full-history fetches

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| False positive grab attribution | LOW | Reset lifetime stats; mark affected entries as "unresolved"; tighten correlation window |
| SQLite "database is locked" errors | LOW | Enable WAL mode (one-line PRAGMA); restart container; no data loss |
| Lifetime stats double-counted after restart | LOW | Recalculate stats from search_history table: `SELECT COUNT(*) WHERE outcome='grabbed'` |
| Pruned rows missing grab correlation | MEDIUM | Lost data cannot be recovered; increase row limit; adjust pruning to exclude pending rows |
| History polling hammering *arr apps | LOW | Increase poll interval; add eventType filter; restart -- no permanent damage |
| CSRF changes break form submissions | LOW | Revert middleware change; test in browser before deploying |
| Graceful shutdown data corruption | MEDIUM | Delete state.json and let cursors reset to 0; search_history in SQLite is durable |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| False positive grab attribution (#1) | Phase 1 (History polling + correlation) | Manual test: organic grab not attributed to fetcharr |
| History pagination mishandled (#2) | Phase 1 (History polling) | Debug logs show `eventType=1` filter and explicit `pageSize` |
| Radarr/Sonarr API asymmetry (#3) | Phase 1 (History polling) | Both apps return grabs correctly; import detection verified per-app |
| Sonarr season correlation (#4) | Phase 2 (Outcome badges) | Season search with partial grabs shows correct "X of Y" count |
| SQLite write contention (#5) | Phase 1 (DB prep, before polling) | `PRAGMA journal_mode` returns `wal`; no locked errors under concurrent access |
| CSRF middleware scope (#6) | Tech debt phase | Document design decision; add custom header if desired |
| Rate limiting scope (#7) | Tech debt phase | Manual search + immediate scheduled cycle do not back-to-back hammer indexers |
| History polling frequency (#8) | Phase 1 (History polling) | Polls scoped to post-search windows, not continuous |
| Graceful shutdown (#9) | Tech debt phase | `docker stop` completes cleanly; state consistent on restart |
| Pruning vs correlation (#10) | Phase 1 (DB schema) | Pending rows survive past 500-row mark |
| Stats double-counting (#11) | Phase 2 (Lifetime stats) | Container restart preserves exact stat values |
| Health check accuracy (#12) | Tech debt phase | Unreachable app -> 503 on /health |
| History timeout handling (#13) | Phase 1 (History polling) | Timeout during history poll logged as warning, not crash |
| Configurable pageSize (#14) | Tech debt phase | Single config value flows to both wanted-list and history API calls |

---

## Sources

- [Radarr OpenAPI Spec](https://raw.githubusercontent.com/Radarr/Radarr/develop/src/Radarr.Api.V3/openapi.json) -- History endpoint query parameters: `page`, `pageSize`, `eventType` (int array), `movieIds` (int array), `downloadId`; `/api/v3/history/movie` endpoint with `movieId` + `eventType` filter; `/api/v3/history/since` with date parameter (HIGH confidence -- official specification)
- [Sonarr History EventType Issue #3587](https://github.com/Sonarr/Sonarr/issues/3587) -- Confirmed Sonarr `HistoryEventType` enum: Unknown(0), Grabbed(1), SeriesFolderImported(2), DownloadFolderImported(3), DownloadFailed(4), EpisodeFileDeleted(5), EpisodeFileRenamed(6), DownloadIgnored(7); confirmed `eventType` query parameter works on v3 API (HIGH confidence -- official issue tracker)
- [pyarr Radarr Documentation](https://docs.totaldebug.uk/pyarr/modules/radarr.html) -- Confirmed Radarr `MovieHistoryEventType` values: unknown, grabbed, downloadFolderImported, downloadFailed, movieFileDeleted, movieFolderImported, movieFileRenamed, downloadIgnored; `get_movie_history(id, event_type)` method signature (HIGH confidence -- maintained library reflecting official API)
- [pyarr Sonarr Documentation](https://docs.totaldebug.uk/pyarr/modules/sonarr.html) -- Sonarr `get_history()` parameters: page, page_size, sort_key, sort_dir, id (episode filter) (MEDIUM confidence -- library docs)
- [Sonarr History/Series Issue #4727](https://github.com/Sonarr/Sonarr/issues/4727) -- `/api/v3/history/series` endpoint with `seriesId` parameter; `includeSeries` and `includeEpisode` query params (MEDIUM confidence -- issue tracker)
- [Radarr Go Client Record Struct](https://pkg.go.dev/github.com/SkYNewZ/radarr) -- Confirmed history record fields: `movieId`, `sourceTitle`, `quality`, `date`, `eventType`, `downloadId` (omitempty) (MEDIUM confidence -- third-party client reflecting API)
- [Sonarr Go Client HistoryRecord](https://pkg.go.dev/golift.io/starr/sonarr) -- Confirmed Sonarr history record fields including `seriesId`, `episodeId`, `date`, `downloadId`, `eventType` (MEDIUM confidence -- third-party client)
- [SQLite WAL Mode Documentation](https://sqlite.org/wal.html) -- WAL mode allows concurrent readers with writers; single writer at a time; `PRAGMA journal_mode=WAL` (HIGH confidence -- official SQLite docs)
- [aiosqlite "database is locked" prevention](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/) -- WAL mode + busy_timeout resolves 99% of concurrent write issues (MEDIUM confidence -- well-sourced technical blog)
- [aiosqlitepool GitHub](https://github.com/slaily/aiosqlitepool) -- Connection pooling for aiosqlite; useful for >5-10 req/s; overkill for fetcharr's workload (LOW confidence -- assessed against project requirements)
- [SlowAPI Rate Limiter](https://github.com/laurentS/slowapi) -- Starlette/FastAPI rate limiting; good for multi-user APIs; overkill for single-user local tool (MEDIUM confidence -- assessed against project requirements)
- [Radarr DeepWiki REST API](https://deepwiki.com/radarr/radarr/4.1-rest-api) -- `/api/v3/history/since` endpoint for changes since a specific date (MEDIUM confidence -- community wiki)
- [Sonarr/Sonarr Command Extension Issue #4759](https://github.com/Sonarr/Sonarr/issues/4759) -- Command API returns command ID; no direct link from command to resulting history events (MEDIUM confidence -- confirms absence of command-to-grab correlation)
- Fetcharr codebase analysis (2026-02-24) -- Direct reading of `db.py`, `engine.py`, `state.py`, `routes.py`, `middleware.py`, `scheduler.py` to identify current patterns and integration points (HIGH confidence -- primary source)

---
*Pitfalls research for: Closed-loop download tracking + tech debt for *arr search automation (v2.0)*
*Researched: 2026-02-24*
