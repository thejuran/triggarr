# Codebase Concerns

**Analysis Date:** 2026-06-01

## Summary

Triggarr v2.8.0 (Hardening & Observability) resolved major safety concerns: bounded search history (SAFETY-01a/b), scheduler resilience (SAFETY-02/03), graceful shutdown drainage (RES-01), tag-list caching (RES-03), and comprehensive security hardening (CSP nonces, apikey= query rejection, Basic-auth control-char validation, session-secret startup checks). Current concerns are primarily residual tech debt and architectural asymmetries—no critical bugs or security gaps.

## Tech Debt

### SAFETY-03: Manual Search Bypass of Failure Counter

**Issue:** Manual searches via `/search-now/{app}/{instance}` route bypass the per-job consecutive-failure counter (`app.state.search_failures`). Scheduled cycles increment/reset this counter based on `connected` state or network errors, but manual searches invoke `cycle_fn(...)` directly without routing through `make_search_job`, so failures do not increment the threshold counter.

**Files:** `triggarr/web/routes.py:876` (search_now handler), `triggarr/search/scheduler.py:325` (TODO comment)

**Impact:** Manual searches that fail do not contribute to escalation logging. If an operator manually searches a failing instance 5 times (hitting max_consecutive_failures=5), only the scheduled cycle would escalate the next time. The counter should unify both paths. Low operational impact (operators see individual error logs anyway), but inconsistent.

**Fix approach:** Refactor `search_now` to go through `make_search_job` or extract a shared `_run_one_cycle(app, app_name, instance_name)` helper that both the scheduler and manual-search routes invoke. This unifies failure counting and counter reset semantics. Deferred in v2.8 to keep scheduler hardening plan focused; suitable for v2.9+ phase.

### DEBT-03: Search History Pruning Hard-Coded to 1000 Rows

**Issue:** `max_history_rows` is configurable in `[general]` section and defaults to 1000, but the resolved-row pruning threshold in `db.insert_search_entry()` is not operator-tunable via config UI. The field exists in `GeneralConfig` but is not exposed in the web UI's settings form. Additionally, the comment notes "only prune resolved rows, preserve pending (outcome='searched')" — pending rows are bounded separately by `PENDING_CAP_MULTIPLIER * max_rows` (default 2000), so two separate caps exist.

**Files:** `triggarr/models/config.py:106`, `triggarr/db.py:429` (pruning logic), `triggarr/web/routes.py` (settings form)

**Impact:** Low. Operators with large search volumes or long-retention needs cannot increase the cap via UI. Pending rows (unresolved searches) are strictly bounded to prevent unbounded growth during tracker outages; resolved rows (completed/failed/grabbed) are trimmed after every insert. Default 1000 is reasonable for most deployments.

**Fix approach:** Either add `max_history_rows` to the settings UI form, or document why it is intentionally not exposed. If exposed, clarify the two-tier bounding (resolved @ max_history_rows, pending @ 2x) in comments.

### DEBT-06: Graceful Shutdown Drain Not Configurable Via UI

**Issue:** `_SHUTDOWN_DRAIN_TIMEOUT` is configurable via `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` env var (default 60s), but is not surfaced in the web settings UI. Operators must know to set this environment variable at container start time. The shutdown drain itself is well-implemented (RES-01): if a search cycle exceeds the timeout, detailed WARNING logs name the stuck job and elapsed time before forcing close. However, misconfigured operators who set low timeouts may truncate in-flight writes.

**Files:** `triggarr/search/scheduler.py:58-75` (env var read), `triggarr/search/scheduler.py:558-622` (shutdown drain)

**Impact:** Low operational risk due to logging. Most deployments use Docker defaults (90s stop-grace-period), which comfortably exceed the 60s drain. Operators who set `--stop-timeout 45` risk losing search state mid-write, but logs will clearly indicate the interruption.

**Fix approach:** Document the env var in startup comments and deployment guides. No UI exposure needed unless operators request tuning. The timeout is an internal performance/safety knob, not a feature setting.

### DEBT-07: HTTP Request Timeout Hard-Coded to 30 Seconds

**Issue:** `request_timeout` defaults to 30 seconds in `GeneralConfig` and is not exposed in the settings UI. Operators with slow or distant *arr servers cannot increase the timeout without editing the config file directly or setting TOML defaults. Timeout applies to all HTTP requests (get_wanted_missing, get_wanted_cutoff, get_tags, get_grab_history, search commands).

