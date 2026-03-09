# Phase 16: Deep Code Review - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix the 7 warning-level issues (W1-W5, W7, W8) identified in 16-REVIEW.md from the v1.2 code review. Update the review doc with resolution status. Medium and filtered issues are deferred to the next milestone.

</domain>

<decisions>
## Implementation Decisions

### Fix scope
- Fix 7 of 8 warning-level (80+) issues: W1, W2, W3, W4, W5, W7, W8
- W6 (redundant Exception in except tuple) is **won't-fix** — the broad catch is intentional safety in a network client
- Medium issues (M1-M8) and filtered issues (<70) are noted for next milestone backlog, not fixed here

### Fix approach
- Follow the suggested diffs from 16-REVIEW.md as the starting point; adjust only if they don't compile or work
- Light cleanup of directly adjacent code is allowed (unused imports, formatting) but no broader refactoring
- Claude audits all templates for similar single-quote `hx-vals` patterns when fixing W1 (XSS) — fix any found

### Testing
- Add regression tests for security fixes only: W1 (XSS in hx-vals) and W7 (SSRF blocklist gaps)
- Other fixes validated by existing test suite passing (`pytest tests/ -x`)

### Ordering & batching
- Claude decides plan grouping (by file, by category, or single plan) for maximum efficiency
- Claude decides commit granularity (separate security commits vs batched)
- After all fixes applied: update 16-REVIEW.md to mark each issue as Fixed, Won't Fix, or Deferred

### Claude's Discretion
- Plan grouping strategy and commit granularity
- Whether to fix additional single-quote hx-vals patterns found during W1 audit
- Light cleanup scope when touching files

</decisions>

<specifics>
## Specific Ideas

- W6 stays as-is because the broad `except Exception` is an intentional safety net in the Sonarr client — unexpected errors should be caught, not propagated
- 16-REVIEW.md should become a living record: each issue marked Fixed, Won't Fix, or Deferred with brief rationale

</specifics>

<deferred>
## Deferred Ideas

- Medium issues (M1-M8) — backlog for next milestone
- Filtered issues (<70): type hints (5), test patterns (3), architectural suggestions (4), container hardening (2) — backlog for next milestone

</deferred>

---

*Phase: 16-deep-code-review*
*Context gathered: 2026-02-24*
