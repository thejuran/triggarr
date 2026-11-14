---
status: partial
phase: 86-pilot-reference-record
source: [86-VERIFICATION.md]
started: 2026-11-14T17:08:40Z
updated: 2026-11-14T17:08:40Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Push the branch and open the Phase 86 PR
expected: one push of `phase-86-pilot-reference-record`, one ready-for-review PR, a per-head checkpoint comment in the `docs/review-checkpoint-record.md` format (owner go-ahead needed for the push)
result: [pending]

### 2. CI on the pushed head
expected: every required check passes on the PR head (`CI ready`, `CodeQL`)
result: [pending]

### 3. Owner exact-commit acceptance and merge
expected: the owner approves the exact PR head in the `review-acceptance` environment and merges; later-found misses in 86-PILOT-RECORD.md are updated before acceptance (D-14)
result: [pending]

### 4. Roadmaps page
expected: the page shows Phase 86 in review with no disagreement warning between STATE.md and ROADMAP.md
result: [pending]

### 5. Greptile on the pushed head (optional)
expected: runs only if free credits allow; not a required check
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
