---
gsd_state_version: 1.0
milestone: v2.9
milestone_name: Launch-Hardening / Sibling Consistency
status: planning
stopped_at: Phase 71 context gathered
last_updated: "2026-06-02T21:37:52.254Z"
last_activity: 2026-06-02
progress:
  total_phases: 5
  completed_phases: 3
  total_plans: 5
  completed_plans: 5
  percent: 60
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-02)

**Core value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.
**Current focus:** Phase 71 — presentation rewrite

## Current Position

Phase: 71
Plan: Not started
Status: Ready to plan
Last activity: 2026-06-02

Progress: [██████████] 100%

**Next step:** `/gsd:plan-phase 68`

### v2.9 milestone shape

Two largely-disjoint tracks (Python code vs. Markdown/docs/repo-metadata), each opening with a discovery/hostile pass that GATES the subsequent fix work. Work isolated on a `launch-hardening` branch; `main` stays releasable; merge + tag **v2.9.0** handled by the orchestrator at milestone-end (`release_intent=true`), not as a roadmap phase. Spec: `docs/superpowers/specs/2026-06-02-launch-hardening-design.md`.

| Phase | Goal | Requirements | Depends on |
|-------|------|--------------|------------|
| 68 — Code-track hostile-reader discovery | Hostile code+history sweep → one triaged findings artifact that gates fix scope | CDISC-01..05 | — |
| 69 — Code-track hardening | `.orchestrator.json` gitignore audit + SAFETY-03 failure-counter unification (with test) + every fold-in finding | CHARD-01..04 | Phase 68 |
| 70 — Presentation discovery | Cynical-reader teardown + codex pass + SeedSyncarr cross-repo consistency audit → critique artifacts | PDISC-01..03 | Phase 69 |
| 71 — Presentation rewrite | Rewrite README / SECURITY.md / community-health / repo-metadata text / release notes + in-app changelog; Playwright screenshots at walkthrough | PREW-01..07 | Phase 70 |

### v2.8 ship record

Shipped 2026-06-01. Audit passed (16/16 requirements — `.planning/milestones/v2.8-MILESTONE-AUDIT.md`); deep-review APPROVED (`.turingmind/REVIEW.md`); live walkthrough passed (caught + fixed the settings-save form bug, `542d5dd`). Released as **v2.8.0** (pyproject + `__version__` bumped, git tag `v2.8.0`), pushed to origin/main. 961 tests passing, ruff clean.

### v2.8.1 patch (post-archive, 2026-06-01)

Out-of-cycle security patch on top of the archived v2.8 milestone (no full GSD phase — hotfix scope).

