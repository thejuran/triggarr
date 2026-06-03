# Phase 74: Count-Only Refresh — Research

**Researched:** 2026-06-03
**Domain:** Python / FastAPI / htmx — behavior-preserving refactor + thin endpoint + UI button
**Confidence:** HIGH (all findings derived directly from live codebase inspection)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Engine seam (D-01..D-04)**
- D-01: Extract per-app helpers `refresh_radarr_counts`, `refresh_sonarr_counts`, `refresh_lidarr_counts` (not a shared core). Each extracts its own cycle's prefix: fetch → cache raw counts → set health → resolve tags → app-specific filter → cache eligible/searchable counts.
- D-02: Reuse existing shared filter primitives inside the helpers (`filter_monitored`, `filter_unreleased_movies`, `filter_sonarr_episodes`, `deduplicate_to_seasons`, `cap_batch_sizes`, `resolve_tag_id`/`filter_by_tag`). Filter sequence must not drift.
- D-03: Slicing stays exclusively in the cycle function. `slice_batch` and cursor writes are NOT moved into the helper. This is the structural cursor guarantee (CNT-02).
- D-04: On fetch failure the helper sets `connected=False` + `unreachable_since` and returns — mirroring the cycle's current abort branch.

**Count-path state semantics (D-05..D-06)**
- D-05: Count path updates `connected`, `unreachable_since`, `missing_count`, `cutoff_count`, eligible/searchable counts. Does NOT stamp `last_run`/`last_success`. Does NOT touch `app.state.search_failures` (SAFETY-03).
- D-06: Count path must NOT route through `_run_one_cycle` (scheduler.py). Calls `refresh_*_counts` directly.

**API endpoint (D-07..D-08)**
- D-07: `POST /api/refresh-counts/{app}/{instance}` is structurally identical to `search_now` (guards, rate-limit, `search_lock`, `_build_app_context` → `app_card.html`) minus search + failure-counter/`last_run` updates. Always 200 + card on success; 429 on rate-limit; 400 on validation.
- D-08: Reuse `SEARCH_RATE_LIMIT_SECONDS` (10s) keyed `{app}_{instance}`. Prefer sibling `last_refresh_time` dict (planner confirms) so refresh and search don't rate-limit each other.

**UI (D-09..D-14)**
- D-09: Connected footer → two side-by-side buttons: `flex gap-2`, each `flex-1`. Search Now stays primary. "Refresh counts" is secondary (lighter style, `ph-arrows-clockwise` icon).
- D-10: Disconnected footer unchanged — single "Retry Connection" button only.
- D-11: Button label exactly "Refresh counts". Icon `ph-arrows-clockwise`.
- D-12: Mirrors Search Now interaction exactly: `hx-post`, `hx-target`, `hx-swap="outerHTML"`, `hx-disabled-elt="this"`, full-card swap. No spinner. No disabling sibling Search Now.
- D-13: No extra success cue — the card swap is the confirmation.
- D-14: No distinct failure signal — fetch failure renders existing disconnected state.

### Claude's Discretion
- Exact secondary-button Tailwind classes for "Refresh counts" (within "lighter than Search Now, uses `ph-arrows-clockwise`, `flex-1`").
- Whether to share `last_search_time` vs. sibling `last_refresh_time` dict (D-08 prefers sibling).
- Test fixture organization (`test_refresh_counts.py` vs. extending existing modules) — follow existing layout conventions.

### Deferred Ideas (OUT OF SCOPE)
- "Counts as of HH:MM" refresh timestamp on the card.
- Refresh-failed toast / out-of-band notification.
- Animated spinning refresh icon.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CNT-01 | Extract shared fetch+raw-count+filter+eligible-count logic from each `run_*_cycle` into a reusable helper; existing scheduled-cycle search behavior unchanged | Focus points 1, 2 — exact seam lines identified, helper signature designed |
| CNT-02 | Count-only refresh updates counts/health and never advances the search cursor (structural — slicing in cycle only) | Focus point 1 — `slice_batch` first call in each cycle is the seam; D-03 structural guarantee |
| CNT-03 | Count-only refresh does NOT stamp `last_run`/`last_success` and does NOT touch SAFETY-03 failure counter | Focus points 3, 4 — helper signature omits db; count path bypasses `_run_one_cycle` |
| CNT-04 | `POST /api/refresh-counts/{app}/{instance}` mirrors `search_now` minus the search | Focus point 3 — endpoint skeleton derived from `search_now` (routes.py:880) |
| CNT-05 | "Refresh counts" button on each app card triggers the refresh and updates the card in place | app_card.html analysis — connected footer button block lines 118–125 |
</phase_requirements>

---

## Summary

Phase 74 is a behavior-preserving refactor of the hot search path plus a thin new endpoint and UI button. The work breaks into three tightly-coupled deliverables:

1. **Engine seam extraction** (CNT-01/02): In each of the three `run_*_cycle` functions in `engine.py`, everything before the first `slice_batch` call is extracted into a per-app helper (`refresh_radarr_counts`, `refresh_sonarr_counts`, `refresh_lidarr_counts`). The helper mutates `ist` in place and also returns the filtered lists that the cycle function needs for slicing. The cycle then calls the helper, receives the filtered lists, and continues into slice+search+cursor+stamp unchanged.

2. **New endpoint** (CNT-04): `POST /api/refresh-counts/{app}/{instance}` is a structural copy of `search_now` (routes.py:880) with the `_run_one_cycle` call replaced by a direct `refresh_*_counts` helper call, and the `last_search_time` stamp replaced with a sibling `last_refresh_time` stamp.

3. **UI button** (CNT-05): The connected footer in `partials/app_card.html` (lines 118-125) splits from a single full-width "Search Now" button into two `flex-1` side-by-side buttons.

