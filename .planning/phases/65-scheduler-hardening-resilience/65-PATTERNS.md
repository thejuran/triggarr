# Phase 65: Scheduler Hardening & Resilience - Pattern Map

**Mapped:** 2026-05-25
**Files to modify:** 4 source + 3 tests
**Analogs found:** 7 / 7 (all required patterns already exist in the codebase)

## Scope Extracted from RESEARCH.md

No CONTEXT.md exists for Phase 65. The file list is extracted directly from
RESEARCH.md sections "Implementation Approach" (lines 325-426) and "Validation
Architecture" (lines 696-723):

| Target | Action | RESEARCH cite |
|--------|--------|---------------|
| `triggarr/search/scheduler.py:124` | Narrow `except Exception` → narrow tuple; add `_record_failure` logic; add `EVENT_JOB_ERROR` listener registration; bump 35.0→60.0; add `app.state.search_failures` + `app.state.search_lock_holder` initialization; track holder inside lock with `try/finally`; rewrite TimeoutError branch | 327-426 |
| `triggarr/models/config.py:85` | Add `max_consecutive_failures: int = 5` to GeneralConfig | 350 |
| `triggarr/config.py:33` | Add commented `# max_consecutive_failures = 5` after `# tracking_delay_seconds = 90` line in DEFAULT_CONFIG | 351 |
| `triggarr/web/routes.py:500` | Add `safe_int(form.get("max_consecutive_failures"), 5, 1, 100)` to general dict; add context dict entry around line 402 | 374-376 |
| `triggarr/templates/settings.html` | Add number input for `max_consecutive_failures` (min=1 max=100) after `tracking_window_minutes` block | 376 |
| `tests/test_scheduler.py:35-55` | **Invert** existing `test_make_search_job_exception_swallowed` (rename, assert `pytest.raises(RuntimeError)`) | 343 |
| `tests/test_scheduler.py` (new tests) | Add ~7 new tests: httperror_swallowed, event_job_error_listener, failure_counter_{increments,escalates,resets,per_instance}, shutdown_timeout_is_60s, shutdown_timeout_logs_holder | 700-710 |
| `tests/test_clients.py` (new tests) | Add TEST-04: `test_aclose_does_not_hang_with_in_flight_requests` (+ optional `test_aclose_raises_when_requests_in_flight`) | 711-712 |
| `tests/test_config.py` (1 new test) | `test_general_config_default_max_consecutive_failures` — mirror `test_skip_unreleased_defaults_true` shape | 707 |

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/search/scheduler.py` (narrow exception + counter + listener + drain) | scheduler infrastructure / async job wrapper | event-driven (APScheduler) + request-response (httpx outbound) | `triggarr/search/engine.py:313-321` (narrow-tuple discrimination, `_sanitize_exc`) + self `scheduler.py:221` (`app.state.last_search_time` per-job dict) + self `scheduler.py:241-247` (APScheduler `add_job` pattern) | exact (each piece) |
| `triggarr/models/config.py` (new `max_consecutive_failures` field) | config model / pydantic BaseModel | request-response (TOML load) | self `models/config.py:79-83` (existing int-default fields on GeneralConfig — `max_history_rows`, `request_timeout`, `tracking_window_minutes`, `tracking_delay_seconds`) | exact |
| `triggarr/config.py` (DEFAULT_CONFIG template line) | config layer / TOML template | file-I/O | self `config.py:28-33` (existing commented defaults inside `[general]`) | exact |
| `triggarr/web/routes.py` (form handler + context dict) | route handler / form POST | request-response | self `routes.py:500` (`max_history_rows` safe_int wiring); self `routes.py:398` (template context dict) | exact |
| `triggarr/templates/settings.html` (number input) | UI template / HTML form | request-response | self `templates/settings.html:42-47` (`max_history_rows` `<input type="number" min="0" max="100000">`) | exact |
| `tests/test_scheduler.py` (inversion + 7 new tests) | unit test / scheduler behavior | event-driven | self `tests/test_scheduler.py:35-55, 63-89` (existing patch+AsyncMock+loguru-sink shape) | exact |
| `tests/test_clients.py` (TEST-04 aclose test) | unit test / async client lifecycle | event-driven (asyncio cancel) + request-response | self `tests/test_clients.py:83-97` (`_ConcreteClient + MockTransport` pattern) | exact (with extension to async handler + `asyncio.wait_for`) |
| `tests/test_config.py` (1 default-value test) | unit test / pydantic defaults | n/a (in-memory construction) | self `tests/test_config.py:153-155` (`test_skip_unreleased_defaults_true`) | exact |

## Pattern Assignments

### `triggarr/search/scheduler.py` — narrow exception (SAFETY-02)

**Analog:** `triggarr/search/engine.py:313-321` and `engine.py:426-431` — the canonical narrow-tuple-plus-sanitize pattern used 22× in engine.py.

**Imports already present at scheduler.py:18-23** — no new module imports needed for the narrow tuple itself:
```python
import aiosqlite
import httpx
import pydantic
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from loguru import logger
```

**New imports needed (planner — add at top of scheduler.py):**
```python
import time  # RES-01: monotonic timestamp for lock_holder
from apscheduler.events import EVENT_JOB_ERROR  # SAFETY-02: listener for propagated types
from triggarr.search.engine import _sanitize_exc  # SAFETY-03: safe exc logging
```

(Precedent for cross-module `_`-prefixed import: `scheduler.py:232` already does `from triggarr.web.routes import _sync_auth_state` — same convention.)

**Existing narrow-tuple discrimination pattern to copy** (`engine.py:313-321`):
```python
try:
    missing = await client.get_wanted_missing()
    cutoff = await client.get_wanted_cutoff()
