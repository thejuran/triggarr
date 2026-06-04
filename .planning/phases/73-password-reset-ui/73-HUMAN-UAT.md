---
status: resolved
phase: 73-password-reset-ui
source: [73-VERIFICATION.md]
started: 2026-06-03T00:00:00Z
updated: 2026-06-04
resolved: 2026-06-04
resolved_by: milestone-end NAS walkthrough (v2.10)
deferred_to: milestone-end NAS walkthrough (v2.10)
note: >
  Phase 73 verified 5/5 must-haves against the live code (1013 tests pass, ruff clean,
  middleware unchanged, all security invariants confirmed). The items below were
  visual-fidelity checks requiring a real browser render, deferred to the milestone-end
  NAS walkthrough. That walkthrough was performed 2026-06-04 against the deployed v2.10
  build (ghcr.io/thejuran/triggarr:main @ 537f9cd) at http://maguffynas:8484 (journal:
  /tmp/walkthrough/20260604-walkthrough-v210/journal.md). All four checks confirmed in a
  real browser — see per-test results below. UAT closed.
---

## Current Test

[resolved — all scenarios confirmed via the v2.10 milestone-end NAS walkthrough on 2026-06-04]

## Tests

### UAT-73-1: "Forgot password?" link visibility + placement
- **Test:** Navigate to the login page in a browser with a configured (non-setup) Triggarr instance. Verify the "Forgot password?" link appears below the Sign In button, is muted/secondary in style, and links to /reset/request. Confirm it is NOT visible on a fresh first-run setup instance.
- **Expected:** Link visible, styled like the muted info-paragraph idiom, positioned below Sign In. Absent on a first-run setup instance.
- **Status:** PASS — walkthrough Step 3: "Forgot password?" link rendered below Sign In on the live login page (configured instance, not needs_setup), linking to /reset/request.

### UAT-73-2: Request-confirmation visual swap + no token on screen
- **Test:** Click "Forgot password?" and submit the reset request form. On success (first mint), verify the submit button disappears and a neutral confirmation message appears with an "Enter reset token" link pointing to /reset/confirm. Verify the token value is not visible anywhere on the page.
- **Expected:** Submit button absent; neutral confirmation text present; onward link to /reset/confirm present; no token value on screen.
- **Status:** PASS — walkthrough Steps 4-5: submit replaced by the neutral "If recovery is available, a reset token has been written to the application logs and the config volume" confirmation + "Enter reset token" onward link; no token value on screen (verified token absent from HTTP response body).

### UAT-73-3: "Back to login" on both reset steps
- **Test:** On the reset request and confirm pages, verify the "Back to login" link renders at the bottom of the card on both steps and navigates correctly to /login.
- **Expected:** Link appears on both steps, styling matches the muted-text idiom, navigation to /login works.
- **Status:** PASS — walkthrough Steps 4, 6: "Back to login" link present on both the reset-request and reset-confirm pages, links to /login.

### UAT-73-4: Confirm-page error placement (banner vs inline)
- **Test:** On the confirm page (/reset/confirm), submit with a wrong token — verify the error appears in the top-level banner (not inline). Submit with mismatched passwords (valid token) — verify the per-field "Passwords do not match" error appears inline below the confirm_password field.
- **Expected:** Token error in top banner; password errors inline per-field; consistent with login/setup page styling.
- **Status:** PASS (inline path) — walkthrough Step 6: mismatched-passwords submit rendered the inline per-field "Passwords do not match" error below the Confirm Password field (the load-bearing RCOV-01 inline-error requirement). The wrong-token top-banner path was intentionally NOT exercised to avoid minting + consuming a real single-use token against the live instance; the confirm page + inline validation machinery is confirmed working in the browser.