The primary constraint: the existing scheduled-cycle search behavior must be unchanged — existing cycle tests (test_search.py::test_run_radarr_cycle_cursor_advancement, test_run_radarr_cycle_network_failure, etc.) must stay green after the refactor.

**Primary recommendation:** Extract helpers as `refresh_*_counts(...) -> tuple[list[dict], list[dict]] | None` returning the filtered (missing, cutoff) lists (None on fetch failure). The cycle calls the helper and receives the lists it needs for slicing; the count path calls the helper and discards the return.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Count fetch + cache (raw counts, health, eligible/searchable) | API/Backend (`engine.py`) | — | Already lives in engine; extraction keeps it there |
| Cursor advance + search dispatch | API/Backend (`engine.py` cycle fn) | — | Stays exclusively in cycle fn by design (D-03) |
| SAFETY-03 failure counter | API/Backend (`scheduler.py _run_one_cycle`) | — | Count path deliberately bypasses this |
| Rate-limiting (count endpoint) | API/Backend (`routes.py`) | — | Same `search_lock` + `SEARCH_RATE_LIMIT_SECONDS` pattern as `search_now` |
| Card partial response | Frontend Server (templates) | `routes.py _build_app_context` | Same `_build_app_context` → `app_card.html` path as `search_now` |
| "Refresh counts" button | Browser / Client (`app_card.html`) | — | htmx `hx-post` + `hx-disabled-elt` in existing partial |

---

## Focus Point 1: Exact Seam Lines in Each Cycle Function

### Radarr (`run_radarr_cycle`, engine.py:275)

**Shared prefix (extract into helper):** lines 306–406
- line 306: `cycle_start = time.monotonic()` — NOTE: `cycle_start` is only used in the diagnostic summary at line 501, which stays in the cycle. The helper does NOT need `cycle_start`; the cycle re-starts its own timer if it wants to measure total elapsed.
- lines 307–309: instance guard (return early if instance_name not in state)
- line 310: `ist = state["radarr"][instance_name]`
- lines 312–323: fetch `missing`/`cutoff` with abort branch (sets `connected=False`, `unreachable_since`, returns state on failure)
- lines 325–329: `get_library_count()` (cosmetic, never aborts)
- lines 332–339: `ist["connected"]=True`, `ist["unreachable_since"]=None`, `ist["missing_count"]`, `ist["cutoff_count"]`, `ist["total_items"]`
- lines 341–353: `cap_batch_sizes()` — computes `missing_limit`/`cutoff_limit` — SEARCH-ONLY sizing but is used in the prefix for FILTERING purposes? **Critical observation:** `cap_batch_sizes` produces `missing_limit`/`cutoff_limit` which are passed into `slice_batch`. However the filter step that happens before `slice_batch` does NOT use `missing_limit`/`cutoff_limit` — filtering is applied to the full lists and the resulting lists are what gets passed to `slice_batch`. Therefore `cap_batch_sizes` belongs in the **search-only block**, NOT the prefix. The helper does not need `missing_limit`/`cutoff_limit`.
- lines 355–390: tag resolution block (`ist["tag_warnings"]`, resolve `missing_tag_id`/`cutoff_tag_id`)
- lines 392–393: `searched_count = 0`, `skipped_count = 0` — these stay in the cycle only
- lines 395–406: missing queue filtering: `filter_monitored(missing)` → `ist["missing_monitored"]` → optional `filter_by_tag` → optional `filter_unreleased_movies` → `ist["missing_eligible"]`

**Search-only block (stays in cycle):** everything from line 407 onward
- line 407: `cursor = ist["missing_cursor"]`
- line 408: `batch, new_cursor = slice_batch(missing, cursor, missing_limit)` ← **FIRST `slice_batch` CALL = seam boundary**
- lines 409–448: search loop + `ist["missing_cursor"] = new_cursor` + wrap-around log
- lines 450–498: cutoff queue filter + `slice_batch` + search loop + cursor write
- lines 500–513: diagnostic summary + `ist["last_run"]` + `ist["last_success"]`

**ist writes in prefix (Radarr):**
- `ist["connected"]` (False on abort, True on success)
- `ist["unreachable_since"]` (ISO string on abort, None on success)
- `ist["tag_warnings"]` (set twice: `[]` on abort at line 318, resolved list at line 358+)
- `ist["missing_count"]`
- `ist["cutoff_count"]`
- `ist["total_items"]`
- `ist["missing_monitored"]`
- `ist["missing_eligible"]`

**ist writes in search-only block (Radarr — NOT in helper):**
- `ist["missing_cursor"]` (line 445)
- `ist["missing_pass"]` (line 447)
- `ist["cutoff_cursor"]` (line 494)
- `ist["cutoff_pass"]` (line 496)
- `ist["last_run"]` (line 512)
- `ist["last_success"]` (line 513)

