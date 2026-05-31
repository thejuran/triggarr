# Phase 67: Observability & CSRF Test Coverage - Research

**Researched:** 2026-05-31
**Domain:** FastAPI app.state extension, engine state threading, Jinja2 template rendering, pytest TestClient middleware testing
**Confidence:** HIGH — all findings sourced directly from the project codebase

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Add `last_success: str | None` (ISO-8601 `…Z`) to `AppState` TypedDict in `triggarr/state.py:48-51`. Default `None` in `_default_instance_state()`.
- **D-02:** Write `ist["last_success"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")` at the same success point as `ist["connected"] = True` in each cycle fn (engine.py:331/505, 567/748, 812/984). Manual `search_now` calls cycle fn directly so it updates too.
- **D-03:** Stale flag computed at render time in `_build_app_context`. `last_success_stale = (last_success is None) OR (now - last_success > 2 × search_interval_minutes)`. Expose `last_success` and `last_success_stale` in the context dict.
- **D-04:** Render on `app_card.html` schedule row (lines 50-53). "Last OK" entry showing `last_success[11:19]` or "Never". Amber treatment (`text-amber-400` / `bg-amber-500/15`) when stale and value exists. No new polling wiring needed.
- **D-05:** `app.state.tag_cache: dict[tuple[str, str], tuple[list[Tag], float]]` keyed `(app_name, instance_name)` → `(tags, fetched_at_monotonic)`. Initialize `{}` in the lifespan `app.state` block (scheduler.py:409-457).
- **D-06:** 1-hour TTL. Module constant `_TAG_CACHE_TTL_SECONDS = 3600.0` (mirrors `_SHUTDOWN_DRAIN_TIMEOUT` pattern). Cache only successful fetches; on error: warn + `tags=[]` + `tag_fetch_ok=False` (no negative caching).
- **D-07:** Tag cache wraps `get_tags()` call sites in engine.py. Coupling mechanism for cycle fns to reach the cache is Claude's discretion (resolver callable, cache dict pass-through, or `app.state` passthrough).
- **D-08:** Targeted invalidation in the settings-save handler in `routes.py` under `search_lock`, after config write. Delete entries for instances whose `url`, `api_key`, `missing_tag`, or `cutoff_tag` changed. Acceptable fallback: invalidate all entries present in new config.
- **D-09:** Pure test work — no middleware modifications. Add ROADMAP-named scenarios.
- **D-10:** Scheme-mismatch test PINS current behavior (ALLOW) with explanatory comment — middleware compares `urlparse(origin).netloc` (strips scheme), so `Origin: https://testserver` with `Host: testserver` is ALLOWED.
- **D-11:** Spoofed-host tests assert REJECT: `Origin: http://evil.com` → 403, `Origin: https://testserver.evil.com` → 403, `Origin: http://testserver:8080` vs `Host: testserver` → 403.
- **D-12:** All tests drive through `TestClient` with crafted headers, assert status only, no internal middleware state coupling.

### Claude's Discretion
- Exact threading mechanism for tag cache into engine cycle fns (D-07): resolver callable vs. cache dict pass-through vs. `app.state` passthrough.
- Exact amber stale-flag markup position on the card (D-04): must reuse existing amber tokens.
- Whether changed-instance diff for D-08 lives inline in the save handler or in a small helper.

### Deferred Ideas (OUT OF SCOPE)
- Per-app-type rollup of last-successful-search (stats/health strip).
- Scheduler job dashboard (OBS-01 in STATE.md).
- Hardening OriginCheck to compare scheme.
- Caching `get_tags()` failure results (negative caching).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RES-02 | Dashboard surfaces "last successful search" timestamp per app type, visibly stale-flagged when older than 2× configured interval | D-01/D-02: TypedDict + engine write; D-03: render-time stale computation; D-04: app_card template extension |
| RES-03 | Tag list responses cached in `app.state` with 1h TTL, invalidated on instance config save | D-05/D-06: cache structure + TTL; D-07: wraps engine get_tags() calls; D-08: save handler invalidation |
| TEST-01 | OriginCheckMiddleware test suite covers missing Origin, missing Referer, both missing, scheme mismatch, spoofed-host | D-09/D-10/D-11/D-12: existing harness extensible; specific behaviors verified from source |
</phase_requirements>

---

## Summary

Phase 67 has three independent fronts within a single-process FastAPI daemon. All work stays within existing files — no new routes, no new config keys, no new dependencies.

**RES-02** adds a `last_success` field parallel to the existing `last_run` field, threading through four layers that already exist for `last_run`: TypedDict definition in state.py, write at cycle success in engine.py, render-time stale computation in `_build_app_context` in routes.py, and Jinja template in `app_card.html`. The `save_state` function serialises `json.dump(state, ...)` over the entire TypedDict — any new key written to the dict is automatically persisted, so no serialization changes are needed.

**RES-03** adds `app.state.tag_cache` as a plain dict initialized in the lifespan block alongside the existing scratch dicts (`search_failures`, `last_search_time`). The central design question is how engine cycle functions — which currently have no access to `app.state` — should reach the cache. Analysis of existing call sites (scheduler `make_search_job` closure and routes `search_now` endpoint) determines the appropriate threading mechanism.

**TEST-01** is pure test extension work. All five ROADMAP scenarios can be added to `tests/test_middleware.py` following the existing `_make_app()` + `TestClient` harness exactly. One scenario (scheme mismatch) requires a behavior-documenting comment rather than a behavioral fix.

