---
phase: 76-never-searched-first-search-queue
plan: "01"
subsystem: search-engine
tags: [pure-function, state-model, tdd, queue-priority]
dependency_graph:
  requires: []
  provides:
    - prioritize_batch pure function in triggarr/search/engine.py
    - AppState missing_searched/cutoff_searched fields in triggarr/state.py
  affects:
    - triggarr/search/engine.py (new pure function alongside slice_batch)
    - triggarr/state.py (AppState TypedDict + _default_instance_state)
    - tests/test_search.py (new prioritize_batch unit matrix)
    - tests/test_state.py (new searched-log round-trip/default/back-compat tests)
tech_stack:
  added: []
  patterns:
    - Pure function with Callable key_fn parameter (mirrors filter_by_tag convention)
    - Ordered searched-log as list[str] (oldest-front membership + recency encoding)
    - Additive TypedDict field additions (total=False; no migration needed)
key_files:
  created: []
  modified:
    - triggarr/search/engine.py
    - triggarr/state.py
    - tests/test_search.py
    - tests/test_state.py
decisions:
  - prioritize_batch placed near slice_batch in engine.py; slice_batch kept intact (oracle test dependency)
  - Test assertions revised to match correct pass-completion semantics — items already in pruned log count toward coverage even if not re-batched this cycle
  - Cursor fields (missing_cursor/cutoff_cursor) intentionally kept in AppState and _default_instance_state (HIGH-2: removing them while call sites still read them would KeyError; Plan 02 removes them with the call-site rewrite)
metrics:
  duration: 5m
  completed: "2026-06-04"
  tasks: 2
  files: 4
requirements: [QUEUE-01, QUEUE-02, QUEUE-04, QUEUE-05, QUEUE-06, QUEUE-09, QUEUE-10]
---

# Phase 76 Plan 01: prioritize_batch Pure Function + AppState Searched-Log Fields Summary

Pure never-searched-first dispatch function and additive AppState searched-log substrate with exhaustive TDD unit matrix including MED-1 zero-batch pass-completion guard and cold-start-equivalence oracle.

## What Was Built

### Task 1: TDD prioritize_batch — RED/GREEN/REFACTOR

Implemented `prioritize_batch(eligible_items, searched_log, batch_size, key_fn) -> tuple[list, list[str], bool]` in `triggarr/search/engine.py`.

**Algorithm (spec §6):**
1. Build `eligible_ids` set from `key_fn` over eligible items.
2. Prune `searched_log` to currently-eligible IDs preserving order (QUEUE-10).
3. Partition into `unsearched` (fetch order) and `searched` (in log).
4. Batch = `unsearched[:batch_size]`; if short, top up from pruned log front (oldest-first) (QUEUE-04/05).
5. Mark on attempt: append batched keys to log; re-batched keys move to tail (QUEUE-08).
6. `pass_completed = bool(batch) and eligible_ids.issubset(set(new_log))` — `bool(batch)` is MANDATORY (MED-1).

`slice_batch` remains untouched (oracle test depends on it; Plan 03 removes it).

**TDD Gate Compliance:**
- RED commit `81fa3c6`: 13 failing tests (ImportError — prioritize_batch not yet defined)
- GREEN commit `9b32c74`: all 14 prioritize_batch tests pass
- REFACTOR: ruff UP/SIM checks passed with no changes needed

**Test matrix (spec §8, exhaustive):**
- `test_prioritize_batch_cold_start` — empty log → first N items in fetch order
- `test_prioritize_batch_cold_start_equivalence` — QUEUE-06 oracle: `prioritize_batch(items,[], N, fn)[0] == slice_batch(items, 0, N)[0]` for N in {0,1,3,5,7}
- `test_prioritize_batch_unsearched_first` — unsearched take priority over already-searched
- `test_prioritize_batch_topup_oldest_first` — fewer unsearched than N; top-up fills from log front
- `test_prioritize_batch_pass_completion` — last unsearched batched → pass_completed=True
- `test_prioritize_batch_mid_pass_no_completion` — unsearched remain → pass_completed=False
- `test_prioritize_batch_prune_departed_items` — departed IDs drop from log, survivor order preserved
- `test_prioritize_batch_research_recency` — re-batched item moves to log tail
- `test_prioritize_batch_empty_eligible` — returns ([], [], False)
- `test_prioritize_batch_eligible_smaller_than_batch` — all searched, pass_completed=True
- `test_prioritize_batch_zero_batch_size_guard` — MED-1: batch_size=0, log already covers eligible → ([], unchanged_log, False)
- `test_prioritize_batch_negative_batch_size_guard` — MED-1 defensive: batch_size<0 → same
- `test_prioritize_batch_key_fn_sonarr_composite` — "1:1"/"1:2"/"1:0" are distinct keys; S2 searched after S1 despite same seriesId
- `test_prioritize_batch_key_fn_radarr_int_to_str` — int ids appear as str in new_log

