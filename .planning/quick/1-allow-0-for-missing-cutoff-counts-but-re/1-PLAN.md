---
phase: quick
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - triggarr/models/config.py
  - triggarr/web/routes.py
  - triggarr/templates/settings.html
  - tests/test_validation.py
  - tests/test_web.py
autonomous: true
requirements: [QUICK-1]

must_haves:
  truths:
    - "User can set missing count to 0 and cutoff count to a positive value (and vice versa)"
    - "User cannot save settings where both missing and cutoff are 0 for an enabled app"
    - "HTML inputs accept 0 as a valid minimum"
  artifacts:
    - path: "triggarr/models/config.py"
      provides: "ArrConfig model_validator enforcing at least one count >= 1"
      contains: "model_validator"
    - path: "triggarr/web/routes.py"
      provides: "safe_int minimum changed from 1 to 0 for count fields"
    - path: "triggarr/templates/settings.html"
      provides: "min=0 on missing and cutoff inputs"
    - path: "tests/test_validation.py"
      provides: "Updated safe_int test for 0-minimum"
    - path: "tests/test_web.py"
      provides: "Test for both-zero rejection"
  key_links:
    - from: "triggarr/web/routes.py"
      to: "triggarr/models/config.py"
      via: "Pydantic validation catches both-zero before TOML write"
      pattern: "SettingsModel\\(\\*\\*new_config\\)"
---

<objective>
Allow 0 for missing/cutoff search counts but enforce that at least one of the two must be >= 1 for each enabled app.

Purpose: Users may want to skip missing searches entirely (0) while still running cutoff searches, or vice versa. Currently the minimum is 1 for both, which forces unnecessary searches.
Output: Updated model validation, route handling, HTML inputs, and tests.
</objective>

<execution_context>
@/Users/julianamacbook/.claude/get-shit-done/workflows/execute-plan.md
@/Users/julianamacbook/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@triggarr/models/config.py
@triggarr/web/routes.py
@triggarr/templates/settings.html
@triggarr/web/validation.py
@tests/test_validation.py
@tests/test_web.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Lower minimum to 0 and add cross-field validation</name>
  <files>
    triggarr/models/config.py
    triggarr/web/routes.py
    triggarr/templates/settings.html
  </files>
  <action>
1. In `triggarr/models/config.py`:
   - Add `from pydantic import BaseModel, SecretStr, model_validator` to imports.
   - Add a `@model_validator(mode="after")` on `ArrConfig` that checks: if `self.enabled` is True, then `self.search_missing_count + self.search_cutoff_count` must be >= 1. If both are 0, raise `ValueError("At least one of search_missing_count or search_cutoff_count must be >= 1 when enabled")`. If `enabled` is False, allow any combination (including both 0).

2. In `triggarr/web/routes.py` lines 225-226:
   - Change `safe_int(form.get(f"{name}_search_missing_count"), 5, 1, 100)` to use minimum `0` instead of `1`.
   - Change `safe_int(form.get(f"{name}_search_cutoff_count"), 5, 1, 100)` to use minimum `0` instead of `1`.
   - The existing Pydantic validation block (lines 229-234) already catches ValidationError and redirects to /settings with 303 -- this will handle the both-zero case via the new model_validator. No additional route-level validation needed.

3. In `triggarr/templates/settings.html` lines 71 and 76:
   - Change `min="1"` to `min="0"` on the `search_missing_count` input.
   - Change `min="1"` to `min="0"` on the `search_cutoff_count` input.
  </action>
  <verify>
    <automated>cd /Users/julianamacbook/triggarr && uv run python -c "
from triggarr.models.config import ArrConfig
# 0 missing, positive cutoff -- should work
a = ArrConfig(enabled=True, search_missing_count=0, search_cutoff_count=5)
assert a.search_missing_count == 0
# positive missing, 0 cutoff -- should work
b = ArrConfig(enabled=True, search_missing_count=5, search_cutoff_count=0)
assert b.search_cutoff_count == 0
# both 0 disabled -- should work
c = ArrConfig(enabled=False, search_missing_count=0, search_cutoff_count=0)
# both 0 enabled -- should fail
try:
    ArrConfig(enabled=True, search_missing_count=0, search_cutoff_count=0)
    raise AssertionError('Should have raised')
except Exception as e:
    assert 'at least one' in str(e).lower() or 'At least one' in str(e)
print('All model validation checks passed')
"</automated>
  </verify>
  <done>
    - ArrConfig rejects both-zero counts when enabled=True, allows when enabled=False
    - safe_int calls in routes.py accept 0 as minimum for count fields
    - HTML inputs have min="0" for missing and cutoff counts
  </done>
</task>

<task type="auto">
  <name>Task 2: Update tests for new 0-minimum behavior</name>
  <files>
    tests/test_validation.py
    tests/test_web.py
  </files>
  <action>
1. In `tests/test_validation.py`, class `TestSafeInt`:
   - Update `test_below_minimum_clamped` (line 111-112): change the assertion to test that 0 is valid when minimum=0. Replace with: `assert safe_int("0", default=5, minimum=0, maximum=1440) == 0` (0 is now within bounds when minimum=0).
   - Add `test_negative_clamped_to_zero`: `assert safe_int("-5", default=5, minimum=0, maximum=100) == 0` to verify negatives still clamp.
   - Update `test_negative_below_minimum_clamped` (line 117-118): keep this test as-is since it tests with minimum=1, which is still a valid use case (search_interval still uses min=1).

2. In `tests/test_web.py`:
   - Add `test_save_settings_rejects_both_zero_counts` test: POST to /settings with radarr enabled, `radarr_search_missing_count=0`, `radarr_search_cutoff_count=0`, sonarr disabled with valid counts. Assert response is 303 redirect to /settings (Pydantic validation rejects it). Assert config file was NOT written (config_path should not exist since no prior successful save in this test).
   - Add `test_save_settings_accepts_zero_missing_with_positive_cutoff` test: POST to /settings with radarr enabled, `radarr_search_missing_count=0`, `radarr_search_cutoff_count=5`, sonarr disabled. Assert response is 303 redirect to /settings AND config file WAS written successfully.
  </action>
  <verify>
    <automated>cd /Users/julianamacbook/triggarr && uv run pytest tests/test_validation.py tests/test_web.py -x -q</automated>
  </verify>
  <done>
    - test_below_minimum_clamped updated for 0-minimum scenario
    - New test_negative_clamped_to_zero validates negative-to-zero clamping
    - test_save_settings_rejects_both_zero_counts confirms Pydantic validation catches both-zero
    - test_save_settings_accepts_zero_missing_with_positive_cutoff confirms 0 is accepted when other count is positive
    - All existing tests still pass (no regressions)
  </done>
</task>

</tasks>

<verification>
Run the full test suite and linter to confirm no regressions:
```bash
cd /Users/julianamacbook/triggarr && uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/
```
</verification>

<success_criteria>
- 0 is accepted as a valid value for search_missing_count and search_cutoff_count
- Both-zero for an enabled app is rejected at the Pydantic model level
- Both-zero for a disabled app is allowed
- HTML form inputs accept 0
- All tests pass including new both-zero rejection and zero-acceptance tests
- No ruff violations
</success_criteria>

<output>
After completion, create `.planning/quick/1-allow-0-for-missing-cutoff-counts-but-re/1-SUMMARY.md`
</output>
