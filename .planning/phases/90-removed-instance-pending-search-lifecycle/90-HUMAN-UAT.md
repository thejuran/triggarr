---
status: partial
phase: 90-removed-instance-pending-search-lifecycle
source: [90-VERIFICATION.md]
started: 2026-11-19T19:00:00Z
updated: 2026-11-19T19:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. "Instance removed" badge, tooltip and filter in a real browser
expected: History and the dashboard activity rail show a gray "Instance removed" badge/pill that reads as distinct from "Legacy — tracking discontinued"; hovering shows "This instance was removed before the search finished; it will not be checked again."; the History outcome filter narrows to those rows.
result: [pending]

### 2. Removal and same-name reuse against a live Radarr, Sonarr or Lidarr
expected: removing an instance with pending searches (Remove action, and separately a Save Settings submission that leaves it out) turns its pending searches into "Instance removed" under the original name; a new instance added under the same name shows none of the old totals and is never credited after a cycle runs.
result: [pending]

### 3. First start on a copy of the production database
expected: the startup log shows one INFO line per app with how many searches are being closed as "Instance removed", then a normal startup; a second start closes nothing.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
