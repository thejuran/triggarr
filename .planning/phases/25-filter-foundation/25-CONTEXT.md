# Phase 25: Filter Foundation - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Config model field (`skip_unreleased` on GeneralConfig) and pure filter functions for identifying unreleased Radarr movies, with comprehensive edge-case tests. No UI changes, no engine wiring — those are Phase 26.

</domain>

<decisions>
## Implementation Decisions

### Release date logic
- Use `digitalRelease` and `physicalRelease` fields only (NOT `inCinemas` or `status`)
- A movie is "released" if either date is in the past (whichever comes first)
- Movies with null/missing dates for both fields pass through (searched, not blackholed)
- Date parsing uses `datetime.fromisoformat()` with Z replacement, matching existing Sonarr pattern

### Filter scope
- Filter applies to Radarr missing queue ONLY — cutoff queue items already have files
- Sonarr unaired-episode filtering (`filter_sonarr_episodes`) stays unconditional and unchanged
- Filter placement (Phase 26): after `filter_monitored`, before cursor/`slice_batch`

### Config field
- `skip_unreleased: bool = True` on `GeneralConfig` in models/config.py
- Default: enabled (skip unreleased) — searching unreleased media is almost always undesirable

### Claude's Discretion
- Default config template presentation (commented vs active in DEFAULT_CONFIG)
- Filter function naming convention (following existing patterns)
- Logging verbosity for skipped items
- Test strategy and edge case coverage

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `filter_sonarr_episodes()` at engine.py:145-173: Direct pattern to follow — monitors + air date filtering in one function, uses `datetime.fromisoformat()` with Z replacement
- `filter_monitored()` at engine.py:70-81: Simpler filter pattern, list comprehension style

### Established Patterns
- Date parsing: `datetime.fromisoformat(str.replace("Z", "+00:00"))` with try/except for ValueError/AttributeError
- Config model: Pydantic BaseModel fields with defaults on `GeneralConfig` (models/config.py:56-66)
- DEFAULT_CONFIG template: Commented-out optional fields with descriptions (config.py:13-44)
- Pure filter functions: Take list[dict], return list[dict], no side effects

### Integration Points
- `GeneralConfig` in models/config.py — add `skip_unreleased` field
- `DEFAULT_CONFIG` in config.py — add commented config line
- `run_radarr_cycle()` in engine.py — Phase 26 will wire filter between `filter_monitored` (line 241) and `slice_batch` (line 243)
- Settings save in routes.py — Phase 26 will add form field parsing

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. User's original motivation: avoid cam recordings and mismarked trailers from unreleased media searches.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 25-filter-foundation*
*Context gathered: 2026-03-09*
