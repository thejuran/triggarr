# Phase 69: Code-track hardening - Pattern Map

**Mapped:** 2026-06-02
**Files analyzed:** 6 new/modified files
**Analogs found:** 6 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/search/scheduler.py` | service (extraction) | event-driven | itself — lift `job()` body lines 163–275 into `_run_one_cycle` | self-refactor |
| `triggarr/web/routes.py` | controller (call-site update) | request-response | `triggarr/search/scheduler.py` — `job()` closure for counter call sequence | role-match |
| `tests/test_scheduler.py` | test | event-driven | itself — lines 162–553 (`_build_outage_app` + 6 existing failure-counter tests) | self-extension |
| `pyproject.toml` | config (dependency pin) | — | itself — existing `fastapi` dependency entry line 15 | self-edit |
| `.gitleaksignore` | config (tooling) | — | itself — current 4 bare-path entries | self-replacement |
| `.gitignore` | config (repo hygiene) | — | itself — GSD/tooling transients block lines 69–74 | self-append |

---

## Pattern Assignments

### `triggarr/search/scheduler.py` — extract `_run_one_cycle` helper (CHARD-02)

**Self-refactor:** The new `_run_one_cycle` function is a mechanical lift of the
inner body of `make_search_job`'s `job()` closure. Every excerpt below is the
exact code that lifts; planner should instruct executor to extract it verbatim
rather than rewriting.

**What lifts — Inner try #1 (cycle execution), lines 163–186:**
```python
# --- Cycle execution (narrow-tuple catch; OSError REMOVED — Codex
# finding 2: OSError is durability, not transient *arr blip). ---
try:
    app.state.triggarr_state = await cycle_fn(
        client,
        app.state.triggarr_state,
        instance_name,
        instance_config,
        app.state.settings,
        app.state.db,
        get_tags_fn=_get_tags_cached,
    )
# SAFETY-02: narrow tuple — code-bug exceptions (RuntimeError,
# KeyError, etc.) intentionally propagate to APScheduler's
# EVENT_JOB_ERROR listener (_on_job_error). Do NOT add
# asyncio.CancelledError here: it is BaseException, not Exception,
# and the shutdown drain depends on its propagation.
# SAFETY-03 (Codex finding 2): OSError moved to the dedicated
# persistence branch below; persistence durability failures must
# not be conflated with transient *arr cycle blips.
except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error) as exc:
    _record_cycle_failure(app, job_id, app_name, reason=_sanitize_exc(exc))
    return
```

**What lifts — `_evaluate_cycle_outcome` call, line 192:**
```python
# SAFETY-03 (Codex finding 1): cycle outcome derived from
# state[app][inst][connected] — covers the REAL *arr outage path
# where the engine catches httpx.HTTPError internally, sets
# connected = False, and returns state without raising.
_evaluate_cycle_outcome(app, app_name, instance_name, job_id)
```

**What lifts — Inner try #2 (persistence), lines 199–218:**
```python
# SAFETY-03 (Codex finding 2): persistence is its own try/except.
# OSError / aiosqlite.Error here are durability failures, NOT
# transient *arr blips. Log ERROR immediately (no threshold gate),
# mark persistence_degraded, and re-raise so EVENT_JOB_ERROR also
# logs with job_id context. The counter is NOT incremented.
try:
    await asyncio.get_running_loop().run_in_executor(
        None, save_state, app.state.triggarr_state, state_path
    )
    # WR-09: clear `persistence_degraded` once a save succeeds.
    app.state.persistence_degraded = False
except (OSError, aiosqlite.Error) as persist_exc:
    app.state.persistence_degraded = True
    logger.error(
        "{app}: persistence failed -- {exc}",
        app=app_name.title(),
        exc=_sanitize_exc(persist_exc),
    )
    raise
