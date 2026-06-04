---
phase: 76-never-searched-first-search-queue
plan: "02"
subsystem: search-engine
tags: [queue-priority, state-migration, cycle-integration, tdd]
dependency_graph:
  requires:
    - 76-01 (prioritize_batch pure function + AppState searched-log fields)
  provides:
    - cursor fields removed from AppState + _default_instance_state
    - legacy cursor-key strip in _merge_defaults (HIGH-1 inline pop)
    - 6 rewired cycle call sites in engine.py using prioritize_batch
    - load->save round-trip test proving cursor keys absent from written JSON
    - Sonarr both-queue + Specials composite-key integration (MED-2)
  affects:
    - triggarr/state.py (TypedDict, _default_instance_state, _merge_defaults)
    - triggarr/search/engine.py (6 call sites: Radarr/Sonarr/Lidarr x missing/cutoff)
    - tests/test_state.py (cursor asserts -> searched-log asserts + HIGH-1 round-trip test)
    - tests/test_search.py (cursor-advancement -> searched-log tests + new cycle-integration)
    - tests/test_web.py (Rule 1 auto-fix: one cursor assert -> searched-log assert)
tech_stack:
  added: []
  patterns:
    - Thin-caller pattern at each cycle site (define key_fn, call prioritize_batch, thin write-back)
    - Inline legacy-key pop in _merge_defaults (HIGH-1, no migration framework, no version bump)
    - Loguru field-binding for pass-complete INFO line (never f-string into message)
key_files:
  created: []
  modified:
    - triggarr/state.py
    - triggarr/search/engine.py
    - tests/test_state.py
    - tests/test_search.py
    - tests/test_web.py
decisions:
  - "HIGH-2: cursor field removal and call-site rewrite land in the same plan -- no broken checkpoint"
  - "HIGH-1: inline pop in _merge_defaults (not a versioned migration, YAGNI) actively removes legacy cursor keys so save_state never writes them back"
  - "Thin-caller pattern: per-app key_fn defined at each site, prioritize_batch called, write-back ist['<q>_searched'] = [] if pass_done else new_log"
  - "slice_batch def retained (Plan 03 removes it after all callers migrated)"
  - "Rule 1 auto-fix: test_web.py cursor assertion broken by field removal; fixed to assert missing_searched == []"
metrics:
  duration: "~35m"
  completed: "2026-06-04"
  tasks: 3
  files: 5
requirements: [QUEUE-02, QUEUE-03, QUEUE-07, QUEUE-08, QUEUE-09, QUEUE-11]
---

# Phase 76 Plan 02: Cursor Removal + 6 Call-Site Rewire + Cycle-Integration Summary

Remove cursor fields atomically with the call-site rewrite, strip legacy keys on load, and prove the composite key at the real call sites for both Sonarr queues including Specials.

## What Was Built

### Task 1: Remove cursor fields + _merge_defaults strip + HIGH-1 round-trip test

**`triggarr/state.py` changes:**
- Deleted `missing_cursor: int` and `cutoff_cursor: int` from `AppState` TypedDict (HIGH-2)
- Updated `_default_instance_state()` to return only `missing_searched=[]`, `cutoff_searched=[]`, `last_run=None`, `last_success=None`
- Updated module docstring (cosmetic: "cursors" -> "searched-logs")
- Added inline legacy-key strip in `_merge_defaults` immediately after the `{**_default_instance_state(), **instance_data}` merge:
  ```python
  for legacy_key in ("missing_cursor", "cutoff_cursor"):
      merged.pop(legacy_key, None)
  ```
  This actively removes pre-upgrade cursor keys on load so `save_state` never writes them back (HIGH-1). Implemented as a loop over a tuple -- semantically equivalent to two direct pops. No version bump, no migration framework (spec S9 YAGNI).
- `_is_v22_state_format` / `_migrate_v22_state` left untouched (they detect real v2.2 on-disk format using `missing_cursor` presence and run before `_merge_defaults`)

**`tests/test_state.py` changes:**
- All cursor-value assertions flipped to searched-log assertions and `"missing_cursor" not in` checks
- v2.2 migration test: fixture shape kept (legitimate old file), output assertions updated -- cursor keys STRIPPED, non-cursor fields survive
- Added `test_strip_on_load_save_round_trip`: writes a pre-upgrade state.json with `missing_cursor=7, cutoff_cursor=3, missing_pass=2, missing_searched=["1"]`; calls `load_state` then `save_state` to a separate path; re-reads the WRITTEN JSON file directly; asserts `"missing_cursor" not in` and `"cutoff_cursor" not in` the saved instance dict, while `missing_pass==2` and `missing_searched==["1"]` survive

### Task 2: Rewire all 6 cycle call sites to prioritize_batch

**`triggarr/search/engine.py` changes -- all 6 sites:**

| Site | key_fn |
|------|--------|
| Radarr missing | `lambda m: str(m["id"])` |
| Radarr cutoff | `lambda m: str(m["id"])` |
| Sonarr missing | `lambda s: f'{s["seriesId"]}:{s["seasonNumber"]}'` |
| Sonarr cutoff | `lambda s: f'{s["seriesId"]}:{s["seasonNumber"]}'` |
| Lidarr missing | `lambda a: str(a["id"])` |
| Lidarr cutoff | `lambda a: str(a["id"])` |

