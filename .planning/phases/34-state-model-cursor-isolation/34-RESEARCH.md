# Phase 34: State Model & Cursor Isolation - Research

**Researched:** 2026-03-10
**Domain:** JSON state persistence, data migration, TypedDict restructuring
**Confidence:** HIGH

## Summary

Phase 34 restructures Triggarr's flat `state.json` format from `{"radarr": AppState, "sonarr": AppState}` to a nested per-instance format `{"radarr": {"Default": AppState, "4K Radarr": AppState}, "sonarr": {...}}`. This mirrors the Phase 33 config model where `Settings.radarr` and `Settings.sonarr` are `dict[str, InstanceConfig]`.

The scope is well-contained: one data model file (`state.py`), one migration path (v2.2 flat state to v2.3 nested state), and updates to all consumers (engine, scheduler, routes, tracking). The existing atomic write pattern, `_merge_defaults` approach, and v2.2 detection pattern from `config.py` provide proven templates.

**Primary recommendation:** Restructure `TriggarrState` to use `dict[str, AppState]` for radarr/sonarr, add `_is_v22_state_format` detection and `_migrate_v22_state` transformation mirroring the config migration pattern, and update all consumers to pass instance names through the call chain.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
1. **State keying: instance name (not stable ID)** -- State is keyed by instance name, matching the config dict keys from Phase 33. Cursor reset on rename is acceptable.
2. **Orphaned state cleanup on load** -- When loading state, remove entries that don't match any configured instance name. No retention period.
3. **v2.2 state migration assigns cursors to "Default"** -- Existing flat `state["radarr"]` and `state["sonarr"]` cursor data maps to the `"Default"` instance key.

### Claude's Discretion
None specified.

### Deferred Ideas (OUT OF SCOPE)
None.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INST-03 | Each instance maintains independent round-robin cursors that persist across restarts | State restructuring to `dict[str, AppState]` per app type, with save/load verified per instance name. Orphan cleanup prevents cross-contamination. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `json` | 3.11+ | State serialization | Already used, no new dependency |
| Python stdlib `typing.TypedDict` | 3.11+ | State shape definition | Already used for `AppState`/`TriggarrState` |

### Supporting
No new libraries needed. This phase modifies existing code only.

## Architecture Patterns

### Current State Shape (v2.2 -- being replaced)
```json
{
  "radarr": {"missing_cursor": 5, "cutoff_cursor": 2, "last_run": "..."},
  "sonarr": {"missing_cursor": 3, "cutoff_cursor": 0, "last_run": "..."},
  "search_log": []
}
```

### Target State Shape (v2.3)
```json
{
  "radarr": {
    "Default": {"missing_cursor": 5, "cutoff_cursor": 2, "last_run": "..."},
    "4K Radarr": {"missing_cursor": 0, "cutoff_cursor": 0, "last_run": "..."}
  },
  "sonarr": {
    "Default": {"missing_cursor": 3, "cutoff_cursor": 0, "last_run": "..."}
  },
  "search_log": []
}
```

### Pattern 1: v2.2 Detection (mirror config.py approach)
**What:** Detect flat state format by checking if the radarr/sonarr value is an `AppState` dict (has `missing_cursor` key) vs a nested dict of instance names.
**When to use:** On `load_state`, before `_merge_defaults`.
```python
def _is_v22_state_format(data: dict) -> bool:
    """Check if state uses v2.2 flat format (AppState directly under radarr/sonarr)."""
    for section in ("radarr", "sonarr"):
        section_data = data.get(section, {})
        if isinstance(section_data, dict) and "missing_cursor" in section_data:
            return True
    return False
```

### Pattern 2: State Migration (flat to nested)
**What:** Wrap flat AppState into `{"Default": AppState}` for each app type.
**When to use:** At load time when v2.2 format is detected.
```python
def _migrate_v22_state(data: dict) -> dict:
    """Transform v2.2 flat state to v2.3 per-instance format."""
    result = dict(data)
    for section in ("radarr", "sonarr"):
        section_data = result.get(section, {})
        if isinstance(section_data, dict) and "missing_cursor" in section_data:
            result[section] = {"Default": section_data}
    return result
```

