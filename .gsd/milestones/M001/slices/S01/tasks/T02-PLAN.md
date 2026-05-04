---
estimated_steps: 8
estimated_files: 7
skills_used: []
---

# T02: Fill config-dir verification gaps or fix real path bugs

Why: focused tests already exist, but this task fills gaps found by T01 so path behavior is proven at the right boundary.

Do:
1. Add or adjust tests for any missing startup/config/state path behavior found in T01.
2. Preserve absolute-path validation for `TRIGGARR_CONFIG_DIR`.
3. Preserve `/config` default behavior when unset.
4. If code changes are needed, keep path injection and atomic write patterns consistent with existing modules.
5. Do not change Docker's default `/config` behavior.

Done when: focused tests prove the config-dir contract and no stale helper-only assumption remains untested.

## Inputs

- `T01 audit outcome`
- `tests/test_config_dir.py`
- `tests/test_state.py`
- `tests/test_startup.py`

## Expected Output

- `tests/test_config_dir.py`
- `tests/test_state.py`
- `tests/test_startup.py`
- `Any runtime file needed to fix a real defect`

## Verification

`uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py -q`

## Observability Impact

Keeps explicit invalid-path errors and write-path behavior testable for future agents.
