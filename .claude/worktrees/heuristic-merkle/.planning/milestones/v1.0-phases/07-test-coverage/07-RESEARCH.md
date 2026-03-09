# Phase 7: Test Coverage - Research

**Researched:** 2026-02-24
**Domain:** Async Python testing -- httpx mocking, pytest-asyncio patterns, coverage of retry/pagination/scheduler code paths
**Confidence:** HIGH

## Summary

Phase 7 adds test coverage for async code paths that the existing 92-test suite does not exercise: the `ArrClient` base methods (`_request_with_retry`, `get_paginated`, `validate_connection`), the search cycle orchestrators (`run_radarr_cycle`, `run_sonarr_cycle`), the scheduler job factory (`make_search_job`), and the startup utility `collect_secrets`.

The existing test suite already covers pure functions (filtering, slicing, deduplication, search log), configuration, state persistence, middleware, validation helpers, logging redaction, web routes, and localhost URL detection. What remains are the async methods that make HTTP calls and compose those pure functions -- these require mocking the httpx transport layer or the client methods themselves.

httpx 0.28.1 ships with `MockTransport` (inherits both `AsyncBaseTransport` and `BaseTransport`), which is the cleanest approach for testing `_request_with_retry`, `get_paginated`, and `validate_connection` because it intercepts at the transport layer without monkeypatching. For higher-level cycle and scheduler tests, `unittest.mock.AsyncMock` patching of client methods is the right tool since we want to test the orchestration logic, not re-test HTTP plumbing.

**Primary recommendation:** Use httpx `MockTransport` for `ArrClient` base method tests and `unittest.mock.AsyncMock` for cycle/scheduler tests. No new dependencies required.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| QUAL-07 | All async code paths (clients, cycles, scheduler, startup) have test coverage | All six success criteria map to specific functions; testing approach uses built-in httpx MockTransport + stdlib AsyncMock -- no new deps needed |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 | Test runner | Already installed; `asyncio_mode = "auto"` configured in pyproject.toml |
| pytest-asyncio | 1.3.0 | Async test support | Already installed; auto mode means no `@pytest.mark.asyncio` annotations needed |
| httpx.MockTransport | 0.28.1 (built-in) | Transport-layer mocking for httpx.AsyncClient | Ships with httpx; no extra dependency; supports both sync and async handlers |
| unittest.mock (AsyncMock, patch, MagicMock) | stdlib | Higher-level mocking for client methods and app.state | Python 3.12 stdlib; AsyncMock handles async methods natively |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| io.StringIO | stdlib | Capture loguru output for assertion | Already used in test_startup.py and test_logging.py; use for tests that verify logging side effects |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx.MockTransport | respx (third-party) | respx adds a dependency for routing-style mocks; MockTransport is simpler for this project's needs and already available |
| httpx.MockTransport | pytest-httpx (third-party) | Adds fixture-based mocking; not worth the dependency when MockTransport + manual fixture covers all cases |
| AsyncMock patches | Full integration tests with real httpx + MockTransport | Integration tests for cycles would be brittle (must mock pagination responses); patching client methods is cleaner for cycle logic |

**Installation:**
```bash
# No new packages needed -- all tools are already installed or stdlib
```

## Architecture Patterns

### Recommended Test File Structure
```
tests/
├── test_clients.py        # EXISTING: header/subclass tests
│                           # ADD: _request_with_retry, get_paginated, validate_connection
├── test_search.py         # EXISTING: pure function tests
│                           # ADD: run_radarr_cycle, run_sonarr_cycle async tests
├── test_startup.py        # EXISTING: localhost URL detection
│                           # ADD: collect_secrets test
├── test_scheduler.py      # NEW: make_search_job tests (client-is-None, exception swallowing)
├── conftest.py            # NEW: shared fixtures (mock transport, default state factory)
└── ...                    # Existing files unchanged
```

### Pattern 1: MockTransport for Base Client Methods
**What:** Create an `ArrClient` with a custom `httpx.MockTransport` handler that returns controlled responses, raising exceptions when needed to test retry and error branches.
**When to use:** Testing `_request_with_retry`, `get_paginated`, `validate_connection` -- any method that calls `self._client.request()` or `self._client.get()`.
**Example:**
```python
import httpx
from fetcharr.clients.base import ArrClient

async def test_request_with_retry_success():
    """First-attempt success returns response without retry."""
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"ok": True})
    )
    client = ArrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport)

    response = await client._request_with_retry("GET", "/test")
    assert response.status_code == 200
    await client.close()
```

