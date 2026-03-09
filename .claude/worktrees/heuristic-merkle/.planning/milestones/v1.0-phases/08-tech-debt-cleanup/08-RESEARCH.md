# Phase 8: Tech Debt Cleanup - Research

**Researched:** 2026-02-24
**Domain:** Dead code removal, test gap closure, template hardening, documentation alignment
**Confidence:** HIGH

## Summary

Phase 8 closes all remaining tech debt items identified by the v1.0 milestone audit. The scope is narrow and well-defined: 4 remaining items across code cleanup, template improvement, and test gap closure. Three of the original 7 audit items (stale REQUIREMENTS.md traceability, stale ROADMAP.md plan counts, and missing SUMMARY.md `requirements-completed` frontmatter) have already been addressed and require no further work.

The remaining items are: (1) remove the orphaned `load_settings` import from `routes.py` and its 3 dead `@patch` decorators in `test_web.py`, (2) replace the hardcoded `/settings` form action in `settings.html` with `url_for("save_settings")`, (3) add a happy-path test for `POST /api/search-now/{app}` with `search_lock` in the test fixture, and (4) verify all 17 SUMMARY.md files have `requirements-completed` frontmatter (already confirmed present). All changes are mechanical and low-risk.

**Primary recommendation:** Execute as a single plan with 4 tasks -- each maps 1:1 to a success criterion. No new libraries, no architecture changes, no risk of behavioral regression.

## Standard Stack

No new libraries or tools needed. All work uses existing project infrastructure.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.132.0 | Route definitions, `url_for` resolution in Jinja2 templates | Already in project |
| Jinja2 | (bundled with FastAPI) | Template rendering, `url_for` global function | Already in project |
| pytest | (existing) | Test framework for new search-now happy-path test | Already in project |
| pytest-asyncio | (existing) | Async test support for search-now endpoint test | Already in project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio.Lock | stdlib | search_lock fixture for test_app | Required by search_now route |
| unittest.mock | stdlib | AsyncMock for cycle function in search-now test | Already used extensively in test_web.py |

### Alternatives Considered
None. This phase introduces no new dependencies.

**Installation:**
No installation needed. All dependencies already present.

## Architecture Patterns

### Pattern 1: Dead Import Removal
**What:** Remove unused `from fetcharr.config import load_settings` from `routes.py` (line 22) and corresponding dead `@patch("fetcharr.web.routes.load_settings")` decorators from 3 test functions in `test_web.py` (lines 153, 197, 238).
**When to use:** When a refactor (Phase 6 replaced `load_settings` call with `SettingsModel(**new_config)`) made an import and its test patches obsolete.
**How:**
```python
# routes.py: DELETE this line (line 22)
from fetcharr.config import load_settings

# test_web.py: REMOVE @patch decorator AND mock_load parameter from these 3 functions:
# - test_save_settings_writes_toml (line 153-154)
# - test_save_settings_preserves_existing_api_key (line 197-198)
# - test_save_settings_replaces_api_key_when_provided (line 238-239)
# Also delete mock_new_settings and mock_load.return_value lines in each test
# since load_settings is no longer called.
```

**Critical detail:** The 3 test functions currently accept `mock_load` as the first parameter after `self` (from the `@patch` decorator). When removing the patch, the `mock_load` parameter must also be removed from the function signature. The tests also set `mock_load.return_value` -- these lines become dead code and should be removed. However, the tests may still need adjustments since `save_settings` now uses `SettingsModel(**new_config)` directly, meaning the TOML write happens before any settings model is constructed. The existing tests already verify TOML output (checking `config_path.read_text()`), so they should continue to pass without the patch.

### Pattern 2: Jinja2 `url_for` for Form Actions
**What:** Replace hardcoded `action="/settings"` in `settings.html` with `action="{{ url_for('save_settings') }}"`.
**When to use:** When form actions reference routes by path instead of by name, making them brittle to route path changes.
**How:**
```html
<!-- BEFORE (line 10 of settings.html) -->
<form method="post" action="/settings" class="space-y-8">

<!-- AFTER -->
<form method="post" action="{{ url_for('save_settings') }}" class="space-y-8">
```

**Key detail:** In FastAPI/Starlette Jinja2 templates, `url_for` is automatically available as a global function. The route name defaults to the Python function name. The POST `/settings` route is defined as `async def save_settings(...)`, so `url_for('save_settings')` resolves to `/settings`. The `request` object is already passed to all `TemplateResponse` calls, which is required for `url_for` to work.

### Pattern 3: search_now Happy-Path Test with search_lock
**What:** Add a test that POSTs to `/api/search-now/radarr` with a properly configured test app that includes `search_lock` on `app.state`, and verifies a 200 response.
**When to use:** The existing `test_app` fixture in `test_web.py` is missing `app.state.search_lock = asyncio.Lock()`, so any test hitting the search_now endpoint would fail with `AttributeError`.
**How:**
```python
import asyncio
from unittest.mock import AsyncMock, patch

def test_search_now_happy_path(client, test_app):
    """POST /api/search-now/radarr triggers cycle and returns 200."""
    # Add missing search_lock to fixture
    test_app.state.search_lock = asyncio.Lock()

    with patch(
        "fetcharr.web.routes.run_radarr_cycle",
        new=AsyncMock(return_value=test_app.state.fetcharr_state),
    ), patch(
        "fetcharr.web.routes.save_state",
    ):
        response = client.post("/api/search-now/radarr")
        assert response.status_code == 200
```

