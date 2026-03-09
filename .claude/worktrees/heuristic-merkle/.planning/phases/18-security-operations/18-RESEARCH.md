# Phase 18: Security & Operations - Research

**Researched:** 2026-02-25
**Domain:** Rate limiting, CSRF validation, health check endpoint, graceful shutdown
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
All implementation details are at Claude's discretion. The success criteria are precise and testable.

### Claude's Discretion
- **Rate limiting**: Window duration, in-memory tracking approach, 429 response format, UI feedback on rejection
- **Origin/CSRF validation**: Allowed origins list, Referer vs Origin header priority, rejection response format
- **Health check**: Response body structure, which dependencies to probe, timeout thresholds
- **Graceful shutdown**: Shutdown order, timeout before force-exit, signal handling approach

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEBT-01 | Rate limiting on search-now endpoint | In-memory timestamp per app, `time.monotonic()`, stdlib only, return HTTP 429 |
| DEBT-02 | CSRF protection on settings POST verified/hardened | `OriginCheckMiddleware` already exists in `fetcharr/web/middleware.py` — gap is test coverage for settings-specific behavior and hardening review |
| DEBT-05 | Health check endpoint for container orchestrators | New `GET /health` route in `routes.py`, reads `connected` from `app.state.fetcharr_state`, returns 200 or 503 |
| DEBT-06 | Graceful shutdown handler (close scheduler, clients, DB, flush logs) | Lifespan `finally` block already closes clients and DB; gap is `scheduler.shutdown(wait=True)` + search_lock drain to prevent data loss mid-cycle |
</phase_requirements>

## Summary

Phase 18 adds four operational hardening items before the tracking feature ships. Three of the four have substantial existing infrastructure: CSRF middleware already exists (DEBT-02), the lifespan shutdown already closes clients and DB (DEBT-06 partial), and the codebase has no external deps to add. Only `GET /health` (DEBT-05) and the rate limiter (DEBT-01) require net-new code.

The rate limiter is a simple in-memory timestamp check per app using `time.monotonic()`. A dict `{app_name: last_request_time}` on `app.state` suffices; no external library is needed. The REQUIREMENTS.md explicitly excludes slowapi and Redis for this single-user local tool. The primary work for DEBT-02 is a hardening audit of `OriginCheckMiddleware` (currently only applied to all POSTs) and completing test coverage for the settings POST path specifically. For DEBT-06, the existing shutdown sequence uses `scheduler.shutdown(wait=False)`, which is the data-loss risk: a running search cycle that is writing to the database may be cut off before the DB is closed. Changing to `wait=True` (or acquiring `search_lock` before shutting down) ensures the in-flight cycle completes.

The Dockerfile already has a `HEALTHCHECK` directive that polls `/` (the main UI page). DEBT-05 requires updating this to probe `/health`, which returns 200 or 503 based on whether enabled apps have their `connected` state set to `True`. This is a two-part change: add the route, update the Dockerfile CMD.

**Primary recommendation:** Four small, focused changes to existing files — no new modules, no new dependencies. Rate limiter goes on `app.state`, health route goes in `routes.py`, CSRF middleware receives a targeted audit + test, and the shutdown sequence gets `wait=True` or a lock-drain before scheduler shutdown.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `time` (stdlib) | Python 3.11+ built-in | Monotonic timestamp for rate limiting window | No external dep; `time.monotonic()` is immune to clock adjustments |
| `fastapi` | 0.133.0 (installed) | HTTP 429/503 responses, `JSONResponse` | Already in stack |
| `starlette.middleware.base` | (via fastapi) | `BaseHTTPMiddleware` for CSRF check | Already used in `OriginCheckMiddleware` |
| `asyncio` | stdlib | `asyncio.Lock` for search_lock already in use | Already on `app.state.search_lock` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `loguru` | (installed) | Log rate-limit rejections and shutdown events | Already the project logger |
| `aiosqlite` | (installed) | DB close in shutdown sequence | Already in use |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `time.monotonic()` dict | `slowapi` / `redis-py` | Explicitly excluded by REQUIREMENTS.md for this single-user tool |
| Origin/Referer check | Cookie-based CSRF tokens | Explicitly excluded by REQUIREMENTS.md (sessionless app) |
| In-lifespan shutdown | `signal.signal()` in `__main__.py` | Lifespan `finally` is already the correct hook; no separate signal handler needed |

