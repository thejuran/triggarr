# S02: Refresh README and project documentation

**Goal:** Bring user-facing docs and root TODO/backlog notes into alignment with the verified code behavior and current product capabilities.
**Demo:** After this: README and adjacent docs explain current Docker/standalone setup, nested multi-instance config, auth/security behavior, and no longer point to stale missing configurable-config work.

## Must-Haves

- README configuration examples use the current nested instance format.
- Config-directory docs distinguish Docker `/config` default from standalone `TRIGGARR_CONFIG_DIR`.
- Security/auth section matches actual code behavior and avoids obsolete absolute claims.
- `TODO.md` no longer references the missing `.claude/plans/mellow-tinkering-creek.md` file or claims already-shipped work is missing.

## Proof Level

- This slice proves: Artifact/content proof plus source-trace audit against code/tests.

## Integration Closure

Produces updated docs for S03 to verify with command checks, lint/tests, and user review.

## Verification

- Improves future-agent and user diagnostics by removing stale backlog pointers and documenting operational path behavior explicitly.

## Tasks

- [ ] **T01: Audit README and adjacent docs against current behavior** `est:1h`
  Why: the README already shows signs of mixed-era documentation, so edits should be grounded in code and tests rather than assumptions.
  - Files: `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, `docker-compose.yml`, `CHANGELOG.md`, `TODO.md`, `triggarr/models/config.py`, `triggarr/models/config.py`, `triggarr/auth.py`, `triggarr/web/middleware.py`, `tests/test_auth_config.py`, `tests/test_auth_routes.py`, `tests/test_config.py`
  - Verify: `rg -n "no authentication|TRIGGARR_CONFIG_DIR|\[radarr\]|\[sonarr\]|\[lidarr\]|/config|mellow-tinkering-creek|latest/download" README.md SECURITY.md CONTRIBUTING.md docker-compose.yml CHANGELOG.md TODO.md` plus written audit findings.

- [ ] **T02: Update README install, config, and security sections** `est:1.5h`
  Why: README is the primary user entry point and currently mixes current standalone config-dir docs with stale config/security examples.
  - Files: `README.md`
  - Verify: `rg -n "no authentication|\[radarr\]\s*$|\[sonarr\]\s*$|\[lidarr\]\s*$|mellow-tinkering-creek" README.md` should show no stale/contradictory matches except intentional explanatory context.

- [ ] **T03: Retire stale TODO and reconcile supporting docs** `est:45m`
  Why: stale backlog notes caused this milestone; leaving them stale would recreate the problem for the next agent.
  - Files: `TODO.md`, `.gsd/DEFERRED-BACKLOG.md`, `README.md`, `SECURITY.md`, `CONTRIBUTING.md`
  - Verify: `! rg -n "mellow-tinkering-creek|Hardcoded `/config/` paths prevent running outside Docker|Fix: add `TRIGGARR_CONFIG_DIR`" TODO.md .gsd/DEFERRED-BACKLOG.md README.md`

## Files Likely Touched

- README.md
- SECURITY.md
- CONTRIBUTING.md
- docker-compose.yml
- CHANGELOG.md
- TODO.md
- triggarr/models/config.py
- triggarr/auth.py
- triggarr/web/middleware.py
- tests/test_auth_config.py
- tests/test_auth_routes.py
- tests/test_config.py
- .gsd/DEFERRED-BACKLOG.md
