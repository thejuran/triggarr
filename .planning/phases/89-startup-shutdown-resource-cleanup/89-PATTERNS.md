# Phase 89: Startup & Shutdown Resource Cleanup - Pattern Map

**Mapped:** 2026-11-18
**Files analyzed:** 2 (1 source, 1 test)
**Analogs found:** 2 / 2 (both are the file itself — this phase modifies existing code in place, it does not add new files)

## Plan-check corrections (2026-11-18)

These take precedence over the older sketches further down; see the matching block at the top of 89-RESEARCH.md for evidence.

- **`_safe_close` shape:** not `async with asyncio.timeout(...): await close_fn()`. aiosqlite's `Connection.close()` awaits again in its `finally:`, so a cancelled direct await may never return. Run the close in an owned task, wait with `asyncio.wait({task}, timeout=_CLEANUP_STEP_TIMEOUT)`, and cancel-once / keep-referenced / observe any task that outlives the cap. The existing shutdown drain keeps its `asyncio.timeout`. Signature: `_safe_close(context, label, close_fn)`.
- **Scheduler guard:** no `scheduler_started` flag. Read `scheduler.running`; `BaseScheduler.start()` sets `STATE_RUNNING` before its logging, start event and `wakeup()`, so `start()` can raise with the scheduler running. `AsyncIOScheduler.shutdown()` only queues the stop; yield one loop iteration and re-read the state.
- **TEST-04 rationale:** in TEST-04 `close()` returns cleanly and the `AssertionError` is on the in-flight request task (`tests/test_clients.py:190-203`). It is background for "failures near close are not httpx-typed", not proof that `close()` raises `AssertionError`. The broad catch stays (D-07).
- **D-05:** a sanitized cause line is logged first, before cleanup; the summary line is last.
- **Tests:** lifespan tests use the `_observe_lifespan` helper (drive, observe, rescue, then assert); no assertion inside a `finally:`.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|---------------|
| `triggarr/search/scheduler.py` (`create_lifespan`/`lifespan`, setup + shutdown sections; new `_safe_close` helper + `_CLEANUP_STEP_TIMEOUT` constant) | middleware/lifecycle (FastAPI/Starlette `@asynccontextmanager` lifespan — acquire-N-resources, release-on-any-exit) | event-driven (ASGI lifespan protocol) + resource-cleanup (not CRUD) | *Itself* — the file's own shutdown drain (`scheduler.py:669-755`) and `_read_shutdown_drain_timeout`/`_SHUTDOWN_DRAIN_TIMEOUT` idiom (`scheduler.py:67-113`); secondary: `_close_removed_client` in `triggarr/web/routes.py:1009-1040` (closest *other-file* analog for "close one resource, isolate its failure, keep going") | exact (same file, same idiom family) |
| `tests/test_scheduler.py` (new `test_startup_failure_*`, `test_shutdown_*_close_fails` functions) | test | request-response (in-process ASGI lifespan drive) / event-driven | *Itself* — `tests/test_scheduler.py:974-1023` (lifespan-drive pattern), `:1946-1965` (`_FakeScheduler`), `:1200-1270` (`io.StringIO` log-capture + `logger.add`/`logger.remove`), `:917-965` (failure-injection via `patch(..., side_effect=...)` + log-sink assertion) | exact |

There are no genuinely new files in this phase (CONTEXT.md/RESEARCH.md both confirm: "No new files or directories. All changes are inside `triggarr/search/scheduler.py`" plus its test file). The pattern-mapping task therefore reduces to: which parts of the *existing* file/test file are closest analogs for the *new* code being inserted into them. Both columns above resolve to the same two files, which is itself the strongest possible analog match — new code should look exactly like the surrounding code in the same module.

## Pattern Assignments

### `triggarr/search/scheduler.py` — new `_safe_close` helper + `_CLEANUP_STEP_TIMEOUT` constant (utility, resource-cleanup)

**Analog:** `_read_shutdown_drain_timeout` / `_SHUTDOWN_DRAIN_TIMEOUT` (module-constant-plus-helper pattern already in this file) and the existing shutdown drain's `asyncio.timeout()` usage.