At each site:
- Deleted `cursor = ist["<q>_cursor"]` read and `ist["<q>_cursor"] = new_cursor` write
- Replaced `batch, new_cursor = slice_batch(items, cursor, limit)` with `batch, new_log, pass_done = prioritize_batch(items, ist.get("<q>_searched", []), limit, key_fn=...)`
- Per-item loop body left byte-for-byte unchanged (both `except PendingCapExceeded` and `except (httpx.HTTPError, pydantic.ValidationError, aiosqlite.Error, OSError)` arms verbatim -- no log mutation inside the loop, mark-on-attempt lives inside `prioritize_batch` before the loop)
- After loop: `ist["<q>_searched"] = [] if pass_done else new_log`
- Replaced wrap-detect block with `if pass_done:` that bumps `ist["<q>_pass"]` and emits one loguru field-bound INFO line
- `slice_batch` def retained (Plan 03 removes it); `refresh_*_counts` untouched

### Task 3: Migrate cursor-asserts + cycle-integration coverage

**`tests/test_search.py` changes:**

Migrated tests (cursor-value asserts -> searched-log asserts):
- `test_run_radarr_cycle_happy_path`: `missing_cursor == 0` -> `missing_searched == []`, `missing_pass == 1`
- `test_run_radarr_cycle_network_failure`: seeded `missing_searched = ["1","2"]`; asserts unchanged on abort
- `test_run_radarr_cycle_cursor_advancement` -> `test_run_radarr_cycle_searched_log_advancement`
- `test_run_sonarr_cycle_network_failure`: seeded `missing_searched`; asserts unchanged
- `test_run_sonarr_cycle_cursor_advancement` -> `test_run_sonarr_cycle_searched_log_advancement`
- Lidarr happy-path, network-failure, cursor-advancement analogously migrated
- `test_run_*_cycle_empty_queues` (3 tests): cursor asserts -> `missing_searched == []`
- `test_cleanup_orphaned_instances_does_not_mutate_input`: updated AppState args
- `test_make_test_state_helper_works`: cursor assert -> searched-log assert

New Radarr cycle-integration extensions:
- `test_run_radarr_cycle_mark_on_attempt`: failing search still contributes to pass completion (D-04)
- `test_run_radarr_cycle_new_item_jumps_line`: new eligible item searched before already-searched
- `test_run_radarr_cycle_pass_reset`: 2 consecutive passes increment missing_pass to 1 then 2
- `test_run_radarr_cycle_commit_at_cycle_end`: searched-log and missing_pass consistent at cycle end

MANDATORY Sonarr both-queue + Specials integration (MED-2):
- `test_run_sonarr_cycle_missing_composite_key_with_specials`: seriesId=123 seasons 0,1,2; batch_size=2 < 3; asserts composite key format "123:N" in missing_searched across 2 cycles
- `test_run_sonarr_cycle_missing_specials_distinct_key`: proves "123:0" and "123:1" are distinct non-colliding keys
- `test_run_sonarr_cycle_cutoff_composite_key_with_specials`: same shape against cutoff_searched queue
- `test_run_sonarr_cycle_both_queues_exact_composite_keys`: drives BOTH queues simultaneously; asserts exact {"123:0","123:1","123:2"} in both missing_searched and cutoff_searched; both passes complete in 2 cycles

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `9f2c238` | feat(76-02) | Remove cursor fields from AppState + strip legacy cursor keys on load |
| `36dd6ba` | feat(76-02) | Rewire all 6 cycle call sites to prioritize_batch with per-app key_fn |
| `cde32d3` | feat(76-02) | Migrate cycle cursor-asserts to searched-log + Sonarr MED-2 + Radarr extensions |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_web.py cursor assertion broken by field removal**
- **Found during:** Task 3 final full-suite run
- **Issue:** `test_save_settings_creates_state_for_new_instance` asserted `state["radarr"]["Default"]["missing_cursor"] == 0` -- KeyError after cursor field removal
- **Fix:** Updated assertion to `missing_searched == []` and `"missing_cursor" not in`
- **Files modified:** `tests/test_web.py`
- **Commit:** `cde32d3`

## Known Stubs

None. All cursor fields removed; searched-logs are live and correctly wired at all 6 call sites.

## Threat Flags

None. Internal dispatch rewiring only -- no new endpoints, network calls, user input, or secrets introduced. The pass-complete INFO line emits only app/queue/pass-number/item-count via loguru field-binding (T-76-04 mitigated as designed).

## Self-Check: PASSED

- `triggarr/state.py` exists: no `missing_cursor: int` in TypedDict; has `merged.pop(legacy_key, None)` loop in `_merge_defaults`
- `triggarr/search/engine.py`: 6 `batch, new_log, pass_done = prioritize_batch(` call sites; no `ist["missing_cursor"]` or `ist["cutoff_cursor"]` accesses; `slice_batch` def present
- `tests/test_state.py`: has `test_strip_on_load_save_round_trip` asserting cursor keys ABSENT from written JSON
- `tests/test_search.py`: has `"123:0"` composite key assertions; MANDATORY Sonarr both-queue tests pass
- Commits `9f2c238`, `36dd6ba`, `cde32d3` exist in git log
- `uv run pytest tests/test_state.py tests/test_search.py -x -q` -> 165 passed
- `uv run pytest tests/ -x -q` -> 1094 passed
- `uv run ruff check triggarr/ tests/` -> All checks passed
