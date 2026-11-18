"""Tests for the scheduler job factory and lifespan shutdown.

Covers: client-None early return, unhandled exception swallowing,
graceful shutdown with search_lock drain (DEBT-06),
and tracking integration after search cycles (Plan 20-03).
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import io
import re
import shutil
import threading
import time
from dataclasses import dataclass, field
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


def _build_outage_app(
    tmp_path,
    *,
    max_consecutive_failures=5,
    transport_handler,
    search_missing_count=5,
    search_cutoff_count=5,
):
    """Build a FastAPI app wired with a real RadarrClient on a MockTransport.

    The returned (app, job) tuple lets the test drive `make_search_job` end
    to end: the real `run_radarr_cycle` runs, its internal HTTP calls hit the
    MockTransport (which returns whatever the handler decides), and the
    scheduler's post-cycle counter logic observes the engine's graded
    outcome (78-05 / OUTCOME-04).

    Note: settings are mutated AFTER make_settings() to apply the per-test
    max_consecutive_failures and (R-07) per-queue search counts
    (GeneralConfig/InstanceConfig are plain BaseModels — direct attribute
    mutation is allowed).
    """
    settings = make_settings()
    settings.general.max_consecutive_failures = max_consecutive_failures
    settings.radarr["Default"].search_missing_count = search_missing_count
    settings.radarr["Default"].search_cutoff_count = search_cutoff_count

    # Real RadarrClient with its httpx.AsyncClient swapped for one driven
    # by the MockTransport. base_url must match the original so any path
    # the engine constructs (e.g. /api/v3/wanted/missing) resolves correctly.
    real_client = RadarrClient(base_url="http://radarr-test:7878", api_key=SecretStr("test-key"))
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

    default_client = RadarrClient(base_url="http://radarr-default:7878", api_key=SecretStr("key-default"))
    default_client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(default_handler),
        base_url="http://radarr-default:7878",
        headers={"X-Api-Key": "key-default", "Content-Type": "application/json"},
    )
    default_client._app_name = "Radarr"

    fourk_client = RadarrClient(base_url="http://radarr-4k:7878", api_key=SecretStr("key-4k"))
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


# ---------------------------------------------------------------------------
# 78-05 (OUTCOME-04): counter follows the cycle grade, not `connected`
#
# These tests patch `run_radarr_cycle` with a fake cycle function that writes
# a full LastCycleRecord directly, so the counter logic can be driven by a
# specific grade sequence without needing a real *arr backend for every case.
# The real-engine tests further below still exercise the actual fetch/dispatch
# path (R-07, command rejection).
# ---------------------------------------------------------------------------


def _fake_cycle(grade: str, *, connected: bool = True, fetch_error: str | None = None):
    """Build a fake cycle function with the run_radarr_cycle signature.

    Writes a full ``LastCycleRecord`` to ``state["radarr"][instance_name]["last_cycle"]``
    with the given grade (and every other required key), so the scheduler's
    grade-driven counter can be exercised directly without the real engine.
    """

    async def _cycle(client, state, instance_name, instance_config, settings, db, *, get_tags_fn=None):
        ist = state["radarr"][instance_name]
        ist["connected"] = connected
        ist["last_cycle"] = {
            "grade": grade,
            "accepted": 0,
            "failed": 0,
            "malformed_skipped": 0,
            "persistence_failed": 0,
            "failure_reasons": [],
            "unevaluated": [],
            "eligible": {},
            "fetch_error": fetch_error,
            "finished_at": "2026-01-01T00:00:00Z",
        }
        return state

    return _cycle


def _build_fake_cycle_app(tmp_path, *, max_consecutive_failures=5):
    """Build a FastAPI app for driving the scheduler's counter via a patched cycle fn.

    Unlike `_build_outage_app`, the client is a bare MagicMock: the patched
    `run_radarr_cycle` (via `_fake_cycle`) never touches it.
    """
    settings = make_settings()
    settings.general.max_consecutive_failures = max_consecutive_failures

    state = _default_state(settings)
    state["radarr"]["Default"] = _default_instance_state()
    state["radarr"]["Default"]["connected"] = True

    app = FastAPI()
    app.state.radarr_clients = {"Default": MagicMock()}
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


def _build_fake_cycle_manual_app(tmp_path, *, max_consecutive_failures=5):
    """Build (app, client, instance_config) for driving `_run_one_cycle` with a patched cycle fn.

    Mirrors `_build_fake_cycle_app` but returns the pieces `_run_one_cycle`
    takes directly (the Search Now shape), not a `job()` closure.
    """
    settings = make_settings()
    settings.general.max_consecutive_failures = max_consecutive_failures

    state = _default_state(settings)
    state["radarr"]["Default"] = _default_instance_state()
    state["radarr"]["Default"]["connected"] = True

    app = FastAPI()
    app.state.radarr_clients = {"Default": MagicMock()}
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
    return app, MagicMock(), instance_config


_NO_TRACKING_RESULT = {"grabbed": 0, "partial": 0, "partial_expired": 0, "unresolved": 0, "errors": 0}


async def test_failure_counter_increments_on_grade_failed(tmp_path):
    """OUTCOME-04: three Failed-graded cycles increment the counter to 3."""
    app, job = _build_fake_cycle_app(tmp_path)
    with (
        patch(
            "triggarr.search.scheduler.run_tracking_check",
            new=AsyncMock(return_value=_NO_TRACKING_RESULT),
        ),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
        patch("triggarr.search.scheduler.run_radarr_cycle", new=_fake_cycle("failed")),
    ):
        await job()
        await job()
        await job()

    assert app.state.search_failures["radarr_Default_search"] == 3


async def test_failure_counter_counts_grade_failed_with_connected_true(tmp_path):
    """OUTCOME-04: a Failed grade increments the counter even though `connected` stays True.

    Proves the counter no longer reads `connected` -- a reachable *arr that
    rejects every command (grade Failed, connected True) must still count.
    """
    app, job = _build_fake_cycle_app(tmp_path)
    with (
        patch(
            "triggarr.search.scheduler.run_tracking_check",
            new=AsyncMock(return_value=_NO_TRACKING_RESULT),
        ),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
        patch("triggarr.search.scheduler.run_radarr_cycle", new=_fake_cycle("failed", connected=True)),
    ):
        await job()

    assert app.state.search_failures["radarr_Default_search"] == 1
    assert app.state.triggarr_state["radarr"]["Default"]["connected"] is True


async def test_failure_counter_resets_on_grade_partial_after_failed(tmp_path):
    """OUTCOME-04: Failed, Failed, Partial -> counter resets to 0 on Partial."""
    app, job = _build_fake_cycle_app(tmp_path)
    with (
        patch(
            "triggarr.search.scheduler.run_tracking_check",
            new=AsyncMock(return_value=_NO_TRACKING_RESULT),
        ),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
    ):
        with patch("triggarr.search.scheduler.run_radarr_cycle", new=_fake_cycle("failed")):
            await job()
        with patch("triggarr.search.scheduler.run_radarr_cycle", new=_fake_cycle("failed")):
            await job()
        with patch("triggarr.search.scheduler.run_radarr_cycle", new=_fake_cycle("partial")):
            await job()

    assert app.state.search_failures["radarr_Default_search"] == 0


async def test_failure_counter_resets_on_grade_nothing_needed_after_failed(tmp_path):
    """OUTCOME-04: Failed, then Nothing needed searching -> counter resets to 0."""
    app, job = _build_fake_cycle_app(tmp_path)
    with (
        patch(
            "triggarr.search.scheduler.run_tracking_check",
            new=AsyncMock(return_value=_NO_TRACKING_RESULT),
        ),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
    ):
        with patch("triggarr.search.scheduler.run_radarr_cycle", new=_fake_cycle("failed")):
            await job()
        with patch("triggarr.search.scheduler.run_radarr_cycle", new=_fake_cycle("nothing_needed")):
            await job()

    assert app.state.search_failures["radarr_Default_search"] == 0


async def test_failure_counter_resets_on_grade_success_after_failed(tmp_path):
    """OUTCOME-04: Failed, then Success -> counter resets to 0."""
    app, job = _build_fake_cycle_app(tmp_path)
    with (
        patch(
            "triggarr.search.scheduler.run_tracking_check",
            new=AsyncMock(return_value=_NO_TRACKING_RESULT),
        ),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
    ):
        with patch("triggarr.search.scheduler.run_radarr_cycle", new=_fake_cycle("failed")):
            await job()
        with patch("triggarr.search.scheduler.run_radarr_cycle", new=_fake_cycle("success")):
            await job()

    assert app.state.search_failures["radarr_Default_search"] == 0


async def test_failure_counter_resets_when_last_cycle_missing():
    """OUTCOME-04: a state with no last_cycle (pre-first-cycle) resets to 0 and does not raise."""
    app = FastAPI()
    app.state.triggarr_state = {"radarr": {"Default": {}}}
    app.state.search_failures = {"radarr_Default_search": 3}

    result = _evaluate_cycle_outcome(app, "radarr", "Default", "radarr_Default_search")

    assert result is True
    assert app.state.search_failures["radarr_Default_search"] == 0


async def test_search_now_failure_counter_follows_grade_sequence(tmp_path):
    """OUTCOME-04 / D-02: Search Now path -- Failed, Failed, Partial -> 1, 2, 0."""
    app, real_client, instance_config = _build_fake_cycle_manual_app(tmp_path)

    async def _get_tags_cached() -> list:
        return []

    with (
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
    ):
        with patch("triggarr.search.scheduler.run_radarr_cycle", new=_fake_cycle("failed")):
            async with app.state.search_lock:
                await _run_one_cycle(
                    app, "radarr", "Default", real_client, instance_config,
                    tmp_path / "state.json", _get_tags_cached,
                )
        assert app.state.search_failures["radarr_Default_search"] == 1

        with patch("triggarr.search.scheduler.run_radarr_cycle", new=_fake_cycle("failed")):
            async with app.state.search_lock:
                await _run_one_cycle(
                    app, "radarr", "Default", real_client, instance_config,
                    tmp_path / "state.json", _get_tags_cached,
                )
        assert app.state.search_failures["radarr_Default_search"] == 2

        with patch("triggarr.search.scheduler.run_radarr_cycle", new=_fake_cycle("partial")):
            async with app.state.search_lock:
                await _run_one_cycle(
                    app, "radarr", "Default", real_client, instance_config,
                    tmp_path / "state.json", _get_tags_cached,
                )
        assert app.state.search_failures["radarr_Default_search"] == 0


async def test_search_now_failure_counter_resets_on_grade_nothing_needed(tmp_path):
    """OUTCOME-04 / D-02: Search Now path -- Failed, then Nothing needed searching -> 0."""
    app, real_client, instance_config = _build_fake_cycle_manual_app(tmp_path)

    async def _get_tags_cached() -> list:
        return []

    with patch("triggarr.search.scheduler.save_state", new=MagicMock()):
        with patch("triggarr.search.scheduler.run_radarr_cycle", new=_fake_cycle("failed")):
            async with app.state.search_lock:
                await _run_one_cycle(
                    app, "radarr", "Default", real_client, instance_config,
                    tmp_path / "state.json", _get_tags_cached,
                )
        assert app.state.search_failures["radarr_Default_search"] == 1

        with patch("triggarr.search.scheduler.run_radarr_cycle", new=_fake_cycle("nothing_needed")):
            async with app.state.search_lock:
                await _run_one_cycle(
                    app, "radarr", "Default", real_client, instance_config,
                    tmp_path / "state.json", _get_tags_cached,
                )
        assert app.state.search_failures["radarr_Default_search"] == 0


async def test_failure_counter_increments_on_real_arr_command_rejection(tmp_path):
    """OUTCOME-04: a reachable *arr that rejects every command still grades Failed.

    200 wanted/missing with one monitored movie, but POST /api/v3/command
    returns 500 for every attempt -- the engine's real per-item failure path
    (not a patched cycle fn) must still grade Failed and increment the counter.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v3/tag":
            return httpx.Response(200, json=[])
        if request.method == "POST" and request.url.path == "/api/v3/command":
            return httpx.Response(500, json={"error": "Internal Server Error"})
        if request.url.path == "/api/v3/wanted/missing":
            return httpx.Response(
                200,
                json={
                    "page": 1, "pageSize": 50, "sortKey": "id", "totalRecords": 1,
                    "records": [{"id": 1, "title": "M", "monitored": True}],
                },
            )
        return httpx.Response(
            200, json={"page": 1, "pageSize": 50, "sortKey": "id", "totalRecords": 0, "records": []}
        )

    app, job = _build_outage_app(tmp_path, transport_handler=handler)

    with (
        patch("triggarr.clients.base.asyncio.sleep", new=AsyncMock()),
        patch("triggarr.search.engine.insert_search_entry", new=AsyncMock()),
        patch(
            "triggarr.search.scheduler.run_tracking_check",
            new=AsyncMock(return_value=_NO_TRACKING_RESULT),
        ),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
    ):
        await job()

    assert app.state.search_failures["radarr_Default_search"] == 1
    assert app.state.triggarr_state["radarr"]["Default"]["last_cycle"]["grade"] == "failed"
    assert app.state.triggarr_state["radarr"]["Default"]["connected"] is True


