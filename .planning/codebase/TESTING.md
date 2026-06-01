# Testing Patterns

**Analysis Date:** 2026-06-01

## Test Framework

**Runner:**
- Framework: pytest 9.0.3+ (configured in `pyproject.toml`)
- Async support: pytest-asyncio (auto mode enabled)
- Config location: `pyproject.toml` `[tool.pytest.ini_options]`
- Async mode: `asyncio_mode = "auto"` (all `async def test_*` functions are auto-wrapped)

**Assertion Library:**
- Python standard assertions (`assert`)
- pytest parametrization via `@pytest.mark.parametrize`
- pytest raises for exception testing: `with pytest.raises(ValidationError, match="...")`

**Run Commands:**
```bash
uv run pytest tests/ -x -q              # Run all tests, stop on first failure
uv run pytest tests/ -v                 # Verbose output
uv run pytest tests/ --cov=triggarr     # Coverage report (if coverage plugin installed)
uv run pytest tests/test_config.py      # Single file
uv run pytest -k test_radarr_grabbed    # Filter by test name
```

## Test File Organization

**Location:**
- Test files co-located in `tests/` directory (separate from source, not alongside)
- Parallel structure mirrors source: `tests/test_config.py` mirrors `triggarr/config.py`, `tests/test_db.py` mirrors `triggarr/db.py`

**Naming:**
- Test modules: `test_*.py` (e.g., `test_config.py`, `test_tracking.py`, `test_middleware.py`)
- Test functions: `test_<feature>` or `async def test_<feature>` (async for I/O-heavy tests)
- Test count: 241 async/sync test functions across 39 test files (as of 2026-06-01)

**Structure:**
```
tests/
├── conftest.py           # Shared fixtures and factories
├── test_config.py        # Config loading, migration, validation
├── test_state.py         # State persistence, atomic writes
├── test_db.py            # Database init, migrations, queries
├── test_tracking.py      # Grab history tracking, outcome resolution
├── test_middleware.py    # CSRF (OriginCheckMiddleware) tests
├── test_logging.py       # Loguru setup, redaction
├── test_search.py        # Search engine cycles (large — 1800+ lines)
├── test_web.py           # FastAPI routes, forms, responses
└── ... (34 other test files)
```

## Test Structure

**Suite Organization:**
```python
# Header: docstring explaining what's tested
"""Tests for config loading, default generation, validation, and SecretStr security."""

from __future__ import annotations

# Imports: standard lib, third-party, local (organized by ruff)
import io
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
import tomli_w
from loguru import logger
from pydantic import SecretStr, ValidationError

# Fixtures and helpers (if any inline)
VALID_TOML = """\
[general]
log_level = "debug"
...
"""

# Tests grouped by feature with section comments
# --- Config loading tests ---

def test_settings_loads_from_toml(tmp_path: Path) -> None:
    """Valid TOML config loads all sections correctly."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(VALID_TOML)

    settings = load_settings(config_file)

    assert settings.general.log_level == "debug"
```

**Patterns:**

1. **Setup:** Use `tmp_path` fixture (pytest-provided) for file isolation
2. **Assertions:** One logical assertion per line; multiple assertions in same test if testing one feature
3. **Cleanup:** pytest fixtures auto-cleanup `tmp_path`; async resources closed explicitly

Example from `test_config.py` lines 57-72:
```python
def test_settings_loads_from_toml(tmp_path: Path) -> None:
    """Valid TOML config loads all sections correctly."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(VALID_TOML)
    
    settings = load_settings(config_file)
    
    assert settings.general.log_level == "debug"
    assert "Default" in settings.radarr
    assert settings.radarr["Default"].api_key.get_secret_value() == "radarr-secret-key-123"
```

## Mocking

**Framework:** `unittest.mock.AsyncMock`, `unittest.mock.MagicMock`, `unittest.mock.patch`

**Patterns:**

1. **Async Client Mocking:**
   ```python
   from unittest.mock import AsyncMock
   
   radarr = AsyncMock()
   radarr.get_grab_history.return_value = [_grab(...)]
   counts = await run_tracking_check(db, radarr, "Radarr", "Default", tracking_window_minutes=60)
   ```
   Example: `test_tracking.py` lines 115-117

