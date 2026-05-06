---
id: T02
parent: S02
milestone: M001
key_files:
  - README.md
key_decisions:
  - Removed the README claim that arbitrary TOML fields can be overridden via pydantic-style environment variables because the current Settings source customization only loads init data and TOML.
  - Documented Disabled auth as an explicit config mode while recommending External for reverse-proxy/SSO deployments.
duration: 
verification_result: passed
completed_at: 2026-05-06T00:02:37.639Z
blocker_discovered: false
---

# T02: Updated README install, config, and security guidance to match current config-dir, multi-instance, and auth behavior.

**Updated README install, config, and security guidance to match current config-dir, multi-instance, and auth behavior.**

## What Happened

T02 updated README install, configuration, and security guidance. Docker guidance now explains `/config` as the default config/data directory for the mounted volume. Standalone guidance documents `TRIGGARR_CONFIG_DIR` as an absolute startup-level path and explains first-run config generation. Configuration examples now use nested per-instance TOML tables such as `[radarr.Default]`, `[radarr."4K"]`, `[sonarr.Default]`, and `[lidarr.Default]`. The stale no-auth security model was replaced with setup mode, Forms/Basic/External/Disabled auth behavior, signed sessions, X-Api-Key access, rate limiting, CSRF/origin checks, security headers, and reverse-proxy recommendations.

## Verification

Original task verification passed: README stale-text scan found no contradictory no-auth, flat table, or missing-plan markers, and the README TOML example parsed with `tomllib` and instantiated current `Settings`. Later fresh M001 completion verification passed docs/auth/proxy tests and full tests.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `! rg -n "no authentication|\[radarr\]\s*$|\[sonarr\]\s*$|\[lidarr\]\s*$|mellow-tinkering-creek" README.md` | 0 | ✅ pass — no stale README matches | 22ms |
| 2 | `uv run python README TOML extraction/Settings validation` | 0 | ✅ pass — nested README TOML example matches current Settings model | 272ms |

## Deviations

None.

## Known Issues

The S02 README update was later refined by S04 to reconcile External-auth and secure-cookie trust-boundary wording.

## Files Created/Modified

- `README.md`
