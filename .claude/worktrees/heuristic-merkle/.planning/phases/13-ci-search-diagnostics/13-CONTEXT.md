# Phase 13: CI & Search Diagnostics - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Push CI to GitHub remote runners so all tests pass on GitHub Actions, and add diagnostic logging to search cycles for troubleshooting. CI workflow already exists at `.github/workflows/ci.yml` with test, lint, and Docker build jobs — this phase ensures it works on remote runners. Search diagnostics add API version detection and per-cycle summary logging.

</domain>

<decisions>
## Implementation Decisions

### Diagnostic log content
- Log cycle duration for every search cycle (e.g., "Radarr missing cycle completed in 4.2s")
- Log summary breakdown per cycle: items fetched, searched, skipped — not just raw total count
- All diagnostic logs at INFO level (always visible, no opt-in needed)
- Both Radarr and Sonarr get the same diagnostic treatment — consistent logging across both apps and all queue types (missing + cutoff)

### Version detection fallback
- Detect Sonarr API version once at startup only — no periodic re-checking
- If version detection fails (unreachable, unexpected response): log a warning and assume v3, continue running
- Purely informational logging — no behavior differences based on detected version
- Version only visible in logs — not exposed in API status or dashboard (dashboard is Phase 14's territory)

### CI pass criteria
- All three jobs (test, lint, Docker build) required to pass for PRs
- Single Python version: 3.13 only (matches Docker target)
- No coverage tracking or thresholds
- No Tailwind CSS build verification in CI (CSS is committed)

### Claude's Discretion
- Exact log message formatting and structure
- How to detect Sonarr v3 vs v4 (endpoint probing strategy)
- CI workflow caching strategy (uv cache, Docker layer cache)
- Branch protection rule configuration details

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-ci-search-diagnostics*
*Context gathered: 2026-02-24*
