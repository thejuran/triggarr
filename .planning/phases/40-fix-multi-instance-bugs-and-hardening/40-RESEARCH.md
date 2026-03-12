# Phase 40: Fix Multi-Instance Bugs and Hardening - Research

**Researched:** 2026-03-11
**Domain:** Bug fixes and hardening for multi-instance support (v2.3)
**Confidence:** HIGH

## Summary

This phase addresses 11 bugs found during deep code review of the v2.3 multi-instance support. All bugs have been confirmed by reading the actual source code. The bugs fall into three severity tiers: crash-causing bugs in the validate-schedule-cycle chain (3 bugs), safety/correctness bugs in config handling and UI (4 bugs), and medium-priority code hygiene issues (4 bugs).

All affected source files already have comprehensive test coverage (302 tests across 18 test files). The fixes are straightforward -- no new libraries, architectural changes, or complex patterns are needed. Each fix is a localized change to an existing function with clear before/after behavior.

**Primary recommendation:** Fix crash bugs first (engine.py KeyError, routes.py missing state entry, startup.py loop overwrite), then hardening fixes, then test hygiene. Group the validate-schedule-cycle chain bugs into one plan since they share a root cause.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- validate_connections loop overwrite: Fix by either validate first-only or key by instance name (Confidence: 90)
- KeyError crash if instance missing from state: Guard with setdefault before access (Confidence: 88)
- save_settings creates scheduler job but no state entry: Add state entry when creating runtime instance (Confidence: 85)
- CSS selector injection via card_id: Sanitize with regex [^a-zA-Z0-9_-] -> "-" (Confidence: 82)
- settings_page save silently deletes non-first instances: Preserve all instances on settings save (Confidence: 82)
- _atomic_toml_write leaks temp file on write failure: Wrap in try/except, unlink tmp_path on failure (Confidence: 78)
- Unbounded instance_filter list in SQL query: Cap instance_filter length to 10 (Confidence: 78)
- Tag fetch failure indistinguishable from empty tag list: Log warning on tag fetch failure (Confidence: 75)
- cleanup_orphaned_instances mutates state in-place: Return new dict consistent with other state functions (Confidence: 72)
- Test helper _default_instance_state shadows production symbol: Rename test helper to avoid shadowing (Confidence: 72)
- No length limit on instance_name path parameter: Add length validation (Confidence: 70)

### Claude's Discretion
- Implementation order (suggest: fix crash bugs first, then hardening)
- Whether to batch related fixes or separate them
- Test approach for each fix

### Deferred Ideas (OUT OF SCOPE)
- Multi-instance settings UI (Phase 39 scope)
- Full per-instance dashboard UI (Phase 39 scope)
</user_constraints>

## Bug Analysis and Fix Patterns

### Bug Group 1: Validate-Schedule-Cycle Chain (Crash Bugs)

These three bugs share a root cause: runtime-added instances don't get state entries, and the engine assumes they exist.

#### Bug 1: validate_connections loop overwrite (startup.py:110-118)
**Confirmed:** Lines 110-118 iterate `get_enabled_instances("radarr")` and overwrite `results["radarr"]` each iteration. With 2+ enabled Radarr instances, only the last instance's result survives.
**Fix pattern:** Key results by `f"{app_type}_{inst_name}"` instead of just `app_type`. Update callers (line 187-191) to iterate the new keyed results. Alternative: validate only the first instance per type (simpler, matches current UI which only shows first instance).
**Recommendation:** Key by instance name (`results[f"radarr/{inst_name}"]`) for forward compatibility with Phase 39 multi-instance UI.

#### Bug 2: KeyError crash in engine.py:299,498
**Confirmed:** `ist = state["radarr"][instance_name]` (line 299) and `ist = state["sonarr"][instance_name]` (line 498) will KeyError if the instance name has no state entry.
**Fix pattern:** Use `state["radarr"].setdefault(instance_name, _default_instance_state())` at the top of each cycle function. Import `_default_instance_state` from `triggarr.state`.
**Note:** The engine already imports from `triggarr.state` (line 27), so `_default_instance_state` just needs adding to the import.

