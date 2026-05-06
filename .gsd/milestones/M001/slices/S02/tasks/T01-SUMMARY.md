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
  - Kept T01 as an audit-only task and deferred broad prose changes to later S02 work because the expected output was a source-backed docs audit list.
duration: 
verification_result: passed
completed_at: 2026-05-06T00:02:31.243Z
blocker_discovered: false
---

# T01: Audited README and adjacent docs against current config-dir, auth, multi-instance, release, and Lidarr behavior.

**Audited README and adjacent docs against current config-dir, auth, multi-instance, release, and Lidarr behavior.**

## What Happened

T01 audited README and adjacent docs against verified auth, config-dir, multi-instance, release, and Lidarr behavior. It identified stale install/version examples, Docker-only `/config` wording that needed standalone `TRIGGARR_CONFIG_DIR` clarification, flat-era TOML examples, obsolete no-auth security claims, SECURITY.md capability/auth gaps, and stale TODO references to missing configurable-config work. No broad prose edits were made in this task; the audit became the source-backed edit plan for T02/T03 and later S04 remediation.

## Verification

Original task verification passed: stale-drift scan found expected stale markers for follow-up edits, and focused pytest coverage for config-dir, startup, auth, reverse-proxy, and client capabilities passed (192 tests) with known Starlette warnings. Later fresh M001 completion verification also passed full tests and lint.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg stale drift scan across README, SECURITY, CONTRIBUTING, docker-compose, CHANGELOG, TODO` | 0 | ✅ pass — expected audit findings found | 66ms |
| 2 | `uv run pytest tests/test_config_dir.py tests/test_startup.py tests/test_auth_config.py tests/test_auth_middleware.py tests/test_auth_routes.py tests/test_clients.py -q` | 0 | ✅ pass — 192 focused tests passed | 10826ms |

## Deviations

None. T01 was intentionally audit-only; broad prose edits were left to later S02 tasks.

## Known Issues

The audit found stale README.md, SECURITY.md, and TODO.md guidance that later S02/S04 tasks remediated.

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
