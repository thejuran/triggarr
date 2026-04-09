# Feature Landscape

**Domain:** Community health files and unhappy-path test hardening for an open-source *arr ecosystem tool
**Researched:** 2026-04-09

## Table Stakes

Features users/contributors expect. Missing = project feels unprofessional or unwelcoming.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| CONTRIBUTING.md with dev setup | Every credible OSS project has one; Sonarr, Recyclarr, Overseerr all include it. GitHub surfaces it in the "Community" sidebar | Low | README already has a 5-line Development section with uv/pytest/ruff/tailwind/docker commands. CONTRIBUTING.md expands with fork/branch/PR workflow, code style expectations, and testing requirements |
| SECURITY.md with reporting instructions | GitHub surfaces "Security" tab; empty looks negligent. Sonarr has one (Discord + email, 72h SLA). Required for GitHub's community health score | Low | Use GitHub Private Vulnerability Reporting (PVR) -- free, built-in, no Discord/email infrastructure needed for a single-maintainer project |
| Bug report issue template (YAML form) | Structured reports save maintainer triage time; prevents "it doesn't work" issues with no context | Low | YAML form at `.github/ISSUE_TEMPLATE/bug-report.yml` with dropdowns for deploy method (Docker/pip), version, Radarr/Sonarr version, and required fields for reproduction steps and logs |
| Feature request issue template (YAML form) | Channels feature requests into structured format; separates from bugs | Low | YAML form at `.github/ISSUE_TEMPLATE/feature-request.yml` with description, use case, and alternatives considered |
| Issue template config with contact links | Directs support questions away from issues to a more appropriate channel | Low | `.github/ISSUE_TEMPLATE/config.yml` with `contact_links` pointing to GitHub Discussions for Q&A |
| Repo topics | Discoverability on GitHub; standard for *arr ecosystem tools | Low | `radarr`, `sonarr`, `arr`, `automation`, `docker`, `fastapi`, `python`, `htmx` via `gh repo edit --add-topic` |
| Unhappy-path tests: connection failures | 466 tests exist but network failures are the number one runtime issue for *arr tools. Existing tests cover some (test_validate_connection_connect_error, test_validate_connection_timeout) but gaps remain in mid-cycle failures and retry exhaustion | Medium | httpx.ConnectError, httpx.TimeoutException during search API calls, DNS resolution failures, connection refused mid-cycle, retry exhaustion paths |
| Unhappy-path tests: bad API responses | *arr APIs return unexpected shapes during version upgrades or edge conditions | Medium | HTTP 401/403/500 responses, malformed JSON, missing expected fields in paginated responses, empty arrays where non-empty expected, HTML error pages instead of JSON |
| Unhappy-path tests: corrupt state/config | Users hand-edit TOML files; SQLite can corrupt after unclean Docker shutdown | Medium | Malformed TOML (syntax errors, wrong types), missing required config keys, corrupt SQLite (invalid header), zero-byte state files, partial writes interrupted mid-save |

## Differentiators

Features that set project apart. Not expected, but signal quality and maturity.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| GitHub Discussions enabled | Separates support/ideas from bug reports; Overseerr uses this pattern successfully. Gives users a place to ask questions without cluttering issues | Low | Enable via `gh repo edit --enable-discussions`; configure Q&A and Ideas categories |
| PR template | Guides contributors to include testing evidence and describe changes systematically | Low | `.github/PULL_REQUEST_TEMPLATE.md` with checklist: tests pass, ruff clean, description of change, related issue |
| Unhappy-path tests: search logic edge cases | Proves round-robin, cursor management, and tag filtering are resilient under adversarial or degenerate data. Differentiates Triggarr's test quality from Huntarr and similar tools that have minimal testing | Medium | Empty wanted lists mid-cycle, instance added/removed between cycles, tag renamed/deleted in *arr between resolution and use, all items filtered by release date (zero eligible), cursor beyond list length after items removed from *arr |
| Enable GitHub Private Vulnerability Reporting | PVR is the modern standard -- security researchers can report directly on GitHub without needing email or Discord. Only ~30% of small OSS projects enable this | Low | Repository setting (not a file); referenced from SECURITY.md. Enable via web UI under Settings > Code security > Private vulnerability reporting |
| Security model summary in SECURITY.md | Triggarr already has a documented security model in README (no credential exposure, CSRF, SSRF validation, input clamping). Surfacing it in SECURITY.md builds trust and shows intentional security design | Low | Extract and reference existing security model section from README; add scope statement (what is and is not a vulnerability for this project) |

## Anti-Features

Features to explicitly NOT build in this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Code of Conduct (Contributor Covenant) | Known to trigger content filters during AI-assisted generation; single-maintainer hobby project does not need formal CoC enforcement yet | Add a brief "Be respectful" note in CONTRIBUTING.md; add CoC manually later if community grows beyond a handful of contributors |
| CLA / DCO sign-off requirement | Overkill for a hobby project; adds friction that deters drive-by contributors who might fix a typo or improve docs | Standard GitHub fork/PR workflow is sufficient; MIT/Apache license provides adequate IP clarity |
| Stale bot / auto-close issues | Signals abandoned maintenance rather than active curation; frustrates users who report legitimate bugs that take time to fix | Manually manage issues; small project volume makes this tractable |
| Complex branching strategy (gitflow) | Single maintainer with main + dev tag workflow; gitflow adds ceremony without benefit at this scale | Keep current pattern: develop on main, tag releases after UAT |
| 100% code coverage target | Diminishing returns; existing 466 tests are comprehensive for happy paths. Chasing coverage metrics leads to low-value tests | Focus unhappy-path tests on high-risk areas with real failure modes: network, config parsing, state recovery |
| Integration tests against real *arr instances | Requires running Radarr/Sonarr in CI; complex Docker-in-Docker setup, flaky network, slow execution, version matrix explosion | Continue with mocked httpx responses; real-instance testing stays in manual UAT |
| Changelog automation (release-drafter, conventional commits) | Adds CI complexity and commit message bureaucracy; manual changelog is fine at current scale and more readable | Keep existing manual changelog pattern |
| CODEOWNERS file | Single maintainer owns everything; CODEOWNERS adds no value until there are domain-specific reviewers | Revisit if project gains regular contributors with defined areas of ownership |
| Sponsors / funding configuration | Premature; project needs community first, funding later | Revisit if adoption grows past niche usage |