**Installation:** No new packages required. All tools are stdlib or already in `pyproject.toml`.

## Architecture Patterns

### Recommended Project Structure

No new files needed. All changes go into existing modules:

```
fetcharr/
├── web/
│   ├── routes.py         # Add /health route; add rate-limit state + check to search-now
│   └── middleware.py     # Audit OriginCheckMiddleware (may be no change needed)
├── search/
│   └── scheduler.py      # Change scheduler.shutdown(wait=False) → wait=True + lock drain
└── __main__.py           # No change needed (uvicorn handles SIGTERM → lifespan finally)
Dockerfile                # Update HEALTHCHECK CMD: / → /health
```

### Pattern 1: In-Memory Rate Limiter on app.state

**What:** Store a dict mapping `app_name → last_search_time` on `app.state`. In the `search_now` handler, compare `time.monotonic()` against the last timestamp before acquiring the search lock. Return HTTP 429 immediately if within the window.

**When to use:** Single-user local tool; per-app rate limiting; no persistence across restarts required.

**Example:**
```python
# In lifespan (scheduler.py), initialize on app.state:
app.state.last_search_time: dict[str, float] = {}

# In search_now route (routes.py):
import time

SEARCH_RATE_LIMIT_SECONDS = 10  # window duration — Claude's discretion

@router.post("/api/search-now/{app_name}", response_class=HTMLResponse)
async def search_now(request: Request, app_name: str) -> HTMLResponse:
    if app_name not in ("radarr", "sonarr"):
        return HTMLResponse("Invalid app", status_code=400)

    client = getattr(request.app.state, f"{app_name}_client", None)
    if client is None:
        return HTMLResponse("App not enabled", status_code=400)

    # Rate limit check
    now = time.monotonic()
    last = request.app.state.last_search_time.get(app_name, 0.0)
    if now - last < SEARCH_RATE_LIMIT_SECONDS:
        return HTMLResponse("Too many requests", status_code=429)
    request.app.state.last_search_time[app_name] = now

    # ... rest of handler unchanged
```

**Notes:**
- `time.monotonic()` is the correct clock for durations (wall-clock-safe).
- The dict must be initialized in the lifespan before yield (not at module level), so tests can inject a clean state.
- The check happens _before_ the `search_lock` acquisition to fail fast without serializing.
- No locking needed on the dict itself: FastAPI's async event loop is single-threaded; concurrent coroutines do not race on simple dict access between `await` points.

### Pattern 2: /health Endpoint

**What:** A `GET /health` route that reads `app.state.fetcharr_state` and returns 200 (all enabled apps connected) or 503 (any enabled app disconnected or not yet verified).

**When to use:** Container orchestrator probing (Docker HEALTHCHECK, Kubernetes liveness/readiness).

**Example:**
```python
from fastapi.responses import JSONResponse

@router.get("/health")
async def health(request: Request) -> JSONResponse:
    """Health probe for container orchestrators.

    Returns 200 when all enabled apps are reachable,
    503 when any enabled app is unreachable or not yet verified.
    """
    settings = request.app.state.settings
    state = request.app.state.fetcharr_state
    problems = []

    for app_name in ("radarr", "sonarr"):
        cfg = getattr(settings, app_name)
        if not cfg.enabled:
            continue
        app_state = state.get(app_name, {})
        connected = app_state.get("connected")
        if connected is not True:  # None (not yet run) or False (unreachable) → unhealthy
            problems.append(app_name)

    if problems:
        return JSONResponse(
            {"status": "unhealthy", "unreachable": problems},
            status_code=503,
        )
    return JSONResponse({"status": "ok"})
```

