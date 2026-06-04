# Phase 74: Count-Only Refresh - Pattern Map

**Mapped:** 2026-06-03
**Files analyzed:** 5 (3 new, 1 modified, 1 modified-fixture)
**Analogs found:** 5 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/search/engine.py` (new helpers) | service | request-response | `run_radarr_cycle` / `run_sonarr_cycle` / `run_lidarr_cycle` in same file | exact — prefix extraction |
| `triggarr/web/routes.py` (new endpoint) | controller | request-response | `search_now` (routes.py:880) | exact — structural copy minus search call |
| `triggarr/templates/partials/app_card.html` | component | request-response | existing connected footer button (app_card.html:119-125) | exact — split one button into two |
| `tests/test_refresh_counts.py` | test | — | `test_search.py` (engine helpers) + `test_web.py` (route tests) | exact — same fixture + async pattern |
| `tests/test_web.py` (fixture addition) | test | — | `test_app` fixture (test_web.py:28) | exact — add one state field |

---

## Pattern Assignments

### `triggarr/search/engine.py` — New helper functions

**Analog:** `run_radarr_cycle` (engine.py:275), `run_sonarr_cycle` (engine.py:517), `run_lidarr_cycle` (engine.py:766)

#### Imports pattern (engine.py:9-27)

```python
from __future__ import annotations

import contextlib
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import aiosqlite
import httpx
import pydantic
from loguru import logger

from triggarr.clients.lidarr import LidarrClient
from triggarr.clients.radarr import RadarrClient
from triggarr.clients.sonarr import SonarrClient
from triggarr.db import PendingCapExceeded, insert_search_entry
from triggarr.models.arr import Tag
from triggarr.models.config import InstanceConfig, Settings
from triggarr.state import TriggarrState
```

The helpers do NOT add new imports. They use the same types already imported. `aiosqlite` remains imported (used by cycle functions), but the helpers themselves do not receive a `db` parameter.

#### Radarr prefix (actual seam lines confirmed from live code)

**Fetch + abort branch** (engine.py:312-323):
```python
    try:
        missing = await client.get_wanted_missing()
        cutoff = await client.get_wanted_cutoff()
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning("Radarr: Cycle aborted -- {exc}", exc=_sanitize_exc(exc))
        ist["connected"] = False
        ist["tag_warnings"] = []
        if not ist.get("unreachable_since"):
            ist["unreachable_since"] = (
                datetime.now(UTC).isoformat().replace("+00:00", "Z")
            )
        return state
```
**In the helper:** replace `return state` with `return None` (helper return contract).

**Library count (cosmetic, never aborts)** (engine.py:325-330):
```python
    try:
        total_items = await client.get_library_count()
    except (httpx.HTTPError, pydantic.ValidationError, ValueError):
        total_items = ist.get("total_items")  # keep previous value
```

**Health + raw count cache** (engine.py:332-339):
```python
    ist["connected"] = True
    ist["unreachable_since"] = None

    ist["missing_count"] = len(missing)
    ist["cutoff_count"] = len(cutoff)
    ist["total_items"] = total_items
```

**cap_batch_sizes block** (engine.py:341-353): STAYS IN CYCLE ONLY — not in helper. The helper does not call `cap_batch_sizes`.

**Tag resolution block** (engine.py:355-390):
```python
    missing_tag_id: int | None = None
    cutoff_tag_id: int | None = None
    ist["tag_warnings"] = []
    if instance_config.missing_tag or instance_config.cutoff_tag:
        tag_fetch_ok = False
        try:
            tags = await get_tags_fn() if get_tags_fn is not None else await client.get_tags()
            tag_fetch_ok = True
        except (httpx.HTTPError, pydantic.ValidationError) as exc:
            logger.warning(
                "Radarr: Failed to fetch tags -- skipping tag filtering: {exc}",
                exc=_sanitize_exc(exc),
            )
            tags = []

        if instance_config.missing_tag:
            missing_tag_id = resolve_tag_id(instance_config.missing_tag, tags)
            if missing_tag_id is None and tag_fetch_ok:
                logger.warning(
                    "Radarr: Tag '{tag}' not found -- searching all missing items",
                    tag=instance_config.missing_tag,
                )
                ist["tag_warnings"].append({"tag": instance_config.missing_tag, "field": "missing"})

        if instance_config.cutoff_tag:
            cutoff_tag_id = resolve_tag_id(instance_config.cutoff_tag, tags)
            if cutoff_tag_id is None and tag_fetch_ok:
                logger.warning(
                    "Radarr: Tag '{tag}' not found -- searching all cutoff items",
                    tag=instance_config.cutoff_tag,
                )
                ist["tag_warnings"].append({"tag": instance_config.cutoff_tag, "field": "cutoff"})
