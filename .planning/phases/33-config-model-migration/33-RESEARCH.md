# Phase 33: Config Model & Migration - Research

**Researched:** 2026-03-09
**Domain:** Pydantic config models, TOML serialization, config migration
**Confidence:** HIGH

## Summary

Phase 33 transforms Triggarr's flat single-instance config model (`Settings.radarr: ArrConfig`, `Settings.sonarr: ArrConfig`) into a multi-instance model where each app type holds a `dict[str, InstanceConfig]` of named instances. The TOML format uses named subtables (`[radarr."4K Radarr"]`) which both `tomllib` and `tomli_w` handle correctly -- verified via live round-trip testing.

The migration from v2.2 format is straightforward: detect flat keys (`url`, `api_key`, `enabled`) directly under `[radarr]`/`[sonarr]` sections, wrap them in a `"Default"` instance, backup the original file, and write the new format. The detection heuristic is reliable because v2.3 format never has those keys at the top level of a section -- they're always nested under instance name keys.

This phase is model-and-file-only: no scheduler changes, no state migration (Phase 34), no UI changes (Phase 39). The scope is tightly bounded to `triggarr/models/config.py`, `triggarr/config.py`, and their tests.

**Primary recommendation:** Use `dict[str, InstanceConfig]` for the radarr/sonarr fields on Settings, with a Pydantic model_validator to enforce max 5 instances and unique names. Add a `detect_and_migrate_v22()` function to `config.py` that runs before `load_settings()`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
1. Multi-instance management is web UI only. Users do not hand-edit TOML to manage instances. The `[general]` section remains hand-editable in TOML for power users.
2. TOML config shape: readable nested format (e.g., named table sections like `[radarr."4K Radarr"]`) rather than array-of-tables.
3. Instance identification: display name as key. No separate internal ID. Names must be unique within same app type. Maximum 5 instances per app type.
4. Default config: empty instances with comment directing users to web UI.
5. Comments dropped on UI save -- acceptable since `tomli_w` does not preserve comments.
6. Migration: auto-detect v2.2 format, migrate to multi-instance with instance name "Default", backup to `triggarr.toml.bak`, log migration, show one-time banner in web UI.

### Claude's Discretion
(None captured -- all decisions locked)

### Deferred Ideas (OUT OF SCOPE)
(None captured)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INST-01 | User can configure multiple named Radarr instances with independent URL, API key, schedule, and batch sizes | `dict[str, InstanceConfig]` on Settings model, each InstanceConfig holds all per-instance fields. TOML named subtables verified working. |
| INST-02 | User can configure multiple named Sonarr instances with independent URL, API key, schedule, and batch sizes | Same pattern as INST-01, symmetric for sonarr field. |
| INST-04 | Existing single-instance config auto-migrates to multi-instance format on upgrade | Detection heuristic (flat keys under section = v2.2) verified reliable. Wrap in "Default" instance, backup original. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.x (already installed) | Config model validation | Already used for ArrConfig/Settings |
| pydantic-settings[toml] | already installed | TOML settings source | Already used for Settings loading |
| tomllib | stdlib (3.11+) | TOML parsing | Already used in config.py |
| tomli-w | already installed | TOML writing | Already used in routes.py for config save |

### Supporting
No new dependencies needed. All required libraries are already in the project.

**Installation:**
```bash
# No new packages needed
```

## Architecture Patterns

### Recommended Model Structure

```python
# triggarr/models/config.py

class InstanceConfig(BaseModel):
    """Configuration for a single *arr instance."""
    url: str = ""
    api_key: SecretStr = SecretStr("")
    enabled: bool = False
    search_interval: int = 30
    search_missing_count: int = 5
    search_cutoff_count: int = 5

    @model_validator(mode="after")
    def at_least_one_search_count(self) -> InstanceConfig:
        if self.enabled and self.search_missing_count <= 0 and self.search_cutoff_count <= 0:
            msg = "At least one of search_missing_count or search_cutoff_count must be > 0 when enabled"
            raise ValueError(msg)
        return self

class Settings(BaseSettings):
    general: GeneralConfig = GeneralConfig()
    radarr: dict[str, InstanceConfig] = {}
    sonarr: dict[str, InstanceConfig] = {}

    @model_validator(mode="after")
    def validate_instances(self) -> Settings:
        for app_type in ("radarr", "sonarr"):
            instances = getattr(self, app_type)
            if len(instances) > 5:
                msg = f"Maximum 5 {app_type} instances allowed"
                raise ValueError(msg)
        return self

    @property
    def has_enabled_app(self) -> bool:
        for app_type in ("radarr", "sonarr"):
            for cfg in getattr(self, app_type).values():
                if cfg.enabled and cfg.url.strip():
                    return True
        return False
```

