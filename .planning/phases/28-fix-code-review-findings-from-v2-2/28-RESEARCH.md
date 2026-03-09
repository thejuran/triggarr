# Phase 28: Fix Code Review Findings from v2.2 - Research

**Researched:** 2026-03-09
**Domain:** Code review / bug fix / quality hardening
**Confidence:** HIGH

## Summary

Phase 28 addresses code review findings from the v2.2 (Skip Unreleased Media) milestone, which added 3 phases (25-27) modifying 8 source files and adding 30 tests. The v2.2 changes are well-tested (300 tests passing, lint clean) but contain one correctness bug in the skip badge math, a minor template structure issue, and an opportunity to address some deferred findings from the Phase 16 deep review that touch the same files.

The primary finding is a **misleading skip badge count**: the dashboard shows "N skipped (unreleased)" where N includes both unmonitored and unreleased items, since `missing_count` captures raw API count before any filtering, while `missing_eligible` captures post-filter count. The label claims it is only unreleased, which is incorrect when unmonitored items exist.

**Primary recommendation:** Fix the skip badge math by tracking a `missing_monitored` count (post-filter_monitored, pre-filter_unreleased) so the skip count accurately reflects only unreleased items, then address the minor template and deferred findings.

## Findings

### F1. Skip Badge Math Includes Unmonitored Items (BUG)

**Severity:** Medium-High (incorrect user-facing data)
**Confidence:** HIGH
**Files:** `triggarr/search/engine.py:271,292-295`, `triggarr/templates/partials/app_card.html:50-51`

**What is wrong:** `state["radarr"]["missing_count"]` is set at line 271 to the raw API response count (before `filter_monitored`). `state["radarr"]["missing_eligible"]` is set at line 295 after both `filter_monitored` AND `filter_unreleased_movies`. The template computes `missing_count - missing_eligible` and labels it "N skipped (unreleased)".

If there are unmonitored items, the difference includes them too, but the badge falsely attributes the entire difference to unreleased filtering.

**Example:** 50 raw items, 42 monitored, 30 released. Badge shows "20 skipped (unreleased)" when only 12 are actually unreleased skips.

**Fix:** Track a `missing_monitored` count after `filter_monitored` but before `filter_unreleased_movies`. Use `missing_monitored - missing_eligible` for the skip badge. Alternatively, rename the badge to be more generic, but specific counts are more useful.

### F2. Settings Template Description Text Placement (MINOR)

**Severity:** Low (cosmetic)
**Confidence:** HIGH
**File:** `triggarr/templates/settings.html:62-71`

The skip_unreleased checkbox is in a `<div class="flex items-center gap-3 mt-2">` (lines 62-68), but the description `<p>` text (lines 69-71) is a sibling outside this div, sitting as a separate child of the grid column. This means the description text doesn't visually associate well with the checkbox on narrow screens. All other settings use `<label>` + `<input>` + `<p>` within a single `<div>`.

**Fix:** Wrap the checkbox div and description `<p>` in a container div, matching the pattern used by other settings (e.g., the Tracking Window field at lines 55-61).

### F3. Sonarr Eligible/Total Display Mixes Units (COSMETIC)

**Severity:** Low (confusing display, not incorrect)
**Confidence:** HIGH
**Files:** `triggarr/search/engine.py:422,444-445`, `triggarr/templates/partials/app_card.html:35-36`

For Sonarr, `missing_count` = raw episode count, but `missing_eligible` = deduplicated season count. The display shows "2 of 15 items" which mixes seasons and episodes. Pre-v2.2 just showed "15 items" (episodes only). The cursor progress line at line 44 now uses `missing_eligible` (seasons), which is correct since the cursor iterates over seasons.

**Fix options:**
1. Track `missing_monitored` for Sonarr as well (episode count after `filter_sonarr_episodes`) and display that as the "of N" denominator, keeping `missing_eligible` (seasons) for cursor progress.
2. Accept the current display since the cursor progress is correct and the "X of Y" gives a rough sense of reduction.

**Recommendation:** Option 2 (accept as-is) -- the display is slightly confusing but not incorrect per se, and "fixing" it would add complexity without clear user value. The Sonarr card doesn't show a skip badge, so there's no misleading label.

### F4. No INFO-Level Summary of Unreleased Skip Count (ENHANCEMENT)

**Severity:** Low (observability gap)
**Confidence:** HIGH
**File:** `triggarr/search/engine.py:220-223`

Individual skips are logged at DEBUG level (appropriate). But there's no summary log at INFO level showing how many items were filtered. The cycle summary at line 364-370 doesn't mention filtered items. Adding a one-line INFO log when items are actually skipped would improve observability without noise.

