---
phase: 75-drain-timeout-config-parity-deferred-record-correction
plan: "02"
subsystem: web-settings
tags: [config-knob, settings-ui, drain-timeout, safe-float, tdd]
dependency_graph:
  requires: ["75-01"]
  provides: ["shutdown_drain_timeout GET render", "shutdown_drain_timeout POST parse", "drain-timeout settings input"]
  affects: ["triggarr/web/routes.py", "triggarr/templates/settings.html", "tests/test_web.py"]
tech_stack:
  added: []
  patterns: ["safe_float parse via config-knob round-trip loop", "settings.html numeric input with env-override help text"]
key_files:
  created: []
  modified:
    - triggarr/web/routes.py
    - triggarr/templates/settings.html
    - tests/test_web.py
decisions:
  - "Used safe_float (not safe_int) for shutdown_drain_timeout parse to preserve fractional values (e.g. 1.5)"
  - "Placement of input in settings.html: after max_consecutive_failures, before skip_unreleased"
  - "step=0.5 on input signals float nature to the browser"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-03"
  tasks_completed: 2
  files_modified: 3
---

# Phase 75 Plan 02: Settings UI Wire-Up for shutdown_drain_timeout Summary

One-liner: Wired the drain-timeout config knob through the full settings round-trip — safe_float parse in POST handler, GET render dict, numeric input with env-override help text in settings.html.

## What Was Built

- **routes.py GET render:** `"shutdown_drain_timeout": settings.general.shutdown_drain_timeout,` added to the settings render context dict adjacent to `max_consecutive_failures`.
- **routes.py POST parse:** `"shutdown_drain_timeout": safe_float(form.get("shutdown_drain_timeout"), 60.0, 1.0, 3600.0),` added to the `new_config["general"]` dict — uses `safe_float` (not `safe_int`) so fractional values survive (D-03).
- **routes.py import:** `safe_float` added to the validation import, sorted before `safe_int` per ruff I.
- **settings.html input:** `<input type="number" name="shutdown_drain_timeout" value="{{ shutdown_drain_timeout }}" min="1" max="3600" step="0.5">` added with `form="settings-form"` association, label "Shutdown Drain Timeout (seconds)", and help text documenting `TRIGGARR_SHUTDOWN_DRAIN_TIMEOUT` env-override precedence and minimum 1s (D-10).
- **tests/test_web.py:**
  - `test_save_settings_drain_timeout_round_trip`: POSTs "120.5", asserts `settings.general.shutdown_drain_timeout == 120.5`.
  - `test_save_settings_drain_timeout_clamp_floor`: POSTs "0.5", asserts result is clamped to 1.0.
  - Extended `test_settings_page_renders_new_config_fields` to assert `"shutdown_drain_timeout" in response.text`.

## TDD Gate Compliance

- RED commit (`ce567d3`): `test(75-02): add failing drain-timeout settings round-trip test` — all 3 new assertions failed before implementation.
- GREEN commit Task 1 (`05cfd1b`): `feat(75-02): parse and render shutdown_drain_timeout in settings handler` — round-trip and clamp tests pass.
- GREEN commit Task 2 (`dbc3dcb`): `feat(75-02): add drain-timeout numeric input to settings.html` — render assertion passes.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| RED | ce567d3 | test(75-02): add failing drain-timeout settings round-trip test |
| GREEN Task 1 | 05cfd1b | feat(75-02): parse and render shutdown_drain_timeout in settings handler |
| GREEN Task 2 | dbc3dcb | feat(75-02): add drain-timeout numeric input to settings.html |

## Verification

- `uv run pytest tests/test_web.py -k drain -x -q` exits 0 (2 drain tests pass)
- `uv run pytest tests/test_web.py -k "settings and render" -x -q` exits 0 (render test passes)
- `uv run pytest tests/ -x -q` exits 0 (1057 tests passing)
- `uv run ruff check triggarr/ tests/` exits 0

## Deviations from Plan

None — plan executed exactly as written. `safe_float` was already present in validation.py from Plan 75-01; `shutdown_drain_timeout` was already on `GeneralConfig` from Plan 75-01. Both dependencies confirmed before starting.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. The `{{ shutdown_drain_timeout }}` render uses a typed float from the config model (not user-controlled text); Jinja2 autoescaping is on. T-75-04 (safe_float clamp) and T-75-05 (XSS via float render) mitigations in place per threat model.

## Self-Check: PASSED

- triggarr/web/routes.py — modified (contains `safe_float`, `shutdown_drain_timeout`)
- triggarr/templates/settings.html — modified (contains `shutdown_drain_timeout` input)
- tests/test_web.py — modified (contains drain round-trip and clamp tests)
- Commits ce567d3, 05cfd1b, dbc3dcb — all present in git log
