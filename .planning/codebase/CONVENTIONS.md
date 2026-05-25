# Coding Conventions

**Analysis Date:** 2026-05-25

## Naming Patterns

**Files:**
- Lowercase with underscores: `config.py`, `logging.py`, `search_engine.py`
- Module names reflect their primary function or domain
- Package directories (e.g., `clients/`, `models/`, `search/`, `web/`)

**Functions:**
- Lowercase with underscores: `load_settings()`, `get_config_path()`, `filter_monitored()`
- Public functions are regular: `def get_config_path() -> Path:`
- Private functions start with underscore: `def _atomic_toml_write()`, `def _is_v22_format()`
- Async functions use `async def`: `async def run_radarr_cycle()`, `async def get_wanted_missing()`
- Helper functions for internal module use prefixed with underscore: `_relative_time()`, `_sanitize_card_id()`

**Variables:**
- Lowercase with underscores: `config_path`, `search_interval`, `api_key`, `item_count`
- Constants in UPPERCASE: `COOKIE_MAX_AGE`, `APP_TYPES`, `_V22_FLAT_KEYS`
- Private module-level constants start with underscore: `_PKG_DIR`, `_jinja_env`

**Types:**
- PascalCase for classes: `Settings`, `InstanceConfig`, `GeneralConfig`, `AuthConfig`
- TypedDict names: `AppState`, `TriggarrState`
- Use type hints on all public function signatures

## Code Style

**Formatting:**
- Tool: `ruff` (configured in `pyproject.toml`)
- Line length: 120 characters
- Python target: 3.11+

**Linting:**
- Enabled rule sets: E (errors), F (pyflakes), I (imports), UP (upgrades), B (flake8-bugbear), SIM (simplify)
- Run: `uv run ruff check triggarr/ tests/`
- Format imports with ruff's `I` rule (import sorting)

**Type Hints:**
- Required on all public function signatures
- Avoid `Any` when a specific type is known
- Use `|` for union types (PEP 604): `str | None`, `dict[str, Any]`
- Use `from __future__ import annotations` at top of all modules for PEP 563 compatibility

**Async Functions:**
- Prefix with `async def` when the function contains `await`
- Never mark functions `async` if they contain no `await` calls
- Always `await` external calls (HTTP, database, file I/O)
- Wrap external `await` calls in try/except with meaningful error context

## Import Organization

**Order:**
1. `from __future__ import annotations` (if used)
2. Standard library (stdlib)
3. Third-party packages
4. Local imports from `triggarr` package

**Path Aliases:**
- None configured — use absolute imports from package root: `from triggarr.models.config import Settings`
- Internal imports use full paths: `from triggarr.clients.radarr import RadarrClient`

**Example (from `triggarr/search/engine.py`):**
```python
from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from datetime import UTC, datetime

import aiosqlite
import httpx
import pydantic
from loguru import logger

from triggarr.clients.lidarr import LidarrClient
from triggarr.db import insert_search_entry
from triggarr.models.config import Settings
from triggarr.state import TriggarrState
```

## Error Handling

**Patterns:**
- Specific exception catching: Never bare `except:` — always catch specific exceptions
- Example from `triggarr/clients/base.py`:
  ```python
  try:
      response = await self._client.request(method, path, **kwargs)
      response.raise_for_status()
      return response
  except (httpx.HTTPStatusError, httpx.TransportError) as exc:
      logger.warning("Retry failed: {exc}", exc=type(exc).__name__)
      raise
  ```
