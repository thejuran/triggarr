# M001: Portable Config Directory & Documentation Refresh

**Gathered:** 2026-05-03
**Status:** Ready for planning

## Project Description

Triggarr is a Docker-first Python automation daemon that triggers scheduled searches across Radarr, Sonarr, and Lidarr, with a FastAPI + htmx dashboard, persistent state, SQLite search history, and multi-instance/tag-aware search behavior.

## Why This Milestone

Legacy GSD audit surfaced a pending TODO: make the config directory configurable for non-Docker deployments. Current code inspection shows this support already exists through `TRIGGARR_CONFIG_DIR` in `triggarr/models/config.py`, `triggarr/state.py`, and `entrypoint.sh`, with coverage in `tests/test_config_dir.py`. The real risk is that the backlog and public documentation are stale: `TODO.md` still claims the feature is missing; README partially documents `TRIGGARR_CONFIG_DIR` but still includes old flat `[radarr]` / `[sonarr]` / `[lidarr]` config examples and a security section that claims no authentication despite current auth-related code and tests.

This milestone turns that stale backlog item into verified behavior and brings user-facing documentation back into alignment with the current product.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Run Triggarr outside Docker with `TRIGGARR_CONFIG_DIR` pointing at an absolute writable directory and know where config/state files are stored.
- Read the README and supporting docs without being misled about config format, auth/security behavior, Docker defaults, or current Radarr/Sonarr/Lidarr capabilities.
- Trust that stale TODO/backlog notes no longer describe already-shipped work as missing.

### Entry point / environment

- Entry point: `triggarr` CLI / Docker entrypoint / README install instructions
- Environment: local dev, standalone pip install, Docker deployment
- Live dependencies involved: filesystem only for config/state path proof; no live *arr instance required

## Completion Class

- Contract complete means: tests prove `TRIGGARR_CONFIG_DIR` path derivation, absolute-path validation, config generation/loading, and state path behavior.
- Integration complete means: the real startup/config/state paths use the same config directory contract across CLI, app startup, web routes, and Docker entrypoint assumptions.
- Operational complete means: a fresh custom config directory can be exercised through the real startup path without falling back to `/config` unexpectedly.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- A custom absolute `TRIGGARR_CONFIG_DIR` is honored for both `triggarr.toml` and `state.json` path derivation.
- Public documentation describes the current nested multi-instance config model and current auth/security posture accurately.
- The stale root `TODO.md` item is either removed, closed as already shipped, or rewritten so it no longer misdirects future agents.
- Verification uses real commands in this repo; documentation updates are checked for link/path drift and reviewed by the user before completion.

## Architectural Decisions

### Preserve `/config` as the default while supporting `TRIGGARR_CONFIG_DIR`

**Decision:** Keep `/config` as the backward-compatible default config directory and use `TRIGGARR_CONFIG_DIR` only when explicitly set to an absolute path.

**Rationale:** Docker users already mount `/config`; changing that default would break existing deployments. The environment variable gives standalone users a portable path without changing Docker behavior.

**Alternatives Considered:**
- Change default to platform-specific user config dirs — rejected because it would break Docker-first expectations and existing documentation.
- Allow relative paths — rejected because config/state writes should not depend on process working directory and relative paths increase path confusion.

## Error Handling Strategy

Invalid `TRIGGARR_CONFIG_DIR` values should fail early with explicit absolute-path validation. Config generation and state writes should continue using existing atomic write patterns and should not log secrets. Documentation should explain the startup-level nature of env vars separately from TOML settings.

## Risks and Unknowns

- Docs may be substantially stale beyond the config-dir TODO — README already appears inconsistent with current auth and multi-instance config behavior.
- Some `/config` mentions are intentional Docker defaults, not bugs; the milestone must distinguish default Docker paths from portable standalone paths.
- Current tests may prove helper functions but not the real CLI/startup path; final verification needs at least one operational check.

## Existing Codebase / Prior Art

- `triggarr/models/config.py` — defines `get_config_dir()`, `CONFIG_DIR`, `CONFIG_PATH`, `Settings`, and absolute-path validation.
- `triggarr/state.py` — defines `get_state_path()` from `get_config_dir()` and path-injected state read/write helpers.
- `entrypoint.sh` — uses `TRIGGARR_CONFIG_DIR:-/config` for Docker user home/chown/setup.
- `tests/test_config_dir.py` — existing focused tests for env-var support and path validation.
- `README.md` — partially updated standalone docs, but config reference/security sections appear stale.
- `TODO.md` — stale pointer claiming configurable config-dir work is still missing; referenced plan file is absent.
- `.gsd/DEFERRED-BACKLOG.md` — transition audit that surfaced this work.

## Relevant Requirements

- Portable config directory — user can choose a non-`/config` config/state directory for standalone runs while Docker behavior remains backward-compatible.
- Documentation parity — README and adjacent docs accurately describe current install, config, security, and operational behavior.
- Backlog hygiene — stale historical TODOs do not send future work toward already-shipped changes.

## Scope

### In Scope

- Verify existing `TRIGGARR_CONFIG_DIR` runtime behavior and fill any test gaps.
- Fix any real residual hardcoded `/config` bugs if verification finds them.
- Update README configuration examples to current nested multi-instance format.
- Review and update README/security/install/development docs for current behavior.
- Retire or correct stale `TODO.md` content.

### Out of Scope / Non-Goals

- Reworking the entire configuration model.
- Changing Docker's default `/config` mount path.
- Adding cross-instance deduplication or dynamic hot-add.
- Rewriting all historical GSD v1 artifacts.
- Publishing, tagging, pushing, or opening external issues/PRs.

## Technical Constraints

- Preserve SecretStr discipline and never expose API keys in docs examples beyond placeholders.
- Preserve atomic file writes for config and state.
- Keep `/config` default backward-compatible for Docker.
- Use current GSD milestone/slice/task directories for new planning while preserving root-level v1 files as history.

## Integration Points

- Filesystem config/state paths — `triggarr.toml`, `state.json`, `.migrated` marker, and SQLite data path assumptions if any.
- Docker entrypoint — `PUID`/`PGID` chown/setup must remain compatible with `/config` and custom config dir.
- README install instructions — Docker and standalone users need accurate path guidance.

## Testing Requirements

- Focused tests: `uv run pytest tests/test_config_dir.py tests/test_state.py tests/test_startup.py -q`
- Docs/content checks: search for stale flat config examples, missing plan references, and contradictory auth/no-auth claims.
- Full verification before milestone completion: `uv run pytest tests/ -x -q` and `uv run ruff check triggarr/ tests/`.

## Acceptance Criteria

- `TRIGGARR_CONFIG_DIR` behavior is verified through helper-level and startup/config/state-level tests.
- README accurately documents Docker `/config`, standalone `TRIGGARR_CONFIG_DIR`, current nested multi-instance TOML, and current security/auth behavior.
- `TODO.md` no longer claims configurable config-dir support is missing.
- Final UAT includes a user documentation review before declaring the docs update complete.

## Open Questions

- The exact current auth posture should be verified against code/tests before rewriting the security model section.
- Whether to remove `TODO.md` entirely or convert it into a short “no pending TODOs” note can be decided during execution based on remaining backlog.
