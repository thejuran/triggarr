# Phase 75: Drain-Timeout Config Parity & Deferred-Record Correction - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-03
**Phase:** 75-drain-timeout-config-parity-deferred-record-correction
**Areas discussed:** Parse helper, Wiring approach, Docs scope

---

## Parse helper (settings POST parse for the float field)

| Option | Description | Selected |
|--------|-------------|----------|
| Add safe_float helper | New `safe_float(value, default, min, max)` in validation.py mirroring safe_int; parse drain timeout with it (`1.0`–`3600.0`, default `60.0`). Honest float semantics. | ✓ |
| Reuse safe_int (whole seconds) | Follow `request_timeout`'s precedent (float field parsed via safe_int → whole seconds). Zero new code, but loses fractional-second precision for a new float knob. | |

**User's choice:** Add safe_float helper (Recommended)
**Notes:** The existing `request_timeout` float field is parsed via `safe_int` (a wrinkle).
We deliberately do NOT propagate that to a brand-new float knob — a dedicated `safe_float`
keeps the field's declared float type honest.

---

## Wiring approach (how the configured value + env precedence reaches the shutdown drain)

| Option | Description | Selected |
|--------|-------------|----------|
| Local resolve at shutdown start | Refactor `_read_shutdown_drain_timeout(configured)` to apply env override + `>=1.0` clamp on top of the config default; compute one local at shutdown and replace the ~6 `_SHUTDOWN_DRAIN_TIMEOUT` references with it. Precedence in one tested function. | ✓ |
| Keep module constant, refresh on settings load | Keep `_SHUTDOWN_DRAIN_TIMEOUT` global, reassign on settings (re)load; shutdown reads the mutable global. Fewer edits but re-introduces import-time/staleness footgun and mutable module state in tests. | |

**User's choice:** Local resolve at shutdown start (Recommended)
**Notes:** Matches the spec's §4.3 implementation note. Removes the import-time-staleness
footgun: configured value read from `app.state.settings` at shutdown time, where settings
is already in scope. Env override wins over config; `>=1.0` clamp applies to both sources.

---

## Docs scope (which artifacts DOCS-01 corrects) — multi-select

| Option | Description | Selected |
|--------|-------------|----------|
| STATE.md deferred table | Correct `.planning/STATE.md` Deferred Items: DEBT-07/08/03 already shipped; DEBT-06 now shipped. | ✓ |
| README / settings docs | Document the new drain-timeout config/settings-UI path + env-override precedence (README already has the env var). | ✓ |
| In-app changelog entry | Add a `CHANGELOG.md` section (rendered in the in-app changelog modal) covering drain timeout + the v2.10 recovery/counts flows. | ✓ |
| field help text (precedence note) | Inline help text on the settings.html input documenting config-default-vs-env-override precedence. | ✓ |

**User's choice:** All four surfaces selected.
**Notes:** DEBT-07/08/03 are demonstrably already shipped (config.py:128-130 + settings.html
inputs), so the deferred table is factually wrong. README already documents the env var
(README.md:86/95/140) — the correction adds the config-field path, not the env var itself.

---

## Claude's Discretion

- `safe_float` clamp ceiling beyond the agreed `3600.0`; int-like string coercion (via `float()`).
- Whether `_SHUTDOWN_DRAIN_TIMEOUT` module constant is deleted or kept unreferenced
  (functional requirement: shutdown reads config, not import-time state).
- Exact CHANGELOG.md wording/ordering; settings.html input placement; test file organization.

## Deferred Ideas

None — discussion stayed within phase scope.