### Pattern 1: Rename ArrConfig to InstanceConfig
**What:** Rename `ArrConfig` to `InstanceConfig` to reflect its new role as per-instance config rather than per-app config.
**When to use:** This phase -- the rename clarifies semantics.
**Impact:** `ArrConfig` is referenced in `config.py`, `routes.py`, `conftest.py`, and tests. All references must update. Keep `ArrConfig` as a deprecated alias during this phase if needed for incremental migration, but since Phase 33 is self-contained, a clean rename is preferred.

### Pattern 2: v2.2 Detection and Migration
**What:** Before loading settings, read raw TOML, check if it's v2.2 format, and if so, migrate in-place with backup.
**When to use:** In `ensure_config()` or a new `migrate_config_if_needed()` called before `load_settings()`.

```python
def is_v22_format(data: dict) -> bool:
    """Check if TOML data uses v2.2 flat format."""
    for app in ("radarr", "sonarr"):
        section = data.get(app, {})
        if "url" in section or "api_key" in section or "enabled" in section:
            return True
    return False

def migrate_v22_to_v23(data: dict) -> dict:
    """Convert v2.2 flat config to v2.3 multi-instance format."""
    migrated = {"general": data.get("general", {})}
    for app in ("radarr", "sonarr"):
        section = data.get(app, {})
        if section:
            migrated[app] = {"Default": section}
        else:
            migrated[app] = {}
    return migrated
```

### Pattern 3: Config Serialization for tomli_w
**What:** When serializing Settings to TOML for disk write, SecretStr values must be extracted.
**When to use:** In save_settings route and migration write.

```python
def settings_to_toml_dict(settings: Settings) -> dict:
    """Convert Settings to a plain dict suitable for tomli_w.dumps()."""
    result = {"general": settings.general.model_dump()}
    for app_type in ("radarr", "sonarr"):
        instances = getattr(settings, app_type)
        result[app_type] = {}
        for name, cfg in instances.items():
            dumped = cfg.model_dump()
            dumped["api_key"] = cfg.api_key.get_secret_value()
            result[app_type][name] = dumped
    return result
```

### Pattern 4: Default Config Template (New Format)
**What:** New default config for fresh installs has empty instance sections with a comment.

```
# Triggarr Configuration

[general]
# Log level: debug, info, warning, error
log_level = "info"
# ... (same commented defaults as before)

# Instance configuration is managed through the web UI.
# Add your first Radarr or Sonarr instance at: http://<host>:8080/settings

[radarr]
# Instances added via web UI will appear here

[sonarr]
# Instances added via web UI will appear here
```

### Pattern 5: Migration Banner Flag
**What:** After migration, set a flag so the web UI can show a one-time banner.
**When to use:** Migration writes a marker file or adds a field to state.
**Recommendation:** Use a simple marker file `triggarr.migrated` in the config dir. The web UI checks for it, shows the banner, and deletes it on dismiss. This avoids polluting config or state with UI concerns.

### Anti-Patterns to Avoid
- **Storing instance names as separate fields alongside config:** Don't add a `name` field to InstanceConfig -- the dict key IS the name. Duplicating it creates sync issues.
- **Array-of-tables (`[[radarr]]`):** Decision locked to named subtables. Array-of-tables loses the name as a structural key and requires an explicit `name` field.
- **Migrating state in this phase:** State migration is Phase 34. Config migration here should NOT touch `state.json`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TOML parsing/writing | Custom parser | tomllib + tomli_w | Already in project, handles edge cases (quoted keys, etc.) |
| Config validation | Manual checks | Pydantic model_validator | Already established pattern, catches errors before disk write |
| Atomic file writes | Custom logic | Existing tempfile+fsync+replace pattern | Already proven in codebase, copy the pattern |

**Key insight:** The existing codebase already has all the infrastructure needed. This phase is about reshaping models and adding migration logic, not introducing new tooling.

## Common Pitfalls