### Pattern 2: AsyncMock for Cycle Orchestration
**What:** Patch the client methods (`get_wanted_missing`, `search_movies`, etc.) with `AsyncMock` to test cycle logic (batch processing, cursor advancement, error handling) without involving HTTP.
**When to use:** Testing `run_radarr_cycle`, `run_sonarr_cycle`, `make_search_job`.
**Example:**
```python
from unittest.mock import AsyncMock, patch
from fetcharr.search.engine import run_radarr_cycle
from fetcharr.state import _default_state

async def test_run_radarr_cycle_happy_path():
    """Happy path: fetches items, searches, advances cursors."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _default_state()
    settings = _make_settings()  # helper

    result = await run_radarr_cycle(client, state, settings)
    client.search_movies.assert_called_once_with([1])
    assert result["radarr"]["missing_cursor"] == 0  # wrapped (1 item)
```

### Pattern 3: Callable Transport with Call Counter for Retry Tests
**What:** Use a closure-based transport handler that tracks invocation count, returning failure on first call and success on second, to test retry logic precisely.
**When to use:** `_request_with_retry` retry-on-failure and retry-also-fails tests.
**Example:**
```python
async def test_request_with_retry_retries_on_failure():
    """First attempt fails, retry succeeds."""
    call_count = 0

    def handler(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(500)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = ArrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport)

    response = await client._request_with_retry("GET", "/test")
    assert call_count == 2
    assert response.status_code == 200
```

### Pattern 4: FastAPI app.state Mocking for Scheduler Tests
**What:** Create a minimal FastAPI instance, populate `app.state` with mock objects, and call `make_search_job` to get the closure, then invoke it directly.
**When to use:** Testing `make_search_job` for client-is-None early return and exception swallowing.
**Example:**
```python
import asyncio
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fetcharr.search.scheduler import make_search_job

async def test_make_search_job_client_none_returns_early():
    """Job returns immediately when client is None on app.state."""
    app = FastAPI()
    app.state.radarr_client = None
    app.state.search_lock = asyncio.Lock()
    # No other state needed -- early return before accessing them

    job = make_search_job(app, "radarr", Path("/tmp/state.json"))
    await job()  # Should return without error
```

### Anti-Patterns to Avoid
- **Mocking too deep:** Do not mock `asyncio.sleep` just to speed up retry tests -- MockTransport responds instantly so the 2s sleep is the only real delay. Patch `asyncio.sleep` to avoid 2-second waits in retry tests.
- **Testing implementation details:** Do not assert on log message exact text; assert on state changes, return values, and call counts instead.
- **Shared mutable state between tests:** Each test must create its own `_default_state()` instance. Never share state objects across tests.
- **Forgetting to close clients:** Use `try/finally` or context managers when creating real `ArrClient` instances in tests to avoid resource warnings.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| httpx response mocking | Custom httpx subclass stubs | `httpx.MockTransport` | Built-in, handles both sync/async, returns real `httpx.Response` objects |
| Async method mocking | Manual coroutine wrappers | `unittest.mock.AsyncMock` | Stdlib since Python 3.8; handles `await` natively; tracks calls |
| Fake FastAPI state | Custom state container class | Real `FastAPI()` instance + attribute assignment | `app.state` is just a Starlette `State` object; direct assignment works |
| Test settings factory | Duplicated Settings constructors | Shared fixture in conftest.py | Multiple test files need `Settings` with known values; DRY |

**Key insight:** Every mocking need in this phase is covered by httpx's built-in `MockTransport` and Python's stdlib `unittest.mock`. No third-party test mock libraries are needed.

## Common Pitfalls

### Pitfall 1: 2-Second Sleeps in Retry Tests
**What goes wrong:** `_request_with_retry` calls `asyncio.sleep(2)` on retry. Two retry tests = 4+ seconds of dead wait.
**Why it happens:** The sleep is production behavior in the retry path.
**How to avoid:** Patch `asyncio.sleep` as a no-op `AsyncMock` in all tests that exercise the retry path. This is safe because the sleep has no side effects beyond the delay.
**Warning signs:** Test suite takes > 1 second when it should complete in < 0.5s.

### Pitfall 2: MockTransport Handler Must Return httpx.Response
**What goes wrong:** Returning a dict or tuple from MockTransport handler causes cryptic errors.
**Why it happens:** MockTransport expects `httpx.Response` objects with proper status codes, headers, and content.
**How to avoid:** Always return `httpx.Response(status_code, json=...)` or `httpx.Response(status_code, text=...)` from handlers.
**Warning signs:** TypeError or AttributeError deep inside httpx internals.

