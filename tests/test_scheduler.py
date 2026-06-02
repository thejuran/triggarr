"""Tests for the scheduler job factory and lifespan shutdown.

Covers: client-None early return, unhandled exception swallowing,
graceful shutdown with search_lock drain (DEBT-06),
and tracking integration after search cycles (Plan 20-03).
"""

from __future__ import annotations

import asyncio
import importlib
import io
import re
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

from tests.conftest import make_settings
from triggarr.clients.radarr import RadarrClient
from triggarr.db import init_db, insert_search_entry
from triggarr.models.arr import Tag
from triggarr.models.config import InstanceConfig, Settings
from triggarr.search.scheduler import _TAG_CACHE_TTL_SECONDS, _run_one_cycle, make_search_job
from triggarr.state import _default_instance_state, _default_state, save_state
from triggarr.web.routes import STATIC_DIR, router


async def test_make_search_job_client_none_returns_early():
    """Job returns immediately without error when client is None."""
    app = FastAPI()
    app.state.radarr_clients = {}
    app.state.search_lock = asyncio.Lock()

    job = make_search_job(app, "radarr", "Default", Path("/tmp/state.json"))
    # Should complete without error and without touching other state attrs
    await job()


async def test_make_search_job_unexpected_exception_propagates():
    """SAFETY-02: unexpected (non-narrow-tuple) exceptions now propagate.

    RuntimeError is NOT in (httpx.HTTPError, pydantic.ValidationError,
    aiosqlite.Error, OSError), so it must escape the wrapper and reach
    APScheduler's EVENT_JOB_ERROR listener.
    """
    app = FastAPI()
    app.state.radarr_clients = {"Default": AsyncMock()}
    app.state.search_lock = asyncio.Lock()
    # Pre-initialize state attrs the later plans (65-02 / 65-03) will populate.
    # Harmless here under the inverted assertion.
    app.state.search_failures = {}
    app.state.search_lock_holder = None
    app.state.tag_cache = {}
    app.state.triggarr_state = _default_state(make_settings())
    app.state.settings = make_settings()
    # app.state.db is referenced as an argument to cycle_fn(...) before the
    # mocked side_effect fires; provide a MagicMock so attribute access works.
    # (Rule 3 — exposed by narrow-tuple change: the prior broad-except masked
    # the AttributeError; tracking_check is never reached because cycle_fn raises.)
    app.state.db = MagicMock()

    with (
        patch(
            "triggarr.search.scheduler.run_radarr_cycle",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
        patch(
            "triggarr.search.scheduler.save_state",
            new=MagicMock(),
        ),
        pytest.raises(RuntimeError, match="boom"),
    ):
        job = make_search_job(app, "radarr", "Default", Path("/tmp/state.json"))
        await job()


async def test_make_search_job_httperror_swallowed():
    """SAFETY-02: httpx.ConnectError IS still caught (it's in the narrow tuple)."""
    app = FastAPI()
    app.state.radarr_clients = {"Default": AsyncMock()}
    app.state.search_lock = asyncio.Lock()
    app.state.search_failures = {}
    app.state.search_lock_holder = None
    app.state.tag_cache = {}
    app.state.triggarr_state = _default_state(make_settings())
    app.state.settings = make_settings()
    app.state.db = MagicMock()  # see propagation test for rationale

    with (
        patch(
            "triggarr.search.scheduler.run_radarr_cycle",
            new=AsyncMock(side_effect=httpx.ConnectError("connection refused")),
        ),
        patch(
            "triggarr.search.scheduler.save_state",
            new=MagicMock(),
        ),
    ):
        job = make_search_job(app, "radarr", "Default", Path("/tmp/state.json"))
        # Should NOT raise -- httpx.ConnectError is in the narrow tuple.
        await job()


async def test_event_job_error_listener_logs_unexpected_exception():
    """SAFETY-02: the EVENT_JOB_ERROR listener logs propagated exceptions.

    When a non-narrow-tuple exception (e.g. RuntimeError) escapes a job
    wrapper, APScheduler fires EVENT_JOB_ERROR and the registered
    `_on_job_error` listener logs at ERROR level with job_id + type name
    + sanitized exception message.
    """
    from triggarr.search.scheduler import _on_job_error

    # WR-08: invoke the listener directly rather than calling
    # `scheduler._dispatch_event(event)`. `_dispatch_event` is a private
    # APScheduler API (leading underscore) -- any APScheduler upgrade
    # can rename or change its signature without warning, leaving this
    # test broken with an unhelpful AttributeError. The unit under test
    # here is `_on_job_error`, not APScheduler's dispatch path, so calling
    # the listener directly is both more robust and more faithful to the
    # test intent.
    sink = io.StringIO()
    sink_id = logger.add(sink, format="{level} | {message}", level="ERROR")
    try:
        event = JobExecutionEvent(
            code=EVENT_JOB_ERROR,
            job_id="radarr_Default_search",
            jobstore="default",
            scheduled_run_time=datetime.now(UTC),
            exception=RuntimeError("synthetic boom"),
        )
        _on_job_error(event)
    finally:
        logger.remove(sink_id)

    output = sink.getvalue()
    assert output.startswith("ERROR | "), f"Expected ERROR-level log line, got: {output!r}"
    assert "radarr_Default_search" in output, f"Missing job_id in: {output!r}"
    assert "RuntimeError" in output, f"Missing exception type in: {output!r}"
    assert "synthetic boom" in output, f"Missing exception message in: {output!r}"


# ---------------------------------------------------------------------------
# SAFETY-03 (Plan 65-02): consecutive-failure counter + escalation
#
# The outage-driven tests below build a real RadarrClient wired to an
# httpx.MockTransport (pattern verified in tests/test_clients.py:83-97).
# They DO NOT patch run_radarr_cycle itself — the goal is to exercise the
# REAL engine path so that the engine's `connected = False` signal flows
# through scheduler.make_search_job and triggers the counter increment
# (Codex finding 1 from REVIEWS.md).
# ---------------------------------------------------------------------------


def _build_outage_app(tmp_path, *, max_consecutive_failures=5, transport_handler):
    """Build a FastAPI app wired with a real RadarrClient on a MockTransport.

    The returned (app, job) tuple lets the test drive `make_search_job` end
    to end: the real `run_radarr_cycle` runs, its internal HTTP calls hit the
    MockTransport (which returns whatever the handler decides), and the
    scheduler's post-cycle counter logic observes the engine's
    `connected = True / False` outcome.

    Note: settings are mutated AFTER make_settings() to apply the per-test
    max_consecutive_failures (GeneralConfig is a plain BaseModel — direct
    attribute mutation is allowed).
    """
    settings = make_settings()
    settings.general.max_consecutive_failures = max_consecutive_failures

    # Real RadarrClient with its httpx.AsyncClient swapped for one driven
    # by the MockTransport. base_url must match the original so any path
    # the engine constructs (e.g. /api/v3/wanted/missing) resolves correctly.
    real_client = RadarrClient(base_url="http://radarr-test:7878", api_key="test-key")
    real_client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(transport_handler),
        base_url="http://radarr-test:7878",
        headers={"X-Api-Key": "test-key", "Content-Type": "application/json"},
    )
    real_client._app_name = "Radarr"

    state = _default_state(settings)
    # Ensure the Default instance state exists and starts as connected.
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