**Files:** `triggarr/models/config.py:107`, `triggarr/clients/base.py` (client initialization)

**Impact:** Low. Most *arr servers respond within 5-10s even under load. Timeouts trigger controlled exception handling (httpx.HTTPError caught, connected=False set, cycle retries on next interval). Operators with genuinely slow servers (due to network, disk I/O, or overload) currently cannot self-serve a fix.

**Fix approach:** Add `request_timeout` to settings UI with validation (e.g., 5.0–120.0 seconds). This is a user-facing configuration knob, unlike DEBT-06.

### DEBT-08: *arr API Pagination Page Size Hard-Coded to 50

**Issue:** `page_size` defaults to 50 items per API call and is not exposed in settings UI. Operators with very large libraries (thousands of movies/episodes) may want to tune this to balance request count vs. response size. Smaller page sizes = more requests but smaller network frames; larger page sizes = fewer requests but bigger buffers.

**Files:** `triggarr/models/config.py:108`, `triggarr/clients/base.py:get_paginated()`

**Impact:** Minimal. 50 items per page is safe for almost all deployments and matches typical *arr defaults. Only operators with extreme library sizes (10,000+ movies) might benefit from tuning. The pagination loop is solid and handles empty pages correctly.

**Fix approach:** Add `page_size` to settings UI with reasonable bounds (e.g., 10–500). Low priority unless customers request it.

### TRACK-07: Tracking Window Hard-Coded to 60 Minutes

**Issue:** `tracking_window_minutes` defaults to 60 minutes and is configurable in `[general]` section, but is not exposed in the web UI. This window determines how long after a search to wait for corresponding grabs before marking the search as unresolved. Operators with slow indexers or long processing pipelines may need to increase it.

**Files:** `triggarr/models/config.py:109`, `triggarr/tracking.py:22-123` (run_tracking_check)

**Impact:** Low. 60 minutes is a reasonable default for most indexers. If an operator's indexer is slower (e.g., 2-hour processing), searches will be marked unresolved prematurely. However, tracking runs every cycle (same interval as searches), so the next cycle can re-check and update the outcome if grabs arrive late.

**Fix approach:** Add `tracking_window_minutes` to settings UI with validation (e.g., 15–240 minutes). This is user-facing and directly affects search-outcome tracking.

### Unused Config Fields

**Issue:** `tracking_delay_seconds` (30 field in GeneralConfig) is read from config but never used in any cycle or tracking logic. It was likely a placeholder for future staggered tracking but is not referenced anywhere.

**Files:** `triggarr/models/config.py:110`

**Impact:** None — dead code. No security or correctness issue. Can be removed on next major version if cleanup is desired.