async def test_failure_counter_ignores_inactive_queue_fetch_failure(tmp_path):
    """R-07: an inactive queue's fetch failure never increments the counter.

    search_cutoff_count=0 makes the cutoff queue inactive. Its 503 fetch
    failure must never abort the cycle, grade Failed, or flip `connected` --
    only an active queue's fetch failure does that (spec Sec 3.1 / R-07).
    """
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v3/tag":
            return httpx.Response(200, json=[])
        if request.method == "POST" and request.url.path == "/api/v3/command":
            return httpx.Response(201, json={"id": 1})
        if request.url.path == "/api/v3/wanted/missing":
            return httpx.Response(
                200,
                json={
                    "page": 1, "pageSize": 50, "sortKey": "id", "totalRecords": 1,
                    "records": [{"id": 1, "title": "M", "monitored": True}],
                },
            )
        if request.url.path == "/api/v3/wanted/cutoff":
            return httpx.Response(503, json={"error": "Service unavailable"})
        return httpx.Response(
            200, json={"page": 1, "pageSize": 50, "sortKey": "id", "totalRecords": 0, "records": []}
        )

    app, job = _build_outage_app(
        tmp_path, transport_handler=handler, search_missing_count=1, search_cutoff_count=0,
    )

    with (
        patch("triggarr.clients.base.asyncio.sleep", new=AsyncMock()),
        patch("triggarr.search.engine.insert_search_entry", new=AsyncMock()),
        patch(
            "triggarr.search.scheduler.run_tracking_check",
            new=AsyncMock(return_value=_NO_TRACKING_RESULT),
        ),
        patch("triggarr.search.scheduler.save_state", new=MagicMock()),
    ):
        await job()
        await job()
        await job()

    assert app.state.search_failures["radarr_Default_search"] == 0
    assert app.state.triggarr_state["radarr"]["Default"]["last_cycle"]["grade"] == "success"
    assert app.state.triggarr_state["radarr"]["Default"]["connected"] is True


