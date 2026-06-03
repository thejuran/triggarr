---
phase: 71-presentation-rewrite
plan: "02"
subsystem: validation / config-model
tags: [ssrf, security, pydantic, config-load, tdd-green]
dependency_graph:
  requires: ["71-01"]
  provides: ["validate_arr_url_config", "InstanceConfig.validate_url_ssrf"]
  affects: ["triggarr/web/validation.py", "triggarr/models/config.py"]
tech_stack:
  added: []
  patterns:
    - "validate_arr_url_config — sibling SSRF validator (loopback-relaxed)"
    - "validate_url_ssrf — Pydantic v2 @field_validator with local import to avoid circular"
key_files:
  created: []
  modified:
    - triggarr/web/validation.py
    - triggarr/models/config.py
decisions:
  - "Loopback IP literals (127.0.0.1, ::1) PERMITTED at config load (D-02 relaxed variant; same-host homelab pattern). Only link-local/unspecified/multicast IP literals + BLOCKED_HOSTS metadata hosts remain blocked."
  - "local import `from triggarr.web.validation import validate_arr_url_config` inside validate_url_ssrf to avoid module-level circular import"
  - "validate_url_ssrf defined AFTER reject_apikey_in_url so Pydantic v2 definition-order guarantee preserves apikey= rejection firing first (T-71-01b)"
  - "Field validator unconditional — disabled instances with metadata/link-local URL still rejected at startup (intended hardening)"
metrics:
  duration: "~5 minutes"
  completed: "2026-06-02"
  tasks: 2
  files: 2
---

# Phase 71 Plan 02: Config-load SSRF Validation (TDD GREEN) Summary

Implemented the TDD GREEN phase for config-load SSRF validation (D-01/D-02): added `validate_arr_url_config()` (loopback-relaxed variant) to `validation.py` and wired it via a `validate_url_ssrf` `@field_validator` on `InstanceConfig`.

## Precise Net-Behavior Statement (for plans 05/06 to quote verbatim)

"Link-local / unspecified / multicast IP literals, and known cloud-metadata hostnames/IPs are blocked BOTH at config load (triggarr.toml at startup) AND via the web settings form. Loopback IP literals (127.0.0.1, ::1) are PERMITTED at config load (relaxed variant for same-host *arr) and blocked ONLY by the web settings form. The DNS name `localhost` is a hostname, not an IP literal, so it is NOT resolved at validation time and is PERMITTED in BOTH paths (config load and web form) — like any other unresolved DNS hostname. Arbitrary DNS hostnames are NOT resolved at validation time and remain an accepted residual risk (DNS rebinding); network-layer egress controls are the mitigation. Config-load validation applies regardless of `enabled` — no loopback/private-LAN/localhost deployment breaks, but a configured-but-unsafe URL (link-local/metadata/non-http/malformed) will now fail at startup even if the instance is disabled."

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Add `validate_arr_url_config()` to `triggarr/web/validation.py` | `14eecb5` |
| 2 | Add `validate_url_ssrf` `@field_validator` to `InstanceConfig` | `9be610a` |

## Implementation Details

### Task 1 — `validate_arr_url_config()` in `triggarr/web/validation.py`

Placed immediately after `validate_arr_url` closes (~line 108), before `safe_int`. The function is a direct copy of `validate_arr_url` with two `is_loopback` checks removed:
- `addr.is_loopback` removed from the direct-address blocked check
- `mapped.is_loopback` removed from the IPv4-mapped IPv6 blocked check

All other logic is verbatim: scheme allow-list, BLOCKED_HOSTS check, link-local/unspecified/multicast blocking, `_BLOCKED_NETWORKS` membership check, and the `except ValueError: pass` DNS fall-through so "localhost" and arbitrary DNS names are accepted without resolution.

Verification: `grep -n is_loopback validation.py` returns only lines 88 and 95 (inside `validate_arr_url` only — the new function has zero occurrences).

### Task 2 — `validate_url_ssrf` in `triggarr/models/config.py`

Added after `reject_apikey_in_url` (Pydantic v2 runs same-field validators in definition order). Uses a local import inside the validator body to avoid a circular import at module level (`web.validation` imports nothing from `models`). Validates the `url` field unconditionally — no branch on `enabled`.

## Verification Results

- `uv run pytest tests/test_validation.py::TestValidateArrUrlConfig -q`: 7 passed
- `uv run pytest tests/test_validation.py::TestValidateArrUrl -q`: 25 passed (strict path unchanged)
- `uv run pytest tests/test_config.py tests/test_validation.py -q`: 138 passed
- `uv run pytest tests/ -x -q`: **982 passed** (965 pre-existing + 17 new from plan 71-01)
- `uv run ruff check triggarr/ tests/`: All checks passed

## Deviations from Plan

None — plan executed exactly as written.

## TDD Gate Compliance

- RED gate: Plan 71-01 committed failing tests (ImportError + DID NOT RAISE) — verified before implementing
- GREEN gate: Tasks 1 and 2 committed as `feat(71-02): ...` after tests turned green
- No REFACTOR step needed (code was clean as written)

## Known Stubs

None.

## Threat Flags

None. The new surface (validate_url_ssrf field_validator on InstanceConfig.url) is the mitigated threat T-71-01 from the plan's threat model. No additional unplanned security surface introduced.

## Self-Check: PASSED

- `triggarr/web/validation.py` contains `def validate_arr_url_config` — FOUND
- `triggarr/models/config.py` contains `def validate_url_ssrf` — FOUND
- Commit `14eecb5` exists — FOUND
- Commit `9be610a` exists — FOUND
- 982 tests pass, ruff clean — VERIFIED
