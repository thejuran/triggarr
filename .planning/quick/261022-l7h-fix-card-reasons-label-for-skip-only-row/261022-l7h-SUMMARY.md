---
phase: quick-261022-l7h
plan: 01
subsystem: ui
tags: [jinja2, fastapi, htmx, dashboard-card, template]

requires: []
provides:
  - "Three-way dashboard card detail label (failure reason(s) / skipped record(s) / detail(s))"
affects: []

tech-stack:
  added: []
  patterns:
    - "Jinja namespace row classification before a <details>/<summary> block, to branch label wording without touching backend data"

key-files:
  created: []
  modified:
    - tests/test_app_cards.py
    - triggarr/templates/partials/cycle_grade.html

key-decisions:
  - "D-01: skip-only label reads 'Show N skipped record(s)' where N = malformed_skipped (records), not row count"
  - "D-02: any real failure or fetch failure keeps 'Show N failure reason(s)' unchanged"
  - "D-03: row text and grade colors stay byte-identical"
  - "D-04: 0-failure cycles with any unevaluated-queue row read 'Show N detail(s)' where N = reason_count (rows)"
  - "DISC-01: template-only fix; triggarr/search/outcome.py untouched"
  - "DISC-03: skipped-record N counts records (malformed_skipped), not rows"

patterns-established:
  - "Row-text classification by prefix/suffix inside the template, guarded by a Jinja namespace, avoids adding a new backend field for a presentation-only distinction"

requirements-completed: [QUICK-261022-l7h]

duration: 10min
completed: 2026-10-22
---

# Quick Task 261022-l7h: Fix card reasons label for skip-only rows Summary

**Dashboard card's expandable detail label now distinguishes three cases — real failures, malformed-record skips, and unevaluated queues — instead of always saying "failure reason(s)".**

## Performance

- **Duration:** ~10 min (RED commit `7da265f` to GREEN commit `e0e72ba`, plus setup/review)
- **Completed:** 2026-10-22
- **Tasks:** 2 (RED test commit, GREEN fix commit)
- **Files modified:** 2 (`tests/test_app_cards.py`, `triggarr/templates/partials/cycle_grade.html`)

## Accomplishments

- A Partial cycle whose only detail row is a malformed-record skip (e.g. "1 accepted, 0 failed" with "1 missing-queue record skipped — malformed data") now renders "Show 1 skipped record" instead of "Show 1 failure reason".
- A 0-failure cycle with any unevaluated-queue row (alone or mixed with malformed skips) renders "Show N detail(s)", N = row count — this reaches Success-grade cards too, since `has_detail` can be true on a green card with unevaluated rows.
- Any cycle with a real failure (`failed > 0`) or a fetch failure keeps the unchanged "Show N failure reason(s)" label, exactly as before.
- Row text and all three grade colors (`text-triggarr-green` / `text-amber-400` / `text-triggarr-danger`) are byte-identical to before the change.

## The three label rules as shipped

1. **Any real failure or fetch failure** (`failed > 0` or `fetch_failed`), or any row that isn't a recognized skip/unevaluated row (the "other" classification — see below) -> **"Show N failure reason(s)"**, N = `reason_count` (rows). Unchanged from before this task (D-02).
2. **0 failures, and the list includes at least one unevaluated-queue row** (a row starting with `"Missing queue not evaluated: "` or `"Cutoff unmet queue not evaluated: "`), whether alone or mixed with malformed-skip rows -> **"Show N detail(s)"**, N = `reason_count` (rows) (D-04).
3. **0 failures, and every row is a malformed-record skip row** (ends with `"— malformed data"` or `"skipped"`, no unevaluated rows present) -> **"Show N skipped record(s)"**, N = `malformed_skipped` (records, not rows) (D-01).

Implementation: a Jinja `namespace(malformed=0, unevaluated=0, other=0)` loop classifies each row in `app.last_cycle.reasons` by its text (prefix check for unevaluated rows, then suffix check for malformed rows, else "other"). `no_failure = failed == 0 and not fetch_failed and ns.other == 0`. The `<summary>` becomes an if/elif/else: unevaluated-detail branch first, then skipped-record branch, then the original failure-reason line unchanged. See `triggarr/templates/partials/cycle_grade.html`.

## DISC-03 note: N counts records, not rows

The skipped-record count intentionally reads `app.last_cycle.malformed_skipped` (the record count), not `reason_count` (the row count). One per-queue malformed row can represent multiple records — e.g. `malformed_by_queue={"missing": 2, "cutoff": 1}` produces 2 rows but 3 records, and the card reads **"Show 3 skipped records"**, confirmed by `test_card_skip_only_plural_counts_records_not_rows`. The details-label branch (rule 2) deliberately counts the opposite way — rows (`reason_count`), per the owner's D-04 decision — since an unevaluated-queue row has no natural "record" count.