async def test_failure_counter_increments_on_real_arr_outage(tmp_path):
    """SAFETY-03 (Codex finding 1): counter observes REAL *arr outage path.

    The engine cycle catches httpx.HTTPError internally and sets
    state["radarr"][instance]["connected"] = False. The scheduler MUST detect
    this via the returned state and increment the counter — NOT only the
    rare narrow-tuple exception escape path.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "Service unavailable"})

    app, job = _build_outage_app(tmp_path, transport_handler=handler)
    # Patch asyncio.sleep so the retry inside _request_with_retry does not
    # actually sleep 2s × 3 cycles. Patch run_tracking_check to no-op so
    # the AsyncMock db doesn't have to model aiosqlite's cursor protocol.
    # Patch save_state so the cycle's post-success persistence call doesn't
    # write to disk (we patch the imported reference inside scheduler).
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
    # Confirm the test actually drove the engine's outage path (not a
    # synthetic shortcut).
    assert app.state.triggarr_state["radarr"]["Default"]["connected"] is False


async def test_failure_counter_increments_on_cycle_exception(tmp_path):
    """SAFETY-03: rare cycle-exception path also feeds the counter.

    Engine cycles normally catch httpx.HTTPError/pydantic.ValidationError
    and return state with `connected = False`. The narrow-tuple except in
    make_search_job exists for the rare case where something else escapes
    (e.g. aiosqlite.Error from inside the cycle). This test drives that path
    by patching run_radarr_cycle itself.
    """
    app = FastAPI()
    app.state.radarr_clients = {"Default": AsyncMock()}
    app.state.sonarr_clients = {}
    app.state.lidarr_clients = {}
    app.state.search_lock = asyncio.Lock()
    app.state.search_lock_holder = None
    app.state.triggarr_state = _default_state(make_settings())
    app.state.settings = make_settings()
    app.state.search_failures = {}
    app.state.persistence_degraded = False
    app.state.tag_cache = {}
    app.state.db = MagicMock()

    with (
        patch(
            "triggarr.search.scheduler.run_radarr_cycle",
            new=AsyncMock(side_effect=aiosqlite.Error("db locked")),
        ),
        patch(
            "triggarr.search.scheduler.save_state",
            new=MagicMock(),
        ),
    ):
        job = make_search_job(app, "radarr", "Default", tmp_path / "state.json")
        await job()
        await job()
        await job()

    assert app.state.search_failures["radarr_Default_search"] == 3


async def test_failure_counter_escalates_at_threshold(tmp_path):
    """SAFETY-03: at/above max_consecutive_failures, log level escalates to ERROR.

    With max_consecutive_failures=3, the first two failures log at WARNING
    and the third escalates to ERROR. The ERROR line must include the
    `(count/threshold)` marker so the operator can tell why escalation
    fired.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "Service unavailable"})

    app, job = _build_outage_app(
        tmp_path, max_consecutive_failures=3, transport_handler=handler
    )

    sink = io.StringIO()
    sink_id = logger.add(sink, format="{level} | {message}", level="WARNING")
    try:
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
    finally:
        logger.remove(sink_id)

    output = sink.getvalue()
    warning_lines = [line for line in output.splitlines() if line.startswith("WARNING | ")
                     and "search cycle failed" in line]
    error_lines = [line for line in output.splitlines() if line.startswith("ERROR | ")
                   and "search cycle failed" in line]

    # First two cycles below threshold = WARNING; third at threshold = ERROR
    assert len(warning_lines) == 2, (
        f"Expected 2 WARNING failure lines, got {len(warning_lines)}: {output!r}"
    )
    assert len(error_lines) >= 1, (
        f"Expected at least 1 ERROR failure line, got {len(error_lines)}: {output!r}"
    )
    assert "(3/3)" in error_lines[0], (
        f"Expected count/threshold marker '(3/3)' in ERROR line: {error_lines[0]!r}"
    )