**Fixture gap detail:** The existing `test_app` fixture (lines 19-92 in `test_web.py`) sets up `app.state.settings`, `app.state.scheduler`, `app.state.radarr_client`, `app.state.sonarr_client`, and `app.state.fetcharr_state`, but does NOT set `app.state.search_lock`. The search_now route accesses `request.app.state.search_lock` on line 251, so any happy-path test using the current fixture would crash. The fix is to either add `search_lock` to the fixture itself, or set it in the individual test. Adding it to the fixture is cleaner since it avoids breaking other tests.

### Anti-Patterns to Avoid
- **Patching things that aren't called:** The existing `@patch("fetcharr.web.routes.load_settings")` decorators are a textbook example -- they give false confidence that something is being tested when the patched function is never invoked.
- **Hardcoded URLs in templates:** The `action="/settings"` is fragile -- if the route path changes, the template silently breaks. Always use `url_for()` to reference routes by name.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Route URL resolution in templates | Hardcoded path strings | `url_for('route_name')` | FastAPI/Starlette provides this built-in; stays in sync with route definitions |
| Async lock in test fixtures | Custom synchronization | `asyncio.Lock()` | Stdlib, matches production code exactly |

**Key insight:** All 4 changes are mechanical deletions, substitutions, or additions. No custom logic is needed.

## Common Pitfalls

### Pitfall 1: Removing @patch Without Removing mock_load Parameter
**What goes wrong:** Removing the `@patch` decorator but leaving `mock_load` in the function signature causes the test to receive `client` as `mock_load` and `test_app` as `client`, leading to cryptic failures.
**Why it happens:** `@patch` injects the mock as an extra positional argument. When the decorator is removed, the parameter list must shrink by one.
**How to avoid:** For each of the 3 tests, remove both the `@patch(...)` line AND the `mock_load` parameter from the function signature. Also remove any `mock_load.return_value = ...` and `mock_new_settings` setup lines that were only there to satisfy the dead patch.
**Warning signs:** `AttributeError: 'TestClient' object has no attribute 'post'` (because `client` landed in the wrong parameter).

### Pitfall 2: url_for Requires request in Template Context
**What goes wrong:** `url_for('save_settings')` raises `RuntimeError: No request found in scope` if the template is rendered without a `request` in context.
**Why it happens:** Starlette's `url_for` uses the request's scope to resolve routes.
**How to avoid:** Verify that `settings_page` (the GET `/settings` handler) passes `request=request` to `TemplateResponse`. It already does (line 114), so this is safe.
**Warning signs:** Template rendering crash on `GET /settings`.

### Pitfall 3: TestClient and asyncio.Lock Interaction
**What goes wrong:** `TestClient` runs async routes in a separate event loop thread. Using `asyncio.Lock()` created in the main thread may cause issues.
**Why it happens:** FastAPI's `TestClient` (backed by Starlette's `TestClient` which uses `anyio`) handles event loop threading, but locks must be created in a compatible context.
**How to avoid:** Create the `asyncio.Lock()` at fixture setup time (inside `test_app`), not inline in the test. The `TestClient` will use it correctly because it runs the ASGI app in the same loop context. This pattern is already proven in `tests/test_scheduler.py` (lines 23 and 34).
**Warning signs:** `RuntimeError: cannot use Lock from different event loop`.

### Pitfall 4: SUMMARY.md Frontmatter Already Fixed
**What goes wrong:** Attempting to add `requirements-completed` to SUMMARY.md files that already have it creates duplicates.
**Why it happens:** The audit noted the field was missing, but it was added between the audit and this phase.
**How to avoid:** The research confirms all 17 plan SUMMARY.md files already contain `requirements-completed` frontmatter. The phase plan should verify this with a grep rather than blindly adding the field.
**Warning signs:** Duplicate YAML keys in frontmatter.

## Code Examples

### Dead Import Removal (routes.py)

Current state (line 22):
```python
from fetcharr.config import load_settings
```
Action: Delete this line entirely. No other code in `routes.py` references `load_settings`.

Verification:
```bash
grep -n 'load_settings' fetcharr/web/routes.py
# Should return 0 matches after fix
```

### Dead @patch Removal (test_web.py)

