# Phase 43: Update Notification & Cleanup - Research

**Researched:** 2026-03-13
**Domain:** GitHub API integration, htmx UI banners, dead code removal
**Confidence:** HIGH

## Summary

This phase adds two dashboard features (update notification badge and migration banner) and removes dead code. All three areas are straightforward with well-understood patterns already established in the codebase.

The update check requires a new httpx client to poll the GitHub Releases API, a background APScheduler job running every 24 hours, and a nav bar badge in `base.html`. The migration banner requires reading the `.migrated` marker file (already created by `config.py:158-160`), rendering a dismissible banner via htmx, and a DELETE endpoint that removes the marker. Dead code removal is a targeted deletion of the `ArrConfig` alias and its test references.

**Primary recommendation:** Use the existing httpx async client pattern and APScheduler job scheduling pattern already in the codebase. No new dependencies needed.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Nav bar badge next to existing version text -- e.g., "v0.1.0 - v0.2.0 available"
- Check GitHub releases API every 24 hours (on startup + periodic background check)
- Badge links to GitHub releases page (opens in new tab)
- Silent fail on GitHub API errors -- no indicator shown, debug-level log, retry next cycle
- Green/accent color for the "available" text to match the triggarr-green theme
- Full-width info banner at top of dashboard, above health summary card
- Blue/info color scheme (bg-blue-500/20 text-blue-400) to distinguish from warnings
- Dismissible -- clicking X deletes the `.migrated` marker file via API endpoint
- One-time notice: once dismissed, stays gone across restarts
- Message: "Config migrated to v2.3 format. Your settings were updated."
- Remove ArrConfig backward-compat alias from `models/config.py` (lines 64-65)
- Remove ArrConfig import from `tests/test_config.py` (line 18)
- Also scan for and remove any other unused imports or dead references introduced during the v2.3 multi-instance migration

### Claude's Discretion
- GitHub API endpoint choice (releases/latest vs releases list)
- Version comparison logic (semver parsing vs string comparison)
- How to cache the latest version check result in memory
- Background task scheduling approach for the 24h check interval
- Migration banner dismiss endpoint path

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VER-02 | Dashboard indicates when a newer release is available by checking GitHub/GHCR | GitHub Releases API pattern, version comparison, APScheduler job, nav bar badge template |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | (already in deps) | GitHub API calls | Already used for all HTTP in the project |
| apscheduler | >=3.11,<4 | 24h periodic update check | Already used for search scheduling |
| packaging | (stdlib-adjacent, pip-bundled) | Semver version comparison | Standard Python version parsing, more robust than string compare |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| jinja2 | (already in deps) | Banner and badge templates | Already used for all UI |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `packaging.version` | String split + tuple compare | packaging handles pre-release, build metadata edge cases cleanly |
| APScheduler job | asyncio.create_task with sleep loop | APScheduler already manages the event loop; adding a raw task creates lifecycle management burden |
| `/releases/latest` endpoint | `/releases` list endpoint | `/releases/latest` returns a single object, simpler; `/releases` allows checking pre-releases but adds complexity |

**Installation:**
```bash
# No new dependencies needed -- httpx, apscheduler, jinja2 already installed
# packaging is available in the Python environment (bundled with pip/setuptools)
# If not available, add: uv add packaging
```

**Note on `packaging`:** This is bundled with pip and widely available, but is NOT part of the Python stdlib. Verify it's importable in the Docker image. If not, either add it as a dependency or fall back to a simple tuple comparison of version segments (see Code Examples below).

## Architecture Patterns

### Recommended Module Structure
```
triggarr/
  update_check.py          # New: GitHub release check logic
  templates/
    base.html              # Modified: update badge in nav bar
    partials/
      migration_banner.html  # New: dismissible migration banner
    dashboard.html          # Modified: include migration banner
  web/routes.py            # Modified: dismiss endpoint, migration banner context
  search/scheduler.py      # Modified: schedule update check job, store result on app.state
  models/config.py         # Modified: remove ArrConfig alias
```

### Pattern 1: GitHub Release Check Module
**What:** A standalone async function that fetches the latest release tag from GitHub and compares it to `__version__`.
**When to use:** Called by APScheduler every 24h and once at startup.

