---
phase: 45-community-health-repo-metadata
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - .github/ISSUE_TEMPLATE/bug-report.yml
  - .github/ISSUE_TEMPLATE/feature-request.yml
  - .github/ISSUE_TEMPLATE/config.yml
  - .github/pull_request_template.md
autonomous: false
requirements:
  - COMM-04
  - COMM-05
  - COMM-06
  - COMM-07
  - META-01
  - META-02
must_haves:
  truths:
    - "A user clicking New Issue sees a bug report form with dropdowns for version, deployment method, and app type"
    - "A user clicking New Issue sees a feature request form with description, use case, and alternatives fields"
    - "Blank issues are disabled and a Discussions contact link is shown"
    - "A contributor opening a PR sees a checklist with tests pass, ruff clean, Docker builds"
    - "The repo is discoverable via GitHub topics and has Discussions enabled"
  artifacts:
    - path: ".github/ISSUE_TEMPLATE/bug-report.yml"
      provides: "Bug report YAML form template"
      contains: "type: dropdown"
    - path: ".github/ISSUE_TEMPLATE/feature-request.yml"
      provides: "Feature request YAML form template"
      contains: "use case"
    - path: ".github/ISSUE_TEMPLATE/config.yml"
      provides: "Issue template config with blank_issues_enabled: false"
      contains: "blank_issues_enabled: false"
    - path: ".github/pull_request_template.md"
      provides: "PR template with CI checklist"
      contains: "- [ ]"
  key_links:
    - from: ".github/ISSUE_TEMPLATE/config.yml"
      to: "GitHub Discussions"
      via: "contact_links URL"
      pattern: "discussions"
    - from: ".github/pull_request_template.md"
      to: ".github/workflows/ci.yml"
      via: "checklist mirrors CI jobs"
      pattern: "tests pass"
---

<objective>
Create GitHub issue templates (bug report + feature request YAML forms), issue config (blank issues disabled + Discussions link), PR template (CI checklist), and configure repo metadata (topics + Discussions).

Purpose: Users get structured issue forms instead of blank textareas, contributors get a PR checklist, and the repo is discoverable.
Output: Issue templates, PR template in .github/, repo metadata configured via gh CLI.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.github/workflows/ci.yml
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create issue templates, PR template, and config</name>
  <files>.github/ISSUE_TEMPLATE/bug-report.yml, .github/ISSUE_TEMPLATE/feature-request.yml, .github/ISSUE_TEMPLATE/config.yml, .github/pull_request_template.md</files>
  <read_first>
    - .github/workflows/ci.yml (CI checks: test, lint, docker -- PR checklist must mirror these; version/environment info useful for bug reports)
    - .planning/REQUIREMENTS.md (COMM-04, COMM-05, COMM-06, COMM-07 exact field specs)
  </read_first>
  <action>
Create the `.github/ISSUE_TEMPLATE/` directory and four files total:

**bug-report.yml** (per D-05 YAML forms with dropdowns, per D-06 optional config excerpt, per COMM-04):

```yaml
name: Bug Report
description: Report a bug in Triggarr
title: "[Bug]: "
labels: ["bug"]
body:
  - type: dropdown
    id: version
    attributes:
      label: Triggarr Version
      options:
        - v2.4
        - v2.3
        - v2.2
        - Older
    validations:
      required: true
  - type: dropdown
    id: deployment
    attributes:
      label: Deployment Method
      options:
        - Docker Compose
        - Docker run
        - Bare metal
    validations:
      required: true
  - type: dropdown
    id: app-type
    attributes:
      label: App Type
      options:
        - Radarr
        - Sonarr
        - Both
    validations:
      required: true
  - type: textarea
    id: description
    attributes:
      label: Description
      description: What happened?
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
      description: What did you expect to happen?
    validations:
      required: true
  - type: textarea
    id: logs
    attributes:
      label: Relevant Logs
      description: Paste any relevant log output
      render: text
    validations:
      required: false
  - type: textarea
    id: config
    attributes:
      label: Config Excerpt
      description: "Paste relevant config sections. **Remove API keys before pasting.**"
      render: toml
    validations:
      required: false
```

**feature-request.yml** (per COMM-05):

```yaml
name: Feature Request
description: Suggest a feature for Triggarr
title: "[Feature]: "
labels: ["enhancement"]
body:
  - type: textarea
    id: description
    attributes:
      label: Description
      description: What feature would you like?
    validations:
      required: true
  - type: textarea
    id: use-case
    attributes:
      label: Use Case
      description: Why do you need this? What problem does it solve?
    validations:
      required: true
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives Considered
      description: Have you considered any workarounds or alternative approaches?
    validations:
      required: false
```

**config.yml** (per D-07, per COMM-06):

```yaml
blank_issues_enabled: false
contact_links:
  - name: Questions & Discussion
    url: https://github.com/thejuran/triggarr/discussions
    about: Ask questions and share ideas in Discussions
```

**.github/pull_request_template.md** (per D-04 CI checklist only, minimal friction):

```markdown
## Changes



## CI Checklist

- [ ] Tests pass (`uv run pytest tests/ -x -q`)
- [ ] Ruff clean (`uv run ruff check triggarr/ tests/`)
- [ ] Docker builds (`docker build -t triggarr:local .`)
```