```

**What STAYS in `job()` and is NOT lifted (scheduler-specific, lines 124–162, 220–275):**
- Client/config lookup from `app.state` at job-entry (lines 124–130)
- `job_id` construction (line 135) — must also be constructed in `_run_one_cycle` from its `(app_name, instance_name)` params
- `app.state.search_lock_holder` set (line 141) and clear in `finally` (line 274)
- `_get_tags_cached` closure construction (lines 152–161) — stays local in each caller; passed as parameter to `_run_one_cycle`
- Tracking check (lines 221–269) — scheduled path only; omit from `_run_one_cycle`

**Required function signature for `_run_one_cycle` (from RESEARCH.md §P68-FI-003):**
```python
async def _run_one_cycle(
    app: FastAPI,
    app_name: str,
    instance_name: str,
    client: ArrClient,
    instance_config: InstanceConfig,
    state_path: Path,
    get_tags_fn: Callable[[], Awaitable[list[Tag]]],
) -> None:
    """SAFETY-03: shared cycle body for both scheduled and manual search paths.

    Caller MUST hold app.state.search_lock for the full duration.
    Counter increment/reset, persistence, and persistence_degraded flag
    are all managed here so both paths share identical semantics.
    """
    job_id = f"{app_name}_{instance_name}_search"
    # [inner try #1 — cycle execution]
    # [_evaluate_cycle_outcome call]
    # [inner try #2 — persistence]
```

**TODO removal (D-02) — `_evaluate_cycle_outcome`, lines 322–343:**
Remove these lines verbatim (the full TODO block):
```python
    NOTE: This helper is invoked only from `make_search_job` (the APScheduler
    job factory). The manual-search-now endpoint in `triggarr/web/routes.py`
    invokes `cycle_fn(...)` directly and bypasses `make_search_job`, so a
    successful manual search does NOT currently reset the per-job counter,
    and a failing manual search does NOT currently increment it.
    TODO(SAFETY-03): refactor `search_now` to go through `make_search_job`
    (or extract a shared `_run_one_cycle(app, app_name, instance_name)`
    helper) so manual and scheduled searches share the same counter
    semantics. Deferred to a follow-up plan in v2.8 to keep this plan's
    diff focused on the scheduler path.
```
Also remove the comment at lines 342–343:
```python
    # connected is True or unknown — treat as success to avoid double-counting.
    # SAFETY-03: manual searches via search_now bypass this reset (see TODO
    # above). The cycle counter is per-scheduler-job today.
```

**Verify after edit:** `grep -rn "TODO(SAFETY-03)" triggarr/` must return nothing.

**Import additions needed in `scheduler.py`:** None — `ArrClient`, `Tag`, `Callable`, `Awaitable`, `Path`,
`asyncio`, `httpx`, `pydantic`, `aiosqlite`, `_sanitize_exc`, `save_state`, `_record_cycle_failure`,
`_evaluate_cycle_outcome` are all already imported/defined in-file.

**Module's existing import block (lines 22–55) — copy exactly for any new helper:**
```python
from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
import httpx
import pydantic
from apscheduler.events import EVENT_JOB_ERROR
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from loguru import logger

from triggarr.clients.base import ArrClient, Tag
from triggarr.clients.lidarr import LidarrClient
from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.db import init_db, migrate_from_state
from triggarr.models.config import APP_TYPES, Settings
from triggarr.search.engine import _sanitize_exc, run_lidarr_cycle, run_radarr_cycle, run_sonarr_cycle
from triggarr.state import (
    TriggarrState,
    _default_instance_state,
    cleanup_orphaned_instances,
    load_state,
    save_state,
)
from triggarr.tracking import run_tracking_check
from triggarr.update_check import check_for_update
```

---

### `triggarr/web/routes.py` — route `search_now` through `_run_one_cycle` (CHARD-02)

**Analog:** `triggarr/search/scheduler.py` `job()` closure pattern for counter calls.

**Current `search_now` handler body inside the lock (lines 904–962 — what changes):**
```python
    async with request.app.state.search_lock:
        # Re-check inside lock to prevent concurrent bypass (DRSEC-03)
        now = time.monotonic()
        last = request.app.state.last_search_time.get(rate_key, 0.0)
        if now - last < SEARCH_RATE_LIMIT_SECONDS:
            logger.info(
                "{name}/{inst}: Manual search rate-limited (after lock)",
                name=app_name.title(), inst=instance_name,
            )
            return HTMLResponse("Rate limited -- try again shortly", status_code=429)
        request.app.state.last_search_time[rate_key] = now

        # RES-03: manual searches read/populate the tag cache exactly like
        # scheduled cycles (same resolver shape as make_search_job's job()
        # closure). Without this, every manual search would re-fetch tags and
        # bypass RES-03. The resolver does NOT catch exceptions, so a failed
        # get_tags() propagates to the cycle fn's guard and is never cached.
        cache_key = (app_name, instance_name)

        async def _get_tags_cached() -> list[Tag]:
            cache = request.app.state.tag_cache
            entry = cache.get(cache_key)
            if entry is not None:
                cached_tags, fetched_at = entry
                if time.monotonic() - fetched_at < _TAG_CACHE_TTL_SECONDS:
                    return cached_tags
            fresh_tags = await client.get_tags()
            cache[cache_key] = (fresh_tags, time.monotonic())
            return fresh_tags

        try:
            request.app.state.triggarr_state = await cycle_fn(   # <-- REPLACE with _run_one_cycle
                client,
                request.app.state.triggarr_state,
                instance_name,
                instance_config,
                request.app.state.settings,
                request.app.state.db,
                get_tags_fn=_get_tags_cached,
            )
            await asyncio.get_running_loop().run_in_executor(     # <-- moves into _run_one_cycle
                None, save_state, request.app.state.triggarr_state, request.app.state.state_path
            )
            logger.info("{name}/{inst}: Manual search triggered", name=app_name.title(), inst=instance_name)
        except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
            # CR-01: same sanitization split applied in scheduler's ...
            logger.error(
                "{name}/{inst}: Manual search failed -- {exc}",
                name=app_name.title(),
                inst=instance_name,
                exc=(
                    _sanitize_exc(exc)
                    if isinstance(exc, httpx.HTTPError | pydantic.ValidationError)
                    else str(exc)
                ),
            )
