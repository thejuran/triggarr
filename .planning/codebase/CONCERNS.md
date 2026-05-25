# Codebase Concerns

**Analysis Date:** 2026-05-25

## Tech Debt

**DEBT-03: Search history cleanup policy**
- Issue: `max_history_rows` setting in `triggarr.models.config:79` defines a limit (default 1000), but no automated cleanup query exists to enforce it
- Files: `triggarr/models/config.py`, `triggarr/db.py`
- Impact: SQLite database grows unbounded after `max_history_rows` is exceeded; long-running instances may accumulate hundreds of thousands of rows without trimming
- Fix approach: Implement a trim-after-insert query in `db.py` that deletes oldest rows when the limit is exceeded. This should run asynchronously to avoid blocking searches

**DEBT-06: Graceful shutdown race condition with search cycles**
- Issue: Lifespan shutdown at `triggarr/search/scheduler.py:266-273` tries to acquire `search_lock` with a 35-second timeout to drain in-flight cycles
- Files: `triggarr/search/scheduler.py`, `triggarr/search/scheduler.py:make_search_job`
- Impact: If a search cycle is deadlocked or genuinely takes >35s, the timeout fires and forces a close, potentially leaving state files partially written or database in an inconsistent state. Also, scheduler shutdown happens with `wait=False`, so jobs may still be executing when clients start closing
- Fix approach: (1) Increase timeout to 60-90s for large libraries; (2) Consider adding a more robust lock-with-signal pattern using asyncio.Event; (3) Log the exact job still running before forcing close

**DEBT-07: Request timeout applied globally**
- Issue: `request_timeout` in `triggarr/models/config.py:80` is set once at startup (default 30s) and applied to all HTTP requests via `ArrClient.__init__` at `triggarr/clients/base.py:35`
- Files: `triggarr/clients/base.py`, `triggarr/models/config.py`
- Impact: (1) Large library queries (especially Sonarr with thousands of series) may timeout before finishing; (2) Users cannot override per-request; (3) Changes to config require restart to take effect
- Fix approach: Read timeout from settings at request time rather than init time, or provide per-operation overrides for expensive calls (e.g., get_wanted_missing, get_library_count)

**DEBT-08: Pagination page size affects memory and API load**
- Issue: `page_size` in `triggarr/models/config.py:81` (default 50) is applied to all paginated endpoints. Very large page sizes can cause memory spikes and API timeouts; very small sizes cause many round trips
- Files: `triggarr/clients/base.py:147-195`, `triggarr/models/config.py`
- Impact: Users with massive libraries may need manual tuning; large page sizes risk OOM on memory-constrained systems
- Fix approach: Add adaptive paging that adjusts page size based on response time; or expose per-endpoint overrides

**config.py atomic writes suppressing OSError:**
- Issue: `_atomic_toml_write` at `triggarr/config.py:113-115` suppresses all OSError exceptions during temp file cleanup
- Files: `triggarr/config.py`
- Impact: If the final `os.replace()` fails due to permission errors or filesystem issues, the exception is silently swallowed and the old config file is lost
- Fix approach: Log the OSError before suppressing it, or re-raise if it's not a "file does not exist" error

## Known Issues & Behaviors

**Migration marker race condition:**
- Issue: In `triggarr/config.py:161`, after v2.2→v2.3 config migration, a `.migrated` marker file is written to `config_path.parent`. If the config is in a read-only directory or permissions change mid-migration, the marker is lost silently
- Files: `triggarr/config.py`
- Impact: Web UI banner conditionally checks for `.migrated` file to show migration notice; if file write fails, users won't see the banner even though migration happened
- Mitigation: Marker file is cosmetic (migration is durable); worst case users see the notice multiple times

