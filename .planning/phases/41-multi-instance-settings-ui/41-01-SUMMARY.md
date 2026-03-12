---
phase: 41-multi-instance-settings-ui
plan: 01
subsystem: ui
tags: [htmx, jinja2, tailwind, fastapi, pydantic, toml, settings, multi-instance]

# Dependency graph
requires:
  - phase: 40-fix-multi-instance-bugs
    provides: "Multi-instance config model, per-instance state, tag fields"
provides:
  - "Full multi-instance settings CRUD from web UI"
  - "validate_instance_name function for instance name safety"
  - "Tag autocomplete endpoint for *arr tag datalists"
  - "Add/remove instance endpoints with proper cleanup"
  - "Accordion-based settings template with per-instance fields"
affects: [settings, config, search, scheduler]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "INSTANCE_FIELD_RE regex for {app}__{inst}__{field} form parsing"
    - "_settings_to_dict helper for SecretStr-safe serialization"
    - "details/summary accordion for multi-instance UI"

key-files:
  created: []
  modified:
    - "triggarr/web/validation.py"
    - "triggarr/web/routes.py"
    - "triggarr/templates/settings.html"
    - "tests/test_web.py"
    - "tests/test_validation.py"

key-decisions:
  - "Used double-underscore separator for form field names ({app}__{inst}__{field}) to avoid collision with single underscores in instance names"
  - "validate_instance_name rejects double underscores to protect form field parsing"
  - "Tag autocomplete uses htmx hx-get on focus with datalist, not select dropdown"
  - "Combined template rewrite with backend (Task 2 done in Task 1 since backend tests required template)"
  - "response_model=None for endpoints returning mixed HTMLResponse/RedirectResponse"
  - "_settings_to_dict extracts SecretStr values for safe TOML serialization"

patterns-established:
  - "Multi-instance form field naming: {app}__{instance}__{field}"
  - "INSTANCE_FIELD_RE regex for parsing multi-instance form data"
  - "Accordion per-instance settings with details/summary elements"

requirements-completed: [INST-05, INST-06, TAG-06]

# Metrics
duration: 11min
completed: 2026-03-12
---

# Phase 41 Plan 01: Multi-Instance Settings UI Summary

**Full multi-instance settings CRUD with tag autocomplete, add/remove instance endpoints, and accordion-based web UI replacing single-instance settings form**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-12T02:25:21Z
- **Completed:** 2026-03-12T02:36:10Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Settings page now shows ALL configured instances per app type in accordion layout (not just the first)
- Users can edit every field of every instance including missing_tag and cutoff_tag with autocomplete
- Add/remove instance endpoints with full validation, max-5 limit, and scheduler/client/state cleanup
- API keys never leaked in form HTML (masked password fields with preservation on empty submit)
- All 436 tests pass, lint clean

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `1edec41` (test)
2. **Task 1 GREEN: Implementation + template rewrite** - `f384545` (feat)

**Plan metadata:** [pending] (docs: complete plan)

_Note: Task 2 (template rewrite) was completed as part of Task 1 GREEN since the backend tests required the template to render the multi-instance structure._

## Files Created/Modified
- `triggarr/web/validation.py` - Added validate_instance_name function
- `triggarr/web/routes.py` - Refactored settings_page, save_settings; added tag_autocomplete, add_instance, remove_instance endpoints; added _settings_to_dict helper
- `triggarr/templates/settings.html` - Full rewrite: nested instance accordion, tag fields with htmx datalist, add/remove instance forms
- `tests/test_web.py` - Added multi-instance fixture, 16 new tests; updated existing tests to use new field naming convention
- `tests/test_validation.py` - Added TestValidateInstanceName class with 10 tests

## Decisions Made
- Double-underscore separator for form fields: `{app}__{inst}__{field}` avoids collision with single underscores in instance names
- validate_instance_name rejects `__` to protect the form field parsing regex
- Tag autocomplete uses htmx `hx-get` on focus with `<datalist>` for native browser autocomplete UX
- Combined template rewrite into Task 1 because backend tests needed the template to render instances
- Used `response_model=None` on add/remove endpoints since FastAPI doesn't support Union return types
- Created `_settings_to_dict` helper to safely extract SecretStr values for TOML serialization

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated existing tests to new multi-instance field naming convention**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** 12 existing tests used old single-instance field names (radarr_url, radarr_api_key, etc.) which no longer match INSTANCE_FIELD_RE
- **Fix:** Updated all test data to use new {app}__{inst}__{field} convention
- **Files modified:** tests/test_web.py
- **Verification:** All 436 tests pass
- **Committed in:** f384545 (Task 1 GREEN commit)

**2. [Rule 3 - Blocking] Combined Task 2 template rewrite into Task 1**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Backend tests require settings template to render multi-instance structure; cannot test backend without template changes
- **Fix:** Included full template rewrite as part of Task 1 GREEN phase
- **Files modified:** triggarr/templates/settings.html
- **Verification:** All tests pass including multi-instance rendering assertions
- **Committed in:** f384545 (Task 1 GREEN commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both deviations necessary for tests to pass. Template rewrite moved into Task 1 to avoid test failures. No scope creep.

## Issues Encountered
- FastAPI rejects Union return types (HTMLResponse | RedirectResponse) on route decorators -- used `response_model=None`
- ruff E501 on validation error message -- shortened message to fit 120 char limit

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Multi-instance settings CRUD fully functional
- Tag autocomplete endpoint ready for any *arr instance
- Foundation laid for any further settings UI improvements

---
*Phase: 41-multi-instance-settings-ui*
*Completed: 2026-03-12*