except (httpx.HTTPError, pydantic.ValidationError) as exc:
    logger.warning("Radarr: Cycle aborted -- {exc}", exc=_sanitize_exc(exc))
```

**Existing four-type narrow tuple to mirror** (`engine.py:426`, used 22 sites):
```python
except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
    logger.warning(
        "Radarr: Failed to search {title}: {exc}",
        title=movie.get("title", "unknown"),
        exc=_sanitize_exc(exc),
    )
```

**Current broken code to replace** (`scheduler.py:124-129`):
```python
        except Exception as exc:
            logger.error(
                "{app}: Unhandled error in search cycle -- {exc}",
                app=app_name.title(),
                exc=exc,
            )
```

**Patch shape (SAFETY-02 + SAFETY-03 combined — from RESEARCH 352-373, 581-607):**
```python
        except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
            job_id = f"{app_name}_{instance_name}_search"
            count = app.state.search_failures.get(job_id, 0) + 1
            app.state.search_failures[job_id] = count
            threshold = app.state.settings.general.max_consecutive_failures
            log_fn = logger.error if count >= threshold else logger.warning
            log_fn(
                "{app}: search cycle failed ({count}/{threshold}) -- {exc}",
                app=app_name.title(),
                count=count,
                threshold=threshold,
                exc=_sanitize_exc(exc),
            )
        finally:
            app.state.search_lock_holder = None  # RES-01
```

**Invariants to preserve:**
- `asyncio.CancelledError` MUST remain uncaught — it is `BaseException`, not in narrow tuple; shutdown drain depends on its propagation (RESEARCH Pitfall 7, lines 541-544).
- `PendingCapExceeded` is already caught inside each engine cycle (verified at engine.py:416 etc.) — won't reach this handler.
- The tracking-check inner `try/except` at scheduler.py:119 already uses the correct narrow tuple — leave it unchanged.

---

### `triggarr/search/scheduler.py` — EVENT_JOB_ERROR listener (SAFETY-02 sibling)

**Analog:** No existing `add_listener` call in the codebase (verified: `grep -rn "EVENT_JOB\|add_listener" triggarr/` returns zero). This is a new pattern. Closest precedent is the existing `add_job` shape immediately above.

**Existing `add_job` pattern to copy positionally** (`scheduler.py:241-247, 264-270`):
```python
scheduler.add_job(
    job_fn,
    "interval",
    minutes=cfg.search_interval,
    id=job_id,
    next_run_time=datetime.now(UTC),
)
```

**Patch shape (RESEARCH 332-342, 612-624):**
Insert AFTER all `add_job` calls but BEFORE `scheduler.start()` (around scheduler.py:254-255):
```python
def _on_job_error(event):
    logger.error(
        "Job {job} failed unexpectedly: {type}: {exc}",
        job=event.job_id,
        type=type(event.exception).__name__,
        exc=_sanitize_exc(event.exception)
            if isinstance(event.exception, (httpx.HTTPError, pydantic.ValidationError))
            else str(event.exception),
    )

scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
scheduler.start()
```

**Note on sanitization:** RESEARCH 740 (Security Domain) requires sanitizing httpx exceptions because `httpx.HTTPError.request.url` may carry credentials. For non-httpx types (RuntimeError, KeyError, etc.), `str(event.exception)` is safe per RESEARCH Open Question 3 (lines 803-806).

---

### `triggarr/search/scheduler.py` — consecutive-failure counter (SAFETY-03)

**Analog:** `triggarr/search/scheduler.py:221` — `app.state.last_search_time: dict[str, float] = {}` is the canonical per-job-id in-memory dict on `app.state`.

**Existing per-job dict pattern** (`scheduler.py:221`):
```python
app.state.last_search_time: dict[str, float] = {}
```

Used in `routes.py:818-839`:
```python
last = request.app.state.last_search_time.get(rate_key, 0.0)
...
request.app.state.last_search_time[rate_key] = now
```

**Patch shape — initialization (RESEARCH 352):**
Add alongside line 221 in `create_lifespan`:
```python
app.state.last_search_time: dict[str, float] = {}
app.state.search_failures: dict[str, int] = {}                  # SAFETY-03
app.state.search_lock_holder: tuple[str, float] | None = None   # RES-01
```

**Patch shape — reset on success (RESEARCH 369-373, 590):**
Inside `make_search_job`'s success path, after `save_state` returns successfully but before the tracking block:
```python
app.state.triggarr_state = await cycle_fn(...)
await asyncio.get_running_loop().run_in_executor(
    None, save_state, app.state.triggarr_state, state_path
)
app.state.search_failures[job_id] = 0  # SAFETY-03: reset on success
# --- Tracking check (unchanged) ---
```

**Per-instance scoping:** Each `(app_type, instance_name)` produces a distinct `job_id`, so the counter is naturally per-instance — same property as `last_search_time`. Verified test: `test_failure_counter_per_instance_scoped` must drive Radarr/Default and Radarr/4K independently.

---

### `triggarr/search/scheduler.py` — lock holder tracking + 60s timeout (RES-01)

**Analog:** `triggarr/search/engine.py:304` — `cycle_start = time.monotonic()` is the canonical monotonic-timestamp precedent.

**Existing monotonic pattern** (`engine.py:304`):
```python
cycle_start = time.monotonic()
```

**Existing shutdown drain to extend** (`scheduler.py:272-293`):
```python
try:
    yield
finally:
    # 1. Stop scheduler from scheduling new jobs (does NOT wait for async jobs)
    scheduler.shutdown(wait=False)

    # 2. Drain any in-flight search cycle before closing resources (DEBT-06)
    try:
        await asyncio.wait_for(app.state.search_lock.acquire(), timeout=35.0)
        app.state.search_lock.release()
    except TimeoutError:
        logger.warning("Shutdown: search cycle did not finish in 35s — forcing close")
    ...
```

**Patch shape — holder tracking inside job wrapper (RESEARCH 395-406):**
Inside `make_search_job`'s `async with app.state.search_lock:` block (scheduler.py:80), set holder before `cycle_fn`, clear in `finally`:
```python
async with app.state.search_lock:
    job_id = f"{app_name}_{instance_name}_search"
    app.state.search_lock_holder = (job_id, time.monotonic())  # RES-01
    try:
        app.state.triggarr_state = await cycle_fn(...)
        await asyncio.get_running_loop().run_in_executor(None, save_state, ...)
        app.state.search_failures[job_id] = 0                   # SAFETY-03
        # --- Tracking check (unchanged inner try/except) ---
        ...
    except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
        # ... failure-counter branch from SAFETY-03 ...
    finally:
        app.state.search_lock_holder = None                     # RES-01
```

**Patch shape — shutdown timeout branch (RESEARCH 247-260, 640-655):**
Replace scheduler.py:279-283:
```python
try:
    await asyncio.wait_for(app.state.search_lock.acquire(), timeout=60.0)
    app.state.search_lock.release()
except TimeoutError:
    holder = getattr(app.state, "search_lock_holder", None)
    if holder:
        job_id, started = holder
        elapsed = time.monotonic() - started
        logger.warning(
            "Shutdown: search cycle did not finish in 60s -- job={job} elapsed={elapsed:.1f}s -- forcing close",
            job=job_id,
            elapsed=elapsed,
        )
    else:
        logger.warning(
            "Shutdown: search lock did not drain in 60s (no holder recorded) -- forcing close"
        )
```

**Invariants to preserve:**
- The holder assignment MUST be INSIDE `async with app.state.search_lock:` (RESEARCH Pitfall 4, lines 526-529). Setting it before the lock allows two jobs to overwrite each other.
- Use `time.monotonic()`, NEVER `time.time()` (RESEARCH Pitfall 3, lines 521-524).
- Use `getattr(app.state, "search_lock_holder", None)` in shutdown branch in case lifespan failed before initialization.

---

### `triggarr/models/config.py` — new `max_consecutive_failures` field (SAFETY-03)

**Analog:** `triggarr/models/config.py:79-83` — the existing block of int-typed defaults in GeneralConfig.

**Existing pattern to copy** (`models/config.py:79-83`):
```python
class GeneralConfig(BaseModel):
    """Global application settings."""

    log_level: str = "info"
    hard_max_per_cycle: int = 0  # 0 = unlimited; caps total items per app per cycle
    # v2.0 additions
    max_history_rows: int = 1000  # DEBT-03: max resolved rows kept in search_history
    request_timeout: float = 30.0  # DEBT-07: outbound HTTP timeout in seconds
    page_size: int = 50  # DEBT-08: *arr API pagination size
    tracking_window_minutes: int = 60  # TRACK-07: how long to wait for grabs after search
    tracking_delay_seconds: int = 90  # Delay before tracking check (unused)
    # v2.2: skip Radarr movies without past digital/physical release date
    skip_unreleased: bool = True
```

**Patch shape (RESEARCH 184, 350):**
Add immediately after `tracking_delay_seconds`:
```python
    tracking_delay_seconds: int = 90  # Delay before tracking check (unused)
    max_consecutive_failures: int = 5  # SAFETY-03: escalate WARNING→ERROR after N consecutive failures
    # v2.2: skip Radarr movies without past digital/physical release date
    skip_unreleased: bool = True
