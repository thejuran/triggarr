---
phase: 71-presentation-rewrite
plan: "03"
subsystem: community-health
tags: [github-templates, dropdowns, snapshot-tests, audit]
dependency_graph:
  requires: []
  provides: [PREW-04]
  affects: [.github/ISSUE_TEMPLATE/bug-report.yml, tests/test_github_templates.py]
tech_stack:
  added: []
  patterns: [yaml.safe_load per-option list-membership assertion]
key_files:
  created: []
  modified:
    - .github/ISSUE_TEMPLATE/bug-report.yml
    - tests/test_github_templates.py
decisions:
  - "D-10: bug-report.yml version dropdown updated (v2.8.1, v2.8, v2.7, v2.6, v2.5, v2.4, Older) and App Type dropdown updated (Radarr, Sonarr, Lidarr, All); snapshot tests strengthened to per-option list membership with absent-option assertions"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-02"
  tasks: 2
  files: 2
---

# Phase 71 Plan 03: Community-Health Bug-Report Dropdowns + Snapshot Tests Summary

**One-liner:** Version dropdown updated to v2.8.1..v2.4 + App Type gains Lidarr/All; snapshot assertions strengthened to per-option YAML list membership with absent-option checks.

## What Was Done

### Task 1: Update bug-report.yml version + App Type dropdowns and strengthen snapshot assertions

**bug-report.yml changes:**
- Version dropdown `options` replaced: `v2.3, v2.2, v2.1, Older` → `v2.8.1, v2.8, v2.7, v2.6, v2.5, v2.4, Older` (7 options, matching current release history from latest v2.8.1 down to v2.4)
- App Type dropdown `options` replaced: `Radarr, Sonarr, Both` → `Radarr, Sonarr, Lidarr, All` (Lidarr added as first-class app; "Both" replaced by the more accurate "All")
- YAML structure, labels, ids, indentation unchanged; only the two `options:` lists changed
- YAML parses cleanly: `yaml.safe_load` exits 0

**test_github_templates.py changes:**
- `test_version_dropdown_options`: Strengthened from loose whole-file `in content` substring check to per-option list membership. Loads YAML via `yaml.safe_load`, extracts `data["body"][0]["attributes"]["options"]` (the version dropdown at body index 0), asserts each expected option (`v2.8.1, v2.8, v2.7, v2.6, v2.5, v2.4, Older`) is a discrete list entry, AND asserts `v2.3` is absent.
- `test_app_type_dropdown_options`: Same strengthening. Extracts `data["body"][2]["attributes"]["options"]` (App Type dropdown at body index 2), asserts `Radarr, Sonarr, Lidarr, All` are present, AND asserts `Both` is absent.
- `test_deployment_dropdown_options`: Unchanged (deployment dropdown not modified).
- All other tests in the class (test_valid_yaml, test_has_dropdowns, test_config_excerpt_redaction_warning, test_config_excerpt_is_optional, TestFeatureRequestTemplate, TestIssueTemplateConfig, TestPRTemplate) remain untouched and green.

**Verification:** `uv run pytest tests/test_github_templates.py -x -q` — 21 passed.

**Commit:** ea5f725

### Task 2: Confirm remaining community-health files present and accurate (PREW-04)

Audit-only pass — no files modified.

**CONTRIBUTING.md** (present, accurate): Contains dev setup (`uv sync --extra dev`), test/lint/Docker commands matching CI, conventional commit prefixes (feat/fix/docs/test/refactor), fork workflow, PR workflow. The Tailwind dev-command line is intentionally not edited here — plan 05 owns that file for the Tailwind command correction (avoids parallel-wave file conflict). No factual drift beyond what plan 05 addresses.

**PR template (.github/pull_request_template.md)** (present, accurate): Exactly 3 checklist items — pytest (`uv run pytest tests/ -x -q`), ruff (`uv run ruff check triggarr/ tests/`), Docker build (`docker build -t triggarr:local .`). No drift.

**feature-request.yml** (present, accurate): YAML valid, name="Feature Request", use-case field present, alternatives field present. No drift.

**config.yml** (present, accurate): `blank_issues_enabled: false`, GitHub Discussions contact link pointing to `github.com/thejuran/triggarr/discussions`. No drift.

**LICENSE** (present, accurate): MIT License, copyright year 2026, "Triggarr Contributors". No drift.

**Verification:** `uv run pytest tests/test_community_health.py tests/test_github_templates.py -x -q` — 42 passed (0 failures).

## Deviations from Plan

None — plan executed exactly as written.

## Community-Health Confirmation (PREW-04)

All four community-health file groups confirmed present and accurate:

| File | Status | Notes |
|------|--------|-------|
| CONTRIBUTING.md | Present, accurate | Tailwind dev-command owned by plan 05 (not touched here) |
| .github/pull_request_template.md | Present, accurate | 3-item CI checklist matches current commands |
| .github/ISSUE_TEMPLATE/feature-request.yml | Present, accurate | No drift |
| .github/ISSUE_TEMPLATE/config.yml | Present, accurate | `blank_issues_enabled: false`, Discussions link intact |
| LICENSE | Present, accurate | MIT, 2026, correct |

No drift found requiring a follow-up. The only known pending edit in this file group (CONTRIBUTING.md Tailwind command) is intentionally owned by plan 05 to prevent parallel-wave file conflicts.

## Known Stubs

None.

## Threat Flags

None. This plan edits GitHub issue-template YAML and a test file. No runtime code, no new attack surface, no trust boundary crossed.

## Self-Check

Files confirmed:
- `.github/ISSUE_TEMPLATE/bug-report.yml` — contains `v2.8.1`, `v2.4`, `Lidarr`, `All`; does NOT contain standalone `- v2.3` or `- Both`
- `tests/test_github_templates.py` — contains `v2.8.1` and `Lidarr` assertions; uses `yaml.safe_load` per-option list membership

Commits confirmed:
- ea5f725 — fix(71-03): update bug-report.yml dropdowns + strengthen snapshot assertions

## Self-Check: PASSED