```
Note: `searched_count = 0` and `skipped_count = 0` at engine.py:392-393 stay in the cycle only.

**Missing filter + eligible count** (engine.py:395-406):
```python
    missing = filter_monitored(missing)
    ist["missing_monitored"] = len(missing)
    if missing_tag_id is not None:
        missing = filter_by_tag(missing, missing_tag_id, _radarr_tags)
        logger.debug("Radarr: Tag filter applied -- {n} missing items match tag", n=len(missing))
    if settings.general.skip_unreleased:
        missing = filter_unreleased_movies(missing)
        skipped_unreleased = ist["missing_monitored"] - len(missing)
        if skipped_unreleased > 0:
            logger.info("Radarr: {n} unreleased movies skipped", n=skipped_unreleased)
    ist["missing_eligible"] = len(missing)
    # SEAM: next line (407) is cursor = ist["missing_cursor"] — stays in cycle
```

**Cutoff filter** (engine.py:451-455, inside cycle search-only block):
```python
    cutoff = filter_monitored(cutoff)
    if cutoff_tag_id is not None:
        cutoff = filter_by_tag(cutoff, cutoff_tag_id, _radarr_tags)
        logger.debug("Radarr: Tag filter applied -- {n} cutoff items match tag", n=len(cutoff))
    # (no ist write for cutoff eligible in Radarr — just local var)