**Module-constant placement pattern** (`triggarr/search/scheduler.py:100-113`):
```python
# RES-01 (Codex finding 3): configurable; default 60.0s; clamped >= 1.0 to
# prevent misconfig disabling drain entirely. Recommended deployment: set
# docker-compose stop_grace_period > this value (default 90s).
_SHUTDOWN_DRAIN_TIMEOUT: float = _read_shutdown_drain_timeout()

# RES-03 (D-06): tag-list cache TTL. ...
# Mirrors the _SHUTDOWN_DRAIN_TIMEOUT module-constant pattern; unlike the
# drain timeout this is NOT operator-configurable (no env-override) — the
# TTL is an internal performance knob.
_TAG_CACHE_TTL_SECONDS: float = 3600.0
```
Copy this shape for `_CLEANUP_STEP_TIMEOUT: float = 5.0` — a bare module constant with a one-line comment explaining it is a hardcoded cap, not operator-configurable (D-09 explicitly says "a module constant, not a new config setting").

**`asyncio.timeout()` idiom to reuse for the per-step cap** (`triggarr/search/scheduler.py:701-716`, the WR-01 comment block):
```python
# WR-01: use `asyncio.timeout()` (Python 3.11+) instead of
# `asyncio.wait_for(lock.acquire(), ...)`. The wait_for idiom
# has a documented footgun: if it is *cancelled* (not timed
# out), the underlying acquire() task may complete after
# wait_for has unwound, leaving the lock acquired with no
# matching release. ...
acquired = False
try:
    try:
        async with asyncio.timeout(drain):
            await app.state.search_lock.acquire()
            acquired = True
    except TimeoutError:
        ...
```
`_safe_close`'s own `async with asyncio.timeout(_CLEANUP_STEP_TIMEOUT): await close_fn()` is the same idiom applied to a single resource's close instead of a lock acquire — same reason to prefer `asyncio.timeout()` over `asyncio.wait_for()` (cancellation-race safety), already litigated once in this exact file.

**Sanitized-exception logging to reuse (zero new sanitization code)** (`triggarr/clients/base.py:17-33`, already imported into `scheduler.py` at lines 48-49 via `triggarr.search.engine`):
```python
def _sanitize_exc(exc: Exception) -> str:
    """Return a safe, type-based summary of an exception for storage. ..."""
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
The unconditional fallback `return type(exc).__name__` already produces exactly D-07's example wording `(AssertionError)` for any exception `_sanitize_exc` doesn't specifically recognize — confirmed by RESEARCH.md. Call `_sanitize_exc(exc)` inside `_safe_close`'s `except Exception as exc:` branch; never `str(exc)`.

**Recommended `_safe_close` shape** (synthesized from the two patterns above; this is new code, there is no existing function of this exact shape in the repo — it is the one genuinely new primitive this phase adds):
```python
_CLEANUP_STEP_TIMEOUT: float = 5.0  # D-09: hardcoded cap, not operator-configurable


async def _safe_close(label: str, close_fn: Callable[[], Awaitable[None]]) -> bool:
    """Attempt one cleanup step; log and continue, never raise. Returns success."""
    try:
        async with asyncio.timeout(_CLEANUP_STEP_TIMEOUT):
            await close_fn()
        return True
    except Exception as exc:
        logger.warning(
            "Cleanup: {label} did not close cleanly ({exc})",
            label=label,
            exc=_sanitize_exc(exc),
        )
        return False
