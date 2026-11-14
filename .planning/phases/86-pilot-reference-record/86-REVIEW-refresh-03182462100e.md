---
phase: 86-pilot-reference-record
reviewed: 2026-10-30T20:45:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - tests/test_malformed_records_client_path.py
  - tests/test_refresh_counts.py
  - triggarr/search/engine.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 86: Code Review Report

**Reviewed:** 2026-10-30T20:45:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Scope is diff `d5a4467..0318246`. The change makes Refresh counts (`refresh_radarr_counts`, `refresh_sonarr_counts`, `refresh_lidarr_counts`) fetch with `allow_non_object_records=True` and skip malformed records one at a time with `_screen_queue`, as the scheduled cycles already do. A malformed record no longer marks the whole instance disconnected.

I compared each refresh chain with its scheduled-cycle chain (`engine.py:1083-1137`, `1366-1432`, `1698-1750`). Radarr and Lidarr match stage for stage, including the `missing_monitored` adjustment. Sonarr does not. The refresh path skips `filter_monitored` before the air-date check, so it logs unmonitored episodes as malformed when the scheduled cycle does not. I confirmed this with a probe (WR-01). Counts stay correct.

The new docstrings and comments also say that `cutoff_screened` never lets a malformed record out of the helper. That is not true (WR-02).

No security issues. API keys are not logged: `_log_malformed_skip` emits only the record count and IDs. The targeted tests pass (88 passed), and `ruff` reports no problems. The convention check returned no findings.

## Warnings

### WR-01: Sonarr Refresh counts logs unmonitored episodes as malformed; the scheduled cycle does not

**File:** `triggarr/search/engine.py:2111-2115` (missing) and `2137-2141` (cutoff)
**Issue:** The scheduled cycle runs `_screen_queue` → `filter_monitored` → `_screen_queue(date_fields=("airDateUtc",))` (`engine.py:1368-1373`, `1415-1420`). Only monitored episodes get the timezone check. The refresh path skips `filter_monitored` and runs the date check on every episode. An unmonitored episode with an `airDateUtc` that has no timezone (for example `"2020-01-01T00:00:00"`) is therefore logged as malformed during Refresh counts and never during a scheduled cycle.

I confirmed this with a probe. One good episode plus one unmonitored episode with no timezone produced `Sonarr: Skipped 1 missing-queue record(s) with malformed date data (ids=[5])` from `refresh_sonarr_counts`.

This contradicts the docstring and comments ("the same as the scheduled cycle", "matching the scheduled cycle's fetch"). It also breaks `_screen_queue`'s own rule that a record the queue would never search is never counted for a field nothing reads (`engine.py:172-175`). The effect: whenever someone clicks Refresh counts, the System Logs show false warnings about records Triggarr would never search. That can send the operator after a problem that does not exist. Counts are not affected.
**Fix:** Add `filter_monitored` before the date check in both refresh chains, as the cycle does:
```python
filtered_missing = _screen_queue(missing_episodes, app_label="Sonarr", queue="missing", tally=screen_tally)
filtered_missing = filter_monitored(filtered_missing)
filtered_missing = _screen_queue(
    filtered_missing, app_label="Sonarr", queue="missing", tally=screen_tally, date_fields=("airDateUtc",)
)
filtered_missing = filter_sonarr_episodes(filtered_missing)
```
```python
cutoff_screened = _screen_queue(cutoff_episodes, app_label="Sonarr", queue="cutoff", tally=screen_tally)
filtered_cutoff = filter_monitored(cutoff_screened)
filtered_cutoff = _screen_queue(
    filtered_cutoff, app_label="Sonarr", queue="cutoff", tally=screen_tally, date_fields=("airDateUtc",)
)
```
Add a regression test: an unmonitored episode with no timezone in `airDateUtc` must produce no "Skipped" warning in `refresh_sonarr_counts`.