- **Fix:** `change_password` now rotates `session_secret`, invalidating all other sessions on password change while re-issuing the acting user's cookie (CWE-613). Supersedes v2.6 threat decision T-58-07/AR-58-02 (was *accept*, now *mitigate*). Deep-reviewed (APPROVED), docs + threat model reconciled. Commits `0866332` (fix) + `0e745ab` (tests).
- **CI:** all workflow actions bumped to Node 24 majors (PR #20, squash `d538554`) ahead of GitHub's 2026-06-16 Node 20 forced cutover.
- Released as **v2.8.1** (git tag `v2.8.1`, container published); 965 tests passing, ruff clean.

## Performance Metrics

**Overall:**

- Total plans completed: 159 across 14 shipped milestones (through v2.8)
- Milestones shipped: 14 (v1.0, v1.1, v1.2, v2.0, v2.1, v2.2, v2.3, v2.4, v2.5, v2.6, v2.7, v2.8)
- Tests passing: 965 (post v2.8.1)
- Phases completed: 67 (through v2.8)

## Accumulated Context

### Decisions

Full decision log in PROJECT.md Key Decisions table. v2.9 design decisions (D-1..D-12) in `docs/superpowers/specs/2026-06-02-launch-hardening-design.md` §2.

- [Phase ?]: Phase 68 discovery: history scan CLEAN (1038 commits all-refs, no real secret); 4 FOLD-IN findings P68-FI-001..004 gate Phase 69 CHARD-04 fix scope

### Pending Todos

None.

### Roadmap Evolution

v2.7 shipped as planned (4 phases, 8 plans, all 22 requirements satisfied). Phase 63 inserted mid-milestone as gap-closure for HDR-06 (favicon asset quality deferral from Phase 60 D-05) — closed cleanly in 1 plan + 1 day.

v2.8 roadmap created 2026-05-25 from codebase audit (CONCERNS.md). 16 v1 requirements across 4 phases (64-67). No deferred requirements — 100% coverage in milestone scope.

v2.9 roadmap created 2026-06-02 from the launch-hardening design spec. 19 v1 requirements across 4 phases (68-71, continuing from v2.8's Phase 67 — not reset to 1). Two disjoint tracks, each gated by a discovery phase: code (68→69) and presentation (70→71). 100% coverage; config-knob UI debt (DEBT-03/06/07/08) and v2.6 UI-01..03 pixel verification explicitly parked to v2 (spec D-5). Flat phase layout (`.planning/phases/<N>-<slug>/`) per the v2.7/v2.8 convention.

### Key v2.9 Phasing Rationale

- **Phase 68 first (discovery gates fix):** The hostile-reader sweep (ruff whole-tree + Shield SAST/secrets/dep-audit + git-history secrets scan + entry-point skim) must produce the triaged findings artifact *before* Phase 69 can know its full fix scope. Per spec D-3, only genuinely high-visibility findings fold into Phase 69; everything else is parked with rationale in the same artifact. The git-history scan (CDISC-03) is the launch-visible-risk addition unique to an already-public repo with 13 milestones of commits.
- **Phase 69 second (code hardening), depends on 68:** Closes the curated known items — `.orchestrator.json` gitignore audit-and-close (CHARD-01; confirmed as of 2026-06-02 that `.DS_Store`/`.playwright-mcp/` are already ignored, so this is audit-and-close not a fixed checklist) and SAFETY-03 manual/scheduled failure-counter unification (CHARD-02) with a covering test (CHARD-03) — plus every fold-in finding from Phase 68 (CHARD-04). SAFETY-03 bar: the `# TODO` at `scheduler.py:~325` is resolved; no existing scheduler failure-counter test deleted/skipped.
- **Phase 70 third (presentation discovery):** Cynical-reader teardown (PDISC-01) + codex adversarial pass against existing README/docs (PDISC-02) + same-author cross-repo consistency audit vs SeedSyncarr (PDISC-03). Touches docs/Markdown only — disjoint from the code track, so it *could* run in parallel with 68/69, but is sequenced after 69 for a clean single-threaded milestone. Its critique artifacts gate Phase 71.
- **Phase 71 last (presentation rewrite), depends on 70:** Rewrites README/SECURITY.md/community-health/repo-metadata text/release notes + in-app changelog (PREW-01,03,04,05,06,07) driven by Phase 70's critique. PREW-02 (fresh Playwright screenshots) is captured at the milestone-end NAS walkthrough against the deployed branch build, so that requirement's verification completes at walkthrough time, not mid-phase. PREW-07 cross-repo signal reconciliation closes the loop with the PDISC-03 audit.

### Cross-cutting thread

The only coupling between the two tracks is the *security framing*: the v2.8/v2.8.1 hardening the code track confirms intact (CSP nonces, session rotation on password change, `apikey=` rejection, Basic-auth control-char validation) is the same posture the presentation track states plainly as a selling point in README/SECURITY.md (PREW-03).

### Blockers/Concerns

None.

### Deferred Items

Items parked this milestone (spec D-5 / §3.3) and carried forward:

| Category | Item | Source Milestone | Status |
|----------|------|------------------|--------|
| v2 requirement | DEBT-07: Expose HTTP request timeout in settings UI | v2.9 (spec D-5) | parked (invisible to launch reader) |
| v2 requirement | DEBT-08: Expose *arr API page size in settings UI | v2.9 (spec D-5) | parked (invisible to launch reader) |
| v2 requirement | DEBT-03: Expose search-history cap in settings UI | v2.9 (spec D-5) | parked (invisible to launch reader) |
| v2 requirement | DEBT-06: Surface graceful-shutdown drain timeout in settings UI | v2.9 (spec D-5) | parked (invisible to launch reader) |
| requirement | UI-01: Login page pixel-exact visual verification | v2.6 | human_needed (behind first-run setup, not launch-visible) |
| requirement | UI-02: Setup page pixel-exact visual verification | v2.6 | human_needed (behind first-run setup, not launch-visible) |
| requirement | UI-03: Settings security pixel-exact visual verification | v2.6 | human_needed (behind first-run setup, not launch-visible) |
| tech-debt | `--color-triggarr-primaryDark` duplicate token (unused in templates) | v2.7 | cosmetic cleanup (invisible to launch reader) |
| v2 requirement | PERF-01: Per-endpoint request timeout overrides | v2.8 audit | deferred |
| v2 requirement | PERF-02: Per-endpoint pagination page-size overrides | v2.8 audit | deferred |
| v2 requirement | PERF-03: State JSON streaming/compression | v2.8 audit | deferred |
| v2 requirement | SCALE-01: Lift 5-instance-per-app-type hard limit | v2.8 audit | deferred |
| v2 requirement | SCALE-02: Search history archival / PostgreSQL path | v2.8 audit | deferred |
| v2 requirement | AUDIT-01: Config change audit log | v2.8 audit | deferred |
| v2 requirement | OBS-01: Scheduler job dashboard | v2.8 audit | deferred |
| Phase 68 P01 | 25min | 5 tasks | 1 files |

### Quick Tasks Completed

| Date | Task | Outcome |
|------|------|---------|
| 2026-05-19 | Address Dependabot alerts and PR | Merged PR #19 (idna 3.11→3.15, squash cc61133). Closes alert #12 (CVE-2026-45409, IDNA encoding bypass, medium). |

### Reference Artifacts

- `docs/superpowers/specs/2026-06-02-launch-hardening-design.md` -- v2.9 design spec (source of truth for this milestone)
- `.planning/milestones/v2.8-ROADMAP.md` -- archived v2.8 roadmap
- `.planning/milestones/v2.7-ROADMAP.md` -- archived v2.7 roadmap
- `.planning/milestones/v2.7-REQUIREMENTS.md` -- archived v2.7 requirements
- `.planning/milestones/v2.7-MILESTONE-AUDIT.md` -- archived v2.7 milestone audit
- `.aidesigner/runs/2026-04-16T00-05-51-229Z-triggarr-full-dashboard-redesign-v3-/design.html` -- v2.7 design spec (preserved for future reference)
- `.planning/milestones/v2.6-ROADMAP.md` -- archived v2.6 roadmap
- `.planning/codebase/CONCERNS.md` -- v2.8 source audit (2026-05-25); file:line pointers

## Session Continuity

Last session: 2026-06-02T21:37:52.250Z
Stopped at: Phase 71 context gathered
Resume file: .planning/phases/71-presentation-rewrite/71-CONTEXT.md

## Operator Next Steps

- Confirm the working branch is `launch-hardening` before planning (all v2.9 work is branch-isolated; `main` stays releasable).
- Plan the first phase: `/gsd:plan-phase 68`
