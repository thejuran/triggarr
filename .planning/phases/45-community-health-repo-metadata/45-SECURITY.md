---
phase: 45-community-health-repo-metadata
status: secured
threats_total: 4
threats_closed: 4
threats_open: 0
audited: 2026-04-09
---

## Threat Register

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| T-45-01 | Info Disclosure | SECURITY.md | mitigate | CLOSED | No internal file paths, config locations, or block-list entries exposed. Mechanisms described at abstraction level only. |
| T-45-02 | Info Disclosure | CONTRIBUTING.md | accept | CLOSED | Dev commands already public in CLAUDE.md and CI. No secrets exposed. |
| T-45-03 | Info Disclosure | bug-report.yml config excerpt | mitigate | CLOSED | Field warns "Remove API keys before pasting" and is optional (required: false). |
| T-45-04 | Spoofing | Issue templates | accept | CLOSED | GitHub handles authentication for issue submission. Standard for public repos. |

## Accepted Risks

- **T-45-02**: Dev commands (uv sync, pytest, ruff, docker build) are intentionally public — they appear in CLAUDE.md and CI workflows.
- **T-45-04**: Issue template spoofing is a platform-level concern handled by GitHub authentication. No additional mitigation possible or needed.

## Security Audit 2026-04-09

| Metric | Count |
|--------|-------|
| Threats found | 4 |
| Closed | 4 |
| Open | 0 |