**Primary recommendation:** Implement the three fronts as parallel waves. RES-02 and TEST-01 are fully independent. RES-03 depends on understanding the call-site coupling mechanism (resolved below in Research Q1).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| last_success timestamp write | API/Backend (engine) | — | Engine owns cycle execution; writes happen at the success point |
| Stale flag computation | API/Backend (routes) | — | Computed at render time in `_build_app_context`; render-time not stored |
| last_success template display | Frontend (Jinja/htmx) | — | Card already auto-refreshes every 5s; no new polling |
| Tag cache storage | API/Backend (app.state) | — | In-process singleton dict; single worker |
| Tag cache TTL resolution | API/Backend (engine) | — | Wraps the existing `get_tags()` call site per cycle |
| Tag cache invalidation | API/Backend (routes) | — | Settings-save handler under search_lock |
| CSRF test harness | Test layer | — | Pure test extension; middleware itself unchanged |

---

## Research Findings by Question

### Q1: Tag-Cache Threading — Cycle Fn Access to app.state

**Current cycle fn signatures (VERIFIED from engine.py):**

```python
async def run_radarr_cycle(
    client: RadarrClient,
    state: TriggarrState,
    instance_name: str,
    instance_config: InstanceConfig,
    settings: Settings,
    db: aiosqlite.Connection,
) -> TriggarrState:
```

All three cycle functions (`run_radarr_cycle`, `run_sonarr_cycle`, `run_lidarr_cycle`) have identical parameter shapes. None receives `app.state` or any cache object.

**Call site 1 — `make_search_job` job() closure (scheduler.py:136-143):**
```python
app.state.triggarr_state = await cycle_fn(
    client,
    app.state.triggarr_state,
    instance_name,
    instance_config,
    app.state.settings,
    app.state.db,
)
```
The closure captures `app` directly and reads `app.state` at call time. This is the stated "read from app.state at call time" philosophy. `app` is fully available here.

**Call site 2 — `search_now` endpoint (routes.py:870-877):**
```python
request.app.state.triggarr_state = await cycle_fn(
    client,
    request.app.state.triggarr_state,
    instance_name,
    instance_config,
    request.app.state.settings,
    request.app.state.db,
)
```
`request.app` is also fully available here, so `request.app.state.tag_cache` is accessible.

**Three candidate mechanisms evaluated:**

**(a) Pass a `get_tags` resolver callable into cycle fn signature**
- Add `get_tags_fn: Callable[[], Awaitable[list[Tag]]] | None = None` (or required) to each cycle fn.
- Caller builds the resolver: `lambda: _resolve_cached_tags(app.state.tag_cache, app_name, instance_name, client)`.
- Pros: cycle fns stay pure; no `app.state` coupling; testable in isolation.
- Cons: signature change on all three cycle fns; all three call sites must be updated; all existing test_search.py tests that call cycle fns directly must either pass a resolver or use `None` (where `None` → unconditional `client.get_tags()`).

**(b) Pass `tag_cache` dict + `app_name`/`instance_name` into cycle fn**
- Add `tag_cache: dict | None = None` parameter. Inside the cycle fn, resolve inline.
- Pros: simpler than (a); still no `app.state` coupling.
- Cons: same signature change and test update burden as (a); the dict is mutable shared state passed by reference (fine, but less explicit than a callable).

**(c) Pass `app.state` through (or pass `app` object)**
- Add `tag_cache: dict | None = None` parameter defaulting to `None`; pass `app.state.tag_cache` from call sites.
- Equivalent to (b) in practice; cleaner than passing raw `app`.

**Recommendation for Claude's Discretion (D-07): Option (a) — resolver callable**

Rationale:
- Aligns perfectly with the existing `make_search_job` philosophy: "read from app.state at call time." The callable IS the "read at call time" pattern, just factored into a lambda at the call site rather than inside the cycle fn.
- Testable: tests can pass `AsyncMock()` as the resolver or `None` (where `None` means "skip caching, call client.get_tags() directly") to preserve existing test coverage without modification.
- Clean: cycle fns remain pure functions with no knowledge of `app.state` internals.
- The `None` default means existing call sites without a resolver continue to work during incremental rollout and existing tests need zero changes (cycle fn falls back to `await client.get_tags()` when resolver is `None`).

**Recommended resolver helper location:** New `_resolve_cached_tags` function in `triggarr/search/scheduler.py` or in a small new `triggarr/search/tag_cache.py`. The scheduler module already imports `time` (monotonic) and defines `_SHUTDOWN_DRAIN_TIMEOUT` module-constant pattern; placing `_TAG_CACHE_TTL_SECONDS` there keeps all cache logic co-located.

**Precise signature addition to each cycle fn:**
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
Keyword-only (`*`) prevents positional confusion. `None` → existing `await client.get_tags()` path. This means ALL existing tests pass unchanged.

