# Phase 18: Security & Operations - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Production safety hardening before the tracking feature ships. Four specific capabilities: rate limiting on the search-now endpoint, CSRF/Origin validation on settings POST, a health check endpoint for container orchestrators, and graceful shutdown handling on SIGTERM.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation details are at Claude's discretion. The success criteria are precise and testable — implementation choices should be the simplest approach that satisfies them:

- **Rate limiting**: Window duration, in-memory tracking approach, 429 response format, UI feedback on rejection
- **Origin/CSRF validation**: Allowed origins list, Referer vs Origin header priority, rejection response format
- **Health check**: Response body structure, which dependencies to probe, timeout thresholds
- **Graceful shutdown**: Shutdown order, timeout before force-exit, signal handling approach

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. Requirements doc explicitly notes:
- In-memory timestamp check is sufficient for rate limiting (no slowapi/Redis)
- Origin/Referer validation is the correct CSRF approach (no cookie-based tokens)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 18-security-operations*
*Context gathered: 2026-02-25*
