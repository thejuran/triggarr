---
phase: 67-observability-csrf-test-coverage
plan: "01"
subsystem: observability
tags: [last_success, app_card, state, engine, routes, template, tdd]
dependency_graph:
  requires: []
  provides: [last_success_field, last_success_stale_computation, last_ok_card_display]
  affects: [triggarr/state.py, triggarr/search/engine.py, triggarr/web/routes.py, triggarr/templates/partials/app_card.html]
tech_stack:
  added: []
  patterns: [TypedDict_field_extension, render_time_stale_computation, amber_stale_flag_pattern]
key_files:
  created: []
  modified:
    - triggarr/state.py
    - triggarr/search/engine.py
    - triggarr/web/routes.py
    - triggarr/templates/partials/app_card.html
    - tests/test_state.py
    - tests/test_search.py
    - tests/test_web.py
    - tests/test_app_cards.py
decisions:
  - "last_success written as single now_iso capture alongside last_run at all three cycle success points (D-02)"
  - "Stale computation at render time in _build_app_context using 2x search_interval threshold (D-03)"
  - "Last OK rendered on separate row beneath Last run/Next row for layout clarity (D-04 discretion)"
  - "Last OK shown in BOTH connected/waiting AND unreachable branches (Codex finding A fix)"
  - "Never case always text-triggarr-muted, never amber (Pitfall 4 guard)"
metrics:
  duration_seconds: 529
  completed_date: "2026-05-31"
  tasks_completed: 3
  files_changed: 8
---

# Phase 67 Plan 01: Last Successful Search Timestamp Summary

Per-instance "Last OK" timestamp threaded through state (TypedDict field) → engine (write at cycle success) → routes (render-time stale computation) → template (amber-flagged card entry), with Codex finding A fix ensuring the timestamp is visible on unreachable cards.

## Tasks Completed

| Task | Type | Commits | Status |
|------|------|---------|--------|
| T1: Add last_success field + write at cycle success | TDD (RED/GREEN) | 26db34d (RED), 7a53be9 (GREEN) | Done |
| T2: Compute last_success_stale in _build_app_context | TDD (RED/GREEN) | e3f42ff (RED), 944ce5f (GREEN) | Done |
| T3: Render Last OK on app card + unreachable fix | execute | 1c42fa9 | Done |

## What Was Built

**T1 (state.py + engine.py):** Added `last_success: str | None` to `AppState` TypedDict immediately after `last_run` (line 51), with default `None` in `_default_instance_state()`. In `engine.py`, all three cycle functions (Radarr line 508, Sonarr line 752, Lidarr line 990) now capture a single `now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")` and assign both `ist["last_run"] = now_iso` and `ist["last_success"] = now_iso`. The connection-error early-return paths are untouched, so `last_success` only records cycles that reached the connected-True completion point. Serialization is automatic via `json.dump` + `_merge_defaults` dict-merge (no migration code needed).

**T2 (routes.py):** Added `timedelta` to the `from datetime import ...` line. In `_build_app_context`, after `app_state` is resolved, reads `last_success`, defaults `last_success_stale = True`, then parses the ISO timestamp with `fromisoformat`, reads `instance_cfg.search_interval`, computes threshold as `timedelta(minutes=search_interval * 2)`, and sets `last_success_stale = (now - ls_dt) > threshold`. Exception handler is `except (ValueError, TypeError)` (no bare except per CLAUDE.md). Both `"last_success"` and `"last_success_stale"` keys added to the returned context dict alongside `"last_run"`.

**T3 (app_card.html):** Added a dedicated `<div class="text-[11px] font-mono text-triggarr-muted mb-4">Last OK: ...` row beneath the existing "Last run / Next" row in the connected/waiting body. The existing schedule row changed from `mb-4` to `mb-1` since the Last OK row now carries the bottom margin. Amber guard: `{% if app.last_success %}` outer check, then `{% if app.last_success_stale %}text-amber-400{% else %}text-triggarr-text{% endif %}` inner class. The `{% else %}Never{% endif %}` branch always uses `text-triggarr-muted`. In the unreachable body, an equivalent "Last OK" line was added beneath the "Check API key" hint — fixing Codex adversarial finding A.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_schedule_row_present locked old mb-4 class on schedule row**
- **Found during:** Task 3 full suite run
- **Issue:** The schedule row `<div>` class changed from `mb-4 flex justify-between` to `mb-1 flex justify-between` because the Last OK row now provides bottom spacing. `tests/test_app_cards.py:174` asserted the old class string exactly.
- **Fix:** Updated the test assertion to `mb-1` and added a docstring explaining the layout change.
- **Files modified:** `tests/test_app_cards.py`
- **Commit:** d252b55

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| T1 RED (`test(67-01): ...`) | 26db34d | PASS |
| T1 GREEN (`feat(67-01): add last_success field...`) | 7a53be9 | PASS |
| T2 RED (`test(67-01): add failing tests for last_success_stale...`) | e3f42ff | PASS |
| T2 GREEN (`feat(67-01): compute last_success_stale...`) | 944ce5f | PASS |

## Verification

- `uv run pytest tests/ -x -q` → 944 passed, 27 warnings
- `uv run ruff check triggarr/ tests/` → All checks passed
- `grep -c 'last_success' triggarr/search/engine.py` → 6 (3 comment lines + 3 assignments = 1 per cycle)
- Codex finding A: `test_app_card_unreachable_still_shows_last_ok` passes — Last OK renders on disconnected cards
- Pitfall 4: `test_app_card_no_last_success_renders_never_without_amber` passes — Never is never amber

## Known Stubs

None. All data is wired: `last_success` written in engine cycles → read in `_build_app_context` → rendered in `app_card.html`.

## Threat Flags

None. The `last_success` field is an ISO timestamp written only at in-process cycle completion. No external input reaches it. The rendered timestamp in HTML is non-sensitive per the plan's threat register (T-67-01: accept, LOW).

## Self-Check: PASSED

All files verified present. All 6 task commits verified in git log (26db34d, 7a53be9, e3f42ff, 944ce5f, 1c42fa9, d252b55). 944 tests passing, ruff clean.
