---
estimated_steps: 7
estimated_files: 6
skills_used: []
---

# T01: Run focused runtime and docs verification

Why: docs and runtime behavior are now coupled; focused verification should rerun after all code/docs edits to catch regressions before expensive full-suite checks.

Do:
1. Run the focused config-dir/state/startup tests from S01.
2. Run content checks from S02 for stale README/TODO claims.
3. If failures are found, fix locally but pause before committing or proceeding per project preference.
4. Record exact command output in the task summary.

Done when: focused runtime and docs checks pass on the final edited tree.

## Inputs

- `S01 summary`
- `S02 summary`
- `README.md`
- `TODO.md`
- `tests/test_config_dir.py`

## Expected Output

- `M001/S03/T01 summary with focused verification evidence`

## Verification

`uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py -q` and stale-content `rg` checks from S02.

## Observability Impact

Provides high-signal commands future agents can rerun when config-dir or docs drift recurs.
