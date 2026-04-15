# Phase 54: Auth Config & Helpers - Pattern Map

**Mapped:** 2026-04-14
**Files analyzed:** 4 new/modified files
**Analogs found:** 4 / 4

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/models/config.py` (MODIFY) | model | config-validation | `triggarr/models/config.py` (InstanceConfig) | exact |
| `triggarr/auth.py` (NEW) | utility | transform | `triggarr/config.py` (pure helper functions) | role-match |
| `triggarr/startup.py` (MODIFY) | service | startup-orchestration | `triggarr/startup.py` (collect_secrets) | exact |
| `tests/test_auth.py` (NEW) | test | unit-test | `tests/test_config.py` | exact |
| `pyproject.toml` (MODIFY) | config | dependency | `pyproject.toml` | exact |

## Pattern Assignments

### `triggarr/models/config.py` -- Add AuthConfig model (model, config-validation)

**Analog:** `triggarr/models/config.py` -- `InstanceConfig` class

**Imports pattern** (lines 1-9):
```python
from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, SecretStr, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, TomlConfigSettingsSource
```

**Nested BaseModel pattern** (lines 38-65) -- follow `InstanceConfig` structure for `AuthConfig`:
```python
class InstanceConfig(BaseModel):
    """Configuration for a single *arr instance.

    Each named instance holds its own URL, API key, schedule, and batch sizes.
    Multiple instances can be configured per app type (radarr, sonarr).
    """

    url: str = ""
    api_key: SecretStr = SecretStr("")
    enabled: bool = False

    # Search tuning (sensible defaults -- override in config to customize)
    search_interval: int = 30  # Minutes between search cycles
    search_missing_count: int = 5  # Missing items to search per cycle
    search_cutoff_count: int = 5  # Cutoff items to search per cycle

    # Tag filtering (empty = search all items, no filtering)
    missing_tag: str = ""  # Tag name for missing queue filter
    cutoff_tag: str = ""  # Tag name for cutoff queue filter

    @model_validator(mode="after")
    def at_least_one_search_count(self) -> InstanceConfig:
        """Ensure at least one search count is positive when instance is enabled."""
        if self.enabled and self.search_missing_count <= 0 and self.search_cutoff_count <= 0:
            msg = "At least one of search_missing_count or search_cutoff_count must be > 0 when enabled"
            raise ValueError(msg)
        return self
```

**Settings field registration pattern** (lines 82-97) -- add `auth: AuthConfig = AuthConfig()` following same style:
```python
class Settings(BaseSettings):
    general: GeneralConfig = GeneralConfig()
    radarr: dict[str, InstanceConfig] = {}
    sonarr: dict[str, InstanceConfig] = {}
    lidarr: dict[str, InstanceConfig] = {}
```

**Property helper pattern** (lines 109-116) -- follow `has_enabled_app` style for `needs_setup` / `is_disabled`:
```python
    @property
    def has_enabled_app(self) -> bool:
        """Check if at least one instance across any app type is enabled with a URL."""
        for app_type in APP_TYPES:
            for cfg in getattr(self, app_type).values():
                if cfg.enabled and cfg.url.strip():
                    return True
        return False
```

---

### `triggarr/auth.py` -- New auth helper module (utility, transform)

**Analog:** `triggarr/config.py` -- pure helper functions with docstrings

**Module docstring pattern** (line 1):
```python
"""TOML configuration loading, default config generation, and v2.2 migration."""
```

**Future annotations pattern** (line 3):
```python
from __future__ import annotations
```

**Function docstring style** (lines 92-101) -- Google-style with Args/Returns sections:
```python
def _atomic_toml_write(path: Path, data: dict) -> None:
    """Write TOML data to a file atomically using tempfile + fsync + rename.

    On failure (e.g. serialization error), the temp file is cleaned up
    so no orphaned files remain on disk.

    Args:
        path: Destination file path.
        data: TOML-serializable dict.
    """
```

**No analog for crypto functions** -- use RESEARCH.md patterns (bcrypt/itsdangerous). Key convention: functions accept and return `str`, encoding to/from bytes is internal to the helper.

---

### `triggarr/startup.py` -- Extend collect_secrets() (service, startup-orchestration)

**Analog:** `triggarr/startup.py` -- `collect_secrets()` function itself

**Exact function to extend** (lines 49-68):
```python
def collect_secrets(settings: Settings) -> list[str]:
    """Extract API key values from all configured instances.

    This is the ONLY place where ``get_secret_value()`` is called for
    logging purposes.  The returned list is passed to the redaction
    filter so secrets never appear in log output.

    Args:
        settings: Loaded application settings.

    Returns:
        List of non-empty secret strings for the redaction filter.
    """
    secrets: list[str] = []
    for app_type in APP_TYPES:
        for cfg in getattr(settings, app_type).values():
            value = cfg.api_key.get_secret_value()
            if value:
                secrets.append(value)
    return secrets