### Pitfall 1: Breaking Downstream Accessors
**What goes wrong:** Code like `settings.radarr.url` (used in scheduler, startup, engine, routes) breaks because `settings.radarr` is now a dict, not an ArrConfig.
**Why it happens:** Existing code assumes single-instance flat access.
**How to avoid:** This phase should NOT update downstream consumers (scheduler, engine, startup). Those are Phase 34+ concerns. However, the Settings model must provide backward-compatible access OR downstream code must be updated in parallel. **Recommendation:** Since Phase 34 handles per-instance scheduling, this phase should focus only on the model and config file operations. Add helper methods to Settings (e.g., `get_all_instances(app_type)`, `get_enabled_instances(app_type)`) but leave actual consumer refactoring to Phase 34.
**Warning signs:** Import errors or attribute errors in scheduler/engine code.

### Pitfall 2: SecretStr Leaking During Migration
**What goes wrong:** API keys appear in logs or backup files during migration.
**Why it happens:** `model_dump()` returns `SecretStr('**********')`, not the actual value.
**How to avoid:** When writing migrated config to disk, use `cfg.api_key.get_secret_value()`. When logging migration, never log the raw TOML data.
**Warning signs:** `SecretStr('**********')` appearing in TOML files.

### Pitfall 3: Migration Runs Every Startup
**What goes wrong:** Migration logic runs even after already migrated.
**Why it happens:** Detection logic doesn't account for already-migrated config.
**How to avoid:** The detection heuristic is reliable -- if `url`/`api_key`/`enabled` exist directly under `[radarr]`/`[sonarr]`, it's v2.2. After migration, those keys are nested under instance names, so detection returns False. No marker file needed for migration detection itself.
**Warning signs:** Backup file being recreated on every restart.

### Pitfall 4: Empty Sections in TOML
**What goes wrong:** `tomli_w.dumps({"radarr": {}})` produces `[radarr]\n` which is valid but may confuse users reading the file.
**Why it happens:** Empty dict serializes as empty table.
**How to avoid:** This is acceptable per decision #1 (TOML is machine-managed for instances). The default template uses comments to explain.

### Pitfall 5: Config Path Module-Level Constants
**What goes wrong:** Tests that need different config paths fail because `CONFIG_PATH` is set at import time.
**Why it happens:** Module-level constants evaluated once.
**How to avoid:** Continue the existing pattern: functions accept `config_path` parameters, tests pass `tmp_path`. This is already established.

## Code Examples

### v2.2 Config Detection and Migration (Verified Pattern)
```python
# Source: Live testing with tomllib + tomli_w in this project
import tomllib
import tomli_w
import shutil
from pathlib import Path
from loguru import logger

def detect_and_migrate_v22(config_path: Path) -> bool:
    """Detect v2.2 config format and migrate to v2.3 if needed.

    Returns True if migration was performed.
    """
    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    if not _is_v22_format(data):
        return False

    # Backup original
    backup_path = config_path.with_suffix(".toml.bak")
    shutil.copy2(config_path, backup_path)
    logger.info("Config backup saved to {}", backup_path)

    # Migrate
    migrated = _migrate_v22_to_v23(data)

    # Write migrated config atomically
    _atomic_write_toml(config_path, migrated)

    logger.info("Config migrated from v2.2 to v2.3 multi-instance format")
    return True

def _is_v22_format(data: dict) -> bool:
    for app in ("radarr", "sonarr"):
        section = data.get(app, {})
        if "url" in section or "api_key" in section or "enabled" in section:
            return True
    return False

def _migrate_v22_to_v23(data: dict) -> dict:
    migrated = {"general": data.get("general", {})}
    for app in ("radarr", "sonarr"):
        section = data.get(app, {})
        if section:
            migrated[app] = {"Default": section}
        else:
            migrated[app] = {}
    return migrated
```

### TOML Round-Trip Verified
```python
# Source: Live testing in project environment
# Input TOML:
#   [radarr."4K Radarr"]
#   url = "http://radarr4k:7878"
#   api_key = "key1"
#   enabled = true
#
# Parses to: {"radarr": {"4K Radarr": {"url": "...", "api_key": "...", "enabled": true}}}
# Serializes back to identical TOML structure via tomli_w.dumps()
# Confidence: HIGH -- verified in this project's Python environment
```