2. **Database Mocking:**
   - Avoid mocking; use real aiosqlite with `tmp_path` instead
   - Real DB ensures migrations work and state matches production
   - Example: `test_tracking.py` `_init_db()` creates real SQLite connection (lines 34-39)

3. **Patch for Global State:**
   ```python
   with patch("triggarr.web.middleware.OriginCheckMiddleware._disabled_warned_at", 0.0):
       # test code
   ```
   Or use autouse fixtures in `conftest.py` to reset between tests:
   Example: `conftest.py` lines 13-26 reset AuthMiddleware and rate limiter state

**What to Mock:**
- External API clients (Radarr, Sonarr, Lidarr) — use AsyncMock to return fixtures
- HTTP response objects when testing error handling paths
- Long-running operations (when time-dependent behavior needs control)

**What NOT to Mock:**
- Database connections — use real aiosqlite
- Config loading — test against actual TOML files
- File I/O — use `tmp_path` fixture for isolation
- Loguru logger — capture output instead

## Fixtures and Factories

**Test Data:**

1. **Settings Factory (`conftest.py`):**
   ```python
   def make_settings(
       radarr_url: str = "http://radarr:7878",
       radarr_enabled: bool = True,
       radarr_api_key: str = "radarr-test-key",
       ...
   ) -> Settings:
       """Build a Settings instance with sensible test defaults."""
       return Settings(
           general=general or GeneralConfig(),
           radarr={"Default": InstanceConfig(
               url=radarr_url,
               api_key=radarr_api_key,
               enabled=radarr_enabled,
               ...
           )},
           ...
       )
   ```
   Usage: `settings = make_settings(radarr_enabled=False)`
   Location: `tests/conftest.py` lines 29-76

2. **State Factory (`conftest.py`):**
   ```python
   def default_state(settings: Settings | None = None) -> TriggarrState:
       """Return a fresh default application state."""
       return _default_state(settings)
   ```
   Location: `tests/conftest.py` lines 79-89

3. **Async DB Helper (`test_tracking.py`):**
   ```python
   async def _init_db(tmp_path):
       """Create a test database with migrations applied, return (db, db_path)."""
       db_path = tmp_path / "test.db"
       db = await aiosqlite.connect(db_path)
       await init_db(db, db_path)
       return db, db_path
   ```
   Location: `test_tracking.py` lines 34-39

4. **Entry Insert Helper (`test_tracking.py`):**
   ```python
   async def _insert_entry(
       db,
       *,
       app: str = "Radarr",
       queue_type: str = "missing",
       item_name: str = "Test Item",
       outcome: str = "searched",
       timestamp: datetime | None = None,
   ) -> int:
       """Insert a search entry, optionally override timestamp, return its id."""
       ...
       return row_id
   ```
   Usage: `row_id = await _insert_entry(db, app="Sonarr", item_id=42, timestamp=...)`
   Location: `test_tracking.py` lines 42-73

5. **Grab Event Builder (`test_tracking.py`):**
   ```python
   def _grab(grab_id: int, date: datetime, source: str = "Release.1080p") -> GrabEvent:
       """Helper to build a GrabEvent with ISO date string."""
       return GrabEvent(
           id=grab_id,
           date=date.isoformat().replace("+00:00", "Z"),
           eventType="grabbed",
           sourceTitle=source,
       )
   ```
   Location: `test_tracking.py` lines 24-31

**Location:**
- Shared factories: `tests/conftest.py` (auto-discovered by pytest)
- Test-specific helpers: Defined at top of test file as `_helper()` function (prefixed with `_`)

## Coverage

**Requirements:** No hard requirement; coverage is tracked but not enforced

**View Coverage:**
```bash
uv run pytest tests/ --cov=triggarr --cov-report=html
```

**Gaps Noted:**
- Test count (241 tests) is comprehensive
- Focus areas: config migration, state persistence, database migrations, search cycles, tracking, middleware
- Some UI routes may have lower coverage (manual testing via FastAPI TestClient)

## Test Types

**Unit Tests:**
- Scope: Individual functions in isolation
- Approach: Mock external dependencies (HTTP clients, DB connections)
- Examples:
  - `test_config.py`: Config parsing, validation, SecretStr security
  - `test_logging.py`: Redaction sink, log format
  - `test_state.py`: State migration, merging, cleanup

