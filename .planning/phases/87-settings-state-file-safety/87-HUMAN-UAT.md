---
status: partial
phase: 87-settings-state-file-safety
source: [87-VERIFICATION.md]
started: 2026-11-15T23:42:31Z
updated: 2026-11-15T23:42:31Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Failed removal shows its message on the instance row
expected: With a removal that fails to save, the fixed "was not removed" sentence appears inside the clicked instance's own row with no full-page reload; unsaved edits in other rows and the Add Instance form are still present; clicking Remove again on that row replaces the message; reloading the page clears it.
result: [pending]

### 2. Clicking or selecting the error message
expected: Selecting or reading the message does not collapse the instance's section (code review IN-01: the message sits inside the row's summary without click isolation, so a click currently toggles the row).
result: [pending]

### 3. Screen-reader announcement
expected: With a screen reader running, a failed removal's message is announced without moving focus to the row.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