**What the helper must return for the cycle to continue:** The cycle needs the filtered `missing` list and filtered `cutoff` list to pass to `slice_batch`. These lists are local variables after filtering; the cycle cannot re-read them from `ist` (they aren't stored). Therefore the helper must return them. On fetch failure the helper returns `None` and the cycle returns early.

### Sonarr (`run_sonarr_cycle`, engine.py:517)

**Shared prefix (extract into helper):** lines 549–645
- Same structural pattern as Radarr
- Fetch returns `missing_episodes`, `cutoff_episodes` (not movies)
- Filter chain: `filter_sonarr_episodes()` (not `filter_monitored` alone, not `filter_unreleased_movies`) → optional `filter_by_tag` → `deduplicate_to_seasons()`
- Additional ist writes vs. Radarr: `ist["missing_eligible"]` (line 644) AND `ist["missing_searchable"]` (line 645) — set from `len(missing_seasons)` after dedup

**Seam boundary:** line 647 — `batch, new_cursor = slice_batch(missing_seasons, cursor, missing_limit)` ← FIRST `slice_batch` CALL

**ist writes in prefix (Sonarr):**
- `ist["connected"]`, `ist["unreachable_since"]`, `ist["tag_warnings"]`
- `ist["missing_count"]`, `ist["cutoff_count"]`, `ist["total_items"]`
- `ist["missing_eligible"]` (episode count after filter, before dedup)
- `ist["missing_searchable"]` (season count after dedup — Sonarr-specific)

**ist writes in search-only block (Sonarr — NOT in helper):**
- `ist["missing_cursor"]` (line 688), `ist["missing_pass"]` (line 690)
- `ist["cutoff_searchable"]` (line 700) — NOTE: cutoff_searchable is set AFTER the cutoff dedup but BEFORE the `slice_batch` call. This means it is currently in the search-only block per the current code order. However semantically it is a count field, not a search outcome. **Resolution:** `ist["cutoff_searchable"]` is set at line 700, which is before the second `slice_batch` call at line 702. To keep the helper self-contained, move `cutoff_searchable` into the helper (it is the same type of field as `missing_searchable`). The helper must compute and cache both.
- `ist["cutoff_cursor"]` (line 743), `ist["cutoff_pass"]` (line 745)
- `ist["last_run"]` (line 761), `ist["last_success"]` (line 762)

**What the helper returns:** `(missing_seasons, cutoff_seasons)` — the deduped season lists the cycle slices. On fetch failure: `None`.

### Lidarr (`run_lidarr_cycle`, engine.py:766)

**Shared prefix (extract into helper):** lines 801–896
- Albums are atomic (no dedup step unlike Sonarr). No `filter_sonarr_episodes`, no `deduplicate_to_seasons`.
- Filter chain: `filter_monitored()` → optional `filter_by_tag()` → `ist["missing_eligible"]`
- No `missing_searchable` (Lidarr albums are already atomic; no season dedup layer)
- No `cutoff_searchable` is set at all in Lidarr (confirmed by grep: only `missing_monitored` and `missing_eligible`)

**Seam boundary:** line 898 — `batch, new_cursor = slice_batch(missing, cursor, missing_limit)` ← FIRST `slice_batch` CALL

**ist writes in prefix (Lidarr):**
- `ist["connected"]`, `ist["unreachable_since"]`, `ist["tag_warnings"]`
- `ist["missing_count"]`, `ist["cutoff_count"]`, `ist["total_items"]`
- `ist["missing_monitored"]`, `ist["missing_eligible"]`
- (No `missing_searchable`, no `cutoff_searchable`)

**ist writes in search-only block (Lidarr — NOT in helper):**
- `ist["missing_cursor"]` (line 936), `ist["missing_pass"]` (line 938)
- `ist["cutoff_cursor"]` (line 986), `ist["cutoff_pass"]` (line 988)
- `ist["last_run"]` (line 1003), `ist["last_success"]` (line 1004)

**What the helper returns:** `(missing, cutoff)` — the filtered album lists. On fetch failure: `None`.

---

## Focus Point 2: Helper Return Contract

### The crux

The cycle function, after calling the helper, immediately needs the filtered lists (post-filter, pre-slice) to pass to `slice_batch`. These lists are local variables computed inside the helper. The cycle cannot re-read them from `ist` — they are not stored there. Therefore:

**The helper must return the filtered lists, not just mutate `ist`.**

On fetch failure the helper should return `None` (the abort case). The cycle checks the return and early-returns if `None`.

### Recommended helper signatures

**Radarr:**
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
    """Extract and cache Radarr raw + eligible counts; return filtered lists for slicing.

    Mutates state[radarr][instance_name] in place:
      connected, unreachable_since, tag_warnings,
      missing_count, cutoff_count, total_items,
      missing_monitored, missing_eligible.

    Returns:
        (missing_filtered, cutoff_filtered) for the caller to slice, or
        None if the fetch failed (connected already set to False in ist).
    """
```

**Sonarr:**
```python
async def refresh_sonarr_counts(
    client: SonarrClient,
    state: TriggarrState,
    instance_name: str,
    instance_config: InstanceConfig,
    settings: Settings,
    *,
    get_tags_fn: Callable[[], Awaitable[list[Tag]]] | None = None,
) -> tuple[list[dict], list[dict]] | None:
    """Extract and cache Sonarr raw + eligible + searchable counts; return season lists.

    Mutates state[sonarr][instance_name] in place:
      connected, unreachable_since, tag_warnings,
      missing_count, cutoff_count, total_items,
      missing_eligible, missing_searchable, cutoff_searchable.

    Returns:
        (missing_seasons, cutoff_seasons) for the caller to slice, or
        None if the fetch failed.
    """
```

**Lidarr:**
```python
async def refresh_lidarr_counts(
    client: LidarrClient,
    state: TriggarrState,
    instance_name: str,
    instance_config: InstanceConfig,
    settings: Settings,
    *,
    get_tags_fn: Callable[[], Awaitable[list[Tag]]] | None = None,
) -> tuple[list[dict], list[dict]] | None:
    """Extract and cache Lidarr raw + eligible counts; return filtered album lists.

    Mutates state[lidarr][instance_name] in place:
      connected, unreachable_since, tag_warnings,
      missing_count, cutoff_count, total_items,
      missing_monitored, missing_eligible.

    Returns:
        (missing_filtered, cutoff_filtered) for the caller to slice, or
        None if the fetch failed.
    """
```

### cap_batch_sizes placement

`cap_batch_sizes` (engine.py:92) computes the `missing_limit`/`cutoff_limit` sizing for `slice_batch`. It does NOT affect the filtered list contents (filtering happens on full lists). The sizes it produces are only consumed by `slice_batch` in the search-only block. Therefore `cap_batch_sizes` stays in the **cycle function** (search-only block), not in the helper.

The helper receives `instance_config` and `settings` purely for `skip_unreleased` and tag config reads. It does NOT call `cap_batch_sizes`.

### Refactored cycle pattern

```python
async def run_radarr_cycle(...) -> TriggarrState:
    cycle_start = time.monotonic()
    if instance_name not in state.get("radarr", {}):
        logger.warning(...)
        return state

    result = await refresh_radarr_counts(
        client, state, instance_name, instance_config, settings,
        get_tags_fn=get_tags_fn,
    )
    if result is None:
        return state  # fetch failed; ist already updated by helper

    missing, cutoff = result

    # cap batch sizes (search-only sizing — stays here)
    missing_limit = instance_config.search_missing_count
    cutoff_limit = instance_config.search_cutoff_count
    hard_max = settings.general.hard_max_per_cycle
    missing_limit, cutoff_limit = cap_batch_sizes(missing_limit, cutoff_limit, hard_max)

    ist = state["radarr"][instance_name]
    searched_count = 0
    skipped_count = 0

    # --- Missing queue ---
    cursor = ist["missing_cursor"]
    batch, new_cursor = slice_batch(missing, cursor, missing_limit)
    # ... search loop ...
    ist["missing_cursor"] = new_cursor

    # --- Cutoff queue ---
    # ... same pattern ...

    # --- Diagnostic summary ---
    elapsed = time.monotonic() - cycle_start
    logger.info(...)
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    ist["last_run"] = now_iso
    ist["last_success"] = now_iso
    return state
```

**Important:** The refactored cycle is behavior-identical to today's cycle. The only structural change is moving lines 307–406 (Radarr) into a separate function. The `ist` variable can be re-acquired after the helper call via `state["radarr"][instance_name]` since the helper mutates it in place.

---

## Focus Point 3: Count Endpoint Call Path

### Minimal call path (no `_run_one_cycle`)

```python
@router.post("/api/refresh-counts/{app_name}/{instance_name}", response_class=HTMLResponse)
async def refresh_counts(request: Request, app_name: str, instance_name: str) -> HTMLResponse:
    # --- Validation guards (mirror search_now exactly) ---
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

    # --- Optimistic rate limit check (fast-fail, mirrors search_now:895-901) ---
    rate_key = f"{app_name}_{instance_name}"
    now = time.monotonic()
    last = request.app.state.last_refresh_time.get(rate_key, 0.0)  # sibling dict
    if now - last < SEARCH_RATE_LIMIT_SECONDS:
        logger.info("{name}/{inst}: Count refresh rate-limited", ...)
        return HTMLResponse("Rate limited -- try again shortly", status_code=429)

    async with request.app.state.search_lock:
        # --- Re-check inside lock (DRSEC-03 parity) ---
        now = time.monotonic()
        last = request.app.state.last_refresh_time.get(rate_key, 0.0)
        if now - last < SEARCH_RATE_LIMIT_SECONDS:
            return HTMLResponse("Rate limited -- try again shortly", status_code=429)
        request.app.state.last_refresh_time[rate_key] = now

        # --- Tag cache resolver (RES-03 parity, same shape as search_now:920-931) ---
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

        # --- Direct helper call (no _run_one_cycle, no failure counter, no save_state) ---
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
            logger.info("{name}/{inst}: Count refresh triggered", ...)
        except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) as exc:
            # Same sanitization split as search_now:948-964
            logger.error("{name}/{inst}: Count refresh failed -- {exc}", ...)

    # --- Always 200 + card (same as search_now:967-972) ---
    app_data = _build_app_context(request, app_name, instance_name)
    return templates.TemplateResponse(
        request=request,
        name="partials/app_card.html",
        context={"app": app_data},
    )
