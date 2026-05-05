---
id: S01
parent: M001
milestone: M001
provides:
  - Verified config-dir contract for S02 documentation updates.
  - Evidence that no production hardcoded `/config` runtime defect needs fixing before docs are refreshed.
  - Clear operational semantics for fresh standalone installs using `TRIGGARR_CONFIG_DIR`.
requires:
  []
affects:
  - S02: Refresh README and project documentation
  - S03: Integrated verification and docs UAT
key_files:
  - tests/test_config_dir.py
  - tests/test_startup.py
  - .gsd/milestones/M001/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T03-SUMMARY.md
key_decisions:
  - Kept Docker/default `/config` behavior unchanged because runtime references are intentional defaults, not defects.
  - Filled verification gaps with boundary tests and operational probes rather than changing production code.
  - Treated `ensure_config()` first-run exit code 1 as expected operator-edit behavior after default config generation.
patterns_established:
  - Set `TRIGGARR_CONFIG_DIR` before importing modules with import-time path constants in tests/probes.
  - Use focused boundary tests for `create_lifespan()` and `_run()` to verify env-derived path wiring without starting a real server.
  - Use fresh temp-directory operational probes to prove config/state/SQLite co-location before writing user documentation.
observability_surfaces:
  - Focused pytest command: `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py -q`.
  - Operational path probe prints resolved custom config, state, and SQLite paths plus default/relative-path outcomes.
  - Failure mode for invalid config dir is explicit `ValueError`; first-run default generation warning + exit 1 is expected behavior.
drill_down_paths:
  - .gsd/milestones/M001/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-05-05T21:55:13.839Z
blocker_discovered: false
---

# S01: Verify portable config directory contract

**Verified that Triggarr's portable config-directory contract is implemented: absolute `TRIGGARR_CONFIG_DIR` drives config, state, and SQLite paths; `/config` remains the Docker/default fallback; relative paths fail early.**

## What Happened

S01 turned the stale configurable-config-directory TODO into verified current behavior before documentation changes. T01 audited the runtime path consumers across config, state, startup, scheduler, web routes, Docker, compose, and documentation. The audit found no production hardcoded `/config` defect: runtime config/state paths derive from `TRIGGARR_CONFIG_DIR`, SQLite is derived beside `state.json`, and Docker `/config` references are intentional defaults/backward compatibility. The remaining stale material is documentation/TODO text for S02.

T02 filled the verification gap instead of changing production runtime code. Focused tests now prove the lifespan boundary exposes injected config/state paths and initializes SQLite beside the supplied state path, and the module entrypoint derives `triggarr.toml` plus `state.json` from an absolute `TRIGGARR_CONFIG_DIR` while preserving existing default and invalid-path coverage.

T03 added the realistic fresh-directory proof: with `TRIGGARR_CONFIG_DIR=$(mktemp -d)`, `ensure_config()` writes `triggarr.toml` under that directory and intentionally exits with code 1 for first-run operator editing; state and SQLite derivation resolve to `state.json` and `triggarr.db` in the same directory. Fresh closeout verification also confirmed the env-unset default remains `/config`, relative values are rejected with the existing clear error, and this environment did not create `/config/triggarr.toml`.

Operational Readiness: the health signal for this contract is the focused pytest suite plus the operational path probe. Failure signals are explicit: relative paths raise `ValueError` during config module initialization, and first-run config generation logs a warning then exits with code 1 by design. Recovery is to set an absolute `TRIGGARR_CONFIG_DIR`, edit the generated `triggarr.toml`, and restart. Monitoring gaps: there is no separate runtime dashboard indicator for the resolved config directory, which is acceptable for this slice because the feature is a startup/path contract rather than a live service metric.

## Verification

Fresh closeout verification passed. `gsd_exec` artifact sanity check `15b534d9-6418-4e62-a788-1c93916bcbaf` exited 0 and confirmed all three task summaries exist, S01 plan checkboxes for T01/T02/T03 are checked, and the T03 summary is present. Operational config-dir contract check `26853aa3-7f44-4609-acac-8251219cf877` exited 0 and printed derived paths under a temp custom directory, `fresh_default_generation=exit_1_then_file_created`, `default_dir=/config`, `relative_dir_rejected=clear_error`, and `host_config_file_absent=/config/triggarr.toml`. Focused pytest verification `bdfcf5af-b6dd-4fa5-ab71-45bfcafceb15` exited 0 with `52 passed in 0.12s` for `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py -q`.

## Requirements Advanced

- INST-04 — reaffirmed continuity-related config startup/migration path behavior; requirement was already validated.

## Requirements Validated

- INST-04 — S01 evidence confirms config startup/default-generation paths remain controlled by the supplied config path and do not require a new runtime fix.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

Runtime production code did not require changes because the audit found the portable config-dir behavior already implemented; the slice added/used focused tests and operational probes to prove the contract instead.

## Known Limitations

No user-facing UI or health endpoint reports the resolved config directory. Documentation/TODO text remains stale until S02 updates it.

## Follow-ups

S02 should document the verified contract: absolute `TRIGGARR_CONFIG_DIR` controls `triggarr.toml`, `state.json`, and `triggarr.db`; `/config` remains the Docker default; relative values are invalid; first-run config generation writes the default config and exits for editing.

## Files Created/Modified

- `tests/test_config_dir.py` — Focused tests covering lifespan-exposed config/state paths and SQLite derivation beside the state path.
- `tests/test_startup.py` — Entrypoint boundary test covering env-derived config/state paths passed into startup/lifespan.