The function should:
1. Create a one-shot httpx.AsyncClient (no persistent connection needed for 24h intervals)
2. GET `https://api.github.com/repos/thejuran/triggarr/releases/latest`
3. Parse the `tag_name` field (e.g., "v2.3.0") -- strip leading "v"
4. Compare against `__version__` using version tuple comparison
5. Return `{"latest_version": "2.3.0", "update_available": True/False, "html_url": "..."}` or `None` on error

### Pattern 2: App State Storage for Update Info
**What:** Store the update check result on `app.state.update_info` as a simple dict.
**When to use:** Set by the background job, read by templates via Jinja2 globals or template context.

Best approach: Pass update info as a Jinja2 global (like `triggarr_version` already is) that gets updated in-place. Since Jinja2 globals are read at render time, updating a mutable dict works without thread safety issues (single-threaded async).

### Pattern 3: Migration Banner with htmx Dismiss
**What:** Banner checks for `.migrated` file existence, renders conditionally, dismisses via DELETE.
**When to use:** On every dashboard page load, check `CONFIG_DIR / ".migrated"` exists.

The dismiss flow:
1. Banner has `hx-delete="/api/dismiss-migration"` and `hx-swap="outerHTML"` targeting itself
2. Endpoint deletes the `.migrated` file and returns empty HTML
3. Banner disappears without page reload

### Anti-Patterns to Avoid
- **Polling GitHub on every page load:** Would hit rate limits (60/hr unauthenticated). Use cached background check.
- **Storing update state in a file:** Unnecessary persistence. In-memory is fine -- it refreshes on startup anyway.
- **Using `packaging` without fallback:** If the Docker image doesn't have it, the app crashes on import. Use try/except import with tuple fallback.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Version comparison | Regex + string split + manual pre-release handling | `packaging.version.Version` or tuple compare of `int` segments | Edge cases with pre-release suffixes, build metadata |
| HTTP client for GitHub | Raw `urllib` or new library | `httpx.AsyncClient` | Already the project standard |
| Periodic scheduling | `asyncio.sleep` loop | APScheduler interval job | Already manages lifecycle, shutdown, error handling |

**Key insight:** This phase has zero new dependencies. Everything is already in the project.

## Common Pitfalls

### Pitfall 1: GitHub API Rate Limiting
**What goes wrong:** Unauthenticated GitHub API allows 60 requests/hour. Multiple restarts or aggressive polling hits the limit.
**Why it happens:** Not caching results, checking too frequently, or not handling 403 responses.
**How to avoid:** Check once at startup + every 24h. On 403, log debug and skip. Cache result in memory.
**Warning signs:** HTTP 403 with `X-RateLimit-Remaining: 0` header.

### Pitfall 2: Version String Format Mismatch
**What goes wrong:** GitHub tag is "v2.3.0" but `__version__` is "0.1.0" (no "v" prefix). Direct string comparison fails.
**Why it happens:** Different conventions for tag names vs Python package versions.
**How to avoid:** Strip leading "v" from GitHub tag before comparison. Handle tags that don't match expected format gracefully.
**Warning signs:** Update badge showing when versions are equal, or never showing.

### Pitfall 3: Migration Marker Path
**What goes wrong:** `.migrated` file is in `CONFIG_DIR` (which defaults to `/config`), but code looks in wrong directory.
**Why it happens:** Hardcoding path instead of using `CONFIG_DIR` constant.
**How to avoid:** Use `CONFIG_DIR / ".migrated"` from `models/config.py`, same as the creation code in `config.py:159`.
**Warning signs:** Banner never appears even after migration.

### Pitfall 4: Dead Code Removal Breaking Tests
**What goes wrong:** Removing `ArrConfig` alias breaks tests that import it.
**Why it happens:** Tests at `tests/test_config.py` use `ArrConfig` in multiple places (lines 18, 110, 118, 122, 132, 133, 366, 367).
**How to avoid:** Update ALL test references to use `InstanceConfig` directly. Run full test suite after removal.
**Warning signs:** Import errors in test collection.

### Pitfall 5: GitHub API Unavailability in Docker/Firewalled Environments
**What goes wrong:** Some self-hosters run Docker without outbound internet access to GitHub.
**Why it happens:** Air-gapped or restrictive firewall setups.
**How to avoid:** Silent failure is already the locked decision. Ensure `httpx.ConnectError` and `httpx.TimeoutException` are caught and logged at debug level only.
**Warning signs:** Repeated debug logs about GitHub API failures.