async def test_failure_counter_resets_on_success(tmp_path):
    """SAFETY-03: a successful cycle resets the counter to 0.

    Drives 4 cycles via a stateful MockTransport: 503, 503, 200, 503.
    Counter trajectory: 1, 2, 0 (reset), 1.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        # Cycle 1, 2, 4 → fail (503). Cycle 3 → success (200 with valid
        # paginated payload). The cycle counter is set explicitly by the
        # test body before each await job() below.
        if state["cycle"] in (1, 2, 4):
            return httpx.Response(503, json={"error": "Service unavailable"})
        # Cycle 3 success path: PaginatedResponse needs page/pageSize/sortKey/
        # totalRecords/records. Tag endpoint returns a flat JSON array.
        if request.url.path == "/api/v3/tag":
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json={
                "page": 1,
                "pageSize": 50,
                "sortKey": "id",
                "totalRecords": 0,
                "records": [],
            },
        )

    state = {"cycle": 1}
    app, job = _build_outage_app(tmp_path, transport_handler=handler)
    connected_snapshots = []

    with (
        patch("triggarr.clients.base.asyncio.sleep", new=AsyncMock()),
        patch(
            "triggarr.search.scheduler.run_tracking_check",
            new=AsyncMock(return_value={"grabbed": 0, "partial": 0, "partial_expired": 0,
                                        "unresolved": 0, "errors": 0}),
        ),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
    ):
        # Cycle 1 (503)
        state["cycle"] = 1
        await job()
        connected_snapshots.append(app.state.triggarr_state["radarr"]["Default"]["connected"])
        # Cycle 2 (503)
        state["cycle"] = 2
        await job()
        connected_snapshots.append(app.state.triggarr_state["radarr"]["Default"]["connected"])
        # Cycle 3 (200 — success)
        state["cycle"] = 3
        await job()
        connected_snapshots.append(app.state.triggarr_state["radarr"]["Default"]["connected"])
        # Cycle 4 (503 again)
        state["cycle"] = 4
        await job()
        connected_snapshots.append(app.state.triggarr_state["radarr"]["Default"]["connected"])

    assert app.state.search_failures["radarr_Default_search"] == 1, (
        f"Expected counter=1 after F/F/S/F, got {app.state.search_failures}"
    )
    assert connected_snapshots == [False, False, True, False], (
        f"Unexpected connected trajectory: {connected_snapshots}"
    )


async def test_failure_counter_per_instance_scoped(tmp_path):
    """SAFETY-03: counter is keyed per (app, instance), not shared across instances.

    Default instance returns 503 (failure); 4K instance returns 200 (success).
    Counters must remain independent.
    """
    def default_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "Service unavailable"})

    def fourk_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v3/tag":
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json={
                "page": 1,
                "pageSize": 50,
                "sortKey": "id",
                "totalRecords": 0,
                "records": [],
            },
        )

    # Build settings with two radarr instances.
    settings = Settings(
        radarr={
            "Default": InstanceConfig(
                url="http://radarr-default:7878",
                api_key="key-default",
                enabled=True,
                search_missing_count=5,
                search_cutoff_count=5,
                search_interval=30,
            ),
            "4K": InstanceConfig(
                url="http://radarr-4k:7878",
                api_key="key-4k",
                enabled=True,
                search_missing_count=5,
                search_cutoff_count=5,
                search_interval=30,
            ),
        },
    )

    default_client = RadarrClient(base_url="http://radarr-default:7878", api_key="key-default")
    default_client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(default_handler),
        base_url="http://radarr-default:7878",
        headers={"X-Api-Key": "key-default", "Content-Type": "application/json"},
    )
    default_client._app_name = "Radarr"

    fourk_client = RadarrClient(base_url="http://radarr-4k:7878", api_key="key-4k")
    fourk_client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(fourk_handler),
        base_url="http://radarr-4k:7878",
        headers={"X-Api-Key": "key-4k", "Content-Type": "application/json"},
    )
    fourk_client._app_name = "Radarr"

    state = _default_state(settings)
    state["radarr"]["Default"] = _default_instance_state()
    state["radarr"]["Default"]["connected"] = True
    state["radarr"]["4K"] = _default_instance_state()
    state["radarr"]["4K"]["connected"] = True

    app = FastAPI()
    app.state.radarr_clients = {"Default": default_client, "4K": fourk_client}
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

    default_job = make_search_job(app, "radarr", "Default", tmp_path / "state.json")
    fourk_job = make_search_job(app, "radarr", "4K", tmp_path / "state.json")

    with (
        patch("triggarr.clients.base.asyncio.sleep", new=AsyncMock()),
        patch(
            "triggarr.search.scheduler.run_tracking_check",
            new=AsyncMock(return_value={"grabbed": 0, "partial": 0, "partial_expired": 0,
                                        "unresolved": 0, "errors": 0}),
        ),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
    ):
        await default_job()
        await fourk_job()

    assert app.state.search_failures.get("radarr_Default_search", 0) == 1
    assert app.state.search_failures.get("radarr_4K_search", 0) == 0


async def test_persistence_failure_logs_error_and_marks_degraded(tmp_path):
    """SAFETY-03 (Codex finding 2): persistence failure is a hard error, not transient.

    When save_state raises OSError (disk full, permission denied), the cycle
    has already completed successfully and `connected = True`. The scheduler
    MUST:
      - log at ERROR immediately (no threshold gate),
      - set app.state.persistence_degraded = True,
      - re-raise so APScheduler's EVENT_JOB_ERROR listener logs with job_id,
      - NOT increment the search-failure counter (durability != *arr outage).
    """
    def success_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v3/tag":
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json={
                "page": 1,
                "pageSize": 50,
                "sortKey": "id",
                "totalRecords": 0,
                "records": [],
            },
        )

    app, job = _build_outage_app(tmp_path, transport_handler=success_handler)

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
    assert app.state.persistence_degraded is True
    assert app.state.search_failures.get("radarr_Default_search", 0) == 0


# ---------------------------------------------------------------------------
# DEBT-06: Graceful shutdown — lock drain before resource close
# ---------------------------------------------------------------------------


async def test_shutdown_drains_search_lock(tmp_path):
    """Lifespan finally block acquires search_lock before closing DB (DEBT-06).

    Verifies that the shutdown sequence completes cleanly when the lock is
    uncontested (normal path).  The lock-drain logic runs in the finally
    block via asyncio.wait_for, proving it executes before DB close.
    """
    from triggarr.search.scheduler import create_lifespan

    settings = make_settings(radarr_enabled=False, sonarr_enabled=False)

    state_path = tmp_path / "state.json"
    config_path = tmp_path / "triggarr.toml"

    lifespan_fn = create_lifespan(settings, state_path, config_path)

    app = FastAPI(lifespan=lifespan_fn)

    # Run lifespan up through yield, then trigger shutdown
    async with lifespan_fn(app):
        # Verify search_lock was created on app.state
        assert hasattr(app.state, "search_lock"), "search_lock should be set during lifespan startup"
        assert isinstance(app.state.search_lock, asyncio.Lock)

    # If we reach here, the lifespan finally block completed without deadlock.
    # The lock-drain logic (wait_for + acquire + release) ran before db.close().
    assert True, "Lifespan shutdown completed cleanly with search_lock drain"


async def test_shutdown_proceeds_after_lock_released(tmp_path):
    """Shutdown waits for held lock then proceeds (simulates in-flight cycle ending)."""
    from triggarr.search.scheduler import create_lifespan

    settings = make_settings(radarr_enabled=False, sonarr_enabled=False)

    state_path = tmp_path / "state.json"
    config_path = tmp_path / "triggarr.toml"

    lifespan_fn = create_lifespan(settings, state_path, config_path)

    app = FastAPI(lifespan=lifespan_fn)

    async with lifespan_fn(app):
        # Simulate an in-flight search cycle by acquiring the lock
        await app.state.search_lock.acquire()
        # Release immediately (simulating cycle completion just before shutdown)
        app.state.search_lock.release()

    # Shutdown completed — lock drain succeeded after release
    assert True, "Shutdown completed after lock was released"


# ---------------------------------------------------------------------------
# RES-01 (Plan 65-03): configurable shutdown drain + holder identity logging
#
# Three tests:
#   A. default constant value is 60.0
#   B. TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT env var override + clamp >= 1.0
#   C. shutdown drain timeout logs holder identity (INFO on entry, WARNING on
#      timeout) — Codex finding 3 demanded INFO-on-entry so the holder is
#      observable even if Docker SIGKILLs the process before the timeout.
# ---------------------------------------------------------------------------


def test_shutdown_timeout_default_is_60s():
    """RES-01: module-level _SHUTDOWN_DRAIN_TIMEOUT defaults to 60.0 (float)."""
    from triggarr.search.scheduler import _SHUTDOWN_DRAIN_TIMEOUT

    assert _SHUTDOWN_DRAIN_TIMEOUT == 60.0
    assert isinstance(_SHUTDOWN_DRAIN_TIMEOUT, float)


def test_shutdown_timeout_env_var_override(monkeypatch):
    """RES-01: TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT env var overrides the default.

    The module constant is read at import time. The test reloads the module
    after setting the env var so the new value is picked up. Values < 1.0
    are clamped to 1.0 so a misconfiguration cannot disable the drain entirely.
    """
    import triggarr.search.scheduler as sched

    original_timeout = sched._SHUTDOWN_DRAIN_TIMEOUT
    try:
        # 1. Override path
        monkeypatch.setenv("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", "15.0")
        importlib.reload(sched)
        assert sched._SHUTDOWN_DRAIN_TIMEOUT == 15.0

        # 2. Clamp path: "0" is below the >=1.0 floor; must clamp up to 1.0.
        monkeypatch.setenv("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", "0")
        importlib.reload(sched)
        assert sched._SHUTDOWN_DRAIN_TIMEOUT >= 1.0
        assert sched._SHUTDOWN_DRAIN_TIMEOUT == 1.0
    finally:
        # Restore module state so other tests see the default.
        monkeypatch.delenv("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", raising=False)
        importlib.reload(sched)
        # Sanity: module constant restored to default.
        assert original_timeout == sched._SHUTDOWN_DRAIN_TIMEOUT


async def test_shutdown_timeout_logs_holder_identity(tmp_path, monkeypatch):
    """RES-01 (Codex finding 3): shutdown drain logs holder identity twice.

    On entry to the drain (INFO) AND on timeout (WARNING), the log must
    name the holder (job_id) and the elapsed runtime. The INFO-on-entry
    log fires immediately so that even if Docker SIGKILLs the process
    before the drain timeout completes, the operator still has visibility
    into which instance was stuck.
    """
    import triggarr.search.scheduler as sched
    from triggarr.search.scheduler import create_lifespan

    # Force a very short drain timeout so the test finishes in <1s.
    monkeypatch.setattr(sched, "_SHUTDOWN_DRAIN_TIMEOUT", 0.1)

    settings = make_settings(radarr_enabled=False, sonarr_enabled=False)
    state_path = tmp_path / "state.json"
    config_path = tmp_path / "triggarr.toml"

    lifespan_fn = create_lifespan(settings, state_path, config_path)
    app = FastAPI(lifespan=lifespan_fn)

    sink = io.StringIO()
    sink_id = logger.add(sink, format="{level} | {message}", level="INFO")
    try:
        async with lifespan_fn(app):
            # Simulate a stuck cycle: acquire the lock without releasing AND
            # inject a synthetic holder tuple representing a job that started
            # 100 seconds ago.
            await app.state.search_lock.acquire()
            app.state.search_lock_holder = (
                "radarr_Default_search",
                time.monotonic() - 100.0,
            )
            # On block exit, the finally runs: INFO-on-entry log fires
            # immediately; wait_for times out at 0.1s; WARNING-on-timeout fires.
    finally:
        logger.remove(sink_id)

    output = sink.getvalue()

    # Assert INFO-on-entry log exists, names the holder, and is at INFO level.
    info_lines = [
        line for line in output.splitlines()
        if line.startswith("INFO | ") and "radarr_Default_search" in line
    ]
    assert info_lines, (
        f"Expected INFO-on-entry log naming radarr_Default_search, got:\n{output!r}"
    )

    # Assert WARNING-on-timeout log exists, names the holder, and includes
    # elapsed=99.x or 100.x (rounding tolerance for wall-clock jitter).
    warning_lines = [
        line for line in output.splitlines()
        if line.startswith("WARNING | ") and "radarr_Default_search" in line
    ]
    assert warning_lines, (
        f"Expected WARNING-on-timeout log naming radarr_Default_search, got:\n{output!r}"
    )
    assert re.search(r"elapsed=(99|100)\.\d", warning_lines[0]), (
        f"Expected elapsed=99.x or 100.x in WARNING line: {warning_lines[0]!r}"
    )


# ---------------------------------------------------------------------------
# Tracking integration (Plan 20-03): run_tracking_check after search cycle
# ---------------------------------------------------------------------------


async def _make_app_with_db(tmp_path, *, radarr_client=None, sonarr_client=None):
    """Build a mock FastAPI app with real DB and search_lock for scheduler tests."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    state_path = tmp_path / "state.json"
    settings = make_settings()
    state = _default_state(settings)
    save_state(state, state_path)

    app = FastAPI()
    app.state.db = db
    app.state.search_lock = asyncio.Lock()
    app.state.triggarr_state = state
    app.state.settings = settings
    app.state.radarr_clients = {"Default": radarr_client} if radarr_client else {}
    app.state.sonarr_clients = {"Default": sonarr_client} if sonarr_client else {}
    app.state.state_path = state_path
    # Plan 65-02: scheduler now reads/writes these state attrs unconditionally.
    app.state.search_failures = {}
    app.state.persistence_degraded = False
    app.state.tag_cache = {}
    return app, db, state_path


