---
status: awaiting_human_verify
trigger: "Downloads are being marked as complete (false completions) when they haven't actually finished. Since v2.0 launched closed-loop tracking — it never worked correctly."
created: 2026-03-09T00:00:00Z
updated: 2026-03-09T00:02:00Z
---

## Current Focus

hypothesis: CONFIRMED -- get_grab_history uses wrong API endpoint and wrong eventType format
test: All 303 tests pass, linting clean
expecting: User deploys and confirms tracking no longer produces false completions
next_action: Await human verification in real environment

## Symptoms

expected: Closed-loop download tracking accurately reflects real download state in Radarr/Sonarr
actual: Downloads are marked complete (false completions) when they're not actually done
errors: No error messages — behavior is silently wrong
reproduction: Trigger any search — false completions happen every time
started: Since v2.0 launch — never worked correctly

## Eliminated

## Evidence

- timestamp: 2026-03-09T00:00:30Z
  checked: correlation.py correlate_grabs() logic
  found: Window filtering logic is correct (grab_time >= search_time AND grab_time <= search_time + window). Would correctly filter per-item grabs.
  implication: The correlation logic itself is sound; problem is upstream in the data it receives.

- timestamp: 2026-03-09T00:00:45Z
  checked: radarr.py and sonarr.py get_grab_history methods
  found: Both use get_paginated("/api/v3/history") with movieId/seriesId as extra_params and eventType=1 (integer). The /api/v3/history is the GENERAL history endpoint, not per-item.
  implication: The wrong endpoint is being used. Per-item history endpoints are /api/v3/history/movie (Radarr) and /api/v3/history/series (Sonarr). The general endpoint likely ignores movieId/seriesId params and returns ALL history.

- timestamp: 2026-03-09T00:00:50Z
  checked: pyarr library documentation (authoritative Python Radarr/Sonarr wrapper)
  found: pyarr uses separate methods: get_movie_history(id) for per-movie history, which hits a different endpoint than get_history() which hits the general paginated endpoint. eventType uses string values like "grabbed", not integer 1.
  implication: Confirms that (1) per-item history is a separate endpoint and (2) eventType should be a string.

- timestamp: 2026-03-09T00:00:55Z
  checked: GrabEvent model and test mocking pattern
  found: All tests mock get_grab_history() return values, never hitting real API. Tests pass but don't validate that the API call returns correct data.
  implication: The bug was never caught by tests because mocking bypasses the actual API call.

- timestamp: 2026-03-09T00:01:30Z
  checked: Fix applied, test suite run
  found: All 303 tests pass, ruff linting clean. Tests updated to validate correct endpoint paths and param formats.
  implication: Fix is mechanically sound.

## Resolution

root_cause: Two bugs in get_grab_history() methods in both radarr.py and sonarr.py: (1) Wrong API endpoint -- using /api/v3/history (general, paginated) instead of /api/v3/history/movie or /api/v3/history/series (per-item, non-paginated). The general endpoint ignores movieId/seriesId parameters and returns ALL grab history across ALL items. (2) Wrong eventType format -- passing integer 1 instead of string "grabbed". Combined effect: tracking sees ALL grabs from ALL items, causing any search to be falsely correlated with unrelated grabs within the time window.
fix: (1) Added get_json_list() method to ArrClient base class for non-paginated endpoints. (2) Changed RadarrClient.get_grab_history to use /api/v3/history/movie with movieId param and eventType="grabbed". (3) Changed SonarrClient.get_grab_history to use /api/v3/history/series with seriesId param and eventType="grabbed". (4) Updated all client tests to use flat JSON array responses (matching real API format) and validate correct endpoint paths + param formats.
verification: 303 tests pass, ruff clean
files_changed:
  - triggarr/clients/base.py
  - triggarr/clients/radarr.py
  - triggarr/clients/sonarr.py
  - tests/test_clients.py
