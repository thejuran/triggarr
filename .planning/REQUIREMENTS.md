# Requirements: Triggarr

**Defined:** 2026-04-09
**Core Value:** Reliably trigger searches in Radarr and Sonarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.

## v2.4 Requirements

Requirements for Community Polish & Test Hardening milestone. Each maps to roadmap phases.

### Community Health

- [ ] **COMM-01**: Repository has CONTRIBUTING.md with fork/branch/PR workflow, dev setup, test/lint commands
- [ ] **COMM-02**: Repository has SECURITY.md with supported versions table and GitHub private vulnerability reporting link
- [ ] **COMM-03**: SECURITY.md includes security model summary (SecretStr, CSRF, SSRF, input clamping, atomic writes, Docker hardening, loguru redaction)
- [ ] **COMM-04**: Repository has bug report issue template (YAML form) with version, deployment method, app type, description, expected vs actual, logs, config excerpt fields
- [ ] **COMM-05**: Repository has feature request issue template (YAML form) with description, use case, alternatives considered fields
- [ ] **COMM-06**: Repository has issue template config.yml with blank_issues_enabled: false and Discussions contact link
- [ ] **COMM-07**: Repository has pull request template with CI checklist

### Repo Metadata

- [ ] **META-01**: Repository has GitHub topics set (radarr, sonarr, automation, selfhosted, arr, docker, python)
- [ ] **META-02**: Repository has GitHub Discussions enabled with General and Q&A categories

### Test Hardening — Connection Failures

- [ ] **CONN-01**: Tests verify graceful handling when *arr instance is unreachable (connection refused, timeout)
- [ ] **CONN-02**: Tests verify graceful handling of DNS resolution failure
- [ ] **CONN-03**: Tests verify graceful handling of SSL/TLS errors
- [ ] **CONN-04**: Tests verify graceful handling when instance goes down mid-search-cycle

### Test Hardening — Bad API Responses

- [ ] **API-01**: Tests verify graceful handling of malformed JSON from *arr
- [ ] **API-02**: Tests verify graceful handling of unexpected HTTP status codes (401, 403, 500, 502)
- [ ] **API-03**: Tests verify graceful handling of API version mismatches (Sonarr v3/v4 edge cases)
- [ ] **API-04**: Tests verify graceful handling of empty or truncated paginated responses

### Test Hardening — Corrupt State/Config

- [ ] **STATE-01**: Tests verify recovery from broken TOML config (syntax errors, missing fields, wrong types)
- [ ] **STATE-02**: Tests verify recovery from corrupt SQLite database (locked, schema mismatch)
- [ ] **STATE-03**: Tests verify recovery from invalid JSON state file (truncated, wrong structure)
- [ ] **STATE-04**: Tests verify config migration handles unexpected starting state

### Test Hardening — Search Logic Edge Cases

- [ ] **SRCH-01**: Tests verify correct behavior with empty queues (nothing wanted or cutoff-unmet)
- [ ] **SRCH-02**: Tests verify correct behavior when all items filtered out by tags
- [ ] **SRCH-03**: Tests verify graceful handling of tag resolution failure (configured tag doesn't exist)
- [ ] **SRCH-04**: Tests verify correct behavior when batch size exceeds available items
- [ ] **SRCH-05**: Tests verify correct behavior when cursor position exceeds queue length

## Future Requirements

None deferred — milestone scope is complete.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Code of Conduct | Triggers content filter; unnecessary for homelab tool |
| CLA/DCO | Unnecessary friction for a small project |
| Stale bot | Annoying for contributors |
| Integration tests against real *arr | Complex, flaky, requires running instances |
| Coverage targets | Diminishing returns; test quality over quantity |
| Docs site (MkDocs) | README sufficient for current project size |
| awesome-arr submission | Can revisit later |
| Code hardening | Codebase is already clean (no AI artifacts, no dead code) |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| COMM-01 | Phase 45 | Pending |
| COMM-02 | Phase 45 | Pending |
| COMM-03 | Phase 45 | Pending |
| COMM-04 | Phase 45 | Pending |
| COMM-05 | Phase 45 | Pending |
| COMM-06 | Phase 45 | Pending |
| COMM-07 | Phase 45 | Pending |
| META-01 | Phase 45 | Pending |
| META-02 | Phase 45 | Pending |
| CONN-01 | Phase 46 | Pending |
| CONN-02 | Phase 46 | Pending |
| CONN-03 | Phase 46 | Pending |
| CONN-04 | Phase 46 | Pending |
| API-01 | Phase 46 | Pending |
| API-02 | Phase 46 | Pending |
| API-03 | Phase 46 | Pending |
| API-04 | Phase 46 | Pending |
| STATE-01 | Phase 47 | Pending |
| STATE-02 | Phase 47 | Pending |
| STATE-03 | Phase 47 | Pending |
| STATE-04 | Phase 47 | Pending |
| SRCH-01 | Phase 47 | Pending |
| SRCH-02 | Phase 47 | Pending |
| SRCH-03 | Phase 47 | Pending |
| SRCH-04 | Phase 47 | Pending |
| SRCH-05 | Phase 47 | Pending |

**Coverage:**
- v2.4 requirements: 26 total
- Mapped to phases: 26
- Unmapped: 0

---
*Requirements defined: 2026-04-09*
*Last updated: 2026-04-09 after roadmap creation*