async def test_failure_counter_log_reason_names_instance_unreachable_on_fetch_failure(tmp_path):
    """OUTCOME-04: a real fetch-failure's grade-driven reason still says 'instance unreachable'.

    Log-line continuity: the engine's fetch-failure record grades Failed, and
    the scheduler's failure reason for a fetch_error-carrying record is the
    same "instance unreachable" text operators already search logs for.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "Service unavailable"})

    app, job = _build_outage_app(tmp_path, transport_handler=handler)

    sink = io.StringIO()
    sink_id = logger.add(sink, format="{level} | {message}", level="WARNING")
    try:
        with (
            patch("triggarr.clients.base.asyncio.sleep", new=AsyncMock()),
            patch(
                "triggarr.search.scheduler.run_tracking_check",
                new=AsyncMock(return_value=_NO_TRACKING_RESULT),
            ),
            patch("triggarr.search.scheduler.save_state", new=MagicMock()),
        ):
            await job()
    finally:
        logger.remove(sink_id)

    output = sink.getvalue()
    assert "instance unreachable" in output, f"Expected 'instance unreachable' in log output: {output!r}"
    assert app.state.triggarr_state["radarr"]["Default"]["last_cycle"]["grade"] == "failed"


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


# ---------------------------------------------------------------------------
# D-04/D-06 (Plan 75-03): _read_shutdown_drain_timeout precedence matrix
#
# Tests the refactored helper that accepts a `configured` default and
# applies env override on top, with >= 1.0 clamp on both sources and a
# finite guard (math.isfinite) so the helper NEVER returns nan/inf.
# ---------------------------------------------------------------------------


def test_drain_timeout_configured_default_used_when_env_unset(monkeypatch):
    """D-04: env unset → configured value is returned (clamped to >= 1.0)."""
    import math

    from triggarr.search.scheduler import _read_shutdown_drain_timeout

    monkeypatch.delenv("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", raising=False)
    result = _read_shutdown_drain_timeout(45.0)
    assert result == 45.0
    assert math.isfinite(result)


def test_drain_timeout_env_overrides_configured(monkeypatch):
    """D-06: env set → env value wins over configured."""
    import math

    from triggarr.search.scheduler import _read_shutdown_drain_timeout

    monkeypatch.setenv("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", "15.0")
    result = _read_shutdown_drain_timeout(45.0)
    assert result == 15.0
    assert math.isfinite(result)


def test_drain_timeout_clamp_on_configured(monkeypatch):
    """D-06: configured value below 1.0 is clamped up to 1.0."""
    import math

    from triggarr.search.scheduler import _read_shutdown_drain_timeout

    monkeypatch.delenv("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", raising=False)
    result = _read_shutdown_drain_timeout(0.5)
    assert result == 1.0
    assert math.isfinite(result)


def test_drain_timeout_clamp_on_env(monkeypatch):
    """D-06: env value below 1.0 is clamped up to 1.0."""
    import math

    from triggarr.search.scheduler import _read_shutdown_drain_timeout

    monkeypatch.setenv("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", "0")
    result = _read_shutdown_drain_timeout(45.0)
    assert result == 1.0
    assert math.isfinite(result)


def test_drain_timeout_malformed_env_falls_back_to_configured(monkeypatch):
    """D-06: malformed env value falls back to configured (no crash)."""
    import math

    from triggarr.search.scheduler import _read_shutdown_drain_timeout

    monkeypatch.setenv("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", "abc")
    result = _read_shutdown_drain_timeout(45.0)
    assert result == 45.0
    assert math.isfinite(result)


def test_drain_timeout_env_nan_falls_back_to_configured(monkeypatch):
    """D-06 finite guard: env 'nan' is non-finite → falls back to configured."""
    import math

    from triggarr.search.scheduler import _read_shutdown_drain_timeout

    monkeypatch.setenv("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", "nan")
    result = _read_shutdown_drain_timeout(45.0)
    assert result == 45.0
    assert math.isfinite(result) is True


def test_drain_timeout_env_inf_falls_back_to_configured(monkeypatch):
    """D-06 finite guard: env 'inf' is non-finite → falls back to configured.

    Without the isfinite guard, max(inf, 1.0) == inf would pass through.
    """
    import math

    from triggarr.search.scheduler import _read_shutdown_drain_timeout

    monkeypatch.setenv("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", "inf")
    result = _read_shutdown_drain_timeout(45.0)
    assert result == 45.0
    assert math.isfinite(result) is True


def test_drain_timeout_env_neg_inf_falls_back_to_configured(monkeypatch):
    """D-06 finite guard: env '-inf' is non-finite → falls back to configured."""
    import math

    from triggarr.search.scheduler import _read_shutdown_drain_timeout

    monkeypatch.setenv("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", "-inf")
    result = _read_shutdown_drain_timeout(45.0)
    assert result == 45.0
    assert math.isfinite(result) is True


def test_drain_timeout_configured_inf_returns_finite(monkeypatch):
    """D-06 finite guard (defense in depth): non-finite configured → finite 60.0.

    75-01's allow_inf_nan=False makes this unreachable from the model, but the
    helper guards it defensively since it is the single choke point feeding
    asyncio.timeout.
    """
    import math

    from triggarr.search.scheduler import _read_shutdown_drain_timeout

    monkeypatch.delenv("TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT", raising=False)
    result = _read_shutdown_drain_timeout(float("inf"))
    assert math.isfinite(result) is True
    assert result == 60.0


async def test_shutdown_timeout_logs_holder_identity(tmp_path):
    """RES-01 (Codex finding 3): shutdown drain logs holder identity twice.

    On entry to the drain (INFO) AND on timeout (WARNING), the log must
    name the holder (job_id) and the elapsed runtime. The INFO-on-entry
    log fires immediately so that even if Docker SIGKILLs the process
    before the drain timeout completes, the operator still has visibility
    into which instance was stuck.

    Uses config-driven drain (shutdown_drain_timeout=1.0, the field minimum)
    instead of monkeypatching the module constant. The lock is held and never
    released, so the drain always times out regardless of the value.
    """
    from triggarr.search.scheduler import create_lifespan

    # Force a fast drain via config (1.0 is the field minimum under ge=1.0).
    # Do NOT use 0.1 — that raises ValidationError under 75-01's ge=1.0 bound.
    settings = make_settings(
        general=GeneralConfig(shutdown_drain_timeout=1.0),
        radarr_enabled=False,
        sonarr_enabled=False,
    )
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
            # immediately; asyncio.timeout fires at 1.0s; WARNING-on-timeout fires.
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
    # elapsed = (time of timeout check) - started ≈ 100s injected + drain 1.0s + overhead.
    # Allow 100–103s to tolerate wall-clock jitter across platforms.
    assert re.search(r"elapsed=(100|101|102|103)\.\d", warning_lines[0]), (
        f"Expected elapsed=100.x–103.x in WARNING line: {warning_lines[0]!r}"
    )


async def test_shutdown_drain_reads_configured_value(tmp_path):
    """D-05 / FINDING A: shutdown block reads the CONFIGURED drain value, not a hardcoded default.

    Uses a DISTINCTIVE shutdown_drain_timeout=7.0 (not the 60.0 default, not the 1.0 minimum)
    with the lock UNHELD so asyncio.timeout(7.0) returns instantly on the uncontested acquire
    — no real timeout wait. Asserts the no-holder drain-entry INFO log contains 'timeout=7.0s'.
    A shutdown block reading a hardcoded 60.0 would log 'timeout=60.0s' and the assertion
    would FAIL — proving the configured value genuinely reached the block.
    """
    from triggarr.search.scheduler import create_lifespan

    # Distinctive value: clearly not 60.0 (default) or 1.0 (minimum).
    settings = make_settings(
        general=GeneralConfig(shutdown_drain_timeout=7.0),
        radarr_enabled=False,
        sonarr_enabled=False,
    )
    state_path = tmp_path / "state.json"
    config_path = tmp_path / "triggarr.toml"

    lifespan_fn = create_lifespan(settings, state_path, config_path)
    app = FastAPI(lifespan=lifespan_fn)

    sink = io.StringIO()
    sink_id = logger.add(sink, format="{level} | {message}", level="INFO")
    try:
        async with lifespan_fn(app):
            # Lock is UNHELD — no acquire, no holder injected.
            # The no-holder branch logs the drain-entry INFO and then
            # asyncio.timeout(7.0) returns instantly on the uncontested acquire.
            pass
    finally:
        logger.remove(sink_id)

    output = sink.getvalue()

    # The no-holder drain-entry INFO line must contain 'timeout=7.0s'.
    # If the shutdown block reads a hardcoded 60.0, it would log 'timeout=60.0s'
    # and this assertion would fail — genuinely discriminating config-read from config-ignored.
    assert "timeout=7.0s" in output, (
        f"Expected drain-entry INFO to log 'timeout=7.0s' (configured value), got:\n{output!r}"
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

    real_client = RadarrClient(base_url="http://radarr-test:7878", api_key=SecretStr("test-key"))
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


async def test_tag_cache_fresh_entry_missing_configured_tag_refetches(tmp_path):
    """vibe-check bugs-001: a fresh cached list that lacks the configured tag is refetched.

    The tag was created in Radarr after the list was cached. The queue must
    not be skipped (or graded) on the stale list; the fresh list replaces the
    cache entry.
    """
    tag_calls = {"count": 0}

    def tag_handler(request: httpx.Request) -> httpx.Response:
        tag_calls["count"] += 1
        return httpx.Response(200, json=[{"id": 5, "label": "triggarr"}])

    app, job = _build_tag_cache_app(tmp_path, tag_handler=tag_handler)
    cached_at = time.monotonic()
    app.state.tag_cache[("radarr", "Default")] = ([Tag(id=99, label="other")], cached_at)

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

    assert tag_calls["count"] == 1
    ist = app.state.triggarr_state["radarr"]["Default"]
    assert ist["tag_warnings"] == []
    assert ist["unresolved_tag_scopes"] == {}
    cached_tags, fetched_at = app.state.tag_cache[("radarr", "Default")]
    assert [t.label for t in cached_tags] == ["triggarr"]
    assert fetched_at >= cached_at


async def test_tag_cache_refetch_still_missing_skips_queue_once(tmp_path):
    """bugs-001 companion: a tag that is really missing is confirmed by one fresh fetch, then skipped."""
    tag_calls = {"count": 0}

    def tag_handler(request: httpx.Request) -> httpx.Response:
        tag_calls["count"] += 1
        return httpx.Response(200, json=[{"id": 99, "label": "other"}])

    app, job = _build_tag_cache_app(tmp_path, tag_handler=tag_handler)
    app.state.tag_cache[("radarr", "Default")] = ([Tag(id=99, label="other")], time.monotonic())

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

    assert tag_calls["count"] == 1
    ist = app.state.triggarr_state["radarr"]["Default"]
    assert ist["tag_warnings"] == [{"tag": "triggarr", "field": "missing", "reason": "not_found"}]


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

    real_client = RadarrClient(base_url="http://radarr-test:7878", api_key=SecretStr("test-key"))
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

    real_client = RadarrClient(base_url="http://radarr-test:7878", api_key=SecretStr("test-key"))
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


# ---------------------------------------------------------------------------
# Phase 81 (Plan 04): attribution cutover + stable-ID wiring at startup
# ---------------------------------------------------------------------------


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

    @property
    def running(self) -> bool:
        return self.started and self.shutdown_wait is None

    def shutdown(self, wait: bool = True) -> None:
        self.shutdown_wait = wait


async def test_lifespan_records_attribution_cutover_once(tmp_path):
    """Running the lifespan twice leaves exactly one attribution_cutover row with an unchanged cutover_at."""
    from triggarr.search.scheduler import create_lifespan

    settings = Settings(
        sonarr={"Default": InstanceConfig(
            url="http://sonarr:8989", api_key="sonarr-test-key", enabled=True, id="sid-sonarr",
        )},
    )
    state_path = tmp_path / "state.json"
    config_path = tmp_path / "triggarr.toml"

    with patch("triggarr.search.scheduler.AsyncIOScheduler", return_value=_FakeScheduler()):
        lifespan_fn = create_lifespan(settings, state_path, config_path)
        app = FastAPI(lifespan=lifespan_fn)
        async with lifespan_fn(app):
            db = app.state.db
            async with db.execute("SELECT cutover_at FROM attribution_cutover") as cursor:
                rows = await cursor.fetchall()
            assert len(rows) == 1
            first_cutover_at = rows[0]["cutover_at"]
            async with db.execute("SELECT instance_stable_id FROM sonarr_instance_pre_fix") as cursor:
                pre_fix_rows = await cursor.fetchall()
            assert {r["instance_stable_id"] for r in pre_fix_rows} == {"sid-sonarr"}

    with patch("triggarr.search.scheduler.AsyncIOScheduler", return_value=_FakeScheduler()):
        lifespan_fn2 = create_lifespan(settings, state_path, config_path)
        app2 = FastAPI(lifespan=lifespan_fn2)
        async with lifespan_fn2(app2):
            db2 = app2.state.db
            async with db2.execute("SELECT cutover_at FROM attribution_cutover") as cursor:
                rows2 = await cursor.fetchall()
            assert len(rows2) == 1
            assert rows2[0]["cutover_at"] == first_cutover_at


async def test_lifespan_cutover_after_init_db(tmp_path):
    """ensure_cutover_recorded is called exactly once, right after init_db, with the name->stable-id mapping."""
    from triggarr.search.scheduler import create_lifespan

    settings = Settings(
        sonarr={"Default": InstanceConfig(
            url="http://sonarr:8989", api_key="sonarr-test-key", enabled=True, id="sid-sonarr",
        )},
    )
    state_path = tmp_path / "state.json"
    config_path = tmp_path / "triggarr.toml"

    call_order: list[str] = []
    captured_mapping: dict[str, str] = {}

    async def fake_init_db(db, db_path, **kwargs):
        call_order.append("init_db")

    async def fake_ensure_cutover_recorded(db, sonarr_instances):
        call_order.append("ensure_cutover_recorded")
        captured_mapping.update(sonarr_instances)

    with (
        patch("triggarr.search.scheduler.init_db", new=AsyncMock(side_effect=fake_init_db)),
        patch(
            "triggarr.search.scheduler.ensure_cutover_recorded",
            new=AsyncMock(side_effect=fake_ensure_cutover_recorded),
        ),
        patch("triggarr.search.scheduler.AsyncIOScheduler", return_value=_FakeScheduler()),
    ):
        lifespan_fn = create_lifespan(settings, state_path, config_path)
        app = FastAPI(lifespan=lifespan_fn)
        async with lifespan_fn(app):
            pass

    assert call_order == ["init_db", "ensure_cutover_recorded"]
    assert captured_mapping == {"Default": "sid-sonarr"}


async def test_lifespan_passes_stable_id_mapping_to_init_db(tmp_path):
    """S1: init_db receives a {(app, name): stable id} mapping built from every configured instance."""
    from triggarr.search.scheduler import create_lifespan

    settings = Settings(
        radarr={"Default": InstanceConfig(
            url="http://radarr:7878", api_key="radarr-test-key", enabled=True, id="sid-r",
        )},
        sonarr={"Main": InstanceConfig(
            url="http://sonarr:8989", api_key="sonarr-test-key", enabled=True, id="sid-m",
        )},
    )
    state_path = tmp_path / "state.json"
    config_path = tmp_path / "triggarr.toml"

    captured: dict = {}

    async def fake_init_db(db, db_path, **kwargs):
        captured.update(kwargs)

    with (
        patch("triggarr.search.scheduler.init_db", new=AsyncMock(side_effect=fake_init_db)),
        patch("triggarr.search.scheduler.ensure_cutover_recorded", new=AsyncMock()),
        patch("triggarr.search.scheduler.AsyncIOScheduler", return_value=_FakeScheduler()),
    ):
        lifespan_fn = create_lifespan(settings, state_path, config_path)
        app = FastAPI(lifespan=lifespan_fn)
        async with lifespan_fn(app):
            pass

    assert captured["instance_stable_ids"] == {("Radarr", "Default"): "sid-r", ("Sonarr", "Main"): "sid-m"}


async def test_lifespan_associates_existing_rows_on_upgrade(tmp_path, monkeypatch):
    """S1: a v9 DB's existing Sonarr rows get associated with their stable ID at startup, columns unchanged."""
    from tests.migration_faults import seed_v9_db
    from triggarr.search.scheduler import create_lifespan

    v9_db_path = await seed_v9_db(tmp_path, monkeypatch)
    state_path = tmp_path / "state.json"
    db_path = state_path.parent / "triggarr.db"
    shutil.copy(v9_db_path, db_path)

    settings = Settings(
        radarr={"Default": InstanceConfig(
            url="http://radarr:7878", api_key="radarr-test-key", enabled=True, id="sid-r",
        )},
        sonarr={"Old": InstanceConfig(
            url="http://sonarr:8989", api_key="sonarr-test-key", enabled=True, id="sid-a",
        )},
    )
    config_path = tmp_path / "triggarr.toml"

    with patch("triggarr.search.scheduler.AsyncIOScheduler", return_value=_FakeScheduler()):
        lifespan_fn = create_lifespan(settings, state_path, config_path)
        app = FastAPI(lifespan=lifespan_fn)
        async with lifespan_fn(app):
            db = app.state.db
            async with db.execute(
                "SELECT item_name, outcome, instance_stable_id FROM search_history "
                "WHERE instance_id = 'Old' ORDER BY id"
            ) as cursor:
                rows = await cursor.fetchall()
            assert [r["item_name"] for r in rows] == ["Old Show A", "Old Show B", "Old Show C"]
            assert [r["outcome"] for r in rows] == ["searched", "partial", "grabbed"]
            assert all(r["instance_stable_id"] == "sid-a" for r in rows)

            async with db.execute(
                "SELECT episodes_found, episodes_updated, instance_stable_id FROM lifetime_stats "
                "WHERE app = 'Sonarr' AND instance_id = 'Old'"
            ) as cursor:
                lifetime_row = await cursor.fetchone()
            assert lifetime_row["episodes_found"] == 3
            assert lifetime_row["episodes_updated"] == 1
            assert lifetime_row["instance_stable_id"] == "sid-a"


