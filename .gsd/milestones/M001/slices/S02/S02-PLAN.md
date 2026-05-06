# S02: S02

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

- [x] **T01: Audited README and adjacent docs against verified auth, config-dir, multi-instance, release, and Lidarr behavior.** `est:1h`
  Why: the README already shows signs of mixed-era documentation, so edits should be grounded in code and tests rather than assumptions.
  - Files: `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, `docker-compose.yml`, `CHANGELOG.md`, `TODO.md`, `triggarr/models/config.py`, `triggarr/models/config.py`, `triggarr/auth.py`, `triggarr/web/middleware.py`, `tests/test_auth_config.py`, `tests/test_auth_routes.py`, `tests/test_config.py`
  - Verify: `rg -n "no authentication|TRIGGARR_CONFIG_DIR|\[radarr\]|\[sonarr\]|\[lidarr\]|/config|mellow-tinkering-creek|latest/download" README.md SECURITY.md CONTRIBUTING.md docker-compose.yml CHANGELOG.md TODO.md` plus written audit findings.

- [x] **T02: Updated README install, config, and security guidance to match current config-dir, multi-instance, and auth behavior.** `est:1.5h`
  Why: README is the primary user entry point and currently mixes current standalone config-dir docs with stale config/security examples.
  - Files: `README.md`
  - Verify: `rg -n "no authentication|\[radarr\]\s*$|\[sonarr\]\s*$|\[lidarr\]\s*$|mellow-tinkering-creek" README.md` should show no stale/contradictory matches except intentional explanatory context.

- [x] **T03: Retired the stale configurable config-directory TODO and reconciled backlog/security docs with current path and auth behavior.** `est:45m`
  Why: stale backlog notes caused this milestone; leaving them stale would recreate the problem for the next agent.
  - Files: `TODO.md`, `.gsd/DEFERRED-BACKLOG.md`, `README.md`, `SECURITY.md`, `CONTRIBUTING.md`
  - Verify: `! rg -n "mellow-tinkering-creek|Hardcoded `/config/` paths prevent running outside Docker|Fix: add `TRIGGARR_CONFIG_DIR`" TODO.md .gsd/DEFERRED-BACKLOG.md README.md`

- [x] **T04: Apply final docs review corrections** `est:30m`
  Fix the slice-level reviewer findings in README.md and SECURITY.md without changing runtime code. Required corrections: (1) adjust SECURITY.md session-cookie wording to say cookies are marked secure when the request is HTTPS or carries X-Forwarded-Proto: https, and direct operators to configure TRUSTED_PROXY_IPS so forwarded headers are only honored from expected proxies; (2) adjust README Docker config-dir wording so it says Triggarr uses /config when TRIGGARR_CONFIG_DIR is unset, not that the image exports the env var; (3) adjust README SSRF wording so it names blocked non-HTTP, metadata/link-local/loopback/unspecified/multicast cases rather than inappropriate public IPs; (4) soften README full-subnet TRUSTED_PROXY_IPS guidance so specific proxy IPs are preferred and full-subnet trust is only for fully trusted Docker networks. Optionally add one sentence clarifying that config TOML credentials are plaintext on disk protected by file permissions/volume security, not encrypted at rest.
  - Files: `README.md`, `SECURITY.md`
  - Verify: rg -n "The Docker image defaults `TRIGGARR_CONFIG_DIR`|inappropriate public IPs|forwarded as HTTPS by a trusted proxy|use 172\.18\.0\.0/16 for the full subnet|mellow-tinkering-creek|Hardcoded `/config/` paths prevent running outside Docker|Fix: add `TRIGGARR_CONFIG_DIR`" README.md SECURITY.md TODO.md .gsd/DEFERRED-BACKLOG.md should return no matches; then run the README TOML extraction/Settings parse check from T02 if README examples changed.

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
