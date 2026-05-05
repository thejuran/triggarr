# S01: Verify portable config directory contract — UAT

**Milestone:** M001
**Written:** 2026-05-05T21:55:13.839Z

# UAT: Portable Config Directory Contract

## UAT Type
Operational/developer acceptance test for startup path derivation and focused regression coverage. This UAT verifies local process behavior without live Radarr/Sonarr servers.

## Preconditions
- Repository dependencies are installed with `uv sync --extra dev` or equivalent.
- The commands run from the repository root.
- No production secrets are required.
- If `/config/triggarr.toml` already exists on a developer machine, treat the `/config` absence check as environment-specific and verify it was not modified by the custom-dir test.

## Test Case 1 — Fresh absolute custom directory drives generated config and derived data paths
1. Create a temp directory: `cfg_dir=$(mktemp -d)`.
2. Run a Python probe with `TRIGGARR_CONFIG_DIR="$cfg_dir"` that imports `CONFIG_PATH`, `get_config_dir()`, and `get_state_path()` after the env var is set.
3. Call `ensure_config(CONFIG_PATH)` and capture `SystemExit`.
4. Assert `get_config_dir() == Path(cfg_dir).resolve()`.
5. Assert `CONFIG_PATH == Path(cfg_dir) / "triggarr.toml"` and the file exists after `ensure_config()`.
6. Assert the first-run `SystemExit` code is `1`, because Triggarr intentionally stops after generating a default config for operator editing.
7. Assert `get_state_path() == Path(cfg_dir) / "state.json"`.
8. Assert the SQLite path derived as `get_state_path().parent / "triggarr.db"` equals `Path(cfg_dir) / "triggarr.db"`.

Expected outcome: config, state, and SQLite paths all live under the temp directory; first-run config generation exits 1 by design; no path resolves to `/config`.

## Test Case 2 — Env-unset default remains Docker-compatible
1. Run a fresh Python process with `TRIGGARR_CONFIG_DIR` unset.
2. Import `get_config_dir()`.
3. Assert `get_config_dir() == Path('/config')`.

Expected outcome: Docker/default behavior is unchanged.

## Test Case 3 — Relative config directory fails early
1. Run a fresh Python process with `TRIGGARR_CONFIG_DIR=relative`.
2. Import `triggarr.models.config`.
3. Capture the raised exception.
4. Assert it is a `ValueError` and the message contains `absolute path`.

Expected outcome: relative config-dir values are rejected before startup continues, with a clear error.

## Test Case 4 — Focused regression suite
1. Run `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py -q`.
2. Confirm all tests pass.

Expected outcome: 52 focused tests pass, covering config-dir validation, default behavior, state path derivation, startup path wiring, and lifespan/SQLite path initialization.

## Edge Cases Covered
- Import-time path constants are only trusted after the environment is set before import.
- Fresh config generation intentionally stops the process after writing the default file.
- Docker `/config` references are preserved as defaults, not treated as runtime defects.
- `/config/triggarr.toml` is not created by the custom-directory operational check in this environment.

## Not Proven By This UAT
- Public README/TODO documentation accuracy; that is S02.
- Full project tests, lint, Docker build, and user documentation review; those are S03 milestone-level closure checks.
- Live Radarr/Sonarr connectivity or scheduler behavior against real services.
- Performance under load or behavior on non-POSIX filesystems.