```

**Key differences from `search_now`:**
1. Rate-limit dict: `last_refresh_time` (sibling, initialized in lifespan alongside `last_search_time`)
2. Call: `refresh_fn(...)` instead of `_run_one_cycle(...)`
3. No `save_state` — the count helper does not mutate cursor/last_run, so the state diff is small enough to skip the persistence overhead. The state is already in-memory and the 5-second polling will pick it up.
4. No SAFETY-03: no `app.state.search_failures` touch anywhere in the count path

**Note on `aiosqlite.Error` in the except tuple:** The helper itself does not call aiosqlite (no `db` parameter). However, the except tuple should still mirror search_now for forward-compatibility and consistency. The helper's tag resolution can raise `httpx.HTTPError` or `pydantic.ValidationError`. OSError could arise from any future I/O. Keeping the full tuple is safer than a narrower one.

**Note on `save_state`:** Unlike `_run_one_cycle`, the count path does NOT call `save_state`. The count-path ist mutations (health + counts) are in-memory updates; they will be persisted the next time the scheduled cycle runs. This is acceptable because the count refresh is purely observational — its data is also ephemeral (the next cycle overwrites it anyway).

---

## Focus Point 4: Rate-Limit Dict Decision

**Recommendation: use a sibling `last_refresh_time` dict (D-08 preference confirmed).**

Rationale:
- `last_search_time` (routes.py, initialized at scheduler.py:500) is the rate-limit for `search_now`. If we share it, a user clicking "Refresh counts" immediately after "Search Now" gets rate-limited for 10 seconds — which is confusing because no search ran.
- With a sibling `last_refresh_time`, the two operations rate-limit independently. A refresh 2s after a search is not blocked; a second refresh within 10s is blocked.
- No invariant is broken: both dicts use the same rate constant (`SEARCH_RATE_LIMIT_SECONDS = 10`), the same key format, and the same double-check inside `search_lock` (DRSEC-03).

**Initialization:** Add `app.state.last_refresh_time = {}` in the lifespan at `scheduler.py:500` alongside `app.state.last_search_time = {}`. Also add it to `test_app` fixture in `tests/test_web.py` (line 122).

---

## Focus Point 5: Behavior-Preservation Test Strategy

### Tests that pin the existing cycle behavior (must stay green)

**test_search.py** — these are the behavior-preservation anchors:

| Test | What it pins | Risk if refactor breaks it |
|------|-------------|---------------------------|
| `test_run_radarr_cycle_cursor_advancement` (line 337) | cursor advances 0→2→4→0 over 3 cycle calls | cursor write moved into helper |
| `test_run_radarr_cycle_network_failure` (line 274) | `missing_cursor=5` unchanged on abort | abort branch changed |
| `test_run_radarr_cycle_happy_path` (line 241) | `search_movies` called 2x, `last_run` set, `connected=True` | prefix extraction disrupts search or last_run |
| `test_run_radarr_cycle_writes_last_success_on_success` (line 2661) | `last_success` stamped | `last_success` accidentally moved into helper |
| `test_run_radarr_cycle_does_not_write_last_success_on_failure` (line 2684) | `last_success` NOT stamped on fetch failure | abort branch changed |
| `test_run_sonarr_cycle_cursor_advancement` (line 494) | Sonarr cursor advances | same |
| `test_run_sonarr_cycle_network_failure` (line 432) | abort behavior | same |
| `test_run_lidarr_cycle_cursor_advancement` (line 2099) | Lidarr cursor advances | same |
| `test_run_lidarr_cycle_network_failure` (line 2048) | abort behavior | same |
| `test_run_radarr_cycle_eligible_count_*` (lines 924, 959) | `missing_eligible` correctly set | count field moved out of prefix |
| `test_run_sonarr_cycle_eligible_count` (line 991) | Sonarr `missing_eligible` + `missing_searchable` | same |
| `test_run_radarr_cycle_uses_get_tags_fn_when_provided` (line 2708) | `get_tags_fn` parameter honored | parameter not threaded into helper |
| `test_run_radarr_cycle_get_tags_fn_exception_suppresses_filtering` (line 2777) | tag fetch failure handled inside cycle | exception handling moved |
| `test_tag_warnings_cleared_on_radarr_connectivity_failure` (line 1956) | `tag_warnings=[]` on abort | abort branch wrong |

### New tests needed (file: `tests/test_refresh_counts.py`)

Follows the existing pattern: new feature module → new test file (mirrors `test_search.py` for engine helpers, `test_web.py` for routes).

**Engine helper tests (pure unit, no TestClient):**

```python
# CNT-01: helper returns correct raw + eligible counts
async def test_refresh_radarr_counts_returns_counts(tmp_path): ...
async def test_refresh_sonarr_counts_returns_counts(tmp_path): ...
async def test_refresh_lidarr_counts_returns_counts(tmp_path): ...