```

**Extension point:** After the existing `for app_type` loop (line 67), add auth secret gathering following the same `get_secret_value()` + empty-check pattern.

---

### `tests/test_auth.py` -- New unit tests (test, unit-test)

**Analog:** `tests/test_config.py`

**Imports pattern** (lines 1-22):
```python
"""Tests for config loading, default generation, validation, and SecretStr security."""

from __future__ import annotations

import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
import tomli_w
from pydantic import ValidationError

from triggarr.config import (
    _atomic_toml_write,
    load_settings,
)
from triggarr.models.config import GeneralConfig, InstanceConfig, Settings
```

**SecretStr masking test pattern** (lines 314-320):
```python
def test_instance_config_secret_str_hidden() -> None:
    """SecretStr api_key value does not appear in str(), repr(), or model_dump_json() of InstanceConfig."""
    secret = "super-secret-instance-key"
    cfg = InstanceConfig(url="http://localhost:7878", api_key=secret, enabled=True)
    assert secret not in str(cfg)
    assert secret not in repr(cfg)
    assert secret not in cfg.model_dump_json()
```

**Default value test pattern** (lines 150-154):
```python
def test_skip_unreleased_defaults_true() -> None:
    """GeneralConfig().skip_unreleased defaults to True."""
    assert GeneralConfig().skip_unreleased is True
```

**TOML round-trip test pattern** (lines 626-649):
```python
def test_toml_round_trip(tmp_path: Path) -> None:
    """TOML round-trip: load migrated config, serialize back, reload -- same values."""
    config_file = tmp_path / "triggarr.toml"
    config_file.write_text(V22_RADARR_SONARR_TOML)

    detect_and_migrate_v22(config_file)

    with open(config_file, "rb") as f:
        data1 = tomllib.load(f)

    round_trip_file = tmp_path / "round_trip.toml"
    with open(round_trip_file, "wb") as f:
        tomli_w.dump(data1, f)

    with open(round_trip_file, "rb") as f:
        data2 = tomllib.load(f)

    assert data1["radarr"]["Default"]["url"] == data2["radarr"]["Default"]["url"]
```

**Test naming convention:** `test_<subject>_<behavior>` with docstring explaining what is being tested. One assertion concept per test.

---

### `pyproject.toml` -- Add dependencies (config, dependency)

**Analog:** `pyproject.toml` itself

**Dependency addition point** (lines 10-22):
```python
dependencies = [
    "pydantic-settings[toml]",
    "httpx",
    "loguru",
    "tomli-w",
    "fastapi",
    "uvicorn[standard]",
    "apscheduler>=3.11,<4",
    "jinja2",
    "aiofiles",
    "aiosqlite",
    "python-multipart",
]
```

Add `"bcrypt"` and `"itsdangerous"` to the dependencies list. Follow existing style: lowercase, no version pins for simple deps (only `apscheduler` has a pin).

---

## Shared Patterns

### SecretStr Discipline
**Source:** `triggarr/models/config.py` line 46, `triggarr/web/routes.py` lines 140-153
**Apply to:** `AuthConfig` model fields, `collect_secrets()` extension, future TOML write paths

Pattern: Declare as `SecretStr = SecretStr("")`. Only call `.get_secret_value()` at:
1. TOML serialization (`_settings_to_dict` in routes.py)
2. HTTP client init (existing pattern in startup.py line 125)
3. Crypto operations (new: passing to bcrypt/itsdangerous)

```python
# Declaration (models/config.py):
api_key: SecretStr = SecretStr("")

# Extraction for TOML write (web/routes.py line 152):
d["api_key"] = cfg.api_key.get_secret_value()  # TOML serialization extraction

# Extraction for log redaction (startup.py line 65):
value = cfg.api_key.get_secret_value()
if value:
    secrets.append(value)
```

### Module Docstring + Future Annotations
**Source:** Every Python file in `triggarr/`
**Apply to:** `triggarr/auth.py`, `tests/test_auth.py`

```python
"""Module-level docstring describing purpose."""

from __future__ import annotations
```

### Google-style Docstrings
**Source:** `triggarr/startup.py` lines 49-68, `triggarr/config.py` lines 92-101
**Apply to:** All functions in `triggarr/auth.py`

Format: Summary line, blank line, optional detail paragraph, `Args:` section, `Returns:` section. Use RST-style double backticks for code references in docstrings.

### Test Structure
**Source:** `tests/test_config.py`
**Apply to:** `tests/test_auth.py`

- Module docstring
- `from __future__ import annotations`
- Section separators: `# ---------------------------------------------------------------------------`
- Test function naming: `test_<subject>_<behavior>`
- One-line docstring per test explaining the assertion
- `tmp_path` fixture for file I/O tests
- `pytest.raises(ExceptionType, match="substring")` for error tests

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `triggarr/auth.py` (crypto functions) | utility | transform | No crypto/auth code exists in codebase yet. Use RESEARCH.md Pattern 2 (bcrypt/itsdangerous wrappers). Module structure follows `triggarr/config.py` conventions. |

## Metadata

**Analog search scope:** `triggarr/`, `tests/`
**Files scanned:** 6 analog files read in full
**Pattern extraction date:** 2026-04-14