### Pattern 3: Orphan Cleanup
**What:** Remove state entries for instances not in current config.
**When to use:** At load time, after migration, before returning state.
**Requires:** Config (Settings) must be available at load time or cleanup done separately.
```python
def _cleanup_orphaned_instances(state: dict, settings: Settings) -> dict:
    """Remove state entries for instances not in current config."""
    for app_type in ("radarr", "sonarr"):
        configured_names = set(getattr(settings, app_type, {}).keys())
        state_names = set(state.get(app_type, {}).keys())
        for orphan in state_names - configured_names:
            del state[app_type][orphan]
    return state
```

### Pattern 4: Default State from Config
**What:** Generate per-instance default state entries from config.
**When to use:** At load time, to ensure every configured instance has state.
```python
def _default_instance_state() -> AppState:
    """Return a fresh AppState for a single instance."""
    return AppState(missing_cursor=0, cutoff_cursor=0, last_run=None)

def _default_state(settings: Settings | None = None) -> TriggarrState:
    """Return default state. If settings provided, creates per-instance entries."""
    if settings is None:
        return TriggarrState(radarr={}, sonarr={}, search_log=[])
    state = TriggarrState(search_log=[])
    for app_type in ("radarr", "sonarr"):
        instances = getattr(settings, app_type, {})
        state[app_type] = {name: _default_instance_state() for name in instances}
    return state
```

### Pattern 5: Consumer Access Pattern Change
**What:** Engine functions receive instance name and access `state["radarr"]["Default"]` instead of `state["radarr"]`.
**Key change:** `run_radarr_cycle` and `run_sonarr_cycle` need an `instance_name` parameter, and all `state["radarr"]` accesses become `state["radarr"][instance_name]`.

### Anti-Patterns to Avoid
- **Passing Settings to load_state at module level:** `load_state` is called in `create_lifespan` where settings are available, so passing settings there is fine. Do NOT try to make `_default_state()` depend on settings at import time.
- **Mutating state dict keys during iteration:** When cleaning up orphans, collect keys to delete first, then delete.

## Architecture Decision: Orphan Cleanup Location

The orphan cleanup needs access to both state and settings. Two options:

**Option A (Recommended):** Perform orphan cleanup in `create_lifespan` after loading state and before exposing on `app.state`. This keeps `load_state` pure (no settings dependency) and cleanup is explicit.

**Option B:** Pass settings into `load_state`. This couples state loading to config, which is a new dependency direction.

**Recommendation:** Option A. Keep `load_state` focused on file I/O and format migration. Do orphan cleanup as a separate step in `create_lifespan`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file writes | Custom temp-file logic | Existing `save_state` pattern | Already battle-tested with fsync + rename |
| v2.2 format detection | Complex heuristics | Simple key-presence check (`"missing_cursor" in section_data`) | Mirrors proven pattern in `config.py._is_v22_format` |

## Common Pitfalls

### Pitfall 1: Settings Dependency in _default_state
**What goes wrong:** If `_default_state()` requires Settings, existing tests and the `conftest.default_state()` helper break.
**Why it happens:** Temptation to generate per-instance defaults from config everywhere.
**How to avoid:** Make settings optional in `_default_state`. When called without settings, return empty dicts for radarr/sonarr. Only populate instance entries when settings are provided.
**Warning signs:** Test imports of `_default_state` failing.

### Pitfall 2: Merge Defaults Must Be Two-Level Deep
**What goes wrong:** `_merge_defaults` currently does shallow merge per app key. With nested instances, it needs to merge per-instance within each app.
**Why it happens:** The merge logic assumes `state["radarr"]` is a flat dict of AppState fields.
**How to avoid:** Update `_merge_defaults` to iterate over instance names and merge each instance's AppState separately.
**Warning signs:** Missing fields in loaded state after migration.

### Pitfall 3: Consumer Signature Changes Ripple
**What goes wrong:** `run_radarr_cycle` and `run_sonarr_cycle` currently take the full `TriggarrState` and access `state["radarr"]` directly. Adding `instance_name` requires updating all callers.
**Why it happens:** Tight coupling between engine functions and state shape.
**How to avoid:** Systematic update: engine.py (add instance_name param), scheduler.py (pass instance_name in job factory), routes.py (pass instance_name for search-now). Map all callers before changing signatures.
**Warning signs:** KeyError on `state["radarr"]["missing_cursor"]` (now a dict of instances, not an AppState).