# CNT-02: cursor never advanced by helper
async def test_refresh_radarr_counts_does_not_advance_cursor(tmp_path):
    # Set cursor=5, call helper, assert cursor still 5
async def test_refresh_sonarr_counts_does_not_advance_cursor(tmp_path): ...
async def test_refresh_lidarr_counts_does_not_advance_cursor(tmp_path): ...

# CNT-03: no last_run / no last_success stamp
async def test_refresh_radarr_counts_does_not_stamp_last_run(tmp_path): ...
async def test_refresh_sonarr_counts_does_not_stamp_last_run(tmp_path): ...

# CNT-03: health updated on success
async def test_refresh_radarr_counts_sets_connected_true(tmp_path): ...

# CNT-03: health updated on failure
async def test_refresh_radarr_counts_sets_connected_false_on_fetch_error(tmp_path):
    # client.get_wanted_missing raises httpx.ConnectError
    # assert ist["connected"] is False, ist["unreachable_since"] is not None
    # assert helper returns None

# CNT-03: no search_failures touch (test via checking that search_failures dict unchanged)
# (This is a property of the code path, not the helper itself — test at route level)
```

**Route tests (TestClient, same pattern as test_web.py `test_search_now_*`):**

```python
# CNT-04: basic happy path
def test_refresh_counts_happy_path(client, test_app): ...

# CNT-04: invalid app returns 400
def test_refresh_counts_invalid_app(client): ...

# CNT-04: rate-limited returns 429
def test_refresh_counts_rate_limited(client, test_app): ...

# CNT-04: DRSEC-03 concurrent protection
def test_refresh_counts_rate_limit_concurrent_protection(client, test_app): ...

# CNT-04: search_failures dict untouched (assert test_app.state.search_failures == {})
def test_refresh_counts_does_not_touch_failure_counter(client, test_app): ...

# CNT-04: last_search_time dict untouched (independent rate-limit dicts)
def test_refresh_counts_does_not_touch_last_search_time(client, test_app): ...

# CNT-05: card HTML contains "Refresh counts" button
def test_app_card_connected_has_refresh_counts_button(client): ...

