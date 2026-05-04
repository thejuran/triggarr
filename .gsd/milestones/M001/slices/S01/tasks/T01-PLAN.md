---
estimated_steps: 7
estimated_files: 11
skills_used: []
---

# T01: Audit config-dir consumers and classify path references

Why: establish the exact current behavior before editing code or docs; the existing TODO appears stale, but the runtime path needs verification beyond a superficial read.

Do:
1. Audit every non-test `/config`, `CONFIG_DIR`, `CONFIG_PATH`, `STATE_PATH`, `.migrated`, and database path reference.
2. Classify each as intentional Docker default, runtime-configurable behavior, or potential bug.
3. Check whether SQLite/search-history data path is tied to config dir or another documented location.
4. Record the audit outcome in the task summary and use it to guide T02.

Done when: the task summary identifies whether this is a no-code verification task or whether specific hardcoded path bugs need fixing.

## Inputs

- `.gsd/milestones/M001/M001-CONTEXT.md`
- `.gsd/DEFERRED-BACKLOG.md`
- `TODO.md`
- `triggarr/models/config.py`
- `triggarr/state.py`

## Expected Output

- `M001/S01/T01 summary of config path audit`
- `Optional code changes only if a real runtime path defect is found`

## Verification

`rg -n "(/config|TRIGGARR_CONFIG_DIR|CONFIG_DIR|CONFIG_PATH|STATE_PATH|state\.json|triggarr\.toml|\.migrated)" triggarr entrypoint.sh Dockerfile docker-compose.yml README.md TODO.md` and a written classification in the task summary.

## Observability Impact

Improves future diagnostics by distinguishing intentional defaults from configurable runtime paths.
