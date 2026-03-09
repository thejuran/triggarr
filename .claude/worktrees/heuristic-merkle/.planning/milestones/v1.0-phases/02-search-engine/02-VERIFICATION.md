---
phase: 02-search-engine
verified: 2026-02-23T22:40:00Z
status: passed
score: 6/6 success criteria verified
re_verification: false
---

# Phase 2: Search Engine Verification Report

**Phase Goal:** Fetcharr automatically cycles through wanted and cutoff-unmet items for both apps on a configurable schedule, with round-robin position persisted across restarts and Sonarr searching at season level
**Verified:** 2026-02-23T22:40:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Fetcharr triggers MoviesSearch commands for Radarr wanted and cutoff-unmet items on a configurable interval, cycling sequentially through the list | VERIFIED | `run_radarr_cycle` in `fetcharr/search/engine.py` fetches missing+cutoff, filters, slices via `slice_batch`, calls `client.search_movies([movie["id"]])`. Scheduler fires on `settings.radarr.search_interval` minutes. |
| 2 | Fetcharr triggers SeasonSearch commands for Sonarr at season level, deduplicating episode records to unique (seriesId, seasonNumber) pairs before searching | VERIFIED | `run_sonarr_cycle` calls `filter_sonarr_episodes` -> `deduplicate_to_seasons` -> `slice_batch` -> `client.search_season(season["seriesId"], season["seasonNumber"])`. Confirmed in source and tested. |
| 3 | Missing and cutoff-unmet queues are independent with separate cursors per app; advancing one does not affect the other | VERIFIED | Each cycle reads `state["radarr"]["missing_cursor"]` and `state["radarr"]["cutoff_cursor"]` independently, updates each after its own batch. `AppState` TypedDict holds both cursors. Sonarr mirrors same pattern. |
| 4 | Round-robin cursor positions survive a container restart — position is read from the state file on startup, not reset to zero | VERIFIED | `scheduler.py` calls `load_state(state_path)` at lifespan start; `save_state(state, state_path)` called after every cycle (lines 70, 78). `load_state` reads from disk; `_default_state` only used when file does not exist. |
| 5 | Unmonitored items and future air date items (Sonarr) are filtered out before being added to any search queue | VERIFIED | Radarr: `filter_monitored(missing)` before `slice_batch`. Sonarr: `filter_sonarr_episodes` checks both `monitored=True` AND `airDateUtc` in the past. 19 tests including `test_filter_sonarr_episodes_excludes_future_air_date`, `test_filter_sonarr_episodes_excludes_unmonitored` — all pass. |
| 6 | Search log entries record human-readable item names alongside timestamps, not just internal IDs | VERIFIED | `append_search_log(state, "Radarr", "missing", movie["title"])` — uses `movie["title"]`. Sonarr uses `season["display_name"]` producing "Show Title - Season N" format. Timestamp is ISO-8601 with Z suffix. Bounded at 50 entries. |

