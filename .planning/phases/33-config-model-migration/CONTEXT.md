# Phase 33 Context: Config Model & Migration

**Phase Goal:** Users can define multiple named Radarr/Sonarr instances in config, and existing v2.2 configs auto-migrate safely on upgrade.

**Requirements:** INST-01, INST-02, INST-04

## Decisions

### 1. Multi-instance management is web UI only

Instance add/edit/remove happens exclusively through the web UI. Users do not hand-edit TOML to manage instances. The `[general]` section remains hand-editable in TOML for power users.

**Impact:** TOML structure optimizes for machine read/write and debuggability, not hand-editing ergonomics.

### 2. TOML config shape: readable nested format

Use a readable nested structure (e.g., named table sections like `[radarr."4K Radarr"]`) rather than array-of-tables. Prioritize readability for troubleshooting over hand-editing convenience.

### 3. Instance identification: display name as key

- Users provide a display name when adding an instance (e.g., "4K Radarr", "Anime Sonarr")
- No separate internal ID — the display name IS the key for state, database, and config
- Names must be unique within the same app type (two "Default" OK if one Radarr, one Sonarr)
- Maximum 5 instances per app type

### 4. Default config: empty instances with comment

On first run (no existing config), generate default config with empty instance lists and a comment directing users to the web UI to add instances. `[general]` section keeps its current commented defaults.

### 5. Comments dropped on UI save

`tomli_w` does not preserve TOML comments, and that's acceptable since instance config is UI-managed. The `[general]` section comments will be lost on first UI-triggered save.

### 6. Migration: auto-detect and convert v2.2 config

- Detect v2.2 format (flat `[radarr]`/`[sonarr]` sections without nested instances)
- Migrate to multi-instance format with instance name "Default"
- User can rename "Default" later via UI
- Enabled apps become enabled instances; disabled apps become disabled instances (preserving URL/key)
- Backup original to `triggarr.toml.bak` before overwriting
- Log migration message at startup
- Show one-time banner in web UI indicating migration occurred

## Code Context

### Current config model (`triggarr/models/config.py`)
- `Settings` has flat `radarr: ArrConfig` and `sonarr: ArrConfig` fields
- `ArrConfig` holds: url, api_key (SecretStr), enabled, search_interval, search_missing_count, search_cutoff_count
- Validation: when enabled, at least one count must be > 0

### Current config loading (`triggarr/config.py`)
- TOML loaded via `tomllib`, saved via `tomli_w` with atomic write (tempfile + fsync + os.replace)
- `ensure_config()` generates default on first run, exits with message
- `load_settings()` parses TOML and validates via Pydantic

### Current state format (`triggarr/state.py`)
- `state["radarr"]` / `state["sonarr"]` — flat per-app cursor dicts
- Phase 34 will handle state migration (not this phase)

### Patterns to preserve
- SecretStr for all API keys
- Atomic file writes (tempfile + fsync + os.replace)
- Pydantic validation before any config write
- `get_config_dir()` for testable path resolution

## Deferred Ideas

- (none captured)

---
*Created: 2026-03-09 during Phase 33 discussion*
