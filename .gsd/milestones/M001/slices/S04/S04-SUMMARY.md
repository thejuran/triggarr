---
id: S04
parent: M001
milestone: M001
provides:
  - filter_by_tag() pure function with tag accessor pattern
  - Tag filtering wired into run_radarr_cycle and run_sonarr_cycle
  - End-to-end tag-based search filtering for both Radarr and Sonarr
requires:
  - slice: S02
    provides: "Per-instance state with independent cursors"
  - slice: S03
    provides: "Tag model, get_tags(), resolve_tag_id()"
affects:
  - S06
  - S07
key_files:
  - triggarr/search/engine.py
  - tests/test_search.py
key_decisions:
  - "Tag accessor pattern uses Callable[[dict], list[int]] for Radarr vs Sonarr tag location difference"
  - "Tag fields default to empty string (search all) for backward compatibility"
  - "Tag resolution happens once per cycle (not per queue) to minimize API calls"
  - "Sonarr tag filter placed before deduplicate_to_seasons (deduped dicts lose series.tags)"
  - "Radarr filter order: filter_monitored -> filter_by_tag -> filter_unreleased_movies"
patterns_established:
  - "Tag accessor: lambda for Radarr (item['tags']), lambda for Sonarr (item['series']['tags'])"
  - "Tag resolution block: resolve once, apply per-queue with None check for fail-open"
  - "get_tags() only called when at least one tag is configured"
observability_surfaces:
  - "loguru info when tag filtering applied, warning when tag not found"
drill_down_paths:
  - .planning/phases/36-search-engine-tag-filtering/36-01-SUMMARY.md
  - .planning/phases/36-search-engine-tag-filtering/36-02-SUMMARY.md
duration: 10min
verification_result: passed
completed_at: 2026-03-11
---

# S04: Search Engine Tag Filtering

**filter_by_tag pure function and end-to-end tag filtering wired into both Radarr and Sonarr cycle functions with fail-open semantics**

## What Happened

Added InstanceConfig tag fields (missing_tag, cutoff_tag) with empty string defaults. Built filter_by_tag() pure function using Callable tag accessor pattern to handle Radarr (tags on movie) vs Sonarr (tags on series) difference. Wired tag resolution and filtering into both run_radarr_cycle and run_sonarr_cycle with correct pipeline ordering: Radarr does filter_monitored → filter_by_tag → filter_unreleased; Sonarr places tag filter before deduplicate_to_seasons. get_tags() API call is skipped entirely when both tags are empty. Fail-open: unresolved tag name proceeds without filtering. 371 tests passing, 9 new integration tests for cycle-level tag filtering.

## Verification

- 371 tests pass, lint clean
- 9 new integration tests cover: tag filtering applied, no-tag searches all, tag not found fails open, correct pipeline ordering
- Both Radarr and Sonarr cycle functions tested

## Requirements Validated

- TAG-01 — Missing queue tag filter proven by cycle integration tests
- TAG-02 — Cutoff queue tag filter proven by cycle integration tests
- TAG-03 — No-tag default behavior preserved by empty-string tests

## Deviations

None — plans executed exactly as written.

## Known Limitations

- Tag filtering works at the engine level but scheduler still uses first-enabled-instance pattern — S06 will wire per-instance scheduling

## Follow-ups

- S07: Tag not-found warning badge on dashboard (TAG-05)
- S07: Tag autocomplete in settings UI (TAG-06)

## Files Created/Modified

- `triggarr/search/engine.py` — filter_by_tag(), tag accessors, tag resolution in cycle functions
- `tests/test_search.py` — 9 integration tests for tag filtering in cycles

## Forward Intelligence

### What the next slice should know
- Tag filtering is complete at the engine level — no changes needed in S05/S06 for filtering itself
- get_tags() returns list[Tag] and is already called conditionally per cycle

### What's fragile
- Sonarr tag filter MUST stay before deduplicate_to_seasons — moving it after would silently break filtering

### Authoritative diagnostics
- test_search.py tag filtering tests are the source of truth

### What assumptions changed
- None
