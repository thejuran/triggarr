---
id: T01
parent: S02
milestone: M001
key_files:
  - README.md
  - SECURITY.md
  - TODO.md
  - CONTRIBUTING.md
  - docker-compose.yml
  - CHANGELOG.md
  - triggarr/models/config.py
  - triggarr/state.py
  - triggarr/__main__.py
  - triggarr/web/middleware.py
  - triggarr/auth.py
  - tests/test_config_dir.py
  - tests/test_startup.py
  - tests/test_auth_config.py
  - tests/test_auth_middleware.py
  - tests/test_auth_routes.py
  - tests/test_auth_integration.py
  - tests/test_clients.py
key_decisions:
  - Kept T01 as an audit-only task and deferred broad prose changes to later S02 work because the task's expected output is the source-backed docs audit list.
duration: 
verification_result: passed
completed_at: 2026-05-05T21:58:50.487Z
blocker_discovered: false
---

# T01: Audited README and adjacent docs against verified auth, config-dir, multi-instance, release, and Lidarr behavior.

**Audited README and adjacent docs against verified auth, config-dir, multi-instance, release, and Lidarr behavior.**

## What Happened

Loaded the write-docs workflow and treated the reader as a future docs editor who needs a source-backed edit plan. No broad prose edits were made in T01; the intended output is the audit that subsequent S02 tasks can apply.

Docs audit findings, each backed by source/tests:

1. README install/version example is stale: the pip install URL still names `triggarr-2.7.0-py3-none-any.whl`, while `pyproject.toml`, `triggarr/__init__.py`, and `CHANGELOG.md` show current version `2.7.1`. A future README edit should avoid pinning a stale wheel filename or update it to the current release.
2. README config-location language mixes Docker-only `/config/triggarr.toml` with standalone behavior. Source and focused tests confirm `/config` is the env-unset Docker/default fallback, while absolute `TRIGGARR_CONFIG_DIR` drives `triggarr.toml`, `state.json`, and `triggarr.db` for standalone installs; relative values are rejected. Relevant evidence: `triggarr.models.config.get_config_dir/get_config_path`, `triggarr.state.get_state_path`, `triggarr.__main__._run`, S01 summary, `tests/test_config_dir.py`, and `tests/test_startup.py`.
3. README configuration examples are flat-era TOML. Current settings model uses nested per-instance tables (`radarr`, `sonarr`, `lidarr` as `dict[str, InstanceConfig]`), and v2.2 flat migration only wraps flat Radarr/Sonarr into `Default`; Lidarr is already v2.7-era and should be documented as nested. Relevant evidence: `triggarr.models.config.Settings`, `triggarr.config.DEFAULT_CONFIG`, `_is_v22_format`, `_migrate_v22_to_v23`, `tests/test_config.py`, and settings UI form names.
4. README security model is stale and materially wrong: it says Triggarr has no authentication, but current code defaults to Forms auth setup, supports Basic/External/Disabled modes, signed session cookies, a generated API key, password changes, login/logout, and login rate limiting. Relevant evidence: `triggarr.models.config.AuthConfig`, `triggarr.web.middleware.AuthMiddleware`, `triggarr.auth`, `triggarr/templates/setup.html`, `triggarr/templates/login.html`, `triggarr/templates/settings.html`, `tests/test_auth_config.py`, `tests/test_auth_middleware.py`, `tests/test_auth_routes.py`, and `tests/test_auth_integration.py`.
5. README reverse-proxy guidance is mostly aligned with current source: `ROOT_PATH`, `TRUSTED_PROXY_IPS`, `proxy_headers=True`, and `forwarded_allow_ips` are implemented and tested. Future edits should preserve the warning against wildcard trusted proxies and should integrate the auth modes rather than describing a no-auth deployment model. Relevant evidence: `triggarr.__main__`, `tests/test_root_path.py`, and `AuthMiddleware` External mode.
6. SECURITY.md is stale on capabilities and auth: it describes a daemon connecting to Radarr and Sonarr only, omitting Lidarr and the current application authentication controls. Relevant evidence: `APP_TYPES`, `LidarrClient`, `tests/test_clients.py`, and the auth test suite.
7. TODO.md is stale and should be removed or replaced: it claims hardcoded `/config/` prevents non-Docker use and points to missing `.claude/plans/mellow-tinkering-creek.md`. S01 already verified the config-dir contract is implemented; current source/tests confirm the TODO no longer represents product behavior.
8. docker-compose.yml is not stale for `/config`: the named volume mounted at `/config` matches the Docker default and entrypoint ownership behavior. It may need only adjacent README/security wording updates, not a functional compose change.
9. CONTRIBUTING.md development commands are aligned with current project commands; no conflicting user-facing guidance found there.
10. CHANGELOG.md already records v2.7.1 and Lidarr support in v2.7.0; use it as release/source context when updating README install and capability prose.

## Verification

Ran the task-specified drift scan across README, SECURITY, CONTRIBUTING, docker-compose, CHANGELOG, and TODO; it found the expected stale README/TODO markers for no-auth wording, flat config examples, Docker/default path language, stale latest/download version, and missing-plan TODO. Ran focused pytest coverage for config-dir path behavior, startup path wiring, auth model/middleware/routes/integration, reverse proxy-related startup behavior, and client capabilities; all 192 focused tests passed with only existing Starlette TestClient cookie deprecation warnings.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "no authentication|TRIGGARR_CONFIG_DIR|\[radarr\]|\[sonarr\]|\[lidarr\]|/config|mellow-tinkering-creek|latest/download" README.md SECURITY.md CONTRIBUTING.md docker-compose.yml CHANGELOG.md TODO.md` | 0 | ✅ pass | 66ms |
| 2 | `uv run pytest tests/test_config_dir.py tests/test_startup.py tests/test_auth_config.py tests/test_auth_middleware.py tests/test_auth_routes.py tests/test_clients.py -q` | 0 | ✅ pass | 10826ms |

## Deviations

None. The task called for an audit summary, so no broad README or adjacent-doc prose edits were made.

## Known Issues

README.md, SECURITY.md, and TODO.md still contain stale user-facing guidance; this is the intended input to the subsequent documentation-edit task in S02.

## Files Created/Modified

- `README.md`
- `SECURITY.md`
- `TODO.md`
- `CONTRIBUTING.md`
- `docker-compose.yml`
- `CHANGELOG.md`
- `triggarr/models/config.py`
- `triggarr/state.py`
- `triggarr/__main__.py`
- `triggarr/web/middleware.py`
- `triggarr/auth.py`
- `tests/test_config_dir.py`
- `tests/test_startup.py`
- `tests/test_auth_config.py`
- `tests/test_auth_middleware.py`
- `tests/test_auth_routes.py`
- `tests/test_auth_integration.py`
- `tests/test_clients.py`
