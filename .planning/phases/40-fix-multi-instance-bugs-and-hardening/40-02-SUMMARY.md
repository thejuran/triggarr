---
phase: 40-fix-multi-instance-bugs-and-hardening
plan: 02
subsystem: web, config
tags: [toml, htmx, css-sanitization, atomic-write, multi-instance]

requires:
  - phase: 33-multi-instance-config-model
    provides: InstanceConfig model with tag fields, _atomic_toml_write helper
provides:
  - Instance preservation on settings save (all instances kept, not just first)
  - CSS-safe card IDs via _sanitize_card_id helper
  - Temp file cleanup on atomic write failure
  - Deduplication of manual write logic in routes.py
affects: [39-multi-instance-settings-ui]

tech-stack:
  added: []
  patterns: [re.sub sanitization for HTML IDs, contextlib.suppress for cleanup]

key-files:
  created: []
  modified:
    - triggarr/web/routes.py
    - triggarr/config.py
    - tests/test_web.py
    - tests/test_config.py

key-decisions:
  - "Preserve tag fields (missing_tag, cutoff_tag) on both edited and non-edited instances"
  - "Use re.sub with [^a-zA-Z0-9_-] pattern for card ID sanitization"
  - "Move temp file creation before try block so except can always unlink it"

patterns-established:
  - "_sanitize_card_id: Centralized HTML id/CSS selector sanitization for instance names"

requirements-completed: [BUG-04, BUG-05, BUG-06]

duration: 25min
completed: 2026-03-11
---

# Phase 40 Plan 02: Config Safety and CSS Sanitization Summary

**Fix settings save silently deleting non-first instances, sanitize CSS card IDs for special-character instance names, and clean up temp files on atomic write failure**

## Performance

- **Duration:** 25 min
- **Started:** 2026-03-12T01:04:38Z
- **Completed:** 2026-03-12T01:30:06Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Settings save now preserves all configured instances (not just the first) including tag fields
- Card IDs are sanitized via _sanitize_card_id replacing dots, hashes, spaces with hyphens
- _atomic_toml_write now cleans up temp files when serialization or replace fails
- Removed duplicate manual tempfile+replace code from routes.py, using shared _atomic_toml_write

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix settings save instance deletion and refactor to use _atomic_toml_write** - `6c51d81` (feat, from 40-01 overlap) + test updates in plan
2. **Task 2: Fix CSS injection and atomic write temp file leak** - `d92fc19` (test) + `f26f8a8` (fix)

**Plan metadata:** (this commit)

_Note: Task 1's implementation was partially completed by plan 40-01 which addressed the same BUG-05 fixes during its execution. This plan verified the implementation, updated the test for the write-failure path, and committed Task 2's changes._

## Files Created/Modified
- `triggarr/web/routes.py` - Added _sanitize_card_id, used _atomic_toml_write, preserved all instances
- `triggarr/config.py` - Added contextlib import, except block with os.unlink for temp cleanup
- `tests/test_web.py` - BUG-04 sanitization tests, BUG-05 instance preservation tests, updated write-failure test
- `tests/test_config.py` - BUG-06 temp file cleanup test, _atomic_toml_write success regression test

## Decisions Made
- Preserve tag fields (missing_tag, cutoff_tag) on both the edited first instance and all non-edited instances during settings save
- Use `re.sub(r"[^a-zA-Z0-9_-]", "-", raw)` for card ID sanitization -- covers dots, hashes, spaces, and any other special characters
- Move `tempfile.mkstemp` before the try block so the except clause always has `tmp_path` available for cleanup

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated write-failure test for new _atomic_toml_write delegation**
- **Found during:** Task 1 (verifying existing tests)
- **Issue:** test_save_settings_cleans_temp_on_replace_failure patched `routes.tempfile.NamedTemporaryFile` which no longer exists after refactor
- **Fix:** Replaced with test_save_settings_propagates_write_failure that patches `routes._atomic_toml_write`
- **Files modified:** tests/test_web.py
- **Verification:** Test passes, verifies 500 error on write failure
- **Committed in:** 6c51d81 (part of 40-01 overlap)

**2. [Rule 1 - Bug] Fixed unused import lint errors in test_web.py**
- **Found during:** Task 1 (ruff check)
- **Issue:** Removing tempfile/contextlib/tomli_w from routes.py left `os` import unused in tests; 40-01 left unused `AsyncMock, patch` import in BUG-11 test
- **Fix:** Removed unused imports
- **Files modified:** tests/test_web.py
- **Verification:** `ruff check` passes clean

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both auto-fixes necessary for correctness after refactoring. No scope creep.

## Issues Encountered
- Task 1 was already implemented by plan 40-01 (which included BUG-05 fixes as part of its BUG-03 work). Verified the implementation was correct and tests pass rather than duplicating work.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All BUG-04/05/06 fixes complete and tested
- Ready for Phase 39 multi-instance settings UI work
- No blockers

---
*Phase: 40-fix-multi-instance-bugs-and-hardening*
*Completed: 2026-03-11*
