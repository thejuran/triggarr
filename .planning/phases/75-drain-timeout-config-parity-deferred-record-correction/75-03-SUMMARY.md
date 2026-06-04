---
phase: 75-drain-timeout-config-parity-deferred-record-correction
plan: "03"
subsystem: scheduler
tags: [tdd, scheduler, config, shutdown, finite-guard]
dependency_graph:
  requires: ["75-01"]
  provides: ["config-aware shutdown drain", "finite-guaranteed drain timeout"]
  affects: ["triggarr/search/scheduler.py", "tests/test_scheduler.py"]
tech_stack:
  added: ["math.isfinite guard"]
  patterns: ["config-default-with-env-override", "finite-only drain value", "local-resolve at shutdown"]
key_files:
  modified:
    - triggarr/search/scheduler.py
    - tests/test_scheduler.py
decisions:
  - "D-04: _read_shutdown_drain_timeout(configured=60.0) resolves drain from config with env override"
  - "D-05: drain local resolved from app.state.settings at shutdown time, not import-time module state"
  - "D-06: finite guard math.isfinite prevents nan/inf disabling asyncio.timeout"
  - "FLAG 1: module constant _SHUTDOWN_DRAIN_TIMEOUT retained as no-arg call so existing constant tests stay green"
  - "FLAG 2: app.state.settings confirmed bound at lifespan startup before shutdown block runs"
  - "FINDING A: separate discriminating test (7.0 distinctive, lock unheld) proves configured value reaches block"
  - "elapsed assertion widened: 1.0s drain + 100s injected = ~101s elapsed (allow 100–103 for jitter)"
metrics:
  duration_seconds: 345
  completed_date: "2026-06-04"
  tasks_completed: 2
  files_modified: 2
requirements: [CFG-04]
---

# Phase 75 Plan 03: Shutdown Drain Config Parity Summary

Config-aware, finite-guaranteed `_read_shutdown_drain_timeout(configured)` + local `drain` resolution in shutdown block, with precedence-matrix tests (incl. non-finite) and discriminating config-read test.

## What Was Built

### Task 1: Refactor `_read_shutdown_drain_timeout` (D-04, D-06)

**RED** (`test(75-03): add drain-timeout precedence-matrix tests (incl. non-finite)`):
Added 8 precedence-matrix tests for `_read_shutdown_drain_timeout(configured)`:
- env unset → configured; env overrides configured; clamp on both sources
- malformed env → configured; env nan/inf/-inf → configured (each asserting `math.isfinite`)
- non-finite configured → finite 60.0 (defense in depth)

**GREEN** (`refactor(75-03): config-default-with-env-override + finite-guaranteed drain timeout`):
- Added `import math` to scheduler.py
- Changed signature to `def _read_shutdown_drain_timeout(configured: float = 60.0) -> float`
- env unset → use `configured`; env set → `float(raw)`, fallback to `configured` on `(ValueError, TypeError)`
- `math.isfinite` guard before clamp: non-finite resolved value falls back to `configured if math.isfinite(configured) else 60.0`
- `max(value, 1.0)` clamp applies to BOTH sources; helper NEVER returns nan/inf
- Retained `_SHUTDOWN_DRAIN_TIMEOUT: float = _read_shutdown_drain_timeout()` as no-arg call (FLAG 1)

### Task 2: Local drain resolution in shutdown block (D-05, FLAG 2, FINDING A)

**RED** (`test(75-03): migrate holder-identity (1.0) + add discriminating config-read drain test (7.0)`):
- Added `GeneralConfig` to the `from triggarr.models.config import ...` line
- Migrated `test_shutdown_timeout_logs_holder_identity`: removed `monkeypatch.setattr(sched, "_SHUTDOWN_DRAIN_TIMEOUT", 0.1)`, replaced with `make_settings(general=GeneralConfig(shutdown_drain_timeout=1.0))` — 1.0 is the ge=1.0 field minimum
- Added `test_shutdown_drain_reads_configured_value`: sets 7.0 (distinctive), lock unheld, asserts `"timeout=7.0s"` in loguru capture

