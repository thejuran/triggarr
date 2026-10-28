# Phase 85: Follow-on CI Improvements & Acceptance Usability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-26
**Phase:** 85-follow-on-ci-improvements-acceptance-usability
**Areas discussed:** Docs-only check path, Automated update PRs, Security-scan blocking rules, Scope edges

---

## Docs-only check path (ACCEPT-03)

| Option | Description | Selected |
|--------|-------------|----------|
| No — full checks always | Every PR runs every required check; classification can never reduce checks; GitHub requires nothing the policy exempts; needs ACCEPT-03 wording note | ✓ |
| Yes — real fast path | Content checker skips image/browser jobs for ordinary-docs-only diffs; new safeguard with misclassification risk | |

**User's choice:** No — full checks always

| Option | Description | Selected |
|--------|-------------|----------|
| Permanent test + this PR | Permanent no-skip wiring test with four-case fixtures; phase PR is the real GitHub run; no throwaway PRs | ✓ |
| Four throwaway draft PRs | One isolated draft PR per case; strongest evidence; 4+ pushes, Greptile credits, bends no-docs-only-PRs rule | |

**User's choice:** Permanent test + this PR

---

## Automated update PRs (CIMAINT-02)

| Question | Options | Selected |
|----------|---------|----------|
| Cadence | Monthly / Weekly | Monthly |
| Grouping | Per ecosystem, majors split / One PR for everything | Per ecosystem, majors split |
| Security updates | Immediate separate PR / Wait for next cycle | Immediate separate PR |
| Bot PR review | Same as any code PR / Lighter lane (CI + Codex only) | Same as any code PR |

---

## Security-scan blocking rules (CIMAINT-03)

| Question | Options | Selected |
|----------|---------|----------|
| What blocks | Critical + High with fix / Critical only with fix / Any severity with fix | Critical + High, fix available |
| Unfixed vulns | Report, don't block / Block Critical even if unfixed | Report, don't block |
| Exceptions | Owner approves, 30-day expiry / Owner approves, 90-day expiry | Owner approves, 30-day expiry |
| Where gate applies | Everywhere incl. publish / PRs only, report on publish | Everywhere, incl. publish |

---

## Scope edges

| Question | Options | Selected |
|----------|---------|----------|
| Wheel/sdist release assets | Drop them / Keep + smoke-test | Drop them |
| Phase 83 carry-forward to fold (multi) | Codex fallback definition; Review-list drift guard; Codex runner hardening | All three |

**Notes:** planchk-router CI tests already owner-decided 2026-10-26 (not re-asked). Card-template refactor and craft-skill clone left out by Claude as out of theme / needing separate approval.

---

## Claude's Discretion

Scanner choice; Dockerfile uv.lock mechanics; actionlint wiring and skip rule; coverage tooling; release-job split for least privilege; exact Dependabot keys/limits/day; acceptance-register redesign (PR+SHA keyed, serialize until proven) presented to owner as Claude's approach, not questioned.

## Deferred Ideas

- Docs-only CI fast path (revisit only if docs-only changes become common)
- Wheel clean-install smoke test (only if a pip/PyPI path returns)
- Card-template text-matching refactor; craft-skill `code-reviewer` sticky accept