Current state -- 3 affected test functions:
```python
# Test 1 (lines 153-194): test_save_settings_writes_toml
@patch("fetcharr.web.routes.load_settings")           # DELETE
def test_save_settings_writes_toml(mock_load, ...):    # Remove mock_load param
    mock_new_settings = MagicMock()                    # DELETE block
    ...
    mock_load.return_value = mock_new_settings         # DELETE

# Test 2 (lines 197-235): test_save_settings_preserves_existing_api_key
@patch("fetcharr.web.routes.load_settings")           # DELETE
def test_save_settings_preserves_existing_api_key(mock_load, ...):  # Remove mock_load param
    mock_new_settings = MagicMock()                    # DELETE block
    ...
    mock_load.return_value = mock_new_settings         # DELETE

# Test 3 (lines 238-275): test_save_settings_replaces_api_key_when_provided
@patch("fetcharr.web.routes.load_settings")           # DELETE
def test_save_settings_replaces_api_key_when_provided(mock_load, ...):  # Remove mock_load param
    mock_new_settings = MagicMock()                    # DELETE block
    ...
    mock_load.return_value = mock_new_settings         # DELETE
```

**Important:** In each test, the `mock_new_settings` variable and all lines that configure it (`mock_new_settings.radarr.enabled = ...` etc.) were only used to set `mock_load.return_value`. Since `save_settings` now constructs `SettingsModel(**new_config)` directly, these mock setup blocks are entirely dead code and should be removed.

### Template url_for Fix (settings.html)

```html
<!-- Line 10 BEFORE -->
<form method="post" action="/settings" class="space-y-8">

<!-- Line 10 AFTER -->
<form method="post" action="{{ url_for('save_settings') }}" class="space-y-8">
```

### search_now Happy-Path Test (test_web.py)

```python
import asyncio

def test_search_now_happy_path(client, test_app):
    """POST /api/search-now/radarr triggers cycle and returns 200 with updated card."""
    test_app.state.search_lock = asyncio.Lock()

    with patch(
        "fetcharr.web.routes.run_radarr_cycle",
        new=AsyncMock(return_value=test_app.state.fetcharr_state),
    ), patch(
        "fetcharr.web.routes.save_state",
    ):
        response = client.post("/api/search-now/radarr")
        assert response.status_code == 200
        assert "Radarr" in response.text  # Card partial contains app name
```

Alternative: Add `search_lock` directly to the `test_app` fixture for all tests:
```python
# In test_app fixture, after app.state.state_path line:
app.state.search_lock = asyncio.Lock()
```
This is preferred because it makes the fixture complete and allows future tests to use search_now without repeating the lock setup.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `load_settings()` reload after disk write | `SettingsModel(**new_config)` direct construction | Phase 6 (06-03) | `load_settings` import in routes.py became dead code |
| Patching `load_settings` in save_settings tests | No patch needed (model constructed inline) | Phase 6 (06-03) | 3 `@patch` decorators became dead code |

**Deprecated/outdated:**
- `load_settings` in `routes.py`: Orphaned since Phase 6 replaced the reload pattern. Safe to remove -- `load_settings` is still used by `ensure_config` in `config.py` and by tests in `test_config.py`, so the function itself is NOT dead, only the import in `routes.py`.

## Open Questions

None. All 4 success criteria are well-defined with clear implementation paths. No ambiguity remains.

## Audit Gap Reconciliation

The v1.0 audit identified 7 tech debt items. Current status:

| # | Audit Item | Status | Action Needed |
|---|-----------|--------|---------------|
| 1 | Orphaned `load_settings` import in `routes.py` | OPEN | Remove import line 22 |
| 2 | Dead `@patch` in 3 test cases in `test_web.py` | OPEN | Remove patches + dead mock setup |
| 3 | `settings.html` form action hardcoded `/settings` | OPEN | Replace with `url_for("save_settings")` |
| 4 | Missing search_now happy-path test (no `search_lock` in fixture) | OPEN | Add test + fix fixture |
| 5 | REQUIREMENTS.md traceability stale ("Planned" entries) | ALREADY FIXED | Verify only |
| 6 | ROADMAP.md stale plan counts (Phases 5-7) | ALREADY FIXED | Verify only |
| 7 | SUMMARY.md missing `requirements-completed` frontmatter | ALREADY FIXED | Verify only |

**Net work:** 4 items to fix, 3 items to verify-only.

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `fetcharr/web/routes.py` (lines 22, 124-237, 240-276)
- Direct code inspection of `tests/test_web.py` (lines 153-275, 278-282)
- Direct code inspection of `fetcharr/templates/settings.html` (line 10)
- Direct code inspection of `tests/test_scheduler.py` (lines 23, 34 -- `search_lock` pattern)
- Direct code inspection of `tests/conftest.py` (fixture factory pattern)
- `.planning/v1.0-MILESTONE-AUDIT.md` (full audit report with 7 tech debt items)
- Grep verification: all 17 plan SUMMARY.md files already contain `requirements-completed` frontmatter
- Grep verification: REQUIREMENTS.md contains no "Planned" entries
- Grep verification: ROADMAP.md only has "0/?" for Phase 8 (expected)

### Secondary (MEDIUM confidence)
- FastAPI Jinja2 `url_for` behavior based on Starlette documentation and existing usage in `base.html` (lines 7-8)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, all existing project tooling
- Architecture: HIGH -- changes are mechanical, all patterns already used in codebase
- Pitfalls: HIGH -- identified from direct code inspection and prior project test patterns

**Research date:** 2026-02-24
**Valid until:** Indefinite (tech debt cleanup, no external dependency risk)
