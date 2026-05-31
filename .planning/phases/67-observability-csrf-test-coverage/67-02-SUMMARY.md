---
phase: 67-observability-csrf-test-coverage
plan: "02"
subsystem: performance
tags: [tag_cache, ttl, scheduler, engine, routes, resolver, invalidation, tdd, RES-03]
dependency_graph:
  requires: [67-01]
  provides: [tag_cache, _TAG_CACHE_TTL_SECONDS, get_tags_fn_resolver, tag_cache_invalidation]
  affects:
    - triggarr/search/scheduler.py
    - triggarr/search/engine.py
    - triggarr/web/routes.py
tech_stack:
  added: []
  patterns:
    - module_constant_TTL
    - app_state_scratch_dict
    - read_app_state_at_call_time_resolver
    - monotonic_TTL_comparison
    - targeted_cache_invalidation_under_search_lock
key_files:
  created: []
  modified:
    - triggarr/search/scheduler.py
    - triggarr/search/engine.py
    - triggarr/web/routes.py
    - tests/test_scheduler.py
    - tests/test_search.py
    - tests/test_web.py
decisions:
  - "D-05: app.state.tag_cache keyed (app_name, instance_name) -> (tags, fetched_at_monotonic), initialized in lifespan app.state block with WR-05 doc-comment style"
  - "D-06: _TAG_CACHE_TTL_SECONDS = 3600.0 module constant using time.monotonic(); no env-override (internal performance knob, not operator-configurable)"
  - "D-07: keyword-only get_tags_fn resolver (None default) wraps get_tags() call sites; resolver has NO try/except so failed fetches propagate to the cycle guard and are never cached (negative-caching avoidance)"
  - "D-08: targeted invalidation diffs url/api_key/missing_tag/cutoff_tag under existing search_lock; api_key compared via SecretStr equality matching the existing url/key diff style"
  - "Codex finding B: form-removal invalidation wired into the existing removal loop (new_cfg is None or not enabled) — reuses the already-computed removed/disabled set, no second pass"
  - "search_now wired with its own get_tags_fn resolver (promoted from optional to required) so no user-triggered path bypasses RES-03"
metrics:
  duration_seconds: 3000
  completed_date: "2026-05-31"
  tasks_completed: 2
  files_changed: 6
---

# Phase 67 Plan 02: Tag List Caching with 1h TTL Summary

A per-`(app_name, instance_name)` tag-list cache with a 1-hour `time.monotonic()` TTL, threaded into all three engine cycle fns via a keyword-only `get_tags_fn` resolver (None default keeps every existing call backward-compatible), populated by the scheduler `job()` closure and manual `search_now`, and invalidated under the existing `search_lock` on config change, instance removal, and form-removal.

## Tasks Completed

| Task | Type | Commits | Status |
|------|------|---------|--------|
| T1: TTL constant + tag_cache init + cached resolver + get_tags_fn param | TDD (RED/GREEN) | 0fd2416 (RED), 41247c7 (GREEN) | Done |
| T2: invalidate tag cache on config change/removal + wire search_now | TDD (RED/GREEN) | 2c8306e (RED), 2605cbf (GREEN) | Done |

## What Was Built

**T1 (scheduler.py + engine.py):**
- `scheduler.py`: added `_TAG_CACHE_TTL_SECONDS: float = 3600.0` next to `_SHUTDOWN_DRAIN_TIMEOUT` (D-06), documented as a monotonic-clock, non-operator-configurable internal knob. Initialized `app.state.tag_cache = {}` in the lifespan `app.state` block following the WR-05 doc-comment style (key `(app_name, instance_name)` -> value `(tags, fetched_at_monotonic)`). Inside the `job()` closure, within the existing `async with app.state.search_lock` and before `await cycle_fn(...)`, built `cache_key = (app_name, instance_name)` and an inner `async def _get_tags_cached()` that returns the cached tags when fresh (`time.monotonic() - fetched_at < _TAG_CACHE_TTL_SECONDS`) else fetches and stores. The resolver has NO try/except — a failed `get_tags()` propagates to the cycle fn's existing `except (httpx.HTTPError, pydantic.ValidationError)` guard, so the store line is unreachable on failure (D-07 negative-caching avoidance). Passed `get_tags_fn=_get_tags_cached` to the cycle call.
- `engine.py`: added `from collections.abc import Awaitable` (Callable already imported). Added keyword-only `*, get_tags_fn: Callable[[], Awaitable[list[Tag]]] | None = None` to `run_radarr_cycle`, `run_sonarr_cycle`, `run_lidarr_cycle`. At each `get_tags()` call site replaced `tags = await client.get_tags()` with `tags = await get_tags_fn() if get_tags_fn is not None else await client.get_tags()`, keeping the surrounding `tag_fetch_ok` / `try` / `except` guard exactly as-is.

