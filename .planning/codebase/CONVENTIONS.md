# Coding Conventions

**Analysis Date:** 2026-06-01

## Naming Patterns

**Files:**
- Lowercase with underscores: `config.py`, `state.py`, `tracking.py`
- Test files: `test_*.py` (e.g., `test_config.py`, `test_middleware.py`)
- Private/internal modules: `_migrate_v22_to_v23()`, `_atomic_toml_write()`, `_sanitize_exc()`
- Directories: Lowercase, plural for collections: `tests/`, `models/`, `clients/`, `web/`

**Functions:**
- Async search/tracking functions use clear action verbs: `run_radarr_cycle()`, `run_tracking_check()`, `run_migrations()`
- Helper functions prefixed with `_`: `_parse_timestamp()`, `_determine_outcome()`, `_default_instance_state()`
- Type/class initialization: `make_settings()`, `make_app()` (test factories)
- Private query functions: `_get_outcome()`, `_get_stat()` (test database helpers)
- Camel case reserved for class methods: `model_validate()`, `get_secret_value()`, `get_paginated()`

**Variables:**
- Snake case throughout: `config_path`, `search_window_minutes`, `raw_api_key`, `instance_id`
- Boolean flags end with descriptive suffix: `renamed`, `window_expired`, `has_enabled_app`
- Loop accumulators/counters: `counts`, `rows`, `groups`, `entries`
- Abbreviated where clear: `exc` (exception), `db` (database), `app` (application), `msg` (message)

**Types:**
- Pydantic models use PascalCase: `Settings`, `InstanceConfig`, `AppState`, `TriggarrState`, `GrabEvent`
- TypedDict models use PascalCase: `AppState`, `TriggarrState` (defined in `triggarr/state.py`)
- Generic type hints after imports: `dict[str, Any]`, `list[dict]`, `tuple[str | None, str]`

## Code Style

**Formatting:**
- Tool: `ruff` (via `uv run ruff check triggarr/ tests/`)
- Line length: 120 characters (configured in `pyproject.toml`)
- Target version: Python 3.11+

**Linting:**
- Rules enabled: `E` (errors), `F` (Pyflakes), `I` (isort imports), `UP` (pyupgrade), `B` (bugbear), `SIM` (simplify)
- Config location: `pyproject.toml` under `[tool.ruff]`
- No bare `except:` — always catch specific exception types
- Imports organized by ruff isort plugin (E/F/I/UP/B/SIM rules)

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first in module files)
2. Standard library: `import os`, `import sys`, `from pathlib import Path`, `from typing import TYPE_CHECKING`
3. Third-party: `import httpx`, `import pydantic`, `from loguru import logger`, `import aiosqlite`
4. Local: `from triggarr.config import load_settings`, `from triggarr.models.config import Settings`
5. Conditional imports under `if TYPE_CHECKING:` block for forward references

**Path Aliases:**
- No path aliases in use; all imports are explicit relative paths from `triggarr/` root
- Test imports: `from tests.conftest import make_settings`, `from triggarr.clients.base import ArrClient`

## Error Handling

**Patterns:**

1. **HTTP/API Errors:**
   - Catch and log: `except (httpx.HTTPError, pydantic.ValidationError) as exc:`
   - Log structured messages with context: `"Tracking[{inst}]: failed to fetch grab history..."`
   - For HTTPStatusError, extract status code: `f"HTTP {exc.response.status_code}"`
   - Never log full request/response bodies (secrets in headers)
   - Example from `triggarr/tracking.py` lines 62-76

2. **Config Loading Errors:**
   - TOML parsing: Catch `tomllib.TOMLDecodeError` and `UnicodeDecodeError` separately
   - Call dedicated handler `_log_corrupt_config_and_exit()` to provide user-friendly error message
   - Path-only disclosure — never log config contents
   - Example: `triggarr/config.py` lines 361-373

3. **Database/File Operations:**
   - Catch `OSError` for file I/O, log with context and path
   - Use context managers (`with`, `async with`) to ensure cleanup
   - For temp file cleanup failures, log but don't re-raise FileNotFoundError
   - Example: `triggarr/config.py` lines 120-142

4. **Pydantic Validation:**
   - Validation errors bubble up — do NOT catch and suppress
   - Let `ValidationError` surface for debugging (operator needs to fix config)
   - Tests explicitly check: `with pytest.raises(ValidationError, match="..."):`

5. **Search Cycle Errors:**
   - Non-fatal errors (network, validation) logged but cycle continues
   - Caught as tuple: `except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)`
   - Count errors for dashboard visibility
   - Example: `triggarr/search/engine.py` tracks `error_count` in cycle returns

## Logging

**Framework:** loguru (never use `print()` or `logging` module)

