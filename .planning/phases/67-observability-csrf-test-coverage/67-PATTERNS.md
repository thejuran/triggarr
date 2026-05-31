# Phase 67: Observability & CSRF Test Coverage - Pattern Map

**Mapped:** 2026-05-31
**Files analyzed:** 8 source files to modify + 4 test files to extend
**Analogs found:** 12 / 12

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `triggarr/state.py` | model | CRUD | existing `last_run: str \| None` field at line 50 | exact |
| `triggarr/search/engine.py` | service | request-response | existing `ist["last_run"] = ...` at lines 506/748/984; existing `get_tags()` block at lines 357-367 | exact |
| `triggarr/search/scheduler.py` | service | event-driven | existing `app.state.search_failures = {}` init at line 445; `_SHUTDOWN_DRAIN_TIMEOUT` at line 81 | exact |
| `triggarr/web/routes.py` (_build_app_context) | controller | request-response | existing `app_state.get("last_run")` at line 278; existing `url_changed` diff at lines 633-634 | exact |
| `triggarr/web/routes.py` (remove_instance) | controller | request-response | existing `triggarr_state[app_name].pop(instance_name, None)` at line 813 | exact |
| `triggarr/templates/partials/app_card.html` | component | request-response | existing schedule row at lines 51-54; existing amber badge at lines 38-48 | exact |
| `tests/test_middleware.py` | test | request-response | existing `test_post_matching_origin_passes` / `test_post_mismatched_origin_returns_403` at lines 34-49 | exact |
| `tests/test_search.py` | test | request-response | existing `test_run_radarr_cycle_happy_path` at lines 241-271 | exact |
| `tests/test_state.py` | test | CRUD | existing `test_nested_state_round_trip` at lines 24-45 | exact |
| `tests/test_scheduler.py` | test | event-driven | existing `app.state` setup block at lines 53-65, 85-91 | exact |
| `tests/test_web.py` | test | request-response | (see shared patterns — no specific excerpt pulled) | role-match |

---

## Pattern Assignments

### `triggarr/state.py` — add `last_success` to AppState + `_default_instance_state()`

**Analog:** existing `last_run` field, same file

**TypedDict field pattern** (lines 43-61 — add beside `last_run`):
```python
class AppState(TypedDict, total=False):
    ...
    last_run: str | None  # ISO timestamp        ← existing line 50
    last_success: str | None  # ISO timestamp — last cycle that reached connected=True
    connected: bool | None  # True after successful fetch, False after failure
```

**`_default_instance_state` pattern** (lines 76-78 — add `last_success=None`):
```python
def _default_instance_state() -> AppState:
    """Return a fresh AppState for a single instance at cursor 0."""
    return AppState(missing_cursor=0, cutoff_cursor=0, last_run=None, last_success=None)
```

**Why no serialization change needed:** `save_state` at line 205 calls `json.dump(state, f, indent=2)` — any key written to the TypedDict is automatically persisted. `_merge_defaults` at line 142 does `{**_default_instance_state(), **instance_data}`, so loaded instances that already have `last_success` preserve it; fresh instances get `None` from the default.

---

### `triggarr/search/engine.py` — write `last_success` at cycle success + wrap `get_tags()` with resolver

#### RES-02: last_success write

**Analog:** `ist["last_run"] = ...` at lines 505-506 (Radarr), 747-748 (Sonarr), 983-984 (Lidarr)

**Success-point write pattern** (line 505-506, exact):
```python
# --- Update last_run ---
ist["last_run"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
```
Add `last_success` immediately after (or capture once):
```python
# --- Update last_run and last_success ---
now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
ist["last_run"] = now_iso
ist["last_success"] = now_iso
```
Repeat at lines 747-748 (Sonarr) and 983-984 (Lidarr) — same pattern, same position.

**Why this location:** Line 506 is only reached when the cycle did NOT early-return at the connection-error path (lines 313-321). `ist["connected"] = True` is set at line 331, which is inside the connected branch. `last_success` at line 506 is strictly "cycle reached connected-True end" — the same semantics as D-02.

#### RES-03: get_tags_fn parameter + resolver call

