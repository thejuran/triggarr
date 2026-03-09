# Phase 20: Tracking Integration - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the tracking infrastructure (Phase 19's history polling clients and correlation functions) into the search cycle so that search history entries automatically update from "searched" to their terminal outcome (grabbed/partial/unresolved). Increment lifetime stats atomically with outcome changes. The dashboard display of these outcomes is Phase 21.

</domain>

<decisions>
## Implementation Decisions

### State transitions
- One-way only: states move forward, never backwards
- Radarr: binary outcome — searched -> grabbed OR searched -> unresolved
- Sonarr: three-state — searched -> partial -> grabbed OR searched -> unresolved
- Partial -> grabbed is allowed: keep checking partial entries until the tracking window expires; if all episodes resolve, upgrade to grabbed
- Unresolved triggers on tracking window expiry only — no removal/blacklist detection

### Lifetime stat increments
- Increment on terminal state only (grabbed or partial), not on first detection
- Partial counts: if 3 of 5 Sonarr episodes are grabbed, add 3 to episodes_found
- Separate counters: distinguish "found" (from wanted/missing searches) vs "updated" (from cutoff-unmet searches) per STATS-03/04
- Atomic: update outcome + increment stats in the same DB transaction

### Failure & retry behavior
- Log tracking failures as warning level (visible in default logs, non-fatal)
- Retry within tracking window: failed entries stay "searched" and get re-polled each cycle until window expires — no explicit retry counter
- Cycle completes normally even if all tracking polls fail — searches proceed, entries stay "searched"
- Trust Phase 17's tracking-aware pruning guard — no extra defensive checks needed

### Claude's Discretion
- Poll scheduling: how tracking checks fit into the search cycle (after each search, end of cycle, separate task)
- Exact DB query patterns for finding trackable entries and updating outcomes
- Error handling implementation details (httpx.HTTPError + pydantic.ValidationError per CLAUDE.md)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches that match the existing codebase patterns (loguru, atomic writes, pytest-asyncio).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 20-tracking-integration*
*Context gathered: 2026-02-25*