# CNT-05: disconnected card does NOT contain "Refresh counts"
def test_app_card_disconnected_no_refresh_counts_button(client): ...
```

**Fixture reuse:** The `test_app` fixture in `tests/test_web.py` (line 28) must gain `app.state.last_refresh_time = {}` (line ~122). Tests in `test_refresh_counts.py` can import and extend it, or the fixture can be promoted to `conftest.py` if needed. Following existing conventions, extend `test_web.py`'s `test_app` fixture by adding the new state field.

**Monotonic clock / cursor fixture:** No special fixtures needed. The existing pattern (`state["radarr"]["Default"]["missing_cursor"] = 5` before call, assert `== 5` after) is sufficient for CNT-02. The existing `_make_test_state()` helper (test_search.py:230) is reusable.

---

## Focus Point 6: Pitfalls

### Pitfall 1: Tag resolver exception swallowing in the helper

**What:** The cycle's tag resolution block (engine.py:360-390) catches `(httpx.HTTPError, pydantic.ValidationError)` and sets `tags=[]`, `tag_fetch_ok=False`. This means a failed `get_tags_fn()` is NOT propagated — it is swallowed inside the tag block. The helper inherits this exact behavior (it is the same code). This is correct for the count path: a tag fetch failure does not abort the count refresh; it just skips tag filtering.

**Risk:** If someone wraps the helper call in a too-broad except and assumes tag failures propagate, they will be confused. Document in the helper docstring.

**Verify:** The existing test `test_run_radarr_cycle_get_tags_fn_exception_suppresses_filtering` (line 2777) verifies this. After the refactor this same test must continue to pass — it tests the full `run_radarr_cycle` which calls the helper.

### Pitfall 2: `cutoff_searchable` is inside the Sonarr search-only block but semantically belongs in the prefix

**What:** In `run_sonarr_cycle`, `ist["cutoff_searchable"] = len(cutoff_seasons)` (line 700) is set between the cutoff `filter_sonarr_episodes` call and the second `slice_batch` call. It looks like it's in the prefix but technically it's after the first `slice_batch` call (missing queue). The seam boundary I defined is "before the first `slice_batch` call." `cutoff_searchable` is set at line 700, after the first `slice_batch` at line 647.

**Resolution:** Move `cutoff_searchable` into the helper. The helper computes `deduplicate_to_seasons(cutoff_episodes)` and stores `ist["cutoff_searchable"] = len(cutoff_seasons)`. It returns `(missing_seasons, cutoff_seasons)`. This does not change the visible behavior of the cycle (the count is still set before `slice_batch(cutoff_seasons,...)` is called in the cycle). The cycle just receives `cutoff_seasons` from the helper rather than recomputing them.

**Action:** The planner must explicitly note that the Sonarr helper computes BOTH `missing_seasons` and `cutoff_seasons` (and sets `missing_searchable` AND `cutoff_searchable`) before returning.

### Pitfall 3: `cap_batch_sizes` must stay in the cycle, not the helper

**What:** The CONTEXT.md (D-02) says "Reuse shared filter primitives including `cap_batch_sizes`." However, `cap_batch_sizes` produces batch-size limits for slicing, not count data. It does not affect the content of the filtered lists — it only limits how many items get searched.

**Risk:** If `cap_batch_sizes` is moved into the helper, the helper would compute `missing_limit`/`cutoff_limit` but not use them (since slicing stays in the cycle). The cycle would then need to recompute them, leading to duplication or a different signature.

**Resolution:** `cap_batch_sizes` stays in the cycle function (after the helper returns). The helper does NOT call `cap_batch_sizes`. D-02's intent is that the filter primitives like `filter_monitored`, `filter_unreleased_movies`, etc. are reused — `cap_batch_sizes` is a sizing primitive for slicing, not a filter.

### Pitfall 4: `ist` re-acquisition after helper call

**What:** Inside `run_radarr_cycle`, after calling `refresh_radarr_counts(...)`, the cycle needs to access `ist`. Two patterns work:
- Option A: `ist = state["radarr"][instance_name]` — re-acquire after the helper call (the helper mutated `state` in place)
- Option B: the cycle already extracted `ist` before the helper call, and the helper receives and mutates the same dict

Since the helper takes `state` (the full `TriggarrState`) and extracts `ist` internally, the cycle must re-acquire `ist` after the call if it didn't already hold a reference. OR: the cycle can extract `ist = state["radarr"][instance_name]` before calling the helper, and the helper will mutate the same dict object. Both work because Python dicts are mutated in place; the helper calling `ist["connected"] = True` is visible from the caller's reference. Either approach is fine; choose whichever is cleaner in the refactored cycle.

### Pitfall 5: `cycle_start` and the diagnostic summary

**What:** `cycle_start = time.monotonic()` is set at line 306 (before the fetch). The diagnostic summary at line 501 uses it. After extraction, `cycle_start` is still needed by the cycle (for total elapsed including the helper's work). Do NOT move `cycle_start` into the helper. The cycle sets it before calling the helper.

### Pitfall 6: The count endpoint catches `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` but the helper has no `db` parameter

**What:** The helper does not call aiosqlite (no search history writes). The `aiosqlite.Error` in the except tuple is for future-safety and consistency with `search_now`. It does not cause a logic error. Leave it in the tuple.

### Pitfall 7: `last_refresh_time` not initialized in `test_app` fixture

**What:** The `test_app` fixture (test_web.py:28) initializes `app.state.last_search_time = {}` (line 122). It does NOT currently initialize `app.state.last_refresh_time`. Any test that hits the `refresh_counts` endpoint will raise `AttributeError` if the fixture is not updated.

**Resolution:** Add `app.state.last_refresh_time = {}` to the `test_app` fixture alongside `app.state.last_search_time`.

---

## Architecture Patterns

### System Architecture Diagram

```
User clicks "Refresh counts"
  → htmx POST /api/refresh-counts/{app}/{instance}
    → routes.py:refresh_counts()
      → guard checks (len, APP_TYPES, enabled, client) → 400 if invalid
      → optimistic rate-limit check (last_refresh_time) → 429 if limited
      → async with search_lock:
          → re-check rate limit (DRSEC-03)
          → update last_refresh_time[rate_key]
          → _get_tags_cached closure (reads/writes app.state.tag_cache)
          → refresh_*_counts(client, state, ..., get_tags_fn=_get_tags_cached)
              → engine.py:refresh_radarr_counts()
                → client.get_wanted_missing() / get_wanted_cutoff()
                  [fetch failure] → ist[connected=False, unreachable_since=...] → return None
                → client.get_library_count() (best-effort)
                → ist[connected=True, unreachable_since=None]
                → ist[missing_count, cutoff_count, total_items]
                → tag resolution (uses get_tags_fn → tag_cache)
                → ist[tag_warnings]
                → filter_monitored / filter_unreleased_movies / filter_by_tag
                → ist[missing_monitored, missing_eligible]
                → return (missing_filtered, cutoff_filtered)
          → (count path: return value discarded, ist already mutated)
          → except (httpx, pydantic, aiosqlite, OSError) → log, swallow
      → _build_app_context(request, app_name, instance_name)
      → TemplateResponse("partials/app_card.html", {app: app_data})
  ← 200 + card HTML (hx-swap="outerHTML" replaces card in DOM)