**Analog:** existing `get_tags()` block at lines 357-367 (Radarr):
```python
if instance_config.missing_tag or instance_config.cutoff_tag:
    tag_fetch_ok = False
    try:
        tags = await client.get_tags()           # ← line 360 — wrap this
        tag_fetch_ok = True
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning(
            "Radarr: Failed to fetch tags -- skipping tag filtering: {exc}",
            exc=_sanitize_exc(exc),
        )
        tags = []
```

**New cycle fn signature pattern** (keyword-only, None default preserves all existing tests):
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
```
Required import addition to engine.py: `from collections.abc import Awaitable, Callable` (check if already present — Callable may already be imported).

**Replace `await client.get_tags()` with resolver call:**
```python
if instance_config.missing_tag or instance_config.cutoff_tag:
    tag_fetch_ok = False
    try:
        if get_tags_fn is not None:
            tags = await get_tags_fn()
        else:
            tags = await client.get_tags()
        tag_fetch_ok = True
    except (httpx.HTTPError, pydantic.ValidationError) as exc:
        logger.warning(
            "Radarr: Failed to fetch tags -- skipping tag filtering: {exc}",
            exc=_sanitize_exc(exc),
        )
        tags = []
```
Same substitution at lines 594-597 (Sonarr) and 839-842 (Lidarr).

**Critical:** The resolver must NOT catch exceptions — if `get_tags_fn()` raises, the exception propagates to the existing `except (httpx.HTTPError, pydantic.ValidationError)` guard, which sets `tags=[]` and `tag_fetch_ok=False`. This is exactly D-07's "only cache successful fetches" requirement — the cache store line in the resolver is never reached when an exception propagates.

---

### `triggarr/search/scheduler.py` — module constant, tag_cache init, resolver factory

#### Module constant pattern

**Analog:** `_SHUTDOWN_DRAIN_TIMEOUT` at line 81:
```python
# RES-01 (Codex finding 3): configurable; default 60.0s; clamped >= 1.0 to
# prevent misconfig disabling drain entirely. ...
_SHUTDOWN_DRAIN_TIMEOUT: float = _read_shutdown_drain_timeout()
```

**New constant** (add near line 81, after `_SHUTDOWN_DRAIN_TIMEOUT`):
```python
# RES-03: tag-list cache TTL. Successful get_tags() responses are cached in
# app.state.tag_cache for this duration (using time.monotonic()). 1 hour
# matches the typical *arr tag-list churn rate. Invalidated on instance
# config save (url/api_key/missing_tag/cutoff_tag changes).
_TAG_CACHE_TTL_SECONDS: float = 3600.0
```

#### app.state.tag_cache initialization in lifespan

**Analog:** existing `app.state` scratch dict inits at lines 437-457:
```python
# WR-05: `app.state` is starlette.datastructures.State ...
# last_search_time: dict[str, float]  (key: rate-limit token, value: monotonic ts)
app.state.last_search_time = {}
...
# search_failures: dict[str, int]
app.state.search_failures = {}
...
# search_lock_holder: tuple[str, float] | None
app.state.search_lock_holder = None
```

**New init** (add after line 457, following the WR-05 comment style):
```python
# RES-03: tag-list cache keyed by (app_name, instance_name).
# value: (tags: list[Tag], fetched_at: float) where fetched_at is time.monotonic().
# Invalidated on instance config save for changed instances; cleared on remove_instance.
# tag_cache: dict[tuple[str, str], tuple[list, float]]
app.state.tag_cache = {}
```

#### Resolver factory in `make_search_job` job() closure

**Analog:** existing "read from app.state at call time" pattern at lines 136-143:
```python
async def job() -> None:
    clients = getattr(app.state, f"{app_name}_clients", {})
    client = clients.get(instance_name)
    ...
    async with app.state.search_lock:
        ...
        app.state.triggarr_state = await cycle_fn(
            client,
            app.state.triggarr_state,
            instance_name,
            instance_config,
            app.state.settings,
            app.state.db,
        )
```

**Resolver built inside job() at call time** (add before `await cycle_fn(...)`, inside `async with app.state.search_lock`):
```python
# RES-03: build tag resolver at job execution time (reads app.state.tag_cache at
# call time — consistent with the "read from app.state at call time" philosophy).
cache_key = (app_name, instance_name)