The PR template has an open "Changes" section (blank, contributor fills in) and the CI checklist with the three items matching the three CI jobs in ci.yml (test, lint, docker). Per D-04: no other structured sections, just the checklist.
  </action>
  <verify>
    <automated>grep -q "type: dropdown" .github/ISSUE_TEMPLATE/bug-report.yml && grep -q "Remove API keys" .github/ISSUE_TEMPLATE/bug-report.yml && grep -q "use-case" .github/ISSUE_TEMPLATE/feature-request.yml && grep -q "blank_issues_enabled: false" .github/ISSUE_TEMPLATE/config.yml && grep -q "discussions" .github/ISSUE_TEMPLATE/config.yml && grep -q "uv run pytest" .github/pull_request_template.md && grep -q "docker build" .github/pull_request_template.md && echo "PASS"</automated>
  </verify>
  <acceptance_criteria>
    - .github/ISSUE_TEMPLATE/bug-report.yml exists with three "type: dropdown" blocks (version, deployment, app type per D-05)
    - bug-report.yml contains dropdown options "v2.4", "v2.3", "v2.2", "Older" for version
    - bug-report.yml contains dropdown options "Docker Compose", "Docker run", "Bare metal" for deployment
    - bug-report.yml contains dropdown options "Radarr", "Sonarr", "Both" for app type
    - bug-report.yml contains "Remove API keys" in config excerpt field (per D-06)
    - bug-report.yml config excerpt field has "required: false" (optional per D-06)
    - .github/ISSUE_TEMPLATE/feature-request.yml exists with "use-case" and "alternatives" fields
    - .github/ISSUE_TEMPLATE/config.yml contains "blank_issues_enabled: false" and "github.com/thejuran/triggarr/discussions" (per D-07)
    - .github/pull_request_template.md contains exactly 3 "- [ ]" checklist items
    - PR template contains "uv run pytest tests/ -x -q", "uv run ruff check triggarr/ tests/", "docker build -t triggarr:local ."
  </acceptance_criteria>
  <done>Four GitHub template files created: bug report with dropdowns and optional config excerpt, feature request with use case and alternatives, config with blank issues disabled and Discussions link, PR template with CI checklist</done>
</task>

<task type="auto">
  <name>Task 2: Set GitHub topics and enable Discussions</name>
  <files>N/A (GitHub API calls only)</files>
  <read_first>
    - .planning/REQUIREMENTS.md (META-01 topic list, META-02 Discussions categories)
  </read_first>
  <action>
Run these `gh` CLI commands to configure repo metadata:

1. Set GitHub topics (per META-01):
```bash
gh repo edit thejuran/triggarr --add-topic radarr --add-topic sonarr --add-topic automation --add-topic selfhosted --add-topic arr --add-topic docker --add-topic python
```

2. Enable GitHub Discussions (per META-02):
```bash
gh repo edit thejuran/triggarr --enable-discussions
```

Note: GitHub automatically creates General and Q&A categories when Discussions is first enabled. If those categories do not appear after enabling, note this for the human verification step.
  </action>
  <verify>
    <automated>gh repo view thejuran/triggarr --json repositoryTopics | grep -q "radarr" && gh repo view thejuran/triggarr --json hasDiscussionsEnabled | grep -q "true" && echo "PASS"</automated>
  </verify>
  <acceptance_criteria>
    - `gh repo view thejuran/triggarr --json repositoryTopics` output contains "radarr", "sonarr", "automation", "selfhosted", "arr", "docker", "python"
    - `gh repo view thejuran/triggarr --json hasDiscussionsEnabled` output contains "true"
  </acceptance_criteria>
  <done>Repository has 7 topics set and Discussions enabled</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Verify templates and metadata on GitHub</name>
  <files>N/A</files>
  <action>
Pause for human verification of all GitHub-side changes. The executor presents the verification steps below and waits for the user to confirm.
  </action>
  <what-built>
All community health files are committed and pushed. GitHub topics are set and Discussions is enabled. Issue templates and PR template are in place.
  </what-built>
  <how-to-verify>
1. Visit https://github.com/thejuran/triggarr -- confirm 7 topics appear under the repo name (radarr, sonarr, automation, selfhosted, arr, docker, python)
2. Click the "Discussions" tab -- confirm it exists and has General and Q&A categories
3. Click "New Issue" -- confirm you see bug report and feature request forms (not a blank textarea), and a link to Discussions
4. Open "New Pull Request" against a test branch -- confirm the PR template appears with the CI checklist
  </how-to-verify>
  <verify>
    <automated>echo "Human verification required"</automated>
  </verify>
  <done>User confirms all templates render correctly on GitHub and topics/Discussions are visible</done>
  <resume-signal>Type "approved" or describe any issues</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Issue template inputs -> maintainer | User-submitted issues are untrusted input; templates structure but do not sanitize |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-45-03 | Information Disclosure | bug-report.yml config excerpt | mitigate | Config excerpt field includes explicit warning: "Remove API keys before pasting." Field is optional (required: false). |
| T-45-04 | Spoofing | Issue templates | accept | GitHub handles authentication for issue submission. Templates cannot prevent spoofed reports, but this is standard for public repos. |
</threat_model>

<verification>
- All four .github files exist: ISSUE_TEMPLATE/bug-report.yml, ISSUE_TEMPLATE/feature-request.yml, ISSUE_TEMPLATE/config.yml, pull_request_template.md
- Bug report has YAML form with three dropdowns and optional config excerpt with redaction warning
- Feature request has description, use case, alternatives fields
- Config has blank_issues_enabled: false and Discussions link
- PR template has three CI checklist items matching ci.yml jobs
- GitHub topics set and Discussions enabled
</verification>

<success_criteria>
- Users see structured forms (not blank textarea) when opening issues
- Blank issues are disabled with Discussions contact link
- PR template shows CI checklist
- Repo has 7 topics and Discussions with General + Q&A categories
</success_criteria>

<output>
After completion, create `.planning/phases/45-community-health-repo-metadata/45-02-SUMMARY.md`
</output>