```

**HTTP response contract — MUST be preserved exactly (lines 964–970):**
```python
    # Return updated card partial
    app_data = _build_app_context(request, app_name, instance_name)
    return templates.TemplateResponse(
        request=request,
        name="partials/app_card.html",
        context={"app": app_data},
    )
```
This is ALWAYS returned (no early 500) regardless of cycle outcome. The refactored handler must
preserve this: the outer try/except wraps the `_run_one_cycle` call and still falls through to the
TemplateResponse on any exception (including the persistence re-raise from `_run_one_cycle`).

**After refactor — structure inside lock:**
```python
    async with request.app.state.search_lock:
        # [rate-limit re-check — unchanged]
        # [_get_tags_cached closure — unchanged]
        try:
            await _run_one_cycle(
                request.app,
                app_name,
                instance_name,
                client,
                instance_config,
                request.app.state.state_path,   # state_path from app.state, not closure
                _get_tags_cached,
            )
            logger.info("{name}/{inst}: Manual search triggered", name=app_name.title(), inst=instance_name)
        except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
            logger.error(
                "{name}/{inst}: Manual search failed -- {exc}",
                name=app_name.title(),
                inst=instance_name,
                exc=(
                    _sanitize_exc(exc)
                    if isinstance(exc, httpx.HTTPError | pydantic.ValidationError)
                    else str(exc)
                ),
            )
    # Return updated card partial — always, even on failure [unchanged]
```

**Import addition to `routes.py` (line 50 already imports from `scheduler`):**
```python
from triggarr.search.scheduler import _TAG_CACHE_TTL_SECONDS, _run_one_cycle, make_search_job
```
(add `_run_one_cycle` to the existing import; the `cycle_fns` dict and `cycle_fn` lookup in
`search_now` can be removed since `_run_one_cycle` owns the dispatch internally via its `app_name`
parameter — or kept and passed as a parameter depending on planner's helper signature choice.)

**Key constraint (RESEARCH §Pitfall 3):** The handler must always return the TemplateResponse — never 500.
The `_run_one_cycle` persistence re-raise is caught by the outer `except` block and logged, then
execution falls through to the card render. This is the existing behavior: a failure still returns
200 + re-rendered card.

---

### `tests/test_scheduler.py` — add CHARD-03 tests (2 new tests)

**Self-extension of existing pattern.** New tests follow the `_build_outage_app` + MockTransport
pattern used by all 6 existing failure-counter tests. DO NOT patch `_record_cycle_failure` or
`_evaluate_cycle_outcome` — drive counter logic end-to-end through real `_run_one_cycle` call.

**The reusable helper to copy — `_build_outage_app` (lines 162–209):**
```python
def _build_outage_app(tmp_path, *, max_consecutive_failures=5, transport_handler):
    """Build a FastAPI app wired with a real RadarrClient on a MockTransport."""
    settings = make_settings()
    settings.general.max_consecutive_failures = max_consecutive_failures

    real_client = RadarrClient(base_url="http://radarr-test:7878", api_key="test-key")
    real_client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(transport_handler),
        base_url="http://radarr-test:7878",
        headers={"X-Api-Key": "test-key", "Content-Type": "application/json"},
    )
    real_client._app_name = "Radarr"

    state = _default_state(settings)
    state["radarr"]["Default"] = _default_instance_state()
    state["radarr"]["Default"]["connected"] = True

    app = FastAPI()
    app.state.radarr_clients = {"Default": real_client}
    app.state.sonarr_clients = {}
    app.state.lidarr_clients = {}
    app.state.search_lock = asyncio.Lock()
    app.state.search_lock_holder = None
    app.state.triggarr_state = state
    app.state.settings = settings
    app.state.search_failures = {}
    app.state.persistence_degraded = False
    app.state.tag_cache = {}
    app.state.db = AsyncMock()
    app.state.state_path = tmp_path / "state.json"

    job = make_search_job(app, "radarr", "Default", tmp_path / "state.json")
    return app, job