async def _get_tags_cached() -> list:
    cache = app.state.tag_cache
    entry = cache.get(cache_key)
    if entry is not None:
        cached_tags, fetched_at = entry
        if time.monotonic() - fetched_at < _TAG_CACHE_TTL_SECONDS:
            return cached_tags
    # Cache miss or TTL expired — fetch from API.
    # Raises on error; caller's except guard handles (no negative caching).
    fresh_tags = await client.get_tags()
    cache[cache_key] = (fresh_tags, time.monotonic())
    return fresh_tags

app.state.triggarr_state = await cycle_fn(
    client,
    app.state.triggarr_state,
    instance_name,
    instance_config,
    app.state.settings,
    app.state.db,
    get_tags_fn=_get_tags_cached,
)
```
`time` is already imported at line 27. `_TAG_CACHE_TTL_SECONDS` is defined in this module.

---

### `triggarr/web/routes.py` — `_build_app_context` stale computation + `save_settings` invalidation + `remove_instance` cleanup

#### RES-02: stale computation in `_build_app_context`

**Analog:** existing `app_state.get("last_run")` read and context dict return at lines 278-295:
```python
return {
    ...
    "last_run": app_state.get("last_run"),
    ...
    "tag_warnings": app_state.get("tag_warnings", []),
}
```

**Import change** (line 16, add `timedelta`):
```python
# before:
from datetime import UTC, datetime
# after:
from datetime import UTC, datetime, timedelta
```

**Stale computation** (add after `app_state = ...` resolution at line 265, before the `return` at line 274):
```python
last_success = app_state.get("last_success")
last_success_stale = True  # default: no timestamp = stale
if last_success is not None:
    try:
        ls_dt = datetime.fromisoformat(last_success.replace("Z", "+00:00"))
        instance_cfg = enabled[instance_name]
        threshold = timedelta(minutes=instance_cfg.search_interval * 2)
        last_success_stale = (datetime.now(UTC) - ls_dt) > threshold
    except (ValueError, TypeError):
        last_success_stale = True
```

**Add to returned dict** (alongside `last_run`):
```python
return {
    ...
    "last_run": app_state.get("last_run"),
    "last_success": last_success,
    "last_success_stale": last_success_stale,
    ...
}
```

**Note:** `enabled[instance_name]` is safe at this point — the function returns `None` early at line 262 if `instance_name not in enabled`, so it is always resolved before reaching this code.

#### RES-03: tag cache invalidation in `save_settings`

**Analog:** existing `url_changed` / `key_changed` diff at lines 630-634, inside the `async with request.app.state.search_lock:` block:
```python
async with request.app.state.search_lock:
    ...
    for name in APP_TYPES:
        new_instances = getattr(new_settings, name)
        old_instances = getattr(current_settings, name)
        ...
        for inst_name, new_cfg in new_instances.items():
            ...
            old_cfg = old_instances.get(inst_name)
            url_changed = old_cfg is None or new_cfg.url != old_cfg.url
            key_changed = old_cfg is None or new_cfg.api_key != old_cfg.api_key
```

**Tag cache invalidation** (add after the scheduler/client update loop at ~line 665, still inside `search_lock`):
```python
# RES-03: invalidate tag cache for instances whose cache-relevant config changed.
for name in APP_TYPES:
    new_instances = getattr(new_settings, name)
    old_instances = getattr(current_settings, name)
    for inst_name, new_cfg in new_instances.items():
        old_cfg = old_instances.get(inst_name)
        if old_cfg is None:
            continue  # new instance — no cache entry yet
        cache_relevant_changed = (
            new_cfg.url != old_cfg.url
            or new_cfg.api_key != old_cfg.api_key
            or new_cfg.missing_tag != old_cfg.missing_tag
            or new_cfg.cutoff_tag != old_cfg.cutoff_tag
        )
        if cache_relevant_changed:
            request.app.state.tag_cache.pop((name, inst_name), None)
```
`current_settings` is captured at line 507 (before lock), `new_settings` is the validated model at line 582 — both in scope throughout the handler.

#### RES-03: tag cache cleanup in `remove_instance`

**Analog:** existing state entry cleanup at lines 810-813:
```python
# Clean up state entry
triggarr_state = request.app.state.triggarr_state
if app_name in triggarr_state:
    triggarr_state[app_name].pop(instance_name, None)