```

**Naming convention check:** `max_consecutive_failures` follows existing snake_case + descriptive + "max_"-prefix-when-cap pattern (`max_history_rows`, `hard_max_per_cycle`).

---

### `triggarr/config.py` — DEFAULT_CONFIG template addition

**Analog:** `triggarr/config.py:28-34` — the commented-default block in `[general]`.

**Existing pattern to copy** (`config.py:25-34`):
```python
[general]
# Log level: debug, info, warning, error
log_level = "info"
# hard_max_per_cycle = 0
# max_history_rows = 1000
# request_timeout = 30.0
# page_size = 50
# tracking_window_minutes = 60
# tracking_delay_seconds = 90
# skip_unreleased = true
```

**Patch shape (RESEARCH 188-192, 351):**
Add commented line after `# tracking_delay_seconds = 90`:
```python
# tracking_delay_seconds = 90
# max_consecutive_failures = 5
# skip_unreleased = true
```

The commented form means "documented default — uncomment to override". Matches all sibling entries.

---

### `triggarr/web/routes.py` — POST /settings form field + context dict (SAFETY-03)

**Analog:** `triggarr/web/routes.py:500` — `safe_int(form.get("max_history_rows"), 1000, 0, 100_000)` is the exact-shape sibling.

**Existing form-handling pattern to copy** (`routes.py:496-507`):
```python
new_config: dict = {
    "general": {
        "log_level": safe_log_level(form.get("log_level")),
        "hard_max_per_cycle": safe_int(form.get("hard_max_per_cycle"), 0, 0, 1000),
        "max_history_rows": safe_int(form.get("max_history_rows"), 1000, 0, 100_000),
        "request_timeout": safe_int(form.get("request_timeout"), 30, 5, 300),
        "page_size": safe_int(form.get("page_size"), 50, 10, 500),
        "tracking_window_minutes": safe_int(form.get("tracking_window_minutes"), 60, 5, 1440),
        "tracking_delay_seconds": current_settings.general.tracking_delay_seconds,
        "skip_unreleased": form.get("skip_unreleased") == "on",
    },
}
```

**Patch shape — form handling (RESEARCH 196):**
Add one entry, alongside `tracking_window_minutes`:
```python
        "tracking_window_minutes": safe_int(form.get("tracking_window_minutes"), 60, 5, 1440),
        "tracking_delay_seconds": current_settings.general.tracking_delay_seconds,
        "max_consecutive_failures": safe_int(form.get("max_consecutive_failures"), 5, 1, 100),
        "skip_unreleased": form.get("skip_unreleased") == "on",
```

**Existing template-context pattern to copy** (`routes.py:394-408`):
```python
context={
    "apps": apps,
    "log_level": settings.general.log_level,
    "hard_max_per_cycle": settings.general.hard_max_per_cycle,
    "max_history_rows": settings.general.max_history_rows,
    "request_timeout": settings.general.request_timeout,
    "page_size": settings.general.page_size,
    "tracking_window_minutes": settings.general.tracking_window_minutes,
    "tracking_delay_seconds": settings.general.tracking_delay_seconds,
    "skip_unreleased": settings.general.skip_unreleased,
    ...
},
```

**Patch shape — context dict (RESEARCH 200):**
Add immediately after `tracking_delay_seconds`:
```python
    "tracking_delay_seconds": settings.general.tracking_delay_seconds,
    "max_consecutive_failures": settings.general.max_consecutive_failures,
    "skip_unreleased": settings.general.skip_unreleased,
```

**Validation bounds rationale:** `safe_int(..., 5, 1, 100)` — lower bound 1 prevents "escalate-immediately"; upper bound 100 defends against typos. Matches the wider `safe_int(..., default, lo, hi)` convention used throughout the file.

---

### `triggarr/templates/settings.html` — number input for `max_consecutive_failures`

**Analog:** `triggarr/templates/settings.html:42-47` — the `max_history_rows` input.

**Existing pattern to copy** (`templates/settings.html:41-47`):
```html
<div>
    <label class="block text-sm text-triggarr-muted mb-1">Max History Rows</label>
    <input type="number" name="max_history_rows" value="{{ max_history_rows }}"
           min="0" max="100000"
           class="w-full bg-triggarr-bg border border-triggarr-border rounded px-3 py-2 text-sm">
    <p class="text-xs text-triggarr-muted mt-1">0 = unlimited. Max resolved rows kept in search history.</p>
</div>
```

**Patch shape:**
Insert after the `tracking_window_minutes` block (templates/settings.html:62-68), before the `skip_unreleased` checkbox:
```html
<div>
    <label class="block text-sm text-triggarr-muted mb-1">Max Consecutive Failures</label>
    <input type="number" name="max_consecutive_failures" value="{{ max_consecutive_failures }}"
           min="1" max="100"
           class="w-full bg-triggarr-bg border border-triggarr-border rounded px-3 py-2 text-sm">
    <p class="text-xs text-triggarr-muted mt-1">After N consecutive search cycle failures, escalate log level from warning to error.</p>
</div>
```