**Notes:**
- If no apps are enabled, `problems` stays empty → 200. This is correct: a container with no apps configured is not misconfigured, it's waiting for setup.
- `connected is not True` covers both `None` (never run yet) and `False` (failed). This means the health check is 503 on first startup until the first search cycle completes — which is acceptable. The Dockerfile `start-period=10s` accounts for this.
- Response body is JSON (small, parseable). The Dockerfile HEALTHCHECK CMD probes HTTP status only, not body.

### Pattern 3: Graceful Shutdown — Lock Drain + scheduler.shutdown(wait=True)

**What:** Before calling `scheduler.shutdown()` in the lifespan `finally` block, acquire `search_lock` to wait for any in-flight search cycle to complete, then shut down the scheduler and close resources.

**When to use:** SIGTERM from `docker stop` triggers uvicorn → lifespan `finally` → this sequence.

**Current code (scheduler.py lifespan `finally` block):**
```python
finally:
    scheduler.shutdown(wait=False)   # ← data loss risk: cuts off in-flight cycle
    for name in ("radarr", "sonarr"):
        client = getattr(app.state, f"{name}_client", None)
        if client:
            await client.close()
    await app.state.db.close()
    logger.info("Search engine stopped")
```

**Recommended fix:**
```python
finally:
    # Stop scheduler from firing new jobs
    scheduler.shutdown(wait=False)

    # Wait for any in-flight search cycle to complete before closing resources
    # This prevents mid-write DB corruption on SIGTERM
    async with app.state.search_lock:
        pass  # lock acquisition ensures any running cycle has released it

    # Close clients (from app.state — may have been replaced by config editor)
    for name in ("radarr", "sonarr"):
        client = getattr(app.state, f"{name}_client", None)
        if client:
            await client.close()

    # Close shared database connection
    await app.state.db.close()

    logger.info("Search engine stopped")
```

**Why `wait=False` then lock-drain instead of `wait=True` on scheduler:**

APScheduler's `scheduler.shutdown(wait=True)` with an `AsyncIOScheduler` waits for the executor's thread pool, but the search jobs are `async` coroutines running directly on the event loop — not in a thread pool. The `wait` parameter does not wait for async jobs to complete; it waits for the `ThreadPoolExecutor` which isn't used here. The `search_lock` is the correct synchronization primitive for this codebase's async jobs.

**Signal path:**
```
docker stop
  → SIGTERM → Python process (PID 1 via entrypoint.sh exec)
  → uvicorn.Server.handle_exit() sets should_exit=True
  → uvicorn main_loop exits
  → uvicorn calls lifespan shutdown (the finally block runs)
  → scheduler stopped, lock drained, clients closed, DB closed
  → process exits cleanly
```

The `exec` in `entrypoint.sh` ensures Python is PID 1 and receives SIGTERM directly — this is already correct.

### Pattern 4: CSRF Middleware Audit (DEBT-02)

**What:** `OriginCheckMiddleware` in `middleware.py` is already implemented and applied to ALL POST requests via `app.add_middleware(OriginCheckMiddleware)` in `__main__.py`. The existing test suite (`test_middleware.py`) covers 6 cases: matching origin, mismatched origin, matching referer, mismatched referer, missing both headers (allowed), GET bypass.

**Gap:** The success criterion for DEBT-02 is: "Settings POST requests without valid Origin/Referer headers are rejected." This is already true by the middleware's design, but needs verification that it applies to the settings route specifically (not just a test app). The existing `test_middleware.py` tests a standalone minimal app; there is no integration test verifying the middleware is wired into the full app and blocks `/settings` POST.

**Hardening audit checklist:**
1. Verify `OriginCheckMiddleware` is registered before the router in `__main__.py` — YES, `app.add_middleware(OriginCheckMiddleware)` is called before `app.include_router(router)`.
2. Verify cross-origin POST to `/settings` returns 403 — currently only tested on a test-app `/test` endpoint, not the real `/settings` route.
3. Edge case: What if `Host` header is missing entirely? `host = request.headers.get("host", "")` → empty string. `urlparse(origin).netloc` will be non-empty for any real origin → mismatch → 403. This is the safe behavior.
4. No changes to `middleware.py` logic are required. Only a targeted integration test for the settings route is the gap.