### Pitfall 3: raise_for_status() on MockTransport Responses
**What goes wrong:** `httpx.Response(500)` from MockTransport does NOT auto-raise; `raise_for_status()` in production code triggers `HTTPStatusError` which needs the request object to be present.
**Why it happens:** MockTransport sets the request on the response automatically when routed through `AsyncClient.request()`, so this works correctly. But constructing `httpx.Response(500)` manually outside a client call won't have a request attached.
**How to avoid:** Always route through the client (via `client._request_with_retry` or `client.get`), never call `response.raise_for_status()` on manually constructed Response objects.
**Warning signs:** `RuntimeError: Cannot call raise_for_status without a request instance`.

### Pitfall 4: MockTransport for Exceptions (ConnectError, Timeout)
**What goes wrong:** Returning an error response is NOT the same as raising `httpx.ConnectError` or `httpx.TimeoutException`. For `validate_connection` tests, the transport handler must `raise` the exception, not return a response.
**Why it happens:** `ConnectError` and `TimeoutException` are transport-level errors, not HTTP status errors.
**How to avoid:** Use `def handler(request): raise httpx.ConnectError("refused")` in MockTransport for connection failure tests, `raise httpx.TimeoutException("timed out")` for timeout tests.
**Warning signs:** Test expects `validate_connection` to return `False` but it returns `True` because a response was returned instead of an exception raised.