**Score:** 6/6 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `fetcharr/models/config.py` | ArrConfig with search_interval, search_missing_count, search_cutoff_count | VERIFIED | Fields present at lines 21-23 with defaults 30, 5, 5. Backward-compatible (simple attribute defaults). |
| `fetcharr/clients/radarr.py` | search_movies method posting MoviesSearch command | VERIFIED | Method at line 31-36; posts `{"name": "MoviesSearch", "movieIds": movie_ids}` to `/api/v3/command`. |
| `fetcharr/clients/sonarr.py` | search_season method posting SeasonSearch command | VERIFIED | Method at line 47-56; posts `{"name": "SeasonSearch", "seriesId": ..., "seasonNumber": ...}` to `/api/v3/command`. |
| `fetcharr/search/__init__.py` | Search subpackage marker | VERIFIED | File exists (44 bytes), serves as package marker. |
| `fetcharr/search/engine.py` | filter_monitored, slice_batch, append_search_log, deduplicate_to_seasons, filter_sonarr_episodes, run_radarr_cycle, run_sonarr_cycle | VERIFIED | All 7 exports present. Cycle functions are async coroutines. 285 lines, fully substantive. |
| `fetcharr/search/scheduler.py` | create_lifespan factory with AsyncIOScheduler | VERIFIED | Contains `AsyncIOScheduler`, `@asynccontextmanager`, interval jobs with `next_run_time=datetime.now(timezone.utc)`, `save_state` after each cycle. |
| `fetcharr/__main__.py` | FastAPI app with lifespan-managed scheduler served via uvicorn | VERIFIED | Imports `uvicorn`, `FastAPI`, `create_lifespan`; creates `FastAPI(lifespan=create_lifespan(settings, STATE_PATH))`, serves via `uvicorn.Server`. |
| `pyproject.toml` | APScheduler dependency | VERIFIED | `"apscheduler>=3.11,<4"` in dependencies list at line 17. |
| `tests/test_search.py` | 19 tests for all utility functions | VERIFIED | 19 tests collected and passed (confirmed via pytest run). Covers all 5 utility functions with edge cases. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `fetcharr/search/engine.py` | `fetcharr/state.py` | `append_search_log` modifies `state["search_log"]`; cycles read/write cursor fields | WIRED | `state["search_log"].append(entry)` at line 82; `state["radarr"]["missing_cursor"]` read/write in `run_radarr_cycle` lines 178, 191. |
| `fetcharr/clients/radarr.py` | `ArrClient.post` | `search_movies` calls `self.post` with MoviesSearch payload | WIRED | `return await self.post("/api/v3/command", json_data={"name": "MoviesSearch", ...})` at lines 33-36. |
| `fetcharr/clients/sonarr.py` | `ArrClient.post` | `search_season` calls `self.post` with SeasonSearch payload | WIRED | `return await self.post("/api/v3/command", json_data={"name": "SeasonSearch", ...})` at lines 49-55. |
| `fetcharr/search/engine.py` | `fetcharr/clients/radarr.py` | `run_radarr_cycle` calls `client.search_movies` | WIRED | `await client.search_movies([movie["id"]])` at line 182; `client.get_wanted_missing()` / `get_wanted_cutoff()` at lines 170-171. |
| `fetcharr/search/engine.py` | `fetcharr/clients/sonarr.py` | `run_sonarr_cycle` calls `client.search_season` | WIRED | `await client.search_season(season["seriesId"], season["seasonNumber"])` at line 253; fetch calls at lines 240-241. |
| `fetcharr/search/scheduler.py` | `fetcharr/search/engine.py` | Scheduler jobs call run_radarr_cycle and run_sonarr_cycle | WIRED | `state = await run_radarr_cycle(radarr_client, state, settings)` at line 69; `run_sonarr_cycle` at line 77. Both imported at line 23. |
| `fetcharr/search/scheduler.py` | `fetcharr/state.py` | Scheduler calls `save_state` after each cycle | WIRED | `save_state(state, state_path)` at lines 70 and 78, immediately after each cycle call. `load_state(state_path)` at line 46. |
| `fetcharr/__main__.py` | `fetcharr/search/scheduler.py` | FastAPI lifespan delegates to `create_lifespan` | WIRED | `from fetcharr.search.scheduler import create_lifespan` at line 11; `FastAPI(lifespan=create_lifespan(settings, STATE_PATH))` at line 34. |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SRCH-01 | 02-02 | Fetcharr fetches wanted (missing) items from Radarr | SATISFIED | `run_radarr_cycle` calls `client.get_wanted_missing()` → `/api/v3/wanted/missing`. |
| SRCH-02 | 02-02 | Fetcharr fetches cutoff unmet items from Radarr | SATISFIED | `run_radarr_cycle` calls `client.get_wanted_cutoff()` → `/api/v3/wanted/cutoff`. |
| SRCH-03 | 02-02 | Fetcharr fetches wanted (missing) items from Sonarr | SATISFIED | `run_sonarr_cycle` calls `client.get_wanted_missing()` → `/api/v3/wanted/missing?includeSeries=true`. |
| SRCH-04 | 02-02 | Fetcharr fetches cutoff unmet items from Sonarr | SATISFIED | `run_sonarr_cycle` calls `client.get_wanted_cutoff()` → `/api/v3/wanted/cutoff?includeSeries=true`. |
| SRCH-05 | 02-02 | Fetcharr cycles through items sequentially via round-robin, wrapping to start | SATISFIED | `slice_batch` implements wrap-around cursor; `new_cursor = 0` when reaching end of list. 3 wrap-related tests pass. |
| SRCH-06 | 02-02 | Sonarr searches trigger at season level using SeasonSearch command | SATISFIED | `deduplicate_to_seasons` collapses episodes → `client.search_season(seriesId, seasonNumber)` posts `SeasonSearch` command. |
| SRCH-07 | 02-02 | Missing and cutoff queues are separate per app with independent cursors | SATISFIED | `state["radarr"]["missing_cursor"]` and `state["radarr"]["cutoff_cursor"]` updated independently within each cycle function. |
| SRCH-08 | 02-03 | Round-robin cursor positions persist across container restarts | SATISFIED | `save_state` called after every cycle; `load_state` on startup reads persisted cursors. State uses atomic write-then-rename. |
| SRCH-09 | 02-01 | Unmonitored items are filtered out before adding to search queue | SATISFIED | `filter_monitored` used in `run_radarr_cycle`; `filter_sonarr_episodes` checks `monitored=True` for Sonarr. |
| SRCH-10 | 02-02 | Future air date items are filtered out of Sonarr queues | SATISFIED | `filter_sonarr_episodes` skips items where `airDateUtc` is None (TBA) or in the future. Test `test_filter_sonarr_episodes_excludes_future_air_date` passes. |
| SRCH-11 | 02-01 | Search log entries show human-readable item names, not just IDs | SATISFIED | `append_search_log(state, app, queue_type, movie["title"])` for Radarr; `season["display_name"]` ("Show - Season N") for Sonarr. |
| CONF-01 | 02-01 | User can configure number of items to search per cycle, per app (separate missing/cutoff counts) | SATISFIED | `ArrConfig.search_missing_count` and `ArrConfig.search_cutoff_count` fields; used as `settings.radarr.search_missing_count` / `search_cutoff_count` in cycle functions. |
| CONF-02 | 02-01 | User can configure search interval per app | SATISFIED | `ArrConfig.search_interval` field; used as `minutes=settings.radarr.search_interval` in `scheduler.add_job`. |