```
The helper must also filter `cutoff` before returning so the cycle receives the filtered list.

**Helper return:** `return (missing, cutoff)` where both are the filtered (post-`filter_monitored`, post-tag-filter, post-`filter_unreleased_movies`) lists. On abort: `return None`.

#### Radarr helper signature (from RESEARCH.md Focus Point 2)

```python
async def refresh_radarr_counts(
    client: RadarrClient,
    state: TriggarrState,
    instance_name: str,
    instance_config: InstanceConfig,
    settings: Settings,
    *,
    get_tags_fn: Callable[[], Awaitable[list[Tag]]] | None = None,
) -> tuple[list[dict], list[dict]] | None:
```

#### Sonarr-specific differences (engine.py:549-645)

The Sonarr prefix is structurally identical to Radarr with these differences:

- Fetch variables are `missing_episodes`, `cutoff_episodes` (not `missing`, `cutoff`)
- Missing filter chain: `filter_sonarr_episodes()` instead of `filter_monitored()` + `filter_unreleased_movies()`; no `missing_monitored` ist write for Sonarr
- Dedup: `missing_seasons = deduplicate_to_seasons(missing_episodes)` (engine.py:643)
- Two additional ist writes: `ist["missing_eligible"] = len(missing_episodes)` (line 644) and `ist["missing_searchable"] = len(missing_seasons)` (line 645)
- **`cutoff_searchable` moves into helper:** at engine.py:700 `ist["cutoff_searchable"] = len(cutoff_seasons)` is currently after the first `slice_batch` call (line 647) but semantically belongs in the prefix. Move it into the helper so the helper computes both `missing_seasons` AND `cutoff_seasons` and sets `ist["cutoff_searchable"]` before returning
- Cutoff filter chain (engine.py:694-699): `filter_sonarr_episodes(cutoff_episodes)` → optional `filter_by_tag` → `deduplicate_to_seasons(cutoff_episodes)` → set `ist["cutoff_searchable"]`
- Helper return: `(missing_seasons, cutoff_seasons)` (deduplicated season lists, not episode lists)
- Seam boundary: line 646 `cursor = ist["missing_cursor"]` / line 647 `batch, new_cursor = slice_batch(missing_seasons, cursor, missing_limit)`

#### Lidarr-specific differences (engine.py:801-896)

- Albums are atomic — no `deduplicate_to_seasons` step
- Missing filter chain: `filter_monitored(missing)` → `ist["missing_monitored"] = len(missing)` → optional `filter_by_tag` → `ist["missing_eligible"] = len(missing)` (line 896)
- No `missing_searchable`, no `cutoff_searchable` ist writes
- Cutoff filter: `filter_monitored(cutoff)` → optional `filter_by_tag` (engine.py:943-946)
- Helper return: `(missing, cutoff)` (filtered album lists)
- Seam boundary: line 897 `cursor = ist["missing_cursor"]` / line 898 `batch, new_cursor = slice_batch(missing, cursor, missing_limit)`

#### Refactored cycle pattern

The cycle calls the helper, receives filtered lists, then continues (from RESEARCH.md Focus Point 2):

```python
async def run_radarr_cycle(
    client: RadarrClient,
    state: TriggarrState,
    instance_name: str,
    instance_config: InstanceConfig,
    settings: Settings,
    db: aiosqlite.Connection,
    *,
    get_tags_fn: Callable[[], Awaitable[list[Tag]]] | None = None,
) -> TriggarrState:
    cycle_start = time.monotonic()
    if instance_name not in state.get("radarr", {}):
        logger.warning("Radarr: instance {name} not in state -- skipping", name=instance_name)
        return state

    result = await refresh_radarr_counts(
        client, state, instance_name, instance_config, settings,
        get_tags_fn=get_tags_fn,
    )
    if result is None:
        return state  # fetch failed; ist already updated by helper

    missing, cutoff = result
    ist = state["radarr"][instance_name]

    # cap batch sizes (search-only sizing — stays in cycle)
    missing_limit = instance_config.search_missing_count
    cutoff_limit = instance_config.search_cutoff_count
    hard_max = settings.general.hard_max_per_cycle
    orig_missing, orig_cutoff = missing_limit, cutoff_limit
    missing_limit, cutoff_limit = cap_batch_sizes(missing_limit, cutoff_limit, hard_max)
    if hard_max > 0 and (missing_limit != orig_missing or cutoff_limit != orig_cutoff):
        logger.debug(...)

    searched_count = 0
    skipped_count = 0

    # --- Missing queue (slice + search loop + cursor write) ---
    cursor = ist["missing_cursor"]
    batch, new_cursor = slice_batch(missing, cursor, missing_limit)
    # ... existing search loop ...
    ist["missing_cursor"] = new_cursor
    # ...

    # --- Cutoff queue (same pattern) ---
    # ...

    # --- Diagnostic summary + last_run/last_success (unchanged) ---
    elapsed = time.monotonic() - cycle_start
    logger.info(...)
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    ist["last_run"] = now_iso
    ist["last_success"] = now_iso
    return state
```

**Critical:** `cycle_start = time.monotonic()` stays in the cycle (line 306), NOT in the helper. The diagnostic summary at line 500-513 continues to use `cycle_start` to measure total elapsed including the helper's work.

---

### `triggarr/web/routes.py` — New `refresh_counts` endpoint

**Analog:** `search_now` (routes.py:880-972)

#### Import addition

Add to the existing import from `triggarr.search.engine`:
```python
from triggarr.search.engine import (
    _sanitize_exc,
    refresh_lidarr_counts,
    refresh_radarr_counts,
    refresh_sonarr_counts,
)
```
(Currently only `_sanitize_exc` is imported from engine at line 52.)

#### Guards pattern (routes.py:883-893) — copy verbatim

```python
@router.post("/api/refresh-counts/{app_name}/{instance_name}", response_class=HTMLResponse)
async def refresh_counts(request: Request, app_name: str, instance_name: str) -> HTMLResponse:
    """Trigger a count-only refresh for a specific instance and return updated card."""
    if len(instance_name) > 64:
        return HTMLResponse("Instance name too long", status_code=400)
    if app_name not in APP_TYPES:
        return HTMLResponse("Invalid app", status_code=400)

    clients = getattr(request.app.state, f"{app_name}_clients", {})
    enabled = request.app.state.settings.get_enabled_instances(app_name)
    if instance_name not in enabled or instance_name not in clients:
        return HTMLResponse("Instance not enabled", status_code=400)
    client = clients[instance_name]
    instance_config = enabled[instance_name]
