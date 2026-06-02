# Phase 68: Code-track hostile-reader discovery - Discussion Log

> **Audit trail only.** Not consumed by downstream agents (researcher, planner, executor).
> Decisions captured in `68-CONTEXT.md`.

**Date:** 2026-06-02
**Phase:** 68-code-track-hostile-reader-discovery
**Mode:** discuss

## Areas Discussed

### Findings artifact format & location
- **Options presented:** Structured MD in phase dir (per-source tables, FOLD-IN/PARKED tags) / Top-level CONCERNS-style doc / Let the planner decide.
- **Selected:** Structured MD in phase dir → `68-FINDINGS.md`, one table per source, each row classified FOLD-IN/PARKED with rationale + file:line. Phase 69 reads FOLD-IN rows as its fix checklist.
- **Why:** Keeps milestone-specific triage with the phase artifacts (committed), and makes the gate mechanically consumable by Phase 69's CHARD-04 without re-investigation.

### Fold-in vs parked severity bar
- **Options presented:** Launch-visible OR security / Security-only fold-in / Any real finding folds in.
- **Selected:** Launch-visible OR security — FOLD-IN if (a) visible to a repo/README/git-log browser OR (b) any real security/secret exposure; PARK pure-internal nitpicks with rationale.
- **Why:** Operationalizes spec D-3's "launch-visible" bound while treating secrets as always-fold-in. Avoids both under-scoping (missing visible sloppiness) and scope-ballooning into invisible debt the spec parks (D-5).

### git-history secrets scan handling
- **Options presented:** Scan full history + triage each hit (rotate-then-document) / history report-only.
- **Selected:** Scan full history honoring `.gitleaksignore`; any non-allowlisted hit = potential real exposure, triaged highest-priority; clean result stated explicitly.
- **Why:** Repo is already public with 13 milestones of history — an old-commit leak is already exposed. Report-only would leave a real leak live.

### Entry-point skim depth
- **Options presented:** Hostile-reader skim (not full audit) / Thorough per-file audit.
- **Selected:** Hostile-reader skim — ~2-min "what would a skeptical engineer flag" framing per file; deep correctness analysis left to the turingmind deep-review gate on Phase 69's diff.
- **Why:** Keeps Phase 68 lightweight and gating; avoids duplicating the deep review that already runs downstream.

## Claude's Discretion (noted, not asked)
- Exact `68-FINDINGS.md` column layout, tool run order, ruff per-violation vs summary, optional scan-provenance header.

## Deferred Ideas
- Config-knob UI debt (DEBT-03/06/07/08) — pre-parked by spec D-5, must not be folded in.
- UI-01/02/03 auth-page verification — out of scope.
- Fixing fold-in findings — Phase 69.

## Tooling availability confirmed during discussion
- gitleaks 8.30.1, semgrep (installed), Shield plugin 0.3.1, pip-audit — all present. No gray area premised on missing tools.