Tailwind classes copied verbatim from sibling inputs — do not invent new ones. `min`/`max` attributes match the `safe_int` bounds in `routes.py`.

---

### `tests/test_scheduler.py` — invert existing test + add 7 new tests

**Analog:** Existing tests in same file — `test_make_search_job_exception_swallowed` (lines 35-55), `test_search_job_logs_tracking_results` (lines 226-266, for loguru sink capture pattern), `test_shutdown_drains_search_lock` (lines 63-89, for lifespan fixture pattern).

**Imports already present at test_scheduler.py:8-21:**
```python
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
from fastapi import FastAPI

from tests.conftest import make_settings
from triggarr.db import init_db, insert_search_entry
from triggarr.search.scheduler import make_search_job
from triggarr.state import _default_state, save_state
```

**New imports needed (planner):**
```python
import io
import time
import httpx
import pytest
from loguru import logger
```

#### Inversion: `test_make_search_job_exception_swallowed` → propagation

**Existing test to invert** (`test_scheduler.py:35-55`):
```python
async def test_make_search_job_exception_swallowed():
    """Job catches and swallows unhandled exceptions from cycle function."""
    app = FastAPI()
    app.state.radarr_clients = {"Default": AsyncMock()}
    app.state.search_lock = asyncio.Lock()
    app.state.triggarr_state = _default_state(make_settings())
    app.state.settings = make_settings()

    with (
        patch(
            "triggarr.search.scheduler.run_radarr_cycle",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
        patch(
            "triggarr.search.scheduler.save_state",
            new=MagicMock(),
        ),
    ):
        job = make_search_job(app, "radarr", "Default", Path("/tmp/state.json"))
        # Should NOT raise -- exception is caught internally
        await job()
```

**Patch shape — rename + invert (RESEARCH 343, 536-539, 700):**
```python
async def test_make_search_job_unexpected_exception_propagates():
    """SAFETY-02: unexpected (non-narrow-tuple) exceptions now propagate.

    RuntimeError is NOT in (httpx.HTTPError, pydantic.ValidationError,
    aiosqlite.Error, OSError), so it must escape the wrapper and reach
    APScheduler's EVENT_JOB_ERROR listener.
    """
    app = FastAPI()
    app.state.radarr_clients = {"Default": AsyncMock()}
    app.state.search_lock = asyncio.Lock()
    app.state.search_failures = {}                            # SAFETY-03 init
    app.state.search_lock_holder = None                       # RES-01 init
    app.state.triggarr_state = _default_state(make_settings())
    app.state.settings = make_settings()

    with (
        patch("triggarr.search.scheduler.run_radarr_cycle",
              new=AsyncMock(side_effect=RuntimeError("boom"))),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
        pytest.raises(RuntimeError, match="boom"),
    ):
        job = make_search_job(app, "radarr", "Default", Path("/tmp/state.json"))
        await job()
```

#### Sibling test: narrow-tuple type IS swallowed

```python
async def test_make_search_job_httperror_swallowed():
    """SAFETY-02: httpx.ConnectError IS still caught (it's in the narrow tuple)."""
    app = FastAPI()
    app.state.radarr_clients = {"Default": AsyncMock()}
    app.state.search_lock = asyncio.Lock()
    app.state.search_failures = {}
    app.state.search_lock_holder = None
    app.state.triggarr_state = _default_state(make_settings())
    app.state.settings = make_settings()

    with (
        patch("triggarr.search.scheduler.run_radarr_cycle",
              new=AsyncMock(side_effect=httpx.ConnectError("connection refused"))),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
    ):
        job = make_search_job(app, "radarr", "Default", Path("/tmp/state.json"))
        await job()  # MUST NOT raise

    assert app.state.search_failures["radarr_Default_search"] == 1
```

#### Loguru sink capture pattern (used by escalation tests)

**Analog:** `tests/test_scheduler.py:226-266` (`test_search_job_logs_tracking_results`):
```python
from loguru import logger

captured_messages = []

def sink(message):
    captured_messages.append(str(message))

sink_id = logger.add(sink, level="INFO")
try:
    ...
    await job()
    tracking_logs = [m for m in captured_messages if "Tracking:" in m]
    assert len(tracking_logs) > 0
finally:
    logger.remove(sink_id)
```

**For SAFETY-03 escalation tests** (RESEARCH Pitfall 8, lines 546-549) use `format="{level} | {message}"` so the test can discriminate WARNING vs ERROR:
```python
sink = io.StringIO()
handler_id = logger.add(sink, format="{level} | {message}", level="WARNING")
try:
    ...
finally:
    logger.remove(handler_id)
assert "ERROR | " in sink.getvalue()  # 3rd call escalated
```

