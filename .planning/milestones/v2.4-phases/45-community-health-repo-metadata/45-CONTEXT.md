# Phase 45: Community Health & Repo Metadata - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver community health files (CONTRIBUTING.md, SECURITY.md, issue templates, PR template, LICENSE) and repo metadata (GitHub topics, Discussions) so contributors and users have clear guidance on how to report issues, submit changes, and report vulnerabilities.

</domain>

<decisions>
## Implementation Decisions

### CONTRIBUTING.md
- **D-01:** Quick reference style — concise, assumes contributor knows git. Prerequisites, fork/branch/PR steps, dev commands (uv sync, pytest, ruff), done.
- **D-02:** Include conventional commit conventions: `feat:`, `fix:`, `docs:`, `test:` prefixes. Matches the commit style already used in the repo.

### License
- **D-03:** MIT License. Add LICENSE file at repo root.

### PR Template
- **D-04:** CI checklist only — minimal friction. Just the checklist items: tests pass, ruff clean, Docker builds. Open description field, no structured sections.

### Issue Templates
- **D-05:** Use YAML form templates with dropdowns where possible. Version as dropdown (v2.4, v2.3, v2.2, older), deployment method as dropdown (Docker Compose, Docker run, bare metal), app type as dropdown (Radarr, Sonarr, both).
- **D-06:** Bug report includes optional config excerpt field with clear redaction warning ("Remove API keys before pasting"). Not required.
- **D-07:** Blank issues disabled (`blank_issues_enabled: false`) with Discussions contact link per COMM-06.

### Claude's Discretion
- SECURITY.md structure and depth — follow requirements (COMM-02, COMM-03) for supported versions table, GitHub private vulnerability reporting link, and security model summary covering SecretStr, CSRF, SSRF, input clamping, atomic writes, Docker hardening, loguru redaction.
- Feature request template field specifics — follow COMM-05 requirements (description, use case, alternatives considered).
- GitHub topics exact list — follow META-01 (radarr, sonarr, automation, selfhosted, arr, docker, python).
- Discussions categories — follow META-02 (General and Q&A).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Documentation
- `README.md` — Current project documentation; CONTRIBUTING.md should reference dev setup commands consistent with this
- `CLAUDE.md` — Development commands and code conventions (authoritative source for dev setup steps)

### CI/CD Configuration
- `.github/workflows/ci.yml` — CI workflow; PR template checklist items should match what CI actually checks
- `.github/workflows/release.yml` — Release workflow; SECURITY.md supported versions should align with release tags

### Security Model (for SECURITY.md content)
- `triggarr/config.py` — SecretStr usage for API keys
- `triggarr/middleware.py` — CSRF Origin/Referer validation
- `triggarr/security.py` — SSRF validation, input clamping
- `Dockerfile` — Docker hardening (multi-stage, PUID/PGID, least-privilege)

### Requirements
- `.planning/REQUIREMENTS.md` — COMM-01 through COMM-07, META-01, META-02 with exact field specifications

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.github/workflows/ci.yml` — CI checks (pytest, ruff, Docker build) that PR template checklist should mirror
- `CLAUDE.md` — Dev commands section is the authoritative source for contributor dev setup

### Established Patterns
- No existing community health files — this is greenfield for CONTRIBUTING.md, SECURITY.md, templates
- Conventional commit style already used in git history (feat/fix/docs prefixes)

### Integration Points
- `.github/ISSUE_TEMPLATE/` — New directory for bug report and feature request YAML forms + config.yml
- `.github/pull_request_template.md` — New file for PR template
- Repo root — CONTRIBUTING.md, SECURITY.md, LICENSE files

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 45-community-health-repo-metadata*
*Context gathered: 2026-04-09*