```

**The `_build_outage_app` variant for `search_now` tests:**
The CHARD-03 tests call `_run_one_cycle` directly (or invoke the `search_now` route via
`TestClient`) rather than `job()`. They need the same `app` + client setup as `_build_outage_app`
but WITHOUT creating a `make_search_job` job. Recommended: create a `_build_manual_app` helper
that mirrors `_build_outage_app` but returns `(app, real_client, instance_config)` instead of
`(app, job)`, so the test calls:
```python
await _run_one_cycle(app, "radarr", "Default", real_client, instance_config,
                     tmp_path / "state.json", _get_tags_cached)
```
directly inside `async with app.state.search_lock:` (as the helper requires the lock held by the caller).

**Existing test shape to mirror — `test_failure_counter_increments_on_real_arr_outage` (lines 212–245):**
```python
async def test_failure_counter_increments_on_real_arr_outage(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "Service unavailable"})

    app, job = _build_outage_app(tmp_path, transport_handler=handler)
    with (
        patch("triggarr.clients.base.asyncio.sleep", new=AsyncMock()),
        patch(
            "triggarr.search.scheduler.run_tracking_check",
            new=AsyncMock(return_value={"grabbed": 0, "partial": 0, "partial_expired": 0,
                                        "unresolved": 0, "errors": 0}),
        ),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
    ):
        await job()
        await job()
        await job()

    assert app.state.search_failures["radarr_Default_search"] == 3
    assert app.state.triggarr_state["radarr"]["Default"]["connected"] is False