### Pydantic dict[str, InstanceConfig] Verified
```python
# Source: Live testing in project environment
# Settings(radarr={"4K Radarr": {...}, "Default": {...}})
# correctly creates dict[str, InstanceConfig]
# Pydantic validates each instance independently
# Empty dict {} is valid (no instances configured yet)
# Confidence: HIGH -- verified in this project's Python environment
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Settings.radarr: ArrConfig` (single flat) | `Settings.radarr: dict[str, InstanceConfig]` (named multi) | This phase | All downstream consumers need updating (Phase 34+) |
| `ArrConfig` name | `InstanceConfig` name | This phase | Clearer semantics for multi-instance world |
| Comments in default config guiding TOML editing | Comments directing to web UI | This phase | Reflects UI-managed instance workflow |

## Open Questions

1. **How should `has_enabled_app` and downstream accessors work during the transition between Phase 33 and Phase 34?**
   - What we know: Phase 33 changes the model shape, Phase 34 updates scheduler/engine to use it.
   - What's unclear: Between phases, the app may not start if scheduler code expects `settings.radarr.url` but gets a dict.
   - Recommendation: Phase 33 must include enough shim/helper methods on Settings that the app still starts (even if it doesn't schedule anything). Alternatively, treat Phase 33 + 34 as a single atomic change that must both land before the app works. **The planner should decide this.**

2. **Migration banner implementation detail**
   - What we know: Decision says "show one-time banner in web UI indicating migration occurred."
   - What's unclear: Best mechanism for a one-time flag (marker file vs state field vs config field).
   - Recommendation: Marker file `config_dir / ".migrated"` -- simple, no schema pollution. Web UI reads it, shows banner, deletes on dismiss. But this is a minor detail the planner can decide.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_config.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INST-01 | Multiple named Radarr instances in Settings model | unit | `uv run pytest tests/test_config.py -x -q -k "multi_instance_radarr"` | Needs new tests |
| INST-02 | Multiple named Sonarr instances in Settings model | unit | `uv run pytest tests/test_config.py -x -q -k "multi_instance_sonarr"` | Needs new tests |
| INST-01/02 | Max 5 instances validation | unit | `uv run pytest tests/test_config.py -x -q -k "max_instances"` | Needs new tests |
| INST-01/02 | Duplicate name rejection (same app type) | unit | `uv run pytest tests/test_config.py -x -q -k "duplicate_name"` | Needs new tests |
| INST-04 | v2.2 format detection | unit | `uv run pytest tests/test_config.py -x -q -k "detect_v22"` | Needs new tests |
| INST-04 | v2.2 to v2.3 migration | unit | `uv run pytest tests/test_config.py -x -q -k "migrate_v22"` | Needs new tests |
| INST-04 | Backup created on migration | unit | `uv run pytest tests/test_config.py -x -q -k "backup"` | Needs new tests |
| INST-04 | Already-migrated config not re-migrated | unit | `uv run pytest tests/test_config.py -x -q -k "no_remigrate"` | Needs new tests |
| INST-01/02 | TOML round-trip (load and save multi-instance) | unit | `uv run pytest tests/test_config.py -x -q -k "toml_roundtrip"` | Needs new tests |
| INST-01/02 | SecretStr not leaked in serialized TOML | unit | `uv run pytest tests/test_config.py -x -q -k "secret"` | Partially exists |
| INST-01/02 | has_enabled_app works with multi-instance | unit | `uv run pytest tests/test_config.py -x -q -k "has_enabled"` | Needs update |
| INST-04 | Default config for fresh install (empty instances) | unit | `uv run pytest tests/test_config.py -x -q -k "default_config"` | Needs update |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_config.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] New test functions for multi-instance model validation (INST-01, INST-02)
- [ ] New test functions for v2.2 detection and migration (INST-04)
- [ ] Update existing `test_config.py` tests for new model shape
- [ ] Update `conftest.py` `make_settings()` for new model shape

## Sources

### Primary (HIGH confidence)
- Live round-trip testing with tomllib + tomli_w in project environment -- verified named subtable format works
- Live Pydantic testing -- verified `dict[str, InstanceConfig]` pattern works
- Direct code reading of `triggarr/models/config.py`, `triggarr/config.py`, `triggarr/web/routes.py`

### Secondary (MEDIUM confidence)
- Pydantic BaseModel documentation for `dict[str, Model]` field types
- tomli-w documentation for nested table serialization

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all verified in project
- Architecture: HIGH -- model pattern verified with live testing, TOML round-trip confirmed
- Pitfalls: HIGH -- based on direct code reading of existing consumers

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable domain, no fast-moving dependencies)