- HTTP errors: Catch `httpx.HTTPStatusError`, `httpx.HTTPError`, `httpx.TimeoutException`
- Validation errors: Catch `pydantic.ValidationError`
- Always log errors with loguru before re-raising
- Sanitize exception messages for logs (don't leak URLs, API keys, paths)

**Example from `triggarr/search/engine.py`:**
```python
def _sanitize_exc(exc: Exception) -> str:
    """Return a safe, type-based summary of an exception for storage."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    if isinstance(exc, httpx.TimeoutException):
        return "request timeout"
    return type(exc).__name__
```

## Logging

**Framework:** Loguru

**Usage:**
- Import: `from loguru import logger`
- Never use `print()` or `logging` module
- API keys are automatically redacted by `create_redacting_sink()` in `triggarr/logging.py`

**Patterns:**
```python
logger.info("Message with {var}", var=value)
logger.warning("Something unexpected: {path}", path=config_path)
logger.debug("Internal state: {state}", state=some_dict)
logger.exception("API call failed")  # Logs full traceback

# Never:
logger.info(f"API key: {api_key}")  # Would be logged unsanitized before redaction
```

**Log Levels:**
- `debug`: Internal state, detailed flow (cursor positions, batch slicing)
- `info`: Lifecycle events, config migration, connection validation
- `warning`: Non-fatal failures, retries, config issues
- `error`: Unrecoverable errors (logged at endpoint level)

**Secrets Redaction:**
- Secrets are automatically redacted by the custom sink before any output
- Covers both log messages AND exception tracebacks
- SecretStr values: Call `.get_secret_value()` only at initialization (HTTP client setup)

**Example from `triggarr/logging.py`:**
```python
def create_redacting_sink(secrets: list[str], stream: IO[str] = sys.stderr) -> Callable[[str], None]:
    """Create a loguru sink that redacts secrets from the full formatted output."""
    def sink(message: Any) -> None:
        text = str(message)
        for secret in secrets:
            if secret:
                text = text.replace(secret, "[REDACTED]")
        stream.write(text)
    return sink
```

## Comments

**When to Comment:**
- Complex algorithms: Explain the "why", not the "what"
- Non-obvious logic: Tag-filtering logic, batch capping, deduplication
- Workarounds: Mark with `# DEBT-XX` or `# SRCH-XX` markers for tracking

**Example from `triggarr/search/engine.py`:**
```python
def cap_batch_sizes(missing_count: int, cutoff_count: int, hard_max: int) -> tuple[int, int]:
    """Cap total batch sizes to a hard maximum, splitting proportionally."""
    if hard_max <= 0:
        return (missing_count, cutoff_count)
    total_requested = missing_count + cutoff_count
    if total_requested <= hard_max:
        return (missing_count, cutoff_count)
    # Proportional split, round down for missing, remainder to cutoff
    effective_missing = max(0, (missing_count * hard_max) // total_requested)
    effective_cutoff = hard_max - effective_missing
    return (effective_missing, effective_cutoff)
```

**JSDoc/Docstrings:**
- All public functions require docstrings
- Format: Google-style with Args, Returns, Raises
- Example from `triggarr/auth.py`:
  ```python
  def hash_password(plaintext: str) -> str:
      """Hash a plaintext password with bcrypt (12 rounds).
      
      Args:
          plaintext: The password to hash.
      
      Returns:
          Bcrypt hash string suitable for storage.
      
      Raises:
          ValueError: If password exceeds 72 bytes (bcrypt limit).
      """
  ```

**Inline Comments:**
- Used sparingly; prefer clear code over comments
- Useful for non-obvious intent: `# keep previous value`, `# wrap-around detected`
- Mark technical debt: `# DEBT-03: max resolved rows kept in search_history`

## Function Design

**Size:**
- Keep functions focused and testable (under 50 lines preferred)
- Pure functions (no side effects) for filtering/batching logic
- Async functions for I/O-bound operations (HTTP, database)

**Parameters:**
- Type hints required on all parameters
- Keyword-only arguments for optional parameters using `*` separator
- Example from `triggarr/web/routes.py`:
  ```python
  def _relative_time(dt: datetime | None, *, short_threshold: bool = False) -> str:
  ```

**Return Values:**
- Explicit return types required
- Return tuples for multiple values: `tuple[list, int]` for (batch, new_cursor)
- Use `| None` for optional returns: `str | None`

**Example (Pure Function):**
```python
def filter_monitored(items: list[dict]) -> list[dict]:
    """Filter out items where monitored is not True."""
    return [item for item in items if item.get("monitored", False)]
```

## Module Design

**Exports:**
- Public functions/classes exported directly from module
- Private functions/classes prefixed with underscore
- Example: `triggarr/config.py` exports `load_settings()`, `ensure_config()`, `generate_default_config()`

**File Organization:**
- Module docstring at top with purpose
- Imports grouped per PEP 8
- Helper functions before public functions
- Constants at module level

**Example Module Structure (`triggarr/auth.py`):**
```python
"""Authentication helpers: password hashing, cookie signing, and token generation."""

from __future__ import annotations

import secrets
import bcrypt
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # Constants

def hash_password(plaintext: str) -> str:  # Public functions
    ...

def verify_password(plaintext: str, hashed: str) -> bool:
    ...
```

## Data Handling

**Atomic Writes:**
- Used for config (TOML) and state (JSON) files
- Pattern: write to temp file, fsync, rename atomically
- Example from `triggarr/config.py`:
  ```python
  def _atomic_toml_write(path: Path, data: dict) -> None:
      """Write TOML data atomically using tempfile + fsync + rename."""
      dir_fd = None
      fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
      try:
          with os.fdopen(fd, "wb") as f:
              tomli_w.dump(data, f)
              f.flush()
              os.fsync(f.fileno())
          os.replace(tmp_path, path)
          dir_fd = os.open(path.parent, os.O_RDONLY)
          os.fsync(dir_fd)
      except Exception:
          with contextlib.suppress(OSError):
              os.unlink(tmp_path)
          raise
      finally:
          if dir_fd is not None:
              os.close(dir_fd)
  ```

**SecretStr Usage:**
- All API keys stored as `SecretStr` in config models
- Call `.get_secret_value()` ONLY when initializing HTTP clients
- Never log or repr a SecretStr directly
- Example from `triggarr/models/config.py`:
  ```python
  class InstanceConfig(BaseModel):
      api_key: SecretStr = SecretStr("")
  ```

**Validation:**
- Use Pydantic validators with `@model_validator` for custom logic
- Example from `triggarr/models/config.py`:
  ```python
  @model_validator(mode="after")
  def at_least_one_search_count(self) -> InstanceConfig:
      """Ensure at least one search count is positive when enabled."""
      if self.enabled and self.search_missing_count <= 0 and self.search_cutoff_count <= 0:
          msg = "At least one search count must be > 0 when enabled"
          raise ValueError(msg)
      return self
  ```

## Testing Integration

**Test File Locations:**
- Tests in `tests/` directory parallel to `triggarr/` package
- Example: `triggarr/search/engine.py` → `tests/test_search.py`

**Test Naming:**
- Test classes: `TestClassName` (each test class tests one function/behavior)
- Test methods: `test_description()` (describe what is being tested)
- Example from `tests/test_validation.py`:
  ```python
  class TestValidateArrUrl:
      def test_valid_http_url(self) -> None:
          ok, err = validate_arr_url("http://radarr:7878")
          assert ok is True
  ```

---

*Convention analysis: 2026-05-25*
