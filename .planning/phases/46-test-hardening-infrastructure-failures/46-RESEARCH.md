# Phase 46: Test Hardening -- Infrastructure Failures - Research

**Researched:** 2026-04-09
**Domain:** Python test hardening (httpx error simulation, pytest-asyncio)
**Confidence:** HIGH

## Summary

This phase adds tests verifying Triggarr handles network and API failures gracefully. The codebase already has a solid error handling architecture: `_request_with_retry` in `ArrClient` catches `httpx.HTTPStatusError` and `httpx.TransportError`, the search cycle functions catch `httpx.HTTPError` and `pydantic.ValidationError`, and `validate_connection` handles `ConnectError`, `TimeoutException`, and `HTTPStatusError` individually. The existing test infrastructure uses `httpx.MockTransport` for client-level tests and `AsyncMock` with `side_effect` for cycle-level tests.

The milestone audit correctly identified significant existing coverage. The gap analysis below shows exactly what is covered, partially covered, and missing for each requirement. The primary work is filling gaps in CONN-02 (DNS), CONN-03 (SSL), API-01 (malformed JSON at multiple layers), API-02 (403/500/502 status codes), API-03 (Sonarr v3/v4 edge cases beyond basic detection), and API-04 (truncated pagination).

**Primary recommendation:** Follow the existing test patterns (MockTransport for client-level, AsyncMock for cycle-level), target the specific httpx exception subclasses for DNS/SSL, and add focused tests that fill the documented gaps without duplicating the 8+ existing ConnectError tests.

## Project Constraints (from CLAUDE.md)

- Python 3.11+, ruff linting (E, F, I, UP, B, SIM), line length 120
- pytest-asyncio with asyncio_mode=auto
- Loguru for logging (never print/logging module)
- Tests run via `uv run pytest tests/ -x -q`
- Lint via `uv run ruff check triggarr/ tests/`
- Resilience pattern: error handling catches `httpx.HTTPError` + `pydantic.ValidationError` (no bare `except:`)

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CONN-01 | Tests verify graceful handling when *arr instance is unreachable (connection refused, timeout) | Partially covered: 8+ existing ConnectError tests + timeout tests. Gap: need to verify logging output and state consistency in more scenarios |
| CONN-02 | Tests verify graceful handling of DNS resolution failure | NOT covered. httpx raises `ConnectError` for DNS failures -- same parent class as connection refused, but distinct error message. Need explicit DNS failure tests |
| CONN-03 | Tests verify graceful handling of SSL/TLS errors | NOT covered. httpx raises `ConnectError` for SSL errors. Need explicit SSL error tests |
| CONN-04 | Tests verify graceful handling when instance goes down mid-search-cycle | Partially covered: per-item skip tests exist (search_movies raises ConnectError on first item, continues to second). Gap: need test where fetch succeeds but subsequent search commands fail for ALL items |
| API-01 | Tests verify graceful handling of malformed JSON from *arr | Partially covered: `test_get_paginated_malformed_response` exists (pydantic ValidationError). Gap: need malformed JSON that causes json.JSONDecodeError (not just schema mismatch), and malformed JSON at cycle level |
| API-02 | Tests verify graceful handling of unexpected HTTP status codes (401, 403, 500, 502) | Partially covered: 401 tested in validate_connection, 500 tested in retry logic. Gap: 403 and 502 status codes not tested; status codes during search cycles not tested |
| API-03 | Tests verify graceful handling of API version mismatches (Sonarr v3/v4 edge cases) | Partially covered: detect_api_version tests exist for v3, v4, and error fallback. Gap: edge cases like version "5.0", empty version string, missing version key in response, non-standard version format |
| API-04 | Tests verify graceful handling of empty or truncated paginated responses | Partially covered: empty pagination tested. Gap: truncated responses (totalRecords says 10 but only 3 returned), missing records key, page returns fewer items than expected mid-pagination |
</phase_requirements>

## Standard Stack

### Core (already installed -- no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 | Test framework | Already in project [VERIFIED: `uv run python -c`] |
| pytest-asyncio | 1.3.0 | Async test support | Already in project, asyncio_mode=auto [VERIFIED: `uv run python -c`] |
| httpx | 0.28.1 | HTTP client (MockTransport for testing) | Already in project [VERIFIED: `uv run python -c`] |
| pydantic | (installed) | Validation error testing | Already in project [VERIFIED: imports in test files] |

