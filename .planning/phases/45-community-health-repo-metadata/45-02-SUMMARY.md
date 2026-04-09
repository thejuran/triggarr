# Plan 45-02 Summary: Issue Templates, PR Template, Repo Metadata

**Status:** Complete
**Commit:** c49083c

## What Was Built

- **bug-report.yml** -- YAML form with 3 dropdowns (version, deployment method, app type), description, expected behavior, optional logs, optional config excerpt with API key redaction warning
- **feature-request.yml** -- YAML form with description, use case, alternatives considered fields
- **config.yml** -- blank_issues_enabled: false, Discussions contact link
- **pull_request_template.md** -- CI checklist (tests pass, ruff clean, Docker builds)
- **GitHub topics** -- 7 topics set: arr, automation, docker, python, radarr, selfhosted, sonarr
- **GitHub Discussions** -- Enabled with default categories

## Requirements Satisfied

- COMM-04: Bug report issue template with all required fields
- COMM-05: Feature request issue template with description, use case, alternatives
- COMM-06: Issue config with blank_issues_enabled: false and Discussions link
- COMM-07: PR template with CI checklist
- META-01: 7 GitHub topics set
- META-02: Discussions enabled

## Tests Added

- `tests/test_github_templates.py` -- 18 tests validating template files and content

## Decisions Applied

- D-04: Minimal PR template (CI checklist only)
- D-05: YAML form templates with dropdowns
- D-06: Optional config excerpt with redaction warning
- D-07: Blank issues disabled with Discussions link

## Threat Mitigations

- T-45-03: Config excerpt field warns "Remove API keys before pasting" and is optional
- T-45-04: Accepted -- GitHub handles authentication for issue submission

## Pending Human Verification

Task 3 requires manual verification on GitHub:
1. Confirm 7 topics visible on repo page
2. Confirm Discussions tab with General and Q&A categories
3. Confirm New Issue shows structured forms (not blank textarea)
4. Confirm PR template renders with CI checklist