## Feature Dependencies

```
GitHub Discussions (repo setting)
  +--referenced-by--> Issue template config.yml (contact_links section)

CONTRIBUTING.md (standalone file)
  +--references--> README Development section (existing)

SECURITY.md (standalone file)
  +--references--> README Security Model section (existing)
  +--references--> GitHub PVR (repo setting)

Issue templates (bug + feature YAML forms)
  +--require--> .github/ISSUE_TEMPLATE/ directory (new)

Issue template config.yml
  +--requires--> GitHub Discussions enabled (for contact_links to work)

PR template (standalone file in .github/)
  +--no dependencies--

Repo topics (repo setting)
  +--no dependencies--

Unhappy-path tests: connection failures
  +--depends-on--> existing httpx mock patterns (test_clients.py, test_search.py)
  +--depends-on--> existing conftest.py fixtures

Unhappy-path tests: bad API responses
  +--depends-on--> existing mock patterns (test_clients.py, test_search.py)
  +--depends-on--> pydantic validation error handling in client code

Unhappy-path tests: corrupt state/config
  +--depends-on--> existing tmp_path patterns (test_state.py, test_config.py, test_db.py)

Unhappy-path tests: search logic edge cases
  +--depends-on--> existing search test fixtures (test_search.py)
  +--depends-on--> understanding of round-robin cursor logic
```

## MVP Recommendation

Prioritize (natural ordering by dependency and value):

1. **Repo metadata** (topics + enable Discussions) -- unblocks issue template config.yml contact links; zero-code changes
2. **CONTRIBUTING.md** -- most visible community health file; references dev setup already in README; attracts contributors
3. **SECURITY.md + enable PVR** -- completes GitHub's security tab; documents existing security model; responsible disclosure path
4. **Issue templates** (bug + feature YAML forms + config.yml) -- depends on Discussions being enabled for contact links
5. **PR template** -- quick win; guides any future contributors to provide context
6. **Unhappy-path tests: connection failures** -- highest real-world failure mode for *arr tools (network issues between Docker containers)
7. **Unhappy-path tests: bad API responses** -- second most common runtime issue (*arr version upgrades change API shapes)
8. **Unhappy-path tests: corrupt state/config** -- protects upgrade and crash-recovery paths
9. **Unhappy-path tests: search logic edge cases** -- proves resilience of core round-robin and tag filtering algorithms

Defer: Code of Conduct (content filter issue + premature), CLA/DCO (friction), integration tests (complexity), CODEOWNERS (single maintainer).

## Complexity Summary

| Category | Deliverable Count | Estimated Complexity |
|----------|------------------|---------------------|
| Community health files | 5 files (CONTRIBUTING.md, SECURITY.md, bug-report.yml, feature-request.yml, config.yml) + PR template | Low -- all templated content, patterns well-established |
| Repo settings | 3 changes (topics, Discussions, PVR) | Low -- CLI or web UI toggles |
| Unhappy-path tests: connection failures | ~8-12 new tests | Medium -- requires understanding retry logic, mid-cycle failure modes |
| Unhappy-path tests: bad API responses | ~8-12 new tests | Medium -- requires mocking various HTTP status codes and malformed payloads |
| Unhappy-path tests: corrupt state/config | ~8-12 new tests | Medium -- requires crafting corrupt files and verifying recovery behavior |
| Unhappy-path tests: search edge cases | ~6-10 new tests | Medium -- requires understanding cursor arithmetic and degenerate list states |
| **Total** | ~8 deliverables + ~30-46 new tests | Low-Medium overall |

## Sources

- [Sonarr CONTRIBUTING.md](https://github.com/Sonarr/Sonarr/blob/develop/CONTRIBUTING.md) -- structure: tools, getting started, contributing code, PR rules
- [Sonarr Security Policy](https://github.com/Sonarr/Sonarr/security/policy) -- minimal: Discord + email, 72h response SLA
- [Recyclarr repo](https://github.com/recyclarr/recyclarr) -- has CONTRIBUTING.md, SECURITY.md in .github/, MIT license
- [Overseerr repo](https://github.com/sct/overseerr) -- has CONTRIBUTING.md, CODE_OF_CONDUCT.md, uses GitHub Discussions
- [GitHub Issue Forms Syntax](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms) -- YAML form schema: name, description, body with inputs/dropdowns/checkboxes/textarea
- [GitHub Private Vulnerability Reporting](https://docs.github.com/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability) -- modern alternative to email-based reporting, free for OSS
- [Adding a Security Policy](https://docs.github.com/en/code-security/getting-started/adding-a-security-policy-to-your-repository) -- SECURITY.md placement and GitHub integration
- [FastAPI Contributing Guidelines](https://fastapi.tiangolo.com/contributing/) -- upstream pattern for Python/FastAPI projects
- [Negative Testing in Python](https://medium.com/delivus/negative-testing-in-python-web-applications-with-pytest-db0304234638) -- pytest patterns for unhappy paths
- [Pytest Exception Testing](https://pytest-with-eric.com/introduction/pytest-assert-exception/) -- pytest.raises patterns with match validation
