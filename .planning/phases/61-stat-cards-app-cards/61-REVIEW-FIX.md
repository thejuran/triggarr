---
phase: 61-stat-cards-app-cards
fixed_at: 2026-04-15T00:00:00Z
review_path: .planning/phases/61-stat-cards-app-cards/61-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 61: Code Review Fix Report

**Fixed at:** 2026-04-15T00:00:00Z
**Source review:** .planning/phases/61-stat-cards-app-cards/61-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: Unguarded arithmetic on potentially-None stat counts in stats_row.html

**Files modified:** `triggarr/templates/partials/stats_row.html`
**Commit:** 09c0464
**Applied fix:** Wrapped all three count additions (`movies_found + movies_updated`, `episodes_found + episodes_updated`, `albums_found + albums_updated`) with `{% if ... is not none and ... is not none %}` guards, rendering `&mdash;` as fallback. Matches the existing pattern used for `overall_rate` in the same template.

---

### WR-02: Waiting-state connection pill missing visible border

**Files modified:** `triggarr/templates/partials/app_card.html`
**Commit:** 5792913
**Applied fix:** Changed the Waiting pill border from `border-triggarr-border/40` (same opacity as the background) to `border-triggarr-border/20`, giving it a visually distinct border consistent with the Connected (`/20`) and Unreachable (`/20`) pill pattern.

---

### WR-03: test_output_css_contains_mini_bar reads generated file — will fail in clean CI

**Files modified:** `tests/test_stats_health.py`
**Commit:** ed935c5
**Applied fix:** Renamed the test to `test_css_has_mini_bar_rule` and changed it to read `input.css` (the source file) instead of the generated `output.css`. The test now asserts both `.mini-bar` presence and `height: 6px`, consistent with the other CSS rule tests in `test_app_cards.py`.

---

_Fixed: 2026-04-15T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