**Fix:** After line 294 (`missing = filter_unreleased_movies(missing)`), log at INFO level if any items were actually filtered:
```python
skipped_unreleased = pre_filter_count - len(missing)
if skipped_unreleased > 0:
    logger.info("Radarr: {n} unreleased movies skipped", n=skipped_unreleased)
```

### F5. Deferred Phase 16 Findings Still Open

The following Medium-priority findings from Phase 16 remain unaddressed and touch related code areas:

| ID | Finding | File | Severity |
|----|---------|------|----------|
| M1 | Stored XSS defense: `entry.detail` in title attribute missing `\| e` | templates/partials/search_log.html, history_results.html | 72 |
| M3 | `contextlib.suppress(Exception)` too broad in migration | db.py:61-64 | 78 |
| M5 | `print()` instead of Loguru in config.py | config.py:90 | 78 |
| M6 | `callable` lowercase return type annotation | search/scheduler.py:75 | 78 |

**Recommendation:** Fix M3, M5, M6 in this phase since they are small, mechanical fixes. Defer M1 if the autoescaping already covers it (it does -- Jinja2 autoescaping handles title attributes).

## Architecture Patterns

### State Field Naming Convention

The codebase uses a consistent pattern for AppState fields:
- `missing_count` / `cutoff_count` -- raw API totals (pre-filter)
- `missing_cursor` / `cutoff_cursor` -- batch position
- `missing_pass` / `cutoff_pass` -- wrap-around counter
- `missing_eligible` -- post-filter count (new in v2.2)

The fix for F1 should add `missing_monitored` to track the intermediate count (post-filter_monitored, pre-filter_unreleased), following this naming convention.

### Template Conditional Pattern

Skip badge uses a multi-condition guard:
```jinja2
{%- if app.skip_unreleased and app.name == 'radarr' and app.missing_eligible is not none and app.missing_count is not none and app.missing_eligible < app.missing_count %}
```

After the F1 fix, this condition should use `missing_monitored` instead of `missing_count`:
```jinja2
{%- if app.skip_unreleased and app.name == 'radarr' and app.missing_eligible is not none and app.missing_monitored is not none and app.missing_eligible < app.missing_monitored %}
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| XSS escaping | Custom filter | Jinja2 autoescaping (already enabled) | Framework handles all contexts |
| Atomic writes | Manual file IO | tempfile + os.replace pattern (already in codebase) | Crash-safe by design |

## Common Pitfalls

### Pitfall 1: State Migration for New Fields

**What goes wrong:** Adding new fields to AppState TypedDict without ensuring `_merge_defaults` handles them.
**Why it happens:** `total=False` on TypedDict means fields are optional, but `_default_state()` only sets explicit defaults.
**How to avoid:** New fields with `None` default are safe (dict `.get()` returns None). Only set explicit defaults in `_default_state()` if a non-None default is needed.
**Impact on F1:** `missing_monitored` can use `.get()` with None default -- no state migration needed.

### Pitfall 2: Template Condition Ordering

**What goes wrong:** Jinja2 short-circuit evaluation -- putting `app.missing_monitored is not none` after arithmetic on it would cause a template error.
**How to avoid:** Always check `is not none` before using the value in arithmetic.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (auto mode) |
| Config file | pyproject.toml |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements to Test Map

| Finding | Behavior | Test Type | Automated Command | File Exists? |
|---------|----------|-----------|-------------------|-------------|
| F1 | Skip badge shows only unreleased count | unit | `uv run pytest tests/test_web.py::test_app_card_skip_indicator_shown -x` | Needs update |
| F1 | missing_monitored tracked in engine state | unit | `uv run pytest tests/test_search.py -k "eligible" -x` | Needs update |
| F2 | Settings checkbox styling | manual | Visual inspection | N/A |
| F4 | INFO log for skipped unreleased count | unit | `uv run pytest tests/test_search.py -k "unreleased" -x` | New test |
| M3 | Suppress narrowed to OperationalError | unit | `uv run pytest tests/ -x -q` | Existing coverage |
| M5 | No print() calls | lint | `uv run ruff check triggarr/ --select T201` | N/A |
| M6 | Callable type annotation | lint | `uv run ruff check triggarr/ --select UP006` | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q && uv run ruff check triggarr/ tests/`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. Tests need updating (not creation from scratch).

## Sources

### Primary (HIGH confidence)
- Direct code review of v2.2 diff (git diff 1b03471..cb4033d)
- Phase 16 deep review document (.planning/phases/16-deep-code-review/16-REVIEW.md)
- Phase 25/26/27 verification reports

## Metadata

**Confidence breakdown:**
- Findings (F1-F5): HIGH -- verified by reading actual source code and tracing data flow
- Fix approaches: HIGH -- follows established codebase patterns
- Deferred findings: HIGH -- documented in Phase 16 review with specific file/line references

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable codebase, no external dependencies in scope)