#### Shutdown holder-identity test pattern

**Analog:** `tests/test_scheduler.py:63-89` (`test_shutdown_drains_search_lock`) — uses `create_lifespan + FastAPI(lifespan=lifespan_fn)` and runs `async with lifespan_fn(app):`. Reuse this fixture skeleton; the new test simulates a never-released lock + patches the 60.0 timeout to 0.1s. Pattern hint from RESEARCH 411:

```python
async def test_shutdown_timeout_logs_holder_identity(tmp_path, monkeypatch):
    """RES-01: when lock drain times out, log includes job_id and elapsed seconds."""
    from triggarr.search.scheduler import create_lifespan

    settings = make_settings(radarr_enabled=False, sonarr_enabled=False)
    lifespan_fn = create_lifespan(settings, tmp_path / "state.json", tmp_path / "triggarr.toml")
    app = FastAPI(lifespan=lifespan_fn)

    sink = io.StringIO()
    handler_id = logger.add(sink, format="{message}", level="WARNING")
    try:
        async with lifespan_fn(app):
            # Hold the lock and inject the holder tuple (simulating stuck cycle)
            await app.state.search_lock.acquire()
            app.state.search_lock_holder = ("radarr_Default_search", time.monotonic() - 100.0)
            # Lifespan exit triggers the drain; patch timeout to fail-fast
            # (planner: patch via monkeypatch of asyncio.wait_for OR an injected constant)
    finally:
        logger.remove(handler_id)

    output = sink.getvalue()
    assert "radarr_Default_search" in output
    assert "elapsed=" in output
```

**Planner decision:** How to make the 60.0 patchable. Options:
1. Extract `60.0` into a module-level constant (`_SHUTDOWN_DRAIN_TIMEOUT = 60.0`) and monkeypatch it.
2. Monkeypatch `asyncio.wait_for` to raise TimeoutError immediately.
3. Use `asyncio.wait_for` with a separate test-only fixture that wraps the lifespan.

RESEARCH 411 suggests option 1 ("patch the timeout to 0.1s") — preferred for clarity and one-line testability.

---

### `tests/test_clients.py` — TEST-04 aclose in-flight test

**Analog:** `tests/test_clients.py:83-97` — `_ConcreteClient + MockTransport` setup, already established.

**Existing pattern to copy** (`test_clients.py:83-97`):
```python
async def test_request_with_retry_first_attempt_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        response = await client._request_with_retry("GET", "/test")
        assert response.status_code == 200
    finally:
        await client.close()
```

**Imports already present at test_clients.py:1-18:**
```python
import io
import json
from unittest.mock import AsyncMock, patch
import httpx
import pydantic
import pytest
from loguru import logger
```

**New imports needed (planner):**
```python
import asyncio
import contextlib
```

**Patch shape (RESEARCH 287-318, 711-712):**
```python
async def test_aclose_does_not_hang_with_in_flight_requests() -> None:
    """TEST-04: ArrClient.close() completes within 2s even with pending requests.

    Proves RES-01 + TEST-04: the shutdown drain (extended to 60s in lifespan)
    is sufficient because aclose() itself does not block indefinitely on a
    pending request -- it cancels the connection pool and the awaiting task
    surfaces an httpx exception.
    """
    request_started = asyncio.Event()

    async def slow_handler(request: httpx.Request) -> httpx.Response:
        request_started.set()
        await asyncio.sleep(10)  # would block forever if not interrupted
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(slow_handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")

    pending = asyncio.create_task(client.get("/slow"))
    await request_started.wait()

    pending.cancel()
    with contextlib.suppress(asyncio.CancelledError, httpx.HTTPError):
        await pending

    # close() MUST complete within 2 seconds
    await asyncio.wait_for(client.close(), timeout=2.0)
```

**Optional sibling test (RESEARCH 323, 712):**
```python
async def test_aclose_raises_when_requests_in_flight() -> None:
    """TEST-04 (variant): aclose() raises RuntimeError if requests are not cancelled first.

    Documents the httpx behavior we depend on: aclose surfaces a RuntimeError
    rather than hanging. If httpx ever changes this, our shutdown drain logic
    needs to be revisited.
    """
    request_started = asyncio.Event()

    async def slow_handler(request: httpx.Request) -> httpx.Response:
        request_started.set()
        await asyncio.sleep(10)
        return httpx.Response(200)

    transport = httpx.MockTransport(slow_handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")

    pending = asyncio.create_task(client.get("/slow"))
    await request_started.wait()

    # Do NOT cancel; close must still return within 2s (raising or not)
    with contextlib.suppress(RuntimeError):
        await asyncio.wait_for(client.close(), timeout=2.0)

    pending.cancel()
    with contextlib.suppress(asyncio.CancelledError, httpx.HTTPError, RuntimeError):
        await pending
```

