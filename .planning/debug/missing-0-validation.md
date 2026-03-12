---
status: awaiting_human_verify
trigger: "Setting missing=0 in Radarr settings produces validation error 'value should be greater than 0', but 0 should be allowed for missing if upgrade is greater than 0."
created: 2026-03-10T00:00:00Z
updated: 2026-03-10T00:00:00Z
---

## Current Focus

hypothesis: HTML template still has min="1" on missing and cutoff count inputs, preventing 0 from being submitted
test: Check settings.html for min attribute values on those inputs
expecting: min="1" instead of min="0"
next_action: Change min="1" to min="0" on lines 111 and 116 of settings.html

## Symptoms

expected: User can set missing=0 in Radarr settings when upgrade > 0
actual: Validation rejects missing=0 with "value should be greater than 0"
errors: "value should be greater than 0"
reproduction: Go to Radarr settings, set missing=0, try to save
started: Since cross-field validation was added (v1.x era) -- the feature to allow 0 was added but the validation still blocks it

## Eliminated

(none)

## Evidence

- timestamp: 2026-03-10T00:01:00Z
  checked: triggarr/web/routes.py lines 305-306
  found: safe_int calls already use minimum=0 for search_missing_count and search_cutoff_count
  implication: Backend accepts 0 -- bug is not in route handling

- timestamp: 2026-03-10T00:01:00Z
  checked: triggarr/models/config.py lines 47-53
  found: model_validator allows missing=0 as long as cutoff > 0 (and vice versa)
  implication: Pydantic model accepts 0 -- bug is not in model validation

- timestamp: 2026-03-10T00:01:00Z
  checked: triggarr/templates/settings.html lines 108-117
  found: HTML inputs for search_missing_count (line 111) and search_cutoff_count (line 116) still have min="1"
  implication: Browser-side HTML5 validation prevents 0 from being submitted. This is the root cause.

- timestamp: 2026-03-10T00:02:00Z
  checked: .planning/quick/1-allow-0-for-missing-cutoff-counts-but-re/1-SUMMARY.md
  found: Summary claims "HTML form inputs updated to min='0'" but the actual template was never changed
  implication: The original quick task had a gap -- the HTML template edit was missed during execution

## Resolution

root_cause: HTML template settings.html has min="1" on search_missing_count and search_cutoff_count inputs (lines 111, 116), causing browser-side validation to reject 0. The backend (routes.py, config.py model validator) already supports 0, but the HTML was never updated despite the plan and summary claiming it was.
fix: Change min="1" to min="0" on lines 111 and 116 of settings.html
verification: 303 tests pass, 0 ruff violations, model validation confirms 0 accepted with positive counterpart
files_changed:
  - triggarr/templates/settings.html
