---
phase: 75-drain-timeout-config-parity-deferred-record-correction
plan: "01"
subsystem: config
tags: [config, validation, tdd, security, pydantic]
dependency_graph:
  requires: []
  provides:
    - "GeneralConfig.shutdown_drain_timeout: finite-only float field, default 60.0, ge=1.0"
    - "safe_float: parse-and-clamp helper with non-finite rejection via math.isfinite"
  affects:
    - "triggarr/models/config.py (GeneralConfig schema change — additive, backward-compatible)"
    - "triggarr/web/validation.py (new helper, no existing behavior changed)"
tech_stack:
  added: []
  patterns:
    - "Field(ge=1.0, allow_inf_nan=False) — bounded finite-only Pydantic float field"
    - "math.isfinite guard before max/min clamp in safe_float"
    - "TDD RED/GREEN cycle — one RED commit + one GREEN commit per task"
key_files:
  created: []
  modified:
    - "triggarr/models/config.py"
    - "triggarr/web/validation.py"
    - "tests/test_config.py"
    - "tests/test_validation.py"
decisions:
  - "allow_inf_nan=False on shutdown_drain_timeout: ge=1.0 alone accepts +inf in pydantic v2 (verified in venv); adding allow_inf_nan=False closes the gap and defends against a TOML 'inf' unbounding the drain"
  - "No le= bound on the model: the UI form clamp (3600.0) is the practical ceiling; the model enforces only the safety floor"
  - "math.isfinite guard in safe_float placed after the try/except but before the max/min clamp: nan and inf parse without raising but survive the clamp (max(nan,1.0)==nan), so the guard must come first"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-04T02:41:28Z"
  tasks: 2
  files_changed: 4
---

# Phase 75 Plan 01: Drain-Timeout Config Field & safe_float Helper Summary

Adds the bounded, finite-only `shutdown_drain_timeout` field to `GeneralConfig` (D-01) and the `safe_float` parse-and-clamp helper to `validation.py` (D-03). Both surfaces guarantee finite values: `nan`/`inf`/`-inf` are NOT rejected by `float()` alone and survive a `max(value, 1.0)` clamp, which is the exact "typo disabling/unbounding the drain" vector that §4.2 of the design spec defends against.

## Tasks

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 (RED) | Add failing test for shutdown_drain_timeout config field | 9bfd4a6 | tests/test_config.py |
| 1 (GREEN) | Add finite-only shutdown_drain_timeout GeneralConfig field | 3d042c8 | triggarr/models/config.py |
| 2 (RED) | Add failing TestSafeFloat suite (incl. non-finite cases) | b1b31d9 | tests/test_validation.py |
| 2 (GREEN) | Add safe_float parse-and-clamp helper (rejects non-finite) | 462f621 | triggarr/web/validation.py |

## Verification

- `uv run pytest tests/test_config.py -k shutdown_drain_timeout -x -q` — 1 passed
- `uv run pytest tests/test_validation.py -k SafeFloat -x -q` — 10 passed
- `uv run pytest tests/ -x -q` — 1055 passed (71 new tests: 1 config + 10 validation + prior 984 + review-pass additions from phase 74)
- `uv run ruff check triggarr/ tests/` — all checks passed

## TDD Gate Compliance

RED/GREEN sequence honored for both tasks:
1. `test(75-01): add failing test for shutdown_drain_timeout config field` (RED — `9bfd4a6`)
2. `feat(75-01): add finite-only shutdown_drain_timeout GeneralConfig field` (GREEN — `3d042c8`)
3. `test(75-01): add failing TestSafeFloat suite (incl. non-finite cases)` (RED — `b1b31d9`)
4. `feat(75-01): add safe_float parse-and-clamp helper (rejects non-finite)` (GREEN — `462f621`)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. Both new surfaces are complete implementations with no placeholder data.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced. The `shutdown_drain_timeout` field is a pure numeric knob; `safe_float` is a pure parsing helper. STRIDE threats T-75-01/T-75-01b/T-75-02 from the plan's threat model are fully mitigated as designed.

## Self-Check: PASSED

- FOUND: .planning/phases/75-drain-timeout-config-parity-deferred-record-correction/75-01-SUMMARY.md
- FOUND: triggarr/models/config.py
- FOUND: triggarr/web/validation.py
- FOUND: tests/test_config.py
- FOUND: tests/test_validation.py
- FOUND commit 9bfd4a6 (RED test_config)
- FOUND commit 3d042c8 (GREEN config.py)
- FOUND commit b1b31d9 (RED test_validation)
- FOUND commit 462f621 (GREEN validation.py)