async def test_tracking_job_passes_instance_stable_id(tmp_path):
    """The scheduled job's tracking call passes instance_stable_id = that instance's InstanceConfig.id."""
    radarr_client = AsyncMock()
    sonarr_client = AsyncMock()
    app, db, state_path = await _make_app_with_db(tmp_path, radarr_client=radarr_client, sonarr_client=sonarr_client)
    app.state.settings.radarr["Default"].id = "sid-radarr"
    app.state.settings.sonarr["Default"].id = "sid-sonarr"

    tracking_result = {
        "grabbed": 0, "partial": 0, "partial_expired": 0, "unresolved": 0, "errors": 0, "identity_skipped": 0,
    }

    try:
        with (
            patch(
                "triggarr.search.scheduler.run_radarr_cycle",
                new=AsyncMock(return_value=app.state.triggarr_state),
            ),
            patch(
                "triggarr.search.scheduler.run_sonarr_cycle",
                new=AsyncMock(return_value=app.state.triggarr_state),
            ),
            patch("triggarr.search.scheduler.save_state", new=MagicMock()),
            patch(
                "triggarr.search.scheduler.run_tracking_check",
                new=AsyncMock(return_value=tracking_result),
            ) as mock_tracking,
        ):
            radarr_job = make_search_job(app, "radarr", "Default", state_path)
            await radarr_job()
            sonarr_job = make_search_job(app, "sonarr", "Default", state_path)
            await sonarr_job()

        assert mock_tracking.call_count == 2
        radarr_kwargs = mock_tracking.call_args_list[0].kwargs
        sonarr_kwargs = mock_tracking.call_args_list[1].kwargs
        assert radarr_kwargs["instance_stable_id"] == "sid-radarr"
        assert sonarr_kwargs["instance_stable_id"] == "sid-sonarr"
    finally:
        await db.close()


async def test_tracking_summary_logs_identity_skipped(tmp_path):
    """A non-zero identity_skipped count is both logged and a reason to emit the tracking summary line."""
    sonarr_client = AsyncMock()
    app, db, state_path = await _make_app_with_db(tmp_path, sonarr_client=sonarr_client)

    captured_messages: list[str] = []
    sink_id = logger.add(lambda m: captured_messages.append(str(m)), level="INFO")

    tracking_result = {
        "grabbed": 0, "partial": 0, "partial_expired": 0, "unresolved": 0, "errors": 0, "identity_skipped": 3,
    }

    try:
        with (
            patch(
                "triggarr.search.scheduler.run_sonarr_cycle",
                new=AsyncMock(return_value=app.state.triggarr_state),
            ),
            patch("triggarr.search.scheduler.save_state", new=MagicMock()),
            patch(
                "triggarr.search.scheduler.run_tracking_check",
                new=AsyncMock(return_value=tracking_result),
            ),
        ):
            job = make_search_job(app, "sonarr", "Default", state_path)
            await job()

        tracking_logs = [m for m in captured_messages if "Tracking:" in m]
        assert any("identity_skipped=3" in m for m in tracking_logs), (
            f"Expected an identity_skipped=3 tracking summary log, got: {captured_messages}"
        )
    finally:
        logger.remove(sink_id)
        await db.close()



_LEGACY_SEARCH_LOG = [
    {"name": "Old Show S01", "timestamp": "2024-01-01T00:00:00Z", "app": "Sonarr", "queue_type": "missing"},
    {"name": "Old Show S02", "timestamp": "2024-01-02T00:00:00Z", "app": "Sonarr", "queue_type": "missing"},
    {"name": "Old Movie", "timestamp": "2024-01-03T00:00:00Z", "app": "Radarr", "queue_type": "missing"},
]


async def _lifespan_snapshot_with_legacy_search_log(tmp_path) -> dict:
    """Start the real lifespan with a legacy state.json search_log and snapshot what startup recorded."""
    import json

    from triggarr.attribution import get_attribution_disclosure
    from triggarr.db import get_search_history
    from triggarr.search.scheduler import create_lifespan

    settings = Settings(
        sonarr={"Main": InstanceConfig(url="http://sonarr:8989", api_key="sonarr-test-key", enabled=True,
                                       id="sid-sonarr-main")},
    )
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"radarr": {}, "sonarr": {}, "lidarr": {}, "search_log": _LEGACY_SEARCH_LOG}))
    config_path = tmp_path / "triggarr.toml"
    with patch("triggarr.search.scheduler.AsyncIOScheduler", return_value=_FakeScheduler()):
        lifespan_fn = create_lifespan(settings, state_path, config_path)
        app = FastAPI(lifespan=lifespan_fn)
        async with lifespan_fn(app):
            db = app.state.db
            async with db.execute(
                "SELECT legacy_max_history_id, any_pre_fix_sonarr_data FROM attribution_cutover"
            ) as cursor:
                cutover = dict(await cursor.fetchone())
            async with db.execute(
                "SELECT id, outcome, instance_id, instance_stable_id FROM search_history ORDER BY id"
            ) as cursor:
                rows = [dict(r) for r in await cursor.fetchall()]
            history = await get_search_history(db)
            all_view = await get_attribution_disclosure(db)
            main_view = await get_attribution_disclosure(db, view_app="sonarr", sonarr_stable_id="sid-sonarr-main")
    return {
        "cutover": cutover,
        "rows": rows,
        "legacy_by_name": {e["name"]: e["is_legacy"] for e in history["entries"]},
        "all_view": all_view,
        "main_view": main_view,
        "search_log_after": json.loads(state_path.read_text())["search_log"],
    }


async def test_lifespan_imports_legacy_search_log_before_cutover(tmp_path):
    """The one-time state.json import runs before the cutover, so the cutover covers the imported rows."""
    snap = await _lifespan_snapshot_with_legacy_search_log(tmp_path)
    assert max(r["id"] for r in snap["rows"]) == 3
    assert snap["cutover"]["legacy_max_history_id"] == 3
    assert snap["cutover"]["any_pre_fix_sonarr_data"] == 1


async def test_lifespan_imported_sonarr_rows_are_legacy_and_disclosed(tmp_path):
    """Imported pre-fix Sonarr rows read as Legacy; the all-instances view shows the cutover note."""
    snap = await _lifespan_snapshot_with_legacy_search_log(tmp_path)
    assert snap["legacy_by_name"] == {"Old Show S01": True, "Old Show S02": True, "Old Movie": False}
    assert snap["all_view"]["show_cutover_note"] is True


async def test_lifespan_imported_rows_keep_outcomes_and_stay_unassociated(tmp_path):
    """Imported rows keep their stored outcomes and are never associated with a configured instance's stable ID."""
    snap = await _lifespan_snapshot_with_legacy_search_log(tmp_path)
    assert [r["outcome"] for r in snap["rows"]] == ["searched", "searched", "searched"]
    assert all(r["instance_stable_id"] is None for r in snap["rows"])
    assert all(r["instance_id"] == "Default" for r in snap["rows"])
    assert snap["main_view"]["show_cutover_note"] is False
    assert snap["search_log_after"] == []


def _legacy_import_startup(tmp_path):
    """Real lifespan inputs with a legacy state.json search_log; returns (settings, state_path, config_path)."""
    import json

    settings = Settings(
        sonarr={"Main": InstanceConfig(url="http://sonarr:8989", api_key="sonarr-test-key", enabled=True,
                                       id="sid-sonarr-main")},
    )
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"radarr": {}, "sonarr": {}, "lidarr": {}, "search_log": _LEGACY_SEARCH_LOG}))
    return settings, state_path, tmp_path / "triggarr.toml"


async def _run_lifespan(settings, state_path, config_path, probe):
    """Run one real startup/shutdown, calling ``probe(db)`` while the app is up."""
    from triggarr.search.scheduler import create_lifespan

    with patch("triggarr.search.scheduler.AsyncIOScheduler", return_value=_FakeScheduler()):
        lifespan_fn = create_lifespan(settings, state_path, config_path)
        app = FastAPI(lifespan=lifespan_fn)
        async with lifespan_fn(app):
            return await probe(app.state.db)