### Supporting (no additional installs needed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unittest.mock | stdlib | AsyncMock, patch | Cycle-level tests mocking client methods |
| io.StringIO | stdlib | Capture loguru output | Verifying error logging behavior |
| loguru | (installed) | Log capture for assertions | Verifying warnings logged on failures |

**Installation:** None required. All dependencies already present.

## Architecture Patterns

### Existing Test Pattern: Client-Level (MockTransport)

Used for testing `ArrClient` methods directly (validate_connection, get_paginated, _request_with_retry).

```python
# Pattern from test_clients.py [VERIFIED: codebase]
async def test_example() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")  # or return httpx.Response(...)

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.validate_connection()
        assert result is False
    finally:
        await client.close()
```

### Existing Test Pattern: Cycle-Level (AsyncMock)

Used for testing `run_radarr_cycle` / `run_sonarr_cycle` / `run_lidarr_cycle` with mocked client methods.

```python
# Pattern from test_search.py [VERIFIED: codebase]
async def test_cycle_network_failure(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))

    state = _make_test_state()
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["connected"] is False
    await db.close()
```

### Log Capture Pattern

```python
# Pattern from test_startup.py [VERIFIED: codebase]
sink = io.StringIO()
handler_id = logger.add(sink, format="{message}", level="WARNING")
try:
    # ... do something that logs
    pass
finally:
    logger.remove(handler_id)
assert "expected message" in sink.getvalue()
```

### Anti-Patterns to Avoid
- **Do not create new test files for this phase:** All tests should go in existing `test_clients.py` and `test_search.py` to maintain the established organization
- **Do not test exception types that httpx doesn't actually raise:** Verify the specific exception hierarchy before simulating
- **Do not duplicate existing ConnectError tests:** 8+ already exist -- focus on DNS/SSL variants and missing status codes

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP error simulation | Custom error classes | httpx built-in exceptions (ConnectError, TimeoutException, etc.) | httpx exception hierarchy is the actual runtime contract |
| Mock HTTP transport | Request interceptors | httpx.MockTransport | Already used throughout test suite |
| Async client mocking | Manual mock objects | unittest.mock.AsyncMock | Standard pattern, already established |

## httpx Exception Hierarchy (Critical for This Phase)

The exception hierarchy determines which exceptions to simulate for each requirement. [VERIFIED: `uv run python -c "import httpx; ..."`]

```
httpx.HTTPError
  httpx.HTTPStatusError          # 4xx/5xx responses after raise_for_status()
  httpx.RequestError
    httpx.TransportError
      httpx.TimeoutException     # CONN-01: timeout
      httpx.ConnectError         # CONN-01: connection refused, CONN-02: DNS, CONN-03: SSL
      httpx.ReadError            # mid-transfer failures
      httpx.WriteError
      httpx.CloseError
      httpx.ProtocolError
        httpx.LocalProtocolError
        httpx.RemoteProtocolError
      httpx.ProxyError
      httpx.DecodingError
      httpx.NetworkError
```

Key insight: DNS failures and SSL errors both raise `httpx.ConnectError` at the transport level. The code catches `httpx.ConnectError` in `validate_connection` and catches `httpx.HTTPError` (parent) in cycle functions. So DNS and SSL errors ARE handled by existing code paths -- the tests just need to verify this explicitly with appropriate error messages. [VERIFIED: codebase error handling patterns]

## Detailed Gap Analysis Per Requirement

### CONN-01: Connection Refused + Timeout (PARTIAL -- fill gaps)

**Already covered:**
- `test_validate_connection_connect_error` -- ConnectError returns False [VERIFIED: test_clients.py:282]
- `test_validate_connection_timeout` -- TimeoutException returns False [VERIFIED: test_clients.py:299]
- `test_run_radarr_cycle_network_failure` -- ConnectError aborts cycle, sets connected=False [VERIFIED: test_search.py:263]
- `test_run_sonarr_cycle_network_failure` -- same for Sonarr [VERIFIED: test_search.py:421]
- `test_run_lidarr_cycle_network_failure` -- same for Lidarr [VERIFIED: test_search.py:2037]
- `test_request_with_retry_retries_on_failure` -- 500 retries once [VERIFIED: test_clients.py:97]
- `test_request_with_retry_reraises_when_retry_fails` -- re-raises after retry exhausted [VERIFIED: test_clients.py:121]
- `test_tracking_failure_nonfatal` -- ConnectError during tracking is non-fatal [VERIFIED: test_tracking.py:330]

