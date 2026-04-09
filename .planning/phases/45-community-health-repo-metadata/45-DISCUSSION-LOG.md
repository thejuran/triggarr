# Phase 45: Community Health & Repo Metadata - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-09
**Phase:** 45-community-health-repo-metadata
**Areas discussed:** CONTRIBUTING.md tone & depth, License, PR template sections, Issue template strictness

---

## CONTRIBUTING.md Tone & Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Quick reference (Recommended) | Concise: prerequisites, fork/branch/PR steps, dev commands. Assumes contributor knows git. | ✓ |
| Beginner-friendly walkthrough | Step-by-step with explanations for first-time OSS contributors. | |
| Detailed with architecture | Quick reference + brief architecture overview of FastAPI routes, htmx templates, key modules. | |

**User's choice:** Quick reference
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, conventional commits | feat:, fix:, docs:, test: prefixes. Matches GSD commit style. | ✓ |
| No conventions | Just descriptive messages. Less friction. | |
| You decide | Claude picks. | |

**User's choice:** Yes, conventional commits
**Notes:** None

---

## License

| Option | Description | Selected |
|--------|-------------|----------|
| MIT (Recommended) | Permissive, simple, widely understood. Most contributor-friendly. | ✓ |
| Apache 2.0 | Permissive with patent grant. Used by VolvLog. | |
| GPL v3 | Copyleft. Used by DVC Dashboard. | |
| Skip license for now | Don't add LICENSE in this phase. | |

**User's choice:** MIT
**Notes:** None

---

## PR Template Sections

| Option | Description | Selected |
|--------|-------------|----------|
| CI checklist only (Recommended) | Just the checklist: tests pass, ruff clean, Docker builds. Minimal friction. | ✓ |
| Structured sections | Description, Changes, Test Plan, CI Checklist sections. | |
| Checklist + description prompt | Brief 'What does this PR do?' prompt plus CI checklist. | |

**User's choice:** CI checklist only
**Notes:** None

---

## Issue Template Strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Dropdowns where possible (Recommended) | Version, deployment, app type as dropdowns. Easier to triage. | ✓ |
| All free text | Labeled text areas only. Less friction but inconsistent. | |
| Mix: dropdowns + free text | Dropdowns for structured fields, free text for descriptions. | |

**User's choice:** Dropdowns where possible
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Optional field (Recommended) | Include config field but don't require it. Redaction warning included. | ✓ |
| Required with redaction note | Required, with clear warning to redact API keys. | |
| No config field | Skip entirely. Ask in comments if needed. | |

**User's choice:** Optional field
**Notes:** None

---

## Claude's Discretion

- SECURITY.md structure and depth (follow requirements COMM-02, COMM-03)
- Feature request template fields (follow COMM-05)
- GitHub topics exact list (follow META-01)
- Discussions categories (follow META-02)

## Deferred Ideas

None — discussion stayed within phase scope.
