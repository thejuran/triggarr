---
id: T01
parent: S01
milestone: M001
key_files:
  - (none)
key_decisions:
  - Classified this as a no-code audit because runtime config/state/SQLite paths follow `TRIGGARR_CONFIG_DIR`; only docs/backlog text is stale.
duration: 
verification_result: passed
completed_at: 2026-05-04T00:44:44.516Z
blocker_discovered: false
---

# T01: Audited config, state, Docker, web, and SQLite path references and found no runtime hardcoded `/config` defect; the remaining issue is stale documentation/TODO text.

**Audited config, state, Docker, web, and SQLite path references and found no runtime hardcoded `/config` defect; the remaining issue is stale documentation/TODO text.**

## What Happened

The audit started from the milestone context, deferred backlog, TODO, config model, and state persistence modules. The durable project memory noted that the TODO pointer is stale and the missing plan file should not be treated as authoritative.

Path classification:

- `triggarr/models/config.py`: `get_config_dir()` reads `TRIGGARR_CONFIG_DIR`, defaults to `/config`, rejects relative paths, and derives `CONFIG_DIR` plus `CONFIG_PATH = CONFIG_DIR / "triggarr.toml"`. This is runtime-configurable behavior with an intentional Docker-compatible default. The import-time constants are explicitly documented as frozen after first import.
- `triggarr/state.py`: `get_state_path()` derives `state.json` from `get_config_dir()`, and `STATE_PATH` is similarly import-time frozen. `load_state()` and `save_state()` also accept injected paths, so tests and runtime wiring can pass explicit paths. This is runtime-configurable behavior.
- `triggarr/__main__.py` and `triggarr/startup.py`: the process imports `CONFIG_PATH` and `STATE_PATH` after environment setup and passes them into startup/lifespan. `startup()` accepts an override for tests but defaults to the env-derived config path. This is intentional runtime wiring, not a hardcoded path bug.
- `triggarr/search/scheduler.py`: `create_lifespan()` receives `state_path` and `config_path`; it loads/saves JSON state through `state_path` and derives SQLite as `state_path.parent / "triggarr.db"`. Search history therefore follows the config directory because `state_path` follows `TRIGGARR_CONFIG_DIR`. This answers the SQLite path question: the DB is tied to the state/config directory, not a separate documented location.
- `triggarr/config.py`: config generation, loading, migration, backups, and `.migrated` marker creation all operate relative to the supplied `config_path`. This is runtime-configurable behavior.
- `triggarr/web/routes.py`: settings, auth, instance add/remove, API-key, and security write paths use `request.app.state.config_path` and `request.app.state.state_path`, preserving the startup-provided location. The dashboard and dismiss-migration route use `CONFIG_DIR / ".migrated"`; in production this matches the env-derived config path, while path-injected tests patch `CONFIG_DIR`. I did not classify this as a runtime bug because production startup derives both `CONFIG_DIR` and `config_path` from the same `TRIGGARR_CONFIG_DIR` value.
- `entrypoint.sh`: `CONFIG_DIR="${TRIGGARR_CONFIG_DIR:-/config}"` controls user home, directory creation, ownership, and privilege drop home directory. This is intentional Docker default plus runtime-configurable behavior.
- `Dockerfile` and `docker-compose.yml`: `/config` appears as fallback user home, image volume, and compose volume mount. These are intentional Docker defaults and should remain backward compatible.
- `README.md` and `TODO.md`: `/config/triggarr.toml`, flat config examples, and the TODO claiming configurable config-dir work is missing are stale documentation/backlog references. These are not runtime bugs and should guide T02 documentation/backlog cleanup.

Conclusion: this is a no-code verification task. No specific hardcoded runtime path bug needs fixing before T02. T02 should focus on correcting README/TODO language so Docker `/config` remains documented as the default while standalone `TRIGGARR_CONFIG_DIR` is described as the portable config/data directory for `triggarr.toml`, `state.json`, and `triggarr.db`.

## Verification

Ran the task-specified ripgrep audit over runtime code, Docker files, README, and TODO. It completed successfully with exit code 0 and identified all targeted config/state path references for classification.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "(/config|TRIGGARR_CONFIG_DIR|CONFIG_DIR|CONFIG_PATH|STATE_PATH|state\.json|triggarr\.toml|\.migrated)" triggarr entrypoint.sh Dockerfile docker-compose.yml README.md TODO.md` | 0 | ✅ pass | 22ms |

## Deviations

None.

## Known Issues

No runtime path defect found. Stale TODO and README content still need cleanup in T02: TODO.md claims config-dir support is missing, README says all settings live in `/config/triggarr.toml`, and README still shows old flat `[radarr]` / `[sonarr]` / `[lidarr]` examples.

## Files Created/Modified

None.