**Log redaction via string replacement:**
- Issue: Logging redaction at `triggarr/logging.py:36-42` uses simple string replacement in the full formatted output
- Files: `triggarr/logging.py`, `triggarr/startup.py:49-75`
- Impact: (1) Redaction is O(N*M) where N=log lines and M=secrets; (2) If an API key appears as a substring within another secret or in a URL, partial redaction can occur; (3) Redaction doesn't apply to exception tracebacks that include formatted values (e.g., f-string expansions in exception messages from third-party libraries)
- Mitigation: API keys are properly extracted via `SecretStr.get_secret_value()` only at startup, so accidental logging of keys is unlikely. Logging redacting sink is only called once at startup to configure secrets list

**Configuration hot-reload potential data loss:**
- Issue: Route handler at `triggarr/web/routes.py` allows live config edits via web UI. If a user saves config while a search cycle is in progress, and the search cycle tries to read config mid-write, it could read partial/corrupted TOML
- Files: `triggarr/web/routes.py`, `triggarr/config.py`
- Impact: Search cycle could crash or skip items if it reads malformed instance config
- Mitigation: Atomic write-then-rename pattern prevents file corruption, but there's no transaction-level lock preventing config read during write. In practice, TOML serialization is fast (~1-5ms), so the window is small

**Unresolved session cookie expiry handling:**
- Issue: Session cookies signed at `triggarr/auth.py:84-85` have a max_age of 30 days (COOKIE_MAX_AGE). If a user's local clock skews significantly, cookie validation at `triggarr/auth.py:104` could reject valid cookies or accept expired ones
- Files: `triggarr/auth.py`, `triggarr/web/middleware.py:131`
- Impact: Users with out-of-sync system clocks may be unexpectedly logged out
- Mitigation: Container typically syncs time via NTP; this is a user configuration issue. No change needed unless clocks are frequently misaligned

## Security Considerations

**CSP allows unsafe-inline scripts:**
- Risk: Content Security Policy at `triggarr/web/middleware.py:41-48` includes `script-src 'self' 'unsafe-inline'` because htmx requires inline event handlers (hx-on, hx-trigger) and some templates use inline <script> blocks
- Files: `triggarr/web/middleware.py`
- Current mitigation: Route handlers escape all user input via Jinja2 autoescape, and no user-controlled data is rendered into inline scripts; only framework/app data appears inline
- Recommendations: (1) Extract inline scripts to static JS files with nonce-based CSP; (2) Migrate htmx attribute handlers to delegated JS event listeners; (3) Audit all inline <script> tags to ensure no user input

**API key sent in URL query parameters (Radarr/Sonarr convention):**
- Risk: *arr applications require API keys in requests. While Triggarr uses httpx headers (`X-Api-Key`), if users misunderstand config and add `?apikey=...` to the URL, it will be logged in plaintext
- Files: `triggarr/clients/base.py:30-35`, `triggarr/startup.py`
- Current mitigation: Redacting sink at startup collects all configured API keys and redacts them from logs
- Recommendations: (1) Validate config URLs to reject URLs containing `apikey=` query parameter; (2) Log a warning if user's URL contains a query parameter

**Basic auth header handling:**
- Risk: Basic auth decoding at `triggarr/web/middleware.py:158-184` uses plain base64 decoding without additional header validation
- Files: `triggarr/web/middleware.py`
- Current mitigation: Credentials are verified via bcrypt and timing-safe comparison; only valid credentials proceed
- Recommendations: (1) Add strict username/password character validation (e.g., reject null bytes); (2) Log failed auth attempts (currently silent on decode error)

**Session secret entropy:**
- Risk: Session secret generated at `triggarr/auth.py:61-67` uses `secrets.token_hex(32)` (64 chars, ~256 bits). Adequate for session signing but could be validated at config load time
- Files: `triggarr/auth.py`
- Current mitigation: Bcrypt and TimestampSigner both provide strong defaults
- Recommendations: (1) Validate at startup that session_secret length > 32 chars; (2) Log a warning if secret was auto-generated (user needs to save config to persist it)

## Performance Bottlenecks

