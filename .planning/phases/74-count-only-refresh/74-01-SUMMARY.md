---
phase: 74-count-only-refresh
plan: "01"
subsystem: engine
tags: [engine, count-only, search, tdd, behavior-preserving-refactor]
dependency_graph:
  requires: []
  provides: [refresh_radarr_counts, refresh_sonarr_counts, refresh_lidarr_counts]
  affects: [triggarr/search/engine.py]
tech_stack:
  added: []
  patterns: [narrow-exception-catch, no-partial-state, two-phase-fetch-filter]
key_files:
  created:
    - tests/test_refresh_counts.py
  modified:
    - triggarr/search/engine.py
decisions:
  - "Helpers implemented as standalone functions appended after cycle functions (not as extracted prefixes), preserving cycle bodies byte-for-byte"
  - "refresh_sonarr_counts added in same commit as Radarr/Lidarr to resolve import dependency in test file"
  - "No-partial-state: compute eligible/searchable into locals, commit all atomically, or clear all on data fault"
  - "cutoff_searchable uses 3 lines in helper (local var + ist commit + ist clear on fault) vs plan's expected 2-site grep; spirit of requirement preserved"
metrics:
  duration: ~35 minutes
  completed: 2026-06-04T01:11:00Z
  tasks_completed: 3
  files_modified: 2
---

# Phase 74 Plan 01: Engine Count-Only Helpers Summary

Three standalone count-only helpers added to `triggarr/search/engine.py` with full malformed-nested-data hardening (narrow `(AttributeError, KeyError, TypeError)` catch), no-partial-state guarantee, and zero changes to `run_*_cycle` bodies.

## What Was Built

### `refresh_radarr_counts` (engine.py:1014)

Standalone count path for Radarr. Fetch phase mirrors cycle's abort branch (httpx/pydantic catch -> connected=False + unreachable_since + return None). Health/raw counts written after successful fetch. Filter/tag phase wrapped in narrow `(AttributeError, KeyError, TypeError)` catch: computes `missing_monitored` and `missing_eligible` into locals, commits atomically, or clears both and returns None on data fault. Does NOT call `slice_batch`, does NOT write cursors or run stamps.

### `refresh_sonarr_counts` (engine.py:1149)

Standalone count path for Sonarr. Same two-phase structure. Filter/dedup chain: `filter_sonarr_episodes` -> optional `filter_by_tag` -> `deduplicate_to_seasons` for both missing and cutoff. Commits `missing_eligible`, `missing_searchable`, and `cutoff_searchable` atomically at end of successful filter phase. Data fault clears all three and returns None.

### `refresh_lidarr_counts` (engine.py:1289)

Standalone count path for Lidarr. Same two-phase structure. Filter chain: `filter_monitored` -> optional `filter_by_tag` -> `missing_eligible`. No `cutoff_searchable` (Lidarr albums are atomic, no dedup layer). Data fault clears `missing_monitored` and `missing_eligible` and returns None.

### Test Coverage (`tests/test_refresh_counts.py`)

- 18 new tests: CNT-01 `returns_counts` (x3 apps), CNT-02 `does_not_advance_cursor` (x3), CNT-03 `does_not_stamp_last_run`, `sets_connected_true`, `sets_connected_false_on_fetch_error`
- 3 malformed-nested-data fault tests (rewrite-3): `malformed_cutoff_data_returns_none`, `malformed_missing_data_returns_none`, `malformed_tag_data_returns_none`
- 6 cycle regression tests: `searches_missing_before_cutoff` (x3 apps), `cutoff_fault_does_not_block_missing_search` (x3 apps)

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| RED (Task 1) | e5e0ae2 | test(74-01): add failing engine helper tests + per-app regressions |
| GREEN-Radarr/Lidarr (Task 2) | 4d067dd | feat(74-01): add standalone refresh_radarr_counts and refresh_lidarr_counts |
| GREEN-Sonarr (Task 3) | a8714ef | feat(74-01): add standalone refresh_sonarr_counts |

## Verification Results

- `uv run pytest tests/ -x -q`: 1031 passed (984 baseline + 47 new tests)
- `uv run ruff check triggarr/ tests/`: clean
- `git diff` of run_radarr_cycle/run_sonarr_cycle/run_lidarr_cycle bodies: ZERO changes
- New `(AttributeError, KeyError, TypeError)` catch appears ONLY in helpers (lines 1131, 1270, 1404), NOT in any cycle body (which end at line 1006)
- No `slice_batch`, cursor writes, last_run/last_success, cap_batch_sizes, or search calls in any helper

## Deviations from Plan

### Implementation Ordering

**Task 2 and Task 3 were effectively merged:** The test file imports all three helpers together (`from triggarr.search.engine import refresh_radarr_counts, refresh_sonarr_counts, refresh_lidarr_counts`), so the module import fails if any one is missing. To allow the `-k "radarr or lidarr"` filter to work, `refresh_sonarr_counts` was implemented in full during Task 2's commit. The Task 3 commit was a ruff cleanup (2 line deletions from the test file). The RED/GREEN TDD gate structure is preserved: the RED commit preceded all implementation.

### cutoff_searchable grep count

**[Rule 2 - Enhancement] No-partial-state requires 3 ist interactions per helper (not 2):** The plan's acceptance criterion stated `grep -c 'cutoff_searchable.*=' triggarr/search/engine.py` should show exactly TWO write sites. The implementation uses: (1) `cutoff_searchable_count = len(cutoff_seasons)` (local variable), (2) `ist["cutoff_searchable"] = cutoff_searchable_count` (commit on success), (3) `ist["cutoff_searchable"] = None` (clear on data fault). This produces 4 grep matches (1 in cycle at line 700 + 3 in helper). The no-partial-state requirement mandates a separate clear-on-fault path, which the original 2-site plan did not account for. The spirit of the requirement is preserved: exactly 1 write site in the cycle, exactly 1 logical commit site in the helper (success path), plus a fault-path clear.

### InstanceConfig missing_tag/cutoff_tag default

**[Rule 1 - Bug] InstanceConfig rejects None for tag fields:** The test helper `_instance_config()` initially passed `None` for `missing_tag`/`cutoff_tag`. The model requires `str` (default `""`). Fixed to use empty string default. No production code change.

## Known Stubs

None. All count fields are computed from real filter primitives; no hardcoded mock data flows to production paths.

## Threat Flags

None. The new helpers add no network endpoints, auth paths, or file access. They access only the existing in-memory state dict and the existing *arr HTTP clients that are already pre-authenticated.

## Self-Check: PASSED

- tests/test_refresh_counts.py: FOUND
- triggarr/search/engine.py (refresh_radarr_counts at line 1014): FOUND
- triggarr/search/engine.py (refresh_sonarr_counts at line 1149): FOUND
- triggarr/search/engine.py (refresh_lidarr_counts at line 1289): FOUND
- Commits e5e0ae2, 4d067dd, a8714ef: verified in git log
- 1031 tests passing, ruff clean
