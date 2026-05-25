# Testing Patterns

**Analysis Date:** 2026-05-25

## Test Framework

**Runner:**
- pytest 9.0.3+
- Config: `pyproject.toml` with `asyncio_mode = "auto"`
- Async support: `pytest-asyncio`

**Assertion Library:**
- Built-in `assert` statements

**Run Commands:**
```bash
uv run pytest tests/ -x -q             # Run all tests, stop on first failure
uv run pytest tests/ -x -q -k search   # Run specific test by name pattern
uv run pytest tests/ -v                # Verbose output with test names
uv run pytest tests/test_validation.py::TestValidateArrUrl::test_valid_http_url  # Single test
```

## Test File Organization

**Location:**
- Tests in `tests/` directory (parallel to `triggarr/` package)
- Pattern: `tests/test_<module_name>.py` for corresponding `triggarr/<module_name>.py`
- Example: `triggarr/auth.py` → `tests/test_auth_*.py` (multiple files for auth features)

**Naming:**
- File: `test_<component>.py` (e.g., `test_validation.py`, `test_logging.py`, `test_search.py`)
- Test class: `Test<FunctionOrFeature>` (one class per function/behavior)
- Test method: `test_<scenario>()` (describes the test case)

**Example from `tests/test_validation.py`:**
```
tests/
├── conftest.py                    # Shared fixtures
├── test_validation.py             # URL validation, safe_int, safe_log_level
├── test_logging.py                # Loguru setup, redaction
├── test_search.py                 # Search engine functions, cycles
├── test_db.py                     # SQLite operations
├── test_web.py                    # Web routes, dashboard
├── test_auth_config.py            # AuthConfig models
├── test_middleware.py             # Auth middleware
└── ... (20+ test files)
```

**Structure:**
```python
"""Test module for <component> -- <what is tested>."""

from __future__ import annotations

import pytest
from <imports>

# ---------------------------------------------------------------------------
# Test Class (one per function or behavior group)
# ---------------------------------------------------------------------------


class TestFunctionName:
    """Docstring describing what this test class tests."""
    
    def test_normal_case(self) -> None:
        """Docstring: what is expected to pass."""
        # Arrange, Act, Assert
        
    def test_edge_case(self) -> None:
        """Docstring: boundary condition."""
        
    def test_error_case(self) -> None:
        """Docstring: what should fail."""
        with pytest.raises(ValueError):
            ...
```

## Test Structure

**Suite Organization:**
- One test class per function/feature
- Test methods are independent (no shared state between tests)
- Autouse fixtures reset module-level singletons before each test

**Example from `tests/test_validation.py`:**
```python
class TestValidateArrUrl:
    """URL validation: scheme enforcement, SSRF blocking, private-IP allow."""

    def test_valid_http_url(self) -> None:
        ok, err = validate_arr_url("http://radarr:7878")
        assert ok is True
        assert err == ""

    def test_ftp_scheme_rejected(self) -> None:
        ok, err = validate_arr_url("ftp://evil.com")
        assert ok is False
        assert "scheme" in err.lower()

    def test_cloud_metadata_ip_blocked(self) -> None:
        ok, err = validate_arr_url("http://169.254.169.254/latest/meta-data")
        assert ok is False
```

**Patterns:**

1. **Setup/Teardown:**
   - Use pytest fixtures for setup/teardown
   - Autouse fixtures for global cleanup: `@pytest.fixture(autouse=True)`
   - Example from `tests/conftest.py`:
     ```python
     @pytest.fixture(autouse=True)
     def _reset_disabled_warned():
         """Reset AuthMiddleware._disabled_warned_at before each test."""
         AuthMiddleware._disabled_warned_at = 0.0
         yield
         AuthMiddleware._disabled_warned_at = 0.0
     ```

2. **Assertion Pattern:**
   - Use simple `assert` statements
   - Use `pytest.raises()` for exception testing
   - Compare return tuples: `batch, new_cursor = slice_batch(...); assert batch == [3, 4]; assert new_cursor == 5`