```
`asyncio.TimeoutError`/`TimeoutError` is already an `Exception` subclass in 3.11+ (project's `target-version = "py311"`), so one `except Exception` branch covers both a raised close error and a timed-out close — no second `except TimeoutError` clause is structurally required (RESEARCH.md Pattern 2 note); add one only if the two cases need distinguishable wording.

---

### `triggarr/search/scheduler.py` — failed-startup cleanup (new `try/except Exception` wrapping the setup section)

**Analog:** The file's own existing shutdown `finally:` block (`scheduler.py:669-755`) — same resources (scheduler, clients, db), same ordering concern, same "every remaining step still runs" requirement (D-02/D-04) — just triggered from the *other* end of the lifespan generator.

**What is being wrapped** (`triggarr/search/scheduler.py:479-668`, current unprotected acquisition — lines approximate, re-verify against current file before editing):
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    state: TriggarrState = load_state(state_path)
    scheduler = AsyncIOScheduler()
    ...
    db = await aiosqlite.connect(db_path)                       # line 496
    await db.execute("PRAGMA journal_mode=WAL")
    ...
    await init_db(db, db_path, instance_stable_ids=instance_stable_ids)   # line 509
    ...
    await ensure_cutover_recorded(db, {...})                     # line 526 — deliberately uncaught today
    ...
    for app_type in APP_TYPES:                                  # line 534 — client construction
        ...
            clients[inst_name] = cls(base_url=cfg.url, api_key=cfg.api_key, ...)
    ...
    for app_name in APP_TYPES:                                  # line 630 — job scheduling
        for inst_name, cfg in settings.get_enabled_instances(app_name).items():
            scheduler.add_job(job_fn, "interval", ...)
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
    scheduler.start()                                            # line 652
    scheduler.add_job(update_check_job, "interval", ...)         # line 661 — runs AFTER start()
    try:
        yield
    finally:
        ...  # existing shutdown, unchanged by this pattern
```

**Existing shutdown loop this phase hardens, as the shape to mirror for the new failed-startup branch** (`triggarr/search/scheduler.py:671-755`):
```python
try:
    yield
finally:
    # 1. Stop scheduler from scheduling new jobs (does NOT wait for async jobs)
    scheduler.shutdown(wait=False)

    # 2. Drain any in-flight search cycle before closing resources (DEBT-06)
    ...
    # 3. Close HTTP clients (all instances)
    for app_type in APP_TYPES:
        for client in getattr(app.state, f"{app_type}_clients", {}).values():
            await client.close()

    # 4. Close shared database connection (all writes complete per step 2)
    await app.state.db.close()

    logger.info("Search engine stopped")
```
D-04 keeps this order unchanged; the new work is (a) guarding step 1 with a `scheduler_started` flag (Pitfall C) and (b) wrapping steps 1/3/4's individual calls in `_safe_close` instead of bare `await`. The new failed-startup branch is this same four-step shape, run from an `except Exception as startup_exc:` instead of the `finally:`, operating on plain local variables (`db`, `created_clients`, `scheduler_started`) tracked during acquisition rather than on `app.state` (RESEARCH.md Pattern 1 — `app.state.db`/`app.state.{app_type}_clients` are not populated until line ~549-553, after several steps that can themselves fail).