**Critical notes from RESEARCH:**
- Use `asyncio.Event()` to synchronize "request actually in flight" — sleeping a constant duration is flaky (RESEARCH 296).
- Cancel the pending task BEFORE `aclose()` per httpx #2093 recommendation (RESEARCH 311-313).
- Wrap `client.close()` in `asyncio.wait_for(..., timeout=2.0)` — long enough for normal cleanup, short enough to catch a true hang (RESEARCH Pitfall 5, lines 531-534).
- `MockTransport` accepts async handlers since httpx 0.20 (RESEARCH Assumption A2). [VERIFIED via REPL]

---

### `tests/test_config.py` — `max_consecutive_failures` default test

**Analog:** `tests/test_config.py:153-155` — `test_skip_unreleased_defaults_true` is the closest one-line default-value test.

**Existing pattern to copy** (`test_config.py:153-155`):
```python
def test_skip_unreleased_defaults_true() -> None:
    """GeneralConfig().skip_unreleased defaults to True."""
    assert GeneralConfig().skip_unreleased is True
```

**Imports already present at test_config.py:24:**
```python
from triggarr.models.config import GeneralConfig, InstanceConfig, Settings
```

**Patch shape (RESEARCH 707):**
```python
def test_general_config_default_max_consecutive_failures() -> None:
    """GeneralConfig().max_consecutive_failures defaults to 5 (SAFETY-03)."""
    assert GeneralConfig().max_consecutive_failures == 5
```

**Optional sibling test** (mirrors `test_skip_unreleased_from_toml` at test_config.py:158-166) — verify the field loads from TOML when explicitly set. Planner discretion.

## Shared Patterns

### Loguru-only logging with `{name}=value` formatters

**Source:** Used throughout `triggarr/search/scheduler.py`, `engine.py`, `clients/base.py`
**Apply to:** All new log lines in scheduler.py

```python
logger.error(
    "{app}: search cycle failed ({count}/{threshold}) -- {exc}",
    app=app_name.title(),
    count=count,
    threshold=threshold,
    exc=_sanitize_exc(exc),
)
```