```

#### Rate-limit pattern (routes.py:895-913) — copy, change dict name

```python
    # Optimistic rate limit check BEFORE lock (fast-fail for obvious cases)
    rate_key = f"{app_name}_{instance_name}"
    now = time.monotonic()
    last = request.app.state.last_refresh_time.get(rate_key, 0.0)  # sibling dict
    if now - last < SEARCH_RATE_LIMIT_SECONDS:
        logger.info("{name}/{inst}: Count refresh rate-limited", name=app_name.title(), inst=instance_name)
        return HTMLResponse("Rate limited -- try again shortly", status_code=429)

    async with request.app.state.search_lock:
        # Re-check inside lock to prevent concurrent bypass (DRSEC-03)
        now = time.monotonic()
        last = request.app.state.last_refresh_time.get(rate_key, 0.0)
        if now - last < SEARCH_RATE_LIMIT_SECONDS:
            logger.info(
                "{name}/{inst}: Count refresh rate-limited (after lock)",
                name=app_name.title(), inst=instance_name,
            )
            return HTMLResponse("Rate limited -- try again shortly", status_code=429)
        request.app.state.last_refresh_time[rate_key] = now
```
**Key difference from `search_now`:** `last_refresh_time` (sibling dict) instead of `last_search_time`. Both use the same `SEARCH_RATE_LIMIT_SECONDS = 10` constant (routes.py:146).

#### Tag cache resolver (routes.py:920-931) — copy verbatim inside lock

```python
        cache_key = (app_name, instance_name)

        async def _get_tags_cached() -> list[Tag]:
            cache = request.app.state.tag_cache
            entry = cache.get(cache_key)
            if entry is not None:
                cached_tags, fetched_at = entry
                if time.monotonic() - fetched_at < _TAG_CACHE_TTL_SECONDS:
                    return cached_tags
            fresh_tags = await client.get_tags()
            cache[cache_key] = (fresh_tags, time.monotonic())
            return fresh_tags
```

#### Core call (replaces `_run_one_cycle`) — what changes

```python
        refresh_fns = {
            "radarr": refresh_radarr_counts,
            "sonarr": refresh_sonarr_counts,
            "lidarr": refresh_lidarr_counts,
        }
        refresh_fn = refresh_fns[app_name]
        try:
            await refresh_fn(
                client,
                request.app.state.triggarr_state,
                instance_name,
                instance_config,
                request.app.state.settings,
                get_tags_fn=_get_tags_cached,
            )
            logger.info("{name}/{inst}: Count refresh triggered", name=app_name.title(), inst=instance_name)
        except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
            logger.error(
                "{name}/{inst}: Count refresh failed -- {exc}",
                name=app_name.title(),
                inst=instance_name,
                exc=(
                    _sanitize_exc(exc)
                    if isinstance(exc, httpx.HTTPError | pydantic.ValidationError)
                    else str(exc)
                ),
            )
```
**What is absent vs. `search_now`:**
- No `_run_one_cycle` call (and no `save_state` call)
- No `app.state.search_failures` touch
- No `last_run`/`last_success` update

#### Always-200 card response (routes.py:966-972) — copy verbatim

```python
    # Return updated card partial
    app_data = _build_app_context(request, app_name, instance_name)
    return templates.TemplateResponse(
        request=request,
        name="partials/app_card.html",
        context={"app": app_data},
    )
```

#### State initialization — where to add `last_refresh_time`

In `triggarr/search/scheduler.py` lifespan, alongside `last_search_time` at line 500:
```python
        app.state.last_search_time = {}
        # NEW: sibling rate-limit dict for refresh_counts endpoint (D-08)
        app.state.last_refresh_time = {}