**Close-one-resource-isolate-its-failure precedent from another module** (`triggarr/web/routes.py:1009-1040`, `_close_removed_client`):
```python
async def _close_removed_client(client: ArrClient) -> tuple[Exception | None, asyncio.CancelledError | None]:
    """Close a removed instance's client, finishing even if the request is cancelled.
    ...
    Returns the close's own error (None only when it succeeded) and the first
    cancellation received while waiting, which the caller re-raises. ...
    """
    closing = asyncio.ensure_future(client.close())
    cancelled: asyncio.CancelledError | None = None
    while not closing.done():
        try:
            await asyncio.shield(closing)
        except asyncio.CancelledError as exc:
            if cancelled is None:
                cancelled = exc
        except Exception:
            pass  # the close's own error: read from closing below and returned
    if closing.cancelled():
        return RuntimeError("the close was cancelled before it finished"), cancelled
    error = closing.exception()
    if error is not None and not isinstance(error, Exception):
        raise error
    return error, cancelled
```
And its caller's logging (`triggarr/web/routes.py:1236-1247`):
```python
if client:
    close_error, close_cancel = await _close_removed_client(client)
    if cancelled is None:
        cancelled = close_cancel
    if close_error is not None:
        logger.error(
            "Removed {app}/{inst} but closing its connection failed: {exc_type}: {exc}",
            app=app_name,
            inst=instance_name,
            exc_type=type(close_error).__name__,
            exc=close_error,
        )
```
**Precedent note (wording shape only, not mechanism):** this is Phase 87's established *wording* precedent for "name the app, the instance, and the reason" (D-07's required shape). Match its wording style, but do **not** copy its sanitization: this call site logs `exc=close_error` (the raw exception object interpolated by loguru, not routed through `_sanitize_exc`), and `_close_removed_client` itself is considerably more elaborate than this phase needs (it exists to survive the request's own cancellation under `BaseHTTPMiddleware`, a concern the lifespan's own cleanup does not have — the lifespan is not running under a request's cancel scope). For Phase 89, `_safe_close` plus `_sanitize_exc(exc)` is the correct, simpler, D-07-compliant mechanism; `_close_removed_client` is cited only for its log-wording precedent ("naming the app, the instance and the reason").

**Scheduler-shutdown guard pattern (Pitfall C — new, no prior in-repo analog; derive from installed `apscheduler` source cited in RESEARCH.md):**
```python
# Track locally; set True only immediately after scheduler.start() returns
# without raising (mirrors Starlette's own `started` flag pattern in
# Router.lifespan).
scheduler_started = False
...
scheduler.start()
scheduler_started = True
...
# In the failed-startup except block:
if scheduler_started:
    try:
        scheduler.shutdown(wait=False)
    except Exception as exc:
        logger.warning("Cleanup: scheduler shutdown failed ({exc})", exc=_sanitize_exc(exc))
# else: scheduler was never started -- LIFE-03 already holds trivially.
```
Note `scheduler.shutdown()` is synchronous (no `async def`, no `await` inside, per installed `apscheduler` source) — call it directly, not through the `asyncio.timeout`-wrapped `_safe_close` (RESEARCH.md Pattern 3 flags this explicitly: wrapping a non-yielding sync call in `asyncio.timeout` cannot actually time it out).

**D-05 summary line placement** (new; no direct prior analog — closest shape is the existing `logger.info("Search engine stopped")` one-liner at the end of shutdown, `scheduler.py:755`):
```python
logger.error(
    "Startup failed; closed the database and {count} connection(s) before exiting",
    count=closed_count,
)
raise startup_exc  # D-03: original error, unchanged, unreplaced
```

---

### `tests/test_scheduler.py` — new failed-startup and shutdown-close-failure tests

**Analog:** `tests/test_scheduler.py` itself — the existing lifespan-drive pattern, `_FakeScheduler` double, and `io.StringIO` log-capture pattern already used for structurally identical assertions in this same file.

**Imports already present and reusable** (`tests/test_scheduler.py:1-42`):
```python
from __future__ import annotations

import asyncio
import importlib
import io
import re
import shutil
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import httpx
import pytest
from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from loguru import logger
from pydantic import SecretStr

from tests.conftest import make_settings
from triggarr.clients.radarr import RadarrClient
from triggarr.db import init_db, insert_search_entry
from triggarr.models.arr import Tag
from triggarr.models.config import GeneralConfig, InstanceConfig, Settings
from triggarr.search.scheduler import (
    _TAG_CACHE_TTL_SECONDS,
    _evaluate_cycle_outcome,
    _run_one_cycle,
    make_search_job,
)
from triggarr.state import _default_instance_state, _default_state, save_state
from triggarr.web.routes import STATIC_DIR, router
```
Add `_safe_close`, `_CLEANUP_STEP_TIMEOUT` (or whatever names the planner picks) to the `from triggarr.search.scheduler import (...)` block if a test imports them directly (e.g. to assert the constant's value, mirroring `test_shutdown_timeout_default_is_60s` at line 1038-1043).

**Core lifespan-drive pattern to copy** (`tests/test_scheduler.py:974-1000`, `:1980-1991`):
```python
with patch("triggarr.search.scheduler.AsyncIOScheduler", return_value=_FakeScheduler()):
    lifespan_fn = create_lifespan(settings, state_path, config_path)
    app = FastAPI(lifespan=lifespan_fn)
    async with lifespan_fn(app):
        db = app.state.db
        ...
```
For the new failed-startup tests, this becomes `with pytest.raises(SomeError): async with lifespan_fn(app): pass` — but per RESEARCH.md Pitfall A, `pytest.raises(...)` alone is insufficient; it must be paired with positive post-failure assertions (below).

**`_FakeScheduler` double to reuse / extend** (`tests/test_scheduler.py:1946-1965`):
```python
class _FakeScheduler:
    """Scheduler stand-in that records calls without scheduling real jobs."""

    def __init__(self) -> None:
        self.started = False
        self.shutdown_wait: bool | None = None
        self.jobs: list[tuple[tuple, dict]] = []
        self.listeners: list[tuple[tuple, dict]] = []

    def add_job(self, *args, **kwargs) -> None:
        self.jobs.append((args, kwargs))

    def add_listener(self, *args, **kwargs) -> None:
        self.listeners.append((args, kwargs))

    def start(self) -> None:
        self.started = True

    def shutdown(self, wait: bool = True) -> None:
        self.shutdown_wait = wait
```
This double currently cannot simulate `scheduler.start()` raising (D-11/LIFE-03's "scheduler_started stays False" test stage) or `scheduler.shutdown()` raising (Pitfall C's defensive catch). RESEARCH.md Open Question 2 recommends extending this exact double (e.g. a `start_side_effect: Exception | None = None` constructor arg, or a one-off local subclass in the new test) rather than attempting to trigger a genuine internal APScheduler failure — follow that recommendation; it is the project's existing convention for scheduler-level lifespan tests.

**Failure-injection + log-sink assertion pattern to copy** (`tests/test_scheduler.py:944-964`, persistence-failure test — same shape as the new D-05/D-06/D-07 log-wording assertions need):
```python
sink = io.StringIO()
sink_id = logger.add(sink, format="{level} | {message}", level="ERROR")
try:
    with (
        patch("triggarr.clients.base.asyncio.sleep", new=AsyncMock()),
        patch(
            "triggarr.search.scheduler.save_state",
            new=MagicMock(side_effect=OSError(28, "No space left on device")),
        ),
        pytest.raises(OSError, match="No space left"),
    ):
        await job()
finally:
    logger.remove(sink_id)

output = sink.getvalue()
assert any(
    line.startswith("ERROR | ")
    and ("persistence" in line.lower() or "save_state" in line.lower() or "durability" in line.lower())
    for line in output.splitlines()
), f"Expected ERROR-level persistence log line, got: {output!r}"
```
For the new tests: patch `triggarr.search.scheduler.init_db` (or `ensure_cutover_recorded`, or a client class, or `scheduler.start` via `_FakeScheduler`) with `new=AsyncMock(side_effect=SomeError(...))`, wrap the `async with lifespan_fn(app): ...` block in `pytest.raises(SomeError)`, and assert both the warning-level cleanup lines (D-06/D-07 wording) and the error-level summary line (D-05) via the same `io.StringIO`/`logger.add` sink.

**Thread-liveness assertion (D-12 — the one genuinely new assertion shape, no direct prior analog in this file; derive from RESEARCH.md's verified `aiosqlite` source read):**
```python
# After the failed-startup `async with lifespan_fn(app): ...` block exits:
assert db is not None  # captured from a reference held before/at failure, or
                        # exposed by the test via a patched aiosqlite.connect wrapper
conn_thread = db._thread  # aiosqlite.Connection's internal worker Thread
conn_thread.join(timeout=2.0)
assert not conn_thread.is_alive(), "aiosqlite worker thread did not stop after failed-startup cleanup"
```
Capturing the real `aiosqlite.Connection` instance for this assertion requires either (a) wrapping `aiosqlite.connect` to stash the connection in a test-local variable before the failure is injected later in setup, or (b) injecting the failure late enough (e.g. `ensure_cutover_recorded`, client construction, `scheduler.start()`) that `db` is already assigned to the local variable the new cleanup code tracks — the planner should pick the injection point per stage and capture `db` via a thin `patch("triggarr.search.scheduler.aiosqlite.connect", wraps=aiosqlite.connect)`-style spy if the earliest stage (`init_db` itself raising) needs this assertion too.

**TEST-04 background for "failures around an in-flight close are not httpx-typed"** (`tests/test_clients.py:203`, `:330-387` — already in the repo, cited by D-07/Pitfall B). CORRECTED: the `AssertionError` below is raised on the in-flight request task; `close()` itself returns cleanly (`tests/test_clients.py:190-203`). TEST-04 does not show `close()` raising:
```python
# tests/test_clients.py:203
_HTTPX_INFLIGHT_NO_CANCEL_EXC: type[BaseException] = AssertionError
```
```python
# tests/test_clients.py:384-387
assert isinstance(result[0], _HTTPX_INFLIGHT_NO_CANCEL_EXC), (
    f"Expected in-flight task to raise {_HTTPX_INFLIGHT_NO_CANCEL_EXC.__name__} "
    ...
    "If this is an intentional httpx change, update _HTTPX_INFLIGHT_NO_CANCEL_EXC."
)
```
The new D-11 shutdown test ("A shutdown test makes one client's close raise") should mock a client's `.close()` to raise `AssertionError` directly (`AsyncMock(side_effect=AssertionError("boom"))`) as a synthetic failure — this pins the "broad `Exception`, not `httpx.HTTPError`" contract (D-07, Pitfall B) at the `_safe_close` level, cheaply. It proves the breadth of the catch and that later steps continue; it does not reproduce TEST-04, where `close()` does not raise.

**`make_settings`/`default_state` factories to reuse unchanged** (`tests/conftest.py:39-99`):
```python
def make_settings(
    radarr_url: str = "http://radarr:7878",
    radarr_enabled: bool = True,
    ...
    general: GeneralConfig | None = None,
) -> Settings:
    """Build a Settings instance with sensible test defaults. ..."""
    return Settings(
        general=general or GeneralConfig(),
        radarr={"Default": InstanceConfig(...)},
        sonarr={"Default": InstanceConfig(...)},
        lidarr={"Default": InstanceConfig(...)},
    )
```
For the "closes every client built before the Nth instance's construction fails" test stage, construct `Settings` directly with multiple named instances in the dict (e.g. `sonarr={"First": InstanceConfig(...), "Second": InstanceConfig(...)}`) the same way `test_lifespan_associates_existing_rows_on_upgrade` (`tests/test_scheduler.py:2086-2093`) and `test_lifespan_records_attribution_cutover_once` build multi-field `Settings(...)` literals directly rather than through `make_settings` — `make_settings` only supports one "Default" instance per app type, so a multi-instance stage needs the direct-literal form.

---

## Shared Patterns

### Exception sanitization (apply to every new log line in `_safe_close` and the D-05/D-06/D-07 lines)
**Source:** `triggarr/clients/base.py:17-33` (`_sanitize_exc`), already imported into `scheduler.py` at lines 48-49.
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
**Apply to:** `_safe_close`'s `except Exception` branch; the D-05 summary line never needs this (it has no exception, just a count); the D-06/D-07 per-step warning lines always route their `exc` through this, never `str(exc)` or an f-string embedding the raw exception.

### Bounded wait via `asyncio.timeout()`, never `asyncio.wait_for()`
**CORRECTED:** applies to the existing shutdown drain only. `_safe_close` bounds its wait with `asyncio.wait({task}, timeout=...)` on an owned task (see Plan-check corrections); `asyncio.wait` never cancels on timeout, so it is not the `wait_for` idiom WR-01 rejected.
**Source:** `triggarr/search/scheduler.py:701-716` (WR-01 comment + the existing shutdown-drain's `async with asyncio.timeout(drain): ...`).
**Apply to:** `_safe_close`'s per-step cap. Already litigated once in this file (the drain); the new cap is the same idiom, same rationale (cancellation-safety), different call site.

### Loguru brace-style keyword log arguments, never `print`/stdlib `logging`, never f-string-embedded secrets
**Source:** throughout `scheduler.py`, e.g. lines 690-700, 726-738, 755.
**Apply to:** every new log line this phase adds (`_safe_close`'s warning, the D-05 summary error line, Pitfall C's scheduler-shutdown-failure warning).
```python
logger.warning(
    "Cleanup: {label} did not close cleanly ({exc})",
    label=label,
    exc=_sanitize_exc(exc),
)
```

### "Track resources as plain locals, not on `app.state`, until acquisition succeeds"
**Source:** Starlette's own `started` flag pattern (`Router.lifespan`, confirmed in RESEARCH.md from installed source) — no in-repo analog exists yet because `scheduler.py`'s current code has no failure path to track resources for; this is the one genuinely new structural idea this phase introduces, and RESEARCH.md Pattern 1 is the canonical description.
**Apply to:** `db`, `created_clients` (a flat list, not the per-app-type dict used on `app.state`), and `scheduler_started` — all three must be assigned/updated immediately after each successful acquisition step, inside the `try:` block, so the `except Exception as startup_exc:` branch can read them regardless of which step failed.

## No Analog Found

None. This phase touches exactly one source file and one test file, both already read in full; every new piece of logic (`_safe_close`, the failed-startup `except` branch, the `scheduler_started` guard, the thread-liveness test assertion) is either a direct reuse of an existing in-file/in-repo pattern or — where RESEARCH.md itself identifies it as genuinely new (the plain-locals tracking shape, the thread-liveness check) — is specified above with its derivation cited rather than left unsourced.

## Conventions

Derived repo-wide via the shared deterministic module (`gsd-tools.cjs verify conventions --derive`), not scoped to `triggarr/search/` — that subtree alone (4 Python files) returned `insufficient-data` on every axis, so the table below is the repo-wide baseline. Triggarr is a pure-Python codebase; the `export-style`/`import-style` axes are JS/TS-oriented and found zero applicable files here.

| Axis | Dominant | Share | Entropy | Status |
|------|----------|-------|---------|--------|
| File-name casing | camel* | 77.4% | 0.609 | named contract |
| Identifier casing | — (no single form reaches majority) | 43.4% | 0.783 | contested hotspot |
| Export style | n/a | — | — | insufficient-data (no JS/TS export syntax in this repo) |
| Import style | n/a | — | — | insufficient-data (no JS/TS import syntax in this repo) |

*The generic casing axes are tuned for JS/TS-style tokenization and classify some Python `snake_case` names/files into its "camel"/"other" buckets rather than a dedicated "snake" bucket in every case; treat "camel" here as this tool's label for the repo's actual dominant convention (which, read directly from the files in this phase's scope, is `snake_case` for both Python filenames and identifiers — `scheduler.py`, `_safe_close`, `_CLEANUP_STEP_TIMEOUT`, `_sanitize_exc`). Follow the files read directly in this report (snake_case functions/variables, `CONSTANT_CASE` module constants, `PascalCase` classes) over the raw tool label where they disagree — this is exactly the project's existing style already shown in every excerpt above.

**Contested hotspots (author's choice):** This tool's prototype example of an intentional, repo-wide-contested-but-locally-consistent split is the GSD plugin's own CJS<->SDK dual resolver (`bin/lib/**` is CJS `module.exports`/`require`; `sdk/src/**` is ESM `export`/`import`): each half is internally consistent per-directory, contested only when compared repo-wide. Triggarr has no analogous dual-module-system split (it is pure Python throughout), so this phase has no comparable "author's choice, match the local directory" axis to call out beyond the identifier-casing table row above — within `scheduler.py` itself, naming is already 100% consistent (snake_case functions/locals, `CONSTANT_CASE` module constants, `PascalCase` classes), so the new `_safe_close`/`_CLEANUP_STEP_TIMEOUT` code has one unambiguous local convention to match regardless of the repo-wide contested share.

## Metadata

**Analog search scope:** `triggarr/search/scheduler.py` (full file), `triggarr/clients/base.py` (full file), `triggarr/web/routes.py` (lines 1000-1254), `tests/test_scheduler.py` (lines 1-120, 917-1046, 1940-2120), `tests/test_clients.py` (lines 160-390), `tests/conftest.py` (full file)
**Files scanned:** 6
**Pattern extraction date:** 2026-11-18