Scheduled cycle (unchanged behavior):
  → scheduler.py:make_search_job() → _run_one_cycle()
    → run_radarr_cycle(client, state, ..., get_tags_fn=...)
      → refresh_radarr_counts(...)   ← calls the new helper
        [same prefix as above]
        → return (missing_filtered, cutoff_filtered)
      → cap_batch_sizes(...)
      → slice_batch(missing, cursor, missing_limit) ← cursor advances here
      → search loop + ist[missing_cursor, cutoff_cursor]
      → ist[last_run, last_success]
    → _evaluate_cycle_outcome → search_failures counter
    → save_state()
```

### Recommended Project Structure Changes

```
triggarr/search/
├── engine.py          # Add refresh_radarr_counts, refresh_sonarr_counts, refresh_lidarr_counts
│                      # Refactor run_*_cycle to call helpers
├── scheduler.py       # Add app.state.last_refresh_time = {} in lifespan init
triggarr/web/
├── routes.py          # Add refresh_counts route; import refresh_*_counts from engine
triggarr/templates/partials/
├── app_card.html      # Split connected footer into two flex-1 buttons
tests/
├── test_refresh_counts.py  # New file: engine helper tests + route tests
├── test_web.py            # Add last_refresh_time to test_app fixture
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tag cache invalidation | Custom TTL logic | Existing `_get_tags_cached` closure pattern (routes.py:922, scheduler.py:152) | Already battle-tested with DRSEC-03 double-check |
| Rate limiting | Custom counter | `SEARCH_RATE_LIMIT_SECONDS` + `last_refresh_time` dict (mirror `last_search_time` pattern) | Optimistic + in-lock double-check already handles concurrent bypass |
| Error sanitization | Custom message scrubbing | `_sanitize_exc()` (engine.py:30) — already imported in routes.py | Handles httpx credential leak via `?apikey=` in URL |
| Card HTML generation | Custom template | `_build_app_context` + `partials/app_card.html` | Already handles all state fields, connected/disconnected states |
| App/instance validation | Custom lookup | Existing `APP_TYPES` check + `get_enabled_instances()` + clients dict check (search_now pattern) | Handles disabled instances and missing clients |

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single monolithic cycle function | Shared cycle + per-app helpers (this phase) | Phase 74 | Count path gets structural cursor-non-advance guarantee |
| SAFETY-03 in each search path separately | Centralized in `_run_one_cycle` (scheduler.py:290) | Phase 65 | Count path bypasses it cleanly since it bypasses `_run_one_cycle` |
| No tag cache | `app.state.tag_cache` with TTL (RES-03) | Phase 65 | Count path reuses exact same cache resolver |

---

## Validation Architecture