#### Bug 3: save_settings creates job but no state entry (routes.py:390-440)
**Confirmed:** Lines 390-436 create new clients and scheduler jobs for runtime-added instances but never call `state.setdefault(app_type, {}).setdefault(inst_name, _default_instance_state())`.
**Fix pattern:** After creating the scheduler job (line 430), add:
```python
triggarr_state = request.app.state.triggarr_state
if inst_name not in triggarr_state.get(name, {}):
    triggarr_state.setdefault(name, {})[inst_name] = _default_instance_state()
```

### Bug Group 2: Config Safety and Correctness

#### Bug 4: CSS selector injection (routes.py:131, app_card.html:1,72)
**Confirmed:** Line 131 builds `card_id` as `f"{app_name}-{instance_name}".replace(" ", "-")`. Characters like `.`, `#`, `>`, `[`, `]` in instance names break htmx CSS selectors on lines 1 and 72 of app_card.html.
**Fix pattern:** Add a `_sanitize_card_id` helper using `re.sub(r"[^a-zA-Z0-9_-]", "-", card_id)`. Apply in `_build_app_context` at line 131.

#### Bug 5: settings save deletes non-first instances (routes.py:314-344)
**Confirmed:** Lines 335-344 build `new_config[name]` with only `first_inst_name`. Any additional instances in `current_settings` are dropped.
**Fix pattern:** Start with all current instances, then overlay the first instance's form data:
```python
new_config[name] = {}
for existing_name, existing_cfg in current_instances.items():
    if existing_name == first_inst_name:
        new_config[name][first_inst_name] = {form data...}
    else:
        new_config[name][existing_name] = existing_cfg.model_dump()
```
The `model_dump()` approach preserves SecretStr values correctly since `tomli_w` needs plain strings. Use `existing_cfg.api_key.get_secret_value()` for the api_key field.

#### Bug 6: _atomic_toml_write temp file leak (config.py:96-109)
**Confirmed:** If `tomli_w.dump(data, f)` raises on line 100, `tmp_path` (string from `tempfile.mkstemp`) is never cleaned up. The `finally` block only handles `dir_fd`.
**Fix pattern:** Wrap the write+replace in try/except, unlink `tmp_path` on failure:
```python
def _atomic_toml_write(path: Path, data: dict) -> None:
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

#### Bug 7: Unbounded instance_filter in SQL (db.py:363-366)
**Confirmed:** `instance_filter` from `_split_filter_param` has no length cap. While the app limits to 10 instances, the query param is user-controlled.
**Fix pattern:** In `partial_history_results` (routes.py:264), cap the list: `instance_filter = instance_filter[:10] if instance_filter else None`. Or apply the cap in `_split_filter_param`.

### Bug Group 3: Medium Priority Hygiene

#### Bug 8: Tag fetch failure silent (engine.py:335-362)
**Confirmed:** When `get_tags()` raises, `tags = []` (line 346). The "tag not found" warning on line 350 only fires `if tags` (non-empty list). So a network failure silently bypasses tag filtering with no log trace.
**Fix pattern:** Already partially fixed -- line 344 logs `"Failed to fetch tags -- skipping tag filtering"`. The issue is that when `tags = []` from a fetch failure AND a tag is configured, no "not found" warning fires because the `if tags:` guard on line 350. The fix is to distinguish "fetch failed" from "tag not in list". Track whether fetch succeeded with a boolean flag.

#### Bug 9: cleanup_orphaned_instances mutation (state.py:203-222)
**Confirmed:** Line 221 `del state_section[orphan]` mutates in-place, unlike other state functions which return new dicts.
**Fix pattern:** Build new dicts instead of mutating:
```python
def cleanup_orphaned_instances(state: TriggarrState, settings: Settings) -> TriggarrState:
    result = dict(state)
    for app_type in ("radarr", "sonarr"):
        configured_names = set(getattr(settings, app_type, {}).keys())
        current = result.get(app_type, {})
        result[app_type] = {k: v for k, v in current.items() if k in configured_names}
    return result
