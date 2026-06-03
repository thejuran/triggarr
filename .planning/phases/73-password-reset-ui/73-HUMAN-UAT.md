---
status: partial
phase: 73-password-reset-ui
source: [73-VERIFICATION.md]
started: 2026-06-03T00:00:00Z
updated: 2026-06-03T00:00:00Z
deferred_to: milestone-end NAS walkthrough (v2.10)
note: >
  Phase 73 verified 5/5 must-haves against the live code (1013 tests pass, ruff clean,
  middleware unchanged, all security invariants confirmed). The items below are
  visual-fidelity checks that require a real browser render. Per orchestrator decision
  (2026-06-03), they are deferred to the milestone-end NAS walkthrough, which deploys
  and exercises the full Track A reset flow in a browser — the natural place to confirm
  these. This mirrors how prior login/setup visual checks (UI-01/02/03) were handled.
---

## Current Test

[awaiting human testing at the v2.10 milestone-end NAS walkthrough]

## Tests

### UAT-73-1: "Forgot password?" link visibility + placement
- **Test:** Navigate to the login page in a browser with a configured (non-setup) Triggarr instance. Verify the "Forgot password?" link appears below the Sign In button, is muted/secondary in style, and links to /reset/request. Confirm it is NOT visible on a fresh first-run setup instance.
- **Expected:** Link visible, styled like the muted info-paragraph idiom, positioned below Sign In. Absent on a first-run setup instance.
- **Status:** pending

### UAT-73-2: Request-confirmation visual swap + no token on screen
- **Test:** Click "Forgot password?" and submit the reset request form. On success (first mint), verify the submit button disappears and a neutral confirmation message appears with an "Enter reset token" link pointing to /reset/confirm. Verify the token value is not visible anywhere on the page.
- **Expected:** Submit button absent; neutral confirmation text present; onward link to /reset/confirm present; no token value on screen.
- **Status:** pending

### UAT-73-3: "Back to login" on both reset steps
- **Test:** On the reset request and confirm pages, verify the "Back to login" link renders at the bottom of the card on both steps and navigates correctly to /login.
- **Expected:** Link appears on both steps, styling matches the muted-text idiom, navigation to /login works.
- **Status:** pending

### UAT-73-4: Confirm-page error placement (banner vs inline)
- **Test:** On the confirm page (/reset/confirm), submit with a wrong token — verify the error appears in the top-level banner (not inline). Submit with mismatched passwords (valid token) — verify the per-field "Passwords do not match" error appears inline below the confirm_password field.
- **Expected:** Token error in top banner; password errors inline per-field; consistent with login/setup page styling.
- **Status:** pending