**Updated call site in `make_search_job` (scheduler.py):**
```python
import time
# Build resolver at job() execution time (reads app.state at call time)
cache_key = (app_name, instance_name)
async def _get_tags_cached() -> list[Tag]:
    cache = app.state.tag_cache
    entry = cache.get(cache_key)
    if entry is not None:
        tags, fetched_at = entry
        if time.monotonic() - fetched_at < _TAG_CACHE_TTL_SECONDS:
            return tags
    tags = await client.get_tags()  # raises on error — caller handles
    cache[cache_key] = (tags, time.monotonic())
    return tags

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

**Important:** The resolver must NOT catch exceptions — the cycle fn's existing `except (httpx.HTTPError, pydantic.ValidationError)` guard wraps `await get_tags_fn()` and handles errors there (setting `tags=[]`, `tag_fetch_ok=False`). Only successful (non-error) fetches reach the cache store line — this is the D-07 "only cache successful fetches" requirement satisfied automatically.

**Updated call site in `search_now` (routes.py):**
The same `_get_tags_cached` inner async function pattern can be inlined, or a module-level helper `_make_tag_resolver(tag_cache, cache_key, client)` can be shared between the two call sites.

---

### Q2: last_success — State Shape, Success Points, Render, Serialization

**Current AppState TypedDict (state.py:43-61) — exact fields (VERIFIED):**
```python
class AppState(TypedDict, total=False):
    missing_cursor: int
    cutoff_cursor: int
    missing_pass: int
    cutoff_pass: int
    last_run: str | None           # ISO timestamp
    connected: bool | None
    unreachable_since: str | None
    missing_count: int | None
    missing_eligible: int | None
    missing_monitored: int | None
    missing_searchable: int | None
    cutoff_count: int | None
    cutoff_searchable: int | None
    total_items: int | None
    tag_warnings: list[dict]
```

**`_default_instance_state()` (state.py:76-78) — exact current return (VERIFIED):**
```python
def _default_instance_state() -> AppState:
    return AppState(missing_cursor=0, cutoff_cursor=0, last_run=None)