```

#### Bug 10: Test helper name shadowing (tests/test_search.py:217)
**Confirmed:** `_default_instance_state()` in tests shadows `triggarr.state._default_instance_state`. The test helper returns a full `TriggarrState` with nested Default instance, while the production function returns a single `AppState`. Line 220 uses a deferred import alias to work around the collision.
**Fix pattern:** Rename the test helper to `_make_test_state()` or `_default_test_state()`. Update all ~25 call sites in test_search.py.

#### Bug 11: No length limit on instance_name path parameter (routes.py:443,509)
**Confirmed:** `instance_name: str` path parameter has no length validation. Arbitrarily long names flow into logger calls.
**Fix pattern:** Add early validation in both `search_now` and `partial_app_card`:
```python
if len(instance_name) > 64:
    return HTMLResponse("Instance name too long", status_code=400)
```

### Architectural Note: Duplicate Atomic Write in routes.py

Lines 354-364 in routes.py implement atomic write manually instead of using `_atomic_toml_write` from config.py. This is identified in CONTEXT.md specifics. The fix for Bug 5 (preserve non-first instances) should also refactor to use `_atomic_toml_write`, eliminating the duplication.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file write | Custom tempfile+rename in routes.py | `_atomic_toml_write` from config.py | Already exists, includes dir fsync |
| CSS ID sanitization | Complex character-by-character filtering | `re.sub(r"[^a-zA-Z0-9_-]", "-", value)` | Standard regex, covers all edge cases |
| State initialization | Inline dict construction | `_default_instance_state()` from state.py | Single source of truth for default state shape |

## Common Pitfalls

### Pitfall 1: Breaking SecretStr Serialization in Config Preservation
**What goes wrong:** Using `model_dump()` on InstanceConfig serializes `api_key` as a SecretStr object, not a plain string. TOML writer chokes.
**How to avoid:** When preserving existing instances in save_settings, explicitly call `api_key.get_secret_value()` for the api_key field. Use a dict comprehension that handles SecretStr fields.

### Pitfall 2: Forgetting to Save State After Adding Entry
**What goes wrong:** Adding a state entry for a runtime instance but not persisting it. If the app crashes before the first cycle, the state entry is lost.
**How to avoid:** Call `save_state()` after adding the new state entry in save_settings.

### Pitfall 3: Race Between State Mutation and Cleanup
**What goes wrong:** `cleanup_orphaned_instances` mutating state in-place while a cycle coroutine is reading it.
**How to avoid:** Return a new dict (the fix) and assign atomically. Since Python's GIL protects dict assignment, `state = new_dict` is safe.

### Pitfall 4: CSS ID Starting with Digit
**What goes wrong:** If sanitized card_id starts with a digit (e.g., instance "4K" becomes "4K"), CSS selectors may not work.
**How to avoid:** The card_id is always prefixed with app name (e.g., "radarr-4K"), so it always starts with a letter. No additional handling needed.

## Code Examples

### Sanitize Card ID
```python
import re

def _sanitize_card_id(raw: str) -> str:
    """Sanitize a string for use as an HTML id / CSS selector target."""
    return re.sub(r"[^a-zA-Z0-9_-]", "-", raw)

