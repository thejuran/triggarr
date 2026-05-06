---
id: T03
parent: S02
milestone: M001
key_files:
  - TODO.md
  - .gsd/DEFERRED-BACKLOG.md
  - SECURITY.md
key_decisions:
  - Kept TODO.md as an explicit empty backlog marker instead of deleting it, so future agents can distinguish no pending TODOs from a missing file.
  - Retired the configurable config-directory item in `.gsd/DEFERRED-BACKLOG.md` rather than leaving it as active carry-forward, because current source/tests already implement the path contract.
duration: 
verification_result: passed
completed_at: 2026-05-06T00:02:44.705Z
blocker_discovered: false
---

# T03: Retired the stale configurable config-directory TODO and reconciled backlog/security docs with current path and auth behavior.

**Retired the stale configurable config-directory TODO and reconciled backlog/security docs with current path and auth behavior.**

## What Happened

T03 replaced the root TODO with an explicit no-pending-TODOs state and noted that configurable config-directory work is retired because current code derives config, state, and SQLite paths from an absolute `TRIGGARR_CONFIG_DIR` while preserving `/config` as Docker default. It also updated `.gsd/DEFERRED-BACKLOG.md` so the legacy transition audit no longer promotes the retired config-dir item, and refreshed SECURITY.md to match Radarr/Sonarr/Lidarr support, setup/default auth behavior, Forms/Basic/External/Disabled modes, X-Api-Key support, signed sessions, protected routes, config-dir behavior, and container hardening guidance.

## Verification

Original task verification passed: task stale-marker scan and supporting-doc drift scan returned no matches, and README-referenced local docs/assets existed. Later fresh M001 completion verification passed docs guardrails, full tests, and lint.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `! rg stale configurable config-dir TODO markers in TODO.md .gsd/DEFERRED-BACKLOG.md README.md` | 0 | ✅ pass — no stale TODO markers | 16ms |
| 2 | `! rg stale no-auth/config-dir phrases in README.md SECURITY.md TODO.md .gsd/DEFERRED-BACKLOG.md` | 0 | ✅ pass — no stale supporting-doc matches | 65ms |
| 3 | `uv run python assert README-referenced local docs/assets exist` | 0 | ✅ pass | 150ms |

## Deviations

Extended the edit set to SECURITY.md because the S02 file list and T01 audit identified it as adjacent supporting documentation with stale auth/capability prose.

## Known Issues

None for T03 after later S04 refinements; human documentation UAT remains a release gate outside this task.

## Files Created/Modified

- `TODO.md`
- `.gsd/DEFERRED-BACKLOG.md`
- `SECURITY.md`