**Synchronous state JSON load/save with large state:**
- Problem: State file is loaded/saved synchronously via `json.load()` and `json.dump()` at `triggarr/state.py:150-180`. For very large state files (e.g., thousands of instances or searches), this blocks the async event loop
- Files: `triggarr/state.py`, `triggarr/search/scheduler.py:91`
- Cause: Triggarr uses `run_in_executor(None, save_state, ...)` correctly, but there's no similar pattern for load; state is loaded at startup synchronously, which can delay startup on slow I/O
- Improvement path: (1) Profile state file size in production; (2) If >1MB, consider incremental streaming or compression

**Tag list fetched on every tag-filtering search:**
- Problem: When an instance has a `missing_tag` or `cutoff_tag` set, `run_radarr_cycle` (and Sonarr/Lidarr equivalents) call `client.get_tags()` on every cycle to resolve tag names to IDs
- Files: `triggarr/search/engine.py` (called from radarr_cycle, sonarr_cycle, lidarr_cycle)
- Cause: No caching of tag list; for instances with 100+ tags, this is an extra paginated API round-trip per cycle
- Improvement path: (1) Cache tag list in app.state with a TTL (e.g., 1 hour); (2) Invalidate on config change; (3) Measure tag fetch latency in production

**N+1 query pattern in search history pagination:**
- Problem: Route handler at `triggarr/web/routes.py` fetches search history page by page without pre-computing row counts or result sizes
- Files: `triggarr/web/routes.py`
- Cause: SQLite queries are fast, but with thousands of rows and frequent polling, page count calculations may repeat
- Improvement path: (1) Add a cached view or computed column for recent search count; (2) Use limit+offset with a known total for pagination

## Fragile Areas

**Search cycle exception handling is broad:**
- Files: `triggarr/search/scheduler.py:124-129`
- Why fragile: Catches all Exception types, including KeyboardInterrupt subclasses and memory errors. If a critical error occurs, it's logged but the job continues silently. Repeated errors build up without alerting the user
- Safe modification: (1) Narrow exception handling to catch only expected types (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError); (2) Add a counter for consecutive failures and log an ERROR instead of just reporting the first one; (3) Consider pausing the job after N consecutive failures instead of continuing to retry
- Test coverage: Test suite has `test_search.py` but gaps exist for: (a) repeated consecutive failures; (b) partial state corruption recovery

**Lifespan shutdown with multiple concurrent app updates:**
- Files: `triggarr/search/scheduler.py:134-285`
- Why fragile: Lifespan yields once to start the app, then runs teardown on shutdown. If multiple routes try to update app.state.settings during graceful shutdown, they may race with the scheduler's client close operations
- Safe modification: (1) Add a "shutting_down" flag to app.state; (2) Reject config updates if shutting_down is true; (3) Ensure all route handlers check this flag before modifying shared state
- Test coverage: No integration tests for concurrent config updates during shutdown

**Database schema migrations with no rollback:**
- Files: `triggarr/db.py:54-76`
- Why fragile: Migration registry at `MIGRATIONS` dict is sequential, one-way only. If a migration has a bug (e.g., drops wrong column), there's no rollback mechanism
- Safe modification: (1) Backup-before-migrate is in place (good); (2) Add a version check at app startup to warn if schema version is newer than code supports; (3) Document manual rollback steps (restore .bak, reset version)
- Test coverage: Migrations are tested, but gap: no test for corrupted/incomplete migration recovery

## Scaling Limits

**Fixed database file on single disk:**
- Current capacity: SQLite supports databases up to ~2TB, but single-instance bottleneck around 10-50GB for typical CRUD
- Limit: Where it breaks: Triggarr stores all search history in one SQLite file (`state.db`). With a very large library and aggressive search tuning, history could grow to GB-scale within months, slowing queries
- Scaling path: (1) Archive old history to separate tables or files; (2) Implement periodic cleanup of rows older than X days (DEBT-03); (3) Consider PostgreSQL migration if history retention becomes critical

