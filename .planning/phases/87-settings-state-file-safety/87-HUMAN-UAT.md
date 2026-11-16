---
status: partial
phase: 87-settings-state-file-safety
source: [87-VERIFICATION.md]
started: 2026-11-15T23:42:31Z
updated: 2026-11-16T00:08:56Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Failed removal shows its message on the instance row
expected: With a removal that fails to save, the fixed "was not removed" sentence appears inside the clicked instance's own row with no full-page reload; unsaved edits in other rows and the Add Instance form are still present; clicking Remove again on that row replaces the message; reloading the page clears it.
result: passed (2026-11-15, run by Claude in a real browser via Playwright against a local copy of the app at code head f099c6a8, settings folder made read-only to force the failed save). The fixed sentence appeared on the clicked row only, the other row's slot stayed empty, the page did not reload, an unsaved URL edit on another row and an unsaved Add Instance name were both still present, a second Remove click on the same row left exactly one message, and each failed attempt wrote exactly one error log entry. Also exercised: Remove on a row whose instance had already been removed by another request reloaded the Settings page with that row gone; a normal removal with the folder writable again reloaded with the row gone; no browser console errors or warnings. Not exercised: a retry that ends in a session-expired response.

### 2. Clicking or selecting the error message
expected: Selecting or reading the message does not collapse the instance's section (code review IN-01: the message sits inside the row's summary without click isolation, so a click currently toggles the row).
result: passed (2026-11-15, same run, after fix-round commit 92ddc3a1). Clicking the message left the instance section open.

### 3. Screen-reader announcement
expected: With a screen reader running, a failed removal's message is announced without moving focus to the row.
result: [pending]

## Summary

total: 3
passed: 2
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