**Integration Tests:**
- Scope: Multiple components working together (e.g., DB + config + state)
- Approach: Real dependencies where safe (SQLite, file I/O), mocked HTTP
- Examples:
  - `test_db.py`: Full migration workflow, insertion + retrieval
  - `test_tracking.py`: DB + tracking orchestrator + mocked Radarr/Sonarr clients
  - `test_middleware.py`: FastAPI middleware with TestClient

**E2E Tests:**
- Framework: Not explicitly used; integration tests with real TestClient serve this role
- Approach: `test_web.py` uses `TestClient` to test full HTTP request/response cycle
- No separate Playwright/Selenium tests (UI is htmx-based, tested via FastAPI routing)

## Common Patterns

**Async Testing:**
```python
async def test_radarr_grabbed(tmp_path):
    """Radarr entry with grab within window resolves to 'grabbed'."""
    db, _ = await _init_db(tmp_path)
    searched_at = datetime.now(UTC) - timedelta(minutes=30)
    row_id = await _insert_entry(db, app="Radarr", item_id=42, timestamp=searched_at)

    radarr = AsyncMock()
    grab_time = searched_at + timedelta(minutes=10)
    radarr.get_grab_history.return_value = [_grab(100, grab_time)]

    counts = await run_tracking_check(db, radarr, "Radarr", "Default", tracking_window_minutes=60)

    assert await _get_outcome(db, row_id) == "grabbed"
    await db.close()
```
Location: `test_tracking.py` lines 109-125

**Error Testing:**
```python
def test_instance_config_rejects_both_counts_zero_when_enabled():
    """InstanceConfig rejects both search counts = 0 when enabled."""
    with pytest.raises(ValidationError, match="At least one"):
        InstanceConfig(
            url="http://radarr:7878",
            api_key="test-key",
            enabled=True,
            search_missing_count=0,
            search_cutoff_count=0,
        )
```
Location: `test_config.py` lines 123-133

**Fixture Isolation:**
```python
@pytest.fixture(autouse=True)
def _reset_disabled_warned():
    """Reset AuthMiddleware._disabled_warned_at before each test."""
    AuthMiddleware._disabled_warned_at = 0.0
    yield
    AuthMiddleware._disabled_warned_at = 0.0
```
Location: `conftest.py` lines 13-18

**Database Query Verification:**
```python
async def _get_outcome(db, row_id: int) -> str:
    """Read the outcome column for a specific search_history row."""
    async with db.execute("SELECT outcome FROM search_history WHERE id = ?", (row_id,)) as cursor:
        row = await cursor.fetchone()
    return row[0]

# In test:
assert await _get_outcome(db, row_id) == "grabbed"
```
Location: `test_tracking.py` lines 76-80

## Recent Test Additions (v2.8)

**OriginCheckMiddleware CSRF Suite:**
- `test_middleware.py`: 15+ tests covering Origin/Referer validation, scheme comparison, suffix spoof detection
- Pins current behavior per defense document D-10, D-11

**Corrupt TOML Handling:**
- `test_config.py`: Tests for `_log_corrupt_config_and_exit()`, TOMLDecodeError handling
- Validates v2.2 migration detection with intentionally broken TOML

**Concurrent Save Stability:**
- `test_state.py`: Tests atomic write-then-rename, directory fsync durability
- Verifies state round-trip (save + load) preserves nested per-instance data

**Async Cleanup:**
- All async tests call `await db.close()` explicitly
- Fixtures use `yield` for setup/teardown
- No resource leaks from temp files (pytest auto-cleanup `tmp_path`)

## Running Tests

**All Tests:**
```bash
uv run pytest tests/ -x -q
```

**Specific Test File:**
```bash
uv run pytest tests/test_tracking.py -v
```

**Single Test:**
```bash
uv run pytest tests/test_tracking.py::test_radarr_grabbed -v
```

**With Output Capture (see print/log output):**
```bash
uv run pytest tests/ -s
```

**Coverage:**
```bash
uv run pytest tests/ --cov=triggarr --cov-report=term-missing
```

---

*Testing analysis: 2026-06-01*