### Pitfall 4: Dashboard Routes Still Read Flat State
**What goes wrong:** `_build_app_context` in routes.py reads `state.get("radarr", {}).get("missing_cursor")` -- this breaks when `state["radarr"]` is now `{"Default": AppState}`.
**Why it happens:** Dashboard was built for single-instance.
**How to avoid:** For this phase, dashboard can show the first/only instance or aggregate. CONTEXT.md lists routes.py as a file to modify. The dashboard will need to iterate instances.
**Warning signs:** Dashboard shows "0" for all cursors after upgrade.

### Pitfall 5: Scheduler Creates One Job Per Instance
**What goes wrong:** Current scheduler creates one job per app type ("radarr_search", "sonarr_search"). With multi-instance, each instance needs its own job.
**Why it happens:** Scheduler was built for single-instance.
**How to avoid:** This phase focuses on state isolation. The scheduler loop-per-instance change may be partially addressed here (passing instance_name) but the full multi-instance scheduling is Phase 35+ territory. Check ROADMAP for scope boundaries.
**Warning signs:** Only one instance gets searched per cycle.

### Pitfall 6: State Migration Only Runs Once
**What goes wrong:** If migration runs but save fails, next load re-migrates. If migration runs and saves, but app crashes before config migration, state is v2.3 but config is v2.2.
**Why it happens:** Two independent migration paths (config in ensure_config, state in load_state).
**How to avoid:** Config migration already happens in `ensure_config` before state is loaded. State migration at load time is safe because config migration has already completed. The ordering in `__main__.py` -> `startup()` -> `ensure_config()` guarantees config migrates first.

## Code Examples

### Updated TriggarrState TypedDict
```python
class TriggarrState(TypedDict, total=False):
    """Top-level application state with per-instance cursors."""
    radarr: dict[str, AppState]  # {"Default": AppState, "4K": AppState}
    sonarr: dict[str, AppState]
    search_log: list[dict]
```

### Updated run_radarr_cycle Signature
```python
async def run_radarr_cycle(
    client: RadarrClient,
    state: TriggarrState,
    instance_name: str,  # NEW
    settings: Settings,
    db: aiosqlite.Connection,
) -> TriggarrState:
    # Access state via: state["radarr"][instance_name]
    inst = state["radarr"][instance_name]
    cursor = inst["missing_cursor"]
    # ... rest of cycle logic unchanged, just using inst instead of state["radarr"]
```

### Updated make_search_job
```python
def make_search_job(
    app: FastAPI, app_type: str, instance_name: str, state_path: Path
) -> Callable[[], Coroutine]:
    cycle_fn = run_radarr_cycle if app_type == "radarr" else run_sonarr_cycle

    async def job() -> None:
        client = getattr(app.state, f"{app_type}_clients", {}).get(instance_name)
        if client is None:
            return
        async with app.state.search_lock:
            app.state.triggarr_state = await cycle_fn(
                client, app.state.triggarr_state, instance_name,
                app.state.settings, app.state.db,
            )
            save_state(app.state.triggarr_state, state_path)
    return job
```

### load_state with Migration
```python
def load_state(state_path: Path = STATE_PATH) -> TriggarrState:
    if not state_path.exists():
        return TriggarrState(radarr={}, sonarr={}, search_log=[])
    try:
        with open(state_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt state file at {} -- resetting to defaults", state_path)
        return TriggarrState(radarr={}, sonarr={}, search_log=[])

    if _is_v22_state_format(data):
        logger.info("Migrating v2.2 state to v2.3 per-instance format")
        data = _migrate_v22_state(data)

    return _merge_defaults(data)
```

## Files Requiring Changes

