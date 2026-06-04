---
phase: 76-never-searched-first-search-queue
verified: 2026-06-04T21:05:09Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 76: Never-Searched-First Search Queue Verification Report

**Phase Goal:** The scheduler remembers which items it has already searched (per instance, per queue) and prioritizes never-searched items each cycle, while staying behavior-identical to today on a cold start.
**Verified:** 2026-06-04T21:05:09Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | prioritize_batch is the live dispatcher at all 6 call sites; slice_batch is gone everywhere | VERIFIED | 6 `batch, new_log, pass_done = prioritize_batch(` lines in engine.py at lines 455, 509, 704, 764, 965, 1020; `grep -rq "slice_batch" triggarr/ tests/` returns empty |
| 2 | Searched-log state model: AppState has missing_searched/cutoff_searched list[str]; cursor fields removed; _default_instance_state seeds empty logs | VERIFIED | state.py lines 48–49 declare fields; lines 77–84 seed `missing_searched=[], cutoff_searched=[]`; no `missing_cursor: int` or `cutoff_cursor: int` in AppState TypedDict |
| 3 | HIGH-1 strip-on-load: _merge_defaults pops missing_cursor/cutoff_cursor; load→save→read-back test asserts cursor keys absent from written JSON | VERIFIED | state.py lines 152–153 have the inline pop loop; `test_strip_on_load_save_round_trip` in test_state.py (line 566) reads back the written JSON file and asserts cursor key absence |
| 4 | MED-1 bool(batch) pass guard: batch_size<=0 returns pass_completed=False and does NOT grow the log | VERIFIED | engine.py line 201: `pass_completed = bool(batch) and eligible_ids.issubset(set(new_log))`; tests `test_prioritize_batch_zero_batch_size_guard` and `test_prioritize_batch_negative_batch_size_guard` at lines 207–230 cover both cases |
| 5 | Mark-on-attempt + prune: failed search stays in log; log pruned to eligible each cycle | VERIFIED | prioritize_batch marks before the loop (keys appended before `for` in the search loop body); prune at line 179; `test_run_radarr_cycle_mark_on_attempt` (line 539) and `test_prioritize_batch_prune_departed_items` (line 159) cover both properties |
| 6 | Commit-at-cycle-end only: searched-log and *_pass commit via single save_state() at cycle end; per-item loop body unchanged | VERIFIED | All 6 call sites write `ist["<q>_searched"]` and `ist["<q>_pass"]` after the loop; no writes inside try/except; save_state() is called once per cycle in the orchestrator (unchanged) |
| 7 | Cold-start equivalence (QUEUE-06): prioritize_batch(items, [], N, key_fn)[0] equals the first-N items in fetch order; fixed-expectation test (no slice_batch reference) | VERIFIED | `test_prioritize_batch_cold_start_fixed_expectation` at line 88 asserts hardcoded expected values for N=0,1,3,5,7 with no slice_batch dependency |
| 8 | Count-only queue-independence preserved: refresh_*_counts neither reads nor writes the searched-log (Radarr/Sonarr/Lidarr) | VERIFIED | `test_refresh_radarr_counts_does_not_touch_searched_log` (line 129), `test_refresh_sonarr_counts_does_not_touch_searched_log` (line 251), `test_refresh_lidarr_counts_does_not_touch_searched_log` (line 317) — all three seed logs and assert unchanged after refresh |
| 9 | Behavior preservation: full suite green (1089 passing), ruff clean | VERIFIED | `uv run pytest tests/ -x -q` → 1089 passed; `uv run ruff check triggarr/ tests/` → All checks passed |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `triggarr/search/engine.py` | `prioritize_batch` pure function + 6 wired call sites; slice_batch absent | VERIFIED | Function at line 133; 6 calls at lines 455, 509, 704, 764, 965, 1020; no slice_batch anywhere |
| `triggarr/state.py` | AppState with missing_searched/cutoff_searched; cursor fields removed; _merge_defaults inline strip | VERIFIED | Fields at lines 48–49; _default_instance_state at 77–84; strip loop at 152–153 |
| `tests/test_search.py` | prioritize_batch unit matrix + cold-start fixed-expectation + cycle integration incl. Sonarr both-queue+Specials | VERIFIED | Full matrix at lines 79–260; cold-start fixed-expectation at line 88; Sonarr both-queue+Specials at lines 863–1060 |
| `tests/test_state.py` | searched-log round-trip + HIGH-1 load-save-readback + default-state + back-compat tests | VERIFIED | Round-trip at line 488; HIGH-1 readback at line 566; default-state at line 513; back-compat at line 535 |
| `tests/test_refresh_counts.py` | Re-expressed queue-independence tests asserting searched-log unchanged (Radarr/Sonarr/Lidarr) | VERIFIED | Three tests at lines 129, 251, 317; no cursor references remain |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| engine.py Radarr missing site | prioritize_batch | `key_fn=lambda m: str(m["id"])` | WIRED | Line 455–458 |
| engine.py Radarr cutoff site | prioritize_batch | `key_fn=lambda m: str(m["id"])` | WIRED | Line 509–512 |
| engine.py Sonarr missing site | prioritize_batch | `key_fn=lambda s: f'{s["seriesId"]}:{s["seasonNumber"]}'` | WIRED | Line 704–707 |
| engine.py Sonarr cutoff site | prioritize_batch | `key_fn=lambda s: f'{s["seriesId"]}:{s["seasonNumber"]}'` | WIRED | Line 764–767 |
| engine.py Lidarr missing site | prioritize_batch | `key_fn=lambda a: str(a["id"])` | WIRED | Line 965–968 |
| engine.py Lidarr cutoff site | prioritize_batch | `key_fn=lambda a: str(a["id"])` | WIRED | Line 1020–1023 |
| state.py _merge_defaults | legacy cursor strip | `for legacy_key in ("missing_cursor","cutoff_cursor"): merged.pop(legacy_key, None)` | WIRED | Lines 152–153 |
| tests/test_refresh_counts.py | queue-independence invariant | seed searched-log, refresh, assert unchanged | WIRED | All 3 apps covered |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| engine.py call sites | `missing_searched`/`cutoff_searched` | `ist.get("<q>_searched", [])` from loaded TriggarrState | Yes — loaded from state.json via load_state() → save_state() | FLOWING |
| state.py | `missing_searched`, `cutoff_searched` | JSON deserialization in load_state(); defaults from _default_instance_state() | Yes — real JSON persistence with atomic write | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite green | `uv run pytest tests/ -x -q` | 1089 passed, 0 failed, 32 warnings | PASS |
| Ruff clean | `uv run ruff check triggarr/ tests/` | All checks passed | PASS |
| slice_batch absent everywhere | `grep -rq "slice_batch" triggarr/ tests/` | No output (empty) | PASS |
| No cursor reads/writes at call sites | `grep -n "ist\[.(missing|cutoff)_cursor" engine.py` | No output | PASS |
| Cursor fields removed from AppState | `grep -E "missing_cursor: int|cutoff_cursor: int" triggarr/state.py` | No output | PASS |
| Legacy cursor strip present in _merge_defaults | `grep -Eq "pop\(.(missing|cutoff)_cursor" triggarr/state.py` | Line 152 matches | PASS |
| No cursor refs in tests outside test_state.py | `grep -rlE "missing_cursor|cutoff_cursor" tests/ | grep -v test_state.py` | No output | PASS |
| Legacy cursor regression coverage in test_state.py | `grep -qE "missing_cursor|cutoff_cursor" tests/test_state.py` | Many hits at v2.2 fixture + strip assertions | PASS |

