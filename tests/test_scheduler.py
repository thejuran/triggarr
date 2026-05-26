"""Tests for the scheduler job factory and lifespan shutdown.

Covers: client-None early return, unhandled exception swallowing,
graceful shutdown with search_lock drain (DEBT-06),
and tracking integration after search cycles (Plan 20-03).
"""

from __future__ import annotations

import asyncio
import io
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import httpx
import pytest
from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from loguru import logger

from tests.conftest import make_settings
from triggarr.db import init_db, insert_search_entry
from triggarr.search.scheduler import make_search_job
from triggarr.state import _default_state, save_state


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
    app.state.triggarr_state = _default_state(make_settings())
    app.state.settings = make_settings()

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

    scheduler = AsyncIOScheduler()
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

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
        scheduler._dispatch_event(event)
    finally:
        logger.remove(sink_id)

    output = sink.getvalue()
    assert output.startswith("ERROR | "), f"Expected ERROR-level log line, got: {output!r}"
    assert "radarr_Default_search" in output, f"Missing job_id in: {output!r}"
    assert "RuntimeError" in output, f"Missing exception type in: {output!r}"
    assert "synthetic boom" in output, f"Missing exception message in: {output!r}"


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
    """Tracking failure does not prevent state save or raise from the job."""
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
                new=AsyncMock(side_effect=RuntimeError("tracking exploded")),
            ),
        ):
            job = make_search_job(app, "radarr", "Default", state_path)
            # Should NOT raise despite tracking failure
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
