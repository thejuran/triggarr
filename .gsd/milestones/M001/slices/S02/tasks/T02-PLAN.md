---
estimated_steps: 9
estimated_files: 1
skills_used: []
---

# T02: Update README install, config, and security sections

Why: README is the primary user entry point and currently mixes current standalone config-dir docs with stale config/security examples.

Do:
1. Update Docker and standalone install sections only where S01 verified behavior supports the claim.
2. Replace flat app config examples with nested multi-instance examples that match the current `dict[str, InstanceConfig]` model.
3. Document `TRIGGARR_CONFIG_DIR` as a startup-level environment variable and clarify `/config` as the Docker default.
4. Rewrite the security/auth section to reflect actual current auth behavior after verifying it in code/tests.
5. Keep examples free of real secrets; use placeholders only.
6. Keep prose concise and useful for fresh users.

Done when: README no longer contradicts verified runtime behavior or current config model.

## Inputs

- `T01 docs audit findings`
- `triggarr/models/config.py`
- `triggarr/auth.py`
- `triggarr/web/middleware.py`

## Expected Output

- `README.md`

## Verification

`rg -n "no authentication|\[radarr\]\s*$|\[sonarr\]\s*$|\[lidarr\]\s*$|mellow-tinkering-creek" README.md` should show no stale/contradictory matches except intentional explanatory context.

## Observability Impact

Improves install/debug clarity by making config/state path behavior explicit.