async def test_lifespan_imported_legacy_rows_stay_out_of_grab_rate_denominators(tmp_path):
    """Frozen legacy Sonarr rows are excluded from grab-rate denominators; unresolved rows still count."""
    from triggarr.db import get_dashboard_stats, insert_search_entry

    settings, state_path, config_path = _legacy_import_startup(tmp_path)

    async def probe(db):
        imported = await get_dashboard_stats(db)
        # A pre-cutover Sonarr row that later resolved as unresolved is no
        # longer frozen, so it counts against the rate.
        await db.execute("UPDATE search_history SET outcome = 'unresolved' WHERE item_name = 'Old Show S01'")
        await db.commit()
        after_unresolved = await get_dashboard_stats(db)
        # A post-cutover Sonarr row counts as usual.
        await insert_search_entry(
            db, "Sonarr", "missing", "New Show S01", outcome="grabbed", item_id=7, instance_id="Main",
            instance_stable_id="sid-sonarr-main",
        )
        return imported, after_unresolved, await get_dashboard_stats(db)

    imported, after_unresolved, after_new = await _run_lifespan(settings, state_path, config_path, probe)
    assert imported["sonarr_rate"] is None
    assert imported["radarr_rate"] == 0.0
    assert imported["overall_rate"] == 0.0
    assert after_unresolved["sonarr_rate"] == 0.0
    assert after_new["sonarr_rate"] == 50.0
    assert after_new["overall_rate"] == pytest.approx(100 / 3)


async def test_lifespan_restart_after_legacy_import_neither_reimports_nor_moves_cutover(tmp_path):
    """A second start finds search_log cleared: no duplicate rows, cutover and legacy rows unchanged."""
    from triggarr.db import get_search_history

    settings, state_path, config_path = _legacy_import_startup(tmp_path)

    async def probe(db):
        async with db.execute("SELECT legacy_max_history_id, any_pre_fix_sonarr_data, cutover_at "
                              "FROM attribution_cutover") as cursor:
            cutover = [dict(r) for r in await cursor.fetchall()]
        async with db.execute("SELECT id, item_name FROM search_history ORDER BY id") as cursor:
            rows = [tuple(r) for r in await cursor.fetchall()]
        history = await get_search_history(db)
        return cutover, rows, {e["name"]: e["is_legacy"] for e in history["entries"]}

    first = await _run_lifespan(settings, state_path, config_path, probe)
    second = await _run_lifespan(settings, state_path, config_path, probe)
    assert len(first[0]) == 1
    assert second == first
    assert [name for _, name in second[1]] == ["Old Show S01", "Old Show S02", "Old Movie"]


# ---------------------------------------------------------------------------
# Phase 89: startup/shutdown resource cleanup (LIFE-01..03)
# ---------------------------------------------------------------------------

_CAP = "triggarr.search.scheduler._CLEANUP_STEP_TIMEOUT"


def _capture_sink(level: str = "WARNING") -> tuple[io.StringIO, int]:
    sink = io.StringIO()
    return sink, logger.add(sink, format="{level} | {message}", level=level)


def _sink_lines(sink: io.StringIO) -> list[str]:
    return [line for line in sink.getvalue().splitlines() if line.strip()]


def test_cleanup_step_timeout_default_is_5s():
    from triggarr.search.scheduler import _CLEANUP_STEP_TIMEOUT

    assert _CLEANUP_STEP_TIMEOUT == 5.0
    assert isinstance(_CLEANUP_STEP_TIMEOUT, float)


async def test_safe_close_returns_true_on_success():
    from triggarr.search.scheduler import _ABANDONED_CLOSE_TASKS, _safe_close

    close_fn = AsyncMock()
    sink, sink_id = _capture_sink("WARNING")
    try:
        result = await _safe_close("Shutdown", "database", close_fn)
    finally:
        logger.remove(sink_id)
    assert result is True
    close_fn.assert_awaited_once()
    assert _sink_lines(sink) == []
    assert len(_ABANDONED_CLOSE_TASKS) == 0


async def test_safe_close_logs_sanitized_warning_and_returns_false_on_exception():
    from triggarr.search.scheduler import _safe_close

    close_fn = AsyncMock(side_effect=AssertionError("in-flight close"))
    sink, sink_id = _capture_sink("WARNING")
    try:
        result = await _safe_close("Shutdown", "Sonarr/'anime' connection", close_fn)
    finally:
        logger.remove(sink_id)
    assert result is False
    lines = _sink_lines(sink)
    warnings = [line for line in lines if line.startswith("WARNING | ")]
    assert warnings == ["WARNING | Shutdown: could not close Sonarr/'anime' connection (AssertionError); continuing"]
    assert "in-flight close" not in sink.getvalue()


async def test_safe_close_never_logs_url_credentials():
    from triggarr.search.scheduler import _safe_close

    exc = httpx.ConnectError("boom", request=httpx.Request("GET", "http://sonarr:8989/api?apikey=SECRET-KEY-123"))
    close_fn = AsyncMock(side_effect=exc)
    sink, sink_id = _capture_sink("WARNING")
    try:
        result = await _safe_close("Shutdown", "Sonarr/'Default' connection", close_fn)
    finally:
        logger.remove(sink_id)
    assert result is False
    output = sink.getvalue()
    assert "SECRET-KEY-123" not in output
    assert "apikey" not in output
    warnings = [line for line in _sink_lines(sink) if line.startswith("WARNING | ")]
    assert len(warnings) == 1
    assert "HTTP error: ConnectError" in warnings[0]


async def test_safe_close_times_out_and_continues():
    from triggarr.search.scheduler import _ABANDONED_CLOSE_TASKS, _safe_close

    async def close_fn():
        await asyncio.Event().wait()

    sink, sink_id = _capture_sink("WARNING")
    try:
        with patch(_CAP, 0.05):
            start = time.monotonic()
            result = await _safe_close("Shutdown", "database", close_fn)
            elapsed = time.monotonic() - start
        await asyncio.sleep(0.05)
        remaining = len(_ABANDONED_CLOSE_TASKS)
    finally:
        logger.remove(sink_id)
    assert result is False
    assert elapsed < 1.0
    assert _sink_lines(sink) == ["WARNING | Shutdown: database did not close within 0.05s; continuing"]
    assert remaining == 0


async def test_safe_close_returns_at_cap_when_close_waits_in_cancellation_finalizer():
    # An `async with asyncio.timeout(cap): await close_fn()` implementation fails this
    # test at "helper task is done": the awaiting task cannot finish while the close
    # keeps waiting in its own cancellation finalizer (aiosqlite's close() does this).
    from triggarr.search.scheduler import _ABANDONED_CLOSE_TASKS, _safe_close

    release = asyncio.Event()
    in_finalizer = asyncio.Event()

    async def close_fn():
        try:
            await asyncio.Event().wait()
        finally:
            in_finalizer.set()
            await release.wait()

    sink, sink_id = _capture_sink("WARNING")
    helper = None
    try:
        with patch(_CAP, 0.05):
            start = time.monotonic()
            helper = asyncio.ensure_future(_safe_close("Shutdown", "database", close_fn))
            await asyncio.wait({helper}, timeout=2.0)
            elapsed = time.monotonic() - start
            helper_done = helper.done()
            result = helper.result() if helper_done and not helper.cancelled() else None
            await asyncio.sleep(0.01)
            finalizer_reached = in_finalizer.is_set()
            abandoned = list(_ABANDONED_CLOSE_TASKS)
            abandoned_pending = [not t.done() for t in abandoned]
            next_result = await _safe_close("Shutdown", "next step", AsyncMock())
        warnings = [line for line in _sink_lines(sink) if line.startswith("WARNING | ")]
        release.set()
        if abandoned:
            await asyncio.wait(abandoned, timeout=2.0)
        after_done = [t.done() for t in abandoned]
        after_len = len(_ABANDONED_CLOSE_TASKS)
    finally:
        release.set()
        if helper is not None and not helper.done():
            helper.cancel()
            await asyncio.wait({helper}, timeout=2.0)
        pending = [t for t in _ABANDONED_CLOSE_TASKS if not t.done()]
        if pending:
            await asyncio.wait(pending, timeout=2.0)
        logger.remove(sink_id)
    assert helper_done, "helper task is done"
    assert result is False
    assert elapsed < 1.0
    assert finalizer_reached
    assert len(abandoned) == 1 and abandoned_pending == [True]
    assert next_result is True
    assert warnings == ["WARNING | Shutdown: database did not close within 0.05s; continuing"]
    assert after_done == [True]
    assert after_len == 0


async def test_safe_close_observes_late_failure_of_abandoned_close():
    import gc

    from triggarr.search.scheduler import _ABANDONED_CLOSE_TASKS, _safe_close

    release = asyncio.Event()

    async def close_fn():
        try:
            await asyncio.Event().wait()
        finally:
            await release.wait()
            raise RuntimeError("late boom http://x/?apikey=SECRET-KEY-123")

    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    contexts: list[dict] = []
    loop.set_exception_handler(lambda _loop, ctx: contexts.append(ctx))
    sink, sink_id = _capture_sink("DEBUG")
    helper = None
    try:
        with patch(_CAP, 0.05):
            helper = asyncio.ensure_future(_safe_close("Shutdown", "database", close_fn))
            await asyncio.wait({helper}, timeout=2.0)
        abandoned = list(_ABANDONED_CLOSE_TASKS)
        release.set()
        if abandoned:
            await asyncio.wait(abandoned, timeout=2.0)
        await asyncio.sleep(0.01)
        remaining = len(_ABANDONED_CLOSE_TASKS)
        del abandoned
        helper = None
        gc.collect()
        await asyncio.sleep(0)
        output = sink.getvalue()
        lines = _sink_lines(sink)
    finally:
        release.set()
        loop.set_exception_handler(previous_handler)
        logger.remove(sink_id)
    assert remaining == 0
    assert [line for line in lines if line.startswith("WARNING | ")] == [
        "WARNING | Shutdown: database did not close within 0.05s; continuing"
    ]
    assert "late boom" not in output
    assert "SECRET-KEY-123" not in output
    assert [line for line in lines if line.startswith("DEBUG | ")] == [
        "DEBUG | Shutdown: abandoned close of database ended after the cap (RuntimeError)"
    ]
    assert not any("never retrieved" in str(c.get("message", "")) for c in contexts), contexts


