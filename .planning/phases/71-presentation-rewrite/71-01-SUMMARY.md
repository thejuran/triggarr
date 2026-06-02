---
phase: 71-presentation-rewrite
plan: "01"
subsystem: tests
tags: [tdd, red, ssrf, validation, config]
dependency_graph:
  requires: []
  provides: [RED test stubs for validate_arr_url_config and validate_url_ssrf field_validator]
  affects: [tests/test_validation.py, tests/test_config.py]
tech_stack:
  added: []
  patterns: [pytest.raises(ValidationError), tuple[bool,str] return convention, one-method-per-case class structure]
key_files:
  created: []
  modified:
    - tests/test_validation.py
    - tests/test_config.py
decisions:
  - "D-02: config-load SSRF validation is the relaxed variant (loopback/localhost permitted; cloud-metadata + link-local still blocked)"
  - "D-03: covering config-load validation test required; no existing validate_arr_url or web-form test deleted or skipped"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-02"
  tasks: 2
  files_modified: 2
---

# Phase 71 Plan 01: Config-Load SSRF Validation — RED Test Stubs Summary

**One-liner:** RED-phase test stubs for the relaxed config-load SSRF contract: loopback allowed, cloud-metadata/link-local blocked, disabled-instance and apikey-ordering cases locked.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add TestValidateArrUrlConfig RED stub to test_validation.py | bfc712d | tests/test_validation.py |
| 2 | Add InstanceConfig config-load SSRF integration RED stubs to test_config.py | 4c7b25d | tests/test_config.py |

## What Was Built

### Task 1 — tests/test_validation.py

Added `validate_arr_url_config` to the existing import block (alphabetical position, multi-line import form). Added `TestValidateArrUrlConfig` class (7 methods) immediately after `TestValidateArrUrl` closes and before `TestSafeInt`, mirroring the one-method-per-case style of the analog.

Methods: `test_empty_string_allowed`, `test_loopback_ipv4_allowed`, `test_localhost_hostname_allowed`, `test_private_192_168_allowed`, `test_cloud_metadata_ip_blocked`, `test_link_local_ip_blocked`, `test_gcp_metadata_hostname_blocked`.

**RED state confirmed:** `ImportError: cannot import name 'validate_arr_url_config'` — the function does not exist yet.

### Task 2 — tests/test_config.py

Added a clearly-commented `D-01/D-02/D-03: InstanceConfig config-load SSRF validation (relaxed variant)` section after the SEC-02 block (line 286) and before `test_multi_instance_radarr`, containing 6 module-level test functions.

Functions added:
- `test_instance_config_loopback_url_valid` — PASSES at RED (no validator blocks loopback yet)
- `test_instance_config_localhost_url_valid` — PASSES at RED
- `test_instance_config_metadata_url_raises` — FAILS RED: DID NOT RAISE
- `test_instance_config_link_local_url_raises` — FAILS RED: DID NOT RAISE
- `test_instance_config_disabled_instance_metadata_url_still_raises` — FAILS RED: DID NOT RAISE
- `test_instance_config_metadata_url_with_apikey_rejects_apikey_first` — PASSES at RED (reject_apikey_in_url already exists; apikey rejection fires on the metadata+apikey URL)

## RED State Confirmation

| Test | RED Reason | Expected |
|------|-----------|----------|
| TestValidateArrUrlConfig (all 7) | ImportError: cannot import validate_arr_url_config | Correct — function not implemented yet |
| test_instance_config_metadata_url_raises | Failed: DID NOT RAISE ValidationError | Correct — validate_url_ssrf field_validator not added yet |
| test_instance_config_link_local_url_raises | Failed: DID NOT RAISE ValidationError | Correct |
| test_instance_config_disabled_instance_metadata_url_still_raises | Failed: DID NOT RAISE ValidationError | Correct |
| test_instance_config_loopback_url_valid | PASSES | Acceptable at RED — loopback already allowed |
| test_instance_config_localhost_url_valid | PASSES | Acceptable at RED |
| test_instance_config_metadata_url_with_apikey_rejects_apikey_first | PASSES | Acceptable at RED — reject_apikey_in_url already exists |

## Existing Tests — Unchanged

- All 30 pre-existing tests in `tests/test_config.py` pass unchanged.
- `TestValidateArrUrl` class in `tests/test_validation.py` is byte-for-byte unchanged (no methods removed/renamed/skipped). Note: module collection for TestValidateArrUrl also fails at RED because the new import statement covers the whole module — this is expected and documented in the plan acceptance criteria.
- No existing test is marked skip/xfail or deleted.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Flags

None. This is a test-only plan. No new attack surface introduced.

## Self-Check: PASSED

- tests/test_validation.py contains `class TestValidateArrUrlConfig`: FOUND
- tests/test_validation.py contains `validate_arr_url_config` in import: FOUND
- tests/test_config.py contains all 6 function names: FOUND
- Commit bfc712d exists: FOUND
- Commit 4c7b25d exists: FOUND
- ruff check tests/test_validation.py tests/test_config.py: PASSED