**T2 (routes.py):**
- `save_settings`: after the per-app scheduler/client loop, inside `search_lock`, added the D-08 targeted diff — iterate `APP_TYPES`, look up each `new_cfg`'s `old_cfg` in `current_settings` (pre-update snapshot), skip new instances (`old_cfg is None`), and `request.app.state.tag_cache.pop((name, inst_name), None)` when `url`/`api_key`/`missing_tag`/`cutoff_tag` changed. `api_key` comparison uses SecretStr equality, matching the existing `key_changed` diff.
- `save_settings` form-removal (Codex finding B): inside the EXISTING removal loop (`if new_cfg is None or not new_cfg.enabled:`), after `clients_dict.pop(inst_name, None)`, added `request.app.state.tag_cache.pop((name, inst_name), None)`.
- `remove_instance`: after `triggarr_state[app_name].pop(instance_name, None)`, added `request.app.state.tag_cache.pop((app_name, instance_name), None)` (Pitfall 5).
- `search_now`: imported `_TAG_CACHE_TTL_SECONDS` from scheduler; built the same `_get_tags_cached` resolver reading `request.app.state.tag_cache` and passed `get_tags_fn=_get_tags_cached` so manual searches read/populate the cache.

**Tests:** `test_search.py` — 3 resolver tests (resolver-used-when-provided, fallback-when-None, resolver-exception-suppresses-filtering). `test_scheduler.py` — 3 cache tests (hit skips fetch, miss stores, stale refreshes) via a real RadarrClient on MockTransport with a tag-configured instance, plus `app.state.tag_cache = {}` added to all job()-exercising fixtures (Pitfall 8). `test_web.py` — 5 tests (changed->popped, unchanged->preserved, endpoint-removed->popped, form-removed->popped, search_now warm-cache reuse), plus `tag_cache = {}` added to both app fixtures.

## Deviations from Plan

None - plan executed exactly as written. (The plan's Task 2 verify `-k` listed `search_now_cache`; the implemented test is named `test_search_now_reuses_warm_tag_cache`, matched by `search_now`/`reuses_warm` and verified passing.)

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| T1 RED (`test(67-02): add failing tests for tag cache resolver and TTL`) | 0fd2416 | PASS |
| T1 GREEN (`feat(67-02): tag-list cache with 1h TTL threaded into cycle fns`) | 41247c7 | PASS |
| T2 RED (`test(67-02): add failing tests for tag cache invalidation and search_now`) | 2c8306e | PASS |
| T2 GREEN (`feat(67-02): invalidate tag cache on config change/removal; wire search_now`) | 2605cbf | PASS |

Commit chain is strictly linear with RED preceding GREEN for each task: 8833b61 -> 0fd2416 (T1 RED) -> 41247c7 (T1 GREEN) -> 2c8306e (T2 RED) -> 2605cbf (T2 GREEN) -> c5e7058 (docs).

RED runs confirmed real failures before implementation:
- T1 RED: `test_run_radarr_cycle_uses_get_tags_fn_when_provided` and `..._get_tags_fn_exception_suppresses_filtering` failed with `TypeError: run_radarr_cycle() got an unexpected keyword argument 'get_tags_fn'`; the three scheduler cache tests failed to import `_TAG_CACHE_TTL_SECONDS` (collection ImportError). The `falls_back_to_client` test passed in RED (it asserts the pre-existing direct-call behavior).
- T2 RED: 4 of 5 web tests failed (search_now awaited get_tags; invalidation pops absent); `preserves_unchanged` passed in RED (trivially true before any invalidation logic exists).

## Verification

- `uv run pytest tests/test_scheduler.py tests/test_search.py -k "tag_cache or get_tags_fn or cache or happy_path or make_search_job"` → 11 passed
- `uv run pytest tests/test_web.py` (full) → 245 passed
- `uv run pytest tests/ -q` → 960 passed, 27 warnings (baseline was 949; +11 net new tests, no regressions)
- `uv run ruff check triggarr/ tests/` → All checks passed
- Acceptance greps: `_TAG_CACHE_TTL_SECONDS` in scheduler.py = 2 (>=2); `get_tags_fn` in engine.py = 6 (>=6); `tag_cache.pop` in routes.py = 3 (>=3)
- Resolver has NO try/except around `client.get_tags()` (verified by reading the `_get_tags_cached` body at scheduler.py:152) — negative-caching guard intact

## Known Stubs

None. The cache is fully wired: scheduler job() and search_now build the resolver → engine cycle fns call it → successful fetches stored in app.state.tag_cache → save_settings/remove_instance invalidate.

## Threat Flags

None new. The implementation matches the plan's threat register exactly: T-67-03 (poisoning via failed fetch) mitigated by the no-try/except resolver; T-67-04/T-67-07 (stale cache after config change / form-removal) mitigated by the search_lock invalidation in save_settings and remove_instance. No new network endpoints, auth paths, or schema changes were introduced. The cache stores only `list[Tag]` (id/label), never any SecretStr; the cache key contains instance_name, not the secret.

## Self-Check: PASSED

All modified files verified present and changed. All four task commits verified in git log (0fd2416, 41247c7, 2c8306e, 2605cbf). 960 tests passing, ruff clean.
