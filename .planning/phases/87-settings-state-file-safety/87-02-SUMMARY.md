---
phase: 87-settings-state-file-safety
plan: 02
subsystem: ui
tags: [htmx, jinja2, fastapi, tailwind]

# Dependency graph
requires:
  - phase: 87-01
    provides: "_removal_failed_response (D-05 fixed wording, htmx-200/direct-500 split, no HX-Redirect on failure) and the read-under-lock/write/swap reorder of remove_instance"
provides:
  - "settings.html Remove button retargeted from hx-target=\"body\" hx-swap=\"outerHTML\" to hx-target=\"next .remove-error\" hx-swap=\"innerHTML\", so a failed removal's response swaps only that instance row's own error slot"
  - "a row-local, empty, aria-live=\"polite\" .remove-error span inside each instance's <summary>, visible even when the row is collapsed"
  - "test_no_new_body_swap_html_targets now pins zero hx-target=body/html occurrences in triggarr/templates/ (was exactly one, the old Remove button)"
  - "test_settings_remove_button_targets_row_error_slot proving the per-row wiring (button retarget + slot placement + empty-on-load) against a real multi-instance render"
  - "MAINTENANCE.md records: the D-13 settings-writer audit result (remove_instance was the only outlier, already fixed), the D-14 Save-Settings/Add-Instance friendly-error gap, the UTF-8 UnicodeDecodeError load_state crash, and the add_instance/save_settings pre-lock settings snapshot (lost-update risk) -- all four for an owner decision, none fixed in this plan"
affects: [90]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "row-scoped htmx error slot via hx-target=\"next .selector\" + hx-swap=\"innerHTML\", placed inside a collapsible <summary> so it stays visible when the row is collapsed"

key-files:
  created: []
  modified:
    - triggarr/templates/settings.html
    - tests/test_web.py
    - .planning/backlog/MAINTENANCE.md

key-decisions:
  - "Kept the existing text-red-400/text-sm classes already used on the Remove button itself (rather than security_password.html's text-red-500) so the error message visually matches the button it's attached to; all required classes (w-full, flex-wrap, gap-2, text-red-400, text-sm) already existed in output.css, so no Tailwind rebuild was needed"
  - "Used a <span> (not a <div>) for the error slot because <summary> permits only phrasing content"

requirements-completed: [CONSIST-02]

# Metrics
duration: ~15min
completed: 2026-11-15
---

# Phase 87 Plan 02: Row-Local Removal Error Display Summary

**Retargeted the instance Remove button from a full-body swap to a row-local `.remove-error` slot (D-04/D-06), tightened the SEC-01 body-swap guard test to zero occurrences, and recorded the D-13 audit plus three deferred findings in MAINTENANCE.md.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-11-15T23:08:00Z (approx)
- **Completed:** 2026-11-15T23:22:15Z
- **Tasks:** 2
- **Files modified:** 3 (`triggarr/templates/settings.html`, `tests/test_web.py`, `.planning/backlog/MAINTENANCE.md`)

## Accomplishments