## Unchanged-by-design: eligible-not-searched row

A Failed cycle whose only row is `"N eligible item(s) not searched this cycle"` (produced only when `accepted=0, failed=0`, no unevaluated rows, and `malformed_skipped=0`) keeps "Show N failure reason(s)" — this row is classified as "other" (it matches neither the unevaluated prefix nor the malformed-skip suffix), so `no_failure` evaluates false and the unchanged failure-label branch fires. This was outside the owner's task boundary (it is neither a skip nor an unevaluated-queue row). Locked by `test_card_eligible_not_searched_row_keeps_failure_label`, added per the plan-check addition — this test passes both before and after the fix, confirming the "other" path was never broken by this change.

## Rejected alternative

**Backend `skip_only`/row-type flag in `cycle_view()`.** RESEARCH.md's primary recommendation and the plan's DISC-01 both rejected adding a new field to `triggarr/search/outcome.py`'s `cycle_view()` return dict. The template can already tell every row type apart from its fixed, already-sanitized wording (unevaluated-queue prefixes, malformed-skip suffixes), and the owner's task boundary was explicitly "change only the label wording in `cycle_grade.html`". Adding a backend field would have been a correct but unnecessarily broader change for a presentation-only distinction; `git diff HEAD~2 -- triggarr/search/outcome.py` confirms that file is untouched.

## Task Commits

Both tasks were committed atomically, each a RED/GREEN pair per the plan's TDD gate:

1. **Task 1 (RED): Add failing regression tests for the three-way card label** - `7da265f` (test)
2. **Task 2 (GREEN): Make the summary label three-way in cycle_grade.html** - `e0e72ba` (fix)

## Files Created/Modified

- `tests/test_app_cards.py` - 10 new regression tests (9 from the plan + 1 plan-check addition) locking the three-way label and the unchanged eligible-not-searched "other" path
- `triggarr/templates/partials/cycle_grade.html` - row classification namespace + three-way `<summary>` if/elif/else, replacing the single always-"failure reason(s)" line

## Decisions Made

All decisions were locked in CONTEXT.md (D-01..D-04, DISC-01, DISC-03) before execution; none required new judgment calls during implementation. See "key-decisions" above and the full rationale in CONTEXT.md / RESEARCH.md.

## Deviations from Plan

None - plan executed exactly as written, including the orchestrator's plan-check addition (one extra regression test for the eligible-not-searched "other" path, added to Task 1 and confirmed passing both before and after the Task 2 fix).

## Issues Encountered

None. RED run showed the predicted 7 failed / 3 passed split (2 plan-specified keep-failure-label tests plus the 1 plan-check addition, which is designed to pass unconditionally). GREEN run showed all 84 tests in `tests/test_app_cards.py` passing (74 baseline + 10 new).

## Verification Evidence

- RED: `uv run pytest tests/test_app_cards.py -q -k "skip_only or details_label or mixed_failure or eligible_not_searched"` -> 7 failed, 3 passed (against the unchanged template, commit `7da265f`).
- GREEN: `uv run pytest tests/test_app_cards.py -x -q` -> 84 passed (commit `e0e72ba`).
- Full suite: `uv run pytest tests/ -x -q` -> 2215 passed.
- Lint: `uv run ruff check triggarr/ tests/` -> All checks passed.
- `git diff HEAD~2 -- triggarr/search/outcome.py` -> empty (template-only, DISC-01 honored).
- `git log --format=%s -2` -> both commit subjects contain `261022-l7h`.
- Template diff reviewed manually: the `<details data-cycle-detail` line, the `<li>` row loop, and the grade-color `if`/`elif` chain (lines 1-13) are unchanged; only the row-classification block and the `<summary>` if/elif/else were added (D-03 honored).
- No untracked files after either commit (`git status --short`); no accidental file deletions (`git diff --diff-filter=D` empty for both commits).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Quick task complete. No follow-on work identified; the owner's task boundary (skip-only and unevaluated-queue rows no longer labeled as failures) is fully closed. This SUMMARY, STATE.md, and ROADMAP.md updates are left to the orchestrator per this task's constraints.

## Self-Check: PASSED

- FOUND: tests/test_app_cards.py
- FOUND: triggarr/templates/partials/cycle_grade.html
- FOUND: .planning/quick/261022-l7h-fix-card-reasons-label-for-skip-only-row/261022-l7h-SUMMARY.md
- FOUND: commit 7da265f (test)
- FOUND: commit e0e72ba (fix)

---
*Phase: quick-261022-l7h*
*Completed: 2026-10-22*
