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
completed_at: 2026-05-05T22:02:00.517Z
blocker_discovered: false
---

# T02: Updated README install, config, and security guidance to match current config-dir, multi-instance, and auth behavior.

**Updated README install, config, and security guidance to match current config-dir, multi-instance, and auth behavior.**

## What Happened

Updated README.md only, keeping the task scope focused on install, configuration, and security/auth sections. The Docker install guidance now explains that /config is the Docker default config directory and that triggarr.toml, state.json, and triggarr.db live on the mounted volume. The standalone install guidance now pins the current 2.7.1 wheel URL, documents that TRIGGARR_CONFIG_DIR must be an absolute startup-level path, and explains the first-run default-config generation/re-run behavior. The configuration reference now uses nested per-instance TOML tables such as [radarr.Default], [radarr."4K"], [sonarr.Default], and [lidarr.Default], with placeholder API keys only. The stale general pydantic environment override claim was removed because Settings.settings_customise_sources currently omits env_settings. The security model was rewritten to describe setup mode, Forms/Basic/External/Disabled auth behavior, signed sessions, X-Api-Key support, rate limiting, secret redaction, CSRF/origin checks, security headers, and reverse-proxy recommendations.

## Verification

Verified the task-specified stale-text scan has no matches for contradictory README no-auth language, flat app table headings, or the missing mellow-tinkering-creek pointer. Also parsed the README TOML example with tomllib and instantiated triggarr.models.config.Settings from it to confirm the documented nested multi-instance structure matches the current model.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `! rg -n "no authentication|\[radarr\]\s*$|\[sonarr\]\s*$|\[lidarr\]\s*$|mellow-tinkering-creek" README.md` | 0 | ✅ pass | 22ms |
| 2 | `uv run python - <<'PY'  # extract README toml block, tomllib.loads(...), Settings(**data), assert nested instances` | 0 | ✅ pass | 272ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `README.md`