- `settings.html`'s instance Remove button no longer targets `hx-target="body" hx-swap="outerHTML"`. It now targets `hx-target="next .remove-error" hx-swap="innerHTML"`, an empty, `aria-live="polite"` span placed immediately after the button inside the same `<summary>`. On a failed removal, 87-01's `_removal_failed_response` 200 body swaps into that one span only -- the rest of the Settings page, including any unsaved edits in other instance rows, is untouched (D-04). The slot has no timer and no close control, so it persists until the next Remove click on that row (which replaces it via the same `innerHTML` swap) or a page reload (D-06). The successful path is unchanged: htmx still gets `HX-Redirect` (no body/html swap, so no stale-CSP-nonce risk, SEC-01), and a direct POST still gets 303.
- `summary`'s class gained `flex-wrap` and `gap-2` so the row-local message wraps onto its own line under the instance name and button rather than overflowing the header row.
- `test_no_new_body_swap_html_targets` now asserts `len(matches) == 0` (previously exactly 1, naming the old Remove button) and the stale `matches[0]`-indexing assertion was removed entirely -- it would have raised `IndexError` once the expected count dropped to zero. The docstring was rewritten to state the new invariant: no template uses `hx-target="body"`/`"html"` any more, and any future one must pair with `HX-Redirect` or a non-script-bearing partial.
- A new render test, `test_settings_remove_button_targets_row_error_slot`, proves against the real `multi_instance_app` fixture (3 configured instances, computed via `sum(len(getattr(settings, app)) for app in APP_TYPES)`, not hard-coded) that: every instance row's Remove button carries the new `hx-target`; every row has exactly one `.remove-error` slot, empty in the rendered HTML; and each slot appears after its own button and before that row's closing `</summary>`.
- `.planning/backlog/MAINTENANCE.md` now records four findings under "Small follow-ups," each tagged `(Phase 87, 2026-11-15)`: (1) the D-13 re-audit of every settings-writing route in `routes.py` with file:line evidence, confirming `remove_instance` was the only route that mutated live settings before writing (already fixed in Phase 87) and that the other seven routes already write before swapping; (2) the D-14 note that a failed Save Settings still shows a raw server-error page and a failed Add Instance shows a bare unstyled error page, pointing at the UI Redesign milestone; (3) a reproduced finding that a non-UTF-8 `state.json` makes `load_state` raise an uncaught `UnicodeDecodeError` (outside CONSIST-03's valid-JSON scope); (4) a finding that `add_instance` and `save_settings` both read `request.app.state.settings` before taking `search_lock`, a lost-update risk with routes.py line evidence for the read and the lock in each. All four are recorded for an owner decision and not fixed in this plan.

## Task Commits

Each task's RED/GREEN steps were committed atomically:

1. **Task 1: Row-local error slot and retargeted Remove button (D-04, D-06)**
   - `95176264` test(87-02): add failing tests for row-local removal error slot
   - `76094beb` feat(87-02): show failed-removal message on the instance row
2. **Task 2: Record the D-13 audit, the D-14 follow-up and two planning-time findings in MAINTENANCE.md**
   - `f0e29d87` docs(87-02): record settings-writer audit and follow-ups (no code change; verified via `git diff --stat HEAD~1` showing only the MAINTENANCE.md file)

## Per-Test Pre-Fix Outcomes (RED evidence)

Ran against the current (unfixed) template before the GREEN commit:

| Test | Pre-fix outcome |
|------|------------------|
| `test_settings_remove_button_targets_row_error_slot` | FAILED -- `assert 0 == 3`: `hx-target="next .remove-error"` did not exist anywhere in the rendered page (the button still used `hx-target="body"`). |
| `test_no_new_body_swap_html_targets` | FAILED (readably) -- `AssertionError: ... Found 1: ['.../settings.html:167']`, not `IndexError`. The old second assertion (`matches[0]`) was removed in the same RED commit, so there was nothing left to raise an index error once the count assertion's expectation changed to 0. |

Both tests passed after the GREEN template change; the full `uv run pytest tests/test_web.py -k "remove_instance or body_swap or remove_button or settings" -x -q` run (57 tests) passed, and the full suite (3310 passed, 1 pre-existing skip) and `uv run ruff check triggarr/ tests/` ("All checks passed!") were re-run at the end of the plan.

## Files Created/Modified

- `triggarr/templates/settings.html` -- instance `<summary>` gained `flex-wrap gap-2`; Remove button's `hx-target`/`hx-swap` changed; new `<span class="remove-error w-full text-red-400 text-sm" aria-live="polite"></span>` added after the button, inside the same `<summary>`.
- `tests/test_web.py` -- added `test_settings_remove_button_targets_row_error_slot`; rewrote `test_no_new_body_swap_html_targets`'s assertion and docstring; added `APP_TYPES` to the existing `triggarr.models.config` import line.
- `.planning/backlog/MAINTENANCE.md` -- header date bumped to 2026-11-15; four new bullets added under "Small follow-ups" (D-13 audit, D-14 follow-up, UTF-8 crash finding, pre-lock snapshot finding).

## Decisions Made

- Re-verified the D-13 audit against current code (not just RESEARCH.md's prior pass) per the plan's Task 2 instruction, confirming every route's file:line evidence directly before writing it into MAINTENANCE.md (see the grep output captured during execution: every settings-writing route's read, lock and write/swap lines).
- Reproduced the UTF-8 finding live (`load_state` on a `state.json` containing bytes `ff fe 7b` raises `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte`) rather than asserting it from memory, before writing the MAINTENANCE.md entry.
- All required Tailwind classes for the new slot/summary markup (`w-full`, `flex-wrap`, `gap-2`, `text-red-400`, `text-sm`) were already present in `triggarr/static/css/output.css` (verified via `grep -c`), so no CSS rebuild was needed or performed.

## Deviations from Plan

None - plan executed exactly as written.

## Assumption Drift (advisory)

None.

## Issues Encountered

None.

## Threat Flags

None - no new network endpoint, auth path, file-access pattern, or schema change introduced. The threat_model's own T-87-07 through T-87-10b dispositions are satisfied as written: the response body stays `html.escape`d plain text from 87-01 (no `| safe` added to the template); zero `hx-target="body"/"html"` occurrences remain (pinned by the rewritten guard test); MAINTENANCE.md entries cite only code locations and behavior, no secrets or file contents; the failure swap is scoped to the row slot only; the pre-lock snapshot risk (T-87-10b) is recorded, accepted, and not fixed per the plan.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CONSIST-02 is now fully delivered: the response contract from 87-01 and the row-local display from this plan together satisfy D-04 through D-06.
- The D-13/D-14 MAINTENANCE.md records give Phase 90 (same `remove_instance` route) and any future UI Redesign work the evidence they need without re-auditing.
- The UTF-8 `load_state` crash and the `add_instance`/`save_settings` pre-lock snapshot are both recorded for an owner decision; neither blocks Phase 87's own success criteria, which do not require fixing them.
- Full suite: `3310 passed, 1 skipped` (the skip is pre-existing and unrelated to this plan); `ruff check triggarr/ tests/` reports `All checks passed!`.

---
*Phase: 87-settings-state-file-safety*
*Completed: 2026-11-15*
