---
id: M004
provides:
  - Clean GitHub tag list with no spurious dev tags
key_decisions:
  - Most of the original M004 scope was already resolved before execution — only tag cleanup remained
patterns_established: []
observability_surfaces: []
requirement_outcomes: []
duration: <5 min
verification_result: passed
completed_at: 2026-04-07
---

# M004: Version Bump & Release Tag Cleanup

**Deleted spurious `v2.6.1-dev` tag from GitHub; confirmed version strings and update checker were already correct.**

## What Happened

The original queue entry described `__version__` stuck at `"2.5.3"` with a spurious `v2.6.0-dev` tag. By the time M004 started, the version had already been bumped to `2.6.1-dev` and the update checker already handled pre-release correctly. The only remaining action was deleting the `v2.6.1-dev` tag from local and remote.

## Cross-Slice Verification

- `git tag -l` confirms no dev tags remain locally
- GitHub remote confirms tag deleted
- `_parse_version()` correctly strips `-dev` suffixes
- Update checker skips pre-release GitHub releases

## Requirement Changes

- none

## Forward Intelligence

### What the next milestone should know
- Version is `2.6.1-dev` — bump to `2.6.1` (or next version) when ready to release

### What's fragile
- nothing

### Authoritative diagnostics
- `git tag -l | sort -V` — verify tag list is clean

### What assumptions changed
- Original M004 scope was 4 items; 3 of 4 were already resolved before execution

## Files Created/Modified

- No code files modified — tag-only change