**Max 5 instances per app type (hard limit):**
- Current capacity: Config validation at `triggarr/models/config.py:133-137` enforces max 5 instances per app type
- Limit: Users with more instances are blocked
- Scaling path: Remove the hard limit or increase to 10-20 if scheduler and state management can handle more concurrent jobs

**Memory footprint of LogBuffer:**
- Current capacity: In-memory ring buffer at `triggarr/log_buffer.py:29-31` stores up to 200 log entries (default)
- Limit: Each LogEntry has timestamp + level + message; if messages are very long (e.g., detailed exception tracebacks), buffer could reach 2-5MB
- Scaling path: For long-running instances, consider: (1) Rotating log files instead of in-memory buffer; (2) Streaming logs to file rather than keeping in memory

## Dependencies at Risk

**idna 3.11→3.15 update (recent Dependabot PR #19):**
- Risk: IDNA encoding vulnerability (CVE-2026-45409, medium severity) fixed in idna 3.15
- Impact: Affects domain validation and DNS resolution in any downstream integrations
- Migration plan: Already merged in commit cc61133; no further action needed

**python-multipart patched version:**
- Risk: Commit b619e14 pins python-multipart to a patched version due to upstream security/reliability issues
- Files: `pyproject.toml`
- Impact: If upstream fixes issues and we forget to update the pin, we stay vulnerable
- Migration plan: Monitor python-multipart releases; update patch pin when upstream resolves the core issue

**Node.js 20 deprecation in GitHub Actions:**
- Risk: GitHub Actions deprecation warning during CI/release; Node.js 20 will be removed Sept 16, 2026
- Files: `.github/workflows/ci.yml`, `.github/workflows/release.yml`
- Impact: CI will fail after Sept 16, 2026 unless action versions are updated
- Migration plan: Document in TODO.md (already done). Need to update action versions to Node.js 24 compatible before deadline

## Missing or Incomplete Features

**No audit logging for config changes:**
- Problem: Routes at `triggarr/web/routes.py` allow editing auth and instance config via web UI, but no audit trail of who changed what
- Blocks: (1) Security teams cannot audit changes; (2) Users cannot undo accidental config edits
- Mitigation: Config changes are logged at INFO level with timestamps; file-level backup (`*.bak` on migration) exists

**Limited visibility into scheduler health:**
- Problem: If scheduled jobs silently fail or get stuck, the user has no dashboard indicator
- Blocks: (1) Users don't know if searches are actually happening; (2) Long-running jobs that exceed DEBT-06 timeout are not surfaced
- Improvement: (1) Add a "last successful search" timestamp to dashboard; (2) Expose scheduler job list (next run time, last duration) in web UI

## Test Coverage Gaps

**Integration tests for async client cleanup:**
- What's not tested: Closing clients with in-flight requests; timeout behavior during graceful shutdown
- Files: `triggarr/clients/base.py:275-283`, `triggarr/search/scheduler.py:275-281`
- Risk: If a client doesn't cleanly close (e.g., socket hangs), app shutdown could hang indefinitely
- Priority: Medium (affects production uptime)

**Security middleware with origin spoofing:**
- What's not tested: OriginCheckMiddleware (triggarr/web/middleware.py:52-77) with missing Origin/Referer headers in non-browser contexts
- Files: `triggarr/web/middleware.py`
- Risk: Legitimate API clients without standard headers might be rejected; or spoofed headers might slip through
- Priority: High (security-sensitive)

**Corrupted config file recovery:**
- What's not tested: Starting app with a TOML file containing syntax errors or invalid UTF-8
- Files: `triggarr/config.py:170-185`
- Risk: App exits with unclear error; users don't know to restore from backup
- Priority: High (user experience on misconfiguration)

**Concurrent config saves via web UI:**
- What's not tested: Two simultaneous PUT requests to the config endpoint
- Files: `triggarr/web/routes.py` (config editor routes)
- Risk: One save silently overwrites the other; state inconsistency if scheduler reads mid-write
- Priority: Medium (rare but data-loss scenario)

---

*Concerns audit: 2026-05-25*