```

---

### `triggarr/templates/partials/app_card.html` — Footer button modification

**Analog:** existing connected-state button (app_card.html:119-125)

#### Current connected footer (lines 118-126) — the section to replace

```html
    {% else %}
      <button hx-post="{{ request.url_for('search_now', app_name=app.name, instance_name=app.instance) }}"
              hx-target="#{{ app.card_id }}-card"
              hx-swap="outerHTML"
              hx-disabled-elt="this"
              class="w-full flex items-center justify-center gap-2 py-2 rounded-md bg-triggarr-elevated hover:bg-triggarr-border border border-triggarr-border text-xs font-semibold transition-colors text-triggarr-text group disabled:opacity-50 disabled:cursor-not-allowed">
        <i class="ph ph-magnifying-glass {% if app.name == 'radarr' %}group-hover:text-triggarr-radarr{% elif app.name == 'sonarr' %}group-hover:text-triggarr-sonarr{% elif app.name == 'lidarr' %}group-hover:text-triggarr-green{% endif %} transition-colors"></i>Search Now
      </button>
    {% endif %}
```

#### Target: two side-by-side buttons (D-09, D-11, D-12)

```html
    {% else %}
      <div class="flex gap-2">
        <button hx-post="{{ request.url_for('search_now', app_name=app.name, instance_name=app.instance) }}"
                hx-target="#{{ app.card_id }}-card"
                hx-swap="outerHTML"
                hx-disabled-elt="this"
                class="flex-1 flex items-center justify-center gap-2 py-2 rounded-md bg-triggarr-elevated hover:bg-triggarr-border border border-triggarr-border text-xs font-semibold transition-colors text-triggarr-text group disabled:opacity-50 disabled:cursor-not-allowed">
          <i class="ph ph-magnifying-glass {% if app.name == 'radarr' %}group-hover:text-triggarr-radarr{% elif app.name == 'sonarr' %}group-hover:text-triggarr-sonarr{% elif app.name == 'lidarr' %}group-hover:text-triggarr-green{% endif %} transition-colors"></i>Search Now
        </button>
        <button hx-post="{{ request.url_for('refresh_counts', app_name=app.name, instance_name=app.instance) }}"
                hx-target="#{{ app.card_id }}-card"
                hx-swap="outerHTML"
                hx-disabled-elt="this"
                class="flex-1 flex items-center justify-center gap-2 py-2 rounded-md bg-triggarr-card hover:bg-triggarr-elevated border border-triggarr-border text-xs font-semibold transition-colors text-triggarr-muted disabled:opacity-50 disabled:cursor-not-allowed">
          <i class="ph ph-arrows-clockwise"></i>Refresh counts
        </button>
      </div>
    {% endif %}
```

**Key copy decisions:**
- Search Now: `w-full` → `flex-1` (only change; all other classes identical)
- Refresh counts: mirrors all htmx attrs (`hx-post`, `hx-target`, `hx-swap="outerHTML"`, `hx-disabled-elt="this"`); lighter style (`bg-triggarr-card` vs `bg-triggarr-elevated`, `text-triggarr-muted` vs `text-triggarr-text`); `ph-arrows-clockwise` icon (same icon as Retry Connection at line 116); no app-colored `group-hover` (secondary action)
- Disconnected branch (lines 111-117): UNCHANGED — single "Retry Connection" button, no "Refresh counts"

---

### `tests/test_refresh_counts.py` — New test module

**Analogs:** `tests/test_search.py` (engine helper unit tests) and `tests/test_web.py` (route integration tests)

#### Imports pattern (copy from test_search.py:1-39 and test_web.py:1-24)

```python
"""Tests for count-only refresh: engine helpers and refresh_counts route."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import httpx
import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from triggarr.db import init_db
from triggarr.models.arr import Tag
from triggarr.models.config import GeneralConfig, InstanceConfig
from triggarr.search.engine import (
    refresh_lidarr_counts,
    refresh_radarr_counts,
    refresh_sonarr_counts,
)
from triggarr.state import _default_instance_state, _default_state
from triggarr.web.routes import STATIC_DIR, router
```

#### Engine helper test scaffold (copy from test_search.py:241-295)

```python
def _make_test_state():
    """Return a default per-instance state nested under 'Default'."""
    state = _default_state()
    state["radarr"] = {"Default": _default_instance_state()}
    state["sonarr"] = {"Default": _default_instance_state()}
    state["lidarr"] = {"Default": _default_instance_state()}
    return state


def _instance_config(missing_count: int = 2, cutoff_count: int = 2) -> InstanceConfig:
    return InstanceConfig(
        url="http://radarr:7878",
        api_key="test-key",
        enabled=True,
        search_missing_count=missing_count,
        search_cutoff_count=cutoff_count,
    )


async def test_refresh_radarr_counts_returns_counts(tmp_path):
    """CNT-01: helper returns filtered lists and caches raw counts in ist."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True},
        {"id": 2, "title": "Movie B", "monitored": False},  # filtered out
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=50)

    state = _make_test_state()
    settings = make_settings()
    instance_config = _instance_config()

    result = await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert result is not None
    missing, cutoff = result
    assert len(missing) == 1  # only monitored
    assert state["radarr"]["Default"]["missing_count"] == 2
    assert state["radarr"]["Default"]["cutoff_count"] == 0
    assert state["radarr"]["Default"]["connected"] is True
    assert state["radarr"]["Default"]["missing_eligible"] == 1