**Gaps to fill:**
- TimeoutException during cycle fetch (not just ConnectError) -- verify same abort behavior
- Verify `unreachable_since` is set on first failure and preserved (not overwritten) on subsequent failures
- Verify logging output on connection failures (log capture)

### CONN-02: DNS Resolution Failure (NOT COVERED)

**What to test:** `httpx.ConnectError("Name or service not known")` -- DNS failures raise ConnectError with DNS-specific messages. Since the code catches ConnectError, this is handled, but we need explicit tests proving it.

**Tests needed:**
- Client-level: validate_connection with DNS failure returns False
- Cycle-level: DNS failure during fetch aborts cycle gracefully

### CONN-03: SSL/TLS Errors (NOT COVERED)

**What to test:** `httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED]")` -- SSL errors also raise ConnectError at the transport level.

**Tests needed:**
- Client-level: validate_connection with SSL error returns False
- Cycle-level: SSL error during fetch aborts cycle gracefully

### CONN-04: Instance Down Mid-Cycle (PARTIAL -- fill gaps)

**Already covered:**
- `test_run_radarr_cycle_per_item_skip` -- first search_movies fails, second succeeds, both logged [VERIFIED: test_search.py:287]
- `test_run_sonarr_cycle_per_item_skip` -- same for Sonarr [VERIFIED: test_search.py:444]
- `test_run_lidarr_cycle_per_item_skip` -- same for Lidarr [VERIFIED: test_search.py:2059]