### WR-02: Docstrings and comments falsely say no malformed record leaves the helper

**File:** `triggarr/search/engine.py:1974-1981, 2012` (Radarr), `2131-2137, 2181` (Sonarr), `2296-2302, 2337` (Lidarr); docstrings at `1895-1896`, `2055-2056`, `2220-2221`
**Issue:** The comments say "cutoff_screened is also what the tuple returns, so a malformed record never flows out of this helper", and the docstrings now describe the second tuple item as `screened_cutoff`. But `cutoff_screened` comes from `_screen_queue(cutoff, ...)` with no checks, which removes only non-object records. A cutoff record with a non-integer `id`, non-list `tags`, a non-dict `series`/`artist`, or a non-integer `seriesId`/`seasonNumber` is still returned. The records that actually pass every check are in `filtered_cutoff`, which the code builds and then discards.

The only production caller (`triggarr/web/routes.py:1166-1173`) currently ignores the return value, so nothing breaks today. But this is an explicit safety claim on a public helper. A future caller that trusts it would get records that crash `search_movies`/`search_season`.
**Fix:** Either return the fully screened list:
```python
return (filtered_missing, filtered_cutoff if not scope.cutoff_unresolved else [], scope.cutoff_tag_id)
```
or keep `cutoff_screened` and correct the wording, for example: "non-object records removed; other per-field checks apply only to the count chain". Then add a test that pins whichever contract you choose.

## Info

### IN-01: The Radarr/Lidarr Refresh counts cutoff chain builds a list that is never used

**File:** `triggarr/search/engine.py:1979-1991` (Radarr), `2299-2313` (Lidarr)
**Issue:** `filtered_cutoff` is not written to `ist` (Radarr and Lidarr have no `cutoff_searchable`) and is not returned (WR-02). The chain used to exist only to raise on bad data. With `_screen_queue` in place, its only remaining effects are warning lines in the log and the leftover safety net. A reader cannot tell this from the code.
**Fix:** Either return `filtered_cutoff` (resolves WR-02), or add a one-line comment saying the chain runs only to log skipped records and keep the safety net.

### IN-02: The client-path refresh test sends a malformed cutoff record but checks nothing about cutoff

**File:** `tests/test_malformed_records_client_path.py:278-299`
**Issue:** `test_refresh_counts_skips_non_object_record` sends `"cutoff": [None, _GOOD[app]]` but asserts only `connected`, `unreachable_since` and `missing_eligible`. It does not check the cutoff side: Sonarr's `cutoff_searchable == 1`, the "upgrade-queue" skip log line, or the cutoff part of the returned tuple. A regression in the cutoff screening path would not be caught. No refresh test covers a release date with no timezone (Radarr `skip_unreleased`) or a non-integer `id`/`seriesId` either. Before this change, both of those disconnected the instance.
**Fix:** Assert `ist["cutoff_searchable"] == 1` for Sonarr and check the log for "upgrade-queue". Add one refresh test each for a Radarr `digitalRelease` with no timezone and a non-integer `id`.

### IN-03: Calling `monkeypatch.undo()` mid-test undoes every patch on the fixture

**File:** `tests/test_refresh_counts.py:710, 951, 1156`
**Issue:** `monkeypatch.undo()` reverts every patch made through the test's `monkeypatch` instance, including any made by fixtures that share it. No autouse fixture uses `monkeypatch` today (`tests/conftest.py:23-37`), so this is safe now. A future fixture that patches through `monkeypatch` would be undone silently halfway through these tests.
**Fix:** Use a scoped patch for the failing stage, e.g. `with monkeypatch.context() as m: m.setattr(engine, "filter_by_tag", _boom); result1 = await ...`, or `unittest.mock.patch.object` as a context manager.

## Set aside (needs ruling)

None.

---

_Reviewed: 2026-10-30T20:45:00Z_
_Reviewer: Claude (bm-code-reviewer)_
_Depth: standard_