### Probe Execution

Step 7c: SKIPPED (no probe scripts declared; phase is a pure code refactor with no `scripts/*/tests/probe-*.sh` files)

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| QUEUE-01 | 76-01, 76-02 | AppState persists ordered searched-log per queue in state.json | SATISFIED | missing_searched/cutoff_searched fields at state.py:48–49; round-trip tests in test_state.py |
| QUEUE-02 | 76-01, 76-02 | Item IDs normalized per app type; Sonarr uses seriesId:seasonNumber composite | SATISFIED | key_fn per call site verified; Sonarr tests assert "123:0"/"123:1"/"123:2" distinctness |
| QUEUE-03 | 76-02, 76-03 | cursor fields removed; pre-upgrade state.json loads cleanly with cursors stripped | SATISFIED | _merge_defaults inline pop at state.py:152–153; test_strip_on_load_save_round_trip reads back written JSON |
| QUEUE-04 | 76-01, 76-02 | Never-searched items fill batch first (fetch order) | SATISFIED | prioritize_batch algorithm at engine.py:183; test_prioritize_batch_unsearched_first |
| QUEUE-05 | 76-01, 76-02 | Top up with oldest-searched-first when unsearched < N | SATISFIED | engine.py:188–194; test_prioritize_batch_topup_oldest_first |
| QUEUE-06 | 76-01, 76-03 | Cold start produces same batch as prior first-cycle cursor walk | SATISFIED | test_prioritize_batch_cold_start_fixed_expectation (slice_batch-free, hardcoded expected values) |
| QUEUE-07 | 76-02, 76-03 | slice_batch replaced at all 6 sites; slice_batch removed | SATISFIED | 6 call sites verified; `grep -rq slice_batch` returns empty |
| QUEUE-08 | 76-01, 76-02 | Mark-on-attempt: item marked before search loop, failing item stays in log | SATISFIED | prioritize_batch marks before loop; test_run_radarr_cycle_mark_on_attempt proves failing item counted |
| QUEUE-09 | 76-01, 76-02 | Pass completes when all eligible searched; log cleared, pass counter increments | SATISFIED | bool(batch) guard at engine.py:201; pass-reset tests in test_search.py |
| QUEUE-10 | 76-01, 76-02 | Log pruned to currently-eligible each cycle | SATISFIED | engine.py:179 prune step; test_prioritize_batch_prune_departed_items |
| QUEUE-11 | 76-02 | Searched-log and pass counter commit only at cycle end via single save_state() | SATISFIED | Write-back after loop at each call site; no writes inside try/except; per-item loop body unchanged |

### Anti-Patterns Found

No anti-patterns found. Scan of modified files:
- No TBD/FIXME/XXX markers in triggarr/search/engine.py, triggarr/state.py
- No stub patterns (return [], return {}, empty handlers)
- No hardcoded empty data flowing to rendering
- No mutable defaults on searched_log parameter

### Human Verification Required

None. All must-haves are mechanically verifiable. The phase is a pure dispatch refactor with no new UI surface.

### Gaps Summary

No gaps. All 9 observable truths are VERIFIED against live code. The full test suite (1089 tests) passes and ruff is clean. All 11 requirement IDs (QUEUE-01 through QUEUE-11) have implementation evidence in the codebase.

---

_Verified: 2026-06-04T21:05:09Z_
_Verifier: Claude (gsd-verifier)_
