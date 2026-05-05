---
id: T03
parent: S02
milestone: M001
key_files:
  - TODO.md
  - .gsd/DEFERRED-BACKLOG.md
  - SECURITY.md
key_decisions:
  - Kept TODO.md as an explicit empty backlog marker instead of deleting it, so future agents can distinguish "no pending TODOs" from a missing or forgotten file.
  - Retired the configurable config-directory item in .gsd/DEFERRED-BACKLOG.md rather than leaving it in active carry-forward, because current source/tests already implement the path contract.
duration: 
verification_result: passed
completed_at: 2026-05-05T22:04:20.052Z
blocker_discovered: false
---

# T03: Retired the stale configurable config-directory TODO and reconciled backlog/security docs with current path and auth behavior.

**Retired the stale configurable config-directory TODO and reconciled backlog/security docs with current path and auth behavior.**

## What Happened

Replaced the root TODO with an explicit "no pending TODOs" state and a short note that configurable config-directory work is already retired because current code derives config, state, and SQLite paths from an absolute TRIGGARR_CONFIG_DIR while preserving /config as the Docker default. Updated .gsd/DEFERRED-BACKLOG.md so the legacy transition audit no longer promotes the retired config-dir item and now leaves only the 6h update-check stash as an active carry-forward candidate. Refreshed SECURITY.md to match current product capabilities: Radarr/Sonarr/Lidarr support, setup/default auth behavior, Forms/Basic/External/Disabled modes, X-Api-Key support, signed sessions, route protection, config-dir path behavior, and current container hardening guidance. Checked README-referenced local paths and supporting docs so future agents are not pointed at missing files or stale security/path behavior.

## Verification

Ran the exact task stale-marker check against TODO.md, .gsd/DEFERRED-BACKLOG.md, and README.md; it exited 0 with no matches. Ran an additional supporting-doc drift scan across README.md, SECURITY.md, TODO.md, and .gsd/DEFERRED-BACKLOG.md for stale no-auth/config-dir phrases; it exited 0 with no matches. Verified README-referenced local docs/assets exist, including screenshots, docker-compose.yml, SECURITY.md, CONTRIBUTING.md, CHANGELOG.md, and TODO.md.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `! rg -n 'mellow-tinkering-creek|Hardcoded `/config/` paths prevent running outside Docker|Fix: add `TRIGGARR_CONFIG_DIR`' TODO.md .gsd/DEFERRED-BACKLOG.md README.md` | 0 | ✅ pass | 16ms |
| 2 | `! rg -n 'no authentication|Triggarr is a single-process automation daemon that connects to Radarr and Sonarr instances|mellow-tinkering-creek|Hardcoded `/config/` paths prevent running outside Docker|Fix: add `TRIGGARR_CONFIG_DIR`' README.md SECURITY.md TODO.md .gsd/DEFERRED-BACKLOG.md` | 0 | ✅ pass | 65ms |
| 3 | `uv run python - <<'PY'  # assert README-referenced local docs/assets exist` | 0 | ✅ pass | 150ms |

## Deviations

Extended the edit set to SECURITY.md because the slice-level T03 file list and T01 audit identified it as an adjacent supporting doc with stale auth/capability prose; no legacy GSD PROJECT/REQUIREMENTS/DECISIONS/QUEUE/STATE files were rewritten.

## Known Issues

None.

## Files Created/Modified

- `TODO.md`
- `.gsd/DEFERRED-BACKLOG.md`
- `SECURITY.md`