### Pitfall 5: validate_connection Does NOT Use _request_with_retry
**What goes wrong:** Assuming `validate_connection` has retry behavior and testing accordingly.
**Why it happens:** `validate_connection` calls `self._client.get()` directly (the httpx client's get, not the ArrClient wrapper), per decision [01-02]: "validate_connection calls system/status directly (no retry) for clear startup diagnostics."
**How to avoid:** Read the source carefully. `validate_connection` has its own separate try/except branches for HTTPStatusError (401 vs other), ConnectError, TimeoutException, and ValidationError.
**Warning signs:** Tests structured around retry logic for validate_connection when there is none.

### Pitfall 6: State Mutation in Cycle Tests
**What goes wrong:** Tests assert on state values but forget that `run_radarr_cycle` / `run_sonarr_cycle` mutate the state dict in place AND return it.
**Why it happens:** The functions modify the passed-in state dict (e.g., `state["radarr"]["missing_cursor"] = new_cursor`).
**How to avoid:** Create a fresh `_default_state()` per test. Assert on the returned state OR the original reference (they're the same object).
**Warning signs:** State from one test leaking into another.

## Code Examples

### MockTransport for Paginated Response (Multi-Page)
```python
import httpx
from fetcharr.clients.base import ArrClient

async def test_get_paginated_multi_page():
    """Multi-page response collects all records."""
    def handler(request):
        page = int(request.url.params.get("page", "1"))
        if page == 1:
            return httpx.Response(200, json={
                "page": 1, "pageSize": 2, "sortKey": "id",
                "totalRecords": 3,
                "records": [{"id": 1}, {"id": 2}],
            })
        return httpx.Response(200, json={
            "page": 2, "pageSize": 2, "sortKey": "id",
            "totalRecords": 3,
            "records": [{"id": 3}],
        })

    transport = httpx.MockTransport(handler)
    client = ArrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport)

    result = await client.get_paginated("/api/v3/wanted/missing", page_size=2)
    assert len(result) == 3
    await client.close()
```

### MockTransport for Empty Paginated Response
```python
async def test_get_paginated_empty():
    """Zero totalRecords returns empty list immediately."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={
        "page": 1, "pageSize": 50, "sortKey": "id",
        "totalRecords": 0, "records": [],
    }))
    client = ArrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport)

    result = await client.get_paginated("/test")
    assert result == []
    await client.close()
```

### MockTransport for Malformed API Response (ValidationError)
```python
import pytest
import pydantic

async def test_get_paginated_malformed_response():
    """Malformed API response (missing required fields) raises ValidationError."""
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"bad": "data"})
    )
    client = ArrClient(base_url="http://test", api_key="key")
    client._client = httpx.AsyncClient(transport=transport)

    with pytest.raises(pydantic.ValidationError):
        await client.get_paginated("/test")
    await client.close()
```

### validate_connection Branches
```python
async def test_validate_connection_success():
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={
        "version": "5.0.0"
    }))
    client = ArrClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport)
    assert await client.validate_connection() is True

async def test_validate_connection_401():
    transport = httpx.MockTransport(lambda req: httpx.Response(401))
    client = ArrClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport)
    assert await client.validate_connection() is False

async def test_validate_connection_connect_error():
    def handler(request):
        raise httpx.ConnectError("refused")
    transport = httpx.MockTransport(handler)
    client = ArrClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport)
    assert await client.validate_connection() is False

async def test_validate_connection_timeout():
    def handler(request):
        raise httpx.TimeoutException("timed out")
    transport = httpx.MockTransport(handler)
    client = ArrClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport)
    assert await client.validate_connection() is False
```

### Cycle Test with Network Failure
```python
from unittest.mock import AsyncMock
from fetcharr.search.engine import run_radarr_cycle
from fetcharr.state import _default_state

async def test_run_radarr_cycle_network_failure():
    """Network failure aborts cycle, sets connected=False, preserves cursors."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))

    state = _default_state()
    state["radarr"]["missing_cursor"] = 5

    result = await run_radarr_cycle(client, state, settings)
    assert result["radarr"]["connected"] is False
    assert result["radarr"]["missing_cursor"] == 5  # unchanged
    assert result["radarr"]["unreachable_since"] is not None
```

### collect_secrets Test
```python
from fetcharr.startup import collect_secrets
from fetcharr.models.config import ArrConfig, Settings

def test_collect_secrets_extracts_all_api_keys():
    """collect_secrets returns all non-empty API key values."""
    settings = Settings(
        radarr=ArrConfig(url="http://r:7878", api_key="radarr-key", enabled=True),
        sonarr=ArrConfig(url="http://s:8989", api_key="sonarr-key", enabled=True),
    )
    secrets = collect_secrets(settings)
    assert "radarr-key" in secrets
    assert "sonarr-key" in secrets
    assert len(secrets) == 2
```

### make_search_job Tests
```python
import asyncio
from pathlib import Path
from fastapi import FastAPI
from fetcharr.search.scheduler import make_search_job

async def test_make_search_job_client_none():
    """Job returns early when client is None -- no error, no state access."""
    app = FastAPI()
    app.state.radarr_client = None
    app.state.search_lock = asyncio.Lock()

    job = make_search_job(app, "radarr", Path("/tmp/state.json"))
    await job()  # Should not raise

async def test_make_search_job_exception_swallowed():
    """Unhandled exception in cycle is caught and logged, not propagated."""
    app = FastAPI()
    app.state.radarr_client = AsyncMock()
    app.state.search_lock = asyncio.Lock()
    app.state.fetcharr_state = _default_state()
    app.state.settings = _make_settings()

    with patch("fetcharr.search.scheduler.run_radarr_cycle", side_effect=RuntimeError("boom")):
        with patch("fetcharr.search.scheduler.save_state"):
            job = make_search_job(app, "radarr", Path("/tmp/state.json"))
            await job()  # Should not raise
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@pytest.mark.asyncio` on every test | `asyncio_mode = "auto"` in pyproject.toml | pytest-asyncio 0.18+ | No decorator needed; all async test functions run automatically |
| `aiohttp` test utilities | httpx `MockTransport` | httpx 0.20+ | Transport-layer mocking ships with httpx; no third-party mock library needed |
| `responses` library for requests | `httpx.MockTransport` | N/A (this project uses httpx, not requests) | MockTransport is the httpx-native approach |

**Deprecated/outdated:**
- `pytest-aiohttp`: Only for aiohttp, not relevant to httpx
- `responses`: Only for `requests` library, not httpx

## Open Questions

1. **asyncio.sleep patching scope**
   - What we know: `_request_with_retry` has `await asyncio.sleep(2)` in the retry path. Patching it speeds up tests.
   - What's unclear: Whether to use a `conftest.py` autouse fixture or per-test `patch` decorators.
   - Recommendation: Use per-test `patch` for clarity -- only retry tests need it. An autouse fixture would mask which tests actually hit the sleep.

## Sources

### Primary (HIGH confidence)
- httpx 0.28.1 source code (`httpx.MockTransport`) -- verified locally via `python -c "from httpx._transports.mock import MockTransport"`
- Python 3.12 stdlib `unittest.mock.AsyncMock` -- verified locally
- pytest-asyncio 1.3.0 with `asyncio_mode = "auto"` -- verified in pyproject.toml
- Project source files: `fetcharr/clients/base.py`, `fetcharr/search/engine.py`, `fetcharr/search/scheduler.py`, `fetcharr/startup.py`

### Secondary (MEDIUM confidence)
- httpx official docs on MockTransport usage patterns -- consistent with local testing

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools already installed; verified locally
- Architecture: HIGH - Patterns derived from reading the actual source code and matching to standard pytest/httpx patterns
- Pitfalls: HIGH - Derived from specific code analysis (e.g., validate_connection has no retry, sleep in retry path, MockTransport exception raising)

**Research date:** 2026-02-24
**Valid until:** 2026-03-24 (stable -- no fast-moving dependencies)