### Task 2: ADD AppState searched-log fields + state tests

**`triggarr/state.py` changes:**
- Added `missing_searched: list[str]` and `cutoff_searched: list[str]` to `AppState` TypedDict with field comments matching the existing style
- Updated `_default_instance_state()` to return `missing_searched=[]` and `cutoff_searched=[]` alongside the still-present cursor fields (additive; no broken checkpoint)
- Cursor fields `missing_cursor`/`cutoff_cursor` intentionally kept (removed in Plan 02 with the 6 call-site rewrite)

**New tests in `tests/test_state.py`:**
- `test_searched_log_round_trip` — save/load round-trip preserves `missing_searched=["1","2"]` and `cutoff_searched=["9"]`
- `test_default_instance_state_has_empty_searched_logs` — _default_instance_state() seeds empty logs and still seeds cursors
- `test_default_state_with_settings_includes_searched_logs` — merge path auto-inherits empty logs
- `test_back_compat_load_pre_upgrade_state` — pre-upgrade state.json with cursor keys but no searched-logs loads clean: empty logs defaulted, missing_pass=2 carried forward, cursor values preserved (strip happens in Plan 02)

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `81fa3c6` | test(76-01) | RED: add failing prioritize_batch unit matrix + cold-start oracle |
| `9b32c74` | feat(76-01) | GREEN: implement prioritize_batch — never-searched-first dispatch |
| `8b9b510` | feat(76-01) | add searched-log fields to AppState + round-trip/default/back-compat tests |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected test assertions for pass-completion semantics**
- **Found during:** GREEN verification pass
- **Issue:** Initial test cases asserted `pass_completed is False` in scenarios where the pruned log already contained the items not in the current batch. Since `eligible_ids.issubset(set(new_log))` includes items that were in the pruned log from before (not just newly-batched items), pass_completed correctly resolved to True in those cases.
- **Fix:** Updated `test_prioritize_batch_unsearched_first` (changed batch_size to 2 so item 5 is excluded), `test_prioritize_batch_topup_oldest_first` (corrected assertion to True — all 5 eligible in new_log), and `test_prioritize_batch_research_recency` (corrected to True — item 3 survives in log from before)
- **Files modified:** `tests/test_search.py`
- **Commit:** `9b32c74`

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test commit before impl) | `81fa3c6` | PASS — ImportError confirms function absent |
| GREEN (impl commit, tests pass) | `9b32c74` | PASS — 14/14 tests green |
| REFACTOR | N/A | No structural changes needed; ruff clean |

## Known Stubs

None. `prioritize_batch` is a fully-implemented pure function. AppState fields are added and seeded with correct empty defaults. No stubs, no hardcoded empty values flowing to UI.

## Threat Flags

None. This plan adds a pure in-memory function and two `list[str]` state fields that ride the existing atomic `save_state()` write path. No new endpoints, network calls, user input, or secrets introduced (consistent with T-76-01/T-76-02/T-76-03 in the plan threat model — all accepted/mitigated by design).

## Self-Check: PASSED

- `triggarr/search/engine.py` exists and contains `def prioritize_batch(` and `def slice_batch(`
- `triggarr/state.py` exists and contains `missing_searched: list[str]` and `missing_cursor: int`
- Commits `81fa3c6`, `9b32c74`, `8b9b510` exist in git log
- `uv run pytest tests/test_search.py tests/test_state.py -x -q` → 156 passed
- `uv run ruff check triggarr/ tests/` → All checks passed
