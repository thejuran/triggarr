# Phase 90: Removed-Instance Pending-Search Lifecycle - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-18
**Phase:** 90-removed-instance-pending-search-lifecycle
**Areas discussed:** Radarr/Lidarr too?, How it reads in History, Effect on stats, How long they're kept

---

## Radarr/Lidarr too?

| Option | Description | Selected |
|--------|-------------|----------|
| All three apps (Recommended) | Same close-out and same-name protection for Sonarr, Radarr and Lidarr; widens the phase beyond the requirement wording | ✓ |
| Sonarr only, backlog the rest | Keep phase as written; record Radarr/Lidarr same-name problem in the backlog | |
| Close-out for all, protection Sonarr only | Close-out for all three; leave Radarr/Lidarr name-based lookup alone | |

**User's choice:** All three apps.

## How it reads in History

| Question | Options | Selected |
|----------|---------|----------|
| Badge text | "Instance removed" (tooltip explains) / "Instance removed — not tracked" | Instance removed |
| Badge style | Same gray as Legacy, different words / Own distinct color | Same gray |
| Outcome filter | Add "Instance removed" option / No filter option | Add it |

## Effect on stats

| Question | Options | Selected |
|----------|---------|----------|
| Grab rate | Leave them out / Count as no grab | Leave them out |
| Removed instance's lifetime stats | Leave as-is / Delete on removal | Leave as-is |

## How long they're kept

| Question | Options | Selected |
|----------|---------|----------|
| Retention | Age out normally / Keep forever | Age out normally |
| Last grab check before closing | No, close immediately / Try one check first | Close immediately |

## Claude's Discretion

- Mechanism (real terminal outcome expected), consolidation of the shared pending-outcome rule, startup sweep shape, `grab_ownership` handling, log wording, test structure.
- Close-out timing (on removal plus a startup sweep) was proposed by Claude and not contested.

## Deferred Ideas

None.
