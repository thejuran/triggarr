---
gsd_state_version: 1.0
milestone: v2.8
milestone_name: Hardening & Observability
status: ready_to_plan
stopped_at: Phase 65 complete (4/4) — ready to discuss Phase 66
last_updated: 2026-05-26T03:59:16.618Z
last_activity: 2026-05-26 -- Phase 65 execution started
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 8
  completed_plans: 16
  percent: 25
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-25)

**Core value:** Reliably trigger searches in Radarr, Sonarr, and Lidarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback — without exposing credentials or expanding attack surface.
**Current focus:** Phase 66 — security hardening

## Current Position

Phase: 66
Plan: Not started
Status: Ready to plan
Last activity: 2026-05-26

```
v2.8 Progress: [                    ] 0% (0/4 phases)
Phase 64: [ ] Data Safety & Config Integrity
Phase 65: [ ] Scheduler Hardening & Resilience
Phase 66: [ ] Security Hardening
Phase 67: [ ] Observability & CSRF Test Coverage
```

## Performance Metrics

**Overall:**

- Total plans completed: 143 across 13 shipped milestones
- Milestones shipped: 13 (v1.0, v1.1, v1.2, v2.0, v2.1, v2.2, v2.3, v2.4, v2.5, v2.6, v2.7)
- Tests passing: 857
- Shipped LOC: ~6,178 Python source + 1,502 HTML templates + 7,184 CSS

## Accumulated Context

### Decisions

Full decision log in PROJECT.md Key Decisions table.

### Pending Todos

None.

### Roadmap Evolution

v2.7 shipped as planned (4 phases, 8 plans, all 22 requirements satisfied). Phase 63 inserted mid-milestone as gap-closure for HDR-06 (favicon asset quality deferral from Phase 60 D-05) — closed cleanly in 1 plan + 1 day.

v2.8 roadmap created 2026-05-25 from codebase audit (CONCERNS.md). 16 v1 requirements across 4 phases (64-67). No deferred requirements — 100% coverage in milestone scope.

### Key v2.8 Phasing Rationale

- **Phase 64 first**: Config write lock (SAFETY-05) and atomic write hardening (SAFETY-04) must exist before Phase 66 adds URL validation through the same config save path. TEST-03 (concurrent save) verifies SAFETY-05 in the same phase per pairing constraint.
- **Phase 65 second**: Scheduler exception narrowing (SAFETY-02/03) and graceful shutdown extension (RES-01) are coupled through `scheduler.py`. TEST-04 (async client cleanup) verifies RES-01. Phase 64's config lock is a prerequisite for scheduler safely reading fresh config.
- **Phase 66 third**: SEC-01 (CSP nonce migration) is the largest item — touches `middleware.py`, base template, and all pages with inline `<script>`. Grouped with SEC-02 (URL apikey= rejection), SEC-03 (Basic auth null-byte), SEC-04 (session secret validation). Depends on Phase 64's config save lock being in place for SEC-02.
- **Phase 67 last**: RES-02 (last-successful-search dashboard) depends on Phase 65's scheduler recording timestamps. RES-03 (tag caching) invalidation hooks into the config save path established in Phase 64. TEST-01 (OriginCheckMiddleware) is greenfield test work with no ordering dependency.

### Blockers/Concerns

None.

### Deferred Items

Items carried forward (not in v2.8 scope):

| Category | Item | Source Milestone | Status |
|----------|------|------------------|--------|
| requirement | UI-01: Login page pixel-exact visual verification | v2.6 | human_needed |
| requirement | UI-02: Setup page pixel-exact visual verification | v2.6 | human_needed |
| requirement | UI-03: Settings security pixel-exact visual verification | v2.6 | human_needed |
| tech-debt | `--color-triggarr-primaryDark` duplicate token (unused in templates) | v2.7 | cosmetic cleanup |
| v2 requirement | PERF-01: Per-endpoint request timeout overrides | v2.8 audit | deferred |
| v2 requirement | PERF-02: Per-endpoint pagination page-size overrides | v2.8 audit | deferred |
| v2 requirement | PERF-03: State JSON streaming/compression | v2.8 audit | deferred |
| v2 requirement | SCALE-01: Lift 5-instance-per-app-type hard limit | v2.8 audit | deferred |
| v2 requirement | SCALE-02: Search history archival / PostgreSQL path | v2.8 audit | deferred |
| v2 requirement | AUDIT-01: Config change audit log | v2.8 audit | deferred |
| v2 requirement | OBS-01: Scheduler job dashboard | v2.8 audit | deferred |

### Quick Tasks Completed

| Date | Task | Outcome |
|------|------|---------|
| 2026-05-19 | Address Dependabot alerts and PR | Merged PR #19 (idna 3.11→3.15, squash cc61133). Closes alert #12 (CVE-2026-45409, IDNA encoding bypass, medium). |

### Reference Artifacts

- `.planning/milestones/v2.7-ROADMAP.md` -- archived v2.7 roadmap
- `.planning/milestones/v2.7-REQUIREMENTS.md` -- archived v2.7 requirements
- `.planning/milestones/v2.7-MILESTONE-AUDIT.md` -- archived v2.7 milestone audit
- `.aidesigner/runs/2026-04-16T00-05-51-229Z-triggarr-full-dashboard-redesign-v3-/design.html` -- v2.7 design spec (preserved for future reference)
- `.planning/milestones/v2.6-ROADMAP.md` -- archived v2.6 roadmap
- `.planning/codebase/CONCERNS.md` -- v2.8 source audit (2026-05-25); file:line pointers for all 16 v1 requirements

## Session Continuity

Last session: 2026-05-25T00:00:00.000Z
Stopped at: v2.8 roadmap created — ready for `/gsd:plan-phase 64`
Resume file: n/a (roadmap just created)
