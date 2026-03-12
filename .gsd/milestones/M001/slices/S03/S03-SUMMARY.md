---
id: S03
parent: M001
milestone: M001
provides:
  - Tag model with extra=ignore
  - ArrClient.get_tags() method for /api/v3/tag endpoint
  - resolve_tag_id(tag_name, tags) -> Optional[int] pure function
requires:
  - slice: S01
    provides: "InstanceConfig with missing_tag and cutoff_tag fields"
affects:
  - S04
  - S06
  - S07
key_files:
  - triggarr/models/arr.py
  - triggarr/clients/base.py
  - triggarr/search/engine.py
  - tests/test_clients.py
  - tests/test_search.py
key_decisions:
  - "Tag model uses extra=ignore to match GrabEvent/SystemStatus pattern"
  - "resolve_tag_id is a pure function following filter_monitored pattern"
patterns_established:
  - "Tag resolution: get_tags() returns list[Tag], resolve_tag_id converts name to ID"
  - "Pure function pattern for search filtering helpers"
observability_surfaces:
  - "loguru warning when tag name not found in *arr instance"
drill_down_paths:
  - .planning/phases/35-client-registry-tag-resolution/35-01-SUMMARY.md
duration: 3min
verification_result: passed
completed_at: 2026-03-11
---

# S03: Client Registry & Tag Resolution

**Tag model, get_tags() client method, and resolve_tag_id() pure function for tag name-to-ID resolution**

## What Happened

Added Tag BaseModel (id, label, extra=ignore) to arr.py. Added get_tags() async method to ArrClient base class that calls /api/v3/tag. Added resolve_tag_id() pure function to engine.py that finds a tag by name (case-insensitive) and returns its numeric ID, or None if not found. All tests passing.

## Verification

- Tests cover get_tags() API call, resolve_tag_id() with match/no-match/case-insensitive
- Lint clean (ruff)

## Deviations

None.

## Known Limitations

- Client registry (one client per instance) not yet implemented — S06 will wire this

## Follow-ups

- S04 uses get_tags() and resolve_tag_id() in cycle functions
- S07 uses get_tags() for tag autocomplete in settings UI

## Files Created/Modified

- `triggarr/models/arr.py` — Tag model
- `triggarr/clients/base.py` — get_tags() method
- `triggarr/search/engine.py` — resolve_tag_id() function
- `tests/test_clients.py` — get_tags() tests
- `tests/test_search.py` — resolve_tag_id() tests

## Forward Intelligence

### What the next slice should know
- resolve_tag_id returns Optional[int] — None means tag not found, should fail open

### What's fragile
- Nothing — pure function with simple contract

### Authoritative diagnostics
- test_clients.py and test_search.py cover tag resolution

### What assumptions changed
- None