async def test_refresh_radarr_counts_does_not_advance_cursor(tmp_path):
    """CNT-02: helper must not touch missing_cursor or cutoff_cursor."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[
        {"id": 1, "title": "Movie A", "monitored": True},
    ])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=1)

    state = _make_test_state()
    state["radarr"]["Default"]["missing_cursor"] = 5
    state["radarr"]["Default"]["cutoff_cursor"] = 3

    settings = make_settings()
    instance_config = _instance_config()

    await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert state["radarr"]["Default"]["missing_cursor"] == 5  # unchanged
    assert state["radarr"]["Default"]["cutoff_cursor"] == 3  # unchanged


async def test_refresh_radarr_counts_does_not_stamp_last_run(tmp_path):
    """CNT-03: helper must not write last_run or last_success."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.get_library_count = AsyncMock(return_value=0)

    state = _make_test_state()
    settings = make_settings()
    instance_config = _instance_config()

    await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert state["radarr"]["Default"].get("last_run") is None
    assert state["radarr"]["Default"].get("last_success") is None


async def test_refresh_radarr_counts_sets_connected_false_on_fetch_error(tmp_path):
    """CNT-03: fetch failure sets connected=False and returns None."""
    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(side_effect=httpx.ConnectError("refused"))

    state = _make_test_state()
    settings = make_settings()
    instance_config = _instance_config()

    result = await refresh_radarr_counts(client, state, "Default", instance_config, settings)

    assert result is None
    assert state["radarr"]["Default"]["connected"] is False
    assert state["radarr"]["Default"]["unreachable_since"] is not None
```

#### Route test scaffold (copy from test_web.py fixture + test_search_now_* pattern)

```python
@pytest.fixture
async def refresh_test_app(tmp_path):
    """Minimal FastAPI app with last_refresh_time initialized (mirrors test_app in test_web.py:28)."""
    app = FastAPI()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(router)

    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(db_path) as db:
        await init_db(db, db_path)
        app.state.db = db
        app.state.triggarr_state = {
            "radarr": {
                "Default": {
                    "missing_cursor": 0, "cutoff_cursor": 0,
                    "last_run": None, "connected": True,
                    "unreachable_since": None,
                    "missing_count": 5, "cutoff_count": 2,
                },
            },
            "sonarr": {"Default": {"missing_cursor": 0, "cutoff_cursor": 0,
                                   "last_run": None, "connected": None,
                                   "unreachable_since": None, "missing_count": None, "cutoff_count": None}},
            "lidarr": {"Default": {"missing_cursor": 0, "cutoff_cursor": 0,
                                   "last_run": None, "connected": None,
                                   "unreachable_since": None, "missing_count": None, "cutoff_count": None}},
            "search_log": [],
        }
        app.state.settings = make_settings(radarr_enabled=True, sonarr_enabled=True)
        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_job.next_run_time = None
        mock_scheduler.get_job.return_value = mock_job
        app.state.scheduler = mock_scheduler

        radarr_client = MagicMock()
        radarr_client.close = AsyncMock()
        sonarr_client = MagicMock()
        sonarr_client.close = AsyncMock()
        lidarr_client = MagicMock()
        lidarr_client.close = AsyncMock()
        app.state.radarr_clients = {"Default": radarr_client}
        app.state.sonarr_clients = {"Default": sonarr_client}
        app.state.lidarr_clients = {"Default": lidarr_client}

        app.state.config_path = tmp_path / "triggarr.toml"
        app.state.state_path = tmp_path / "state.json"
        app.state.search_lock = asyncio.Lock()
        app.state.search_lock_holder = None
        app.state.search_failures = {}
        app.state.persistence_degraded = False
        app.state.last_search_time = {}
        app.state.last_refresh_time = {}  # NEW: sibling rate-limit dict
        app.state.last_health_check = None
        app.state.tag_cache = {}

        yield app


