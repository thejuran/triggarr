---
id: T02
parent: S01
milestone: M001
key_files:
  - tests/test_config_dir.py
  - tests/test_startup.py
key_decisions:
  - Kept Docker/default `/config` runtime behavior unchanged and filled verification gaps with boundary tests instead of changing production code.
duration: 
verification_result: mixed
completed_at: 2026-05-04T01:38:57.401Z
blocker_discovered: false
---

# T02: Added focused tests proving env-derived config, state, and SQLite paths are wired through startup and lifespan boundaries.

**Added focused tests proving env-derived config, state, and SQLite paths are wired through startup and lifespan boundaries.**

## What Happened

I preserved the runtime implementation because T01 found no hardcoded `/config` defect and the existing modules already derive paths from `TRIGGARR_CONFIG_DIR` while keeping `/config` as the unset default. I added a lifespan boundary test in `tests/test_config_dir.py` that verifies `create_lifespan()` exposes the injected config/state paths on `app.state` and initializes SQLite at `state_path.parent / "triggarr.db"`. I also added an entrypoint boundary test in `tests/test_startup.py` that sets a temporary absolute `TRIGGARR_CONFIG_DIR`, runs the real `_run()` with startup/server patched, and asserts the derived `triggarr.toml` and `state.json` paths are passed to startup and lifespan. The first verification run exposed a test bug: `_run()` imports `startup` inside the function, so patching `triggarr.__main__.startup` was invalid. I corrected the test to patch `triggarr.startup.startup`; the focused suite then passed.

## Verification

Ran the task-required focused pytest command. The first run failed due to a test patch target mismatch, then the corrected run passed all 52 tests across `tests/test_config_dir.py`, `tests/test_state.py`, and `tests/test_startup.py`. This confirms absolute-path validation and `/config` defaults remain covered, default state read/write follows the current config directory, startup derives the current config path, the module entrypoint derives both config and state paths from the env var, and lifespan derives SQLite beside the injected state path.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py -q` | 1 | ❌ fail | 220ms |
| 2 | `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py -q` | 0 | ✅ pass | 120ms |

## Deviations

None. Runtime code did not need changes because the missing coverage was filled with tests.

## Known Issues

None for the runtime config-dir contract. Stale README/TODO documentation noted by T01 remains outside this task's expected output.

## Files Created/Modified

- `tests/test_config_dir.py`
- `tests/test_startup.py`