# Usage in _build_app_context:
"card_id": _sanitize_card_id(f"{app_name}-{instance_name}"),
```

### Guard State Access with setdefault
```python
# At top of run_radarr_cycle, before any state access:
state["radarr"].setdefault(instance_name, _default_instance_state())
ist = state["radarr"][instance_name]
```

### Preserve All Instances on Settings Save
```python
# Build new_config preserving non-first instances:
new_config[name] = {}
for existing_name, existing_cfg in current_instances.items():
    if existing_name == first_inst_name:
        # Apply form data for the instance being edited
        new_config[name][first_inst_name] = {
            "url": url,
            "api_key": submitted_key if submitted_key else existing_cfg.api_key.get_secret_value(),
            # ... other fields from form
        }
    else:
        # Preserve other instances unchanged
        new_config[name][existing_name] = {
            "url": existing_cfg.url,
            "api_key": existing_cfg.api_key.get_secret_value(),
            "enabled": existing_cfg.enabled,
            "search_interval": existing_cfg.search_interval,
            "search_missing_count": existing_cfg.search_missing_count,
            "search_cutoff_count": existing_cfg.search_cutoff_count,
        }
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (asyncio_mode=auto) |
| Config file | pyproject.toml (existing) |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Bug # | Behavior | Test Type | Automated Command | File Exists? |
|-------|----------|-----------|-------------------|-------------|
| 1 | validate_connections keys by instance | unit | `uv run pytest tests/test_startup.py -x -q` | Yes |
| 2 | engine.py setdefault guard | unit | `uv run pytest tests/test_search.py -x -q` | Yes |
| 3 | save_settings adds state entry | unit | `uv run pytest tests/test_web.py -x -q` | Yes |
| 4 | card_id sanitization | unit | `uv run pytest tests/test_web.py -x -q` | Yes |
| 5 | settings save preserves instances | unit | `uv run pytest tests/test_web.py -x -q` | Yes |
| 6 | atomic_toml_write temp cleanup | unit | `uv run pytest tests/test_config.py -x -q` | Yes |
| 7 | instance_filter length cap | unit | `uv run pytest tests/test_web.py -x -q` | Yes |
| 8 | tag fetch failure logging | unit | `uv run pytest tests/test_search.py -x -q` | Yes |
| 9 | cleanup_orphaned no mutation | unit | `uv run pytest tests/test_state.py -x -q` | Yes |
| 10 | test helper rename | unit | `uv run pytest tests/test_search.py -x -q` | Yes |
| 11 | instance_name length limit | unit | `uv run pytest tests/test_web.py -x -q` | Yes |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. All 18 test files and 302 tests are in place. New tests will be added alongside each fix.

## Recommended Implementation Order

**Plan 1: Crash Bugs (validate-schedule-cycle chain)**
- Bug 2: engine.py setdefault guard (prevents KeyError crashes)
- Bug 3: save_settings adds state entry (prevents runtime crash)
- Bug 1: validate_connections keyed results (data loss, not crash, but same chain)

**Plan 2: Config Safety and Hardening**
- Bug 5: settings save preserves non-first instances (data loss prevention)
- Bug 6: _atomic_toml_write temp file cleanup
- Bug 5 also: refactor routes.py to use _atomic_toml_write (dedup)
- Bug 4: CSS selector injection sanitization

**Plan 3: Input Validation and Hygiene**
- Bug 7: instance_filter length cap
- Bug 11: instance_name path parameter length limit
- Bug 8: tag fetch failure distinguishable logging
- Bug 9: cleanup_orphaned_instances immutable return
- Bug 10: test helper rename

## Sources

### Primary (HIGH confidence)
- Direct source code inspection of all affected files (startup.py, search/engine.py, search/scheduler.py, web/routes.py, config.py, state.py, db.py, templates/partials/app_card.html, web/validation.py, tests/test_search.py)
- CONTEXT.md bug reports with line numbers confirmed against actual code

## Metadata

**Confidence breakdown:**
- Bug analysis: HIGH - all bugs confirmed by reading actual source code at exact line numbers
- Fix patterns: HIGH - straightforward Python patterns (setdefault, re.sub, dict comprehension)
- Test coverage: HIGH - all test files exist, 302 tests passing

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable codebase, bugs won't change)
