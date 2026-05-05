---
id: T03
parent: S01
milestone: M001
key_files:
  - (none)
key_decisions:
  - Treated `ensure_config` exiting with code 1 after fresh default config generation as expected operational behavior and verified the subsequent startup load path instead of changing production code.
duration: 
verification_result: passed
completed_at: 2026-05-05T21:50:35.327Z
blocker_discovered: false
---

# T03: Proved a fresh absolute TRIGGARR_CONFIG_DIR creates and reloads config/state under the custom directory without touching /config.

**Proved a fresh absolute TRIGGARR_CONFIG_DIR creates and reloads config/state under the custom directory without touching /config.**

## What Happened

Ran a standalone operational proof using `TRIGGARR_CONFIG_DIR=$(mktemp -d)` before importing Triggarr modules, matching the import-time config-dir contract. The command exercised the real first-run config creation path via `ensure_config`, verified the intentional `SystemExit(1)` after writing the editable default config, then exercised the subsequent `startup(config_path)` load path from the generated config. It also wrote and reloaded default state through `save_state()`/`load_state()`, proving `state.json` is derived under the same custom directory. No production or test files were changed in this task; the proof command itself is the expected output. During command construction, the local macOS `/var` symlink resolution and first-run `ensure_config` exit were handled explicitly rather than changing runtime behavior.

## Verification

Operational command passed with exit code 0. It printed custom-directory paths for `config_path` and `state_path`, confirmed both files existed under the resolved temporary directory, confirmed `fresh_create_exit_code=1` for the expected first-run template-write behavior, confirmed `startup_loaded=True`, and included `test ! -e /config/triggarr.toml`. The focused slice suite also passed fresh: `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py -q` reported `52 passed in 0.14s`. Exact operational command used:

```bash
set -euo pipefail
start_ms=$(python3 - <<'PY'
import time
print(time.monotonic_ns() // 1_000_000)
PY
)
cfg_dir="$(mktemp -d)"
TRIGGARR_CONFIG_DIR="$cfg_dir" uv run python - <<'PY'
import asyncio
import os
from pathlib import Path

from triggarr.config import ensure_config
from triggarr.models.config import get_config_path
from triggarr.state import TriggarrState, get_state_path, load_state, save_state
from triggarr.startup import startup

config_dir = Path(os.environ["TRIGGARR_CONFIG_DIR"]).resolve()
config_path = get_config_path()
state_path = get_state_path()

assert config_dir.is_absolute(), config_dir
assert config_path == config_dir / "triggarr.toml", config_path
assert state_path == config_dir / "state.json", state_path

try:
    ensure_config(config_path)
except SystemExit as exc:
    assert exc.code == 1, exc.code
else:
    raise AssertionError("fresh ensure_config did not exit after writing default config")
assert config_path.exists(), config_path

loaded_settings = asyncio.run(startup(config_path))
assert loaded_settings is not None

state = TriggarrState(radarr={}, sonarr={}, lidarr={}, search_log=[])
save_state(state)
loaded_state = load_state()
assert loaded_state == state
assert state_path.exists(), state_path

assert not Path("/config/triggarr.toml").exists()

print(f"config_dir={config_dir}")
print(f"config_path={config_path}")
print(f"state_path={state_path}")
print(f"config_exists={config_path.exists()}")
print(f"state_exists={state_path.exists()}")
print("fresh_create_exit_code=1")
print("startup_loaded=True")
print("docker_default_config_absent=True")
PY
test ! -e /config/triggarr.toml
rm -rf "$cfg_dir"
end_ms=$(python3 - <<'PY'
import time
print(time.monotonic_ns() // 1_000_000)
PY
)
echo "duration_ms=$((end_ms - start_ms))"
```

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `TRIGGARR_CONFIG_DIR=$(mktemp -d) operational Python proof with ensure_config fresh create, startup load, save_state/load_state, and test ! -e /config/triggarr.toml` | 0 | ✅ pass | 374ms |
| 2 | `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py -q` | 0 | ✅ pass | 140ms |

## Deviations

None. The command documents the expected first-run `ensure_config` exit after default config creation, which is runtime behavior rather than a task deviation.

## Known Issues

None.

## Files Created/Modified

None.