```

**Add after state cleanup** (inside the `async with request.app.state.search_lock:` block):
```python
# RES-03: clean up tag cache entry for removed instance
request.app.state.tag_cache.pop((app_name, instance_name), None)
```

---

### `triggarr/templates/partials/app_card.html` — "Last OK" entry in schedule row

**Analog 1:** existing schedule row at lines 51-54:
```html
<div class="text-[11px] font-mono text-triggarr-muted mb-4 flex justify-between">
  <span>Last run: <span class="text-triggarr-text">{% if app.last_run %}{{ app.last_run[11:19] }}{% else %}Never{% endif %}</span></span>
  <span>Next: <span class="text-triggarr-text">{% if app.next_run %}{{ app.next_run[11:16] }}{% else %}&mdash;{% endif %}</span></span>
</div>
```
Key patterns to copy: `[11:19]` slice for HH:MM:SS, `Never` fallback, `text-triggarr-text` class for live values.

**Analog 2:** existing amber tag-warning badge at lines 38-48:
```html
<div class="bg-amber-500/15 text-amber-400 text-xs px-3 py-1.5 rounded mb-3 ...">
```
Key tokens: `bg-amber-500/15 text-amber-400` — reuse for stale flag, do not invent new color.

**"Last OK" entry** (add as third `<span>` in the schedule row `<div>`, or as a second row beneath):
```html
<span>Last OK:
  {% if app.last_success %}
    <span class="{% if app.last_success_stale %}text-amber-400{% else %}text-triggarr-text{% endif %}">{{ app.last_success[11:19] }}</span>
  {% else %}
    <span class="text-triggarr-muted">Never</span>
  {% endif %}
</span>
```
**Critical (Pitfall 4):** Amber only when `app.last_success` is truthy AND `app.last_success_stale`. "Never" (null `last_success`) renders in muted color — amber implies stale data, not "no data yet". The template condition `{% if app.last_success_stale %}` is guarded by the outer `{% if app.last_success %}` — do not check `last_success_stale` in the `else` branch.

**Layout note:** Three spans in `flex justify-between` changes the two-column layout to three-column. If the card's narrow width makes this crowded, the planner may render "Last OK" on a second `<div>` row beneath the existing "Last run / Next" row.

---

### `tests/test_middleware.py` — new CSRF scenario tests

**Analog:** existing `_make_app()` + module-level `client` + test pattern at lines 15-49:
```python
def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(OriginCheckMiddleware)
    @app.post("/test")
    async def post_endpoint():
        return {"status": "ok"}
    return app

client = TestClient(_make_app())

def test_post_matching_origin_passes():
    response = client.post(
        "/test",
        headers={"Origin": "http://testserver", "Host": "testserver"},
    )
    assert response.status_code == 200
```
All new tests: same `client` (module-level), same header-crafting shape, `assert response.status_code == N`, no internal middleware state access.

**Five new test functions to add** (after line 83, before the DEBT-02 section):

```python
def test_post_missing_origin_with_matching_referer_passes():
    """POST with Origin absent and Referer matching Host returns 200.
    Explicit missing-Origin coverage — middleware falls through to Referer check."""
    response = client.post(
        "/test",
        headers={"Referer": "http://testserver/page", "Host": "testserver"},
    )
    assert response.status_code == 200


def test_post_missing_referer_with_matching_origin_passes():
    """POST with Referer absent and Origin matching Host returns 200.
    Explicit missing-Referer coverage — middleware evaluates Origin branch."""
    response = client.post(
        "/test",
        headers={"Origin": "http://testserver", "Host": "testserver"},
    )
    assert response.status_code == 200


def test_post_scheme_mismatch_is_allowed():
    """POST with Origin=https://testserver against Host=testserver returns 200.

    The middleware compares urlparse(origin).netloc (which strips scheme) against
    the raw Host header value. 'https://testserver' has netloc='testserver',
    which equals Host='testserver', so scheme differences are IGNORED.

    In Triggarr's single-origin deployment model this is not a security bypass:
    an attacker cannot cause a browser to emit Origin: https://testserver from
    a cross-origin page. This test PINS the current behavior so any future
    refactor that inadvertently changes it is caught immediately.
    Do NOT change this test to assert 403 — scheme comparison is intentionally
    absent from the middleware (D-10 in Phase 67 CONTEXT.md).
    """
    response = client.post(
        "/test",
        headers={"Origin": "https://testserver", "Host": "testserver"},
    )
    assert response.status_code == 200