@pytest.fixture
def refresh_client(refresh_test_app):
    return TestClient(refresh_test_app)


def test_refresh_counts_invalid_app(refresh_client):
    """POST /api/refresh-counts/invalid returns 400."""
    response = refresh_client.post("/api/refresh-counts/invalid/Default")
    assert response.status_code == 400
    assert "Invalid app" in response.text


def test_refresh_counts_happy_path(refresh_client, refresh_test_app):
    """POST /api/refresh-counts/radarr/Default returns 200 with card HTML."""
    with patch(
        "triggarr.web.routes.refresh_radarr_counts",
        new=AsyncMock(return_value=([], [])),
    ):
        response = refresh_client.post("/api/refresh-counts/radarr/Default")
    assert response.status_code == 200
    assert "Radarr" in response.text


def test_refresh_counts_rate_limited(refresh_client, refresh_test_app):
    """Second POST within rate window returns 429."""
    refresh_test_app.state.last_refresh_time["radarr_Default"] = time.monotonic()
    response = refresh_client.post("/api/refresh-counts/radarr/Default")
    assert response.status_code == 429
    assert "Rate limited" in response.text


def test_refresh_counts_rate_limit_concurrent_protection(refresh_client, refresh_test_app):
    """Two rapid requests: second returns 429 (DRSEC-03 parity)."""
    with patch(
        "triggarr.web.routes.refresh_radarr_counts",
        new=AsyncMock(return_value=([], [])),
    ):
        resp1 = refresh_client.post("/api/refresh-counts/radarr/Default")
        assert resp1.status_code == 200
        resp2 = refresh_client.post("/api/refresh-counts/radarr/Default")
        assert resp2.status_code == 429
        assert "Rate limited" in resp2.text


def test_refresh_counts_does_not_touch_failure_counter(refresh_client, refresh_test_app):
    """search_failures dict untouched by refresh_counts (CNT-03)."""
    refresh_test_app.state.search_failures["radarr_Default_search"] = 0
    with patch(
        "triggarr.web.routes.refresh_radarr_counts",
        new=AsyncMock(return_value=([], [])),
    ):
        refresh_client.post("/api/refresh-counts/radarr/Default")
    assert refresh_test_app.state.search_failures.get("radarr_Default_search", 0) == 0


def test_refresh_counts_does_not_touch_last_search_time(refresh_client, refresh_test_app):
    """last_search_time dict untouched (independent rate-limit dicts)."""
    with patch(
        "triggarr.web.routes.refresh_radarr_counts",
        new=AsyncMock(return_value=([], [])),
    ):
        refresh_client.post("/api/refresh-counts/radarr/Default")
    assert "radarr_Default" not in refresh_test_app.state.last_search_time


def test_app_card_connected_has_refresh_counts_button(refresh_client):
    """CNT-05: connected card partial contains 'Refresh counts' button."""
    response = refresh_client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Refresh counts" in response.text


def test_app_card_disconnected_no_refresh_counts_button(refresh_client, refresh_test_app):
    """CNT-05: disconnected card does NOT contain 'Refresh counts' button."""
    refresh_test_app.state.triggarr_state["radarr"]["Default"]["connected"] = False
    response = refresh_client.get("/partials/app-card/radarr/Default")
    assert response.status_code == 200
    assert "Refresh counts" not in response.text
    assert "Retry Connection" in response.text
```

---

### `tests/test_web.py` — Fixture modification

**Analog:** `test_app` fixture (test_web.py:28)

**Single line to add** at line 123, immediately after `app.state.last_search_time = {}` (line 122):

```python
        # Rate limit state (needed by search_now rate limiter — DEBT-01)
        app.state.last_search_time = {}
        app.state.last_refresh_time = {}          # NEW: Phase 74 sibling dict
        app.state.last_health_check = None