**Setup:** `triggarr/logging.py` configures a custom redacting sink

**Patterns:**

- Initialize with `from loguru import logger` at module top
- Structured logging with named parameters: `logger.info("Config loaded: {path}", path=config_path)`
- Levels used: `debug` (dev/trace), `info` (lifecycle), `warning` (recoverable issues), `error` (failures)
- Secret redaction automatic via custom sink — no need to mask in code
- Never call `print()` for output
- Log buffer captured separately for web UI (see `triggarr/log_buffer.py`)

Examples:
- `logger.info("Schema migration complete (now v{v})", v=target)` (line 112, `triggarr/db.py`)
- `logger.warning("Tracking[{inst}]: failed to fetch ...", inst=instance_id, ...)` (line 65, `triggarr/tracking.py`)
- `logger.error("Config write failed: {path} - {exc}", path=path, exc=exc)` (line 131, `triggarr/config.py`)

## Comments

**When to Comment:**
- Document non-obvious algorithmic choices (e.g., v2.2 config migration detection logic)
- Reference external constraints (e.g., SAFETY-01b pending row cap multiplier)
- Explain why, not what (code shows what; comments explain why)
- Mark temporary workarounds with task/issue references

**JSDoc/TSDoc:**
- All public functions documented with docstrings (Google-style)
- Args section: parameter types and purpose
- Returns section: type and description
- Example from `triggarr/config.py` lines 230-235:
  ```python
  def generate_default_config(config_path: Path) -> None:
      """Write a commented default TOML config template to disk atomically.

      Args:
          config_path: Destination path for the config file.
      """
  ```

## Function Design

**Size:** 
- Preference for single-responsibility functions
- Migration functions like `_migrate_v7()` can be longer (~100 lines) due to SQL complexity
- Search cycle functions `run_radarr_cycle()` organized into clear sections with blank lines

**Parameters:**
- Type hints on all parameters: `config_path: Path`, `batch_size: int`
- Keyword-only args for optional parameters in orchestrator functions: `run_tracking_check(..., tracking_window_minutes: int)`
- Factories use keyword args with sensible defaults: `make_settings(radarr_url: str = "http://radarr:7878", ...)`

**Return Values:**
- Explicit return types on all functions: `-> dict[str, int]`, `-> TriggarrState`, `-> None`
- Tuple unpacking for multi-value returns: `outcome, detail, stat_increments = _determine_outcome(...)`
- Optional returns documented: `-> str | None`, `-> Path | None`

## Module Design

**Exports:**
- Public functions at module level (no wrapper classes unless necessary)
- Internal helpers prefixed with `_` to signal non-public API
- Each module has a docstring explaining purpose: `"""SQLite-backed search history persistence. ..."""`
- Example: `triggarr/config.py` exports `load_settings()`, `generate_default_config()`, `ensure_config()`; `_atomic_toml_write()` is internal

**Barrel Files:**
- Minimal use; each module is imported directly by name
- `tests/conftest.py` re-exports test helpers: `make_settings()`, `default_state()`
- No wildcard imports (`from module import *`)

## API Key Security

**SecretStr Pattern:**
- All API keys stored in `pydantic.SecretStr` fields (e.g., `api_key: SecretStr` in `InstanceConfig`)
- Call `.get_secret_value()` ONLY when initializing HTTP client: `client = httpx.AsyncClient(headers={"X-Api-Key": config.api_key.get_secret_value()})`
- Never store return value in variable or log it
- Tests verify: `assert secret not in str(config)` (line 118, `test_config.py`)

## Atomic File Writes

**Pattern (SAFETY-04):**
```python
# 1. Create temp file in same directory as target
fd, tmp_path = tempfile.mkstemp(dir=parent_dir, suffix=".tmp")
# 2. Write and fsync data
with os.fdopen(fd, "wb") as f:
    data.dump(f)
    f.flush()
    os.fsync(f.fileno())
# 3. Atomic replace
os.replace(tmp_path, target_path)
# 4. fsync parent directory for durability
dir_fd = os.open(parent_path, os.O_RDONLY)
os.fsync(dir_fd)
os.close(dir_fd)
```

Applied in:
- `triggarr/config.py` `_atomic_toml_write()` (lines 94-162)
- `triggarr/state.py` `save_state()` (lines 185-257)
- `triggarr/config.py` `generate_default_config()` (lines 230-297)

## Python Version & Future Imports

**Version:** 3.11+

**Future Imports:**
- All modules start with `from __future__ import annotations` to enable PEP 563 postponed evaluation
- Allows forward references without `TYPE_CHECKING` block in many cases
- Necessary for recursive types and self-references

Example: `triggarr/state.py` line 11

---

*Convention analysis: 2026-06-01*