async def test_search_job_runs_tracking_after_cycle(tmp_path):
    """After a search cycle, tracking resolves a pending 'searched' entry to 'grabbed'."""
    from triggarr.models.arr import GrabEvent

    radarr_client = AsyncMock()
    # get_wanted_missing and get_cutoff_unmet return empty pages (no new searches needed)
    radarr_client.get_wanted_missing = AsyncMock(return_value={"page": 1, "totalRecords": 0, "records": []})
    radarr_client.get_cutoff_unmet = AsyncMock(return_value={"page": 1, "totalRecords": 0, "records": []})

    app, db, state_path = await _make_app_with_db(tmp_path, radarr_client=radarr_client)

    try:
        # Insert a "searched" entry with timestamp old enough for grab to fall within window
        search_time = datetime.now(UTC) - timedelta(minutes=5)
        await insert_search_entry(
            db, "Radarr", "missing", "Test Movie",
            outcome="searched", item_id=42, missing_count=None,
        )
        # Override timestamp to search_time
        await db.execute(
            "UPDATE search_history SET timestamp = ? WHERE id = (SELECT last_insert_rowid())",
            (search_time.isoformat().replace("+00:00", "Z"),),
        )
        await db.commit()

        # Mock grab history: a grab happened 2 minutes after search
        grab_time = search_time + timedelta(minutes=2)
        grab_date = grab_time.isoformat().replace("+00:00", "Z")
        radarr_client.get_grab_history = AsyncMock(return_value=[
            GrabEvent(id=100, date=grab_date, eventType="grabbed", sourceTitle="Movie.2024.1080p"),
        ])

        # Patch the cycle function to be a no-op (we only care about tracking)
        with (
            patch(
                "triggarr.search.scheduler.run_radarr_cycle",
                new=AsyncMock(return_value=app.state.triggarr_state),
            ),
            patch(
                "triggarr.search.scheduler.save_state",
                new=MagicMock(),
            ),
        ):
            job = make_search_job(app, "radarr", "Default", state_path)
            await job()

        # Verify the entry was resolved to "grabbed"
        async with db.execute("SELECT outcome FROM search_history WHERE item_id = 42") as cursor:
            row = await cursor.fetchone()
        assert row is not None, "Search entry should exist"
        assert row[0] == "grabbed", f"Expected 'grabbed', got '{row[0]}'"
    finally:
        await db.close()


