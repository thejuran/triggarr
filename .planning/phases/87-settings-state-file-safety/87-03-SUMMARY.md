---
phase: 87-settings-state-file-safety
plan: 03
subsystem: state
tags: [json, loguru, atomic-write, shutil, tempfile]

# Dependency graph
requires: []
provides:
  - "load_state recovers to default state for any valid-JSON non-object root ([], 42, null, string, bool, float) instead of raising AttributeError"
  - "Both broken-file cases (non-object root, unparseable JSON) share one recovery helper (_recover_from_bad_state_file) that sets the bad file aside and logs one warning"
  - "Exactly one diagnostic copy (state.json.corrupt) is kept beside a broken state file, replaced on each new occurrence, with permissions no wider than the source"
  - "A failed set-aside (mkstemp/copy2/os.replace OSError) never blocks startup recovery and leaks no temp file or descriptor"
affects: [90-removed-instance-pending-search-lifecycle, 92-built-image-recovery-demonstration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single isinstance(data, dict) entry-point guard in load_state, before any helper that assumes dict shape (not duplicated inside _is_v22_state_format or _merge_defaults)"
    - "Shared recovery helper for both broken-file cases (parse failure and wrong shape), keeping one warning-and-reset path to test and reason about"
    - "Set-aside-before-reset via mkstemp (same dir) -> shutil.copy2 -> os.replace onto one fixed destination name, mirroring config.py's backup pattern but adding the try/except that pattern lacked"

key-files:
  created: []
  modified:
    - triggarr/state.py
    - tests/test_state.py

key-decisions:
  - "Non-object-root guard placed immediately after the JSONDecodeError/OSError except block and before _is_v22_state_format, so both broken-file branches route through the same helper (D-09)"
  - "Descriptor from tempfile.mkstemp is closed immediately after creation since it is never used for writing (shutil.copy2 does its own I/O); this removes one class of leak regardless of which later step fails"
  - "copy_succeeded tracked as a local bool to pick the D-10 warning's closing sentence (names the copy location on success, omits it on failure) without changing the helper's unconditional return of _default_state()"

patterns-established:
  - "Broken-file recovery (any shape) always goes through _recover_from_bad_state_file -- future broken-file cases should route through it rather than adding ad hoc handling"

requirements-completed: [CONSIST-03]

# Metrics
duration: 6min (commit span; context gathering and verification outside that span)
completed: 2026-11-15
---

# Phase 87 Plan 03: Non-Object State Root Recovery Summary

**`load_state` now resets to defaults with a logged warning for any valid-JSON non-object root, and both broken-file cases (bad shape, unparseable) set the bad file aside as one overwritten `state.json.corrupt` copy before resetting.**

## Performance

- **Duration:** 6 min between first and last commit (18:04:31 to 18:10:18 local); context reading and final verification took longer around that span
- **Tasks:** 2 completed (each TDD: test commit then feat/fix commit)
- **Files modified:** 2 (`triggarr/state.py`, `tests/test_state.py`)

## Accomplishments

- `load_state` no longer crashes on a valid-JSON non-object root (`[]`, `42`, `null`, a string, `true`, `1.5`, and the originally-documented `[1, 2, 3]` case) -- all recover to default state (CONSIST-03)
- Both broken-file cases (non-object root, and the existing JSONDecodeError/OSError path) now share one recovery helper, `_recover_from_bad_state_file`, so there is one warning-and-reset behavior to test and maintain (D-09)
- Every reset to defaults first sets the bad file aside as `state.json.corrupt` beside the original, replacing any earlier copy (D-08), with permissions never wider than the source (via `shutil.copy2`, which preserves mode bits) (T-87-13)
- The set-aside write goes through a same-directory temp file plus `os.replace` onto one fixed destination name, so an existing file (or symlink) at that name is replaced, not written through (T-87-14), and it can never accumulate copies across repeated corruption (T-87-15)
- A failure at `mkstemp`, `shutil.copy2`, or `os.replace` is caught, logged, and never blocks recovery; the temp descriptor is closed immediately after `mkstemp` and any leftover temp file is cleaned up in a `finally` clause, so no file or descriptor is ever leaked (D-11, T-87-16)
- The D-10 warning names the file path, the kind of data found (e.g. "a list"), that queue progress and last-run times were reset, that search history is unaffected, and -- only when the copy succeeded -- where the diagnostic copy was kept; it never echoes any value from the bad file (T-87-12)
- D-12 confirmed unchanged: `test_state_wrong_nested_type_recovers` passes unmodified, and a direct check of the planning-time cases (`{"radarr": {"X": 5}}`, `{"search_log": 7}`, `{"radarr": []}`, `{"sonarr": {"missing_cursor": 3}}`, `{}`) confirms none of them crash or change behavior

## Task Commits

Each task followed RED -> GREEN:

1. **Task 1: Non-object root recovers to defaults with the D-10 warning**
   - `d0e9849f` test(87-03): add failing tests for non-object state root
   - `ead84cb1` fix(87-03): recover from a non-object state file instead of crashing
2. **Task 2: Set the bad file aside -- exactly one copy, safe permissions, never blocks recovery**
   - `1e50b3d3` test(87-03): add failing tests for state file set-aside
   - `921dff94` feat(87-03): keep one diagnostic copy of a bad state file

No separate plan-metadata commit was requested for this plan; this SUMMARY is committed on its own per the sequential-execution instructions for this run.

## RED-phase baselines (D-01)

**Task 1 RED, baseline = original repository code (commit `18665bb7`, before any change in this plan):**
- `test_state_wrong_structure_list_recovers` -- failed: `"[1, 2, 3]"` raised `AttributeError: 'list' object has no attribute 'get'` in `_is_v22_state_format`
- `test_state_non_object_root_recovers[[]]`, `[42]`, `[null]`, `["a string"]`, `[true]`, `[1.5]` -- each failed with the same `AttributeError` (`'list'`, `'int'`, `'NoneType'`, `'str'`, `'bool'`, `'float'` object has no attribute `'get'` respectively)
- `test_state_non_object_warning_names_kind_without_contents` -- failed: `load_state` raised `AttributeError` before any warning was logged
- `test_state_wrong_nested_type_recovers` and `test_state_corrupt_warning_names_reason_without_contents` were left unchanged and continued to pass (not part of the RED set); confirmed by running the full `tests/test_state.py` suite at this baseline (36 passed)
- Full Task 1 RED run: 8 failed, 35 deselected (filter `-k "wrong_structure or non_object"`)

**Task 2 RED, baseline = post-Task-1 code (commit `ead84cb1`, before any Task 2 change to `state.py`):**
- `test_state_bad_file_set_aside_non_object` -- failed: no `state.json.corrupt` was written
- `test_state_bad_file_set_aside_unparseable` -- failed: no `state.json.corrupt` was written
- `test_state_set_aside_keeps_exactly_one_copy` -- failed: no `state.json.corrupt*` file existed to glob
- `test_state_set_aside_permissions_not_wider` -- failed: `state.json.corrupt` did not exist to `.stat()`
- `test_state_set_aside_failure_still_recovers[mkstemp]` -- failed: no WARNING line contained "set aside"
- `test_state_set_aside_failure_still_recovers[copy2]` -- failed: patching `triggarr.state.shutil.copy2` raised `AttributeError: module 'triggarr.state' has no attribute 'shutil'` (not yet imported)
- `test_state_set_aside_failure_still_recovers[replace]` -- failed: no WARNING line contained "set aside"
- `test_state_set_aside_replace_failure_keeps_previous_copy` -- **already passed** against this baseline (7 failed, 1 passed total). Recorded per the plan as an existing-passing safety guard for the new rename step, not a new RED test: Task 1's code returns default state on any broken file without touching the set-aside path at all, so a pre-existing `state.json.corrupt` holding `"OLD"` is left untouched regardless of what `os.replace` is patched to do.

All 8 new Task 1 tests and all 7 new-RED Task 2 tests pass after their respective GREEN commits; the full `tests/test_state.py` suite is 51 passed after Task 2.

## Files Created/Modified

- `triggarr/state.py` -- added `_describe_json_kind`, extended `_recover_from_bad_state_file` with the set-aside step, added the `isinstance(data, dict)` guard and the `import shutil` line
- `tests/test_state.py` -- flipped the known-crash test to a recovery test, added non-object-root, warning-content, and set-aside test coverage

## Decisions Made

None beyond what the plan already locked. The plan's "Claude's Discretion" items (warning wording, set-aside file name `state.json.corrupt`, relying on `shutil.copy2`'s mode-preservation instead of an explicit `chmod`) were resolved exactly as the plan's GREEN instructions specified.

## Deviations from Plan

None - plan executed exactly as written. All acceptance-criteria greps, the targeted test filter, the full test suite, and ruff all pass as specified in the plan's `<verification>` block.

## Known Stubs

None.

## Threat Flags

None beyond the plan's own `<threat_model>` register (T-87-11 through T-87-16), all of which are addressed by this plan's changes and covered by the tests enumerated above. No new network endpoint, auth path, or schema change was introduced.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `load_state` can no longer crash startup on any valid-JSON state file, regardless of shape.
- Phase 92 (built-image recovery demonstration) can rely on `state.json.corrupt` as the fixed diagnostic-copy name when it later restarts the built image against a non-object state file.
- Phase 90 (removed-instance pending-search lifecycle) is unaffected by this plan; it depends on Plan 87-01's `remove_instance` route, not this plan's files.

---
*Phase: 87-settings-state-file-safety*
*Completed: 2026-11-15*

## Self-Check: PASSED

- FOUND: triggarr/state.py
- FOUND: tests/test_state.py
- FOUND: .planning/phases/87-settings-state-file-safety/87-03-SUMMARY.md
- FOUND commit: d0e9849f (test: add failing tests for non-object state root)
- FOUND commit: ead84cb1 (fix: recover from a non-object state file instead of crashing)
- FOUND commit: 1e50b3d3 (test: add failing tests for state file set-aside)
- FOUND commit: 921dff94 (feat: keep one diagnostic copy of a bad state file)
- FOUND commit: d756ee0 (docs: add plan 03 execution summary)
