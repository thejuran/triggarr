---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T02: Run full tests and lint

Why: milestone completion requires project-level confidence, not only focused checks.

Do:
1. Run the full test suite with fail-fast.
2. Run ruff against source and tests.
3. If either fails, diagnose root cause, fix locally, then prompt the user to review before continuing as required by project preference.
4. Record command, exit code, and duration evidence in the task summary.

Done when: full test and lint verification pass on the final edited tree.

## Inputs

- `S03/T01 focused verification state`
- `pyproject.toml`
- `tests`

## Expected Output

- `M001/S03/T02 summary with full verification evidence`

## Verification

`uv run pytest tests/ -x -q` and `uv run ruff check triggarr/ tests/`

## Observability Impact

Captures baseline project health after docs/runtime reconciliation.