## Code Examples

### GitHub Release Check Function
```python
# Source: GitHub REST API docs + project httpx patterns
from __future__ import annotations

import httpx
from loguru import logger

from triggarr import __version__

GITHUB_RELEASES_URL = "https://api.github.com/repos/thejuran/triggarr/releases/latest"


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string like '2.3.0' or 'v2.3.0' into a comparable tuple."""
    clean = version_str.lstrip("v")
    try:
        return tuple(int(x) for x in clean.split("."))
    except (ValueError, AttributeError):
        return (0,)


async def check_for_update() -> dict | None:
    """Check GitHub for a newer Triggarr release.

    Returns dict with latest_version, update_available, html_url on success.
    Returns None on any error (silent failure per locked decision).
    """
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.get(
                GITHUB_RELEASES_URL,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            response.raise_for_status()

        data = response.json()
        tag = data.get("tag_name", "")
        html_url = data.get("html_url", "")
        latest = _parse_version(tag)
        current = _parse_version(__version__)

        return {
            "latest_version": tag.lstrip("v"),
            "update_available": latest > current,
            "html_url": html_url,
        }
    except (httpx.HTTPError, httpx.TimeoutException, KeyError, ValueError) as exc:
        logger.debug("Update check failed: {exc}", exc=exc)
        return None
```

### APScheduler Job for Update Check
```python
# In scheduler.py lifespan, after existing job scheduling:
from triggarr.update_check import check_for_update

# Initialize on app.state
app.state.update_info = None  # Will be set by check_for_update job

async def update_check_job():
    result = await check_for_update()
    if result is not None:
        app.state.update_info = result
        if result["update_available"]:
            logger.info(
                "Update available: v{version}",
                version=result["latest_version"],
            )

# Run immediately at startup, then every 24h
scheduler.add_job(
    update_check_job,
    "interval",
    hours=24,
    id="update_check",
    next_run_time=datetime.now(UTC),
)
```

### Nav Bar Update Badge (base.html modification)
```html
<!-- In base.html nav bar, after the version span (line 19) -->
<span class="text-xs text-triggarr-muted ml-2">v{{ triggarr_version }}</span>
{% if update_info and update_info.update_available %}
<a href="{{ update_info.html_url }}" target="_blank" rel="noopener"
   class="text-xs text-triggarr-green ml-1 hover:underline">
  v{{ update_info.latest_version }} available
</a>
{% endif %}
```

**Note:** `update_info` needs to be available in all templates. Two approaches:
1. Add to `templates.env.globals` as a mutable dict (updated by background job)
2. Pass in every route's template context

Option 1 is better -- it mirrors how `triggarr_version` is already a global. Store a mutable dict on `app.state.update_info` and set `templates.env.globals["update_info"]` to point to the same dict object. Updates to the dict are reflected in all future renders.

**Problem:** `templates.env.globals` is set at module level in `routes.py`, before `app.state` exists. The global must be a mutable container set once, then mutated in place by the background job.

**Solution:** Use a module-level mutable dict:
```python
# In routes.py (module level)
_update_info: dict = {}
templates.env.globals["update_info"] = _update_info

# In scheduler.py update job:
from triggarr.web.routes import _update_info
# ... inside update_check_job:
_update_info.clear()
_update_info.update(result)
```

### Migration Banner Template
```html
<!-- partials/migration_banner.html -->
<div id="migration-banner"
     class="bg-blue-500/20 text-blue-400 border border-blue-500/30 rounded-lg p-4 mb-4 flex items-center justify-between">
  <span>Config migrated to v2.3 format. Your settings were updated.</span>
  <button hx-delete="{{ request.url_for('dismiss_migration') }}"
          hx-target="#migration-banner"
          hx-swap="outerHTML"
          class="text-blue-400 hover:text-white ml-4">
    &times;
  </button>
</div>
```

### Migration Banner Dismiss Endpoint
```python
# In routes.py
from triggarr.models.config import CONFIG_DIR

@router.delete("/api/dismiss-migration", response_class=HTMLResponse)
async def dismiss_migration(request: Request) -> HTMLResponse:
    """Dismiss the migration banner by deleting the .migrated marker file."""
    marker = CONFIG_DIR / ".migrated"
    marker.unlink(missing_ok=True)
    return HTMLResponse("")  # Empty response removes the banner via hx-swap
```