**Gaps to fill:**
- Instance goes down after successful fetch but ALL search commands fail (not just first)
- Verify cycle completes (doesn't crash) and cursor still advances
- Verify skipped counts are accurate in diagnostic summary

### API-01: Malformed JSON (PARTIAL -- fill gaps)

**Already covered:**
- `test_get_paginated_malformed_response` -- bad schema raises pydantic.ValidationError [VERIFIED: test_clients.py:225]

**Gaps to fill:**
- Invalid JSON (not valid JSON at all, e.g. truncated response body) -- httpx response.json() raises json.JSONDecodeError which is NOT caught by the pydantic.ValidationError handler. Need to verify behavior
- Malformed JSON during cycle-level operations (get_wanted_missing returns unparseable data)
- Non-dict response where dict expected (e.g. API returns string instead of object)

**Important note:** `response.json()` raises `httpx.DecodingError` (subclass of `TransportError`) when JSON is invalid. This IS caught by the `httpx.HTTPError` handler in cycles. Need to verify this path. [VERIFIED: httpx exception hierarchy]

### API-02: Unexpected HTTP Status Codes (PARTIAL -- fill gaps)

**Already covered:**
- 401: `test_validate_connection_401` [VERIFIED: test_clients.py:264]
- 500: `test_request_with_retry_retries_on_failure` + `test_request_with_retry_reraises_when_retry_fails` [VERIFIED: test_clients.py:97,121]

**Gaps to fill:**
- 403 Forbidden during validate_connection (different from 401 -- should log differently?)
- 502 Bad Gateway during validate_connection
- 403/500/502 during cycle fetch (get_wanted_missing) -- verify abort behavior
- 403/500/502 during search command -- verify skip-and-continue behavior

### API-03: Sonarr v3/v4 API Version Mismatches (PARTIAL -- fill gaps)

**Already covered:**
- `test_detect_api_version_parses_v3` -- version "3.0.10.1567" -> "v3" [VERIFIED: test_startup.py:155]
- `test_detect_api_version_parses_v4` -- version "4.0.1.929" -> "v4" [VERIFIED: test_startup.py:170]
- `test_detect_api_version_handles_error` -- 500 error falls back to "v3" [VERIFIED: test_startup.py:185]
- `test_sonarr_version_detection_v3/v4/failure` -- integration tests via validate_connections [VERIFIED: test_startup.py:212,234,256]

**Gaps to fill:**
- Edge case: version string "5.0.0" (future major version) -- what does detect_api_version return?
- Edge case: empty version string ""
- Edge case: missing "version" key in response JSON (KeyError handling)
- Edge case: version string with unexpected format "4.0.0-beta1"
- Edge case: ConnectError/TimeoutException during version detection (not just HTTP 500)

**Note on actual behavior:** `detect_api_version` catches `(httpx.HTTPError, pydantic.ValidationError, KeyError)`. The KeyError catch handles missing "version" key. ConnectError is a subclass of httpx.HTTPError, so it IS caught. [VERIFIED: sonarr.py:46]

### API-04: Empty/Truncated Paginated Responses (PARTIAL -- fill gaps)

**Already covered:**
- `test_get_paginated_empty_results` -- totalRecords=0 returns empty list [VERIFIED: test_clients.py:201]
- `test_get_paginated_single_page` and `test_get_paginated_multi_page` -- happy paths [VERIFIED: test_clients.py:143,166]

**Gaps to fill:**
- Truncated: totalRecords=10 but only 3 records returned across all pages (server lies)
- Missing records key in response (should trigger pydantic ValidationError)
- Page 2+ returns empty records array (mid-pagination truncation)
- totalRecords changes between pages (server inconsistency -- code locks totalRecords from first page, verify this)
- response.json() returns non-dict (e.g. plain string or null)

## Common Pitfalls

### Pitfall 1: Duplicating Existing ConnectError Tests
**What goes wrong:** Writing tests that assert the same behavior already verified in 8+ existing tests.
**Why it happens:** Not auditing existing coverage before writing new tests.
**How to avoid:** The gap analysis above identifies exactly what is NOT covered. Only write tests for those gaps.
**Warning signs:** Test name closely matches an existing test name.

### Pitfall 2: Testing Exception Types httpx Doesn't Raise
**What goes wrong:** Simulating `socket.gaierror` or `ssl.SSLError` directly when httpx wraps these into `ConnectError`.
**Why it happens:** Confusing raw socket exceptions with httpx's transport layer.
**How to avoid:** Always simulate httpx exception types, not underlying stdlib exceptions. httpx catches low-level errors and re-raises them as its own types.
**Warning signs:** Importing from `socket` or `ssl` module in test files.

### Pitfall 3: Not Closing Clients in Tests
**What goes wrong:** Resource warnings from unclosed httpx.AsyncClient instances.
**Why it happens:** Missing `finally: await client.close()` block.
**How to avoid:** Follow the existing try/finally pattern in every client-level test. Cycle-level tests use AsyncMock which doesn't need closing.
**Warning signs:** ResourceWarning in test output.

### Pitfall 4: Forgetting asyncio.sleep Mock in Retry Tests
**What goes wrong:** Tests take 2+ seconds due to actual sleep in `_request_with_retry`.
**Why it happens:** The retry logic calls `asyncio.sleep(2)` between attempts.
**How to avoid:** Patch `asyncio.sleep` with `AsyncMock` when testing retry behavior.
**Warning signs:** Slow test execution.

### Pitfall 5: JSON Decode vs Pydantic Validation Confusion
**What goes wrong:** Assuming `response.json()` failure is caught by pydantic.ValidationError handler.
**Why it happens:** `response.json()` raises `json.JSONDecodeError` (or httpx.DecodingError), not pydantic.ValidationError.
**How to avoid:** Understand the two failure modes: (1) valid JSON but wrong schema -> pydantic.ValidationError, (2) invalid JSON -> httpx.DecodingError. Both are caught by `httpx.HTTPError` handler in cycles.

## Code Examples

### Simulating DNS Failure
```python
# DNS failures raise ConnectError with DNS-specific message [VERIFIED: httpx source behavior]
async def test_validate_connection_dns_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("[Errno -2] Name or service not known")

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://nonexistent.invalid", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.validate_connection()
        assert result is False
    finally:
        await client.close()
```

### Simulating SSL Error
```python
# SSL errors also raise ConnectError [VERIFIED: httpx source behavior]
async def test_validate_connection_ssl_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED]")

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="https://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="https://test")
    try:
        result = await client.validate_connection()
        assert result is False
    finally:
        await client.close()
```

### Simulating Truncated Pagination
```python
# Server claims 10 records but only returns 3 [ASSUMED: pattern follows existing pagination tests]
async def test_get_paginated_truncated_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "page": 1, "pageSize": 50, "sortKey": "id",
            "totalRecords": 10,
            "records": [{"id": 1}, {"id": 2}, {"id": 3}],
        }
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    client = _ConcreteClient(base_url="http://test", api_key="key")
    client._app_name = "Test"
    client._client = httpx.AsyncClient(transport=transport, base_url="http://test")
    try:
        result = await client.get_paginated("/items")
        # Pagination terminates because page*pageSize >= totalRecords is false,
        # but records is < pageSize, so it depends on termination logic.
        # Current code: terminates when len(records)==0 or page*pageSize>=totalRecords
        # With 3 records and pageSize=50: 1*50=50 >= 10, so it terminates.
        assert len(result) == 3  # Returns what we got, not what was promised
    finally:
        await client.close()
```

### Simulating 403/502 at Cycle Level
```python
# Status code errors at cycle level [ASSUMED: follows existing cycle test pattern]
async def test_radarr_cycle_403_aborts(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    request = httpx.Request("GET", "http://test/api/v3/wanted/missing")
    response = httpx.Response(403, request=request)
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(
        side_effect=httpx.HTTPStatusError("Forbidden", request=request, response=response)
    )

    state = _make_test_state()
    settings = _cycle_settings()
    instance_config = _cycle_instance_config()

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)
    assert result["radarr"]["Default"]["connected"] is False
    await db.close()
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | pyproject.toml (asyncio_mode = "auto") |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONN-01 | Connection refused + timeout handling | unit | `uv run pytest tests/test_clients.py tests/test_search.py -x -q -k "connect_error or timeout"` | Partial -- needs gap tests |
| CONN-02 | DNS resolution failure handling | unit | `uv run pytest tests/test_clients.py tests/test_search.py -x -q -k "dns"` | Wave 0 |
| CONN-03 | SSL/TLS error handling | unit | `uv run pytest tests/test_clients.py tests/test_search.py -x -q -k "ssl"` | Wave 0 |
| CONN-04 | Mid-cycle instance down | unit | `uv run pytest tests/test_search.py -x -q -k "mid_cycle or all_fail"` | Partial -- needs gap tests |
| API-01 | Malformed JSON handling | unit | `uv run pytest tests/test_clients.py tests/test_search.py -x -q -k "malformed or invalid_json"` | Partial -- needs gap tests |
| API-02 | Unexpected HTTP status codes | unit | `uv run pytest tests/test_clients.py tests/test_search.py -x -q -k "403 or 502 or status"` | Wave 0 for 403/502 |
| API-03 | Sonarr v3/v4 version edge cases | unit | `uv run pytest tests/test_startup.py -x -q -k "detect_api_version"` | Partial -- needs edge cases |
| API-04 | Truncated pagination | unit | `uv run pytest tests/test_clients.py -x -q -k "truncat or paginated"` | Partial -- needs truncation tests |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
None -- existing test infrastructure fully supports this phase. No new frameworks, config files, or fixtures needed. The `_ConcreteClient`, `_make_test_state`, `_cycle_settings`, and `_cycle_instance_config` helpers are all already available.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | httpx.DecodingError is raised when response.json() encounters invalid JSON | Code Examples / API-01 gap analysis | Tests for invalid JSON may need different exception type |
| A2 | Truncated pagination test -- behavior when totalRecords=10 but only 3 returned and pageSize=50 | Code Examples | Pagination termination logic may differ; verified via code reading but not runtime test |

## Open Questions

1. **Should tests verify specific log messages or just that logging occurs?**
   - What we know: Existing tests use `io.StringIO` + loguru to capture and assert on log content
   - What's unclear: Whether the planner should require exact message matching or substring matching
   - Recommendation: Use substring matching (e.g., `"refused" in sink.getvalue()`) to avoid brittle tests

2. **Should malformed JSON tests go in test_clients.py or test_search.py?**
   - What we know: Client-level malformed JSON test exists in test_clients.py; no cycle-level equivalent
   - What's unclear: Best organization
   - Recommendation: Client-level JSON tests in test_clients.py, cycle-level in test_search.py (matching existing organization)

## Sources

### Primary (HIGH confidence)
- Codebase: `triggarr/clients/base.py` -- error handling in _request_with_retry, validate_connection, get_paginated
- Codebase: `triggarr/clients/sonarr.py` -- detect_api_version implementation
- Codebase: `triggarr/search/engine.py` -- cycle error handling patterns (_sanitize_exc, try/except blocks)
- Codebase: `tests/test_clients.py` -- 40+ existing client tests
- Codebase: `tests/test_search.py` -- 100+ existing search tests including network failure and per-item skip
- Codebase: `tests/test_startup.py` -- Sonarr v3/v4 detection tests
- Codebase: `tests/test_tracking.py` -- tracking failure nonfatal test
- Runtime verification: httpx 0.28.1 exception hierarchy via `dir(httpx)`

### Secondary (MEDIUM confidence)
- httpx exception hierarchy documentation (verified via runtime introspection)

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and verified
- Architecture: HIGH -- patterns directly extracted from existing test files
- Pitfalls: HIGH -- derived from actual codebase patterns and exception hierarchy
- Gap analysis: HIGH -- every existing test verified by line number in codebase

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (stable -- test patterns and httpx API unlikely to change)