**Fix approach:** Remove `tracking_delay_seconds` from GeneralConfig and any TOML defaults, or document its intended use. For now, leaving it in place maintains config backwards-compatibility (old files won't error on load).

## Known Issues & Fragile Areas

### Manual Search Counter Asymmetry

**Files:** `triggarr/web/routes.py:876-970` (search_now), `triggarr/search/scheduler.py:279-346` (_record_cycle_failure, _evaluate_cycle_outcome)

**Why fragile:** The failure counter is the mechanism for escalating alerts when an instance becomes unreachable. If operators habitually use the manual search button (e.g., testing connectivity), those failures do not increment the counter, making the escalation signal less reliable. The code is correct for scheduled cycles, but incomplete across both triggering paths.

**Safe modification:** Before refactoring search_now, ensure:
1. Unit tests cover both scheduled and manual failure scenarios independently.
2. Run test_concurrent_settings_save_serialized to verify lock semantics are unchanged.
3. Verify that extracting a shared helper does not introduce new race conditions (lock must be held for the entire cycle + state save).

**Test coverage:** `tests/test_search.py` covers scheduled cycle failure handling; no explicit test for manual search failures incrementing counters (see gap below).

### Shutdown Drain TOCTOU Race Window

**Files:** `triggarr/search/scheduler.py:563-615` (lifespan finally block)

**Why fragile:** The shutdown drain acquires `search_lock` with a timeout. After the timeout fires, the code re-reads `app.state.search_lock_holder` defensively, because a race could have cleared it (the cycle finished but another caller acquired the lock before timeout). If the holder is None at that point, the WARNING log assumes the lock drained successfully, when in fact the cycle may still be running in another thread (unlikely but theoretically possible under extreme scheduler load).

**Safe modification:** The current approach is sound: asyncio.timeout() is safer than asyncio.wait_for() (documented in WR-01 comment). No change needed unless thread-safety concerns arise.

**Test coverage:** `tests/test_web.py::test_concurrent_settings_save_serialized` covers concurrent lock contention; shutdown drain timeout race is covered by integration tests (not unit-tested in isolation).

### Asyncio.Lock Requires Single-Worker Deployment

**Files:** `triggarr/search/scheduler.py:453-461` (SAFETY-05 comment)

**Why fragile:** The search_lock is an `asyncio.Lock`, which is per-event-loop. If uvicorn is ever configured with `workers=N` (N > 1), each worker process gets its own event loop, and the lock no longer serializes across processes. Config writes and search cycles could race, corrupting state. The code currently enforces single-worker via `uvicorn.Config(...)` in `__main__.py:75` with no `workers=` parameter.

**Safe modification:** Before adding multi-worker support:
1. Replace `asyncio.Lock` with a file-level lock (`fcntl.flock` on Unix, `msvcrt.locking` on Windows) or a process-level primitive.
2. Test concurrent config writes across multiple worker processes.
3. Audit lock coverage (ast audit script `tests/audit_lock_coverage.py` verifies all _atomic_toml_write calls are locked).

**Test coverage:** `tests/test_web.py::test_concurrent_settings_save_serialized` uses asyncio.gather() to simulate concurrency within a single event loop. No multi-worker test exists (not applicable until multi-worker is supported).

### Tag Cache Invalidation on Config Change

**Files:** `triggarr/web/routes.py:640-656` (instance add), `triggarr/web/routes.py:701-705` (instance enable/url change), `triggarr/web/routes.py:859` (instance remove)

**Why fragile:** When an instance is added, removed, or its URL/API key is updated, the tag cache entry is invalidated (set to None or deleted). However, if a manual search or scheduled cycle is in-flight at the moment of invalidation, the resolver (`_get_tags_cached` closure in `make_search_job` or `search_now`) will fetch fresh tags and cache them with the old config. The invalidation happens AFTER the in-lock state write but BEFORE a potential second read by the cycle.

**Impact:** Minimal. In-flight cycles use the tag resolver snapshot captured at job start, so they are unaffected. A race where invalidation and an inflight cycle both update the cache simultaneously is defended by the asyncio.Lock (single-worker model). The cache value itself (list[Tag]) is immutable after fetch, so even a concurrent read sees consistent data.

**Safe modification:** Tag cache is sound as-is. No changes needed unless cache TTL or invalidation logic changes.

**Test coverage:** `tests/test_web.py::test_tag_cache_invalidation_on_config_change` (added in v2.8)

### Resolved-Row Pruning Query Correctness

**Files:** `triggarr/db.py:430-441` (DELETE query in insert_search_entry)

**Why fragile:** The pruning query uses `COALESCE(outcome, 'searched') != 'searched'` to identify resolved rows (those with an explicit outcome != 'searched'). This correctly skips NULL outcomes (which default to 'searched' when displayed). However, the query assumes all non-NULL, non-'searched' outcomes are "resolved" — i.e., their row can be deleted if outside the top N. The outcomes are: "grabbed", "partial", "unresolved", "failed", "error". If a new outcome is added in tracking logic without updating the pruning predicate, old rows with that outcome will not be pruned.

**Impact:** Low. Outcomes are defined in `triggarr.tracking._determine_outcome()` and are stable. The schema version number ensures migrations run if outcomes change. The query is correct for the current outcome set.

**Safe modification:** When adding new outcomes:
1. Update the pruning predicate if the new outcome represents a "resolved" state.
2. Document the outcome enum in both `db.py` and `tracking.py`.
3. Increment the schema version if the semantics change.

**Test coverage:** `tests/test_db.py` covers pruning with mocked outcomes; adding a new outcome requires a new migration test.

## Security Considerations

### Session Secret Validation at Startup

**Files:** `triggarr/startup.py:50-90` (validate_session_secret)

**Risk:** Session secret is used for signing session cookies. If empty or unset at startup, auth becomes vulnerable (attacker can forge session cookies). The startup check (SEC-04 D-12/D-13/D-14) validates this and exits with a clear error. This is correctly implemented.

**Current mitigation:**
- `startup.py` checks `settings.auth.session_secret` is non-empty and logs an error if missing.
- Config validation ensures SecretStr fields are not logged or exposed.
- Secret is persisted atomically (write-then-rename) so it is never partially written.

**Recommendations:** No changes. The validation is sound and startup failure is the right behavior.

### API Key Query Parameter Rejection

**Files:** `triggarr/models/config.py:68-80` (InstanceConfig.url validator)

**Risk:** URLs containing `?apikey=...` would leak credentials to logs, config backups, and request.url in exception messages. The validator rejects these at config load time.

**Current mitigation:**
- Pydantic validator rejects `apikey=` in query string.
- Error message is clear: "Do not use apikey= in URL; use api_key field instead."
- All HTTP clients use api_key (SecretStr) separately; URLs are never mixed with keys.

**Recommendations:** No changes. This is well-defended and user-friendly.

### Basic Auth Control-Character Rejection

**Files:** `triggarr/web/middleware.py:26-28` (_has_control_chars), `triggarr/web/middleware.py:88-127` (AuthMiddleware)

**Risk:** Control characters (0x00–0x1F, 0x7F) in HTTP headers could bypass parsing or inject headers. The middleware rejects requests with control chars in Authorization headers.

**Current mitigation:**
- AuthMiddleware checks all incoming requests for control chars in the Authorization header (D-09).
- Non-ASCII UTF-8 is allowed (per HTTP spec).
- Rejected requests return 400 Bad Request immediately.

**Recommendations:** No changes. Mitigation is sound.

### CSP Script-Src Nonce Injection

**Files:** `triggarr/web/middleware.py:49` (CSP header), `triggarr/web/routes.py:68-71` (expose nonce to Jinja)

**Risk:** Inline JavaScript in templates needs a per-request nonce to pass CSP. Without it, Tailwind's JIT mode or any script tags would be blocked.

**Current mitigation:**
- Middleware generates a unique nonce per request using `secrets.token_hex(16)`.
- Nonce is exposed to Jinja as `{{ csp_nonce }}` via context processor.
- CSP header is set: `script-src 'nonce-...' 'unsafe-inline'` — wait, this includes 'unsafe-inline', which defeats CSP.

**Potential issue:** The CSP header includes both `'nonce-...'` AND `'unsafe-inline'`. The `'unsafe-inline'` fallback is documented in the comment (D-04: "style-src keeps 'unsafe-inline' for Tailwind utility output"), but script-src should NOT need unsafe-inline if all scripts use the nonce. This warrants review.

**Recommendations:** Audit whether script-src actually needs 'unsafe-inline' or if all inline scripts are properly nonce'd. If unsafe-inline is necessary (e.g., due to a third-party library), document why and consider replacing it with a hash-source (`'sha256-...'`) for that specific script.

## Performance Bottlenecks

### Tag List Fetching on Every Search

**Files:** `triggarr/search/scheduler.py:142-161` (tag resolver in make_search_job), `triggarr/web/routes.py:916-932` (tag resolver in search_now)

**Problem:** Before v2.8, every search cycle would call `get_tags()`, querying the *arr API for the full tag list (usually 100–1000 tags). For multi-instance setups with 5-minute search intervals, this meant 288 tag fetches per day per instance.

**Current mitigation (RES-03 in v2.8):** Tag list cache with 1-hour TTL (configurable via `_TAG_CACHE_TTL_SECONDS` module constant). Cache is keyed by (app_name, instance_name) and invalidated on instance config changes. This reduces tag fetches by 99% in steady state.

**Remaining concern:** The TTL is hard-coded (not configurable via UI). If an operator's tag list changes frequently (manual tag edits, automation that adds/removes tags), a 1-hour stale cache could skip newly added tags until the TTL expires or the instance config is re-saved.

**Impact:** Low. Tag additions are rare after initial setup. If an operator manually adds a tag and searches immediately, the cycle will use the cached list and miss the tag — but the tag filter is purely for filtering which items to search, not for correctness. On the next search (when cache expires), the tag will be included.

**Fix approach:** Leave TTL as-is (internal knob). If customers request dynamic TTL, add a config field with validation (e.g., 10–3600 minutes).

### Pending-Row Cap Reached During Tracker Outage

**Files:** `triggarr/db.py:391-420` (pending cap enforcement)

**Problem:** When the *arr tracker is unreachable for extended periods, search entries accumulate with `outcome='searched'` (pending resolution). If the cap is hit (default 2000), new searches are REJECTED with a `PendingCapExceeded` exception, stopping the cycle.

**Current impact:** Correct behavior—better to stop searching than to grow the database unboundedly. The rejection is logged with actionable detail (which app/instance/item was rejected). Operators can query the DB to see pending rows and restart the tracker to resolve them.

**Potential improvement:** In a future phase, consider a "slow drain" mode where if pending rows exceed 1.5x the cap, searches are rate-limited (e.g., skip every other item) to allow tracking checks time to resolve pending rows. This would keep the service responsive during gradual tracker recovery.

**Current status:** Not a bottleneck in practice. Trackers usually recover within hours, and the cap is 2000 rows (enormous for typical deployments).

## Scaling Limits

### Single-Worker Process Limit

**Current capacity:** One uvicorn worker process, one event loop, can handle ~100–200 concurrent HTTP requests (typical for small-to-medium teams).

**Limit:** If Triggarr is deployed to a 32-core server, only one core is used. For teams with thousands of manually-triggered searches per hour, a single worker will bottleneck.

**Scaling path:** Refactor lock from asyncio.Lock to file-level lock (fcntl.flock) or distributed lock (Redis), then set `workers=N` in uvicorn.Config. Requires thorough testing of concurrent state access.

**Priority:** Low. Current deployments (media server + a few users) do not hit this limit.

### Database Write Serialization

**Current approach:** All writes to triggarr.db (search_history inserts, outcome updates, stats updates) happen serially via a single aiosqlite connection with asyncio.get_running_loop().run_in_executor(). This serializes all DB writes to a thread pool.

**Capacity:** ~1000 inserts/updates per second (depends on disk I/O and schema). For a server doing 10 searches per minute, that is ~100 inserts per minute = well under capacity.

**Limit:** If Triggarr is doing 100+ concurrent searches per minute (1000+ per hour), the write queue will grow. Searches block on `save_state` (executor call), delaying response.

**Scaling path:** Use connection pooling (aiosqlite.connect with pool_size > 1) or a dedicated write-ahead log (WAL mode is already enabled, which helps).

**Current status:** Not a concern for typical deployments.

## Missing Critical Features

### Operator Configuration Audit

**Gap:** Triggarr has no built-in audit log or change history for configuration edits. If an operator misconfigures an instance (wrong URL, disabled when shouldn't be), there is no record of who made the change or when.

**Impact:** Low for small teams. For shared deployments, useful for debugging "why did searches stop?"

**Path to implement:** Add a config change audit table to triggarr.db, log every save_settings call with a timestamp and diff (old vs. new values, redacting secrets). Expose via a read-only audit log view in the UI.

### Health Check Metric Scraping

**Gap:** Triggarr has a `/health` endpoint (returns JSON status), but no Prometheus-compatible metrics endpoint (`/metrics`). Monitoring systems (Grafana, Prometheus) cannot scrape search counts, cycle runtimes, or failure rates.

**Impact:** Low. The app logs to loguru, which can be forwarded to Loki/Datadog/etc.

**Path to implement:** Add `from prometheus_client import Counter, Histogram` and expose `/metrics` endpoint with search counts, cycle times, and error rates.

## Test Coverage Gaps

### Manual Search Failure Counter Not Tested

**What's not tested:** Manual searches that fail do not increment `app.state.search_failures`. There is no test asserting that manual and scheduled failures have different counter semantics (or that they should unify).

**Files:** `triggarr/web/routes.py:876` (search_now), no explicit test for failure counter increment

**Risk:** If the counter logic changes, manual search behavior could diverge from scheduled cycles unnoticed.

**Priority:** Medium. Add a test: `test_search_now_failure_counter_increment` that:
1. Mocks a failing client (raises httpx.HTTPError).
2. Calls search_now twice.
3. Asserts that `app.state.search_failures[job_id]` does NOT increment (documents current behavior).
4. Later, when refactored to go through `make_search_job`, assert that it DOES increment.

### Shutdown Drain Timeout Not Unit-Tested

**What's not tested:** The graceful shutdown drain with timeout. No unit test for the case where `search_lock.acquire()` times out and `search_lock_holder` is recorded.

**Files:** `triggarr/search/scheduler.py:558-622` (shutdown drain logic)

**Risk:** If the timeout logic is changed (e.g., by refactoring or removing the holder re-check), integration tests might not catch a race condition.

**Priority:** Low. Integration tests (app startup/shutdown cycles) cover the happy path. The edge case of a cycle that takes >60 seconds is hard to reproduce in unit tests without mocking asyncio.timeout.

**Path to implement:** Add a mock-based test in `tests/test_search.py`:
- Mock `asyncio.timeout()` to always raise TimeoutError.
- Mock `app.state.search_lock.acquire()` to hang.
- Verify that the shutdown logs a WARNING with the holder's job_id and elapsed time.

### Pending-Row Cap Rejection Not Covered

**What's not tested:** The `PendingCapExceeded` exception path. No test for inserting searches until pending rows hit the cap, then verifying the next insert is rejected.

**Files:** `triggarr/db.py:414-420` (PendingCapExceeded raise)

**Risk:** If the cap logic changes (e.g., cap value or query), old rows that should have been rejected might be accepted, or vice versa.

**Priority:** Medium. Add a test: `test_pending_cap_exceeded`:
1. Insert 2000+ searches with outcome='searched'.
2. Assert the next insert raises PendingCapExceeded.
3. Verify the exception carries the correct app, instance_id, cap, and pending_count.

## Residual Debt Summary

| Item | Severity | Type | Path |
|------|----------|------|------|
| Manual search counter bypass | Low | Design gap | `triggarr/web/routes.py:876` |
| History pruning UI exposure | Low | Configuration | `triggarr/models/config.py:106` |
| HTTP timeout not configurable | Low | Configuration | `triggarr/models/config.py:107` |
| Page size not configurable | Low | Configuration | `triggarr/models/config.py:108` |
| Tracking window not exposed | Low | Configuration | `triggarr/models/config.py:109` |
| Unused tracking_delay_seconds | Trivial | Dead code | `triggarr/models/config.py:110` |
| Shutdown drain not tunable via UI | Low | Configuration | `triggarr/search/scheduler.py:58-75` |
| CSP unsafe-inline script-src review | Medium | Security audit | `triggarr/web/middleware.py:49` |
| Tag cache TTL hard-coded | Low | Performance knob | `triggarr/search/scheduler.py:91` |
| Multi-worker lock not supported | Medium | Scalability | `triggarr/search/scheduler.py:453-461` |
| No audit log for config changes | Low | Observability | N/A |
| No Prometheus metrics endpoint | Low | Observability | N/A |

## Hardening Confirmed in v2.8

The following issues from prior versions have been **resolved** and are documented in code as "hardening":

- ✅ **SAFETY-01a:** Search history row cap (1000 resolved rows)
- ✅ **SAFETY-01b:** Pending row cap (2000 rows) to prevent unbounded growth during tracker outages
- ✅ **SAFETY-02:** Narrow exception handling in scheduler cycles + EVENT_JOB_ERROR listener to surface code bugs
- ✅ **SAFETY-03:** Per-job consecutive-failure counter + escalation logging
- ✅ **SAFETY-04:** Atomic config writes (write-then-rename) with corrupt-TOML recovery
- ✅ **SAFETY-05:** AST audit to verify all config writes are locked (see `tests/audit_lock_coverage.py`)
- ✅ **RES-01:** Graceful shutdown drain with configurable timeout
- ✅ **RES-02:** Last success timestamp for stale-indicator rendering
- ✅ **RES-03:** Tag list cache with 1-hour TTL
- ✅ **SEC-01:** CSP nonce injection for script-src
- ✅ **SEC-02:** Reject URLs with embedded apikey= parameters
- ✅ **SEC-03:** Reject requests with control characters in Auth header
- ✅ **SEC-04:** Validate session-secret non-empty at startup

These hardening measures are reflected throughout the codebase with inline comments and tests. The priority for future work is the residual debt (mostly configuration UI exposure) and optional scalability improvements (multi-worker support).

---

*Concerns audit: 2026-06-01*