```

Without this addition, any test that hits `GET /partials/app-card/...` after Phase 74 routes are registered will raise `AttributeError: 'State' object has no attribute 'last_refresh_time'` — Pitfall 7 from RESEARCH.md.

---

## Shared Patterns

### Authentication / access control
**Source:** `triggarr/web/routes.py` — `search_now` guards (lines 883-893)
**Apply to:** `refresh_counts` endpoint
```python
    if len(instance_name) > 64:
        return HTMLResponse("Instance name too long", status_code=400)
    if app_name not in APP_TYPES:
        return HTMLResponse("Invalid app", status_code=400)
    clients = getattr(request.app.state, f"{app_name}_clients", {})
    enabled = request.app.state.settings.get_enabled_instances(app_name)
    if instance_name not in enabled or instance_name not in clients:
        return HTMLResponse("Instance not enabled", status_code=400)
```

### Error handling (always-200 + card, _sanitize_exc)
**Source:** `triggarr/web/routes.py` — `search_now` except block (lines 948-964)
**Apply to:** `refresh_counts` endpoint — mirror the exact `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` tuple and `_sanitize_exc` split
```python
        except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
            logger.error(
                "{name}/{inst}: ... -- {exc}",
                name=app_name.title(),
                inst=instance_name,
                exc=(
                    _sanitize_exc(exc)
                    if isinstance(exc, httpx.HTTPError | pydantic.ValidationError)
                    else str(exc)
                ),
            )
```

### DRSEC-03 double-check inside search_lock
**Source:** `triggarr/web/routes.py` (lines 903-913)
**Apply to:** `refresh_counts` rate-limit block
Optimistic check before lock + re-check after lock acquisition. Use `last_refresh_time` instead of `last_search_time`.

### ist mutation pattern (abort branch)
**Source:** `triggarr/search/engine.py` — abort branch in `run_radarr_cycle` (lines 315-323)
**Apply to:** All three `refresh_*_counts` helpers — abort branch sets `connected=False`, `tag_warnings=[]`, conditionally sets `unreachable_since`, returns `None`

### ist mutation pattern (success branch)
**Source:** `triggarr/search/engine.py` — lines 332-339
**Apply to:** All three `refresh_*_counts` helpers — success sets `connected=True`, `unreachable_since=None`, then writes raw count fields

### Tag cache resolver
**Source:** `triggarr/web/routes.py` — `_get_tags_cached` closure (lines 922-931); also `triggarr/search/scheduler.py` — `_get_tags_cached` closure (lines 152-161)
**Apply to:** `refresh_counts` endpoint — copy verbatim, same `_TAG_CACHE_TTL_SECONDS` import from scheduler

---

## No Analog Found

All files have close analogs. No "no analog" entries.

---

## Seam Confirmation (live line numbers verified)

| Cycle Function | Prefix range | Seam (first slice_batch line) | Last ist write in prefix |
|----------------|--------------|-------------------------------|--------------------------|
| `run_radarr_cycle` (engine.py:275) | lines 306-406 | line 408 | `ist["missing_eligible"] = len(missing)` line 406 |
| `run_sonarr_cycle` (engine.py:517) | lines 549-645 (+700 for cutoff_searchable) | line 647 | `ist["missing_searchable"] = len(missing_seasons)` line 645; `ist["cutoff_searchable"]` moved from line 700 into helper |
| `run_lidarr_cycle` (engine.py:766) | lines 801-896 | line 898 | `ist["missing_eligible"] = len(missing)` line 896 |

**Lidarr note:** Confirmed by reading lines 801-898 — no `cutoff_searchable` write anywhere in Lidarr cycle. Template at app_card.html:98 uses `cutoff_searchable if cutoff_searchable is not none else cutoff_count`, so Lidarr simply shows `cutoff_count`.

---

## Metadata

**Analog search scope:** `triggarr/search/engine.py`, `triggarr/web/routes.py`, `triggarr/search/scheduler.py`, `triggarr/templates/partials/app_card.html`, `tests/test_search.py`, `tests/test_web.py`, `tests/conftest.py`
**Files scanned:** 7 source files + 2 planning documents
**Pattern extraction date:** 2026-06-03