async def test_safe_close_retrieves_close_failure_when_caller_is_cancelled():
    # An implementation that attaches its result observer only `if not task.done()` in
    # the `finally:` fails this test at the "never retrieved" assertion: the context
    # message "Task exception was never retrieved" carries the raw RuntimeError text
    # (probe on Python 3.11.14, 2026-11-18).
    import gc

    from triggarr.search.scheduler import _ABANDONED_CLOSE_TASKS, _safe_close

    gate = asyncio.Event()
    parked = asyncio.Event()

    async def close_fn():
        parked.set()
        await gate.wait()
        raise RuntimeError("boom http://x/?apikey=SECRET-KEY-123")

    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    contexts: list[dict] = []
    loop.set_exception_handler(lambda _loop, ctx: contexts.append(ctx))
    sink, sink_id = _capture_sink("DEBUG")
    cancelled = False
    try:
        helper = asyncio.ensure_future(_safe_close("Shutdown", "database", close_fn))
        await parked.wait()
        gate.set()
        helper.cancel()
        try:
            await helper
        except asyncio.CancelledError:
            cancelled = True
        del helper
        for _ in range(2):
            gc.collect()
            await asyncio.sleep(0)
        output = sink.getvalue()
        lines = _sink_lines(sink)
        remaining = len(_ABANDONED_CLOSE_TASKS)
    finally:
        gate.set()
        loop.set_exception_handler(previous_handler)
        logger.remove(sink_id)
    assert cancelled is True
    assert not any("never retrieved" in str(c.get("message", "")) for c in contexts), contexts
    for secret in ("SECRET-KEY-123", "apikey", "boom"):
        assert secret not in output
        assert not any(secret in repr(c) for c in contexts)
    assert [line for line in lines if line.startswith("WARNING | ")] == [
        "WARNING | Shutdown: could not close database (RuntimeError); continuing"
    ]
    assert remaining == 0


async def test_safe_close_returns_at_cap_on_wedged_real_aiosqlite_close(tmp_path):
    from triggarr.search.scheduler import _ABANDONED_CLOSE_TASKS, _safe_close

    conn = await aiosqlite.connect(tmp_path / "wedge.db")
    gate = threading.Event()
    wedge = asyncio.ensure_future(conn._execute(gate.wait))
    helper = None
    sink, sink_id = _capture_sink("WARNING")
    try:
        await asyncio.sleep(0.05)
        with patch(_CAP, 0.2):
            start = time.monotonic()
            helper = asyncio.ensure_future(_safe_close("Shutdown", "database", conn.close))
            await asyncio.wait({helper}, timeout=3.0)
            elapsed = time.monotonic() - start
        helper_done = helper.done()
        result = helper.result() if helper_done and not helper.cancelled() else None
        warnings = [line for line in _sink_lines(sink) if line.startswith("WARNING | ")]
        thread_alive_wedged = conn._thread.is_alive()
        abandoned = list(_ABANDONED_CLOSE_TASKS)
        gate.set()
        await asyncio.wait({wedge}, timeout=3.0)
        if abandoned:
            await asyncio.wait(abandoned, timeout=3.0)
        await asyncio.to_thread(conn._thread.join, 2.0)
        thread_alive_after = conn._thread.is_alive()
        remaining = len(_ABANDONED_CLOSE_TASKS)
    finally:
        gate.set()
        await asyncio.wait({wedge}, timeout=3.0)
        pending = [t for t in _ABANDONED_CLOSE_TASKS if not t.done()]
        if pending:
            await asyncio.wait(pending, timeout=3.0)
        if conn._thread.is_alive():
            closer = asyncio.ensure_future(aiosqlite.Connection.close(conn))
            await asyncio.wait({closer}, timeout=3.0)
            await asyncio.to_thread(conn._thread.join, 2.0)
        logger.remove(sink_id)
    assert helper_done
    assert result is False
    assert elapsed < 1.5
    assert len(warnings) == 1 and "database" in warnings[0]
    assert thread_alive_wedged is True
    assert thread_alive_after is False
    assert remaining == 0


def test_safe_stop_scheduler_logs_warning_when_shutdown_raises():
    from triggarr.search.scheduler import _safe_stop_scheduler

    class _Boom(_FakeScheduler):
        def shutdown(self, wait: bool = True) -> None:
            raise RuntimeError("scheduler boom")

    ok = _FakeScheduler()
    sink, sink_id = _capture_sink("WARNING")
    try:
        result = _safe_stop_scheduler("Shutdown", _Boom())
        ok_result = _safe_stop_scheduler("Shutdown", ok)
    finally:
        logger.remove(sink_id)
    assert result is False
    assert _sink_lines(sink) == ["WARNING | Shutdown: could not stop the scheduler (RuntimeError); continuing"]
    assert ok_result is True
    assert ok.shutdown_wait is False