def test_post_suffix_spoof_returns_403():
    """POST with Origin=https://testserver.evil.com against Host=testserver returns 403.
    urlparse netloc='testserver.evil.com' != 'testserver' — suffix spoof rejected."""
    response = client.post(
        "/test",
        headers={"Origin": "https://testserver.evil.com", "Host": "testserver"},
    )
    assert response.status_code == 403


def test_post_port_mismatch_returns_403():
    """POST with Origin=http://testserver:8080 against Host=testserver returns 403.
    urlparse netloc='testserver:8080' != 'testserver' — port mismatch rejected."""
    response = client.post(
        "/test",
        headers={"Origin": "http://testserver:8080", "Host": "testserver"},
    )
    assert response.status_code == 403
```

---

### `tests/test_search.py` — RES-02 (last_success) + RES-03 (cache hit/miss) tests

**Analog:** `test_run_radarr_cycle_happy_path` at lines 241-271:
```python
async def test_run_radarr_cycle_happy_path(tmp_path):
    db_path = tmp_path / "test.db"
    db = await aiosqlite.connect(db_path)
    await init_db(db, db_path)

    client = AsyncMock()
    client.get_wanted_missing = AsyncMock(return_value=[...])
    client.get_wanted_cutoff = AsyncMock(return_value=[])
    client.search_movies = AsyncMock()

    state = _make_test_state()
    settings = _cycle_settings(missing_count=2, cutoff_count=2)
    instance_config = _cycle_instance_config(missing_count=2, cutoff_count=2)

    result = await run_radarr_cycle(client, state, "Default", instance_config, settings, db)

    assert result["radarr"]["Default"]["last_run"] is not None
    assert result["radarr"]["Default"]["connected"] is True
    await db.close()
```

**New RES-02 tests** — extend the happy-path / failure patterns:
- `test_run_radarr_cycle_writes_last_success_on_success` — call with no `get_tags_fn` (tag-free config), assert `result["radarr"]["Default"]["last_success"] is not None`.
- `test_run_radarr_cycle_does_not_write_last_success_on_failure` — reuse the `test_run_radarr_cycle_network_failure` pattern (httpx.ConnectError side_effect), assert `result["radarr"]["Default"].get("last_success") is None`.

**New RES-03 tests** — use `AsyncMock` as `get_tags_fn`:
- `test_run_radarr_cycle_uses_get_tags_fn_when_provided` — pass `get_tags_fn=AsyncMock(return_value=[])`, assert `client.get_tags` is NOT called.
- `test_run_radarr_cycle_falls_back_to_client_get_tags_when_no_fn` — pass no `get_tags_fn`, assert `client.get_tags` IS called (for a tag-configured instance).
- `test_run_radarr_cycle_get_tags_fn_exception_sets_tag_fetch_ok_false` — pass `get_tags_fn=AsyncMock(side_effect=httpx.ConnectError("x"))`, assert cycle does not raise and `ist["tag_warnings"]` behavior is correct.

**Important (Pitfall 1):** All existing tests call cycle fns with 6 positional args. The new `get_tags_fn` is keyword-only (`*`), so existing calls are unchanged. New tests that need to exercise the resolver pass `get_tags_fn=AsyncMock(...)`.

---

### `tests/test_state.py` — RES-02 state round-trip

**Analog:** `test_nested_state_round_trip` at lines 24-45:
```python
def test_nested_state_round_trip(tmp_path: Path) -> None:
    state = TriggarrState(
        radarr={"Default": AppState(missing_cursor=42, cutoff_cursor=7, last_run="2026-01-15T10:00:00Z")},
        ...
    )
    save_state(state, state_file)
    loaded = load_state(state_file)
    assert loaded["radarr"]["Default"]["missing_cursor"] == 42
    assert loaded["radarr"]["Default"]["last_run"] == ...