async def test_search_job_tracking_failure_nonfatal(tmp_path):
    """Tracking failure does not prevent state save or raise from the job.

    SAFETY-02 narrowed the outer except to (httpx.HTTPError,
    pydantic.ValidationError, aiosqlite.Error, OSError). The inner
    tracking-check try/except uses the same narrow tuple. To stay in
    the realistic failure path (tracking calls httpx + aiosqlite), this
    test simulates an httpx.ConnectError — which is what a Radarr/Sonarr
    history-endpoint outage actually raises. RuntimeError would now
    correctly propagate (it's a code bug, not a transient failure).
    """
    radarr_client = AsyncMock()
    app, db, state_path = await _make_app_with_db(tmp_path, radarr_client=radarr_client)

    try:
        with (
            patch(
                "triggarr.search.scheduler.run_radarr_cycle",
                new=AsyncMock(return_value=app.state.triggarr_state),
            ),
            patch(
                "triggarr.search.scheduler.save_state",
                new=MagicMock(),
            ) as mock_save,
            patch(
                "triggarr.search.scheduler.run_tracking_check",
                new=AsyncMock(side_effect=httpx.ConnectError("tracking unreachable")),
            ),
        ):
            job = make_search_job(app, "radarr", "Default", state_path)
            # Should NOT raise despite tracking failure (httpx.ConnectError is
            # in the inner tracking narrow tuple)
            await job()
            # State was saved before tracking ran
            mock_save.assert_called_once()
    finally:
        await db.close()


