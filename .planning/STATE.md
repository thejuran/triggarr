---
gsd_state_version: 1.0
milestone: v2.2
milestone_name: Skip Unreleased Media
status: active
stopped_at: null
last_updated: "2026-03-09"
last_activity: 2026-03-09 — Roadmap created for v2.2
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-09)

**Core value:** Reliably trigger searches in Radarr and Sonarr for missing and upgrade-eligible media on a schedule, with closed-loop feedback -- without exposing credentials or expanding attack surface.
**Current focus:** Phase 25 - Filter Foundation

## Current Position

Phase: 25 (1 of 3 in v2.2)
Plan: 0 of ? in current phase
Status: Ready to plan
Last activity: 2026-03-09 -- Roadmap created for v2.2 Skip Unreleased Media

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Overall:**
- Total plans completed: 51 (v1.0: 18, v1.1: 5, v1.2: 8, v2.0: 18, v2.1: 2)
- Milestones shipped: 5 (v1.0, v1.1, v1.2, v2.0, v2.1)

## Accumulated Context

### Decisions

Full decision log in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v2.2 Roadmap]: Null release dates = search anyway (don't blackhole). PITFALLS.md approach over STACK.md.
- [v2.2 Roadmap]: Filter uses digitalRelease and physicalRelease only (NOT inCinemas or status field)
- [v2.2 Roadmap]: Filter goes after filter_monitored, before cursor/slice_batch in pipeline
- [v2.2 Roadmap]: Cutoff-unmet queue is never filtered
- [v2.2 Roadmap]: Sonarr filtering remains unconditional (toggle controls Radarr only)

### Pending Todos

None.

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-03-09
Stopped at: Roadmap created for v2.2 milestone
Resume file: None