```

**New test shape for CHARD-03 — `test_search_now_failure_counter_increment`:**
```python
async def test_search_now_failure_counter_increment(tmp_path):
    """CHARD-03: manual search_now failure increments app.state.search_failures.

    Mirrors test_failure_counter_increments_on_real_arr_outage but drives
    _run_one_cycle directly (the shared helper, not the APScheduler job wrapper).
    Does NOT patch _record_cycle_failure or _evaluate_cycle_outcome.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "Service unavailable"})

    # Build same app fixture as scheduled-path tests
    # [_build_manual_app variant here — same state shape as _build_outage_app
    #  but returns (app, real_client, instance_config) instead of (app, job)]

    with (
        patch("triggarr.clients.base.asyncio.sleep", new=AsyncMock()),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
    ):
        # _run_one_cycle requires caller holds search_lock
        async with app.state.search_lock:
            await _run_one_cycle(
                app, "radarr", "Default", real_client, instance_config,
                tmp_path / "state.json", _get_tags_cached,
            )
        async with app.state.search_lock:
            await _run_one_cycle(
                app, "radarr", "Default", real_client, instance_config,
                tmp_path / "state.json", _get_tags_cached,
            )

    assert app.state.search_failures["radarr_Default_search"] == 2
    assert app.state.triggarr_state["radarr"]["Default"]["connected"] is False
```

**New test shape for CHARD-03 — `test_search_now_failure_counter_resets_on_success`:**
```python
async def test_search_now_failure_counter_resets_on_success(tmp_path):
    """CHARD-03: successful manual search resets the failure counter to 0.

    Mirrors test_failure_counter_resets_on_success: drive fail then success
    via _run_one_cycle and assert counter trajectory F→reset.
    """
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(503, json={"error": "Service unavailable"})
        # Second call: success — tag endpoint + paginated body
        if request.url.path == "/api/v3/tag":
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json={"page": 1, "pageSize": 50, "sortKey": "id", "totalRecords": 0, "records": []},
        )

    # [_build_manual_app variant]

    with (
        patch("triggarr.clients.base.asyncio.sleep", new=AsyncMock()),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
    ):
        async with app.state.search_lock:
            await _run_one_cycle(...)  # cycle 1 — fail
        assert app.state.search_failures["radarr_Default_search"] == 1

        async with app.state.search_lock:
            await _run_one_cycle(...)  # cycle 2 — success
        assert app.state.search_failures["radarr_Default_search"] == 0
```

**Additional imports needed at top of test file** (add to existing import block at lines 8–32):
```python
from triggarr.search.scheduler import _TAG_CACHE_TTL_SECONDS, _run_one_cycle, make_search_job
```
(`_run_one_cycle` is new; `make_search_job` and `_TAG_CACHE_TTL_SECONDS` already imported at line 31.)

**Note on tracking patch:** The `_run_one_cycle` helper (per RESEARCH recommendation) does NOT include
`run_tracking_check` — that stays in `job()` only. So CHARD-03 tests do NOT need the
`run_tracking_check` patch that the existing scheduled-path tests use.

**Note on `save_state` patch:** `_run_one_cycle` calls `save_state` internally (persistence branch),
so CHARD-03 tests MUST patch `triggarr.search.scheduler.save_state` to `MagicMock()` to avoid
filesystem writes (same as existing tests).

---

### `pyproject.toml` — raise fastapi pin (CHARD-04 / P68-FI-002)

**Current entry (line 15):**
```toml
"fastapi",
```

**Target entry:**
```toml
"fastapi>=0.136.3",   # >=0.136.1 pulls starlette>=1.0.0; 0.136.3 is latest 2026-06-02
```

**Context: surrounding dependencies block (lines 10–24) for positioning:**
```toml
dependencies = [
    "pydantic-settings[toml]",
    "httpx",
    "loguru",
    "tomli-w",
    "fastapi",           # <-- line 15, replace this line
    "uvicorn[standard]",
    "apscheduler>=3.11,<4",
    "jinja2",
    "aiofiles",
    "aiosqlite",
    "python-multipart>=0.0.27",
    "bcrypt",
    "itsdangerous",
]
```

**Verify commands (from RESEARCH §P68-FI-002):**
```bash
uv lock
uv run python -c "import importlib.metadata; print(importlib.metadata.version('starlette'))"
# must be >=1.0.1
uv run pytest tests/ -x -q
uv run ruff check triggarr/ tests/
uv export --no-dev --no-emit-project --format requirements-txt > /tmp/r.txt
uv run pip-audit -r /tmp/r.txt --format json | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print('CLEAN' if not [x for x in d['dependencies'] if x.get('vulns')] else 'VULN')"
```

---

### `.gitleaksignore` — convert to 8.x fingerprints (CHARD-04 / P68-FI-001)

**Current file (4 bare-path entries — all rejected by gitleaks 8.30.x):**
```
# Test fixture API keys -- not real credentials
tests/test_auth_middleware.py
tests/test_auth_routes.py
tests/test_auth_integration.py
tests/test_auth_config.py
```

**Target format (gitleaks 8.x fingerprint per line):**
```
# False-positive fingerprints (all generic-api-key, all confirmed test fixtures or doc prose)
commitSHA:filepath:rule:line
```

**CRITICAL EXECUTOR NOTE (RESEARCH §Risk Flag — New Commits Since Research):**
The 23 fingerprints in RESEARCH.md §P68-FI-001 were captured at HEAD `abe85e5` (2026-06-02).
Phase 69's own planning/research commits will advance HEAD and may add new `generic-api-key` prose
hits. The executor MUST regenerate fingerprints from a live run immediately before writing the file:
```bash
gitleaks git . --no-banner --report-format json --report-path /tmp/gl_report.json --redact
python3 -c "
import json
data = json.load(open('/tmp/gl_report.json'))
for h in data:
    print(h['Fingerprint'])
"
```
Write ALL emitted fingerprints into `.gitleaksignore` (not just the original 4 test-file paths).
The RESEARCH.md list of 23 is a lower-bound reference; the actual count at executor time may be higher.

**Verify after write:**
```bash
gitleaks git . --no-banner --redact 2>&1 | grep -E "Invalid .gitleaksignore entry|leaks found"
# Expected: no "Invalid entry" lines; "leaks found: 0"
```

---

### `.gitignore` — add `.orchestrator.json` (CHARD-01 / P68-FI-004)

**Insertion point — GSD/tooling transients block (lines 69–74):**
```
# ── GSD / tooling transients (machine-generated, not source) ──
.planning/HANDOFF.json
.turingmind/
.claude/scheduled_tasks.lock
.playwright-mcp/
```

**Target state (append `.orchestrator.json` to the block):**
```
# ── GSD / tooling transients (machine-generated, not source) ──
.planning/HANDOFF.json
.turingmind/
.claude/scheduled_tasks.lock
.playwright-mcp/
.orchestrator.json
```

**Verify after edit:**
```bash
git check-ignore .orchestrator.json
# Must output: .orchestrator.json

git status --porcelain | grep "\.orchestrator\.json"
# Must return nothing (file no longer shown as untracked)
```

**Audit-and-close sweep (D-10) — run after .gitignore edit:**
```bash
git status --porcelain | grep "^??"  # review each untracked file
git ls-files | grep -E "\.(DS_Store|swp|code-workspace|swo)$"  # must return empty
```

---

## Shared Patterns

### Exception handling in cycle code
**Source:** `triggarr/search/scheduler.py` lines 184–186, 211–218
**Apply to:** `_run_one_cycle` body, `search_now` outer catch

Two distinct exception-handling scopes that must NOT be merged:
1. **Narrow-tuple for cycle blips** — `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error)` — increments counter and returns
2. **OSError + aiosqlite.Error for persistence** — logs ERROR, sets `persistence_degraded = True`, re-raises

The existing `search_now` catch uses a flat `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` that conflates both. The refactor separates them inside `_run_one_cycle` while the outer `search_now` catch wraps `_run_one_cycle` to handle the persistence re-raise gracefully for the HTTP response.

### Log sanitization (CR-01)
**Source:** `triggarr/web/routes.py` lines 949–962, `triggarr/search/scheduler.py` lines 260–268
**Apply to:** Any new `logger.error` / `logger.warning` with an exception

```python
exc=(
    _sanitize_exc(exc)
    if isinstance(exc, httpx.HTTPError | pydantic.ValidationError)
    else str(exc)
)
```
httpx/pydantic exceptions may carry `?apikey=` query strings; aiosqlite/OSError do not.

### job_id key convention
**Source:** `triggarr/search/scheduler.py` lines 135, 279–304
**Apply to:** `_run_one_cycle` internal construction, CHARD-03 test assertions

```python
job_id = f"{app_name}_{instance_name}_search"
# Example: "radarr_Default_search"
```
All counter dict accesses use this key: `app.state.search_failures[job_id]`.

### Loguru call style (no f-strings in log calls)
**Source:** `triggarr/search/scheduler.py` lines 213–217, routes.py lines 953–962
**Apply to:** Any new `logger.*` calls in `_run_one_cycle` and updated `search_now`

```python
logger.error(
    "{app}: persistence failed -- {exc}",
    app=app_name.title(),
    exc=_sanitize_exc(persist_exc),
)
```
Use `{placeholder}` + keyword args, not f-strings. Loguru defers interpolation; f-strings defeat lazy evaluation and risk logging secrets if `_sanitize_exc` is bypassed.

---

## No Analog Found

All 6 files have direct self-analogs or close role-match analogs. No file requires pulling patterns
from RESEARCH.md only.

---

## Metadata

**Analog search scope:** `triggarr/search/`, `triggarr/web/`, `tests/`, repo root config files
**Files read:** `scheduler.py` (full, 400+ lines), `routes.py` (header + lines 875–970),
`tests/test_scheduler.py` (lines 1–553), `tests/conftest.py` (lines 1–77),
`pyproject.toml` (lines 1–46), `.gitignore` (lines 1–74), `.gitleaksignore` (lines 1–5)
**Pattern extraction date:** 2026-06-02
