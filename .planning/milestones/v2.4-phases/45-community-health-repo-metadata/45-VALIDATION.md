---
phase: 45
slug: community-health-repo-metadata
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-09
---

# Phase 45 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (pytest-asyncio) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_community_health.py tests/test_github_templates.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~0.03 seconds (phase tests), ~30 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_community_health.py tests/test_github_templates.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 45-01-01 | 01 | 1 | COMM-01 | T-45-02 | Dev commands public, no secrets | content | `uv run pytest tests/test_community_health.py::TestContributing -x -q` | ✅ | ✅ green |
| 45-01-02 | 01 | 1 | COMM-02, COMM-03 | T-45-01 | Abstraction-level security docs, no internal paths | content | `uv run pytest tests/test_community_health.py::TestSecurity -x -q` | ✅ | ✅ green |
| 45-01-03 | 01 | 1 | D-03 | — | N/A | content | `uv run pytest tests/test_community_health.py::TestLicense -x -q` | ✅ | ✅ green |
| 45-02-01 | 02 | 1 | COMM-04 | T-45-03 | Config excerpt warns about API key redaction | content | `uv run pytest tests/test_github_templates.py::TestBugReportTemplate -x -q` | ✅ | ✅ green |
| 45-02-02 | 02 | 1 | COMM-05 | — | N/A | content | `uv run pytest tests/test_github_templates.py::TestFeatureRequestTemplate -x -q` | ✅ | ✅ green |
| 45-02-03 | 02 | 1 | COMM-06 | — | N/A | content | `uv run pytest tests/test_github_templates.py::TestIssueTemplateConfig -x -q` | ✅ | ✅ green |
| 45-02-04 | 02 | 1 | COMM-07 | — | N/A | content | `uv run pytest tests/test_github_templates.py::TestPRTemplate -x -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 7 GitHub topics visible on repo page | META-01 | GitHub API-side config, not testable locally | Visit repo page, confirm topics: radarr, sonarr, automation, selfhosted, arr, docker, python |
| Discussions tab enabled with General and Q&A categories | META-02 | GitHub API-side config, not testable locally | Click Discussions tab, confirm it exists with default categories |
| Issue forms render as structured forms (not blank textarea) | COMM-04, COMM-05 | GitHub-side rendering | Click New Issue, confirm bug report and feature request forms appear |
| PR template renders with CI checklist | COMM-07 | GitHub-side rendering | Open a new PR, confirm template auto-populates |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-09