```

**New tests:**
- `test_last_success_persists_round_trip` — write `AppState(..., last_success="2026-05-31T10:00:00Z")`, save, load, assert `loaded["radarr"]["Default"]["last_success"] == "2026-05-31T10:00:00Z"`.
- `test_last_success_defaults_to_none_for_fresh_state` — load a state JSON without a `last_success` key, assert `loaded["radarr"]["Default"].get("last_success") is None` (verifies `_merge_defaults` fills the default).

---

### `tests/test_scheduler.py` — RES-03 tag cache init + TTL behavior

**Analog:** existing `app.state` setup block at lines 53-65:
```python
app.state.radarr_clients = {"Default": AsyncMock()}
app.state.search_lock = asyncio.Lock()
app.state.search_failures = {}
app.state.search_lock_holder = None
app.state.triggarr_state = _default_state(make_settings())
app.state.settings = make_settings()
app.state.db = MagicMock()
```

**All existing tests that exercise `make_search_job`** will need `app.state.tag_cache = {}` added to their setup (Pitfall 8). The tests that call `job()` will reach the new resolver code which reads `app.state.tag_cache`.

**New RES-03 tests** (follow the `test_make_search_job_httperror_swallowed` shape with patches):
- `test_tag_cache_hit_skips_get_tags_call` — pre-populate `app.state.tag_cache[("radarr", "Default")] = ([], time.monotonic())`, patch cycle_fn to an AsyncMock, patch `client.get_tags` to assert it is NOT called via the resolver.
- `test_tag_cache_miss_calls_get_tags_and_stores_result` — start with empty `app.state.tag_cache`, configure a tag in `instance_config`, run job, assert `app.state.tag_cache[("radarr", "Default")]` is populated after a successful cycle.
- `test_tag_cache_ttl_expired_triggers_fresh_fetch` — pre-populate with a stale entry (fetched_at far in the past beyond TTL), assert `client.get_tags` is called again.

---

## Shared Patterns

### ISO-8601-Z timestamp write (all engine cycle fns)
**Source:** `triggarr/search/engine.py` line 506
**Apply to:** All three cycle fn success points (lines 506, 748, 984)
```python
ist["last_run"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
```
`last_success` uses the identical expression. Capture both in one `now_iso` variable for efficiency.

### app.state scratch dict initialization (lifespan block)
**Source:** `triggarr/search/scheduler.py` lines 437-457
**Apply to:** `app.state.tag_cache = {}` addition
Follow the WR-05 comment style: doc-comment above each entry describes `type: description` since Starlette State discards runtime annotations.

### Module constant pattern
**Source:** `triggarr/search/scheduler.py` line 81
**Apply to:** `_TAG_CACHE_TTL_SECONDS: float = 3600.0`
No env-override function needed for the TTL (it is not operator-configurable like the drain timeout).

### `time.monotonic()` for elapsed-time logic
**Source:** `triggarr/search/scheduler.py` line 131 (`app.state.search_lock_holder = (job_id, time.monotonic())`)
**Apply to:** tag cache TTL comparison in the resolver
Do NOT use `datetime.now(UTC)` for TTL — monotonic is immune to NTP/clock-drift.

### TestClient CSRF test harness
**Source:** `tests/test_middleware.py` lines 15-31
**Apply to:** All five new TEST-01 test functions
Same module-level `client = TestClient(_make_app())`, same `headers={}` crafting, same `assert response.status_code == N`. No `_make_settings_app()` needed — the simple `_make_app()` harness suffices.

### Under-`search_lock` mutation
**Source:** `triggarr/web/routes.py` lines 591-665 (save_settings) and lines 789-813 (remove_instance)
**Apply to:** tag cache invalidation (save_settings) and tag cache cleanup (remove_instance)
Both already acquire `request.app.state.search_lock` — the new tag_cache operations go inside the existing lock block, no new locking.

### Error handling in cycle fns
**Source:** `triggarr/search/engine.py` lines 362-367 (tag-fetch failure path)
**Apply to:** resolver callable must NOT catch exceptions — let them propagate to the existing `except (httpx.HTTPError, pydantic.ValidationError)` guard
```python
except (httpx.HTTPError, pydantic.ValidationError) as exc:
    logger.warning(
        "Radarr: Failed to fetch tags -- skipping tag filtering: {exc}",
        exc=_sanitize_exc(exc),
    )
    tags = []
```

---

## No Analog Found

All files in scope have close existing analogs. No entries.

---

## Metadata

**Analog search scope:** `/Users/julianamacbook/triggarr/triggarr/`, `/Users/julianamacbook/triggarr/tests/`
**Files scanned:** 10
**Pattern extraction date:** 2026-05-31