**GREEN** (`feat(75-03): resolve shutdown drain from config at shutdown time`):
- Added `drain = _read_shutdown_drain_timeout(app.state.settings.general.shutdown_drain_timeout)` at top of shutdown-drain block
- Replaced all 5 `_SHUTDOWN_DRAIN_TIMEOUT` references in shutdown path with `drain` (2x `t=drain` in info logs, `asyncio.timeout(drain)`, 2x `timeout=drain` in warning logs)
- Fixed elapsed assertion: with 1.0s drain + 100s injected start offset, elapsed at timeout is ~101s; widened pattern to allow 100–103s

## Verification

- `uv run pytest tests/ -x -q` → **1065 passed** (all green; 1044 baseline + 21 new tests)
- `uv run ruff check triggarr/ tests/` → **All checks passed**
- `grep -n "_SHUTDOWN_DRAIN_TIMEOUT" triggarr/search/scheduler.py` → only in module docstring, helper docstring, env-var string (line 79), constant definition (line 95), and a comment (line 102) — NOT in the shutdown drain block
- discriminating test (`test_shutdown_drain_reads_configured_value`) completes in < 1s (lock unheld → instant acquire)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Elapsed assertion needed widening after drain value change**
- **Found during:** Task 2 GREEN
- **Issue:** The original `test_shutdown_timeout_logs_holder_identity` asserted `elapsed=(99|100)\.\d` — written when `_SHUTDOWN_DRAIN_TIMEOUT=0.1` was monkeypatched so drain fired in ~0.1s. With `shutdown_drain_timeout=1.0`, the drain fires after ~1.0s, making elapsed ≈ 101s instead of ≈ 100s.
- **Fix:** Widened regex to `elapsed=(100|101|102|103)\.\d` to tolerate the 1.0s drain plus platform jitter.
- **Files modified:** `tests/test_scheduler.py`
- **Commit:** `7b209c1`

## TDD Gate Compliance

RED gate: Two separate RED commits committed before their respective GREEN commits:
1. `8621417` `test(75-03): add drain-timeout precedence-matrix tests (incl. non-finite)` — Task 1 RED
2. `9f8e2de` `test(75-03): migrate holder-identity (1.0) + add discriminating config-read drain test (7.0)` — Task 2 RED

GREEN gate:
1. `adca559` `refactor(75-03): config-default-with-env-override + finite-guaranteed drain timeout` — Task 1 GREEN
2. `7b209c1` `feat(75-03): resolve shutdown drain from config at shutdown time` — Task 2 GREEN

Both gates present in correct order. RED → GREEN sequence honored.

## Known Stubs

None.

## Threat Flags

No new threat surface beyond what was analyzed in the plan's threat model. The drain block reads `app.state.settings.general.shutdown_drain_timeout` which is:
- Bound at lifespan startup (FLAG 2 confirmed)
- Finite-bounded at the model (`allow_inf_nan=False` from 75-01)
- Additionally guarded in the helper (defense in depth)

## Self-Check: PASSED

- `triggarr/search/scheduler.py` — contains `def _read_shutdown_drain_timeout(configured: float = 60.0) -> float` ✓
- `triggarr/search/scheduler.py` — contains `drain = _read_shutdown_drain_timeout(app.state.settings.general.shutdown_drain_timeout)` ✓
- `triggarr/search/scheduler.py` — contains `asyncio.timeout(drain)` ✓
- `triggarr/search/scheduler.py` — retains `_SHUTDOWN_DRAIN_TIMEOUT: float = _read_shutdown_drain_timeout()` ✓
- `tests/test_scheduler.py` — contains `GeneralConfig` import ✓
- `tests/test_scheduler.py` — contains `test_shutdown_drain_reads_configured_value` ✓
- Commits `8621417`, `adca559`, `9f8e2de`, `7b209c1` present in worktree history ✓