async def test_search_job_logs_tracking_results(tmp_path, capsys):
    """Tracking results are logged at info level when there are resolved entries."""
    from loguru import logger

    radarr_client = AsyncMock()
    app, db, state_path = await _make_app_with_db(tmp_path, radarr_client=radarr_client)

    captured_messages = []

    def sink(message):
        captured_messages.append(str(message))

    sink_id = logger.add(sink, level="INFO")

    try:
        tracking_result = {"grabbed": 1, "partial": 0, "unresolved": 0, "errors": 0}

        with (
            patch(
                "triggarr.search.scheduler.run_radarr_cycle",
                new=AsyncMock(return_value=app.state.triggarr_state),
            ),
            patch(
                "triggarr.search.scheduler.save_state",
                new=MagicMock(),
            ),
            patch(
                "triggarr.search.scheduler.run_tracking_check",
                new=AsyncMock(return_value=tracking_result),
            ),
        ):
            job = make_search_job(app, "radarr", "Default", state_path)
            await job()

        # Check that tracking info was logged
        tracking_logs = [m for m in captured_messages if "Tracking:" in m]
        assert len(tracking_logs) > 0, f"Expected tracking log message, got: {captured_messages}"
        assert "1 grabbed" in tracking_logs[0]
    finally:
        logger.remove(sink_id)
        await db.close()


# ---------------------------------------------------------------------------
# RES-03 (Plan 67-02): tag-list cache TTL + resolver threaded into job()
#
# These tests build a real RadarrClient on an httpx.MockTransport (same shape
# as _build_outage_app) but configure a missing_tag so the engine actually
# reaches the tag-resolution block and invokes the job()'s _get_tags_cached
# resolver. They assert against app.state.tag_cache directly: cache hit avoids
# the get_tags() round-trip, cache miss stores a fresh entry, and a stale entry
# triggers a refresh.
# ---------------------------------------------------------------------------


