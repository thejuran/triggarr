# Quick Task 261022-l7h: Fix card reasons label for skip-only rows - Context

**Gathered:** 2026-10-22
**Status:** Ready for planning

<domain>
## Task Boundary

Fix the dashboard card's expandable detail label: when a Partial or Failed cycle's only detail rows are skip-only (malformed-record skip or unevaluated-queue) rows and there are zero actual failures, the summary text must not say "failure reason(s)". Write the failing regression test first (in tests/test_app_cards.py, using the Phase 80-style skip-only Partial cycle fixture), then change only the label wording in triggarr/templates/partials/cycle_grade.html so skip-only rows are never called failures. Keep the existing row text (e.g. "1 missing-queue record skipped — malformed data") and the existing grade colors (success/partial/failed) unchanged.

Owner-approved as the Phase 83 quick-task demonstration (83-QUICK-PROPOSAL.md, "Owner decision", 2026-10-22 15:15 EDT).

</domain>

<decisions>
## Implementation Decisions

### Skip-only label wording
- When every detail row is a skip-only row (zero actual failures), the link reads "Show 1 skipped record" (singular) / "Show N skipped records" (plural). Owner selected this wording.

### Mixed failure + skip rows
- When the list contains at least one real failure, keep today's wording "Show N failure reason(s)" unchanged. Only skip-only lists change. Owner selected the minimal change.

### Unevaluated-queue rows (owner decision after plan check)
- With 0 failures, when the list includes any unevaluated-queue row (alone, or mixed with malformed-record skips), the link reads "Show 1 detail" / "Show N details", where N = number of rows. Only lists made up solely of malformed-record skips use "Show N skipped record(s)". Any real failure keeps "Show N failure reason(s)". Owner selected the neutral wording on 2026-10-22 after the plan checker flagged that unevaluated-queue rows are in the task boundary.

### Claude's Discretion
- How skip-only rows are detected in the template (use existing row/cycle data; no new backend fields unless the template cannot tell rows apart).

</decisions>

<specifics>
## Specific Ideas

- Reproduction: a Partial cycle "1 accepted, 0 failed" whose only detail row is "1 missing-queue record skipped — malformed data" currently renders "Show 1 failure reason" (83-QUICK-PROPOSAL.md).
- Row text and grade colors (success/partial/failed) stay byte-identical.
- Test first: the regression test must fail against the current template before the template changes.

</specifics>

<canonical_refs>
## Canonical References

- `.planning/phases/83-paired-bm-codex-review-risk-based-depth/83-QUICK-PROPOSAL.md` — reproduction evidence and owner decision
- `triggarr/templates/partials/cycle_grade.html` — the label
- `tests/test_app_cards.py` — existing card render tests and Phase 80-style fixtures

</canonical_refs>