| File | Change | Complexity |
|------|--------|------------|
| `triggarr/state.py` | Restructure TypedDicts, add migration, update merge_defaults | HIGH -- core of the phase |
| `triggarr/search/engine.py` | Add `instance_name` param, use `state[app_type][instance_name]` | MEDIUM -- mechanical but touches many lines |
| `triggarr/search/scheduler.py` | Pass instance_name to job factory, iterate instances in lifespan | MEDIUM -- scheduler loop changes |
| `triggarr/web/routes.py` | Update `_build_app_context` and `search_now` for per-instance state | MEDIUM -- dashboard reads |
| `triggarr/tracking.py` | No state access changes needed (tracking reads from DB, not state) | NONE |
| `triggarr/startup.py` | `collect_secrets` and `check_localhost_urls` iterate `dict[str, InstanceConfig]` | LOW -- already dict-based from Phase 33 |
| `tests/test_state.py` | Update all tests for nested format, add migration tests | MEDIUM |
| `tests/conftest.py` | Update `default_state()` for nested format | LOW |

## Scope Boundary: What This Phase Does NOT Do

Per the ROADMAP and dependency structure:
- **Does NOT** create per-instance clients or per-instance scheduler jobs (that is Phase 35+ / scheduler refactor territory)
- **Does NOT** change the dashboard UI layout (Phase 39)
- **Does** make the state model ready for multi-instance by restructuring data
- **Does** update engine signatures to accept instance_name
- **Does** update scheduler to pass instance_name (even if only "Default" is used initially)

Note: The scheduler currently accesses `settings.radarr` as a dict but the engine still treats it as a single flat config (e.g., `settings.radarr.search_missing_count`). The engine needs updating to accept instance-specific config. This is within scope because the state changes require knowing which instance config to use.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` (asyncio_mode=auto) |
| Quick run command | `uv run pytest tests/test_state.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INST-03a | Independent per-instance cursors in state | unit | `uv run pytest tests/test_state.py::test_independent_instance_cursors -x` | Wave 0 |
| INST-03b | Cursors persist across save/load cycle | unit | `uv run pytest tests/test_state.py::test_per_instance_round_trip -x` | Wave 0 |
| INST-03c | v2.2 flat state migrates to nested "Default" | unit | `uv run pytest tests/test_state.py::test_v22_state_migration -x` | Wave 0 |
| INST-03d | Orphaned instance state cleaned on load | unit | `uv run pytest tests/test_state.py::test_orphan_cleanup -x` | Wave 0 |
| INST-03e | Two instances do not cross-contaminate | unit | `uv run pytest tests/test_state.py::test_no_cross_contamination -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_state.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_state.py` -- needs new tests for nested format, migration, orphan cleanup, cross-contamination
- [ ] `tests/conftest.py` -- `default_state()` needs updating for nested format
- [ ] Existing `test_state.py` tests need updating (they assert flat format)

## Open Questions

1. **Engine config access pattern**
   - What we know: `run_radarr_cycle` currently reads `settings.radarr.search_missing_count` directly. With multi-instance, it needs the specific instance's config.
   - What's unclear: Whether to pass the `InstanceConfig` directly or have the engine look it up from `settings.radarr[instance_name]`.
   - Recommendation: Pass `InstanceConfig` directly to keep the engine decoupled from Settings shape. Cleaner signature: `run_radarr_cycle(client, state, instance_name, instance_config, general_config, db)`.

2. **Scheduler job IDs with instance names**
   - What we know: Current job IDs are `"radarr_search"` and `"sonarr_search"`.
   - What's unclear: Whether to change to `"radarr_Default_search"` now or defer to scheduler refactor phase.
   - Recommendation: Change now since the state model requires instance-aware job execution. Use `f"{app_type}_{instance_name}_search"` format.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of `triggarr/state.py`, `triggarr/config.py`, `triggarr/search/engine.py`, `triggarr/search/scheduler.py`, `triggarr/web/routes.py`, `triggarr/models/config.py`
- Phase 33 completed output (config model is `dict[str, InstanceConfig]`)
- Phase 34 CONTEXT.md locked decisions

### Secondary (MEDIUM confidence)
- Pattern inference from config.py v2.2 migration approach (applied to state migration)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies, pure refactor of existing code
- Architecture: HIGH - patterns directly mirror proven config migration from Phase 33
- Pitfalls: HIGH - identified from direct code analysis of all consumer files

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (stable internal refactor, no external dependencies)