3. **Docstrings:**
   - Each test method has a one-line docstring describing what is tested
   - Example: `def test_valid_http_url(self) -> None: """HTTP URLs with valid schemes accepted."""`

## Mocking

**Framework:** `unittest.mock`

**Patterns:**
- `MagicMock()` for class instances and methods
- `AsyncMock()` for async functions
- `patch()` as context manager or decorator for replacing modules/functions

**Common Mocks from `tests/test_web.py`:**

```python
from unittest.mock import AsyncMock, MagicMock, patch

# Mock FastAPI app state
app.state.scheduler = MagicMock()
mock_job = MagicMock()
mock_job.next_run_time = None
app.state.scheduler.get_job.return_value = mock_job

# Mock async HTTP clients
radarr_client = MagicMock()
radarr_client.close = AsyncMock()

# Mock database
db = MagicMock()
```

**What to Mock:**
- External HTTP clients (ArrClient instances)
- Scheduler/job state
- Database connections (for integration tests, use real `aiosqlite` connection)
- File system operations (use `tmp_path` fixture instead)

**What NOT to Mock:**
- Pydantic models (validate real objects)
- Core filtering/batching logic (test the pure functions)
- Validation helpers (test actual validation)
- SQLite database (use in-memory or temp file with real migrations)

**Example from `tests/test_web.py`:**
```python
# Don't mock validation -- test real validation
ok, err = validate_arr_url("http://radarr:7878")
assert ok is True

# Do mock external HTTP client
mock_client = MagicMock()
mock_client.get_status = AsyncMock(return_value={"version": "5.0.0"})
app.state.clients = {"Default": mock_client}
```

## Fixtures and Factories

**Test Data (Fixtures):**
- Shared fixtures in `tests/conftest.py`
- Factory functions for building test data

**Example from `tests/conftest.py`:**
```python
def make_settings(
    radarr_url: str = "http://radarr:7878",
    radarr_enabled: bool = True,
    radarr_api_key: str = "radarr-test-key",
    sonarr_url: str = "http://sonarr:8989",
    sonarr_enabled: bool = True,
    sonarr_api_key: str = "sonarr-test-key",
    search_missing_count: int = 5,
    search_cutoff_count: int = 5,
    search_interval: int = 30,
    general: GeneralConfig | None = None,
) -> Settings:
    """Build a Settings instance with sensible test defaults."""
    return Settings(
        general=general or GeneralConfig(),
        radarr={"Default": InstanceConfig(
            url=radarr_url,
            api_key=radarr_api_key,
            enabled=radarr_enabled,
            search_missing_count=search_missing_count,
            search_cutoff_count=search_cutoff_count,
            search_interval=search_interval,
        )},
        # ... sonarr, lidarr ...
    )


def default_state(settings: Settings | None = None) -> TriggarrState:
    """Return a fresh default application state."""
    return _default_state(settings)
```

**Fixture Registration (pytest):**
```python
@pytest.fixture(autouse=True)
def _reset_rate_limit_state():
    """Reset rate limiter state before each test."""
    _reset_rate_limiter()
    yield
    _reset_rate_limiter()


@pytest.fixture
async def test_app(tmp_path):
    """Build a minimal FastAPI app with mocked state."""
    app = FastAPI()
    app.state.db = await aiosqlite.connect(tmp_path / "test.db")
    return app
```

**Location:**
- Global fixtures: `tests/conftest.py`
- Module-specific fixtures: top of test file before test classes
- Fixture function names prefixed with underscore for autouse fixtures: `_reset_rate_limit_state`

## Coverage

**Requirements:** No enforced coverage target