All 13 requirements (SRCH-01 through SRCH-11, CONF-01, CONF-02) are SATISFIED. No orphaned requirements found — REQUIREMENTS.md maps all 13 IDs to Phase 2, and all 13 appear across the three plans.

---

### Anti-Patterns Found

None. No TODO/FIXME/HACK/placeholder comments found in any phase files. The `return [], 0` in `slice_batch` (engine.py line 53) is the correct empty-list guard, not a stub.

---

### Human Verification Required

**1. First-run immediate search timing**

**Test:** Start Fetcharr with a valid config (both apps enabled). Observe logs within 10 seconds.
**Expected:** Both Radarr and Sonarr cycle logs appear immediately (not after 30 minutes), confirming `next_run_time=datetime.now(timezone.utc)` takes effect.
**Why human:** Cannot verify scheduler timing behavior programmatically without a running instance and live *arr endpoints.

**2. Cursor persistence across container restart**

**Test:** Start Fetcharr, let one full cycle complete, check `state.json` for non-zero cursors. Stop container, restart. Observe that the first cycle log entry matches the expected next position (not position 0).
**Expected:** State file has non-zero cursor after first cycle; on restart, cursor resumes from saved position.
**Why human:** Requires a live running instance, actual *arr API, and disk I/O across two process lifetimes.

**3. Skip-and-continue on individual search failure**

**Test:** Mock or configure one movie/season to trigger a search API error (e.g., wrong movieId). Observe that other items in the same batch still get searched.
**Expected:** Warning log for the failing item; remaining batch items succeed.
**Why human:** Requires live *arr connectivity with controlled failure injection.

---

### Summary

Phase 2 goal is fully achieved. All 6 success criteria are verified against the actual codebase:

- The search engine pipeline (fetch → filter → deduplicate → slice → search → log) is completely implemented for both Radarr (MoviesSearch) and Sonarr (SeasonSearch) in `fetcharr/search/engine.py`.
- Round-robin cursor mechanics work correctly with wrapping, and both missing/cutoff queues have independent cursors per app in the state dict.
- APScheduler drives the cycles via FastAPI lifespan (`create_lifespan` in `fetcharr/search/scheduler.py`), with immediate first-run and `save_state` called after every cycle for persistence.
- All 13 requirements are satisfied with no gaps or orphaned IDs.
- 40/40 tests pass (21 Phase 1 + 19 Phase 2), with no regressions.
- All 6 commit hashes documented in summaries (a96140f, 64115f5, c749822, aaea54f, e515c1b, 7657b30) are confirmed in the git log.

Three items flagged for human verification relate to runtime behavior (scheduling timing, cross-restart persistence, error handling) that cannot be confirmed without a live instance — they are low-risk given the clean code paths verified above.

---

_Verified: 2026-02-23T22:40:00Z_
_Verifier: Claude (gsd-verifier)_