### Anti-Patterns to Avoid

- **Initializing rate-limit state at module level (dict literal in routes.py):** Module-level state persists across tests and pollutes test isolation. Initialize on `app.state` in the lifespan instead.
- **Using `time.time()` instead of `time.monotonic()`:** Wall clock can jump backward (NTP, DST). `time.monotonic()` is the correct choice for measuring durations.
- **Health check that makes outbound HTTP calls to Radarr/Sonarr:** This would be a live probe, slow, and dependent on external services being up at the moment of the check. The success criterion says "when both apps are reachable" — use the in-memory `connected` state tracked by search cycles, not a live probe.
- **`scheduler.shutdown(wait=True)` thinking it waits for async jobs:** With `AsyncIOScheduler`, `wait=True` only affects the thread pool executor. Async jobs run on the event loop, not in threads. Always use `search_lock` for async job drain.
- **Adding `/health` to `OriginCheckMiddleware` POST check:** `/health` is GET only; it passes through the middleware without needing any special treatment.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limit state storage | Custom class with TTL eviction | Simple dict + `time.monotonic()` | One endpoint, one app name, one timestamp per app — no complexity needed |
| CSRF protection | Custom token-based system | Origin/Referer check (already exists) | REQUIREMENTS.md explicitly chose this approach; cookie tokens inappropriate for sessionless app |
| Graceful shutdown hook | `signal.signal()` in `__main__.py` | Lifespan `finally` block | FastAPI lifespan is the canonical hook; uvicorn converts SIGTERM into lifespan shutdown automatically |

**Key insight:** All four requirements are satisfied by small modifications to existing files. The infrastructure (middleware, lifespan, search_lock, app.state) is already in place.

## Common Pitfalls

