# Triggarr Community Polish & Test Hardening

**Date:** 2026-04-09
**Scope:** Two-phase milestone adding community health files and unhappy-path test coverage.

## Phase 1: Community Health Files

### CONTRIBUTING.md

Standard open-source contribution guide:

- Fork, branch, PR workflow
- How to run tests: `pytest`
- How to lint: `ruff check`
- Docker dev setup instructions
- Expectation that PRs pass CI before review

### SECURITY.md

Two sections:

**Reporting vulnerabilities:**
- Supported versions table (latest release only)
- Link to GitHub private vulnerability reporting

**Security model summary:**
- API keys never exposed via HTTP endpoints (SecretStr masking everywhere)
- CSRF protection via Origin/Referer middleware validation
- SSRF validation on configured URLs
- Input clamping for all config values
- Config file permissions: mode 0o600
- Atomic file writes (write-temp + fsync + os.replace) for config and state
- Docker: CAP_DROP ALL + minimal capabilities (CHOWN, DAC_OVERRIDE, FOWNER, SETUID, SETGID)
- PUID/PGID least-privilege container execution
- Custom loguru redacting sink (API keys never appear in logs)

### Issue Templates (YAML Forms)

**Bug report** (`bug.yml`):
- Fields: Triggarr version, deployment method (Docker/pip), app type (Radarr/Sonarr/Lidarr), description, expected vs actual behavior, relevant logs, config excerpt (remind to redact API keys)

**Feature request** (`feature.yml`):
- Fields: description, use case, alternatives considered

### Repo Metadata

**Topics:** `radarr`, `sonarr`, `lidarr`, `automation`, `selfhosted`, `arr`, `docker`, `python`

**GitHub Discussions:** Enable with General and Q&A categories.

---

## Phase 2: Test Hardening — Unhappy Paths

Targeted tests for error handling across four categories. Each test asserts specific behavior (graceful degradation, appropriate logging, no crashes, state not corrupted) — not just "no exception."

### Connection Failures

- *arr instance unreachable (connection refused, timeout)
- DNS resolution failure
- SSL/TLS errors
- Instance goes down mid-search-cycle (succeeds for first batch, fails for second)

### Bad API Responses

- Malformed JSON from *arr
- Unexpected HTTP status codes (401 unauthorized, 403 forbidden, 500 internal, 502 bad gateway)
- API version mismatches (Sonarr v3 vs v4 edge cases)
- Empty or truncated paginated responses

### Corrupt State/Config

- Broken TOML config (syntax errors, missing required fields, wrong types)
- Corrupt SQLite database (locked, schema mismatch after failed migration)
- Invalid JSON state file (truncated write, wrong structure)
- Config migration from unexpected starting state

### Search Logic Edge Cases

- Empty queues (nothing wanted-missing or cutoff-unmet)
- All items filtered out by tags (zero remaining after filter)
- Tag resolution failure (configured tag name doesn't exist in *arr)
- Batch size larger than available items
- Cursor position beyond queue length (items removed from *arr between cycles)

---

## Out of Scope

- Docs site (MkDocs) — README is sufficient for current project size
- Community outreach posts — original Reddit post (163 upvotes, 268K views) already established presence
- awesome-arr submission — can revisit later
- Code hardening — codebase is already clean (no AI artifacts, no dead code)
