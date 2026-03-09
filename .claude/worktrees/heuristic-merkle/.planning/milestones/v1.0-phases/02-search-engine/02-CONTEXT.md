# Phase 2: Search Engine - Context

**Gathered:** 2026-02-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Automated search cycling through Radarr and Sonarr wanted and cutoff-unmet lists. Fetcharr fetches item lists, cycles through them via round-robin with persisted cursors, triggers search commands, and logs activity. Sonarr searches at season level. Web UI and Docker packaging are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Cycle refresh behavior
- Re-fetch item lists from *arr at the start of every cycle — always current, grabbed items disappear immediately
- Cursor stores a position index (not item ID) — simple, predictable, self-correcting on wrap
- On wrap past end of list, cursor resets to 0 silently — no log entry for wrap events
- Missing and cutoff-unmet run on the same timer per app, interleaved — one interval triggers a batch of missing then a batch of cutoff-unmet

### Default tuning
- Default search interval: 30 minutes per app
- Default batch size: 5 items per queue per cycle
- Radarr and Sonarr share the same defaults but are independently configurable
- First search cycle runs immediately on startup — no waiting for the first interval

### Mid-cycle error handling
- Individual item search failure: skip and continue — log the failure, advance cursor past it, search remaining items in batch
- *arr unreachable mid-cycle: abort entire cycle, try again at next interval — no retry loop
- On abort, cursor stays in place — next successful cycle picks up exactly where this one left off
- Radarr and Sonarr cycles are independent — one app failing does not block the other

### Search log detail
- Keep last 50 entries in state file (bounded, oldest evicted)
- Each entry contains: item name, timestamp, app (Radarr/Sonarr), queue type (missing/cutoff-unmet)
- Sonarr entries show "Show Title - Season N" format (e.g., "Breaking Bad - Season 3")
- Log entries go to both stdout (structured logging) and state file (for Web UI in Phase 3)

### Claude's Discretion
- Exact APScheduler job configuration and lifespan wiring
- Internal data structures for queue management
- Structured logging format details
- State file schema evolution from Phase 1

</decisions>

<specifics>
## Specific Ideas

- Search cycle should feel like Huntarr/Searcharr — fire-and-forget search commands, let *arr handle the rest
- Stdout logging should be useful in `docker logs` — one line per searched item, scannable
- State file is the single source of truth for cursor positions and search history

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-search-engine*
*Context gathered: 2026-02-23*
