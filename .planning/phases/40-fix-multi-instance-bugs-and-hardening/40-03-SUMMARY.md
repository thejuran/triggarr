---
phase: 40-fix-multi-instance-bugs-and-hardening
plan: 03
subsystem: api, search, state
tags: [input-validation, logging, immutability, test-hygiene]

requires:
  - phase: 36-search-engine-tag-filtering
    provides: Tag resolution in cycle functions
provides:
  - Capped instance_filter (10 max) in SQL IN clause
  - Instance name length validation (64 char max)
  - tag_fetch_ok flag for distinguishing fetch failures from empty tags
  - Immutable cleanup_orphaned_instances
  - Renamed test helper (_make_test_state)
affects: [web-routes, search-engine, state-management]

tech-stack:
  added: []
  patterns: [tag_fetch_ok boolean flag for fetch-vs-empty distinction]

key-files:
  created: []
  modified:
    - triggarr/web/routes.py
    - triggarr/search/engine.py
    - triggarr/state.py
    - tests/test_web.py
    - tests/test_search.py

key-decisions:
  - "tag_fetch_ok boolean replaces 'if tags:' guard for clearer fetch-failure semantics"
  - "cleanup_orphaned_instances uses dict comprehension for immutability"
  - "Test helper renamed to _make_test_state with direct import of production symbol"

patterns-established:
  - "tag_fetch_ok: Use boolean flag to distinguish API fetch failure from empty result"
  - "Immutable state transforms: Return new dict instead of mutating input"

requirements-completed: [BUG-07, BUG-08, BUG-09, BUG-10, BUG-11]

duration: 25min
completed: 2026-03-11
---

# Phase 40 Plan 03: Input Validation and Code Hygiene Summary

**Capped SQL IN clause to 10 items, validated instance name length, distinguished tag fetch failures from empty tags, made state cleanup immutable, and renamed shadowed test helper**

## Performance

- **Duration:** 25 min
- **Started:** 2026-03-12T01:04:15Z
- **Completed:** 2026-03-12T01:29:34Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Instance filter in SQL queries capped at 10 entries to prevent unbounded IN clause
- Instance name path parameters validated at 64 chars max with 400 response
- Tag fetch failures now produce distinct log messages from "tag not found" warnings via tag_fetch_ok flag
- cleanup_orphaned_instances returns a new dict without mutating the input state
- Test helper renamed from _default_instance_state to _make_test_state, removing production symbol shadowing

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix input validation** - `af45f46` (test) + `6b79099` (feat)
2. **Task 2: Fix tag logging, state mutation, and test helper** - `83bf31c` (test) + `6de9fc5` (feat)

_TDD tasks have RED (test) + GREEN (feat) commits._

## Files Created/Modified
- `triggarr/web/routes.py` - Instance filter cap and instance_name length validation
- `triggarr/search/engine.py` - tag_fetch_ok flag in Radarr and Sonarr cycle functions
- `triggarr/state.py` - Immutable cleanup_orphaned_instances via dict comprehension
- `tests/test_web.py` - Tests for input validation (4 new tests)
- `tests/test_search.py` - Tests for tag logging, state mutation, helper rename (4 new tests); renamed ~30 call sites

## Decisions Made
- Used tag_fetch_ok boolean flag instead of checking `if tags:` -- clearer semantics for distinguishing fetch failure from empty tag list
- cleanup_orphaned_instances builds a new dict via comprehension rather than deleting from the input
- Test helper imports _default_instance_state directly from triggarr.state (no deferred import workaround needed after rename)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing test failures observed in test_web.py (test_save_settings_preserves_non_edited_instances, test_save_settings_preserves_tag_fields, test_save_settings_uses_atomic_toml_write, test_save_settings_propagates_write_failure, test_save_settings_cleans_temp_on_replace_failure) -- these reference _atomic_toml_write and multi-instance settings preservation from plans 40-01/40-02 that added tests ahead of implementation. Not caused by this plan's changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All BUG-07 through BUG-11 fixes complete
- Phase 40 hardening complete (all 3 plans done)
- Ready for next milestone planning

---
*Phase: 40-fix-multi-instance-bugs-and-hardening*
*Completed: 2026-03-11*