### Pitfall 1: Rate Limit Window Initialization Race
**What goes wrong:** `app.state.last_search_time` is accessed in the route before the lifespan has run (in tests that don't use the full lifespan fixture).
**Why it happens:** Tests that build a minimal `FastAPI()` app and call the router directly won't have `last_search_time` on `app.state`.
**How to avoid:** Initialize `app.state.last_search_time = {}` in the lifespan alongside `search_lock`, and in test fixtures that mock `app.state`.
**Warning signs:** `AttributeError: 'State' object has no attribute 'last_search_time'` in tests.

### Pitfall 2: Health Check Returns 200 Before First Search Cycle
**What goes wrong:** On first container start, no search cycle has run yet, so `connected` is `None` for all apps. Health check returns 503 indefinitely even when apps are reachable.
**Why it happens:** The search cycle sets `connected=True/False`; until it runs, the state has no `connected` key.
**How to avoid:** This is expected behavior — the health check truthfully reports "not yet verified." The Dockerfile `start-period=10s` means Docker won't count failures during startup. Accept 503 during startup; it resolves after the first scheduled cycle (which runs at `next_run_time=datetime.now(UTC)` — immediately on start).
**Warning signs:** Probing `/health` within the first few seconds of startup returns 503 — this is correct, not a bug.

### Pitfall 3: Middleware Not Applied to Settings Route
**What goes wrong:** A test verifies `OriginCheckMiddleware` on a standalone test app but the real app might not have it registered correctly.
**Why it happens:** `TestClient` for route tests in `test_web.py` builds a `FastAPI()` app with only the router — no middleware. So those tests don't exercise CSRF protection.
**How to avoid:** Write an integration test that adds `OriginCheckMiddleware` to the test app and POST to `/settings` with a mismatched Origin. This is the only real gap in DEBT-02.
**Warning signs:** `test_middleware.py` passes but a cross-origin POST to `/settings` in production is never explicitly tested.

### Pitfall 4: Shutdown Deadlock on search_lock
**What goes wrong:** If the search lock is already held by a job that itself is waiting for the event loop (e.g., a hanging HTTP request to Radarr), the `async with search_lock` in the shutdown sequence waits forever.
**Why it happens:** The outbound HTTP calls in search cycles have a configurable timeout (`request_timeout`, default 30s). A SIGTERM could arrive during a 30-second wait.
**How to avoid:** Use `asyncio.wait_for()` with a timeout when acquiring the lock during shutdown. If the lock cannot be acquired within the timeout, log a warning and proceed with forced closure. A 35-second timeout (slightly longer than max request_timeout) is a reasonable bound.
**Warning signs:** `docker stop` hangs for longer than expected; the container's stop timeout (`docker stop -t`) is relevant here (Docker default is 10s — shorter than the request timeout default).

**Concrete fix for Pitfall 4:**
```python
finally:
    scheduler.shutdown(wait=False)
    # Drain in-flight search cycle with bounded timeout
    try:
        await asyncio.wait_for(app.state.search_lock.acquire(), timeout=35.0)
        app.state.search_lock.release()
    except asyncio.TimeoutError:
        logger.warning("Shutdown: timed out waiting for search lock — forcing closure")
    # Close clients and DB regardless
    for name in ("radarr", "sonarr"):
        ...
```

### Pitfall 5: Rate Limit Blocks Scheduler Job (Not Just UI)
**What goes wrong:** If the rate limit state is checked per-incoming-HTTP-request only, it correctly blocks the UI button. If the rate-limit timestamp is accidentally shared with the scheduler, scheduled jobs would also get blocked.
**Why it happens:** Would happen if the rate limit were implemented in a middleware or on a shared state that the scheduler job also reads.
**How to avoid:** The rate limit check lives only in the `search_now` route handler. The scheduler jobs call `cycle_fn` directly and bypass the HTTP layer entirely — they are not affected by the rate limiter regardless of implementation.

## Code Examples

### Rate Limiter — Complete Handler Pattern

```python
# Source: project-specific pattern using stdlib time.monotonic()
import time

SEARCH_RATE_LIMIT_SECONDS = 10  # Minimum seconds between manual searches per app

@router.post("/api/search-now/{app_name}", response_class=HTMLResponse)
async def search_now(request: Request, app_name: str) -> HTMLResponse:
    if app_name not in ("radarr", "sonarr"):
        return HTMLResponse("Invalid app", status_code=400)

    client = getattr(request.app.state, f"{app_name}_client", None)
    if client is None:
        return HTMLResponse("App not enabled", status_code=400)

    # DEBT-01: Rate limit check before acquiring search lock
    now = time.monotonic()
    last = request.app.state.last_search_time.get(app_name, 0.0)
    if now - last < SEARCH_RATE_LIMIT_SECONDS:
        logger.info("{name}: Manual search rate-limited", name=app_name.title())
        return HTMLResponse("Rate limited — try again shortly", status_code=429)
    request.app.state.last_search_time[app_name] = now

    cycle_fn = run_radarr_cycle if app_name == "radarr" else run_sonarr_cycle
    async with request.app.state.search_lock:
        # ... existing search cycle code unchanged
```

### Health Endpoint — Complete Route

```python
# Source: project-specific pattern reading from app.state.fetcharr_state
from fastapi.responses import JSONResponse

@router.get("/health")
async def health(request: Request) -> JSONResponse:
    settings = request.app.state.settings
    state = request.app.state.fetcharr_state
    problems: list[str] = []

    for app_name in ("radarr", "sonarr"):
        cfg = getattr(settings, app_name)
        if not cfg.enabled:
            continue
        connected = state.get(app_name, {}).get("connected")
        if connected is not True:
            problems.append(app_name)

    if problems:
        return JSONResponse({"status": "unhealthy", "unreachable": problems}, status_code=503)
    return JSONResponse({"status": "ok"})
```

### Dockerfile HEALTHCHECK Update

```dockerfile
# Replace:
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/')" || exit 1

# With:
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1
```

Note: `start-period` increased from 10s to 30s to account for the fact that `/health` returns 503 until the first search cycle runs (which fires immediately at startup but takes time to complete its HTTP calls to Radarr/Sonarr).

### Graceful Shutdown — Complete Updated Finally Block

```python
# Source: project-specific pattern using asyncio.wait_for + search_lock
finally:
    # 1. Stop scheduler from scheduling new jobs
    scheduler.shutdown(wait=False)

    # 2. Drain any in-flight search cycle (prevents DB writes being cut off)
    try:
        await asyncio.wait_for(app.state.search_lock.acquire(), timeout=35.0)
        app.state.search_lock.release()
    except asyncio.TimeoutError:
        logger.warning("Shutdown: search cycle did not finish in 35s — forcing close")

    # 3. Close HTTP clients (app.state versions, post config-editor swaps)
    for name in ("radarr", "sonarr"):
        client = getattr(app.state, f"{name}_client", None)
        if client:
            await client.close()

    # 4. Close database connection (all writes complete per step 2)
    await app.state.db.close()

    logger.info("Search engine stopped")
```

### Lifespan State Initialization (add to existing lifespan)

```python
# In create_lifespan, after app.state.search_lock = asyncio.Lock(), add:
app.state.last_search_time: dict[str, float] = {}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Dockerfile HEALTHCHECK polls `/` (UI page) | Will poll `/health` (dedicated endpoint) | Phase 18 | Orchestrators get semantic 200/503 vs always-200 from UI |
| `scheduler.shutdown(wait=False)` | `wait=False` + `search_lock` drain | Phase 18 | Prevents in-flight DB writes from being cut off on SIGTERM |

**Deprecated/outdated:**
- Dockerfile `start-period=10s`: Too short once health check is `/health` (which returns 503 until first cycle). Update to 30s.

## Open Questions

1. **What window duration for rate limiting?**
   - What we know: "Rapid repeated clicks" is the threat; single-user tool. The test verifies "HTTP 429 after the first request within the rate limit window."
   - What's unclear: How short should the window be? 10s prevents button-mashing without annoying legitimate use.
   - Recommendation: 10 seconds. Short enough to not frustrate users who want to retry after fixing a problem; long enough to block button-mashing. This is Claude's discretion per CONTEXT.md.

2. **Should `/health` return 200 when no apps are enabled?**
   - What we know: If no apps are enabled, `problems` is empty and the endpoint returns 200.
   - What's unclear: Is an unconfigured container "healthy"?
   - Recommendation: Yes, return 200. A container with no apps configured is in a valid state (waiting for setup). The UI shows a "no apps configured" warning; the health check is for orchestrator restart decisions.

3. **Docker stop timeout interaction**
   - What we know: `docker stop` sends SIGTERM, waits 10 seconds by default, then sends SIGKILL. The search cycle's outbound HTTP requests have a default 30s timeout. If a cycle is mid-request at SIGTERM time, the 35s lock wait in shutdown could be killed by SIGKILL.
   - What's unclear: Should the docker-compose.yml add `stop_grace_period: 40s`?
   - Recommendation: Add `stop_grace_period: 40s` to docker-compose.yml, or document that users should set it. This is a nice-to-have; the shutdown is still cleaner than the current `wait=False` even without it.

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `fetcharr/web/middleware.py`, `fetcharr/web/routes.py`, `fetcharr/search/scheduler.py`, `fetcharr/db.py`, `fetcharr/__main__.py`, `fetcharr/startup.py`, `Dockerfile`, `entrypoint.sh`
- Runtime inspection: `uvicorn.server.Server` source — verified SIGTERM → `should_exit=True` → lifespan shutdown flow
- Runtime inspection: `apscheduler.schedulers.asyncio.AsyncIOScheduler.shutdown` — verified `wait=True` is thread-pool scoped, not async-job scoped
- `.planning/REQUIREMENTS.md` — verified exclusions (no slowapi, no Redis, no cookie CSRF tokens)

### Secondary (MEDIUM confidence)
- Python `time.monotonic()` documentation: recommended for elapsed-time measurements, immune to system clock adjustments (multiple authoritative sources)
- uvicorn SIGTERM behavior: verified via source inspection of `capture_signals()` and `handle_exit()` methods

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in pyproject.toml; verified versions from `uv run python -c`
- Architecture: HIGH — all patterns derived from direct codebase analysis, not speculation
- Pitfalls: HIGH — pitfall 4 (shutdown deadlock) verified via APScheduler source inspection

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (stable — no fast-moving dependencies involved)