### Dead Code Removal Checklist
```python
# models/config.py -- DELETE lines 64-65:
# # Backward-compat alias for transition period (Plan 02+ will update consumers)
# ArrConfig = InstanceConfig

# tests/test_config.py -- line 18: change import
# FROM: from triggarr.models.config import ArrConfig, GeneralConfig, InstanceConfig, Settings
# TO:   from triggarr.models.config import GeneralConfig, InstanceConfig, Settings

# tests/test_config.py -- ALL occurrences of ArrConfig -> InstanceConfig:
# line 110: ArrConfig(...) -> InstanceConfig(...)
# line 118: docstring "ArrConfig rejects" -> "InstanceConfig rejects"
# line 122: ArrConfig(...) -> InstanceConfig(...)
# line 132: docstring "ArrConfig allows" -> "InstanceConfig allows"
# line 133: ArrConfig(...) -> InstanceConfig(...)
# line 366-367: Remove entire test_arr_config_alias_works test (tests the alias itself)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `ArrConfig` (single instance) | `InstanceConfig` (multi-instance) | Phase 33 (v2.3) | Alias no longer needed, all consumers updated |
| No update notification | GitHub Releases API check | This phase | Users know when to update |

**Deprecated/outdated:**
- `ArrConfig` alias: Was kept for transition period during v2.3 development. All consumers now use `InstanceConfig`. Safe to remove.

## Open Questions

1. **`packaging` availability in Docker image**
   - What we know: The Docker image uses Python 3.12. `packaging` is bundled with pip/setuptools but not guaranteed in all environments.
   - What's unclear: Whether the production Docker image has it available.
   - Recommendation: Use simple tuple comparison of version segments (shown in code examples). No external dependency needed. This handles all realistic version formats (X.Y.Z) for this project.

2. **Jinja2 global update timing**
   - What we know: `templates.env.globals` is evaluated at render time for mutable objects.
   - What's unclear: Thread safety is not a concern (single-threaded async), but mutation during template rendering is theoretically possible.
   - Recommendation: Use a module-level mutable dict. The background job updates it atomically (dict.update is effectively atomic in CPython for simple dicts). Alternatively, replace the entire dict reference via `templates.env.globals["update_info"] = new_dict` in the job.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VER-02a | check_for_update returns update info when newer version exists | unit | `uv run pytest tests/test_update_check.py::test_update_available -x` | Wave 0 |
| VER-02b | check_for_update returns no update when current is latest | unit | `uv run pytest tests/test_update_check.py::test_no_update -x` | Wave 0 |
| VER-02c | check_for_update returns None on HTTP error (silent fail) | unit | `uv run pytest tests/test_update_check.py::test_silent_failure -x` | Wave 0 |
| VER-02d | _parse_version handles "v" prefix and plain versions | unit | `uv run pytest tests/test_update_check.py::test_parse_version -x` | Wave 0 |
| VER-02e | dismiss_migration endpoint deletes .migrated marker | unit | `uv run pytest tests/test_web.py::test_dismiss_migration -x` | Wave 0 |
| VER-02f | ArrConfig alias removed, InstanceConfig used everywhere | unit | `uv run pytest tests/test_config.py -x` | Existing (modified) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_update_check.py` -- covers VER-02a through VER-02d
- [ ] `tests/test_web.py` -- add test for dismiss migration endpoint (VER-02e)

## Sources

### Primary (HIGH confidence)
- Project codebase: `triggarr/models/config.py`, `triggarr/config.py`, `triggarr/web/routes.py`, `triggarr/search/scheduler.py`, `triggarr/templates/base.html`, `triggarr/templates/dashboard.html`
- GitHub REST API docs: `/repos/{owner}/{repo}/releases/latest` returns single release object with `tag_name` and `html_url`

### Secondary (MEDIUM confidence)
- httpx async client patterns verified in project codebase (`clients/base.py`)
- APScheduler interval job patterns verified in project codebase (`search/scheduler.py`)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in project, no new deps
- Architecture: HIGH - patterns directly follow existing codebase conventions
- Pitfalls: HIGH - well-understood domain (HTTP API, file operations, code removal)

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable domain, no fast-moving targets)
