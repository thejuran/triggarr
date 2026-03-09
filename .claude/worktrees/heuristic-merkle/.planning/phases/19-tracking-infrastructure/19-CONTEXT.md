# Phase 19: Tracking Infrastructure - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Isolated, testable components for polling grab history from Radarr and Sonarr and correlating grabs to fetcharr-triggered searches. No wiring into search cycles (Phase 20), no dashboard display (Phase 21), no DB outcome updates (Phase 20).

</domain>

<decisions>
## Implementation Decisions

### Correlation matching
- Most recent search gets credit when multiple searches exist for the same item within the tracking window
- Use the configurable `tracking_window` from GeneralConfig as the single source of truth (no hardcoded fallback)
- Inclusive boundary: `grab_time <= search_time + window` (grabs at exactly the boundary still match)
- Pure functions only — take search records + grab history in, return match results out. No DB writes. Phase 20 handles integration and outcome updates.
- Return grab count per item (not just matched/unmatched) so Phase 20 can determine grabbed/partial/unresolved status

### Sonarr episode granularity
- Series-level matching: correlate by series ID, not season number. Any grab for that series within the window counts.
- Season pack grabs cover all missing episodes — one grab satisfies the search if it covers the series
- Missing and cutoff-unmet searches treated identically — a grab is a grab regardless of search type

### History event filtering
- Only the "grabbed" event type counts. No downloadFolderImported or other events.
- Per-item queries: use `/history?movieId=X` (Radarr) and `/history?seriesId=X` (Sonarr) with eventType filter
- Reuse existing httpx.AsyncClient instances from RadarrClient/SonarrClient — shared connection pool, timeouts, API key handling
- Handle pagination using configurable pageSize from Phase 17

### Component structure
- History polling methods added to existing RadarrClient and SonarrClient classes (e.g., `get_grab_history`)
- Pure correlation functions in new `fetcharr/correlation.py` module — no I/O, easy to test
- Pydantic models for data structures (GrabEvent, CorrelationResult, etc.) — matches project convention
- Synthetic test data for unit tests — hand-crafted minimal fixtures, no real API responses

### Claude's Discretion
- Exact Pydantic model field names and structure
- Pagination implementation details
- Test helper organization
- Correlation function signatures beyond the described contract

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 19-tracking-infrastructure*
*Context gathered: 2026-02-25*