def _spy_connect(captured: list, hook=None):
    """Return a stand-in for aiosqlite.connect that records every Connection it opens."""
    real_connect = aiosqlite.connect

    def spy(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        if hook is not None:
            hook(conn)
        captured.append(conn)
        return conn

    return spy


@dataclass
class _LifespanObservation:
    exc: BaseException | None
    reached_yield: bool
    exit_timed_out: bool
    elapsed: float
    scheduler_running: bool
    scheduler_shutdown_wait: bool | None
    clients_closed: list[bool] = field(default_factory=list)
    worker_alive: list[bool] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    rescue_errors: list[str] = field(default_factory=list)


async def _observe_lifespan(
    settings,
    tmp_path,
    scheduler,
    *,
    body=None,
    tracked=None,
    gates=(),
    connect_hook=None,
    log_level="INFO",
    deadline=10.0,
) -> _LifespanObservation:
    """Drive the lifespan, observe its end state, then rescue every resource.

    Stages are strictly ordered: DRIVE (owned task under a deadline), OBSERVE
    (no assertions, nothing raises), RESCUE (unconditional, exception-safe).
    Tests assert only against the returned observation.
    """
    from triggarr.search.scheduler import _ABANDONED_CLOSE_TASKS, create_lifespan

    tracked = tracked if tracked is not None else []
    captured: list = []
    rescue_errors: list[str] = []
    sink, sink_id = _capture_sink(log_level)
    reached = [False]
    task = None
    obs = None
    with contextlib.ExitStack() as stack:
        try:
            stack.enter_context(
                patch("triggarr.search.scheduler.aiosqlite.connect", side_effect=_spy_connect(captured, connect_hook))
            )
            stack.enter_context(patch("triggarr.search.scheduler.AsyncIOScheduler", return_value=scheduler))
            lifespan_fn = create_lifespan(settings, tmp_path / "state.json", tmp_path / "triggarr.toml")
            app = FastAPI(lifespan=lifespan_fn)

            async def drive():
                async with lifespan_fn(app):
                    reached[0] = True
                    if body is not None:
                        await body(app)

            start = time.monotonic()
            task = asyncio.ensure_future(drive())
            await asyncio.wait({task}, timeout=deadline)
            elapsed = time.monotonic() - start
            exit_timed_out = not task.done()
            exc: BaseException | None = None
            if task.done():
                exc = asyncio.CancelledError() if task.cancelled() else task.exception()

            scheduler_running = bool(getattr(scheduler, "running", False))
            scheduler_shutdown_wait = getattr(scheduler, "shutdown_wait", None)
            clients_closed: list[bool] = []
            for client in tracked:
                try:
                    clients_closed.append(bool(client._client.is_closed))
                except Exception as err:
                    rescue_errors.append(type(err).__name__)
                    clients_closed.append(False)
            worker_alive: list[bool] = []
            for conn in captured:
                try:
                    thread = conn._thread
                    if thread.ident is not None:
                        await asyncio.to_thread(thread.join, 2.0)
                    worker_alive.append(thread.is_alive())
                except Exception as err:
                    rescue_errors.append(type(err).__name__)
                    worker_alive.append(False)
            lines = _sink_lines(sink)
            obs = _LifespanObservation(
                exc=exc,
                reached_yield=reached[0],
                exit_timed_out=exit_timed_out,
                elapsed=elapsed,
                scheduler_running=scheduler_running,
                scheduler_shutdown_wait=scheduler_shutdown_wait,
                clients_closed=clients_closed,
                worker_alive=worker_alive,
                lines=lines,
                rescue_errors=rescue_errors,
            )
        finally:
            for gate in gates:
                with contextlib.suppress(Exception):
                    gate.set()
            try:
                if task is not None and not task.done():
                    await asyncio.wait({task}, timeout=5.0)
                    if not task.done():
                        task.cancel()
                        await asyncio.wait({task}, timeout=2.0)
            except Exception as err:
                rescue_errors.append(type(err).__name__)
            try:
                if getattr(scheduler, "running", False):
                    scheduler.shutdown(wait=False)
                    await asyncio.sleep(0)
            except Exception as err:
                rescue_errors.append(type(err).__name__)
            for client in tracked:
                try:
                    await client._client.aclose()
                except Exception as err:
                    rescue_errors.append(type(err).__name__)
            for conn in captured:
                try:
                    if conn._thread.is_alive():
                        closer = asyncio.ensure_future(aiosqlite.Connection.close(conn))
                        await asyncio.wait({closer}, timeout=2.0)
                        await asyncio.to_thread(conn._thread.join, 2.0)
                except Exception as err:
                    rescue_errors.append(type(err).__name__)
            try:
                pending = [t for t in _ABANDONED_CLOSE_TASKS if not t.done()]
                if pending:
                    await asyncio.wait(pending, timeout=2.0)
            except Exception as err:
                rescue_errors.append(type(err).__name__)
            logger.remove(sink_id)
    assert obs is not None
    obs.rescue_errors = rescue_errors
    return obs


def _track_all_clients(app, tracked: list) -> dict:
    clients = {
        "radarr": app.state.radarr_clients["Default"],
        "sonarr": app.state.sonarr_clients["Default"],
        "lidarr": app.state.lidarr_clients["Default"],
    }
    tracked.extend(clients.values())
    return clients


async def test_shutdown_continues_when_client_close_fails(tmp_path):
    tracked: list = []

    async def body(app):
        clients = _track_all_clients(app, tracked)
        clients["radarr"].close = AsyncMock(side_effect=AssertionError("in-flight close"))

    obs = await _observe_lifespan(make_settings(), tmp_path, _FakeScheduler(), body=body, tracked=tracked)
    assert obs.exc is None, f"lifespan exit raised {obs.exc!r}"
    assert obs.exit_timed_out is False
    assert obs.scheduler_shutdown_wait is False
    assert obs.clients_closed == [False, True, True]
    assert obs.worker_alive == [False]
    warning = "WARNING | Shutdown: could not close Radarr/'Default' connection (AssertionError); continuing"
    assert [line for line in obs.lines if line.startswith("WARNING | Shutdown:")] == [warning]
    assert not any("in-flight close" in line for line in obs.lines)
    stopped = "INFO | Search engine stopped"
    assert stopped in obs.lines
    assert obs.lines.index(stopped) > obs.lines.index(warning)
    assert not any(line.startswith("ERROR | ") for line in obs.lines)
    assert obs.rescue_errors == []


async def test_shutdown_continues_when_db_close_fails(tmp_path):
    settings = make_settings(radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False)

    async def body(app):
        app.state.db.close = AsyncMock(side_effect=OSError(5, "Input/output error"))

    obs = await _observe_lifespan(settings, tmp_path, _FakeScheduler(), body=body)
    assert obs.exc is None, f"lifespan exit raised {obs.exc!r}"
    warnings = [line for line in obs.lines if line.startswith("WARNING | Shutdown:")]
    assert warnings == ["WARNING | Shutdown: could not close database (OSError); continuing"]
    assert not any("Input/output error" in line for line in obs.lines)
    assert obs.lines[-1] == "INFO | Search engine stopped"
    assert not any(line.startswith("ERROR | ") for line in obs.lines)
    assert obs.rescue_errors == []


async def test_shutdown_abandons_hung_client_close_after_cap(tmp_path):
    tracked: list = []
    hang = asyncio.Event()
    release = asyncio.Event()

    async def hung_close():
        try:
            await hang.wait()
        finally:
            await release.wait()

    async def body(app):
        clients = _track_all_clients(app, tracked)
        clients["sonarr"].close = hung_close

    with patch(_CAP, 0.05):
        obs = await _observe_lifespan(
            make_settings(), tmp_path, _FakeScheduler(), body=body, tracked=tracked, gates=(hang, release), deadline=2.0
        )
    assert obs.exit_timed_out is False, "lifespan exit did not finish within the deadline"
    assert obs.exc is None
    assert obs.elapsed < 2.0
    assert obs.clients_closed == [True, False, True]
    assert obs.worker_alive == [False]
    warnings = [line for line in obs.lines if line.startswith("WARNING | Shutdown:")]
    assert warnings == ["WARNING | Shutdown: Sonarr/'Default' connection did not close within 0.05s; continuing"]
    assert "INFO | Search engine stopped" in obs.lines
    assert obs.rescue_errors == []


async def test_shutdown_order_is_unchanged(tmp_path):
    order: list[str] = []

    class _OrderScheduler(_FakeScheduler):
        def shutdown(self, wait: bool = True) -> None:
            order.append("scheduler")
            super().shutdown(wait)

    tracked: list = []

    def recording(name: str, real_close):
        async def close():
            order.append(name)
            await real_close()

        return close

    async def body(app):
        clients = _track_all_clients(app, tracked)
        for app_type, client in clients.items():
            client.close = recording(app_type, client.close)
        app.state.db.close = recording("db", app.state.db.close)

    obs = await _observe_lifespan(make_settings(), tmp_path, _OrderScheduler(), body=body, tracked=tracked)
    assert obs.exc is None
    assert order == ["scheduler", "radarr", "sonarr", "lidarr", "db"]
    assert obs.rescue_errors == []


# ---------------------------------------------------------------------------
# Failed startup: release everything opened so far (LIFE-01, LIFE-03)
# ---------------------------------------------------------------------------

_CAUSE = "ERROR | Startup failed (RuntimeError); closing what was opened"


def _summary(text: str) -> str:
    return f"ERROR | Startup failed; closed {text} before exiting"


def _recording_factory(cls, record: list, fail_on_call: int | None = None, after_build=None):
    """Build a client constructor stand-in that records instances and can fail on the Nth call."""
    calls = [0]

    def factory(**kwargs):
        calls[0] += 1
        if fail_on_call is not None and calls[0] == fail_on_call:
            raise RuntimeError("simulated client construction failure")
        instance = cls(**kwargs)
        if after_build is not None:
            after_build(instance)
        record.append(instance)
        return instance

    return factory


class _FailingStartScheduler(_FakeScheduler):
    """start() fails before the scheduler ever reaches the running state."""

    def start(self) -> None:
        raise RuntimeError("simulated scheduler start failure")


def _failed_startup_lines(obs: _LifespanObservation) -> list[str]:
    assert _CAUSE in obs.lines, obs.lines
    return obs.lines[obs.lines.index(_CAUSE):]


def _common_failed_startup_asserts(obs: _LifespanObservation) -> None:
    assert obs.reached_yield is False
    assert obs.exit_timed_out is False


async def test_startup_failure_init_db_closes_database_and_reraises(tmp_path):
    injected = RuntimeError("simulated upgrade failure")
    fake = _FakeScheduler()
    with patch("triggarr.search.scheduler.init_db", new=AsyncMock(side_effect=injected)):
        obs = await _observe_lifespan(make_settings(), tmp_path, fake, log_level="WARNING")
    assert obs.exc is injected
    _common_failed_startup_asserts(obs)
    assert obs.worker_alive == [False]
    assert _failed_startup_lines(obs) == [_CAUSE, _summary("the database and 0 connection(s)")]
    assert not any("simulated upgrade failure" in line for line in obs.lines)
    assert fake.started is False
    assert obs.scheduler_shutdown_wait is None
    assert obs.rescue_errors == []


async def test_startup_failure_cutover_closes_database(tmp_path):
    tracked: list = []
    settings = make_settings(sonarr_enabled=False, lidarr_enabled=False)
    with (
        patch(
            "triggarr.search.scheduler.ensure_cutover_recorded",
            new=AsyncMock(side_effect=RuntimeError("simulated cutover failure")),
        ),
        patch("triggarr.search.scheduler.RadarrClient", side_effect=_recording_factory(RadarrClient, tracked)),
    ):
        obs = await _observe_lifespan(settings, tmp_path, _FakeScheduler(), tracked=tracked, log_level="WARNING")
    assert type(obs.exc) is RuntimeError
    assert str(obs.exc) == "simulated cutover failure"
    _common_failed_startup_asserts(obs)
    assert tracked == []
    assert obs.worker_alive == [False]
    assert _failed_startup_lines(obs) == [_CAUSE, _summary("the database and 0 connection(s)")]
    assert obs.scheduler_shutdown_wait is None
    assert obs.rescue_errors == []


async def test_startup_failure_client_construction_closes_earlier_clients(tmp_path):
    from triggarr.clients.sonarr import SonarrClient

    tracked: list = []
    settings = Settings(
        radarr={"Default": InstanceConfig(url="http://radarr:7878", api_key="radarr-test-key", enabled=True)},
        sonarr={
            "First": InstanceConfig(url="http://sonarr:8989", api_key="sonarr-test-key", enabled=True),
            "Second": InstanceConfig(url="http://sonarr2:8989", api_key="sonarr-test-key-2", enabled=True),
        },
    )
    with (
        patch("triggarr.search.scheduler.RadarrClient", side_effect=_recording_factory(RadarrClient, tracked)),
        patch(
            "triggarr.search.scheduler.SonarrClient",
            side_effect=_recording_factory(SonarrClient, tracked, fail_on_call=2),
        ),
    ):
        obs = await _observe_lifespan(settings, tmp_path, _FakeScheduler(), tracked=tracked, log_level="WARNING")
    assert type(obs.exc) is RuntimeError
    assert str(obs.exc) == "simulated client construction failure"
    _common_failed_startup_asserts(obs)
    assert obs.clients_closed == [True, True]
    assert obs.worker_alive == [False]
    assert _failed_startup_lines(obs) == [_CAUSE, _summary("the database and 2 connection(s)")]
    assert obs.scheduler_shutdown_wait is None
    assert obs.rescue_errors == []


async def test_startup_failure_scheduler_not_started_no_shutdown_call(tmp_path):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.schedulers.base import STATE_STOPPED

    real = AsyncIOScheduler()
    settings = make_settings(radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False)
    injected = RuntimeError("simulated upgrade failure")
    with patch("triggarr.search.scheduler.init_db", new=AsyncMock(side_effect=injected)):
        obs = await _observe_lifespan(settings, tmp_path, real, log_level="WARNING")
    assert obs.exc is injected
    _common_failed_startup_asserts(obs)
    assert obs.worker_alive == [False]
    assert obs.scheduler_running is False
    assert real.state == STATE_STOPPED
    assert not any("SchedulerNotRunningError" in line for line in obs.lines)
    assert not any(line.startswith("WARNING | Startup") for line in obs.lines)
    assert obs.rescue_errors == []


async def test_startup_failure_cleanup_also_fails_still_raises_original(tmp_path):
    from triggarr.clients.sonarr import SonarrClient

    tracked: list = []
    fake = _FailingStartScheduler()
    settings = make_settings(lidarr_enabled=False)
    with (
        patch(
            "triggarr.search.scheduler.RadarrClient",
            side_effect=_recording_factory(
                RadarrClient,
                tracked,
                after_build=lambda c: setattr(c, "close", AsyncMock(side_effect=AssertionError("close boom"))),
            ),
        ),
        patch("triggarr.search.scheduler.SonarrClient", side_effect=_recording_factory(SonarrClient, tracked)),
    ):
        obs = await _observe_lifespan(settings, tmp_path, fake, tracked=tracked, log_level="WARNING")
    assert type(obs.exc) is RuntimeError
    assert str(obs.exc) == "simulated scheduler start failure"
    _common_failed_startup_asserts(obs)
    assert obs.clients_closed == [False, True]
    assert obs.worker_alive == [False]
    assert _failed_startup_lines(obs) == [
        _CAUSE,
        "WARNING | Startup cleanup: could not close Radarr/'Default' connection (AssertionError); continuing",
        _summary("the database and 1 connection(s)"),
    ]
    assert not any("close boom" in line or "simulated scheduler start failure" in line for line in obs.lines)
    assert obs.scheduler_shutdown_wait is None
    assert obs.rescue_errors == []


async def test_startup_failure_cleanup_also_fails_on_db_close(tmp_path):
    settings = make_settings(radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False)
    with patch(
        "triggarr.search.scheduler.ensure_cutover_recorded",
        new=AsyncMock(side_effect=RuntimeError("simulated cutover failure")),
    ):
        obs = await _observe_lifespan(
            settings,
            tmp_path,
            _FakeScheduler(),
            connect_hook=lambda conn: setattr(conn, "close", AsyncMock(side_effect=OSError(5, "Input/output error"))),
            log_level="WARNING",
        )
    assert type(obs.exc) is RuntimeError
    _common_failed_startup_asserts(obs)
    assert _CAUSE in obs.lines
    assert _failed_startup_lines(obs) == [
        _CAUSE,
        "WARNING | Startup cleanup: could not close database (OSError); continuing",
        _summary("0 connection(s)"),
    ]
    assert not any("Input/output error" in line for line in obs.lines)
    assert obs.rescue_errors == []


async def test_startup_failure_cause_line_never_logs_credentials(tmp_path):
    settings = make_settings(radarr_enabled=False, sonarr_enabled=False, lidarr_enabled=False)
    leaking = httpx.ConnectError(
        "boom", request=httpx.Request("GET", "http://sonarr:8989/api?apikey=SECRET-KEY-123")
    )
    with patch("triggarr.search.scheduler.init_db", new=AsyncMock(side_effect=leaking)):
        obs = await _observe_lifespan(settings, tmp_path, _FakeScheduler(), log_level="WARNING")
    assert obs.exc is leaking
    _common_failed_startup_asserts(obs)
    assert obs.worker_alive == [False]
    cause = "ERROR | Startup failed (HTTP error: ConnectError); closing what was opened"
    assert cause in obs.lines
    assert obs.lines[obs.lines.index(cause):] == [cause, _summary("the database and 0 connection(s)")]
    assert not any("SECRET-KEY-123" in line or "apikey" in line for line in obs.lines)
    assert obs.rescue_errors == []


async def test_startup_failure_scheduler_started_shuts_scheduler_down(tmp_path):
    class _FailingUpdateCheckScheduler(_FakeScheduler):
        def add_job(self, *args, **kwargs) -> None:
            if kwargs.get("id") == "update_check":
                raise RuntimeError("simulated add_job failure")
            super().add_job(*args, **kwargs)

    tracked: list = []
    fake = _FailingUpdateCheckScheduler()
    settings = make_settings(sonarr_enabled=False, lidarr_enabled=False)
    with patch("triggarr.search.scheduler.RadarrClient", side_effect=_recording_factory(RadarrClient, tracked)):
        obs = await _observe_lifespan(settings, tmp_path, fake, tracked=tracked, log_level="WARNING")
    assert type(obs.exc) is RuntimeError
    assert str(obs.exc) == "simulated add_job failure"
    _common_failed_startup_asserts(obs)
    assert obs.clients_closed == [True]
    assert obs.worker_alive == [False]
    assert fake.started is True
    assert obs.scheduler_shutdown_wait is False
    assert obs.scheduler_running is False
    assert _failed_startup_lines(obs) == [_CAUSE, _summary("the scheduler, the database and 1 connection(s)")]
    assert len([j for j in fake.jobs if j[1].get("id") == "radarr_Default_search"]) == 1
    assert obs.rescue_errors == []


async def test_startup_failure_partial_scheduler_start_is_stopped(tmp_path):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.schedulers.base import STATE_STOPPED

    class _PartialStartScheduler(AsyncIOScheduler):
        # BaseScheduler.start() sets STATE_RUNNING and only then calls wakeup(),
        # so start() raises with the scheduler already running. A flag set only
        # after start() returns would miss this case.
        def __init__(self) -> None:
            super().__init__()
            self.injected = RuntimeError("simulated wakeup failure")

        def wakeup(self) -> None:
            raise self.injected

    tracked: list = []
    real = _PartialStartScheduler()
    settings = make_settings(sonarr_enabled=False, lidarr_enabled=False)
    with patch("triggarr.search.scheduler.RadarrClient", side_effect=_recording_factory(RadarrClient, tracked)):
        obs = await _observe_lifespan(settings, tmp_path, real, tracked=tracked, log_level="WARNING")
    assert obs.exc is real.injected
    _common_failed_startup_asserts(obs)
    assert obs.clients_closed == [True]
    assert obs.worker_alive == [False]
    assert obs.scheduler_running is False
    assert real.state == STATE_STOPPED
    assert _failed_startup_lines(obs) == [_CAUSE, _summary("the scheduler, the database and 1 connection(s)")]
    assert not any("SchedulerNotRunningError" in line for line in obs.lines)
    assert obs.rescue_errors == []


async def test_startup_failure_scheduler_start_raises_no_shutdown_call(tmp_path):
    tracked: list = []
    fake = _FailingStartScheduler()
    settings = make_settings(sonarr_enabled=False, lidarr_enabled=False)
    with patch("triggarr.search.scheduler.RadarrClient", side_effect=_recording_factory(RadarrClient, tracked)):
        obs = await _observe_lifespan(settings, tmp_path, fake, tracked=tracked, log_level="WARNING")
    assert type(obs.exc) is RuntimeError
    _common_failed_startup_asserts(obs)
    assert fake.started is False
    assert obs.scheduler_shutdown_wait is None
    assert obs.clients_closed == [True]
    assert obs.worker_alive == [False]
    assert _failed_startup_lines(obs) == [_CAUSE, _summary("the database and 1 connection(s)")]
    assert obs.rescue_errors == []


async def test_stop_scheduler_if_running_reports_a_scheduler_that_stays_running():
    from triggarr.search.scheduler import _stop_scheduler_if_running

    class _StuckScheduler(_FakeScheduler):
        started = True

        @property
        def running(self) -> bool:
            return True

    sink, sink_id = _capture_sink("WARNING")
    try:
        stuck = _StuckScheduler()
        assert await _stop_scheduler_if_running("Startup cleanup", stuck) is False
        assert stuck.shutdown_wait is False
        assert _sink_lines(sink) == ["WARNING | Startup cleanup: the scheduler did not stop; continuing"]

        sink.truncate(0)
        sink.seek(0)
        started = _FakeScheduler()
        started.started = True
        assert await _stop_scheduler_if_running("Startup cleanup", started) is True
        assert _sink_lines(sink) == []

        never = _FakeScheduler()
        assert await _stop_scheduler_if_running("Startup cleanup", never) is False
        assert never.shutdown_wait is None
        assert _sink_lines(sink) == []
    finally:
        logger.remove(sink_id)


# ---------------------------------------------------------------------------
# Failed startup by cancellation or interrupt (Phase 89 review WR-01)
# ---------------------------------------------------------------------------


class _StartupInterrupt(BaseException):
    """A non-Exception interrupt that, unlike KeyboardInterrupt/SystemExit, asyncio
    stores on the task instead of re-raising out of the event loop."""


async def test_startup_cancelled_during_init_db_still_closes_database(tmp_path):
    async def cancelled_init_db(*args, **kwargs):
        # Cancel the lifespan's own task while it awaits this upgrade step, as an
        # outer timeout or a harness tearing the app down would.
        asyncio.current_task().cancel()
        await asyncio.sleep(10)

    fake = _FakeScheduler()
    with patch("triggarr.search.scheduler.init_db", new=cancelled_init_db):
        obs = await _observe_lifespan(make_settings(), tmp_path, fake, log_level="WARNING")
    assert isinstance(obs.exc, asyncio.CancelledError)
    _common_failed_startup_asserts(obs)
    assert obs.worker_alive == [False]
    cause = "ERROR | Startup interrupted (CancelledError); closing what was opened"
    assert cause in obs.lines, obs.lines
    assert obs.lines[obs.lines.index(cause):] == [
        cause,
        "ERROR | Startup interrupted; closed the database and 0 connection(s) before exiting",
    ]
    assert fake.started is False
    assert obs.rescue_errors == []


async def test_startup_interrupt_during_client_construction_closes_earlier_clients(tmp_path):
    from triggarr.clients.sonarr import SonarrClient

    tracked: list = []
    calls = [0]

    def interrupting_sonarr(**kwargs):
        calls[0] += 1
        if calls[0] == 2:
            raise _StartupInterrupt()
        instance = SonarrClient(**kwargs)
        tracked.append(instance)
        return instance

    settings = Settings(
        radarr={"Default": InstanceConfig(url="http://radarr:7878", api_key="radarr-test-key", enabled=True)},
        sonarr={
            "First": InstanceConfig(url="http://sonarr:8989", api_key="sonarr-test-key", enabled=True),
            "Second": InstanceConfig(url="http://sonarr2:8989", api_key="sonarr-test-key-2", enabled=True),
        },
    )
    with (
        patch("triggarr.search.scheduler.RadarrClient", side_effect=_recording_factory(RadarrClient, tracked)),
        patch("triggarr.search.scheduler.SonarrClient", side_effect=interrupting_sonarr),
    ):
        obs = await _observe_lifespan(settings, tmp_path, _FakeScheduler(), tracked=tracked, log_level="WARNING")
    assert type(obs.exc) is _StartupInterrupt
    _common_failed_startup_asserts(obs)
    assert obs.clients_closed == [True, True]
    assert obs.worker_alive == [False]
    cause = "ERROR | Startup interrupted (_StartupInterrupt); closing what was opened"
    assert cause in obs.lines, obs.lines
    assert obs.lines[obs.lines.index(cause):] == [
        cause,
        "ERROR | Startup interrupted; closed the database and 2 connection(s) before exiting",
    ]
    assert obs.rescue_errors == []


async def test_startup_cleanup_cancelled_midway_still_closes_remaining_steps_database_last(tmp_path):
    from triggarr.clients.sonarr import SonarrClient

    owner: list[asyncio.Task] = []
    order: list[str] = []

    class _OwnerRecordingFailingStart(_FailingStartScheduler):
        def start(self) -> None:
            owner.append(asyncio.current_task())
            super().start()

    def recording(name: str, real_close, cancel_owner: bool = False):
        async def close():
            order.append(name)
            await real_close()
            if cancel_owner:
                # A cancellation of the lifespan arrives while cleanup is
                # waiting on this close.
                owner[0].cancel()
                await asyncio.sleep(0)

        return close

    tracked: list = []
    settings = make_settings(lidarr_enabled=False)
    with (
        patch(
            "triggarr.search.scheduler.RadarrClient",
            side_effect=_recording_factory(
                RadarrClient, tracked, after_build=lambda c: setattr(c, "close", recording("radarr", c.close))
            ),
        ),
        patch(
            "triggarr.search.scheduler.SonarrClient",
            side_effect=_recording_factory(
                SonarrClient,
                tracked,
                after_build=lambda c: setattr(c, "close", recording("sonarr", c.close, cancel_owner=True)),
            ),
        ),
    ):
        obs = await _observe_lifespan(
            settings,
            tmp_path,
            _OwnerRecordingFailingStart(),
            tracked=tracked,
            connect_hook=lambda conn: setattr(conn, "close", recording("db", conn.close)),
            log_level="WARNING",
        )
    # Cleanup closes clients newest first, then the database.
    assert order == ["sonarr", "radarr", "db"]
    assert isinstance(obs.exc, asyncio.CancelledError)
    _common_failed_startup_asserts(obs)
    assert obs.clients_closed == [True, True]
    assert obs.worker_alive == [False]
    assert _failed_startup_lines(obs) == [
        _CAUSE,
        "WARNING | Startup cleanup: closing Sonarr/'Default' connection was interrupted by cancellation; continuing",
        _summary("the database and 1 connection(s)"),
    ]
    assert not any("simulated scheduler start failure" in line for line in obs.lines)
    assert obs.rescue_errors == []
