# S01: Verify portable config directory contract

**Goal:** Prove the config directory feature is real across helper functions, startup/config loading, state path derivation, and Docker default assumptions before changing user docs.
**Demo:** After this: a temporary absolute `TRIGGARR_CONFIG_DIR` is proven through tests/startup checks to control config and state paths, and any real residual `/config` bug is fixed or documented as absent.

## Must-Haves

- `TRIGGARR_CONFIG_DIR` absolute-path behavior is covered by focused tests.
- `/config` remains the default when the env var is unset.
- Relative config-dir values fail early with a clear error.
- Any remaining hardcoded `/config` runtime bug found by audit is fixed before docs are updated.

## Proof Level

- This slice proves: Contract + integration proof using focused tests and startup/config/state path checks.

## Integration Closure

Produces a verified config-dir contract for S02 to document. S02 still needs to update public docs, and S03 still needs final full-suite/lint/UAT closure.

## Verification

- Confirms invalid path failures stay explicit and config/state write paths remain inspectable without logging secrets.

## Tasks

- [x] **T01: Audit config-dir consumers and classify path references** `est:45m`
  Why: establish the exact current behavior before editing code or docs; the existing TODO appears stale, but the runtime path needs verification beyond a superficial read.
  - Files: `triggarr/models/config.py`, `triggarr/state.py`, `triggarr/config.py`, `triggarr/startup.py`, `triggarr/__main__.py`, `triggarr/web/routes.py`, `triggarr/search/scheduler.py`, `triggarr/db.py`, `entrypoint.sh`, `Dockerfile`, `docker-compose.yml`
  - Verify: `rg -n "(/config|TRIGGARR_CONFIG_DIR|CONFIG_DIR|CONFIG_PATH|STATE_PATH|state\.json|triggarr\.toml|\.migrated)" triggarr entrypoint.sh Dockerfile docker-compose.yml README.md TODO.md` and a written classification in the task summary.

- [ ] **T02: Fill config-dir verification gaps or fix real path bugs** `est:1h`
  Why: focused tests already exist, but this task fills gaps found by T01 so path behavior is proven at the right boundary.
  - Files: `tests/test_config_dir.py`, `tests/test_state.py`, `tests/test_startup.py`, `triggarr/models/config.py`, `triggarr/state.py`, `triggarr/startup.py`, `triggarr/__main__.py`
  - Verify: `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py -q`

- [ ] **T03: Prove fresh custom config-dir startup behavior** `est:45m`
  Why: before documentation updates, prove the behavior through a realistic fresh-directory scenario instead of relying only on unit tests.
  - Files: `triggarr/__main__.py`, `triggarr/config.py`, `triggarr/state.py`, `tests/test_config_dir.py`
  - Verify: A command using `TRIGGARR_CONFIG_DIR=$(mktemp -d)` that proves generated/derived paths live under that directory, plus `test ! -e /config/triggarr.toml` if environment-safe.

## Files Likely Touched

- triggarr/models/config.py
- triggarr/state.py
- triggarr/config.py
- triggarr/startup.py
- triggarr/__main__.py
- triggarr/web/routes.py
- triggarr/search/scheduler.py
- triggarr/db.py
- entrypoint.sh
- Dockerfile
- docker-compose.yml
- tests/test_config_dir.py
- tests/test_state.py
- tests/test_startup.py