**View Coverage:**
```bash
uv run pytest tests/ --cov=triggarr --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- Pure functions: `filter_monitored()`, `slice_batch()`, `validate_arr_url()`
- Individual methods of models
- Validation logic
- Example from `tests/test_search.py`:
  ```python
  def test_filter_monitored_keeps_only_monitored():
      items = [
          {"id": 1, "monitored": True},
          {"id": 2, "monitored": False},
          {"id": 3},
          {"id": 4, "monitored": True},
      ]
      result = filter_monitored(items)
      assert len(result) == 2
      assert result[0]["id"] == 1
  ```

**Integration Tests:**
- Database operations with real SQLite: `tests/test_db.py`
- Config loading and migration: `tests/test_config.py`
- Web routes with FastAPI TestClient: `tests/test_web.py`
- Middleware behavior: `tests/test_middleware.py`
- Example from `tests/test_db.py`:
  ```python
  async def test_insert_and_retrieve(tmp_path):
      """Inserted entries are retrieved in newest-first order."""
      db_path = tmp_path / "test.db"
      db = await aiosqlite.connect(db_path)
      await init_db(db, db_path)
      
      await insert_search_entry(db, "Radarr", "missing", "Movie A")
      await insert_search_entry(db, "Sonarr", "cutoff", "Show B")
      
      results = await get_recent_searches(db)
      assert len(results) == 2
  ```

**E2E Tests:**
- Not formally present; web UI tested via FastAPI TestClient
- Example from `tests/test_web.py`:
  ```python
  @pytest.fixture
  async def test_app(tmp_path):
      """Build a minimal FastAPI app with mocked state."""
      app = FastAPI()
      app.include_router(router)
      return app
  
  # Use TestClient to make requests
  client = TestClient(app)
  response = client.get("/")
  assert response.status_code == 200
  ```

## Common Patterns

**Async Testing:**
- pytest-asyncio with `asyncio_mode = "auto"` (no need for `@pytest.mark.asyncio`)
- Example from `tests/test_search.py`:
  ```python
  async def test_run_radarr_cycle_success(tmp_path):
      """run_radarr_cycle fetches, filters, slices, and logs searches."""
      db = await aiosqlite.connect(tmp_path / "test.db")
      await init_db(db, db_path)
      
      settings = make_settings()
      state = default_state(settings)
      
      # Async call without decorator -- pytest-asyncio handles it
      result = await run_radarr_cycle(db, settings, state)
      assert result is not None
  ```

**Error Testing:**
- Use `pytest.raises()` context manager
- Example from `tests/test_validation.py`:
  ```python
  def test_ftp_scheme_rejected(self) -> None:
      ok, err = validate_arr_url("ftp://evil.com")
      assert ok is False
      assert "scheme" in err.lower()
  ```

**Exception Details:**
- For ValidationError: check error count and message
- Example from `tests/test_validation.py`:
  ```python
  def test_invalid_log_level(self) -> None:
      with pytest.raises(ValidationError, match="log_level"):
          Settings(general=GeneralConfig(log_level="critical"))
  ```

**Parametrized Tests (pytest.mark.parametrize):**
- Not heavily used in this codebase
- When used, groups test cases for the same function with different inputs

## Database Testing

**SQLite with Real Migrations:**
- `tests/test_db.py` uses real aiosqlite connections
- Migrations run via `init_db()` before test
- Temp directory for each test via pytest's `tmp_path` fixture

**Example from `tests/test_db.py`:**
```python
async def _init_test_db(tmp_path):
    """Create a test database with migrations applied."""
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)
    return db, db_path


async def test_insert_and_retrieve(tmp_path):
    db, db_path = await _init_test_db(tmp_path)
    
    await insert_search_entry(db, "Radarr", "missing", "Movie A")
    results = await get_recent_searches(db)
    assert len(results) == 1
    await db.close()
```

## Logging in Tests

**Capturing Logs:**
- Use `loguru` directly in tests
- Example from `tests/test_logging.py`:
  ```python
  import io
  from loguru import logger
  from triggarr.logging import create_redacting_sink
  
  def test_redaction_filter_removes_secret() -> None:
      secret = "my-api-key-abc123"
      output = io.StringIO()
      
      logger.remove()
      sink = create_redacting_sink([secret], stream=output)
      logger.add(sink, format="{message}", colorize=False)
      
      logger.info("Connecting with key {key}", key=secret)
      
      result = output.getvalue()
      assert secret not in result
      assert "[REDACTED]" in result
  ```

---

*Testing analysis: 2026-05-25*