> `workflow.nyquist_validation` is not explicitly `false` in `.planning/config.json` (key absent — treated as enabled).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3+ with pytest-asyncio |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Async mode | `asyncio_mode = "auto"` |
| Quick run command | `uv run pytest tests/test_refresh_counts.py tests/test_search.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| CNT-01 | Helper returns correct raw+eligible counts | unit | `uv run pytest tests/test_refresh_counts.py -k "returns_counts" -x` | Wave 0 |
| CNT-01 | Existing cycle tests stay green | unit | `uv run pytest tests/test_search.py -x -q` | Exists |
| CNT-02 | Cursor unchanged after helper call | unit | `uv run pytest tests/test_refresh_counts.py -k "cursor" -x` | Wave 0 |
| CNT-03 | No `last_run`/`last_success` stamp | unit | `uv run pytest tests/test_refresh_counts.py -k "last_run" -x` | Wave 0 |
| CNT-03 | `search_failures` untouched | integration | `uv run pytest tests/test_refresh_counts.py -k "failure_counter" -x` | Wave 0 |
| CNT-03 | Health updated on success | unit | `uv run pytest tests/test_refresh_counts.py -k "connected" -x` | Wave 0 |
| CNT-03 | Health updated on fetch failure | unit | `uv run pytest tests/test_refresh_counts.py -k "fetch_error" -x` | Wave 0 |
| CNT-04 | Endpoint happy path 200 + card | integration | `uv run pytest tests/test_refresh_counts.py -k "happy_path" -x` | Wave 0 |
| CNT-04 | 400 on invalid app/instance | integration | `uv run pytest tests/test_refresh_counts.py -k "invalid" -x` | Wave 0 |
| CNT-04 | 429 on rate limit | integration | `uv run pytest tests/test_refresh_counts.py -k "rate_limited" -x` | Wave 0 |
| CNT-04 | DRSEC-03 concurrent protection | integration | `uv run pytest tests/test_refresh_counts.py -k "concurrent" -x` | Wave 0 |
| CNT-05 | Connected card has "Refresh counts" button | integration | `uv run pytest tests/test_refresh_counts.py -k "button" -x` | Wave 0 |
| CNT-05 | Disconnected card has NO "Refresh counts" button | integration | `uv run pytest tests/test_refresh_counts.py -k "disconnected" -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_refresh_counts.py tests/test_search.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green (baseline 984 tests) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_refresh_counts.py` — covers all CNT-01..05 requirements above
- [ ] `tests/test_web.py` — add `app.state.last_refresh_time = {}` to `test_app` fixture (line ~122)

---

## Security Domain

> `security_enforcement` not set to `false` — section required.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Endpoint is behind existing auth middleware (no change) |
| V3 Session Management | no | No session changes |
| V4 Access Control | yes | Same enabled-instance + client validation as `search_now` (APP_TYPES check, instance_name length guard, enabled dict lookup) |
| V5 Input Validation | yes | `len(instance_name) > 64` guard, `app_name not in APP_TYPES` check — mirror `search_now` exactly |
| V6 Cryptography | no | No crypto operations |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Instance name injection via path param | Tampering | `len(instance_name) > 64` guard + `APP_TYPES` check (already in `search_now`) |
| Rate-limit bypass via concurrent requests | Tampering | DRSEC-03 double-check inside `search_lock` (same as `search_now`) |
| Tag cache poisoning | Tampering | No negative caching (D-07) — same resolver as `search_now`; failed fetches do not update cache |
| API key leak via exception message | Information Disclosure | `_sanitize_exc()` applied to httpx/pydantic exceptions before logging; `aiosqlite.Error`/`OSError` use `str(exc)` (no credentials) |

**SecretStr discipline:** The `refresh_counts` endpoint never touches `api_key` directly. The `client` object is already constructed with `.get_secret_value()` consumed at init time. The helper inherits this — it calls `client.get_wanted_missing()` etc., which are pre-authenticated. No new SecretStr exposure point is created.

---

## Open Questions

1. **`tdd_mode: true` in config.json** — the planner should order Wave 0 tasks as: (1) write `tests/test_refresh_counts.py` stubs, (2) extract helpers in `engine.py`, (3) add endpoint in `routes.py`, (4) update `app_card.html`. This way failing tests drive each implementation task.

2. **`partial_app_card` route reuse** — the existing `GET /partials/app-card/{app_name}/{instance_name}` route (routes.py:975) is the periodic polling endpoint. The new `POST /api/refresh-counts/...` mirrors `search_now` in returning the same card partial. This is correct — no new partial is needed.

3. **Lidarr `cutoff_searchable`** — Lidarr does NOT set `ist["cutoff_searchable"]` anywhere in the current code (confirmed by grep). The template (app_card.html:98) checks `cutoff_searchable if cutoff_searchable is not none else cutoff_count`. So Lidarr just shows `cutoff_count` in the UI. The Lidarr helper does not need to set `cutoff_searchable`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `save_state` is intentionally omitted from the count path (counts are ephemeral, next cycle overwrites) | Focus Point 3 | If counts need to survive a restart, add `save_state` call — but the spec says nothing about count persistence |
| A2 | `tdd_mode: true` means Wave 0 should create test stubs before implementation | Validation Architecture | If planner interprets differently, test order changes |

---

## Sources

### Primary (HIGH confidence — derived from live codebase inspection)

- `triggarr/search/engine.py` — full read, line-by-line analysis of all three cycle functions
- `triggarr/web/routes.py` — full read of `search_now` (line 880), `_build_app_context` (line 248), state init (via scheduler.py lifespan)
- `triggarr/search/scheduler.py` — full read, `_run_one_cycle` (line 290), `_record_cycle_failure` (line 231), lifespan state init (line 500)
- `triggarr/templates/partials/app_card.html` — full read, footer button block (lines 109-127)
- `tests/test_search.py` — full index of behavior-pinning tests
- `tests/test_web.py` — full read of `test_app` fixture and `search_now` tests
- `.planning/phases/74-count-only-refresh/74-CONTEXT.md` — locked decisions D-01..D-14
- `docs/superpowers/specs/2026-06-02-recovery-counts-config-design.md` §3 — spec source of truth

### Secondary (MEDIUM confidence)

- `.planning/codebase/CONVENTIONS.md`, `.planning/codebase/TESTING.md` — code and test pattern conventions
- `.planning/REQUIREMENTS.md` — CNT-01..05 acceptance criteria

---

## Metadata

**Confidence breakdown:**
- Seam analysis: HIGH — read every line of the three cycle functions
- Helper signatures: HIGH — derived from actual code, not speculation
- Endpoint skeleton: HIGH — derived from `search_now` verbatim
- Test strategy: HIGH — derived from existing test file inspection
- Pitfalls: HIGH — all derived from actual code observations

**Research date:** 2026-06-03
**Valid until:** Stable (this is a codebase read; only changes if engine.py/routes.py change)

---

## RESEARCH COMPLETE

**Phase:** 74 — Count-Only Refresh
**Confidence:** HIGH

### Key Findings

- **Radarr seam:** last prefix line is `ist["missing_eligible"] = len(missing)` (engine.py:406); first search-only line is `cursor = ist["missing_cursor"]` (407) / `slice_batch(missing, cursor, missing_limit)` (408). `cap_batch_sizes` stays in the cycle, not the helper.
- **Sonarr seam:** `ist["missing_searchable"] = len(missing_seasons)` (645) is the last prefix write; `ist["cutoff_searchable"]` (700) should move into the helper since it is a count field, not a search outcome, and the helper already has `cutoff_seasons` computed. First search-only line is `cursor = ist["missing_cursor"]` (646) / `slice_batch(missing_seasons, ...)` (647).
- **Lidarr seam:** `ist["missing_eligible"] = len(missing)` (896) is the last prefix write; `slice_batch(missing, ...)` (898) is the search-only boundary. No `*_searchable` counts in Lidarr.
- **Helper return contract:** must return `(filtered_missing, filtered_cutoff) | None`. The cycle needs these lists for `slice_batch`; they are not stored in `ist`. The count path discards the return value.
- **Rate-limit dict:** use sibling `last_refresh_time` (initialized in lifespan alongside `last_search_time`); prevents a refresh from rate-limiting a subsequent search.
- **New file:** `tests/test_refresh_counts.py` following existing `test_search.py` / `test_web.py` patterns; also update `test_app` fixture in `test_web.py` with `app.state.last_refresh_time = {}`.

### File Created

`.planning/phases/74-count-only-refresh/74-RESEARCH.md`

### Ready for Planning

Research complete. Planner can now create PLAN.md files.
