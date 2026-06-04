---
phase: 74-count-only-refresh
plan: "02"
subsystem: web-routes
tags: [route, tdd, count-only, rate-limit, always-200, search-lock, htmx]
dependency_graph:
  requires: [74-01]
  provides: [refresh_counts route, last_refresh_time state init]
  affects:
    - triggarr/web/routes.py
    - triggarr/search/scheduler.py
    - tests/test_refresh_counts.py
    - tests/test_web.py
tech_stack:
  added: []
  patterns:
    - optimistic-then-in-lock rate-limit (DRSEC-03 parity)
    - bare-await-discard-return (codex rewrite-2 contract)
    - always-200-on-none (codex rewrite-3 contract)
    - sibling-rate-limit-dict (D-08)
key_files:
  created: []
  modified:
    - triggarr/web/routes.py
    - triggarr/search/scheduler.py
    - tests/test_refresh_counts.py
    - tests/test_web.py
decisions:
  - "Bare await: helper return is discarded; card built from in-place ist mutation unconditionally after try/except (codex rewrite-2 + rewrite-3)"
  - "Route catch tuple stays exactly (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError) — no widening for (AttributeError, KeyError, TypeError) since the helper handles those internally and returns None"
  - "sibling last_refresh_time dict initialized in scheduler lifespan and test fixtures so refresh and search rate-limits are independent (D-08)"
metrics:
  duration: ~25 minutes
  completed: 2026-06-04T01:45:00Z
  tasks_completed: 2
  files_modified: 4
---

# Phase 74 Plan 02: refresh_counts Route Summary

`POST /api/refresh-counts/{app}/{instance}` added as a structural copy of `search_now`, calling the per-app count helper directly under `search_lock` with the helper return discarded and the card built unconditionally from the in-place ist mutation.

## What Was Built

### `refresh_counts` endpoint (`triggarr/web/routes.py:981`)

Structural copy of `search_now` with these differences:
- Calls `refresh_fns[app_name](...)` directly (not `_run_one_cycle`)
- Helper await is a **bare statement** — return value discarded (no unpack, no assignment)
- Uses `request.app.state.last_refresh_time` (sibling dict, D-08) instead of `last_search_time`
- `_build_app_context(...)` → `TemplateResponse(...)` runs **unconditionally** after the try/except (always-200 on helper None from fetch failure OR rewrite-3 malformed-data fault)
- No `save_state`, no `search_failures` touch, no `last_run`/`last_success` stamp

Guards (mirrors `search_now`):
- `len(instance_name) > 64` → 400
- `app_name not in APP_TYPES` → 400
- Instance not enabled or no client → 400
- Rate-limited (optimistic pre-lock + DRSEC-03 in-lock re-check) → 429
- Success or helper None → 200 + card partial

Catch tuple: exactly `(httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` — backstop only; helper catches its own `(AttributeError, KeyError, TypeError)` internally (rewrite-3).

### `app.state.last_refresh_time = {}` (`triggarr/search/scheduler.py`)

Initialized immediately after `last_search_time` in the lifespan. Sibling dict so a count refresh and a manual search can each proceed without rate-limiting the other (D-08, Focus Point 4).

### Route tests (`tests/test_refresh_counts.py`)

11 new route tests added to the existing file:

| Test | What it proves |
|------|---------------|
| `test_refresh_counts_invalid_app` | 400 + "Invalid app" guard |
| `test_refresh_counts_instance_name_too_long` | 400 on >64 char name |
| `test_refresh_counts_happy_path` | 200 + Radarr card; 3-tuple mock |
| `test_refresh_counts_three_tuple_passes_through` | Codex rewrite-2: 3-tuple return flows through without error |
| `test_refresh_counts_builds_card_from_ist_not_return` | Codex rewrite-2: card built from ist mutation, not return value |
| `test_refresh_counts_malformed_data_returns_200_card` | Rewrite-3: helper returning None → 200 + disconnected card, NOT 500 |
| `test_refresh_counts_malformed_data_does_not_mutate_search_state` | Rewrite-3: search_failures/cursors/last_search_time/last_run unchanged on data fault |
| `test_refresh_counts_rate_limited` | 429 when rate key pre-seeded |
| `test_refresh_counts_rate_limit_concurrent_protection` | DRSEC-03: first 200, second 429 |
| `test_refresh_counts_does_not_touch_failure_counter` | search_failures unchanged on success (CNT-03) |
| `test_refresh_counts_does_not_touch_last_search_time` | last_search_time untouched (independent dicts) |

### `tests/test_web.py` fixture

Added `app.state.last_refresh_time = {}` to `test_app` fixture between `last_search_time` and `last_health_check` (Pitfall 7 from RESEARCH.md). Prevents `AttributeError` in all post-Plan-02 card-partial tests that use the `test_app` fixture.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| RED (Task 1) | 35b781a | test(74-02): add failing refresh_counts route tests + fixture state |
| GREEN (Task 2) | d3aca2a | feat(74-02): add POST /api/refresh-counts endpoint |

## Verification Results

- `uv run pytest tests/test_refresh_counts.py -k "refresh_counts" -x -q`: 29 passed (11 new route + 18 Plan 01 engine tests)
- `uv run pytest tests/ -x -q`: **1042 passed** (1031 Plan 01 baseline + 11 new route tests)
- `uv run ruff check triggarr/ tests/`: clean
- `git diff triggarr/web/middleware.py`: empty (T-74-05 — no auth surface change)

### Source-level assertions

- `grep -n "async def refresh_counts" triggarr/web/routes.py` → line 981 confirmed
- `grep -n "await refresh_fns\[app_name\]" triggarr/web/routes.py` → line 1050, bare await
- `grep -E "(=|,)\s*await refresh_fns\[app_name\]" triggarr/web/routes.py` → NO MATCH (not assigned/unpacked)
- No `_run_one_cycle`, `save_state`, `search_failures`, `last_run`/`last_success` writes in the new function body
- Catch tuple contains no `AttributeError/KeyError/TypeError` (comment only explains WHY they are excluded)
- `grep -c "last_refresh_time" triggarr/search/scheduler.py` → 2 (dict init + comment)
- `grep -c "last_refresh_time" tests/test_web.py` → 1 (fixture state line)
- `grep -c "last_refresh_time" tests/test_refresh_counts.py` → 3 (fixture + test references)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. The endpoint delegates entirely to the engine helper (already live from Plan 01) and returns the same card partial as `search_now`. No hardcoded values flow to the UI.

## Threat Flags

None. The new endpoint:
- Is NOT added to `EXEMPT_PREFIXES` (inherits auth middleware unchanged — T-74-05)
- Has the same `len > 64` + `APP_TYPES` allowlist + enabled-instance/client guards as `search_now` (T-74-06)
- Has the same DRSEC-03 double-check on `last_refresh_time` (T-74-07)
- Uses `_sanitize_exc` for httpx/pydantic exceptions; `str(exc)` for sqlite/OSError (T-74-08)
- Never touches `search_failures` or `last_search_time` (T-74-09)
- Bare await discards the helper return; card built from ist (T-74-10)
- Helper returns None (not raises) on malformed data; endpoint's unconditional response build covers it (T-74-12)

## Self-Check: PASSED

- triggarr/web/routes.py (refresh_counts at line 981): FOUND
- triggarr/search/scheduler.py (last_refresh_time init): FOUND
- tests/test_refresh_counts.py (11 route tests + 2 fixtures): FOUND
- tests/test_web.py (last_refresh_time in test_app fixture): FOUND
- Commits 35b781a (RED) and d3aca2a (GREEN): verified in git log
- 1042 tests passing, ruff clean
