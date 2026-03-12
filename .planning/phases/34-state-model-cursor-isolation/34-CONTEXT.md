# Phase 34 Context: State Model & Cursor Isolation

## Decisions

### 1. State keying: instance name (not stable ID)

**Decision:** State is keyed by instance name, matching the config dict keys from Phase 33.

**Rationale:** Simpler, consistent with config shape. Cursor reset on rename is acceptable — renaming is rare and round-robin simply restarts from position 0.

**Shape:**
```json
{
  "radarr": {
    "Default": {"missing_cursor": 5, "cutoff_cursor": 2, "last_run": "...", ...},
    "4K Radarr": {"missing_cursor": 0, "cutoff_cursor": 0, ...}
  },
  "sonarr": {
    "Default": {"missing_cursor": 3, ...}
  }
}
```

### 2. Orphaned state cleanup on load

**Decision:** When loading state, remove entries that don't match any configured instance name. No retention period.

**Rationale:** Prevents stale data accumulation. If an instance is removed from config, its cursor data is no longer useful.

### 3. v2.2 state migration assigns cursors to "Default"

**Decision:** Existing flat `state["radarr"]` and `state["sonarr"]` cursor data maps to the `"Default"` instance key, matching Phase 33's config migration.

**Rationale:** Preserves cursor progress for users upgrading from v2.2. Consistent naming with config migration.

## Code Context

### Files to modify
- `triggarr/state.py` — Restructure `TriggarrState` and `AppState` TypedDicts, update `load_state`/`save_state`, add v2.2 state migration and orphan cleanup
- `triggarr/search/engine.py` — Callers access state via instance name instead of flat app key
- `triggarr/search/scheduler.py` — Passes instance name when reading/writing state
- `triggarr/web/routes.py` — Dashboard reads per-instance state
- `triggarr/tracking.py` — Tracking reads per-instance state

### Patterns to follow
- Atomic write-then-rename (existing pattern in `save_state`)
- `_merge_defaults` pattern for backward-compat state loading
- v2.2 detection via key presence (same approach as `_is_v22_format` in config.py)

### Integration points
- Phase 33's `Settings.radarr`/`Settings.sonarr` are `dict[str, InstanceConfig]` — state keys must match these instance names
- `_default_state()` needs to generate per-instance defaults from config
- State migration runs at startup alongside config migration in `__main__.py`

## Deferred Ideas

None.
