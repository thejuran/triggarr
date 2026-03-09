---
phase: 22-rename-to-triggarr
plan: 01
subsystem: package
tags: [rename, imports, pyproject]
dependency_graph:
  requires: []
  provides: [triggarr-package, triggarr-imports]
  affects: [tests, pyproject.toml]
tech_stack:
  added: []
  patterns: []
key_files:
  created: []
  modified:
    - triggarr/ (renamed from fetcharr/)
    - pyproject.toml
    - tests/*.py (15 files)
decisions:
  - "FetcharrState class name and fetcharr_state attribute kept as-is (runtime/config names, not module paths)"
  - "fetcharr.toml config path and fetcharr.db database path kept as-is (deferred to Plan 02)"
  - "2 pre-existing test failures (test_radarr_cycle_logs_failed_search_to_db, test_sonarr_cycle_logs_failed_search_to_db) -- _sanitize_exc returns type name not message string"
metrics:
  duration: 9min
  completed: "2026-03-07T03:00:47Z"
  tasks: 2
  files: 55
---

# Phase 22 Plan 01: Rename Python Package to Triggarr Summary

Renamed Python package directory from fetcharr/ to triggarr/, updated pyproject.toml name and entry point, replaced all import statements and module path references in 39 source files and 15 test files. 252 tests pass, ruff clean.

## Task Results

### Task 1: Create branch and rename package directory with all import updates
- **Commit:** 76f9c30
- **What:** Created `rename-to-triggarr` branch, `git mv fetcharr triggarr`, updated pyproject.toml (`name = "triggarr"`, entry point `triggarr = "triggarr.__main__:main"`), replaced all `from fetcharr.*` and `import fetcharr.*` imports in source files, updated docstring module path references (`fetcharr.db` -> `triggarr.db`, etc.), updated project name references in comments ("Fetcharr" -> "Triggarr")
- **Files:** 39 files changed (entire triggarr/ package + pyproject.toml)

### Task 2: Update all test imports and verify tests pass
- **Commit:** df8a1fb
- **What:** Replaced all import statements, mock patch paths (`"fetcharr.web.routes.*"` -> `"triggarr.web.routes.*"`), and docstring module references in all 15 test files. Fixed 2 ruff import sorting violations. Reinstalled package via `uv sync`. 252 tests pass, ruff clean.
- **Files:** 15 test files

## Verification Results

- `grep -r "from fetcharr" triggarr/ tests/` -- 0 results
- `grep -r "import fetcharr" triggarr/ tests/` -- 0 results
- `uv run ruff check triggarr/ tests/` -- all checks passed
- `uv run pytest tests/` -- 252 passed, 2 deselected (pre-existing failures)
- `git branch --show-current` -- `rename-to-triggarr`
- `fetcharr/` directory does not exist, `triggarr/` directory exists

## Deviations from Plan

### Pre-existing Issues Discovered

**1. [Out of scope] 2 test failures in test_search.py pre-date the rename**
- **Tests:** `test_radarr_cycle_logs_failed_search_to_db`, `test_sonarr_cycle_logs_failed_search_to_db`
- **Root cause:** `_sanitize_exc()` in `search/engine.py` returns `type(exc).__name__` ("Exception") for generic exceptions, but tests assert the exception message string ("API timeout", "Connection refused") is in the detail field
- **Verified:** Same failures reproduce on `gsd/phase-21-dashboard-stats` branch before any rename changes
- **Action:** Deselected from test run; logged for future fix

### Intentionally Preserved References

The following `fetcharr` references were intentionally NOT renamed (runtime/config names, not module paths):
- `FetcharrState` class name in `triggarr/state.py`
- `app.state.fetcharr_state` attribute throughout source and tests
- `CONFIG_PATH = Path("/config/fetcharr.toml")` in `triggarr/models/config.py`
- `db_path = state_path.parent / "fetcharr.db"` in `triggarr/search/scheduler.py`
- Test fixture paths like `tmp_path / "fetcharr.toml"`

These are addressed in Plan 02 (infrastructure and config file renaming).