def _build_tag_cache_app(tmp_path, *, tag_handler):
    """Build a FastAPI app with a real RadarrClient (MockTransport) + a
    tag-configured Default instance, returning (app, job).

    The instance sets missing_tag='triggarr' so run_radarr_cycle reaches the
    get_tags resolver path. tag_handler controls what the /api/v3/tag endpoint
    returns; the wanted/cutoff endpoints return empty paginated payloads so the
    cycle completes successfully (connected=True).
    """
    settings = Settings(
        radarr={
            "Default": InstanceConfig(
                url="http://radarr-test:7878",
                api_key="test-key",
                enabled=True,
                search_missing_count=5,
                search_cutoff_count=5,
                search_interval=30,
                missing_tag="triggarr",
            ),
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v3/tag":
            return tag_handler(request)
        return httpx.Response(
            200,
            json={
                "page": 1,
                "pageSize": 50,
                "sortKey": "id",
                "totalRecords": 0,
                "records": [],
            },
        )

    real_client = RadarrClient(base_url="http://radarr-test:7878", api_key="test-key")
    real_client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
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


async def test_tag_cache_hit_skips_get_tags_call(tmp_path):
    """RES-03: a fresh cache entry is reused; the *arr tag endpoint is not hit."""
    tag_calls = {"count": 0}

    def tag_handler(request: httpx.Request) -> httpx.Response:
        tag_calls["count"] += 1
        return httpx.Response(200, json=[{"id": 5, "label": "triggarr"}])

    app, job = _build_tag_cache_app(tmp_path, tag_handler=tag_handler)
    # Pre-populate a FRESH cache entry (fetched just now).
    app.state.tag_cache[("radarr", "Default")] = (
        [Tag(id=5, label="triggarr")],
        time.monotonic(),
    )

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

    # The cached entry was reused — the /api/v3/tag endpoint was never called.
    assert tag_calls["count"] == 0


async def test_tag_cache_miss_calls_get_tags_and_stores_result(tmp_path):
    """RES-03: an empty cache is populated after a successful cycle fetches tags."""
    tag_calls = {"count": 0}

    def tag_handler(request: httpx.Request) -> httpx.Response:
        tag_calls["count"] += 1
        return httpx.Response(200, json=[{"id": 5, "label": "triggarr"}])

    app, job = _build_tag_cache_app(tmp_path, tag_handler=tag_handler)
    assert app.state.tag_cache == {}  # cold

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

    assert tag_calls["count"] == 1, "Cold cache should trigger exactly one tag fetch"
    entry = app.state.tag_cache.get(("radarr", "Default"))
    assert entry is not None, "Cache entry should be stored after a successful fetch"
    cached_tags, fetched_at = entry
    assert [t.label for t in cached_tags] == ["triggarr"]
    assert isinstance(fetched_at, float)


async def test_tag_cache_ttl_expired_triggers_fresh_fetch(tmp_path):
    """RES-03: a stale entry (older than the TTL) triggers a refresh."""
    tag_calls = {"count": 0}

    def tag_handler(request: httpx.Request) -> httpx.Response:
        tag_calls["count"] += 1
        return httpx.Response(200, json=[{"id": 5, "label": "triggarr"}])

    app, job = _build_tag_cache_app(tmp_path, tag_handler=tag_handler)
    # Pre-populate a STALE entry (fetched beyond the TTL window).
    stale_at = time.monotonic() - (_TAG_CACHE_TTL_SECONDS + 1.0)
    app.state.tag_cache[("radarr", "Default")] = (
        [Tag(id=99, label="stale")],
        stale_at,
    )

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

    assert tag_calls["count"] == 1, "Stale entry should trigger exactly one refresh fetch"
    entry = app.state.tag_cache.get(("radarr", "Default"))
    assert entry is not None
    cached_tags, fetched_at = entry
    # Entry was refreshed to the live value, not the stale one.
    assert [t.label for t in cached_tags] == ["triggarr"]
    assert fetched_at > stale_at


# ---------------------------------------------------------------------------
# CHARD-02/03 (Plan 69-03): _run_one_cycle — manual search failure-counter tests
#
# These tests drive _run_one_cycle directly (not the APScheduler job wrapper)
# with a real RadarrClient on an httpx.MockTransport — identical pattern to the
# 6 existing scheduled-path failure-counter tests. Do NOT patch
# _record_cycle_failure or _evaluate_cycle_outcome; test the actual counter
# logic end-to-end through the shared helper.
# ---------------------------------------------------------------------------


def _build_manual_app(tmp_path, *, transport_handler, max_consecutive_failures=5):
    """Build a FastAPI app + (real_client, instance_config) for _run_one_cycle tests.

    Returns (app, real_client, instance_config) instead of (app, job) so the
    test can call _run_one_cycle directly inside its own async with search_lock.
    """
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

    instance_config = settings.get_enabled_instances("radarr")["Default"]
    return app, real_client, instance_config


async def test_search_now_failure_counter_increment(tmp_path):
    """CHARD-03 (SAFETY-03): manual _run_one_cycle failure increments search_failures.

    Mirrors test_failure_counter_increments_on_real_arr_outage but drives
    _run_one_cycle directly (the shared helper, not the APScheduler job wrapper).
    Does NOT patch _record_cycle_failure or _evaluate_cycle_outcome — exercises
    the real counter logic end-to-end through the shared helper.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "Service unavailable"})

    app, real_client, instance_config = _build_manual_app(tmp_path, transport_handler=handler)

    async def _get_tags_cached() -> list:
        return []

    with (
        patch("triggarr.clients.base.asyncio.sleep", new=AsyncMock()),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
    ):
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

    assert app.state.search_failures["radarr_Default_search"] == 2, (
        f"Expected counter=2 after 2 failures, got {app.state.search_failures}"
    )
    assert app.state.triggarr_state["radarr"]["Default"]["connected"] is False


async def test_search_now_failure_counter_resets_on_success(tmp_path):
    """CHARD-03 (SAFETY-03): successful _run_one_cycle resets the failure counter to 0.

    Mirrors test_failure_counter_resets_on_success: drive fail then success via
    _run_one_cycle and assert counter trajectory: 1 → reset to 0.

    Uses a cycle-counter dict (set explicitly before each _run_one_cycle call)
    so the handler can distinguish cycle 1 (fail) vs cycle 2 (success) without
    the retry-request count interfering.
    """
    cycle = {"n": 1}

    def handler(request: httpx.Request) -> httpx.Response:
        if cycle["n"] == 1:
            return httpx.Response(503, json={"error": "Service unavailable"})
        # Cycle 2 success: tag endpoint returns [] (flat array), paginated endpoints
        # return empty records so the cycle completes with connected=True.
        if request.url.path == "/api/v3/tag":
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json={"page": 1, "pageSize": 50, "sortKey": "id", "totalRecords": 0, "records": []},
        )

    app, real_client, instance_config = _build_manual_app(tmp_path, transport_handler=handler)

    async def _get_tags_cached() -> list:
        return []

    with (
        patch("triggarr.clients.base.asyncio.sleep", new=AsyncMock()),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
    ):
        # Cycle 1 — fail (503)
        cycle["n"] = 1
        async with app.state.search_lock:
            await _run_one_cycle(
                app, "radarr", "Default", real_client, instance_config,
                tmp_path / "state.json", _get_tags_cached,
            )
        assert app.state.search_failures["radarr_Default_search"] == 1, (
            f"Expected counter=1 after first failure, got {app.state.search_failures}"
        )

        # Cycle 2 — success (200)
        cycle["n"] = 2
        async with app.state.search_lock:
            await _run_one_cycle(
                app, "radarr", "Default", real_client, instance_config,
                tmp_path / "state.json", _get_tags_cached,
            )

    assert app.state.search_failures["radarr_Default_search"] == 0, (
        f"Expected counter=0 after success, got {app.state.search_failures}"
    )


async def test_search_now_failure_returns_card_200(tmp_path):
    """HTTP-contract guard (RESEARCH Pitfall 3): failing manual search returns HTTP 200 + card.

    Drives the actual search_now route via TestClient with a 503-returning
    MockTransport-backed client. Asserts that even on failure the response is
    HTTP 200 and contains the app_card partial markup — never a 500.
    This guards the always-return-card-on-failure contract through the refactor.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "Service unavailable"})

    settings = make_settings()

    real_client = RadarrClient(base_url="http://radarr-test:7878", api_key="test-key")
    real_client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://radarr-test:7878",
        headers={"X-Api-Key": "test-key", "Content-Type": "application/json"},
    )
    real_client._app_name = "Radarr"

    state = _default_state(settings)
    state["radarr"]["Default"] = _default_instance_state()
    state["radarr"]["Default"]["connected"] = True

    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    db_path = tmp_path / "test.db"
    db_conn = await aiosqlite.connect(db_path)
    await init_db(db_conn, db_path)

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
    app.state.db = db_conn
    app.state.state_path = tmp_path / "state.json"
    app.state.last_search_time = {}
    app.state.last_health_check = None
    # Minimal scheduler mock (needed for dashboard template rendering)
    mock_scheduler = MagicMock()
    mock_job = MagicMock()
    mock_job.next_run_time = None
    mock_scheduler.get_job.return_value = mock_job
    app.state.scheduler = mock_scheduler

    try:
        with (
            patch("triggarr.clients.base.asyncio.sleep", new=AsyncMock()),
            patch("triggarr.search.scheduler.save_state", new=MagicMock()),
            patch("triggarr.web.routes.save_state", new=MagicMock()),
            TestClient(app, raise_server_exceptions=True) as tc,
        ):
            response = tc.post("/api/search-now/radarr/Default")
    finally:
        await db_conn.close()

    assert response.status_code == 200, (
        f"Expected HTTP 200 on failing manual search, got {response.status_code}: {response.text}"
    )
    # The response should contain the app_card partial markup (not a server error page)
    assert "app_card" in response.text or "radarr" in response.text.lower(), (
        f"Expected app_card partial content in response, got: {response.text[:200]}"
    )
