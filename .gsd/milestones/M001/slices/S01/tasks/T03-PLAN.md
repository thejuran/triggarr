---
estimated_steps: 8
estimated_files: 4
skills_used: []
---

# T03: Prove fresh custom config-dir startup behavior

Why: before documentation updates, prove the behavior through a realistic fresh-directory scenario instead of relying only on unit tests.

Do:
1. Use a temporary absolute directory for `TRIGGARR_CONFIG_DIR`.
2. Exercise the real config creation/loading path in a subprocess or focused test-safe command.
3. Confirm `triggarr.toml` and derived `state.json` paths point under the custom directory.
4. Confirm nothing in this check writes to `/config`.
5. Record the exact command and outcome in the task summary.

Done when: there is command evidence that a standalone custom config dir works at the operational boundary.

## Inputs

- `T02 verified behavior`
- `triggarr/__main__.py`
- `triggarr/config.py`
- `triggarr/state.py`

## Expected Output

- `M001/S01/T03 summary with operational command evidence`
- `Optional test if the check exposes a gap worth automating`

## Verification

A command using `TRIGGARR_CONFIG_DIR=$(mktemp -d)` that proves generated/derived paths live under that directory, plus `test ! -e /config/triggarr.toml` if environment-safe.

## Observability Impact

Provides operational evidence future agents can repeat when debugging standalone installs.