Per `./CLAUDE.md`: "Loguru for logging with custom redacting sink (never print/logging module)". The `{}` placeholder + kwargs form is universal in this codebase — do NOT use f-strings inside `logger.xxx` calls (they bypass loguru's lazy formatting and the redacting sink).

### Narrow-exception discrimination tuple

**Source:** `triggarr/search/engine.py:426` (and 21 sibling sites)
**Apply to:** scheduler.py SAFETY-02 patch — reuse the EXACT tuple, do not add or remove types.

```python
except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
```

`asyncio.CancelledError` is intentionally absent — it is `BaseException`, not `Exception`, and the shutdown drain relies on it propagating to unwind the lock cleanly (RESEARCH Pitfall 7).

### `_sanitize_exc` for safe error logging

**Source:** `triggarr/search/engine.py:30-44`
**Apply to:** All failure log lines that include the exception object (scheduler.py SAFETY-03 patch + EVENT_JOB_ERROR listener)

```python
def _sanitize_exc(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.TimeoutException):
        return "request timeout"
    if isinstance(exc, httpx.HTTPError):
        return f"HTTP error: {type(exc).__name__}"
    if isinstance(exc, pydantic.ValidationError):
        return f"validation error ({exc.error_count()} issues)"
    return type(exc).__name__
```

Strips `httpx.HTTPError.request.url` (which may carry `apikey=` query parameters) — required by the SecretStr discipline in `./CLAUDE.md` and RESEARCH Security Domain (line 740).

### Per-instance `app.state` dict (precedent for `search_failures`)

**Source:** `triggarr/search/scheduler.py:221`
**Apply to:** New `app.state.search_failures: dict[str, int]` and `app.state.search_lock_holder: tuple[str, float] | None`

```python
app.state.last_search_time: dict[str, float] = {}    # existing
app.state.search_failures: dict[str, int] = {}        # NEW (SAFETY-03)
app.state.search_lock_holder: tuple[str, float] | None = None  # NEW (RES-01)
```

Lifespan-scoped (fresh-start each boot). Single-uvicorn-worker assumption (see lock comment block at scheduler.py:210-219) makes plain dict assignment safe — no asyncio.Lock around dict mutations needed because all writes happen inside the existing `search_lock`.

### Job ID derivation (stable string)

**Source:** `triggarr/web/routes.py:596, 607`; `triggarr/search/scheduler.py:240`
**Apply to:** All new lookups in `app.state.search_failures` and `app.state.search_lock_holder`

```python
job_id = f"{app_name}_{instance_name}_search"
```

Do NOT invent a new identifier scheme. The same string is APScheduler's job_id, used by `scheduler.get_job(job_id)`/`scheduler.remove_job(job_id)` in routes.py, and is deterministic from config so it survives restart-style scenarios.

### `time.monotonic()` not `time.time()` for elapsed measurement

**Source:** `triggarr/search/engine.py:304`
**Apply to:** `app.state.search_lock_holder` timestamp

```python
app.state.search_lock_holder = (job_id, time.monotonic())
...
elapsed = time.monotonic() - started
```

NTP correction can jump wall clock backward, producing negative elapsed (RESEARCH Pitfall 3).

### `safe_int(form.get(...), default, lo, hi)` form coercion

**Source:** `triggarr/web/routes.py:499-503`
**Apply to:** New `max_consecutive_failures` form field

```python
"max_consecutive_failures": safe_int(form.get("max_consecutive_failures"), 5, 1, 100),
```

Lower bound 1 (zero is pointless: would escalate immediately on first failure). Upper bound 100 (defends against typos).

### Test fixtures: `make_settings` + `_default_state`

**Source:** `tests/conftest.py:29-77` (`make_settings` factory); `triggarr/state.py:_default_state`
**Apply to:** All new scheduler tests

```python
from tests.conftest import make_settings
from triggarr.state import _default_state

app.state.settings = make_settings()
app.state.triggarr_state = _default_state(make_settings())
```

### `async def test_*` (no decorator) under `asyncio_mode = "auto"`

**Source:** `pyproject.toml:38`
**Apply to:** All new async tests in test_scheduler.py + test_clients.py

```python
async def test_something(tmp_path):
    ...
```

No `@pytest.mark.asyncio` — `asyncio_mode = "auto"` handles it.

### Loguru sink lifecycle in tests (always `try/finally remove`)

**Source:** `tests/test_scheduler.py:238-266`, `tests/test_startup.py:261-267`
**Apply to:** All new tests that capture loguru output

```python
sink_id = logger.add(sink, level="WARNING")
try:
    ...
finally:
    logger.remove(sink_id)
```

Leaking sinks across tests is a known loguru gotcha.

### `with patch(...)` context manager (no `@patch` decorators)

**Source:** `tests/test_scheduler.py:43-52`, `tests/test_config.py:674`
**Apply to:** All new tests requiring mocks

```python
with (
    patch("triggarr.search.scheduler.run_radarr_cycle",
          new=AsyncMock(side_effect=httpx.ConnectError("x"))),
    patch("triggarr.search.scheduler.save_state", new=MagicMock()),
):
    ...
```

Phase 64 PATTERNS.md confirmed this is the repo convention. Patch the import binding in the target module (`triggarr.search.scheduler.X`), not the original source.

## No Analog Found

Files/patterns with no close existing match (planner should fall back to RESEARCH.md guidance):

| Pattern | Reason | Mitigation |
|---------|--------|-----------|
| `scheduler.add_listener(EVENT_JOB_ERROR, fn)` | Triggarr has never registered an APScheduler listener (verified zero hits for `EVENT_JOB\|add_listener`). | RESEARCH §B (lines 139-153) supplies the full signature; APScheduler 3.x event code verified locally via `inspect.signature(JobExecutionEvent)`. Place near `scheduler.start()` per RESEARCH 491. |
| `httpx.MockTransport` with **async** handler + `asyncio.Event()` sync | Existing `MockTransport` usage in test_clients.py uses sync handlers only. | RESEARCH §F (lines 286-318) supplies the full test sketch; Assumption A2 (line 785) confirms async handlers are supported in installed httpx version. |
| Patching a module-level numeric constant for shutdown-timeout test | No precedent in repo — existing scheduler tests don't need to patch the timeout. | Extract `60.0` into a module-level constant `_SHUTDOWN_DRAIN_TIMEOUT` so `monkeypatch.setattr("triggarr.search.scheduler._SHUTDOWN_DRAIN_TIMEOUT", 0.1)` is one line. Surface as a planner decision. |

## Metadata

**Analog search scope:**
- `/Users/julianamacbook/triggarr/triggarr/search/` (scheduler.py, engine.py)
- `/Users/julianamacbook/triggarr/triggarr/clients/` (base.py)
- `/Users/julianamacbook/triggarr/triggarr/models/` (config.py)
- `/Users/julianamacbook/triggarr/triggarr/web/` (routes.py)
- `/Users/julianamacbook/triggarr/triggarr/templates/` (settings.html)
- `/Users/julianamacbook/triggarr/triggarr/config.py` (DEFAULT_CONFIG template)
- `/Users/julianamacbook/triggarr/tests/` (test_scheduler.py, test_clients.py, test_config.py)
- `/Users/julianamacbook/triggarr/.planning/phases/64-data-safety-config-integrity/64-PATTERNS.md` (predecessor)

**Files scanned:** 9 source + 4 tests + 1 template + 1 predecessor PATTERNS.md

**Pattern extraction date:** 2026-05-25

**Skills consulted:** None — Phase 65 is Python hardening; no `.claude/skills/` entry applies (only `aidesigner-frontend` exists locally).

**Predecessor mirrored:** Phase 64 (Data Safety & Config Integrity) introduced `max_history_rows` end-to-end (models/config.py + config.py DEFAULT_CONFIG + routes.py form-handling + tests/test_config.py) — Phase 65 follows that exact spine for `max_consecutive_failures`.