```
Add `last_success=None` here.

**Serialization — `save_state` uses `json.dump(state, f, indent=2)` (VERIFIED):** The entire TriggarrState dict is serialised as-is. Any new key written to an instance AppState dict is automatically persisted. No explicit change to save_state or load_state is required — `_merge_defaults` (state.py:128-150) merges loaded per-instance data over `_default_instance_state()`, so `last_success` from a loaded state file will be preserved; a fresh state will default to `None` from the TypedDict default. The `total=False` TypedDict means no key is required.

**Exact success points in engine.py where `ist["last_run"]` is set (VERIFIED):**
- `run_radarr_cycle`: line 506 — `ist["last_run"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")` — after the full cycle loop, after diagnostic summary. `ist["connected"] = True` is set at line 331 (the guard at the top of the connected branch). `last_success` should be written at line 506, same location as `last_run`.
- `run_sonarr_cycle`: line 748 — same pattern.
- `run_lidarr_cycle`: line 984 — same pattern.

All three reach `last_run` only when the cycle does NOT early-return on connection failure. An early return at lines 313-321/549-557/794-802 (connection error paths) does NOT update `last_run`. The `last_success` write at the same location means: only a cycle that fully completed the connected branch records a success timestamp. This is exactly the D-02 semantics.

**`_build_app_context` (routes.py:242-295) — current context keys (VERIFIED):**
Returns a dict with: `name`, `instance`, `card_id`, `last_run`, `next_run`, `missing_cursor`, `cutoff_cursor`, `missing_pass`, `cutoff_pass`, `connected`, `unreachable_since`, `missing_count`, `missing_eligible`, `missing_monitored`, `missing_searchable`, `cutoff_count`, `cutoff_searchable`, `total_items`, `skip_unreleased`, `tag_warnings`.

**Per-instance `search_interval` availability in `_build_app_context` (VERIFIED):**
`settings = request.app.state.settings` is available. `enabled = settings.get_enabled_instances(app_name)` returns the `dict[str, InstanceConfig]`. The function already calls `enabled[instance_name]` (or resolves it from `next(iter(enabled))`). `InstanceConfig.search_interval: int = 30` is directly accessible as `enabled[instance_name].search_interval`.

**Stale computation to add in `_build_app_context`:**
```python
last_success = app_state.get("last_success")
now_dt = datetime.now(UTC)
last_success_stale = True  # default for "Never" case
if last_success is not None:
    try:
        ls_dt = datetime.fromisoformat(last_success.replace("Z", "+00:00"))
        interval_cfg = enabled[instance_name]  # already resolved above
        threshold = timedelta(minutes=interval_cfg.search_interval * 2)
        last_success_stale = (now_dt - ls_dt) > threshold
    except (ValueError, TypeError):
        last_success_stale = True
```
Note: `datetime` and `UTC` are already imported in routes.py (line 16). `timedelta` needs to be added to that import.

**app_card.html schedule row (lines 50-54) — current markup (VERIFIED):**
```html
<div class="text-[11px] font-mono text-triggarr-muted mb-4 flex justify-between">
  <span>Last run: <span class="text-triggarr-text">{% if app.last_run %}{{ app.last_run[11:19] }}{% else %}Never{% endif %}</span></span>
  <span>Next: <span class="text-triggarr-text">{% if app.next_run %}{{ app.next_run[11:16] }}{% else %}&mdash;{% endif %}</span></span>
</div>
```
The "Last OK" entry should be added within or after this div. The existing `flex justify-between` structure has two spans; adding a third `span` in between or wrapping in a second line is the right approach. Amber stale flag pattern from the existing tag-warning badge (lines 38-47): `bg-amber-500/15 text-amber-400`.

---

### Q3: OriginCheckMiddleware — Existing Coverage vs. Required Gaps

**Middleware dispatch logic (middleware.py:72-86) — exact current code (VERIFIED):**
```python
if request.method in ("POST", "PUT", "PATCH", "DELETE"):
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    host = request.headers.get("host", "")

    if origin:
        if urlparse(origin).netloc != host:
            return Response("Forbidden", status_code=403)
    elif referer and urlparse(referer).netloc != host:
        return Response("Forbidden", status_code=403)
    # Neither header present: allow (same-origin browser behavior)
```

**Existing test functions in test_middleware.py (VERIFIED — lines 34-173):**

| Test function | What it covers |
|---|---|
| `test_post_matching_origin_passes` | POST + matching Origin → 200 |
| `test_post_mismatched_origin_returns_403` | POST + mismatched Origin → 403 |
| `test_post_matching_referer_passes` | POST + matching Referer (no Origin) → 200 |
| `test_post_mismatched_referer_returns_403` | POST + mismatched Referer (no Origin) → 403 |
| `test_post_no_origin_no_referer_passes` | POST + neither header → 200 |
| `test_get_with_mismatched_origin_passes` | GET + mismatched Origin → 200 (non-POST passthrough) |
| `test_settings_post_cross_origin_rejected` | Integration: POST /settings + mismatched Origin → 403 |
| `test_settings_post_same_origin_passes` | Integration: POST /settings + matching Origin → not 403 |
| SecurityHeadersMiddleware tests (4 tests) | Separate class, not relevant |

**Gap analysis against ROADMAP Phase 67 Success Criterion 3:**

| Required scenario | Existing test | Gap? |
|---|---|---|
| Missing Origin header (Referer present) | `test_post_matching_referer_passes` covers "missing Origin + matching Referer → 200"; `test_post_mismatched_referer_returns_403` covers "missing Origin + mismatched Referer → 403". These tests IMPLICITLY cover this but do not have "missing_origin" in their names | Names don't signal intent explicitly — add explicit named tests for clarity |
| Missing Referer header (Origin present) | `test_post_matching_origin_passes` and `test_post_mismatched_origin_returns_403` both have Origin and no Referer — this IS implicitly covered | Add explicit test with descriptive name |
| Both headers absent | `test_post_no_origin_no_referer_passes` — COVERED | Keep existing, no new test needed |
| Scheme mismatch | NOT COVERED — no test exists | Add: `test_post_scheme_mismatch_is_allowed` pinning ALLOW behavior with comment |
| Spoofed host | `test_post_mismatched_origin_returns_403` covers `evil.com` but NOT suffix-spoof (`testserver.evil.com`) or port mismatch | Add: `test_post_suffix_spoof_returns_403`, `test_post_port_mismatch_returns_403` |

**New tests to add (ROADMAP compliance):**

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
    refactor that inadvertently breaks it is caught immediately.
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

The `test_post_no_origin_no_referer_passes` test already covers "both absent" and is correctly named. D-09 says "both absent" is already covered — confirmed.

**Decision on existing implicit coverage:** The CONTEXT.md D-09 says to add tests for "missing Origin (Referer present)" and "missing Referer (Origin present)" as EXPLICIT assertions. Even though the existing tests technically exercise those code paths, new explicitly-named tests provide regression locks and satisfy the ROADMAP criterion 3 wording. Add them; do not rely on implicit coverage alone.

---

### Q4: Settings-Save Handler Shape for D-08 (Tag Cache Invalidation)

**Handler name and location (VERIFIED — routes.py:503-688):**
`save_settings` at `@router.post("/settings")`.

**Lock acquisition point (VERIFIED — routes.py:591):**
```python
async with request.app.state.search_lock:
```
The entire config write, settings update, scheduler update, and state persist happen inside this single lock block.

**Available data for diff (VERIFIED — routes.py:503-688):**
At the point where the lock is acquired:
- `current_settings = request.app.state.settings` — the OLD settings (read before form parsing, line 507).
- `new_settings` — validated new `SettingsModel` (line 582).

Both are full `SettingsModel` objects with `InstanceConfig` per instance. Diffing is straightforward:
```python
# Inside the search_lock block, after the TOML write and settings update:
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

**Existing "what changed" computation in the handler (VERIFIED):** The handler already computes `url_changed` and `key_changed` for client recreation (lines 633-634). However, it does NOT currently diff `missing_tag`/`cutoff_tag`. The D-08 diff logic extends this pattern. The diff can either be inlined in the save handler (after line 596 `request.app.state.settings = new_settings`) or extracted to a small helper `_invalidate_tag_cache_for_changed_instances(app_state, old_settings, new_settings)`.

**Note on `current_settings` lifecycle:** `current_settings` is captured BEFORE the lock is acquired (line 507). Inside the lock, `request.app.state.settings` is updated to `new_settings` (line 596). The diff should use the locally-captured `current_settings` (pre-update) against `new_settings` (post-validation), which are both in scope throughout the handler.

**The `add_instance` handler (routes.py:716-767):** Also acquires `search_lock` and writes config. A new instance has no cache entry yet (by definition), so no tag cache invalidation is needed there.

**The `remove_instance` handler (routes.py:770-825):** Also acquires `search_lock`. Removes instance state. Should also remove the tag cache entry for the removed instance: `request.app.state.tag_cache.pop((app_name, instance_name), None)`.

---

### Q5: Pitfalls

**Pitfall 1: Cycle fn signature change breaks all existing test_search.py tests**
The three cycle fns have 19+ existing tests in test_search.py. Adding a new `get_tags_fn` keyword-only parameter with `None` default ensures backward compatibility — existing tests pass unchanged because `None` triggers the original `await client.get_tags()` code path. The resolver callable is only used when non-None.

**Pitfall 2: Tag cache TTL uses `time.monotonic()` — correct, but requires import coordination**
`time.monotonic()` is already imported in scheduler.py (`import time`, line 32). The `_TAG_CACHE_TTL_SECONDS` constant and the resolver helper must live in a module that also imports `time`. If the helper lives in scheduler.py, this is already satisfied. If it lives in engine.py, `time` is also already imported there (line 12). Do NOT use `datetime.now(UTC)` for the TTL comparison — monotonic is correct and already established by the `search_lock_holder` pattern.

**Pitfall 3: Negative caching bug if failure path is not handled carefully**
The resolver callable must be structured so that cache storage occurs ONLY after a successful `get_tags()` call. If the call is `tags = await client.get_tags()` with no try/except in the resolver, any exception propagates to the cycle fn's existing `except (httpx.HTTPError, pydantic.ValidationError)` guard. The guard sets `tags = []` and `tag_fetch_ok = False` — but the cache store line in the resolver was never reached (exception propagated before it). This is correct behavior automatically, as long as the resolver does not catch exceptions itself.

**Pitfall 4: `last_success_stale` when `last_success` is None**
D-03 says `last_success is None` → `last_success_stale = True`. The template should render "Never" with no amber treatment (amber only when stale AND a value exists — D-04: "when `last_success_stale` is true and a value exists"). A clean branch in the template:
```jinja
{% if app.last_success %}
  <span class="{% if app.last_success_stale %}text-amber-400{% else %}text-triggarr-text{% endif %}">{{ app.last_success[11:19] }}</span>
{% else %}
  <span class="text-triggarr-muted">Never</span>
{% endif %}
```
The stale flag should NOT apply amber to "Never" — only to a real stale timestamp.

**Pitfall 5: `_merge_defaults` in state.py and new `last_success` key**
`_merge_defaults` (state.py:128-150) performs `{**_default_instance_state(), **instance_data}` for each loaded instance. Since `_default_instance_state()` returns `AppState(missing_cursor=0, cutoff_cursor=0, last_run=None)` today, adding `last_success=None` to it ensures:
- Fresh instances get `last_success=None`.
- Loaded instances that already have `last_success` in JSON preserve it (instance_data wins via `**`).
- Loaded instances from before the feature (no `last_success` key) get `None` from the default.
No special migration is needed.

**Pitfall 6: `timedelta` import missing from routes.py**
The stale computation requires `timedelta`. `datetime` is already imported at routes.py:17 (`from datetime import UTC, datetime`). Add `timedelta` to that import.

**Pitfall 7: `search_now` endpoint and `app.state.tag_cache`**
The `search_now` route (routes.py:828-899) calls the cycle fn directly and has access to `request.app.state`. If the cycle fn is called with `get_tags_fn=None` (no resolver), the manual search bypasses the cache entirely — which means it makes an unconditional `get_tags()` call and does NOT update the cache. This is acceptable for Phase 67 scope (the cache is primarily for scheduled cycles). However, for full consistency, the `search_now` endpoint should also pass a resolver so manual searches benefit from the cache. This requires `request.app.state.tag_cache` to be initialized (it will be, in lifespan).

**Pitfall 8: `tag_cache` not initialized in test app.state fixtures**
Tests in test_scheduler.py that create a `FastAPI()` app and set `app.state.*` manually (lines 37-65, 85-91, etc.) will need `app.state.tag_cache = {}` added when testing paths that exercise the tag cache resolver. Tests that do not go through the cache resolver need no change. The Wave 0 gap list for tests should note this.

**Pitfall 9: Scheme-mismatch test must document WHY it asserts ALLOW**
If the test comment is absent or unclear, future engineers may assume it is a bug and "fix" the test to assert 403 — or worse, "fix" the middleware. The test MUST include the extended comment from D-10 explaining the single-origin model rationale.

**Pitfall 10: `_build_app_context` `search_interval` resolution path**
The function currently resolves `instance_name` either from the parameter or `next(iter(enabled))` (line 260). By the time we compute `last_success_stale`, `instance_name` is always resolved. `enabled[instance_name]` is valid because the function returns `None` early if `instance_name not in enabled` (line 262-263). So `enabled[instance_name].search_interval` is always safe at that point.

---

## Standard Stack

### Core (no new packages — all existing project dependencies)

| Component | Location | Phase 67 Use |
|-----------|----------|--------------|
| `time.monotonic()` | stdlib | Tag cache TTL; already imported in scheduler.py and engine.py |
| `datetime` / `timedelta` | stdlib | `last_success` timestamp + stale delta; `timedelta` needs adding to routes.py import |
| `fastapi.testclient.TestClient` | existing dep | TEST-01 harness; already used in test_middleware.py |
| `app.state` (Starlette State) | existing | tag_cache dict storage |
| `TypedDict` | stdlib | `last_success` field addition to AppState |

No new dependencies are required for any of the three fronts.

---

## Package Legitimacy Audit

Not applicable — Phase 67 introduces no new packages.

---

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ APScheduler job() / search_now endpoint                      │
│   ↓ builds get_tags_fn resolver (reads app.state.tag_cache) │
│   ↓ passes resolver to cycle fn                             │
├─────────────────────────────────────────────────────────────┤
│ run_{app}_cycle(client, state, ..., get_tags_fn)            │
│   ↓ if missing_tag or cutoff_tag configured:                │
│     ↓ await get_tags_fn()  ←→  app.state.tag_cache (TTL)   │
│   ↓ on success: ist["last_success"] = ISO-8601-Z            │
│   ↓ return updated state                                    │
├─────────────────────────────────────────────────────────────┤
│ save_state(state) → state.json (persists last_success)      │
├─────────────────────────────────────────────────────────────┤
│ POST /settings (save_settings)                              │
│   ↓ under search_lock: diff old_cfg vs new_cfg             │
│   ↓ pop changed instance entries from app.state.tag_cache  │
├─────────────────────────────────────────────────────────────┤
│ GET / (dashboard) → _build_app_context()                    │
│   ↓ read last_success from state                           │
│   ↓ compute last_success_stale (now - last_success > 2×)   │
│   ↓ pass last_success + last_success_stale to template     │
├─────────────────────────────────────────────────────────────┤
│ app_card.html (htmx auto-refresh every 5s)                  │
│   ↓ render "Last OK: HH:MM:SS" or "Never"                  │
│   ↓ amber if last_success_stale and value present          │
└─────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure (no new files required)

All changes are within existing files. Optional new file if tag cache resolver is extracted:
```
triggarr/
├── search/
│   ├── engine.py         # add last_success write + get_tags_fn parameter
│   ├── scheduler.py      # add tag_cache init + _TAG_CACHE_TTL_SECONDS + resolver helper
│   └── tag_cache.py      # (optional) extracted resolver helper if kept out of scheduler.py
├── state.py              # add last_success field to AppState + _default_instance_state
├── web/
│   └── routes.py         # _build_app_context: stale computation; save_settings: invalidation
└── templates/
    └── partials/
        └── app_card.html  # schedule row: add Last OK entry
tests/
└── test_middleware.py     # add 5 new test functions
```

### Anti-Patterns to Avoid

- **Caching a tag fetch failure result:** If `get_tags()` raises, do NOT store `([], monotonic())` in the cache. This would pin a transient outage as a "valid" 1-hour empty cache entry. Let the exception propagate; only store after a successful return.
- **Using `datetime.now()` for TTL comparison instead of `time.monotonic()`:** Wall-clock jumps (NTP adjustments, DST in non-UTC environments, Docker clock drift) can make a cache entry look permanently fresh or instantly expire. Monotonic is the correct choice and is already established in the codebase.
- **Modifying OriginCheckMiddleware for TEST-01:** The test work is pure — no middleware changes. Changing the middleware to reject scheme mismatches would be out of scope and is explicitly rejected (D-10).
- **Amber treatment on "Never" (null last_success):** The stale amber color should only apply when there IS a timestamp that is stale, not when the value is null/never. "Never" renders in muted color.
- **Placing tag cache resolution logic inside engine.py cycle fns directly:** That would couple engine to app.state or require passing the whole dict in. The resolver callable keeps separation of concerns.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Time-based TTL expiry | Custom clock tracking | `time.monotonic()` — already in codebase |
| Thread-safe cache | asyncio Lock on tag_cache | Not needed — single event loop, single worker; plain dict access is safe |
| Custom test harness for middleware | New test infrastructure | `TestClient` with header crafting — already established in test_middleware.py |
| Timestamp formatting | Custom formatter | `[11:19]` slice — already the project pattern for HH:MM:SS |

---

## Validation Architecture

**Framework:** pytest-asyncio with `asyncio_mode=auto` (from CLAUDE.md and pyproject.toml)

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | File | Automated Command |
|--------|----------|-----------|------|-------------------|
| RES-02 | `last_success` written in AppState on cycle success | unit | tests/test_search.py | `uv run pytest tests/test_search.py -x -q` |
| RES-02 | `last_success` NOT written on cycle failure (connected=False) | unit | tests/test_search.py | same |
| RES-02 | `last_success` persists via `save_state`/`load_state` round-trip | unit | tests/test_state.py | `uv run pytest tests/test_state.py -x -q` |
| RES-02 | `_build_app_context` computes `last_success_stale=True` when None | unit | tests/test_web.py | `uv run pytest tests/test_web.py -x -q` |
| RES-02 | `_build_app_context` computes `last_success_stale=True` when old | unit | tests/test_web.py | same |
| RES-02 | `_build_app_context` computes `last_success_stale=False` when fresh | unit | tests/test_web.py | same |
| RES-03 | Cache hit avoids second `get_tags()` call within TTL | unit | tests/test_scheduler.py or tests/test_search.py | `uv run pytest tests/test_scheduler.py -x -q` |
| RES-03 | Cache miss triggers `get_tags()` and stores result | unit | tests/test_scheduler.py or tests/test_search.py | same |
| RES-03 | TTL expiry triggers fresh fetch | unit | tests/test_scheduler.py | same |
| RES-03 | Tag fetch failure does NOT cache empty result | unit | tests/test_search.py | `uv run pytest tests/test_search.py -x -q` |
| RES-03 | `save_settings` invalidates changed instance's cache entry | unit | tests/test_web.py | `uv run pytest tests/test_web.py -x -q` |
| RES-03 | `save_settings` preserves unchanged instance's cache entry | unit | tests/test_web.py | same |
| TEST-01 | Scheme mismatch (https Origin vs http Host) → ALLOW | unit | tests/test_middleware.py | `uv run pytest tests/test_middleware.py -x -q` |
| TEST-01 | Suffix-spoof Origin → 403 | unit | tests/test_middleware.py | same |
| TEST-01 | Port-mismatch Origin → 403 | unit | tests/test_middleware.py | same |
| TEST-01 | Missing Origin, matching Referer → 200 (explicit named) | unit | tests/test_middleware.py | same |
| TEST-01 | Missing Referer, matching Origin → 200 (explicit named) | unit | tests/test_middleware.py | same |

### TDD Mode Notes

- **TEST-01 tests:** These ARE the test work — write them first, run to confirm they pass immediately (given middleware behavior is already correct for most, or fail for scheme-mismatch until verified).
- **RES-02 tests:** TDD-eligible — write `test_last_success_written_on_success` before modifying engine.py.
- **RES-03 tag cache tests:** TDD-eligible — write `test_cache_hit_skips_get_tags` before adding the resolver parameter to cycle fns.
- **Template rendering (RES-02 card):** Not TDD — Jinja template output is integration-tested or snapshot-tested; functional verification via browser is more natural.

### Sampling Rate
- Per task commit: `uv run pytest tests/test_middleware.py tests/test_search.py tests/test_state.py tests/test_web.py tests/test_scheduler.py -x -q`
- Per wave merge: `uv run pytest tests/ -x -q`
- Phase gate: full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] Existing `tests/test_search.py` tests call cycle fns directly — they pass with `get_tags_fn=None` default, but new tests for the cache resolver path need to pass a mock resolver.
- [ ] `tests/test_scheduler.py` tests that build minimal `app.state` (lines 37-65, 85-91) do not set `app.state.tag_cache` — will need `app.state.tag_cache = {}` when testing the job() path that reads the cache.
- [ ] `tests/test_web.py` tests that call `_build_app_context` or `save_settings` do not currently need `tag_cache` in `app.state`, but will after D-08 is wired.

---

## Common Pitfalls

### Pitfall 1: Cycle fn test breakage from signature change
**What goes wrong:** Adding `get_tags_fn` as a positional parameter breaks existing test calls.
**Why it happens:** All 19+ test_search.py calls pass cycle fns with positional args.
**How to avoid:** Make `get_tags_fn` keyword-only with `None` default (`*, get_tags_fn=None`). No existing call sites need updating.
**Warning signs:** Test collection errors from positional arg count mismatch.

### Pitfall 2: Negative caching
**What goes wrong:** A `get_tags()` exception path stores `([], monotonic())` in the cache, pinning a stale empty tag list for up to 1 hour.
**Why it happens:** If the resolver catches exceptions to return `[]`, it looks like a successful fetch.
**How to avoid:** Resolver must NOT catch exceptions. The existing cycle fn exception handler sets `tags=[]` only after the resolver has re-raised.
**Warning signs:** Tag filtering is silently bypassed after a transient *arr outage.

### Pitfall 3: `timedelta` not imported in routes.py
**What goes wrong:** `NameError: name 'timedelta' is not defined` at runtime.
**Why it happens:** `datetime` is imported but `timedelta` is not (routes.py:17).
**How to avoid:** Change `from datetime import UTC, datetime` to `from datetime import UTC, datetime, timedelta`.

### Pitfall 4: Amber applied to "Never" case
**What goes wrong:** When `last_success` is None, `last_success_stale=True`, and template applies amber to "Never" text — which is visually misleading (amber implies stale data, not "no data").
**Why it happens:** Template checks `last_success_stale` without guarding on `last_success` being non-null.
**How to avoid:** Template condition: amber ONLY when `app.last_success and app.last_success_stale`.

### Pitfall 5: `remove_instance` handler missing tag cache cleanup
**What goes wrong:** After an instance is removed, its `(app_name, instance_name)` key lingers in `tag_cache` indefinitely, leaking memory (small but unnecessary).
**Why it happens:** D-08 focuses on `save_settings`; `remove_instance` is a separate handler.
**How to avoid:** Add `request.app.state.tag_cache.pop((app_name, instance_name), None)` inside the `remove_instance` handler's search_lock block.

---

## Code Examples

### last_success write in engine.py (pattern for all three cycle fns)
```python
# Source: engine.py existing pattern at lines 505-507 (Radarr); 747-749 (Sonarr); 983-985 (Lidarr)
# --- Update last_run and last_success ---
ist["last_run"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
ist["last_success"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
```
Or more efficiently, capture once:
```python
now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
ist["last_run"] = now_iso
ist["last_success"] = now_iso
```

### Tag cache initialization in lifespan (scheduler.py)
```python
# Source: scheduler.py:437-457 existing pattern for search_failures / last_search_time
# tag_cache: dict[tuple[str, str], tuple[list[Tag], float]]
# key: (app_name, instance_name), value: (tags, time.monotonic() at fetch)
app.state.tag_cache = {}
```
Module constant alongside `_SHUTDOWN_DRAIN_TIMEOUT`:
```python
_TAG_CACHE_TTL_SECONDS: float = 3600.0
```

### Resolver callable (scheduler.py or tag_cache.py)
```python
# Source: derived from make_search_job "read from app.state at call time" philosophy
from triggarr.models.arr import Tag

def _make_tag_resolver(
    tag_cache: dict,
    cache_key: tuple[str, str],
    client: ArrClient,
) -> Callable[[], Awaitable[list[Tag]]]:
    """Return an async callable that resolves tags from cache or live API."""
    async def _resolve() -> list[Tag]:
        entry = tag_cache.get(cache_key)
        if entry is not None:
            cached_tags, fetched_at = entry
            if time.monotonic() - fetched_at < _TAG_CACHE_TTL_SECONDS:
                return cached_tags
        # Cache miss or expired — fetch from API (raises on error, caller handles)
        fresh_tags = await client.get_tags()
        tag_cache[cache_key] = (fresh_tags, time.monotonic())
        return fresh_tags
    return _resolve
```

### Stale computation in _build_app_context (routes.py)
```python
# Source: derived from existing last_run read pattern at routes.py:278
from datetime import UTC, datetime, timedelta  # add timedelta

last_success = app_state.get("last_success")
last_success_stale = True  # default when no timestamp
if last_success is not None:
    try:
        ls_dt = datetime.fromisoformat(last_success.replace("Z", "+00:00"))
        instance_cfg = enabled[instance_name]
        threshold = timedelta(minutes=instance_cfg.search_interval * 2)
        last_success_stale = (datetime.now(UTC) - ls_dt) > threshold
    except (ValueError, TypeError):
        last_success_stale = True
# Add to returned dict:
# "last_success": last_success,
# "last_success_stale": last_success_stale,
```

### app_card.html schedule row extension
```jinja
{# Source: app_card.html:50-54 existing schedule row #}
<div class="text-[11px] font-mono text-triggarr-muted mb-4 flex justify-between">
  <span>Last run: <span class="text-triggarr-text">{% if app.last_run %}{{ app.last_run[11:19] }}{% else %}Never{% endif %}</span></span>
  <span>Last OK:
    {% if app.last_success %}
      <span class="{% if app.last_success_stale %}text-amber-400{% else %}text-triggarr-text{% endif %}">{{ app.last_success[11:19] }}</span>
    {% else %}
      <span class="text-triggarr-muted">Never</span>
    {% endif %}
  </span>
  <span>Next: <span class="text-triggarr-text">{% if app.next_run %}{{ app.next_run[11:16] }}{% else %}&mdash;{% endif %}</span></span>
</div>
```
Note: The existing `flex justify-between` row now has three spans. This changes layout from two-column to three-column distribution. If layout is tight, the planner may choose to add a second row beneath the existing one instead of extending the same row.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| No last_success tracking | `last_success` per-instance in AppState | Enables stale-flag observability |
| `get_tags()` on every cycle | Cached `get_tags()` with 1h TTL | Eliminates per-cycle round-trip for tag-filtered instances |
| Test suite has implicit CSRF coverage gaps | Explicit named tests for all ROADMAP scenarios | Regression-locks netloc equality guard |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `add_instance` handler needs no tag cache invalidation (new instance has no entry) | Q4 | Low — no entry exists to invalidate; next cycle will populate cache correctly |
| A2 | `_merge_defaults` two-level merge picks up `last_success` from loaded JSON automatically | Q2 | Low — verified in code; `{**default, **loaded_data}` means loaded `last_success` wins |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

---

## Open Questions

1. **Schedule row layout with three spans**
   - What we know: The existing row is `flex justify-between` with two spans.
   - What's unclear: Whether three spans in one row fits the card's narrow width at typical viewport sizes.
   - Recommendation: Planner notes this as a discretionary layout call for D-04. The alternative is a second row `<div>` below the "Last run / Next" row specifically for "Last OK".

2. **`search_now` tag cache participation**
   - What we know: D-07 says to wrap `get_tags()` call sites in engine.py. `search_now` calls the cycle fn directly.
   - What's unclear: Whether manual searches should also populate/read the cache (for full consistency) or leave that as a future enhancement.
   - Recommendation: Pass the resolver to the `search_now` call site too — it's one additional line and gives manual searches the same cache benefit. The resolver is cheap to construct.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 67 is pure code/test changes within the existing single-process daemon; no new external dependencies, services, or CLI tools required.

---

## Project Constraints (from CLAUDE.md)

| Directive | Phase 67 Impact |
|-----------|----------------|
| Python 3.11+, ruff (E,F,I,UP,B,SIM), 120 line length | All new code must pass `uv run ruff check` |
| SecretStr for all API keys | Tag cache stores `list[Tag]` (not secrets); no SecretStr concern |
| Loguru for logging (never print/logging module) | Any new log lines in resolver helper must use `logger.` |
| Atomic file writes | Not applicable — tag cache is in-memory; state.json writes unchanged |
| pytest-asyncio with asyncio_mode=auto | New async tests must be `async def test_*()` (no decorator needed) |
| No bare `except:` | Resolver callable must use typed exception handlers |

---

## Security Domain

TEST-01 concerns the security layer (CSRF protection). No new attack surface is introduced.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V4 Access Control | Yes — CSRF | Origin/Referer header validation (OriginCheckMiddleware) — test coverage only |
| V5 Input Validation | No | Not applicable to Phase 67 changes |
| V6 Cryptography | No | Not applicable |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Phase 67 Mitigation |
|---------|--------|---------------------|
| CSRF via spoofed Origin | Spoofing | TEST-01 regression-locks suffix-spoof and port-mismatch rejection |
| CSRF via missing headers | Spoofing | D-09 explicit coverage for missing-header allow path (not a bypass) |
| Cache poisoning (tag cache) | Tampering | Only successful fetches cached; error results never stored |

---

## Sources

### Primary (HIGH confidence)
- `triggarr/state.py` — AppState TypedDict, `_default_instance_state`, `save_state`, `_merge_defaults` — read directly
- `triggarr/search/engine.py` — all three cycle fn signatures, exact success points (last_run writes), get_tags call sites, tag fetch failure pattern
- `triggarr/search/scheduler.py` — `make_search_job` call site, lifespan app.state init block, `_SHUTDOWN_DRAIN_TIMEOUT` pattern
- `triggarr/web/routes.py` — `_build_app_context` full body, `save_settings` handler (lock acquisition, diff data available, invalidation point)
- `triggarr/web/middleware.py` — `OriginCheckMiddleware.dispatch` exact logic
- `triggarr/templates/partials/app_card.html` — schedule row exact markup (lines 50-54)
- `tests/test_middleware.py` — all existing test function names and coverage
- `triggarr/models/config.py` — `InstanceConfig.search_interval` field

### Secondary (MEDIUM confidence)
- `.planning/phases/67-observability-csrf-test-coverage/67-CONTEXT.md` — locked decisions and canonical file:line pointers

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all within existing codebase
- Architecture: HIGH — all patterns verified against exact source code
- Pitfalls: HIGH — derived from direct code reading, not inference

**Research date:** 2026-05-31
**Valid until:** Stable — these are internal codebase facts, not external API docs
